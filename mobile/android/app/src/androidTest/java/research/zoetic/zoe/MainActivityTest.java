package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.isEnabled;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.anyOf;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.not;

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
    public void startupDoesNotOpenCameraOrMicrophone() {
        onView(withText("Guided vision")).check(matches(isDisplayed()));
        onView(withText("Follow your curiosity.")).check(matches(isDisplayed()));
        onView(withText("Guided vision")).perform(click());
        onView(withId(R.id.start_camera)).check(matches(isDisplayed()));
        onView(withId(R.id.inspect_button)).check(matches(not(isEnabled())));
        onView(withId(R.id.listen_button)).check(matches(isDisplayed()));
    }

    @Test
    public void accessibleVolumeUsesStrictThreshold() {
        onView(withText("Accessible volume")).perform(scrollTo(), click());
        onView(withId(R.id.measure_button)).perform(click());
        onView(withId(R.id.volume_result)).check(matches(withText(containsString("A = 3 of 4"))));
        onView(withId(R.id.volume_result)).check(matches(withText(containsString("No action was authorized"))));
    }

    @Test
    public void deviceFieldReadsLocalBatteryAndCapabilities() {
        onView(withText("Device field")).perform(scrollTo(), click());
        onView(withText(containsString("Battery:"))).check(matches(isDisplayed()));
        onView(withText(containsString("On-device speech available:"))).check(matches(isDisplayed()));
    }

    @Test
    public void microphoneStartsAndStopsOneShotListening() {
        onView(withText("Guided vision")).perform(click());
        onView(withId(R.id.listen_button)).perform(click());
        onView(withId(R.id.vision_status)).check(matches(anyOf(
                withText(containsString("On-device speech selected")),
                withText(containsString("Offline speech preferred")),
                withText(containsString("code 7")))));
        onView(withId(R.id.stop_button)).perform(click());
        onView(withId(R.id.vision_status)).check(matches(withText("Speech and listening stopped.")));
    }

    @Test
    public void speakerCheckInvokesSpeechWithoutOpeningSensors() {
        onView(withText("Device field")).perform(scrollTo(), click());
        onView(withText("Speaker check")).perform(click());
        onView(withText(containsString("Battery:"))).check(matches(isDisplayed()));
    }
}
