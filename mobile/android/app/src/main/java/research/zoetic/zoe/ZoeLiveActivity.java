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
import android.graphics.ImageFormat;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.graphics.drawable.GradientDrawable;
import android.location.Location;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.AudioTrack;
import android.media.MediaRecorder;
import android.net.Uri;
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
import android.util.Size;
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
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;

import java.io.File;
import java.nio.ByteBuffer;
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
    private final ExecutorService cameraAnalysisExecutor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final AtomicLong activeTurnId = new AtomicLong(0L);
    private final AtomicLong listenGen = new AtomicLong(0L);
    private final AtomicBoolean cameraAnalysisBusy = new AtomicBoolean(false);
    private final Object latestCamFrameLock = new Object();
    private Bitmap latestCameraBitmap;
    private long lastCameraBitmapMs;
    private final ArExploreBrain arBrain = new ArExploreBrain();
    private SpatialTelemetryCollector spatialTelemetry;

    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private OnDeviceLlmEngine localLlm;
    private final List<ChatHistoryStore.ChatMessage> sessionHistory = new ArrayList<>();

    private ZoeBackdropView idleBackdrop;
    private FrameLayout fullScreenMediaLayer;
    private View topScrim;
    private View bottomScrim;
    private LiveOrbView orbView;
    private TextView stateBadge;
    private TextView captionView;
    private ScrollView captionScroll;
    private View fullScreenSpacer;
    private LinearLayout quickChips;
    private LinearLayout hudBar;
    private LinearLayout sensorHudBar;
    private TextView telemetryHudLine;
    private PreviewView cameraPreview;
    private ZoeSpatialOverlayView spatialOverlayView;
    private FrameLayout arSurfaceHost;
    private ZoeArSurfaceView arSurfaceView;
    private TextView liveHudPill;
    private TextView arTapHint;
    private Button arToggleBtn;
    private Button arModeBtn;
    private Button arRoamBtn;
    private Button arAskBtn;
    private Button fieldToggleBtn;
    private Button dualCamBtn;
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
    private boolean useHeavyArCore6Dof;
    private boolean arRoamEnabled = true;
    private boolean useFrontCamera;
    private boolean spatialFieldOn;
    private volatile boolean dualCamSweepPending;
    private boolean dualCamReturnToBack;
    private final AtomicBoolean acousticPingBusy = new AtomicBoolean(false);
    private boolean webOn;
    private boolean hiZoeWakeMode;
    private boolean useNativeVoice;
    private boolean callActive;
    private boolean preferDeviceRecognizer = true;
    private int consecutiveErrors;
    private volatile OrbState currentOrbState = OrbState.IDLE;

    private volatile String latestCameraReport = "";
    private volatile String latestSpatialContext = "";
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
        spatialTelemetry = new SpatialTelemetryCollector(this, this::onSpatialTelemetryUpdated);

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

        // Root Full-Screen Stage:
        //   Layer 0: Atmospheric idle backdrop (hidden during camera/AR to save GPU overdraw)
        //   Layer 1: TRUE FULL-SCREEN edge-to-edge CameraX Hardware SurfaceView + 60fps Spatial Companion / ARCore
        //   Layer 2: Clean floating translucent glass HUD & controls (never boxes in the camera!)
        FrameLayout stageRoot = new FrameLayout(this);
        stageRoot.setBackgroundColor(Ui.bgColor(this));

        idleBackdrop = new ZoeBackdropView(this);
        stageRoot.addView(idleBackdrop, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        fullScreenMediaLayer = new FrameLayout(this);
        fullScreenMediaLayer.setBackgroundColor(Color.BLACK);
        fullScreenMediaLayer.setVisibility(View.GONE);

        // Zero-copy hardware SurfaceView camera preview (60/90fps edge-to-edge full screen!)
        cameraPreview = new PreviewView(this);
        cameraPreview.setImplementationMode(PreviewView.ImplementationMode.PERFORMANCE);
        cameraPreview.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        fullScreenMediaLayer.addView(cameraPreview, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Ultra-light 60fps IMU-Quaternion 3D Spatial Zoe Companion overlay (zero ARCore lag!)
        spatialOverlayView = new ZoeSpatialOverlayView(this, new ZoeSpatialOverlayView.Listener() {
            @Override
            public void onSpatialHudUpdate(float distanceMeters, String statusHint) {
                latestArDistanceMeters = distanceMeters;
                if (arModeOn && !useHeavyArCore6Dof && !isFinishing() && !isDestroyed()) {
                    liveHudPill.setText(statusHint);
                }
            }

            @Override
            public void onSpatialArrived(ArExploreBrain.Vec3 worldPos, float distanceMeters, boolean userTapped) {
                latestArDistanceMeters = distanceMeters;
                if (!arModeOn || useHeavyArCore6Dof || isFinishing() || isDestroyed()) {
                    return;
                }
                Bitmap snap = getLatestCameraFrameCopy();
                if (snap != null) {
                    handleArSpotInspection(snap, worldPos, distanceMeters, userTapped);
                }
            }
        });
        spatialOverlayView.setVisibility(View.GONE);
        fullScreenMediaLayer.addView(spatialOverlayView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Optional optimized ARCore 6DoF full-screen surface host
        arSurfaceHost = new FrameLayout(this);
        arSurfaceHost.setVisibility(View.GONE);
        fullScreenMediaLayer.addView(arSurfaceHost, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Soft top & bottom gradient scrims so floating HUD stays crisp over bright sunlight or dark rooms
        topScrim = new View(this);
        topScrim.setBackground(new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{Color.argb(190, 6, 10, 18), Color.argb(90, 6, 10, 18), Color.TRANSPARENT}));
        fullScreenMediaLayer.addView(topScrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 196), Gravity.TOP));

        bottomScrim = new View(this);
        bottomScrim.setBackground(new GradientDrawable(
                GradientDrawable.Orientation.BOTTOM_TOP,
                new int[]{Color.argb(215, 6, 10, 18), Color.argb(120, 6, 10, 18), Color.TRANSPARENT}));
        fullScreenMediaLayer.addView(bottomScrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 260), Gravity.BOTTOM));

        stageRoot.addView(fullScreenMediaLayer, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Foreground Chrome Layer (edge-to-edge inset padded)
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

        // Floating Full-Screen Camera / Spatial AR HUD Strip (shown ONLY when camera or AR is active!)
        hudBar = new LinearLayout(this);
        hudBar.setOrientation(LinearLayout.HORIZONTAL);
        hudBar.setGravity(Gravity.CENTER_VERTICAL);
        hudBar.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 2));
        hudBar.setVisibility(View.GONE);

        liveHudPill = Ui.text(this, "● LIVE SIGHT", 11f, Ui.GREEN);
        liveHudPill.setTypeface(Ui.SANS_MEDIUM);
        liveHudPill.setPadding(Ui.dp(this, 10), Ui.dp(this, 5), Ui.dp(this, 10), Ui.dp(this, 5));
        liveHudPill.setBackground(Ui.tonalPillDrawable(this, Color.argb(185, 14, 18, 26), Ui.GREEN, 14));
        hudBar.addView(liveHudPill);

        View hudSpacer = new View(this);
        hudBar.addView(hudSpacer, new LinearLayout.LayoutParams(0, 1, 1f));

        arModeBtn = chipButton("Gyro 60", v -> toggleArTrackingMode());
        arModeBtn.setId(R.id.live_ar_mode_toggle);
        arModeBtn.setTextColor(Color.WHITE);
        arModeBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(190, 26, 56, 108), Ui.CYAN, 16));
        LinearLayout.LayoutParams modeLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32));
        modeLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        hudBar.addView(arModeBtn, modeLp);

        arRoamBtn = chipButton("Roam: on", v -> toggleArRoam());
        arRoamBtn.setId(R.id.live_ar_roam_toggle);
        arRoamBtn.setTextColor(Color.WHITE);
        arRoamBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(195, 22, 92, 76), Ui.GREEN, 16));
        LinearLayout.LayoutParams roamLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32));
        roamLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        hudBar.addView(arRoamBtn, roamLp);

        flipCamBtn = chipButton("⇄", v -> flipCamera());
        flipCamBtn.setId(R.id.live_flip_camera);
        flipCamBtn.setContentDescription("Flip camera");
        flipCamBtn.setTextColor(Color.WHITE);
        flipCamBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(185, 14, 18, 26), Ui.primaryAccent(this), 16));
        LinearLayout.LayoutParams flipLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32));
        flipLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        hudBar.addView(flipCamBtn, flipLp);

        lookNowBtn = chipButton("Look", v -> describeLiveViewProactively());
        lookNowBtn.setId(R.id.live_look_button);
        lookNowBtn.setTextColor(Color.WHITE);
        lookNowBtn.setBackground(Ui.tonalPillDrawable(this, Ui.withAlpha(Ui.resolveColor(this, Ui.COBALT), 215), Ui.COBALT, 16));
        hudBar.addView(lookNowBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32)));

        arAskBtn = chipButton("Ask", v -> triggerArInstantLook());
        arAskBtn.setId(R.id.live_ar_ask_button);
        arAskBtn.setTextColor(Color.WHITE);
        arAskBtn.setBackground(Ui.tonalPillDrawable(this, Ui.withAlpha(Ui.resolveColor(this, Ui.COBALT), 220), Ui.COBALT, 16));
        hudBar.addView(arAskBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32)));

        header.addView(hudBar);

        // Secondary Opt-In Spatial Telemetry Strip (CERN Kloster A_tau/M4 · Dual-Cam Backlight · Acoustic Echo · Google Earth)
        sensorHudBar = new LinearLayout(this);
        sensorHudBar.setOrientation(LinearLayout.HORIZONTAL);
        sensorHudBar.setGravity(Gravity.CENTER_VERTICAL);
        sensorHudBar.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 2));
        sensorHudBar.setVisibility(View.GONE);

        fieldToggleBtn = chipButton("Field: off", v -> toggleSpatialField());
        fieldToggleBtn.setId(R.id.live_field_toggle);
        fieldToggleBtn.setTextColor(Color.WHITE);
        fieldToggleBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(175, 16, 22, 34), Ui.CYAN, 15));
        LinearLayout.LayoutParams fieldLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 30));
        fieldLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        sensorHudBar.addView(fieldToggleBtn, fieldLp);

        dualCamBtn = chipButton("Dual-Cam", v -> runDualCamAmbientSweep());
        dualCamBtn.setId(R.id.live_dual_cam_btn);
        dualCamBtn.setTextColor(Color.WHITE);
        dualCamBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(175, 22, 34, 58), Ui.COBALT, 15));
        LinearLayout.LayoutParams dualLp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 30));
        dualLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        sensorHudBar.addView(dualCamBtn, dualLp);

        telemetryHudLine = Ui.text(this, "Tap Field: CERN Aτ/M₄ · RF · ENU · Echo/Earth", 10.5f, Ui.TEXT);
        telemetryHudLine.setId(R.id.live_telemetry_hud);
        telemetryHudLine.setTextColor(Color.rgb(188, 236, 255));
        telemetryHudLine.setMaxLines(2);
        telemetryHudLine.setEllipsize(android.text.TextUtils.TruncateAt.END);
        telemetryHudLine.setPadding(Ui.dp(this, 10), Ui.dp(this, 4), Ui.dp(this, 10), Ui.dp(this, 4));
        telemetryHudLine.setBackground(Ui.tonalPillDrawable(this, Color.argb(165, 10, 14, 24), Ui.CYAN, 14));
        telemetryHudLine.setClickable(true);
        telemetryHudLine.setOnClickListener(Ui.withHaptic(v -> onTelemetryHudTapped()));
        sensorHudBar.addView(telemetryHudLine, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));

        header.addView(sensorHudBar);
        root.addView(header);

        // Transparent touch-passthrough window over the full-screen camera/AR stage!
        fullScreenSpacer = new View(this);
        fullScreenSpacer.setClickable(false);
        fullScreenSpacer.setFocusable(false);
        fullScreenSpacer.setVisibility(View.GONE);
        root.addView(fullScreenSpacer, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Idle / Voice-Only Center Scroll (hidden during full-screen camera/AR so the camera owns the entire screen!)
        captionScroll = new ScrollView(this);
        captionScroll.setFillViewport(true);
        captionScroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout center = Ui.vertical(this);
        center.setBackgroundColor(Color.TRANSPARENT);
        center.setGravity(Gravity.CENTER_HORIZONTAL | Gravity.CENTER_VERTICAL);
        center.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 8));

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
        captionScroll.addView(center);
        root.addView(captionScroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Shared Bottom Translucent Overlay Column (State Badge + Caption + Quick Chips + Control Dock)
        LinearLayout bottomStack = Ui.vertical(this);
        bottomStack.setBackgroundColor(Color.TRANSPARENT);
        bottomStack.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 14));

        arTapHint = Ui.text(this, "Tap anywhere in your view to glide Zoe over", 11.5f, Ui.TEXT);
        arTapHint.setTextColor(Color.WHITE);
        arTapHint.setGravity(Gravity.CENTER);
        arTapHint.setPadding(Ui.dp(this, 12), Ui.dp(this, 4), Ui.dp(this, 12), Ui.dp(this, 4));
        arTapHint.setBackground(Ui.tonalPillDrawable(this, Color.argb(150, 10, 14, 24), Ui.CYAN, 14));
        LinearLayout.LayoutParams hintLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        hintLp.gravity = Gravity.CENTER_HORIZONTAL;
        hintLp.setMargins(0, 0, 0, Ui.dp(this, 6));
        arTapHint.setVisibility(View.GONE);
        bottomStack.addView(arTapHint, hintLp);

        stateBadge = Ui.text(this, "TAP ORB TO TALK · MIC & CAMERA OFF", 12f, Ui.COBALT);
        stateBadge.setId(R.id.live_state_badge);
        stateBadge.setTypeface(Ui.SANS_MEDIUM);
        stateBadge.setGravity(Gravity.CENTER);
        bottomStack.addView(stateBadge);

        captionView = Ui.text(this,
                "Hi, I'm Zoe. Tap the orb to talk, or tap Live + Cam for full-screen sight.",
                15f, Ui.TEXT);
        captionView.setId(R.id.live_caption_view);
        captionView.setGravity(Gravity.CENTER);
        captionView.setMaxLines(4);
        captionView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        captionView.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 12));
        captionView.setBackground(Ui.cardBackground(this, 20));
        LinearLayout.LayoutParams capLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        capLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 10));
        bottomStack.addView(captionView, capLp);

        // Quick actions row (✦ AR Space · Calm fact · Sing Zoe)
        quickChips = new LinearLayout(this);
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
        LinearLayout.LayoutParams qLp1 = new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f);
        qLp1.setMargins(0, 0, Ui.dp(this, 8), 0);
        LinearLayout.LayoutParams qLp2 = new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f);
        qLp2.setMargins(0, 0, Ui.dp(this, 8), 0);
        quickChips.addView(arToggleBtn, qLp1);
        quickChips.addView(q1, qLp2);
        quickChips.addView(q2, new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f));
        LinearLayout.LayoutParams qcLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        qcLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        bottomStack.addView(quickChips, qcLp);

        // Symmetric 3-button Bottom Control Dock (1:1:1 equal visual weight)
        LinearLayout dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);

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
        bottomStack.addView(dock);
        root.addView(bottomStack);

        stageRoot.addView(root, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        setContentView(stageRoot);
        Ui.configureEdgeToEdge(this, root);
        applyResponsiveGeometry(getResources().getConfiguration());
        updateFullScreenVisualMode();
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
        int orbSize = Ui.dp(this, landscape ? 132 : 212);
        if (orbView != null && orbView.getLayoutParams() != null) {
            orbView.getLayoutParams().width = orbSize;
            orbView.getLayoutParams().height = orbSize;
            orbView.requestLayout();
        }
        syncSpatialOverlayOptics(!landscape);
    }

    private void syncSpatialOverlayOptics(boolean portrait) {
        if (spatialTelemetry == null || spatialOverlayView == null) {
            return;
        }
        SpatialTelemetryFusion.CameraOptics optics = spatialTelemetry.getCameraOptics(portrait);
        spatialOverlayView.setVerticalFovRad(optics.activeFovRad(useFrontCamera));
    }

    private void updateFullScreenVisualMode() {
        boolean fullScreen = cameraOn || arModeOn;
        if (idleBackdrop != null) {
            idleBackdrop.setVisibility(fullScreen ? View.GONE : View.VISIBLE);
        }
        if (fullScreenMediaLayer != null) {
            fullScreenMediaLayer.setVisibility(fullScreen ? View.VISIBLE : View.GONE);
        }
        if (captionScroll != null) {
            captionScroll.setVisibility(fullScreen ? View.GONE : View.VISIBLE);
        }
        if (fullScreenSpacer != null) {
            fullScreenSpacer.setVisibility(fullScreen ? View.VISIBLE : View.GONE);
        }
        if (orbView != null) {
            orbView.setAnimationRunning(!fullScreen);
        }
        if (hudBar != null) {
            hudBar.setVisibility(fullScreen ? View.VISIBLE : View.GONE);
        }
        if (sensorHudBar != null) {
            sensorHudBar.setVisibility(fullScreen ? View.VISIBLE : View.GONE);
        }
        if (dualCamBtn != null) {
            dualCamBtn.setVisibility((cameraOn || (arModeOn && !useHeavyArCore6Dof)) ? View.VISIBLE : View.GONE);
        }
        if (arTapHint != null) {
            arTapHint.setVisibility(arModeOn ? View.VISIBLE : View.GONE);
            arTapHint.setText(useHeavyArCore6Dof
                    ? "6DoF ARCore · Tap any surface to anchor Zoe"
                    : "Spatial 60fps · Tap anywhere to glide Zoe over");
        }
        if (arModeBtn != null) {
            arModeBtn.setVisibility(arModeOn ? View.VISIBLE : View.GONE);
            arModeBtn.setText(useHeavyArCore6Dof ? "6DoF" : "Gyro 60");
        }
        if (arRoamBtn != null) {
            arRoamBtn.setVisibility(arModeOn ? View.VISIBLE : View.GONE);
        }
        if (arAskBtn != null) {
            arAskBtn.setVisibility(arModeOn ? View.VISIBLE : View.GONE);
        }
        if (lookNowBtn != null) {
            lookNowBtn.setVisibility(cameraOn && !arModeOn ? View.VISIBLE : View.GONE);
        }
        if (flipCamBtn != null) {
            flipCamBtn.setVisibility((cameraOn || (arModeOn && !useHeavyArCore6Dof)) ? View.VISIBLE : View.GONE);
        }
        if (captionView != null) {
            if (fullScreen) {
                captionView.setTextColor(Color.WHITE);
                captionView.setMaxLines(3);
                captionView.setBackground(Ui.tonalPillDrawable(this, Color.argb(178, 10, 14, 24), Ui.primaryAccent(this), 20));
            } else {
                captionView.setTextColor(Ui.textColor(this));
                captionView.setMaxLines(6);
                captionView.setBackground(Ui.cardBackground(this, 20));
            }
        }
        if (stateBadge != null && fullScreen) {
            stateBadge.setTextColor(Color.rgb(138, 224, 255));
        } else if (stateBadge != null) {
            stateBadge.setTextColor(Ui.resolveColor(this, Ui.COBALT));
        }
    }

    private Button chipButton(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(11.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMaxLines(1);
        b.setMinWidth(0);
        b.setMinimumWidth(0);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(Ui.dp(this, 10), 0, Ui.dp(this, 10), 0);
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

    // --- Full-Screen Spatial Companion (Default 60fps Gyro-Spatial + Optional Optimized 6DoF ARCore) ---

    private void toggleArSpace() {
        if (arModeOn) {
            stopArSpace();
            captionView.setText("Exited AR Space. Tap ✦ AR Space anytime to bring Zoe back into your view.");
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

    private void toggleArTrackingMode() {
        if (!arModeOn) {
            return;
        }
        boolean want6Dof = !useHeavyArCore6Dof;
        if (want6Dof && !ZoeArSurfaceView.isArCoreSupported(this)) {
            captionView.setText("Google Play Services for AR isn't available on this device — staying in smooth 60fps Spatial Glide!");
            return;
        }
        useHeavyArCore6Dof = want6Dof;
        boolean voiceWasOn = callActive;
        stopArEnginesOnly();
        startActiveArEngine();
        updateFullScreenVisualMode();
        styleHeaderPills();
        if (voiceWasOn) {
            setOrbState(currentOrbState, useHeavyArCore6Dof ? "AR 6DoF LIVE · TAP SURFACES" : "SPATIAL 60fps · EXPLORE & TALK");
        }
    }

    private void triggerArInstantLook() {
        if (!arModeOn) {
            return;
        }
        if (useHeavyArCore6Dof) {
            if (arSurfaceView != null) {
                arSurfaceView.requestInstantLook();
            }
        } else {
            Bitmap snap = getLatestCameraFrameCopy();
            if (snap != null) {
                handleArSpotInspection(snap, spatialOverlayView.getCurrentWorldPos(),
                        Math.max(0.8f, latestArDistanceMeters), true);
            } else {
                describeLiveViewProactively();
            }
        }
    }

    private void startArSpaceAndVoice(boolean withVoice) {
        stopArEnginesOnly();
        arBrain.clearSession();
        arModeOn = true;
        startActiveArEngine();
        cameraToggleBtn.setText(useHeavyArCore6Dof ? "Camera: 6DoF" : "Camera: AR");
        updateFullScreenVisualMode();
        styleHeaderPills();
        updateKeepScreenOn();
        if (!arModeOn) {
            return;
        }
        if (withVoice) {
            beginContinuousVoiceSession();
        } else {
            setOrbState(OrbState.IDLE, useHeavyArCore6Dof
                    ? "AR 6DoF ACTIVE · TAP ANY SURFACE"
                    : "SPATIAL 60fps · TAP ANYWHERE TO GLIDE ZOE");
            captionView.setText(useHeavyArCore6Dof
                    ? "Optimized ARCore 6DoF active. Move gently to map floors/tables, or switch back to Gyro 60 anytime."
                    : "Full-screen 60fps Spatial Zoe active! Pan around your room or tap anywhere to glide Zoe over.");
        }
    }

    private void startActiveArEngine() {
        if (!useHeavyArCore6Dof) {
            // DEFAULT: Zero-lag 60fps Hardware CameraX Preview + Hardware IMU Quaternion 3D Companion!
            arSurfaceHost.setVisibility(View.GONE);
            cameraPreview.setVisibility(View.VISIBLE);
            spatialOverlayView.setVisibility(View.VISIBLE);
            spatialOverlayView.setAutonomousRoam(arRoamEnabled);
            spatialOverlayView.setFrontCameraMirrored(useFrontCamera);
            syncSpatialOverlayOptics(getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
            spatialOverlayView.setLightField(spatialTelemetry.getLightField());
            spatialOverlayView.setActive(true);
            liveHudPill.setText("● 60fps · 1.2m");
            if (!cameraOn) {
                cameraOn = true;
                cameraPreview.post(this::bindCameraPreview);
            }
            return;
        }
        // OPTIONAL: Optimized ARCore 6DoF (horizontal planes only, async off-GL-thread snapshots!)
        if (cameraOn) {
            unbindCameraPreviewOnly();
        }
        spatialOverlayView.setActive(false);
        spatialOverlayView.setVisibility(View.GONE);
        cameraPreview.setVisibility(View.GONE);
        arSurfaceHost.removeAllViews();
        arSurfaceHost.setVisibility(View.VISIBLE);
        arSurfaceView = new ZoeArSurfaceView(this, arBrain, new ZoeArSurfaceView.Listener() {
            @Override
            public void onArTrackingUpdate(int planeCount, float zoeDistMeters, String statusHint) {
                latestArDistanceMeters = zoeDistMeters;
                if (arModeOn && useHeavyArCore6Dof && !isFinishing() && !isDestroyed()) {
                    liveHudPill.setText(statusHint);
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
                    useHeavyArCore6Dof = false;
                    stopArEnginesOnly();
                    startActiveArEngine();
                    updateFullScreenVisualMode();
                    styleHeaderPills();
                    captionView.setText(reason + " Switched automatically to ultra-smooth 60fps Spatial Glide!");
                }
            }
        });
        arSurfaceHost.addView(arSurfaceView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        arSurfaceView.setAutonomousRoam(arRoamEnabled);
        liveHudPill.setText("● AR 6DoF · Scanning…");
        arSurfaceView.startArSession();
    }

    private void stopArEnginesOnly() {
        if (spatialOverlayView != null) {
            spatialOverlayView.setActive(false);
            spatialOverlayView.setVisibility(View.GONE);
        }
        if (arSurfaceView != null) {
            arSurfaceView.stopArSession();
            arSurfaceView = null;
        }
        if (arSurfaceHost != null) {
            arSurfaceHost.removeAllViews();
            arSurfaceHost.setVisibility(View.GONE);
        }
    }

    private void stopArSpace() {
        arModeOn = false;
        stopSpatialTelemetry();
        stopArEnginesOnly();
        if (cameraOn) {
            unbindCameraPreviewOnly();
        }
        cameraToggleBtn.setText("Camera: off");
        updateFullScreenVisualMode();
        styleHeaderPills();
        updateKeepScreenOn();
    }

    // --- Opt-In Multi-Sensor Spatial Telemetry (CERN Kloster A_tau/M4 · Dual-Cam Light-Field · ENU/Google Earth · Acoustic Echo · RF) ---

    private void toggleSpatialField() {
        if (spatialFieldOn) {
            stopSpatialTelemetry();
            captionView.setText("Spatial Telemetry Field turned off. All extra sensors released.");
            return;
        }
        spatialFieldOn = true;
        fieldToggleBtn.setText("Field: on");
        fieldToggleBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(205, 18, 96, 84), Ui.GREEN, 15));
        telemetryHudLine.setText("Fusing IMU · CERN Aτ/M₄ · RF · Light-Field…");
        spatialTelemetry.start();
        if (spatialOverlayView != null) {
            spatialTelemetry.updateImuStability(spatialOverlayView.getImuStability());
        }
        captionView.setText("Spatial Field ON (local-only, zero PII): fusing IMU, CERN Kloster Aτ/M₄, optical light-field, Wi-Fi/BLE/Cell signal, and opt-in ENU grid.");
    }

    private void stopSpatialTelemetry() {
        spatialFieldOn = false;
        dualCamSweepPending = false;
        latestSpatialContext = "";
        if (spatialTelemetry != null) {
            spatialTelemetry.stop();
        }
        if (fieldToggleBtn != null) {
            fieldToggleBtn.setText("Field: off");
            fieldToggleBtn.setBackground(Ui.tonalPillDrawable(this, Color.argb(175, 16, 22, 34), Ui.CYAN, 15));
        }
        if (telemetryHudLine != null) {
            telemetryHudLine.setText("Tap Field for CERN Aτ/M₄ + RF + ENU · Tap here for Echo/Earth");
        }
    }

    private void onSpatialTelemetryUpdated(SpatialTelemetryFusion.FusedFieldSnapshot snap) {
        if (!spatialFieldOn || snap == null || isFinishing() || isDestroyed()) {
            return;
        }
        if (spatialOverlayView != null) {
            spatialTelemetry.updateImuStability(spatialOverlayView.getImuStability());
            spatialOverlayView.setLightField(snap.lightField);
            spatialOverlayView.setSpatialCoherence(snap.spatialCoherence);
            spatialOverlayView.setPreferredHoverDepth(snap.suggestedDepthMeters);
        }
        latestSpatialContext = snap.voiceContextLine;
        runOnUiThread(() -> {
            if (spatialFieldOn && telemetryHudLine != null && !isFinishing() && !isDestroyed()) {
                telemetryHudLine.setText(snap.compactHudLine);
            }
        });
    }

    /**
     * Optional 1-tap Dual-Camera Ambient Light-Field Calibration:
     * Briefly samples the front camera (what is BEHIND you) for ~420ms without running two continuous streams,
     * computes front-vs-rear luminance & warmth, adapts Zoe's 3D rim lighting, and flips straight back!
     */
    private void runDualCamAmbientSweep() {
        if (!cameraOn || (arModeOn && useHeavyArCore6Dof)) {
            captionView.setText("Dual-Cam Light-Field sweep works in full-screen Camera or Gyro 60 Spatial mode.");
            return;
        }
        if (dualCamSweepPending) {
            return;
        }
        Bitmap curRear = getLatestCameraFrameCopy();
        if (curRear != null) {
            if (useFrontCamera) {
                spatialTelemetry.sampleFrontBitmapForBacklight(curRear);
            } else {
                spatialTelemetry.sampleRearBitmap(curRear);
            }
            curRear.recycle();
        }
        dualCamReturnToBack = !useFrontCamera;
        dualCamSweepPending = true;
        useFrontCamera = !useFrontCamera;
        if (spatialOverlayView != null) {
            spatialOverlayView.setFrontCameraMirrored(useFrontCamera);
            syncSpatialOverlayOptics(getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
        }
        captionView.setText("Sampling opposite lens light-field behind you (zero continuous dual-stream load)…");
        bindCameraPreview();
        // Safety fallback in case front camera is unavailable on an emulator/device
        mainHandler.postDelayed(() -> {
            if (dualCamSweepPending && !isFinishing() && !isDestroyed()) {
                completeDualCamSweep();
            }
        }, 1600L);
    }

    private void completeDualCamSweep() {
        if (!dualCamSweepPending) {
            return;
        }
        dualCamSweepPending = false;
        useFrontCamera = !dualCamReturnToBack;
        if (spatialOverlayView != null) {
            spatialOverlayView.setFrontCameraMirrored(useFrontCamera);
            syncSpatialOverlayOptics(getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
            spatialOverlayView.setLightField(spatialTelemetry.getLightField());
        }
        if (cameraOn) {
            bindCameraPreview();
        }
        SpatialTelemetryFusion.LightFieldState lf = spatialTelemetry.getLightField();
        SpatialTelemetryFusion.CameraOptics op = spatialTelemetry.getCameraOptics(
                getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
        captionView.setText(String.format(Locale.US,
                "Dual-Cam Light-Field calibrated! Ahead %.0f%% · Behind %.0f%% (backlight %.2fx, rear %.1fmm / front %.1fmm). Zoe's rim lighting adapted.",
                lf.rearLuma * 100f, lf.frontLuma * 100f, lf.backlightRatio, op.rearFocalMm, op.frontFocalMm));
    }

    private void onTelemetryHudTapped() {
        Location loc = spatialTelemetry != null ? spatialTelemetry.getLatestLocation() : null;
        if (loc != null) {
            try {
                String url = SpatialTelemetryFusion.buildGoogleEarthUrl(
                        loc.getLatitude(), loc.getLongitude(),
                        loc.hasAltitude() ? loc.getAltitude() : 10.0,
                        spatialTelemetry.getCompassDegrees());
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
                return;
            } catch (Exception ignored) {
                try {
                    String geo = String.format(Locale.US, "geo:%.6f,%.6f?q=%.6f,%.6f(Zoe+Explore)",
                            loc.getLatitude(), loc.getLongitude(), loc.getLatitude(), loc.getLongitude());
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(geo)));
                    return;
                } catch (Exception ignored2) {
                }
            }
        }
        triggerAcousticEchoPing();
    }

    private void triggerAcousticEchoPing() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            captionView.setText("Enable Field + Location for Google Earth ENU grid, or allow Mic for an Acoustic Echo depth ping.");
            return;
        }
        if (!acousticPingBusy.compareAndSet(false, true)) {
            return;
        }
        captionView.setText("Sending brief 1.8 kHz acoustic echo ping to gauge nearby room depth…");
        executor.execute(() -> {
            final int sr = 44100;
            AudioRecord recorder = null;
            AudioTrack track = null;
            try {
                short[] chirp = AcousticRanging.chirp(sr, 1800.0, 0.020, 0.16);
                int recSamples = sr / 3;
                int minBuf = Math.max(AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT), recSamples * 2);
                recorder = new AudioRecord(MediaRecorder.AudioSource.MIC, sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf);
                track = new AudioTrack.Builder()
                        .setAudioAttributes(new AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                                .build())
                        .setAudioFormat(new AudioFormat.Builder()
                                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                .setSampleRate(sr)
                                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                                .build())
                        .setBufferSizeInBytes(Math.max(chirp.length * 2, 4096))
                        .setTransferMode(AudioTrack.MODE_STATIC)
                        .build();
                track.write(chirp, 0, chirp.length);
                short[] buf = new short[recSamples];
                recorder.startRecording();
                track.play();
                int offset = 0;
                while (offset < buf.length) {
                    int n = recorder.read(buf, offset, Math.min(2048, buf.length - offset));
                    if (n <= 0) {
                        break;
                    }
                    offset += n;
                }
                AcousticRanging.Measurement m = AcousticRanging.analyze(buf, chirp, sr);
                if (m.candidateDistanceMeters != null && m.candidateDistanceMeters > 0.25 && m.candidateDistanceMeters < 6.0) {
                    float distM = m.candidateDistanceMeters.floatValue();
                    spatialTelemetry.recordAcousticEchoDistance(distM);
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            captionView.setText(String.format(Locale.US,
                                    "Acoustic echo cue: ~%.2fm reflection (RMS %.1f dBFS). Zoe adjusted spatial hover depth!",
                                    distM, m.rmsDbfs));
                        }
                    });
                } else {
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            captionView.setText(String.format(Locale.US,
                                    "Ambient acoustic level: %.1f dBFS (no distinct close wall echo detected).",
                                    m.rmsDbfs));
                        }
                    });
                }
            } catch (RuntimeException err) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        captionView.setText("Acoustic echo ping skipped: " + err.getMessage());
                    }
                });
            } finally {
                if (recorder != null) {
                    try {
                        recorder.stop();
                    } catch (Exception ignored) {
                    }
                    recorder.release();
                }
                if (track != null) {
                    try {
                        track.stop();
                    } catch (Exception ignored) {
                    }
                    track.release();
                }
                acousticPingBusy.set(false);
            }
        });
    }

    private void toggleArRoam() {
        arRoamEnabled = !arRoamEnabled;
        if (spatialOverlayView != null) {
            spatialOverlayView.setAutonomousRoam(arRoamEnabled);
        }
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
        if (spatialOverlayView != null) {
            spatialOverlayView.setFrontCameraMirrored(useFrontCamera);
            syncSpatialOverlayOptics(getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
        }
        if (cameraOn) {
            bindCameraPreview();
        }
    }

    private void startCamera() {
        cameraOn = true;
        cameraToggleBtn.setText("Camera: on");
        cameraPreview.setVisibility(View.VISIBLE);
        updateFullScreenVisualMode();
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

                // Zero-main-thread-stall background ImageAnalysis (replaces slow PreviewView.getBitmap()!)
                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setTargetResolution(new Size(480, 360))
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build();
                analysis.setAnalyzer(cameraAnalysisExecutor, this::cacheLatestImageProxy);

                CameraSelector selector = useFrontCamera
                        ? CameraSelector.DEFAULT_FRONT_CAMERA
                        : CameraSelector.DEFAULT_BACK_CAMERA;
                cameraProvider.bindToLifecycle(this, selector, preview, analysis);
                if (!arModeOn) {
                    liveHudPill.setText("● LIVE SIGHT · FULL SCREEN");
                    if (!callActive) {
                        captionView.setText("Full-screen live sight active! Tap Talk Now or Look anytime.");
                    }
                }
                mainHandler.removeCallbacks(cameraObserverTick);
                mainHandler.postDelayed(cameraObserverTick, 1200L);
            } catch (Exception error) {
                liveHudPill.setText("CAMERA UNAVAILABLE");
                captionView.setText("Camera unavailable: " + error.getMessage());
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void cacheLatestImageProxy(@NonNull ImageProxy proxy) {
        try {
            long now = System.currentTimeMillis();
            // Throttle background YUV->Bitmap caching to ~2fps (500ms) so camera preview stays locked at 60/90fps!
            if (now - lastCameraBitmapMs < 500L) {
                return;
            }
            Bitmap upright = imageProxyToCompactBitmap(proxy);
            if (upright != null) {
                lastCameraBitmapMs = now;
                if (dualCamSweepPending) {
                    if (useFrontCamera) {
                        spatialTelemetry.sampleFrontBitmapForBacklight(upright);
                    } else {
                        spatialTelemetry.sampleRearBitmap(upright);
                    }
                    mainHandler.post(this::completeDualCamSweep);
                } else if (spatialFieldOn) {
                    if (useFrontCamera) {
                        spatialTelemetry.sampleFrontBitmapForBacklight(upright);
                    } else {
                        spatialTelemetry.sampleRearBitmap(upright);
                    }
                }
                synchronized (latestCamFrameLock) {
                    if (latestCameraBitmap != null && !latestCameraBitmap.isRecycled()) {
                        latestCameraBitmap.recycle();
                    }
                    latestCameraBitmap = upright;
                }
            }
        } catch (Throwable ignored) {
        } finally {
            proxy.close();
        }
    }

    private Bitmap getLatestCameraFrameCopy() {
        synchronized (latestCamFrameLock) {
            if (latestCameraBitmap != null && !latestCameraBitmap.isRecycled()) {
                return latestCameraBitmap.copy(Bitmap.Config.ARGB_8888, false);
            }
            return null;
        }
    }

    private static Bitmap imageProxyToCompactBitmap(ImageProxy proxy) {
        if (proxy == null || proxy.getFormat() != ImageFormat.YUV_420_888) {
            return null;
        }
        int w = proxy.getWidth();
        int h = proxy.getHeight();
        int step = Math.max(1, Math.max(w, h) / 360);
        int outW = Math.max(1, w / step);
        int outH = Math.max(1, h / step);
        ImageProxy.PlaneProxy[] planes = proxy.getPlanes();
        ByteBuffer yBuf = planes[0].getBuffer();
        ByteBuffer uBuf = planes[1].getBuffer();
        ByteBuffer vBuf = planes[2].getBuffer();
        int yRS = planes[0].getRowStride(), yPS = planes[0].getPixelStride(), yLim = yBuf.limit();
        int uRS = planes[1].getRowStride(), uPS = planes[1].getPixelStride(), uLim = uBuf.limit();
        int vRS = planes[2].getRowStride(), vPS = planes[2].getPixelStride(), vLim = vBuf.limit();

        int[] pixels = new int[outW * outH];
        int dst = 0;
        for (int oy = 0; oy < outH; oy++) {
            int sy = oy * step;
            int yRow = sy * yRS;
            int uRow = (sy >> 1) * uRS;
            int vRow = (sy >> 1) * vRS;
            for (int ox = 0; ox < outW; ox++) {
                int sx = ox * step;
                int yo = yRow + sx * yPS;
                int uo = uRow + (sx >> 1) * uPS;
                int vo = vRow + (sx >> 1) * vPS;
                int yVal = yo < yLim ? (yBuf.get(yo) & 0xFF) : 0;
                int uVal = uo < uLim ? ((uBuf.get(uo) & 0xFF) - 128) : 0;
                int vVal = vo < vLim ? ((vBuf.get(vo) & 0xFF) - 128) : 0;
                int r = Math.max(0, Math.min(255, yVal + ((351 * vVal) >> 8)));
                int g = Math.max(0, Math.min(255, yVal - ((179 * vVal + 86 * uVal) >> 8)));
                int b = Math.max(0, Math.min(255, yVal + ((443 * uVal) >> 8)));
                pixels[dst++] = 0xFF000000 | (r << 16) | (g << 8) | b;
            }
        }
        Bitmap raw = Bitmap.createBitmap(pixels, outW, outH, Bitmap.Config.ARGB_8888);
        int rot = proxy.getImageInfo().getRotationDegrees();
        if (rot == 0) {
            return raw;
        }
        Matrix m = new Matrix();
        m.postRotate(rot);
        Bitmap rotated = Bitmap.createBitmap(raw, 0, 0, raw.getWidth(), raw.getHeight(), m, true);
        if (rotated != raw) {
            raw.recycle();
        }
        return rotated;
    }

    private void unbindCameraPreviewOnly() {
        cameraOn = false;
        mainHandler.removeCallbacks(cameraObserverTick);
        if (cameraProvider != null) {
            try {
                cameraProvider.unbindAll();
            } catch (Exception ignored) {
            }
        }
        synchronized (latestCamFrameLock) {
            if (latestCameraBitmap != null && !latestCameraBitmap.isRecycled()) {
                latestCameraBitmap.recycle();
            }
            latestCameraBitmap = null;
        }
    }

    private void stopCamera() {
        stopSpatialTelemetry();
        unbindCameraPreviewOnly();
        latestCameraReport = "";
        latestCameraJpeg = null;
        cameraToggleBtn.setText("Camera: off");
        updateFullScreenVisualMode();
        styleHeaderPills();
        updateKeepScreenOn();
    }

    private void captureBackgroundCameraFrame() {
        if (!cameraOn || !cameraAnalysisBusy.compareAndSet(false, true)) {
            return;
        }
        Bitmap frame = getLatestCameraFrameCopy();
        if (frame == null) {
            cameraAnalysisBusy.set(false);
            return;
        }
        executor.execute(() -> {
            try {
                String report = MediaChatHelper.inspectFrameOffline(frame);
                String learnedHint = VisionPriorStore.buildSilentExploreContext(this, frame);
                latestCameraReport = learnedHint.isEmpty() ? report : (report + " " + learnedHint);
            } catch (Exception ignored) {
            } finally {
                if (!frame.isRecycled()) {
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
        Bitmap frame = getLatestCameraFrameCopy();
        if (frame == null && latestCameraReport.isEmpty()) {
            captionView.setText("Waiting for camera preview frame — try tapping Look again.");
            return;
        }
        long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "Look at my camera view";
        setOrbState(OrbState.THINKING, "LOOKING AT YOUR VIEW…");
        captionView.setText("Looking closely at what's in front of your camera…");
        executor.execute(() -> {
            Bitmap working = frame;
            if (working != null) {
                try {
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
                    if (arModeOn && !useHeavyArCore6Dof && spatialOverlayView != null) {
                        spatialOverlayView.setVoiceLevel(norm);
                    }
                    if (spatialFieldOn && spatialTelemetry != null) {
                        spatialTelemetry.updateAcousticLevel(norm);
                    }
                    if (arSurfaceView != null && arModeOn && useHeavyArCore6Dof) {
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

        // Capture a fresh live frame right now from either Live Camera, Spatial 60fps, OR ARCore 6DoF (zero UI stall!)
        final Bitmap freshFrame = cameraOn
                ? getLatestCameraFrameCopy()
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
        String fieldCtx = spatialFieldOn ? latestSpatialContext : "";
        StringBuilder camCtx = new StringBuilder();
        if (withCamera) {
            if (latestCameraReport != null && !latestCameraReport.isEmpty()) {
                camCtx.append(latestCameraReport);
            }
            if (!roomMem.isEmpty()) {
                if (camCtx.length() > 0) camCtx.append(" ");
                camCtx.append(roomMem);
            }
            if (!fieldCtx.isEmpty()) {
                if (camCtx.length() > 0) camCtx.append(" ");
                camCtx.append(fieldCtx);
            }
        }
        String camReport = camCtx.toString().trim();
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
        ZoeArSurfaceView.VisualMood arMood = switch (state) {
            case LISTENING -> ZoeArSurfaceView.VisualMood.LISTENING;
            case THINKING -> ZoeArSurfaceView.VisualMood.THINKING;
            case SPEAKING -> ZoeArSurfaceView.VisualMood.SPEAKING;
            default -> ZoeArSurfaceView.VisualMood.EXPLORING;
        };
        if (arModeOn && !useHeavyArCore6Dof && spatialOverlayView != null) {
            spatialOverlayView.setVisualMood(arMood);
            if (state != OrbState.LISTENING) {
                spatialOverlayView.setVoiceLevel(state == OrbState.SPEAKING ? 0.55f : 0f);
            }
        }
        if (arSurfaceView != null && arModeOn && useHeavyArCore6Dof) {
            arSurfaceView.setVisualMood(arMood);
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
        cameraAnalysisExecutor.shutdownNow();
        executor.shutdownNow();
    }

    /**
     * Smooth 60fps Audio-Reactive Iridescent GEM Aurora Orb (Apple Intelligence / Gemini Live craft).
     * Zero-allocation per-frame drawing (pre-allocated Paint, Path, and RectF buffers).
     */
    private static final class LiveOrbView extends View {
        private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint auroraPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint ringPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint glassRimPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint gemPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint gemFacetPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint motePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Path diamondPath = new Path();
        private final Path facetPath = new Path();
        private final android.graphics.RectF oval = new android.graphics.RectF();
        private final ValueAnimator animator;
        private float phase;
        private float targetLevel;
        private float smoothLevel;
        private boolean speakingPulse;
        private OrbState state = OrbState.IDLE;
        private int cachedGradColor = -1;
        private float cachedGradRadius = -1f;

        LiveOrbView(Context context) {
            super(context);
            ringPaint.setStyle(Paint.Style.STROKE);
            auroraPaint.setStyle(Paint.Style.STROKE);
            auroraPaint.setStrokeCap(Paint.Cap.ROUND);
            glassRimPaint.setStyle(Paint.Style.STROKE);
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(4800L);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setInterpolator(new LinearInterpolator());
            animator.addUpdateListener(a -> {
                phase = (float) a.getAnimatedValue();
                float desired = speakingPulse
                        ? (0.38f + 0.28f * (float) Math.abs(Math.sin(phase * Math.PI * 10.0)))
                        : targetLevel;
                smoothLevel += (desired - smoothLevel) * 0.22f;
                invalidate();
            });
            animator.start();
        }

        void setAnimationRunning(boolean running) {
            if (running) {
                if (animator.isPaused()) {
                    animator.resume();
                } else if (!animator.isStarted()) {
                    animator.start();
                }
            } else if (animator.isRunning()) {
                animator.pause();
            }
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
            if (maxR <= 0f) {
                return;
            }
            float d = getResources().getDisplayMetrics().density;
            float breathe = (float) Math.sin(phase * Math.PI * 2.0);
            float deg = phase * 360f;

            int cCore;
            int cMid;
            int cOuter;
            switch (state) {
                case LISTENING -> {
                    cCore = Color.rgb(66, 224, 174);
                    cMid = Color.rgb(72, 184, 255);
                    cOuter = Color.rgb(120, 112, 255);
                }
                case THINKING -> {
                    cCore = Color.rgb(252, 202, 102);
                    cMid = Color.rgb(186, 128, 255);
                    cOuter = Color.rgb(88, 166, 255);
                }
                case SPEAKING -> {
                    cCore = Color.rgb(248, 104, 146);
                    cMid = Color.rgb(176, 122, 255);
                    cOuter = Color.rgb(86, 166, 255);
                }
                default -> {
                    cCore = Color.rgb(104, 168, 255);
                    cMid = Color.rgb(178, 126, 252);
                    cOuter = Color.rgb(66, 208, 186);
                }
            }

            float radius = maxR * (0.60f + 0.05f * breathe + 0.16f * smoothLevel);

            // 1. Deep multi-stop atmospheric aura glow (cached per state & radius — zero per-frame allocation!)
            if (cachedGradColor != cCore || Math.abs(cachedGradRadius - maxR) > 1f) {
                cachedGradColor = cCore;
                cachedGradRadius = maxR;
                haloPaint.setShader(new RadialGradient(cx, cy, maxR,
                        new int[]{
                                Color.argb(210, Color.red(cCore), Color.green(cCore), Color.blue(cCore)),
                                Color.argb(105, Color.red(cMid), Color.green(cMid), Color.blue(cMid)),
                                Color.argb(52, Color.red(cOuter), Color.green(cOuter), Color.blue(cOuter)),
                                Color.TRANSPARENT},
                        new float[]{0.14f, 0.44f, 0.72f, 1.0f}, Shader.TileMode.CLAMP));
            }
            canvas.drawCircle(cx, cy, maxR, haloPaint);

            // 2. Iridescent counter-rotating fluid aurora ribbons
            int[] ribbonCols = {cCore, cMid, cOuter};
            for (int i = 0; i < 3; i++) {
                canvas.save();
                float rot = (i % 2 == 0 ? deg : -deg * 0.75f) + i * 58f;
                canvas.rotate(rot, cx, cy);
                float rx = radius * (0.86f + 0.07f * (float) Math.sin((phase + i * 0.33) * Math.PI * 2.0));
                float ry = radius * (0.62f + 0.06f * (float) Math.cos((phase + i * 0.33) * Math.PI * 2.0));
                oval.set(cx - rx, cy - ry, cx + rx, cy + ry);
                int col = ribbonCols[i];
                auroraPaint.setColor(Color.argb(115 + (int) (smoothLevel * 80), Color.red(col), Color.green(col), Color.blue(col)));
                auroraPaint.setStrokeWidth((2.4f + smoothLevel * 1.8f) * d);
                canvas.drawOval(oval, auroraPaint);
                canvas.restore();
            }

            // 3. Expanding harmonic pulse ripples
            for (int i = 0; i < 3; i++) {
                float p = (phase + i / 3f) % 1f;
                float r = radius * 0.56f + p * (maxR * 0.96f - radius * 0.56f);
                ringPaint.setStrokeWidth((2.2f * (1f - p) + 0.8f) * d);
                ringPaint.setColor(Color.argb((int) ((1f - p) * 135), Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
                canvas.drawCircle(cx, cy, r, ringPaint);
            }

            // 4. Translucent glass lens rim
            glassRimPaint.setStrokeWidth(1.2f * d);
            glassRimPaint.setColor(Color.argb(110, 240, 246, 255));
            canvas.drawCircle(cx, cy, radius * 0.68f, glassRimPaint);

            // 5. Orbiting starlight motes
            for (int i = 0; i < 6; i++) {
                double a = (phase * Math.PI * 2.0) * (i % 2 == 0 ? 1.0 : -0.65) + i * (Math.PI / 3.0);
                float dist = radius * (0.76f + 0.14f * (float) Math.sin(phase * Math.PI * 4.0 + i));
                float mx = cx + (float) Math.cos(a) * dist;
                float my = cy + (float) Math.sin(a) * dist;
                int mCol = ribbonCols[i % 3];
                motePaint.setColor(Color.argb(175, Color.red(mCol), Color.green(mCol), Color.blue(mCol)));
                canvas.drawCircle(mx, my, (1.8f + (i % 2) * 0.9f) * d, motePaint);
            }

            // 6. Faceted luminous Zoe GEM diamond core
            float g = radius * 0.34f;
            diamondPath.reset();
            diamondPath.moveTo(cx, cy - g);
            diamondPath.lineTo(cx + g * 0.86f, cy);
            diamondPath.lineTo(cx, cy + g);
            diamondPath.lineTo(cx - g * 0.86f, cy);
            diamondPath.close();
            gemPaint.setColor(cCore);
            canvas.drawPath(diamondPath, gemPaint);

            // Bright top-left prism facet highlight
            facetPath.reset();
            facetPath.moveTo(cx, cy - g);
            facetPath.lineTo(cx + g * 0.86f, cy);
            facetPath.lineTo(cx, cy - g * 0.10f);
            facetPath.lineTo(cx - g * 0.86f, cy);
            facetPath.close();
            gemFacetPaint.setColor(Color.argb(135, 255, 255, 255));
            canvas.drawPath(facetPath, gemFacetPaint);
        }
    }
}
