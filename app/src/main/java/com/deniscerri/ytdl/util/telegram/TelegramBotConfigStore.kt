package com.deniscerri.ytdl.util.telegram

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.preference.PreferenceManager
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/** Stores the Telegram bearer token and allowed chat ID encrypted with an Android Keystore key. */
class TelegramBotConfigStore(context: Context) {
    data class Config(val token: String, val chatId: String)

    private val appContext = context.applicationContext
    private val secrets = appContext.getSharedPreferences(SECRET_PREFS, Context.MODE_PRIVATE)
    private val preferences = PreferenceManager.getDefaultSharedPreferences(appContext)

    @Synchronized
    fun save(config: Config) {
        require(config.token.isNotBlank() && config.chatId.isNotBlank())
        secrets.edit()
            .putString(ENCRYPTED_CONFIG_KEY, encrypt("${config.token}\n${config.chatId}"))
            .putBoolean(ENABLED_KEY, true)
            .apply()
    }

    @Synchronized
    fun load(): Config? {
        val encrypted = secrets.getString(ENCRYPTED_CONFIG_KEY, null) ?: return null
        return runCatching {
            val parts = decrypt(encrypted).split('\n', limit = 2)
            if (parts.size != 2 || parts[0].isBlank() || parts[1].isBlank()) null
            else Config(parts[0], parts[1])
        }.getOrNull()
    }

    fun isEnabled(): Boolean = secrets.getBoolean(ENABLED_KEY, false)

    fun setEnabled(enabled: Boolean) {
        secrets.edit().putBoolean(ENABLED_KEY, enabled).apply()
    }

    fun updateOffset(): Long = preferences.getLong(UPDATE_OFFSET_KEY, 0L)

    fun setUpdateOffset(offset: Long) {
        preferences.edit().putLong(UPDATE_OFFSET_KEY, offset).apply()
    }

    fun clear() {
        secrets.edit().clear().apply()
        preferences.edit().remove(UPDATE_OFFSET_KEY).apply()
    }

    private fun encrypt(plainText: String): String {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, getOrCreateKey())
        val encrypted = cipher.doFinal(plainText.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(cipher.iv, Base64.NO_WRAP) + "." +
            Base64.encodeToString(encrypted, Base64.NO_WRAP)
    }

    private fun decrypt(encoded: String): String {
        val parts = encoded.split('.', limit = 2)
        require(parts.size == 2)
        val iv = Base64.decode(parts[0], Base64.NO_WRAP)
        val ciphertext = Base64.decode(parts[1], Base64.NO_WRAP)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, getOrCreateKey(), GCMParameterSpec(128, iv))
        return cipher.doFinal(ciphertext).toString(Charsets.UTF_8)
    }

    private fun getOrCreateKey(): SecretKey {
        val keyStore = KeyStore.getInstance(ANDROID_KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .setRandomizedEncryptionRequired(true)
                .build()
        )
        return generator.generateKey()
    }

    private companion object {
        const val SECRET_PREFS = "k2app_telegram_secret_store"
        const val ENCRYPTED_CONFIG_KEY = "encrypted_bot_config"
        const val ENABLED_KEY = "bot_enabled"
        const val UPDATE_OFFSET_KEY = "k2app_telegram_update_offset"
        const val KEY_ALIAS = "k2app.telegram.bot.config"
        const val ANDROID_KEYSTORE = "AndroidKeyStore"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
    }
}
