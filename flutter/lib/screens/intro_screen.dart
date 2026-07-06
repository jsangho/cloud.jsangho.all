import 'package:flutter/material.dart';
import '../widgets/ring_logo.dart';

// 웹 www/app/page.tsx + wwe-arena-shell.tsx 테마 기반
const _kBg = Color(0xFF0A0A0C);
const _kRed = Color(0xFFDC2626);
const _kStone50 = Color(0xFFFAFAF9);
const _kStone400 = Color(0xFFA8A29E);
const _kStone500 = Color(0xFF78716C);

class IntroScreen extends StatefulWidget {
  const IntroScreen({super.key});

  @override
  State<IntroScreen> createState() => _IntroScreenState();
}

class _IntroScreenState extends State<IntroScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _fade;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..forward();
    _fade = CurvedAnimation(parent: _ctrl, curve: Curves.easeOut);
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      body: Stack(
        fit: StackFit.expand,
        children: [
          // 상단 레드 글로우 (wwe-arena-shell 배경 재현)
          const _Glow(
            alignment: Alignment.topCenter,
            wFactor: 1.1,
            hFactor: 0.55,
            color: Color(0xFFE02020),
            opacity: 0.22,
          ),
          const _Glow(
            alignment: Alignment(0, -0.55),
            wFactor: 0.75,
            hFactor: 0.4,
            color: Color(0xFFE02020),
            opacity: 0.10,
          ),
          const _Glow(
            alignment: Alignment(-1.6, 1.6),
            wFactor: 0.55,
            hFactor: 0.35,
            color: Color(0xFF781414),
            opacity: 0.12,
          ),
          // 하단 비네팅
          const Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                  colors: [Colors.transparent, Color(0xD9000000)],
                  stops: [0.45, 1.0],
                ),
              ),
            ),
          ),
          // 콘텐츠
          SafeArea(
            child: FadeTransition(
              opacity: _fade,
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Spacer(),
                  _HeroSection(),
                  Spacer(flex: 2),
                  _FeatureChips(),
                  SizedBox(height: 24),
                  _CtaSection(),
                  SizedBox(height: 36),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Glow extends StatelessWidget {
  final Alignment alignment;
  final double wFactor;
  final double hFactor;
  final Color color;
  final double opacity;

  const _Glow({
    required this.alignment,
    required this.wFactor,
    required this.hFactor,
    required this.color,
    required this.opacity,
  });

  @override
  Widget build(BuildContext context) {
    final alpha = (opacity * 255).round();
    final r = (color.r * 255.0).round().clamp(0, 255);
    final g = (color.g * 255.0).round().clamp(0, 255);
    final b = (color.b * 255.0).round().clamp(0, 255);
    return Positioned.fill(
      child: Align(
        alignment: alignment,
        child: IgnorePointer(
          child: FractionallySizedBox(
            widthFactor: wFactor,
            heightFactor: hFactor,
            child: DecoratedBox(
              decoration: BoxDecoration(
                gradient: RadialGradient(
                  colors: [Color.fromARGB(alpha, r, g, b), Colors.transparent],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ── 히어로 섹션 ──────────────────────────────────────────────────────────

class _HeroSection extends StatelessWidget {
  const _HeroSection();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          const RingLogo(size: 72),
          const SizedBox(height: 14),
          const Text(
            'KayFabe',
            style: TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w900,
              color: _kStone50,
              letterSpacing: -1.5,
            ),
          ),
          const SizedBox(height: 4),
          const Text(
            'WWE PLE 예측 게임',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: _kStone500,
              letterSpacing: 0.4,
            ),
          ),
          const SizedBox(height: 32),
          // 메인 타이틀 (WWE PLE 부분은 더 굵고 타이트하게)
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              children: [
                TextSpan(
                  text: 'WWE PLE',
                  style: TextStyle(
                    fontSize: 42,
                    fontWeight: FontWeight.w900,
                    color: _kStone50,
                    letterSpacing: -2.5,
                    height: 1.1,
                  ),
                ),
                TextSpan(
                  text: ' 승부 예측,\n당신의 본능을 증명하라',
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    color: _kStone50,
                    letterSpacing: -1.2,
                    height: 1.25,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 18),
          // 서브타이틀
          RichText(
            textAlign: TextAlign.center,
            text: const TextSpan(
              style: TextStyle(fontSize: 15, color: _kStone400, height: 1.65),
              children: [
                TextSpan(text: '경기 결과를 예측하고 점수를 쌓아 '),
                TextSpan(
                  text: '2026',
                  style: TextStyle(
                    color: _kStone50,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                TextSpan(text: '년의\n'),
                TextSpan(
                  text: 'Head of the Table',
                  style: TextStyle(
                    color: _kRed,
                    fontWeight: FontWeight.w700,
                    fontSize: 17,
                  ),
                ),
                TextSpan(text: ' 자리를 차지하세요!'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// ── 피처 칩 ──────────────────────────────────────────────────────────────

class _FeatureChips extends StatelessWidget {
  const _FeatureChips();

  static const _items = [
    ('🏆', '2026 PLE 예측'),
    ('📊', 'AI 스코어보드'),
    ('💬', 'AI 채팅'),
  ];

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 10,
        runSpacing: 10,
        children: [
          for (final (icon, label) in _items) _Chip(icon: icon, label: label),
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String icon;
  final String label;

  const _Chip({required this.icon, required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: const Color(0x4D44403C),
        borderRadius: BorderRadius.circular(100),
        border: Border.all(color: const Color(0x8C44403C)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(icon, style: const TextStyle(fontSize: 13)),
          const SizedBox(width: 6),
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              color: _kStone400,
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      ),
    );
  }
}

// ── CTA 버튼 ─────────────────────────────────────────────────────────────

class _CtaSection extends StatelessWidget {
  const _CtaSection();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        children: [
          SizedBox(
            width: double.infinity,
            height: 54,
            child: ElevatedButton(
              onPressed: () {},
              style: ElevatedButton.styleFrom(
                backgroundColor: _kRed,
                foregroundColor: Colors.white,
                elevation: 0,
                shadowColor: Colors.transparent,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: const Text(
                '예측 시작하기',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.5,
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: double.infinity,
            height: 54,
            child: OutlinedButton(
              onPressed: () {},
              style: OutlinedButton.styleFrom(
                foregroundColor: _kStone400,
                side: const BorderSide(color: Color(0xCC44403C)),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: const Text(
                '랭킹 보기',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  letterSpacing: -0.5,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
