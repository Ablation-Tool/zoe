import Foundation

public enum ConversationResponse {
    public static func isStop(_ heard: String) -> Bool {
        let value = normalize(heard)
        return value.contains("stop") || value.contains("goodbye") || value.contains("bye")
    }

    public static func forInput(_ heard: String) -> String {
        let value = normalize(heard)
        if isStop(value) { return "Stopping our conversation. The microphone is off." }
        if value.contains("battery") || value.contains("device") || value.contains("telemetry") {
            return "Open Device Field for local battery and capability observations. I will not invent unavailable sensor data."
        }
        if value.contains("measure") || value.contains("volume") || value.contains("forecast") {
            return "Accessible volume counts alternatives strictly above your threshold. It measures forecast breadth, not correctness. Open Volume to try it."
        }
        if value.contains("multi") || value.contains("front") || value.contains("back") || value.contains("laptop") {
            return "Multi-view is available in the Android interface. This Apple app keeps one camera preview at a time."
        }
        if value.contains("camera") || value.contains("inspect") || value.contains("look") || value.contains("see") {
            return "Open Guided Vision, start the camera, and choose Inspect once. I will keep each frame and model result separate."
        }
        if value.contains("gemini") || value.contains("question") || value.contains("think") {
            return "For an open-ended question, I can open Gemini with your permission. I will not present its response as my own."
        }
        let spoken = String(value.prefix(240))
        return "I heard you say, \(spoken). I can inspect, measure, check the device, or open Gemini. What would you like to try?"
    }

    private static func normalize(_ heard: String) -> String {
        heard.lowercased().trimmingCharacters(in: .whitespacesAndNewlines)
    }
}
