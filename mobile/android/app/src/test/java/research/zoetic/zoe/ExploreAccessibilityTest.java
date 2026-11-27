package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ExploreAccessibilityTest {

    @Test
    public void profilesConfigureTailoredDeafBlindAndKidSettings() {
        ExploreAccessibility.Settings std = ExploreAccessibility.Settings.standard();
        assertEquals(ExploreAccessibility.Profile.STANDARD, std.profile);
        assertFalse(std.largeCaptions);
        assertFalse(std.muteSpokenTts);
        assertFalse(std.showTypeBar);

        ExploreAccessibility.Settings deaf = ExploreAccessibility.Settings.forProfile(
                ExploreAccessibility.Profile.DEAF_HOH, true);
        assertTrue(deaf.largeCaptions);
        assertTrue(deaf.hapticCues);
        assertTrue(deaf.visualSoundRadar);
        assertTrue(deaf.muteSpokenTts);
        assertTrue(deaf.showTypeBar);
        assertTrue(deaf.kidFriendly);
        assertEquals("Deaf / HoH · Kid", deaf.shortBadge());

        ExploreAccessibility.Settings blind = ExploreAccessibility.Settings.forProfile(
                ExploreAccessibility.Profile.BLIND_LOW_VISION, false);
        assertTrue(blind.audioFirstNarration);
        assertTrue(blind.spatialAudioBeacon);
        assertTrue(blind.hapticCues);
        assertTrue(blind.largeCaptions);
        assertFalse(blind.muteSpokenTts);
        assertEquals("Blind / Audio", blind.shortBadge());
    }

    @Test
    public void clockFaceDirectionAndGuidedCuesSupportAdultAndKidNavigation() {
        assertTrue(ExploreAccessibility.clockFaceDirection(-0.8f).contains("10 o'clock"));
        assertTrue(ExploreAccessibility.clockFaceDirection(-0.35f).contains("11 o'clock"));
        assertTrue(ExploreAccessibility.clockFaceDirection(0.0f).contains("12 o'clock"));
        assertTrue(ExploreAccessibility.clockFaceDirection(0.35f).contains("1 o'clock"));
        assertTrue(ExploreAccessibility.clockFaceDirection(0.8f).contains("2 o'clock"));

        SpatialTelemetryFusion.LightFieldState brightAhead = SpatialTelemetryFusion.computeLightField(
                0.85f, 0.30f, 0f, 0f, true);
        String adultCue = ExploreAccessibility.formatGuidedSceneCue(
                "Door", "EXIT", 0.35f, 1.4f, 90f, brightAhead, false);
        assertTrue(adultCue.contains("1 o'clock"));
        assertTrue(adultCue.contains("1.4 meters"));
        assertTrue(adultCue.contains("door"));
        assertTrue(adultCue.contains("EXIT"));
        assertTrue(adultCue.contains("Facing E"));
        assertTrue(adultCue.contains("Bright light ahead"));

        String kidCue = ExploreAccessibility.formatGuidedSceneCue(
                "Dog", "", 0.0f, 2.0f, 0f, null, true);
        assertTrue(kidCue.contains("big steps"));
        assertTrue(kidCue.contains("dog"));
        assertTrue(kidCue.contains("12 o'clock"));
    }

    @Test
    public void stereoSpatialBeaconPansLeftRightAndShiftsPitchWithDistance() {
        short[] left = ExploreAccessibility.buildStereoSpatialChime(-1.0f, 0.6f, 44100);
        short[] right = ExploreAccessibility.buildStereoSpatialChime(1.0f, 2.4f, 44100);
        assertTrue(left.length > 4000 && left.length % 2 == 0);

        double leftEarEnergyL = 0, rightEarEnergyL = 0;
        for (int i = 0; i < left.length; i += 2) {
            leftEarEnergyL += (double) left[i] * left[i];
            rightEarEnergyL += (double) left[i + 1] * left[i + 1];
        }
        assertTrue(leftEarEnergyL > rightEarEnergyL * 10.0);

        double leftEarEnergyR = 0, rightEarEnergyR = 0;
        for (int i = 0; i < right.length; i += 2) {
            leftEarEnergyR += (double) right[i] * right[i];
            rightEarEnergyR += (double) right[i + 1] * right[i + 1];
        }
        assertTrue(rightEarEnergyR > leftEarEnergyR * 10.0);
    }
}
