package com.naira.remote.security

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import com.naira.remote.services.NairaDeviceAdminReceiver
import com.scottyab.rootbeer.RootBeer
import java.io.File

/**
 * SecurityGuard performs device integrity checks, RootBeer root detection,
 * and tracks Device Admin policy state.
 */
object SecurityGuard {

    data class SecurityStatus(
        val isRooted: Boolean,
        val isDeviceAdminActive: Boolean,
        val isPaired: Boolean,
        val details: String
    )

    /**
     * Checks if the device is rooted using RootBeer and fallback su binary checks.
     */
    fun isDeviceRooted(context: Context): Boolean {
        val rootBeer = RootBeer(context)
        val rootBeerDetected = rootBeer.isRooted

        // Supplementary binary check for custom ROMs / Magisk edge cases
        val suPaths = arrayOf(
            "/system/app/Superuser.apk",
            "/sbin/su",
            "/system/bin/su",
            "/system/xbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/system/sd/xbin/su",
            "/system/bin/failsafe/su",
            "/data/local/su"
        )
        val suBinaryDetected = suPaths.any { File(it).exists() }

        return rootBeerDetected || suBinaryDetected
    }

    /**
     * Checks whether NairaDeviceAdminReceiver is activated as a Device Administrator.
     */
    fun isDeviceAdminActive(context: Context): Boolean {
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as? DevicePolicyManager
        val adminComponent = ComponentName(context, NairaDeviceAdminReceiver::class.java)
        return dpm?.isAdminActive(adminComponent) == true
    }

    /**
     * Evaluates full security status of the Naira remote endpoint.
     */
    fun evaluateSecurity(context: Context): SecurityStatus {
        CryptoVault.init(context)
        val rooted = isDeviceRooted(context)
        val adminActive = isDeviceAdminActive(context)
        val paired = CryptoVault.isPaired()

        val details = when {
            rooted -> "CRITICAL_ALERT // Device root detected. Access restricted."
            !paired -> "STATUS // Endpoint unpaired. Awaiting QR authentication."
            !adminActive -> "WARNING // Device Admin privileges inactive."
            else -> "SECURE // All security policies active & verified."
        }

        return SecurityStatus(
            isRooted = rooted,
            isDeviceAdminActive = adminActive,
            isPaired = paired,
            details = details
        )
    }
}
