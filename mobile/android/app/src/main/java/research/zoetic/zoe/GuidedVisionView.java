package research.zoetic.zoe;

import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Matrix;
import android.media.Image;
import android.net.Uri;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.camera.core.Camera;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import com.google.android.gms.tasks.Task;
import com.google.android.gms.tasks.Tasks;
import com.google.common.util.concurrent.ListenableFuture;
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
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

final class GuidedVisionView extends ScrollView {
    private final MainActivity activity;
    private final PreviewView previewView;
    private final TextView placeholder;
    private final TextView status;
    private final LinearLayout paletteRow;
    private final TextView paletteText;
    private final TextView resultView;
    private final Button inspectButton;
    private final Button flipButton;
    private final Button torchButton;
    private final Button autoSpeakButton;
    private final Button saveJournalButton;
    private final Button sharePhotoButton;
    private final Button cloudAskButton;
    private final LinearLayout saveShareDrawer;
    private final Button saveShareToggle;
    private final TextRecognizer textRecognizer;
    private final ImageLabeler imageLabeler;
    private final ExecutorService analysisExecutor;
    private final AtomicBoolean captureRequested = new AtomicBoolean(false);
    private ProcessCameraProvider cameraProvider;
    private Camera activeCamera;
    private DeviceAiController deviceAi;
    private volatile boolean cameraStarted;
    private volatile boolean cameraStartRequested;
    private boolean useFrontCamera;
    private boolean torchEnabled;
    private boolean autoSpeak;
    private String lastOcr = "";
    private String lastLabels = "";
    private String lastPaletteSummary = "";
    private String lastDeviceAi = "";
    private String lastCloud = "";
    private byte[] lastFrameJpeg;
    private String spoken = "No observation yet. Start the camera, then inspect one frame.";
    private String shared = spoken;

    GuidedVisionView(MainActivity activity) {
        super(activity);
        this.activity = activity;
        setFillViewport(true);
        setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(activity);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(activity, 12), Ui.dp(activity, 4), Ui.dp(activity, 12), Ui.dp(activity, 20));
        addView(content);

