package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.text.Editable;
import android.text.InputType;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;

import java.util.Locale;

final class VolumeView extends ScrollView {
    private final EditText input;
    private final TextView thresholdLabel;
    private final VolumeGraphView graphView;
    private final TextView resultView;
    private AccessibleVolume.Result previous;
    private AccessibleVolume.Result current;

    VolumeView(MainActivity activity) {
        super(activity);
        setFillViewport(true);
        setBackgroundColor(Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(activity);
        content.setBackgroundColor(Color.TRANSPARENT);
        content.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 4), Ui.dp(activity, 16), Ui.dp(activity, 24));
        addView(content);

        content.addView(Ui.heading(activity, "Accessible volume"));
        content.addView(Ui.text(activity,
                "Count alternatives strictly above τ. Breadth is not correctness or permission.",
                14.5f, Ui.MUTED));

        // Clean borderless input + slider + live chart card
        LinearLayout controlCard = Ui.vertical(activity);
        controlCard.setBackground(Ui.cardBackground(activity, 20));
        controlCard.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 14), Ui.dp(activity, 16), Ui.dp(activity, 16));

        TextView distLabel = Ui.text(activity, "Probability distribution", 13.5f, Ui.MUTED);
        distLabel.setTypeface(Ui.SANS_MEDIUM);
        controlCard.addView(distLabel);

        input = Ui.input(activity, "0.70, 0.20, 0.08, 0.02", "e.g. 0.70, 0.20, 0.08, 0.02");
        input.setId(R.id.volume_input);
        input.setTextSize(16f);
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(4);
        input.setGravity(Gravity.TOP | Gravity.START);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        input.setContentDescription("Probabilities separated by commas or spaces");
        controlCard.addView(input);

        thresholdLabel = Ui.text(activity, "Threshold τ = 0.050", 14.5f, Ui.TEXT);
        thresholdLabel.setTypeface(Ui.SANS_MEDIUM);
        thresholdLabel.setPadding(0, Ui.dp(activity, 14), 0, Ui.dp(activity, 4));
        controlCard.addView(thresholdLabel);

        SeekBar threshold = new SeekBar(activity);
        threshold.setId(R.id.volume_threshold);
        threshold.setMax(1000);
        threshold.setProgress(50);
        threshold.setContentDescription("Accessible-volume probability threshold");
        controlCard.addView(threshold);

        graphView = new VolumeGraphView(activity);
        LinearLayout.LayoutParams graphParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(activity, 128));
        graphParams.setMargins(0, Ui.dp(activity, 10), 0, Ui.dp(activity, 14));
        controlCard.addView(graphView, graphParams);

        Button measureButton = Ui.primaryButton(activity, "Measure strict p > τ", Ui.RUBY, this::measure);
        measureButton.setId(R.id.measure_button);
        controlCard.addView(measureButton);

        LinearLayout.LayoutParams cardMargins = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        cardMargins.setMargins(0, Ui.dp(activity, 10), 0, Ui.dp(activity, 12));
        content.addView(controlCard, cardMargins);

        threshold.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                double t = progress / 1000.0;
                thresholdLabel.setText(String.format(Locale.US, "Threshold τ = %.3f", t));
                graphView.update(input.getText().toString(), t);
            }

            @Override public void onStartTrackingTouch(SeekBar seekBar) { }
            @Override public void onStopTrackingTouch(SeekBar seekBar) { }
        });
        input.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) { }
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) { }
            @Override
            public void afterTextChanged(Editable s) {
                graphView.update(s == null ? "" : s.toString(), threshold.getProgress() / 1000.0);
            }
        });
        graphView.update(input.getText().toString(), 0.05);

        resultView = Ui.text(activity,
                "The worked example has three alternatives above 0.05. Tokens exactly at the threshold are excluded.",
                15.5f, Ui.TEXT);
        resultView.setId(R.id.volume_result);
        resultView.setBackground(Ui.cardBackground(activity, 20));
        resultView.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 16), Ui.dp(activity, 16), Ui.dp(activity, 16));
        resultView.setContentDescription("Accessible-volume measurement result");
        content.addView(resultView);

        TextView note = Ui.text(activity,
                "Original equation created by Nicholas Michael Kloster alone, March 6, 2026.",
                12.5f, Ui.MUTED);
        note.setPadding(Ui.dp(activity, 4), Ui.dp(activity, 12), Ui.dp(activity, 4), 0);
        content.addView(note);
    }

    private void measure(View view) {
        measure();
    }

    void measure() {
        try {
            double[] probabilities = AccessibleVolume.parse(input.getText().toString());
            SeekBar threshold = findViewById(R.id.volume_threshold);
            double tau = threshold.getProgress() / 1000.0;
            graphView.update(input.getText().toString(), tau);
            AccessibleVolume.Result next = AccessibleVolume.measure(probabilities, tau);
            String momentum = previous != null
                    && previous.vocabularySize == next.vocabularySize
                    && Double.compare(previous.tau, next.tau) == 0
                    ? String.format(Locale.US, "\nMomentum = %+d", next.accessible - previous.accessible)
                    : "\nMomentum = not available for the first, altered-τ, or differently sized distribution";
            previous = next;
            current = next;
            resultView.setText(next.summary() + momentum
                    + "\n\nBreadth is not correctness. No action was authorized.");
            resultView.announceForAccessibility(next.summary());
        } catch (IllegalArgumentException error) {
            current = null;
            resultView.setText("Measurement rejected: " + error.getMessage());
            resultView.announceForAccessibility("Measurement rejected");
        }
    }

    String spokenSummary() {
        return current == null
                ? "Enter a complete probability distribution and choose Measure."
                : current.summary() + ". Forecast breadth is not correctness.";
    }

    String shareText() {
        return current == null
                ? "Zoe accessible volume\n" + resultView.getText()
                : current.summary() + "\n" + AccessibleVolume.CREATOR + "\nBreadth is not correctness. No action was authorized.";
    }

    /** Clean live probability bar visualizer with a gliding Ruby τ threshold line. */
    private static final class VolumeGraphView extends View {
        private final Paint barPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint gridPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint tauPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint textPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final RectF rect = new RectF();
        private double[] values = {0.70, 0.20, 0.08, 0.02};
        private double tau = 0.05;

        VolumeGraphView(Context context) {
            super(context);
            setImportantForAccessibility(IMPORTANT_FOR_ACCESSIBILITY_NO);
            float d = context.getResources().getDisplayMetrics().density;
            gridPaint.setStrokeWidth(Math.max(1f, 0.8f * d));
            tauPaint.setStrokeWidth(Math.max(1.5f, 1.8f * d));
            textPaint.setTextSize(11f * d);
            textPaint.setTypeface(Ui.SANS_MEDIUM);
            textPaint.setTextAlign(Paint.Align.CENTER);
        }

        void update(String raw, double nextTau) {
            this.tau = Math.max(0.0, Math.min(1.0, nextTau));
            if (raw != null && !raw.trim().isEmpty()) {
                String[] parts = raw.trim().split("[,\\s]+");
                double[] parsed = new double[Math.min(parts.length, 16)];
                int count = 0;
                for (int i = 0; i < parsed.length; i++) {
                    try {
                        double v = Double.parseDouble(parts[i]);
                        if (Double.isFinite(v) && v >= 0.0) {
                            parsed[count++] = Math.min(1.0, v);
                        }
                    } catch (NumberFormatException ignored) {
                    }
                }
                if (count > 0) {
                    double[] trimmed = new double[count];
                    System.arraycopy(parsed, 0, trimmed, 0, count);
                    this.values = trimmed;
                }
            }
            invalidate();
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float w = getWidth();
            float h = getHeight();
            if (w <= 0f || h <= 0f || values.length == 0) {
                return;
            }
            Context ctx = getContext();
            float d = getResources().getDisplayMetrics().density;
            float padTop = 18f * d;
            float padBottom = 10f * d;
            float padLeft = 6f * d;
            float padRight = 24f * d;
            float chartH = Math.max(20f, h - padTop - padBottom);
            float chartW = Math.max(20f, w - padLeft - padRight);
            float baseY = padTop + chartH;

            gridPaint.setColor(Ui.dividerColor(ctx));
            for (int step = 0; step <= 4; step++) {
                float y = baseY - (chartH * step / 4f);
                canvas.drawLine(padLeft, y, padLeft + chartW, y, gridPaint);
            }

            int n = values.length;
            float slotW = chartW / n;
            float barW = Math.min(44f * d, Math.max(6f * d, slotW * 0.58f));
            float radius = 6f * d;
            int activeColor = Ui.resolveColor(ctx, Ui.GREEN);
            int mutedBar = Ui.tonalWellColor(ctx);
            int labelColor = Ui.mutedColor(ctx);

            for (int i = 0; i < n; i++) {
                double p = values[i];
                boolean above = p > tau;
                float cx = padLeft + slotW * (i + 0.5f);
                float barH = (float) (chartH * Math.max(0.02, p));
                rect.set(cx - barW * 0.5f, baseY - barH, cx + barW * 0.5f, baseY);
                barPaint.setColor(above ? activeColor : mutedBar);
                canvas.drawRoundRect(rect, radius, radius, barPaint);
                if (n <= 8) {
                    textPaint.setColor(above ? activeColor : labelColor);
                    canvas.drawText(String.format(Locale.US, "%.2f", p), cx, Math.max(12f * d, rect.top - 5f * d), textPaint);
                }
            }

            float tauY = baseY - (float) (chartH * tau);
            int ruby = Ui.heroAccent(ctx);
            tauPaint.setColor(ruby);
            canvas.drawLine(padLeft, tauY, padLeft + chartW, tauY, tauPaint);
            textPaint.setColor(ruby);
            canvas.drawText("τ", padLeft + chartW + 11f * d, tauY + 4f * d, textPaint);
        }
    }
}
