package research.zoetic.zoe;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.view.Gravity;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;

/**
 * Offline Interactive Dorothy 3D Brain Observatory Activity.
 *
 * Serves the full upgraded MNI152 / ICBM152 / AAL-116 / CIT168 WebGL2 3D human brain,
 * 5 functional neural circuits, 4 cerebrovascular territory simulators, 19-electrode 10-20 EEG cap,
 * 3D textured MNI152 T1-MRI slices, 3D millimeter caliper, offline Zoe Neuroscience Q&A,
 * HD walkthrough videos and gallery, and 25 verified anatomical plates strictly from local APK assets
 * via a sandboxed https://zoe.local/brain/ interceptor with HTTP byte-range support (100% offline).
 */
public final class BrainObservatoryActivity extends ComponentActivity {
    static final String EXTRA_START_TAB = "dorothy_start_tab";
    static final String EXTRA_FOCUS_QUERY = "dorothy_focus_query";

    private static final String ASSET_PREFIX = "dorothy_brain_observatory/";
    private static final String LOCAL_HOST = "zoe.local";
    private static final String LOCAL_PATH_PREFIX = "/brain/";
    private static final String ENTRY_URL = "https://zoe.local/brain/index.html";

    private WebView webView;
    private TextToSpeech tts;
    private boolean ttsReady;
    private String initialTab = "";
    private String initialFocusQuery = "";

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Intent launch = getIntent();
        if (launch != null) {
            String tab = launch.getStringExtra(EXTRA_START_TAB);
            String focus = launch.getStringExtra(EXTRA_FOCUS_QUERY);
            if (tab != null) initialTab = tab.trim();
            if (focus != null) initialFocusQuery = focus.trim();
        }

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.rgb(7, 11, 18));

        // Clean borderless Zoe top bar: [←] Dorothy 3d brain  [ask zoe] [↺] [gem]
        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setBackgroundColor(Color.rgb(14, 20, 32));
        topBar.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));

        Button backBtn = Ui.tonalIconButton(this, "←", "Back to Zoe Home", v -> finish());
        LinearLayout.LayoutParams backLp = new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44));
        backLp.setMargins(0, 0, Ui.dp(this, 10), 0);
        topBar.addView(backBtn, backLp);

        TextView title = Ui.text(this, "Dorothy 3D Brain", 18f, Ui.TEXT);
        title.setTextColor(Color.rgb(245, 208, 120));
        title.setTypeface(Ui.SANS_MEDIUM);
        title.setPadding(0, 0, 0, 0);
        topBar.addView(title, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Button askZoeBtn = new Button(this);
        askZoeBtn.setText("Ask Zoe");
        askZoeBtn.setAllCaps(false);
        askZoeBtn.setTextSize(12.5f);
        askZoeBtn.setTypeface(Ui.SANS_MEDIUM);
        askZoeBtn.setTextColor(Color.rgb(245, 208, 120));
        askZoeBtn.setBackground(Ui.tonalPillDrawable(this, Color.rgb(20, 40, 66), Color.rgb(56, 189, 248), 18));
        askZoeBtn.setPadding(Ui.dp(this, 11), 0, Ui.dp(this, 11), 0);
        askZoeBtn.setMinHeight(Ui.dp(this, 36));
        askZoeBtn.setMinimumHeight(Ui.dp(this, 36));
        askZoeBtn.setStateListAnimator(null);
        askZoeBtn.setContentDescription("Ask Zoe neuroscience questions");
        askZoeBtn.setOnClickListener(v -> {
            if (webView != null) {
                webView.evaluateJavascript("window.switchTab && window.switchTab('askzoe');", null);
            }
        });
        LinearLayout.LayoutParams askLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.WRAP_CONTENT, Ui.dp(this, 36));
        askLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        topBar.addView(askZoeBtn, askLp);

        Button resetBtn = Ui.tonalIconButton(this, "↺", "Reset 3D Brain Camera View", v -> {
            if (webView != null) {
                webView.evaluateJavascript(
                        "(function(){window.switchTab&&window.switchTab('brain3d');window.__DOROTHY_API&&window.__DOROTHY_API.setCameraPreset('hero');})();",
                        null);
            }
        });
        LinearLayout.LayoutParams resetLp = new LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42));
        resetLp.setMargins(0, 0, Ui.dp(this, 4), 0);
        topBar.addView(resetBtn, resetLp);

        ImageView homeGem = Ui.gemHomeButton(this, 26, this::finish);
        topBar.addView(homeGem, new LinearLayout.LayoutParams(Ui.dp(this, 42), Ui.dp(this, 42)));
        root.addView(topBar);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.rgb(7, 11, 18));
        webView.setLayerType(View.LAYER_TYPE_HARDWARE, null);

        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setBuiltInZoomControls(false);
        settings.setDisplayZoomControls(false);
        settings.setUseWideViewPort(true);
        settings.setLoadWithOverviewMode(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setBlockNetworkLoads(false);

        webView.addJavascriptInterface(new ZoeNeuroBridge(), "ZoeNativeBridge");
        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Nullable
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request == null ? null : request.getUrl();
                Map<String, String> headers = request == null ? null : request.getRequestHeaders();
                return interceptLocalObservatoryAsset(uri, headers);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request == null ? null : request.getUrl();
                return uri == null || !LOCAL_HOST.equalsIgnoreCase(uri.getHost());
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                applyInitialNavigation();
            }
        });

        root.addView(webView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f));

        setContentView(root);
        Ui.configureEdgeToEdge(this, root);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView != null) {
                    webView.evaluateJavascript(
                            "(function(){var lb=document.getElementById('lightbox');if(lb&&lb.classList.contains('open')){window.closeLightbox();return 'closed';}return 'none';})()",
                            res -> {
                                if (res == null || !res.contains("closed")) {
                                    finish();
                                }
                            });
                } else {
                    finish();
                }
            }
        });

        webView.loadUrl(ENTRY_URL);
    }

    private void applyInitialNavigation() {
        if (webView == null) return;
        if (!initialFocusQuery.isEmpty()) {
            String escaped = escapeJs(initialFocusQuery);
            initialFocusQuery = "";
            webView.postDelayed(() -> {
                if (webView != null && !isFinishing() && !isDestroyed()) {
                    webView.evaluateJavascript(
                            "window.__DOROTHY_ZOE_QA && window.__DOROTHY_ZOE_QA.focusFromQuery('" + escaped + "');",
                            null);
                }
            }, 350L);
            return;
        }
        if (!initialTab.isEmpty()) {
            String escapedTab = escapeJs(initialTab);
            initialTab = "";
            webView.evaluateJavascript("window.switchTab && window.switchTab('" + escapedTab + "');", null);
        }
    }

    private static String escapeJs(String s) {
        return s.replace("\\", "\\\\").replace("'", "\\'").replace("\n", " ").replace("\r", " ");
    }

    private final class ZoeNeuroBridge {
        @JavascriptInterface
        public void speak(String text) {
            if (text == null || text.trim().isEmpty()) return;
            final String clean = text.trim();
            runOnUiThread(() -> speakAloud(clean));
        }

        @JavascriptInterface
        public void openChat(String prompt) {
            final String clean = prompt == null ? "" : prompt.trim();
            runOnUiThread(() -> {
                Intent chat = new Intent(BrainObservatoryActivity.this, ConversationActivity.class);
                if (!clean.isEmpty()) {
                    chat.putExtra(ConversationActivity.EXTRA_INITIAL_PROMPT, clean);
                }
                startActivity(chat);
            });
        }
    }

    private void speakAloud(String text) {
        if (tts == null) {
            tts = new TextToSpeech(this, status -> {
                ttsReady = (status == TextToSpeech.SUCCESS);
                if (ttsReady && tts != null) {
                    tts.setLanguage(Locale.US);
                    tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "dorothy-neuro");
                }
            });
        } else if (ttsReady) {
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "dorothy-neuro");
        }
    }

    @NonNull
    private WebResourceResponse interceptLocalObservatoryAsset(
            @Nullable Uri uri, @Nullable Map<String, String> reqHeaders) {
        if (uri == null || !LOCAL_HOST.equalsIgnoreCase(uri.getHost())) {
            return forbiddenResponse();
        }
        String path = uri.getPath();
        if (path == null || !path.startsWith(LOCAL_PATH_PREFIX)) {
            return forbiddenResponse();
        }
        String rel = path.substring(LOCAL_PATH_PREFIX.length());
        if (rel.isEmpty() || rel.contains("..") || rel.startsWith("/") || rel.contains("\\")) {
            return forbiddenResponse();
        }
        try {
            String mime = mimeTypeForPath(rel);
            String rangeHeader = findHeaderIgnoreCase(reqHeaders, "Range");
            if (rangeHeader != null && rangeHeader.startsWith("bytes=")) {
                byte[] all = readAssetBytes(ASSET_PREFIX + rel);
                int total = all.length;
                String spec = rangeHeader.substring("bytes=".length()).trim();
                int comma = spec.indexOf(',');
                if (comma >= 0) spec = spec.substring(0, comma).trim();
                int dash = spec.indexOf('-');
                int start = 0;
                int end = total - 1;
                if (dash >= 0) {
                    String sStart = spec.substring(0, dash).trim();
                    String sEnd = spec.substring(dash + 1).trim();
                    if (!sStart.isEmpty()) start = Integer.parseInt(sStart);
                    if (!sEnd.isEmpty()) end = Math.min(total - 1, Integer.parseInt(sEnd));
                }
                if (start < 0 || start >= total || end < start) {
                    Map<String, String> errHeaders = new HashMap<>();
                    errHeaders.put("Content-Range", "bytes */" + total);
                    return new WebResourceResponse("text/plain", "UTF-8", 416, "Range Not Satisfiable",
                            errHeaders, new ByteArrayInputStream(new byte[0]));
                }
                int len = end - start + 1;
                Map<String, String> respHeaders = new HashMap<>();
                respHeaders.put("Accept-Ranges", "bytes");
                respHeaders.put("Content-Range", "bytes " + start + "-" + end + "/" + total);
                respHeaders.put("Content-Length", String.valueOf(len));
                return new WebResourceResponse(mime, null, 206, "Partial Content",
                        respHeaders, new ByteArrayInputStream(all, start, len));
            }

            InputStream in = getAssets().open(ASSET_PREFIX + rel);
            String encoding = mime.startsWith("text/") || mime.contains("javascript") || mime.contains("svg")
                    ? "UTF-8"
                    : null;
            Map<String, String> respHeaders = new HashMap<>();
            respHeaders.put("Accept-Ranges", "bytes");
            return new WebResourceResponse(mime, encoding, 200, "OK", respHeaders, in);
        } catch (IOException | NumberFormatException notFound) {
            return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null,
                    new ByteArrayInputStream("not found".getBytes(StandardCharsets.UTF_8)));
        }
    }

    private byte[] readAssetBytes(String assetPath) throws IOException {
        try (InputStream in = getAssets().open(assetPath);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[16384];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
            }
            return out.toByteArray();
        }
    }

    @Nullable
    private static String findHeaderIgnoreCase(@Nullable Map<String, String> headers, String key) {
        if (headers == null) return null;
        for (Map.Entry<String, String> e : headers.entrySet()) {
            if (e.getKey() != null && e.getKey().equalsIgnoreCase(key)) {
                return e.getValue();
            }
        }
        return null;
    }

    private static WebResourceResponse forbiddenResponse() {
        return new WebResourceResponse("text/plain", "UTF-8", 403, "Forbidden", null,
                new ByteArrayInputStream("offline local observatory only".getBytes(StandardCharsets.UTF_8)));
    }

    private static String mimeTypeForPath(String relPath) {
        String low = relPath.toLowerCase(Locale.US);
        if (low.endsWith(".html")) return "text/html";
        if (low.endsWith(".js")) return "application/javascript";
        if (low.endsWith(".css")) return "text/css";
        if (low.endsWith(".json")) return "application/json";
        if (low.endsWith(".svg")) return "image/svg+xml";
        if (low.endsWith(".png")) return "image/png";
        if (low.endsWith(".jpg") || low.endsWith(".jpeg")) return "image/jpeg";
        if (low.endsWith(".webp")) return "image/webp";
        if (low.endsWith(".gif")) return "image/gif";
        if (low.endsWith(".mp4")) return "video/mp4";
        if (low.endsWith(".webm")) return "video/webm";
        return "application/octet-stream";
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (webView != null) {
            webView.onResume();
        }
    }

    @Override
    protected void onPause() {
        if (webView != null) {
            webView.onPause();
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        if (tts != null) {
            tts.stop();
            tts.shutdown();
            tts = null;
        }
        if (webView != null) {
            webView.loadUrl("about:blank");
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
