package research.zoetic.zoe;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.content.Context;
import android.content.pm.PackageManager;
import android.nfc.NfcAdapter;
import android.os.Build;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.atomic.AtomicBoolean;

public final class RadioActivity extends ComponentActivity {
    private static final int BLUETOOTH_PERMISSION = 101;
    private final List<BluetoothDevice> devices = new ArrayList<>();
    private final Object gattLock = new Object();
    private BluetoothAdapter adapter;
    private BluetoothGatt gatt;
    private NfcAdapter nfc;
    private Spinner devicePicker;
    private TextView status;
    private TextView report;
    private Integer lastRssi;
    private Integer calibratedRssi;
    private boolean nfcListening;

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

        content.addView(Ui.topBar(this, "Radio Field", "Bluetooth RSSI & NFC"));
        status = Ui.statusBanner(this, "Radio telemetry is idle.", Ui.COBALT);
        status.setId(R.id.radio_status);
        content.addView(status);
        BluetoothManager manager = (BluetoothManager) getSystemService(Context.BLUETOOTH_SERVICE);
        adapter = manager == null ? null : manager.getAdapter();
        nfc = NfcAdapter.getDefaultAdapter(this);
        devicePicker = new Spinner(this);
        devicePicker.setId(R.id.radio_devices);
        devicePicker.setBackground(Ui.cardBackground(this, 16));
        LinearLayout.LayoutParams pickerParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        pickerParams.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 8));
        content.addView(devicePicker, pickerParams);
        Button rssi = Ui.primaryButton(this, "Read BLE RSSI", Ui.CYAN, view -> readRssi());
        rssi.setId(R.id.radio_rssi);
        Button calibrate = Ui.button(this, "Calibrate 1 m", Ui.GOLD, view -> calibrate());
        calibrate.setId(R.id.radio_calibrate);
        content.addView(Ui.buttonRow(this, rssi, calibrate));
        Button nfcButton = Ui.button(this, "Listen NFC", Ui.GREEN, view -> toggleNfc());
        nfcButton.setId(R.id.radio_nfc);
        Button stop = Ui.button(this, "Stop", Ui.RUBY, view -> stopRadio());
        stop.setId(R.id.radio_stop);
        content.addView(Ui.buttonRow(this, nfcButton, stop));
        report = Ui.text(this,
                "Select a paired device and tap Read BLE RSSI, or tap Listen NFC to detect a nearby tag.",
                14.5f, Ui.TEXT);
        report.setId(R.id.radio_report);
        report.setBackground(Ui.cardBackground(this, 20));
        report.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
        report.setTextIsSelectable(true);
        LinearLayout.LayoutParams repLp = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        repLp.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
        content.addView(report, repLp);
        TextView note = Ui.text(this,
                "RSSI is signal strength, not verified distance. No tag writing or hidden scanning.",
                12.5f, Ui.MUTED);
        note.setGravity(android.view.Gravity.CENTER);
        content.addView(note);
        if (Build.VERSION.SDK_INT >= 31 && ContextCompat.checkSelfPermission(this, Manifest.permission.BLUETOOTH_CONNECT)
                != PackageManager.PERMISSION_GRANTED) {
            ActivityCompat.requestPermissions(this, new String[]{Manifest.permission.BLUETOOTH_CONNECT}, BLUETOOTH_PERMISSION);
        } else {
            loadBondedDevices();
        }
    }

    private void loadBondedDevices() {
        devices.clear();
        try {
            if (adapter != null && adapter.getBondedDevices() != null) {
                devices.addAll(adapter.getBondedDevices());
            }
            devices.sort(Comparator.comparing(device -> device.getName() == null ? "" : device.getName()));
            List<String> labels = new ArrayList<>();
            for (BluetoothDevice device : devices) {
                labels.add(device.getName() == null ? "Unnamed bonded device" : device.getName());
            }
            if (labels.isEmpty()) {
                labels.add("No bonded devices");
            }
            devicePicker.setAdapter(Ui.spinnerAdapter(this, labels));
            status.setText(adapter == null ? "Bluetooth is unavailable on this device."
                    : devices.size() + " bonded devices available. Select one for a BLE RSSI attempt.");
        } catch (SecurityException error) {
            status.setText("Bluetooth Connect permission was not granted. No device inventory was accessed.");
        }
    }

    private void readRssi() {
        if (adapter == null || !adapter.isEnabled()) {
            status.setText("Bluetooth is off or unavailable. No radio connection was started.");
            return;
        }
        int pos = devicePicker.getSelectedItemPosition();
        if (devices.isEmpty() || pos < 0 || pos >= devices.size()) {
            status.setText("No bonded device is selected. Pair a device in system settings first.");
            return;
        }
        BluetoothDevice device = devices.get(pos);
        closeGatt();
        status.setText("Connecting to the selected bonded device for one RSSI reading…");
        AtomicBoolean rssiReceived = new AtomicBoolean(false);
        try {
            BluetoothGatt newGatt = device.connectGatt(this, false, new BluetoothGattCallback() {
                @Override
                public void onConnectionStateChange(BluetoothGatt activeGatt, int gattStatus, int newState) {
                    if (newState == BluetoothProfile.STATE_CONNECTED && gattStatus == BluetoothGatt.GATT_SUCCESS) {
                        try {
                            if (!activeGatt.readRemoteRssi()) {
                                reportError("The device did not accept an RSSI read.");
                            }
                        } catch (SecurityException error) {
                            reportError("Bluetooth permission was revoked before RSSI was read.");
                        }
                    } else if (newState == BluetoothProfile.STATE_DISCONNECTED && !rssiReceived.get()) {
                        reportError("The device disconnected before RSSI was read.");
                    }
                }

                @Override
                public void onReadRemoteRssi(BluetoothGatt activeGatt, int rssi, int gattStatus) {
                    if (gattStatus == BluetoothGatt.GATT_SUCCESS) {
                        rssiReceived.set(true);
                        lastRssi = rssi;
                        Integer ref = calibratedRssi;
                        runOnUiThread(() -> {
                            if (isFinishing() || isDestroyed()) {
                                return;
                            }
                            if (ref != null) {
                                double candidate = RadioRanging.pathLossDistance(ref, rssi, 2.0);
                                report.setText(String.format(Locale.US,
                                        "BLE RSSI: %d dBm\nCalibration ref (1 m): %d dBm\nPath-loss candidate: %.2f m (exponent 2.0)\n\nRSSI is signal strength, not verified distance or position.",
                                        rssi, ref, candidate));
                            } else {
                                report.setText("BLE RSSI: " + rssi + " dBm\n\nRSSI is signal strength, not distance. Calibrate at a measured one meter only if you want to evaluate the path-loss model.");
                            }
                            status.setText("RSSI reading complete. Connection closed.");
                        });
                    } else {
                        reportError("RSSI read failed with GATT status " + gattStatus + ".");
                    }
                    closeGatt();
                }
            }, BluetoothDevice.TRANSPORT_LE);
            synchronized (gattLock) {
                gatt = newGatt;
            }
        } catch (SecurityException error) {
            reportError("Bluetooth Connect permission was not granted. No connection was started.");
        } catch (RuntimeException error) {
            reportError(error.getMessage());
        }
    }

    private void reportError(String message) {
        runOnUiThread(() -> {
            if (!isFinishing() && !isDestroyed()) {
                status.setText(message);
            }
        });
        closeGatt();
    }

    private void calibrate() {
        if (lastRssi == null) {
            status.setText("Read RSSI at a measured one meter before calibrating.");
            return;
        }
        calibratedRssi = lastRssi;
        double candidate = RadioRanging.pathLossDistance(calibratedRssi, lastRssi, 2.0);
        report.setText(String.format(Locale.US,
                "Calibration: %d dBm at a user-declared 1 m\nCurrent RSSI: %d dBm\nPath-loss candidate: %.2f m with exponent 2.0\n\nThis candidate assumes free-space loss and no obstruction. It is not verified distance or position.",
                calibratedRssi, lastRssi, candidate));
        status.setText("Calibration recorded locally. No RF behavior was changed.");
    }

    private void toggleNfc() {
        if (nfc == null) {
            status.setText("NFC is unavailable on this device.");
            return;
        }
        if (nfcListening) {
            stopRadio();
            return;
        }
        if (!nfc.isEnabled()) {
            status.setText("NFC is off. Enable it in system settings to read a tag.");
            return;
        }
        nfcListening = true;
        nfc.enableReaderMode(this, tag -> runOnUiThread(() -> {
            if (isFinishing() || isDestroyed()) {
                return;
            }
            byte[] tagId = tag.getId();
            String[] techs = tag.getTechList();
            report.setText("NFC tag detected.\nID: " + (tagId == null ? "unavailable" : hex(tagId))
                    + "\nTechnologies: " + (techs == null ? 0 : techs.length)
                    + "\n\nPresence only. NFC is not a distance measurement. No tag content was read or written.");
            status.setText("NFC tag detected. Stop the radio lab to end reader mode.");
        }), NfcAdapter.FLAG_READER_NFC_A | NfcAdapter.FLAG_READER_NFC_B
                | NfcAdapter.FLAG_READER_NFC_F | NfcAdapter.FLAG_READER_NFC_V, null);
        status.setText("NFC reader mode active. Present a tag or stop the radio lab.");
    }

    private static String hex(byte[] value) {
        StringBuilder result = new StringBuilder();
        for (byte item : value) {
            result.append(String.format(Locale.US, "%02X", item));
        }
        return result.toString();
    }

    private void closeGatt() {
        synchronized (gattLock) {
            if (gatt != null) {
                try {
                    gatt.disconnect();
                } catch (SecurityException ignored) {
                }
                try {
                    gatt.close();
                } catch (SecurityException ignored) {
                }
                gatt = null;
            }
        }
    }

    private void stopRadio() {
        closeGatt();
        if (nfcListening && nfc != null) {
            try {
                nfc.disableReaderMode(this);
            } catch (RuntimeException ignored) {
            }
            nfcListening = false;
        }
        status.setText("Radio Lab stopped. No GATT connection or NFC reader is active.");
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode == BLUETOOTH_PERMISSION) {
            if (grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                loadBondedDevices();
            } else {
                status.setText("Bluetooth Connect permission was not granted. No device inventory or connection was accessed.");
            }
        }
    }

    @Override
    protected void onPause() {
        stopRadio();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        stopRadio();
        super.onDestroy();
    }
}
