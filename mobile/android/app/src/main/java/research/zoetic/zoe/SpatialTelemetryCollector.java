package research.zoetic.zoe;

import android.Manifest;
import android.annotation.SuppressLint;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.content.Context;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.hardware.GeomagneticField;
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
import android.net.ConnectivityManager;
import android.net.Network;
import android.net.NetworkCapabilities;
import android.net.TransportInfo;
import android.net.wifi.WifiInfo;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.telephony.CellSignalStrength;
import android.telephony.SignalStrength;
import android.telephony.TelephonyManager;
import android.util.SizeF;

import androidx.core.content.ContextCompat;

import java.util.List;

/**
 * Privacy-First, Zero-Lag Multi-Sensor Telemetry Collector for Zoe Explore (v0.9.6-beta).
 *
 * Strictly opt-in (starts completely idle) and releases every hardware listener on stop().
 * Reads ONLY non-identifying local physical telemetry:
 *   - Camera2 rear & front lens physical characteristics (focal length, sensor size, FOV) — zero extra streams!
 *   - Geomagnetic rotation compass + Barometer relative altitude + Ambient Light lux
 *   - Opt-in coarse/fine GPS -> local ENU metric grid (only if location permission already granted)
 *   - Wi-Fi link RSSI/frequency via NetworkCapabilities (zero SSID/BSSID/MAC!)
 *   - Cellular radio signal strength dBm/level + SIM ready boolean via TelephonyManager (zero IMSI/ICCID/number!)
 *   - Bluetooth bonded proximity count (only if BLUETOOTH_CONNECT granted; zero MAC addresses!)
 */
final class SpatialTelemetryCollector implements SensorEventListener {
    interface Listener {
        void onFieldUpdated(SpatialTelemetryFusion.FusedFieldSnapshot snapshot);
    }

    private static final long POLL_INTERVAL_MS = 1_500L;

    private final Context appContext;
    private final Listener listener;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private final SensorManager sensorManager;
    private final Sensor compassSensor;
    private final Sensor baroSensor;
    private final Sensor lightSensor;
    private final Sensor stepSensor;

    private SpatialTelemetryFusion.CameraOptics cameraOptics;
    private SpatialTelemetryFusion.LightFieldState lightField = SpatialTelemetryFusion.LightFieldState.neutral();
    private SpatialTelemetryFusion.FusedFieldSnapshot lastSnapshot;
    private LiveViewErgonomics.PdrState pdrState = new LiveViewErgonomics.PdrState(0.0, 0.0, 0);

    private boolean active;
    private float magneticHeadingDeg = Float.NaN;
    private float geomagneticDeclinationDeg;
    private float compassDegrees = Float.NaN;
    private float pitchDegrees = 0f;
    private float baselinePressureHpa = Float.NaN;
    private float baroDeltaMeters;
    private float ambientLux;
    private float imuStability = 0.85f;
    private float acousticEnergy = 0.08f;
    private float acousticEchoMeters = -1f;
    private float rearLuma = 0.45f;
    private float rearWarmth;
    private float frontLuma = 0.45f;
    private float frontWarmth;
    private boolean dualCamCalibrated;
    private volatile String localPlaceLabel = "";
    private long lastGeocodeAttemptMs;

    private Location originLocation;
    private Location latestLocation;
    private LocationManager locationManager;
    private boolean locationUpdatesRegistered;

    private final float[] rotMat = new float[9];
    private final float[] orientAngles = new float[3];

    private final LocationListener locationListener = new LocationListener() {
        @Override
        public void onLocationChanged(Location location) {
            if (!active || location == null) {
                return;
            }
            if (originLocation == null) {
                originLocation = location;
            }
            latestLocation = location;
            updateDeclinationAndPlace(location);
            if (originLocation != null) {
                SpatialTelemetryFusion.EnuGridCoord gpsEnu = SpatialTelemetryFusion.toLocalEnuGrid(
                        originLocation.getLatitude(), originLocation.getLongitude(),
                        originLocation.hasAltitude() ? originLocation.getAltitude() : 0.0,
                        location.getLatitude(), location.getLongitude(),
                        location.hasAltitude() ? location.getAltitude() : 0.0);
                pdrState = LiveViewErgonomics.blendWithGpsEnu(
                        pdrState, gpsEnu.eastMeters, gpsEnu.northMeters,
                        location.hasAccuracy() ? location.getAccuracy() : 20f);
            }
        }
    };

    private final Runnable pollTick = new Runnable() {
        @Override
        public void run() {
            if (!active) {
                return;
            }
            publishFusedSnapshot();
            mainHandler.postDelayed(this, POLL_INTERVAL_MS);
        }
    };

