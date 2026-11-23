package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.os.Build;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;

import java.util.Locale;

/**
 * Inclusive Accessibility & Adaptive Navigation Engine for Zoe Explore (v0.9.7-beta).
 *
 * Designed so Deaf / Hard-of-Hearing kids & adults, Blind / Low-Vision kids & adults,
 * Deaf-Blind users, and young kids can navigate their physical environment WITH Zoe using
 * their strongest sensory channels — with zero screen clutter:
 *
 *   - DEAF_HOH: Large high-contrast visual captions, visual Ambient Sound Radar ring,
 *     rich tactile haptic patterns, silent Type-to-Zoe chat bar, and muted TTS by default.
 *   - BLIND_LOW_VISION: Audio-first spatial narration with clock-face directions ("2 o'clock,
 *     about 1.2 meters"), stereo L/R spatial audio beacon chimes, tactile compass/landmark pulses,
 *     full-screen single-tap=Look / double-tap=Talk / long-press=Orientation gestures, and
 *     TalkBack live-region announcements.
 *   - KID_FRIENDLY (combinable with any mode!): Warm, simple, encouraging words, bigger targets,
 *     and zero technical jargon.
 */
final class ExploreAccessibility {
    enum Profile {
        STANDARD,
        DEAF_HOH,
        BLIND_LOW_VISION
    }

    enum HapticCue {
        LISTENING_READY,   // single gentle crisp pulse
        ZOE_SPOTTED,       // double playful tap (Zoe noticed something or arrived)
        ZOE_REPLYING,      // soft rising wave
        SOUND_ALERT,       // triple attention pulse for Deaf/HoH sound radar spike
        DIRECTION_LOCK,    // crisp center-alignment tick for Blind compass/target lock
        STOPPED            // single low release thud
    }

    static final class Settings {
        final Profile profile;
        final boolean kidFriendly;
        final boolean largeCaptions;
        final boolean hapticCues;
        final boolean visualSoundRadar;
        final boolean audioFirstNarration;
        final boolean spatialAudioBeacon;
        final boolean muteSpokenTts;
        final boolean showTypeBar;

        Settings(Profile profile, boolean kidFriendly, boolean largeCaptions, boolean hapticCues,
                 boolean visualSoundRadar, boolean audioFirstNarration, boolean spatialAudioBeacon,
                 boolean muteSpokenTts, boolean showTypeBar) {
            this.profile = profile == null ? Profile.STANDARD : profile;
            this.kidFriendly = kidFriendly;
            this.largeCaptions = largeCaptions;
            this.hapticCues = hapticCues;
            this.visualSoundRadar = visualSoundRadar;
            this.audioFirstNarration = audioFirstNarration;
            this.spatialAudioBeacon = spatialAudioBeacon;
            this.muteSpokenTts = muteSpokenTts;
            this.showTypeBar = showTypeBar;
        }

        static Settings standard() {
            return new Settings(Profile.STANDARD, false, false, true, false, false, false, false, false);
        }

        static Settings forProfile(Profile profile, boolean kidFriendly) {
            return switch (profile == null ? Profile.STANDARD : profile) {
                case DEAF_HOH -> new Settings(
                        Profile.DEAF_HOH, kidFriendly,
                        true,   // largeCaptions
                        true,   // hapticCues
                        true,   // visualSoundRadar
                        false,  // audioFirstNarration
                        false,  // spatialAudioBeacon
                        true,   // muteSpokenTts
                        true    // showTypeBar
                );
                case BLIND_LOW_VISION -> new Settings(
                        Profile.BLIND_LOW_VISION, kidFriendly,
                        true,   // largeCaptions (helps low-vision users too!)
                        true,   // hapticCues
                        false,  // visualSoundRadar
                        true,   // audioFirstNarration
                        true,   // spatialAudioBeacon
                        false,  // muteSpokenTts
                        false   // showTypeBar
                );
                default -> new Settings(
                        Profile.STANDARD, kidFriendly,
                        kidFriendly, // slightly larger friendly text for kids
                        true,
                        false,
                        false,
                        false,
                        false,
                        false
                );
            };
        }

        Settings withKidFriendly(boolean enabled) {
            return new Settings(profile, enabled, largeCaptions || enabled, hapticCues,
                    visualSoundRadar, audioFirstNarration, spatialAudioBeacon, muteSpokenTts, showTypeBar);
        }

        Settings withLargeCaptions(boolean enabled) {
            return new Settings(profile, kidFriendly, enabled, hapticCues,
                    visualSoundRadar, audioFirstNarration, spatialAudioBeacon, muteSpokenTts, showTypeBar);
        }

