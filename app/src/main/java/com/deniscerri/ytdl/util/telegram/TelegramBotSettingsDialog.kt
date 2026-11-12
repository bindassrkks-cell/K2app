package com.deniscerri.ytdl.util.telegram

import android.content.Context
import android.content.Intent
import android.text.InputType
import android.view.View
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.core.content.ContextCompat
import com.deniscerri.ytdl.R
import com.deniscerri.ytdl.service.TelegramPollingService
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import com.google.android.material.textfield.TextInputEditText
import com.google.android.material.textfield.TextInputLayout
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

object TelegramBotSettingsDialog {
    fun show(context: Context, onChanged: () -> Unit) {
        val view = android.view.LayoutInflater.from(context)
            .inflate(R.layout.dialog_telegram_bot_settings, null, false)
        val tokenLayout = view.findViewById<TextInputLayout>(R.id.telegram_token_layout)
        val chatLayout = view.findViewById<TextInputLayout>(R.id.telegram_chat_layout)
        val tokenInput = view.findViewById<TextInputEditText>(R.id.telegram_token_input)
        val chatInput = view.findViewById<TextInputEditText>(R.id.telegram_chat_input)
        val status = view.findViewById<android.widget.TextView>(R.id.telegram_status)
        val store = TelegramBotConfigStore(context)
        val existing = store.load()

        tokenInput.inputType = InputType.TYPE_CLASS_TEXT or
            InputType.TYPE_TEXT_VARIATION_PASSWORD or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS
        existing?.let {
            tokenInput.setText(it.token)
            chatInput.setText(it.chatId)
        }
        if (TelegramPollingService.isRunning) {
            status.visibility = View.VISIBLE
            status.setText(R.string.telegram_polling_status)
        } else if (existing != null) {
            status.visibility = View.VISIBLE
            status.setText(R.string.telegram_credentials_saved)
        }

        val dialog = MaterialAlertDialogBuilder(context)
            .setTitle(R.string.telegram_bot)
            .setView(view)
            .setPositiveButton(R.string.telegram_connect_start, null)
            .setNeutralButton(R.string.telegram_disconnect, null)
            .setNegativeButton(R.string.cancel, null)
            .create()

        dialog.setOnShowListener {
            val connectButton = dialog.getButton(AlertDialog.BUTTON_POSITIVE)
            val disconnectButton = dialog.getButton(AlertDialog.BUTTON_NEUTRAL)
            disconnectButton.isEnabled = existing != null

            disconnectButton.setOnClickListener {
                store.clear()
                context.stopService(Intent(context, TelegramPollingService::class.java))
                Toast.makeText(context, R.string.telegram_disconnect_success, Toast.LENGTH_SHORT).show()
                onChanged()
                dialog.dismiss()
            }

            connectButton.setOnClickListener {
                tokenLayout.error = null
                chatLayout.error = null
                val token = tokenInput.text?.toString()?.trim().orEmpty()
                val chatId = chatInput.text?.toString()?.trim().orEmpty()
                if (!TOKEN_PATTERN.matches(token)) {
                    tokenLayout.error = context.getString(R.string.telegram_token_required)
                    return@setOnClickListener
                }
                if (!CHAT_ID_PATTERN.matches(chatId)) {
                    chatLayout.error = context.getString(R.string.telegram_chat_id_required)
                    return@setOnClickListener
                }

                connectButton.isEnabled = false
                disconnectButton.isEnabled = false
                dialog.getButton(AlertDialog.BUTTON_NEGATIVE).isEnabled = false
                status.visibility = View.VISIBLE
                status.setText(R.string.telegram_connecting)
                CoroutineScope(SupervisorJob() + Dispatchers.Main).launch {
                    try {
                        val identity = withContext(Dispatchers.IO) {
                            TelegramBotApi.validateForPolling(token).also {
                                TelegramBotApi.validateChat(token, chatId)
                            }
                        }
                        val initialOffset = if (existing?.token == token) {
                            store.updateOffset()
                        } else {
                            withContext(Dispatchers.IO) { TelegramBotApi.discardPendingUpdates(token) }
                        }

                        context.stopService(Intent(context, TelegramPollingService::class.java))
                        store.save(TelegramBotConfigStore.Config(token, chatId))
                        store.setUpdateOffset(initialOffset)
                        ContextCompat.startForegroundService(
                            context,
                            Intent(context, TelegramPollingService::class.java)
                                .setAction(TelegramPollingService.ACTION_START)
                        )
                        status.text = context.getString(R.string.telegram_connect_success, identity.username)
                        Toast.makeText(context, status.text, Toast.LENGTH_LONG).show()
                        onChanged()
                        dialog.dismiss()
                    } catch (error: Exception) {
                        val safeMessage = (error.message ?: "Telegram connection failed.")
                            .replace(token, "[hidden]")
                            .take(180)
                        status.text = context.getString(R.string.telegram_connection_failed, safeMessage)
                        connectButton.isEnabled = true
                        disconnectButton.isEnabled = existing != null
                        dialog.getButton(AlertDialog.BUTTON_NEGATIVE).isEnabled = true
                    }
                }
            }
        }
        dialog.show()
    }

    private val TOKEN_PATTERN = Regex("^[0-9]+:[A-Za-z0-9_-]{20,}$")
    private val CHAT_ID_PATTERN = Regex("^-?[0-9]+$")
}
