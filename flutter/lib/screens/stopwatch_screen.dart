import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../stopwatch_channel.dart';
import '../theme/clock_colors.dart';

/// 스톱워치 화면 — 그리기만 한다.
///
/// 계측·랩 기록·최단/최장 판정은 Kotlin `StopwatchEngine` 이 맡고,
/// 여기서는 [StopwatchChannel] 이 흘려주는 상태를 표시하고 명령만 보낸다.
class StopwatchScreen extends StatefulWidget {
  const StopwatchScreen({super.key});

  @override
  State<StopwatchScreen> createState() => _StopwatchScreenState();
}

class _StopwatchScreenState extends State<StopwatchScreen> {
  static const _channel = StopwatchChannel();
  late final Stream<StopwatchState> _states = _channel.states();

  /// 기능 모듈이 Android 전용이라 다른 플랫폼에서는 채널이 응답하지 않는다.
  /// EventChannel은 미등록 채널에 조용히 실패하므로 오류 대신 플랫폼으로 판단한다.
  bool get _supported =>
      !kIsWeb && defaultTargetPlatform == TargetPlatform.android;

  @override
  Widget build(BuildContext context) {
    if (!_supported) {
      return const Scaffold(
        backgroundColor: kClockBg,
        body: SafeArea(child: _Unavailable()),
      );
    }

    return Scaffold(
      backgroundColor: kClockBg,
      body: SafeArea(
        child: StreamBuilder<StopwatchState>(
          stream: _states,
          initialData: StopwatchState.empty,
          builder: (context, snapshot) {
            if (snapshot.hasError) {
              return const _Unavailable();
            }
            return _StopwatchView(
              state: snapshot.data ?? StopwatchState.empty,
              onLapOrReset: (running) =>
                  running ? _channel.lap() : _channel.reset(),
              onToggleRun: (running) =>
                  running ? _channel.stop() : _channel.start(),
            );
          },
        ),
      ),
    );
  }
}

/// 네이티브 기능 모듈이 없는 플랫폼(웹·데스크톱)에서 보이는 화면.
class _Unavailable extends StatelessWidget {
  const _Unavailable();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: 32),
        child: Text(
          '스톱워치 기능은 Android 네이티브 모듈에서 동작합니다.\nAndroid 기기에서 실행하세요.',
          textAlign: TextAlign.center,
          style: TextStyle(color: kClockSubText, fontSize: 15, height: 1.5),
        ),
      ),
    );
  }
}

class _StopwatchView extends StatelessWidget {
  final StopwatchState state;
  final void Function(bool running) onLapOrReset;
  final void Function(bool running) onToggleRun;

  const _StopwatchView({
    required this.state,
    required this.onLapOrReset,
    required this.onToggleRun,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const Spacer(flex: 2),
        _TimeDisplay(text: _format(state.elapsedMs)),
        const Spacer(flex: 2),
        _Controls(
          running: state.running,
          hasRecord: state.hasRecord,
          onLapOrReset: () => onLapOrReset(state.running),
          onToggleRun: () => onToggleRun(state.running),
        ),
        const Spacer(flex: 2),
        Expanded(flex: 9, child: _LapList(state: state)),
      ],
    );
  }
}

/// mm:ss.cc (1시간 이상이면 h:mm:ss.cc)
String _format(int ms) {
  final hours = ms ~/ 3600000;
  final minutes = (ms ~/ 60000 % 60).toString().padLeft(2, '0');
  final seconds = (ms ~/ 1000 % 60).toString().padLeft(2, '0');
  final centis = (ms % 1000 ~/ 10).toString().padLeft(2, '0');
  return hours > 0
      ? '$hours:$minutes:$seconds.$centis'
      : '$minutes:$seconds.$centis';
}

// ── 시간 표시 ────────────────────────────────────────────────────────────

class _TimeDisplay extends StatelessWidget {
  final String text;

  const _TimeDisplay({required this.text});

  @override
  Widget build(BuildContext context) {
    return FittedBox(
      fit: BoxFit.scaleDown,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Text(
          text,
          style: const TextStyle(
            color: kClockText,
            fontSize: 76,
            fontWeight: FontWeight.w200,
            letterSpacing: -2,
            fontFeatures: [FontFeature.tabularFigures()],
          ),
        ),
      ),
    );
  }
}

// ── 랩 / 시작·중단 버튼 ──────────────────────────────────────────────────

class _Controls extends StatelessWidget {
  final bool running;
  final bool hasRecord;
  final VoidCallback onLapOrReset;
  final VoidCallback onToggleRun;

  const _Controls({
    required this.running,
    required this.hasRecord,
    required this.onLapOrReset,
    required this.onToggleRun,
  });

  @override
  Widget build(BuildContext context) {
    final lapEnabled = running || hasRecord;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 36),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          _RoundButton(
            // 정지 상태에서 기록이 남아 있을 때만 재설정으로 바뀐다.
            label: !running && hasRecord ? '재설정' : '랩',
            background: lapEnabled ? kClockButton : kClockCard,
            foreground: lapEnabled ? kClockText : kClockDisabled,
            onPressed: lapEnabled ? onLapOrReset : null,
          ),
          _RoundButton(
            label: running ? '중단' : '시작',
            background: running ? kClockRedBg : kClockGreenBg,
            foreground: running ? kClockRed : kClockGreen,
            onPressed: onToggleRun,
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

// ── 랩 목록 ──────────────────────────────────────────────────────────────

class _LapList extends StatelessWidget {
  final StopwatchState state;

  const _LapList({required this.state});

  @override
  Widget build(BuildContext context) {
    final laps = state.lapsMs;
    // 최신 랩이 위로 오도록 역순 렌더링, 진행 중인 랩은 맨 위.
    final showsCurrent = state.hasRecord;
    final rowCount = laps.length + (showsCurrent ? 1 : 0);

    return ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      itemCount: rowCount,
      separatorBuilder: (_, _) =>
          const Divider(color: kClockDivider, height: 1, thickness: 0.5),
      itemBuilder: (context, row) {
        if (showsCurrent && row == 0) {
          return _LapRow(
            number: laps.length + 1,
            value: state.currentLapMs,
            color: kClockText,
          );
        }
        final index = laps.length - 1 - (showsCurrent ? row - 1 : row);
        return _LapRow(
          number: index + 1,
          value: laps[index],
          color: _colorOf(index),
        );
      },
    );
  }

  Color _colorOf(int index) {
    if (index == state.bestIndex) return kClockGreen;
    if (index == state.worstIndex) return kClockRed;
    return kClockText;
  }
}

class _LapRow extends StatelessWidget {
  final int number;
  final int value;
  final Color color;

  const _LapRow({
    required this.number,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    final style = TextStyle(
      color: color,
      fontSize: 17,
      fontWeight: FontWeight.w400,
      fontFeatures: const [FontFeature.tabularFigures()],
    );

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text('랩 $number', style: style),
          Text(_format(value), style: style),
        ],
      ),
    );
  }
}
