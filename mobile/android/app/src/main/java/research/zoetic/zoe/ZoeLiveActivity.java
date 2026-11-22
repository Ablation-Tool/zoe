package research.zoetic.zoe;

import android.Manifest;
import android.animation.ValueAnimator;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.os.Bundle;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.animation.LinearInterpolator;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Live — Calm Voice & Optional Live Camera Orb (v0.6.0-beta).
 *
 *   - Full-screen breathing GEM audio-reactive orb with 4 visual states (Idle, Listening, Thinking, Speaking)
 *   - Tap the orb anytime for barge-in interrupt & live speaking
 *   - Optional Live Camera sight (`Camera: off/on`, strictly OFF until tapped!) with 1-tap "Look & Discuss"
 *   - Hybrid routing: Cloud SSE (if keyed) -> Zoe Local 1.5B (if installed) -> Zoe Stem (<5ms),
 *     plus optional Live Web citations and Zoe's 44.1 kHz Native Voice synth.
 */
public final class ZoeLiveActivity extends ComponentActivity {
    private static final int PERM_REQ = 84;

    private enum OrbState {
        IDLE,
        LISTENING,
        THINKING,
        SPEAKING
    }

    private final ExecutorService executor = Executors.newCachedThreadPool();
    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private OnDeviceLlmEngine localLlm;
    private final List<ChatHistoryStore.ChatMessage> sessionHistory = new ArrayList<>();

    private LiveOrbView orbView;
    private TextView stateBadge;
    private TextView captionView;
    private PreviewView cameraPreview;
    private FrameLayout cameraCard;
    private Button cameraToggleBtn;
    private Button lookNowBtn;
    private Button webToggleBtn;
    private Button hiZoeToggleBtn;
    private Button voiceModeBtn;
    private Button listenBtn;

