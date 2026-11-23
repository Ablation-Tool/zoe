package research.zoetic.zoe;

import android.animation.ValueAnimator;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.view.GestureDetector;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;
import android.view.animation.LinearInterpolator;

/**
 * Temporary Bounding Box AR Sandbox ("Tunnel Vision") for Zoe Explore.
 *
 * Grounded in axis-oriented bounding volumes (broad-phase outer envelope + tight inner
 * containment box) and inclusive accessibility:
 *   - Runs over a frozen still frame so users never have to hold their phone up steady
 *   - Everything outside the Temporary Bounding Box is calmly dimmed and completely static (zero AR)
 *   - ONLY the interior of the Temporary Bounding Box is Augmented Reality:
 *       * Outer dashed 3D bounding volume + inner crisp 3D containment box + subtle x/y/z triad
 *       * Zoe's smiling crimson gem enters INSIDE the box, gliding gently toward an open corner
 *         beside the framed subject (strictly clamped inside the bounding walls!)
 *       * Lightweight local AR micro-anchors & tight inner subject brackets render strictly
 *         inside canvas.clipRect(boxRect) so Zoe is never overwhelmed by the full room
 *   - Four solid white circular corner Resize Handles + centered 4-way Move Cursor + 1-tap jump
 *   - Strictly zero spinning rings and zero per-frame allocations in onDraw
 */
final class ZoeObservationBoxView extends View implements SensorEventListener {
    interface Listener {
        void onObservationBoxSettled(float leftU, float topV, float rightU, float bottomV, boolean wasTap);
        void onZoeEmblemTapped();
        void onBoxDoubleTap();
        void onBoxLongPress();
    }

    private enum DragMode {
        NONE,
        MOVE,
        TOP_LEFT,
        TOP_RIGHT,
        BOTTOM_LEFT,
        BOTTOM_RIGHT
    }

    private final Listener listener;
    private final Bitmap zoeGemBitmap;
    private final GestureDetector gestureDetector;
    private final SensorManager sensorManager;
    private final Sensor tiltSensor;
    private final ValueAnimator boxAnimator;

    private boolean active;
    private boolean initialized;
    private boolean sensorRegistered;
    private boolean visualSoundRadarEnabled;
    private ZoeArSurfaceView.VisualMood mood = ZoeArSurfaceView.VisualMood.EXPLORING;
    private float voiceLevel;
    private float ambientSoundLevel;

    // Selection Box front face in screen pixel coordinates
    private float boxLeft;
    private float boxTop;
    private float boxRight;
    private float boxBottom;

    // Active drag state
    private DragMode dragMode = DragMode.NONE;
    private float downX;
    private float downY;
    private float startLeft;
    private float startTop;
    private float startRight;
    private float startBottom;
    private boolean didDrag;

    // Interior AR state (strictly inside the Temporary Bounding Box)
    private float animPhase;
    private float zoeCurU = 0.74f;
    private float zoeCurV = 0.28f;
    private float zoeTargetU = 0.74f;
    private float zoeTargetV = 0.28f;
    private float lastDrawnGemCx;
    private float lastDrawnGemCy;
    private float lastDrawnGemHalf = 24f;
    private float smoothTiltX;
    private float smoothTiltY;
    private ArExploreBrain.BoxArAnalysis boxArAnalysis;

