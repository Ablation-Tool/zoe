package research.zoetic.zoe;

import android.app.Activity;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.ImageFormat;
import android.graphics.Matrix;
import android.media.Image;
import android.opengl.GLES11Ext;
import android.opengl.GLES20;
import android.opengl.GLSurfaceView;
import android.view.MotionEvent;
import android.view.Surface;
import android.view.WindowManager;

import com.google.ar.core.Anchor;
import com.google.ar.core.ArCoreApk;
import com.google.ar.core.Camera;
import com.google.ar.core.Config;
import com.google.ar.core.Coordinates2d;
import com.google.ar.core.Frame;
import com.google.ar.core.HitResult;
import com.google.ar.core.Plane;
import com.google.ar.core.Point;
import com.google.ar.core.Pose;
import com.google.ar.core.Session;
import com.google.ar.core.Trackable;
import com.google.ar.core.TrackingState;

import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.FloatBuffer;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicReference;

import javax.microedition.khronos.egl.EGLConfig;
import javax.microedition.khronos.opengles.GL10;

/**
 * Real Google Play Services for AR (ARCore) + OpenGL ES 2.0 3D Spatial Renderer for Zoe (v0.7.0-beta).
 *
 * Renders:
 *   1. Full-resolution live ARCore OES camera feed (zero aspect/rotation distortion)
 *   2. Soft translucent glass contours on discovered 3D horizontal & vertical planes (tables, walls, floors)
 *   3. Zoe's floating luminous 3D Polyhedral GEM Companion + dual orbital rings + floor depth halo
 *   4. Subtle 3D Discovery Beacons at places Zoe already explored in your room
 *
 * Supports:
 *   - Tap anywhere in your room to call Zoe over to that exact 3D Anchor (`frame.hitTest`)
 *   - Autonomous room roaming across discovered 3D planes (triggers curiosity inspection upon arrival!)
 *   - Fast on-demand upright Bitmap snapshot from ARCore's live CPU camera image (`frame.acquireCameraImage()`)
 */
final class ZoeArSurfaceView extends GLSurfaceView implements GLSurfaceView.Renderer {
    interface Listener {
        void onArTrackingUpdate(int planeCount, float zoeDistMeters, String statusHint);
        void onZoeArrivedAtSpot(Bitmap uprightFrame, ArExploreBrain.Vec3 worldPos, float distanceMeters, boolean userTapped);
        void onArUnavailable(String reason);
    }

    enum VisualMood {
        EXPLORING,
        LISTENING,
        THINKING,
        SPEAKING
    }

    private final Activity hostActivity;
    private final ArExploreBrain exploreBrain;
    private final Listener listener;
    private final Object sessionLock = new Object();

    private Session arSession;
    private volatile boolean sessionResumed;
    private boolean cameraTextureBound;
    private int viewportWidth = 1;
    private int viewportHeight = 1;
    private boolean viewportChanged = true;

    private volatile boolean autonomousRoam = true;
    private volatile VisualMood mood = VisualMood.EXPLORING;
    private volatile float voiceLevel;
    private final AtomicBoolean snapshotRequested = new AtomicBoolean(false);
    private final AtomicBoolean snapshotUserInitiated = new AtomicBoolean(false);
    private final AtomicReference<MotionEvent> pendingTap = new AtomicReference<>(null);
    private final Object latestSnapLock = new Object();
    private Bitmap latestCachedFrame;
    private float touchDownX;
    private float touchDownY;

    // 3D Companion motion state (updated on GL thread at 60fps)
    private ArExploreBrain.Vec3 zoePos = new ArExploreBrain.Vec3(0f, -0.05f, -1.15f);
    private ArExploreBrain.Vec3 zoeTarget = new ArExploreBrain.Vec3(0f, -0.05f, -1.15f);
    private Anchor activeAnchor;
    private final List<Anchor> discoveryAnchors = new ArrayList<>();
    private final List<ArExploreBrain.PlaneTarget> trackedPlanesScratch = new ArrayList<>(12);
    private volatile java.util.concurrent.ExecutorService snapshotExecutor =
            java.util.concurrent.Executors.newSingleThreadExecutor();
    private long lastFrameNs;
    private float elapsedSec;
    private long lastRoamPickMs;
    private long lastArriveTriggerMs;
    private long lastHudUpdateMs;
    private boolean pendingArrivalInspection;
    private boolean arrivalWasUserTap;

    // OpenGL handles
    private int cameraTexId = -1;
    private int bgProgram;
    private int bgPosAttr;
    private int bgUvAttr;
    private int colorProgram;
    private int colorPosAttr;
    private int colorMvpUniform;
    private int colorRgbaUniform;

    private final FloatBuffer quadCoords;
    private final FloatBuffer quadUvsTransformed;
    private final FloatBuffer gemVerts;
    private final int gemVertCount;
    private final FloatBuffer ringVerts;
    private final int ringVertCount;
    private FloatBuffer planeScratchBuf;
    private float[] planeScratchVerts = new float[0];
    private final float[] viewMatrix = new float[16];
    private final float[] projMatrix = new float[16];
    private final float[] modelMatrix = new float[16];
    private final float[] vpMatrix = new float[16];
    private final float[] mvpMatrix = new float[16];

