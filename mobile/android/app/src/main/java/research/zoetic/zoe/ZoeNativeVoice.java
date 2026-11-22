package research.zoetic.zoe;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe's First-Principles On-Device Native Voice Synthesizer (zero PyTorch, zero cloud APIs).
 *
 * Ports Zoe's Rosenberg-Klatt glottal soprano excitation + 3-formant vocal tract resonator
 * cascade (`zoe_voice.py` heritage) straight to Android `AudioTrack` at 44.1 kHz PCM:
 *   - `speak(text)` synthesizes spoken syllables with natural pitch intonation
 *   - `singZoe()` sings Zoe's built-in warm soprano theme with 5.3 Hz vibrato
 *   - `playWavBytes(wav)` plays studio-rendered 44-phoneme Woodworth 3D binaural WAVs
 *     fetched explicitly from `/api/speak` when connected to the workstation.
 */
final class ZoeNativeVoice {
    static final int SAMPLE_RATE = 44_100;

    private static final class FormantFrame {
        final double f1;
        final double f2;
        final double f3;
        final double durSec;
        final double pitchHz;
        final boolean voiced;
        final boolean fricative;

        FormantFrame(double f1, double f2, double f3, double durSec, double pitchHz, boolean voiced, boolean fricative) {
            this.f1 = f1;
            this.f2 = f2;
            this.f3 = f3;
            this.durSec = durSec;
            this.pitchHz = pitchHz;
            this.voiced = voiced;
            this.fricative = fricative;
        }
    }

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Object lock = new Object();
    private AudioTrack activeTrack;

    void speak(String text, Runnable onDone) {
        final String clean = text == null ? "" : text.trim();
        if (clean.isEmpty()) {
            if (onDone != null) {
                onDone.run();
            }
            return;
        }
        executor.execute(() -> {
            short[] pcm = synthesizeSpeech(clean.length() > 140 ? clean.substring(0, 140) : clean);
            playPcm(pcm, SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, onDone);
        });
    }

    void singZoe(Runnable onDone) {
        executor.execute(() -> {
            short[] pcm = synthesizeZoeSong();
            playPcm(pcm, SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, onDone);
        });
    }

    void playWavBytes(byte[] wavBytes, Runnable onDone) {
        if (wavBytes == null || wavBytes.length < 44) {
            if (onDone != null) {
                onDone.run();
            }
            return;
        }
        executor.execute(() -> {
            try {
                ByteBuffer bb = ByteBuffer.wrap(wavBytes).order(ByteOrder.LITTLE_ENDIAN);
                int channels = bb.getShort(22) & 0xFFFF;
                int sampleRate = bb.getInt(24);
                int bitsPerSample = bb.getShort(34) & 0xFFFF;
                if (bitsPerSample != 16 || sampleRate < 8000 || sampleRate > 96000) {
                    if (onDone != null) {
                        onDone.run();
                    }
                    return;
                }
                int dataOffset = findDataChunk(wavBytes);
                if (dataOffset < 0 || dataOffset + 8 >= wavBytes.length) {
                    if (onDone != null) {
                        onDone.run();
                    }
                    return;
                }
                int dataLen = Math.min(bb.getInt(dataOffset + 4), wavBytes.length - (dataOffset + 8));
                short[] pcm = new short[dataLen / 2];
                ByteBuffer.wrap(wavBytes, dataOffset + 8, pcm.length * 2)
                        .order(ByteOrder.LITTLE_ENDIAN)
                        .asShortBuffer()
                        .get(pcm);
                int mask = channels == 2 ? AudioFormat.CHANNEL_OUT_STEREO : AudioFormat.CHANNEL_OUT_MONO;
                playPcm(pcm, sampleRate, mask, onDone);
            } catch (RuntimeException error) {
                if (onDone != null) {
                    onDone.run();
                }
            }
        });
    }

    static short[] synthesizeSpeech(String text) {
        List<FormantFrame> frames = textToFrames(text);
        return renderFrames(frames, false);
    }

