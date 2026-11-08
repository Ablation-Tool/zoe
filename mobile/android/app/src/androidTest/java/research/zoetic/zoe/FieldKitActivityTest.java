package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class FieldKitActivityTest {
    @Rule
    public ActivityScenarioRule<FieldKitActivity> activity = new ActivityScenarioRule<>(FieldKitActivity.class);

    @Test
    public void specializedToolsStartAsAnIdleCatalog() {
        onView(withText("Field kit")).check(matches(isDisplayed()));
        onView(withText("Multi-view")).check(matches(isDisplayed()));
        onView(withText("Acoustic ranging")).check(matches(isDisplayed()));
        onView(withText(containsString("Each one starts idle"))).check(matches(isDisplayed()));
    }
}
