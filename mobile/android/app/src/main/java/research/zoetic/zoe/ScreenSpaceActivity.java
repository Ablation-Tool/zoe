package research.zoetic.zoe;

import android.accessibilityservice.AccessibilityService;
import android.content.Intent;
import android.graphics.Bitmap;
import android.os.Bundle;
import android.provider.Settings;
import android.view.MotionEvent;
import android.view.View;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.ArrayList;
import java.util.List;

public final class ScreenSpaceActivity extends ComponentActivity implements ZoeAccessibilityService.Listener {
    private final List<String> timeline = new ArrayList<>();
    private ImageView captureView;
    private TextView status;
    private TextView timelineView;
    private Bitmap bitmap;
    private long ordinal;
    private float downX;
    private float downY;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        android.widget.LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "Screen space"));
        content.addView(Ui.text(this,
                "Your scaled screen, your action timeline. Enable the service, capture explicitly, then tap or swipe. No passive screen reading or background gestures.",
                14, Ui.MUTED));
        status = Ui.text(this, "Screen service is off. Enable it before capture or gestures.", 15, Ui.YELLOW);
        status.setId(R.id.space_status);
        content.addView(status);
        content.addView(Ui.button(this, "Open accessibility settings", view -> {
            startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS));
        }));
        Button capture = Ui.button(this, "Capture screen once", view -> capture());
        capture.setId(R.id.space_capture);
        Button back = Ui.button(this, "Back", view -> global(AccessibilityService.GLOBAL_ACTION_BACK, "Back"));
        content.addView(Ui.buttonRow(this, capture, back));
        content.addView(Ui.buttonRow(this,
                Ui.button(this, "Home", view -> global(AccessibilityService.GLOBAL_ACTION_HOME, "Home")),
                Ui.button(this, "Recents", view -> global(AccessibilityService.GLOBAL_ACTION_RECENTS, "Recents"))));
        captureView = new ImageView(this);
        captureView.setBackgroundColor(Ui.BACKGROUND);
        captureView.setContentDescription("Captured screen. Tap or swipe to perform an explicit gesture.");
        captureView.setClickable(true);
        captureView.setOnTouchListener(this::gesture);
        content.addView(captureView, new android.widget.LinearLayout.LayoutParams(
                android.widget.LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 420)));
        timelineView = Ui.text(this, "No actions recorded. Event ordinals are not wall-clock timestamps.", 14, Ui.TEXT);
        timelineView.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        timelineView.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        content.addView(timelineView);
        content.addView(Ui.text(this,
                "Do not capture lock screens, passwords, payment screens, or private content. Captures stay in memory and are not written to disk by Zoe.",
                12, Ui.MUTED));
    }

    private void capture() {
        if (!ZoeAccessibilityService.isReady()) {
            status.setText("Enable the service first. No screen was captured.");
            return;
        }
        if (!ZoeAccessibilityService.capture()) {
            status.setText("Screenshot is unavailable on this Android version or in this context.");
        } else {
            status.setText("Capturing on your explicit action…");
        }
    }

    private void global(int action, String label) {
        boolean accepted = ZoeAccessibilityService.global(action);
        record(label + " · " + (accepted ? "accepted" : "service unavailable"));
    }

    private boolean gesture(View view, MotionEvent event) {
        if (bitmap == null) {
            if (event.getAction() == MotionEvent.ACTION_UP) {
                status.setText("Capture a screen before gesturing.");
            }
            return true;
        }
        if (event.getAction() == MotionEvent.ACTION_DOWN) {
            downX = event.getX();
            downY = event.getY();
            return true;
        }
        if (event.getAction() == MotionEvent.ACTION_UP) {
            float endX = event.getX();
            float endY = event.getY();
            long duration = Math.max(50, event.getEventTime() - event.getDownTime());
            float startX = sourceX(downX);
            float startY = sourceY(downY);
            float finalX = sourceX(endX);
            float finalY = sourceY(endY);
            boolean accepted = ZoeAccessibilityService.gesture(startX, startY, finalX, finalY, duration);
            if (!accepted) {
                record("Gesture rejected by the system");
            }
        }
        return true;
    }

    private float sourceX(float viewX) {
        float scale = Math.min(captureView.getWidth() / (float) bitmap.getWidth(),
                captureView.getHeight() / (float) bitmap.getHeight());
        float offset = (captureView.getWidth() - bitmap.getWidth() * scale) / 2;
        return (viewX - offset) / scale;
    }

    private float sourceY(float viewY) {
        float scale = Math.min(captureView.getWidth() / (float) bitmap.getWidth(),
                captureView.getHeight() / (float) bitmap.getHeight());
        float offset = (captureView.getHeight() - bitmap.getHeight() * scale) / 2;
        return (viewY - offset) / scale;
    }

    private void record(String action) {
        timeline.add((++ordinal) + " · " + action);
        if (timeline.size() > 12) {
            timeline.remove(0);
        }
        timelineView.setText(String.join("\n", timeline));
        status.setText(action);
    }

    @Override
    public void onCapture(Bitmap bitmap) {
        this.bitmap = bitmap;
        captureView.setImageBitmap(bitmap);
        record("Screen captured");
    }

    @Override
    public void onGesture(boolean completed) {
        record(completed ? "Gesture completed" : "Gesture failed or was cancelled");
    }

    @Override
    protected void onResume() {
        super.onResume();
        ZoeAccessibilityService.setListener(this);
    }

    @Override
    protected void onPause() {
        ZoeAccessibilityService.setListener(null);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (bitmap != null) {
            bitmap.recycle();
            bitmap = null;
        }
        super.onDestroy();
    }
}
