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
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Zoe Main Entry Activity — engineered for instant cold-start on Pixel 7 and all Android phones:
 *   - Home mounts immediately with zero eager camera/ML/TTS instantiation.
 *   - GuidedVisionView and TextToSpeech initialize lazily on first use.
 */
public final class MainActivity extends ComponentActivity {
    static final String EXTRA_START_VIEW = "zoe_start_view";
    private static final int CAMERA_PERMISSION = 41;
    private static final int MICROPHONE_PERMISSION = 42;
    private static final String GEMINI_PACKAGE = "com.google.android.apps.bard";

    private FrameLayout content;
    private HomeView homeView;
    private View homeButton;
    private TextView homeBarTitle;
    private View geminiBottomBar;
    private GuidedVisionView visionView;
    private TextToSpeech textToSpeech;
    private boolean ttsReady;
    private String pendingSpeech;
    private SpeechRecognizer speechRecognizer;
    private Runnable pendingInspect;
    private boolean listening;
    private boolean speechStopRequested;
    private boolean inspectAfterPermission;
    private boolean comfortMode;
    private String visible = "home";

    private final ActivityResultLauncher<Uri> pickLearnFolderLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocumentTree(), uri -> {
                if (uri != null) {
                    try {
                        getContentResolver().takePersistableUriPermission(
                                uri, Intent.FLAG_GRANT_READ_URI_PERMISSION | Intent.FLAG_GRANT_WRITE_URI_PERMISSION);
                    } catch (SecurityException ignored) {
                    }
                    ZoeLearnQueue.saveDriveTreeUri(this, uri);
                    ZoeLearnQueue.saveDestination(this, ZoeLearnQueue.Destination.GOOGLE_DRIVE);
                    if (visionView != null) {
                        visionView.onLearnFolderPicked(uri);
                    }
                }
            });

    private Uri pendingSystemCaptureUri;

    private final ActivityResultLauncher<Uri> systemTakePhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.TakePicture(), saved -> {
                Uri uri = pendingSystemCaptureUri;
                pendingSystemCaptureUri = null;
                if (Boolean.TRUE.equals(saved) && uri != null) {
                    ensureVisionView().inspectPickedMedia(uri, false);
                }
            });

    private final ActivityResultLauncher<Uri> systemTakeVideoLauncher =
            registerForActivityResult(new ActivityResultContracts.CaptureVideo(), saved -> {
                Uri uri = pendingSystemCaptureUri;
                pendingSystemCaptureUri = null;
                if (Boolean.TRUE.equals(saved) && uri != null) {
                    ensureVisionView().inspectPickedMedia(uri, true);
                }
            });

    private GuidedVisionView ensureVisionView() {
        if (visionView == null) {
            visionView = new GuidedVisionView(this);
        }
        return visionView;
    }

    void launchSystemCameraPhoto() {
        try {
            pendingSystemCaptureUri = ZoeLearnQueue.createTempCaptureUri(this, "zoe_cam", "jpg");
            systemTakePhotoLauncher.launch(pendingSystemCaptureUri);
        } catch (Exception error) {
            ensureVisionView().setStatus("camera app unavailable: " + error.getMessage());
        }
    }

    void launchSystemCameraVideo() {
        try {
            pendingSystemCaptureUri = ZoeLearnQueue.createTempCaptureUri(this, "zoe_vid", "mp4");
            systemTakeVideoLauncher.launch(pendingSystemCaptureUri);
        } catch (Exception error) {
            ensureVisionView().setStatus("video camera unavailable: " + error.getMessage());
        }
    }

    private final ActivityResultLauncher<String[]> pickVisionMediaLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) {
                    String mime = getContentResolver().getType(uri);
                    boolean isVideo = mime != null && mime.startsWith("video/");
                    ensureVisionView().inspectPickedMedia(uri, isVideo);
                }
            });

    void pickVisionMedia() {
        try {
            pickVisionMediaLauncher.launch(new String[]{"image/*", "video/*"});
        } catch (ActivityNotFoundException error) {
            ensureVisionView().setStatus("no gallery picker available on this device");
        }
    }

    void openLiveExplore() {
        Intent intent = new Intent(this, ZoeLiveActivity.class)
                .putExtra(ZoeLiveActivity.EXTRA_AUTO_START_LIVE, true);
        startActivity(intent);
        if (!comfortMode) {
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }

    void openBrainObservatory() {
        openBrainObservatory("", "");
    }

    void openBrainObservatory(String startTab, String focusQuery) {
        Intent intent = new Intent(this, BrainObservatoryActivity.class);
        if (startTab != null && !startTab.isEmpty()) {
            intent.putExtra(BrainObservatoryActivity.EXTRA_START_TAB, startTab);
        }
        if (focusQuery != null && !focusQuery.isEmpty()) {
            intent.putExtra(BrainObservatoryActivity.EXTRA_FOCUS_QUERY, focusQuery);
        }
        startActivity(intent);
        if (!comfortMode) {
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }

    void openChatWithPrompt(String prompt) {
        Intent intent = new Intent(this, ConversationActivity.class);
        if (prompt != null && !prompt.trim().isEmpty()) {
            intent.putExtra(ConversationActivity.EXTRA_INITIAL_PROMPT, prompt.trim());
        }
        startActivity(intent);
        if (!comfortMode) {
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }

    void pickZoeLearnDriveFolder() {
        try {
            pickLearnFolderLauncher.launch(ZoeLearnQueue.savedDriveTreeUri(this));
        } catch (ActivityNotFoundException error) {
            if (visionView != null) {
                visionView.setStatus("no folder picker available. use save to device instead");
            }
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        LinearLayout root = Ui.vertical(this);
        homeView = new HomeView(this);
        root.addView(homeView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));

        // Clean borderless Google-style back bar for Guided Vision
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

        setComfortMode(getPreferences(MODE_PRIVATE).getBoolean("comfort", false));
        if (savedInstanceState != null) {
            visible = savedInstanceState.getString("visible", "home");
        } else if (getIntent() != null && getIntent().hasExtra(EXTRA_START_VIEW)) {
            String requested = getIntent().getStringExtra(EXTRA_START_VIEW);
            if (requested != null && !requested.isEmpty()) {
                visible = requested;
            }
        }
        if ("vision".equals(visible)) {
            showVision();
        } else if ("brain".equals(visible)) {
            showHome();
            openBrainObservatory();
        } else {
            showHome();
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
        String requested = intent == null ? null : intent.getStringExtra(EXTRA_START_VIEW);
        if ("vision".equals(requested)) {
            showVision();
        } else {
            showHome();
        }
    }

    /**
     * Floating Google Gemini-style bottom action capsule:
     *   [+] Quick menu | "Ask Zoe" (Chat) | [Eye] Guided Vision | [Wave] Zoe Explore
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
        capsule.setElevation(Ui.dp(this, 6));

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
            if (!comfortMode) {
                overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
            }
        });
        capsule.addView(prompt, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

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

        int liveFill = dark ? Color.rgb(30, 58, 122) : Color.rgb(26, 115, 232);
        int liveGlyph = dark ? Color.rgb(210, 227, 252) : Color.WHITE;
        ImageView liveBtn = Ui.iconActionButton(
                this,
                R.drawable.ic_zoe_live,
                liveGlyph,
                liveFill,
                "Open Zoe Explore live camera and voice",
                v -> {
                    v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    openLiveExplore();
                });
        Ui.attachPressSpring(liveBtn);
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

    final void showHome() {
        cancelPendingInspect();
        if ("vision".equals(visible) && visionView != null) {
            visionView.pauseCamera();
        }
        visible = "home";
        content.removeAllViews();
        content.setVisibility(View.GONE);
        homeButton.setVisibility(View.GONE);
        homeView.setVisibility(View.VISIBLE);
        if (!comfortMode) {
            homeView.setAlpha(0f);
            homeView.animate().alpha(1f).setDuration(140L).start();
        }
        if (geminiBottomBar != null) {
            geminiBottomBar.setVisibility(View.VISIBLE);
        }
        homeView.refreshDynamic();
    }

    final void showVision() {
        cancelPendingInspect();
        GuidedVisionView gv = ensureVisionView();
        visible = "vision";
        if (homeBarTitle != null) {
            homeBarTitle.setText("Guided Vision");
        }
        if (geminiBottomBar != null) {
            geminiBottomBar.setVisibility(View.GONE);
        }
        homeView.setVisibility(View.GONE);
        homeButton.setVisibility(View.VISIBLE);
        content.setVisibility(View.VISIBLE);
        content.removeAllViews();
        content.addView(gv);
        if (!comfortMode) {
            gv.setAlpha(0f);
            gv.setTranslationY(Ui.dp(this, 10));
            gv.animate().alpha(1f).translationY(0f).setDuration(160L)
                    .setInterpolator(new android.view.animation.DecelerateInterpolator()).start();
        }
    }

    boolean isComfortMode() {
        return comfortMode;
    }

    void setComfortMode(boolean enabled) {
        comfortMode = enabled;
        Ui.setComfortMotionReduced(enabled);
        getWindow().setWindowAnimations(enabled ? 0 : android.R.style.Animation_Activity);
        if (textToSpeech != null) {
            textToSpeech.setSpeechRate(enabled ? 0.90f : 1.0f);
        }
        getPreferences(MODE_PRIVATE).edit().putBoolean("comfort", enabled).apply();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if ("home".equals(visible) && homeView != null) {
            homeView.refreshDynamic();
        }
    }

    @Override
    protected void onPause() {
        cancelPendingInspect();
        if ("vision".equals(visible) && visionView != null) {
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
            ensureVisionView().startCamera();
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
            if ("vision".equals(visible) && visionView != null) {
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
        GuidedVisionView gv = ensureVisionView();
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            gv.setStatus("no speech-recognition service is available");
            return;
        }
        speechStopRequested = false;
        destroySpeechRecognizer();
        if (Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            speechRecognizer = SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
            gv.setStatus("On-device speech selected · Listening once...");
        } else {
            speechRecognizer = SpeechRecognizer.createSpeechRecognizer(this);
            gv.setStatus("Offline speech preferred · Listening once...");
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
                if (!speechStopRequested && visionView != null) {
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
                    ensureVisionView().setStatus("No speech recognized. No command was executed.");
                    return;
                }
                String heard = alternatives.get(0);
                VoiceCommand command = VoiceCommand.parse(heard);
                ensureVisionView().setStatus("Heard: " + heard + " · command: " + command.name());
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
            gv.setStatus("Speech recognition could not start: " + error.getMessage());
        }
    }

    private void handleVoiceCommand(VoiceCommand command) {
        switch (command) {
            case INSPECT -> inspectVision();
            case REPEAT -> repeatCurrent();
            case STOP -> stopAllOutput();
            case MEASURE, VOLUME -> {
                AccessibleVolume.Result r = AccessibleVolume.measure(new double[]{0.55, 0.25, 0.15, 0.05}, 0.08);
                ensureVisionView().setStatus(r.summary() + " · No action was authorized.");
                speak(r.summary());
            }
            case VISION -> showVision();
            case DEVICE -> {
                showVision();
                ensureVisionView().setStatus("Device: " + Build.MODEL + " · ready.");
            }
            case GEMINI -> openGemini();
            case UNKNOWN -> ensureVisionView().setStatus("No supported command found. Try inspect, repeat, measure, battery, Gemini, or stop.");
        }
    }

    void repeatCurrent() {
        speak(ensureVisionView().spokenSummary());
    }

    void speak(String text) {
        if (text == null || text.isBlank()) {
            return;
        }
        if (textToSpeech == null) {
            pendingSpeech = text;
            textToSpeech = new TextToSpeech(this, status -> {
                if (status == TextToSpeech.SUCCESS && textToSpeech != null) {
                    ttsReady = true;
                    textToSpeech.setSpeechRate(comfortMode ? 0.90f : 1.0f);
                    if (pendingSpeech != null) {
                        String toSpeak = pendingSpeech;
                        pendingSpeech = null;
                        textToSpeech.speak(toSpeak, TextToSpeech.QUEUE_FLUSH, null, "zoe-speech");
                    }
                }
            });
            return;
        }
        if (ttsReady) {
            textToSpeech.speak(text, TextToSpeech.QUEUE_FLUSH, null, "zoe-speech");
        } else {
            pendingSpeech = text;
        }
    }

    void stopListening() {
        speechStopRequested = true;
        if (speechRecognizer != null) {
            speechRecognizer.cancel();
        }
        listening = false;
        if (visionView != null) {
            visionView.setStatus("listening cancelled · no command was executed");
        }
    }

    void stopAllOutput() {
        speechStopRequested = true;
        pendingSpeech = null;
        if (textToSpeech != null) {
            textToSpeech.stop();
        }
        if (speechRecognizer != null) {
            speechRecognizer.cancel();
        }
        listening = false;
        if (visionView != null) {
            visionView.setStatus("Speech and listening stopped");
        }
    }

    void shareCurrent() {
        String text = ensureVisionView().shareText();
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_TEXT, text)
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe observation");
        try {
            startActivity(Intent.createChooser(share, "Share Zoe observation"));
        } catch (ActivityNotFoundException error) {
            ensureVisionView().setStatus("No sharing app is available.");
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
            if (visionView != null) {
                visionView.setStatus("No Gemini app or web browser is available.");
            }
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
                ensureVisionView().setStatus("Camera permission was not granted. No camera was opened.");
            }
        } else if (requestCode == MICROPHONE_PERMISSION) {
            if (granted) {
                startListening();
            } else {
                ensureVisionView().setStatus("Microphone permission was not granted. No audio was captured.");
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
