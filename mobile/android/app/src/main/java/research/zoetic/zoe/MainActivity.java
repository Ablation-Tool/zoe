package research.zoetic.zoe;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
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
    private TextView homeBarTitle;
    private View geminiBottomBar;
    private GuidedVisionView visionView;
    private VolumeView volumeView;
    private DeviceView deviceView;
    private TextToSpeech textToSpeech;
    private SpeechRecognizer speechRecognizer;
    private Runnable pendingInspect;
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

        // Clean borderless Google-style back bar for embedded views (Vision / Volume / Device)
        LinearLayout backBar = new LinearLayout(this);
        backBar.setOrientation(LinearLayout.HORIZONTAL);
        backBar.setGravity(Gravity.CENTER_VERTICAL);
        backBar.setBackgroundColor(Color.TRANSPARENT);
        backBar.setPadding(Ui.dp(this, 12), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 4));

        android.widget.Button backBtn = Ui.tonalIconButton(this, "←", "Back to Zoe home", view -> showHome());
        LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48));
        backParams.setMargins(0, 0, Ui.dp(this, 10), 0);
        backBar.addView(backBtn, backParams);

        homeBarTitle = Ui.text(this, "", 20f, Ui.TEXT);
        homeBarTitle.setTypeface(Ui.SANS_MEDIUM);
        homeBarTitle.setLetterSpacing(-0.015f);
        homeBarTitle.setPadding(0, 0, 0, 0);
        backBar.addView(homeBarTitle, new LinearLayout.LayoutParams(
                0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));

        ImageView gemHome = Ui.gemHomeButton(this, 30, this::showHome);
        gemHome.setId(R.id.zoe_gem_home);
        LinearLayout.LayoutParams gemHomeLp = new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48));
        gemHomeLp.setMargins(Ui.dp(this, 8), 0, 0, 0);
        backBar.addView(gemHome, gemHomeLp);

        homeButton = backBar;
        homeButton.setVisibility(View.GONE);
        root.addView(homeButton);

        content = new FrameLayout(this);
        content.setVisibility(View.GONE);
        root.addView(content, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));

        // Signature Google Gemini Floating Action Capsule (thumb-reachable ergonomics!)
        geminiBottomBar = buildGeminiCapsule();
        root.addView(geminiBottomBar, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        setContentView(Ui.wrapWithBackdrop(this, root, true));
        Ui.configureEdgeToEdge(this, root);

        visionView = new GuidedVisionView(this);
        volumeView = new VolumeView(this);
        deviceView = new DeviceView(this);
        textToSpeech = new TextToSpeech(this, status -> {
            if (status == TextToSpeech.SUCCESS && textToSpeech != null) {
                textToSpeech.setSpeechRate(comfortMode ? 0.90f : 1.0f);
            }
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
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (!"home".equals(visible)) {
                    showHome();
                } else {
                    setEnabled(false);
                    getOnBackPressedDispatcher().onBackPressed();
                }
            }
        });
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        showHome();
    }

    /**
     * Floating Google Gemini-style bottom action capsule:
     *   [+] Quick actions | "Ask Zoe" (tap to talk/type) | [Eye] Look | [Live wave] Talk now
     * Built with huge >= 48dp targets right in the ergonomic bottom thumb zone.
     */
    private View buildGeminiCapsule() {
        FrameLayout wrapper = new FrameLayout(this);
        wrapper.setBackgroundColor(Color.TRANSPARENT);
        wrapper.setPadding(Ui.dp(this, 16), Ui.dp(this, 6), Ui.dp(this, 16), Ui.dp(this, 14));

        boolean dark = Ui.isDark(this);
        LinearLayout capsule = new LinearLayout(this);
        capsule.setOrientation(LinearLayout.HORIZONTAL);
        capsule.setGravity(Gravity.CENTER_VERTICAL);
        capsule.setMinimumHeight(Ui.dp(this, 64));
        capsule.setPadding(Ui.dp(this, 8), Ui.dp(this, 6), Ui.dp(this, 8), Ui.dp(this, 6));

        GradientDrawable pillBg = new GradientDrawable();
        pillBg.setColor(Ui.panelColor(this));
        pillBg.setCornerRadius(Ui.dp(this, 32));
        pillBg.setStroke(Ui.strokePx(this, 0.8f), Ui.withAlpha(Ui.dividerColor(this), dark ? 140 : 210));
        capsule.setBackground(pillBg);

        // [+] Quick Actions button (SafeConvert, Field kit, Arrange, Google Gemini, Comfort mode)
        ImageView plusBtn = Ui.iconActionButton(
                this,
                R.drawable.ic_zoe_plus,
                Ui.textColor(this),
                Color.TRANSPARENT,
                "More tools and quick actions",
                v -> {
                    v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    homeView.showQuickSheet();
                });
        capsule.addView(plusBtn, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));

        // Center "Ask Zoe" tap zone -> opens Talk with Zoe (voice or typed calm chat)
        TextView prompt = Ui.text(this, "Ask Zoe", 17.5f, Ui.MUTED);
        prompt.setGravity(Gravity.CENTER_VERTICAL);
        prompt.setMinimumHeight(Ui.dp(this, 48));
        prompt.setPadding(Ui.dp(this, 10), 0, Ui.dp(this, 8), 0);
        prompt.setClickable(true);
        prompt.setFocusable(true);
        prompt.setContentDescription("Ask or talk with Zoe");
        prompt.setOnClickListener(v -> {
            v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
            startActivity(new Intent(this, ConversationActivity.class));
        });
        capsule.addView(prompt, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        // Camera / Look icon -> opens Guided vision in one tap
        ImageView lookBtn = Ui.iconActionButton(
                this,
                R.drawable.ic_zoe_vision,
                Ui.textColor(this),
                Color.TRANSPARENT,
                "Open camera to look and read",
                v -> {
                    v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    showVision();
                });
        LinearLayout.LayoutParams lookP = new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48));
        lookP.setMargins(0, 0, Ui.dp(this, 4), 0);
        capsule.addView(lookBtn, lookP);

        // Signature Glowing DeepMind Blue Live Waveform Circle -> Talk with Zoe immediately
        int liveFill = dark ? Color.rgb(30, 58, 122) : Color.rgb(26, 115, 232);
        int liveGlyph = dark ? Color.rgb(210, 227, 252) : Color.WHITE;
        ImageView liveBtn = Ui.iconActionButton(
                this,
                R.drawable.ic_zoe_live,
                liveGlyph,
                liveFill,
                "Start talking with Zoe",
                v -> {
                    v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    startActivity(new Intent(this, ConversationActivity.class));
                });
        capsule.addView(liveBtn, new LinearLayout.LayoutParams(Ui.dp(this, 48), Ui.dp(this, 48)));

        wrapper.addView(capsule, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        return wrapper;
    }

    String currentVisible() {
        return visible;
    }

    private void cancelPendingInspect() {
        if (pendingInspect != null) {
            content.removeCallbacks(pendingInspect);
            pendingInspect = null;
        }
    }

    private void show(FrameLayout frame, View view, String identifier) {
        cancelPendingInspect();
        if (!"vision".equals(identifier) && "vision".equals(visible)) {
            visionView.pauseCamera();
        }
        visible = identifier;
        if (homeBarTitle != null) {
            homeBarTitle.setText("vision".equals(identifier) ? "Guided vision" : "");
        }
        if (geminiBottomBar != null) {
            geminiBottomBar.setVisibility(View.GONE);
        }
        homeView.setVisibility(View.GONE);
        homeButton.setVisibility(View.VISIBLE);
        content.setVisibility(View.VISIBLE);
        content.removeAllViews();
        content.addView(view);
    }

    final void showHome() {
        cancelPendingInspect();
        if ("vision".equals(visible)) {
            visionView.pauseCamera();
        }
        visible = "home";
        content.removeAllViews();
        content.setVisibility(View.GONE);
        homeButton.setVisibility(View.GONE);
        homeView.setVisibility(View.VISIBLE);
        if (geminiBottomBar != null) {
            geminiBottomBar.setVisibility(View.VISIBLE);
        }
        homeView.refreshDynamic();
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

    boolean isComfortMode() {
        return comfortMode;
    }

    void setComfortMode(boolean enabled) {
        comfortMode = enabled;
        getWindow().setWindowAnimations(enabled ? 0 : android.R.style.Animation_Activity);
        if (textToSpeech != null) {
            textToSpeech.setSpeechRate(enabled ? 0.90f : 1.0f);
        }
        getPreferences(MODE_PRIVATE).edit().putBoolean("comfort", enabled).apply();
        if (deviceView != null) {
            deviceView.refresh();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if ("home".equals(visible) && homeView != null) {
            homeView.refreshDynamic();
        } else if ("device".equals(visible) && deviceView != null) {
            deviceView.refresh();
        }
    }

    @Override
    protected void onPause() {
        cancelPendingInspect();
        if ("vision".equals(visible)) {
            visionView.pauseCamera();
        }
        super.onPause();
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
        cancelPendingInspect();
        pendingInspect = () -> {
            pendingInspect = null;
            if ("vision".equals(visible)) {
                visionView.requestInspection();
            }
        };
        content.postDelayed(pendingInspect, 1200);
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
            @Override public void onReadyForSpeech(Bundle params) { listening = true; }
            @Override public void onBeginningOfSpeech() { }
            @Override public void onRmsChanged(float rmsdB) { }
            @Override public void onBufferReceived(byte[] buffer) { }
            @Override public void onEndOfSpeech() { listening = false; }

            @Override
            public void onError(int error) {
                listening = false;
                if (!speechStopRequested) {
                    visionView.setStatus(ConversationActivity.speechErrorLabel(error));
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

            @Override public void onPartialResults(Bundle partialResults) { }
            @Override public void onEvent(int eventType, Bundle params) { }
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
        try {
            startActivity(Intent.createChooser(share, "Share Zoe observation"));
        } catch (ActivityNotFoundException error) {
            visionView.setStatus("No sharing app is available.");
        }
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
        cancelPendingInspect();
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
