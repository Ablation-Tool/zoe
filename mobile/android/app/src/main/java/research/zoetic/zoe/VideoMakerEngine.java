package research.zoetic.zoe;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;
import android.view.Surface;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;

/**
 * Zoe Native Offline HD Video Maker Engine (v0.9.4-beta).
 *
 * Encodes genuine H.264 `.mp4` videos 100% on-device via Android's built-in
 * `MediaCodec` (`video/avc`) + `MediaMuxer` at exact constant-frame-rate 30fps HD (`720×720`)
 * with ZERO external libraries, ZERO cloud uploads, and ZERO watermarks:
 *   - Chladni Wave (animated standing-wave nodal interference)
 *   - Photo Story Reel (smooth cosine-eased Ken Burns zoom & pan over any Image Lab artwork)
 *   - Starlight GEM (luminous harmonic rings + breathing prism)
 *   - Haeckel Living (rotating D_12 silica lattice + pulsing golden-angle phyllotaxis core)
 *   - Patent Kinetic (counter-rotating involute gears + optical prism ray sweep)
 */
final class VideoMakerEngine {
    static final int WIDTH = 720;
    static final int HEIGHT = 720;
    static final int FPS = 30;
    static final int BITRATE = 3_200_000;

    enum Style {
        CHLADNI_RESONANCE("Chladni Wave"),
        PHOTO_STORY_REEL("Photo Story Reel"),
        STARLIGHT_PULSE("Starlight GEM"),
        HAECKEL_LIVING("Haeckel Living"),
        PATENT_KINETIC("Patent Kinetic");

        final String label;

        Style(String label) {
            this.label = label;
        }
    }

    enum Palette {
        COBALT_AURORA("Cobalt Aurora", Color.rgb(12, 18, 36), Color.rgb(86, 156, 255), Color.rgb(72, 224, 196)),
        ROSE_GOLD("Rose Gold", Color.rgb(28, 14, 24), Color.rgb(245, 118, 152), Color.rgb(252, 204, 128)),
        EMERALD_TIDE("Emerald Tide", Color.rgb(10, 26, 24), Color.rgb(66, 214, 164), Color.rgb(138, 232, 255)),
        SOLAR_AMBER("Solar Amber", Color.rgb(26, 18, 12), Color.rgb(255, 168, 76), Color.rgb(255, 226, 138));

        final String label;
        final int bg;
        final int primary;
        final int secondary;

        Palette(String label, int bg, int primary, int secondary) {
            this.label = label;
            this.bg = bg;
            this.primary = primary;
            this.secondary = secondary;
        }
    }

    static final class Spec {
        Style style = Style.CHLADNI_RESONANCE;
        Palette palette = Palette.COBALT_AURORA;
        String title = "Made with Zoe";
        String subtitle = "Offline Creative Studio";
        int durationSec = 4;

        int totalFrames() {
            int clampedSec = Math.max(2, Math.min(10, durationSec));
            return clampedSec * FPS;
        }
    }

    interface ProgressCallback {
        void onFrame(int frameIndex, int totalFrames);
    }

    private VideoMakerEngine() {
    }

    /** Pure JVM-testable exact constant-frame-rate microsecond timestamp helper (fixes wall-clock drift). */
    static long framePresentationTimeUs(int frameIndex, int fps) {
        int safeFps = Math.max(1, fps);
        return (Math.max(0L, (long) frameIndex) * 1_000_000L) / safeFps;
    }

