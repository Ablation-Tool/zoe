package research.zoetic.zoe;

import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.os.Bundle;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.activity.ComponentActivity;
import androidx.core.content.FileProvider;

import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class TripJournalActivity extends ComponentActivity {
    private final ExecutorService executor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean syncing = new AtomicBoolean(false);
    private final ElizaGemClient elizaClient = new ElizaGemClient();
    private TextView status;
    private LinearLayout listContainer;

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

        content.addView(Ui.topBar(this, "Trip journal", "Saved field sightings · private on device"));
        status = Ui.text(this, "Trip journal ready. Offline-first.", 14, Ui.YELLOW);
        status.setId(R.id.journal_status);
        content.addView(status);

        Button sync = Ui.primaryButton(this, "Sync to Lab Relay", Ui.RUBY, view -> syncUnsynced());
        sync.setId(R.id.journal_sync);
        Button export = Ui.button(this, "Share log", Ui.GREEN, view -> shareExport());
        export.setId(R.id.journal_export);
        Button clear = Ui.button(this, "Clear all", Ui.RUBY, view -> confirmClear());
        clear.setId(R.id.journal_clear);
        content.addView(Ui.buttonRow(this, sync, export, clear));

        listContainer = new LinearLayout(this);
        listContainer.setOrientation(LinearLayout.VERTICAL);
        listContainer.setId(R.id.journal_list);
        content.addView(listContainer);

        renderEntries();
    }

    @Override
    protected void onResume() {
        super.onResume();
        renderEntries();
    }

    private void renderEntries() {
        listContainer.removeAllViews();
        List<TripJournalStore.Entry> entries = TripJournalStore.load(this);
        if (entries.isEmpty()) {
            status.setText("No saved trip sightings yet. Open Guided Vision, inspect one frame, and tap Save to Trip Journal.");
            TextView empty = Ui.text(this,
                    "Your saved trip sightings, notes, OCR reads, light measurements, and optional cloud answers will appear right here.",
                    15, Ui.MUTED);
            empty.setBackground(Ui.panelBackground(this, Ui.PANEL, Ui.BORDER, 16));
            empty.setPadding(Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16), Ui.dp(this, 16));
            listContainer.addView(empty);
            return;
        }
        int unsynced = 0;
        for (TripJournalStore.Entry entry : entries) {
            if (!entry.syncedToRelay) {
                unsynced++;
            }
            listContainer.addView(buildCard(entry));
        }
        status.setText(entries.size() + " saved sighting(s) · " + unsynced + " pending workstation relay sync.");
    }

    private LinearLayout buildCard(TripJournalStore.Entry entry) {
        LinearLayout card = new LinearLayout(this);
        card.setOrientation(LinearLayout.VERTICAL);
        card.setBackground(Ui.panelBackground(this, Ui.PANEL,
                Ui.withAlpha(entry.syncedToRelay ? Ui.GREEN : Ui.CYAN, 130), 18));
        card.setPadding(Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14), Ui.dp(this, 14));
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        params.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 4));
        card.setLayoutParams(params);

        LinearLayout hdr = new LinearLayout(this);
        hdr.setOrientation(LinearLayout.HORIZONTAL);
        TextView stamp = Ui.text(this, entry.timestampIso, 12.5f, Ui.GOLD);
        hdr.addView(stamp, new LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1.0f));
        hdr.addView(Ui.badge(this,
                entry.syncedToRelay ? "SYNCED TO ZOE" : "ON DEVICE",
                entry.syncedToRelay ? Ui.GREEN : Ui.CYAN));
        card.addView(hdr);

        File thumbFile = TripJournalStore.thumbnailFile(this, entry);
        if (thumbFile != null) {
            Bitmap bmp = BitmapFactory.decodeFile(thumbFile.getAbsolutePath());
            if (bmp != null) {
                ImageView img = new ImageView(this);
                img.setImageBitmap(bmp);
                img.setAdjustViewBounds(true);
                img.setScaleType(ImageView.ScaleType.CENTER_CROP);
                img.setContentDescription("Trip sighting thumbnail from " + entry.timestampIso);
                LinearLayout.LayoutParams imgParams = new LinearLayout.LayoutParams(
                        LinearLayout.LayoutParams.MATCH_PARENT, Ui.dp(this, 165));
                imgParams.setMargins(0, Ui.dp(this, 8), 0, Ui.dp(this, 8));
                card.addView(img, imgParams);
            }
        }

        StringBuilder body = new StringBuilder();
        if (!entry.note.isEmpty()) {
            body.append("NOTE: ").append(entry.note).append("\n\n");
        }
        if (!entry.paletteSummary.isEmpty()) {
            body.append("OFFLINE PIXEL MATH\n").append(entry.paletteSummary).append("\n\n");
        }
        if (!entry.labels.isEmpty()) {
            body.append("OFFLINE IMAGE LABELS\n").append(entry.labels).append("\n\n");
        }
        if (!entry.ocrText.isEmpty()) {
            body.append("OFFLINE OCR\n").append(entry.ocrText).append("\n\n");
        }
        if (!entry.deviceAiDescription.isEmpty()) {
            body.append("ON-DEVICE GEMINI NANO\n").append(entry.deviceAiDescription).append("\n\n");
        }
        if (!entry.cloudDescription.isEmpty()) {
            body.append("ONLINE CLOUD · GEMINI\n").append(entry.cloudDescription).append('\n');
        }
        TextView details = Ui.text(this, body.toString().trim(), 13.5f, Ui.TEXT);
        details.setTextIsSelectable(true);
        card.addView(details);

        Button editNote = Ui.button(this, "Edit note", Ui.PINK, view -> promptEditNote(entry));
        Button sharePhoto = Ui.button(this, thumbFile != null ? "Share / Gemini" : "Share note", Ui.CYAN,
                view -> shareEntry(entry, thumbFile));
        card.addView(Ui.buttonRow(this, editNote, sharePhoto));
        return card;
    }

    private void promptEditNote(TripJournalStore.Entry entry) {
        EditText input = Ui.input(this, entry.note, "What caught your eye here?");
        new AlertDialog.Builder(this)
                .setTitle("Edit trip note")
                .setView(input)
                .setNegativeButton("Cancel", null)
                .setPositiveButton("Save", (dialog, which) -> {
                    TripJournalStore.updateNote(this, entry.id, input.getText().toString().trim());
                    renderEntries();
                })
                .show();
    }

    private void shareEntry(TripJournalStore.Entry entry, File thumbFile) {
        String text = TripJournalStore.formatRelayNote(entry);
        Intent intent = new Intent(Intent.ACTION_SEND);
        intent.putExtra(Intent.EXTRA_SUBJECT, "Zoe trip sighting · " + entry.timestampIso);
        intent.putExtra(Intent.EXTRA_TEXT, text);
        if (thumbFile != null && thumbFile.isFile()) {
            try {
                File dir = new File(getCacheDir(), "trip_share");
                if (!dir.exists()) {
                    dir.mkdirs();
                }
                File shareCopy = new File(dir, "sighting_share.jpg");
                copyFile(thumbFile, shareCopy);
                Uri uri = FileProvider.getUriForFile(this, getPackageName() + ".fileprovider", shareCopy);
                intent.setType("image/jpeg");
                intent.putExtra(Intent.EXTRA_STREAM, uri);
                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
            } catch (IOException | IllegalArgumentException error) {
                intent.setType("text/plain");
            }
        } else {
            intent.setType("text/plain");
        }
        try {
            startActivity(Intent.createChooser(intent, "Share trip sighting"));
        } catch (ActivityNotFoundException error) {
            status.setText("No sharing app is available.");
        }
    }

    private static void copyFile(File src, File dst) throws IOException {
        try (FileInputStream in = new FileInputStream(src); FileOutputStream out = new FileOutputStream(dst)) {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
            }
        }
    }

    private void shareExport() {
        List<TripJournalStore.Entry> entries = TripJournalStore.load(this);
        if (entries.isEmpty()) {
            status.setText("Nothing to share yet. Save at least one trip sighting first.");
            return;
        }
        Intent share = new Intent(Intent.ACTION_SEND)
                .setType("text/plain")
                .putExtra(Intent.EXTRA_SUBJECT, "Zoe Trip Field Journal")
                .putExtra(Intent.EXTRA_TEXT, TripJournalStore.formatExport(entries));
        try {
            startActivity(Intent.createChooser(share, "Share Trip Journal"));
        } catch (ActivityNotFoundException error) {
            status.setText("No sharing app is available.");
        }
    }

    private void confirmClear() {
        if (TripJournalStore.load(this).isEmpty()) {
            status.setText("Trip journal is already empty.");
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Clear all trip sightings?")
                .setMessage("This deletes all locally saved notes and thumbnails from the phone.")
                .setNegativeButton("Keep", null)
                .setPositiveButton("Clear all", (dialog, which) -> {
                    TripJournalStore.clear(this);
                    renderEntries();
                })
                .show();
    }

    private void syncUnsynced() {
        if (!syncing.compareAndSet(false, true)) {
            return;
        }
        List<TripJournalStore.Entry> entries = TripJournalStore.load(this);
        int pending = 0;
        for (TripJournalStore.Entry entry : entries) {
            if (!entry.syncedToRelay) {
                pending++;
            }
        }
        if (pending == 0) {
            syncing.set(false);
            status.setText("All saved sightings are already synced with Zoe's Lab Relay.");
            return;
        }
        String endpoint = ElizaGemClient.savedEndpoint(this);
        status.setText("Syncing " + pending + " sighting(s) to " + endpoint + "…");
        executor.execute(() -> {
            int sent = 0;
            String lastError = null;
            for (TripJournalStore.Entry entry : entries) {
                if (entry.syncedToRelay) {
                    continue;
                }
                try {
                    elizaClient.relay(endpoint, TripJournalStore.formatRelayNote(entry), "pixel_trip_journal");
                    TripJournalStore.markSynced(this, entry.id);
                    sent++;
                } catch (Exception error) {
                    lastError = error.getMessage();
                    break;
                }
            }
            int finalSent = sent;
            String finalError = lastError;
            runOnUiThread(() -> {
                syncing.set(false);
                if (isFinishing() || isDestroyed()) {
                    return;
                }
                renderEntries();
                if (finalError != null) {
                    status.setText("Synced " + finalSent + " sighting(s), stopped on error: " + finalError
                            + " (check `zoe eliza serve` + `adb reverse tcp:8765 tcp:8765`).");
                } else {
                    status.setText("Synced " + finalSent + " sighting(s) straight into Zoe's Lab Relay.");
                }
            });
        });
    }

    @Override
    protected void onDestroy() {
        executor.shutdownNow();
        super.onDestroy();
    }
}
