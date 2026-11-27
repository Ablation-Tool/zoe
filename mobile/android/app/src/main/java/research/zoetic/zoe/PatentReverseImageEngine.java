package research.zoetic.zoe;

import android.graphics.Bitmap;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * On-Device Visual Contour / Edge Reverse-Image Engine for Google Patents Schematics (v0.9.1-beta).
 *
 * Patent drawings on patents.google.com are monochrome structural line drawings, while live camera
 * frames are full-color photos. To reverse-image match an unfamiliar real-world object against
 * patent drawings accurately on-device:
 *   1. Center-weights the live object & normalizes to a 32x32 grayscale luminance grid.
 *   2. Applies Sobel gradient magnitude + orientation so color/lighting disappear and ONLY pure
 *      structural contours remain (matching black-and-white patent line art!).
 *   3. Extracts a 4-part VisualSignature:
 *        - 16-bin L2-normalized Edge Orientation Histogram (HoG-16)
 *        - 8-ring Concentric Radial Edge Energy Profile
 *        - 64-bit Perceptual Edge Difference Hash (dHash-64)
 *        - Structural Bounding Aspect Ratio, Symmetry & Circularity -> Morphology Query Keywords
 *   4. Re-ranks live candidate patent drawings downloaded from patentimages.storage.googleapis.com
 *      by true visual contour similarity (0%–100%).
 *
 * Pure luminance-array math is 100% JVM unit-testable with zero Android framework dependency.
 */
final class PatentReverseImageEngine {
    static final int GRID_SIZE = 32;

    private static final Pattern LABEL_CONF_PATTERN = Pattern.compile("([A-Za-z][A-Za-z0-9\\s\\-/]{1,36})\\s*\\((\\d{1,3})%\\)");
    private static final Set<String> GENERIC_VAGUE_LABELS = new HashSet<>(Arrays.asList(
            "product", "gadget", "machine", "material", "plastic", "metal", "steel", "aluminum",
            "hardware", "tool", "device", "electronic device", "electronics", "object", "component",
            "artifact", "auto part", "part", "equipment", "appliance", "home appliance", "pattern",
            "design", "wood", "glass", "rectangle", "circle", "cylinder", "sphere", "line",
            "font", "symbol", "logo", "brand", "technology", "engineering", "mechanism", "instrument",
            "accessory", "furniture", "fixture", "container", "handle", "cable", "wire"
    ));

    static final class VisualSignature {
        final float[] hog16;
        final float[] radial8;
        final long dHash64;
        final float aspectRatio;
        final float bilateralSymmetry;
        final float orthogonalRatio;
        final float edgeDensity;
        final String morphologyKeywords;
        final String shapeSummary;

        VisualSignature(float[] hog16, float[] radial8, long dHash64, float aspectRatio,
                        float bilateralSymmetry, float orthogonalRatio, float edgeDensity,
                        String morphologyKeywords, String shapeSummary) {
            this.hog16 = hog16;
            this.radial8 = radial8;
            this.dHash64 = dHash64;
            this.aspectRatio = aspectRatio;
            this.bilateralSymmetry = bilateralSymmetry;
            this.orthogonalRatio = orthogonalRatio;
            this.edgeDensity = edgeDensity;
            this.morphologyKeywords = morphologyKeywords == null ? "" : morphologyKeywords;
            this.shapeSummary = shapeSummary == null ? "" : shapeSummary;
        }
    }

    private PatentReverseImageEngine() {
    }

