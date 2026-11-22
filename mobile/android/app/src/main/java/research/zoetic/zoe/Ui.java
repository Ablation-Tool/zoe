package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Outline;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.graphics.drawable.Drawable;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewOutlineProvider;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowInsetsControllerCompat;

import java.util.List;

/**
 * Google Gemini-inspired Material 3 Expressive design system for Zoe.
 * Built for effortless human & child-with-disabilities ergonomics:
 *   - Follows system Light/Dark automatically (with 1-tap toggle)
 *   - Huge >= 48dp-62dp touch targets with generous spacing
 *   - Open borderless lists, high WCAG AAA contrast, plain language, multimodal icon + text cues
 */
final class Ui {
    private static final String PREFS_NAME = "zoe_ui_prefs";
    private static final String KEY_THEME_OVERRIDE = "theme_override"; // -1 system, 0 light, 1 dark

    // Semantic color token constants (resolved dynamically per Light / Dark mode)
    static final int BACKGROUND = Color.rgb(5, 8, 17);
    static final int PANEL = Color.argb(226, 11, 18, 34);
    static final int PANEL_HI = Color.rgb(19, 30, 54);
    static final int BORDER = Color.rgb(38, 56, 92);
    static final int CYAN = Color.rgb(72, 229, 240);
    static final int RUBY = Color.rgb(239, 68, 90);
    static final int GOLD = Color.rgb(232, 193, 110);
    static final int YELLOW = Color.rgb(248, 225, 148);
    static final int PINK = Color.rgb(228, 152, 246);
    static final int GREEN = Color.rgb(110, 231, 168);
    static final int TEXT = Color.rgb(236, 241, 249);
    static final int MUTED = Color.rgb(148, 168, 198);
    static final int COBALT = Color.rgb(47, 108, 214);

    static final Typeface SANS_REGULAR = Typeface.create("sans-serif", Typeface.NORMAL);
    static final Typeface SANS_MEDIUM = Typeface.create("sans-serif-medium", Typeface.NORMAL);
    static final Typeface SANS_BOLD = Typeface.create("sans-serif", Typeface.BOLD);

    private Ui() {
    }

    private static SharedPreferences prefs(Context context) {
        return context.getApplicationContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
    }

    static boolean isDark(Context context) {
        if (context == null) {
            return true;
        }
        int override = prefs(context).getInt(KEY_THEME_OVERRIDE, -1);
        if (override == 1) {
            return true;
        }
        if (override == 0) {
            return false;
        }
        int uiMode = context.getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK;
        return uiMode == Configuration.UI_MODE_NIGHT_YES;
    }

    static void toggleDark(Context context) {
        if (context != null) {
            boolean nextDark = !isDark(context);
            prefs(context).edit().putInt(KEY_THEME_OVERRIDE, nextDark ? 1 : 0).apply();
        }
    }

    static String themeLabel(Context context) {
        return isDark(context) ? "Dark" : "Light";
    }

