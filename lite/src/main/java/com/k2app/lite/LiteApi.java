package com.k2app.lite;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;

final class LiteApi {
    private final String baseUrl;

    LiteApi(String baseUrl) {
        this.baseUrl = baseUrl.replaceAll("/+$", "");
    }

    JSONObject serviceStatus() throws IOException, JSONException {
        return request("GET", "/api/status", null, null);
    }

    JSONObject pair(String code) throws IOException, JSONException {
        JSONObject body = new JSONObject().put("code", code);
        return request("POST", "/api/v1/auth/pair", body, null);
    }

    JSONObject analyze(String mediaUrl, String token) throws IOException, JSONException {
        JSONObject body = new JSONObject().put("url", mediaUrl);
        return request("POST", "/api/v1/jobs", body, token);
    }

    JSONObject choose(String jobId, int choiceIndex, String token) throws IOException, JSONException {
        JSONObject body = new JSONObject().put("choice_index", choiceIndex);
        return request("POST", "/api/v1/jobs/" + pathPart(jobId) + "/choose", body, token);
    }

    JSONObject job(String jobId, String token) throws IOException, JSONException {
        return request("GET", "/api/v1/jobs/" + pathPart(jobId), null, token);
    }

    private String pathPart(String value) throws IOException {
        return URLEncoder.encode(value, StandardCharsets.UTF_8.name()).replace("+", "%20");
    }

    private JSONObject request(String method, String path, JSONObject body, String bearer)
            throws IOException, JSONException {
        HttpURLConnection connection = null;
        try {
            connection = (HttpURLConnection) new URL(baseUrl + path).openConnection();
            connection.setRequestMethod(method);
            connection.setConnectTimeout(20_000);
            connection.setReadTimeout(120_000);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("User-Agent", "K2App-Lite/1.0");
            if (bearer != null && !bearer.isEmpty()) {
                connection.setRequestProperty("Authorization", "Bearer " + bearer);
            }
            if (body != null) {
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                byte[] payload = body.toString().getBytes(StandardCharsets.UTF_8);
                connection.setFixedLengthStreamingMode(payload.length);
                try (OutputStream output = connection.getOutputStream()) {
                    output.write(payload);
                }
            }
            int status = connection.getResponseCode();
            InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
            String responseText = stream == null ? "{}" : readFully(stream);
            JSONObject response;
            try {
                response = new JSONObject(responseText);
            } catch (JSONException malformed) {
                if (status >= 400) {
                    throw new ApiException(status, "The K2App service returned HTTP " + status + ".");
                }
                throw malformed;
            }
            if (status >= 400) {
                String detail = response.optString("detail", "Request failed (HTTP " + status + ")");
                throw new ApiException(status, detail);
            }
            return response;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    private String readFully(InputStream stream) throws IOException {
        try (InputStream input = stream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            byte[] buffer = new byte[4096];
            int count;
            while ((count = input.read(buffer)) != -1) output.write(buffer, 0, count);
            return output.toString(StandardCharsets.UTF_8.name());
        }
    }

    static final class ApiException extends IOException {
        final int statusCode;

        ApiException(int statusCode, String message) {
            super(message);
            this.statusCode = statusCode;
        }
    }
}
