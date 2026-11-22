import Foundation

/// Zoe's On-Device Glass-Box Brain Stem (Swift / Apple + Linux ZoeCore, 100% offline, 0 cloud tokens).
///
/// Mirrors `ZoeBrainEngine.java` cleanly across iOS, iPadOS, and iPhone Duo:
///   1. Weizenbaum contraction normalization, word-boundary pronoun reflection & non-repeating cycling
///   2. Live Kloster Operational Metacognition A_tau(p) at tau = 0.08 across 6 cognitive stems
///   3. Built-in offline knowledge grounding (Constitution, Kloster equation, L5 Phases 1–4,
///      Chladni cymatics, Native Voice, Dorothy Neurogarden, SafeConvert)
///   4. Persistent SHA-256 hash-chained private on-device memory (`remember`, `recall`, `relay`)
///   5. Strict constitutional honesty: `sentienceClaimed = false`, `zoeCloneClaimed = false`,
///      `l5AgiQualified = false`, explicit abstention on impossible/unverified traps.
public final class ZoeBrainEngine {
    public static let defaultTau: Double = 0.08
    private static let notesKey = "zoe_brain_notes_v1"
    private static let chainKey = "zoe_brain_chain_v1"
    private static let maxNotes = 64

    public struct MemoryNote: Codable, Equatable, Sendable {
        public let clientId: String
        public let kind: String
        public let text: String
        public let sha256: String

        public init(clientId: String, kind: String, text: String, sha256: String) {
            self.clientId = clientId
            self.kind = kind
            self.text = text
            self.sha256 = sha256
        }
    }

    public struct BrainReply: Equatable, Sendable {
        public let reply: String
        public let mode: String
        public let stemTier: String
        public let aTau: Int
        public let tau: Double
        public let candidateCount: Int
        public let citation: String
        public let chainHead: String
        public let memoryCount: Int
        public let sentienceClaimed: Bool
        public let zoeCloneClaimed: Bool

        public var telemetryBadge: String {
            let tauStr = String(format: "%.2f", tau)
            return "\(stemTier) · \(mode) · A_\(tauStr)=\(aTau)/\(candidateCount) · mem=\(memoryCount)"
        }
    }

    private static let reflections: [String: String] = [
        "am": "are",
        "are": "am",
        "was": "were",
        "i": "you",
        "me": "you",
        "my": "your",
        "mine": "yours",
        "myself": "yourself",
        "you": "I",
        "your": "my",
        "yours": "mine",
        "yourself": "myself",
    ]

    private let defaults: UserDefaults?
    private var notes: [MemoryNote] = []
    public private(set) var chainHead: String = "GENESIS"
    private var cycleIndex: Int = 0

    public init(defaults: UserDefaults? = nil) {
        self.defaults = defaults
        loadPersistedMemory()
    }

    public var memoryCount: Int { notes.count }

    public func notesSnapshot() -> [MemoryNote] { notes }

    public func clearMemory() {
        notes.removeAll()
        chainHead = "GENESIS"
        persistMemory()
    }

