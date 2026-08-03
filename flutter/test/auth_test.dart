import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:jsh_flutter/auth.dart';

/// 메모리 저장소 — 실제 Keychain/Keystore 없이 돌리기 위한 대체품.
class _MemoryStorage implements AuthStorage {
  String? refreshToken;
  int clearCount = 0;

  _MemoryStorage([this.refreshToken]);

  @override
  Future<String?> readRefreshToken() async => refreshToken;

  @override
  Future<void> writeRefreshToken(String token) async => refreshToken = token;

  @override
  Future<void> clear() async {
    refreshToken = null;
    clearCount++;
  }

  @override
  Future<String> deviceId() async => 'device-test';
}

/// 경로별로 응답을 미리 정해 두는 가짜 HTTP 어댑터.
///
/// 응답은 `queue`에서 차례로 꺼낸다 — 같은 경로에 대해 401 → 200처럼
/// 호출 순서에 따라 달라지는 시나리오를 만들 수 있다.
class _FakeAdapter implements HttpClientAdapter {
  final Map<String, List<_Reply>> queues;
  final List<String> calls = [];

  /// 리프레시 응답을 늦추고 싶을 때 쓴다 — single-flight 검증에 필요하다.
  Completer<void>? gate;

  _FakeAdapter(this.queues);

  int callsTo(String path) => calls.where((c) => c == path).length;

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    calls.add(options.path);
    if (options.path == '/auth/mobile/refresh' && gate != null) {
      await gate!.future;
    }

