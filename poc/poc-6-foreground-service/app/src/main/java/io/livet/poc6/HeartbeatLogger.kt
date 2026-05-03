package io.livet.poc6

import android.content.Context
import android.os.Build
import android.os.Environment
import android.util.Log
import java.io.BufferedWriter
import java.io.File
import java.io.FileWriter
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Append-only CSV logger for the heartbeat counter.
 *
 * Format: timestamp_iso,counter,device_uptime_ms,system_uptime_ms
 *
 * Path on Android 11+ : /sdcard/Android/data/io.livet.poc6/files/heartbeat.csv
 *   (app-specific external storage; no permission needed; survives reboot)
 *
 * Why we write to *external* storage in this PoC:
 *   - Easy to pull via `adb pull` for the post-test gap analyser
 *   - Production app uses internal storage only (privacy invariant)
 */
class HeartbeatLogger(ctx: Context) {

    private val writer: BufferedWriter
    private val isoFmt = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss.SSSXXX", Locale.US)

    init {
        val dir = ctx.getExternalFilesDir(null)
            ?: ctx.filesDir // fallback if external null
        if (!dir.exists()) dir.mkdirs()
        val file = File(dir, "heartbeat.csv")
        val fresh = !file.exists()
        writer = BufferedWriter(FileWriter(file, /* append */ true))
        if (fresh) {
            writer.write("timestamp_iso,counter,device_uptime_ms,system_uptime_ms")
            writer.newLine()
        }
        writer.flush()
        Log.i(TAG, "Logging to ${file.absolutePath} (fresh=$fresh)")
    }

    fun log(counter: Long) {
        try {
            val now = System.currentTimeMillis()
            val deviceUptime = android.os.SystemClock.uptimeMillis()
            val systemUptime = android.os.SystemClock.elapsedRealtime()
            writer.write("${isoFmt.format(Date(now))},$counter,$deviceUptime,$systemUptime")
            writer.newLine()
            writer.flush()
        } catch (e: Exception) {
            Log.e(TAG, "log() failed", e)
        }
    }

    fun close() {
        try { writer.close() } catch (_: Exception) {}
    }

    companion object {
        private const val TAG = "LiveTPoc6"
    }
}
