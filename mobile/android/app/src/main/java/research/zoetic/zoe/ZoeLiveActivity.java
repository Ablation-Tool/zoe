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
import android.text.TextUtils;
import android.util.Size;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.view.animation.LinearInterpolator;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
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
 * Zoe Explore — Calm, Full-Screen Sight, 60fps Spatial AR & Inclusive Accessibility Companion (v0.9.7-beta).
 *
 * Design principles:
 *   - Focus on what is happening on screen: 90% unobstructed edge-to-edge live camera + floating Zoe GEM,
 *     minimal floating top bar (Back, status dot, Flip, Tools/Accessibility ⚙), and a 3-button dock.
 *   - All advanced tools (AR 6DoF, Multi-Sensor CERN Kloster Field, Dual-Cam Light-Field, Acoustic Echo,
 *     Google Earth, Hi Zoe, Web, Voice engine) live cleanly inside the 1-tap Tools & Accessibility drawer.
 *   - Built-in Accessibility Modes for Deaf / Hard-of-Hearing kids & adults, Blind / Low-Vision kids & adults,
 *     and Kid-Friendly mode (big high-contrast captions, visual sound radar, tactile haptic patterns,
 *     silent Type-to-Zoe bar, stereo L/R spatial audio beacons, clock-face navigation & full-screen gestures).
 *   - Privacy-first (CONSTITUTION.md): mic, camera, AR, and all spatial sensors start strictly OFF until tapped.
 */
public final class ZoeLiveActivity extends ComponentActivity {
    private static final int PERM_REQ = 84;
    private static final long CAMERA_REFRESH_INTERVAL_MS = 4_500L;
    private static final long ECHO_GUARD_MS = 480L;
    private static final long CAPTION_IDLE_FADE_MS = 6_500L;

    private enum OrbState {
        IDLE,
        LISTENING,
        THINKING,
        SPEAKING
    }

    private enum PendingAction {
        NONE,
        START_VOICE_ONLY,
        START_AR_SPACE,
        START_HIZOE,
        START_CAMERA_ONLY,
        START_SPATIAL_FIELD
    }

    private final ExecutorService executor = Executors.newCachedThreadPool();
    private final ExecutorService cameraAnalysisExecutor = Executors.newSingleThreadExecutor();
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final AtomicLong activeTurnId = new AtomicLong(0L);
    private final AtomicLong listenGen = new AtomicLong(0L);
    private final AtomicLong arStartGen = new AtomicLong(0L);
    private final AtomicBoolean cameraAnalysisBusy = new AtomicBoolean(false);
    private final AtomicBoolean acousticPingBusy = new AtomicBoolean(false);
    private final Object latestCamFrameLock = new Object();
    private Bitmap latestCameraBitmap;
    private long lastCameraBitmapMs;
    private final ArExploreBrain arBrain = new ArExploreBrain();
    private SpatialTelemetryCollector spatialTelemetry;
    private ExploreAccessibility.Settings a11y;

    private ZoeBrainEngine brain;
    private ZoeNativeVoice nativeVoice;
    private OnDeviceLlmEngine localLlm;
    private final List<ChatHistoryStore.ChatMessage> sessionHistory = new ArrayList<>();

    // Minimal Full-Screen Stage & Chrome
    private ZoeBackdropView idleBackdrop;
    private FrameLayout fullScreenMediaLayer;
    private PreviewView cameraPreview;
    private ZoeSpatialOverlayView spatialOverlayView;
    private FrameLayout arSurfaceHost;
    private ZoeArSurfaceView arSurfaceView;
    private View topScrim;
    private View bottomScrim;

    private TextView liveHudPill;
    private Button flipCamBtn;
    private Button toolsBtn;
    private ScrollView idleCenterHost;
    private View fullScreenSpacer;
    private LiveOrbView orbView;
    private TextView stateBadge;
    private TextView captionView;
    private LinearLayout typeBar;
    private EditText typeInput;
    private Button typeSendBtn;
    private Button arToggleBtn;
    private Button listenBtn;
    private Button stopBtn;

    // 1-Tap Slide-Up Tools & Accessibility Drawer (keeps main screen 100% calm & focused!)
    private FrameLayout toolsBackdrop;
    private ScrollView toolsSheet;
    private TextView a11ySummaryView;
    private Button a11yStandardBtn;
    private Button a11yDeafBtn;
    private Button a11yBlindBtn;
    private Button a11yKidBtn;
    private Button optBigCaptionsBtn;
    private Button optHapticsBtn;
    private Button optSoundRadarBtn;
    private Button optAudioSonarBtn;
    private Button optTypeBarBtn;

    private Button cameraToggleBtn;
    private Button arModeBtn;
    private Button arRoamBtn;
    private Button lookNowBtn;
    private Button fieldToggleBtn;
    private Button dualCamBtn;
    private TextView telemetryHudLine;
    private Button hiZoeToggleBtn;
    private Button webToggleBtn;
    private Button voiceModeBtn;

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
    private boolean toolsOpen;
    private volatile boolean dualCamSweepPending;
    private volatile boolean dualCamCaptureArmed;
    private final AtomicInteger dualCamWarmupFrames = new AtomicInteger(0);
    private boolean dualCamReturnToBack;
    private boolean webOn;
    private boolean hiZoeWakeMode;
    private boolean useNativeVoice;
    private boolean callActive;
    private boolean preferDeviceRecognizer = true;
    private int consecutiveErrors;
    private long lastSoundAlertHapticMs;
    private volatile OrbState currentOrbState = OrbState.IDLE;

    private volatile String latestCameraReport = "";
    private volatile String latestSpatialContext = "";
    private volatile byte[] latestCameraJpeg;
    private volatile float latestArDistanceMeters = 1.2f;
    private String pendingSpeechOnReady = "";
    private String lastUserSpoken = "";
    private final AtomicInteger pendingTtsChunks = new AtomicInteger(0);
    private volatile boolean streamCompletedForCurrentTurn = true;

    private final Runnable hideIdleCaptionTask = () -> {
        if ((cameraOn || arModeOn) && !a11y.largeCaptions && currentOrbState == OrbState.IDLE && captionView != null) {
            captionView.animate().alpha(0f).setDuration(260L).withEndAction(() -> {
                if ((cameraOn || arModeOn) && !a11y.largeCaptions && currentOrbState == OrbState.IDLE) {
                    captionView.setVisibility(View.GONE);
                    captionView.setAlpha(1f);
                }
            }).start();
        }
    };

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
        a11y = ExploreAccessibility.load(this);
        spatialTelemetry = new SpatialTelemetryCollector(this, this::onSpatialTelemetryUpdated);

        // Pre-warm offline vision + local LLM in background (zero UI thread work)
        executor.execute(() -> {
            MediaChatHelper.warmUp();
            VisionPriorStore.loadAll(this);
            VisionPriorStore.loadBaselineAtlas(this);
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (localModel != null) {
                localLlm.warmUp(localModel);
            }
        });

        FrameLayout stageRoot = new FrameLayout(this);
        stageRoot.setBackgroundColor(Ui.bgColor(this));

        // Layer 0: Atmospheric backdrop (hidden when full-screen camera/AR runs)
        idleBackdrop = new ZoeBackdropView(this);
        stageRoot.addView(idleBackdrop, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Layer 1: TRUE EDGE-TO-EDGE FULL-SCREEN CAMERA + 60fps SPATIAL ZOE / 6DoF ARCORE
        fullScreenMediaLayer = new FrameLayout(this);
        fullScreenMediaLayer.setBackgroundColor(Color.BLACK);
        fullScreenMediaLayer.setVisibility(View.GONE);

        cameraPreview = new PreviewView(this);
        cameraPreview.setImplementationMode(PreviewView.ImplementationMode.PERFORMANCE);
        cameraPreview.setScaleType(PreviewView.ScaleType.FILL_CENTER);
        fullScreenMediaLayer.addView(cameraPreview, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        spatialOverlayView = new ZoeSpatialOverlayView(this, new ZoeSpatialOverlayView.Listener() {
            @Override
            public void onSpatialHudUpdate(float distanceMeters, String statusHint) {
                latestArDistanceMeters = distanceMeters;
                if (arModeOn && !useHeavyArCore6Dof && !isFinishing() && !isDestroyed()) {
                    liveHudPill.setText(statusHint);
                }
            }

            @Override
            public void onSpatialArrived(ArExploreBrain.Vec3 worldPos, float distanceMeters,
                                         float normalizedX, boolean userTapped) {
                latestArDistanceMeters = distanceMeters;
                if (!arModeOn || useHeavyArCore6Dof || isFinishing() || isDestroyed()) {
                    return;
                }
                ExploreAccessibility.pulseHaptic(ZoeLiveActivity.this,
                        ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
                if (a11y.spatialAudioBeacon) {
                    ExploreAccessibility.playStereoSpatialChimeAsync(normalizedX, distanceMeters);
                }
                Bitmap snap = getLatestCameraFrameCopy();
                if (snap != null) {
                    handleArSpotInspection(snap, worldPos, distanceMeters, normalizedX, userTapped);
                }
            }

            @Override
            public void onSpatialDoubleTap() {
                if (arModeOn && !isFinishing() && !isDestroyed()) {
                    onOrbTapped();
                }
            }

            @Override
            public void onSpatialLongPress() {
                if (!isFinishing() && !isDestroyed()) {
                    announceOrientationSummary();
                }
            }
        });
        spatialOverlayView.setVisibility(View.GONE);
        spatialOverlayView.setContentDescription("Live camera and Zoe spatial view. Tap anywhere to inspect, double tap to talk, long press for direction and lighting.");
        fullScreenMediaLayer.addView(spatialOverlayView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        arSurfaceHost = new FrameLayout(this);
        arSurfaceHost.setVisibility(View.GONE);
        fullScreenMediaLayer.addView(arSurfaceHost, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Slim soft scrims ONLY at extreme top & bottom edges (never darkens the middle of your scene!)
        topScrim = new View(this);
        topScrim.setBackground(new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{Color.argb(150, 6, 10, 18), Color.TRANSPARENT}));
        fullScreenMediaLayer.addView(topScrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 112), Gravity.TOP));

        bottomScrim = new View(this);
        bottomScrim.setBackground(new GradientDrawable(
                GradientDrawable.Orientation.BOTTOM_TOP,
                new int[]{Color.argb(185, 6, 10, 18), Color.TRANSPARENT}));
        fullScreenMediaLayer.addView(bottomScrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 188), Gravity.BOTTOM));

