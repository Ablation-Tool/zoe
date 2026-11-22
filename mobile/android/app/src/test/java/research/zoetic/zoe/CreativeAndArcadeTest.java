package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;
import java.util.Random;

public class CreativeAndArcadeTest {
    @Test
    public void parsesPlainEnglishImageEditCommandsAndResetsCleanly() {
        ImageLabEngine.EditSpec spec = ImageLabEngine.parseEditCommand(
                "make it warm, brighter, more contrast, rotate, square, blur privacy, caption Monterey Sunset",
                new ImageLabEngine.EditSpec());
        assertEquals(ImageLabEngine.FilterPreset.WARM_ATELIER, spec.filter);
        assertEquals(24, spec.brightness);
        assertTrue(spec.contrast > 1.2f);
        assertEquals(90, spec.rotationDeg);
        assertEquals(ImageLabEngine.CropMode.SQUARE, spec.crop);
        assertTrue(spec.privacyBlur);
        assertEquals("Monterey Sunset", spec.caption);

        ImageLabEngine.EditSpec noir = ImageLabEngine.parseEditCommand("black and white and unblur", spec);
        assertEquals(ImageLabEngine.FilterPreset.NOIR_BW, noir.filter);
        assertFalse(noir.privacyBlur);

        ImageLabEngine.EditSpec reset = ImageLabEngine.parseEditCommand("reset", noir);
        assertEquals(ImageLabEngine.FilterPreset.ORIGINAL, reset.filter);
        assertEquals(0, reset.rotationDeg);
        assertEquals("", reset.caption);

        // v0.9.4 Pro Studio additions: vellum/blueprint filters, flip, portrait 4:5, vignette, warmth, CFR video timestamps & AI provider selection
        ImageLabEngine.EditSpec pro = ImageLabEngine.parseEditCommand(
                "vellum, warmer, vignette, mirror, 4:5 portrait", new ImageLabEngine.EditSpec());
        assertEquals(ImageLabEngine.FilterPreset.ARCHIVAL_VELLUM, pro.filter);
        assertEquals(16, pro.warmth);
        assertEquals(48, pro.vignette);
        assertTrue(pro.flipHorizontal);
        assertEquals(ImageLabEngine.CropMode.PORTRAIT_4_5, pro.crop);
        assertTrue(pro.summary().contains("vignette 48%"));
        assertTrue(pro.summary().contains("mirror"));

        assertEquals(ScientificVisualSubstrate.BaselinePlate.CHLADNI_PLATE,
                ScientificVisualSubstrate.detectPlateFromCommand("chladni standing wave"));
        assertEquals(ScientificVisualSubstrate.BaselinePlate.FIBONACCI_PHYLLOTAXIS,
                ScientificVisualSubstrate.detectPlateFromCommand("fibonacci phyllotaxis rosette"));
        assertEquals(ScientificVisualSubstrate.BaselinePlate.VORONOI_CRYSTAL,
                ScientificVisualSubstrate.detectPlateFromCommand("voronoi crystal tessellation"));
        assertEquals(ScientificVisualSubstrate.BaselinePlate.LISSAJOUS_ORBIT,
                ScientificVisualSubstrate.detectPlateFromCommand("lissajous harmonic orbit"));
        assertEquals(2, ScientificVisualSubstrate.chladniModesForSeed(42).length);
        assertEquals(2, ScientificVisualSubstrate.lissajousRatiosForSeed(42).length);

        // v0.9.5 filters, vector ink strokes deep-copy & 6th video style
        assertEquals(ImageLabEngine.FilterPreset.GOLDEN_HOUR,
                ImageLabEngine.parseEditCommand("golden hour", new ImageLabEngine.EditSpec()).filter);
        assertEquals(ImageLabEngine.FilterPreset.CYBER_NEON,
                ImageLabEngine.parseEditCommand("cyber neon", new ImageLabEngine.EditSpec()).filter);
        assertEquals(ImageLabEngine.FilterPreset.MATTE_FILM,
                ImageLabEngine.parseEditCommand("matte film", new ImageLabEngine.EditSpec()).filter);
        ImageLabEngine.EditSpec inked = new ImageLabEngine.EditSpec();
        ImageLabEngine.BrushStroke st = new ImageLabEngine.BrushStroke(0xFFFFD666, 0.012f);
        st.points.add(new float[]{0.2f, 0.3f});
        st.points.add(new float[]{0.8f, 0.7f});
        inked.strokes.add(st);
        ImageLabEngine.EditSpec inkedCopy = inked.copy();
        inkedCopy.strokes.clear();
        assertEquals(1, inked.strokes.size());
        assertTrue(inked.summary().contains("1 stroke"));
        assertEquals(6, VideoMakerEngine.Style.values().length);
        assertEquals("Lissajous Orbit", VideoMakerEngine.Style.LISSAJOUS_ORBIT.label);

        assertEquals(0L, VideoMakerEngine.framePresentationTimeUs(0, 30));
        assertEquals(1_000_000L, VideoMakerEngine.framePresentationTimeUs(30, 30));
        assertEquals(4_000_000L, VideoMakerEngine.framePresentationTimeUs(120, 30));
        assertEquals("gemini", ImageLabEngine.selectOnlineImageProvider("gem-key", "oa-key"));
        assertEquals("openai", ImageLabEngine.selectOnlineImageProvider("", "oa-key"));
        assertEquals("none", ImageLabEngine.selectOnlineImageProvider("", ""));
    }

