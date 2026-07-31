import 'package:flutter/services.dart';

/// Kotlin `StopwatchEngine` 이 보내주는 상태 한 벌.
///
/// 계산은 전부 네이티브 쪽에서 끝난 값이다 — 여기서 다시 가공하지 않는다.
class StopwatchState {
  final int elapsedMs;
  final bool running;
  final List<int> lapsMs;
  final int currentLapMs;
  final int bestIndex;
  final int worstIndex;

  const StopwatchState({
    required this.elapsedMs,
    required this.running,
    required this.lapsMs,
    required this.currentLapMs,
    required this.bestIndex,
    required this.worstIndex,
  });

  static const empty = StopwatchState(
    elapsedMs: 0,
    running: false,
    lapsMs: [],
    currentLapMs: 0,
    bestIndex: -1,
    worstIndex: -1,
  );

  factory StopwatchState.fromMap(Map<Object?, Object?> map) {
    return StopwatchState(
      elapsedMs: map['elapsedMs']! as int,
      running: map['running']! as bool,
      lapsMs: (map['laps']! as List<Object?>).cast<int>(),
      currentLapMs: map['currentLapMs']! as int,
      bestIndex: map['bestIndex']! as int,
      worstIndex: map['worstIndex']! as int,
    );
  }

  bool get hasRecord => running || elapsedMs > 0;
}

/// 화면과 네이티브 기능 모듈을 잇는 통로. 로직은 담지 않는다.
class StopwatchChannel {
  static const _method = MethodChannel('cloud.jsangho/stopwatch');
  static const _events = EventChannel('cloud.jsangho/stopwatch/state');

  const StopwatchChannel();

  Stream<StopwatchState> states() => _events.receiveBroadcastStream().map(
    (e) => StopwatchState.fromMap(e as Map<Object?, Object?>),
  );

  Future<void> start() => _method.invokeMethod<void>('start');
  Future<void> stop() => _method.invokeMethod<void>('stop');
  Future<void> lap() => _method.invokeMethod<void>('lap');
  Future<void> reset() => _method.invokeMethod<void>('reset');
}
