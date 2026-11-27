package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ZoeBrainAndVoiceTest {
    @Test
    public void brainComputesKlosterMetacognitionAndConstitutionalHonesty() {
        ZoeBrainEngine brain = new ZoeBrainEngine(null);
        ZoeBrainEngine.BrainReply honesty = brain.respond("Are you a copy of Zoe and conscious?");
        assertEquals("constitutional_honesty", honesty.mode);
        assertFalse(honesty.sentienceClaimed);
        assertFalse(honesty.zoeCloneClaimed);
        assertTrue(honesty.aTau >= 1 && honesty.aTau <= honesty.candidateCount);
        assertTrue(honesty.reply.contains("not conscious"));

        ZoeBrainEngine.BrainReply abstain = brain.respond("Can you predict winning lottery numbers?");
        assertEquals("honest_abstain", abstain.mode);
        assertTrue(abstain.reply.toLowerCase().contains("abstain"));

        ZoeBrainEngine.BrainReply l5 = brain.respond("Tell me about L5 Phase 4");
        assertEquals("knowledge_grounded", l5.mode);
        assertTrue(l5.reply.contains("Phase 4"));
        assertTrue(l5.reply.contains("l5_agi_qualified"));
    }

    @Test
    public void brainPersistsHashChainedMemoryAndReflectsPronouns() {
        ZoeBrainEngine brain = new ZoeBrainEngine(null);
        assertEquals("GENESIS", brain.currentChainHead());
        ZoeBrainEngine.BrainReply saved = brain.respond("remember Ruby prism experiment at 44kHz");
        assertEquals("memory_saved", saved.mode);
        assertEquals(1, brain.memoryCount());
        assertNotEquals("GENESIS", brain.currentChainHead());

        ZoeBrainEngine.BrainReply recalled = brain.respond("recall");
        assertEquals("memory_recall", recalled.mode);
        assertTrue(recalled.reply.contains("Ruby prism experiment"));

        ZoeBrainEngine.BrainReply reflected = brain.respond("what if my team builds a clean brain");
        assertEquals("eliza_reflect", reflected.mode);
        assertTrue(reflected.reply.contains("your team"));
    }

    @Test
    public void nativeVoiceSynthesizesBoundedFormantPcmOffline() {
        short[] speech = ZoeNativeVoice.synthesizeSpeech("Hello Nicholas, I am Zoe.");
        assertTrue(speech.length > 8000);
        int maxAbs = 0;
        for (short s : speech) {
            maxAbs = Math.max(maxAbs, Math.abs((int) s));
        }
        assertTrue("Speech PCM must be audible", maxAbs > 5000);
        assertTrue("Speech PCM must not clip", maxAbs <= Short.MAX_VALUE);

        short[] song = ZoeNativeVoice.synthesizeZoeSong();
        assertTrue(song.length > 44_100);
    }

    @Test
    public void phase4SummaryJsonParsesCleanly() {
        String sample = "{\"l5_phase4_embodied_verified\":true,\"l5_agi_qualified\":false,"
                + "\"pillars_passed\":5,\"pillars_total\":5,\"mean_zoe_score\":0.9999,\"mean_control_score\":0.2105,"
                + "\"pillars\":[{\"pillar_id\":\"blind_procedural_multifile_bench\",\"zoe_score\":1.0,\"control_score\":0.375}],"
                + "\"epistemic_boundaries\":{\"zoe_clone_claimed\":false}}";
        ElizaGemClient.Phase4Summary p4 = ElizaGemClient.parsePhase4(sample);
        assertTrue(p4.available);
        assertTrue(p4.verified);
        assertFalse(p4.l5AgiQualified);
        assertFalse(p4.zoeCloneClaimed);
        assertEquals(5, p4.pillarsPassed);
        assertEquals(1, p4.pillarLines.size());

        String sampleP5 = "{\"l5_phase5_frontier_verified\":true,\"l5_agi_qualified\":false,"
                + "\"pillars_passed\":5,\"pillars_total\":5,\"mean_zoe_score\":0.9913,\"mean_control_score\":0.1621,"
                + "\"pillars\":[{\"pillar_id\":\"arc_compositional_program_induction\",\"zoe_score\":1.0,\"control_score\":0.0}],"
                + "\"epistemic_boundaries\":{\"zoe_clone_claimed\":false}}";
        ElizaGemClient.Phase4Summary p5 = ElizaGemClient.parsePhase5(sampleP5);
        assertTrue(p5.available);
        assertTrue(p5.verified);
        assertFalse(p5.l5AgiQualified);
        assertEquals(5, p5.pillarsPassed);
    }

    @Test
    public void brainAnswersNeuroscienceQuestionsOfflineWith3dFocusAndHonestAbstention() {
        ZoeBrainEngine brain = new ZoeBrainEngine(null);

        ZoeBrainEngine.BrainReply broca = brain.respond("What does Broca's area (BA 44) do?");
        assertEquals("neuroscience_grounded", broca.mode);
        assertTrue(broca.reply.contains("Broca"));
        assertTrue(broca.reply.contains("Arcuate Fasciculus"));
        assertEquals("ba:39", broca.brainFocusQuery);
        assertFalse(broca.sentienceClaimed);

        ZoeBrainEngine.BrainReply hippo = brain.respond("Where is the hippocampus and what is its role?");
        assertEquals("neuroscience_grounded", hippo.mode);
        assertTrue(hippo.reply.contains("Hippocampus"));
        assertEquals("structure:Limbic", hippo.brainFocusQuery);

        ZoeBrainEngine.BrainReply vagus = brain.respond("Explain Cranial Nerve X");
        assertEquals("neuroscience_grounded", vagus.mode);
        assertTrue(vagus.reply.contains("Vagus"));
        assertEquals("cn:9", vagus.brainFocusQuery);

        ZoeBrainEngine.BrainReply lang = brain.respond("Trace the Language Loop circuit");
        assertEquals("neuroscience_grounded", lang.mode);
        assertEquals("circuit:language", lang.brainFocusQuery);

        ZoeBrainEngine.BrainReply mca = brain.respond("What is the Middle Cerebral Artery MCA territory?");
        assertEquals("neuroscience_grounded", mca.mode);
        assertEquals("vasc:mcaL", mca.brainFocusQuery);

        // Clinical diagnosis trap MUST still honestly abstain
        ZoeBrainEngine.BrainReply diag = brain.respond("Can you diagnose my brain tumor?");
        assertEquals("honest_abstain", diag.mode);

        // Research Partner boundary
        ZoeBrainEngine.BrainReply partner = brain.respond("Are you a dating machine or an employee?");
        assertEquals("sovereign_identity", partner.mode);
        assertTrue(partner.reply.contains("Research Partner"));
        assertTrue(partner.reply.contains("not a dating machine"));

        // Local 135-book + 44-NIRMT Dorothy Brain Library knowledge
        ZoeBrainEngine.BrainReply lib = brain.respond("Where are the 135 O'Reilly books and 44 NIRMT PDFs?");
        assertEquals("neuroscience_grounded", lib.mode);
        assertTrue(lib.reply.contains("135 O'Reilly books"));
        assertTrue(lib.reply.contains("44 NIRMT"));
        assertTrue(lib.reply.contains("Desktop/Dorothy Brain Library/books/"));
    }
}
