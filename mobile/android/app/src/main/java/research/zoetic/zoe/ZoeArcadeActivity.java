package research.zoetic.zoe;

import android.content.Intent;
import android.graphics.Color;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Arcade — Ad-Free Offline Games Built for Adults & Kids (v0.6.0-beta).
 *
 *   1. GEM Resonance Memory (4-petal harmonic musical Simon)
 *   2. Tic-Tac-Toe vs Zoe (Kid Mode & Unbeatable Minimax Grandmaster)
 *   3. Kloster A_tau(p) Signal Puzzle (strict threshold metacognition mini-game)
 *   4. 20 Questions & Interactive Story Adventure
 */
public final class ZoeArcadeActivity extends ComponentActivity {
    private final Random rng = new Random();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService audioExec = Executors.newSingleThreadExecutor();

    private TextView status;
    private Button[] tabBtns;
    private LinearLayout[] gamePanels;

    // 1. Memory state
    private final List<Integer> memorySeq = new ArrayList<>();
    private int memoryStep;
    private int memoryBest;
    private boolean memoryPlayingBack;
    private final Button[] petalBtns = new Button[4];
    private TextView memoryScoreView;

    // 2. Tic-Tac-Toe state
    private final int[] tttBoard = new int[9];
    private final Button[] tttCells = new Button[9];
    private boolean tttUnbeatable = true;
    private boolean tttOver;
    private int tttWins;
    private int tttDraws;
    private int tttZoeWins;
    private TextView tttScoreView;
    private Button tttModeBtn;

    // 3. Kloster Signal Puzzle state
    private ArcadeEngine.SignalPuzzle currentPuzzle;
    private double puzzleTau = 0.20;
    private int puzzleStreak;
    private SignalBarView puzzleBarsView;
    private TextView puzzlePromptView;
    private TextView puzzleTauLabel;

