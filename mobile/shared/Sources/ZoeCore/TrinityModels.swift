import Foundation

public enum TrinityError: Error, Equatable {
    case invalid(String)
}

public struct TinyWitness: Equatable {
    public let probabilities: [Int]
    public let tau: Int
    public let accessible: Int
    public let complement: Int
    public let vocabularySize: Int
    public let request: String
    public let response: String
}

public struct TrinityMeasurement: Equatable {
    public static let maximumProbabilities = 64
    public static let scale = 32_768

    public let probabilities: [Double]
    public let tau: Double
    public let zoe: AccessibleVolumeResult
    public let tiny: TinyWitness
    public let quantizationChanged: Bool

    public init(probabilities: [Double], tau: Double) throws {
        guard !probabilities.isEmpty, probabilities.count <= Self.maximumProbabilities else {
            throw TrinityError.invalid("Trinity distributions must contain 1 to 64 probabilities")
        }
        self.probabilities = probabilities
        self.tau = tau
        zoe = try AccessibleVolume.measure(probabilities, tau: tau)
        let quantized = try Self.quantize(probabilities, tau: tau)
        tiny = quantized
        quantizationChanged = zoe.accessible != quantized.accessible || quantized.tau != Int(tau * Double(Self.scale))
    }

    private static func decimal(_ value: Double) throws -> Decimal {
        guard let decimal = Decimal(string: String(value), locale: Locale(identifier: "en_US_POSIX")) else {
            throw TrinityError.invalid("Invalid decimal representation")
        }
        return decimal
    }

    private static func quantize(_ probabilities: [Double], tau: Double) throws -> TinyWitness {
        let scaled = try probabilities.map { try decimal($0) * Decimal(scale) }
        var units = scaled.map { NSDecimalNumber(decimal: $0).intValue }
        let order = units.indices.sorted { left, right in
            let leftFraction = scaled[left] - Decimal(units[left])
            let rightFraction = scaled[right] - Decimal(units[right])
            return leftFraction == rightFraction ? left < right : leftFraction > rightFraction
        }
        let remaining = scale - units.reduce(0, +)
        guard remaining >= 0, remaining <= probabilities.count else {
            throw TrinityError.invalid("Invalid Q0.15 allocation")
        }
        for index in 0..<remaining { units[order[index]] += 1 }
        var threshold = try decimal(tau) * Decimal(scale)
        var rounded = Decimal()
        NSDecimalRound(&rounded, &threshold, 0, .bankers)
        let tinyTau = NSDecimalNumber(decimal: rounded).intValue
        let accessible = units.reduce(into: 0) { count, value in if value > tinyTau { count += 1 } }
        let complement = units.count - accessible
        var request: [UInt8] = [0x80, 0x02, 0, 0, UInt8(2 + units.count * 2)]
        request.append(contentsOf: bytes(tinyTau))
        for unit in units { request.append(contentsOf: bytes(unit)) }
        let response = bytes(accessible) + bytes(complement) + bytes(units.count) + bytes(tinyTau) + [0x90, 0x00]
        return TinyWitness(
            probabilities: units,
            tau: tinyTau,
            accessible: accessible,
            complement: complement,
            vocabularySize: units.count,
            request: hex(request),
            response: hex(response)
        )
    }

    private static func bytes(_ value: Int) -> [UInt8] {
        [UInt8((value >> 8) & 0xff), UInt8(value & 0xff)]
    }

    private static func hex(_ bytes: [UInt8]) -> String {
        bytes.map { String(format: "%02X", $0) }.joined()
    }
}

public struct TrinityEvent: Equatable {
    public let ordinal: Int
    public let source: String
    public let tau: Double
    public let zoeAccessible: Int
    public let zoeSize: Int
    public let tinyAccessible: Int
    public let tinySize: Int
}

public struct TrinityState {
    public let revision: Int
    public let active: TrinityMeasurement
    public let memoryEnabled: Bool
    public let memoryRecords: Int
    public let events: [TrinityEvent]

