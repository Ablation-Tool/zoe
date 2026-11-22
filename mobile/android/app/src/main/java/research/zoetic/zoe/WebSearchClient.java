package research.zoetic.zoe;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

/**
 * Opt-in Live Web Grounding Client for Zoe (v0.5.0-beta).
 *
 * Strictly IDLE until the user explicitly turns on `Web: on` inside Zoe Chat.
 * Zero API keys required, zero trackers, zero ads, HTTPS-only:
 *   1. DuckDuckGo Instant Answer API (https://api.duckduckgo.com/)
 *   2. Wikipedia Open Search API (https://en.wikipedia.org/w/api.php)
 *
 * Returns concise verified snippets and clickable HTTPS source badges that ground
 * BOTH on-device Zoe Local models and Cloud AI providers (Gemini/Claude/ChatGPT/Grok).
 */
final class WebSearchClient {
    private static final int MAX_RESPONSE_BYTES = 512 * 1024;
    private static final int MAX_SOURCES = 4;

    static final class Source {
        final String title;
        final String snippet;
        final String url;
        final String domain;

        Source(String title, String snippet, String url, String domain) {
            this.title = title == null ? "" : title.trim();
            this.snippet = snippet == null ? "" : snippet.trim();
            this.url = url == null ? "" : url.trim();
            this.domain = domain == null ? "" : domain.trim();
        }

        String badgeEntry() {
            String label = domain.isEmpty() ? title : (domain + " · " + title);
            if (label.length() > 44) {
                label = label.substring(0, 43) + "…";
            }
            return label + "|" + url;
        }
    }

    static final class SearchResult {
        final String query;
        final List<Source> sources;
        final long latencyMs;

        SearchResult(String query, List<Source> sources, long latencyMs) {
            this.query = query == null ? "" : query;
            this.sources = sources == null ? new ArrayList<>() : sources;
            this.latencyMs = Math.max(0L, latencyMs);
        }

        boolean hasSources() {
            return !sources.isEmpty();
        }

        List<String> toSourceBadges() {
            List<String> out = new ArrayList<>();
            for (Source s : sources) {
                if (isSafeWebUrl(s.url)) {
                    out.add(s.badgeEntry());
                }
            }
            return out;
        }

        String formatContextForPrompt(int maxChars) {
            if (sources.isEmpty()) {
                return "";
            }
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < sources.size(); i++) {
                Source s = sources.get(i);
                String entry = "[" + (i + 1) + "] " + s.title + " (" + s.domain + "): " + s.snippet + "\n";
                if (sb.length() + entry.length() > maxChars) {
                    break;
                }
                sb.append(entry);
            }
            return sb.toString().trim();
        }

