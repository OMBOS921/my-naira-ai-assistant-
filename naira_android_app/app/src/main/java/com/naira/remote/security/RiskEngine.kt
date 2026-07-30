package com.naira.remote.security

import android.content.Context
import android.util.Log
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import com.naira.remote.bridge.RemoteBridgeClient
import com.naira.remote.services.CommandExecutor
import org.json.JSONObject

/**
 * RiskEngine parses incoming WebSocket JSON command payloads, verifies HMAC signatures & nonces,
 * evaluates risk scores, and triggers biometric authentication when risk_score >= 80 or requires_biometric is true.
 */
class RiskEngine(
    private val context: Context,
    private val commandExecutor: CommandExecutor
) {

    companion object {
        private const val TAG = "RiskEngine"
        private const val HIGH_RISK_THRESHOLD = 80
        private const val CRITICAL_WIPE_RISK = 100
    }

    /**
     * Data class holding evaluation output for telemetry / UI log display.
     */
    data class EvaluationResult(
        val commandId: String,
        val actionType: String,
        val riskScore: Int,
        val isValidHmac: Boolean,
        val requiresBiometric: Boolean,
        val status: String,
        val message: String
    )

    /**
     * Evaluates incoming raw payload string.
     * Validates HMAC signature, checks replay attack nonce, evaluates risk, and dispatches command.
     */
    fun evaluatePayload(
        payloadStr: String,
        activity: FragmentActivity? = null,
        onResult: ((EvaluationResult) -> Unit)? = null
    ) {
        try {
            val json = JSONObject(payloadStr)

            val actionType = json.optString("action_type", json.optString("action", "UNKNOWN"))
            val riskScore = json.optInt("risk_score", 0)
            val requiresBiometric = json.optBoolean("requires_biometric", false)
            val signature = json.optString("signature", "")
            val nonce = json.optString("nonce", "")
            val timestamp = json.optLong("timestamp", 0L)
            val commandId = json.optString("command_id", System.currentTimeMillis().toString())

            val secretKey = CryptoVault.getHmacSecretKey()

            // 1. Verify HMAC signature & nonce replay window
            val payloadToVerify = "$actionType:$nonce:$timestamp"
            val isValidHmac = HmacVerifier.verifyHmac(payloadToVerify, signature, secretKey) &&
                    HmacVerifier.validateNonceAndTimestamp(nonce, timestamp)

            if (!isValidHmac) {
                val result = EvaluationResult(
                    commandId = commandId,
                    actionType = actionType,
                    riskScore = riskScore,
                    isValidHmac = false,
                    requiresBiometric = requiresBiometric,
                    status = "HMAC_REJECTED",
                    message = "Invalid HMAC signature or replayed nonce."
                )
                Log.w(TAG, "Command $commandId rejected: Invalid HMAC or Nonce.")
                sendRejectResponse(commandId, "HMAC_REJECTED", "Signature validation failed.")
                onResult?.invoke(result)
                return
            }

            // 2. Risk evaluation logic
            if (riskScore >= HIGH_RISK_THRESHOLD || requiresBiometric) {
                Log.i(TAG, "High-risk command ($riskScore) detected! Triggering Biometric Prompt...")
                
                if (activity != null) {
                    promptBiometricAuthentication(
                        activity = activity,
                        commandId = commandId,
                        onSuccess = {
                            val result = EvaluationResult(
                                commandId = commandId,
                                actionType = actionType,
                                riskScore = riskScore,
                                isValidHmac = true,
                                requiresBiometric = true,
                                status = "BIOMETRIC_PASSED",
                                message = "Biometric authentication successful."
                            )
                            onResult?.invoke(result)
                            commandExecutor.executeCommand(json, actionType, riskScore)
                        },
                        onFailure = { errorReason ->
                            val result = EvaluationResult(
                                commandId = commandId,
                                actionType = actionType,
                                riskScore = riskScore,
                                isValidHmac = true,
                                requiresBiometric = true,
                                status = "BIOMETRIC_REJECTED",
                                message = "Biometric prompt rejected: $errorReason"
                            )
                            sendRejectResponse(commandId, "BIOMETRIC_REJECTED", errorReason)
                            onResult?.invoke(result)
                        }
                    )
                } else {
                    // Fallback when UI activity context is absent for background service execution
                    val canAuth = canAuthenticateBiometrics(context)
                    if (!canAuth) {
                        Log.w(TAG, "Biometric requested but device has no biometrics/PIN configured.")
                    }
                    // Reject high-risk command without active UI prompt context
                    val result = EvaluationResult(
                        commandId = commandId,
                        actionType = actionType,
                        riskScore = riskScore,
                        isValidHmac = true,
                        requiresBiometric = true,
                        status = "BIOMETRIC_REJECTED",
                        message = "Biometric required but no UI context active."
                    )
                    sendRejectResponse(commandId, "BIOMETRIC_REJECTED", "No UI context available for prompt.")
                    onResult?.invoke(result)
                }
            } else {
                // Low risk command -> Execute immediately
                val result = EvaluationResult(
                    commandId = commandId,
                    actionType = actionType,
                    riskScore = riskScore,
                    isValidHmac = true,
                    requiresBiometric = false,
                    status = "EXECUTED",
                    message = "Command passed risk evaluation."
                )
                onResult?.invoke(result)
                commandExecutor.executeCommand(json, actionType, riskScore)
            }

        } catch (e: Exception) {
            Log.e(TAG, "Error evaluating risk payload: ${e.localizedMessage}", e)
            sendRejectResponse("UNKNOWN", "MALFORMED_JSON", "Failed to parse payload JSON.")
        }
    }

    private fun canAuthenticateBiometrics(context: Context): Boolean {
        val biometricManager = BiometricManager.from(context)
        val authenticators = BiometricManager.Authenticators.BIOMETRIC_STRONG or
                BiometricManager.Authenticators.DEVICE_CREDENTIAL
        return biometricManager.canAuthenticate(authenticators) == BiometricManager.BIOMETRIC_SUCCESS
    }

    private fun promptBiometricAuthentication(
        activity: FragmentActivity,
        commandId: String,
        onSuccess: () -> Unit,
        onFailure: (String) -> Unit
    ) {
        val executor = ContextCompat.getMainExecutor(activity)
        
        val promptInfo = BiometricPrompt.PromptInfo.Builder()
            .setTitle("NAIRA-OS SECURITY OVERRIDE")
            .setSubtitle("High-risk remote command execution requested")
            .setDescription("Authenticate using Biometrics or Device PIN/Pattern to authorize.")
            .setAllowedAuthenticators(
                BiometricManager.Authenticators.BIOMETRIC_STRONG or
                        BiometricManager.Authenticators.DEVICE_CREDENTIAL
            )
            .build()

        val biometricPrompt = BiometricPrompt(activity, executor, object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                super.onAuthenticationSucceeded(result)
                Log.i(TAG, "Biometric authentication SUCCEEDED for command $commandId")
                onSuccess()
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                super.onAuthenticationError(errorCode, errString)
                Log.w(TAG, "Biometric authentication ERROR ($errorCode): $errString")
                onFailure("Authentication Error: $errString")
            }

            override fun onAuthenticationFailed() {
                super.onAuthenticationFailed()
                Log.w(TAG, "Biometric authentication FAILED (mismatch).")
                onFailure("Biometric mismatch.")
            }
        })

        biometricPrompt.authenticate(promptInfo)
    }

    private fun sendRejectResponse(commandId: String, status: String, reason: String) {
        val response = JSONObject().apply {
            put("type", "COMMAND_RESPONSE")
            put("command_id", commandId)
            put("status", status)
            put("message", reason)
            put("timestamp", System.currentTimeMillis() / 1000L)
        }
        RemoteBridgeClient.sendMessage(response.toString())
    }
}
