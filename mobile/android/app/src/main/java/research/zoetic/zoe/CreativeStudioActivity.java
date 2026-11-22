package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Matrix;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.MediaStore;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.EditorInfo;
import android.widget.Button;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;

import java.io.File;
import java.util.ArrayDeque;
import java.util.Deque;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Creative Studio Pro — Offline HD Scientific-Aesthetic Image Lab & 30fps MP4 Video Maker (v0.9.4-beta).
 *
 *   - Image Lab: 8 HD (1280×960) mathematical scientific-aesthetic plates (Atelier, Haeckel Radiolaria,
 *     Ammonite, Weismann, Lamarck, Patent Blueprint, Chladni Cymatics, Fibonacci Phyllotaxis), 9 film/archival
 *     filters with live active-chip highlighting, collapsible precision SeekBar sliders (Brightness, Contrast,
 *     Warmth, Saturation, Vignette), 16-step Undo stack, Hold-to-Compare Before/After preview, 90° rotate,
 *     horizontal flip, 1:1 / 4:5 / 16:9 crops, privacy blur, plain-English command bar, direct Save to Photos
 *     Gallery (MediaStore), PNG Share, and optional BYOK Gemini Imagen / OpenAI AI Art grounded by active plate.
 *   - Video Maker: live 20fps animated preview with Play/Pause + live title/subtitle updates, 5 animated offline
 *     styles (Chladni Wave, Photo Story Reel, Starlight GEM, Haeckel Living, Patent Kinetic), selectable 4s/6s/8s
 *     duration, exact CFR 30fps 720×720 HD H.264 MP4 encoding via MediaCodec + MediaMuxer, direct Save to Movies
 *     Gallery, and MP4 Share.
 */
public final class CreativeStudioActivity extends ComponentActivity {
    private static final int PLATE_W = 1280;
    private static final int PLATE_H = 960;
    private static final int MAX_UNDO = 16;

    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final ZoeNativeVoice nativeVoice = new ZoeNativeVoice();
    private final Handler previewHandler = new Handler(Looper.getMainLooper());
    private final Deque<ImageLabEngine.EditSpec> undoStack = new ArrayDeque<>();

    private Bitmap sourceBitmap;
    private Bitmap editedBitmap;
    private Bitmap videoPreviewBitmap;
    private ScientificVisualSubstrate.BaselinePlate activeBaseline = ScientificVisualSubstrate.BaselinePlate.ATELIER;
    private ImageLabEngine.EditSpec editSpec = new ImageLabEngine.EditSpec();
    private final VideoMakerEngine.Spec videoSpec = new VideoMakerEngine.Spec();
    private File lastExportedVideo;

    private boolean isImageTab = true;
    private boolean videoPreviewPlaying = false;
    private float videoPreviewT = 0.35f;
    private boolean syncingSliders = false;
    private boolean drawMode = false;
    private int activeInkColor = Color.rgb(255, 214, 102);
    private float activeBrushWidthNorm = 0.013f;
    private ImageLabEngine.BrushStroke activeStroke;
    private final Matrix inverseImageMatrix = new Matrix();

    private Button tabImageBtn;
    private Button tabVideoBtn;
    private LinearLayout imagePanel;
    private LinearLayout videoPanel;
    private TextView status;

    // Image Lab widgets & active chip registries
    private ImageView imagePreview;
    private TextView editSummary;
    private TextView baselineMeta;
    private EditText commandInput;
    private Button undoBtn;
    private Button blurBtn;
    private Button cropBtn;
    private Button flipBtn;
    private Button adjustToggleBtn;
    private Button drawToggleBtn;
    private LinearLayout adjustDrawer;
    private LinearLayout drawDrawer;
    private final java.util.List<Button> inkColorBtns = new java.util.ArrayList<>();
    private final java.util.List<Button> brushSizeBtns = new java.util.ArrayList<>();
    private final int[] inkPaletteColors = {
            Color.rgb(255, 214, 102), // Luminous Gold
            Color.rgb(72, 229, 240),  // Coastal Cyan
            Color.rgb(244, 63, 94),   // Living Ruby
            Color.rgb(110, 231, 168), // Botanical Emerald
            Color.rgb(250, 250, 252), // Chalk White
            Color.rgb(18, 22, 32)     // Archival Ink
    };
    private final float[] brushWidths = {0.007f, 0.013f, 0.024f};
    private SeekBar brightBar;
    private SeekBar contrastBar;
    private SeekBar warmthBar;
    private SeekBar satBar;
    private SeekBar vigBar;
    private TextView brightVal;
    private TextView contrastVal;
    private TextView warmthVal;
    private TextView satVal;
    private TextView vigVal;
    private final Map<ScientificVisualSubstrate.BaselinePlate, Button> baselineChips = new LinkedHashMap<>();
    private final Map<ImageLabEngine.FilterPreset, Button> filterChips = new LinkedHashMap<>();

    // Video Maker widgets & active chip registries
    private ImageView videoPreview;
    private Button videoPlayToggleBtn;
    private EditText videoTitleInput;
    private EditText videoSubInput;
    private TextView videoStatus;
    private Button saveVideoGalleryBtn;
    private Button shareVideoBtn;
    private final Map<VideoMakerEngine.Style, Button> styleChips = new LinkedHashMap<>();
    private final Map<VideoMakerEngine.Palette, Button> paletteChips = new LinkedHashMap<>();
    private final Map<Integer, Button> durationChips = new LinkedHashMap<>();

