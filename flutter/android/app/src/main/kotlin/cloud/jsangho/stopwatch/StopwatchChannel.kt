package cloud.jsangho.stopwatch

import android.os.Handler
import android.os.Looper
import io.flutter.plugin.common.BinaryMessenger
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodCall
import io.flutter.plugin.common.MethodChannel

/**
 * [StopwatchEngine] 를 Dart 화면에 연결한다.
 *
 * - 메서드 채널: 화면 → 기능 (start/stop/lap/reset)
 * - 이벤트 채널: 기능 → 화면 (실행 중 [TICK_MS] 간격으로 상태 전송)
 */
class StopwatchChannel(messenger: BinaryMessenger) :
    MethodChannel.MethodCallHandler, EventChannel.StreamHandler {

    companion object {
        const val METHOD_CHANNEL = "cloud.jsangho/stopwatch"
        const val EVENT_CHANNEL = "cloud.jsangho/stopwatch/state"
        private const val TICK_MS = 30L
    }

    private val engine = StopwatchEngine()
    private val methodChannel = MethodChannel(messenger, METHOD_CHANNEL)
    private val eventChannel = EventChannel(messenger, EVENT_CHANNEL)
    private val handler = Handler(Looper.getMainLooper())
    private var sink: EventChannel.EventSink? = null

    /** 실행 중일 때만 스스로 다시 예약한다 — 정지하면 틱이 멈춘다. */
    private val tick = object : Runnable {
        override fun run() {
            emit()
            if (engine.isRunning) handler.postDelayed(this, TICK_MS)
        }
    }

    init {
        methodChannel.setMethodCallHandler(this)
        eventChannel.setStreamHandler(this)
    }

    override fun onMethodCall(call: MethodCall, result: MethodChannel.Result) {
        when (call.method) {
            "start" -> {
                engine.start()
                scheduleTick()
            }
            "stop" -> {
                engine.stop()
                handler.removeCallbacks(tick)
            }
            "lap" -> engine.lap()
            "reset" -> {
                engine.reset()
                handler.removeCallbacks(tick)
            }
            "snapshot" -> {
                result.success(engine.snapshot())
                return
            }
            else -> {
                result.notImplemented()
                return
            }
        }
        // 화면이 즉시 반응하도록 명령 직후 한 번 더 밀어준다.
        emit()
        result.success(engine.snapshot())
    }

    override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
        sink = events
        emit()
        if (engine.isRunning) scheduleTick()
    }

    override fun onCancel(arguments: Any?) {
        handler.removeCallbacks(tick)
        sink = null
    }

    /** 화면이 닫힐 때 예약된 틱과 핸들러를 반드시 걷어낸다. */
    fun dispose() {
        handler.removeCallbacks(tick)
        sink = null
        methodChannel.setMethodCallHandler(null)
        eventChannel.setStreamHandler(null)
    }

    private fun scheduleTick() {
        handler.removeCallbacks(tick)
        handler.postDelayed(tick, TICK_MS)
    }

    private fun emit() {
        sink?.success(engine.snapshot())
    }
}
