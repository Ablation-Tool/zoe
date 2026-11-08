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
        content.setPadding(0, Ui.dp(activity, 12), 0, Ui.dp(activity, 28));
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
        TextView title = Ui.text(activity, "Zoe", 32, Ui.CYAN);
        title.setTypeface(Typeface.create("sans", Typeface.BOLD));
        titles.addView(title);
        titles.addView(Ui.text(activity, "NuClide Research · PLACES", 12, Ui.MUTED));
        header.addView(titles);
        ImageView wordmark = new ImageView(activity);
        wordmark.setImageResource(R.drawable.nuclide_brain);
        wordmark.setAdjustViewBounds(true);
        wordmark.setContentDescription("NuClide Research dual-brain co-brand");
        header.addView(wordmark, new LinearLayout.LayoutParams(Ui.dp(activity, 88), Ui.dp(activity, 44)));
        content.addView(header);

        LinearLayout hero = Ui.vertical(activity);
        hero.setPadding(Ui.dp(activity, 22), Ui.dp(activity, 18), Ui.dp(activity, 22), Ui.dp(activity, 18));
        hero.setBackground(Ui.panelBackground(activity, Ui.CYAN, 28));
        TextView places = Ui.text(activity, "PLAY · LEARN · ADAPT · CREATE · EXPLORE · SHARE", 11, Ui.PINK);
        places.setLetterSpacing(0.08f);
        hero.addView(places);
        TextView invitation = Ui.text(activity, "Follow your curiosity.", 26, Ui.TEXT);
        invitation.setTypeface(Typeface.create("sans", Typeface.BOLD));
        hero.addView(invitation);
        hero.addView(Ui.text(activity,
                "Small observations. Strange ideas. Careful evidence.\nChoose one thing and see where it takes you.",
                15, Ui.MUTED));
        LinearLayout.LayoutParams heroMargins = Ui.margins(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT, activity, 16);
        content.addView(hero, heroMargins);
        TextView privacy = Ui.text(activity, "Nothing listens, watches, or measures from this screen.", 13, Ui.GREEN);
        privacy.setPadding(Ui.dp(activity, 24), 0, Ui.dp(activity, 20), Ui.dp(activity, 4));
        content.addView(privacy);

        content.addView(Ui.section(activity, "START HERE"));
        tool(content, "Guided vision", "Look, read, and describe · one frame at a time",
                android.R.drawable.ic_menu_camera, Ui.CYAN, view -> activity.showVision());
        tool(content, "Talk", "Conversation, captions, and a voice you choose",
                android.R.drawable.ic_btn_speak_now, Ui.PINK, view -> open(ConversationActivity.class));
        tool(content, "Accessible volume", "Create a small experiment with strict p > τ",
                android.R.drawable.ic_menu_sort_by_size, Ui.GREEN, view -> activity.showVolume());
        tool(content, "Trinity", "Tiny + mobile + laptop · one shared experiment",
                android.R.drawable.ic_menu_preferences, Ui.YELLOW, view -> open(TrinityActivity.class));

        content.addView(Ui.section(activity, "KEEP EXPLORING"));
        tool(content, "Field kit", "Cameras, sensors, radio, location, and device tools",
                android.R.drawable.ic_menu_gallery, Ui.CYAN, view -> open(FieldKitActivity.class));
        tool(content, "Device field", "Battery, capabilities, and comfort mode",
                android.R.drawable.ic_menu_info_details, Ui.GREEN, view -> activity.showDevice());
        tool(content, "SafeConvert", "Private, offline unit conversions",
                android.R.drawable.ic_menu_agenda, Ui.PINK, view -> open(SafeConvertActivity.class));
        tool(content, "Researcher guide", "Build, test, share, and understand the boundaries",
                android.R.drawable.ic_menu_edit, Ui.YELLOW, view -> open(ResearchActivity.class));

        TextView footer = Ui.text(activity, "ZOE · weird ideas, careful evidence, human review", 12, Ui.MUTED);
        footer.setGravity(Gravity.CENTER);
        footer.setPadding(Ui.dp(activity, 20), Ui.dp(activity, 22), Ui.dp(activity, 20), 0);
        content.addView(footer);
    }

    private void tool(LinearLayout content, String title, String subtitle, int icon, int accent,
                      View.OnClickListener listener) {
        content.addView(Ui.tool(getContext(), title, subtitle, icon, accent, listener));
    }

    private void open(Class<?> activityClass) {
        getContext().startActivity(new Intent(getContext(), activityClass));
    }
}
