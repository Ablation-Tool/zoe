package research.zoetic.zoe;

import android.content.ContentResolver;
import android.content.ContentValues;
import android.content.Context;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.ColorMatrix;
import android.graphics.ColorMatrixColorFilter;
import android.graphics.LinearGradient;
import android.graphics.Matrix;
import android.graphics.Paint;
import android.graphics.RadialGradient;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.provider.MediaStore;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Zoe Image Lab Engine (v0.9.4-beta):
 *   - 100% offline native HD photo & scientific plate editing: 9 film/archival filters, brightness,
 *     contrast, warmth, saturation, radial vignette, 90° rotation, horizontal flip, 1:1 / 4:5 / 16:9
 *     aspect crops, privacy pixelation blur band, and caption stamping
 *   - Plain-English natural-language edit command parser ("warm, rotate 90, flip, vignette, noir")
 *   - Direct Save to Android Photos Gallery (MediaStore.Images, zero storage permission on Android 10+)
 *   - Optional online BYOK AI image generation supporting BOTH Google Gemini Imagen 3 and OpenAI
 *     using whichever API key the user already saved (explicit tap only).
 */
final class ImageLabEngine {
    enum FilterPreset {
        ORIGINAL("Original"),
        WARM_ATELIER("Atelier Warm"),
        GOLDEN_HOUR("Golden Hour"),
        COBALT_NIGHT("Cobalt Night"),
        NOIR_BW("Noir B&W"),
        MATTE_FILM("Matte Film"),
        EMERALD_FILM("Emerald Film"),
        CYBER_NEON("Cyber Neon"),
        VIVID_POP("Vivid Pop"),
        SEPIA_VINTAGE("Sepia"),
        ARCHIVAL_VELLUM("Vellum"),
        PRUSSIAN_BLUE("Blueprint");

        final String label;

        FilterPreset(String label) {
            this.label = label;
        }
    }

    /** Resolution-independent hand-drawn brush stroke (normalized 0..1 coordinates). */
    static final class BrushStroke {
        final java.util.List<float[]> points = new java.util.ArrayList<>();
        final int color;
        final float widthNorm; // fraction of min(w, h)

        BrushStroke(int color, float widthNorm) {
            this.color = color;
            this.widthNorm = widthNorm;
        }

        BrushStroke copy() {
            BrushStroke c = new BrushStroke(color, widthNorm);
            for (float[] pt : points) {
                c.points.add(new float[]{pt[0], pt[1]});
            }
            return c;
        }
    }

    enum CropMode {
        ORIGINAL("Original"),
        SQUARE("1:1 Square"),
        PORTRAIT_4_5("4:5 Portrait"),
        WIDE_16_9("16:9 Wide");

        final String label;

        CropMode(String label) {
            this.label = label;
        }
    }

    static final class EditSpec {
        FilterPreset filter = FilterPreset.ORIGINAL;
        int brightness;         // -60 .. +60
        float contrast = 1.0f;  // 0.5 .. 1.8
        int warmth;             // -40 .. +40
        float saturation = 1.0f; // 0.0 .. 2.0
        int vignette;           // 0 .. 100
        int rotationDeg;        // 0, 90, 180, 270
        boolean flipHorizontal;
        CropMode crop = CropMode.ORIGINAL;
        boolean privacyBlur;
        String caption = "";
        java.util.List<BrushStroke> strokes = new java.util.ArrayList<>();

        EditSpec copy() {
            EditSpec c = new EditSpec();
            c.filter = this.filter;
            c.brightness = this.brightness;
            c.contrast = this.contrast;
            c.warmth = this.warmth;
            c.saturation = this.saturation;
            c.vignette = this.vignette;
            c.rotationDeg = this.rotationDeg;
            c.flipHorizontal = this.flipHorizontal;
            c.crop = this.crop;
            c.privacyBlur = this.privacyBlur;
            c.caption = this.caption;
            for (BrushStroke st : this.strokes) {
                c.strokes.add(st.copy());
            }
            return c;
        }

