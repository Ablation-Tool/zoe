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
                Text("Guided vision")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.cyan)
                if camera.isRunning {
                    CameraPreview(session: camera.session)
                        .frame(height: 280)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .accessibilityLabel("Camera preview. Analyze only when Inspect is pressed.")
                } else {
                    Text("Camera is off.\nStart it when you are ready.\nNothing is saved by Zoe.")
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.secondary)
                        .frame(maxWidth: .infinity, minHeight: 180)
                        .background(Color(red: 16 / 255, green: 27 / 255, blue: 43 / 255))
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                }
                Text(camera.status)
                    .font(.footnote)
                    .foregroundStyle(.yellow)
                HStack {
                    Button("Start camera") { camera.start() }
                    Button("Inspect once") { camera.inspect() }
                        .disabled(camera.isBusy)
                }
                .buttonStyle(.borderedProminent)
                HStack {
                    Button("Voice command") { speech.start() }
                    Button("Speak") { speaker.speak(camera.narration) }
                    Button("Stop") {
                        speech.stop()
                        speaker.stop()
                    }
                }
                .buttonStyle(.bordered)
                Text(speech.status)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                HStack {
                    ShareLink(item: camera.shareText)
                    Button("Open Gemini") {
                        if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                    }
                }
                .buttonStyle(.bordered)
                Text(camera.shareText)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color(red: 16 / 255, green: 27 / 255, blue: 43 / 255))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                Text("Voice commands: inspect, repeat, stop, measure, battery, Gemini. Listening is one-shot. Image labels are model outputs, not proof of identity or safety.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .background(Color(red: 8 / 255, green: 13 / 255, blue: 24 / 255))
        .onAppear {
            speech.onCommand = handle
        }
        .onDisappear {
            camera.stop()
            speech.stop()
            speaker.stop()
        }
    }

    private func handle(_ command: VoiceCommand) {
        switch command {
        case .inspect:
            camera.inspect()
        case .repeatResult:
            speaker.speak(camera.narration)
        case .stop:
            speech.stop()
            speaker.stop()
        case .measure:
            selection = 1
        case .vision:
            selection = 0
        case .device:
            selection = 2
        case .gemini:
            if let url = URL(string: "https://gemini.google.com") { openURL(url) }
        case .unknown:
            speech.status = "No supported command found. Try inspect, repeat, measure, battery, Gemini, or stop."
        }
    }
}
