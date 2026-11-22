import AVFoundation
import Foundation

/// Zoe's First-Principles On-Device Native Voice Synthesizer (iOS / iPadOS, zero cloud APIs).
///
/// Synthesizes warm soprano Rosenberg-Klatt glottal excitation filtered through a 3-formant
/// vocal tract biquad resonator cascade at 44.1 kHz mono PCM, wrapped in an in-memory RIFF/WAVE
/// buffer played cleanly via `AVAudioPlayer`.
@MainActor
final class ZoeNativeVoice: NSObject, ObservableObject, AVAudioPlayerDelegate {
    static let sampleRate = 44_100
    private var player: AVAudioPlayer?
    private var completion: (() -> Void)?

    private struct FormantFrame {
        let f1: Double
        let f2: Double
        let f3: Double
        let durSec: Double
        let pitchHz: Double
        let voiced: Bool
        let fricative: Bool
    }

    func speak(_ text: String, onDone: (() -> Void)? = nil) {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            onDone?()
            return
        }
        let clipped = String(trimmed.prefix(140))
        let wav = Self.renderWav(frames: Self.textToFrames(clipped), singing: false)
        playWav(wav, onDone: onDone)
    }

    func singZoe(onDone: (() -> Void)? = nil) {
        let notes: [Double] = [261.63, 329.63, 392.00, 329.63, 440.00, 392.00, 329.63, 261.63]
        let vowels: [(Double, Double, Double)] = [
            (450, 880, 2500),
            (290, 2350, 3050),
            (290, 2350, 3050),
            (730, 1180, 2550),
            (730, 1180, 2550),
            (550, 1950, 2600),
            (290, 2350, 3050),
            (320, 920, 2400),
        ]
        let frames = zip(notes, vowels).map { note, v in
            FormantFrame(f1: v.0, f2: v.1, f3: v.2, durSec: 0.28, pitchHz: note, voiced: true, fricative: false)
        }
        let wav = Self.renderWav(frames: frames, singing: true)
        playWav(wav, onDone: onDone)
    }

    func stop() {
        player?.stop()
        player = nil
        completion = nil
    }

    private func playWav(_ wavData: Data, onDone: (() -> Void)?) {
        stop()
        completion = onDone
        do {
            try AVAudioSession.sharedInstance().setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
            try AVAudioSession.sharedInstance().setActive(true)
            let p = try AVAudioPlayer(data: wavData)
            p.delegate = self
            player = p
            if !p.play() {
                finishPlayback()
            }
        } catch {
            finishPlayback()
        }
    }

    nonisolated func audioPlayerDidFinishPlaying(_ player: AVAudioPlayer, successfully flag: Bool) {
        Task { @MainActor in
            self.finishPlayback()
        }
    }

    private func finishPlayback() {
        let done = completion
        completion = nil
        player = nil
        done?()
    }

    private static func textToFrames(_ text: String) -> [FormantFrame] {
        let chars = Array(text.lowercased().prefix(120))
        let count = max(1, chars.count)
        var out: [FormantFrame] = []
        for (idx, c) in chars.enumerated() {
            let progress = count <= 1 ? 0.0 : Double(idx) / Double(count - 1)
            let pitch = 252.0 - 44.0 * progress + 10.0 * sin(progress * Double.pi * 2.0)
            switch c {
            case "a":
                out.append(FormantFrame(f1: 730, f2: 1180, f3: 2550, durSec: 0.085, pitchHz: pitch, voiced: true, fricative: false))
            case "e":
                out.append(FormantFrame(f1: 530, f2: 1880, f3: 2580, durSec: 0.080, pitchHz: pitch, voiced: true, fricative: false))
            case "i", "y":
                out.append(FormantFrame(f1: 280, f2: 2350, f3: 3050, durSec: 0.080, pitchHz: pitch, voiced: true, fricative: false))
            case "o":
                out.append(FormantFrame(f1: 460, f2: 880, f3: 2480, durSec: 0.085, pitchHz: pitch, voiced: true, fricative: false))
            case "u":
                out.append(FormantFrame(f1: 320, f2: 920, f3: 2350, durSec: 0.085, pitchHz: pitch, voiced: true, fricative: false))
            case "s", "z", "f", "h":
                out.append(FormantFrame(f1: 400, f2: 1800, f3: 3800, durSec: 0.042, pitchHz: pitch, voiced: c == "z", fricative: true))
            case "m", "n", "l", "r":
                out.append(FormantFrame(f1: 310, f2: 1300, f3: 2400, durSec: 0.052, pitchHz: pitch * 0.96, voiced: true, fricative: false))
            case " ", ",", ".", "?", "!":
                out.append(FormantFrame(f1: 300, f2: 1200, f3: 2400, durSec: c == " " ? 0.045 : 0.11, pitchHz: pitch, voiced: false, fricative: false))
            default:
                break
            }
        }
        if out.isEmpty {
            out.append(FormantFrame(f1: 460, f2: 880, f3: 2480, durSec: 0.14, pitchHz: 240.0, voiced: true, fricative: false))
        }
        return out
    }

    private static func renderWav(frames: [FormantFrame], singing: Bool) -> Data {
        let sr = Double(sampleRate)
        let totalSamples = frames.reduce(0) { $0 + max(1, Int((($1.durSec) * sr).rounded())) }
        var buf = [Double](repeating: 0.0, count: totalSamples)
        var phase = 0.0
        var noiseState: UInt64 = 20260401
        var y1 = [0.0, 0.0, 0.0]
        var y2 = [0.0, 0.0, 0.0]
        var pos = 0

        let bws = [75.0, 110.0, 160.0]
        let gains = [1.0, 0.58, 0.28]

        for frame in frames {
            let n = max(1, Int((frame.durSec * sr).rounded()))
            let freqs = [frame.f1, frame.f2, frame.f3]
            var a1 = [0.0, 0.0, 0.0]
            var a2 = [0.0, 0.0, 0.0]
            var g0 = [0.0, 0.0, 0.0]
            for k in 0..<3 {
                let r = exp(-Double.pi * bws[k] / sr)
                let w = 2.0 * Double.pi * freqs[k] / sr
                a1[k] = 2.0 * r * cos(w)
                a2[k] = -(r * r)
                g0[k] = (1.0 - r) * gains[k]
            }

            for i in 0..<n where pos < totalSamples {
                let tFrac = Double(i) / Double(n)
                let env = min(1.0, min(tFrac / 0.14, (1.0 - tFrac) / 0.14))
                let vibrato = singing ? (1.0 + 0.014 * sin(2.0 * Double.pi * 5.3 * (Double(pos) / sr))) : 1.0
                let f0 = frame.pitchHz * vibrato
                phase += f0 / sr
                if phase >= 1.0 { phase -= 1.0 }

                var glottal = 0.0
                if frame.voiced {
                    let open = 0.62
                    if phase < open {
                        let p = phase / open
                        glottal = 0.5 * (1.0 - cos(Double.pi * p)) - 0.15 * sin(2.0 * Double.pi * p)
                    } else {
                        let p = (phase - open) / (1.0 - open)
                        glottal = -0.25 * (1.0 - p)
                    }
                }
                noiseState = noiseState &* 6364136223846793005 &+ 1442695040888963407
                let white = (Double(noiseState >> 33) / Double(Int32.max)) - 0.5
                var exc = glottal + (frame.fricative ? 0.35 * white : 0.015 * white)
                if !frame.voiced && !frame.fricative { exc = 0.0 }

                var sample = 0.0
                for k in 0..<3 {
                    let y = g0[k] * exc + a1[k] * y1[k] + a2[k] * y2[k]
                    y2[k] = y1[k]
                    y1[k] = y
                    sample += y
                }
                buf[pos] = sample * env
                pos += 1
            }
        }

        let peak = max(1e-6, buf.reduce(0.0) { max($0, abs($1)) })
        let scale = (Double(Int16.max) * 0.72) / peak
        let dataBytes = totalSamples * 2
        var wav = Data(capacity: 44 + dataBytes)

        func appendU32(_ v: UInt32) {
            var le = v.littleEndian
            withUnsafeBytes(of: &le) { wav.append(contentsOf: $0) }
        }
        func appendU16(_ v: UInt16) {
            var le = v.littleEndian
            withUnsafeBytes(of: &le) { wav.append(contentsOf: $0) }
        }

        wav.append(contentsOf: "RIFF".utf8)
        appendU32(UInt32(36 + dataBytes))
        wav.append(contentsOf: "WAVE".utf8)
        wav.append(contentsOf: "fmt ".utf8)
        appendU32(16)
        appendU16(1)
        appendU16(1)
        appendU32(UInt32(sampleRate))
        appendU32(UInt32(sampleRate * 2))
        appendU16(2)
        appendU16(16)
        wav.append(contentsOf: "data".utf8)
        appendU32(UInt32(dataBytes))

        for v in buf {
            let clamped = max(Double(Int16.min), min(Double(Int16.max), (v * scale).rounded()))
            var sample = Int16(clamped).littleEndian
            withUnsafeBytes(of: &sample) { wav.append(contentsOf: $0) }
        }
        return wav
    }
}
