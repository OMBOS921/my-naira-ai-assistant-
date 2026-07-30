package com.naira.remote.security

import java.security.MessageDigest
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec
import kotlin.math.abs

/**
 * HmacVerifier provides HMAC-SHA256 signature verification, strict timestamp validation (±45s),
 * and a 100-entry LRU nonce cache to prevent replay attacks.
 */
object HmacVerifier {

    private const val MAX_TIMESTAMP_DELTA_SECONDS = 45L
    private const val MAX_NONCE_CACHE_SIZE = 100

    // Synchronized LRU Cache storing last 100 nonces
    private val nonceCache = object : LinkedHashMap<String, Long>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Long>?): Boolean {
            return size > MAX_NONCE_CACHE_SIZE
        }
    }

    /**
     * Generates HMAC-SHA256 signature as hex string.
     */
    fun generateHmac(payload: String, secretKey: String): String {
        return try {
            val mac = Mac.getInstance("HmacSHA256")
            val secretKeySpec = SecretKeySpec(secretKey.toByteArray(Charsets.UTF_8), "HmacSHA256")
            mac.init(secretKeySpec)
            val hmacBytes = mac.doFinal(payload.toByteArray(Charsets.UTF_8))
            bytesToHex(hmacBytes)
        } catch (e: Exception) {
            ""
        }
    }

    /**
     * Verifies HMAC-SHA256 signature using constant-time comparison.
     */
    fun verifyHmac(payload: String, signature: String, secretKey: String): Boolean {
        if (signature.isBlank() || secretKey.isBlank()) return false
        val expectedHmac = generateHmac(payload, secretKey)
        if (expectedHmac.isBlank()) return false

        return MessageDigest.isEqual(
            expectedHmac.lowercase().toByteArray(Charsets.UTF_8),
            signature.lowercase().toByteArray(Charsets.UTF_8)
        )
    }

    /**
     * Validates timestamp within ±45s window and verifies nonce hasn't been used.
     */
    @Synchronized
    fun validateNonceAndTimestamp(nonce: String, timestampSec: Long): Boolean {
        if (nonce.isBlank()) return false

        val currentTimestampSec = System.currentTimeMillis() / 1000L
        val timeDelta = abs(currentTimestampSec - timestampSec)

        // Timestamp window check (±45s)
        if (timeDelta > MAX_TIMESTAMP_DELTA_SECONDS) {
            return false
        }

        // Nonce replay check
        if (nonceCache.containsKey(nonce)) {
            return false // Replay attack detected!
        }

        // Store nonce in LRU cache
        nonceCache[nonce] = currentTimestampSec
        return true
    }

    /**
     * Clears cached nonces (e.g., when resetting session or unpairing).
     */
    @Synchronized
    fun clearNonceCache() {
        nonceCache.clear()
    }

    private fun bytesToHex(bytes: ByteArray): String {
        val sb = StringBuilder()
        for (b in bytes) {
            sb.append(String.format("%02x", b))
        }
        return sb.toString()
    }
}