    /**
     * Returns true when Zoe's offline ML Kit vision cannot confidently identify the object
     * (missing labels, confidence < 72%, or only vague generic classes like "Product"/"Metal"/"Gadget"),
     * signaling that Zoe should reverse-image match the camera edges against Google Patents!
     */
    static boolean isHardToIdentify(String offlineReport) {
        if (offlineReport == null || offlineReport.trim().isEmpty()) {
            return true;
        }
        String lower = offlineReport.toLowerCase(Locale.US);
        if (lower.contains("none above") || !lower.contains("labels:")) {
            return true;
        }
        int idx = offlineReport.indexOf("Labels:");
        String section = offlineReport.substring(idx + "Labels:".length());
        int dot = section.indexOf('.');
        if (dot > 0) {
            section = section.substring(0, dot);
        }
        Matcher m = LABEL_CONF_PATTERN.matcher(section);
        int topConf = 0;
        boolean foundSpecific = false;
        while (m.find()) {
            String lbl = m.group(1).trim().toLowerCase(Locale.US);
            int conf = 0;
            try {
                conf = Integer.parseInt(m.group(2));
            } catch (NumberFormatException ignored) {
            }
            if (conf > topConf) {
                topConf = conf;
            }
            if (!GENERIC_VAGUE_LABELS.contains(lbl) && conf >= 72) {
                foundSpecific = true;
            }
        }
        return !foundSpecific || topConf < 72;
    }

    /**
     * Extracts a VisualSignature directly from an Android Bitmap using bilinear area-averaged
     * downscaling + ONE bulk getPixels() transfer (~10x faster than 1,024 JNI getPixel calls,
     * and anti-aliased so thin contours stay crisp across camera angles).
     */
    static VisualSignature extractFromBitmap(Bitmap bmp, boolean centerCropForCamera) {
        if (bmp == null || bmp.isRecycled() || bmp.getWidth() < 4 || bmp.getHeight() < 4) {
            return null;
        }
        int w = bmp.getWidth();
        int h = bmp.getHeight();
        int left = centerCropForCamera ? Math.round(w * 0.09f) : 0;
        int top = centerCropForCamera ? Math.round(h * 0.09f) : 0;
        int cropW = Math.max(4, w - left * 2);
        int cropH = Math.max(4, h - top * 2);

        Bitmap cropped = null;
        Bitmap grid = null;
        try {
            Bitmap src = bmp;
            if (left > 0 || top > 0) {
                cropped = Bitmap.createBitmap(bmp, left, top, cropW, cropH);
                src = cropped;
            }
            grid = Bitmap.createScaledBitmap(src, GRID_SIZE, GRID_SIZE, true);
            int[] pixels = new int[GRID_SIZE * GRID_SIZE];
            grid.getPixels(pixels, 0, GRID_SIZE, 0, 0, GRID_SIZE, GRID_SIZE);
            float[] gray = new float[GRID_SIZE * GRID_SIZE];
            for (int i = 0; i < pixels.length; i++) {
                int px = pixels[i];
                int r = (px >>> 16) & 0xFF;
                int g = (px >>> 8) & 0xFF;
                int b = px & 0xFF;
                gray[i] = (0.299f * r + 0.587f * g + 0.114f * b) * (1.0f / 255.0f);
            }
            return extractFromGray32(gray);
        } finally {
            if (grid != null && grid != bmp && grid != cropped && !grid.isRecycled()) {
                grid.recycle();
            }
            if (cropped != null && cropped != bmp && !cropped.isRecycled()) {
                cropped.recycle();
            }
        }
    }

