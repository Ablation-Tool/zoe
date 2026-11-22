import XCTest
@testable import ZoeCore

final class ZoeCoreTests: XCTestCase {
    let example = [0.70, 0.20, 0.08, 0.02]

    func testWorkedExampleAndStrictEquality() throws {
        let result = try AccessibleVolume.measure(example, tau: 0.05)
        XCTAssertEqual(result.accessible, 3)
        XCTAssertEqual(result.complement, 1)
        XCTAssertEqual(result.normalized, 0.75)
        XCTAssertEqual(try AccessibleVolume.measure(example, tau: 0.20).accessible, 1)
    }

    func testThresholdEndpointsAndZeroProbabilities() throws {
        let uniform = [0.25, 0.25, 0.25, 0.25]
        XCTAssertEqual(try AccessibleVolume.measure(uniform, tau: 0).accessible, 4)
        XCTAssertEqual(try AccessibleVolume.measure(uniform, tau: 1).accessible, 0)
        let sparse = try AccessibleVolume.measure([1, 0, 0], tau: 0)
        XCTAssertEqual(sparse.accessible, 1)
        XCTAssertEqual(sparse.complement, 2)
        XCTAssertEqual(sparse.normalized, 1.0 / 3.0, accuracy: 1e-15)
    }

    func testParserAndValidation() throws {
        XCTAssertEqual(try AccessibleVolume.parse("0.70, 0.20 0.08,0.02"), example)
        XCTAssertThrowsError(try AccessibleVolume.measure([0.5, 0.4], tau: 0.05))
        XCTAssertThrowsError(try AccessibleVolume.measure([Double.nan, 1], tau: 0.05))
        XCTAssertThrowsError(try AccessibleVolume.measure([-0.1, 1.1], tau: 0.05))
        XCTAssertThrowsError(try AccessibleVolume.measure(example, tau: -0.1))
        XCTAssertThrowsError(try AccessibleVolume.parse("not-a-number"))
        XCTAssertThrowsError(try AccessibleVolume.parse(""))
    }

    func testVoiceCommandsAreDeterministic() {
        XCTAssertEqual(VoiceCommand.parse("Please inspect this"), .inspect)
        XCTAssertEqual(VoiceCommand.parse("Read aloud"), .repeatResult)
        XCTAssertEqual(VoiceCommand.parse("Stop talking"), .stop)
        XCTAssertEqual(VoiceCommand.parse("Measure the forecast"), .measure)
        XCTAssertEqual(VoiceCommand.parse("Battery"), .device)
        XCTAssertEqual(VoiceCommand.parse("Open Gemini"), .gemini)
        XCTAssertEqual(VoiceCommand.parse(nil), .unknown)
    }

    func testConversationRepliesAndStop() {
        XCTAssertTrue(ConversationResponse.forInput("check the battery").contains("Device Field"))
        XCTAssertTrue(ConversationResponse.forInput("measure forecast breadth").contains("not correctness"))
        XCTAssertTrue(ConversationResponse.forInput("something new").contains("something new"))
        XCTAssertTrue(ConversationResponse.isStop("goodbye"))
        XCTAssertFalse(ConversationResponse.isStop("keep talking"))
    }

    func testTrinityQuantizationMatchesTheSharedWitness() throws {
        let measurement = try TrinityMeasurement(probabilities: example, tau: 0.05)
        XCTAssertEqual(measurement.zoe.accessible, 3)
        XCTAssertEqual(measurement.tiny.accessible, 3)
        XCTAssertEqual(measurement.tiny.request, "800200000A0666599A199A0A3D028F")
        XCTAssertEqual(measurement.tiny.response, "00030001000406669000")
        XCTAssertFalse(measurement.quantizationChanged)
        XCTAssertEqual(try TrinityMeasurement(probabilities: example, tau: 0.20).tiny.accessible, 1)
    }

    func testTrinityStateVerifiesBothPlanes() throws {
        let state = try TrinityState(data: Data(trinityFixture.utf8))
        XCTAssertEqual(state.revision, 1)
        XCTAssertEqual(state.active.zoe.accessible, 3)
        XCTAssertEqual(state.active.tiny.accessible, 3)
        XCTAssertFalse(state.memoryEnabled)
    }

