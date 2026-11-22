package research.zoetic.zoe;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class ConnectivityActivity extends ComponentActivity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean downloading = new AtomicBoolean(false);
    private final List<String> events = new ArrayList<>();
    private ConnectivityManager manager;
    private ConnectivityManager.NetworkCallback callback;
    private volatile HttpURLConnection connection;
    private TextView status;
    private TextView report;
    private int ordinal;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        scroll.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        LinearLayout content = Ui.vertical(this);
        content.setBackgroundColor(android.graphics.Color.TRANSPARENT);
        content.setPadding(Ui.dp(this, 16), Ui.dp(this, 12), Ui.dp(this, 16), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(Ui.wrapWithBackdrop(this, scroll));
        Ui.configureEdgeToEdge(this, content);

        content.addView(Ui.topBar(this, "Connectivity", "Network link & speed test"));
        status = Ui.statusBanner(this, "Network observation is idle. No callback or download is active.", Ui.COBALT);
        status.setId(R.id.network_status);
        content.addView(status);
        Button watch = Ui.primaryButton(this, "Watch link", Ui.CYAN, view -> watch());
        watch.setId(R.id.network_watch);
        Button download = Ui.button(this, "Test 1 MiB", Ui.GREEN, view -> download());
        download.setId(R.id.network_download);
        content.addView(Ui.buttonRow(this, watch, download));
        content.addView(Ui.disclosureButton(this, "Stop observation", view -> stopConnectivity()));
        report = Ui.text(this,
                "Tap Watch link to monitor Wi-Fi/cellular changes, or Test 1 MiB for a single HTTPS speed probe.",
                14.5f, Ui.TEXT);
        report.setId(R.id.network_report);
        report.setBackground(Ui.cardBackground(this, 20));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        LinearLayout.LayoutParams repLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        repLp.setMargins(0, Ui.dp(this, 6), 0, Ui.dp(this, 8));
        content.addView(report, repLp);
        TextView note = Ui.text(this,
                "Offline workflows stay available on every network. Carrier bands and emergency priority are not inferred.",
                12.5f, Ui.MUTED);
        note.setGravity(android.view.Gravity.CENTER);
        content.addView(note);
        manager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
    }

    private void watch() {
        if (manager == null) {
            status.setText("Connectivity service is unavailable on this device.");
            return;
        }
        if (callback != null) {
            stopConnectivity();
            return;
        }
        callback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onCapabilitiesChanged(Network network, NetworkCapabilities capabilities) {
                String transport = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ? "Wi-Fi"
                        : capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ? "mobile data"
                        : capabilities.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) ? "Ethernet" : "other";
                record(transport + " · validated=" + capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
                        + " · Android downstream estimate=" + capabilities.getLinkDownstreamBandwidthKbps() + " kbps");
            }

            @Override
            public void onLost(Network network) {
                record("Network lost. Offline workflows remain available.");
            }
        };
        try {
            manager.registerDefaultNetworkCallback(callback);
            status.setText("Watching transport changes. Stop observation or leave to unregister.");
        } catch (RuntimeException error) {
            callback = null;
            status.setText("Network callback failed: " + error.getMessage());
        }
    }

    private void download() {
        if (!downloading.compareAndSet(false, true)) {
            return;
        }
        status.setText("Downloading 1 MiB once from speed.hetzner.de. This is a third-party measurement, not a coverage guarantee.");
        executor.execute(() -> {
            long started = System.nanoTime();
            long total = 0;
            HttpURLConnection localConn = null;
            try {
                localConn = (HttpURLConnection) new URL("https://speed.hetzner.de/1MB.bin").openConnection();
                localConn.setConnectTimeout(8000);
                localConn.setReadTimeout(120_000);
                localConn.setRequestProperty("User-Agent", "Zoe-Mobile/0.2");
                connection = localConn;
                if (!downloading.get()) {
                    return;
                }
                localConn.connect();
                if (localConn.getResponseCode() != HttpURLConnection.HTTP_OK) {
                    throw new IOException("HTTP " + localConn.getResponseCode());
                }
                try (InputStream input = localConn.getInputStream()) {
                    byte[] buffer = new byte[16_384];
                    int count;
                    while (downloading.get() && total < 1024 * 1024 && (count = input.read(buffer)) >= 0) {
                        total += count;
                    }
                }
                if (!downloading.get()) {
                    return;
                }
                long elapsed = System.nanoTime() - started;
                double rate = NetworkSpeedTest.megabitsPerSecond(total, elapsed);
                long bytes = total;
                runOnUiThread(() -> {
                    if (downloading.get() && !isFinishing() && !isDestroyed()) {
                        report.setText(String.format(Locale.US,
                                "Downloaded %d bytes in %.3f s\nMeasured rate: %.3f Mbit/s\n\nOne third-party HTTPS endpoint is not a measure of every carrier, region, emergency service, or future connection.",
                                bytes, elapsed / 1e9, rate));
                        status.setText("Download measurement complete. No download is active.");
                    }
                });
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (downloading.get() && !isFinishing() && !isDestroyed()) {
                        status.setText("Download failed or was cancelled: " + error.getMessage()
                                + ". Offline workflows remain available.");
                    }
                });
            } finally {
                downloading.set(false);
                if (localConn != null) {
                    localConn.disconnect();
                }
                connection = null;
            }
        });
    }

    private void record(String event) {
        runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            events.add((++ordinal) + " · " + event);
            if (events.size() > 12) {
                events.remove(0);
            }
            report.setText(String.join("\n", events));
            status.setText(event);
        });
    }

    private void stopConnectivity() {
        if (callback != null && manager != null) {
            try {
                manager.unregisterNetworkCallback(callback);
            } catch (IllegalArgumentException ignored) {
            }
            callback = null;
        }
        downloading.set(false);
        HttpURLConnection active = connection;
        connection = null;
        if (active != null) {
            Thread cleanup = new Thread(active::disconnect, "zoe-conn-close");
            cleanup.setDaemon(true);
            cleanup.start();
        }
        status.setText("Connectivity observation stopped. No callback or download is active.");
    }

    @Override
    protected void onPause() {
        stopConnectivity();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        stopConnectivity();
        executor.shutdownNow();
        super.onDestroy();
    }
}
