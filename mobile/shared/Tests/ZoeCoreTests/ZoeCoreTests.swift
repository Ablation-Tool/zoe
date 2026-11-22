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

    private let trinityFixture = """
    {"protocol":1,"name":"Zoe Trinity","revision":1,"creator":"Nicholas Michael Kloster alone, March 6, 2026",
    "active":{"probabilities":[0.7,0.2,0.08,0.02],"tau":0.05,
    "zoe":{"accessible":3,"complement":1,"vocabularySize":4},
    "tiny":{"probabilities":[22938,6554,2621,655],"tau":1638,"accessible":3,"complement":1,"vocabularySize":4,
    "request":"800200000A0666599A199A0A3D028F","response":"00030001000406669000"},
    "quantizationChanged":false},"memory":{"enabled":false,"records":0,"tamperEvidenceOnly":true},"events":[]}
    """
}
