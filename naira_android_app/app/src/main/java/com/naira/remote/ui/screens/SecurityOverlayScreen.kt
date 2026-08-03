package com.naira.remote.ui.screens

import android.app.admin.DevicePolicyManager
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.Toast
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Fingerprint
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.naira.remote.security.CryptoVault
import com.naira.remote.security.SecurityGuard
import com.naira.remote.services.NairaDeviceAdminReceiver
import com.naira.remote.ui.theme.*

@Composable
fun SecurityOverlayScreen() {
    val context = LocalContext.current
    var securityStatus by remember { mutableStateOf<SecurityGuard.SecurityStatus?>(null) }
    var showBiometricModal by remember { mutableStateOf(false) }
    var biometricResultText by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        CryptoVault.init(context)
        securityStatus = SecurityGuard.evaluateSecurity(context)
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp)
        ) {
            Text(
                text = "SYS // SECURITY & OVERLAY",
                style = MaterialTheme.typography.headlineMedium,
                color = CyberAlertPink
            )

            Spacer(modifier = Modifier.height(8.dp))

            Text(
                text = "BIOMETRIC & DEVICE POLICY MONITOR",
                style = MaterialTheme.typography.bodyMedium,
                color = CyberTextSecondary
            )

            Spacer(modifier = Modifier.height(20.dp))

            // Interactive Trigger Card for High Risk Action Biometric Overlay
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, CyberAlertPink, RoundedCornerShape(12.dp)),
                colors = CardDefaults.cardColors(containerColor = CyberSurface)
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Shield,
                            contentDescription = "Risk Alert",
                            tint = CyberAlertPink,
                            modifier = Modifier.size(28.dp)
                        )
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = "CRITICAL HIGH-RISK AUTHORIZATION",
                                style = MaterialTheme.typography.labelLarge,
                                color = CyberAlertPink
                            )
                            Text(
                                text = "Simulate action requiring biometric overlay",
                                style = MaterialTheme.typography.bodySmall,
                                color = CyberTextSecondary
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(12.dp))
                    Button(
                        onClick = { showBiometricModal = true },
                        colors = ButtonDefaults.buttonColors(
                            containerColor = CyberAlertPink,
                            contentColor = Color.White
                        ),
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Icon(Icons.Default.Fingerprint, contentDescription = null)
                        Spacer(modifier = Modifier.width(8.dp))
                        Text("TRIGGER BIOMETRIC OVERLAY", style = MaterialTheme.typography.labelLarge, color = Color.White)
                    }

                    if (biometricResultText != null) {
                        Spacer(modifier = Modifier.height(8.dp))
                        Text(
                            text = biometricResultText!!,
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyberNeonCyan
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Root Status Card
            val isRooted = securityStatus?.isRooted == true
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        1.dp,
                        if (isRooted) CyberAlertPink else CyberNeonCyan,
                        RoundedCornerShape(12.dp)
                    ),
                colors = CardDefaults.cardColors(containerColor = CyberSurface)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "DEVICE INTEGRITY (ROOTBEER)",
                        style = MaterialTheme.typography.labelLarge,
                        color = if (isRooted) CyberAlertPink else CyberNeonCyan
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = if (isRooted) {
                            "• Root Status: ROOTED [ALERT]\n• Security State: VULNERABLE\n• Action: Pairing & Admin commands locked."
                        } else {
                            "• Root Status: CLEAN [VERIFIED]\n• Binary Integrity: PASS\n• Test-Keys Check: PASS"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = CyberTextPrimary
                    )
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Device Admin Policy Card
            val isAdminActive = securityStatus?.isDeviceAdminActive == true
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(
                        1.dp,
                        if (isAdminActive) CyberNeonCyan else CyberBorder,
                        RoundedCornerShape(12.dp)
                    ),
                colors = CardDefaults.cardColors(containerColor = CyberSurface)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "DEVICE ADMIN POLICIES",
                        style = MaterialTheme.typography.labelLarge,
                        color = CyberNeonCyan
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        text = if (isAdminActive) {
                            "• NairaDeviceAdminReceiver: ACTIVE\n• Anti-Theft Remote Lock: READY\n• Wipe Data Policy: ENFORCED"
                        } else {
                            "• NairaDeviceAdminReceiver: INACTIVE\n• Anti-Theft Lock: DISABLED"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = CyberTextPrimary
                    )

                    if (!isAdminActive) {
                        Spacer(modifier = Modifier.height(12.dp))
                        Button(
                            onClick = {
                                val intent = Intent(DevicePolicyManager.ACTION_ADD_DEVICE_ADMIN).apply {
                                    putExtra(
                                        DevicePolicyManager.EXTRA_DEVICE_ADMIN,
                                        ComponentName(context, NairaDeviceAdminReceiver::class.java)
                                    )
                                    putExtra(
                                        DevicePolicyManager.EXTRA_ADD_EXPLANATION,
                                        "Naira-OS requires Device Administrator privileges for anti-theft remote lock & security policy enforcement."
                                    )
                                }
                                context.startActivity(intent)
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = CyberNeonCyan, contentColor = CyberBackground)
                        ) {
                            Text("ACTIVATE DEVICE ADMIN", style = MaterialTheme.typography.labelLarge)
                        }
                    }
                }
            }

            Spacer(modifier = Modifier.height(16.dp))

            // Keystore Vault Status Card
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .border(1.dp, CyberBorder, RoundedCornerShape(12.dp)),
                colors = CardDefaults.cardColors(containerColor = CyberSurface)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp)
                ) {
                    Text(
                        text = "HARDWARE KEYSTORE VAULT",
                        style = MaterialTheme.typography.labelLarge,
                        color = CyberNeonCyan
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    val paired = securityStatus?.isPaired == true
                    Text(
                        text = "• Keystore Spec: AES/GCM/NoPadding (NairaMasterKeyAlias)\n" +
                                "• Storage: EncryptedSharedPreferences (AES256_SIV/GCM)\n" +
                                "• Session State: ${if (paired) "ENCRYPTED PAIRING BOUND" else "UNPAIRED"}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = CyberTextPrimary
                    )
                }
            }
        }

        // Floating Dark Biometric Modal Overlay
        if (showBiometricModal) {
            BiometricAuthorizationModal(
                actionName = "Open Banking App",
                riskScore = 85,
                onDismiss = { showBiometricModal = false },
                onBiometricSuccess = {
                    showBiometricModal = false
                    biometricResultText = "[AUTHENTICATED] Action 'Open Banking App' Approved via Biometrics"
                },
                onDenied = {
                    showBiometricModal = false
                    biometricResultText = "[DENIED] Action 'Open Banking App' Rejected by User"
                }
            )
        }
    }
}

