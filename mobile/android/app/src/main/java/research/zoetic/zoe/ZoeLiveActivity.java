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
import android.widget.ImageView;
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
    static final String EXTRA_AUTO_START_LIVE = "zoe_auto_start_live";
    private static final int PERM_REQ = 84;
    private static final long ECHO_GUARD_MS = 480L;
    private static final long CAPTION_IDLE_FADE_MS = 6_500L;
    private static final long FIRST_CURIOSITY_DELAY_MS = 1_700L;
    private static final long AUTONOMOUS_CURIOSITY_INTERVAL_MS = 9_200L;

    private enum OrbState {
        IDLE,
        LISTENING,
        THINKING,
        SPEAKING
    }

    private enum PendingAction {
        NONE,
        START_LIVE_CAMERA_AND_VOICE,
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
    private final ElizaGemClient studioClient = new ElizaGemClient();
    private volatile boolean workstationReachable;
    private volatile boolean workstationFrontierReady;
    private volatile String workstationModelLabel = "";
    private int curiosityQuestIndex;
    private final List<ChatHistoryStore.ChatMessage> sessionHistory = new ArrayList<>();

    // Minimal Symmetrical Full-Screen Stage & Chrome
    private ZoeBackdropView idleBackdrop;
    private FrameLayout fullScreenMediaLayer;
    private PreviewView cameraPreview;
    private ImageView frozenFrameView;
    private ZoeObservationBoxView observationBoxView;
    private final Object frozenFrameLock = new Object();
    private Bitmap frozenFocusBitmap;
    private volatile boolean frozenFrameIsPreviewSpace;
    private volatile boolean pendingFreezeOnNextCameraFrame;
    private ZoeSpatialOverlayView spatialOverlayView;
    private FrameLayout arSurfaceHost;
    private ZoeArSurfaceView arSurfaceView;
    private View topScrim;
    private View bottomScrim;

    private TextView liveHudPill;
    private Button recenterBtn;
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

    // 1-Tap Symmetrical Tools & Accessibility Drawer (clean 2x2 grids + collapsible More Tools)
    private FrameLayout toolsBackdrop;
    private ScrollView toolsSheet;
    private Button moreToolsToggleBtn;
    private LinearLayout moreToolsPanel;
    private boolean moreToolsExpanded;
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
    private Preview activeCameraPreviewUseCase;
    private ImageAnalysis activeImageAnalysis;
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
    private int autoCuriosityStep;
    private float lastAutoSpotU = 0.5f;
    private float lastAutoSpotV = 0.45f;
    private long lastUserSpeechMs;
    private final Object curiosityCropLock = new Object();
    private Bitmap pendingCuriosityCrop;
    private long pendingCuriosityAskedMs;
    private final Runnable autonomousCuriosityTask = this::runAutonomousCuriosityTick;
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
    private volatile String latestPartialHeard = "";
    private volatile long latestPartialAtMs;
    private LiveViewErgonomics.Posture currentPosture = LiveViewErgonomics.Posture.ACTIVE_AR;
    private float activeGuideBearingDeg = Float.NaN;
    private String activeGuideLabel = "";
    private boolean lastGuideWasCentered;
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
        if ((cameraOn || arModeOn) && !a11y.largeCaptions
                && (currentOrbState == OrbState.IDLE || currentOrbState == OrbState.LISTENING)
                && captionView != null) {
            captionView.animate().alpha(0f).setDuration(260L).withEndAction(() -> {
                if ((cameraOn || arModeOn) && !a11y.largeCaptions
                        && (currentOrbState == OrbState.IDLE || currentOrbState == OrbState.LISTENING)) {
                    captionView.setVisibility(View.GONE);
                    captionView.setAlpha(1f);
                }
            }).start();
        }
    };

    // Watchdog so Zoe NEVER stays stuck in "thinking..." if any vision/network/LLM call stalls
    private final Runnable thinkingWatchdog = () -> {
        if (currentOrbState == OrbState.THINKING && !isFinishing() && !isDestroyed()) {
            long turn = activeTurnId.incrementAndGet();
            String fallback = arModeOn
                    ? "ooh, what's this right here?"
                    : "i'm right here, tell me more.";
            finishSimpleReply(turn, fallback);
        }
    };

    // Watchdog so Zoe NEVER stays stuck in "ZOE IS SPEAKING" if Android TTS drops an onDone callback
    private final Runnable speakingWatchdog = () -> {
        if (currentOrbState == OrbState.SPEAKING && !isFinishing() && !isDestroyed()) {
            pendingTtsChunks.set(0);
            streamCompletedForCurrentTurn = true;
            orbView.setSpeakingPulse(false);
            if (callActive) {
                scheduleListeningRearm(ECHO_GUARD_MS);
            } else {
                setOrbState(OrbState.IDLE, "READY");
            }
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

        // Pre-warm ONLY ultra-light offline ML Kit & learned visual memory (<20 MB RAM).
        // Do NOT eagerly load the 1.5 GB LiteRT GPU LLM on launch — avoids Pixel lmkd memory pressure & GPU thermal throttling during live AR!
        executor.execute(() -> {
            MediaChatHelper.warmUp();
            VisionPriorStore.loadAll(this);
            VisionPriorStore.loadBaselineAtlas(this);
            probeWorkstationBridge();
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

        frozenFrameView = new ImageView(this);
        frozenFrameView.setScaleType(ImageView.ScaleType.CENTER_CROP);
        frozenFrameView.setBackgroundColor(Color.BLACK);
        frozenFrameView.setVisibility(View.GONE);
        frozenFrameView.setContentDescription("Frozen still frame for Zoe temporary bounding box");
        fullScreenMediaLayer.addView(frozenFrameView, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        observationBoxView = new ZoeObservationBoxView(this, new ZoeObservationBoxView.Listener() {
            @Override
            public void onObservationBoxSettled(float leftU, float topV, float rightU, float bottomV, boolean wasTap) {
                if (!arModeOn || useHeavyArCore6Dof || isFinishing() || isDestroyed()) {
                    return;
                }
                ExploreAccessibility.pulseHaptic(ZoeLiveActivity.this,
                        ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
                handleObservationBoxSettled(leftU, topV, rightU, bottomV, wasTap);
            }

            @Override
            public void onZoeEmblemTapped() {
                if (arModeOn && !isFinishing() && !isDestroyed()) {
                    onOrbTapped();
                }
            }

            @Override
            public void onBoxDoubleTap() {
                if (arModeOn && !isFinishing() && !isDestroyed()) {
                    onOrbTapped();
                }
            }

            @Override
            public void onBoxLongPress() {
                if (!isFinishing() && !isDestroyed()) {
                    announceOrientationSummary();
                }
            }
        });
        observationBoxView.setVisibility(View.GONE);
        observationBoxView.setContentDescription("Zoe quiet observation box. Drag the white corners to resize or drag inside to move. Lift your finger so Zoe can ask about what is inside.");
        fullScreenMediaLayer.addView(observationBoxView, new FrameLayout.LayoutParams(
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
                                         float tapU, float tapV, boolean userTapped) {
                latestArDistanceMeters = distanceMeters;
                if (!arModeOn || useHeavyArCore6Dof || isFinishing() || isDestroyed()) {
                    return;
                }
                float normX = (tapU * 2f) - 1f;
                ExploreAccessibility.pulseHaptic(ZoeLiveActivity.this,
                        ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
                if (a11y.spatialAudioBeacon) {
                    ExploreAccessibility.playStereoSpatialChimeAsync(normX, distanceMeters);
                }
                Bitmap snap = getLatestCameraFrameCopy();
                if (snap != null) {
                    handleArSpotInspection(snap, worldPos, distanceMeters, tapU, tapV, userTapped);
                }
            }

            @Override
            public void onZoeGemTapped() {
                if (arModeOn && !isFinishing() && !isDestroyed()) {
                    onOrbTapped();
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

        // Layer 2: Calm, Ultra-Minimal Symmetrical Foreground Chrome
        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        // Symmetrical Top Bar (exact left/right mirror balance around dead-center status pill):
        //   Idle: [←]           [ Zoe Explore ]           [⚙]
        //   Live: [←] [◎]       [ ● AR · 1.2m ]       [⇄] [⚙]
        FrameLayout topRow = new FrameLayout(this);
        topRow.setPadding(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 6));

        int iconSize = Ui.dp(this, 44);
        int iconGap = Ui.dp(this, 8);

        LinearLayout topLeftGroup = new LinearLayout(this);
        topLeftGroup.setOrientation(LinearLayout.HORIZONTAL);
        topLeftGroup.setGravity(Gravity.CENTER_VERTICAL);

        Button backBtn = compactGlassButton("←", v -> finish());
        backBtn.setContentDescription("Go back");
        topLeftGroup.addView(backBtn, new LinearLayout.LayoutParams(iconSize, iconSize));

        recenterBtn = compactGlassButton("↻", v -> {
            if (observationBoxView != null && observationBoxView.getVisibility() == View.VISIBLE) {
                retakeFrozenFocusFrame();
                ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.DIRECTION_LOCK, a11y.hapticCues);
            } else if (spatialOverlayView != null) {
                spatialOverlayView.recenterInFrontOfUser();
                ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.DIRECTION_LOCK, a11y.hapticCues);
            }
        });
        recenterBtn.setContentDescription("Take a new still frame for Zoe's temporary bounding box");
        recenterBtn.setVisibility(View.GONE);
        LinearLayout.LayoutParams recLp = new LinearLayout.LayoutParams(iconSize, iconSize);
        recLp.setMargins(iconGap, 0, 0, 0);
        topLeftGroup.addView(recenterBtn, recLp);
        topRow.addView(topLeftGroup, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.START | Gravity.CENTER_VERTICAL));

        liveHudPill = Ui.text(this, "zoe explore", 13.5f, Ui.TEXT);
        liveHudPill.setTypeface(Ui.SANS_MEDIUM);
        liveHudPill.setGravity(Gravity.CENTER);
        liveHudPill.setPadding(Ui.dp(this, 14), Ui.dp(this, 8), Ui.dp(this, 14), Ui.dp(this, 8));
        liveHudPill.setBackground(Ui.tonalPillDrawable(this, Color.argb(155, 12, 16, 26), Ui.primaryAccent(this), 20));
        liveHudPill.setTextColor(Color.WHITE);
        liveHudPill.setClickable(true);
        liveHudPill.setContentDescription("Zoe Explore status. Tap for direction and room summary.");
        liveHudPill.setOnClickListener(Ui.withHaptic(v -> {
            if (arModeOn && !useHeavyArCore6Dof && observationBoxView != null) {
                handleObservationBoxSettled(
                        observationBoxView.getBoxLeftNorm(),
                        observationBoxView.getBoxTopNorm(),
                        observationBoxView.getBoxRightNorm(),
                        observationBoxView.getBoxBottomNorm(),
                        true);
            } else if (cameraOn || arModeOn) {
                announceOrientationSummary();
            } else {
                setToolsSheetOpen(true);
            }
        }));
        topRow.addView(liveHudPill, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.CENTER));

        LinearLayout topRightGroup = new LinearLayout(this);
        topRightGroup.setOrientation(LinearLayout.HORIZONTAL);
        topRightGroup.setGravity(Gravity.CENTER_VERTICAL);

        flipCamBtn = compactGlassButton("⇄", v -> flipCamera());
        flipCamBtn.setId(R.id.live_flip_camera);
        flipCamBtn.setContentDescription("Flip front and rear camera");
        flipCamBtn.setVisibility(View.GONE);
        LinearLayout.LayoutParams flipLp = new LinearLayout.LayoutParams(iconSize, iconSize);
        flipLp.setMargins(0, 0, iconGap, 0);
        topRightGroup.addView(flipCamBtn, flipLp);

        toolsBtn = compactGlassButton("⚙", v -> setToolsSheetOpen(!toolsOpen));
        toolsBtn.setId(R.id.live_tools_button);
        toolsBtn.setContentDescription("Open Zoe Explore tools and accessibility settings");
        topRightGroup.addView(toolsBtn, new LinearLayout.LayoutParams(iconSize, iconSize));
        topRow.addView(topRightGroup, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT,
                Gravity.END | Gravity.CENTER_VERTICAL));

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
        orbView.setContentDescription("Zoe. Tap to start live camera and voice.");
        orbView.setClickable(true);
        orbView.setFocusable(true);
        orbView.setOnClickListener(Ui.withHaptic(v -> {
            if (!cameraOn && !arModeOn) {
                startLiveCameraAndVoiceOnEntry();
            } else {
                onOrbTapped();
            }
        }));
        LinearLayout.LayoutParams orbLp = new LinearLayout.LayoutParams(Ui.dp(this, 176), Ui.dp(this, 176));
        center.addView(orbView, orbLp);

        stateBadge = Ui.text(this, "tap zoe to start live camera & voice", 13f, Ui.MUTED);
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

        captionView = Ui.text(this, "hi, i'm zoe. tap talk or zoe explore", 15f, Ui.TEXT);
        captionView.setId(R.id.live_caption_view);
        captionView.setContentDescription("Hi, I'm Zoe. Tap Talk or Zoe Explore.");
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
        typeInput = Ui.input(this, "", "type to zoe…");
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
        typeSendBtn = Ui.primaryButton(this, "send", Ui.COBALT, v -> submitTypedMessage());
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

        // Clean Symmetrical Bottom Dock: [ <zoe emblem> focus ]  [ talk ]  [ end ]
        LinearLayout dock = new LinearLayout(this);
        dock.setOrientation(LinearLayout.HORIZONTAL);
        dock.setGravity(Gravity.CENTER_VERTICAL);

        arToggleBtn = Ui.button(this, "focus", Ui.RUBY, v -> toggleArSpace());
        arToggleBtn.setId(R.id.live_ar_toggle);
        arToggleBtn.setContentDescription("Toggle Zoe quiet observation box");
        android.graphics.drawable.Drawable gemIcon = ContextCompat.getDrawable(this, R.drawable.zoe_emblem);
        if (gemIcon != null) {
            int iconPx = Ui.dp(this, 22);
            gemIcon.setBounds(0, 0, iconPx, iconPx);
            arToggleBtn.setCompoundDrawablesRelative(gemIcon, null, null, null);
            arToggleBtn.setCompoundDrawablePadding(Ui.dp(this, 6));
        }

        listenBtn = Ui.primaryButton(this, "talk", Ui.COBALT, v -> onPrimaryActionTapped());
        listenBtn.setId(R.id.live_talk_button);
        listenBtn.setContentDescription("Talk to Zoe or interrupt");

        stopBtn = Ui.button(this, "end", Ui.MUTED, v -> stopLiveCall());
        stopBtn.setId(R.id.live_stop_button);
        stopBtn.setContentDescription("Stop camera, microphone, and all sensors");

        LinearLayout.LayoutParams dlp1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.15f);
        dlp1.setMargins(0, 0, Ui.dp(this, 8), 0);
        LinearLayout.LayoutParams dlp2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
        dlp2.setMargins(0, 0, Ui.dp(this, 8), 0);
        LinearLayout.LayoutParams dlp3 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 0.85f);
        dock.addView(arToggleBtn, dlp1);
        dock.addView(listenBtn, dlp2);
        dock.addView(stopBtn, dlp3);
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

        // When launched from the Zoe Explore button on Home / Guided Vision, go straight into Live Camera View!
        if (getIntent() != null && getIntent().getBooleanExtra(EXTRA_AUTO_START_LIVE, false)) {
            mainHandler.post(this::startLiveCameraAndVoiceOnEntry);
        }
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
        inner.setPadding(Ui.dp(this, 18), Ui.dp(this, 16), Ui.dp(this, 18), Ui.dp(this, 22));

        // Clean symmetrical header
        LinearLayout sheetHdr = new LinearLayout(this);
        sheetHdr.setOrientation(LinearLayout.HORIZONTAL);
        sheetHdr.setGravity(Gravity.CENTER_VERTICAL);
        TextView sheetTitle = Ui.text(this, "explore & accessibility", 16.5f, Ui.TEXT);
        sheetTitle.setTextColor(Color.WHITE);
        sheetTitle.setTypeface(Ui.SANS_MEDIUM);
        sheetHdr.addView(sheetTitle, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        Button doneBtn = compactGlassButton("done", v -> setToolsSheetOpen(false));
        doneBtn.setPadding(Ui.dp(this, 16), 0, Ui.dp(this, 16), 0);
        sheetHdr.addView(doneBtn, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 36)));
        inner.addView(sheetHdr);

        // --- SECTION 1: Accessibility (Symmetrical 2×2 Grid) ---
        inner.addView(sheetSectionLabel("accessibility mode"));

        LinearLayout profRow1 = new LinearLayout(this);
        profRow1.setOrientation(LinearLayout.HORIZONTAL);
        a11yStandardBtn = sheetPill("standard", v -> selectAccessibilityProfile(ExploreAccessibility.Profile.STANDARD));
        a11yStandardBtn.setId(R.id.live_a11y_standard);
        a11yDeafBtn = sheetPill("deaf / hoh", v -> selectAccessibilityProfile(ExploreAccessibility.Profile.DEAF_HOH));
        a11yDeafBtn.setId(R.id.live_a11y_deaf);
        addEvenRow(profRow1, a11yStandardBtn, a11yDeafBtn);
        inner.addView(profRow1);

        LinearLayout profRow2 = new LinearLayout(this);
        profRow2.setOrientation(LinearLayout.HORIZONTAL);
        a11yBlindBtn = sheetPill("blind / audio", v -> selectAccessibilityProfile(ExploreAccessibility.Profile.BLIND_LOW_VISION));
        a11yBlindBtn.setId(R.id.live_a11y_blind);
        a11yKidBtn = sheetPill("kid mode: off", v -> {
            a11y = a11y.withKidFriendly(!a11y.kidFriendly);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(true);
        });
        a11yKidBtn.setId(R.id.live_a11y_kid);
        addEvenRow(profRow2, a11yBlindBtn, a11yKidBtn);
        inner.addView(profRow2);

        a11ySummaryView = Ui.text(this, "", 12f, Ui.TEXT);
        a11ySummaryView.setTextColor(Color.rgb(190, 218, 244));
        a11ySummaryView.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4));
        inner.addView(a11ySummaryView);

        // --- SECTION 2: Explore (Symmetrical 2×2 Grid) ---
        inner.addView(sheetSectionLabel("camera & ar"));

        LinearLayout expRow1 = new LinearLayout(this);
        expRow1.setOrientation(LinearLayout.HORIZONTAL);
        cameraToggleBtn = sheetPill("camera: off", v -> {
            setToolsSheetOpen(false);
            toggleCamera();
        });
        cameraToggleBtn.setId(R.id.live_camera_toggle);
        fieldToggleBtn = sheetPill("field: off", v -> toggleSpatialField());
        fieldToggleBtn.setId(R.id.live_field_toggle);
        addEvenRow(expRow1, cameraToggleBtn, fieldToggleBtn);
        inner.addView(expRow1);

        LinearLayout expRow2 = new LinearLayout(this);
        expRow2.setOrientation(LinearLayout.HORIZONTAL);
        arRoamBtn = sheetPill("glide: on", v -> toggleArRoam());
        arRoamBtn.setId(R.id.live_ar_roam_toggle);
        lookNowBtn = sheetPill("look now", v -> {
            setToolsSheetOpen(false);
            describeLiveViewProactively();
        });
        lookNowBtn.setId(R.id.live_look_button);
        addEvenRow(expRow2, arRoamBtn, lookNowBtn);
        inner.addView(expRow2);

        LinearLayout expRow3 = new LinearLayout(this);
        expRow3.setOrientation(LinearLayout.HORIZONTAL);
        Button learnSpotBtn = sheetPill("learn this", v -> {
            setToolsSheetOpen(false);
            promptTeachFromLiveView();
        });
        Button questBtn = sheetPill("quest", v -> {
            setToolsSheetOpen(false);
            triggerCuriosityQuest();
        });
        addEvenRow(expRow3, learnSpotBtn, questBtn);
        inner.addView(expRow3);

        // --- SECTION 3: Voice & Input (Symmetrical 2×2 Grid) ---
        inner.addView(sheetSectionLabel("voice & input"));

        LinearLayout voiceRow1 = new LinearLayout(this);
        voiceRow1.setOrientation(LinearLayout.HORIZONTAL);
        hiZoeToggleBtn = sheetPill("hi zoe: off", v -> {
            setToolsSheetOpen(false);
            toggleHiZoeMode();
        });
        hiZoeToggleBtn.setId(R.id.live_hizoe_toggle);
        webToggleBtn = sheetPill("web: off", v -> toggleWeb());
        webToggleBtn.setId(R.id.live_web_toggle);
        addEvenRow(voiceRow1, hiZoeToggleBtn, webToggleBtn);
        inner.addView(voiceRow1);

        LinearLayout voiceRow2 = new LinearLayout(this);
        voiceRow2.setOrientation(LinearLayout.HORIZONTAL);
        optTypeBarBtn = sheetPill("type bar", v -> {
            a11y = a11y.withTypeBar(!a11y.showTypeBar);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
        });
        voiceModeBtn = sheetPill("voice: os", v -> toggleVoiceEngine());
        voiceModeBtn.setId(R.id.live_voice_toggle);
        addEvenRow(voiceRow2, optTypeBarBtn, voiceModeBtn);
        inner.addView(voiceRow2);

        // --- Collapsible More Tools & Sensors (collapsed by default so main sheet stays ultra-calm!) ---
        moreToolsToggleBtn = sheetPill("more tools & sensors ▾", v -> {
            moreToolsExpanded = !moreToolsExpanded;
            if (moreToolsPanel != null) {
                moreToolsPanel.setVisibility(moreToolsExpanded ? View.VISIBLE : View.GONE);
            }
            moreToolsToggleBtn.setText(moreToolsExpanded ? "hide extra tools ▴" : "more tools & sensors ▾");
        });
        LinearLayout.LayoutParams moreBtnLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 40));
        moreBtnLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 6));
        inner.addView(moreToolsToggleBtn, moreBtnLp);

        moreToolsPanel = Ui.vertical(this);
        moreToolsPanel.setBackgroundColor(Color.TRANSPARENT);
        moreToolsPanel.setVisibility(View.GONE);

        LinearLayout advA11yRow1 = new LinearLayout(this);
        advA11yRow1.setOrientation(LinearLayout.HORIZONTAL);
        optBigCaptionsBtn = sheetPill("big captions", v -> {
            a11y = a11y.withLargeCaptions(!a11y.largeCaptions);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
        });
        optHapticsBtn = sheetPill("haptics", v -> {
            a11y = a11y.withHapticCues(!a11y.hapticCues);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
            ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
        });
        addEvenRow(advA11yRow1, optBigCaptionsBtn, optHapticsBtn);
        moreToolsPanel.addView(advA11yRow1);

        LinearLayout advA11yRow2 = new LinearLayout(this);
        advA11yRow2.setOrientation(LinearLayout.HORIZONTAL);
        optSoundRadarBtn = sheetPill("sound radar", v -> {
            a11y = a11y.withVisualSoundRadar(!a11y.visualSoundRadar);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(false);
        });
        optAudioSonarBtn = sheetPill("audio sonar", v -> {
            a11y = a11y.withAudioFirstNarration(!a11y.audioFirstNarration);
            ExploreAccessibility.save(this, a11y);
            applyAccessibilitySettings(true);
        });
        addEvenRow(advA11yRow2, optSoundRadarBtn, optAudioSonarBtn);
        moreToolsPanel.addView(advA11yRow2);

        LinearLayout advSensorRow1 = new LinearLayout(this);
        advSensorRow1.setOrientation(LinearLayout.HORIZONTAL);
        arModeBtn = sheetPill("engine: gyro 60", v -> toggleArTrackingMode());
        arModeBtn.setId(R.id.live_ar_mode_toggle);
        dualCamBtn = sheetPill("dual-cam sweep", v -> {
            setToolsSheetOpen(false);
            runDualCamAmbientSweep();
        });
        dualCamBtn.setId(R.id.live_dual_cam_btn);
        addEvenRow(advSensorRow1, arModeBtn, dualCamBtn);
        moreToolsPanel.addView(advSensorRow1);

        LinearLayout advSensorRow2 = new LinearLayout(this);
        advSensorRow2.setOrientation(LinearLayout.HORIZONTAL);
        Button echoBtn = sheetPill("echo ping", v -> {
            setToolsSheetOpen(false);
            triggerAcousticEchoPing();
        });
        Button mapsWalkBtn = sheetPill("maps live walk", v -> {
            setToolsSheetOpen(false);
            openGoogleMapsWalkingLiveView("");
        });
        addEvenRow(advSensorRow2, echoBtn, mapsWalkBtn);
        moreToolsPanel.addView(advSensorRow2);

        LinearLayout advSensorRow3 = new LinearLayout(this);
        advSensorRow3.setOrientation(LinearLayout.HORIZONTAL);
        Button earthBtn = sheetPill("google earth", v -> {
            setToolsSheetOpen(false);
            openGoogleEarthOrHint();
        });
        Button singBtn = sheetPill("sing zoe", v -> {
            setToolsSheetOpen(false);
            singZoeOffline();
        });
        addEvenRow(advSensorRow3, earthBtn, singBtn);
        moreToolsPanel.addView(advSensorRow3);

        telemetryHudLine = Ui.text(this, "spatial field idle · local-only, zero pii", 11.5f, Ui.TEXT);
        telemetryHudLine.setId(R.id.live_telemetry_hud);
        telemetryHudLine.setTextColor(Color.rgb(168, 224, 248));
        telemetryHudLine.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
        telemetryHudLine.setBackground(Ui.tonalPillDrawable(this, Color.argb(140, 8, 12, 22), Ui.CYAN, 14));
        LinearLayout.LayoutParams telLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        telLp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));
        moreToolsPanel.addView(telemetryHudLine, telLp);

        inner.addView(moreToolsPanel);
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
        if (observationBoxView != null) {
            observationBoxView.setVisualSoundRadarEnabled(a11y.visualSoundRadar);
        }
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
        captionView.setText(text == null ? "" : text.toLowerCase(Locale.US));
        captionView.setVisibility(View.VISIBLE);
        if ((cameraOn || arModeOn) && !a11y.largeCaptions && !keepVisibleLonger) {
            mainHandler.postDelayed(hideIdleCaptionTask, CAPTION_IDLE_FADE_MS);
        }
    }

    @Override
    public void onConfigurationChanged(@NonNull Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        applyResponsiveGeometry(newConfig);
        int rot = getCurrentDisplayRotation();
        if (activeImageAnalysis != null) {
            activeImageAnalysis.setTargetRotation(rot);
        }
        if (activeCameraPreviewUseCase != null) {
            activeCameraPreviewUseCase.setTargetRotation(rot);
        }
    }

    private int getCurrentDisplayRotation() {
        try {
            if (cameraPreview != null && cameraPreview.getDisplay() != null) {
                return cameraPreview.getDisplay().getRotation();
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && getDisplay() != null) {
                return getDisplay().getRotation();
            }
            android.view.WindowManager wm = (android.view.WindowManager) getSystemService(WINDOW_SERVICE);
            if (wm != null && wm.getDefaultDisplay() != null) {
                return wm.getDefaultDisplay().getRotation();
            }
        } catch (Throwable ignored) {
        }
        return android.view.Surface.ROTATION_0;
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
        boolean frozenBoxActive = arModeOn && !useHeavyArCore6Dof && isFocusFrameFrozen();
        boolean showLiveCamIcons = (cameraOn || (arModeOn && !useHeavyArCore6Dof)) && !frozenBoxActive;
        if (flipCamBtn != null) {
            flipCamBtn.setVisibility(showLiveCamIcons ? View.VISIBLE : View.GONE);
        }
        if (recenterBtn != null) {
            recenterBtn.setText(arModeOn && !useHeavyArCore6Dof ? "↻" : "◎");
            recenterBtn.setVisibility(arModeOn && !useHeavyArCore6Dof ? View.VISIBLE : View.GONE);
        }
        if (liveHudPill != null) {
            if (!fullScreen) {
                String badge = a11y.profile == ExploreAccessibility.Profile.STANDARD && !a11y.kidFriendly
                        ? "zoe explore"
                        : "zoe · " + a11y.shortBadge().toLowerCase(Locale.US);
                liveHudPill.setText(badge);
            } else if (arModeOn) {
                liveHudPill.setText(frozenBoxActive ? "● box · frozen" : "● box");
            } else {
                liveHudPill.setText(spatialFieldOn ? "● live · field" : "● live");
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
            arToggleBtn.setText(arModeOn ? "● focus" : "focus");
            if (arModeOn) {
                int ruby = Ui.resolveColor(this, Ui.RUBY);
                arToggleBtn.setTextColor(Color.WHITE);
                arToggleBtn.setBackground(Ui.tonalPillDrawable(this, ruby, ruby, 22));
            } else {
                arToggleBtn.setTextColor(fullScreen ? Color.WHITE : Ui.textColor(this));
                arToggleBtn.setBackground(Ui.tonalPillDrawable(this,
                        fullScreen ? Color.argb(175, 22, 26, 38) : Ui.panelColor(this),
                        Ui.resolveColor(this, Ui.RUBY), 22));
            }
        }
        if (listenBtn != null && currentOrbState == OrbState.IDLE) {
            listenBtn.setText(a11y.profile == ExploreAccessibility.Profile.DEAF_HOH && (cameraOn || arModeOn)
                    ? "look"
                    : "talk");
        }
    }

    private void styleDrawerButtons() {
        styleSheetToggle(a11yStandardBtn, a11y.profile == ExploreAccessibility.Profile.STANDARD, Ui.COBALT);
        styleSheetToggle(a11yDeafBtn, a11y.profile == ExploreAccessibility.Profile.DEAF_HOH, Ui.CYAN);
        styleSheetToggle(a11yBlindBtn, a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION, Ui.GOLD);
        if (a11yKidBtn != null) {
            a11yKidBtn.setText(a11y.kidFriendly ? "kid mode: on" : "kid mode: off");
            styleSheetToggle(a11yKidBtn, a11y.kidFriendly, Ui.GREEN);
        }
        styleSheetToggle(optBigCaptionsBtn, a11y.largeCaptions, Ui.CYAN);
        styleSheetToggle(optHapticsBtn, a11y.hapticCues, Ui.GREEN);
        styleSheetToggle(optSoundRadarBtn, a11y.visualSoundRadar, Ui.CYAN);
        styleSheetToggle(optAudioSonarBtn, a11y.audioFirstNarration, Ui.GOLD);
        styleSheetToggle(optTypeBarBtn, a11y.showTypeBar, Ui.COBALT);

        if (cameraToggleBtn != null) {
            cameraToggleBtn.setText(arModeOn ? "camera: ar" : (cameraOn ? "camera: on" : "camera: off"));
            styleSheetToggle(cameraToggleBtn, cameraOn || arModeOn, Ui.GREEN);
        }
        if (arModeBtn != null) {
            arModeBtn.setText(useHeavyArCore6Dof ? "engine: 6dof" : "engine: gyro 60");
            styleSheetToggle(arModeBtn, useHeavyArCore6Dof, Ui.COBALT);
        }
        if (arRoamBtn != null) {
            arRoamBtn.setText(arRoamEnabled ? "glide: on" : "glide: off");
            styleSheetToggle(arRoamBtn, arRoamEnabled, Ui.GREEN);
        }
        if (fieldToggleBtn != null) {
            fieldToggleBtn.setText(spatialFieldOn ? "field: on" : "field: off");
            styleSheetToggle(fieldToggleBtn, spatialFieldOn, Ui.GREEN);
        }
        if (hiZoeToggleBtn != null) {
            hiZoeToggleBtn.setText(hiZoeWakeMode ? "hi zoe: on" : "hi zoe: off");
            styleSheetToggle(hiZoeToggleBtn, hiZoeWakeMode, Ui.CYAN);
        }
        if (webToggleBtn != null) {
            webToggleBtn.setText(webOn ? "web: on" : "web: off");
            styleSheetToggle(webToggleBtn, webOn, Ui.COBALT);
        }
        if (voiceModeBtn != null) {
            voiceModeBtn.setText(useNativeVoice ? "voice: zoe 44k" : "voice: os");
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
                mainHandler.removeCallbacks(speakingWatchdog);
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
            case START_LIVE_CAMERA_AND_VOICE -> {
                if (camGranted) {
                    launchLiveCameraSession(micGranted && !a11y.muteSpokenTts);
                } else if (micGranted && !a11y.muteSpokenTts) {
                    beginContinuousVoiceSession();
                    showCaption("camera permission off. voice mode is ready.", true);
                } else {
                    showCaption("Camera permission is needed for live camera view.", true);
                }
            }
            case START_AR_SPACE -> {
                if (camGranted) {
                    // Only start voice automatically if NOT in Deaf silent mode
                    startArSpaceAndVoice(micGranted && !a11y.muteSpokenTts);
                } else {
                    showCaption("Camera permission is needed for Zoe Explore AR.", true);
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
        showCaption("say \"hi zoe\" anytime. tap end to stop.", false);
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

    // --- Gemini-Live Instant Camera View + Autonomous Zoe Explore AR ---

    private void startLiveCameraAndVoiceOnEntry() {
        if (isFinishing() || isDestroyed()) {
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
            pendingAction = PendingAction.START_LIVE_CAMERA_AND_VOICE;
            ActivityCompat.requestPermissions(this, needed.toArray(new String[0]), PERM_REQ);
            return;
        }
        boolean hasMic = ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
        launchLiveCameraSession(hasMic && !a11y.muteSpokenTts);
    }

    private void launchLiveCameraSession(boolean withVoice) {
        if (!cameraOn) {
            startCamera();
        }
        if (!a11y.largeCaptions && captionView != null) {
            mainHandler.removeCallbacks(hideIdleCaptionTask);
            captionView.setVisibility(View.GONE);
        }
        if (withVoice && !callActive) {
            callActive = true;
            hiZoeWakeMode = false;
            consecutiveErrors = 0;
            styleDrawerButtons();
            updateKeepScreenOn();
            // Warm natural ice-breaker so an open microphone never feels awkward
            long greetingTurn = activeTurnId.incrementAndGet();
            lastUserSpoken = "";
            String opener = a11y.kidFriendly
                    ? "hey! what are we looking at?"
                    : "hey, what are we looking at?";
            finishSimpleReply(greetingTurn, opener);
        }
    }

    private void toggleArSpace() {
        if (arModeOn) {
            stopArOverlayKeepCamera();
            showCaption("zoe explore paused. live camera is still on.", false);
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
            showCaption("arcore 6dof unavailable on this device. using smooth 60fps gyro spatial.", true);
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
        clearPendingCuriosityCrop();
        autoCuriosityStep = 0;
        arRoamEnabled = true;
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
        if (!a11y.largeCaptions && captionView != null) {
            mainHandler.removeCallbacks(hideIdleCaptionTask);
            captionView.setVisibility(View.GONE);
        }
        if (withVoice && !callActive) {
            beginContinuousVoiceSession();
        }
        // Quiet Observation Box mode: gently inspect the framed region once ready (no noisy background roaming timer!)
        if (!useHeavyArCore6Dof) {
            mainHandler.postDelayed(() -> {
                if (arModeOn && !useHeavyArCore6Dof && observationBoxView != null
                        && !isFinishing() && !isDestroyed()) {
                    handleObservationBoxSettled(
                            observationBoxView.getBoxLeftNorm(),
                            observationBoxView.getBoxTopNorm(),
                            observationBoxView.getBoxRightNorm(),
                            observationBoxView.getBoxBottomNorm(),
                            false);
                }
            }, 850L);
        }
    }

    private void scheduleNextCuriosityTick(long delayMs) {
        mainHandler.removeCallbacks(autonomousCuriosityTask);
        if (!arModeOn || !arRoamEnabled || isFinishing() || isDestroyed()) {
            return;
        }
        mainHandler.postDelayed(autonomousCuriosityTask, Math.max(1_200L, delayMs));
    }

    private void runAutonomousCuriosityTick() {
        if (!arModeOn || !arRoamEnabled || isFinishing() || isDestroyed()) {
            return;
        }
        // Never interrupt the user while talking, thinking, speaking, resting, or using Tools
        long now = System.currentTimeMillis();
        if (toolsOpen
                || currentPosture == LiveViewErgonomics.Posture.SAFETY_REST
                || currentOrbState == OrbState.THINKING
                || currentOrbState == OrbState.SPEAKING
                || (now - lastUserSpeechMs) < 5_000L
                || (!latestPartialHeard.isEmpty() && (now - latestPartialAtMs) < 2_500L)) {
            scheduleNextCuriosityTick(3_000L);
            return;
        }
        if (useHeavyArCore6Dof) {
            scheduleNextCuriosityTick(AUTONOMOUS_CURIOSITY_INTERVAL_MS);
            return;
        }

        final int step = autoCuriosityStep++;
        final float prevU = lastAutoSpotU;
        final float prevV = lastAutoSpotV;
        final Bitmap snap = getLatestCameraFrameCopy();
        executor.execute(() -> {
            ArExploreBrain.CuriositySpot spot;
            try {
                if (snap != null) {
                    Bitmap tiny = Bitmap.createScaledBitmap(snap, 96, 72, true);
                    int[] pixels = new int[96 * 72];
                    tiny.getPixels(pixels, 0, 96, 0, 0, 96, 72);
                    if (tiny != snap && !tiny.isRecycled()) {
                        tiny.recycle();
                    }
                    spot = ArExploreBrain.pickVisualCuriositySpot(pixels, 96, 72, prevU, prevV, step);
                } else {
                    spot = ArExploreBrain.pickVisualCuriositySpot(null, 0, 0, prevU, prevV, step);
                }
            } finally {
                if (snap != null && !snap.isRecycled()) {
                    snap.recycle();
                }
            }
            final ArExploreBrain.CuriositySpot chosen = spot;
            runOnUiThread(() -> {
                if (!arModeOn || !arRoamEnabled || isFinishing() || isDestroyed()) {
                    return;
                }
                lastAutoSpotU = chosen.u;
                lastAutoSpotV = chosen.v;
                if (spatialOverlayView != null) {
                    spatialOverlayView.glideToAutonomousSpot(chosen.u, chosen.v, chosen.distanceMeters);
                }
                scheduleNextCuriosityTick(AUTONOMOUS_CURIOSITY_INTERVAL_MS);
            });
        });
    }

    private void savePendingCuriosityCrop(Bitmap crop) {
        if (crop == null || crop.isRecycled()) {
            return;
        }
        // IMPORTANT: NEVER call MediaChatHelper.scaleDown(crop, ...) here because scaleDown
        // recycles its input bitmap, which would crash downstream OCR/label/prior inspection!
        int w = crop.getWidth();
        int h = crop.getHeight();
        int largest = Math.max(w, h);
        Bitmap compact;
        if (largest > 320) {
            float ratio = 320f / largest;
            compact = Bitmap.createScaledBitmap(
                    crop,
                    Math.max(1, Math.round(w * ratio)),
                    Math.max(1, Math.round(h * ratio)),
                    true);
        } else {
            compact = crop.copy(Bitmap.Config.ARGB_8888, false);
        }
        if (compact == null || compact.isRecycled()) {
            return;
        }
        synchronized (curiosityCropLock) {
            if (pendingCuriosityCrop != null && !pendingCuriosityCrop.isRecycled()) {
                pendingCuriosityCrop.recycle();
            }
            pendingCuriosityCrop = compact;
            pendingCuriosityAskedMs = System.currentTimeMillis();
        }
    }

    private Bitmap takePendingCuriosityCropIfFresh() {
        synchronized (curiosityCropLock) {
            if (pendingCuriosityCrop == null || pendingCuriosityCrop.isRecycled()) {
                return null;
            }
            if ((System.currentTimeMillis() - pendingCuriosityAskedMs) > 30_000L) {
                pendingCuriosityCrop.recycle();
                pendingCuriosityCrop = null;
                return null;
            }
            Bitmap out = pendingCuriosityCrop;
            pendingCuriosityCrop = null;
            pendingCuriosityAskedMs = 0L;
            return out;
        }
    }

    private void clearPendingCuriosityCrop() {
        synchronized (curiosityCropLock) {
            if (pendingCuriosityCrop != null && !pendingCuriosityCrop.isRecycled()) {
                pendingCuriosityCrop.recycle();
            }
            pendingCuriosityCrop = null;
            pendingCuriosityAskedMs = 0L;
        }
    }

    private void stopArOverlayKeepCamera() {
        mainHandler.removeCallbacks(autonomousCuriosityTask);
        clearPendingCuriosityCrop();
        arModeOn = false;
        stopArEnginesOnly();
        if (cameraPreview != null) {
            cameraPreview.setVisibility(View.VISIBLE);
        }
        if (!cameraOn) {
            cameraOn = true;
            cameraPreview.post(this::bindCameraPreview);
        }
        updateFullScreenVisualMode();
        styleDrawerButtons();
        updateKeepScreenOn();
    }

    private void startActiveArEngine() {
        final long gen = arStartGen.incrementAndGet();
        if (!useHeavyArCore6Dof) {
            arSurfaceHost.setVisibility(View.GONE);
            spatialOverlayView.setActive(false);
            spatialOverlayView.setVisibility(View.GONE);
            cameraPreview.setVisibility(View.VISIBLE);
            observationBoxView.setVisibility(View.VISIBLE);
            observationBoxView.setVisualSoundRadarEnabled(a11y.visualSoundRadar);
            observationBoxView.setActive(true);
            if (!cameraOn) {
                cameraOn = true;
                pendingFreezeOnNextCameraFrame = true;
                liveHudPill.setText("● box");
                cameraPreview.post(this::bindCameraPreview);
            } else {
                boolean froze = freezeCurrentFrameForObservationBox();
                if (!froze) {
                    pendingFreezeOnNextCameraFrame = true;
                }
                liveHudPill.setText(froze ? "● box · frozen" : "● box");
            }
            return;
        }
        clearFrozenFocusFrame();
        // Safe Camera2 hardware release handoff (260ms) before starting ARCore 6DoF Session
        boolean hadCameraX = cameraOn;
        if (hadCameraX) {
            unbindCameraPreviewOnly();
        }
        if (observationBoxView != null) {
            observationBoxView.setActive(false);
            observationBoxView.setVisibility(View.GONE);
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
                        handleArSpotInspection(uprightFrame, worldPos, distanceMeters, 0.5f, 0.5f, userTapped);
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
        clearFrozenFocusFrame();
        if (observationBoxView != null) {
            observationBoxView.setActive(false);
            observationBoxView.setVisibility(View.GONE);
        }
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
        mainHandler.removeCallbacks(autonomousCuriosityTask);
        clearPendingCuriosityCrop();
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
        if (arModeOn && arRoamEnabled) {
            scheduleNextCuriosityTick(FIRST_CURIOSITY_DELAY_MS);
        } else {
            mainHandler.removeCallbacks(autonomousCuriosityTask);
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
        // Live-View Ergonomic Posture (Tilt-Down Safety Rest / Tilt-Up Instant AR!)
        LiveViewErgonomics.Posture nextP = LiveViewErgonomics.nextPosture(
                currentPosture, spatialTelemetry.getPitchDegrees());
        if (nextP != currentPosture) {
            currentPosture = nextP;
            if (spatialOverlayView != null) {
                spatialOverlayView.setPosture(currentPosture);
            }
            if (a11y.hapticCues) {
                ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.DIRECTION_LOCK, true);
            }
        }
        if (spatialOverlayView != null) {
            spatialTelemetry.updateImuStability(spatialOverlayView.getImuStability());
            spatialOverlayView.setLightField(snap.lightField);
            spatialOverlayView.setSpatialCoherence(snap.spatialCoherence);
            spatialOverlayView.setPreferredHoverDepth(snap.suggestedDepthMeters);
            spatialOverlayView.updateCurrentTrueHeading(spatialTelemetry.getCompassDegrees());
            if (Float.isFinite(activeGuideBearingDeg) && Float.isFinite(spatialTelemetry.getCompassDegrees())) {
                float d = LiveViewErgonomics.signedBearingDeltaDeg(spatialTelemetry.getCompassDegrees(), activeGuideBearingDeg);
                boolean centered = Math.abs(d) <= 12f;
                if (centered && !lastGuideWasCentered) {
                    ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.DIRECTION_LOCK, a11y.hapticCues);
                    if (a11y.spatialAudioBeacon) {
                        ExploreAccessibility.playStereoSpatialChimeAsync(0f, 0.8f);
                    }
                }
                lastGuideWasCentered = centered;
            }
        }
        String place = spatialTelemetry.getLocalPlaceLabel();
        int steps = spatialTelemetry.getStepCount();
        StringBuilder enrichedCtx = new StringBuilder(snap.voiceContextLine);
        if (place != null && !place.isEmpty()) {
            enrichedCtx.append(" Near ").append(place).append(".");
        }
        if (steps > 0) {
            enrichedCtx.append(" Walked ").append(steps).append(" steps.");
        }
        latestSpatialContext = enrichedCtx.toString().trim();
        runOnUiThread(() -> {
            if (spatialFieldOn && telemetryHudLine != null && !isFinishing() && !isDestroyed()) {
                String hud = snap.compactHudLine;
                if (place != null && !place.isEmpty()) {
                    hud = place + " · " + hud;
                }
                telemetryHudLine.setText(hud);
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

    private void openGoogleMapsWalkingLiveView(String destination) {
        String target = destination == null ? "" : destination.trim();
        if (target.isEmpty()) {
            Location loc = spatialTelemetry != null ? spatialTelemetry.getLatestLocation() : null;
            if (loc != null) {
                try {
                    String geo = String.format(Locale.US, "geo:%.6f,%.6f?z=19", loc.getLatitude(), loc.getLongitude());
                    startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(geo)));
                    return;
                } catch (Exception ignored) {
                }
            }
            showCaption("Say \"Walk to <place>\" (e.g. \"Walk to coffee shop\") to open Google Maps Walking / Live View!", true);
            return;
        }
        try {
            String navUri = LiveViewErgonomics.buildGoogleMapsWalkingUri(target);
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(navUri)));
        } catch (Exception ignored) {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://www.google.com/maps/dir/?api=1&travelmode=walking&destination=" + Uri.encode(target))));
            } catch (Exception ignored2) {
            }
        }
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
        String place = spatialTelemetry.getLocalPlaceLabel();
        if (place != null && !place.isEmpty()) {
            summary = "Near " + place + ". " + summary;
        }
        int steps = spatialTelemetry.getStepCount();
        if (steps > 0) {
            summary = summary + " " + steps + (steps == 1 ? " step walked." : " steps walked.");
        }
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

    /**
     * Freezes the live camera view into a crisp still frame so the user never has to keep
     * holding their phone up while framing or talking inside Zoe's Temporary Bounding Box.
     */
    private boolean freezeCurrentFrameForObservationBox() {
        Bitmap previewSnap = null;
        boolean fromPreview = false;
        try {
            if (cameraPreview != null && cameraPreview.getWidth() > 0 && cameraPreview.getHeight() > 0) {
                previewSnap = cameraPreview.getBitmap();
                if (previewSnap != null && !previewSnap.isRecycled()) {
                    fromPreview = true;
                }
            }
        } catch (Throwable ignored) {
            previewSnap = null;
        }
        if (previewSnap == null) {
            Bitmap fallback = getLatestCameraFrameCopy();
            if (fallback != null && !fallback.isRecycled()) {
                if (useFrontCamera) {
                    Matrix mirror = new Matrix();
                    mirror.postScale(-1f, 1f);
                    Bitmap flipped = Bitmap.createBitmap(
                            fallback, 0, 0, fallback.getWidth(), fallback.getHeight(), mirror, true);
                    if (flipped != fallback) {
                        fallback.recycle();
                    }
                    previewSnap = flipped;
                } else {
                    previewSnap = fallback;
                }
            }
        }
        if (previewSnap == null || previewSnap.isRecycled()) {
            return false;
        }
        Bitmap oldToRecycle;
        synchronized (frozenFrameLock) {
            oldToRecycle = frozenFocusBitmap;
            frozenFocusBitmap = previewSnap;
            frozenFrameIsPreviewSpace = fromPreview;
        }
        pendingFreezeOnNextCameraFrame = false;
        if (frozenFrameView != null) {
            frozenFrameView.setImageBitmap(previewSnap);
            frozenFrameView.setVisibility(View.VISIBLE);
        }
        // Hide SurfaceView and sleep the live camera HAL while frozen!
        // Eliminates SurfaceFlinger transparent-region spam and keeps the phone cool in the user's lap.
        if (cameraPreview != null) {
            cameraPreview.setVisibility(View.INVISIBLE);
        }
        if (cameraOn) {
            unbindCameraPreviewOnly();
        }
        if (oldToRecycle != null && oldToRecycle != previewSnap && !oldToRecycle.isRecycled()) {
            oldToRecycle.recycle();
        }
        updateFullScreenVisualMode();
        return true;
    }

    private void retakeFrozenFocusFrame() {
        if (!arModeOn || useHeavyArCore6Dof || isFinishing() || isDestroyed()) {
            return;
        }
        clearFrozenFocusFrame();
        if (observationBoxView != null) {
            observationBoxView.setBoxArAnalysis(null);
        }
        if (cameraPreview != null) {
            cameraPreview.setVisibility(View.VISIBLE);
        }
        if (!cameraOn) {
            cameraOn = true;
            cameraPreview.post(this::bindCameraPreview);
        }
        pendingFreezeOnNextCameraFrame = true;
        updateFullScreenVisualMode();
        showCaption("snapping a new still frame…", true);
        mainHandler.postDelayed(() -> {
            if (arModeOn && !useHeavyArCore6Dof && !isFinishing() && !isDestroyed()) {
                if (!isFocusFrameFrozen()) {
                    freezeCurrentFrameForObservationBox();
                }
                if (observationBoxView != null) {
                    handleObservationBoxSettled(
                            observationBoxView.getBoxLeftNorm(),
                            observationBoxView.getBoxTopNorm(),
                            observationBoxView.getBoxRightNorm(),
                            observationBoxView.getBoxBottomNorm(),
                            false);
                }
            }
        }, 780L);
    }

    private void clearFrozenFocusFrame() {
        pendingFreezeOnNextCameraFrame = false;
        if (frozenFrameView != null) {
            frozenFrameView.setImageDrawable(null);
            frozenFrameView.setVisibility(View.GONE);
        }
        Bitmap toRecycle;
        synchronized (frozenFrameLock) {
            toRecycle = frozenFocusBitmap;
            frozenFocusBitmap = null;
            frozenFrameIsPreviewSpace = false;
        }
        if (toRecycle != null && !toRecycle.isRecycled()) {
            toRecycle.recycle();
        }
    }

    private boolean isFocusFrameFrozen() {
        synchronized (frozenFrameLock) {
            return frozenFocusBitmap != null && !frozenFocusBitmap.isRecycled();
        }
    }

    /**
     * Crops strictly inside [leftU, topV, rightU, bottomV] from the frozen still frame (or falls back
     * to the latest live frame if still warming up). Returns a fresh Bitmap owned by the caller.
     */
    private Bitmap getFrozenBoxCrop(float leftU, float topV, float rightU, float bottomV) {
        Bitmap frozenCopy = null;
        boolean previewSpace = false;
        synchronized (frozenFrameLock) {
            if (frozenFocusBitmap != null && !frozenFocusBitmap.isRecycled()) {
                frozenCopy = frozenFocusBitmap.copy(Bitmap.Config.ARGB_8888, false);
                previewSpace = frozenFrameIsPreviewSpace;
            }
        }
        if (frozenCopy != null) {
            try {
                if (previewSpace) {
                    int w = frozenCopy.getWidth();
                    int h = frozenCopy.getHeight();
                    int x0 = Math.max(0, Math.min(w - 2, Math.round(Math.min(leftU, rightU) * w)));
                    int y0 = Math.max(0, Math.min(h - 2, Math.round(Math.min(topV, bottomV) * h)));
                    int x1 = Math.max(x0 + 2, Math.min(w, Math.round(Math.max(leftU, rightU) * w)));
                    int y1 = Math.max(y0 + 2, Math.min(h, Math.round(Math.max(topV, bottomV) * h)));
                    return Bitmap.createBitmap(frozenCopy, x0, y0, x1 - x0, y1 - y0);
                }
                int pw = cameraPreview != null ? cameraPreview.getWidth() : 0;
                int ph = cameraPreview != null ? cameraPreview.getHeight() : 0;
                return MediaChatHelper.cropRectRegion(frozenCopy, leftU, topV, rightU, bottomV, pw, ph, false);
            } finally {
                if (!frozenCopy.isRecycled()) {
                    frozenCopy.recycle();
                }
            }
        }
        Bitmap live = getLatestCameraFrameCopy();
        if (live == null) {
            return null;
        }
        try {
            int pw = cameraPreview != null ? cameraPreview.getWidth() : 0;
            int ph = cameraPreview != null ? cameraPreview.getHeight() : 0;
            return MediaChatHelper.cropRectRegion(live, leftU, topV, rightU, bottomV, pw, ph, useFrontCamera);
        } finally {
            if (!live.isRecycled()) {
                live.recycle();
            }
        }
    }

    /**
     * Temporary Bounding Box AR Sandbox ("Tunnel Vision"): crops strictly inside the user's framed
     * Selection Box [leftU, topV, rightU, bottomV] from the frozen still frame, runs lightweight
     * local AR feature analysis ONLY inside the box so Zoe glides beside the subject inside her box,
     * and gently asks "what's this?" to invite a natural reply.
     */
    private void handleObservationBoxSettled(float leftU, float topV, float rightU, float bottomV, boolean wasTap) {
        if (!arModeOn || isFinishing() || isDestroyed()) {
            return;
        }
        if (!isFocusFrameFrozen()) {
            freezeCurrentFrameForObservationBox();
        }
        final Bitmap boxCrop = getFrozenBoxCrop(leftU, topV, rightU, bottomV);
        if (boxCrop == null) {
            return;
        }
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "";
        setOrbState(OrbState.THINKING, "looking…");
        showCaption("looking inside the box…", true);
        final int stepForQuestion = autoCuriosityStep++;

        executor.execute(() -> {
            String cropReport = "";
            String learnedHint = "";
            byte[] jpeg = null;
            try {
                if (!boxCrop.isRecycled()) {
                    // Broad-phase / narrow-phase local AR feature detection strictly inside the box!
                    Bitmap tiny = Bitmap.createScaledBitmap(boxCrop, 72, 72, true);
                    int[] px = new int[72 * 72];
                    tiny.getPixels(px, 0, 72, 0, 0, 72, 72);
                    if (tiny != boxCrop && !tiny.isRecycled()) {
                        tiny.recycle();
                    }
                    final ArExploreBrain.BoxArAnalysis finalBoxAr = ArExploreBrain.analyzeBoundingBoxPixels(px, 72, 72);
                    runOnUiThread(() -> {
                        if (arModeOn && !useHeavyArCore6Dof && observationBoxView != null
                                && !isFinishing() && !isDestroyed()) {
                            observationBoxView.setBoxArAnalysis(finalBoxAr);
                        }
                    });

                    savePendingCuriosityCrop(boxCrop);
                    cropReport = MediaChatHelper.inspectFrameOffline(boxCrop);
                    learnedHint = VisionPriorStore.buildSilentExploreContext(this, boxCrop);
                    jpeg = MediaChatHelper.bitmapToJpeg(boxCrop, 84);
                }
            } catch (Throwable ignored) {
                // Never swallow and freeze in THINKING: proceed cleanly to natural curious fallback!
            } finally {
                if (!boxCrop.isRecycled()) {
                    boxCrop.recycle();
                }
            }

            String cleanLearnedName = ExploreDecisionEngine.extractCleanLearnedName(learnedHint);
            latestCameraReport = learnedHint.isEmpty() ? cropReport : (cropReport + " " + learnedHint);
            latestCameraJpeg = jpeg;

            if (myTurn != activeTurnId.get()) {
                return;
            }

            // Optional Gemini Vision cloud look strictly on the user's framed selection box
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (jpeg != null && !geminiKey.isEmpty()) {
                try {
                    String prompt = "You are Zoe looking strictly inside the user's temporary bounding box on a still frame. "
                            + "Gently ask ONE short, friendly curious question (under 14 words, plain speech, no em dashes) "
                            + "like 'Ooh, what's this?' or asking them to tell you about what is inside the box.";
                    String reply = CloudVisionClient.askVision(
                            geminiKey, MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT + "\n" + prompt, jpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }

            String question = ArExploreBrain.buildNaturalCuriousQuestion(
                    cropReport, cleanLearnedName, 1.0f, stepForQuestion, a11y.kidFriendly);
            final String finalQuestion = question.trim();
            runOnUiThread(() -> finishSimpleReply(myTurn, finalQuestion));
        });
    }

    /**
     * Collaborative investigation when the user answers "i don't know" to Zoe's "what's this?" question:
     * responds warmly with "let's figure it out together!" and shares honest clues strictly from the box.
     */
    private void investigateObservationBoxTogether(String rawSpoken, Bitmap freshBoxCrop) {
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = rawSpoken;
        setOrbState(OrbState.THINKING, "figuring it out…");
        showCaption(LiveSessionLogic.formatLiveCaption(rawSpoken, "let's figure it out together…"), true);

        executor.execute(() -> {
            Bitmap crop = freshBoxCrop;
            String report = "";
            String shapeSummary = "";
            String colorSummary = "";
            byte[] jpeg = null;
            try {
                if (crop != null && !crop.isRecycled()) {
                    report = MediaChatHelper.inspectFrameOffline(crop);
                    FramePalette.Analysis pal = FramePalette.analyzeBitmap(crop);
                    if (pal != null) {
                        colorSummary = MediaChatHelper.formatDistinctColorNames(pal.names);
                    }
                    PatentReverseImageEngine.VisualSignature sig = PatentReverseImageEngine.extractFromBitmap(crop, true);
                    if (sig != null && sig.shapeSummary != null) {
                        shapeSummary = sig.shapeSummary;
                    }
                    jpeg = MediaChatHelper.bitmapToJpeg(crop, 82);
                    // Keep the crop saved in case the user figures it out and names it right after!
                    savePendingCuriosityCrop(crop);
                }
            } catch (Throwable ignored) {
                // Always recover cleanly to collaborative offline response instead of hanging
            } finally {
                if (crop != null && !crop.isRecycled()) {
                    crop.recycle();
                }
            }
            if (myTurn != activeTurnId.get()) {
                return;
            }

            // Optional Gemini Vision or Workstation Frontier-Pro collaborative sleuthing strictly on the box crop
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (jpeg != null && !geminiKey.isEmpty()) {
                try {
                    String prompt = "The user said '" + rawSpoken + "' about the object inside their selection box. "
                            + "Start with 'Let's figure it out together!' and share 1 or 2 short, concrete visual clues "
                            + "you spot in this crop so we can narrow down what it is. Plain speech, no em dashes.";
                    String reply = CloudVisionClient.askVision(
                            geminiKey, MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT + "\n" + prompt, jpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }
            if (workstationReachable) {
                try {
                    String endpoint = ElizaGemClient.savedEndpoint(this);
                    String gear = workstationFrontierReady ? "gear3" : "auto";
                    String clues = "User framed an object in Zoe's quiet observation box and said '" + rawSpoken
                            + "'. Observations strictly inside the box: " + report
                            + (colorSummary.isEmpty() ? "" : " Colors: " + colorSummary + ".")
                            + (shapeSummary.isEmpty() ? "" : " Shape: " + shapeSummary + ".")
                            + " Start with 'Let's figure it out together!' and offer 1 or 2 short friendly clues or a follow-up question to help identify it. No em dashes.";
                    ElizaGemClient.ChatReply labRes = studioClient.chat(endpoint, clues, gear);
                    if (myTurn == activeTurnId.get() && labRes != null && labRes.reply != null && !labRes.reply.trim().isEmpty()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(labRes.reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                        return;
                    }
                } catch (Exception ignored) {
                }
            }

            String offlineCollab = ArExploreBrain.buildLetsFigureItOutReply(
                    report, shapeSummary, colorSummary, a11y.kidFriendly);
            runOnUiThread(() -> finishSimpleReply(myTurn, offlineCollab));
        });
    }

    private void handleArSpotInspection(Bitmap uprightFrame, ArExploreBrain.Vec3 worldPos,
                                        float distanceMeters, float tapU, float tapV, boolean userTapped) {
        if (!arModeOn || uprightFrame == null || isFinishing() || isDestroyed()) {
            if (uprightFrame != null && !uprightFrame.isRecycled()) {
                uprightFrame.recycle();
            }
            return;
        }
        if (!userTapped && (currentOrbState == OrbState.THINKING || currentOrbState == OrbState.SPEAKING)) {
            uprightFrame.recycle();
            return;
        }
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "";
        setOrbState(OrbState.THINKING, userTapped ? "LOOKING…" : "CURIOUS…");
        if (userTapped) {
            showCaption("Looking closely right there…", true);
        }
        final float normX = (tapU * 2f) - 1f;
        final int previewW = cameraPreview != null ? cameraPreview.getWidth() : 0;
        final int previewH = cameraPreview != null ? cameraPreview.getHeight() : 0;
        final boolean mirroredFront = useFrontCamera;
        final int stepForQuestion = autoCuriosityStep;

        executor.execute(() -> {
            Bitmap tapCrop = null;
            String cropReport = "";
            String fullReport = "";
            byte[] jpeg = null;
            String learnedHint = "";
            try {
                // 1. Zoom right onto the EXACT spot where Zoe floated or the user tapped
                tapCrop = MediaChatHelper.cropTapRegion(
                        uprightFrame, tapU, tapV, previewW, previewH, mirroredFront, 0.45f);
                if (tapCrop != null) {
                    savePendingCuriosityCrop(tapCrop);
                    cropReport = MediaChatHelper.inspectFrameOffline(tapCrop);
                    learnedHint = VisionPriorStore.buildSilentExploreContext(this, tapCrop);
                    jpeg = MediaChatHelper.bitmapToJpeg(tapCrop, 82);
                } else {
                    savePendingCuriosityCrop(uprightFrame);
                }
                // Fall back to full frame only if zoomed crop had no confident object/text
                String cropLabel = ArExploreBrain.extractPrimaryLabel(cropReport);
                String cropOcr = ArExploreBrain.extractOcrSnippet(cropReport);
                if (cropLabel.isEmpty() && cropOcr.isEmpty()) {
                    fullReport = MediaChatHelper.inspectFrameOffline(uprightFrame);
                    if (learnedHint.isEmpty()) {
                        learnedHint = VisionPriorStore.buildSilentExploreContext(this, uprightFrame);
                    }
                    if (jpeg == null) {
                        jpeg = MediaChatHelper.bitmapToJpeg(uprightFrame, 78);
                    }
                }
            } catch (Throwable err) {
                if (tapCrop != null && !tapCrop.isRecycled()) tapCrop.recycle();
                uprightFrame.recycle();
                return;
            }
            if (tapCrop != null && !tapCrop.isRecycled()) tapCrop.recycle();
            uprightFrame.recycle();

            String bestReport = (!ArExploreBrain.extractPrimaryLabel(cropReport).isEmpty()
                    || !ArExploreBrain.extractOcrSnippet(cropReport).isEmpty())
                    ? cropReport
                    : (!fullReport.isEmpty() ? fullReport : cropReport);
            String cleanLearnedName = ExploreDecisionEngine.extractCleanLearnedName(learnedHint);
            StringBuilder enriched = new StringBuilder(bestReport);
            if (!learnedHint.isEmpty()) enriched.append(" ").append(learnedHint);
            latestCameraReport = enriched.toString().trim();
            latestCameraJpeg = jpeg;

            String label = ArExploreBrain.extractPrimaryLabel(bestReport);
            String ocr = ArExploreBrain.extractOcrSnippet(bestReport);
            arBrain.recordDiscoveryIfNew(bestReport, worldPos, distanceMeters, System.currentTimeMillis());

            if (myTurn != activeTurnId.get()) return;

            // Optional Gemini Vision cloud look ONLY if user saved a Gemini API key
            String geminiKey = MultiAiClient.savedKey(this, MultiAiClient.Provider.GEMINI);
            if (jpeg != null && !geminiKey.isEmpty()) {
                try {
                    String prompt = userTapped
                            ? "In 1 short friendly sentence, name the specific object or text centered in this zoomed camera crop. Be concrete and honest."
                            : "You are Zoe exploring a room in AR with your partner. Ask ONE short, playful, genuinely curious question (under 15 words, plain speech, no em dashes) about the main object in this crop, like 'Ooh, what's this?' or asking them to tell you about it.";
                    String reply = CloudVisionClient.askVision(
                            geminiKey, MultiAiClient.savedModel(this, MultiAiClient.Provider.GEMINI),
                            MultiAiClient.ZOE_SYSTEM_PROMPT + "\n" + prompt, jpeg);
                    if (myTurn == activeTurnId.get()) {
                        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(reply);
                        runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    }
                    return;
                } catch (Exception ignored) {
                }
            }

            // Ultra-fast (<200ms!), zero-thermal-throttle grounded speech
            String reply;
            if (!userTapped) {
                // Zoe leads the exploration and asks YOU the curious question ("Ooh, what's this?")!
                if (a11y.audioFirstNarration || a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION) {
                    String posCue = ExploreAccessibility.clockFaceDirection(normX);
                    String q = ArExploreBrain.buildNaturalCuriousQuestion(
                            bestReport, cleanLearnedName, distanceMeters, stepForQuestion, a11y.kidFriendly);
                    reply = posCue + ": " + q;
                } else {
                    reply = ArExploreBrain.buildNaturalCuriousQuestion(
                            bestReport, cleanLearnedName, distanceMeters, stepForQuestion, a11y.kidFriendly);
                }
            } else if (a11y.audioFirstNarration || a11y.profile == ExploreAccessibility.Profile.BLIND_LOW_VISION) {
                reply = ExploreAccessibility.formatGuidedSceneCue(
                        label, ocr, normX, distanceMeters,
                        spatialTelemetry.getCompassDegrees(),
                        spatialTelemetry.getLightField(),
                        a11y.kidFriendly);
            } else {
                reply = LiveViewErgonomics.buildGroundedVisualAnswer(
                        bestReport, distanceMeters,
                        spatialFieldOn ? spatialTelemetry.getCompassDegrees() : Float.NaN,
                        a11y.kidFriendly);
                if (!cleanLearnedName.isEmpty()) {
                    reply = reply + " Looks like your " + cleanLearnedName + ".";
                }
            }
            final String finalReply = reply.trim();
            runOnUiThread(() -> finishSimpleReply(myTurn, finalReply));
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
                int displayRot = getCurrentDisplayRotation();
                Preview preview = new Preview.Builder()
                        .setTargetRotation(displayRot)
                        .build();
                preview.setSurfaceProvider(cameraPreview.getSurfaceProvider());
                activeCameraPreviewUseCase = preview;

                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setTargetResolution(new Size(640, 480))
                        .setTargetRotation(displayRot)
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build();
                analysis.setAnalyzer(cameraAnalysisExecutor, this::cacheLatestImageProxy);
                activeImageAnalysis = analysis;

                CameraSelector selector = useFrontCamera
                        ? CameraSelector.DEFAULT_FRONT_CAMERA
                        : CameraSelector.DEFAULT_BACK_CAMERA;
                cameraProvider.bindToLifecycle(this, selector, preview, analysis);

                if (dualCamSweepPending) {
                    // Arm opposite-lens capture ONLY AFTER CameraX has bound the opposite lens!
                    dualCamWarmupFrames.set(0);
                    dualCamCaptureArmed = true;
                }
            } catch (Exception error) {
                showCaption("Camera unavailable: " + error.getMessage(), true);
            }
        }, ContextCompat.getMainExecutor(this));
    }

    private void cacheLatestImageProxy(@NonNull ImageProxy proxy) {
        try {
            // While the user's still frame is frozen in Zoe's Temporary Bounding Box, skip live
            // frame decoding to save CPU, heat, and battery while the phone rests comfortably.
            if (arModeOn && !useHeavyArCore6Dof && isFocusFrameFrozen() && !pendingFreezeOnNextCameraFrame) {
                return;
            }
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
            if (!pendingFreezeOnNextCameraFrame && now - lastCameraBitmapMs < 180L) {
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
                if (pendingFreezeOnNextCameraFrame && arModeOn && !useHeavyArCore6Dof) {
                    pendingFreezeOnNextCameraFrame = false;
                    mainHandler.post(() -> {
                        if (arModeOn && !useHeavyArCore6Dof && !isFinishing() && !isDestroyed()
                                && !isFocusFrameFrozen()) {
                            freezeCurrentFrameForObservationBox();
                        }
                    });
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
        int step = Math.max(1, Math.max(w, h) / 480);
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
        activeImageAnalysis = null;
        activeCameraPreviewUseCase = null;
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

    private void describeLiveViewProactively() {
        if (!cameraOn && !arModeOn) {
            toggleArSpace();
            return;
        }
        Bitmap frame = (arModeOn && !useHeavyArCore6Dof && observationBoxView != null)
                ? getFrozenBoxCrop(
                        observationBoxView.getBoxLeftNorm(),
                        observationBoxView.getBoxTopNorm(),
                        observationBoxView.getBoxRightNorm(),
                        observationBoxView.getBoxBottomNorm())
                : (cameraOn
                        ? getLatestCameraFrameCopy()
                        : (arSurfaceView != null ? arSurfaceView.getLatestSnapshotCopy() : null));
        if (frame == null && latestCameraReport.isEmpty()) {
            showCaption("hold steady a second and tap again.", false);
            return;
        }
        long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "what do you see?";
        setOrbState(OrbState.THINKING, "looking…");
        showCaption("looking…", false);
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
                latestPartialHeard = "";
                setOrbState(OrbState.LISTENING, hiZoeWakeMode ? "WAITING FOR 'HI ZOE'" : "LISTENING…");
            }

            @Override
            public void onBeginningOfSpeech() {}

            @Override
            public void onRmsChanged(float rmsdB) {
                if (myGen == listenGen.get()) {
                    float norm = Math.max(0f, Math.min(1f, (rmsdB + 2f) / 11f));
                    orbView.setAudioLevel(norm);
                    if (arModeOn && !useHeavyArCore6Dof && observationBoxView != null) {
                        observationBoxView.setVoiceLevel(norm);
                        if (a11y.visualSoundRadar) {
                            observationBoxView.setAmbientSoundLevel(norm);
                        }
                    }
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
                        // Rescue dropped partial transcript so Zoe NEVER ignores a question on Pixel timeout/no-match!
                        String rescued = latestPartialHeard;
                        long partialTs = latestPartialAtMs;
                        latestPartialHeard = "";
                        if (!hiZoeWakeMode && LiveViewErgonomics.shouldRescuePartialTranscript(
                                rescued, partialTs, System.currentTimeMillis())) {
                            processSpokenPrompt(rescued);
                            return;
                        }
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
                if (heard.isEmpty() && LiveViewErgonomics.shouldRescuePartialTranscript(
                        latestPartialHeard, latestPartialAtMs, System.currentTimeMillis())) {
                    heard = latestPartialHeard.trim();
                }
                latestPartialHeard = "";
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
                            finishSimpleReply(myTurn, "Hi, I'm Zoe. Ready to explore together.");
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
                if (partial != null && !partial.isEmpty() && !partial.get(0).trim().isEmpty()) {
                    String p = partial.get(0).trim();
                    latestPartialHeard = p;
                    latestPartialAtMs = System.currentTimeMillis();
                    if (!hiZoeWakeMode) {
                        showCaption("You: " + p, true);
                    }
                }
            }

            @Override
            public void onEvent(int eventType, Bundle params) {}
        });

        Intent intent = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE, Locale.getDefault().toLanguageTag())
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                // Pixel AiAi & GoogleTTS expect Integer (int), NOT Long — passing Long throws ClassCastException -> 0ms timeout!
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 1800)
                .putExtra(RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS, 1400);
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
        lastUserSpeechMs = System.currentTimeMillis();
        if (ConversationResponse.isStop(spoken)) {
            stopLiveCall();
            return;
        }
        // Live Voice Teaching ("learn this as <object>" / "remember this is my <object>")
        String teachLabel = ZoeLearnQueue.parseLiveTeachLabel(spoken);
        if (!teachLabel.isEmpty()) {
            teachCurrentExploreFrame(teachLabel);
            return;
        }
        // Natural Reverse-Curiosity Conversation when Zoe's Quiet Observation Box is open:
        //   1. "i don't know" / "not sure" -> "let's figure it out together!" using clues strictly inside the box
        //   2. Naming the object ("that's my mug") -> learns the razor-clean cropped contour into visual memory
        if (arModeOn) {
            if (ArExploreBrain.isDontKnowReply(spoken)) {
                Bitmap boxCrop = takePendingCuriosityCropIfFresh();
                if (boxCrop == null && !useHeavyArCore6Dof && observationBoxView != null) {
                    boxCrop = getFrozenBoxCrop(
                            observationBoxView.getBoxLeftNorm(),
                            observationBoxView.getBoxTopNorm(),
                            observationBoxView.getBoxRightNorm(),
                            observationBoxView.getBoxBottomNorm());
                }
                if (boxCrop != null) {
                    investigateObservationBoxTogether(spoken, boxCrop);
                    return;
                }
            }
            String answerName = ArExploreBrain.extractUserAnswerObjectName(spoken);
            if (!answerName.isEmpty()) {
                Bitmap answeredCrop = takePendingCuriosityCropIfFresh();
                if (answeredCrop != null) {
                    learnFromCuriosityAnswer(answerName, answeredCrop, spoken);
                    return;
                }
            }
        }
        String lowQuest = spoken.toLowerCase(Locale.US);
        if (lowQuest.contains("curiosity quest") || lowQuest.contains("surprise me")
                || lowQuest.contains("explore quest") || lowQuest.contains("give me a quest")) {
            triggerCuriosityQuest();
            return;
        }
        // Direct Explore Voice-Action Router: Zoe immediately obeys camera, navigation, bearing & accessibility requests!
        LiveViewErgonomics.ParsedVoiceAction parsed = LiveViewErgonomics.parseExploreVoiceAction(spoken);
        if (parsed.action != LiveViewErgonomics.ExploreVoiceAction.NONE) {
            handleExploreVoiceAction(parsed, spoken);
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

        final boolean cropToObservationBox = arModeOn && !useHeavyArCore6Dof && observationBoxView != null;
        final Bitmap freshFrame = cropToObservationBox
                ? getFrozenBoxCrop(
                        observationBoxView.getBoxLeftNorm(),
                        observationBoxView.getBoxTopNorm(),
                        observationBoxView.getBoxRightNorm(),
                        observationBoxView.getBoxBottomNorm())
                : (cameraOn
                        ? getLatestCameraFrameCopy()
                        : (arModeOn && arSurfaceView != null ? arSurfaceView.getLatestSnapshotCopy() : null));
        executor.execute(() -> {
            if (myTurn != activeTurnId.get()) {
                if (freshFrame != null && !freshFrame.isRecycled()) freshFrame.recycle();
                return;
            }
            Bitmap frameForVision = null;
            if (freshFrame != null) {
                try {
                    Bitmap small = MediaChatHelper.scaleDown(freshFrame, 512);
                    if (small != freshFrame && !freshFrame.isRecycled()) {
                        freshFrame.recycle();
                    }
                    if (small != null) {
                        String baseReport = MediaChatHelper.inspectFrameOffline(small);
                        String learnedHint = VisionPriorStore.buildSilentExploreContext(this, small);
                        latestCameraReport = learnedHint.isEmpty() ? baseReport : (baseReport + " " + learnedHint);
                        latestCameraJpeg = MediaChatHelper.bitmapToJpeg(small, 78);
                        frameForVision = small;
                    }
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

        // Seamless Workstation Frontier-Pro Studio Bridge (USB adb reverse or HTTPS, zero phone API key required!)
        if (workstationReachable) {
            try {
                String endpoint = ElizaGemClient.savedEndpoint(this);
                String gear = workstationFrontierReady ? "gear3" : "auto";
                ElizaGemClient.ChatReply labRes = studioClient.chat(endpoint, fusedPrompt, gear);
                if (myTurn == activeTurnId.get() && labRes != null && labRes.reply != null && !labRes.reply.trim().isEmpty()) {
                    String clean = OnDeviceLlmEngine.enforceZoeSovereignty(labRes.reply);
                    runOnUiThread(() -> finishSimpleReply(myTurn, clean));
                    return;
                }
            } catch (Exception ignored) {
                workstationReachable = false;
                workstationFrontierReady = false;
            }
        }

        // Instant <200ms grounded camera sight path: when asking directly what the camera sees (and no cloud key),
        // answer IMMEDIATELY from zoomed ML Kit + OCR + Palette + learned priors with zero 1.5 GB LLM memory spike!
        if (withCamera && LiveSessionLogic.isLikelyCameraQuestion(spoken)) {
            String grounded = LiveViewErgonomics.buildGroundedVisualAnswer(
                    latestCameraReport, latestArDistanceMeters,
                    spatialFieldOn ? spatialTelemetry.getCompassDegrees() : Float.NaN,
                    a11y.kidFriendly);
            if (myTurn == activeTurnId.get()) {
                runOnUiThread(() -> finishSimpleReply(myTurn, grounded));
            }
            return;
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

    private void triggerCuriosityQuest() {
        long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        String quest = ZoeLearnQueue.curiosityQuest(curiosityQuestIndex++);
        lastUserSpoken = "Curiosity Quest";
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
        finishSimpleReply(myTurn, quest);
    }

    private void promptTeachFromLiveView() {
        if (!cameraOn && !arModeOn) {
            toggleArSpace();
            showCaption("Aim at an object and say \"learn this as…\" or tap ✦ Learn This again.", true);
            return;
        }
        EditText input = Ui.input(this, ArExploreBrain.extractPrimaryLabel(latestCameraReport),
                "What should Zoe learn this as?");
        new android.app.AlertDialog.Builder(this)
                .setTitle("❖ Teach Zoe Live")
                .setMessage("Zoe learns this object's contour geometry locally (shared with Guided Vision) and digests it to your Workstation when linked.")
                .setView(input)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Learn", (d, w) -> {
                    String clean = VisionPriorStore.cleanLabel(input.getText().toString());
                    if (!clean.isEmpty()) {
                        teachCurrentExploreFrame(clean);
                    }
                })
                .show();
    }

    private void learnFromCuriosityAnswer(String label, Bitmap crop, String rawSpoken) {
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = rawSpoken;
        setOrbState(OrbState.THINKING, "LEARNING…");
        showCaption(LiveSessionLogic.formatLiveCaption(rawSpoken, "Remembering \"" + label + "\"…"), true);
        executor.execute(() -> {
            try {
                PatentReverseImageEngine.VisualSignature sig = PatentReverseImageEngine.extractFromBitmap(crop, true);
                VisionPriorStore.teach(this, label, sig, "zoe_explore_curiosity", "", "");
                ZoeLearnQueue.incrementDigestedCount(this);
                if (workstationReachable) {
                    try {
                        MobileDigestionBundle.Summary bundle = MobileDigestionBundle.collect(this, brain);
                        studioClient.digestMobileBundle(ElizaGemClient.savedEndpoint(this), bundle.bundleJson);
                    } catch (Exception ignored) {
                    }
                }
                runOnUiThread(() -> {
                    if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
                        String reply = a11y.kidFriendly
                                ? "Ooh, " + label + "! I'll remember what it looks like. Let's see what else is here!"
                                : "Ooh, " + label + ", got it! I'll remember what that looks like next time we explore.";
                        finishSimpleReply(myTurn, reply);
                        scheduleNextCuriosityTick(AUTONOMOUS_CURIOSITY_INTERVAL_MS);
                    }
                });
            } catch (Exception ignored) {
                runOnUiThread(() -> {
                    if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                        finishSimpleReply(myTurn, "Oh cool, " + label + "! Thanks for telling me.");
                        scheduleNextCuriosityTick(AUTONOMOUS_CURIOSITY_INTERVAL_MS);
                    }
                });
            } finally {
                if (!crop.isRecycled()) {
                    crop.recycle();
                }
            }
        });
    }

    private void teachCurrentExploreFrame(String label) {
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = "Learn this as " + label;
        Bitmap snap = (arModeOn && !useHeavyArCore6Dof && observationBoxView != null)
                ? getFrozenBoxCrop(
                        observationBoxView.getBoxLeftNorm(),
                        observationBoxView.getBoxTopNorm(),
                        observationBoxView.getBoxRightNorm(),
                        observationBoxView.getBoxBottomNorm())
                : (cameraOn
                        ? getLatestCameraFrameCopy()
                        : (arModeOn && arSurfaceView != null ? arSurfaceView.getLatestSnapshotCopy() : null));
        if (snap == null) {
            finishSimpleReply(myTurn, "turn on focus or camera first so i can see \"" + label + "\" and learn its shape!");
            return;
        }
        setOrbState(OrbState.THINKING, "learning…");
        showCaption("zoe\nlearning \"" + label + "\"…", true);
        executor.execute(() -> {
            try {
                PatentReverseImageEngine.VisualSignature sig = PatentReverseImageEngine.extractFromBitmap(snap, true);
                VisionPriorStore.teach(this, label, sig, "explore_live", "", "");
                ZoeLearnQueue.incrementDigestedCount(this);
                boolean synced = false;
                if (workstationReachable) {
                    try {
                        MobileDigestionBundle.Summary bundle = MobileDigestionBundle.collect(this, brain);
                        ElizaGemClient.DigestResult res = studioClient.digestMobileBundle(
                                ElizaGemClient.savedEndpoint(this), bundle.bundleJson);
                        synced = res != null && res.available;
                    } catch (Exception ignored) {
                    }
                }
                final boolean didSync = synced;
                runOnUiThread(() -> {
                    if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.ZOE_SPOTTED, a11y.hapticCues);
                        String msg = didSync
                                ? "Got it! I learned \"" + label + "\" and digested it straight to your Workstation Studio."
                                : "Got it! I learned \"" + label + "\" into my visual memory. I'll recognize it offline next time in both Explore and Guided Vision.";
                        finishSimpleReply(myTurn, msg);
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> {
                    if (myTurn == activeTurnId.get() && !isFinishing() && !isDestroyed()) {
                        finishSimpleReply(myTurn, "Hold steady for a second and try teaching \"" + label + "\" again.");
                    }
                });
            } finally {
                if (!snap.isRecycled()) {
                    snap.recycle();
                }
            }
        });
    }

    private void probeWorkstationBridge() {
        try {
            ElizaGemClient.Status st = studioClient.fetchStatusQuick(ElizaGemClient.savedEndpoint(this));
            workstationReachable = true;
            workstationFrontierReady = st.frontierReady;
            workstationModelLabel = st.frontierReady && !st.frontierModel.isEmpty()
                    ? st.frontierModel : st.defaultGear;
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed() && !cameraOn && !arModeOn && liveHudPill != null) {
                    liveHudPill.setText(workstationFrontierReady ? "pro · explore" : "lab · explore");
                }
            });
        } catch (Exception ignored) {
            workstationReachable = false;
            workstationFrontierReady = false;
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

    private void handleExploreVoiceAction(LiveViewErgonomics.ParsedVoiceAction parsed, String rawSpoken) {
        final long myTurn = activeTurnId.incrementAndGet();
        stopAudioOnly();
        lastUserSpoken = rawSpoken;
        switch (parsed.action) {
            case FLIP_CAMERA -> {
                if (!cameraOn && !arModeOn) startCamera();
                flipCamera();
                finishSimpleReply(myTurn, useFrontCamera ? "Switched to the front camera." : "Switched to the rear camera.");
            }
            case RECENTER_ZOE -> {
                if (spatialOverlayView != null) spatialOverlayView.recenterInFrontOfUser();
                finishSimpleReply(myTurn, "Right here in front of you.");
            }
            case TOGGLE_ROAM_OFF -> {
                arRoamEnabled = false;
                if (spatialOverlayView != null) spatialOverlayView.setAutonomousRoam(false);
                if (arSurfaceView != null) arSurfaceView.setAutonomousRoam(false);
                styleDrawerButtons();
                finishSimpleReply(myTurn, "Got it, I'll stay right here.");
            }
            case TOGGLE_ROAM_ON -> {
                arRoamEnabled = true;
                if (spatialOverlayView != null) spatialOverlayView.setAutonomousRoam(true);
                if (arSurfaceView != null) arSurfaceView.setAutonomousRoam(true);
                styleDrawerButtons();
                finishSimpleReply(myTurn, "Gliding around your view again.");
            }
            case ENABLE_DEAF_MODE -> {
                selectAccessibilityProfile(ExploreAccessibility.Profile.DEAF_HOH);
            }
            case ENABLE_BLIND_MODE -> {
                selectAccessibilityProfile(ExploreAccessibility.Profile.BLIND_LOW_VISION);
            }
            case ENABLE_KID_MODE -> {
                a11y = a11y.withKidFriendly(true);
                ExploreAccessibility.save(this, a11y);
                applyAccessibilitySettings(true);
            }
            case ENABLE_STANDARD_MODE -> {
                selectAccessibilityProfile(ExploreAccessibility.Profile.STANDARD);
            }
            case ENABLE_FIELD -> {
                if (!spatialFieldOn) toggleSpatialField();
                finishSimpleReply(myTurn, "Spatial telemetry field is on.");
            }
            case DISABLE_FIELD -> {
                stopSpatialTelemetry();
                finishSimpleReply(myTurn, "Spatial telemetry field is off.");
            }
            case DUAL_CAM_SWEEP -> {
                runDualCamAmbientSweep();
                finishSimpleReply(myTurn, "Checking the lighting behind you now.");
            }
            case ECHO_PING -> {
                triggerAcousticEchoPing();
            }
            case ANNOUNCE_ORIENTATION -> {
                announceOrientationSummary();
            }
            case OPEN_GOOGLE_EARTH -> {
                openGoogleEarthOrHint();
            }
            case OPEN_GOOGLE_MAPS_WALK -> {
                finishSimpleReply(myTurn, "Opening walking directions to " + parsed.targetQuery + " in Google Maps.");
                openGoogleMapsWalkingLiveView(parsed.targetQuery);
            }
            case GUIDE_BEARING -> {
                activeGuideBearingDeg = parsed.targetBearingDeg;
                activeGuideLabel = parsed.targetQuery;
                lastGuideWasCentered = false;
                if (!spatialFieldOn) activateSpatialFieldNow();
                if (spatialOverlayView != null) {
                    spatialOverlayView.setGuidanceBearing(activeGuideBearingDeg, activeGuideLabel);
                }
                finishSimpleReply(myTurn, "Guiding you " + activeGuideLabel + ". Follow the floating arrows or feel the tick when locked straight ahead.");
            }
            case CLEAR_GUIDE -> {
                activeGuideBearingDeg = Float.NaN;
                activeGuideLabel = "";
                if (spatialOverlayView != null) spatialOverlayView.clearGuidanceBearing();
                finishSimpleReply(myTurn, "Cleared the direction guide.");
            }
            case OPEN_TOOLS -> {
                setToolsSheetOpen(true);
                finishSimpleReply(myTurn, "Opened Tools and Accessibility.");
            }
            default -> {
            }
        }
    }

    private void finalizeStreamedTurn(long myTurn, String finalReply, boolean streamTtsNow,
                                      int spokenOffset, boolean alreadyStartedSpeaking) {
        if (myTurn != activeTurnId.get()) return;
        String clean = OnDeviceLlmEngine.enforceZoeSovereignty(finalReply);
        if (clean.trim().isEmpty()) clean = "I'm right here with you.";
        // Anti-blindness guard: if compact local model falsely claims "I cannot see" while camera is ON,
        // replace immediately with real grounded camera + color + OCR + compass reading!
        if (LiveViewErgonomics.isBlindOrGenericHallucination(clean, lastUserSpoken, cameraOn || arModeOn)) {
            clean = LiveViewErgonomics.buildGroundedVisualAnswer(
                    latestCameraReport, latestArDistanceMeters,
                    spatialTelemetry != null ? spatialTelemetry.getCompassDegrees() : Float.NaN,
                    a11y.kidFriendly);
            // Force fresh clean reply so the corrected grounded text is spoken/displayed cleanly
            final String corrected = clean;
            runOnUiThread(() -> finishSimpleReply(myTurn, corrected));
            return;
        }
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
        showCaption(LiveSessionLogic.formatLiveCaption(lastUserSpoken, clean), a11y.largeCaptions || arModeOn);
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
        mainHandler.removeCallbacks(speakingWatchdog);
        mainHandler.postDelayed(speakingWatchdog, 11_000L);
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
        mainHandler.removeCallbacks(speakingWatchdog);
        mainHandler.removeCallbacks(thinkingWatchdog);
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
        mainHandler.removeCallbacks(autonomousCuriosityTask);
        clearPendingCuriosityCrop();
        clearFrozenFocusFrame();
        callActive = false;
        hiZoeWakeMode = false;
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        if (arModeOn) {
            stopArSpace();
        }
        activeGuideBearingDeg = Float.NaN;
        activeGuideLabel = "";
        currentPosture = LiveViewErgonomics.Posture.ACTIVE_AR;
        if (spatialOverlayView != null) {
            spatialOverlayView.clearGuidanceBearing();
            spatialOverlayView.setPosture(LiveViewErgonomics.Posture.ACTIVE_AR);
        }
        stopCamera();
        styleDrawerButtons();
        updateKeepScreenOn();
        ExploreAccessibility.pulseHaptic(this, ExploreAccessibility.HapticCue.STOPPED, a11y.hapticCues);
        setOrbState(OrbState.IDLE, "mic & camera off");
        showCaption("Explore paused. Mic, camera, and sensors are off.", true);
    }

    private void setOrbState(OrbState state, String label) {
        currentOrbState = state;
        mainHandler.removeCallbacks(thinkingWatchdog);
        if (state == OrbState.THINKING) {
            mainHandler.postDelayed(thinkingWatchdog, 7_500L);
        }
        orbView.setOrbState(state);
        ZoeArSurfaceView.VisualMood arMood = switch (state) {
            case LISTENING -> ZoeArSurfaceView.VisualMood.LISTENING;
            case THINKING -> ZoeArSurfaceView.VisualMood.THINKING;
            case SPEAKING -> ZoeArSurfaceView.VisualMood.SPEAKING;
            default -> ZoeArSurfaceView.VisualMood.EXPLORING;
        };
        if (arModeOn && !useHeavyArCore6Dof && observationBoxView != null) {
            observationBoxView.setVisualMood(arMood);
            if (state != OrbState.LISTENING) {
                observationBoxView.setVoiceLevel(state == OrbState.SPEAKING ? 0.55f : 0f);
            }
        }
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
        stateBadge.setText(label == null ? "" : label.toLowerCase(Locale.US));
        listenBtn.setText(switch (state) {
            case LISTENING -> "listening…";
            case SPEAKING -> "interrupt";
            case THINKING -> "thinking…";
            default -> (a11y.profile == ExploreAccessibility.Profile.DEAF_HOH && (cameraOn || arModeOn)) ? "look" : "talk";
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
        clearPendingCuriosityCrop();
        clearFrozenFocusFrame();
        callActive = false;
        activeTurnId.incrementAndGet();
        stopAudioOnly();
        if (arModeOn) {
            stopArSpace();
        }
        activeGuideBearingDeg = Float.NaN;
        activeGuideLabel = "";
        currentPosture = LiveViewErgonomics.Posture.ACTIVE_AR;
        if (spatialOverlayView != null) {
            spatialOverlayView.clearGuidanceBearing();
            spatialOverlayView.setPosture(LiveViewErgonomics.Posture.ACTIVE_AR);
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
     * Clean, Simple Interactive Zoe Gem (zero spinning rings, zero per-frame allocations).
     * Shows Zoe herself (her smiling crimson gem) with a calm breathing ambient glow.
     */
    private static final class LiveOrbView extends View {
        private final Bitmap zoeGemBitmap;
        private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint gemBitmapPaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        private final android.graphics.RectF gemDst = new android.graphics.RectF();
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
            zoeGemBitmap = ZoeSpatialOverlayView.renderZoeGemBitmap(context, 320);
            animator = ValueAnimator.ofFloat(0f, 1f);
            animator.setDuration(4200L);
            animator.setRepeatCount(ValueAnimator.INFINITE);
            animator.setInterpolator(new LinearInterpolator());
            animator.addUpdateListener(a -> {
                phase = (float) a.getAnimatedValue();
                float desired = speakingPulse
                        ? (0.35f + 0.25f * (float) Math.abs(Math.sin(phase * Math.PI * 8.0)))
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
            float breathe = (float) Math.sin(phase * Math.PI * 2.0);

            int glowColor = switch (state) {
                case LISTENING -> Color.rgb(88, 228, 182);
                case THINKING -> Color.rgb(252, 206, 112);
                case SPEAKING -> Color.rgb(248, 96, 134);
                default -> Color.rgb(236, 84, 118);
            };

            if (cachedGradColor != glowColor || Math.abs(cachedGradRadius - maxR) > 1f) {
                cachedGradColor = glowColor;
                cachedGradRadius = maxR;
                haloPaint.setShader(new RadialGradient(cx, cy, maxR,
                        new int[]{
                                Color.argb(145, Color.red(glowColor), Color.green(glowColor), Color.blue(glowColor)),
                                Color.argb(52, Color.red(glowColor), Color.green(glowColor), Color.blue(glowColor)),
                                Color.TRANSPARENT},
                        new float[]{0.18f, 0.56f, 1.0f}, Shader.TileMode.CLAMP));
            }
            canvas.drawCircle(cx, cy, maxR * (0.88f + 0.04f * breathe + 0.08f * smoothLevel), haloPaint);

            float bobOffset = breathe * maxR * 0.035f;
            float halfGem = maxR * (0.48f + 0.025f * breathe + 0.08f * smoothLevel);
            gemDst.set(cx - halfGem, cy - halfGem + bobOffset, cx + halfGem, cy + halfGem + bobOffset);
            canvas.drawBitmap(zoeGemBitmap, null, gemDst, gemBitmapPaint);
        }
    }
}
