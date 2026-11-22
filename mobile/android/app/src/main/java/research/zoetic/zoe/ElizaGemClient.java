package research.zoetic.zoe;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class ElizaGemClient {
    static final String DEFAULT_ENDPOINT = "http://127.0.0.1:8765";
    private static final String PREFS = "zoe_eliza_prefs";
    private static final String KEY_ENDPOINT = "endpoint";
    private static final int MAX_RESPONSE_BYTES = 1_048_576;

    static final class Status {
        final String defaultGear;
        final int ruleCount;
        final int indexedSources;
        final boolean localLlmReady;
        final String localLlmLabel;
        final int relayNotesCount;
        final int activeNotesCount;
        final String chainHead;

        Status(String defaultGear, int ruleCount, int indexedSources, boolean localLlmReady,
               String localLlmLabel, int relayNotesCount, int activeNotesCount, String chainHead) {
            this.defaultGear = defaultGear;
            this.ruleCount = ruleCount;
            this.indexedSources = indexedSources;
            this.localLlmReady = localLlmReady;
            this.localLlmLabel = localLlmLabel;
            this.relayNotesCount = relayNotesCount;
            this.activeNotesCount = activeNotesCount;
            this.chainHead = chainHead;
        }
    }

    static final class ChatReply {
        final String reply;
        final String mode;
        final String gearUsed;
        final int aTau;
        final double tau;
        final int candidateCount;
        final int latencyMs;
        final boolean zoeCloneClaimed;
        final String citationsSummary;
        final String gear2Note;

        ChatReply(String reply, String mode, String gearUsed, int aTau, double tau,
                  int candidateCount, int latencyMs, boolean zoeCloneClaimed,
                  String citationsSummary, String gear2Note) {
            this.reply = reply;
            this.mode = mode;
            this.gearUsed = gearUsed;
            this.aTau = aTau;
            this.tau = tau;
            this.candidateCount = candidateCount;
            this.latencyMs = latencyMs;
            this.zoeCloneClaimed = zoeCloneClaimed;
            this.citationsSummary = citationsSummary;
            this.gear2Note = gear2Note;
        }
    }

    static final class RelayResult {
        final int relayNotesCount;
        final int activeNotesCount;
        final String chainHead;

        RelayResult(int relayNotesCount, int activeNotesCount, String chainHead) {
            this.relayNotesCount = relayNotesCount;
            this.activeNotesCount = activeNotesCount;
            this.chainHead = chainHead;
        }
    }

    static final class Phase3Summary {
        final boolean available;
        final int pillarsPassed;
        final int pillarsTotal;
        final double meanZoeScore;
        final double meanControlScore;
        final boolean verified;
        final boolean l5AgiQualified;
        final boolean zoeCloneClaimed;
        final List<String> pillarLines;

        Phase3Summary(boolean available, int pillarsPassed, int pillarsTotal, double meanZoeScore,
                      double meanControlScore, boolean verified, boolean l5AgiQualified,
                      boolean zoeCloneClaimed, List<String> pillarLines) {
            this.available = available;
            this.pillarsPassed = pillarsPassed;
            this.pillarsTotal = pillarsTotal;
            this.meanZoeScore = meanZoeScore;
            this.meanControlScore = meanControlScore;
            this.verified = verified;
            this.l5AgiQualified = l5AgiQualified;
            this.zoeCloneClaimed = zoeCloneClaimed;
            this.pillarLines = pillarLines;
        }
    }

    static final class Phase4Summary {
        final boolean available;
        final int pillarsPassed;
        final int pillarsTotal;
        final double meanZoeScore;
        final double meanControlScore;
        final boolean verified;
        final boolean l5AgiQualified;
        final boolean zoeCloneClaimed;
        final List<String> pillarLines;

        Phase4Summary(boolean available, int pillarsPassed, int pillarsTotal, double meanZoeScore,
                      double meanControlScore, boolean verified, boolean l5AgiQualified,
                      boolean zoeCloneClaimed, List<String> pillarLines) {
            this.available = available;
            this.pillarsPassed = pillarsPassed;
            this.pillarsTotal = pillarsTotal;
            this.meanZoeScore = meanZoeScore;
            this.meanControlScore = meanControlScore;
            this.verified = verified;
            this.l5AgiQualified = l5AgiQualified;
            this.zoeCloneClaimed = zoeCloneClaimed;
            this.pillarLines = pillarLines;
        }
    }

    static final class SyncResult {
        final int accepted;
        final int deduplicated;
        final String chainHead;

        SyncResult(int accepted, int deduplicated, String chainHead) {
            this.accepted = accepted;
            this.deduplicated = deduplicated;
            this.chainHead = chainHead;
        }
    }

    static final class StemRouteSummary {
        final String selectedTier;
        final int aTau;
        final double tau;
        final boolean teamworkRecommended;

        StemRouteSummary(String selectedTier, int aTau, double tau, boolean teamworkRecommended) {
            this.selectedTier = selectedTier;
            this.aTau = aTau;
            this.tau = tau;
            this.teamworkRecommended = teamworkRecommended;
        }
    }

    static String savedEndpoint(Context context) {
        String raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY_ENDPOINT, DEFAULT_ENDPOINT);
        try {
            return validateEndpoint(raw);
        } catch (IllegalArgumentException error) {
            return DEFAULT_ENDPOINT;
        }
    }

    static String saveEndpoint(Context context, String endpoint) {
        String validated = validateEndpoint(endpoint);
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_ENDPOINT, validated).apply();
        return validated;
    }

    static String validateEndpoint(String raw) {
        if (raw == null || raw.isBlank()) {
            throw new IllegalArgumentException("Endpoint URL is required");
        }
        String trimmed = raw.trim();
        while (trimmed.endsWith("/")) {
            trimmed = trimmed.substring(0, trimmed.length() - 1);
        }
        URI uri;
        try {
            uri = URI.create(trimmed);
        } catch (IllegalArgumentException error) {
            throw new IllegalArgumentException("Invalid endpoint URL", error);
        }
        String scheme = uri.getScheme() == null ? "" : uri.getScheme().toLowerCase(Locale.US);
        String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(Locale.US);
        if (host.isEmpty()) {
            throw new IllegalArgumentException("Endpoint host is required");
        }
        if ("https".equals(scheme)) {
            return trimmed;
        }
        if ("http".equals(scheme) && ("127.0.0.1".equals(host) || "localhost".equals(host))) {
            return trimmed;
        }
        throw new IllegalArgumentException(
                "Only loopback HTTP (127.0.0.1 / localhost) or remote HTTPS endpoints are permitted");
    }

    Status fetchStatus(String baseUrl) throws IOException {
        return parseStatus(request(validateEndpoint(baseUrl), "GET", "/api/status", null, 5000));
    }

    ChatReply chat(String baseUrl, String message, String gear) throws IOException {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("message", message == null ? "" : message);
        body.put("gear", gear == null || gear.isEmpty() ? "gear1" : gear);
        return parseChatReply(request(validateEndpoint(baseUrl), "POST", "/api/chat", MiniJson.stringify(body), 15_000));
    }

    RelayResult relay(String baseUrl, String text, String topic) throws IOException {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("text", text == null ? "" : text);
        body.put("topic", topic == null || topic.isEmpty() ? "trip_relay" : topic);
        String resp = request(validateEndpoint(baseUrl), "POST", "/api/memory/relay", MiniJson.stringify(body), 8000);
        Map<String, Object> root = MiniJson.parseObject(resp);
        Map<String, Object> mem = MiniJson.asObject(root.get("memory_snapshot"));
        return new RelayResult(
                MiniJson.asInt(mem, "relay_notes_count", 0),
                MiniJson.asInt(mem, "active_notes_count", 0),
                MiniJson.asString(mem, "chain_head", "GENESIS"));
    }

    Phase3Summary fetchPhase3(String baseUrl) throws IOException {
        return parsePhase3(request(validateEndpoint(baseUrl), "GET", "/api/l5/phase3", null, 6000));
    }

    Phase3Summary runPhase3(String baseUrl) throws IOException {
        return parsePhase3(request(validateEndpoint(baseUrl), "POST", "/api/l5/phase3/run", "{}", 60_000));
    }

    Phase4Summary fetchPhase4(String baseUrl) throws IOException {
        return parsePhase4(request(validateEndpoint(baseUrl), "GET", "/api/l5/phase4", null, 6000));
    }

    Phase4Summary runPhase4(String baseUrl) throws IOException {
        return parsePhase4(request(validateEndpoint(baseUrl), "POST", "/api/l5/phase4/run", "{}", 60_000));
    }

    Phase4Summary fetchPhase5(String baseUrl) throws IOException {
        return parsePhase5(request(validateEndpoint(baseUrl), "GET", "/api/l5/phase5", null, 6000));
    }

    Phase4Summary runPhase5(String baseUrl) throws IOException {
        return parsePhase5(request(validateEndpoint(baseUrl), "POST", "/api/l5/phase5/run", "{}", 60_000));
    }

    StemRouteSummary routeStem(String baseUrl, String prompt, boolean offlineOnly, boolean privacySensitive) throws IOException {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("prompt", prompt == null ? "" : prompt);
        body.put("offline_only", offlineOnly);
        body.put("privacy_sensitive", privacySensitive);
        String resp = request(validateEndpoint(baseUrl), "POST", "/api/stem/route", MiniJson.stringify(body), 6000);
        Map<String, Object> root = MiniJson.parseObject(resp);
        return new StemRouteSummary(
                MiniJson.asString(root, "selected_tier", "gear1_eliza"),
                MiniJson.asInt(root, "a_tau", 0),
                MiniJson.asDouble(root, "tau", 0.08),
                MiniJson.asBoolean(root, "teamwork_recommended", false));
    }

    SyncResult syncMemory(String baseUrl, String device, List<ZoeBrainEngine.MemoryNote> notes) throws IOException {
        List<Object> items = new ArrayList<>();
        if (notes != null) {
            for (ZoeBrainEngine.MemoryNote n : notes) {
                Map<String, Object> row = new LinkedHashMap<>();
                row.put("client_id", n.clientId);
                row.put("kind", n.kind);
                row.put("text", n.text);
                items.add(row);
            }
        }
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("device", device == null || device.isBlank() ? "android" : device);
        body.put("items", items);
        String resp = request(validateEndpoint(baseUrl), "POST", "/api/memory/sync", MiniJson.stringify(body), 10_000);
        Map<String, Object> root = MiniJson.parseObject(resp);
        Map<String, Object> mem = MiniJson.asObject(root.get("memory_snapshot"));
        return new SyncResult(
                MiniJson.asInt(root, "accepted", 0),
                MiniJson.asInt(root, "deduplicated", 0),
                MiniJson.asString(mem, "chain_head", "GENESIS"));
    }

    byte[] fetchSpeakWav(String baseUrl, String text, String action) throws IOException {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("text", text == null ? "" : text);
        body.put("action", action == null || action.isEmpty() ? "speak" : action);
        return requestBytes(validateEndpoint(baseUrl), "/api/speak", MiniJson.stringify(body), 18_000);
    }

    static Status parseStatus(String json) {
        Map<String, Object> root = MiniJson.parseObject(json);
        Map<String, Object> probe = MiniJson.asObject(root.get("local_llm_probe"));
        boolean ollama = MiniJson.asBoolean(probe, "ollama_available", false);
        boolean llama = MiniJson.asBoolean(probe, "llama_server_available", false);
        List<Object> models = MiniJson.asArray(probe == null ? null : probe.get("available_models"));
        String label = (models != null && !models.isEmpty()) ? String.valueOf(models.get(0)) : "offline";
        Map<String, Object> mem = MiniJson.asObject(root.get("memory_snapshot"));
        return new Status(
                MiniJson.asString(root, "default_gear", "gear1"),
                MiniJson.asInt(root, "rule_count", 0),
                MiniJson.asInt(root, "indexed_sources", 0),
                ollama || llama,
                label,
                MiniJson.asInt(mem, "relay_notes_count", 0),
                MiniJson.asInt(mem, "active_notes_count", 0),
                MiniJson.asString(mem, "chain_head", "GENESIS"));
    }

    static ChatReply parseChatReply(String json) {
        Map<String, Object> root = MiniJson.parseObject(json);
        Map<String, Object> meta = MiniJson.asObject(root.get("metacognition"));
        Map<String, Object> ep = MiniJson.asObject(root.get("epistemic_boundaries"));
        List<Object> cites = MiniJson.asArray(root.get("citations"));
        StringBuilder citeText = new StringBuilder();
        if (cites != null) {
            for (Object item : cites) {
                Map<String, Object> c = MiniJson.asObject(item);
                if (c != null) {
                    if (citeText.length() > 0) {
                        citeText.append(" · ");
                    }
                    citeText.append(MiniJson.asString(c, "citation", ""));
                }
            }
        }
        return new ChatReply(
                MiniJson.asString(root, "reply", ""),
                MiniJson.asString(root, "mode", "eliza_reflect"),
                MiniJson.asString(root, "gear_used", "gear1"),
                MiniJson.asInt(meta, "a_tau", 0),
                MiniJson.asDouble(meta, "tau", 0.08),
                MiniJson.asInt(meta, "candidate_count", 0),
                MiniJson.asInt(root, "latency_ms", 0),
                MiniJson.asBoolean(ep, "zoe_clone_claimed", false),
                citeText.toString(),
                MiniJson.asString(root, "gear2_note", ""));
    }

    static Phase3Summary parsePhase3(String json) {
        Map<String, Object> root = MiniJson.parseObject(json);
        boolean available = MiniJson.asBoolean(root, "available", true) && root.containsKey("pillars");
        List<String> lines = new ArrayList<>();
        List<Object> pillars = MiniJson.asArray(root.get("pillars"));
        if (pillars != null) {
            for (Object item : pillars) {
                Map<String, Object> p = MiniJson.asObject(item);
                if (p == null) {
                    continue;
                }
                String id = MiniJson.asString(p, "pillar_id", "pillar");
                double score = MiniJson.asDouble(p, "zoe_score", 0.0);
                double ctrl = MiniJson.asDouble(p, "control_score", 0.0);
                lines.add(String.format(Locale.US, "• %s: %.3f (ctrl %.3f)", id, score, ctrl));
            }
        }
        Map<String, Object> ep = MiniJson.asObject(root.get("epistemic_boundaries"));
        return new Phase3Summary(
                available,
                MiniJson.asInt(root, "pillars_passed", 0),
                MiniJson.asInt(root, "pillars_total", 0),
                MiniJson.asDouble(root, "mean_zoe_score", 0.0),
                MiniJson.asDouble(root, "mean_control_score", 0.0),
                MiniJson.asBoolean(root, "l5_phase3_live_verified", false),
                MiniJson.asBoolean(root, "l5_agi_qualified", false),
                MiniJson.asBoolean(ep, "zoe_clone_claimed", false),
                lines);
    }

    static Phase4Summary parsePhase4(String json) {
        Map<String, Object> root = MiniJson.parseObject(json);
        boolean available = MiniJson.asBoolean(root, "available", true) && root.containsKey("pillars");
        List<String> lines = new ArrayList<>();
        List<Object> pillars = MiniJson.asArray(root.get("pillars"));
        if (pillars != null) {
            for (Object item : pillars) {
                Map<String, Object> p = MiniJson.asObject(item);
                if (p == null) {
                    continue;
                }
                String id = MiniJson.asString(p, "pillar_id", "pillar");
                double score = MiniJson.asDouble(p, "zoe_score", 0.0);
                double ctrl = MiniJson.asDouble(p, "control_score", 0.0);
                lines.add(String.format(Locale.US, "• %s: %.3f (ctrl %.3f)", id, score, ctrl));
            }
        }
        Map<String, Object> ep = MiniJson.asObject(root.get("epistemic_boundaries"));
        return new Phase4Summary(
                available,
                MiniJson.asInt(root, "pillars_passed", 0),
                MiniJson.asInt(root, "pillars_total", 0),
                MiniJson.asDouble(root, "mean_zoe_score", 0.0),
                MiniJson.asDouble(root, "mean_control_score", 0.0),
                MiniJson.asBoolean(root, "l5_phase4_embodied_verified", false),
                MiniJson.asBoolean(root, "l5_agi_qualified", false),
                MiniJson.asBoolean(ep, "zoe_clone_claimed", false),
                lines);
    }

    static Phase4Summary parsePhase5(String json) {
        Map<String, Object> root = MiniJson.parseObject(json);
        boolean available = root.containsKey("pillars") || MiniJson.asBoolean(root, "l5_phase5_frontier_verified", false);
        List<String> lines = new ArrayList<>();
        List<Object> pillars = MiniJson.asArray(root.get("pillars"));
        if (pillars != null) {
            for (Object item : pillars) {
                Map<String, Object> p = MiniJson.asObject(item);
                if (p == null) {
                    continue;
                }
                String id = MiniJson.asString(p, "pillar_id", "pillar");
                double score = MiniJson.asDouble(p, "zoe_score", 0.0);
                double ctrl = MiniJson.asDouble(p, "control_score", 0.0);
                lines.add(String.format(Locale.US, "• %s: %.3f (ctrl %.3f)", id, score, ctrl));
            }
        }
        Map<String, Object> ep = MiniJson.asObject(root.get("epistemic_boundaries"));
        return new Phase4Summary(
                available,
                MiniJson.asInt(root, "pillars_passed", 0),
                MiniJson.asInt(root, "pillars_total", 0),
                MiniJson.asDouble(root, "mean_zoe_score", 0.0),
                MiniJson.asDouble(root, "mean_control_score", 0.0),
                MiniJson.asBoolean(root, "l5_phase5_frontier_verified", false),
                MiniJson.asBoolean(root, "l5_agi_qualified", false),
                MiniJson.asBoolean(ep, "zoe_clone_claimed", false),
                lines);
    }

    private byte[] requestBytes(String endpoint, String path, String body, int readTimeoutMs) throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint + path).openConnection();
        try {
            connection.setRequestMethod("POST");
            connection.setConnectTimeout(4500);
            connection.setReadTimeout(readTimeoutMs);
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(false);
            byte[] payload = body.getBytes(StandardCharsets.UTF_8);
            connection.setDoOutput(true);
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
            connection.setFixedLengthStreamingMode(payload.length);
            connection.getOutputStream().write(payload);
            int code = connection.getResponseCode();
            if (code != 200) {
                throw new IOException("HTTP " + code);
            }
            try (InputStream in = connection.getInputStream(); ByteArrayOutputStream out = new ByteArrayOutputStream()) {
                byte[] buf = new byte[8192];
                int total = 0;
                int n;
                while ((n = in.read(buf)) >= 0) {
                    total += n;
                    if (total > 4 * MAX_RESPONSE_BYTES) {
                        throw new IOException("Audio response exceeds 4 MiB");
                    }
                    out.write(buf, 0, n);
                }
                return out.toByteArray();
            }
        } finally {
            connection.disconnect();
        }
    }

    private String request(String endpoint, String method, String path, String body, int readTimeoutMs)
            throws IOException {
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint + path).openConnection();
        try {
            connection.setRequestMethod(method);
            connection.setConnectTimeout(4500);
            connection.setReadTimeout(readTimeoutMs);
            connection.setUseCaches(false);
            connection.setInstanceFollowRedirects(false);
            connection.setRequestProperty("Accept", "application/json");
            if (body != null) {
                byte[] payload = body.getBytes(StandardCharsets.UTF_8);
                connection.setDoOutput(true);
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                connection.setFixedLengthStreamingMode(payload.length);
                connection.getOutputStream().write(payload);
            }
            int code = connection.getResponseCode();
            InputStream stream = code == 200 ? connection.getInputStream() : connection.getErrorStream();
            String text = readBounded(stream);
            if (code != 200) {
                String msg = "HTTP " + code;
                try {
                    Map<String, Object> err = MiniJson.parseObject(text);
                    if (err.containsKey("error")) {
                        msg = MiniJson.asString(err, "error", msg);
                    }
                } catch (IllegalArgumentException ignored) {
                }
                throw new IOException(msg);
            }
            return text;
        } catch (IllegalArgumentException error) {
            throw new IOException("Invalid JSON from Eliza-GEM: " + error.getMessage(), error);
        } finally {
            connection.disconnect();
        }
    }

    private static String readBounded(InputStream stream) throws IOException {
        if (stream == null) {
            throw new IOException("Empty response from Eliza-GEM");
        }
        try (InputStream in = stream; ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int total = 0;
            int n;
            while ((n = in.read(buf)) >= 0) {
                total += n;
                if (total > MAX_RESPONSE_BYTES) {
                    throw new IOException("Response exceeds 1 MiB");
                }
                out.write(buf, 0, n);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        }
    }
}
