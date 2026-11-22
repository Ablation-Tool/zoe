package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.provider.MediaStore;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Creative Studio — Offline Image Lab & Native MP4 Video Maker (v0.6.0-beta).
 *
 *   - Image Lab: instant offline film/tone filters, brightness/contrast, 90° rotation, 1:1 / 16:9 crop,
 *     privacy pixelation blur, caption stamping, plain-English command bar ("warm, rotate 90, noir"),
 *     optional online BYOK AI image generation, and PNG export/share.
 *   - Video Maker: renders genuine H.264 `.mp4` videos 100% offline via Android MediaCodec + MediaMuxer
 *     (Chladni Wave, Photo Story Reel with Ken Burns motion, or Starlight GEM), plus live camera capture.
 */
public final class CreativeStudioActivity extends ComponentActivity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ZoeNativeVoice nativeVoice = new ZoeNativeVoice();

    private Bitmap sourceBitmap;
    private Bitmap editedBitmap;
    private ScientificVisualSubstrate.BaselinePlate activeBaseline = ScientificVisualSubstrate.BaselinePlate.ATELIER;
    private ImageLabEngine.EditSpec editSpec = new ImageLabEngine.EditSpec();
    private final VideoMakerEngine.Spec videoSpec = new VideoMakerEngine.Spec();
    private File lastExportedVideo;

    private Button tabImageBtn;
    private Button tabVideoBtn;
    private LinearLayout imagePanel;
    private LinearLayout videoPanel;
    private TextView status;

    // Image Lab widgets
    private ImageView imagePreview;
    private TextView editSummary;
    private TextView baselineMeta;
    private EditText commandInput;
    private Button blurBtn;
    private Button cropBtn;

    // Video Maker widgets
    private ImageView videoPreview;
    private EditText videoTitleInput;
    private EditText videoSubInput;
    private TextView videoStatus;
    private Button shareVideoBtn;

    private final ActivityResultLauncher<String[]> pickPhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) {
                    loadPickedPhoto(uri);
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sourceBitmap = ImageLabEngine.createAtelierStarterBitmap(720, 540);

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        LinearLayout header = Ui.vertical(this);
        header.setBackgroundColor(Color.TRANSPARENT);
        header.setPadding(Ui.dp(this, 18), Ui.dp(this, 4), Ui.dp(this, 18), Ui.dp(this, 4));
        header.addView(Ui.topBar(this, "Creative Studio", null));

        // Clean segmented pill bar (Apple Photos style)
        LinearLayout tabRow = new LinearLayout(this);
        tabRow.setOrientation(LinearLayout.HORIZONTAL);
        tabRow.setBackground(Ui.cardBackground(this, 22));
        tabRow.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4));
        tabImageBtn = pillChip("Image Lab", v -> showTab(true));
        tabImageBtn.setId(R.id.studio_tab_image);
        tabVideoBtn = pillChip("Video Maker", v -> showTab(false));
        tabVideoBtn.setId(R.id.studio_tab_video);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f);
        tlp.setMargins(0, 0, Ui.dp(this, 4), 0);
        tabRow.addView(tabImageBtn, tlp);
        tabRow.addView(tabVideoBtn, new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f));
        header.addView(tabRow);

        status = Ui.text(this, "Offline studio ready — edit Zoe's Atelier canvas or pick any photo.", 12.5f, Ui.MUTED);
        status.setId(R.id.studio_status);
        status.setPadding(Ui.dp(this, 4), Ui.dp(this, 8), Ui.dp(this, 4), Ui.dp(this, 2));
        header.addView(status);
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout body = Ui.vertical(this);
        body.setPadding(Ui.dp(this, 18), Ui.dp(this, 8), Ui.dp(this, 18), Ui.dp(this, 36));

        imagePanel = buildImageLabPanel();
        videoPanel = buildVideoMakerPanel();
        body.addView(imagePanel);
        body.addView(videoPanel);

        scroll.addView(body);
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);
        showTab(true);
        refreshImagePreview();
        refreshVideoPreview();
    }

    private LinearLayout buildImageLabPanel() {
        LinearLayout panel = Ui.vertical(this);

        imagePreview = new ImageView(this);
        imagePreview.setId(R.id.studio_image_preview);
        imagePreview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        imagePreview.setBackground(Ui.cardBackground(this, 22));
        imagePreview.setPadding(Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8));
        LinearLayout.LayoutParams imgLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 250));
        imgLp.setMargins(0, 0, 0, Ui.dp(this, 8));
        panel.addView(imagePreview, imgLp);

        editSummary = Ui.text(this, "Original", 12.5f, Ui.MUTED);
        editSummary.setId(R.id.studio_edit_summary);
        editSummary.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), Ui.dp(this, 2));
        panel.addView(editSummary);

        baselineMeta = Ui.text(this,
                "Baseline: " + activeBaseline.lineage + " · " + activeBaseline.mathSummary,
                11.5f, Ui.COBALT);
        baselineMeta.setId(R.id.studio_baseline_meta);
        baselineMeta.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), Ui.dp(this, 8));
        panel.addView(baselineMeta);

        // Scientific-Aesthetic Procedural Baseline Strip (Haeckel · Weismann · Lamarck · Google Patents)
        HorizontalScrollView baseScroll = new HorizontalScrollView(this);
        baseScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout baseRow = new LinearLayout(this);
        baseRow.setOrientation(LinearLayout.HORIZONTAL);
        for (ScientificVisualSubstrate.BaselinePlate plate : ScientificVisualSubstrate.BaselinePlate.values()) {
            Button pb = pillChip(plate.chipLabel, v -> applyScientificBaseline(plate));
            if (plate == ScientificVisualSubstrate.BaselinePlate.HAECKEL_RADIOLARIA) {
                pb.setId(R.id.studio_baseline_haeckel);
            } else if (plate == ScientificVisualSubstrate.BaselinePlate.PATENT_BLUEPRINT) {
                pb.setId(R.id.studio_baseline_patent);
            }
            LinearLayout.LayoutParams blp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            blp.setMargins(0, 0, Ui.dp(this, 6), 0);
            baseRow.addView(pb, blp);
        }
        baseScroll.addView(baseRow);
        LinearLayout.LayoutParams bsLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        bsLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        panel.addView(baseScroll, bsLp);

        // Plain-English command bar
        LinearLayout cmdRow = new LinearLayout(this);
        cmdRow.setOrientation(LinearLayout.HORIZONTAL);
        cmdRow.setGravity(Gravity.CENTER_VERTICAL);
        cmdRow.setBackground(Ui.cardBackground(this, 22));
        cmdRow.setPadding(Ui.dp(this, 10), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));
        commandInput = new EditText(this);
        commandInput.setId(R.id.studio_command_input);
        commandInput.setHint("e.g. haeckel, patent, warm, rotate, blur, caption Sunset…");
        commandInput.setTextColor(Ui.textColor(this));
        commandInput.setHintTextColor(Ui.mutedColor(this));
        commandInput.setBackground(null);
        commandInput.setTextSize(14f);
        Button applyCmdBtn = Ui.primaryButton(this, "Apply", Ui.COBALT, v -> {
            String cmd = commandInput.getText() == null ? "" : commandInput.getText().toString().trim();
            if (!cmd.isEmpty()) {
                ScientificVisualSubstrate.BaselinePlate detectedPlate =
                        ScientificVisualSubstrate.detectPlateFromCommand(cmd);
                if (detectedPlate != null) {
                    applyScientificBaseline(detectedPlate, cmd);
                    commandInput.setText("");
                    return;
                }
                editSpec = ImageLabEngine.parseEditCommand(cmd, editSpec);
                commandInput.setText("");
                refreshImagePreview();
                status.setText("Applied edit: " + editSpec.summary());
            }
        });
        applyCmdBtn.setId(R.id.studio_apply_cmd);
        applyCmdBtn.setTextSize(13.5f);
        applyCmdBtn.setMinHeight(Ui.dp(this, 38));
        applyCmdBtn.setMinimumHeight(Ui.dp(this, 38));
        cmdRow.addView(commandInput, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        cmdRow.addView(applyCmdBtn);
        LinearLayout.LayoutParams cmdLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cmdLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        panel.addView(cmdRow, cmdLp);

        // Filter preset horizontal filmstrip (sleek 34dp pills)
        HorizontalScrollView filterScroll = new HorizontalScrollView(this);
        filterScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout filterRow = new LinearLayout(this);
        filterRow.setOrientation(LinearLayout.HORIZONTAL);
        for (ImageLabEngine.FilterPreset preset : ImageLabEngine.FilterPreset.values()) {
            Button fb = pillChip(preset.label, v -> {
                editSpec.filter = preset;
                refreshImagePreview();
                status.setText("Filter: " + preset.label);
            });
            LinearLayout.LayoutParams flp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            flp.setMargins(0, 0, Ui.dp(this, 6), 0);
            filterRow.addView(fb, flp);
        }
        filterScroll.addView(filterRow);
        LinearLayout.LayoutParams fsLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        fsLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        panel.addView(filterScroll, fsLp);

        // Single clean horizontal tool strip (replaces 6 clunky stacked buttons!)
        HorizontalScrollView toolScroll = new HorizontalScrollView(this);
        toolScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout toolRow = new LinearLayout(this);
        toolRow.setOrientation(LinearLayout.HORIZONTAL);
        Button rotateBtn = pillChip("Rotate 90°", v -> {
            editSpec.rotationDeg = (editSpec.rotationDeg + 90) % 360;
            refreshImagePreview();
        });
        cropBtn = pillChip("Crop: Orig", v -> {
            ImageLabEngine.CropMode[] modes = ImageLabEngine.CropMode.values();
            editSpec.crop = modes[(editSpec.crop.ordinal() + 1) % modes.length];
            refreshImagePreview();
        });
        blurBtn = pillChip("Blur: off", v -> {
            editSpec.privacyBlur = !editSpec.privacyBlur;
            refreshImagePreview();
        });
        Button brightBtn = pillChip("Light +", v -> {
            editSpec.brightness = editSpec.brightness >= 48 ? -24 : editSpec.brightness + 24;
            refreshImagePreview();
        });
        Button resetBtn = pillChip("Reset", v -> {
            editSpec = new ImageLabEngine.EditSpec();
            refreshImagePreview();
            status.setText("Reset to original image.");
        });
        for (Button tb : new Button[]{rotateBtn, cropBtn, blurBtn, brightBtn, resetBtn}) {
            LinearLayout.LayoutParams tlp2 = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 36));
            tlp2.setMargins(0, 0, Ui.dp(this, 6), 0);
            toolRow.addView(tb, tlp2);
        }
        toolScroll.addView(toolRow);
        LinearLayout.LayoutParams tsLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tsLp.setMargins(0, 0, 0, Ui.dp(this, 14));
        panel.addView(toolScroll, tsLp);

        // Clean 2-button primary footer
        Button pickBtn = Ui.button(this, "Pick Photo", Ui.COBALT, v -> pickPhotoLauncher.launch(new String[]{"image/*"}));
        Button sharePngBtn = Ui.primaryButton(this, "Save & Share", Ui.GREEN, v -> shareEditedImage());
        panel.addView(Ui.buttonRow(this, pickBtn, sharePngBtn));

        // Quiet secondary disclosure actions (zero bulky box clutter!)
        Button toVideoBtn = Ui.disclosureButton(this, "Turn into Video Reel →", v -> {
            videoSpec.style = VideoMakerEngine.Style.PHOTO_STORY_REEL;
            showTab(false);
            refreshVideoPreview();
            status.setText("Loaded your edited image into Photo Story Reel!");
        });
        Button aiGenBtn = Ui.disclosureButton(this, "✨ AI Art (OpenAI Key)", v -> generateOnlineAiImage());
        panel.addView(Ui.buttonRow(this, toVideoBtn, aiGenBtn));

        return panel;
    }

    private LinearLayout buildVideoMakerPanel() {
        LinearLayout panel = Ui.vertical(this);

        videoPreview = new ImageView(this);
        videoPreview.setId(R.id.studio_video_preview);
        videoPreview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        videoPreview.setBackground(Ui.cardBackground(this, 22));
        videoPreview.setPadding(Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8));
        LinearLayout.LayoutParams vpLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 230));
        vpLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        panel.addView(videoPreview, vpLp);

        // Style pills
        HorizontalScrollView styleScroll = new HorizontalScrollView(this);
        styleScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout styleRow = new LinearLayout(this);
        styleRow.setOrientation(LinearLayout.HORIZONTAL);
        for (VideoMakerEngine.Style st : VideoMakerEngine.Style.values()) {
            Button sb = pillChip(st.label, v -> {
                videoSpec.style = st;
                refreshVideoPreview();
                status.setText("Video style: " + st.label);
            });
            LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            slp.setMargins(0, 0, Ui.dp(this, 6), 0);
            styleRow.addView(sb, slp);
        }
        styleScroll.addView(styleRow);
        panel.addView(styleScroll);

        // Palette pills
        HorizontalScrollView palScroll = new HorizontalScrollView(this);
        palScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout palRow = new LinearLayout(this);
        palRow.setOrientation(LinearLayout.HORIZONTAL);
        palRow.setPadding(0, Ui.dp(this, 6), 0, Ui.dp(this, 8));
        for (VideoMakerEngine.Palette pal : VideoMakerEngine.Palette.values()) {
            Button pb = pillChip(pal.label, v -> {
                videoSpec.palette = pal;
                refreshVideoPreview();
            });
            LinearLayout.LayoutParams plp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            plp.setMargins(0, 0, Ui.dp(this, 6), 0);
            palRow.addView(pb, plp);
        }
        palScroll.addView(palRow);
        panel.addView(palScroll);

        videoTitleInput = styledInput("Video title (e.g. Made with Zoe)", videoSpec.title);
        videoSubInput = styledInput("Caption / subtitle", videoSpec.subtitle);
        panel.addView(videoTitleInput);
        panel.addView(videoSubInput);

        videoStatus = Ui.text(this, "Encodes a real H.264 .mp4 100% offline using your phone's hardware encoder.", 12.5f, Ui.MUTED);
        videoStatus.setId(R.id.studio_video_status);
        videoStatus.setPadding(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 10));
        panel.addView(videoStatus);

        Button renderBtn = Ui.primaryButton(this, "🎬 Create MP4", Ui.COBALT, v -> exportOfflineMp4());
        renderBtn.setId(R.id.studio_render_mp4);
        shareVideoBtn = Ui.button(this, "Share MP4", Ui.GREEN, v -> shareExportedVideo());
        shareVideoBtn.setEnabled(false);
        panel.addView(Ui.buttonRow(this, renderBtn, shareVideoBtn));

        Button recordBtn = Ui.disclosureButton(this, "Record Live Clip", v -> {
            try {
                startActivity(new Intent(MediaStore.ACTION_VIDEO_CAPTURE));
            } catch (ActivityNotFoundException ignored) {
                status.setText("No built-in video recorder available.");
            }
        });
        Button soundBtn = Ui.disclosureButton(this, "Preview Zoe Sound", v -> {
            status.setText("Playing Zoe's 44.1 kHz native soprano theme…");
            nativeVoice.singZoe(null);
        });
        panel.addView(Ui.buttonRow(this, recordBtn, soundBtn));

        return panel;
    }

    private EditText styledInput(String hint, String initial) {
        EditText et = new EditText(this);
        et.setHint(hint);
        et.setText(initial);
        et.setTextColor(Ui.textColor(this));
        et.setHintTextColor(Ui.mutedColor(this));
        et.setTextSize(14.5f);
        et.setBackground(Ui.cardBackground(this, 16));
        et.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 14), Ui.dp(this, 10));
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));
        et.setLayoutParams(lp);
        return et;
    }

    private Button pillChip(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(12.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMaxLines(1);
        b.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        b.setTextColor(Ui.textColor(this));
        b.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 18));
        b.setStateListAnimator(null);
        b.setOnClickListener(listener);
        return b;
    }

    private void showTab(boolean imageTab) {
        imagePanel.setVisibility(imageTab ? View.VISIBLE : View.GONE);
        videoPanel.setVisibility(imageTab ? View.GONE : View.VISIBLE);
        styleTab(tabImageBtn, imageTab);
        styleTab(tabVideoBtn, !imageTab);
    }

    private void styleTab(Button btn, boolean selected) {
        if (selected) {
            btn.setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 18));
        } else {
            btn.setTextColor(Ui.mutedColor(this));
            btn.setBackground(Ui.tonalPillDrawable(this, Color.TRANSPARENT, Ui.primaryAccent(this), 18));
        }
    }

    private void loadPickedPhoto(Uri uri) {
        status.setText("Loading photo…");
        executor.execute(() -> {
            try {
                Bitmap bmp = MediaChatHelper.decodeScaledBitmap(this, uri, 1280);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        sourceBitmap = bmp;
                        editSpec = new ImageLabEngine.EditSpec();
                        refreshImagePreview();
                        refreshVideoPreview();
                        status.setText("Loaded your photo (" + bmp.getWidth() + "×" + bmp.getHeight() + ").");
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> status.setText("Could not open photo: " + err.getMessage()));
            }
        });
    }

    private void refreshImagePreview() {
        editedBitmap = ImageLabEngine.applyEdits(sourceBitmap, editSpec);
        imagePreview.setImageBitmap(editedBitmap);
        editSummary.setText(editSpec.summary());
        blurBtn.setText(editSpec.privacyBlur ? "Blur: on" : "Blur: off");
        cropBtn.setText("Crop: " + editSpec.crop.label);
    }

    private void refreshVideoPreview() {
        videoSpec.title = videoTitleInput == null ? videoSpec.title : videoTitleInput.getText().toString();
        videoSpec.subtitle = videoSubInput == null ? videoSpec.subtitle : videoSubInput.getText().toString();
        Bitmap prev = Bitmap.createBitmap(VideoMakerEngine.WIDTH, VideoMakerEngine.HEIGHT, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(prev);
        VideoMakerEngine.renderFrame(c, VideoMakerEngine.WIDTH, VideoMakerEngine.HEIGHT, editedBitmap, videoSpec, 0.35f);
        videoPreview.setImageBitmap(prev);
    }

    private void shareEditedImage() {
        if (editedBitmap == null) {
            return;
        }
        try {
            Uri uri = MediaChatHelper.savePngForShare(this, editedBitmap, "zoe_edit_" + System.currentTimeMillis() + ".png");
            Intent share = new Intent(Intent.ACTION_SEND)
                    .setType("image/png")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(share, "Save or share Zoe image"));
            status.setText("Exported edited PNG ready to share or save.");
        } catch (Exception err) {
            status.setText("Export failed: " + err.getMessage());
        }
    }

    private void applyScientificBaseline(ScientificVisualSubstrate.BaselinePlate plate) {
        String concept = commandInput == null || commandInput.getText() == null
                ? "" : commandInput.getText().toString().trim();
        applyScientificBaseline(plate, concept);
    }

    private void applyScientificBaseline(ScientificVisualSubstrate.BaselinePlate plate, String concept) {
        activeBaseline = plate;
        sourceBitmap = ScientificVisualSubstrate.renderScientificPlate(plate, concept, 720, 540);
        editSpec = new ImageLabEngine.EditSpec();
        refreshImagePreview();
        refreshVideoPreview();
        if (baselineMeta != null) {
            baselineMeta.setText("Baseline: " + plate.lineage + " · " + plate.mathSummary);
        }
        status.setText("Rendered factual baseline: " + plate.lineage + " (100% offline math).");
    }

    private void generateOnlineAiImage() {
        String prompt = commandInput.getText() == null ? "" : commandInput.getText().toString().trim();
        if (prompt.isEmpty()) {
            status.setText("Type an image idea in the command box above first, then tap AI Art (grounded by " + activeBaseline.chipLabel + ").");
            return;
        }
        String groundedPrompt = ScientificVisualSubstrate.augmentPromptWithBaseline(prompt, activeBaseline);
        status.setText("Generating AI artwork grounded in " + activeBaseline.lineage + "…");
        executor.execute(() -> {
            try {
                Bitmap bmp = ImageLabEngine.generateOnlineImage(this, groundedPrompt);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        sourceBitmap = bmp;
                        editSpec = new ImageLabEngine.EditSpec();
                        refreshImagePreview();
                        status.setText("Generated AI artwork grounded by " + activeBaseline.chipLabel + "!");
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> status.setText(err.getMessage()));
            }
        });
    }

    private void exportOfflineMp4() {
        videoSpec.title = videoTitleInput.getText().toString().trim();
        videoSpec.subtitle = videoSubInput.getText().toString().trim();
        refreshVideoPreview();
        videoStatus.setText("Encoding H.264 MP4 offline on your phone…");
        shareVideoBtn.setEnabled(false);

        File outFile = new File(new File(getCacheDir(), "creative_studio"), "zoe_video_" + System.currentTimeMillis() + ".mp4");
        Bitmap photoSnap = editedBitmap;
        executor.execute(() -> {
            try {
                File mp4 = VideoMakerEngine.exportMp4(outFile, photoSnap, videoSpec, (idx, total) -> {
                    if (idx % 10 == 0 || idx == total) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed()) {
                                videoStatus.setText("Encoding frame " + idx + " / " + total + " (100% offline)…");
                            }
                        });
                    }
                });
                long kb = Math.max(1L, mp4.length() / 1024L);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        lastExportedVideo = mp4;
                        shareVideoBtn.setEnabled(true);
                        videoStatus.setText("Created offline MP4 (" + kb + " KB · " + videoSpec.durationSec + "s H.264)! Tap Share MP4.");
                        status.setText("Video ready (" + kb + " KB MP4).");
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        videoStatus.setText("MP4 encoding error: " + err.getMessage());
                    }
                });
            }
        });
    }

    private void shareExportedVideo() {
        if (lastExportedVideo == null || !lastExportedVideo.isFile()) {
            return;
        }
        try {
            Uri uri = MediaChatHelper.shareUriForFile(this, lastExportedVideo);
            Intent share = new Intent(Intent.ACTION_SEND)
                    .setType("video/mp4")
                    .putExtra(Intent.EXTRA_STREAM, uri)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(Intent.createChooser(share, "Share Zoe MP4 Video"));
        } catch (Exception err) {
            status.setText("Share failed: " + err.getMessage());
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        nativeVoice.stop();
        executor.shutdownNow();
    }
}
