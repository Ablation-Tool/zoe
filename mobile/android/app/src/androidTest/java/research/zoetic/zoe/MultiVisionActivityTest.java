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
public class MultiVisionActivityTest {
    @Rule
    public ActivityScenarioRule<MultiVisionActivity> activity = new ActivityScenarioRule<>(MultiVisionActivity.class);

    @Test
    public void multiViewStartsIdleAndStopsCleanly() {
        onView(withId(R.id.multi_status)).check(matches(withText("Multi-view is off. Start all sources when ready.")));
        onView(withId(R.id.multi_stop)).perform(click());
        onView(withId(R.id.multi_status)).check(matches(withText("Multi-view stopped. Phone cameras are unbound.")));
    }
}
