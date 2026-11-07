import Foundation

public enum VoiceCommand: String, Equatable {
    case inspect
    case repeatResult
    case stop
    case measure
    case vision
    case device
    case gemini
    case unknown

    public static func parse(_ text: String?) -> VoiceCommand {
        let command = text?.lowercased().trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if command.isEmpty { return .unknown }
        if containsAny(command, ["stop", "quiet", "silence"]) { return .stop }
        if containsAny(command, ["repeat", "read aloud", "speak"]) { return .repeatResult }
        if containsAny(command, ["measure", "volume", "forecast"]) { return .measure }
        if containsAny(command, ["device", "battery", "telemetry"]) { return .device }
        if containsAny(command, ["vision", "camera"]) { return .vision }
        if containsAny(command, ["inspect", "look", "describe", "see"]) { return .inspect }
        if containsAny(command, ["gemini", "assistant"]) { return .gemini }
        return .unknown
    }

    private static func containsAny(_ text: String, _ candidates: [String]) -> Bool {
        candidates.contains(where: { text.contains($0) })
    }
}
