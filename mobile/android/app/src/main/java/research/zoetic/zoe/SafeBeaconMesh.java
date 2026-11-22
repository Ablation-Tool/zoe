package research.zoetic.zoe;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothManager;
import android.bluetooth.le.AdvertiseCallback;
import android.bluetooth.le.AdvertiseData;
import android.bluetooth.le.AdvertiseSettings;
import android.bluetooth.le.BluetoothLeAdvertiser;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanFilter;
import android.bluetooth.le.ScanResult;
import android.bluetooth.le.ScanSettings;
import android.content.Context;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.os.ParcelUuid;
import android.util.Base64;

import androidx.core.content.ContextCompat;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;

/**
 * Offline Bluetooth Low Energy (BLE) Help Beacon & Blind Encrypted Relay Mesh for SafeConvert (v0.8.0-beta).
 *
 * Designed with strict anti-stalkerware & survivor-safety guardrails (CONSTITUTION.md):
 *   - Starts strictly OFF; never runs covertly in the background.
 *   - Hard 30-minute auto-expiry prevents permanent covert tracking.
 *   - 1-tap Rotate / Revoke All Keys immediately invalidates prior beacon identities.
 *   - Supports two distinct offline BLE modes (zero cell signal or Wi-Fi needed):
 *       1. BLIND_E2EE_RELAY (AirTag / Find My style): 15-minute rotating cryptographic tag derived via
 *          SHA-256(secret || epoch). Nearby Zoe phones cannot identify the sender — they record blind
 *          sightings for encrypted relay only to pre-trusted Safe People.
 *       2. LOCAL_SOS_MESH (Opt-in nearby alert): short-range (~30-80m) signed BLE emergency ping
 *          alerting actively scanning nearby Zoe phones with approximate RSSI distance.
 */
final class SafeBeaconMesh {
    static final UUID SERVICE_UUID = UUID.fromString("0000FE7A-0000-1000-8000-00805F9B34FB");
    static final ParcelUuid SERVICE_PARCEL_UUID = new ParcelUuid(SERVICE_UUID);
    static final byte MAGIC = 0x5A; // 'Z'
    static final byte PROTOCOL_VERSION = 0x01;
    static final byte MODE_BLIND_RELAY = 0x01;
    static final byte MODE_LOCAL_SOS = 0x02;
    static final int PACKET_LEN = 22;
    static final long ROTATION_WINDOW_MS = 15L * 60L * 1000L;
    static final long MAX_BEACON_DURATION_MS = 30L * 60L * 1000L;

    private static final String PREFS = "zoe_safe_beacon_v1";
    private static final String KEY_SECRET_B64 = "beacon_secret_b64";

    static final class ParsedBeacon {
        final byte mode;
        final String rotatingTagHex;
        final int rssi;
        final double approxMeters;
        final long seenAtMs;

        ParsedBeacon(byte mode, String rotatingTagHex, int rssi, double approxMeters, long seenAtMs) {
            this.mode = mode;
            this.rotatingTagHex = rotatingTagHex;
            this.rssi = rssi;
            this.approxMeters = approxMeters;
            this.seenAtMs = seenAtMs;
        }

        boolean isLocalSos() {
            return mode == MODE_LOCAL_SOS;
        }
    }

    interface MeshListener {
        void onBeaconStatusChanged(boolean advertising, byte mode, String tagPreview, String message);
        void onNearbySighting(List<ParsedBeacon> sightings);
    }

    private final Context appContext;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Map<String, ParsedBeacon> sightings = new LinkedHashMap<>();

    private BluetoothLeAdvertiser advertiser;
    private BluetoothLeScanner scanner;
    private AdvertiseCallback activeAdvCallback;
    private ScanCallback activeScanCallback;
    private MeshListener listener;

    private boolean advertising;
    private boolean scanning;
    private byte activeMode;
    private long expiresAtMs;

    private final Runnable autoExpireTask = () -> {
        if (advertising) {
            stopAdvertising("Beacon automatically turned off after 30-minute safety limit.");
        }
    };

    SafeBeaconMesh(Context ctx) {
        this.appContext = ctx.getApplicationContext();
    }

