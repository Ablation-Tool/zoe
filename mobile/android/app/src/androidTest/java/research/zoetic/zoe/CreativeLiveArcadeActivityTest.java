package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.closeSoftKeyboard;
import static androidx.test.espresso.action.ViewActions.replaceText;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class CreativeLiveArcadeActivityTest {
    @Test
    public void zoeLiveStartsIdleWithMinimalChromeAndAccessibleModes() {
        try (ActivityScenario<ZoeLiveActivity> scenario = ActivityScenario.launch(ZoeLiveActivity.class)) {
            // Minimal clean initial stage: Orb + AR + Talk + End + Tools gear; drawer starts closed!
            onView(withId(R.id.live_orb_view)).check(matches(isDisplayed()));
            onView(withId(R.id.live_ar_toggle)).check(matches(isDisplayed()));
            onView(withId(R.id.live_talk_button)).check(matches(isDisplayed()));
            onView(withId(R.id.live_tools_button)).check(matches(isDisplayed()));
            onView(withId(R.id.live_tools_sheet)).check(matches(not(isDisplayed())));

            // Open Tools & Accessibility sheet and verify Deaf / HoH, Blind / Audio, Kid Mode, Web & Field defaults
            onView(withId(R.id.live_tools_button)).perform(click());
            onView(withId(R.id.live_tools_sheet)).check(matches(isDisplayed()));
            onView(withId(R.id.live_camera_toggle)).perform(scrollTo()).check(matches(withText("Camera: off")));
            onView(withId(R.id.live_field_toggle)).perform(scrollTo()).check(matches(withText("Field: off")));
            onView(withId(R.id.live_hizoe_toggle)).perform(scrollTo()).check(matches(withText("Hi Zoe: off")));
            onView(withId(R.id.live_web_toggle)).perform(scrollTo()).check(matches(withText("Web: off")));
            onView(withId(R.id.live_web_toggle)).perform(click());
            onView(withId(R.id.live_web_toggle)).check(matches(withText("Web: on")));

            // Verify Deaf / HoH + Blind / Audio + Kid Mode accessibility toggles work cleanly
            onView(withId(R.id.live_a11y_deaf)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_kid)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_kid)).check(matches(withText("Kid Mode: on")));
            onView(withId(R.id.live_a11y_blind)).perform(scrollTo(), click());
            // Reset cleanly back to Standard (Kid off) before closing drawer
            onView(withId(R.id.live_a11y_kid)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_standard)).perform(scrollTo(), click());

            // Close drawer and verify End kill-switch reports MIC & CAMERA OFF
            onView(withText("Done")).perform(scrollTo(), click());
            onView(withId(R.id.live_stop_button)).perform(click());
            onView(withId(R.id.live_state_badge)).check(matches(withText(containsString("MIC & CAMERA OFF"))));
        }
    }

    @Test
    public void creativeStudioAppliesNaturalLanguageImageEditsAndOpensVideoMaker() {
        try (ActivityScenario<CreativeStudioActivity> scenario = ActivityScenario.launch(CreativeStudioActivity.class)) {
            onView(withId(R.id.studio_image_preview)).check(matches(isDisplayed()));
            onView(withId(R.id.studio_baseline_haeckel)).perform(scrollTo(), click());
            onView(withId(R.id.studio_baseline_meta)).check(matches(withText(containsString("Kunstformen der Natur"))));
            onView(withId(R.id.studio_baseline_patent)).perform(scrollTo(), click());
            onView(withId(R.id.studio_baseline_meta)).check(matches(withText(containsString("patents.google.com"))));
            onView(withId(R.id.studio_baseline_chladni)).perform(scrollTo(), click());
            onView(withId(R.id.studio_baseline_meta)).check(matches(withText(containsString("Chladni"))));
            onView(withId(R.id.studio_baseline_phyllotaxis)).perform(scrollTo(), click());
            onView(withId(R.id.studio_baseline_meta)).check(matches(withText(containsString("137.508"))));
            onView(withId(R.id.studio_baseline_voronoi)).perform(scrollTo(), click());
            onView(withId(R.id.studio_baseline_meta)).check(matches(withText(containsString("Voronoi"))));
            onView(withId(R.id.studio_baseline_lissajous)).perform(scrollTo(), click());
            onView(withId(R.id.studio_baseline_meta)).check(matches(withText(containsString("Lissajous"))));
            onView(withId(R.id.studio_draw_toggle)).perform(scrollTo(), click());
            onView(withId(R.id.studio_draw_toggle)).check(matches(withText(containsString("Drawing"))));
            onView(withId(R.id.studio_draw_toggle)).perform(click());

            onView(withId(R.id.studio_command_input))
                    .perform(scrollTo(), replaceText("warm, rotate, blur, vignette, caption Pixel Test"), closeSoftKeyboard());
            onView(withId(R.id.studio_apply_cmd)).perform(scrollTo(), click());
            onView(withId(R.id.studio_edit_summary)).check(matches(withText(containsString("Atelier Warm"))));
            onView(withId(R.id.studio_edit_summary)).check(matches(withText(containsString("Pixel Test"))));
            onView(withId(R.id.studio_undo_btn)).perform(scrollTo(), click());
            onView(withId(R.id.studio_edit_summary)).check(matches(withText("Original")));

            onView(withId(R.id.studio_tab_video)).perform(click());
            onView(withId(R.id.studio_video_preview)).perform(scrollTo()).check(matches(isDisplayed()));
            onView(withId(R.id.studio_video_play_toggle)).perform(scrollTo(), click());
            onView(withId(R.id.studio_video_play_toggle)).check(matches(withText(containsString("Pause"))));
            onView(withId(R.id.studio_video_play_toggle)).perform(click());
            onView(withId(R.id.studio_render_mp4)).perform(scrollTo());
            onView(withId(R.id.studio_render_mp4)).check(matches(isDisplayed()));
        }
    }

    @Test
    public void zoeArcadePlaysTicTacToeAndOpensAllFourOfflineGames() {
        try (ActivityScenario<ZoeArcadeActivity> scenario = ActivityScenario.launch(ZoeArcadeActivity.class)) {
            onView(withId(R.id.arcade_memory_start)).perform(scrollTo()).check(matches(isDisplayed()));
            onView(withId(R.id.arcade_tab_ttt)).perform(click());
            onView(withId(R.id.arcade_ttt_cell0)).perform(scrollTo(), click());
            onView(withId(R.id.arcade_ttt_cell0)).check(matches(withText("X")));
            onView(withId(R.id.arcade_tab_signal)).perform(click());
            onView(withText(containsString("Check Signal Lock"))).perform(scrollTo()).check(matches(isDisplayed()));
            onView(withId(R.id.arcade_tab_20q)).perform(click());
            onView(withText("Is it alive?")).perform(scrollTo(), click());
            onView(withId(R.id.arcade_status)).check(matches(withText(containsString("Question 1"))));
        }
    }

    @Test
    public void privacyVaultComputesSafetyNumberAndSealsUnsealsE2eeEnvelope() {
        try (ActivityScenario<PrivacyVaultActivity> scenario = ActivityScenario.launch(PrivacyVaultActivity.class)) {
            onView(withId(R.id.vault_safety_number)).check(matches(isDisplayed()));
            onView(withId(R.id.vault_message_input))
                    .perform(scrollTo(), replaceText("Secret Signal-grade note"), closeSoftKeyboard());
            onView(withId(R.id.vault_seal_btn)).perform(scrollTo(), click());
            onView(withId(R.id.vault_output)).check(matches(withText(containsString("ZOE-SIGNAL-V1:"))));
            onView(withId(R.id.vault_message_input)).perform(scrollTo(), replaceText(""), closeSoftKeyboard());
            onView(withId(R.id.vault_unseal_btn)).perform(scrollTo(), click());
            onView(withId(R.id.vault_output)).check(matches(withText("Secret Signal-grade note")));
        }
    }
}
