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

import androidx.test.core.app.ActivityScenario;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class CreativeLiveArcadeActivityTest {
    @Test
    public void zoeLiveStartsIdleWithCameraAndWebOff() {
        try (ActivityScenario<ZoeLiveActivity> scenario = ActivityScenario.launch(ZoeLiveActivity.class)) {
            onView(withId(R.id.live_orb_view)).check(matches(isDisplayed()));
            onView(withId(R.id.live_camera_toggle)).check(matches(withText("Camera: off")));
            onView(withId(R.id.live_hizoe_toggle)).check(matches(withText("Hi Zoe: off")));
            onView(withId(R.id.live_web_toggle)).check(matches(withText("Web: off")));
            onView(withId(R.id.live_web_toggle)).perform(click());
            onView(withId(R.id.live_web_toggle)).check(matches(withText("Web: on")));
            onView(withId(R.id.live_stop_button)).perform(click());
            onView(withId(R.id.live_state_badge)).check(matches(withText(containsString("MIC & CAMERA OFF"))));
        }
    }

    @Test
    public void creativeStudioAppliesNaturalLanguageImageEditsAndOpensVideoMaker() {
        try (ActivityScenario<CreativeStudioActivity> scenario = ActivityScenario.launch(CreativeStudioActivity.class)) {
            onView(withId(R.id.studio_image_preview)).check(matches(isDisplayed()));
            onView(withId(R.id.studio_command_input))
                    .perform(scrollTo(), replaceText("warm, rotate, blur, caption Pixel Test"), closeSoftKeyboard());
            onView(withId(R.id.studio_apply_cmd)).perform(scrollTo(), click());
            onView(withId(R.id.studio_edit_summary)).check(matches(withText(containsString("Atelier Warm"))));
            onView(withId(R.id.studio_edit_summary)).check(matches(withText(containsString("Pixel Test"))));

            onView(withId(R.id.studio_tab_video)).perform(click());
            onView(withId(R.id.studio_video_preview)).check(matches(isDisplayed()));
            onView(withId(R.id.studio_render_mp4)).perform(scrollTo());
            onView(withId(R.id.studio_render_mp4)).check(matches(isDisplayed()));
        }
    }

    @Test
    public void zoeArcadePlaysTicTacToeAndOpensAllFourOfflineGames() {
        try (ActivityScenario<ZoeArcadeActivity> scenario = ActivityScenario.launch(ZoeArcadeActivity.class)) {
            onView(withId(R.id.arcade_memory_start)).check(matches(isDisplayed()));
            onView(withId(R.id.arcade_tab_ttt)).perform(click());
            onView(withId(R.id.arcade_ttt_cell0)).perform(click());
            onView(withId(R.id.arcade_ttt_cell0)).check(matches(withText("X")));
            onView(withId(R.id.arcade_tab_signal)).perform(click());
            onView(withText(containsString("Check Signal Lock"))).check(matches(isDisplayed()));
            onView(withId(R.id.arcade_tab_20q)).perform(click());
            onView(withText("Is it alive?")).perform(click());
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
