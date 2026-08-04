import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kayfabe/auth.dart';
import 'package:kayfabe/main.dart';

const _method = MethodChannel('cloud.jsangho/stopwatch');
const _events = EventChannel('cloud.jsangho/stopwatch/state');

/// Kotlin `StopwatchEngine` 을 대신하는 테스트용 가짜 기능 모듈.
///
/// 시간은 스스로 흐르지 않고 [advance] 로만 움직인다 — 결과를 예측할 수 있어야 한다.
class _FakeEngine {
  bool running = false;
  int elapsedMs = 0;
  final List<int> laps = [];
  MockStreamHandlerEventSink? sink;

  void advance(int ms) {
    elapsedMs += ms;
    _emit();
  }

  void handle(String method) {
    switch (method) {
      case 'start':
        running = true;
      case 'stop':
        running = false;
      case 'lap':
        if (running) laps.add(elapsedMs - _lapsTotal);
      case 'reset':
        running = false;
        elapsedMs = 0;
        laps.clear();
    }
    _emit();
  }

  void _emit() => sink?.success(snapshot());

  int get _lapsTotal => laps.fold(0, (a, b) => a + b);

  Map<Object?, Object?> snapshot() {
    var best = -1;
    var worst = -1;
    if (laps.length >= 2) {
      best = 0;
      worst = 0;
      for (var i = 1; i < laps.length; i++) {
        if (laps[i] < laps[best]) best = i;
        if (laps[i] > laps[worst]) worst = i;
      }
    }
    return {
      'elapsedMs': elapsedMs,
      'running': running,
      'laps': List<Object?>.from(laps),
      'currentLapMs': elapsedMs - _lapsTotal,
      'bestIndex': best,
      'worstIndex': worst,
    };
  }
}

/// 가짜 기능 모듈을 채널에 물린다.
///
/// 반드시 테스트 바디 안에서 부른다 — `setUp` 에서 등록하면 이벤트 채널이
/// 위젯 테스트의 바인딩에 붙지 않아 상태가 화면까지 오지 않는다.
_FakeEngine _installFakeEngine() {
  final engine = _FakeEngine();
  final messenger =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  messenger.setMockMethodCallHandler(_method, (call) async {
    engine.handle(call.method);
    return engine.snapshot();
  });
  addTearDown(() => messenger.setMockMethodCallHandler(_method, null));

  messenger.setMockStreamHandler(
    _events,
    MockStreamHandler.inline(
      onListen: (arguments, sink) {
        engine.sink = sink;
        sink.success(engine.snapshot());
      },
      onCancel: (arguments) => engine.sink = null,
    ),
  );
  return engine;
}

/// 앱을 띄우고 인트로 영상(4초) → 메인 메뉴 → 시계 홈까지 도달시킨다.
///
/// 테스트 환경엔 video_player 플러그인이 없어 재생은 실패하지만,
/// 인트로 화면은 타이머만으로 다음 화면으로 넘어간다.
///
/// 세션은 [AuthController.debugSignIn]으로 미리 채운다 — 카카오 로그인 화면을
/// 통과하는 것이 이 파일의 관심사가 아니다.
Future<void> _pumpAppPastIntro(WidgetTester tester) async {
  final auth = AuthController()
    ..debugSignIn(
      const AuthUser(userId: 1, nickname: '테스터', email: null, role: 'user'),
    );

  await tester.pumpWidget(KayfabeApp(auth: auth));
  await tester.pump(const Duration(seconds: 4)); // 인트로 타이머 만료
  await tester.pumpAndSettle(); // 메인 메뉴로 전환 완료

  await tester.tap(find.text('시계'));
  await tester.pumpAndSettle();
}

void main() {
  // 플랫폼 오버라이드는 테스트 본문이 끝나기 전에 되돌려야 한다 —
  // 프레임워크가 tearDown보다 먼저 "디버그 변수 원복" 불변식을 검사한다.
  Future<void> onPlatform(
    TargetPlatform platform,
    Future<void> Function() body,
  ) async {
    debugDefaultTargetPlatformOverride = platform;
    try {
      await body();
    } finally {
      debugDefaultTargetPlatformOverride = null;
    }
  }

  // IndexedStack은 선택되지 않은 탭을 Offstage로 감싸므로 기본 finder가 걸러낸다.
  // 즉 아래 검증은 "현재 보이는 탭"만 대상으로 한다.

  testWidgets('스톱워치 탭이 기본으로 뜨고 탭 4개가 보인다', (tester) async {
    await onPlatform(TargetPlatform.android, () async {
      _installFakeEngine();
      await _pumpAppPastIntro(tester);

      expect(find.text('세계 시계'), findsOneWidget);
      expect(find.text('알람'), findsOneWidget);
      expect(find.text('스톱워치'), findsOneWidget);
      expect(find.text('타이머'), findsOneWidget);

      expect(find.text('00:00.00'), findsOneWidget);
      expect(find.text('시작'), findsOneWidget);
      expect(find.text('랩'), findsOneWidget);

      await tester.pumpWidget(const SizedBox.shrink()); // 타이머 정리
    });
  });

  testWidgets('탭을 옮기면 해당 화면이 보인다', (tester) async {
    await onPlatform(TargetPlatform.android, () async {
      _installFakeEngine();
      await _pumpAppPastIntro(tester);

      await tester.tap(find.byIcon(Icons.public));
      await tester.pump();
      expect(find.text('서울'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.alarm));
      await tester.pump();
      expect(find.text('기상'), findsOneWidget);

      await tester.tap(find.byIcon(Icons.hourglass_bottom));
      await tester.pump();
      expect(find.text('시간'), findsOneWidget);
      expect(find.text('분'), findsOneWidget);
      expect(find.text('초'), findsOneWidget);

      await tester.pumpWidget(const SizedBox.shrink());
    });
  });

  testWidgets('화면은 네이티브가 보낸 상태만 그린다', (tester) async {
    await onPlatform(TargetPlatform.android, () async {
      final engine = _installFakeEngine();
      await _pumpAppPastIntro(tester);

      await tester.tap(find.text('시작'));
      await tester.idle();
      await tester.pump();
      expect(find.text('중단'), findsOneWidget);

      engine.advance(9450);
      await tester.idle();
      await tester.pump();
      // 큰 표시 + 진행 중인 랩 1 — 아직 확정된 랩이 없어 값이 같다.
      expect(find.text('00:09.45'), findsNWidgets(2));

      await tester.tap(find.text('랩'));
      await tester.idle();
      await tester.pump();
      expect(find.text('랩 1'), findsOneWidget);
      expect(find.text('랩 2'), findsOneWidget);

      await tester.tap(find.text('중단'));
      await tester.idle();
      await tester.pump();
      expect(find.text('재설정'), findsOneWidget);

      await tester.pumpWidget(const SizedBox.shrink());
    });
  });

  testWidgets('Android가 아니면 안내 문구를 보여준다', (tester) async {
    await onPlatform(TargetPlatform.iOS, () async {
      _installFakeEngine();
      await _pumpAppPastIntro(tester);

      expect(find.textContaining('Android 네이티브 모듈'), findsOneWidget);
      expect(find.text('00:00.00'), findsNothing);

      await tester.pumpWidget(const SizedBox.shrink());
    });
  });
}
