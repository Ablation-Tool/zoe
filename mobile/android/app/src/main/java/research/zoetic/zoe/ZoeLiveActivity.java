package research.zoetic.zoe;

import android.Manifest;
import android.animation.ValueAnimator;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.media.AudioAttributes;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.speech.tts.UtteranceProgressListener;
import android.speech.tts.Voice;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.animation.LinearInterpolator;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.annotation.NonNull;
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
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

/**
 * Zoe Explore — Flawless Gemini-Live-Style Real-Time Voice + Simultaneous Live Camera Orb (v0.6.2-beta).
 *
 * Key architecture:
 *   - Simultaneous Live Camera Sight + Continuous Hands-Free Voice Conversation (talk & look all at once!)
 *   - Pixel on-device SpeechRecognizer (API 31+) with silent auto-rearm on pauses (never aborts on code 6/7!)
 *   - Sentence-level real-time streaming TTS (`QUEUE_ADD`) so Zoe speaks Sentence 1 while Sentence 2 generates
 *   - Turn-ID barge-in cancellation (`AtomicLong`) + post-TTS echo guard (260ms) + background LLM warm-up
 *   - Proper runtime permission flow (`onRequestPermissionsResult`) so 1 tap starts live immediately
 *   - Privacy-first (`CONSTITUTION.md`): both mic and camera start strictly OFF until tapped, and release on stop.
 */
public final class ZoeLiveActivity extends ComponentActivity {
    private static final int PERM_REQ = 84;
    private static final long CAMERA_REFRESH_INTERVAL_MS = 2400L;
    private static final long ECHO_GUARD_MS = 380L;

    private enum OrbState {
        IDLE,
        LISTENING,
        THINKING,
        SPEAKING
    }

    private enum PendingAction {
        NONE,
        START_VOICE_ONLY,
        START_LIVE_PLUS_CAM,
        START_AR_SPACE,
        START_HIZOE,
        START_CAMERA_ONLY
    }

    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final AtomicLong activeTurnId = new AtomicLong(0L);
    private final AtomicLong listenGen = new AtomicLong(0L);
    private final AtomicBoolean cameraAnalysisBusy = new AtomicBoolean(false);
    private final ArExploreBrain arBrain = new ArExploreBrain();

    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private OnDeviceLlmEngine localLlm;
    private final List<ChatHistoryStore.ChatMessage> sessionHistory = new ArrayList<>();

    private LiveOrbView orbView;
    private TextView stateBadge;
    private TextView captionView;
    private ScrollView captionScroll;
    private PreviewView cameraPreview;
    private FrameLayout cameraCard;
    private TextView cameraSightPill;
    private FrameLayout arCard;
    private FrameLayout arSurfaceHost;
    private ZoeArSurfaceView arSurfaceView;
    private TextView arHudPill;
    private Button arToggleBtn;
    private Button arRoamBtn;
    private Button arAskBtn;
    private Button cameraToggleBtn;
    private Button lookNowBtn;
    private Button flipCamBtn;
    private Button webToggleBtn;
    private Button hiZoeToggleBtn;
    private Button voiceModeBtn;
    private Button listenBtn;
    private Button liveCamBtn;

    private ProcessCameraProvider cameraProvider;
    private TextToSpeech tts;
    private SpeechRecognizer recognizer;
    private PendingAction pendingAction = PendingAction.NONE;

    private boolean ttsReady;
    private boolean cameraOn;
    private boolean arModeOn;
    private boolean arRoamEnabled = true;
    private boolean useFrontCamera;
    private boolean webOn;
    private boolean hiZoeWakeMode;
    private boolean useNativeVoice;
    private boolean callActive;
    private boolean preferDeviceRecognizer = true;
    private int consecutiveErrors;
    private volatile OrbState currentOrbState = OrbState.IDLE;

    private volatile String latestCameraReport = "";
    private volatile byte[] latestCameraJpeg;
    private volatile float latestArDistanceMeters = 0f;
    private String pendingSpeechOnReady = "";
    private String lastUserSpoken = "";
    private final AtomicInteger pendingTtsChunks = new AtomicInteger(0);
    private volatile boolean streamCompletedForCurrentTurn = true;

    private final Runnable cameraObserverTick = new Runnable() {
        @Override
        public void run() {
            if (!cameraOn || isFinishing() || isDestroyed()) {
                return;
            }
            captureBackgroundCameraFrame();
            mainHandler.postDelayed(this, CAMERA_REFRESH_INTERVAL_MS);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        brain = new ZoeBrainEngine(this);
        nativeVoice = new ZoeNativeVoice();
        localLlm = new OnDeviceLlmEngine(this);

        // Pre-warm on-device ML Kit singletons, clean-room visual atlas & shared LiteRT LLM + KV-cache in background!
        executor.execute(() -> {
            MediaChatHelper.warmUp();
            VisionPriorStore.loadAll(this);
            VisionPriorStore.loadBaselineAtlas(this);
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (localModel != null) {
                localLlm.warmUp(localModel);
            }
        });

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        LinearLayout header = Ui.vertical(this);
        header.setBackgroundColor(Color.TRANSPARENT);
        header.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 4));
        header.addView(Ui.topBar(this, "Zoe Explore", null));