    /**
     * Pure JVM-testable edge/contour extractor on a 32x32 luminance grid [0..1] with adaptive
     * contrast normalization for illumination invariance across dim rooms and bright sunlight.
     */
    static VisualSignature extractFromGray32(float[] rawGray) {
        if (rawGray == null || rawGray.length != GRID_SIZE * GRID_SIZE) {
            return null;
        }
        // Illumination-invariant min-max stretch when dynamic range is non-trivial
        float minL = Float.MAX_VALUE;
        float maxL = -Float.MAX_VALUE;
        for (float v : rawGray) {
            if (v < minL) minL = v;
            if (v > maxL) maxL = v;
        }
        float[] gray = rawGray;
        float span = maxL - minL;
        if (span > 0.08f && (minL > 0.02f || maxL < 0.98f)) {
            gray = new float[rawGray.length];
            float inv = 1.0f / span;
            for (int i = 0; i < rawGray.length; i++) {
                gray[i] = (rawGray[i] - minL) * inv;
            }
        }
        float[] mag = new float[GRID_SIZE * GRID_SIZE];
        float[] hog = new float[16];
        float[] radial = new float[8];

        float maxMag = 1e-5f;
        float sumMag = 0f;
        float center = (GRID_SIZE - 1) * 0.5f;
        float maxRadius = center * 1.4142f;

        for (int y = 1; y < GRID_SIZE - 1; y++) {
            for (int x = 1; x < GRID_SIZE - 1; x++) {
                float gx = -gray[(y - 1) * GRID_SIZE + (x - 1)] + gray[(y - 1) * GRID_SIZE + (x + 1)]
                        - 2f * gray[y * GRID_SIZE + (x - 1)] + 2f * gray[y * GRID_SIZE + (x + 1)]
                        - gray[(y + 1) * GRID_SIZE + (x - 1)] + gray[(y + 1) * GRID_SIZE + (x + 1)];
                float gy = -gray[(y - 1) * GRID_SIZE + (x - 1)] - 2f * gray[(y - 1) * GRID_SIZE + x] - gray[(y - 1) * GRID_SIZE + (x + 1)]
                        + gray[(y + 1) * GRID_SIZE + (x - 1)] + 2f * gray[(y + 1) * GRID_SIZE + x] + gray[(y + 1) * GRID_SIZE + (x + 1)];
                float m = (float) Math.sqrt(gx * gx + gy * gy);
                mag[y * GRID_SIZE + x] = m;
                if (m > maxMag) {
                    maxMag = m;
                }
                sumMag += m;

                // Orientation in [0, pi) quantized into 16 bins
                double angle = Math.atan2(gy, gx);
                if (angle < 0) angle += Math.PI;
                int bin = Math.min(15, Math.max(0, (int) ((angle / Math.PI) * 16.0)));
                hog[bin] += m;

                float dist = (float) Math.hypot(x - center, y - center);
                int rBin = Math.min(7, Math.max(0, (int) ((dist / maxRadius) * 8.0f)));
                radial[rBin] += m;
            }
        }

        // Compute active contour bounding box & bilateral edge symmetry
        float thresh = Math.max(0.08f, maxMag * 0.24f);
        int minX = GRID_SIZE, maxX = 0, minY = GRID_SIZE, maxY = 0;
        int activeCount = 0;
        float symNum = 0f, symDen = 1e-5f;
        for (int y = 1; y < GRID_SIZE - 1; y++) {
            for (int x = 1; x < GRID_SIZE - 1; x++) {
                float m = mag[y * GRID_SIZE + x];
                if (m >= thresh) {
                    activeCount++;
                    if (x < minX) minX = x;
                    if (x > maxX) maxX = x;
                    if (y < minY) minY = y;
                    if (y > maxY) maxY = y;
                }
                float mirrorM = mag[y * GRID_SIZE + (GRID_SIZE - 1 - x)];
                symNum += Math.min(m, mirrorM);
                symDen += Math.max(m, mirrorM);
            }
        }
        float bboxW = maxX >= minX ? (maxX - minX + 1) : GRID_SIZE;
        float bboxH = maxY >= minY ? (maxY - minY + 1) : GRID_SIZE;
        float aspect = bboxW / Math.max(1f, bboxH);
        float symmetry = Math.max(0f, Math.min(1f, symNum / symDen));
        float density = activeCount / (float) ((GRID_SIZE - 2) * (GRID_SIZE - 2));

        // Orthogonal energy ratio (bins near 0°, 90°, 180°)
        float totalHog = 1e-5f;
        for (float v : hog) totalHog += v;
        float orthoRatio = (hog[0] + hog[7] + hog[8] + hog[15]) / totalHog;

        l2Normalize(hog);
        l2Normalize(radial);

        // 64-bit Perceptual Edge Difference Hash (9x8 downsampled edge grid)
        float[][] grid9x8 = new float[8][9];
        for (int row = 0; row < 8; row++) {
            for (int col = 0; col < 9; col++) {
                float acc = 0f;
                int y0 = row * 4;
                int x0 = Math.min(GRID_SIZE - 3, (col * GRID_SIZE) / 9);
                for (int dy = 0; dy < 4; dy++) {
                    for (int dx = 0; dx < 3; dx++) {
                        acc += mag[(y0 + dy) * GRID_SIZE + Math.min(GRID_SIZE - 1, x0 + dx)];
                    }
                }
                grid9x8[row][col] = acc;
            }
        }
        long dHash = 0L;
        int bit = 0;
        for (int row = 0; row < 8; row++) {
            for (int col = 0; col < 8; col++) {
                if (grid9x8[row][col] > grid9x8[row][col + 1]) {
                    dHash |= (1L << bit);
                }
                bit++;
            }
        }

        // Infer structural morphology query terms directly from contour geometry
        String keywords;
        String summary;
        if (aspect > 1.65f || aspect < 0.60f) {
            keywords = "elongated shaft lever handle bracket linkage tool";
            summary = String.format(Locale.US, "elongated contour (%.1f:1, %.0f%% symmetric)", aspect, symmetry * 100f);
        } else if (orthoRatio < 0.29f && symmetry > 0.56f) {
            keywords = "circular rotary ring lens gear bearing hub mechanism";
            summary = String.format(Locale.US, "radial/circular contour (%.0f%% symmetric)", symmetry * 100f);
        } else if (orthoRatio >= 0.44f) {
            keywords = "rectangular housing enclosure module panel bracket connector";
            summary = String.format(Locale.US, "orthogonal housing contour (%.0f%% rectilinear)", orthoRatio * 100f);
        } else if (symmetry > 0.62f) {
            keywords = "symmetrical clamp hinge valve optical prism assembly";
            summary = String.format(Locale.US, "bilaterally symmetric mechanism (%.0f%%)", symmetry * 100f);
        } else {
            keywords = "mechanical structural device assembly apparatus";
            summary = String.format(Locale.US, "complex structural contour (density %.0f%%)", density * 100f);
        }

        return new VisualSignature(hog, radial, dHash, aspect, symmetry, orthoRatio, density, keywords, summary);
    }