        stageRoot.addView(fullScreenMediaLayer, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Layer 2: Calm, Ultra-Minimal Foreground Chrome (ZERO wall of pills!)
        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        // Single clean Top Row: [←]  [● Status Pill]   <spacer>   [⇄]  [⚙]
        LinearLayout topRow = new LinearLayout(this);
        topRow.setOrientation(LinearLayout.HORIZONTAL);
        topRow.setGravity(Gravity.CENTER_VERTICAL);
        topRow.setPadding(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 6));

        Button backBtn = compactGlassButton("←", v -> finish());
        backBtn.setContentDescription("Go back");
        LinearLayout.LayoutParams backLp = new LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42));
        backLp.setMargins(0, 0, Ui.dp(this, 8), 0);
        topRow.addView(backBtn, backLp);

        liveHudPill = Ui.text(this, "Zoe Explore", 13.5f, Ui.TEXT);
        liveHudPill.setTypeface(Ui.SANS_MEDIUM);
        liveHudPill.setPadding(Ui.dp(this, 12), Ui.dp(this, 7), Ui.dp(this, 12), Ui.dp(this, 7));
        liveHudPill.setBackground(Ui.tonalPillDrawable(this, Color.argb(155, 12, 16, 26), Ui.primaryAccent(this), 18));
        liveHudPill.setTextColor(Color.WHITE);
        liveHudPill.setClickable(true);
        liveHudPill.setContentDescription("Zoe Explore status. Tap for direction and room summary.");
        liveHudPill.setOnClickListener(Ui.withHaptic(v -> {
            if (cameraOn || arModeOn) {
                announceOrientationSummary();
            } else {
                setToolsSheetOpen(true);
            }
        }));
        topRow.addView(liveHudPill);

        topRow.addView(new View(this), new LinearLayout.LayoutParams(0, 1, 1f));

        flipCamBtn = compactGlassButton("⇄", v -> flipCamera());
        flipCamBtn.setId(R.id.live_flip_camera);
        flipCamBtn.setContentDescription("Flip front and rear camera");
        flipCamBtn.setVisibility(View.GONE);
        LinearLayout.LayoutParams flipLp = new LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42));
        flipLp.setMargins(0, 0, Ui.dp(this, 8), 0);
        topRow.addView(flipCamBtn, flipLp);

        toolsBtn = compactGlassButton("⚙", v -> setToolsSheetOpen(!toolsOpen));
        toolsBtn.setId(R.id.live_tools_button);
        toolsBtn.setContentDescription("Open Zoe Explore tools and accessibility settings");
        topRow.addView(toolsBtn, new LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42)));

        root.addView(topRow);

        // Wide-open touch-passthrough spacer when full-screen camera/AR is active!
        fullScreenSpacer = new View(this);
        fullScreenSpacer.setClickable(false);
        fullScreenSpacer.setFocusable(false);
        fullScreenSpacer.setVisibility(View.GONE);
        root.addView(fullScreenSpacer, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Calm idle orb view (shown ONLY when camera & AR are off)
        idleCenterHost = new ScrollView(this);
        idleCenterHost.setFillViewport(true);
        idleCenterHost.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout center = Ui.vertical(this);
        center.setBackgroundColor(Color.TRANSPARENT);
        center.setGravity(Gravity.CENTER);
        center.setPadding(Ui.dp(this, 20), Ui.dp(this, 8), Ui.dp(this, 20), Ui.dp(this, 8));

        orbView = new LiveOrbView(this);
        orbView.setId(R.id.live_orb_view);
        orbView.setContentDescription("Zoe Explore orb. Tap to speak or interrupt.");
        orbView.setClickable(true);
        orbView.setFocusable(true);
        orbView.setOnClickListener(Ui.withHaptic(v -> onOrbTapped()));
        LinearLayout.LayoutParams orbLp = new LinearLayout.LayoutParams(Ui.dp(this, 212), Ui.dp(this, 212));
        center.addView(orbView, orbLp);

        stateBadge = Ui.text(this, "TAP ZOE TO TALK · MIC & CAMERA OFF", 12f, Ui.COBALT);
        stateBadge.setId(R.id.live_state_badge);
        stateBadge.setTypeface(Ui.SANS_MEDIUM);
        stateBadge.setGravity(Gravity.CENTER);
        stateBadge.setPadding(0, Ui.dp(this, 14), 0, 0);
        center.addView(stateBadge);

        idleCenterHost.addView(center);
        root.addView(idleCenterHost, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        // Minimal Bottom Area: Live Caption (clean & adaptive) + Optional Deaf Type Bar + 3-Button Dock
        LinearLayout bottomStack = Ui.vertical(this);
        bottomStack.setBackgroundColor(Color.TRANSPARENT);
        bottomStack.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 14));

        captionView = Ui.text(this, "Hi, I'm Zoe. Tap ✦ AR to explore together or tap Talk.", 15f, Ui.TEXT);
        captionView.setId(R.id.live_caption_view);
        captionView.setGravity(Gravity.CENTER);
        captionView.setMaxLines(3);
        captionView.setEllipsize(TextUtils.TruncateAt.END);
        captionView.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 14), Ui.dp(this, 10));
        captionView.setBackground(Ui.cardBackground(this, 18));
        captionView.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        LinearLayout.LayoutParams capLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        capLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        bottomStack.addView(captionView, capLp);

        // Silent Type-to-Zoe bar (automatically shown in Deaf / Hard-of-Hearing mode or when toggled!)
        typeBar = new LinearLayout(this);
        typeBar.setId(R.id.live_type_bar);
        typeBar.setOrientation(LinearLayout.HORIZONTAL);
        typeBar.setGravity(Gravity.CENTER_VERTICAL);
        typeBar.setVisibility(View.GONE);
        typeInput = Ui.input(this, "", "Type to Zoe…");
        typeInput.setId(R.id.live_type_input);
        typeInput.setImeOptions(EditorInfo.IME_ACTION_SEND);
        typeInput.setSingleLine(true);
        typeInput.setOnEditorActionListener((v, actionId, event) -> {
            if (actionId == EditorInfo.IME_ACTION_SEND) {
                submitTypedMessage();
                return true;
            }
            return false;
        });
        typeSendBtn = Ui.primaryButton(this, "Send", Ui.COBALT, v -> submitTypedMessage());
        typeSendBtn.setId(R.id.live_type_send);
        typeSendBtn.setMinWidth(0);
        typeSendBtn.setMinimumWidth(0);
        typeSendBtn.setPadding(Ui.dp(this, 16), Ui.dp(this, 10), Ui.dp(this, 16), Ui.dp(this, 10));
        LinearLayout.LayoutParams tiLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        tiLp.setMargins(0, 0, Ui.dp(this, 8), 0);
        typeBar.addView(typeInput, tiLp);
        typeBar.addView(typeSendBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        LinearLayout.LayoutParams tbLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tbLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        bottomStack.addView(typeBar, tbLp);

        // Clean 3-Button Bottom Dock: [✦ AR]  [Talk / Look]  [End]
        LinearLayout dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        dock.setGravity(Gravity.CENTER_VERTICAL);

        arToggleBtn = Ui.button(this, "✦ AR", Ui.CYAN, v -> toggleArSpace());
        arToggleBtn.setId(R.id.live_ar_toggle);
        arToggleBtn.setContentDescription("Toggle full-screen camera and Zoe spatial AR");

        listenBtn = Ui.primaryButton(this, "Talk", Ui.COBALT, v -> onPrimaryActionTapped());
        listenBtn.setId(R.id.live_talk_button);
        listenBtn.setContentDescription("Talk to Zoe or interrupt");

        stopBtn = Ui.button(this, "End", Ui.RUBY, v -> stopLiveCall());
        stopBtn.setId(R.id.live_stop_button);
        stopBtn.setContentDescription("Stop camera, microphone, and all sensors");

        LinearLayout.LayoutParams dlp1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        dlp1.setMargins(0, 0, Ui.dp(this, 8), 0);
        LinearLayout.LayoutParams dlp2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.25f);
        dlp2.setMargins(0, 0, Ui.dp(this, 8), 0);
        dock.addView(arToggleBtn, dlp1);
        dock.addView(listenBtn, dlp2);
        dock.addView(stopBtn, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 0.9f));
        bottomStack.addView(dock);

        root.addView(bottomStack);
        stageRoot.addView(root, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        // Layer 3: Slide-Up Tools & Accessibility Drawer (1 tap on ⚙ — zero clutter on live view!)
        buildToolsAndAccessibilitySheet(stageRoot);

        setContentView(stageRoot);
        Ui.configureEdgeToEdge(this, root);
        applyResponsiveGeometry(getResources().getConfiguration());
        applyAccessibilitySettings(false);
        updateFullScreenVisualMode();
        styleDrawerButtons();
        initTts();
    }

    private void buildToolsAndAccessibilitySheet(FrameLayout stageRoot) {
        toolsBackdrop = new FrameLayout(this);
        toolsBackdrop.setBackgroundColor(Color.argb(150, 4, 7, 14));
        toolsBackdrop.setVisibility(View.GONE);
        toolsBackdrop.setClickable(true);
        toolsBackdrop.setOnClickListener(v -> setToolsSheetOpen(false));

        toolsSheet = new ScrollView(this);
        toolsSheet.setId(R.id.live_tools_sheet);
        toolsSheet.setBackground(Ui.tonalPillDrawable(this, Color.argb(246, 16, 20, 30), Ui.primaryAccent(this), 26));
        toolsSheet.setClickable(true);

        LinearLayout inner = Ui.vertical(this);
        inner.setBackgroundColor(Color.TRANSPARENT);
        inner.setPadding(Ui.dp(this, 18), Ui.dp(this, 16), Ui.dp(this, 18), Ui.dp(this, 24));

        // Sheet header
        LinearLayout sheetHdr = new LinearLayout(this);
        sheetHdr.setOrientation(LinearLayout.HORIZONTAL);
        sheetHdr.setGravity(Gravity.CENTER_VERTICAL);
        TextView sheetTitle = Ui.text(this, "Explore Tools & Accessibility", 16.5f, Ui.TEXT);
        sheetTitle.setTextColor(Color.WHITE);
        sheetTitle.setTypeface(Ui.SANS_MEDIUM);
        sheetHdr.addView(sheetTitle, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button doneBtn = compactGlassButton("Done", v -> setToolsSheetOpen(false));
        doneBtn.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        sheetHdr.addView(doneBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34)));
        inner.addView(sheetHdr);

        // --- SECTION 1: Accessibility & Guided Navigation ---
        TextView a11yHdr = sheetSectionLabel("Accessibility & Navigation Mode");
        inner.addView(a11yHdr);

        LinearLayout profRow1 = new LinearLayout(this);
        profRow1.setOrientation(LinearLayout.HORIZONTAL);
        a11yStandardBtn = sheetPill("Standard", v -> selectAccessibilityProfile(ExploreAccessibility.Profile.STANDARD));
        a11yStandardBtn.setId(R.id.live_a11y_standard);
        a11yDeafBtn = sheetPill("Deaf / HoH", v -> selectAccessibilityProfile(ExploreAccessibility.Profile.DEAF_HOH));
        a11yDeafBtn.setId(R.id.live_a11y_deaf);
        addEvenRow(profRow1, a11yStandardBtn, a11yDeafBtn);
        inner.addView(profRow1);

        LinearLayout profRow2 = new LinearLayout(this);
        profRow2.setOrientation(LinearLayout.HORIZONTAL);
        a11yBlindBtn = sheetPill("Blind / Audio", v -> selectAccessibilityProfile(ExploreAccessibility.Profile.BLIND_LOW_VISION));
        a11yBlindBtn.setId(R.id.live_a11y_blind);
        a11yKidBtn = sheetPill("Kid Mode: off", v -> {
            a11y = a11y.withKidFriendly(!a11y.kidFriendly);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(true);
        });
        a11yKidBtn.setId(R.id.live_a11y_kid);
        addEvenRow(profRow2, a11yBlindBtn, a11yKidBtn);
        inner.addView(profRow2);

        a11ySummaryView = Ui.text(this, "", 12.5f, Ui.TEXT);
        a11ySummaryView.setTextColor(Color.rgb(198, 224, 248));
        a11ySummaryView.setPadding(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 8));
        inner.addView(a11ySummaryView);

        // Fine-grained mix & match accessibility aids (supports Deaf-Blind, low-vision, sensory needs!)
        LinearLayout optRow1 = new LinearLayout(this);
        optRow1.setOrientation(LinearLayout.HORIZONTAL);
        optBigCaptionsBtn = sheetPill("Big Captions", v -> {
            a11y = a11y.withLargeCaptions(!a11y.largeCaptions);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
        });
        optHapticsBtn = sheetPill("Haptics", v -> {
            a11y = a11y.withHapticCues(!a11y.hapticCues);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
            ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
        });
        optSoundRadarBtn = sheetPill("Sound Radar", v -> {
            a11y = a11y.withVisualSoundRadar(!a11y.visualSoundRadar);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
        });
        addEvenRow(optRow1, optBigCaptionsBtn, optHapticsBtn, optSoundRadarBtn);
        inner.addView(optRow1);

        LinearLayout optRow2 = new LinearLayout(this);
        optRow2.setOrientation(LinearLayout.HORIZONTAL);
        optAudioSonarBtn = sheetPill("Audio Sonar", v -> {
            a11y = a11y.withAudioFirstNarration(!a11y.audioFirstNarration);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(true);
        });
        optTypeBarBtn = sheetPill("Type Bar", v -> {
            a11y = a11y.withTypeBar(!a11y.showTypeBar);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
        });
        addEvenRow(optRow2, optAudioSonarBtn, optTypeBarBtn);
        inner.addView(optRow2);

        // --- SECTION 2: Camera, Spatial AR & Multi-Sensor Telemetry ---
        inner.addView(sheetSectionLabel("Camera, Spatial AR & Sensors (Opt-In)"));

        LinearLayout camRow = new LinearLayout(this);
        camRow.setOrientation(LinearLayout.HORIZONTAL);
        cameraToggleBtn = sheetPill("Camera: off", v -> {
            setToolsSheetOpen(false);
            toggleCamera();
        });
        cameraToggleBtn.setId(R.id.live_camera_toggle);
        arModeBtn = sheetPill("Engine: Gyro 60", v -> toggleArTrackingMode());
        arModeBtn.setId(R.id.live_ar_mode_toggle);
        arRoamBtn = sheetPill("Glide: on", v -> toggleArRoam());
        arRoamBtn.setId(R.id.live_ar_roam_toggle);
        addEvenRow(camRow, cameraToggleBtn, arModeBtn, arRoamBtn);
        inner.addView(camRow);

        LinearLayout sensorRow = new LinearLayout(this);
        sensorRow.setOrientation(LinearLayout.HORIZONTAL);
        fieldToggleBtn = sheetPill("Field: off", v -> toggleSpatialField());
        fieldToggleBtn.setId(R.id.live_field_toggle);
        dualCamBtn = sheetPill("Dual-Cam Sweep", v -> {
            setToolsSheetOpen(false);
            runDualCamAmbientSweep();
        });
        dualCamBtn.setId(R.id.live_dual_cam_btn);
        lookNowBtn = sheetPill("Look Now", v -> {
            setToolsSheetOpen(false);
            describeLiveViewProactively();
        });
        lookNowBtn.setId(R.id.live_look_button);
        addEvenRow(sensorRow, fieldToggleBtn, dualCamBtn, lookNowBtn);
        inner.addView(sensorRow);

        LinearLayout geoRow = new LinearLayout(this);
        geoRow.setOrientation(LinearLayout.HORIZONTAL);
        Button echoBtn = sheetPill("Echo Depth Ping", v -> {
            setToolsSheetOpen(false);
            triggerAcousticEchoPing();
        });
        Button earthBtn = sheetPill("Open Google Earth", v -> {
            setToolsSheetOpen(false);
            openGoogleEarthOrHint();
        });
        addEvenRow(geoRow, echoBtn, earthBtn);
        inner.addView(geoRow);

        telemetryHudLine = Ui.text(this, "Spatial Field idle · Local-only, zero PII (CERN Aτ/M₄ · RF · ENU)", 11.5f, Ui.TEXT);
        telemetryHudLine.setId(R.id.live_telemetry_hud);
        telemetryHudLine.setTextColor(Color.rgb(168, 224, 248));
        telemetryHudLine.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
        telemetryHudLine.setBackground(Ui.tonalPillDrawable(this, Color.argb(140, 8, 12, 22), Ui.CYAN, 14));
        LinearLayout.LayoutParams telLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        telLp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 4));
        inner.addView(telemetryHudLine, telLp);

        // --- SECTION 3: Voice & Extras ---
        inner.addView(sheetSectionLabel("Voice, Grounding & Fun"));

        LinearLayout voiceRow = new LinearLayout(this);
        voiceRow.setOrientation(LinearLayout.HORIZONTAL);
        hiZoeToggleBtn = sheetPill("Hi Zoe: off", v -> {
            setToolsSheetOpen(false);
            toggleHiZoeMode();
        });
        hiZoeToggleBtn.setId(R.id.live_hizoe_toggle);
        webToggleBtn = sheetPill("Web: off", v -> toggleWeb());
        webToggleBtn.setId(R.id.live_web_toggle);
        voiceModeBtn = sheetPill("Voice: OS", v -> toggleVoiceEngine());
        voiceModeBtn.setId(R.id.live_voice_toggle);
        addEvenRow(voiceRow, hiZoeToggleBtn, webToggleBtn, voiceModeBtn);
        inner.addView(voiceRow);

        LinearLayout funRow = new LinearLayout(this);
        funRow.setOrientation(LinearLayout.HORIZONTAL);
        Button factBtn = sheetPill("Calm Fact", v -> {
            setToolsSheetOpen(false);
            processSpokenPrompt("Tell me a short calming science fact about nature.");
        });
        Button singBtn = sheetPill("Sing Zoe", v -> {
            setToolsSheetOpen(false);
            singZoeOffline();
        });
        addEvenRow(funRow, factBtn, singBtn);
        inner.addView(funRow);

        toolsSheet.addView(inner);

        FrameLayout.LayoutParams sheetLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        int margin = Ui.dp(this, 10);
        sheetLp.setMargins(margin, Ui.dp(this, 76), margin, margin);
        toolsBackdrop.addView(toolsSheet, sheetLp);
        stageRoot.addView(toolsBackdrop, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
    }

    private TextView sheetSectionLabel(String text) {
        TextView tv = Ui.text(this, text, 11.5f, Ui.TEXT);
        tv.setTextColor(Color.rgb(142, 184, 232));
        tv.setTypeface(Ui.SANS_MEDIUM);
        tv.setPadding(Ui.dp(this, 4), Ui.dp(this, 12), Ui.dp(this, 4), Ui.dp(this, 6));
        return tv;
    }

    private Button compactGlassButton(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(15f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMinWidth(0);
        b.setMinimumWidth(0);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(0, 0, 0, 0);
        b.setTextColor(Color.WHITE);
        b.setBackground(Ui.tonalPillDrawable(this, Color.argb(165, 14, 18, 28), Ui.primaryAccent(this), 21));
        b.setStateListAnimator(null);
        b.setOnClickListener(Ui.withHaptic(listener));
        return b;
    }

    private Button sheetPill(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(12f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMaxLines(1);
        b.setEllipsize(TextUtils.TruncateAt.END);
        b.setMinWidth(0);
        b.setMinimumWidth(0);
        b.setMinHeight(0);
        b.setMinimumHeight(0);
        b.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
        b.setTextColor(Color.rgb(220, 232, 246));
        b.setBackground(Ui.tonalPillDrawable(this, Color.argb(190, 26, 32, 46), Ui.primaryAccent(this), 16));
        b.setStateListAnimator(null);
        b.setOnClickListener(Ui.withHaptic(listener));
        return b;
    }

    private void addEvenRow(LinearLayout row, Button... buttons) {
        LinearLayout.LayoutParams rowLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        rowLp.setMargins(0, 0, 0, Ui.dp(this, 6));
        row.setLayoutParams(rowLp);
        for (int i = 0; i < buttons.length; i++) {
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 42), 1f);
            if (i < buttons.length - 1) {
                lp.setMargins(0, 0, Ui.dp(this, 6), 0);
            }
            row.addView(buttons[i], lp);
        }
    }

    private void setToolsSheetOpen(boolean open) {
        toolsOpen = open;
        if (toolsBackdrop != null) {
            toolsBackdrop.setVisibility(open ? View.VISIBLE : View.GONE);
        }
        if (open) {
            styleDrawerButtons();
        }
    }

    private void selectAccessibilityProfile(ExploreAccessibility.Profile profile) {
        a11y = ExploreAccessibility.Settings.forProfile(profile, a11y.kidFriendly);
        ExploreAccessibility.save(this, a11y);
        applyAccessibilitySettings(true);
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
    }

    private void applyAccessibilitySettings(boolean announceChange) {
        if (spatialOverlayView != null) {
            spatialOverlayView.setVisualSoundRadarEnabled(a11y.visualSoundRadar);
            spatialOverlayView.setBlindGestureMode(a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION);
        }
        if (typeBar != null) {
            typeBar.setVisibility(a11y.showTypeBar ? View.VISIBLE : View.GONE);
        }
        int dockHeight = Ui.dp(this, (a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION || a11y.kidFriendly) ? 58 : 48);
        for (Button b : new Button[]{arToggleBtn, listenBtn, stopBtn}) {
            if (b != null) {
                b.setMinimumHeight(dockHeight);
                b.setTextSize(a11y.kidFriendly || a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION ? 15f : 13.5f);
            }
        }
        if (captionView != null) {
            captionView.setTextSize(a11y.largeCaptions ? 20f : 14.5f);
            captionView.setMaxLines(a11y.largeCaptions ? 5 : 3);
            if (a11y.largeCaptions) {
                mainHandler.removeCallbacks(hideIdleCaptionTask);
                captionView.setVisibility(View.VISIBLE);
                captionView.setAlpha(1f);
            }
        }
        if (a11ySummaryView != null) {
            String desc = switch (a11y.profile) {
                case DEAF_HOH -> "Deaf / Hard-of-Hearing: Big high-contrast captions, visual ambient Sound Radar ring, haptic vibration cues, silent Type-to-Zoe bar, speaker muted by default.";
                case BLIND_LOW_VISION -> "Blind / Low-Vision: Tap screen to hear what's ahead (clock-face + distance + text), double-tap to talk, long-press for compass & lighting, stereo directional chimes + haptics.";
                default -> "Standard: Clean full-screen camera + floating Zoe with minimal controls. Turn on Kid Mode or any aid below anytime.";
            };
            if (a11y.kidFriendly) {
                desc += " Kid Mode ON: friendly simple words and extra-large buttons.";
            }
            a11ySummaryView.setText(desc);
        }
        styleDrawerButtons();
        updateFullScreenVisualMode();
        if (announceChange) {
            String msg = switch (a11y.profile) {
                case DEAF_HOH -> a11y.kidFriendly
                        ? "Deaf Kid mode is on! Big captions, sound ring, gentle buzzes, and typing bar are ready."
                        : "Deaf / Hard-of-Hearing mode active: large captions, visual sound radar, haptics, and Type-to-Zoe enabled.";
                case BLIND_LOW_VISION -> a11y.kidFriendly
                        ? "Audio Guide for kids is on! Tap anywhere and I'll tell you what's in front of you. Double tap to talk."
                        : "Blind / Low-Vision mode active. Single tap anywhere to hear what is ahead, double tap to talk, long press for direction and lighting.";
                default -> a11y.kidFriendly
                        ? "Kid Mode is on! Big buttons and friendly answers ready."
                        : "Standard mode active.";
            };
            showCaption(msg, true);
            if (!a11y.muteSpokenTts && a11y.audioFirstNarration) {
                long t = activeTurnId.incrementAndGet();
                speakCompleteReply(msg, t);
            }
        }
    }

    private void showCaption(String text, boolean keepVisibleLonger) {
        if (captionView == null) {
            return;
        }
        mainHandler.removeCallbacks(hideIdleCaptionTask);
        captionView.animate().cancel();
        captionView.setAlpha(1f);
        captionView.setText(text);
        captionView.setVisibility(View.VISIBLE);
        if ((cameraOn || arModeOn) && !a11y.largeCaptions && !keepVisibleLonger) {
            mainHandler.postDelayed(hideIdleCaptionTask, CAPTION_IDLE_FADE_MS);
        }
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
        if (idleCenterHost != null) {
            idleCenterHost.setVisibility(fullScreen ? View.GONE : View.VISIBLE);
        }
        if (fullScreenSpacer != null) {
            fullScreenSpacer.setVisibility(fullScreen ? View.VISIBLE : View.GONE);
        }
        if (orbView != null) {
            orbView.setAnimationRunning(!fullScreen);
        }
        if (flipCamBtn != null) {
            flipCamBtn.setVisibility((cameraOn || (arModeOn && !useHeavyArCore6Dof)) ? View.VISIBLE : View.GONE);
        }
        if (liveHudPill != null) {
            if (!fullScreen) {
                String badge = a11y.profile == ExploreAccessibility.Profile.STANDARD && !a11y.kidFriendly
                        ? "Zoe Explore"
                        : "Zoe · " + a11y.shortBadge();
                liveHudPill.setText(badge);
            } else if (!arModeOn) {
                liveHudPill.setText(spatialFieldOn ? "● Live · Field" : "● Live");
            }
        }
        if (captionView != null) {
            if (fullScreen) {
                captionView.setTextColor(Color.WHITE);
                int bgAlpha = a11y.largeCaptions ? 225 : 168;
                captionView.setBackground(Ui.tonalPillDrawable(this, Color.argb(bgAlpha, 8, 12, 20),
                        a11y.largeCaptions ? Ui.CYAN : Ui.primaryAccent(this), 18));
            } else {
                captionView.setTextColor(Ui.textColor(this));
                captionView.setBackground(Ui.cardBackground(this, 18));
                captionView.setVisibility(View.VISIBLE);
                captionView.setAlpha(1f);
            }
        }
        if (arToggleBtn != null) {
            arToggleBtn.setText(arModeOn ? "● AR" : "✦ AR");
        }
        if (listenBtn != null && currentOrbState == OrbState.IDLE) {
            listenBtn.setText(a11y.profile == ExploreAccessibility.Profile.DEAF_HOH && (cameraOn || arModeOn)
                    ? "Look"
                    : "Talk");
        }
    }

    private void styleDrawerButtons() {
        styleSheetToggle(a11yStandardBtn, a11y.profile == ExploreAccessibility.Profile.STANDARD, Ui.COBALT);
        styleSheetToggle(a11yDeafBtn, a11y.profile == ExploreAccessibility.Profile.DEAF_HOH, Ui.CYAN);
        styleSheetToggle(a11yBlindBtn, a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION, Ui.GOLD);
        if (a11yKidBtn != null) {
            a11yKidBtn.setText(a11y.kidFriendly ? "Kid Mode: on" : "Kid Mode: off");
            styleSheetToggle(a11yKidBtn, a11y.kidFriendly, Ui.GREEN);
        }
        styleSheetToggle(optBigCaptionsBtn, a11y.largeCaptions, Ui.CYAN);
        styleSheetToggle(optHapticsBtn, a11y.hapticCues, Ui.GREEN);
        styleSheetToggle(optSoundRadarBtn, a11y.visualSoundRadar, Ui.CYAN);
        styleSheetToggle(optAudioSonarBtn, a11y.audioFirstNarration, Ui.GOLD);
        styleSheetToggle(optTypeBarBtn, a11y.showTypeBar, Ui.COBALT);

        if (cameraToggleBtn != null) {
            cameraToggleBtn.setText(arModeOn ? "Camera: AR" : (cameraOn ? "Camera: on" : "Camera: off"));
            styleSheetToggle(cameraToggleBtn, cameraOn || arModeOn, Ui.GREEN);
        }
        if (arModeBtn != null) {
            arModeBtn.setText(useHeavyArCore6Dof ? "Engine: 6DoF" : "Engine: Gyro 60");
            styleSheetToggle(arModeBtn, useHeavyArCore6Dof, Ui.COBALT);
        }
        if (arRoamBtn != null) {
            arRoamBtn.setText(arRoamEnabled ? "Glide: on" : "Glide: off");
            styleSheetToggle(arRoamBtn, arRoamEnabled, Ui.GREEN);
        }
        if (fieldToggleBtn != null) {
            fieldToggleBtn.setText(spatialFieldOn ? "Field: on" : "Field: off");
            styleSheetToggle(fieldToggleBtn, spatialFieldOn, Ui.GREEN);
        }
        if (hiZoeToggleBtn != null) {
            hiZoeToggleBtn.setText(hiZoeWakeMode ? "Hi Zoe: on" : "Hi Zoe: off");
            styleSheetToggle(hiZoeToggleBtn, hiZoeWakeMode, Ui.CYAN);
        }
        if (webToggleBtn != null) {
            webToggleBtn.setText(webOn ? "Web: on" : "Web: off");
            styleSheetToggle(webToggleBtn, webOn, Ui.COBALT);
        }
        if (voiceModeBtn != null) {
            voiceModeBtn.setText(useNativeVoice ? "Voice: Zoe 44k" : "Voice: OS");
            styleSheetToggle(voiceModeBtn, useNativeVoice, Ui.PINK);
        }
        if (toolsBtn != null) {
            boolean custom = a11y.profile != ExploreAccessibility.Profile.STANDARD || a11y.kidFriendly || spatialFieldOn;
            toolsBtn.setBackground(Ui.tonalPillDrawable(this,
                    custom ? Color.argb(200, 24, 78, 118) : Color.argb(165, 14, 18, 28),
                    custom ? Ui.CYAN : Ui.primaryAccent(this), 21));
        }
    }

    private void styleSheetToggle(Button btn, boolean active, int accentRes) {
        if (btn == null) {
            return;
        }
        if (active) {
            int accent = Ui.resolveColor(this, accentRes);
            btn.setTextColor(Color.rgb(12, 16, 22));
            btn.setBackground(Ui.tonalPillDrawable(this, accent, accent, 16));
        } else {
            btn.setTextColor(Color.rgb(214, 226, 242));
            btn.setBackground(Ui.tonalPillDrawable(this, Color.argb(190, 26, 32, 46), Ui.primaryAccent(this), 16));
        }
    }

    private void updateKeepScreenOn() {
        if (callActive || cameraOn || arModeOn) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }
    }

    // --- Silent Type-to-Zoe (for Deaf / Hard-of-Hearing & quiet environments) ---

    private void submitTypedMessage() {
        if (typeInput == null) {
            return;
        }
        String text = typeInput.getText() == null ? "" : typeInput.getText().toString().trim();
        if (text.isEmpty()) {
            return;
        }
        typeInput.setText("");
        processSpokenPrompt(text);
    }

    private void onPrimaryActionTapped() {
        if (a11y.profile == ExploreAccessibility.Profile.DEAF_HOH && (cameraOn || arModeOn) && currentOrbState == OrbState.IDLE) {
            describeLiveViewProactively();
            return;
        }
        onOrbTapped();
    }

    // --- TTS Engine ---

    private void initTts() {
        tts = new TextToSpeech(this, st -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            ttsReady = st == TextToSpeech.SUCCESS;
            if (ttsReady && tts != null) {
                tts.setLanguage(Locale.US);
                tts.setSpeechRate(a11y.kidFriendly ? 0.96f : 1.03f);
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
                if (!pendingSpeechOnReady.isEmpty() && !a11y.muteSpokenTts) {
                    String toSpeak = pendingSpeechOnReady;
                    pendingSpeechOnReady = "";
                    speakCompleteReply(toSpeak, activeTurnId.get());
                }
            } else {
                useNativeVoice = true;
                styleDrawerButtons();
                if (!pendingSpeechOnReady.isEmpty() && !a11y.muteSpokenTts) {
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
                if (v == null || v.getLocale() == null || !"en".equalsIgnoreCase(v.getLocale().getLanguage())) {
                    continue;
                }
                int score = 0;
                if ("US".equalsIgnoreCase(v.getLocale().getCountry())) score += 10;
                if (!v.isNetworkConnectionRequired()) score += 8;
                if (v.getQuality() >= Voice.QUALITY_HIGH) score += 6;
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
            if (isFinishing() || isDestroyed() || turnOfUtterance != activeTurnId.get()) {
                return;
            }
            if (remaining == 0 && streamCompletedForCurrentTurn) {
                orbView.setSpeakingPulse(false);
                if (callActive) {
                    scheduleListeningRearm(ECHO_GUARD_MS);
                } else {
                    setOrbState(OrbState.IDLE, "READY · TAP ZOE TO TALK");
                }
            }
        });
    }

    private static long parseTurnFromUtteranceId(String id) {
        if (id == null) return -1L;
        int idx = id.indexOf(':');
        if (idx <= 0) return -1L;
        try {
            return Long.parseLong(id.substring(0, idx));
        } catch (NumberFormatException ignored) {
            return -1L;
        }
    }

    // --- Runtime Permissions ---

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
            case START_AR_SPACE -> {
                if (camGranted) {
                    // Only start voice automatically if NOT in Deaf silent mode
                    startArSpaceAndVoice(micGranted && !a11y.muteSpokenTts);
                } else {
                    showCaption("Camera permission is needed for full-screen AR.", true);
                }
            }
            case START_VOICE_ONLY -> {
                if (micGranted) {
                    beginContinuousVoiceSession();
                } else {
                    showCaption("Microphone permission is needed to talk live.", true);
                }
            }
            case START_HIZOE -> {
                if (micGranted) {
                    activateHiZoeMode();
                } else {
                    showCaption("Microphone permission is needed for \"Hi Zoe\" mode.", true);
                }
            }
            case START_CAMERA_ONLY -> {
                if (camGranted) {
                    startCamera();
                } else {
                    showCaption("Camera permission was denied. Zoe's camera stays off.", true);
                }
            }
            case START_SPATIAL_FIELD -> activateSpatialFieldNow();
            default -> {
            }
        }
    }

    // --- Controls (inside Tools & Accessibility drawer) ---

    private void toggleHiZoeMode() {
        if (hiZoeWakeMode) {
            hiZoeWakeMode = false;
            callActive = false;
            activeTurnId.incrementAndGet();
            stopAudioOnly();
            setOrbState(OrbState.IDLE, "HI ZOE OFF · MIC IDLE");
            showCaption("\"Hi Zoe\" listener turned off.", false);
            styleDrawerButtons();
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
        styleDrawerButtons();
        updateKeepScreenOn();
        setOrbState(OrbState.LISTENING, "WAITING FOR 'HI ZOE'");
        showCaption("Say \"Hi Zoe\" anytime — tap End to stop.", false);
        scheduleListeningRearm(150L);
    }

    private void toggleWeb() {
        webOn = !webOn;
        styleDrawerButtons();
        showCaption(webOn ? "Web grounding ON." : "Web grounding OFF (100% offline).", false);
    }

    private void toggleVoiceEngine() {
        useNativeVoice = !useNativeVoice;
        styleDrawerButtons();
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

    private void singZoeOffline() {
        long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        setOrbState(OrbState.SPEAKING, "SINGING ZOE");
        showCaption("Singing Zoe's offline soprano melody…", false);
        nativeVoice.singZoe(() -> runOnUiThread(() -> {
            if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                if (callActive) {
                    scheduleListeningRearm(ECHO_GUARD_MS);
                } else {
                    setOrbState(OrbState.IDLE, "READY · TAP ZOE TO TALK");
                }
            }
        }));
    }

    // --- Full-Screen Spatial Companion (Default 60fps Gyro-Spatial + Safe 6DoF ARCore Handoff) ---

    private void toggleArSpace() {
        if (arModeOn) {
            stopArSpace();
            showCaption("AR paused. Tap ✦ AR anytime.", false);
            return;
        }
        List<String> needed = new ArrayList<>();
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.CAMERA);
        }
        if (!a11y.muteSpokenTts
                && ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.RECORD_AUDIO);
        }
        if (!needed.isEmpty()) {
            pendingAction = PendingAction.START_AR_SPACE;
            ActivityCompat.requestPermissions(this, needed.toArray(new String[0]), PERM_REQ);
            return;
        }
        boolean hasMic = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
        startArSpaceAndVoice(hasMic && !a11y.muteSpokenTts);
    }

    private void toggleArTrackingMode() {
        boolean want6Dof = !useHeavyArCore6Dof;
        if (want6Dof && !ZoeArSurfaceView.isArCoreSupported(this)) {
            showCaption("ARCore 6DoF unavailable on this device — using smooth 60fps Gyro Spatial.", true);
            return;
        }
        useHeavyArCore6Dof = want6Dof;
        styleDrawerButtons();
        if (!arModeOn) {
            return;
        }
        stopArEnginesOnly();
        startActiveArEngine();
        updateFullScreenVisualMode();
    }

    private void startArSpaceAndVoice(boolean withVoice) {
        stopArEnginesOnly();
        arBrain.clearSession();
        arModeOn = true;
        startActiveArEngine();
        updateFullScreenVisualMode();
        styleDrawerButtons();
        updateKeepScreenOn();
        if (!arModeOn) {
            return;
        }
        if (a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION && !spatialFieldOn) {
            activateSpatialFieldNow();
        }
        if (withVoice) {
            beginContinuousVoiceSession();
        } else {
            String hint = a11y.profile == ExploreAccessibility.Profile.DEAF_HOH
                    ? "Tap anywhere to glide Zoe over, or type below."
                    : "Tap anywhere in view to glide Zoe over.";
            showCaption(hint, false);
        }
    }

    private void startActiveArEngine() {
        final long gen = arStartGen.incrementAndGet();
        if (!useHeavyArCore6Dof) {
            arSurfaceHost.setVisibility(View.GONE);
            cameraPreview.setVisibility(View.VISIBLE);
            spatialOverlayView.setVisibility(View.VISIBLE);
            spatialOverlayView.setAutonomousRoam(arRoamEnabled);
            spatialOverlayView.setFrontCameraMirrored(useFrontCamera);
            spatialOverlayView.setVisualSoundRadarEnabled(a11y.visualSoundRadar);
            spatialOverlayView.setBlindGestureMode(a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION);
            syncSpatialOverlayOptics(getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
            spatialOverlayView.setLightField(spatialTelemetry.getLightField());
            spatialOverlayView.setActive(true);
            liveHudPill.setText("● AR · 1.2m");
            if (!cameraOn) {
                cameraOn = true;
                cameraPreview.post(this::bindCameraPreview);
            }
            return;
        }
        // Safe Camera2 hardware release handoff (260ms) before starting ARCore 6DoF Session (prevents black screen!)
        boolean hadCameraX = cameraOn;
        if (hadCameraX) {
            unbindCameraPreviewOnly();
        }
        spatialOverlayView.setActive(false);
        spatialOverlayView.setVisibility(View.GONE);
        cameraPreview.setVisibility(View.GONE);
        arSurfaceHost.removeAllViews();
        arSurfaceHost.setVisibility(View.VISIBLE);
        liveHudPill.setText("● 6DoF · Starting…");

        mainHandler.postDelayed(() -> {
            if (gen != arStartGen.get() || !arModeOn || !useHeavyArCore6Dof || isFinishing() || isDestroyed()) {
                return;
            }
            arSurfaceView = new ZoeArSurfaceView(this, arBrain, new ZoeArSurfaceView.Listener() {
                @Override
                public void onArTrackingUpdate(int planeCount, float zoeDistMeters, String statusHint) {
                    latestArDistanceMeters = zoeDistMeters;
                    if (arModeOn && useHeavyArCore6Dof && !isFinishing() && !isDestroyed()) {
                        liveHudPill.setText(planeCount > 0
                                ? String.format(Locale.US, "● 6DoF · %d · %.1fm", planeCount, zoeDistMeters)
                                : "● 6DoF · Scanning…");
                    }
                }

                @Override
                public void onZoeArrivedAtSpot(Bitmap uprightFrame, ArExploreBrain.Vec3 worldPos,
                                               float distanceMeters, boolean userTapped) {
                    latestArDistanceMeters = distanceMeters;
                    if (userTapped || a11y.audioFirstNarration) {
                        handleArSpotInspection(uprightFrame, worldPos, distanceMeters, 0f, userTapped);
                    } else if (uprightFrame != null && !uprightFrame.isRecycled()) {
                        uprightFrame.recycle();
                    }
                }

                @Override
                public void onArUnavailable(String reason) {
                    if (!isFinishing() && !isDestroyed()) {
                        useHeavyArCore6Dof = false;
                        stopArEnginesOnly();
                        startActiveArEngine();
                        updateFullScreenVisualMode();
                        styleDrawerButtons();
                        showCaption("Switched to smooth 60fps Gyro Spatial.", false);
                    }
                }
            });
            arSurfaceHost.addView(arSurfaceView, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            arSurfaceView.setAutonomousRoam(arRoamEnabled);
            arSurfaceView.startArSession();
        }, hadCameraX ? 260L : 40L);
    }

    private void stopArEnginesOnly() {
        arStartGen.incrementAndGet();
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
        updateFullScreenVisualMode();
        styleDrawerButtons();
        updateKeepScreenOn();
    }

    private void toggleArRoam() {
        arRoamEnabled = !arRoamEnabled;
        if (spatialOverlayView != null) {
            spatialOverlayView.setAutonomousRoam(arRoamEnabled);
        }
        if (arSurfaceView != null) {
            arSurfaceView.setAutonomousRoam(arRoamEnabled);
        }
        styleDrawerButtons();
    }

    // --- Opt-In Multi-Sensor Spatial Telemetry (Bug-Fixed Dual-Cam + CERN Kloster + ENU/Google Earth + Acoustic Echo) ---

    private void toggleSpatialField() {
        if (spatialFieldOn) {
            stopSpatialTelemetry();
            showCaption("Spatial Field off. Extra sensors released.", false);
            return;
        }
        boolean hasLoc = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED;
        if (!hasLoc) {
            pendingAction = PendingAction.START_SPATIAL_FIELD;
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION},
                    PERM_REQ);
            return;
        }
        activateSpatialFieldNow();
    }

    private void activateSpatialFieldNow() {
        spatialFieldOn = true;
        telemetryHudLine.setText("Fusing IMU · CERN Aτ/M₄ · RF · Light-Field…");
        spatialTelemetry.start();
        if (spatialOverlayView != null) {
            spatialTelemetry.updateImuStability(spatialOverlayView.getImuStability());
        }
        styleDrawerButtons();
        updateFullScreenVisualMode();
    }

    private void stopSpatialTelemetry() {
        spatialFieldOn = false;
        dualCamSweepPending = false;
        dualCamCaptureArmed = false;
        latestSpatialContext = "";
        if (spatialTelemetry != null) {
            spatialTelemetry.stop();
        }
        if (telemetryHudLine != null) {
            telemetryHudLine.setText("Spatial Field idle · Local-only, zero PII (CERN Aτ/M₄ · RF · ENU)");
        }
        styleDrawerButtons();
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
     * Bug-fixed Dual-Cam Light-Field Sweep:
     * Samples rear frame first, switches to front lens, waits for bindToLifecycle + 3 AE warm-up frames
     * BEFORE sampling front luminance/warmth (so it NEVER reads a stale rear frame!), then flips back!
     */
    private void runDualCamAmbientSweep() {
        if (!cameraOn || (arModeOn && useHeavyArCore6Dof)) {
            showCaption("Turn on ✦ AR or Camera first for Dual-Cam Light-Field sweep.", false);
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
        dualCamCaptureArmed = false;
        dualCamWarmupFrames.set(0);
        dualCamSweepPending = true;
        useFrontCamera = !useFrontCamera;
        if (spatialOverlayView != null) {
            spatialOverlayView.setFrontCameraMirrored(useFrontCamera);
            syncSpatialOverlayOptics(getResources().getConfiguration().orientation != Configuration.ORIENTATION_LANDSCAPE);
        }
        showCaption("Sampling opposite lens light-field…", false);
        bindCameraPreview();
        mainHandler.postDelayed(() -> {
            if (dualCamSweepPending && !isFinishing() && !isDestroyed()) {
                completeDualCamSweep();
            }
        }, 2_200L);
    }

    private void completeDualCamSweep() {
        if (!dualCamSweepPending) {
            return;
        }
        dualCamSweepPending = false;
        dualCamCaptureArmed = false;
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
        String msg = String.format(Locale.US,
                "Light-Field synced · Ahead %.0f%% · Behind %.0f%%.",
                lf.rearLuma * 100f, lf.frontLuma * 100f);
        showCaption(msg, false);
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.DIRECTION_LOCK, a11y.hapticCues);
    }

    private void openGoogleEarthOrHint() {
        Location loc = spatialTelemetry != null ? spatialTelemetry.getLatestLocation() : null;
        if (loc == null) {
            showCaption("Turn on Field (with Location) first to open your ENU spot in Google Earth.", true);
            return;
        }
        try {
            String url = SpatialTelemetryFusion.buildGoogleEarthUrl(
                    loc.getLatitude(), loc.getLongitude(),
                    loc.hasAltitude() ? loc.getAltitude() : 10.0,
                    spatialTelemetry.getCompassDegrees());
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
        } catch (Exception ignored) {
            try {
                String geo = String.format(Locale.US, "geo:%.6f,%.6f?q=%.6f,%.6f(Zoe+Explore)",
                        loc.getLatitude(), loc.getLongitude(), loc.getLatitude(), loc.getLongitude());
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(geo)));
            } catch (Exception ignored2) {
            }
        }
    }

    private void announceOrientationSummary() {
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.DIRECTION_LOCK, a11y.hapticCues);
        if (!spatialFieldOn) {
            spatialTelemetry.start();
            spatialFieldOn = true;
            styleDrawerButtons();
        }
        String summary = ExploreAccessibility.formatOrientationSummary(
                spatialTelemetry.getLastSnapshot(),
                spatialTelemetry.getCompassDegrees(),
                a11y.kidFriendly);
        showCaption(summary, true);
        if (!a11y.muteSpokenTts) {
            long turn = activeTurnId.incrementAndGet();
            speakCompleteReply(summary, turn);
        }
    }

    private void triggerAcousticEchoPing() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            showCaption("Allow Microphone permission to run an acoustic depth ping.", true);
            return;
        }
        if (!acousticPingBusy.compareAndSet(false, true)) {
            return;
        }
        showCaption("Listening for room echo…", false);
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
                    if (n <= 0) break;
                    offset += n;
                }
                AcousticRanging.Measurement m = AcousticRanging.analyze(buf, chirp, sr);
                if (m.candidateDistanceMeters != null && m.candidateDistanceMeters > 0.25 && m.candidateDistanceMeters < 6.0) {
                    float distM = m.candidateDistanceMeters.floatValue();
                    spatialTelemetry.recordAcousticEchoDistance(distM);
                    String msg = String.format(Locale.US, "Nearest echo ~%.1f meters.", distM);
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            showCaption(msg, false);
                            if (a11y.audioFirstNarration && !a11y.muteSpokenTts) {
                                speakCompleteReply(msg, activeTurnId.incrementAndGet());
                            }
                        }
                    });
                } else {
                    runOnUiThread(() -> {
                        if (!isFinishing() && !isDestroyed()) {
                            showCaption("Open space ahead (no close echo).", false);
                        }
                    });
                }
            } catch (RuntimeException err) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        showCaption("Echo ping unavailable right now.", false);
                    }
                });
            } finally {
                if (recorder != null) {
                    try { recorder.stop(); } catch (Exception ignored) {}
                    recorder.release();
                }
                if (track != null) {
                    try { track.stop(); } catch (Exception ignored) {}
                    track.release();
                }
                acousticPingBusy.set(false);
            }
        });
    }

    private void handleArSpotInspection(Bitmap uprightFrame, ArExploreBrain.Vec3 worldPos,
                                        float distanceMeters, float normalizedX, boolean userTapped) {
        if (!arModeOn || uprightFrame == null || isFinishing() || isDestroyed()) {
            return;
        }
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
                learnedHint = VisionPriorStore.buildSilentExploreContext(this, uprightFrame);
            } catch (Throwable err) {
                uprightFrame.recycle();
                return;
            }
            uprightFrame.recycle();
            String scaleNote = ScientificVisualSubstrate.describeRelativeScale(distanceMeters);
            StringBuilder enriched = new StringBuilder(report);
            if (!learnedHint.isEmpty()) enriched.append(" ").append(learnedHint);
            if (!scaleNote.isEmpty()) enriched.append(" ").append(scaleNote);
            latestCameraReport = enriched.toString().trim();
            latestCameraJpeg = jpeg;

            String label = ArExploreBrain.extractPrimaryLabel(report);
            String ocr = ArExploreBrain.extractOcrSnippet(report);

            // In Blind / Low-Vision or Kid-Friendly mode, speak a fast, crystal-clear directional cue right away!
            if (a11y.audioFirstNarration || a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION) {
                String guided = ExploreAccessibility.formatGuidedSceneCue(
                        label, ocr, normalizedX, distanceMeters,
                        spatialTelemetry.getCompassDegrees(),
                        spatialTelemetry.getLightField(),
                        a11y.kidFriendly);
                long myTurn = activeTurnId.incrementAndGet();
                runOnUiThread(() -> finishSimpleReply(myTurn, guided));
                return;
            }

            ArExploreBrain.SpatialDiscovery discovery = arBrain.recordDiscoveryIfNew(
                    report, worldPos, distanceMeters, System.currentTimeMillis());
            final ArExploreBrain.SpatialDiscovery targetDisc = discovery != null
                    ? discovery
                    : new ArExploreBrain.SpatialDiscovery(
                            label, ocr, latestCameraReport, worldPos, distanceMeters, System.currentTimeMillis());
            runOnUiThread(() -> {
                if (!arModeOn || isFinishing() || isDestroyed()) return;
                askCuriousArQuestion(targetDisc);
            });
        });
    }

    private void askCuriousArQuestion(ArExploreBrain.SpatialDiscovery discovery) {
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "Look here";
        setOrbState(OrbState.THINKING, "LOOKING…");
        showCaption("Looking…", false);

        String roomMemory = arBrain.summarizeRoomMemory();
        String curiosityPrompt = ArExploreBrain.buildCuriosityQuestionPrompt(discovery, roomMemory);
        if (a11y.kidFriendly) {
            curiosityPrompt += " Use very warm, simple kid-friendly words (1 short sentence).";
        }

        String finalPrompt = curiosityPrompt;
        executor.execute(() -> {
            if (myTurn != activeTurnId.get()) return;
            byte[] jpeg = latestCameraJpeg;
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (jpeg != null && !geminiKey.isEmpty()) {
                try {
                    String reply = CloudVisionClient.askVision(
                            geminiKey,
                            MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT + "\n" + finalPrompt,
                            jpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }
            final boolean streamTtsNow = !a11y.muteSpokenTts && !useNativeVoice && ttsReady && tts != null;
            final int[] spokenOffset = {0};
            final boolean[] startedSpeaking = {false};
            if (streamTtsNow) {
                pendingTtsChunks.set(0);
                streamCompletedForCurrentTurn = false;
            }
            File localModel = OnDeviceLlmEngine.findInstalledModelFile(this, OnDeviceLlmEngine.selectedModel(this));
            if (localModel != null) {
                try {
                    String chatMl = OnDeviceLlmEngine.buildChatMlPrompt(finalPrompt, sessionHistory, "", "");
                    String reply = localLlm.generateStreaming(localModel, chatMl, (partial, done) ->
                            handleStreamChunk(myTurn, partial, streamTtsNow, spokenOffset, startedSpeaking));
                    finalizeStreamedTurn(myTurn, reply, streamTtsNow, spokenOffset[0], startedSpeaking[0]);
                    return;
                } catch (Exception ignored) {
                }
            }
            String offlineQ = ArExploreBrain.buildOfflineCuriousQuestion(discovery);
            if (myTurn == activeTurnId.get()) {
                runOnUiThread(() -> finishSimpleReply(myTurn, offlineQ));
            }
        });
    }

    // --- CameraX Hardware SurfaceView ---

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
        cameraPreview.setVisibility(View.VISIBLE);
        updateFullScreenVisualMode();
        styleDrawerButtons();
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

                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setTargetResolution(new Size(480, 360))
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build();
                analysis.setAnalyzer(cameraAnalysisExecutor, this::cacheLatestImageProxy);

                CameraSelector selector = useFrontCamera
                        ? CameraSelector.DEFAULT_FRONT_CAMERA
                        : CameraSelector.DEFAULT_BACK_CAMERA;
                cameraProvider.bindToLifecycle(this, selector, preview, analysis);

                if (dualCamSweepPending) {
                    // Arm opposite-lens capture ONLY AFTER CameraX has bound the opposite lens!
                    dualCamWarmupFrames.set(0);
                    dualCamCaptureArmed = true;
                }
                mainHandler.removeCallbacks(cameraObserverTick);
                mainHandler.postDelayed(cameraObserverTick, 1800L);
            } catch (Exception error) {
                showCaption("Camera unavailable: " + error.getMessage(), true);
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void cacheLatestImageProxy(@NonNull ImageProxy proxy) {
        try {
            long now = System.currentTimeMillis();
            if (dualCamSweepPending && dualCamCaptureArmed) {
                // Skip first 3 frames so the opposite lens Auto-Exposure settles before reading real brightness!
                if (dualCamWarmupFrames.incrementAndGet() < 4) {
                    return;
                }
                Bitmap upright = imageProxyToCompactBitmap(proxy);
                if (upright != null) {
                    dualCamCaptureArmed = false;
                    if (useFrontCamera) {
                        spatialTelemetry.sampleFrontBitmapForBacklight(upright);
                    } else {
                        spatialTelemetry.sampleRearBitmap(upright);
                    }
                    upright.recycle();
                    mainHandler.post(this::completeDualCamSweep);
                }
                return;
            }
            if (now - lastCameraBitmapMs < 550L) {
                return;
            }
            Bitmap upright = imageProxyToCompactBitmap(proxy);
            if (upright != null) {
                lastCameraBitmapMs = now;
                if (spatialFieldOn) {
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
        updateFullScreenVisualMode();
        styleDrawerButtons();
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
        if (!cameraOn && !arModeOn) {
            toggleArSpace();
            return;
        }
        Bitmap frame = cameraOn
                ? getLatestCameraFrameCopy()
                : (arSurfaceView != null ? arSurfaceView.getLatestSnapshotCopy() : null);
        if (frame == null && latestCameraReport.isEmpty()) {
            showCaption("Hold steady a second and tap again.", false);
            return;
        }
        long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "What do you see?";
        setOrbState(OrbState.THINKING, "LOOKING…");
        showCaption("Looking…", false);
        executor.execute(() -> {
            Bitmap working = frame;
            if (working != null) {
                try {
                    String baseReport = MediaChatHelper.inspectFrameOffline(working);
                    String learnedHint = VisionPriorStore.buildSilentExploreContext(this, working);
                    latestCameraReport = learnedHint.isEmpty() ? baseReport : (baseReport + " " + learnedHint);
                    latestCameraJpeg = MediaChatHelper.bitmapToJpeg(working, 80);
                    if (a11y.audioFirstNarration || a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION) {
                        String guided = ExploreAccessibility.formatGuidedSceneCue(
                                ArExploreBrain.extractPrimaryLabel(baseReport),
                                ArExploreBrain.extractOcrSnippet(baseReport),
                                0f, latestArDistanceMeters,
                                spatialTelemetry.getCompassDegrees(),
                                spatialTelemetry.getLightField(),
                                a11y.kidFriendly);
                        working.recycle();
                        runOnUiThread(() -> finishSimpleReply(myTurn, guided));
                        return;
                    }
                } catch (Exception ignored) {
                }
            }
            try {
                String prompt = a11y.kidFriendly
                        ? "Tell me in one warm simple sentence what you see in front of the camera right now."
                        : "Tell me naturally in one or two short sentences what you see in my camera right now.";
                answerTurnInBackground(myTurn, prompt, true, working);
            } finally {
                if (working != null && !working.isRecycled()) {
                    working.recycle();
                }
            }
        });
    }

    // --- Voice & Continuous Listening (Echo-Hardened!) ---

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
        callActive = true;
        consecutiveErrors = 0;
        styleDrawerButtons();
        updateKeepScreenOn();
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.LISTENING_READY, a11y.hapticCues);
        scheduleListeningRearm(120L);
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
            setOrbState(OrbState.IDLE, "VOICE UNAVAILABLE");
            showCaption("Speech recognizer unavailable on this device. Open ⚙ to enable Type Bar.", true);
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
                if (myGen != listenGen.get()) return;
                consecutiveErrors = 0;
                setOrbState(OrbState.LISTENING, hiZoeWakeMode ? "WAITING FOR 'HI ZOE'" : "LISTENING…");
            }

            @Override
            public void onBeginningOfSpeech() {}

            @Override
            public void onRmsChanged(float rmsdB) {
                if (myGen == listenGen.get()) {
                    float norm = Math.max(0f, Math.min(1f, (rmsdB + 2f) / 11f));
                    orbView.setAudioLevel(norm);
                    if (arModeOn && !useHeavyArCore6Dof && spatialOverlayView != null) {
                        spatialOverlayView.setVoiceLevel(norm);
                        if (a11y.visualSoundRadar) {
                            spatialOverlayView.setAmbientSoundLevel(norm);
                            long now = System.currentTimeMillis();
                            if (norm > 0.78f && (now - lastSoundAlertHapticMs) > 2_500L) {
                                lastSoundAlertHapticMs = now;
                                ExploreAccessibility.pulseHaptic(ZoeLiveActivity.this,
                                        ExploreAccessibility.HapticCue.SOUND_ALERT, a11y.hapticCues);
                            }
                        }
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
            public void onBufferReceived(byte[] buffer) {}

            @Override
            public void onEndOfSpeech() {
                if (myGen == listenGen.get()) {
                    orbView.setAudioLevel(0f);
                }
            }

            @Override
            public void onError(int error) {
                if (myGen != listenGen.get() || !callActive || isFinishing() || isDestroyed()) return;
                orbView.setAudioLevel(0f);
                LiveSessionLogic.ErrorPolicy policy = LiveSessionLogic.classifySpeechError(error);
                switch (policy.action) {
                    case SILENT_REARM -> {
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
                            setOrbState(OrbState.IDLE, "TAP TALK TO RESUME");
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
                            setOrbState(OrbState.IDLE, "TAP TALK TO RESUME");
                            updateKeepScreenOn();
                        }
                    }
                    case FATAL_PERMISSION -> {
                        callActive = false;
                        hiZoeWakeMode = false;
                        styleDrawerButtons();
                        updateKeepScreenOn();
                        setOrbState(OrbState.IDLE, "MIC PERMISSION NEEDED");
                        showCaption(policy.userMessage, true);
                    }
                }
            }

            @Override
            public void onResults(Bundle results) {
                if (myGen != listenGen.get() || isFinishing() || isDestroyed()) return;
                consecutiveErrors = 0;
                orbView.setAudioLevel(0f);
                ArrayList<String> matches = results.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                String heard = (matches != null && !matches.isEmpty()) ? matches.get(0).trim() : "";
                if (heard.isEmpty() || isLikelyRoomNoiseBlip(heard)) {
                    if (callActive) {
                        scheduleListeningRearm(260L);
                    } else {
                        setOrbState(OrbState.IDLE, "READY");
                    }
                    return;
                }
                if (hiZoeWakeMode) {
                    if (WakeWordDetector.isHiZoeTrigger(heard)) {
                        String trailing = WakeWordDetector.stripWakePrefix(heard);
                        hiZoeWakeMode = false;
                        styleDrawerButtons();
                        if (trailing.isEmpty()) {
                            long myTurn = activeTurnId.incrementAndGet();
                            lastUserSpoken = heard;
                            finishSimpleReply(myTurn, "Hi! I'm Zoe — ready to explore together.");
                        } else {
                            processSpokenPrompt(trailing);
                        }
                    } else if (callActive) {
                        scheduleListeningRearm(260L);
                    }
                    return;
                }
                processSpokenPrompt(heard);
            }

            @Override
            public void onPartialResults(Bundle partialResults) {
                if (myGen != listenGen.get() || isFinishing() || isDestroyed()) return;
                ArrayList<String> partial = partialResults.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                if (partial != null && !partial.isEmpty() && !partial.get(0).trim().isEmpty() && !hiZoeWakeMode) {
                    showCaption("You: " + partial.get(0).trim(), true);
                }
            }

            @Override
            public void onEvent(int eventType, Bundle params) {}
        });

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1300L)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1100L);
        try {
            recognizer.startListening(intent);
            setOrbState(OrbState.LISTENING, hiZoeWakeMode ? "WAITING FOR 'HI ZOE'" : "LISTENING…");
        } catch (Exception err) {
            preferDeviceRecognizer = false;
            scheduleListeningRearm(500L);
        }
    }

    private static boolean isLikelyRoomNoiseBlip(String heard) {
        String low = heard.toLowerCase(Locale.US).replaceAll("[^a-z]", "");
        return low.equals("uh") || low.equals("um") || low.equals("hm") || low.equals("hmm") || low.length() <= 1;
    }

    // --- Real-Time Sight + Answer Pipeline ---

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
        showCaption(LiveSessionLogic.formatLiveCaption(spoken, hasSight ? "Looking…" : "Thinking…"), true);
        setOrbState(OrbState.THINKING, "THINKING…");

        String lower = spoken.toLowerCase(Locale.US);
        if (lower.contains("who are you") || lower.contains("who built you")
                || lower.contains("alibaba") || lower.contains("are you zoe")) {
            finishSimpleReply(myTurn, brain.respond(spoken).reply);
            return;
        }
        ZoeBrainEngine.BrainReply fastExact = brain.respond(spoken);
        if ("exact_math".equals(fastExact.mode)
                || "unit_conversion".equals(fastExact.mode)
                || "local_clock".equals(fastExact.mode)) {
            finishSimpleReply(myTurn, fastExact.reply);
            return;
        }

        final Bitmap freshFrame = cameraOn
                ? getLatestCameraFrameCopy()
                : (arModeOn && arSurfaceView != null ? arSurfaceView.getLatestSnapshotCopy() : null);
        executor.execute(() -> {
            if (myTurn != activeTurnId.get()) {
                if (freshFrame != null && !freshFrame.isRecycled()) freshFrame.recycle();
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
                    if (!freshFrame.isRecycled()) freshFrame.recycle();
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
        if (myTurn != activeTurnId.get()) return;
        WebSearchClient.SearchResult webRes = webOn ? WebSearchClient.search(spoken) : null;
        String webCtx = (webRes != null && webRes.hasSources()) ? webRes.formatContextForPrompt(700) : "";

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
            if (latestCameraReport != null && !latestCameraReport.isEmpty()) camCtx.append(latestCameraReport);
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

        String styleGuide = a11y.kidFriendly
                ? " Reply in one warm, super-clear kid-friendly sentence."
                : "";

        if (withCamera && camJpeg != null) {
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (!geminiKey.isEmpty()) {
                try {
                    String visionPrompt = MultiAiClient.ZOE_SYSTEM_PROMPT
                            + "\n" + LiveSessionLogic.buildLiveVoicePrompt(spoken, camReport) + styleGuide;
                    String reply = CloudVisionClient.askVision(
                            geminiKey, MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            visionPrompt, camJpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }
        }

        final boolean streamTtsNow = !a11y.muteSpokenTts && !useNativeVoice && ttsReady && tts != null;
        final int[] spokenOffset = {0};
        final boolean[] startedSpeaking = {false};
        if (streamTtsNow) {
            pendingTtsChunks.set(0);
            streamCompletedForCurrentTurn = false;
        }

        String fusedPrompt = LiveSessionLogic.buildLiveVoicePrompt(spoken, camReport) + styleGuide;

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

    private void handleStreamChunk(long myTurn, String fullSoFar, boolean streamTtsNow,
                                   int[] spokenOffset, boolean[] startedSpeaking) {
        if (myTurn != activeTurnId.get() || fullSoFar == null || fullSoFar.isEmpty()) return;
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
                showCaption(LiveSessionLogic.formatLiveCaption(lastUserSpoken, display), true);
                if (startedSpeaking[0]) {
                    setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING");
                }
            }
        });
    }

    private void finalizeStreamedTurn(long myTurn, String finalReply, boolean streamTtsNow,
                                      int spokenOffset, boolean alreadyStartedSpeaking) {
        if (myTurn != activeTurnId.get()) return;
        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(finalReply);
        if (clean.trim().isEmpty()) clean = "I'm right here with you.";
        final String finalDisplay = clean.trim();
        sessionHistory.add(new ChatHistoryStore.ChatMessage("zoe", finalDisplay, "ZOE EXPLORE", "", 0));

        if (a11y.muteSpokenTts) {
            runOnUiThread(() -> {
                if (myTurn != activeTurnId.get() || isFinishing() || isDestroyed()) return;
                ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_REPLYING, a11y.hapticCues);
                showCaption(LiveSessionLogic.formatLiveCaption(lastUserSpoken, finalDisplay), true);
                if (callActive) {
                    scheduleListeningRearm(320L);
                } else {
                    setOrbState(OrbState.IDLE, "READY");
                }
            });
            return;
        }

        if (streamTtsNow) {
            String remainder = LiveSessionLogic.extractRemainder(finalDisplay, spokenOffset);
            if (!remainder.isEmpty()) {
                enqueueTtsChunk(myTurn, remainder, !alreadyStartedSpeaking);
                alreadyStartedSpeaking = true;
            }
            streamCompletedForCurrentTurn = true;
            final boolean spokeAnything = alreadyStartedSpeaking;
            runOnUiThread(() -> {
                if (myTurn != activeTurnId.get() || isFinishing() || isDestroyed()) return;
                showCaption(LiveSessionLogic.formatLiveCaption(lastUserSpoken, finalDisplay), false);
                if (!spokeAnything || pendingTtsChunks.get() == 0) {
                    orbView.setSpeakingPulse(false);
                    if (callActive) {
                        scheduleListeningRearm(ECHO_GUARD_MS);
                    } else {
                        setOrbState(OrbState.IDLE, "READY");
                    }
                } else {
                    setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING");
                }
            });
        } else {
            runOnUiThread(() -> finishSimpleReply(myTurn, finalDisplay));
        }
    }

    private void enqueueTtsChunk(long myTurn, String sentence, boolean flushFirst) {
        if (a11y.muteSpokenTts || tts == null || !ttsReady || sentence == null || sentence.trim().isEmpty()) {
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
        if (myTurn != activeTurnId.get() || isFinishing() || isDestroyed()) return;
        String clean = reply == null || reply.trim().isEmpty() ? "I'm right here." : reply.trim();
        sessionHistory.add(new ChatHistoryStore.ChatMessage("zoe", clean, "ZOE EXPLORE", "", 0));
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_REPLYING, a11y.hapticCues);
        showCaption(LiveSessionLogic.formatLiveCaption(lastUserSpoken, clean), a11y.largeCaptions);
        if (a11y.muteSpokenTts) {
            if (callActive) {
                scheduleListeningRearm(320L);
            } else {
                setOrbState(OrbState.IDLE, "READY");
            }
            return;
        }
        speakCompleteReply(clean, myTurn);
    }

    private void speakCompleteReply(String text, long myTurn) {
        if (a11y.muteSpokenTts) {
            return;
        }
        String speakable = LiveSessionLogic.sanitizeForSpeech(text);
        if (speakable.isEmpty()) {
            if (callActive) scheduleListeningRearm(ECHO_GUARD_MS);
            else setOrbState(OrbState.IDLE, "READY");
            return;
        }
        setOrbState(OrbState.SPEAKING, "ZOE IS SPEAKING");
        if (useNativeVoice) {
            orbView.setSpeakingPulse(true);
            nativeVoice.speak(speakable, () -> runOnUiThread(() -> {
                orbView.setSpeakingPulse(false);
                if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                    if (callActive) scheduleListeningRearm(ECHO_GUARD_MS);
                    else setOrbState(OrbState.IDLE, "READY");
                }
            }));
        } else if (ttsReady && tts != null) {
            pendingTtsChunks.set(0);
            streamCompletedForCurrentTurn = true;
            enqueueTtsChunk(myTurn, speakable, true);
        } else {
            pendingSpeechOnReady = speakable;
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
            try { tts.stop(); } catch (Exception ignored) {}
        }
        nativeVoice.stop();
    }

    private void stopLiveCall() {
        setToolsSheetOpen(false);
        callActive = false;
        hiZoeWakeMode = false;
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        if (arModeOn) {
            stopArSpace();
        }
        stopCamera();
        styleDrawerButtons();
        updateKeepScreenOn();
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.STOPPED, a11y.hapticCues);
        setOrbState(OrbState.IDLE, "MIC & CAMERA OFF");
        showCaption("Explore paused. Mic, camera, and sensors are completely off.", true);
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
            default -> (a11y.profile == ExploreAccessibility.Profile.DEAF_HOH && (cameraOn || arModeOn)) ? "Look" : "Talk";
        });
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (pendingAction == PendingAction.NONE && (callActive || cameraOn || arModeOn || spatialFieldOn)) {
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
            try { tts.shutdown(); } catch (Exception ignored) {}
        }
        localLlm.close();
        cameraAnalysisExecutor.shutdownNow();
        executor.shutdownNow();
    }

    /**
     * Smooth 60fps Audio-Reactive Iridescent GEM Aurora Orb (zero per-frame allocations).
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
                if (animator.isPaused()) animator.resume();
                else if (!animator.isStarted()) animator.start();
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
            if (maxR <= 0f) return;
            float d = getResources().getDisplayMetrics().density;
            float breathe = (float) Math.sin(phase * Math.PI * 2.0);
            float deg = phase * 360f;

            int cCore, cMid, cOuter;
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

            for (int i = 0; i < 3; i++) {
                float p = (phase + i / 3f) % 1f;
                float r = radius * 0.56f + p * (maxR * 0.96f - radius * 0.56f);
                ringPaint.setStrokeWidth((2.2f * (1f - p) + 0.8f) * d);
                ringPaint.setColor(Color.argb((int) ((1f - p) * 135), Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
                canvas.drawCircle(cx, cy, r, ringPaint);
            }

            glassRimPaint.setStrokeWidth(1.2f * d);
            glassRimPaint.setColor(Color.argb(110, 240, 246, 255));
            canvas.drawCircle(cx, cy, radius * 0.68f, glassRimPaint);

            for (int i = 0; i < 6; i++) {
                double a = (phase * Math.PI * 2.0) * (i % 2 == 0 ? 1.0 : -0.65) + i * (Math.PI / 3.0);
                float dist = radius * (0.76f + 0.14f * (float) Math.sin(phase * Math.PI * 4.0 + i));
                float mx = cx + (float) Math.cos(a) * dist;
                float my = cy + (float) Math.sin(a) * dist;
                int mCol = ribbonCols[i % 3];
                motePaint.setColor(Color.argb(175, Color.red(mCol), Color.green(mCol), Color.blue(mCol)));
                canvas.drawCircle(mx, my, (1.8f + (i % 2) * 0.9f) * d, motePaint);
            }

            float g = radius * 0.34f;
            diamondPath.reset();
            diamondPath.moveTo(cx, cy - g);
            diamondPath.lineTo(cx + g * 0.86f, cy);
            diamondPath.lineTo(cx, cy + g);
            diamondPath.lineTo(cx - g * 0.86f, cy);
            diamondPath.close();
            gemPaint.setColor(cCore);
            canvas.drawPath(diamondPath, gemPaint);

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
