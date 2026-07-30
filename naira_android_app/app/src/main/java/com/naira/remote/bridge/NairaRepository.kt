package com.naira.remote.bridge

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

typealias ConnectionState = BridgeState

/**
 * Data class representing an entry in the live action command log stream.
 */
data class CommandLogEntry(
    val timestamp: String = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date()),
    val action: String,
    val status: String,
    val riskScore: Int,
    val message: String = ""
)

/**
 * Singleton repository acting as the central state bridge between background
 * ForegroundService / RemoteBridgeClient and the Jetpack Compose Dashboard UI.
 */
object NairaRepository {

    private val _connectionState = MutableStateFlow(BridgeState.DISCONNECTED)
    val connectionState: StateFlow<BridgeState> = _connectionState.asStateFlow()

    private val _commandLog = MutableStateFlow<List<CommandLogEntry>>(emptyList())
    val commandLog: StateFlow<List<CommandLogEntry>> = _commandLog.asStateFlow()

    /**
     * Updates the active WebSocket bridge connection state.
     */
    fun updateConnectionState(state: BridgeState) {
        _connectionState.value = state
    }

    /**
     * Appends a new command log entry to the live action stream.
     */
    fun appendCommandLog(entry: CommandLogEntry) {
        _commandLog.value = _commandLog.value + entry
    }

    /**
     * Overloaded helper to construct and append a new command log entry.
     */
    fun appendCommandLog(
        action: String,
        status: String,
        riskScore: Int,
        message: String = "",
        timestamp: String = SimpleDateFormat("HH:mm:ss", Locale.getDefault()).format(Date())
    ) {
        val entry = CommandLogEntry(
            timestamp = timestamp,
            action = action,
            status = status,
            riskScore = riskScore,
            message = message
        )
        appendCommandLog(entry)
    }

    /**
     * Clears all entries from the command log stream.
     */
    fun clearLog() {
        _commandLog.value = emptyList()
    }
}
