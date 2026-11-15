package com.deniscerri.ytdl.util.telegram

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.view.View
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import com.deniscerri.ytdl.R
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

object TelegramBotSettingsDialog {
    private const val DEFAULT_API_URL = "https://k2app-telegram-bot.onrender.com"
    private val BOT_USERNAME_PATTERN = Regex("^[A-Za-z0-9_]{5,32}$")

    fun show(context: Context, onChanged: () -> Unit) {
        val view = android.view.LayoutInflater.from(context)
            .inflate(R.layout.dialog_telegram_bot_settings, null, false)
        val urlLayout = view.findViewById<TextInputLayout>(R.id.telegram_server_url_layout)
        val urlInput = view.findViewById<TextInputEditText>(R.id.telegram_server_url_input)
        val status = view.findViewById<TextView>(R.id.telegram_status)
        val openBot = view.findViewById<com.google.android.material.button.MaterialButton>(R.id.telegram_open_bot)
        val store = TelegramServerConnectionStore(context)
        val savedUrl = store.loadUrl()
        urlInput.setText(savedUrl ?: DEFAULT_API_URL)

        var botUrl: String? = null
        val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
        var requestJob: Job? = null
        val dialog = MaterialAlertDialogBuilder(context)
            .setTitle(R.string.telegram_bot)
            .setView(view)
            .setPositiveButton(R.string.telegram_connect, null)
            .setNeutralButton(R.string.telegram_disconnect, null)
            .setNegativeButton(R.string.cancel, null)
            .create()

        dialog.setOnDismissListener {
            requestJob?.cancel()
            scope.coroutineContext[Job]?.cancel()
        }
        dialog.setOnShowListener {
            val connect = dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            val clear = dialog.getButton(AlertDialog.BUTTON_NEUTRAL)
            clear.isEnabled = savedUrl != null
            if (savedUrl != null) {
                status.visibility = View.VISIBLE
                status.setText(R.string.telegram_server_saved)
                openBot.visibility = View.VISIBLE
            }
            openBot.setOnClickListener {
                val target = botUrl
                if (target != null) openTelegramBot(context, target)
                else status.setText(R.string.telegram_connect_to_find_bot)
            }
            clear.setOnClickListener {
                store.clear()
                Toast.makeText(context, R.string.telegram_disconnect_success, Toast.LENGTH_SHORT).show()
                onChanged()
                dialog.dismiss()
            }
            connect.setOnClickListener {
                urlLayout.error = null
                val baseUrl = normalizeApiUrl(urlInput.text?.toString().orEmpty())
                if (baseUrl == null) {
                    urlLayout.error = context.getString(R.string.telegram_server_url_invalid)
                    return@setOnClickListener
                }
                requestJob?.cancel()
                connect.isEnabled = false
                clear.isEnabled = false
                status.visibility = View.VISIBLE
                openBot.visibility = View.GONE
                status.setText(R.string.telegram_connecting)
                requestJob = scope.launch {
                    try {
                        val identity = withContext(Dispatchers.IO) { fetchStatus(baseUrl) }
                        store.saveUrl(baseUrl)
                        botUrl = "https://t.me/${identity.second}"
                        status.text = context.getString(R.string.telegram_connect_success, identity.first)
                        openBot.visibility = View.VISIBLE
                        clear.isEnabled = true
                        onChanged()
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (_: Exception) {
                        status.setText(R.string.telegram_connection_failed)
                        connect.isEnabled = true
                        clear.isEnabled = store.loadUrl() != null
                    }
                }
            }
        }
        dialog.show()
    }

    private fun normalizeApiUrl(value: String): String? {
        val text = value.trim().trimEnd('/')
        val uri = runCatching { Uri.parse(text) }.getOrNull() ?: return null
        if (uri.scheme != "https" || uri.host.isNullOrBlank() || uri.userInfo != null ||
            uri.query != null || uri.fragment != null || uri.path.orEmpty().endsWith("/api/status")) return null
        return text
    }

    private fun fetchStatus(baseUrl: String): Pair<String, String> {
        val connection = URL("$baseUrl/api/status").openConnection() as HttpURLConnection
        try {
            connection.requestMethod = "GET"
            connection.connectTimeout = 10_000
            // Free Render services can take about a minute to wake after inactivity.
            connection.readTimeout = 90_000
            connection.setRequestProperty("Accept", "application/json")
            if (connection.responseCode !in 200..299) throw IllegalStateException("HTTP ${connection.responseCode}")
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            val json = JSONObject(body)
            val username = json.optString("bot_username").removePrefix("@").also {
                require(BOT_USERNAME_PATTERN.matches(it))
            }
            require(json.optString("service") == "k2app" && json.optString("mode") == "webhook")
            val suppliedBotUrl = json.optString("bot_url")
            val botUri = Uri.parse(suppliedBotUrl)
            require(botUri.scheme == "https" && botUri.host == "t.me" && botUri.pathSegments.firstOrNull() == username)
            return Pair(username, username)
        } finally {
            connection.disconnect()
        }
    }

    private fun openTelegramBot(context: Context, botUrl: String) {
        try {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(botUrl)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(context, R.string.telegram_open_bot_failed, Toast.LENGTH_SHORT).show()
        }
    }
}
