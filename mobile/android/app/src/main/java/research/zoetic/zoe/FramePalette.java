package research.zoetic.zoe;

import android.graphics.Bitmap;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class FramePalette {
    static final class Analysis {
        final int brightnessPercent;
        final int contrastPercent;
        final String tone;
        final int[] colors;
        final String[] hexCodes;
        final String[] names;

        Analysis(int brightnessPercent, int contrastPercent, String tone,
                 int[] colors, String[] hexCodes, String[] names) {
            this.brightnessPercent = brightnessPercent;
            this.contrastPercent = contrastPercent;
            this.tone = tone;
            this.colors = colors;
            this.hexCodes = hexCodes;
            this.names = names;
        }

        String summary() {
            StringBuilder out = new StringBuilder();
            for (int i = 0; i < hexCodes.length; i++) {
                if (i > 0) {
                    out.append(" · ");
                }
                out.append(names[i]).append(" ").append(hexCodes[i]);
            }
            return String.format(Locale.US,
                    "Light %d%% · Contrast %d%% · %s\nPalette: %s",
                    brightnessPercent, contrastPercent, tone, out);
        }
    }

    private FramePalette() {
    }

    static Analysis analyzeBitmap(Bitmap bitmap) {
        if (bitmap == null || bitmap.getWidth() <= 0 || bitmap.getHeight() <= 0) {
            throw new IllegalArgumentException("Bitmap is empty");
        }
        int targetW = Math.min(64, bitmap.getWidth());
        int targetH = Math.min(64, bitmap.getHeight());
        Bitmap sample = (bitmap.getWidth() == targetW && bitmap.getHeight() == targetH)
                ? bitmap
                : Bitmap.createScaledBitmap(bitmap, targetW, targetH, true);
        int[] pixels = new int[targetW * targetH];
        sample.getPixels(pixels, 0, targetW, 0, 0, targetW, targetH);
        if (sample != bitmap) {
            sample.recycle();
        }
        return analyzeArgb(pixels, targetW, targetH);
    }

    static Analysis analyzeArgb(int[] pixels, int width, int height) {
        if (pixels == null || width <= 0 || height <= 0 || pixels.length < width * height) {
            throw new IllegalArgumentException("Valid pixel array is required");
        }
        int total = width * height;
        double lumaSum = 0.0;
        double lumaSqSum = 0.0;
        double warmBias = 0.0;
        Map<Integer, int[]> buckets = new HashMap<>();
        for (int i = 0; i < total; i++) {
            int c = pixels[i];
            int r = (c >>> 16) & 0xff;
            int g = (c >>> 8) & 0xff;
            int b = c & 0xff;
            double luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0;
            lumaSum += luma;
            lumaSqSum += luma * luma;
            warmBias += (r - b) / 255.0;

            int qr = (r >> 5) & 0x7;
            int qg = (g >> 5) & 0x7;
            int qb = (b >> 5) & 0x7;
            int key = (qr << 6) | (qg << 3) | qb;
            int[] acc = buckets.get(key);
            if (acc == null) {
                acc = new int[4];
                buckets.put(key, acc);
            }
            acc[0]++;
            acc[1] += r;
            acc[2] += g;
            acc[3] += b;
        }
        double meanLuma = lumaSum / total;
        double variance = Math.max(0.0, lumaSqSum / total - meanLuma * meanLuma);
        int brightnessPct = clampPercent(Math.round(meanLuma * 100.0));
        int contrastPct = clampPercent(Math.round(Math.sqrt(variance) * 200.0));
        double meanWarm = warmBias / total;
        String tone = meanWarm > 0.06 ? "Warm light"
                : (meanWarm < -0.06 ? "Cool light" : "Neutral balanced light");

        List<int[]> ranked = new ArrayList<>(buckets.values());
        ranked.sort((a, b) -> Integer.compare(b[0], a[0]));
        int count = Math.min(3, ranked.size());
        int[] colors = new int[count];
        String[] hexCodes = new String[count];
        String[] names = new String[count];
        for (int i = 0; i < count; i++) {
            int[] acc = ranked.get(i);
            int n = Math.max(1, acc[0]);
            int r = acc[1] / n;
            int g = acc[2] / n;
            int b = acc[3] / n;
            colors[i] = (0xff << 24) | (r << 16) | (g << 8) | b;
            hexCodes[i] = String.format(Locale.US, "#%02X%02X%02X", r, g, b);
            names[i] = colorName(r, g, b);
        }
        return new Analysis(brightnessPct, contrastPct, tone, colors, hexCodes, names);
    }

    static String colorName(int r, int g, int b) {
        int max = Math.max(r, Math.max(g, b));
        int min = Math.min(r, Math.min(g, b));
        int delta = max - min;
        if (max < 42) {
            return "Obsidian";
        }
        if (delta < 24) {
            if (max > 210) {
                return "Ivory";
            }
            return max > 120 ? "Silver" : "Slate";
        }
        double hue;
        if (max == r) {
            hue = 60.0 * (((double) (g - b) / delta) % 6.0);
        } else if (max == g) {
            hue = 60.0 * (((double) (b - r) / delta) + 2.0);
        } else {
            hue = 60.0 * (((double) (r - g) / delta) + 4.0);
        }
        if (hue < 0) {
            hue += 360.0;
        }
        if (hue < 18 || hue >= 340) {
            return max > 180 ? "Crimson" : "Garnet";
        }
        if (hue < 45) {
            return "Amber";
        }
        if (hue < 72) {
            return "Gold";
        }
        if (hue < 160) {
            return "Emerald";
        }
        if (hue < 205) {
            return "Cyan";
        }
        if (hue < 258) {
            return "Cobalt";
        }
        if (hue < 305) {
            return "Violet";
        }
        return "Orchid";
    }

    private static int clampPercent(long value) {
        return (int) Math.max(0, Math.min(100, value));
    }
}
