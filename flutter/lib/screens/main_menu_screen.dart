import 'package:flutter/material.dart';

import '../auth.dart';
import '../photo_upload.dart';
import '../theme/clock_colors.dart';
import 'chat_screen.dart';
import 'clock_home.dart';

/// 인트로 다음에 오는 메인 화면 — 시계·채팅·계정 중 하나를 고른다.
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
              const SizedBox(height: 16),
              _MenuCard(
                icon: Icons.photo_camera_outlined,
                iconColor: kClockAccent,
                title: '사진 보관',
                subtitle: '촬영해서 서버에 올리기',
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => const PhotoCaptureScreen(),
                  ),
                ),
              ),
              const SizedBox(height: 16),
              _MenuCard(
                icon: Icons.person_outline,
                iconColor: kClockSubText,
                title: '계정',
                subtitle: '로그인된 기기 · 로그아웃',
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) =>
                        const AccountScreen(onSignedOut: _backToSignIn),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// 로그아웃 후에는 스택을 통째로 비우고 로그인 화면만 남긴다 —
/// 뒤로 가기로 인증된 화면에 돌아갈 수 있으면 안 된다.
void _backToSignIn(BuildContext context) {
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute<void>(
      builder: (_) => const AuthScreen(onSignedIn: _toMenu),
    ),
    (route) => false,
  );
}

void _toMenu(BuildContext context) {
  Navigator.of(context).pushAndRemoveUntil(
    MaterialPageRoute<void>(builder: (_) => const MainMenuScreen()),
    (route) => false,
  );
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
