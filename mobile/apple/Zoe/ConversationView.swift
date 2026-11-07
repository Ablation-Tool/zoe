import SwiftUI

struct ConversationView: View {
    @StateObject private var speech = SpeechController()
    @StateObject private var speaker = Speaker()
    @State private var active = false
    @State private var exchanges: [String] = []
    @State private var status = "Conversation is off. Start whenever you are ready."
    @State private var lastResponse = "Hi, I'm Zoe. What would you like to explore?"
    @Environment(\.openURL) private var openURL

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text("Talk with Zoe")
                    .font(.largeTitle.bold())
                    .foregroundStyle(.cyan)
                Text("Zoe speaks, you answer, Zoe responds. Turns repeat until Stop. The microphone is off when you leave this screen.")
                    .foregroundStyle(.secondary)
                Text(status)
                    .foregroundStyle(.yellow)
                Menu("Voice") {
                    ForEach(speaker.voices, id: \.identifier) { voice in
                        Button(action: {
                            speaker.selectVoice(voice)
                            speaker.speak("This is Zoe.")
                        }) {
                            Text(voice.name)
                        }
                    }
                }
                HStack {
                    Button(active ? "Restart conversation" : "Start talking", action: start)
                    Button("Stop", action: stop)
                }
                .buttonStyle(.borderedProminent)
                HStack {
                    Button("Repeat") { speaker.speak(lastResponse) }
                    Button("Open Gemini") {
                        stop()
                        if let url = URL(string: "https://gemini.google.com") { openURL(url) }
                    }
                    Button("Clear") {
                        exchanges.removeAll()
                    }
                }
                .buttonStyle(.bordered)
                Text(exchanges.isEmpty ? "No turns yet. Transcripts stay on this screen unless you clear or share them." : exchanges.joined(separator: "\n\n"))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding()
                    .background(Color(red: 16 / 255, green: 27 / 255, blue: 43 / 255))
                    .clipShape(RoundedRectangle(cornerRadius: 16))
                if !exchanges.isEmpty {
                    ShareLink(item: exchanges.joined(separator: "\n\n"))
                }
                Text("Local replies are deterministic for device topics. Open-ended understanding is not faked.")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            }
            .padding()
        }
        .background(Color(red: 8 / 255, green: 13 / 255, blue: 24 / 255))
        .onAppear {
            speech.onTranscript = handle
            speaker.onFinish = {
                if self.active { self.speech.start() }
            }
        }
        .onDisappear(perform: stop)
    }

    private func start() {
        active = true
        status = "Zoe is speaking…"
        speaker.speak(lastResponse)
    }

    private func handle(_ heard: String) {
        guard active else { return }
        append("YOU", heard)
        let response = ConversationResponse.forInput(heard)
        lastResponse = response
        append("ZOE", response)
        if ConversationResponse.isStop(heard) {
            active = false
            status = "Conversation stopped. The microphone is off."
            speaker.speak(response)
        } else {
            status = "Zoe is speaking…"
            speaker.speak(response)
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
        status = "Conversation stopped. The microphone is off."
    }
}
