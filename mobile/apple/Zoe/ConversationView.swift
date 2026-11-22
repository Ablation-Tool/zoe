import AVFoundation
import SwiftUI
import UIKit

struct ConversationView: View {
    var onGoHome: () -> Void = {}
    var onOpenMapsSafety: () -> Void = {}
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @StateObject private var nativeVoice = ZoeNativeVoice()
    @State private var brain = ZoeBrainEngine(defaults: .standard)
    @State private var active = false
    @State private var useNativeVoice = false
    @State private var typedMessage = ""
    @State private var exchanges: [String] = []
    @State private var pendingAction: OsToolsBridge.ActionSuggestion?
    @State private var torchOn = false
    @State private var status = "Microphone is off. Type below or tap Start talking whenever you are ready."
    @State private var brainBadge = "Zoe Brain · gear1_mobile · Offline"
    @State private var lastResponse = "Hi, I'm Zoe. What would you like to explore?"
    @Environment(\.openURL) private var openURL

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text(status)
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(GemPalette.cobalt)

                    HStack(spacing: 10) {
                        Button(useNativeVoice ? "Voice: Zoe Synth" : "Voice: OS TTS") {
                            useNativeVoice.toggle()
                            status = useNativeVoice
                                ? "Zoe Native Formant Voice active (44.1 kHz DSP, 100% offline)."
                                : "Device OS text-to-speech voice active."
                        }
                        .buttonStyle(GemKeycapButtonStyle())

                        Button("Sing Zoe") {
                            status = "Singing Zoe's native soprano theme (44.1 kHz DSP, offline)…"
                            nativeVoice.singZoe()
                        }
                        .buttonStyle(GemKeycapButtonStyle())

                        if !useNativeVoice {
                            Menu("OS Voice") {
                                ForEach(speaker.voices, id: \.identifier) { voice in
                                    Button(voice.name) {
                                        speaker.selectVoice(voice)
                                        speaker.speak("This is Zoe.")
                                    }
                                }
                            }
                            .buttonStyle(GemKeycapButtonStyle())
                        }
                    }

                    HStack(spacing: 10) {
                        Button(action: {
                            stop()
                            onGoHome()
                        }) {
                            Image("RubySprout")
                                .resizable()
                                .scaledToFit()
                                .frame(width: 28, height: 28)
                                .frame(width: 44, height: 44)
                        }
                        .buttonStyle(.plain)
                        .accessibilityLabel("Return to Zoe home")
                        Text(brainBadge)
                            .font(.footnote)
                            .foregroundStyle(GemPalette.muted)
                    }
                    .padding(.top, 2)

                    Text(exchanges.isEmpty
                         ? "No turns yet. Try typing `remember ...`, `navigate to ...`, or tapping Start talking."
                         : exchanges.joined(separator: "\n\n"))
                        .font(.body)
                        .foregroundStyle(GemPalette.ink)
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(20)
                        .gemCard(radius: 24)

