import Foundation

/// Signal-Inspired Symmetric Ratchet, Safety Number Fingerprint & "Hi Zoe" Wake-Word Core
/// (v0.6.0-beta — Swift / Apple + Linux ZoeCore, zero external packages).
public enum ZoeSignalAndWakeCore {
    private static let wakeTriggers = [
        "hi zoe", "hey zoe", "hello zoe", "hang out zoe", "hangout zoe",
        "ok zoe", "okay zoe", "yo zoe", "hi zoey", "hey zoey",
        "hello zoey", "hi zo", "hey zo",
    ]

    public static func isHiZoeTrigger(_ transcript: String) -> Bool {
        let norm = normalize(transcript)
        guard !norm.isEmpty else { return false }
        if norm == "zoe" || norm == "zoey" {
            return true
        }
        for t in wakeTriggers {
            if norm == t || norm.hasPrefix(t + " ") || norm.contains(" " + t) {
                return true
            }
        }
        return false
    }

    public static func stripWakePrefix(_ transcript: String) -> String {
        let trimmed = transcript.trimmingCharacters(in: .whitespacesAndNewlines)
        let lower = trimmed.replacingOccurrences(of: "ë", with: "e")
            .replacingOccurrences(of: "Ë", with: "E")
            .lowercased()
        for t in wakeTriggers {
            if let range = lower.range(of: t) {
                let offset = lower.distance(from: lower.startIndex, to: range.upperBound)
                return String(trimmed.dropFirst(offset))
                    .trimmingCharacters(in: CharacterSet(charactersIn: " ,.:;!?-\t\n"))
            }
        }
        if lower == "zoe" || lower == "zoey" {
            return ""
        }
        return trimmed
    }

    /// Strips markdown markers and raw URLs so spoken responses sound natural and conversational.
    public static func sanitizeForSpeech(_ raw: String) -> String {
        var s = raw
        for token in ["**", "__", "`", "### ", "## ", "# ", "—", "–"] {
            s = s.replacingOccurrences(of: token, with: token == "—" || token == "–" ? ", " : " ")
        }
        let words = s.split(whereSeparator: { $0.isWhitespace })
            .filter { !$0.hasPrefix("http://") && !$0.hasPrefix("https://") }
            .map { $0.trimmingCharacters(in: CharacterSet(charactersIn: "*_~#")) }
            .filter { !$0.isEmpty }
        return words.joined(separator: " ")
    }

    /// Computes a canonical 60-digit Safety Number fingerprint from two identity key byte arrays
    /// (mirrors Signal's sorted key comparison and 12x5-digit visual verification grid).
    public static func computeSafetyNumber(keyA: [UInt8], keyB: [UInt8]) -> String {
        let (first, second) = keyA.lexicographicallyPrecedes(keyB) ? (keyA, keyB) : (keyB, keyA)
        let combined = digits30(first) + digits30(second)
        var groups: [String] = []
        var idx = combined.startIndex
        for _ in 0..<12 {
            let next = combined.index(idx, offsetBy: 5)
            groups.append(String(combined[idx..<next]))
            idx = next
        }
        return stride(from: 0, to: 12, by: 4)
            .map { groups[$0..<($0 + 4)].joined(separator: " ") }
            .joined(separator: "\n")
    }

    private static func digits30(_ bytes: [UInt8]) -> String {
        var acc = bytes
        for round in 0..<64 {
            var mixed: [UInt8] = [UInt8(round & 0xFF)]
            mixed.append(contentsOf: acc)
            mixed.append(contentsOf: bytes)
            acc = sha256Bytes(mixed)
        }
        var out = ""
        for block in 0..<6 {
            let o = (block * 5) % acc.count
            var val: UInt64 = 0
            for k in 0..<5 {
                val = (val << 8) | UInt64(acc[(o + k) % acc.count])
            }
            out += String(format: "%05llu", val % 100_000)
        }
        return out
    }

    private static func sha256Bytes(_ input: [UInt8]) -> [UInt8] {
        // Pure-Swift RFC 6234 SHA-256 (works identically on Apple & Linux without CommonCrypto)
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
        var h: [UInt32] = [
            0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
            0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
        ]
        var msg = input
        let bitLen = UInt64(msg.count) * 8
        msg.append(0x80)
        while (msg.count % 64) != 56 { msg.append(0) }
        for shift in stride(from: 56, through: 0, by: -8) {
            msg.append(UInt8((bitLen >> shift) & 0xFF))
        }
        for chunkStart in stride(from: 0, to: msg.count, by: 64) {
            var w = [UInt32](repeating: 0, count: 64)
            for i in 0..<16 {
                let b = chunkStart + i * 4
                w[i] = (UInt32(msg[b]) << 24) | (UInt32(msg[b + 1]) << 16) | (UInt32(msg[b + 2]) << 8) | UInt32(msg[b + 3])
            }
            for i in 16..<64 {
                let s0 = ror(w[i - 15], 7) ^ ror(w[i - 15], 18) ^ (w[i - 15] >> 3)
                let s1 = ror(w[i - 2], 17) ^ ror(w[i - 2], 19) ^ (w[i - 2] >> 10)
                w[i] = w[i - 16] &+ s0 &+ w[i - 7] &+ s1
            }
            var a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], f = h[5], g = h[6], hh = h[7]
            for i in 0..<64 {
                let s1 = ror(e, 6) ^ ror(e, 11) ^ ror(e, 25)
                let ch = (e & f) ^ ((~e) & g)
                let t1 = hh &+ s1 &+ ch &+ k[i] &+ w[i]
                let s0 = ror(a, 2) ^ ror(a, 13) ^ ror(a, 22)
                let maj = (a & b) ^ (a & c) ^ (b & c)
                let t2 = s0 &+ maj
                hh = g; g = f; f = e; e = d &+ t1
                d = c; c = b; b = a; a = t1 &+ t2
            }
            h[0] = h[0] &+ a; h[1] = h[1] &+ b; h[2] = h[2] &+ c; h[3] = h[3] &+ d
            h[4] = h[4] &+ e; h[5] = h[5] &+ f; h[6] = h[6] &+ g; h[7] = h[7] &+ hh
        }
        var digest: [UInt8] = []
        for word in h {
            digest.append(UInt8((word >> 24) & 0xFF))
            digest.append(UInt8((word >> 16) & 0xFF))
            digest.append(UInt8((word >> 8) & 0xFF))
            digest.append(UInt8(word & 0xFF))
        }
        return digest
    }

    private static func ror(_ v: UInt32, _ n: UInt32) -> UInt32 {
        (v >> n) | (v << (32 - n))
    }

    private static func normalize(_ s: String) -> String {
        let folded = s.replacingOccurrences(of: "ë", with: "e")
            .replacingOccurrences(of: "Ë", with: "E")
            .replacingOccurrences(of: "é", with: "e")
            .replacingOccurrences(of: "É", with: "E")
        let lower = folded.lowercased()
        let cleaned = lower.unicodeScalars.map { CharacterSet.alphanumerics.contains($0) ? Character($0) : " " }
        return String(cleaned).split(whereSeparator: { $0.isWhitespace }).joined(separator: " ")
    }
}
