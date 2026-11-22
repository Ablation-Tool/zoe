package research.zoetic.zoe;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Private on-device multi-thread chat history store for Zoe (v0.4.0-beta).
 * Stored strictly inside app-private files (`allowBackup="false"`), never uploaded automatically.
 */
final class ChatHistoryStore {
    private static final String FILE_NAME = "zoe_chat_threads_v1.json";
    static final int MAX_THREADS = 24;
    static final int MAX_MESSAGES_PER_THREAD = 60;

    static final class ChatMessage {
        final String role;       // "user" or "zoe"
        final String text;
        final String provider;   // e.g. "ZOE STEM", "ZOE LOCAL · 1.5B", "CLAUDE"
        final String glassBox;   // Kloster A_tau(p) & epistemic telemetry
        final long latencyMs;
        final List<String> sources; // Optional "Label|https://..." clickable citations

        ChatMessage(String role, String text, String provider, String glassBox, long latencyMs) {
            this(role, text, provider, glassBox, latencyMs, null);
        }

        ChatMessage(String role, String text, String provider, String glassBox, long latencyMs, List<String> sources) {
            this.role = role == null ? "zoe" : role;
            this.text = text == null ? "" : text;
            this.provider = provider == null ? "" : provider;
            this.glassBox = glassBox == null ? "" : glassBox;
            this.latencyMs = Math.max(0L, latencyMs);
            this.sources = sources == null ? new ArrayList<>() : new ArrayList<>(sources);
        }
    }

    static final class ChatThread {
        final String id;
        String title;
        String updatedIso;
        final List<ChatMessage> messages;

        ChatThread(String id, String title, String updatedIso, List<ChatMessage> messages) {
            this.id = id;
            this.title = (title == null || title.trim().isEmpty()) ? "New conversation" : title.trim();
            this.updatedIso = updatedIso == null ? nowIso() : updatedIso;
            this.messages = messages == null ? new ArrayList<>() : messages;
        }
    }

    private ChatHistoryStore() {
    }

    static String nowIso() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.US).format(new Date());
    }

    static ChatThread newThread() {
        return new ChatThread("chat-" + System.currentTimeMillis(), "New conversation", nowIso(), new ArrayList<>());
    }

    static String titleFromPrompt(String prompt) {
        if (prompt == null || prompt.trim().isEmpty()) {
            return "New conversation";
        }
        String clean = prompt.trim().replaceAll("\\s+", " ");
        return clean.length() > 38 ? clean.substring(0, 38) + "…" : clean;
    }

    static String toJson(List<ChatThread> threads) {
        List<Object> arr = new ArrayList<>();
        if (threads != null) {
            int limit = Math.min(threads.size(), MAX_THREADS);
            for (int i = 0; i < limit; i++) {
                ChatThread t = threads.get(i);
                Map<String, Object> tm = new LinkedHashMap<>();
                tm.put("id", t.id);
                tm.put("title", t.title);
                tm.put("updatedIso", t.updatedIso);
                List<Object> msgs = new ArrayList<>();
                int start = Math.max(0, t.messages.size() - MAX_MESSAGES_PER_THREAD);
                for (int j = start; j < t.messages.size(); j++) {
                    ChatMessage m = t.messages.get(j);
                    Map<String, Object> mm = new LinkedHashMap<>();
                    mm.put("role", m.role);
                    mm.put("text", m.text);
                    mm.put("provider", m.provider);
                    mm.put("glassBox", m.glassBox);
                    mm.put("latencyMs", m.latencyMs);
                    if (!m.sources.isEmpty()) {
                        mm.put("sources", new ArrayList<Object>(m.sources));
                    }
                    msgs.add(mm);
                }
                tm.put("messages", msgs);
                arr.add(tm);
            }
        }
        Map<String, Object> root = new LinkedHashMap<>();
        root.put("threads", arr);
        return MiniJson.stringify(root);
    }

    static List<ChatThread> fromJson(String json) {
        List<ChatThread> out = new ArrayList<>();
        if (json == null || json.trim().isEmpty()) {
            return out;
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(json);
            List<Object> arr = MiniJson.asArray(root.get("threads"));
            if (arr == null) {
                return out;
            }
            for (Object item : arr) {
                Map<String, Object> tm = MiniJson.asObject(item);
                if (tm == null) {
                    continue;
                }
                String id = MiniJson.asString(tm, "id", "chat-0");
                String title = MiniJson.asString(tm, "title", "Conversation");
                String updated = MiniJson.asString(tm, "updatedIso", "");
                List<ChatMessage> msgs = new ArrayList<>();
                List<Object> rawMsgs = MiniJson.asArray(tm.get("messages"));
                if (rawMsgs != null) {
                    for (Object mObj : rawMsgs) {
                        Map<String, Object> mm = MiniJson.asObject(mObj);
                        if (mm == null) {
                            continue;
                        }
                        long lat = 0L;
                        Object latObj = mm.get("latencyMs");
                        if (latObj instanceof Number) {
                            lat = ((Number) latObj).longValue();
                        }
                        List<String> parsedSources = new ArrayList<>();
                        List<Object> rawSources = MiniJson.asArray(mm.get("sources"));
                        if (rawSources != null) {
                            for (Object sObj : rawSources) {
                                if (sObj instanceof String && !((String) sObj).trim().isEmpty()) {
                                    parsedSources.add(((String) sObj).trim());
                                }
                            }
                        }
                        msgs.add(new ChatMessage(
                                MiniJson.asString(mm, "role", "zoe"),
                                MiniJson.asString(mm, "text", ""),
                                MiniJson.asString(mm, "provider", ""),
                                MiniJson.asString(mm, "glassBox", ""),
                                lat,
                                parsedSources));
                    }
                }
                out.add(new ChatThread(id, title, updated, msgs));
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    static List<ChatThread> load(Context ctx) {
        if (ctx == null) {
            return new ArrayList<>();
        }
        File file = new File(ctx.getFilesDir(), FILE_NAME);
        if (!file.exists()) {
            return new ArrayList<>();
        }
        try (FileInputStream in = new FileInputStream(file)) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[4096];
            int read;
            while ((read = in.read(buf)) != -1) {
                out.write(buf, 0, read);
            }
            String raw = new String(out.toByteArray(), StandardCharsets.UTF_8);
            String plainJson = ZoeSignalCrypto.decryptFromVault(ctx, raw);
            return fromJson(plainJson);
        } catch (Exception ignored) {
            return new ArrayList<>();
        }
    }

    static void save(Context ctx, List<ChatThread> threads) {
        if (ctx == null) {
            return;
        }
        File file = new File(ctx.getFilesDir(), FILE_NAME);
        try (FileOutputStream out = new FileOutputStream(file)) {
            String encrypted = ZoeSignalCrypto.encryptForVault(ctx, toJson(threads));
            out.write(encrypted.getBytes(StandardCharsets.UTF_8));
            out.flush();
        } catch (Exception ignored) {
        }
    }
}
