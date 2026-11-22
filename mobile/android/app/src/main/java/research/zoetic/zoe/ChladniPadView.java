package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.view.MotionEvent;
import android.view.View;

final class ChladniPadView extends View {
    static final int MODE_SQUARE = 0;
    static final int MODE_ROSE_DISC = 1;

    interface ModeListener {
        void onModeChanged(int modeType, int[] modes, int roseSymmetry);
    }

    private static final int GRID = 140;
    private static final int[] ROSE_ORDERS = {6, 12, 18, 24};

    private final int[] pixels = new int[GRID * GRID];
    private final Bitmap buffer = Bitmap.createBitmap(GRID, GRID, Bitmap.Config.ARGB_8888);
    private final Paint imagePaint = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Paint ringPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final RectF dest = new RectF();
    private final int[] modes = {1, 4, 2, 6};
    private int modeType = MODE_SQUARE;
    private int roseOrderIndex = 3; // defaults to 24 symmetry when switched to Rose Disc
    private double phase = 0.0;
    private boolean animating = true;
    private ModeListener listener;

    ChladniPadView(Context context) {
        super(context);
        ringPaint.setStyle(Paint.Style.STROKE);
        ringPaint.setStrokeWidth(Ui.dp(context, 2));
        renderPixels();
    }

    void setModeListener(ModeListener listener) {
        this.listener = listener;
        notifyListener();
    }

    int modeType() {
        return modeType;
    }

    int[] modes() {
        return modes.clone();
    }

    int roseSymmetry() {
        return ROSE_ORDERS[roseOrderIndex];
    }

    void toggleModeType() {
        modeType = modeType == MODE_SQUARE ? MODE_ROSE_DISC : MODE_SQUARE;
        renderPixels();
        invalidate();
        notifyListener();
    }

    void setAnimating(boolean active) {
        this.animating = active;
        if (active) {
            postInvalidateOnAnimation();
        }
    }

    private void notifyListener() {
        if (listener != null) {
            listener.onModeChanged(modeType, modes(), roseSymmetry());
        }
    }

