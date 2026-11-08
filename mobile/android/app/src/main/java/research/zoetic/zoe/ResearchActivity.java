package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

public final class ResearchActivity extends ComponentActivity {
    private TextView status;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 12), Ui.dp(this, 18), Ui.dp(this, 28));
        scroll.addView(content);
        setContentView(scroll);

        content.addView(Ui.button(this, "‹ Zoe home", view -> finish()));
        content.addView(Ui.heading(this, "Researcher guide"));
        content.addView(Ui.text(this, "PLAY · LEARN · ADAPT · CREATE · EXPLORE · SHARE", 12, Ui.PINK));
        TextView version = Ui.text(this, "Zoe " + versionName() + " · research preview", 15, Ui.GREEN);
        version.setId(R.id.research_version);
        content.addView(version);

        content.addView(Ui.section(this, "YOUR FIRST FIVE MINUTES"));
        content.addView(Ui.text(this,
                "1. Open Accessible volume and measure the worked distribution.\n\n"
                        + "2. Open Tiny Zoe. Read the simulated card, measure once, then inspect the raw request and response.\n\n"
                        + "3. Try tau = 0.20 with the default distribution. Equality is excluded, so A = 1 of 4.\n\n"
                        + "4. Replay the last command. The bytes and result stay identical.\n\n"
                        + "5. Choose Share session only when you want to export the retained transactions.",
                16, Ui.TEXT));
        Button openCell = Ui.button(this, "Open Tiny Zoe", view ->
                startActivity(new Intent(this, CellActivity.class)));
        openCell.setId(R.id.research_open_cell);
        content.addView(openCell);

        content.addView(Ui.section(this, "WHAT THE RESULT MEANS"));
        content.addView(Ui.text(this,
                "Accessible volume counts probabilities strictly greater than tau. Tiny Zoe quantizes inputs to unsigned Q0.15 before measurement; quantization is an explicit representation change. A result is an observation, not correctness, belief, or permission to act.\n\n"
                        + "Nicholas Michael Kloster alone created the original equation on March 6, 2026.",
                15, Ui.TEXT));

        content.addView(Ui.section(this, "PRIVATE BY DEFAULT"));
        content.addView(Ui.text(this,
                "The home screen starts no sensors. Camera, microphone, location, Bluetooth, accessibility, and network features are separate and explicit. OCR and image labels are bundled. Optional model services and external apps follow their own permissions and behavior.\n\n"
                        + "Tiny Zoe uses no hardware, SIM, storage, or network. Sharing opens Android's chooser; Zoe does not upload the export or write it to a file.",
                15, Ui.TEXT));

        content.addView(Ui.section(this, "BUILD & VERIFY"));
        content.addView(Ui.text(this,
                "Android 8.0 or later · Java 17 · Android SDK 36\n"
                        + "Run host tests, lint, debug builds, and on-device instrumentation before release. Hardware-dependent observations and iOS source tests are not substitutes for device verification.",
                15, Ui.TEXT));
        Button source = Ui.button(this, "View source & full mobile guide", view -> openGuide());
        source.setId(R.id.research_source);
        content.addView(source);

        content.addView(Ui.section(this, "BEFORE A PUBLIC RELEASE"));
        content.addView(Ui.text(this,
                "Use production signing and a documented update path. Test supported devices, large text, screen readers, interrupted permissions, offline behavior, and lifecycle changes. Review third-party services and complete an independent security and accessibility review. Passing the included tests is necessary evidence, not a guarantee.",
                15, Ui.YELLOW));
        status = Ui.text(this, "Source opens only when you choose it.", 13, Ui.MUTED);
        status.setId(R.id.research_status);
        content.addView(status);
    }

    private String versionName() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (PackageManager.NameNotFoundException error) {
            return "unknown";
        }
    }

    private void openGuide() {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW,
                    Uri.parse("https://github.com/Ablation-Tool/zoe/blob/main/mobile/README.md")));
        } catch (ActivityNotFoundException error) {
            status.setText("No browser is available. The offline guide remains available here.");
        }
    }
}
