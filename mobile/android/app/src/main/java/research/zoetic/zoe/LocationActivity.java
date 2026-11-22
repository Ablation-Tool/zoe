package research.zoetic.zoe;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.Locale;

public final class LocationActivity extends ComponentActivity {
    private static final int LOCATION_PERMISSION = 111;
    private LocationManager manager;
    private TextView status;
    private TextView report;
    private Location first;
    private Location latest;
    CancellationSignal pendingLocation;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable locationTimeout = () -> {
        if (pendingLocation != null) {
            pendingLocation.cancel();
            pendingLocation = null;
            status.setText("No location arrived within 15 seconds. No location request is active.");
        }
    };

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

        content.addView(Ui.topBar(this, "Location Field", "One-shot position · straight-line distance"));
        content.addView(Ui.text(this,
                "One-shot location with accuracy and timestamp. Mark two points for a straight-line distance. No background tracking or address lookup.",
                14.5f, Ui.MUTED));
        status = Ui.text(this, "Location is idle. No location request is active.", 15, Ui.YELLOW);
        status.setId(R.id.location_status);
        content.addView(status);
        Button locate = Ui.button(this, "Locate once", Ui.CYAN, view -> locateOnce());
        locate.setId(R.id.location_once);
        Button settings = Ui.button(this, "Location settings", Ui.GOLD, view ->
                startActivity(new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)));
        content.addView(Ui.buttonRow(this, locate, settings));
        content.addView(Ui.button(this, "Mark first point", Ui.GREEN, view -> {
            if (latest == null) {
                status.setText("Locate once before marking a point.");
            } else {
                first = latest;
                status.setText("First point marked in memory. Move, then locate again.");
            }
        }));
        content.addView(Ui.button(this, "Stop and clear points", Ui.RUBY, view -> stopLocation()));
        report = Ui.text(this,
                "No location observation yet. Coordinates, accuracy, and point-to-point distance appear only after you request them.",
                16, Ui.TEXT);
        report.setId(R.id.location_report);
        report.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        content.addView(report);
        content.addView(Ui.text(this,
                "Straight-line distance ignores terrain, roads, elevation, and obstacles. Location accuracy and provider timestamps remain visible.",
                12.5f, Ui.MUTED));
        manager = (LocationManager) getSystemService(LOCATION_SERVICE);
    }

    private boolean hasLocationPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    private void locateOnce() {
        if (!hasLocationPermission()) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION},
                    LOCATION_PERMISSION);
            return;
        }
        if (manager == null) {
            status.setText("Location service is unavailable on this device.");
            return;
        }
        cancelPendingLocation();
        try {
            String provider = null;
            if (Build.VERSION.SDK_INT >= 31 && manager.isProviderEnabled(LocationManager.FUSED_PROVIDER)) {
                provider = LocationManager.FUSED_PROVIDER;
            } else if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                    == PackageManager.PERMISSION_GRANTED
                    && manager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                provider = LocationManager.GPS_PROVIDER;
            } else if (manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                provider = LocationManager.NETWORK_PROVIDER;
            }
            if (provider == null) {
                status.setText("No location provider is enabled. No location request is active.");
                return;
            }
            status.setText("Requesting one location from " + provider + "…");
            if (Build.VERSION.SDK_INT >= 30) {
                CancellationSignal request = new CancellationSignal();
                pendingLocation = request;
                handler.postDelayed(locationTimeout, 15_000);
                manager.getCurrentLocation(provider, request, ContextCompat.getMainExecutor(this), current -> {
                    if (pendingLocation != request) {
                        return;
                    }
                    pendingLocation = null;
                    handler.removeCallbacks(locationTimeout);
                    publishLocation(current);
                });
            } else {
                publishLocation(manager.getLastKnownLocation(provider));
            }
        } catch (RuntimeException error) {
            cancelPendingLocation();
            status.setText("Location permission or provider access failed: " + error.getMessage());
        }
    }

    private void cancelPendingLocation() {
        handler.removeCallbacks(locationTimeout);
        if (pendingLocation != null) {
            pendingLocation.cancel();
            pendingLocation = null;
        }
    }

    private void stopLocation() {
        cancelPendingLocation();
        first = null;
        latest = null;
        report.setText("No location observation yet. Coordinates, accuracy, and point-to-point distance appear only after you request them.");
        status.setText("Location stopped. No points are retained and no location request is active.");
    }

    private void publishLocation(Location current) {
        if (current == null) {
            status.setText("No current or cached location is available. Enable a provider and try again.");
            return;
        }
        latest = current;
        long ageSeconds = Math.max(0, (System.currentTimeMillis() - current.getTime()) / 1000);
        StringBuilder text = new StringBuilder(String.format(Locale.US,
                "Latitude: %.6f\nLongitude: %.6f\nAccuracy: %.1f m\nProvider: %s\nReading age: %d s\n",
                current.getLatitude(), current.getLongitude(), current.getAccuracy(), current.getProvider(), ageSeconds));
        if (first != null && first != current) {
            double distance = LocationMath.haversineMeters(first.getLatitude(), first.getLongitude(),
                    current.getLatitude(), current.getLongitude());
            text.append(String.format(Locale.US,
                    "\nStraight-line distance from first point: %.2f m\nThis is not a route, safe path, or obstacle-aware measurement.", distance));
            status.setText("Location and point-to-point distance updated. No tracking is active.");
        } else {
            status.setText("Location updated once. No tracking is active.");
        }
        report.setText(text.toString());
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == LOCATION_PERMISSION) {
            boolean granted = false;
            for (int r : grantResults) {
                if (r == PackageManager.PERMISSION_GRANTED) {
                    granted = true;
                    break;
                }
            }
            if (granted) {
                locateOnce();
            } else {
                status.setText("Location permission was not granted. No location was read.");
            }
        }
    }

    @Override
    protected void onPause() {
        boolean wasActive = pendingLocation != null;
        cancelPendingLocation();
        if (wasActive) {
            status.setText("Location paused. No location request is active.");
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        cancelPendingLocation();
        super.onDestroy();
    }
}
