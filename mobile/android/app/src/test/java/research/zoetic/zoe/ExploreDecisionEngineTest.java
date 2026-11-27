package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ExploreDecisionEngineTest {

    @Test
    public void routesEveryTriggerToOneUnambiguousDecision() {
        // 1. Tap on screen -> zoomed INSPECT_VIEW at exact clamped (u, v)
        ExploreDecisionEngine.Decision tap = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.TAP_OBJECT, "", true, 0.32f, 0.74f);
        assertEquals(ExploreDecisionEngine.DecisionKind.INSPECT_VIEW, tap.kind);
        assertTrue(tap.isZoomedTap);
        assertEquals(0.32f, tap.focusU, 0.001f);
        assertEquals(0.74f, tap.focusV, 0.001f);

        // 2. Look button -> centered INSPECT_VIEW (full frame)
        ExploreDecisionEngine.Decision look = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.LOOK_NOW, "", true, 0.5f, 0.5f);
        assertEquals(ExploreDecisionEngine.DecisionKind.INSPECT_VIEW, look.kind);
        assertFalse(look.isZoomedTap);

        // 3. Stop phrase wins highest priority
        ExploreDecisionEngine.Decision stop = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.SPOKEN_OR_TYPED, "stop", true, 0.5f, 0.5f);
        assertEquals(ExploreDecisionEngine.DecisionKind.STOP, stop.kind);

        // 4. Direct Explore action obeys immediately
        ExploreDecisionEngine.Decision act = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.SPOKEN_OR_TYPED, "flip camera please", true, 0.5f, 0.5f);
        assertEquals(ExploreDecisionEngine.DecisionKind.DIRECT_ACTION, act.kind);
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.FLIP_CAMERA, act.voiceAction.action);

        // 5. Sight question with camera ON -> INSPECT_VIEW; with camera OFF -> CONVERSE
        ExploreDecisionEngine.Decision seeOn = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.SPOKEN_OR_TYPED, "What is that?", true, 0.5f, 0.5f);
        assertEquals(ExploreDecisionEngine.DecisionKind.INSPECT_VIEW, seeOn.kind);

        ExploreDecisionEngine.Decision seeOff = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.SPOKEN_OR_TYPED, "What is that?", false, 0.5f, 0.5f);
        assertEquals(ExploreDecisionEngine.DecisionKind.CONVERSE, seeOff.kind);

        // 6. General chat -> CONVERSE
        ExploreDecisionEngine.Decision chat = ExploreDecisionEngine.decide(
                ExploreDecisionEngine.Trigger.SPOKEN_OR_TYPED, "What is 14 times 12?", true, 0.5f, 0.5f);
        assertEquals(ExploreDecisionEngine.DecisionKind.CONVERSE, chat.kind);
    }

    @Test
    public void stripsRawContourDebugMetadataFromLearnedMemory() {
        String raw = "Learned visual memory candidate: Calico Cat (88% structural contour match, reinforced 3x). Reference dimensions: 40cm.";
        assertEquals("Calico Cat", ExploreDecisionEngine.extractCleanLearnedName(raw));
        assertEquals("", ExploreDecisionEngine.extractCleanLearnedName(""));
        assertEquals("", ExploreDecisionEngine.extractCleanLearnedName("unformatted text"));
    }
}
