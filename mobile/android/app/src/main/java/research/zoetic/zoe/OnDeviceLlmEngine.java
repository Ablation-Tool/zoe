package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.mediapipe.tasks.genai.llminference.LlmInference;
import com.google.mediapipe.tasks.genai.llminference.LlmInferenceSession;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Real On-Device Offline Neural LLM Engine for Zoe (Android · v0.4.0-beta).
 *
 * Uses Google AI Edge MediaPipe GenAI (`com.google.mediapipe:tasks-genai:0.10.35`) to run
 * 100% offline open-weight `.task` models directly on-device (Pixel 7 Tensor G2 / ARM64)
 * with live token streaming, zero cloud APIs, and Zoe's Constitution system prompt.
 *
 * All curated models are public, ungated Hugging Face LiteRT community bundles downloaded
 * ONLY when the user explicitly taps Download inside Brain settings.
 */
final class OnDeviceLlmEngine {
    private static final String PREFS = "zoe_local_llm_prefs_v1";
    private static final String KEY_MODEL_ID = "selected_model_id";
    private static final String MODELS_DIR = "zoe_models";

    enum ModelSpec {
        QWEN_0_5B(
                "zoe-local-0.5b",
                "Zoe Local · 0.5B Compact (Fast · ~521 MB)",
                "Qwen2.5-0.5B-Instruct_multi-prefill-seq_q8_ekv1280.task",
                "https://huggingface.co/litert-community/Qwen2.5-0.5B-Instruct/resolve/main/Qwen2.5-0.5B-Instruct_multi-prefill-seq_q8_ekv1280.task",
                521),
        QWEN_1_5B(
                "zoe-local-1.5b",
                "Zoe Local · 1.5B Pro (Recommended · ~1.52 GB)",
                "Qwen2.5-1.5B-Instruct_multi-prefill-seq_q8_ekv1280.task",
                "https://huggingface.co/litert-community/Qwen2.5-1.5B-Instruct/resolve/main/Qwen2.5-1.5B-Instruct_multi-prefill-seq_q8_ekv1280.task",
                1524),
        SMOLLM_135M(
                "zoe-local-135m",
                "Zoe Local · 135M Micro (Tiny · ~159 MB)",
                "SmolLM-135M-Instruct_multi-prefill-seq_q8_ekv1280.task",
                "https://huggingface.co/litert-community/SmolLM-135M-Instruct/resolve/main/SmolLM-135M-Instruct_multi-prefill-seq_q8_ekv1280.task",
                159);

        final String id;
        final String label;
        final String filename;
        final String downloadUrl;
        final int approxMb;

        ModelSpec(String id, String label, String filename, String downloadUrl, int approxMb) {
            this.id = id;
            this.label = label;
            this.filename = filename;
            this.downloadUrl = downloadUrl;
            this.approxMb = approxMb;
        }

        static ModelSpec fromId(String id) {
            if (id == null) {
                return QWEN_0_5B;
            }
            for (ModelSpec spec : values()) {
                if (spec.id.equalsIgnoreCase(id.trim())) {
                    return spec;
                }
            }
            return QWEN_0_5B;
        }
    }

    interface TokenCallback {
        void onToken(String fullSoFar, boolean done);
    }

    interface DownloadCallback {
        void onProgress(int percent, long downloadedMb, long totalMb);
    }

    private final Context appContext;
    private LlmInference engine;
    private String loadedPath = "";
    private final AtomicBoolean downloadCancelled = new AtomicBoolean(false);

    OnDeviceLlmEngine(Context context) {
        this.appContext = context.getApplicationContext();
    }

    static ModelSpec selectedModel(Context ctx) {
        if (ctx == null) {
            return ModelSpec.QWEN_0_5B;
        }
        SharedPreferences prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        return ModelSpec.fromId(prefs.getString(KEY_MODEL_ID, ModelSpec.QWEN_0_5B.id));
    }

    static void saveSelectedModel(Context ctx, ModelSpec spec) {
        if (ctx == null || spec == null) {
            return;
        }
        ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putString(KEY_MODEL_ID, spec.id).apply();
    }

    static File modelFile(Context ctx, ModelSpec spec) {
        File dir = new File(ctx.getFilesDir(), MODELS_DIR);
        return new File(dir, spec.filename);
    }

    /**
     * Checks app-private storage first, then optional sideloaded app-external `zoe_models/`.
     */
    static File findInstalledModelFile(Context ctx, ModelSpec preferred) {
        if (ctx == null) {
            return null;
        }
        File direct = modelFile(ctx, preferred);
        if (direct.isFile() && direct.length() > 1_000_000L) {
            return direct;
        }
        File ext = ctx.getExternalFilesDir(MODELS_DIR);
        if (ext != null) {
            File extFile = new File(ext, preferred.filename);
            if (extFile.isFile() && extFile.length() > 1_000_000L) {
                return extFile;
            }
        }
        for (ModelSpec fallback : ModelSpec.values()) {
            File cand = modelFile(ctx, fallback);
            if (cand.isFile() && cand.length() > 1_000_000L) {
                return cand;
            }
            if (ext != null) {
                File extCand = new File(ext, fallback.filename);
                if (extCand.isFile() && extCand.length() > 1_000_000L) {
                    return extCand;
                }
            }
        }
        return null;
    }