    final queue = queues[options.path];
    if (queue == null || queue.isEmpty) {
      return ResponseBody.fromString('{}', 404);
    }
    final reply = queue.length == 1 ? queue.first : queue.removeAt(0);
    return ResponseBody.fromString(
      jsonEncode(reply.body),
      reply.status,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

class _Reply {
  final int status;
  final Map<String, dynamic> body;

  const _Reply(this.status, [this.body = const {}]);
}

Dio _dioWith(_FakeAdapter adapter) {
  // validateStatus는 기본값(4xx는 DioException)을 그대로 쓴다 — 프로덕션 Dio와
  // 같은 조건이라야 401 인터셉터가 실제로 검증된다.
  final dio = Dio(BaseOptions(baseUrl: 'https://auth.example.test'));
  dio.httpClientAdapter = adapter;
  return dio;
}

const _rotated = {
  'token': 'access-2',
  'refreshToken': 'refresh-2',
  'expiresIn': 900,
};

void main() {
  test('리프레시가 성공하면 회전된 refresh token이 즉시 저장된다', () async {
    final storage = _MemoryStorage('refresh-1');
    final adapter = _FakeAdapter({
      '/auth/mobile/refresh': [const _Reply(200, _rotated)],
    });
    final api = AuthApiClient(storage, dio: _dioWith(adapter));

    expect(await api.restore(), isTrue);
    expect(storage.refreshToken, 'refresh-2');
    expect(api.accessToken, 'access-2');
  });

  test('401을 받은 요청은 리프레시 후 한 번 재시도한다', () async {
    final storage = _MemoryStorage('refresh-1');
    final adapter = _FakeAdapter({
      '/protected': [
        const _Reply(401),
        const _Reply(200, {'ok': true}),
      ],
      '/auth/mobile/refresh': [const _Reply(200, _rotated)],
    });
    final dio = _dioWith(adapter);
    AuthApiClient(storage, dio: dio);

    final response = await dio.get<dynamic>('/protected');

    expect(response.statusCode, 200);
    expect(adapter.callsTo('/protected'), 2);
    expect(adapter.callsTo('/auth/mobile/refresh'), 1);
  });

  test('동시에 401을 받은 요청 5건이 리프레시를 한 번만 부른다', () async {
    final storage = _MemoryStorage('refresh-1');
    final adapter = _FakeAdapter({
      '/protected': [
        const _Reply(401),
        const _Reply(200, {'ok': true}),
      ],
      '/auth/mobile/refresh': [const _Reply(200, _rotated)],
    })..gate = Completer<void>();
    final dio = _dioWith(adapter);
    AuthApiClient(storage, dio: dio);

    final inFlight = List.generate(5, (_) => dio.get<dynamic>('/protected'));
    // 다섯 요청이 모두 401을 받고 리프레시 대기에 합류할 때까지 이벤트 루프를 돌린다.
    await Future<void>.delayed(Duration.zero);
    adapter.gate!.complete();
    await Future.wait(inFlight);

    expect(adapter.callsTo('/auth/mobile/refresh'), 1);
  });

  test('리프레시가 401이면 저장소를 비우고 세션 만료를 알린다', () async {
    final storage = _MemoryStorage('refresh-1');
    final adapter = _FakeAdapter({
      '/auth/mobile/refresh': [const _Reply(401)],
    });
    final api = AuthApiClient(storage, dio: _dioWith(adapter));

    var expired = false;
    api.onSessionExpired = () => expired = true;

    expect(await api.restore(), isFalse);
    expect(storage.refreshToken, isNull);
    expect(expired, isTrue);
  });

  test('재시도한 요청이 다시 401이어도 무한 루프에 빠지지 않는다', () async {
    final storage = _MemoryStorage('refresh-1');
    final adapter = _FakeAdapter({
      '/protected': [const _Reply(401)],
      '/auth/mobile/refresh': [const _Reply(200, _rotated)],
    });
    final dio = _dioWith(adapter);
    AuthApiClient(storage, dio: dio);

    await expectLater(
      dio.get<dynamic>('/protected'),
      throwsA(
        isA<DioException>().having(
          (e) => e.response?.statusCode,
          'statusCode',
          401,
        ),
      ),
    );
    // 두 번째 401은 그대로 올라간다 — 재시도도 리프레시도 한 번뿐이다.
    expect(adapter.callsTo('/protected'), 2);
    expect(adapter.callsTo('/auth/mobile/refresh'), 1);
  });

  test('네트워크 오류로 리프레시가 실패해도 저장된 토큰은 지우지 않는다', () async {
    final storage = _MemoryStorage('refresh-1');
    final dio = _dioWith(_FakeAdapter(const {}));
    dio.httpClientAdapter = _ThrowingAdapter();
    final api = AuthApiClient(storage, dio: dio);

    expect(await api.restore(), isFalse);
    expect(storage.refreshToken, 'refresh-1');
    expect(storage.clearCount, 0);
  });

  test('저장된 refresh token이 없으면 복원은 조용히 실패한다', () async {
    final adapter = _FakeAdapter(const {});
    final api = AuthApiClient(_MemoryStorage(), dio: _dioWith(adapter));

    expect(await api.restore(), isFalse);
    expect(adapter.calls, isEmpty);
  });

  test('email이 null인 로그인 응답도 파싱된다', () async {
    final storage = _MemoryStorage();
    final adapter = _FakeAdapter({
      '/auth/mobile/kakao': [
        const _Reply(200, {
          'token': 'access-1',
          'refreshToken': 'refresh-1',
          'expiresIn': 900,
          'user': {
            'userId': 7,
            'nickname': '홍길동',
            'email': null,
            'role': 'user',
          },
        }),
      ],
    });
    final api = AuthApiClient(storage, dio: _dioWith(adapter));

    final user = await api.loginWithKakao(
      code: 'code',
      device: const DeviceMeta(
        deviceId: 'device-test',
        deviceName: 'Pixel 8',
        os: 'android',
        appVersion: '1.0.0+1',
      ),
    );

    expect(user.userId, 7);
    expect(user.email, isNull);
    expect(storage.refreshToken, 'refresh-1');
  });

  test('로그인 실패는 서버 원문 대신 한국어 문구로 바뀐다', () async {
    final adapter = _FakeAdapter({
      '/auth/mobile/kakao': [
        const _Reply(401, {'detail': 'kakao code exchange failed'}),
      ],
    });
    final api = AuthApiClient(_MemoryStorage(), dio: _dioWith(adapter));

    await expectLater(
      api.loginWithKakao(
        code: 'code',
        device: const DeviceMeta(
          deviceId: 'device-test',
          deviceName: 'Pixel 8',
          os: 'android',
          appVersion: '1.0.0+1',
        ),
      ),
      throwsA(
        isA<AuthFailure>().having(
          (failure) => failure.message,
          'message',
          isNot(contains('kakao code exchange failed')),
        ),
      ),
    );
  });

  test('로그아웃은 서버 호출이 실패해도 로컬 토큰을 지운다', () async {
    final storage = _MemoryStorage('refresh-1');
    final dio = _dioWith(_FakeAdapter(const {}));
    dio.httpClientAdapter = _ThrowingAdapter();
    final api = AuthApiClient(storage, dio: dio);

    await api.logout();

    expect(storage.refreshToken, isNull);
    expect(api.accessToken, isNull);
  });

  test('모든 기기 로그아웃도 서버 실패와 무관하게 로컬 토큰을 지운다', () async {
    final storage = _MemoryStorage('refresh-1');
    final dio = _dioWith(_FakeAdapter(const {}));
    dio.httpClientAdapter = _ThrowingAdapter();
    final api = AuthApiClient(storage, dio: dio);

    await api.logoutAll();

    expect(storage.refreshToken, isNull);
    expect(api.accessToken, isNull);
  });

  test('기기 목록을 파싱하고 현재 기기를 구분한다', () async {
    final adapter = _FakeAdapter({
      '/auth/mobile/sessions': [
        const _Reply(200, {
          'sessions': [
            {
              'jti': 'a',
              'deviceId': 'device-1',
              'deviceName': 'Pixel 8',
              'os': 'android',
              'appVersion': '1.0.0+1',
              'issuedAt': 1785000000,
              'current': true,
            },
            {
              'jti': 'b',
              'deviceId': 'device-2',
              'deviceName': 'iPhone 15',
              'os': 'ios',
              'appVersion': '1.0.0+1',
              'issuedAt': 1784000000,
              'current': false,
            },
          ],
        }),
      ],
    });
    final api = AuthApiClient(_MemoryStorage(), dio: _dioWith(adapter));

    final devices = await api.listSessions();

    expect(devices, hasLength(2));
    expect(devices.where((d) => d.current).map((d) => d.deviceId), [
      'device-1',
    ]);
    expect(devices.first.issuedAtLocal.isUtc, isFalse);
  });

  test('기기 목록이 비어 있어도 빈 배열로 처리한다', () async {
    final adapter = _FakeAdapter({
      '/auth/mobile/sessions': [
        const _Reply(200, {'sessions': <dynamic>[]}),
      ],
    });
    final api = AuthApiClient(_MemoryStorage(), dio: _dioWith(adapter));

    expect(await api.listSessions(), isEmpty);
  });

  test('복원이 실패하면 컨트롤러는 로그아웃 상태로 확정된다', () async {
    final adapter = _FakeAdapter({
      '/auth/mobile/refresh': [const _Reply(401)],
    });
    final storage = _MemoryStorage('refresh-1');
    final controller = AuthController(
      storage: storage,
      api: AuthApiClient(storage, dio: _dioWith(adapter)),
    );

    expect(controller.status, AuthStatus.unknown);
    await controller.restore();

    expect(controller.status, AuthStatus.signedOut);
    await controller.restored; // 인트로가 무한 대기하지 않는다
  });
}

/// 항상 연결 오류를 내는 어댑터.
class _ThrowingAdapter implements HttpClientAdapter {
  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) {
    throw DioException.connectionError(
      requestOptions: options,
      reason: 'offline',
    );
  }

  @override
  void close({bool force = false}) {}
}
