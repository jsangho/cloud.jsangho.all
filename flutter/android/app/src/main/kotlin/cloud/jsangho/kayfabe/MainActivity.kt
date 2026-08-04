package cloud.jsangho.jsh_flutter

import cloud.jsangho.stopwatch.StopwatchChannel
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine

class MainActivity : FlutterActivity() {

    private var stopwatch: StopwatchChannel? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        stopwatch = StopwatchChannel(flutterEngine.dartExecutor.binaryMessenger)
    }

    override fun cleanUpFlutterEngine(flutterEngine: FlutterEngine) {
        stopwatch?.dispose()
        stopwatch = null
        super.cleanUpFlutterEngine(flutterEngine)
    }
}