    static void renderFrame(Canvas canvas, int w, int h, Bitmap optionalPhoto, Spec spec, float t) {
        Spec s = spec == null ? new Spec() : spec;
        canvas.drawColor(s.palette.bg);
        float scale = Math.min(w, h) / 480f;

        if (s.style == Style.PHOTO_STORY_REEL && optionalPhoto != null) {
            // Smooth cosine ease-in-out Ken Burns zoom & pan
            float eased = 0.5f - 0.5f * (float) Math.cos(t * Math.PI);
            float zoom = 1.0f + 0.18f * eased;
            int pw = optionalPhoto.getWidth();
            int ph = optionalPhoto.getHeight();
            int cropW = Math.max(16, (int) (pw / zoom));
            int cropH = Math.max(16, (int) (ph / zoom));
            int maxShiftX = Math.max(0, pw - cropW);
            int maxShiftY = Math.max(0, ph - cropH);
            int sx = (int) (maxShiftX * eased);
            int sy = (int) (maxShiftY * (0.35f + 0.30f * eased));
            Paint p = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
            canvas.drawBitmap(optionalPhoto, new Rect(sx, sy, sx + cropW, sy + cropH), new Rect(0, 0, w, h), p);

            Paint scrim = new Paint();
            scrim.setShader(new LinearGradient(0, h * 0.60f, 0, h,
                    Color.TRANSPARENT, Color.argb(220, 10, 13, 22), Shader.TileMode.CLAMP));
            canvas.drawRect(0, h * 0.60f, w, h, scrim);
        } else if (s.style == Style.CHLADNI_RESONANCE) {
            double phase = t * Math.PI * 2.0;
            double m = 2.0 + 2.5 * Math.sin(phase * 0.5);
            double n = 4.0 + 2.0 * Math.cos(phase * 0.5);
            Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
            int step = Math.max(8, w / 64);
            for (int y = step / 2; y < h; y += step) {
                double ny = (double) y / h;
                double cmY = Math.cos(m * Math.PI * ny - phase * 0.3);
                double cnY = Math.cos(n * Math.PI * ny);
                for (int x = step / 2; x < w; x += step) {
                    double nx = (double) x / w;
                    double val = Math.cos(m * Math.PI * nx + phase * 0.3) * cnY
                            - Math.cos(n * Math.PI * nx) * cmY;
                    double nodal = Math.max(0.0, 1.0 - Math.abs(val) * 3.5);
                    if (nodal > 0.16) {
                        int alpha = (int) Math.min(255, nodal * 245);
                        dot.setColor(blendColor(s.palette.primary, s.palette.secondary, (float) ((nx + ny) * 0.5), alpha));
                        canvas.drawCircle(x, y, (float) ((1.5 + nodal * 2.7) * scale), dot);
                    }
                }
            }
        } else if (s.style == Style.HAECKEL_LIVING) {
            // Rotating D_12 Haeckel radiolaria lattice + breathing golden-angle phyllotaxis core
            float cx = w * 0.5f;
            float cy = h * 0.45f;
            float maxR = Math.min(w, h) * 0.34f;
            int order = 12;
            double rot = t * Math.PI * 2.0 / 3.0;
            float pulse = 1.0f + 0.06f * (float) Math.sin(t * Math.PI * 4.0);

            Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
            line.setStyle(Paint.Style.STROKE);
            line.setStrokeCap(Paint.Cap.ROUND);
            for (int i = 0; i < order; i++) {
                double a = rot + (2.0 * Math.PI * i) / order;
                float cos = (float) Math.cos(a);
                float sin = (float) Math.sin(a);
                line.setStrokeWidth(2.4f * scale);
                line.setColor(i % 2 == 0 ? s.palette.primary : s.palette.secondary);
                canvas.drawLine(cx + cos * maxR * 0.22f, cy + sin * maxR * 0.22f,
                        cx + cos * maxR * 1.06f * pulse, cy + sin * maxR * 1.06f * pulse, line);
            }
            float[] rings = {0.32f, 0.56f, 0.80f};
            for (int rIdx = 0; rIdx < rings.length; rIdx++) {
                float rad = maxR * rings[rIdx] * pulse;
                line.setStrokeWidth(1.6f * scale);
                line.setColor(blendColor(s.palette.primary, s.palette.secondary, rIdx / 2f, 185));
                canvas.drawCircle(cx, cy, rad, line);
                Path poly = new Path();
                double spin = rIdx % 2 == 0 ? rot : -rot;
                for (int i = 0; i <= order; i++) {
                    double a = spin + (2.0 * Math.PI * i) / order;
                    float px = cx + (float) Math.cos(a) * rad;
                    float py = cy + (float) Math.sin(a) * rad;
                    if (i == 0) poly.moveTo(px, py);
                    else poly.lineTo(px, py);
                }
                canvas.drawPath(poly, line);
            }
            Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
            double pScale = maxR * 0.044 * pulse;
            for (int k = 1; k <= 78; k++) {
                double[] pt = ScientificVisualSubstrate.phyllotaxisPoint(k, pScale);
                float rx = (float) (pt[0] * Math.cos(-rot) - pt[1] * Math.sin(-rot));
                float ry = (float) (pt[0] * Math.sin(-rot) + pt[1] * Math.cos(-rot));
                dot.setColor(blendColor(s.palette.secondary, s.palette.primary, k / 78f, 235));
                canvas.drawCircle(cx + rx, cy + ry, (2.2f + (k / 78f) * 2.6f) * scale, dot);
            }
        } else if (s.style == Style.PATENT_KINETIC) {
            // Prussian drafting grid + interlocking counter-rotating involute gears + sweeping prism ray
            Paint grid = new Paint(Paint.ANTI_ALIAS_FLAG);
            grid.setColor(Color.argb(32, 180, 218, 255));
            grid.setStrokeWidth(1f * scale);
            int gStep = Math.max(24, w / 20);
            for (int x = gStep; x < w; x += gStep) canvas.drawLine(x, 0, x, h, grid);
            for (int y = gStep; y < h; y += gStep) canvas.drawLine(0, y, w, y, grid);

            Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
            line.setStyle(Paint.Style.STROKE);
            line.setColor(Color.rgb(235, 244, 255));
            line.setStrokeWidth(2.4f * scale);

            Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
            dash.setStyle(Paint.Style.STROKE);
            dash.setColor(s.palette.secondary);
            dash.setStrokeWidth(1.3f * scale);
            dash.setPathEffect(new DashPathEffect(new float[]{10f * scale, 5f * scale}, 0f));

            double rot1 = t * Math.PI * 2.0 / 2.0;
            double rot2 = -rot1 * (14.0 / 10.0) + Math.PI / 10.0;
            drawGear(canvas, w * 0.36f, h * 0.45f, w * 0.17f, 14, rot1, line, dash);
            drawGear(canvas, w * 0.67f, h * 0.45f, w * 0.12f, 10, rot2, line, dash);

            // Sweeping golden laser ray across drafting plane
            Paint ray = new Paint(Paint.ANTI_ALIAS_FLAG);
            ray.setColor(s.palette.primary);
            ray.setStrokeWidth(2.6f * scale);
            float sweepY = h * (0.28f + 0.32f * (0.5f + 0.5f * (float) Math.sin(t * Math.PI * 2.0)));
            canvas.drawLine(w * 0.08f, sweepY, w * 0.92f, h * 0.88f - sweepY, ray);
        } else {
            // Starlight GEM expanding harmonic waves
            float cx = w * 0.5f;
            float cy = h * 0.44f;
            Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
            ring.setStyle(Paint.Style.STROKE);
            for (int i = 0; i < 9; i++) {
                float p = (t + i / 9.0f) % 1.0f;
                float r = 24f * scale + p * (w * 0.48f);
                int alpha = (int) ((1.0f - p) * 215);
                ring.setStrokeWidth((3.5f * (1.0f - p) + 1.2f) * scale);
                ring.setColor(blendColor(s.palette.primary, s.palette.secondary, p, alpha));
                canvas.drawCircle(cx, cy, r, ring);
            }
            Paint gem = new Paint(Paint.ANTI_ALIAS_FLAG);
            gem.setColor(s.palette.primary);
            Path diamond = new Path();
            float rad = (36f + (float) Math.sin(t * Math.PI * 4.0) * 6f) * scale;
            diamond.moveTo(cx, cy - rad);
            diamond.lineTo(cx + rad, cy);
            diamond.lineTo(cx, cy + rad);
            diamond.lineTo(cx - rad, cy);
            diamond.close();
            canvas.drawPath(diamond, gem);
        }

        // Clean title & subtitle lower-third overlay
        Paint titlePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        titlePaint.setColor(Color.rgb(245, 248, 252));
        titlePaint.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        titlePaint.setTextAlign(Paint.Align.CENTER);
        titlePaint.setTextSize(30f * scale);
        titlePaint.setShadowLayer(8f * scale, 0f, 2f * scale, Color.argb(185, 0, 0, 0));

        Paint subPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        subPaint.setColor(Color.rgb(200, 214, 232));
        subPaint.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        subPaint.setTextAlign(Paint.Align.CENTER);
        subPaint.setTextSize(18f * scale);

        String title = (s.title == null || s.title.trim().isEmpty()) ? "Made with Zoe" : s.title.trim();
        String sub = s.subtitle == null ? "" : s.subtitle.trim();
        canvas.drawText(title, w / 2f, h - 62f * scale, titlePaint);
        if (!sub.isEmpty()) {
            canvas.drawText(sub, w / 2f, h - 32f * scale, subPaint);
        }
    }

