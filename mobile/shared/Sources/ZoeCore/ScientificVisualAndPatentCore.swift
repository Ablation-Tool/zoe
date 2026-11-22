import Foundation

/// Zoe Scientific-Aesthetic Visual Substrate & Google Patents Catalog Core (v0.9.0-beta — Swift / Apple + Linux ZoeCore).
/// Mirrors `ScientificVisualSubstrate.java` and `GooglePatentsClient.java` for full Android/Apple parity.
public enum ScientificVisualAndPatentCore {
    public static let goldenRatio: Double = 1.61803398875
    public static let goldenAngleDeg: Double = 137.50776405
    public static let goldenAngleRad: Double = goldenAngleDeg * .pi / 180.0

    public enum BaselinePlate: String, CaseIterable, Identifiable, Sendable {
        case atelier = "✦ Atelier"
        case haeckelRadiolaria = "🐚 Haeckel"
        case haeckelAmmonite = "🌀 Ammonite"
        case weismannGermplasm = "🧬 Weismann"
        case lamarckMorphospace = "🌿 Lamarck"
        case patentBlueprint = "📐 Patent"

        public var id: String { rawValue }

        public var lineage: String {
            switch self {
            case .atelier: return "Monterey Coastal Atelier"
            case .haeckelRadiolaria: return "Ernst Haeckel · Kunstformen der Natur (1899)"
            case .haeckelAmmonite: return "Ernst Haeckel · Cephalopoda Spiral (1899)"
            case .weismannGermplasm: return "August Weismann · Das Keimplasma (1892)"
            case .lamarckMorphospace: return "Jean-Baptiste Lamarck · Philosophie Zoologique (1809)"
            case .patentBlueprint: return "Orthographic Patent Schematic (patents.google.com)"
            }
        }

        public var mathSummary: String {
            switch self {
            case .atelier: return "Horizon composition · Chladni rings"
            case .haeckelRadiolaria: return "Dihedral D_n silica lattice · Golden angle 137.508°"
            case .haeckelAmmonite: return "Logarithmic spiral r = a·e^(bθ) · φ = 1.618"
            case .weismannGermplasm: return "Germ-line symmetry · Mitotic spindle field"
            case .lamarckMorphospace: return "Comparative anatomy · Continuous morphospace"
            case .patentBlueprint: return "Involute gear + prism optics · Orthographic callouts"
            }
        }
    }

    public struct PatentMatch: Equatable, Sendable {
        public let publicationNumber: String
        public let title: String
        public let snippet: String
        public let assignee: String
        public let patentUrl: String
        public let dimensionsNote: String

        public init(publicationNumber: String, title: String, snippet: String,
                    assignee: String, patentUrl: String, dimensionsNote: String) {
            self.publicationNumber = publicationNumber
            self.title = title
            self.snippet = snippet
            self.assignee = assignee
            self.patentUrl = patentUrl
            self.dimensionsNote = dimensionsNote
        }
    }

    public static func deterministicSeed(_ concept: String) -> Int {
        let norm = concept.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        guard !norm.isEmpty else { return 1899 }
        var h: UInt32 = 0x811c9dc5
        for scalar in norm.unicodeScalars {
            h ^= UInt32(scalar.value & 0xFFFF)
            h = h &* 16777619
        }
        return Int(h & 0x7FFFFFFF)
    }

    public static func symmetryOrder(forSeed seed: Int) -> Int {
        let orders = [6, 8, 10, 12, 14, 16]
        return orders[abs(seed) % orders.count]
    }

    public static func phyllotaxisPoint(index: Int, scale: Double) -> (x: Double, y: Double) {
        let r = scale * sqrt(Double(max(0, index)))
        let theta = Double(index) * goldenAngleRad
        return (r * cos(theta), r * sin(theta))
    }

    public static func logarithmicSpiralPoint(thetaRad: Double, a: Double, b: Double) -> (x: Double, y: Double) {
        let r = a * exp(b * thetaRad)
        return (r * cos(thetaRad), r * sin(thetaRad))
    }

    public static func augmentPrompt(_ userPrompt: String, plate: BaselinePlate) -> String {
        let subject = userPrompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            ? "symmetrical natural and mechanical study"
            : userPrompt.trimmingCharacters(in: .whitespacesAndNewlines)
        switch plate {
        case .haeckelRadiolaria:
            return "\(subject). Grounded in Ernst Haeckel's Kunstformen der Natur (1899) chromolithograph style: radial dihedral symmetry, golden-angle 137.5° phyllotaxis, fine copperplate stippling, factual biological proportions."
        case .haeckelAmmonite:
            return "\(subject). Grounded in Ernst Haeckel's dark-ground marine plate style: mathematically true logarithmic spiral r = a·e^(bθ), golden-ratio chambers, luminous mineral inks."
        case .weismannGermplasm:
            return "\(subject). Grounded in August Weismann's 1892 Das Keimplasma scientific monograph engraving: cytological symmetry, crisp spindle field geometry, nested structural hierarchy."
        case .lamarckMorphospace:
            return "\(subject). Grounded in Jean-Baptiste Lamarck's 1809 natural history comparative anatomy plate: ordered morphological progression, fine zoological etching on archival parchment."
        case .patentBlueprint:
            return "\(subject). Grounded in classic USPTO / Google Patents orthographic engineering schematic style: crisp isometric & orthographic line drawing, dashed centerlines, numbered reference callouts (10, 12, 14), exact mechanical proportions."
        case .atelier:
            return "\(subject). Clean factual proportions, crisp lighting, balanced geometric harmony."
        }
    }