@Composable
fun BiometricAuthorizationModal(
    actionName: String,
    riskScore: Int,
    onDismiss: () -> Unit,
    onBiometricSuccess: () -> Unit,
    onDenied: () -> Unit
) {
    val context = LocalContext.current

    Dialog(onDismissRequest = onDismiss) {
        Card(
            modifier = Modifier
                .fillMaxWidth()
                .border(2.dp, CyberAlertPink, RoundedCornerShape(20.dp)),
            colors = CardDefaults.cardColors(containerColor = CyberBackground.copy(alpha = 0.95f))
        ) {
            Column(
                modifier = Modifier
                    .padding(24.dp)
                    .fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = "CRITICAL ACTION REQUEST",
                    style = MaterialTheme.typography.headlineMedium,
                    color = CyberAlertPink
                )

                Spacer(modifier = Modifier.height(12.dp))

                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = CyberSurface)
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = "Action: $actionName",
                            style = MaterialTheme.typography.bodyLarge,
                            color = CyberTextPrimary
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Risk Score: $riskScore/100 (HIGH RISK)",
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyberAlertPink
                        )
                    }
                }

                Spacer(modifier = Modifier.height(24.dp))

                Box(
                    modifier = Modifier
                        .size(80.dp)
                        .background(CyberSurface, CircleShape)
                        .border(2.dp, CyberNeonCyan, CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = Icons.Default.Fingerprint,
                        contentDescription = "Fingerprint Sensor",
                        tint = CyberNeonCyan,
                        modifier = Modifier.size(48.dp)
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                Text(
                    text = "Biometric Verification Required",
                    style = MaterialTheme.typography.bodyMedium,
                    color = CyberTextSecondary
                )

                Spacer(modifier = Modifier.height(24.dp))

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    OutlinedButton(
                        onClick = onDenied,
                        colors = ButtonDefaults.outlinedButtonColors(contentColor = CyberAlertPink),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("DENY", style = MaterialTheme.typography.labelLarge)
                    }

                    Spacer(modifier = Modifier.width(16.dp))

                    Button(
                        onClick = {
                            if (context is FragmentActivity) {
                                triggerBiometricPrompt(
                                    activity = context,
                                    onSuccess = onBiometricSuccess,
                                    onError = { err ->
                                        Toast.makeText(context, "Biometric failed: $err", Toast.LENGTH_SHORT).show()
                                    }
                                )
                            } else {
                                // Fallback mock success if context is not FragmentActivity
                                onBiometricSuccess()
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = CyberNeonCyan, contentColor = CyberBackground),
                        modifier = Modifier.weight(1f)
                    ) {
                        Text("APPROVE", style = MaterialTheme.typography.labelLarge)
                    }
                }
            }
        }
    }
}

private fun triggerBiometricPrompt(
    activity: FragmentActivity,
    onSuccess: () -> Unit,
    onError: (String) -> Unit
) {
    val executor = ContextCompat.getMainExecutor(activity)
    val biometricPrompt = BiometricPrompt(
        activity,
        executor,
        object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                super.onAuthenticationSucceeded(result)
                onSuccess()
            }

            override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
                super.onAuthenticationError(errorCode, errString)
                onError(errString.toString())
            }

            override fun onAuthenticationFailed() {
                super.onAuthenticationFailed()
                onError("Fingerprint not recognized")
            }
        }
    )

    val promptInfo = BiometricPrompt.PromptInfo.Builder()
        .setTitle("Biometric Approval Required")
        .setSubtitle("Confirm authorization for high-risk action")
        .setNegativeButtonText("Cancel")
        .build()

    biometricPrompt.authenticate(promptInfo)
}
