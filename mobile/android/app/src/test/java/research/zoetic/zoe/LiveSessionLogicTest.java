package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class LiveSessionLogicTest {
    @Test
    public void silenceAndNoMatchSilentlyRearmWithoutKillingLiveCall() {
        LiveSessionLogic.ErrorPolicy p7 = LiveSessionLogic.classifySpeechError(LiveSessionLogic.ERR_NO_MATCH);
        LiveSessionLogic.ErrorPolicy p6 = LiveSessionLogic.classifySpeechError(LiveSessionLogic.ERR_SPEECH_TIMEOUT);
        assertEquals(LiveSessionLogic.RecoveryAction.SILENT_REARM, p7.action);
        assertEquals(LiveSessionLogic.RecoveryAction.SILENT_REARM, p6.action);
        assertTrue(p7.delayMs >= 200L);
        assertEquals("", p7.userMessage);
    }

    @Test
    public void busyAndClientErrorsResetRecognizerCleanlyAndPermissionIsFatal() {
        assertEquals(LiveSessionLogic.RecoveryAction.RESET_AND_RETRY,
                LiveSessionLogic.classifySpeechError(LiveSessionLogic.ERR_RECOGNIZER_BUSY).action);
        assertEquals(LiveSessionLogic.RecoveryAction.RESET_AND_RETRY,
                LiveSessionLogic.classifySpeechError(LiveSessionLogic.ERR_CLIENT).action);
        assertEquals(LiveSessionLogic.RecoveryAction.FALLBACK_RECOGNIZER,
                LiveSessionLogic.classifySpeechError(LiveSessionLogic.ERR_LANGUAGE_UNAVAILABLE).action);
        LiveSessionLogic.ErrorPolicy perm = LiveSessionLogic.classifySpeechError(LiveSessionLogic.ERR_INSUFFICIENT_PERMISSIONS);
        assertEquals(LiveSessionLogic.RecoveryAction.FATAL_PERMISSION, perm.action);
        assertTrue(perm.userMessage.contains("Microphone permission"));
    }

    @Test
    public void sanitizeForSpeechRemovesMarkdownAndUrlsCleanly() {
        String cleaned = LiveSessionLogic.sanitizeForSpeech(
                "## Hello!\n- **Zoe** sees `bright blue` sky — visit https://example.com/test now.");
        assertFalse(cleaned.contains("**"));
        assertFalse(cleaned.contains("`"));
        assertFalse(cleaned.contains("##"));
        assertFalse(cleaned.contains("https://"));
        assertTrue(cleaned.contains("Hello!"));
        assertTrue(cleaned.contains("Zoe sees bright blue sky"));
    }

    @Test
    public void sentenceStreamingExtractsCompletedSentencesIncrementally() {
        String s1 = "I see a coffee mug on your desk. It looks warm and ";
        LiveSessionLogic.SentenceBatch b1 = LiveSessionLogic.extractReadySentences(s1, 0);
        assertEquals(1, b1.sentences.size());
        assertEquals("I see a coffee mug on your desk.", b1.sentences.get(0));

        String s2 = s1 + "cozy! Want me to read the label?";
        LiveSessionLogic.SentenceBatch b2 = LiveSessionLogic.extractReadySentences(s2, b1.nextOffset);
        assertEquals(1, b2.sentences.size());
        assertEquals("It looks warm and cozy!", b2.sentences.get(0));

        String rem = LiveSessionLogic.extractRemainder(s2, b2.nextOffset);
        assertEquals("Want me to read the label?", rem);
    }

    @Test
    public void liveVoicePromptFusesSimultaneousCameraSight() {
        String prompt = LiveSessionLogic.buildLiveVoicePrompt(
                "What am I holding?",
                "Labels: Mug (92%), Coffee (84%). Visible text: \"ZOE LAB\".");
        assertTrue(prompt.contains("Live camera currently sees"));
        assertTrue(prompt.contains("ZOE LAB"));
        assertTrue(prompt.contains("What am I holding?"));
        assertTrue(LiveSessionLogic.isLikelyCameraQuestion("What am I holding?"));
    }

    @Test
    public void wakeWordHandlesZoeyAndDiacriticVariants() {
        assertTrue(WakeWordDetector.isHiZoeTrigger("Hi Zoë, what's on my desk?"));
        assertEquals("what's on my desk?", WakeWordDetector.stripWakePrefix("Hi Zoë, what's on my desk?"));
        assertTrue(WakeWordDetector.isHiZoeTrigger("Hey Zoey"));
        assertTrue(WakeWordDetector.isHiZoeTrigger("Zoe"));
        assertFalse(WakeWordDetector.isHiZoeTrigger("Let's check the weather"));
    }
}