        Settings withHapticCues(boolean enabled) {
            return new Settings(profile, kidFriendly, largeCaptions, enabled,
                    visualSoundRadar, audioFirstNarration, spatialAudioBeacon, muteSpokenTts, showTypeBar);
        }

        Settings withVisualSoundRadar(boolean enabled) {
            return new Settings(profile, kidFriendly, largeCaptions, hapticCues,
                    enabled, audioFirstNarration, spatialAudioBeacon, muteSpokenTts, showTypeBar);
        }

        Settings withAudioFirstNarration(boolean enabled) {
            return new Settings(profile, kidFriendly, largeCaptions, hapticCues,
                    visualSoundRadar, enabled, spatialAudioBeacon, enabled ? false : muteSpokenTts, showTypeBar);
        }

        Settings withTypeBar(boolean enabled) {
            return new Settings(profile, kidFriendly, largeCaptions, hapticCues,
                    visualSoundRadar, audioFirstNarration, spatialAudioBeacon, muteSpokenTts, enabled);
        }

        String shortBadge() {
            String base = switch (profile) {
                case DEAF_HOH -> "Deaf / HoH";
                case BLIND_LOW_VISION -> "Blind / Audio";
                default -> "Standard";
            };
            return kidFriendly ? (base + " · Kid") : base;
        }
    }

    private static final String PREFS = "zoe_explore_accessibility_v1";

    private ExploreAccessibility() {
    }

    static Settings load(Context context) {
        if (context == null) {
            return Settings.standard();
        }
        SharedPreferences sp = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String profName = sp.getString("profile", Profile.STANDARD.name());
        Profile profile;
        try {
            profile = Profile.valueOf(profName);
        } catch (IllegalArgumentException ignored) {
            profile = Profile.STANDARD;
        }
        boolean kid = sp.getBoolean("kid", false);
        Settings def = Settings.forProfile(profile, kid);
        return new Settings(
                profile,
                kid,
                sp.getBoolean("largeCaptions", def.largeCaptions),
                sp.getBoolean("hapticCues", def.hapticCues),
                sp.getBoolean("visualSoundRadar", def.visualSoundRadar),
                sp.getBoolean("audioFirstNarration", def.audioFirstNarration),
                sp.getBoolean("spatialAudioBeacon", def.spatialAudioBeacon),
                sp.getBoolean("muteSpokenTts", def.muteSpokenTts),
                sp.getBoolean("showTypeBar", def.showTypeBar)
        );
    }