    static int resolveColor(Context context, int token) {
        boolean dark = isDark(context);
        int alpha = Color.alpha(token);
        int rgb = token & 0x00FFFFFF;
        int resolvedRgb;
        switch (rgb) {
            case 0x050811 -> resolvedRgb = dark ? 0x0E0F12 : 0xFFFFFF; // Google Gemini Canvas
            case 0x0B1222 -> {
                resolvedRgb = dark ? 0x1E1F20 : 0xF0F4F9; // Google Gemini Elevated Pill / Card Surface
                if (alpha == 226) {
                    alpha = 255;
                }
            }
            case 0x131E36 -> resolvedRgb = dark ? 0x2A2B2F : 0xE1E7F0; // Google Gemini Tonal Well
            case 0x26385C -> resolvedRgb = dark ? 0x33353A : 0xDCE1E8; // Soft Hairline
            case 0x48E5F0 -> resolvedRgb = dark ? 0x78D9EC : 0x007B83; // Google Teal
            case 0xEF445A -> resolvedRgb = dark ? 0xF43F5E : 0xD62848; // Zoe Living Ruby
            case 0xE8C16E -> resolvedRgb = dark ? 0xFDD663 : 0xB06000; // Google Warm Gold
            case 0xF8E194 -> resolvedRgb = dark ? 0xFDE293 : 0x9A5000; // Status Amber
            case 0xE498F6 -> resolvedRgb = dark ? 0xD7AEFB : 0x8430CE; // DeepMind Soft Violet
            case 0x6EE7A8 -> resolvedRgb = dark ? 0x81C995 : 0x137333; // Google Botanical Green
            case 0x2F6CD6 -> resolvedRgb = dark ? 0x8AB4F8 : 0x1A73E8; // Google DeepMind Blue
            case 0xECF1F9 -> resolvedRgb = dark ? 0xE8EAED : 0x1F1F1F; // Primary Ink (WCAG AAA)
            case 0x94A8C6 -> resolvedRgb = dark ? 0x9AA0A6 : 0x5F6368; // Secondary Muted Ink
            default -> {
                return token;
            }
        }
        return Color.argb(alpha, Color.red(resolvedRgb), Color.green(resolvedRgb), Color.blue(resolvedRgb));
    }

    static int bgColor(Context context) {
        return resolveColor(context, BACKGROUND);
    }

    static int panelColor(Context context) {
        return resolveColor(context, PANEL);
    }

    static int tonalWellColor(Context context) {
        return resolveColor(context, PANEL_HI);
    }

    static int dividerColor(Context context) {
        return resolveColor(context, BORDER);
    }

    static int textColor(Context context) {
        return resolveColor(context, TEXT);
    }

    static int mutedColor(Context context) {
        return resolveColor(context, MUTED);
    }

    /** Primary interactive Google DeepMind Blue accent. */
    static int primaryAccent(Context context) {
        return resolveColor(context, COBALT);
    }

    /** Zoe's warm Living Ruby brand accent. */
    static int heroAccent(Context context) {
        return resolveColor(context, RUBY);
    }

    static int dp(Context context, int value) {
        return Math.round(value * context.getResources().getDisplayMetrics().density);
    }

    static int strokePx(Context context, float strokeDp) {
        return Math.max(1, Math.round(strokeDp * context.getResources().getDisplayMetrics().density));
    }

    static int withAlpha(int color, int alpha) {
        return Color.argb(alpha, Color.red(color), Color.green(color), Color.blue(color));
    }

    static FrameLayout wrapWithBackdrop(Context context, View foreground) {
        return wrapWithBackdrop(context, foreground, false);
    }

