package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;
import static org.junit.Assert.assertEquals;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class TrinityActivityTest {
    @Rule
    public ActivityScenarioRule<TrinityActivity> activity = new ActivityScenarioRule<>(TrinityActivity.class);

    @Test
    public void trinityStartsIdleAndMeasureDoesNotAttemptNetwork() {
        onView(withId(R.id.trinity_status)).check(matches(withText(containsString("Trinity is off"))));
        onView(withId(R.id.trinity_measure)).perform(scrollTo(), click());
        onView(withId(R.id.trinity_status)).check(matches(withText(containsString("Nothing was sent"))));
    }

    @Test
    public void responseParserVerifiesBothPlanesAndApduWitness() throws Exception {
        String json = "{\"protocol\":1,\"name\":\"Zoe Trinity\",\"revision\":1,"
                + "\"creator\":\"Nicholas Michael Kloster alone, March 6, 2026\","
                + "\"active\":{\"probabilities\":[0.7,0.2,0.08,0.02],\"tau\":0.05,"
                + "\"zoe\":{\"accessible\":3,\"complement\":1,\"vocabularySize\":4},"
                + "\"tiny\":{\"probabilities\":[22938,6554,2621,655],\"tau\":1638,"
                + "\"accessible\":3,\"complement\":1,\"vocabularySize\":4,"
                + "\"request\":\"800200000A0666599A199A0A3D028F\",\"response\":\"00030001000406669000\"},"
                + "\"quantizationChanged\":false},\"memory\":{\"enabled\":false,\"records\":0,\"tamperEvidenceOnly\":true},"
                + "\"events\":[]}";
        TrinityClient.State state = TrinityClient.parseState(json);
        assertEquals(3, state.active.mobile.result().accessible);
        assertEquals(3, state.active.tiny.accessible);
        assertEquals("800200000A0666599A199A0A3D028F", state.active.tiny.request);
    }
}
