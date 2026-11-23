package research.zoetic.zoe;

import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.core.content.FileProvider;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Guided Vision: seamless native phone camera integration with symmetrical color-coded cards.
 *
 * Launches the phone's own built-in Camera app (TakePicture / CaptureVideo) or Gallery directly
 * so all pre-configured zoom, macro, HDR+, flash, and night sight settings stay intact, then
 * organizes Zoe's observations into a balanced 2x2 color-coded grid.
 */
final class GuidedVisionView extends ScrollView {
    private static final int ACCENT_MEMORY = Color.rgb(244, 114, 146); // ruby rose
    private static final int ACCENT_TEXT = Color.rgb(124, 180, 255);   // cobalt blue
    private static final int ACCENT_LABELS = Color.rgb(94, 234, 212);  // emerald mint
    private static final int ACCENT_LIGHT = Color.rgb(247, 201, 110);  // amber gold
    private static final int ACCENT_DEEP = Color.rgb(92, 225, 230);    // bright cyan

    private final MainActivity activity;
    private final ElizaGemClient studioClient = new ElizaGemClient();
    private final ImageView mediaPreview;
    private final LinearLayout emptyCameraPrompt;
    private final TextView status;

    private final TextView emptyHintView;
    private final LinearLayout deepInspectCard;
    private final TextView deepInspectBody;
    private final LinearLayout observationGrid;
    private final TextView memoryCardBody;
    private final TextView textCardBody;
    private final TextView labelsCardBody;
    private final TextView lightCardBody;
    private final LinearLayout lightSwatchRow;
    private final TextView privacyFootNote;

    private final Button askZoeButton;
    private final LinearLayout learnBar;
    private final Button digestZoeButton;
    private final Button saveLearnDeviceButton;
    private final Button saveLearnDriveButton;
    private final Button autoSpeakButton;
    private final Button autoLearnButton;
    private final Button pickDriveFolderButton;
    private final Button teachObjectButton;
    private final Button patentPriorButton;
    private final Button memoryBadgeButton;
    private final Button saveJournalButton;
    private final Button sharePhotoButton;
    private final Button cloudAskButton;
    private final LinearLayout moreOptionsDrawer;
    private final Button moreOptionsToggle;
    private final ExecutorService analysisExecutor;

    private DeviceAiController deviceAi;
    private boolean autoSpeak;
    private String lastOcr = "";
    private String lastLabels = "";
    private String lastJudgeReport = "";
    private String lastPaletteSummary = "";
    private FramePalette.Analysis lastPaletteAnalysis;
    private String lastDeviceAi = "";
    private String lastCloud = "";
    private String lastStructuralNote = "";
    private PatentReverseImageEngine.VisualSignature lastVisualSignature;
    private VisionPriorStore.MatchResult lastPriorMatch;
    private byte[] lastFrameJpeg;
    private String spoken = "no photo yet. tap take photo, record video, or gallery";
    private String shared = spoken;

