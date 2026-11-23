package research.zoetic.zoe;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.core.content.FileProvider;
import androidx.core.view.ViewCompat;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Home Screen — Pure Gemini-Level Calm Minimalism:
 *   - Quiet borderless top bar (= menu · zoe ready • · theme toggle)
 *   - Vast breathing canvas with Zoe's original Red Smiling Gem centered over "hi, im zoe"
 *   - Zero redundant cards or ad-like boxes; Chat, Guided Vision & Zoe Explore live cleanly
 *     in the ergonomic bottom capsule under your thumb.
 */
final class HomeView extends ScrollView {
    private final MainActivity host;
    private final ExecutorService probeExecutor = Executors.newSingleThreadExecutor();
    private final ElizaGemClient studioClient = new ElizaGemClient();
    private final TextView modePillLabel;
    private final View statusDot;
    private volatile int savedSightingsCount;
    private volatile int learnedObjectsCount;

    HomeView(MainActivity activity) {
        super(activity);
        this.host = activity;
        setFillViewport(true);
        setBackgroundColor(Color.TRANSPARENT);

        LinearLayout content = Ui.vertical(activity);
        content.setBackgroundColor(Color.TRANSPARENT);
        content.setPadding(0, Ui.dp(activity, 4), 0, Ui.dp(activity, 16));
        addView(content);

        // 1. Quiet Borderless Top Bar (= menu · zoe ready • · theme toggle)
        LinearLayout topBar = new LinearLayout(activity);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setBackgroundColor(Color.TRANSPARENT);
        topBar.setPadding(Ui.dp(activity, 12), Ui.dp(activity, 6), Ui.dp(activity, 12), Ui.dp(activity, 2));

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

        TextView brandTitle = Ui.text(activity, "zoe", 20f, Ui.TEXT);
        brandTitle.setTypeface(Ui.SANS_REGULAR);
        brandTitle.setPadding(0, 0, Ui.dp(activity, 6), 0);
        ViewCompat.setAccessibilityHeading(brandTitle, true);
        brandTap.addView(brandTitle);

        modePillLabel = Ui.text(activity, "ready", 14f, Ui.MUTED);
        modePillLabel.setPadding(0, 0, Ui.dp(activity, 6), 0);
        brandTap.addView(modePillLabel);

        statusDot = new View(activity);
        GradientDrawable dotBg = new GradientDrawable();
        dotBg.setShape(GradientDrawable.OVAL);
        dotBg.setColor(Ui.primaryAccent(activity));
        statusDot.setBackground(dotBg);
        statusDot.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
        LinearLayout.LayoutParams dotParams = new LinearLayout.LayoutParams(Ui.dp(activity, 7), Ui.dp(activity, 7));
        dotParams.setMargins(0, 0, 0, Ui.dp(activity, 6));
        brandTap.addView(statusDot, dotParams);
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
        content.addView(topBar);

        // 2. Vast Serene Centerpiece: Original Crown-Smile Red Gem + "hi, im zoe"
        LinearLayout hero = new LinearLayout(activity);
        hero.setOrientation(LinearLayout.VERTICAL);
        hero.setGravity(Gravity.CENTER);
        hero.setBackgroundColor(Color.TRANSPARENT);
        hero.setPadding(Ui.dp(activity, 24), 0, Ui.dp(activity, 24), Ui.dp(activity, 40));

        ImageView heroGem = Ui.zoeSparkIcon(activity, 94);
        heroGem.setClickable(true);
        heroGem.setFocusable(true);
        heroGem.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
        heroGem.setContentDescription("Zoe");
        Ui.attachPressSpring(heroGem);
        heroGem.setOnClickListener(Ui.withHaptic(v -> open(ConversationActivity.class)));
        LinearLayout.LayoutParams gemLp = new LinearLayout.LayoutParams(Ui.dp(activity, 98), Ui.dp(activity, 98));
        gemLp.setMargins(0, 0, 0, Ui.dp(activity, 18));
        hero.addView(heroGem, gemLp);

        TextView greeting = Ui.text(activity, "hi, i'm zoe", 34f, Ui.TEXT);
        greeting.setGravity(Gravity.CENTER);
        greeting.setTypeface(Ui.SANS_MEDIUM);
        greeting.setLetterSpacing(-0.025f);
        greeting.setPadding(0, 0, 0, 0);
        greeting.setContentDescription("Hi, I'm Zoe");
        Ui.applyGeminiGreetingShader(greeting);
        hero.addView(greeting);

        content.addView(hero, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1.0f));

