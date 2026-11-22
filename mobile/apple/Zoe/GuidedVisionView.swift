import SwiftUI

struct GuidedVisionView: View {
    @Binding var selection: Int
    @StateObject private var camera = CameraController()
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @Environment(\.openURL) private var openURL

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
