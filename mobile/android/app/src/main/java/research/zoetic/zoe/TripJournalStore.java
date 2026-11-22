package research.zoetic.zoe;

import android.content.Context;
import android.graphics.Bitmap;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

final class TripJournalStore {
    static final int MAX_ENTRIES = 40;
    private static final String INDEX_FILE = "trip_journal.json";
    private static final String THUMB_DIR = "trip_thumbs";

    static final class Entry {
        final String id;
        final String timestampIso;
        final String note;
        final String ocrText;
        final String labels;
        final String paletteSummary;
        final String deviceAiDescription;
        final String cloudDescription;
        final String thumbFilename;
        final boolean syncedToRelay;

        Entry(String id, String timestampIso, String note, String ocrText, String labels,
              String paletteSummary, String deviceAiDescription, String cloudDescription,
              String thumbFilename, boolean syncedToRelay) {
            this.id = safe(id);
            this.timestampIso = safe(timestampIso);
            this.note = safe(note);
            this.ocrText = safe(ocrText);
            this.labels = safe(labels);
            this.paletteSummary = safe(paletteSummary);
            this.deviceAiDescription = safe(deviceAiDescription);
            this.cloudDescription = safe(cloudDescription);
            this.thumbFilename = safe(thumbFilename);
            this.syncedToRelay = syncedToRelay;
        }

        Entry withNote(String updatedNote) {
            return new Entry(id, timestampIso, updatedNote, ocrText, labels,
                    paletteSummary, deviceAiDescription, cloudDescription, thumbFilename, syncedToRelay);
        }

        Entry withSynced(boolean synced) {
            return new Entry(id, timestampIso, note, ocrText, labels,
                    paletteSummary, deviceAiDescription, cloudDescription, thumbFilename, synced);
        }

        private static String safe(String value) {
            return value == null ? "" : value;
        }
    }

    private TripJournalStore() {
    }

    static String newId() {
        return "trip-" + System.currentTimeMillis();
    }

    static String nowIso() {
        return new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(new Date());
    }

    static String toJson(List<Entry> entries) {
        List<Object> serialized = new ArrayList<>();
        if (entries != null) {
            for (Entry entry : entries) {
                Map<String, Object> item = new LinkedHashMap<>();
                item.put("id", entry.id);
                item.put("timestampIso", entry.timestampIso);
                item.put("note", entry.note);
                item.put("ocrText", entry.ocrText);
                item.put("labels", entry.labels);
                item.put("paletteSummary", entry.paletteSummary);
                item.put("deviceAiDescription", entry.deviceAiDescription);
                item.put("cloudDescription", entry.cloudDescription);
                item.put("thumbFilename", entry.thumbFilename);
                item.put("syncedToRelay", entry.syncedToRelay);
                serialized.add(item);
            }
        }
        return MiniJson.stringify(serialized);
    }

    static List<Entry> fromJson(String json) {
        if (json == null || json.isBlank()) {
            return new ArrayList<>();
        }
        List<Object> raw = MiniJson.parseArray(json);
        List<Entry> entries = new ArrayList<>();
        for (Object item : raw) {
            Map<String, Object> map = MiniJson.asObject(item);
            if (map == null) {
                continue;
            }
            entries.add(new Entry(
                    MiniJson.asString(map, "id", ""),
                    MiniJson.asString(map, "timestampIso", ""),
                    MiniJson.asString(map, "note", ""),
                    MiniJson.asString(map, "ocrText", ""),
                    MiniJson.asString(map, "labels", ""),
                    MiniJson.asString(map, "paletteSummary", ""),
                    MiniJson.asString(map, "deviceAiDescription", ""),
                    MiniJson.asString(map, "cloudDescription", ""),
                    MiniJson.asString(map, "thumbFilename", ""),
                    MiniJson.asBoolean(map, "syncedToRelay", false)));
        }
        return trimBounded(entries);
    }

    static List<Entry> trimBounded(List<Entry> entries) {
        List<Entry> copy = new ArrayList<>(entries);
        while (copy.size() > MAX_ENTRIES) {
            copy.remove(copy.size() - 1);
        }
        return copy;
    }

    static String formatRelayNote(Entry entry) {
        StringBuilder out = new StringBuilder("[Trip ").append(entry.timestampIso).append("] ");
        if (!entry.note.isEmpty()) {
            out.append("Note: ").append(entry.note).append(" | ");
        }
        if (!entry.labels.isEmpty()) {
            out.append("Labels: ").append(entry.labels).append(" | ");
        }
        if (!entry.ocrText.isEmpty()) {
            String snippet = entry.ocrText.replace('\n', ' ').trim();
            if (snippet.length() > 160) {
                snippet = snippet.substring(0, 160) + "…";
            }
            out.append("OCR: \"").append(snippet).append("\" | ");
        }
        if (!entry.paletteSummary.isEmpty()) {
            out.append(entry.paletteSummary.replace('\n', ' ')).append(" | ");
        }
        if (!entry.deviceAiDescription.isEmpty()) {
            out.append("Device AI: ").append(entry.deviceAiDescription).append(" | ");
        }
        if (!entry.cloudDescription.isEmpty()) {
            out.append("Online Cloud: ").append(entry.cloudDescription).append(" | ");
        }
        String text = out.toString().trim();
        if (text.endsWith("|")) {
            text = text.substring(0, text.length() - 1).trim();
        }
        return text;
    }

