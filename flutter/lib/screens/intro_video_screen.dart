import 'dart:async';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../auth.dart';
import '../theme/clock_colors.dart';
import 'main_menu_screen.dart';

/// 인트로 영상을 4초간 재생한 뒤 다음 화면으로 넘어가는 화면.
///
/// 다음 화면은 세션 유무로 갈린다:
/// - 모바일 세션이 살아 있으면 곧장 [MainMenuScreen]
/// - 아니면 [AuthScreen]에서 카카오 로그인을 받고 [MainMenuScreen]
///
/// 영상 길이나 초기화 성공 여부와 무관하게 4초 뒤에는 반드시 넘어간다.
/// 재생이 안 되는 기기에서 앱이 인트로에 갇히지 않게 하려는 것이다.
class IntroVideoScreen extends StatefulWidget {
  const IntroVideoScreen({super.key});

  @override
  State<IntroVideoScreen> createState() => _IntroVideoScreenState();
}

class _IntroVideoScreenState extends State<IntroVideoScreen> {
  static const _introDuration = Duration(seconds: 4);

  /// 세션 복원이 인트로보다 오래 걸릴 때 더 기다려 주는 한도.
  /// 이 시간을 넘기면 로그아웃으로 보고 로그인 화면을 띄운다 — 무한 대기는 만들지 않는다.
  static const _restoreGrace = Duration(seconds: 3);

  final _controller = VideoPlayerController.asset('assets/videos/intro.mp4');
  bool _ready = false;
  bool _navigated = false;

  @override
  void initState() {
    super.initState();
    unawaited(_prepare());
    unawaited(_advanceWhenReady());
  }

  Future<void> _prepare() async {
    try {
      await _controller.initialize();
      if (!mounted) return;
      await _controller.play();
      if (!mounted) return;
      setState(() => _ready = true);
    } on Object {
      // 재생에 실패해도 아래 타이머가 다음 화면으로 넘겨준다.
    }
  }

  Future<void> _advanceWhenReady() async {
    // AuthScope는 initState에서 조회할 수 없다 — 첫 await 뒤에 찾는다.
    await Future<void>.delayed(_introDuration);
    if (!mounted) return;

    final auth = AuthScope.of(context);
    if (auth.status == AuthStatus.unknown) {
      await auth.restored.timeout(_restoreGrace, onTimeout: () {});
    }
    if (!mounted || _navigated) return;

    _navigated = true;
    if (auth.isSignedIn) {
      _replaceWithMenu(context);
      return;
    }
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(
        builder: (_) => const AuthScreen(onSignedIn: _replaceWithMenu),
      ),
    );
  }

  /// 로그인 화면에서도 불리므로 자기 화면의 [context]를 쓰지 않는다 —
  /// 인트로 라우트는 그 시점에 이미 트리에서 빠져 있다.
  static void _replaceWithMenu(BuildContext context) {
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => const MainMenuScreen()),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      body: Center(
        child: _ready
            ? AspectRatio(
                aspectRatio: _controller.value.aspectRatio,
                child: VideoPlayer(_controller),
              )
            : const SizedBox.shrink(),
      ),
    );
  }
}
