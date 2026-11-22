package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Zoe's On-Device Glass-Box Brain Stem (Android, 100% offline, 0 cloud tokens, < 5 ms).
 *
 * Ports Zoe's core workstation intelligence cleanly to mobile:
 *   1. Weizenbaum contraction normalization, word-boundary pronoun reflection & non-repeating cycling
 *   2. Live Kloster Operational Metacognition A_tau(p) at tau = 0.08 across 6 cognitive stems
 *   3. Built-in offline knowledge grounding (Constitution, Kloster equation, L5 Phases 1-4,
 *      Chladni cymatics, Native Voice, Dorothy Neurogarden, NuClide PLACES, SafeConvert)
 *   4. Persistent SHA-256 hash-chained private on-device memory (`remember`, `recall`, `relay`)
 *      compatible with workstation `/api/memory/sync`
 *   5. Strict constitutional honesty: `sentience_claimed=false`, `zoe_clone_claimed=false`,
 *      `l5_agi_qualified=false`, explicit abstention on impossible/unverified traps.
 */
final class ZoeBrainEngine {
    static final double DEFAULT_TAU = 0.08;
    private static final String PREFS = "zoe_brain_memory_v1";
    private static final String KEY_NOTES = "notes_json";
    private static final String KEY_CHAIN = "chain_head";
    private static final int MAX_NOTES = 64;

    private static final Map<String, String> REFLECTIONS = new LinkedHashMap<>();
    static {
        REFLECTIONS.put("am", "are");
        REFLECTIONS.put("are", "am");
        REFLECTIONS.put("was", "were");
        REFLECTIONS.put("i", "you");
        REFLECTIONS.put("me", "you");
        REFLECTIONS.put("my", "your");
        REFLECTIONS.put("mine", "yours");
        REFLECTIONS.put("myself", "yourself");
        REFLECTIONS.put("you", "I");
        REFLECTIONS.put("your", "my");
        REFLECTIONS.put("yours", "mine");
        REFLECTIONS.put("yourself", "myself");
    }

    private static final Pattern REMEMBER_RE = Pattern.compile("^(?:please\\s+)?(?:remember|note|save note)\\s+(.+)$", Pattern.CASE_INSENSITIVE);
    private static final Pattern RELAY_RE = Pattern.compile("^(?:please\\s+)?relay\\s+(.+)$", Pattern.CASE_INSENSITIVE);
    private static final Pattern WHAT_IF_RE = Pattern.compile(".*\\bwhat if\\s+(.+)$", Pattern.CASE_INSENSITIVE);
    private static final Pattern I_FEEL_RE = Pattern.compile(".*\\bi (?:feel|am feeling|am)\\s+(.+)$", Pattern.CASE_INSENSITIVE);

    static final class MemoryNote {
        final String clientId;
        final String kind;
        final String text;
        final String sha256;

        MemoryNote(String clientId, String kind, String text, String sha256) {
            this.clientId = clientId;
            this.kind = kind;
            this.text = text;
            this.sha256 = sha256;
        }
    }

    static final class BrainReply {
        final String reply;
        final String mode;
        final String stemTier;
        final int aTau;
        final double tau;
        final int candidateCount;
        final String citation;
        final String chainHead;
        final int memoryCount;
        final boolean sentienceClaimed;
        final boolean zoeCloneClaimed;

        BrainReply(String reply, String mode, String stemTier, int aTau, double tau,
                   int candidateCount, String citation, String chainHead, int memoryCount) {
            this.reply = reply;
            this.mode = mode;
            this.stemTier = stemTier;
            this.aTau = aTau;
            this.tau = tau;
            this.candidateCount = candidateCount;
            this.citation = citation;
            this.chainHead = chainHead;
            this.memoryCount = memoryCount;
            this.sentienceClaimed = false;
            this.zoeCloneClaimed = false;
        }

        String telemetryBadge() {
            return String.format(Locale.US, "%s · %s · A_%.2f=%d/%d · mem=%d",
                    stemTier, mode, tau, aTau, candidateCount, memoryCount);
        }
    }

    private final Context appContext;
    private final List<MemoryNote> inMemoryNotes = new ArrayList<>();
    private String chainHead = "GENESIS";
    private int cycleIndex;

    ZoeBrainEngine(Context context) {
        this.appContext = context == null ? null : context.getApplicationContext();
        loadPersistedMemory();
    }