    private static final float[] QUAD_NDC = {
            -1f, -1f,
            1f, -1f,
            -1f, 1f,
            1f, 1f
    };

    private static final String BG_VERT_SHADER =
            "attribute vec2 aPos;\n"
                    + "attribute vec2 aTex;\n"
                    + "varying vec2 vTex;\n"
                    + "void main() {\n"
                    + "  gl_Position = vec4(aPos, 0.0, 1.0);\n"
                    + "  vTex = aTex;\n"
                    + "}\n";

    private static final String BG_FRAG_SHADER =
            "#extension GL_OES_EGL_image_external : require\n"
                    + "precision mediump float;\n"
                    + "uniform samplerExternalOES sTex;\n"
                    + "varying vec2 vTex;\n"
                    + "void main() {\n"
                    + "  gl_FragColor = texture2D(sTex, vTex);\n"
                    + "}\n";

    private static final String COLOR_VERT_SHADER =
            "uniform mat4 uMvp;\n"
                    + "attribute vec3 aPos;\n"
                    + "void main() {\n"
                    + "  gl_Position = uMvp * vec4(aPos, 1.0);\n"
                    + "}\n";

    private static final String COLOR_FRAG_SHADER =
            "precision mediump float;\n"
                    + "uniform vec4 uColor;\n"
                    + "void main() {\n"
                    + "  gl_FragColor = uColor;\n"
                    + "}\n";

    ZoeArSurfaceView(Activity activity, ArExploreBrain brain, Listener listener) {
        super(activity);
        this.hostActivity = activity;
        this.exploreBrain = brain;
        this.listener = listener;

        setPreserveEGLContextOnPause(true);
        setEGLContextClientVersion(2);
        setEGLConfigChooser(8, 8, 8, 8, 16, 0);
        setRenderer(this);
        setRenderMode(RENDERMODE_CONTINUOUSLY);

        quadCoords = makeFloatBuffer(QUAD_NDC);
        quadUvsTransformed = ByteBuffer.allocateDirect(8 * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        float[] oct = buildOctahedronTriangles();
        gemVerts = makeFloatBuffer(oct);
        gemVertCount = oct.length / 3;
        float[] ring = buildCircleRing(40, 1.0f);
        ringVerts = makeFloatBuffer(ring);
        ringVertCount = ring.length / 3;
    }

    static boolean isArCoreSupported(Context ctx) {
        try {
            ArCoreApk.Availability avail = ArCoreApk.getInstance().checkAvailability(ctx);
            return avail.isSupported() || avail.isTransient();
        } catch (Throwable ignored) {
            return false;
        }
    }

    void setAutonomousRoam(boolean enabled) {
        this.autonomousRoam = enabled;
    }

    void setVisualMood(VisualMood mood) {
        this.mood = mood == null ? VisualMood.EXPLORING : mood;
    }

    void setVoiceLevel(float level) {
        this.voiceLevel = Math.max(0f, Math.min(1f, level));
    }

    /** Requests an immediate upright camera frame + Zoe's current 3D position for inspection. */
    void requestInstantLook() {
        snapshotUserInitiated.set(true);
        snapshotRequested.set(true);
    }

    /** Returns a fresh defensive copy of the latest upright AR camera frame (for Voice or Patent Reverse-Image Search). */
    Bitmap getLatestSnapshotCopy() {
        synchronized (latestSnapLock) {
            if (latestCachedFrame != null && !latestCachedFrame.isRecycled()) {
                return latestCachedFrame.copy(Bitmap.Config.ARGB_8888, false);
            }
            return null;
        }
    }

    /** Starts or resumes the real ARCore 6DoF session safely with synchronized GL thread lifecycle. */
    boolean startArSession() {
        synchronized (sessionLock) {
            try {
                ArCoreApk.InstallStatus install = ArCoreApk.getInstance().requestInstall(hostActivity, true);
                if (install == ArCoreApk.InstallStatus.INSTALL_REQUESTED) {
                    notifyUnavailable("Opening Google Play Services for AR install prompt…");
                    return false;
                }
                if (arSession == null) {
                    arSession = new Session(hostActivity);
                    Config cfg = new Config(arSession);
                    // Performance-tuned ARCore config: HORIZONTAL planes + disabled light/depth estimation
                    // cuts SLAM CPU & thermal load dramatically while keeping smooth 6DoF room tracking!
                    cfg.setPlaneFindingMode(Config.PlaneFindingMode.HORIZONTAL);
                    cfg.setUpdateMode(Config.UpdateMode.LATEST_CAMERA_IMAGE);
                    cfg.setFocusMode(Config.FocusMode.AUTO);
                    cfg.setLightEstimationMode(Config.LightEstimationMode.DISABLED);
                    cfg.setDepthMode(Config.DepthMode.DISABLED);
                    arSession.configure(cfg);
                    cameraTextureBound = false;
                }
                if (snapshotExecutor == null || snapshotExecutor.isShutdown()) {
                    snapshotExecutor = java.util.concurrent.Executors.newSingleThreadExecutor();
                }
                arSession.resume();
                sessionResumed = true;
                viewportChanged = true;
                onResume();
                return true;
            } catch (Throwable err) {
                notifyUnavailable("Google Play Services for AR unavailable: " + err.getMessage());
                stopArSession();
                return false;
            }
        }
    }

    void stopArSession() {
        sessionResumed = false;
        onPause();
        synchronized (sessionLock) {
            cameraTextureBound = false;
            clearAnchorsQuietly();
            if (arSession != null) {
                try {
                    arSession.pause();
                    arSession.close();
                } catch (Throwable ignored) {
                }
                arSession = null;
            }
        }
        synchronized (latestSnapLock) {
            if (latestCachedFrame != null && !latestCachedFrame.isRecycled()) {
                latestCachedFrame.recycle();
            }
            latestCachedFrame = null;
        }
        snapshotExecutor.shutdownNow();
    }

    private void clearAnchorsQuietly() {
        if (activeAnchor != null) {
            try {
                activeAnchor.detach();
            } catch (Throwable ignored) {
            }
            activeAnchor = null;
        }
        for (Anchor a : discoveryAnchors) {
            try {
                a.detach();
            } catch (Throwable ignored) {
            }
        }
        discoveryAnchors.clear();
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (event == null) {
            return false;
        }
        int act = event.getActionMasked();
        if (act == MotionEvent.ACTION_DOWN) {
            touchDownX = event.getX();
            touchDownY = event.getY();
            if (getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(true);
            }
            return true;
        }
        if (act == MotionEvent.ACTION_MOVE) {
            float dy = Math.abs(event.getY() - touchDownY);
            float dx = Math.abs(event.getX() - touchDownX);
            if (dy > 28f && dy > dx && getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(false);
            }
            return true;
        }
        if (act == MotionEvent.ACTION_UP) {
            if (getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(false);
            }
            if (Math.hypot(event.getX() - touchDownX, event.getY() - touchDownY) < 32f) {
                pendingTap.set(MotionEvent.obtain(event));
                performClick();
            }
            return true;
        }
        if (act == MotionEvent.ACTION_CANCEL && getParent() != null) {
            getParent().requestDisallowInterceptTouchEvent(false);
        }
        return true;
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    @Override
    public void onSurfaceCreated(GL10 gl, EGLConfig config) {
        GLES20.glClearColor(0.05f, 0.06f, 0.09f, 1.0f);
        int[] tex = new int[1];
        GLES20.glGenTextures(1, tex, 0);
        cameraTexId = tex[0];
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, cameraTexId);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_S, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_WRAP_T, GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MIN_FILTER, GLES20.GL_LINEAR);
        GLES20.glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, GLES20.GL_TEXTURE_MAG_FILTER, GLES20.GL_LINEAR);

