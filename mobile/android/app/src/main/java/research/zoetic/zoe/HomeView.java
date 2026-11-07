package research.zoetic.zoe;

import android.content.Intent;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.View;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

final class HomeView extends ScrollView {
    HomeView(MainActivity activity) {
        super(activity);
        setFillViewport(true);
        LinearLayout content = Ui.vertical(activity);
        content.setPadding(0, Ui.dp(activity, 12), 0, Ui.dp(activity, 24));
        addView(content);

        LinearLayout header = new LinearLayout(activity);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(Ui.dp(activity, 20), Ui.dp(activity, 8), Ui.dp(activity, 16), Ui.dp(activity, 8));
        ImageView emblem = new ImageView(activity);
        emblem.setImageResource(R.drawable.zoe_eye);
        emblem.setContentDescription("Zoe orbital eye");
        header.addView(emblem, new LinearLayout.LayoutParams(Ui.dp(activity, 68), Ui.dp(activity, 56)));
        LinearLayout titles = Ui.vertical(activity);
        titles.setLayoutParams(new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));
        TextView title = Ui.text(activity, "Zoe", 30, Ui.CYAN);
        title.setTypeface(Typeface.create("sans", Typeface.BOLD));
        titles.addView(title);
        titles.addView(Ui.text(activity, activity.getString(R.string.app_subtitle), 12, Ui.MUTED));
        header.addView(titles);
        ImageView wordmark = new ImageView(activity);
        wordmark.setImageResource(R.drawable.nuclide_brain);
        wordmark.setAdjustViewBounds(true);
        wordmark.setContentDescription("NuClide Research dual-brain co-brand");
        header.addView(wordmark, new LinearLayout.LayoutParams(Ui.dp(activity, 96), Ui.dp(activity, 44)));
        content.addView(header);
        TextView invitation = Ui.text(activity, "Small core. Thoughtful tools.", 18, Ui.TEXT);
        invitation.setPadding(Ui.dp(activity, 22), Ui.dp(activity, 8), Ui.dp(activity, 18), 0);
        content.addView(invitation);
        TextView privacy = Ui.text(activity, "Choose an app. Sensors stay off until you ask.", 14, Ui.MUTED);
        privacy.setPadding(Ui.dp(activity, 22), 0, Ui.dp(activity, 18), Ui.dp(activity, 8));
        content.addView(privacy);

        section(content, "Everyday");
        setting(content, "Guided vision", "Camera, text, labels & optional device AI",
                android.R.drawable.ic_menu_camera, view -> activity.showVision());
        setting(content, "Talk", "Conversation, captions & your chosen voice",
                android.R.drawable.ic_btn_speak_now, view -> open(ConversationActivity.class));
        setting(content, "Multi-view", "Phone back, front & laptop cameras",
                android.R.drawable.ic_menu_gallery, view -> open(MultiVisionActivity.class));
        setting(content, "SafeConvert", "Private unit converter",
                android.R.drawable.ic_menu_agenda, view -> open(SafeConvertActivity.class));

        section(content, "Little sister");
        setting(content, "Zoe Cell", "Native card-protocol simulator · no reader required",
                android.R.drawable.ic_menu_preferences, view -> open(CellActivity.class));

        section(content, "Measure & explore");
        setting(content, "Accessible volume", "Nicholas’s strict next-token measurement",
                android.R.drawable.ic_menu_sort_by_size, view -> activity.showVolume());
        setting(content, "Device field", "Battery, capabilities & comfort mode",
                android.R.drawable.ic_menu_info_details, view -> activity.showDevice());
        setting(content, "Acoustic ranging", "One-shot chirp & echo observations",
                android.R.drawable.ic_menu_call, view -> open(RangingActivity.class));
        setting(content, "Radio field", "Bonded Bluetooth & NFC presence",
                android.R.drawable.ic_menu_share, view -> open(RadioActivity.class));
        setting(content, "Location field", "One-shot position & distance",
                android.R.drawable.ic_menu_mylocation, view -> open(LocationActivity.class));
        setting(content, "Connectivity", "Network changes & optional rate check",
                android.R.drawable.ic_menu_rotate, view -> open(ConnectivityActivity.class));

        section(content, "Device tools");
        setting(content, "Screen Space", "Explicit captures & mapped gestures",
                android.R.drawable.ic_menu_crop, view -> open(ScreenSpaceActivity.class));
        setting(content, "App Observatory", "Read-only installed-app metadata",
                android.R.drawable.ic_menu_view, view -> open(AppObservatoryActivity.class));
    }

    private void open(Class<?> activityClass) {
        startActivity(new Intent(getContext(), activityClass));
    }

    private void startActivity(Intent intent) {
        getContext().startActivity(intent);
    }

    private void section(LinearLayout content, String label) {
        TextView section = Ui.text(getContext(), label, 14, Ui.PINK);
        section.setTypeface(Typeface.create("sans", Typeface.BOLD));
        section.setPadding(Ui.dp(getContext(), 24), Ui.dp(getContext(), 14),
                Ui.dp(getContext(), 16), Ui.dp(getContext(), 5));
        content.addView(section);
    }

    private void setting(LinearLayout content, String title, String subtitle, int icon,
                         View.OnClickListener listener) {
        MainActivity activity = (MainActivity) getContext();
        LinearLayout row = new LinearLayout(activity);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setOrientation(LinearLayout.HORIZONTAL);
        row.setMinimumHeight(Ui.dp(activity, 76));
        row.setPadding(Ui.dp(activity, 14), Ui.dp(activity, 8),
                Ui.dp(activity, 12), Ui.dp(activity, 8));
        row.setBackground(Ui.panelBackground(activity, Ui.PANEL, 18));
        row.setClickable(true);
        row.setFocusable(true);
        row.setContentDescription(title + ". " + subtitle);
        row.setOnClickListener(listener);

        ImageView symbol = new ImageView(activity);
        symbol.setImageResource(icon);
        symbol.setColorFilter(Ui.CYAN);
        symbol.setPadding(Ui.dp(activity, 9), Ui.dp(activity, 9),
                Ui.dp(activity, 9), Ui.dp(activity, 9));
        symbol.setBackground(Ui.panelBackground(activity, Ui.CYAN, 24));
        symbol.setContentDescription(null);
        row.addView(symbol, new LinearLayout.LayoutParams(Ui.dp(activity, 44), Ui.dp(activity, 44)));

        LinearLayout labels = Ui.vertical(activity);
        labels.setPadding(Ui.dp(activity, 14), 0, Ui.dp(activity, 6), 0);
        TextView titleView = Ui.text(activity, title, 17, Ui.TEXT);
        titleView.setTypeface(Typeface.create("sans", Typeface.BOLD));
        labels.addView(titleView);
        labels.addView(Ui.text(activity, subtitle, 12, Ui.MUTED));
        row.addView(labels, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));

        TextView chevron = Ui.text(activity, "›", 28, Ui.MUTED);
        chevron.setGravity(Gravity.CENTER);
        chevron.setContentDescription(null);
        row.addView(chevron, new LinearLayout.LayoutParams(Ui.dp(activity, 24), Ui.dp(activity, 44)));
        LinearLayout.LayoutParams margins = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        margins.setMargins(Ui.dp(activity, 14), Ui.dp(activity, 4), Ui.dp(activity, 14), Ui.dp(activity, 4));
        content.addView(row, margins);
    }
}
