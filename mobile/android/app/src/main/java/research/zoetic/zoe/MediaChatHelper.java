package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.MediaMetadataRetriever;
import android.net.Uri;

import androidx.core.content.FileProvider;

import com.google.android.gms.tasks.Tasks;
import com.google.mlkit.vision.common.InputImage;
import com.google.mlkit.vision.label.ImageLabel;
import com.google.mlkit.vision.label.ImageLabeler;
import com.google.mlkit.vision.label.ImageLabeling;
import com.google.mlkit.vision.label.defaults.ImageLabelerOptions;
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognition;
import com.google.mlkit.vision.text.TextRecognizer;
import com.google.mlkit.vision.text.latin.TextRecognizerOptions;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.concurrent.TimeUnit;

/**
 * Multimodal Photo & Video Attachment Helper for Zoe Chat (v0.6.0-beta).
 *
 * Works BOTH offline and online:
 *   - Photos: downscales safely, extracts offline ML Kit OCR + image labels + dominant colors,
 *     and prepares compact JPEG bytes for optional Cloud Vision APIs.
 *   - Videos: uses native Android `MediaMetadataRetriever` to extract 3 evenly spaced key frames
 *     (15%, 50%, 85%), reads duration/dimensions, and runs offline ML Kit OCR + labeling across
 *     all 3 keyframes so Zoe can understand and discuss shared videos even 100% offline.
 */
final class MediaChatHelper {
    static final class MediaAttachment {
        final String kind;          // "photo" or "video"
        final String label;         // short display badge e.g. "Photo (800×600)" or "Video (12s · 3 frames)"
        final Bitmap thumbnail;
        final byte[] jpegBytes;
        final String offlineReport; // rich text description for Zoe Local 1.5B / Zoe Stem / Cloud prompt

        MediaAttachment(String kind, String label, Bitmap thumbnail, byte[] jpegBytes, String offlineReport) {
            this.kind = kind;
            this.label = label;
            this.thumbnail = thumbnail;
            this.jpegBytes = jpegBytes;
            this.offlineReport = offlineReport == null ? "" : offlineReport;
        }
    }

    private static final Object MLKIT_LOCK = new Object();
    private static TextRecognizer sharedTextRecognizer;
    private static ImageLabeler sharedImageLabeler;

    private MediaChatHelper() {
    }

    static TextRecognizer getSharedTextRecognizer() {
        synchronized (MLKIT_LOCK) {
            if (sharedTextRecognizer == null) {
                sharedTextRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
            }
            return sharedTextRecognizer;
        }
    }

    static ImageLabeler getSharedImageLabeler() {
        synchronized (MLKIT_LOCK) {
            if (sharedImageLabeler == null) {
                sharedImageLabeler = ImageLabeling.getClient(new ImageLabelerOptions.Builder()
                        .setConfidenceThreshold(0.52f).build());
            }
            return sharedImageLabeler;
        }
    }

    /** Pre-warms ML Kit OCR & ImageLabeler singletons silently off the UI thread so first frame is instant. */
    static void warmUp() {
        try {
            getSharedTextRecognizer();
            getSharedImageLabeler();
        } catch (Throwable ignored) {
        }
    }

    static Bitmap decodeScaledBitmap(Context ctx, Uri uri, int maxSide) throws IOException {
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        try (InputStream in = ctx.getContentResolver().openInputStream(uri)) {
            if (in == null) {
                throw new IOException("Could not open selected image");
            }
            BitmapFactory.decodeStream(in, null, bounds);
        }
        int sample = 1;
        int largest = Math.max(bounds.outWidth, bounds.outHeight);
        while (largest / sample > maxSide * 2) {
            sample *= 2;
        }
        BitmapFactory.Options opts = new BitmapFactory.Options();
        opts.inSampleSize = sample;
        Bitmap raw;
        try (InputStream in = ctx.getContentResolver().openInputStream(uri)) {
            if (in == null) {
                throw new IOException("Could not decode image");
            }
            raw = BitmapFactory.decodeStream(in, null, opts);
        }
        if (raw == null) {
            throw new IOException("Unsupported image format");
        }
        return scaleDown(raw, maxSide);
    }

