package research.zoetic.zoe;

import java.io.UnsupportedEncodingException;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Pure, deterministic OS & AI app bridge helpers for Zoe (v0.4.0-beta).
 *
 * Uses built-in phone telemetry and official OS intents (Google Maps, Apple Maps,
 * Android Personal Safety / Emergency Info, Flashlight, Clock Timer/Alarm, and zero-key
 * handoffs to installed Claude, Grok, ChatGPT, and Gemini apps) with zero tracking SDKs
 * and zero silent execution — every action requires an explicit user tap.
 */
final class OsToolsBridge {
    static final String GOOGLE_MAPS_PACKAGE = "com.google.android.apps.maps";
    static final String PIXEL_SAFETY_PACKAGE = "com.google.android.apps.safetyhub";
    static final String ANDROID_EMERGENCY_PACKAGE = "com.android.emergency";
    static final String CLAUDE_PACKAGE = "com.anthropic.claude";
    static final String GROK_PACKAGE = "ai.x.grok";
    static final String CHATGPT_PACKAGE = "com.openai.chatgpt";
    static final String GEMINI_PACKAGE = "com.google.android.apps.bard";

    enum ActionKind {
        NONE,
        NAVIGATE,
        MAP_SEARCH,
        OPEN_LOCATION,
        OPEN_SAFETY,
        TOGGLE_TORCH,
        SET_TIMER,
        SET_ALARM
    }

    static final class ActionSuggestion {
        final ActionKind kind;
        final String label;
        final String query;
        final int seconds;
        final int hour;
        final int minute;
        final boolean autoExecuted;

        ActionSuggestion(ActionKind kind, String label, String query, int seconds, int hour, int minute) {
            this.kind = kind;
            this.label = label == null ? "" : label;
            this.query = query == null ? "" : query;
            this.seconds = seconds;
            this.hour = hour;
            this.minute = minute;
            this.autoExecuted = false;
        }

        boolean isActionable() {
            return kind != ActionKind.NONE;
        }
    }

