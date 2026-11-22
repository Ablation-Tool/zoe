package research.zoetic.zoe;

import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

public class MobileDigestionTest {

    private static PatentReverseImageEngine.VisualSignature sampleSignature(float bias) {
        float[] hog = new float[16];
        float[] rad = new float[8];
        for (int i = 0; i < 16; i++) {
            hog[i] = (i == 2 ? 0.8f : 0.1f) + bias * 0.01f;
        }
        for (int i = 0; i < 8; i++) {
            rad[i] = i == 1 ? 0.9f : 0.1f;
        }
        return new PatentReverseImageEngine.VisualSignature(
                hog, rad, 0x123456789ABCDEF0L, 1.05f, 0.92f, 0.35f, 0.28f,
                "radial gear", "bilateral metallic gear");
    }

    @Test
    public void buildsPrivacyFirewalledBundleExcludingPhotosAndChatBodies() {
        VisionPriorStore.Prototype proto = new VisionPriorStore.Prototype(
                "Brass Caliper", "user_confirmed", "", "150 mm",
                sampleSignature(0f), 2, 1795320000000L);
        ZoeBrainEngine.MemoryNote note = new ZoeBrainEngine.MemoryNote(
                "mob_n1", "note", "Optical bench verified at 440Hz", "abc123");
        TripJournalStore.Entry trip = new TripJournalStore.Entry(
                "trip-1", "2026-11-22 03:30:00", "Desk prism sighting",
                "PRISM 60 DEG", "Optical prism", "Cyan / Gold",
                "", "", "trip-1.jpg", false);
        ChatHistoryStore.ChatMessage userMsg = new ChatHistoryStore.ChatMessage(
                "user", "SUPER_SECRET_PRIVATE_CHAT_BODY_DO_NOT_UPLOAD", "", "", 0L);
        ChatHistoryStore.ChatMessage zoeMsg = new ChatHistoryStore.ChatMessage(
                "zoe", "PRIVATE_REPLY_BODY", "ZOE STEM",
                "gear1_mobile · exact_math · A_0.08=3/6 · mem=1", 12L);
        ChatHistoryStore.ChatThread thread = new ChatHistoryStore.ChatThread(
                "chat-1", "Haeckel Radiolaria Symmetry", "2026-11-22 03:31",
                Arrays.asList(userMsg, zoeMsg));

        MobileDigestionBundle.Summary summary = MobileDigestionBundle.build(
                "Pixel 7", "0.9.3",
                Collections.singletonList(proto),
                Collections.singletonList(note),
                Collections.singletonList(trip),
                Collections.singletonList(thread));

        assertEquals(1, summary.visionPrototypesCount);
        assertEquals(1, summary.brainNotesCount);
        assertEquals(1, summary.tripSightingsCount);
        assertEquals(1, summary.chatThreadsCount);
        assertEquals(2, summary.chatMessagesCount);
        assertEquals(64, summary.bundleSha256.length());

        // Raw chat bodies and thumbnail filenames MUST NEVER appear in the digestion bundle
        assertFalse(summary.bundleJson.contains("SUPER_SECRET_PRIVATE_CHAT_BODY"));
        assertFalse(summary.bundleJson.contains("PRIVATE_REPLY_BODY"));
        assertFalse(summary.bundleJson.contains("trip-1.jpg"));
        assertFalse(summary.bundleJson.contains("thumbFilename"));

        // Explicit firewall flags and aggregated telemetry MUST be present
        Map<String, Object> parsed = MiniJson.parseObject(summary.bundleJson);
        Map<String, Object> fw = MiniJson.asObject(parsed.get("privacy_firewall"));
        assertTrue(MiniJson.asBoolean(fw, "safeconvert_excluded", false));
        assertTrue(MiniJson.asBoolean(fw, "privacy_vault_excluded", false));
        assertTrue(MiniJson.asBoolean(fw, "raw_photos_excluded", false));
        assertTrue(MiniJson.asBoolean(fw, "chat_bodies_excluded", false));

        Map<String, Object> chatTel = MiniJson.asObject(parsed.get("chat_telemetry"));
        assertEquals(3.0, MiniJson.asDouble(chatTel, "avg_a_tau", 0.0), 0.01);
        assertEquals(12.0, MiniJson.asDouble(chatTel, "avg_latency_ms", 0.0), 0.01);
    }

    @Test
    public void clientPrivacyFirewallBlocksForbiddenPrivateDomains() {
        String hostileSafeConvert = "{\"privacy_firewall\":{\"safeconvert_excluded\":true},\"safeconvert_logs\":[\"x\"]}";
        try {
            MobileDigestionBundle.assertOutgoingFirewall(hostileSafeConvert);
            fail("Expected client firewall to reject safeconvert_logs");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("privacy firewall"));
        }