    // 4. 20 Questions state
    private ArcadeEngine.MysteryItem secretItem;
    private int questionsAsked;
    private TextView q20LogView;
    private EditText q20Input;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.TRANSPARENT);

        LinearLayout header = Ui.vertical(this);
        header.setBackgroundColor(Color.TRANSPARENT);
        header.setPadding(Ui.dp(this, 18), Ui.dp(this, 4), Ui.dp(this, 18), Ui.dp(this, 4));
        header.addView(Ui.topBar(this, "Zoe Arcade", null));

        // Clean 4-tab segmented pill bar — ALL 4 tabs fit edge-to-edge cleanly with ZERO clipping!
        LinearLayout tabRow = new LinearLayout(this);
        tabRow.setOrientation(LinearLayout.HORIZONTAL);
        tabRow.setBackground(Ui.cardBackground(this, 22));
        tabRow.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4));

        String[] names = {"Memory", "Tic-Tac-Toe", "Signal", "20Q"};
        int[] tabIds = {R.id.arcade_tab_memory, R.id.arcade_tab_ttt, R.id.arcade_tab_signal, R.id.arcade_tab_20q};
        tabBtns = new Button[4];
        for (int i = 0; i < 4; i++) {
            final int idx = i;
            Button b = pillChip(names[i], v -> selectGameTab(idx));
            b.setId(tabIds[i]);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 36), 1f);
            if (i < 3) {
                lp.setMargins(0, 0, Ui.dp(this, 4), 0);
            }
            tabRow.addView(b, lp);
            tabBtns[i] = b;
        }
        header.addView(tabRow);

        status = Ui.text(this, "Play offline with Zoe — zero ads, zero tracking.", 12.5f, Ui.MUTED);
        status.setId(R.id.arcade_status);
        status.setPadding(Ui.dp(this, 4), Ui.dp(this, 8), Ui.dp(this, 4), Ui.dp(this, 2));
        header.addView(status);
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout body = Ui.vertical(this);
        body.setPadding(Ui.dp(this, 18), Ui.dp(this, 8), Ui.dp(this, 18), Ui.dp(this, 32));

        gamePanels = new LinearLayout[]{
                buildMemoryPanel(),
                buildTicTacToePanel(),
                buildSignalPuzzlePanel(),
                buildTwentyQuestionsPanel()
        };
        for (LinearLayout panel : gamePanels) {
            body.addView(panel);
        }
        scroll.addView(body);
        root.addView(scroll, new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(Ui.wrapWithBackdrop(this, root));
        Ui.configureEdgeToEdge(this, root);
        selectGameTab(0);
    }

    private Button pillChip(String label, View.OnClickListener listener) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextSize(12.5f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setMaxLines(1);
        b.setPadding(Ui.dp(this, 6), 0, Ui.dp(this, 6), 0);
        b.setStateListAnimator(null);
        b.setOnClickListener(Ui.withHaptic(listener));
        return b;
    }

    private void selectGameTab(int index) {
        for (int i = 0; i < 4; i++) {
            boolean sel = i == index;
            gamePanels[i].setVisibility(sel ? View.VISIBLE : View.GONE);
            if (sel) {
                tabBtns[i].setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
                tabBtns[i].setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 18));
            } else {
                tabBtns[i].setTextColor(Ui.mutedColor(this));
                tabBtns[i].setBackground(Ui.tonalPillDrawable(this, Color.TRANSPARENT, Ui.primaryAccent(this), 18));
            }
        }
    }

    // --- 1. GEM Resonance Memory ---

    private LinearLayout buildMemoryPanel() {
        LinearLayout panel = Ui.vertical(this);
        memoryScoreView = Ui.text(this, "Round 0 · Best streak: 0", 15f, Ui.TEXT);
        memoryScoreView.setTypeface(Ui.SANS_MEDIUM);
        memoryScoreView.setPadding(Ui.dp(this, 4), 0, 0, Ui.dp(this, 10));
        panel.addView(memoryScoreView);

        int[] accents = {Ui.COBALT, Ui.GREEN, Ui.GOLD, Ui.RUBY};
        for (int row = 0; row < 2; row++) {
            LinearLayout r = new LinearLayout(this);
            r.setOrientation(LinearLayout.HORIZONTAL);
            for (int col = 0; col < 2; col++) {
                final int idx = row * 2 + col;
                int resolved = Ui.resolveColor(this, accents[idx]);
                Button b = new Button(this);
                b.setText(ArcadeEngine.PETAL_NAMES[idx]);
                b.setTextSize(16f);
                b.setTypeface(Ui.SANS_MEDIUM);
                b.setAllCaps(false);
                b.setTextColor(Ui.isDark(this) && idx == 2 ? Color.rgb(16, 18, 22) : Color.WHITE);
                b.setBackground(Ui.tonalPillDrawable(this, resolved, resolved, 26));
                b.setAlpha(0.80f);
                b.setStateListAnimator(null);
                b.setOnClickListener(Ui.withHaptic(v -> onPetalTapped(idx)));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 118), 1f);
                lp.setMargins(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
                r.addView(b, lp);
                petalBtns[idx] = b;
            }
            panel.addView(r);
        }

        Button startMem = Ui.primaryButton(this, "Start GEM Memory", Ui.COBALT, v -> startMemoryGame());
        startMem.setId(R.id.arcade_memory_start);
        LinearLayout.LayoutParams smLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        smLp.setMargins(0, Ui.dp(this, 12), 0, 0);
        panel.addView(startMem, smLp);
        return panel;
    }

    private void startMemoryGame() {
        memorySeq.clear();
        memoryStep = 0;
        advanceMemoryRound();
    }

    private void advanceMemoryRound() {
        List<Integer> next = ArcadeEngine.nextMemoryRound(memorySeq, rng);
        memorySeq.clear();
        memorySeq.addAll(next);
        memoryStep = 0;
        memoryScoreView.setText("Round " + memorySeq.size() + " · Best streak: " + memoryBest);
        status.setText("Watch and listen to Zoe's " + memorySeq.size() + "-note harmonic pattern…");
        memoryPlayingBack = true;
        for (int i = 0; i < memorySeq.size(); i++) {
            final int petal = memorySeq.get(i);
            final boolean last = i == memorySeq.size() - 1;
            handler.postDelayed(() -> {
                flashPetal(petal);
                playChime(ArcadeEngine.PETAL_FREQS_HZ[petal]);
                if (last) {
                    handler.postDelayed(() -> {
                        memoryPlayingBack = false;
                        status.setText("Your turn! Tap the " + memorySeq.size() + " petals in order.");
                    }, 360L);
                }
            }, (i + 1) * 520L);
        }
    }

    private void onPetalTapped(int idx) {
        if (memoryPlayingBack) {
            return;
        }
        flashPetal(idx);
        playChime(ArcadeEngine.PETAL_FREQS_HZ[idx]);
        if (memorySeq.isEmpty()) {
            status.setText("Nice note! Tap Start GEM Memory to play a pattern round.");
            return;
        }
        if (idx == memorySeq.get(memoryStep)) {
            memoryStep++;
            if (memoryStep >= memorySeq.size()) {
                memoryBest = Math.max(memoryBest, memorySeq.size());
                memoryScoreView.setText("Round " + memorySeq.size() + " cleared! · Best streak: " + memoryBest);
                status.setText("Awesome! Advancing to round " + (memorySeq.size() + 1) + "…");
                handler.postDelayed(this::advanceMemoryRound, 700L);
            }
        } else {
            status.setText("Oops — Zoe played " + ArcadeEngine.PETAL_NAMES[memorySeq.get(memoryStep)] + ". Tap Start to try again!");
            memorySeq.clear();
            memoryStep = 0;
        }
    }

    private void flashPetal(int idx) {
        Button b = petalBtns[idx];
        b.setAlpha(1.0f);
        b.setScaleX(1.05f);
        b.setScaleY(1.05f);
        handler.postDelayed(() -> {
            b.setAlpha(0.75f);
            b.setScaleX(1.0f);
            b.setScaleY(1.0f);
        }, 260L);
    }

    private void playChime(double freqHz) {
        audioExec.execute(() -> {
            try {
                short[] pcm = ArcadeEngine.synthesizeChimePcm(freqHz, 220);
                AudioTrack track = new AudioTrack.Builder()
                        .setAudioAttributes(new AudioAttributes.Builder()
                                .setUsage(AudioAttributes.USAGE_GAME)
                                .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                                .build())
                        .setAudioFormat(new AudioFormat.Builder()
                                .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                                .setSampleRate(44_100)
                                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                                .build())
                        .setBufferSizeInBytes(pcm.length * 2)
                        .setTransferMode(AudioTrack.MODE_STATIC)
                        .build();
                track.write(pcm, 0, pcm.length);
                track.play();
                Thread.sleep(240L);
                track.release();
            } catch (Exception ignored) {
            }
        });
    }

    // --- 2. Tic-Tac-Toe vs Zoe ---

    private LinearLayout buildTicTacToePanel() {
        LinearLayout panel = Ui.vertical(this);
        tttScoreView = Ui.text(this, "You (X): 0 · Draws: 0 · Zoe (O): 0", 15f, Ui.TEXT);
        tttScoreView.setTypeface(Ui.SANS_MEDIUM);
        tttScoreView.setPadding(Ui.dp(this, 4), 0, 0, Ui.dp(this, 10));
        panel.addView(tttScoreView);

        for (int r = 0; r < 3; r++) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            for (int c = 0; c < 3; c++) {
                final int idx = r * 3 + c;
                Button cell = new Button(this);
                cell.setText("");
                cell.setTextSize(28f);
                cell.setTypeface(Ui.SANS_MEDIUM);
                cell.setTextColor(Ui.textColor(this));
                cell.setBackground(Ui.cardBackground(this, 18));
                cell.setStateListAnimator(null);
                cell.setOnClickListener(Ui.withHaptic(v -> onTttCellTap(idx)));
                if (idx == 0) {
                    cell.setId(R.id.arcade_ttt_cell0);
                }
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 92), 1f);
                lp.setMargins(Ui.dp(this, 5), Ui.dp(this, 5), Ui.dp(this, 5), Ui.dp(this, 5));
                row.addView(cell, lp);
                tttCells[idx] = cell;
            }
            panel.addView(row);
        }

        tttModeBtn = Ui.button(this, "Mode: Unbeatable", Ui.GOLD, v -> {
            tttUnbeatable = !tttUnbeatable;
            tttModeBtn.setText(tttUnbeatable ? "Mode: Unbeatable" : "Mode: Kid Friendly");
            resetTicTacToe();
        });
        Button newBoard = Ui.primaryButton(this, "New Board", Ui.COBALT, v -> resetTicTacToe());
        LinearLayout tttActions = Ui.buttonRow(this, newBoard, tttModeBtn);
        tttActions.setPadding(0, Ui.dp(this, 10), 0, 0);
        panel.addView(tttActions);
        return panel;
    }

    private void onTttCellTap(int idx) {
        if (tttOver || tttBoard[idx] != 0) {
            return;
        }
        tttBoard[idx] = 1;
        renderTttBoard();
        if (checkTttEnd()) {
            return;
        }
        int zoeMove = ArcadeEngine.chooseZoeMove(tttBoard, tttUnbeatable, rng);
        if (zoeMove >= 0) {
            tttBoard[zoeMove] = 2;
            renderTttBoard();
            checkTttEnd();
        }
    }

    private boolean checkTttEnd() {
        int w = ArcadeEngine.checkWinner(tttBoard);
        if (w == 1) {
            tttOver = true;
            tttWins++;
            status.setText("You win Tic-Tac-Toe! Awesome move!");
            updateTttScore();
            return true;
        }
        if (w == 2) {
            tttOver = true;
            tttZoeWins++;
            status.setText("Zoe wins this round! Tap New Board for a rematch.");
            updateTttScore();
            return true;
        }
        if (ArcadeEngine.isBoardFull(tttBoard)) {
            tttOver = true;
            tttDraws++;
            status.setText("It's a draw! Great defense.");
            updateTttScore();
            return true;
        }
        return false;
    }

    private void resetTicTacToe() {
        for (int i = 0; i < 9; i++) {
            tttBoard[i] = 0;
        }
        tttOver = false;
        renderTttBoard();
        status.setText("Fresh Tic-Tac-Toe board — your move (X)!");
    }

    private void renderTttBoard() {
        int xColor = Ui.resolveColor(this, Ui.COBALT);
        int oColor = Ui.resolveColor(this, Ui.RUBY);
        int emptyColor = Ui.textColor(this);
        for (int i = 0; i < 9; i++) {
            tttCells[i].setText(tttBoard[i] == 1 ? "X" : tttBoard[i] == 2 ? "O" : "");
            tttCells[i].setTextColor(tttBoard[i] == 1 ? xColor : tttBoard[i] == 2 ? oColor : emptyColor);
        }
    }

    private void updateTttScore() {
        tttScoreView.setText("You (X): " + tttWins + " · Draws: " + tttDraws + " · Zoe (O): " + tttZoeWins);
    }

    // --- 3. Kloster A_tau(p) Signal Puzzle ---

    private LinearLayout buildSignalPuzzlePanel() {
        LinearLayout panel = Ui.vertical(this);
        puzzlePromptView = Ui.text(this, "", 16f, Ui.TEXT);
        puzzlePromptView.setTypeface(Ui.SANS_MEDIUM);
        puzzlePromptView.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        puzzlePromptView.setBackground(Ui.cardBackground(this, 20));
        panel.addView(puzzlePromptView);

        LinearLayout chartCard = Ui.vertical(this);
        chartCard.setBackground(Ui.cardBackground(this, 20));
        chartCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        LinearLayout.LayoutParams ccLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        ccLp.setMargins(0, Ui.dp(this, 10), 0, Ui.dp(this, 10));

        puzzleBarsView = new SignalBarView(this);
        chartCard.addView(puzzleBarsView, new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, Ui.dp(this, 152)));

        puzzleTauLabel = Ui.text(this, "Threshold τ = 0.20", 14.5f, Ui.GOLD);
        puzzleTauLabel.setTypeface(Ui.SANS_MEDIUM);
        puzzleTauLabel.setPadding(0, Ui.dp(this, 10), 0, Ui.dp(this, 4));
        chartCard.addView(puzzleTauLabel);

        SeekBar slider = new SeekBar(this);
        slider.setMax(60);
        slider.setProgress(20);
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                puzzleTau = progress / 100.0;
                refreshPuzzleReadout();
            }

            @Override public void onStartTrackingTouch(SeekBar seekBar) { }
            @Override public void onStopTrackingTouch(SeekBar seekBar) { }
        });
        chartCard.addView(slider);
        panel.addView(chartCard, ccLp);

        Button checkBtn = Ui.primaryButton(this, "Check Signal Lock", Ui.GREEN, v -> {
            int got = currentPuzzle.evaluateCount(puzzleTau);
            if (got == currentPuzzle.targetCount) {
                puzzleStreak++;
                status.setText("Bullseye! A_τ(p) = " + got + " of 5 · Streak: " + puzzleStreak + "!");
                loadNewSignalPuzzle();
            } else {
                puzzleStreak = 0;
                status.setText("Currently " + got + " open (goal is " + currentPuzzle.targetCount + "). Needs strictly p > τ.");
            }
        });
        Button skipBtn = Ui.button(this, "New Puzzle", Ui.COBALT, v -> loadNewSignalPuzzle());
        panel.addView(Ui.buttonRow(this, checkBtn, skipBtn));

        loadNewSignalPuzzle();
        return panel;
    }

    private void loadNewSignalPuzzle() {
        currentPuzzle = ArcadeEngine.generateSignalPuzzle(rng);
        refreshPuzzleReadout();
    }

    private void refreshPuzzleReadout() {
        if (currentPuzzle == null) {
            return;
        }
        puzzlePromptView.setText("Goal: Tune τ so " + currentPuzzle.targetCount
                + " of 5 signals pass  ·  Streak: " + puzzleStreak);
        puzzleBarsView.update(currentPuzzle.probs, puzzleTau);
        puzzleTauLabel.setText(String.format(Locale.US, "Threshold τ = %.2f  (strictly p > τ)", puzzleTau));
    }

    /** Crisp Material 3 graphical bar chart with gliding Ruby τ line for the Signal Puzzle. */
    private static final class SignalBarView extends View {
        private final android.graphics.Paint barPaint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Paint gridPaint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Paint tauPaint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.Paint textPaint = new android.graphics.Paint(android.graphics.Paint.ANTI_ALIAS_FLAG);
        private final android.graphics.RectF rect = new android.graphics.RectF();
        private double[] probs = new double[0];
        private double tau = 0.20;

        SignalBarView(android.content.Context ctx) {
            super(ctx);
            float d = ctx.getResources().getDisplayMetrics().density;
            gridPaint.setStrokeWidth(Math.max(1f, 0.8f * d));
            tauPaint.setStrokeWidth(Math.max(1.5f, 2f * d));
            textPaint.setTextSize(11.5f * d);
            textPaint.setTypeface(Ui.SANS_MEDIUM);
            textPaint.setTextAlign(android.graphics.Paint.Align.CENTER);
        }

        void update(double[] nextProbs, double nextTau) {
            this.probs = nextProbs == null ? new double[0] : nextProbs;
            this.tau = nextTau;
            invalidate();
        }

        @Override
        protected void onDraw(android.graphics.Canvas canvas) {
            super.onDraw(canvas);
            float w = getWidth();
            float h = getHeight();
            if (w <= 0f || h <= 0f || probs.length == 0) {
                return;
            }
            android.content.Context ctx = getContext();
            float d = getResources().getDisplayMetrics().density;
            float padTop = 20f * d;
            float padBottom = 22f * d;
            float padLeft = 8f * d;
            float padRight = 24f * d;
            float chartW = Math.max(20f, w - padLeft - padRight);
            float chartH = Math.max(20f, h - padTop - padBottom);
            float baseY = padTop + chartH;

            gridPaint.setColor(Ui.dividerColor(ctx));
            for (int step = 0; step <= 3; step++) {
                float y = baseY - (chartH * step / 3f);
                canvas.drawLine(padLeft, y, padLeft + chartW, y, gridPaint);
            }

            // Draw the gliding Ruby τ line cleanly behind the bars so digits never collide
            float maxScale = 0.65f;
            float tauFrac = (float) Math.min(1.0, Math.max(0.0, tau / maxScale));
            float tauY = baseY - chartH * tauFrac;
            int ruby = Ui.heroAccent(ctx);
            tauPaint.setColor(ruby);
            canvas.drawLine(padLeft, tauY, padLeft + chartW, tauY, tauPaint);
            textPaint.setColor(ruby);
            canvas.drawText("τ", padLeft + chartW + 12f * d, tauY + 4f * d, textPaint);

            float slotW = chartW / probs.length;
            float barW = Math.min(42f * d, Math.max(12f * d, slotW * 0.56f));
            int openCol = Ui.resolveColor(ctx, Ui.GREEN);
            int cutCol = Ui.tonalWellColor(ctx);
            int mutedCol = Ui.mutedColor(ctx);

            for (int i = 0; i < probs.length; i++) {
                double p = probs[i];
                boolean pass = p > tau;
                float cx = padLeft + slotW * (i + 0.5f);
                float frac = (float) Math.min(1.0, p / maxScale);
                float barH = Math.max(6f * d, chartH * frac);
                rect.set(cx - barW * 0.5f, baseY - barH, cx + barW * 0.5f, baseY);
                barPaint.setColor(pass ? openCol : cutCol);
                canvas.drawRoundRect(rect, 7f * d, 7f * d, barPaint);
                // Aligned top value row + crisp bottom status row -> zero collision at any τ
                textPaint.setColor(pass ? openCol : mutedCol);
                canvas.drawText(String.format(Locale.US, "%.2f", p), cx, 13f * d, textPaint);
                canvas.drawText(pass ? "OPEN" : "cut", cx, baseY + 15f * d, textPaint);
            }
        }
    }

    // --- 4. 20 Questions & Interactive Story Adventure ---

    private LinearLayout buildTwentyQuestionsPanel() {
        LinearLayout panel = Ui.vertical(this);
        secretItem = ArcadeEngine.MYSTERY_DECK.get(rng.nextInt(ArcadeEngine.MYSTERY_DECK.size()));
        questionsAsked = 0;

        q20LogView = Ui.text(this,
                "I'm thinking of a mystery item from nature, music, or science! Ask yes/no questions below or guess what it is.",
                15f, Ui.TEXT);
        q20LogView.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        q20LogView.setBackground(Ui.cardBackground(this, 20));
        panel.addView(q20LogView);

        Button b1 = Ui.button(this, "Is it alive?", Ui.COBALT, v -> ask20Q("Is it alive?"));
        Button b2 = Ui.button(this, "Bigger than backpack?", Ui.CYAN, v -> ask20Q("Is it larger than a backpack?"));
        panel.addView(Ui.buttonRow(this, b1, b2));

        Button b3 = Ui.button(this, "Uses electricity?", Ui.GOLD, v -> ask20Q("Does it use electricity?"));
        Button b4 = Ui.button(this, "Give me a hint!", Ui.GREEN, v -> ask20Q("Give me a hint"));
        panel.addView(Ui.buttonRow(this, b3, b4));

        LinearLayout inputRow = new LinearLayout(this);
        inputRow.setOrientation(LinearLayout.HORIZONTAL);
        inputRow.setGravity(Gravity.CENTER_VERTICAL);
        inputRow.setBackground(Ui.cardBackground(this, 20));
        inputRow.setPadding(Ui.dp(this, 12), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));
        q20Input = new EditText(this);
        q20Input.setHint("Ask a question or guess (e.g. Sea Otter)…");
        q20Input.setTextColor(Ui.textColor(this));
        q20Input.setHintTextColor(Ui.mutedColor(this));
        q20Input.setBackground(null);
        Button askBtn = Ui.primaryButton(this, "Ask", Ui.COBALT, v -> {
            String q = q20Input.getText() == null ? "" : q20Input.getText().toString().trim();
            if (!q.isEmpty()) {
                q20Input.setText("");
                ask20Q(q);
            }
        });
        inputRow.addView(q20Input, new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f));
        inputRow.addView(askBtn);
        LinearLayout.LayoutParams irLp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        irLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        panel.addView(inputRow, irLp);

        Button newSecret = Ui.button(this, "New Secret", Ui.MUTED, v -> {
            secretItem = ArcadeEngine.MYSTERY_DECK.get(rng.nextInt(ArcadeEngine.MYSTERY_DECK.size()));
            questionsAsked = 0;
            q20LogView.setText("Picked a brand-new mystery item! Ask your first yes/no question.");
            status.setText("New 20 Questions round ready.");
        });
        Button storyBtn = Ui.primaryButton(this, "Play AI Story in Chat →", Ui.PINK, v -> {
            Intent i = new Intent(this, ConversationActivity.class);
            startActivity(i);
        });
        panel.addView(Ui.buttonRow(this, newSecret, storyBtn));
        return panel;
    }

    private void ask20Q(String q) {
        questionsAsked++;
        String ans = ArcadeEngine.answerTwentyQuestions(secretItem, q);
        q20LogView.setText("Q" + questionsAsked + ": " + q + "\n\nZoe: " + ans);
        status.setText("20 Questions · Question " + questionsAsked + " of 20");
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        handler.removeCallbacksAndMessages(null);
        audioExec.shutdownNow();
    }
}
