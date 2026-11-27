package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.DocumentsContract;
import android.provider.MediaStore;

import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * User-Controlled Guided Vision & Zoe Explore Learning Pipeline ("Zoe Learn").
 *
 * Honors CONSTITUTION.md Articles I, IV & VI:
 *   - Transparent destination choice: Ask Each Shot (default) · Instant Digest to Zoe ·
 *     Device `Pictures/Zoe Learn` folder · Google Drive `Zoe Learn` folder (via Android SAF).
 *   - Never uploads raw photos covertly; Workstation `/api/digest/mobile` always enforces
 *     `MobileDigestionBundle` privacy firewall (compact geometric signatures only).
 *   - Pure JVM-testable helpers for filename sanitization, live voice-teach parsing, and
 *     Zoe Explore Curiosity Quests.
 */
final class ZoeLearnQueue {
    static final String GOOGLE_DRIVE_PACKAGE = "com.google.android.apps.docs";
    static final String DEVICE_FOLDER_NAME = "Zoe Learn";

    private static final String PREFS = "zoe_learn_queue_v1";
    private static final String KEY_DEST = "learn_destination";
    private static final String KEY_DRIVE_TREE_URI = "drive_tree_uri";
    private static final String KEY_QUEUED_COUNT = "queued_count";
    private static final String KEY_DIGESTED_COUNT = "digested_count";

    private static final Pattern TEACH_RE = Pattern.compile(
            "^(?:hey\\s+zoe[,\\s]+|zoe[,\\s]+)?(?:please\\s+)?"
                    + "(?:(?:learn|teach(?:\\s+zoe)?|save)\\s+(?:this|that|it)\\s+(?:as|is)\\s+"
                    + "|remember\\s+(?:this|that)\\s+(?:is|as)\\s+"
                    + "|(?:this|that)\\s+is\\s+(?:called|named)\\s+)(.+)$",
            Pattern.CASE_INSENSITIVE);

    private static final String[] CURIOSITY_QUESTS = new String[]{
            "Let's play Light & Focus! Point me at something with crisp texture or lettering, and I'll read its light contrast and remember its shape.",
            "Pattern Hunt! Find a repeating geometric shape, spiral, or plant leaf near you and tap look now so we can inspect its contour.",
            "Teach Me Something New! Hold up your favorite everyday tool or object on your desk and say \"learn this as\" followed by its name.",
            "Color Palette Quest! Aim at the most colorful corner in the room so we can measure its dominant hex colors and light warmth.",
            "Micro-Detail Mission! Bring a book cover, circuit board, or label close and ask me what it says, then ask follow-up questions live!",
            "Acoustic Echo Check! Open tools and tap echo ping to hear how sound bounces off the nearest wall or open doorway around you."
    };

    enum Destination {
        ASK("ask", "Auto-Learn: Ask", "Choose after each capture"),
        INSTANT_DIGEST("instant", "Auto-Learn: Instant Zoe", "Teach & digest immediately"),
        DEVICE_FOLDER("device", "Auto-Learn: Device", "Save to Pictures/Zoe Learn"),
        GOOGLE_DRIVE("drive", "Auto-Learn: Drive", "Save to Drive · Zoe Learn");

        final String id;
        final String shortLabel;
        final String helper;

        Destination(String id, String shortLabel, String helper) {
            this.id = id;
            this.shortLabel = shortLabel;
            this.helper = helper;
        }

        Destination next() {
            Destination[] all = values();
            return all[(ordinal() + 1) % all.length];
        }

        static Destination fromId(String id) {
            if (id == null) {
                return ASK;
            }
            for (Destination d : values()) {
                if (d.id.equalsIgnoreCase(id.trim())) {
                    return d;
                }
            }
            return ASK;
        }
    }

    private ZoeLearnQueue() {
    }

