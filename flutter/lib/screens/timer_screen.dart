import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../theme/clock_colors.dart';

enum _Status { idle, running, paused }

/// 카운트다운 타이머 화면.
class TimerScreen extends StatefulWidget {
  const TimerScreen({super.key});

  @override
  State<TimerScreen> createState() => _TimerScreenState();
}

class _TimerScreenState extends State<TimerScreen> {
  final _hourCtrl = FixedExtentScrollController();
  final _minuteCtrl = FixedExtentScrollController(initialItem: 5);
  final _secondCtrl = FixedExtentScrollController();

  /// 시작 시점에 확정된 전체 시간. 남은 시간은 여기서 파생시킨다.
  Duration _total = Duration.zero;
  final Stopwatch _watch = Stopwatch();
  Timer? _ticker;
  _Status _status = _Status.idle;

  @override
  void dispose() {
    _ticker?.cancel();
    _hourCtrl.dispose();
    _minuteCtrl.dispose();
    _secondCtrl.dispose();
    super.dispose();
  }

  Duration get _remaining {
    final left = _total - _watch.elapsed;
    return left.isNegative ? Duration.zero : left;
  }

  Duration get _picked => Duration(
    hours: _hourCtrl.hasClients ? _hourCtrl.selectedItem : 0,
    minutes: _minuteCtrl.hasClients ? _minuteCtrl.selectedItem : 5,
    seconds: _secondCtrl.hasClients ? _secondCtrl.selectedItem : 0,
  );

  void _startTicker() {
    _ticker?.cancel();
    _ticker = Timer.periodic(const Duration(milliseconds: 200), (_) {
      if (_remaining == Duration.zero) {
        _finish();
      } else {
        setState(() {});
      }
    });
  }

  void _start() {
    final picked = _picked;
    if (picked == Duration.zero) return;
    setState(() {
      _total = picked;
      _watch
        ..reset()
        ..start();
      _status = _Status.running;
    });
    _startTicker();
  }

  void _pause() {
    _ticker?.cancel();
    _ticker = null;
    setState(() {
      _watch.stop();
      _status = _Status.paused;
    });
  }

  void _resume() {
    setState(() {
      _watch.start();
      _status = _Status.running;
    });
    _startTicker();
  }

  void _cancel() {
    _ticker?.cancel();
    _ticker = null;
    setState(() {
      _watch
        ..stop()
        ..reset();
      _total = Duration.zero;
      _status = _Status.idle;
    });
  }

  Future<void> _finish() async {
    _cancel();
    SystemSound.play(SystemSoundType.alert);
    HapticFeedback.heavyImpact();
    if (!mounted) return;

    await showDialog<void>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: kClockCard,
        title: const Text('타이머 종료', style: TextStyle(color: kClockText)),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('확인', style: TextStyle(color: kClockAccent)),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final idle = _status == _Status.idle;

    return Scaffold(
      backgroundColor: kClockBg,
      appBar: AppBar(
        backgroundColor: kClockBg,
        surfaceTintColor: kClockBg,
        title: const Text(
          '타이머',
          style: TextStyle(
            color: kClockText,
            fontSize: 32,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            Expanded(
              flex: 8,
              child: idle
                  ? _DurationPicker(
                      hourCtrl: _hourCtrl,
                      minuteCtrl: _minuteCtrl,
                      secondCtrl: _secondCtrl,
                      // 선택이 0이 되면 시작 버튼이 비활성화돼야 한다.
                      onChanged: () => setState(() {}),
                    )
                  : _Countdown(remaining: _remaining, total: _total),
            ),
            const Spacer(),
            _Controls(
              status: _status,
              canStart: !idle || _picked > Duration.zero,
              onCancel: idle ? null : _cancel,
              onPrimary: switch (_status) {
                _Status.idle => _start,
                _Status.running => _pause,
                _Status.paused => _resume,
              },
            ),
            const Spacer(flex: 2),
          ],
        ),
      ),
    );
  }
}

// ── 시/분/초 휠 ──────────────────────────────────────────────────────────

class _DurationPicker extends StatelessWidget {
  final FixedExtentScrollController hourCtrl;
  final FixedExtentScrollController minuteCtrl;
  final FixedExtentScrollController secondCtrl;
  final VoidCallback onChanged;

  const _DurationPicker({
    required this.hourCtrl,
    required this.minuteCtrl,
    required this.secondCtrl,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _Wheel(
          controller: hourCtrl,
          count: 24,
          unit: '시간',
          onChanged: onChanged,
        ),
        _Wheel(
          controller: minuteCtrl,
          count: 60,
          unit: '분',
          onChanged: onChanged,
        ),
        _Wheel(
          controller: secondCtrl,
          count: 60,
          unit: '초',
          onChanged: onChanged,
        ),
      ],
    );
  }
}

