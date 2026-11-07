package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

import android.Manifest;
import android.os.Build;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.rule.GrantPermissionRule;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class RadioActivityTest {
    @Rule
    public ActivityScenarioRule<RadioActivity> activity = new ActivityScenarioRule<>(RadioActivity.class);

    @Rule
    public GrantPermissionRule permissions = Build.VERSION.SDK_INT >= 31
            ? GrantPermissionRule.grant(Manifest.permission.BLUETOOTH_CONNECT)
            : GrantPermissionRule.grant();

    @Test
    public void radioLabStopsConnectionsAndReaderMode() {
        onView(withId(R.id.radio_stop)).perform(click());
        onView(withId(R.id.radio_status)).check(matches(withText("Radio Lab stopped. No GATT connection or NFC reader is active.")));
    }
}
