package research.zoetic.zoe;

import java.util.Locale;

/**
 * Single Unified Decision Brain for Zoe Explore (v0.9.9-beta).
 *
 * Replaces overlapping, competing speech/vision/background pipelines with ONE calm,
 * deterministic 4-branch decision funnel so Zoe always knows exactly what is happening:
 *
 *   1. STOP          -> User asked to stop/end -> halt mic, camera & sensors cleanly.
 *   2. DIRECT_ACTION -> Spoken control command (flip camera, recenter, mode switch, guide, walk).
 *   3. INSPECT_VIEW  -> Tap on screen, "Look" button, or sight question while camera/AR is active ->
 *                       single on-demand zoomed/centered vision pass (zero background polling race!).
 *   4. CONVERSE      -> Direct question or chat -> fast exact math/identity/clock, or calm reply.
 */
final class ExploreDecisionEngine {
    enum Trigger {
        TAP_OBJECT,
        LOOK_NOW,
        SPOKEN_OR_TYPED
    }

    enum DecisionKind {
        STOP,
        DIRECT_ACTION,
        INSPECT_VIEW,
        CONVERSE
    }

    static final class Decision {
        final DecisionKind kind;
        final LiveViewErgonomics.ParsedVoiceAction voiceAction;
        final String cleanPrompt;
        final float focusU;
        final float focusV;
        final boolean isZoomedTap;

        Decision(DecisionKind kind, LiveViewErgonomics.ParsedVoiceAction voiceAction,
                 String cleanPrompt, float focusU, float focusV, boolean isZoomedTap) {
            this.kind = kind == null ? DecisionKind.CONVERSE : kind;
            this.voiceAction = voiceAction != null
                    ? voiceAction
                    : new LiveViewErgonomics.ParsedVoiceAction(LiveViewErgonomics.ExploreVoiceAction.NONE, "", Float.NaN);
            this.cleanPrompt = cleanPrompt == null ? "" : cleanPrompt.trim();
            this.focusU = Float.isFinite(focusU) ? Math.max(0.05f, Math.min(0.95f, focusU)) : 0.5f;
            this.focusV = Float.isFinite(focusV) ? Math.max(0.05f, Math.min(0.95f, focusV)) : 0.5f;
            this.isZoomedTap = isZoomedTap;
        }
    }

    private ExploreDecisionEngine() {
    }

    /**
     * Makes ONE unambiguous decision for any Zoe Explore turn (tap, look button, or speech/text).
     */
    static Decision decide(Trigger trigger, String spokenText, boolean cameraActive,
                           float tapU, float tapV) {
        Trigger t = trigger == null ? Trigger.SPOKEN_OR_TYPED : trigger;
        String clean = spokenText == null ? "" : spokenText.trim();

        if (t == Trigger.TAP_OBJECT) {
            return new Decision(DecisionKind.INSPECT_VIEW, null, "", tapU, tapV, true);
        }
        if (t == Trigger.LOOK_NOW) {
            return new Decision(DecisionKind.INSPECT_VIEW, null, "What do you see?", 0.5f, 0.5f, false);
        }

        // SPOKEN_OR_TYPED: strict priority 1 -> 2 -> 3 -> 4
        if (ConversationResponse.isStop(clean)) {
            return new Decision(DecisionKind.STOP, null, clean, 0.5f, 0.5f, false);
        }
        LiveViewErgonomics.ParsedVoiceAction action = LiveViewErgonomics.parseExploreVoiceAction(clean);
        if (action.action != LiveViewErgonomics.ExploreVoiceAction.NONE) {
            return new Decision(DecisionKind.DIRECT_ACTION, action, clean, 0.5f, 0.5f, false);
        }
        if (cameraActive && isDirectSightRequest(clean)) {
            return new Decision(DecisionKind.INSPECT_VIEW, null, clean, 0.5f, 0.5f, false);
        }
        return new Decision(DecisionKind.CONVERSE, null, clean, 0.5f, 0.5f, false);
    }

    /**
     * True when the user is asking Zoe to look at or read what is currently in front of the lens.
     */
    static boolean isDirectSightRequest(String spoken) {
        if (spoken == null || spoken.trim().isEmpty()) {
            return false;
        }
        if (LiveSessionLogic.isLikelyCameraQuestion(spoken)) {
            return true;
        }
        String l = spoken.toLowerCase(Locale.US);
        return l.contains("identify") || l.contains("what is that") || l.contains("what's that")
                || l.contains("what is this") || l.contains("what's this")
                || l.contains("read this") || l.contains("read that")
                || l.contains("describe") || l.contains("tell me what you see");
    }

    /**
     * Extracts ONLY a short, natural user-taught name from a VisionPriorStore hint, or "" if it is
     * raw debug/contour metadata — keeping Zoe's spoken answers clean, natural, and uncluttered!
     */
    static String extractCleanLearnedName(String rawHint) {
        if (rawHint == null || rawHint.trim().isEmpty()) {
            return "";
        }
        String prefix = "Learned visual memory candidate:";
        int idx = rawHint.indexOf(prefix);
        if (idx < 0) {
            return "";
        }
        String tail = rawHint.substring(idx + prefix.length()).trim();
        int paren = tail.indexOf('(');
        String name = (paren > 0 ? tail.substring(0, paren) : tail).trim();
        if (name.length() < 2 || name.length() > 40) {
            return "";
        }
        return name;
    }
}
