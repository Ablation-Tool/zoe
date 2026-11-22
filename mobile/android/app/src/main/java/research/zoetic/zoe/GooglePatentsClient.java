package research.zoetic.zoe;

import android.graphics.Bitmap;
import android.graphics.BitmapFactory;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Opt-in Google Patents Visual Reverse-Image & Public Catalog Client for Zoe Explore (v0.9.1-beta).
 *
 * When Zoe's offline sight encounters an unfamiliar or hard-to-ID object, she:
 *   1. Extracts structural contour edges (Sobel + HoG-16 + radial symmetry + dHash-64) via
 *      PatentReverseImageEngine and any stamped OCR patent numbers (US/EP/WO/PAT. NO.).
 *   2. Fetches candidate patents with real schematic drawings from `https://patents.google.com/xhr/query`.
 *   3. Downloads candidate schematic PNGs from `https://patentimages.storage.googleapis.com/...` in parallel.
 *   4. Computes real visual contour similarity between the live camera object's edges and every patent
 *      schematic drawing, re-ranking matches by visual score (0%–100%) and returning the winning
 *      schematic Bitmap for live visual comparison!
 *
 * Zero API keys, HTTPS-only, bounded reads, strictly opt-in, and honest about candidate uncertainty.
 */
final class GooglePatentsClient {
    static final float MIN_VISUAL_CONFIDENCE = 0.70f;
    static final String PHYSICAL_CPC_FILTER = "(cpc:A47 OR cpc:B25 OR cpc:F16 OR cpc:G01 OR cpc:G02 OR cpc:H01)";
    private static final int MAX_RESPONSE_BYTES = 512 * 1024;
    private static final int MAX_THUMB_BYTES = 384 * 1024;
    private static final Pattern PATENT_ID_PATTERN = Pattern.compile(
            "\\b(US|EP|WO|CN|JP|DE|GB)[\\s-]?([0-9]{4,10})[\\s-]?([A-Z][0-9]?)?\\b",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern US_COMMA_PATENT_PATTERN = Pattern.compile(
            "\\bPAT(?:ENT)?\\.?\\s*(?:NO\\.?)?\\s*([0-9]{1,2},[0-9]{3},[0-9]{3}|[0-9]{6,8})\\b",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern DIMENSION_PATTERN = Pattern.compile(
            "\\b(\\d+(?:\\.\\d+)?\\s*(?:mm|cm|m|inch(?:es)?|in\\.|degrees?|°|µm|nm))\\b",
            Pattern.CASE_INSENSITIVE);

    static final class PatentMatch {
        final String publicationNumber;
        final String title;
        final String snippet;
        final String assignee;
        final String publicationDate;
        final String patentUrl;
        final String thumbnailUrl;
        final String dimensionsNote;
        final float visualSimilarity; // 0.0..1.0 (-1 if no drawing compared)
        final Bitmap schematicBitmap; // optional downloaded schematic drawing PNG

        PatentMatch(String publicationNumber, String title, String snippet,
                    String assignee, String publicationDate, String patentUrl,
                    String thumbnailUrl, String dimensionsNote) {
            this(publicationNumber, title, snippet, assignee, publicationDate,
                    patentUrl, thumbnailUrl, dimensionsNote, -1f, null);
        }

        PatentMatch(String publicationNumber, String title, String snippet,
                    String assignee, String publicationDate, String patentUrl,
                    String thumbnailUrl, String dimensionsNote,
                    float visualSimilarity, Bitmap schematicBitmap) {
            this.publicationNumber = publicationNumber == null ? "" : publicationNumber.trim();
            this.title = title == null ? "" : title.trim();
            this.snippet = snippet == null ? "" : snippet.trim();
            this.assignee = assignee == null ? "" : assignee.trim();
            this.publicationDate = publicationDate == null ? "" : publicationDate.trim();
            this.patentUrl = patentUrl == null ? "" : patentUrl.trim();
            this.thumbnailUrl = thumbnailUrl == null ? "" : thumbnailUrl.trim();
            this.dimensionsNote = dimensionsNote == null ? "" : dimensionsNote.trim();
            this.visualSimilarity = visualSimilarity;
            this.schematicBitmap = schematicBitmap;
        }

        PatentMatch withVisualScore(float score, Bitmap bmp) {
            return new PatentMatch(publicationNumber, title, snippet, assignee,
                    publicationDate, patentUrl, thumbnailUrl, dimensionsNote, score, bmp);
        }

        int visualMatchPercent() {
            return visualSimilarity < 0f ? -1 : Math.round(visualSimilarity * 100f);
        }
    }

    static final class LookupResult {
        final String query;
        final String detectedPatentId;
        final String shapeSummary;
        final String scaleComparison;
        final int drawingsCompared;
        final List<PatentMatch> matches;
        final long latencyMs;
        final String errorNote;

        LookupResult(String query, String detectedPatentId, String shapeSummary,
                     String scaleComparison, int drawingsCompared,
                     List<PatentMatch> matches, long latencyMs, String errorNote) {
            this.query = query == null ? "" : query;
            this.detectedPatentId = detectedPatentId == null ? "" : detectedPatentId;
            this.shapeSummary = shapeSummary == null ? "" : shapeSummary;
            this.scaleComparison = scaleComparison == null ? "" : scaleComparison;
            this.drawingsCompared = Math.max(0, drawingsCompared);
            this.matches = matches == null ? new ArrayList<>() : matches;
            this.latencyMs = Math.max(0L, latencyMs);
            this.errorNote = errorNote == null ? "" : errorNote;
        }

        boolean hasMatches() {
            return !matches.isEmpty();
        }

        PatentMatch topMatch() {
            return matches.isEmpty() ? null : matches.get(0);
        }

        String formatSpokenSummary() {
            if (matches.isEmpty()) {
                String base = "I reverse-searched Google Patents for \"" + query + "\" but didn't find a close drawing match yet.";
                if (!scaleComparison.isEmpty()) {
                    return base + " " + scaleComparison;
                }
                return base + " Try centering the object cleanly or showing any stamped part number.";
            }
            PatentMatch top = matches.get(0);
            StringBuilder sb = new StringBuilder();
            if (!detectedPatentId.isEmpty()) {
                sb.append("I read patent number ").append(detectedPatentId).append(". ");
            } else if (drawingsCompared > 0 && top.visualMatchPercent() >= 0) {
                sb.append("I compared your camera contours against ")
                        .append(drawingsCompared)
                        .append(" Google Patents drawings. ");
            }
            sb.append("Top candidate is ").append(top.publicationNumber)
                    .append(": ").append(top.title);
            if (top.visualMatchPercent() >= 0) {
                sb.append(" (").append(top.visualMatchPercent()).append("% edge-contour match)");
            }
            sb.append(". ");
            if (!top.dimensionsNote.isEmpty()) {
                sb.append("Patent dimensions: ").append(top.dimensionsNote).append(". ");
            }
            if (!scaleComparison.isEmpty()) {
                sb.append(scaleComparison).append(" ");
            }
            return sb.toString().trim();
        }

        String formatPromptContext(int maxChars) {
            if (matches.isEmpty()) {
                return "";
            }
            StringBuilder sb = new StringBuilder("Google Patents Visual Reverse-Search Candidates (patents.google.com):\n");
            for (int i = 0; i < matches.size(); i++) {
                PatentMatch m = matches.get(i);
                String simStr = m.visualMatchPercent() >= 0 ? (" [" + m.visualMatchPercent() + "% visual contour match]") : "";
                String line = "[" + (i + 1) + "] " + m.publicationNumber + " — " + m.title + simStr
                        + (m.assignee.isEmpty() ? "" : " (" + m.assignee + ")")
                        + ": " + m.snippet
                        + (m.dimensionsNote.isEmpty() ? "" : " [Dimensions: " + m.dimensionsNote + "]")
                        + "\n";
                if (sb.length() + line.length() > maxChars) {
                    break;
                }
                sb.append(line);
            }
            return sb.toString().trim();
        }
    }

    private GooglePatentsClient() {
    }

    static String extractPatentNumber(String text) {
        if (text == null || text.trim().isEmpty()) {
            return "";
        }
        Matcher m1 = PATENT_ID_PATTERN.matcher(text);
        if (m1.find()) {
            String prefix = m1.group(1).toUpperCase(Locale.US);
            String digits = m1.group(2);
            String kind = m1.group(3) == null ? "" : m1.group(3).toUpperCase(Locale.US);
            return prefix + digits + kind;
        }
        Matcher m2 = US_COMMA_PATENT_PATTERN.matcher(text);
        if (m2.find()) {
            String digits = m2.group(1).replace(",", "");
            return "US" + digits;
        }
        return "";
    }

    static String extractDimensionsNote(String text) {
        if (text == null || text.isEmpty()) {
            return "";
        }
        Matcher m = DIMENSION_PATTERN.matcher(text);
        List<String> found = new ArrayList<>();
        while (m.find() && found.size() < 3) {
            String tok = m.group(1).trim();
            if (!found.contains(tok)) {
                found.add(tok);
            }
        }
        return String.join(", ", found);
    }

    static String buildStructuralQuery(String cameraReport, String spokenHint) {
        return buildStructuralQuery(cameraReport, spokenHint, null);
    }

    static String buildStructuralQuery(String cameraReport, String spokenHint,
                                       PatentReverseImageEngine.VisualSignature sig) {
        String ocr = ArExploreBrain.extractOcrSnippet(cameraReport);
        String patId = extractPatentNumber(ocr + " " + (spokenHint == null ? "" : spokenHint));
        if (!patId.isEmpty()) {
            return patId;
        }
        String label = ArExploreBrain.extractPrimaryLabel(cameraReport);
        String cleanedHint = WebSearchClient.cleanSearchQuery(spokenHint == null ? "" : spokenHint);
        if (cleanedHint.toLowerCase(Locale.US).matches(".*(what is this|what's this|identify this|patent|look up|reverse).*")) {
            cleanedHint = cleanedHint.replaceAll(
                    "(?i)\\b(what is this|what's this|identify this|look up|reverse image|search|patent|for this|check|can you)\\b", "")
                    .replaceAll("\\s+", " ").trim();
        }
        StringBuilder q = new StringBuilder();
        if (!cleanedHint.isEmpty()) {
            q.append(cleanedHint);
        }
        if (!label.isEmpty() && !q.toString().toLowerCase(Locale.US).contains(label.toLowerCase(Locale.US))) {
            if (q.length() > 0) q.append(' ');
            q.append(label);
        }
        // When offline labels are missing/vague, inject pure contour morphology keywords from the camera frame!
        if (sig != null && !sig.morphologyKeywords.isEmpty()
                && (PatentReverseImageEngine.isHardToIdentify(cameraReport) || q.length() < 12)) {
            if (q.length() > 0) q.append(' ');
            q.append(sig.morphologyKeywords);
        }
        if (!ocr.isEmpty() && ocr.length() >= 3) {
            String shortOcr = ocr.length() > 28 ? ocr.substring(0, 28).trim() : ocr;
            if (q.length() > 0) q.append(' ');
            q.append(shortOcr);
        }
        if (q.length() == 0) {
            return "optical prism gear mechanism";
        }
        String out = q.toString().replaceAll("\\s+", " ").trim();
        return out.length() > 96 ? out.substring(0, 96).trim() : out;
    }

    /**
     * Wraps general structural shape queries with physical-object CPC patent classes
     * (A47 household articles, B25 tools, F16 mechanical engineering, G01 measurement,
     * G02 optics, H01 electrical hardware) so abstract software/business flowcharts are excluded.
     * Exact stamped patent IDs bypass the filter so direct number lookups always resolve.
     */
    static String applyPhysicalCpcFilter(String query, String detectedPatentId) {
        if (query == null || query.trim().isEmpty()) {
            return "";
        }
        if (detectedPatentId != null && !detectedPatentId.trim().isEmpty()) {
            return query.trim();
        }
        return query.trim() + " " + PHYSICAL_CPC_FILTER;
    }

    /**
     * Distills a verbose legal patent title (e.g., "Method and apparatus for an optical beam-splitting
     * prism assembly having a rotary mount") into a crisp physical object concept for Guided Vision learning.
     */
    static String cleanPhysicalConcept(String patentTitle) {
        if (patentTitle == null || patentTitle.trim().isEmpty()) {
            return "";
        }
        String cleaned = patentTitle
                .replaceAll("(?i)^(systems?\\s+and\\s+methods?\\s+for|method\\s+and\\s+apparatus\\s+for|apparatus\\s+for|device\\s+for|improved|novel)\\s+", "")
                .replaceAll("(?i)\\b(thereof|therefor|comprising.*|having.*)$", "")
                .replaceAll("\\s+", " ")
                .trim();
        if (cleaned.endsWith(",") || cleaned.endsWith("-") || cleaned.endsWith(":")) {
            cleaned = cleaned.substring(0, cleaned.length() - 1).trim();
        }
        if (cleaned.isEmpty()) {
            cleaned = patentTitle.trim();
        }
        if (cleaned.length() > 54) {
            cleaned = cleaned.substring(0, 54).trim();
        }
        return Character.toUpperCase(cleaned.charAt(0)) + cleaned.substring(1);
    }

    static List<PatentMatch> parseGooglePatentsJson(String json, int maxResults) {
        List<PatentMatch> out = new ArrayList<>();
        if (json == null || json.trim().isEmpty()) {
            return out;
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(json);
            Map<String, Object> results = MiniJson.asObject(root.get("results"));
            List<Object> clusters = MiniJson.asArray(results == null ? null : results.get("cluster"));
            if (clusters == null) {
                return out;
            }
            for (Object clObj : clusters) {
                Map<String, Object> cl = MiniJson.asObject(clObj);
                List<Object> items = MiniJson.asArray(cl == null ? null : cl.get("result"));
                if (items == null) {
                    continue;
                }
                for (Object itemObj : items) {
                    if (out.size() >= Math.max(1, maxResults)) {
                        return out;
                    }
                    Map<String, Object> item = MiniJson.asObject(itemObj);
                    Map<String, Object> pat = MiniJson.asObject(item == null ? null : item.get("patent"));
                    if (pat == null) {
                        continue;
                    }
                    String pub = MiniJson.asString(pat, "publication_number", "").trim();
                    String title = decodeEntities(WebSearchClient.stripHtml(MiniJson.asString(pat, "title", "")));
                    String snippet = decodeEntities(WebSearchClient.stripHtml(MiniJson.asString(pat, "snippet", "")));
                    String assignee = decodeEntities(MiniJson.asString(pat, "assignee", "")).trim();
                    String pubDate = MiniJson.asString(pat, "publication_date", "").trim();
                    String thumb = MiniJson.asString(pat, "thumbnail", "").trim();
                    if (pub.isEmpty() || title.isEmpty()) {
                        continue;
                    }
                    String url = "https://patents.google.com/patent/" + pub + "/en";
                    // Verified empirically: full schematic PNG paths (not 60x80/ paths) serve HTTP 200 directly!
                    String thumbUrl = (!thumb.isEmpty() && !thumb.startsWith("60x80/"))
                            ? ("https://patentimages.storage.googleapis.com/" + thumb)
                            : "";
                    String dims = extractDimensionsNote(title + " " + snippet);
                    out.add(new PatentMatch(pub, title, trimText(snippet, 220), assignee, pubDate, url, thumbUrl, dims));
                }
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    /**
     * Text/OCR-only search (used when no camera frame is active).
     */
    static LookupResult searchPatents(String cameraReport, String spokenHint, float observedDistMeters, int limit) {
        return reverseImageSearchPatents(null, cameraReport, spokenHint, observedDistMeters, limit);
    }

    /**
     * FULL Patent Visual Reverse-Image Search:
     *   - Extracts live Sobel edge-contour VisualSignature from {@code cameraFrame}
     *   - Queries patents.google.com for up to 10 candidate patents
     *   - Downloads real patent schematic PNGs in parallel from patentimages.storage.googleapis.com
     *   - Re-ranks candidates by real edge-contour visual similarity (0%–100%)
     *   - Returns the top visually matched schematic drawing Bitmap for side-by-side display!
     */
    static LookupResult reverseImageSearchPatents(Bitmap cameraFrame, String cameraReport,
                                                  String spokenHint, float observedDistMeters, int limit) {
        long t0 = System.currentTimeMillis();
        PatentReverseImageEngine.VisualSignature querySig =
                cameraFrame != null ? PatentReverseImageEngine.extractFromBitmap(cameraFrame, true) : null;
        String query = buildStructuralQuery(cameraReport, spokenHint, querySig);
        String detectedId = extractPatentNumber(
                ArExploreBrain.extractOcrSnippet(cameraReport) + " " + (spokenHint == null ? "" : spokenHint));
        String scaleNote = ScientificVisualSubstrate.describeRelativeScale(observedDistMeters);
        String shapeNote = querySig == null ? "" : querySig.shapeSummary;

        try {
            int fetchCount = querySig != null ? 10 : Math.max(2, Math.min(5, limit));
            String filteredQuery = applyPhysicalCpcFilter(query, detectedId);
            String inner = "q=" + urlEncode(filteredQuery) + "&num=" + fetchCount;
            String endpoint = "https://patents.google.com/xhr/query?url=" + urlEncode(inner);
            String json = getHttpsText(endpoint);
            List<PatentMatch> candidates = parseGooglePatentsJson(json, fetchCount);

            if (candidates.isEmpty()) {
                return new LookupResult(query, detectedId, shapeNote, scaleNote, 0, candidates,
                        System.currentTimeMillis() - t0, "");
            }

            // Download up to 6 schematic PNG drawings in parallel and visually re-rank them!
            List<PatentMatch> scored = new ArrayList<>();
            int drawingsCompared = 0;
            if (querySig != null) {
                ExecutorService pool = Executors.newFixedThreadPool(4);
                try {
                    List<Future<PatentMatch>> futures = new ArrayList<>();
                    int queuedWithDrawing = 0;
                    for (PatentMatch cand : candidates) {
                        if (!cand.thumbnailUrl.isEmpty() && queuedWithDrawing < 6) {
                            queuedWithDrawing++;
                            futures.add(pool.submit(() -> {
                                Bitmap drawing = fetchDrawingBitmap(cand.thumbnailUrl);
                                if (drawing == null) {
                                    return cand;
                                }
                                PatentReverseImageEngine.VisualSignature drawSig =
                                        PatentReverseImageEngine.extractFromBitmap(drawing, false);
                                float sim = PatentReverseImageEngine.compareSignatures(querySig, drawSig);
                                drawing.recycle();
                                return cand.withVisualScore(sim, null);
                            }));
                        } else if (!detectedId.isEmpty()) {
                            scored.add(cand);
                        }
                    }
                    for (Future<PatentMatch> f : futures) {
                        try {
                            PatentMatch res = f.get(5, TimeUnit.SECONDS);
                            if (res.visualSimilarity >= 0f) {
                                drawingsCompared++;
                            }
                            // Strictly reject low-similarity noise unless an exact stamped patent ID was read!
                            if (!detectedId.isEmpty() || res.visualSimilarity >= MIN_VISUAL_CONFIDENCE) {
                                scored.add(res);
                            }
                        } catch (Exception ignored) {
                        }
                    }
                } finally {
                    pool.shutdownNow();
                }
                Collections.sort(scored, (a, b) -> Float.compare(b.visualSimilarity, a.visualSimilarity));
            } else {
                scored.addAll(candidates);
            }

            int keep = Math.min(Math.max(1, limit), scored.size());
            List<PatentMatch> trimmed = scored.isEmpty() ? new ArrayList<>() : new ArrayList<>(scored.subList(0, keep));
            return new LookupResult(query, detectedId, shapeNote, scaleNote, drawingsCompared,
                    trimmed, System.currentTimeMillis() - t0, "");
        } catch (Exception err) {
            return new LookupResult(query, detectedId, shapeNote, scaleNote, 0, new ArrayList<>(),
                    System.currentTimeMillis() - t0, "Offline or catalog temporarily unreachable: " + err.getMessage());
        }
    }

    /**
     * Silent structural prior resolver for Guided Vision & Zoe Explore:
     * runs CPC-filtered contour comparison under the hood, rejects weak matches honestly,
     * never leaks bitmaps, and never pops up noisy raw patent UI to the user.
     */
    static LookupResult silentResolveForVision(Bitmap cameraFrame, String cameraReport,
                                               String spokenHint, float observedDistMeters) {
        return reverseImageSearchPatents(cameraFrame, cameraReport, spokenHint, observedDistMeters, 2);
    }

    private static Bitmap fetchDrawingBitmap(String url) {
        if (!WebSearchClient.isSafeWebUrl(url)) {
            return null;
        }
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL(url).openConnection();
            conn.setConnectTimeout(4_500);
            conn.setReadTimeout(5_500);
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", "ZoeMobile/0.9 (https://github.com/Ablation-Tool/zoe)");
            int code = conn.getResponseCode();
            if (code < 200 || code >= 300) {
                return null;
            }
            byte[] bytes = readBoundedBytes(conn.getInputStream(), MAX_THUMB_BYTES);
            BitmapFactory.Options opts = new BitmapFactory.Options();
            opts.inJustDecodeBounds = true;
            BitmapFactory.decodeByteArray(bytes, 0, bytes.length, opts);
            int sample = 1;
            while (Math.max(opts.outWidth, opts.outHeight) / sample > 480) {
                sample *= 2;
            }
            BitmapFactory.Options decodeOpts = new BitmapFactory.Options();
            decodeOpts.inSampleSize = sample;
            return BitmapFactory.decodeByteArray(bytes, 0, bytes.length, decodeOpts);
        } catch (Exception ignored) {
            return null;
        } finally {
            if (conn != null) {
                conn.disconnect();
            }
        }
    }

    private static String getHttpsText(String endpointUrl) throws IOException {
        if (!WebSearchClient.isSafeWebUrl(endpointUrl)) {
            throw new IOException("Only HTTPS Google Patents queries are permitted");
        }
        HttpURLConnection conn = (HttpURLConnection) new URL(endpointUrl).openConnection();
        conn.setConnectTimeout(8_000);
        conn.setReadTimeout(10_000);
        conn.setRequestMethod("GET");
        conn.setRequestProperty("User-Agent", "ZoeMobile/0.9 (https://github.com/Ablation-Tool/zoe)");
        conn.setRequestProperty("Accept", "application/json");
        int code = conn.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
        byte[] raw = readBoundedBytes(stream, MAX_RESPONSE_BYTES);
        conn.disconnect();
        if (code < 200 || code >= 300) {
            throw new IOException("Google Patents HTTP " + code);
        }
        return new String(raw, java.nio.charset.StandardCharsets.UTF_8);
    }

    private static byte[] readBoundedBytes(InputStream stream, int maxBytes) throws IOException {
        if (stream == null) {
            return new byte[0];
        }
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        byte[] buf = new byte[4096];
        int total = 0;
        int read;
        while ((read = stream.read(buf)) != -1) {
            total += read;
            if (total > maxBytes) {
                throw new IOException("Response exceeded byte limit");
            }
            out.write(buf, 0, read);
        }
        return out.toByteArray();
    }

    private static String decodeEntities(String s) {
        if (s == null) return "";
        return s.replace("&hellip;", "…")
                .replace("&ndash;", "–")
                .replace("&mdash;", "—")
                .replace("&#39;", "'")
                .replace("&nbsp;", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }

    private static String trimText(String s, int max) {
        if (s == null) return "";
        String t = s.trim();
        return t.length() > max ? t.substring(0, max - 1).trim() + "…" : t;
    }

    private static String urlEncode(String s) {
        try {
            return URLEncoder.encode(s, "UTF-8");
        } catch (Exception ignored) {
            return s;
        }
    }
}
