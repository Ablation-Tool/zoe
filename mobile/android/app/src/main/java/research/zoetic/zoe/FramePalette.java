package research.zoetic.zoe;

import android.graphics.Bitmap;

import java.util.Locale;

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
        // Flat primitive 512-bucket histogram (zero boxed Integer/HashMap GC churn per frame!)
        int[] bucketCount = new int[512];
        int[] bucketR = new int[512];
        int[] bucketG = new int[512];
        int[] bucketB = new int[512];
        for (int i = 0; i < total; i++) {
            int c = pixels[i];
            int r = (c >>> 16) & 0xff;
            int g = (c >>> 8) & 0xff;
            int b = c & 0xff;
            double luma = (0.2126 * r + 0.7152 * g + 0.0722 * b) * (1.0 / 255.0);
            lumaSum += luma;
            lumaSqSum += luma * luma;
            warmBias += (r - b) * (1.0 / 255.0);

            int key = ((r & 0xE0) << 1) | ((g & 0xE0) >>> 2) | (b >>> 5);
            bucketCount[key]++;
            bucketR[key] += r;
            bucketG[key] += g;
            bucketB[key] += b;
        }
        double meanLuma = lumaSum / total;
        double variance = Math.max(0.0, lumaSqSum / total - meanLuma * meanLuma);
        int brightnessPct = clampPercent(Math.round(meanLuma * 100.0));
        int contrastPct = clampPercent(Math.round(Math.sqrt(variance) * 200.0));
        double meanWarm = warmBias / total;
        String tone = meanWarm > 0.06 ? "Warm light"
                : (meanWarm < -0.06 ? "Cool light" : "Neutral balanced light");

        // Top-3 selection in single linear scan (zero sorting allocations)
        int[] topIdx = new int[]{-1, -1, -1};
        int[] topCnt = new int[]{0, 0, 0};
        for (int k = 0; k < 512; k++) {
            int cnt = bucketCount[k];
            if (cnt <= 0) continue;
            if (cnt > topCnt[0]) {
                topCnt[2] = topCnt[1]; topIdx[2] = topIdx[1];
                topCnt[1] = topCnt[0]; topIdx[1] = topIdx[0];
                topCnt[0] = cnt; topIdx[0] = k;
            } else if (cnt > topCnt[1]) {
                topCnt[2] = topCnt[1]; topIdx[2] = topIdx[1];
                topCnt[1] = cnt; topIdx[1] = k;
            } else if (cnt > topCnt[2]) {
                topCnt[2] = cnt; topIdx[2] = k;
            }
        }
        int count = 0;
        for (int idx : topIdx) {
            if (idx >= 0) count++;
        }
        int[] colors = new int[count];
        String[] hexCodes = new String[count];
        String[] names = new String[count];
        for (int i = 0; i < count; i++) {
            int k = topIdx[i];
            int n = Math.max(1, bucketCount[k]);
            int r = bucketR[k] / n;
            int g = bucketG[k] / n;
            int b = bucketB[k] / n;
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
