package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Bitmap;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * On-Device Self-Improving Structural Visual Memory for Guided Vision & Zoe Explore (v0.9.1-beta).
 *
 * Instead of showing noisy raw patent popups to the user, Zoe uses this private app-local store
 * (allowBackup="false", zero cloud telemetry) to learn and refine object contour prototypes over time:
 *   - Every time the user teaches/confirms an object in Guided Vision — or Guided Vision resolves a
 *     high-confidence CPC-filtered physical patent schematic — Zoe stores or reinforces its 4-part
 *     Sobel VisualSignature (HoG-16, Radial-8, dHash-64, aspect ratio, bilateral symmetry).
 *   - Repeated confirmations incrementally refine the prototype via L2-normalized running mean so
 *     recognition accuracy improves cleanly offline across lighting & angle changes.
 *   - Both Guided Vision and Zoe Explore query this store silently (<2ms offline) to recognize
 *     previously learned objects without cluttering the UI.
 */
final class VisionPriorStore {
    static final float DEFAULT_MIN_SCORE = 0.78f;
    static final float ATLAS_MIN_SCORE = 0.84f;
    static final int MAX_PROTOTYPES = 120;
    private static final String FILE_NAME = "zoe_vision_priors.json";
    private static final String ATLAS_ASSET = "zoe_visual_atlas.json";

    static final class Prototype {
        final String label;
        final String source; // "user_confirmed", "patent_cpc"
        final String patentRef;
        final String dimensionsNote;
        final PatentReverseImageEngine.VisualSignature signature;
        final int confirmCount;
        final long updatedAtMs;

        Prototype(String label, String source, String patentRef, String dimensionsNote,
                  PatentReverseImageEngine.VisualSignature signature, int confirmCount, long updatedAtMs) {
            this.label = cleanLabel(label);
            this.source = source == null ? "user_confirmed" : source.trim();
            this.patentRef = patentRef == null ? "" : patentRef.trim();
            this.dimensionsNote = dimensionsNote == null ? "" : dimensionsNote.trim();
            this.signature = signature;
            this.confirmCount = Math.max(1, confirmCount);
            this.updatedAtMs = updatedAtMs;
        }
    }

    static final class MatchResult {
        final Prototype prototype;
        final float score;

        MatchResult(Prototype prototype, float score) {
            this.prototype = prototype;
            this.score = score;
        }

        int matchPercent() {
            return Math.round(Math.max(0f, Math.min(1f, score)) * 100f);
        }

        String formatGuidedSummary() {
            StringBuilder sb = new StringBuilder();
            sb.append(prototype.label)
                    .append(" (")
                    .append(matchPercent())
                    .append("% contour match · ");
            if ("patent_cpc".equals(prototype.source)) {
                sb.append("patent structural prior");
            } else if ("atlas_baseline".equals(prototype.source)) {
                sb.append("Haeckel/CPC offline atlas");
            } else {
                sb.append("learned offline");
            }
            if (prototype.confirmCount > 1) {
                sb.append(" · seen ").append(prototype.confirmCount).append("×");
            }
            sb.append(")");
            if (!prototype.dimensionsNote.isEmpty()) {
                sb.append(" · Typical scale: ").append(prototype.dimensionsNote);
            }
            return sb.toString();
        }

        String formatSilentPromptHint() {
            StringBuilder sb = new StringBuilder();
            sb.append("Learned visual memory candidate: ").append(prototype.label)
                    .append(" (").append(matchPercent()).append("% structural contour match");
            if (prototype.confirmCount > 1) {
                sb.append(", reinforced ").append(prototype.confirmCount).append("x");
            }
            sb.append(").");
            if (!prototype.dimensionsNote.isEmpty()) {
                sb.append(" Reference dimensions: ").append(prototype.dimensionsNote).append(".");
            }
            return sb.toString();
        }
    }

    private VisionPriorStore() {
    }

    static String cleanLabel(String raw) {
        if (raw == null) {
            return "";
        }
        String cleaned = raw.replaceAll("[\\r\\n\\t]+", " ")
                .replaceAll("\\s+", " ")
                .trim();
        if (cleaned.length() > 64) {
            cleaned = cleaned.substring(0, 64).trim();
        }
        return cleaned;
    }