    private static SharedPreferences prefs(Context ctx) {
        return ctx.getApplicationContext().getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    static Destination savedDestination(Context ctx) {
        if (ctx == null) {
            return Destination.ASK;
        }
        return Destination.fromId(prefs(ctx).getString(KEY_DEST, Destination.ASK.id));
    }

    static void saveDestination(Context ctx, Destination dest) {
        if (ctx != null && dest != null) {
            prefs(ctx).edit().putString(KEY_DEST, dest.id).apply();
        }
    }

    static Uri savedDriveTreeUri(Context ctx) {
        if (ctx == null) {
            return null;
        }
        String raw = prefs(ctx).getString(KEY_DRIVE_TREE_URI, "").trim();
        return raw.isEmpty() ? null : Uri.parse(raw);
    }

    static void saveDriveTreeUri(Context ctx, Uri uri) {
        if (ctx == null) {
            return;
        }
        prefs(ctx).edit().putString(KEY_DRIVE_TREE_URI, uri == null ? "" : uri.toString()).apply();
    }

    static int queuedCount(Context ctx) {
        return ctx == null ? 0 : prefs(ctx).getInt(KEY_QUEUED_COUNT, 0);
    }

    static int incrementQueuedCount(Context ctx) {
        if (ctx == null) {
            return 0;
        }
        int next = queuedCount(ctx) + 1;
        prefs(ctx).edit().putInt(KEY_QUEUED_COUNT, next).apply();
        return next;
    }

    static int digestedCount(Context ctx) {
        return ctx == null ? 0 : prefs(ctx).getInt(KEY_DIGESTED_COUNT, 0);
    }

    static int incrementDigestedCount(Context ctx) {
        if (ctx == null) {
            return 0;
        }
        int next = digestedCount(ctx) + 1;
        prefs(ctx).edit().putInt(KEY_DIGESTED_COUNT, next).apply();
        return next;
    }

    /** Pure JVM-testable filename sanitizer for saved Zoe Learn captures. */
    static String sanitizeSlug(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return "capture";
        }
        String cleaned = raw.trim().toLowerCase(Locale.US)
                .replaceAll("[^a-z0-9]+", "_")
                .replaceAll("^_+|_+$", "");
        if (cleaned.isEmpty()) {
            return "capture";
        }
        return cleaned.length() > 28 ? cleaned.substring(0, 28) : cleaned;
    }