        String hostileVault = "{\"privacy_firewall\":{\"privacy_vault_excluded\":true},\"e2ee_private_key\":\"secret\"}";
        try {
            MobileDigestionBundle.assertOutgoingFirewall(hostileVault);
            fail("Expected client firewall to reject e2ee_private_key");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("privacy firewall"));
        }
    }

    @Test
    public void parsesWorkstationDigestResponseAndMergesRefinedPrototypesSafely() {
        String sampleResponse = "{"
                + "\"available\":true,"
                + "\"cycle_number\":3,"
                + "\"privacy_firewall\":{\"firewall_verified\":true},"
                + "\"ingested\":{\"brain_notes_added\":2,\"trip_sightings_added\":1,"
                + "\"vision_prototypes_added\":1,\"vision_prototypes_reinforced\":1,"
                + "\"vision_atlas_enriched\":1,\"workstation_vision_library_total\":4,"
                + "\"digested_knowledge_facts_total\":7},"
                + "\"self_improvement\":{\"digested_zoe_score\":0.9625,\"undigested_control_score\":0.4125,\"improvement_delta\":0.55},"
                + "\"visual_improvement\":{\"digested_visual_accuracy\":1.0,\"control_visual_accuracy\":0.25,\"atlas_zero_forgetting_retention\":1.0},"
                + "\"kloster_calibration\":{\"recommended_tau\":0.08,\"calibration_rationale\":\"Canonical Kloster threshold well-calibrated.\"},"
                + "\"memory_snapshot\":{\"chain_head\":\"abcdef1234567890\"},"
                + "\"epistemic_boundaries\":{\"l5_agi_qualified\":false,\"zoe_clone_claimed\":false},"
                + "\"refined_prototypes\":[{"
                + "\"label\":\"Brass Caliper\",\"source\":\"user_confirmed\",\"patentRef\":\"CPC-G01B\","
                + "\"dims\":\"150-200 mm measurement tool\",\"count\":4,\"updated\":1795320099000,"
                + "\"dHash\":\"123456789abcdef0\",\"aspect\":1.05,\"sym\":0.92,\"ortho\":0.35,\"density\":0.28,"
                + "\"kw\":\"caliper\",\"summary\":\"enriched\",\"hog\":[0.1,0.1,0.8,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1,0.1],"
                + "\"radial\":[0.1,0.9,0.1,0.1,0.1,0.1,0.1,0.1]}]}";

        ElizaGemClient.DigestResult res = ElizaGemClient.parseDigestResult(sampleResponse);
        assertTrue(res.available);
        assertEquals(3, res.cycleNumber);
        assertTrue(res.firewallVerified);
        assertFalse(res.l5AgiQualified);
        assertFalse(res.zoeCloneClaimed);
        assertEquals(0.9625, res.digestedZoeScore, 0.0001);
        assertEquals(1, res.refinedPrototypes.size());
        assertEquals("CPC-G01B", res.refinedPrototypes.get(0).patentRef);

        // Merge back into local store: adopts CPC-G01B enrichment & higher confirmCount while preserving user_confirmed
        VisionPriorStore.Prototype local = new VisionPriorStore.Prototype(
                "Brass Caliper", "user_confirmed", "", "", sampleSignature(0f), 2, 1795320000000L);
        List<VisionPriorStore.Prototype> merged = VisionPriorStore.mergeRefined(
                Collections.singletonList(local), res.refinedPrototypes);
        assertEquals(1, merged.size());
        assertEquals("CPC-G01B", merged.get(0).patentRef);
        assertEquals("150-200 mm measurement tool", merged.get(0).dimensionsNote);
        assertEquals(4, merged.get(0).confirmCount);
        assertEquals("user_confirmed", merged.get(0).source);

        // Ensure weaker workstation prototype never downgrades a stronger local user_confirmed count
        VisionPriorStore.Prototype strongerLocal = new VisionPriorStore.Prototype(
                "Brass Caliper", "user_confirmed", "LOCAL-REF", "150 mm", sampleSignature(1f), 9, 1795320999000L);
        List<VisionPriorStore.Prototype> protectedMerge = VisionPriorStore.mergeRefined(
                Collections.singletonList(strongerLocal), res.refinedPrototypes);
        assertEquals(9, protectedMerge.get(0).confirmCount);
        assertEquals("LOCAL-REF", protectedMerge.get(0).patentRef);
    }
}
