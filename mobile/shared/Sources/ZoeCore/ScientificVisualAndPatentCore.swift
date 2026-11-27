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
        case chladniPlate = "✨ Chladni"
        case fibonacciPhyllotaxis = "🌸 Phyllotaxis"
        case voronoiCrystal = "💎 Voronoi"
        case lissajousOrbit = "🌊 Lissajous"

        public var id: String { rawValue }

        public var lineage: String {
            switch self {
            case .atelier: return "Monterey Coastal Atelier"
            case .haeckelRadiolaria: return "Ernst Haeckel · Kunstformen der Natur (1899)"
            case .haeckelAmmonite: return "Ernst Haeckel · Cephalopoda Spiral (1899)"
            case .weismannGermplasm: return "August Weismann · Das Keimplasma (1892)"
            case .lamarckMorphospace: return "Jean-Baptiste Lamarck · Philosophie Zoologique (1809)"
            case .patentBlueprint: return "Orthographic Patent Schematic (patents.google.com)"
            case .chladniPlate: return "Ernst Chladni · Acoustic Nodal Plate (1787)"
            case .fibonacciPhyllotaxis: return "Botanical Vogel Spiral · Fibonacci (13, 21)"
            case .voronoiCrystal: return "Georgy Voronoi · Cellular Tessellation (1908)"
            case .lissajousOrbit: return "Jules Lissajous · Harmonic Phase Curves (1857)"
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
            case .chladniPlate: return "Standing wave cos(mπx)cos(nπy) − cos(nπx)cos(mπy) = 0"
            case .fibonacciPhyllotaxis: return "Golden divergence 137.508° · Counter-rotating parastichies"
            case .voronoiCrystal: return "Natural crystal cleavage · Nearest-site Dirichlet domains"
            case .lissajousOrbit: return "Parametric resonance x = sin(at + δ), y = sin(bt)"
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
        case .chladniPlate:
            return "\(subject). Grounded in Ernst Chladni's 1787 acoustic standing-wave cymatic plate geometry: symmetric nodal curves, luminous gold and cyan sand lines on obsidian slate."
        case .fibonacciPhyllotaxis:
            return "\(subject). Grounded in botanical Vogel golden-angle phyllotaxis (137.508°): counter-rotating (13, 21) Fibonacci parastichy spirals, archival watercolor and ink stippling."
        case .voronoiCrystal:
            return "\(subject). Grounded in Georgy Voronoi's 1908 cellular tessellation geometry: luminous crystalline facets, nearest-site Dirichlet boundaries, subtle gilt edge lines."
        case .lissajousOrbit:
            return "\(subject). Grounded in Jules Lissajous's 1857 harmonic phase interferometry: crisp parametric resonance ribbons x = sin(at + δ), y = sin(bt) on obsidian archival slate."
        case .atelier:
            return "\(subject). Clean factual proportions, crisp lighting, balanced geometric harmony."
        }
    }

    public static func chladniModes(forSeed seed: Int) -> (m: Int, n: Int) {
        let pairs: [(Int, Int)] = [(2, 5), (3, 5), (3, 7), (4, 7), (2, 7), (5, 8)]
        let pick = pairs[abs(seed) % pairs.count]
        return (pick.0, pick.1)
    }

    public static func lissajousRatios(forSeed seed: Int) -> (a: Int, b: Int) {
        let pairs: [(Int, Int)] = [(3, 4), (5, 7), (3, 5), (4, 5), (5, 6), (2, 3)]
        let pick = pairs[abs(seed) % pairs.count]
        return (pick.0, pick.1)
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

    // MARK: On-Device Visual Contour Reverse-Image Matching (Mirrors PatentReverseImageEngine.java)

    public struct VisualSignature: Sendable {
        public let hog16: [Double]
        public let radial8: [Double]
        public let dHash64: UInt64
        public let aspectRatio: Double
        public let bilateralSymmetry: Double
        public let morphologyKeywords: String
    }

    private static let genericVagueLabels: Set<String> = [
        "product", "gadget", "machine", "material", "plastic", "metal", "steel", "aluminum",
        "hardware", "tool", "device", "electronic device", "electronics", "object", "component",
        "artifact", "auto part", "part", "equipment", "appliance", "pattern", "design", "wood", "glass"
    ]

    public static func isHardToIdentify(_ offlineReport: String) -> Bool {
        let lower = offlineReport.lowercased()
        if lower.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || lower.contains("none above") || !lower.contains("labels:") {
            return true
        }
        guard let regex = try? NSRegularExpression(pattern: "([A-Za-z][A-Za-z0-9\\s\\-/]{1,36})\\s*\\((\\d{1,3})%\\)") else {
            return true
        }
        let matches = regex.matches(in: offlineReport, range: NSRange(offlineReport.startIndex..., in: offlineReport))
        var topConf = 0
        var specific = false
        for m in matches {
            if let r1 = Range(m.range(at: 1), in: offlineReport),
               let r2 = Range(m.range(at: 2), in: offlineReport),
               let conf = Int(offlineReport[r2]) {
                let lbl = String(offlineReport[r1]).trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
                topConf = max(topConf, conf)
                if !genericVagueLabels.contains(lbl) && conf >= 72 {
                    specific = true
                }
            }
        }
        return !specific || topConf < 72
    }

    public static func extractVisualSignature(gray32: [Double]) -> VisualSignature? {
        let n = 32
        guard gray32.count == n * n else { return nil }
        var mag = Array(repeating: 0.0, count: n * n)
        var hog = Array(repeating: 0.0, count: 16)
        var radial = Array(repeating: 0.0, count: 8)
        var maxMag = 1e-5
        let center = Double(n - 1) * 0.5
        let maxR = center * 1.4142

        for y in 1..<(n - 1) {
            for x in 1..<(n - 1) {
                let gx = -gray32[(y - 1) * n + (x - 1)] + gray32[(y - 1) * n + (x + 1)]
                    - 2 * gray32[y * n + (x - 1)] + 2 * gray32[y * n + (x + 1)]
                    - gray32[(y + 1) * n + (x - 1)] + gray32[(y + 1) * n + (x + 1)]
                let gy = -gray32[(y - 1) * n + (x - 1)] - 2 * gray32[(y - 1) * n + x] - gray32[(y - 1) * n + (x + 1)]
                    + gray32[(y + 1) * n + (x - 1)] + 2 * gray32[(y + 1) * n + x] + gray32[(y + 1) * n + (x + 1)]
                let m = hypot(gx, gy)
                mag[y * n + x] = m
                maxMag = max(maxMag, m)
                var ang = atan2(gy, gx)
                if ang < 0 { ang += .pi }
                let hBin = min(15, max(0, Int((ang / .pi) * 16.0)))
                hog[hBin] += m
                let rBin = min(7, max(0, Int((hypot(Double(x) - center, Double(y) - center) / maxR) * 8.0)))
                radial[rBin] += m
            }
        }

        let thresh = max(0.08, maxMag * 0.24)
        var minX = n, maxX = 0, minY = n, maxY = 0
        var symNum = 0.0, symDen = 1e-5
        for y in 1..<(n - 1) {
            for x in 1..<(n - 1) {
                let m = mag[y * n + x]
                if m >= thresh {
                    minX = min(minX, x); maxX = max(maxX, x)
                    minY = min(minY, y); maxY = max(maxY, y)
                }
                let mm = mag[y * n + (n - 1 - x)]
                symNum += min(m, mm)
                symDen += max(m, mm)
            }
        }
        let bboxW = maxX >= minX ? Double(maxX - minX + 1) : Double(n)
        let bboxH = maxY >= minY ? Double(maxY - minY + 1) : Double(n)
        let aspect = bboxW / max(1.0, bboxH)
        let sym = min(1.0, max(0.0, symNum / symDen))
        let totalHog = max(1e-5, hog.reduce(0, +))
        let ortho = (hog[0] + hog[7] + hog[8] + hog[15]) / totalHog

        let normVec: ([Double]) -> [Double] = { v in
            let s = sqrt(v.reduce(0) { $0 + $1 * $1 })
            return s > 1e-6 ? v.map { $0 / s } : v
        }
        hog = normVec(hog)
        radial = normVec(radial)

        var dHash: UInt64 = 0
        var bit = 0
        for row in 0..<8 {
            var cells: [Double] = []
            for col in 0..<9 {
                var acc = 0.0
                let y0 = row * 4
                let x0 = min(n - 3, (col * n) / 9)
                for dy in 0..<4 {
                    for dx in 0..<3 {
                        acc += mag[(y0 + dy) * n + min(n - 1, x0 + dx)]
                    }
                }
                cells.append(acc)
            }
            for col in 0..<8 {
                if cells[col] > cells[col + 1] { dHash |= (1 << UInt64(bit)) }
                bit += 1
            }
        }

        let kw: String
        if aspect > 1.65 || aspect < 0.60 {
            kw = "elongated shaft lever handle bracket linkage tool"
        } else if ortho < 0.29 && sym > 0.56 {
            kw = "circular rotary ring lens gear bearing hub mechanism"
        } else if ortho >= 0.44 {
            kw = "rectangular housing enclosure module panel bracket connector"
        } else {
            kw = "symmetrical mechanical structural device assembly"
        }
        return VisualSignature(hog16: hog, radial8: radial, dHash64: dHash,
                               aspectRatio: aspect, bilateralSymmetry: sym, morphologyKeywords: kw)
    }

    public static func compareVisualSignatures(_ a: VisualSignature, _ b: VisualSignature) -> Double {
        let hogSim = max(0.0, zip(a.hog16, b.hog16).reduce(0.0) { $0 + $1.0 * $1.1 })
        let radSim = max(0.0, zip(a.radial8, b.radial8).reduce(0.0) { $0 + $1.0 * $1.1 })
        let hamming = (a.dHash64 ^ b.dHash64).nonzeroBitCount
        let hashSim = 1.0 - Double(hamming) / 64.0
        let aspectSim = min(a.aspectRatio, b.aspectRatio) / max(0.01, max(a.aspectRatio, b.aspectRatio))
        let symSim = 1.0 - abs(a.bilateralSymmetry - b.bilateralSymmetry)
        return min(1.0, max(0.0, 0.40 * hogSim + 0.25 * radSim + 0.20 * hashSim + 0.15 * (0.55 * aspectSim + 0.45 * symSim)))
    }

    // MARK: CPC Physical-Class Patent Filtering & Self-Improving Guided Vision Memory (Mirrors VisionPriorStore.java)

    public static let physicalCpcFilter = "(cpc:A47 OR cpc:B25 OR cpc:F16 OR cpc:G01 OR cpc:G02 OR cpc:H01)"

    public static func applyPhysicalCpcFilter(query: String, detectedPatentId: String) -> String {
        let q = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !q.isEmpty else { return "" }
        if !detectedPatentId.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            return q
        }
        return "\(q) \(physicalCpcFilter)"
    }

    public static func cleanPhysicalConcept(_ patentTitle: String) -> String {
        var cleaned = patentTitle.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { return "" }
        let prefixes = [
            "^(?i)(systems?\\s+and\\s+methods?\\s+for|method\\s+and\\s+apparatus\\s+for|apparatus\\s+for|device\\s+for|improved|novel)\\s+",
        ]
        for p in prefixes {
            cleaned = cleaned.replacingOccurrences(of: p, with: "", options: .regularExpression)
        }
        cleaned = cleaned.replacingOccurrences(of: "(?i)\\b(thereof|therefor|comprising.*|having.*)$", with: "", options: .regularExpression)
            .replacingOccurrences(of: "\\s+", with: " ", options: .regularExpression)
            .trimmingCharacters(in: CharacterSet(charactersIn: " ,-:"))
        if cleaned.isEmpty { cleaned = patentTitle.trimmingCharacters(in: .whitespacesAndNewlines) }
        cleaned = String(cleaned.prefix(54)).trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.prefix(1).uppercased() + cleaned.dropFirst()
    }

    public struct VisionPrototype: Sendable {
        public let label: String
        public let source: String
        public let signature: VisualSignature
        public let confirmCount: Int

        public init(label: String, source: String, signature: VisualSignature, confirmCount: Int = 1) {
            self.label = label.trimmingCharacters(in: .whitespacesAndNewlines)
            self.source = source
            self.signature = signature
            self.confirmCount = max(1, confirmCount)
        }
    }

    public static func teachOrReinforce(
        store: [VisionPrototype],
        label: String,
        signature: VisualSignature,
        source: String = "user_confirmed"
    ) -> [VisionPrototype] {
        let clean = label.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !clean.isEmpty else { return store }
        var next = store
        if let idx = next.firstIndex(where: { $0.label.caseInsensitiveCompare(clean) == .orderedSame }) {
            let prev = next[idx]
            let count = prev.confirmCount + 1
            let pw = Double(prev.confirmCount) / Double(count)
            let nw = 1.0 / Double(count)
            let normBlend: ([Double], [Double]) -> [Double] = { a, b in
                let raw = zip(a, b).map { $0 * pw + $1 * nw }
                let s = sqrt(raw.reduce(0) { $0 + $1 * $1 })
                return s > 1e-6 ? raw.map { $0 / s } : raw
            }
            let refined = VisualSignature(
                hog16: normBlend(prev.signature.hog16, signature.hog16),
                radial8: normBlend(prev.signature.radial8, signature.radial8),
                dHash64: signature.dHash64,
                aspectRatio: prev.signature.aspectRatio * pw + signature.aspectRatio * nw,
                bilateralSymmetry: prev.signature.bilateralSymmetry * pw + signature.bilateralSymmetry * nw,
                morphologyKeywords: signature.morphologyKeywords
            )
            next[idx] = VisionPrototype(label: prev.label, source: prev.source == "user_confirmed" ? "user_confirmed" : source,
                                        signature: refined, confirmCount: count)
        } else {
            next.append(VisionPrototype(label: clean, source: source, signature: signature, confirmCount: 1))
        }
        return next
    }

    public static func findBestMatch(
        store: [VisionPrototype],
        query: VisualSignature,
        minScore: Double = 0.78
    ) -> (prototype: VisionPrototype, score: Double)? {
        var best: VisionPrototype?
        var bestRaw = -1.0
        var bestRank = -1.0
        for proto in store {
            let sim = compareVisualSignatures(query, proto.signature)
            guard sim >= minScore else { continue }
            let rank = sim + (proto.source == "user_confirmed" ? 0.015 : 0.0)
            if rank > bestRank {
                bestRank = rank
                bestRaw = sim
                best = proto
            }
        }
        return best.map { ($0, bestRaw) }
    }

    public static func findBestMatchWithAtlas(
        userStore: [VisionPrototype],
        atlas: [VisionPrototype],
        query: VisualSignature,
        userMinScore: Double = 0.78,
        atlasMinScore: Double = 0.84
    ) -> (prototype: VisionPrototype, score: Double)? {
        if let userHit = findBestMatch(store: userStore, query: query, minScore: userMinScore) {
            return userHit
        }
        return findBestMatch(store: atlas, query: query, minScore: atlasMinScore)
    }
}