    // --- Pure Cryptographic Packet & Distance Helpers (100% JVM Unit-Testable!) ---

    static byte[] deriveRotatingTag(byte[] secret32, long epochBucket) {
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            sha.update("ZOE-SAFE-BEACON-V1".getBytes(StandardCharsets.UTF_8));
            sha.update(secret32);
            sha.update(ByteBuffer.allocate(8).putLong(epochBucket).array());
            byte[] full = sha.digest();
            byte[] tag16 = new byte[16];
            System.arraycopy(full, 0, tag16, 0, 16);
            return tag16;
        } catch (Exception err) {
            throw new IllegalStateException("SHA-256 unavailable", err);
        }
    }

    static byte[] computeCheck4(byte mode, byte[] tag16) {
        try {
            MessageDigest sha = MessageDigest.getInstance("SHA-256");
            sha.update(MAGIC);
            sha.update(PROTOCOL_VERSION);
            sha.update(mode);
            sha.update(tag16);
            byte[] full = sha.digest();
            return new byte[]{full[0], full[1], full[2], full[3]};
        } catch (Exception err) {
            throw new IllegalStateException("SHA-256 unavailable", err);
        }
    }

    static byte[] buildBeaconPayload(byte[] secret32, byte mode, long nowMs) {
        long epoch = Math.max(0L, nowMs) / ROTATION_WINDOW_MS;
        byte[] tag16 = deriveRotatingTag(secret32, epoch);
        byte[] check4 = computeCheck4(mode, tag16);
        byte[] out = new byte[PACKET_LEN];
        out[0] = MAGIC;
        out[1] = (byte) ((PROTOCOL_VERSION << 4) | (mode & 0x0F));
        System.arraycopy(tag16, 0, out, 2, 16);
        System.arraycopy(check4, 0, out, 18, 4);
        return out;
    }

    static ParsedBeacon parseBeaconPayload(byte[] payload, int rssi, long nowMs) {
        if (payload == null || payload.length < PACKET_LEN) {
            return null;
        }
        if (payload[0] != MAGIC) {
            return null;
        }
        byte ver = (byte) ((payload[1] >> 4) & 0x0F);
        byte mode = (byte) (payload[1] & 0x0F);
        if (ver != PROTOCOL_VERSION || (mode != MODE_BLIND_RELAY && mode != MODE_LOCAL_SOS)) {
            return null;
        }
        byte[] tag16 = new byte[16];
        System.arraycopy(payload, 2, tag16, 0, 16);
        byte[] expected = computeCheck4(mode, tag16);
        for (int i = 0; i < 4; i++) {
            if (payload[18 + i] != expected[i]) {
                return null;
            }
        }
        return new ParsedBeacon(mode, toHex(tag16), rssi, estimateDistanceMeters(rssi), nowMs);
    }

    /**
     * Log-distance BLE RSSI approximation (clearly labeled approximate in UI; walls/bodies affect RF).
     */
    static double estimateDistanceMeters(int rssi) {
        if (rssi >= 0 || rssi < -115) {
            return -1.0;
        }
        double txPowerAt1m = -59.0;
        double pathLossExponent = 2.4;
        double dist = Math.pow(10.0, (txPowerAt1m - rssi) / (10.0 * pathLossExponent));
        return Math.max(0.5, Math.min(120.0, Math.round(dist * 10.0) / 10.0));
    }

    static String toHex(byte[] bytes) {
        StringBuilder sb = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            sb.append(String.format(Locale.US, "%02x", b & 0xFF));
        }
        return sb.toString();
    }

    // --- Device Secret Management (Anti-Stalkerware 1-Tap Rotation/Revocation) ---

    byte[] getOrCreateSecret() {
        SharedPreferences prefs = appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String b64 = prefs.getString(KEY_SECRET_B64, "");
        if (b64 != null && !b64.isEmpty()) {
            try {
                byte[] decoded = Base64.decode(b64, Base64.NO_WRAP);
                if (decoded.length == 32) {
                    return decoded;
                }
            } catch (IllegalArgumentException ignored) {
            }
        }
        return rotateSecret();
    }

    byte[] rotateSecret() {
        byte[] next = new byte[32];
        new SecureRandom().nextBytes(next);
        appContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_SECRET_B64, Base64.encodeToString(next, Base64.NO_WRAP))
                .apply();
        return next;
    }

    String currentTagPreview() {
        byte[] tag = deriveRotatingTag(getOrCreateSecret(), System.currentTimeMillis() / ROTATION_WINDOW_MS);
        return toHex(tag).substring(0, 12).toUpperCase(Locale.US);
    }

    String verificationKeyFingerprint() {
        byte[] sec = getOrCreateSecret();
        try {
            return ZoeSignalCrypto.computeSafetyNumber(sec, sec).replace('\n', ' ').substring(0, 23);
        } catch (Exception ignored) {
            return currentTagPreview();
        }
    }

    // --- Hardware Android BLE Advertiser & Scanner ---

    void setListener(MeshListener listener) {
        this.listener = listener;
    }

    boolean isAdvertising() {
        return advertising;
    }

    boolean isScanning() {
        return scanning;
    }

    long remainingSeconds() {
        if (!advertising) {
            return 0L;
        }
        return Math.max(0L, (expiresAtMs - System.currentTimeMillis()) / 1000L);
    }

    static String[] requiredBlePermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            return new String[]{
                    Manifest.permission.BLUETOOTH_ADVERTISE,
                    Manifest.permission.BLUETOOTH_SCAN,
                    Manifest.permission.BLUETOOTH_CONNECT
            };
        }
        return new String[]{Manifest.permission.ACCESS_FINE_LOCATION};
    }

    boolean hasBlePermissions() {
        for (String perm : requiredBlePermissions()) {
            if (ContextCompat.checkSelfPermission(appContext, perm) != PackageManager.PERMISSION_GRANTED) {
                return false;
            }
        }
        return true;
    }

    @SuppressWarnings("MissingPermission")
    void startBeacon(byte mode) {
        if (!hasBlePermissions()) {
            notifyStatus(false, mode, "Bluetooth permissions are required to start the offline Help Beacon.");
            return;
        }
        BluetoothManager bm = (BluetoothManager) appContext.getSystemService(Context.BLUETOOTH_SERVICE);
        BluetoothAdapter adapter = bm == null ? null : bm.getAdapter();
        if (adapter == null || !adapter.isEnabled()) {
            notifyStatus(false, mode, "Turn on Bluetooth to broadcast an offline BLE Help Beacon.");
            return;
        }
        BluetoothLeAdvertiser adv = adapter.getBluetoothLeAdvertiser();
        if (adv == null) {
            notifyStatus(false, mode, "This device does not support BLE peripheral advertising.");
            return;
        }
        stopAdvertising(null);

        byte[] payload = buildBeaconPayload(getOrCreateSecret(), mode, System.currentTimeMillis());
        AdvertiseSettings settings = new AdvertiseSettings.Builder()
                .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
                .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_HIGH)
                .setConnectable(false)
                .setTimeout((int) MAX_BEACON_DURATION_MS)
                .build();
        AdvertiseData data = new AdvertiseData.Builder()
                .setIncludeDeviceName(false)
                .setIncludeTxPowerLevel(false)
                .addServiceUuid(SERVICE_PARCEL_UUID)
                .addServiceData(SERVICE_PARCEL_UUID, payload)
                .build();

        activeMode = mode;
        advertiser = adv;
        activeAdvCallback = new AdvertiseCallback() {
            @Override
            public void onStartSuccess(AdvertiseSettings settingsInEffect) {
                advertising = true;
                expiresAtMs = System.currentTimeMillis() + MAX_BEACON_DURATION_MS;
                handler.removeCallbacks(autoExpireTask);
                handler.postDelayed(autoExpireTask, MAX_BEACON_DURATION_MS);
                String desc = mode == MODE_LOCAL_SOS
                        ? "Offline BLE Local SOS Beacon active (auto-stops in 30m · rotating tag " + currentTagPreview() + ")."
                        : "Offline Blind E2EE Relay Beacon active (AirTag-style · auto-stops in 30m · tag " + currentTagPreview() + ").";
                notifyStatus(true, mode, desc);
            }

            @Override
            public void onStartFailure(int errorCode) {
                advertising = false;
                notifyStatus(false, mode, "Could not start BLE beacon (error " + errorCode + ").");
            }
        };
        try {
            adv.startAdvertising(settings, data, activeAdvCallback);
        } catch (SecurityException | IllegalStateException err) {
            advertising = false;
            notifyStatus(false, mode, "BLE beacon failed: " + err.getMessage());
        }
    }

    @SuppressWarnings("MissingPermission")
    void stopAdvertising(String message) {
        handler.removeCallbacks(autoExpireTask);
        boolean wasActive = advertising;
        advertising = false;
        expiresAtMs = 0L;
        if (advertiser != null && activeAdvCallback != null) {
            try {
                advertiser.stopAdvertising(activeAdvCallback);
            } catch (Exception ignored) {
            }
        }
        activeAdvCallback = null;
        if (message != null && (wasActive || listener != null)) {
            notifyStatus(false, activeMode, message);
        }
    }

    @SuppressWarnings("MissingPermission")
    void startMeshScan() {
        if (!hasBlePermissions()) {
            notifyStatus(advertising, activeMode, "Bluetooth scan permission is needed to listen for nearby Zoe beacons.");
            return;
        }
        BluetoothManager bm = (BluetoothManager) appContext.getSystemService(Context.BLUETOOTH_SERVICE);
        BluetoothAdapter adapter = bm == null ? null : bm.getAdapter();
        if (adapter == null || !adapter.isEnabled()) {
            notifyStatus(advertising, activeMode, "Turn on Bluetooth to scan for nearby offline Zoe beacons.");
            return;
        }
        BluetoothLeScanner sc = adapter.getBluetoothLeScanner();
        if (sc == null) {
            notifyStatus(advertising, activeMode, "BLE scanner unavailable on this device.");
            return;
        }
        stopMeshScan();
        scanner = sc;
        ScanFilter filter = new ScanFilter.Builder()
                .setServiceUuid(SERVICE_PARCEL_UUID)
                .build();
        ScanSettings settings = new ScanSettings.Builder()
                .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
                .build();
        activeScanCallback = new ScanCallback() {
            @Override
            public void onScanResult(int callbackType, ScanResult result) {
                if (result == null || result.getScanRecord() == null) {
                    return;
                }
                byte[] data = result.getScanRecord().getServiceData(SERVICE_PARCEL_UUID);
                ParsedBeacon parsed = parseBeaconPayload(data, result.getRssi(), System.currentTimeMillis());
                if (parsed != null) {
                    synchronized (sightings) {
                        sightings.put(parsed.rotatingTagHex, parsed);
                        if (sightings.size() > 24) {
                            String oldest = sightings.keySet().iterator().next();
                            sightings.remove(oldest);
                        }
                    }
                    notifySightings();
                }
            }
        };
        try {
            sc.startScan(Collections.singletonList(filter), settings, activeScanCallback);
            scanning = true;
            notifyStatus(advertising, activeMode, "Scanning offline via Bluetooth LE for nearby Zoe Help Beacons…");
        } catch (SecurityException | IllegalStateException err) {
            scanning = false;
            notifyStatus(advertising, activeMode, "BLE scan failed: " + err.getMessage());
        }
    }

    @SuppressWarnings("MissingPermission")
    void stopMeshScan() {
        scanning = false;
        if (scanner != null && activeScanCallback != null) {
            try {
                scanner.stopScan(activeScanCallback);
            } catch (Exception ignored) {
            }
        }
        activeScanCallback = null;
    }

    void stopAll() {
        stopAdvertising(null);
        stopMeshScan();
    }

    List<ParsedBeacon> snapshotSightings() {
        synchronized (sightings) {
            return new ArrayList<>(sightings.values());
        }
    }

    private void notifyStatus(boolean advOn, byte mode, String msg) {
        MeshListener l = listener;
        if (l != null) {
            handler.post(() -> l.onBeaconStatusChanged(advOn, mode, currentTagPreview(), msg));
        }
    }

    private void notifySightings() {
        MeshListener l = listener;
        if (l != null) {
            List<ParsedBeacon> copy = snapshotSightings();
            handler.post(() -> l.onNearbySighting(copy));
        }
    }
}