    static FrameLayout wrapWithBackdrop(Context context, View foreground, boolean ignoredDesktopMode) {
        FrameLayout frame = new FrameLayout(context);
        frame.setBackgroundColor(bgColor(context));
        frame.addView(new ZoeBackdropView(context), new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        foreground.setBackgroundColor(Color.TRANSPARENT);
        frame.addView(foreground, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        return frame;
    }

    /** Gentle Google Gemini-style horizontal gradient headline (high contrast in both Light & Dark). */
    static void applyGeminiGreetingShader(TextView view) {
        boolean dark = isDark(view.getContext());
        int start = dark ? Color.rgb(138, 180, 248) : Color.rgb(26, 115, 232);
        int mid = dark ? Color.rgb(197, 138, 249) : Color.rgb(147, 51, 234);
        int end = dark ? Color.rgb(244, 114, 146) : Color.rgb(214, 40, 72);
        view.post(() -> {
            float width = Math.max(view.getWidth(), dp(view.getContext(), 220));
            view.getPaint().setShader(new LinearGradient(
                    0f, 0f, width, 0f,
                    new int[]{start, mid, end},
                    new float[]{0f, 0.52f, 1f},
                    Shader.TileMode.CLAMP));
            view.invalidate();
        });
    }

    static void applyGradientText(TextView view, int startColor, int midColor, int endColor) {
        view.getPaint().setShader(null);
        view.setTextColor(textColor(view.getContext()));
    }

    /** Pure borderless Zoe Living Spark emblem (no harsh ring, clean floating icon). */
    static ImageView zoeSparkIcon(Context context, int sizeDp) {
        ImageView image = new ImageView(context);
        image.setImageResource(R.drawable.zoe_ruby_sprout);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        image.setLayoutParams(new LinearLayout.LayoutParams(dp(context, sizeDp), dp(context, sizeDp)));
        return image;
    }

    /** Navigates straight back to Zoe's Home screen from any nested screen. */
    static void goHome(android.app.Activity activity) {
        if (activity == null) {
            return;
        }
        if (activity instanceof MainActivity) {
            ((MainActivity) activity).showHome();
            return;
        }
        android.content.Intent home = new android.content.Intent(activity, MainActivity.class)
                .addFlags(android.content.Intent.FLAG_ACTIVITY_CLEAR_TOP | android.content.Intent.FLAG_ACTIVITY_SINGLE_TOP);
        activity.startActivity(home);
        activity.finish();
    }

    /** Ergonomic 48dp tappable Zoe GEM-Ellipsis home button. */
    static ImageView gemHomeButton(Context context, int iconSizeDp, Runnable onClick) {
        ImageView icon = zoeSparkIcon(context, iconSizeDp);
        int pad = Math.max(dp(context, 4), (dp(context, 48) - dp(context, iconSizeDp)) / 2);
        icon.setPadding(pad, pad, pad, pad);
        icon.setClickable(true);
        icon.setFocusable(true);
        icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_YES);
        icon.setContentDescription("Return to Zoe home");
        icon.setBackground(tonalPillDrawable(context, Color.TRANSPARENT, primaryAccent(context), 99));
        icon.setOnClickListener(view -> {
            view.performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK);
            if (onClick != null) {
                onClick.run();
            }
        });
        return icon;
    }

