package research.zoetic.zoe;

import java.util.Locale;

/**
 * Opt-In "Hi Zoe" Hangout Wake-Word Detector (v0.6.0-beta).
 *
 * Strictly opt-in and visible under CONSTITUTION.md — never runs covertly in the background.
 * When the user enables "Hi Zoe: on" inside Zoe Explore or Zoe Chat, recognizes natural
 * hangout greetings ("Hi Zoe", "Hey Zoe", "Hang out Zoe") and strips the wake phrase so
 * any trailing request is answered immediately without repeating yourself.
 */
final class WakeWordDetector {
    private static final String[] TRIGGERS = {
            "hi zoe", "hey zoe", "hello zoe", "hang out zoe", "hangout zoe",
            "ok zoe", "okay zoe", "yo zoe", "hi zoey", "hey zoey"
    };

    private WakeWordDetector() {
    }

    static boolean isHiZoeTrigger(String transcript) {
        if (transcript == null || transcript.trim().isEmpty()) {
            return false;
        }
        String norm = normalize(transcript);
        for (String trigger : TRIGGERS) {
            if (norm.equals(trigger) || norm.startsWith(trigger + " ") || norm.contains(" " + trigger)) {
                return true;
            }
        }
        return false;
    }

    static String stripWakePrefix(String transcript) {
        if (transcript == null) {
            return "";
        }
        String trimmed = transcript.trim();
        String lower = trimmed.toLowerCase(Locale.US);
        for (String trigger : TRIGGERS) {
            int idx = lower.indexOf(trigger);
            if (idx >= 0) {
                String after = trimmed.substring(idx + trigger.length())
                        .replaceFirst("^[\\s,.:;!?-]+", "")
                        .trim();
                return after;
            }
        }
        return trimmed;
    }

    private static String normalize(String s) {
        return s.toLowerCase(Locale.US)
                .replaceAll("[^a-z0-9\\s]", " ")
                .replaceAll("\\s+", " ")
                .trim();
    }
}
