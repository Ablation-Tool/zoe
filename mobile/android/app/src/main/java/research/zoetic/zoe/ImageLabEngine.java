package research.zoetic.zoe;

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
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/**
 * Zoe Image Lab Engine (v0.6.0-beta):
 *   - 100% offline native photo editing (film filters, brightness/contrast, rotate, aspect crops,
 *     privacy pixelation blur band, and caption stamping)
 *   - Plain-English natural-language edit command parser ("warm, rotate 90, black and white, caption Sunset")
 *   - Built-in procedural "Zoe Atelier" starter artwork so editing works immediately offline
 *   - Optional online BYOK AI image generation (OpenAI Images API) when user has a key configured.
 */
final class ImageLabEngine {
    enum FilterPreset {
        ORIGINAL("Original"),
        WARM_ATELIER("Atelier Warm"),
        COBALT_NIGHT("Cobalt Night"),
        NOIR_BW("Noir B&W"),
        EMERALD_FILM("Emerald Film"),
        VIVID_POP("Vivid Pop"),
        SEPIA_VINTAGE("Sepia");

        final String label;

        FilterPreset(String label) {
            this.label = label;
        }
    }

    enum CropMode {
        ORIGINAL("Original"),
        SQUARE("1:1 Square"),
        WIDE_16_9("16:9 Wide");

        final String label;

        CropMode(String label) {
            this.label = label;
        }
    }

    static final class EditSpec {
        FilterPreset filter = FilterPreset.ORIGINAL;
        int brightness;       // -60 .. +60
        float contrast = 1.0f; // 0.6 .. 1.6
        int rotationDeg;      // 0, 90, 180, 270
        CropMode crop = CropMode.ORIGINAL;
        boolean privacyBlur;
        String caption = "";

