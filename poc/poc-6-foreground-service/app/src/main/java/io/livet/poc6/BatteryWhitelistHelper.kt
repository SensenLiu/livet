package io.livet.poc6

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings

/**
 * Helpers to detect & request battery-optimisation whitelist.
 *
 * The production app will replace this with the full 6-ROM router that
 * jumps users to MIUI / Honor / OPPO / vivo / Flyme / AOSP specific
 * settings screens with on-screen GIF guidance. For PoC-6 we use only the
 * standard Android intent (which works as fallback on all ROMs but may not
 * hit the optimal screen on some).
 */
object BatteryWhitelistHelper {

    fun isIgnoringBatteryOptimisations(ctx: Context): Boolean {
        val pm = ctx.getSystemService(Context.POWER_SERVICE) as PowerManager
        return pm.isIgnoringBatteryOptimizations(ctx.packageName)
    }

    @SuppressLint("BatteryLife")
    fun requestIgnoreBatteryOptimisations(ctx: Context) {
        // Standard Android intent — works on AOSP & most OEMs
        val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
            data = Uri.parse("package:${ctx.packageName}")
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        try {
            ctx.startActivity(intent)
        } catch (_: Exception) {
            // Fallback: just open battery settings page
            try {
                ctx.startActivity(Intent(Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                })
            } catch (_: Exception) {
                // Worst case: app details page
                ctx.startActivity(Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS).apply {
                    data = Uri.parse("package:${ctx.packageName}")
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                })
            }
        }
    }

    /**
     * Returns a human-readable hint for which OEM-specific screen the user
     * should ALSO check (since Android's standard whitelist is sometimes
     * insufficient on Chinese ROMs).
     */
    fun oemAdditionalHint(): String? {
        val brand = Build.BRAND.lowercase()
        val manuf = Build.MANUFACTURER.lowercase()
        return when {
            "xiaomi" in brand || "redmi" in brand || "xiaomi" in manuf ->
                "MIUI/HyperOS: 设置 → 应用 → LiveT-PoC6 → 自启动 / 省电策略 → 无限制"
            "huawei" in brand || "honor" in brand ->
                "EMUI/MagicOS: 设置 → 应用 → LiveT-PoC6 → 启动管理 → 全部手动管理(开三项)"
            "oppo" in brand || "realme" in brand ->
                "ColorOS: 设置 → 电池 → 应用电池优化 → LiveT-PoC6 → 不优化"
            "vivo" in brand || "iqoo" in brand ->
                "OriginOS: 设置 → 电池 → 后台高耗电 → LiveT-PoC6 → 允许"
            "meizu" in brand ->
                "Flyme: 设置 → 应用管理 → LiveT-PoC6 → 权限 → 后台运行"
            else -> null
        }
    }
}