        FrameLayout cameraFrame = new FrameLayout(activity);
        cameraFrame.setBackground(Ui.panelBackground(activity, android.graphics.Color.rgb(9, 17, 23), Ui.BORDER, 22));
        cameraFrame.setClipToOutline(true);
        previewView = new PreviewView(activity);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        previewView.setContentDescription("Camera preview. No frame is analyzed until Inspect is pressed.");
        cameraFrame.addView(previewView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        placeholder = Ui.text(activity,
                "Camera off · ready when you are.",
                14.5f, android.graphics.Color.rgb(216, 224, 232));
        placeholder.setGravity(android.view.Gravity.BOTTOM | android.view.Gravity.CENTER_HORIZONTAL);
        placeholder.setPadding(Ui.dp(activity, 12), 0, Ui.dp(activity, 12), Ui.dp(activity, 24));
        cameraFrame.addView(placeholder, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        cameraFrame.addView(new ViewfinderReticleView(activity), new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        content.addView(cameraFrame, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(activity, 240)));

        status = Ui.text(activity,
                "Camera and microphone are idle.",
                14, Ui.YELLOW);
        status.setId(R.id.vision_status);
        content.addView(status);
        textRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        imageLabeler = ImageLabeling.getClient(ImageLabelerOptions.DEFAULT_OPTIONS);
        analysisExecutor = Executors.newSingleThreadExecutor();

        Button start = Ui.primaryButton(activity, "Start camera", Ui.CYAN, view -> activity.startCamera());
        start.setId(R.id.start_camera);
        inspectButton = Ui.primaryButton(activity, "Inspect once", Ui.GREEN, view -> requestInspection());
        inspectButton.setId(R.id.inspect_button);
        inspectButton.setEnabled(false);
        content.addView(Ui.buttonRow(activity, start, inspectButton));

        Button listen = Ui.button(activity, "Voice", Ui.CYAN, view -> activity.startListening());
        listen.setId(R.id.listen_button);
        Button speak = Ui.button(activity, "Speak", Ui.PINK, view -> activity.repeatCurrent());
        speak.setId(R.id.speak_button);
        Button stop = Ui.button(activity, "Stop", Ui.RUBY, view -> activity.stopAllOutput());
        stop.setId(R.id.stop_button);
        content.addView(Ui.buttonRow(activity, listen, speak, stop));

        LinearLayout optionsDrawer = Ui.vertical(activity);
        optionsDrawer.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        optionsDrawer.setVisibility(GONE);
        flipButton = Ui.button(activity, "Lens: back", Ui.GOLD, view -> flipCamera());
        flipButton.setId(R.id.vision_flip_camera);
        torchButton = Ui.button(activity, "Flash: off", Ui.GOLD, view -> toggleTorch());
        torchButton.setId(R.id.vision_torch);
        autoSpeakButton = Ui.button(activity, "Auto-speak: off", Ui.PINK, view -> toggleAutoSpeak());
        autoSpeakButton.setId(R.id.vision_autospeak);
        optionsDrawer.addView(Ui.buttonRow(activity, flipButton, torchButton, autoSpeakButton));

        Button optionsToggle = Ui.disclosureButton(activity, "Camera options ▾", null);
        optionsToggle.setOnClickListener(view -> {
            boolean open = optionsDrawer.getVisibility() != VISIBLE;
            optionsDrawer.setVisibility(open ? VISIBLE : GONE);
            optionsToggle.setText(open ? "Camera options ▴" : "Camera options ▾");
        });
        content.addView(optionsToggle);
        content.addView(optionsDrawer);

        LinearLayout paletteCard = Ui.vertical(activity);
        paletteCard.setId(R.id.vision_palette);
        paletteCard.setBackground(Ui.panelBackground(activity, Ui.PANEL, Ui.withAlpha(Ui.GOLD, 120), 16));
        paletteCard.setPadding(Ui.dp(activity, 12), Ui.dp(activity, 10), Ui.dp(activity, 12), Ui.dp(activity, 10));
        paletteRow = new LinearLayout(activity);
        paletteRow.setOrientation(LinearLayout.HORIZONTAL);
        paletteCard.addView(paletteRow);
        paletteText = Ui.text(activity, "Color palette & light meter appear after Inspect once.", 13, Ui.GOLD);
        paletteCard.addView(paletteText);
        content.addView(paletteCard, Ui.margins(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, activity, 4));

        resultView = Ui.text(activity,
                "OCR and image labels will appear here after inspection.",
                15f, Ui.TEXT);
        resultView.setBackground(Ui.panelBackground(activity, Ui.GREEN, 16));
        resultView.setPadding(Ui.dp(activity, 14), Ui.dp(activity, 14), Ui.dp(activity, 14), Ui.dp(activity, 14));
        resultView.setTextIsSelectable(true);
        content.addView(resultView, Ui.margins(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, activity, 4));

        saveShareDrawer = Ui.vertical(activity);
        saveShareDrawer.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        saveShareDrawer.setVisibility(GONE);

        saveJournalButton = Ui.button(activity, "Save to Trip Journal", Ui.GREEN, view -> promptSaveToJournal());
        saveJournalButton.setId(R.id.vision_save_journal);
        saveJournalButton.setEnabled(false);
        sharePhotoButton = Ui.button(activity, "Show Photo to Gemini", Ui.GOLD, view -> sharePhotoWithApps());
        sharePhotoButton.setId(R.id.vision_share_photo);
        sharePhotoButton.setEnabled(false);
        saveShareDrawer.addView(Ui.buttonRow(activity, saveJournalButton, sharePhotoButton));

        cloudAskButton = Ui.button(activity, "Ask Cloud Vision", Ui.CYAN, view -> askCloudVision());
        cloudAskButton.setId(R.id.vision_cloud_ask);
        cloudAskButton.setEnabled(false);
        Button share = Ui.button(activity, "Share result", Ui.PINK, view -> activity.shareCurrent());
        share.setId(R.id.share_button);
        Button gemini = Ui.button(activity, "Open Gemini", Ui.GOLD, view -> activity.openGemini());
        gemini.setId(R.id.gemini_button);
        saveShareDrawer.addView(Ui.buttonRow(activity, cloudAskButton, share, gemini));

        if (DeviceAiController.hasRealAiCoreService(activity)) {
            saveShareDrawer.addView(Ui.buttonRow(activity,
                    Ui.button(activity, "Check device AI", Ui.CYAN, view -> ensureDeviceAi().check()),
                    Ui.button(activity, "Enable AI model", Ui.CYAN, view -> ensureDeviceAi().enable())));
        }

        saveShareToggle = Ui.disclosureButton(activity, "Save & share ▾", null);
        saveShareToggle.setOnClickListener(view -> {
            boolean open = saveShareDrawer.getVisibility() != VISIBLE;
            saveShareDrawer.setVisibility(open ? VISIBLE : GONE);
            saveShareToggle.setText(open ? "Save & share ▴" : "Save & share ▾");
        });
        content.addView(saveShareToggle);
        content.addView(saveShareDrawer);
    }

    void startCamera() {
        if (cameraStarted) {
            setStatus("Camera is already active. Choose Inspect once when ready.");
            return;
        }
        cameraStartRequested = true;
        final ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(activity);
        future.addListener(() -> {
            if (!cameraStartRequested || activity.isFinishing() || activity.isDestroyed()
                    || !"vision".equals(activity.currentVisible())) {
                return;
            }
            try {
                cameraProvider = future.get();
                bindCameraUseCases();
            } catch (Exception error) {
                setStatus("Camera could not start: " + error.getMessage());
            }
        }, ContextCompat.getMainExecutor(activity));
    }

    private void bindCameraUseCases() {
        if (cameraProvider == null) {
            return;
        }
        Preview preview = new Preview.Builder().build();
        preview.setSurfaceProvider(previewView.getSurfaceProvider());
        ImageAnalysis analysis = new ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build();
        analysis.setAnalyzer(analysisExecutor, this::analyze);
        CameraSelector selector = useFrontCamera
                ? CameraSelector.DEFAULT_FRONT_CAMERA
                : CameraSelector.DEFAULT_BACK_CAMERA;
        cameraProvider.unbindAll();
        activeCamera = cameraProvider.bindToLifecycle(activity, selector, preview, analysis);
        torchEnabled = false;
        torchButton.setText("Flash: off");
        torchButton.setEnabled(!useFrontCamera && activeCamera.getCameraInfo().hasFlashUnit());
        cameraStarted = true;
        placeholder.setVisibility(GONE);
        inspectButton.setEnabled(true);
        setStatus((useFrontCamera ? "Front" : "Back") + " camera active. No continuous analysis. Choose Inspect once.");
    }

    private void flipCamera() {
        useFrontCamera = !useFrontCamera;
        flipButton.setText(useFrontCamera ? "Lens: front" : "Lens: back");
        if (cameraStarted && cameraProvider != null) {
            try {
                bindCameraUseCases();
            } catch (Exception error) {
                setStatus("Could not switch lens: " + error.getMessage());
            }
        } else {
            setStatus("Selected " + (useFrontCamera ? "front" : "back") + " camera for next start.");
        }
    }

    private void toggleTorch() {
        if (!cameraStarted || activeCamera == null || !activeCamera.getCameraInfo().hasFlashUnit()) {
            setStatus("Flash/torch is unavailable on the active camera.");
            return;
        }
        torchEnabled = !torchEnabled;
        activeCamera.getCameraControl().enableTorch(torchEnabled);
        torchButton.setText(torchEnabled ? "Flash: on" : "Flash: off");
        setStatus(torchEnabled ? "Flashlight turned on." : "Flashlight turned off.");
    }

    private void toggleAutoSpeak() {
        autoSpeak = !autoSpeak;
        autoSpeakButton.setText(autoSpeak ? "Auto-speak: on" : "Auto-speak: off");
        setStatus(autoSpeak ? "Auto-speak enabled for inspections." : "Auto-speak turned off.");
    }

    void requestInspection() {
        if (!cameraStarted) {
            setStatus("Start the camera before inspecting a frame.");
            return;
        }
        if (!captureRequested.compareAndSet(false, true)) {
            return;
        }
        inspectButton.setEnabled(false);
        setStatus("Inspecting one frame with on-device OCR, labels, and light meter…");
    }

    private DeviceAiController ensureDeviceAi() {
        if (deviceAi == null) {
            deviceAi = new DeviceAiController(activity, this::setStatus);
        }
        return deviceAi;
    }

    private Bitmap orientedBitmap(ImageProxy imageProxy) {
        Bitmap bitmap = imageProxy.toBitmap();
        int rotation = imageProxy.getImageInfo().getRotationDegrees() % 360;
        if (rotation == 0) {
            return bitmap;
        }
        Matrix matrix = new Matrix();
        matrix.postRotate(rotation);
        Bitmap rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.getWidth(), bitmap.getHeight(), matrix, true);
        bitmap.recycle();
        return rotated;
    }