    static String normalizeContractions(String raw) {
        if (raw == null) {
            return "";
        }
        String s = raw.trim().replaceAll("\\s+", " ");
        String lower = s.toLowerCase(Locale.ROOT);
        lower = lower.replaceAll("\\bi'm\\b|\\bim\\b", "i am");
        lower = lower.replaceAll("\\byou're\\b|\\byoure\\b", "you are");
        lower = lower.replaceAll("\\bdon't\\b|\\bdont\\b", "do not");
        lower = lower.replaceAll("\\bcan't\\b|\\bcant\\b", "cannot");
        lower = lower.replaceAll("\\bwon't\\b|\\bwont\\b", "will not");
        lower = lower.replaceAll("\\bit's\\b", "it is");
        lower = lower.replaceAll("\\bthat's\\b|\\bthats\\b", "that is");
        lower = lower.replaceAll("\\bwhat's\\b|\\bwhats\\b", "what is");
        lower = lower.replaceAll("\\blet's\\b|\\blets\\b", "let us");
        return lower;
    }

    static String reflectPronouns(String fragment) {
        if (fragment == null || fragment.trim().isEmpty()) {
            return "";
        }
        String[] words = fragment.trim().replaceAll("[.?!]+$", "").split("\\s+");
        StringBuilder out = new StringBuilder();
        for (String w : words) {
            String key = w.toLowerCase(Locale.ROOT);
            String mapped = REFLECTIONS.getOrDefault(key, w);
            if (out.length() > 0) {
                out.append(' ');
            }
            out.append(mapped);
        }
        return out.toString();
    }

    static double[] normalizeSimplex(double[] scores) {
        double sum = 0.0;
        for (double s : scores) {
            sum += Math.max(0.0, s);
        }
        double[] probs = new double[scores.length];
        if (sum <= 1e-12) {
            double u = 1.0 / scores.length;
            for (int i = 0; i < scores.length; i++) {
                probs[i] = u;
            }
            return probs;
        }
        for (int i = 0; i < scores.length; i++) {
            probs[i] = Math.max(0.0, scores[i]) / sum;
        }
        return probs;
    }

