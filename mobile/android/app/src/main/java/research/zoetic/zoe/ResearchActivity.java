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
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 28));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        content.addView(Ui.topBar(this, "Researcher guide", "How Zoe works & limits"));
        TextView version = Ui.statusBanner(this, "Zoe " + versionName() + " · research preview", Ui.GREEN);
        version.setId(R.id.research_version);
        content.addView(version);

        content.addView(Ui.section(this, "YOUR FIRST FIVE MINUTES"));
        TextView firstFive = Ui.text(this,
                "1. Open Accessible volume and measure the worked distribution.\n\n"
                        + "2. Open Tiny Zoe. Read the simulated card, measure once, then inspect the raw bytes.\n\n"
                        + "3. Try τ = 0.20 with the default distribution. Equality is excluded, so A = 1 of 4.\n\n"
                        + "4. Replay the last command — the bytes and result stay identical.",
                14.5f, Ui.TEXT);
        firstFive.setBackground(Ui.cardBackground(this, 20));
        firstFive.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        content.addView(firstFive);
        Button openCell = Ui.primaryButton(this, "Open Tiny Zoe", Ui.RUBY, view ->
                startActivity(new Intent(this, CellActivity.class)));
        openCell.setId(R.id.research_open_cell);
        LinearLayout.LayoutParams ocLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        ocLp.setMargins(0, Ui.dp(this, 10), 0, 0);
        content.addView(openCell, ocLp);

        content.addView(Ui.section(this, "What the result means"));
        TextView meaningCard = Ui.text(this,
                "Accessible volume counts probabilities strictly greater than τ. Tiny Zoe quantizes inputs to Q0.15 before measurement. A result is an observation, not proof or permission to act.\n\n"
                        + "Nicholas Michael Kloster alone created the original equation on March 6, 2026.",
                14.5f, Ui.TEXT);
        meaningCard.setBackground(Ui.cardBackground(this, 20));
        meaningCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        content.addView(meaningCard);

        content.addView(Ui.section(this, "Private by default"));
        TextView privacyCard = Ui.text(this,
                "Home starts no sensors. Camera, mic, GPS, Bluetooth, and network features only run when you tap. OCR, labels, and color analysis run offline.",
                14.5f, Ui.TEXT);
        privacyCard.setBackground(Ui.cardBackground(this, 20));
        privacyCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        content.addView(privacyCard);

        content.addView(Ui.section(this, "Build & Release Checklist"));
        TextView releaseCard = Ui.text(this,
                "Android 8.0+ · Java 17 · Android SDK 36.\n\n"
                        + "Before any public release: use production signing, verify on real hardware across large text & screen readers, and complete an independent security and accessibility review.",
                14f, Ui.MUTED);
        releaseCard.setBackground(Ui.cardBackground(this, 20));
        releaseCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        content.addView(releaseCard);

        Button source = Ui.button(this, "View source & mobile guide", view -> openGuide());
        source.setId(R.id.research_source);
        LinearLayout.LayoutParams srcLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        srcLp.setMargins(0, Ui.dp(this, 10), 0, 0);
        content.addView(source, srcLp);

        status = Ui.text(this, "Source opens only when you choose it.", 13, Ui.MUTED);
        status.setId(R.id.research_status);
        status.setGravity(android.view.Gravity.CENTER);
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
