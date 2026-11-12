package com.deniscerri.ytdl.util.telegram

import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

object TelegramBotApi {
    data class BotIdentity(val username: String)

    class ApiException(message: String, val errorCode: Int? = null) : IOException(message)

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(35, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    fun validateForPolling(token: String): BotIdentity {
        val me = call(token, "getMe").getJSONObject("result")
        val webhook = call(token, "getWebhookInfo").getJSONObject("result")
        if (webhook.optString("url").isNotBlank()) {
            throw ApiException("This bot already has a webhook configured. Telegram polling and a webhook cannot run at the same time.")
        }
        return BotIdentity(me.optString("username").ifBlank { "bot" })
    }

    fun validateChat(token: String, chatId: String) {
        call(token, "getChat?chat_id=$chatId")
    }

    /** Discards any messages that were already waiting when a new bot was connected. */
    fun discardPendingUpdates(token: String): Long {
        val updates = call(token, "getUpdates?offset=-1&timeout=0&allowed_updates=%5B%22message%22%5D")
            .optJSONArray("result") ?: JSONArray()
        var nextOffset = 0L
        for (index in 0 until updates.length()) {
            nextOffset = maxOf(nextOffset, updates.getJSONObject(index).optLong("update_id") + 1L)
        }
        return nextOffset
    }

    fun getUpdates(token: String, offset: Long): JSONArray {
        val result = call(
            token,
            "getUpdates?offset=$offset&timeout=20&allowed_updates=%5B%22message%22%5D"
        ).optJSONArray("result")
        return result ?: JSONArray()
    }

    fun sendMessage(token: String, chatId: String, text: String) {
        val body = JSONObject()
            .put("chat_id", chatId)
            .put("text", text)
        call(token, "sendMessage", body)
    }

    private fun call(token: String, method: String, body: JSONObject? = null): JSONObject {
        val requestBuilder = Request.Builder()
            .url("https://api.telegram.org/bot$token/$method")
            .header("Accept", "application/json")
        if (body == null) {
            requestBuilder.get()
        } else {
            requestBuilder.post(body.toString().toRequestBody(JSON_MEDIA_TYPE))
        }

        client.newCall(requestBuilder.build()).execute().use { response ->
            val responseText = response.body?.string().orEmpty()
            val json = try {
                JSONObject(responseText)
            } catch (_: Exception) {
                throw ApiException("Telegram returned an unreadable response.", response.code)
            }
            if (!response.isSuccessful || !json.optBoolean("ok", false)) {
                val description = json.optString("description").ifBlank { "Telegram request failed." }
                throw ApiException(description, json.optInt("error_code").takeIf { it != 0 } ?: response.code)
            }
            return json
        }
    }

    private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
}
