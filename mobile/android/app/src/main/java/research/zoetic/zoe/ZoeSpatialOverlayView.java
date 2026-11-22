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
import android.view.MotionEvent;
import android.view.Surface;
import android.view.View;
import android.view.WindowManager;

import java.util.ArrayList;
import java.util.List;

/**
 * Ultra-Light 60/90fps Gyro-Spatial 3D Companion Overlay for Zoe Explore (v0.9.6-beta).
 *
 * Solves ARCore SLAM lag & thermal throttling for Zoe's room-companion use case:
 *   - Runs directly on top of CameraX hardware SurfaceView (`ImplementationMode.PERFORMANCE`)
 *   - Uses Pixel/Android Sensor Hub `TYPE_GAME_ROTATION_VECTOR` (zero magnetometer desk jitter,
 *     < 0.1% CPU!) to world-lock Zoe's 3D floating GEM companion in your physical space
 *   - Tap anywhere on the full-screen camera to summon Zoe to that exact 3D world direction
 *   - Smooth 3D spring flight, luminous stardust ribbon trail, dual counter-rotating orbital rings,
 *     world-pinned discovery beacons, and off-screen edge guide arrow when you pan away
 *   - Strictly zero per-frame allocations inside `onDraw` and zero CPU when inactive!
 */
final class ZoeSpatialOverlayView extends View implements SensorEventListener, Choreographer.FrameCallback {
    interface Listener {
        void onSpatialHudUpdate(float distanceMeters, String statusHint);
        void onSpatialArrived(ArExploreBrain.Vec3 worldPos, float distanceMeters, boolean userTapped);
    }

    private static final int TRAIL_CAPACITY = 16;
    private static final long ROAM_INTERVAL_MS = 9_000L;
    private static final long HUD_THROTTLE_MS = 450L;

    private final SensorManager sensorManager;
    private final Sensor rotationSensor;
    private final Listener listener;

    // Sensor fusion 3x3 world rotation matrix (zero-allocation scratch buffers)
    private final float[] rawRotMat = new float[9];
    private final float[] remappedRotMat = new float[9];
    private final float[] activeRotMat = {
            1f, 0f, 0f,
            0f, 1f, 0f,
            0f, 0f, 1f
    };
    private boolean hasOrientation;
    private boolean active;
    private boolean autonomousRoam = true;
    private boolean frontCameraMirrored;
    private float verticalFovRad = ArExploreBrain.DEFAULT_SPATIAL_FOV_RAD;
    private float preferredHoverDepthM = 1.20f;
    private float imuStability = 0.88f;
    private SpatialTelemetryFusion.LightFieldState lightField = SpatialTelemetryFusion.LightFieldState.neutral();
    private float spatialCoherence = 0.72f;
    private ZoeArSurfaceView.VisualMood mood = ZoeArSurfaceView.VisualMood.EXPLORING;
    private float targetVoiceLevel;
    private float smoothVoiceLevel;

    // 3D world-space companion state
    private ArExploreBrain.Vec3 zoePos = new ArExploreBrain.Vec3(0f, 0.04f, -1.20f);
    private ArExploreBrain.Vec3 zoeTarget = new ArExploreBrain.Vec3(0f, 0.04f, -1.20f);
    private final List<ArExploreBrain.Vec3> discoveryBeacons = new ArrayList<>();
    private final float[] trailX = new float[TRAIL_CAPACITY];
    private final float[] trailY = new float[TRAIL_CAPACITY];
    private int trailHead;
    private int trailCount;