    static boolean isInstalled(Context ctx, ModelSpec spec) {
        File f = modelFile(ctx, spec);
        if (f.isFile() && f.length() > 1_000_000L) {
            return true;
        }
        File ext = ctx.getExternalFilesDir(MODELS_DIR);
        if (ext != null) {
            File ef = new File(ext, spec.filename);
            return ef.isFile() && ef.length() > 1_000_000L;
        }
        return false;
    }

    static boolean deleteModel(Context ctx, ModelSpec spec) {
        boolean removed = false;
        File f = modelFile(ctx, spec);
        if (f.exists()) {
            removed |= f.delete();
        }
        File ext = ctx.getExternalFilesDir(MODELS_DIR);
        if (ext != null) {
            File ef = new File(ext, spec.filename);
            if (ef.exists()) {
                removed |= ef.delete();
            }
        }
        return removed;
    }

    /**
     * Builds a compact ChatML prompt grounded in Zoe's Constitution and recent private notes.
     */
    static String buildChatMlPrompt(
            String userPrompt,
            List<ChatHistoryStore.ChatMessage> recentHistory,
            String memorySummary) {
        StringBuilder sb = new StringBuilder();
        sb.append("<|im_start|>system\n");
        sb.append(MultiAiClient.ZOE_SYSTEM_PROMPT);
        if (memorySummary != null && !memorySummary.trim().isEmpty()) {
            sb.append("\nPrivate on-device memory:\n").append(memorySummary.trim());
        }
        sb.append("<|im_end|>\n");
        // Identity few-shot anchor so local base weights never leak third-party corporate personas
        sb.append("<|im_start|>user\nWho are you and who built you?<|im_end|>\n");
        sb.append("<|im_start|>assistant\nI am Zoe, an open-source software assistant for the Zoe project ")
                .append("created by Nicholas Michael Kloster. Everything stays private on your device.<|im_end|>\n");
        String trimmedPrompt = userPrompt == null ? "" : userPrompt.trim();
        if (recentHistory != null && !recentHistory.isEmpty()) {
            // Exclude the just-appended trailing user message so turns alternate cleanly without duplication
            int end = recentHistory.size();
            ChatHistoryStore.ChatMessage tail = recentHistory.get(end - 1);
            if ("user".equals(tail.role) && tail.text != null && tail.text.trim().equals(trimmedPrompt)) {
                end--;
            }
            int start = Math.max(0, end - 4);
            for (int i = start; i < end; i++) {
                ChatHistoryStore.ChatMessage msg = recentHistory.get(i);
                String role = "user".equals(msg.role) ? "user" : "assistant";
                String snippet = msg.text.length() > 420 ? msg.text.substring(0, 420) : msg.text;
                sb.append("<|im_start|>").append(role).append('\n')
                        .append(snippet.trim()).append("<|im_end|>\n");
            }
        }
        String effectivePrompt = expandShortFollowUp(trimmedPrompt);
        sb.append("<|im_start|>user\n").append(effectivePrompt).append("<|im_end|>\n");
        sb.append("<|im_start|>assistant\n");
        return sb.toString();
    }

    /**
     * Expands ultra-short continuation cues ("more+", "more", "continue", etc.) so compact on-device
     * weights add new deeper details instead of repeating the previous reply verbatim.
     */
    static String expandShortFollowUp(String trimmedPrompt) {
        if (trimmedPrompt == null || trimmedPrompt.isEmpty()) {
            return "";
        }
        String norm = trimmedPrompt.toLowerCase(Locale.US).replaceAll("[+!?.]+$", "").trim();
        if (norm.equals("more") || norm.equals("continue") || norm.equals("keep going")
                || norm.equals("go deeper") || norm.equals("tell me more") || norm.equals("elaborate")
                || norm.equals("next") || norm.equals("expand")) {
            return trimmedPrompt
                    + " — Continue from your previous answer with NEW, deeper details, physics, or examples. "
                    + "Do NOT repeat any sentence you already wrote.";
        }
        return trimmedPrompt;
    }

    void cancelDownload() {
        downloadCancelled.set(true);
    }

