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
import android.widget.LinearLayout;
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
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        content.addView(Ui.topBar(this, "Screen space", "Explicit captures · mapped gestures"));
        content.addView(Ui.text(this,
                "Your scaled screen, your action timeline. Enable the service, capture explicitly, then tap or swipe. No passive screen reading or background gestures.",
                14, Ui.MUTED));
        status = Ui.text(this, "Screen service is off. Enable it before capture or gestures.", 15, Ui.YELLOW);
        status.setId(R.id.space_status);
        content.addView(status);
        content.addView(Ui.button(this, "Open accessibility settings", Ui.GOLD, view ->
                showAccessibilityDisclosure()));
        Button capture = Ui.button(this, "Capture screen once", Ui.CYAN, view -> capture());
        capture.setId(R.id.space_capture);
        Button back = Ui.button(this, "Back", Ui.PINK, view -> global(AccessibilityService.GLOBAL_ACTION_BACK, "Back"));
        content.addView(Ui.buttonRow(this, capture, back));
        content.addView(Ui.buttonRow(this,
                Ui.button(this, "Home", Ui.GREEN, view -> global(AccessibilityService.GLOBAL_ACTION_HOME, "Home")),
                Ui.button(this, "Recents", Ui.CYAN, view -> global(AccessibilityService.GLOBAL_ACTION_RECENTS, "Recents"))));
        captureView = new ImageView(this);
        captureView.setBackground(Ui.panelBackground(this, Ui.PANEL, Ui.BORDER, 12));
        captureView.setScaleType(ImageView.ScaleType.FIT_CENTER);
        captureView.setContentDescription("Captured screen. Tap or swipe to perform an explicit gesture.");
        captureView.setClickable(true);
        captureView.setOnTouchListener(this::gesture);
        content.addView(captureView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 420)));
        timelineView = Ui.text(this, "No actions recorded. Event ordinals are not wall-clock timestamps.", 14, Ui.TEXT);
        timelineView.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        timelineView.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        content.addView(timelineView);
        content.addView(Ui.text(this,
                "Do not capture lock screens, passwords, payment screens, or private content. Captures stay in memory and are not written to disk by Zoe.",
                12, Ui.MUTED));
    }

    /** Google Play prominent disclosure + affirmative consent before the system settings open. */
    private void showAccessibilityDisclosure() {
        new android.app.AlertDialog.Builder(this)
                .setTitle("Before you enable Zoe Screen Space")
                .setMessage("Zoe asks for Android's accessibility service only to offer two optional "
                        + "assistive actions that you start yourself: capturing your screen once, and "
                        + "performing one tap or swipe you draw on that capture.\n\n"
                        + "Zoe does NOT read screen content, watch what you type, run in the background, "
                        + "save captures to storage, or send anything over the network. Captures stay in "
                        + "memory on this screen and disappear when you leave.\n\n"
                        + "You can turn the service off at any time in Android Accessibility settings.")
                .setPositiveButton("I understand · Continue", (dialog, which) ->
                        startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)))
                .setNegativeButton("Cancel", null)
                .show();
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
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN && view.getParent() != null) {
            view.getParent().requestDisallowInterceptTouchEvent(true);
        } else if ((action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL)
                && view.getParent() != null) {
            view.getParent().requestDisallowInterceptTouchEvent(false);
        }
        if (bitmap == null || bitmap.getWidth() <= 0 || bitmap.getHeight() <= 0
                || captureView.getWidth() <= 0 || captureView.getHeight() <= 0) {
            if (action == MotionEvent.ACTION_UP) {
                status.setText("Capture a screen before gesturing.");
            }
            return true;
        }
        if (action == MotionEvent.ACTION_DOWN) {
            downX = event.getX();
            downY = event.getY();
            return true;
        }
        if (action == MotionEvent.ACTION_UP) {
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
        if (scale <= 0f) {
            return 0f;
        }
        float offset = (captureView.getWidth() - bitmap.getWidth() * scale) / 2f;
        float mapped = (viewX - offset) / scale;
        return Math.max(0f, Math.min(bitmap.getWidth() - 1f, mapped));
    }

    private float sourceY(float viewY) {
        float scale = Math.min(captureView.getWidth() / (float) bitmap.getWidth(),
                captureView.getHeight() / (float) bitmap.getHeight());
        if (scale <= 0f) {
            return 0f;
        }
        float offset = (captureView.getHeight() - bitmap.getHeight() * scale) / 2f;
        float mapped = (viewY - offset) / scale;
        return Math.max(0f, Math.min(bitmap.getHeight() - 1f, mapped));
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
    public void onCapture(Bitmap newBitmap) {
        if (newBitmap == null) {
            record("Screen capture returned null");
            return;
        }
        Bitmap previous = this.bitmap;
        this.bitmap = newBitmap;
        captureView.setImageBitmap(newBitmap);
        if (previous != null && previous != newBitmap && !previous.isRecycled()) {
            previous.recycle();
        }
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
        if (ZoeAccessibilityService.isReady() && timeline.isEmpty()) {
            status.setText("Screen service ready. Tap Capture screen once when ready.");
        }
    }

    @Override
    protected void onPause() {
        ZoeAccessibilityService.setListener(null);
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        captureView.setImageBitmap(null);
        if (bitmap != null && !bitmap.isRecycled()) {
            bitmap.recycle();
            bitmap = null;
        }
        super.onDestroy();
    }
}