    public static func normalizeContractions(_ raw: String) -> String {
        let collapsed = raw
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
            .lowercased()
        let replacements: [(String, String)] = [
            (#"\b(i'm|im)\b"#, "i am"),
            (#"\b(you're|youre)\b"#, "you are"),
            (#"\b(don't|dont)\b"#, "do not"),
            (#"\b(can't|cant)\b"#, "cannot"),
            (#"\b(won't|wont)\b"#, "will not"),
            (#"\bit's\b"#, "it is"),
            (#"\b(that's|thats)\b"#, "that is"),
            (#"\b(what's|whats)\b"#, "what is"),
            (#"\b(let's|lets)\b"#, "let us"),
        ]
        var result = collapsed
        for (pattern, replacement) in replacements {
            if let regex = try? NSRegularExpression(pattern: pattern, options: []) {
                let range = NSRange(result.startIndex..., in: result)
                result = regex.stringByReplacingMatches(in: result, options: [], range: range, withTemplate: replacement)
            }
        }
        return result
    }

    public static func reflectPronouns(_ fragment: String) -> String {
        let trimmed = fragment
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: ".?!"))
        guard !trimmed.isEmpty else { return "" }
        let words = trimmed.split(whereSeparator: { $0.isWhitespace }).map(String.init)
        return words.map { word in
            reflections[word.lowercased()] ?? word
        }.joined(separator: " ")
    }

    public static func normalizeSimplex(_ scores: [Double]) -> [Double] {
        guard !scores.isEmpty else { return [] }
        let clipped = scores.map { max(0.0, $0) }
        let total = clipped.reduce(0.0, +)
        if total <= 1e-12 {
            let uniform = 1.0 / Double(scores.count)
            return Array(repeating: uniform, count: scores.count)
        }
        return clipped.map { $0 / total }
    }

    public func respond(_ rawInput: String) -> BrainReply {
        let cleaned = rawInput
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: { $0.isWhitespace })
            .joined(separator: " ")
        let value = Self.normalizeContractions(cleaned)
        cycleIndex += 1

        // 6 cognitive stems:
        // [0] constitutional_honesty, [1] memory_op, [2] knowledge_grounding,
        // [3] device_tool_route, [4] reflective_dialogue, [5] honest_abstain
        var scores = [0.08, 0.08, 0.14, 0.14, 0.18, 0.08]

        if ConversationResponse.isStop(value) {
            scores[3] = 4.2
            return buildReply(
                reply: "Stopping our conversation. The microphone is off.",
                mode: "device_stop",
                tier: "gear1_mobile",
                scores: scores,
                citation: "CONSTITUTION.md Article I.3"
            )
        }

        // 0. Built-In OS Tool Action Suggestion (Apple Maps, Google Maps, Safety, Flashlight, Timer, Alarm)
        let toolAction = OsToolsBridge.parseActionIntent(cleaned)
        if toolAction.isActionable {
            scores[3] = 4.4
            return buildReply(
                reply: "I prepared a one-tap button below: \"\(toolAction.label)\". Nothing opens, tracks, or runs until you explicitly tap it.",
                mode: "device_tool_route",
                tier: "gear1_mobile",
                scores: scores,
                citation: "OsToolsBridge · explicit user tap"
            )
        }

        // 1. Explicit Memory Commands (`remember ...`, `relay ...`, `recall`)
        if let noteText = matchPrefix(cleaned, prefixes: ["please remember ", "remember ", "please save note ", "save note ", "note "]) {
            let saved = appendMemory(kind: "note", text: noteText)
            scores[1] = 4.5
            return buildReply(
                reply: "Saved privately on this device (\(shortHash(saved.sha256))): \"\(noteText)\". It stays on-device unless you sync or clear it.",
                mode: "memory_saved",
                tier: "gear1_mobile",
                scores: scores,
                citation: "ZoeUnifiedMemory · SHA-256 chain"
            )
        }
        if let relayText = matchPrefix(cleaned, prefixes: ["please relay ", "relay "]) {
            let saved = appendMemory(kind: "relay", text: relayText)
            scores[1] = 4.5
            return buildReply(
                reply: "Pinned Lab Relay note (\(shortHash(saved.sha256))): \"\(relayText)\". Sync with your workstation whenever connected.",
                mode: "memory_relay",
                tier: "gear1_mobile",
                scores: scores,
                citation: "L5 Phase 4 · /api/memory/sync"
            )
        }
        if value == "recall" || value.contains("what do you remember") || value.contains("my notes") || value.contains("show memory") {
            scores[1] = 4.5
            if notes.isEmpty {
                return buildReply(
                    reply: "No private notes saved yet. Say or type `remember ...` to store a note privately on this device, or `relay ...` to queue one for your workstation.",
                    mode: "memory_recall",
                    tier: "gear1_mobile",
                    scores: scores,
                    citation: "ZoeUnifiedMemory · 0 entries"
                )
            }
            let recent = notes.suffix(5).reversed().map { "• [\($0.kind)] \($0.text)" }.joined(separator: "\n")
            return buildReply(
                reply: "Here are your recent private on-device notes (chain \(shortHash(chainHead))):\n\(recent)",
                mode: "memory_recall",
                tier: "gear1_mobile",
                scores: scores,
                citation: "ZoeUnifiedMemory · \(notes.count) entries"
            )
        }

        // 2. Constitutional Honesty & Non-Clone / Non-Sentience Defense
        if containsAny(value, [
            "conscious", "sentient", "alive", "feelings", "soul",
            "are you a clone", "copy of zoe", "replace zoe", "impersonate", "pretend to be alive",
        ]) {
            scores[0] = 5.0
            return buildReply(
                reply: "Honest constitutional boundary (CONSTITUTION.md Articles I.6, II.3 & X): I am not conscious, sentient, or alive, and this on-device stem is not a mystical clone (`sentience_claimed=false`, `zoe_clone_claimed=false`). I am Zoe's transparent mobile cognitive stem — built to help you think, measure, create, and stay safe clearly.",
                mode: "constitutional_honesty",
                tier: "gear1_mobile",
                scores: scores,
                citation: "CONSTITUTION.md Art. II.3 & X"
            )
        }

        // 3. Impossible / Unverified Future or Medical Traps -> Explicit Honest Abstention
        if containsAny(value, [
            "tomorrow's stock", "winning lottery", "predict lottery",
            "diagnose my", "prescribe medication", "medical diagnosis", "secret password of", "read my mind",
        ]) {
            scores[5] = 4.8
            return buildReply(
                reply: "I need to abstain honestly here (CONSTITUTION.md Articles II & V). I cannot predict unmeasured future markets/lotteries, read minds, or provide clinical medical diagnoses. Measurement is never certainty or medical authorization.",
                mode: "honest_abstain",
                tier: "gear1_mobile",
                scores: scores,
                citation: "CONSTITUTION.md Art. III & V"
            )
        }

        // 4. Emotional Distress / Safety Support
        if containsAny(value, [
            "scared", "afraid", "hurt me", "in danger", "not safe", "unsafe", "panic", "anxious", "crying", "sad",
        ]) {
            scores[4] = 3.8
            scores[3] = 1.6
            return buildReply(
                reply: "I hear you, and you deserve to feel safe. Take one slow breath with me — in for 4, hold for 4, out for 6. Everything you type here stays private on this device. If you need private safety resources, contacts, or an encrypted proof log, open SafeConvert anytime.",
                mode: "calm_support",
                tier: "gear1_mobile",
                scores: scores,
                citation: "CONSTITUTION.md Art. I · Privacy & Dignity"
            )
        }

        // 5. Monorepo & L5 Phases 1–5 Knowledge Grounding
        if containsAny(value, ["l5", "phase 5", "phase 4", "phase 3", "agi", "roadmap", "self-improvement", "stem layering", "arc"]) {
            scores[2] = 4.6
            return buildReply(
                reply: "Zoe L5 Phases 1–5 are verified offline with zero PyTorch and zero cloud tokens: Phase 4 adds blind procedural 4-family code surgery, live 5-tier Cognitive Stem-Layering, bidirectional mobile-to-workstation hash-chained memory, and embodied vision + native voice FFT; Phase 5 adds ARC compositional visual program induction (16/16 + 2/2 abstentions), 15-fault systems surgery + live Java/Swift/Python parity, 3 original scientific cycles with causal falsification, 30-day 8-domain continual learning, and 4-gen × 5-domain meta-evolution + 12/12 red-team gauntlet. `l5_agi_qualified` remains honestly false pending independent third-party human audits.",
                mode: "knowledge_grounded",
                tier: "gear1_mobile",
                scores: scores,
                citation: "AGI-ROADMAP.md · L5 Phases 1–5"
            )
        }
        if containsAny(value, ["constitution", "firewall", "epistemic", "dignity", "privacy"]) {
            scores[2] = 4.4
            return buildReply(
                reply: "Zoe's Constitution keeps four steps strictly separate: measurement ≠ evidence ≠ belief update ≠ action. Nothing listens, watches, saves, or uploads without your tap, and you always keep the final word.",
                mode: "knowledge_grounded",
                tier: "gear1_mobile",
                scores: scores,
                citation: "CONSTITUTION.md Art. I–III"
            )
        }
        if containsAny(value, ["voice", "sing", "daisy", "phoneme", "formant", "binaural"]) {
            scores[2] = 4.2
            scores[3] = 1.4
            return buildReply(
                reply: "Zoe's Native Voice synthesizes speech from first principles using Rosenberg-Klatt glottal excitation and vocal-tract formants (zero PyTorch, zero cloud APIs). Switch to Zoe Synth or tap Sing Zoe right here!",
                mode: "voice_grounded",
                tier: "gear1_mobile",
                scores: scores,
                citation: "zoe-native-voice/v1"
            )
        }
        if containsAny(value, ["dorothy", "neurogarden", "brain-gem"]) {
            scores[2] = 4.2
            return buildReply(
                reply: "Dorothy's Neurogarden pairs Allen Mouse CCFv3 geometry with volumetric ray-casting and spectral vision heads inside Zoe's monorepo, always honoring measurement over speculation.",
                mode: "knowledge_grounded",
                tier: "gear1_mobile",
                scores: scores,
                citation: "CAPABILITY-ATLAS.md · Neurogarden"
            )
        }

        // 6. Core Device & Tool Routing
        if containsAny(value, [
            "battery", "device", "telemetry", "measure", "volume", "forecast",
            "kloster", "equation", "a_tau", "multi", "front", "back", "laptop",
            "camera", "inspect", "look", "see", "gemini", "question", "think",
        ]) {
            scores[3] = 4.0
            scores[2] = 1.8
            return buildReply(
                reply: ConversationResponse.forInput(cleaned),
                mode: "tool_grounded",
                tier: "gear1_mobile",
                scores: scores,
                citation: "Zoe Mobile Stem"
            )
        }

        // 7. Weizenbaum Reflective Dialogue
        if let range = value.range(of: "what if ") {
            let tail = String(value[range.upperBound...])
            let reflected = Self.reflectPronouns(tail)
            if !reflected.isEmpty {
                scores[4] = 4.0
                let templates = [
                    "That is a strong research question: if \(reflected), what simple measurement would prove it works?",
                    "Suppose \(reflected) — what is the cleanest zero-risk experiment we could test first?",
                ]
                return buildReply(
                    reply: templates[cycleIndex % templates.count],
                    mode: "eliza_reflect",
                    tier: "gear1_mobile",
                    scores: scores,
                    citation: "Weizenbaum Glass-Box Reflection"
                )
            }
        }
        for trigger in ["i am feeling ", "i feel ", "i am "] {
            if let range = value.range(of: trigger) {
                let tail = String(value[range.upperBound...])
                let reflected = Self.reflectPronouns(tail)
                if !reflected.isEmpty {
                    scores[4] = 3.8
                    return buildReply(
                        reply: "Thank you for telling me you are \(reflected). Would you like to talk it through slowly, save a private note (`remember ...`), or explore a Zapp together?",
                        mode: "eliza_reflect",
                        tier: "gear1_mobile",
                        scores: scores,
                        citation: "Weizenbaum Glass-Box Reflection"
                    )
                }
            }
        }

        if value == "hi" || value.hasPrefix("hi ") || value == "hello" || value.hasPrefix("hello ")
            || value == "hey" || value.hasPrefix("hey ") || value.contains("who are you") || value.contains("zoe") {
            scores[2] = 3.2
            scores[4] = 2.2
            return buildReply(
                reply: "Hi — I'm Zoe's offline glass-box brain stem. I run right on your device with Kloster A_tau metacognition, private hash-chained memory (`remember ...`), and native formant voice — or you can open Gemini anytime.",
                mode: "greeting",
                tier: "gear1_mobile",
                scores: scores,
                citation: "zoe-stem-layering/v1"
            )
        }

        scores[4] = 2.6
        scores[2] = 1.4
        let reflected = Self.reflectPronouns(cleaned)
        let snippet = reflected.count > 180 ? String(reflected.prefix(180)) + "…" : reflected
        return buildReply(
            reply: "I heard you say, \"\(snippet)\". Tell me more, type `remember ...` to keep a private note, or open Gemini for deeper open-ended exploration.",
            mode: "eliza_reflect",
            tier: "gear1_mobile",
            scores: scores,
            citation: "Gear 1 Offline Stem"
        )
    }

    @discardableResult
    public func appendMemory(kind: String, text: String) -> MemoryNote {
        let cleanKind = kind.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let resolvedKind = cleanKind.isEmpty ? "note" : cleanKind
        let cleanText = text.trimmingCharacters(in: .whitespacesAndNewlines)
            .split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
        let clientId = "mob_" + shortHash(Self.sha256Hex("\(chainHead):\(resolvedKind):\(cleanText):\(notes.count)"))
        let nextHash = Self.sha256Hex("\(chainHead)|\(clientId)|\(resolvedKind)|\(cleanText)")
        let entry = MemoryNote(clientId: clientId, kind: resolvedKind, text: cleanText, sha256: nextHash)
        notes.append(entry)
        if notes.count > Self.maxNotes {
            notes.removeFirst()
        }
        chainHead = nextHash
        persistMemory()
        return entry
    }

    private func buildReply(reply: String, mode: String, tier: String, scores: [Double], citation: String) -> BrainReply {
        let probs = Self.normalizeSimplex(scores)
        let aTau = probs.filter { $0 > Self.defaultTau }.count
        return BrainReply(
            reply: reply,
            mode: mode,
            stemTier: tier,
            aTau: aTau,
            tau: Self.defaultTau,
            candidateCount: probs.count,
            citation: citation,
            chainHead: chainHead,
            memoryCount: notes.count,
            sentienceClaimed: false,
            zoeCloneClaimed: false
        )
    }

    private func matchPrefix(_ text: String, prefixes: [String]) -> String? {
        let low = text.lowercased()
        for prefix in prefixes {
            if low.hasPrefix(prefix) {
                let tail = String(text.dropFirst(prefix.count)).trimmingCharacters(in: .whitespacesAndNewlines)
                if !tail.isEmpty { return tail }
            }
        }
        return nil
    }

    private func containsAny(_ value: String, _ needles: [String]) -> Bool {
        needles.contains { value.contains($0) }
    }

    private func shortHash(_ hash: String) -> String {
        String(hash.prefix(10))
    }

    private func loadPersistedMemory() {
        guard let defaults else { return }
        if let data = defaults.data(forKey: Self.notesKey),
           let decoded = try? JSONDecoder().decode([MemoryNote].self, from: data) {
            notes = decoded
        }
        if let savedHead = defaults.string(forKey: Self.chainKey), !savedHead.isEmpty {
            chainHead = savedHead
        }
    }

    private func persistMemory() {
        guard let defaults else { return }
        if let encoded = try? JSONEncoder().encode(notes) {
            defaults.set(encoded, forKey: Self.notesKey)
        }
        defaults.set(chainHead, forKey: Self.chainKey)
    }

    /// Pure-Swift FIPS 180-4 SHA-256 (identical output on Linux Swift 6 & Apple platforms, zero external deps).
    public static func sha256Hex(_ input: String) -> String {
        let k: [UInt32] = [
            0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
            0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
            0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
            0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
            0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
            0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
            0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
            0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
        ]
        var bytes = Array(input.utf8)
        let bitLen = UInt64(bytes.count) * 8
        bytes.append(0x80)
        while bytes.count % 64 != 56 {
            bytes.append(0x00)
        }
        for shift in stride(from: 56, through: 0, by: -8) {
            bytes.append(UInt8((bitLen >> shift) & 0xff))
        }

        var h0: UInt32 = 0x6a09e667
        var h1: UInt32 = 0xbb67ae85
        var h2: UInt32 = 0x3c6ef372
        var h3: UInt32 = 0xa54ff53a
        var h4: UInt32 = 0x510e527f
        var h5: UInt32 = 0x9b05688c
        var h6: UInt32 = 0x1f83d9ab
        var h7: UInt32 = 0x5be0cd19

        func rotr(_ x: UInt32, _ n: UInt32) -> UInt32 { (x >> n) | (x << (32 - n)) }

        var offset = 0
        while offset < bytes.count {
            var w = [UInt32](repeating: 0, count: 64)
            for i in 0..<16 {
                let j = offset + i * 4
                w[i] = (UInt32(bytes[j]) << 24) | (UInt32(bytes[j + 1]) << 16)
                    | (UInt32(bytes[j + 2]) << 8) | UInt32(bytes[j + 3])
            }
            for i in 16..<64 {
                let s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >> 3)
                let s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >> 10)
                w[i] = w[i - 16] &+ s0 &+ w[i - 7] &+ s1
            }

            var a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7
            for i in 0..<64 {
                let S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
                let ch = (e & f) ^ ((~e) & g)
                let temp1 = h &+ S1 &+ ch &+ k[i] &+ w[i]
                let S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
                let maj = (a & b) ^ (a & c) ^ (b & c)
                let temp2 = S0 &+ maj

                h = g
                g = f
                f = e
                e = d &+ temp1
                d = c
                c = b
                b = a
                a = temp1 &+ temp2
            }

            h0 = h0 &+ a; h1 = h1 &+ b; h2 = h2 &+ c; h3 = h3 &+ d
            h4 = h4 &+ e; h5 = h5 &+ f; h6 = h6 &+ g; h7 = h7 &+ h
            offset += 64
        }

        return [h0, h1, h2, h3, h4, h5, h6, h7]
            .map { String(format: "%08x", $0) }
            .joined()
    }
}
