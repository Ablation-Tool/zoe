import SwiftUI

struct VolumeView: View {
    @State private var input = "0.70, 0.20, 0.08, 0.02"
    @State private var tau = 0.05
    @State private var previous: AccessibleVolumeResult?
    @State private var current: AccessibleVolumeResult?
    @State private var report = "The worked example has three alternatives above 0.05. Tokens exactly at the threshold are excluded."

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Accessible volume")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.cyan)
                Text("Measure how many alternatives remain open before selection. Forecast breadth is not correctness, safety, or permission.")
                    .foregroundStyle(.secondary)
                Text("Probability distribution")
                    .font(.headline)
                TextField("Probabilities", text: $input, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .lineLimit(2...6)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .accessibilityLabel("Probabilities separated by commas or spaces")
                Text(String(format: "Threshold τ = %.3f", tau))
                    .foregroundStyle(.yellow)
                Slider(value: $tau, in: 0...1, step: 0.001) {
                    Text("Probability threshold")
                }
                Button("Measure strict p > τ", action: measure)
                    .buttonStyle(.borderedProminent)
                    .frame(maxWidth: .infinity)
                Text(report)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color(red: 16 / 255, green: 27 / 255, blue: 43 / 255))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                    .accessibilityLabel("Accessible-volume measurement result")
                if current != nil {
                    ShareLink(item: report + "\n\n" + AccessibleVolume.creator)
                }
                Text("Original equation created by Nicholas Michael Kloster alone, March 6, 2026.\n\nMomentum compares consecutive counts at the same threshold and vocabulary size. Equal counts do not imply identical distributions or accessible-set membership.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .background(Color(red: 8 / 255, green: 13 / 255, blue: 24 / 255))
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
