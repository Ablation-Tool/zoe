package research.zoetic.zoe;

import java.util.Locale;

/**
 * Clean-Room Live-View Ergonomics, Pedestrian Dead-Reckoning & Voice-Action Router (v0.9.8-beta).
 *
 * Uses built-in Android platform telemetry patterns (True-North GeomagneticField declination,
 * hardware Step Detector dead-reckoning, pitch-based Tilt-Down Safety Rest / Tilt-Up AR,
 * floating bearing chevrons, and Google Maps Walking/Live-View handoff) PLUS fixes the
 * "Zoe pretending to be deaf or blind" issues:
 *   1. Direct Explore Voice-Action Router so Zoe immediately obeys spoken navigation & camera commands
 *   2. Partial-transcript rescue helper so Pixel SpeechRecognizer timeouts never drop your question
 *   3. Anti-blindness reply guard so compact local LLMs never answer "I cannot see" when live camera is ON!
 */
final class LiveViewErgonomics {
    enum Posture {
        ACTIVE_AR,      // Phone raised (eye/chest level): bright crisp AR & full sight
        SAFETY_REST     // Phone tilted down (>58° toward ground): calm eyes-up safety rest & battery save
    }

    enum ExploreVoiceAction {
        NONE,
        FLIP_CAMERA,
        RECENTER_ZOE,
        TOGGLE_ROAM_ON,
        TOGGLE_ROAM_OFF,
        ENABLE_DEAF_MODE,
        ENABLE_BLIND_MODE,
        ENABLE_KID_MODE,
        ENABLE_STANDARD_MODE,
        ENABLE_FIELD,
        DISABLE_FIELD,
        DUAL_CAM_SWEEP,
        ECHO_PING,
        ANNOUNCE_ORIENTATION,
        OPEN_GOOGLE_EARTH,
        OPEN_GOOGLE_MAPS_WALK,
        GUIDE_BEARING,
        CLEAR_GUIDE,
        OPEN_TOOLS
    }

    static final class ParsedVoiceAction {
        final ExploreVoiceAction action;
        final String targetQuery;      // e.g., destination name for Google Maps Walking / Live View
        final float targetBearingDeg;  // 0..360 if GUIDE_BEARING, NaN otherwise

        ParsedVoiceAction(ExploreVoiceAction action, String targetQuery, float targetBearingDeg) {
            this.action = action == null ? ExploreVoiceAction.NONE : action;
            this.targetQuery = targetQuery == null ? "" : targetQuery.trim();
            this.targetBearingDeg = targetBearingDeg;
        }
    }

    static final class PdrState {
        final double eastMeters;
        final double northMeters;
        final int stepCount;

        PdrState(double eastMeters, double northMeters, int stepCount) {
            this.eastMeters = eastMeters;
            this.northMeters = northMeters;
            this.stepCount = Math.max(0, stepCount);
        }
    }

    static final float DEFAULT_STRIDE_METERS = 0.72f;
    static final float TILT_DOWN_ENTER_DEG = -58f;
    static final float TILT_UP_EXIT_DEG = -44f;

    private LiveViewErgonomics() {
    }

    /**
     * Converts magnetic azimuth to True Geographic North using Android GeomagneticField declination.
     */
    static float magneticToTrueNorth(float magneticHeadingDeg, float declinationDeg) {
        if (!Float.isFinite(magneticHeadingDeg)) {
            return Float.NaN;
        }
        float decl = Float.isFinite(declinationDeg) ? declinationDeg : 0f;
        return (float) SpatialTelemetryFusion.normalizeHeading(magneticHeadingDeg + decl);
    }

