package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
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
public class TripJournalActivityTest {
    @Rule
    public ActivityScenarioRule<TripJournalActivity> activity = new ActivityScenarioRule<>(TripJournalActivity.class);

    @Test
    public void startsWithoutUploadingOrSavingAutomatically() {
        onView(withId(R.id.journal_sync)).check(matches(isDisplayed()));
        onView(withId(R.id.journal_export)).check(matches(isDisplayed()));
        onView(withId(R.id.journal_status)).check(matches(anyOf(
                withText(containsString("No saved trip sightings")),
                withText(containsString("saved sighting")))));
    }
}
