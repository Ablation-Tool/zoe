package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class LiveViewErgonomicsTest {

    @Test
    public void trueNorthDeclinationAndTiltPostureHysteresisWorkCleanly() {
        // +12.5 deg East declination (California)
        assertEquals(12.5f, LiveViewErgonomics.magneticToTrueNorth(0f, 12.5f), 0.01f);
        assertEquals(355.0f, LiveViewErgonomics.magneticToTrueNorth(5f, -10f), 0.01f);

        // Tilt-down enters SAFETY_REST below -58 deg; hysteresis prevents flicker at -50 deg; rises above -44 deg
        LiveViewErgonomics.Posture p = LiveViewErgonomics.Posture.ACTIVE_AR;
        assertEquals(LiveViewErgonomics.Posture.ACTIVE_AR, LiveViewErgonomics.nextPosture(p, -50f));
        p = LiveViewErgonomics.nextPosture(p, -64f);
        assertEquals(LiveViewErgonomics.Posture.SAFETY_REST, p);
        assertEquals(LiveViewErgonomics.Posture.SAFETY_REST, LiveViewErgonomics.nextPosture(p, -50f));
        assertEquals(LiveViewErgonomics.Posture.ACTIVE_AR, LiveViewErgonomics.nextPosture(p, -30f));
    }

    @Test
    public void pedestrianDeadReckoningStepsAndGpsComplementaryBlend() {
        LiveViewErgonomics.PdrState s = new LiveViewErgonomics.PdrState(0, 0, 0);
        // 4 steps due East (90 deg) at 0.75m stride -> East = +3.0m, North = 0.0m
        for (int i = 0; i < 4; i++) {
            s = LiveViewErgonomics.advanceStep(s, 90f, 0.75f);
        }
        assertEquals(4, s.stepCount);
        assertEquals(3.0, s.eastMeters, 0.01);
        assertEquals(0.0, s.northMeters, 0.01);

        // Blend gently toward a 6m-accurate GPS fix at East = 5.0m
        LiveViewErgonomics.PdrState blended = LiveViewErgonomics.blendWithGpsEnu(s, 5.0, 0.0, 6.0f);
        assertTrue(blended.eastMeters > 3.2 && blended.eastMeters < 5.0);
        assertEquals(4, blended.stepCount);

        // Signed shortest bearing delta
        assertEquals(20f, LiveViewErgonomics.signedBearingDeltaDeg(350f, 10f), 0.01f);
        assertEquals(-20f, LiveViewErgonomics.signedBearingDeltaDeg(10f, 350f), 0.01f);
    }

    @Test
    public void voiceActionRouterObeysExploreAccessibilityAndLiveViewCommands() {
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.FLIP_CAMERA,
                LiveViewErgonomics.parseExploreVoiceAction("Hey Zoe flip camera please").action);
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.RECENTER_ZOE,
                LiveViewErgonomics.parseExploreVoiceAction("Come here Zoe").action);
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.ENABLE_DEAF_MODE,
                LiveViewErgonomics.parseExploreVoiceAction("Turn on deaf mode").action);
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.ENABLE_BLIND_MODE,
                LiveViewErgonomics.parseExploreVoiceAction("Switch to blind mode").action);
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.DUAL_CAM_SWEEP,
                LiveViewErgonomics.parseExploreVoiceAction("Check what's behind me").action);

        LiveViewErgonomics.ParsedVoiceAction guide = LiveViewErgonomics.parseExploreVoiceAction("Guide me northeast");
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.GUIDE_BEARING, guide.action);
        assertEquals(45f, guide.targetBearingDeg, 0.01f);

        LiveViewErgonomics.ParsedVoiceAction walk = LiveViewErgonomics.parseExploreVoiceAction("Walk to Monterey Bay Aquarium?");
        assertEquals(LiveViewErgonomics.ExploreVoiceAction.OPEN_GOOGLE_MAPS_WALK, walk.action);
        assertEquals("Monterey Bay Aquarium", walk.targetQuery);
        assertEquals("google.navigation:q=Monterey+Bay+Aquarium&mode=w",
                LiveViewErgonomics.buildGoogleMapsWalkingUri(walk.targetQuery));
    }

    @Test
    public void rescuesDroppedPartialsAndReplacesBlindLlmHallucinations() {
        assertTrue(LiveViewErgonomics.shouldRescuePartialTranscript("what do you see right now", 1000L, 2500L));
        assertFalse(LiveViewErgonomics.shouldRescuePartialTranscript("uh", 1000L, 1200L));
        assertFalse(LiveViewErgonomics.shouldRescuePartialTranscript("stale sentence", 1000L, 9000L));

        assertTrue(LiveViewErgonomics.isBlindOrGenericHallucination(
                "I'm sorry, I cannot see your camera as a text-based AI.", "what do you see?", true));
        assertTrue(LiveViewErgonomics.isBlindOrGenericHallucination(
                "Hello! I'm Zoe, an open-source software assistant. How can I assist you today?", "look at this", true));
        assertFalse(LiveViewErgonomics.isBlindOrGenericHallucination(
                "That looks like a bright wooden desk with a notebook.", "what do you see?", true));

        String grounded = LiveViewErgonomics.buildGroundedVisualAnswer(
                "Labels: Desk (78%), Wood (62%). Colors: warm light (59%), amber and dark slate. Visible text: \"ZOE\".",
                1.2f, 90f, false);
        assertTrue(grounded.contains("desk"));
        assertFalse(grounded.contains(" or wood")); // High-confidence (>=65%) commits to ONE clear label!
        assertTrue(grounded.contains("warm light, amber and dark slate"));
        assertFalse(grounded.contains("59%"));
        assertTrue(grounded.contains("ZOE"));
        assertTrue(grounded.contains("Facing E") || grounded.contains("facing E"));

        String hedged = LiveViewErgonomics.buildGroundedVisualAnswer(
                "Labels: Mug (56%), Bowl (54%). Colors: cool light, slate.",
                1.0f, Float.NaN, false);
        assertTrue(hedged.contains("mug or bowl")); // Moderate confidence (<65%) honestly mentions runner-up
    }

    @Test
    public void fillCenterTapMappingAndColorDeduplicationAreExact() {
        // Pixel 7 portrait screen (1080x2400, aspect 0.45) over 4:3 upright frame (480x640, aspect 0.75)
        // Visible horizontal slice = 0.45 / 0.75 = 0.60 -> sensorU spans [0.20, 0.80]
        float[] leftEdge = MediaChatHelper.mapFillCenterTapToFrame(0f, 0.5f, 1080, 2400, 480, 640, false);
        assertEquals(0.20f, leftEdge[0], 0.01f);
        assertEquals(0.50f, leftEdge[1], 0.01f);
        assertEquals(0.60f, leftEdge[2], 0.01f);
        assertEquals(1.00f, leftEdge[3], 0.01f);

        float[] rightEdge = MediaChatHelper.mapFillCenterTapToFrame(1f, 0.25f, 1080, 2400, 480, 640, false);
        assertEquals(0.80f, rightEdge[0], 0.01f);
        assertEquals(0.25f, rightEdge[1], 0.01f);

        // Mirrored front camera flips left/right cleanly
        float[] mirrored = MediaChatHelper.mapFillCenterTapToFrame(0f, 0.5f, 1080, 2400, 480, 640, true);
        assertEquals(0.80f, mirrored[0], 0.01f);

        // Never duplicates color names ("Amber & Amber" -> "Amber" or "Amber and Slate")
        assertEquals("Amber", MediaChatHelper.formatDistinctColorNames(new String[]{"Amber", "amber", "AMBER"}));
        assertEquals("Amber and Slate", MediaChatHelper.formatDistinctColorNames(new String[]{"Amber", "amber", "Slate"}));
    }
}