    /**
     * Pure JVM-testable nearest-prototype lookup with strict similarity threshold so unrelated
     * scenes are honestly rejected instead of producing false positives.
     */
    static MatchResult findBestMatch(List<Prototype> store,
                                     PatentReverseImageEngine.VisualSignature query,
                                     float minScore) {
        if (store == null || store.isEmpty() || query == null) {
            return null;
        }
        Prototype best = null;
        float bestRaw = -1f;
        float bestRank = -1f;
        for (Prototype p : store) {
            if (p == null || p.signature == null || p.label.isEmpty()) {
                continue;
            }
            float sim = PatentReverseImageEngine.compareSignatures(query, p.signature);
            if (sim < minScore) {
                continue;
            }
            // Small priority nudge for explicitly user-confirmed objects on near-ties
            float rank = sim + ("user_confirmed".equals(p.source) ? 0.015f : 0f);
            if (rank > bestRank) {
                bestRank = rank;
                bestRaw = sim;
                best = p;
            }
        }
        return best == null ? null : new MatchResult(best, bestRaw);
    }

    /**
     * Pure JVM-testable incremental prototype learner:
     *   - If {@code label} already exists, refines its HoG-16 / Radial-8 / geometry with an online
     *     running mean and increments {@code confirmCount}.
     *   - Otherwise inserts a new learned prototype, keeping store size bounded cleanly.
     */
    static List<Prototype> teachOrReinforce(List<Prototype> existing,
                                            String label,
                                            PatentReverseImageEngine.VisualSignature sig,
                                            String source,
                                            String patentRef,
                                            String dimensionsNote,
                                            long nowMs) {
        String clean = cleanLabel(label);
        List<Prototype> updated = existing == null ? new ArrayList<>() : new ArrayList<>(existing);
        if (clean.isEmpty() || sig == null) {
            return updated;
        }
        int matchIdx = -1;
        for (int i = 0; i < updated.size(); i++) {
            if (updated.get(i).label.equalsIgnoreCase(clean)) {
                matchIdx = i;
                break;
            }
        }
        if (matchIdx >= 0) {
            Prototype prev = updated.get(matchIdx);
            int nextCount = prev.confirmCount + 1;
            float prevW = (float) prev.confirmCount / nextCount;
            float newW = 1.0f / nextCount;

            float[] blendedHog = blendNormalized(prev.signature.hog16, sig.hog16, prevW, newW);
            float[] blendedRad = blendNormalized(prev.signature.radial8, sig.radial8, prevW, newW);
            float blendedAspect = prev.signature.aspectRatio * prevW + sig.aspectRatio * newW;
            float blendedSym = prev.signature.bilateralSymmetry * prevW + sig.bilateralSymmetry * newW;
            float blendedOrtho = prev.signature.orthogonalRatio * prevW + sig.orthogonalRatio * newW;
            float blendedDens = prev.signature.edgeDensity * prevW + sig.edgeDensity * newW;

            PatentReverseImageEngine.VisualSignature refined = new PatentReverseImageEngine.VisualSignature(
                    blendedHog, blendedRad, sig.dHash64, blendedAspect, blendedSym,
                    blendedOrtho, blendedDens, sig.morphologyKeywords, sig.shapeSummary);
            String finalSource = "user_confirmed".equals(prev.source) || "user_confirmed".equals(source)
                    ? "user_confirmed"
                    : (source == null || source.isEmpty() ? prev.source : source);
            String finalPat = (patentRef != null && !patentRef.trim().isEmpty()) ? patentRef.trim() : prev.patentRef;
            String finalDims = (dimensionsNote != null && !dimensionsNote.trim().isEmpty())
                    ? dimensionsNote.trim() : prev.dimensionsNote;
            updated.set(matchIdx, new Prototype(prev.label, finalSource, finalPat, finalDims, refined, nextCount, nowMs));
        } else {
            updated.add(new Prototype(clean, source, patentRef, dimensionsNote, sig, 1, nowMs));
            if (updated.size() > MAX_PROTOTYPES) {
                // Evict oldest single-observation prototype first
                int evictIdx = 0;
                long oldestTs = Long.MAX_VALUE;
                for (int i = 0; i < updated.size(); i++) {
                    Prototype p = updated.get(i);
                    long scoreTs = p.updatedAtMs + (p.confirmCount > 1 ? 86_400_000L * 365L : 0L);
                    if (scoreTs < oldestTs) {
                        oldestTs = scoreTs;
                        evictIdx = i;
                    }
                }
                updated.remove(evictIdx);
            }
        }
        return updated;
    }

    private static float[] blendNormalized(float[] a, float[] b, float wa, float wb) {
        int n = Math.min(a.length, b.length);
        float[] out = new float[n];
        double sumSq = 0.0;
        for (int i = 0; i < n; i++) {
            out[i] = a[i] * wa + b[i] * wb;
            sumSq += out[i] * out[i];
        }
        float norm = (float) Math.sqrt(sumSq);
        if (norm > 1e-6f) {
            for (int i = 0; i < n; i++) {
                out[i] /= norm;
            }
        }
        return out;
    }