        bgProgram = compileProgram(BG_VERT_SHADER, BG_FRAG_SHADER);
        bgPosAttr = GLES20.glGetAttribLocation(bgProgram, "aPos");
        bgUvAttr = GLES20.glGetAttribLocation(bgProgram, "aTex");

        colorProgram = compileProgram(COLOR_VERT_SHADER, COLOR_FRAG_SHADER);
        colorPosAttr = GLES20.glGetAttribLocation(colorProgram, "aPos");
        colorMvpUniform = GLES20.glGetUniformLocation(colorProgram, "uMvp");
        colorRgbaUniform = GLES20.glGetUniformLocation(colorProgram, "uColor");
        cameraTextureBound = false;
        lastFrameNs = System.nanoTime();
    }

    @Override
    public void onSurfaceChanged(GL10 gl, int width, int height) {
        GLES20.glViewport(0, 0, Math.max(1, width), Math.max(1, height));
        viewportWidth = Math.max(1, width);
        viewportHeight = Math.max(1, height);
        viewportChanged = true;
    }

    @Override
    public void onDrawFrame(GL10 gl) {
        GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT | GLES20.GL_DEPTH_BUFFER_BIT);
        synchronized (sessionLock) {
            Session session = arSession;
            if (session == null || !sessionResumed) {
                return;
            }
            try {
                if (!cameraTextureBound && cameraTexId >= 0) {
                    session.setCameraTextureName(cameraTexId);
                    cameraTextureBound = true;
                }
                if (viewportChanged) {
                    int rotation = currentDisplayRotation();
                    session.setDisplayGeometry(rotation, viewportWidth, viewportHeight);
                    viewportChanged = false;
                }
                Frame frame = session.update();
                Camera camera = frame.getCamera();

                // 1. Draw full-screen live AR camera background
                drawCameraBackground(frame);

                long nowNs = System.nanoTime();
                float dt = Math.max(0.001f, Math.min(0.1f, (nowNs - lastFrameNs) / 1_000_000_000f));
                lastFrameNs = nowNs;
                elapsedSec += dt;
                long nowMs = System.currentTimeMillis();

                if (camera.getTrackingState() != TrackingState.TRACKING) {
                    throttleHudUpdate(0, 0f, "Slowly move your phone to map surfaces…");
                    return;
                }

                camera.getViewMatrix(viewMatrix, 0);
                camera.getProjectionMatrix(projMatrix, 0, 0.08f, 30.0f);
                android.opengl.Matrix.multiplyMM(vpMatrix, 0, projMatrix, 0, viewMatrix, 0);

                Pose camPose = camera.getPose();
                ArExploreBrain.Vec3 camPos = new ArExploreBrain.Vec3(camPose.tx(), camPose.ty(), camPose.tz());
                float[] zAxis = camPose.getZAxis();
                ArExploreBrain.Vec3 camFwd = new ArExploreBrain.Vec3(-zAxis[0], -zAxis[1], -zAxis[2]);

                // 2. Collect & render up to 8 tracked 3D planes (reusing scratch list — zero GC stutter!)
                Collection<Plane> allPlanes = session.getAllTrackables(Plane.class);
                trackedPlanesScratch.clear();
                int surfaceCount = 0;
                GLES20.glEnable(GLES20.GL_BLEND);
                GLES20.glBlendFunc(GLES20.GL_SRC_ALPHA, GLES20.GL_ONE_MINUS_SRC_ALPHA);
                GLES20.glDisable(GLES20.GL_DEPTH_TEST);

                for (Plane plane : allPlanes) {
                    if (plane.getTrackingState() != TrackingState.TRACKING || plane.getSubsumedBy() != null) {
                        continue;
                    }
                    surfaceCount++;
                    if (surfaceCount <= 8) {
                        drawPlaneContour(plane);
                    }
                    Pose pp = plane.getCenterPose();
                    trackedPlanesScratch.add(new ArExploreBrain.PlaneTarget(
                            String.valueOf(System.identityHashCode(plane)),
                            new ArExploreBrain.Vec3(pp.tx(), pp.ty(), pp.tz()),
                            plane.getExtentX(),
                            plane.getExtentZ(),
                            plane.getType() == Plane.Type.VERTICAL
                    ));
                }

                // 3. Handle tap-to-call-Zoe hit-testing in real 3D world space!
                MotionEvent tap = pendingTap.getAndSet(null);
                if (tap != null) {
                    handleTapInWorld(frame, tap, camPos);
                    tap.recycle();
                }

                // 4. Update Zoe's 3D navigation target (User Tap Anchor OR Autonomous Curiosity Roam!)
                if (activeAnchor != null && activeAnchor.getTrackingState() == TrackingState.TRACKING) {
                    Pose ap = activeAnchor.getPose();
                    zoeTarget = new ArExploreBrain.Vec3(ap.tx(), ap.ty() + ArExploreBrain.HOVER_CLEARANCE_M, ap.tz());
                } else if (autonomousRoam && !trackedPlanesScratch.isEmpty() && (nowMs - lastRoamPickMs) > 10_500L) {
                    ArExploreBrain.PlaneTarget nextPlane = exploreBrain.chooseNextExploreTarget(camPos, trackedPlanesScratch);
                    if (nextPlane != null) {
                        zoeTarget = ArExploreBrain.hoverPositionForPlane(nextPlane, camPos);
                        lastRoamPickMs = nowMs;
                        pendingArrivalInspection = true;
                        arrivalWasUserTap = false;
                    }
                } else if (trackedPlanesScratch.isEmpty() && activeAnchor == null) {
                    zoeTarget = ArExploreBrain.defaultHoverInFront(camPos, camFwd, elapsedSec);
                }

                // Smooth 60fps 3D spring flight!
                zoePos = ArExploreBrain.stepGlide(zoePos, zoeTarget, dt, 2.8f);
                float zoeDist = camPos.distanceTo(zoePos);

                // Strictly ON-DEMAND snapshot (NEVER stalls GL thread on a periodic timer!):
                boolean reachedSpot = pendingArrivalInspection && zoePos.distanceTo(zoeTarget) < 0.14f
                        && (arrivalWasUserTap || (nowMs - lastArriveTriggerMs) > 9_500L);
                boolean explicitSnap = snapshotRequested.get();
                if (reachedSpot || explicitSnap) {
                    snapshotRequested.set(false);
                    boolean wasTap = arrivalWasUserTap || snapshotUserInitiated.getAndSet(false);
                    pendingArrivalInspection = false;
                    arrivalWasUserTap = false;
                    lastArriveTriggerMs = nowMs;
                    dispatchAsyncSnapshot(frame, zoePos, zoeDist, wasTap);
                }

                // 5. Render 3D discovery beacons + Zoe's floating 3D Luminous GEM Prism & Orbital Rings!
                GLES20.glEnable(GLES20.GL_DEPTH_TEST);
                drawDiscoveryBeacons();
                drawZoeCompanion3D(camPos);

                String hud = surfaceCount > 0
                        ? String.format(java.util.Locale.US, "● AR 6DoF · %d surfaces · %.1fm", surfaceCount, zoeDist)
                        : "● AR 6DoF · Scanning room…";
                throttleHudUpdate(surfaceCount, zoeDist, hud);
            } catch (Throwable ignored) {
            }
        }
    }

    private void handleTapInWorld(Frame frame, MotionEvent tap, ArExploreBrain.Vec3 camPos) {
        List<HitResult> hits = frame.hitTest(tap);
        for (HitResult hit : hits) {
            Trackable t = hit.getTrackable();
            boolean validPlane = (t instanceof Plane)
                    && ((Plane) t).isPoseInPolygon(hit.getHitPose())
                    && ((Plane) t).getTrackingState() == TrackingState.TRACKING;
            boolean validPoint = (t instanceof Point)
                    && ((Point) t).getOrientationMode() == Point.OrientationMode.ESTIMATED_SURFACE_NORMAL;
            if (validPlane || validPoint) {
                if (activeAnchor != null) {
                    try {
                        activeAnchor.detach();
                    } catch (Throwable ignored) {
                    }
                }
                activeAnchor = hit.createAnchor();
                if (discoveryAnchors.size() < 12) {
                    discoveryAnchors.add(hit.createAnchor());
                }
                Pose p = activeAnchor.getPose();
                zoeTarget = new ArExploreBrain.Vec3(p.tx(), p.ty() + ArExploreBrain.HOVER_CLEARANCE_M, p.tz());
                lastRoamPickMs = System.currentTimeMillis();
                pendingArrivalInspection = true;
                arrivalWasUserTap = true;
                return;
            }
        }
        // Even if tapping mid-air before planes lock, glide slightly closer and inspect!
        snapshotUserInitiated.set(true);
        snapshotRequested.set(true);
    }

    private void drawCameraBackground(Frame frame) {
        GLES20.glDisable(GLES20.GL_DEPTH_TEST);
        GLES20.glDepthMask(false);
        frame.transformCoordinates2d(
                Coordinates2d.OPENGL_NORMALIZED_DEVICE_COORDINATES,
                quadCoords,
                Coordinates2d.TEXTURE_NORMALIZED,
                quadUvsTransformed);
        quadCoords.position(0);
        quadUvsTransformed.position(0);

        GLES20.glUseProgram(bgProgram);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES, cameraTexId);
        GLES20.glEnableVertexAttribArray(bgPosAttr);
        GLES20.glVertexAttribPointer(bgPosAttr, 2, GLES20.GL_FLOAT, false, 0, quadCoords);
        GLES20.glEnableVertexAttribArray(bgUvAttr);
        GLES20.glVertexAttribPointer(bgUvAttr, 2, GLES20.GL_FLOAT, false, 0, quadUvsTransformed);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP, 0, 4);
        GLES20.glDisableVertexAttribArray(bgPosAttr);
        GLES20.glDisableVertexAttribArray(bgUvAttr);
        GLES20.glDepthMask(true);
    }

    private void drawPlaneContour(Plane plane) {
        FloatBuffer poly = plane.getPolygon();
        if (poly == null || poly.limit() < 6) {
            return;
        }
        int pts = poly.limit() / 2;
        int needed = pts * 3;
        if (planeScratchVerts.length < needed) {
            planeScratchVerts = new float[Math.max(needed, 96)];
            planeScratchBuf = ByteBuffer.allocateDirect(planeScratchVerts.length * 4)
                    .order(ByteOrder.nativeOrder()).asFloatBuffer();
        }
        for (int i = 0; i < pts; i++) {
            planeScratchVerts[i * 3] = poly.get(i * 2);
            planeScratchVerts[i * 3 + 1] = 0f;
            planeScratchVerts[i * 3 + 2] = poly.get(i * 2 + 1);
        }
        planeScratchBuf.clear();
        planeScratchBuf.put(planeScratchVerts, 0, needed);
        planeScratchBuf.position(0);
        FloatBuffer buf = planeScratchBuf;
        plane.getCenterPose().toMatrix(modelMatrix, 0);
        android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);

        GLES20.glUseProgram(colorProgram);
        GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
        GLES20.glEnableVertexAttribArray(colorPosAttr);
        GLES20.glVertexAttribPointer(colorPosAttr, 3, GLES20.GL_FLOAT, false, 0, buf);

        // Soft translucent DeepMind blue/aqua fill
        GLES20.glUniform4f(colorRgbaUniform, 0.34f, 0.68f, 1.0f, 0.11f);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLE_FAN, 0, pts);

        // Crisp subtle perimeter glow
        GLES20.glLineWidth(2.5f);
        GLES20.glUniform4f(colorRgbaUniform, 0.45f, 0.85f, 0.98f, 0.45f);
        GLES20.glDrawArrays(GLES20.GL_LINE_LOOP, 0, pts);
        GLES20.glDisableVertexAttribArray(colorPosAttr);
    }

    private void drawDiscoveryBeacons() {
        GLES20.glUseProgram(colorProgram);
        GLES20.glEnableVertexAttribArray(colorPosAttr);
        for (Anchor a : discoveryAnchors) {
            if (a.getTrackingState() != TrackingState.TRACKING) {
                continue;
            }
            Pose p = a.getPose();
            android.opengl.Matrix.setIdentityM(modelMatrix, 0);
            android.opengl.Matrix.translateM(modelMatrix, 0, p.tx(), p.ty() + 0.03f, p.tz());
            android.opengl.Matrix.rotateM(modelMatrix, 0, elapsedSec * 50f, 0f, 1f, 0f);
            android.opengl.Matrix.scaleM(modelMatrix, 0, 0.025f, 0.025f, 0.025f);
            android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
            GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
            GLES20.glUniform4f(colorRgbaUniform, 0.40f, 0.92f, 0.76f, 0.72f);
            gemVerts.position(0);
            GLES20.glVertexAttribPointer(colorPosAttr, 3, GLES20.GL_FLOAT, false, 0, gemVerts);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLES, 0, gemVertCount);
        }
        GLES20.glDisableVertexAttribArray(colorPosAttr);
    }

    private void drawZoeCompanion3D(ArExploreBrain.Vec3 camPos) {
        float bob = (float) Math.sin(elapsedSec * 2.4) * 0.028f;
        float pulse = 1.0f + 0.08f * (float) Math.sin(elapsedSec * 3.2) + 0.22f * voiceLevel;
        float r, g, b;
        switch (mood) {
            case LISTENING -> {
                r = 0.26f; g = 0.88f; b = 0.66f;
            }
            case THINKING -> {
                r = 0.96f; g = 0.74f; b = 0.36f;
            }
            case SPEAKING -> {
                r = 0.96f; g = 0.44f; b = 0.58f;
            }
            default -> {
                r = 0.42f; g = 0.68f; b = 1.00f;
            }
        }

        // Face gently toward the user while slowly spinning
        float yawDeg = (float) Math.toDegrees(Math.atan2(camPos.x - zoePos.x, camPos.z - zoePos.z)) + elapsedSec * 28f;

        GLES20.glUseProgram(colorProgram);
        GLES20.glEnableVertexAttribArray(colorPosAttr);

        // 1. Soft translucent outer crystal aura
        android.opengl.Matrix.setIdentityM(modelMatrix, 0);
        android.opengl.Matrix.translateM(modelMatrix, 0, zoePos.x, zoePos.y + bob, zoePos.z);
        android.opengl.Matrix.rotateM(modelMatrix, 0, yawDeg, 0f, 1f, 0f);
        android.opengl.Matrix.scaleM(modelMatrix, 0, 0.095f * pulse, 0.132f * pulse, 0.095f * pulse);
        android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
        GLES20.glUniform4f(colorRgbaUniform, r, g, b, 0.42f);
        gemVerts.position(0);
        GLES20.glVertexAttribPointer(colorPosAttr, 3, GLES20.GL_FLOAT, false, 0, gemVerts);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLES, 0, gemVertCount);

        // 2. Luminous inner GEM prism core
        android.opengl.Matrix.setIdentityM(modelMatrix, 0);
        android.opengl.Matrix.translateM(modelMatrix, 0, zoePos.x, zoePos.y + bob, zoePos.z);
        android.opengl.Matrix.rotateM(modelMatrix, 0, -yawDeg * 0.7f, 0f, 1f, 0f);
        android.opengl.Matrix.scaleM(modelMatrix, 0, 0.056f * pulse, 0.078f * pulse, 0.056f * pulse);
        android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
        GLES20.glUniform4f(colorRgbaUniform, Math.min(1f, r + 0.25f), Math.min(1f, g + 0.22f), Math.min(1f, b + 0.20f), 0.92f);
        gemVerts.position(0);
        GLES20.glVertexAttribPointer(colorPosAttr, 3, GLES20.GL_FLOAT, false, 0, gemVerts);
        GLES20.glDrawArrays(GLES20.GL_TRIANGLES, 0, gemVertCount);

        // 3. Dual counter-rotating orbital halo rings around Zoe!
        GLES20.glLineWidth(3.5f);
        ringVerts.position(0);
        GLES20.glVertexAttribPointer(colorPosAttr, 3, GLES20.GL_FLOAT, false, 0, ringVerts);

        android.opengl.Matrix.setIdentityM(modelMatrix, 0);
        android.opengl.Matrix.translateM(modelMatrix, 0, zoePos.x, zoePos.y + bob, zoePos.z);
        android.opengl.Matrix.rotateM(modelMatrix, 0, 28f, 1f, 0f, 0f);
        android.opengl.Matrix.rotateM(modelMatrix, 0, elapsedSec * 62f, 0f, 1f, 0f);
        android.opengl.Matrix.scaleM(modelMatrix, 0, 0.145f * pulse, 0.145f * pulse, 0.145f * pulse);
        android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
        GLES20.glUniform4f(colorRgbaUniform, r, g, b, 0.85f);
        GLES20.glDrawArrays(GLES20.GL_LINE_LOOP, 0, ringVertCount);

        android.opengl.Matrix.setIdentityM(modelMatrix, 0);
        android.opengl.Matrix.translateM(modelMatrix, 0, zoePos.x, zoePos.y + bob, zoePos.z);
        android.opengl.Matrix.rotateM(modelMatrix, 0, -34f, 0f, 0f, 1f);
        android.opengl.Matrix.rotateM(modelMatrix, 0, -elapsedSec * 48f, 0f, 1f, 0f);
        android.opengl.Matrix.scaleM(modelMatrix, 0, 0.175f * pulse, 0.175f * pulse, 0.175f * pulse);
        android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
        GLES20.glUniform4f(colorRgbaUniform, 0.55f, 0.90f, 1.0f, 0.58f);
        GLES20.glDrawArrays(GLES20.GL_LINE_LOOP, 0, ringVertCount);

        // 4. Subtle surface halo directly beneath Zoe to ground her 3D depth in your room!
        android.opengl.Matrix.setIdentityM(modelMatrix, 0);
        android.opengl.Matrix.translateM(modelMatrix, 0, zoePos.x, zoePos.y - ArExploreBrain.HOVER_CLEARANCE_M + 0.01f, zoePos.z);
        android.opengl.Matrix.scaleM(modelMatrix, 0, 0.09f, 0.09f, 0.09f);
        android.opengl.Matrix.multiplyMM(mvpMatrix, 0, vpMatrix, 0, modelMatrix, 0);
        GLES20.glUniformMatrix4fv(colorMvpUniform, 1, false, mvpMatrix, 0);
        GLES20.glUniform4f(colorRgbaUniform, r, g, b, 0.45f);
        GLES20.glDrawArrays(GLES20.GL_LINE_LOOP, 0, ringVertCount);

        GLES20.glDisableVertexAttribArray(colorPosAttr);
    }

    private void throttleHudUpdate(int surfaces, float distM, String text) {
        long now = System.currentTimeMillis();
        if (listener != null && (now - lastHudUpdateMs) > 650L) {
            lastHudUpdateMs = now;
            hostActivity.runOnUiThread(() -> listener.onArTrackingUpdate(surfaces, distM, text));
        }
    }

    /**
     * Copies only downsampled raw YUV samples (~20KB, <1.2ms on GL thread!) and performs RGB
     * conversion + rotation completely OFF the GL thread so ARCore never drops frames!
     */
    private void dispatchAsyncSnapshot(Frame frame, ArExploreBrain.Vec3 spotCopy, float zoeDist, boolean wasTap) {
        final int rotDeg = switch (currentDisplayRotation()) {
            case Surface.ROTATION_90 -> 0;
            case Surface.ROTATION_180 -> 270;
            case Surface.ROTATION_270 -> 180;
            default -> 90;
        };
        final int outW;
        final int outH;
        final byte[] ySmall;
        final byte[] uSmall;
        final byte[] vSmall;
        try (Image img = frame.acquireCameraImage()) {
            if (img == null || img.getFormat() != ImageFormat.YUV_420_888) {
                return;
            }
            int w = img.getWidth();
            int h = img.getHeight();
            int step = Math.max(2, Math.max(w, h) / 300);
            outW = Math.max(1, w / step);
            outH = Math.max(1, h / step);
            ySmall = new byte[outW * outH];
            uSmall = new byte[outW * outH];
            vSmall = new byte[outW * outH];

            Image.Plane yp = img.getPlanes()[0];
            Image.Plane up = img.getPlanes()[1];
            Image.Plane vp = img.getPlanes()[2];
            ByteBuffer yBuf = yp.getBuffer();
            ByteBuffer uBuf = up.getBuffer();
            ByteBuffer vBuf = vp.getBuffer();
            int yRS = yp.getRowStride(), yPS = yp.getPixelStride(), yLim = yBuf.limit();
            int uRS = up.getRowStride(), uPS = up.getPixelStride(), uLim = uBuf.limit();
            int vRS = vp.getRowStride(), vPS = vp.getPixelStride(), vLim = vBuf.limit();

            int dst = 0;
            for (int oy = 0; oy < outH; oy++) {
                int sy = oy * step;
                int yRow = sy * yRS;
                int uvRow = (sy >> 1) * uRS;
                int vRow = (sy >> 1) * vRS;
                for (int ox = 0; ox < outW; ox++) {
                    int sx = ox * step;
                    int yo = yRow + sx * yPS;
                    int uo = uvRow + (sx >> 1) * uPS;
                    int vo = vRow + (sx >> 1) * vPS;
                    ySmall[dst] = yo < yLim ? yBuf.get(yo) : 0;
                    uSmall[dst] = uo < uLim ? uBuf.get(uo) : (byte) 128;
                    vSmall[dst] = vo < vLim ? vBuf.get(vo) : (byte) 128;
                    dst++;
                }
            }
        } catch (Throwable ignored) {
            return;
        }

        java.util.concurrent.ExecutorService exec = snapshotExecutor;
        if (exec == null || exec.isShutdown()) {
            return;
        }
        try {
            exec.execute(() -> {
            try {
                int[] pixels = new int[outW * outH];
                for (int i = 0; i < pixels.length; i++) {
                    int yVal = ySmall[i] & 0xFF;
                    int uVal = (uSmall[i] & 0xFF) - 128;
                    int vVal = (vSmall[i] & 0xFF) - 128;
                    int r = clampByte(yVal + ((351 * vVal) >> 8));
                    int g = clampByte(yVal - ((179 * vVal + 86 * uVal) >> 8));
                    int b = clampByte(yVal + ((443 * uVal) >> 8));
                    pixels[i] = 0xFF000000 | (r << 16) | (g << 8) | b;
                }
                Bitmap raw = Bitmap.createBitmap(pixels, outW, outH, Bitmap.Config.ARGB_8888);
                Bitmap upright = raw;
                if (rotDeg != 0) {
                    Matrix m = new Matrix();
                    m.postRotate(rotDeg);
                    upright = Bitmap.createBitmap(raw, 0, 0, raw.getWidth(), raw.getHeight(), m, true);
                    if (upright != raw) {
                        raw.recycle();
                    }
                }
                synchronized (latestSnapLock) {
                    if (latestCachedFrame != null && !latestCachedFrame.isRecycled()) {
                        latestCachedFrame.recycle();
                    }
                    latestCachedFrame = upright.copy(Bitmap.Config.ARGB_8888, false);
                }
                Bitmap finalSnap = upright;
                if (listener != null) {
                    hostActivity.runOnUiThread(() -> listener.onZoeArrivedAtSpot(finalSnap, spotCopy, zoeDist, wasTap));
                }
            } catch (Throwable ignored) {
            }
        });
        } catch (java.util.concurrent.RejectedExecutionException ignored) {
        }
    }

    private void notifyUnavailable(String msg) {
        if (listener != null) {
            hostActivity.runOnUiThread(() -> listener.onArUnavailable(msg));
        }
    }

    private int currentDisplayRotation() {
        WindowManager wm = (WindowManager) hostActivity.getSystemService(Context.WINDOW_SERVICE);
        if (wm != null && wm.getDefaultDisplay() != null) {
            return wm.getDefaultDisplay().getRotation();
        }
        return Surface.ROTATION_0;
    }

    private static int clampByte(int v) {
        return v < 0 ? 0 : Math.min(255, v);
    }

    private static FloatBuffer makeFloatBuffer(float[] data) {
        FloatBuffer fb = ByteBuffer.allocateDirect(data.length * 4).order(ByteOrder.nativeOrder()).asFloatBuffer();
        fb.put(data);
        fb.position(0);
        return fb;
    }

    private static float[] buildOctahedronTriangles() {
        float[] top = {0f, 1f, 0f};
        float[] bot = {0f, -1f, 0f};
        float[] px = {1f, 0f, 0f};
        float[] nx = {-1f, 0f, 0f};
        float[] pz = {0f, 0f, 1f};
        float[] nz = {0f, 0f, -1f};
        float[][] tris = {
                top, pz, px, top, px, nz, top, nz, nx, top, nx, pz,
                bot, px, pz, bot, nz, px, bot, nx, nz, bot, pz, nx
        };
        float[] out = new float[tris.length * 3];
        for (int i = 0; i < tris.length; i++) {
            out[i * 3] = tris[i][0];
            out[i * 3 + 1] = tris[i][1];
            out[i * 3 + 2] = tris[i][2];
        }
        return out;
    }

    private static float[] buildCircleRing(int segments, float radius) {
        float[] out = new float[segments * 3];
        for (int i = 0; i < segments; i++) {
            double ang = (2.0 * Math.PI * i) / segments;
            out[i * 3] = (float) (Math.cos(ang) * radius);
            out[i * 3 + 1] = 0f;
            out[i * 3 + 2] = (float) (Math.sin(ang) * radius);
        }
        return out;
    }

    private static int compileProgram(String vs, String fs) {
        int v = compileShader(GLES20.GL_VERTEX_SHADER, vs);
        int f = compileShader(GLES20.GL_FRAGMENT_SHADER, fs);
        int p = GLES20.glCreateProgram();
        GLES20.glAttachShader(p, v);
        GLES20.glAttachShader(p, f);
        GLES20.glLinkProgram(p);
        return p;
    }

    private static int compileShader(int type, String src) {
        int s = GLES20.glCreateShader(type);
        GLES20.glShaderSource(s, src);
        GLES20.glCompileShader(s);
        return s;
    }
}
