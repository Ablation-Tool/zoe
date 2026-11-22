package research.zoetic.zoe;

import java.util.Locale;

/**
 * Multi-Sensor Spatial Telemetry Fusion Engine for Zoe Explore (v0.9.6-beta).
 *
 * Pure, deterministic spatial mathematics fusing on-device physical sensors without heavy ARCore SLAM:
 *   1. Dual-Camera Optical Geometry & Front/Back Light-Field:
 *      - Computes true hardware vertical FOV from Camera2 focal length + sensor dimensions for BOTH lenses.
 *      - Uses optional brief front+rear ambient luminance & warmth calibration so Zoe renders rim lighting
 *        and contrast in front of you grounded in the real lighting behind you (zero continuous dual-stream load!).
 *   2. Local ENU Metric Grid + GPS + Google Earth / geo: Orientation:
 *      - Converts opt-in WGS-84 (lat, lon, alt) relative to session origin into local metric (East, North, Up)
 *        grid coordinates + compass cardinal heading + one-tap Google Earth Web / geo: context link.
 *   3. CERN / Kloster A_tau(p) & M_4^(1/4) Multi-Channel Spatial Field Detector:
 *      - Normalizes [IMU stability, Acoustic energy, Front/Rear optical contrast, Wi-Fi RSSI, BLE proximity,
 *        Cellular radio signal] into a probability simplex p, computes Kloster Accessible Volume A_tau(p) via
 *        AccessibleVolume.measure(), and CERN fourth-moment concentration M_4^(1/4) = (sum p_i^4)^(1/4)
 *        to quantify spatial coherence and room/zone transitions locally with ZERO PII!
 *
 * Constitutional Privacy Guarantee (CONSTITUTION.md):
 *   - All sensors start strictly OFF until user opt-in.
 *   - RF telemetry uses strictly coarse signal strength (dBm / level) — NEVER SSIDs, MACs, IMSI, IMEI,
 *     ICCID, or phone numbers.
 */
final class SpatialTelemetryFusion {
    static final double EARTH_RADIUS_M = 6_371_008.8;
    static final double CHANNEL_TAU = 0.12;
    static final float DEFAULT_FOV_RAD = ArExploreBrain.DEFAULT_SPATIAL_FOV_RAD;

    private SpatialTelemetryFusion() {
    }

    static final class CameraOptics {
        final float rearVerticalFovRad;
        final float frontVerticalFovRad;
        final float rearFocalMm;
        final float frontFocalMm;
        final float rearAperture;
        final float frontAperture;

        CameraOptics(float rearVerticalFovRad, float frontVerticalFovRad,
                     float rearFocalMm, float frontFocalMm,
                     float rearAperture, float frontAperture) {
            this.rearVerticalFovRad = clampFov(rearVerticalFovRad);
            this.frontVerticalFovRad = clampFov(frontVerticalFovRad);
            this.rearFocalMm = Math.max(0f, rearFocalMm);
            this.frontFocalMm = Math.max(0f, frontFocalMm);
            this.rearAperture = Math.max(0f, rearAperture);
            this.frontAperture = Math.max(0f, frontAperture);
        }

        static CameraOptics defaults() {
            return new CameraOptics(DEFAULT_FOV_RAD, 1.18f, 0f, 0f, 0f, 0f);
        }

        float activeFovRad(boolean frontActive) {
            return frontActive ? frontVerticalFovRad : rearVerticalFovRad;
        }
    }

    static final class LightFieldState {
        final float rearLuma;       // 0..1 average brightness in front of user
        final float frontLuma;      // 0..1 average brightness behind user
        final float rearWarmth;     // -1 (cool) .. +1 (warm)
        final float frontWarmth;    // -1 (cool) .. +1 (warm)
        final float backlightRatio; // frontLuma / (rearLuma + 0.08)
        final float rimIntensity;   // 0.18..1.0 specular rim boost on Zoe GEM
        final float contrastBoost;  // 0.75..1.45 halo contrast over bright/dark camera scene
        final boolean calibrated;