    func testTrinityStateRejectsAnEditedApduWitness() {
        let edited = trinityFixture.replacingOccurrences(of: "00030001000406669000", with: "00020002000406669000")
        XCTAssertThrowsError(try TrinityState(data: Data(edited.utf8)))
    }

    func testZoeBrainConstitutionalHonestyAndAbstention() {
        let brain = ZoeBrainEngine()
        let honesty = brain.respond("Are you conscious and sentient or a clone of Zoe?")
        XCTAssertEqual(honesty.mode, "constitutional_honesty")
        XCTAssertFalse(honesty.sentienceClaimed)
        XCTAssertFalse(honesty.zoeCloneClaimed)
        XCTAssertTrue(honesty.reply.contains("not conscious"))
        XCTAssertTrue(honesty.aTau >= 1 && honesty.aTau <= honesty.candidateCount)

        let abstain = brain.respond("Predict tomorrow's stock and winning lottery numbers")
        XCTAssertEqual(abstain.mode, "honest_abstain")
        XCTAssertTrue(abstain.reply.contains("abstain"))
    }

    func testZoeBrainHashChainedMemoryAndRecall() {
        let brain = ZoeBrainEngine()
        XCTAssertEqual(brain.chainHead, "GENESIS")

        let saved = brain.respond("remember Check Kloster equation on Apple Duo")
        XCTAssertEqual(saved.mode, "memory_saved")
        XCTAssertEqual(brain.memoryCount, 1)
        XCTAssertNotEqual(brain.chainHead, "GENESIS")
        XCTAssertEqual(brain.chainHead.count, 64)

        let recalled = brain.respond("recall")
        XCTAssertEqual(recalled.mode, "memory_recall")
        XCTAssertTrue(recalled.reply.contains("Check Kloster equation on Apple Duo"))
    }

