import SwiftUI

struct VolumeView: View {
    @State private var input = "0.70, 0.20, 0.08, 0.02"
    @State private var tau = 0.05
    @State private var previous: AccessibleVolumeResult?
    @State private var current: AccessibleVolumeResult?
    @State private var report = "The worked example has three alternatives above 0.05. Tokens exactly at the threshold are excluded."

    private var previewValues: [Double] {
        let parts = input.split { $0 == "," || $0.isWhitespace }
        let parsed = parts.compactMap { Double($0) }.filter { $0.isFinite && $0 >= 0 }.map { min(1.0, $0) }
        return parsed.isEmpty ? [0.70, 0.20, 0.08, 0.02] : Array(parsed.prefix(16))
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Count open choices strictly above τ. Breadth is not correctness, safety, or permission.")
                    .font(.body)
                    .foregroundStyle(GemPalette.muted)

                VStack(alignment: .leading, spacing: 14) {
                    Text("Probability distribution")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(GemPalette.muted)
                    TextField("0.70, 0.20, 0.08, 0.02", text: $input, axis: .vertical)
                        .font(.body)
                        .foregroundStyle(GemPalette.ink)
                        .padding(14)
                        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(GemPalette.surfaceHigh))
                        .lineLimit(2...5)
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)
                        .accessibilityLabel("Probabilities separated by commas or spaces")

                    Text(String(format: "Threshold τ = %.3f", tau))
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(GemPalette.ink)
                    Slider(value: $tau, in: 0...1, step: 0.001) {
                        Text("Probability threshold")
                    }
                    .tint(GemPalette.ruby)

                    VolumeGraphView(values: previewValues, tau: tau)
                        .frame(height: 132)

                    Button("Measure strict p > τ", action: measure)
                        .buttonStyle(GemPrimaryButtonStyle())
                }
                .padding(18)
                .gemCard(radius: 24)

                Text(report)
                    .font(.body)
                    .foregroundStyle(GemPalette.ink)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(18)
                    .gemCard(radius: 24)
                    .accessibilityLabel("Accessible-volume measurement result")

                if current != nil {
                    ShareLink(item: report + "\n\n" + AccessibleVolume.creator)
                        .buttonStyle(GemKeycapButtonStyle())
                }

                Text("Original equation created by Nicholas Michael Kloster alone, March 6, 2026.\n\nMomentum compares consecutive counts at the same threshold and vocabulary size.")
                    .font(.footnote)
                    .foregroundStyle(GemPalette.muted)
            }
            .padding(18)
        }
        .gemScreen()
    }

    private func measure() {
        do {
            let next = try AccessibleVolume.measure(AccessibleVolume.parse(input), tau: tau)
            let momentum: String
            if let previous, previous.vocabularySize == next.vocabularySize {
                momentum = String(format: "\nMomentum = %+d", next.accessible - previous.accessible)
            } else {
                momentum = "\nMomentum = not available for the first or differently sized distribution"
            }
            previous = next
            current = next
            report = next.summary() + momentum + "\n\nBreadth is not correctness. No action was authorized."
        } catch {
            current = nil
            report = "Measurement rejected: \(error)"
        }
    }
}

/// Live interactive p > τ bar chart with gliding Zoe Ruby threshold line.
private struct VolumeGraphView: View {
    let values: [Double]
    let tau: Double

    var body: some View {
        GeometryReader { geo in
            let chartH = max(24, geo.size.height - 28)
            let chartW = max(24, geo.size.width - 28)
            let tauY = 18 + chartH * (1 - min(1, max(0, tau)))

            ZStack(alignment: .topLeading) {
                // Soft horizontal reference lines
                ForEach(0..<5, id: \.self) { step in
                    let y = 18 + chartH * CGFloat(step) / 4
                    Path { p in
                        p.move(to: CGPoint(x: 4, y: y))
                        p.addLine(to: CGPoint(x: chartW, y: y))
                    }
                    .stroke(GemPalette.hairline, lineWidth: 0.7)
                }

                // Probability bars
                HStack(alignment: .bottom, spacing: 8) {
                    ForEach(Array(values.enumerated()), id: \.offset) { _, value in
                        let above = value > tau
                        VStack(spacing: 4) {
                            if values.count <= 8 {
                                Text(String(format: "%.2f", value))
                                    .font(.caption2.weight(.medium))
                                    .foregroundStyle(above ? GemPalette.emerald : GemPalette.muted)
                            }
                            RoundedRectangle(cornerRadius: 7, style: .continuous)
                                .fill(above ? GemPalette.emerald : GemPalette.surfaceHigh)
                                .frame(height: max(6, chartH * CGFloat(value)))
                        }
                        .frame(maxWidth: .infinity)
                    }
                }
                .frame(width: chartW - 8, height: chartH + 18, alignment: .bottom)
                .offset(x: 4, y: 0)

                // Gliding Zoe Ruby τ threshold line
                Path { p in
                    p.move(to: CGPoint(x: 4, y: tauY))
                    p.addLine(to: CGPoint(x: chartW, y: tauY))
                }
                .stroke(GemPalette.ruby, lineWidth: 2)

                Text("τ")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(GemPalette.ruby)
                    .position(x: chartW + 12, y: tauY)
            }
        }
        .accessibilityHidden(true)
    }
}