    private final Runnable videoPreviewTick = new Runnable() {
        @Override
        public void run() {
            if (!videoPreviewPlaying || isImageTab || isFinishing() || isDestroyed()) {
                return;
            }
            videoPreviewT = (videoPreviewT + 0.022f) % 1.0f;
            renderVideoPreviewFrame();
            previewHandler.postDelayed(this, 50L);
        }
    };

    private final ActivityResultLauncher<String[]> pickPhotoLauncher =
            registerForActivityResult(new ActivityResultContracts.OpenDocument(), uri -> {
                if (uri != null) {
                    loadPickedPhoto(uri);
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sourceBitmap = ImageLabEngine.createAtelierStarterBitmap(PLATE_W, PLATE_H);

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        LinearLayout header = Ui.vertical(this);
        header.setBackgroundColor(Color.TRANSPARENT);
        header.setPadding(Ui.dp(this, 16), Ui.dp(this, 4), Ui.dp(this, 16), Ui.dp(this, 4));
        header.addView(Ui.topBar(this, "Creative Studio", "Photos · Art · 30fps Video"));

        // Clean segmented pill bar (20dp concentric geometry)
        LinearLayout tabRow = new LinearLayout(this);
        tabRow.setOrientation(LinearLayout.HORIZONTAL);
        tabRow.setBackground(Ui.cardBackground(this, 20));
        tabRow.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4));
        tabImageBtn = pillChip("Image Lab", v -> showTab(true));
        tabImageBtn.setId(R.id.studio_tab_image);
        tabVideoBtn = pillChip("Video Maker", v -> showTab(false));
        tabVideoBtn.setId(R.id.studio_tab_video);
        LinearLayout.LayoutParams tlp = new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f);
        tlp.setMargins(0, 0, Ui.dp(this, 6), 0);
        tabRow.addView(tabImageBtn, tlp);
        tabRow.addView(tabVideoBtn, new LinearLayout.LayoutParams(0, Ui.dp(this, 38), 1f));
        header.addView(tabRow);

