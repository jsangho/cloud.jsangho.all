import 'package:flutter/material.dart';

import '../theme/clock_colors.dart';
import 'alarm_screen.dart';
import 'stopwatch_screen.dart';
import 'timer_screen.dart';
import 'world_clock_screen.dart';

/// 세계 시계 · 알람 · 스톱워치 · 타이머 탭을 묶는 셸.
class ClockHome extends StatefulWidget {
  const ClockHome({super.key});

  @override
  State<ClockHome> createState() => _ClockHomeState();
}

class _ClockHomeState extends State<ClockHome> {
  int _index = 2; // 스톱워치

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      // IndexedStack이라 탭을 옮겨도 스톱워치·타이머가 계속 돈다.
      body: IndexedStack(
        index: _index,
        children: const [
          WorldClockScreen(),
          AlarmScreen(),
          StopwatchScreen(),
          TimerScreen(),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        type: BottomNavigationBarType.fixed,
        backgroundColor: kClockCard,
        selectedItemColor: kClockAccent,
        unselectedItemColor: kClockSubText,
        selectedFontSize: 11,
        unselectedFontSize: 11,
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.public), label: '세계 시계'),
          BottomNavigationBarItem(icon: Icon(Icons.alarm), label: '알람'),
          BottomNavigationBarItem(icon: Icon(Icons.timer), label: '스톱워치'),
          BottomNavigationBarItem(
            icon: Icon(Icons.hourglass_bottom),
            label: '타이머',
          ),
        ],
      ),
    );
  }
}
