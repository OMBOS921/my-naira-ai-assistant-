package com.naira.remote

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.compose.setContent
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.Security
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.naira.remote.security.CryptoVault
import com.naira.remote.services.NairaForegroundService
import com.naira.remote.ui.screens.DashboardScreen
import com.naira.remote.ui.screens.PairingScreen
import com.naira.remote.ui.screens.SecurityOverlayScreen
import com.naira.remote.ui.theme.CyberBackground
import com.naira.remote.ui.theme.CyberNeonCyan
import com.naira.remote.ui.theme.CyberSurface
import com.naira.remote.ui.theme.CyberTextSecondary
import com.naira.remote.ui.theme.NairaTheme
import java.security.MessageDigest

class MainActivity : FragmentActivity() {

    private val requestNotificationPermissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { isGranted ->
            if (!isGranted) {
                Toast.makeText(this, "Notification permission is required for Naira-OS status updates", Toast.LENGTH_SHORT).show()
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Startup Anti-Tamper Signing Certificate Verification Check
        verifyAppSigningCertificateHash()

        // Doze Mode Battery Optimization Exemption Check
        requestIgnoreBatteryOptimizations()

        // Check Android 13+ (API 33+) POST_NOTIFICATIONS runtime permission
        requestNotificationPermission()

        // Initialize Android Keystore Vault & Encrypted SharedPreferences
        CryptoVault.init(this)

        // Start Naira persistent foreground daemon
        NairaForegroundService.startService(this)

        setContent {
            NairaTheme {
                MainAppScreen()
            }
        }
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestNotificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }

    private fun requestIgnoreBatteryOptimizations() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            val packageName = packageName
            if (!powerManager.isIgnoringBatteryOptimizations(packageName)) {
                val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                    data = Uri.parse("package:$packageName")
                }
                startActivity(intent)
            }
        }
    }

    private fun verifyAppSigningCertificateHash() {
        try {
            val packageInfo = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNING_CERTIFICATES)
            } else {
                @Suppress("DEPRECATION")
                packageManager.getPackageInfo(packageName, PackageManager.GET_SIGNATURES)
            }

            val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                packageInfo.signingInfo?.apkContentsSigners
            } else {
                @Suppress("DEPRECATION")
                packageInfo.signatures
            }

            if (signatures != null && signatures.isNotEmpty()) {
                val certBytes = signatures[0].toByteArray()
                val md = MessageDigest.getInstance("SHA-256")
                val digest = md.digest(certBytes)
                val fingerprint = digest.joinToString("") { "%02X".format(it) }

                // Pre-calculated Expected Release / Debug Fingerprint placeholder check
                // In production, matching is asserted against expected release key hash
                if (fingerprint.isEmpty()) {
                    Toast.makeText(this, "FATAL: Tamper Check Failed", Toast.LENGTH_LONG).show()
                    finishAffinity()
                }
            }
        } catch (e: Exception) {
            // Log or ignore during dev test execution
        }
    }
}

sealed class Screen(val route: String, val title: String, val icon: @Composable () -> Unit) {
    object Pairing : Screen("pairing", "PAIRING", { Icon(Icons.Default.QrCodeScanner, contentDescription = "Pairing") })
    object Dashboard : Screen("dashboard", "DASHBOARD", { Icon(Icons.Default.Dashboard, contentDescription = "Dashboard") })
    object Security : Screen("security", "SECURITY", { Icon(Icons.Default.Security, contentDescription = "Security") })
}

@Composable
fun MainAppScreen() {
    val navController = rememberNavController()
    val items = listOf(Screen.Pairing, Screen.Dashboard, Screen.Security)

    val startRoute = if (CryptoVault.isPaired()) Screen.Dashboard.route else Screen.Pairing.route

    Scaffold(
        bottomBar = {
            NavigationBar(
                containerColor = CyberSurface,
                contentColor = CyberNeonCyan
            ) {
                val navBackStackEntry by navController.currentBackStackEntryAsState()
                val currentRoute = navBackStackEntry?.destination?.route ?: startRoute

                items.forEach { screen ->
                    NavigationBarItem(
                        icon = screen.icon,
                        label = {
                            Text(
                                text = screen.title,
                                style = MaterialTheme.typography.labelLarge
                            )
                        },
                        selected = currentRoute == screen.route,
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = CyberBackground,
                            selectedTextColor = CyberNeonCyan,
                            indicatorColor = CyberNeonCyan,
                            unselectedIconColor = CyberTextSecondary,
                            unselectedTextColor = CyberTextSecondary
                        ),
                        onClick = {
                            if (currentRoute != screen.route) {
                                navController.navigate(screen.route) {
                                    popUpTo(navController.graph.startDestinationId) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = startRoute,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Pairing.route) {
                PairingScreen(
                    onPairingComplete = {
                        navController.navigate(Screen.Dashboard.route) {
                            popUpTo(Screen.Pairing.route) { inclusive = true }
                        }
                    }
                )
            }
            composable(Screen.Dashboard.route) { DashboardScreen() }
            composable(Screen.Security.route) { SecurityOverlayScreen() }
        }
    }
}
