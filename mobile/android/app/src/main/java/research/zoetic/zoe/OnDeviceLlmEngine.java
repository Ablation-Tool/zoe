package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;

import com.google.common.util.concurrent.ListenableFuture;
import com.google.mediapipe.framework.image.BitmapImageBuilder;
import com.google.mediapipe.framework.image.MPImage;
import com.google.mediapipe.tasks.genai.llminference.GraphOptions;
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

    private static final Object SHARED_LOCK = new Object();
    private static LlmInference sharedEngine;
    private static LlmInferenceSession sharedBaseSession;
    private static boolean sharedKvCloneSupported = true;
    private static boolean sharedVisionEnabled;
    private static String sharedLoadedPath = "";
    private static String sharedActiveBackend = "CPU";

    static final String BASE_SYSTEM_PREFIX = "<|im_start|>system\n"
            + MultiAiClient.ZOE_SYSTEM_PROMPT
            + "<|im_end|>\n"
            + "<|im_start|>user\nWho are you and who built you?<|im_end|>\n"
            + "<|im_start|>assistant\nI am Zoe, an open-source software assistant for the Zoe project "
            + "created by Nicholas Michael Kloster. Everything stays private on your device.<|im_end|>\n";

    private final Context appContext;
    private final java.util.concurrent.atomic.AtomicReference<LlmInferenceSession> activeSession =
            new java.util.concurrent.atomic.AtomicReference<>(null);
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
        releaseSharedEngine();
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
     * Builds a compact ChatML prompt grounded in Zoe's Constitution, recent private notes,
     * and optional opt-in live web citations.
     */
    static String buildChatMlPrompt(
            String userPrompt,
            List<ChatHistoryStore.ChatMessage> recentHistory,
            String memorySummary) {
        return buildChatMlPrompt(userPrompt, recentHistory, memorySummary, "");
    }

    static String buildChatMlPrompt(
            String userPrompt,
            List<ChatHistoryStore.ChatMessage> recentHistory,
            String memorySummary,
            String webContext) {
        StringBuilder sb = new StringBuilder();
        sb.append("<|im_start|>system\n");
        sb.append(MultiAiClient.ZOE_SYSTEM_PROMPT);
        if (memorySummary != null && !memorySummary.trim().isEmpty()) {
            sb.append("\nPrivate on-device memory:\n").append(memorySummary.trim());
        }
        if (webContext != null && !webContext.trim().isEmpty()) {
            sb.append("\nLive verified web facts (ground your answer in these concisely):\n")
                    .append(webContext.trim());
        }
        sb.append("<|im_end|>\n");
        // Identity few-shot anchor so local base weights never leak third-party corporate personas
        sb.append("<|im_start|>user\nWho are you and who built you?<|im_end|>\n");
        sb.append("<|im_start|>assistant\nI am Zoe, an open-source software assistant for the Zoe project ")
                .append("created by Nicholas Michael Kloster. Everything stays private on your device.<|im_end|>\n");
        sb.append(buildChatMlTurnDelta(userPrompt, recentHistory, "", ""));
        return sb.toString();
    }

    /**
     * Builds ONLY the per-turn suffix after {@link #BASE_SYSTEM_PREFIX} so KV-cached base sessions
     * cloned via {@code LlmInferenceSession.cloneSession()} skip re-prefilling the system prompt!
     */
    static String buildChatMlTurnDelta(
            String userPrompt,
            List<ChatHistoryStore.ChatMessage> recentHistory,
            String memorySummary,
            String webContext) {
        StringBuilder sb = new StringBuilder();
        String trimmedPrompt = userPrompt == null ? "" : userPrompt.trim();
        if (recentHistory != null && !recentHistory.isEmpty()) {
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
        StringBuilder effectiveUser = new StringBuilder();
        if (memorySummary != null && !memorySummary.trim().isEmpty()) {
            effectiveUser.append("[On-device memory: ").append(memorySummary.trim()).append("]\n");
        }
        if (webContext != null && !webContext.trim().isEmpty()) {
            effectiveUser.append("[Verified context: ").append(webContext.trim()).append("]\n");
        }
        effectiveUser.append(expandShortFollowUp(trimmedPrompt));
        sb.append("<|im_start|>user\n").append(effectiveUser).append("<|im_end|>\n");
        sb.append("<|im_start|>assistant\n");
        return sb.toString();
    }

    /**
     * Returns true when a sideloaded or downloaded LiteRT `.task` bundle includes native multimodal
     * vision encoders (e.g., Gemma 3n / Vision / VL packs), unlocking direct {@code session.addImage()}.
     */
    static boolean supportsNativeVision(File modelFile) {
        if (modelFile == null) {
            return false;
        }
        String n = modelFile.getName().toLowerCase(Locale.US);
        return n.contains("gemma-3n") || n.contains("gemma3n") || n.contains("vision")
                || n.contains("multimodal") || n.contains("-vl");
    }

    /**
     * Extracts the turn delta when a full prompt begins with {@link #BASE_SYSTEM_PREFIX} (enabling
     * zero-prefill KV-cache session cloning automatically!). Returns null if system context changed.
     */
    static String extractClonableDelta(String fullPrompt) {
        if (fullPrompt != null && fullPrompt.startsWith(BASE_SYSTEM_PREFIX)) {
            return fullPrompt.substring(BASE_SYSTEM_PREFIX.length());
        }
        return null;
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

    /**
     * Loads (or reuses) the process-wide shared MediaPipe LiteRT engine across Zoe Chat & Zoe Explore
     * (0 ms reload when switching screens!). Prefers hardware GPU (Tensor G2 Mali-G710) with
     * automatic safe fallback to CPU if a model pack or device lacks GPU delegate support.
     */
    private LlmInference ensureSharedEngine(File modelFile) {
        synchronized (SHARED_LOCK) {
            String path = modelFile.getAbsolutePath();
            if (sharedEngine != null && path.equals(sharedLoadedPath)) {
                return sharedEngine;
            }
            releaseSharedEngineLocked();
            boolean enableVision = supportsNativeVision(modelFile);
            try {
                LlmInference.LlmInferenceOptions.Builder gpuBuilder = LlmInference.LlmInferenceOptions.builder()
                        .setModelPath(path)
                        .setMaxTokens(1024)
                        .setMaxTopK(40)
                        .setPreferredBackend(LlmInference.Backend.GPU);
                if (enableVision) {
                    gpuBuilder.setMaxNumImages(1);
                }
                sharedEngine = LlmInference.createFromOptions(appContext, gpuBuilder.build());
                sharedLoadedPath = path;
                sharedActiveBackend = "GPU";
                sharedVisionEnabled = enableVision;
                sharedKvCloneSupported = true;
                return sharedEngine;
            } catch (Throwable gpuUnavailable) {
                LlmInference.LlmInferenceOptions.Builder cpuBuilder = LlmInference.LlmInferenceOptions.builder()
                        .setModelPath(path)
                        .setMaxTokens(1024)
                        .setMaxTopK(40)
                        .setPreferredBackend(LlmInference.Backend.CPU);
                if (enableVision) {
                    cpuBuilder.setMaxNumImages(1);
                }
                sharedEngine = LlmInference.createFromOptions(appContext, cpuBuilder.build());
                sharedLoadedPath = path;
                sharedActiveBackend = "CPU";
                sharedVisionEnabled = enableVision;
                sharedKvCloneSupported = true;
                return sharedEngine;
            }
        }
    }

    /** Pre-computes the base system-prompt KV-cache session once so turns can clone in <5ms. */
    private void ensureWarmBaseSessionLocked(LlmInference engine) {
        if (!sharedKvCloneSupported || sharedBaseSession != null || sharedVisionEnabled) {
            return;
        }
        try {
            LlmInferenceSession.LlmInferenceSessionOptions baseOpts =
                    LlmInferenceSession.LlmInferenceSessionOptions.builder()
                            .setTopK(40)
                            .setTopP(0.92f)
                            .setTemperature(0.75f)
                            .build();
            LlmInferenceSession base = LlmInferenceSession.createFromOptions(engine, baseOpts);
            base.addQueryChunk(BASE_SYSTEM_PREFIX);
            sharedBaseSession = base;
        } catch (Throwable unsupported) {
            sharedKvCloneSupported = false;
            sharedBaseSession = null;
        }
    }

    static String activeBackendLabel() {
        return sharedActiveBackend;
    }

    static String runtimeTelemetryLabel() {
        StringBuilder sb = new StringBuilder(sharedActiveBackend);
        if (sharedBaseSession != null && sharedKvCloneSupported) {
            sb.append(" · KV-Clone");
        }
        if (sharedVisionEnabled) {
            sb.append(" · Native Vision");
        }
        return sb.toString();
    }

    /** Pre-loads the shared MediaPipe LiteRT model + KV base session in background for instant first turn. */
    void warmUp(File modelFile) {
        if (modelFile == null || !modelFile.isFile()) {
            return;
        }
        try {
            LlmInference eng = ensureSharedEngine(modelFile);
            synchronized (SHARED_LOCK) {
                ensureWarmBaseSessionLocked(eng);
            }
        } catch (Throwable ignored) {
        }
    }

    /**
     * Immediately interrupts any in-flight local token generation (true Gemini-Live-speed barge-in!).
     */
    void cancelActiveGeneration() {
        LlmInferenceSession current = activeSession.getAndSet(null);
        if (current != null) {
            try {
                current.cancelGenerateResponseAsync();
            } catch (Throwable ignored) {
            }
        }
    }

    String generateStreaming(
            File modelFile,
            String prompt,
            TokenCallback callback) throws Exception {
        return generateStreamingWithOptionalImage(modelFile, prompt, null, callback);
    }

    /**
     * Production streaming generation supporting:
     *   1. Zero-prefill KV-cache cloning ({@code cloneSession()}) when prompt begins with BASE_SYSTEM_PREFIX
     *   2. Direct on-device multimodal {@code addImage(MPImage)} when a vision-capable `.task` pack is loaded
     *   3. Seamless fallback to standard full-prompt session if cloning or vision isn't supported by the pack
     */
    String generateStreamingWithOptionalImage(
            File modelFile,
            String prompt,
            Bitmap optionalImage,
            TokenCallback callback) throws Exception {
        if (modelFile == null || !modelFile.isFile()) {
            throw new IOException("No offline .task model installed yet.");
        }
        cancelActiveGeneration();
        LlmInference engine = ensureSharedEngine(modelFile);
        synchronized (SHARED_LOCK) {
            StringBuilder full = new StringBuilder();
            boolean attachVision = optionalImage != null && !optionalImage.isRecycled() && sharedVisionEnabled;
            String clonableDelta = (!attachVision && sharedKvCloneSupported) ? extractClonableDelta(prompt) : null;

            LlmInferenceSession session = null;
            boolean usedClone = false;
            if (clonableDelta != null) {
                ensureWarmBaseSessionLocked(engine);
                if (sharedBaseSession != null) {
                    try {
                        session = sharedBaseSession.cloneSession();
                        session.addQueryChunk(clonableDelta);
                        usedClone = true;
                    } catch (Throwable cloneFailed) {
                        sharedKvCloneSupported = false;
                        if (session != null) {
                            try { session.close(); } catch (Throwable ignored) {}
                            session = null;
                        }
                    }
                }
            }

            if (session == null) {
                LlmInferenceSession.LlmInferenceSessionOptions.Builder sessionBuilder =
                        LlmInferenceSession.LlmInferenceSessionOptions.builder()
                                .setTopK(40)
                                .setTopP(0.92f)
                                .setTemperature(0.75f)
                                .setRandomSeed((int) (System.nanoTime() & 0x7fffffffL));
                if (attachVision) {
                    sessionBuilder.setGraphOptions(
                            GraphOptions.builder().setEnableVisionModality(true).build());
                }
                session = LlmInferenceSession.createFromOptions(engine, sessionBuilder.build());
                session.addQueryChunk(prompt);
                if (attachVision) {
                    try {
                        Bitmap sized = MediaChatHelper.scaleDown(
                                optionalImage.copy(Bitmap.Config.ARGB_8888, false), 512);
                        MPImage mpImg = new BitmapImageBuilder(sized).build();
                        session.addImage(mpImg);
                        if (!sized.isRecycled()) {
                            sized.recycle();
                        }
                    } catch (Throwable ignored) {
                    }
                }
            }

            try (LlmInferenceSession active = session) {
                activeSession.set(active);
                ListenableFuture<String> future = active.generateResponseAsync((partialResult, done) -> {
                    if (partialResult != null) {
                        full.append(partialResult);
                    }
                    if (callback != null) {
                        callback.onToken(cleanResponse(full.toString()), done);
                    }
                });
                String finalText = future.get();
                String best = (finalText != null && !finalText.trim().isEmpty()) ? finalText : full.toString();
                if (best.trim().isEmpty() && usedClone) {
                    sharedKvCloneSupported = false;
                }
                return cleanResponse(best);
            } finally {
                activeSession.set(null);
            }
        }
    }

    static String cleanResponse(String raw) {
        if (raw == null) {
            return "";
        }
        String cleaned = raw.replace("<|im_end|>", "")
                .replace("<|endoftext|>", "")
                .replace("\\n", "\n")
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

    /** Cancels this screen's active turn while keeping the shared engine warm across Zoe Chat & Explore. */
    void close() {
        cancelActiveGeneration();
    }

    static void releaseSharedEngine() {
        synchronized (SHARED_LOCK) {
            releaseSharedEngineLocked();
        }
    }

    private static void releaseSharedEngineLocked() {
        if (sharedBaseSession != null) {
            try {
                sharedBaseSession.close();
            } catch (Exception ignored) {
            }
            sharedBaseSession = null;
        }
        if (sharedEngine != null) {
            try {
                sharedEngine.close();
            } catch (Exception ignored) {
            }
            sharedEngine = null;
            sharedLoadedPath = "";
            sharedActiveBackend = "CPU";
            sharedVisionEnabled = false;
            sharedKvCloneSupported = true;
        }
    }
}
