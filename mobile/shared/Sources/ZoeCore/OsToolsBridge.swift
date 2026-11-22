import Foundation

/// Pure, cross-platform OS bridge helpers for Zoe (v0.3.0-beta — Swift / Apple + Linux ZoeCore).
///
/// Mirrors `OsToolsBridge.java` across iOS, iPadOS, and iPhone Duo:
///   - Universal Google Maps + Apple Maps URL builders (zero API key, zero tracking SDKs)
///   - Compass cardinal conversion & shareable live location pin formatting
///   - Offline natural-language OS action parser (`autoExecuted = false` always — user tap required)
public enum OsToolsBridge {
    public enum ActionKind: String, Equatable, Sendable {
        case none
        case navigate
        case mapSearch
        case openLocation
        case openSafety
        case toggleTorch
        case setTimer
        case setAlarm
    }

    public struct ActionSuggestion: Equatable, Sendable {
        public let kind: ActionKind
        public let label: String
        public let query: String
        public let seconds: Int
        public let hour: Int
        public let minute: Int
        public let autoExecuted: Bool

        public init(
            kind: ActionKind,
            label: String,
            query: String = "",
            seconds: Int = 0,
            hour: Int = 0,
            minute: Int = 0
        ) {
            self.kind = kind
            self.label = label
            self.query = query
            self.seconds = seconds
            self.hour = hour
            self.minute = minute
            self.autoExecuted = false
        }

        public var isActionable: Bool { kind != .none }
    }

    public static func isValidCoordinate(lat: Double, lon: Double) -> Bool {
        lat.isFinite && lon.isFinite && lat >= -90.0 && lat <= 90.0 && lon >= -180.0 && lon <= 180.0
    }

    public static func encode(_ value: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        var allowed = CharacterSet.urlQueryAllowed
        allowed.remove(charactersIn: "&+=?")
        return trimmed.addingPercentEncoding(withAllowedCharacters: allowed) ?? trimmed
    }

    public static func googleMapsPinUrl(lat: Double, lon: Double) -> String {
        guard isValidCoordinate(lat: lat, lon: lon) else {
            return "https://www.google.com/maps"
        }
        return String(format: "https://www.google.com/maps/search/?api=1&query=%.6f,%.6f", lat, lon)
    }

    public static func appleMapsPinUrl(lat: Double, lon: Double, label: String = "Zoe Pin") -> String {
        guard isValidCoordinate(lat: lat, lon: lon) else {
            return "https://maps.apple.com/"
        }
        let clean = label.trimmingCharacters(in: .whitespacesAndNewlines)
        let q = clean.isEmpty ? "Zoe Pin" : clean
        return String(format: "https://maps.apple.com/?ll=%.6f,%.6f&q=%@", lat, lon, encode(q))
    }

    public static func appleMapsNavigationUrl(destination: String) -> String {
        let clean = cleanQuery(destination)
        guard !clean.isEmpty else { return "https://maps.apple.com/" }
        return "https://maps.apple.com/?daddr=" + encode(clean)
    }

    public static func appleMapsSearchUrl(query: String, lat: Double? = nil, lon: Double? = nil) -> String {
        let clean = cleanQuery(query)
        guard !clean.isEmpty else { return "https://maps.apple.com/" }
        if let lat, let lon, isValidCoordinate(lat: lat, lon: lon) {
            return String(format: "https://maps.apple.com/?q=%@&sll=%.6f,%.6f", encode(clean), lat, lon)
        }
        return "https://maps.apple.com/?q=" + encode(clean)
    }

    public static func googleMapsAppNavigationUrl(destination: String) -> String {
        let clean = cleanQuery(destination)
        guard !clean.isEmpty else { return "comgooglemaps://" }
        return "comgooglemaps://?daddr=" + encode(clean) + "&directionsmode=driving"
    }

    public static func googleMapsWebDirectionsUrl(destination: String) -> String {
        let clean = cleanQuery(destination)
        guard !clean.isEmpty else { return "https://www.google.com/maps" }
        return "https://www.google.com/maps/dir/?api=1&destination=" + encode(clean)
    }

    public static func googleMapsSearchUrl(query: String) -> String {
        let clean = cleanQuery(query)
        guard !clean.isEmpty else { return "https://www.google.com/maps" }
        return "https://www.google.com/maps/search/?api=1&query=" + encode(clean)
    }

    public static func compassCardinal(_ azimuthDegrees: Double) -> String {
        guard azimuthDegrees.isFinite else { return "N" }
        let norm = (azimuthDegrees.truncatingRemainder(dividingBy: 360.0) + 360.0)
            .truncatingRemainder(dividingBy: 360.0)
        let dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        let idx = Int(floor((norm + 22.5) / 45.0)) % 8
        return dirs[idx]
    }

