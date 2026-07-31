import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/clock_colors.dart';

class _Alarm {
  final TimeOfDay time;
  final String label;
  bool enabled;

  _Alarm({required this.time, required this.label, this.enabled = true});

  /// 정렬·중복 발동 방지에 쓰는 분 단위 키.
  int get minuteOfDay => time.hour * 60 + time.minute;
}

/// 알람 목록 화면.
///
/// 앱이 떠 있는 동안에만 울린다 — 백그라운드/종료 상태 알림은
/// `flutter_local_notifications` 같은 플러그인과 플랫폼 설정이 따로 필요하다.
class AlarmScreen extends StatefulWidget {
  const AlarmScreen({super.key});

  @override
  State<AlarmScreen> createState() => _AlarmScreenState();
}

class _AlarmScreenState extends State<AlarmScreen> {
  final List<_Alarm> _alarms = [
    _Alarm(time: const TimeOfDay(hour: 7, minute: 0), label: '기상'),
    _Alarm(
      time: const TimeOfDay(hour: 12, minute: 30),
      label: '점심',
      enabled: false,
    ),
  ];
  Timer? _ticker;

  /// 같은 분에 알람이 반복 발동하지 않도록 마지막 발동 시각을 기억한다.
  String? _lastFiredKey;

  @override
  void initState() {
    super.initState();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) => _checkAlarms());
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  void _checkAlarms() {
    final now = DateTime.now();
    final key = '${now.year}${now.month}${now.day}-${now.hour}:${now.minute}';
    if (key == _lastFiredKey) return;

    final due = _alarms.where(
      (a) =>
          a.enabled && a.time.hour == now.hour && a.time.minute == now.minute,
    );
    if (due.isEmpty) return;

    _lastFiredKey = key;
    _ring(due.first);
  }

  Future<void> _ring(_Alarm alarm) async {
    SystemSound.play(SystemSoundType.alert);
    HapticFeedback.heavyImpact();
    if (!mounted) return;

    await showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: kClockCard,
        title: Text(
          _formatTime(alarm.time),
          style: const TextStyle(color: kClockText, fontSize: 28),
        ),
        content: Text(
          alarm.label,
          style: const TextStyle(color: kClockSubText, fontSize: 15),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('중지', style: TextStyle(color: kClockAccent)),
          ),
        ],
      ),
    );
  }

  Future<void> _addAlarm() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
      builder: (context, child) => Theme(
        data: ThemeData.dark(useMaterial3: true).copyWith(
          colorScheme: const ColorScheme.dark(
            primary: kClockAccent,
            surface: kClockCard,
          ),
        ),
        child: child!,
      ),
    );
    if (picked == null) return;

    setState(() {
      _alarms.add(_Alarm(time: picked, label: '알람'));
      _alarms.sort((a, b) => a.minuteOfDay.compareTo(b.minuteOfDay));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kClockBg,
      appBar: AppBar(
        backgroundColor: kClockBg,
        surfaceTintColor: kClockBg,
        title: const Text(
          '알람',
          style: TextStyle(
            color: kClockText,
            fontSize: 32,
            fontWeight: FontWeight.w700,
          ),
        ),
        actions: [
          IconButton(
            onPressed: _addAlarm,
            icon: const Icon(Icons.add, color: kClockAccent),
            tooltip: '알람 추가',
          ),
        ],
      ),
      body: _alarms.isEmpty
          ? const Center(
              child: Text(
                '알람 없음',
                style: TextStyle(color: kClockSubText, fontSize: 17),
              ),
            )
          : ListView.separated(
              itemCount: _alarms.length,
              separatorBuilder: (_, _) => const Divider(
                color: kClockDivider,
                height: 1,
                thickness: 0.5,
                indent: 20,
              ),
              itemBuilder: (context, i) {
                final alarm = _alarms[i];
                return Dismissible(
                  key: ObjectKey(alarm),
                  direction: DismissDirection.endToStart,
                  background: Container(
                    color: kClockRed,
                    alignment: Alignment.centerRight,
                    padding: const EdgeInsets.only(right: 24),
                    child: const Icon(Icons.delete, color: kClockText),
                  ),
                  onDismissed: (_) => setState(() => _alarms.removeAt(i)),
                  child: _AlarmRow(
                    alarm: alarm,
                    onToggle: (on) => setState(() => alarm.enabled = on),
                  ),
                );
              },
            ),
    );
  }
}

// ── 알람 한 줄 ───────────────────────────────────────────────────────────

class _AlarmRow extends StatelessWidget {
  final _Alarm alarm;
  final ValueChanged<bool> onToggle;

  const _AlarmRow({required this.alarm, required this.onToggle});

  @override
  Widget build(BuildContext context) {
    final color = alarm.enabled ? kClockText : kClockDisabled;

    return Padding(
      padding: const EdgeInsets.fromLTRB(20, 10, 12, 10),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _formatTime(alarm.time),
                  style: TextStyle(
                    color: color,
                    fontSize: 44,
                    fontWeight: FontWeight.w300,
                    fontFeatures: const [FontFeature.tabularFigures()],
                  ),
                ),
                Text(
                  alarm.label,
                  style: TextStyle(
                    color: alarm.enabled ? kClockSubText : kClockDisabled,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
          Switch.adaptive(
            value: alarm.enabled,
            activeThumbColor: kClockText,
            activeTrackColor: kClockGreen,
            onChanged: onToggle,
          ),
        ],
      ),
    );
  }
}

/// "오전 7:00" 형태.
String _formatTime(TimeOfDay t) {
  final hour12 = t.hour % 12 == 0 ? 12 : t.hour % 12;
  final period = t.hour < 12 ? '오전' : '오후';
  return '$period $hour12:${t.minute.toString().padLeft(2, '0')}';
}
