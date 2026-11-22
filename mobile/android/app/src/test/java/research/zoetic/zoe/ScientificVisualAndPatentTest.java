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

    @Test
    public void patentReverseImageEngineDetectsHardToIdObjectsAndMatchesContours() {
        // Hard-to-ID detection: vague labels or low confidence trigger patent reverse-image search
        assertTrue(PatentReverseImageEngine.isHardToIdentify("Labels: none above 55%."));
        assertTrue(PatentReverseImageEngine.isHardToIdentify("Labels: Gadget (64%), Plastic (58%)."));
        assertTrue(PatentReverseImageEngine.isHardToIdentify("Labels: Product (88%), Metal (79%)."));
        assertFalse(PatentReverseImageEngine.isHardToIdentify("Labels: Guitar (91%), Musical instrument (84%)."));

        // Synthetic 32x32 circle (gear/ring) vs horizontal elongated bar (lever/shaft)
        float[] circleA = new float[32 * 32];
        float[] circleB = new float[32 * 32];
        float[] horizBar = new float[32 * 32];
        for (int y = 0; y < 32; y++) {
            for (int x = 0; x < 32; x++) {
                double d = Math.hypot(x - 15.5, y - 15.5);
                circleA[y * 32 + x] = (d >= 7.0 && d <= 10.5) ? 1f : 0f;
                circleB[y * 32 + x] = (d >= 6.5 && d <= 11.0) ? 0.85f : 0.1f; // different brightness/scale!
                horizBar[y * 32 + x] = (y >= 13 && y <= 18 && x >= 3 && x <= 28) ? 1f : 0f;
            }
        }
        PatentReverseImageEngine.VisualSignature sigCircleA = PatentReverseImageEngine.extractFromGray32(circleA);
        PatentReverseImageEngine.VisualSignature sigCircleB = PatentReverseImageEngine.extractFromGray32(circleB);
        PatentReverseImageEngine.VisualSignature sigBar = PatentReverseImageEngine.extractFromGray32(horizBar);

        float sameShapeSim = PatentReverseImageEngine.compareSignatures(sigCircleA, sigCircleB);
        float diffShapeSim = PatentReverseImageEngine.compareSignatures(sigCircleA, sigBar);
        assertTrue("Expected circle-to-circle contour match (" + sameShapeSim + ") > circle-to-bar (" + diffShapeSim + ")",
                sameShapeSim > diffShapeSim + 0.12f);
        assertTrue(sigBar.morphologyKeywords.contains("elongated"));
        assertTrue(sigCircleA.morphologyKeywords.contains("circular") || sigCircleA.morphologyKeywords.contains("symmetrical"));

        String morphQuery = GooglePatentsClient.buildStructuralQuery("Labels: none above 55%.", "what is this?", sigCircleA);
        assertFalse(morphQuery.isEmpty());
        assertTrue(morphQuery.contains("circular") || morphQuery.contains("symmetrical"));
    }

    @Test
    public void visionPriorStoreLearnsReinforcesPersistsAndRejectsUnrelatedShapes() {
        // CPC physical-class filtering excludes software flowcharts while preserving exact patent numbers
        String filtered = GooglePatentsClient.applyPhysicalCpcFilter("circular rotary lens gear", "");
        assertTrue(filtered.contains("cpc:G02"));
        assertTrue(filtered.contains("cpc:F16"));
        assertEquals("US10234567B2", GooglePatentsClient.applyPhysicalCpcFilter("US10234567B2", "US10234567B2"));

        assertEquals("Optical beam-splitting prism assembly",
                GooglePatentsClient.cleanPhysicalConcept("Method and apparatus for optical beam-splitting prism assembly having a mount"));

        // Construct two distinct synthetic shapes (ring vs elongated bar)
        float[] ring1 = new float[32 * 32];
        float[] ring2 = new float[32 * 32];
        float[] bar = new float[32 * 32];
        for (int y = 0; y < 32; y++) {
            for (int x = 0; x < 32; x++) {
                double d = Math.hypot(x - 15.5, y - 15.5);
                ring1[y * 32 + x] = (d >= 7.0 && d <= 10.5) ? 1f : 0f;
                ring2[y * 32 + x] = (d >= 6.8 && d <= 10.8) ? 0.88f : 0.08f;
                bar[y * 32 + x] = (y >= 13 && y <= 18 && x >= 3 && x <= 28) ? 1f : 0f;
            }
        }
        PatentReverseImageEngine.VisualSignature sRing1 = PatentReverseImageEngine.extractFromGray32(ring1);
        PatentReverseImageEngine.VisualSignature sRing2 = PatentReverseImageEngine.extractFromGray32(ring2);
        PatentReverseImageEngine.VisualSignature sBar = PatentReverseImageEngine.extractFromGray32(bar);

        // Before teaching: empty store returns null
        List<VisionPriorStore.Prototype> store = new java.util.ArrayList<>();
        assertEquals(null, VisionPriorStore.findBestMatch(store, sRing2, VisionPriorStore.DEFAULT_MIN_SCORE));

        // Teach "Optical Ring Lens" once, then reinforce it with a second observation
        store = VisionPriorStore.teachOrReinforce(store, "Optical Ring Lens", sRing1, "user_confirmed", "", "42 mm", 1000L);
        assertEquals(1, store.size());
        store = VisionPriorStore.teachOrReinforce(store, "optical ring lens", sRing2, "user_confirmed", "", "", 2000L);
        assertEquals(1, store.size());
        assertEquals(2, store.get(0).confirmCount);
        assertEquals("42 mm", store.get(0).dimensionsNote);

        // JSON persistence round-trip preserves learned prototype cleanly
        String json = VisionPriorStore.serializeJson(store);
        List<VisionPriorStore.Prototype> restored = VisionPriorStore.deserializeJson(json);
        assertEquals(1, restored.size());
        assertEquals("Optical Ring Lens", restored.get(0).label);
        assertEquals(2, restored.get(0).confirmCount);

        // Recognizing a similar ring succeeds offline; an unrelated elongated bar is honestly rejected!
        VisionPriorStore.MatchResult hit = VisionPriorStore.findBestMatch(restored, sRing2, VisionPriorStore.DEFAULT_MIN_SCORE);
        assertTrue(hit != null && "Optical Ring Lens".equals(hit.prototype.label) && hit.matchPercent() >= 78);
        assertTrue(hit.formatSilentPromptHint().contains("Optical Ring Lens"));

        VisionPriorStore.MatchResult miss = VisionPriorStore.findBestMatch(restored, sBar, VisionPriorStore.DEFAULT_MIN_SCORE);
        assertEquals(null, miss);

        // Illumination invariance: dim low-contrast copy of ring1 must match bright ring1 strongly!
        float[] dimRing = new float[32 * 32];
        for (int i = 0; i < dimRing.length; i++) {
            dimRing[i] = 0.12f + ring1[i] * 0.25f;
        }
        PatentReverseImageEngine.VisualSignature sDimRing = PatentReverseImageEngine.extractFromGray32(dimRing);
        float illumSim = PatentReverseImageEngine.compareSignatures(sRing1, sDimRing);
        assertTrue("Expected illumination-invariant contour match >= 0.90, got " + illumSim, illumSim >= 0.90f);
    }

    @Test
    public void cleanRoomVisualAtlasLoadsAll18ArchetypesAndKvCloneDeltaWorks() throws Exception {
        // Verify generated clean-room offline visual atlas (Haeckel + Physical CPC geometry)
        java.nio.file.Path atlasPath = java.nio.file.Paths.get("src/main/assets/zoe_visual_atlas.json");
        assertTrue("Expected zoe_visual_atlas.json to exist", java.nio.file.Files.isRegularFile(atlasPath));
        String json = new String(java.nio.file.Files.readAllBytes(atlasPath), java.nio.charset.StandardCharsets.UTF_8);
        List<VisionPriorStore.Prototype> atlas = VisionPriorStore.deserializeJson(json);
        assertEquals(18, atlas.size());

        // Synthetic optical ring matches clean-room atlas offline; user-taught prototype wins priority!
        float[] ring = new float[32 * 32];
        for (int y = 0; y < 32; y++) {
            for (int x = 0; x < 32; x++) {
                double nx = ((x + 0.5) / 32.0) * 2.0 - 1.0;
                double ny = ((y + 0.5) / 32.0) * 2.0 - 1.0;
                double r = Math.hypot(nx, ny);
                ring[y * 32 + x] = (r >= 0.48 && r <= 0.76) ? 1f : 0f;
            }
        }
        PatentReverseImageEngine.VisualSignature ringSig = PatentReverseImageEngine.extractFromGray32(ring);
        VisionPriorStore.MatchResult atlasHit = VisionPriorStore.findBestMatchWithAtlas(
                java.util.Collections.emptyList(), atlas, ringSig,
                VisionPriorStore.DEFAULT_MIN_SCORE, VisionPriorStore.ATLAS_MIN_SCORE);
        assertTrue("Expected atlas baseline match on optical lens ring",
                atlasHit != null && atlasHit.prototype.label.contains("Lens Ring"));

        List<VisionPriorStore.Prototype> userStore = VisionPriorStore.teachOrReinforce(
                java.util.Collections.emptyList(), "My Camera Filter Ring", ringSig, "user_confirmed", "", "58 mm", 5000L);
        VisionPriorStore.MatchResult userPriority = VisionPriorStore.findBestMatchWithAtlas(
                userStore, atlas, ringSig,
                VisionPriorStore.DEFAULT_MIN_SCORE, VisionPriorStore.ATLAS_MIN_SCORE);
        assertEquals("My Camera Filter Ring", userPriority.prototype.label);

        // Verify OnDeviceLlmEngine KV-cache clone prefix split & multimodal pack detection
        String fullPrompt = OnDeviceLlmEngine.buildChatMlPrompt("Hello Zoe", java.util.Collections.emptyList(), "", "");
        String delta = OnDeviceLlmEngine.extractClonableDelta(fullPrompt);
        assertTrue(delta != null && delta.contains("Hello Zoe") && !delta.contains("<|im_start|>system"));

        assertTrue(OnDeviceLlmEngine.supportsNativeVision(new java.io.File("gemma-3n-E2B-it-int4-vision.task")));
        assertFalse(OnDeviceLlmEngine.supportsNativeVision(new java.io.File("Qwen2.5-1.5B-Instruct.task")));
    }
}