    public static func extractPatentNumber(from text: String) -> String {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return "" }
        if let regex = try? NSRegularExpression(pattern: "\\b(US|EP|WO|CN|JP|DE|GB)[\\s-]?([0-9]{4,10})[\\s-]?([A-Z][0-9]?)?\\b", options: [.caseInsensitive]),
           let match = regex.firstMatch(in: trimmed, range: NSRange(trimmed.startIndex..., in: trimmed)),
           let r1 = Range(match.range(at: 1), in: trimmed),
           let r2 = Range(match.range(at: 2), in: trimmed) {
            let kind = match.range(at: 3).location != NSNotFound
                ? Range(match.range(at: 3), in: trimmed).map { String(trimmed[$0]).uppercased() } ?? ""
                : ""
            return String(trimmed[r1]).uppercased() + String(trimmed[r2]) + kind
        }
        if let regex2 = try? NSRegularExpression(pattern: "\\bPAT(?:ENT)?\\.?\\s*(?:NO\\.?)?\\s*([0-9]{1,2},[0-9]{3},[0-9]{3}|[0-9]{6,8})\\b", options: [.caseInsensitive]),
           let match = regex2.firstMatch(in: trimmed, range: NSRange(trimmed.startIndex..., in: trimmed)),
           let r1 = Range(match.range(at: 1), in: trimmed) {
            return "US" + String(trimmed[r1]).replacingOccurrences(of: ",", with: "")
        }
        return ""
    }

    public static func describeRelativeScale(meters: Double) -> String {
        guard meters > 0 && meters.isFinite else { return "" }
        let refs: [(String, Double)] = [
            ("standard AA battery", 0.0505),
            ("credit card width", 0.0856),
            ("soda can height", 0.122),
            ("modern smartphone", 0.155),
            ("A4 / US Letter sheet", 0.297),
            ("laptop screen width", 0.34),
            ("standard desk height", 0.74),
            ("acoustic guitar", 1.00),
            ("standard doorway height", 2.03),
        ]
        var nearest = refs[0]
        var bestRatio = Double.greatestFiniteMagnitude
        for ref in refs {
            let ratio = max(meters / ref.1, ref.1 / meters)
            if ratio < bestRatio {
                bestRatio = ratio
                nearest = ref
            }
        }
        if meters < 0.40 {
            return String(format: "Scale reference: ~%.0f mm (roughly comparable to a %@, %.0f mm).",
                          meters * 1000.0, nearest.0, nearest.1 * 1000.0)
        }
        return String(format: "Scale reference: ~%.2f m (roughly %.1fx the size of a %@).",
                      meters, meters / nearest.1, nearest.0)
    }

    public static func parseGooglePatentsJson(_ json: String, maxResults: Int = 3) -> [PatentMatch] {
        guard let data = json.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let results = obj["results"] as? [String: Any],
              let clusters = results["cluster"] as? [[String: Any]] else {
            return []
        }
        var out: [PatentMatch] = []
        for cl in clusters {
            guard let items = cl["result"] as? [[String: Any]] else { continue }
            for item in items {
                if out.count >= max(1, maxResults) { return out }
                guard let pat = item["patent"] as? [String: Any],
                      let pub = pat["publication_number"] as? String, !pub.isEmpty,
                      let rawTitle = pat["title"] as? String, !rawTitle.isEmpty else {
                    continue
                }
                let title = rawTitle.replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                let rawSnippet = (pat["snippet"] as? String ?? "")
                    .replacingOccurrences(of: "<[^>]+>", with: " ", options: .regularExpression)
                    .replacingOccurrences(of: "&hellip;", with: "…")
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                let assignee = (pat["assignee"] as? String ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
                let dims = extractDimensions(title + " " + rawSnippet)
                out.append(PatentMatch(
                    publicationNumber: pub,
                    title: title,
                    snippet: String(rawSnippet.prefix(220)),
                    assignee: assignee,
                    patentUrl: "https://patents.google.com/patent/\(pub)/en",
                    dimensionsNote: dims
                ))
            }
        }
        return out
    }

    private static func extractDimensions(_ text: String) -> String {
        guard let regex = try? NSRegularExpression(pattern: "\\b(\\d+(?:\\.\\d+)?\\s*(?:mm|cm|m|inch(?:es)?|degrees?|°))\\b", options: [.caseInsensitive]) else {
            return ""
        }
        let matches = regex.matches(in: text, range: NSRange(text.startIndex..., in: text))
        var seen: [String] = []
        for m in matches.prefix(3) {
            if let r = Range(m.range(at: 1), in: text) {
                let s = String(text[r]).trimmingCharacters(in: .whitespacesAndNewlines)
                if !seen.contains(s) { seen.append(s) }
            }
        }
        return seen.joined(separator: ", ")
    }
}
