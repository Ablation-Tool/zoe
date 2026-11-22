package research.zoetic.zoe;

import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.InstallSourceInfo;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.widget.AdapterView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import androidx.activity.ComponentActivity;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class AppObservatoryActivity extends ComponentActivity {
    private final List<PackageInfo> packages = new ArrayList<>();
    private Spinner picker;
    private TextView status;
    private TextView report;

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

        content.addView(Ui.topBar(this, "App Observatory", "Read-only launcher metadata"));
        content.addView(Ui.text(this,
                "Read-only package, version, installer, and enabled-state inspection. Public launchers only—no private app data, force stop, uninstall, or Play Protect control.",
                14, Ui.MUTED));
        status = Ui.text(this, "Loading the package inventory…", 15, Ui.YELLOW);
        status.setId(R.id.apps_status);
        content.addView(status);
        picker = new Spinner(this);
        picker.setId(R.id.apps_picker);
        picker.setBackground(Ui.panelBackground(this, Ui.PANEL, Ui.withAlpha(Ui.GREEN, 110), 14));
        LinearLayout.LayoutParams pickerParams = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        pickerParams.setMargins(0, Ui.dp(this, 4), 0, Ui.dp(this, 6));
        content.addView(picker, pickerParams);
        content.addView(Ui.buttonRow(this,
                Ui.button(this, "Inspect selected", Ui.CYAN, view -> inspect()),
                Ui.button(this, "Open public launcher", Ui.GREEN, view -> launch())));
        content.addView(Ui.button(this, "Show Google / Play services", Ui.GOLD, view -> filterGoogle()));
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
        Set<String> seen = new HashSet<>();
        Intent launchable = new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER);
        for (ResolveInfo resolve : getPackageManager()
                .queryIntentActivities(launchable, PackageManager.GET_META_DATA)) {
            if (resolve.activityInfo == null) {
                continue;
            }
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
        picker.setAdapter(Ui.spinnerAdapter(this, labels));
        picker.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener() {
            @Override
            public void onItemSelected(AdapterView<?> parent, View view, int position, long id) {
                inspect();
            }

            @Override
            public void onNothingSelected(AdapterView<?> parent) {
            }
        });
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
        int position = picker.getSelectedItemPosition();
        if (position < 0 || position >= packages.size()) {
            return null;
        }
        return packages.get(position);
    }

    @SuppressWarnings("deprecation")
    private long packageVersionCode(PackageInfo item) {
        return Build.VERSION.SDK_INT >= 28 ? item.getLongVersionCode() : item.versionCode;
    }

    @SuppressWarnings("deprecation")
    private String installerName(String packageName) {
        try {
            if (Build.VERSION.SDK_INT >= 30) {
                InstallSourceInfo info = getPackageManager().getInstallSourceInfo(packageName);
                String installer = info.getInstallingPackageName();
                return installer == null ? "unknown/system" : installer;
            }
            String installer = getPackageManager().getInstallerPackageName(packageName);
            return installer == null ? "unknown/system" : installer;
        } catch (PackageManager.NameNotFoundException | SecurityException error) {
            return "unknown/system";
        }
    }

    private void inspect() {
        PackageInfo item = selected();
        if (item == null) {
            status.setText("No launcher-visible package is selected.");
            return;
        }
        ApplicationInfo application = item.applicationInfo;
        report.setText("Package: " + item.packageName
                + "\nVersion: " + item.versionName + " (" + packageVersionCode(item) + ")\n"
                + "Enabled: " + (application != null && application.enabled)
                + "\nInstaller: " + installerName(item.packageName)
                + "\nTarget SDK: " + (application == null ? "unknown" : application.targetSdkVersion)
                + "\n\nMetadata only. No private application data or Play Protect service was accessed.");
        status.setText("Package metadata inspected read-only.");
    }

    private void launch() {
        PackageInfo item = selected();
        if (item == null) {
            return;
        }
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