        String summary() {
            StringBuilder sb = new StringBuilder(filter.label);
            if (brightness != 0) {
                sb.append(" · bright ").append(brightness > 0 ? "+" : "").append(brightness);
            }
            if (Math.abs(contrast - 1.0f) > 0.04f) {
                sb.append(String.format(Locale.US, " · contrast %.1fx", contrast));
            }
            if (warmth != 0) {
                sb.append(" · warmth ").append(warmth > 0 ? "+" : "").append(warmth);
            }
            if (Math.abs(saturation - 1.0f) > 0.05f) {
                sb.append(String.format(Locale.US, " · sat %d%%", Math.round(saturation * 100f)));
            }
            if (vignette > 0) {
                sb.append(" · vignette ").append(vignette).append("%");
            }
            if (rotationDeg != 0) {
                sb.append(" · rot ").append(rotationDeg).append("°");
            }
            if (flipHorizontal) {
                sb.append(" · mirror");
            }
            if (crop != CropMode.ORIGINAL) {
                sb.append(" · ").append(crop.label);
            }
            if (privacyBlur) {
                sb.append(" · privacy blur");
            }
            if (!strokes.isEmpty()) {
                sb.append(" · ").append(strokes.size()).append(strokes.size() == 1 ? " stroke" : " strokes");
            }
            if (!caption.isEmpty()) {
                sb.append(" · \"").append(caption).append("\"");
            }
            return sb.toString();
        }
    }

    private ImageLabEngine() {
    }

    /**
     * Parses natural-language photo edit commands deterministically offline.
     */
    static EditSpec parseEditCommand(String command, EditSpec current) {
        EditSpec next = current == null ? new EditSpec() : current.copy();
        if (command == null || command.trim().isEmpty()) {
            return next;
        }
        String raw = command.trim();
        String lower = raw.toLowerCase(Locale.US);

        if (lower.contains("reset") || lower.contains("original") || lower.contains("clear edits")) {
            return new EditSpec();
        }
        if (lower.contains("black and white") || lower.contains("b&w") || lower.contains("noir") || lower.contains("grayscale") || lower.contains("monochrome")) {
            next.filter = FilterPreset.NOIR_BW;
        } else if (lower.contains("vellum") || lower.contains("parchment") || lower.contains("archival")) {
            next.filter = FilterPreset.ARCHIVAL_VELLUM;
        } else if (lower.contains("cyanotype") || lower.contains("prussian")) {
            next.filter = FilterPreset.PRUSSIAN_BLUE;
        } else if (lower.contains("sepia") || lower.contains("vintage") || lower.contains("retro")) {
            next.filter = FilterPreset.SEPIA_VINTAGE;
        } else if (lower.contains("golden hour") || lower.contains("honey") || lower.contains("sunlit")) {
            next.filter = FilterPreset.GOLDEN_HOUR;
        } else if (lower.contains("cyber") || lower.contains("neon") || lower.contains("synth")) {
            next.filter = FilterPreset.CYBER_NEON;
        } else if (lower.contains("matte") || lower.contains("portra") || lower.contains("faded")) {
            next.filter = FilterPreset.MATTE_FILM;
        } else if (lower.contains("warm") || lower.contains("sunset") || lower.contains("golden")) {
            next.filter = FilterPreset.WARM_ATELIER;
        } else if (lower.contains("cool") || lower.contains("cobalt") || lower.contains("night") || lower.contains("blue")) {
            next.filter = FilterPreset.COBALT_NIGHT;
        } else if (lower.contains("emerald") || lower.contains("forest") || lower.contains("film") || lower.contains("cinematic")) {
            next.filter = FilterPreset.EMERALD_FILM;
        } else if (lower.contains("vivid") || lower.contains("pop") || lower.contains("vibrant") || lower.contains("saturate")) {
            next.filter = FilterPreset.VIVID_POP;
        }

        if (lower.contains("brighter") || lower.contains("lighten") || lower.contains("brighten")) {
            next.brightness = Math.min(60, next.brightness + 24);
        } else if (lower.contains("darker") || lower.contains("dim")) {
            next.brightness = Math.max(-60, next.brightness - 24);
        }
        if (lower.contains("more contrast") || lower.contains("punchy") || lower.contains("sharper") || lower.contains("crisp")) {
            next.contrast = Math.min(1.8f, next.contrast + 0.25f);
        } else if (lower.contains("soft") || lower.contains("less contrast")) {
            next.contrast = Math.max(0.5f, next.contrast - 0.2f);
        }
        if (lower.contains("warmer")) {
            next.warmth = Math.min(40, next.warmth + 16);
        } else if (lower.contains("cooler")) {
            next.warmth = Math.max(-40, next.warmth - 16);
        }
        if (lower.contains("vignette")) {
            next.vignette = lower.contains("no vignette") || lower.contains("remove vignette") ? 0 : 48;
        }
        if (lower.contains("mirror") || lower.contains("flip horizontal") || lower.equals("flip")) {
            next.flipHorizontal = !next.flipHorizontal;
        }

        if (lower.contains("rotate left") || lower.contains("270")) {
            next.rotationDeg = (next.rotationDeg + 270) % 360;
        } else if (lower.contains("flip 180") || lower.contains("upside down") || lower.contains("180")) {
            next.rotationDeg = (next.rotationDeg + 180) % 360;
        } else if (lower.contains("rotate") || lower.contains("turn")) {
            next.rotationDeg = (next.rotationDeg + 90) % 360;
        }

        if (lower.contains("square") || lower.contains("1:1")) {
            next.crop = CropMode.SQUARE;
        } else if (lower.contains("4:5") || lower.contains("portrait")) {
            next.crop = CropMode.PORTRAIT_4_5;
        } else if (lower.contains("16:9") || lower.contains("widescreen") || lower.contains("wide")) {
            next.crop = CropMode.WIDE_16_9;
        }

        if (lower.contains("unblur") || lower.contains("remove blur")) {
            next.privacyBlur = false;
        } else if (lower.contains("blur") || lower.contains("pixelate") || lower.contains("privacy") || lower.contains("hide face")) {
            next.privacyBlur = true;
        }

        String[] capKeys = {"caption ", "add caption ", "add text ", "title ", "stamp "};
        for (String key : capKeys) {
            int idx = lower.indexOf(key);
            if (idx >= 0) {
                String val = raw.substring(idx + key.length()).trim();
                int comma = val.indexOf(',');
                if (comma > 0) {
                    val = val.substring(0, comma).trim();
                }
                val = val.replaceAll("^[\"']|[\"']$", "").trim();
                if (!val.isEmpty()) {
                    next.caption = val.length() > 64 ? val.substring(0, 64) : val;
                }
                break;
            }
        }
        return next;
    }

