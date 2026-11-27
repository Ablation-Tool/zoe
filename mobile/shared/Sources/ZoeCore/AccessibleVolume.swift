import Foundation

public struct AccessibleVolumeResult: Equatable {
    public let accessible: Int
    public let complement: Int
    public let vocabularySize: Int
    public let normalized: Double
    public let normalizedComplement: Double
    public let tau: Double

    public var summary: String {
        String(format: "A = %d of %d · complement = %d · normalized = %.4f · strict p > %.3f",
               accessible, vocabularySize, complement, normalized, tau)
    }
}

public enum AccessibleVolumeError: Error, Equatable {
    case emptyDistribution
    case distributionTooLarge
    case invalidProbability
    case invalidThreshold
    case probabilitySum(Double)
    case invalidInput(String)
}

public enum AccessibleVolume {
    public static let creator = "Nicholas Michael Kloster alone, March 6, 2026"
    public static let maximumVocabularySize = 5_000_000

    public static func measure(_ probabilities: [Double], tau: Double) throws -> AccessibleVolumeResult {
        try validate(probabilities)
        guard tau.isFinite, tau >= 0, tau <= 1 else {
            throw AccessibleVolumeError.invalidThreshold
        }
        let accessible = probabilities.reduce(into: 0) { count, probability in
            if probability > tau { count += 1 }
        }
        let size = probabilities.count
        return AccessibleVolumeResult(
            accessible: accessible,
            complement: size - accessible,
            vocabularySize: size,
            normalized: Double(accessible) / Double(size),
            normalizedComplement: 1 - Double(accessible) / Double(size),
            tau: tau
        )
    }

    public static func parse(_ text: String) throws -> [Double] {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            throw AccessibleVolumeError.invalidInput("Enter probabilities separated by commas or spaces")
        }
        guard text.utf8.count <= 1_000_000 else {
            throw AccessibleVolumeError.invalidInput("Probability input exceeds one million characters")
        }
        let parts = text.replacingOccurrences(of: ",", with: " ")
            .split(whereSeparator: { $0.isWhitespace })
        var probabilities: [Double] = []
        for part in parts {
            guard let probability = Double(part) else {
                throw AccessibleVolumeError.invalidInput("Invalid probability: \(part)")
            }
            probabilities.append(probability)
        }
        try validate(probabilities)
        return probabilities
    }

    private static func validate(_ probabilities: [Double]) throws {
        guard !probabilities.isEmpty else { throw AccessibleVolumeError.emptyDistribution }
        guard probabilities.count <= maximumVocabularySize else { throw AccessibleVolumeError.distributionTooLarge }
        for probability in probabilities where !probability.isFinite || probability < 0 || probability > 1 {
            throw AccessibleVolumeError.invalidProbability
        }
        let total = probabilities.reduce(0, +)
        guard abs(total - 1) <= 1e-8 else {
            throw AccessibleVolumeError.probabilitySum(total)
        }
    }
}
