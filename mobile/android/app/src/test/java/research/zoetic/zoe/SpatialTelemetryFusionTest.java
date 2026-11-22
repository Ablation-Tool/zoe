package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class SpatialTelemetryFusionTest {

    @Test
    public void dualCameraVerticalFovMatchesPinholeOptics() {
        // Pixel 7-like rear wide lens (~9.8mm sensor long edge, 6.81mm focal length -> ~71.5 deg portrait FOV)
        float portraitFov = SpatialTelemetryFusion.computeVerticalFovRad(9.8f, 7.3f, 6.81f, true);
        float landscapeFov = SpatialTelemetryFusion.computeVerticalFovRad(9.8f, 7.3f, 6.81f, false);
        assertTrue(portraitFov > landscapeFov);
        assertTrue(portraitFov > 0.9f && portraitFov < 1.5f);
        assertEquals(SpatialTelemetryFusion.DEFAULT_FOV_RAD,
                SpatialTelemetryFusion.computeVerticalFovRad(0f, 0f, 0f, true), 1e-4f);
    }

    @Test
    public void frontBehindLightFieldDrivesRimLightingAndContrast() {
        // Bright window behind user (frontLuma=0.90) vs dimmer room ahead (rearLuma=0.25)
        SpatialTelemetryFusion.LightFieldState backlit = SpatialTelemetryFusion.computeLightField(
                0.25f, 0.90f, -0.1f, 0.4f, true);
        // Dark behind user (frontLuma=0.10) vs sunny scene ahead (rearLuma=0.88)
        SpatialTelemetryFusion.LightFieldState sunAhead = SpatialTelemetryFusion.computeLightField(
                0.88f, 0.10f, 0.2f, -0.2f, true);

        assertTrue(backlit.backlightRatio > 2.0f);
        assertTrue(backlit.rimIntensity > sunAhead.rimIntensity + 0.35f);
        assertTrue(sunAhead.contrastBoost > backlit.contrastBoost + 0.25f);
        assertTrue(backlit.calibrated);

        int[] warmBright = new int[]{0xFFFFD8A8, 0xFFFCE0B0, 0xFFFFE4BA, 0xFFFFD098};
        float[] lw = SpatialTelemetryFusion.sampleLumaAndWarmth(warmBright);
        assertTrue(lw[0] > 0.80f);
        assertTrue(lw[1] > 0.20f);
    }

    @Test
    public void enuLocalGridAndGoogleEarthUrlAreGeometricallyAccurate() {
        // Move ~111m North from origin (0.001 deg latitude)
        SpatialTelemetryFusion.EnuGridCoord enu = SpatialTelemetryFusion.toLocalEnuGrid(
                36.6177, -121.9166, 15.0,
                36.6187, -121.9166, 18.5);
        assertEquals(0.0, enu.eastMeters, 0.5);
        assertEquals(111.19, enu.northMeters, 1.0);
        assertEquals(3.5, enu.upMeters, 1e-4);
        assertTrue(enu.gridCellCode.startsWith("G[+0E,+22N]"));

        String earthUrl = SpatialTelemetryFusion.buildGoogleEarthUrl(36.6177, -121.9166, 15.0, 45.0f);
        assertTrue(earthUrl.startsWith("https://earth.google.com/web/@36.617700,-121.916600,15.0a"));
        assertTrue(earthUrl.contains("45.0h"));
        assertEquals("NE", SpatialTelemetryFusion.compassCardinal(45.0f));
        assertEquals("NW", SpatialTelemetryFusion.compassCardinal(-45.0f));
    }

    @Test
    public void cernKlosterFusionQuantifiesActiveChannelsM4AndZoneShift() {
        SpatialTelemetryFusion.LightFieldState indoor = SpatialTelemetryFusion.computeLightField(
                0.35f, 0.40f, 0.1f, 0.15f, true);
        SpatialTelemetryFusion.EnuGridCoord origin = SpatialTelemetryFusion.toLocalEnuGrid(
                36.6177, -121.9166, 10.0, 36.6177, -121.9166, 10.0);

        SpatialTelemetryFusion.TelemetryInput roomA = new SpatialTelemetryFusion.TelemetryInput(
                0.92f, 0.35f, 1.80f, 180f, 0.0f, 92.0f,
                -52, 5180, -64, 3, -95, 3, true, indoor, origin);

        SpatialTelemetryFusion.FusedFieldSnapshot snapA = SpatialTelemetryFusion.fuse(roomA, null);
        assertNotNull(snapA);
        assertEquals(6, snapA.channelSpectrum.length);
        double sum = 0.0;
        for (double p : snapA.channelSpectrum) {
            sum += p;
        }
        assertEquals(1.0, sum, 1e-9);
        assertTrue(snapA.klosterATau >= 3 && snapA.klosterATau <= 6);
        assertTrue(snapA.klosterM4Root >= 0.26 && snapA.klosterM4Root <= 1.0);
        assertTrue(snapA.spatialCoherence > 0.55f);
        assertFalse(snapA.zoneChanged);
        // Acoustic echo 1.80m -> comfortable ~1.22m hover depth
        assertEquals(1.80f * 0.68f, snapA.suggestedDepthMeters, 0.05f);
        assertTrue(snapA.compactHudLine.contains("Aτ="));
        assertTrue(snapA.compactHudLine.contains("WiFi -52dBm"));
        assertTrue(snapA.compactHudLine.contains("Cell -95dBm"));
        assertTrue(snapA.compactHudLine.contains("Echo 1.8m"));

        // Walk outdoors: Wi-Fi drops completely, strong sunlight + strong cellular + BLE disappears -> zone shift!
        SpatialTelemetryFusion.LightFieldState outdoor = SpatialTelemetryFusion.computeLightField(
                0.95f, 0.85f, 0.0f, 0.0f, true);
        SpatialTelemetryFusion.TelemetryInput outside = new SpatialTelemetryFusion.TelemetryInput(
                0.40f, 0.10f, -1f, 8000f, -3.2f, 185.0f,
                -127, 0, -127, 0, -70, 4, true, outdoor, origin);
        SpatialTelemetryFusion.FusedFieldSnapshot snapB = SpatialTelemetryFusion.fuse(outside, snapA);
        assertTrue(snapB.zoneShiftScore >= 0.16f);
        assertTrue(snapB.zoneChanged);
        assertTrue(snapB.voiceContextLine.contains("zone transition"));
    }
}
