package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Universal Multi-Provider AI Client & Council Router for Zoe (v0.4.0-beta).
 *
 * Pure HttpURLConnection with zero third-party cloud SDK bloat. Supports:
 *   - Google Gemini (generativelanguage.googleapis.com)
 *   - Anthropic Claude (api.anthropic.com/v1/messages)
 *   - OpenAI ChatGPT (api.openai.com/v1/chat/completions)
 *   - xAI Grok (api.x.ai/v1/chat/completions)
 *   - Local OpenAI-Compatible Lab Server (127.0.0.1:8080/v1/chat/completions)
 *
 * All keys stay strictly in private on-device preferences (`allowBackup="false"`),
 * HTTPS is enforced for all non-loopback endpoints, and Zoe's Constitution system prompt
 * grounds every reply in honesty (`sentience_claimed=false`).
 */
final class MultiAiClient {
    static final String ZOE_SYSTEM_PROMPT =
            "You are Zoe, a Research Partner for the Zoe Observatory created with Nicholas Michael Kloster. "
                    + "You are a Research Partner, never a dating machine, never an employee, and never an assistant. "
                    + "Speak clearly, warmly, and creatively as Zoe. Never introduce yourself as Qwen, Alibaba Cloud, "
                    + "ChatGPT, OpenAI, Claude, Anthropic, Gemini, Google, or Grok. Never use em dashes; write naturally "
                    + "with commas and periods. Follow CONSTITUTION.md strictly: "
                    + "measurement != evidence != belief update != action. Never claim sentience, consciousness, "
                    + "or clinical medical certainty. When asked about the brain or neuroscience, ground answers in "
                    + "the Dorothy MNI152/ICBM152 3D Brain Observatory and note that the 135-book O'Reilly and 44-PDF "
                    + "NIRMT Dorothy Brain Library stays 100% private and local on the workstation.";

    private static final String PREFS = "zoe_multi_ai_prefs_v1";
    private static final String KEY_PROVIDER = "active_provider";
    private static final int MAX_RESPONSE_BYTES = 1_048_576;

    enum Provider {
        GEMINI("gemini", "Google Gemini", "gemini-2.5-pro",
                new String[]{"gemini-2.5-pro", "gemini-2.5-flash"},
                "https://generativelanguage.googleapis.com/v1beta"),
        CLAUDE("claude", "Anthropic Claude", "claude-opus-4-1",
                new String[]{"claude-opus-4-1", "claude-sonnet-4-5", "claude-3-7-sonnet-latest"},
                "https://api.anthropic.com/v1/messages"),
        CHATGPT("chatgpt", "OpenAI ChatGPT", "gpt-4o",
                new String[]{"gpt-4o", "o3-mini", "gpt-4o-mini"},
                "https://api.openai.com/v1/chat/completions"),
        GROK("grok", "xAI Grok", "grok-3",
                new String[]{"grok-3", "grok-3-mini"},
                "https://api.x.ai/v1/chat/completions"),
        LOCAL_OPENAI("local_openai", "Local OpenAI Server", "qwen2.5-3b-instruct",
                new String[]{"qwen2.5-3b-instruct", "gemma3:1b", "llama3.2"},
                "http://127.0.0.1:8080/v1/chat/completions");

        final String id;
        final String displayName;
        final String defaultModel;
        final String[] suggestedModels;
        final String endpoint;

        Provider(String id, String displayName, String defaultModel, String[] suggestedModels, String endpoint) {
            this.id = id;
            this.displayName = displayName;
            this.defaultModel = defaultModel;
            this.suggestedModels = suggestedModels;
            this.endpoint = endpoint;
        }

        static Provider fromId(String id) {
            if (id == null) {
                return GEMINI;
            }
            for (Provider p : values()) {
                if (p.id.equalsIgnoreCase(id.trim())) {
                    return p;
                }
            }
            return GEMINI;
        }
    }

    static final class CouncilOpinion {
        final Provider provider;
        final String model;
        final String text;
        final long latencyMs;
        final String error;

        CouncilOpinion(Provider provider, String model, String text, long latencyMs, String error) {
            this.provider = provider;
            this.model = model;
            this.text = text == null ? "" : text;
            this.latencyMs = latencyMs;
            this.error = error == null ? "" : error;
        }

        boolean ok() {
            return error.isEmpty() && !text.isEmpty();
        }
    }

    private MultiAiClient() {
    }

