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
import com.google.mlkit.vision.text.Text;
import com.google.mlkit.vision.text.TextRecognizer;

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
    private final Button teachObjectButton;
    private final Button patentPriorButton;
    private final Button memoryBadgeButton;
    private final LinearLayout improveDrawer;
    private final Button improveToggle;
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
    private String lastJudgeReport = "";
    private String lastPaletteSummary = "";
    private String lastDeviceAi = "";
    private String lastCloud = "";
    private String lastStructuralNote = "";
    private boolean lastHardToIdentify;
    private PatentReverseImageEngine.VisualSignature lastVisualSignature;
    private VisionPriorStore.MatchResult lastPriorMatch;
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
        content.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 8), Ui.dp(activity, 16), Ui.dp(activity, 20));
        addView(content);

        FrameLayout cameraFrame = new FrameLayout(activity);
        cameraFrame.setBackground(Ui.panelBackground(activity, android.graphics.Color.rgb(9, 17, 23), Ui.BORDER, 20));
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
        textRecognizer = MediaChatHelper.getSharedTextRecognizer();
        imageLabeler = MediaChatHelper.getSharedImageLabeler();
        analysisExecutor = Executors.newSingleThreadExecutor();
        analysisExecutor.execute(() -> VisionPriorStore.loadAll(activity));

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

        // Self-Improving Recognition Drawer (offline contour memory + silent CPC-filtered patent structural priors)
        improveDrawer = Ui.vertical(activity);
        improveDrawer.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        improveDrawer.setVisibility(GONE);

        teachObjectButton = Ui.button(activity, "Teach Zoe", Ui.GREEN, view -> promptTeachObject());
        teachObjectButton.setId(R.id.vision_teach_button);
        teachObjectButton.setEnabled(false);

        patentPriorButton = Ui.button(activity, "Patent prior", Ui.COBALT, view -> runSilentPatentPrior());
        patentPriorButton.setId(R.id.vision_patent_prior_button);
        patentPriorButton.setEnabled(false);

        memoryBadgeButton = Ui.button(activity, "Memory: " + VisionPriorStore.learnedCount(activity), Ui.GOLD, view -> showLearnedMemoryDialog());
        memoryBadgeButton.setId(R.id.vision_memory_badge);
        improveDrawer.addView(Ui.buttonRow(activity, teachObjectButton, patentPriorButton, memoryBadgeButton));

        improveToggle = Ui.disclosureButton(activity, "Improve recognition ▾", null);
        improveToggle.setId(R.id.vision_improve_toggle);
        improveToggle.setOnClickListener(view -> {
            boolean open = improveDrawer.getVisibility() != VISIBLE;
            improveDrawer.setVisibility(open ? VISIBLE : GONE);
            improveToggle.setText(open ? "Improve recognition ▴" : "Improve recognition ▾");
        });
        content.addView(improveToggle);
        content.addView(improveDrawer);

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
            PatentReverseImageEngine.VisualSignature visualSig =
                    PatentReverseImageEngine.extractFromBitmap(bitmap, true);
            VisionPriorStore.MatchResult priorMatch =
                    VisionPriorStore.matchSignature(activity, visualSig, VisionPriorStore.DEFAULT_MIN_SCORE);
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
                                    palette, visualSig, priorMatch, jpegBytes, description));
                        });
                    } else {
                        bitmap.recycle();
                        post(() -> publish(recognized, labels, textTask.getException(), labelsTask.getException(),
                                palette, visualSig, priorMatch, jpegBytes, null));
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
                         FramePalette.Analysis palette,
                         PatentReverseImageEngine.VisualSignature visualSig,
                         VisionPriorStore.MatchResult priorMatch,
                         byte[] jpegBytes, String aiDescription) {
        inspectButton.setEnabled(cameraStarted);
        lastFrameJpeg = jpegBytes;
        lastVisualSignature = visualSig;
        lastPriorMatch = priorMatch;
        lastStructuralNote = "";
        lastCloud = "";
        boolean hasFrame = jpegBytes != null && jpegBytes.length > 0;
        saveJournalButton.setEnabled(hasFrame);
        sharePhotoButton.setEnabled(hasFrame);
        cloudAskButton.setEnabled(hasFrame);
        teachObjectButton.setEnabled(visualSig != null);
        patentPriorButton.setEnabled(hasFrame && visualSig != null);
        refreshMemoryBadge();
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
        List<String> judgeLabels = new ArrayList<>();
        for (ImageLabel label : ordered) {
            if (label.getConfidence() >= 0.5f && labelText.size() < 5) {
                int pct = Math.round(label.getConfidence() * 100);
                labelText.add(String.format(Locale.US, "%s %d%%", label.getText(), pct));
                judgeLabels.add(String.format(Locale.US, "%s (%d%%)", label.getText(), pct));
            }
        }
        lastLabels = String.join(" · ", labelText);
        StringBuilder judgeSb = new StringBuilder("Labels: ");
        judgeSb.append(judgeLabels.isEmpty() ? "none above 50%" : String.join(", ", judgeLabels)).append(".");
        if (!lastOcr.isEmpty()) {
            judgeSb.append(" Visible text: \"").append(lastOcr.length() > 80 ? lastOcr.substring(0, 80) : lastOcr).append("\".");
        }
        lastJudgeReport = judgeSb.toString();
        lastHardToIdentify = PatentReverseImageEngine.isHardToIdentify(lastJudgeReport);

        if (lastHardToIdentify && visualSig != null) {
            improveDrawer.setVisibility(VISIBLE);
            improveToggle.setText("Improve recognition ▴");
        }

        StringBuilder display = buildDisplayReport(textError, labelsError, ordered);
        resultView.setText(display.toString());

        StringBuilder narration = new StringBuilder();
        if (lastPriorMatch != null) {
            narration.append("Learned structural match: ").append(lastPriorMatch.prototype.label).append(". ");
        }
        if (!lastDeviceAi.isEmpty()) {
            narration.append("Device AI description. ").append(lastDeviceAi).append(". ");
        }
        if (!lastOcr.isEmpty()) {
            narration.append("Text found. ").append(lastOcr);
        } else if (lastDeviceAi.isEmpty() && !labelText.isEmpty()) {
            narration.append("Image labels. ").append(String.join(", ", labelText));
        } else if (lastDeviceAi.isEmpty() && lastPriorMatch == null) {
            narration.append("No text or confident image labels were found. Open Improve recognition to teach Zoe or run silent patent prior matching.");
        }
        spoken = narration.length() > 1200 ? narration.substring(0, 1200) : narration.toString();
        shared = display.toString();
        setStatus(lastPriorMatch != null
                ? "Recognized \"" + lastPriorMatch.prototype.label + "\" from Zoe's offline visual memory."
                : (lastHardToIdentify
                        ? "Unfamiliar shape — tap Teach Zoe object or Patent prior below to improve recognition."
                        : "Inspection complete. Speak, teach Zoe, save to Trip Journal, or inspect another frame."));
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
        if (lastPriorMatch != null || !lastStructuralNote.isEmpty() || lastVisualSignature != null) {
            display.append("STRUCTURAL RECOGNITION (OFFLINE MEMORY)\n");
            if (lastPriorMatch != null) {
                display.append("Recognized: ").append(lastPriorMatch.formatGuidedSummary()).append("\n");
            }
            if (!lastStructuralNote.isEmpty()) {
                display.append(lastStructuralNote).append("\n");
            }
            if (lastVisualSignature != null && !lastVisualSignature.shapeSummary.isEmpty()) {
                display.append("Geometry: ").append(lastVisualSignature.shapeSummary);
                if (lastHardToIdentify && lastPriorMatch == null) {
                    display.append(" · Unfamiliar object (tap Teach Zoe object or Patent prior to learn)");
                }
            }
            display.append("\n\n");
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
        display.append("\n\nModel outputs and structural matches remain candidate observations, not proof of identity. Nothing is saved unless you tap Save or Teach.");
        return display;
    }

    private void refreshMemoryBadge() {
        memoryBadgeButton.setText("Memory: " + VisionPriorStore.learnedCount(activity));
    }

    private void promptTeachObject() {
        if (lastVisualSignature == null) {
            setStatus("Inspect a frame first before teaching Zoe.");
            return;
        }
        String defaultGuess = lastPriorMatch != null
                ? lastPriorMatch.prototype.label
                : ArExploreBrain.extractPrimaryLabel(lastJudgeReport);
        EditText input = Ui.input(activity, defaultGuess, "Object name (e.g. Precision Caliper, Prism Lens)");
        new AlertDialog.Builder(activity)
                .setTitle("Teach Zoe this object")
                .setMessage("Saves only the compact edge-contour geometry locally on-device (no photo saved). Improves future recognition in both Guided Vision and Zoe Explore.")
                .setView(input)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Learn offline", (dialog, which) -> {
                    String name = VisionPriorStore.cleanLabel(input.getText().toString());
                    if (name.isEmpty()) {
                        setStatus("Enter a short object name so Zoe can learn its contour.");
                        return;
                    }
                    PatentReverseImageEngine.VisualSignature sig = lastVisualSignature;
                    VisionPriorStore.teach(activity, name, sig, "user_confirmed", "", "");
                    lastPriorMatch = VisionPriorStore.matchSignature(activity, sig, 0.5f);
                    lastStructuralNote = "Saved \"" + name + "\" into on-device structural memory (shared silently with Zoe Explore).";
                    refreshMemoryBadge();
                    StringBuilder updated = buildDisplayReport(null, null, Collections.emptyList());
                    resultView.setText(updated.toString());
                    shared = updated.toString();
                    setStatus("Learned \"" + name + "\" offline — Zoe's recognition just got sharper.");
                })
                .show();
    }

    private void runSilentPatentPrior() {
        if (lastFrameJpeg == null || lastFrameJpeg.length == 0 || lastVisualSignature == null) {
            setStatus("Inspect a frame first before running silent patent structural matching.");
            return;
        }
        final byte[] snapshot = lastFrameJpeg;
        final String judge = lastJudgeReport;
        final PatentReverseImageEngine.VisualSignature sig = lastVisualSignature;
        patentPriorButton.setEnabled(false);
        setStatus("Comparing contours silently against physical Google Patents classes (A47/B25/F16/G01/G02/H01)…");
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
                    String concept = GooglePatentsClient.cleanPhysicalConcept(top.title);
                    VisionPriorStore.teach(activity, concept, sig, "patent_cpc", top.publicationNumber, top.dimensionsNote);
                    lastPriorMatch = VisionPriorStore.matchSignature(activity, sig, 0.5f);
                    StringBuilder note = new StringBuilder();
                    note.append("Refined via physical patent catalog (").append(res.drawingsCompared).append(" drawings compared): ")
                            .append(concept);
                    if (top.visualMatchPercent() >= 0) {
                        note.append(" · ").append(top.visualMatchPercent()).append("% contour match");
                    }
                    if (!top.dimensionsNote.isEmpty()) {
                        note.append(" · Reference scale: ").append(top.dimensionsNote);
                    }
                    note.append(" — learned into offline memory.");
                    lastStructuralNote = note.toString();
                    refreshMemoryBadge();
                    StringBuilder updated = buildDisplayReport(null, null, Collections.emptyList());
                    resultView.setText(updated.toString());
                    shared = updated.toString();
                    spoken = "Structural prior identified " + concept + " and saved it to Zoe's offline visual memory.";
                    setStatus("Refined recognition: \"" + concept + "\" learned into offline memory.");
                    if (autoSpeak) {
                        activity.speak(spoken);
                    }
                } else {
                    lastStructuralNote = !res.errorNote.isEmpty()
                            ? res.errorNote
                            : "No high-confidence physical patent contour match (rejected noisy candidates). Tap Teach Zoe object to train directly.";
                    StringBuilder updated = buildDisplayReport(null, null, Collections.emptyList());
                    resultView.setText(updated.toString());
                    shared = updated.toString();
                    setStatus("No high-confidence structural patent match — tap Teach Zoe object to train Zoe directly.");
                }
            });
        });
    }

    private void showLearnedMemoryDialog() {
        List<VisionPriorStore.Prototype> list = VisionPriorStore.loadAll(activity);
        if (list.isEmpty()) {
            new AlertDialog.Builder(activity)
                    .setTitle("Zoe's Offline Visual Memory")
                    .setMessage("No objects learned yet.\n\nInspect an unfamiliar object and tap \"Teach Zoe object\" or \"Patent prior\" — Zoe stores compact Sobel contour signatures locally (never uploaded) to recognize objects faster offline in both Guided Vision and Zoe Explore.")
                    .setPositiveButton("Got it", null)
                    .show();
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < Math.min(20, list.size()); i++) {
            VisionPriorStore.Prototype p = list.get(i);
            sb.append("• ").append(p.label)
                    .append(" (seen ").append(p.confirmCount).append("×")
                    .append("patent_cpc".equals(p.source) ? ", patent prior" : ", taught")
                    .append(")\n");
        }
        if (list.size() > 20) {
            sb.append("… and ").append(list.size() - 20).append(" more.\n");
        }
        new AlertDialog.Builder(activity)
                .setTitle("Zoe's Offline Visual Memory (" + list.size() + ")")
                .setMessage(sb.toString().trim())
                .setNegativeButton("Close", null)
                .setNeutralButton("Clear all", (d, w) -> {
                    VisionPriorStore.clearAll(activity);
                    lastPriorMatch = null;
                    refreshMemoryBadge();
                    setStatus("Cleared Zoe's local visual recognition memory.");
                })
                .show();
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
            params.setMargins(0, 0, i < palette.colors.length - 1 ? Ui.dp(activity, 6) : 0, 0);
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
        lastVisualSignature = null;
        lastPriorMatch = null;
        lastStructuralNote = "";
        inspectButton.setEnabled(false);
        saveJournalButton.setEnabled(false);
        sharePhotoButton.setEnabled(false);
        cloudAskButton.setEnabled(false);
        teachObjectButton.setEnabled(false);
        patentPriorButton.setEnabled(false);
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
        // Keep shared MediaChatHelper ML Kit singletons warm across screens; only close local DeviceAI & executor.
        if (deviceAi != null) {
            deviceAi.close();
        }
        analysisExecutor.shutdownNow();
    }
}
