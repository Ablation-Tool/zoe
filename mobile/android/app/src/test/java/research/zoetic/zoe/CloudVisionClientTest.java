package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class CloudVisionClientTest {
    @Test
    public void buildsValidGeminiRequestJsonAndParsesCandidateText() {
        String req = CloudVisionClient.buildRequestJson("What plant is this?", "AQID");
        assertTrue(req.contains("What plant is this?"));
        assertTrue(req.contains("image/jpeg"));
        assertTrue(req.contains("AQID"));

        String resp = "{\"candidates\":[{\"content\":{\"parts\":[{\"text\":\"A stained glass Porsche.\"}]}}]}";
        assertEquals("A stained glass Porsche.", CloudVisionClient.parseResponseText(resp));
    }

    @Test
    public void validatesSafeModelNamesOnly() {
        assertEquals("gemini-2.5-flash", CloudVisionClient.validateModel("gemini-2.5-flash"));
        boolean rejected = false;
        try {
            CloudVisionClient.validateModel("gemini-2.5/../../evil");
        } catch (IllegalArgumentException expected) {
            rejected = true;
        }
        assertTrue(rejected);
    }
}
