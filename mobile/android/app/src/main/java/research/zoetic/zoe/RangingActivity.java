package research.zoetic.zoe;

import android.Manifest;
import android.content.Context;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.AudioTrack;
import android.media.MediaRecorder;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.os.VibratorManager;
import android.speech.tts.TextToSpeech;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class RangingActivity extends ComponentActivity implements SensorEventListener {
    private static final int SAMPLE_RATE = 48_000;
    private static final int MICROPHONE_PERMISSION = 91;
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean running = new AtomicBoolean(false);
    private TextView status;
    private TextView report;
    private AudioRecord recorder;
    private AudioTrack track;
    private SensorManager sensors;
    private Sensor accelerometer;
    private double motionSquared;
    private int motionSamples;
    private TextToSpeech speaker;
    private String spoken = "Acoustic Ranging Lab. Start one gentle chirp when ready.";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        android.widget.LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "Acoustic Ranging Lab"));
        content.addView(Ui.text(this,
                "One gentle 2 kHz, 20 ms chirp per tap. Sound-level, motion, and echo candidates remain separate from verified distance.",
                15, Ui.MUTED));
        status = Ui.text(this, "Microphone, speaker, and motion telemetry are idle.", 16, Ui.YELLOW);
        status.setId(R.id.range_status);
        content.addView(status);
        Button ping = Ui.button(this, "Ping once", view -> ping());
        ping.setId(R.id.range_ping);
        Button stop = Ui.button(this, "Stop", view -> stopRanging());
        stop.setId(R.id.range_stop);
        content.addView(Ui.buttonRow(this, ping, stop));
        content.addView(Ui.buttonRow(this,
                Ui.button(this, "Speak result", view -> {
                    if (speaker != null) {
                        speaker.speak(spoken, TextToSpeech.QUEUE_FLUSH, null, "zoe-range");
                    }
                }),
                Ui.button(this, "Share result", view -> {
                    android.content.Intent share = new android.content.Intent(android.content.Intent.ACTION_SEND)
                            .setType("text/plain")
                            .putExtra(android.content.Intent.EXTRA_TEXT, report.getText().toString());
                    startActivity(android.content.Intent.createChooser(share, "Share acoustic observation"));
                })));
        report = Ui.text(this,
                "No acoustic observation yet. Results include raw timing, a candidate distance if a second correlation peak appears, and an explicit uncalibrated boundary.",
                17, Ui.TEXT);
        report.setId(R.id.range_report);
        report.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        content.addView(report);
        content.addView(Ui.text(this,
                "dBFS is not calibrated sound-pressure level. Motion RMS is not displacement. Echo candidates are not certified obstacle detection or a blindness-safety system. Text, optional speech, and vibration provide alternative feedback.",
                13, Ui.MUTED));
        sensors = (SensorManager) getSystemService(Context.SENSOR_SERVICE);
        accelerometer = sensors == null ? null : sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
        speaker = new TextToSpeech(this, result -> { });
    }

    private void ping() {
        if (!running.compareAndSet(false, true)) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            running.set(false);
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, MICROPHONE_PERMISSION);
            return;
        }
        status.setText("Recording one second and playing one gentle chirp…");
        motionSquared = 0;
        motionSamples = 0;
        if (accelerometer != null) {
            sensors.registerListener(this, accelerometer, SensorManager.SENSOR_DELAY_GAME);
        }
        executor.execute(this::capture);
    }

    private void capture() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            running.set(false);
            runOnUiThread(() -> status.setText("Microphone permission was not granted. No audio was captured."));
            return;
        }
        short[] reference = AcousticRanging.chirp(SAMPLE_RATE, 2000, 0.020, 0.08);
        short[] recorded = new short[SAMPLE_RATE];
        try {
            int minimum = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            recorder = new AudioRecord(MediaRecorder.AudioSource.MIC, SAMPLE_RATE,
                    AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, Math.max(minimum * 4, 8192));
            recorder.startRecording();
            track = new AudioTrack(android.media.AudioManager.STREAM_MUSIC, SAMPLE_RATE,
                    AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT,
                    reference.length, AudioTrack.MODE_STATIC);
            track.write(reference, 0, reference.length);
            track.play();
            int offset = 0;
            while (running.get() && offset < recorded.length) {
                int count = recorder.read(recorded, offset, recorded.length - offset);
                if (count < 0) {
                    throw new IllegalStateException("AudioRecord error " + count);
                }
                offset += count;
            }
            AcousticRanging.Measurement measurement = AcousticRanging.analyze(recorded, reference, SAMPLE_RATE);
            double motionRms = motionSamples == 0 ? 0 : Math.sqrt(motionSquared / motionSamples);
            runOnUiThread(() -> publish(measurement, motionRms));
        } catch (SecurityException error) {
            runOnUiThread(() -> {
                status.setText("Microphone permission was revoked. No audio is being captured.");
                running.set(false);
            });
        } catch (Exception error) {
            runOnUiThread(() -> {
                status.setText("Acoustic capture failed: " + error.getMessage());
                running.set(false);
            });
        } finally {
            releaseAudio();
        }
    }

    private void publish(AcousticRanging.Measurement measurement, double motionRms) {
        running.set(false);
        StringBuilder text = new StringBuilder(String.format(Locale.US,
                "Sound level: %.1f dBFS (not SPL)\nMotion RMS: %.4f m/s² (not displacement)\n",
                measurement.rmsDbfs, motionRms));
        if (measurement.directLagSeconds != null) {
            text.append(String.format(Locale.US, "Direct-path correlation lag: %.3f ms\n",
                    measurement.directLagSeconds * 1000));
        }
        if (measurement.echoLagSeconds != null) {
            text.append(String.format(Locale.US,
                    "Echo candidate: %.3f ms beyond direct path\nCandidate distance: %.2f m at 343 m/s\nCorrelation: %.2f\n\nUNCALIBRATED: this is a timing-derived candidate, not verified distance or safe navigation guidance.",
                    measurement.echoLagSeconds * 1000, measurement.candidateDistanceMeters, measurement.correlation));
            vibrate(new long[]{0, 45});
        } else {
            text.append("\nNo second correlation peak above 0.25 was found. No distance is reported.\n\nThe result may reflect device latency, direct acoustic coupling, noise, or no usable echo.");
            vibrate(new long[]{0, 35, 80, 35});
        }
        text.append("\n\nNo audio was saved by Zoe.");
        report.setText(text.toString());
        spoken = text.toString();
        status.setText("Acoustic observation complete. Text, speech, and vibration are available.");
    }

    private void vibrate(long[] timings) {
        if (Build.VERSION.SDK_INT < 26) {
            return;
        }
        Vibrator vibrator;
        if (Build.VERSION.SDK_INT >= 31) {
            VibratorManager manager = (VibratorManager) getSystemService(Context.VIBRATOR_MANAGER_SERVICE);
            vibrator = manager == null ? null : manager.getDefaultVibrator();
        } else {
            vibrator = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
        }
        if (vibrator != null && vibrator.hasVibrator()) {
            vibrator.vibrate(VibrationEffect.createWaveform(timings, -1));
        }
    }

    private void releaseAudio() {
        if (recorder != null) {
            try {
                recorder.stop();
            } catch (IllegalStateException ignored) {
            }
            recorder.release();
            recorder = null;
        }
        if (track != null) {
            track.stop();
            track.release();
            track = null;
        }
        if (sensors != null) {
            sensors.unregisterListener(this);
        }
    }

    private void stopRanging() {
        running.set(false);
        releaseAudio();
        if (speaker != null) {
            speaker.stop();
        }
        status.setText("Acoustic Lab stopped. Microphone, speaker, and motion telemetry are idle.");
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        double magnitudeSquared = 0;
        for (float value : event.values) {
            magnitudeSquared += value * value;
        }
        motionSquared += Math.max(0, magnitudeSquared - SensorManager.GRAVITY_EARTH * SensorManager.GRAVITY_EARTH);
        motionSamples++;
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == MICROPHONE_PERMISSION && grantResults.length > 0
                && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
            ping();
        } else if (requestCode == MICROPHONE_PERMISSION) {
            status.setText("Microphone permission was not granted. No audio was captured.");
        }
    }

    @Override
    protected void onPause() {
        stopRanging();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        running.set(false);
        releaseAudio();
        if (speaker != null) {
            speaker.shutdown();
        }
        executor.shutdownNow();
        super.onDestroy();
    }
}
