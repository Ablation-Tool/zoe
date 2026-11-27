package research.zoetic.zoe;

import android.app.AlertDialog;
import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Outline;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.view.Gravity;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.ViewGroup;
import android.view.ViewOutlineProvider;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.core.content.FileProvider;
import androidx.core.view.ViewCompat;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Home Screen with Dorothy 3D Brain Observatory as the interactive Centerpiece:
 *   - Clean borderless top bar (= menu · zoe ready • · theme toggle)
 *   - Compact Zoe smiling red gem + "hi, i'm zoe" greeting
 *   - Hero Dorothy 3D Brain Centerpiece card (real MNI152 cortex preview + 1-tap Explore 3D Brain,
 *     Ask Zoe: Brain, and Videos & Gallery)
 *   - Quick Neuroscience Q&A prompt chips powered by Zoe's offline Dorothy Neuro-Atlas
 *   - Bottom ergonomic capsule (+ | ask zoe | Guided Vision | Zoe Explore)
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
        int swDp = activity.getResources().getConfiguration().screenWidthDp;
        int sidePadDp = swDp >= 720 ? Math.min(96, (swDp - 680) / 2) : (swDp >= 600 ? 24 : 0);
        content.setPadding(Ui.dp(activity, sidePadDp), Ui.dp(activity, 4), Ui.dp(activity, sidePadDp), Ui.dp(activity, 16));
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

        TextView brandTitle = Ui.text(activity, "Zoe", 20f, Ui.TEXT);
        brandTitle.setTypeface(Ui.SANS_REGULAR);
        brandTitle.setPadding(0, 0, Ui.dp(activity, 6), 0);
        ViewCompat.setAccessibilityHeading(brandTitle, true);
        brandTap.addView(brandTitle);

        modePillLabel = Ui.text(activity, "Ready", 14f, Ui.MUTED);
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

        // 2. Compact Zoe Greeting Header
        LinearLayout greetRow = new LinearLayout(activity);
        greetRow.setOrientation(LinearLayout.HORIZONTAL);
        greetRow.setGravity(Gravity.CENTER_VERTICAL);
        greetRow.setPadding(Ui.dp(activity, 20), Ui.dp(activity, 8), Ui.dp(activity, 20), Ui.dp(activity, 10));

        ImageView heroGem = Ui.zoeSparkIcon(activity, 44);
        heroGem.setClickable(true);
        heroGem.setFocusable(true);
        heroGem.setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_YES);
        heroGem.setContentDescription("Zoe");
        Ui.attachPressSpring(heroGem);
        heroGem.setOnClickListener(Ui.withHaptic(v -> open(ConversationActivity.class)));
        LinearLayout.LayoutParams gemLp = new LinearLayout.LayoutParams(Ui.dp(activity, 46), Ui.dp(activity, 46));
        gemLp.setMargins(0, 0, Ui.dp(activity, 12), 0);
        greetRow.addView(heroGem, gemLp);

        LinearLayout greetCol = Ui.vertical(activity);
        greetCol.setBackgroundColor(Color.TRANSPARENT);
        TextView greeting = Ui.text(activity, "Hi, I'm Zoe", 26f, Ui.TEXT);
        greeting.setTypeface(Ui.SANS_MEDIUM);
        greeting.setLetterSpacing(-0.02f);
        greeting.setPadding(0, 0, 0, 0);
        greeting.setContentDescription("Hi, I'm Zoe");
        Ui.applyGeminiGreetingShader(greeting);
        greetCol.addView(greeting);
        greetRow.addView(greetCol, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f));
        content.addView(greetRow);

        // 3. CENTERPIECE: Dorothy 3D Brain Observatory Hero Card
        LinearLayout brainCard = buildDorothyCenterpieceCard(activity);
        LinearLayout.LayoutParams cardLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        cardLp.setMargins(Ui.dp(activity, 16), Ui.dp(activity, 2), Ui.dp(activity, 16), Ui.dp(activity, 12));
        content.addView(brainCard, cardLp);

        // 4. Stacked 2-Column Neuroscience Quick Topics ("Ask Zoe about the brain")
        TextView askHdr = Ui.text(activity, "Ask Zoe about the brain", 13.5f, Ui.MUTED);
        askHdr.setTypeface(Ui.SANS_MEDIUM);
        askHdr.setPadding(Ui.dp(activity, 22), Ui.dp(activity, 4), Ui.dp(activity, 22), Ui.dp(activity, 8));
        content.addView(askHdr);

        String[][] brainPrompts = {
                {"Broca's Area (BA 44)", "What does Broca's Area (BA 44) do?"},
                {"Hippocampus & Memory", "Where is the Hippocampus and what is its role?"},
                {"Cranial Nerve X (Vagus)", "Explain Cranial Nerve X (Vagus)"},
                {"Language Loop Circuit", "Explain the Language Loop neural circuit"},
                {"Circle of Willis & MCA", "What is the Circle of Willis and MCA territory?"},
                {"10-20 EEG Brain Waves", "How do 10-20 EEG brain waves work?"}
        };
        int chipFill = dark ? Color.rgb(20, 29, 46) : Color.rgb(238, 244, 252);
        int chipStroke = dark ? Color.argb(120, 56, 189, 248) : Color.argb(140, 26, 115, 232);
        LinearLayout stackBox = Ui.vertical(activity);
        stackBox.setBackgroundColor(Color.TRANSPARENT);
        stackBox.setPadding(Ui.dp(activity, 16), 0, Ui.dp(activity, 16), Ui.dp(activity, 6));
        for (int i = 0; i < brainPrompts.length; i += 2) {
            LinearLayout row = new LinearLayout(activity);
            row.setOrientation(LinearLayout.HORIZONTAL);
            LinearLayout.LayoutParams rowLp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            rowLp.setMargins(0, 0, 0, Ui.dp(activity, 8));
            for (int col = 0; col < 2 && (i + col) < brainPrompts.length; col++) {
                String[] pair = brainPrompts[i + col];
                Button chip = new Button(activity);
                chip.setText(pair[0]);
                chip.setTextSize(13f);
                chip.setTypeface(Ui.SANS_MEDIUM);
                chip.setAllCaps(false);
                chip.setSingleLine(true);
                chip.setEllipsize(android.text.TextUtils.TruncateAt.END);
                chip.setMinHeight(Ui.dp(activity, 46));
                chip.setMinimumHeight(Ui.dp(activity, 46));
                chip.setPadding(Ui.dp(activity, 12), 0, Ui.dp(activity, 12), 0);
                chip.setTextColor(Ui.textColor(activity));
                chip.setBackground(Ui.outlinedPillDrawable(activity, chipFill, chipStroke, Ui.primaryAccent(activity), 18));
                chip.setStateListAnimator(null);
                Ui.attachPressSpring(chip);
                chip.setOnClickListener(Ui.withHaptic(v -> host.openChatWithPrompt(pair[1])));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
                lp.setMargins(col == 0 ? 0 : Ui.dp(activity, 4), 0, col == 0 ? Ui.dp(activity, 4) : 0, 0);
                row.addView(chip, lp);
            }
            stackBox.addView(row, rowLp);
        }
        content.addView(stackBox);

        refreshDynamic();
    }

    private LinearLayout buildDorothyCenterpieceCard(MainActivity activity) {
        LinearLayout card = Ui.vertical(activity);
        card.setId(R.id.home_dorothy_centerpiece);
        int cardBgColor = Color.rgb(11, 17, 29);
        GradientDrawable cardBg = new GradientDrawable();
        cardBg.setColor(cardBgColor);
        cardBg.setCornerRadius(Ui.dp(activity, 26));
        cardBg.setStroke(Ui.strokePx(activity, 1.1f), Color.argb(135, 245, 208, 120));
        card.setBackground(cardBg);
        card.setElevation(Ui.dp(activity, 8));
        card.setClipToOutline(true);
        card.setOutlineProvider(new ViewOutlineProvider() {
            @Override
            public void getOutline(View view, Outline outline) {
                outline.setRoundRect(0, 0, view.getWidth(), view.getHeight(), Ui.dp(activity, 26));
            }
        });

        // Hero Real 3D Brain Visual (loaded cleanly from bundled observatory preview asset)
        FrameLayout mediaFrame = new FrameLayout(activity);
        mediaFrame.setBackgroundColor(Color.rgb(7, 11, 18));
        mediaFrame.setClickable(true);
        mediaFrame.setFocusable(true);
        mediaFrame.setContentDescription("Open Dorothy 3D Brain Observatory");
        mediaFrame.setOnClickListener(Ui.withHaptic(v -> host.openBrainObservatory()));

        ImageView heroImg = new ImageView(activity);
        heroImg.setScaleType(ImageView.ScaleType.CENTER_CROP);
        Bitmap bmp = loadAssetBitmap(activity, "dorothy_brain_observatory/previews/hero_brain_card.jpg");
        if (bmp == null) {
            bmp = loadAssetBitmap(activity, "dorothy_brain_observatory/previews/01_hero_tissue.jpg");
        }
        if (bmp != null) {
            heroImg.setImageBitmap(bmp);
        } else {
            heroImg.setImageResource(R.drawable.zoe_emblem);
            heroImg.setScaleType(ImageView.ScaleType.FIT_CENTER);
        }
        int heroHeightDp = activity.getResources().getConfiguration().screenWidthDp >= 600 ? 256 : 210;
        mediaFrame.addView(heroImg, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(activity, heroHeightDp)));

        // Bottom dark scrim for crystal-clear gold typography over 3D render
        View scrim = new View(activity);
        GradientDrawable scrimBg = new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{Color.argb(0, 7, 11, 18), Color.argb(65, 7, 11, 18), Color.argb(242, 11, 17, 29)});
        scrim.setBackground(scrimBg);
        mediaFrame.addView(scrim, new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(activity, heroHeightDp)));

        // Bottom overlay title on hero visual
        LinearLayout heroText = Ui.vertical(activity);
        heroText.setBackgroundColor(Color.TRANSPARENT);
        heroText.setPadding(Ui.dp(activity, 16), 0, Ui.dp(activity, 16), Ui.dp(activity, 10));
        TextView heroTitle = Ui.text(activity, "Dorothy 3D Brain", 22f, Ui.TEXT);
        heroTitle.setTextColor(Color.rgb(245, 208, 120));
        heroTitle.setTypeface(Ui.SANS_BOLD);
        heroTitle.setPadding(0, 0, 0, 0);
        heroText.addView(heroTitle);

        FrameLayout.LayoutParams htLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM);
        mediaFrame.addView(heroText, htLp);
        card.addView(mediaFrame);

        // Action Controls inside Centerpiece Card
        LinearLayout actions = Ui.vertical(activity);
        actions.setBackgroundColor(cardBgColor);
        actions.setPadding(Ui.dp(activity, 14), Ui.dp(activity, 10), Ui.dp(activity, 14), Ui.dp(activity, 14));

        Button openBrainBtn = new Button(activity);
        openBrainBtn.setId(R.id.home_open_brain_btn);
        openBrainBtn.setText("Explore Dorothy 3D Brain");
        openBrainBtn.setAllCaps(false);
        openBrainBtn.setTextSize(15.5f);
        openBrainBtn.setTypeface(Ui.SANS_BOLD);
        openBrainBtn.setTextColor(Color.rgb(7, 11, 18));
        openBrainBtn.setMinHeight(Ui.dp(activity, 48));
        openBrainBtn.setMinimumHeight(Ui.dp(activity, 48));
        GradientDrawable goldBtnBg = new GradientDrawable(
                GradientDrawable.Orientation.LEFT_RIGHT,
                new int[]{Color.rgb(245, 208, 120), Color.rgb(251, 191, 36)});
        goldBtnBg.setCornerRadius(Ui.dp(activity, 24));
        openBrainBtn.setBackground(goldBtnBg);
        openBrainBtn.setStateListAnimator(null);
        Ui.attachPressSpring(openBrainBtn);
        openBrainBtn.setOnClickListener(Ui.withHaptic(v -> host.openBrainObservatory()));
        actions.addView(openBrainBtn, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));

        LinearLayout subRow = new LinearLayout(activity);
        subRow.setOrientation(LinearLayout.HORIZONTAL);
        LinearLayout.LayoutParams subRowLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        subRowLp.setMargins(0, Ui.dp(activity, 8), 0, 0);

        Button askBrainBtn = darkCardButton(activity, "Ask Zoe: Brain", Color.rgb(56, 189, 248),
                v -> host.openBrainObservatory("askzoe", ""));
        askBrainBtn.setId(R.id.home_ask_brain_btn);
        LinearLayout.LayoutParams leftLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
        leftLp.setMargins(0, 0, Ui.dp(activity, 4), 0);
        subRow.addView(askBrainBtn, leftLp);

        Button mediaBtn = darkCardButton(activity, "Videos & Gallery", Color.rgb(52, 211, 153),
                v -> host.openBrainObservatory("media", ""));
        mediaBtn.setId(R.id.home_brain_media_btn);
        LinearLayout.LayoutParams rightLp = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1.0f);
        rightLp.setMargins(Ui.dp(activity, 4), 0, 0, 0);
        subRow.addView(mediaBtn, rightLp);

        actions.addView(subRow, subRowLp);
        card.addView(actions);
        return card;
    }

    private Button darkCardButton(Context ctx, String label, int accentColor, OnClickListener listener) {
        Button b = new Button(ctx);
        b.setText(label);
        b.setAllCaps(false);
        b.setTextSize(13.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setTextColor(accentColor);
        b.setMinHeight(Ui.dp(ctx, 44));
        b.setMinimumHeight(Ui.dp(ctx, 44));
        GradientDrawable bg = new GradientDrawable();
        bg.setColor(Color.rgb(20, 29, 46));
        bg.setCornerRadius(Ui.dp(ctx, 22));
        bg.setStroke(Ui.strokePx(ctx, 0.9f), Ui.withAlpha(accentColor, 140));
        b.setBackground(bg);
        b.setStateListAnimator(null);
        Ui.attachPressSpring(b);
        b.setOnClickListener(Ui.withHaptic(listener));
        return b;
    }

    private static Bitmap loadAssetBitmap(Context ctx, String assetPath) {
        try (InputStream in = ctx.getAssets().open(assetPath)) {
            return BitmapFactory.decodeStream(in);
        } catch (Exception ignored) {
            return null;
        }
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
        modePillLabel.setText("Offline".equals(net) ? "Offline" : "Ready");
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
                        modePillLabel.setText("Pro · Linked");
                        setStatusDotColor(Ui.resolveColor(getContext(), Ui.GREEN));
                    } else {
                        modePillLabel.setText("Lab · Linked");
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

        TextView heading = Ui.text(ctx, "Zoe", 20f, Ui.TEXT);
        heading.setTypeface(Ui.SANS_MEDIUM);
        heading.setPadding(Ui.dp(ctx, 10), 0, Ui.dp(ctx, 10), Ui.dp(ctx, 8));
        ViewCompat.setAccessibilityHeading(heading, true);
        box.addView(heading);

        final AlertDialog dialog = new AlertDialog.Builder(ctx).setView(sheetScroll).create();

        box.addView(Ui.geminiActionRow(ctx, "Dorothy 3D Brain", "Interactive MNI152 3D Brain, Circuits, EEG & Videos",
                R.drawable.ic_zoe_gem, Ui.GOLD, v -> {
                    dialog.dismiss();
                    host.openBrainObservatory();
                }));
        box.addView(Ui.geminiActionRow(ctx, "Ask Zoe: Neuroscience", "Offline Brain Q&A Linked to 3D Fly-To",
                R.drawable.ic_zoe_talk, Ui.CYAN, v -> {
                    dialog.dismiss();
                    host.openBrainObservatory("askzoe", "");
                }));
        box.addView(Ui.geminiActionRow(ctx, "Brain Videos & Gallery", "Walkthrough Videos, HD Captures & 25 Plates",
                R.drawable.ic_zoe_vision, Ui.GREEN, v -> {
                    dialog.dismiss();
                    host.openBrainObservatory("media", "");
                }));
        box.addView(Ui.geminiActionRow(ctx, "Chat", "Talk, Question & Research with Zoe",
                R.drawable.ic_zoe_talk, Ui.RUBY, v -> {
                    dialog.dismiss();
                    open(ConversationActivity.class);
                }));
        box.addView(Ui.geminiActionRow(ctx, "Guided Vision", "Show Zoe Photos, Videos & Camera",
                R.drawable.ic_zoe_vision, Ui.COBALT, v -> {
                    dialog.dismiss();
                    host.showVision();
                }));
        box.addView(Ui.geminiActionRow(ctx, "Zoe Explore", "Live Camera, Voice & AR Sight",
                R.drawable.ic_zoe_live, Ui.CYAN, v -> {
                    dialog.dismiss();
                    host.openLiveExplore();
                }));
        box.addView(Ui.geminiActionRow(ctx, "Share Knowledge Seed", "Export Learned Contours & Notes",
                R.drawable.ic_zoe_gem, Ui.GREEN, v -> {
                    dialog.dismiss();
                    shareKnowledgeSeed();
                }));
        boolean comfort = host.isComfortMode();
        box.addView(Ui.geminiActionRow(ctx,
                comfort ? "Comfort Mode: On" : "Comfort Mode: Off",
                "Slower Voice & Gentle Motion",
                R.drawable.ic_zoe_talk, Ui.GOLD, v -> {
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
        top.addView(Ui.zoeSparkIcon(ctx, 50));
        LinearLayout titleCol = new LinearLayout(ctx);
        titleCol.setOrientation(LinearLayout.VERTICAL);
        titleCol.setPadding(Ui.dp(ctx, 14), 0, 0, 0);
        TextView title = Ui.text(ctx, "Zoe", 22f, Ui.TEXT);
        title.setTypeface(Ui.SANS_MEDIUM);
        title.setPadding(0, 0, 0, 0);
        ViewCompat.setAccessibilityHeading(title, true);
        titleCol.addView(title);
        TextView ver = Ui.text(ctx, "v0.9.6 · Dorothy 3D Brain Centerpiece", 13.5f, Ui.MUTED);
        ver.setPadding(0, 0, 0, 0);
        titleCol.addView(ver);
        top.addView(titleCol);
        box.addView(top);

        TextView oath = Ui.text(ctx,
                "Privacy and dignity by design. Nothing listens, watches, saves, or uploads until you choose.",
                15.5f, Ui.TEXT);
        oath.setPadding(0, Ui.dp(ctx, 16), 0, Ui.dp(ctx, 8));
        box.addView(oath);

        TextView credit = Ui.text(ctx,
                "Created with Nicholas Michael Kloster · Theme: "
                        + Ui.themeLabel(ctx) + " · Learned objects: " + learnedObjectsCount
                        + "\nSaved sightings: " + savedSightingsCount
                        + " · sentience_claimed=false",
                13f, Ui.MUTED);
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

    private void open(Class<?> activityClass) {
        getContext().startActivity(new Intent(getContext(), activityClass));
        if (!host.isComfortMode()) {
            host.overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }
}