    @androidx.annotation.OptIn(markerClass = androidx.camera.core.ExperimentalGetImage.class)
    private void analyze(ImageProxy imageProxy) {
        if (!captureRequested.getAndSet(false)) {
            imageProxy.close();
            return;
        }
        try {
            Image mediaImage = imageProxy.getImage();
            if (mediaImage == null) {
                imageProxy.close();
                post(() -> {
                    inspectButton.setEnabled(cameraStarted);
                    setStatus("The selected frame had no readable image.");
                });
                return;
            }
            Bitmap bitmap = orientedBitmap(imageProxy);
            FramePalette.Analysis palette = FramePalette.analyzeBitmap(bitmap);
            byte[] jpegBytes = compressBoundedJpeg(bitmap);
            boolean aiReady = deviceAi != null && deviceAi.isReady();

            InputImage input = InputImage.fromMediaImage(mediaImage, imageProxy.getImageInfo().getRotationDegrees());
            Task<Text> textTask = textRecognizer.process(input);
            Task<List<ImageLabel>> labelsTask = imageLabeler.process(input);
            Tasks.whenAllComplete(Arrays.asList(textTask, labelsTask)).addOnCompleteListener(analysisExecutor, completed -> {
                try {
                    String recognized = textTask.isSuccessful() ? textTask.getResult().getText() : "";
                    List<ImageLabel> labels = labelsTask.isSuccessful() ? labelsTask.getResult() : Collections.emptyList();
                    if (aiReady && deviceAi != null) {
                        deviceAi.describe(bitmap, description -> {
                            bitmap.recycle();
                            post(() -> publish(recognized, labels, textTask.getException(), labelsTask.getException(),
                                    palette, jpegBytes, description));
                        });
                    } else {
                        bitmap.recycle();
                        post(() -> publish(recognized, labels, textTask.getException(), labelsTask.getException(),
                                palette, jpegBytes, null));
                    }
                } finally {
                    imageProxy.close();
                }
            });
        } catch (RuntimeException error) {
            imageProxy.close();
            post(() -> {
                inspectButton.setEnabled(cameraStarted);
                setStatus("Inspection failed: " + error.getMessage());
            });
        }
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

    private void publish(String recognized, List<ImageLabel> labels, Exception textError, Exception labelsError,
                         FramePalette.Analysis palette, byte[] jpegBytes, String aiDescription) {
        inspectButton.setEnabled(cameraStarted);
        lastFrameJpeg = jpegBytes;
        lastCloud = "";
        boolean hasFrame = jpegBytes != null && jpegBytes.length > 0;
        saveJournalButton.setEnabled(hasFrame);
        sharePhotoButton.setEnabled(hasFrame);
        cloudAskButton.setEnabled(hasFrame);
        if (hasFrame) {
            saveShareDrawer.setVisibility(VISIBLE);
            saveShareToggle.setText("Save & share ▴");
        }

        if (palette != null) {
            lastPaletteSummary = palette.summary();
            renderPaletteSwatches(palette);
        }

        String cleanText = recognized == null ? "" : recognized.trim();
        if (cleanText.length() > 4000) {
            cleanText = cleanText.substring(0, 4000) + "…";
        }
        lastOcr = cleanText;
        lastDeviceAi = aiDescription == null ? "" : aiDescription.trim();

        List<ImageLabel> ordered = new ArrayList<>(labels);
        ordered.sort((first, second) -> Float.compare(second.getConfidence(), first.getConfidence()));
        List<String> labelText = new ArrayList<>();
        for (ImageLabel label : ordered) {
            if (label.getConfidence() >= 0.5f && labelText.size() < 5) {
                labelText.add(String.format(Locale.US, "%s %.0f%%", label.getText(), label.getConfidence() * 100));
            }
        }
        lastLabels = String.join(" · ", labelText);

        StringBuilder display = buildDisplayReport(textError, labelsError, ordered);
        resultView.setText(display.toString());

        StringBuilder narration = new StringBuilder();
        if (!lastDeviceAi.isEmpty()) {
            narration.append("Device AI description. ").append(lastDeviceAi).append(". ");
        }
        if (!lastOcr.isEmpty()) {
            narration.append("Text found. ").append(lastOcr);
        } else if (lastDeviceAi.isEmpty() && !labelText.isEmpty()) {
            narration.append("Image labels. ").append(String.join(", ", labelText));
        } else if (lastDeviceAi.isEmpty()) {
            narration.append("No text or confident image labels were found. Try a clearer or closer frame.");
        }
        spoken = narration.length() > 1200 ? narration.substring(0, 1200) : narration.toString();
        shared = display.toString();
        setStatus("Inspection complete. Speak, save to Trip Journal, show Gemini, or inspect another frame.");
        resultView.announceForAccessibility("Inspection complete");
        if (autoSpeak) {
            activity.speak(spoken);
        }
    }

    private StringBuilder buildDisplayReport(Exception textError, Exception labelsError, List<ImageLabel> ordered) {
        StringBuilder display = new StringBuilder();
        if (!lastCloud.isEmpty()) {
            display.append("ONLINE CLOUD · GEMINI\n").append(lastCloud).append("\n\n");
        }
        if (!lastDeviceAi.isEmpty()) {
            display.append("DEVICE AI DESCRIPTION\n").append(lastDeviceAi).append("\n\n");
        }
        display.append("TEXT\n").append(lastOcr.isEmpty() ? "No text recognized." : lastOcr);
        display.append("\n\nIMAGE LABELS\n");
        display.append(lastLabels.isEmpty() ? "No labels at or above 50% confidence." : lastLabels);
        if (!lastPaletteSummary.isEmpty()) {
            display.append("\n\nOFFLINE PIXEL MATH\n").append(lastPaletteSummary);
        }
        if (textError != null || labelsError != null) {
            display.append("\n\nA model reported an error. Results may be incomplete; no failure was converted into success.");
        }
        if (ordered != null) {
            boolean catSpotted = ordered.stream().anyMatch(label -> "cat".equalsIgnoreCase(label.getText()));
            if (catSpotted) {
                display.append("\n\nCOMPANION\nCat in the field. Identity and tail status remain unmeasured.");
            }
        }
        display.append("\n\nModel outputs remain separate. Confidence is not correctness. One frame was inspected; nothing is saved unless you tap Save.");
        return display;
    }

    private void renderPaletteSwatches(FramePalette.Analysis palette) {
        paletteRow.removeAllViews();
        for (int i = 0; i < palette.colors.length; i++) {
            TextView swatch = Ui.text(activity, palette.hexCodes[i], 10f, android.graphics.Color.WHITE);
            swatch.setTypeface(android.graphics.Typeface.MONOSPACE);
            swatch.setGravity(android.view.Gravity.CENTER);
            swatch.setShadowLayer(4f, 0f, 1f, android.graphics.Color.BLACK);
            swatch.setBackground(Ui.panelBackground(activity, palette.colors[i], Ui.withAlpha(Ui.GOLD, 130), 10));
            swatch.setContentDescription(palette.names[i] + " " + palette.hexCodes[i]);
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, Ui.dp(activity, 28), 1.0f);
            params.setMargins(0, 0, Ui.dp(activity, 6), 0);
            paletteRow.addView(swatch, params);
        }
        paletteText.setText(palette.summary());
    }