        // Symmetric 4-pill status strip (16dp outer rails, 8dp inner gutters, uniform 36dp height)
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
        Button[] toggleBtns = new Button[]{cameraToggleBtn, hiZoeToggleBtn, webToggleBtn, voiceModeBtn};
        for (int i = 0; i < toggleBtns.length; i++) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 36), 1f);
            if (i < toggleBtns.length - 1) {
                lp.setMargins(0, 0, Ui.dp(this, 8), 0);
            }
            toggles.addView(toggleBtns[i], lp);
        }
        header.addView(toggles);
        root.addView(header);

        captionScroll = new ScrollView(this);
        captionScroll.setFillViewport(true);
        captionScroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout center = Ui.vertical(this);
        center.setBackgroundColor(Color.TRANSPARENT);
        center.setGravity(Gravity.CENTER_HORIZONTAL);
        center.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 12));

        // Concentric Live Camera Sight Card (20dp outer, 6dp frame, 14dp inner radius — hidden & OFF until tapped!)
        cameraCard = new FrameLayout(this);
        cameraCard.setBackground(Ui.cardBackground(this, 20));
        cameraCard.setPadding(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
        cameraPreview = new PreviewView(this);
        cameraPreview.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        cameraPreview.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        cameraPreview.setOutlineProvider(new android.view.ViewOutlineProvider() {
            @Override
            public void getOutline(View view, android.graphics.Outline outline) {
                outline.setRoundRect(0, 0, view.getWidth(), view.getHeight(), Ui.dp(ZoeLiveActivity.this, 14));
            }
        });
        cameraPreview.setClipToOutline(true);
        cameraCard.addView(cameraPreview, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Subtle live overlay controls inside camera viewfinder (LIVE SIGHT pill + Flip + Look now)
        LinearLayout camOverlayTop = new LinearLayout(this);
        camOverlayTop.setOrientation(LinearLayout.HORIZONTAL);
        camOverlayTop.setGravity(Gravity.CENTER_VERTICAL);
        camOverlayTop.setPadding(Ui.dp(this, 10), Ui.dp(this, 10), Ui.dp(this, 10), 0);

        cameraSightPill = Ui.text(this, "● LIVE SIGHT", 11f, Ui.GREEN);
        cameraSightPill.setTypeface(Ui.SANS_MEDIUM);
        cameraSightPill.setPadding(Ui.dp(this, 10), Ui.dp(this, 5), Ui.dp(this, 10), Ui.dp(this, 5));
        cameraSightPill.setBackground(Ui.tonalPillDrawable(this, Color.argb(185, 14, 18, 26), Ui.GREEN, 14));
        camOverlayTop.addView(cameraSightPill);

        View camSpacer = new View(this);
        camOverlayTop.addView(camSpacer, new LinearLayout.LayoutParams(0, 1, 1f));

        flipCamBtn = chipButton("⇄ Flip", v -> flipCamera());
        flipCamBtn.setId(R.id.live_flip_camera);
        flipCamBtn.setTextColor(Color.WHITE);
        flipCamBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(185, 14, 18, 26), Ui.primaryAccent(this), 16));
        LinearLayout.LayoutParams flipLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32));
        flipLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        camOverlayTop.addView(flipCamBtn, flipLp);

        lookNowBtn = chipButton("Look now", v -> describeLiveViewProactively());
        lookNowBtn.setId(R.id.live_look_button);
        lookNowBtn.setTextColor(Color.WHITE);
        lookNowBtn.setBackground(Ui.tonalPillDrawable(this, Ui.withAlpha(Ui.resolveColor(this, Ui.COBALT), 215), Ui.COBALT, 16));
        camOverlayTop.addView(lookNowBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32)));

        cameraCard.addView(camOverlayTop, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP));
        cameraCard.setVisibility(View.GONE);

        LinearLayout.LayoutParams camLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 236));
        camLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        center.addView(cameraCard, camLp);

        // Concentric ARCore 6DoF 3D Interactive Room Card (20dp outer, 6dp frame, 14dp inner radius)
        arCard = new FrameLayout(this);
        arCard.setBackground(Ui.cardBackground(this, 20));
        arCard.setPadding(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
        arSurfaceHost = new FrameLayout(this);
        arSurfaceHost.setOutlineProvider(new android.view.ViewOutlineProvider() {
            @Override
            public void getOutline(View view, android.graphics.Outline outline) {
                outline.setRoundRect(0, 0, view.getWidth(), view.getHeight(), Ui.dp(ZoeLiveActivity.this, 14));
            }
        });
        arSurfaceHost.setClipToOutline(true);
        arCard.addView(arSurfaceHost, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        LinearLayout arOverlayTop = new LinearLayout(this);
        arOverlayTop.setOrientation(LinearLayout.HORIZONTAL);
        arOverlayTop.setGravity(Gravity.CENTER_VERTICAL);
        arOverlayTop.setPadding(Ui.dp(this, 10), Ui.dp(this, 10), Ui.dp(this, 10), 0);

        arHudPill = Ui.text(this, "● AR 6DoF · Scanning room…", 11f, Ui.GREEN);
        arHudPill.setTypeface(Ui.SANS_MEDIUM);
        arHudPill.setPadding(Ui.dp(this, 10), Ui.dp(this, 5), Ui.dp(this, 10), Ui.dp(this, 5));
        arHudPill.setBackground(Ui.tonalPillDrawable(this, Color.argb(195, 14, 18, 26), Ui.GREEN, 14));
        arOverlayTop.addView(arHudPill);

        View arSpacer = new View(this);
        arOverlayTop.addView(arSpacer, new LinearLayout.LayoutParams(0, 1, 1f));

        arRoamBtn = chipButton("Roam: on", v -> toggleArRoam());
        arRoamBtn.setId(R.id.live_ar_roam_toggle);
        arRoamBtn.setTextColor(Color.WHITE);
        arRoamBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(195, 22, 92, 76), Ui.GREEN, 16));
        LinearLayout.LayoutParams roamLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32));
        roamLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        arOverlayTop.addView(arRoamBtn, roamLp);

        arAskBtn = chipButton("Ask here", v -> {
            if (arSurfaceView != null) {
                arSurfaceView.requestInstantLook();
            }
        });
        arAskBtn.setId(R.id.live_ar_ask_button);
        arAskBtn.setTextColor(Color.WHITE);
        arAskBtn.setBackground(Ui.tonalPillDrawable(this, Ui.withAlpha(Ui.resolveColor(this, Ui.COBALT), 220), Ui.COBALT, 16));
        arOverlayTop.addView(arAskBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32)));
        arCard.addView(arOverlayTop, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.TOP));

        TextView arTapHint = Ui.text(this, "Tap anywhere in your space to call Zoe over", 11.5f, Ui.TEXT);
        arTapHint.setTextColor(Color.WHITE);
        arTapHint.setPadding(Ui.dp(this, 12), Ui.dp(this, 5), Ui.dp(this, 12), Ui.dp(this, 5));
        arTapHint.setBackground(Ui.tonalPillDrawable(this, Color.argb(165, 14, 18, 26), Ui.COBALT, 14));
        FrameLayout.LayoutParams hintLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL);
        hintLp.setMargins(0, 0, 0, Ui.dp(this, 12));
        arCard.addView(arTapHint, hintLp);
        arCard.setVisibility(View.GONE);

        LinearLayout.LayoutParams arLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 348));
        arLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        center.addView(arCard, arLp);

        // Breathing 60fps Audio-Reactive GEM Orb (tap anytime to talk or interrupt mid-sentence!)
        orbView = new LiveOrbView(this);
        orbView.setId(R.id.live_orb_view);
        orbView.setContentDescription("Zoe Explore orb. Tap to speak or interrupt.");
        orbView.setClickable(true);
        orbView.setFocusable(true);
        orbView.setOnClickListener(Ui.withHaptic(v -> onOrbTapped()));
        LinearLayout.LayoutParams orbLp = new LinearLayout.LayoutParams(Ui.dp(this, 212), Ui.dp(this, 212));
        orbLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        center.addView(orbView, orbLp);

        stateBadge = Ui.text(this, "TAP ORB TO TALK · MIC & CAMERA OFF", 12f, Ui.COBALT);
        stateBadge.setId(R.id.live_state_badge);
        stateBadge.setTypeface(Ui.SANS_MEDIUM);
        stateBadge.setGravity(Gravity.CENTER);
        center.addView(stateBadge);

        captionView = Ui.text(this,
                "Hi, I'm Zoe. Tap the orb to talk, or tap Live + Cam to show me around.",
                15.5f, Ui.TEXT);
        captionView.setId(R.id.live_caption_view);
        captionView.setGravity(Gravity.CENTER);
        captionView.setPadding(Ui.dp(this, 18), Ui.dp(this, 16), Ui.dp(this, 18), Ui.dp(this, 16));
        captionView.setBackground(Ui.cardBackground(this, 22));
        LinearLayout.LayoutParams capLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        capLp.setMargins(0, Ui.dp(this, 12), 0, Ui.dp(this, 12));
        center.addView(captionView, capLp);

        // Clean borderless quick actions (✦ AR Space · Calm fact · Sing Zoe)
        LinearLayout quickChips = new LinearLayout(this);
        quickChips.setOrientation(LinearLayout.HORIZONTAL);
        quickChips.setGravity(Gravity.CENTER);
        arToggleBtn = chipButton("✦ AR Space", v -> toggleArSpace());
        arToggleBtn.setId(R.id.live_ar_toggle);
        Button q1 = chipButton("Calm fact", v -> processSpokenPrompt("Tell me a short calming science fact about nature."));
        Button q2 = chipButton("Sing Zoe", v -> {
            long myTurn = activeTurnId.incrementAndGet();
            stopAudioOnly();
            setOrbState(OrbState.SPEAKING, "SINGING ZOE (44.1 kHz OFFLINE)");
            captionView.setText("Singing Zoe's native Rosenberg-Klatt soprano melody (zero cloud APIs)…");
            nativeVoice.singZoe(() -> runOnUiThread(() -> {
                if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                    if (callActive) {
                        scheduleListeningRearm(ECHO_GUARD_MS);
                    } else {
                        setOrbState(OrbState.IDLE, "READY · TAP ORB TO GO LIVE");
                    }
                }
            }));
        });
        LinearLayout.LayoutParams qLp1 = new LinearLayout.LayoutParams(0, Ui.dp(this, 40), 1f);
        qLp1.setMargins(0, 0, Ui.dp(this, 8), 0);
        LinearLayout.LayoutParams qLp2 = new LinearLayout.LayoutParams(0, Ui.dp(this, 40), 1f);
        qLp2.setMargins(0, 0, Ui.dp(this, 8), 0);
        quickChips.addView(arToggleBtn, qLp1);
        quickChips.addView(q1, qLp2);
        quickChips.addView(q2, new LinearLayout.LayoutParams(0, Ui.dp(this, 40), 1f));
        center.addView(quickChips);

        captionScroll.addView(center);
        root.addView(captionScroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Symmetric 3-button Bottom Control Dock (16dp rails, 8dp gutters, equal 1:1:1 visual weight)
        LinearLayout dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        dock.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 16));

        listenBtn = Ui.primaryButton(this, "Talk Now", Ui.COBALT, v -> onOrbTapped());
        listenBtn.setId(R.id.live_talk_button);
        listenBtn.setTextSize(13.5f);

        liveCamBtn = Ui.button(this, "Live + Cam", Ui.CYAN, v -> startLiveVoiceAndCamera());
        liveCamBtn.setId(R.id.live_cam_live_button);
        liveCamBtn.setTextSize(13.5f);

        Button stopBtn = Ui.button(this, "End / Mute", Ui.RUBY, v -> stopLiveCall());
        stopBtn.setId(R.id.live_stop_button);
        stopBtn.setTextSize(13.5f);

        LinearLayout.LayoutParams dlp1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        dlp1.setMargins(0, 0, Ui.dp(this, 8), 0);
        LinearLayout.LayoutParams dlp2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        dlp2.setMargins(0, 0, Ui.dp(this, 8), 0);
        dock.addView(listenBtn, dlp1);
        dock.addView(liveCamBtn, dlp2);
        dock.addView(stopBtn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        root.addView(dock);

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);
        applyResponsiveGeometry(getResources().getConfiguration());
        styleHeaderPills();
        initTts();
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        applyResponsiveGeometry(newConfig);
    }

    private void applyResponsiveGeometry(Configuration cfg) {
        boolean landscape = cfg != null && cfg.orientation == Configuration.ORIENTATION_LANDSCAPE;
        int camH = Ui.dp(this, landscape ? 168 : 236);
        int arH = Ui.dp(this, landscape ? 220 : 348);
        int orbSize = Ui.dp(this, cameraOn ? (landscape ? 92 : 132) : (landscape ? 128 : 204));
        if (cameraCard != null && cameraCard.getLayoutParams() != null) {
            cameraCard.getLayoutParams().height = camH;
            cameraCard.requestLayout();
        }
        if (arCard != null && arCard.getLayoutParams() != null) {
            arCard.getLayoutParams().height = arH;
            arCard.requestLayout();
        }
        if (orbView != null && orbView.getLayoutParams() != null) {
            orbView.getLayoutParams().width = orbSize;
            orbView.getLayoutParams().height = orbSize;
            orbView.requestLayout();
        }
    }

    private Button chipButton(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(11.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMaxLines(1);
        b.setPadding(Ui.dp(this, 8), 0, Ui.dp(this, 8), 0);
        b.setTextColor(Ui.mutedColor(this));
        b.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 17));
        b.setStateListAnimator(null);
        b.setOnClickListener(Ui.withHaptic(listener));
        return b;
    }

    private void styleHeaderPills() {
        styleTogglePill(cameraToggleBtn, cameraOn || arModeOn, Ui.GREEN);
        styleTogglePill(hiZoeToggleBtn, hiZoeWakeMode, Ui.CYAN);
        styleTogglePill(webToggleBtn, webOn, Ui.COBALT);
        styleTogglePill(voiceModeBtn, useNativeVoice, Ui.PINK);
        if (arToggleBtn != null) {
            styleTogglePill(arToggleBtn, arModeOn, Ui.COBALT);
            arToggleBtn.setText(arModeOn ? "✦ AR: On" : "✦ AR Space");
        }
        liveCamBtn.setText(arModeOn ? "AR Live" : (cameraOn && callActive ? "Cam Live" : "Live + Cam"));
    }

    private void styleTogglePill(Button btn, boolean active, int accentRes) {
        if (active) {
            int accent = Ui.resolveColor(this, accentRes);
            btn.setTextColor(Ui.isDark(this) ? Color.rgb(14, 16, 22) : Color.WHITE);
            btn.setBackground(Ui.tonalPillDrawable(this, accent, accent, 17));
        } else {
            btn.setTextColor(Ui.mutedColor(this));
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 17));
        }
    }

    private void updateKeepScreenOn() {
        if (callActive || cameraOn || arModeOn) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
    }

    private void initTts() {
        tts = new TextToSpeech(this, st -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            ttsReady = st == TextToSpeech.SUCCESS;
            if (ttsReady && tts != null) {
                tts.setLanguage(Locale.US);
                tts.setSpeechRate(1.03f);
                tts.setPitch(1.02f);
                tts.setAudioAttributes(new AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build());
                selectBestEnglishVoice();
                tts.setOnUtteranceProgressListener(new UtteranceProgressListener() {
                    @Override
                    public void onStart(String utteranceId) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed()) {
                                orbView.setSpeakingPulse(true);
                            }
                        });
                    }

                    @Override
                    public void onDone(String utteranceId) {
                        handleTtsChunkFinished(utteranceId);
                    }

                    @Override
                    public void onError(String utteranceId) {
                        handleTtsChunkFinished(utteranceId);
                    }
                });
                if (!pendingSpeechOnReady.isEmpty()) {
                    String toSpeak = pendingSpeechOnReady;
                    pendingSpeechOnReady = "";
                    speakCompleteReply(toSpeak, activeTurnId.get());
                }
            } else {
                // OS TTS unavailable — cleanly switch to Zoe's 100% offline 44.1 kHz voice so Explore never hangs!
                useNativeVoice = true;
                voiceModeBtn.setText("Voice: Zoe 44k");
                styleHeaderPills();
                if (!pendingSpeechOnReady.isEmpty()) {
                    String toSpeak = pendingSpeechOnReady;
                    pendingSpeechOnReady = "";
                    speakCompleteReply(toSpeak, activeTurnId.get());
                }
            }
        }));
    }

    private void selectBestEnglishVoice() {
        try {
            Set<Voice> all = tts.getVoices();
            if (all == null || all.isEmpty()) {
                return;
            }
            Voice best = null;
            int bestScore = -1;
            for (Voice v : all) {
                if (v == null || v.getLocale() == null) {
                    continue;
                }
                if (!"en".equalsIgnoreCase(v.getLocale().getLanguage())) {
                    continue;
                }
                int score = 0;
                if ("US".equalsIgnoreCase(v.getLocale().getCountry())) {
                    score += 10;
                }
                if (!v.isNetworkConnectionRequired()) {
                    score += 8;
                }
                if (v.getQuality() >= Voice.QUALITY_HIGH) {
                    score += 6;
                }
                if (score > bestScore) {
                    bestScore = score;
                    best = v;
                }
            }
            if (best != null) {
                tts.setVoice(best);
            }
        } catch (Exception ignored) {
        }
    }

    private void handleTtsChunkFinished(String utteranceId) {
        long turnOfUtterance = parseTurnFromUtteranceId(utteranceId);
        int remaining = Math.max(0, pendingTtsChunks.decrementAndGet());
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            if (turnOfUtterance != activeTurnId.get()) {
                return;
            }
            if (remaining == 0 && streamCompletedForCurrentTurn) {
                orbView.setSpeakingPulse(false);
                if (callActive) {
                    scheduleListeningRearm(ECHO_GUARD_MS);
                } else {
                    setOrbState(OrbState.IDLE, "READY · TAP ORB TO GO LIVE");
                }
            }
        });
    }

    private static long parseTurnFromUtteranceId(String id) {
        if (id == null) {
            return -1L;
        }
        int idx = id.indexOf(':');
        if (idx <= 0) {
            return -1L;
        }
        try {
            return Long.parseLong(id.substring(0, idx));
        } catch (NumberFormatException ignored) {
            return -1L;
        }
    }

    // --- Runtime Permissions (1 tap goes live immediately upon grant!) ---

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != PERM_REQ) {
            return;
        }
        boolean micGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
        boolean camGranted = ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED;
        PendingAction act = pendingAction;
        pendingAction = PendingAction.NONE;

        switch (act) {
            case START_LIVE_PLUS_CAM -> {
                if (camGranted) {
                    startCamera();
                }
                if (micGranted) {
                    beginContinuousVoiceSession();
                } else if (!camGranted) {
                    captionView.setText("Microphone or camera permission was denied. Tap Talk Now or Camera anytime to retry.");
                }
            }
            case START_AR_SPACE -> {
                if (camGranted) {
                    startArSpaceAndVoice(micGranted);
                } else {
                    captionView.setText("Camera permission is needed for AR Space. Tap ✦ AR Space anytime to allow.");
                }
            }
            case START_VOICE_ONLY -> {
                if (micGranted) {
                    beginContinuousVoiceSession();
                } else {
                    captionView.setText("Microphone permission is needed to talk live. Tap Talk Now to allow.");
                }
            }
            case START_HIZOE -> {
                if (micGranted) {
                    activateHiZoeMode();
                } else {
                    captionView.setText("Microphone permission is needed for \"Hi Zoe\" mode.");
                }
            }
            case START_CAMERA_ONLY -> {
                if (camGranted) {
                    startCamera();
                } else {
                    captionView.setText("Camera permission was denied. Zoe's camera stays off.");
                }
            }
            default -> {
            }
        }
    }

    // --- Top Bar Controls ---

    private void toggleHiZoeMode() {
        if (hiZoeWakeMode) {
            hiZoeWakeMode = false;
            hiZoeToggleBtn.setText("Hi Zoe: off");
            callActive = false;
            activeTurnId.incrementAndGet();
            stopAudioOnly();
            setOrbState(OrbState.IDLE, "HI ZOE OFF · TAP ORB TO GO LIVE");
            captionView.setText("\"Hi Zoe\" listener turned off. Microphone is idle.");
            styleHeaderPills();
            updateKeepScreenOn();
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            pendingAction = PendingAction.START_HIZOE;
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, PERM_REQ);
            return;
        }
        activateHiZoeMode();
    }

    private void activateHiZoeMode() {
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        hiZoeWakeMode = true;
        callActive = true;
        consecutiveErrors = 0;
        hiZoeToggleBtn.setText("Hi Zoe: on");
        styleHeaderPills();
        updateKeepScreenOn();
        setOrbState(OrbState.LISTENING, "WAITING FOR 'HI ZOE' · VISIBLE OPT-IN");
        captionView.setText("\"Hi Zoe\" hangout mode is active. Say \"Hi Zoe\" (or \"Hi Zoe, ...\") anytime — tap End / Mute to turn off.");
        scheduleListeningRearm(150L);
    }

    private void toggleWeb() {
        webOn = !webOn;
        webToggleBtn.setText(webOn ? "Web: on" : "Web: off");
        styleHeaderPills();
        captionView.setText(webOn
                ? "Live Web Grounding ON (zero-key DuckDuckGo + Wikipedia citations)."
                : "Live Web Grounding OFF (100% offline local voice mode).");
    }

    private void toggleVoiceEngine() {
        useNativeVoice = !useNativeVoice;
        voiceModeBtn.setText(useNativeVoice ? "Voice: Zoe 44k" : "Voice: OS");
        styleHeaderPills();
    }

    private void toggleCamera() {
        if (arModeOn) {
            stopArSpace();
            return;
        }
        if (cameraOn) {
            stopCamera();
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            pendingAction = PendingAction.START_CAMERA_ONLY;
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, PERM_REQ);
            return;
        }
        startCamera();
    }

    // --- Google Play Services for AR (ARCore 6DoF) Interactive Space ---

    private void toggleArSpace() {
        if (arModeOn) {
            stopArSpace();
            captionView.setText("Exited AR Space. Tap ✦ AR Space anytime to bring Zoe back into your room.");
            return;
        }
        List<String> needed = new ArrayList<>();
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.CAMERA);
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.RECORD_AUDIO);
        }
        if (!needed.isEmpty()) {
            pendingAction = PendingAction.START_AR_SPACE;
            ActivityCompat.requestPermissions(this, needed.toArray(new String[0]), PERM_REQ);
            return;
        }
        startArSpaceAndVoice(true);
    }

    private void startArSpaceAndVoice(boolean withVoice) {
        if (cameraOn) {
            stopCamera();
        }
        if (!ZoeArSurfaceView.isArCoreSupported(this)) {
            captionView.setText("Google Play Services for AR is not supported on this device — opening Live + Cam instead.");
            startLiveVoiceAndCamera();
            return;
        }
        // Recreate a fresh GL surface on every AR start to prevent stale EGL textures or black-screen restarts
        if (arSurfaceView != null) {
            arSurfaceView.stopArSession();
            arSurfaceView = null;
        }
        arSurfaceHost.removeAllViews();
        arSurfaceView = new ZoeArSurfaceView(this, arBrain, new ZoeArSurfaceView.Listener() {
            @Override
            public void onArTrackingUpdate(int planeCount, float zoeDistMeters, String statusHint) {
                latestArDistanceMeters = zoeDistMeters;
                if (arModeOn && !isFinishing() && !isDestroyed()) {
                    arHudPill.setText(statusHint);
                }
            }

            @Override
            public void onZoeArrivedAtSpot(Bitmap uprightFrame, ArExploreBrain.Vec3 worldPos,
                                           float distanceMeters, boolean userTapped) {
                latestArDistanceMeters = distanceMeters;
                handleArSpotInspection(uprightFrame, worldPos, distanceMeters, userTapped);
            }

            @Override
            public void onArUnavailable(String reason) {
                if (!isFinishing() && !isDestroyed()) {
                    stopArSpace();
                    captionView.setText(reason);
                }
            }
        });
        arSurfaceHost.addView(arSurfaceView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        arSurfaceView.setAutonomousRoam(arRoamEnabled);
        arBrain.clearSession();
        arCard.setVisibility(View.VISIBLE);
        orbView.setVisibility(View.GONE);
        arModeOn = true;
        cameraToggleBtn.setText("Camera: AR");
        styleHeaderPills();
        updateKeepScreenOn();

        if (!arSurfaceView.startArSession()) {
            return;
        }
        if (withVoice) {
            beginContinuousVoiceSession();
        } else {
            setOrbState(OrbState.IDLE, "AR SPACE ACTIVE · TAP ANYWHERE IN ROOM");
            captionView.setText("Zoe entered your AR space! Move your phone to map surfaces or tap anywhere to call Zoe over.");
        }
    }

    private void stopArSpace() {
        arModeOn = false;
        if (arSurfaceView != null) {
            arSurfaceView.stopArSession();
            arSurfaceView = null;
        }
        arSurfaceHost.removeAllViews();
        arCard.setVisibility(View.GONE);
        orbView.setVisibility(View.VISIBLE);
        cameraToggleBtn.setText("Camera: off");
        styleHeaderPills();
        updateKeepScreenOn();
    }

    private void toggleArRoam() {
        arRoamEnabled = !arRoamEnabled;
        if (arSurfaceView != null) {
            arSurfaceView.setAutonomousRoam(arRoamEnabled);
        }
        arRoamBtn.setText(arRoamEnabled ? "Roam: on" : "Roam: off");
        arRoamBtn.setBackground(Ui.tonalPillDrawable(this,
                arRoamEnabled ? Color.argb(195, 22, 92, 76) : Color.argb(185, 28, 32, 42),
                arRoamEnabled ? Ui.GREEN : Ui.MUTED, 16));
    }

    private void handleArSpotInspection(Bitmap uprightFrame, ArExploreBrain.Vec3 worldPos,
                                        float distanceMeters, boolean userTapped) {
        if (!arModeOn || uprightFrame == null || isFinishing() || isDestroyed()) {
            return;
        }
        // Never interrupt if Zoe is already thinking/speaking unless the user explicitly tapped a spot!
        if (!userTapped && (currentOrbState == OrbState.THINKING || currentOrbState == OrbState.SPEAKING)) {
            uprightFrame.recycle();
            return;
        }
        executor.execute(() -> {
            String report;
            byte[] jpeg;
            String learnedHint = "";
            try {
                report = MediaChatHelper.inspectFrameOffline(uprightFrame);
                jpeg = MediaChatHelper.bitmapToJpeg(uprightFrame, 78);
                // Silently query Guided Vision's on-device learned visual memory (<2ms offline, zero UI clutter!)
                learnedHint = VisionPriorStore.buildSilentExploreContext(this, uprightFrame);
            } catch (Throwable err) {
                uprightFrame.recycle();
                return;
            }
            uprightFrame.recycle();
            String scaleNote = ScientificVisualSubstrate.describeRelativeScale(distanceMeters);
            StringBuilder enriched = new StringBuilder(report);
            if (!learnedHint.isEmpty()) {
                enriched.append(" ").append(learnedHint);
            }
            if (!scaleNote.isEmpty()) {
                enriched.append(" ").append(scaleNote);
            }
            latestCameraReport = enriched.toString().trim();
            latestCameraJpeg = jpeg;

            ArExploreBrain.SpatialDiscovery discovery = arBrain.recordDiscoveryIfNew(
                    report, worldPos, distanceMeters, System.currentTimeMillis());
            if (!userTapped && discovery == null) {
                return;
            }
            final ArExploreBrain.SpatialDiscovery targetDisc = discovery != null
                    ? discovery
                    : new ArExploreBrain.SpatialDiscovery(
                            ArExploreBrain.extractPrimaryLabel(report),
                            ArExploreBrain.extractOcrSnippet(report),
                            latestCameraReport, worldPos, distanceMeters, System.currentTimeMillis());
            runOnUiThread(() -> {
                if (!arModeOn || isFinishing() || isDestroyed()) {
                    return;
                }
                if (!userTapped && (currentOrbState == OrbState.THINKING || currentOrbState == OrbState.SPEAKING)) {
                    return;
                }
                askCuriousArQuestion(targetDisc, userTapped);
            });
        });
    }

    private void askCuriousArQuestion(ArExploreBrain.SpatialDiscovery discovery, boolean userTapped) {
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = userTapped ? "Tapped spot in AR space" : "Zoe explored your room";
        setOrbState(OrbState.THINKING, "ZOE IS EXPLORING YOUR SPACE…");
        captionView.setText(userTapped
                ? "Gliding over to check out the spot you tapped…"
                : "Drifting over to explore something in your room…");

        String roomMemory = arBrain.summarizeRoomMemory();
        String curiosityPrompt = ArExploreBrain.buildCuriosityQuestionPrompt(discovery, roomMemory);

        executor.execute(() -> {
            if (myTurn != activeTurnId.get()) {
                return;
            }
            // 1. Optional Gemini Vision if user saved a Gemini API key
            byte[] jpeg = latestCameraJpeg;
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (jpeg != null && !geminiKey.isEmpty()) {
                try {
                    String reply = CloudVisionClient.askVision(
                            geminiKey,
                            MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT + "\n" + curiosityPrompt,
                            jpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }
            // 2. On-device Zoe Local 1.5B sentence-streaming curious question (100% offline!)
            final boolean streamTtsNow = !useNativeVoice && ttsReady && tts != null;
            final int[] spokenOffset = {0};
            final boolean[] startedSpeaking = {false};
            if (streamTtsNow) {
                pendingTtsChunks.set(0);
                streamCompletedForCurrentTurn = false;
            }
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (localModel != null) {
                try {
                    String chatMl = OnDeviceLlmEngine.buildChatMlPrompt(curiosityPrompt, sessionHistory, "", "");
                    String reply = localLlm.generateStreaming(localModel, chatMl, (partial, done) ->
                            handleStreamChunk(myTurn, partial, streamTtsNow, spokenOffset, startedSpeaking));
                    finalizeStreamedTurn(myTurn, reply, streamTtsNow, spokenOffset[0], startedSpeaking[0]);
                    return;
                } catch (Exception ignored) {
                }
            }
            // 3. Instant deterministic offline curious question fallback (<2ms!)
            String offlineQ = ArExploreBrain.buildOfflineCuriousQuestion(discovery);
            if (myTurn == activeTurnId.get()) {
                runOnUiThread(() -> finishSimpleReply(myTurn, offlineQ));
            }
        });
    }

    /**
     * One-tap Google Gemini Live mode: turns on Live Camera Sight AND Continuous Voice simultaneously!
     */
    private void startLiveVoiceAndCamera() {
        if (arModeOn) {
            stopArSpace();
        }
        if (cameraOn && callActive) {
            describeLiveViewProactively();
            return;
        }
        List<String> needed = new ArrayList<>();
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.RECORD_AUDIO);
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.CAMERA);
        }
        if (!needed.isEmpty()) {
            pendingAction = PendingAction.START_LIVE_PLUS_CAM;
            ActivityCompat.requestPermissions(this, needed.toArray(new String[0]), PERM_REQ);
            return;
        }
        if (!cameraOn) {
            startCamera();
        }
        beginContinuousVoiceSession();
    }

    private void flipCamera() {
        useFrontCamera = !useFrontCamera;
        if (cameraOn) {
            bindCameraPreview();
        }
    }

    private void startCamera() {
        cameraOn = true;
        cameraToggleBtn.setText("Camera: on");
        cameraCard.setVisibility(View.VISIBLE);
        applyResponsiveGeometry(getResources().getConfiguration());
        styleHeaderPills();
        updateKeepScreenOn();
        cameraPreview.post(this::bindCameraPreview);
    }

    private void bindCameraPreview() {
        ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            if (!cameraOn || isFinishing() || isDestroyed()) {
                return;
            }
            try {
                cameraProvider = future.get();
                cameraProvider.unbindAll();
                Preview preview = new Preview.Builder().build();
                preview.setSurfaceProvider(cameraPreview.getSurfaceProvider());
                CameraSelector selector = useFrontCamera
                        ? CameraSelector.DEFAULT_FRONT_CAMERA
                        : CameraSelector.DEFAULT_BACK_CAMERA;
                cameraProvider.bindToLifecycle(this, selector, preview);
                cameraSightPill.setText("● LIVE SIGHT");
                if (!callActive) {
                    captionView.setText("Live sight active! Tap Talk Now (or just speak when live) and ask Zoe about anything you point at.");
                }
                mainHandler.removeCallbacks(cameraObserverTick);
                mainHandler.postDelayed(cameraObserverTick, 900L);
            } catch (Exception error) {
                cameraSightPill.setText("CAMERA UNAVAILABLE");
                captionView.setText("Camera unavailable: " + error.getMessage());
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void stopCamera() {
        cameraOn = false;
        latestCameraReport = "";
        latestCameraJpeg = null;
        mainHandler.removeCallbacks(cameraObserverTick);
        if (cameraProvider != null) {
            try {
                cameraProvider.unbindAll();
            } catch (Exception ignored) {
            }
        }
        cameraCard.setVisibility(View.GONE);
        cameraToggleBtn.setText("Camera: off");
        applyResponsiveGeometry(getResources().getConfiguration());
        styleHeaderPills();
        updateKeepScreenOn();
    }

    private void captureBackgroundCameraFrame() {
        if (!cameraOn || !cameraAnalysisBusy.compareAndSet(false, true)) {
            return;
        }
        Bitmap frame = cameraPreview.getBitmap();
        if (frame == null) {
            cameraAnalysisBusy.set(false);
            return;
        }
        executor.execute(() -> {
            Bitmap small = null;
            try {
                // Skip unnecessary JPEG encoding during silent background heartbeat (cuts CPU/GC!)
                small = MediaChatHelper.scaleDown(frame, 480);
                String report = MediaChatHelper.inspectFrameOffline(small);
                String learnedHint = VisionPriorStore.buildSilentExploreContext(this, small);
                latestCameraReport = learnedHint.isEmpty() ? report : (report + " " + learnedHint);
            } catch (Exception ignored) {
            } finally {
                if (small != null && !small.isRecycled()) {
                    small.recycle();
                } else if (!frame.isRecycled()) {
                    frame.recycle();
                }
                cameraAnalysisBusy.set(false);
            }
        });
    }

    private void describeLiveViewProactively() {
        if (!cameraOn) {
            return;
        }
        // Snapshot the freshest possible frame immediately and let Zoe describe it aloud!
        Bitmap frame = cameraPreview.getBitmap();
        if (frame == null && latestCameraReport.isEmpty()) {
            captionView.setText("Waiting for camera preview frame — try tapping Look now again.");
            return;
        }
        long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "Look at my camera view";
        setOrbState(OrbState.THINKING, "LOOKING AT YOUR VIEW…");
        captionView.setText("Looking closely at what's in front of your camera…");
        executor.execute(() -> {
            Bitmap working = null;
            if (frame != null) {
                try {
                    working = MediaChatHelper.scaleDown(frame, 640);
                    String baseReport = MediaChatHelper.inspectFrameOffline(working);
                    String learnedHint = VisionPriorStore.buildSilentExploreContext(this, working);
                    latestCameraReport = learnedHint.isEmpty() ? baseReport : (baseReport + " " + learnedHint);
                    latestCameraJpeg = MediaChatHelper.bitmapToJpeg(working, 80);
                } catch (Exception ignored) {
                }
            }
            try {
                answerTurnInBackground(myTurn, "Tell me naturally in two sentences what you see in my camera right now.", true, working);
            } finally {
                if (working != null && !working.isRecycled()) {
                    working.recycle();
                }
            }
        });
    }

    // --- Continuous Voice Session & Barge-In ---

    private void onOrbTapped() {
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            pendingAction = PendingAction.START_VOICE_ONLY;
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.RECORD_AUDIO}, PERM_REQ);
            return;
        }
        beginContinuousVoiceSession();
    }

    private void beginContinuousVoiceSession() {
        hiZoeWakeMode = false;
        hiZoeToggleBtn.setText("Hi Zoe: off");
        callActive = true;
        consecutiveErrors = 0;
        styleHeaderPills();
        updateKeepScreenOn();
        captionView.setText(arModeOn
                ? "Zoe is floating in your AR space! Walk around, talk naturally, or tap anywhere in your room to call Zoe over."
                : (cameraOn
                        ? "I'm listening and looking live — speak naturally about anything in front of your camera."
                        : "I'm listening live — speak naturally, or tap the orb anytime to interrupt."));
        scheduleListeningRearm(100L);
    }

    private void scheduleListeningRearm(long delayMs) {
        final long myGen = listenGen.incrementAndGet();
        mainHandler.postDelayed(() -> {
            if (myGen == listenGen.get() && callActive && !isFinishing() && !isDestroyed()) {
                startListeningOnce(myGen);
            }
        }, Math.max(60L, delayMs));
    }

    private SpeechRecognizer createBestRecognizer() {
        if (preferDeviceRecognizer && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S
                && SpeechRecognizer.isOnDeviceRecognitionAvailable(this)) {
            return SpeechRecognizer.createOnDeviceSpeechRecognizer(this);
        }
        return SpeechRecognizer.createSpeechRecognizer(this);
    }

    private void startListeningOnce(long myGen) {
        if (!callActive || myGen != listenGen.get() || isFinishing() || isDestroyed()) {
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)
                && (Build.VERSION.SDK_INT < Build.VERSION_CODES.S || !SpeechRecognizer.isOnDeviceRecognitionAvailable(this))) {
            setOrbState(OrbState.IDLE, "VOICE RECOGNIZER UNAVAILABLE");
            captionView.setText("Speech recognition service is unavailable on this device. Tap a quick prompt above or use Zoe Chat.");
            callActive = false;
            updateKeepScreenOn();
            return;
        }
        destroyRecognizerQuietly();
        try {
            recognizer = createBestRecognizer();
        } catch (Exception err) {
            preferDeviceRecognizer = false;
            recognizer = SpeechRecognizer.createSpeechRecognizer(this);
        }

        recognizer.setRecognitionListener(new RecognitionListener() {
            @Override
            public void onReadyForSpeech(Bundle params) {
                if (myGen != listenGen.get()) {
                    return;
                }
                consecutiveErrors = 0;
                setOrbState(OrbState.LISTENING, hiZoeWakeMode
                        ? "WAITING FOR 'HI ZOE' · SPEAK ANYTIME"
                        : (arModeOn ? "AR SPACE LIVE · EXPLORE & TALK"
                                : (cameraOn ? "LIVE VOICE + SIGHT · SPEAK NATURALLY" : "LIVE · LISTENING NATURALLY")));
            }

            @Override
            public void onBeginningOfSpeech() {
            }

            @Override
            public void onRmsChanged(float rmsdB) {
                if (myGen == listenGen.get()) {
                    float norm = Math.max(0f, Math.min(1f, (rmsdB + 2f) / 11f));
                    orbView.setAudioLevel(norm);
                    if (arSurfaceView != null && arModeOn) {
                        arSurfaceView.setVoiceLevel(norm);
                    }
                }
            }

            @Override
            public void onBufferReceived(byte[] buffer) {
            }

            @Override
            public void onEndOfSpeech() {
                if (myGen == listenGen.get()) {
                    orbView.setAudioLevel(0f);
                    if (!hiZoeWakeMode) {
                        setOrbState(OrbState.THINKING, (cameraOn || arModeOn) ? "SEEING & THINKING…" : "THINKING…");
                    }
                }
            }

            @Override
            public void onError(int error) {
                if (myGen != listenGen.get() || !callActive || isFinishing() || isDestroyed()) {
                    return;
                }
                orbView.setAudioLevel(0f);
                LiveSessionLogic.ErrorPolicy policy = LiveSessionLogic.classifySpeechError(error);
                switch (policy.action) {
                    case SILENT_REARM -> {
                        // Normal silence/pause! Keep the orb calmly glowing and silently re-arm — zero error banner!
                        consecutiveErrors = 0;
                        scheduleListeningRearm(policy.delayMs);
                    }
                    case FALLBACK_RECOGNIZER -> {
                        preferDeviceRecognizer = !preferDeviceRecognizer;
                        consecutiveErrors++;
                        if (consecutiveErrors <= 6) {
                            scheduleListeningRearm(policy.delayMs);
                        } else {
                            callActive = false;
                            setOrbState(OrbState.IDLE, "TAP ORB TO RESUME LIVE");
                            captionView.setText("Voice paused briefly. Tap the orb anytime to keep talking.");
                            updateKeepScreenOn();
                        }
                    }
                    case RESET_AND_RETRY -> {
                        destroyRecognizerQuietly();
                        consecutiveErrors++;
                        if (consecutiveErrors <= 5) {
                            scheduleListeningRearm(policy.delayMs);
                        } else {
                            callActive = false;
                            setOrbState(OrbState.IDLE, "TAP ORB TO RESUME LIVE");
                            captionView.setText("Voice paused. Tap Talk Now anytime to continue.");
                            updateKeepScreenOn();
                        }
                    }
                    case FATAL_PERMISSION -> {
                        callActive = false;
                        hiZoeWakeMode = false;
                        hiZoeToggleBtn.setText("Hi Zoe: off");
                        styleHeaderPills();
                        updateKeepScreenOn();
                        setOrbState(OrbState.IDLE, "MIC PERMISSION NEEDED");
                        captionView.setText(policy.userMessage);
                    }
                }
            }

            @Override
            public void onResults(Bundle results) {
                if (myGen != listenGen.get() || isFinishing() || isDestroyed()) {
                    return;
                }
                consecutiveErrors = 0;
                orbView.setAudioLevel(0f);
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                String heard = (matches != null && !matches.isEmpty()) ? matches.get(0).trim() : "";
                if (heard.isEmpty()) {
                    if (callActive) {
                        scheduleListeningRearm(240L);
                    } else {
                        setOrbState(OrbState.IDLE, "READY · TAP ORB TO GO LIVE");
                    }
                    return;
                }
                if (hiZoeWakeMode) {
                    if (WakeWordDetector.isHiZoeTrigger(heard)) {
                        String trailing = WakeWordDetector.stripWakePrefix(heard);
                        hiZoeWakeMode = false;
                        hiZoeToggleBtn.setText("Hi Zoe: off");
                        styleHeaderPills();
                        if (trailing.isEmpty()) {
                            long myTurn = activeTurnId.incrementAndGet();
                            lastUserSpoken = heard;
                            finishSimpleReply(myTurn, "Hi! I'm Zoe — ready to hang out and explore. What are we getting into?");
                        } else {
                            processSpokenPrompt(trailing);
                        }
                    } else if (callActive) {
                        captionView.setText("Listening for \"Hi Zoe\"…");
                        scheduleListeningRearm(260L);
                    }
                    return;
                }
                processSpokenPrompt(heard);
            }

            @Override
            public void onPartialResults(Bundle partialResults) {
                if (myGen != listenGen.get() || isFinishing() || isDestroyed()) {
                    return;
                }
                ArrayList<String> partial = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (partial != null && !partial.isEmpty() && !partial.get(0).trim().isEmpty()) {
                    String p = partial.get(0).trim();
                    if (!hiZoeWakeMode) {
                        captionView.setText("You: " + p);
                    }
                }
            }

            @Override
            public void onEvent(int eventType, Bundle params) {
            }
        });

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1300L)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1100L);
        try {
            recognizer.startListening(intent);
            setOrbState(OrbState.LISTENING, hiZoeWakeMode
                    ? "WAITING FOR 'HI ZOE' · VISIBLE OPT-IN"
                    : (arModeOn ? "AR SPACE LIVE · EXPLORE & TALK"
                            : (cameraOn ? "LIVE VOICE + SIGHT · SPEAK NATURALLY" : "LIVE · LISTENING…")));
        } catch (Exception err) {
            preferDeviceRecognizer = false;
            scheduleListeningRearm(500L);
        }
    }

    // --- Real-Time Simultaneous Sight + Sentence-Streaming Speech Pipeline ---

    private void processSpokenPrompt(String spoken) {
        if (ConversationResponse.isStop(spoken)) {
            stopLiveCall();
            return;
        }
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = spoken;
        sessionHistory.add(new ChatHistoryStore.ChatMessage("user", spoken, "YOU", "", 0));
        final boolean hasSight = cameraOn || arModeOn;
        captionView.setText(LiveSessionLogic.formatLiveCaption(spoken, hasSight ? "Looking & thinking…" : "Thinking…"));
        setOrbState(OrbState.THINKING, hasSight ? "SEEING & THINKING…" : "ZOE IS THINKING…");

        String lower = spoken.toLowerCase(Locale.US);
        boolean identity = lower.contains("who are you") || lower.contains("who built you")
                || lower.contains("alibaba") || lower.contains("are you zoe");
        if (identity) {
            finishSimpleReply(myTurn, brain.respond(spoken).reply);
            return;
        }
        // Instant <2ms deterministic exact math, unit conversions, and real local device clock!
        ZoeBrainEngine.BrainReply fastExact = brain.respond(spoken);
        if ("exact_math".equals(fastExact.mode)
                || "unit_conversion".equals(fastExact.mode)
                || "local_clock".equals(fastExact.mode)) {
            finishSimpleReply(myTurn, fastExact.reply);
            return;
        }

        // Capture a fresh live frame right now from either Live Camera OR AR Space!
        final Bitmap freshFrame = cameraOn
                ? cameraPreview.getBitmap()
                : (arModeOn && arSurfaceView != null ? arSurfaceView.getLatestSnapshotCopy() : null);
        executor.execute(() -> {
            if (myTurn != activeTurnId.get()) {
                if (freshFrame != null && !freshFrame.isRecycled()) {
                    freshFrame.recycle();
                }
                return;
            }
            Bitmap frameForVision = null;
            if (freshFrame != null) {
                try {
                    Bitmap small = MediaChatHelper.scaleDown(freshFrame, 512);
                    String baseReport = MediaChatHelper.inspectFrameOffline(small);
                    String learnedHint = VisionPriorStore.buildSilentExploreContext(this, small);
                    latestCameraReport = learnedHint.isEmpty() ? baseReport : (baseReport + " " + learnedHint);
                    latestCameraJpeg = MediaChatHelper.bitmapToJpeg(small, 78);
                    frameForVision = small;
                } catch (Exception ignored) {
                    if (!freshFrame.isRecycled()) {
                        freshFrame.recycle();
                    }
                }
            }
            try {
                answerTurnInBackground(myTurn, spoken, hasSight, frameForVision);
            } finally {
                if (frameForVision != null && !frameForVision.isRecycled()) {
                    frameForVision.recycle();
                }
            }
        });
    }

    private void answerTurnInBackground(long myTurn, String spoken, boolean withCamera, Bitmap liveFrame) {
        if (myTurn != activeTurnId.get()) {
            return;
        }
        WebSearchClient.SearchResult webRes = webOn ? WebSearchClient.search(spoken) : null;
        String webCtx = (webRes != null && webRes.hasSources()) ? webRes.formatContextForPrompt(700) : "";

        // Silent background patent grounding ONLY when Web: on AND (an exact patent number is stamped/read OR user explicitly asks about a patent).
        // Zero noisy cards or popups are ever shown to the user in Zoe Explore!
        String lowerSpoken = spoken == null ? "" : spoken.toLowerCase(Locale.US);
        String exactPatentId = GooglePatentsClient.extractPatentNumber(
                ArExploreBrain.extractOcrSnippet(latestCameraReport) + " " + (spoken == null ? "" : spoken));
        boolean wantsSilentPatent = webOn && (!exactPatentId.isEmpty()
                || lowerSpoken.contains("patent")
                || lowerSpoken.contains("schematic"));
        GooglePatentsClient.LookupResult patRes = null;
        if (wantsSilentPatent) {
            patRes = GooglePatentsClient.silentResolveForVision(
                    liveFrame, latestCameraReport, spoken, arModeOn ? latestArDistanceMeters : 0f);
            if (patRes.hasMatches()) {
                String patCtx = patRes.formatPromptContext(520);
                webCtx = webCtx.isEmpty() ? patCtx : (webCtx + "\n" + patCtx);
            }
        }
        String roomMem = arModeOn ? arBrain.summarizeRoomMemory() : "";
        String camReport = withCamera
                ? (roomMem.isEmpty() ? latestCameraReport : (latestCameraReport + " " + roomMem).trim())
                : "";
        byte[] camJpeg = withCamera ? latestCameraJpeg : null;

        // 1. Live Multimodal Gemini Vision when Camera is ON + user saved a Gemini key
        if (withCamera && camJpeg != null) {
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (!geminiKey.isEmpty()) {
                try {
                    String visionPrompt = MultiAiClient.ZOE_SYSTEM_PROMPT
                            + "\n" + LiveSessionLogic.buildLiveVoicePrompt(spoken, camReport);
                    String reply = CloudVisionClient.askVision(
                            geminiKey,
                            MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            visionPrompt,
                            camJpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }
        }

        // Prepare live sentence-streaming speech state for OS TTS (real-time speech while generating!)
        final boolean streamTtsNow = !useNativeVoice && ttsReady && tts != null;
        final int[] spokenOffset = {0};
        final boolean[] startedSpeaking = {false};
        if (streamTtsNow) {
            pendingTtsChunks.set(0);
            streamCompletedForCurrentTurn = false;
        }

        String fusedPrompt = LiveSessionLogic.buildLiveVoicePrompt(spoken, camReport);

        // 2. Cloud Multi-AI SSE Streaming (if keyed)
        MultiAiClient.Provider activeCloud = MultiAiClient.activeProvider(this);
        String cloudKey = MultiAiClient.savedKey(this, activeCloud);
        if (!cloudKey.isEmpty()) {
            try {
                String reply = MultiAiClient.askStreaming(
                        this, activeCloud, fusedPrompt, sessionHistory, "", webCtx, webOn,
                        partial -> handleStreamChunk(myTurn, partial, streamTtsNow, spokenOffset, startedSpeaking));
                finalizeStreamedTurn(myTurn, reply, streamTtsNow, spokenOffset[0], startedSpeaking[0]);
                return;
            } catch (Exception ignored) {
            }
        }

        // 3. On-Device Zoe Local Neural Streaming (GPU-first + KV-Clone + Native Multimodal Vision if pack supports it!)
        File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
        if (localModel != null) {
            try {
                String chatMl = OnDeviceLlmEngine.buildChatMlPrompt(fusedPrompt, sessionHistory, "", webCtx);
                String reply = localLlm.generateStreamingWithOptionalImage(localModel, chatMl, liveFrame, (partial, done) ->
                        handleStreamChunk(myTurn, partial, streamTtsNow, spokenOffset, startedSpeaking));
                finalizeStreamedTurn(myTurn, reply, streamTtsNow, spokenOffset[0], startedSpeaking[0]);
                return;
            } catch (Exception ignored) {
            }
        }

        // 4. Instant Offline / Patent Reverse-Search Fallback (Patent match or Web summary or Camera or Zoe Stem <5ms)
        String fallback;
        if (patRes != null && patRes.hasMatches()) {
            fallback = patRes.formatSpokenSummary();
        } else if (webRes != null && webRes.hasSources()) {
            fallback = webRes.formatFallbackAnswer();
        } else if (withCamera && !camReport.isEmpty()) {
            fallback = "Here is what I see right now: " + camReport;
        } else {
            fallback = brain.respond(spoken).reply;
        }
        if (myTurn == activeTurnId.get()) {
            runOnUiThread(() -> finishSimpleReply(myTurn, fallback));
        }
    }

    private void handleStreamChunk(
            long myTurn,
            String fullSoFar,
            boolean streamTtsNow,
            int[] spokenOffset,
            boolean[] startedSpeaking) {
        if (myTurn != activeTurnId.get() || fullSoFar == null || fullSoFar.isEmpty()) {
            return;
        }
        String display = OnDeviceLlmEngine.enforceZoeSovereignty(fullSoFar);
        if (streamTtsNow) {
            LiveSessionLogic.SentenceBatch batch = LiveSessionLogic.extractReadySentences(display, spokenOffset[0]);
            spokenOffset[0] = batch.nextOffset;
            for (String sentence : batch.sentences) {
                boolean first = !startedSpeaking[0];
                startedSpeaking[0] = true;
                enqueueTtsChunk(myTurn, sentence, first);
            }
        }
        runOnUiThread(() -> {
            if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                captionView.setText(LiveSessionLogic.formatLiveCaption(lastUserSpoken, display));
                if (startedSpeaking[0]) {
                    setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING · TAP ORB TO INTERRUPT");
                }
            }
        });
    }

    private void finalizeStreamedTurn(
            long myTurn,
            String finalReply,
            boolean streamTtsNow,
            int spokenOffset,
            boolean alreadyStartedSpeaking) {
        if (myTurn != activeTurnId.get()) {
            return;
        }
        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(finalReply);
        if (clean.trim().isEmpty()) {
            clean = "I'm right here listening.";
        }
        final String finalDisplay = clean.trim();
        sessionHistory.add(new ChatHistoryStore.ChatMessage("zoe", finalDisplay, "ZOE EXPLORE", "", 0));

        if (streamTtsNow) {
            String remainder = LiveSessionLogic.extractRemainder(finalDisplay, spokenOffset);
            if (!remainder.isEmpty()) {
                enqueueTtsChunk(myTurn, remainder, !alreadyStartedSpeaking);
                alreadyStartedSpeaking = true;
            }
            streamCompletedForCurrentTurn = true;
            final boolean spokeAnything = alreadyStartedSpeaking;
            runOnUiThread(() -> {
                if (myTurn != activeTurnId.get() || isFinishing() || isDestroyed()) {
                    return;
                }
                captionView.setText(LiveSessionLogic.formatLiveCaption(lastUserSpoken, finalDisplay));
                if (!spokeAnything || pendingTtsChunks.get() == 0) {
                    orbView.setSpeakingPulse(false);
                    if (callActive) {
                        scheduleListeningRearm(ECHO_GUARD_MS);
                    } else {
                        setOrbState(OrbState.IDLE, "READY · TAP ORB TO GO LIVE");
                    }
                } else {
                    setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING · TAP ORB TO INTERRUPT");
                }
            });
        } else {
            runOnUiThread(() -> finishSimpleReply(myTurn, finalDisplay));
        }
    }

    private void enqueueTtsChunk(long myTurn, String sentence, boolean flushFirst) {
        if (tts == null || !ttsReady || sentence == null || sentence.trim().isEmpty()) {
            return;
        }
        pendingTtsChunks.incrementAndGet();
        int queueMode = flushFirst ? TextToSpeech.QUEUE_FLUSH : TextToSpeech.QUEUE_ADD;
        String uttId = myTurn + ":" + System.nanoTime();
        int rc = tts.speak(sentence.trim(), queueMode, null, uttId);
        if (rc != TextToSpeech.SUCCESS) {
            handleTtsChunkFinished(uttId);
        }
    }

    private void finishSimpleReply(long myTurn, String reply) {
        if (myTurn != activeTurnId.get() || isFinishing() || isDestroyed()) {
            return;
        }
        String clean = reply == null || reply.trim().isEmpty() ? "I'm here and listening." : reply.trim();
        sessionHistory.add(new ChatHistoryStore.ChatMessage("zoe", clean, "ZOE EXPLORE", "", 0));
        captionView.setText(LiveSessionLogic.formatLiveCaption(lastUserSpoken, clean));
        speakCompleteReply(clean, myTurn);
    }

    private void speakCompleteReply(String text, long myTurn) {
        String speakable = LiveSessionLogic.sanitizeForSpeech(text);
        if (speakable.isEmpty()) {
            if (callActive) {
                scheduleListeningRearm(ECHO_GUARD_MS);
            } else {
                setOrbState(OrbState.IDLE, "READY · TAP ORB TO GO LIVE");
            }
            return;
        }
        setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING · TAP ORB TO INTERRUPT");
        if (useNativeVoice) {
            orbView.setSpeakingPulse(true);
            nativeVoice.speak(speakable, () -> runOnUiThread(() -> {
                orbView.setSpeakingPulse(false);
                if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                    if (callActive) {
                        scheduleListeningRearm(ECHO_GUARD_MS);
                    } else {
                        setOrbState(OrbState.IDLE, "READY · TAP ORB TO GO LIVE");
                    }
                }
            }));
        } else if (ttsReady && tts != null) {
            pendingTtsChunks.set(0);
            streamCompletedForCurrentTurn = true;
            enqueueTtsChunk(myTurn, speakable, true);
        } else {
            pendingSpeechOnReady = speakable;
            setOrbState(OrbState.IDLE, "PREPARING VOICE…");
        }
    }

    private void destroyRecognizerQuietly() {
        if (recognizer != null) {
            try {
                recognizer.cancel();
                recognizer.destroy();
            } catch (Exception ignored) {
            }
            recognizer = null;
        }
    }

    private void stopAudioOnly() {
        listenGen.incrementAndGet();
        pendingTtsChunks.set(0);
        streamCompletedForCurrentTurn = true;
        pendingSpeechOnReady = "";
        localLlm.cancelActiveGeneration();
        orbView.setAudioLevel(0f);
        orbView.setSpeakingPulse(false);
        destroyRecognizerQuietly();
        if (tts != null) {
            try {
                tts.stop();
            } catch (Exception ignored) {
            }
        }
        nativeVoice.stop();
    }

    private void stopLiveCall() {
        callActive = false;
        hiZoeWakeMode = false;
        hiZoeToggleBtn.setText("Hi Zoe: off");
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        if (arModeOn) {
            stopArSpace();
        }
        stopCamera();
        styleHeaderPills();
        updateKeepScreenOn();
        setOrbState(OrbState.IDLE, "EXPLORE PAUSED · MIC & CAMERA OFF");
        captionView.setText("Zoe Explore paused. Both microphone and camera are completely off.");
    }

    private void setOrbState(OrbState state, String label) {
        currentOrbState = state;
        orbView.setOrbState(state);
        if (arSurfaceView != null && arModeOn) {
            arSurfaceView.setVisualMood(switch (state) {
                case LISTENING -> ZoeArSurfaceView.VisualMood.LISTENING;
                case THINKING -> ZoeArSurfaceView.VisualMood.THINKING;
                case SPEAKING -> ZoeArSurfaceView.VisualMood.SPEAKING;
                default -> ZoeArSurfaceView.VisualMood.EXPLORING;
            });
            if (state != OrbState.LISTENING) {
                arSurfaceView.setVoiceLevel(state == OrbState.SPEAKING ? 0.55f : 0f);
            }
        }
        stateBadge.setText(label);
        listenBtn.setText(switch (state) {
            case LISTENING -> "Listening…";
            case SPEAKING -> "Interrupt";
            case THINKING -> "Thinking…";
            default -> "Talk Now";
        });
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (callActive || cameraOn || arModeOn) {
            stopLiveCall();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        mainHandler.removeCallbacksAndMessages(null);
        callActive = false;
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        if (arModeOn) {
            stopArSpace();
        }
        stopCamera();
        if (tts != null) {
            try {
                tts.shutdown();
            } catch (Exception ignored) {
            }
        }
        localLlm.close();
        executor.shutdownNow();
    }

    /**
     * Smooth 60fps Audio-Reactive GEM Breathing Orb rendered natively on Android Canvas.
     */
    private static final class LiveOrbView extends View {
        private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint ringPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint gemPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final ValueAnimator animator;
        private float phase;
        private float targetLevel;
        private float smoothLevel;
        private boolean speakingPulse;
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
                float desired = speakingPulse
                        ? (0.35f + 0.25f * (float) Math.abs(Math.sin(phase * Math.PI * 10.0)))
                        : targetLevel;
                smoothLevel += (desired - smoothLevel) * 0.22f;
                invalidate();
            });
            animator.start();
        }

        void setOrbState(OrbState next) {
            this.state = next == null ? OrbState.IDLE : next;
            invalidate();
        }

        void setAudioLevel(float level) {
            this.targetLevel = Math.max(0f, Math.min(1f, level));
        }

        void setSpeakingPulse(boolean active) {
            this.speakingPulse = active;
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

            float radius = maxR * (0.62f + 0.055f * breathe + 0.16f * smoothLevel);
            haloPaint.setShader(new RadialGradient(cx, cy, maxR,
                    new int[]{Color.argb(195, Color.red(cCore), Color.green(cCore), Color.blue(cCore)),
                            Color.argb(85, Color.red(cOuter), Color.green(cOuter), Color.blue(cOuter)),
                            Color.TRANSPARENT},
                    new float[]{0.2f, 0.66f, 1.0f}, Shader.TileMode.CLAMP));
            canvas.drawCircle(cx, cy, maxR, haloPaint);

            for (int i = 0; i < 3; i++) {
                float p = (phase + i / 3f) % 1f;
                float r = radius * 0.54f + p * (maxR - radius * 0.54f);
                ringPaint.setStrokeWidth(3f * (1f - p) + 1f);
                ringPaint.setColor(Color.argb((int) ((1f - p) * 165), Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
                canvas.drawCircle(cx, cy, r, ringPaint);
            }

            // Central luminous GEM diamond
            gemPaint.setColor(cCore);
            float g = radius * 0.35f;
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