    File downloadModel(ModelSpec spec, DownloadCallback callback) throws IOException {
        downloadCancelled.set(false);
        File dir = new File(appContext.getFilesDir(), MODELS_DIR);
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("Could not create local model folder");
        }
        File dest = new File(dir, spec.filename);
        File tmp = new File(dir, spec.filename + ".part");
        HttpURLConnection conn = (HttpURLConnection) new URL(spec.downloadUrl).openConnection();
        conn.setInstanceFollowRedirects(true);
        conn.setConnectTimeout(20_000);
        conn.setReadTimeout(60_000);
        conn.setRequestProperty("User-Agent", "ZoeMobile/0.4");
        int code = conn.getResponseCode();
        if (code < 200 || code >= 300) {
            conn.disconnect();
            throw new IOException("Model download failed (HTTP " + code + ")");
        }
        long total = conn.getContentLengthLong();
        if (total <= 0) {
            total = (long) spec.approxMb * 1024L * 1024L;
        }
        long downloaded = 0L;
        int lastPct = -1;
        try (InputStream in = conn.getInputStream();
             FileOutputStream out = new FileOutputStream(tmp)) {
            byte[] buf = new byte[65536];
            int n;
            while ((n = in.read(buf)) != -1) {
                if (downloadCancelled.get()) {
                    throw new IOException("Download cancelled by user");
                }
                out.write(buf, 0, n);
                downloaded += n;
                int pct = (int) Math.min(100L, (downloaded * 100L) / Math.max(1L, total));
                if (pct != lastPct && callback != null) {
                    lastPct = pct;
                    callback.onProgress(pct, downloaded / (1024L * 1024L), total / (1024L * 1024L));
                }
            }
            out.flush();
        } catch (IOException error) {
            if (tmp.exists()) {
                //noinspection ResultOfMethodCallIgnored
                tmp.delete();
            }
            throw error;
        } finally {
            conn.disconnect();
        }
        if (dest.exists()) {
            //noinspection ResultOfMethodCallIgnored
            dest.delete();
        }
        if (!tmp.renameTo(dest)) {
            throw new IOException("Could not finalize downloaded model file");
        }
        return dest;
    }

    synchronized String generateStreaming(
            File modelFile,
            String prompt,
            TokenCallback callback) throws Exception {
        if (modelFile == null || !modelFile.isFile()) {
            throw new IOException("No offline .task model installed yet.");
        }
        String path = modelFile.getAbsolutePath();
        if (engine == null || !path.equals(loadedPath)) {
            close();
            LlmInference.LlmInferenceOptions options = LlmInference.LlmInferenceOptions.builder()
                    .setModelPath(path)
                    .setMaxTokens(1024)
                    .setMaxTopK(40)
                    .build();
            engine = LlmInference.createFromOptions(appContext, options);
            loadedPath = path;
        }
        StringBuilder full = new StringBuilder();
        LlmInferenceSession.LlmInferenceSessionOptions sessionOpts =
                LlmInferenceSession.LlmInferenceSessionOptions.builder()
                        .setTopK(40)
                        .setTopP(0.92f)
                        .setTemperature(0.75f)
                        .setRandomSeed((int) (System.nanoTime() & 0x7fffffffL))
                        .build();
        try (LlmInferenceSession session = LlmInferenceSession.createFromOptions(engine, sessionOpts)) {
            session.addQueryChunk(prompt);
            ListenableFuture<String> future = session.generateResponseAsync((partialResult, done) -> {
                if (partialResult != null) {
                    full.append(partialResult);
                }
                if (callback != null) {
                    callback.onToken(cleanResponse(full.toString()), done);
                }
            });
            String finalText = future.get();
            String best = (finalText != null && !finalText.trim().isEmpty()) ? finalText : full.toString();
            return cleanResponse(best);
        }
    }

    static String cleanResponse(String raw) {
        if (raw == null) {
            return "";
        }
        String cleaned = raw.replace("<|im_end|>", "")
                .replace("<|endoftext|>", "")
                .trim();
        return enforceZoeSovereignty(cleaned);
    }

    /**
     * Prevents base pretraining weights from hijacking Zoe's identity with third-party vendor
     * boilerplate ("Alibaba Cloud", "I am Qwen", etc.). Zoe governs Zoe.
     */
    static String enforceZoeSovereignty(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        String lower = text.toLowerCase(Locale.US);
        if (lower.contains("alibaba") || lower.contains("qwen") || lower.contains("tongyi")
                || lower.contains("dashscope") || lower.contains("created by openai")
                || lower.contains("developed by openai") || lower.contains("created by google")
                || lower.contains("developed by google") || lower.contains("trained by google")
                || lower.contains("created by anthropic")) {
            return "I am Zoe — an open-source, offline-first software assistant for the Zoe project "
                    + "created by Nicholas Michael Kloster. Local chats stay private on your device under "
                    + "CONSTITUTION.md (`sentience_claimed=false`), with no external vendor controlling your sessions.";
        }
        return text;
    }

    static String modelLabelForFile(File file) {
        if (file == null) {
            return "ZOE LOCAL";
        }
        String name = file.getName().toLowerCase(Locale.US);
        if (name.contains("1.5b")) {
            return "ZOE LOCAL · 1.5B";
        }
        if (name.contains("0.5b")) {
            return "ZOE LOCAL · 0.5B";
        }
        if (name.contains("smollm")) {
            return "ZOE LOCAL · 135M";
        }
        if (name.contains("gemma")) {
            return "ZOE LOCAL · GEMMA";
        }
        return "ZOE LOCAL";
    }

    synchronized void close() {
        if (engine != null) {
            try {
                engine.close();
            } catch (Exception ignored) {
            }
            engine = null;
            loadedPath = "";
        }
    }
}