    /**
     * Hysteresis state machine for signature Live-View ergonomic posture:
     *   - Tilt phone down below -58° -> calm SAFETY_REST ("eyes up, watch your step", saves battery)
     *   - Raise phone above -44° -> snaps cleanly back to ACTIVE_AR without flicker!
     */
    static Posture nextPosture(Posture current, float pitchDegrees) {
        Posture cur = current == null ? Posture.ACTIVE_AR : current;
        if (!Float.isFinite(pitchDegrees)) {
            return cur;
        }
        if (cur == Posture.ACTIVE_AR && pitchDegrees < TILT_DOWN_ENTER_DEG) {
            return Posture.SAFETY_REST;
        }
        if (cur == Posture.SAFETY_REST && pitchDegrees > TILT_UP_EXIT_DEG) {
            return Posture.ACTIVE_AR;
        }
        return cur;
    }

    /**
     * Advances local ENU Pedestrian Dead-Reckoning by one detected hardware footstep along True-North heading.
     * Works 100% indoors with ZERO GPS lock!
     */
    static PdrState advanceStep(PdrState current, float trueHeadingDeg, float strideMeters) {
        PdrState cur = current == null ? new PdrState(0.0, 0.0, 0) : current;
        float stride = (Float.isFinite(strideMeters) && strideMeters > 0.25f && strideMeters < 1.5f)
                ? strideMeters : DEFAULT_STRIDE_METERS;
        if (!Float.isFinite(trueHeadingDeg)) {
            return new PdrState(cur.eastMeters, cur.northMeters, cur.stepCount + 1);
        }
        double rad = Math.toRadians(SpatialTelemetryFusion.normalizeHeading(trueHeadingDeg));
        double dEast = stride * Math.sin(rad);
        double dNorth = stride * Math.cos(rad);
        return new PdrState(cur.eastMeters + dEast, cur.northMeters + dNorth, cur.stepCount + 1);
    }

    /**
     * Complementary fusion blending indoor/smooth PDR ENU with outdoor GPS ENU when GPS accuracy is good.
     */
    static PdrState blendWithGpsEnu(PdrState pdr, double gpsEastM, double gpsNorthM, float gpsAccuracyM) {
        PdrState cur = pdr == null ? new PdrState(0.0, 0.0, 0) : pdr;
        if (!Double.isFinite(gpsEastM) || !Double.isFinite(gpsNorthM)
                || !Float.isFinite(gpsAccuracyM) || gpsAccuracyM <= 0f || gpsAccuracyM > 35f) {
            return cur;
        }
        // Stronger GPS trust when accuracy <= 8m, softer pull when 10..35m
        double alpha = Math.max(0.08, Math.min(0.45, 4.0 / Math.max(4.0, gpsAccuracyM)));
        double e = cur.eastMeters + (gpsEastM - cur.eastMeters) * alpha;
        double n = cur.northMeters + (gpsNorthM - cur.northMeters) * alpha;
        return new PdrState(e, n, cur.stepCount);
    }

    /**
     * Signed shortest angular delta from current heading to target bearing in [-180, +180] degrees.
     * Positive = turn right; Negative = turn left; |delta| <= 12° = locked straight ahead!
     */
    static float signedBearingDeltaDeg(float currentHeadingDeg, float targetBearingDeg) {
        if (!Float.isFinite(currentHeadingDeg) || !Float.isFinite(targetBearingDeg)) {
            return 0f;
        }
        double diff = ((targetBearingDeg - currentHeadingDeg) % 360.0 + 540.0) % 360.0 - 180.0;
        return (float) diff;
    }

    /**
     * Builds Android's public Google Maps Walking Navigation URI (which includes Google Maps Live View on Pixel!).
     */
    static String buildGoogleMapsWalkingUri(String destination) {
        String clean = destination == null ? "" : destination.trim();
        if (clean.isEmpty()) {
            return "https://www.google.com/maps";
        }
        return "google.navigation:q=" + UriEncoder.encodeQueryComponent(clean) + "&mode=w";
    }

