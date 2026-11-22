package research.zoetic.zoe;

import android.Manifest;
import android.content.ActivityNotFoundException;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.location.Address;
import android.location.Geocoder;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.CancellationSignal;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.List;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * Zoe Maps & Safety Zapp (v0.3.0-beta):
 *   - Uses built-in OS telemetry (Android LocationManager FUSED/GPS, SensorManager compass,
 *     and platform Geocoder) — starts strictly idle with zero hidden background tracking.
 *   - One-tap handoffs to Google Maps (navigate, search, pin, directions) and universal
 *     Google/Apple Maps share links.
 *   - Direct bridge to Android's built-in Personal Safety app (Pixel safetyhub / Android
 *     Emergency Info), SafeConvert, hardware Flashlight, and Emergency Dialer (never auto-dials).
 */
public final class LocationActivity extends ComponentActivity implements SensorEventListener {
    private static final int LOCATION_PERMISSION = 111;
    private static final int LOCATION_PERMISSION_LIVE = 112;

    private LocationManager manager;
    private SensorManager sensorManager;
    private Sensor rotationSensor;
    private final ExecutorService geocoderPool = Executors.newSingleThreadExecutor();

    private TextView status;
    private TextView report;
    private Button liveToggle;
    private EditText mapsQuery;
    private Button torchButton;

    private Location first;
    private Location latest;
    private String latestAddress = "";
    private Double compassDegrees;
    private long lastGeocodeMs;
    private boolean liveActive;
    private boolean torchOn;

    CancellationSignal pendingLocation;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable locationTimeout = () -> {
        if (pendingLocation != null) {
            pendingLocation.cancel();
            pendingLocation = null;
            status.setText("No location arrived within 15 seconds. No location request is active.");
        }
    };

    private final LocationListener liveListener = new LocationListener() {
        @Override
        public void onLocationChanged(Location location) {
            if (liveActive) {
                publishLocation(location);
            }
        }

        @Override
        public void onProviderDisabled(String provider) {
            if (liveActive) {
                status.setText("Location provider disabled (" + provider + ").");
            }
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

        content.addView(Ui.topBar(this, "Maps & Safety", "Live OS GPS · Google Maps · Personal Safety"));
        content.addView(Ui.text(this,
                "Uses your phone's built-in GPS, compass, Google Maps, and Personal Safety app. Starts strictly idle — stops automatically whenever you leave.",
                14f, Ui.MUTED));

        status = Ui.text(this, "Location is idle. No location request is active.", 15, Ui.YELLOW);
        status.setId(R.id.location_status);
        content.addView(status);

        // 1. On-Device GPS & Live Telemetry Controls
        Button locate = Ui.primaryButton(this, "Locate once", Ui.CYAN, view -> locateOnce());
        locate.setId(R.id.location_once);
        liveToggle = Ui.button(this, "Live location: off", Ui.GREEN, view -> toggleLiveLocation());
        liveToggle.setId(R.id.location_live_toggle);
        content.addView(Ui.buttonRow(this, locate, liveToggle));

        Button markFirst = Ui.button(this, "Mark first point", Ui.GREEN, view -> {
            if (latest == null) {
                status.setText("Locate once before marking a point.");
            } else {
                first = latest;
                status.setText("First point marked in memory. Move, then locate again.");
                refreshReportText();
            }
        });
        Button stopBtn = Ui.button(this, "Stop and clear points", Ui.RUBY, view -> stopLocation());
        content.addView(Ui.buttonRow(this, markFirst, stopBtn));

        report = Ui.text(this,
                "No location observation yet. Coordinates, compass bearing, speed, street address, and point-to-point distance appear only after you request them.",
                15f, Ui.TEXT);
        report.setId(R.id.location_report);
        report.setBackground(Ui.cardBackground(this, 22));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        LinearLayout.LayoutParams repLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        repLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 10));
        content.addView(report, repLp);

        // 2. Google Maps Integration Card
        LinearLayout mapsCard = Ui.vertical(this);
        mapsCard.setBackground(Ui.cardBackground(this, 24));
        mapsCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        mapsCard.addView(Ui.text(this, "GOOGLE MAPS HANDOFF", 12.5f, Ui.COBALT));

        mapsQuery = Ui.input(this, "", "Destination or place (e.g. hospital nearby)…");
        mapsQuery.setId(R.id.maps_query_input);
        mapsCard.addView(mapsQuery);

