package research.zoetic.zoe;

import android.content.Intent;
import android.os.Bundle;
import android.widget.LinearLayout;
import android.widget.ScrollView;

import androidx.activity.ComponentActivity;

public final class FieldKitActivity extends ComponentActivity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        LinearLayout content = Ui.vertical(this);
        content.setPadding(0, Ui.dp(this, 12), 0, Ui.dp(this, 28));
        scroll.addView(content);
        setContentView(scroll);

        content.addView(Ui.button(this, "‹ Zoe home", view -> finish()));
        content.addView(Ui.heading(this, "Field kit"));
        content.addView(Ui.text(this,
                "Specialized instruments for deliberate experiments. Each one starts idle and explains its own limits.",
                15, Ui.MUTED));
        content.addView(Ui.section(this, "LOOK & LISTEN"));
        tool(content, "Multi-view", "Phone back, front, and an optional localhost laptop camera",
                android.R.drawable.ic_menu_gallery, Ui.CYAN, MultiVisionActivity.class);
        tool(content, "Acoustic ranging", "One-shot chirp and uncalibrated echo candidates",
                android.R.drawable.ic_menu_call, Ui.PINK, RangingActivity.class);
        content.addView(Ui.section(this, "MEASURE"));
        tool(content, "Tiny Zoe", "Standalone Zoe Cell protocol simulator and APDU console",
                android.R.drawable.ic_menu_preferences, Ui.YELLOW, CellActivity.class);
        tool(content, "Radio field", "Bonded Bluetooth metadata, optional RSSI, and NFC presence",
                android.R.drawable.ic_menu_share, Ui.GREEN, RadioActivity.class);
        tool(content, "Location field", "One-shot position with cancel, timeout, and clear",
                android.R.drawable.ic_menu_mylocation, Ui.YELLOW, LocationActivity.class);
        tool(content, "Connectivity", "Transport changes and an optional HTTPS rate check",
                android.R.drawable.ic_menu_rotate, Ui.CYAN, ConnectivityActivity.class);
        content.addView(Ui.section(this, "DEVICE TOOLS"));
        tool(content, "Screen Space", "Explicit captures and mapped gestures · accessibility setup required",
                android.R.drawable.ic_menu_crop, Ui.PINK, ScreenSpaceActivity.class);
        tool(content, "App Observatory", "Read-only metadata for launcher-visible apps",
                android.R.drawable.ic_menu_view, Ui.GREEN, AppObservatoryActivity.class);
        content.addView(Ui.text(this,
                "Observations are not proof of identity, safe navigation, position, or correctness.",
                13, Ui.MUTED));
    }

    private void tool(LinearLayout content, String title, String subtitle, int icon, int accent,
                      Class<?> activityClass) {
        content.addView(Ui.tool(this, title, subtitle, icon, accent,
                view -> startActivity(new Intent(this, activityClass))));
    }
}
