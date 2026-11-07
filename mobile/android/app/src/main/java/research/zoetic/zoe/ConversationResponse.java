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
        if (value.contains("measure") || value.contains("volume") || value.contains("forecast")) {
            return "Accessible volume counts alternatives strictly above your threshold. It measures forecast breadth, not correctness. Open Volume to try it.";
        }
        if (value.contains("multi") || value.contains("front") || value.contains("back") || value.contains("laptop")) {
            return "Open Multi-view to see the phone's back and front cameras beside an optional laptop feed. Each source reports its own status.";
        }
        if (value.contains("camera") || value.contains("inspect") || value.contains("look") || value.contains("see")) {
            return "Open Guided Vision, start the camera, and choose Inspect once. I will keep each frame and model result separate.";
        }
        if (value.contains("gemini") || value.contains("question") || value.contains("think")) {
            return "For an open-ended question, I can open Gemini with your permission. I will not present its response as my own.";
        }
        String spoken = value.length() > 240 ? value.substring(0, 240) + "…" : value;
        return "I heard you say, " + spoken + ". I can inspect, measure, check the device, or open Gemini. What would you like to try?";
    }

    private static String normalize(String heard) {
        return heard == null ? "" : heard.toLowerCase(Locale.ROOT).trim();
    }
}