        Button navBtn = Ui.primaryButton(this, "Navigate (Maps)", Ui.COBALT, view -> launchNavigation());
        navBtn.setId(R.id.maps_navigate_btn);
        Button searchBtn = Ui.button(this, "Search Maps", Ui.CYAN, view -> launchMapSearch());
        searchBtn.setId(R.id.maps_search_btn);
        mapsCard.addView(Ui.buttonRow(this, navBtn, searchBtn));

        Button openPinBtn = Ui.button(this, "Open Pin / Route", Ui.GREEN, view -> openPinOrDirections());
        openPinBtn.setId(R.id.maps_open_pin_btn);
        Button sharePinBtn = Ui.button(this, "Share Live Pin", Ui.GOLD, view -> shareLivePin());
        sharePinBtn.setId(R.id.maps_share_pin_btn);
        mapsCard.addView(Ui.buttonRow(this, openPinBtn, sharePinBtn));

        LinearLayout.LayoutParams mapsLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        mapsLp.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 12));
        content.addView(mapsCard, mapsLp);

        // 3. Built-In Phone Safety & Hardware Tools Card
        LinearLayout safetyCard = Ui.vertical(this);
        safetyCard.setBackground(Ui.cardBackground(this, 24));
        safetyCard.setPadding(Ui.dp(this, 16), Ui.dp(this, 14), Ui.dp(this, 16), Ui.dp(this, 14));
        safetyCard.addView(Ui.text(this, "BUILT-IN PHONE SAFETY & TOOLS", 12.5f, Ui.RUBY));

        Button personalSafetyBtn = Ui.primaryButton(this, "Personal Safety app", Ui.RUBY, view -> openPersonalSafety());
        personalSafetyBtn.setId(R.id.safety_open_app_btn);
        Button safeConvertBtn = Ui.button(this, "SafeConvert", Ui.PINK, view ->
                startActivity(new Intent(this, SafeConvertActivity.class)));
        safetyCard.addView(Ui.buttonRow(this, personalSafetyBtn, safeConvertBtn));

        torchButton = Ui.button(this, "Flashlight: off", Ui.GOLD, view -> toggleFlashlight());
        torchButton.setId(R.id.safety_torch_btn);
        Button dialerBtn = Ui.button(this, "Emergency dialer", Ui.RUBY, view -> openEmergencyDialer());
        safetyCard.addView(Ui.buttonRow(this, torchButton, dialerBtn));

        Button settings = Ui.button(this, "Location settings", Ui.MUTED, view ->
                startActivity(new Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)));
        safetyCard.addView(settings);

        content.addView(safetyCard);

        content.addView(Ui.text(this,
                "Straight-line distance ignores terrain, roads, elevation, and obstacles. Live GPS and compass stop automatically whenever you leave this screen. Nothing shares your location or dials without your explicit tap.",
                12.5f, Ui.MUTED));

        manager = (LocationManager) getSystemService(LOCATION_SERVICE);
        sensorManager = (SensorManager) getSystemService(SENSOR_SERVICE);
        if (sensorManager != null) {
            rotationSensor = sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR);
        }
    }

    private boolean hasLocationPermission() {
        return ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED
                || ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
    }

    private String pickProvider() {
        if (manager == null) {
            return null;
        }
        if (Build.VERSION.SDK_INT >= 31 && manager.isProviderEnabled(LocationManager.FUSED_PROVIDER)) {
            return LocationManager.FUSED_PROVIDER;
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED
                && manager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
            return LocationManager.GPS_PROVIDER;
        }
        if (manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
            return LocationManager.NETWORK_PROVIDER;
        }
        return null;
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
        stopLiveUpdatesOnly();
        cancelPendingLocation();
        try {
            String provider = pickProvider();
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
        } catch (SecurityException error) {
            cancelPendingLocation();
            status.setText("Location permission denied: " + error.getMessage());
        } catch (RuntimeException error) {
            cancelPendingLocation();
            status.setText("Location provider access failed: " + error.getMessage());
        }
    }

    private void toggleLiveLocation() {
        if (liveActive) {
            stopLiveUpdatesOnly();
            status.setText("Live location paused. No tracking is active.");
            return;
        }
        if (!hasLocationPermission()) {
            ActivityCompat.requestPermissions(this,
                    new String[]{Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION},
                    LOCATION_PERMISSION_LIVE);
            return;
        }
        if (manager == null) {
            status.setText("Location service is unavailable on this device.");
            return;
        }
        cancelPendingLocation();
        String provider = pickProvider();
        if (provider == null) {
            status.setText("No location provider is enabled. Enable GPS in Location settings.");
            return;
        }
        try {
            liveActive = true;
            liveToggle.setText("Live location: on");
            manager.requestLocationUpdates(provider, 3_000L, 2.0f, liveListener, Looper.getMainLooper());
            if (sensorManager != null && rotationSensor != null) {
                sensorManager.registerListener(this, rotationSensor, SensorManager.SENSOR_DELAY_UI);
            }
            status.setText("Live OS telemetry active (" + provider + " · stops automatically when you leave).");
            Location cached = manager.getLastKnownLocation(provider);
            if (cached != null) {
                publishLocation(cached);
            }
        } catch (SecurityException error) {
            stopLiveUpdatesOnly();
            status.setText("Location permission denied: " + error.getMessage());
        } catch (RuntimeException error) {
            stopLiveUpdatesOnly();
            status.setText("Could not start live location: " + error.getMessage());
        }
    }

    private void stopLiveUpdatesOnly() {
        if (liveActive) {
            liveActive = false;
            if (liveToggle != null) {
                liveToggle.setText("Live location: off");
            }
        }
        if (manager != null) {
            try {
                manager.removeUpdates(liveListener);
            } catch (RuntimeException ignored) {
            }
        }
        if (sensorManager != null) {
            sensorManager.unregisterListener(this);
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
        stopLiveUpdatesOnly();
        cancelPendingLocation();
        first = null;
        latest = null;
        latestAddress = "";
        compassDegrees = null;
        report.setText("No location observation yet. Coordinates, compass bearing, speed, street address, and point-to-point distance appear only after you request them.");
        status.setText("Location stopped. No points are retained and no location request is active.");
    }

    private void publishLocation(Location current) {
        if (current == null) {
            status.setText("No current or cached location is available. Enable a provider and try again.");
            return;
        }
        latest = current;
        if (liveActive) {
            status.setText("Live OS telemetry active (" + current.getProvider() + " · stops on exit).");
        } else if (first != null && first != current) {
            status.setText("Location and point-to-point distance updated. No tracking is active.");
        } else {
            status.setText("Location updated once. No tracking is active.");
        }
        refreshReportText();
        resolveAddressAsync(current);
    }

    private void refreshReportText() {
        if (latest == null) {
            return;
        }
        long ageSeconds = Math.max(0, (System.currentTimeMillis() - latest.getTime()) / 1000);
        StringBuilder text = new StringBuilder();
        if (latestAddress != null && !latestAddress.isEmpty()) {
            text.append("Address (OS Geocoder): ").append(latestAddress).append('\n');
        }
        text.append(String.format(Locale.US,
                "Latitude: %.6f\nLongitude: %.6f\nAccuracy: +/- %.1f m\nProvider: %s · Age: %d s\n",
                latest.getLatitude(), latest.getLongitude(), latest.getAccuracy(),
                latest.getProvider(), ageSeconds));
        if (latest.hasAltitude()) {
            text.append(String.format(Locale.US, "Altitude: %.1f m\n", latest.getAltitude()));
        }
        if (latest.hasSpeed()) {
            float kmh = latest.getSpeed() * 3.6f;
            float mph = latest.getSpeed() * 2.23694f;
            text.append(String.format(Locale.US, "Speed: %.1f km/h (%.1f mph)\n", kmh, mph));
        }
        if (compassDegrees != null) {
            text.append(String.format(Locale.US, "Compass: %.0f° (%s)\n",
                    compassDegrees, OsToolsBridge.compassCardinal(compassDegrees)));
        }
        if (first != null && first != latest) {
            double distance = LocationMath.haversineMeters(first.getLatitude(), first.getLongitude(),
                    latest.getLatitude(), latest.getLongitude());
            text.append(String.format(Locale.US,
                    "\nStraight-line distance from first point: %.2f m\nThis is not a route, safe path, or obstacle-aware measurement.",
                    distance));
        }
        report.setText(text.toString().trim());
    }

    private void resolveAddressAsync(Location loc) {
        long now = System.currentTimeMillis();
        if (now - lastGeocodeMs < 8_000L || !Geocoder.isPresent()) {
            return;
        }
        lastGeocodeMs = now;
        final double lat = loc.getLatitude();
        final double lon = loc.getLongitude();
        geocoderPool.execute(() -> {
            try {
                Geocoder geocoder = new Geocoder(this, Locale.getDefault());
                @SuppressWarnings("deprecation")
                List<Address> results = geocoder.getFromLocation(lat, lon, 1);
                if (results != null && !results.isEmpty()) {
                    String line = results.get(0).getAddressLine(0);
                    if (line != null && !line.trim().isEmpty()) {
                        runOnUiThread(() -> {
                            if (!isFinishing() && !isDestroyed() && latest != null) {
                                latestAddress = line.trim();
                                refreshReportText();
                            }
                        });
                    }
                }
            } catch (Exception ignored) {
                // Offline or geocoder unavailable — never fabricate an address.
            }
        });
    }

    private void launchNavigation() {
        String dest = mapsQuery.getText() == null ? "" : mapsQuery.getText().toString().trim();
        if (dest.isEmpty()) {
            status.setText("Enter a destination or place above, then tap Navigate (Maps).");
            return;
        }
        Intent nav = new Intent(Intent.ACTION_VIEW, Uri.parse(OsToolsBridge.androidNavigationUri(dest)));
        nav.setPackage(OsToolsBridge.GOOGLE_MAPS_PACKAGE);
        try {
            startActivity(nav);
            status.setText("Handed off navigation to Google Maps.");
        } catch (ActivityNotFoundException fallback) {
            openUriWithFallback(OsToolsBridge.googleMapsSearchUrl(dest), "Opened directions in browser/maps.");
        }
    }

    private void launchMapSearch() {
        String query = mapsQuery.getText() == null ? "" : mapsQuery.getText().toString().trim();
        boolean hasFix = latest != null;
        String uri = OsToolsBridge.androidGeoSearchUri(
                query,
                hasFix ? latest.getLatitude() : 0.0,
                hasFix ? latest.getLongitude() : 0.0,
                hasFix);
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(uri));
        try {
            startActivity(intent);
            status.setText("Opened Maps search.");
        } catch (ActivityNotFoundException fallback) {
            openUriWithFallback(OsToolsBridge.googleMapsSearchUrl(query), "Opened Google Maps in browser.");
        }
    }

    private void openPinOrDirections() {
        if (latest == null) {
            status.setText("Tap Locate once or Live location: on first so Zoe has a pin to open.");
            return;
        }
        if (first != null && first != latest) {
            String dirUrl = OsToolsBridge.googleMapsDirectionsUrl(
                    first.getLatitude(), first.getLongitude(),
                    latest.getLatitude(), latest.getLongitude());
            openUriWithFallback(dirUrl, "Opened Point 1 -> current pin route in Google Maps.");
            return;
        }
        String label = latestAddress.isEmpty() ? "Zoe Pin" : latestAddress;
        Intent pin = new Intent(Intent.ACTION_VIEW,
                Uri.parse(OsToolsBridge.androidGeoPinUri(latest.getLatitude(), latest.getLongitude(), label)));
        try {
            startActivity(pin);
            status.setText("Opened current GPS pin in Maps.");
        } catch (ActivityNotFoundException fallback) {
            openUriWithFallback(OsToolsBridge.googleMapsPinUrl(latest.getLatitude(), latest.getLongitude()),
                    "Opened current GPS pin in browser.");
        }
    }

    private void shareLivePin() {
        if (latest == null) {
            status.setText("Tap Locate once first before sharing your GPS pin.");
            return;
        }
        String msg = OsToolsBridge.formatShareLocationMessage(
                latest.getLatitude(), latest.getLongitude(), latest.getAccuracy(), latestAddress);
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "My location pin (Zoe)")
                .putExtra(Intent.EXTRA_TEXT, msg);
        startActivity(Intent.createChooser(share, "Share live location pin"));
        status.setText("Opened Android share sheet for your GPS pin.");
    }

    private void openPersonalSafety() {
        PackageManager pm = getPackageManager();
        Intent safetyHub = pm.getLaunchIntentForPackage(OsToolsBridge.PIXEL_SAFETY_PACKAGE);
        if (safetyHub != null) {
            startActivity(safetyHub);
            status.setText("Opened built-in Personal Safety app.");
            return;
        }
        Intent emergencyApp = pm.getLaunchIntentForPackage(OsToolsBridge.ANDROID_EMERGENCY_PACKAGE);
        if (emergencyApp != null) {
            startActivity(emergencyApp);
            status.setText("Opened Android Emergency Info.");
            return;
        }
        try {
            startActivity(new Intent("android.content.action.SAFETY_CENTER"));
            status.setText("Opened Android Safety Center.");
        } catch (ActivityNotFoundException fallback) {
            startActivity(new Intent(Settings.ACTION_SETTINGS));
            status.setText("Opened Device Settings -> Safety & Emergency.");
        }
    }

    private void openEmergencyDialer() {
        Intent dial = new Intent(Intent.ACTION_DIAL, Uri.parse("tel:911"));
        try {
            startActivity(dial);
            status.setText("Opened phone dialer (nothing dials until you press Call).");
        } catch (ActivityNotFoundException error) {
            status.setText("Phone dialer is unavailable on this device.");
        }
    }

    private void toggleFlashlight() {
        setFlashlight(!torchOn);
    }

    private void setFlashlight(boolean enable) {
        CameraManager cm = (CameraManager) getSystemService(Context.CAMERA_SERVICE);
        if (cm == null) {
            status.setText("Camera flashlight service is unavailable on this device.");
            return;
        }
        try {
            String targetId = null;
            for (String id : cm.getCameraIdList()) {
                CameraCharacteristics chars = cm.getCameraCharacteristics(id);
                Boolean hasFlash = chars.get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                Integer facing = chars.get(CameraCharacteristics.LENS_FACING);
                if (Boolean.TRUE.equals(hasFlash)
                        && (facing == null || facing == CameraCharacteristics.LENS_FACING_BACK)) {
                    targetId = id;
                    break;
                }
            }
            if (targetId == null) {
                torchOn = false;
                torchButton.setText("Flashlight: off");
                status.setText("No rear flashlight hardware was found on this device.");
                return;
            }
            cm.setTorchMode(targetId, enable);
            torchOn = enable;
            torchButton.setText(torchOn ? "Flashlight: on" : "Flashlight: off");
            status.setText(torchOn ? "Flashlight turned on." : "Flashlight turned off.");
        } catch (Exception error) {
            torchOn = false;
            torchButton.setText("Flashlight: off");
            status.setText("Flashlight unavailable: " + error.getMessage());
        }
    }

    private void openUriWithFallback(String url, String successMsg) {
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            status.setText(successMsg);
        } catch (ActivityNotFoundException error) {
            status.setText("No maps or browser app is available to open: " + url);
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (!liveActive || event.sensor.getType() != Sensor.TYPE_ROTATION_VECTOR) {
            return;
        }
        float[] rotMatrix = new float[9];
        float[] orientation = new float[3];
        SensorManager.getRotationMatrixFromVector(rotMatrix, event.values);
        SensorManager.getOrientation(rotMatrix, orientation);
        double deg = (Math.toDegrees(orientation[0]) + 360.0) % 360.0;
        if (compassDegrees == null || Math.abs(deg - compassDegrees) >= 3.0) {
            compassDegrees = deg;
            refreshReportText();
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        boolean granted = false;
        for (int r : grantResults) {
            if (r == PackageManager.PERMISSION_GRANTED) {
                granted = true;
                break;
            }
        }
        if (requestCode == LOCATION_PERMISSION) {
            if (granted) {
                locateOnce();
            } else {
                status.setText("Location permission was not granted. No location was read.");
            }
        } else if (requestCode == LOCATION_PERMISSION_LIVE) {
            if (granted) {
                toggleLiveLocation();
            } else {
                status.setText("Location permission was not granted. Live location stays off.");
            }
        }
    }

    @Override
    protected void onPause() {
        boolean wasActive = pendingLocation != null || liveActive;
        stopLiveUpdatesOnly();
        cancelPendingLocation();
        if (wasActive) {
            status.setText("Location paused. No location request is active.");
        }
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        stopLiveUpdatesOnly();
        cancelPendingLocation();
        if (torchOn) {
            setFlashlight(false);
        }
        geocoderPool.shutdownNow();
        super.onDestroy();
    }
}
