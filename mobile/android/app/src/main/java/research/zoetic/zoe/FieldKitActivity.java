package research.zoetic.zoe;

import android.content.Intent;
import android.os.Bundle;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

public final class FieldKitActivity extends ComponentActivity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(0, Ui.dp(this, 8), 0, Ui.dp(this, 28));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        LinearLayout headerPad = new LinearLayout(this);
        headerPad.setOrientation(LinearLayout.VERTICAL);
        headerPad.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        headerPad.setPadding(Ui.dp(this, 16), 0, Ui.dp(this, 16), 0);
        headerPad.addView(Ui.topBar(this, "Field kit", "Each one starts idle"));
        content.addView(headerPad);

        content.addView(Ui.section(this, "Look & listen"));
        addGroup(content,
                row("Multi-view", "Back, front & laptop", R.drawable.ic_zoe_vision, Ui.COBALT, MultiVisionActivity.class),
                row("Acoustic ranging", "One-shot chirp & echo", R.drawable.ic_zoe_talk, Ui.RUBY, RangingActivity.class));

        content.addView(Ui.section(this, "Measure"));
        addGroup(content,
                row("Tiny Zoe", "Protocol simulator", R.drawable.ic_zoe_gem, Ui.GOLD, CellActivity.class),
                row("Radio field", "Bluetooth & NFC", R.drawable.ic_zoe_radio, Ui.GREEN, RadioActivity.class),
                row("Location field", "One-shot GPS", R.drawable.ic_zoe_location, Ui.GOLD, LocationActivity.class),
                row("Connectivity", "Link & speed test", R.drawable.ic_zoe_trinity, Ui.CYAN, ConnectivityActivity.class));

        content.addView(Ui.section(this, "Device tools"));
        addGroup(content,
                row("Screen Space", "Capture & gestures", R.drawable.ic_zoe_screen, Ui.PINK, ScreenSpaceActivity.class),
                row("App Observatory", "Installed apps", R.drawable.ic_zoe_apps, Ui.GREEN, AppObservatoryActivity.class));

        TextView note = Ui.text(this, "Observations are not proof.", 12.5f, Ui.MUTED);
        note.setAlpha(0.75f);
        note.setGravity(android.view.Gravity.CENTER);
        note.setPadding(Ui.dp(this, 20), Ui.dp(this, 16), Ui.dp(this, 20), 0);
        content.addView(note);
    }

    private LinearLayout row(String title, String subtitle, int icon, int accent, Class<?> activityClass) {
        return Ui.groupedRow(this, title, subtitle, icon, accent,
                view -> startActivity(new Intent(this, activityClass)));
    }

    private void addGroup(LinearLayout content, LinearLayout... rows) {
        LinearLayout card = Ui.groupedCard(this);
        for (int i = 0; i < rows.length; i++) {
            if (i > 0) {
                card.addView(Ui.insetDivider(this));
            }
            card.addView(rows[i]);
        }
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.setMargins(Ui.dp(this, 16), 0, Ui.dp(this, 16), 0);
        content.addView(card, params);
    }
}