class _Wheel extends StatelessWidget {
  final FixedExtentScrollController controller;
  final int count;
  final String unit;
  final VoidCallback onChanged;

  const _Wheel({
    required this.controller,
    required this.count,
    required this.unit,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 100,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(
            width: 52,
            child: ListWheelScrollView.useDelegate(
              controller: controller,
              itemExtent: 40,
              perspective: 0.004,
              physics: const FixedExtentScrollPhysics(),
              onSelectedItemChanged: (_) => onChanged(),
              childDelegate: ListWheelChildBuilderDelegate(
                childCount: count,
                builder: (context, i) => Center(
                  child: Text(
                    '$i',
                    style: const TextStyle(color: kClockText, fontSize: 24),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 4),
          Text(
            unit,
            style: const TextStyle(color: kClockSubText, fontSize: 15),
          ),
        ],
      ),
    );
  }
}

// ── 남은 시간 ────────────────────────────────────────────────────────────

class _Countdown extends StatelessWidget {
  final Duration remaining;
  final Duration total;

  const _Countdown({required this.remaining, required this.total});

  @override
  Widget build(BuildContext context) {
    final progress = total == Duration.zero
        ? 0.0
        : remaining.inMilliseconds / total.inMilliseconds;
    final endsAt = DateTime.now().add(remaining);

    return Center(
      child: SizedBox(
        width: 260,
        height: 260,
        child: Stack(
          alignment: Alignment.center,
          children: [
            SizedBox.expand(
              child: CircularProgressIndicator(
                value: progress,
                strokeWidth: 6,
                backgroundColor: kClockDivider,
                valueColor: const AlwaysStoppedAnimation(kClockAccent),
              ),
            ),
            Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                FittedBox(
                  fit: BoxFit.scaleDown,
                  child: Text(
                    _formatRemaining(remaining),
                    style: const TextStyle(
                      color: kClockText,
                      fontSize: 56,
                      fontWeight: FontWeight.w200,
                      fontFeatures: [FontFeature.tabularFigures()],
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(
                      Icons.notifications,
                      color: kClockSubText,
                      size: 15,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      '${endsAt.hour.toString().padLeft(2, '0')}:'
                      '${endsAt.minute.toString().padLeft(2, '0')}',
                      style: const TextStyle(
                        color: kClockSubText,
                        fontSize: 15,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// 1시간 미만이면 mm:ss, 그 이상이면 h:mm:ss. 남은 시간은 올림해서 보여준다.
String _formatRemaining(Duration d) {
  final ceil = Duration(seconds: (d.inMilliseconds / 1000).ceil());
  final hours = ceil.inHours;
  final minutes = ceil.inMinutes.remainder(60).toString().padLeft(2, '0');
  final seconds = ceil.inSeconds.remainder(60).toString().padLeft(2, '0');
  return hours > 0 ? '$hours:$minutes:$seconds' : '$minutes:$seconds';
}

// ── 취소 / 시작·일시정지 버튼 ────────────────────────────────────────────

class _Controls extends StatelessWidget {
  final _Status status;
  final bool canStart;
  final VoidCallback? onCancel;
  final VoidCallback onPrimary;

  const _Controls({
    required this.status,
    required this.canStart,
    required this.onCancel,
    required this.onPrimary,
  });

  @override
  Widget build(BuildContext context) {
    final (label, fg, bg) = switch (status) {
      _Status.running => ('일시 정지', kClockAccent, kClockAccentBg),
      _Status.paused => ('재개', kClockGreen, kClockGreenBg),
      _Status.idle => ('시작', kClockGreen, kClockGreenBg),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 36),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          _RoundButton(
            label: '취소',
            background: onCancel == null ? kClockCard : kClockButton,
            foreground: onCancel == null ? kClockDisabled : kClockText,
            onPressed: onCancel,
          ),
          _RoundButton(
            label: label,
            background: canStart ? bg : kClockCard,
            foreground: canStart ? fg : kClockDisabled,
            onPressed: canStart ? onPrimary : null,
          ),
        ],
      ),
    );
  }
}

class _RoundButton extends StatelessWidget {
  final String label;
  final Color background;
  final Color foreground;
  final VoidCallback? onPressed;

  const _RoundButton({
    required this.label,
    required this.background,
    required this.foreground,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 82,
      height: 82,
      child: Material(
        color: background,
        shape: const CircleBorder(side: BorderSide(color: kClockBg, width: 2)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onPressed,
          child: Center(
            child: Text(
              label,
              textAlign: TextAlign.center,
              style: TextStyle(
                color: foreground,
                fontSize: 17,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
