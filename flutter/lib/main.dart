import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/intro_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
    ),
  );
  runApp(const KayfabeApp());
}

class KayfabeApp extends StatelessWidget {
  const KayfabeApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
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
      home: const IntroScreen(),
    );
  }
}
