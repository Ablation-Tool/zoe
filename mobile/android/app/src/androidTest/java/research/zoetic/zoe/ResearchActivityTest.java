package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class ResearchActivityTest {
    @Rule
    public ActivityScenarioRule<ResearchActivity> activity = new ActivityScenarioRule<>(ResearchActivity.class);

    @Test
    public void guideIsOfflineTruthfulAndLeadsToTinyZoe() {
        onView(withId(R.id.research_version)).check(matches(withText(containsString("research preview"))));
        onView(withText(containsString("YOUR FIRST FIVE MINUTES"))).check(matches(isDisplayed()));
        onView(withId(R.id.research_open_cell)).perform(scrollTo(), click());
        onView(withId(R.id.cell_status)).check(matches(withText(containsString("No hardware"))));
    }

    @Test
    public void releaseChecklistDoesNotClaimPerfectSafety() {
        onView(withText(containsString("independent security and accessibility review")))
                .perform(scrollTo())
                .check(matches(isDisplayed()));
        onView(withId(R.id.research_status)).check(matches(withText(containsString("only when you choose"))));
    }
}
