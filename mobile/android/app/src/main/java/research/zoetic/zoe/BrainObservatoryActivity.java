package research.zoetic.zoe;

import android.annotation.SuppressLint;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
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
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Locale;

/**
 * Offline Interactive Dorothy 3D Brain Observatory Activity.
 *
 * Serves the real MNI152 / ICBM152 / AAL-116 / CIT168 WebGL2 3D human brain, synchronized
 * MNI152 T1-MRI tri-planar slices, 52 Brodmann areas, 12 Cranial Nerves, and 25 verified
 * public-domain / CC-BY anatomical plates strictly from local APK assets via a sandboxed
 * https://zoe.local/brain/ interceptor (100% offline, zero external network requests,
 * zero copyrighted textbook files).
 */
public final class BrainObservatoryActivity extends ComponentActivity {
    private static final String ASSET_PREFIX = "dorothy_brain_observatory/";
    private static final String LOCAL_HOST = "zoe.local";
    private static final String LOCAL_PATH_PREFIX = "/brain/";
    private static final String ENTRY_URL = "https://zoe.local/brain/index.html";

    private WebView webView;

    @SuppressLint("SetJavaScriptEnabled")
    @Override
    protected void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout root = Ui.vertical(this);
        root.setBackgroundColor(Color.rgb(7, 11, 18));

        // Clean borderless Zoe top bar: [←] Dorothy 3d brain  [↺] [gem]
        LinearLayout topBar = new LinearLayout(this);
        topBar.setOrientation(LinearLayout.HORIZONTAL);
        topBar.setGravity(Gravity.CENTER_VERTICAL);
        topBar.setBackgroundColor(Color.rgb(14, 20, 32));
        topBar.setPadding(Ui.dp(this, 10), Ui.dp(this, 6), Ui.dp(this, 10), Ui.dp(this, 6));

        Button backBtn = Ui.tonalIconButton(this, "←", "back to zoe home", v -> finish());
        LinearLayout.LayoutParams backLp = new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44));
        backLp.setMargins(0, 0, Ui.dp(this, 10), 0);
        topBar.addView(backBtn, backLp);

        TextView title = Ui.text(this, "Dorothy 3d brain", 18.5f, Ui.TEXT);
        title.setTextColor(Color.rgb(245, 208, 120));
        title.setTypeface(Ui.SANS_MEDIUM);
        title.setPadding(0, 0, 0, 0);
        topBar.addView(title, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f));

        Button resetBtn = Ui.tonalIconButton(this, "↺", "reset 3d brain camera view", v -> {
            if (webView != null) {
                webView.evaluateJavascript("window.__DOROTHY_API && window.__DOROTHY_API.setCameraPreset('hero');", null);
            }
        });
        LinearLayout.LayoutParams resetLp = new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44));
        resetLp.setMargins(0, 0, Ui.dp(this, 6), 0);
        topBar.addView(resetBtn, resetLp);

        ImageView homeGem = Ui.gemHomeButton(this, 28, this::finish);
        topBar.addView(homeGem, new LinearLayout.LayoutParams(Ui.dp(this, 44), Ui.dp(this, 44)));
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
        settings.setBlockNetworkLoads(false);

        webView.setWebChromeClient(new WebChromeClient());
        webView.setWebViewClient(new WebViewClient() {
            @Nullable
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request == null ? null : request.getUrl();
                return interceptLocalObservatoryAsset(uri);
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request == null ? null : request.getUrl();
                return uri == null || !LOCAL_HOST.equalsIgnoreCase(uri.getHost());
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

    @NonNull
    private WebResourceResponse interceptLocalObservatoryAsset(@Nullable Uri uri) {
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
            InputStream in = getAssets().open(ASSET_PREFIX + rel);
            String mime = mimeTypeForPath(rel);
            String encoding = mime.startsWith("text/") || mime.contains("javascript") || mime.contains("svg")
                    ? "UTF-8"
                    : null;
            return new WebResourceResponse(mime, encoding, in);
        } catch (IOException notFound) {
            return new WebResourceResponse("text/plain", "UTF-8", 404, "Not Found", null,
                    new ByteArrayInputStream("not found".getBytes(StandardCharsets.UTF_8)));
        }
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
        if (webView != null) {
            webView.loadUrl("about:blank");
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
