package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.anyOf;
import static org.hamcrest.Matchers.containsString;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class AppObservatoryActivityTest {
    @Rule
    public ActivityScenarioRule<AppObservatoryActivity> activity = new ActivityScenarioRule<>(AppObservatoryActivity.class);

    @Test
    public void packageInventoryIsReadOnly() {
        onView(withId(R.id.apps_status)).check(matches(anyOf(
                withText(containsString("launcher-visible")),
                withText("Package metadata inspected read-only."))));
        onView(withId(R.id.apps_report)).check(matches(withText(containsString("No private application data"))));
    }
}
