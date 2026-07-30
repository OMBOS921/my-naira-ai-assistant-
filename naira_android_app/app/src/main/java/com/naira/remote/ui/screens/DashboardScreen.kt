package com.naira.remote.ui.screens

import android.content.Context
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp

import androidx.fragment.app.FragmentActivity
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel

import com.naira.remote.bridge.BridgeState
import com.naira.remote.bridge.CommandLogEntry
import com.naira.remote.bridge.NairaRepository
import com.naira.remote.bridge.RemoteBridgeClient
import com.naira.remote.security.CryptoVault
import com.naira.remote.security.RiskEngine
import com.naira.remote.services.CommandExecutor
import com.naira.remote.ui.theme.*
import com.naira.remote.ui.viewmodel.DashboardViewModel
import kotlinx.coroutines.flow.collectLatest

@Composable
fun DashboardScreen(
    viewModel: DashboardViewModel = viewModel()
) {
    val context = LocalContext.current
    val activity = context as? FragmentActivity

    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val bridgeState = uiState.connectionState
    val commandLogs = uiState.commandLogs

    val commandExecutor = remember { CommandExecutor(context) }
    val riskEngine = remember { RiskEngine(context, commandExecutor) }

    val listState = rememberLazyListState()

    // Listen to incoming WebSocket messages and feed into RiskEngine & NairaRepository
    LaunchedEffect(Unit) {
        RemoteBridgeClient.incomingMessages.collectLatest { rawPayload ->
            riskEngine.evaluatePayload(
                payloadStr = rawPayload,
                activity = activity,
                onResult = { result ->
                    NairaRepository.appendCommandLog(
                        action = result.actionType,
                        status = result.status,
                        riskScore = result.riskScore,
                        message = result.message
                    )
                }
            )
        }
    }

    // Auto-scroll log console when new entries arrive
    LaunchedEffect(commandLogs.size) {
        if (commandLogs.isNotEmpty()) {
            listState.animateScrollToItem(commandLogs.size - 1)
        }
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(20.dp)
        ) {
            // Screen Header
            Text(
                text = "SYS // TELEMETRY & COMMAND HUD",
                style = MaterialTheme.typography.headlineSmall,
                color = CyberNeonCyan
            )

            Text(
                text = "REALTIME WEBSOCKET BRIDGE & RISK ENGINE",
                style = MaterialTheme.typography.labelMedium,
                color = CyberTextSecondary
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Glowing Status Orbit Canvas Component (Wired to connectionState)
            GlowingStatusOrbitCard(bridgeState = bridgeState)

            Spacer(modifier = Modifier.height(20.dp))

            // Live Action Stream Header
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "LIVE ACTION STREAM CONSOLE",
                    style = MaterialTheme.typography.labelLarge,
                    color = CyberNeonCyan
                )

                Text(
                    text = "${commandLogs.size} EVENTS",
                    style = MaterialTheme.typography.labelSmall,
                    color = CyberTextMuted
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            // Console Container with LazyColumn auto-scroll (Wired to commandLogs)
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f)
                    .clip(RoundedCornerShape(12.dp))
                    .background(CyberSurface)
                    .border(1.dp, CyberBorder, RoundedCornerShape(12.dp))
                    .padding(12.dp)
            ) {
                if (commandLogs.isEmpty()) {
                    Column(
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.Center,
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "[ AWAITING SIGNED PAYLOADS ]",
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyberTextMuted,
                            fontFamily = FontFamily.Monospace
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "No action frames received via WebSocket yet.",
                            style = MaterialTheme.typography.labelSmall,
                            color = CyberTextSecondary
                        )
                    }
                } else {
                    LazyColumn(
                        state = listState,
                        modifier = Modifier.fillMaxSize(),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        items(commandLogs) { entry ->
                            ConsoleLogItem(entry = entry)
                        }
                    }
                }
            }
        }
    }
}

/**
 * Animated "Glowing Status Orbit" Canvas component.
 */
