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
    public static let defaultSpatialFovRad: Float = 1.08

    public struct ScreenProjection: Equatable, Sendable {
        public let screenX: Float
        public let screenY: Float
        public let perspectiveScale: Float
        public let inFront: Bool
        public let onScreen: Bool
    }

    public struct LightFieldState: Equatable, Sendable {
        public let rearLuma: Float
        public let frontLuma: Float
        public let backlightRatio: Float
        public let rimIntensity: Float
        public let contrastBoost: Float
        public let calibrated: Bool
    }

    public struct EnuGridCoord: Equatable, Sendable {
        public let eastMeters: Double
        public let northMeters: Double
        public let upMeters: Double
        public let gridCellCode: String
    }

    public struct FusedFieldSnapshot: Equatable, Sendable {
        public let klosterATau: Int
        public let klosterM4Root: Double
        public let spatialCoherence: Float
        public let suggestedDepthMeters: Float
    }

    public static func projectWorldToScreen(
        worldPos: Vec3,
        rotMat3x3: [Float],
        viewW: Float,
        viewH: Float,
        verticalFovRad: Float = defaultSpatialFovRad
    ) -> ScreenProjection {
        guard rotMat3x3.count == 9 else {
            return ScreenProjection(screenX: viewW * 0.5, screenY: viewH * 0.5, perspectiveScale: 1, inFront: false, onScreen: false)
        }
        let cx = rotMat3x3[0] * worldPos.x + rotMat3x3[3] * worldPos.y + rotMat3x3[6] * worldPos.z
        let cy = rotMat3x3[1] * worldPos.x + rotMat3x3[4] * worldPos.y + rotMat3x3[7] * worldPos.z
        let cz = rotMat3x3[2] * worldPos.x + rotMat3x3[5] * worldPos.y + rotMat3x3[8] * worldPos.z
        let focal = (viewH * 0.5) / max(0.25, tan(verticalFovRad * 0.5))
        let inFront = cz < -0.15
        let depth = max(0.35, abs(cz))
        let sx = (viewW * 0.5) + (cx / depth) * focal
        let sy = (viewH * 0.5) - (cy / depth) * focal
        let scale = max(0.42, min(1.85, 1.15 / depth))
        let onScreen = inFront && sx >= -40 && sx <= viewW + 40 && sy >= -40 && sy <= viewH + 40
        return ScreenProjection(screenX: sx, screenY: sy, perspectiveScale: scale, inFront: inFront, onScreen: onScreen)
    }

    public static func unprojectTapToWorld(
        tapX: Float,
        tapY: Float,
        viewW: Float,
        viewH: Float,
        verticalFovRad: Float = defaultSpatialFovRad,
        rotMat3x3: [Float],
        depthMeters: Float = 1.24
    ) -> Vec3 {
        let focal = (viewH * 0.5) / max(0.25, tan(verticalFovRad * 0.5))
        let nx = (tapX - viewW * 0.5) / focal
        let ny = (viewH * 0.5 - tapY) / focal
        let nz: Float = -1.0
        let invLen = 1.0 / max(0.0001, sqrt(nx * nx + ny * ny + nz * nz))
        let d = max(0.65, min(2.6, depthMeters))
        let rx = nx * invLen * d
        let ry = ny * invLen * d
        let rz = nz * invLen * d
        guard rotMat3x3.count == 9 else { return Vec3(x: rx, y: ry, z: rz) }
        return Vec3(
            x: rotMat3x3[0] * rx + rotMat3x3[1] * ry + rotMat3x3[2] * rz,
            y: rotMat3x3[3] * rx + rotMat3x3[4] * ry + rotMat3x3[5] * rz,
            z: rotMat3x3[6] * rx + rotMat3x3[7] * ry + rotMat3x3[8] * rz
        )
    }

    public static func computeLightField(rearLuma: Float, frontLuma: Float, calibrated: Bool) -> LightFieldState {
        let rl = max(0, min(1, rearLuma))
        let fl = max(0, min(1, frontLuma))
        let ratio = fl / (rl + 0.08)
        let rim = max(0.18, min(1.0, 0.24 + 0.56 * fl + 0.22 * max(0, fl - rl)))
        let contrast = max(0.78, min(1.42, 0.84 + 0.56 * rl))
        return LightFieldState(
            rearLuma: rl, frontLuma: fl, backlightRatio: ratio,
            rimIntensity: rim, contrastBoost: contrast, calibrated: calibrated
        )
    }

    public static func toLocalEnuGrid(
        originLat: Double, originLon: Double, originAlt: Double,
        curLat: Double, curLon: Double, curAlt: Double
    ) -> EnuGridCoord {
        let r = 6_371_008.8
        let dLat = (curLat - originLat) * .pi / 180.0
        let dLon = (curLon - originLon) * .pi / 180.0
        let meanLat = ((originLat + curLat) * 0.5) * .pi / 180.0
        let north = dLat * r
        let east = dLon * r * cos(meanLat)
        let up = curAlt - originAlt
        let cellE = Int(floor(east / 5.0))
        let cellN = Int(floor(north / 5.0))
        let code = String(format: "G[%+dE,%+dN]", cellE, cellN)
        return EnuGridCoord(eastMeters: east, northMeters: north, upMeters: up, gridCellCode: code)
    }

    public static func fuseSpatialChannels(
        imuStability: Float,
        acousticEnergy: Float,
        opticalEnergy: Float,
        wifiEnergy: Float,
        bleEnergy: Float,
        cellEnergy: Float,
        acousticEchoMeters: Float = -1
    ) -> FusedFieldSnapshot {
        let raw = [
            max(0.05, Double(imuStability)),
            max(0.03, Double(acousticEnergy)),
            max(0.05, Double(opticalEnergy)),
            max(0.02, Double(wifiEnergy)),
            max(0.02, Double(bleEnergy)),
            max(0.02, Double(cellEnergy)),
        ]
        let total = raw.reduce(0, +)
        let p = raw.map { $0 / total }
        let aTau = (try? AccessibleVolume.measure(p, tau: 0.12).accessible) ?? 1
        let m4Root = pow(p.reduce(0.0) { $0 + pow($1, 4) }, 0.25)
        let coherence = max(0, min(1, Float(Double(aTau) / 6.0) * 0.45 + max(0, min(1, imuStability)) * 0.55))
        let depth: Float = (acousticEchoMeters > 0.35 && acousticEchoMeters < 4.5)
            ? max(0.78, min(2.20, acousticEchoMeters * 0.68))
            : 1.20
        return FusedFieldSnapshot(klosterATau: aTau, klosterM4Root: m4Root, spatialCoherence: coherence, suggestedDepthMeters: depth)
    }

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