    static FrameLayout circularFramedImage(Context context, int drawableRes, int sizeDp,
                                             int ringStart, int ringEnd) {
        int outerPx = dp(context, sizeDp);
        FrameLayout box = new FrameLayout(context);
        box.setBackgroundColor(Color.TRANSPARENT);
        box.setLayoutParams(new LinearLayout.LayoutParams(outerPx, outerPx));

        ImageView image = new ImageView(context);
        image.setImageResource(drawableRes);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setOutlineProvider(new ViewOutlineProvider() {
            @Override
            public void getOutline(View view, Outline outline) {
                outline.setOval(0, 0, view.getWidth(), view.getHeight());
            }
        });
        image.setClipToOutline(true);
        box.addView(image, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        return box;
    }

    static void configureEdgeToEdge(ComponentActivity activity, View root) {
        WindowCompat.setDecorFitsSystemWindows(activity.getWindow(), false);
        WindowInsetsControllerCompat controller = WindowCompat.getInsetsController(
                activity.getWindow(), activity.getWindow().getDecorView());
        if (controller != null) {
            boolean light = !isDark(activity);
            controller.setAppearanceLightStatusBars(light);
            controller.setAppearanceLightNavigationBars(light);
        }
        final int baseLeft = root.getPaddingLeft();
        final int baseTop = root.getPaddingTop();
        final int baseRight = root.getPaddingRight();
        final int baseBottom = root.getPaddingBottom();
        ViewCompat.setOnApplyWindowInsetsListener(root, (view, windowInsets) -> {
            Insets insets = windowInsets.getInsets(
                    WindowInsetsCompat.Type.systemBars()
                            | WindowInsetsCompat.Type.displayCutout()
                            | WindowInsetsCompat.Type.ime());
            view.setPadding(
                    baseLeft + insets.left,
                    baseTop + insets.top,
                    baseRight + insets.right,
                    baseBottom + insets.bottom);
            return windowInsets;
        });
        ViewCompat.requestApplyInsets(root);
    }

    /** Clean Google Gemini borderless top bar with generous 48dp back target. */
    static LinearLayout topBar(ComponentActivity activity, String title, String subtitle) {
        LinearLayout container = new LinearLayout(activity);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setBackgroundColor(Color.TRANSPARENT);
        container.setPadding(0, dp(activity, 2), 0, dp(activity, 6));

        LinearLayout row = new LinearLayout(activity);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setBackgroundColor(Color.TRANSPARENT);

        Button back = tonalIconButton(activity, "←", "Back to Zoe home", view -> activity.finish());
        LinearLayout.LayoutParams backParams = new LinearLayout.LayoutParams(dp(activity, 48), dp(activity, 48));
        backParams.setMargins(0, 0, dp(activity, 12), 0);
        row.addView(back, backParams);

        LinearLayout titles = new LinearLayout(activity);
        titles.setOrientation(LinearLayout.VERTICAL);
        titles.setBackgroundColor(Color.TRANSPARENT);

        TextView titleView = text(activity, title, 21f, TEXT);
        titleView.setTypeface(SANS_MEDIUM);
        titleView.setLetterSpacing(-0.015f);
        titleView.setPadding(0, 0, 0, 0);
        titleView.setMaxLines(1);
        titleView.setEllipsize(TextUtils.TruncateAt.END);
        ViewCompat.setAccessibilityHeading(titleView, true);
        titles.addView(titleView);

        if (subtitle != null && !subtitle.isEmpty()) {
            TextView subView = text(activity, subtitle, 13.5f, MUTED);
            subView.setPadding(0, dp(activity, 2), 0, 0);
            subView.setMaxLines(1);
            subView.setEllipsize(TextUtils.TruncateAt.END);
            titles.addView(subView);
        }
        row.addView(titles, new LinearLayout.LayoutParams(
                0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        ImageView gemHome = gemHomeButton(activity, 30, () -> goHome(activity));
        gemHome.setId(R.id.zoe_gem_home);
        LinearLayout.LayoutParams gemHomeLp = new LinearLayout.LayoutParams(dp(activity, 48), dp(activity, 48));
        gemHomeLp.setMargins(dp(activity, 8), 0, 0, 0);
        row.addView(gemHome, gemHomeLp);

        container.addView(row);
        return container;
    }

    /** Ergonomic 48dp circular icon button (zero clutter, crisp ripple). */
    static Button tonalIconButton(Context context, String glyph, String contentDesc, View.OnClickListener listener) {
        Button b = new Button(context);
        b.setText(glyph);
        b.setTextSize(19f);
        b.setTextColor(textColor(context));
        b.setTypeface(SANS_MEDIUM);
        b.setAllCaps(false);
        b.setGravity(Gravity.CENTER);
        b.setMinWidth(dp(context, 48));
        b.setMinimumWidth(dp(context, 48));
        b.setMinHeight(dp(context, 48));
        b.setMinimumHeight(dp(context, 48));
        b.setBackground(tonalPillDrawable(context, Color.TRANSPARENT, primaryAccent(context), 99));
        b.setPadding(0, 0, 0, 0);
        b.setContentDescription(contentDesc);
        b.setOnClickListener(listener);
        b.setStateListAnimator(null);
        return b;
    }

    /** Ergonomic 48dp drawable icon button (Google Gemini top/bottom bar glyphs). */
    static ImageView iconActionButton(Context context, int iconRes, int tintColor,
                                      int bgFillColor, String contentDesc, View.OnClickListener listener) {
        ImageView iv = new ImageView(context);
        iv.setImageResource(iconRes);
        iv.setColorFilter(tintColor);
        int pad = dp(context, 12);
        iv.setPadding(pad, pad, pad, pad);
        iv.setMinimumWidth(dp(context, 48));
        iv.setMinimumHeight(dp(context, 48));
        iv.setBackground(tonalPillDrawable(context, bgFillColor, primaryAccent(context), 99));
        iv.setClickable(true);
        iv.setFocusable(true);
        iv.setContentDescription(contentDesc);
        iv.setOnClickListener(listener);
        return iv;
    }

    static LinearLayout vertical(Context context) {
        LinearLayout layout = new LinearLayout(context);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(bgColor(context));
        return layout;
    }

    static TextView text(Context context, String value, float size, int color) {
        TextView view = new TextView(context);
        view.setText(value);
        view.setTextSize(size);
        view.setTypeface(SANS_REGULAR);
        view.setTextColor(resolveColor(context, color));
        view.setLineSpacing(0, 1.28f);
        view.setPadding(0, dp(context, 4), 0, dp(context, 4));
        return view;
    }

    static TextView heading(Context context, String value) {
        TextView view = text(context, value, 26f, TEXT);
        view.setTypeface(SANS_MEDIUM);
        view.setLetterSpacing(-0.02f);
        ViewCompat.setAccessibilityHeading(view, true);
        return view;
    }

    static TextView badge(Context context, String label, int accent) {
        int resolved = resolveColor(context, accent);
        boolean dark = isDark(context);
        TextView view = new TextView(context);
        view.setText(label);
        view.setTextSize(12.5f);
        view.setTextColor(resolved);
        view.setTypeface(SANS_MEDIUM);
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(withAlpha(resolved, dark ? 44 : 24));
        bg.setCornerRadius(dp(context, 99));
        view.setBackground(bg);
        view.setPadding(dp(context, 12), dp(context, 5), dp(context, 12), dp(context, 5));
        return view;
    }

    static Button button(Context context, String label, View.OnClickListener listener) {
        return button(context, label, COBALT, listener);
    }

    /** Primary CTA pill: refined 48dp Material 3 Expressive stadium pill (never awkwardly wraps). */
    static Button primaryButton(Context context, String label, int accent, View.OnClickListener listener) {
        boolean dark = isDark(context);
        int fill = dark ? Color.rgb(138, 180, 248) : Color.rgb(26, 115, 232);
        int ink = dark ? Color.rgb(14, 15, 18) : Color.WHITE;
        Button button = new Button(context);
        button.setText(label);
        button.setTextSize(14.5f);
        button.setTextColor(stateTextColors(ink, withAlpha(textColor(context), 110)));
        button.setTypeface(SANS_MEDIUM);
        button.setAllCaps(false);
        button.setMaxLines(1);
        button.setEllipsize(TextUtils.TruncateAt.END);
        button.setMinHeight(dp(context, 48));
        button.setMinimumHeight(dp(context, 48));
        button.setBackground(statePillDrawable(context, fill, tonalWellColor(context), ink, 24));
        button.setPadding(dp(context, 16), dp(context, 8), dp(context, 16), dp(context, 8));
        button.setOnClickListener(listener);
        button.setContentDescription(label);
        button.setStateListAnimator(null);
        return button;
    }

    /** Secondary action pill: 46dp airy tonal pill with subtle hairline definition (single-line crisp). */
    static Button button(Context context, String label, int accent, View.OnClickListener listener) {
        int fill = tonalWellColor(context);
        int ink = textColor(context);
        Button button = new Button(context);
        button.setText(label);
        button.setTextSize(14f);
        button.setTextColor(stateTextColors(ink, withAlpha(ink, 95)));
        button.setTypeface(SANS_MEDIUM);
        button.setAllCaps(false);
        button.setMaxLines(1);
        button.setEllipsize(TextUtils.TruncateAt.END);
        button.setMinHeight(dp(context, 46));
        button.setMinimumHeight(dp(context, 46));
        button.setBackground(statePillDrawable(context, fill, withAlpha(fill, 110), primaryAccent(context), 23));
        button.setPadding(dp(context, 14), dp(context, 8), dp(context, 14), dp(context, 8));
        button.setOnClickListener(listener);
        button.setContentDescription(label);
        button.setStateListAnimator(null);
        return button;
    }

    private static ColorStateList stateTextColors(int enabledColor, int disabledColor) {
        return new ColorStateList(
                new int[][]{new int[]{-android.R.attr.state_enabled}, new int[]{}},
                new int[]{disabledColor, enabledColor});
    }

    private static Drawable statePillDrawable(Context context, int enabledFill, int disabledFill,
                                              int rippleColor, int radiusDp) {
        GradientDrawable fill = new GradientDrawable();
        fill.setColor(new ColorStateList(
                new int[][]{new int[]{-android.R.attr.state_enabled}, new int[]{}},
                new int[]{disabledFill, enabledFill}));
        fill.setCornerRadius(dp(context, radiusDp));
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(Color.WHITE);
        mask.setCornerRadius(dp(context, radiusDp));
        return new RippleDrawable(ColorStateList.valueOf(withAlpha(rippleColor, 40)), fill, mask);
    }

    /** Quiet text-only disclosure trigger (keeps optional advanced controls calm). */
    static Button disclosureButton(Context context, String label, View.OnClickListener listener) {
        Button b = button(context, label, MUTED, listener);
        b.setTextSize(14f);
        b.setTextColor(mutedColor(context));
        b.setBackground(tonalPillDrawable(context, Color.TRANSPARENT, primaryAccent(context), 22));
        return b;
    }

    static Drawable tonalPillDrawable(Context context, int fillColor, int rippleColor, int radiusDp) {
        GradientDrawable fill = new GradientDrawable();
        fill.setColor(fillColor);
        fill.setCornerRadius(dp(context, radiusDp));
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(Color.WHITE);
        mask.setCornerRadius(dp(context, radiusDp));
        return new RippleDrawable(ColorStateList.valueOf(withAlpha(rippleColor, 40)), fill, mask);
    }

    static Drawable outlinedPillDrawable(Context context, int fillColor, int strokeColor, int rippleColor, int radiusDp) {
        GradientDrawable fill = new GradientDrawable();
        fill.setColor(fillColor);
        fill.setCornerRadius(dp(context, radiusDp));
        fill.setStroke(strokePx(context, 1f), strokeColor);
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(Color.WHITE);
        mask.setCornerRadius(dp(context, radiusDp));
        return new RippleDrawable(ColorStateList.valueOf(withAlpha(rippleColor, 40)), fill, mask);
    }

    static EditText input(Context context, String initial, String hint) {
        EditText input = new EditText(context);
        input.setText(initial);
        input.setHint(hint);
        input.setTextSize(16f);
        input.setTypeface(SANS_REGULAR);
        input.setTextColor(textColor(context));
        input.setHintTextColor(mutedColor(context));
        input.setMinHeight(dp(context, 54));
        input.setMinimumHeight(dp(context, 54));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(tonalWellColor(context));
        bg.setCornerRadius(dp(context, 18));
        input.setBackground(bg);
        input.setPadding(dp(context, 18), dp(context, 14), dp(context, 18), dp(context, 14));
        return input;
    }

    /** Soft Google Gemini elevated surface with whisper-thin glass edge definition. */
    static GradientDrawable cardBackground(Context context, int radiusDp) {
        boolean dark = isDark(context);
        GradientDrawable background = new GradientDrawable();
        background.setColor(panelColor(context));
        background.setStroke(strokePx(context, 0.75f), withAlpha(dividerColor(context), dark ? 80 : 120));
        background.setCornerRadius(dp(context, radiusDp));
        return background;
    }

    static GradientDrawable panelBackground(Context context, int stroke, int radiusDp) {
        return cardBackground(context, Math.min(radiusDp, 22));
    }

    static GradientDrawable panelBackground(Context context, int fillColor, int stroke, int radiusDp) {
        int resolvedFill = resolveColor(context, fillColor);
        GradientDrawable background = new GradientDrawable();
        background.setColor(resolvedFill);
        background.setCornerRadius(dp(context, Math.min(radiusDp, 22)));
        return background;
    }

    static Drawable ripplePanel(Context context, int fillColor, int stroke, int radiusDp, int rippleColor) {
        GradientDrawable surface = panelBackground(context, fillColor, stroke, radiusDp);
        GradientDrawable mask = new GradientDrawable();
        mask.setColor(Color.WHITE);
        mask.setCornerRadius(dp(context, Math.min(radiusDp, 22)));
        return new RippleDrawable(ColorStateList.valueOf(withAlpha(resolveColor(context, rippleColor), 36)), surface, mask);
    }

    static Drawable heroBackground(Context context) {
        return cardBackground(context, 24);
    }

    static ArrayAdapter<String> spinnerAdapter(Context context, List<String> items) {
        return new ArrayAdapter<>(context, android.R.layout.simple_spinner_dropdown_item, items) {
            @Override
            public View getView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getView(position, convertView, parent);
                view.setTextColor(textColor(context));
                view.setTextSize(15f);
                view.setTypeface(SANS_REGULAR);
                view.setPadding(dp(context, 14), dp(context, 12), dp(context, 14), dp(context, 12));
                return view;
            }

            @Override
            public View getDropDownView(int position, View convertView, ViewGroup parent) {
                TextView view = (TextView) super.getDropDownView(position, convertView, parent);
                view.setTextColor(textColor(context));
                view.setBackgroundColor(panelColor(context));
                view.setTextSize(15f);
                view.setPadding(dp(context, 16), dp(context, 14), dp(context, 16), dp(context, 14));
                return view;
            }
        };
    }

    static String networkStatusLabel(Context context) {
        try {
            ConnectivityManager cm = (ConnectivityManager) context.getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm == null) {
                return "Offline";
            }
            Network active = cm.getActiveNetwork();
            if (active == null) {
                return "Offline";
            }
            NetworkCapabilities caps = cm.getNetworkCapabilities(active);
            if (caps == null) {
                return "Offline";
            }
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                return "Wi-Fi";
            }
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR)) {
                return "Mobile data";
            }
            if (caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)) {
                return "Ethernet";
            }
            return "Online";
        } catch (RuntimeException error) {
            return "Offline";
        }
    }

    static LinearLayout.LayoutParams margins(int width, int height, Context context, int marginDp) {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(width, height);
        int margin = dp(context, marginDp);
        params.setMargins(margin, margin, margin, margin);
        return params;
    }

    /** Soft circular tinted icon well (child-friendly, unmistakable visual cue). */
    static ImageView iconCircle(Context context, int iconRes, int accent, int sizeDp) {
        int resolved = resolveColor(context, accent);
        boolean dark = isDark(context);
        ImageView symbol = new ImageView(context);
        symbol.setImageResource(iconRes);
        symbol.setColorFilter(resolved);
        int pad = dp(context, sizeDp >= 44 ? 11 : 9);
        symbol.setPadding(pad, pad, pad, pad);
        GradientDrawable well = new GradientDrawable();
        well.setShape(GradientDrawable.OVAL);
        well.setColor(withAlpha(resolved, dark ? 38 : 22));
        symbol.setBackground(well);
        symbol.setContentDescription(null);
        symbol.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        symbol.setLayoutParams(new LinearLayout.LayoutParams(dp(context, sizeDp), dp(context, sizeDp)));
        return symbol;
    }

    /**
     * Borderless Google Gemini-style open action row:
     * zero visual box clutter, huge 62dp ergonomic touch target, crisp friendly icon +
     * plain-English 17sp title + 3-word calm helper for effortless adult & child scanning.
     */
    static LinearLayout geminiActionRow(Context context, String title, String helper, int iconRes,
                                        int accent, View.OnClickListener listener) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setMinimumHeight(dp(context, 62));
        row.setBackground(tonalPillDrawable(context, Color.TRANSPARENT, accent, 20));
        row.setPadding(dp(context, 16), dp(context, 10), dp(context, 16), dp(context, 10));
        row.setClickable(true);
        row.setFocusable(true);
        row.setContentDescription(title + ". " + helper);
        row.setOnClickListener(listener);

        row.addView(iconCircle(context, iconRes, accent, 42));

        LinearLayout labels = new LinearLayout(context);
        labels.setOrientation(LinearLayout.VERTICAL);
        labels.setBackgroundColor(Color.TRANSPARENT);
        labels.setPadding(dp(context, 16), 0, dp(context, 8), 0);

        TextView titleView = text(context, title, 17f, TEXT);
        titleView.setTypeface(SANS_REGULAR);
        titleView.setPadding(0, 0, 0, dp(context, 1));
        titleView.setMaxLines(1);
        titleView.setEllipsize(TextUtils.TruncateAt.END);
        titleView.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        labels.addView(titleView);

        if (helper != null && !helper.isEmpty()) {
            TextView subView = text(context, helper, 13.5f, MUTED);
            subView.setPadding(0, 0, 0, 0);
            subView.setMaxLines(1);
            subView.setEllipsize(TextUtils.TruncateAt.END);
            subView.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
            labels.addView(subView);
        }
        row.addView(labels, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));
        return row;
    }

    /** Single clean row for use inside a grouped container (Field kit, etc.). */
    static LinearLayout groupedRow(Context context, String title, String subtitle, int icon,
                                   int accent, View.OnClickListener listener) {
        LinearLayout row = geminiActionRow(context, title, subtitle, icon, accent, listener);
        TextView chevron = text(context, "›", 20f, MUTED);
        chevron.setAlpha(0.55f);
        chevron.setGravity(Gravity.CENTER);
        chevron.setPadding(0, 0, 0, 0);
        chevron.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        row.addView(chevron, new LinearLayout.LayoutParams(dp(context, 20), dp(context, 42)));
        return row;
    }

    /** Inset hairline separator inside a grouped card. */
    static View insetDivider(Context context) {
        View line = new View(context);
        line.setBackgroundColor(dividerColor(context));
        line.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, strokePx(context, 0.7f));
        p.setMargins(dp(context, 72), 0, dp(context, 16), 0);
        line.setLayoutParams(p);
        return line;
    }

    /** Soft borderless grouped container holding rows with inset dividers. */
    static LinearLayout groupedCard(Context context) {
        LinearLayout card = new LinearLayout(context);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(cardBackground(context, 24));
        card.setPadding(0, dp(context, 6), 0, dp(context, 6));
        card.setClipToOutline(true);
        return card;
    }

    static LinearLayout tool(Context context, String title, String subtitle, int icon,
                             int accent, View.OnClickListener listener) {
        return tool(context, null, title, subtitle, icon, accent, listener);
    }

    static LinearLayout tool(Context context, String indexTag, String title, String subtitle, int icon,
                             int accent, View.OnClickListener listener) {
        LinearLayout row = groupedRow(context, title, subtitle, icon, accent, listener);
        row.setBackground(ripplePanel(context, PANEL, BORDER, 20, accent));
        LinearLayout.LayoutParams margins = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        margins.setMargins(dp(context, 16), dp(context, 5), dp(context, 16), dp(context, 5));
        row.setLayoutParams(margins);
        return row;
    }

    /** Calm native section header (preserves label text verbatim for tests & semantics). */
    static TextView section(Context context, String label) {
        TextView section = text(context, label, 13.5f, MUTED);
        section.setTypeface(SANS_MEDIUM);
        section.setLetterSpacing(0.03f);
        section.setPadding(dp(context, 20), dp(context, 18), dp(context, 16), dp(context, 8));
        ViewCompat.setAccessibilityHeading(section, true);
        return section;
    }

    static LinearLayout buttonRow(Context context, Button... buttons) {
        LinearLayout row = new LinearLayout(context);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER);
        for (Button button : buttons) {
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
            params.setMargins(dp(context, 5), dp(context, 5), dp(context, 5), dp(context, 5));
            row.addView(button, params);
        }
        return row;
    }
}
