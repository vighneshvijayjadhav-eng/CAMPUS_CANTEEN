package `in`.ac.aissms.canteen.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

data class StoredSession(val accessToken: String, val refreshToken: String, val sessionId: String)

interface TokenStorage {
    fun load(): StoredSession?
    fun save(session: StoredSession)
    fun clear()
}

/**
 * Persists the rotating session so students stay signed in across restarts. Tokens are
 * encrypted with a non-exportable AES-GCM key held in the Android Keystore; only ciphertext
 * reaches SharedPreferences. Backups are disabled in the manifest.
 */
class KeystoreTokenStorage(context: Context) : TokenStorage {
    private val prefs = context.getSharedPreferences("session", Context.MODE_PRIVATE)

    override fun load(): StoredSession? = runCatching {
        val sealed = prefs.getString(KEY, null) ?: return null
        val raw = Base64.decode(sealed, Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw, 0, IV_BYTES))
        val parts = String(cipher.doFinal(raw, IV_BYTES, raw.size - IV_BYTES)).split('\n')
        StoredSession(parts[0], parts[1], parts[2])
    }.getOrElse {
        clear() // Unreadable (e.g. key invalidated): require a fresh sign-in.
        null
    }

    override fun save(session: StoredSession) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val plain = listOf(session.accessToken, session.refreshToken, session.sessionId)
            .joinToString("\n").toByteArray()
        val sealed = cipher.iv + cipher.doFinal(plain)
        prefs.edit().putString(KEY, Base64.encodeToString(sealed, Base64.NO_WRAP)).apply()
    }

    override fun clear() {
        prefs.edit().remove(KEY).apply()
    }

    private fun key(): SecretKey {
        val store = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (store.getEntry(ALIAS, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        generator.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build(),
        )
        return generator.generateKey()
    }

    private companion object {
        const val ALIAS = "canteen_session_key"
        const val KEY = "sealed_session"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
    }
}

class InMemoryTokenStorage(private var session: StoredSession? = null) : TokenStorage {
    override fun load() = session
    override fun save(session: StoredSession) { this.session = session }
    override fun clear() { session = null }
}
