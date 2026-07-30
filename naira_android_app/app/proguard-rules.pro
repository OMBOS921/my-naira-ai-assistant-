# ProGuard / R8 Shrinking, Obfuscation, and Security Preservation Rules for Naira-OS Remote App

# 1. Preserve Cryptographic, Keystore, & Security Modules
-keep class com.naira.remote.security.** { *; }
-keepclassmembers class com.naira.remote.security.** { *; }

# 2. Preserve Jetpack Security Crypto & Biometrics
-keep class androidx.security.crypto.** { *; }
-keepclassmembers class androidx.security.crypto.** { *; }
-keep class androidx.biometric.** { *; }
-keepclassmembers class androidx.biometric.** { *; }

# 3. Preserve RootBeer Library Detection Signatures
-keep class com.scottyab.rootbeer.** { *; }
-keepclassmembers class com.scottyab.rootbeer.** { *; }

# 4. Preserve Foreground Services & Receivers
-keep class com.naira.remote.services.** { *; }
-keepclassmembers class com.naira.remote.services.** { *; }

# 5. Serialization & Network Data Models
-keepattributes Signature
-keepattributes *Annotation*
-keepattributes EnclosingMethod
-keepattributes InnerClasses
-keepattributes SourceFile,LineNumberTable

# 6. OkHttp & WebSocket Obfuscation Rules
-dontwarn okhttp3.**
-dontwarn okio.**
-keepnames class okhttp3.** { *; }

# 7. Firebase Cloud Messaging Rules
-keep class com.google.firebase.messaging.** { *; }
-keepclassmembers class com.google.firebase.messaging.** { *; }
