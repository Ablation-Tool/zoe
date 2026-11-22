package research.zoetic.zoe;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Pure, testable real-time voice & simultaneous-vision logic for Zoe Explore (v0.6.2-beta).
 *
 * Separates speech sanitization, incremental sentence-level TTS chunking, Android SpeechRecognizer
 * error recovery policy, and live camera + voice prompt fusion from Activity UI code so every
 * edge case is covered by deterministic JUnit tests.
 */
final class LiveSessionLogic {
    enum RecoveryAction {
        SILENT_REARM,
        RESET_AND_RETRY,
        FALLBACK_RECOGNIZER,
        FATAL_PERMISSION
    }

    static final class ErrorPolicy {
        final RecoveryAction action;
        final long delayMs;
        final String userMessage;

        ErrorPolicy(RecoveryAction action, long delayMs, String userMessage) {
            this.action = action;
            this.delayMs = delayMs;
            this.userMessage = userMessage;
        }
    }

    static final class SentenceBatch {
        final List<String> sentences;
        final int nextOffset;

        SentenceBatch(List<String> sentences, int nextOffset) {
            this.sentences = sentences;
            this.nextOffset = nextOffset;
        }
    }

    // Android SpeechRecognizer error constants (duplicated here so pure JVM unit tests run without Android framework stubs)
    static final int ERR_NETWORK_TIMEOUT = 1;
    static final int ERR_NETWORK = 2;
    static final int ERR_AUDIO = 3;
    static final int ERR_SERVER = 4;
    static final int ERR_CLIENT = 5;
    static final int ERR_SPEECH_TIMEOUT = 6;
    static final int ERR_NO_MATCH = 7;
    static final int ERR_RECOGNIZER_BUSY = 8;
    static final int ERR_INSUFFICIENT_PERMISSIONS = 9;
    static final int ERR_TOO_MANY_REQUESTS = 10;
    static final int ERR_SERVER_DISCONNECTED = 11;
    static final int ERR_LANGUAGE_NOT_SUPPORTED = 12;
    static final int ERR_LANGUAGE_UNAVAILABLE = 13;

    private LiveSessionLogic() {
    }

    /**
     * Classifies Android SpeechRecognizer error codes so normal silence or temporary busy states
     * never kill a live Gemini-style conversation or display jarring "code 7" errors.
     */
    static ErrorPolicy classifySpeechError(int errorCode) {
        return switch (errorCode) {
            case ERR_NO_MATCH, ERR_SPEECH_TIMEOUT -> new ErrorPolicy(
                    RecoveryAction.SILENT_REARM,
                    260L,
                    "");
            case ERR_RECOGNIZER_BUSY, ERR_CLIENT, ERR_AUDIO -> new ErrorPolicy(
                    RecoveryAction.RESET_AND_RETRY,
                    600L,
                    "");
            case ERR_NETWORK_TIMEOUT, ERR_NETWORK, ERR_SERVER, ERR_SERVER_DISCONNECTED,
                    ERR_LANGUAGE_NOT_SUPPORTED, ERR_LANGUAGE_UNAVAILABLE, ERR_TOO_MANY_REQUESTS -> new ErrorPolicy(
                    RecoveryAction.FALLBACK_RECOGNIZER,
                    480L,
                    "");
            case ERR_INSUFFICIENT_PERMISSIONS -> new ErrorPolicy(
                    RecoveryAction.FATAL_PERMISSION,
                    0L,
                    "Microphone permission is needed for live voice. Tap Talk Now to allow.");
            default -> new ErrorPolicy(
                    RecoveryAction.RESET_AND_RETRY,
                    700L,
                    "");
        };
    }

    /**
     * Cleans model markdown, code backticks, bullet markers, and raw URLs so TTS sounds natural
     * and conversational instead of reading symbols aloud ("asterisk asterisk").
     */
    static String sanitizeForSpeech(String raw) {
        if (raw == null || raw.isEmpty()) {
            return "";
        }
        String s = raw
                .replaceAll("```[\\s\\S]*?```", " ")
                .replaceAll("`([^`]+)`", "$1")
                .replaceAll("\\*\\*([^*]+)\\*\\*", "$1")
                .replaceAll("\\*([^*]+)\\*", "$1")
                .replaceAll("__([^_]+)__", "$1")
                .replaceAll("https?://\\S+", "")
                .replaceAll("(?m)^\\s*#{1,6}\\s*", "")
                .replaceAll("(?m)^\\s*[-•*+]\\s+", "")
                .replace("—", ", ")
                .replace("–", ", ")
                .replaceAll("[*_~#<>|\\[\\]]", " ")
                .replaceAll("\\s+", " ")
                .trim();
        return s;
    }

