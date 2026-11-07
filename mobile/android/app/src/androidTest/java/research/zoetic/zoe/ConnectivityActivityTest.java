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
public class ConnectivityActivityTest {
    @Rule
    public ActivityScenarioRule<ConnectivityActivity> activity = new ActivityScenarioRule<>(ConnectivityActivity.class);

    @Test
    public void observationStartsAndStopsWithoutADefaultDownload() {
        onView(withId(R.id.network_status)).check(matches(withText("Network observation is idle. No callback or download is active.")));
        onView(withText("Stop observation")).perform(click());
        onView(withId(R.id.network_status)).check(matches(withText("Connectivity observation stopped. No callback or download is active.")));
    }
}
