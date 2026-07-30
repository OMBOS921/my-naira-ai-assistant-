package com.naira.remote.services

import android.util.Log
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import com.naira.remote.bridge.RemoteBridgeClient
import com.naira.remote.security.CryptoVault
import com.naira.remote.security.HmacVerifier
import kotlin.math.abs

/**
 * NairaFCMService handles high-priority Firebase Cloud Messaging pings
 * from the Naira-OS PC backend:
 * 1. Wake pings: {"wake": true, "session_id": "..."} or {"type": "wake", "session_id": "..."}
 * 2. URL updates: {"type": "url_update", "new_url": "wss://...", "hmac": "...", "timestamp": "..."}
 */
class NairaFCMService : FirebaseMessagingService() {

    companion object {
        private const val TAG = "NairaFCMService"
    }

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        Log.i(TAG, "New FCM Registration Token: $token")
        // Store FCM Token in CryptoVault / SharedPreferences if needed for backend registration
    }

    override fun onMessageReceived(remoteMessage: RemoteMessage) {
        super.onMessageReceived(remoteMessage)

        Log.d(TAG, "FCM Message received from: ${remoteMessage.from}")

        // Initialize CryptoVault context if needed
        CryptoVault.init(applicationContext)

        if (remoteMessage.data.isNotEmpty()) {
            val dataMap = remoteMessage.data
            val type = dataMap["type"] ?: ""
            val wakeString = dataMap["wake"]
            val isWake = wakeString?.toBoolean() ?: false

            when {
                type == "url_update" || dataMap.containsKey("new_url") -> {
                    handleUrlUpdatePayload(dataMap)
                }
                type == "wake" || isWake -> {
                    val sessionId = dataMap["session_id"] ?: ""
                    handleWakePing(sessionId)
                }
                else -> {
                    Log.w(TAG, "Unrecognized FCM payload data: $dataMap")
                }
            }
        }
    }

    /**
     * Handles URL-Update FCM payload for auto-healing dynamic Ngrok tunnel URLs.
     * Expected payload structure:
     * {"type": "url_update", "new_url": "wss://xxxx.ngrok.io/ws/remote", "hmac": "...", "timestamp": "..."}
     */
    private fun handleUrlUpdatePayload(dataMap: Map<String, String>) {
        val newUrl = dataMap["new_url"] ?: ""
        val hmac = dataMap["hmac"] ?: ""
        val timestampStr = dataMap["timestamp"] ?: ""
        val timestampSec = timestampStr.toLongOrNull() ?: 0L

        if (newUrl.isBlank() || hmac.isBlank() || timestampSec == 0L) {
            Log.w(TAG, "URL_UPDATE_REJECTED: Missing required fields in URL-update payload (new_url, hmac, or timestamp).")
            return
        }

        val masterKey = CryptoVault.getMasterKey()
        if (masterKey.isNullOrBlank()) {
            Log.w(TAG, "URL_UPDATE_REJECTED: Device not paired. Master Key unavailable.")
            return
        }

        // 1. Validate timestamp within ±45s window
        val currentTimestampSec = System.currentTimeMillis() / 1000L
        val timeDelta = abs(currentTimestampSec - timestampSec)
        if (timeDelta > 45L) {
            Log.w(TAG, "URL_UPDATE_REJECTED: Timestamp is outside ±45s window (delta=${timeDelta}s, remote=$timestampSec, local=$currentTimestampSec).")
            return
        }

        // 2. Validate HMAC signature on new_url + timestamp using Master Key
        val payloadToVerify = "$newUrl$timestampStr"
        val isValidHmac = HmacVerifier.verifyHmac(payloadToVerify, hmac, masterKey)

        if (!isValidHmac) {
            Log.w(TAG, "URL_UPDATE_REJECTED: Invalid HMAC signature for new_url update.")
            return
        }

        // 3. Overwrite stored URL in EncryptedSharedPreferences
        Log.i(TAG, "FCM URL-Update verified successfully. Overwriting stored Ngrok tunnel URL to: $newUrl")
        CryptoVault.updateTunnelUrl(newUrl)

        // 4. Trigger RemoteBridgeClient reconnect with the new URL
        try {
            RemoteBridgeClient.reconnect(newUrl)
        } catch (e: Exception) {
            Log.e(TAG, "Error reconnecting WebSocket bridge with updated URL: ${e.localizedMessage}", e)
        }
    }

    /**
     * Triggers secure WebSocket bridge connection upon receiving FCM wake ping.
     */
    private fun handleWakePing(sessionId: String) {
        val serverUrl = CryptoVault.getPairedServerUrl()
        if (serverUrl.isBlank()) {
            Log.w(TAG, "Wake ping received, but device is not paired with a server URL.")
            return
        }

        Log.i(TAG, "High-priority wake ping received! Connecting WebSocket bridge to $serverUrl")
        try {
            RemoteBridgeClient.connect(serverUrl)
        } catch (e: Exception) {
            Log.e(TAG, "Error initiating WebSocket bridge from FCM wake: ${e.localizedMessage}", e)
        }
    }
}