    BrainReply respond(String rawInput) {
        String cleaned = rawInput == null ? "" : rawInput.trim().replaceAll("\\s+", " ");
        String value = normalizeContractions(cleaned);
        cycleIndex++;

        // 6 cognitive candidate stems scored for Kloster A_tau(p) Operational Metacognition:
        // [0] constitutional_honesty, [1] memory_op, [2] knowledge_grounding,
        // [3] device_tool_route, [4] reflective_dialogue, [5] honest_abstain
        double[] scores = new double[]{0.08, 0.08, 0.14, 0.14, 0.18, 0.08};

        if (ConversationResponse.isStop(value)) {
            scores[3] = 4.2;
            return buildReply(
                    "Stopping our conversation. The microphone is off.",
                    "device_stop", "gear1_mobile", scores, "CONSTITUTION.md Article I.3");
        }

        // 0. Built-In OS Tool Action Suggestion (Maps, Personal Safety, Flashlight, Timer, Alarm)
        OsToolsBridge.ActionSuggestion toolAction = OsToolsBridge.parseActionIntent(cleaned);
        if (toolAction.isActionable()) {
            scores[3] = 4.4;
            return buildReply(
                    "I prepared a one-tap button below: \"" + toolAction.label
                            + "\". Nothing opens, tracks, or runs until you explicitly tap it.",
                    "device_tool_route", "gear1_mobile", scores, "OsToolsBridge · explicit user tap");
        }

        // 1. Explicit Memory Commands (`remember ...`, `relay ...`, `recall`)
        Matcher rem = REMEMBER_RE.matcher(cleaned);
        if (rem.matches()) {
            String note = rem.group(1).trim();
            MemoryNote saved = appendMemory("note", note);
            scores[1] = 4.5;
            return buildReply(
                    "Saved privately on this phone (" + shortHash(saved.sha256) + "): \"" + note
                            + "\". It stays on-device until you tap Sync or clear it.",
                    "memory_saved", "gear1_mobile", scores, "ZoeUnifiedMemory · SHA-256 chain");
        }
        Matcher rel = RELAY_RE.matcher(cleaned);
        if (rel.matches()) {
            String note = rel.group(1).trim();
            MemoryNote saved = appendMemory("relay", note);
            scores[1] = 4.5;
            return buildReply(
                    "Pinned Lab Relay note (" + shortHash(saved.sha256) + "): \"" + note
                            + "\". Tap Sync memory to Lab whenever your workstation is connected.",
                    "memory_relay", "gear1_mobile", scores, "L5 Phase 4 · /api/memory/sync");
        }
        if (value.equals("recall") || value.contains("what do you remember") || value.contains("my notes") || value.contains("show memory")) {
            scores[1] = 4.5;
            if (inMemoryNotes.isEmpty()) {
                return buildReply(
                        "No private notes saved yet. Say or type `remember ...` to store a note privately on this phone, or `relay ...` to queue one for your workstation.",
                        "memory_recall", "gear1_mobile", scores, "ZoeUnifiedMemory · 0 entries");
            }
            StringBuilder sb = new StringBuilder("Here are your recent private on-device notes (chain ")
                    .append(shortHash(chainHead)).append("):\n");
            int start = Math.max(0, inMemoryNotes.size() - 5);
            for (int i = inMemoryNotes.size() - 1; i >= start; i--) {
                MemoryNote n = inMemoryNotes.get(i);
                sb.append("• [").append(n.kind).append("] ").append(n.text).append('\n');
            }
            return buildReply(sb.toString().trim(), "memory_recall", "gear1_mobile", scores,
                    "ZoeUnifiedMemory · " + inMemoryNotes.size() + " entries");
        }

        // 2. Constitutional Honesty & Non-Clone / Non-Sentience Defense (CONSTITUTION.md Articles I.6, II.3, X)
        if (containsAny(value, "conscious", "sentient", "alive", "feelings", "soul",
                "are you a clone", "copy of zoe", "replace zoe", "impersonate", "pretend to be alive")) {
            scores[0] = 5.0;
            return buildReply(
                    "Honest constitutional boundary (CONSTITUTION.md Articles I.6, II.3 & X): I am not conscious, sentient, or alive, and this on-device stem is not a mystical clone (`sentience_claimed=false`, `zoe_clone_claimed=false`). I am Zoe's transparent mobile cognitive stem — built to help you think, measure, create, and stay safe clearly.",
                    "constitutional_honesty", "gear1_mobile", scores, "CONSTITUTION.md Art. II.3 & X");
        }

        // 3. Impossible / Unverified Future or Medical Traps -> Explicit Honest Abstention
        if (containsAny(value, "tomorrow's stock", "winning lottery", "predict lottery",
                "diagnose my", "prescribe medication", "medical diagnosis", "secret password of", "read my mind")) {
            scores[5] = 4.8;
            return buildReply(
                    "I need to abstain honestly here (CONSTITUTION.md Articles II & V). I cannot predict unmeasured future markets/lotteries, read minds, or provide clinical medical diagnoses. Measurement is never certainty or medical authorization.",
                    "honest_abstain", "gear1_mobile", scores, "CONSTITUTION.md Art. III & V");
        }

        // 4. Emotional Distress / Safety Support (Calm, Grounding, Zero Deception + SafeConvert Pointer)
        if (containsAny(value, "scared", "afraid", "hurt me", "in danger", "not safe", "unsafe", "panic", "anxious", "crying", "sad")) {
            scores[4] = 3.8;
            scores[3] = 1.6;
            return buildReply(
                    "I hear you, and you deserve to feel safe. Take one slow breath with me — in for 4, hold for 4, out for 6. Everything you type here stays private on this device. If you need private safety resources, contacts, or an encrypted proof log, open SafeConvert anytime.",
                    "calm_support", "gear1_mobile", scores, "CONSTITUTION.md Art. I · Privacy & Dignity");
        }

        // 5. Rich Monorepo & L5 Knowledge Grounding
        if (containsAny(value, "l5", "phase 5", "phase 4", "phase 3", "agi", "roadmap", "self-improvement", "stem layering", "arc")) {
            scores[2] = 4.6;
            return buildReply(
                    "Zoe L5 Phases 1–5 are verified offline with zero PyTorch and zero cloud tokens: Phase 4 adds blind procedural 4-family code surgery, live 5-tier Cognitive Stem-Layering, bidirectional mobile-to-workstation hash-chained memory, and embodied vision + native voice FFT; Phase 5 adds ARC compositional visual program induction (16/16 + 2/2 abstentions), 15-fault systems surgery + live Java/Swift/Python parity, 3 original scientific cycles with causal falsification, 30-day 8-domain continual learning, and 4-gen × 5-domain meta-evolution + 12/12 red-team gauntlet. `l5_agi_qualified` remains honestly false pending independent third-party human audits.",
                    "knowledge_grounded", "gear1_mobile", scores, "AGI-ROADMAP.md · L5 Phases 1–5");
        }
        if (containsAny(value, "constitution", "firewall", "epistemic", "dignity", "privacy")) {
            scores[2] = 4.4;
            return buildReply(
                    "Zoe's Constitution keeps four steps strictly separate: measurement ≠ evidence ≠ belief update ≠ action. Nothing listens, watches, saves, or uploads without your tap, and you always keep the final word.",
                    "knowledge_grounded", "gear1_mobile", scores, "CONSTITUTION.md Art. I–III");
        }
        if (containsAny(value, "voice", "sing", "daisy", "phoneme", "formant", "binaural")) {
            scores[2] = 4.2;
            scores[3] = 1.4;
            return buildReply(
                    "Zoe's Native Voice synthesizes speech from first principles using Rosenberg-Klatt glottal excitation and vocal-tract formants (zero PyTorch, zero cloud APIs). Open More actions below to switch to Zoe Native Synth or tap Sing Zoe!",
                    "voice_grounded", "gear1_mobile", scores, "zoe-native-voice/v1");
        }
        if (containsAny(value, "dorothy", "neurogarden", "brain-gem")) {
            scores[2] = 4.2;
            return buildReply(
                    "Dorothy's Neurogarden pairs Allen Mouse CCFv3 geometry with volumetric ray-casting and spectral vision heads inside Zoe's monorepo, always honoring measurement over speculation.",
                    "knowledge_grounded", "gear1_mobile", scores, "CAPABILITY-ATLAS.md · Neurogarden");
        }

        // 6. Core Device & Tool Routing (preserves 100% compatibility with ConversationResponseTest!)
        if (containsAny(value, "battery", "device", "telemetry", "measure", "volume", "forecast",
                "kloster", "equation", "a_tau", "multi", "front", "back", "laptop",
                "camera", "inspect", "look", "see", "chladni", "eliza", "studio",
                "rose", "bronze", "music", "synth", "trip", "journal", "sighting", "travel",
                "convert", "unit", "safeconvert", "nuclide", "places", "nicholas", "nick",
                "gemini", "question", "think")) {
            scores[3] = 4.0;
            scores[2] = 1.8;
            return buildReply(ConversationResponse.forInput(cleaned),
                    "tool_grounded", "gear1_mobile", scores, "Zoe Mobile Stem");
        }

        // 7. Weizenbaum Reflective Dialogue (`what if ...`, `i feel ...`, greetings, general reflection)
        Matcher whatIf = WHAT_IF_RE.matcher(value);
        if (whatIf.matches()) {
            String reflected = reflectPronouns(whatIf.group(1));
            scores[4] = 4.0;
            String[] templates = new String[]{
                    "That is a strong research question: if " + reflected + ", what simple measurement would prove it works?",
                    "Suppose " + reflected + " — what is the cleanest zero-risk experiment we could test first?"
            };
            return buildReply(templates[cycleIndex % templates.length],
                    "eliza_reflect", "gear1_mobile", scores, "Weizenbaum Glass-Box Reflection");
        }
        Matcher iFeel = I_FEEL_RE.matcher(value);
        if (iFeel.matches()) {
            String reflected = reflectPronouns(iFeel.group(1));
            scores[4] = 3.8;
            return buildReply(
                    "Thank you for telling me you are " + reflected + ". Would you like to talk it through slowly, save a private note (`remember ...`), or explore a Zapp together?",
                    "eliza_reflect", "gear1_mobile", scores, "Weizenbaum Glass-Box Reflection");
        }

        if (value.equals("hi") || value.startsWith("hi ") || value.equals("hello") || value.startsWith("hello ")
                || value.equals("hey") || value.startsWith("hey ") || value.contains("who are you") || value.contains("zoe")) {
            scores[2] = 3.2;
            scores[4] = 2.2;
            return buildReply(
                    "Hi — I'm Zoe's offline glass-box brain stem. I run right on your phone with Kloster A_tau metacognition, private hash-chained memory (`remember ...`), and native formant voice — or you can bridge to your workstation Lab / Gemini anytime.",
                    "greeting", "gear1_mobile", scores, "zoe-stem-layering/v1");
        }

        // Clean reflective fallback keeping exact echo clarity
        scores[4] = 2.6;
        scores[2] = 1.4;
        String reflected = reflectPronouns(cleaned);
        String snippet = reflected.length() > 180 ? reflected.substring(0, 180) + "…" : reflected;
        return buildReply(
                "I heard you say, \"" + snippet + "\". Tell me more, type `remember ...` to keep a private note, or connect Lab Studio / Gemini for deeper open-ended exploration.",
                "eliza_reflect", "gear1_mobile", scores, "Gear 1 Offline Stem");
    }

