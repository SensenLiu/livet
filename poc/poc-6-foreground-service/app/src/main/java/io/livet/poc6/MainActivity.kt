package io.livet.poc6

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private val handler = Handler(Looper.getMainLooper())
    private val refresher = object : Runnable {
        override fun run() {
            updateState()
            handler.postDelayed(this, 1_500L)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        // Notifications permission (Android 13+)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                ActivityCompat.requestPermissions(
                    this, arrayOf(Manifest.permission.POST_NOTIFICATIONS), 100
                )
            }
        }

        findViewById<android.widget.Button>(R.id.btn_start).setOnClickListener {
            LiveTForegroundService.start(applicationContext)
        }
        findViewById<android.widget.Button>(R.id.btn_stop).setOnClickListener {
            LiveTForegroundService.stop(applicationContext)
        }
        findViewById<android.widget.Button>(R.id.btn_battery).setOnClickListener {
            BatteryWhitelistHelper.requestIgnoreBatteryOptimisations(this)
        }
    }

    override fun onResume() {
        super.onResume()
        handler.post(refresher)
    }

    override fun onPause() {
        super.onPause()
        handler.removeCallbacks(refresher)
    }

    private fun updateState() {
        val whitelisted = BatteryWhitelistHelper.isIgnoringBatteryOptimisations(this)
        val hint = BatteryWhitelistHelper.oemAdditionalHint()

        findViewById<TextView>(R.id.txt_status).text = buildString {
            append("ROM: ${Build.BRAND} ${Build.MODEL}\n")
            append("Android: ${Build.VERSION.RELEASE} (API ${Build.VERSION.SDK_INT})\n")
            append("Battery whitelisted: ${if (whitelisted) "✓ YES" else "✗ NO"}\n")
            if (hint != null) append("\n额外: $hint\n")
            append("\n服务启动后,heartbeat 写入 \n/sdcard/Android/data/io.livet.poc6/files/heartbeat.csv\n")
            append("\nadb pull 后用 analyze_heartbeat.py 分析 gap 即可.")
        }
    }
}
