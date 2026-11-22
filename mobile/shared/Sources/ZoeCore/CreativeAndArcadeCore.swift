import Foundation

/// Zoe Creative Studio & Arcade Core (v0.6.0-beta — Swift / Apple + Linux ZoeCore).
/// Mirrors `ImageLabEngine.java` and `ArcadeEngine.java` for full Android/Apple parity.
public enum CreativeAndArcadeCore {
    public enum FilterPreset: String, CaseIterable, Identifiable, Sendable {
        case original = "Original"
        case warmAtelier = "Atelier Warm"
        case cobaltNight = "Cobalt Night"
        case noirBW = "Noir B&W"
        case emeraldFilm = "Emerald Film"
        case vividPop = "Vivid Pop"
        case sepia = "Sepia"
        public var id: String { rawValue }
    }

    public enum CropMode: String, CaseIterable, Identifiable, Sendable {
        case original = "Original"
        case square = "1:1 Square"
        case wide16x9 = "16:9 Wide"
        public var id: String { rawValue }
    }

    public struct ImageEditSpec: Equatable, Sendable {
        public var filter: FilterPreset = .original
        public var brightness: Int = 0
        public var contrast: Double = 1.0
        public var rotationDeg: Int = 0
        public var crop: CropMode = .original
        public var privacyBlur: Bool = false
        public var caption: String = ""

        public init() {}
    }

    public static func parseImageEditCommand(_ command: String, current: ImageEditSpec = ImageEditSpec()) -> ImageEditSpec {
        let raw = command.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !raw.isEmpty else { return current }
        let lower = raw.lowercased()
        if lower.contains("reset") || lower.contains("original") || lower.contains("clear edits") {
            return ImageEditSpec()
        }
        var next = current
        if lower.contains("black and white") || lower.contains("b&w") || lower.contains("noir") || lower.contains("grayscale") {
            next.filter = .noirBW
        } else if lower.contains("sepia") || lower.contains("vintage") {
            next.filter = .sepia
        } else if lower.contains("warm") || lower.contains("sunset") {
            next.filter = .warmAtelier
        } else if lower.contains("cool") || lower.contains("cobalt") || lower.contains("night") {
            next.filter = .cobaltNight
        } else if lower.contains("emerald") || lower.contains("film") {
            next.filter = .emeraldFilm
        } else if lower.contains("vivid") || lower.contains("pop") {
            next.filter = .vividPop
        }

        if lower.contains("brighter") || lower.contains("lighten") {
            next.brightness = min(60, next.brightness + 24)
        } else if lower.contains("darker") || lower.contains("dim") {
            next.brightness = max(-60, next.brightness - 24)
        }
        if lower.contains("more contrast") || lower.contains("punchy") {
            next.contrast = min(1.6, next.contrast + 0.25)
        }
        if lower.contains("rotate left") || lower.contains("270") {
            next.rotationDeg = (next.rotationDeg + 270) % 360
        } else if lower.contains("180") {
            next.rotationDeg = (next.rotationDeg + 180) % 360
        } else if lower.contains("rotate") {
            next.rotationDeg = (next.rotationDeg + 90) % 360
        }
        if lower.contains("square") || lower.contains("1:1") {
            next.crop = .square
        } else if lower.contains("16:9") || lower.contains("wide") {
            next.crop = .wide16x9
        }
        if lower.contains("unblur") {
            next.privacyBlur = false
        } else if lower.contains("blur") || lower.contains("privacy") || lower.contains("pixelate") {
            next.privacyBlur = true
        }
        for key in ["caption ", "add caption ", "add text ", "title "] {
            if let range = lower.range(of: key) {
                let offset = lower.distance(from: lower.startIndex, to: range.upperBound)
                var val = String(raw.dropFirst(offset)).trimmingCharacters(in: .whitespacesAndNewlines)
                if let comma = val.firstIndex(of: ",") { val = String(val[..<comma]) }
                val = val.trimmingCharacters(in: CharacterSet(charactersIn: "\"' "))
                if !val.isEmpty { next.caption = String(val.prefix(64)) }
                break
            }
        }
        return next
    }

    // MARK: Tic-Tac-Toe Minimax (0=empty, 1=Player X, 2=Zoe O)

    private static let winLines = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6],
    ]

    public static func checkWinner(_ board: [Int]) -> Int {
        guard board.count == 9 else { return 0 }
        for line in winLines {
            let a = board[line[0]]
            if a != 0 && a == board[line[1]] && a == board[line[2]] { return a }
        }
        return 0
    }

    public static func chooseZoeMove(_ board: [Int], unbeatable: Bool = true) -> Int {
        guard board.count == 9 else { return -1 }
        let open = (0..<9).filter { board[$0] == 0 }
        guard !open.isEmpty else { return -1 }
        if !unbeatable, let randomMove = open.randomElement(), Int.random(in: 0..<100) < 40 {
            return randomMove
        }
        var bestScore = Int.min
        var bestMove = open[0]
        var copy = board
        for idx in open {
            copy[idx] = 2
            let score = minimax(&copy, depth: 0, zoeTurn: false)
            copy[idx] = 0
            if score > bestScore {
                bestScore = score
                bestMove = idx
            }
        }
        return bestMove
    }

    private static func minimax(_ board: inout [Int], depth: Int, zoeTurn: Bool) -> Int {
        let w = checkWinner(board)
        if w == 2 { return 10 - depth }
        if w == 1 { return depth - 10 }
        if !board.contains(0) { return 0 }
        if zoeTurn {
            var best = Int.min
            for i in 0..<9 where board[i] == 0 {
                board[i] = 2
                best = max(best, minimax(&board, depth: depth + 1, zoeTurn: false))
                board[i] = 0
            }
            return best
        } else {
            var best = Int.max
            for i in 0..<9 where board[i] == 0 {
                board[i] = 1
                best = min(best, minimax(&board, depth: depth + 1, zoeTurn: true))
                board[i] = 0
            }
            return best
        }
    }

    public static func evaluateSignalPuzzle(probs: [Double], tau: Double) -> Int {
        probs.filter { $0 > tau }.count
    }
}
