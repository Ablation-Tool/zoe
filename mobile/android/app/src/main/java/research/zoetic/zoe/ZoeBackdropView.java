package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Shader;
import android.view.View;

/**
 * Google Gemini-inspired calm ambient canvas:
 * pure deep velvet night with a whisper-soft lower sapphire glow in Dark mode,
 * or spotless white with a gentle cool sky-blue mist in Light mode.
 * Zero grids, zero dots, zero distracting visual noise.
 */
final class ZoeBackdropView extends View {
    private final Paint glowPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private int lastW = -1;
    private int lastH = -1;
    private boolean lastDark;

    ZoeBackdropView(Context context) {
        super(context);
        setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        Context ctx = getContext();
        boolean dark = Ui.isDark(ctx);
        canvas.drawColor(Ui.bgColor(ctx));

        int w = getWidth();
        int h = getHeight();
        if (w <= 0 || h <= 0) {
            return;
        }
        if (w != lastW || h != lastH || dark != lastDark) {
            lastW = w;
            lastH = h;
            lastDark = dark;
            float cx = w * 0.50f;
            float cy = h * 0.80f;
            float radius = Math.max(w, h) * 0.62f;
            int centerColor = dark
                    ? Color.argb(115, 24, 48, 108)   // Soft Google Gemini sapphire ambient glow
                    : Color.argb(120, 224, 236, 255); // Whisper-soft Google sky-blue mist
            int midColor = dark
                    ? Color.argb(45, 34, 30, 82)
                    : Color.argb(45, 242, 246, 255);
            glowPaint.setShader(new RadialGradient(
                    cx, cy, radius,
                    new int[]{centerColor, midColor, Color.TRANSPARENT},
                    new float[]{0f, 0.55f, 1f},
                    Shader.TileMode.CLAMP));
        }
        canvas.drawRect(0, 0, w, h, glowPaint);
    }
}
