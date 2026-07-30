package com.naira.remote.security

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.admin.DeviceAdminReceiver
import android.content.Context
import android.content.Intent
import android.os.Build
import android.util.Log
import androidx.core.app.NotificationCompat

/**
 * NairaDeviceAdminReceiver handles Device Administrator lifecycle events and
 * tracks DeviceAdmin active state in SharedPreferences.
 */
class NairaDeviceAdminReceiver : DeviceAdminReceiver() {

    companion object {
        private const val TAG = "NairaDeviceAdminReceiver"
        private const val PREFS_NAME = "naira_device_admin_prefs"
        private const val KEY_ADMIN_ACTIVE = "device_admin_active"
        private const val WARNING_CHANNEL_ID = "naira_device_admin_warning"

        /**
         * Reads the device admin status from SharedPreferences.
         */
        fun isAdminActive(context: Context): Boolean {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            return prefs.getBoolean(KEY_ADMIN_ACTIVE, false)
        }

        private fun setAdminActive(context: Context, active: Boolean) {
            val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit().putBoolean(KEY_ADMIN_ACTIVE, active).apply()
        }
    }

    override fun onEnabled(context: Context, intent: Intent) {
        super.onEnabled(context, intent)
        Log.i(TAG, "Device Admin rights granted/enabled.")
        setAdminActive(context, true)
    }

    override fun onDisabled(context: Context, intent: Intent) {
        super.onDisabled(context, intent)
        Log.w(TAG, "Device Admin rights revoked/disabled!")
        setAdminActive(context, false)
        notifyForegroundServiceWarning(context)
    }

    override fun onPasswordFailed(context: Context, intent: Intent) {
        super.onPasswordFailed(context, intent)
        Log.w(TAG, "Device unlock password attempt failed (possible brute-force event detected).")
    }

    private fun notifyForegroundServiceWarning(context: Context) {
        val notificationManager =
            context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                WARNING_CHANNEL_ID,
                "Security Warnings",
                NotificationManager.IMPORTANCE_HIGH
            ).apply {
                description = "Security policy alerts for Naira-OS Remote"
            }
            notificationManager.createNotificationChannel(channel)
        }

        val warningNotification = NotificationCompat.Builder(context, WARNING_CHANNEL_ID)
            .setContentTitle("WARNING: Device Admin Deactivated")
            .setContentText("Device Administrator privileges were removed. Remote security enforcement is limited.")
            .setSmallIcon(android.R.drawable.stat_sys_warning)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()

        notificationManager.notify(2001, warningNotification)
    }
}
