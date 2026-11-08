package research.zoetic.zoe;

import android.app.AlertDialog;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class TrinityActivity extends ComponentActivity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean inFlight = new AtomicBoolean(false);
    private final TrinityClient client = new TrinityClient();
    private Handler handler;
    private EditText probabilities;
    private EditText threshold;
    private TextView status;
    private TextView mobileReport;
    private TextView tinyReport;
    private TextView laptopReport;
    private TextView history;
    private Button connect;
    private boolean connected;
    private int revision = -1;

    private final Runnable poll = new Runnable() {
        @Override
        public void run() {
            if (connected) {
                perform(client::fetch, false, "Shared field synchronized.");
            }
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        handler = new Handler(Looper.getMainLooper());
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 12), Ui.dp(this, 18), Ui.dp(this, 28));
        scroll.addView(content);
        setContentView(scroll);

        content.addView(Ui.button(this, "‹ Zoe home", view -> finish()));
        content.addView(Ui.heading(this, "Zoe Trinity"));
        content.addView(Ui.text(this, "PLAY · LEARN · ADAPT · CREATE · EXPLORE · SHARE", 11, Ui.PINK));
        content.addView(Ui.text(this,
                "Three planes. One shared field. Tiny checks the bytes, mobile holds the experiment, and laptop keeps the long view.",
                16, Ui.TEXT));
        status = Ui.text(this, "Trinity is off. Start the laptop companion, then connect explicitly.", 16, Ui.YELLOW);
        status.setId(R.id.trinity_status);
        content.addView(status);
        TextView setup = Ui.text(this,
                "On the laptop, from the Zoe checkout:\npython mobile/tools/zoe_trinity.py\n\nThen connect the Android over USB:\nadb reverse tcp:8767 tcp:8767\n\nOpen http://127.0.0.1:8767 on the laptop. No cloud, camera, or microphone is used.",
                13, Ui.MUTED);
        setup.setTextIsSelectable(true);
        setup.setBackground(Ui.panelBackground(this, Ui.CYAN, 18));
        setup.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        content.addView(setup);

        content.addView(Ui.section(this, "THE SHARED EXPERIMENT"));
        content.addView(Ui.text(this, "Probability distribution · 1 to 64 values", 14, Ui.TEXT));
        probabilities = input("0.70, 0.20, 0.08, 0.02");
        probabilities.setId(R.id.trinity_probabilities);
        content.addView(probabilities);
        content.addView(Ui.text(this, "Threshold τ", 14, Ui.TEXT));
        threshold = input("0.05");
        threshold.setId(R.id.trinity_threshold);
        content.addView(threshold);
        connect = Ui.button(this, "Connect laptop", view -> connect());
        connect.setId(R.id.trinity_connect);
        Button measure = Ui.button(this, "Measure together", view -> measure());
        measure.setId(R.id.trinity_measure);
        content.addView(Ui.buttonRow(this, connect, measure));
        Button reset = Ui.button(this, "Fresh shared view", view -> confirmReset());
        reset.setId(R.id.trinity_reset);
        content.addView(reset);

        content.addView(Ui.section(this, "01 · TINY ZOE / CELL PLANE"));
        tinyReport = plane("Quantized Q0.15 witness appears after connection.", Ui.YELLOW);
        tinyReport.setId(R.id.trinity_tiny);
        content.addView(tinyReport);
        content.addView(Ui.section(this, "02 · ZOE MOBILE / NATIVE PLANE"));
        mobileReport = plane("Strict floating-point measurement appears after connection.", Ui.CYAN);
        mobileReport.setId(R.id.trinity_mobile);
        content.addView(mobileReport);
        content.addView(Ui.section(this, "03 · LAPTOP ZOE / FIELD PLANE"));
        laptopReport = plane("Revision, history, and optional long-term memory appear after connection.", Ui.PINK);
        laptopReport.setId(R.id.trinity_laptop);
        content.addView(laptopReport);
        content.addView(Ui.section(this, "FIELD NOTES"));
        history = Ui.text(this, "No shared observations loaded.", 14, Ui.TEXT);
        history.setId(R.id.trinity_history);
        history.setTextIsSelectable(true);
        content.addView(history);
        content.addView(Ui.text(this,
                "Observation ≠ evidence ≠ belief update ≠ action. Trinity measurements authorize no external action. Nicholas Michael Kloster alone created the original equation on March 6, 2026.",
                13, Ui.MUTED));
    }

    private EditText input(String value) {
        EditText input = new EditText(this);
        input.setText(value);
        input.setTextSize(16);
        input.setTextColor(Ui.TEXT);
        input.setHintTextColor(Ui.MUTED);
        input.setSingleLine(true);
        input.setPadding(Ui.dp(this, 14), Ui.dp(this, 10), Ui.dp(this, 14), Ui.dp(this, 10));
        input.setBackground(Ui.panelBackground(this, Ui.MUTED, 12));
        return input;
    }

    private TextView plane(String value, int accent) {
        TextView view = Ui.text(this, value, 15, Ui.TEXT);
        view.setBackground(Ui.panelBackground(this, accent, 18));
        view.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        view.setTextIsSelectable(true);
        return view;
    }

    private void connect() {
        if (connected) {
            connected = false;
            handler.removeCallbacks(poll);
            connect.setText("Connect laptop");
            status.setText("Trinity disconnected. No further laptop requests will be made.");
            return;
        }
        connected = true;
        revision = -1;
        connect.setText("Disconnect");
        status.setText("Connecting to the laptop over ADB localhost…");
        perform(client::fetch, true, "Connected. All three planes are synchronized.");
    }

    private void measure() {
        if (!connected) {
            status.setText("Connect the laptop before measuring together. Nothing was sent.");
            return;
        }
        try {
            String distribution = probabilities.getText().toString();
            String tau = threshold.getText().toString().trim();
            if (distribution.length() > 4096 || tau.length() > 64) {
                throw new IllegalArgumentException("Distribution or threshold input is too long");
            }
            double[] values = AccessibleVolume.parse(distribution);
            double thresholdValue = Double.parseDouble(tau);
            new TrinityMeasurement(values, thresholdValue);
            perform(() -> client.measure(values, thresholdValue), true, "Measured together across all three planes.");
        } catch (IllegalArgumentException error) {
            status.setText("Experiment rejected: " + error.getMessage());
        }
    }

    private void confirmReset() {
        if (!connected) {
            status.setText("Connect the laptop before starting a fresh shared view.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Start a fresh shared view?")
                .setMessage("The live history will clear. An enabled laptop journal preserves this reset and all earlier events.")
                .setNegativeButton("Keep exploring", null)
                .setPositiveButton("Fresh view", (dialog, which) ->
                        perform(client::reset, true, "Fresh shared view started."))
                .show();
    }

    private void perform(Request request, boolean forceInputs, String success) {
        if (!connected || !inFlight.compareAndSet(false, true)) {
            return;
        }
        handler.removeCallbacks(poll);
        executor.execute(() -> {
            try {
                TrinityClient.State state = request.run();
                runOnUiThread(() -> complete(state, null, forceInputs, success));
            } catch (Exception error) {
                runOnUiThread(() -> complete(null, error, forceInputs, success));
            }
        });
    }

    private void complete(TrinityClient.State state, Exception error, boolean forceInputs, String success) {
        inFlight.set(false);
        if (!connected) {
            return;
        }
        if (error != null) {
            status.setText("Trinity could not synchronize: " + error.getMessage()
                    + ". Check the laptop server and adb reverse; no data was sent elsewhere.");
        } else {
            render(state, forceInputs);
            status.setText(success + " Revision " + state.revision + ".");
        }
        handler.postDelayed(poll, 1500);
    }

    private void render(TrinityClient.State state, boolean forceInputs) {
        if (forceInputs || (!probabilities.hasFocus() && !threshold.hasFocus())) {
            StringBuilder distribution = new StringBuilder();
            for (double value : state.active.mobile.probabilities()) {
                if (distribution.length() > 0) {
                    distribution.append(", ");
                }
                distribution.append(value);
            }
            probabilities.setText(distribution.toString());
            threshold.setText(Double.toString(state.active.mobile.tau()));
        }
        AccessibleVolume.Result mobile = state.active.mobile.result();
        mobileReport.setText(String.format(Locale.US,
                "Zoe mobile\nA = %d of %d · complement = %d\nStrict p > %.6f · equality excluded\nNormalized accessible volume %.6f",
                mobile.accessible, mobile.vocabularySize, mobile.complement,
                state.active.mobile.tau(), mobile.normalized));
        TrinityClient.TinyWitness tiny = state.active.tiny;
        tinyReport.setText(String.format(Locale.US,
                "Tiny Zoe\nA = %d of %d · complement = %d\nQ0.15 τ = %d / 32768\n%s\nAPDU request %s\nAPDU response %s",
                tiny.accessible, tiny.vocabularySize, tiny.complement, tiny.tau,
                tiny.changed ? "Quantization changed the representation or count" : "Quantized count agrees with mobile",
                tiny.request, tiny.response));
        laptopReport.setText(state.memoryEnabled
                ? String.format(Locale.US,
                "Laptop Zoe\nRevision %d · %d retained live observations\nLong-term journal: %d events, verified on load\nTamper evidence, not authentication",
                state.revision, state.events.size(), state.memoryRecords)
                : String.format(Locale.US,
                "Laptop Zoe\nRevision %d · %d retained live observations\nMemory only · stopping the server erases this session\nStart with --memory PATH for an append-only journal",
                state.revision, state.events.size()));
        StringBuilder notes = new StringBuilder();
        for (int index = state.events.size() - 1; index >= 0; index--) {
            TrinityClient.Event event = state.events.get(index);
            notes.append(String.format(Locale.US,
                    "#%d · %s · τ %.6f\nMobile A %d/%d · Tiny A %d/%d\n",
                    event.ordinal, event.source, event.tau, event.zoeAccessible,
                    event.zoeSize, event.tinyAccessible, event.tinySize));
        }
        history.setText(notes.length() == 0 ? "No shared measurements yet. Make the first mark." : notes.toString());
        revision = state.revision;
    }

    @Override
    protected void onPause() {
        connected = false;
        handler.removeCallbacks(poll);
        connect.setText("Connect laptop");
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        connected = false;
        handler.removeCallbacks(poll);
        executor.shutdownNow();
        super.onDestroy();
    }

    private interface Request {
        TrinityClient.State run() throws Exception;
    }
}
