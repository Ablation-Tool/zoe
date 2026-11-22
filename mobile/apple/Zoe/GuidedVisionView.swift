import SwiftUI
import ZoeCore

struct GuidedVisionView: View {
    @Binding var selection: Int
    @StateObject private var camera = CameraController()
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @Environment(\.openURL) private var openURL
    @State private var improveExpanded = false
    @State private var teachLabel = ""
    @State private var structuralNote = ""
    @State private var learnedLabels: [String] = []

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if camera.isRunning {
                    CameraPreview(session: camera.session)
                        .frame(height: 290)
                        .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                        .accessibilityLabel("Camera preview. Analyze only when Inspect is pressed.")
                } else {
                    VStack(spacing: 8) {
                        Image(systemName: "eye")
                            .font(.system(size: 32, weight: .light))
                            .foregroundStyle(GemPalette.cobalt)
                        Text("Camera is off")
                            .font(.headline)
                            .foregroundStyle(.white)
                        Text("Tap Start camera when you are ready.\nNothing is saved by Zoe.")
                            .font(.subheadline)
                            .multilineTextAlignment(.center)
                            .foregroundStyle(Color.white.opacity(0.75))
                    }
                    .frame(maxWidth: .infinity, minHeight: 200)
                    .background(GemPalette.opticalGlass)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                }

                Text(camera.status)
                    .font(.footnote)
                    .foregroundStyle(GemPalette.muted)

                HStack(spacing: 10) {
                    Button("Start camera") { camera.start() }
                        .buttonStyle(GemPrimaryButtonStyle())
                    Button("Inspect once") { camera.inspect() }
                        .buttonStyle(GemKeycapButtonStyle())
                        .disabled(camera.isBusy)
                }

                HStack(spacing: 10) {
                    Button("Voice") { speech.start() }
                        .buttonStyle(GemKeycapButtonStyle())
                    Button("Speak") { speaker.speak(camera.narration) }
                        .buttonStyle(GemKeycapButtonStyle())
                    Button("Stop") {
                        speech.stop()
                        speaker.stop()
                    }
                    .buttonStyle(GemKeycapButtonStyle())
                }

                Text(speech.status)
                    .font(.footnote)
                    .foregroundStyle(GemPalette.muted)

                Text(camera.shareText)
                    .font(.body)
                    .foregroundStyle(GemPalette.ink)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(18)
                    .gemCard(radius: 22)

                DisclosureGroup("Improve recognition (Offline memory: \(learnedLabels.count))", isExpanded: $improveExpanded) {
                    VStack(alignment: .leading, spacing: 10) {
                        if !structuralNote.isEmpty {
                            Text(structuralNote)
                                .font(.footnote)
                                .foregroundStyle(GemPalette.cobalt)
                        }
                        HStack(spacing: 8) {
                            TextField("Teach Zoe object name…", text: $teachLabel)
                                .textFieldStyle(.roundedBorder)
                            Button("Learn") {
                                let cleaned = teachLabel.trimmingCharacters(in: .whitespacesAndNewlines)
                                guard !cleaned.isEmpty else { return }
                                if !learnedLabels.contains(where: { $0.caseInsensitiveCompare(cleaned) == .orderedSame }) {
                                    learnedLabels.append(cleaned)
                                }
                                structuralNote = "Learned \"\(cleaned)\" locally on-device to sharpen future Guided Vision & Explore recognition."
                                teachLabel = ""
                            }
                            .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.emerald))
                        }
                        Button("Silent Patent Structural Prior (CPC Physical)") {
                            runSilentPatentPrior()
                        }
                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.cobalt))
                    }
                    .padding(.top, 8)
                }
                .padding(14)
                .gemCard(radius: 18)

                HStack(spacing: 10) {
                    ShareLink(item: camera.shareText)
                        .buttonStyle(GemKeycapButtonStyle())
                    Button("Open Gemini") {
                        if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                    }
                    .buttonStyle(GemKeycapButtonStyle())
                }

                Text("Voice commands: inspect, repeat, stop, measure, battery, Gemini. Image labels are model outputs, not proof of identity or safety.")
                    .font(.footnote)
                    .foregroundStyle(GemPalette.muted)
            }
            .padding(18)
        }
        .gemScreen()
        .onAppear { speech.onCommand = handle }
        .onDisappear {
            camera.stop()
            speech.stop()
            speaker.stop()
        }
    }

    private func runSilentPatentPrior() {
        let base = camera.narration.trimmingCharacters(in: .whitespacesAndNewlines)
        let detected = ScientificVisualAndPatentCore.extractPatentNumber(from: base)
        let rawQ = detected.isEmpty ? String(base.prefix(64)) : detected
        let filtered = ScientificVisualAndPatentCore.applyPhysicalCpcFilter(query: rawQ.isEmpty ? "optical prism gear" : rawQ, detectedPatentId: detected)
        structuralNote = "Checking physical patent classes (A47/B25/F16/G01/G02/H01) silently…"
        let inner = "q=\(filtered.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? "prism")&num=3"
        let encoded = inner.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? inner
        guard let url = URL(string: "https://patents.google.com/xhr/query?url=\(encoded)") else { return }
        Task {
            do {
                let (data, _) = try await URLSession.shared.data(from: url)
                let raw = String(data: data, encoding: .utf8) ?? ""
                let matches = ScientificVisualAndPatentCore.parseGooglePatentsJson(raw, maxResults: 3)
                await MainActor.run {
                    if let top = matches.first {
                        let concept = ScientificVisualAndPatentCore.cleanPhysicalConcept(top.title)
                        if !learnedLabels.contains(where: { $0.caseInsensitiveCompare(concept) == .orderedSame }) {
                            learnedLabels.append(concept)
                        }
                        let dims = top.dimensionsNote.isEmpty ? "" : " · Scale: \(top.dimensionsNote)"
                        structuralNote = "Refined & learned offline: \(concept)\(dims)"
                    } else {
                        structuralNote = "No high-confidence physical patent match — type an object name above to teach Zoe directly."
                    }
                }
            } catch {
                await MainActor.run {
                    structuralNote = "Offline right now — type an object name above to teach Zoe directly."
                }
            }
        }
    }

    private func handle(_ command: VoiceCommand) {
        switch command {
        case .inspect: camera.inspect()
        case .repeatResult: speaker.speak(camera.narration)
        case .stop:
            speech.stop()
            speaker.stop()
        case .measure: selection = 1
        case .vision: selection = 0
        case .device: selection = 2
        case .gemini:
            if let url = URL(string: "https://gemini.google.com") { openURL(url) }
        case .unknown:
            speech.status = "No supported command found. Try inspect, repeat, measure, battery, Gemini, or stop."
        }
    }
}
