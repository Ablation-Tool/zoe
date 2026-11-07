package research.zoetic.zoe;

import android.Manifest;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.camera.core.CameraSelector;
import androidx.camera.core.ConcurrentCamera;
import androidx.camera.core.Preview;
import androidx.camera.core.UseCaseGroup;
import androidx.camera.lifecycle.ProcessCameraProvider;
import androidx.camera.view.PreviewView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.common.util.concurrent.ListenableFuture;

public final class MultiVisionActivity extends ComponentActivity {
    private static final int CAMERA_PERMISSION = 81;
    private PreviewView backPreview;
    private PreviewView frontPreview;
    private TextView backStatus;
    private TextView frontStatus;
    private TextView laptopStatus;
    private TextView status;
    private ProcessCameraProvider cameraProvider;
    private LaptopStreamClient laptopClient;
    private boolean started;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "Multi-view"));
        content.addView(Ui.text(this,
                "Phone back + phone front + laptop over ADB localhost. Every source is independent; nothing is recorded by Zoe.",
                15, Ui.MUTED));
        status = Ui.text(this, "Multi-view is off. Start all sources when ready.", 16, Ui.YELLOW);
        status.setId(R.id.multi_status);
        content.addView(status);
        Button start = Ui.button(this, "Start all sources", view -> startSources());
        start.setId(R.id.multi_start);
        Button stop = Ui.button(this, "Stop all", view -> stopSources());
        stop.setId(R.id.multi_stop);
        content.addView(Ui.buttonRow(this, start, stop));
        LinearLayout feeds = new LinearLayout(this);
        feeds.setOrientation(LinearLayout.HORIZONTAL);
        backPreview = new PreviewView(this);
        frontPreview = new PreviewView(this);
        backStatus = feedLabel("Phone back · idle");
        frontStatus = feedLabel("Phone front · idle");
        laptopStatus = feedLabel("Laptop · idle");
        feeds.addView(feed(backPreview, backStatus), feedParams());
        feeds.addView(feed(frontPreview, frontStatus), feedParams());
        ImageView laptop = new ImageView(this);
        laptop.setId(R.id.laptop_view);
        laptop.setBackgroundColor(Ui.BACKGROUND);
        laptop.setScaleType(ImageView.ScaleType.FIT_CENTER);
        laptop.setContentDescription("Laptop camera feed over ADB localhost");
        feeds.addView(feed(laptop, laptopStatus), feedParams());
        int feedHeightDp = getResources().getConfiguration().orientation
                == android.content.res.Configuration.ORIENTATION_LANDSCAPE ? 190 : 300;
        content.addView(feeds, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, feedHeightDp)));
        content.addView(Ui.text(this,
                "Concurrent camera hardware is checked at runtime. If a source fails, its label says so while the others continue. Laptop streaming requires the local bridge on port 8766 and adb reverse.",
                13, Ui.MUTED));
    }

    private TextView feedLabel(String value) {
        return Ui.text(this, value, 12, Ui.CYAN);
    }

    private FrameLayout feed(android.view.View view, TextView label) {
        FrameLayout frame = new FrameLayout(this);
        frame.addView(view, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        label.setBackgroundColor(Ui.BACKGROUND);
        frame.addView(label, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                android.view.Gravity.BOTTOM | android.view.Gravity.CENTER_HORIZONTAL));
        return frame;
    }

    private LinearLayout.LayoutParams feedParams() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0,
                LinearLayout.LayoutParams.MATCH_PARENT, 1.0f);
        params.setMargins(Ui.dp(this, 3), Ui.dp(this, 3), Ui.dp(this, 3), Ui.dp(this, 3));
        return params;
    }

    private void startSources() {
        if (started) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION);
            return;
        }
        started = true;
        status.setText("Starting phone back, phone front, and laptop independently…");
        final ListenableFuture<ProcessCameraProvider> future = ProcessCameraProvider.getInstance(this);
        future.addListener(() -> {
            try {
                cameraProvider = future.get();
            } catch (Exception error) {
                status.setText("The camera provider failed: " + error.getMessage());
                return;
            }
            cameraProvider.unbindAll();
            Preview back = new Preview.Builder().build();
            back.setSurfaceProvider(backPreview.getSurfaceProvider());
            Preview front = new Preview.Builder().build();
            front.setSurfaceProvider(frontPreview.getSurfaceProvider());
            try {
                UseCaseGroup backGroup = new UseCaseGroup.Builder().addUseCase(back).build();
                UseCaseGroup frontGroup = new UseCaseGroup.Builder().addUseCase(front).build();
                cameraProvider.bindToLifecycle(java.util.Arrays.asList(
                        new ConcurrentCamera.SingleCameraConfig(CameraSelector.DEFAULT_BACK_CAMERA, backGroup, this),
                        new ConcurrentCamera.SingleCameraConfig(CameraSelector.DEFAULT_FRONT_CAMERA, frontGroup, this)));
                backStatus.setText("Phone back · live");
                frontStatus.setText("Phone front · live");
            } catch (Exception concurrentError) {
                frontStatus.setText("Phone front · " + concurrentError.getMessage());
                cameraProvider.unbindAll();
                try {
                    cameraProvider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, back);
                    backStatus.setText("Phone back · live");
                } catch (Exception error) {
                    backStatus.setText("Phone back · " + error.getMessage());
                }
            }
            status.setText("Preview attempts complete. Each source reports its own state; no frames are saved.");
        }, ContextCompat.getMainExecutor(this));
        ImageView laptopView = findViewById(R.id.laptop_view);
        if (laptopClient == null) {
            laptopClient = new LaptopStreamClient(laptopView, laptopStatus);
        }
        laptopClient.start();
    }

    private void stopSources() {
        started = false;
        if (cameraProvider != null) {
            cameraProvider.unbindAll();
        }
        if (laptopClient != null) {
            laptopClient.close();
            laptopClient = null;
        }
        backStatus.setText("Phone back · idle");
        frontStatus.setText("Phone front · idle");
        status.setText("Multi-view stopped. Phone cameras are unbound.");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == CAMERA_PERMISSION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                startSources();
            } else {
                status.setText("Camera permission was not granted. Laptop feed was not started either.");
            }
        }
    }

    @Override
    protected void onPause() {
        stopSources();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (laptopClient != null) {
            laptopClient.close();
        }
        super.onDestroy();
    }
}
