import 'dart:async';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../theme/clock_colors.dart';
import 'main_menu_screen.dart';

/// 인트로 영상을 4초간 재생한 뒤 메인 화면(시계·채팅 선택)으로 넘어가는 화면.
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

  final _controller = VideoPlayerController.asset('assets/videos/intro.mp4');
  Timer? _timer;
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer(_introDuration, _goHome);
    unawaited(_prepare());
  }

  Future<void> _prepare() async {
    try {
      await _controller.initialize();
      if (!mounted) return;
      await _controller.play();
      if (!mounted) return;
      setState(() => _ready = true);
    } on Object {
      // 재생에 실패해도 타이머가 홈으로 넘겨준다.
    }
  }

  void _goHome() {
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      MaterialPageRoute<void>(builder: (_) => const MainMenuScreen()),
    );
  }

  @override
  void dispose() {
    _timer?.cancel();
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
