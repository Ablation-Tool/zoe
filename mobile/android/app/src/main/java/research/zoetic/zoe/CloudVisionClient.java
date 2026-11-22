package research.zoetic.zoe;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

final class CloudVisionClient {
    static final String DEFAULT_MODEL = "gemini-2.5-flash";
    static final String[] SUPPORTED_MODELS = {"gemini-2.5-flash", "gemini-2.5-pro"};
    private static final String PREFS = "zoe_cloud_prefs";
    private static final String KEY_API = "gemini_api_key";
    private static final String KEY_MODEL = "gemini_model";
    private static final int MAX_RESPONSE_BYTES = 1_048_576;

    private CloudVisionClient() {
    }

    static String savedApiKey(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_API, "").trim();
    }

    static void saveApiKey(Context context, String apiKey) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_API, apiKey == null ? "" : apiKey.trim()).apply();
    }

    static String savedModel(Context context) {
        String model = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_MODEL, DEFAULT_MODEL);
        for (String supported : SUPPORTED_MODELS) {
            if (supported.equals(model)) {
                return model;
            }
        }
        return DEFAULT_MODEL;
    }

    static void saveModel(Context context, String model) {
        String chosen = DEFAULT_MODEL;
        for (String supported : SUPPORTED_MODELS) {
            if (supported.equals(model)) {
                chosen = supported;
                break;
            }
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_MODEL, chosen).apply();
    }

    static String validateModel(String model) {
        if (model == null || !model.matches("[a-zA-Z0-9._-]{3,64}")) {
            throw new IllegalArgumentException("Unsupported Gemini model identifier");
        }
        return model;
    }

    static String buildRequestJson(String prompt, String optionalBase64Jpeg) {
        if (prompt == null || prompt.isBlank()) {
            throw new IllegalArgumentException("Prompt is required");
        }
        List<Object> parts = new ArrayList<>();
        Map<String, Object> textPart = new LinkedHashMap<>();
        textPart.put("text", prompt.trim());
        parts.add(textPart);
        if (optionalBase64Jpeg != null && !optionalBase64Jpeg.isBlank()) {
            Map<String, Object> inlineData = new LinkedHashMap<>();
            inlineData.put("mime_type", "image/jpeg");
            inlineData.put("data", optionalBase64Jpeg);
            Map<String, Object> imagePart = new LinkedHashMap<>();
            imagePart.put("inline_data", inlineData);
            parts.add(imagePart);
        }
        Map<String, Object> content = new LinkedHashMap<>();
        content.put("parts", parts);
        List<Object> contents = new ArrayList<>();
        contents.add(content);
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("contents", contents);
        return MiniJson.stringify(root);
    }

    static String parseResponseText(String responseJson) {
        Map<String, Object> root = MiniJson.parseObject(responseJson);
        List<Object> candidates = MiniJson.asArray(root.get("candidates"));
        if (candidates == null || candidates.isEmpty()) {
            throw new IllegalArgumentException("No candidates returned by Gemini API");
        }
        Map<String, Object> first = MiniJson.asObject(candidates.get(0));
        Map<String, Object> content = MiniJson.asObject(first == null ? null : first.get("content"));
        List<Object> parts = MiniJson.asArray(content == null ? null : content.get("parts"));
        if (parts == null || parts.isEmpty()) {
            throw new IllegalArgumentException("Empty candidate response");
        }
        StringBuilder out = new StringBuilder();
        for (Object part : parts) {
            Map<String, Object> partMap = MiniJson.asObject(part);
            String text = MiniJson.asString(partMap, "text", "");
            if (!text.isEmpty()) {
                if (out.length() > 0) {
                    out.append('\n');
                }
                out.append(text);
            }
        }
        if (out.length() == 0) {
            throw new IllegalArgumentException("Candidate contained no text");
        }
        return out.toString().trim();
    }

    static String askText(String apiKey, String model, String prompt) throws IOException {
        return invoke(apiKey, model, buildRequestJson(prompt, null));
    }

    static String askVision(String apiKey, String model, String prompt, byte[] jpegBytes) throws IOException {
        if (jpegBytes == null || jpegBytes.length == 0) {
            throw new IOException("No captured frame is ready to send");
        }
        String base64 = Base64.getEncoder().encodeToString(jpegBytes);
        return invoke(apiKey, model, buildRequestJson(prompt, base64));
    }

    private static String invoke(String apiKey, String model, String jsonBody) throws IOException {
        if (apiKey == null || apiKey.trim().isEmpty()) {
            throw new IOException("No Gemini API key saved yet. Add yours in Eliza-GEM Studio or use Show Photo to Gemini.");
        }
        String safeModel = validateModel(model == null || model.isEmpty() ? DEFAULT_MODEL : model);
        URL url = new URL("https://generativelanguage.googleapis.com/v1beta/models/" + safeModel + ":generateContent");
        HttpURLConnection connection = (HttpURLConnection) url.openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(10_000);
            connection.setReadTimeout(25_000);
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(false);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setRequestProperty("Accept", "application/json");
            connection.setRequestProperty("x-goog-api-key", apiKey.trim());
            byte[] payload = jsonBody.getBytes(StandardCharsets.UTF_8);
            connection.setFixedLengthStreamingMode(payload.length);
            connection.getOutputStream().write(payload);

            int code = connection.getResponseCode();
            InputStream stream = code == 200 ? connection.getInputStream() : connection.getErrorStream();
            String response = readBounded(stream);
            if (code != 200) {
                String message = "Cloud Gemini HTTP " + code;
                try {
                    Map<String, Object> errRoot = MiniJson.parseObject(response);
                    Map<String, Object> errObj = MiniJson.asObject(errRoot.get("error"));
                    if (errObj != null) {
                        message = MiniJson.asString(errObj, "message", message);
                    }
                } catch (IllegalArgumentException ignored) {
                }
                throw new IOException(message);
            }
            return parseResponseText(response);
        } catch (IllegalArgumentException error) {
            throw new IOException("Invalid Cloud Gemini JSON: " + error.getMessage(), error);
        } finally {
            connection.disconnect();
        }
    }

    private static String readBounded(InputStream stream) throws IOException {
        if (stream == null) {
            throw new IOException("Empty response from Cloud Gemini");
        }
        try (InputStream in = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int total = 0;
            int n;
            while ((n = in.read(buf)) >= 0) {
                total += n;
                if (total > MAX_RESPONSE_BYTES) {
                    throw new IOException("Cloud response exceeded 1 MiB");
                }
                out.write(buf, 0, n);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }
}
