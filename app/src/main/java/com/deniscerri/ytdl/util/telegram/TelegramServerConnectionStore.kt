package com.deniscerri.ytdl.util.telegram

import android.content.Context
import androidx.preference.PreferenceManager

/** Stores only the public HTTPS endpoint used by the standalone Telegram bot service. */
class TelegramServerConnectionStore(context: Context) {
    private val preferences = PreferenceManager.getDefaultSharedPreferences(context.applicationContext)

    init {
        // The server now owns the bot token. Retire the old local polling configuration.
        context.applicationContext.getSharedPreferences("k2app_telegram_secret_store", Context.MODE_PRIVATE)
            .edit().clear().apply()
        preferences.edit().remove("k2app_telegram_update_offset").apply()
    }

    fun loadUrl(): String? = preferences.getString(URL_KEY, null)
    fun saveUrl(url: String) = preferences.edit().putString(URL_KEY, url).apply()
    fun clear() = preferences.edit().remove(URL_KEY).apply()

    private companion object {
        const val URL_KEY = "telegram_server_api_url"
    }
}
