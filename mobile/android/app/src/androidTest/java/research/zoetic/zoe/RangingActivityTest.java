package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class RangingActivityTest {
    @Rule
    public ActivityScenarioRule<RangingActivity> activity = new ActivityScenarioRule<>(RangingActivity.class);

    @Test
    public void rangingStartsIdleAndStopsCleanly() {
        onView(withId(R.id.range_status)).check(matches(withText("Microphone, speaker, and motion telemetry are idle.")));
        onView(withId(R.id.range_stop)).perform(click());
        onView(withId(R.id.range_status)).check(matches(withText("Acoustic Lab stopped. Microphone, speaker, and motion telemetry are idle.")));
    }
}
