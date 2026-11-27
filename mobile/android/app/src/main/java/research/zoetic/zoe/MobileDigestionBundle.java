package research.zoetic.zoe;

import android.content.Context;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Privacy-Firewalled Mobile -> Workstation Digestion Bundle Collector (v0.9.3-beta).
 *
 * Strictly honors CONSTITUTION.md Article I:
 *   - HARD-EXCLUDED: SafeConvert safety logs/vault/contacts/BLE beacon state, Privacy Vault
 *     E2EE keys/envelopes, raw camera images/thumbnails, and raw private chat transcripts.
 *   - EXPLICIT CONSENT ONLY: built only when the user taps "Feed & Digest into Zoe Lab".
 *   - Collects structured, compact learning signals across Guided Vision / Zoe Explore
 *     (`VisionPriorStore`), private Brain notes/relays (`ZoeBrainEngine`), textual Trip
 *     Journal sightings (`TripJournalStore` with thumb filenames stripped), and aggregated
 *     non-sensitive chat routing telemetry (`ChatHistoryStore`).
 */
final class MobileDigestionBundle {
    static final String CONTRACT = "zoe-mobile-digestion/v1";
    private static final String[] FORBIDDEN_CLIENT_KEYS = new String[]{
            "safeconvert", "safe_convert", "safe_vault", "safe_evidence", "safe_beacon",
            "safety_contacts", "privacy_vault", "e2ee_private_key", "ecdh_private",
            "private_key_pkcs8", "vault_envelope", "raw_photo_base64", "data:image/",
            "BEGIN PRIVATE KEY"
    };
    private static final Pattern A_TAU_RE = Pattern.compile("A_\\d+\\.\\d+=(\\d+)/\\d+");
    private static final Set<String> TOPIC_STOPWORDS = Set.of(
            "the", "and", "for", "with", "that", "this", "from", "have", "what", "when", "where",
            "how", "why", "you", "your", "about", "into", "can", "could", "would", "should",
            "please", "tell", "show", "just", "make", "need", "want", "like", "more", "some",
            "hello", "hey", "thanks", "thank", "new", "conversation", "zoe", "are", "was", "were"
    );

    static final class Summary {
        final String bundleJson;
        final String bundleSha256;
        final int visionPrototypesCount;
        final int brainNotesCount;
        final int tripSightingsCount;
        final int chatThreadsCount;
        final int chatMessagesCount;

        Summary(String bundleJson, String bundleSha256, int visionPrototypesCount,
                int brainNotesCount, int tripSightingsCount, int chatThreadsCount, int chatMessagesCount) {
            this.bundleJson = bundleJson;
            this.bundleSha256 = bundleSha256;
            this.visionPrototypesCount = visionPrototypesCount;
            this.brainNotesCount = brainNotesCount;
            this.tripSightingsCount = tripSightingsCount;
            this.chatThreadsCount = chatThreadsCount;
            this.chatMessagesCount = chatMessagesCount;
        }
    }

    private MobileDigestionBundle() {
    }

    static Summary collect(Context context, ZoeBrainEngine brain) {
        List<VisionPriorStore.Prototype> protos = VisionPriorStore.loadAll(context);
        List<ZoeBrainEngine.MemoryNote> notes = brain == null
                ? Collections.emptyList()
                : brain.notesSnapshot();
        List<TripJournalStore.Entry> trips = TripJournalStore.load(context);
        List<ChatHistoryStore.ChatThread> threads = ChatHistoryStore.load(context);
        String device = android.os.Build.MODEL != null && !android.os.Build.MODEL.trim().isEmpty()
                ? android.os.Build.MODEL.trim()
                : "Android";
        String appVersion = "0.9.3";
        if (context != null) {
            try {
                String vn = context.getPackageManager()
                        .getPackageInfo(context.getPackageName(), 0).versionName;
                if (vn != null && !vn.trim().isEmpty()) {
                    appVersion = vn.trim();
                }
            } catch (Exception ignored) {
            }
        }
        return build(device, appVersion, protos, notes, trips, threads);
    }

