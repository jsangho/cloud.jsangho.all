/// 카카오 로그인과 모바일 세션 — 화면·저장소·API 클라이언트를 한 파일에 모았다.
///
/// 설계 근거는 `_docs/flutter-kakao-oauth-harness.md`에 있다. 요약하면:
///
/// - 앱은 **인가 코드만** 얻어 서버로 넘기고, 그 대가로 우리 서비스의 JWT 쌍을 받는다.
///   카카오 access/refresh token은 앱에 남지 않는다 (D-1).
/// - refresh token과 device_id만 [FlutterSecureStorage]에 저장하고, access token은
///   메모리에만 둔다 (D-2).
/// - 화면에 쓰는 유저 정보의 출처는 서버 응답뿐이다. `UserApi.instance.me()`를 쓰지
///   않는다 (D-3).
/// - 401은 single-flight로 한 번만 리프레시하고, 원 요청을 한 번만 재시도한다 (D-5).
///
/// 토큰·인가 코드를 로그로 출력하지 않는다 (`avoid_print: error`로도 막혀 있다).
library;

import 'dart:async';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:kakao_flutter_sdk_user/kakao_flutter_sdk_user.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:uuid/uuid.dart';

import 'theme/clock_colors.dart';

// ── 설정 ─────────────────────────────────────────────────────────────────

/// 빌드 시 `--dart-define`으로 주입한다.
///
/// 네이티브 앱 키는 앱 바이너리에 들어가는 게 정상이다 — 비밀값이 아니다.
/// 반대로 `client_secret`은 **절대 앱에 넣지 않는다**. 서버 전용이다.
class AuthConfig {
  const AuthConfig._();

  static const kakaoNativeAppKey = String.fromEnvironment(
    'KAKAO_NATIVE_APP_KEY',
  );

  static const apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://auth.jsangho.cloud',
  );

  /// 카카오 콘솔 등록값·서버 `KAKAO_MOBILE_REDIRECT_URI`와 **완전히 같은 문자열**이어야
  /// 한다. 셋 중 하나라도 다르면 인가 코드 교환이 실패한다.
  static String get redirectUri => 'kakao$kakaoNativeAppKey://oauth';

  static bool get isConfigured => kakaoNativeAppKey.isNotEmpty;
}

/// `main()`에서 한 번만 호출한다. 키가 없으면 조용히 넘어가고, 로그인 화면이
/// 설정 누락을 안내한다 — 여기서 던지면 앱이 아예 뜨지 않는다.
Future<void> initKakaoSdk() async {
  if (!AuthConfig.isConfigured) return;
  await KakaoSdk.init(nativeAppKey: AuthConfig.kakaoNativeAppKey);
}

// ── 모델 ─────────────────────────────────────────────────────────────────

@immutable
class AuthUser {
  final int userId;
  final String nickname;

  /// 카카오 이메일은 선택 동의 항목이라 **null일 수 있다.**
  /// 화면의 필수 요소로 삼지 않는다.
  final String? email;
  final String role;

  const AuthUser({
    required this.userId,
    required this.nickname,
    required this.email,
    required this.role,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      userId: json['userId'] as int,
      nickname: (json['nickname'] as String?) ?? '',
      email: json['email'] as String?,
      role: (json['role'] as String?) ?? 'user',
    );
  }
}

/// 서버에 살아 있는 모바일 세션 한 줄 (`GET /auth/mobile/sessions`).
@immutable
class DeviceSession {
  final String jti;
  final String deviceId;
  final String deviceName;
  final String os;
  final String appVersion;

  /// 발급 시각(epoch seconds). 회전해도 최초 로그인 시각을 유지한다.
  final int issuedAt;

  /// 지금 이 기기인지. 서버가 access token의 `device_id`와 대조해 알려준다.
  final bool current;

  const DeviceSession({
    required this.jti,
    required this.deviceId,
    required this.deviceName,
    required this.os,
    required this.appVersion,
    required this.issuedAt,
    required this.current,
  });

  factory DeviceSession.fromJson(Map<String, dynamic> json) {
    return DeviceSession(
      jti: (json['jti'] as String?) ?? '',
      deviceId: (json['deviceId'] as String?) ?? '',
      deviceName: (json['deviceName'] as String?) ?? '',
      os: (json['os'] as String?) ?? '',
      appVersion: (json['appVersion'] as String?) ?? '',
      issuedAt: (json['issuedAt'] as int?) ?? 0,
      current: (json['current'] as bool?) ?? false,
    );
  }

