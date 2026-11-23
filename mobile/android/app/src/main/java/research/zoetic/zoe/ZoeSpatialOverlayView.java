package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.drawable.Drawable;
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

import androidx.core.content.ContextCompat;

/**
 * Clean, Calm 60/90fps Spatial AR Companion for Zoe Explore.
 *
 * Renders Zoe herself (her smiling faceted crimson gem, with zero spinning rings or visual clutter)
 * floating smoothly in 3D camera space:
 *   - Autonomous curiosity navigation: glides to visually intriguing objects in the camera frame
 *     and notifies ZoeLiveActivity on arrival so SHE asks YOU "What's this?"
 *   - Direct interaction: tap Zoe herself to talk/interrupt, or tap any object in view to show her
 *   - Full accessibility preserved: Deaf/HoH visual Sound Radar, Blind/Low-Vision full-screen
 *     gestures (Tap = Look, Double-Tap = Talk, Long-Press = Orientation), Tilt-Down Safety Rest,
 *     and Compass Bearing Chevrons
 *   - Strictly zero per-frame allocations inside `onDraw` and zero CPU when inactive
 */
final class ZoeSpatialOverlayView extends View implements SensorEventListener, Choreographer.FrameCallback {
    interface Listener {
        void onSpatialHudUpdate(float distanceMeters, String statusHint);
        void onSpatialArrived(ArExploreBrain.Vec3 worldPos, float distanceMeters,
                              float tapU, float tapV, boolean userTapped);
        void onZoeGemTapped();
        void onSpatialDoubleTap();
        void onSpatialLongPress();
    }

    private static final long HUD_THROTTLE_MS = 650L;

    private final SensorManager sensorManager;
    private final Sensor rotationSensor;
    private final Listener listener;
    private final GestureDetector gestureDetector;
    private final Bitmap zoeGemBitmap;

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
    private float preferredHoverDepthM = 1.18f;
    private float imuStability = 0.88f;
    private SpatialTelemetryFusion.LightFieldState lightField = SpatialTelemetryFusion.LightFieldState.neutral();
    private float spatialCoherence = 0.72f;
    private ZoeArSurfaceView.VisualMood mood = ZoeArSurfaceView.VisualMood.EXPLORING;
    private float targetVoiceLevel;
    private float smoothVoiceLevel;
    private float targetAmbientSoundLevel;
    private float smoothAmbientSoundLevel;

    // 3D world-space companion state
    private ArExploreBrain.Vec3 zoePos = new ArExploreBrain.Vec3(0f, 0.04f, -1.18f);
    private ArExploreBrain.Vec3 zoeTarget = new ArExploreBrain.Vec3(0f, 0.04f, -1.18f);
    private float lastScreenX = -1000f;
    private float lastScreenY = -1000f;
    private float prevScreenX = -1000f;
    private float smoothLeanDeg;
    private boolean zoeCurrentlyOnScreen;

    // Timing, autonomous arrival & focus ripple state
    private long lastFrameNs;
    private float elapsedSec;
    private float offscreenSec;
    private long lastHudMs;
    private boolean userPinnedTarget;
    private boolean pendingAutoInspection;
    private float autoFlightElapsedSec;
    private float autoSpotU = 0.5f;
    private float autoSpotV = 0.45f;
    private float focusRippleX;
    private float focusRippleY;
    private float focusRippleAge = 99f;

    // Pre-allocated drawing objects (zero per-frame GC churn!)
    private final Paint haloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint gemBitmapPaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final Paint ripplePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint arrowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint radarPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint restPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint chevronPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint guideTextPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path arrowPath = new Path();
    private final Path chevronPath = new Path();
    private final RectF oval = new RectF();
    private final RectF gemDstRect = new RectF();
    private int cachedHaloColor = -1;
    private float cachedHaloRadius = -1f;
    private float cachedHaloX = -1f;
    private float cachedHaloY = -1f;

