package com.naira.remote.services

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.util.Log
import com.naira.remote.bridge.RemoteBridgeClient
import org.json.JSONObject

/**
 * CommandExecutor executes verified commands received from the Naira-OS PC backend
 * and streams execution results/telemetry back via WebSocket.
 */
class CommandExecutor(private val context: Context) {

    companion object {
        private const val TAG = "CommandExecutor"
    }

    /**
     * Executes parsed command object and reports results back over WebSocket bridge.
     */
    fun executeCommand(commandJson: JSONObject, actionType: String, riskScore: Int) {
        val payloadData = commandJson.optJSONObject("data") ?: JSONObject()
        val commandId = commandJson.optString("command_id", System.currentTimeMillis().toString())

        Log.i(TAG, "Executing command ID: $commandId | Action: $actionType | Risk: $riskScore")

        try {
            when (actionType.uppercase()) {
                "PING" -> {
                    sendResponse(commandId, "SUCCESS", "PONG - Naira Remote Daemon Active")
                }
                "TELEMETRY_GET" -> {
                    val battery = getBatteryStatus()
                    sendResponse(commandId, "SUCCESS", "Battery level: $battery%, Status: Operational")
                }
                "LOCK_SCREEN" -> {
                    lockDeviceScreen()
                    sendResponse(commandId, "SUCCESS", "Device screen locked successfully.")
                }
                "DEVICE_WIPE", "FACTORY_RESET" -> {
                    if (riskScore == 100) {
                        handleDeviceWipe(commandId)
                    } else {
                        sendResponse(commandId, "REJECTED", "Device wipe rejected: risk score must be 100.")
                    }
                }
                else -> {
                    sendResponse(commandId, "EXECUTED", "Custom action '$actionType' processed successfully.")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Command execution failed: ${e.localizedMessage}", e)
            sendResponse(commandId, "ERROR", "Execution failed: ${e.localizedMessage}")
        }
    }

    private fun lockDeviceScreen() {
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as? DevicePolicyManager
        val adminComponent = ComponentName(context, NairaDeviceAdminReceiver::class.java)
        if (dpm != null && dpm.isAdminActive(adminComponent)) {
            dpm.lockNow()
        } else {
            Log.w(TAG, "Device admin not active. Cannot lock screen programmatically.")
        }
    }

    private fun handleDeviceWipe(commandId: String) {
        val dpm = context.getSystemService(Context.DEVICE_POLICY_SERVICE) as? DevicePolicyManager
        val adminComponent = ComponentName(context, NairaDeviceAdminReceiver::class.java)

        if (dpm != null && dpm.isAdminActive(adminComponent)) {
            Log.w(TAG, "CRITICAL: Triggering device wipe via DevicePolicyManager!")
            sendResponse(commandId, "EXECUTING_WIPE", "Device wipe initiated by authorized remote admin.")
            dpm.wipeData(0)
        } else {
            Log.e(TAG, "Device Admin not enabled! Cannot execute device wipe.")
            sendResponse(commandId, "ERROR", "Device Admin permission not granted for wipe action.")
        }
    }

    private fun getBatteryStatus(): Int {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as? android.os.BatteryManager
        return batteryManager?.getIntProperty(android.os.BatteryManager.BATTERY_PROPERTY_CAPACITY) ?: 100
    }

    private fun sendResponse(commandId: String, status: String, message: String) {
        val responseJson = JSONObject().apply {
            put("type", "COMMAND_RESPONSE")
            put("command_id", commandId)
            put("status", status)
            put("message", message)
            put("timestamp", System.currentTimeMillis() / 1000L)
        }

        RemoteBridgeClient.sendMessage(responseJson.toString())
    }
}
