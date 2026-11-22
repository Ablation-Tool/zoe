package research.zoetic.zoe;

import android.Manifest;
import android.content.pm.PackageManager;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
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

import java.util.Arrays;

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
    private volatile boolean started;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        content.addView(Ui.topBar(this, "Multi-view", "Back · Front · Laptop"));
        status = Ui.statusBanner(this, "Multi-view is off. Start all sources when ready.", Ui.COBALT);
        status.setId(R.id.multi_status);
        content.addView(status);
        Button start = Ui.primaryButton(this, "Start all", Ui.CYAN, view -> startSources());
        start.setId(R.id.multi_start);
        Button stop = Ui.button(this, "Stop all", Ui.RUBY, view -> stopSources());
        stop.setId(R.id.multi_stop);
        content.addView(Ui.buttonRow(this, start, stop));
        LinearLayout feeds = new LinearLayout(this);
        feeds.setOrientation(LinearLayout.HORIZONTAL);
        backPreview = new PreviewView(this);
        frontPreview = new PreviewView(this);
        backStatus = feedLabel("Back · idle");
        frontStatus = feedLabel("Front · idle");
        laptopStatus = feedLabel("Laptop · idle");
        feeds.addView(feed(backPreview, backStatus), feedParams());
        feeds.addView(feed(frontPreview, frontStatus), feedParams());
        ImageView laptop = new ImageView(this);
        laptop.setId(R.id.laptop_view);
        laptop.setBackgroundColor(android.graphics.Color.rgb(9, 17, 23));
        laptop.setScaleType(ImageView.ScaleType.FIT_CENTER);
        laptop.setContentDescription("Laptop camera feed over ADB localhost");
        feeds.addView(feed(laptop, laptopStatus), feedParams());
        int feedHeightDp = getResources().getConfiguration().orientation
                == Configuration.ORIENTATION_LANDSCAPE ? 190 : 300;
        LinearLayout.LayoutParams feedsLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, feedHeightDp));
        feedsLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        content.addView(feeds, feedsLp);
        TextView note = Ui.text(this,
                "Nothing is recorded. Laptop feed uses local ADB port 8766.",
                12.5f, Ui.MUTED);
        note.setGravity(Gravity.CENTER);
        content.addView(note);
    }

    private TextView feedLabel(String value) {
        return Ui.text(this, value, 12, android.graphics.Color.rgb(160, 235, 228));
    }

    private FrameLayout feed(View view, TextView label) {
        FrameLayout frame = new FrameLayout(this);
        frame.setBackground(Ui.panelBackground(this, android.graphics.Color.rgb(9, 17, 23), Ui.BORDER, 16));
        frame.setClipToOutline(true);
        frame.addView(view, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.MATCH_PARENT));
        label.setBackgroundColor(android.graphics.Color.argb(210, 9, 17, 23));
        label.setGravity(Gravity.CENTER_HORIZONTAL);
        frame.addView(label, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL));
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
            if (!started || isFinishing() || isDestroyed()) {
                return;
            }
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
                cameraProvider.bindToLifecycle(Arrays.asList(
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
        started = false;
        if (laptopClient != null) {
            laptopClient.close();
            laptopClient = null;
        }
        super.onDestroy();
    }
}