    // Pre-allocated paints & rects (strictly zero allocations in onDraw)
    private final Paint dimPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint outerDashPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint outerBackDashPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint innerDepthPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint borderPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint axisPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint axisTextPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint anchorFillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint anchorGlowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint scanLinePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint zoeHaloPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint handleFillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint handleStrokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint moveCursorPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint radarPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint gemBitmapPaint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);

    private final RectF boxRect = new RectF();
    private final RectF outerFrontRect = new RectF();
    private final RectF outerBackRect = new RectF();
    private final RectF innerBackRect = new RectF();
    private final RectF gemRect = new RectF();
    private final RectF radarRect = new RectF();
    private int cachedHaloColor = -1;
    private float cachedHaloRadius = -1f;
    private float cachedHaloCx = -1f;
    private float cachedHaloCy = -1f;

    ZoeObservationBoxView(Context context, Listener listener) {
        super(context);
        this.listener = listener;
        this.zoeGemBitmap = ZoeSpatialOverlayView.renderZoeGemBitmap(context, 192);
        this.sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        Sensor grav = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_GRAVITY) : null;
        this.tiltSensor = grav != null ? grav
                : (sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER) : null);

        float d = context.getResources().getDisplayMetrics().density;

        dimPaint.setStyle(Paint.Style.FILL);
        dimPaint.setColor(Color.argb(164, 6, 10, 18));

        outerDashPaint.setStyle(Paint.Style.STROKE);
        outerDashPaint.setStrokeWidth(1.25f * d);
        outerDashPaint.setColor(Color.argb(136, 224, 236, 250));
        outerDashPaint.setPathEffect(new DashPathEffect(new float[]{8.5f * d, 5.5f * d}, 0f));

        outerBackDashPaint.setStyle(Paint.Style.STROKE);
        outerBackDashPaint.setStrokeWidth(1.0f * d);
        outerBackDashPaint.setColor(Color.argb(72, 190, 214, 240));
        outerBackDashPaint.setPathEffect(new DashPathEffect(new float[]{6f * d, 5f * d}, 0f));

        innerDepthPaint.setStyle(Paint.Style.STROKE);
        innerDepthPaint.setStrokeWidth(1.05f * d);
        innerDepthPaint.setColor(Color.argb(95, 130, 228, 208));

        borderPaint.setStyle(Paint.Style.STROKE);

        axisPaint.setStyle(Paint.Style.STROKE);
        axisPaint.setStrokeWidth(1.2f * d);
        axisPaint.setStrokeCap(Paint.Cap.ROUND);
        axisTextPaint.setStyle(Paint.Style.FILL);
        axisTextPaint.setTextSize(9f * d);
        axisTextPaint.setTypeface(Typeface.MONOSPACE);

        anchorFillPaint.setStyle(Paint.Style.FILL);
        anchorGlowPaint.setStyle(Paint.Style.STROKE);
        anchorGlowPaint.setStrokeWidth(1.4f * d);

        scanLinePaint.setStyle(Paint.Style.STROKE);
        scanLinePaint.setStrokeWidth(2.0f * d);

        handleFillPaint.setStyle(Paint.Style.FILL);
        handleFillPaint.setColor(Color.WHITE);
        handleStrokePaint.setStyle(Paint.Style.STROKE);
        handleStrokePaint.setColor(Color.argb(118, 16, 20, 30));

        moveCursorPaint.setStyle(Paint.Style.STROKE);
        moveCursorPaint.setStrokeCap(Paint.Cap.ROUND);
        moveCursorPaint.setStrokeJoin(Paint.Join.ROUND);

        radarPaint.setStyle(Paint.Style.STROKE);
        setWillNotDraw(false);

        boxAnimator = ValueAnimator.ofFloat(0f, 1f);
        boxAnimator.setDuration(4400L);
        boxAnimator.setRepeatCount(ValueAnimator.INFINITE);
        boxAnimator.setInterpolator(new LinearInterpolator());
        boxAnimator.addUpdateListener(a -> {
            animPhase = (float) a.getAnimatedValue();
            // Smooth spring glide for Zoe strictly inside the Temporary Bounding Box
            zoeCurU += (zoeTargetU - zoeCurU) * 0.11f;
            zoeCurV += (zoeTargetV - zoeCurV) * 0.11f;
            if (active) {
                invalidate();
            }
        });

        gestureDetector = new GestureDetector(context, new GestureDetector.SimpleOnGestureListener() {
            @Override
            public boolean onSingleTapConfirmed(MotionEvent e) {
                if (!active || didDrag) {
                    return false;
                }
                if (isOnZoeInsideBox(e.getX(), e.getY())) {
                    performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    if (ZoeObservationBoxView.this.listener != null) {
                        ZoeObservationBoxView.this.listener.onZoeEmblemTapped();
                    }
                    return true;
                }
                if (isInsideBox(e.getX(), e.getY())) {
                    performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    notifyBoxSettled(true);
                    return true;
                }
                // Accessibility 1-tap jump: tapping anywhere on the frozen frame slides the box there!
                recenterBoxAt(e.getX(), e.getY());
                performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                notifyBoxSettled(true);
                return true;
            }

            @Override
            public boolean onDoubleTap(MotionEvent e) {
                if (active && ZoeObservationBoxView.this.listener != null) {
                    ZoeObservationBoxView.this.listener.onBoxDoubleTap();
                    return true;
                }
                return false;
            }

            @Override
            public void onLongPress(MotionEvent e) {
                if (active && !didDrag && ZoeObservationBoxView.this.listener != null) {
                    ZoeObservationBoxView.this.listener.onBoxLongPress();
                }
            }
        });
    }

    void setActive(boolean enabled) {
        if (this.active == enabled) {
            return;
        }
        this.active = enabled;
        dragMode = DragMode.NONE;
        didDrag = false;
        if (enabled) {
            boxArAnalysis = null;
            zoeTargetU = 0.74f;
            zoeTargetV = 0.28f;
            zoeCurU = zoeTargetU;
            zoeCurV = zoeTargetV;
            if (getWidth() > 1 && getHeight() > 1) {
                resetDefaultBox(getWidth(), getHeight());
            } else {
                initialized = false;
            }
            registerTiltSensor(true);
            if (!boxAnimator.isStarted()) {
                boxAnimator.start();
            } else if (boxAnimator.isPaused()) {
                boxAnimator.resume();
            }
        } else {
            registerTiltSensor(false);
            if (boxAnimator.isRunning()) {
                boxAnimator.pause();
            }
        }
        invalidate();
    }

    void setBoxArAnalysis(ArExploreBrain.BoxArAnalysis analysis) {
        this.boxArAnalysis = analysis;
        if (analysis != null) {
            this.zoeTargetU = Math.max(0.20f, Math.min(0.80f, analysis.zoePerchU));
            this.zoeTargetV = Math.max(0.20f, Math.min(0.80f, analysis.zoePerchV));
        }
        if (active) {
            invalidate();
        }
    }

    void resetToCenter() {
        boxArAnalysis = null;
        if (getWidth() > 1 && getHeight() > 1) {
            resetDefaultBox(getWidth(), getHeight());
            invalidate();
        } else {
            initialized = false;
        }
    }

    void setVisualMood(ZoeArSurfaceView.VisualMood nextMood) {
        this.mood = nextMood == null ? ZoeArSurfaceView.VisualMood.EXPLORING : nextMood;
        if (active) {
            invalidate();
        }
    }

    void setVoiceLevel(float level) {
        this.voiceLevel = Math.max(0f, Math.min(1f, level));
        if (active) {
            invalidate();
        }
    }

    void setVisualSoundRadarEnabled(boolean enabled) {
        this.visualSoundRadarEnabled = enabled;
        if (active) {
            invalidate();
        }
    }

    void setAmbientSoundLevel(float level) {
        this.ambientSoundLevel = Math.max(0f, Math.min(1f, level));
        if (active && visualSoundRadarEnabled) {
            invalidate();
        }
    }

    float getBoxLeftNorm() {
        return getWidth() <= 1 ? 0.22f : Math.max(0.02f, Math.min(0.95f, boxLeft / getWidth()));
    }

    float getBoxTopNorm() {
        return getHeight() <= 1 ? 0.28f : Math.max(0.05f, Math.min(0.90f, boxTop / getHeight()));
    }

    float getBoxRightNorm() {
        return getWidth() <= 1 ? 0.78f : Math.max(getBoxLeftNorm() + 0.08f, Math.min(0.98f, boxRight / getWidth()));
    }

    float getBoxBottomNorm() {
        return getHeight() <= 1 ? 0.62f : Math.max(getBoxTopNorm() + 0.08f, Math.min(0.94f, boxBottom / getHeight()));
    }

    private void registerTiltSensor(boolean register) {
        if (sensorManager == null || tiltSensor == null) {
            return;
        }
        if (register && !sensorRegistered) {
            try {
                sensorManager.registerListener(this, tiltSensor, SensorManager.SENSOR_DELAY_UI);
                sensorRegistered = true;
            } catch (Exception ignored) {
            }
        } else if (!register && sensorRegistered) {
            try {
                sensorManager.unregisterListener(this);
            } catch (Exception ignored) {
            }
            sensorRegistered = false;
            smoothTiltX = 0f;
            smoothTiltY = 0f;
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (!active || event == null || event.values == null || event.values.length < 2) {
            return;
        }
        // Subtle 3D bounding-volume parallax ONLY inside the box as the phone tilts gently
        float gx = Math.max(-6f, Math.min(6f, event.values[0])) / 6f;
        float gy = Math.max(-6f, Math.min(6f, event.values[1] - 4.5f)) / 6f;
        smoothTiltX += (gx - smoothTiltX) * 0.14f;
        smoothTiltY += (gy - smoothTiltY) * 0.14f;
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    protected void onDetachedFromWindow() {
        super.onDetachedFromWindow();
        registerTiltSensor(false);
        boxAnimator.cancel();
    }

    private void resetDefaultBox(int w, int h) {
        float side = Math.min(w * 0.64f, h * 0.35f);
        float cx = w * 0.5f;
        float cy = h * 0.44f;
        boxLeft = cx - side * 0.5f;
        boxRight = cx + side * 0.5f;
        boxTop = cy - side * 0.5f;
        boxBottom = cy + side * 0.5f;
        clampBoxToSafeViewport(w, h);
        initialized = true;
    }

    private void recenterBoxAt(float cx, float cy) {
        int w = getWidth();
        int h = getHeight();
        if (w <= 1 || h <= 1) {
            return;
        }
        float bw = boxRight - boxLeft;
        float bh = boxBottom - boxTop;
        boxLeft = cx - bw * 0.5f;
        boxRight = cx + bw * 0.5f;
        boxTop = cy - bh * 0.5f;
        boxBottom = cy + bh * 0.5f;
        clampBoxToSafeViewport(w, h);
        boxArAnalysis = null;
        invalidate();
    }

    private void clampBoxToSafeViewport(int w, int h) {
        float d = getResources().getDisplayMetrics().density;
        float padSide = 18f * d;
        float padTop = 86f * d;
        float padBottom = 184f * d;
        float minSize = 104f * d;

        float maxW = Math.max(minSize, w - padSide * 2f);
        float maxH = Math.max(minSize, h - padTop - padBottom);
        float bw = Math.max(minSize, Math.min(maxW, boxRight - boxLeft));
        float bh = Math.max(minSize, Math.min(maxH, boxBottom - boxTop));

        if (boxLeft < padSide) {
            boxLeft = padSide;
            boxRight = boxLeft + bw;
        }
        if (boxRight > w - padSide) {
            boxRight = w - padSide;
            boxLeft = boxRight - bw;
        }
        if (boxTop < padTop) {
            boxTop = padTop;
            boxBottom = boxTop + bh;
        }
        if (boxBottom > h - padBottom) {
            boxBottom = h - padBottom;
            boxTop = boxBottom - bh;
        }
    }

    @Override
    protected void onSizeChanged(int w, int h, int oldw, int oldh) {
        super.onSizeChanged(w, h, oldw, oldh);
        if (w > 1 && h > 1 && !initialized) {
            resetDefaultBox(w, h);
        } else if (w > 1 && h > 1) {
            clampBoxToSafeViewport(w, h);
        }
    }

    private boolean isInsideBox(float x, float y) {
        return x >= boxLeft && x <= boxRight && y >= boxTop && y <= boxBottom;
    }

    private boolean isOnZoeInsideBox(float x, float y) {
        float d = getResources().getDisplayMetrics().density;
        float hitR = Math.max(28f * d, lastDrawnGemHalf + 10f * d);
        return Math.hypot(x - lastDrawnGemCx, y - lastDrawnGemCy) <= hitR;
    }

    private DragMode hitTestHandle(float x, float y) {
        float d = getResources().getDisplayMetrics().density;
        float r = 38f * d;
        if (Math.hypot(x - boxLeft, y - boxTop) <= r) return DragMode.TOP_LEFT;
        if (Math.hypot(x - boxRight, y - boxTop) <= r) return DragMode.TOP_RIGHT;
        if (Math.hypot(x - boxLeft, y - boxBottom) <= r) return DragMode.BOTTOM_LEFT;
        if (Math.hypot(x - boxRight, y - boxBottom) <= r) return DragMode.BOTTOM_RIGHT;
        if (isInsideBox(x, y)) return DragMode.MOVE;
        return DragMode.NONE;
    }

    private void notifyBoxSettled(boolean wasTap) {
        if (listener != null && active) {
            listener.onObservationBoxSettled(
                    getBoxLeftNorm(), getBoxTopNorm(), getBoxRightNorm(), getBoxBottomNorm(), wasTap);
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (!active || event == null) {
            return false;
        }
        float d = getResources().getDisplayMetrics().density;
        float x = event.getX();
        float y = event.getY();

        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN -> {
                downX = x;
                downY = y;
                startLeft = boxLeft;
                startTop = boxTop;
                startRight = boxRight;
                startBottom = boxBottom;
                didDrag = false;
                dragMode = hitTestHandle(x, y);
                if (dragMode != DragMode.NONE) {
                    performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                }
            }
            case MotionEvent.ACTION_MOVE -> {
                if (dragMode != DragMode.NONE) {
                    float dx = x - downX;
                    float dy = y - downY;
                    if (!didDrag && Math.hypot(dx, dy) > 8f * d) {
                        didDrag = true;
                        boxArAnalysis = null;
                    }
                    if (didDrag) {
                        applyDragDelta(dx, dy);
                        invalidate();
                    }
                }
            }
            case MotionEvent.ACTION_UP -> {
                boolean finishedFraming = didDrag && dragMode != DragMode.NONE;
                dragMode = DragMode.NONE;
                invalidate();
                if (finishedFraming) {
                    performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    performClick();
                    notifyBoxSettled(false);
                    return true;
                }
            }
            case MotionEvent.ACTION_CANCEL -> {
                dragMode = DragMode.NONE;
                didDrag = false;
                invalidate();
            }
            default -> {
            }
        }
        gestureDetector.onTouchEvent(event);
        return true;
    }

    private void applyDragDelta(float dx, float dy) {
        int w = getWidth();
        int h = getHeight();
        float d = getResources().getDisplayMetrics().density;
        float padSide = 18f * d;
        float padTop = 86f * d;
        float padBottom = 184f * d;
        float minSize = 104f * d;

        switch (dragMode) {
            case MOVE -> {
                float bw = startRight - startLeft;
                float bh = startBottom - startTop;
                float nl = Math.max(padSide, Math.min(w - padSide - bw, startLeft + dx));
                float nt = Math.max(padTop, Math.min(h - padBottom - bh, startTop + dy));
                boxLeft = nl;
                boxTop = nt;
                boxRight = nl + bw;
                boxBottom = nt + bh;
            }
            case TOP_LEFT -> {
                boxLeft = Math.max(padSide, Math.min(startRight - minSize, startLeft + dx));
                boxTop = Math.max(padTop, Math.min(startBottom - minSize, startTop + dy));
            }
            case TOP_RIGHT -> {
                boxRight = Math.min(w - padSide, Math.max(startLeft + minSize, startRight + dx));
                boxTop = Math.max(padTop, Math.min(startBottom - minSize, startTop + dy));
            }
            case BOTTOM_LEFT -> {
                boxLeft = Math.max(padSide, Math.min(startRight - minSize, startLeft + dx));
                boxBottom = Math.min(h - padBottom, Math.max(startTop + minSize, startBottom + dy));
            }
            case BOTTOM_RIGHT -> {
                boxRight = Math.min(w - padSide, Math.max(startLeft + minSize, startRight + dx));
                boxBottom = Math.min(h - padBottom, Math.max(startTop + minSize, startBottom + dy));
            }
            default -> {
            }
        }
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    @Override
    protected void onDraw(Canvas canvas) {
        if (!active) {
            return;
        }
        int w = getWidth();
        int h = getHeight();
        if (w <= 1 || h <= 1) {
            return;
        }
        if (!initialized) {
            resetDefaultBox(w, h);
        }
        float d = getResources().getDisplayMetrics().density;
        float bw = boxRight - boxLeft;
        float bh = boxBottom - boxTop;
        float cx = (boxLeft + boxRight) * 0.5f;
        float cy = (boxTop + boxBottom) * 0.5f;
        float breathe = (float) Math.sin(animPhase * Math.PI * 2.0);

        // 1. Calm dimmed Cropping Overlay strictly OUTSIDE the Temporary Bounding Box (still, zero AR outside)
        canvas.drawRect(0f, 0f, w, boxTop, dimPaint);
        canvas.drawRect(0f, boxBottom, w, h, dimPaint);
        canvas.drawRect(0f, boxTop, boxLeft, boxBottom, dimPaint);
        canvas.drawRect(boxRight, boxTop, w, boxBottom, dimPaint);

        // Optional Deaf / HoH Visual Sound Radar border
        if (visualSoundRadarEnabled && ambientSoundLevel > 0.08f) {
            float rNorm = Math.min(1f, ambientSoundLevel);
            radarPaint.setStrokeWidth((2.5f + rNorm * 5f) * d);
            radarPaint.setColor(rNorm > 0.65f
                    ? Color.argb((int) (rNorm * 160), 255, 196, 86)
                    : Color.argb((int) (rNorm * 160), 72, 232, 196));
            float inset = 14f * d;
            radarRect.set(inset, inset * 3f, w - inset, h - inset * 3.4f);
            canvas.drawRoundRect(radarRect, 28f * d, 28f * d, radarPaint);
        }

        // 3D depth projection vector for the Temporary Bounding Volume (calm isometric default + subtle phone tilt)
        float depthDx = (10f - smoothTiltX * 6f) * d;
        float depthDy = (-8f + smoothTiltY * 5f) * d;

        // 2. Broad-Phase Outer Dashed 3D Bounding Volume (cleanly outside the white corner handles)
        float marginPx = 15f * d;
        outerFrontRect.set(
                Math.max(4f * d, boxLeft - marginPx),
                Math.max(4f * d, boxTop - marginPx),
                Math.min(w - 4f * d, boxRight + marginPx),
                Math.min(h - 4f * d, boxBottom + marginPx));
        outerBackRect.set(
                Math.max(2f * d, outerFrontRect.left + depthDx),
                Math.max(2f * d, outerFrontRect.top + depthDy),
                Math.min(w - 2f * d, outerFrontRect.right + depthDx),
                Math.min(h - 2f * d, outerFrontRect.bottom + depthDy));
        canvas.drawRect(outerBackRect, outerBackDashPaint);
        canvas.drawLine(outerFrontRect.left, outerFrontRect.top, outerBackRect.left, outerBackRect.top, outerBackDashPaint);
        canvas.drawLine(outerFrontRect.right, outerFrontRect.top, outerBackRect.right, outerBackRect.top, outerBackDashPaint);
        canvas.drawLine(outerFrontRect.left, outerFrontRect.bottom, outerBackRect.left, outerBackRect.bottom, outerBackDashPaint);
        canvas.drawLine(outerFrontRect.right, outerFrontRect.bottom, outerBackRect.right, outerBackRect.bottom, outerBackDashPaint);
        canvas.drawRect(outerFrontRect, outerDashPaint);

        int borderColor = switch (mood) {
            case LISTENING -> Color.argb(235, 110, 238, 196);
            case THINKING -> Color.argb(235, 252, 212, 120);
            case SPEAKING -> Color.argb(240, 248, 118, 152);
            default -> Color.argb(230, 255, 255, 255);
        };

        // 3. STRICTLY INTERIOR AUGMENTED REALITY SANDBOX (clipped to ONLY Zoe's Temporary Bounding Box!)
        boxRect.set(boxLeft, boxTop, boxRight, boxBottom);
        canvas.save();
        canvas.clipRect(boxRect);

        // 3a. Inner 3D tight containment back-plane & perspective depth rails inside the bounding box
        float insetX = Math.min(bw * 0.12f, 16f * d);
        float insetY = Math.min(bh * 0.12f, 16f * d);
        float innerBackShiftX = -smoothTiltX * 7f * d;
        float innerBackShiftY = smoothTiltY * 7f * d;
        innerBackRect.set(
                boxLeft + insetX + innerBackShiftX,
                boxTop + insetY + innerBackShiftY,
                boxRight - insetX + innerBackShiftX,
                boxBottom - insetY + innerBackShiftY);
        innerDepthPaint.setColor(Color.argb(66, Color.red(borderColor), Color.green(borderColor), Color.blue(borderColor)));
        canvas.drawRect(innerBackRect, innerDepthPaint);
        canvas.drawLine(boxLeft, boxTop, innerBackRect.left, innerBackRect.top, innerDepthPaint);
        canvas.drawLine(boxRight, boxTop, innerBackRect.right, innerBackRect.top, innerDepthPaint);
        canvas.drawLine(boxLeft, boxBottom, innerBackRect.left, innerBackRect.bottom, innerDepthPaint);
        canvas.drawLine(boxRight, boxBottom, innerBackRect.right, innerBackRect.bottom, innerDepthPaint);

        // 3b. Narrow-phase AR local salient micro-anchor dots strictly inside the box (zero clutter!)
        ArExploreBrain.BoxArAnalysis ar = boxArAnalysis;
        if (ar != null && ar.detailScore > 0.10f && dragMode == DragMode.NONE) {
            anchorFillPaint.setColor(Color.argb(195, 255, 224, 138));
            anchorGlowPaint.setColor(Color.argb(88, 128, 240, 212));
            for (int i = 0; i < ar.anchorUs.length && i < ar.anchorVs.length; i++) {
                float ax = boxLeft + ar.anchorUs[i] * bw;
                float ay = boxTop + ar.anchorVs[i] * bh;
                canvas.drawCircle(ax, ay, 2.5f * d, anchorFillPaint);
                canvas.drawCircle(ax, ay, (5.2f + 0.7f * breathe) * d, anchorGlowPaint);
            }
        }

        // 3c. Gentle single-axis shimmer line ONLY during the brief active inspection inside the box
        if (mood == ZoeArSurfaceView.VisualMood.THINKING) {
            float scanY = boxTop + ((animPhase * 2f) % 1f) * bh;
            scanLinePaint.setColor(Color.argb(105, 252, 212, 120));
            canvas.drawLine(boxLeft + 6f * d, scanY, boxRight - 6f * d, scanY, scanLinePaint);
        }

        // 3d. Subtle x / y / z axis triad well clear of the bottom-left white corner handle
        if (bw >= 150f * d && bh >= 150f * d) {
            drawMiniAxisTriad(canvas, boxLeft + 26f * d, boxBottom - 24f * d, d);
        }

        // 3e. Zoe Herself INSIDE the Temporary Bounding Box (strictly clamped to bounding volume walls!)
        float minSide = Math.min(bw, bh);
        float baseHalf = Math.max(15f * d, Math.min(24f * d, minSide * 0.14f));
        float gemScale = 1f + 0.04f * breathe + 0.11f * voiceLevel;
        float gemHalf = baseHalf * gemScale;
        float padWall = gemHalf + 10f * d;

        float rawGemCx = boxLeft + zoeCurU * bw + smoothTiltX * 7f * d;
        float rawGemCy = boxTop + zoeCurV * bh + breathe * 3.5f * d + smoothTiltY * 5f * d;
        float gemCx = Math.max(boxLeft + padWall, Math.min(boxRight - padWall, rawGemCx));
        float gemCy = Math.max(boxTop + padWall, Math.min(boxBottom - padWall, rawGemCy));
        lastDrawnGemCx = gemCx;
        lastDrawnGemCy = gemCy;
        lastDrawnGemHalf = gemHalf;

        // Soft warm AR presence halo behind Zoe strictly inside the box
        float haloR = gemHalf * 1.85f;
        int haloColor = switch (mood) {
            case LISTENING -> Color.rgb(98, 236, 192);
            case THINKING -> Color.rgb(252, 210, 118);
            case SPEAKING -> Color.rgb(248, 108, 144);
            default -> Color.rgb(236, 92, 126);
        };
        updateZoeHaloShader(gemCx, gemCy, haloR, haloColor);
        canvas.drawCircle(gemCx, gemCy, haloR, zoeHaloPaint);

        gemRect.set(gemCx - gemHalf, gemCy - gemHalf, gemCx + gemHalf, gemCy + gemHalf);
        canvas.drawBitmap(zoeGemBitmap, null, gemRect, gemBitmapPaint);

        // 3f. Subtle Centered 4-Way Move Cursor inside the box (brighter when moving)
        int cursorAlpha = dragMode == DragMode.MOVE ? 245 : 135;
        moveCursorPaint.setColor(Color.argb(cursorAlpha, 255, 126, 68));
        moveCursorPaint.setStrokeWidth(2.0f * d);
        float arm = 9.0f * d;
        float tip = 3.0f * d;
        canvas.drawLine(cx - arm, cy, cx + arm, cy, moveCursorPaint);
        canvas.drawLine(cx, cy - arm, cx, cy + arm, moveCursorPaint);
        canvas.drawLine(cx - arm, cy, cx - arm + tip, cy - tip, moveCursorPaint);
        canvas.drawLine(cx - arm, cy, cx - arm + tip, cy + tip, moveCursorPaint);
        canvas.drawLine(cx + arm, cy, cx + arm - tip, cy - tip, moveCursorPaint);
        canvas.drawLine(cx + arm, cy, cx + arm - tip, cy + tip, moveCursorPaint);
        canvas.drawLine(cx, cy - arm, cx - tip, cy - arm + tip, moveCursorPaint);
        canvas.drawLine(cx, cy - arm, cx + tip, cy - arm + tip, moveCursorPaint);
        canvas.drawLine(cx, cy + arm, cx - tip, cy + arm - tip, moveCursorPaint);
        canvas.drawLine(cx, cy + arm, cx + tip, cy + arm - tip, moveCursorPaint);

        canvas.restore();

        // 4. Crisp Front Selection Box Border + 4 Solid White Circular Corner Resize Handles
        borderPaint.setColor(borderColor);
        borderPaint.setStrokeWidth((dragMode != DragMode.NONE ? 2.4f : 1.75f) * d);
        canvas.drawRect(boxRect, borderPaint);

        float handleR = (dragMode != DragMode.NONE && dragMode != DragMode.MOVE ? 12.5f : 11f) * d;
        handleStrokePaint.setStrokeWidth(1.4f * d);
        drawCornerHandle(canvas, boxLeft, boxTop, handleR);
        drawCornerHandle(canvas, boxRight, boxTop, handleR);
        drawCornerHandle(canvas, boxLeft, boxBottom, handleR);
        drawCornerHandle(canvas, boxRight, boxBottom, handleR);
    }

    private void updateZoeHaloShader(float gemCx, float gemCy, float haloR, int haloColor) {
        if (cachedHaloColor != haloColor || Math.abs(cachedHaloRadius - haloR) > 1.5f
                || Math.abs(cachedHaloCx - gemCx) > 1.5f || Math.abs(cachedHaloCy - gemCy) > 1.5f) {
            cachedHaloColor = haloColor;
            cachedHaloRadius = haloR;
            cachedHaloCx = gemCx;
            cachedHaloCy = gemCy;
            zoeHaloPaint.setShader(new RadialGradient(gemCx, gemCy, Math.max(1f, haloR),
                    new int[]{
                            Color.argb(128, Color.red(haloColor), Color.green(haloColor), Color.blue(haloColor)),
                            Color.argb(38, Color.red(haloColor), Color.green(haloColor), Color.blue(haloColor)),
                            Color.TRANSPARENT},
                    new float[]{0.15f, 0.60f, 1.0f}, Shader.TileMode.CLAMP));
        }
    }

    private void drawMiniAxisTriad(Canvas canvas, float ox, float oy, float d) {
        float len = 14f * d;
        // x axis (right, soft mint)
        axisPaint.setColor(Color.argb(150, 120, 236, 198));
        canvas.drawLine(ox, oy, ox + len, oy, axisPaint);
        axisTextPaint.setColor(Color.argb(165, 120, 236, 198));
        canvas.drawText("x", ox + len + 2f * d, oy + 3f * d, axisTextPaint);

        // z axis (up, soft sky)
        axisPaint.setColor(Color.argb(150, 156, 212, 255));
        canvas.drawLine(ox, oy, ox, oy - len, axisPaint);
        axisTextPaint.setColor(Color.argb(165, 156, 212, 255));
        canvas.drawText("z", ox - 2.5f * d, oy - len - 2.5f * d, axisTextPaint);

        // y depth axis (diagonal back-right, soft coral)
        axisPaint.setColor(Color.argb(145, 255, 158, 134));
        canvas.drawLine(ox, oy, ox + len * 0.56f, oy - len * 0.48f, axisPaint);
    }

    private void drawCornerHandle(Canvas canvas, float x, float y, float radius) {
        canvas.drawCircle(x, y, radius, handleFillPaint);
        canvas.drawCircle(x, y, radius, handleStrokePaint);
    }
}