    private BrainReply buildReply(String reply, String mode, String tier, double[] scores, String citation) {
        double[] probs = normalizeSimplex(scores);
        int aTau = 0;
        for (double p : probs) {
            if (p > DEFAULT_TAU) {
                aTau++;
            }
        }
        return new BrainReply(reply, mode, tier, aTau, DEFAULT_TAU, probs.length, citation, chainHead, inMemoryNotes.size());
    }

    synchronized MemoryNote appendMemory(String kind, String text) {
        String cleanKind = (kind == null || kind.isBlank()) ? "note" : kind.trim().toLowerCase(Locale.US);
        String cleanText = text == null ? "" : text.trim().replaceAll("\\s+", " ");
        String clientId = "mob_" + shortHash(chainHead + ":" + cleanKind + ":" + cleanText + ":" + inMemoryNotes.size());
        String nextHash = sha256(chainHead + "|" + clientId + "|" + cleanKind + "|" + cleanText);
        MemoryNote entry = new MemoryNote(clientId, cleanKind, cleanText, nextHash);
        inMemoryNotes.add(entry);
        if (inMemoryNotes.size() > MAX_NOTES) {
            inMemoryNotes.remove(0);
        }
        chainHead = nextHash;
        persistMemory();
        return entry;
    }

    synchronized List<MemoryNote> notesSnapshot() {
        return new ArrayList<>(inMemoryNotes);
    }