    private static void drawGear(Canvas canvas, float cx, float cy, float gr, int teeth,
                                 double rot, Paint line, Paint dash) {
        Path gear = new Path();
        for (int i = 0; i < teeth * 2; i++) {
            double a = rot + (Math.PI * i) / teeth;
            float r = (i % 2 == 0) ? gr * 1.13f : gr * 0.92f;
            float px = cx + (float) Math.cos(a) * r;
            float py = cy + (float) Math.sin(a) * r;
            if (i == 0) gear.moveTo(px, py);
            else gear.lineTo(px, py);
        }
        gear.close();
        canvas.drawPath(gear, line);
        canvas.drawCircle(cx, cy, gr * 0.50f, line);
        canvas.drawCircle(cx, cy, gr * 0.18f, line);
        canvas.drawLine(cx - gr * 1.25f, cy, cx + gr * 1.25f, cy, dash);
        canvas.drawLine(cx, cy - gr * 1.25f, cx, cy + gr * 1.25f, dash);
    }

    static File exportMp4(File outFile, Bitmap optionalPhoto, Spec spec, ProgressCallback callback) throws IOException {
        Spec s = spec == null ? new Spec() : spec;
        int totalFrames = s.totalFrames();
        File parent = outFile.getParentFile();
        if (parent != null && !parent.exists()) {
            //noinspection ResultOfMethodCallIgnored
            parent.mkdirs();
        }
        if (outFile.exists()) {
            //noinspection ResultOfMethodCallIgnored
            outFile.delete();
        }

        MediaFormat format = MediaFormat.createVideoFormat(MediaFormat.MIMETYPE_VIDEO_AVC, WIDTH, HEIGHT);
        format.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);
        format.setInteger(MediaFormat.KEY_BIT_RATE, BITRATE);
        format.setInteger(MediaFormat.KEY_FRAME_RATE, FPS);
        format.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, 1);

        MediaCodec encoder = null;
        MediaMuxer muxer = null;
        Surface inputSurface = null;
        boolean muxerStarted = false;
        int trackIndex = -1;
        int emittedFrames = 0;

        try {
            encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC);
            encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE);
            inputSurface = encoder.createInputSurface();
            encoder.start();

            muxer = new MediaMuxer(outFile.getAbsolutePath(), MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4);
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();

            for (int frame = 0; frame < totalFrames; frame++) {
                float progress = totalFrames <= 1 ? 0f : (float) frame / (totalFrames - 1);
                Canvas surfaceCanvas = inputSurface.lockHardwareCanvas();
                try {
                    renderFrame(surfaceCanvas, WIDTH, HEIGHT, optionalPhoto, s, progress);
                } finally {
                    inputSurface.unlockCanvasAndPost(surfaceCanvas);
                }
                if (callback != null) {
                    callback.onFrame(frame + 1, totalFrames);
                }
                int[] state = drainEncoder(encoder, muxer, info, trackIndex, muxerStarted, emittedFrames, false);
                trackIndex = state[0];
                muxerStarted = state[1] == 1;
                emittedFrames = state[2];
            }

            encoder.signalEndOfInputStream();
            int[] endState = drainEncoder(encoder, muxer, info, trackIndex, muxerStarted, emittedFrames, true);
            muxerStarted = endState[1] == 1;
        } finally {
            if (inputSurface != null) {
                inputSurface.release();
            }
            if (encoder != null) {
                try {
                    encoder.stop();
                } catch (Exception ignored) {
                }
                encoder.release();
            }
            if (muxer != null) {
                if (muxerStarted) {
                    try {
                        muxer.stop();
                    } catch (Exception ignored) {
                    }
                }
                muxer.release();
            }
        }
        if (!outFile.isFile() || outFile.length() < 1024L) {
            throw new IOException("MP4 encoder produced an empty file");
        }
        return outFile;
    }

    /**
     * Publishes an encoded offline MP4 directly into Android's Movies gallery (`Movies/Zoe Studio`).
     */
    static Uri saveVideoToGallery(Context ctx, File mp4File, String displayName) throws IOException {
        if (ctx == null || mp4File == null || !mp4File.isFile()) {
            throw new IOException("No rendered MP4 file to save");
        }
        ContentResolver resolver = ctx.getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.Video.Media.DISPLAY_NAME, displayName);
        values.put(MediaStore.Video.Media.MIME_TYPE, "video/mp4");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.put(MediaStore.Video.Media.RELATIVE_PATH, Environment.DIRECTORY_MOVIES + "/Zoe Studio");
            values.put(MediaStore.Video.Media.IS_PENDING, 1);
        }
        Uri uri = resolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values);
        if (uri == null) {
            throw new IOException("Could not create Movies gallery entry");
        }
        try (FileInputStream in = new FileInputStream(mp4File);
             OutputStream out = resolver.openOutputStream(uri)) {
            if (out == null) {
                throw new IOException("Could not open video stream");
            }
            byte[] buf = new byte[16_384];
            int n;
            while ((n = in.read(buf)) != -1) {
                out.write(buf, 0, n);
            }
            out.flush();
        } catch (IOException err) {
            resolver.delete(uri, null, null);
            throw err;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues done = new ContentValues();
            done.put(MediaStore.Video.Media.IS_PENDING, 0);
            resolver.update(uri, done, null, null);
        }
        return uri;
    }

    private static int[] drainEncoder(
            MediaCodec encoder,
            MediaMuxer muxer,
            MediaCodec.BufferInfo info,
            int trackIndex,
            boolean muxerStarted,
            int emittedFrames,
            boolean endOfStream) {
        int loops = 0;
        while (loops++ < 250) {
            int outIndex = encoder.dequeueOutputBuffer(info, endOfStream ? 15_000L : 2_000L);
            if (outIndex == MediaCodec.INFO_TRY_AGAIN_LATER) {
                if (!endOfStream) {
                    break;
                }
            } else if (outIndex == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                if (!muxerStarted) {
                    trackIndex = muxer.addTrack(encoder.getOutputFormat());
                    muxer.start();
                    muxerStarted = true;
                }
            } else if (outIndex >= 0) {
                ByteBuffer encoded = encoder.getOutputBuffer(outIndex);
                if (encoded != null && (info.flags & MediaCodec.BUFFER_FLAG_CODEC_CONFIG) == 0 && info.size > 0 && muxerStarted) {
                    encoded.position(info.offset);
                    encoded.limit(info.offset + info.size);
                    // Enforce exact monotonic CFR timestamps so video playback matches target duration exactly!
                    info.presentationTimeUs = framePresentationTimeUs(emittedFrames, FPS);
                    muxer.writeSampleData(trackIndex, encoded, info);
                    emittedFrames++;
                }
                encoder.releaseOutputBuffer(outIndex, false);
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                    break;
                }
            }
        }
        return new int[]{trackIndex, muxerStarted ? 1 : 0, emittedFrames};
    }

    private static int blendColor(int c1, int c2, float f, int alpha) {
        float clamped = Math.max(0f, Math.min(1f, f));
        int r = (int) (Color.red(c1) * (1f - clamped) + Color.red(c2) * clamped);
        int g = (int) (Color.green(c1) * (1f - clamped) + Color.green(c2) * clamped);
        int b = (int) (Color.blue(c1) * (1f - clamped) + Color.blue(c2) * clamped);
        return Color.argb(alpha, r, g, b);
    }
}
