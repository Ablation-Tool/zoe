package research.zoetic.zoe;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.Locale;

public final class MainActivity extends ComponentActivity {
    private static final int CAMERA_PERMISSION = 41;
    private static final int MICROPHONE_PERMISSION = 42;
    private static final String GEMINI_PACKAGE = "com.google.android.apps.bard";

    private FrameLayout content;
    private HomeView homeView;
    private View homeButton;
    private GuidedVisionView visionView;
    private VolumeView volumeView;
    private DeviceView deviceView;
    private TextToSpeech textToSpeech;
    private SpeechRecognizer speechRecognizer;
    private boolean listening;
    private boolean speechStopRequested;
    private boolean inspectAfterPermission;
    private boolean comfortMode;
    private String visible = "home";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = Ui.vertical(this);
        homeView = new HomeView(this);
        root.addView(homeView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));
        homeButton = Ui.button(this, "‹ Zoe home", view -> showHome());
        homeButton.setVisibility(View.GONE);
        root.addView(homeButton);
        content = new FrameLayout(this);
        content.setVisibility(View.GONE);
        root.addView(content, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));
        root.addView(Ui.text(this,
                "Offline-first. Optional model services and external apps may use network under their own permissions.",
                12, Ui.MUTED));
        setContentView(root);

        visionView = new GuidedVisionView(this);
        volumeView = new VolumeView(this);
        deviceView = new DeviceView(this);
        textToSpeech = new TextToSpeech(this, status -> {
        });
        setComfortMode(getPreferences(MODE_PRIVATE).getBoolean("comfort", false));
        if (savedInstanceState != null) {
            visible = savedInstanceState.getString("visible", "home");
        }
        switch (visible) {
            case "vision" -> showVision();
            case "volume" -> showVolume();
            case "device" -> showDevice();
            default -> showHome();
        }
    }

    private void show(FrameLayout frame, View view, String identifier) {
        if (!"vision".equals(identifier) && "vision".equals(visible)) {
            visionView.pauseCamera();
        }
        visible = identifier;
        homeView.setVisibility(View.GONE);
        homeButton.setVisibility(View.VISIBLE);
        content.setVisibility(View.VISIBLE);
        content.removeAllViews();
        content.addView(view);
    }

    final void showHome() {
        if ("vision".equals(visible)) {
            visionView.pauseCamera();
        }
        visible = "home";
        content.removeAllViews();
        content.setVisibility(View.GONE);
        homeButton.setVisibility(View.GONE);
        homeView.setVisibility(View.VISIBLE);
    }

    final void showVision() {
        show(content, visionView, "vision");
    }

    final void showVolume() {
        show(content, volumeView, "volume");
    }

    final void showDevice() {
        show(content, deviceView, "device");
        deviceView.refresh();
    }

    @Override
    public void onBackPressed() {
        if (!"home".equals(visible)) {
            showHome();
        } else {
            super.onBackPressed();
        }
    }

    boolean isComfortMode() {
        return comfortMode;
    }

    void setComfortMode(boolean enabled) {
        comfortMode = enabled;
        getWindow().setWindowAnimations(enabled ? 0 : android.R.style.Animation_Activity);
        if (textToSpeech != null) {
            textToSpeech.setSpeechRate(enabled ? 0.92f : 1.0f);
        }
        getPreferences(MODE_PRIVATE).edit().putBoolean("comfort", enabled).apply();
        if (deviceView != null) {
            deviceView.refresh();
        }
    }

    @Override
    protected void onSaveInstanceState(Bundle state) {
        state.putString("visible", visible);
        super.onSaveInstanceState(state);
    }

    void startCamera() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            showVision();
            visionView.startCamera();
        } else {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION);
        }
    }

    void inspectVision() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            inspectAfterPermission = true;
            startCamera();
            return;
        }
        showVision();
        startCamera();
        content.postDelayed(() -> visionView.requestInspection(), 1200);
    }

    void startListening() {
        if (listening) {
            stopListening();
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, MICROPHONE_PERMISSION);
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            visionView.setStatus("No speech-recognition service is available.");
            return;
        }
        speechStopRequested = false;
        destroySpeechRecognizer();
        if (Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            speechRecognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
            visionView.setStatus("On-device speech selected. Listening once…");
        } else {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
            visionView.setStatus("Offline speech preferred; service behavior controls actual processing. Listening once…");
        }
        speechRecognizer.setRecognitionListener(new RecognitionListener() {
            @Override
            public void onReadyForSpeech(Bundle params) {
                listening = true;
            }

            @Override
            public void onBeginningOfSpeech() {
            }

            @Override
            public void onRmsChanged(float rmsdB) {
            }

            @Override
            public void onBufferReceived(byte[] buffer) {
            }

            @Override
            public void onEndOfSpeech() {
                listening = false;
            }

            @Override
            public void onError(int error) {
                listening = false;
                if (!speechStopRequested) {
                    visionView.setStatus("Speech recognition ended with code " + error + ". No command was executed.");
                }
            }

            @Override
            public void onResults(Bundle results) {
                listening = false;
                if (speechStopRequested) {
                    return;
                }
                ArrayList<String> alternatives = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (alternatives == null || alternatives.isEmpty()) {
                    visionView.setStatus("No speech recognized. No command was executed.");
                    return;
                }
                String heard = alternatives.get(0);
                VoiceCommand command = VoiceCommand.parse(heard);
                visionView.setStatus("Heard: " + heard + " · command: " + command.name());
                handleVoiceCommand(command);
            }

            @Override
            public void onPartialResults(Bundle partialResults) {
            }

            @Override
            public void onEvent(int eventType, Bundle params) {
            }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault())
                .putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, false)
                .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true);
        try {
            speechRecognizer.startListening(intent);
        } catch (RuntimeException error) {
            listening = false;
            visionView.setStatus("Speech recognition could not start: " + error.getMessage());
        }
    }

    private void handleVoiceCommand(VoiceCommand command) {
        switch (command) {
            case INSPECT -> inspectVision();
            case REPEAT -> repeatCurrent();
            case STOP -> stopAllOutput();
            case MEASURE -> {
                showVolume();
                volumeView.measure();
            }
            case VISION -> showVision();
            case VOLUME -> showVolume();
            case DEVICE -> showDevice();
            case GEMINI -> openGemini();
            case UNKNOWN -> visionView.setStatus("No supported command found. Try inspect, repeat, measure, battery, Gemini, or stop.");
        }
    }

    void repeatCurrent() {
        switch (visible) {
            case "volume" -> speak(volumeView.spokenSummary());
            case "device" -> speak("Device field refreshed. " + Build.MODEL + ". Battery and capability details are on screen.");
            default -> speak(visionView.spokenSummary());
        }
    }

    void speak(String text) {
        if (textToSpeech == null || text == null || text.isBlank()) {
            return;
        }
        textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, "zoe-speech");
    }

    void stopListening() {
        speechStopRequested = true;
        if (speechRecognizer != null) {
            speechRecognizer.cancel();
        }
        listening = false;
        visionView.setStatus("Listening cancelled. No command was executed.");
    }

    void stopAllOutput() {
        speechStopRequested = true;
        if (textToSpeech != null) {
            textToSpeech.stop();
        }
        if (speechRecognizer != null) {
            speechRecognizer.cancel();
        }
        listening = false;
        visionView.setStatus("Speech and listening stopped.");
    }

    void shareCurrent() {
        String text = "volume".equals(visible) ? volumeView.shareText() : visionView.shareText();
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, text)
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe observation");
        startActivity(Intent.createChooser(share, "Share Zoe observation"));
    }

    void openGemini() {
        try {
            Intent launch = getPackageManager().getLaunchIntentForPackage(GEMINI_PACKAGE);
            if (launch == null) {
                launch = new Intent(Intent.ACTION_VIEW, Uri.parse("https://gemini.google.com"));
            }
            startActivity(launch);
        } catch (ActivityNotFoundException error) {
            visionView.setStatus("No Gemini app or web browser is available.");
        }
    }

    private void destroySpeechRecognizer() {
        if (speechRecognizer != null) {
            speechRecognizer.destroy();
            speechRecognizer = null;
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        if (requestCode == CAMERA_PERMISSION) {
            if (granted && inspectAfterPermission) {
                inspectAfterPermission = false;
                inspectVision();
            } else if (granted) {
                startCamera();
            } else {
                inspectAfterPermission = false;
                visionView.setStatus("Camera permission was not granted. No camera was opened.");
            }
        } else if (requestCode == MICROPHONE_PERMISSION) {
            if (granted) {
                startListening();
            } else {
                visionView.setStatus("Microphone permission was not granted. No audio was captured.");
            }
        }
    }

    @Override
    protected void onDestroy() {
        destroySpeechRecognizer();
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
        if (visionView != null) {
            visionView.close();
        }
        super.onDestroy();
    }
}