    public static func formatShareLocationMessage(
        lat: Double,
        lon: Double,
        accuracyMeters: Double,
        address: String? = nil
    ) -> String {
        guard isValidCoordinate(lat: lat, lon: lon) else { return "Location unavailable." }
        var lines = ["My current location (shared from Zoe):"]
        if let addr = address?.trimmingCharacters(in: .whitespacesAndNewlines), !addr.isEmpty {
            lines.append(addr)
        }
        lines.append(String(format: "Coordinates: %.6f, %.6f (accuracy +/- %.0f m)", lat, lon, max(0.0, accuracyMeters)))
        lines.append("Apple Maps: " + appleMapsPinUrl(lat: lat, lon: lon, label: "Shared location"))
        lines.append("Google Maps: " + googleMapsPinUrl(lat: lat, lon: lon))
        return lines.joined(separator: "\n")
    }

    public static func parseActionIntent(_ rawInput: String) -> ActionSuggestion {
        let text = rawInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return ActionSuggestion(kind: .none, label: "") }
        let lower = text.lowercased()

        if let dest = firstCapture(
            pattern: #"(?:navigate|directions|route|drive|walk|take me)\s+(?:to|toward|towards)\s+(.+)"#,
            in: text
        ) {
            let clean = cleanQuery(dest)
            if !clean.isEmpty {
                return ActionSuggestion(kind: .navigate, label: "Navigate to \(clean)", query: clean)
            }
        }

        if let groups = captures(
            pattern: #"(?:set|start)\s+(?:a\s+)?(?:timer\s+(?:for\s+)?)?(\d{1,3})\s*(second|sec|seconds|secs|minute|min|minutes|mins|hour|hr|hours|hrs)(?:\s+timer)?"#,
            in: text
        ), groups.count >= 2, let amount = Int(groups[0]) {
            let unit = groups[1].lowercased()
            let mult = unit.hasPrefix("h") ? 3600 : (unit.hasPrefix("m") ? 60 : 1)
            let total = max(1, min(86400, amount * mult))
            return ActionSuggestion(kind: .setTimer, label: "Start \(amount) \(unit) timer", seconds: total)
        }

        if let groups = captures(
            pattern: #"(?:set\s+(?:an\s+)?alarm|wake\s+me(?:\s+up)?)\s+(?:for|at)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"#,
            in: text
        ), !groups.isEmpty, var h = Int(groups[0]) {
            let m = groups.count >= 2 ? (Int(groups[1]) ?? 0) : 0
            let ampm = groups.count >= 3 ? groups[2].lowercased() : ""
            if ampm == "pm", h >= 1, h < 12 { h += 12 }
            else if ampm == "am", h == 12 { h = 0 }
            if h >= 0, h <= 23, m >= 0, m <= 59 {
                let label = String(format: "Set %02d:%02d alarm", h, m)
                return ActionSuggestion(kind: .setAlarm, label: label, hour: h, minute: m)
            }
        }

        if lower.contains("personal safety") || lower.contains("safety app")
            || lower.contains("emergency info") || lower.contains("medical id") {
            return ActionSuggestion(kind: .openSafety, label: "Open Safety & Medical ID")
        }

        if lower.contains("flashlight") || lower.contains("torch")
            || lower.contains("turn on the light") || lower.contains("turn on light") {
            return ActionSuggestion(kind: .toggleTorch, label: "Toggle Flashlight")
        }

        if lower.contains("where am i") || lower.contains("my location")
            || lower.contains("share location") || lower.contains("share my location")
            || lower == "open maps" || lower.contains("open google maps")
            || lower.contains("open apple maps") {
            return ActionSuggestion(kind: .openLocation, label: "Open Maps & Safety")
        }

        let placeTriggers = ["nearby", "near me", "maps", "hospital", "pharmacy", "coffee", "gas", "food", "shelter", "police", "store"]
        if placeTriggers.contains(where: { lower.contains($0) }),
           let place = firstCapture(pattern: #"(?:find|search maps for|locate|nearest|closest)\s+(.+)"#, in: text) {
            let clean = cleanQuery(place)
            if !clean.isEmpty {
                return ActionSuggestion(kind: .mapSearch, label: "Search \"\(clean)\" in Maps", query: clean)
            }
        }

        return ActionSuggestion(kind: .none, label: "")
    }

    private static func cleanQuery(_ raw: String) -> String {
        raw.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: ".?!"))
            .trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private static func firstCapture(pattern: String, in text: String) -> String? {
        captures(pattern: pattern, in: text)?.first
    }

    private static func captures(pattern: String, in text: String) -> [String]? {
        guard let regex = try? NSRegularExpression(pattern: pattern, options: [.caseInsensitive]) else {
            return nil
        }
        let ns = text as NSString
        guard let match = regex.firstMatch(in: text, options: [], range: NSRange(location: 0, length: ns.length)) else {
            return nil
        }
        var out: [String] = []
        for idx in 1..<match.numberOfRanges {
            let r = match.range(at: idx)
            if r.location != NSNotFound {
                out.append(ns.substring(with: r))
            } else {
                out.append("")
            }
        }
        return out
    }
}
