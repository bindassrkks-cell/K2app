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
    String remoteFileUrl;
    String fileName;
    String mimeType;
    String localPath;
    int progress;
    int deviceProgress;
    long downloadId = -1L;
    long downloadedBytes;
    long totalBytes;
    long createdAt;

    DownloadRecord(String jobId, String title, String url, String choiceLabel) {
        this.jobId = jobId;
        this.title = title;
        this.url = url;
        this.choiceLabel = choiceLabel;
        this.status = "queued";
        this.statusText = "Waiting for the server";
        this.remoteFileUrl = "";
        this.fileName = "";
        this.mimeType = "application/octet-stream";
        this.localPath = "";
        this.progress = 0;
        this.deviceProgress = 0;
        this.createdAt = System.currentTimeMillis();
    }

    JSONObject toJson() throws JSONException {
        return new JSONObject()
                .put("job_id", jobId)
                .put("title", title)
                // The submitted URL may contain private query parameters; do not persist it in local history.
                .put("choice", choiceLabel)
                .put("status", status)
                .put("status_text", statusText)
                .put("remote_file_url", remoteFileUrl)
                .put("file_name", fileName)
                .put("mime_type", mimeType)
                .put("local_path", localPath)
                .put("progress", progress)
                .put("device_progress", deviceProgress)
                .put("download_id", downloadId)
                .put("downloaded_bytes", downloadedBytes)
                .put("total_bytes", totalBytes)
                .put("created_at", createdAt);
    }

    static DownloadRecord fromJson(JSONObject json) {
        DownloadRecord record = new DownloadRecord(
                json.optString("job_id"),
                json.optString("title", "Media"),
                "",
                json.optString("choice", "Media"));
        record.status = json.optString("status", "queued");
        record.statusText = json.optString("status_text", "Waiting for the server");
        record.remoteFileUrl = json.optString("remote_file_url", "");
        record.fileName = json.optString("file_name", "");
        record.mimeType = json.optString("mime_type", "application/octet-stream");
        record.localPath = json.optString("local_path", "");
        record.progress = Math.max(0, Math.min(100, json.optInt("progress", 0)));
        record.deviceProgress = Math.max(0, Math.min(100, json.optInt("device_progress", 0)));
        record.downloadId = json.optLong("download_id", -1L);
        record.downloadedBytes = Math.max(0L, json.optLong("downloaded_bytes", 0L));
        record.totalBytes = Math.max(0L, json.optLong("total_bytes", 0L));
        record.createdAt = json.optLong("created_at", System.currentTimeMillis());
        if ("done".equalsIgnoreCase(record.status) && record.localPath.isEmpty()) {
            record.status = "failed";
            record.statusText = "This was a Telegram-only job. Start it again to save a copy on this phone.";
            record.progress = 0;
        } else if ("uploading".equalsIgnoreCase(record.status)) {
            record.status = "failed";
            record.statusText = "Telegram delivery is no longer used. Start this link again to save it on this phone.";
            record.progress = 0;
        }
        return record;
    }

    boolean isCompleted() {
        return "done".equalsIgnoreCase(status);
    }

    boolean isTerminal() {
        return isCompleted() || "failed".equalsIgnoreCase(status);
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
