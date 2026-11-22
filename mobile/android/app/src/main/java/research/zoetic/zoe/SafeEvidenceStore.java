package research.zoetic.zoe;

import android.content.Context;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.TimeZone;
import java.util.UUID;

final class SafeEvidenceStore {
    static final String VAULT_DIR_NAME = "uc_vault";
    private static final String INDEX_FILE = "index.json";
    static final int MAX_ENTRIES = 50;
    static final int MAX_NOTE_CHARS = 2000;
    private static final Object VAULT_LOCK = new Object();

    private SafeEvidenceStore() {
    }

    static final class Entry {
        final String id;
        final String type;
        final String timestampUtc;
        final String note;
        final String fileName;
        final String mimeType;
        final long sizeBytes;
        final int durationSec;
        final String sha256;

        Entry(String id, String type, String timestampUtc, String note, String fileName,
              String mimeType, long sizeBytes, int durationSec, String sha256) {
            this.id = id == null ? "" : id;
            this.type = type == null ? "text" : type;
            this.timestampUtc = timestampUtc == null ? "" : timestampUtc;
            this.note = note == null ? "" : note;
            this.fileName = fileName == null ? "" : fileName;
            this.mimeType = mimeType == null ? "" : mimeType;
            this.sizeBytes = Math.max(0L, sizeBytes);
            this.durationSec = Math.max(0, durationSec);
            this.sha256 = sha256 == null ? "" : sha256;
        }
    }

    static File vaultDir(Context context) {
        return new File(context.getFilesDir(), VAULT_DIR_NAME);
    }

    static boolean isSafeFileName(String name) {
        return name != null
                && !name.isEmpty()
                && name.length() <= 128
                && !name.contains("..")
                && name.matches("[A-Za-z0-9._-]+");
    }

