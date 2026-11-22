import SwiftUI

/// Zoe Explore — Gemini-Live-Style Simultaneous Live Camera & Continuous Voice Orb for Apple (v0.6.2-beta).
struct ZoeLiveView: View {
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @StateObject private var camera = CameraController()
    @StateObject private var nativeVoice = ZoeNativeVoice()
    @State private var brain = ZoeBrainEngine(defaults: .standard)

    @State private var active = false
    @State private var hiZoeMode = false
    @State private var cameraOn = false
    @State private var pulse = false
    @State private var useNativeVoice = false
    @State private var caption = "Hi, I'm Zoe. Tap the orb to talk hands-free, or tap Live + Cam to show me your world and talk all at once."
    @State private var stateLabel = "TAP ORB TO GO LIVE · MIC & CAMERA START OFF"

    var body: some View {
        VStack(spacing: 14) {
            HStack(spacing: 6) {
                Button(cameraOn ? "Camera: on" : "Camera: off") {
                    cameraOn.toggle()
                    if cameraOn {
                        camera.start()
                    } else {
                        camera.stop()
                    }
                }
                .buttonStyle(GemKeycapButtonStyle(accent: cameraOn ? GemPalette.emerald : GemPalette.muted))

                Button(hiZoeMode ? "Hi Zoe: on" : "Hi Zoe: off") {
                    hiZoeMode.toggle()
                    if hiZoeMode {
                        active = true
                        stateLabel = "WAITING FOR 'HI ZOE' · VISIBLE OPT-IN"
                        caption = "\"Hi Zoe\" hangout mode is active. Say \"Hi Zoe\" anytime — tap End / Mute to turn off."
                        speech.start()
                    } else {
                        stopLive()
                    }
                }
                .buttonStyle(GemKeycapButtonStyle(accent: hiZoeMode ? GemPalette.seafoam : GemPalette.muted))

                Button(useNativeVoice ? "Voice: Zoe 44k" : "Voice: iOS") {
                    useNativeVoice.toggle()
                }
                .buttonStyle(GemKeycapButtonStyle(accent: useNativeVoice ? GemPalette.ruby : GemPalette.muted))
            }
            .padding(.horizontal, 16)

            if cameraOn {
                ZStack(alignment: .topTrailing) {
                    CameraPreview(session: camera.session)
                        .frame(height: 210)
                        .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
                    Button("Look now") {
                        camera.inspect()
                        let sight = camera.narration
                        caption = sight
                        speakClean(sight)
                    }
                    .font(.caption.weight(.semibold))
                    .padding(.horizontal, 12)
                    .padding(.vertical, 6)
                    .background(.ultraThinMaterial, in: Capsule())
                    .padding(10)
                }
                .padding(.horizontal, 16)
            }

            Spacer(minLength: 4)

            Button(action: onOrbTap) {
                ZStack {
                    Circle()
                        .fill(RadialGradient(
                            colors: [
                                (active ? GemPalette.emerald : GemPalette.cobalt).opacity(0.65),
                                GemPalette.seafoam.opacity(0.18),
                                Color.clear,
                            ],
                            center: .center,
                            startRadius: 20,
                            endRadius: cameraOn ? 78 : 112
                        ))
                        .frame(width: cameraOn ? 148 : 212, height: cameraOn ? 148 : 212)
                        .scaleEffect(pulse ? 1.07 : 0.94)
                        .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulse)

                    Image("RubySprout")
                        .resizable()
                        .scaledToFit()
                        .frame(width: cameraOn ? 46 : 64, height: cameraOn ? 46 : 64)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Zoe Explore orb. Tap to speak or interrupt.")

            Text(stateLabel)
                .font(.caption.weight(.semibold))
                .foregroundStyle(GemPalette.cobalt)

            Text(caption)
                .font(.body)
                .foregroundStyle(GemPalette.ink)
                .multilineTextAlignment(.center)
                .padding(16)
                .frame(maxWidth: .infinity)
                .gemCard(radius: 22)
                .padding(.horizontal, 16)

            Spacer(minLength: 4)

            HStack(spacing: 8) {
                Button(active ? "Listening…" : "Talk Now", action: onOrbTap)
                    .buttonStyle(GemPrimaryButtonStyle())
                Button(cameraOn && active ? "Cam Live" : "Live + Cam") {
                    if !cameraOn {
                        cameraOn = true
                        camera.start()
                    }
                    onOrbTap()
                }
                .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.seafoam))
                Button("End / Mute", action: stopLive)
                    .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
        }
        .gemScreen()
        .onAppear {
            pulse = true
            speech.onPartialTranscript = { partial in
                if active && !hiZoeMode && !partial.isEmpty {
                    caption = "You: \(partial)"
                }
            }
            speech.onSilenceTimeout = {
                if active {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.28) {
                        if active { speech.start() }
                    }
                }
            }
            speech.onTranscript = { heard in
                guard active else { return }
                if ConversationResponse.isStop(heard) {
                    stopLive()
                    return
                }
                if hiZoeMode {
                    if ZoeSignalAndWakeCore.isHiZoeTrigger(heard) {
                        hiZoeMode = false
                        let trailing = ZoeSignalAndWakeCore.stripWakePrefix(heard)
                        let reply = trailing.isEmpty
                            ? "Hi! I'm Zoe — ready to hang out and explore. What are we getting into?"
                            : brain.respond(trailing).reply
                        caption = reply
                        speakClean(reply)
                    } else if active {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) {
                            if active { speech.start() }
                        }
                    }
                    return
                }
                if cameraOn {
                    camera.inspect()
                }
                let sightPrefix = cameraOn && !camera.narration.isEmpty ? "\(camera.narration) " : ""
                let reply = sightPrefix + brain.respond(heard).reply
                caption = "You: \(heard)\n\n\(reply)"
                speakClean(reply)
            }
            speaker.onFinish = {
                if active {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.26) {
                        if active { speech.start() }
                    }
                }
            }
        }
        .onDisappear(perform: stopLive)
    }

    private func speakClean(_ raw: String) {
        let clean = ZoeSignalAndWakeCore.sanitizeForSpeech(raw)
        stateLabel = "ZOE IS SPEAKING · TAP ORB TO INTERRUPT"
        if useNativeVoice {
            nativeVoice.speak(clean) {
                if active {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.26) {
                        if active { speech.start() }
                    }
                }
            }
        } else {
            speaker.speak(clean)
        }
    }

    private func onOrbTap() {
        speaker.stop()
        nativeVoice.stop()
        active = true
        stateLabel = cameraOn ? "LIVE VOICE + SIGHT · SPEAK NATURALLY" : "LIVE · LISTENING NATURALLY"
        speech.start()
    }

    private func stopLive() {
        active = false
        hiZoeMode = false
        cameraOn = false
        speech.stop()
        speaker.stop()
        nativeVoice.stop()
        camera.stop()
        stateLabel = "EXPLORE PAUSED · MIC & CAMERA OFF"
    }
}