        EditSpec copy() {
            EditSpec c = new EditSpec();
            c.filter = this.filter;
            c.brightness = this.brightness;
            c.contrast = this.contrast;
            c.rotationDeg = this.rotationDeg;
            c.crop = this.crop;
            c.privacyBlur = this.privacyBlur;
            c.caption = this.caption;
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
            if (rotationDeg != 0) {
                sb.append(" · rot ").append(rotationDeg).append("°");
            }
            if (crop != CropMode.ORIGINAL) {
                sb.append(" · ").append(crop.label);
            }
            if (privacyBlur) {
                sb.append(" · privacy blur");
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
        } else if (lower.contains("sepia") || lower.contains("vintage") || lower.contains("retro")) {
            next.filter = FilterPreset.SEPIA_VINTAGE;
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
            next.contrast = Math.min(1.6f, next.contrast + 0.25f);
        } else if (lower.contains("soft") || lower.contains("less contrast")) {
            next.contrast = Math.max(0.6f, next.contrast - 0.2f);
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
     * Generates a calm procedural Monterey-Atelier starter canvas so users can test every edit offline.
     */
    static Bitmap createAtelierStarterBitmap(int w, int h) {
        Bitmap bmp = Bitmap.createBitmap(w, h, Bitmap.Config.ARGB_8888);
        Canvas c = new Canvas(bmp);

        Paint sky = new Paint(Paint.ANTI_ALIAS_FLAG);
        sky.setShader(new LinearGradient(0, 0, 0, h,
                new int[]{Color.rgb(18, 28, 58), Color.rgb(34, 72, 128), Color.rgb(218, 124, 96), Color.rgb(245, 198, 134)},
                new float[]{0f, 0.45f, 0.78f, 1f}, Shader.TileMode.CLAMP));
        c.drawRect(0, 0, w, h, sky);

        // Glowing sun disc
        Paint sun = new Paint(Paint.ANTI_ALIAS_FLAG);
        sun.setColor(Color.argb(215, 255, 232, 178));
        c.drawCircle(w * 0.68f, h * 0.48f, w * 0.13f, sun);

        // Calm ocean horizon
        Paint sea = new Paint(Paint.ANTI_ALIAS_FLAG);
        sea.setShader(new LinearGradient(0, h * 0.56f, 0, h,
                Color.rgb(26, 62, 102), Color.rgb(12, 24, 46), Shader.TileMode.CLAMP));
        c.drawRect(0, h * 0.56f, w, h, sea);

        // Layered coastal silhouettes
        Paint ridge = new Paint(Paint.ANTI_ALIAS_FLAG);
        ridge.setColor(Color.rgb(20, 32, 54));
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
        ring.setStrokeWidth(2.5f);
        ring.setColor(Color.argb(90, 166, 214, 255));
        for (int i = 1; i <= 4; i++) {
            c.drawCircle(w * 0.68f, h * 0.48f, w * (0.14f + i * 0.06f), ring);
        }

        // Shimmering water reflections
        Paint shimmer = new Paint(Paint.ANTI_ALIAS_FLAG);
        shimmer.setColor(Color.argb(120, 255, 224, 168));
        for (int i = 0; i < 8; i++) {
            float ry = h * (0.64f + i * 0.04f);
            float rw = w * (0.16f - i * 0.012f);
            c.drawRoundRect(new RectF(w * 0.68f - rw, ry, w * 0.68f + rw, ry + 5f), 4f, 4f, shimmer);
        }
        return bmp;
    }

    static Bitmap applyEdits(Bitmap src, EditSpec spec) {
        if (src == null) {
            return null;
        }
        EditSpec s = spec == null ? new EditSpec() : spec;

        // 1. Rotation
        Bitmap working = src;
        if (s.rotationDeg % 360 != 0) {
            Matrix m = new Matrix();
            m.postRotate(s.rotationDeg % 360);
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

        // 3. ColorMatrix filter + brightness + contrast
        ColorMatrix cm = buildColorMatrix(s.filter, s.brightness, s.contrast);
        Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        paint.setColorFilter(new ColorMatrixColorFilter(cm));
        canvas.drawBitmap(working, new Rect(cx, cy, cx + cw, cy + ch), new Rect(0, 0, cw, ch), paint);
        if (working != src) {
            working.recycle();
        }

        // 4. Optional offline privacy pixelation band (center horizontal strip for faces/plates)
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

        // 5. Optional crisp caption overlay
        if (s.caption != null && !s.caption.trim().isEmpty()) {
            String cap = s.caption.trim();
            Paint bar = new Paint(Paint.ANTI_ALIAS_FLAG);
            bar.setColor(Color.argb(175, 14, 17, 26));
            float barH = Math.max(44f, ch * 0.12f);
            canvas.drawRect(0, ch - barH, cw, ch, bar);

            Paint txt = new Paint(Paint.ANTI_ALIAS_FLAG);
            txt.setColor(Color.rgb(244, 246, 250));
            txt.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
            txt.setTextAlign(Paint.Align.CENTER);
            txt.setTextSize(Math.max(18f, Math.min(34f, ch * 0.052f)));
            Paint.FontMetrics fm = txt.getFontMetrics();
            float textY = ch - (barH / 2f) - (fm.ascent + fm.descent) / 2f;
            canvas.drawText(cap, cw / 2f, textY, txt);
        }

        return out;
    }

    static ColorMatrix buildColorMatrix(FilterPreset preset, int brightness, float contrast) {
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
     * Optional online AI image generator (uses user's own OpenAI API key saved in Brain settings).
     */
    static Bitmap generateOnlineImage(Context ctx, String prompt) throws IOException {
        String key = MultiAiClient.savedKey(ctx, MultiAiClient.Provider.CHATGPT);
        if (key.isEmpty()) {
            throw new IOException("Save an OpenAI ChatGPT API key in Zoe Chat → ⚙ Brain to generate online AI images.");
        }
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
        conn.disconnect();
        String resp = out.toString("UTF-8");
        if (code < 200 || code >= 300) {
            throw new IOException("Image API HTTP " + code);
        }
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
        byte[] bytes = Base64.getDecoder().decode(b64);
        Bitmap bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.length);
        if (bmp == null) {
            throw new IOException("Could not decode generated image");
        }
        return bmp;
    }
}
