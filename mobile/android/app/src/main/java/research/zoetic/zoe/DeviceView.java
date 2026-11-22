package research.zoetic.zoe;

import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.pm.PackageManager;
import android.hardware.SensorManager;
import android.os.BatteryManager;
import android.os.Build;
import android.speech.SpeechRecognizer;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.util.Locale;

/**
 * Clean Apple/Google Settings-style device status & hardware check screen.
 */
final class DeviceView extends ScrollView {
    private final MainActivity activity;
    private final LinearLayout deviceCard;
    private final LinearLayout capabilityCard;
    private final Button comfortButton;

    DeviceView(MainActivity activity) {
        super(activity);
        this.activity = activity;
        setFillViewport(true);
        setBackgroundColor(android.graphics.Color.TRANSPARENT);

        LinearLayout content = Ui.vertical(activity);
        content.setPadding(Ui.dp(activity, 16), Ui.dp(activity, 4), Ui.dp(activity, 16), Ui.dp(activity, 28));
        addView(content);

        TextView subtitle = Ui.text(activity, "Battery, voice & hardware status.", 14.5f, Ui.MUTED);
        subtitle.setPadding(Ui.dp(activity, 4), 0, Ui.dp(activity, 4), Ui.dp(activity, 6));
        content.addView(subtitle);

        comfortButton = Ui.button(activity, "Comfort: Off", Ui.PINK, view -> {
            activity.setComfortMode(!activity.isComfortMode());
            refresh();
        });

        content.addView(Ui.buttonRow(activity,
                Ui.primaryButton(activity, "Refresh", Ui.CYAN, view -> refresh()),
                Ui.button(activity, "Speaker check", Ui.GREEN, view -> activity.speak(
                        "Zoe speaker check. Audio is working clearly."))));

        content.addView(Ui.section(activity, "This phone"));
        deviceCard = Ui.groupedCard(activity);
        content.addView(deviceCard, cardMargins(activity));

        content.addView(Ui.section(activity, "Capabilities"));
        capabilityCard = Ui.groupedCard(activity);
        content.addView(capabilityCard, cardMargins(activity));

        LinearLayout row2 = Ui.buttonRow(activity,
                comfortButton,
                Ui.button(activity, "Open Gemini", Ui.GOLD, view -> activity.openGemini()));
        row2.setPadding(0, Ui.dp(activity, 8), 0, 0);
        content.addView(row2);

        TextView note = Ui.text(activity,
                "Checked locally on your phone. Capability is not proof or permission.",
                12.5f, Ui.MUTED);
        note.setGravity(android.view.Gravity.CENTER);
        note.setPadding(Ui.dp(activity, 12), Ui.dp(activity, 14), Ui.dp(activity, 12), 0);
        content.addView(note);
    }

    private static LinearLayout.LayoutParams cardMargins(Context ctx) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.setMargins(0, 0, 0, Ui.dp(ctx, 4));
        return lp;
    }

    private void addRow(LinearLayout card, String label, String value) {
        if (card.getChildCount() > 0) {
            card.addView(Ui.cardDivider(getContext()));
        }
        card.addView(Ui.settingRow(getContext(), label, value));
    }

    void refresh() {
        Context context = getContext();
        Intent battery = context.registerReceiver(null, new IntentFilter(Intent.ACTION_BATTERY_CHANGED));
        String batteryText = "Unavailable";
        if (battery != null) {
            int level = battery.getIntExtra(BatteryManager.EXTRA_LEVEL, -1);
            int scale = battery.getIntExtra(BatteryManager.EXTRA_SCALE, -1);
            int status = battery.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
            int temperatureTenths = battery.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Integer.MIN_VALUE);
            String charging = status == BatteryManager.BATTERY_STATUS_CHARGING
                    || status == BatteryManager.BATTERY_STATUS_FULL ? "Charging" : "Battery";
            batteryText = String.format(Locale.US, "%d%% · %s", level * 100 / Math.max(scale, 1), charging);
            if (temperatureTenths != Integer.MIN_VALUE) {
                batteryText += String.format(Locale.US, " · %.1f°C", temperatureTenths / 10.0);
            }
        }
        SensorManager sensors = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        int sensorCount = sensors == null ? 0 : sensors.getSensorList(android.hardware.Sensor.TYPE_ALL).size();
        boolean hasCam = context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_CAMERA_ANY);
        boolean hasMic = context.getPackageManager().hasSystemFeature(PackageManager.FEATURE_MICROPHONE);
        boolean hasSpeech = SpeechRecognizer.isRecognitionAvailable(context);
        boolean onDeviceSpeech = Build.VERSION.SDK_INT >= 31 && SpeechRecognizer.isOnDeviceRecognitionAvailable(context);
        String gemini = "Not installed";
        try {
            gemini = "v" + context.getPackageManager().getPackageInfo("com.google.android.apps.bard", 0).versionName;
        } catch (PackageManager.NameNotFoundException ignored) {
        }

        deviceCard.removeAllViews();
        addRow(deviceCard, "Model", Build.MODEL);
        addRow(deviceCard, "Android", Build.VERSION.RELEASE + " (API " + Build.VERSION.SDK_INT + ")");
        addRow(deviceCard, "Battery:", batteryText);
        addRow(deviceCard, "Network", Ui.networkStatusLabel(context));
        addRow(deviceCard, "Comfort mode", activity.isComfortMode() ? "On" : "Off");

        String aiSummary = DeviceAiController.hasRealAiCoreService(context)
                ? "Gemini Nano ready"
                : "Offline OCR & labels";

        capabilityCard.removeAllViews();
        addRow(capabilityCard, "Camera & mic", (hasCam ? "Camera" : "No cam") + " · " + (hasMic ? "Mic" : "No mic"));
        addRow(capabilityCard, "Speech service", hasSpeech ? "Available" : "Unavailable");
        addRow(capabilityCard, "On-device speech available:", onDeviceSpeech ? "Yes" : "No");
        addRow(capabilityCard, "On-device AI", aiSummary);
        addRow(capabilityCard, "Sensors", sensorCount + " active");
        addRow(capabilityCard, "Gemini app", gemini);

        comfortButton.setText(activity.isComfortMode() ? "Comfort: On" : "Comfort: Off");
        deviceCard.announceForAccessibility("Device field refreshed");
    }
}
