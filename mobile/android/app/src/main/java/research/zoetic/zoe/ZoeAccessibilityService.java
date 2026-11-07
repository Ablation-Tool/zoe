package research.zoetic.zoe;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.Path;
import android.os.Build;
import android.view.accessibility.AccessibilityEvent;

import androidx.core.content.ContextCompat;

public final class ZoeAccessibilityService extends AccessibilityService {
    interface Listener {
        void onCapture(Bitmap bitmap);
        void onGesture(boolean completed);
    }

    private static ZoeAccessibilityService instance;
    private Listener listener;

    static boolean isReady() {
        return instance != null;
    }

    static void setListener(Listener listener) {
        if (instance != null) {
            instance.listener = listener;
        }
    }

    static boolean capture() {
        if (instance == null || Build.VERSION.SDK_INT < 30) {
            return false;
        }
        instance.captureScreen();
        return true;
    }

    static boolean gesture(float startX, float startY, float endX, float endY, long durationMs) {
        if (instance == null) {
            return false;
        }
        Path path = new Path();
        path.moveTo(startX, startY);
        path.lineTo(endX, endY);
        GestureDescription.StrokeDescription stroke = new GestureDescription.StrokeDescription(path, 0, Math.max(50, durationMs));
        return instance.dispatchGesture(new GestureDescription.Builder().addStroke(stroke).build(),
                new GestureResultCallback() {
                    @Override
                    public void onCompleted(GestureDescription gestureDescription) {
                        if (instance != null && instance.listener != null) {
                            instance.listener.onGesture(true);
                        }
                    }

                    @Override
                    public void onCancelled(GestureDescription gestureDescription) {
                        if (instance != null && instance.listener != null) {
                            instance.listener.onGesture(false);
                        }
                    }
                }, null);
    }

    static boolean global(int action) {
        return instance != null && instance.performGlobalAction(action);
    }

    private void captureScreen() {
        if (Build.VERSION.SDK_INT < 30) {
            if (listener != null) {
                listener.onGesture(false);
            }
            return;
        }
        takeScreenshot(android.view.Display.DEFAULT_DISPLAY, ContextCompat.getMainExecutor(this),
                new AccessibilityService.TakeScreenshotCallback() {
                    @Override
                    public void onSuccess(ScreenshotResult result) {
                        android.hardware.HardwareBuffer buffer = result.getHardwareBuffer();
                        Bitmap bitmap = Bitmap.wrapHardwareBuffer(buffer, result.getColorSpace());
                        buffer.close();
                        if (listener != null) {
                            listener.onCapture(bitmap);
                        }
                    }

                    @Override
                    public void onFailure(int errorCode) {
                        if (listener != null) {
                            listener.onGesture(false);
                        }
                    }
                });
    }

    @Override
    protected void onServiceConnected() {
        super.onServiceConnected();
        instance = this;
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    @Override
    public boolean onUnbind(Intent intent) {
        listener = null;
        instance = null;
        return super.onUnbind(intent);
    }

    @Override
    public void onDestroy() {
        listener = null;
        instance = null;
        super.onDestroy();
    }
}
