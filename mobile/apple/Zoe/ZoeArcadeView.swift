import SwiftUI

/// Zoe Arcade — Ad-Free Offline Games for Apple (v0.6.0-beta).
struct ZoeArcadeView: View {
    @State private var board = Array(repeating: 0, count: 9)
    @State private var unbeatable = true
    @State private var over = false
    @State private var status = "Play Tic-Tac-Toe or tune Kloster A_tau(p) signals offline!"
    @State private var wins = 0
    @State private var draws = 0
    @State private var zoeWins = 0

    @State private var probs = [0.42, 0.28, 0.16, 0.09, 0.05]
    @State private var targetCount = 2
    @State private var tau = 0.20
    @State private var streak = 0

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                Text(status)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(GemPalette.cobalt)
                    .frame(maxWidth: .infinity, alignment: .leading)

                // Tic-Tac-Toe vs Zoe
                VStack(spacing: 10) {
                    Text("Tic-Tac-Toe vs Zoe · You \(wins) · Draws \(draws) · Zoe \(zoeWins)")
                        .font(.headline)
                        .foregroundStyle(GemPalette.ink)

                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                        ForEach(0..<9, id: \.self) { idx in
                            Button {
                                tapCell(idx)
                            } label: {
                                Text(board[idx] == 1 ? "X" : board[idx] == 2 ? "O" : "")
                                    .font(.title.weight(.bold))
                                    .foregroundStyle(board[idx] == 1 ? GemPalette.cobalt : GemPalette.ruby)
                                    .frame(maxWidth: .infinity, minHeight: 74)
                                    .background(RoundedRectangle(cornerRadius: 16).fill(GemPalette.surfaceHigh))
                            }
                            .buttonStyle(.plain)
                        }
                    }

                    HStack(spacing: 8) {
                        Button("New Board") { resetBoard() }
                            .buttonStyle(GemPrimaryButtonStyle())
                        Button(unbeatable ? "Mode: Unbeatable" : "Mode: Kid Friendly") {
                            unbeatable.toggle()
                            resetBoard()
                        }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ochre))
                    }
                }
                .padding(16)
                .gemCard(radius: 22)

                // Kloster A_tau(p) Signal Puzzle
                VStack(alignment: .leading, spacing: 10) {
                    Text("Kloster A_τ(p) Signal Puzzle · Streak \(streak)")
                        .font(.headline)
                        .foregroundStyle(GemPalette.ink)
                    Text("Tune τ so strictly \(targetCount) of 5 signals exceed τ (p > τ).")
                        .font(.subheadline)
                        .foregroundStyle(GemPalette.muted)

                    ForEach(Array(probs.enumerated()), id: \.offset) { idx, p in
                        HStack {
                            Text("x\(idx + 1)  \(String(format: "%.2f", p))")
                                .font(.caption.monospaced())
                            ProgressView(value: p)
                                .tint(p > tau ? GemPalette.emerald : GemPalette.muted)
                            Text(p > tau ? "OPEN" : "cut")
                                .font(.caption2.weight(.semibold))
                                .foregroundStyle(p > tau ? GemPalette.emerald : GemPalette.muted)
                        }
                    }

                    Slider(value: $tau, in: 0.0...0.60, step: 0.01)
                    Text("Threshold τ = \(String(format: "%.2f", tau))")
                        .font(.caption.monospaced())
                        .foregroundStyle(GemPalette.ochre)

                    Button("Check Signal Lock") {
                        let got = CreativeAndArcadeCore.evaluateSignalPuzzle(probs: probs, tau: tau)
                        if got == targetCount {
                            streak += 1
                            status = "Bullseye! Strict A_tau(p) = \(got) · Streak \(streak)!"
                            targetCount = Int.random(in: 1...4)
                        } else {
                            streak = 0
                            status = "Currently \(got) open (target is \(targetCount)). Remember strict p > τ!"
                        }
                    }
                    .buttonStyle(GemPrimaryButtonStyle(accent: GemPalette.emerald))
                }
                .padding(16)
                .gemCard(radius: 22)
            }
            .padding(16)
        }
        .gemScreen()
    }

    private func tapCell(_ idx: Int) {
        guard !over && board[idx] == 0 else { return }
        board[idx] = 1
        if finishIfEnded() { return }
        let move = CreativeAndArcadeCore.chooseZoeMove(board, unbeatable: unbeatable)
        if move >= 0 {
            board[move] = 2
            _ = finishIfEnded()
        }
    }

    private func finishIfEnded() -> Bool {
        let w = CreativeAndArcadeCore.checkWinner(board)
        if w == 1 {
            over = true; wins += 1; status = "You win Tic-Tac-Toe!"; return true
        }
        if w == 2 {
            over = true; zoeWins += 1; status = "Zoe wins this round!"; return true
        }
        if !board.contains(0) {
            over = true; draws += 1; status = "Draw! Great defense."; return true
        }
        return false
    }

    private func resetBoard() {
        board = Array(repeating: 0, count: 9)
        over = false
        status = "Fresh board — your move (X)!"
    }
}