    public init(data: Data) throws {
        guard data.count <= 1_048_576 else { throw TrinityError.invalid("Trinity response exceeds 1 MiB") }
        let payload = try JSONDecoder().decode(Payload.self, from: data)
        guard payload.protocolVersion == 1, payload.name == "Zoe Trinity",
              payload.creator == AccessibleVolume.creator else {
            throw TrinityError.invalid("Unsupported protocol or missing original-equation credit")
        }
        guard payload.revision >= 0 else { throw TrinityError.invalid("Invalid revision") }
        active = try TrinityMeasurement(probabilities: payload.active.probabilities, tau: payload.active.tau)
        try Self.compare(zoe: payload.active.zoe, result: active.zoe)
        let tiny = payload.active.tiny
        guard tiny.probabilities == active.tiny.probabilities,
              tiny.tau == active.tiny.tau,
              tiny.accessible == active.tiny.accessible,
              tiny.complement == active.tiny.complement,
              tiny.vocabularySize == active.tiny.vocabularySize,
              tiny.request == active.tiny.request,
              tiny.response == active.tiny.response,
              payload.active.quantizationChanged == active.quantizationChanged else {
            throw TrinityError.invalid("Tiny witness does not match the distribution")
        }
        guard payload.memory.tamperEvidenceOnly,
              payload.memory.records >= 0,
              !payload.memory.enabled || payload.memory.records >= payload.revision else {
            throw TrinityError.invalid("Invalid journal state")
        }
        guard payload.events.count <= 24 else { throw TrinityError.invalid("Too many retained events") }
        var previous = 0
        var parsedEvents: [TrinityEvent] = []
        for event in payload.events {
            guard event.ordinal > previous, event.ordinal <= payload.revision,
                  ["android", "apple", "laptop"].contains(event.source),
                  event.tau.isFinite, event.tau >= 0, event.tau <= 1 else {
                throw TrinityError.invalid("Invalid event sequence, source, or threshold")
            }
            try Self.validate(event: event.zoe)
            try Self.validate(event: event.tiny)
            parsedEvents.append(TrinityEvent(
                ordinal: event.ordinal,
                source: event.source,
                tau: event.tau,
                zoeAccessible: event.zoe.accessible,
                zoeSize: event.zoe.vocabularySize,
                tinyAccessible: event.tiny.accessible,
                tinySize: event.tiny.vocabularySize
            ))
            previous = event.ordinal
        }
        revision = payload.revision
        memoryEnabled = payload.memory.enabled
        memoryRecords = payload.memory.records
        events = parsedEvents
    }

    private static func compare(zoe: Counts, result: AccessibleVolumeResult) throws {
        guard zoe.accessible == result.accessible,
              zoe.complement == result.complement,
              zoe.vocabularySize == result.vocabularySize else {
            throw TrinityError.invalid("Mobile measurement does not match the distribution")
        }
    }

    private static func validate(event: Counts) throws {
        guard event.vocabularySize >= 1, event.vocabularySize <= TrinityMeasurement.maximumProbabilities,
              event.accessible >= 0, event.accessible <= event.vocabularySize else {
            throw TrinityError.invalid("Invalid event counts")
        }
    }

    private struct Payload: Decodable {
        let protocolVersion: Int
        let name: String
        let revision: Int
        let creator: String
        let active: Active
        let memory: Memory
        let events: [Event]

        enum CodingKeys: String, CodingKey {
            case protocolVersion = "protocol", name, revision, creator, active, memory, events
        }
    }

    private struct Active: Decodable {
        let probabilities: [Double]
        let tau: Double
        let zoe: Counts
        let tiny: Tiny
        let quantizationChanged: Bool
    }

    private struct Tiny: Decodable {
        let probabilities: [Int]
        let tau: Int
        let accessible: Int
        let complement: Int
        let vocabularySize: Int
        let request: String
        let response: String
    }

    private struct Memory: Decodable {
        let enabled: Bool
        let records: Int
        let tamperEvidenceOnly: Bool
    }

    private struct Event: Decodable {
        let ordinal: Int
        let source: String
        let tau: Double
        let zoe: Counts
        let tiny: Counts
    }

    private struct Counts: Decodable {
        let accessible: Int
        let complement: Int
        let vocabularySize: Int
    }
}
