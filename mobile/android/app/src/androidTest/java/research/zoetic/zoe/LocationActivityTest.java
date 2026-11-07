package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.junit.Assert.assertNull;

import android.Manifest;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.rule.GrantPermissionRule;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class LocationActivityTest {
    @Rule
    public ActivityScenarioRule<LocationActivity> activity = new ActivityScenarioRule<>(LocationActivity.class);

    @Rule
    public GrantPermissionRule permissions = GrantPermissionRule.grant(
            Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION);

    @Test
    public void locationStartsIdleWithoutReadingCoordinates() {
        onView(withId(R.id.location_status)).check(matches(withText("Location is idle. No location request is active.")));
    }

    @Test
    public void stopCancelsThePendingPlatformRequest() {
        onView(withId(R.id.location_once)).perform(click());
        onView(withText("Stop and clear points")).perform(click());
        activity.getScenario().onActivity(activity -> assertNull(activity.pendingLocation));
        onView(withId(R.id.location_status)).check(matches(withText(
                "Location stopped. No points are retained and no location request is active.")));
    }
}