    private void renderPixels() {
        int n1 = modes[0];
        int m1 = modes[1];
        int n2 = modes[2];
        int m2 = modes[3];
        double pulse = 0.21 + 0.045 * Math.sin(phase);
        double invPulseSq = 1.0 / (pulse * pulse);
        int sym = ROSE_ORDERS[roseOrderIndex];

        if (modeType == MODE_SQUARE) {
            for (int py = 0; py < GRID; py++) {
                double y = (py / (double) (GRID - 1)) * 2.0 - 1.0;
                int row = py * GRID;
                for (int px = 0; px < GRID; px++) {
                    double x = (px / (double) (GRID - 1)) * 2.0 - 1.0;
                    double z1 = Math.cos(n1 * Math.PI * x) * Math.cos(m1 * Math.PI * y)
                            - Math.cos(m1 * Math.PI * x) * Math.cos(n1 * Math.PI * y);
                    double z2 = Math.cos(n2 * Math.PI * x) * Math.cos(m2 * Math.PI * y)
                            + Math.cos(m2 * Math.PI * x) * Math.cos(n2 * Math.PI * y);
                    double s1 = Math.exp(-(z1 * z1) * invPulseSq);
                    double s2 = Math.exp(-(z2 * z2) * invPulseSq);
                    double z = 0.65 * z1 + 0.35 * z2;
                    double s = Math.exp(-(z * z) * invPulseSq);
                    double cross = s1 * s2;
                    int r = Math.min(255, (int) Math.round(4 + s2 * 238 + cross * 195 + s * 32));
                    int g = Math.min(255, (int) Math.round(7 + s1 * 212 + cross * 165 + s * 40));
                    int b = Math.min(255, (int) Math.round(16 + s1 * 236 + s2 * 82));
                    pixels[row + px] = (0xff << 24) | (r << 16) | (g << 8) | b;
                }
            }
        } else {
            double radialFreq = (2.2 + 0.6 * n1) * Math.PI;
            double innerRing = (3.4 + 0.4 * m1) * Math.PI;
            double rot = phase * 0.22;
            for (int py = 0; py < GRID; py++) {
                double y = (py / (double) (GRID - 1)) * 2.0 - 1.0;
                int row = py * GRID;
                for (int px = 0; px < GRID; px++) {
                    double x = (px / (double) (GRID - 1)) * 2.0 - 1.0;
                    double r = Math.hypot(x, y);
                    if (r > 0.98) {
                        pixels[row + px] = Color.rgb(4, 6, 13);
                        continue;
                    }
                    double theta = Math.atan2(y, x) + rot;
                    double petal = Math.cos(sym * 0.5 * theta) * Math.sin(radialFreq * r);
                    double rose = Math.cos((sym / 3.0) * theta) * Math.cos(innerRing * r);
                    double wave = 0.62 * petal + 0.38 * rose;
                    double grain = Math.exp(-(wave * wave) / (pulse * pulse * 0.9));
                    double rimGlow = Math.exp(-Math.pow((r - 0.90) / 0.04, 2.0));
                    double coreGlow = Math.exp(-(r * r) / 0.035);
                    int red = Math.min(255, (int) Math.round(6 + grain * 234 + rimGlow * 188 + coreGlow * 160));
                    int green = Math.min(255, (int) Math.round(9 + grain * 188 + rimGlow * 142 + coreGlow * 48));
                    int blue = Math.min(255, (int) Math.round(16 + grain * 108 + rimGlow * 74 + coreGlow * 78));
                    pixels[row + px] = (0xff << 24) | (red << 16) | (green << 8) | blue;
                }
            }
        }
        buffer.setPixels(pixels, 0, GRID, 0, 0, GRID, GRID);
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        dest.set(0, 0, getWidth(), getHeight());
        canvas.drawBitmap(buffer, null, dest, imagePaint);
        if (modeType == MODE_ROSE_DISC) {
            float cx = getWidth() * 0.5f;
            float cy = getHeight() * 0.5f;
            float outerRadius = Math.min(getWidth(), getHeight()) * 0.485f;
            float innerRadius = outerRadius * 0.93f;
            ringPaint.setColor(Ui.withAlpha(Ui.GOLD, 195));
            canvas.drawCircle(cx, cy, outerRadius, ringPaint);
            ringPaint.setColor(Ui.withAlpha(Ui.GOLD, 110));
            canvas.drawCircle(cx, cy, innerRadius, ringPaint);
            for (int i = 0; i < 24; i++) {
                double ang = (2.0 * Math.PI * i) / 24.0;
                float sx = cx + (float) (Math.cos(ang) * innerRadius);
                float sy = cy + (float) (Math.sin(ang) * innerRadius);
                float ex = cx + (float) (Math.cos(ang) * outerRadius);
                float ey = cy + (float) (Math.sin(ang) * outerRadius);
                canvas.drawLine(sx, sy, ex, ey, ringPaint);
            }
        }
        if (animating && isAttachedToWindow()) {
            phase += 0.07;
            renderPixels();
            postInvalidateDelayed(36);
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_DOWN) {
            if (getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(true);
            }
        } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_CANCEL) {
            if (getParent() != null) {
                getParent().requestDisallowInterceptTouchEvent(false);
            }
        }
        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_MOVE) {
            int prev0 = modes[0];
            int prev1 = modes[1];
            int prevRose = roseOrderIndex;
            float w = Math.max(1f, getWidth());
            float h = Math.max(1f, getHeight());
            float nx = Math.max(0f, Math.min(0.999f, event.getX() / w));
            float ny = Math.max(0f, Math.min(0.999f, event.getY() / h));
            modes[0] = 1 + (int) Math.floor(nx * 6);
            modes[1] = 1 + (int) Math.floor(ny * 6);
            modes[2] = 1 + ((modes[0] + modes[1]) % 7);
            modes[3] = 2 + ((modes[0] * 2 + modes[1]) % 6);
            roseOrderIndex = Math.min(ROSE_ORDERS.length - 1, (int) Math.floor(nx * ROSE_ORDERS.length));
            if (modes[0] != prev0 || modes[1] != prev1 || roseOrderIndex != prevRose) {
                performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK);
            }
            renderPixels();
            invalidate();
            notifyListener();
            return true;
        }
        if (action == MotionEvent.ACTION_UP) {
            performClick();
            return true;
        }
        return super.onTouchEvent(event);
    }

    @Override
    public boolean performClick() {
        return super.performClick();
    }

    @Override
    protected void onDetachedFromWindow() {
        animating = false;
        super.onDetachedFromWindow();
    }
}
