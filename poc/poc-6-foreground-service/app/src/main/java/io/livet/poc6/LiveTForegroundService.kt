package io.livet.poc6

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat

/**
 * LiveT PoC-6: minimal long-running foreground service.
 *
 * Goal: stay alive 12+ hours across all major Chinese ROMs and emit a
 * heartbeat tick every 5 s to disk. We then post-analyse the CSV for gaps
 * to detect ROM-imposed kills.
 *
 * Privacy invariants (mirrored from the production app philosophy bullet #3):
 *  - This service does NOT touch the microphone here (PoC-6 scope only).
 *  - When the production version captures audio, raw PCM is held in a
 *    bounded ring buffer and zeroed on dispatch. NO audio file is ever
 *    written to disk.
 *
 * Why this code looks dense in spite of being a PoC:
 *  - Notification channel + foreground type + wake-lock acquisition are
 *    the exact ingredients that determine whether MIUI/Honor/OPPO will
 *    or won't kill us. Missing any one -> false negative.
 */
class LiveTForegroundService : Service() {

    private val handler = Handler(Looper.getMainLooper())
    private var heartbeatLogger: HeartbeatLogger? = null
    private var wakeLock: PowerManager.WakeLock? = null
    @Volatile private var counter: Long = 0L

    private val tickRunnable = object : Runnable {
        override fun run() {
            counter += 1
            heartbeatLogger?.log(counter)
            updateNotification(counter)
            handler.postDelayed(this, TICK_INTERVAL_MS)
        }
    }

    override fun onCreate() {
        super.onCreate()
        Log.i(TAG, "onCreate")
        heartbeatLogger = HeartbeatLogger(this)
        // Wake lock keeps the CPU from suspending the service ticker.
        // We use PARTIAL_WAKE_LOCK because we don't need the screen on.
        wakeLock = (getSystemService(Context.POWER_SERVICE) as PowerManager).run {
            newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "$TAG::wakelock")
        }.also { it.setReferenceCounted(false) }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        Log.i(TAG, "onStartCommand")
        startForeground(NOTIFICATION_ID, buildNotification(0))

        wakeLock?.takeIf { !it.isHeld }?.acquire(WAKE_LOCK_HOURS * 60L * 60L * 1000L)

        // Idempotent — remove and re-post in case of restart
        handler.removeCallbacks(tickRunnable)
        handler.post(tickRunnable)

        // START_STICKY: if killed by OOM (not user), system tries to recreate
        return START_STICKY
    }

    override fun onDestroy() {
        Log.i(TAG, "onDestroy (last counter=$counter)")
        handler.removeCallbacks(tickRunnable)
        wakeLock?.takeIf { it.isHeld }?.release()
        heartbeatLogger?.close()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun buildNotification(counter: Long): Notification {
        ensureChannel()

        val pendingIntent = PendingIntent.getActivity(
            this, 0,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE,
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notif_title))
            .setContentText(getString(R.string.notif_text, counter))
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setOnlyAlertOnce(true)
            .build()
    }

    private fun updateNotification(counter: Long) {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(NOTIFICATION_ID, buildNotification(counter))
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        if (nm.getNotificationChannel(CHANNEL_ID) != null) return
        val channel = NotificationChannel(
            CHANNEL_ID,
            getString(R.string.notif_channel_name),
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = getString(R.string.notif_channel_desc)
            setShowBadge(false)
        }
        nm.createNotificationChannel(channel)
    }

    companion object {
        private const val TAG = "LiveTPoc6"
        private const val CHANNEL_ID = "livet-poc6-fgs"
        private const val NOTIFICATION_ID = 1001
        private const val TICK_INTERVAL_MS = 5_000L
        private const val WAKE_LOCK_HOURS = 24L

        fun start(ctx: Context) {
            val intent = Intent(ctx, LiveTForegroundService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                ctx.startForegroundService(intent)
            } else {
                ctx.startService(intent)
            }
        }

        fun stop(ctx: Context) {
            ctx.stopService(Intent(ctx, LiveTForegroundService::class.java))
        }
    }
}
