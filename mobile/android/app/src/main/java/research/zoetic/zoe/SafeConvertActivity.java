package research.zoetic.zoe;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Address;
import android.location.Geocoder;
import android.location.Location;
import android.location.LocationManager;
import android.media.MediaMetadataRetriever;
import android.media.MediaPlayer;
import android.media.MediaRecorder;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.SystemClock;
import android.provider.MediaStore;
import android.speech.tts.TextToSpeech;
import android.telephony.TelephonyManager;
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
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class SafeConvertActivity extends ComponentActivity {
    private static final String ASSET_PREFIX = "file:///android_asset/safeconvert/";
    private static final String PREFS_NAME = "uc_prefs";
    private static final String PREFS_KEY = "uc_pref_v1";
    private static final int MAX_CONTACTS_JSON_LEN = 4096;
    private static final int AUDIO_PERMISSION = 141;
    private static final int BLE_PERMISSION = 142;
    private static final int LOCATION_PERMISSION = 143;

    private static final int BLE_ACTION_NONE = 0;
    private static final int BLE_ACTION_BLIND_RELAY = 1;
    private static final int BLE_ACTION_LOCAL_SOS = 2;
    private static final int BLE_ACTION_SCAN = 3;

    private static final Set<String> EU_EEA_CODES = new HashSet<>(Arrays.asList(
            "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR",
            "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK",
            "SI", "ES", "SE", "NO", "IS", "LI", "CH"
    ));

    private static final Set<String> LATAM_CODES = new HashSet<>(Arrays.asList(
            "MX", "AR", "CO", "CL", "PE", "BR", "UY", "EC", "GT", "CR", "PA",
            "DO", "HN", "SV", "NI", "BO", "PY", "VE"
    ));

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

    private SafeBeaconMesh beaconMesh;
    private int pendingBleAction = BLE_ACTION_NONE;
    private boolean pendingLocationRequest;
    private CancellationSignal locationCancelSignal;
    private final ExecutorService ioExecutor = Executors.newSingleThreadExecutor();

    private TextToSpeech calmTts;
    private boolean calmTtsReady;
    private String pendingSpeechText;
    private String pendingSpeechLang = "en";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        videoCaptureLauncher = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> handleVideoCaptureResult());

        beaconMesh = new SafeBeaconMesh(this);
        beaconMesh.setListener(new SafeBeaconMesh.MeshListener() {
            @Override
            public void onBeaconStatusChanged(boolean advertising, byte mode, String tagPreview, String message) {
                notifyJsEvent("beacon_status", buildBeaconStateJson(message));
            }

            @Override
            public void onNearbySighting(List<SafeBeaconMesh.ParsedBeacon> sightings) {
                List<Map<String, Object>> rows = new ArrayList<>();
                for (SafeBeaconMesh.ParsedBeacon b : sightings) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    row.put("mode", b.isLocalSos() ? "sos" : "blind");
                    row.put("isSos", b.isLocalSos());
                    row.put("tag", b.rotatingTagHex.length() > 12
                            ? b.rotatingTagHex.substring(0, 12).toUpperCase(Locale.US)
                            : b.rotatingTagHex.toUpperCase(Locale.US));
                    row.put("rssi", b.rssi);
                    row.put("approxMeters", b.approxMeters);
                    row.put("seenAtMs", b.seenAtMs);
                    rows.add(row);
                }
                notifyJsEvent("beacon_sightings", MiniJson.stringify(rows));
            }
        });

        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 10), Ui.dp(this, 8), Ui.dp(this, 10), Ui.dp(this, 8));
        content.addView(Ui.topBar(this, "SafeConvert", "Private, offline unit converter"));

        webView = new WebView(this);
        webView.setId(R.id.safe_web);
        webView.setBackgroundColor(android.graphics.Color.TRANSPARENT);
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
                                "No phone, messaging, maps, or browser app is available for that action.",
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
        String themeParam = Ui.isDark(this) ? "dark" : "light";
        String regionParam = detectDeviceRegion();
        String langParam = detectDeviceLanguage();
        webView.loadUrl(ASSET_PREFIX + "index.html?theme=" + themeParam
                + "&region=" + regionParam + "&lang=" + langParam);

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

    static String mapIsoCountryToRegion(String isoCountry) {
        if (isoCountry == null) {
            return "US";
        }
        String code = isoCountry.trim().toUpperCase(Locale.US);
        if (code.isEmpty()) {
            return "US";
        }
        if ("US".equals(code) || "PR".equals(code) || "VI".equals(code) || "GU".equals(code)) {
            return "US";
        }
        if ("GB".equals(code) || "UK".equals(code)) {
            return "UK";
        }
        if ("CA".equals(code)) {
            return "CA";
        }
        if ("AU".equals(code) || "NZ".equals(code)) {
            return "AU";
        }
        if ("IN".equals(code)) {
            return "IN";
        }
        if (EU_EEA_CODES.contains(code)) {
            return "EU";
        }
        if (LATAM_CODES.contains(code)) {
            return "MX";
        }
        return "GLOBAL";
    }

    static String normalizeLangCode(String rawLang) {
        if (rawLang == null) {
            return "en";
        }
        String lang = rawLang.trim().toLowerCase(Locale.US);
        if (lang.startsWith("es")) return "es";
        if (lang.startsWith("fr")) return "fr";
        if (lang.startsWith("de")) return "de";
        if (lang.startsWith("pt")) return "pt";
        return "en";
    }

    private String detectDeviceRegion() {
        try {
            TelephonyManager tm = (TelephonyManager) getSystemService(Context.TELEPHONY_SERVICE);
            if (tm != null) {
                String net = tm.getNetworkCountryIso();
                if (net != null && !net.trim().isEmpty()) {
                    return mapIsoCountryToRegion(net);
                }
                String sim = tm.getSimCountryIso();
                if (sim != null && !sim.trim().isEmpty()) {
                    return mapIsoCountryToRegion(sim);
                }
            }
        } catch (RuntimeException ignored) {
        }
        return mapIsoCountryToRegion(Locale.getDefault().getCountry());
    }

    private String detectDeviceLanguage() {
        return normalizeLangCode(Locale.getDefault().getLanguage());
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
                || lower.startsWith("https:")
                || lower.startsWith("geo:");
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

    // --- Calm Story & Young Child Read-Aloud TTS (Silent by default, instant <10ms panic kill) ---

    private static Locale localeForLang(String langCode) {
        String norm = normalizeLangCode(langCode);
        if ("es".equals(norm)) return new Locale("es");
        if ("fr".equals(norm)) return Locale.FRENCH;
        if ("de".equals(norm)) return Locale.GERMAN;
        if ("pt".equals(norm)) return new Locale("pt");
        return Locale.US;
    }

    private void speakCalmText(String text, String langCode) {
        if (text == null || text.trim().isEmpty()) {
            return;
        }
        String clean = text.trim();
        if (clean.length() > 2800) {
            clean = clean.substring(0, 2800);
        }
        pendingSpeechText = clean;
        pendingSpeechLang = normalizeLangCode(langCode);
        if (calmTts == null) {
            calmTts = new TextToSpeech(getApplicationContext(), status -> {
                if (status == TextToSpeech.SUCCESS) {
                    calmTtsReady = true;
                    runOnUiThread(() -> {
                        if (pendingSpeechText != null && !isFinishing() && !isDestroyed()) {
                            speakWithReadyTts(pendingSpeechText, pendingSpeechLang);
                        }
                    });
                } else {
                    calmTtsReady = false;
                    notifyJsEvent("tts_error", "Offline speech voice is unavailable on this device.");
                }
            });
            return;
        }
        if (calmTtsReady) {
            speakWithReadyTts(clean, pendingSpeechLang);
        }
    }

    private void speakWithReadyTts(String text, String langCode) {
        TextToSpeech tts = calmTts;
        if (tts == null || !calmTtsReady) {
            return;
        }
        try {
            tts.setLanguage(localeForLang(langCode));
            tts.setSpeechRate(0.88f);
            tts.setPitch(1.0f);
            tts.speak(text, TextToSpeech.QUEUE_FLUSH, null, "zoe_calm_story");
            notifyJsEvent("tts_started", "Zoe is reading softly… Tap Stop or ✕ EXIT anytime.");
        } catch (RuntimeException err) {
            notifyJsEvent("tts_error", "Could not start calm voice reading.");
        }
    }

    private void stopCalmSpeech(boolean notifyJs) {
        pendingSpeechText = null;
        TextToSpeech tts = calmTts;
        if (tts != null) {
            try {
                tts.stop();
            } catch (RuntimeException ignored) {
            }
        }
        if (notifyJs) {
            notifyJsEvent("tts_stopped", "");
        }
    }

    // --- Opt-in One-Shot GPS Locator (Stops immediately after 1 fix) ---

    private boolean hasLocationPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void cancelPendingLocation() {
        CancellationSignal sig = locationCancelSignal;
        locationCancelSignal = null;
        if (sig != null) {
            try {
                sig.cancel();
            } catch (RuntimeException ignored) {
            }
        }
    }

    @SuppressWarnings("MissingPermission")
    private void requestOneShotLocation() {
        if (!hasLocationPermission()) {
            pendingLocationRequest = true;
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION},
                    LOCATION_PERMISSION);
            return;
        }
        LocationManager lm = (LocationManager) getSystemService(Context.LOCATION_SERVICE);
        if (lm == null) {
            notifyJsEvent("location_error", "Location service is unavailable on this device.");
            return;
        }
        cancelPendingLocation();
        String provider = lm.isProviderEnabled(LocationManager.GPS_PROVIDER)
                ? LocationManager.GPS_PROVIDER
                : (lm.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
                ? LocationManager.NETWORK_PROVIDER
                : null);

        if (provider == null) {
            Location last = bestLastKnownLocation(lm);
            if (last != null) {
                deliverLocationFix(last);
            } else {
                notifyJsEvent("location_error", "Location is turned off. Enable GPS or pick your region manually.");
            }
            return;
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            CancellationSignal sig = new CancellationSignal();
            locationCancelSignal = sig;
            try {
                lm.getCurrentLocation(provider, sig, getMainExecutor(), location -> {
                    locationCancelSignal = null;
                    if (location != null) {
                        deliverLocationFix(location);
                    } else {
                        Location fallback = bestLastKnownLocation(lm);
                        if (fallback != null) {
                            deliverLocationFix(fallback);
                        } else {
                            notifyJsEvent("location_error", "Could not get a GPS fix right now. Try near a window or pick your region.");
                        }
                    }
                });
            } catch (RuntimeException err) {
                locationCancelSignal = null;
                notifyJsEvent("location_error", "Location request could not start.");
            }
        } else {
            Location fallback = bestLastKnownLocation(lm);
            if (fallback != null) {
                deliverLocationFix(fallback);
            } else {
                notifyJsEvent("location_error", "No recent GPS fix found. Open Maps to locate yourself.");
            }
        }
    }

    @SuppressWarnings("MissingPermission")
    private Location bestLastKnownLocation(LocationManager lm) {
        Location best = null;
        for (String p : Arrays.asList(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER, LocationManager.PASSIVE_PROVIDER)) {
            try {
                Location candidate = lm.getLastKnownLocation(p);
                if (candidate != null && (best == null || candidate.getTime() > best.getTime())) {
                    best = candidate;
                }
            } catch (RuntimeException ignored) {
            }
        }
        return best;
    }

    private void deliverLocationFix(Location loc) {
        double lat = loc.getLatitude();
        double lon = loc.getLongitude();
        int accM = Math.max(1, Math.round(loc.getAccuracy()));
        String latStr = String.format(Locale.US, "%.5f", lat);
        String lonStr = String.format(Locale.US, "%.5f", lon);
        String mapsUrl = "https://maps.google.com/?q=" + latStr + "," + lonStr;
        String appleMapsUrl = "https://maps.apple.com/?ll=" + latStr + "," + lonStr;
        String fallbackRegion = detectDeviceRegion();

        ioExecutor.execute(() -> {
            String resolvedRegion = fallbackRegion;
            String label = latStr + ", " + lonStr;
            if (Geocoder.isPresent()) {
                try {
                    Geocoder geocoder = new Geocoder(getApplicationContext(), Locale.getDefault());
                    @SuppressWarnings("deprecation")
                    List<Address> addresses = geocoder.getFromLocation(lat, lon, 1);
                    if (addresses != null && !addresses.isEmpty()) {
                        Address addr = addresses.get(0);
                        if (addr.getCountryCode() != null && !addr.getCountryCode().isEmpty()) {
                            resolvedRegion = mapIsoCountryToRegion(addr.getCountryCode());
                        }
                        String line = addr.getAddressLine(0);
                        if (line != null && !line.trim().isEmpty()) {
                            label = line.trim();
                        }
                    }
                } catch (IOException | RuntimeException ignored) {
                    // 100% graceful offline fallback — raw GPS coordinates still work offline!
                }
            }
            Map<String, Object> payload = new LinkedHashMap<>();
            payload.put("lat", latStr);
            payload.put("lon", lonStr);
            payload.put("accuracyM", accM);
            payload.put("label", label);
            payload.put("region", resolvedRegion);
            payload.put("mapsUrl", mapsUrl);
            payload.put("appleMapsUrl", appleMapsUrl);
            notifyJsEvent("location_ready", MiniJson.stringify(payload));
        });
    }

    // --- Offline BLE Help Beacon & Blind Relay Mesh ---

    private String buildBeaconStateJson(String message) {
        Map<String, Object> state = new LinkedHashMap<>();
        state.put("advertising", beaconMesh != null && beaconMesh.isAdvertising());
        state.put("scanning", beaconMesh != null && beaconMesh.isScanning());
        state.put("remainingSec", beaconMesh != null ? beaconMesh.remainingSeconds() : 0L);
        state.put("tag", beaconMesh != null ? beaconMesh.currentTagPreview() : "");
        state.put("fingerprint", beaconMesh != null ? beaconMesh.verificationKeyFingerprint() : "");
        if (message != null) {
            state.put("message", message);
        }
        return MiniJson.stringify(state);
    }

    private void executeBleAction(int action) {
        if (beaconMesh == null) {
            return;
        }
        if (!beaconMesh.hasBlePermissions()) {
            pendingBleAction = action;
            ActivityCompat.requestPermissions(this, SafeBeaconMesh.requiredBlePermissions(), BLE_PERMISSION);
            return;
        }
        if (action == BLE_ACTION_BLIND_RELAY) {
            beaconMesh.startBeacon(SafeBeaconMesh.MODE_BLIND_RELAY);
        } else if (action == BLE_ACTION_LOCAL_SOS) {
            beaconMesh.startBeacon(SafeBeaconMesh.MODE_LOCAL_SOS);
        } else if (action == BLE_ACTION_SCAN) {
            beaconMesh.startMeshScan();
        }
    }

    private void shareBeaconVerificationKey() {
        if (beaconMesh == null) {
            return;
        }
        String fp = beaconMesh.verificationKeyFingerprint();
        String tag = beaconMesh.currentTagPreview();
        String body = "Zoe SafeConvert Offline BLE Beacon Verification Key\n"
                + "Safety Fingerprint: " + fp + "\n"
                + "Current 15-min Rotating Tag: " + tag + "\n"
                + "Keep this private with your trusted Safe People. Rotate anytime inside SafeConvert to revoke old keys.";
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe Offline Beacon Key")
                .putExtra(Intent.EXTRA_TEXT, body);
        try {
            startActivity(Intent.createChooser(share, "Share Beacon Verification Key"));
        } catch (ActivityNotFoundException error) {
            notifyJsEvent("beacon_status", buildBeaconStateJson("No sharing app available."));
        }
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
        stopCalmSpeech(false);
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
        stopCalmSpeech(false);
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
        stopCalmSpeech(false);
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

    private void stopSensitiveSensorsImmediate() {
        stopAudioPlayback();
        stopCalmSpeech(false);
        cancelPendingLocation();
        if (beaconMesh != null) {
            beaconMesh.stopAll();
        }
    }

    private void snapToCover() {
        if (awaitingVideoCapture) {
            return;
        }
        vaultUnlocked = false;
        stopAudioRecording(false);
        stopSensitiveSensorsImmediate();
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
        } else if (requestCode == BLE_PERMISSION) {
            int action = pendingBleAction;
            pendingBleAction = BLE_ACTION_NONE;
            if (beaconMesh != null && beaconMesh.hasBlePermissions() && action != BLE_ACTION_NONE) {
                executeBleAction(action);
            } else {
                notifyJsEvent("beacon_status", buildBeaconStateJson(
                        "Bluetooth permission was not granted. Offline BLE beacon did not start."));
            }
        } else if (requestCode == LOCATION_PERMISSION) {
            boolean wantLoc = pendingLocationRequest;
            pendingLocationRequest = false;
            if (wantLoc && hasLocationPermission()) {
                requestOneShotLocation();
            } else {
                notifyJsEvent("location_error",
                        "Location permission was not granted. You can still pick your region manually anytime.");
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
        stopSensitiveSensorsImmediate();
        if (calmTts != null) {
            try {
                calmTts.shutdown();
            } catch (RuntimeException ignored) {
            }
            calmTts = null;
        }
        ioExecutor.shutdownNow();
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
                    if (!visible) {
                        stopSensitiveSensorsImmediate();
                    }
                }
            });
        }

        @JavascriptInterface
        public boolean supportsMediaVault() {
            return true;
        }

        @JavascriptInterface
        public boolean supportsBeaconMesh() {
            return true;
        }

        @JavascriptInterface
        public String getDetectedRegion() {
            return detectDeviceRegion();
        }

        @JavascriptInterface
        public String getDetectedLang() {
            return detectDeviceLanguage();
        }

        @JavascriptInterface
        public void requestLocationFix() {
            runOnUiThread(SafeConvertActivity.this::requestOneShotLocation);
        }

        @JavascriptInterface
        public void speakCalmText(String text, String langCode) {
            runOnUiThread(() -> SafeConvertActivity.this.speakCalmText(text, langCode));
        }

        @JavascriptInterface
        public void stopCalmSpeech() {
            runOnUiThread(() -> SafeConvertActivity.this.stopCalmSpeech(true));
        }

        @JavascriptInterface
        public String getBeaconStateJson() {
            return buildBeaconStateJson(null);
        }

        @JavascriptInterface
        public void startBlindRelayBeacon() {
            runOnUiThread(() -> executeBleAction(BLE_ACTION_BLIND_RELAY));
        }

        @JavascriptInterface
        public void startLocalSosBeacon() {
            runOnUiThread(() -> executeBleAction(BLE_ACTION_LOCAL_SOS));
        }

        @JavascriptInterface
        public void stopBeacon() {
            runOnUiThread(() -> {
                if (beaconMesh != null) {
                    beaconMesh.stopAdvertising("Offline Help Beacon stopped.");
                }
            });
        }

        @JavascriptInterface
        public void startMeshScan() {
            runOnUiThread(() -> executeBleAction(BLE_ACTION_SCAN));
        }

        @JavascriptInterface
        public void stopMeshScan() {
            runOnUiThread(() -> {
                if (beaconMesh != null) {
                    beaconMesh.stopMeshScan();
                    notifyJsEvent("beacon_status", buildBeaconStateJson("Nearby beacon scan stopped."));
                }
            });
        }

        @JavascriptInterface
        public String rotateBeaconKeys() {
            if (beaconMesh != null) {
                beaconMesh.stopAdvertising(null);
                beaconMesh.rotateSecret();
            }
            String json = buildBeaconStateJson("Keys rotated! All previous offline beacon tags are permanently revoked.");
            notifyJsEvent("beacon_status", json);
            return json;
        }

        @JavascriptInterface
        public void shareBeaconKey() {
            runOnUiThread(SafeConvertActivity.this::shareBeaconVerificationKey);
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
