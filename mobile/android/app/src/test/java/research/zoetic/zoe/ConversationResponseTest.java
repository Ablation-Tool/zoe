package research.zoetic.zoe;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class ConversationResponseTest {
    @Test
    public void deviceTopicsHaveExplicitDeterministicReplies() {
        assertTrue(ConversationResponse.forInput("check the battery").contains("Device Field"));
        assertTrue(ConversationResponse.forInput("measure forecast breadth").contains("not correctness"));
        assertTrue(ConversationResponse.forInput("show front and back cameras").contains("Multi-view"));
        assertTrue(ConversationResponse.forInput("open Gemini").contains("not present its response as my own"));
        assertTrue(ConversationResponse.forInput("something new").contains("something new"));
    }

    @Test
    public void atelierTopicsAreCoveredOffline() {
        assertTrue(ConversationResponse.forInput("play chladni").contains("Eliza-GEM"));
        assertTrue(ConversationResponse.forInput("open my trip journal").contains("Trip Journal"));
        assertTrue(ConversationResponse.forInput("kloster equation").contains("Kloster"));
        assertTrue(ConversationResponse.forInput("hello zoe").contains("Zoe"));
    }

    @Test
    public void stopEndsTheLoop() {
        assertTrue(ConversationResponse.isStop("stop talking"));
        assertTrue(ConversationResponse.isStop("goodbye"));
        assertFalse(ConversationResponse.isStop("keep talking"));
    }
}
