package research.zoetic.zoe;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Opt-in Google Patents Public Catalog Client for Zoe Explore & Creative Studio (v0.9.0-beta).
 *
 * Strictly IDLE until the user explicitly taps `📐 Patent` or asks Zoe to look up an unfamiliar
 * mechanism with `Web: on`. Zero API keys, HTTPS-only, bounded 512 KiB reads:
 *   - Extracts stamped patent numbers straight from camera OCR (US / EP / WO / PAT. NO.)
 *   - Builds structural mechanism & geometry queries from camera visual observations + AR distance
 *   - Queries Google Patents public JSON endpoint (`https://patents.google.com/xhr/query`)
 *   - Extracts dimensional measurements (`mm`, `cm`, `inch`, `deg`) & schematic thumbnail links
 *   - Honestly labels results as candidate engineering matches (`measurement ≠ identity proof`).
 */
final class GooglePatentsClient {
    private static final int MAX_RESPONSE_BYTES = 512 * 1024;
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

        PatentMatch(String publicationNumber, String title, String snippet,
                    String assignee, String publicationDate, String patentUrl,
                    String thumbnailUrl, String dimensionsNote) {
            this.publicationNumber = publicationNumber == null ? "" : publicationNumber.trim();
            this.title = title == null ? "" : title.trim();
            this.snippet = snippet == null ? "" : snippet.trim();
            this.assignee = assignee == null ? "" : assignee.trim();
            this.publicationDate = publicationDate == null ? "" : publicationDate.trim();
            this.patentUrl = patentUrl == null ? "" : patentUrl.trim();
            this.thumbnailUrl = thumbnailUrl == null ? "" : thumbnailUrl.trim();
            this.dimensionsNote = dimensionsNote == null ? "" : dimensionsNote.trim();
        }
    }

    static final class LookupResult {
        final String query;
        final String detectedPatentId;
        final String scaleComparison;
        final List<PatentMatch> matches;
        final long latencyMs;
        final String errorNote;

        LookupResult(String query, String detectedPatentId, String scaleComparison,
                     List<PatentMatch> matches, long latencyMs, String errorNote) {
            this.query = query == null ? "" : query;
            this.detectedPatentId = detectedPatentId == null ? "" : detectedPatentId;
            this.scaleComparison = scaleComparison == null ? "" : scaleComparison;
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
                String base = "I checked the Google Patents catalog for \"" + query + "\" but didn't find a direct match yet.";
                if (!scaleComparison.isEmpty()) {
                    return base + " " + scaleComparison;
                }
                return base + " Try pointing closer to any stamped label or patent number.";
            }
            PatentMatch top = matches.get(0);
            StringBuilder sb = new StringBuilder();
            if (!detectedPatentId.isEmpty()) {
                sb.append("I spotted patent number ").append(detectedPatentId).append(". ");
            }
            sb.append("Closest Google Patents catalog candidate is ").append(top.publicationNumber)
                    .append(": ").append(top.title).append(". ");
            if (!top.dimensionsNote.isEmpty()) {
                sb.append("Referenced dimensions: ").append(top.dimensionsNote).append(". ");
            }
            if (!scaleComparison.isEmpty()) {
                sb.append(scaleComparison).append(" ");
            }
            sb.append("Tap the patent badge to inspect the schematic drawings directly.");
            return sb.toString().trim();
        }

        String formatPromptContext(int maxChars) {
            if (matches.isEmpty()) {
                return "";
            }
            StringBuilder sb = new StringBuilder("Google Patents Catalog Candidates (patents.google.com):\n");
            for (int i = 0; i < matches.size(); i++) {
                PatentMatch m = matches.get(i);
                String line = "[" + (i + 1) + "] " + m.publicationNumber + " — " + m.title
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

    /**
     * Detects stamped patent numbers straight out of camera OCR text (e.g., "PAT. 6,123,456" or "US10234567B2").
     */
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

    /**
     * Builds a structural Google Patents search query from Zoe Explore's offline camera labels, OCR text,
     * and optional spoken clue so Zoe can look up unfamiliar hardware, tools, optics, or mechanisms.
     */
    static String buildStructuralQuery(String cameraReport, String spokenHint) {
        String ocr = ArExploreBrain.extractOcrSnippet(cameraReport);
        String patId = extractPatentNumber(ocr + " " + (spokenHint == null ? "" : spokenHint));
        if (!patId.isEmpty()) {
            return patId;
        }
        String label = ArExploreBrain.extractPrimaryLabel(cameraReport);
        String cleanedHint = WebSearchClient.cleanSearchQuery(spokenHint == null ? "" : spokenHint);
        // Strip generic conversational fillers when building a mechanical catalog query
        if (cleanedHint.toLowerCase(Locale.US).matches(".*(what is this|what's this|identify this|patent|look up).*")) {
            cleanedHint = cleanedHint.replaceAll("(?i)\\b(what is this|what's this|identify this|look up|patent|for this|check)\\b", "")
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
        if (!ocr.isEmpty() && ocr.length() >= 3) {
            String shortOcr = ocr.length() > 32 ? ocr.substring(0, 32).trim() : ocr;
            if (q.length() > 0) q.append(' ');
            q.append(shortOcr);
        }
        if (q.length() == 0) {
            return "optical prism gear mechanism";
        }
        String out = q.toString().replaceAll("\\s+", " ").trim();
        return out.length() > 96 ? out.substring(0, 96).trim() : out;
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
                    String thumbUrl = thumb.isEmpty() ? "" : ("https://patentimages.storage.googleapis.com/" + thumb);
                    String dims = extractDimensionsNote(title + " " + snippet);
                    out.add(new PatentMatch(pub, title, trimText(snippet, 220), assignee, pubDate, url, thumbUrl, dims));
                }
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    static LookupResult searchPatents(String cameraReport, String spokenHint, float observedDistMeters, int limit) {
        long t0 = System.currentTimeMillis();
        String query = buildStructuralQuery(cameraReport, spokenHint);
        String detectedId = extractPatentNumber(
                ArExploreBrain.extractOcrSnippet(cameraReport) + " " + (spokenHint == null ? "" : spokenHint));
        String scaleNote = ScientificVisualSubstrate.describeRelativeScale(observedDistMeters);
        try {
            String inner = "q=" + urlEncode(query) + "&num=" + Math.max(1, Math.min(5, limit));
            String endpoint = "https://patents.google.com/xhr/query?url=" + urlEncode(inner);
            String json = getHttps(endpoint);
            List<PatentMatch> matches = parseGooglePatentsJson(json, limit);
            return new LookupResult(query, detectedId, scaleNote, matches, System.currentTimeMillis() - t0, "");
        } catch (Exception err) {
            return new LookupResult(query, detectedId, scaleNote, new ArrayList<>(),
                    System.currentTimeMillis() - t0, "Offline or catalog temporarily unreachable: " + err.getMessage());
        }
    }

    private static String getHttps(String endpointUrl) throws IOException {
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
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        if (stream != null) {
            byte[] buf = new byte[4096];
            int total = 0;
            int read;
            while ((read = stream.read(buf)) != -1) {
                total += read;
                if (total > MAX_RESPONSE_BYTES) {
                    conn.disconnect();
                    throw new IOException("Patent catalog response exceeded 512 KiB");
                }
                out.write(buf, 0, read);
            }
        }
        conn.disconnect();
        if (code < 200 || code >= 300) {
            throw new IOException("Google Patents HTTP " + code);
        }
        return out.toString("UTF-8");
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
