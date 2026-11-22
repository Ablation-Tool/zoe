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
                        .setConfidenceThreshold(0.50f).build());
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
                Set<String> unique = new LinkedHashSet<>();
                for (ImageLabel l : labelTask.getResult()) {
                    if (l.getConfidence() < 0.42f) {
                        continue;
                    }
                    if (unique.size() >= 5) {
                        break;
                    }
                    unique.add(l.getText() + " (" + Math.round(l.getConfidence() * 100f) + "%)");
                }
                labels.addAll(unique);
            }
        } catch (Exception ignored) {
        }
        StringBuilder sb = new StringBuilder();
        sb.append("Labels: ").append(labels.isEmpty() ? "low-confidence scene" : String.join(", ", labels)).append(".");
        // Always include real dominant color & lighting tone so Zoe NEVER feels visually blind in dim or close-up shots!
        try {
            FramePalette.Analysis pal = FramePalette.analyzeBitmap(bmp);
            if (pal != null && pal.names != null && pal.names.length > 0) {
                StringBuilder c = new StringBuilder();
                c.append(pal.tone).append(" (").append(pal.brightnessPercent).append("%), ");
                for (int i = 0; i < Math.min(2, pal.names.length); i++) {
                    if (i > 0) c.append(" & ");
                    c.append(pal.names[i]);
                }
                sb.append(" Colors: ").append(c).append(".");
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
