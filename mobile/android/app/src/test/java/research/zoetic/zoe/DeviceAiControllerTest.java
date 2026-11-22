package research.zoetic.zoe;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class DeviceAiControllerTest {
    @Test
    public void recognizesStubAiCoreVersionNames() {
        assertTrue(DeviceAiController.isStubVersionName("0.stub.aicore_20260703.00_RC01.955890832"));
        assertTrue(DeviceAiController.isStubVersionName("STUB"));
        assertFalse(DeviceAiController.isStubVersionName("0.5.12345"));
        assertFalse(DeviceAiController.isStubVersionName(null));
    }

    @Test
    public void mapsSpeechRecognizerErrorCodesWithReadableCodeTag() {
        String label = ConversationActivity.speechErrorLabel(7);
        assertTrue(label.contains("code 7"));
        assertTrue(label.contains("No speech match"));
    }
}