    /**
     * Computes visual structural similarity in [0.0, 1.0] between a live camera edge signature
     * and a Google Patents schematic drawing signature.
     */
    static float compareSignatures(VisualSignature a, VisualSignature b) {
        if (a == null || b == null) {
            return 0f;
        }
        float hogSim = Math.max(0f, dot(a.hog16, b.hog16));
        float radSim = Math.max(0f, dot(a.radial8, b.radial8));
        int hamming = Long.bitCount(a.dHash64 ^ b.dHash64);
        float hashSim = 1.0f - (hamming / 64.0f);

        float aspectRatioMin = Math.min(a.aspectRatio, b.aspectRatio);
        float aspectRatioMax = Math.max(0.01f, Math.max(a.aspectRatio, b.aspectRatio));
        float aspectSim = aspectRatioMin / aspectRatioMax;
        float symSim = 1.0f - Math.abs(a.bilateralSymmetry - b.bilateralSymmetry);
        float geomSim = 0.55f * aspectSim + 0.45f * symSim;

        float score = 0.40f * hogSim + 0.25f * radSim + 0.20f * hashSim + 0.15f * geomSim;
        return Math.max(0f, Math.min(1f, score));
    }

    private static void l2Normalize(float[] vec) {
        double sumSq = 0.0;
        for (float v : vec) {
            sumSq += v * v;
        }
        float norm = (float) Math.sqrt(sumSq);
        if (norm > 1e-6f) {
            for (int i = 0; i < vec.length; i++) {
                vec[i] /= norm;
            }
        }
    }

    private static float dot(float[] a, float[] b) {
        int n = Math.min(a.length, b.length);
        float sum = 0f;
        for (int i = 0; i < n; i++) {
            sum += a[i] * b[i];
        }
        return sum;
    }
}
