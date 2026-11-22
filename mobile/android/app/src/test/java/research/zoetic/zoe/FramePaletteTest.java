package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class FramePaletteTest {
    @Test
    public void analyzesDominantColorsBrightnessAndTone() {
        int[] pixels = new int[16];
        int crimson = 0xFFDC283C;
        int cyan = 0xFF40D8E0;
        for (int i = 0; i < 12; i++) {
            pixels[i] = crimson;
        }
        for (int i = 12; i < 16; i++) {
            pixels[i] = cyan;
        }
        FramePalette.Analysis analysis = FramePalette.analyzeArgb(pixels, 4, 4);
        assertTrue(analysis.brightnessPercent > 20 && analysis.brightnessPercent < 80);
        assertTrue(analysis.contrastPercent >= 0);
        assertEquals("Crimson", analysis.names[0]);
        assertTrue(analysis.summary().contains("Light "));
        assertTrue(analysis.summary().contains("Palette: "));
    }

    @Test
    public void classifiesObsidianForDarkPixels() {
        int[] pixels = {0xFF070D18, 0xFF080E1A, 0xFF060B14, 0xFF091020};
        FramePalette.Analysis analysis = FramePalette.analyzeArgb(pixels, 2, 2);
        assertEquals("Obsidian", analysis.names[0]);
        assertTrue(analysis.brightnessPercent < 15);
    }
}