    static short[] synthesizeZoeSong() {
        // Gentle soprano melody ("Zoe — clear light — always free") in C major pentatonic
        double[] notes = {261.63, 329.63, 392.00, 329.63, 440.00, 392.00, 329.63, 261.63};
        double[][] vowels = {
                {450, 880, 2500},  // OH ("Zo-")
                {290, 2350, 3050}, // IY ("-e")
                {290, 2350, 3050}, // IY ("clear")
                {730, 1180, 2550}, // AA ("light")
                {730, 1180, 2550}, // AA ("al-")
                {550, 1950, 2600}, // EH ("-ways")
                {290, 2350, 3050}, // IY ("free")
                {320, 920, 2400},  // UW (warm resolve)
        };
        List<FormantFrame> frames = new ArrayList<>();
        for (int i = 0; i < notes.length; i++) {
            frames.add(new FormantFrame(vowels[i][0], vowels[i][1], vowels[i][2], 0.28, notes[i], true, false));
        }
        return renderFrames(frames, true);
    }

    private static List<FormantFrame> textToFrames(String text) {
        List<FormantFrame> out = new ArrayList<>();
        String low = text.toLowerCase(Locale.ROOT);
        int len = Math.min(low.length(), 120);
        for (int i = 0; i < len; i++) {
            char c = low.charAt(i);
            double progress = len <= 1 ? 0.0 : (i / (double) (len - 1));
            // Natural warm soprano speaking declination (252 Hz -> 208 Hz)
            double pitch = 252.0 - 44.0 * progress + 10.0 * Math.sin(progress * Math.PI * 2.0);
            if (c == 'a') {
                out.add(new FormantFrame(730, 1180, 2550, 0.085, pitch, true, false));
            } else if (c == 'e') {
                out.add(new FormantFrame(530, 1880, 2580, 0.080, pitch, true, false));
            } else if (c == 'i' || c == 'y') {
                out.add(new FormantFrame(280, 2350, 3050, 0.080, pitch, true, false));
            } else if (c == 'o') {
                out.add(new FormantFrame(460, 880, 2480, 0.085, pitch, true, false));
            } else if (c == 'u') {
                out.add(new FormantFrame(320, 920, 2350, 0.085, pitch, true, false));
            } else if (c == 's' || c == 'z' || c == 'f' || c == 'h') {
                out.add(new FormantFrame(400, 1800, 3800, 0.042, pitch, c == 'z', true));
            } else if (c == 'm' || c == 'n' || c == 'l' || c == 'r') {
                out.add(new FormantFrame(310, 1300, 2400, 0.052, pitch * 0.96, true, false));
            } else if (c == ' ' || c == ',' || c == '.' || c == '?' || c == '!') {
                out.add(new FormantFrame(300, 1200, 2400, c == ' ' ? 0.045 : 0.11, pitch, false, false));
            }
        }
        if (out.isEmpty()) {
            out.add(new FormantFrame(460, 880, 2480, 0.14, 240.0, true, false));
        }
        return out;
    }