        status = Ui.text(this, "Hold preview to compare original.", 12.5f, Ui.MUTED);
        status.setId(R.id.studio_status);
        status.setMaxLines(1);
        status.setEllipsize(android.text.TextUtils.TruncateAt.END);
        status.setPadding(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 2));
        header.addView(status);
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        scroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout body = Ui.vertical(this);
        body.setBackgroundColor(Color.TRANSPARENT);
        body.setPadding(Ui.dp(this, 16), Ui.dp(this, 8), Ui.dp(this, 16), Ui.dp(this, 32));

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
        panel.setBackgroundColor(Color.TRANSPARENT);

        imagePreview = new ImageView(this);
        imagePreview.setId(R.id.studio_image_preview);
        imagePreview.setContentDescription("Creative Studio image preview. Press and hold to compare original.");
        imagePreview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        imagePreview.setBackground(Ui.cardBackground(this, 20));
        imagePreview.setPadding(Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8));
        imagePreview.setOnTouchListener((v, ev) -> {
            if (drawMode && editedBitmap != null) {
                int action = ev.getActionMasked();
                float vx = ev.getX() - imagePreview.getPaddingLeft();
                float vy = ev.getY() - imagePreview.getPaddingTop();
                float[] pts = {vx, vy};
                if (imagePreview.getImageMatrix().invert(inverseImageMatrix)) {
                    inverseImageMatrix.mapPoints(pts);
                }
                float nx = Math.max(0f, Math.min(1f, pts[0] / Math.max(1f, editedBitmap.getWidth())));
                float ny = Math.max(0f, Math.min(1f, pts[1] / Math.max(1f, editedBitmap.getHeight())));
                if (action == MotionEvent.ACTION_DOWN) {
                    if (v.getParent() != null) {
                        v.getParent().requestDisallowInterceptTouchEvent(true);
                    }
                    pushUndo();
                    activeStroke = new ImageLabEngine.BrushStroke(activeInkColor, activeBrushWidthNorm);
                    activeStroke.points.add(new float[]{nx, ny});
                    editSpec.strokes.add(activeStroke);
                    refreshImagePreview();
                    return true;
                } else if (action == MotionEvent.ACTION_MOVE && activeStroke != null) {
                    float[] last = activeStroke.points.get(activeStroke.points.size() - 1);
                    if (Math.hypot(nx - last[0], ny - last[1]) >= 0.006) {
                        activeStroke.points.add(new float[]{nx, ny});
                        refreshImagePreview();
                    }
                    return true;
                } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
                    if (v.getParent() != null) {
                        v.getParent().requestDisallowInterceptTouchEvent(false);
                    }
                    activeStroke = null;
                    status.setText("Ink layer updated (" + editSpec.strokes.size()
                            + (editSpec.strokes.size() == 1 ? " stroke)." : " strokes)."));
                    return true;
                }
                return true;
            }
            if (ev.getAction() == MotionEvent.ACTION_DOWN && sourceBitmap != null) {
                imagePreview.setImageBitmap(sourceBitmap);
                editSummary.setText("Comparing: Original (release to return)");
                return true;
            } else if (ev.getAction() == MotionEvent.ACTION_UP || ev.getAction() == MotionEvent.ACTION_CANCEL) {
                if (editedBitmap != null) {
                    imagePreview.setImageBitmap(editedBitmap);
                }
                editSummary.setText(editSpec.summary());
                return true;
            }
            return false;
        });
        LinearLayout.LayoutParams imgLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 260));
        imgLp.setMargins(0, 0, 0, Ui.dp(this, 8));
        panel.addView(imagePreview, imgLp);

        editSummary = Ui.text(this, "Original", 12.5f, Ui.MUTED);
        editSummary.setId(R.id.studio_edit_summary);
        editSummary.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), Ui.dp(this, 2));
        panel.addView(editSummary);

        baselineMeta = Ui.text(this,
                "Baseline: " + activeBaseline.lineage + " · " + activeBaseline.mathSummary,
                11f, Ui.MUTED);
        baselineMeta.setId(R.id.studio_baseline_meta);
        baselineMeta.setMaxLines(2);
        baselineMeta.setEllipsize(android.text.TextUtils.TruncateAt.END);
        baselineMeta.setPadding(Ui.dp(this, 4), 0, Ui.dp(this, 4), Ui.dp(this, 6));
        panel.addView(baselineMeta);

        // 10 HD Scientific-Aesthetic Procedural Baselines (active chip highlighted!)
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
            } else if (plate == ScientificVisualSubstrate.BaselinePlate.CHLADNI_PLATE) {
                pb.setId(R.id.studio_baseline_chladni);
            } else if (plate == ScientificVisualSubstrate.BaselinePlate.FIBONACCI_PHYLLOTAXIS) {
                pb.setId(R.id.studio_baseline_phyllotaxis);
            } else if (plate == ScientificVisualSubstrate.BaselinePlate.VORONOI_CRYSTAL) {
                pb.setId(R.id.studio_baseline_voronoi);
            } else if (plate == ScientificVisualSubstrate.BaselinePlate.LISSAJOUS_ORBIT) {
                pb.setId(R.id.studio_baseline_lissajous);
            }
            baselineChips.put(plate, pb);
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
        cmdRow.setPadding(Ui.dp(this, 12), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));
        commandInput = new EditText(this);
        commandInput.setId(R.id.studio_command_input);
        commandInput.setHint("Try warm, voronoi, lissajous, blur…");
        commandInput.setSingleLine(true);
        commandInput.setImeOptions(EditorInfo.IME_ACTION_DONE);
        commandInput.setTextColor(Ui.textColor(this));
        commandInput.setHintTextColor(Ui.mutedColor(this));
        commandInput.setBackground(null);
        commandInput.setTextSize(14f);
        Runnable runCommand = () -> {
            String cmd = commandInput.getText() == null ? "" : commandInput.getText().toString().trim();
            if (!cmd.isEmpty()) {
                ScientificVisualSubstrate.BaselinePlate detectedPlate =
                        ScientificVisualSubstrate.detectPlateFromCommand(cmd);
                if (detectedPlate != null) {
                    applyScientificBaseline(detectedPlate, cmd);
                    commandInput.setText("");
                    return;
                }
                pushUndo();
                editSpec = ImageLabEngine.parseEditCommand(cmd, editSpec);
                commandInput.setText("");
                refreshImagePreview();
                status.setText("Applied edit: " + editSpec.summary());
            }
        };
        commandInput.setOnEditorActionListener((v, actionId, ev) -> {
            if (actionId == EditorInfo.IME_ACTION_DONE
                    || (ev != null && ev.getKeyCode() == KeyEvent.KEYCODE_ENTER && ev.getAction() == KeyEvent.ACTION_DOWN)) {
                runCommand.run();
                return true;
            }
            return false;
        });
        Button applyCmdBtn = Ui.primaryButton(this, "Apply", Ui.COBALT, v -> runCommand.run());
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

        // 12 Film & Archival Filter Presets (active chip highlighted!)
        HorizontalScrollView filterScroll = new HorizontalScrollView(this);
        filterScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout filterRow = new LinearLayout(this);
        filterRow.setOrientation(LinearLayout.HORIZONTAL);
        for (ImageLabEngine.FilterPreset preset : ImageLabEngine.FilterPreset.values()) {
            Button fb = pillChip(preset.label, v -> {
                pushUndo();
                editSpec.filter = preset;
                refreshImagePreview();
                status.setText("Filter: " + preset.label);
            });
            filterChips.put(preset, fb);
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

        // Precision Studio Tool Strip (Undo · Tune · ✎ Draw · Rotate · Crop · Flip · Blur · Reset)
        HorizontalScrollView toolScroll = new HorizontalScrollView(this);
        toolScroll.setHorizontalScrollBarEnabled(false);
        LinearLayout toolRow = new LinearLayout(this);
        toolRow.setOrientation(LinearLayout.HORIZONTAL);

        undoBtn = pillChip("Undo", v -> popUndo());
        undoBtn.setId(R.id.studio_undo_btn);

        Button rotateBtn = pillChip("Rotate 90°", v -> {
            pushUndo();
            editSpec.rotationDeg = (editSpec.rotationDeg + 90) % 360;
            refreshImagePreview();
        });
        flipBtn = pillChip("Flip ↔", v -> {
            pushUndo();
            editSpec.flipHorizontal = !editSpec.flipHorizontal;
            refreshImagePreview();
        });
        cropBtn = pillChip("Crop: Orig", v -> {
            pushUndo();
            ImageLabEngine.CropMode[] modes = ImageLabEngine.CropMode.values();
            editSpec.crop = modes[(editSpec.crop.ordinal() + 1) % modes.length];
            refreshImagePreview();
        });
        blurBtn = pillChip("Blur: off", v -> {
            pushUndo();
            editSpec.privacyBlur = !editSpec.privacyBlur;
            refreshImagePreview();
        });
        adjustToggleBtn = pillChip("Tune ▾", v -> {
            boolean open = adjustDrawer.getVisibility() != View.VISIBLE;
            adjustDrawer.setVisibility(open ? View.VISIBLE : View.GONE);
            adjustToggleBtn.setText(open ? "Tune ▴" : "Tune ▾");
            styleChip(adjustToggleBtn, open);
        });
        adjustToggleBtn.setId(R.id.studio_adjust_toggle);

        drawToggleBtn = pillChip("✎ Draw", v -> {
            drawMode = !drawMode;
            drawDrawer.setVisibility(drawMode ? View.VISIBLE : View.GONE);
            drawToggleBtn.setText(drawMode ? "✎ Drawing" : "✎ Draw");
            styleChip(drawToggleBtn, drawMode);
            status.setText(drawMode
                    ? "Draw mode ON — sketch directly on canvas with your finger."
                    : "Draw mode OFF — hold preview to compare original.");
        });
        drawToggleBtn.setId(R.id.studio_draw_toggle);

        Button resetBtn = pillChip("Reset", v -> {
            pushUndo();
            editSpec = new ImageLabEngine.EditSpec();
            refreshImagePreview();
            status.setText("Reset edits to clean plate.");
        });
        for (Button tb : new Button[]{undoBtn, adjustToggleBtn, drawToggleBtn, rotateBtn, cropBtn, flipBtn, blurBtn, resetBtn}) {
            LinearLayout.LayoutParams tlp2 = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 36));
            tlp2.setMargins(0, 0, Ui.dp(this, 6), 0);
            toolRow.addView(tb, tlp2);
        }
        toolScroll.addView(toolRow);
        LinearLayout.LayoutParams tsLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        tsLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        panel.addView(toolScroll, tsLp);

        // Collapsible Live Vector Ink Bar (6 Ink Swatches · S/M/L Nib · Clear Ink)
        drawDrawer = Ui.vertical(this);
        drawDrawer.setBackground(Ui.cardBackground(this, 20));
        drawDrawer.setPadding(Ui.dp(this, 12), Ui.dp(this, 10), Ui.dp(this, 12), Ui.dp(this, 10));
        drawDrawer.setVisibility(View.GONE);

        LinearLayout colorRow = new LinearLayout(this);
        colorRow.setOrientation(LinearLayout.HORIZONTAL);
        colorRow.setGravity(Gravity.CENTER_VERTICAL);
        String[] colorNames = {"Gold", "Cyan", "Ruby", "Emerald", "White", "Ink"};
        for (int i = 0; i < inkPaletteColors.length; i++) {
            final int col = inkPaletteColors[i];
            Button sw = new Button(this);
            sw.setContentDescription("Ink color " + colorNames[i]);
            sw.setStateListAnimator(null);
            sw.setOnClickListener(Ui.withHaptic(v -> {
                activeInkColor = col;
                refreshDrawPaletteStates();
            }));
            Ui.attachPressSpring(sw);
            inkColorBtns.add(sw);
            LinearLayout.LayoutParams swLp = new LinearLayout.LayoutParams(Ui.dp(this, 32), Ui.dp(this, 32));
            swLp.setMargins(0, 0, Ui.dp(this, 8), 0);
            colorRow.addView(sw, swLp);
        }
        drawDrawer.addView(colorRow);

        LinearLayout nibRow = new LinearLayout(this);
        nibRow.setOrientation(LinearLayout.HORIZONTAL);
        nibRow.setGravity(Gravity.CENTER_VERTICAL);
        nibRow.setPadding(0, Ui.dp(this, 8), 0, 0);
        String[] sizeLabels = {"S", "M", "L"};
        for (int i = 0; i < brushWidths.length; i++) {
            final float wNorm = brushWidths[i];
            Button sb = pillChip(sizeLabels[i], v -> {
                activeBrushWidthNorm = wNorm;
                refreshDrawPaletteStates();
            });
            sb.setMinWidth(Ui.dp(this, 44));
            sb.setMinimumWidth(Ui.dp(this, 44));
            sb.setPadding(Ui.dp(this, 12), 0, Ui.dp(this, 12), 0);
            brushSizeBtns.add(sb);
            LinearLayout.LayoutParams sbLp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32));
            sbLp.setMargins(0, 0, Ui.dp(this, 8), 0);
            nibRow.addView(sb, sbLp);
        }
        Button clearInkBtn = pillChip("Clear Ink", v -> {
            if (!editSpec.strokes.isEmpty()) {
                pushUndo();
                editSpec.strokes.clear();
                refreshImagePreview();
                status.setText("Cleared hand-drawn ink layer.");
            }
        });
        clearInkBtn.setMinWidth(0);
        clearInkBtn.setMinimumWidth(0);
        clearInkBtn.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.primaryAccent(this), 16));
        nibRow.addView(clearInkBtn, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 32)));
        drawDrawer.addView(nibRow);
        refreshDrawPaletteStates();

        LinearLayout.LayoutParams ddLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        ddLp.setMargins(0, 0, 0, Ui.dp(this, 10));
        panel.addView(drawDrawer, ddLp);

        // Collapsible Precision Tune Sliders Card (Brightness · Contrast · Warmth · Saturation · Vignette)
        adjustDrawer = Ui.vertical(this);
        adjustDrawer.setBackground(Ui.cardBackground(this, 20));
        adjustDrawer.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        adjustDrawer.setVisibility(View.GONE);

        brightVal = Ui.text(this, "0", 12f, Ui.COBALT);
        brightBar = addSliderRow(adjustDrawer, "Brightness", 120, 60, brightVal, p -> {
            editSpec.brightness = p - 60;
            refreshImagePreview();
        });
        contrastVal = Ui.text(this, "1.0x", 12f, Ui.COBALT);
        contrastBar = addSliderRow(adjustDrawer, "Contrast", 130, 50, contrastVal, p -> {
            editSpec.contrast = 0.5f + (p / 100f);
            refreshImagePreview();
        });
        warmthVal = Ui.text(this, "0", 12f, Ui.COBALT);
        warmthBar = addSliderRow(adjustDrawer, "Warmth", 80, 40, warmthVal, p -> {
            editSpec.warmth = p - 40;
            refreshImagePreview();
        });
        satVal = Ui.text(this, "100%", 12f, Ui.COBALT);
        satBar = addSliderRow(adjustDrawer, "Saturation", 200, 100, satVal, p -> {
            editSpec.saturation = p / 100f;
            refreshImagePreview();
        });
        vigVal = Ui.text(this, "0%", 12f, Ui.COBALT);
        vigBar = addSliderRow(adjustDrawer, "Vignette", 100, 0, vigVal, p -> {
            editSpec.vignette = p;
            refreshImagePreview();
        });
        LinearLayout.LayoutParams adjLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        adjLp.setMargins(0, 0, 0, Ui.dp(this, 12));
        panel.addView(adjustDrawer, adjLp);

        // Symmetrical Primary Action Row (Pick Photo | Save to Photos) + Secondary Row (Share PNG | Turn into Reel | AI Art)
        Button pickBtn = Ui.button(this, "Pick Photo", Ui.COBALT, v -> pickPhotoLauncher.launch(new String[]{"image/*"}));
        Button saveGalleryBtn = Ui.primaryButton(this, "Save to Photos", Ui.GREEN, v -> saveImageToGallery());
        saveGalleryBtn.setId(R.id.studio_save_gallery);
        panel.addView(Ui.buttonRow(this, pickBtn, saveGalleryBtn));

        Button sharePngBtn = Ui.disclosureButton(this, "Share PNG", v -> shareEditedImage());
        Button toVideoBtn = Ui.disclosureButton(this, "Photo Reel →", v -> {
            videoSpec.style = VideoMakerEngine.Style.PHOTO_STORY_REEL;
            showTab(false);
            refreshVideoPreview();
            status.setText("Loaded edited artwork into 30fps Photo Story Reel!");
        });
        panel.addView(Ui.buttonRow(this, sharePngBtn, toVideoBtn));

        Button aiGenBtn = Ui.disclosureButton(this, "✨ AI Art (Gemini / OpenAI Key)", v -> generateOnlineAiImage());
        panel.addView(aiGenBtn);

        return panel;
    }

    private LinearLayout buildVideoMakerPanel() {
        LinearLayout panel = Ui.vertical(this);
        panel.setBackgroundColor(Color.TRANSPARENT);

        videoPreview = new ImageView(this);
        videoPreview.setId(R.id.studio_video_preview);
        videoPreview.setContentDescription("Live animated video preview. Tap to play or pause.");
        videoPreview.setScaleType(ImageView.ScaleType.FIT_CENTER);
        videoPreview.setBackground(Ui.cardBackground(this, 20));
        videoPreview.setPadding(Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8), Ui.dp(this, 8));
        videoPreview.setClickable(true);
        videoPreview.setFocusable(true);
        videoPreview.setOnClickListener(Ui.withHaptic(v -> toggleVideoPreviewPlayback()));
        LinearLayout.LayoutParams vpLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 250));
        vpLp.setMargins(0, 0, 0, Ui.dp(this, 8));
        panel.addView(videoPreview, vpLp);

        // Play / Pause Live Preview + Duration Selector Row (4s · 6s · 8s)
        LinearLayout playRow = new LinearLayout(this);
        playRow.setOrientation(LinearLayout.HORIZONTAL);
        playRow.setGravity(Gravity.CENTER_VERTICAL);
        videoPlayToggleBtn = pillChip("▶ Preview", v -> toggleVideoPreviewPlayback());
        videoPlayToggleBtn.setId(R.id.studio_video_play_toggle);
        LinearLayout.LayoutParams plBtnLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
        plBtnLp.setMargins(0, 0, Ui.dp(this, 10), 0);
        playRow.addView(videoPlayToggleBtn, plBtnLp);

        for (int sec : new int[]{4, 6, 8}) {
            Button db = pillChip(sec + "s HD", v -> {
                videoSpec.durationSec = sec;
                refreshVideoChipStates();
                videoStatus.setText("Ready: " + VideoMakerEngine.WIDTH + "×" + VideoMakerEngine.HEIGHT
                        + " @ " + VideoMakerEngine.FPS + "fps CFR (" + sec + "s H.264 offline).");
            });
            durationChips.put(sec, db);
            LinearLayout.LayoutParams dlp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            dlp.setMargins(0, 0, Ui.dp(this, 6), 0);
            playRow.addView(db, dlp);
        }
        LinearLayout.LayoutParams prLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        prLp.setMargins(0, 0, 0, Ui.dp(this, 8));
        panel.addView(playRow, prLp);

        // 5 Offline Animated Video Styles (active chip highlighted!)
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
            styleChips.put(st, sb);
            LinearLayout.LayoutParams slp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            slp.setMargins(0, 0, Ui.dp(this, 6), 0);
            styleRow.addView(sb, slp);
        }
        styleScroll.addView(styleRow);
        panel.addView(styleScroll);

        // 4 Color Palettes (active chip highlighted!)
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
            paletteChips.put(pal, pb);
            LinearLayout.LayoutParams plp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 34));
            plp.setMargins(0, 0, Ui.dp(this, 6), 0);
            palRow.addView(pb, plp);
        }
        palScroll.addView(palRow);
        panel.addView(palScroll);

        TextWatcher liveTitleWatcher = new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {}
            @Override public void afterTextChanged(Editable s) {
                refreshVideoPreview();
            }
        };
        videoTitleInput = styledInput("Video title (e.g. Made with Zoe)", videoSpec.title);
        videoSubInput = styledInput("Caption / subtitle", videoSpec.subtitle);
        videoTitleInput.addTextChangedListener(liveTitleWatcher);
        videoSubInput.addTextChangedListener(liveTitleWatcher);
        panel.addView(videoTitleInput);
        panel.addView(videoSubInput);

        videoStatus = Ui.text(this,
                "Encodes 720×720 HD @ 30fps exact-CFR H.264 .mp4 100% offline.", 12.5f, Ui.MUTED);
        videoStatus.setId(R.id.studio_video_status);
        videoStatus.setPadding(Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 10));
        panel.addView(videoStatus);

        Button renderBtn = Ui.primaryButton(this, "🎬 Create HD MP4", Ui.COBALT, v -> exportOfflineMp4());
        renderBtn.setId(R.id.studio_render_mp4);
        saveVideoGalleryBtn = Ui.button(this, "Save to Movies", Ui.GREEN, v -> saveVideoToGallery());
        saveVideoGalleryBtn.setId(R.id.studio_video_save_gallery);
        saveVideoGalleryBtn.setEnabled(false);
        panel.addView(Ui.buttonRow(this, renderBtn, saveVideoGalleryBtn));

        shareVideoBtn = Ui.disclosureButton(this, "Share MP4", v -> shareExportedVideo());
        shareVideoBtn.setEnabled(false);
        Button soundBtn = Ui.disclosureButton(this, "Preview Zoe Sound", v -> {
            status.setText("Playing Zoe's 44.1 kHz native soprano theme…");
            nativeVoice.singZoe(null);
        });
        panel.addView(Ui.buttonRow(this, shareVideoBtn, soundBtn));

        Button recordBtn = Ui.disclosureButton(this, "Record Live Camera Clip", v -> {
            try {
                startActivity(new Intent(MediaStore.ACTION_VIDEO_CAPTURE));
            } catch (ActivityNotFoundException ignored) {
                status.setText("No built-in video recorder available.");
            }
        });
        panel.addView(recordBtn);

        return panel;
    }

    private interface IntConsumer {
        void accept(int value);
    }

    private SeekBar addSliderRow(LinearLayout parent, String label, int max, int initial,
                                 TextView valView, IntConsumer onChange) {
        LinearLayout header = new LinearLayout(this);
        header.setOrientation(LinearLayout.HORIZONTAL);
        TextView lbl = Ui.text(this, label, 12.5f, Ui.TEXT);
        header.addView(lbl, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        header.addView(valView);
        parent.addView(header);

        SeekBar bar = new SeekBar(this);
        bar.setMax(max);
        bar.setProgress(initial);
        bar.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                if (fromUser && !syncingSliders) {
                    onChange.accept(progress);
                }
            }
            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
                pushUndo();
            }
            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {}
        });
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, Ui.dp(this, 6));
        parent.addView(bar, lp);
        return bar;
    }

    private EditText styledInput(String hint, String initial) {
        EditText et = Ui.input(this, initial, hint);
        et.setSingleLine(true);
        et.setMinHeight(Ui.dp(this, 46));
        et.setMinimumHeight(Ui.dp(this, 46));
        et.setTextSize(14.5f);
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
        b.setOnClickListener(Ui.withHaptic(listener));
        Ui.attachPressSpring(b);
        return b;
    }

    private void refreshDrawPaletteStates() {
        int ring = Ui.primaryAccent(this);
        for (int i = 0; i < inkColorBtns.size() && i < inkPaletteColors.length; i++) {
            int col = inkPaletteColors[i];
            boolean sel = col == activeInkColor;
            Button b = inkColorBtns.get(i);
            if (sel) {
                b.setBackground(Ui.outlinedPillDrawable(this, col, ring, ring, 99));
                b.setScaleX(1.12f);
                b.setScaleY(1.12f);
            } else {
                b.setBackground(Ui.outlinedPillDrawable(this, col, Ui.dividerColor(this), ring, 99));
                b.setScaleX(1.0f);
                b.setScaleY(1.0f);
            }
        }
        for (int i = 0; i < brushSizeBtns.size() && i < brushWidths.length; i++) {
            Button btn = brushSizeBtns.get(i);
            boolean sel = Math.abs(brushWidths[i] - activeBrushWidthNorm) < 0.002f;
            if (sel) {
                btn.setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
                btn.setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 16));
            } else {
                btn.setTextColor(Ui.textColor(this));
                btn.setBackground(Ui.tonalPillDrawable(this, Ui.tonalWellColor(this), Ui.primaryAccent(this), 16));
            }
        }
    }

    private void styleChip(Button btn, boolean selected) {
        if (btn == null) {
            return;
        }
        if (selected) {
            btn.setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 18));
        } else {
            btn.setTextColor(Ui.textColor(this));
            btn.setBackground(Ui.tonalPillDrawable(this, Ui.panelColor(this), Ui.primaryAccent(this), 18));
        }
    }

    private void showTab(boolean imageTab) {
        this.isImageTab = imageTab;
        imagePanel.setVisibility(imageTab ? View.VISIBLE : View.GONE);
        videoPanel.setVisibility(imageTab ? View.GONE : View.VISIBLE);
        styleTab(tabImageBtn, imageTab);
        styleTab(tabVideoBtn, !imageTab);
        if (imageTab) {
            stopVideoPreviewPlayback();
        } else {
            refreshVideoPreview();
        }
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

    private void pushUndo() {
        undoStack.push(editSpec.copy());
        while (undoStack.size() > MAX_UNDO) {
            undoStack.removeLast();
        }
        updateUndoButton();
    }

    private void popUndo() {
        if (undoStack.isEmpty()) {
            status.setText("Nothing to undo.");
            return;
        }
        editSpec = undoStack.pop();
        refreshImagePreview();
        status.setText("Undid last edit (" + undoStack.size() + " left).");
    }

    private void updateUndoButton() {
        if (undoBtn != null) {
            boolean hasUndo = !undoStack.isEmpty();
            undoBtn.setEnabled(hasUndo);
            undoBtn.setAlpha(hasUndo ? 1.0f : 0.45f);
            undoBtn.setText(hasUndo ? "Undo (" + undoStack.size() + ")" : "Undo");
        }
    }

    private void loadPickedPhoto(Uri uri) {
        status.setText("Loading photo…");
        executor.execute(() -> {
            try {
                Bitmap bmp = MediaChatHelper.decodeScaledBitmap(this, uri, 1600);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        sourceBitmap = bmp;
                        undoStack.clear();
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
        styleChip(blurBtn, editSpec.privacyBlur);
        flipBtn.setText(editSpec.flipHorizontal ? "Flip: on" : "Flip ↔");
        styleChip(flipBtn, editSpec.flipHorizontal);
        cropBtn.setText("Crop: " + editSpec.crop.label);
        styleChip(cropBtn, editSpec.crop != ImageLabEngine.CropMode.ORIGINAL);
        updateUndoButton();

        for (Map.Entry<ScientificVisualSubstrate.BaselinePlate, Button> e : baselineChips.entrySet()) {
            styleChip(e.getValue(), e.getKey() == activeBaseline);
        }
        for (Map.Entry<ImageLabEngine.FilterPreset, Button> e : filterChips.entrySet()) {
            styleChip(e.getValue(), e.getKey() == editSpec.filter);
        }

        syncingSliders = true;
        if (brightBar != null) {
            brightBar.setProgress(Math.max(0, Math.min(120, editSpec.brightness + 60)));
            brightVal.setText((editSpec.brightness > 0 ? "+" : "") + editSpec.brightness);
        }
        if (contrastBar != null) {
            contrastBar.setProgress(Math.max(0, Math.min(130, Math.round((editSpec.contrast - 0.5f) * 100f))));
            contrastVal.setText(String.format(Locale.US, "%.1fx", editSpec.contrast));
        }
        if (warmthBar != null) {
            warmthBar.setProgress(Math.max(0, Math.min(80, editSpec.warmth + 40)));
            warmthVal.setText((editSpec.warmth > 0 ? "+" : "") + editSpec.warmth);
        }
        if (satBar != null) {
            satBar.setProgress(Math.max(0, Math.min(200, Math.round(editSpec.saturation * 100f))));
            satVal.setText(Math.round(editSpec.saturation * 100f) + "%");
        }
        if (vigBar != null) {
            vigBar.setProgress(Math.max(0, Math.min(100, editSpec.vignette)));
            vigVal.setText(editSpec.vignette + "%");
        }
        syncingSliders = false;
    }

    private void refreshVideoChipStates() {
        for (Map.Entry<VideoMakerEngine.Style, Button> e : styleChips.entrySet()) {
            styleChip(e.getValue(), e.getKey() == videoSpec.style);
        }
        for (Map.Entry<VideoMakerEngine.Palette, Button> e : paletteChips.entrySet()) {
            styleChip(e.getValue(), e.getKey() == videoSpec.palette);
        }
        for (Map.Entry<Integer, Button> e : durationChips.entrySet()) {
            styleChip(e.getValue(), e.getKey() == videoSpec.durationSec);
        }
    }

    private void refreshVideoPreview() {
        videoSpec.title = videoTitleInput == null ? videoSpec.title : videoTitleInput.getText().toString();
        videoSpec.subtitle = videoSubInput == null ? videoSpec.subtitle : videoSubInput.getText().toString();
        refreshVideoChipStates();
        renderVideoPreviewFrame();
    }

    private void renderVideoPreviewFrame() {
        if (videoPreview == null) {
            return;
        }
        if (videoPreviewBitmap == null || videoPreviewBitmap.isRecycled()) {
            videoPreviewBitmap = Bitmap.createBitmap(480, 480, Bitmap.Config.ARGB_8888);
        }
        Canvas c = new Canvas(videoPreviewBitmap);
        VideoMakerEngine.renderFrame(c, 480, 480, editedBitmap, videoSpec, videoPreviewT);
        videoPreview.setImageBitmap(videoPreviewBitmap);
        videoPreview.invalidate();
    }

    private void toggleVideoPreviewPlayback() {
        if (videoPreviewPlaying) {
            stopVideoPreviewPlayback();
        } else {
            videoPreviewPlaying = true;
            if (videoPlayToggleBtn != null) {
                videoPlayToggleBtn.setText("⏸ Pause");
                styleChip(videoPlayToggleBtn, true);
            }
            previewHandler.removeCallbacks(videoPreviewTick);
            previewHandler.post(videoPreviewTick);
        }
    }

    private void stopVideoPreviewPlayback() {
        videoPreviewPlaying = false;
        previewHandler.removeCallbacks(videoPreviewTick);
        if (videoPlayToggleBtn != null) {
            videoPlayToggleBtn.setText("▶ Preview");
            styleChip(videoPlayToggleBtn, false);
        }
    }

    private void saveImageToGallery() {
        if (editedBitmap == null) {
            return;
        }
        Bitmap snap = editedBitmap;
        String name = "zoe_studio_" + System.currentTimeMillis() + ".png";
        status.setText("Saving HD PNG to Photos/Zoe Studio…");
        executor.execute(() -> {
            try {
                ImageLabEngine.saveToGallery(this, snap, name);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Saved to Photos → Pictures/Zoe Studio (" + snap.getWidth() + "×" + snap.getHeight() + " PNG).");
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        status.setText("Gallery save failed: " + err.getMessage());
                    }
                });
            }
        });
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
            startActivity(Intent.createChooser(share, "Share Zoe image"));
            status.setText("Exported HD PNG ready to share.");
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
        sourceBitmap = ScientificVisualSubstrate.renderScientificPlate(plate, concept, PLATE_W, PLATE_H);
        undoStack.clear();
        editSpec = new ImageLabEngine.EditSpec();
        refreshImagePreview();
        refreshVideoPreview();
        if (baselineMeta != null) {
            baselineMeta.setText("Baseline: " + plate.lineage + " · " + plate.mathSummary);
        }
        status.setText(plate.chipLabel + " HD plate ready · hold preview to compare.");
    }

    private void generateOnlineAiImage() {
        String prompt = commandInput.getText() == null ? "" : commandInput.getText().toString().trim();
        if (prompt.isEmpty()) {
            status.setText("Type an image idea in the command box above first, then tap AI Art (grounded by " + activeBaseline.chipLabel + ").");
            return;
        }
        String groundedPrompt = ScientificVisualSubstrate.augmentPromptWithBaseline(prompt, activeBaseline);
        status.setText("Generating online AI artwork grounded in " + activeBaseline.lineage + "…");
        executor.execute(() -> {
            try {
                Bitmap bmp = ImageLabEngine.generateOnlineImage(this, groundedPrompt);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        sourceBitmap = bmp;
                        undoStack.clear();
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
        stopVideoPreviewPlayback();
        videoSpec.title = videoTitleInput.getText().toString().trim();
        videoSpec.subtitle = videoSubInput.getText().toString().trim();
        refreshVideoPreview();
        videoStatus.setText("Encoding " + VideoMakerEngine.WIDTH + "×" + VideoMakerEngine.HEIGHT
                + " @ " + VideoMakerEngine.FPS + "fps H.264 MP4 offline…");
        saveVideoGalleryBtn.setEnabled(false);
        shareVideoBtn.setEnabled(false);

        File outFile = new File(new File(getCacheDir(), "creative_studio"), "zoe_video_" + System.currentTimeMillis() + ".mp4");
        Bitmap photoSnap = editedBitmap;
        executor.execute(() -> {
            try {
                File mp4 = VideoMakerEngine.exportMp4(outFile, photoSnap, videoSpec, (idx, total) -> {
                    if (idx % 12 == 0 || idx == total) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed()) {
                                videoStatus.setText("Encoding HD frame " + idx + " / " + total + " (30fps CFR offline)…");
                            }
                        });
                    }
                });
                long kb = Math.max(1L, mp4.length() / 1024L);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        lastExportedVideo = mp4;
                        saveVideoGalleryBtn.setEnabled(true);
                        shareVideoBtn.setEnabled(true);
                        videoStatus.setText("Created " + videoSpec.durationSec + "s HD MP4 (" + kb + " KB · 720×720 30fps)! Save or Share.");
                        status.setText("HD Video ready (" + kb + " KB MP4).");
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

    private void saveVideoToGallery() {
        if (lastExportedVideo == null || !lastExportedVideo.isFile()) {
            return;
        }
        File snap = lastExportedVideo;
        String name = "zoe_reel_" + System.currentTimeMillis() + ".mp4";
        videoStatus.setText("Saving MP4 to Movies/Zoe Studio…");
        executor.execute(() -> {
            try {
                VideoMakerEngine.saveVideoToGallery(this, snap, name);
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        videoStatus.setText("Saved MP4 to Gallery → Movies/Zoe Studio!");
                        status.setText("Saved MP4 to Movies/Zoe Studio.");
                    }
                });
            } catch (Exception err) {
                runOnUiThread(() -> {
                    if (!isFinishing() && !isDestroyed()) {
                        videoStatus.setText("Save MP4 failed: " + err.getMessage());
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
            startActivity(Intent.createChooser(share, "Share Zoe HD MP4 Video"));
        } catch (Exception err) {
            status.setText("Share failed: " + err.getMessage());
        }
    }

    @Override
    protected void onPause() {
        stopVideoPreviewPlayback();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        stopVideoPreviewPlayback();
        super.onDestroy();
        nativeVoice.stop();
        executor.shutdownNow();
    }
}
