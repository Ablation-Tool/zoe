package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.replaceText;
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

import java.util.concurrent.atomic.AtomicReference;

@RunWith(AndroidJUnit4.class)
public class CellActivityTest {
    @Rule
    public ActivityScenarioRule<CellActivity> activity = new ActivityScenarioRule<>(CellActivity.class);

    @Test
    public void simulatorStartsWithoutHardwareOrSimAccess() {
        onView(withId(R.id.cell_status)).check(matches(withText(
                "Simulator idle. No hardware, SIM, or network access.")));
        onView(withId(R.id.cell_budget)).check(matches(withText(containsString("1,900,000"))));
    }

    @Test
    public void informationUsesRealProtocolResponses() {
        onView(withId(R.id.cell_info)).perform(scrollTo(), click());
        onView(withId(R.id.cell_report)).check(matches(withText(containsString("ZOE/NUCLIDE"))));
        onView(withId(R.id.cell_report)).check(matches(withText(containsString("0x9000"))));
    }

    @Test
    public void measurementExcludesThresholdEquality() {
        onView(withId(R.id.cell_threshold)).perform(scrollTo(), replaceText("0.20"));
        onView(withId(R.id.cell_measure)).perform(scrollTo(), click());
        onView(withId(R.id.cell_report)).check(matches(withText(containsString("A = 1 of 4"))));
        onView(withId(R.id.cell_report)).check(matches(withText(containsString("APDU request: 15 bytes"))));
        onView(withId(R.id.cell_report)).check(matches(withText(containsString("no action authorized"))));
    }

    @Test
    public void malformedHexCannotCreateATransaction() {
        onView(withId(R.id.cell_raw)).perform(scrollTo(), replaceText("GG"));
        onView(withId(R.id.cell_send)).perform(scrollTo(), click());
        onView(withId(R.id.cell_status)).check(matches(withText(containsString("non-hexadecimal"))));
        onView(withId(R.id.cell_history)).check(matches(withText("No transactions in this session.")));
    }

    @Test
    public void errorsAreInspectableAndReplayUsesIdenticalBytes() {
        onView(withId(R.id.cell_raw)).perform(scrollTo(), replaceText("80020000"));
        onView(withId(R.id.cell_send)).perform(scrollTo(), click());
        onView(withId(R.id.cell_report)).check(matches(withText(containsString("0x6700"))));
        onView(withId(R.id.cell_history)).check(matches(withText(containsString("#1"))));
        onView(withId(R.id.cell_raw)).perform(scrollTo(), replaceText("80010000"));
        onView(withId(R.id.cell_send)).perform(scrollTo(), click());
        onView(withId(R.id.cell_history)).check(matches(withText(containsString("#2"))));
        AtomicReference<String> before = new AtomicReference<>();
        activity.getScenario().onActivity(activity -> before.set(
                ((android.widget.TextView) activity.findViewById(R.id.cell_report)).getText().toString()));
        onView(withId(R.id.cell_replay)).perform(scrollTo(), click());
        onView(withId(R.id.cell_history)).check(matches(withText(containsString("#3"))));
        activity.getScenario().onActivity(activity -> assertEquals(before.get(),
                ((android.widget.TextView) activity.findViewById(R.id.cell_report)).getText().toString()));
    }

    @Test
    public void resetClearsHistoryAndPreventsEmptyReplay() {
        onView(withId(R.id.cell_info)).perform(scrollTo(), click());
        onView(withId(R.id.cell_reset)).perform(scrollTo(), click());
        onView(withId(R.id.cell_history)).check(matches(withText("No transactions in this session.")));
        onView(withId(R.id.cell_replay)).perform(scrollTo(), click());
        onView(withId(R.id.cell_status)).check(matches(withText(
                "No transaction to replay. Session is empty.")));
    }

    @Test
    public void emptySessionCannotOpenAnExport() {
        onView(withId(R.id.cell_share)).perform(scrollTo(), click());
        onView(withId(R.id.cell_status)).check(matches(withText(
                "Nothing to share yet. Read or measure on the simulated card first.")));
        onView(withId(R.id.cell_history)).check(matches(withText("No transactions in this session.")));
    }

    @Test
    public void oversizedProbabilityTextIsRejectedBeforeParsing() {
        onView(withId(R.id.cell_probabilities)).perform(scrollTo(), replaceText("1".repeat(4097)));
        onView(withId(R.id.cell_measure)).perform(scrollTo(), click());
        onView(withId(R.id.cell_status)).check(matches(withText(containsString("4096 characters"))));
        onView(withId(R.id.cell_history)).check(matches(withText("No transactions in this session.")));
    }
}
