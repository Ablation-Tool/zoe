package research.zoetic.zoe;

import android.text.InputType;
import android.view.View;
import android.widget.EditText;
import android.widget.ScrollView;
import android.widget.SeekBar;
import android.widget.TextView;

import java.util.Locale;

final class VolumeView extends ScrollView {
    private final EditText input;
    private final TextView thresholdLabel;
    private final TextView resultView;
    private AccessibleVolume.Result previous;
    private AccessibleVolume.Result current;

    VolumeView(MainActivity activity) {
        super(activity);
        setFillViewport(true);
        android.widget.LinearLayout content = Ui.vertical(activity);
        content.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 8), Ui.dp(activity, 16), Ui.dp(activity, 24));
        addView(content);

        content.addView(Ui.heading(activity, "Accessible volume"));
        content.addView(Ui.text(activity,
                "Measure how many alternatives remain open before selection. Forecast breadth is not correctness, safety, or permission.",
                16, Ui.MUTED));
        content.addView(Ui.text(activity, "Probability distribution", 16, Ui.CYAN));
        input = new EditText(activity);
        input.setId(R.id.volume_input);
        input.setText("0.70, 0.20, 0.08, 0.02");
        input.setTextColor(Ui.TEXT);
        input.setHintTextColor(Ui.MUTED);
        input.setTextSize(18);
        input.setSingleLine(false);
        input.setMinLines(2);
        input.setMaxLines(6);
        input.setGravity(android.view.Gravity.TOP | android.view.Gravity.START);
        input.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        input.setBackground(Ui.panelBackground(activity, Ui.CYAN, 12));
        input.setPadding(Ui.dp(activity, 14), Ui.dp(activity, 12), Ui.dp(activity, 14), Ui.dp(activity, 12));
        input.setContentDescription("Probabilities separated by commas or spaces");
        content.addView(input);

        thresholdLabel = Ui.text(activity, "Threshold τ = 0.050", 17, Ui.YELLOW);
        content.addView(thresholdLabel);
        SeekBar threshold = new SeekBar(activity);
        threshold.setId(R.id.volume_threshold);
        threshold.setMax(1000);
        threshold.setProgress(50);
        threshold.setContentDescription("Accessible-volume probability threshold");
        threshold.setOnSeekBarChangeListener(new SeekBar.OnSeekBarChangeListener() {
            @Override
            public void onProgressChanged(SeekBar seekBar, int progress, boolean fromUser) {
                thresholdLabel.setText(String.format(Locale.US, "Threshold τ = %.3f", progress / 1000.0));
            }

            @Override
            public void onStartTrackingTouch(SeekBar seekBar) {
            }

            @Override
            public void onStopTrackingTouch(SeekBar seekBar) {
            }
        });
        content.addView(threshold);
        android.widget.Button measureButton = Ui.button(activity, "Measure strict p > τ", this::measure);
        measureButton.setId(R.id.measure_button);
        content.addView(measureButton);

        resultView = Ui.text(activity,
                "The worked example has three alternatives above 0.05. Tokens exactly at the threshold are excluded.",
                18, Ui.GREEN);
        resultView.setId(R.id.volume_result);
        resultView.setBackground(Ui.panelBackground(activity, Ui.GREEN, 16));
        resultView.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 16), Ui.dp(activity, 16), Ui.dp(activity, 16));
        resultView.setContentDescription("Accessible-volume measurement result");
        content.addView(resultView);
        content.addView(Ui.text(activity,
                "Original equation created by Nicholas Michael Kloster alone, March 6, 2026.\n\nMomentum compares consecutive counts at the same threshold and vocabulary size. Equal counts do not imply identical distributions or accessible-set membership.",
                14, Ui.MUTED));
    }

    private void measure(View view) {
        measure();
    }

    void measure() {
        try {
            double[] probabilities = AccessibleVolume.parse(input.getText().toString());
            SeekBar threshold = findViewById(R.id.volume_threshold);
            double tau = threshold.getProgress() / 1000.0;
            AccessibleVolume.Result next = AccessibleVolume.measure(probabilities, tau);
            String momentum = previous != null && previous.vocabularySize == next.vocabularySize
                    ? String.format(Locale.US, "\nMomentum = %+d", next.accessible - previous.accessible)
                    : "\nMomentum = not available for the first or differently sized distribution";
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
        return resultView.getText().toString() + "\n\n" + AccessibleVolume.CREATOR;
    }
}
