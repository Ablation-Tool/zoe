package research.zoetic.zoe;

import android.content.Context;
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.os.Bundle;
import android.widget.Button;
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
    private HttpURLConnection connection;
    private TextView status;
    private TextView report;
    private int ordinal;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        android.widget.LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "Connectivity Field"));
        content.addView(Ui.text(this,
                "Transport changes, Android's downstream estimate, and an optional one-shot download rate. Offline workflows remain available on every network.",
                15, Ui.MUTED));
        status = Ui.text(this, "Network observation is idle. No callback or download is active.", 16, Ui.YELLOW);
        status.setId(R.id.network_status);
        content.addView(status);
        Button watch = Ui.button(this, "Watch network changes", view -> watch());
        watch.setId(R.id.network_watch);
        Button download = Ui.button(this, "Measure 1 MiB once", view -> download());
        download.setId(R.id.network_download);
        content.addView(Ui.buttonRow(this, watch, download));
        content.addView(Ui.button(this, "Stop observation", view -> stopConnectivity()));
        report = Ui.text(this,
                "No network observation yet. Transport, validation, and rate are different measurements. Carrier band and emergency priority are not inferred.",
                17, Ui.TEXT);
        report.setId(R.id.network_report);
        report.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        content.addView(report);
        content.addView(Ui.text(this,
                "Low-bandwidth path: use offline OCR and labels, defer optional model downloads, and run the laptop bridge at 320×240 / 2 fps. Band 14, FirstNet, WPS, carrier priority, and emergency coverage are not controlled or guaranteed by this app.",
                13, Ui.MUTED));
        manager = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
    }

    private void watch() {
        if (callback != null) {
            stopConnectivity();
            return;
        }
        callback = new ConnectivityManager.NetworkCallback() {
            @Override
            public void onCapabilitiesChanged(Network network, NetworkCapabilities capabilities) {
                String transport = capabilities.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) ? "Wi-Fi"
                        : capabilities.hasTransport(NetworkCapabilities.TRANSPORT_CELLULAR) ? "cellular"
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
            try {
                connection = (HttpURLConnection) new URL("https://speed.hetzner.de/1MB.bin").openConnection();
                connection.setConnectTimeout(8000);
                connection.setReadTimeout(120_000);
                connection.setRequestProperty("User-Agent", "Zoe-Mobile/0.1");
                connection.connect();
                if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) {
                    throw new IOException("HTTP " + connection.getResponseCode());
                }
                try (InputStream input = connection.getInputStream()) {
                    byte[] buffer = new byte[16_384];
                    int count;
                    while (total < 1024 * 1024 && (count = input.read(buffer)) >= 0) {
                        total += count;
                    }
                }
                long elapsed = System.nanoTime() - started;
                double rate = NetworkSpeedTest.megabitsPerSecond(total, elapsed);
                long bytes = total;
                runOnUiThread(() -> {
                    report.setText(String.format(Locale.US,
                            "Downloaded %d bytes in %.3f s\nMeasured rate: %.3f Mbit/s\n\nOne third-party HTTPS endpoint is not a measure of every carrier, region, emergency service, or future connection.",
                            bytes, elapsed / 1e9, rate));
                    status.setText("Download measurement complete. No download is active.");
                });
            } catch (Exception error) {
                runOnUiThread(() -> status.setText("Download failed or was cancelled: " + error.getMessage()
                        + ". Offline workflows remain available."));
            } finally {
                downloading.set(false);
                if (connection != null) {
                    connection.disconnect();
                    connection = null;
                }
            }
        });
    }

    private void record(String event) {
        runOnUiThread(() -> {
            events.add((++ordinal) + " · " + event);
            if (events.size() > 12) {
                events.remove(0);
            }
            report.setText(String.join("\n", events));
            status.setText(event);
        });
    }

    private void stopConnectivity() {
        if (callback != null) {
            manager.unregisterNetworkCallback(callback);
            callback = null;
        }
        downloading.set(false);
        if (connection != null) {
            connection.disconnect();
            connection = null;
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