        String formatFallbackAnswer() {
            if (sources.isEmpty()) {
                return "Live Web search found no direct public encyclopedia summary for \"" + query + "\".";
            }
            StringBuilder sb = new StringBuilder("Here is what live public web sources report for \"")
                    .append(query).append("\":\n\n");
            for (int i = 0; i < sources.size(); i++) {
                Source s = sources.get(i);
                sb.append(i + 1).append(". ").append(s.title).append(" — ").append(s.snippet).append("\n\n");
            }
            sb.append("Tap any source chip below to read the original page directly.");
            return sb.toString().trim();
        }
    }

    private WebSearchClient() {
    }

    static boolean isSafeWebUrl(String url) {
        return url != null && url.trim().toLowerCase(Locale.US).startsWith("https://");
    }

    static String cleanSearchQuery(String raw) {
        if (raw == null) {
            return "";
        }
        String q = raw.trim().replaceAll("\\s+", " ");
        String lower = q.toLowerCase(Locale.US);
        String[] prefixes = {
                "search the web for ", "search web for ", "web search for ", "search for ",
                "look up ", "find info on ", "what is the latest on ", "tell me about ",
                "explain ", "who is ", "what is ", "what are ", "where is ", "when was "
        };
        for (String p : prefixes) {
            if (lower.startsWith(p) && q.length() > p.length() + 1) {
                q = q.substring(p.length()).trim();
                lower = q.toLowerCase(Locale.US);
                break;
            }
        }
        q = q.replaceAll("[?!.]+$", "").trim();
        return q.length() > 120 ? q.substring(0, 120).trim() : q;
    }

    static String stripHtml(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.replaceAll("<[^>]+>", " ")
                .replace("&quot;", "\"")
                .replace("&amp;", "&")
                .replace("&#039;", "'")
                .replace("&lt;", "<")
                .replace("&gt;", ">")
                .replaceAll("\\s+", " ")
                .trim();
    }

    static String extractDomain(String url) {
        if (!isSafeWebUrl(url)) {
            return "web";
        }
        try {
            String host = new URL(url).getHost();
            if (host == null || host.isEmpty()) {
                return "web";
            }
            if (host.startsWith("www.")) {
                host = host.substring(4);
            }
            if (host.startsWith("en.wikipedia.org")) {
                return "Wikipedia";
            }
            return host;
        } catch (Exception ignored) {
            return "web";
        }
    }

    static List<Source> parseDuckDuckGoJson(String json) {
        List<Source> out = new ArrayList<>();
        if (json == null || json.trim().isEmpty()) {
            return out;
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(json);
            String heading = MiniJson.asString(root, "Heading", "").trim();
            String abstractText = stripHtml(MiniJson.asString(root, "AbstractText", ""));
            String abstractUrl = MiniJson.asString(root, "AbstractURL", "").trim();
            if (!abstractText.isEmpty() && isSafeWebUrl(abstractUrl)) {
                out.add(new Source(
                        heading.isEmpty() ? "Instant Summary" : heading,
                        trimSnippet(abstractText, 240),
                        abstractUrl,
                        extractDomain(abstractUrl)));
            }
            List<Object> topics = MiniJson.asArray(root.get("RelatedTopics"));
            if (topics != null) {
                for (Object item : topics) {
                    if (out.size() >= 2) {
                        break;
                    }
                    Map<String, Object> m = MiniJson.asObject(item);
                    if (m == null) {
                        continue;
                    }
                    String text = stripHtml(MiniJson.asString(m, "Text", ""));
                    String firstUrl = MiniJson.asString(m, "FirstURL", "").trim();
                    if (!text.isEmpty() && isSafeWebUrl(firstUrl)) {
                        String title = text.contains(" - ") ? text.substring(0, text.indexOf(" - ")).trim() : trimSnippet(text, 44);
                        out.add(new Source(title, trimSnippet(text, 200), firstUrl, extractDomain(firstUrl)));
                    }
                }
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    static List<Source> parseWikipediaSearchJson(String json) {
        List<Source> out = new ArrayList<>();
        if (json == null || json.trim().isEmpty()) {
            return out;
        }
        try {
            Map<String, Object> root = MiniJson.parseObject(json);
            Map<String, Object> query = MiniJson.asObject(root.get("query"));
            List<Object> search = MiniJson.asArray(query == null ? null : query.get("search"));
            if (search == null) {
                return out;
            }
            for (Object item : search) {
                if (out.size() >= 3) {
                    break;
                }
                Map<String, Object> m = MiniJson.asObject(item);
                if (m == null) {
                    continue;
                }
                String title = MiniJson.asString(m, "title", "").trim();
                String snippet = stripHtml(MiniJson.asString(m, "snippet", ""));
                if (title.isEmpty() || snippet.isEmpty()) {
                    continue;
                }
                String url = "https://en.wikipedia.org/wiki/" + urlEncodePath(title.replace(' ', '_'));
                out.add(new Source(title, trimSnippet(snippet, 220), url, "Wikipedia"));
            }
        } catch (Exception ignored) {
        }
        return out;
    }

    static SearchResult search(String rawQuery) {
        long t0 = System.currentTimeMillis();
        String cleaned = cleanSearchQuery(rawQuery);
        List<Source> combined = new ArrayList<>();
        Set<String> seenUrls = new LinkedHashSet<>();
        if (cleaned.isEmpty()) {
            return new SearchResult("", combined, 0L);
        }

        // 1. DuckDuckGo Instant Answer API (zero key, zero tracking)
        try {
            String ddgUrl = "https://api.duckduckgo.com/?q=" + urlEncode(cleaned)
                    + "&format=json&no_html=1&skip_disambig=1";
            String json = getHttps(ddgUrl);
            for (Source s : parseDuckDuckGoJson(json)) {
                if (combined.size() < MAX_SOURCES && seenUrls.add(s.url.toLowerCase(Locale.US))) {
                    combined.add(s);
                }
            }
        } catch (Exception ignored) {
        }

        // 2. Wikipedia Open Search API (zero key, open encyclopedia grounding)
        try {
            String wikiUrl = "https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch="
                    + urlEncode(cleaned) + "&srlimit=3&utf8=1&format=json";
            String json = getHttps(wikiUrl);
            for (Source s : parseWikipediaSearchJson(json)) {
                if (combined.size() < MAX_SOURCES && seenUrls.add(s.url.toLowerCase(Locale.US))) {
                    combined.add(s);
                }
            }
        } catch (Exception ignored) {
        }

        return new SearchResult(cleaned, combined, System.currentTimeMillis() - t0);
    }

    private static String getHttps(String endpointUrl) throws IOException {
        if (!isSafeWebUrl(endpointUrl)) {
            throw new IOException("Only HTTPS web search endpoints are permitted");
        }
        HttpURLConnection conn = (HttpURLConnection) new URL(endpointUrl).openConnection();
        conn.setConnectTimeout(8_000);
        conn.setReadTimeout(10_000);
        conn.setRequestMethod("GET");
        conn.setRequestProperty("User-Agent", "ZoeMobile/0.5 (https://github.com/Ablation-Tool/zoe)");
        conn.setRequestProperty("Accept", "application/json");
        int code = conn.getResponseCode();
        InputStream stream = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
        String body = readBounded(stream);
        conn.disconnect();
        if (code < 200 || code >= 300) {
            throw new IOException("Web search HTTP " + code);
        }
        return body;
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
                throw new IOException("Web search response exceeded 512 KiB");
            }
            out.write(buf, 0, read);
        }
        return out.toString("UTF-8");
    }

    private static String trimSnippet(String text, int max) {
        if (text == null) {
            return "";
        }
        String t = text.trim();
        return t.length() > max ? t.substring(0, max - 1).trim() + "…" : t;
    }

    private static String urlEncode(String s) {
        try {
            return URLEncoder.encode(s, "UTF-8");
        } catch (Exception ignored) {
            return s;
        }
    }

    private static String urlEncodePath(String s) {
        try {
            return URLEncoder.encode(s, "UTF-8").replace("+", "%20").replace("%2F", "/");
        } catch (Exception ignored) {
            return s;
        }
    }
}
