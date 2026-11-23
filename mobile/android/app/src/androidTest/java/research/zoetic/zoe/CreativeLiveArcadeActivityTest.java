package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
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
    public void zoeLiveStartsCleanLowercaseWithAccessibleModes() {
        try (ActivityScenario<ZoeLiveActivity> scenario = ActivityScenario.launch(ZoeLiveActivity.class)) {
            onView(withId(R.id.live_orb_view)).check(matches(isDisplayed()));
            onView(withId(R.id.live_ar_toggle)).check(matches(withText("focus")));
            onView(withId(R.id.live_talk_button)).check(matches(withText("talk")));
            onView(withId(R.id.live_tools_button)).check(matches(isDisplayed()));
            onView(withId(R.id.live_tools_sheet)).check(matches(not(isDisplayed())));

            onView(withId(R.id.live_tools_button)).perform(click());
            onView(withId(R.id.live_tools_sheet)).check(matches(isDisplayed()));
            onView(withId(R.id.live_camera_toggle)).perform(scrollTo()).check(matches(withText("camera: off")));
            onView(withId(R.id.live_field_toggle)).perform(scrollTo()).check(matches(withText("field: off")));
            onView(withId(R.id.live_hizoe_toggle)).perform(scrollTo()).check(matches(withText("hi zoe: off")));
            onView(withId(R.id.live_web_toggle)).perform(scrollTo()).check(matches(withText("web: off")));
            onView(withId(R.id.live_web_toggle)).perform(click());
            onView(withId(R.id.live_web_toggle)).check(matches(withText("web: on")));

            onView(withId(R.id.live_a11y_deaf)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_kid)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_kid)).check(matches(withText("kid mode: on")));
            onView(withId(R.id.live_a11y_blind)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_kid)).perform(scrollTo(), click());
            onView(withId(R.id.live_a11y_standard)).perform(scrollTo(), click());

            onView(withText("done")).perform(scrollTo(), click());
            onView(withId(R.id.live_stop_button)).perform(click());
            onView(withId(R.id.live_state_badge)).check(matches(withText(containsString("mic & camera off"))));
        }
    }

    @Test
    public void dorothyBrainObservatoryLaunchesOfflineWebGlCleanly() {
        try (ActivityScenario<BrainObservatoryActivity> scenario = ActivityScenario.launch(BrainObservatoryActivity.class)) {
            onView(withText("Dorothy 3d brain")).check(matches(isDisplayed()));
        }
    }
}
