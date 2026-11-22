package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.view.Choreographer;
import android.view.GestureDetector;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.View;
import android.view.WindowManager;

import java.util.ArrayList;
import java.util.List;

/**
 * Ultra-Light 60/90fps Gyro-Spatial 3D Companion & Accessibility Canvas for Zoe Explore (v0.9.7-beta).
 *
 * Key upgrades & bug fixes:
 *   - Hardware `TYPE_GAME_ROTATION_VECTOR` + real Camera2 hardware vertical FOV projection
 *   - Clean `onSizeChanged` re-centering so Zoe NEVER spawns off-screen before layout completes
 *   - Gentle off-screen leash: when roaming freely, Zoe glides back into your view if you pan away;
 *     when you tap a spot, she glides straight there with a ripple & beacon
 *   - Silent playful roaming by default (no jarring 9-second auto-chatter interrupting your voice!)
 *   - Built-in Deaf / Hard-of-Hearing Visual Ambient Sound Radar ring (zero UI clutter!)
 *   - Built-in Blind / Low-Vision full-screen GestureDetector (Tap = Look, Double-Tap = Talk, Long-Press = Compass/Orientation!)
 *   - Strictly zero per-frame allocations inside `onDraw` and zero CPU when inactive!
 */
final class ZoeSpatialOverlayView extends View implements SensorEventListener, Choreographer.FrameCallback {
    interface Listener {
        void onSpatialHudUpdate(float distanceMeters, String statusHint);
        void onSpatialArrived(ArExploreBrain.Vec3 worldPos, float distanceMeters, float normalizedX, boolean userTapped);
        void onSpatialDoubleTap();
        void onSpatialLongPress();
    }

    private static final int TRAIL_CAPACITY = 14;
    private static final long ROAM_INTERVAL_MS = 10_500L;
    private static final long HUD_THROTTLE_MS = 500L;

    private final SensorManager sensorManager;
    private final Sensor rotationSensor;
    private final Listener listener;
    private final GestureDetector gestureDetector;

    // Sensor fusion 3x3 world rotation matrix (zero-allocation scratch buffers)
    private final float[] rawRotMat = new float[9];
    private final float[] remappedRotMat = new float[9];
    private final float[] activeRotMat = {
            1f, 0f, 0f,
            0f, 1f, 0f,
            0f, 0f, 1f
    };
    private boolean hasOrientation;
    private boolean needsInitialPlacement = true;
    private boolean active;
    private boolean autonomousRoam = true;
    private boolean frontCameraMirrored;
    private boolean visualSoundRadarEnabled;
    private boolean blindGestureMode;
    private LiveViewErgonomics.Posture posture = LiveViewErgonomics.Posture.ACTIVE_AR;
    private float guideTargetBearingDeg = Float.NaN;
    private float currentTrueHeadingDeg = Float.NaN;
    private String guideLabel = "";
    private boolean guideLockedCentered;
    private float verticalFovRad = ArExploreBrain.DEFAULT_SPATIAL_FOV_RAD;
    private float preferredHoverDepthM = 1.22f;
    private float imuStability = 0.88f;
    private SpatialTelemetryFusion.LightFieldState lightField = SpatialTelemetryFusion.LightFieldState.neutral();
    private float spatialCoherence = 0.72f;
    private ZoeArSurfaceView.VisualMood mood = ZoeArSurfaceView.VisualMood.EXPLORING;
    private float targetVoiceLevel;
    private float smoothVoiceLevel;
    private float targetAmbientSoundLevel;
    private float smoothAmbientSoundLevel;

    // 3D world-space companion state
    private ArExploreBrain.Vec3 zoePos = new ArExploreBrain.Vec3(0f, 0.04f, -1.22f);
    private ArExploreBrain.Vec3 zoeTarget = new ArExploreBrain.Vec3(0f, 0.04f, -1.22f);
    private final List<ArExploreBrain.Vec3> discoveryBeacons = new ArrayList<>();
    private final float[] trailX = new float[TRAIL_CAPACITY];
    private final float[] trailY = new float[TRAIL_CAPACITY];
    private int trailHead;
    private int trailCount;

