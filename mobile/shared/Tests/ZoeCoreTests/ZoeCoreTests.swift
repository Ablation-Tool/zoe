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
}