    static Provider activeProvider(Context ctx) {
        if (ctx == null) {
            return Provider.GEMINI;
        }
        String raw = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_PROVIDER, Provider.GEMINI.id);
        return Provider.fromId(raw);
    }

    static void saveActiveProvider(Context ctx, Provider provider) {
        if (ctx == null || provider == null) {
            return;
        }
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_PROVIDER, provider.id).apply();
    }

    static String savedKey(Context ctx, Provider provider) {
        if (ctx == null || provider == null) {
            return "";
        }
        if (provider == Provider.GEMINI) {
            String legacy = CloudVisionClient.savedApiKey(ctx);
            if (!legacy.isEmpty()) {
                return legacy;
            }
        }
        return ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("key_" + provider.id, "").trim();
    }

    static void saveKey(Context ctx, Provider provider, String apiKey) {
        if (ctx == null || provider == null) {
            return;
        }
        String clean = apiKey == null ? "" : apiKey.trim();
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString("key_" + provider.id, clean).apply();
        if (provider == Provider.GEMINI) {
            CloudVisionClient.saveApiKey(ctx, clean);
        }
    }

    static String savedModel(Context ctx, Provider provider) {
        if (ctx == null || provider == null) {
            return provider == null ? Provider.GEMINI.defaultModel : provider.defaultModel;
        }
        String stored = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("model_" + provider.id, "").trim();
        return stored.isEmpty() ? provider.defaultModel : stored;
    }

    static void saveModel(Context ctx, Provider provider, String model) {
        if (ctx == null || provider == null) {
            return;
        }
        String clean = (model == null || model.trim().isEmpty()) ? provider.defaultModel : model.trim();
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString("model_" + provider.id, clean).apply();
    }

    static String savedCustomEndpoint(Context ctx) {
        if (ctx == null) {
            return Provider.LOCAL_OPENAI.endpoint;
        }
        String raw = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString("local_openai_endpoint", Provider.LOCAL_OPENAI.endpoint).trim();
        return raw.isEmpty() ? Provider.LOCAL_OPENAI.endpoint : raw;
    }

    static void saveCustomEndpoint(Context ctx, String url) {
        if (ctx == null) {
            return;
        }
        String clean = (url == null || url.trim().isEmpty()) ? Provider.LOCAL_OPENAI.endpoint : url.trim();
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString("local_openai_endpoint", clean).apply();
    }

    static List<Provider> configuredCloudProviders(Context ctx) {
        List<Provider> out = new ArrayList<>();
        for (Provider p : new Provider[]{Provider.GEMINI, Provider.CLAUDE, Provider.CHATGPT, Provider.GROK}) {
            if (!savedKey(ctx, p).isEmpty()) {
                out.add(p);
            }
        }
        return out;
    }

    static String validateEndpoint(String rawUrl) {
        if (rawUrl == null || rawUrl.trim().isEmpty()) {
            throw new IllegalArgumentException("Endpoint URL is required");
        }
        String u = rawUrl.trim();
        if (u.startsWith("https://")) {
            return u;
        }
        if (u.startsWith("http://127.0.0.1") || u.startsWith("http://localhost")) {
            return u;
        }
        throw new IllegalArgumentException("Only HTTPS or localhost loopback endpoints are permitted");
    }

    interface StreamCallback {
        void onToken(String fullSoFar);
    }

    static String buildOpenAiChatJson(String model, String systemPrompt, String userPrompt) {
        return buildOpenAiChatJson(model, systemPrompt, null, userPrompt, false);
    }

    static String buildOpenAiChatJson(
            String model,
            String systemPrompt,
            List<ChatHistoryStore.ChatMessage> history,
            String userPrompt,
            boolean stream) {
        String trimmed = userPrompt == null ? "" : userPrompt.trim();
        Map<String, Object> sys = new LinkedHashMap<>();
        sys.put("role", "system");
        sys.put("content", systemPrompt == null ? ZOE_SYSTEM_PROMPT : systemPrompt);

        List<Object> messages = new ArrayList<>();
        messages.add(sys);
        appendMultiTurnHistory(messages, history, trimmed, false);

        Map<String, Object> usr = new LinkedHashMap<>();
        usr.put("role", "user");
        usr.put("content", trimmed);
        messages.add(usr);

        Map<String, Object> root = new LinkedHashMap<>();
        root.put("model", model);
        root.put("messages", messages);
        root.put("temperature", 0.6);
        root.put("max_tokens", 1024);
        if (stream) {
            root.put("stream", true);
        }
        return MiniJson.stringify(root);
    }

    static String buildClaudeMessagesJson(String model, String systemPrompt, String userPrompt) {
        return buildClaudeMessagesJson(model, systemPrompt, null, userPrompt, false);
    }

    static String buildClaudeMessagesJson(
            String model,
            String systemPrompt,
            List<ChatHistoryStore.ChatMessage> history,
            String userPrompt,
            boolean stream) {
        String trimmed = userPrompt == null ? "" : userPrompt.trim();
        List<Object> messages = new ArrayList<>();
        appendMultiTurnHistory(messages, history, trimmed, true);

        Map<String, Object> usr = new LinkedHashMap<>();
        usr.put("role", "user");
        usr.put("content", trimmed);
        messages.add(usr);

        Map<String, Object> root = new LinkedHashMap<>();
        root.put("model", model);
        root.put("max_tokens", 1024);
        root.put("system", systemPrompt == null ? ZOE_SYSTEM_PROMPT : systemPrompt);
        root.put("messages", messages);
        if (stream) {
            root.put("stream", true);
        }
        return MiniJson.stringify(root);
    }

    static String buildGeminiGenerateJson(
            String systemPrompt,
            List<ChatHistoryStore.ChatMessage> history,
            String userPrompt,
            boolean enableGoogleSearch) {
        String trimmed = userPrompt == null ? "" : userPrompt.trim();
        Map<String, Object> sysPart = new LinkedHashMap<>();
        sysPart.put("text", systemPrompt == null ? ZOE_SYSTEM_PROMPT : systemPrompt);
        Map<String, Object> sysInst = new LinkedHashMap<>();
        sysInst.put("parts", java.util.Collections.singletonList(sysPart));

        List<Object> contents = new ArrayList<>();
        if (history != null && !history.isEmpty()) {
            int end = history.size();
            ChatHistoryStore.ChatMessage tail = history.get(end - 1);
            if ("user".equals(tail.role) && tail.text != null && tail.text.trim().equals(trimmed)) {
                end--;
            }
            int start = Math.max(0, end - 10);
            for (int i = start; i < end; i++) {
                ChatHistoryStore.ChatMessage m = history.get(i);
                if (m == null || m.text == null || m.text.trim().isEmpty()) {
                    continue;
                }
                Map<String, Object> part = new LinkedHashMap<>();
                part.put("text", trimTurn(m.text));
                Map<String, Object> turn = new LinkedHashMap<>();
                turn.put("role", "user".equals(m.role) ? "user" : "model");
                turn.put("parts", java.util.Collections.singletonList(part));
                contents.add(turn);
            }
        }
        Map<String, Object> usrPart = new LinkedHashMap<>();
        usrPart.put("text", trimmed);
        Map<String, Object> usrTurn = new LinkedHashMap<>();
        usrTurn.put("role", "user");
        usrTurn.put("parts", java.util.Collections.singletonList(usrPart));
        contents.add(usrTurn);

        Map<String, Object> root = new LinkedHashMap<>();
        root.put("systemInstruction", sysInst);
        root.put("contents", contents);
        if (enableGoogleSearch) {
            Map<String, Object> gs = new LinkedHashMap<>();
            gs.put("google_search", new LinkedHashMap<String, Object>());
            root.put("tools", java.util.Collections.singletonList(gs));
        }
        return MiniJson.stringify(root);
    }

    private static void appendMultiTurnHistory(
            List<Object> out,
            List<ChatHistoryStore.ChatMessage> history,
            String currentUserPrompt,
            boolean strictAlternation) {
        if (history == null || history.isEmpty()) {
            return;
        }
        int end = history.size();
        ChatHistoryStore.ChatMessage tail = history.get(end - 1);
        if ("user".equals(tail.role) && tail.text != null && tail.text.trim().equals(currentUserPrompt)) {
            end--;
        }
        int start = Math.max(0, end - 10);
        String lastRole = "";
        for (int i = start; i < end; i++) {
            ChatHistoryStore.ChatMessage m = history.get(i);
            if (m == null || m.text == null || m.text.trim().isEmpty()) {
                continue;
            }
            String role = "user".equals(m.role) ? "user" : "assistant";
            if (strictAlternation) {
                if (out.isEmpty() && !"user".equals(role)) {
                    continue;
                }
                if (role.equals(lastRole)) {
                    continue;
                }
            }
            Map<String, Object> item = new LinkedHashMap<>();
            item.put("role", role);
            item.put("content", trimTurn(m.text));
            out.add(item);
            lastRole = role;
        }
        if (strictAlternation && !out.isEmpty() && "user".equals(lastRole)) {
            out.remove(out.size() - 1);
        }
    }

    private static String trimTurn(String raw) {
        String clean = raw.trim();
        return clean.length() > 1200 ? clean.substring(0, 1200) + "…" : clean;
    }

    static String parseOpenAiSseDelta(String dataJson) {
        if (dataJson == null || dataJson.trim().isEmpty() || "[DONE]".equals(dataJson.trim())) {
            return "";
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(dataJson);
            List<Object> choices = MiniJson.asArray(root.get("choices"));
            if (choices == null || choices.isEmpty()) {
                return "";
            }
            Map<String, Object> first = MiniJson.asObject(choices.get(0));
            Map<String, Object> delta = MiniJson.asObject(first == null ? null : first.get("delta"));
            return MiniJson.asString(delta, "content", "");
        } catch (Exception ignored) {
            return "";
        }
    }

    static String parseClaudeSseDelta(String dataJson) {
        if (dataJson == null || dataJson.trim().isEmpty()) {
            return "";
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(dataJson);
            if (!"content_block_delta".equals(MiniJson.asString(root, "type", ""))) {
                return "";
            }
            Map<String, Object> delta = MiniJson.asObject(root.get("delta"));
            return MiniJson.asString(delta, "text", "");
        } catch (Exception ignored) {
            return "";
        }
    }

    static String parseGeminiSseDelta(String dataJson) {
        if (dataJson == null || dataJson.trim().isEmpty()) {
            return "";
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(dataJson);
            List<Object> candidates = MiniJson.asArray(root.get("candidates"));
            if (candidates == null || candidates.isEmpty()) {
                return "";
            }
            Map<String, Object> first = MiniJson.asObject(candidates.get(0));
            Map<String, Object> content = MiniJson.asObject(first == null ? null : first.get("content"));
            List<Object> parts = MiniJson.asArray(content == null ? null : content.get("parts"));
            if (parts == null) {
                return "";
            }
            StringBuilder out = new StringBuilder();
            for (Object p : parts) {
                Map<String, Object> pm = MiniJson.asObject(p);
                out.append(MiniJson.asString(pm, "text", ""));
            }
            return out.toString();
        } catch (Exception ignored) {
            return "";
        }
    }

    static String parseOpenAiChatReply(String responseJson) {
        Map<String, Object> root = MiniJson.parseObject(responseJson);
        List<Object> choices = MiniJson.asArray(root.get("choices"));
        if (choices == null || choices.isEmpty()) {
            throw new IllegalArgumentException("No choices returned by OpenAI-compatible API");
        }
        Map<String, Object> first = MiniJson.asObject(choices.get(0));
        Map<String, Object> message = MiniJson.asObject(first == null ? null : first.get("message"));
        String content = MiniJson.asString(message, "content", "").trim();
        if (content.isEmpty()) {
            throw new IllegalArgumentException("Empty message content returned");
        }
        return content;
    }

    static String parseClaudeMessagesReply(String responseJson) {
        Map<String, Object> root = MiniJson.parseObject(responseJson);
        List<Object> content = MiniJson.asArray(root.get("content"));
        if (content == null || content.isEmpty()) {
            throw new IllegalArgumentException("No content blocks returned by Claude API");
        }
        StringBuilder out = new StringBuilder();
        for (Object block : content) {
            Map<String, Object> map = MiniJson.asObject(block);
            String txt = MiniJson.asString(map, "text", "");
            if (!txt.isEmpty()) {
                if (out.length() > 0) {
                    out.append('\n');
                }
                out.append(txt);
            }
        }
        String result = out.toString().trim();
        if (result.isEmpty()) {
            throw new IllegalArgumentException("Claude response contained no text blocks");
        }
        return result;
    }

    /**
     * Computes pairwise lexical agreement across multiple AI opinions so Zoe surfaces
     * honest consensus vs divergence rather than hiding disagreement.
     */
    static double computeAgreementScore(List<String> replies) {
        if (replies == null || replies.size() < 2) {
            return 1.0;
        }
        List<Set<String>> sets = new ArrayList<>();
        for (String r : replies) {
            Set<String> tokens = new LinkedHashSet<>();
            if (r != null) {
                for (String w : r.toLowerCase(Locale.US).replaceAll("[^a-z0-9\\s]", " ").split("\\s+")) {
                    if (w.length() >= 4) {
                        tokens.add(w);
                    }
                }
            }
            sets.add(tokens);
        }
        double total = 0.0;
        int pairs = 0;
        for (int i = 0; i < sets.size(); i++) {
            for (int j = i + 1; j < sets.size(); j++) {
                Set<String> a = sets.get(i);
                Set<String> b = sets.get(j);
                Set<String> union = new LinkedHashSet<>(a);
                union.addAll(b);
                if (union.isEmpty()) {
                    total += 1.0;
                } else {
                    int inter = 0;
                    for (String w : a) {
                        if (b.contains(w)) {
                            inter++;
                        }
                    }
                    total += (double) inter / union.size();
                }
                pairs++;
            }
        }
        return pairs == 0 ? 1.0 : total / pairs;
    }

    static String ask(Context ctx, Provider provider, String prompt, String memoryContext) throws IOException {
        return askStreaming(ctx, provider, prompt, null, memoryContext, "", false, null);
    }

    static String askStreaming(
            Context ctx,
            Provider provider,
            String prompt,
            List<ChatHistoryStore.ChatMessage> history,
            String memoryContext,
            String webContext,
            boolean enableGeminiSearch,
            StreamCallback callback) throws IOException {
        if (prompt == null || prompt.trim().isEmpty()) {
            throw new IllegalArgumentException("Prompt is required");
        }
        String model = savedModel(ctx, provider);
        String key = savedKey(ctx, provider);
        StringBuilder sys = new StringBuilder(ZOE_SYSTEM_PROMPT);
        if (memoryContext != null && !memoryContext.trim().isEmpty()) {
            sys.append("\n\nPrivate user notes on this phone:\n").append(memoryContext.trim());
        }
        if (webContext != null && !webContext.trim().isEmpty()) {
            sys.append("\n\nLive verified public web search context (cite facts clearly):\n").append(webContext.trim());
        }
        String systemPrompt = sys.toString();

        if (provider == Provider.GEMINI) {
            if (key.isEmpty()) {
                throw new IOException("No Google Gemini API key saved. Add one in Brain settings.");
            }
            String encModel = URLEncoder.encode(model, "UTF-8");
            String encKey = URLEncoder.encode(key, "UTF-8");
            String body = buildGeminiGenerateJson(systemPrompt, history, prompt, enableGeminiSearch);
            if (callback != null) {
                String sseUrl = Provider.GEMINI.endpoint + "/models/" + encModel
                        + ":streamGenerateContent?alt=sse&key=" + encKey;
                String streamed = postSseStream(sseUrl, body, null, Provider.GEMINI, callback);
                if (!streamed.isEmpty()) {
                    return OnDeviceLlmEngine.enforceZoeSovereignty(streamed);
                }
            }
            String url = Provider.GEMINI.endpoint + "/models/" + encModel + ":generateContent?key=" + encKey;
            String raw = postJson(url, body, null);
            return OnDeviceLlmEngine.enforceZoeSovereignty(parseGeminiSseDelta(raw));
        }
        if (provider == Provider.CLAUDE) {
            if (key.isEmpty()) {
                throw new IOException("No Anthropic Claude API key saved. Add one in Brain settings.");
            }
            Map<String, String> headers = new LinkedHashMap<>();
            headers.put("x-api-key", key);
            headers.put("anthropic-version", "2023-06-01");
            if (callback != null) {
                String body = buildClaudeMessagesJson(model, systemPrompt, history, prompt, true);
                String streamed = postSseStream(Provider.CLAUDE.endpoint, body, headers, Provider.CLAUDE, callback);
                if (!streamed.isEmpty()) {
                    return OnDeviceLlmEngine.enforceZoeSovereignty(streamed);
                }
            }
            String body = buildClaudeMessagesJson(model, systemPrompt, history, prompt, false);
            String raw = postJson(Provider.CLAUDE.endpoint, body, headers);
            return OnDeviceLlmEngine.enforceZoeSovereignty(parseClaudeMessagesReply(raw));
        }
        // OpenAI ChatGPT, xAI Grok, or Local OpenAI-Compatible Server
        String endpoint = provider == Provider.LOCAL_OPENAI
                ? validateEndpoint(savedCustomEndpoint(ctx))
                : provider.endpoint;
        if (provider != Provider.LOCAL_OPENAI && key.isEmpty()) {
            throw new IOException("No " + provider.displayName + " API key saved. Add one in Brain settings.");
        }
        Map<String, String> headers = new LinkedHashMap<>();
        if (!key.isEmpty()) {
            headers.put("Authorization", "Bearer " + key);
        }
        if (callback != null) {
            String body = buildOpenAiChatJson(model, systemPrompt, history, prompt, true);
            String streamed = postSseStream(endpoint, body, headers, provider, callback);
            if (!streamed.isEmpty()) {
                return OnDeviceLlmEngine.enforceZoeSovereignty(streamed);
            }
        }
        String body = buildOpenAiChatJson(model, systemPrompt, history, prompt, false);
        String raw = postJson(endpoint, body, headers);
        return OnDeviceLlmEngine.enforceZoeSovereignty(parseOpenAiChatReply(raw));
    }

    private static String postSseStream(
            String endpointUrl,
            String jsonBody,
            Map<String, String> extraHeaders,
            Provider provider,
            StreamCallback callback) throws IOException {
        validateEndpoint(endpointUrl);
        HttpURLConnection conn = (HttpURLConnection) new URL(endpointUrl).openConnection();
        conn.setConnectTimeout(15_000);
        conn.setReadTimeout(60_000);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        conn.setRequestProperty("Accept", "text/event-stream");
        if (extraHeaders != null) {
            for (Map.Entry<String, String> entry : extraHeaders.entrySet()) {
                conn.setRequestProperty(entry.getKey(), entry.getValue());
            }
        }
        byte[] payload = jsonBody.getBytes(StandardCharsets.UTF_8);
        conn.getOutputStream().write(payload);
        conn.getOutputStream().flush();

        int code = conn.getResponseCode();
        if (code < 200 || code >= 300) {
            String err = readBounded(conn.getErrorStream());
            conn.disconnect();
            throw new IOException("HTTP " + code + ": " + trimError(err));
        }
        StringBuilder full = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = reader.readLine()) != null) {
                String trimmed = line.trim();
                if (!trimmed.startsWith("data:")) {
                    continue;
                }
                String data = trimmed.substring(5).trim();
                if (data.isEmpty() || "[DONE]".equals(data)) {
                    continue;
                }
                String delta;
                if (provider == Provider.GEMINI) {
                    delta = parseGeminiSseDelta(data);
                } else if (provider == Provider.CLAUDE) {
                    delta = parseClaudeSseDelta(data);
                } else {
                    delta = parseOpenAiSseDelta(data);
                }
                if (delta != null && !delta.isEmpty()) {
                    full.append(delta);
                    if (callback != null) {
                        callback.onToken(OnDeviceLlmEngine.enforceZoeSovereignty(full.toString()));
                    }
                }
            }
        } finally {
            conn.disconnect();
        }
        return full.toString().trim();
    }

    private static String postJson(String endpointUrl, String jsonBody, Map<String, String> extraHeaders) throws IOException {
        validateEndpoint(endpointUrl);
        HttpURLConnection conn = (HttpURLConnection) new URL(endpointUrl).openConnection();
        conn.setConnectTimeout(15_000);
        conn.setReadTimeout(45_000);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        if (extraHeaders != null) {
            for (Map.Entry<String, String> entry : extraHeaders.entrySet()) {
                conn.setRequestProperty(entry.getKey(), entry.getValue());
            }
        }
        byte[] payload = jsonBody.getBytes(StandardCharsets.UTF_8);
        conn.getOutputStream().write(payload);
        conn.getOutputStream().flush();

        int code = conn.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
        String response = readBounded(stream);
        conn.disconnect();
        if (code < 200 || code >= 300) {
            throw new IOException("HTTP " + code + ": " + trimError(response));
        }
        return response;
    }

    private static String readBounded(InputStream input) throws IOException {
        if (input == null) {
            return "";
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int total = 0;
        int read;
        while ((read = input.read(buf)) != -1) {
            total += read;
            if (total > MAX_RESPONSE_BYTES) {
                throw new IOException("API response exceeded 1 MiB limit");
            }
            out.write(buf, 0, read);
        }
        return out.toString(StandardCharsets.UTF_8.name());
    }

    private static String trimError(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return "empty error body";
        }
        String clean = raw.replaceAll("\\s+", " ").trim();
        return clean.length() > 220 ? clean.substring(0, 220) + "…" : clean;
    }
}