        refreshDynamic();
    }

    private void shareKnowledgeSeed() {
        Context ctx = getContext();
        Context appCtx = ctx.getApplicationContext();
        probeExecutor.execute(() -> {
            try {
                ZoeBrainEngine brain = new ZoeBrainEngine(appCtx);
                MobileDigestionBundle.Summary summary = MobileDigestionBundle.collect(appCtx, brain);
                MobileDigestionBundle.assertOutgoingFirewall(summary.bundleJson);
                File dir = new File(appCtx.getCacheDir(), "zoe_learn");
                if (!dir.exists()) dir.mkdirs();
                File out = new File(dir, "zoe-knowledge-seed.json");
                try (FileOutputStream fos = new FileOutputStream(out)) {
                    fos.write(summary.bundleJson.getBytes(StandardCharsets.UTF_8));
                }
                Uri uri = FileProvider.getUriForFile(appCtx, appCtx.getPackageName() + ".fileprovider", out);
                post(() -> {
                    Intent share = new Intent(Intent.ACTION_SEND)
                            .setType("application/json")
                            .putExtra(Intent.EXTRA_STREAM, uri)
                            .putExtra(Intent.EXTRA_SUBJECT, "Zoe Knowledge Seed")
                            .putExtra(Intent.EXTRA_TEXT, "Privacy-firewalled Zoe Knowledge Seed ("
                                    + summary.visionPrototypesCount + " prototypes, "
                                    + summary.brainNotesCount + " notes)")
                            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                    ctx.startActivity(Intent.createChooser(share, "Share Knowledge Seed"));
                });
            } catch (Exception ignored) {
            }
        });
    }

    /** Zero main-thread disk I/O: refreshes telemetry counts and Workstation badge asynchronously. */
    void refreshDynamic() {
        String net = Ui.networkStatusLabel(getContext());
        modePillLabel.setText("Offline".equals(net) ? "offline" : "ready");
        setStatusDotColor(Ui.primaryAccent(getContext()));
        Context appCtx = getContext().getApplicationContext();
        String endpoint = ElizaGemClient.savedEndpoint(appCtx);
        probeExecutor.execute(() -> {
            savedSightingsCount = TripJournalStore.load(appCtx).size();
            learnedObjectsCount = VisionPriorStore.loadAll(appCtx).size();
            try {
                ElizaGemClient.Status st = studioClient.fetchStatusQuick(endpoint);
                post(() -> {
                    if (host.isFinishing() || host.isDestroyed()) return;
                    if (st.frontierReady) {
                        modePillLabel.setText("pro · linked");
                        setStatusDotColor(Ui.resolveColor(getContext(), Ui.GREEN));
                    } else {
                        modePillLabel.setText("lab · linked");
                        setStatusDotColor(Ui.resolveColor(getContext(), Ui.CYAN));
                    }
                });
            } catch (Exception ignored) {
            }
        });
    }

    private void setStatusDotColor(int color) {
        GradientDrawable bg = new GradientDrawable();
        bg.setShape(GradientDrawable.OVAL);
        bg.setColor(color);
        statusDot.setBackground(bg);
    }

    /** Clean Quick Menu Sheet (opened from Top '=' or Bottom '+' capsule). */
    void showQuickSheet() {
        Context ctx = getContext();
        ScrollView sheetScroll = new ScrollView(ctx);
        sheetScroll.setBackgroundColor(Color.TRANSPARENT);
        LinearLayout box = new LinearLayout(ctx);
        box.setOrientation(LinearLayout.VERTICAL);
        box.setBackground(Ui.cardBackground(ctx, 28));
        box.setPadding(Ui.dp(ctx, 18), Ui.dp(ctx, 20), Ui.dp(ctx, 18), Ui.dp(ctx, 18));
        sheetScroll.addView(box);

        TextView heading = Ui.text(ctx, "zoe", 20f, Ui.TEXT);
        heading.setTypeface(Ui.SANS_MEDIUM);
        heading.setPadding(Ui.dp(ctx, 10), 0, Ui.dp(ctx, 10), Ui.dp(ctx, 8));
        ViewCompat.setAccessibilityHeading(heading, true);
        box.addView(heading);

        final AlertDialog dialog = new AlertDialog.Builder(ctx).setView(sheetScroll).create();

        box.addView(Ui.geminiActionRow(ctx, "chat", "talk, question & teach zoe",
                R.drawable.ic_zoe_talk, Ui.RUBY, v -> {
                    dialog.dismiss();
                    open(ConversationActivity.class);
                }));
        box.addView(Ui.geminiActionRow(ctx, "guided vision", "show zoe photos, videos & camera",
                R.drawable.ic_zoe_vision, Ui.COBALT, v -> {
                    dialog.dismiss();
                    host.showVision();
                }));
        box.addView(Ui.geminiActionRow(ctx, "zoe explore", "live camera, voice & ar sight",
                R.drawable.ic_zoe_live, Ui.CYAN, v -> {
                    dialog.dismiss();
                    host.openLiveExplore();
                }));
        box.addView(Ui.geminiActionRow(ctx, "share knowledge seed", "export learned contours & notes",
                R.drawable.ic_zoe_gem, Ui.GREEN, v -> {
                    dialog.dismiss();
                    shareKnowledgeSeed();
                }));
        boolean comfort = host.isComfortMode();
        box.addView(Ui.geminiActionRow(ctx,
                comfort ? "comfort mode: on" : "comfort mode: off",
                "slower voice & gentle motion",
                R.drawable.ic_zoe_talk, Ui.GOLD, v -> {
                    host.setComfortMode(!comfort);
                    dialog.dismiss();
                }));

        Button close = Ui.button(ctx, "close", Ui.MUTED, v -> dialog.dismiss());
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
        top.addView(Ui.zoeSparkIcon(ctx, 50));
        LinearLayout titleCol = new LinearLayout(ctx);
        titleCol.setOrientation(LinearLayout.VERTICAL);
        titleCol.setPadding(Ui.dp(ctx, 14), 0, 0, 0);
        TextView title = Ui.text(ctx, "zoe", 22f, Ui.TEXT);
        title.setTypeface(Ui.SANS_MEDIUM);
        title.setPadding(0, 0, 0, 0);
        ViewCompat.setAccessibilityHeading(title, true);
        titleCol.addView(title);
        TextView ver = Ui.text(ctx, "v0.9.6 · collaborative open research", 13.5f, Ui.MUTED);
        ver.setPadding(0, 0, 0, 0);
        titleCol.addView(ver);
        top.addView(titleCol);
        box.addView(top);

        TextView oath = Ui.text(ctx,
                "privacy and dignity by design. nothing listens, watches, saves, or uploads until you choose",
                15.5f, Ui.TEXT);
        oath.setPadding(0, Ui.dp(ctx, 16), 0, Ui.dp(ctx, 8));
        box.addView(oath);

        TextView credit = Ui.text(ctx,
                "created by nicholas michael kloster · theme: "
                        + Ui.themeLabel(ctx).toLowerCase(java.util.Locale.US) + " · learned objects: " + learnedObjectsCount
                        + "\nsaved sightings: " + savedSightingsCount
                        + " · sentience_claimed=false",
                13f, Ui.MUTED);
        credit.setPadding(0, 0, 0, Ui.dp(ctx, 16));
        box.addView(credit);

        final AlertDialog dialog = new AlertDialog.Builder(ctx).setView(box).create();
        Button ok = Ui.primaryButton(ctx, "done", Ui.COBALT, v -> dialog.dismiss());
        box.addView(ok);
        dialog.show();
        if (dialog.getWindow() != null) {
            dialog.getWindow().setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
        }
    }

    private void open(Class<?> activityClass) {
        getContext().startActivity(new Intent(getContext(), activityClass));
        if (!host.isComfortMode()) {
            host.overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }
}
