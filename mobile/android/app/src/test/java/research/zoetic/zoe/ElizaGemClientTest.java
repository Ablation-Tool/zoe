package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ElizaGemClientTest {
    @Test
    public void acceptsLoopbackHttpAndRemoteHttpsButRejectsRemoteCleartext() {
        assertEquals("http://127.0.0.1:8765", ElizaGemClient.validateEndpoint("http://127.0.0.1:8765/"));
        assertEquals("http://localhost:8765", ElizaGemClient.validateEndpoint("http://localhost:8765"));
        assertEquals("https://zoe-lab.example.com", ElizaGemClient.validateEndpoint("https://zoe-lab.example.com/"));

        boolean rejected = false;
        try {
            ElizaGemClient.validateEndpoint("http://192.168.1.50:8765");
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        assertTrue(rejected);
    }

    @Test
    public void parsesStatusChatReplyAndPhase3Report() {
        String statusJson = "{\"default_gear\":\"gear2\",\"rule_count\":64,\"indexed_sources\":19,"
                + "\"local_llm_probe\":{\"ollama_available\":false,\"llama_server_available\":true,"
                + "\"available_models\":[\"Qwen2.5-3B-Instruct\"]},"
                + "\"memory_snapshot\":{\"relay_notes_count\":3,\"active_notes_count\":7,\"chain_head\":\"abc123\"}}";
        ElizaGemClient.Status status = ElizaGemClient.parseStatus(statusJson);
        assertEquals("gear2", status.defaultGear);
        assertEquals(64, status.ruleCount);
        assertTrue(status.localLlmReady);
        assertEquals("Qwen2.5-3B-Instruct", status.localLlmLabel);
        assertEquals(3, status.relayNotesCount);
        assertFalse(status.frontierReady);

        String frontierJson = "{\"default_gear\":\"gear3\",\"rule_count\":64,\"indexed_sources\":31,"
                + "\"frontier_probe\":{\"available\":true,\"model\":\"gemini-2.5-pro\"},"
                + "\"local_llm_probe\":{\"ollama_available\":false,\"llama_server_available\":false,\"available_models\":[]},"
                + "\"memory_snapshot\":{\"relay_notes_count\":1,\"active_notes_count\":4,\"chain_head\":\"f00d\"}}";
        ElizaGemClient.Status frontierStatus = ElizaGemClient.parseStatus(frontierJson);
        assertEquals("gear3", frontierStatus.defaultGear);
        assertTrue(frontierStatus.frontierReady);
        assertEquals("gemini-2.5-pro", frontierStatus.frontierModel);

        String chatJson = "{\"reply\":\"Kloster A_0.08 keeps breadth distinct from truth.\","
                + "\"mode\":\"evidence_cite\",\"gear_used\":\"gear1\",\"latency_ms\":12,"
                + "\"metacognition\":{\"a_tau\":2,\"tau\":0.08,\"candidate_count\":6},"
                + "\"epistemic_boundaries\":{\"zoe_clone_claimed\":false},"
                + "\"citations\":[{\"citation\":\"CONSTITUTION.md\"}]}";
        ElizaGemClient.ChatReply reply = ElizaGemClient.parseChatReply(chatJson);
        assertEquals("evidence_cite", reply.mode);
        assertEquals(2, reply.aTau);
        assertFalse(reply.zoeCloneClaimed);
        assertTrue(reply.citationsSummary.contains("CONSTITUTION.md"));

        String p3Json = "{\"pillars_passed\":5,\"pillars_total\":5,\"mean_zoe_score\":0.99989,"
                + "\"mean_control_score\":0.18334,\"l5_phase3_live_verified\":true,\"l5_agi_qualified\":false,"
                + "\"epistemic_boundaries\":{\"zoe_clone_claimed\":false},"
                + "\"pillars\":[{\"pillar_id\":\"external_unseen_repo_surgery\",\"zoe_score\":1.0,\"control_score\":0.22}]}";
        ElizaGemClient.Phase3Summary p3 = ElizaGemClient.parsePhase3(p3Json);
        assertTrue(p3.available);
        assertEquals(5, p3.pillarsPassed);
        assertFalse(p3.l5AgiQualified);
        assertFalse(p3.zoeCloneClaimed);
        assertEquals(1, p3.pillarLines.size());
    }
}