    // --- Pure JVM JSON Serialization (MiniJson-compatible, zero external deps) ---

    static String serializeJson(List<Prototype> list) {
        StringBuilder sb = new StringBuilder();
        sb.append("{\"version\":1,\"prototypes\":[");
        if (list != null) {
            for (int i = 0; i < list.size(); i++) {
                Prototype p = list.get(i);
                if (p == null || p.signature == null) {
                    continue;
                }
                if (i > 0) sb.append(',');
                sb.append('{');
                sb.append("\"label\":").append(jsonStr(p.label)).append(',');
                sb.append("\"source\":").append(jsonStr(p.source)).append(',');
                sb.append("\"patentRef\":").append(jsonStr(p.patentRef)).append(',');
                sb.append("\"dims\":").append(jsonStr(p.dimensionsNote)).append(',');
                sb.append("\"count\":").append(p.confirmCount).append(',');
                sb.append("\"updated\":").append(p.updatedAtMs).append(',');
                sb.append("\"dHash\":").append(jsonStr(Long.toUnsignedString(p.signature.dHash64, 16))).append(',');
                sb.append("\"aspect\":").append(String.format(Locale.US, "%.4f", p.signature.aspectRatio)).append(',');
                sb.append("\"sym\":").append(String.format(Locale.US, "%.4f", p.signature.bilateralSymmetry)).append(',');
                sb.append("\"ortho\":").append(String.format(Locale.US, "%.4f", p.signature.orthogonalRatio)).append(',');
                sb.append("\"density\":").append(String.format(Locale.US, "%.4f", p.signature.edgeDensity)).append(',');
                sb.append("\"kw\":").append(jsonStr(p.signature.morphologyKeywords)).append(',');
                sb.append("\"summary\":").append(jsonStr(p.signature.shapeSummary)).append(',');
                sb.append("\"hog\":").append(floatArrayJson(p.signature.hog16)).append(',');
                sb.append("\"radial\":").append(floatArrayJson(p.signature.radial8));
                sb.append('}');
            }
        }
        sb.append("]}");
        return sb.toString();
    }