    static String nowUtcIso() {
        SimpleDateFormat fmt = new SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US);
        fmt.setTimeZone(TimeZone.getTimeZone("UTC"));
        return fmt.format(new Date());
    }

    static String newId() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 12);
    }

    static String sha256Hex(byte[] data) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            if (data != null) {
                digest.update(data);
            }
            return toHex(digest.digest());
        } catch (NoSuchAlgorithmException error) {
            throw new IllegalStateException("SHA-256 unavailable", error);
        }
    }

    static String sha256File(File file) {
        if (file == null || !file.isFile()) {
            return "";
        }
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] buf = new byte[8192];
            try (FileInputStream in = new FileInputStream(file)) {
                int n;
                while ((n = in.read(buf)) >= 0) {
                    if (n > 0) {
                        digest.update(buf, 0, n);
                    }
                }
            }
            return toHex(digest.digest());
        } catch (IOException | NoSuchAlgorithmException error) {
            return "";
        }
    }

    private static String toHex(byte[] bytes) {
        StringBuilder out = new StringBuilder(bytes.length * 2);
        for (byte b : bytes) {
            out.append(Character.forDigit((b >>> 4) & 0x0f, 16));
            out.append(Character.forDigit(b & 0x0f, 16));
        }
        return out.toString();
    }

    static List<Entry> load(File vaultDir) {
        synchronized (VAULT_LOCK) {
            List<Entry> out = new ArrayList<>();
            if (vaultDir == null) {
                return out;
            }
            File idx = new File(vaultDir, INDEX_FILE);
            if (!idx.isFile()) {
                return out;
            }
            String json = readUtf8(idx);
            if (json.isBlank()) {
                return out;
            }
            try {
                List<Object> arr = MiniJson.parseArray(json);
                for (Object item : arr) {
                    Map<String, Object> m = MiniJson.asObject(item);
                    if (m == null) {
                        continue;
                    }
                    Object sizeObj = m.get("sizeBytes");
                    long size = sizeObj instanceof Number ? ((Number) sizeObj).longValue() : 0L;
                    out.add(new Entry(
                            MiniJson.asString(m, "id", ""),
                            MiniJson.asString(m, "type", "text"),
                            MiniJson.asString(m, "timestampUtc", ""),
                            MiniJson.asString(m, "note", ""),
                            MiniJson.asString(m, "fileName", ""),
                            MiniJson.asString(m, "mimeType", ""),
                            size,
                            MiniJson.asInt(m, "durationSec", 0),
                            MiniJson.asString(m, "sha256", "")));
                    if (out.size() >= MAX_ENTRIES) {
                        break;
                    }
                }
            } catch (IllegalArgumentException ignored) {
            }
            return out;
        }
    }

    static String loadJson(File vaultDir) {
        return toJson(load(vaultDir));
    }

    static Entry addText(File vaultDir, String rawNote) {
        String clean = sanitizeNote(rawNote);
        if (vaultDir == null || clean.isEmpty()) {
            return null;
        }
        byte[] bytes = clean.getBytes(StandardCharsets.UTF_8);
        Entry entry = new Entry(
                newId(),
                "text",
                nowUtcIso(),
                clean,
                "",
                "text/plain",
                bytes.length,
                0,
                sha256Hex(bytes));
        synchronized (VAULT_LOCK) {
            List<Entry> list = load(vaultDir);
            list.add(0, entry);
            trimAndPersist(vaultDir, list);
        }
        return entry;
    }

    static Entry addMedia(File vaultDir, String type, File mediaFile, String mimeType,
                          String rawNote, int durationSec) {
        if (vaultDir == null || mediaFile == null || !mediaFile.isFile()) {
            return null;
        }
        String fileName = mediaFile.getName();
        if (!isSafeFileName(fileName) || !isInsideDir(vaultDir, mediaFile)) {
            return null;
        }
        String safeType = "video".equals(type) ? "video" : "audio";
        String cleanNote = sanitizeNote(rawNote);
        String hash = sha256File(mediaFile);
        Entry entry = new Entry(
                newId(),
                safeType,
                nowUtcIso(),
                cleanNote,
                fileName,
                mimeType == null ? ("video".equals(safeType) ? "video/mp4" : "audio/mp4") : mimeType,
                mediaFile.length(),
                Math.max(0, durationSec),
                hash);
        synchronized (VAULT_LOCK) {
            List<Entry> list = load(vaultDir);
            list.add(0, entry);
            trimAndPersist(vaultDir, list);
        }
        return entry;
    }

    static boolean deleteEntry(File vaultDir, String id) {
        if (vaultDir == null || id == null || id.isEmpty()) {
            return false;
        }
        synchronized (VAULT_LOCK) {
            List<Entry> list = load(vaultDir);
            boolean removed = false;
            List<Entry> kept = new ArrayList<>();
            for (Entry e : list) {
                if (!removed && id.equals(e.id)) {
                    removed = true;
                    File f = resolveMediaFile(vaultDir, e);
                    if (f != null && f.exists()) {
                        //noinspection ResultOfMethodCallIgnored
                        f.delete();
                    }
                } else {
                    kept.add(e);
                }
            }
            if (removed) {
                trimAndPersist(vaultDir, kept);
            }
            return removed;
        }
    }

    static void clearAll(File vaultDir) {
        if (vaultDir == null) {
            return;
        }
        synchronized (VAULT_LOCK) {
            File[] files = vaultDir.listFiles();
            if (files != null) {
                for (File f : files) {
                    if (f.isFile()) {
                        //noinspection ResultOfMethodCallIgnored
                        f.delete();
                    }
                }
            }
        }
    }

    static Entry findById(File vaultDir, String id) {
        if (vaultDir == null || id == null || id.isEmpty()) {
            return null;
        }
        for (Entry e : load(vaultDir)) {
            if (id.equals(e.id)) {
                return e;
            }
        }
        return null;
    }

    static File resolveMediaFile(File vaultDir, Entry entry) {
        if (vaultDir == null || entry == null || !isSafeFileName(entry.fileName)) {
            return null;
        }
        File candidate = new File(vaultDir, entry.fileName);
        if (!isInsideDir(vaultDir, candidate) || !candidate.isFile()) {
            return null;
        }
        return candidate;
    }

    static String toJson(List<Entry> entries) {
        List<Object> arr = new ArrayList<>();
        if (entries != null) {
            for (Entry e : entries) {
                Map<String, Object> m = new LinkedHashMap<>();
                m.put("id", e.id);
                m.put("type", e.type);
                m.put("timestampUtc", e.timestampUtc);
                m.put("note", e.note);
                m.put("fileName", e.fileName);
                m.put("mimeType", e.mimeType);
                m.put("sizeBytes", e.sizeBytes);
                m.put("durationSec", e.durationSec);
                m.put("sha256", e.sha256);
                arr.add(m);
            }
        }
        return MiniJson.stringify(arr);
    }

    static String formatExportText(List<Entry> entries) {
        if (entries == null || entries.isEmpty()) {
            return "Safety Log is empty.";
        }
        StringBuilder out = new StringBuilder();
        out.append("PRIVATE SAFETY LOG · ").append(entries.size()).append(" ENTRY(S)\n\n");
        for (int i = 0; i < entries.size(); i++) {
            Entry e = entries.get(i);
            out.append('#').append(i + 1)
                    .append(" · ").append(e.type.toUpperCase(Locale.US))
                    .append(" · ").append(e.timestampUtc).append('\n');
            if (!e.note.isEmpty()) {
                out.append("Note: ").append(e.note).append('\n');
            }
            if (!e.fileName.isEmpty()) {
                out.append("File: ").append(e.fileName)
                        .append(" (").append(e.durationSec).append(" s, ")
                        .append(e.sizeBytes).append(" bytes)\n");
            } else {
                out.append("Size: ").append(e.sizeBytes).append(" bytes\n");
            }
            if (!e.sha256.isEmpty()) {
                out.append("SHA-256: ").append(e.sha256).append('\n');
            }
            out.append('\n');
        }
        out.append("Note: UTC timestamps and SHA-256 digests document local integrity on this device; they do not replace an independent legal notary.");
        return out.toString().trim();
    }

    private static String sanitizeNote(String rawNote) {
        if (rawNote == null) {
            return "";
        }
        String clean = rawNote.trim();
        if (clean.length() > MAX_NOTE_CHARS) {
            return clean.substring(0, MAX_NOTE_CHARS);
        }
        return clean;
    }

    private static boolean isInsideDir(File dir, File candidate) {
        try {
            String dirPath = dir.getCanonicalPath();
            if (!dirPath.endsWith(File.separator)) {
                dirPath = dirPath + File.separator;
            }
            String candidatePath = candidate.getCanonicalPath();
            return candidatePath.startsWith(dirPath);
        } catch (IOException error) {
            return false;
        }
    }

    private static void trimAndPersist(File vaultDir, List<Entry> list) {
        while (list.size() > MAX_ENTRIES) {
            Entry dropped = list.remove(list.size() - 1);
            File f = resolveMediaFile(vaultDir, dropped);
            if (f != null && f.exists()) {
                //noinspection ResultOfMethodCallIgnored
                f.delete();
            }
        }
        if (!vaultDir.exists()) {
            //noinspection ResultOfMethodCallIgnored
            vaultDir.mkdirs();
        }
        File idx = new File(vaultDir, INDEX_FILE);
        writeUtf8(idx, toJson(list));
    }

    private static String readUtf8(File file) {
        try (FileInputStream in = new FileInputStream(file);
             ByteArrayOutputStream out = new ByteArrayOutputStream()) {
            byte[] buf = new byte[4096];
            int n;
            while ((n = in.read(buf)) >= 0) {
                out.write(buf, 0, n);
            }
            return out.toString(StandardCharsets.UTF_8.name());
        } catch (IOException error) {
            return "";
        }
    }

    private static void writeUtf8(File file, String content) {
        try (FileOutputStream out = new FileOutputStream(file)) {
            out.write(content.getBytes(StandardCharsets.UTF_8));
        } catch (IOException ignored) {
        }
    }
}
