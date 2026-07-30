package com.naira.remote.security

import android.content.Context
import android.content.SharedPreferences
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * CryptoVault provides hardware-backed Android Keystore cryptography and EncryptedSharedPreferences
 * to ensure plaintext keys (Master Key & Ngrok Tunnel URL) never hit plain RAM/storage.
 */
object CryptoVault {

    private const val PREFS_FILENAME = "naira_secure_vault"
    private const val KEY_MASTER_KEY = "vault_master_key"
    private const val KEY_NGROK_URL = "vault_ngrok_url"
    private const val KEYSTORE_ALIAS = "NairaMasterKeyAlias"
    private const val AES_GCM_TAG_LENGTH = 128
    private const val IV_SIZE = 12

    private var sharedPreferences: SharedPreferences? = null

    @Synchronized
    fun init(context: Context) {
        if (sharedPreferences != null) return

        try {
            val masterKey = MasterKey.Builder(context.applicationContext)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            sharedPreferences = EncryptedSharedPreferences.create(
                context.applicationContext,
                PREFS_FILENAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        } catch (e: Exception) {
            // Fallback or recovery if Keystore gets corrupted
            context.applicationContext.getSharedPreferences(PREFS_FILENAME, Context.MODE_PRIVATE).edit().clear().apply()
            val masterKey = MasterKey.Builder(context.applicationContext)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()

            sharedPreferences = EncryptedSharedPreferences.create(
                context.applicationContext,
                PREFS_FILENAME,
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            )
        }

        ensureKeystoreKeyGenerated()
    }

    private fun ensureKeystoreKeyGenerated() {
        val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        if (!keyStore.containsAlias(KEYSTORE_ALIAS)) {
            val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
            val keyGenSpec = KeyGenParameterSpec.Builder(
                KEYSTORE_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()

            keyGenerator.init(keyGenSpec)
            keyGenerator.generateKey()
        }
    }

    fun saveMasterKey(masterKey: String) {
        sharedPreferences?.edit()?.putString(KEY_MASTER_KEY, masterKey)?.apply()
    }

    fun getMasterKey(): String? {
        return sharedPreferences?.getString(KEY_MASTER_KEY, null)
    }

    fun saveNgrokUrl(url: String) {
        sharedPreferences?.edit()?.putString(KEY_NGROK_URL, url)?.apply()
    }

    fun updateTunnelUrl(newUrl: String) {
        saveNgrokUrl(newUrl)
    }

    fun getNgrokUrl(): String? {
        return sharedPreferences?.getString(KEY_NGROK_URL, null)
    }

    fun getPairedServerUrl(): String {
        return getNgrokUrl() ?: ""
    }

    fun getHmacSecretKey(): String? {
        return getMasterKey()
    }

    fun isPaired(): Boolean {
        return !getMasterKey().isNull_or_blank() && !getNgrokUrl().isNull_or_blank()
    }

    fun clearVault() {
        sharedPreferences?.edit()?.clear()?.apply()
    }

    private fun String?.isNull_or_blank(): Boolean {
        return this == null || this.trim().isEmpty()
    }

    /**
     * Encrypts plain text string using Keystore AES/GCM/NoPadding.
     * Returns Base64-encoded IV + CipherText.
     */
    fun encryptData(plainText: String): String? {
        return try {
            val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            val secretKey = keyStore.getKey(KEYSTORE_ALIAS, null) as SecretKey

            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, secretKey)
            val iv = cipher.iv
            val cipherText = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))

            val combined = ByteArray(iv.size + cipherText.size)
            System.arraycopy(iv, 0, combined, 0, iv.size)
            System.arraycopy(cipherText, 0, combined, iv.size, cipherText.size)

            Base64.encodeToString(combined, Base64.NO_WRAP)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    /**
     * Decrypts Base64-encoded IV + CipherText using Keystore AES/GCM/NoPadding.
     */
    fun decryptData(encodedData: String): String? {
        return try {
            val combined = Base64.decode(encodedData, Base64.NO_WRAP)
            if (combined.size <= IV_SIZE) return null

            val iv = ByteArray(IV_SIZE)
            val cipherText = ByteArray(combined.size - IV_SIZE)

            System.arraycopy(combined, 0, iv, 0, IV_SIZE)
            System.arraycopy(combined, IV_SIZE, cipherText, 0, cipherText.size)

            val keyStore = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            val secretKey = keyStore.getKey(KEYSTORE_ALIAS, null) as SecretKey

            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            val spec = GCMParameterSpec(AES_GCM_TAG_LENGTH, iv)
            cipher.init(Cipher.DECRYPT_MODE, secretKey, spec)

            String(cipher.doFinal(cipherText), Charsets.UTF_8)
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }
}
