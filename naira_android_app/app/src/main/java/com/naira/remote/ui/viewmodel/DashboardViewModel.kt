package com.naira.remote.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.naira.remote.bridge.BridgeState
import com.naira.remote.bridge.CommandLogEntry
import com.naira.remote.bridge.NairaRepository
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn

/**
 * Combined UI State data class for the DashboardScreen HUD.
 */
data class DashboardUiState(
    val connectionState: BridgeState = BridgeState.DISCONNECTED,
    val commandLogs: List<CommandLogEntry> = emptyList()
)

/**
 * ViewModel serving telemetry and command stream data to DashboardScreen.
 */
class DashboardViewModel : ViewModel() {

    /**
     * Combined StateFlow exposing connection state and command logs from NairaRepository.
     */
    val uiState: StateFlow<DashboardUiState> = combine(
        NairaRepository.connectionState,
        NairaRepository.commandLog
    ) { connState, logs ->
        DashboardUiState(
            connectionState = connState,
            commandLogs = logs
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5000),
        initialValue = DashboardUiState()
    )

    fun clearLogs() {
        NairaRepository.clearLog()
    }
}
