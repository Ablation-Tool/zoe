package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.Arrays;
import java.util.Locale;

public final class CellActivity extends ComponentActivity {
    private CellSession session;
    private EditText probabilities;
    private EditText threshold;
    private EditText rawCommand;
    private TextView status;
    private TextView report;
    private TextView historyView;
    private CellCodec.EncodedMeasurement lastMeasurement;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        session = new CellSession();
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        content.addView(Ui.topBar(this, "Tiny Zoe", "Offline protocol simulator"));
        status = Ui.statusBanner(this, "Simulator idle. No hardware, SIM, or network access.", Ui.COBALT);
        status.setId(R.id.cell_status);
        content.addView(status);

        LinearLayout heroCard = Ui.vertical(this);
        heroCard.setBackground(Ui.cardBackground(this, 20));
        heroCard.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        android.widget.ImageView geometry = new android.widget.ImageView(this);
        geometry.setImageResource(R.drawable.cell_hourglass);
        geometry.setAdjustViewBounds(true);
        geometry.setContentDescription("Divine Zoe: concentric chalice and hourglass layers");
        heroCard.addView(geometry, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 96)));
        TextView budget = Ui.text(this,
                "Budget: under 1,900,000 bytes · Reference model: 2,735 bytes (local behavioral simulator only).",
                13, Ui.MUTED);
        budget.setId(R.id.cell_budget);
        budget.setGravity(android.view.Gravity.CENTER);
        heroCard.addView(budget);
        content.addView(heroCard);

        LinearLayout.LayoutParams inLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        inLp.setMargins(0, Ui.dp(this, 2), 0, Ui.dp(this, 8));
        content.addView(Ui.section(this, "Worked Example"));
        content.addView(Ui.text(this, "Probability distribution", 13.5f, Ui.MUTED));
        probabilities = input("0.70, 0.20, 0.08, 0.02");
        probabilities.setId(R.id.cell_probabilities);
        probabilities.setContentDescription("Probabilities separated by commas or spaces");
        content.addView(probabilities, inLp);
        content.addView(Ui.text(this, "Threshold τ", 13.5f, Ui.MUTED));
        threshold = input("0.05");
        threshold.setId(R.id.cell_threshold);
        threshold.setContentDescription("Threshold tau between zero and one");
        LinearLayout.LayoutParams inLp2 = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        inLp2.setMargins(0, Ui.dp(this, 2), 0, Ui.dp(this, 8));
        content.addView(threshold, inLp2);

        Button info = Ui.button(this, "Read card", view -> readInfo());
        info.setId(R.id.cell_info);
        Button measure = Ui.primaryButton(this, "Measure", Ui.RUBY, view -> measure());
        measure.setId(R.id.cell_measure);
        content.addView(Ui.buttonRow(this, info, measure));
        Button reset = Ui.button(this, "Reset", view -> reset());
        reset.setId(R.id.cell_reset);
        Button share = Ui.button(this, "Share", view -> shareSession());
        share.setId(R.id.cell_share);
        content.addView(Ui.buttonRow(this, reset, share));

        report = Ui.text(this,
                "Tap Read card or Measure to test the offline simulator.",
                14.5f, Ui.TEXT);
        report.setId(R.id.cell_report);
        report.setBackground(Ui.cardBackground(this, 20));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        report.setTextIsSelectable(true);
        LinearLayout.LayoutParams repLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        repLp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 6));
        content.addView(report, repLp);

        content.addView(Ui.section(this, "Protocol Console"));
        rawCommand = input("80010000");
        rawCommand.setId(R.id.cell_raw);
        rawCommand.setContentDescription("Hexadecimal APDU command for the local simulator");
        content.addView(rawCommand);
        Button send = Ui.button(this, "Send APDU", view -> sendRaw());
        send.setId(R.id.cell_send);
        Button replay = Ui.button(this, "Replay last", view -> replay());
        replay.setId(R.id.cell_replay);
        content.addView(Ui.buttonRow(this, send, replay));
        historyView = Ui.text(this, "No transactions in this session.", 13.5f, Ui.TEXT);
        historyView.setId(R.id.cell_history);
        historyView.setBackground(Ui.cardBackground(this, 18));
        historyView.setPadding(Ui.dp(this, 14), Ui.dp(this, 12), Ui.dp(this, 14), Ui.dp(this, 12));
        content.addView(historyView, repLp);
        TextView credit = Ui.text(this,
                "Local simulation only · Nicholas Michael Kloster, March 6, 2026.",
                12.5f, Ui.MUTED);
        credit.setGravity(android.view.Gravity.CENTER);
        content.addView(credit);
    }

    private EditText input(String value) {
        EditText input = Ui.input(this, value, "");
        input.setSingleLine(true);
        return input;
    }

    private void readInfo() {
        lastMeasurement = null;
        present(session.transact(CellCodec.infoRequest()),
                "Simulated card information returned. No hardware was accessed.");
    }

    private void measure() {
        try {
            String distributionText = probabilities.getText().toString();
            if (distributionText.length() > 4096) {
                throw new IllegalArgumentException("Probability input exceeds 4096 characters");
            }
            String thresholdText = threshold.getText().toString().trim();
            if (thresholdText.length() > 64) {
                throw new IllegalArgumentException("Tau input exceeds 64 characters");
            }
            double[] distribution = AccessibleVolume.parse(distributionText);
            double tau = Double.parseDouble(thresholdText);
            lastMeasurement = CellCodec.encode(distribution, tau);
            present(session.transact(lastMeasurement.apdu),
                    "Simulated card answered. No hardware or SIM was accessed.");
        } catch (IllegalArgumentException error) {
            fail(error);
        }
    }

    private void sendRaw() {
        try {
            lastMeasurement = null;
            present(session.transact(CellCodec.parseCommand(rawCommand.getText().toString())),
                    "Raw APDU completed locally. No hardware or external action was used.");
        } catch (IllegalArgumentException error) {
            fail(error);
        }
    }

    private void replay() {
        CellSession.Transaction transaction = session.replay();
        if (transaction == null) {
            status.setText("No transaction to replay. Session is empty.");
            return;
        }
        present(transaction, "Replayed the same bounded request locally. No external action was used.");
    }

    private void present(CellSession.Transaction transaction, String message) {
        report.setText(format(transaction));
        rawCommand.setText(CellCodec.hex(transaction.request()));
        StringBuilder history = new StringBuilder();
        for (CellSession.Transaction item : session.history()) {
            if (history.length() > 0) {
                history.append('\n');
            }
            history.append(item.summary());
        }
        historyView.setText(history);
        status.setText(message);
    }

    private String format(CellSession.Transaction transaction) {
        byte[] request = transaction.request();
        byte[] response = transaction.response();
        StringBuilder text = new StringBuilder(String.format(Locale.US,
                "APDU request: %d bytes\n%s\nAPDU response: %d bytes\n%s\nStatus: 0x%04X\n",
                request.length, CellCodec.hex(request), response.length,
                CellCodec.hex(response), transaction.status()));
        if (transaction.status() == 0x9000 && request.length > 1) {
            if (request[1] == 0x01) {
                text.append('\n').append(CellCodec.decodeInfo(response));
            } else if (request[1] == 0x02) {
                CellCodec.Measurement measurement = CellCodec.decodeMeasurement(response);
                text.append(String.format(Locale.US,
                        "\nA = %d of %d\nComplement = %d\nQuantized tau = %.6f",
                        measurement.accessible, measurement.vocabularySize,
                        measurement.complement, measurement.tau / (double) CellCodec.SCALE));
                if (lastMeasurement != null) {
                    text.append("\n\nQ0.15 probabilities:\n")
                            .append(Arrays.toString(lastMeasurement.probabilities));
                }
                text.append("\n\nStrict p > τ · equality excluded · no action authorized");
            }
        }
        return text.toString();
    }

    private void fail(IllegalArgumentException error) {
        status.setText("Command rejected: " + error.getMessage());
        report.setText("No measurement was returned. Check the distribution and threshold, then try again.");
    }

    private void shareSession() {
        if (session.history().isEmpty()) {
            status.setText("Nothing to share yet. Read or measure on the simulated card first.");
            return;
        }
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Tiny Zoe · simulated protocol session")
                .putExtra(Intent.EXTRA_TEXT, session.exportText());
        try {
            startActivity(Intent.createChooser(share, "Share simulated session"));
            status.setText("Share sheet opened. The export describes a simulation, not physical-card evidence.");
        } catch (ActivityNotFoundException error) {
            status.setText("No sharing app is available. The session remains only on this screen.");
        }
    }

    private void reset() {
        session.reset();
        lastMeasurement = null;
        rawCommand.setText("80010000");
        historyView.setText("No transactions in this session.");
        status.setText("Simulator reset. No hardware, SIM, or network access.");
        report.setText("No command sent. Choose Read simulated card or Measure on simulated card.");
    }
}