    // Timing & touch state
    private long lastFrameNs;
    private float elapsedSec;
    private float offscreenSec;
    private long lastRoamMs;
    private long lastHudMs;
    private int roamStep;
    private boolean userPinnedTarget;
    private boolean pendingTapInspection;
    private float lastTapNormX;
    private float tapRippleX;
    private float tapRippleY;
    private float tapRippleAge = 99f;

    // Pre-allocated drawing objects (zero per-frame GC churn!)
    private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ringPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint gemPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint facetPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint trailPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint beaconPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint ripplePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint arrowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint radarPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint restPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint chevronPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint guideTextPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path gemPath = new Path();
    private final Path facetPath = new Path();
    private final Path arrowPath = new Path();
    private final Path chevronPath = new Path();
    private final RectF oval = new RectF();
    private int cachedHaloColor = -1;
    private float cachedHaloRadius = -1f;
    private float cachedHaloX = -1f;
    private float cachedHaloY = -1f;

    ZoeSpatialOverlayView(Context context, Listener listener) {
        super(context);
        this.listener = listener;
        this.sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        Sensor gameRot = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR) : null;
        this.rotationSensor = gameRot != null
                ? gameRot
                : (sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR) : null);

        ringPaint.setStyle(Paint.Style.STROKE);
        ringPaint.setStrokeCap(Paint.Cap.ROUND);
        trailPaint.setStyle(Paint.Style.FILL);
        ripplePaint.setStyle(Paint.Style.STROKE);
        arrowPaint.setStyle(Paint.Style.FILL);
        radarPaint.setStyle(Paint.Style.STROKE);
        restPaint.setStyle(Paint.Style.FILL);
        chevronPaint.setStyle(Paint.Style.STROKE);
        chevronPaint.setStrokeCap(Paint.Cap.ROUND);
        chevronPaint.setStrokeJoin(Paint.Join.ROUND);
        guideTextPaint.setColor(Color.WHITE);
        guideTextPaint.setTextAlign(Paint.Align.CENTER);
        setWillNotDraw(false);

        gestureDetector = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public boolean onDown(MotionEvent e) {
                return true;
            }

            @Override
            public boolean onSingleTapConfirmed(MotionEvent e) {
                handleCanvasSingleTap(e.getX(), e.getY());
                return true;
            }

            @Override
            public boolean onDoubleTap(MotionEvent e) {
                if (ZoeSpatialOverlayView.this.listener != null) {
                    ZoeSpatialOverlayView.this.listener.onSpatialDoubleTap();
                }
                return true;
            }

            @Override
            public void onLongPress(MotionEvent e) {
                if (ZoeSpatialOverlayView.this.listener != null) {
                    ZoeSpatialOverlayView.this.listener.onSpatialLongPress();
                }
            }
        });
    }

    void setActive(boolean enabled) {
        if (this.active == enabled) {
            return;
        }
        this.active = enabled;
        if (enabled) {
            hasOrientation = false;
            needsInitialPlacement = true;
            userPinnedTarget = false;
            pendingTapInspection = false;
            trailCount = 0;
            trailHead = 0;
            discoveryBeacons.clear();
            elapsedSec = 0f;
            offscreenSec = 0f;
            lastFrameNs = 0L;
            lastRoamMs = System.currentTimeMillis();
            zoePos = new ArExploreBrain.Vec3(0f, 0.04f, -preferredHoverDepthM);
            zoeTarget = zoePos;
            if (sensorManager != null && rotationSensor != null) {
                sensorManager.registerListener(this, rotationSensor, SensorManager.SENSOR_DELAY_GAME);
            }
            Choreographer.getInstance().removeFrameCallback(this);
            Choreographer.getInstance().postFrameCallback(this);
        } else {
            Choreographer.getInstance().removeFrameCallback(this);
            if (sensorManager != null) {
                sensorManager.unregisterListener(this);
            }
        }
        invalidate();
    }

    void setAutonomousRoam(boolean enabled) {
        this.autonomousRoam = enabled;
    }

    void setFrontCameraMirrored(boolean mirrored) {
        this.frontCameraMirrored = mirrored;
    }

    void setVisualSoundRadarEnabled(boolean enabled) {
        this.visualSoundRadarEnabled = enabled;
    }

    void setBlindGestureMode(boolean enabled) {
        this.blindGestureMode = enabled;
    }

    void setPosture(LiveViewErgonomics.Posture next) {
        this.posture = next == null ? LiveViewErgonomics.Posture.ACTIVE_AR : next;
    }

    void setGuidanceBearing(float targetBearingDeg, String label) {
        this.guideTargetBearingDeg = targetBearingDeg;
        this.guideLabel = label == null ? "" : label;
        this.guideLockedCentered = false;
    }

    void clearGuidanceBearing() {
        this.guideTargetBearingDeg = Float.NaN;
        this.guideLabel = "";
        this.guideLockedCentered = false;
    }

    void updateCurrentTrueHeading(float trueHeadingDeg) {
        this.currentTrueHeadingDeg = trueHeadingDeg;
    }

    boolean isGuidanceBearingLocked() {
        return guideLockedCentered;
    }

    void setVerticalFovRad(float fovRad) {
        if (Float.isFinite(fovRad) && fovRad >= 0.55f && fovRad <= 1.85f) {
            this.verticalFovRad = fovRad;
        }
    }

    void setPreferredHoverDepth(float meters) {
        if (Float.isFinite(meters) && meters >= 0.65f && meters <= 2.4f) {
            this.preferredHoverDepthM = meters;
        }
    }

    void setLightField(SpatialTelemetryFusion.LightFieldState state) {
        this.lightField = state == null ? SpatialTelemetryFusion.LightFieldState.neutral() : state;
    }

    void setSpatialCoherence(float coherence) {
        if (Float.isFinite(coherence)) {
            this.spatialCoherence = Math.max(0.2f, Math.min(1f, coherence));
        }
    }

    float getImuStability() {
        return imuStability;
    }

    void setVisualMood(ZoeArSurfaceView.VisualMood nextMood) {
        this.mood = nextMood == null ? ZoeArSurfaceView.VisualMood.EXPLORING : nextMood;
    }

    void setVoiceLevel(float level) {
        float clamped = Math.max(0f, Math.min(1f, level));
        this.targetVoiceLevel = clamped;
        this.targetAmbientSoundLevel = Math.max(this.targetAmbientSoundLevel * 0.85f, clamped);
    }

    void setAmbientSoundLevel(float level) {
        this.targetAmbientSoundLevel = Math.max(0f, Math.min(1f, level));
    }

    void recenterInFrontOfUser() {
        if (getWidth() <= 1 || getHeight() <= 1) {
            needsInitialPlacement = true;
            return;
        }
        userPinnedTarget = false;
        zoeTarget = ArExploreBrain.unprojectTapToWorld(
                getWidth() * 0.5f, getHeight() * 0.44f,
                getWidth(), getHeight(),
                verticalFovRad, activeRotMat, preferredHoverDepthM);
        lastRoamMs = System.currentTimeMillis();
    }

    ArExploreBrain.Vec3 getCurrentWorldPos() {
        return zoePos;
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        if (active && w > 1 && h > 1 && needsInitialPlacement) {
            placeInCenterNow(w, h);
        }
    }

    private void placeInCenterNow(float w, float h) {
        needsInitialPlacement = false;
        zoePos = ArExploreBrain.unprojectTapToWorld(
                w * 0.5f, h * 0.44f, w, h,
                verticalFovRad, activeRotMat, preferredHoverDepthM);
        zoeTarget = zoePos;
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        setActive(false);
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (!active || event == null || event.values == null) {
            return;
        }
        SensorManager.getRotationMatrixFromVector(rawRotMat, event.values);
        int rot = currentDisplayRotation();
        int axisX = SensorManager.AXIS_X;
        int axisY = SensorManager.AXIS_Y;
        switch (rot) {
            case Surface.ROTATION_90 -> {
                axisX = SensorManager.AXIS_Y;
                axisY = SensorManager.AXIS_MINUS_X;
            }
            case Surface.ROTATION_180 -> {
                axisX = SensorManager.AXIS_MINUS_X;
                axisY = SensorManager.AXIS_MINUS_Y;
            }
            case Surface.ROTATION_270 -> {
                axisX = SensorManager.AXIS_MINUS_Y;
                axisY = SensorManager.AXIS_X;
            }
            default -> {
            }
        }
        SensorManager.remapCoordinateSystem(rawRotMat, axisX, axisY, remappedRotMat);
        float delta = 0f;
        for (int i = 0; i < 9; i++) {
            delta += Math.abs(remappedRotMat[i] - activeRotMat[i]);
        }
        float instStab = Math.max(0f, Math.min(1f, 1f - delta * 2.4f));
        imuStability += (instStab - imuStability) * 0.18f;
        System.arraycopy(remappedRotMat, 0, activeRotMat, 0, 9);
        if (!hasOrientation) {
            hasOrientation = true;
            if (getWidth() > 1 && getHeight() > 1) {
                placeInCenterNow(getWidth(), getHeight());
            } else {
                needsInitialPlacement = true;
            }
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    private void handleCanvasSingleTap(float rawX, float rawY) {
        if (!active || getWidth() <= 1 || getHeight() <= 1) {
            return;
        }
        float tx = frontCameraMirrored ? (getWidth() - rawX) : rawX;
        lastTapNormX = ((rawX / Math.max(1f, (float) getWidth())) * 2f) - 1f;
        zoeTarget = ArExploreBrain.unprojectTapToWorld(
                tx, rawY, getWidth(), getHeight(),
                verticalFovRad, activeRotMat, preferredHoverDepthM);
        if (discoveryBeacons.size() >= 8) {
            discoveryBeacons.remove(0);
        }
        discoveryBeacons.add(zoeTarget);
        tapRippleX = rawX;
        tapRippleY = rawY;
        tapRippleAge = 0f;
        lastRoamMs = System.currentTimeMillis();
        userPinnedTarget = true;
        pendingTapInspection = true;
        performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK);
        performClick();
        // In Blind / Low-Vision mode, fire instant inspection immediately without waiting for flight!
        if (blindGestureMode && listener != null) {
            pendingTapInspection = false;
            float dist = Math.max(0.35f, zoeTarget.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f)));
            listener.onSpatialArrived(zoeTarget, dist, lastTapNormX, true);
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (!active || event == null) {
            return false;
        }
        return gestureDetector.onTouchEvent(event);
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    @Override
    public void doFrame(long frameTimeNanos) {
        if (!active) {
            return;
        }
        float dt = lastFrameNs == 0L ? 0.016f : Math.max(0.001f, Math.min(0.08f, (frameTimeNanos - lastFrameNs) / 1_000_000_000f));
        lastFrameNs = frameTimeNanos;
        elapsedSec += dt;
        tapRippleAge += dt;
        smoothVoiceLevel += (targetVoiceLevel - smoothVoiceLevel) * Math.min(1f, dt * 14f);
        smoothAmbientSoundLevel += (targetAmbientSoundLevel - smoothAmbientSoundLevel) * Math.min(1f, dt * 10f);
        targetAmbientSoundLevel = Math.max(0f, targetAmbientSoundLevel - dt * 0.45f);

        long nowMs = System.currentTimeMillis();
        // Gentle playful roam around the user's current view (strictly silent unless user taps!)
        if (autonomousRoam && !pendingTapInspection && (nowMs - lastRoamMs) > ROAM_INTERVAL_MS) {
            roamStep++;
            userPinnedTarget = false;
            zoeTarget = ArExploreBrain.chooseSpatialRoamWaypoint(activeRotMat, roamStep);
            lastRoamMs = nowMs;
        }

        // Smooth 60/90fps critically-damped 3D spring flight
        zoePos = ArExploreBrain.stepGlide(zoePos, zoeTarget, dt, 3.6f);
        float dist = Math.max(0.35f, zoePos.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f)));

        if (pendingTapInspection && zoePos.distanceTo(zoeTarget) < 0.12f) {
            pendingTapInspection = false;
            if (listener != null) {
                listener.onSpatialArrived(zoePos, dist, lastTapNormX, true);
            }
        }

        if (listener != null && (nowMs - lastHudMs) > HUD_THROTTLE_MS) {
            lastHudMs = nowMs;
            String hud = String.format(java.util.Locale.US, "● AR · %.1fm", dist);
            listener.onSpatialHudUpdate(dist, hud);
        }

        invalidate();
        Choreographer.getInstance().postFrameCallback(this);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        if (!active) {
            return;
        }
        float w = getWidth();
        float h = getHeight();
        if (w <= 1f || h <= 1f) {
            return;
        }
        float d = getResources().getDisplayMetrics().density;

        // 0. Live-View Style Ergonomic Tilt-Down Safety Rest (phone pointed at ground -> calm dim "Eyes Up" veil!)
        if (posture == LiveViewErgonomics.Posture.SAFETY_REST) {
            restPaint.setColor(Color.argb(132, 6, 10, 18));
            canvas.drawRect(0f, 0f, w, h, restPaint);
            guideTextPaint.setTextSize(15f * d);
            guideTextPaint.setColor(Color.argb(220, 210, 232, 255));
            canvas.drawText("Eyes up · Tilt phone up to resume AR", w * 0.5f, h * 0.48f, guideTextPaint);
            return;
        }

        // 0b. Floating Live-View Style Aurora Bearing Chevrons when guiding toward a compass heading!
        if (Float.isFinite(guideTargetBearingDeg) && Float.isFinite(currentTrueHeadingDeg)) {
            float delta = LiveViewErgonomics.signedBearingDeltaDeg(currentTrueHeadingDeg, guideTargetBearingDeg);
            guideLockedCentered = Math.abs(delta) <= 12f;
            float normX = Math.max(-0.82f, Math.min(0.82f, delta / 45f));
            float gx = w * 0.5f + normX * (w * 0.42f);
            float gy = h * 0.27f;
            int chevColor = guideLockedCentered ? Color.rgb(72, 236, 178) : Color.rgb(112, 198, 255);
            chevronPaint.setStrokeWidth(3.2f * d);
            for (int c = 0; c < 3; c++) {
                float pulseWave = (float) Math.sin(elapsedSec * 4.5 - c * 0.85) * 0.35f + 0.65f;
                int a = (int) (pulseWave * 215f);
                chevronPaint.setColor(Color.argb(a, Color.red(chevColor), Color.green(chevColor), Color.blue(chevColor)));
                float sz = (12f + c * 4f) * d;
                float cy = gy - c * 11f * d;
                chevronPath.reset();
                if (guideLockedCentered) {
                    // Forward-pointing upward chevron stack (right on bearing!)
                    chevronPath.moveTo(gx - sz, cy + sz * 0.55f);
                    chevronPath.lineTo(gx, cy - sz * 0.35f);
                    chevronPath.lineTo(gx + sz, cy + sz * 0.55f);
                } else {
                    float dirSign = delta > 0 ? 1f : -1f;
                    float ox = gx + dirSign * c * 10f * d;
                    chevronPath.moveTo(ox - dirSign * sz * 0.4f, gy - sz * 0.7f);
                    chevronPath.lineTo(ox + dirSign * sz * 0.45f, gy);
                    chevronPath.lineTo(ox - dirSign * sz * 0.4f, gy + sz * 0.7f);
                }
                canvas.drawPath(chevronPath, chevronPaint);
            }
            guideTextPaint.setTextSize(12.5f * d);
            guideTextPaint.setColor(chevColor);
            String label = guideLockedCentered
                    ? ("● STRAIGHT AHEAD · " + guideLabel)
                    : String.format(java.util.Locale.US, "%s %s · %.0f°",
                            delta > 0 ? "Turn right →" : "← Turn left", guideLabel, Math.abs(delta));
            canvas.drawText(label, w * 0.5f, gy + 32f * d, guideTextPaint);
        }

        // 0c. Deaf / Hard-of-Hearing Visual Ambient Sound Radar Ring (pure visual cue, zero button clutter!)
        if (visualSoundRadarEnabled && smoothAmbientSoundLevel > 0.08f) {
            float rNorm = Math.min(1f, smoothAmbientSoundLevel);
            int alpha = (int) (rNorm * 145f);
            radarPaint.setStrokeWidth((2.5f + rNorm * 6.0f) * d);
            radarPaint.setColor(rNorm > 0.65f
                    ? Color.argb(alpha, 255, 196, 86)
                    : Color.argb(alpha, 72, 232, 196));
            float inset = (18f - rNorm * 8f) * d;
            oval.set(inset, inset * 3.2f, w - inset, h - inset * 3.6f);
            canvas.drawRoundRect(oval, 34f * d, 34f * d, radarPaint);
        }

        // 1. Subtle world-locked discovery beacons
        for (int i = 0; i < discoveryBeacons.size(); i++) {
            ArExploreBrain.ScreenProjection bp = ArExploreBrain.projectWorldToScreen(
                    discoveryBeacons.get(i), activeRotMat, w, h, verticalFovRad);
            if (!bp.onScreen) {
                continue;
            }
            float bx = frontCameraMirrored ? (w - bp.screenX) : bp.screenX;
            float br = (4.0f * bp.perspectiveScale) * d;
            beaconPaint.setColor(Color.argb(135, 96, 232, 198));
            canvas.drawCircle(bx, bp.screenY, br, beaconPaint);
            ripplePaint.setStrokeWidth(1.3f * d);
            ripplePaint.setColor(Color.argb(80, 120, 220, 255));
            canvas.drawCircle(bx, bp.screenY, br * 2.0f, ripplePaint);
        }

        // 2. Tap summon ripple ring
        if (tapRippleAge < 0.72f) {
            float p = tapRippleAge / 0.72f;
            ripplePaint.setStrokeWidth((2.4f * (1f - p) + 0.8f) * d);
            ripplePaint.setColor(Color.argb((int) ((1f - p) * 200), 120, 224, 255));
            canvas.drawCircle(tapRippleX, tapRippleY, (12f + p * 42f) * d, ripplePaint);
        }

        // 3. Project Zoe's 3D world position + gentle floating bob onto the full-screen camera
        float bobY = (float) Math.sin(elapsedSec * 2.4) * 0.024f;
        ArExploreBrain.Vec3 drawPos = new ArExploreBrain.Vec3(zoePos.x, zoePos.y + bobY, zoePos.z);
        ArExploreBrain.ScreenProjection proj = ArExploreBrain.projectWorldToScreen(
                drawPos, activeRotMat, w, h, verticalFovRad);
        float sx = frontCameraMirrored ? (w - proj.screenX) : proj.screenX;
        float sy = proj.screenY;

        int cCore;
        int cAccent;
        switch (mood) {
            case LISTENING -> {
                cCore = Color.rgb(72, 232, 178);
                cAccent = Color.rgb(92, 196, 255);
            }
            case THINKING -> {
                cCore = Color.rgb(252, 202, 102);
                cAccent = Color.rgb(186, 134, 255);
            }
            case SPEAKING -> {
                cCore = Color.rgb(248, 108, 148);
                cAccent = Color.rgb(122, 186, 255);
            }
            default -> {
                cCore = Color.rgb(106, 176, 255);
                cAccent = Color.rgb(96, 228, 206);
            }
        }

        if (!proj.onScreen) {
            offscreenSec += 0.016f;
            // Gentle leash: if Zoe isn't pinned and has been off-screen > 1.4s, glide smoothly back in front!
            if (!userPinnedTarget && offscreenSec > 1.4f) {
                offscreenSec = 0f;
                recenterInFrontOfUser();
            }
            drawOffscreenPointer(canvas, sx, sy, w, h, d, cCore);
            return;
        }
        offscreenSec = 0f;

        // Update luminous flight trail ring buffer
        trailX[trailHead] = sx;
        trailY[trailHead] = sy;
        trailHead = (trailHead + 1) % TRAIL_CAPACITY;
        if (trailCount < TRAIL_CAPACITY) {
            trailCount++;
        }

        // 4. Draw subtle luminous stardust trail
        for (int i = 0; i < trailCount; i++) {
            int idx = (trailHead - 1 - i + TRAIL_CAPACITY) % TRAIL_CAPACITY;
            float frac = 1f - (i / (float) TRAIL_CAPACITY);
            int alpha = (int) (frac * frac * 88f);
            trailPaint.setColor(Color.argb(alpha, Color.red(cAccent), Color.green(cAccent), Color.blue(cAccent)));
            canvas.drawCircle(trailX[idx], trailY[idx], (1.8f + frac * 5.2f) * proj.perspectiveScale * d, trailPaint);
        }

        float pulse = 1f + 0.055f * (float) Math.sin(elapsedSec * 3.2) + 0.22f * smoothVoiceLevel;
        float baseR = 44f * proj.perspectiveScale * pulse * d;

        // 5. Atmospheric radial aura glow (modulated by Front/Back Light-Field contrast & spatial coherence!)
        float haloR = baseR * (1.68f + 0.26f * lightField.contrastBoost);
        int haloAlphaCore = Math.min(230, (int) (155f * lightField.contrastBoost));
        int haloAlphaMid = Math.min(140, (int) (64f * (0.7f + 0.5f * spatialCoherence)));
        if (cachedHaloColor != cCore
                || Math.abs(cachedHaloRadius - haloR) > 2f
                || Math.abs(cachedHaloX - sx) > 1.5f
                || Math.abs(cachedHaloY - sy) > 1.5f) {
            cachedHaloColor = cCore;
            cachedHaloRadius = haloR;
            cachedHaloX = sx;
            cachedHaloY = sy;
            haloPaint.setShader(new RadialGradient(
                    sx, sy, Math.max(4f, cachedHaloRadius),
                    new int[]{
                            Color.argb(haloAlphaCore, Color.red(cCore), Color.green(cCore), Color.blue(cCore)),
                            Color.argb(haloAlphaMid, Color.red(cAccent), Color.green(cAccent), Color.blue(cAccent)),
                            Color.TRANSPARENT},
                    new float[]{0.12f, 0.52f, 1f}, Shader.TileMode.CLAMP));
        }
        canvas.drawCircle(sx, sy, cachedHaloRadius, haloPaint);

        // 6. Dual 3D counter-rotating orbital halo rings
        float deg = elapsedSec * (44f + 20f * spatialCoherence);
        ringPaint.setStrokeWidth((2.1f + smoothVoiceLevel * 1.4f) * d);
        ringPaint.setColor(Color.argb(180, Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
        canvas.save();
        canvas.rotate(deg, sx, sy);
        oval.set(sx - baseR * 1.12f, sy - baseR * 0.42f, sx + baseR * 1.12f, sy + baseR * 0.42f);
        canvas.drawOval(oval, ringPaint);
        canvas.restore();

        ringPaint.setStrokeWidth(1.5f * d);
        ringPaint.setColor(Color.argb(145, Color.red(cAccent), Color.green(cAccent), Color.blue(cAccent)));
        canvas.save();
        canvas.rotate(-deg * 0.72f + 54f, sx, sy);
        oval.set(sx - baseR * 1.28f, sy - baseR * 0.54f, sx + baseR * 1.28f, sy + baseR * 0.54f);
        canvas.drawOval(oval, ringPaint);
        canvas.restore();

        // 7. Faceted 3D luminous Zoe GEM prism core with Dual-Camera Backlight Rim Reflection
        float gH = baseR * 0.60f;
        float gW = baseR * 0.46f;
        float shimmer = (float) Math.sin(elapsedSec * 2.1) * gW * 0.14f;
        gemPath.reset();
        gemPath.moveTo(sx, sy - gH);
        gemPath.lineTo(sx + gW, sy);
        gemPath.lineTo(sx, sy + gH);
        gemPath.lineTo(sx - gW, sy);
        gemPath.close();
        gemPaint.setColor(Color.argb(232, Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
        canvas.drawPath(gemPath, gemPaint);

        int rimR = lightField.frontWarmth >= 0f ? 255 : (int) (255 + lightField.frontWarmth * 40f);
        int rimG = 248;
        int rimB = lightField.frontWarmth <= 0f ? 255 : (int) (255 - lightField.frontWarmth * 55f);
        int rimAlpha = Math.max(95, Math.min(230, (int) (95f + 135f * lightField.rimIntensity)));
        facetPath.reset();
        facetPath.moveTo(sx, sy - gH);
        facetPath.lineTo(sx + gW, sy);
        facetPath.lineTo(sx + shimmer, sy - gH * 0.06f);
        facetPath.lineTo(sx - gW, sy);
        facetPath.close();
        facetPaint.setColor(Color.argb(rimAlpha, rimR, rimG, rimB));
        canvas.drawPath(facetPath, facetPaint);

        if (lightField.calibrated && lightField.rimIntensity > 0.35f) {
            ringPaint.setStrokeWidth((1.2f + lightField.rimIntensity * 1.4f) * d);
            ringPaint.setColor(Color.argb((int) (lightField.rimIntensity * 195f), rimR, rimG, rimB));
            canvas.drawPath(gemPath, ringPaint);
        }
    }

    private void drawOffscreenPointer(Canvas canvas, float sx, float sy, float w, float h, float d, int color) {
        float cx = w * 0.5f;
        float cy = h * 0.5f;
        float ang = (float) Math.atan2(sy - cy, sx - cx);
        float margin = 34f * d;
        float rx = Math.max(24f, w * 0.5f - margin);
        float ry = Math.max(24f, h * 0.5f - margin * 3.0f);
        float ex = cx + (float) Math.cos(ang) * rx;
        float ey = cy + (float) Math.sin(ang) * ry;

        canvas.save();
        canvas.translate(ex, ey);
        canvas.rotate((float) Math.toDegrees(ang));
        float sz = 11f * d;
        arrowPath.reset();
        arrowPath.moveTo(sz, 0f);
        arrowPath.lineTo(-sz * 0.7f, -sz * 0.68f);
        arrowPath.lineTo(-sz * 0.35f, 0f);
        arrowPath.lineTo(-sz * 0.7f, sz * 0.68f);
        arrowPath.close();
        arrowPaint.setColor(Color.argb(215, Color.red(color), Color.green(color), Color.blue(color)));
        canvas.drawPath(arrowPath, arrowPaint);
        canvas.restore();
    }

    private int currentDisplayRotation() {
        WindowManager wm = (WindowManager) getContext().getSystemService(Context.WINDOW_SERVICE);
        if (wm != null && wm.getDefaultDisplay() != null) {
            return wm.getDefaultDisplay().getRotation();
        }
        return Surface.ROTATION_0;
    }
}
