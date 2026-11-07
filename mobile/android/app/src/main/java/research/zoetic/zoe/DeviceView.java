package research.zoetic.zoe;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.hardware.SensorManager;
import android.os.BatteryManager;
import android.os.Build;
import android.speech.SpeechRecognizer;
import android.widget.ScrollView;

import java.util.Locale;

final class DeviceView extends ScrollView {
    private final MainActivity activity;
    private final android.widget.TextView report;

    DeviceView(MainActivity activity) {
        super(activity);
        this.activity = activity;
        setFillViewport(true);
        android.widget.LinearLayout content = Ui.vertical(activity);
        content.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 8), Ui.dp(activity, 16), Ui.dp(activity, 24));
        addView(content);
        content.addView(Ui.heading(activity, "Device field"));
        content.addView(Ui.text(activity, "NuClide Research = Zoe + Nick · stable and unstable in balance", 14, Ui.PINK));
        content.addView(Ui.text(activity,
                "Local capability and battery observations. No Zoe-authored telemetry or image upload.",
                16, Ui.MUTED));
        report = Ui.text(activity, "", 16, Ui.TEXT);
        report.setBackground(Ui.panelBackground(activity, Ui.CYAN, 16));
        report.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 16), Ui.dp(activity, 16), Ui.dp(activity, 16));
        content.addView(report);
        content.addView(Ui.buttonRow(activity,
                Ui.button(activity, "Refresh", view -> refresh()),
                Ui.button(activity, "Speaker check", view -> activity.speak(
                        "Zoe speaker check. Measurement, evidence, belief, and action remain distinct."))));
        content.addView(Ui.button(activity, "Open Gemini", view -> activity.openGemini()));
        content.addView(Ui.button(activity, "Toggle comfort mode", view -> {
            activity.setComfortMode(!activity.isComfortMode());
            refresh();
        }));
        content.addView(Ui.text(activity, "Nicholas + Cat · USA · PLACES = Play. Learn. Adapt. Create. Explore. Share.", 14, Ui.PINK));
        content.addView(Ui.text(activity,
                "Speaker output occurs only after the button is pressed. Sensor inventory does not activate motion, location, camera, or microphone streams.",
                14, Ui.MUTED));
    }

    void refresh() {
        Context context = getContext();
        Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        String batteryText = "Battery unavailable";
        if (battery != null) {
            int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
            int status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
            int temperatureTenths = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
            String charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                    || status == BatteryManager.BATTERY_STATUS_FULL ? "charging/full" : "not charging";
            batteryText = String.format(Locale.US, "%d%% · %s", level * 100 / Math.max(scale, 1), charging);
            if (temperatureTenths != Integer.MIN_VALUE) {
                batteryText += String.format(Locale.US, " · %.1f °C", temperatureTenths / 10.0);
            }
        }
        SensorManager sensors = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        int sensorCount = sensors == null ? 0 : sensors.getSensorList(android.hardware.Sensor.TYPE_ALL).size();
        boolean onDeviceSpeech = Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(context);
        String gemini = "not installed";
        try {
            gemini = context.getPackageManager().getPackageInfo("com.google.android.apps.bard", 0).versionName;
        } catch (PackageManager.NameNotFoundException ignored) {
        }
        String value = "Device: " + Build.MODEL + " (" + Build.DEVICE + ")\n"
                + "Android: " + Build.VERSION.RELEASE + " · API " + Build.VERSION.SDK_INT + "\n"
                + "Security patch: " + Build.VERSION.SECURITY_PATCH + "\n\n"
                + "Battery: " + batteryText + "\n"
                + "Declared sensors: " + sensorCount + "\n"
                + "Camera hardware: " + context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY) + "\n"
                + "Microphone hardware: " + context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_MICROPHONE) + "\n"
                + "Speech service: " + SpeechRecognizer.isRecognitionAvailable(context) + "\n"
                + "On-device speech available: " + onDeviceSpeech + "\n"
                + "Gemini app: " + gemini + "\n\n"
                + "Comfort mode: " + (activity.isComfortMode() ? "on · relaxed speech + no activity animations" : "off") + "\n\n"
                + "Capability is not correctness or authorization. Model and sensor availability must be checked at runtime.";
        report.setText(value);
        report.announceForAccessibility("Device field refreshed");
    }
}