    static String buildCaptureFileName(String label, long epochMs) {
        String stamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.US).format(new Date(epochMs));
        return "ZoeLearn_" + stamp + "_" + sanitizeSlug(label) + ".jpg";
    }

    /**
     * Pure JVM-testable parser for live voice teaching in Zoe Explore.
     * Examples: "learn this as a prism lens", "remember this is my coffee mug", "teach zoe this is a caliper".
     */
    static String parseLiveTeachLabel(String spoken) {
        if (spoken == null || spoken.trim().isEmpty()) {
            return "";
        }
        Matcher m = TEACH_RE.matcher(spoken.trim());
        if (!m.matches()) {
            return "";
        }
        String candidate = m.group(1) == null ? "" : m.group(1).trim();
        candidate = candidate.replaceAll("[.!?]+$", "").trim();
        candidate = candidate.replaceFirst("^(?i)(?:a|an|the|my|our)\\s+", "").trim();
        return VisionPriorStore.cleanLabel(candidate);
    }

    /** Returns a playful, real-world curiosity quest prompt for Zoe Explore. */
    static String curiosityQuest(int index) {
        int safe = Math.floorMod(index, CURIOSITY_QUESTS.length);
        return CURIOSITY_QUESTS[safe];
    }

    /**
     * Saves the inspected frame cleanly to the user's on-device `Pictures/Zoe Learn` folder
     * via Android MediaStore (zero legacy storage permissions needed on Android 10+).
     */
    static String saveToDeviceZoeLearn(Context ctx, byte[] jpegBytes, String label) throws IOException {
        if (ctx == null || jpegBytes == null || jpegBytes.length == 0) {
            throw new IOException("No image bytes available to save.");
        }
        String fileName = buildCaptureFileName(label, System.currentTimeMillis());
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues cv = new ContentValues();
            cv.put(MediaStore.Images.Media.DISPLAY_NAME, fileName);
            cv.put(MediaStore.Images.Media.MIME_TYPE, "image/jpeg");
            cv.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/" + DEVICE_FOLDER_NAME);
            cv.put(MediaStore.Images.Media.IS_PENDING, 1);
            ContentResolver cr = ctx.getContentResolver();
            Uri uri = cr.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, cv);
            if (uri == null) {
                throw new IOException("Could not create MediaStore entry in Pictures/" + DEVICE_FOLDER_NAME);
            }
            try (OutputStream out = cr.openOutputStream(uri)) {
                if (out == null) {
                    throw new IOException("Could not open output stream for Pictures/" + DEVICE_FOLDER_NAME);
                }
                out.write(jpegBytes);
            }
            ContentValues done = new ContentValues();
            done.put(MediaStore.Images.Media.IS_PENDING, 0);
            cr.update(uri, done, null, null);
            incrementQueuedCount(ctx);
            return "Pictures/" + DEVICE_FOLDER_NAME + "/" + fileName;
        }
        File dir = new File(ctx.getFilesDir(), "zoe_learn");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("Could not create local zoe_learn folder");
        }
        File file = new File(dir, fileName);
        try (FileOutputStream fos = new FileOutputStream(file)) {
            fos.write(jpegBytes);
        }
        incrementQueuedCount(ctx);
        return "zoe_learn/" + fileName;
    }

    /**
     * Writes an inspected frame straight into the user's chosen SAF folder (e.g., Google Drive -> Zoe Learn)
     * using pure Android DocumentsContract with zero third-party OAuth SDK dependencies.
     */
    static String saveToPickedTreeFolder(Context ctx, Uri treeUri, byte[] jpegBytes, String label) throws IOException {
        if (ctx == null || treeUri == null || jpegBytes == null || jpegBytes.length == 0) {
            throw new IOException("No Google Drive folder linked yet.");
        }
        String fileName = buildCaptureFileName(label, System.currentTimeMillis());
        ContentResolver cr = ctx.getContentResolver();
        String treeDocId = DocumentsContract.getTreeDocumentId(treeUri);
        Uri parentDocUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, treeDocId);
        Uri created = DocumentsContract.createDocument(cr, parentDocUri, "image/jpeg", fileName);
        if (created == null) {
            throw new IOException("Could not create file in chosen Drive/SAF folder.");
        }
        try (OutputStream out = cr.openOutputStream(created)) {
            if (out == null) {
                throw new IOException("Could not write to chosen Drive/SAF folder.");
            }
            out.write(jpegBytes);
        }
        incrementQueuedCount(ctx);
        return fileName;
    }

    /** Creates a FileProvider URI in cache/trip_share for zero-boilerplate native System Camera capture. */
    static Uri createTempCaptureUri(Context ctx, String prefix, String extension) throws IOException {
        File dir = new File(ctx.getCacheDir(), "trip_share");
        if (!dir.exists() && !dir.mkdirs()) {
            throw new IOException("Could not create camera capture cache folder.");
        }
        String safePrefix = sanitizeSlug(prefix);
        String ext = extension == null || extension.isEmpty() ? "jpg" : extension.replace(".", "");
        File file = new File(dir, safePrefix + "_" + System.currentTimeMillis() + "." + ext);
        return FileProvider.getUriForFile(ctx, ctx.getPackageName() + ".fileprovider", file);
    }

    /** Opens Google Drive (or Android share sheet) to save a Guided Vision frame into Drive -> Zoe Learn. */
    static boolean shareToGoogleDrive(Context ctx, byte[] jpegBytes, String label, String summary) {
        if (ctx == null || jpegBytes == null || jpegBytes.length == 0) {
            return false;
        }
        try {
            File dir = new File(ctx.getCacheDir(), "trip_share");
            if (!dir.exists()) {
                dir.mkdirs();
            }
            File file = new File(dir, buildCaptureFileName(label, System.currentTimeMillis()));
            try (FileOutputStream fos = new FileOutputStream(file)) {
                fos.write(jpegBytes);
            }
            Uri uri = FileProvider.getUriForFile(ctx, ctx.getPackageName() + ".fileprovider", file);
            Intent driveIntent = new Intent(Intent.ACTION_SEND)
                    .setType("image/jpeg")
                    .setPackage(GOOGLE_DRIVE_PACKAGE)
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_SUBJECT, "Zoe Learn · " + sanitizeSlug(label))
                    .putExtra(Intent.EXTRA_TEXT, summary == null ? "" : summary)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            try {
                ctx.startActivity(driveIntent);
                return true;
            } catch (ActivityNotFoundException noDrive) {
                Intent chooser = new Intent(Intent.ACTION_SEND)
                        .setType("image/jpeg")
                        .putExtra(Intent.EXTRA_STREAM, uri)
                        .putExtra(Intent.EXTRA_SUBJECT, "Zoe Learn · " + sanitizeSlug(label))
                        .putExtra(Intent.EXTRA_TEXT, summary == null ? "" : summary)
                        .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                ctx.startActivity(Intent.createChooser(chooser, "Save to Google Drive (Zoe Learn)"));
                return true;
            }
        } catch (IOException | ActivityNotFoundException error) {
            return false;
        }
    }
}