    private static short[] renderFrames(List<FormantFrame> frames, boolean singing) {
        int totalSamples = 0;
        for (FormantFrame f : frames) {
            totalSamples += Math.max(1, (int) Math.round(f.durSec * SAMPLE_RATE));
        }
        double[] buf = new double[totalSamples];
        double phase = 0.0;
        long noiseState = 20260401L;

        // Stateful 3-bandpass biquad resonator cascade (F1, F2, F3)
        double[] y1 = new double[3];
        double[] y2 = new double[3];
        int pos = 0;
        for (FormantFrame frame : frames) {
            int n = Math.max(1, (int) Math.round(frame.durSec * SAMPLE_RATE));
            double[] freqs = {frame.f1, frame.f2, frame.f3};
            double[] bws = {75.0, 110.0, 160.0};
            double[] gains = {1.0, 0.58, 0.28};

            double[] a1 = new double[3];
            double[] a2 = new double[3];
            double[] g0 = new double[3];
            for (int k = 0; k < 3; k++) {
                double r = Math.exp(-Math.PI * bws[k] / SAMPLE_RATE);
                double w = 2.0 * Math.PI * freqs[k] / SAMPLE_RATE;
                a1[k] = 2.0 * r * Math.cos(w);
                a2[k] = -(r * r);
                g0[k] = (1.0 - r) * gains[k];
            }

            for (int i = 0; i < n && pos < totalSamples; i++, pos++) {
                double tFrac = i / (double) n;
                double env = Math.min(1.0, Math.min(tFrac / 0.14, (1.0 - tFrac) / 0.14));
                double vibrato = singing ? (1.0 + 0.014 * Math.sin(2.0 * Math.PI * 5.3 * (pos / (double) SAMPLE_RATE))) : 1.0;
                double f0 = frame.pitchHz * vibrato;
                phase += f0 / SAMPLE_RATE;
                if (phase >= 1.0) {
                    phase -= 1.0;
                }

                // Rosenberg-Klatt smooth glottal pulse (warm soprano voice quality)
                double glottal = 0.0;
                if (frame.voiced) {
                    double open = 0.62;
                    if (phase < open) {
                        double p = phase / open;
                        glottal = 0.5 * (1.0 - Math.cos(Math.PI * p)) - 0.15 * Math.sin(2.0 * Math.PI * p);
                    } else {
                        double p = (phase - open) / (1.0 - open);
                        glottal = -0.25 * (1.0 - p);
                    }
                }
                noiseState = (noiseState * 6364136223846793005L + 1442695040888963407L);
                double white = ((noiseState >> 33) / (double) Integer.MAX_VALUE) - 0.5;
                double exc = glottal + (frame.fricative ? 0.35 * white : 0.015 * white);
                if (!frame.voiced && !frame.fricative) {
                    exc = 0.0;
                }

                double sample = 0.0;
                for (int k = 0; k < 3; k++) {
                    double y = g0[k] * exc + a1[k] * y1[k] + a2[k] * y2[k];
                    y2[k] = y1[k];
                    y1[k] = y;
                    sample += y;
                }
                buf[pos] = sample * env;
            }
        }

        double peak = 1e-6;
        for (double v : buf) {
            peak = Math.max(peak, Math.abs(v));
        }
        short[] pcm = new short[totalSamples];
        double scale = (Short.MAX_VALUE * 0.72) / peak;
        for (int i = 0; i < totalSamples; i++) {
            pcm[i] = (short) Math.max(Short.MIN_VALUE, Math.min(Short.MAX_VALUE, Math.round(buf[i] * scale)));
        }
        return pcm;
    }

    private static int findDataChunk(byte[] wav) {
        int pos = 12;
        while (pos + 8 <= wav.length) {
            if (wav[pos] == 'd' && wav[pos + 1] == 'a' && wav[pos + 2] == 't' && wav[pos + 3] == 'a') {
                return pos;
            }
            int size = ByteBuffer.wrap(wav, pos + 4, 4).order(ByteOrder.LITTLE_ENDIAN).getInt();
            pos += 8 + Math.max(0, size);
        }
        return -1;
    }

    private void playPcm(short[] samples, int sampleRate, int channelMask, Runnable onDone) {
        AudioTrack track = null;
        try {
            track = new AudioTrack.Builder()
                    .setAudioAttributes(new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_ASSISTANT)
                            .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                            .build())
                    .setAudioFormat(new AudioFormat.Builder()
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setSampleRate(sampleRate)
                            .setChannelMask(channelMask)
                            .build())
                    .setTransferMode(AudioTrack.MODE_STATIC)
                    .setBufferSizeInBytes(samples.length * 2)
                    .build();
            track.write(samples, 0, samples.length);
            synchronized (lock) {
                stopLocked();
                activeTrack = track;
                track.play();
            }
        } catch (RuntimeException error) {
            if (track != null) {
                try {
                    track.release();
                } catch (RuntimeException ignored) {
                }
            }
        } finally {
            if (onDone != null) {
                onDone.run();
            }
        }
    }

    void stop() {
        synchronized (lock) {
            stopLocked();
        }
    }

    private void stopLocked() {
        if (activeTrack != null) {
            try {
                if (activeTrack.getPlayState() == AudioTrack.PLAYSTATE_PLAYING) {
                    activeTrack.stop();
                }
            } catch (IllegalStateException ignored) {
            }
            activeTrack.release();
            activeTrack = null;
        }
    }

    void close() {
        stop();
        executor.shutdownNow();
    }
}