    /**
     * Generates a luminous procedural Monterey-Atelier starter canvas with starfield & Chladni rings.
     */
    static Bitmap createAtelierStarterBitmap(int w, int h) {
        Bitmap bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);

        Paint sky = new Paint(Paint.ANTI_ALIAS_FLAG);
        sky.setShader(new LinearGradient(0, 0, 0, h,
                new int[]{Color.rgb(14, 22, 48), Color.rgb(30, 66, 122), Color.rgb(218, 124, 96), Color.rgb(246, 202, 138)},
                new float[]{0f, 0.44f, 0.76f, 1f}, Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, sky);

        // Crisp twilight stars in upper sky
        Paint star = new Paint(Paint.ANTI_ALIAS_FLAG);
        for (int i = 0; i < 36; i++) {
            float sx = ((i * 197 + 41) % 997) / 997f * w;
            float sy = ((i * 113 + 19) % 491) / 491f * (h * 0.42f);
            float sr = (i % 4 == 0) ? Math.max(1.8f, w * 0.0024f) : Math.max(1.0f, w * 0.0014f);
            star.setColor(Color.argb(120 + (i * 29) % 120, 232, 242, 255));
            c.drawCircle(sx, sy, sr, star);
        }

        // Solar halo + glowing sun disc
        float sunX = w * 0.68f;
        float sunY = h * 0.47f;
        Paint halo = new Paint(Paint.ANTI_ALIAS_FLAG);
        halo.setShader(new RadialGradient(sunX, sunY, w * 0.34f,
                Color.argb(110, 255, 224, 158), Color.argb(0, 255, 210, 140), Shader.TileMode.CLAMP));
        c.drawCircle(sunX, sunY, w * 0.34f, halo);

        Paint sun = new Paint(Paint.ANTI_ALIAS_FLAG);
        sun.setColor(Color.argb(232, 255, 236, 188));
        c.drawCircle(sunX, sunY, w * 0.125f, sun);

        // Calm ocean horizon
        Paint sea = new Paint(Paint.ANTI_ALIAS_FLAG);
        sea.setShader(new LinearGradient(0, h * 0.56f, 0, h,
                Color.rgb(26, 62, 102), Color.rgb(10, 20, 42), Shader.TileMode.CLAMP));
        c.drawRect(0, h * 0.56f, w, h, sea);

        // Layered coastal silhouettes
        Paint ridgeFar = new Paint(Paint.ANTI_ALIAS_FLAG);
        ridgeFar.setColor(Color.argb(175, 36, 54, 88));
        android.graphics.Path farPath = new android.graphics.Path();
        farPath.moveTo(0, h * 0.59f);
        farPath.quadTo(w * 0.30f, h * 0.40f, w * 0.56f, h * 0.56f);
        farPath.quadTo(w * 0.80f, h * 0.62f, w, h * 0.50f);
        farPath.lineTo(w, h * 0.66f);
        farPath.lineTo(0, h * 0.66f);
        farPath.close();
        c.drawPath(farPath, ridgeFar);

        Paint ridge = new Paint(Paint.ANTI_ALIAS_FLAG);
        ridge.setColor(Color.rgb(18, 29, 50));
        android.graphics.Path path = new android.graphics.Path();
        path.moveTo(0, h * 0.62f);
        path.quadTo(w * 0.22f, h * 0.44f, w * 0.48f, h * 0.59f);
        path.quadTo(w * 0.72f, h * 0.67f, w, h * 0.55f);
        path.lineTo(w, h * 0.68f);
        path.lineTo(0, h * 0.68f);
        path.close();
        c.drawPath(path, ridge);

        // Subtle Chladni starlight rings
        Paint ring = new Paint(Paint.ANTI_ALIAS_FLAG);
        ring.setStyle(Paint.Style.STROKE);
        ring.setStrokeWidth(Math.max(2.0f, w * 0.0032f));
        ring.setColor(Color.argb(95, 166, 214, 255));
        for (int i = 1; i <= 4; i++) {
            c.drawCircle(sunX, sunY, w * (0.14f + i * 0.06f), ring);
        }

        // Shimmering water reflections
        Paint shimmer = new Paint(Paint.ANTI_ALIAS_FLAG);
        shimmer.setColor(Color.argb(130, 255, 224, 168));
        float barH = Math.max(4f, h * 0.008f);
        for (int i = 0; i < 8; i++) {
            float ry = h * (0.64f + i * 0.04f);
            float rw = w * (0.16f - i * 0.012f);
            c.drawRoundRect(new RectF(sunX - rw, ry, sunX + rw, ry + barH), barH, barH, shimmer);
        }
        return bmp;
    }