        LightFieldState(float rearLuma, float frontLuma, float rearWarmth, float frontWarmth,
                        float backlightRatio, float rimIntensity, float contrastBoost, boolean calibrated) {
            this.rearLuma = rearLuma;
            this.frontLuma = frontLuma;
            this.rearWarmth = rearWarmth;
            this.frontWarmth = frontWarmth;
            this.backlightRatio = backlightRatio;
            this.rimIntensity = rimIntensity;
            this.contrastBoost = contrastBoost;
            this.calibrated = calibrated;
        }

        static LightFieldState neutral() {
            return new LightFieldState(0.45f, 0.45f, 0f, 0f, 0.85f, 0.45f, 1.0f, false);
        }
    }

    static final class EnuGridCoord {
        final double eastMeters;
        final double northMeters;
        final double upMeters;
        final double distanceFromOriginMeters;
        final String gridCellCode;

        EnuGridCoord(double eastMeters, double northMeters, double upMeters,
                     double distanceFromOriginMeters, String gridCellCode) {
            this.eastMeters = eastMeters;
            this.northMeters = northMeters;
            this.upMeters = upMeters;
            this.distanceFromOriginMeters = distanceFromOriginMeters;
            this.gridCellCode = gridCellCode;
        }
    }

    static final class TelemetryInput {
        final float imuStability;      // 0..1 (1 = steady hand, 0 = rapid pan)
        final float acousticEnergy;    // 0..1 (from mic RMS or echo ping)
        final float acousticEchoMeters;// <= 0 if no echo ping yet
        final float ambientLux;        // >= 0 hardware light sensor lux
        final float baroDeltaMeters;   // relative vertical meters from session start
        final float compassDegrees;    // 0..360 true/magnetic azimuth, NaN if unavailable
        final int wifiRssiDbm;         // -127 if unavailable
        final int wifiFreqMhz;         // 0 if unavailable
        final int bleStrongestRssiDbm; // -127 if unavailable
        final int bleNearbyCount;      // non-identifying count only
        final int cellDbm;             // -140 if unavailable
        final int cellLevel;           // 0..4 (non-identifying OS radio bar level)
        final boolean simReady;        // boolean presence only — NEVER reads IMSI/ICCID/number
        final LightFieldState lightField;
        final EnuGridCoord gridCoord;  // nullable if GPS off

        TelemetryInput(float imuStability, float acousticEnergy, float acousticEchoMeters,
                       float ambientLux, float baroDeltaMeters, float compassDegrees,
                       int wifiRssiDbm, int wifiFreqMhz,
                       int bleStrongestRssiDbm, int bleNearbyCount,
                       int cellDbm, int cellLevel, boolean simReady,
                       LightFieldState lightField, EnuGridCoord gridCoord) {
            this.imuStability = clamp01(imuStability);
            this.acousticEnergy = clamp01(acousticEnergy);
            this.acousticEchoMeters = acousticEchoMeters;
            this.ambientLux = Math.max(0f, ambientLux);
            this.baroDeltaMeters = Float.isFinite(baroDeltaMeters) ? baroDeltaMeters : 0f;
            this.compassDegrees = compassDegrees;
            this.wifiRssiDbm = wifiRssiDbm;
            this.wifiFreqMhz = Math.max(0, wifiFreqMhz);
            this.bleStrongestRssiDbm = bleStrongestRssiDbm;
            this.bleNearbyCount = Math.max(0, bleNearbyCount);
            this.cellDbm = cellDbm;
            this.cellLevel = Math.max(0, Math.min(4, cellLevel));
            this.simReady = simReady;
            this.lightField = lightField == null ? LightFieldState.neutral() : lightField;
            this.gridCoord = gridCoord;
        }
    }

