package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

import java.util.Arrays;
import java.util.Collections;
import java.util.List;

public class MultiAiAndChatTest {
    @Test
    public void buildsAndParsesOpenAiGrokAndClaudePayloadsAndEnforcesHttps() {
        String openAiReq = MultiAiClient.buildOpenAiChatJson("grok-3-mini", MultiAiClient.ZOE_SYSTEM_PROMPT, "Hello Zoe");
        assertTrue(openAiReq.contains("\"grok-3-mini\""));
        assertTrue(openAiReq.contains("Hello Zoe"));

        String openAiResp = "{\"choices\":[{\"message\":{\"role\":\"assistant\",\"content\":\"Calm verified answer.\"}}]}";
        assertEquals("Calm verified answer.", MultiAiClient.parseOpenAiChatReply(openAiResp));

        String claudeReq = MultiAiClient.buildClaudeMessagesJson("claude-sonnet-4-5", MultiAiClient.ZOE_SYSTEM_PROMPT, "Test");
        assertTrue(claudeReq.contains("\"claude-sonnet-4-5\""));
        String claudeResp = "{\"content\":[{\"type\":\"text\",\"text\":\"Structured Claude reply.\"}]}";
        assertEquals("Structured Claude reply.", MultiAiClient.parseClaudeMessagesReply(claudeResp));

        assertEquals("https://api.x.ai/v1/chat/completions",
                MultiAiClient.validateEndpoint("https://api.x.ai/v1/chat/completions"));
        assertEquals("http://127.0.0.1:8080/v1/chat/completions",
                MultiAiClient.validateEndpoint("http://127.0.0.1:8080/v1/chat/completions"));
        try {
            MultiAiClient.validateEndpoint("http://evil.example.com/v1/chat");
            fail("Non-loopback cleartext HTTP must be rejected");
        } catch (IllegalArgumentException expected) {
            assertTrue(expected.getMessage().contains("HTTPS"));
        }

        double high = MultiAiClient.computeAgreementScore(Arrays.asList(
                "Zoe measures accessible volume cleanly offline.",
                "Zoe measures accessible volume cleanly offline on device."));
        double low = MultiAiClient.computeAgreementScore(Arrays.asList(
                "Quantum acoustics cymatics bronze resonance plate.",
                "Strawberry pancake breakfast syrup recipe."));
        assertTrue(high > low);
    }

    @Test
    public void parsesMultiStepPlansAndChatHistoryRoundTripsAndChatMlPrompt() {
        List<OsToolsBridge.ActionSuggestion> plan = OsToolsBridge.parseActionPlan(
                "Navigate to Memorial Hospital and set a 5 minute timer then turn on flashlight");
        assertEquals(3, plan.size());
        assertEquals(OsToolsBridge.ActionKind.NAVIGATE, plan.get(0).kind);
        assertEquals(OsToolsBridge.ActionKind.SET_TIMER, plan.get(1).kind);
        assertEquals(300, plan.get(1).seconds);
        assertEquals(OsToolsBridge.ActionKind.TOGGLE_TORCH, plan.get(2).kind);
        for (OsToolsBridge.ActionSuggestion step : plan) {
            assertFalse(step.autoExecuted);
        }
        assertEquals("claude://claude.ai/new?q=Hello%20Claude", OsToolsBridge.claudeDeepLinkUri("Hello Claude"));

        ChatHistoryStore.ChatThread thread = new ChatHistoryStore.ChatThread(
                "chat-1", "Kloster check", "2026-11-21 23:20",
                Arrays.asList(
                        new ChatHistoryStore.ChatMessage("user", "What is A_tau?", "YOU", "", 0),
                        new ChatHistoryStore.ChatMessage("zoe", "Strict count above tau.", "ZOE STEM", "A_0.08=1/6", 3)));
        String json = ChatHistoryStore.toJson(Collections.singletonList(thread));
        List<ChatHistoryStore.ChatThread> parsed = ChatHistoryStore.fromJson(json);
        assertEquals(1, parsed.size());
        assertEquals("Kloster check", parsed.get(0).title);
        assertEquals(2, parsed.get(0).messages.size());
        assertEquals("A_0.08=1/6", parsed.get(0).messages.get(1).glassBox);

        String chatMl = OnDeviceLlmEngine.buildChatMlPrompt("Explain gravity", parsed.get(0).messages, "- Remember Newton");
        assertTrue(chatMl.contains("<|im_start|>system"));
        assertTrue(chatMl.contains("Nicholas Michael Kloster"));
        assertTrue(chatMl.contains("Remember Newton"));
        assertTrue(chatMl.contains("Explain gravity"));
        assertEquals("Hello world", OnDeviceLlmEngine.cleanResponse("Hello world<|im_end|>"));
        assertEquals("Line 1\n\nLine 2", OnDeviceLlmEngine.cleanResponse("Line 1\\n\\nLine 2<|im_end|>"));

        // Verify duplicate trailing user message is deduplicated and "more+" expands cleanly
        List<ChatHistoryStore.ChatMessage> withTrailingMore = Arrays.asList(
                new ChatHistoryStore.ChatMessage("user", "How do rainbows form?", "YOU", "", 0),
                new ChatHistoryStore.ChatMessage("zoe", "Sunlight refracts inside water droplets.", "ZOE LOCAL", "", 10),
                new ChatHistoryStore.ChatMessage("user", "more+", "YOU", "", 0));
        String followUpPrompt = OnDeviceLlmEngine.buildChatMlPrompt("more+", withTrailingMore, "");
        assertEquals(-1, followUpPrompt.indexOf("<|im_start|>user\nmore+<|im_end|>"));
        assertTrue(followUpPrompt.contains("Do NOT repeat any sentence you already wrote"));

        String filtered = OnDeviceLlmEngine.enforceZoeSovereignty(
                "Yes, I am Zoe, an AI assistant built by Alibaba Cloud.");
        assertTrue(filtered.contains("I am Zoe"));
        assertTrue(filtered.contains("Nicholas Michael Kloster"));
        assertFalse(filtered.toLowerCase().contains("alibaba"));

        ZoeBrainEngine brain = new ZoeBrainEngine(null);
        ZoeBrainEngine.BrainReply who = brain.respond("Who built you?");
        assertEquals("sovereign_identity", who.mode);
        assertTrue(who.reply.contains("Nicholas Michael Kloster"));
        assertFalse(who.reply.toLowerCase().contains("alibaba"));
    }

