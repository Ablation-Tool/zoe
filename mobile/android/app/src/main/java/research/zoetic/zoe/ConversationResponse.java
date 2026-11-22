package research.zoetic.zoe;

import java.util.Locale;

final class ConversationResponse {
    private ConversationResponse() {
    }

    static boolean isStop(String heard) {
        String value = normalize(heard);
        return value.contains("stop") || value.contains("goodbye") || value.contains("bye");
    }

    static String forInput(String heard) {
        String value = normalize(heard);
        if (isStop(value)) {
            return "Stopping our conversation. The microphone is off.";
        }
        if (value.contains("battery") || value.contains("device") || value.contains("telemetry")) {
            return "Open Device Field for local battery and capability observations. I will not invent unavailable sensor data.";
        }
        if (value.contains("measure") || value.contains("volume") || value.contains("forecast")
                || value.contains("kloster") || value.contains("equation") || value.contains("a_tau")) {
            return "Accessible volume measures strict p > tau using Nicholas Michael Kloster's March 6, 2026 equation in Accessible Volume and Tiny Zoe. Forecast breadth is not correctness, safety, or permission.";
        }
        if (value.contains("multi") || value.contains("front") || value.contains("back") || value.contains("laptop")) {
            return "Open Multi-view to see the phone's back and front cameras beside an optional laptop feed. Each source reports its own status.";
        }
        if (value.contains("camera") || value.contains("inspect") || value.contains("look") || value.contains("see")) {
            return "Open Guided Vision, start the camera, and choose Inspect once. I will keep each frame and model result separate.";
        }
        if (value.contains("chladni") || value.contains("eliza") || value.contains("studio")
                || value.contains("rose") || value.contains("bronze") || value.contains("music") || value.contains("synth")) {
            return "Open Eliza-GEM Studio for the offline Chladni eigenmode and Languidou Bronze Rose Disc resonance pad, or bridge back to your workstation over USB or HTTPS.";
        }
        if (value.contains("trip") || value.contains("journal") || value.contains("sighting") || value.contains("travel")) {
            return "Open Trip Journal to review your explicitly saved sightings, notes, and offline pixel palettes, or sync them to Zoe's Lab Relay.";
        }
        if (value.contains("convert") || value.contains("unit") || value.contains("safeconvert")) {
            return "Open SafeConvert for private, 100% offline unit conversions with zero network access.";
        }
        if (value.contains("nuclide") || value.contains("places") || value.contains("nicholas")
                || value.contains("nick") || value.equals("cat") || value.contains(" cat")) {
            return "NuClide Research is Zoe + Nick · stable and unstable in balance · PLACES: Play, Learn, Adapt, Create, Explore, Share.";
        }
        if (value.contains("gemini") || value.contains("question") || value.contains("think")) {
            return "For an open-ended question, I can open Gemini with your permission. I will not present its response as my own.";
        }
        if (isGreeting(value) || value.contains("who are you") || value.contains("zoe")) {
            return "Hi — I'm Zoe's offline deterministic stem inside Zoetic Atelier. Ask me about Chladni, Trip Journal, Guided Vision, Accessible Volume, or toggle Cloud chat / open Gemini anytime.";
        }
        String spoken = value.length() > 240 ? value.substring(0, 240) + "…" : value;
        return "I heard you say, " + spoken + ". I can inspect, measure, check the device, open Chladni, or open Gemini. What would you like to try?";
    }

    private static boolean isGreeting(String value) {
        return value.equals("hi")
                || value.startsWith("hi ")
                || value.contains(" hi ")
                || value.equals("hey")
                || value.startsWith("hey ")
                || value.contains(" hey ")
                || value.contains("hello");
    }

    private static String normalize(String heard) {
        return heard == null ? "" : heard.toLowerCase(Locale.ROOT).trim();
    }
}