    ZoeSpatialOverlayView(Context context, Listener listener) {
        super(context);
        this.listener = listener;
        this.zoeGemBitmap = renderZoeGemBitmap(context, 256);
        this.sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        Sensor gameRot = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_GAME_ROTATION_VECTOR) : null;
        this.rotationSensor = gameRot != null
                ? gameRot
                : (sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR) : null);

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

    /** Rasterizes Zoe's crisp smiling crimson gem vector drawable once for zero-allocation 60/90fps drawing. */
    static Bitmap renderZoeGemBitmap(Context context, int sizePx) {
        int s = Math.max(64, sizePx);
        Bitmap bmp = Bitmap.createBitmap(s, s, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);
        Drawable drawable = ContextCompat.getDrawable(context, R.drawable.zoe_emblem);
        if (drawable != null) {
            drawable.setBounds(0, 0, s, s);
            drawable.draw(c);
        }
        return bmp;
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
            pendingAutoInspection = false;
            autoFlightElapsedSec = 0f;
            elapsedSec = 0f;
            offscreenSec = 0f;
            smoothLeanDeg = 0f;
            lastFrameNs = 0L;
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
        if (!enabled) {
            pendingAutoInspection = false;
        }
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
        pendingAutoInspection = false;
        zoeTarget = ArExploreBrain.unprojectTapToWorld(
                getWidth() * 0.5f, getHeight() * 0.44f,
                getWidth(), getHeight(),
                verticalFovRad, activeRotMat, preferredHoverDepthM);
    }

    /**
     * Autonomous AR navigation: glides Zoe smoothly in 3D space over to a visually interesting spot
     * in the live camera view, and triggers arrival inspection so she can ask the user "What's this?"
     */
    void glideToAutonomousSpot(float screenU, float screenV, float distanceMeters) {
        if (!active || getWidth() <= 1 || getHeight() <= 1) {
            return;
        }
        float clampedU = Math.max(0.18f, Math.min(0.82f, screenU));
        float clampedV = Math.max(0.22f, Math.min(0.70f, screenV));
        float rawX = clampedU * getWidth();
        float rawY = clampedV * getHeight();
        float tx = frontCameraMirrored ? (getWidth() - rawX) : rawX;
        float dist = Math.max(0.85f, Math.min(1.65f, distanceMeters));

        zoeTarget = ArExploreBrain.unprojectTapToWorld(
                tx, rawY, getWidth(), getHeight(),
                verticalFovRad, activeRotMat, dist);
        autoSpotU = clampedU;
        autoSpotV = clampedV;
        userPinnedTarget = false;
        pendingAutoInspection = true;
        autoFlightElapsedSec = 0f;
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
        float d = getResources().getDisplayMetrics().density;
        float hitRadius = 56f * d;
        // Tapping directly on Zoe herself talks / interrupts cleanly (except in Blind mode where any tap describes ahead)
        if (!blindGestureMode && zoeCurrentlyOnScreen
                && Math.hypot(rawX - lastScreenX, rawY - lastScreenY) <= hitRadius) {
            performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK);
            performClick();
            if (listener != null) {
                listener.onZoeGemTapped();
            }
            return;
        }

        float tx = frontCameraMirrored ? (getWidth() - rawX) : rawX;
        float tapU = Math.max(0.05f, Math.min(0.95f, rawX / Math.max(1f, (float) getWidth())));
        float tapV = Math.max(0.05f, Math.min(0.95f, rawY / Math.max(1f, (float) getHeight())));
        zoeTarget = ArExploreBrain.unprojectTapToWorld(
                tx, rawY, getWidth(), getHeight(),
                verticalFovRad, activeRotMat, preferredHoverDepthM);
        focusRippleX = rawX;
        focusRippleY = rawY;
        focusRippleAge = 0f;
        userPinnedTarget = true;
        pendingAutoInspection = false;
        performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK);
        performClick();
        if (listener != null) {
            float dist = Math.max(0.35f, zoeTarget.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f)));
            listener.onSpatialArrived(zoeTarget, dist, tapU, tapV, true);
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
        focusRippleAge += dt;
        smoothVoiceLevel += (targetVoiceLevel - smoothVoiceLevel) * Math.min(1f, dt * 14f);
        smoothAmbientSoundLevel += (targetAmbientSoundLevel - smoothAmbientSoundLevel) * Math.min(1f, dt * 10f);
        targetAmbientSoundLevel = Math.max(0f, targetAmbientSoundLevel - dt * 0.45f);

        // Smooth 60/90fps critically-damped 3D spring flight
        zoePos = ArExploreBrain.stepGlide(zoePos, zoeTarget, dt, 3.4f);
        float dist = Math.max(0.35f, zoePos.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f)));

        if (pendingAutoInspection) {
            autoFlightElapsedSec += dt;
            if (zoePos.distanceTo(zoeTarget) < 0.14f || autoFlightElapsedSec > 0.95f) {
                pendingAutoInspection = false;
                if (getWidth() > 1 && getHeight() > 1) {
                    focusRippleX = autoSpotU * getWidth();
                    focusRippleY = autoSpotV * getHeight();
                    focusRippleAge = 0f;
                }
                if (listener != null) {
                    listener.onSpatialArrived(zoePos, dist, autoSpotU, autoSpotV, false);
                }
            }
        }

        long nowMs = System.currentTimeMillis();
        if (listener != null && (nowMs - lastHudMs) > HUD_THROTTLE_MS) {
            lastHudMs = nowMs;
            listener.onSpatialHudUpdate(dist, "● zoe explore");
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

        // 0. Ergonomic Tilt-Down Safety Rest (phone pointed at ground -> calm dim "Eyes Up" veil)
        if (posture == LiveViewErgonomics.Posture.SAFETY_REST) {
            restPaint.setColor(Color.argb(132, 6, 10, 18));
            canvas.drawRect(0f, 0f, w, h, restPaint);
            guideTextPaint.setTextSize(15f * d);
            guideTextPaint.setColor(Color.argb(220, 210, 232, 255));
            canvas.drawText("Eyes up · Tilt phone up to resume", w * 0.5f, h * 0.48f, guideTextPaint);
            return;
        }

        // 0b. Compass Bearing Chevrons (when user asks Zoe to guide toward a heading)
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

        // 0c. Deaf / Hard-of-Hearing Visual Ambient Sound Radar border pulse
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

        // 1. One gentle, brief focus ripple when Zoe lands on an object or user taps a spot
        if (focusRippleAge < 0.85f) {
            float p = focusRippleAge / 0.85f;
            ripplePaint.setStrokeWidth((2.2f * (1f - p) + 0.8f) * d);
            ripplePaint.setColor(Color.argb((int) ((1f - p) * 190), 255, 186, 200));
            canvas.drawCircle(focusRippleX, focusRippleY, (14f + p * 40f) * d, ripplePaint);
        }

        // 2. Project Zoe's 3D world position + gentle calm hover bob onto live camera
        float bobY = (float) Math.sin(elapsedSec * 2.2) * 0.022f;
        ArExploreBrain.ScreenProjection proj = ArExploreBrain.projectWorldToScreen(
                zoePos.x, zoePos.y + bobY, zoePos.z, activeRotMat, w, h, verticalFovRad);
        float sx = frontCameraMirrored ? (w - proj.screenX) : proj.screenX;
        float sy = proj.screenY;

        int glowColor;
        switch (mood) {
            case LISTENING -> glowColor = Color.rgb(92, 232, 186);
            case THINKING -> glowColor = Color.rgb(252, 206, 112);
            case SPEAKING -> glowColor = Color.rgb(248, 96, 134);
            default -> glowColor = Color.rgb(238, 86, 122);
        }

        if (!proj.onScreen) {
            zoeCurrentlyOnScreen = false;
            offscreenSec += 0.016f;
            if (!userPinnedTarget && offscreenSec > 1.2f) {
                offscreenSec = 0f;
                recenterInFrontOfUser();
            }
            drawOffscreenPointer(canvas, sx, sy, w, h, d, glowColor);
            return;
        }
        zoeCurrentlyOnScreen = true;
        offscreenSec = 0f;

        // Playful subtle velocity tilt as Zoe glides left/right toward something interesting
        float vx = prevScreenX > -500f ? (sx - prevScreenX) : 0f;
        prevScreenX = sx;
        lastScreenX = sx;
        lastScreenY = sy;
        float targetLean = Math.max(-9f, Math.min(9f, vx * 0.42f));
        smoothLeanDeg += (targetLean - smoothLeanDeg) * 0.16f;

        float breathe = 1f + 0.035f * (float) Math.sin(elapsedSec * 2.8) + 0.16f * smoothVoiceLevel;
        float gemHalfSize = 44f * proj.perspectiveScale * breathe * d;

        // 3. Soft calm ambient glow behind Zoe (ZERO spinning rings!)
        float haloR = gemHalfSize * (1.72f + 0.18f * lightField.contrastBoost);
        int haloAlphaCore = Math.min(185, (int) ((115f + 55f * smoothVoiceLevel) * lightField.contrastBoost));
        if (cachedHaloColor != glowColor
                || Math.abs(cachedHaloRadius - haloR) > 2f
                || Math.abs(cachedHaloX - sx) > 1.5f
                || Math.abs(cachedHaloY - sy) > 1.5f) {
            cachedHaloColor = glowColor;
            cachedHaloRadius = haloR;
            cachedHaloX = sx;
            cachedHaloY = sy;
            haloPaint.setShader(new RadialGradient(
                    sx, sy, Math.max(4f, cachedHaloRadius),
                    new int[]{
                            Color.argb(haloAlphaCore, Color.red(glowColor), Color.green(glowColor), Color.blue(glowColor)),
                            Color.argb(haloAlphaCore / 3, Color.red(glowColor), Color.green(glowColor), Color.blue(glowColor)),
                            Color.TRANSPARENT},
                    new float[]{0.18f, 0.56f, 1f}, Shader.TileMode.CLAMP));
        }
        canvas.drawCircle(sx, sy, cachedHaloRadius, haloPaint);

        // 4. Draw ZOE HERSELF — her exact faceted smiling crimson gem!
        canvas.save();
        canvas.rotate(smoothLeanDeg, sx, sy);
        gemDstRect.set(sx - gemHalfSize, sy - gemHalfSize, sx + gemHalfSize, sy + gemHalfSize);
        canvas.drawBitmap(zoeGemBitmap, null, gemDstRect, gemBitmapPaint);
        canvas.restore();
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
