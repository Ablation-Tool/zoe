package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.isEnabled;
import static androidx.test.espresso.matcher.ViewMatchers.withContentDescription;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.anyOf;
import static org.hamcrest.Matchers.containsString;

import android.Manifest;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.rule.GrantPermissionRule;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class MainActivityTest {
    @Rule
    public ActivityScenarioRule<MainActivity> activity = new ActivityScenarioRule<>(MainActivity.class);

    @Rule
    public GrantPermissionRule permissions = GrantPermissionRule.grant(
            Manifest.permission.CAMERA, Manifest.permission.RECORD_AUDIO);

    @Test
    public void startupShowsPureLowercaseCanvasAndSeamlessNativeCameraVision() {
        onView(withText("Hi, I'm Zoe")).check(matches(isDisplayed()));
        onView(withId(R.id.home_dorothy_centerpiece)).check(matches(isDisplayed()));
        onView(withId(R.id.home_open_brain_btn)).check(matches(isDisplayed()));
        onView(withText("Ask Zoe")).check(matches(isDisplayed()));
        onView(withContentDescription("Open camera to look and read")).perform(click());
        onView(withId(R.id.start_camera)).perform(scrollTo()).check(matches(withText("Take Photo")));
        onView(withId(R.id.inspect_button)).perform(scrollTo()).check(matches(isEnabled()));
        onView(withId(R.id.vision_gallery_button)).perform(scrollTo()).check(matches(withText("Gallery")));
        onView(withId(R.id.listen_button)).perform(scrollTo()).check(matches(withText("Voice")));
    }

    @Test
    public void microphoneStartsAndStopsOneShotListening() {
        onView(withContentDescription("Open camera to look and read")).perform(click());
        onView(withId(R.id.listen_button)).perform(scrollTo(), click());
        onView(withId(R.id.vision_status)).perform(scrollTo()).check(matches(anyOf(
                withText(containsString("On-device speech selected")),
                withText(containsString("Offline speech preferred")),
                withText(containsString("code 7")))));
        onView(withId(R.id.stop_button)).perform(scrollTo(), click());
        onView(withId(R.id.vision_status)).perform(scrollTo()).check(matches(withText("Speech and listening stopped")));
    }

    @Test
    public void tappingGemLogoReturnsToZoeHome() {
        onView(withContentDescription("Open camera to look and read")).perform(click());
        onView(withId(R.id.zoe_gem_home)).perform(click());
        onView(withText("Hi, I'm Zoe")).check(matches(isDisplayed()));
    }
}
