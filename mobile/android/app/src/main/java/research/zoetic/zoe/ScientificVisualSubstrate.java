package research.zoetic.zoe;

import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.DashPathEffect;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.RadialGradient;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;

import java.util.Locale;

/**
 * Zoe Scientific-Aesthetic Visual Substrate (v0.9.4-beta).
 *
 * Grounds Zoe's image generation & visual reasoning on factual, mathematically structured,
 * public-domain scientific artistry, wave physics, phyllotaxis, and engineering schematics:
 *   - Ernst Haeckel (1834–1919), Kunstformen der Natur (1899–1904):
 *       dihedral D_n radiolarian lattices, golden-angle phyllotaxis (137.507764°),
 *       and logarithmic ammonite spirals r(θ) = a·e^(bθ).
 *   - August Weismann (1834–1914), Das Keimplasma (1892):
 *       cytological germ-line/soma inheritance architecture and hyperbolic mitotic spindles.
 *   - Jean-Baptiste Lamarck (1744–1829), Philosophie Zoologique (1809):
 *       comparative anatomical morphospace & continuous structural branching series.
 *   - Google Patents Public Catalog (patents.google.com):
 *       orthographic schematics, involute gear & optical prism ray-tracing blueprints,
 *       dimensional callouts, and real-world physical scale reference comparisons.
 *   - Ernst Chladni (1787) Standing-Wave Nodal Eigenmodes & Vogel Fibonacci Phyllotaxis (13, 21).
 *
 * 100% deterministic and offline for procedural HD plate generation; also augments optional online
 * AI image prompts with factual geometry, symmetry, and historical plate lineage.
 */
final class ScientificVisualSubstrate {
    static final double GOLDEN_RATIO = 1.61803398875;
    static final double GOLDEN_ANGLE_DEG = 137.50776405;
    static final double GOLDEN_ANGLE_RAD = Math.toRadians(GOLDEN_ANGLE_DEG);

    enum BaselinePlate {
        ATELIER("✦ Atelier", "Monterey Coastal Atelier", "Horizon composition · Chladni rings"),
        HAECKEL_RADIOLARIA("🐚 Haeckel", "Ernst Haeckel · Kunstformen der Natur (1899)", "Dihedral D_n silica lattice · Golden angle 137.508°"),
        HAECKEL_AMMONITE("🌀 Ammonite", "Ernst Haeckel · Cephalopoda Spiral (1899)", "Logarithmic spiral r = a·e^(bθ) · φ = 1.618"),
        WEISMANN_GERMPLASM("🧬 Weismann", "August Weismann · Das Keimplasma (1892)", "Germ-line symmetry · Mitotic spindle field"),
        LAMARCK_MORPHOSPACE("🌿 Lamarck", "Jean-Baptiste Lamarck · Philosophie Zoologique (1809)", "Comparative anatomy · Continuous morphospace"),
        PATENT_BLUEPRINT("📐 Patent", "Orthographic Patent Schematic (patents.google.com)", "Involute gear + prism optics · Orthographic callouts"),
        CHLADNI_PLATE("✨ Chladni", "Ernst Chladni · Acoustic Nodal Plate (1787)", "Standing wave cos(mπx)cos(nπy) − cos(nπx)cos(mπy) = 0"),
        FIBONACCI_PHYLLOTAXIS("🌸 Phyllotaxis", "Botanical Vogel Spiral · Fibonacci (13, 21)", "Golden divergence 137.508° · Counter-rotating parastichies");

        final String chipLabel;
        final String lineage;
        final String mathSummary;

        BaselinePlate(String chipLabel, String lineage, String mathSummary) {
            this.chipLabel = chipLabel;
            this.lineage = lineage;
            this.mathSummary = mathSummary;
        }
    }

    static final class ScaleReference {
        final String name;
        final float meters;

        ScaleReference(String name, float meters) {
            this.name = name;
            this.meters = meters;
        }
    }

    private static final ScaleReference[] REAL_WORLD_SCALES = {
            new ScaleReference("standard AA battery", 0.0505f),
            new ScaleReference("credit card width", 0.0856f),
            new ScaleReference("soda can height", 0.122f),
            new ScaleReference("modern smartphone", 0.155f),
            new ScaleReference("A4 / US Letter sheet", 0.297f),
            new ScaleReference("laptop screen width", 0.34f),
            new ScaleReference("standard desk height", 0.74f),
            new ScaleReference("acoustic guitar", 1.00f),
            new ScaleReference("standard doorway height", 2.03f)
    };

    private ScientificVisualSubstrate() {
    }

    // --- Pure Mathematical & Prompt-Grounding Helpers (100% JVM Unit-Testable!) ---

    static int deterministicSeed(String concept) {
        if (concept == null || concept.trim().isEmpty()) {
            return 1899;
        }
        int h = 0x811c9dc5;
        String norm = concept.trim().toLowerCase(Locale.US);
        for (int i = 0; i < norm.length(); i++) {
            h ^= norm.charAt(i);
            h *= 16777619;
        }
        return h & 0x7FFFFFFF;
    }

    static int symmetryOrderForSeed(int seed) {
        int[] orders = {6, 8, 10, 12, 14, 16};
        return orders[Math.abs(seed) % orders.length];
    }

