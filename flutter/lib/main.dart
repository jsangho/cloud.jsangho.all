import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'auth.dart';
import 'screens/intro_video_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  await initKakaoSdk();

  // 세션 복원은 인트로 영상이 도는 동안 백그라운드로 진행된다. 영상이 끝날 때쯤이면
  // 대개 판정이 끝나 있어 사용자는 대기를 체감하지 않는다.
  // 실패해도 조용히 로그아웃 상태로 두므로 결과를 기다리지 않는다.
  final auth = AuthController();
  unawaited(auth.restore());

  runApp(KayfabeApp(auth: auth));
}

class KayfabeApp extends StatelessWidget {
  final AuthController auth;

  const KayfabeApp({required this.auth, super.key});

  @override
  Widget build(BuildContext context) {
    return AuthScope(
      notifier: auth,
      child: MaterialApp(
        title: 'KayFabe',
        debugShowCheckedModeBanner: false,
        theme: ThemeData.dark(useMaterial3: true).copyWith(
          scaffoldBackgroundColor: const Color(0xFF0A0A0C),
          colorScheme: const ColorScheme.dark(
            primary: Color(0xFFDC2626),
            surface: Color(0xFF0A0A0C),
            onSurface: Color(0xFFFAFAF9),
          ),
        ),
        home: const IntroVideoScreen(),
      ),
    );
  }
}
