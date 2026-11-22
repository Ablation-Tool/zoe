package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.List;

public class ScientificVisualAndPatentTest {
    @Test
    public void haeckelMathSeedsGoldenAngleSpiralAndPromptGroundingWork() {
        int s1 = ScientificVisualSubstrate.deterministicSeed("radiolaria prism");
        int s2 = ScientificVisualSubstrate.deterministicSeed("radiolaria prism");
        int s3 = ScientificVisualSubstrate.deterministicSeed("ammonite gear");
        assertEquals(s1, s2);
        assertNotEquals(s1, s3);

        int order = ScientificVisualSubstrate.symmetryOrderForSeed(s1);
        assertTrue(order >= 6 && order <= 16 && order % 2 == 0);

        double[] p1 = ScientificVisualSubstrate.phyllotaxisPoint(1, 10.0);
        double[] p9 = ScientificVisualSubstrate.phyllotaxisPoint(9, 10.0);
        double r1 = Math.hypot(p1[0], p1[1]);
        double r9 = Math.hypot(p9[0], p9[1]);
        assertEquals(10.0, r1, 1e-6);
        assertEquals(30.0, r9, 1e-6);

        double[] sp0 = ScientificVisualSubstrate.logarithmicSpiralPoint(0.0, 4.0, 0.2);
        double[] spPi = ScientificVisualSubstrate.logarithmicSpiralPoint(Math.PI, 4.0, 0.2);
        assertEquals(4.0, sp0[0], 1e-6);
        assertTrue(Math.hypot(spPi[0], spPi[1]) > 4.0);

        String grounded = ScientificVisualSubstrate.augmentPromptWithBaseline(
                "bioluminescent jellyfish lantern", ScientificVisualSubstrate.BaselinePlate.HAECKEL_RADIOLARIA);
        assertTrue(grounded.contains("Kunstformen der Natur"));
        assertTrue(grounded.contains("137.5°"));

        String patentPrompt = ScientificVisualSubstrate.augmentPromptWithBaseline(
                "mechanical optical lens", ScientificVisualSubstrate.BaselinePlate.PATENT_BLUEPRINT);
        assertTrue(patentPrompt.contains("orthographic"));

        assertEquals(ScientificVisualSubstrate.BaselinePlate.WEISMANN_GERMPLASM,
                ScientificVisualSubstrate.detectPlateFromCommand("draw weismann germ plasm"));
        assertEquals(ScientificVisualSubstrate.BaselinePlate.LAMARCK_MORPHOSPACE,
                ScientificVisualSubstrate.detectPlateFromCommand("lamarck comparative taxonomy"));
        assertEquals(ScientificVisualSubstrate.BaselinePlate.PATENT_BLUEPRINT,
                ScientificVisualSubstrate.detectPlateFromCommand("patent schematic blueprint"));
    }

    @Test
    public void extractsStampedPatentIdsParsesGooglePatentsJsonAndComparesRealScale() {
        assertEquals("US10234567B2", GooglePatentsClient.extractPatentNumber("Model X · US10234567B2 Made in USA"));
        assertEquals("US6123456", GooglePatentsClient.extractPatentNumber("PAT. NO. 6,123,456"));
        assertEquals("EP3456789A1", GooglePatentsClient.extractPatentNumber("Ref EP 3456789 A1"));
        assertEquals("", GooglePatentsClient.extractPatentNumber("just a coffee mug"));

        String sampleJson = "{\"results\":{\"total_num_results\":2,\"cluster\":[{\"result\":[{"
                + "\"patent\":{\"publication_number\":\"US9876543B2\","
                + "\"title\":\"Optical beam-splitting prism assembly\","
                + "\"snippet\":\"A precision 42.5 mm prism mounted on a 60 degree gear stage &hellip;\","
                + "\"assignee\":\"Zoetic Optics Lab\",\"publication_date\":\"2024-05-12\","
                + "\"thumbnail\":\"thumb/US9876543B2.png\"}}]}]}}";
        List<GooglePatentsClient.PatentMatch> matches = GooglePatentsClient.parseGooglePatentsJson(sampleJson, 3);
        assertEquals(1, matches.size());
        GooglePatentsClient.PatentMatch m = matches.get(0);
        assertEquals("US9876543B2", m.publicationNumber);
        assertEquals("https://patents.google.com/patent/US9876543B2/en", m.patentUrl);
        assertTrue(m.dimensionsNote.contains("42.5 mm"));
        assertTrue(m.thumbnailUrl.contains("patentimages.storage.googleapis.com"));

        String qFromOcr = GooglePatentsClient.buildStructuralQuery(
                "Labels: Tool (82%). Visible text: \"PAT. 6,123,456\".", "what is this?");
        assertEquals("US6123456", qFromOcr);

        String scaleSmall = ScientificVisualSubstrate.describeRelativeScale(0.15f);
        assertTrue(scaleSmall.contains("mm"));
        assertTrue(scaleSmall.contains("smartphone"));

        String scaleMeter = ScientificVisualSubstrate.describeRelativeScale(1.05f);
        assertTrue(scaleMeter.contains("guitar"));
        assertFalse(scaleMeter.isEmpty());
    }
}
