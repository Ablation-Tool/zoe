package research.zoetic.zoe;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.text.TextUtils;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.core.view.ViewCompat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Google DeepMind x Zoe Home Screen — engineered for effortless human & child-with-disabilities ergonomics:
 *   - Borderless Google Gemini top bar (= menu, "Zoe Private •", theme toggle, Zoe GEM-Ellipsis emblem)
 *   - Spacious breathing greeting with Zoe GEM-Ellipsis anchor
 *   - Focused Top 3 spacious 72dp rounded pill cards (reduces Hick's Law cognitive load immediately!)
 *   - Gemini-style Explore | Arrange pill toggle visible right above the fold
 *   - Calm grouped "More Zapps" card tucked cleanly below gentle breathing space
 */
final class HomeView extends ScrollView {
    private static final class ZappSpec {
        final String id;
        final String title;
        final String simpleHelper;
        final int iconRes;
        final int accent;
        final Runnable action;

        ZappSpec(String id, String title, String simpleHelper,
                 int iconRes, int accent, Runnable action) {
            this.id = id;
            this.title = title;
            this.simpleHelper = simpleHelper;
            this.iconRes = iconRes;
            this.accent = accent;
            this.action = action;
        }
    }

    private final MainActivity host;
    private final TextView modePillLabel;
    private final Button explorePill;
    private final Button arrangeButton;
    private final Button resetButton;
    private final TextView zappsHint;
    private final LinearLayout primaryContainer;
    private final LinearLayout moreContainer;
    private final Map<String, ZappSpec> zappMap = new LinkedHashMap<>();
    private boolean arrangeMode;
    private int savedSightingsCount;

    HomeView(MainActivity activity) {
        super(activity);
        this.host = activity;
        setFillViewport(true);
        setBackgroundColor(Color.TRANSPARENT);

        LinearLayout content = Ui.vertical(activity);
        content.setBackgroundColor(Color.TRANSPARENT);
        content.setPadding(0, Ui.dp(activity, 4), 0, Ui.dp(activity, 20));
        addView(content);

        // 1. Ultra-clean Google Gemini Borderless Top Bar
        LinearLayout topBar = new LinearLayout(activity);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setBackgroundColor(Color.TRANSPARENT);
        topBar.setPadding(Ui.dp(activity, 12), Ui.dp(activity, 6), Ui.dp(activity, 12), Ui.dp(activity, 4));

        ImageView menuBtn = Ui.iconActionButton(
                activity,
                R.drawable.ic_zoe_menu,
                Ui.textColor(activity),
                Color.TRANSPARENT,
                "Open menu",
                v -> showQuickSheet());
        topBar.addView(menuBtn, new LinearLayout.LayoutParams(Ui.dp(activity, 48), Ui.dp(activity, 48)));

        LinearLayout brandTap = new LinearLayout(activity);
        brandTap.setOrientation(LinearLayout.HORIZONTAL);
        brandTap.setGravity(Gravity.CENTER_VERTICAL);
        brandTap.setMinimumHeight(Ui.dp(activity, 48));
        brandTap.setPadding(Ui.dp(activity, 8), 0, Ui.dp(activity, 8), 0);
        brandTap.setClickable(true);
        brandTap.setFocusable(true);
        brandTap.setContentDescription("About Zoe");
        brandTap.setOnClickListener(v -> showAboutSheet());

        TextView brandTitle = Ui.text(activity, "Zoe", 21f, Ui.TEXT);
        brandTitle.setTypeface(Ui.SANS_REGULAR);
        brandTitle.setPadding(0, 0, Ui.dp(activity, 6), 0);
        ViewCompat.setAccessibilityHeading(brandTitle, true);
        brandTap.addView(brandTitle);

        modePillLabel = Ui.text(activity, "beta", 16f, Ui.MUTED);
        modePillLabel.setPadding(0, 0, Ui.dp(activity, 6), 0);
        brandTap.addView(modePillLabel);

        View dot = new View(activity);
        GradientDrawable dotBg = new GradientDrawable();
        dotBg.setShape(GradientDrawable.OVAL);
        dotBg.setColor(Ui.primaryAccent(activity));
        dot.setBackground(dotBg);
        dot.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams dotParams = new LinearLayout.LayoutParams(Ui.dp(activity, 7), Ui.dp(activity, 7));
        dotParams.setMargins(0, 0, 0, Ui.dp(activity, 8));
        brandTap.addView(dot, dotParams);

        topBar.addView(brandTap);

        View spacer = new View(activity);
        spacer.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        topBar.addView(spacer, new LinearLayout.LayoutParams(0, 1, 1.0f));

        boolean dark = Ui.isDark(activity);
        Button themeButton = Ui.tonalIconButton(
                activity,
                dark ? "☼" : "◐",
                dark ? "Switch to Light appearance" : "Switch to Dark appearance",
                view -> {
                    performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    Ui.toggleDark(getContext());
                    activity.recreate();
                });
        themeButton.setId(R.id.home_theme_toggle);
        topBar.addView(themeButton, new LinearLayout.LayoutParams(Ui.dp(activity, 48), Ui.dp(activity, 48)));

        ImageView gemAvatar = Ui.gemHomeButton(activity, 32, this::returnToHomeTop);
        topBar.addView(gemAvatar, new LinearLayout.LayoutParams(Ui.dp(activity, 48), Ui.dp(activity, 48)));
        content.addView(topBar);

        // 2. Spacious, Calm Breathing Hero with Zoe GEM-Ellipsis Anchor
        LinearLayout hero = new LinearLayout(activity);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setBackgroundColor(Color.TRANSPARENT);
        hero.setPadding(Ui.dp(activity, 24), Ui.dp(activity, 28), Ui.dp(activity, 24), Ui.dp(activity, 24));

        ImageView heroGem = Ui.zoeSparkIcon(activity, 46);
        heroGem.setClickable(true);
        heroGem.setFocusable(true);
        heroGem.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
        heroGem.setContentDescription("Zoe home");
        heroGem.setBackground(Ui.tonalPillDrawable(activity, Color.TRANSPARENT, Ui.primaryAccent(activity), 16));
        heroGem.setOnClickListener(v -> {
            v.performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
            returnToHomeTop();
        });
        LinearLayout.LayoutParams gemLp = new LinearLayout.LayoutParams(Ui.dp(activity, 48), Ui.dp(activity, 48));
        gemLp.setMargins(0, 0, 0, Ui.dp(activity, 12));
        hero.addView(heroGem, gemLp);

        TextView greeting = Ui.text(activity, "Hi, I'm Zoe", 32f, Ui.TEXT);
        greeting.setTypeface(Ui.SANS_MEDIUM);
        greeting.setLetterSpacing(-0.025f);
        greeting.setPadding(0, 0, 0, Ui.dp(activity, 4));
        Ui.applyGeminiGreetingShader(greeting);
        hero.addView(greeting);

        TextView tagline = Ui.text(activity, "Follow your curiosity.", 17f, Ui.MUTED);
        tagline.setPadding(0, 0, 0, 0);
        hero.addView(tagline);
        content.addView(hero);

        registerSpecs(activity);

        // 3. Focused Primary Stage (Top 3 Big Ergonomic 72dp Pill Cards — Zero Overload!)
        primaryContainer = Ui.vertical(activity);
        primaryContainer.setId(R.id.home_zapps_list);
        primaryContainer.setBackgroundColor(Color.TRANSPARENT);
        primaryContainer.setPadding(Ui.dp(activity, 16), 0, Ui.dp(activity, 16), 0);
        content.addView(primaryContainer);

        // 4. Gemini-Style Explore | Arrange Mode Toggle — RIGHT ABOVE THE FOLD!
        zappsHint = Ui.text(activity, "Tap ★ to pin #1, or ↑ ↓ to move any Zapp.", 13.5f, Ui.MUTED);
        zappsHint.setGravity(Gravity.CENTER);
        zappsHint.setPadding(Ui.dp(activity, 24), Ui.dp(activity, 12), Ui.dp(activity, 24), Ui.dp(activity, 2));
        zappsHint.setVisibility(GONE);
        content.addView(zappsHint);

        LinearLayout pillRow = new LinearLayout(activity);
        pillRow.setOrientation(LinearLayout.HORIZONTAL);
        pillRow.setGravity(Gravity.CENTER);
        pillRow.setBackgroundColor(Color.TRANSPARENT);
        pillRow.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 18), Ui.dp(activity, 16), Ui.dp(activity, 8));

        explorePill = modeTogglePill("Explore", v -> {
            if (arrangeMode) {
                toggleArrangeMode();
            }
        });
        LinearLayout.LayoutParams ep = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(activity, 44));
        ep.setMargins(Ui.dp(activity, 4), 0, Ui.dp(activity, 4), 0);
        pillRow.addView(explorePill, ep);

        arrangeButton = modeTogglePill("Arrange", v -> toggleArrangeMode());
        arrangeButton.setId(R.id.home_arrange_zapps);
        arrangeButton.setContentDescription("Arrange Zapps");
        LinearLayout.LayoutParams ap = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(activity, 44));
        ap.setMargins(Ui.dp(activity, 4), 0, Ui.dp(activity, 4), 0);
        pillRow.addView(arrangeButton, ap);

        resetButton = modeTogglePill("Reset", v -> {
            performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
            ZappLayoutStore.resetOrder(getContext());
            renderZapps();
        });
        resetButton.setId(R.id.home_reset_zapps);
        resetButton.setTextColor(Ui.heroAccent(activity));
        resetButton.setVisibility(GONE);
        LinearLayout.LayoutParams rp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(activity, 44));
        rp.setMargins(Ui.dp(activity, 4), 0, Ui.dp(activity, 4), 0);
        pillRow.addView(resetButton, rp);
        content.addView(pillRow);

        // 5. Calm Grouped "More tools" Drawer-Card tucked gently below the fold
        moreContainer = Ui.vertical(activity);
        moreContainer.setBackgroundColor(Color.TRANSPARENT);
        moreContainer.setPadding(0, Ui.dp(activity, 20), 0, 0);
        content.addView(moreContainer);

        styleModePills();
        refreshDynamic();
    }

    private void registerSpecs(MainActivity activity) {
        addSpec(new ZappSpec("vision", "Guided vision",
                "Look around & read aloud",
                R.drawable.ic_zoe_vision, Ui.COBALT, activity::showVision));
        addSpec(new ZappSpec("talk", "Talk",
                "Speak or type calmly with Zoe",
                R.drawable.ic_zoe_talk, Ui.RUBY, () -> open(ConversationActivity.class)));
        addSpec(new ZappSpec("journal", "Trip journal",
                "Your saved notes & photos",
                R.drawable.ic_zoe_trip, Ui.GREEN, () -> open(TripJournalActivity.class)));
        addSpec(new ZappSpec("studio", "Eliza-GEM Studio",
                "Sound shapes & local lab",
                R.drawable.ic_zoe_gem, Ui.PINK, () -> open(ElizaGemActivity.class)));
        addSpec(new ZappSpec("maps", "Maps & Safety",
                "Live GPS, Google Maps & Safety app",
                R.drawable.ic_zoe_location, Ui.CYAN, () -> open(LocationActivity.class)));
        addSpec(new ZappSpec("volume", "Accessible volume",
                "Count open choices clearly",
                R.drawable.ic_zoe_volume, Ui.GREEN, activity::showVolume));
        addSpec(new ZappSpec("trinity", "Trinity",
                "Link phone & computer",
                R.drawable.ic_zoe_trinity, Ui.COBALT, () -> open(TrinityActivity.class)));
        addSpec(new ZappSpec("kit", "Field kit",
                "Cameras, GPS & sensor tools",
                R.drawable.ic_zoe_kit, Ui.CYAN, () -> open(FieldKitActivity.class)));
        addSpec(new ZappSpec("device", "Device field",
                "Battery & speaker check",
                R.drawable.ic_zoe_device, Ui.GREEN, activity::showDevice));
        addSpec(new ZappSpec("safeconvert", "SafeConvert",
                "Units & private safety helper",
                R.drawable.ic_zoe_convert, Ui.RUBY, () -> open(SafeConvertActivity.class)));
        addSpec(new ZappSpec("guide", "Researcher guide",
                "How Zoe works & limits",
                R.drawable.ic_zoe_guide, Ui.GOLD, () -> open(ResearchActivity.class)));
    }

    private void addSpec(ZappSpec spec) {
        zappMap.put(spec.id, spec);
    }

    private Button modeTogglePill(String label, OnClickListener listener) {
        Button b = new Button(getContext());
        b.setText(label);
        b.setTextSize(14.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMinHeight(Ui.dp(getContext(), 44));
        b.setMinimumHeight(Ui.dp(getContext(), 44));
        b.setPadding(Ui.dp(getContext(), 20), 0, Ui.dp(getContext(), 20), 0);
        b.setStateListAnimator(null);
        b.setOnClickListener(listener);
        return b;
    }

    private void styleModePills() {
        Context ctx = getContext();
        int activeFill = Ui.panelColor(ctx);
        int activeBorder = Ui.dividerColor(ctx);
        int ink = Ui.textColor(ctx);
        int muted = Ui.mutedColor(ctx);

        if (arrangeMode) {
            explorePill.setTextColor(muted);
            explorePill.setBackground(Ui.tonalPillDrawable(ctx, Color.TRANSPARENT, Ui.primaryAccent(ctx), 22));
            arrangeButton.setText("Done");
            arrangeButton.setContentDescription("Done arranging Zapps");
            arrangeButton.setTextColor(ink);
            arrangeButton.setBackground(Ui.outlinedPillDrawable(ctx, activeFill, activeBorder, Ui.primaryAccent(ctx), 22));
            resetButton.setVisibility(VISIBLE);
            zappsHint.setVisibility(VISIBLE);
        } else {
            explorePill.setTextColor(ink);
            explorePill.setBackground(Ui.outlinedPillDrawable(ctx, activeFill, activeBorder, Ui.primaryAccent(ctx), 22));
            arrangeButton.setText("Arrange");
            arrangeButton.setContentDescription("Arrange Zapps");
            arrangeButton.setTextColor(muted);
            arrangeButton.setBackground(Ui.tonalPillDrawable(ctx, Color.TRANSPARENT, Ui.primaryAccent(ctx), 22));
            resetButton.setVisibility(GONE);
            zappsHint.setVisibility(GONE);
        }
    }

    void toggleArrangeMode() {
        arrangeMode = !arrangeMode;
        styleModePills();
        renderZapps();
    }

    void refreshDynamic() {
        savedSightingsCount = TripJournalStore.load(getContext()).size();
        String net = Ui.networkStatusLabel(getContext());
        modePillLabel.setText("Offline".equals(net) ? "beta · offline" : "beta");
        renderZapps();
    }

    private void renderZapps() {
        primaryContainer.removeAllViews();
        moreContainer.removeAllViews();
        List<String> order = ZappLayoutStore.loadOrder(getContext());
        List<ZappSpec> orderedSpecs = new ArrayList<>();
        for (String id : order) {
            ZappSpec spec = zappMap.get(id);
            if (spec != null) {
                orderedSpecs.add(spec);
            }
        }

        if (arrangeMode) {
            for (int i = 0; i < orderedSpecs.size(); i++) {
                View row = buildArrangeRow(orderedSpecs.get(i), i, orderedSpecs.size(), order);
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                        ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
                lp.setMargins(0, Ui.dp(getContext(), 4), 0, Ui.dp(getContext(), 4));
                primaryContainer.addView(row, lp);
            }
            return;
        }

        // Focused Top 3 Ergonomic Hero Cards (72dp tall, generous spacing — effortless for children & adults!)
        int primaryCount = Math.min(3, orderedSpecs.size());
        for (int i = 0; i < primaryCount; i++) {
            ZappSpec spec = orderedSpecs.get(i);
            String helper = "journal".equals(spec.id) && savedSightingsCount > 0
                    ? savedSightingsCount + " saved notes"
                    : spec.simpleHelper;
            LinearLayout card = buildHeroActionCard(spec, helper);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            lp.setMargins(0, Ui.dp(getContext(), 5), 0, Ui.dp(getContext(), 5));
            primaryContainer.addView(card, lp);
        }

        // Remaining Zapps inside ONE calm grouped Material 3 container below the fold
        if (orderedSpecs.size() > primaryCount) {
            TextView moreLabel = Ui.section(getContext(), "More Zapps");
            moreLabel.setPadding(Ui.dp(getContext(), 24), Ui.dp(getContext(), 8),
                    Ui.dp(getContext(), 20), Ui.dp(getContext(), 8));
            moreContainer.addView(moreLabel);

            LinearLayout groupCard = Ui.groupedCard(getContext());
            for (int i = primaryCount; i < orderedSpecs.size(); i++) {
                if (i > primaryCount) {
                    groupCard.addView(Ui.insetDivider(getContext()));
                }
                ZappSpec spec = orderedSpecs.get(i);
                String helper = "journal".equals(spec.id) && savedSightingsCount > 0
                        ? savedSightingsCount + " saved notes"
                        : spec.simpleHelper;
                LinearLayout row = Ui.groupedRow(getContext(), spec.title, helper, spec.iconRes, spec.accent, v -> {
                    performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
                    spec.action.run();
                });
                row.setOnLongClickListener(v -> {
                    performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
                    showQuickMoveDialog(spec);
                    return true;
                });
                groupCard.addView(row);
            }
            LinearLayout.LayoutParams gp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            gp.setMargins(Ui.dp(getContext(), 16), 0, Ui.dp(getContext(), 16), 0);
            moreContainer.addView(groupCard, gp);
        }
    }

    /** Large 72dp soft tonal card for the Top 3 pinned Zapps (clear single-glance target). */
    private LinearLayout buildHeroActionCard(ZappSpec spec, String helper) {
        Context ctx = getContext();
        LinearLayout row = Ui.groupedRow(ctx, spec.title, helper, spec.iconRes, spec.accent, v -> {
            performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
            spec.action.run();
        });
        row.setMinimumHeight(Ui.dp(ctx, 74));
        row.setPadding(Ui.dp(ctx, 18), Ui.dp(ctx, 14), Ui.dp(ctx, 18), Ui.dp(ctx, 14));
        boolean dark = Ui.isDark(ctx);
        int fill = dark ? Color.argb(215, 28, 30, 36) : Color.rgb(242, 245, 250);
        int stroke = dark ? Color.argb(95, 76, 86, 112) : Color.argb(140, 214, 222, 235);
        row.setBackground(Ui.outlinedPillDrawable(ctx, fill, stroke, spec.accent, 24));
        row.setOnLongClickListener(v -> {
            performHapticFeedback(HapticFeedbackConstants.LONG_PRESS);
            showQuickMoveDialog(spec);
            return true;
        });
        return row;
    }

    private View buildArrangeRow(ZappSpec spec, int index, int total, List<String> order) {
        LinearLayout row = new LinearLayout(getContext());
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setMinimumHeight(Ui.dp(getContext(), 62));
        row.setBackground(Ui.cardBackground(getContext(), 22));
        row.setPadding(Ui.dp(getContext(), 14), Ui.dp(getContext(), 8),
                Ui.dp(getContext(), 10), Ui.dp(getContext(), 8));

        row.addView(Ui.iconCircle(getContext(), spec.iconRes, spec.accent, 38));

        TextView titleView = Ui.text(getContext(), spec.title, 16f, Ui.TEXT);
        titleView.setTypeface(Ui.SANS_MEDIUM);
        titleView.setPadding(Ui.dp(getContext(), 12), 0, Ui.dp(getContext(), 6), 0);
        titleView.setMaxLines(1);
        titleView.setEllipsize(TextUtils.TruncateAt.END);
        row.addView(titleView, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));

        row.addView(moveChip("★", "Pin " + spec.title + " to top", index > 0, () -> {
            ZappLayoutStore.saveOrder(getContext(), ZappLayoutStore.moveToTop(order, spec.id));
            renderZapps();
        }));
        row.addView(moveChip("↑", "Move " + spec.title + " up", index > 0, () -> {
            ZappLayoutStore.saveOrder(getContext(), ZappLayoutStore.moveUp(order, spec.id));
            renderZapps();
        }));
        row.addView(moveChip("↓", "Move " + spec.title + " down", index < total - 1, () -> {
            ZappLayoutStore.saveOrder(getContext(), ZappLayoutStore.moveDown(order, spec.id));
            renderZapps();
        }));
        return row;
    }

    private Button moveChip(String label, String desc, boolean enabled, Runnable onMove) {
        Button b = Ui.tonalIconButton(getContext(), label, desc, view -> {
            performHapticFeedback(HapticFeedbackConstants.CLOCK_TICK);
            onMove.run();
        });
        b.setTextSize(15f);
        b.setEnabled(enabled);
        b.setAlpha(enabled ? 1.0f : 0.28f);
        b.setBackground(Ui.tonalPillDrawable(getContext(), Ui.tonalWellColor(getContext()), Ui.primaryAccent(getContext()), 99));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                Ui.dp(getContext(), 48), Ui.dp(getContext(), 48));
        p.setMargins(Ui.dp(getContext(), 4), 0, 0, 0);
        b.setLayoutParams(p);
        return b;
    }

    /** Clean big-button Quick Menu Sheet (opened from Top '=' or Bottom '+' capsule). */
    void showQuickSheet() {
        Context ctx = getContext();
        LinearLayout box = new LinearLayout(ctx);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setBackground(Ui.cardBackground(ctx, 28));
        box.setPadding(Ui.dp(ctx, 18), Ui.dp(ctx, 20), Ui.dp(ctx, 18), Ui.dp(ctx, 18));

        TextView heading = Ui.text(ctx, "Quick actions", 20f, Ui.TEXT);
        heading.setTypeface(Ui.SANS_MEDIUM);
        heading.setPadding(Ui.dp(ctx, 10), 0, Ui.dp(ctx, 10), Ui.dp(ctx, 10));
        ViewCompat.setAccessibilityHeading(heading, true);
        box.addView(heading);

        final AlertDialog dialog = new AlertDialog.Builder(ctx).setView(box).create();

        box.addView(Ui.geminiActionRow(ctx, "Maps & Safety", "Live GPS, Google Maps & Safety app",
                R.drawable.ic_zoe_location, Ui.CYAN, v -> {
                    dialog.dismiss();
                    open(LocationActivity.class);
                }));
        box.addView(Ui.geminiActionRow(ctx, "SafeConvert", "Units & private safety helper",
                R.drawable.ic_zoe_convert, Ui.RUBY, v -> {
                    dialog.dismiss();
                    open(SafeConvertActivity.class);
                }));
        box.addView(Ui.geminiActionRow(ctx, "Field kit", "Cameras, GPS & sensors",
                R.drawable.ic_zoe_kit, Ui.CYAN, v -> {
                    dialog.dismiss();
                    open(FieldKitActivity.class);
                }));
        box.addView(Ui.geminiActionRow(ctx, arrangeMode ? "Done arranging" : "Arrange Zapps",
                "Put your favorites at the top",
                R.drawable.ic_zoe_apps, Ui.GOLD, v -> {
                    dialog.dismiss();
                    toggleArrangeMode();
                }));
        box.addView(Ui.geminiActionRow(ctx, "Open Google Gemini", "Jump to Gemini when you choose",
                R.drawable.ic_zoe_gem, Ui.COBALT, v -> {
                    dialog.dismiss();
                    host.openGemini();
                }));
        boolean comfort = host.isComfortMode();
        box.addView(Ui.geminiActionRow(ctx,
                comfort ? "Comfort mode: On" : "Comfort mode: Off",
                "Slower voice & gentle motion",
                R.drawable.ic_zoe_talk, Ui.GREEN, v -> {
                    host.setComfortMode(!comfort);
                    dialog.dismiss();
                }));

        Button close = Ui.button(ctx, "Close", Ui.MUTED, v -> dialog.dismiss());
        LinearLayout.LayoutParams cp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cp.setMargins(Ui.dp(ctx, 6), Ui.dp(ctx, 12), Ui.dp(ctx, 6), 0);
        box.addView(close, cp);

        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }
    }

    private void showAboutSheet() {
        Context ctx = getContext();
        LinearLayout box = new LinearLayout(ctx);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setBackground(Ui.cardBackground(ctx, 28));
        box.setPadding(Ui.dp(ctx, 24), Ui.dp(ctx, 24), Ui.dp(ctx, 24), Ui.dp(ctx, 22));

        LinearLayout top = new LinearLayout(ctx);
        top.setOrientation(LinearLayout.HORIZONTAL);
        top.setGravity(Gravity.CENTER_VERTICAL);
        top.addView(Ui.zoeSparkIcon(ctx, 48));
        LinearLayout titleCol = new LinearLayout(ctx);
        titleCol.setOrientation(LinearLayout.VERTICAL);
        titleCol.setPadding(Ui.dp(ctx, 14), 0, 0, 0);
        TextView title = Ui.text(ctx, "Zoe (beta)", 22f, Ui.TEXT);
        title.setTypeface(Ui.SANS_MEDIUM);
        title.setPadding(0, 0, 0, 0);
        ViewCompat.setAccessibilityHeading(title, true);
        titleCol.addView(title);
        TextView ver = Ui.text(ctx, "v0.3.0-beta · Offline-first · Free", 13.5f, Ui.MUTED);
        ver.setPadding(0, 0, 0, 0);
        titleCol.addView(ver);
        top.addView(titleCol);
        box.addView(top);

        TextView oath = Ui.text(ctx,
                "Privacy and dignity by design. Nothing listens, watches, saves, or uploads until you tap.",
                15.5f, Ui.TEXT);
        oath.setPadding(0, Ui.dp(ctx, 16), 0, Ui.dp(ctx, 8));
        box.addView(oath);

        TextView credit = Ui.text(ctx,
                "Built for everyone — calm, clear, and accessible.\nAppearance: "
                        + Ui.themeLabel(ctx) + " · Saved notes: " + savedSightingsCount,
                13.5f, Ui.MUTED);
        credit.setPadding(0, 0, 0, Ui.dp(ctx, 16));
        box.addView(credit);

        final AlertDialog dialog = new AlertDialog.Builder(ctx).setView(box).create();
        Button ok = Ui.primaryButton(ctx, "Done", Ui.COBALT, v -> dialog.dismiss());
        box.addView(ok);
        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }
    }

    private void showQuickMoveDialog(ZappSpec spec) {
        List<String> current = ZappLayoutStore.loadOrder(getContext());
        String[] options = new String[]{
                "Pin to top (#1)",
                "Move up",
                "Move down",
                "Open Arrange mode"
        };
        new AlertDialog.Builder(getContext())
                .setTitle("Arrange: " + spec.title)
                .setItems(options, (dialog, which) -> {
                    switch (which) {
                        case 0 -> {
                            ZappLayoutStore.saveOrder(getContext(), ZappLayoutStore.moveToTop(current, spec.id));
                            renderZapps();
                        }
                        case 1 -> {
                            ZappLayoutStore.saveOrder(getContext(), ZappLayoutStore.moveUp(current, spec.id));
                            renderZapps();
                        }
                        case 2 -> {
                            ZappLayoutStore.saveOrder(getContext(), ZappLayoutStore.moveDown(current, spec.id));
                            renderZapps();
                        }
                        default -> {
                            if (!arrangeMode) {
                                toggleArrangeMode();
                            }
                        }
                    }
                })
                .show();
    }

    private void returnToHomeTop() {
        if (arrangeMode) {
            toggleArrangeMode();
        }
        smoothScrollTo(0, 0);
    }

    private void open(Class<?> activityClass) {
        getContext().startActivity(new Intent(getContext(), activityClass));
    }
}