    static void save(Context context, Settings s) {
        if (context == null || s == null) {
            return;
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit()
                .putString("profile", s.profile.name())
                .putBoolean("kid", s.kidFriendly)
                .putBoolean("largeCaptions", s.largeCaptions)
                .putBoolean("hapticCues", s.hapticCues)
                .putBoolean("visualSoundRadar", s.visualSoundRadar)
                .putBoolean("audioFirstNarration", s.audioFirstNarration)
                .putBoolean("spatialAudioBeacon", s.spatialAudioBeacon)
                .putBoolean("muteSpokenTts", s.muteSpokenTts)
                .putBoolean("showTypeBar", s.showTypeBar)
                .apply();
    }

    /**
     * Converts a normalized horizontal screen coordinate (-1 left .. 0 center .. +1 right)
     * into an intuitive clock-face navigation phrase for Blind / Low-Vision guidance.
     */
    static String clockFaceDirection(float normalizedX) {
        if (!Float.isFinite(normalizedX)) {
            return "straight ahead at 12 o'clock";
        }
        if (normalizedX < -0.58f) {
            return "to your left around 10 o'clock";
        }
        if (normalizedX < -0.22f) {
            return "slightly left at 11 o'clock";
        }
        if (normalizedX > 0.58f) {
            return "to your right around 2 o'clock";
        }
        if (normalizedX > 0.22f) {
            return "slightly right at 1 o'clock";
        }
        return "straight ahead at 12 o'clock";
    }

    /**
     * Formats an honest, non-cluttered spatial navigation description tailored to Blind / Low-Vision
     * users and Kid-Friendly mode (clock-face bearing, approximate steps/meters, OCR text, lighting).
     */
    static String formatGuidedSceneCue(String primaryLabel, String ocrSnippet, float normalizedX,
                                       float distanceMeters, float compassDegrees,
                                       SpatialTelemetryFusion.LightFieldState lightField,
                                       boolean kidFriendly) {
        String dir = clockFaceDirection(normalizedX);
        String distText = distanceMeters > 0.25f
                ? (kidFriendly
                        ? String.format(Locale.US, "about %.0f big steps away", Math.max(1f, distanceMeters * 1.4f))
                        : String.format(Locale.US, "about %.1f meters away", distanceMeters))
                : "right in front of you";
        StringBuilder sb = new StringBuilder();
        if (primaryLabel != null && !primaryLabel.isEmpty()) {
            if (kidFriendly) {
                sb.append("I see what looks like a ").append(primaryLabel.toLowerCase(Locale.US))
                        .append(" ").append(dir).append(", ").append(distText).append(".");
            } else {
                sb.append(capitalizeFirst(dir)).append(", ").append(distText)
                        .append(": looks like ").append(primaryLabel.toLowerCase(Locale.US)).append(".");
            }
        } else {
            sb.append(kidFriendly
                    ? "Looking " + dir + ". Move slowly and I'll tell you what I spot."
                    : "Scanning " + dir + ". No high-confidence object yet.");
        }
        if (ocrSnippet != null && !ocrSnippet.isEmpty()) {
            sb.append(" Text reads: \"").append(ocrSnippet).append("\".");
        }
        if (Float.isFinite(compassDegrees)) {
            sb.append(String.format(Locale.US, " Facing %s.", SpatialTelemetryFusion.compassCardinal(compassDegrees)));
        }
        if (lightField != null && lightField.calibrated) {
            if (lightField.rearLuma > 0.72f) {
                sb.append(" Bright light ahead.");
            } else if (lightField.rearLuma < 0.20f) {
                sb.append(" Dim lighting ahead.");
            }
            if (lightField.frontLuma > lightField.rearLuma + 0.28f) {
                sb.append(" Brighter light behind you.");
            }
        }
        return sb.toString().trim();
    }

    /**
     * Formats a spoken orientation summary for Blind / Low-Vision long-press gesture
     * (Compass + ENU grid + ambient lighting + acoustic echo distance — zero jargon!).
     */
    static String formatOrientationSummary(SpatialTelemetryFusion.FusedFieldSnapshot snap,
                                           float compassDegrees, boolean kidFriendly) {
        StringBuilder sb = new StringBuilder();
        if (Float.isFinite(compassDegrees)) {
            String card = SpatialTelemetryFusion.compassCardinal(compassDegrees);
            if (kidFriendly) {
                sb.append("You are facing ").append(expandCardinal(card)).append(".");
            } else {
                sb.append(String.format(Locale.US, "Facing %s, %.0f degrees.",
                        expandCardinal(card), SpatialTelemetryFusion.normalizeHeading(compassDegrees)));
            }
        } else {
            sb.append(kidFriendly ? "Turn slowly so I can feel which way we are facing."
                    : "Compass calibrating. Move the phone gently in a figure-eight.");
        }
        if (snap != null) {
            if (snap.gridCoord != null && snap.gridCoord.distanceFromOriginMeters >= 1.5) {
                sb.append(String.format(Locale.US, " About %.0f meters from where we started.",
                        snap.gridCoord.distanceFromOriginMeters));
            }
            if (snap.suggestedDepthMeters > 0.4f && snap.suggestedDepthMeters != 1.20f) {
                sb.append(String.format(Locale.US, " Open space ahead feels about %.1f meters.",
                        snap.suggestedDepthMeters));
            }
            if (snap.lightField != null && snap.lightField.calibrated) {
                sb.append(snap.lightField.rearLuma > 0.65f ? " Bright space ahead."
                        : (snap.lightField.rearLuma < 0.22f ? " Dim space ahead." : " Even indoor light."));
            }
        }
        return sb.toString().trim();
    }

    /**
     * Synthesizes a short stereo spatial audio beacon chime (44.1 kHz, 16-bit stereo PCM)
     * panned left/right by normalizedX (-1..+1) and pitched by proximity (closer = higher pitch).
     * Pure deterministic waveform generator so Blind / Low-Vision users can hear where Zoe or a target is!
     */
    static short[] buildStereoSpatialChime(float normalizedX, float distanceMeters, int sampleRate) {
        int sr = Math.max(8000, sampleRate);
        int frames = (int) (sr * 0.13); // crisp 130ms chime
        float pan = Math.max(-1f, Math.min(1f, Float.isFinite(normalizedX) ? normalizedX : 0f));
        // Constant-power stereo panning
        double angle = (pan + 1.0) * (Math.PI * 0.25);
        double gainL = Math.cos(angle);
        double gainR = Math.sin(angle);
        // Proximity pitch: closer (0.4m) -> 880 Hz, farther (3.0m) -> 420 Hz
        float clampedDist = Math.max(0.4f, Math.min(3.0f, Float.isFinite(distanceMeters) ? distanceMeters : 1.2f));
        double freqHz = 880.0 - ((clampedDist - 0.4) / 2.6) * 460.0;

        short[] stereo = new short[frames * 2];
        for (int i = 0; i < frames; i++) {
            double t = i / (double) sr;
            double env = Math.sin(Math.PI * i / Math.max(1, frames - 1));
            double sample = (0.72 * Math.sin(2.0 * Math.PI * freqHz * t)
                    + 0.28 * Math.sin(2.0 * Math.PI * freqHz * 1.5 * t)) * env * 0.28;
            stereo[i * 2] = (short) Math.round(sample * gainL * Short.MAX_VALUE);
            stereo[i * 2 + 1] = (short) Math.round(sample * gainR * Short.MAX_VALUE);
        }
        return stereo;
    }

    /** Plays a non-blocking stereo spatial chime for Blind / Low-Vision audio-first navigation. */
    static void playStereoSpatialChimeAsync(float normalizedX, float distanceMeters) {
        Thread t = new Thread(() -> {
            AudioTrack track = null;
            try {
                final int sr = 44100;
                short[] pcm = buildStereoSpatialChime(normalizedX, distanceMeters, sr);
                track = new AudioTrack.Builder()
                        .setAudioAttributes(new AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_ASSISTANCE_ACCESSIBILITY)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                                .build())
                        .setAudioFormat(new AudioFormat.Builder()
                                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                .setSampleRate(sr)
                                .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO)
                                .build())
                        .setBufferSizeInBytes(Math.max(pcm.length * 2, 4096))
                        .setTransferMode(AudioTrack.MODE_STATIC)
                        .build();
                track.write(pcm, 0, pcm.length);
                track.play();
                Thread.sleep(160L);
            } catch (Throwable ignored) {
            } finally {
                if (track != null) {
                    try {
                        track.stop();
                    } catch (Throwable ignored) {
                    }
                    track.release();
                }
            }
        }, "zoe-spatial-chime");
        t.setDaemon(true);
        t.start();
    }

    /** Fires a distinct, meaningful tactile vibration pattern for Deaf/HoH and Blind navigation. */
    static void pulseHaptic(Context context, HapticCue cue, boolean enabled) {
        if (!enabled || context == null || cue == null) {
            return;
        }
        try {
            Vibrator v = null;
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                VibratorManager vm = (VibratorManager) context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
                if (vm != null) {
                    v = vm.getDefaultVibrator();
                }
            } else {
                v = (Vibrator) context.getSystemService(Context.VIBRATOR_SERVICE);
            }
            if (v == null || !v.hasVibrator()) {
                return;
            }
            long[] timings;
            int[] amps;
            switch (cue) {
                case LISTENING_READY -> {
                    timings = new long[]{0, 32};
                    amps = new int[]{0, 140};
                }
                case ZOE_SPOTTED -> {
                    timings = new long[]{0, 28, 55, 42};
                    amps = new int[]{0, 150, 0, 210};
                }
                case ZOE_REPLYING -> {
                    timings = new long[]{0, 22, 40, 28};
                    amps = new int[]{0, 110, 0, 150};
                }
                case SOUND_ALERT -> {
                    timings = new long[]{0, 35, 45, 35, 45, 55};
                    amps = new int[]{0, 175, 0, 195, 0, 235};
                }
                case DIRECTION_LOCK -> {
                    timings = new long[]{0, 20};
                    amps = new int[]{0, 180};
                }
                default -> {
                    timings = new long[]{0, 45};
                    amps = new int[]{0, 120};
                }
            }
            v.vibrate(VibrationEffect.createWaveform(timings, amps, -1));
        } catch (Throwable ignored) {
        }
    }

    private static String expandCardinal(String card) {
        return switch (card) {
            case "N" -> "North";
            case "NE" -> "Northeast";
            case "E" -> "East";
            case "SE" -> "Southeast";
            case "S" -> "South";
            case "SW" -> "Southwest";
            case "W" -> "West";
            case "NW" -> "Northwest";
            default -> card;
        };
    }

    private static String capitalizeFirst(String s) {
        if (s == null || s.isEmpty()) {
            return "";
        }
        return Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }
}