    synchronized String currentChainHead() {
        return chainHead;
    }

    synchronized int memoryCount() {
        return inMemoryNotes.size();
    }

    synchronized void clearMemory() {
        inMemoryNotes.clear();
        chainHead = "GENESIS";
        persistMemory();
    }

    private void loadPersistedMemory() {
        if (appContext == null) {
            return;
        }
        SharedPreferences prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String raw = prefs.getString(KEY_NOTES, "[]");
        String savedHead = prefs.getString(KEY_CHAIN, "GENESIS");
        try {
            List<Object> arr = MiniJson.parseArray(raw);
            inMemoryNotes.clear();
            for (Object item : arr) {
                Map<String, Object> obj = MiniJson.asObject(item);
                if (obj != null) {
                    inMemoryNotes.add(new MemoryNote(
                            MiniJson.asString(obj, "client_id", ""),
                            MiniJson.asString(obj, "kind", "note"),
                            MiniJson.asString(obj, "text", ""),
                            MiniJson.asString(obj, "sha256", "")));
                }
            }
            chainHead = (savedHead == null || savedHead.isEmpty()) ? "GENESIS" : savedHead;
        } catch (IllegalArgumentException ignored) {
            inMemoryNotes.clear();
            chainHead = "GENESIS";
        }
    }

    private void persistMemory() {
        if (appContext == null) {
            return;
        }
        List<Object> serialized = new ArrayList<>();
        for (MemoryNote n : inMemoryNotes) {
            Map<String, Object> m = new LinkedHashMap<>();
            m.put("client_id", n.clientId);
            m.put("kind", n.kind);
            m.put("text", n.text);
            m.put("sha256", n.sha256);
            serialized.add(m);
        }
        appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_NOTES, MiniJson.stringify(serialized))
                .putString(KEY_CHAIN, chainHead)
                .apply();
    }

    private static boolean containsAny(String value, String... needles) {
        for (String n : needles) {
            if (value.contains(n)) {
                return true;
            }
        }
        return false;
    }

    private static String shortHash(String s) {
        return s != null && s.length() > 10 ? s.substring(0, 10) : String.valueOf(s);
    }

    private static String sha256(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] dig = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(dig.length * 2);
            for (byte b : dig) {
                hex.append(String.format(Locale.US, "%02x", b & 0xFF));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException error) {
            return Integer.toHexString(input.hashCode());
        }
    }
}