                    if let action = pendingAction, action.isActionable {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("BUILT-IN PHONE ACTION · TAP TO RUN")
                                .font(.caption.weight(.semibold))
                                .foregroundStyle(GemPalette.seafoam)
                            if action.kind == .navigate || action.kind == .mapSearch {
                                HStack(spacing: 10) {
                                    Button("Apple Maps") { runPendingAction(preferGoogleMaps: false) }
                                        .buttonStyle(GemPrimaryButtonStyle(accent: GemPalette.cobalt))
                                    Button("Google Maps") { runPendingAction(preferGoogleMaps: true) }
                                        .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.emerald))
                                }
                            } else {
                                Button(action.label) { runPendingAction(preferGoogleMaps: false) }
                                    .buttonStyle(GemPrimaryButtonStyle(accent: GemPalette.cobalt))
                            }
                            Button("Dismiss") { pendingAction = nil }
                                .buttonStyle(GemKeycapButtonStyle())
                        }
                        .padding(14)
                        .gemCard(radius: 20)
                    }

                    HStack(spacing: 10) {
                        Button("Repeat") { speakReply(lastResponse, resumeListening: false) }
                            .buttonStyle(GemKeycapButtonStyle())
                        Button("Clear") { exchanges.removeAll() }
                            .buttonStyle(GemKeycapButtonStyle())
                        if !exchanges.isEmpty {
                            ShareLink(item: exchanges.joined(separator: "\n\n"))
                                .buttonStyle(GemKeycapButtonStyle())
                        }
                        Button("Open Gemini") {
                            stop()
                            if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                        }
                        .buttonStyle(GemKeycapButtonStyle())
                    }
                }
                .padding(18)
            }

            // Bottom thumb-zone ergonomic Google Gemini composer + voice dock
            VStack(spacing: 10) {
                HStack(spacing: 8) {
                    TextField("Message Zoe…", text: $typedMessage)
                        .textFieldStyle(.plain)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 11)
                        .submitLabel(.send)
                        .onSubmit(sendTyped)

                    Button("Send", action: sendTyped)
                        .buttonStyle(GemPrimaryButtonStyle())
                        .fixedSize()
                }
                .padding(6)
                .gemCard(radius: 28)

                HStack(spacing: 10) {
                    Button(active ? "Restart talking" : "Start talking", action: start)
                        .buttonStyle(GemPrimaryButtonStyle())
                    Button("Stop", action: stop)
                        .buttonStyle(GemKeycapButtonStyle())
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 8)
            .padding(.bottom, 14)
        }
        .gemScreen()
        .onAppear {
            brainBadge = "Zoe Brain · gear1_mobile · mem=\(brain.memoryCount) · Offline"
            speech.onTranscript = handle
            speaker.onFinish = {
                if self.active { self.speech.start() }
            }
        }
        .onDisappear(perform: stop)
    }

    private func sendTyped() {
        let msg = typedMessage.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !msg.isEmpty else { return }
        typedMessage = ""
        append("YOU", msg)
        let suggestion = OsToolsBridge.parseActionIntent(msg)
        if suggestion.isActionable { pendingAction = suggestion }
        let res = brain.respond(msg)
        lastResponse = res.reply
        brainBadge = res.telemetryBadge
        append("ZOE", res.reply)
        status = "Zoe Brain replied offline (0 cloud tokens)."
        speakReply(res.reply, resumeListening: false)
    }

    private func start() {
        active = true
        status = "Zoe is speaking…"
        speakReply(lastResponse, resumeListening: true)
    }

    private func handle(_ heard: String) {
        guard active else { return }
        append("YOU", heard)
        let suggestion = OsToolsBridge.parseActionIntent(heard)
        if suggestion.isActionable { pendingAction = suggestion }
        let res = brain.respond(heard)
        lastResponse = res.reply
        brainBadge = res.telemetryBadge
        append("ZOE", res.reply)
        if ConversationResponse.isStop(heard) {
            active = false
            status = "Conversation stopped. The microphone is off."
            speakReply(res.reply, resumeListening: false)
        } else {
            status = "Zoe is speaking…"
            speakReply(res.reply, resumeListening: true)
        }
    }

    private func runPendingAction(preferGoogleMaps: Bool) {
        guard let act = pendingAction, act.isActionable else { return }
        switch act.kind {
        case .navigate:
            if preferGoogleMaps {
                if let app = URL(string: OsToolsBridge.googleMapsAppNavigationUrl(destination: act.query)),
                   UIApplication.shared.canOpenURL(app) {
                    openURL(app)
                } else if let web = URL(string: OsToolsBridge.googleMapsWebDirectionsUrl(destination: act.query)) {
                    openURL(web)
                }
            } else if let apple = URL(string: OsToolsBridge.appleMapsNavigationUrl(destination: act.query)) {
                openURL(apple)
            }
        case .mapSearch:
            let urlStr = preferGoogleMaps
                ? OsToolsBridge.googleMapsSearchUrl(query: act.query)
                : OsToolsBridge.appleMapsSearchUrl(query: act.query)
            if let url = URL(string: urlStr) { openURL(url) }
        case .openLocation, .openSafety:
            stop()
            onOpenMapsSafety()
        case .toggleTorch:
            if let device = AVCaptureDevice.default(for: .video), device.hasTorch {
                do {
                    try device.lockForConfiguration()
                    torchOn.toggle()
                    device.torchMode = torchOn ? .on : .off
                    device.unlockForConfiguration()
                    status = torchOn ? "Flashlight on." : "Flashlight off."
                } catch {
                    status = "Flashlight unavailable."
                }
            }
        case .setTimer, .setAlarm:
            status = "iOS does not allow third-party apps to create Clock timers/alarms silently; ask Siri or open the Clock app."
        case .none:
            break
        }
    }

    private func speakReply(_ text: String, resumeListening: Bool) {
        if useNativeVoice {
            nativeVoice.speak(text) {
                if resumeListening && self.active {
                    self.speech.start()
                }
            }
        } else {
            speaker.speak(text)
        }
    }

    private func append(_ role: String, _ text: String) {
        exchanges.append("\(role) · \(text)")
        if exchanges.count > 12 { exchanges.removeFirst() }
    }

    private func stop() {
        active = false
        speech.stop()
        speaker.stop()
        nativeVoice.stop()
        status = "Conversation stopped. The microphone is off."
    }
}