    private static final class ViewfinderReticleView extends View {
        private final android.graphics.Paint cornerPaint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Paint crossPaint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);

        ViewfinderReticleView(MainActivity context) {
            super(context);
            setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            float d = context.getResources().getDisplayMetrics().density;
            cornerPaint.setColor(Ui.withAlpha(Ui.CYAN, 200));
            cornerPaint.setStyle(android.graphics.Paint.Style.STROKE);
            cornerPaint.setStrokeWidth(2.0f * d);
            cornerPaint.setStrokeCap(android.graphics.Paint.Cap.ROUND);

            crossPaint.setColor(Ui.withAlpha(Ui.GOLD, 120));
            crossPaint.setStyle(android.graphics.Paint.Style.STROKE);
            crossPaint.setStrokeWidth(1.1f * d);
        }

        @Override
        protected void onDraw(android.graphics.Canvas canvas) {
            super.onDraw(canvas);
            float w = getWidth();
            float h = getHeight();
            if (w <= 0 || h <= 0) {
                return;
            }
            float m = Ui.dp(getContext(), 14);
            float len = Ui.dp(getContext(), 22);
            // Four optical L-brackets
            canvas.drawLine(m, m, m + len, m, cornerPaint);
            canvas.drawLine(m, m, m, m + len, cornerPaint);
            canvas.drawLine(w - m, m, w - m - len, m, cornerPaint);
            canvas.drawLine(w - m, m, w - m, m + len, cornerPaint);
            canvas.drawLine(m, h - m, m + len, h - m, cornerPaint);
            canvas.drawLine(m, h - m, m, h - m - len, cornerPaint);
            canvas.drawLine(w - m, h - m, w - m - len, h - m, cornerPaint);
            canvas.drawLine(w - m, h - m, w - m, h - m - len, cornerPaint);

            // Center calibration reticle
            float cx = w * 0.5f;
            float cy = h * 0.5f;
            float r = Ui.dp(getContext(), 14);
            canvas.drawCircle(cx, cy, r, crossPaint);
            canvas.drawLine(cx - r * 1.4f, cy, cx - r * 0.45f, cy, crossPaint);
            canvas.drawLine(cx + r * 0.45f, cy, cx + r * 1.4f, cy, crossPaint);
            canvas.drawLine(cx, cy - r * 1.4f, cx, cy - r * 0.45f, crossPaint);
            canvas.drawLine(cx, cy + r * 0.45f, cx, cy + r * 1.4f, crossPaint);
        }
    }

    private void promptSaveToJournal() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("Inspect a frame before saving to Trip Journal.");
            return;
        }
        EditText noteInput = Ui.input(activity, "", "Optional trip note (e.g., where we are)");
        new AlertDialog.Builder(activity)
                .setTitle("Save to Trip Journal?")
                .setMessage("Saves this single sighting and a compact thumbnail locally on your phone (never uploaded unless you sync).")
                .setView(noteInput)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", (dialog, which) -> {
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
                    setStatus("Saved explicitly to Trip Journal. View anytime offline or sync back home.");
                })
                .show();
    }

    private void sharePhotoWithApps() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("Inspect a frame before sharing a photo.");
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
                    .putExtra(Intent.EXTRA_SUBJECT, "Zoe trip sighting")
                    .putExtra(Intent.EXTRA_TEXT, "Showing Zoe & Gemini what I found:\n\n" + shared)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            activity.startActivity(Intent.createChooser(share, "Show photo to Gemini or share"));
            setStatus("Opened photo share sheet (choose Gemini to ask about this image).");
        } catch (IOException | ActivityNotFoundException error) {
            setStatus("Could not share photo: " + error.getMessage());
        }
    }

    private void askCloudVision() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0) {
            setStatus("Inspect a frame first before asking Cloud Vision.");
            return;
        }
        String key = CloudVisionClient.savedApiKey(activity);
        if (key.isEmpty()) {
            setStatus("No Gemini API key set yet. Tap Show Photo to Gemini (works now) or add a key in Eliza-GEM Studio.");
            return;
        }
        String model = CloudVisionClient.savedModel(activity);
        byte[] snapshot = lastFrameJpeg;
        cloudAskButton.setEnabled(false);
        setStatus("Asking Online Cloud (" + model + ") via " + Ui.networkStatusLabel(activity) + "…");
        String prompt = "You are helping Nicholas and Zoe explore on a trip. Describe clearly and honestly what is in this image. "
                + (lastOcr.isEmpty() ? "" : "On-device OCR read: " + lastOcr + ". ");
        analysisExecutor.execute(() -> {
            try {
                String answer = CloudVisionClient.askVision(key, model, prompt, snapshot);
                post(() -> {
                    cloudAskButton.setEnabled(true);
                    lastCloud = answer;
                    StringBuilder updated = buildDisplayReport(null, null, Collections.emptyList());
                    resultView.setText(updated.toString());
                    shared = updated.toString();
                    spoken = "Online Cloud Gemini says. " + (answer.length() > 1100 ? answer.substring(0, 1100) : answer);
                    setStatus("Online Cloud Vision replied (kept separate from offline measurements).");
                    if (autoSpeak) {
                        activity.speak(spoken);
                    }
                });
            } catch (Exception error) {
                post(() -> {
                    cloudAskButton.setEnabled(true);
                    setStatus("Cloud Vision failed: " + error.getMessage());
                });
            }
        });
    }

    void setStatus(String value) {
        status.setText(value);
    }

    String spokenSummary() {
        return spoken;
    }

    String shareText() {
        return shared;
    }

    void pauseCamera() {
        cameraStartRequested = false;
        captureRequested.set(false);
        cameraStarted = false;
        if (activeCamera != null && torchEnabled) {
            try {
                activeCamera.getCameraControl().enableTorch(false);
            } catch (RuntimeException ignored) {
            }
        }
        activeCamera = null;
        torchEnabled = false;
        torchButton.setText("Flash: off");
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        lastFrameJpeg = null;
        inspectButton.setEnabled(false);
        saveJournalButton.setEnabled(false);
        sharePhotoButton.setEnabled(false);
        cloudAskButton.setEnabled(false);
        placeholder.setVisibility(VISIBLE);
        placeholder.bringToFront();
        setStatus("Camera is off. Nothing is saved by Zoe.");
    }

    void close() {
        cameraStartRequested = false;
        captureRequested.set(false);
        lastFrameJpeg = null;
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        textRecognizer.close();
        imageLabeler.close();
        if (deviceAi != null) {
            deviceAi.close();
        }
        analysisExecutor.shutdownNow();
    }
}
