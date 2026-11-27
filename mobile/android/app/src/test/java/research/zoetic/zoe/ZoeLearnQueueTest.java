package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ZoeLearnQueueTest {
    @Test
    public void sanitizesSlugsAndFormatsCaptureFileNames() {
        assertEquals("prism_lens_24mm", ZoeLearnQueue.sanitizeSlug("  Prism Lens 24mm!!  "));
        assertEquals("capture", ZoeLearnQueue.sanitizeSlug("   "));
        assertEquals("capture", ZoeLearnQueue.sanitizeSlug(null));

        String fn = ZoeLearnQueue.buildCaptureFileName("Digital Caliper", 1_760_000_000_000L);
        assertTrue(fn.startsWith("ZoeLearn_"));
        assertTrue(fn.endsWith("_digital_caliper.jpg"));
    }

    @Test
    public void cyclesDestinationsAndParsesDefaultsCleanly() {
        assertEquals(ZoeLearnQueue.Destination.ASK, ZoeLearnQueue.Destination.fromId(null));
        assertEquals(ZoeLearnQueue.Destination.INSTANT_DIGEST, ZoeLearnQueue.Destination.ASK.next());
        assertEquals(ZoeLearnQueue.Destination.DEVICE_FOLDER, ZoeLearnQueue.Destination.INSTANT_DIGEST.next());
        assertEquals(ZoeLearnQueue.Destination.GOOGLE_DRIVE, ZoeLearnQueue.Destination.DEVICE_FOLDER.next());
        assertEquals(ZoeLearnQueue.Destination.ASK, ZoeLearnQueue.Destination.GOOGLE_DRIVE.next());
        assertEquals(ZoeLearnQueue.Destination.GOOGLE_DRIVE, ZoeLearnQueue.Destination.fromId("drive"));
    }

    @Test
    public void parsesLiveVoiceTeachCommandsAndRejectsRegularSpeech() {
        assertEquals("prism lens", ZoeLearnQueue.parseLiveTeachLabel("Zoe, learn this as a prism lens."));
        assertEquals("blue ceramic mug", ZoeLearnQueue.parseLiveTeachLabel("remember this is my blue ceramic mug!"));
        assertEquals("vernier caliper", ZoeLearnQueue.parseLiveTeachLabel("Hey Zoe teach zoe this is a vernier caliper"));
        assertEquals("monstera leaf", ZoeLearnQueue.parseLiveTeachLabel("this is called a monstera leaf"));

        assertEquals("", ZoeLearnQueue.parseLiveTeachLabel("What do you see right now?"));
        assertEquals("", ZoeLearnQueue.parseLiveTeachLabel("Tell me a joke"));
        assertEquals("", ZoeLearnQueue.parseLiveTeachLabel(""));
    }

    @Test
    public void providesNonEmptyCuriosityQuestsForAnyIndex() {
        String q0 = ZoeLearnQueue.curiosityQuest(0);
        String q1 = ZoeLearnQueue.curiosityQuest(1);
        String qNeg = ZoeLearnQueue.curiosityQuest(-1);
        assertFalse(q0.isEmpty());
        assertFalse(q1.isEmpty());
        assertFalse(qNeg.isEmpty());
        assertFalse(q0.equals(q1));
    }
}