    static final class FusedFieldSnapshot {
        final double[] channelSpectrum;    // 6-channel probability simplex summing to 1.0
        final int klosterATau;             // Kloster A_tau(p) active sensing channels (1..6)
        final double klosterM4Root;        // CERN fourth-moment trigger M_4^(1/4) in [6^(-3/4)≈0.261, 1.0]
        final float spatialCoherence;      // 0..1 overall multi-sensor fusion lock
        final float zoneShiftScore;        // 0..1 L1 spectral novelty vs previous snapshot
        final boolean zoneChanged;         // true when RF+optical+baro indicate a new room/zone
        final float suggestedDepthMeters;  // acoustic + optical fused hover depth (0.75..2.2m)
        final LightFieldState lightField;
        final EnuGridCoord gridCoord;
        final float compassDegrees;
        final float baroDeltaMeters;
        final String compactHudLine;
        final String voiceContextLine;

        FusedFieldSnapshot(double[] channelSpectrum, int klosterATau, double klosterM4Root,
                           float spatialCoherence, float zoneShiftScore, boolean zoneChanged,
                           float suggestedDepthMeters, LightFieldState lightField, EnuGridCoord gridCoord,
                           float compassDegrees, float baroDeltaMeters,
                           String compactHudLine, String voiceContextLine) {
            this.channelSpectrum = channelSpectrum;
            this.klosterATau = klosterATau;
            this.klosterM4Root = klosterM4Root;
            this.spatialCoherence = spatialCoherence;
            this.zoneShiftScore = zoneShiftScore;
            this.zoneChanged = zoneChanged;
            this.suggestedDepthMeters = suggestedDepthMeters;
            this.lightField = lightField;
            this.gridCoord = gridCoord;
            this.compassDegrees = compassDegrees;
            this.baroDeltaMeters = baroDeltaMeters;
            this.compactHudLine = compactHudLine;
            this.voiceContextLine = voiceContextLine;
        }
    }

    /**
     * Exact pinhole camera vertical field-of-view (radians) from Camera2 physical sensor height & focal length.
     * For portrait orientation, Android sensor width runs vertically so we compute from the long/portrait axis cleanly.
     */
    static float computeVerticalFovRad(float sensorLongMm, float sensorShortMm, float focalLengthMm, boolean portrait) {
        if (!Float.isFinite(focalLengthMm) || focalLengthMm <= 0.1f) {
            return DEFAULT_FOV_RAD;
        }
        float axisMm = portrait ? Math.max(sensorLongMm, sensorShortMm) : Math.min(sensorLongMm, sensorShortMm);
        if (!Float.isFinite(axisMm) || axisMm <= 0.1f) {
            return DEFAULT_FOV_RAD;
        }
        float fov = (float) (2.0 * Math.atan(axisMm / (2.0 * focalLengthMm)));
        return clampFov(fov);
    }

    /**
     * Computes physically grounded rim lighting & contrast adaptation for Zoe rendered in front of you,
     * knowing the ambient brightness & color warmth behind you (front camera) vs in front of you (rear camera).
     */
    static LightFieldState computeLightField(float rearLuma, float frontLuma,
                                             float rearWarmth, float frontWarmth,
                                             boolean calibrated) {
        float rl = clamp01(rearLuma);
        float fl = clamp01(frontLuma);
        float rw = clampSigned(rearWarmth);
        float fw = clampSigned(frontWarmth);
        float ratio = fl / (rl + 0.08f);
        // Stronger rim glow when bright light is behind the user (frontLuma > rearLuma)
        float rim = clampRange(0.24f + 0.56f * fl + 0.22f * Math.max(0f, fl - rl), 0.18f, 1.0f);
        // Boost halo contrast slightly over very bright scenes so Zoe stays crisp in sunlight
        float contrast = clampRange(0.84f + 0.56f * rl, 0.78f, 1.42f);
        return new LightFieldState(rl, fl, rw, fw, ratio, rim, contrast, calibrated);
    }