    /** Pure JVM-testable bundle builder with strict privacy firewall guarantees. */
    static Summary build(String device,
                         String appVersion,
                         List<VisionPriorStore.Prototype> prototypes,
                         List<ZoeBrainEngine.MemoryNote> notes,
                         List<TripJournalStore.Entry> trips,
                         List<ChatHistoryStore.ChatThread> threads) {
        List<VisionPriorStore.Prototype> safeProtos = prototypes == null ? Collections.emptyList() : prototypes;
        List<ZoeBrainEngine.MemoryNote> safeNotes = notes == null ? Collections.emptyList() : notes;
        List<TripJournalStore.Entry> safeTrips = trips == null ? Collections.emptyList() : trips;
        List<ChatHistoryStore.ChatThread> safeThreads = threads == null ? Collections.emptyList() : threads;

        Map<String, Object> root = new LinkedHashMap<>();
        root.put("contract", CONTRACT);
        root.put("device", device == null || device.trim().isEmpty() ? "android" : device.trim());
        root.put("app_version", appVersion == null || appVersion.trim().isEmpty() ? "0.9.3" : appVersion.trim());

        Map<String, Object> firewall = new LinkedHashMap<>();
        firewall.put("safeconvert_excluded", true);
        firewall.put("privacy_vault_excluded", true);
        firewall.put("raw_photos_excluded", true);
        firewall.put("chat_bodies_excluded", true);
        root.put("privacy_firewall", firewall);

        // 1. Brain Notes & Relays (SHA-256 hash-chained)
        List<Object> notesArr = new ArrayList<>();
        for (ZoeBrainEngine.MemoryNote n : safeNotes) {
            if (n == null || n.text == null || n.text.trim().isEmpty()) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("client_id", n.clientId);
            row.put("kind", n.kind);
            row.put("text", n.text);
            notesArr.add(row);
        }
        root.put("brain_notes", notesArr);

        // 2. Trip Journal Sightings (structured text ONLY — thumbFilename explicitly omitted!)
        List<Object> tripsArr = new ArrayList<>();
        for (TripJournalStore.Entry e : safeTrips) {
            if (e == null) {
                continue;
            }
            if (e.note.isEmpty() && e.labels.isEmpty() && e.ocrText.isEmpty() && e.paletteSummary.isEmpty()) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", e.id);
            row.put("timestampIso", e.timestampIso);
            row.put("note", e.note);
            row.put("labels", e.labels);
            row.put("ocrText", e.ocrText);
            row.put("paletteSummary", e.paletteSummary);
            tripsArr.add(row);
        }
        root.put("trip_sightings", tripsArr);

        // 3. Learned Visual Prototypes (compact Sobel/HoG-16/Radial-8 vectors, zero raw photos)
        List<Object> protoArr = new ArrayList<>();
        for (VisionPriorStore.Prototype p : safeProtos) {
            if (p == null || p.signature == null || p.label.isEmpty()) {
                continue;
            }
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("label", p.label);
            row.put("source", p.source);
            row.put("patentRef", p.patentRef);
            row.put("dims", p.dimensionsNote);
            row.put("count", p.confirmCount);
            row.put("updated", p.updatedAtMs);
            row.put("dHash", Long.toUnsignedString(p.signature.dHash64, 16));
            row.put("aspect", round4(p.signature.aspectRatio));
            row.put("sym", round4(p.signature.bilateralSymmetry));
            row.put("ortho", round4(p.signature.orthogonalRatio));
            row.put("density", round4(p.signature.edgeDensity));
            row.put("kw", p.signature.morphologyKeywords);
            row.put("summary", p.signature.shapeSummary);
            row.put("hog", toDoubleList(p.signature.hog16));
            row.put("radial", toDoubleList(p.signature.radial8));
            protoArr.add(row);
        }
        root.put("vision_prototypes", protoArr);

        // 4. Aggregated Non-Sensitive Chat Routing Telemetry (NO private chat bodies!)
        int totalMessages = 0;
        long latencySum = 0L;
        int latencyCount = 0;
        double aTauSum = 0.0;
        int aTauCount = 0;
        Map<String, Integer> providerCounts = new LinkedHashMap<>();
        Map<String, Integer> keywordFreq = new LinkedHashMap<>();

        for (ChatHistoryStore.ChatThread t : safeThreads) {
            if (t == null) {
                continue;
            }
            extractTopicKeywords(t.title, keywordFreq);
            if (t.messages == null) {
                continue;
            }
            for (ChatHistoryStore.ChatMessage m : t.messages) {
                if (m == null) {
                    continue;
                }
                totalMessages++;
                if (m.latencyMs > 0) {
                    latencySum += m.latencyMs;
                    latencyCount++;
                }
                if (m.provider != null && !m.provider.trim().isEmpty()
                        && !"user".equalsIgnoreCase(m.role)
                        && !"YOU".equalsIgnoreCase(m.provider.trim())) {
                    String key = m.provider.trim();
                    providerCounts.put(key, providerCounts.getOrDefault(key, 0) + 1);
                }
                if (m.glassBox != null && !m.glassBox.isEmpty()) {
                    Matcher matcher = A_TAU_RE.matcher(m.glassBox);
                    if (matcher.find()) {
                        try {
                            aTauSum += Integer.parseInt(matcher.group(1));
                            aTauCount++;
                        } catch (NumberFormatException ignored) {
                        }
                    }
                }
            }
        }

        List<Map.Entry<String, Integer>> sortedKw = new ArrayList<>(keywordFreq.entrySet());
        sortedKw.sort((a, b) -> {
            int cmp = Integer.compare(b.getValue(), a.getValue());
            return cmp != 0 ? cmp : a.getKey().compareTo(b.getKey());
        });
        List<Object> topTopics = new ArrayList<>();
        for (int i = 0; i < Math.min(16, sortedKw.size()); i++) {
            topTopics.add(sortedKw.get(i).getKey());
        }

        Map<String, Object> chatTel = new LinkedHashMap<>();
        chatTel.put("thread_count", safeThreads.size());
        chatTel.put("message_count", totalMessages);
        chatTel.put("avg_latency_ms", latencyCount > 0 ? round2((double) latencySum / latencyCount) : 0.0);
        chatTel.put("avg_a_tau", aTauCount > 0 ? round2(aTauSum / aTauCount) : 2.0);
        chatTel.put("provider_counts", new LinkedHashMap<String, Object>(providerCounts));
        chatTel.put("topic_keywords", topTopics);
        root.put("chat_telemetry", chatTel);

        String unsignedJson = MiniJson.stringify(root);
        String digest = sha256Hex(unsignedJson);
        root.put("bundle_sha256", digest);
        String finalJson = MiniJson.stringify(root);
        assertOutgoingFirewall(finalJson);

        return new Summary(finalJson, digest, protoArr.size(), notesArr.size(),
                tripsArr.size(), safeThreads.size(), totalMessages);
    }