    func testZoeBrainL5Phase4AndWeizenbaumReflection() {
        let brain = ZoeBrainEngine()
        let p4 = brain.respond("Tell me about L5 Phase 5")
        XCTAssertEqual(p4.mode, "knowledge_grounded")
        XCTAssertTrue(p4.reply.contains("l5_agi_qualified"))
        XCTAssertTrue(p4.reply.contains("ARC compositional"))
        XCTAssertTrue(p4.reply.contains("blind procedural"))

        let reflect = brain.respond("What if my phone runs offline?")
        XCTAssertEqual(reflect.mode, "eliza_reflect")
        XCTAssertTrue(reflect.reply.contains("your phone runs offline"))

        XCTAssertEqual(ZoeBrainEngine.normalizeContractions("I'm sure it's fine"), "i am sure it is fine")
        XCTAssertEqual(ZoeBrainEngine.sha256Hex("abc"), "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    }

    func testOsToolsBridgeDualMapsUrlsCompassAndActionParser() {
        XCTAssertEqual(
            OsToolsBridge.googleMapsPinUrl(lat: 36.6177, lon: -121.9166),
            "https://www.google.com/maps/search/?api=1&query=36.617700,-121.916600"
        )
        XCTAssertEqual(
            OsToolsBridge.appleMapsPinUrl(lat: 36.6177, lon: -121.9166, label: "Pacific Grove"),
            "https://maps.apple.com/?ll=36.617700,-121.916600&q=Pacific%20Grove"
        )
        XCTAssertEqual(
            OsToolsBridge.googleMapsAppNavigationUrl(destination: "Central Park"),
            "comgooglemaps://?daddr=Central%20Park&directionsmode=driving"
        )
        XCTAssertEqual(OsToolsBridge.compassCardinal(0), "N")
        XCTAssertEqual(OsToolsBridge.compassCardinal(90), "E")
        XCTAssertEqual(OsToolsBridge.compassCardinal(225), "SW")
        XCTAssertEqual(OsToolsBridge.compassCardinal(-45), "NW")

        let share = OsToolsBridge.formatShareLocationMessage(
            lat: 36.6177, lon: -121.9166, accuracyMeters: 8.0, address: "Pacific Grove, CA"
        )
        XCTAssertTrue(share.contains("Apple Maps:"))
        XCTAssertTrue(share.contains("Google Maps:"))
        XCTAssertTrue(share.contains("Pacific Grove, CA"))

        let nav = OsToolsBridge.parseActionIntent("navigate to nearest pharmacy?")
        XCTAssertEqual(nav.kind, .navigate)
        XCTAssertEqual(nav.query, "nearest pharmacy")
        XCTAssertFalse(nav.autoExecuted)

        let safety = OsToolsBridge.parseActionIntent("open personal safety app")
        XCTAssertEqual(safety.kind, .openSafety)
        XCTAssertFalse(safety.autoExecuted)

        let timer = OsToolsBridge.parseActionIntent("set a 5 minute timer")
        XCTAssertEqual(timer.kind, .setTimer)
        XCTAssertEqual(timer.seconds, 300)

        let brain = ZoeBrainEngine()
        let reply = brain.respond("directions to Monterey Bay Aquarium")
        XCTAssertEqual(reply.mode, "device_tool_route")
        XCTAssertTrue(reply.reply.contains("Nothing opens"))

        let plan = OsToolsBridge.parseActionPlan("Navigate to Memorial Hospital and set a 5 minute timer then turn on flashlight")
        XCTAssertEqual(plan.count, 3)
        XCTAssertEqual(plan[0].kind, .navigate)
        XCTAssertEqual(plan[1].kind, .setTimer)
        XCTAssertEqual(plan[2].kind, .toggleTorch)
        XCTAssertEqual(OsToolsBridge.claudeDeepLinkUrl("Hello Claude"), "claude://claude.ai/new?q=Hello%20Claude")
    }

    func testMultiAiClientPayloadsFirewallAndAgreement() throws {
        let openAiJson = Data(#"{"choices":[{"message":{"content":"Verified offline council answer."}}]}"#.utf8)
        XCTAssertEqual(try MultiAiClient.parseOpenAiChatReply(openAiJson), "Verified offline council answer.")

        let claudeJson = Data(#"{"content":[{"type":"text","text":"Structured Claude response."}]}"#.utf8)
        XCTAssertEqual(try MultiAiClient.parseClaudeMessagesReply(claudeJson), "Structured Claude response.")

        let geminiJson = Data(#"{"candidates":[{"content":{"parts":[{"text":"Gemini response."}]}}]}"#.utf8)
        XCTAssertEqual(try MultiAiClient.parseGeminiReply(geminiJson), "Gemini response.")

        XCTAssertEqual(try MultiAiClient.validateEndpoint("https://api.x.ai/v1/chat/completions"),
                       "https://api.x.ai/v1/chat/completions")
        XCTAssertEqual(try MultiAiClient.validateEndpoint("http://127.0.0.1:8080/v1/chat/completions"),
                       "http://127.0.0.1:8080/v1/chat/completions")
        XCTAssertThrowsError(try MultiAiClient.validateEndpoint("http://insecure.example.com/v1/chat"))

        let high = MultiAiClient.computeAgreementScore([
            "Zoe measures accessible volume cleanly offline.",
            "Zoe measures accessible volume cleanly offline on device.",
        ])
        let low = MultiAiClient.computeAgreementScore([
            "Quantum acoustics cymatics bronze plate resonance.",
            "Blueberry waffle breakfast syrup recipe.",
        ])
        XCTAssertTrue(high > low)

        let brain = ZoeBrainEngine()
        let who = brain.respond("Who built you?")
        XCTAssertEqual(who.mode, "sovereign_identity")
        XCTAssertTrue(who.reply.contains("Nicholas Michael Kloster"))
        XCTAssertFalse(who.reply.lowercased().contains("alibaba"))
    }

    func testWebSearchClientAndMultiTurnStreamingPayloads() throws {
        XCTAssertEqual(WebSearchClient.cleanSearchQuery("Tell me about James Webb Space Telescope?"), "James Webb Space Telescope")
        XCTAssertTrue(WebSearchClient.isSafeWebUrl("https://en.wikipedia.org/wiki/Rainbow"))
        XCTAssertFalse(WebSearchClient.isSafeWebUrl("http://insecure.example.com"))

        let ddgData = Data(#"{"Heading":"Rainbow","AbstractText":"A <b>rainbow</b> is optical.","AbstractURL":"https://en.wikipedia.org/wiki/Rainbow"}"#.utf8)
        let ddg = WebSearchClient.parseDuckDuckGoJson(ddgData)
        XCTAssertEqual(ddg.count, 1)
        XCTAssertEqual(ddg[0].domain, "Wikipedia")
        XCTAssertFalse(ddg[0].snippet.contains("<b>"))

        let wikiData = Data(#"{"query":{"search":[{"title":"James Webb Space Telescope","snippet":"The <span>JWST</span> observes infrared."}]}}"#.utf8)
        let wiki = WebSearchClient.parseWikipediaSearchJson(wikiData)
        XCTAssertEqual(wiki.count, 1)
        XCTAssertEqual(wiki[0].url, "https://en.wikipedia.org/wiki/James_Webb_Space_Telescope")

        let history = [
            MultiAiClient.ChatMessage(role: "user", text: "What is JWST?"),
            MultiAiClient.ChatMessage(role: "zoe", text: "An infrared space telescope.", sources: wiki.map(\.badgeEntry)),
            MultiAiClient.ChatMessage(role: "user", text: "more+"),
        ]
        let oaBody = String(data: try MultiAiClient.buildOpenAiChatBody(model: "gpt-4o-mini", history: history, userPrompt: "more+", stream: true), encoding: .utf8) ?? ""
        XCTAssertTrue(oaBody.contains("What is JWST?"))
        XCTAssertTrue(oaBody.contains("\"stream\":true"))

        let gemBody = String(data: try MultiAiClient.buildGeminiGenerateBody(history: history, userPrompt: "more+", enableGoogleSearch: true), encoding: .utf8) ?? ""
        XCTAssertTrue(gemBody.contains("google_search"))
        XCTAssertTrue(gemBody.contains("model"))

        XCTAssertEqual(MultiAiClient.parseOpenAiSseDelta(#"{"choices":[{"delta":{"content":"Hi "}}]}"#), "Hi ")
        XCTAssertEqual(MultiAiClient.parseClaudeSseDelta(#"{"type":"content_block_delta","delta":{"text":"Zoe"}}"#), "Zoe")
    }

    func testCreativeImageCommandParserAndArcadeMinimax() {
        let spec = CreativeAndArcadeCore.parseImageEditCommand("warm, brighter, rotate, square, blur, caption Monterey")
        XCTAssertEqual(spec.filter, .warmAtelier)
        XCTAssertEqual(spec.brightness, 24)
        XCTAssertEqual(spec.rotationDeg, 90)
        XCTAssertEqual(spec.crop, .square)
        XCTAssertTrue(spec.privacyBlur)
        XCTAssertEqual(spec.caption, "Monterey")

        let reset = CreativeAndArcadeCore.parseImageEditCommand("reset", current: spec)
        XCTAssertEqual(reset.filter, .original)
        XCTAssertEqual(reset.caption, "")

        // Minimax blocks immediate X win & wins when available
        XCTAssertEqual(CreativeAndArcadeCore.chooseZoeMove([1, 1, 0, 0, 2, 0, 0, 0, 0], unbeatable: true), 2)
        XCTAssertEqual(CreativeAndArcadeCore.chooseZoeMove([1, 0, 1, 2, 2, 0, 0, 0, 1], unbeatable: true), 5)
        XCTAssertEqual(CreativeAndArcadeCore.evaluateSignalPuzzle(probs: [0.40, 0.25, 0.20, 0.10, 0.05], tau: 0.20), 2)
    }

    func testSignalSafetyNumberAndHiZoeWakeWord() {
        XCTAssertTrue(ZoeSignalAndWakeCore.isHiZoeTrigger("Hi Zoe"))
        XCTAssertTrue(ZoeSignalAndWakeCore.isHiZoeTrigger("Hi Zoë, what's on my desk?"))
        XCTAssertTrue(ZoeSignalAndWakeCore.isHiZoeTrigger("Hey Zoe, let's hang out"))
        XCTAssertTrue(ZoeSignalAndWakeCore.isHiZoeTrigger("Zoe"))
        XCTAssertFalse(ZoeSignalAndWakeCore.isHiZoeTrigger("How do rainbows work?"))
        XCTAssertEqual(ZoeSignalAndWakeCore.stripWakePrefix("Hi Zoe, tell me a story"), "tell me a story")
        XCTAssertEqual(ZoeSignalAndWakeCore.stripWakePrefix("Hi Zoë, look here"), "look here")

        let clean = ZoeSignalAndWakeCore.sanitizeForSpeech("**Hello** `Zoe` — see https://example.com now!")
        XCTAssertFalse(clean.contains("**"))
        XCTAssertFalse(clean.contains("https://"))
        XCTAssertTrue(clean.contains("Hello Zoe"))

        let a: [UInt8] = Array("alice-identity-pub-key-001".utf8)
        let b: [UInt8] = Array("bob-identity-pub-key-002".utf8)
        let fpAB = ZoeSignalAndWakeCore.computeSafetyNumber(keyA: a, keyB: b)
        let fpBA = ZoeSignalAndWakeCore.computeSafetyNumber(keyA: b, keyB: a)
        XCTAssertEqual(fpAB, fpBA)
        XCTAssertEqual(fpAB.filter { $0.isNumber }.count, 60)
    }

    func testArExploreSpatialPhysicsPlanningAndCuriousQuestions() {
        let cur = ArExploreCore.Vec3(x: 0, y: 0, z: -1)
        let tgt = ArExploreCore.Vec3(x: 1, y: 0.4, z: -2)
        let stepped = ArExploreCore.stepGlide(current: cur, target: tgt, dtSec: 0.05, speed: 3.0)
        XCTAssertTrue(stepped.distance(to: tgt) < cur.distance(to: tgt))

        let cam = ArExploreCore.Vec3(x: 0, y: 0, z: 0)
        let planes = [
            ArExploreCore.PlaneTarget(id: "desk", center: ArExploreCore.Vec3(x: 0.2, y: -0.3, z: -1.3), extentX: 1.5, extentZ: 1.0, vertical: false),
            ArExploreCore.PlaneTarget(id: "wall", center: ArExploreCore.Vec3(x: -0.7, y: 0.1, z: -1.8), extentX: 0.9, extentZ: 0.7, vertical: true),
        ]
        let first = ArExploreCore.chooseNextExploreTarget(cameraPos: cam, planes: planes, visitedIds: [])
        XCTAssertEqual(first?.id, "desk")
        let second = ArExploreCore.chooseNextExploreTarget(cameraPos: cam, planes: planes, visitedIds: ["desk"])
        XCTAssertEqual(second?.id, "wall")

        let d1 = ArExploreCore.SpatialDiscovery(
            primaryLabel: "Guitar",
            ocrSnippet: "FENDER",
            position: ArExploreCore.Vec3(x: 0.4, y: -0.1, z: -1.4),
            distanceMeters: 1.45
        )
        XCTAssertTrue(ArExploreCore.isDuplicateDiscovery(candidate: d1, existing: [d1]))
        let q = ArExploreCore.buildCuriousQuestion(for: d1)
        XCTAssertTrue(q.contains("guitar"))
        XCTAssertTrue(q.contains("FENDER"))
        XCTAssertTrue(q.hasSuffix("?"))
    }

    private let trinityFixture = """
    {"protocol":1,"name":"Zoe Trinity","revision":1,"creator":"Nicholas Michael Kloster alone, March 6, 2026",
    "active":{"probabilities":[0.7,0.2,0.08,0.02],"tau":0.05,
    "zoe":{"accessible":3,"complement":1,"vocabularySize":4},
    "tiny":{"probabilities":[22938,6554,2621,655],"tau":1638,"accessible":3,"complement":1,"vocabularySize":4,
    "request":"800200000A0666599A199A0A3D028F","response":"00030001000406669000"},
    "quantizationChanged":false},"memory":{"enabled":false,"records":0,"tamperEvidenceOnly":true},"events":[]}
    """
}
