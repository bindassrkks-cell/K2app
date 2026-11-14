package com.deniscerri.ytdl.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.util.Patterns
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.ViewModelStore
import androidx.preference.PreferenceManager
import com.deniscerri.ytdl.MainActivity
import com.deniscerri.ytdl.R
import com.deniscerri.ytdl.database.DBManager
import com.deniscerri.ytdl.database.enums.DownloadType
import com.deniscerri.ytdl.database.repository.ResultRepository
import com.deniscerri.ytdl.database.viewmodel.DownloadViewModel
import com.deniscerri.ytdl.util.DownloadQueueUtil
import com.deniscerri.ytdl.util.telegram.TelegramBotApi
import com.deniscerri.ytdl.util.telegram.TelegramBotConfigStore
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** User-started foreground long polling for URLs sent to the configured Telegram chat. */
class TelegramPollingService : Service() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private lateinit var configStore: TelegramBotConfigStore
    private var pollingJob: Job? = null

    override fun onCreate() {
        super.onCreate()
        configStore = TelegramBotConfigStore(this)
        isRunning = true
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            configStore.setEnabled(false)
            stopSelf(startId)
            return START_NOT_STICKY
        }

        val config = configStore.load()
        if (config == null || !configStore.isEnabled()) {
            stopSelf(startId)
            return START_NOT_STICKY
        }

        startAsForeground(notification(getString(R.string.telegram_service_notification)))
        if (pollingJob?.isActive != true) {
            pollingJob = serviceScope.launch { pollTelegram(config) }
        }
        return START_STICKY
    }

    private fun startAsForeground(notification: Notification) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                notification,
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            )
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private suspend fun pollTelegram(config: TelegramBotConfigStore.Config) {
        var offset = configStore.updateOffset()
        while (serviceScope.isActive) {
            try {
                val updates = withContext(Dispatchers.IO) {
                    TelegramBotApi.getUpdates(config.token, offset)
                }
                for (index in 0 until updates.length()) {
                    val update = updates.optJSONObject(index) ?: continue
                    val updateId = update.optLong("update_id", offset - 1L)
                    val message = update.optJSONObject("message")
                    try {
                        if (message != null && isAllowedChat(message, config.chatId)) {
                            handleMessage(message, config)
                        }
                    } catch (_: Exception) {
                        // A failed message must not stop polling other updates; never log the bot token.
                    } finally {
                        if (updateId >= offset) {
                            offset = updateId + 1L
                            configStore.setUpdateOffset(offset)
                        }
                    }
                }
            } catch (error: CancellationException) {
                throw error
            } catch (error: TelegramBotApi.ApiException) {
                if (error.errorCode == 401) {
                    configStore.setEnabled(false)
                    updateNotification("Telegram rejected the saved token. Reconnect in K2App settings.")
                    stopSelf()
                    return
                }
                delay(POLL_RETRY_DELAY_MS)
            } catch (_: Exception) {
                delay(POLL_RETRY_DELAY_MS)
            }
        }
    }

    private fun isAllowedChat(message: JSONObject, expectedChatId: String): Boolean {
        val actualChatId = message.optJSONObject("chat")?.optString("id").orEmpty()
        return actualChatId == expectedChatId
    }

    private suspend fun handleMessage(
        message: JSONObject,
        config: TelegramBotConfigStore.Config
    ) {
        val text = message.optString("text").ifBlank { message.optString("caption") }
        if (text.isBlank()) return

        val urls = extractUrls(text).take(MAX_URLS_PER_MESSAGE)
        if (urls.isEmpty()) {
            if (text.startsWith("/start") || text.startsWith("/help")) {
                sendReply(config, getString(R.string.telegram_help_message))
            }
            return
        }

        urls.forEach { url ->
            val queued = runCatching { enqueueUrl(url) }.getOrDefault(false)
            val reply = if (queued) {
                getString(R.string.telegram_url_queued)
            } else {
                getString(R.string.telegram_url_failed)
            }
            sendReply(config, reply)
        }
    }

    private suspend fun enqueueUrl(url: String): Boolean = withContext(Dispatchers.IO) {
        val database = DBManager.getInstance(applicationContext)
        val resultRepository = ResultRepository(
            database.resultDao,
            database.commandTemplateDao,
            applicationContext
        )
        val result = resultRepository.getResultsFromSource(
            inputQuery = url,
            resetResults = false,
            addToResults = false,
            singleItem = true
        ).firstOrNull() ?: return@withContext false

        val viewModelStore = ViewModelStore()
        try {
            val viewModel = ViewModelProvider(
                viewModelStore,
                ViewModelProvider.AndroidViewModelFactory.getInstance(application)
            )[DownloadViewModel::class.java]
            val preferences = PreferenceManager.getDefaultSharedPreferences(applicationContext)
            val typeName = preferences.getString("preferred_download_type", DownloadType.video.toString())
                ?: DownloadType.video.toString()
            val type = runCatching { DownloadType.valueOf(typeName) }.getOrDefault(DownloadType.video)
            val downloadItem = viewModel.createDownloadItemFromResult(result, givenType = type)
            val queueResult = DownloadQueueUtil(applicationContext).enqueue(listOf(downloadItem))
            val scheduledSuccessfully = preferences.getBoolean("use_scheduler", false) &&
                queueResult.queued.isEmpty() && queueResult.message.isBlank()
            queueResult.queued.isNotEmpty() || queueResult.duplicates.isNotEmpty() || scheduledSuccessfully
        } finally {
            viewModelStore.clear()
        }
    }

    private fun extractUrls(text: String): List<String> {
        val urlPattern = Regex("https?://[^\\s<>]+", RegexOption.IGNORE_CASE)
        return urlPattern.findAll(text)
            .map { it.value.trimEnd('.', ',', '!', '?', ';', ':', ')', ']', '}', '\"', '\'') }
            .filter { candidate ->
                candidate.length <= MAX_URL_LENGTH && runCatching {
                    val uri = Uri.parse(candidate)
                    uri.scheme in listOf("http", "https") &&
                        !uri.host.isNullOrBlank() &&
                        Patterns.WEB_URL.matcher(uri.host!!).matches()
                }.getOrDefault(false)
            }
            .distinct()
            .toList()
    }

    private fun sendReply(config: TelegramBotConfigStore.Config, message: String) {
        runCatching { TelegramBotApi.sendMessage(config.token, config.chatId, message) }
    }

    private fun updateNotification(message: String) {
        val manager = getSystemService(NotificationManager::class.java)
        manager.notify(NOTIFICATION_ID, notification(message))
    }

    private fun notification(message: String): Notification {
        val stopIntent = Intent(this, TelegramPollingService::class.java).setAction(ACTION_STOP)
        val stopPendingIntent = PendingIntent.getService(
            this,
            STOP_REQUEST_CODE,
            stopIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val openAppIntent = PendingIntent.getActivity(
            this,
            OPEN_APP_REQUEST_CODE,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_link)
            .setContentTitle("${getString(R.string.app_name)} · ${getString(R.string.telegram_bot)}")
            .setContentText(message)
            .setContentIntent(openAppIntent)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .addAction(R.drawable.ic_link, getString(R.string.telegram_stop_polling), stopPendingIntent)
            .build()
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.telegram_service_channel),
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = getString(R.string.telegram_service_notification)
                setShowBadge(false)
            }
            getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        }
    }

    override fun onTimeout(startId: Int, fgsType: Int) {
        if (fgsType and ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC != 0) {
            configStore.setEnabled(false)
            updateNotification(getString(R.string.telegram_service_limit_reached))
            stopSelf(startId)
        }
    }

    override fun onDestroy() {
        isRunning = false
        serviceScope.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_START = "com.deniscerri.ytdl.action.TELEGRAM_START"
        const val ACTION_STOP = "com.deniscerri.ytdl.action.TELEGRAM_STOP"
        @Volatile var isRunning: Boolean = false
            private set

        private const val CHANNEL_ID = "k2app_telegram_polling"
        private const val NOTIFICATION_ID = 7421
        private const val STOP_REQUEST_CODE = 7422
        private const val OPEN_APP_REQUEST_CODE = 7423
        private const val POLL_RETRY_DELAY_MS = 6_000L
        private const val MAX_URLS_PER_MESSAGE = 5
        private const val MAX_URL_LENGTH = 2048
    }
}
