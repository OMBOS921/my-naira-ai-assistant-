package com.naira.remote.bridge

import android.util.Log
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import kotlin.math.min
import kotlin.math.pow

enum class BridgeState {
    DISCONNECTED,
    CONNECTING,
    CONNECTED,
    RECONNECTING
}

/**
 * Secure OkHttp-based WebSocket Client for Naira-OS Remote Bridge.
 * Enforces wss:// TLS security, certificate pinning for Ngrok/tunnel endpoints,
 * exponential backoff reconnection, and connection lifecycle state management.
 * Synchronizes connection state changes and command execution events to NairaRepository.
 */
object RemoteBridgeClient {

    private const val TAG = "RemoteBridgeClient"
    private const val INITIAL_BACKOFF_MS = 1000L
    private const val MAX_BACKOFF_MS = 60000L
    private const val BACKOFF_MULTIPLIER = 2.0

    private val _connectionState = MutableStateFlow(BridgeState.DISCONNECTED)
    val connectionState: StateFlow<BridgeState> = _connectionState.asStateFlow()

    private val _incomingMessages = MutableSharedFlow<String>(extraBufferCapacity = 64)
    val incomingMessages: SharedFlow<String> = _incomingMessages.asSharedFlow()

    private var client: OkHttpClient? = null
    private var webSocket: WebSocket? = null
    private var currentUrl: String = ""
    private var isExplicitlyClosed = false
    private var reconnectAttempt = 0
    private var scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var reconnectJob: Job? = null

    private fun updateState(state: BridgeState) {
        _connectionState.value = state
        NairaRepository.updateConnectionState(state)
    }

    /**
     * Initializes OkHttpClient with Certificate Pinning for secure tunnel connections.
     */
    private fun buildOkHttpClient(hostname: String): OkHttpClient {
        val pinnerBuilder = CertificatePinner.Builder()

        // Certificate pinning for ngrok domains if ngrok is targeted
        if (hostname.contains("ngrok")) {
            pinnerBuilder.add("*.ngrok-free.app", "sha256/47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=")
            pinnerBuilder.add("*.ngrok.io", "sha256/47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU=")
        }

        return OkHttpClient.Builder()
            .certificatePinner(pinnerBuilder.build())
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.MILLISECONDS) // Keep-alive WebSocket stream
            .writeTimeout(10, TimeUnit.SECONDS)
            .pingInterval(15, TimeUnit.SECONDS)
            .build()
    }

    /**
     * Establishes a secure wss:// WebSocket connection.
     * Throws IllegalArgumentException if ws:// is attempted.
     */
    @Synchronized
    fun connect(wssUrl: String) {
        if (wssUrl.isBlank()) return

        // Reject clear-text ws://
        if (wssUrl.startsWith("ws://", ignoreCase = true)) {
            updateState(BridgeState.DISCONNECTED)
            val errorMsg = "SECURITY ERROR: Clear-text 'ws://' rejected. Must use encrypted 'wss://'."
            Log.e(TAG, errorMsg)
            throw IllegalArgumentException(errorMsg)
        }

        if (!wssUrl.startsWith("wss://", ignoreCase = true)) {
            val errorMsg = "INVALID PROTOCOL: Connection URL must start with 'wss://'."
            Log.e(TAG, errorMsg)
            throw IllegalArgumentException(errorMsg)
        }

        currentUrl = wssUrl
        isExplicitlyClosed = false
        reconnectJob?.cancel()

        val uri = java.net.URI(wssUrl)
        val host = uri.host ?: "localhost"

        client = buildOkHttpClient(host)
        initiateWebSocketConnection()
    }

    private fun initiateWebSocketConnection() {
        if (isExplicitlyClosed) return

        if (_connectionState.value != BridgeState.RECONNECTING) {
            updateState(BridgeState.CONNECTING)
        }

        val request = Request.Builder()
            .url(currentUrl)
            .addHeader("User-Agent", "Naira-OS-Android-Remote/1.0")
            .build()

        webSocket = client?.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WebSocket Connected successfully to $currentUrl")
                updateState(BridgeState.CONNECTED)
                reconnectAttempt = 0
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(TAG, "Incoming frame: $text")
                scope.launch {
                    _incomingMessages.emit(text)
                }

                try {
                    val json = JSONObject(text)
                    val action = json.optString("action_type", json.optString("action", "COMMAND_RECEIVED"))
                    val risk = json.optInt("risk_score", 0)
                    NairaRepository.appendCommandLog(
                        action = action,
                        status = "RECEIVED",
                        riskScore = risk,
                        message = "Incoming WebSocket payload frame received."
                    )
                } catch (e: Exception) {
                    NairaRepository.appendCommandLog(
                        action = "RAW_FRAME",
                        status = "RECEIVED",
                        riskScore = 0,
                        message = text.take(60)
                    )
                }
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                Log.w(TAG, "WebSocket Closing ($code): $reason")
                webSocket.close(code, reason)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WebSocket Closed ($code): $reason")
                if (!isExplicitlyClosed) {
                    scheduleReconnection()
                } else {
                    updateState(BridgeState.DISCONNECTED)
                }
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WebSocket Failure: ${t.localizedMessage}", t)
                if (!isExplicitlyClosed) {
                    scheduleReconnection()
                } else {
                    updateState(BridgeState.DISCONNECTED)
                }
            }
        })
    }

    /**
     * Schedules exponential backoff reconnection.
     */
    private fun scheduleReconnection() {
        if (isExplicitlyClosed) return

        updateState(BridgeState.RECONNECTING)
        reconnectAttempt++

        val delayMs = min(
            MAX_BACKOFF_MS,
            (INITIAL_BACKOFF_MS * BACKOFF_MULTIPLIER.pow((reconnectAttempt - 1).toDouble())).toLong()
        )

        Log.w(TAG, "Reconnecting attempt #$reconnectAttempt in ${delayMs}ms...")

        reconnectJob?.cancel()
        reconnectJob = scope.launch {
            delay(delayMs)
            if (!isExplicitlyClosed) {
                initiateWebSocketConnection()
            }
        }
    }

    /**
     * Sends text payload frame over WebSocket connection.
     */
    fun sendMessage(message: String): Boolean {
        val ws = webSocket
        return if (ws != null && _connectionState.value == BridgeState.CONNECTED) {
            ws.send(message)
        } else {
            Log.w(TAG, "Cannot send message. Client not connected.")
            false
        }
    }

    /**
     * Reconnects WebSocket bridge, optionally updating target URL.
     */
    @Synchronized
    fun reconnect(newUrl: String? = null) {
        val targetUrl = if (!newUrl.isNullOrBlank()) {
            newUrl
        } else {
            currentUrl.ifBlank { com.naira.remote.security.CryptoVault.getNgrokUrl() ?: "" }
        }

        if (targetUrl.isBlank()) {
            Log.w(TAG, "Cannot reconnect: No valid server URL available.")
            return
        }

        Log.i(TAG, "Reconnecting WebSocket bridge to: $targetUrl")
        disconnect()
        connect(targetUrl)
    }

    /**
     * Explicitly closes WebSocket connection and stops reconnecting.
     */
    @Synchronized
    fun disconnect() {
        isExplicitlyClosed = true
        reconnectJob?.cancel()
        webSocket?.close(1000, "User initiated disconnect")
        webSocket = null
        updateState(BridgeState.DISCONNECTED)
        Log.i(TAG, "WebSocket Disconnected.")
    }
}
