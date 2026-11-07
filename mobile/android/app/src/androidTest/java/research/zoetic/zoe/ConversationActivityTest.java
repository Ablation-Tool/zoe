package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;

import android.Manifest;

import androidx.test.ext.junit.rules.ActivityScenarioRule;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.rule.GrantPermissionRule;

import org.junit.Rule;
import org.junit.Test;
import org.junit.runner.RunWith;

@RunWith(AndroidJUnit4.class)
public class ConversationActivityTest {
    @Rule
    public ActivityScenarioRule<ConversationActivity> activity = new ActivityScenarioRule<>(ConversationActivity.class);

    @Rule
    public GrantPermissionRule permissions = GrantPermissionRule.grant(Manifest.permission.RECORD_AUDIO);

    @Test
    public void conversationCanStartAndAlwaysStops() {
        onView(withId(R.id.conversation_start)).perform(click());
        onView(withId(R.id.conversation_stop)).perform(click());
        onView(withId(R.id.conversation_status)).check(matches(withText("Conversation stopped. The microphone is off.")));
    }

    @Test
    public void installedEnglishVoicePickerIsAvailable() {
        onView(withId(R.id.conversation_voice)).check(matches(isDisplayed()));
    }

    @Test
    public void captionModeStartsSilentlyAndStops() {
        onView(withText("Caption mode: off")).perform(click());
        onView(withId(R.id.conversation_captions)).check(matches(withText("Caption mode: on")));
        onView(withId(R.id.conversation_start)).perform(click());
        onView(withId(R.id.conversation_stop)).perform(click());
        onView(withId(R.id.conversation_status)).check(matches(withText("Conversation stopped. The microphone is off.")));
    }
}
