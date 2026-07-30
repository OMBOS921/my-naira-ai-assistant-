package com.naira.remote.ui.theme

import android.app.Activity
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView

private val CyberDarkColorScheme = darkColorScheme(
    primary = CyberNeonCyan,
    onPrimary = CyberBackground,
    primaryContainer = CyberSurfaceVariant,
    onPrimaryContainer = CyberNeonCyan,
    secondary = CyberSecondaryPurple,
    onSecondary = CyberTextPrimary,
    secondaryContainer = CyberSurfaceVariant,
    onSecondaryContainer = CyberSecondaryPurpleLight,
    error = CyberAlertPink,
    onError = CyberBackground,
    background = CyberBackground,
    onBackground = CyberTextPrimary,
    surface = CyberSurface,
    onSurface = CyberTextPrimary,
    surfaceVariant = CyberSurfaceVariant,
    onSurfaceVariant = CyberTextSecondary
)

@Composable
fun NairaTheme(
    content: @Composable () -> Unit
) {
    val colorScheme = CyberDarkColorScheme
    val view = LocalView.current

    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            window.navigationBarColor = colorScheme.background.toArgb()
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = CyberTypography,
        content = content
    )
}
