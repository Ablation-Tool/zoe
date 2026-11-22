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
import android.widget.HorizontalScrollView;
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
    private TextView puzzleBarsView;
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
        header.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 4));
        header.addView(Ui.topBar(this, "Zoe Arcade", "100% Offline · Ad-Free · Play with Zoe"));

        HorizontalScrollView tabStrip = new HorizontalScrollView(this);
        tabStrip.setHorizontalScrollBarEnabled(false);
        LinearLayout tabRow = new LinearLayout(this);
        tabRow.setOrientation(LinearLayout.HORIZONTAL);
        tabRow.setPadding(0, Ui.dp(this, 4), 0, Ui.dp(this, 4));

        String[] names = {"Memory", "Tic-Tac-Toe", "Kloster Signal", "20 Questions"};
        int[] tabIds = {R.id.arcade_tab_memory, R.id.arcade_tab_ttt, R.id.arcade_tab_signal, R.id.arcade_tab_20q};
        tabBtns = new Button[4];
        for (int i = 0; i < 4; i++) {
            final int idx = i;
            Button b = pillChip(names[i], v -> selectGameTab(idx));
            b.setId(tabIds[i]);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, Ui.dp(this, 40));
            lp.setMargins(0, 0, Ui.dp(this, 6), 0);
            tabRow.addView(b, lp);
            tabBtns[i] = b;
        }
        tabStrip.addView(tabRow);
        header.addView(tabStrip);

        status = Ui.text(this, "Pick a game and play with Zoe offline — zero ads, zero tracking.", 13.5f, Ui.COBALT);
        status.setId(R.id.arcade_status);
        status.setPadding(Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4), Ui.dp(this, 4));
        header.addView(status);
        root.addView(header);

        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        LinearLayout body = Ui.vertical(this);
        body.setPadding(Ui.dp(this, 14), Ui.dp(this, 6), Ui.dp(this, 14), Ui.dp(this, 18));

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
        b.setTextSize(13f);
        b.setTypeface(Ui.SANS_MEDIUM);
        b.setAllCaps(false);
        b.setPadding(Ui.dp(this, 14), 0, Ui.dp(this, 14), 0);
        b.setStateListAnimator(null);
        b.setOnClickListener(listener);
        return b;
    }

    private void selectGameTab(int index) {
        for (int i = 0; i < 4; i++) {
            boolean sel = i == index;
            gamePanels[i].setVisibility(sel ? View.VISIBLE : View.GONE);
            if (sel) {
                tabBtns[i].setTextColor(Ui.isDark(this) ? Color.rgb(14, 15, 18) : Color.WHITE);
                tabBtns[i].setBackground(Ui.tonalPillDrawable(this, Ui.primaryAccent(this), Ui.primaryAccent(this), 20));
            } else {
                tabBtns[i].setTextColor(Ui.textColor(this));
                tabBtns[i].setBackground(Ui.outlinedPillDrawable(this, Ui.panelColor(this), Ui.dividerColor(this), Ui.primaryAccent(this), 20));
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
                Button b = new Button(this);
                b.setText(ArcadeEngine.PETAL_NAMES[idx]);
                b.setTextSize(16f);
                b.setTypeface(Ui.SANS_MEDIUM);
                b.setAllCaps(false);
                b.setTextColor(Color.WHITE);
                b.setBackground(Ui.tonalPillDrawable(this, accents[idx], accents[idx], 26));
                b.setAlpha(0.75f);
                b.setOnClickListener(v -> onPetalTapped(idx));
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(0, Ui.dp(this, 118), 1f);
                lp.setMargins(Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6), Ui.dp(this, 6));
                r.addView(b, lp);
                petalBtns[idx] = b;
            }
            panel.addView(r);
        }

        Button startMem = Ui.primaryButton(this, "Start GEM Memory", Ui.COBALT, v -> startMemoryGame());
        startMem.setId(R.id.arcade_memory_start);
        panel.addView(startMem);
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
                cell.setOnClickListener(v -> onTttCellTap(idx));
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

        tttModeBtn = Ui.button(this, "Difficulty: Unbeatable", Ui.GOLD, v -> {
            tttUnbeatable = !tttUnbeatable;
            tttModeBtn.setText(tttUnbeatable ? "Difficulty: Unbeatable" : "Difficulty: Kid Friendly");
            resetTicTacToe();
        });
        Button newBoard = Ui.primaryButton(this, "New Board", Ui.COBALT, v -> resetTicTacToe());
        panel.addView(Ui.buttonRow(this, newBoard, tttModeBtn));
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
        for (int i = 0; i < 9; i++) {
            tttCells[i].setText(tttBoard[i] == 1 ? "X" : tttBoard[i] == 2 ? "O" : "");
            tttCells[i].setTextColor(tttBoard[i] == 1 ? Ui.COBALT : tttBoard[i] == 2 ? Ui.RUBY : Ui.textColor(this));
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
        puzzlePromptView.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        puzzlePromptView.setBackground(Ui.cardBackground(this, 20));
        panel.addView(puzzlePromptView);

        puzzleBarsView = Ui.text(this, "", 14.5f, Ui.CYAN);
        puzzleBarsView.setTypeface(android.graphics.Typeface.MONOSPACE);
        puzzleBarsView.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        panel.addView(puzzleBarsView);

        puzzleTauLabel = Ui.text(this, "Threshold τ = 0.20", 14.5f, Ui.GOLD);
        puzzleTauLabel.setPadding(Ui.dp(this, 6), Ui.dp(this, 4), Ui.dp(this, 6), Ui.dp(this, 4));
        panel.addView(puzzleTauLabel);

        SeekBar slider = new SeekBar(this);
        slider.setMax(60);
        slider.setProgress(20);
        slider.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                puzzleTau = progress / 100.0;
                refreshPuzzleReadout();
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {
            }
        });
        panel.addView(slider);

        Button checkBtn = Ui.primaryButton(this, "Check Signal Lock", Ui.GREEN, v -> {
            int got = currentPuzzle.evaluateCount(puzzleTau);
            if (got == currentPuzzle.targetCount) {
                puzzleStreak++;
                status.setText("Bullseye! Strict A_tau(p) = " + got + " of 5 · Streak: " + puzzleStreak + "!");
                loadNewSignalPuzzle();
            } else {
                puzzleStreak = 0;
                status.setText("Currently A_tau(p) = " + got + " (target is " + currentPuzzle.targetCount + "). Remember strict inequality p > τ!");
            }
        });
        Button skipBtn = Ui.button(this, "New Distribution", Ui.COBALT, v -> loadNewSignalPuzzle());
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
        puzzlePromptView.setText("Goal: Tune τ so strictly A_τ(p) = " + currentPuzzle.targetCount
                + " of 5 signals pass (Streak: " + puzzleStreak + ")");
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < currentPuzzle.probs.length; i++) {
            double p = currentPuzzle.probs[i];
            boolean pass = p > puzzleTau;
            int bars = Math.max(1, (int) Math.round(p * 24));
            StringBuilder barStr = new StringBuilder();
            for (int k = 0; k < bars; k++) {
                barStr.append(pass ? '█' : '░');
            }
            sb.append(String.format(Locale.US, "x%d  %.2f  %s %s\n", i + 1, p, barStr, pass ? "OPEN" : "cut"));
        }
        puzzleBarsView.setText(sb.toString().trim());
        puzzleTauLabel.setText(String.format(Locale.US, "Threshold τ = %.2f  (strictly p > τ)", puzzleTau));
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
