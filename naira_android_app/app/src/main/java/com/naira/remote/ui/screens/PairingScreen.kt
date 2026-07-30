package com.naira.remote.ui.screens

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.view.ViewGroup
import android.view.WindowManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.annotation.OptIn
import androidx.camera.core.*
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import com.naira.remote.security.CryptoVault
import com.naira.remote.security.SecurityGuard
import com.naira.remote.ui.theme.*
import org.json.JSONObject
import java.util.concurrent.Executors
import kotlin.math.abs

@Composable
fun PairingScreen(onPairingComplete: (() -> Unit)? = null) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    // Initialize Cryptographic Storage
    LaunchedEffect(Unit) {
        CryptoVault.init(context)
    }

    // 1. Enforce FLAG_SECURE window protection during QR scanning
    DisposableEffect(Unit) {
        val window = (context as? Activity)?.window
        window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        onDispose {
            window?.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
        }
    }

    // State management
    var isDeviceRooted by remember { mutableStateOf(false) }
    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED
        )
    }
    var scanStatus by remember { mutableStateOf<String?>(null) }
    var isSuccess by remember { mutableStateOf(CryptoVault.isPaired()) }
    var scannedPayload by remember { mutableStateOf<String?>(null) }

    // Check device security state
    LaunchedEffect(Unit) {
        isDeviceRooted = SecurityGuard.isDeviceRooted(context)
    }

    // Permission launcher
    val cameraPermissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasCameraPermission = isGranted
    }

    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.background
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Top
        ) {
            Spacer(modifier = Modifier.height(16.dp))

            Text(
                text = "SYS // PAIRING HUD",
                style = MaterialTheme.typography.headlineMedium,
                color = CyberNeonCyan
            )

            Spacer(modifier = Modifier.height(8.dp))

            val statusText = when {
                isDeviceRooted -> "STATUS: ROOT DETECTED [BLOCKED]"
                isSuccess -> "STATUS: PAIRED & ENCRYPTED"
                else -> "STATUS: UNPAIRED // CAMERA READY"
            }
            val statusColor = when {
                isDeviceRooted -> CyberAlertPink
                isSuccess -> CyberNeonCyan
                else -> CyberTextSecondary
            }

            Text(
                text = statusText,
                style = MaterialTheme.typography.labelLarge,
                color = statusColor
            )

            Spacer(modifier = Modifier.height(24.dp))

            if (isDeviceRooted) {
                // Root Warning Screen Block
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(2.dp, CyberAlertPink, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = CyberSurface)
                ) {
                    Column(
                        modifier = Modifier.padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "[ SECURITY GUARD ALERT ]",
                            style = MaterialTheme.typography.headlineSmall,
                            color = CyberAlertPink
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "Root access detected on this device. Cryptographic key pair exchange is strictly blocked to protect Naira-OS host systems.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyberTextPrimary
                        )
                    }
                }
            } else if (isSuccess) {
                // Already Paired Card
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, CyberNeonCyan, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = CyberSurface)
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "[ SESSION ENCRYPTED ]",
                            style = MaterialTheme.typography.titleMedium,
                            color = CyberNeonCyan
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "Ngrok Endpoint:\n${CryptoVault.getNgrokUrl() ?: "Active"}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyberTextPrimary
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = {
                                CryptoVault.clearVault()
                                isSuccess = false
                                scanStatus = null
                            },
                            colors = ButtonDefaults.buttonColors(containerColor = CyberAlertPink)
                        ) {
                            Text("UNPAIR DEVICE", style = MaterialTheme.typography.labelLarge)
                        }
                    }
                }
            } else if (!hasCameraPermission) {
                // Camera Permission Request Card
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, CyberBorder, RoundedCornerShape(12.dp)),
                    colors = CardDefaults.cardColors(containerColor = CyberSurface)
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally
                    ) {
                        Text(
                            text = "[ CAMERA PERMISSION REQUIRED ]",
                            style = MaterialTheme.typography.titleMedium,
                            color = CyberNeonCyan
                        )
                        Spacer(modifier = Modifier.height(12.dp))
                        Text(
                            text = "Grant camera permission to scan host QR code with CameraX & ML Kit detector.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = CyberTextPrimary
                        )
                        Spacer(modifier = Modifier.height(16.dp))
                        Button(
                            onClick = { cameraPermissionLauncher.launch(Manifest.permission.CAMERA) },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = CyberNeonCyan,
                                contentColor = CyberBackground
                            )
                        ) {
                            Text("GRANT CAMERA ACCESS", style = MaterialTheme.typography.labelLarge)
                        }
                    }
                }
            } else {
                // CameraX Scanner View + Cyber Overlay
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(340.dp)
                        .border(2.dp, CyberNeonCyan, RoundedCornerShape(16.dp))
                ) {
                    AndroidView(
                        factory = { ctx ->
                            val previewView = PreviewView(ctx).apply {
                                layoutParams = ViewGroup.LayoutParams(
                                    ViewGroup.LayoutParams.MATCH_PARENT,
                                    ViewGroup.LayoutParams.MATCH_PARENT
                                )
                            }

                            val cameraProviderFuture = ProcessCameraProvider.getInstance(ctx)
                            cameraProviderFuture.addListener({
                                val cameraProvider = cameraProviderFuture.get()

                                val preview = Preview.Builder().build().also {
                                    it.setSurfaceProvider(previewView.surfaceProvider)
                                }

                                val options = BarcodeScannerOptions.Builder()
                                    .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
                                    .build()
                                val scanner = BarcodeScanning.getClient(options)

                                val imageAnalysis = ImageAnalysis.Builder()
                                    .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                                    .build()

                                val executor = Executors.newSingleThreadExecutor()

                                imageAnalysis.setAnalyzer(executor) { imageProxy ->
                                    @OptIn(ExperimentalGetImage::class)
                                    val mediaImage = imageProxy.image
                                    if (mediaImage != null && !isSuccess) {
                                        val image = InputImage.fromMediaImage(
                                            mediaImage,
                                            imageProxy.imageInfo.rotationDegrees
                                        )

                                        scanner.process(image)
                                            .addOnSuccessListener { barcodes ->
                                                for (barcode in barcodes) {
                                                    val rawValue = barcode.rawValue ?: continue
                                                    if (rawValue != scannedPayload) {
                                                        scannedPayload = rawValue
                                                        val result = processPairingQr(rawValue)
                                                        scanStatus = result.message
                                                        if (result.success) {
                                                            isSuccess = true
                                                            onPairingComplete?.invoke()
                                                            break
                                                        }
                                                    }
                                                }
                                            }
                                            .addOnCompleteListener {
                                                imageProxy.close()
                                            }
                                    } else {
                                        imageProxy.close()
                                    }
                                }

                                try {
                                    cameraProvider.unbindAll()
                                    cameraProvider.bindToLifecycle(
                                        lifecycleOwner,
                                        CameraSelector.DEFAULT_BACK_CAMERA,
                                        preview,
                                        imageAnalysis
                                    )
                                } catch (exc: Exception) {
                                    exc.printStackTrace()
                                }
                            }, ContextCompat.getMainExecutor(ctx))

                            previewView
                        },
                        modifier = Modifier.fillMaxSize()
                    )

                    // Cyber HUD Scan Line Indicator
                    Box(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(24.dp)
                            .border(1.dp, CyberNeonCyan.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
                    )
                }

                Spacer(modifier = Modifier.height(16.dp))

                scanStatus?.let { status ->
                    val statusStyleColor = if (isSuccess) CyberNeonCyan else CyberAlertPink
                    Text(
                        text = status,
                        style = MaterialTheme.typography.bodyMedium,
                        color = statusStyleColor
                    )
                }
            }
        }
    }
}