    /**
     * Incrementally extracts completed sentences from a live-streaming text buffer starting at
     * {@code consumedOffset} so Zoe starts speaking Sentence 1 aloud while Sentence 2 streams.
     */
    static SentenceBatch extractReadySentences(String streamedSoFar, int consumedOffset) {
        List<String> ready = new ArrayList<>();
        if (streamedSoFar == null || streamedSoFar.isEmpty()) {
            return new SentenceBatch(ready, Math.max(0, consumedOffset));
        }
        int start = Math.max(0, Math.min(consumedOffset, streamedSoFar.length()));
        int len = streamedSoFar.length();
        int scan = start;
        while (scan < len) {
            char ch = streamedSoFar.charAt(scan);
            boolean boundary = false;
            if (ch == '\n') {
                boundary = true;
            } else if ((ch == '.' || ch == '!' || ch == '?') && scan + 1 < len) {
                char next = streamedSoFar.charAt(scan + 1);
                if (Character.isWhitespace(next)) {
                    // Avoid splitting decimals ("3.14") or common abbreviations ("Dr.", "Mr.", "U.S.", "vs.", "Fig.")
                    boolean prevDigit = scan > start && Character.isDigit(streamedSoFar.charAt(scan - 1));
                    boolean nextDigit = scan + 1 < len && Character.isDigit(next);
                    if (!(ch == '.' && ((prevDigit && nextDigit) || endsWithAbbreviation(streamedSoFar, start, scan)))) {
                        boundary = true;
                    }
                }
            }
            if (boundary) {
                String rawSegment = streamedSoFar.substring(start, scan + 1).trim();
                String spoken = sanitizeForSpeech(rawSegment);
                if (spoken.length() >= 4) {
                    ready.add(spoken);
                    start = scan + 1;
                }
            }
            scan++;
        }
        return new SentenceBatch(ready, start);
    }

    private static boolean endsWithAbbreviation(String text, int start, int dotIdx) {
        int wordStart = dotIdx;
        while (wordStart > start && Character.isLetter(text.charAt(wordStart - 1))) {
            wordStart--;
        }
        String w = text.substring(wordStart, dotIdx).toLowerCase(Locale.US);
        if (w.length() == 1 && (wordStart == start || text.charAt(wordStart - 1) == '.')) {
            return true; // e.g., "U.S.", "e.g.", "i.e."
        }
        return w.equals("dr") || w.equals("mr") || w.equals("ms") || w.equals("mrs")
                || w.equals("prof") || w.equals("st") || w.equals("vs") || w.equals("fig")
                || w.equals("no") || w.equals("approx") || w.equals("etc") || w.equals("pat");
    }

    /**
     * Extracts any remaining trailing speech text once a stream finishes.
     */
    static String extractRemainder(String finalFullText, int consumedOffset) {
        if (finalFullText == null || finalFullText.isEmpty()) {
            return "";
        }
        int start = Math.max(0, Math.min(consumedOffset, finalFullText.length()));
        if (start >= finalFullText.length()) {
            return "";
        }
        return sanitizeForSpeech(finalFullText.substring(start));
    }

    /**
     * Fuses the user's live spoken question with real-time camera observations (when Camera is ON)
     * and conversational spoken-style pacing instructions so Zoe Explore feels like Gemini Live.
     */
    static String buildLiveVoicePrompt(String userSpoken, String liveCameraObs) {
        String cleanUser = userSpoken == null ? "" : userSpoken.trim();
        StringBuilder sb = new StringBuilder();
        sb.append("Live real-time voice call. Reply warmly and naturally in 1 to 3 short spoken sentences, ")
                .append("plain speech only with no markdown, lists, or asterisks.");
        if (liveCameraObs != null && !liveCameraObs.trim().isEmpty()) {
            sb.append("\nLive camera currently sees: ").append(liveCameraObs.trim());
            sb.append("\nIf relevant to what the user says, naturally weave in what you see.");
        }
        sb.append("\nUser said: ").append(cleanUser);
        return sb.toString();
    }

    /**
     * Formats a calm, scannable live transcript card showing both what you said and Zoe's reply.
     */
    static String formatLiveCaption(String lastUserLine, String zoeLine) {
        String u = lastUserLine == null ? "" : lastUserLine.trim();
        String z = zoeLine == null ? "" : zoeLine.trim();
        if (u.isEmpty()) {
            return z;
        }
        if (z.isEmpty()) {
            return "You: " + u;
        }
        return "You: " + u + "\n\n" + z;
    }

    static boolean isLikelyCameraQuestion(String spoken) {
        if (spoken == null) {
            return false;
        }
        String l = spoken.toLowerCase(Locale.US);
        return l.contains("look") || l.contains("see") || l.contains("this") || l.contains("that")
                || l.contains("read") || l.contains("camera") || l.contains("holding")
                || l.contains("color") || l.contains("what is it") || l.contains("what's in front");
    }
}
