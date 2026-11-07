package research.zoetic.zoe;

import android.Manifest;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.location.Location;
import android.location.LocationManager;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.Button;
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
    android.os.CancellationSignal pendingLocation;
    private final android.os.Handler handler = new android.os.Handler(android.os.Looper.getMainLooper());
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
        android.widget.LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "Location Field"));
        content.addView(Ui.text(this,
                "One-shot location with accuracy and timestamp. Mark two points for a straight-line distance. No background tracking or address lookup.",
                15, Ui.MUTED));
        status = Ui.text(this, "Location is idle. No location request is active.", 16, Ui.YELLOW);
        status.setId(R.id.location_status);
        content.addView(status);
        Button locate = Ui.button(this, "Locate once", view -> locateOnce());
        locate.setId(R.id.location_once);
        Button settings = Ui.button(this, "Location settings", view ->
                startActivity(new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)));
        content.addView(Ui.buttonRow(this, locate, settings));
        content.addView(Ui.button(this, "Mark first point", view -> {
            if (latest == null) {
                status.setText("Locate once before marking a point.");
            } else {
                first = latest;
                status.setText("First point marked in memory. Move, then locate again.");
            }
        }));
        content.addView(Ui.button(this, "Stop and clear points", view -> stopLocation()));
        report = Ui.text(this,
                "No location observation yet. Coordinates, accuracy, and point-to-point distance appear only after you request them.",
                17, Ui.TEXT);
        report.setId(R.id.location_report);
        report.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        content.addView(report);
        content.addView(Ui.text(this,
                "Straight-line distance ignores terrain, roads, elevation, and obstacles. Location accuracy and provider timestamps remain visible.",
                13, Ui.MUTED));
        manager = (LocationManager) getSystemService(LOCATION_SERVICE);
    }

    private void locateOnce() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION},
                    LOCATION_PERMISSION);
            return;
        }
        cancelPendingLocation();
        try {
            String provider = manager.isProviderEnabled(LocationManager.GPS_PROVIDER)
                    ? LocationManager.GPS_PROVIDER
                    : manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
                    ? LocationManager.NETWORK_PROVIDER : null;
            if (provider == null) {
                status.setText("No location provider is enabled. No location request is active.");
                return;
            }
            status.setText("Requesting one location from " + provider + "…");
            if (Build.VERSION.SDK_INT >= 30) {
                android.os.CancellationSignal request = new android.os.CancellationSignal();
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
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                locateOnce();
            } else {
                status.setText("Location permission was not granted. No location was read.");
            }
        }
    }

    @Override
    protected void onPause() {
        cancelPendingLocation();
        status.setText("Location paused. No location request is active.");
        super.onPause();
    }
}
