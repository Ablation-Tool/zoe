import SwiftUI

/// Zoe Live Voice & Camera Orb for Apple (iPhone, iPad & iPhone Duo Fold · v0.6.0-beta).
struct ZoeLiveView: View {
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @StateObject private var nativeVoice = ZoeNativeVoice()
    @State private var brain = ZoeBrainEngine(defaults: .standard)

    @State private var active = false
    @State private var hiZoeMode = false
    @State private var pulse = false
    @State private var useNativeVoice = false
    @State private var caption = "Hi, I'm Zoe. Tap the orb or enable 'Hi Zoe' whenever you want to hang out and explore — mic starts off."
    @State private var stateLabel = "ZOE EXPLORE · MIC STARTS OFF"

    var body: some View {
        VStack(spacing: 18) {
            HStack(spacing: 8) {
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
                .buttonStyle(GemKeycapButtonStyle())
                Button("Sing Zoe") {
                    stateLabel = "SINGING ZOE (44.1 kHz OFFLINE)"
                    caption = "Singing Zoe's native soprano melody offline…"
                    nativeVoice.singZoe()
                }
                .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
            }
            .padding(.horizontal, 16)

            Spacer()

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
                            startRadius: 24,
                            endRadius: 115
                        ))
                        .frame(width: 220, height: 220)
                        .scaleEffect(pulse ? 1.07 : 0.94)
                        .animation(.easeInOut(duration: 2.0).repeatForever(autoreverses: true), value: pulse)

                    Image("RubySprout")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 68, height: 68)
                }
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Zoe Live orb. Tap to speak or interrupt.")

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

            Spacer()

            HStack(spacing: 12) {
                Button(active ? "Listening…" : "Talk Now", action: onOrbTap)
                    .buttonStyle(GemPrimaryButtonStyle())
                Button("End / Mute", action: stopLive)
                    .buttonStyle(GemKeycapButtonStyle(accent: GemPalette.ruby))
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
        }
        .gemScreen()
        .onAppear {
            pulse = true
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
                        stateLabel = "ZOE IS SPEAKING · TAP ORB TO INTERRUPT"
                        speaker.speak(reply)
                    } else if active {
                        speech.start()
                    }
                    return
                }
                let reply = brain.respond(heard).reply
                caption = reply
                stateLabel = "ZOE IS SPEAKING · TAP ORB TO INTERRUPT"
                if useNativeVoice {
                    nativeVoice.speak(reply) {
                        if active { speech.start() }
                    }
                } else {
                    speaker.speak(reply)
                }
            }
            speaker.onFinish = {
                if active { speech.start() }
            }
        }
        .onDisappear(perform: stopLive)
    }

    private func onOrbTap() {
        speaker.stop()
        nativeVoice.stop()
        active = true
        stateLabel = "LISTENING · SPEAK NATURALLY"
        speech.start()
    }

    private func stopLive() {
        active = false
        speech.stop()
        speaker.stop()
        nativeVoice.stop()
        stateLabel = "LIVE CALL ENDED · MIC OFF"
    }
}