    private static final Pattern NAV_RE = Pattern.compile(
            "(?:navigate|directions|route|drive|walk|take me)\\s+(?:to|toward|towards)\\s+(.+)",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern SEARCH_RE = Pattern.compile(
            "(?:find|search maps for|locate|nearest|closest)\\s+(.+)",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern TIMER_RE = Pattern.compile(
            "(?:set|start)\\s+(?:a\\s+)?(?:timer\\s+(?:for\\s+)?)?(\\d{1,3})\\s*(second|sec|seconds|secs|minute|min|minutes|mins|hour|hr|hours|hrs)(?:\\s+timer)?",
            Pattern.CASE_INSENSITIVE);
    private static final Pattern ALARM_RE = Pattern.compile(
            "(?:set\\s+(?:an\\s+)?alarm|wake\\s+me(?:\\s+up)?)\\s+(?:for|at)\\s+(\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?",
            Pattern.CASE_INSENSITIVE);

    private OsToolsBridge() {
    }

    static boolean isValidCoordinate(double lat, double lon) {
        return Double.isFinite(lat) && Double.isFinite(lon)
                && lat >= -90.0 && lat <= 90.0
                && lon >= -180.0 && lon <= 180.0;
    }

    static String encode(String value) {
        if (value == null) {
            return "";
        }
        try {
            return URLEncoder.encode(value.trim(), "UTF-8").replace("+", "%20");
        } catch (UnsupportedEncodingException impossible) {
            return value.trim();
        }
    }

    static String googleMapsPinUrl(double lat, double lon) {
        if (!isValidCoordinate(lat, lon)) {
            return "https://www.google.com/maps";
        }
        return String.format(Locale.US,
                "https://www.google.com/maps/search/?api=1&query=%.6f,%.6f", lat, lon);
    }

    static String appleMapsPinUrl(double lat, double lon, String label) {
        if (!isValidCoordinate(lat, lon)) {
            return "https://maps.apple.com/";
        }
        String q = (label == null || label.trim().isEmpty()) ? "Zoe Pin" : label.trim();
        return String.format(Locale.US,
                "https://maps.apple.com/?ll=%.6f,%.6f&q=%s", lat, lon, encode(q));
    }

    static String androidGeoPinUri(double lat, double lon, String label) {
        if (!isValidCoordinate(lat, lon)) {
            return "geo:0,0";
        }
        String q = (label == null || label.trim().isEmpty()) ? "Zoe Pin" : label.trim();
        return String.format(Locale.US,
                "geo:%.6f,%.6f?q=%.6f,%.6f(%s)", lat, lon, lat, lon, encode(q));
    }

    static String androidNavigationUri(String destination) {
        String clean = cleanQuery(destination);
        if (clean.isEmpty()) {
            return "geo:0,0";
        }
        return "google.navigation:q=" + encode(clean);
    }

    static String androidGeoSearchUri(String query, double lat, double lon, boolean hasFix) {
        String clean = cleanQuery(query);
        if (clean.isEmpty()) {
            return hasFix && isValidCoordinate(lat, lon)
                    ? androidGeoPinUri(lat, lon, "Current location")
                    : "geo:0,0";
        }
        if (hasFix && isValidCoordinate(lat, lon)) {
            return String.format(Locale.US, "geo:%.6f,%.6f?q=%s", lat, lon, encode(clean));
        }
        return "geo:0,0?q=" + encode(clean);
    }

    static String googleMapsDirectionsUrl(double lat1, double lon1, double lat2, double lon2) {
        if (!isValidCoordinate(lat1, lon1) || !isValidCoordinate(lat2, lon2)) {
            return "https://www.google.com/maps";
        }
        return String.format(Locale.US,
                "https://www.google.com/maps/dir/?api=1&origin=%.6f,%.6f&destination=%.6f,%.6f",
                lat1, lon1, lat2, lon2);
    }

    static String googleMapsSearchUrl(String query) {
        String clean = cleanQuery(query);
        if (clean.isEmpty()) {
            return "https://www.google.com/maps";
        }
        return "https://www.google.com/maps/search/?api=1&query=" + encode(clean);
    }

    static String compassCardinal(double azimuthDegrees) {
        if (!Double.isFinite(azimuthDegrees)) {
            return "N";
        }
        double norm = ((azimuthDegrees % 360.0) + 360.0) % 360.0;
        String[] dirs = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"};
        int idx = (int) Math.floor((norm + 22.5) / 45.0) % 8;
        return dirs[idx];
    }

    static String formatShareLocationMessage(double lat, double lon, float accuracyMeters, String address) {
        if (!isValidCoordinate(lat, lon)) {
            return "Location unavailable.";
        }
        StringBuilder sb = new StringBuilder();
        sb.append("My current location (shared from Zoe):\n");
        if (address != null && !address.trim().isEmpty()) {
            sb.append(address.trim()).append('\n');
        }
        sb.append(String.format(Locale.US, "Coordinates: %.6f, %.6f (accuracy +/- %.0f m)\n",
                lat, lon, Math.max(0f, accuracyMeters)));
        sb.append("Google Maps: ").append(googleMapsPinUrl(lat, lon)).append('\n');
        sb.append("Apple Maps: ").append(appleMapsPinUrl(lat, lon, "Shared location"));
        return sb.toString();
    }

    static ActionSuggestion parseActionIntent(String rawInput) {
        if (rawInput == null || rawInput.trim().isEmpty()) {
            return new ActionSuggestion(ActionKind.NONE, "", "", 0, 0, 0);
        }
        String text = rawInput.trim();
        String lower = text.toLowerCase(Locale.US);

        Matcher nav = NAV_RE.matcher(text);
        if (nav.find()) {
            String dest = cleanQuery(nav.group(1));
            if (!dest.isEmpty()) {
                return new ActionSuggestion(ActionKind.NAVIGATE,
                        "Navigate to " + dest + " (Google Maps)", dest, 0, 0, 0);
            }
        }

        Matcher timer = TIMER_RE.matcher(text);
        if (timer.find()) {
            int amount = safeInt(timer.group(1), 0);
            String unit = timer.group(2).toLowerCase(Locale.US);
            int mult = unit.startsWith("h") ? 3600 : (unit.startsWith("m") ? 60 : 1);
            int total = Math.max(1, Math.min(86400, amount * mult));
            return new ActionSuggestion(ActionKind.SET_TIMER,
                    "Start " + amount + " " + unit + " timer", "", total, 0, 0);
        }

        Matcher alarm = ALARM_RE.matcher(text);
        if (alarm.find()) {
            int h = safeInt(alarm.group(1), -1);
            int m = alarm.group(2) == null ? 0 : safeInt(alarm.group(2), 0);
            String ampm = alarm.group(3) == null ? "" : alarm.group(3).toLowerCase(Locale.US);
            if ("pm".equals(ampm) && h >= 1 && h < 12) {
                h += 12;
            } else if ("am".equals(ampm) && h == 12) {
                h = 0;
            }
            if (h >= 0 && h <= 23 && m >= 0 && m <= 59) {
                String label = String.format(Locale.US, "Set %02d:%02d alarm", h, m);
                return new ActionSuggestion(ActionKind.SET_ALARM, label, "", 0, h, m);
            }
        }

        if (lower.contains("personal safety") || lower.contains("safety app")
                || lower.contains("emergency info") || lower.contains("medical id")) {
            return new ActionSuggestion(ActionKind.OPEN_SAFETY,
                    "Open Personal Safety", "", 0, 0, 0);
        }

        if (lower.contains("flashlight") || lower.contains("torch")
                || lower.contains("turn on the light") || lower.contains("turn on light")) {
            return new ActionSuggestion(ActionKind.TOGGLE_TORCH,
                    "Toggle Flashlight", "", 0, 0, 0);
        }

        if (lower.contains("where am i") || lower.contains("my location")
                || lower.contains("share location") || lower.contains("share my location")
                || lower.equals("open maps") || lower.contains("open google maps")
                || lower.contains("open apple maps")) {
            return new ActionSuggestion(ActionKind.OPEN_LOCATION,
                    "Open Maps & Safety", "", 0, 0, 0);
        }

        Matcher search = SEARCH_RE.matcher(text);
        if (search.find() && (lower.contains("nearby") || lower.contains("near me")
                || lower.contains("maps") || lower.contains("hospital") || lower.contains("pharmacy")
                || lower.contains("coffee") || lower.contains("gas") || lower.contains("food")
                || lower.contains("shelter") || lower.contains("police") || lower.contains("store"))) {
            String place = cleanQuery(search.group(1));
            if (!place.isEmpty()) {
                return new ActionSuggestion(ActionKind.MAP_SEARCH,
                        "Search \"" + place + "\" in Maps", place, 0, 0, 0);
            }
        }

        return new ActionSuggestion(ActionKind.NONE, "", "", 0, 0, 0);
    }

    /**
     * Approval-gated multi-step plan parser (inspired by personal agents, constrained by
     * CONSTITUTION.md: measurement != evidence != belief update != action; autoExecuted=false).
     */
    static List<ActionSuggestion> parseActionPlan(String rawInput) {
        List<ActionSuggestion> plan = new ArrayList<>();
        if (rawInput == null || rawInput.trim().isEmpty()) {
            return plan;
        }
        String[] parts = rawInput.split("(?i)(?:\\s+and\\s+then\\s+|\\s+then\\s+|\\s+and\\s+|\\s*;\\s*)");
        Set<String> seen = new LinkedHashSet<>();
        for (String part : parts) {
            ActionSuggestion step = parseActionIntent(part);
            if (step.isActionable()) {
                String key = step.kind.name() + "|" + step.query.toLowerCase(Locale.US)
                        + "|" + step.seconds + "|" + step.hour + ":" + step.minute;
                if (seen.add(key)) {
                    plan.add(step);
                }
            }
        }
        if (plan.isEmpty()) {
            ActionSuggestion single = parseActionIntent(rawInput);
            if (single.isActionable()) {
                plan.add(single);
            }
        }
        return plan;
    }

    static String claudeDeepLinkUri(String prompt) {
        String clean = prompt == null ? "" : prompt.trim();
        return clean.isEmpty() ? "claude://claude.ai/new" : "claude://claude.ai/new?q=" + encode(clean);
    }

    static String claudeWebUrl(String prompt) {
        String clean = prompt == null ? "" : prompt.trim();
        return clean.isEmpty() ? "https://claude.ai/new" : "https://claude.ai/new?q=" + encode(clean);
    }

    static String grokWebUrl() {
        return "https://grok.com/";
    }

    static String chatGptWebUrl() {
        return "https://chatgpt.com/";
    }

    static String geminiWebUrl() {
        return "https://gemini.google.com/app";
    }

    private static String cleanQuery(String raw) {
        if (raw == null) {
            return "";
        }
        return raw.trim().replaceAll("[.?!]+$", "").trim();
    }

    private static int safeInt(String raw, int fallback) {
        try {
            return Integer.parseInt(raw);
        } catch (NumberFormatException error) {
            return fallback;
        }
    }
}
