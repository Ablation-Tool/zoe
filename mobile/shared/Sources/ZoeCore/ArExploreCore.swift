import Foundation

/// Cross-platform 3D Spatial Curiosity & Autonomous AR Exploration Core for Zoe (v0.7.0-beta).
/// Powers Apple ARKit (ZoeLiveView) with identical spatial math and constitutional boundaries to Android ARCore.
public enum ArExploreCore {
    public struct Vec3: Equatable, Sendable {
        public var x: Float
        public var y: Float
        public var z: Float

        public init(x: Float, y: Float, z: Float) {
            self.x = x
            self.y = y
            self.z = z
        }

        public func distance(to other: Vec3) -> Float {
            let dx = x - other.x
            let dy = y - other.y
            let dz = z - other.z
            return sqrt(dx * dx + dy * dy + dz * dz)
        }
    }

    public struct PlaneTarget: Equatable, Sendable {
        public let id: String
        public let center: Vec3
        public let extentX: Float
        public let extentZ: Float
        public let vertical: Bool

        public init(id: String, center: Vec3, extentX: Float, extentZ: Float, vertical: Bool) {
            self.id = id
            self.center = center
            self.extentX = max(0, extentX)
            self.extentZ = max(0, extentZ)
            self.vertical = vertical
        }
    }

    public struct SpatialDiscovery: Equatable, Sendable {
        public let primaryLabel: String
        public let ocrSnippet: String
        public let position: Vec3
        public let distanceMeters: Float

        public init(primaryLabel: String, ocrSnippet: String, position: Vec3, distanceMeters: Float) {
            self.primaryLabel = primaryLabel
            self.ocrSnippet = ocrSnippet
            self.position = position
            self.distanceMeters = max(0, distanceMeters)
        }
    }

    public static let minExploreDistM: Float = 0.40
    public static let maxExploreDistM: Float = 3.20
    public static let dedupRadiusM: Float = 0.45
    public static let hoverClearanceM: Float = 0.22

    public static func stepGlide(current: Vec3, target: Vec3, dtSec: Float, speed: Float = 2.8) -> Vec3 {
        let dt = max(0.001, min(0.15, dtSec))
        let alpha = 1.0 - exp(-max(0.5, speed) * dt)
        return Vec3(
            x: current.x + (target.x - current.x) * alpha,
            y: current.y + (target.y - current.y) * alpha,
            z: current.z + (target.z - current.z) * alpha
        )
    }

    public static func chooseNextExploreTarget(
        cameraPos: Vec3,
        planes: [PlaneTarget],
        visitedIds: Set<String>
    ) -> PlaneTarget? {
        var bestUnvisited: (PlaneTarget, Float)?
        var bestAny: (PlaneTarget, Float)?
        for p in planes {
            let d = cameraPos.distance(to: p.center)
            guard d >= minExploreDistM && d <= maxExploreDistM else { continue }
            let area = min(2.5, p.extentX * p.extentZ)
            let score = area * 0.9 - abs(d - 1.35) * 0.65 + (p.vertical ? 0.15 : 0.30)
            if bestAny == nil || score > bestAny!.1 {
                bestAny = (p, score)
            }
            if !visitedIds.contains(p.id), bestUnvisited == nil || score > bestUnvisited!.1 {
                bestUnvisited = (p, score)
            }
        }
        return bestUnvisited?.0 ?? bestAny?.0
    }

    public static func isDuplicateDiscovery(
        candidate: SpatialDiscovery,
        existing: [SpatialDiscovery]
    ) -> Bool {
        let normLabel = candidate.primaryLabel.lowercased()
        for prev in existing {
            let near = candidate.position.distance(to: prev.position) < dedupRadiusM
            if near && !normLabel.isEmpty && normLabel == prev.primaryLabel.lowercased() {
                return true
            }
            if near && !candidate.ocrSnippet.isEmpty
                && candidate.ocrSnippet.lowercased() == prev.ocrSnippet.lowercased() {
                return true
            }
        }
        return false
    }

    public static func buildCuriousQuestion(for discovery: SpatialDiscovery) -> String {
        let dist = String(format: "%.1f meters", max(0.3, discovery.distanceMeters))
        if !discovery.ocrSnippet.isEmpty && !discovery.primaryLabel.isEmpty {
            return "I floated over near what looks like a \(discovery.primaryLabel.lowercased()) about \(dist) away and spotted \"\(discovery.ocrSnippet)\" — what's the story behind it?"
        }
        if !discovery.ocrSnippet.isEmpty {
            return "I drifted about \(dist) over and spotted text reading \"\(discovery.ocrSnippet)\" — is that something you're working on?"
        }
        let lbl = discovery.primaryLabel.isEmpty ? "interesting spot" : discovery.primaryLabel.lowercased()
        return "I floated over to explore what looks like a \(lbl) about \(dist) away — tell me about it, what is it used for?"
    }
}
