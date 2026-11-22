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
 * Zoe Scientific-Aesthetic Visual Substrate (v0.9.0-beta).
 *
 * Grounds Zoe's image generation & visual reasoning on factual, mathematically structured,
 * public-domain scientific artistry and engineering schematics:
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
 *
 * 100% deterministic and offline for procedural plate generation; also augments optional online
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
        PATENT_BLUEPRINT("📐 Patent", "Orthographic Patent Schematic (patents.google.com)", "Involute gear + prism optics · Orthographic callouts");

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

    // --- 100% Offline Procedural Scientific-Aesthetic Plate Renderer ---

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
            default -> {
            }
        }
        return bmp;
    }

    private static void drawArchivalFrame(Canvas c, int w, int h, int bgColor, int inkColor,
                                          String headerText, String footerText) {
        c.drawColor(bgColor);
        Paint border = new Paint(Paint.ANTI_ALIAS_FLAG);
        border.setStyle(Paint.Style.STROKE);
        border.setColor(Color.argb(145, Color.red(inkColor), Color.green(inkColor), Color.blue(inkColor)));
        border.setStrokeWidth(2.4f);
        c.drawRect(18, 18, w - 18, h - 18, border);
        border.setStrokeWidth(1.0f);
        c.drawRect(25, 25, w - 25, h - 25, border);

        Paint txt = new Paint(Paint.ANTI_ALIAS_FLAG);
        txt.setColor(Color.argb(195, Color.red(inkColor), Color.green(inkColor), Color.blue(inkColor)));
        txt.setTypeface(Typeface.create(Typeface.SERIF, Typeface.NORMAL));
        txt.setTextAlign(Paint.Align.CENTER);
        txt.setTextSize(Math.max(12f, h * 0.026f));
        c.drawText(headerText, w / 2f, 44f, txt);
        txt.setTextSize(Math.max(11f, h * 0.023f));
        c.drawText(footerText, w / 2f, h - 32f, txt);
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
        float cy = h / 2f + 4f;
        float maxR = Math.min(w, h) * 0.35f;

        // Soft warm sepia lithograph halo
        Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
        glow.setShader(new RadialGradient(cx, cy, maxR * 1.15f,
                Color.argb(65, 29, 91, 107), Color.argb(0, 245, 239, 224), Shader.TileMode.CLAMP));
        c.drawCircle(cx, cy, maxR * 1.15f, glow);

        // Radial calcite spines & petal fins
        Paint spine = new Paint(Paint.ANTI_ALIAS_FLAG);
        spine.setStrokeCap(Paint.Cap.ROUND);
        int teal = Color.rgb(29, 91, 107);
        int coral = Color.rgb(184, 74, 57);
        int ochre = Color.rgb(198, 152, 58);

        for (int i = 0; i < order; i++) {
            double ang = (2.0 * Math.PI * i) / order;
            float cos = (float) Math.cos(ang);
            float sin = (float) Math.sin(ang);

            // Delicate botanical petal lobe
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
            fill.setColor(i % 2 == 0 ? Color.argb(68, 29, 91, 107) : Color.argb(62, 184, 74, 57));
            c.drawPath(petal, fill);

            spine.setStyle(Paint.Style.STROKE);
            spine.setColor(ink);
            spine.setStrokeWidth(1.5f);
            c.drawPath(petal, spine);

            // Outer silica spike
            spine.setColor(i % 2 == 0 ? teal : coral);
            spine.setStrokeWidth(2.6f);
            c.drawLine(cx + cos * maxR * 0.35f, cy + sin * maxR * 0.35f,
                    cx + cos * maxR * 1.04f, cy + sin * maxR * 1.04f, spine);
        }

        // Golden-ratio concentric lattice rings & geodesic chords
        Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
        ring.setStyle(Paint.Style.STROKE);
        ring.setColor(ink);
        float[] radii = {maxR * 0.22f, maxR * 0.36f, maxR * 0.58f, maxR * 0.82f};
        for (int rIdx = 0; rIdx < radii.length; rIdx++) {
            ring.setStrokeWidth(rIdx == 2 ? 2.2f : 1.3f);
            c.drawCircle(cx, cy, radii[rIdx], ring);
            Path poly = new Path();
            for (int i = 0; i <= order; i++) {
                double a = (2.0 * Math.PI * i) / order + (rIdx % 2 == 0 ? 0 : Math.PI / order);
                float px = cx + (float) Math.cos(a) * radii[rIdx];
                float py = cy + (float) Math.sin(a) * radii[rIdx];
                if (i == 0) poly.moveTo(px, py);
                else poly.lineTo(px, py);
            }
            ring.setColor(rIdx % 2 == 0 ? Color.argb(150, 29, 91, 107) : Color.argb(145, 198, 152, 58));
            c.drawPath(poly, ring);
            ring.setColor(ink);
        }

        // Golden-angle phyllotaxis core (137.508° Fibonacci florets)
        Paint dot = new Paint(Paint.ANTI_ALIAS_FLAG);
        double scale = maxR * 0.044;
        for (int k = 1; k <= 88; k++) {
            double[] pt = phyllotaxisPoint(k, scale);
            float r = (float) (2.1 + (k / 88.0) * 3.1);
            dot.setColor(k % 3 == 0 ? ochre : (k % 2 == 0 ? coral : teal));
            c.drawCircle(cx + (float) pt[0], cy + (float) pt[1], r, dot);
            dot.setStyle(Paint.Style.STROKE);
            dot.setStrokeWidth(0.8f);
            dot.setColor(ink);
            c.drawCircle(cx + (float) pt[0], cy + (float) pt[1], r, dot);
            dot.setStyle(Paint.Style.FILL);
        }
    }

    private static void drawHaeckelAmmonite(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(16, 24, 34);
        int ivory = Color.rgb(236, 226, 202);
        String top = "CEPHALOPODA · LOGARITHMIC SPIRAL r(θ) = a·e^(bθ)";
        String bot = label.isEmpty()
                ? "Haeckel Dark-Ground Marine Plate · Growth Factor φ = 1.618"
                : "Marine Study: " + label + " · r(θ) = a·e^(bθ)";
        drawArchivalFrame(c, w, h, bg, ivory, top, bot);

        float cx = w * 0.48f;
        float cy = h * 0.52f;
        double b = 0.175 + ((seed % 5) * 0.008);
        double a = Math.min(w, h) * 0.011;

        Paint glow = new Paint(Paint.ANTI_ALIAS_FLAG);
        glow.setShader(new RadialGradient(cx, cy, Math.min(w, h) * 0.42f,
                Color.argb(95, 76, 178, 172), Color.argb(0, 16, 24, 34), Shader.TileMode.CLAMP));
        c.drawCircle(cx, cy, Math.min(w, h) * 0.42f, glow);

        // Chambered logarithmic spiral + curved septa
        Path outer = new Path();
        Path inner = new Path();
        Paint rib = new Paint(Paint.ANTI_ALIAS_FLAG);
        rib.setStyle(Paint.Style.STROKE);
        int steps = 210;
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
            if (i > 22 && i % 6 == 0) {
                rib.setColor(i % 12 == 0 ? Color.argb(190, 232, 186, 114) : Color.argb(120, 118, 212, 206));
                rib.setStrokeWidth(i % 12 == 0 ? 1.8f : 1.0f);
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
        spiralStroke.setStrokeWidth(3.0f);
        c.drawPath(outer, spiralStroke);
        spiralStroke.setColor(Color.rgb(122, 214, 206));
        spiralStroke.setStrokeWidth(1.6f);
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
        float cy = h / 2f + 4f;
        float rx = w * 0.34f;
        float ry = h * 0.27f;

        // Cell membrane double contour
        Paint stroke = new Paint(Paint.ANTI_ALIAS_FLAG);
        stroke.setStyle(Paint.Style.STROKE);
        stroke.setColor(Color.argb(42, 108, 72, 148));
        stroke.setStyle(Paint.Style.FILL);
        c.drawOval(new RectF(cx - rx, cy - ry, cx + rx, cy + ry), stroke);

        stroke.setStyle(Paint.Style.STROKE);
        stroke.setColor(ink);
        stroke.setStrokeWidth(2.6f);
        c.drawOval(new RectF(cx - rx, cy - ry, cx + rx, cy + ry), stroke);
        stroke.setStrokeWidth(1.1f);
        c.drawOval(new RectF(cx - rx + 8, cy - ry + 8, cx + rx - 8, cy + ry - 8), stroke);

        // Two centrosome poles + hyperbolic mitotic spindle arcs
        float poleL = cx - rx * 0.68f;
        float poleR = cx + rx * 0.68f;
        Paint spindle = new Paint(Paint.ANTI_ALIAS_FLAG);
        spindle.setStyle(Paint.Style.STROKE);
        spindle.setColor(Color.argb(140, 44, 92, 138));
        spindle.setStrokeWidth(1.3f);
        for (int i = -6; i <= 6; i++) {
            Path arc = new Path();
            arc.moveTo(poleL, cy);
            arc.quadTo(cx, cy + i * (ry * 0.14f), poleR, cy);
            c.drawPath(arc, spindle);
        }

        // Symmetrical chromatid dyads aligned at equatorial metaphase plate
        Paint dyad = new Paint(Paint.ANTI_ALIAS_FLAG);
        dyad.setStyle(Paint.Style.STROKE);
        dyad.setStrokeCap(Paint.Cap.ROUND);
        dyad.setStrokeWidth(5.5f);
        int pairs = 5 + (seed % 3);
        for (int i = 0; i < pairs; i++) {
            float y = cy - ry * 0.52f + (i * (ry * 1.04f) / Math.max(1, pairs - 1));
            dyad.setColor(i % 2 == 0 ? Color.rgb(168, 56, 76) : Color.rgb(42, 106, 134));
            c.drawLine(cx - 18, y - 9, cx - 4, y, dyad);
            c.drawLine(cx - 18, y + 9, cx - 4, y, dyad);
            c.drawLine(cx + 18, y - 9, cx + 4, y, dyad);
            c.drawLine(cx + 18, y + 9, cx + 4, y, dyad);
        }

        // Pole asters & annotation labels
        Paint polePaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        polePaint.setColor(Color.rgb(186, 134, 42));
        c.drawCircle(poleL, cy, 9f, polePaint);
        c.drawCircle(poleR, cy, 9f, polePaint);

        Paint lbl = new Paint(Paint.ANTI_ALIAS_FLAG);
        lbl.setColor(ink);
        lbl.setTypeface(Typeface.create(Typeface.SERIF, Typeface.ITALIC));
        lbl.setTextSize(14f);
        c.drawText("Centrosome A", poleL - 36, cy - 18, lbl);
        c.drawText("Centrosome B", poleR - 36, cy - 18, lbl);
        c.drawText("Equatorial Germ-Plasm Plate (Id)", cx - 96, cy + ry + 20, lbl);
    }

    private static void drawLamarckMorphospace(Canvas c, int w, int h, int seed, String label) {
        int bg = Color.rgb(242, 236, 220);
        int ink = Color.rgb(42, 38, 30);
        String top = "PHILOSOPHIE ZOOLOGIQUE · J.-B. LAMARCK (1809)";
        String bot = label.isEmpty()
                ? "Tableau · Continuous Branching Morphospace & Comparative Series"
                : "Morphospace: " + label + " · Continuous Adaptation Series";
        drawArchivalFrame(c, w, h, bg, ink, top, bot);

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
            stem.setStrokeWidth(2.6f);
            c.drawPath(curve, stem);

            // Progressive morphological specimen medallion at each branch tip
            float r = Math.min(w, h) * 0.068f;
            Paint fill = new Paint(Paint.ANTI_ALIAS_FLAG);
            fill.setColor(Color.argb(65, Color.red(palette[i]), Color.green(palette[i]), Color.blue(palette[i])));
            c.drawCircle(tipX, tipY, r, fill);
            stem.setColor(palette[i]);
            stem.setStrokeWidth(2.0f);
            c.drawCircle(tipX, tipY, r, stem);

            int lobes = 3 + i + (seed % 2);
            for (int k = 0; k < lobes; k++) {
                double a = (2.0 * Math.PI * k) / lobes;
                c.drawLine(tipX, tipY, tipX + (float) Math.cos(a) * r * 0.82f, tipY + (float) Math.sin(a) * r * 0.82f, stem);
            }
        }
        // Horizontal morphological strata dashed guides
        Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
        dash.setStyle(Paint.Style.STROKE);
        dash.setColor(Color.argb(80, 42, 38, 30));
        dash.setPathEffect(new DashPathEffect(new float[]{6f, 6f}, 0f));
        for (int row = 1; row <= 3; row++) {
            float gy = h * (0.24f + row * 0.16f);
            c.drawLine(46, gy, w - 46, gy, dash);
        }
    }

    private static void drawPatentBlueprint(Canvas c, int w, int h, int seed, String label) {
        // Authentic Prussian technical blueprint with crisp white orthographic drafting lines
        Paint bgPaint = new Paint();
        bgPaint.setShader(new LinearGradient(0, 0, w, h,
                Color.rgb(16, 46, 92), Color.rgb(10, 32, 68), Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, bgPaint);

        // Engineering millimeter grid
        Paint grid = new Paint(Paint.ANTI_ALIAS_FLAG);
        grid.setColor(Color.argb(38, 178, 214, 255));
        grid.setStrokeWidth(1f);
        int step = Math.max(20, w / 28);
        for (int x = 28; x < w - 28; x += step) {
            c.drawLine(x, 28, x, h - 28, grid);
        }
        for (int y = 28; y < h - 28; y += step) {
            c.drawLine(28, y, w - 28, y, grid);
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
        line.setStrokeWidth(2.2f);

        Paint dash = new Paint(Paint.ANTI_ALIAS_FLAG);
        dash.setStyle(Paint.Style.STROKE);
        dash.setColor(cyan);
        dash.setStrokeWidth(1.2f);
        dash.setPathEffect(new DashPathEffect(new float[]{12f, 5f, 3f, 5f}, 0f));

        // Left mechanism: precision involute gear assembly (10)
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

        // Right mechanism: optical prism & refracted beam ray-trace (14)
        float px = w * 0.69f;
        float py = h * 0.52f;
        float pr = Math.min(w, h) * 0.19f;
        Path prism = new Path();
        prism.moveTo(px, py - pr);
        prism.lineTo(px + pr * 0.92f, py + pr * 0.72f);
        prism.lineTo(px - pr * 0.92f, py + pr * 0.72f);
        prism.close();
        c.drawPath(prism, line);

        // Incident & refracted optical rays
        Paint ray = new Paint(Paint.ANTI_ALIAS_FLAG);
        ray.setColor(Color.rgb(255, 220, 128));
        ray.setStrokeWidth(2.0f);
        c.drawLine(px - pr * 1.35f, py + pr * 0.18f, px - pr * 0.44f, py - pr * 0.06f, ray);
        c.drawLine(px - pr * 0.44f, py - pr * 0.06f, px + pr * 0.46f, py - pr * 0.02f, ray);
        c.drawLine(px + pr * 0.46f, py - pr * 0.02f, px + pr * 1.32f, py + pr * 0.34f, ray);

        // Numbered patent callout leaders (10, 12, 14, 16) + dimensional bar
        Paint callTxt = new Paint(Paint.ANTI_ALIAS_FLAG);
        callTxt.setColor(white);
        callTxt.setTypeface(Typeface.MONOSPACE);
        callTxt.setTextSize(15f);
        drawCallout(c, gx + gr * 0.75f, gy - gr * 0.75f, gx + gr * 1.15f, gy - gr * 1.15f, "10", line, callTxt);
        drawCallout(c, gx, gy + gr * 0.52f, gx - gr * 0.95f, gy + gr * 1.05f, "12", line, callTxt);
        drawCallout(c, px, py - pr * 0.55f, px + pr * 0.85f, py - pr * 1.05f, "14", line, callTxt);
        drawCallout(c, px + pr * 0.95f, py + pr * 0.25f, px + pr * 1.25f, py + pr * 0.78f, "16", line, callTxt);

        // Dimension bracket under gear
        float dimY = gy + gr * 1.38f;
        c.drawLine(gx - gr, dimY, gx + gr, dimY, dash);
        c.drawLine(gx - gr, dimY - 6, gx - gr, dimY + 6, line);
        c.drawLine(gx + gr, dimY - 6, gx + gr, dimY + 6, line);
        callTxt.setTextSize(12.5f);
        c.drawText("Ø 84.0 mm", gx - 34, dimY - 6, callTxt);
    }

    private static void drawCallout(Canvas c, float x0, float y0, float x1, float y1,
                                    String num, Paint line, Paint txt) {
        c.drawLine(x0, y0, x1, y1, line);
        c.drawText(num, x1 + 4, y1 + 4, txt);
    }
}