    static double[] phyllotaxisPoint(int index, double scale) {
        double r = scale * Math.sqrt(Math.max(0, index));
        double theta = index * GOLDEN_ANGLE_RAD;
        return new double[]{r * Math.cos(theta), r * Math.sin(theta)};
    }

    static double[] logarithmicSpiralPoint(double thetaRad, double a, double b) {
        double r = a * Math.exp(b * thetaRad);
        return new double[]{r * Math.cos(thetaRad), r * Math.sin(thetaRad)};
    }

    static int[] chladniModesForSeed(int seed) {
        int[][] pairs = {{2, 5}, {3, 5}, {3, 7}, {4, 7}, {2, 7}, {5, 8}};
        return pairs[Math.abs(seed) % pairs.length];
    }

    static BaselinePlate detectPlateFromCommand(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return null;
        }
        String lower = raw.toLowerCase(Locale.US);
        if (lower.contains("haeckel") || lower.contains("radiolaria") || lower.contains("kunstformen") || lower.contains("lithograph")) {
            return BaselinePlate.HAECKEL_RADIOLARIA;
        }
        if (lower.contains("ammonite") || lower.contains("nautilus") || lower.contains("spiral") || lower.contains("medusa")) {
            return BaselinePlate.HAECKEL_AMMONITE;
        }
        if (lower.contains("weismann") || lower.contains("germ") || lower.contains("mitosis") || lower.contains("cell")) {
            return BaselinePlate.WEISMANN_GERMPLASM;
        }
        if (lower.contains("lamarck") || lower.contains("morphospace") || lower.contains("taxonomy") || lower.contains("phylogeny")) {
            return BaselinePlate.LAMARCK_MORPHOSPACE;
        }
        if (lower.contains("patent") || lower.contains("blueprint") || lower.contains("schematic") || lower.contains("orthographic")) {
            return BaselinePlate.PATENT_BLUEPRINT;
        }
        if (lower.contains("chladni") || lower.contains("cymatic") || lower.contains("nodal") || lower.contains("standing wave")) {
            return BaselinePlate.CHLADNI_PLATE;
        }
        if (lower.contains("phyllotaxis") || lower.contains("fibonacci") || lower.contains("sunflower") || lower.contains("rosette")) {
            return BaselinePlate.FIBONACCI_PHYLLOTAXIS;
        }
        return null;
    }

    /**
     * Wraps any creative prompt with a factual, mathematically structured scientific-aesthetic
     * baseline so higher-level AI image generation preserves symmetry, exact proportions, and craft.
     */
    static String augmentPromptWithBaseline(String userPrompt, BaselinePlate plate) {
        String subject = (userPrompt == null || userPrompt.trim().isEmpty())
                ? "symmetrical natural and mechanical study"
                : userPrompt.trim();
        BaselinePlate p = plate == null ? BaselinePlate.HAECKEL_RADIOLARIA : plate;
        return switch (p) {
            case HAECKEL_RADIOLARIA -> subject + ". Grounded in Ernst Haeckel's Kunstformen der Natur (1899) chromolithograph style: "
                    + "precise radial dihedral symmetry, golden-angle 137.5° phyllotaxis structure, fine copperplate stippling, "
                    + "mineral pigments on warm archival vellum, factually accurate biological proportions.";
            case HAECKEL_AMMONITE -> subject + ". Grounded in Ernst Haeckel's deep-ground marine lithographic plate style: "
                    + "mathematically true logarithmic spiral r = a·e^(bθ), chambered golden-ratio geometry, luminous mineral inks "
                    + "against dark indigo archival plate ground, fine anatomical symmetry.";
            case WEISMANN_GERMPLASM -> subject + ". Grounded in August Weismann's 1892 Das Keimplasma scientific monograph engraving: "
                    + "accurate cytological symmetry, crisp spindle field geometry, clear nested structural hierarchy, delicate scientific ink linework.";
            case LAMARCK_MORPHOSPACE -> subject + ". Grounded in Jean-Baptiste Lamarck's 1809 natural history comparative anatomy plate: "
                    + "ordered morphological progression, fine zoological etching, clear anatomical proportions on museum herbarium parchment.";
            case PATENT_BLUEPRINT -> subject + ". Grounded in classic USPTO / Google Patents orthographic engineering schematic style: "
                    + "crisp isometric and orthographic technical line drawing, dashed centerlines, exact mechanical proportions, "
                    + "clean numbered reference callouts (10, 12, 14), dimensional ticks, zero blurry artifacts.";
            case CHLADNI_PLATE -> subject + ". Grounded in Ernst Chladni's 1787 acoustic standing-wave cymatic plate geometry: "
                    + "symmetric nodal interference curves cos(m*pi*x)*cos(n*pi*y) - cos(n*pi*x)*cos(m*pi*y) = 0, luminous gold and cyan "
                    + "acoustic sand lines on obsidian slate, exact mirror symmetry.";
            case FIBONACCI_PHYLLOTAXIS -> subject + ". Grounded in botanical Vogel golden-angle phyllotaxis (137.508°): "
                    + "crisp counter-rotating (13, 21) Fibonacci parastichy spirals, archival botanical watercolor and ink stippling, "
                    + "exact mathematical floret packing.";
            case ATELIER -> subject + ". Clean factual proportions, crisp lighting, balanced geometric harmony, museum-grade clarity.";
        };
    }

    /**
     * Compares an observed real-world distance or estimated object span (in meters) against familiar
     * everyday physical scale references so Zoe Explore can reason concretely about relative sizes.
     */
    static String describeRelativeScale(float observedMeters) {
        if (observedMeters <= 0f || Float.isNaN(observedMeters) || Float.isInfinite(observedMeters)) {
            return "";
        }
        ScaleReference nearest = REAL_WORLD_SCALES[0];
        float bestRatio = Float.MAX_VALUE;
        for (ScaleReference ref : REAL_WORLD_SCALES) {
            float ratio = Math.max(observedMeters / ref.meters, ref.meters / observedMeters);
            if (ratio < bestRatio) {
                bestRatio = ratio;
                nearest = ref;
            }
        }
        if (observedMeters < 0.40f) {
            return String.format(Locale.US, "Scale reference: ~%.0f mm (roughly comparable to a %s, %.0f mm).",
                    observedMeters * 1000f, nearest.name, nearest.meters * 1000f);
        }
        return String.format(Locale.US, "Scale reference: ~%.2f m (roughly %.1fx the size of a %s).",
                observedMeters, observedMeters / nearest.meters, nearest.name);
    }

    // --- 100% Offline Procedural HD Scientific-Aesthetic Plate Renderer ---

    static Bitmap renderScientificPlate(BaselinePlate plate, String concept, int w, int h) {
        BaselinePlate p = plate == null ? BaselinePlate.ATELIER : plate;
        if (p == BaselinePlate.ATELIER) {
            return ImageLabEngine.createAtelierStarterBitmap(w, h);
        }
        int seed = deterministicSeed(concept);
        String label = (concept == null || concept.trim().isEmpty()) ? "" : concept.trim();
        Bitmap bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);
        switch (p) {
            case HAECKEL_RADIOLARIA -> drawHaeckelRadiolaria(c, w, h, seed, label);
            case HAECKEL_AMMONITE -> drawHaeckelAmmonite(c, w, h, seed, label);
            case WEISMANN_GERMPLASM -> drawWeismannGermPlasm(c, w, h, seed, label);
            case LAMARCK_MORPHOSPACE -> drawLamarckMorphospace(c, w, h, seed, label);
            case PATENT_BLUEPRINT -> drawPatentBlueprint(c, w, h, seed, label);
            case CHLADNI_PLATE -> drawChladniPlate(c, w, h, seed, label);
            case FIBONACCI_PHYLLOTAXIS -> drawFibonacciPhyllotaxis(c, w, h, seed, label);
            default -> {
            }
        }
        return bmp;
    }

    private static void drawArchivalFrame(Canvas c, int w, int h, int bgColor, int inkColor,
                                          String headerText, String footerText) {
        if (bgColor != Color.TRANSPARENT) {
            c.drawColor(bgColor);
        }
        float padOuter = Math.max(18f, Math.min(w, h) * 0.032f);
        float padInner = padOuter + Math.max(6f, Math.min(w, h) * 0.011f);
        Paint border = new Paint(Paint.ANTI_ALIAS_FLAG);
        border.setStyle(Paint.Style.STROKE);
        border.setColor(Color.argb(150, Color.red(inkColor), Color.green(inkColor), Color.blue(inkColor)));
        border.setStrokeWidth(Math.max(2.0f, h * 0.0036f));
        c.drawRect(padOuter, padOuter, w - padOuter, h - padOuter, border);
        border.setStrokeWidth(Math.max(1.0f, h * 0.0017f));
        c.drawRect(padInner, padInner, w - padInner, h - padInner, border);

        Paint txt = new Paint(Paint.ANTI_ALIAS_FLAG);
        txt.setColor(Color.argb(205, Color.red(inkColor), Color.green(inkColor), Color.blue(inkColor)));
        txt.setTypeface(Typeface.create(Typeface.SERIF, Typeface.NORMAL));
        txt.setTextAlign(Paint.Align.CENTER);
        txt.setTextSize(Math.max(13f, h * 0.025f));
        c.drawText(headerText, w / 2f, padInner + Math.max(20f, h * 0.034f), txt);
        txt.setTextSize(Math.max(11.5f, h * 0.022f));
        c.drawText(footerText, w / 2f, h - padInner - Math.max(10f, h * 0.016f), txt);
    }

    private static void drawHaeckelRadiolaria(Canvas c, int w, int h, int seed, String label) {
        int vellum = Color.rgb(245, 239, 224);
        int ink = Color.rgb(34, 30, 26);
        int order = symmetryOrderForSeed(seed);
        String top = "KUNSTFORMEN DER NATUR · E. HAECKEL (1899) · D" + order + " SYMMETRY";
        String bot = label.isEmpty()
                ? "Actinomma silica geodesic · Golden Angle 137.508° · φ = 1.618"
                : "Plate Study: " + label + " · D" + order + " · φ = 1.618";
        drawArchivalFrame(c, w, h, vellum, ink, top, bot);

        float cx = w / 2f;
        float cy = h / 2f + h * 0.006f;
        float maxR = Math.min(w, h) * 0.35f;
        float s = Math.min(w, h) / 540f;

        Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
        glow.setShader(new RadialGradient(cx, cy, maxR * 1.18f,
                Color.argb(72, 29, 91, 107), Color.argb(0, 245, 239, 224), Shader.TileMode.CLAMP));
        c.drawCircle(cx, cy, maxR * 1.18f, glow);

        Paint spine = new Paint(Paint.ANTI_ALIAS_FLAG);
        spine.setStrokeCap(Paint.Cap.ROUND);
        int teal = Color.rgb(29, 91, 107);
        int coral = Color.rgb(184, 74, 57);
        int ochre = Color.rgb(198, 152, 58);

        for (int i = 0; i < order; i++) {
            double ang = (2.0 * Math.PI * i) / order;
            float cos = (float) Math.cos(ang);
            float sin = (float) Math.sin(ang);

            double angL = ang - Math.PI / (order * 1.7);
            double angR = ang + Math.PI / (order * 1.7);
            Path petal = new Path();
            petal.moveTo(cx + cos * maxR * 0.24f, cy + sin * maxR * 0.24f);
            petal.quadTo(
                    cx + (float) Math.cos(angL) * maxR * 0.72f,
                    cy + (float) Math.sin(angL) * maxR * 0.72f,
                    cx + cos * maxR * 0.88f,
                    cy + sin * maxR * 0.88f);
            petal.quadTo(
                    cx + (float) Math.cos(angR) * maxR * 0.72f,
                    cy + (float) Math.sin(angR) * maxR * 0.72f,
                    cx + cos * maxR * 0.24f,
                    cy + sin * maxR * 0.24f);
            Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
            fill.setColor(i % 2 == 0 ? Color.argb(74, 29, 91, 107) : Color.argb(66, 184, 74, 57));
            c.drawPath(petal, fill);

            spine.setStyle(Paint.Style.STROKE);
            spine.setColor(ink);
            spine.setStrokeWidth(1.5f * s);
            c.drawPath(petal, spine);

            spine.setColor(i % 2 == 0 ? teal : coral);
            spine.setStrokeWidth(2.6f * s);
            c.drawLine(cx + cos * maxR * 0.35f, cy + sin * maxR * 0.35f,
                    cx + cos * maxR * 1.05f, cy + sin * maxR * 1.05f, spine);
        }

        Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
        ring.setStyle(Paint.Style.STROKE);
        ring.setColor(ink);
        float[] radii = {maxR * 0.22f, maxR * 0.36f, maxR * 0.58f, maxR * 0.82f};
        for (int rIdx = 0; rIdx < radii.length; rIdx++) {
            ring.setStrokeWidth((rIdx == 2 ? 2.2f : 1.3f) * s);
            c.drawCircle(cx, cy, radii[rIdx], ring);
            Path poly = new Path();
            for (int i = 0; i <= order; i++) {
                double a = (2.0 * Math.PI * i) / order + (rIdx % 2 == 0 ? 0 : Math.PI / order);
                float px = cx + (float) Math.cos(a) * radii[rIdx];
                float py = cy + (float) Math.sin(a) * radii[rIdx];
                if (i == 0) poly.moveTo(px, py);
                else poly.lineTo(px, py);
            }
            ring.setColor(rIdx % 2 == 0 ? Color.argb(155, 29, 91, 107) : Color.argb(150, 198, 152, 58));
            c.drawPath(poly, ring);
            ring.setColor(ink);
        }

        Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
        double scale = maxR * 0.044;
        for (int k = 1; k <= 96; k++) {
            double[] pt = phyllotaxisPoint(k, scale);
            float r = (float) ((2.1 + (k / 96.0) * 3.1) * s);
            dot.setColor(k % 3 == 0 ? ochre : (k % 2 == 0 ? coral : teal));
            c.drawCircle(cx + (float) pt[0], cy + (float) pt[1], r, dot);
            dot.setStyle(Paint.Style.STROKE);
            dot.setStrokeWidth(0.8f * s);
            dot.setColor(ink);
            c.drawCircle(cx + (float) pt[0], cy + (float) pt[1], r, dot);
            dot.setStyle(Paint.Style.FILL);
        }
    }

    private static void drawHaeckelAmmonite(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(14, 21, 32);
        int ivory = Color.rgb(238, 228, 204);
        String top = "CEPHALOPODA · LOGARITHMIC SPIRAL r(θ) = a·e^(bθ)";
        String bot = label.isEmpty()
                ? "Haeckel Dark-Ground Marine Plate · Growth Factor φ = 1.618"
                : "Marine Study: " + label + " · r(θ) = a·e^(bθ)";
        drawArchivalFrame(c, w, h, bg, ivory, top, bot);

        float cx = w * 0.48f;
        float cy = h * 0.52f;
        float s = Math.min(w, h) / 540f;
        double b = 0.175 + ((seed % 5) * 0.008);
        double a = Math.min(w, h) * 0.011;

        Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
        glow.setShader(new RadialGradient(cx, cy, Math.min(w, h) * 0.44f,
                Color.argb(108, 76, 178, 172), Color.argb(0, 14, 21, 32), Shader.TileMode.CLAMP));
        c.drawCircle(cx, cy, Math.min(w, h) * 0.44f, glow);

        Path outer = new Path();
        Path inner = new Path();
        Paint rib = new Paint(Paint.ANTI_ALIAS_FLAG);
        rib.setStyle(Paint.Style.STROKE);
        int steps = 240;
        double maxTheta = 5.4 * Math.PI;
        for (int i = 0; i <= steps; i++) {
            double theta = (maxTheta * i) / steps;
            double[] pOut = logarithmicSpiralPoint(theta, a, b);
            double[] pIn = logarithmicSpiralPoint(Math.max(0, theta - 2.0 * Math.PI), a, b);
            float ox = cx + (float) pOut[0];
            float oy = cy + (float) pOut[1];
            float ix = cx + (float) pIn[0];
            float iy = cy + (float) pIn[1];
            if (i == 0) {
                outer.moveTo(ox, oy);
                inner.moveTo(ix, iy);
            } else {
                outer.lineTo(ox, oy);
                inner.lineTo(ix, iy);
            }
            if (i > 24 && i % 6 == 0) {
                rib.setColor(i % 12 == 0 ? Color.argb(205, 236, 190, 118) : Color.argb(130, 118, 216, 210));
                rib.setStrokeWidth((i % 12 == 0 ? 1.9f : 1.0f) * s);
                Path sept = new Path();
                sept.moveTo(ix, iy);
                float mx = (ix + ox) * 0.5f - (oy - iy) * 0.18f;
                float my = (iy + oy) * 0.5f + (ox - ix) * 0.18f;
                sept.quadTo(mx, my, ox, oy);
                c.drawPath(sept, rib);
            }
        }
        Paint spiralStroke = new Paint(Paint.ANTI_ALIAS_FLAG);
        spiralStroke.setStyle(Paint.Style.STROKE);
        spiralStroke.setColor(ivory);
        spiralStroke.setStrokeWidth(3.0f * s);
        c.drawPath(outer, spiralStroke);
        spiralStroke.setColor(Color.rgb(122, 214, 206));
        spiralStroke.setStrokeWidth(1.6f * s);
        c.drawPath(inner, spiralStroke);
    }

    private static void drawWeismannGermPlasm(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(246, 242, 232);
        int ink = Color.rgb(36, 34, 42);
        String top = "DAS KEIMPLASMA · A. WEISMANN (1892) · CYTOLOGICAL DIVISION";
        String bot = label.isEmpty()
                ? "Fig. 1–3 · Germ-Line Continuity · Mitotic Spindle Geometry"
                : "Cytology Study: " + label + " · Weismann Lineage";
        drawArchivalFrame(c, w, h, bg, ink, top, bot);

        float cx = w / 2f;
        float cy = h / 2f + h * 0.008f;
        float rx = w * 0.34f;
        float ry = h * 0.27f;
        float s = Math.min(w, h) / 540f;

        Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
        stroke.setColor(Color.argb(46, 108, 72, 148));
        stroke.setStyle(Paint.Style.FILL);
        c.drawOval(new RectF(cx - rx, cy - ry, cx + rx, cy + ry), stroke);

        stroke.setStyle(Paint.Style.STROKE);
        stroke.setColor(ink);
        stroke.setStrokeWidth(2.6f * s);
        c.drawOval(new RectF(cx - rx, cy - ry, cx + rx, cy + ry), stroke);
        stroke.setStrokeWidth(1.1f * s);
        c.drawOval(new RectF(cx - rx + 8f * s, cy - ry + 8f * s, cx + rx - 8f * s, cy + ry - 8f * s), stroke);

        float poleL = cx - rx * 0.68f;
        float poleR = cx + rx * 0.68f;
        Paint spindle = new Paint(Paint.ANTI_ALIAS_FLAG);
        spindle.setStyle(Paint.Style.STROKE);
        spindle.setColor(Color.argb(145, 44, 92, 138));
        spindle.setStrokeWidth(1.3f * s);
        for (int i = -6; i <= 6; i++) {
            Path arc = new Path();
            arc.moveTo(poleL, cy);
            arc.quadTo(cx, cy + i * (ry * 0.14f), poleR, cy);
            c.drawPath(arc, spindle);
        }

        Paint dyad = new Paint(Paint.ANTI_ALIAS_FLAG);
        dyad.setStyle(Paint.Style.STROKE);
        dyad.setStrokeCap(Paint.Cap.ROUND);
        dyad.setStrokeWidth(5.5f * s);
        int pairs = 5 + (seed % 3);
        for (int i = 0; i < pairs; i++) {
            float y = cy - ry * 0.52f + (i * (ry * 1.04f) / Math.max(1, pairs - 1));
            dyad.setColor(i % 2 == 0 ? Color.rgb(168, 56, 76) : Color.rgb(42, 106, 134));
            c.drawLine(cx - 18f * s, y - 9f * s, cx - 4f * s, y, dyad);
            c.drawLine(cx - 18f * s, y + 9f * s, cx - 4f * s, y, dyad);
            c.drawLine(cx + 18f * s, y - 9f * s, cx + 4f * s, y, dyad);
            c.drawLine(cx + 18f * s, y + 9f * s, cx + 4f * s, y, dyad);
        }

        Paint polePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        polePaint.setColor(Color.rgb(186, 134, 42));
        c.drawCircle(poleL, cy, 9f * s, polePaint);
        c.drawCircle(poleR, cy, 9f * s, polePaint);

        Paint lbl = new Paint(Paint.ANTI_ALIAS_FLAG);
        lbl.setColor(ink);
        lbl.setTypeface(Typeface.create(Typeface.SERIF, Typeface.ITALIC));
        lbl.setTextSize(14f * s);
        c.drawText("Centrosome A", poleL - 36f * s, cy - 18f * s, lbl);
        c.drawText("Centrosome B", poleR - 36f * s, cy - 18f * s, lbl);
        c.drawText("Equatorial Germ-Plasm Plate (Id)", cx - 96f * s, cy + ry + 22f * s, lbl);
    }

    private static void drawLamarckMorphospace(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(242, 236, 220);
        int ink = Color.rgb(42, 38, 30);
        String top = "PHILOSOPHIE ZOOLOGIQUE · J.-B. LAMARCK (1809)";
        String bot = label.isEmpty()
                ? "Tableau · Continuous Branching Morphospace & Comparative Series"
                : "Morphospace: " + label + " · Continuous Adaptation Series";
        drawArchivalFrame(c, w, h, bg, ink, top, bot);

        float s = Math.min(w, h) / 540f;
        Paint stem = new Paint(Paint.ANTI_ALIAS_FLAG);
        stem.setStyle(Paint.Style.STROKE);
        stem.setStrokeCap(Paint.Cap.ROUND);

        float baseX = w * 0.50f;
        float baseY = h * 0.82f;
        int branches = 5;
        int[] palette = {
                Color.rgb(44, 102, 84),
                Color.rgb(52, 92, 136),
                Color.rgb(162, 98, 46),
                Color.rgb(132, 64, 88),
                Color.rgb(74, 118, 66)
        };

        for (int i = 0; i < branches; i++) {
            float t = (i - 2f) / 2f;
            float tipX = w * (0.50f + t * 0.34f);
            float tipY = h * (0.28f + Math.abs(t) * 0.08f);

            Path curve = new Path();
            curve.moveTo(baseX, baseY);
            curve.cubicTo(baseX, h * 0.62f, baseX + t * w * 0.22f, h * 0.50f, tipX, tipY);
            stem.setColor(ink);
            stem.setStrokeWidth(2.6f * s);
            c.drawPath(curve, stem);

            float r = Math.min(w, h) * 0.068f;
            Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
            fill.setColor(Color.argb(72, Color.red(palette[i]), Color.green(palette[i]), Color.blue(palette[i])));
            c.drawCircle(tipX, tipY, r, fill);
            stem.setColor(palette[i]);
            stem.setStrokeWidth(2.0f * s);
            c.drawCircle(tipX, tipY, r, stem);

            int lobes = 3 + i + (seed % 2);
            for (int k = 0; k < lobes; k++) {
                double a = (2.0 * Math.PI * k) / lobes;
                c.drawLine(tipX, tipY, tipX + (float) Math.cos(a) * r * 0.82f, tipY + (float) Math.sin(a) * r * 0.82f, stem);
            }
        }
        Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
        dash.setStyle(Paint.Style.STROKE);
        dash.setColor(Color.argb(85, 42, 38, 30));
        dash.setStrokeWidth(1.2f * s);
        dash.setPathEffect(new DashPathEffect(new float[]{6f * s, 6f * s}, 0f));
        for (int row = 1; row <= 3; row++) {
            float gy = h * (0.24f + row * 0.16f);
            c.drawLine(w * 0.08f, gy, w * 0.92f, gy, dash);
        }
    }

    private static void drawPatentBlueprint(Canvas c, int w, int h, int seed, String label) {
        float s = Math.min(w, h) / 540f;
        Paint bgPaint = new Paint();
        bgPaint.setShader(new LinearGradient(0, 0, w, h,
                Color.rgb(14, 44, 88), Color.rgb(9, 28, 62), Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, bgPaint);

        Paint grid = new Paint(Paint.ANTI_ALIAS_FLAG);
        grid.setColor(Color.argb(38, 178, 214, 255));
        grid.setStrokeWidth(1f * s);
        int step = Math.max(20, w / 28);
        for (int x = (int) (28 * s); x < w - 28 * s; x += step) {
            c.drawLine(x, 28 * s, x, h - 28 * s, grid);
        }
        for (int y = (int) (28 * s); y < h - 28 * s; y += step) {
            c.drawLine(28 * s, y, w - 28 * s, y, grid);
        }

        int white = Color.rgb(236, 245, 255);
        int cyan = Color.rgb(138, 218, 255);
        String top = "U.S. PATENT ORTHOGRAPHIC SHEET 1 OF 1 · FIG. 1";
        String bot = label.isEmpty()
                ? "Scale 1:1 · Meshed Involute Gear & Prism Assembly · patents.google.com"
                : "FIG. 1 · " + label.toUpperCase(Locale.US) + " · SCALE 1:1 · Ø 84.0 mm";
        drawArchivalFrame(c, w, h, Color.TRANSPARENT, white, top, bot);

        Paint line = new Paint(Paint.ANTI_ALIAS_FLAG);
        line.setStyle(Paint.Style.STROKE);
        line.setColor(white);
        line.setStrokeWidth(2.2f * s);

        Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
        dash.setStyle(Paint.Style.STROKE);
        dash.setColor(cyan);
        dash.setStrokeWidth(1.2f * s);
        dash.setPathEffect(new DashPathEffect(new float[]{12f * s, 5f * s, 3f * s, 5f * s}, 0f));

        float gx = w * 0.34f;
        float gy = h * 0.52f;
        float gr = Math.min(w, h) * 0.19f;
        int teeth = 12 + (seed % 5) * 2;
        Path gear = new Path();
        for (int i = 0; i < teeth * 2; i++) {
            double a = (Math.PI * i) / teeth;
            float r = (i % 2 == 0) ? gr * 1.13f : gr * 0.94f;
            float px = gx + (float) Math.cos(a) * r;
            float py = gy + (float) Math.sin(a) * r;
            if (i == 0) gear.moveTo(px, py);
            else gear.lineTo(px, py);
        }
        gear.close();
        c.drawPath(gear, line);
        c.drawCircle(gx, gy, gr * 0.52f, line);
        c.drawCircle(gx, gy, gr * 0.18f, line);
        c.drawLine(gx - gr * 1.35f, gy, gx + gr * 1.35f, gy, dash);
        c.drawLine(gx, gy - gr * 1.35f, gx, gy + gr * 1.35f, dash);

        float px = w * 0.69f;
        float py = h * 0.52f;
        float pr = Math.min(w, h) * 0.19f;
        Path prism = new Path();
        prism.moveTo(px, py - pr);
        prism.lineTo(px + pr * 0.92f, py + pr * 0.72f);
        prism.lineTo(px - pr * 0.92f, py + pr * 0.72f);
        prism.close();
        c.drawPath(prism, line);

        Paint ray = new Paint(Paint.ANTI_ALIAS_FLAG);
        ray.setColor(Color.rgb(255, 220, 128));
        ray.setStrokeWidth(2.2f * s);
        c.drawLine(px - pr * 1.35f, py + pr * 0.18f, px - pr * 0.44f, py - pr * 0.06f, ray);
        c.drawLine(px - pr * 0.44f, py - pr * 0.06f, px + pr * 0.46f, py - pr * 0.02f, ray);
        c.drawLine(px + pr * 0.46f, py - pr * 0.02f, px + pr * 1.32f, py + pr * 0.34f, ray);

        Paint callTxt = new Paint(Paint.ANTI_ALIAS_FLAG);
        callTxt.setColor(white);
        callTxt.setTypeface(Typeface.MONOSPACE);
        callTxt.setTextSize(15f * s);
        drawCallout(c, gx + gr * 0.75f, gy - gr * 0.75f, gx + gr * 1.15f, gy - gr * 1.15f, "10", line, callTxt);
        drawCallout(c, gx, gy + gr * 0.52f, gx - gr * 0.95f, gy + gr * 1.05f, "12", line, callTxt);
        drawCallout(c, px, py - pr * 0.55f, px + pr * 0.85f, py - pr * 1.05f, "14", line, callTxt);
        drawCallout(c, px + pr * 0.95f, py + pr * 0.25f, px + pr * 1.25f, py + pr * 0.78f, "16", line, callTxt);

        float dimY = gy + gr * 1.38f;
        c.drawLine(gx - gr, dimY, gx + gr, dimY, dash);
        c.drawLine(gx - gr, dimY - 6f * s, gx - gr, dimY + 6f * s, line);
        c.drawLine(gx + gr, dimY - 6f * s, gx + gr, dimY + 6f * s, line);
        callTxt.setTextSize(12.5f * s);
        c.drawText("Ø 84.0 mm", gx - 34f * s, dimY - 6f * s, callTxt);
    }

    private static void drawChladniPlate(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(12, 16, 26);
        int gold = Color.rgb(242, 198, 114);
        int[] modes = chladniModesForSeed(seed);
        int m = modes[0];
        int n = modes[1];
        String top = "CHLADNI CYMATICS · EIGENMODES (m=" + m + ", n=" + n + ")";
        String bot = label.isEmpty()
                ? "Standing Wave Nodal Field · cos(mπx)cos(nπy) − cos(nπx)cos(mπy) = 0"
                : "Acoustic Study: " + label + " · Mode (" + m + ", " + n + ")";
        drawArchivalFrame(c, w, h, bg, gold, top, bot);

        float side = Math.min(w, h) * 0.66f;
        float left = (w - side) * 0.5f;
        float topY = (h - side) * 0.5f + h * 0.008f;

        Paint plateBg = new Paint(Paint.ANTI_ALIAS_FLAG);
        plateBg.setShader(new RadialGradient(w * 0.5f, h * 0.5f, side * 0.75f,
                Color.rgb(22, 32, 52), Color.rgb(10, 14, 24), Shader.TileMode.CLAMP));
        c.drawRect(left, topY, left + side, topY + side, plateBg);

        int grid = 96;
        float cell = side / grid;
        Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
        for (int gy = 0; gy < grid; gy++) {
            double ny = (gy + 0.5) / grid;
            double cmY = Math.cos(m * Math.PI * ny);
            double cnY = Math.cos(n * Math.PI * ny);
            for (int gx = 0; gx < grid; gx++) {
                double nx = (gx + 0.5) / grid;
                double val = Math.cos(m * Math.PI * nx) * cnY - Math.cos(n * Math.PI * nx) * cmY;
                double nodal = Math.max(0.0, 1.0 - Math.abs(val) * 4.2);
                if (nodal > 0.14) {
                    float mix = (float) ((nx + ny) * 0.5);
                    int r = (int) (242 * (1f - mix) + 114 * mix);
                    int g = (int) (198 * (1f - mix) + 224 * mix);
                    int b = (int) (114 * (1f - mix) + 255 * mix);
                    dot.setColor(Color.argb((int) Math.min(255, nodal * 245), r, g, b));
                    c.drawCircle(left + (gx + 0.5f) * cell, topY + (gy + 0.5f) * cell,
                            (float) (cell * (0.34 + nodal * 0.36)), dot);
                }
            }
        }
        Paint rim = new Paint(Paint.ANTI_ALIAS_FLAG);
        rim.setStyle(Paint.Style.STROKE);
        rim.setColor(Color.argb(140, 242, 198, 114));
        rim.setStrokeWidth(Math.max(1.5f, side * 0.004f));
        c.drawRect(left, topY, left + side, topY + side, rim);
    }

    private static void drawFibonacciPhyllotaxis(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(248, 244, 232);
        int ink = Color.rgb(34, 42, 36);
        String top = "BOTANICAL PHYLLOTAXIS · GOLDEN ANGLE 137.508° · FIBONACCI (13, 21)";
        String bot = label.isEmpty()
                ? "Vogel Spiral r = c·√n · Counter-Rotating Parastichy Lattice"
                : "Botanical Study: " + label + " · φ = 1.618";
        drawArchivalFrame(c, w, h, bg, ink, top, bot);

        float cx = w * 0.5f;
        float cy = h * 0.5f + h * 0.008f;
        float maxR = Math.min(w, h) * 0.36f;
        int count = 210;
        double scale = maxR / Math.sqrt(count);
        float s = Math.min(w, h) / 540f;

        // Draw subtle counter-rotating Fibonacci 13-arm & 21-arm parastichy curves
        Paint curve = new Paint(Paint.ANTI_ALIAS_FLAG);
        curve.setStyle(Paint.Style.STROKE);
        curve.setStrokeWidth(1.1f * s);
        for (int arm = 0; arm < 13; arm++) {
            Path p13 = new Path();
            boolean started = false;
            for (int k = arm + 1; k <= count; k += 13) {
                double[] pt = phyllotaxisPoint(k, scale);
                if (!started) {
                    p13.moveTo(cx + (float) pt[0], cy + (float) pt[1]);
                    started = true;
                } else {
                    p13.lineTo(cx + (float) pt[0], cy + (float) pt[1]);
                }
            }
            curve.setColor(Color.argb(65, 44, 112, 92));
            c.drawPath(p13, curve);
        }
        for (int arm = 0; arm < 21; arm++) {
            Path p21 = new Path();
            boolean started = false;
            for (int k = arm + 1; k <= count; k += 21) {
                double[] pt = phyllotaxisPoint(k, scale);
                if (!started) {
                    p21.moveTo(cx + (float) pt[0], cy + (float) pt[1]);
                    started = true;
                } else {
                    p21.lineTo(cx + (float) pt[0], cy + (float) pt[1]);
                }
            }
            curve.setColor(Color.argb(55, 192, 128, 52));
            c.drawPath(p21, curve);
        }

        // Draw botanical seed florets with golden radial color gradient
        Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
        int hueShift = Math.abs(seed) % 3;
        for (int k = 1; k <= count; k++) {
            double[] pt = phyllotaxisPoint(k, scale);
            float frac = (float) k / count;
            float r = (2.4f + frac * 4.4f) * s;
            int col;
            if (hueShift == 1) {
                col = Color.rgb((int) (46 + 150 * frac), (int) (110 + 70 * (1f - frac)), (int) (132 - 42 * frac));
            } else if (hueShift == 2) {
                col = Color.rgb((int) (164 + 62 * frac), (int) (68 + 112 * frac), (int) (96 - 30 * frac));
            } else {
                col = Color.rgb((int) (54 + 168 * frac), (int) (122 + 52 * frac), (int) (82 - 28 * frac));
            }
            dot.setStyle(Paint.Style.FILL);
            dot.setColor(col);
            c.drawCircle(cx + (float) pt[0], cy + (float) pt[1], r, dot);
            dot.setStyle(Paint.Style.STROKE);
            dot.setStrokeWidth(0.75f * s);
            dot.setColor(Color.argb(145, 34, 42, 36));
            c.drawCircle(cx + (float) pt[0], cy + (float) pt[1], r, dot);
        }
    }

    private static void drawCallout(Canvas c, float x0, float y0, float x1, float y1,
                                    String num, Paint line, Paint txt) {
        c.drawLine(x0, y0, x1, y1, line);
        c.drawText(num, x1 + 4, y1 + 4, txt);
    }
}