    /** Client-side double-check ensuring no forbidden private domain ever leaves the phone. */
    static void assertOutgoingFirewall(String bundleJson) {
        if (bundleJson == null || bundleJson.trim().isEmpty()) {
            throw new IllegalArgumentException("Empty digestion bundle");
        }
        String lower = bundleJson.toLowerCase(Locale.US);
        // Strip the explicit boolean attestation section before scanning for forbidden tokens
        String sanitized = lower
                .replace("\"safeconvert_excluded\":true", "")
                .replace("\"privacy_vault_excluded\":true", "")
                .replace("\"raw_photos_excluded\":true", "")
                .replace("\"chat_bodies_excluded\":true", "");
        for (String forbidden : FORBIDDEN_CLIENT_KEYS) {
            if (sanitized.contains(forbidden.toLowerCase(Locale.US))) {
                throw new IllegalArgumentException(
                        "CONSTITUTION.md client privacy firewall blocked forbidden token: " + forbidden);
            }
        }
    }

    private static void extractTopicKeywords(String title, Map<String, Integer> freq) {
        if (title == null || title.trim().isEmpty()) {
            return;
        }
        String[] toks = title.toLowerCase(Locale.US).split("[^a-z0-9]+");
        for (String tok : toks) {
            if (tok.length() < 4 || TOPIC_STOPWORDS.contains(tok)) {
                continue;
            }
            // Never extract purely numeric codes/pins
            if (tok.matches("\\d+")) {
                continue;
            }
            freq.put(tok, freq.getOrDefault(tok, 0) + 1);
        }
    }

    private static List<Object> toDoubleList(float[] arr) {
        List<Object> list = new ArrayList<>(arr.length);
        for (float v : arr) {
            list.add(round4(v));
        }
        return list;
    }

    private static double round4(double v) {
        return Math.round(v * 10000.0) / 10000.0;
    }

    private static double round2(double v) {
        return Math.round(v * 100.0) / 100.0;
    }

    private static String sha256Hex(String input) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] bytes = md.digest(input.getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder(bytes.length * 2);
            for (byte b : bytes) {
                sb.append(String.format(Locale.US, "%02x", b & 0xff));
            }
            return sb.toString();
        } catch (NoSuchAlgorithmException err) {
            return "";
        }
    }
}