    static Bitmap scaleDown(Bitmap src, int maxSide) {
        if (src == null) {
            return null;
        }
        int w = src.getWidth();
        int h = src.getHeight();
        int largest = Math.max(w, h);
        if (largest <= maxSide) {
            return src;
        }
        float ratio = (float) maxSide / largest;
        Bitmap scaled = Bitmap.createScaledBitmap(src, Math.max(1, Math.round(w * ratio)), Math.max(1, Math.round(h * ratio)), true);
        if (scaled != src) {
            src.recycle();
        }
        return scaled;
    }

    static byte[] bitmapToJpeg(Bitmap bmp, int quality) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        bmp.compress(Bitmap.CompressFormat.JPEG, quality, out);
        return out.toByteArray();
    }

    static MediaAttachment analyzePhotoUri(Context ctx, Uri uri) throws IOException {
        Bitmap bmp = decodeScaledBitmap(ctx, uri, 960);
        return analyzePhotoBitmap(bmp);
    }

    static MediaAttachment analyzePhotoBitmap(Bitmap bmp) {
        Bitmap scaled = scaleDown(bmp, 960);
        byte[] jpeg = bitmapToJpeg(scaled, 82);
        String visionSummary = inspectFrameOffline(scaled);
        int w = scaled.getWidth();
        int h = scaled.getHeight();
        String badge = "Photo (" + w + "×" + h + ")";
        String report = "Attached photo (" + w + "×" + h + ").\n"
                + "Offline visual inspection:\n" + visionSummary;
        int tw = Math.min(240, w);
        int th = Math.max(1, Math.round((float) h * tw / Math.max(1, w)));
        Bitmap thumb = Bitmap.createScaledBitmap(scaled, tw, th, true);
        if (scaled != thumb && !scaled.isRecycled()) {
            scaled.recycle();
        }
        return new MediaAttachment("photo", badge, thumb, jpeg, report);
    }

    static MediaAttachment analyzeVideoUri(Context ctx, Uri uri) throws IOException {
        MediaMetadataRetriever mmr = new MediaMetadataRetriever();
        try {
            mmr.setDataSource(ctx, uri);
            String durStr = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
            long durMs = 0L;
            if (durStr != null) {
                try {
                    durMs = Long.parseLong(durStr);
                } catch (NumberFormatException ignored) {
                }
            }
            long[] sampleUs = durMs > 1000L
                    ? new long[]{(long) (durMs * 150L), (long) (durMs * 500L), (long) (durMs * 850L)}
                    : new long[]{0L};

            StringBuilder timeline = new StringBuilder();
            timeline.append("Attached video (duration ").append(formatDurationMs(durMs))
                    .append(", ").append(sampleUs.length).append(" sampled keyframes).\n");
            Bitmap heroFrame = null;
            for (int i = 0; i < sampleUs.length; i++) {
                Bitmap frame = mmr.getFrameAtTime(sampleUs[i], MediaMetadataRetriever.OPTION_CLOSEST_SYNC);
                if (frame == null) {
                    continue;
                }
                Bitmap small = scaleDown(frame, 640);
                String obs = inspectFrameOffline(small);
                timeline.append("Frame ").append(i + 1).append(" [").append(formatDurationMs(sampleUs[i] / 1000L))
                        .append("]: ").append(obs).append("\n");
                if (heroFrame == null || i == 1) {
                    if (heroFrame != null && heroFrame != small && !heroFrame.isRecycled()) {
                        heroFrame.recycle();
                    }
                    heroFrame = small;
                } else if (!small.isRecycled()) {
                    small.recycle();
                }
            }
            if (heroFrame == null) {
                throw new IOException("Could not decode any video frame from the selected file");
            }
            byte[] jpeg = bitmapToJpeg(heroFrame, 82);
            int tw = Math.min(240, heroFrame.getWidth());
            int th = Math.max(1, Math.round((float) heroFrame.getHeight() * tw / Math.max(1, heroFrame.getWidth())));
            Bitmap thumb = Bitmap.createScaledBitmap(heroFrame, tw, th, true);
            if (heroFrame != thumb && !heroFrame.isRecycled()) {
                heroFrame.recycle();
            }
            String badge = "Video (" + formatDurationMs(durMs) + " · " + sampleUs.length + " frames)";
            return new MediaAttachment("video", badge, thumb, jpeg, timeline.toString().trim());
        } finally {
            try {
                mmr.release();
            } catch (Exception ignored) {
            }
        }
    }

    /**
     * Pure-Java aspect-ratio mapping from full-screen PreviewView (ScaleType.FILL_CENTER)
     * normalized tap coordinates (tapU, tapV in 0..1) into the underlying CameraX ImageAnalysis
     * upright bitmap coordinates + visible sensor fraction [sensorU, sensorV, visFracX, visFracY].
     *
     * Without this mapping, a 4:3 sensor (480x640) displayed on a tall 9:20 phone screen (1080x2400)
     * crops 20% off each horizontal side, offsetting off-center taps away from the tapped object!
     */
    static float[] mapFillCenterTapToFrame(float tapU, float tapV, int viewW, int viewH,
                                           int frameW, int frameH, boolean mirroredFront) {
        float u = Float.isFinite(tapU) ? Math.max(0f, Math.min(1f, tapU)) : 0.5f;
        float v = Float.isFinite(tapV) ? Math.max(0f, Math.min(1f, tapV)) : 0.5f;
        if (mirroredFront) {
            u = 1f - u;
        }
        float visFracX = 1f;
        float visFracY = 1f;
        if (viewW > 0 && viewH > 0 && frameW > 0 && frameH > 0) {
            float viewAspect = (float) viewW / (float) viewH;
            float frameAspect = (float) frameW / (float) frameH;
            if (frameAspect > viewAspect * 1.01f) {
                // Sensor is wider than screen -> FILL_CENTER crops left & right edges
                visFracX = Math.max(0.25f, Math.min(1f, viewAspect / frameAspect));
            } else if (viewAspect > frameAspect * 1.01f) {
                // Screen is wider than sensor -> FILL_CENTER crops top & bottom edges
                visFracY = Math.max(0.25f, Math.min(1f, frameAspect / viewAspect));
            }
        }
        float sensorU = (1f - visFracX) * 0.5f + u * visFracX;
        float sensorV = (1f - visFracY) * 0.5f + v * visFracY;
        return new float[]{sensorU, sensorV, visFracX, visFracY};
    }

    /**
     * Crops a zoomed Region-of-Interest centered around the exact PreviewView tap point (tapU, tapV in 0..1),
     * compensating for CameraX FILL_CENTER aspect-ratio cropping and front-camera mirroring!
     */
    static Bitmap cropTapRegion(Bitmap fullFrame, float tapU, float tapV,
                                int viewW, int viewH, boolean mirroredFront, float visibleCropFraction) {
        if (fullFrame == null || fullFrame.isRecycled()) {
            return null;
        }
        int w = fullFrame.getWidth();
        int h = fullFrame.getHeight();
        if (w < 64 || h < 64) {
            return fullFrame.copy(Bitmap.Config.ARGB_8888, false);
        }
        float[] mapped = mapFillCenterTapToFrame(tapU, tapV, viewW, viewH, w, h, mirroredFront);
        float frac = Math.max(0.32f, Math.min(0.85f, visibleCropFraction));
        // Keep crop reasonably square and >= 160px on each side so ML Kit & OCR have crisp detail!
        int cw = Math.max(Math.min(w, 160), Math.round(w * mapped[2] * frac));
        int ch = Math.max(Math.min(h, 160), Math.round(h * mapped[3] * frac));
        cw = Math.min(w, cw);
        ch = Math.min(h, ch);
        int left = Math.max(0, Math.min(w - cw, Math.round(mapped[0] * w - cw * 0.5f)));
        int top = Math.max(0, Math.min(h - ch, Math.round(mapped[1] * h - ch * 0.5f)));
        return Bitmap.createBitmap(fullFrame, left, top, cw, ch);
    }

    /**
     * Deduplicates color names from FramePalette buckets so Zoe never says "amber & amber".
     */
    static String formatDistinctColorNames(String[] names) {
        if (names == null || names.length == 0) {
            return "";
        }
        List<String> distinct = new ArrayList<>();
        Set<String> seenLower = new LinkedHashSet<>();
        for (String raw : names) {
            if (raw == null) continue;
            String trimmed = raw.trim();
            if (trimmed.isEmpty()) continue;
            String key = trimmed.toLowerCase(Locale.US);
            if (seenLower.add(key)) {
                distinct.add(trimmed);
                if (distinct.size() >= 2) {
                    break;
                }
            }
        }
        if (distinct.isEmpty()) return "";
        if (distinct.size() == 1) return distinct.get(0);
        return distinct.get(0) + " and " + distinct.get(1);
    }

    private static boolean isGenericTextureLabel(String text) {
        if (text == null) return true;
        String l = text.trim().toLowerCase(Locale.US);
        return l.equals("pattern") || l.equals("material property") || l.equals("symmetry")
                || l.equals("rectangle") || l.equals("circle") || l.equals("line") || l.equals("font");
    }

    /**
     * Production parallel ML Kit OCR + Image Labeling (~2x faster than sequential execution).
     */
    static String inspectFrameOffline(Bitmap bmp) {
        if (bmp == null || bmp.isRecycled()) {
            return "No frame available.";
        }
        InputImage img = InputImage.fromBitmap(bmp, 0);
        String ocrText = "";
        List<String> labels = new ArrayList<>();
        try {
            com.google.android.gms.tasks.Task<Text> textTask = getSharedTextRecognizer().process(img);
            com.google.android.gms.tasks.Task<List<ImageLabel>> labelTask = getSharedImageLabeler().process(img);
            Tasks.await(Tasks.whenAllComplete(textTask, labelTask), 2800L, TimeUnit.MILLISECONDS);
            if (textTask.isSuccessful() && textTask.getResult() != null && textTask.getResult().getText() != null) {
                ocrText = textTask.getResult().getText().replaceAll("\\s+", " ").trim();
                if (ocrText.length() > 220) {
                    ocrText = ocrText.substring(0, 220) + "…";
                }
            }
            if (labelTask.isSuccessful() && labelTask.getResult() != null) {
                List<String> concrete = new ArrayList<>();
                List<String> generic = new ArrayList<>();
                Set<String> seen = new LinkedHashSet<>();
                for (ImageLabel l : labelTask.getResult()) {
                    if (l.getConfidence() < 0.52f) {
                        continue;
                    }
                    String name = l.getText() == null ? "" : l.getText().trim();
                    if (name.isEmpty() || !seen.add(name.toLowerCase(Locale.US))) {
                        continue;
                    }
                    String formatted = name + " (" + Math.round(l.getConfidence() * 100f) + "%)";
                    if (isGenericTextureLabel(name)) {
                        generic.add(formatted);
                    } else {
                        concrete.add(formatted);
                    }
                }
                for (String c : concrete) {
                    if (labels.size() >= 5) break;
                    labels.add(c);
                }
                for (String g : generic) {
                    if (labels.size() >= 5) break;
                    labels.add(g);
                }
            }
        } catch (Exception ignored) {
        }
        StringBuilder sb = new StringBuilder();
        sb.append("Labels: ").append(labels.isEmpty() ? "low-confidence scene" : String.join(", ", labels)).append(".");
        // Always include real dominant color & lighting tone so Zoe NEVER feels visually blind in dim or close-up shots!
        try {
            FramePalette.Analysis pal = FramePalette.analyzeBitmap(bmp);
            if (pal != null && pal.names != null && pal.names.length > 0) {
                String colorNames = formatDistinctColorNames(pal.names);
                if (!colorNames.isEmpty()) {
                    sb.append(" Colors: ").append(pal.tone).append(", ").append(colorNames).append(".");
                } else {
                    sb.append(" Colors: ").append(pal.tone).append(".");
                }
            }
        } catch (Throwable ignored) {
        }
        if (!ocrText.isEmpty()) {
            sb.append(" Visible text: \"").append(ocrText).append("\".");
        }
        return sb.toString();
    }

    static String formatDurationMs(long ms) {
        long sec = Math.max(0L, ms / 1000L);
        long m = sec / 60L;
        long s = sec % 60L;
        return m > 0 ? String.format(Locale.US, "%d:%02d", m, s) : (s + "s");
    }

    static Uri savePngForShare(Context ctx, Bitmap bmp, String filename) throws IOException {
        File dir = new File(ctx.getCacheDir(), "creative_studio");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("Could not create creative_studio cache folder");
        }
        File file = new File(dir, filename);
        try (FileOutputStream out = new FileOutputStream(file)) {
            bmp.compress(Bitmap.CompressFormat.PNG, 100, out);
            out.flush();
        }
        return FileProvider.getUriForFile(ctx, ctx.getPackageName() + ".fileprovider", file);
    }

    static Uri shareUriForFile(Context ctx, File file) {
        return FileProvider.getUriForFile(ctx, ctx.getPackageName() + ".fileprovider", file);
    }
}
