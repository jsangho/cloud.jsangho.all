package cloud.jsangho.stopwatch

import android.os.SystemClock

/**
 * 스톱워치 기능 담당 — 계측, 랩 기록, 최단/최장 랩 판정.
 *
 * 화면(Dart)은 이 엔진이 만든 상태를 그리기만 한다.
 * 벽시계(System.currentTimeMillis) 대신 elapsedRealtime을 쓰므로 사용자가
 * 기기 시각을 바꿔도 계측이 어긋나지 않는다.
 */
class StopwatchEngine {

    private var startedAt = 0L
    private var accumulatedMs = 0L
    private val laps = mutableListOf<Long>()

    var isRunning = false
        private set

    /** 시작 이후 흐른 전체 시간. */
    val elapsedMs: Long
        get() = if (isRunning) {
            accumulatedMs + (SystemClock.elapsedRealtime() - startedAt)
        } else {
            accumulatedMs
        }

    fun start() {
        if (isRunning) return
        startedAt = SystemClock.elapsedRealtime()
        isRunning = true
    }

    fun stop() {
        if (!isRunning) return
        accumulatedMs = elapsedMs
        isRunning = false
    }

    /** 진행 중인 랩을 확정한다. 정지 상태에서는 무시한다. */
    fun lap() {
        if (!isRunning) return
        laps.add(elapsedMs - laps.sum())
    }

    fun reset() {
        isRunning = false
        startedAt = 0L
        accumulatedMs = 0L
        laps.clear()
    }

    /**
     * 화면이 그릴 상태 한 벌.
     *
     * 진행 중인 랩은 저장하지 않고 매번 파생시킨다 — 전체 경과와 따로 들고 있으면
     * 두 값이 어긋날 수 있다.
     */
    fun snapshot(): Map<String, Any> {
        val elapsed = elapsedMs

        // 최단/최장은 완료된 랩이 2개 이상일 때만 의미가 있다.
        var bestIndex = -1
        var worstIndex = -1
        if (laps.size >= 2) {
            bestIndex = laps.indices.minByOrNull { laps[it] } ?: -1
            worstIndex = laps.indices.maxByOrNull { laps[it] } ?: -1
        }

        return mapOf(
            "elapsedMs" to elapsed,
            "running" to isRunning,
            "laps" to laps.toList(),
            "currentLapMs" to elapsed - laps.sum(),
            "bestIndex" to bestIndex,
            "worstIndex" to worstIndex,
        )
    }
}
