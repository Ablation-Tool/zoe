import Foundation

/// Privacy-Firewalled Mobile -> Workstation L5 Digestion Core for Apple (mirrors MobileDigestionBundle.java & l5_mobile_digestion.py).
///
/// Strictly enforces CONSTITUTION.md Article I:
///   - SafeConvert, Privacy Vault E2EE keys/envelopes, raw photos, and private chat bodies are hard-excluded.
///   - Explicit opt-in only; returns refined structural visual prototypes safely without downgrading user-confirmed entries.
public enum MobileDigestionCore {
    public static let contract = "zoe-mobile-digestion/v1"

    public static let forbiddenTokens: [String] = [
        "safeconvert", "safe_convert", "safe_vault", "safe_evidence", "safe_beacon",
        "safety_contacts", "privacy_vault", "e2ee_private_key", "ecdh_private",
        "private_key_pkcs8", "vault_envelope", "raw_photo_base64", "data:image/",
        "BEGIN PRIVATE KEY",
    ]

    public enum FirewallError: Error, Equatable, Sendable {
        case emptyBundle
        case forbiddenDomainDetected(String)
    }

    public struct DigestedNote: Sendable, Equatable {
        public let clientId: String
        public let kind: String
        public let text: String

        public init(clientId: String, kind: String, text: String) {
            self.clientId = clientId
            self.kind = kind
            self.text = text
        }
    }

    public struct DigestedSighting: Sendable, Equatable {
        public let id: String
        public let timestampIso: String
        public let note: String
        public let labels: String
        public let ocrText: String
        public let paletteSummary: String

        public init(id: String, timestampIso: String, note: String, labels: String, ocrText: String, paletteSummary: String) {
            self.id = id
            self.timestampIso = timestampIso
            self.note = note
            self.labels = labels
            self.ocrText = ocrText
            self.paletteSummary = paletteSummary
        }
    }

    public struct ChatTelemetrySummary: Sendable, Equatable {
        public let threadCount: Int
        public let messageCount: Int
        public let avgLatencyMs: Double
        public let avgATau: Double
        public let providerCounts: [String: Int]
        public let topicKeywords: [String]

        public init(
            threadCount: Int,
            messageCount: Int,
            avgLatencyMs: Double,
            avgATau: Double,
            providerCounts: [String: Int],
            topicKeywords: [String]
        ) {
            self.threadCount = max(0, threadCount)
            self.messageCount = max(0, messageCount)
            self.avgLatencyMs = max(0.0, avgLatencyMs)
            self.avgATau = max(0.0, avgATau)
            self.providerCounts = providerCounts
            self.topicKeywords = topicKeywords
        }
    }

    public static func buildBundleJson(
        device: String,
        appVersion: String,
        prototypes: [ScientificVisualAndPatentCore.VisionPrototype],
        notes: [DigestedNote],
        sightings: [DigestedSighting],
        chatTelemetry: ChatTelemetrySummary
    ) throws -> String {
        let firewall: [String: Any] = [
            "safeconvert_excluded": true,
            "privacy_vault_excluded": true,
            "raw_photos_excluded": true,
            "chat_bodies_excluded": true,
        ]
        let notesArr: [[String: Any]] = notes.compactMap { n in
            let t = n.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !t.isEmpty else { return nil }
            return ["client_id": n.clientId, "kind": n.kind, "text": t]
        }
        let tripsArr: [[String: Any]] = sightings.compactMap { s in
            guard !(s.note.isEmpty && s.labels.isEmpty && s.ocrText.isEmpty && s.paletteSummary.isEmpty) else {
                return nil
            }
            return [
                "id": s.id,
                "timestampIso": s.timestampIso,
                "note": s.note,
                "labels": s.labels,
                "ocrText": s.ocrText,
                "paletteSummary": s.paletteSummary,
            ]
        }
        let protoArr: [[String: Any]] = prototypes.map { p in
            [
                "label": p.label,
                "source": p.source,
                "patentRef": "",
                "dims": "",
                "count": p.confirmCount,
                "updated": 0,
                "dHash": String(p.signature.dHash64, radix: 16),
                "aspect": (p.signature.aspectRatio * 10000).rounded() / 10000,
                "sym": (p.signature.bilateralSymmetry * 10000).rounded() / 10000,
                "ortho": 0.3,
                "density": 0.2,
                "kw": p.signature.morphologyKeywords,
                "summary": "",
                "hog": p.signature.hog16.map { ($0 * 10000).rounded() / 10000 },
                "radial": p.signature.radial8.map { ($0 * 10000).rounded() / 10000 },
            ]
        }
        let chatTel: [String: Any] = [
            "thread_count": chatTelemetry.threadCount,
            "message_count": chatTelemetry.messageCount,
            "avg_latency_ms": (chatTelemetry.avgLatencyMs * 100).rounded() / 100,
            "avg_a_tau": (chatTelemetry.avgATau * 100).rounded() / 100,
            "provider_counts": chatTelemetry.providerCounts,
            "topic_keywords": Array(chatTelemetry.topicKeywords.prefix(16)),
        ]
        let root: [String: Any] = [
            "contract": contract,
            "device": device.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "Apple" : device,
            "app_version": appVersion.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? "0.9.3" : appVersion,
            "privacy_firewall": firewall,
            "brain_notes": notesArr,
            "trip_sightings": tripsArr,
            "vision_prototypes": protoArr,
            "chat_telemetry": chatTel,
        ]
        let data = try JSONSerialization.data(withJSONObject: root, options: [.sortedKeys])
        let json = String(decoding: data, as: UTF8.self)
        try assertOutgoingFirewall(json)
        return json
    }

    public static func assertOutgoingFirewall(_ bundleJson: String) throws {
        let trimmed = bundleJson.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            throw FirewallError.emptyBundle
        }
        var sanitized = trimmed.lowercased()
        for allowed in [
            "\"safeconvert_excluded\":true",
            "\"privacy_vault_excluded\":true",
            "\"raw_photos_excluded\":true",
            "\"chat_bodies_excluded\":true",
        ] {
            sanitized = sanitized.replacingOccurrences(of: allowed, with: "")
        }
        for tok in forbiddenTokens {
            if sanitized.contains(tok.lowercased()) {
                throw FirewallError.forbiddenDomainDetected(tok)
            }
        }
    }

    public static func mergeRefinedPrototypes(
        local: [ScientificVisualAndPatentCore.VisionPrototype],
        refined: [ScientificVisualAndPatentCore.VisionPrototype]
    ) -> [ScientificVisualAndPatentCore.VisionPrototype] {
        var merged = local
        for incoming in refined {
            if let idx = merged.firstIndex(where: { $0.label.caseInsensitiveCompare(incoming.label) == .orderedSame }) {
                let cur = merged[idx]
                let bestSource = (cur.source == "user_confirmed" || incoming.source == "user_confirmed")
                    ? "user_confirmed" : incoming.source
                let adoptIncoming = incoming.confirmCount > cur.confirmCount || cur.source != "user_confirmed"
                let bestSig = adoptIncoming ? incoming.signature : cur.signature
                merged[idx] = ScientificVisualAndPatentCore.VisionPrototype(
                    label: cur.label,
                    source: bestSource,
                    signature: bestSig,
                    confirmCount: max(cur.confirmCount, incoming.confirmCount)
                )
            } else {
                merged.append(incoming)
            }
        }
        return merged
    }
}
