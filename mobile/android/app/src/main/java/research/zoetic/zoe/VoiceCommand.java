package research.zoetic.zoe;

import java.util.Locale;

public enum VoiceCommand {
    INSPECT,
    REPEAT,
    STOP,
    MEASURE,
    VISION,
    VOLUME,
    DEVICE,
    GEMINI,
    UNKNOWN;

    public static VoiceCommand parse(String text) {
        String command = text == null ? "" : text.toLowerCase(Locale.ROOT).trim();
        if (command.isEmpty()) {
            return UNKNOWN;
        }
        if (containsAny(command, "stop", "quiet", "silence")) {
            return STOP;
        }
        if (containsAny(command, "repeat", "read aloud", "speak")) {
            return REPEAT;
        }
        if (containsAny(command, "measure", "volume", "forecast")) {
            return MEASURE;
        }
        if (containsAny(command, "vision", "camera")) {
            return VISION;
        }
        if (containsAny(command, "inspect", "look", "describe", "see")) {
            return INSPECT;
        }
        if (containsAny(command, "device", "battery", "telemetry")) {
            return DEVICE;
        }
        if (containsAny(command, "gemini", "assistant")) {
            return GEMINI;
        }
        return UNKNOWN;
    }

    private static boolean containsAny(String text, String... candidates) {
        for (String candidate : candidates) {
            if (text.contains(candidate)) {
                return true;
            }
        }
        return false;
    }
}