    static Bitmap applyEdits(Bitmap src, EditSpec spec) {
        if (src == null) {
            return null;
        }
        EditSpec s = spec == null ? new EditSpec() : spec;

        // 1. Rotation & optional horizontal mirror
        Bitmap working = src;
        if (s.rotationDeg % 360 != 0 || s.flipHorizontal) {
            Matrix m = new Matrix();
            if (s.flipHorizontal) {
                m.postScale(-1f, 1f, src.getWidth() / 2f, src.getHeight() / 2f);
            }
            if (s.rotationDeg % 360 != 0) {
                m.postRotate(s.rotationDeg % 360);
            }
            working = Bitmap.createBitmap(src, 0, 0, src.getWidth(), src.getHeight(), m, true);
        }

        // 2. Aspect crop
        int w = working.getWidth();
        int h = working.getHeight();
        int cx = 0;
        int cy = 0;
        int cw = w;
        int ch = h;
        if (s.crop == CropMode.SQUARE) {
            int side = Math.min(w, h);
            cx = (w - side) / 2;
            cy = (h - side) / 2;
            cw = side;
            ch = side;
        } else if (s.crop == CropMode.PORTRAIT_4_5) {
            int targetW = Math.min(w, Math.max(16, (h * 4) / 5));
            int targetH = Math.min(h, Math.max(16, (targetW * 5) / 4));
            cx = (w - targetW) / 2;
            cy = (h - targetH) / 2;
            cw = targetW;
            ch = targetH;
        } else if (s.crop == CropMode.WIDE_16_9) {
            int targetH = Math.min(h, Math.max(16, (w * 9) / 16));
            int targetW = Math.min(w, Math.max(16, (targetH * 16) / 9));
            cx = (w - targetW) / 2;
            cy = (h - targetH) / 2;
            cw = targetW;
            ch = targetH;
        }

        Bitmap out = Bitmap.createBitmap(cw, ch, Bitmap.Config.ARGB_8888);
        Canvas canvas = new Canvas(out);

        // 3. ColorMatrix filter + warmth + saturation + brightness + contrast
        ColorMatrix cm = buildColorMatrix(s.filter, s.brightness, s.contrast, s.warmth, s.saturation);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(working, new Rect(cx, cy, cx + cw, cy + ch), new Rect(0, 0, cw, ch), paint);
        if (working != src) {
            working.recycle();
        }

        // 4. Optional radial optical vignette
        if (s.vignette > 0) {
            float strength = Math.min(1f, s.vignette / 100f);
            float radius = Math.max(cw, ch) * 0.72f;
            Paint vig = new Paint(Paint.ANTI_ALIAS_FLAG);
            vig.setShader(new RadialGradient(
                    cw * 0.5f, ch * 0.5f, radius,
                    new int[]{Color.TRANSPARENT, Color.TRANSPARENT, Color.argb((int) (strength * 195), 8, 10, 16)},
                    new float[]{0f, 0.52f, 1f}, Shader.TileMode.CLAMP));
            canvas.drawRect(0, 0, cw, ch, vig);
        }

        // 5. Optional offline privacy pixelation band (center horizontal strip for faces/plates)
        if (s.privacyBlur && cw >= 32 && ch >= 32) {
            int bandTop = (int) (ch * 0.30f);
            int bandH = Math.max(16, (int) (ch * 0.28f));
            Bitmap strip = Bitmap.createBitmap(out, 0, bandTop, cw, bandH);
            Bitmap tiny = Bitmap.createScaledBitmap(strip, Math.max(8, cw / 18), Math.max(4, bandH / 18), true);
            Paint pixPaint = new Paint();
            pixPaint.setFilterBitmap(false);
            canvas.drawBitmap(tiny, null, new Rect(0, bandTop, cw, bandTop + bandH), pixPaint);
            tiny.recycle();
            strip.recycle();
        }

        // 5b. Hand-drawn vector ink strokes (anti-aliased quadratic Bezier smoothing)
        if (s.strokes != null && !s.strokes.isEmpty()) {
            Paint ink = new Paint(Paint.ANTI_ALIAS_FLAG);
            ink.setStyle(Paint.Style.STROKE);
            ink.setStrokeCap(Paint.Cap.ROUND);
            ink.setStrokeJoin(Paint.Join.ROUND);
            float baseDim = Math.min(cw, ch);
            for (BrushStroke stroke : s.strokes) {
                if (stroke.points.isEmpty()) {
                    continue;
                }
                ink.setColor(stroke.color);
                ink.setStrokeWidth(Math.max(3f, stroke.widthNorm * baseDim));
                if (stroke.points.size() == 1) {
                    float[] pt = stroke.points.get(0);
                    canvas.drawPoint(pt[0] * cw, pt[1] * ch, ink);
                } else {
                    android.graphics.Path path = new android.graphics.Path();
                    float[] first = stroke.points.get(0);
                    path.moveTo(first[0] * cw, first[1] * ch);
                    for (int i = 1; i < stroke.points.size(); i++) {
                        float[] prev = stroke.points.get(i - 1);
                        float[] curr = stroke.points.get(i);
                        float midX = ((prev[0] + curr[0]) * 0.5f) * cw;
                        float midY = ((prev[1] + curr[1]) * 0.5f) * ch;
                        path.quadTo(prev[0] * cw, prev[1] * ch, midX, midY);
                    }
                    float[] last = stroke.points.get(stroke.points.size() - 1);
                    path.lineTo(last[0] * cw, last[1] * ch);
                    canvas.drawPath(path, ink);
                }
            }
        }

        // 6. Optional crisp caption overlay
        if (s.caption != null && !s.caption.trim().isEmpty()) {
            String cap = s.caption.trim();
            Paint bar = new Paint(Paint.ANTI_ALIAS_FLAG);
            bar.setColor(Color.argb(182, 14, 17, 26));
            float barH = Math.max(44f, ch * 0.11f);
            canvas.drawRect(0, ch - barH, cw, ch, bar);

            Paint txt = new Paint(Paint.ANTI_ALIAS_FLAG);
            txt.setColor(Color.rgb(244, 246, 250));
            txt.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
            txt.setTextAlign(Paint.Align.CENTER);
            txt.setTextSize(Math.max(18f, Math.min(44f, ch * 0.048f)));
            Paint.FontMetrics fm = txt.getFontMetrics();
            float textY = ch - (barH / 2f) - (fm.ascent + fm.descent) / 2f;
            canvas.drawText(cap, cw / 2f, textY, txt);
        }

        return out;
    }

