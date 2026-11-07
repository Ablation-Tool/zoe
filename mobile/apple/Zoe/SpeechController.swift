import AVFoundation
import Speech
import SwiftUI

final class SpeechController: NSObject, ObservableObject {
    @Published var status = "Voice is idle. Start one command when ready."
    var onCommand: ((VoiceCommand) -> Void)?
    var onTranscript: ((String) -> Void)?

    private let recognizer = SFSpeechRecognizer()
    private let engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var listening = false

    func start() {
        if listening {
            finish("Listening cancelled. No command was executed.")
            return
        }
        guard let recognizer, recognizer.isAvailable else {
            status = "Speech recognition is not currently available."
            return
        }
        guard recognizer.supportsOnDeviceRecognition else {
            status = "On-device speech recognition is unavailable for the current locale. No audio was sent anywhere."
            return
        }
        status = "Requesting speech and microphone permission…"
        SFSpeechRecognizer.requestAuthorization { authorization in
            guard authorization == .authorized else {
                DispatchQueue.main.async { self.status = "Speech recognition permission was not granted." }
                return
            }
            AVCaptureDevice.requestAccess(for: .audio) { granted in
                if granted {
                    DispatchQueue.main.async { self.begin() }
                } else {
                    DispatchQueue.main.async { self.status = "Microphone permission was not granted. No audio was captured." }
                }
            }
        }
    }

    private func begin() {
        do {
            let session = AVAudioSession.sharedInstance()
            try session.setCategory(.record, mode: .measurement, options: .duckOthers)
            try session.setActive(true, options: .notifyOthersOnDeactivation)
            let request = SFSpeechAudioBufferRecognitionRequest()
            request.requiresOnDeviceRecognition = true
            request.shouldReportPartialResults = false
            self.request = request
            let input = engine.inputNode
            let format = input.outputFormat(forBus: 0)
            input.installTap(onBus: 0, bufferSize: 1024, format: format) { buffer, _ in
                request.append(buffer)
            }
            engine.prepare()
            try engine.start()
            listening = true
            status = "Listening once with on-device speech…"
            task = recognizer?.recognitionTask(with: request) { result, error in
                if let result, result.isFinal {
                    let heard = result.bestTranscription.formattedString
                    let command = VoiceCommand.parse(heard)
                    DispatchQueue.main.async {
                        self.onTranscript?(heard)
                        self.onCommand?(command)
                        self.finish("Heard: \(heard) · command: \(command.rawValue)")
                    }
                } else if let error {
                    DispatchQueue.main.async {
                        self.finish("Speech recognition ended: \(error.localizedDescription). No command was executed.")
                    }
                }
            }
        } catch {
            finish("Speech recognition could not start: \(error.localizedDescription)")
        }
    }

    func stop() {
        finish("Listening and speech stopped.")
    }

    private func finish(_ message: String) {
        task?.cancel()
        task = nil
        request?.endAudio()
        request = nil
        if engine.isRunning {
            engine.stop()
        }
        engine.inputNode.removeTap(onBus: 0)
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        listening = false
        status = message
    }
}

final class Speaker: NSObject, ObservableObject, AVSpeechSynthesizerDelegate {
    private let synthesizer = AVSpeechSynthesizer()
    var onFinish: (() -> Void)?
    @Published var selectedVoiceIdentifier = UserDefaults.standard.string(forKey: "zoe_voice")

    var voices: [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices().filter { $0.language.hasPrefix("en") }
    }

    func selectVoice(_ voice: AVSpeechSynthesisVoice) {
        selectedVoiceIdentifier = voice.identifier
        UserDefaults.standard.set(voice.identifier, forKey: "zoe_voice")
    }

    override init() {
        super.init()
        synthesizer.delegate = self
    }

    func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        onFinish?()
    }

    func speak(_ text: String) {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        let utterance = AVSpeechUtterance(string: String(text.prefix(1200)))
        utterance.voice = voices.first(where: { $0.identifier == selectedVoiceIdentifier })
            ?? AVSpeechSynthesisVoice(language: "en-US")
        synthesizer.speak(utterance)
    }

    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
    }
}