    @Test
    public void parsesLiveWebSourcesMultiTurnStreamingPayloadsAndSseDeltas() {
        assertEquals("James Webb Space Telescope", WebSearchClient.cleanSearchQuery("Tell me about James Webb Space Telescope?"));
        assertTrue(WebSearchClient.isSafeWebUrl("https://en.wikipedia.org/wiki/Rainbow"));
        assertFalse(WebSearchClient.isSafeWebUrl("http://insecure.example.com/"));
        assertFalse(WebSearchClient.isSafeWebUrl("javascript:alert(1)"));

        String ddgJson = "{\"Heading\":\"Rainbow\",\"AbstractText\":\"A <b>rainbow</b> is an optical phenomenon.\",\"AbstractURL\":\"https://en.wikipedia.org/wiki/Rainbow\"}";
        List<WebSearchClient.Source> ddg = WebSearchClient.parseDuckDuckGoJson(ddgJson);
        assertEquals(1, ddg.size());
        assertEquals("Wikipedia", ddg.get(0).domain);
        assertFalse(ddg.get(0).snippet.contains("<b>"));

        String wikiJson = "{\"query\":{\"search\":[{\"title\":\"James Webb Space Telescope\",\"snippet\":\"The <span class=\\\"searchmatch\\\">JWST</span> is a space telescope.\"}]}}";
        List<WebSearchClient.Source> wiki = WebSearchClient.parseWikipediaSearchJson(wikiJson);
        assertEquals(1, wiki.size());
        assertEquals("https://en.wikipedia.org/wiki/James_Webb_Space_Telescope", wiki.get(0).url);
        assertTrue(wiki.get(0).snippet.contains("JWST"));

        WebSearchClient.SearchResult sr = new WebSearchClient.SearchResult("JWST", wiki, 120);
        assertTrue(sr.formatContextForPrompt(400).contains("James Webb Space Telescope"));
        assertEquals(1, sr.toSourceBadges().size());

        List<ChatHistoryStore.ChatMessage> history = Arrays.asList(
                new ChatHistoryStore.ChatMessage("user", "What is JWST?", "YOU", "", 0),
                new ChatHistoryStore.ChatMessage("zoe", "An infrared space telescope.", "ZOE LOCAL", "", 40, sr.toSourceBadges()),
                new ChatHistoryStore.ChatMessage("user", "more+", "YOU", "", 0));

        // ChatHistoryStore round-trips clickable source badges
        String threadJson = ChatHistoryStore.toJson(Collections.singletonList(
                new ChatHistoryStore.ChatThread("t2", "JWST", "2026-11-22", history)));
        List<ChatHistoryStore.ChatThread> rt = ChatHistoryStore.fromJson(threadJson);
        assertEquals(1, rt.get(0).messages.get(1).sources.size());

        // Multi-turn streaming JSON for OpenAI, Claude & Gemini
        String oaStream = MultiAiClient.buildOpenAiChatJson("gpt-4o-mini", MultiAiClient.ZOE_SYSTEM_PROMPT, history, "more+", true);
        assertTrue(oaStream.contains("\"stream\":true"));
        assertTrue(oaStream.contains("What is JWST?"));
        String clStream = MultiAiClient.buildClaudeMessagesJson("claude-sonnet-4-5", MultiAiClient.ZOE_SYSTEM_PROMPT, history, "more+", true);
        assertTrue(clStream.contains("\"stream\":true"));
        String gemBody = MultiAiClient.buildGeminiGenerateJson(MultiAiClient.ZOE_SYSTEM_PROMPT, history, "more+", true);
        assertTrue(gemBody.contains("google_search"));
        assertTrue(gemBody.contains("\"role\":\"model\""));

        // SSE token delta parsers
        assertEquals("Hello ", MultiAiClient.parseOpenAiSseDelta("{\"choices\":[{\"delta\":{\"content\":\"Hello \"}}]}"));
        assertEquals("world!", MultiAiClient.parseClaudeSseDelta("{\"type\":\"content_block_delta\",\"delta\":{\"type\":\"text_delta\",\"text\":\"world!\"}}"));
        assertEquals("Gemini token", MultiAiClient.parseGeminiSseDelta("{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"Gemini token\"}]}}]}"));

        // Local ChatML prompt includes verified live web facts when provided
        String groundedChatMl = OnDeviceLlmEngine.buildChatMlPrompt("What is JWST?", history, "", sr.formatContextForPrompt(400));
        assertTrue(groundedChatMl.contains("Live verified web facts"));
        assertTrue(groundedChatMl.contains("James Webb Space Telescope"));
    }
}