@Composable
fun GlowingStatusOrbitCard(bridgeState: BridgeState) {
    val infiniteTransition = rememberInfiniteTransition(label = "OrbitPulse")
    val pulseScale by infiniteTransition.animateFloat(
        initialValue = 0.85f,
        targetValue = 1.15f,
        animationSpec = infiniteRepeatable(
            animation = tween(1500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "PulseScale"
    )

    val rotationAngle by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(6000, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "Rotation"
    )

    val (stateColor, stateLabel) = when (bridgeState) {
        BridgeState.CONNECTED -> Pair(CyberNeonCyan, "CONNECTED (WSS ENCRYPTED)")
        BridgeState.CONNECTING -> Pair(CyberWarningYellow, "CONNECTING TO BRIDGE...")
        BridgeState.RECONNECTING -> Pair(CyberAlertRed, "RECONNECTING (EXP BACKOFF)")
        BridgeState.DISCONNECTED -> Pair(CyberTextMuted, "DISCONNECTED (STANDBY)")
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, stateColor.copy(alpha = 0.5f), RoundedCornerShape(16.dp)),
        colors = CardDefaults.cardColors(containerColor = CyberSurface)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "BRIDGE CONNECTION ORBIT",
                    style = MaterialTheme.typography.labelMedium,
                    color = CyberTextSecondary
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = stateLabel,
                    style = MaterialTheme.typography.titleMedium,
                    color = stateColor,
                    fontFamily = FontFamily.Monospace
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Target: ${CryptoVault.getPairedServerUrl().ifBlank { "WSS Tunnel standby" }}",
                    style = MaterialTheme.typography.bodySmall,
                    color = CyberTextMuted
                )
            }

            // Animated Jetpack Compose Canvas Orbit
            Canvas(modifier = Modifier.size(64.dp)) {
                val center = Offset(size.width / 2, size.height / 2)
                val radius = (size.minDimension / 2) * 0.7f

                // Outer pulsing ring
                drawCircle(
                    color = stateColor.copy(alpha = 0.25f),
                    radius = radius * pulseScale,
                    center = center,
                    style = Stroke(width = 3.dp.toPx())
                )

                // Main orbit ring
                drawCircle(
                    color = stateColor,
                    radius = radius,
                    center = center,
                    style = Stroke(width = 2.dp.toPx())
                )

                // Central glowing node
                drawCircle(
                    color = stateColor,
                    radius = 8.dp.toPx(),
                    center = center
                )

                // Rotating satellite particle
                val satelliteAngleRad = Math.toRadians(rotationAngle.toDouble())
                val satX = center.x + radius * Math.cos(satelliteAngleRad).toFloat()
                val satY = center.y + radius * Math.sin(satelliteAngleRad).toFloat()

                drawCircle(
                    color = Color.White,
                    radius = 4.dp.toPx(),
                    center = Offset(satX, satY)
                )
            }
        }
    }
}

/**
 * Individual log entry view inside the Live Action Stream Console.
 */
@Composable
fun ConsoleLogItem(entry: CommandLogEntry) {
    val statusColor = when (entry.status.uppercase()) {
        "EXECUTED", "BIOMETRIC_PASSED", "CONNECTED", "SUCCESS" -> CyberNeonCyan
        "BIOMETRIC_REJECTED", "HMAC_REJECTED", "ERROR", "REJECTED" -> CyberAlertRed
        else -> CyberWarningYellow
    }

    Card(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, statusColor.copy(alpha = 0.3f), RoundedCornerShape(8.dp)),
        colors = CardDefaults.cardColors(containerColor = CyberBackground.copy(alpha = 0.6f))
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "ACTION: ${entry.action.uppercase()}",
                    style = MaterialTheme.typography.labelMedium,
                    color = CyberTextPrimary,
                    fontFamily = FontFamily.Monospace
                )

                Text(
                    text = "[${entry.timestamp}] ${entry.status}",
                    style = MaterialTheme.typography.labelSmall,
                    color = statusColor,
                    fontFamily = FontFamily.Monospace
                )
            }

            Spacer(modifier = Modifier.height(4.dp))

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "RISK SCORE: ${entry.riskScore}",
                    style = MaterialTheme.typography.bodySmall,
                    color = if (entry.riskScore >= 80) CyberAlertRed else CyberNeonCyan
                )

                Text(
                    text = "STATUS: ${entry.status}",
                    style = MaterialTheme.typography.bodySmall,
                    color = statusColor
                )
            }

            if (entry.message.isNotBlank()) {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = entry.message,
                    style = MaterialTheme.typography.bodySmall,
                    color = CyberTextMuted
                )
            }
        }
    }
}
