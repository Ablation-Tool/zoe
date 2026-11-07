package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

final class Ui {
    static final int BACKGROUND = Color.rgb(8, 13, 24);
    static final int PANEL = Color.rgb(16, 27, 43);
    static final int CYAN = Color.rgb(103, 232, 249);
    static final int YELLOW = Color.rgb(253, 230, 138);
    static final int PINK = Color.rgb(240, 171, 252);
    static final int GREEN = Color.rgb(134, 239, 172);
    static final int TEXT = Color.rgb(226, 232, 240);
    static final int MUTED = Color.rgb(159, 177, 200);

    private Ui() {
    }

    static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static LinearLayout vertical(Context context) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(BACKGROUND);
        return layout;
    }

    static TextView text(Context context, String value, float size, int color) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(size);
        view.setTextColor(color);
        view.setLineSpacing(0, 1.12f);
        view.setPadding(0, dp(context, 5), 0, dp(context, 5));
        return view;
    }

    static TextView heading(Context context, String value) {
        TextView view = text(context, value, 23, CYAN);
        view.setTypeface(Typeface.create("sans", Typeface.BOLD));
        return view;
    }

    static Button button(Context context, String label, View.OnClickListener listener) {
        Button button = new Button(context);
        button.setText(label);
        button.setTextSize(14);
        button.setTextColor(CYAN);
        button.setAllCaps(false);
        button.setMinHeight(dp(context, 48));
        button.setMinimumHeight(dp(context, 48));
        button.setPadding(dp(context, 12), dp(context, 8), dp(context, 12), dp(context, 8));
        button.setBackground(panelBackground(context, CYAN, 16));
        button.setOnClickListener(listener);
        button.setContentDescription(label);
        return button;
    }

    static GradientDrawable panelBackground(Context context, int stroke, int radiusDp) {
        GradientDrawable background = new GradientDrawable();
        background.setColor(PANEL);
        background.setCornerRadius(dp(context, radiusDp));
        background.setStroke(dp(context, 1), stroke);
        return background;
    }

    static LinearLayout.LayoutParams margins(int width, int height, Context context, int marginDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        int margin = dp(context, marginDp);
        params.setMargins(margin, margin, margin, margin);
        return params;
    }

    static LinearLayout buttonRow(Context context, Button... buttons) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        for (Button button : buttons) {
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
            params.setMargins(dp(context, 4), dp(context, 4), dp(context, 4), dp(context, 4));
            row.addView(button, params);
        }
        return row;
    }
}