    private ProcessCameraProvider cameraProvider;
    private TextToSpeech tts;
    private SpeechRecognizer recognizer;
    private boolean ttsReady;
    private boolean cameraOn;
    private boolean webOn;
    private boolean hiZoeWakeMode;
    private boolean useNativeVoice;
    private boolean callActive;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        brain = new ZoeBrainEngine(this);
        nativeVoice = new ZoeNativeVoice();
        localLlm = new OnDeviceLlmEngine(this);

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        LinearLayout header = Ui.vertical(this);
        header.setBackgroundColor(Color.TRANSPARENT);
        header.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 4));
        header.addView(Ui.topBar(this, "Zoe Explore", "Live Voice · 'Hi Zoe' · Optional Camera"));

        // Top quick toggles (Camera, Web & 'Hi Zoe' strictly OFF until tapped!)
        LinearLayout toggles = new LinearLayout(this);
        toggles.setOrientation(LinearLayout.HORIZONTAL);
        toggles.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));
        cameraToggleBtn = chipButton("Camera: off", v -> toggleCamera());
        cameraToggleBtn.setId(R.id.live_camera_toggle);
        hiZoeToggleBtn = chipButton("Hi Zoe: off", v -> toggleHiZoeMode());
        hiZoeToggleBtn.setId(R.id.live_hizoe_toggle);
        webToggleBtn = chipButton("Web: off", v -> toggleWeb());
        webToggleBtn.setId(R.id.live_web_toggle);
        voiceModeBtn = chipButton("Voice: OS", v -> toggleVoiceEngine());
        voiceModeBtn.setId(R.id.live_voice_toggle);
        for (Button b : new Button[]{cameraToggleBtn, hiZoeToggleBtn, webToggleBtn, voiceModeBtn}) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 40), 1f);
            lp.setMargins(0, 0, Ui.dp(this, 4), 0);
            toggles.addView(b, lp);
        }
        header.addView(toggles);
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout center = Ui.vertical(this);
        center.setGravity(Gravity.CENTER_HORIZONTAL);
        center.setPadding(Ui.dp(this, 18), Ui.dp(this, 8), Ui.dp(this, 18), Ui.dp(this, 12));

        // Optional Live Camera Preview Card (hidden & OFF until tapped!)
        cameraCard = new FrameLayout(this);
        cameraCard.setBackground(Ui.cardBackground(this, 24));
        cameraCard.setPadding(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
        cameraPreview = new PreviewView(this);
        cameraPreview.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        cameraCard.addView(cameraPreview, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 210)));
        cameraCard.setVisibility(View.GONE);
        LinearLayout.LayoutParams camLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 222));
        camLp.setMargins(0, 0, 0, Ui.dp(this, 12));
        center.addView(cameraCard, camLp);

        lookNowBtn = Ui.primaryButton(this, "Look & Discuss This View", Ui.CYAN, v -> captureAndDiscussCamera());
        lookNowBtn.setId(R.id.live_look_button);
        lookNowBtn.setVisibility(View.GONE);
        center.addView(lookNowBtn);

        // Breathing GEM Audio Orb (tap anytime to talk or barge-in!)
        orbView = new LiveOrbView(this);
        orbView.setId(R.id.live_orb_view);
        orbView.setContentDescription("Zoe Live orb. Tap to speak or interrupt.");
        orbView.setClickable(true);
        orbView.setFocusable(true);
        orbView.setOnClickListener(v -> onOrbTapped());
        LinearLayout.LayoutParams orbLp = new LinearLayout.LayoutParams(Ui.dp(this, 220), Ui.dp(this, 220));
        orbLp.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));
        center.addView(orbView, orbLp);

        stateBadge = Ui.text(this, "TAP ORB TO TALK · MIC & CAMERA START OFF", 12.5f, Ui.COBALT);
        stateBadge.setId(R.id.live_state_badge);
        stateBadge.setTypeface(Ui.SANS_MEDIUM);
        stateBadge.setGravity(Gravity.CENTER);
        center.addView(stateBadge);

        captionView = Ui.text(this,
                "Hi, I'm Zoe. Tap the orb or Talk Now whenever you want to have a calm hands-free conversation — or turn on Camera to show me something.",
                16f, Ui.TEXT);
        captionView.setId(R.id.live_caption_view);
        captionView.setGravity(Gravity.CENTER);
        captionView.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        captionView.setBackground(Ui.cardBackground(this, 22));
        LinearLayout.LayoutParams capLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        capLp.setMargins(0, Ui.dp(this, 12), 0, Ui.dp(this, 12));
        center.addView(captionView, capLp);

        // Quick spoken conversation starters (accessible even without mic!)
        LinearLayout quickChips = new LinearLayout(this);
        quickChips.setOrientation(LinearLayout.HORIZONTAL);
        quickChips.setGravity(Gravity.CENTER);
        Button q1 = chipButton("Tell me a calm fact", v -> processSpokenPrompt("Tell me one calm, fascinating science fact in two sentences."));
        Button q2 = chipButton("Sing Zoe", v -> {
            setOrbState(OrbState.SPEAKING, "SINGING ZOE (44.1 kHz OFFLINE)");
            captionView.setText("Singing Zoe's native Rosenberg-Klatt soprano melody (zero cloud APIs)...");
            nativeVoice.singZoe(() -> runOnUiThread(() -> setOrbState(OrbState.IDLE, "READY · TAP ORB TO TALK")));
        });
        LinearLayout.LayoutParams qLp = new LinearLayout.LayoutParams(0, Ui.dp(this, 42), 1f);
        qLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        quickChips.addView(q1, qLp);
        quickChips.addView(q2, new LinearLayout.LayoutParams(0, Ui.dp(this, 42), 1f));
        center.addView(quickChips);

        scroll.addView(center);
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Bottom live controls
        LinearLayout dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        dock.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 14));
        listenBtn = Ui.primaryButton(this, "Talk Now", Ui.COBALT, v -> onOrbTapped());
        listenBtn.setId(R.id.live_talk_button);
        Button stopBtn = Ui.button(this, "End / Mute", Ui.RUBY, v -> stopLiveCall());
        stopBtn.setId(R.id.live_stop_button);
        LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        dlp.setMargins(0, 0, Ui.dp(this, 8), 0);
        dock.addView(listenBtn, dlp);
        dock.addView(stopBtn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(dock);

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);
        initTts();
    }

    private Button chipButton(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(12.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setTextColor(Ui.textColor(this));
        b.setBackground(Ui.outlinedPillDrawable(this, Ui.panelColor(this), Ui.dividerColor(this), Ui.primaryAccent(this), 20));
        b.setStateListAnimator(null);
        b.setOnClickListener(listener);
        return b;
    }

    private void initTts() {
        tts = new TextToSpeech(this, st -> {
            ttsReady = st == TextToSpeech.SUCCESS;
            if (ttsReady) {
                tts.setLanguage(Locale.US);
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override
                    public void onStart(String utteranceId) {
                    }

                    @Override
                    public void onDone(String utteranceId) {
                        runOnUiThread(() -> {
                            if (callActive && !isFinishing() && !isDestroyed()) {
                                startListeningOnce();
                            } else {
                                setOrbState(OrbState.IDLE, "READY · TAP ORB TO TALK");
                            }
                        });
                    }

                    @Override
                    public void onError(String utteranceId) {
                        runOnUiThread(() -> setOrbState(OrbState.IDLE, "READY · TAP ORB TO TALK"));
                    }
                });
            }
        });
    }

    private void toggleHiZoeMode() {
        hiZoeWakeMode = !hiZoeWakeMode;
        hiZoeToggleBtn.setText(hiZoeWakeMode ? "Hi Zoe: on" : "Hi Zoe: off");
        if (hiZoeWakeMode) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                hiZoeWakeMode = false;
                hiZoeToggleBtn.setText("Hi Zoe: off");
                ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, PERM_REQ);
                return;
            }
            callActive = true;
            setOrbState(OrbState.LISTENING, "WAITING FOR 'HI ZOE' · VISIBLE OPT-IN");
            captionView.setText("\"Hi Zoe\" hangout mode is active. Say \"Hi Zoe\" (or \"Hi Zoe, ...\") anytime — tap End / Mute to turn off.");
            startListeningOnce();
        } else {
            stopAudioOnly();
            setOrbState(OrbState.IDLE, "HI ZOE OFF · TAP ORB TO TALK");
            captionView.setText("\"Hi Zoe\" listener turned off. Microphone is idle.");
        }
    }

    private void toggleWeb() {
        webOn = !webOn;
        webToggleBtn.setText(webOn ? "Web: on" : "Web: off");
        captionView.setText(webOn
                ? "Live Web Grounding ON (zero-key DuckDuckGo + Wikipedia citations)."
                : "Live Web Grounding OFF (100% offline local voice mode).");
    }

    private void toggleVoiceEngine() {
        useNativeVoice = !useNativeVoice;
        voiceModeBtn.setText(useNativeVoice ? "Voice: Zoe 44k" : "Voice: OS");
    }

    private void toggleCamera() {
        if (cameraOn) {
            stopCamera();
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, PERM_REQ);
            return;
        }
        startCamera();
    }

    private void startCamera() {
        ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            try {
                cameraProvider = future.get();
                cameraProvider.unbindAll();
                Preview preview = new Preview.Builder().build();
                preview.setSurfaceProvider(cameraPreview.getSurfaceProvider());
                cameraProvider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview);
                cameraOn = true;
                cameraCard.setVisibility(View.VISIBLE);
                lookNowBtn.setVisibility(View.VISIBLE);
                cameraToggleBtn.setText("Camera: on");
                captionView.setText("Live camera sight active. Point at anything and tap Look & Discuss.");
            } catch (Exception error) {
                captionView.setText("Camera unavailable: " + error.getMessage());
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void stopCamera() {
        cameraOn = false;
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        cameraCard.setVisibility(View.GONE);
        lookNowBtn.setVisibility(View.GONE);
        cameraToggleBtn.setText("Camera: off");
    }

    private void captureAndDiscussCamera() {
        if (!cameraOn) {
            return;
        }
        Bitmap frame = cameraPreview.getBitmap();
        if (frame == null) {
            captionView.setText("Waiting for camera preview frame — try tapping Look & Discuss again.");
            return;
        }
        setOrbState(OrbState.THINKING, "INSPECTING CAMERA FRAME…");
        captionView.setText("Looking at your camera view (offline OCR + labels)…");
        executor.execute(() -> {
            MediaChatHelper.MediaAttachment att = MediaChatHelper.analyzePhotoBitmap(frame);
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            String finalReply;
            if (!geminiKey.isEmpty()) {
                try {
                    finalReply = CloudVisionClient.askVision(
                            geminiKey,
                            MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT
                                    + "\nDescribe what you see calmly in 2 concise sentences for a live voice call. "
                                    + att.offlineReport,
                            att.jpegBytes);
                } catch (Exception fallback) {
                    finalReply = "Here is what I observed offline in your camera view: " + att.offlineReport;
                }
            } else {
                File modelFile = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
                if (modelFile != null) {
                    try {
                        String prompt = OnDeviceLlmEngine.buildChatMlPrompt(
                                "In two warm spoken sentences, summarize what you see from these camera observations: " + att.offlineReport,
                                sessionHistory, "", "");
                        finalReply = localLlm.generateStreaming(modelFile, prompt, null);
                    } catch (Exception ignored) {
                        finalReply = "Offline camera check: " + att.offlineReport;
                    }
                } else {
                    finalReply = "Offline camera check: " + att.offlineReport;
                }
            }
            String spoken = OnDeviceLlmEngine.enforceZoeSovereignty(finalReply);
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) {
                    captionView.setText(spoken);
                    speakResponse(spoken);
                }
            });
        });
    }

    private void onOrbTapped() {
        // Barge-in interrupt if currently speaking
        stopAudioOnly();
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, PERM_REQ);
            return;
        }
        callActive = true;
        startListeningOnce();
    }

    private void startListeningOnce() {
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            setOrbState(OrbState.IDLE, "VOICE RECOGNIZER UNAVAILABLE");
            captionView.setText("Speech recognition service is unavailable on this device. Tap a quick prompt above or use Zoe Chat.");
            return;
        }
        if (recognizer != null) {
            recognizer.destroy();
        }
        recognizer = SpeechRecognizer.createSpeechRecognizer(this);
        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override
            public void onReadyForSpeech(Bundle params) {
                setOrbState(OrbState.LISTENING, "LISTENING · SPEAK NATURALLY");
            }

            @Override
            public void onBeginningOfSpeech() {
            }

            @Override
            public void onRmsChanged(float rmsdB) {
                orbView.setAudioLevel(Math.max(0f, Math.min(1f, (rmsdB + 2f) / 12f)));
            }

            @Override
            public void onBufferReceived(byte[] buffer) {
            }

            @Override
            public void onEndOfSpeech() {
                setOrbState(OrbState.THINKING, "THINKING…");
            }

            @Override
            public void onError(int error) {
                setOrbState(OrbState.IDLE, "TAP ORB TO TALK AGAIN");
                captionView.setText("Paused listening (code " + error + "). Tap the orb anytime to keep talking.");
                callActive = false;
            }

            @Override
            public void onResults(Bundle results) {
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (matches != null && !matches.isEmpty() && !matches.get(0).trim().isEmpty()) {
                    String heard = matches.get(0).trim();
                    if (hiZoeWakeMode) {
                        if (WakeWordDetector.isHiZoeTrigger(heard)) {
                            String trailing = WakeWordDetector.stripWakePrefix(heard);
                            hiZoeWakeMode = false;
                            hiZoeToggleBtn.setText("Hi Zoe: off");
                            if (trailing.isEmpty()) {
                                finishLiveReply("Hi! I'm Zoe — ready to hang out and explore. What are we getting into?");
                            } else {
                                processSpokenPrompt(trailing);
                            }
                        } else if (callActive) {
                            captionView.setText("Listening for \"Hi Zoe\"… (heard: \"" + heard + "\")");
                            startListeningOnce();
                        }
                        return;
                    }
                    processSpokenPrompt(heard);
                } else {
                    setOrbState(OrbState.IDLE, "TAP ORB TO TALK");
                }
            }

            @Override
            public void onPartialResults(Bundle partialResults) {
                ArrayList<String> partial = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (partial != null && !partial.isEmpty()) {
                    captionView.setText("You: " + partial.get(0));
                }
            }

            @Override
            public void onEvent(int eventType, Bundle params) {
            }
        });
        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, !webOn);
        recognizer.startListening(intent);
        setOrbState(OrbState.LISTENING, "LISTENING…");
    }

    private void processSpokenPrompt(String spoken) {
        if (ConversationResponse.isStop(spoken)) {
            stopLiveCall();
            return;
        }
        sessionHistory.add(new ChatHistoryStore.ChatMessage("user", spoken, "YOU", "", 0));
        captionView.setText("You: \"" + spoken + "\"\n\nThinking…");
        setOrbState(OrbState.THINKING, "ZOE IS THINKING…");

        String lower = spoken.toLowerCase(Locale.US);
        boolean identity = lower.contains("who are you") || lower.contains("who built you")
                || lower.contains("alibaba") || lower.contains("are you zoe");
        if (identity) {
            String ans = brain.respond(spoken).reply;
            finishLiveReply(ans);
            return;
        }

        executor.execute(() -> {
            WebSearchClient.SearchResult webRes = webOn ? WebSearchClient.search(spoken) : null;
            String webCtx = (webRes != null && webRes.hasSources()) ? webRes.formatContextForPrompt(700) : "";

            MultiAiClient.Provider activeCloud = MultiAiClient.activeProvider(this);
            String cloudKey = MultiAiClient.savedKey(this, activeCloud);
            if (!cloudKey.isEmpty()) {
                try {
                    String reply = MultiAiClient.askStreaming(
                            this, activeCloud, spoken, sessionHistory, "", webCtx, webOn,
                            partial -> runOnUiThread(() -> {
                                if (!isFinishing() && !isDestroyed()) {
                                    captionView.setText(partial);
                                }
                            }));
                    runOnUiThread(() -> finishLiveReply(reply));
                    return;
                } catch (Exception ignored) {
                }
            }
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (localModel != null) {
                try {
                    String chatMl = OnDeviceLlmEngine.buildChatMlPrompt(spoken, sessionHistory, "", webCtx);
                    String reply = localLlm.generateStreaming(localModel, chatMl, (partial, done) ->
                            runOnUiThread(() -> {
                                if (!isFinishing() && !isDestroyed() && !partial.isEmpty()) {
                                    captionView.setText(partial);
                                }
                            }));
                    runOnUiThread(() -> finishLiveReply(reply));
                    return;
                } catch (Exception ignored) {
                }
            }
            String fallback = (webRes != null && webRes.hasSources())
                    ? webRes.formatFallbackAnswer()
                    : brain.respond(spoken).reply;
            runOnUiThread(() -> finishLiveReply(fallback));
        });
    }

    private void finishLiveReply(String reply) {
        if (isFinishing() || isDestroyed()) {
            return;
        }
        String clean = reply == null || reply.trim().isEmpty() ? "I'm here and listening." : reply.trim();
        sessionHistory.add(new ChatHistoryStore.ChatMessage("zoe", clean, "ZOE LIVE", "", 0));
        captionView.setText(clean);
        speakResponse(clean);
    }

    private void speakResponse(String text) {
        setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING · TAP ORB TO INTERRUPT");
        if (useNativeVoice) {
            nativeVoice.speak(text, () -> runOnUiThread(() -> {
                if (callActive && !isFinishing() && !isDestroyed()) {
                    startListeningOnce();
                } else {
                    setOrbState(OrbState.IDLE, "READY · TAP ORB TO TALK");
                }
            }));
        } else if (ttsReady && tts != null) {
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "zoe-live-" + System.currentTimeMillis());
        } else {
            setOrbState(OrbState.IDLE, "READY · TAP ORB TO TALK");
        }
    }

    private void stopAudioOnly() {
        if (recognizer != null) {
            try {
                recognizer.stopListening();
                recognizer.cancel();
            } catch (Exception ignored) {
            }
        }
        if (tts != null) {
            tts.stop();
        }
        nativeVoice.stop();
    }

    private void stopLiveCall() {
        callActive = false;
        hiZoeWakeMode = false;
        hiZoeToggleBtn.setText("Hi Zoe: off");
        stopAudioOnly();
        stopCamera();
        setOrbState(OrbState.IDLE, "EXPLORE PAUSED · MIC & CAMERA OFF");
        captionView.setText("Zoe Explore paused. Both microphone and camera are completely off.");
    }

    private void setOrbState(OrbState state, String label) {
        orbView.setOrbState(state);
        stateBadge.setText(label);
        listenBtn.setText(state == OrbState.LISTENING ? "Listening…" : "Talk Now");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        callActive = false;
        stopAudioOnly();
        stopCamera();
        if (recognizer != null) {
            recognizer.destroy();
        }
        if (tts != null) {
            tts.shutdown();
        }
        localLlm.close();
        executor.shutdownNow();
    }

    /**
     * Smooth 60fps GEM Breathing Orb rendered natively on Android Canvas.
     */
    private static final class LiveOrbView extends View {
        private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint ringPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint gemPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final ValueAnimator animator;
        private float phase;
        private float audioLevel;
        private OrbState state = OrbState.IDLE;

        LiveOrbView(Context context) {
            super(context);
            ringPaint.setStyle(Paint.Style.STROKE);
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(4200L);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setInterpolator(new LinearInterpolator());
            animator.addUpdateListener(a -> {
                phase = (float) a.getAnimatedValue();
                invalidate();
            });
            animator.start();
        }

        void setOrbState(OrbState next) {
            this.state = next == null ? OrbState.IDLE : next;
            invalidate();
        }

        void setAudioLevel(float level) {
            this.audioLevel = level;
            invalidate();
        }

        @Override
        protected void onDetachedFromWindow() {
            super.onDetachedFromWindow();
            animator.cancel();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            float cx = getWidth() / 2f;
            float cy = getHeight() / 2f;
            float maxR = Math.min(cx, cy) * 0.92f;
            float breathe = (float) Math.sin(phase * Math.PI * 2.0);

            int cCore;
            int cOuter;
            switch (state) {
                case LISTENING -> {
                    cCore = Color.rgb(66, 214, 164);
                    cOuter = Color.rgb(74, 144, 255);
                }
                case THINKING -> {
                    cCore = Color.rgb(245, 188, 92);
                    cOuter = Color.rgb(174, 118, 255);
                }
                case SPEAKING -> {
                    cCore = Color.rgb(245, 114, 148);
                    cOuter = Color.rgb(92, 162, 255);
                }
                default -> {
                    cCore = Color.rgb(98, 162, 255);
                    cOuter = Color.rgb(62, 198, 182);
                }
            }

            float radius = maxR * (0.64f + 0.06f * breathe + 0.14f * audioLevel);
            haloPaint.setShader(new RadialGradient(cx, cy, maxR,
                    new int[]{Color.argb(190, Color.red(cCore), Color.green(cCore), Color.blue(cCore)),
                            Color.argb(85, Color.red(cOuter), Color.green(cOuter), Color.blue(cOuter)),
                            Color.TRANSPARENT},
                    new float[]{0.2f, 0.65f, 1.0f}, Shader.TileMode.CLAMP));
            canvas.drawCircle(cx, cy, maxR, haloPaint);

            for (int i = 0; i < 3; i++) {
                float p = (phase + i / 3f) % 1f;
                float r = radius * 0.55f + p * (maxR - radius * 0.55f);
                ringPaint.setStrokeWidth(3f * (1f - p) + 1f);
                ringPaint.setColor(Color.argb((int) ((1f - p) * 165), Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
                canvas.drawCircle(cx, cy, r, ringPaint);
            }

            // Central soft GEM diamond
            gemPaint.setColor(cCore);
            float g = radius * 0.36f;
            Path diamond = new Path();
            diamond.moveTo(cx, cy - g);
            diamond.lineTo(cx + g, cy);
            diamond.lineTo(cx, cy + g);
            diamond.lineTo(cx - g, cy);
            diamond.close();
            canvas.drawPath(diamond, gemPaint);
        }
    }
}
