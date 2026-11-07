package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Assume;
import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class ScreenSpaceActivityTest {
    @Rule
    public ActivityScenarioRule<ScreenSpaceActivity> activity = new ActivityScenarioRule<>(ScreenSpaceActivity.class);

    @Test
    public void disabledServiceCannotCaptureOrGesture() {
        Assume.assumeFalse(ZoeAccessibilityService.isReady());
        onView(withId(R.id.space_capture)).perform(click());
        onView(withId(R.id.space_status)).check(matches(withText("Enable the service first. No screen was captured.")));
    }
}