    static List<Prototype> deserializeJson(String json) {
        List<Prototype> out = new ArrayList<>();
        if (json == null || json.trim().isEmpty()) {
            return out;
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(json);
            List<Object> arr = MiniJson.asArray(root.get("prototypes"));
            if (arr == null) {
                return out;
            }
            for (Object item : arr) {
                Map<String, Object> obj = MiniJson.asObject(item);
                if (obj == null) {
                    continue;
                }
                String label = MiniJson.asString(obj, "label", "");
                if (label.isEmpty()) {
                    continue;
                }
                String source = MiniJson.asString(obj, "source", "user_confirmed");
                String patRef = MiniJson.asString(obj, "patentRef", "");
                String dims = MiniJson.asString(obj, "dims", "");
                int count = (int) Math.max(1L, asLong(obj.get("count"), 1L));
                long updated = asLong(obj.get("updated"), 0L);
                long dHash = parseUnsignedHex(MiniJson.asString(obj, "dHash", "0"));
                float aspect = asFloat(obj.get("aspect"), 1f);
                float sym = asFloat(obj.get("sym"), 0.5f);
                float ortho = asFloat(obj.get("ortho"), 0.3f);
                float density = asFloat(obj.get("density"), 0.1f);
                String kw = MiniJson.asString(obj, "kw", "");
                String summary = MiniJson.asString(obj, "summary", "");
                float[] hog = parseFloatArray(MiniJson.asArray(obj.get("hog")), 16);
                float[] radial = parseFloatArray(MiniJson.asArray(obj.get("radial")), 8);
                if (hog == null || radial == null) {
                    continue;
                }
                PatentReverseImageEngine.VisualSignature sig = new PatentReverseImageEngine.VisualSignature(
                        hog, radial, dHash, aspect, sym, ortho, density, kw, summary);
                out.add(new Prototype(label, source, patRef, dims, sig, count, updated));
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    /**
     * Checks user-taught & CPC-learned prototypes first at {@code userMinScore}, then falls back
     * to the clean-room offline Haeckel/CPC structural atlas ONLY at a stricter {@code atlasMinScore}.
     */
    static MatchResult findBestMatchWithAtlas(List<Prototype> userStore,
                                              List<Prototype> atlas,
                                              PatentReverseImageEngine.VisualSignature query,
                                              float userMinScore,
                                              float atlasMinScore) {
        MatchResult userHit = findBestMatch(userStore, query, userMinScore);
        if (userHit != null) {
            return userHit;
        }
        return findBestMatch(atlas, query, atlasMinScore);
    }

    // --- Android App-Private Storage Helpers (RAM-cached for <0.1ms zero-disk-I/O live lookups) ---

    private static List<Prototype> ramCache;
    private static List<Prototype> atlasCache;

    static synchronized List<Prototype> loadBaselineAtlas(Context context) {
        if (atlasCache != null) {
            return atlasCache;
        }
        if (context == null) {
            return Collections.emptyList();
        }
        try (java.io.InputStream in = context.getAssets().open(ATLAS_ASSET);
             java.io.ByteArrayOutputStream out = new java.io.ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
            }
            atlasCache = deserializeJson(new String(out.toByteArray(), StandardCharsets.UTF_8));
            return atlasCache;
        } catch (Exception ignored) {
            atlasCache = Collections.emptyList();
            return atlasCache;
        }
    }

    static synchronized List<Prototype> loadAll(Context context) {
        if (context == null) {
            return new ArrayList<>();
        }
        if (ramCache != null) {
            return new ArrayList<>(ramCache);
        }
        File file = new File(context.getFilesDir(), FILE_NAME);
        if (!file.exists() || file.length() <= 0 || file.length() > 512 * 1024) {
            ramCache = new ArrayList<>();
            return new ArrayList<>();
        }
        try (FileInputStream fis = new FileInputStream(file)) {
            byte[] data = new byte[(int) file.length()];
            int offset = 0;
            while (offset < data.length) {
                int r = fis.read(data, offset, data.length - offset);
                if (r < 0) break;
                offset += r;
            }
            List<Prototype> parsed = deserializeJson(new String(data, 0, offset, StandardCharsets.UTF_8));
            ramCache = new ArrayList<>(parsed);
            return parsed;
        } catch (Exception ignored) {
            ramCache = new ArrayList<>();
            return new ArrayList<>();
        }
    }

    static synchronized void saveAll(Context context, List<Prototype> list) {
        if (context == null) {
            return;
        }
        ramCache = list == null ? new ArrayList<>() : new ArrayList<>(list);
        File file = new File(context.getFilesDir(), FILE_NAME);
        try (FileOutputStream fos = new FileOutputStream(file)) {
            fos.write(serializeJson(list).getBytes(StandardCharsets.UTF_8));
        } catch (Exception ignored) {
        }
    }

    static synchronized int learnedCount(Context context) {
        return loadAll(context).size();
    }

    static synchronized void clearAll(Context context) {
        ramCache = new ArrayList<>();
        if (context == null) {
            return;
        }
        File file = new File(context.getFilesDir(), FILE_NAME);
        if (file.exists()) {
            //noinspection ResultOfMethodCallIgnored
            file.delete();
        }
    }

    static synchronized List<Prototype> teach(Context context,
                                              String label,
                                              PatentReverseImageEngine.VisualSignature sig,
                                              String source,
                                              String patentRef,
                                              String dimensionsNote) {
        List<Prototype> current = loadAll(context);
        List<Prototype> next = teachOrReinforce(
                current, label, sig, source, patentRef, dimensionsNote, System.currentTimeMillis());
        saveAll(context, next);
        return next;
    }

    /**
     * Pure JVM-testable merge of workstation-refined visual prototypes back into local offline memory.
     * Never downgrades a stronger local user_confirmed prototype while adopting Haeckel/CPC enrichments
     * and newly consolidated prototypes from Zoe's workstation L5 digestion loop.
     */
    static List<Prototype> mergeRefined(List<Prototype> local, List<Prototype> refined) {
        List<Prototype> merged = local == null ? new ArrayList<>() : new ArrayList<>(local);
        if (refined == null || refined.isEmpty()) {
            return merged;
        }
        for (Prototype incoming : refined) {
            if (incoming == null || incoming.signature == null || incoming.label.isEmpty()) {
                continue;
            }
            int idx = -1;
            for (int i = 0; i < merged.size(); i++) {
                if (merged.get(i).label.equalsIgnoreCase(incoming.label)) {
                    idx = i;
                    break;
                }
            }
            if (idx >= 0) {
                Prototype cur = merged.get(idx);
                String bestSource = "user_confirmed".equals(cur.source) || "user_confirmed".equals(incoming.source)
                        ? "user_confirmed" : incoming.source;
                String bestPat = !cur.patentRef.isEmpty() ? cur.patentRef : incoming.patentRef;
                String bestDims = !cur.dimensionsNote.isEmpty() ? cur.dimensionsNote : incoming.dimensionsNote;
                boolean adoptIncomingSig = incoming.confirmCount > cur.confirmCount
                        || (!"user_confirmed".equals(cur.source) && incoming.updatedAtMs >= cur.updatedAtMs);
                PatentReverseImageEngine.VisualSignature bestSig = adoptIncomingSig ? incoming.signature : cur.signature;
                int bestCount = Math.max(cur.confirmCount, incoming.confirmCount);
                long bestUpdated = Math.max(cur.updatedAtMs, incoming.updatedAtMs);
                merged.set(idx, new Prototype(cur.label, bestSource, bestPat, bestDims, bestSig, bestCount, bestUpdated));
            } else if (merged.size() < MAX_PROTOTYPES) {
                merged.add(incoming);
            }
        }
        return merged;
    }

    static synchronized int mergeRefinedFromWorkstation(Context context, List<Prototype> refined) {
        if (context == null || refined == null || refined.isEmpty()) {
            return 0;
        }
        List<Prototype> current = loadAll(context);
        List<Prototype> next = mergeRefined(current, refined);
        saveAll(context, next);
        return next.size();
    }

    static MatchResult matchSignature(Context context,
                                      PatentReverseImageEngine.VisualSignature sig,
                                      float minScore) {
        if (context == null || sig == null) {
            return null;
        }
        return findBestMatchWithAtlas(loadAll(context), loadBaselineAtlas(context), sig, minScore, ATLAS_MIN_SCORE);
    }

    /**
     * Silent helper for Zoe Explore: checks user learned memory + clean-room offline structural atlas
     * in <0.1ms RAM-cached lookup and returns a brief context line for Zoe's brain (never UI popups!).
     */
    static String buildSilentExploreContext(Context context, Bitmap liveFrame) {
        if (context == null || liveFrame == null || liveFrame.isRecycled()) {
            return "";
        }
        List<Prototype> stored = loadAll(context);
        List<Prototype> atlas = loadBaselineAtlas(context);
        if (stored.isEmpty() && atlas.isEmpty()) {
            return "";
        }
        PatentReverseImageEngine.VisualSignature sig =
                PatentReverseImageEngine.extractFromBitmap(liveFrame, true);
        MatchResult match = findBestMatchWithAtlas(stored, atlas, sig, DEFAULT_MIN_SCORE, ATLAS_MIN_SCORE);
        return match == null ? "" : match.formatSilentPromptHint();
    }

    private static String floatArrayJson(float[] arr) {
        StringBuilder sb = new StringBuilder("[");
        for (int i = 0; i < arr.length; i++) {
            if (i > 0) sb.append(',');
            sb.append(String.format(Locale.US, "%.4f", arr[i]));
        }
        sb.append(']');
        return sb.toString();
    }

    private static float[] parseFloatArray(List<Object> arr, int expectedLen) {
        if (arr == null || arr.size() != expectedLen) {
            return null;
        }
        float[] out = new float[expectedLen];
        for (int i = 0; i < expectedLen; i++) {
            out[i] = asFloat(arr.get(i), 0f);
        }
        return out;
    }

    private static float asFloat(Object obj, float def) {
        if (obj instanceof Number) {
            return ((Number) obj).floatValue();
        }
        if (obj != null) {
            try {
                return Float.parseFloat(obj.toString());
            } catch (NumberFormatException ignored) {
            }
        }
        return def;
    }

    private static long asLong(Object obj, long def) {
        if (obj instanceof Number) {
            return ((Number) obj).longValue();
        }
        if (obj != null) {
            try {
                return Long.parseLong(obj.toString());
            } catch (NumberFormatException ignored) {
            }
        }
        return def;
    }

    private static long parseUnsignedHex(String hex) {
        if (hex == null || hex.trim().isEmpty()) {
            return 0L;
        }
        try {
            return Long.parseUnsignedLong(hex.trim(), 16);
        } catch (NumberFormatException ignored) {
            return 0L;
        }
    }

    private static String jsonStr(String s) {
        if (s == null) return "\"\"";
        StringBuilder sb = new StringBuilder("\"");
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            switch (c) {
                case '"' -> sb.append("\\\"");
                case '\\' -> sb.append("\\\\");
                case '\n' -> sb.append("\\n");
                case '\r' -> sb.append("\\r");
                case '\t' -> sb.append("\\t");
                default -> {
                    if (c >= 0x20) sb.append(c);
                }
            }
        }
        sb.append('"');
        return sb.toString();
    }
}
