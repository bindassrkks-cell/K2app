package com.k2app.lite;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.util.ArrayList;
import java.util.List;

final class DownloadRecord {
    String jobId;
    String title;
    String url;
    String choiceLabel;
    String status;
    String statusText;
    int progress;
    long createdAt;

    DownloadRecord(String jobId, String title, String url, String choiceLabel) {
        this.jobId = jobId;
        this.title = title;
        this.url = url;
        this.choiceLabel = choiceLabel;
        this.status = "queued";
        this.statusText = "Waiting for the Telegram bot";
        this.progress = 0;
        this.createdAt = System.currentTimeMillis();
    }

    JSONObject toJson() throws JSONException {
        return new JSONObject()
                .put("job_id", jobId)
                .put("title", title)
                .put("url", url)
                .put("choice", choiceLabel)
                .put("status", status)
                .put("status_text", statusText)
                .put("progress", progress)
                .put("created_at", createdAt);
    }

    static DownloadRecord fromJson(JSONObject json) {
        DownloadRecord record = new DownloadRecord(
                json.optString("job_id"),
                json.optString("title", "Media"),
                json.optString("url"),
                json.optString("choice", "Media"));
        record.status = json.optString("status", "queued");
        record.statusText = json.optString("status_text", "Waiting for the Telegram bot");
        record.progress = Math.max(0, Math.min(100, json.optInt("progress", 0)));
        record.createdAt = json.optLong("created_at", System.currentTimeMillis());
        return record;
    }

    boolean isCompleted() {
        return "done".equalsIgnoreCase(status);
    }

    static List<DownloadRecord> parseList(String value) {
        List<DownloadRecord> records = new ArrayList<>();
        if (value == null || value.isEmpty()) return records;
        try {
            JSONArray array = new JSONArray(value);
            for (int i = 0; i < array.length(); i++) {
                JSONObject item = array.optJSONObject(i);
                if (item != null && !item.optString("job_id").isEmpty()) records.add(fromJson(item));
            }
        } catch (JSONException ignored) {
            return new ArrayList<>();
        }
        return records;
    }
}
