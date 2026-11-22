package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class ElizaGemActivityTest {
    @Rule
    public ActivityScenarioRule<ElizaGemActivity> activity = new ActivityScenarioRule<>(ElizaGemActivity.class);

    @Test
    public void startsIdleWithOfflineChladniAndBronzeRoseMode() {
        onView(withId(R.id.eliza_status)).check(matches(withText(containsString("Studio idle"))));
        onView(withId(R.id.eliza_chladni_mode)).check(matches(withText("Plate: Square Atelier")));
        onView(withId(R.id.eliza_chladni_mode)).perform(scrollTo(), click());
        onView(withId(R.id.eliza_chladni_mode)).check(matches(withText("Plate: Bronze Rose Disc")));
    }

    @Test
    public void rejectsRemoteCleartextEndpointExplicitly() {
        onView(withId(R.id.eliza_endpoint)).perform(scrollTo(),
                androidx.test.espresso.action.ViewActions.replaceText("http://192.168.1.9:8765"));
        onView(withId(R.id.eliza_connect)).perform(scrollTo(), click());
        onView(withId(R.id.eliza_status)).check(matches(withText(containsString("Only loopback HTTP"))));
    }
}
