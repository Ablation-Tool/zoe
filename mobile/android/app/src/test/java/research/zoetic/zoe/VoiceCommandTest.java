package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

public class VoiceCommandTest {
    @Test
    public void navigationAndActionsAreDeterministic() {
        assertEquals(VoiceCommand.INSPECT, VoiceCommand.parse("Please inspect this"));
        assertEquals(VoiceCommand.REPEAT, VoiceCommand.parse("Read aloud"));
        assertEquals(VoiceCommand.STOP, VoiceCommand.parse("Stop talking"));
        assertEquals(VoiceCommand.MEASURE, VoiceCommand.parse("Measure the forecast"));
        assertEquals(VoiceCommand.GEMINI, VoiceCommand.parse("Open Gemini"));
        assertEquals(VoiceCommand.UNKNOWN, VoiceCommand.parse("Tell me a joke"));
        assertEquals(VoiceCommand.UNKNOWN, VoiceCommand.parse(null));
    }
}