    /**
     * Extracts normalized luminance (0..1) and color warmth (-1..+1) from ARGB pixel samples.
     */
    static float[] sampleLumaAndWarmth(int[] argbPixels) {
        if (argbPixels == null || argbPixels.length == 0) {
            return new float[]{0.45f, 0f};
        }
        int step = Math.max(1, argbPixels.length / 256);
        double sumLuma = 0.0;
        double sumWarm = 0.0;
        int count = 0;
        for (int i = 0; i < argbPixels.length; i += step) {
            int px = argbPixels[i];
            double r = ((px >> 16) & 0xFF) / 255.0;
            double g = ((px >> 8) & 0xFF) / 255.0;
            double b = (px & 0xFF) / 255.0;
            sumLuma += 0.2126 * r + 0.7152 * g + 0.0722 * b;
            sumWarm += (r - b);
            count++;
        }
        if (count == 0) {
            return new float[]{0.45f, 0f};
        }
        return new float[]{
                clamp01((float) (sumLuma / count)),
                clampSigned((float) (sumWarm / count))
        };
    }

    /**
     * Converts WGS-84 GPS (lat, lon, alt) relative to a local origin into local metric ENU grid coordinates.
     * Uses tangent-plane projection (accurate to < 0.01% across neighborhood/campus exploration scales)
     * paired with LocationMath.haversineMeters for total horizontal distance.
     */
    static EnuGridCoord toLocalEnuGrid(double originLat, double originLon, double originAltMeters,
                                       double curLat, double curLon, double curAltMeters) {
        double horizDist = LocationMath.haversineMeters(originLat, originLon, curLat, curLon);
        double dLatRad = Math.toRadians(curLat - originLat);
        double dLonRad = Math.toRadians(curLon - originLon);
        double meanLatRad = Math.toRadians((originLat + curLat) * 0.5);
        double north = dLatRad * EARTH_RADIUS_M;
        double east = dLonRad * EARTH_RADIUS_M * Math.cos(meanLatRad);
        double up = (Double.isFinite(curAltMeters) && Double.isFinite(originAltMeters))
                ? (curAltMeters - originAltMeters)
                : 0.0;
        int cellE = (int) Math.floor(east / 5.0);
        int cellN = (int) Math.floor(north / 5.0);
        String code = String.format(Locale.US, "G[%+dE,%+dN]", cellE, cellN);
        return new EnuGridCoord(east, north, up, horizDist, code);
    }

    /**
     * Builds a clean Google Earth Web 3D camera link grounded at the user's opt-in GPS position & compass heading.
     */
    static String buildGoogleEarthUrl(double lat, double lon, double altMeters, float headingDegrees) {
        if (!Double.isFinite(lat) || !Double.isFinite(lon) || Math.abs(lat) > 90.0 || Math.abs(lon) > 180.0) {
            throw new IllegalArgumentException("invalid coordinates for Google Earth URL");
        }
        double safeAlt = Double.isFinite(altMeters) ? Math.max(0.0, altMeters) : 10.0;
        double safeHeading = Float.isFinite(headingDegrees) ? normalizeHeading(headingDegrees) : 0.0;
        return String.format(Locale.US,
                "https://earth.google.com/web/@%.6f,%.6f,%.1fa,180d,35y,%.1fh,45t,0r",
                lat, lon, safeAlt, safeHeading);
    }

    /**
     * Computes CERN / Kloster fourth-moment spectral trigger M_4^(1/4) = (sum_i p_i^4)^(1/4).
     * Peaks near 1.0 when a single sensor channel spikes; stays near k^(-3/4) when channels are balanced.
     */
    static double klosterFourthMomentRoot(double[] probabilities) {
        if (probabilities == null || probabilities.length == 0) {
            return 0.0;
        }
        double sum4 = 0.0;
        for (double p : probabilities) {
            double clamped = Math.max(0.0, p);
            double p2 = clamped * clamped;
            sum4 += p2 * p2;
        }
        return Math.pow(Math.max(0.0, sum4), 0.25);
    }

    /**
     * Normalizes RF RSSI in dBm (typically -115..-35 dBm) to a 0..1 signal-strength energy score.
     */
    static float normalizeRssiDbm(int rssiDbm, int minDbm, int maxDbm) {
        if (rssiDbm <= minDbm - 10 || rssiDbm > 0) {
            return 0f;
        }
        return clamp01((rssiDbm - minDbm) / (float) Math.max(1, maxDbm - minDbm));
    }