    /**
     * Parses direct spoken commands inside Zoe Explore so Zoe IMMEDIATELY obeys what you ask
     * instead of ignoring you or replying with generic text!
     */
    static ParsedVoiceAction parseExploreVoiceAction(String spoken) {
        if (spoken == null || spoken.trim().isEmpty()) {
            return new ParsedVoiceAction(ExploreVoiceAction.NONE, "", Float.NaN);
        }
        String raw = spoken.trim();
        String l = raw.toLowerCase(Locale.US).replaceAll("[^a-z0-9\\s'-]", " ").replaceAll("\\s+", " ").trim();

        if (l.contains("flip camera") || l.contains("switch camera") || l.contains("front camera")
                || l.contains("rear camera") || l.contains("back camera") || l.contains("selfie camera")) {
            return new ParsedVoiceAction(ExploreVoiceAction.FLIP_CAMERA, "", Float.NaN);
        }
        if (l.contains("come here") || l.contains("recenter") || l.contains("over here")
                || l.contains("back in front") || l.contains("center yourself")) {
            return new ParsedVoiceAction(ExploreVoiceAction.RECENTER_ZOE, "", Float.NaN);
        }
        if (l.contains("stop moving") || l.contains("stay still") || l.contains("stop roaming") || l.contains("stay put")) {
            return new ParsedVoiceAction(ExploreVoiceAction.TOGGLE_ROAM_OFF, "", Float.NaN);
        }
        if (l.contains("start roaming") || l.contains("float around") || l.contains("glide around")) {
            return new ParsedVoiceAction(ExploreVoiceAction.TOGGLE_ROAM_ON, "", Float.NaN);
        }
        if (l.contains("deaf mode") || l.contains("hard of hearing") || l.contains("silent captions")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ENABLE_DEAF_MODE, "", Float.NaN);
        }
        if (l.contains("blind mode") || l.contains("audio guide") || l.contains("low vision")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ENABLE_BLIND_MODE, "", Float.NaN);
        }
        if (l.contains("kid mode") || l.contains("kids mode") || l.contains("simple mode")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ENABLE_KID_MODE, "", Float.NaN);
        }
        if (l.contains("standard mode") || l.contains("normal mode")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ENABLE_STANDARD_MODE, "", Float.NaN);
        }
        if (l.contains("dual cam") || l.contains("behind me") || l.contains("check lighting") || l.contains("light field")) {
            return new ParsedVoiceAction(ExploreVoiceAction.DUAL_CAM_SWEEP, "", Float.NaN);
        }
        if (l.contains("echo ping") || l.contains("sound ping") || l.contains("how far is the wall") || l.contains("acoustic")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ECHO_PING, "", Float.NaN);
        }
        if (l.contains("field on") || l.contains("sensors on") || l.contains("telemetry on") || l.contains("turn on sensors")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ENABLE_FIELD, "", Float.NaN);
        }
        if (l.contains("field off") || l.contains("sensors off") || l.contains("telemetry off") || l.contains("turn off sensors")) {
            return new ParsedVoiceAction(ExploreVoiceAction.DISABLE_FIELD, "", Float.NaN);
        }
        if (l.contains("open google earth") || l.contains("google earth")) {
            return new ParsedVoiceAction(ExploreVoiceAction.OPEN_GOOGLE_EARTH, "", Float.NaN);
        }
        if (l.contains("open settings") || l.contains("open tools") || l.contains("accessibility settings")) {
            return new ParsedVoiceAction(ExploreVoiceAction.OPEN_TOOLS, "", Float.NaN);
        }
        if (l.contains("clear guide") || l.contains("stop guiding") || l.contains("cancel guide")) {
            return new ParsedVoiceAction(ExploreVoiceAction.CLEAR_GUIDE, "", Float.NaN);
        }
        // Directional bearing guidance ("guide me north", "point me east", "which way is south")
        if (l.contains("guide me") || l.contains("point me") || l.contains("which way is") || l.contains("head ")) {
            Float bearing = parseCardinalBearing(l);
            if (bearing != null) {
                return new ParsedVoiceAction(ExploreVoiceAction.GUIDE_BEARING,
                        SpatialTelemetryFusion.compassCardinal(bearing), bearing);
            }
        }
        // Walking / Live View handoff ("walk to coffee shop", "live view to library", "directions to ...")
        for (String prefix : new String[]{"walk to ", "live view to ", "navigate to ", "directions to ", "google maps to "}) {
            int idx = l.indexOf(prefix);
            if (idx >= 0) {
                String dest = raw.substring(Math.min(raw.length(), idx + prefix.length())).trim();
                dest = dest.replaceAll("[?.!]+$", "").trim();
                if (!dest.isEmpty()) {
                    return new ParsedVoiceAction(ExploreVoiceAction.OPEN_GOOGLE_MAPS_WALK, dest, Float.NaN);
                }
            }
        }
        if (l.contains("where am i") || l.contains("what direction") || l.contains("which way am i facing")
                || l.contains("my heading") || l.contains("compass")) {
            return new ParsedVoiceAction(ExploreVoiceAction.ANNOUNCE_ORIENTATION, "", Float.NaN);
        }
        return new ParsedVoiceAction(ExploreVoiceAction.NONE, "", Float.NaN);
    }

    private static Float parseCardinalBearing(String lower) {
        if (lower.contains("northeast") || lower.contains("north east")) return 45f;
        if (lower.contains("northwest") || lower.contains("north west")) return 315f;
        if (lower.contains("southeast") || lower.contains("south east")) return 135f;
        if (lower.contains("southwest") || lower.contains("south west")) return 225f;
        if (lower.contains("north")) return 0f;
        if (lower.contains("east")) return 90f;
        if (lower.contains("south")) return 180f;
        if (lower.contains("west")) return 270f;
        return null;
    }

    /**
     * Decides whether a captured partial speech transcript should be rescued and sent to Zoe
     * when Android SpeechRecognizer fires ERROR_NO_MATCH or ERROR_SPEECH_TIMEOUT instead of onResults.
     */
    static boolean shouldRescuePartialTranscript(String partial, long partialTimestampMs, long nowMs) {
        if (partial == null) return false;
        String clean = partial.trim();
        if (clean.length() < 3) return false;
        if (nowMs - partialTimestampMs > 4_500L) return false;
        String alpha = clean.toLowerCase(Locale.US).replaceAll("[^a-z]", "");
        return alpha.length() >= 3 && !alpha.equals("hmm") && !alpha.equals("uhh");
    }

    /**
     * Detects when a small on-device LLM erroneously claims it "cannot see" or gives a robotic
     * generic greeting while Zoe's live camera IS actually active — so Zoe replaces it with real visual facts!
     */
    static boolean isBlindOrGenericHallucination(String llmReply, String userSpoken, boolean cameraActive) {
        if (!cameraActive || llmReply == null || llmReply.trim().isEmpty()) {
            return false;
        }
        String r = llmReply.toLowerCase(Locale.US);
        boolean claimsBlind = r.contains("cannot see") || r.contains("can't see")
                || r.contains("unable to see") || r.contains("don't have eyes")
                || r.contains("no access to your camera") || r.contains("as a text-based")
                || r.contains("as an ai language model") || r.contains("do not have visual");
        if (claimsBlind) {
            return true;
        }
        boolean askedToLook = LiveSessionLogic.isLikelyCameraQuestion(userSpoken);
        boolean genericGreeting = r.contains("how can i assist you today")
                || r.contains("how can i help you today")
                || (r.contains("open-source software assistant") && askedToLook);
        return askedToLook && genericGreeting;
    }

    /**
     * Builds a single, calm, decisive spoken description straight from live camera telemetry.
     * Commits to ONE clear label when confidence >= 65% (avoiding muddy "X or Y" hedging!).
     */
    static String buildGroundedVisualAnswer(String cameraReport, float distanceMeters,
                                            float compassDeg, boolean kidFriendly) {
        String primary = ArExploreBrain.extractPrimaryLabel(cameraReport);
        int primaryConf = extractPrimaryConfidencePct(cameraReport);
        String secondary = primaryConf >= 65 ? "" : extractSecondaryLabel(cameraReport);
        String ocr = ArExploreBrain.extractOcrSnippet(cameraReport);
        String colors = extractColorsClause(cameraReport);
        StringBuilder sb = new StringBuilder();
        if (!primary.isEmpty()) {
            sb.append(kidFriendly ? "Right there looks like " : "That looks like ")
                    .append(primary.toLowerCase(Locale.US));
            if (!secondary.isEmpty() && !secondary.equalsIgnoreCase(primary)) {
                sb.append(" or ").append(secondary.toLowerCase(Locale.US));
            }
            if (!colors.isEmpty()) {
                sb.append(" in ").append(colors);
            }
            sb.append(".");
        } else if (!ocr.isEmpty()) {
            sb.append("I can read \"").append(ocr).append("\" right there.");
        } else if (!colors.isEmpty()) {
            sb.append("I see ").append(colors).append(" — move a bit closer so I can spot the exact object.");
        } else {
            sb.append("Move a little closer or give it a bit more light so I can spot what's there.");
        }
        if (!ocr.isEmpty() && !primary.isEmpty()) {
            sb.append(" Text reads: \"").append(ocr).append("\".");
        }
        if (Float.isFinite(compassDeg)) {
            sb.append(String.format(Locale.US, " Facing %s.", SpatialTelemetryFusion.compassCardinal(compassDeg)));
        }
        return sb.toString().trim();
    }

    private static int extractPrimaryConfidencePct(String report) {
        if (report == null) return 0;
        int idx = report.indexOf("Labels:");
        if (idx < 0) return 0;
        int end = report.indexOf('.', idx);
        String body = (end > idx ? report.substring(idx + 7, end) : report.substring(idx + 7)).trim();
        int comma = body.indexOf(',');
        String first = (comma >= 0 ? body.substring(0, comma) : body).trim();
        int lp = first.lastIndexOf('(');
        int pct = first.lastIndexOf('%');
        if (lp >= 0 && pct > lp) {
            try {
                return Integer.parseInt(first.substring(lp + 1, pct).trim());
            } catch (NumberFormatException ignored) {
            }
        }
        return 0;
    }

    private static String extractSecondaryLabel(String report) {
        if (report == null) return "";
        int idx = report.indexOf("Labels:");
        if (idx < 0) return "";
        int end = report.indexOf('.', idx);
        String body = (end > idx ? report.substring(idx + 7, end) : report.substring(idx + 7)).trim();
        String[] parts = body.split(",");
        if (parts.length < 2) return "";
        String second = parts[1].replaceAll("\\s*\\([^)]*\\)", "").trim();
        if (second.equalsIgnoreCase("none above 55%") || second.equalsIgnoreCase("low-confidence scene")) {
            return "";
        }
        return second;
    }

    private static String extractColorsClause(String report) {
        if (report == null) return "";
        int idx = report.indexOf("Colors:");
        if (idx < 0) return "";
        int end = report.indexOf('.', idx);
        String raw = (end > idx ? report.substring(idx + 7, end) : report.substring(idx + 7)).trim();
        // Strip technical brightness percentages like "(59%)" so TTS & captions read naturally
        raw = raw.replaceAll("\\s*\\([^)]*%\\)", "").replaceAll("\\s+", " ").trim();
        return raw.toLowerCase(Locale.US);
    }

    /** Minimal pure-Java RFC 3986 query encoder so unit tests run on JVM without android.net.Uri. */
    private static final class UriEncoder {
        static String encodeQueryComponent(String s) {
            StringBuilder out = new StringBuilder(s.length() + 16);
            for (int i = 0; i < s.length(); i++) {
                char c = s.charAt(i);
                if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
                        || c == '-' || c == '_' || c == '.' || c == '~') {
                    out.append(c);
                } else if (c == ' ') {
                    out.append('+');
                } else {
                    out.append(String.format(Locale.US, "%%%02X", (int) c & 0xFF));
                }
            }
            return out.toString();
        }
    }
}