    SpatialTelemetryCollector(Context context, Listener listener) {
        this.appContext = context.getApplicationContext();
        this.listener = listener;
        this.sensorManager = (SensorManager) appContext.getSystemService(Context.SENSOR_SERVICE);
        this.compassSensor = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_ROTATION_VECTOR) : null;
        this.baroSensor = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_PRESSURE) : null;
        this.lightSensor = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_LIGHT) : null;
        this.stepSensor = sensorManager != null ? sensorManager.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR) : null;
        this.locationManager = (LocationManager) appContext.getSystemService(Context.LOCATION_SERVICE);
        this.cameraOptics = readDualCameraOptics(appContext, true);
    }

    float getPitchDegrees() {
        return pitchDegrees;
    }

    int getStepCount() {
        return pdrState.stepCount;
    }

    String getLocalPlaceLabel() {
        return localPlaceLabel;
    }

    LiveViewErgonomics.PdrState getPdrState() {
        return pdrState;
    }

    SpatialTelemetryFusion.CameraOptics getCameraOptics(boolean portrait) {
        cameraOptics = readDualCameraOptics(appContext, portrait);
        return cameraOptics;
    }

    boolean isActive() {
        return active;
    }

    SpatialTelemetryFusion.FusedFieldSnapshot getLastSnapshot() {
        return lastSnapshot;
    }

    Location getLatestLocation() {
        return latestLocation;
    }

    float getCompassDegrees() {
        return compassDegrees;
    }

    void start() {
        if (active) {
            return;
        }
        active = true;
        baselinePressureHpa = Float.NaN;
        baroDeltaMeters = 0f;
        if (sensorManager != null) {
            if (compassSensor != null) {
                sensorManager.registerListener(this, compassSensor, SensorManager.SENSOR_DELAY_UI);
            }
            if (baroSensor != null) {
                sensorManager.registerListener(this, baroSensor, SensorManager.SENSOR_DELAY_NORMAL);
            }
            if (lightSensor != null) {
                sensorManager.registerListener(this, lightSensor, SensorManager.SENSOR_DELAY_NORMAL);
            }
            if (stepSensor != null) {
                // Hardware Sensor Hub step detector (zero CPU wake!) for indoor/outdoor Pedestrian Dead-Reckoning
                try {
                    sensorManager.registerListener(this, stepSensor, SensorManager.SENSOR_DELAY_NORMAL);
                } catch (RuntimeException ignored) {
                }
            }
        }
        attachLocationIfPermitted();
        mainHandler.removeCallbacks(pollTick);
        mainHandler.post(pollTick);
    }

    void stop() {
        active = false;
        mainHandler.removeCallbacks(pollTick);
        if (sensorManager != null) {
            sensorManager.unregisterListener(this);
        }
        if (locationUpdatesRegistered && locationManager != null) {
            try {
                locationManager.removeUpdates(locationListener);
            } catch (Exception ignored) {
            }
            locationUpdatesRegistered = false;
        }
    }

    void updateImuStability(float stability) {
        this.imuStability = Math.max(0f, Math.min(1f, stability));
    }

    void updateAcousticLevel(float normalizedRms) {
        this.acousticEnergy = Math.max(0f, Math.min(1f, normalizedRms));
    }

    void recordAcousticEchoDistance(float meters) {
        if (Float.isFinite(meters) && meters > 0.25f && meters < 6.0f) {
            this.acousticEchoMeters = meters;
            if (active) {
                publishFusedSnapshot();
            }
        }
    }

    void sampleRearBitmap(Bitmap frame) {
        if (frame == null || frame.isRecycled()) {
            return;
        }
        float[] lw = extractBitmapLumaWarmth(frame);
        this.rearLuma = lw[0];
        this.rearWarmth = lw[1];
        rebuildLightField();
    }

    void sampleFrontBitmapForBacklight(Bitmap frame) {
        if (frame == null || frame.isRecycled()) {
            return;
        }
        float[] lw = extractBitmapLumaWarmth(frame);
        this.frontLuma = lw[0];
        this.frontWarmth = lw[1];
        this.dualCamCalibrated = true;
        rebuildLightField();
        if (active) {
            publishFusedSnapshot();
        }
    }

    SpatialTelemetryFusion.LightFieldState getLightField() {
        return lightField;
    }

    private void rebuildLightField() {
        this.lightField = SpatialTelemetryFusion.computeLightField(
                rearLuma, frontLuma, rearWarmth, frontWarmth, dualCamCalibrated);
    }

    private static float[] extractBitmapLumaWarmth(Bitmap bmp) {
        int w = bmp.getWidth();
        int h = bmp.getHeight();
        if (w <= 0 || h <= 0) {
            return new float[]{0.45f, 0f};
        }
        int stepX = Math.max(1, w / 16);
        int stepY = Math.max(1, h / 16);
        int[] samples = new int[16 * 16];
        int idx = 0;
        for (int y = stepY / 2; y < h && idx < samples.length; y += stepY) {
            for (int x = stepX / 2; x < w && idx < samples.length; x += stepX) {
                samples[idx++] = bmp.getPixel(x, y);
            }
        }
        if (idx < samples.length) {
            int[] trimmed = new int[idx];
            System.arraycopy(samples, 0, trimmed, 0, idx);
            samples = trimmed;
        }
        return SpatialTelemetryFusion.sampleLumaAndWarmth(samples);
    }

    @SuppressLint("MissingPermission")
    void attachLocationIfPermitted() {
        if (!active || locationManager == null || locationUpdatesRegistered) {
            return;
        }
        boolean fine = ContextCompat.checkSelfPermission(appContext, Manifest.permission.ACCESS_FINE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
        boolean coarse = ContextCompat.checkSelfPermission(appContext, Manifest.permission.ACCESS_COARSE_LOCATION)
                == PackageManager.PERMISSION_GRANTED;
        if (!fine && !coarse) {
            return;
        }
        try {
            String provider = null;
            if (Build.VERSION.SDK_INT >= 31 && locationManager.isProviderEnabled(LocationManager.FUSED_PROVIDER)) {
                provider = LocationManager.FUSED_PROVIDER;
            } else if (fine && locationManager.isProviderEnabled(LocationManager.GPS_PROVIDER)) {
                provider = LocationManager.GPS_PROVIDER;
            } else if (locationManager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
                provider = LocationManager.NETWORK_PROVIDER;
            }
            if (provider != null) {
                Location cached = locationManager.getLastKnownLocation(provider);
                if (cached != null) {
                    if (originLocation == null) {
                        originLocation = cached;
                    }
                    latestLocation = cached;
                    updateDeclinationAndPlace(cached);
                }
                locationManager.requestLocationUpdates(provider, 5_000L, 1.5f, locationListener, Looper.getMainLooper());
                locationUpdatesRegistered = true;
            }
        } catch (RuntimeException ignored) {
        }
    }

    @Override
    public void onSensorChanged(SensorEvent event) {
        if (!active || event == null || event.values == null) {
            return;
        }
        int type = event.sensor.getType();
        if (type == Sensor.TYPE_ROTATION_VECTOR) {
            SensorManager.getRotationMatrixFromVector(rotMat, event.values);
            SensorManager.getOrientation(rotMat, orientAngles);
            magneticHeadingDeg = (float) SpatialTelemetryFusion.normalizeHeading(Math.toDegrees(orientAngles[0]));
            compassDegrees = LiveViewErgonomics.magneticToTrueNorth(magneticHeadingDeg, geomagneticDeclinationDeg);
            // Pitch in upright handheld coordinates: ~0° level ahead, -90° pointing flat at ground
            float rawPitch = (float) Math.toDegrees(orientAngles[1]);
            pitchDegrees = -rawPitch - 90f;
            if (pitchDegrees < -90f) pitchDegrees = -180f - pitchDegrees;
            if (pitchDegrees > 90f) pitchDegrees = 180f - pitchDegrees;
        } else if (type == Sensor.TYPE_STEP_DETECTOR) {
            pdrState = LiveViewErgonomics.advanceStep(pdrState, compassDegrees, LiveViewErgonomics.DEFAULT_STRIDE_METERS);
        } else if (type == Sensor.TYPE_PRESSURE && event.values.length > 0) {
            float hpa = event.values[0];
            if (Float.isNaN(baselinePressureHpa)) {
                baselinePressureHpa = hpa;
            }
            float curAlt = SensorManager.getAltitude(SensorManager.PRESSURE_STANDARD_ATMOSPHERE, hpa);
            float baseAlt = SensorManager.getAltitude(SensorManager.PRESSURE_STANDARD_ATMOSPHERE, baselinePressureHpa);
            baroDeltaMeters = curAlt - baseAlt;
        } else if (type == Sensor.TYPE_LIGHT && event.values.length > 0) {
            ambientLux = Math.max(0f, event.values[0]);
        }
    }

    @Override
    public void onAccuracyChanged(Sensor sensor, int accuracy) {
    }

    private void publishFusedSnapshot() {
        int[] wifi = readWifiRssiAndFreq();
        int bleCount = readBluetoothBondedCount();
        int[] cell = readCellularSignalNonPii();

        SpatialTelemetryFusion.EnuGridCoord grid = null;
        if (originLocation != null && latestLocation != null) {
            grid = SpatialTelemetryFusion.toLocalEnuGrid(
                    originLocation.getLatitude(), originLocation.getLongitude(),
                    originLocation.hasAltitude() ? originLocation.getAltitude() : 0.0,
                    latestLocation.getLatitude(), latestLocation.getLongitude(),
                    latestLocation.hasAltitude() ? latestLocation.getAltitude() : 0.0);
        } else if (pdrState.stepCount > 0) {
            // Pure indoor Pedestrian Dead-Reckoning ENU grid even with zero GPS fix!
            double d = Math.hypot(pdrState.eastMeters, pdrState.northMeters);
            int cE = (int) Math.floor(pdrState.eastMeters / 5.0);
            int cN = (int) Math.floor(pdrState.northMeters / 5.0);
            String code = String.format(java.util.Locale.US, "PDR[%+dE,%+dN·%dst]", cE, cN, pdrState.stepCount);
            grid = new SpatialTelemetryFusion.EnuGridCoord(pdrState.eastMeters, pdrState.northMeters, baroDeltaMeters, d, code);
        }

        SpatialTelemetryFusion.TelemetryInput input = new SpatialTelemetryFusion.TelemetryInput(
                imuStability,
                acousticEnergy,
                acousticEchoMeters,
                ambientLux,
                baroDeltaMeters,
                compassDegrees,
                wifi[0], wifi[1],
                bleCount > 0 ? -68 : -127, bleCount,
                cell[0], cell[1], cell[2] == 1,
                lightField,
                grid
        );
        lastSnapshot = SpatialTelemetryFusion.fuse(input, lastSnapshot);
        if (listener != null) {
            listener.onFieldUpdated(lastSnapshot);
        }
    }

    /**
     * Uses Android's built-in GeomagneticField (zero network) for exact True-North declination
     * and platform Geocoder (async, throttled) for nearby street/neighborhood context.
     */
    private void updateDeclinationAndPlace(Location loc) {
        if (loc == null) return;
        try {
            GeomagneticField gmf = new GeomagneticField(
                    (float) loc.getLatitude(),
                    (float) loc.getLongitude(),
                    loc.hasAltitude() ? (float) loc.getAltitude() : 0f,
                    System.currentTimeMillis());
            geomagneticDeclinationDeg = gmf.getDeclination();
            if (Float.isFinite(magneticHeadingDeg)) {
                compassDegrees = LiveViewErgonomics.magneticToTrueNorth(magneticHeadingDeg, geomagneticDeclinationDeg);
            }
        } catch (Throwable ignored) {
        }
        long now = System.currentTimeMillis();
        if (now - lastGeocodeAttemptMs < 30_000L || !Geocoder.isPresent()) {
            return;
        }
        lastGeocodeAttemptMs = now;
        final double lat = loc.getLatitude();
        final double lon = loc.getLongitude();
        Thread t = new Thread(() -> {
            try {
                Geocoder geocoder = new Geocoder(appContext, java.util.Locale.getDefault());
                @SuppressWarnings("deprecation")
                List<Address> list = geocoder.getFromLocation(lat, lon, 1);
                if (list != null && !list.isEmpty()) {
                    Address a = list.get(0);
                    String street = a.getThoroughfare();
                    String locality = a.getLocality();
                    if (street != null && !street.isEmpty() && locality != null && !locality.isEmpty()) {
                        localPlaceLabel = street + ", " + locality;
                    } else if (street != null && !street.isEmpty()) {
                        localPlaceLabel = street;
                    } else if (locality != null && !locality.isEmpty()) {
                        localPlaceLabel = locality;
                    }
                }
            } catch (Throwable ignored) {
            }
        }, "zoe-geocoder");
        t.setDaemon(true);
        t.start();
    }

    private int[] readWifiRssiAndFreq() {
        int rssi = -127;
        int freq = 0;
        try {
            ConnectivityManager cm = (ConnectivityManager) appContext.getSystemService(Context.CONNECTIVITY_SERVICE);
            if (cm != null) {
                Network activeNet = cm.getActiveNetwork();
                NetworkCapabilities caps = activeNet != null ? cm.getNetworkCapabilities(activeNet) : null;
                if (caps != null && caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)) {
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                        int sig = caps.getSignalStrength();
                        if (sig != Integer.MIN_VALUE && sig < 0) {
                            rssi = sig;
                        }
                        TransportInfo ti = caps.getTransportInfo();
                        if (ti instanceof WifiInfo wifiInfo) {
                            // Strictly RSSI & frequency band only — NEVER reads SSID or BSSID/MAC!
                            int wr = wifiInfo.getRssi();
                            if (wr > -120 && wr < 0) {
                                rssi = wr;
                            }
                            freq = Math.max(0, wifiInfo.getFrequency());
                        }
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        return new int[]{rssi, freq};
    }

    private int readBluetoothBondedCount() {
        try {
            if (Build.VERSION.SDK_INT >= 31
                    && ContextCompat.checkSelfPermission(appContext, Manifest.permission.BLUETOOTH_CONNECT)
                    != PackageManager.PERMISSION_GRANTED) {
                return 0;
            }
            BluetoothManager bm = (BluetoothManager) appContext.getSystemService(Context.BLUETOOTH_SERVICE);
            BluetoothAdapter adapter = bm != null ? bm.getAdapter() : null;
            if (adapter != null && adapter.isEnabled() && adapter.getBondedDevices() != null) {
                return adapter.getBondedDevices().size();
            }
        } catch (RuntimeException ignored) {
        }
        return 0;
    }

    /**
     * Strictly non-identifying cellular radio link telemetry: [dBm, level 0..4, simReady 0/1].
     * Uses TelephonyManager.getSignalStrength() (API 28+, ZERO dangerous permissions) and getSimState() integer.
     * NEVER accesses IMSI, IMEI, ICCID, subscriber ID, or phone number!
     */
    private int[] readCellularSignalNonPii() {
        int dbm = -140;
        int level = 0;
        int simReady = 0;
        try {
            TelephonyManager tm = (TelephonyManager) appContext.getSystemService(Context.TELEPHONY_SERVICE);
            if (tm != null) {
                simReady = tm.getSimState() == TelephonyManager.SIM_STATE_READY ? 1 : 0;
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    SignalStrength ss = tm.getSignalStrength();
                    if (ss != null) {
                        level = Math.max(0, Math.min(4, ss.getLevel()));
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                            List<CellSignalStrength> strengths = ss.getCellSignalStrengths();
                            if (strengths != null && !strengths.isEmpty()) {
                                int candidate = strengths.get(0).getDbm();
                                if (candidate > -140 && candidate < -30) {
                                    dbm = candidate;
                                }
                            }
                        }
                    }
                }
            }
        } catch (RuntimeException ignored) {
        }
        return new int[]{dbm, level, simReady};
    }

    /**
     * Queries Android Camera2 physical characteristics for BOTH Rear and Front cameras with ZERO camera stream open!
     */
    static SpatialTelemetryFusion.CameraOptics readDualCameraOptics(Context context, boolean portrait) {
        float rearFov = SpatialTelemetryFusion.DEFAULT_FOV_RAD;
        float frontFov = 1.18f;
        float rearFocal = 0f;
        float frontFocal = 0f;
        float rearAp = 0f;
        float frontAp = 0f;
        try {
            CameraManager cm = (CameraManager) context.getSystemService(Context.CAMERA_SERVICE);
            if (cm != null) {
                for (String camId : cm.getCameraIdList()) {
                    CameraCharacteristics cc = cm.getCameraCharacteristics(camId);
                    Integer facing = cc.get(CameraCharacteristics.LENS_FACING);
                    SizeF sensor = cc.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
                    float[] focals = cc.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
                    float[] apertures = cc.get(CameraCharacteristics.LENS_INFO_AVAILABLE_APERTURES);
                    if (facing == null || sensor == null || focals == null || focals.length == 0) {
                        continue;
                    }
                    float fov = SpatialTelemetryFusion.computeVerticalFovRad(
                            sensor.getWidth(), sensor.getHeight(), focals[0], portrait);
                    float ap = (apertures != null && apertures.length > 0) ? apertures[0] : 0f;
                    if (facing == CameraCharacteristics.LENS_FACING_BACK && rearFocal == 0f) {
                        rearFov = fov;
                        rearFocal = focals[0];
                        rearAp = ap;
                    } else if (facing == CameraCharacteristics.LENS_FACING_FRONT && frontFocal == 0f) {
                        frontFov = fov;
                        frontFocal = focals[0];
                        frontAp = ap;
                    }
                }
            }
        } catch (Throwable ignored) {
        }
        return new SpatialTelemetryFusion.CameraOptics(rearFov, frontFov, rearFocal, frontFocal, rearAp, frontAp);
    }
}