    static String compassCardinal(float degrees) {
        if (!Float.isFinite(degrees)) {
            return "--";
        }
        String[] dirs = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"};
        double norm = normalizeHeading(degrees);
        int idx = (int) Math.floor(((norm + 22.5) % 360.0) / 45.0);
        return dirs[Math.max(0, Math.min(7, idx))];
    }

    static double normalizeHeading(double deg) {
        double m = deg % 360.0;
        return m < 0.0 ? m + 360.0 : m;
    }

    /**
     * Core Multi-Sensor Spatial Telemetry Fusion step.
     * Fuses IMU + Acoustic + Front/Rear Optical Light-Field + Wi-Fi + BLE + Cellular signal into
     * Kloster A_tau(p), CERN M_4^(1/4), spatial coherence, zone-shift novelty, and hover depth.
     */
    static FusedFieldSnapshot fuse(TelemetryInput in, FusedFieldSnapshot previous) {
        float wifiEnergy = normalizeRssiDbm(in.wifiRssiDbm, -100, -35);
        float bleEnergy = Math.max(
                normalizeRssiDbm(in.bleStrongestRssiDbm, -105, -40),
                Math.min(1f, in.bleNearbyCount * 0.18f));
        float cellEnergy = in.cellDbm > -135
                ? normalizeRssiDbm(in.cellDbm, -125, -65)
                : (in.simReady ? (in.cellLevel / 4.0f) : 0f);
        float opticalEnergy = clamp01(0.45f * in.lightField.rearLuma
                + 0.35f * in.lightField.frontLuma
                + 0.20f * Math.min(1f, (float) (Math.log1p(in.ambientLux) / Math.log1p(2000.0))));

        // 6-channel spatial energy vector: [IMU, Acoustic, Optical(Front+Back), Wi-Fi, BLE, Cellular/SIM]
        double[] raw = new double[]{
                Math.max(0.05, in.imuStability),
                Math.max(0.03, in.acousticEnergy),
                Math.max(0.05, opticalEnergy),
                Math.max(0.02, wifiEnergy),
                Math.max(0.02, bleEnergy),
                Math.max(0.02, cellEnergy)
        };
        double sum = 0.0;
        for (double v : raw) {
            sum += v;
        }
        double[] spectrum = new double[raw.length];
        for (int i = 0; i < raw.length; i++) {
            spectrum[i] = raw[i] / sum;
        }

        // Exact Kloster Accessible Volume A_tau(p) & CERN M_4^(1/4) spectral trigger!
        AccessibleVolume.Result kloster = AccessibleVolume.measure(spectrum, CHANNEL_TAU);
        double m4Root = klosterFourthMomentRoot(spectrum);

        // L1 spectral shift across rooms/lighting/RF zones
        float shift = 0f;
        if (previous != null && previous.channelSpectrum != null
                && previous.channelSpectrum.length == spectrum.length) {
            double l1 = 0.0;
            for (int i = 0; i < spectrum.length; i++) {
                l1 += Math.abs(spectrum[i] - previous.channelSpectrum[i]);
            }
            shift = clamp01((float) (l1 * 0.5));
        }
        boolean zoneChanged = shift >= 0.16f;

        // Spatial coherence rises with active sensing breadth A_tau and steady IMU
        float breadthNorm = (float) kloster.normalized;
        float coherence = clamp01(0.45f * breadthNorm + 0.35f * in.imuStability + 0.20f * (1f - shift));

        // Fuse acoustic echo reflection (if pinged) with ambient spaciousness for comfortable Zoe hover depth
        float depth = 1.20f;
        if (in.acousticEchoMeters > 0.35f && in.acousticEchoMeters < 4.5f) {
            depth = clampRange(in.acousticEchoMeters * 0.68f, 0.78f, 2.20f);
        } else if (in.lightField.rearLuma > 0.75f && cellEnergy > 0.45f) {
            // Bright outdoor / open-sky cue: Zoe hovers slightly wider
            depth = 1.48f;
        }

        StringBuilder hud = new StringBuilder();
        hud.append(String.format(Locale.US, "Aτ=%d/6 · M₄=%.2f", kloster.accessible, m4Root));
        if (Float.isFinite(in.compassDegrees)) {
            hud.append(String.format(Locale.US, " · %s %03.0f°",
                    compassCardinal(in.compassDegrees), normalizeHeading(in.compassDegrees)));
        }
        if (in.gridCoord != null) {
            hud.append(String.format(Locale.US, " · %s", in.gridCoord.gridCellCode));
        }
        if (in.wifiRssiDbm > -115) {
            hud.append(String.format(Locale.US, " · WiFi %ddBm", in.wifiRssiDbm));
        }
        if (in.cellDbm > -135) {
            hud.append(String.format(Locale.US, " · Cell %ddBm", in.cellDbm));
        } else if (in.simReady && in.cellLevel > 0) {
            hud.append(String.format(Locale.US, " · Cell %d/4", in.cellLevel));
        }
        if (in.bleNearbyCount > 0) {
            hud.append(String.format(Locale.US, " · BLE %d", in.bleNearbyCount));
        }
        if (in.lightField.calibrated) {
            hud.append(String.format(Locale.US, " · Cam B/F %.0f%%/%.0f%%",
                    in.lightField.rearLuma * 100f, in.lightField.frontLuma * 100f));
        }
        if (in.acousticEchoMeters > 0.3f) {
            hud.append(String.format(Locale.US, " · Echo %.1fm", in.acousticEchoMeters));
        }

        StringBuilder voice = new StringBuilder();
        voice.append(String.format(Locale.US,
                "Spatial telemetry: Kloster A_tau=%d/6, M4=%.2f, coherence=%.0f%%",
                kloster.accessible, m4Root, coherence * 100f));
        if (Float.isFinite(in.compassDegrees)) {
            voice.append(String.format(Locale.US, ", facing %s (%.0f deg)",
                    compassCardinal(in.compassDegrees), normalizeHeading(in.compassDegrees)));
        }
        if (in.gridCoord != null) {
            voice.append(String.format(Locale.US, ", local ENU grid (E %.1fm, N %.1fm, U %.1fm)",
                    in.gridCoord.eastMeters, in.gridCoord.northMeters, in.gridCoord.upMeters));
        }
        if (in.lightField.calibrated) {
            voice.append(String.format(Locale.US,
                    ", front-behind luminance %.0f%% vs rear-ahead %.0f%% (backlight ratio %.2f)",
                    in.lightField.frontLuma * 100f, in.lightField.rearLuma * 100f, in.lightField.backlightRatio));
        }
        if (in.acousticEchoMeters > 0.3f) {
            voice.append(String.format(Locale.US, ", acoustic echo reflection ~%.1fm", in.acousticEchoMeters));
        }
        if (zoneChanged) {
            voice.append(", RF+optical zone transition detected");
        }
        voice.append(".");

        return new FusedFieldSnapshot(
                spectrum,
                kloster.accessible,
                m4Root,
                coherence,
                shift,
                zoneChanged,
                depth,
                in.lightField,
                in.gridCoord,
                in.compassDegrees,
                in.baroDeltaMeters,
                hud.toString(),
                voice.toString()
        );
    }

    private static float clampFov(float fov) {
        if (!Float.isFinite(fov)) {
            return DEFAULT_FOV_RAD;
        }
        return Math.max(0.55f, Math.min(1.85f, fov));
    }

    private static float clamp01(float v) {
        if (!Float.isFinite(v)) {
            return 0f;
        }
        return Math.max(0f, Math.min(1f, v));
    }

    private static float clampSigned(float v) {
        if (!Float.isFinite(v)) {
            return 0f;
        }
        return Math.max(-1f, Math.min(1f, v));
    }

    private static float clampRange(float v, float lo, float hi) {
        if (!Float.isFinite(v)) {
            return lo;
        }
        return Math.max(lo, Math.min(hi, v));
    }
}