    GuidedVisionView(MainActivity activity) {
        super(activity);
        this.activity = activity;
        setFillViewport(true);
        setBackgroundColor(Color.TRANSPARENT);

        LinearLayout content = Ui.vertical(activity);
        content.setBackgroundColor(Color.TRANSPARENT);
        content.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 8), Ui.dp(activity, 16), Ui.dp(activity, 24));
        addView(content);

        analysisExecutor = Executors.newSingleThreadExecutor();
        analysisExecutor.execute(() -> {
            MediaChatHelper.warmUp();
            VisionPriorStore.loadAll(activity);
            VisionPriorStore.loadBaselineAtlas(activity);
        });
        if (DeviceAiController.hasRealAiCoreService(activity)) {
            ensureDeviceAi().autoPrepareQuietly();
        }

        // 1. Clean Seamless Camera Preview Card (1 tap launches your phone's perfected built-in Camera)
        FrameLayout previewFrame = new FrameLayout(activity);
        previewFrame.setBackground(Ui.cardBackground(activity, 24));
        previewFrame.setClipToOutline(true);
        previewFrame.setClickable(true);
        previewFrame.setFocusable(true);
        previewFrame.setContentDescription("Open your phone's camera to take a photo for Zoe");
        previewFrame.setOnClickListener(Ui.withHaptic(v -> activity.launchSystemCameraPhoto()));

        mediaPreview = new ImageView(activity);
        mediaPreview.setScaleType(ImageView.ScaleType.CENTER_CROP);
        mediaPreview.setVisibility(GONE);
        mediaPreview.setContentDescription("Captured photo preview");
        previewFrame.addView(mediaPreview, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        emptyCameraPrompt = Ui.vertical(activity);
        emptyCameraPrompt.setBackgroundColor(Color.TRANSPARENT);
        emptyCameraPrompt.setGravity(Gravity.CENTER);
        emptyCameraPrompt.setPadding(Ui.dp(activity, 24), Ui.dp(activity, 20), Ui.dp(activity, 24), Ui.dp(activity, 20));
        ImageView gemIcon = Ui.zoeSparkIcon(activity, 56);
        LinearLayout.LayoutParams gemLp = new LinearLayout.LayoutParams(Ui.dp(activity, 58), Ui.dp(activity, 58));
        gemLp.setMargins(0, 0, 0, Ui.dp(activity, 12));
        emptyCameraPrompt.addView(gemIcon, gemLp);

        TextView heroPrompt = Ui.text(activity, "tap to open your camera", 17f, Ui.TEXT);
        heroPrompt.setTypeface(Ui.SANS_MEDIUM);
        heroPrompt.setGravity(Gravity.CENTER);
        emptyCameraPrompt.addView(heroPrompt);

        TextView heroHint = Ui.text(activity,
                "uses your phone's built-in camera with all your zoom, macro & hdr settings",
                13f, Ui.MUTED);
        heroHint.setGravity(Gravity.CENTER);
        heroHint.setPadding(0, Ui.dp(activity, 6), 0, 0);
        emptyCameraPrompt.addView(heroHint);

        previewFrame.addView(emptyCameraPrompt, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));

        LinearLayout.LayoutParams camLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(activity, 232));
        camLp.setMargins(0, 0, 0, Ui.dp(activity, 10));
        content.addView(previewFrame, camLp);

        // 2. Direct 1-Tap Native Camera & Gallery Actions (zero popup menus)
        Button takePhotoBtn = Ui.primaryButton(activity, "take photo", Ui.COBALT,
                v -> activity.launchSystemCameraPhoto());
        takePhotoBtn.setId(R.id.start_camera);
        takePhotoBtn.setContentDescription("Take a photo using your phone's built-in camera");

        Button recordVideoBtn = Ui.button(activity, "record video", Ui.CYAN,
                v -> activity.launchSystemCameraVideo());
        recordVideoBtn.setId(R.id.inspect_button);
        recordVideoBtn.setContentDescription("Record a video using your phone's built-in camera");

        Button galleryBtn = Ui.button(activity, "gallery", Ui.GOLD,
                v -> activity.pickVisionMedia());
        galleryBtn.setId(R.id.vision_gallery_button);
        galleryBtn.setContentDescription("Pick a photo or video from your gallery");

        content.addView(Ui.buttonRow(activity, takePhotoBtn, recordVideoBtn, galleryBtn));

        // 3. Clean Voice & Accessibility Row
        Button listen = Ui.button(activity, "voice", Ui.CYAN, view -> activity.startListening());
        listen.setId(R.id.listen_button);
        Button speak = Ui.button(activity, "speak", Ui.PINK, view -> activity.repeatCurrent());
        speak.setId(R.id.speak_button);
        Button stop = Ui.button(activity, "stop", Ui.RUBY, view -> activity.stopAllOutput());
        stop.setId(R.id.stop_button);
        content.addView(Ui.buttonRow(activity, listen, speak, stop));

        status = Ui.statusBanner(activity, "ready · tap take photo, record video, or gallery", Ui.COBALT);
        status.setId(R.id.vision_status);
        content.addView(status);

        // 4. Calm Empty State Hint (replaced by symmetrical 2x2 color-coded grid once media is inspected)
        emptyHintView = Ui.text(activity,
                "take a photo, record a video, or pick from gallery to see memory, text, labels, and light organized clearly",
                13.5f, Ui.MUTED);
        emptyHintView.setGravity(Gravity.CENTER);
        emptyHintView.setPadding(Ui.dp(activity, 14), Ui.dp(activity, 12), Ui.dp(activity, 14), Ui.dp(activity, 12));
        content.addView(emptyHintView);

        // Optional Full-Width Deep Inspect Card (cyan accent)
        deepInspectCard = buildCategoryCard("deep inspect", ACCENT_DEEP);
        deepInspectBody = buildCategoryBody("");
        deepInspectCard.addView(deepInspectBody);
        deepInspectCard.setVisibility(GONE);
        LinearLayout.LayoutParams deepLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        deepLp.setMargins(0, Ui.dp(activity, 6), 0, Ui.dp(activity, 8));
        content.addView(deepInspectCard, deepLp);

        // 5. Symmetrical 2x2 Color-Coded Category Grid (distinct visual anchor for every category)
        observationGrid = Ui.vertical(activity);
        observationGrid.setId(R.id.vision_palette);
        observationGrid.setBackgroundColor(Color.TRANSPARENT);
        observationGrid.setVisibility(GONE);

        int gap = Ui.dp(activity, 8);

        // Top Row: [ visual memory (rose) ]  |  [ text (blue) ]
        LinearLayout row1 = new LinearLayout(activity);
        row1.setOrientation(LinearLayout.HORIZONTAL);
        row1.setBaselineAligned(false);

        LinearLayout memoryCard = buildCategoryCard("visual memory", ACCENT_MEMORY);
        memoryCardBody = buildCategoryBody("no match yet");
        memoryCard.addView(memoryCardBody);

        LinearLayout textCard = buildCategoryCard("text", ACCENT_TEXT);
        textCardBody = buildCategoryBody("none found");
        textCard.addView(textCardBody);

        LinearLayout.LayoutParams leftLp1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        leftLp1.setMargins(0, 0, gap / 2, 0);
        LinearLayout.LayoutParams rightLp1 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        rightLp1.setMargins(gap / 2, 0, 0, 0);
        row1.addView(memoryCard, leftLp1);
        row1.addView(textCard, rightLp1);
        LinearLayout.LayoutParams row1Lp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        row1Lp.setMargins(0, Ui.dp(activity, 6), 0, gap);
        observationGrid.addView(row1, row1Lp);

        // Bottom Row: [ labels (mint) ]  |  [ light & color (gold) ]
        LinearLayout row2 = new LinearLayout(activity);
        row2.setOrientation(LinearLayout.HORIZONTAL);
        row2.setBaselineAligned(false);

        LinearLayout labelsCard = buildCategoryCard("labels", ACCENT_LABELS);
        labelsCardBody = buildCategoryBody("none found");
        labelsCard.addView(labelsCardBody);

        LinearLayout lightCard = buildCategoryCard("light & color", ACCENT_LIGHT);
        lightCardBody = buildCategoryBody("");
        lightCard.addView(lightCardBody);
        lightSwatchRow = new LinearLayout(activity);
        lightSwatchRow.setOrientation(LinearLayout.HORIZONTAL);
        lightSwatchRow.setPadding(0, Ui.dp(activity, 8), 0, 0);
        lightCard.addView(lightSwatchRow);

        LinearLayout.LayoutParams leftLp2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        leftLp2.setMargins(0, 0, gap / 2, 0);
        LinearLayout.LayoutParams rightLp2 = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.MATCH_PARENT, 1f);
        rightLp2.setMargins(gap / 2, 0, 0, 0);
        row2.addView(labelsCard, leftLp2);
        row2.addView(lightCard, rightLp2);
        observationGrid.addView(row2, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        privacyFootNote = Ui.text(activity, "observations only. nothing is saved until you choose", 12f, Ui.MUTED);
        privacyFootNote.setGravity(Gravity.CENTER);
        privacyFootNote.setPadding(0, Ui.dp(activity, 8), 0, Ui.dp(activity, 4));
        observationGrid.addView(privacyFootNote);

        content.addView(observationGrid);

        askZoeButton = Ui.primaryButton(activity, "ask zoe about this", Ui.COBALT, view -> openChatWithObservation());
        askZoeButton.setVisibility(GONE);
        content.addView(askZoeButton, Ui.margins(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, activity, 4));

        // 6. Streamlined "Zoe Learn" Destination Bar (appears after capture)
        learnBar = Ui.vertical(activity);
        learnBar.setBackgroundColor(Color.TRANSPARENT);
        learnBar.setVisibility(GONE);
        digestZoeButton = Ui.button(activity, "digest to zoe", Ui.GREEN, view -> digestCurrentFrameToZoe(false));
        saveLearnDeviceButton = Ui.button(activity, "save to device", Ui.CYAN, view -> saveCurrentFrameToDeviceLearn(false));
        saveLearnDriveButton = Ui.button(activity, "google drive", Ui.GOLD, view -> saveCurrentFrameToDriveLearn(false));
        learnBar.addView(Ui.buttonRow(activity, digestZoeButton, saveLearnDeviceButton, saveLearnDriveButton));
        content.addView(learnBar);

        // 7. Single Collapsible "more options" Drawer (zero main-screen clutter)
        moreOptionsDrawer = Ui.vertical(activity);
        moreOptionsDrawer.setBackgroundColor(Color.TRANSPARENT);
        moreOptionsDrawer.setVisibility(GONE);

        teachObjectButton = Ui.button(activity, "teach zoe", Ui.GREEN, view -> promptTeachObject());
        teachObjectButton.setId(R.id.vision_teach_button);
        teachObjectButton.setEnabled(false);

        patentPriorButton = Ui.button(activity, "patent prior", Ui.COBALT, view -> runSilentPatentPrior());
        patentPriorButton.setId(R.id.vision_patent_prior_button);
        patentPriorButton.setEnabled(false);

        memoryBadgeButton = Ui.button(activity, "memory: " + VisionPriorStore.learnedCount(activity),
                Ui.GOLD, view -> showLearnedMemoryDialog());
        memoryBadgeButton.setId(R.id.vision_memory_badge);
        moreOptionsDrawer.addView(Ui.buttonRow(activity, teachObjectButton, patentPriorButton, memoryBadgeButton));

        autoSpeakButton = Ui.button(activity, "auto-speak: off", Ui.PINK, view -> toggleAutoSpeak());
        autoSpeakButton.setId(R.id.vision_autospeak);
        autoLearnButton = Ui.button(activity,
                ZoeLearnQueue.savedDestination(activity).shortLabel.toLowerCase(Locale.US),
                Ui.GREEN, view -> cycleAutoLearn());
        pickDriveFolderButton = Ui.button(activity,
                ZoeLearnQueue.savedDriveTreeUri(activity) != null ? "drive: linked" : "pick drive folder",
                Ui.COBALT, view -> activity.pickZoeLearnDriveFolder());
        moreOptionsDrawer.addView(Ui.buttonRow(activity, autoSpeakButton, autoLearnButton, pickDriveFolderButton));

        saveJournalButton = Ui.button(activity, "save journal", Ui.GREEN, view -> promptSaveToJournal());
        saveJournalButton.setId(R.id.vision_save_journal);
        saveJournalButton.setEnabled(false);
        sharePhotoButton = Ui.button(activity, "share photo", Ui.GOLD, view -> sharePhotoWithApps());
        sharePhotoButton.setId(R.id.vision_share_photo);
        sharePhotoButton.setEnabled(false);
        cloudAskButton = Ui.button(activity, "deep inspect", Ui.CYAN, view -> askCloudVision());
        cloudAskButton.setId(R.id.vision_cloud_ask);
        cloudAskButton.setEnabled(false);
        moreOptionsDrawer.addView(Ui.buttonRow(activity, saveJournalButton, sharePhotoButton, cloudAskButton));

        Button shareTextBtn = Ui.button(activity, "share text", Ui.PINK, view -> activity.shareCurrent());
        shareTextBtn.setId(R.id.share_button);
        Button liveExploreBtn = Ui.button(activity, "zoe explore", Ui.CYAN, view -> activity.openLiveExplore());
        moreOptionsDrawer.addView(Ui.buttonRow(activity, shareTextBtn, liveExploreBtn));

        if (DeviceAiController.hasRealAiCoreService(activity)) {
            moreOptionsDrawer.addView(Ui.buttonRow(activity,
                    Ui.button(activity, "check device ai", Ui.CYAN, view -> ensureDeviceAi().check()),
                    Ui.button(activity, "enable ai model", Ui.CYAN, view -> ensureDeviceAi().enable())));
        }

        moreOptionsToggle = Ui.disclosureButton(activity, "more options ▾", null);
        moreOptionsToggle.setId(R.id.vision_improve_toggle);
        moreOptionsToggle.setOnClickListener(view -> {
            boolean open = moreOptionsDrawer.getVisibility() != VISIBLE;
            moreOptionsDrawer.setVisibility(open ? VISIBLE : GONE);
            moreOptionsToggle.setText(open ? "more options ▴" : "more options ▾");
        });
        content.addView(moreOptionsToggle);
        content.addView(moreOptionsDrawer);
    }

    /** Creates one cleanly color-coded, rounded category card with a crisp colored badge dot + title. */
    private LinearLayout buildCategoryCard(String title, int accentColor) {
        boolean dark = Ui.isDark(activity);
        int fillColor = dark
                ? Color.argb(235,
                        Math.min(255, 20 + Color.red(accentColor) / 14),
                        Math.min(255, 22 + Color.green(accentColor) / 14),
                        Math.min(255, 28 + Color.blue(accentColor) / 14))
                : Color.argb(245,
                        Math.max(0, 248 - (255 - Color.red(accentColor)) / 18),
                        Math.max(0, 249 - (255 - Color.green(accentColor)) / 18),
                        Math.max(0, 252 - (255 - Color.blue(accentColor)) / 18));
        int strokeColor = Ui.withAlpha(accentColor, dark ? 105 : 145);

        GradientDrawable cardBg = new GradientDrawable();
        cardBg.setColor(fillColor);
        cardBg.setCornerRadius(Ui.dp(activity, 18));
        cardBg.setStroke(Ui.strokePx(activity, 1.1f), strokeColor);

        LinearLayout card = Ui.vertical(activity);
        card.setBackground(cardBg);
        card.setPadding(Ui.dp(activity, 13), Ui.dp(activity, 12), Ui.dp(activity, 13), Ui.dp(activity, 12));

        LinearLayout header = new LinearLayout(activity);
        header.setOrientation(LinearLayout.HORIZONTAL);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(0, 0, 0, Ui.dp(activity, 6));

        View dot = new View(activity);
        GradientDrawable dotBg = new GradientDrawable();
        dotBg.setShape(GradientDrawable.OVAL);
        dotBg.setColor(accentColor);
        dot.setBackground(dotBg);
        dot.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams dotLp = new LinearLayout.LayoutParams(Ui.dp(activity, 8), Ui.dp(activity, 8));
        dotLp.setMargins(0, 0, Ui.dp(activity, 7), 0);
        header.addView(dot, dotLp);

        int labelColor = dark ? accentColor : darkenForLightMode(accentColor);
        TextView titleView = Ui.text(activity, title, 12.5f, labelColor);
        titleView.setTextColor(labelColor);
        titleView.setTypeface(Ui.SANS_MEDIUM);
        titleView.setLetterSpacing(0.02f);
        titleView.setPadding(0, 0, 0, 0);
        header.addView(titleView);

        card.addView(header);
        return card;
    }

    private static int darkenForLightMode(int color) {
        return Color.rgb(
                Math.max(0, (int) (Color.red(color) * 0.62f)),
                Math.max(0, (int) (Color.green(color) * 0.62f)),
                Math.max(0, (int) (Color.blue(color) * 0.62f)));
    }

    private TextView buildCategoryBody(String initialText) {
        TextView tv = Ui.text(activity, initialText, 13.5f, Ui.TEXT);
        tv.setLineSpacing(0f, 1.28f);
        tv.setTextIsSelectable(true);
        tv.setPadding(0, 0, 0, 0);
        return tv;
    }

    /** Launches the phone's built-in Camera app directly (preserving user's zoom/HDR/macro settings). */
    void startCamera() {
        activity.launchSystemCameraPhoto();
    }

    void requestInspection() {
        activity.launchSystemCameraPhoto();
    }

    private void toggleAutoSpeak() {
        autoSpeak = !autoSpeak;
        autoSpeakButton.setText(autoSpeak ? "auto-speak: on" : "auto-speak: off");
        setStatus(autoSpeak ? "auto-speak enabled for inspections" : "auto-speak turned off");
    }

    private DeviceAiController ensureDeviceAi() {
        if (deviceAi == null) {
            deviceAi = new DeviceAiController(activity, this::setStatus);
        }
        return deviceAi;
    }

    private static byte[] compressBoundedJpeg(Bitmap bitmap) {
        int maxDim = 1024;
        int w = bitmap.getWidth();
        int h = bitmap.getHeight();
        Bitmap resized = bitmap;
        if (w > maxDim || h > maxDim) {
            float scale = maxDim / (float) Math.max(w, h);
            resized = Bitmap.createScaledBitmap(bitmap, Math.max(1, Math.round(w * scale)),
                    Math.max(1, Math.round(h * scale)), true);
        }
        try (ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            resized.compress(Bitmap.CompressFormat.JPEG, 84, out);
            return out.toByteArray();
        } catch (IOException error) {
            return new byte[0];
        } finally {
            if (resized != bitmap) {
                resized.recycle();
            }
        }
    }

    /** Extracts clean multiline labels from MediaChatHelper's offline report string. */
    private static String extractFormattedLabels(String judgeReport) {
        if (judgeReport == null || judgeReport.isEmpty()) {
            return "";
        }
        int idx = judgeReport.indexOf("Labels:");
        if (idx < 0) {
            return "";
        }
        String after = judgeReport.substring(idx + "Labels:".length()).trim();
        int period = after.indexOf('.');
        if (period > 0) {
            after = after.substring(0, period).trim();
        }
        if (after.toLowerCase(Locale.US).startsWith("none")) {
            return "";
        }
        String[] parts = after.split(",");
        StringBuilder out = new StringBuilder();
        int count = 0;
        for (String raw : parts) {
            String clean = raw.trim().replace("(", "").replace(")", "").toLowerCase(Locale.US);
            if (!clean.isEmpty() && count < 4) {
                if (out.length() > 0) {
                    out.append("\n");
                }
                out.append(clean);
                count++;
            }
        }
        return out.toString();
    }

    /** Inspect & learn seamlessly from any native Camera photo/video or Gallery item. */
    void inspectPickedMedia(Uri uri, boolean isVideo) {
        if (uri == null) {
            return;
        }
        setStatus(isVideo ? "analyzing video keyframes offline…" : "analyzing photo offline…");
        analysisExecutor.execute(() -> {
            try {
                MediaChatHelper.MediaAttachment att = isVideo
                        ? MediaChatHelper.analyzeVideoUri(activity, uri)
                        : MediaChatHelper.analyzePhotoUri(activity, uri);
                Bitmap bmp = (att.jpegBytes != null && att.jpegBytes.length > 0)
                        ? BitmapFactory.decodeByteArray(att.jpegBytes, 0, att.jpegBytes.length)
                        : att.thumbnail;
                FramePalette.Analysis palette = bmp != null ? FramePalette.analyzeBitmap(bmp) : null;
                PatentReverseImageEngine.VisualSignature sig = bmp != null
                        ? PatentReverseImageEngine.extractFromBitmap(bmp, true)
                        : null;
                VisionPriorStore.MatchResult priorMatch = sig != null
                        ? VisionPriorStore.matchSignature(activity, sig, VisionPriorStore.DEFAULT_MIN_SCORE)
                        : null;
                byte[] jpegBytes = (att.jpegBytes != null && att.jpegBytes.length > 0)
                        ? att.jpegBytes
                        : (bmp != null ? compressBoundedJpeg(bmp) : new byte[0]);
                if (bmp != null && bmp != att.thumbnail && !bmp.isRecycled()) {
                    bmp.recycle();
                }
                post(() -> {
                    lastFrameJpeg = jpegBytes;
                    lastVisualSignature = sig;
                    lastPriorMatch = priorMatch;
                    lastPaletteAnalysis = palette;
                    lastStructuralNote = "";
                    lastCloud = "";
                    lastDeviceAi = "";
                    lastJudgeReport = att.offlineReport == null ? "" : att.offlineReport;
                    lastOcr = ArExploreBrain.extractOcrSnippet(lastJudgeReport);
                    lastLabels = extractFormattedLabels(lastJudgeReport);
                    lastPaletteSummary = palette != null ? palette.summary().toLowerCase(Locale.US) : "";

                    if (jpegBytes != null && jpegBytes.length > 0) {
                        BitmapFactory.Options opts = new BitmapFactory.Options();
                        opts.inSampleSize = 2;
                        Bitmap previewBmp = BitmapFactory.decodeByteArray(jpegBytes, 0, jpegBytes.length, opts);
                        if (previewBmp != null) {
                            mediaPreview.setImageBitmap(previewBmp);
                            mediaPreview.setVisibility(VISIBLE);
                            emptyCameraPrompt.setVisibility(GONE);
                        }
                    } else if (att.thumbnail != null) {
                        mediaPreview.setImageBitmap(att.thumbnail);
                        mediaPreview.setVisibility(VISIBLE);
                        emptyCameraPrompt.setVisibility(GONE);
                    }

                    boolean hasFrame = jpegBytes != null && jpegBytes.length > 0;
                    saveJournalButton.setEnabled(hasFrame);
                    sharePhotoButton.setEnabled(hasFrame);
                    cloudAskButton.setEnabled(hasFrame);
                    teachObjectButton.setEnabled(sig != null);
                    patentPriorButton.setEnabled(hasFrame && sig != null);
                    askZoeButton.setVisibility(VISIBLE);
                    learnBar.setVisibility(VISIBLE);
                    refreshMemoryBadge();

                    renderStructuredObservationCards();
                    shared = buildPlainShareSummary();
                    spoken = lastJudgeReport.length() > 1100 ? lastJudgeReport.substring(0, 1100) : lastJudgeReport;
                    setStatus(priorMatch != null
                            ? "recognized \"" + priorMatch.prototype.label.toLowerCase(Locale.US) + "\" from visual memory"
                            : "inspection complete · tap ask zoe, digest to zoe, or take another photo");
                    observationGrid.announceForAccessibility("Inspection complete");
                    if (autoSpeak && !spoken.isEmpty()) {
                        activity.speak(spoken);
                    }
                    if (hasFrame) {
                        ZoeLearnQueue.Destination dest = ZoeLearnQueue.savedDestination(activity);
                        if (dest == ZoeLearnQueue.Destination.INSTANT_DIGEST) {
                            digestCurrentFrameToZoe(true);
                        } else if (dest == ZoeLearnQueue.Destination.DEVICE_FOLDER) {
                            saveCurrentFrameToDeviceLearn(true);
                        } else if (dest == ZoeLearnQueue.Destination.GOOGLE_DRIVE) {
                            saveCurrentFrameToDriveLearn(true);
                        }
                    }
                });
            } catch (Exception err) {
                post(() -> setStatus("could not inspect media: " + err.getMessage()));
            }
        });
    }

    /** Updates all 4 symmetrical color-coded cards cleanly with crisp visual hierarchy. */
    private void renderStructuredObservationCards() {
        emptyHintView.setVisibility(GONE);
        observationGrid.setVisibility(VISIBLE);

        // Optional Deep Inspect Card
        if (!lastCloud.isEmpty()) {
            deepInspectBody.setText(lastCloud.toLowerCase(Locale.US));
            deepInspectCard.setVisibility(VISIBLE);
        } else {
            deepInspectCard.setVisibility(GONE);
        }

        // Card 1: Visual Memory (Ruby-Rose)
        StringBuilder mem = new StringBuilder();
        if (lastPriorMatch != null) {
            mem.append(lastPriorMatch.formatGuidedSummary().toLowerCase(Locale.US));
        }
        if (!lastStructuralNote.isEmpty()) {
            if (mem.length() > 0) mem.append("\n");
            mem.append(lastStructuralNote.toLowerCase(Locale.US));
        }
        if (lastVisualSignature != null && !lastVisualSignature.shapeSummary.isEmpty()) {
            if (mem.length() > 0) mem.append("\n");
            mem.append(lastVisualSignature.shapeSummary.toLowerCase(Locale.US));
        }
        if (mem.length() == 0) {
            memoryCardBody.setText("none yet");
            memoryCardBody.setTextColor(Ui.mutedColor(activity));
        } else {
            memoryCardBody.setText(mem.toString());
            memoryCardBody.setTextColor(Ui.textColor(activity));
        }

        // Card 2: Text / OCR (Cobalt-Blue)
        if (lastOcr.isEmpty()) {
            textCardBody.setText("no text found");
            textCardBody.setTextColor(Ui.mutedColor(activity));
        } else {
            textCardBody.setText(lastOcr.toLowerCase(Locale.US));
            textCardBody.setTextColor(Ui.textColor(activity));
        }

        // Card 3: Labels (Emerald-Mint)
        if (lastLabels.isEmpty()) {
            labelsCardBody.setText("none above 50%");
            labelsCardBody.setTextColor(Ui.mutedColor(activity));
        } else {
            labelsCardBody.setText(lastLabels);
            labelsCardBody.setTextColor(Ui.textColor(activity));
        }

        // Card 4: Light & Color (Amber-Gold + inline live swatch pills)
        if (lastPaletteAnalysis != null) {
            String summary = lastPaletteAnalysis.summary().toLowerCase(Locale.US);
            int palIdx = summary.indexOf("palette:");
            String lightPart = palIdx > 0 ? summary.substring(0, palIdx).trim() : summary;
            lightPart = lightPart.replace(" · ", "\n");
            lightCardBody.setText(lightPart);
            lightCardBody.setTextColor(Ui.textColor(activity));
            renderPaletteSwatches(lastPaletteAnalysis);
        } else {
            lightCardBody.setText("not measured");
            lightCardBody.setTextColor(Ui.mutedColor(activity));
            lightSwatchRow.removeAllViews();
        }
    }

    private String buildPlainShareSummary() {
        StringBuilder sb = new StringBuilder();
        if (!lastCloud.isEmpty()) {
            sb.append("deep inspect: ").append(lastCloud.toLowerCase(Locale.US)).append("\n");
        }
        if (lastPriorMatch != null) {
            sb.append("visual memory: ").append(lastPriorMatch.formatGuidedSummary().toLowerCase(Locale.US)).append("\n");
        }
        if (!lastOcr.isEmpty()) {
            sb.append("text: ").append(lastOcr.toLowerCase(Locale.US)).append("\n");
        }
        if (!lastLabels.isEmpty()) {
            sb.append("labels: ").append(lastLabels.replace("\n", ", ")).append("\n");
        }
        if (!lastPaletteSummary.isEmpty()) {
            sb.append("light & color: ").append(lastPaletteSummary).append("\n");
        }
        return sb.toString().trim();
    }

    private void refreshMemoryBadge() {
        memoryBadgeButton.setText("memory: " + VisionPriorStore.learnedCount(activity));
    }

    private void promptTeachObject() {
        if (lastVisualSignature == null) {
            setStatus("take or pick a photo first before teaching zoe");
            return;
        }
        String defaultGuess = lastPriorMatch != null
                ? lastPriorMatch.prototype.label
                : ArExploreBrain.extractPrimaryLabel(lastJudgeReport);
        EditText input = Ui.input(activity, defaultGuess.toLowerCase(Locale.US), "object name");
        new AlertDialog.Builder(activity)
                .setTitle("teach zoe this object")
                .setMessage("saves only compact contour geometry locally on-device (no photo uploaded) so zoe recognizes it offline")
                .setView(input)
                .setNegativeButton("cancel", null)
                .setPositiveButton("learn offline", (dialog, which) -> {
                    String name = VisionPriorStore.cleanLabel(input.getText().toString()).toLowerCase(Locale.US);
                    if (name.isEmpty()) {
                        setStatus("enter a short object name so zoe can learn its shape");
                        return;
                    }
                    PatentReverseImageEngine.VisualSignature sig = lastVisualSignature;
                    VisionPriorStore.teach(activity, name, sig, "user_confirmed", "", "");
                    lastPriorMatch = VisionPriorStore.matchSignature(activity, sig, 0.5f);
                    lastStructuralNote = "saved \"" + name + "\"";
                    refreshMemoryBadge();
                    renderStructuredObservationCards();
                    shared = buildPlainShareSummary();
                    setStatus("learned \"" + name + "\" offline");
                })
                .show();
    }

    private void runSilentPatentPrior() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0 || lastVisualSignature == null) {
            setStatus("take or pick a photo first");
            return;
        }
        final byte[] snapshot = lastFrameJpeg;
        final String judge = lastJudgeReport;
        final PatentReverseImageEngine.VisualSignature sig = lastVisualSignature;
        patentPriorButton.setEnabled(false);
        setStatus("checking physical patent contour priors…");
        analysisExecutor.execute(() -> {
            Bitmap bmp = BitmapFactory.decodeByteArray(snapshot, 0, snapshot.length);
            GooglePatentsClient.LookupResult res = GooglePatentsClient.silentResolveForVision(bmp, judge, "", 0f);
            if (bmp != null && !bmp.isRecycled()) {
                bmp.recycle();
            }
            post(() -> {
                patentPriorButton.setEnabled(lastFrameJpeg != null && lastFrameJpeg.length > 0);
                GooglePatentsClient.PatentMatch top = res.topMatch();
                if (top != null) {
                    String concept = GooglePatentsClient.cleanPhysicalConcept(top.title).toLowerCase(Locale.US);
                    VisionPriorStore.teach(activity, concept, sig, "patent_cpc", top.publicationNumber, top.dimensionsNote);
                    lastPriorMatch = VisionPriorStore.matchSignature(activity, sig, 0.5f);
                    lastStructuralNote = "patent prior: " + concept;
                    refreshMemoryBadge();
                    renderStructuredObservationCards();
                    shared = buildPlainShareSummary();
                    spoken = "structural prior identified " + concept;
                    setStatus("learned \"" + concept + "\" into offline memory");
                    if (autoSpeak) {
                        activity.speak(spoken);
                    }
                } else {
                    setStatus("no high-confidence patent contour match · tap teach zoe to train directly");
                }
            });
        });
    }

    private void showLearnedMemoryDialog() {
        List<VisionPriorStore.Prototype> list = VisionPriorStore.loadAll(activity);
        if (list.isEmpty()) {
            new AlertDialog.Builder(activity)
                    .setTitle("visual memory")
                    .setMessage("no objects learned yet. take a photo and tap teach zoe or digest to zoe")
                    .setPositiveButton("done", null)
                    .show();
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < Math.min(20, list.size()); i++) {
            VisionPriorStore.Prototype p = list.get(i);
            sb.append("• ").append(p.label.toLowerCase(Locale.US))
                    .append(" (seen ").append(p.confirmCount).append("×)\n");
        }
        new AlertDialog.Builder(activity)
                .setTitle("visual memory (" + list.size() + ")")
                .setMessage(sb.toString().trim())
                .setNegativeButton("close", null)
                .setNeutralButton("clear all", (d, w) -> {
                    VisionPriorStore.clearAll(activity);
                    lastPriorMatch = null;
                    refreshMemoryBadge();
                    renderStructuredObservationCards();
                    setStatus("cleared local visual memory");
                })
                .show();
    }

    private void renderPaletteSwatches(FramePalette.Analysis palette) {
        lightSwatchRow.removeAllViews();
        for (int i = 0; i < palette.colors.length; i++) {
            View swatch = new View(activity);
            GradientDrawable bg = new GradientDrawable();
            bg.setColor(palette.colors[i]);
            bg.setCornerRadius(Ui.dp(activity, 8));
            bg.setStroke(Ui.strokePx(activity, 0.8f), Ui.withAlpha(Color.WHITE, 90));
            swatch.setBackground(bg);
            swatch.setContentDescription(palette.names[i] + " " + palette.hexCodes[i]);
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, Ui.dp(activity, 20), 1.0f);
            params.setMargins(0, 0, i < palette.colors.length - 1 ? Ui.dp(activity, 5) : 0, 0);
            lightSwatchRow.addView(swatch, params);
        }
    }

    private void promptSaveToJournal() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("take or pick a photo first");
            return;
        }
        EditText noteInput = Ui.input(activity, "", "optional note");
        new AlertDialog.Builder(activity)
                .setTitle("save to journal")
                .setMessage("saves this sighting locally on your phone")
                .setView(noteInput)
                .setNegativeButton("cancel", null)
                .setPositiveButton("save", (dialog, which) -> {
                    byte[] copy = lastFrameJpeg;
                    Bitmap thumb = copy == null ? null : BitmapFactory.decodeByteArray(copy, 0, copy.length);
                    TripJournalStore.Entry entry = new TripJournalStore.Entry(
                            TripJournalStore.newId(),
                            TripJournalStore.nowIso(),
                            noteInput.getText().toString().trim(),
                            lastOcr,
                            lastLabels,
                            lastPaletteSummary,
                            lastDeviceAi,
                            lastCloud,
                            "",
                            false);
                    TripJournalStore.saveEntry(activity, entry, thumb);
                    if (thumb != null) {
                        thumb.recycle();
                    }
                    setStatus("saved locally to journal");
                })
                .show();
    }

    private void sharePhotoWithApps() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("take or pick a photo first");
            return;
        }
        try {
            File dir = new File(activity.getCacheDir(), "trip_share");
            if (!dir.exists()) {
                dir.mkdirs();
            }
            File file = new File(dir, "snapshot.jpg");
            try (FileOutputStream fos = new FileOutputStream(file)) {
                fos.write(lastFrameJpeg);
            }
            Uri uri = FileProvider.getUriForFile(activity, activity.getPackageName() + ".fileprovider", file);
            Intent share = new Intent(Intent.ACTION_SEND)
                    .setType("image/jpeg")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .putExtra(Intent.EXTRA_SUBJECT, "zoe sighting")
                    .putExtra(Intent.EXTRA_TEXT, shared)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivity(Intent.createChooser(share, "share photo"));
            setStatus("opened photo share sheet");
        } catch (IOException | ActivityNotFoundException error) {
            setStatus("could not share photo: " + error.getMessage());
        }
    }

    private void cycleAutoLearn() {
        ZoeLearnQueue.Destination next = ZoeLearnQueue.savedDestination(activity).next();
        ZoeLearnQueue.saveDestination(activity, next);
        autoLearnButton.setText(next.shortLabel.toLowerCase(Locale.US));
        if (next == ZoeLearnQueue.Destination.GOOGLE_DRIVE && ZoeLearnQueue.savedDriveTreeUri(activity) == null) {
            setStatus("auto-learn set to google drive · tap pick drive folder to link");
        } else {
            setStatus(next.shortLabel.toLowerCase(Locale.US) + " (" + next.helper.toLowerCase(Locale.US) + ")");
        }
    }

    void onLearnFolderPicked(Uri uri) {
        pickDriveFolderButton.setText("drive: linked");
        autoLearnButton.setText(ZoeLearnQueue.savedDestination(activity).shortLabel.toLowerCase(Locale.US));
        setStatus("linked google drive folder for zoe learn");
        if (lastFrameJpeg != null && lastFrameJpeg.length > 0) {
            saveCurrentFrameToDriveLearn(false);
        }
    }

    private String bestGuessLabel() {
        if (lastPriorMatch != null && !lastPriorMatch.prototype.label.isEmpty()) {
            return lastPriorMatch.prototype.label;
        }
        String primary = ArExploreBrain.extractPrimaryLabel(lastJudgeReport);
        if (primary != null && !primary.isEmpty()) {
            return primary;
        }
        if (!lastOcr.isEmpty()) {
            return lastOcr.length() > 24 ? lastOcr.substring(0, 24) : lastOcr;
        }
        return "zoe_observation";
    }

    private void digestCurrentFrameToZoe(boolean autoTriggered) {
        if (lastVisualSignature == null) {
            setStatus("take or pick a photo first");
            return;
        }
        final String label = VisionPriorStore.cleanLabel(bestGuessLabel()).toLowerCase(Locale.US);
        final PatentReverseImageEngine.VisualSignature sig = lastVisualSignature;
        digestZoeButton.setEnabled(false);
        setStatus((autoTriggered ? "auto-learn: digesting " : "digesting ") + "\"" + label + "\" into zoe…");
        analysisExecutor.execute(() -> {
            VisionPriorStore.teach(activity, label, sig, "guided_learn", "", "");
            int totalDigested = ZoeLearnQueue.incrementDigestedCount(activity);
            String endpoint = ElizaGemClient.savedEndpoint(activity);
            boolean syncedWorkstation = false;
            int cycleNum = 0;
            try {
                MobileDigestionBundle.Summary bundle = MobileDigestionBundle.collect(activity, new ZoeBrainEngine(activity));
                ElizaGemClient.DigestResult res = studioClient.digestMobileBundle(endpoint, bundle.bundleJson);
                syncedWorkstation = res != null && res.available;
                cycleNum = res != null ? res.cycleNumber : 0;
            } catch (Exception ignored) {
            }
            final boolean synced = syncedWorkstation;
            final int cycle = cycleNum;
            post(() -> {
                digestZoeButton.setEnabled(true);
                refreshMemoryBadge();
                if (synced) {
                    setStatus("zoe digested \"" + label + "\" live (workstation cycle #" + cycle + " · " + totalDigested + " total)");
                } else {
                    setStatus("zoe learned \"" + label + "\" offline (" + totalDigested + " total)");
                }
            });
        });
    }

    private void saveCurrentFrameToDeviceLearn(boolean autoTriggered) {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("take or pick a photo first");
            return;
        }
        final byte[] bytes = lastFrameJpeg;
        final String label = bestGuessLabel();
        saveLearnDeviceButton.setEnabled(false);
        analysisExecutor.execute(() -> {
            try {
                String path = ZoeLearnQueue.saveToDeviceZoeLearn(activity, bytes, label);
                int qCount = ZoeLearnQueue.queuedCount(activity);
                post(() -> {
                    saveLearnDeviceButton.setEnabled(true);
                    setStatus((autoTriggered ? "auto-saved to " : "saved to ") + path.toLowerCase(Locale.US) + " (" + qCount + " saved)");
                });
            } catch (IOException err) {
                post(() -> {
                    saveLearnDeviceButton.setEnabled(true);
                    setStatus("could not save to device: " + err.getMessage());
                });
            }
        });
    }

    private void saveCurrentFrameToDriveLearn(boolean autoTriggered) {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("take or pick a photo first");
            return;
        }
        Uri treeUri = ZoeLearnQueue.savedDriveTreeUri(activity);
        if (treeUri == null) {
            if (autoTriggered) {
                saveCurrentFrameToDeviceLearn(true);
            } else {
                new AlertDialog.Builder(activity)
                        .setTitle("google drive · zoe learn")
                        .setMessage("link your google drive folder once for 1-tap saving, or send this photo directly now")
                        .setPositiveButton("link folder", (d, w) -> activity.pickZoeLearnDriveFolder())
                        .setNeutralButton("send now", (d, w) -> {
                            boolean ok = ZoeLearnQueue.shareToGoogleDrive(activity, lastFrameJpeg, bestGuessLabel(), shared);
                            setStatus(ok ? "opened google drive" : "could not open google drive");
                        })
                        .setNegativeButton("cancel", null)
                        .show();
            }
            return;
        }
        final byte[] bytes = lastFrameJpeg;
        final String label = bestGuessLabel();
        saveLearnDriveButton.setEnabled(false);
        analysisExecutor.execute(() -> {
            try {
                String fileName = ZoeLearnQueue.saveToPickedTreeFolder(activity, treeUri, bytes, label);
                post(() -> {
                    saveLearnDriveButton.setEnabled(true);
                    setStatus((autoTriggered ? "auto-saved to drive: " : "saved to drive: ") + fileName.toLowerCase(Locale.US));
                });
            } catch (IOException err) {
                post(() -> {
                    saveLearnDriveButton.setEnabled(true);
                    ZoeLearnQueue.shareToGoogleDrive(activity, bytes, label, shared);
                    setStatus("opened google drive share sheet");
                });
            }
        });
    }

    private void openChatWithObservation() {
        StringBuilder q = new StringBuilder("guided vision inspected a frame.\n");
        if (!lastOcr.isEmpty()) {
            q.append("visible text: ").append(lastOcr).append("\n");
        }
        if (!lastLabels.isEmpty()) {
            q.append("labels: ").append(lastLabels.replace("\n", ", ")).append("\n");
        }
        if (lastPriorMatch != null) {
            q.append("learned match: ").append(lastPriorMatch.prototype.label).append("\n");
        }
        if (!lastPaletteSummary.isEmpty()) {
            q.append("light & color: ").append(lastPaletteSummary).append("\n");
        }
        q.append("help me understand what i'm looking at");
        Intent chat = new Intent(activity, ConversationActivity.class)
                .putExtra(ConversationActivity.EXTRA_INITIAL_PROMPT, q.toString().trim());
        activity.startActivity(chat);
        if (!activity.isComfortMode()) {
            activity.overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }

    private void askCloudVision() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("take or pick a photo first");
            return;
        }
        String key = CloudVisionClient.savedApiKey(activity);
        if (key.isEmpty()) {
            String endpoint = ElizaGemClient.savedEndpoint(activity);
            String prompt = "Guided Vision frame observation. " + lastJudgeReport
                    + (lastPaletteSummary.isEmpty() ? "" : " Light & color: " + lastPaletteSummary)
                    + " Summarize what this likely is concisely without em dashes.";
            cloudAskButton.setEnabled(false);
            setStatus("asking workstation zoe…");
            analysisExecutor.execute(() -> {
                try {
                    ElizaGemClient.ChatReply reply = studioClient.chat(endpoint, prompt, "gear3");
                    String answer = OnDeviceLlmEngine.enforceZoeSovereignty(reply.reply);
                    post(() -> {
                        cloudAskButton.setEnabled(true);
                        lastCloud = answer;
                        renderStructuredObservationCards();
                        shared = buildPlainShareSummary();
                        spoken = answer.length() > 1100 ? answer.substring(0, 1100) : answer;
                        setStatus("workstation zoe replied");
                        if (autoSpeak) {
                            activity.speak(spoken);
                        }
                    });
                } catch (Exception err) {
                    post(() -> {
                        cloudAskButton.setEnabled(true);
                        setStatus("no cloud key & workstation offline · tap ask zoe about this");
                    });
                }
            });
            return;
        }
        String model = CloudVisionClient.savedModel(activity);
        byte[] snapshot = lastFrameJpeg;
        cloudAskButton.setEnabled(false);
        setStatus("inspecting with " + model.toLowerCase(Locale.US) + "…");
        String prompt = "Describe clearly and honestly what is in this image without em dashes. "
                + (lastOcr.isEmpty() ? "" : "On-device OCR read: " + lastOcr + ". ");
        analysisExecutor.execute(() -> {
            try {
                String answer = OnDeviceLlmEngine.enforceZoeSovereignty(
                        CloudVisionClient.askVision(key, model, prompt, snapshot));
                post(() -> {
                    cloudAskButton.setEnabled(true);
                    lastCloud = answer;
                    renderStructuredObservationCards();
                    shared = buildPlainShareSummary();
                    spoken = answer.length() > 1100 ? answer.substring(0, 1100) : answer;
                    setStatus("deep inspect complete");
                    if (autoSpeak) {
                        activity.speak(spoken);
                    }
                });
            } catch (Exception error) {
                post(() -> {
                    cloudAskButton.setEnabled(true);
                    setStatus("deep inspect failed: " + error.getMessage());
                });
            }
        });
    }

    void setStatus(String value) {
        status.setText(value == null ? "" : value.toLowerCase(Locale.US));
    }

    String spokenSummary() {
        return spoken;
    }

    String shareText() {
        return shared;
    }

    void pauseCamera() {
        // Native Camera app manages its own lifecycle cleanly.
    }

    void close() {
        lastFrameJpeg = null;
        if (deviceAi != null) {
            deviceAi.close();
        }
        analysisExecutor.shutdownNow();
    }
}
