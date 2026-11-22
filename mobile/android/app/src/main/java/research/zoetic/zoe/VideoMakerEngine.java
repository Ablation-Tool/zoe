package research.zoetic.zoe;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.media.MediaCodec;
import android.media.MediaCodecInfo;
import android.media.MediaFormat;
import android.media.MediaMuxer;
import android.view.Surface;

import java.io.File;
import java.io.IOException;
import java.nio.ByteBuffer;

/**
 * Zoe Native Offline Video Maker Engine (v0.6.0-beta).
 *
 * Encodes genuine H.264 `.mp4` videos 100% on-device via Android's built-in
 * `MediaCodec` (`video/avc`) + `MediaMuxer` with ZERO external libraries, ZERO cloud uploads,
 * and ZERO watermarks:
 *   - Chladni Resonance Music Video (animated physical standing-wave nodal interference)
 *   - Photo Story Reel (smooth Ken Burns zoom & pan over any Image Lab photo)
 *   - Starlight Pulse (luminous GEM orbital halo + captions)
 */
final class VideoMakerEngine {
    static final int WIDTH = 480;
    static final int HEIGHT = 480;
    static final int FPS = 20;
    static final int BITRATE = 1_800_000;

    enum Style {
        CHLADNI_RESONANCE("Chladni Wave"),
        PHOTO_STORY_REEL("Photo Story Reel"),
        STARLIGHT_PULSE("Starlight GEM");

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
            return Math.max(20, Math.min(240, durationSec * FPS));
        }
    }

    interface ProgressCallback {
        void onFrame(int frameIndex, int totalFrames);
    }

    private VideoMakerEngine() {
    }

    static void renderFrame(Canvas canvas, int w, int h, Bitmap optionalPhoto, Spec spec, float t) {
        Spec s = spec == null ? new Spec() : spec;
        canvas.drawColor(s.palette.bg);

        if (s.style == Style.PHOTO_STORY_REEL && optionalPhoto != null) {
            // Smooth Ken Burns zoom & gentle pan
            float zoom = 1.0f + 0.16f * t;
            int pw = optionalPhoto.getWidth();
            int ph = optionalPhoto.getHeight();
            int cropW = Math.max(16, (int) (pw / zoom));
            int cropH = Math.max(16, (int) (ph / zoom));
            int maxShiftX = Math.max(0, pw - cropW);
            int maxShiftY = Math.max(0, ph - cropH);
            int sx = (int) (maxShiftX * t);
            int sy = (int) (maxShiftY * 0.5f);
            Paint p = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
            canvas.drawBitmap(optionalPhoto, new Rect(sx, sy, sx + cropW, sy + cropH), new Rect(0, 0, w, h), p);

            Paint scrim = new Paint();
            scrim.setShader(new LinearGradient(0, h * 0.58f, 0, h,
                    Color.TRANSPARENT, Color.argb(215, 10, 13, 22), Shader.TileMode.CLAMP));
            canvas.drawRect(0, h * 0.58f, w, h, scrim);
        } else if (s.style == Style.CHLADNI_RESONANCE) {
            // Animated physical Chladni standing-wave interference cos(m*pi*x)*cos(n*pi*y) - cos(n*pi*x)*cos(m*pi*y)
            double phase = t * Math.PI * 2.0;
            double m = 2.0 + 2.5 * Math.sin(phase * 0.5);
            double n = 4.0 + 2.0 * Math.cos(phase * 0.5);
            Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
            int step = 8;
            for (int y = step / 2; y < h; y += step) {
                double ny = (double) y / h;
                for (int x = step / 2; x < w; x += step) {
                    double nx = (double) x / w;
                    double val = Math.cos(m * Math.PI * nx + phase * 0.3) * Math.cos(n * Math.PI * ny)
                            - Math.cos(n * Math.PI * nx) * Math.cos(m * Math.PI * ny - phase * 0.3);
                    double nodal = Math.max(0.0, 1.0 - Math.abs(val) * 3.4);
                    if (nodal > 0.18) {
                        int alpha = (int) Math.min(255, nodal * 240);
                        dot.setColor(blendColor(s.palette.primary, s.palette.secondary, (float) ((nx + ny) * 0.5), alpha));
                        canvas.drawCircle(x, y, (float) (1.6 + nodal * 2.8), dot);
                    }
                }
            }
        } else {
            // Starlight GEM expanding harmonic waves
            float cx = w * 0.5f;
            float cy = h * 0.44f;
            Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
            ring.setStyle(Paint.Style.STROKE);
            for (int i = 0; i < 9; i++) {
                float p = (t + i / 9.0f) % 1.0f;
                float r = 24f + p * (w * 0.48f);
                int alpha = (int) ((1.0f - p) * 210);
                ring.setStrokeWidth(3.5f * (1.0f - p) + 1.2f);
                ring.setColor(blendColor(s.palette.primary, s.palette.secondary, p, alpha));
                canvas.drawCircle(cx, cy, r, ring);
            }
            // Central glowing diamond
            Paint gem = new Paint(Paint.ANTI_ALIAS_FLAG);
            gem.setColor(s.palette.primary);
            android.graphics.Path diamond = new android.graphics.Path();
            float rad = 36f + (float) Math.sin(t * Math.PI * 4.0) * 6f;
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
        titlePaint.setTextSize(30f);
        titlePaint.setShadowLayer(8f, 0f, 2f, Color.argb(180, 0, 0, 0));

        Paint subPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        subPaint.setColor(Color.rgb(200, 214, 232));
        subPaint.setTypeface(Typeface.create("sans-serif", Typeface.NORMAL));
        subPaint.setTextAlign(Paint.Align.CENTER);
        subPaint.setTextSize(18f);

        String title = (s.title == null || s.title.trim().isEmpty()) ? "Made with Zoe" : s.title.trim();
        String sub = s.subtitle == null ? "" : s.subtitle.trim();
        canvas.drawText(title, w / 2f, h - 62f, titlePaint);
        if (!sub.isEmpty()) {
            canvas.drawText(sub, w / 2f, h - 32f, subPaint);
        }
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
                int[] state = drainEncoder(encoder, muxer, info, trackIndex, muxerStarted, false);
                trackIndex = state[0];
                muxerStarted = state[1] == 1;
            }

            encoder.signalEndOfInputStream();
            int[] endState = drainEncoder(encoder, muxer, info, trackIndex, muxerStarted, true);
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

    private static int[] drainEncoder(
            MediaCodec encoder,
            MediaMuxer muxer,
            MediaCodec.BufferInfo info,
            int trackIndex,
            boolean muxerStarted,
            boolean endOfStream) {
        int loops = 0;
        while (loops++ < 200) {
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
                    muxer.writeSampleData(trackIndex, encoded, info);
                }
                encoder.releaseOutputBuffer(outIndex, false);
                if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) {
                    break;
                }
            }
        }
        return new int[]{trackIndex, muxerStarted ? 1 : 0};
    }

    private static int blendColor(int c1, int c2, float f, int alpha) {
        float clamped = Math.max(0f, Math.min(1f, f));
        int r = (int) (Color.red(c1) * (1f - clamped) + Color.red(c2) * clamped);
        int g = (int) (Color.green(c1) * (1f - clamped) + Color.green(c2) * clamped);
        int b = (int) (Color.blue(c1) * (1f - clamped) + Color.blue(c2) * clamped);
        return Color.argb(alpha, r, g, b);
    }
}
