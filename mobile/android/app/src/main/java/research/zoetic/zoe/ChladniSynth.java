package research.zoetic.zoe;

import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

final class ChladniSynth {
    private static final int SAMPLE_RATE = 44_100;
    private static final double DURATION_SEC = 1.45;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final Object lock = new Object();
    private AudioTrack activeTrack;

    void play(int modeType, int[] modes, int roseSymmetry) {
        final int[] safeModes = modes == null || modes.length < 4 ? new int[]{1, 4, 2, 6} : modes.clone();
        executor.execute(() -> {
            short[] pcm = synthesize(modeType, safeModes, roseSymmetry);
            playPcm(pcm);
        });
    }

    private static short[] synthesize(int modeType, int[] modes, int roseSymmetry) {
        int count = (int) (SAMPLE_RATE * DURATION_SEC);
        short[] samples = new short[count];
        double base = modeType == ChladniPadView.MODE_ROSE_DISC ? 196.0 : 220.0;
        double f1 = clampFreq(base * Math.sqrt((modes[0] * modes[0] + modes[1] * modes[1]) / 5.0));
        double f2 = clampFreq(base * Math.sqrt((modes[2] * modes[2] + modes[3] * modes[3]) / 5.0));
        double f3 = modeType == ChladniPadView.MODE_ROSE_DISC ? clampFreq(base * (roseSymmetry / 12.0 + 0.5)) : 329.63;
        double f4 = f1 * 1.5;

        for (int i = 0; i < count; i++) {
            double t = i / (double) SAMPLE_RATE;
            double attack = Math.min(1.0, t / 0.035);
            double decay = Math.exp(-t * 2.1);
            double env = attack * decay;
            double wave = 0.42 * Math.sin(2.0 * Math.PI * f1 * t)
                    + 0.30 * Math.sin(2.0 * Math.PI * f2 * t)
                    + 0.18 * Math.sin(2.0 * Math.PI * f3 * t)
                    + 0.10 * Math.sin(2.0 * Math.PI * f4 * t);
            samples[i] = (short) Math.round(Short.MAX_VALUE * 0.24 * env * wave);
        }
        return samples;
    }

    private static double clampFreq(double hz) {
        return Math.max(110.0, Math.min(1320.0, hz));
    }

    private void playPcm(short[] samples) {
        AudioTrack track = null;
        try {
            track = new AudioTrack.Builder()
                    .setAudioAttributes(new AudioAttributes.Builder()
                            .setUsage(AudioAttributes.USAGE_MEDIA)
                            .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC)
                            .build())
                    .setAudioFormat(new AudioFormat.Builder()
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                            .setSampleRate(SAMPLE_RATE)
                            .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
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