  DateTime get issuedAtLocal =>
      DateTime.fromMillisecondsSinceEpoch(issuedAt * 1000).toLocal();
}

/// 로그인 실패를 사용자에게 보여줄 한국어 문구로 옮긴 예외.
///
/// 서버·SDK의 원문 메시지는 [debugDetail]에만 담고 화면에는 내보내지 않는다.
class AuthFailure implements Exception {
  final String message;
  final String? debugDetail;

  const AuthFailure(this.message, [this.debugDetail]);

  @override
  String toString() => 'AuthFailure: $message';
}

/// 사용자가 동의 화면에서 직접 취소한 경우. **오류가 아니다** — 팝업을 띄우지 않는다.
class AuthCancelled implements Exception {
  const AuthCancelled();
}

// ── 보안 저장소 ───────────────────────────────────────────────────────────

/// refresh token과 device_id만 담는다. access token은 여기 들어오지 않는다 (D-2).
///
/// 인터페이스로 분리해 둔 이유는 테스트에서 실제 키체인 없이 대체하기 위해서다.
abstract class AuthStorage {
  Future<String?> readRefreshToken();
  Future<void> writeRefreshToken(String token);
  Future<void> clear();

  /// 앱 설치 단위 식별자. 없으면 만들어 저장하고 이후 재사용한다.
  Future<String> deviceId();
}

/// Keychain(iOS) · Keystore(Android)에 얹은 기본 구현.
class SecureAuthStorage implements AuthStorage {
  static const _refreshTokenKey = 'auth.refreshToken';
  static const _deviceIdKey = 'auth.deviceId';

  final FlutterSecureStorage _storage;

  const SecureAuthStorage([this._storage = const FlutterSecureStorage()]);

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _refreshTokenKey);

  @override
  Future<void> writeRefreshToken(String token) =>
      _storage.write(key: _refreshTokenKey, value: token);

  @override
  Future<void> clear() => _storage.delete(key: _refreshTokenKey);

  /// 광고 식별자(IDFA/AAID)나 하드웨어 시리얼을 쓰지 않는다 — 스토어 정책 문제가 따라온다.
  /// 앱을 재설치하면 값이 바뀌는 것이 정상이며, 서버가 기기 상한으로 정리한다.
  @override
  Future<String> deviceId() async {
    final saved = await _storage.read(key: _deviceIdKey);
    if (saved != null && saved.isNotEmpty) return saved;

    final created = const Uuid().v4();
    await _storage.write(key: _deviceIdKey, value: created);
    return created;
  }
}

// ── 기기 메타 ─────────────────────────────────────────────────────────────

@immutable
class DeviceMeta {
  final String deviceId;
  final String deviceName;
  final String os;
  final String appVersion;

  const DeviceMeta({
    required this.deviceId,
    required this.deviceName,
    required this.os,
    required this.appVersion,
  });
}

/// 플랫폼별 값 차이를 여기서 전부 흡수한다 — 호출부는 분기하지 않는다.
class DeviceMetaCollector {
  final AuthStorage _storage;

  const DeviceMetaCollector(this._storage);

  Future<DeviceMeta> collect() async {
    final deviceId = await _storage.deviceId();
    final packageInfo = await PackageInfo.fromPlatform();
    final appVersion = '${packageInfo.version}+${packageInfo.buildNumber}';

    final plugin = DeviceInfoPlugin();
    if (defaultTargetPlatform == TargetPlatform.android) {
      final info = await plugin.androidInfo;
      return DeviceMeta(
        deviceId: deviceId,
        deviceName: '${info.manufacturer} ${info.model}'.trim(),
        os: 'android',
        appVersion: appVersion,
      );
    }
    if (defaultTargetPlatform == TargetPlatform.iOS) {
      final info = await plugin.iosInfo;
      return DeviceMeta(
        deviceId: deviceId,
        deviceName: info.name,
        os: 'ios',
        appVersion: appVersion,
      );
    }
    return DeviceMeta(
      deviceId: deviceId,
      deviceName: defaultTargetPlatform.name,
      os: defaultTargetPlatform.name,
      appVersion: appVersion,
    );
  }
}

// ── 인증 API 클라이언트 ────────────────────────────────────────────────────