    static ColorMatrix buildColorMatrix(FilterPreset preset, int brightness, float contrast) {
        return buildColorMatrix(preset, brightness, contrast, 0, 1.0f);
    }

    static ColorMatrix buildColorMatrix(FilterPreset preset, int brightness, float contrast,
                                        int warmth, float saturation) {
        ColorMatrix cm = new ColorMatrix();
        if (preset == FilterPreset.NOIR_BW) {
            cm.setSaturation(0f);
        } else if (preset == FilterPreset.SEPIA_VINTAGE) {
            cm.set(new float[]{
                    0.393f, 0.769f, 0.189f, 0, 0,
                    0.349f, 0.686f, 0.168f, 0, 0,
                    0.272f, 0.534f, 0.131f, 0, 0,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.WARM_ATELIER) {
            cm.set(new float[]{
                    1.14f, 0.04f, 0, 0, 10,
                    0, 1.04f, 0, 0, 4,
                    0, 0, 0.88f, 0, -6,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.COBALT_NIGHT) {
            cm.set(new float[]{
                    0.86f, 0, 0, 0, -6,
                    0, 0.96f, 0.04f, 0, 0,
                    0, 0.06f, 1.22f, 0, 14,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.EMERALD_FILM) {
            cm.set(new float[]{
                    0.92f, 0, 0, 0, 0,
                    0, 1.12f, 0.04f, 0, 6,
                    0, 0.02f, 0.96f, 0, 2,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.VIVID_POP) {
            cm.setSaturation(1.45f);
        } else if (preset == FilterPreset.ARCHIVAL_VELLUM) {
            cm.set(new float[]{
                    1.06f, 0.08f, 0.02f, 0, 14,
                    0.02f, 1.02f, 0.02f, 0, 10,
                    0, 0.02f, 0.84f, 0, 4,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.PRUSSIAN_BLUE) {
            cm.set(new float[]{
                    0.18f, 0.22f, 0.08f, 0, -10,
                    0.14f, 0.56f, 0.24f, 0, 6,
                    0.22f, 0.44f, 0.78f, 0, 32,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.GOLDEN_HOUR) {
            cm.set(new float[]{
                    1.22f, 0.08f, 0, 0, 16,
                    0.02f, 1.08f, 0.02f, 0, 8,
                    0, 0, 0.78f, 0, -12,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.CYBER_NEON) {
            cm.set(new float[]{
                    1.18f, 0, 0.14f, 0, 6,
                    0, 0.94f, 0.12f, 0, -4,
                    0.12f, 0.06f, 1.30f, 0, 18,
                    0, 0, 0, 1, 0
            });
        } else if (preset == FilterPreset.MATTE_FILM) {
            cm.set(new float[]{
                    0.94f, 0.04f, 0.02f, 0, 16,
                    0.02f, 0.93f, 0.02f, 0, 15,
                    0.02f, 0.02f, 0.90f, 0, 18,
                    0, 0, 0, 1, 0
            });
        }

        if (Math.abs(saturation - 1.0f) > 0.02f && preset != FilterPreset.NOIR_BW) {
            ColorMatrix satM = new ColorMatrix();
            satM.setSaturation(Math.max(0f, Math.min(2.0f, saturation)));
            cm.postConcat(satM);
        }

        if (warmth != 0) {
            float w = Math.max(-40f, Math.min(40f, warmth));
            ColorMatrix wm = new ColorMatrix(new float[]{
                    1f + w * 0.004f, 0, 0, 0, w * 0.45f,
                    0, 1f + w * 0.001f, 0, 0, w * 0.12f,
                    0, 0, 1f - w * 0.004f, 0, -w * 0.45f,
                    0, 0, 0, 1, 0
            });
            cm.postConcat(wm);
        }

        float c = Math.max(0.5f, Math.min(1.8f, contrast));
        float t = (1.0f - c) * 128.0f + brightness;
        ColorMatrix bc = new ColorMatrix(new float[]{
                c, 0, 0, 0, t,
                0, c, 0, 0, t,
                0, 0, c, 0, t,
                0, 0, 0, 1, 0
        });
        cm.postConcat(bc);
        return cm;
    }

    /**
     * Saves edited PNG directly into the user's Android Photos gallery (`Pictures/Zoe Studio`)
     * using scoped MediaStore storage (zero storage permissions needed on Android 10+).
     */
    static Uri saveToGallery(Context ctx, Bitmap bitmap, String displayName) throws IOException {
        if (ctx == null || bitmap == null) {
            throw new IOException("No image ready to save");
        }
        ContentResolver resolver = ctx.getContentResolver();
        ContentValues values = new ContentValues();
        values.put(MediaStore.Images.Media.DISPLAY_NAME, displayName);
        values.put(MediaStore.Images.Media.MIME_TYPE, "image/png");
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            values.put(MediaStore.Images.Media.RELATIVE_PATH, Environment.DIRECTORY_PICTURES + "/Zoe Studio");
            values.put(MediaStore.Images.Media.IS_PENDING, 1);
        }
        Uri uri = resolver.insert(MediaStore.Images.Media.EXTERNAL_CONTENT_URI, values);
        if (uri == null) {
            throw new IOException("Could not create gallery entry");
        }
        try (OutputStream out = resolver.openOutputStream(uri)) {
            if (out == null || !bitmap.compress(Bitmap.CompressFormat.PNG, 100, out)) {
                throw new IOException("PNG write failed");
            }
        } catch (IOException err) {
            resolver.delete(uri, null, null);
            throw err;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ContentValues done = new ContentValues();
            done.put(MediaStore.Images.Media.IS_PENDING, 0);
            resolver.update(uri, done, null, null);
        }
        return uri;
    }

    /** Pure JVM-testable provider selector choosing Gemini Imagen or OpenAI based on saved keys. */
    static String selectOnlineImageProvider(String geminiKey, String openAiKey) {
        if (geminiKey != null && !geminiKey.trim().isEmpty()) {
            return "gemini";
        }
        if (openAiKey != null && !openAiKey.trim().isEmpty()) {
            return "openai";
        }
        return "none";
    }

    /**
     * Optional online AI image generator supporting BOTH Google Gemini Imagen 3 AND OpenAI
     * using whichever API key the user already saved (explicit tap only).
     */
    static Bitmap generateOnlineImage(Context ctx, String prompt) throws IOException {
        String geminiKey = CloudVisionClient.savedApiKey(ctx);
        if (geminiKey.isEmpty()) {
            geminiKey = MultiAiClient.savedKey(ctx, MultiAiClient.Provider.GEMINI);
        }
        String openAiKey = MultiAiClient.savedKey(ctx, MultiAiClient.Provider.CHATGPT);
        String provider = selectOnlineImageProvider(geminiKey, openAiKey);
        if ("gemini".equals(provider)) {
            return generateWithGeminiImagen(geminiKey, prompt);
        }
        if ("openai".equals(provider)) {
            return generateWithOpenAi(openAiKey, prompt);
        }
        throw new IOException("Save a Gemini key (Eliza-GEM Studio / Talk ⚙) or OpenAI key (Talk ⚙) to generate online AI art.");
    }

    private static Bitmap generateWithGeminiImagen(String key, String prompt) throws IOException {
        Map<String, Object> instance = new LinkedHashMap<>();
        instance.put("prompt", prompt.trim());
        Map<String, Object> params = new LinkedHashMap<>();
        params.put("sampleCount", 1);
        params.put("aspectRatio", "4:3");
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("instances", List.of(instance));
        req.put("parameters", params);
        String body = MiniJson.stringify(req);

        URL url = new URL("https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setConnectTimeout(15_000);
        conn.setReadTimeout(60_000);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        conn.setRequestProperty("x-goog-api-key", key);
        conn.getOutputStream().write(body.getBytes(StandardCharsets.UTF_8));
        conn.getOutputStream().flush();

        String resp = readHttpText(conn, "Gemini Imagen");
        Map<String, Object> root = MiniJson.parseObject(resp);
        List<Object> preds = MiniJson.asArray(root.get("predictions"));
        if (preds == null || preds.isEmpty()) {
            throw new IOException("Gemini Imagen returned no image");
        }
        Map<String, Object> first = MiniJson.asObject(preds.get(0));
        String b64 = MiniJson.asString(first, "bytesBase64Encoded", "");
        if (b64.isEmpty()) {
            throw new IOException("Empty base64 image from Gemini Imagen");
        }
        return decodeBase64Bitmap(b64);
    }

    private static Bitmap generateWithOpenAi(String key, String prompt) throws IOException {
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("model", "dall-e-3");
        req.put("prompt", prompt.trim());
        req.put("n", 1);
        req.put("size", "1024x1024");
        req.put("response_format", "b64_json");
        String body = MiniJson.stringify(req);

        HttpURLConnection conn = (HttpURLConnection) new URL("https://api.openai.com/v1/images/generations").openConnection();
        conn.setConnectTimeout(15_000);
        conn.setReadTimeout(60_000);
        conn.setRequestMethod("POST");
        conn.setDoOutput(true);
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
        conn.setRequestProperty("Authorization", "Bearer " + key);
        conn.getOutputStream().write(body.getBytes(StandardCharsets.UTF_8));
        conn.getOutputStream().flush();

        String resp = readHttpText(conn, "OpenAI Images");
        Map<String, Object> root = MiniJson.parseObject(resp);
        List<Object> data = MiniJson.asArray(root.get("data"));
        if (data == null || data.isEmpty()) {
            throw new IOException("No image returned");
        }
        Map<String, Object> first = MiniJson.asObject(data.get(0));
        String b64 = MiniJson.asString(first, "b64_json", "");
        if (b64.isEmpty()) {
            throw new IOException("Empty base64 image");
        }
        return decodeBase64Bitmap(b64);
    }

    private static String readHttpText(HttpURLConnection conn, String label) throws IOException {
        try {
            int code = conn.getResponseCode();
            InputStream in = code >= 200 && code < 300 ? conn.getInputStream() : conn.getErrorStream();
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            if (in != null) {
                byte[] buf = new byte[8192];
                int n;
                while ((n = in.read(buf)) != -1) {
                    out.write(buf, 0, n);
                }
            }
            String resp = out.toString(StandardCharsets.UTF_8.name());
            if (code < 200 || code >= 300) {
                throw new IOException(label + " HTTP " + code);
            }
            return resp;
        } finally {
            conn.disconnect();
        }
    }

    private static Bitmap decodeBase64Bitmap(String b64) throws IOException {
        byte[] bytes = Base64.getDecoder().decode(b64);
        Bitmap bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        if (bmp == null) {
            throw new IOException("Could not decode generated image");
        }
        return bmp;
    }
}
