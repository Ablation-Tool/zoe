package research.zoetic.zoe;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.media.MediaMetadataRetriever;
import android.media.MediaPlayer;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.view.WindowManager;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.LinearLayout;
import android.widget.Toast;

import androidx.activity.ComponentActivity;
import androidx.activity.OnBackPressedCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;
import androidx.core.content.FileProvider;

import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.IOException;
import java.io.UnsupportedEncodingException;
import java.net.URLDecoder;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Locale;

public final class SafeConvertActivity extends ComponentActivity {
    private static final String ASSET_PREFIX = "file:///android_asset/safeconvert/";
    private static final String PREFS_NAME = "uc_prefs";
    private static final String PREFS_KEY = "uc_pref_v1";
    private static final int MAX_CONTACTS_JSON_LEN = 4096;
    private static final int AUDIO_PERMISSION = 141;

    private WebView webView;
    private MediaRecorder audioRecorder;
    private File activeAudioFile;
    private long audioStartMs;
    private boolean audioRecording;
    private boolean pendingAudioStart;
    private MediaPlayer audioPlayer;
    private String playingEntryId;
    private File pendingVideoFile;
    private boolean awaitingVideoCapture;
    private volatile boolean vaultUnlocked;
    private ActivityResultLauncher<Intent> videoCaptureLauncher;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        videoCaptureLauncher = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> handleVideoCaptureResult());

        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
        content.addView(Ui.topBar(this, "SafeConvert", "Private, offline unit converter"));

        webView = new WebView(this);
        webView.setId(R.id.safe_web);
        webView.setContentDescription("Offline unit converter and safety resources");
        webView.getSettings().setJavaScriptEnabled(true);
        webView.getSettings().setDomStorageEnabled(true);
        webView.getSettings().setAllowFileAccess(true);
        webView.getSettings().setAllowContentAccess(false);
        webView.getSettings().setAllowFileAccessFromFileURLs(false);
        webView.getSettings().setAllowUniversalAccessFromFileURLs(false);
        webView.getSettings().setBlockNetworkLoads(true);
        webView.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        WebView.setWebContentsDebuggingEnabled(false);
        webView.addJavascriptInterface(new SafeBridge(), "SafeStore");
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request == null ? null : request.getUrl();
                if (uri != null && uri.toString().startsWith(ASSET_PREFIX)) {
                    return null;
                }
                return new WebResourceResponse("text/plain", "UTF-8",
                        new ByteArrayInputStream("".getBytes(StandardCharsets.UTF_8)));
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request == null ? null : request.getUrl();
                if (uri == null) {
                    return true;
                }
                String url = uri.toString();
                if (url.startsWith(ASSET_PREFIX)) {
                    return false;
                }
                Intent intent = buildExternalIntent(url);
                if (intent != null) {
                    try {
                        startActivity(intent);
                    } catch (ActivityNotFoundException | IllegalArgumentException error) {
                        Toast.makeText(
                                SafeConvertActivity.this,
                                "No phone, messaging, or browser app is available for that action.",
                                Toast.LENGTH_SHORT).show();
                    }
                }
                return true;
            }
        });
        content.addView(webView, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, 0, 1.0f));
        setContentView(Ui.wrapWithBackdrop(this, content));
        Ui.configureEdgeToEdge(this, content);
        webView.loadUrl(ASSET_PREFIX + "index.html");

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (webView == null) {
                    finish();
                    return;
                }
                webView.evaluateJavascript(
                        "(function(){var h=document.getElementById('help');return !!h && !h.hidden && !h.classList.contains('hidden');})();",
                        value -> {
                            if ("true".equals(value)) {
                                snapToCover();
                            } else {
                                finish();
                            }
                        });
            }
        });
    }

    private File vaultDir() {
        return SafeEvidenceStore.vaultDir(this);
    }

    private boolean canReadVault() {
        return !SafeVaultLock.hasPasscode(this) || vaultUnlocked;
    }

    static String sanitizeContactsJson(String json) {
        if (json == null) {
            return null;
        }
        String trimmed = json.trim();
        if (trimmed.isEmpty() || trimmed.length() > MAX_CONTACTS_JSON_LEN) {
            return null;
        }
        if (!trimmed.startsWith("[") || !trimmed.endsWith("]")) {
            return null;
        }
        return trimmed;
    }

    static boolean isAllowedExternalScheme(String url) {
        if (url == null) {
            return false;
        }
        String lower = url.trim().toLowerCase(Locale.US);
        return lower.startsWith("tel:")
                || lower.startsWith("sms:")
                || lower.startsWith("mailto:")
                || lower.startsWith("https:");
    }

    static String[] parseSmsTargetAndBody(String url) {
        if (url == null) {
            return new String[]{"", ""};
        }
        String trimmed = url.trim();
        if (!trimmed.toLowerCase(Locale.US).startsWith("sms:")) {
            return new String[]{"", ""};
        }
        String rest = trimmed.substring(4);
        int q = rest.indexOf('?');
        String target = q >= 0 ? rest.substring(0, q) : rest;
        String body = "";
        if (q >= 0 && q + 1 < rest.length()) {
            for (String pair : rest.substring(q + 1).split("&")) {
                if (pair.startsWith("body=") && pair.length() > 5) {
                    try {
                        body = URLDecoder.decode(pair.substring(5), "UTF-8");
                    } catch (UnsupportedEncodingException | IllegalArgumentException ignored) {
                        body = pair.substring(5);
                    }
                    break;
                }
            }
        }
        return new String[]{target, body};
    }

    private Intent buildExternalIntent(String url) {
        if (!isAllowedExternalScheme(url)) {
            return null;
        }
        String trimmed = url.trim();
        String lower = trimmed.toLowerCase(Locale.US);
        if (lower.startsWith("tel:")) {
            return new Intent(Intent.ACTION_DIAL, Uri.parse(trimmed));
        }
        if (lower.startsWith("sms:")) {
            String[] parsed = parseSmsTargetAndBody(trimmed);
            Intent intent = new Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + parsed[0]));
            if (!parsed[1].isEmpty()) {
                intent.putExtra("sms_body", parsed[1]);
            }
            return intent;
        }
        if (lower.startsWith("mailto:")) {
            return new Intent(Intent.ACTION_SENDTO, Uri.parse(trimmed));
        }
        return new Intent(Intent.ACTION_VIEW, Uri.parse(trimmed));
    }

    @SuppressWarnings("deprecation")
    private static MediaRecorder createLegacyRecorder() {
        return new MediaRecorder();
    }

    private void startAudioRecording() {
        if (audioRecording) {
            return;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO)
                != PackageManager.PERMISSION_GRANTED) {
            pendingAudioStart = true;
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.RECORD_AUDIO}, AUDIO_PERMISSION);
            return;
        }
        stopAudioPlayback();
        File dir = vaultDir();
        if (!dir.exists() && !dir.mkdirs()) {
            notifyJsEvent("audio_error", "Could not create private vault folder.");
            return;
        }
        activeAudioFile = new File(dir, "aud_" + System.currentTimeMillis() + ".m4a");
        MediaRecorder rec = null;
        try {
            rec = Build.VERSION.SDK_INT >= 31 ? new MediaRecorder(this) : createLegacyRecorder();
            rec.setAudioSource(MediaRecorder.AudioSource.MIC);
            rec.setOutputFormat(MediaRecorder.OutputFormat.MPEG_4);
            rec.setAudioEncoder(MediaRecorder.AudioEncoder.AAC);
            rec.setAudioEncodingBitRate(96_000);
            rec.setAudioSamplingRate(44_100);
            rec.setOutputFile(activeAudioFile.getAbsolutePath());
            rec.prepare();
            rec.start();
            audioRecorder = rec;
            audioStartMs = SystemClock.elapsedRealtime();
            audioRecording = true;
            notifyJsEvent("audio_started", "Recording audio privately… Tap Stop & save or ✕ EXIT anytime.");
        } catch (IOException | RuntimeException error) {
            if (rec != null) {
                try {
                    rec.release();
                } catch (RuntimeException ignored) {
                }
            }
            if (activeAudioFile != null && activeAudioFile.exists()) {
                //noinspection ResultOfMethodCallIgnored
                activeAudioFile.delete();
            }
            activeAudioFile = null;
            audioRecorder = null;
            audioRecording = false;
            notifyJsEvent("audio_error", "Could not start audio recorder: " + error.getMessage());
        }
    }

    private void stopAudioRecording(boolean notifyJs) {
        if (!audioRecording) {
            return;
        }
        MediaRecorder rec = audioRecorder;
        File file = activeAudioFile;
        long started = audioStartMs;
        audioRecorder = null;
        activeAudioFile = null;
        audioRecording = false;
        if (rec != null) {
            try {
                rec.stop();
            } catch (RuntimeException ignored) {
            } finally {
                try {
                    rec.release();
                } catch (RuntimeException ignored) {
                }
            }
        }
        int durationSec = Math.max(1, (int) Math.round((SystemClock.elapsedRealtime() - started) / 1000.0));
        if (file != null && file.isFile() && file.length() > 0) {
            SafeEvidenceStore.addMedia(vaultDir(), "audio", file, "audio/mp4", "Audio recording", durationSec);
            if (notifyJs) {
                String msg = canReadVault()
                        ? "Saved private audio recording (" + durationSec + "s, SHA-256 verified)."
                        : "Saved privately into your locked Safety Log (" + durationSec + "s, SHA-256 verified). Unlock to review.";
                notifyJsEvent("vault_updated", msg);
            }
        } else {
            if (file != null && file.exists()) {
                //noinspection ResultOfMethodCallIgnored
                file.delete();
            }
            if (notifyJs) {
                notifyJsEvent("audio_error", "Audio recording was empty or cancelled.");
            }
        }
    }

    private void startVideoCapture() {
        stopAudioRecording(true);
        stopAudioPlayback();
        File dir = vaultDir();
        if (!dir.exists() && !dir.mkdirs()) {
            notifyJsEvent("video_error", "Could not create private vault folder.");
            return;
        }
        pendingVideoFile = new File(dir, "vid_" + System.currentTimeMillis() + ".mp4");
        try {
            Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", pendingVideoFile);
            Intent intent = new Intent(MediaStore.ACTION_VIDEO_CAPTURE)
                    .putExtra(MediaStore.EXTRA_OUTPUT, uri)
                    .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION | Intent.FLAG_GRANT_READ_URI_PERMISSION);
            awaitingVideoCapture = true;
            videoCaptureLauncher.launch(intent);
        } catch (ActivityNotFoundException | IllegalArgumentException error) {
            awaitingVideoCapture = false;
            if (pendingVideoFile != null && pendingVideoFile.exists()) {
                //noinspection ResultOfMethodCallIgnored
                pendingVideoFile.delete();
            }
            pendingVideoFile = null;
            notifyJsEvent("video_error", "No camera app is available to record video.");
        }
    }

    private void handleVideoCaptureResult() {
        awaitingVideoCapture = false;
        applyHelpWindowShield(true);
        File file = pendingVideoFile;
        pendingVideoFile = null;
        if (file != null && file.isFile() && file.length() > 0) {
            int durationSec = readVideoDurationSeconds(file);
            SafeEvidenceStore.addMedia(vaultDir(), "video", file, "video/mp4", "Video recording", durationSec);
            String msg = canReadVault()
                    ? "Saved private video recording (" + durationSec + "s, SHA-256 verified)."
                    : "Saved privately into your locked Safety Log (" + durationSec + "s, SHA-256 verified). Unlock to review.";
            notifyJsEvent("vault_updated", msg);
        } else {
            if (file != null && file.exists()) {
                //noinspection ResultOfMethodCallIgnored
                file.delete();
            }
            notifyJsEvent("video_cancelled", "Video capture cancelled.");
        }
    }

    private static int readVideoDurationSeconds(File file) {
        MediaMetadataRetriever mmr = new MediaMetadataRetriever();
        try {
            mmr.setDataSource(file.getAbsolutePath());
            String msStr = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
            if (msStr != null) {
                long ms = Long.parseLong(msStr);
                return Math.max(1, (int) Math.round(ms / 1000.0));
            }
        } catch (RuntimeException ignored) {
        } finally {
            try {
                mmr.release();
            } catch (Exception ignored) {
            }
        }
        return 0;
    }

    private void playOrToggleAudio(String entryId) {
        if (!canReadVault()) {
            notifyJsEvent("audio_error", "Private Safety Log is locked. Enter your passcode first.");
            return;
        }
        if (entryId == null || entryId.isEmpty()) {
            return;
        }
        if (entryId.equals(playingEntryId)) {
            stopAudioPlayback();
            notifyJsEvent("playback_stopped", "Playback stopped.");
            return;
        }
        stopAudioPlayback();
        SafeEvidenceStore.Entry entry = SafeEvidenceStore.findById(vaultDir(), entryId);
        File file = SafeEvidenceStore.resolveMediaFile(vaultDir(), entry);
        if (file == null) {
            notifyJsEvent("audio_error", "Audio recording file could not be found.");
            return;
        }
        MediaPlayer player = new MediaPlayer();
        try {
            player.setDataSource(file.getAbsolutePath());
            player.setOnCompletionListener(mp -> {
                stopAudioPlayback();
                notifyJsEvent("playback_stopped", "Playback finished.");
            });
            player.prepare();
            player.start();
            audioPlayer = player;
            playingEntryId = entryId;
            notifyJsEvent("playback_started:" + entryId, "Playing private audio recording…");
        } catch (IOException | RuntimeException error) {
            try {
                player.release();
            } catch (RuntimeException ignored) {
            }
            notifyJsEvent("audio_error", "Could not play audio recording.");
        }
    }

    private void stopAudioPlayback() {
        MediaPlayer player = audioPlayer;
        audioPlayer = null;
        playingEntryId = null;
        if (player != null) {
            try {
                if (player.isPlaying()) {
                    player.stop();
                }
            } catch (IllegalStateException ignored) {
            }
            try {
                player.release();
            } catch (RuntimeException ignored) {
            }
        }
    }

    private void openVideo(String entryId) {
        if (!canReadVault()) {
            notifyJsEvent("video_error", "Private Safety Log is locked. Enter your passcode first.");
            return;
        }
        SafeEvidenceStore.Entry entry = SafeEvidenceStore.findById(vaultDir(), entryId);
        File file = SafeEvidenceStore.resolveMediaFile(vaultDir(), entry);
        if (file == null) {
            notifyJsEvent("video_error", "Video recording file could not be found.");
            return;
        }
        try {
            Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", file);
            Intent view = new Intent(Intent.ACTION_VIEW)
                    .setDataAndType(uri, "video/mp4")
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            startActivity(view);
        } catch (ActivityNotFoundException | IllegalArgumentException error) {
            notifyJsEvent("video_error", "No video player app is available.");
        }
    }

    private void shareEvidence(String entryId) {
        if (!canReadVault()) {
            notifyJsEvent("audio_error", "Private Safety Log is locked. Unlock and grant permission first.");
            return;
        }
        SafeEvidenceStore.Entry entry = SafeEvidenceStore.findById(vaultDir(), entryId);
        if (entry == null) {
            return;
        }
        String summary = "UTC: " + entry.timestampUtc
                + "\nType: " + entry.type.toUpperCase(Locale.US)
                + (entry.note.isEmpty() ? "" : "\nNote: " + entry.note)
                + (entry.sha256.isEmpty() ? "" : "\nSHA-256: " + entry.sha256);
        Intent share = new Intent(Intent.ACTION_SEND);
        share.putExtra(Intent.EXTRA_SUBJECT, "Safety Log Entry · " + entry.timestampUtc);
        share.putExtra(Intent.EXTRA_TEXT, summary);
        File file = SafeEvidenceStore.resolveMediaFile(vaultDir(), entry);
        if (file != null) {
            try {
                Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", file);
                share.setType(entry.mimeType.isEmpty() ? "*/*" : entry.mimeType);
                share.putExtra(Intent.EXTRA_STREAM, uri);
                share.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (IllegalArgumentException error) {
                share.setType("text/plain");
            }
        } else {
            share.setType("text/plain");
        }
        try {
            startActivity(Intent.createChooser(share, "Share Safety Log proof"));
        } catch (ActivityNotFoundException error) {
            notifyJsEvent("audio_error", "No sharing app is available.");
        }
    }

    private void shareAllEvidence() {
        if (!canReadVault()) {
            notifyJsEvent("audio_error", "Private Safety Log is locked. Unlock and grant permission first.");
            return;
        }
        List<SafeEvidenceStore.Entry> entries = SafeEvidenceStore.load(vaultDir());
        if (entries.isEmpty()) {
            notifyJsEvent("audio_error", "Safety Log has no entries to share yet.");
            return;
        }
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Safety Log Export")
                .putExtra(Intent.EXTRA_TEXT, SafeEvidenceStore.formatExportText(entries));
        try {
            startActivity(Intent.createChooser(share, "Share full Safety Log"));
        } catch (ActivityNotFoundException error) {
            notifyJsEvent("audio_error", "No sharing app is available.");
        }
    }

    private void notifyJsEvent(String type, String statusText) {
        String script = "if (typeof onSafeMediaEvent === 'function') { onSafeMediaEvent("
                + MiniJson.stringify(type) + ", " + MiniJson.stringify(statusText) + "); }";
        runOnUiThread(() -> {
            if (webView != null && !isFinishing() && !isDestroyed()) {
                webView.evaluateJavascript(script, null);
            }
        });
    }

    private void applyHelpWindowShield(boolean visible) {
        if (visible) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        } else {
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
        }
    }

    private void snapToCover() {
        if (awaitingVideoCapture) {
            return;
        }
        vaultUnlocked = false;
        stopAudioRecording(false);
        stopAudioPlayback();
        applyHelpWindowShield(false);
        if (webView != null) {
            webView.evaluateJavascript("if (typeof exitHelp === 'function') { exitHelp(); }", null);
        }
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == AUDIO_PERMISSION) {
            boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
            if (granted && pendingAudioStart) {
                pendingAudioStart = false;
                startAudioRecording();
            } else {
                pendingAudioStart = false;
                notifyJsEvent("audio_error",
                        "Microphone permission was not granted. Audio recording did not start (notes and video still work).");
            }
        }
    }

    @Override
    protected void onUserLeaveHint() {
        snapToCover();
        super.onUserLeaveHint();
    }

    @Override
    protected void onStop() {
        snapToCover();
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        vaultUnlocked = false;
        stopAudioRecording(false);
        stopAudioPlayback();
        applyHelpWindowShield(false);
        if (webView != null) {
            webView.destroy();
        }
        super.onDestroy();
    }

    private final class SafeBridge {
        @JavascriptInterface
        public String loadContacts() {
            return getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getString(PREFS_KEY, "[]");
        }

        @JavascriptInterface
        public boolean saveContacts(String json) {
            String clean = sanitizeContactsJson(json);
            if (clean == null) {
                return false;
            }
            return getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
                    .edit()
                    .putString(PREFS_KEY, clean)
                    .commit();
        }

        @JavascriptInterface
        public void setHelpVisible(boolean visible) {
            runOnUiThread(() -> {
                if (!isFinishing() && !isDestroyed()) {
                    applyHelpWindowShield(visible);
                }
            });
        }

        @JavascriptInterface
        public boolean supportsMediaVault() {
            return true;
        }

        @JavascriptInterface
        public boolean hasVaultPasscode() {
            return SafeVaultLock.hasPasscode(SafeConvertActivity.this);
        }

        @JavascriptInterface
        public boolean isVaultUnlocked() {
            return canReadVault();
        }

        @JavascriptInterface
        public boolean setVaultPasscode(String code) {
            if (SafeVaultLock.setPasscode(SafeConvertActivity.this, code)) {
                vaultUnlocked = true;
                return true;
            }
            return false;
        }

        @JavascriptInterface
        public boolean unlockVault(String candidate) {
            if (SafeVaultLock.verifyPasscode(SafeConvertActivity.this, candidate)) {
                vaultUnlocked = true;
                return true;
            }
            return false;
        }

        @JavascriptInterface
        public void lockVaultNow() {
            vaultUnlocked = false;
            runOnUiThread(SafeConvertActivity.this::stopAudioPlayback);
        }

        @JavascriptInterface
        public boolean removeVaultPasscode(String currentCode) {
            if (!SafeVaultLock.hasPasscode(SafeConvertActivity.this)
                    || SafeVaultLock.verifyPasscode(SafeConvertActivity.this, currentCode)) {
                SafeVaultLock.clearPasscode(SafeConvertActivity.this);
                vaultUnlocked = true;
                return true;
            }
            return false;
        }

        @JavascriptInterface
        public String loadEvidence() {
            if (!canReadVault()) {
                return "[]";
            }
            return SafeEvidenceStore.loadJson(vaultDir());
        }

        @JavascriptInterface
        public String addTextEvidence(String note) {
            SafeEvidenceStore.addText(vaultDir(), note);
            if (!canReadVault()) {
                return "[]";
            }
            return SafeEvidenceStore.loadJson(vaultDir());
        }

        @JavascriptInterface
        public String deleteEvidence(String id) {
            if (!canReadVault()) {
                return "[]";
            }
            if (id != null && id.equals(playingEntryId)) {
                runOnUiThread(SafeConvertActivity.this::stopAudioPlayback);
            }
            SafeEvidenceStore.deleteEntry(vaultDir(), id);
            return SafeEvidenceStore.loadJson(vaultDir());
        }

        @JavascriptInterface
        public String clearAllEvidence() {
            if (!canReadVault()) {
                return "[]";
            }
            runOnUiThread(SafeConvertActivity.this::stopAudioPlayback);
            SafeEvidenceStore.clearAll(vaultDir());
            return "[]";
        }

        @JavascriptInterface
        public boolean isAudioRecording() {
            return audioRecording;
        }

        @JavascriptInterface
        public void startAudioRecording() {
            runOnUiThread(SafeConvertActivity.this::startAudioRecording);
        }

        @JavascriptInterface
        public void stopAudioRecording() {
            runOnUiThread(() -> SafeConvertActivity.this.stopAudioRecording(true));
        }

        @JavascriptInterface
        public void startVideoRecording() {
            runOnUiThread(SafeConvertActivity.this::startVideoCapture);
        }

        @JavascriptInterface
        public void togglePlayAudio(String id) {
            runOnUiThread(() -> SafeConvertActivity.this.playOrToggleAudio(id));
        }

        @JavascriptInterface
        public void openVideo(String id) {
            runOnUiThread(() -> SafeConvertActivity.this.openVideo(id));
        }

        @JavascriptInterface
        public void shareEvidence(String id) {
            runOnUiThread(() -> SafeConvertActivity.this.shareEvidence(id));
        }

        @JavascriptInterface
        public void shareAllEvidence() {
            runOnUiThread(SafeConvertActivity.this::shareAllEvidence);
        }
    }
}