/// `/auth/mobile/*` 호출부. 서버 계약은 하네스 §5에 있다.
///
/// access token은 [_accessToken]에 메모리로만 들고 있으며, 401이 오면
/// [_refresh]를 **정확히 한 번** 수행하고 원 요청을 한 번만 재시도한다.
class AuthApiClient {
  static const _refreshPath = '/auth/mobile/refresh';
  static const _loginPath = '/auth/mobile/kakao';
  static const _retriedFlag = 'auth.retried';

  final Dio _dio;
  final AuthStorage _storage;

  String? _accessToken;

  /// 진행 중인 리프레시. 동시에 401을 받은 요청들은 새로 시작하지 않고 여기에 합류한다.
  Future<bool>? _refreshing;

  /// 리프레시가 최종 실패했을 때 상위(세션 상태)에 알리는 통로.
  VoidCallback? onSessionExpired;

  AuthApiClient(this._storage, {Dio? dio})
    : _dio =
          dio ??
          Dio(
            BaseOptions(
              baseUrl: AuthConfig.apiBaseUrl,
              connectTimeout: const Duration(seconds: 5),
              receiveTimeout: const Duration(seconds: 10),
              contentType: Headers.jsonContentType,
              // validateStatus를 완화하지 않는다 — 4xx가 정상 응답으로 넘어오면
              // onError가 안 불려 401 리프레시 인터셉터가 통째로 죽는다.
            ),
          ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: _attachBearer,
        onError: _handleUnauthorized,
      ),
    );
  }

  String? get accessToken => _accessToken;

  void _attachBearer(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) {
    final token = _accessToken;
    if (token != null && options.path != _refreshPath) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  Future<void> _handleUnauthorized(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final request = error.requestOptions;
    final isUnauthorized = error.response?.statusCode == 401;

    // 리프레시 요청 자체는 인터셉터를 타지 않는다 (무한 루프 방지).
    // 로그인 요청의 401은 "인가 코드가 무효"라는 뜻이라 리프레시로 풀 수 없다.
    // 재시도는 요청당 한 번뿐이다 — 두 번째 401은 그대로 올린다.
    if (!isUnauthorized ||
        request.path == _refreshPath ||
        request.path == _loginPath ||
        request.extra[_retriedFlag] == true) {
      handler.next(error);
      return;
    }

    final refreshed = await _refreshOnce();
    if (!refreshed) {
      handler.next(error);
      return;
    }

    request.extra[_retriedFlag] = true;
    try {
      handler.resolve(await _dio.fetch<dynamic>(request));
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  /// 이미 리프레시가 돌고 있으면 그 결과를 기다린다 (single-flight, D-5).
  Future<bool> _refreshOnce() {
    return _refreshing ??= _refresh().whenComplete(() => _refreshing = null);
  }

  Future<bool> _refresh() async {
    final refreshToken = await _storage.readRefreshToken();
    if (refreshToken == null) return false;

    Response<dynamic> response;
    try {
      response = await _dio.post<dynamic>(
        _refreshPath,
        data: {'refreshToken': refreshToken},
      );
    } on DioException catch (error) {
      final status = error.response?.statusCode;
      if (status == null || status >= 500) {
        // 네트워크·서버 장애는 세션 만료가 아니다 — 저장된 토큰을 지우지 않는다.
        return false;
      }
      // 4xx면 이 토큰은 죽었다. 지우고 로그인 화면으로 돌려보낸다. 재시도 금지.
      await _storage.clear();
      _accessToken = null;
      onSessionExpired?.call();
      return false;
    }

    final body = response.data as Map<String, dynamic>;
    _accessToken = body['token'] as String;
    // 회전된 새 refresh token을 **즉시** 교체 저장한다. 구 토큰을 다시 쓰면 서버가
    // 탈취로 판단해 모바일 세션 전체를 폐기한다.
    await _storage.writeRefreshToken(body['refreshToken'] as String);
    return true;
  }

  /// 인가 코드를 우리 서버의 JWT 쌍으로 교환한다.
  Future<AuthUser> loginWithKakao({
    required String code,
    required DeviceMeta device,
  }) async {
    Response<dynamic> response;
    try {
      response = await _dio.post<dynamic>(
        _loginPath,
        data: {
          'code': code,
          'redirectUri': AuthConfig.redirectUri,
          'deviceId': device.deviceId,
          'deviceName': device.deviceName,
          'os': device.os,
          'appVersion': device.appVersion,
        },
      );
    } on DioException catch (error) {
      // 서버가 보낸 원문은 debugDetail에만 남기고 화면에는 한국어 문구만 내보낸다.
      final status = error.response?.statusCode;
      throw AuthFailure(
        status == null ? _networkMessage(error) : _statusMessage(status),
        error.message,
      );
    }

    final body = response.data as Map<String, dynamic>;
    _accessToken = body['token'] as String;
    await _storage.writeRefreshToken(body['refreshToken'] as String);
    return AuthUser.fromJson(body['user'] as Map<String, dynamic>);
  }

  /// 앱 시작 시 세션 복원. 실패는 정상 상황이므로 조용히 false를 돌려준다.
  Future<bool> restore() => _refreshOnce();

  /// 서버 호출 성공 여부와 무관하게 로컬 토큰은 지운다 — 서버가 죽어도 로그아웃은 되어야 한다.
  Future<void> logout() async {
    final refreshToken = await _storage.readRefreshToken();
    try {
      if (refreshToken != null) {
        await _dio.post<dynamic>(
          '/auth/mobile/logout',
          data: {'refreshToken': refreshToken},
        );
      }
    } on DioException {
      // 무시한다.
    } finally {
      await _storage.clear();
      _accessToken = null;
    }
  }

  /// 이 계정의 **모바일 세션 전체**를 끊는다. 웹 세션은 그대로 남는다 (D-4).
  Future<void> logoutAll() async {
    try {
      await _dio.post<dynamic>('/auth/mobile/logout-all');
    } on DioException {
      // 무시한다 — 로컬 토큰은 어차피 지운다.
    } finally {
      await _storage.clear();
      _accessToken = null;
    }
  }

  /// 로그인된 기기 목록.
  Future<List<DeviceSession>> listSessions() async {
    Response<dynamic> response;
    try {
      response = await _dio.get<dynamic>('/auth/mobile/sessions');
    } on DioException catch (error) {
      final status = error.response?.statusCode;
      throw AuthFailure(
        status == null ? _networkMessage(error) : '기기 목록을 불러오지 못했습니다.',
        error.message,
      );
    }

    final body = response.data as Map<String, dynamic>;
    final rows = (body['sessions'] as List<dynamic>?) ?? const [];
    return rows
        .map((row) => DeviceSession.fromJson(row as Map<String, dynamic>))
        .toList();
  }

  static String _statusMessage(int? status) {
    return switch (status) {
      400 => '로그인에 실패했습니다. 잠시 후 다시 시도해 주세요.',
      401 => '로그인 정보가 만료됐습니다. 다시 시도해 주세요.',
      502 || 503 || 504 => '잠시 후 다시 시도해 주세요.',
      _ => '로그인에 실패했습니다.',
    };
  }

  static String _networkMessage(DioException error) {
    return switch (error.type) {
      DioExceptionType.connectionTimeout ||
      DioExceptionType.receiveTimeout ||
      DioExceptionType.sendTimeout => '네트워크가 느립니다. 잠시 후 다시 시도해 주세요.',
      _ => '서버에 연결하지 못했습니다. 네트워크를 확인해 주세요.',
    };
  }
}

// ── 세션 상태 ─────────────────────────────────────────────────────────────

enum AuthStatus {
  /// 복원 판정이 끝나지 않았다. 이 동안 인증이 필요한 화면을 그리지 않는다.
  unknown,
  signedIn,
  signedOut,
}

/// 앱 전역 세션 상태. `main()`에서 하나 만들어 [AuthScope]로 내려보낸다.
class AuthController extends ChangeNotifier {
  final AuthApiClient _api;
  final AuthStorage _storage;
  final DeviceMetaCollector _device;

  AuthStatus _status = AuthStatus.unknown;
  AuthUser? _user;

  /// [restore]가 끝나면 완료된다. 인트로 화면이 "판정이 끝났는지"를 기다리는 데 쓴다.
  final _restored = Completer<void>();

  AuthController({
    AuthStorage storage = const SecureAuthStorage(),
    AuthApiClient? api,
  }) : _storage = storage,
       _api = api ?? AuthApiClient(storage),
       _device = DeviceMetaCollector(storage) {
    _api.onSessionExpired = _onSessionExpired;
  }

  AuthStatus get status => _status;
  AuthUser? get user => _user;
  bool get isSignedIn => _status == AuthStatus.signedIn;

  /// 복원 판정이 끝날 때까지 기다린다. 이 전에는 인증이 필요한 화면을 그리지 않는다.
  Future<void> get restored => _restored.future;

  /// 앱 시작 시 한 번 호출한다.
  ///
  /// 저장된 refresh token이 있으면 리프레시를 먼저 시도하고, 성공하면 로그인 상태로
  /// 들어간다. 실패해도 오류 팝업을 띄우지 않는다 — 만료는 정상 상황이다.
  Future<void> restore() async {
    var ok = false;
    try {
      ok = await _api.restore();
    } on Object {
      // 보안 저장소를 못 읽는 상황(플러그인 부재·키체인 오류)도 "로그인 안 됨"으로 본다.
      // 여기서 예외가 새어 나가면 [restored]가 영영 완료되지 않아 앱이 인트로에 갇힌다.
    }
    _status = ok ? AuthStatus.signedIn : AuthStatus.signedOut;
    if (!_restored.isCompleted) _restored.complete();
    notifyListeners();
  }

  /// 카카오 로그인 전체 흐름. 취소면 [AuthCancelled], 실패면 [AuthFailure]를 던진다.
  Future<void> signInWithKakao() async {
    if (!AuthConfig.isConfigured) {
      throw const AuthFailure('앱 설정이 완료되지 않았습니다. 관리자에게 문의해 주세요.');
    }

    final code = await _authorize();
    final device = await _device.collect();
    _user = await _api.loginWithKakao(code: code, device: device);
    _status = AuthStatus.signedIn;
    notifyListeners();
  }

  /// 카카오톡이 깔려 있으면 카카오톡으로, 아니면 웹 브라우저로 인가 코드를 받는다.
  ///
  /// [UserApi.loginWithKakaoTalk]이 아니라 [AuthCodeClient]를 쓰는 이유는, 앱이
  /// 카카오 토큰을 쥐지 않고 **인가 코드만** 서버로 넘기기 위해서다 (D-1).
  Future<String> _authorize() async {
    try {
      if (await isKakaoTalkInstalled()) {
        try {
          return await AuthCodeClient.instance.authorizeWithTalk(
            redirectUri: AuthConfig.redirectUri,
          );
        } on AuthCancelled {
          rethrow;
        } on Exception catch (error) {
          // 카카오톡이 있어도 실행에 실패할 수 있다(구버전·비활성화). 취소가 아니면
          // 브라우저로 폴백한다.
          if (_isCancellation(error)) rethrow;
        }
      }
      return await AuthCodeClient.instance.authorize(
        redirectUri: AuthConfig.redirectUri,
      );
    } on Exception catch (error) {
      if (_isCancellation(error)) throw const AuthCancelled();
      throw AuthFailure('카카오 로그인에 실패했습니다.', error.toString());
    }
  }

  static bool _isCancellation(Object error) {
    if (error is AuthCancelled) return true;
    if (error is KakaoClientException) {
      return error.reason == ClientErrorCause.cancelled;
    }
    if (error is KakaoAuthException) {
      return error.error == AuthErrorCause.accessDenied;
    }
    return false;
  }

  /// 이 기기만 로그아웃한다.
  Future<void> signOut() async {
    await _api.logout();
    _clearSession();
  }

  /// 이 계정의 모바일 세션을 전부 끊는다. 웹 세션은 살아 있다 (D-4) —
  /// 버그가 아니므로 우회 코드를 넣지 않는다.
  Future<void> signOutEverywhere() async {
    await _api.logoutAll();
    _clearSession();
  }

  Future<List<DeviceSession>> loadDevices() => _api.listSessions();

  void _clearSession() {
    _user = null;
    _status = AuthStatus.signedOut;
    notifyListeners();
  }

  void _onSessionExpired() => _clearSession();

  @visibleForTesting
  Future<void> clearStoredSession() => _storage.clear();

  /// 로그인 화면을 거치지 않고 곧장 로그인 상태로 만든다. 위젯 테스트 전용이다.
  @visibleForTesting
  void debugSignIn(AuthUser user) {
    _user = user;
    _status = AuthStatus.signedIn;
    if (!_restored.isCompleted) _restored.complete();
    notifyListeners();
  }
}

/// [AuthController]를 위젯 트리에 내려보낸다.
class AuthScope extends InheritedNotifier<AuthController> {
  const AuthScope({
    required AuthController super.notifier,
    required super.child,
    super.key,
  });

  static AuthController of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AuthScope>();
    assert(scope?.notifier != null, 'AuthScope를 트리 위쪽에 두어야 합니다.');
    return scope!.notifier!;
  }
}

// ── 로그인 화면 ───────────────────────────────────────────────────────────

/// 카카오 로그인 화면. 성공하면 [onSignedIn]에 **이 화면의** context를 넘겨 부른다.
///
/// 이동할 화면을 콜백으로 받는 이유는, 인증 코드가 특정 화면에 묶이지 않게 하려는 것이다.
/// context를 함께 넘기는 이유는, 호출부의 라우트가 이미 트리에서 빠졌을 수 있어서다.
class AuthScreen extends StatefulWidget {
  final void Function(BuildContext context) onSignedIn;

  const AuthScreen({required this.onSignedIn, super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  bool _busy = false;
  String? _error;

  Future<void> _signIn() async {
    setState(() {
      _busy = true;
      _error = null;
    });

    try {
      await AuthScope.of(context).signInWithKakao();
      if (!mounted) return;
      widget.onSignedIn(context);
    } on AuthCancelled {
      // 사용자가 스스로 그만둔 것이다 — 아무것도 띄우지 않는다.
      if (mounted) setState(() => _busy = false);
    } on AuthFailure catch (failure) {
      if (mounted) {
        setState(() {
          _busy = false;
          _error = failure.message;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(flex: 3),
              const Text(
                'KayFabe',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: kClockText,
                  fontSize: 40,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -1,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                '카카오 계정으로 시작하세요',
                textAlign: TextAlign.center,
                style: TextStyle(color: kClockSubText, fontSize: 15),
              ),
              const Spacer(flex: 4),
              if (_error != null) ...[
                Text(
                  _error!,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    color: kClockRed,
                    fontSize: 14,
                    height: 1.4,
                  ),
                ),
                const SizedBox(height: 16),
              ],
              _KakaoLoginButton(busy: _busy, onPressed: _busy ? null : _signIn),
              const SizedBox(height: 24),
              const Text(
                '로그인하면 서비스 이용약관에 동의하는 것으로 봅니다.',
                textAlign: TextAlign.center,
                style: TextStyle(color: kClockDisabled, fontSize: 12),
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }
}

/// 카카오 디자인 가이드의 기본 버튼 — 노란 배경(#FEE500)에 85% 불투명 검정 라벨.
class _KakaoLoginButton extends StatelessWidget {
  static const _kakaoYellow = Color(0xFFFEE500);
  static const _kakaoLabel = Color(0xD9000000);

  final bool busy;
  final VoidCallback? onPressed;

  const _KakaoLoginButton({required this.busy, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: Material(
        color: _kakaoYellow,
        borderRadius: BorderRadius.circular(12),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: Center(
            child: busy
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.4,
                      valueColor: AlwaysStoppedAnimation<Color>(_kakaoLabel),
                    ),
                  )
                : const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.chat_bubble, color: _kakaoLabel, size: 20),
                      SizedBox(width: 10),
                      Text(
                        '카카오 로그인',
                        style: TextStyle(
                          color: _kakaoLabel,
                          fontSize: 16,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

// ── 계정 화면 ─────────────────────────────────────────────────────────────

/// 계정 정보 · 로그인된 기기 목록 · 로그아웃 진입점.
///
/// 로그아웃하면 [onSignedOut]에 이 화면의 context를 넘겨 부른다 — 호출부의 라우트가
/// 이미 트리에서 빠졌을 수 있어 자기 context를 쓰지 않는다.
class AccountScreen extends StatefulWidget {
  final void Function(BuildContext context) onSignedOut;

  const AccountScreen({required this.onSignedOut, super.key});

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  late Future<List<DeviceSession>> _devices;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // AuthScope는 initState에서 조회할 수 없어 로딩만 didChangeDependencies로 미룬다.
    _devices = Future.value(const []);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _devices = AuthScope.of(context).loadDevices();
  }

  Future<void> _signOut({required bool everywhere}) async {
    final auth = AuthScope.of(context);
    setState(() => _busy = true);

    // 서버 호출이 실패해도 로컬 세션은 지워지므로 결과를 분기하지 않는다.
    if (everywhere) {
      await auth.signOutEverywhere();
    } else {
      await auth.signOut();
    }
    if (!mounted) return;
    widget.onSignedOut(context);
  }

  @override
  Widget build(BuildContext context) {
    final user = AuthScope.of(context).user;

    return Scaffold(
      backgroundColor: kClockBg,
      appBar: AppBar(
        backgroundColor: kClockBg,
        title: const Text('계정', style: TextStyle(color: kClockText)),
        iconTheme: const IconThemeData(color: kClockText),
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          children: [
            if (user != null) _ProfileCard(user: user),
            const SizedBox(height: 28),
            const Text(
              '로그인된 기기',
              style: TextStyle(
                color: kClockText,
                fontSize: 17,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 12),
            FutureBuilder<List<DeviceSession>>(
              future: _devices,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Padding(
                    padding: EdgeInsets.symmetric(vertical: 24),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                if (snapshot.hasError) {
                  return const Text(
                    '기기 목록을 불러오지 못했습니다.',
                    style: TextStyle(color: kClockSubText, fontSize: 14),
                  );
                }
                final devices = snapshot.data ?? const <DeviceSession>[];
                if (devices.isEmpty) {
                  return const Text(
                    '표시할 기기가 없습니다.',
                    style: TextStyle(color: kClockSubText, fontSize: 14),
                  );
                }
                return Column(
                  children: [
                    for (final device in devices) _DeviceRow(device: device),
                  ],
                );
              },
            ),
            const SizedBox(height: 32),
            _DangerButton(
              label: '로그아웃',
              color: kClockText,
              onPressed: _busy ? null : () => _signOut(everywhere: false),
            ),
            const SizedBox(height: 10),
            _DangerButton(
              label: '모든 기기에서 로그아웃',
              color: kClockRed,
              onPressed: _busy ? null : () => _signOut(everywhere: true),
            ),
            const SizedBox(height: 12),
            const Text(
              '모든 기기 로그아웃은 앱 세션만 끊습니다. 웹 로그인은 그대로 유지됩니다.',
              style: TextStyle(
                color: kClockDisabled,
                fontSize: 12,
                height: 1.4,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProfileCard extends StatelessWidget {
  final AuthUser user;

  const _ProfileCard({required this.user});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 20),
      decoration: BoxDecoration(
        color: kClockCard,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.account_circle, color: kClockSubText, size: 44),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  user.nickname,
                  style: const TextStyle(
                    color: kClockText,
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                // 이메일은 선택 동의 항목이라 없을 수 있다 — 없으면 그 자리를 비운다.
                Text(
                  user.email ?? '이메일 미제공',
                  style: const TextStyle(color: kClockSubText, fontSize: 13),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _DeviceRow extends StatelessWidget {
  final DeviceSession device;

  const _DeviceRow({required this.device});

  @override
  Widget build(BuildContext context) {
    final name = device.deviceName.isEmpty ? '알 수 없는 기기' : device.deviceName;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: Row(
        children: [
          Icon(
            device.os == 'ios' ? Icons.phone_iphone : Icons.phone_android,
            color: device.current ? kClockGreen : kClockSubText,
            size: 22,
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        name,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: kClockText, fontSize: 15),
                      ),
                    ),
                    if (device.current) ...[
                      const SizedBox(width: 8),
                      const Text(
                        '이 기기',
                        style: TextStyle(color: kClockGreen, fontSize: 12),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  '${_formatDate(device.issuedAtLocal)} · ${device.appVersion}',
                  style: const TextStyle(color: kClockSubText, fontSize: 12),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

String _formatDate(DateTime value) {
  final month = value.month.toString().padLeft(2, '0');
  final day = value.day.toString().padLeft(2, '0');
  final hour = value.hour.toString().padLeft(2, '0');
  final minute = value.minute.toString().padLeft(2, '0');
  return '${value.year}.$month.$day $hour:$minute';
}

class _DangerButton extends StatelessWidget {
  final String label;
  final Color color;
  final VoidCallback? onPressed;

  const _DangerButton({
    required this.label,
    required this.color,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 50,
      child: Material(
        color: kClockCard,
        borderRadius: BorderRadius.circular(12),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: Center(
            child: Text(
              label,
              style: TextStyle(
                color: onPressed == null ? kClockDisabled : color,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