private data class PairingResult(val success: Boolean, val message: String)

/**
 * Validates QR pairing JSON payload and checks 60-second expiry timestamp.
 */
private fun processPairingQr(rawJson: String): PairingResult {
    return try {
        val json = JSONObject(rawJson)

        val masterKey = when {
            json.has("master_key") -> json.getString("master_key")
            json.has("masterKey") -> json.getString("masterKey")
            else -> null
        }

        val ngrokUrl = when {
            json.has("ngrok_url") -> json.getString("ngrok_url")
            json.has("ngrokUrl") -> json.getString("ngrokUrl")
            else -> null
        }

        val timestamp = when {
            json.has("timestamp") -> json.getLong("timestamp")
            else -> null
        }

        if (masterKey.isNull_or_blank() || ngrokUrl.isNull_or_blank() || timestamp == null) {
            return PairingResult(false, "INVALID QR // Missing required keys in JSON payload")
        }

        // Validate 60-second expiry timestamp
        val currentSec = System.currentTimeMillis() / 1000L
        val qrSec = if (timestamp > 10000000000L) timestamp / 1000L else timestamp
        val ageSeconds = abs(currentSec - qrSec)

        if (ageSeconds > 60) {
            return PairingResult(
                false,
                "PAIRING FAILED // QR expired ($ageSeconds s old, max allowed: 60s)"
            )
        }

        // Save into Encrypted CryptoVault
        CryptoVault.saveMasterKey(masterKey)
        CryptoVault.saveNgrokUrl(ngrokUrl)

        PairingResult(true, "PAIRING SUCCESSFUL // Host bound & key secured")
    } catch (e: Exception) {
        PairingResult(false, "INVALID FORMAT // QR payload is not valid JSON")
    }
}

private fun String?.isNull_or_blank(): Boolean {
    return this == null || this.trim().isEmpty()
}
