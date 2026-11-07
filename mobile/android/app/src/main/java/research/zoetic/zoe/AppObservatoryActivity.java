package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.List;

public final class AppObservatoryActivity extends ComponentActivity {
    private final List<PackageInfo> packages = new ArrayList<>();
    private Spinner picker;
    private TextView status;
    private TextView report;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        ScrollView scroll = new ScrollView(this);
        android.widget.LinearLayout content = Ui.vertical(this);
        content.setPadding(Ui.dp(this, 18), Ui.dp(this, 20), Ui.dp(this, 18), Ui.dp(this, 24));
        scroll.addView(content);
        setContentView(scroll);
        content.addView(Ui.heading(this, "App Observatory"));
        content.addView(Ui.text(this,
                "Read-only package, version, installer, and enabled-state inspection. Public launchers only—no private app data, force stop, uninstall, or Play Protect control.",
                14, Ui.MUTED));
        status = Ui.text(this, "Loading the package inventory…", 16, Ui.YELLOW);
        status.setId(R.id.apps_status);
        content.addView(status);
        picker = new Spinner(this);
        picker.setId(R.id.apps_picker);
        content.addView(picker);
        content.addView(Ui.buttonRow(this,
                Ui.button(this, "Inspect selected", view -> inspect()),
                Ui.button(this, "Open public launcher", view -> launch())));
        content.addView(Ui.button(this, "Show Google / Play services", view -> filterGoogle()));
        report = Ui.text(this, "No package selected.", 15, Ui.TEXT);
        report.setId(R.id.apps_report);
        report.setBackground(Ui.panelBackground(this, Ui.CYAN, 16));
        report.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        report.setTextIsSelectable(true);
        content.addView(report);
        loadPackages();
    }

    private void loadPackages() {
        packages.clear();
        java.util.Set<String> seen = new java.util.HashSet<>();
        Intent launchable = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        for (android.content.pm.ResolveInfo resolve : getPackageManager()
                .queryIntentActivities(launchable, PackageManager.GET_META_DATA)) {
            String packageName = resolve.activityInfo.packageName;
            if (!seen.add(packageName)) {
                continue;
            }
            try {
                packages.add(getPackageManager().getPackageInfo(packageName, PackageManager.GET_META_DATA));
            } catch (PackageManager.NameNotFoundException ignored) {
            }
        }
        packages.sort(Comparator.comparing(item -> label(item).toLowerCase()));
        List<String> labels = new ArrayList<>();
        for (PackageInfo item : packages) {
            labels.add(label(item));
        }
        picker.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, labels));
        status.setText(packages.size() + " launcher-visible apps. No full-package inventory.");
        if (!packages.isEmpty()) {
            inspect();
        }
    }

    private String label(PackageInfo item) {
        ApplicationInfo application = item.applicationInfo;
        String label = application == null ? "" : application.loadLabel(getPackageManager()).toString();
        return label.isEmpty() ? item.packageName : label + " · " + item.packageName;
    }

    private PackageInfo selected() {
        return packages.get(picker.getSelectedItemPosition());
    }

    private void inspect() {
        if (packages.isEmpty()) {
            return;
        }
        PackageInfo item = selected();
        ApplicationInfo application = item.applicationInfo;
        String installer = getPackageManager().getInstallerPackageName(item.packageName);
        report.setText("Package: " + item.packageName
                + "\nVersion: " + item.versionName + " (" + item.versionCode + ")\n"
                + "Enabled: " + (application != null && application.enabled)
                + "\nInstaller: " + (installer == null ? "unknown/system" : installer)
                + "\nTarget SDK: " + (application == null ? "unknown" : application.targetSdkVersion)
                + "\n\nMetadata only. No private application data or Play Protect service was accessed.");
        status.setText("Package metadata inspected read-only.");
    }

    private void launch() {
        if (packages.isEmpty()) {
            return;
        }
        PackageInfo item = selected();
        Intent launch = getPackageManager().getLaunchIntentForPackage(item.packageName);
        if (launch == null) {
            status.setText("No public launcher is exported for " + item.packageName + ".");
            return;
        }
        try {
            startActivity(launch);
        } catch (ActivityNotFoundException error) {
            status.setText("The public launcher could not be opened.");
        }
    }

    private void filterGoogle() {
        List<PackageInfo> selected = new ArrayList<>();
        for (PackageInfo item : packages) {
            if (item.packageName.contains("google") || item.packageName.contains("android.vending")) {
                selected.add(item);
            }
        }
        StringBuilder text = new StringBuilder("Google / Play-related packages: " + selected.size() + "\n\n");
        for (PackageInfo item : selected) {
            text.append(item.packageName).append(" · ").append(item.versionName).append("\n");
        }
        text.append("\nPlay Protect is a protected Google service, not a public control API. This inventory does not alter it.");
        report.setText(text.toString());
        status.setText("Google-related public metadata filtered. No service was modified.");
    }
}
