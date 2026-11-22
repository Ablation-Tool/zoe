package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;
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

    @Test
    public void mapsAndPersonalSafetyControlsRenderAndLiveToggleStopsCleanly() {
        onView(withId(R.id.maps_navigate_btn)).perform(scrollTo()).check(matches(isDisplayed()));
        onView(withId(R.id.maps_search_btn)).perform(scrollTo()).check(matches(isDisplayed()));
        onView(withId(R.id.safety_open_app_btn)).perform(scrollTo()).check(matches(isDisplayed()));
        onView(withId(R.id.safety_torch_btn)).perform(scrollTo()).check(matches(isDisplayed()));

        onView(withId(R.id.location_live_toggle)).perform(scrollTo(), click());
        onView(withText("Stop and clear points")).perform(scrollTo(), click());
        onView(withId(R.id.location_status)).check(matches(withText(containsString("Location stopped."))));
    }
}