    static String formatExport(List<Entry> entries) {
        if (entries == null || entries.isEmpty()) {
            return "Zoe Trip Journal is empty. Save sightings explicitly from Guided Vision.";
        }
        StringBuilder out = new StringBuilder("Zoe Trip Field Journal · ")
                .append(entries.size())
                .append(" explicitly saved sighting(s)\n")
                .append("Private on-device observations; OCR/labels remain separate from AI descriptions.\n\n");
        for (int i = 0; i < entries.size(); i++) {
            Entry e = entries.get(i);
            out.append('#').append(i + 1).append(" · ").append(e.timestampIso);
            if (e.syncedToRelay) {
                out.append(" [Synced]");
            }
            out.append('\n');
            if (!e.note.isEmpty()) {
                out.append("Note: ").append(e.note).append('\n');
            }
            if (!e.paletteSummary.isEmpty()) {
                out.append(e.paletteSummary).append('\n');
            }
            if (!e.ocrText.isEmpty()) {
                out.append("OCR: ").append(e.ocrText).append('\n');
            }
            if (!e.labels.isEmpty()) {
                out.append("Labels: ").append(e.labels).append('\n');
            }
            if (!e.deviceAiDescription.isEmpty()) {
                out.append("Device AI: ").append(e.deviceAiDescription).append('\n');
            }
            if (!e.cloudDescription.isEmpty()) {
                out.append("Online Cloud (Gemini): ").append(e.cloudDescription).append('\n');
            }
            out.append('\n');
        }
        return out.toString();
    }

    static synchronized List<Entry> load(Context context) {
        File index = new File(context.getFilesDir(), INDEX_FILE);
        if (!index.isFile()) {
            return Collections.emptyList();
        }
        try {
            byte[] bytes = java.nio.file.Files.readAllBytes(index.toPath());
            return fromJson(new String(bytes, StandardCharsets.UTF_8));
        } catch (IOException | IllegalArgumentException error) {
            return Collections.emptyList();
        }
    }

    static synchronized Entry saveEntry(Context context, Entry entry, Bitmap optionalThumb) {
        String thumbName = entry.thumbFilename;
        if (optionalThumb != null && thumbName.isEmpty()) {
            thumbName = entry.id + ".jpg";
            File dir = new File(context.getFilesDir(), THUMB_DIR);
            if (!dir.exists()) {
                dir.mkdirs();
            }
            File file = new File(dir, thumbName);
            int targetW = Math.min(360, optionalThumb.getWidth());
            int targetH = Math.max(1, Math.round(optionalThumb.getHeight() * (targetW / (float) Math.max(1, optionalThumb.getWidth()))));
            Bitmap scaled = (optionalThumb.getWidth() == targetW && optionalThumb.getHeight() == targetH)
                    ? optionalThumb
                    : Bitmap.createScaledBitmap(optionalThumb, targetW, targetH, true);
            try (ByteArrayOutputStream baos = new ByteArrayOutputStream();
                 FileOutputStream fos = new FileOutputStream(file)) {
                scaled.compress(Bitmap.CompressFormat.JPEG, 82, baos);
                fos.write(baos.toByteArray());
            } catch (IOException ignored) {
                thumbName = "";
            } finally {
                if (scaled != optionalThumb) {
                    scaled.recycle();
                }
            }
        }
        Entry stored = new Entry(entry.id, entry.timestampIso, entry.note, entry.ocrText, entry.labels,
                entry.paletteSummary, entry.deviceAiDescription, entry.cloudDescription,
                thumbName, entry.syncedToRelay);
        List<Entry> current = new ArrayList<>(load(context));
        current.add(0, stored);
        while (current.size() > MAX_ENTRIES) {
            Entry evicted = current.remove(current.size() - 1);
            deleteThumb(context, evicted);
        }
        writeAll(context, current);
        return stored;
    }

    static synchronized void updateNote(Context context, String id, String note) {
        List<Entry> current = new ArrayList<>(load(context));
        for (int i = 0; i < current.size(); i++) {
            if (current.get(i).id.equals(id)) {
                current.set(i, current.get(i).withNote(note));
                break;
            }
        }
        writeAll(context, current);
    }

    static synchronized void markSynced(Context context, String id) {
        List<Entry> current = new ArrayList<>(load(context));
        for (int i = 0; i < current.size(); i++) {
            if (current.get(i).id.equals(id)) {
                current.set(i, current.get(i).withSynced(true));
                break;
            }
        }
        writeAll(context, current);
    }

    static synchronized void clear(Context context) {
        List<Entry> current = load(context);
        for (Entry entry : current) {
            deleteThumb(context, entry);
        }
        File dir = new File(context.getFilesDir(), THUMB_DIR);
        File[] files = dir.listFiles();
        if (files != null) {
            for (File file : files) {
                file.delete();
            }
        }
        File index = new File(context.getFilesDir(), INDEX_FILE);
        if (index.exists()) {
            index.delete();
        }
    }

    static File thumbnailFile(Context context, Entry entry) {
        if (entry == null || entry.thumbFilename.isEmpty()) {
            return null;
        }
        File file = new File(new File(context.getFilesDir(), THUMB_DIR), entry.thumbFilename);
        return file.isFile() ? file : null;
    }

    private static void deleteThumb(Context context, Entry entry) {
        File file = thumbnailFile(context, entry);
        if (file != null) {
            file.delete();
        }
    }

    private static void writeAll(Context context, List<Entry> entries) {
        File index = new File(context.getFilesDir(), INDEX_FILE);
        try (FileOutputStream fos = new FileOutputStream(index)) {
            fos.write(toJson(entries).getBytes(StandardCharsets.UTF_8));
        } catch (IOException ignored) {
        }
    }
}
