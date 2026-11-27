package research.zoetic.zoe;

import static androidx.test.espresso.Espresso.onView;
import static androidx.test.espresso.action.ViewActions.click;
import static androidx.test.espresso.action.ViewActions.closeSoftKeyboard;
import static androidx.test.espresso.action.ViewActions.replaceText;
import static androidx.test.espresso.action.ViewActions.scrollTo;
import static androidx.test.espresso.assertion.ViewAssertions.doesNotExist;
import static androidx.test.espresso.assertion.ViewAssertions.matches;
import static androidx.test.espresso.matcher.ViewMatchers.isDisplayed;
import static androidx.test.espresso.matcher.ViewMatchers.withId;
import static androidx.test.espresso.matcher.ViewMatchers.withText;
import static org.hamcrest.Matchers.containsString;

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
    public void conversationCanStartAndAlwaysStopsWithCleanChrome() {
        onView(withText("Ask AI ↗")).check(doesNotExist());
        onView(withId(R.id.conversation_clear_btn)).check(matches(withText("Clear")));
        onView(withId(R.id.conversation_start)).perform(click());
        onView(withId(R.id.conversation_stop)).perform(click());
        onView(withId(R.id.conversation_status)).check(matches(withText("Conversation stopped · Microphone is off")));
    }

    @Test
    public void settingsSheetHoldsModeWebCaptionsAndVoiceCleanly() {
        onView(withId(R.id.conversation_brain_settings)).perform(click());
        onView(withId(R.id.conversation_mode_auto)).check(matches(isDisplayed()));
        onView(withId(R.id.conversation_web_toggle)).check(matches(withText("Web: Off")));
        onView(withId(R.id.conversation_web_toggle)).perform(click());
        onView(withId(R.id.conversation_web_toggle)).check(matches(withText("Web: On")));
        onView(withId(R.id.conversation_web_toggle)).perform(click());
        onView(withId(R.id.conversation_web_toggle)).check(matches(withText("Web: Off")));
        onView(withId(R.id.conversation_captions)).perform(scrollTo()).check(matches(withText("Caption Mode: Off")));
        onView(withId(R.id.conversation_captions)).perform(click());
        onView(withId(R.id.conversation_captions)).check(matches(withText("Caption Mode: On")));
        onView(withId(R.id.conversation_voice)).perform(scrollTo()).check(matches(isDisplayed()));
        onView(withText("Done")).perform(scrollTo(), click());
    }

    @Test
    public void typingPromptShowsActionBarAndClearResetsChatCleanly() {
        onView(withId(R.id.conversation_input)).perform(replaceText("navigate to Central Park and set a 5 minute timer"), closeSoftKeyboard());
        onView(withId(R.id.conversation_send)).perform(click());
        onView(withId(R.id.conversation_action_bar)).check(matches(isDisplayed()));
        onView(withId(R.id.conversation_action_btn)).check(matches(withText(containsString("Central Park"))));
        onView(withId(R.id.conversation_clear_btn)).perform(click());
        onView(withId(R.id.conversation_status)).check(matches(withText("Chat cleared")));
        onView(withText("Hi, I'm Zoe")).check(matches(isDisplayed()));
    }
}
