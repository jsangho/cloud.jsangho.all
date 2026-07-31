import 'package:flutter/material.dart';

import '../theme/clock_colors.dart';
import 'chat_screen.dart';
import 'clock_home.dart';

/// 인트로 다음에 오는 메인 화면 — 시계와 채팅 중 하나를 고른다.
class MainMenuScreen extends StatelessWidget {
  const MainMenuScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'KayFabe',
                style: TextStyle(
                  color: kClockText,
                  fontSize: 34,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                '무엇을 열까요?',
                style: TextStyle(color: kClockSubText, fontSize: 15),
              ),
              const SizedBox(height: 32),
              _MenuCard(
                icon: Icons.timer,
                iconColor: kClockAccent,
                title: '시계',
                subtitle: '세계 시계 · 알람 · 스톱워치 · 타이머',
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const ClockHome()),
                ),
              ),
              const SizedBox(height: 16),
              _MenuCard(
                icon: Icons.chat_bubble_outline,
                iconColor: kClockGreen,
                title: '채팅',
                subtitle: '대화 화면 열기',
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(builder: (_) => const ChatScreen()),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MenuCard extends StatelessWidget {
  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  const _MenuCard({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: kClockCard,
      borderRadius: BorderRadius.circular(16),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
          child: Row(
            children: [
              Icon(icon, color: iconColor, size: 32),
              const SizedBox(width: 18),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      style: const TextStyle(
                        color: kClockText,
                        fontSize: 19,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      subtitle,
                      style: const TextStyle(
                        color: kClockSubText,
                        fontSize: 13,
                      ),
                    ),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right, color: kClockDisabled, size: 22),
            ],
          ),
        ),
      ),
    );
  }
}
