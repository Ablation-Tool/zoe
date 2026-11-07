package research.zoetic.zoe;

import android.graphics.Bitmap;
import android.graphics.Matrix;
import android.media.Image;
import android.view.View;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.camera.core.CameraSelector;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.core.Preview;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.content.ContextCompat;

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
    private final TextView resultView;
    private final Button inspectButton;
    private final TextRecognizer textRecognizer;
    private final ImageLabeler imageLabeler;
    private final ExecutorService analysisExecutor;
    private final AtomicBoolean captureRequested = new AtomicBoolean(false);
    private ProcessCameraProvider cameraProvider;
    private DeviceAiController deviceAi;
    private boolean cameraStarted;
    private String spoken = "No observation yet. Start the camera, then inspect one frame.";
    private String shared = spoken;

    GuidedVisionView(MainActivity activity) {
        super(activity);
        this.activity = activity;
        setFillViewport(true);
        android.widget.LinearLayout content = Ui.vertical(activity);
        content.setPadding(Ui.dp(activity, 12), Ui.dp(activity, 4), Ui.dp(activity, 12), Ui.dp(activity, 20));
        addView(content);

        FrameLayout cameraFrame = new FrameLayout(activity);
        cameraFrame.setBackground(Ui.panelBackground(activity, Ui.CYAN, 16));
        previewView = new PreviewView(activity);
        previewView.setImplementationMode(PreviewView.ImplementationMode.COMPATIBLE);
        previewView.setContentDescription("Camera preview. No frame is analyzed until Inspect is pressed.");
        cameraFrame.addView(previewView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        placeholder = Ui.text(activity,
                "Camera is off.\nStart it when you are ready.\nNothing is saved by Zoe.",
                18, Ui.MUTED);
        placeholder.setGravity(android.view.Gravity.CENTER);
        cameraFrame.addView(placeholder, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        content.addView(cameraFrame, new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(activity, 270)));

        status = Ui.text(activity,
                "Camera and microphone are idle. Bundled OCR and image-label models run on device.",
                14, Ui.YELLOW);
        status.setId(R.id.vision_status);
        content.addView(status);
        textRecognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS);
        imageLabeler = ImageLabeling.getClient(ImageLabelerOptions.DEFAULT_OPTIONS);
        analysisExecutor = Executors.newSingleThreadExecutor();

        Button start = Ui.button(activity, "Start camera", view -> activity.startCamera());
        start.setId(R.id.start_camera);
        inspectButton = Ui.button(activity, "Inspect once", view -> requestInspection());
        inspectButton.setId(R.id.inspect_button);
        inspectButton.setEnabled(false);
        content.addView(Ui.buttonRow(activity, start, inspectButton));
        Button listen = Ui.button(activity, "Voice command", view -> activity.startListening());
        listen.setId(R.id.listen_button);
        Button speak = Ui.button(activity, "Speak", view -> activity.repeatCurrent());
        speak.setId(R.id.speak_button);
        Button stop = Ui.button(activity, "Stop", view -> activity.stopAllOutput());
        stop.setId(R.id.stop_button);
        content.addView(Ui.buttonRow(activity, listen, speak, stop));
        Button share = Ui.button(activity, "Share result", view -> activity.shareCurrent());
        share.setId(R.id.share_button);
        Button gemini = Ui.button(activity, "Open Gemini", view -> activity.openGemini());
        gemini.setId(R.id.gemini_button);
        content.addView(Ui.buttonRow(activity, share, gemini));
        content.addView(Ui.buttonRow(activity,
                Ui.button(activity, "Check device AI", view -> ensureDeviceAi().check()),
                Ui.button(activity, "Enable AI model", view -> ensureDeviceAi().enable())));

        resultView = Ui.text(activity,
                "OCR and image labels will appear here with confidence kept separate from correctness.",
                16, Ui.TEXT);
        resultView.setBackground(Ui.panelBackground(activity, Ui.GREEN, 16));
        resultView.setPadding(Ui.dp(activity, 14), Ui.dp(activity, 14), Ui.dp(activity, 14), Ui.dp(activity, 14));
        resultView.setTextIsSelectable(true);
        content.addView(resultView);
        content.addView(Ui.text(activity,
                "Voice commands: inspect, repeat, stop, measure, battery, Gemini. Listening is one-shot. Image labels are model outputs, not proof of identity or safety.",
                13, Ui.MUTED));
    }

    void startCamera() {
        if (cameraStarted) {
            setStatus("Camera is already active. Choose Inspect once when ready.");
            return;
        }
        final ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(activity);
        future.addListener(() -> {
            try {
                cameraProvider = future.get();
                Preview preview = new Preview.Builder().build();
                preview.setSurfaceProvider(previewView.getSurfaceProvider());
                ImageAnalysis analysis = new ImageAnalysis.Builder()
                        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                        .build();
                analysis.setAnalyzer(analysisExecutor, this::analyze);
                cameraProvider.unbindAll();
                cameraProvider.bindToLifecycle(activity, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis);
                cameraStarted = true;
                placeholder.setVisibility(GONE);
                inspectButton.setEnabled(true);
                setStatus("Camera active. No continuous analysis. Choose Inspect once.");
            } catch (Exception error) {
                setStatus("Camera could not start: " + error.getMessage());
            }
        }, ContextCompat.getMainExecutor(activity));
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
        setStatus("Inspecting one frame with on-device OCR and labels…");
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
        Image mediaImage = imageProxy.getImage();
        if (mediaImage == null) {
            imageProxy.close();
            post(() -> {
                inspectButton.setEnabled(true);
                setStatus("The selected frame had no readable image.");
            });
            return;
        }
        try {
            InputImage input = InputImage.fromMediaImage(mediaImage, imageProxy.getImageInfo().getRotationDegrees());
            Task<Text> textTask = textRecognizer.process(input);
            Task<List<ImageLabel>> labelsTask = imageLabeler.process(input);
            Tasks.whenAllComplete(Arrays.asList(textTask, labelsTask)).addOnCompleteListener(completed -> {
                String recognized = textTask.isSuccessful() ? textTask.getResult().getText() : "";
                List<ImageLabel> labels = labelsTask.isSuccessful() ? labelsTask.getResult() : Collections.emptyList();
                if (deviceAi != null && deviceAi.isReady()) {
                    Bitmap bitmap = orientedBitmap(imageProxy);
                    imageProxy.close();
                    deviceAi.describe(bitmap, description -> post(() ->
                            publish(recognized, labels, textTask.getException(), labelsTask.getException(), description)));
                } else {
                    imageProxy.close();
                    post(() -> publish(recognized, labels, textTask.getException(), labelsTask.getException(), null));
                }
            });
        } catch (RuntimeException error) {
            imageProxy.close();
            post(() -> {
                inspectButton.setEnabled(true);
                setStatus("Inspection failed: " + error.getMessage());
            });
        }
    }

    private void publish(String recognized, List<ImageLabel> labels, Exception textError, Exception labelsError, String aiDescription) {
        inspectButton.setEnabled(true);
        String cleanText = recognized == null ? "" : recognized.trim();
        if (cleanText.length() > 4000) {
            cleanText = cleanText.substring(0, 4000) + "…";
        }
        String description = aiDescription == null ? "" : aiDescription.trim();
        List<ImageLabel> ordered = new ArrayList<>(labels);
        ordered.sort((first, second) -> Float.compare(second.getConfidence(), first.getConfidence()));
        List<String> labelText = new ArrayList<>();
        for (ImageLabel label : ordered) {
            if (label.getConfidence() >= 0.5f && labelText.size() < 5) {
                labelText.add(String.format(Locale.US, "%s %.0f%%", label.getText(), label.getConfidence() * 100));
            }
        }
        StringBuilder display = new StringBuilder();
        if (!description.isEmpty()) {
            display.append("DEVICE AI DESCRIPTION\n").append(description).append("\n\n");
        }
        display.append("TEXT\n").append(cleanText.isEmpty() ? "No text recognized." : cleanText);
        display.append("\n\nIMAGE LABELS\n");
        display.append(labelText.isEmpty() ? "No labels at or above 50% confidence." : String.join(" · ", labelText));
        if (textError != null || labelsError != null) {
            display.append("\n\nA model reported an error. Results may be incomplete; no failure was converted into success.");
        }
        boolean catSpotted = ordered.stream().anyMatch(label -> "cat".equalsIgnoreCase(label.getText()));
        if (catSpotted) {
            display.append("\n\nCOMPANION\nCat in the field. Identity and tail status remain unmeasured.");
        }
        display.append("\n\nModel outputs remain separate. Confidence is not correctness. One frame was inspected; no image was saved by Zoe.");
        resultView.setText(display.toString());
        StringBuilder narration = new StringBuilder();
        if (!description.isEmpty()) {
            narration.append("Device AI description. ").append(description).append(". ");
        }
        if (!cleanText.isEmpty()) {
            narration.append("Text found. ").append(cleanText);
        } else if (description.isEmpty() && !labelText.isEmpty()) {
            narration.append("Image labels. ").append(String.join(", ", labelText));
        } else if (description.isEmpty()) {
            narration.append("No text or confident image labels were found. Try a clearer or closer frame.");
        }
        spoken = narration.length() > 1200 ? narration.substring(0, 1200) : narration.toString();
        shared = display.toString();
        setStatus("Inspection complete. Speak, share, or inspect another frame when you choose.");
        resultView.announceForAccessibility("Inspection complete");
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
        captureRequested.set(false);
        cameraStarted = false;
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        inspectButton.setEnabled(false);
        placeholder.setVisibility(VISIBLE);
        placeholder.bringToFront();
        setStatus("Camera is off. Nothing is saved by Zoe.");
    }

    void close() {
        captureRequested.set(false);
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