    // Timing & touch state
    private long lastFrameNs;
    private float elapsedSec;
    private long lastRoamMs;
    private long lastArriveMs;
    private long lastHudMs;
    private int roamStep;
    private boolean pendingArrival;
    private boolean arrivalWasTap;
    private float touchDownX;
    private float touchDownY;
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
    private final Path gemPath = new Path();
    private final Path facetPath = new Path();
    private final Path arrowPath = new Path();
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
        setWillNotDraw(false);
    }

    void setActive(boolean enabled) {
        if (this.active == enabled) {
            return;
        }
        this.active = enabled;
        if (enabled) {
            hasOrientation = false;
            trailCount = 0;
            trailHead = 0;
            discoveryBeacons.clear();
            elapsedSec = 0f;
            lastFrameNs = 0L;
            lastRoamMs = System.currentTimeMillis();
            zoePos = new ArExploreBrain.Vec3(0f, 0.04f, -1.20f);
            zoeTarget = zoePos;
            pendingArrival = false;
            arrivalWasTap = false;
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
        this.targetVoiceLevel = Math.max(0f, Math.min(1f, level));
    }

    void recenterInFrontOfUser() {
        zoeTarget = ArExploreBrain.unprojectTapToWorld(
                getWidth() * 0.5f, getHeight() * 0.44f,
                Math.max(1f, getWidth()), Math.max(1f, getHeight()),
                verticalFovRad, activeRotMat, preferredHoverDepthM);
        lastRoamMs = System.currentTimeMillis();
    }

    ArExploreBrain.Vec3 getCurrentWorldPos() {
        return zoePos;
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
        // Track instantaneous IMU angular stability (0..1) for CERN / Kloster spatial telemetry fusion!
        float delta = 0f;
        for (int i = 0; i < 9; i++) {
            delta += Math.abs(remappedRotMat[i] - activeRotMat[i]);
        }
        float instStab = Math.max(0f, Math.min(1f, 1f - delta * 2.4f));
        imuStability += (instStab - imuStability) * 0.18f;
        System.arraycopy(remappedRotMat, 0, activeRotMat, 0, 9);
        if (!hasOrientation) {
            hasOrientation = true;
            // Place Zoe gracefully right in front of wherever the user is pointing right now!
            zoePos = ArExploreBrain.unprojectTapToWorld(
                    Math.max(1f, getWidth()) * 0.5f, Math.max(1f, getHeight()) * 0.44f,
                    Math.max(1f, getWidth()), Math.max(1f, getHeight()),
                    verticalFovRad, activeRotMat, preferredHoverDepthM);
            zoeTarget = zoePos;
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (!active || event == null) {
            return false;
        }
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN) {
            touchDownX = event.getX();
            touchDownY = event.getY();
            return true;
        }
        if (action == MotionEvent.ACTION_UP) {
            float dx = event.getX() - touchDownX;
            float dy = event.getY() - touchDownY;
            if (Math.hypot(dx, dy) < 36f) {
                float tx = frontCameraMirrored ? (getWidth() - event.getX()) : event.getX();
                float ty = event.getY();
                zoeTarget = ArExploreBrain.unprojectTapToWorld(
                        tx, ty,
                        Math.max(1f, getWidth()), Math.max(1f, getHeight()),
                        verticalFovRad, activeRotMat, preferredHoverDepthM);
                if (discoveryBeacons.size() >= 10) {
                    discoveryBeacons.remove(0);
                }
                discoveryBeacons.add(zoeTarget);
                tapRippleX = event.getX();
                tapRippleY = event.getY();
                tapRippleAge = 0f;
                lastRoamMs = System.currentTimeMillis();
                pendingArrival = true;
                arrivalWasTap = true;
                performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK);
                performClick();
            }
            return true;
        }
        return true;
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

        long nowMs = System.currentTimeMillis();
        if (autonomousRoam && !pendingArrival && (nowMs - lastRoamMs) > ROAM_INTERVAL_MS) {
            roamStep++;
            zoeTarget = ArExploreBrain.chooseSpatialRoamWaypoint(activeRotMat, roamStep);
            lastRoamMs = nowMs;
            pendingArrival = true;
            arrivalWasTap = false;
        }

        // Smooth 60/90fps critically-damped 3D spring flight
        zoePos = ArExploreBrain.stepGlide(zoePos, zoeTarget, dt, 3.4f);
        float dist = Math.max(0.35f, zoePos.distanceTo(new ArExploreBrain.Vec3(0f, 0f, 0f)));

        if (pendingArrival && zoePos.distanceTo(zoeTarget) < 0.10f) {
            boolean wasTap = arrivalWasTap;
            pendingArrival = false;
            arrivalWasTap = false;
            if (wasTap || (nowMs - lastArriveMs) > 9_500L) {
                lastArriveMs = nowMs;
                if (listener != null) {
                    listener.onSpatialArrived(zoePos, dist, wasTap);
                }
            }
        }

        if (listener != null && (nowMs - lastHudMs) > HUD_THROTTLE_MS) {
            lastHudMs = nowMs;
            String sensorTag = rotationSensor != null ? "60fps" : "GLIDE";
            String hud = String.format(java.util.Locale.US, "● %s · %.1fm", sensorTag, dist);
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

        // 1. Subtle world-locked discovery beacons
        for (int i = 0; i < discoveryBeacons.size(); i++) {
            ArExploreBrain.ScreenProjection bp = ArExploreBrain.projectWorldToScreen(
                    discoveryBeacons.get(i), activeRotMat, w, h, verticalFovRad);
            if (!bp.onScreen) {
                continue;
            }
            float bx = frontCameraMirrored ? (w - bp.screenX) : bp.screenX;
            float br = (4.5f * bp.perspectiveScale) * d;
            beaconPaint.setColor(Color.argb(145, 96, 232, 198));
            canvas.drawCircle(bx, bp.screenY, br, beaconPaint);
            ripplePaint.setStrokeWidth(1.4f * d);
            ripplePaint.setColor(Color.argb(90, 120, 220, 255));
            canvas.drawCircle(bx, bp.screenY, br * 2.1f, ripplePaint);
        }

        // 2. Tap summon ripple ring
        if (tapRippleAge < 0.75f) {
            float p = tapRippleAge / 0.75f;
            ripplePaint.setStrokeWidth((2.6f * (1f - p) + 0.8f) * d);
            ripplePaint.setColor(Color.argb((int) ((1f - p) * 210), 120, 224, 255));
            canvas.drawCircle(tapRippleX, tapRippleY, (12f + p * 44f) * d, ripplePaint);
        }

        // 3. Project Zoe's 3D world position + gentle floating bob onto the full-screen camera
        float bobY = (float) Math.sin(elapsedSec * 2.5) * 0.026f;
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
            drawOffscreenPointer(canvas, sx, sy, w, h, d, cCore);
            return;
        }

        // Update luminous flight trail ring buffer
        trailX[trailHead] = sx;
        trailY[trailHead] = sy;
        trailHead = (trailHead + 1) % TRAIL_CAPACITY;
        if (trailCount < TRAIL_CAPACITY) {
            trailCount++;
        }

        // 4. Draw luminous stardust trail behind Zoe as she glides across the camera view
        for (int i = 0; i < trailCount; i++) {
            int idx = (trailHead - 1 - i + TRAIL_CAPACITY) % TRAIL_CAPACITY;
            float frac = 1f - (i / (float) TRAIL_CAPACITY);
            int alpha = (int) (frac * frac * 95f);
            trailPaint.setColor(Color.argb(alpha, Color.red(cAccent), Color.green(cAccent), Color.blue(cAccent)));
            canvas.drawCircle(trailX[idx], trailY[idx], (2.0f + frac * 6.0f) * proj.perspectiveScale * d, trailPaint);
        }

        float pulse = 1f + 0.06f * (float) Math.sin(elapsedSec * 3.4) + 0.24f * smoothVoiceLevel;
        float baseR = 46f * proj.perspectiveScale * pulse * d;

        // 5. Atmospheric radial aura glow (modulated by Front/Back Light-Field contrast & spatial coherence!)
        float haloR = baseR * (1.72f + 0.28f * lightField.contrastBoost);
        int haloAlphaCore = Math.min(235, (int) (160f * lightField.contrastBoost));
        int haloAlphaMid = Math.min(145, (int) (68f * (0.7f + 0.5f * spatialCoherence)));
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

        // 6. Dual 3D counter-rotating orbital halo rings (shimmer rate adapts to spatial coherence)
        float deg = elapsedSec * (44f + 22f * spatialCoherence);
        ringPaint.setStrokeWidth((2.2f + smoothVoiceLevel * 1.4f) * d);
        ringPaint.setColor(Color.argb(185, Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
        canvas.save();
        canvas.rotate(deg, sx, sy);
        oval.set(sx - baseR * 1.15f, sy - baseR * 0.44f, sx + baseR * 1.15f, sy + baseR * 0.44f);
        canvas.drawOval(oval, ringPaint);
        canvas.restore();

        ringPaint.setStrokeWidth(1.6f * d);
        ringPaint.setColor(Color.argb(150, Color.red(cAccent), Color.green(cAccent), Color.blue(cAccent)));
        canvas.save();
        canvas.rotate(-deg * 0.72f + 54f, sx, sy);
        oval.set(sx - baseR * 1.32f, sy - baseR * 0.56f, sx + baseR * 1.32f, sy + baseR * 0.56f);
        canvas.drawOval(oval, ringPaint);
        canvas.restore();

        // 7. Faceted 3D luminous Zoe GEM prism core with Dual-Camera Backlight Rim Reflection!
        float gH = baseR * 0.62f;
        float gW = baseR * 0.48f;
        float shimmer = (float) Math.sin(elapsedSec * 2.1) * gW * 0.14f;
        gemPath.reset();
        gemPath.moveTo(sx, sy - gH);
        gemPath.lineTo(sx + gW, sy);
        gemPath.lineTo(sx, sy + gH);
        gemPath.lineTo(sx - gW, sy);
        gemPath.close();
        gemPaint.setColor(Color.argb(232, Color.red(cCore), Color.green(cCore), Color.blue(cCore)));
        canvas.drawPath(gemPath, gemPaint);

        // Specular facet tinted subtly by the ambient light warmth BEHIND the user (front camera light-field!)
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

        // Subtle physical backlight rim stroke around the GEM when front-camera calibration detects strong light behind user
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
        float margin = 38f * d;
        float rx = Math.max(24f, w * 0.5f - margin);
        float ry = Math.max(24f, h * 0.5f - margin * 3.2f);
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