    @Test
    public void arcadeMemoryMinimaxSignalPuzzleAndTwentyQuestionsWorkOffline() {
        List<Integer> seq = ArcadeEngine.nextMemoryRound(null, new Random(7));
        assertEquals(1, seq.size());
        seq = ArcadeEngine.nextMemoryRound(seq, new Random(7));
        assertEquals(2, seq.size());

        // Minimax must block an immediate X win on cell 2
        int[] blockBoard = {1, 1, 0, 0, 2, 0, 0, 0, 0};
        assertEquals(2, ArcadeEngine.chooseZoeMove(blockBoard, true, new Random(1)));

        // Minimax must take an immediate O winning move on cell 5
        int[] winBoard = {1, 0, 1, 2, 2, 0, 0, 0, 1};
        assertEquals(5, ArcadeEngine.chooseZoeMove(winBoard, true, new Random(1)));

        int[] xWins = {1, 1, 1, 2, 2, 0, 0, 0, 0};
        assertEquals(1, ArcadeEngine.checkWinner(xWins));
        int[] line = ArcadeEngine.winningLine(xWins);
        assertEquals(0, line[0]);
        assertEquals(1, line[1]);
        assertEquals(2, line[2]);

        // Strict Kloster A_tau(p) puzzle (equality excluded!)
        ArcadeEngine.SignalPuzzle puz = new ArcadeEngine.SignalPuzzle(new double[]{0.40, 0.25, 0.20, 0.10, 0.05}, 2);
        assertEquals(2, puz.evaluateCount(0.20)); // strictly > 0.20 => 0.40 and 0.25 only!
        assertEquals(3, puz.evaluateCount(0.15));

        ArcadeEngine.MysteryItem otter = ArcadeEngine.MYSTERY_DECK.get(0);
        assertTrue(ArcadeEngine.answerTwentyQuestions(otter, "Is it alive?").startsWith("Yes"));
        assertTrue(ArcadeEngine.answerTwentyQuestions(otter, "Is it a Sea Otter?").contains("YES!"));

        short[] pcm = ArcadeEngine.synthesizeChimePcm(523.25, 120);
        assertTrue(pcm.length > 4000);
        assertEquals("1:05", MediaChatHelper.formatDurationMs(65_000L));
        assertEquals("8s", MediaChatHelper.formatDurationMs(8_000L));
    }

    @Test
    public void signalGradeCryptoSealsUnsealsRatchetsComputesSafetyNumberAndHiZoeWakeWord() throws Exception {
        java.security.KeyPair alice = ZoeSignalCrypto.generateIdentityKeyPair();
        java.security.KeyPair bob = ZoeSignalCrypto.generateIdentityKeyPair();

        // 2-party ECDH + HKDF-SHA256 + Symmetric Ratchet + AES-256-GCM envelope
        String sealed = ZoeSignalCrypto.sealForPeer(bob.getPublic(), "Private Monterey field note 42");
        assertTrue(sealed.startsWith(ZoeSignalCrypto.ENVELOPE_PREFIX));
        assertFalse(sealed.contains("Monterey"));
        assertEquals("Private Monterey field note 42", ZoeSignalCrypto.openFromPeer(bob.getPrivate(), sealed));

        // Wrong key must fail GCM authentication
        boolean rejected = false;
        try {
            ZoeSignalCrypto.openFromPeer(alice.getPrivate(), sealed);
        } catch (Exception expected) {
            rejected = true;
        }
        assertTrue(rejected);

        // Signal-style 60-digit Safety Number must be symmetric across both peers
        String fpAB = ZoeSignalCrypto.computeSafetyNumber(alice.getPublic().getEncoded(), bob.getPublic().getEncoded());
        String fpBA = ZoeSignalCrypto.computeSafetyNumber(bob.getPublic().getEncoded(), alice.getPublic().getEncoded());
        assertEquals(fpAB, fpBA);
        assertEquals(60, fpAB.replaceAll("\\s+", "").length());

        // Symmetric chain ratchet advances deterministically without reusing keys
        byte[] seed = new byte[32];
        Arrays.fill(seed, (byte) 0x5A);
        ZoeSignalCrypto.RatchetStep s1 = ZoeSignalCrypto.ratchetSymmetricChain(seed);
        ZoeSignalCrypto.RatchetStep s2 = ZoeSignalCrypto.ratchetSymmetricChain(s1.nextChainKey);
        assertFalse(Arrays.equals(s1.messageKey, s2.messageKey));
        assertFalse(Arrays.equals(s1.nextChainKey, s2.nextChainKey));

        // "Hi Zoe" wake-word trigger & prefix stripping
        assertTrue(WakeWordDetector.isHiZoeTrigger("Hi Zoe"));
        assertTrue(WakeWordDetector.isHiZoeTrigger("Hey Zoe, let's explore space!"));
        assertFalse(WakeWordDetector.isHiZoeTrigger("Tell me about rainbows"));
        assertEquals("let's explore space!", WakeWordDetector.stripWakePrefix("Hey Zoe, let's explore space!"));
    }
}
