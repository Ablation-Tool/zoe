package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Rule;
import org.junit.Test;
import org.junit.rules.TemporaryFolder;

import java.io.File;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;

public class SafeEvidenceStoreTest {
    @Rule
    public TemporaryFolder temp = new TemporaryFolder();

    @Test
    public void computesStandardSha256Hex() {
        assertEquals(
                "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
                SafeEvidenceStore.sha256Hex("abc".getBytes(StandardCharsets.UTF_8)));
    }

    @Test
    public void rejectsPathTraversalAndUnsafeFileNames() {
        assertFalse(SafeEvidenceStore.isSafeFileName(null));
        assertFalse(SafeEvidenceStore.isSafeFileName(""));
        assertFalse(SafeEvidenceStore.isSafeFileName("../secret.mp4"));
        assertFalse(SafeEvidenceStore.isSafeFileName("sub/clip.m4a"));
        assertFalse(SafeEvidenceStore.isSafeFileName("a\\b.m4a"));
        assertTrue(SafeEvidenceStore.isSafeFileName("aud_1700000000.m4a"));
        assertTrue(SafeEvidenceStore.isSafeFileName("vid_1700000000.mp4"));
    }

    @Test
    public void storesTextsAndMediaWithIntegrityHashesAndDeletesPhysicalFiles() throws Exception {
        File vault = temp.newFolder("uc_vault");

        SafeEvidenceStore.Entry textEntry = SafeEvidenceStore.addText(vault, "Yelled threats in hallway");
        assertNotNull(textEntry);
        assertEquals("text", textEntry.type);
        assertTrue(textEntry.timestampUtc.endsWith("Z"));
        assertEquals(
                SafeEvidenceStore.sha256Hex("Yelled threats in hallway".getBytes(StandardCharsets.UTF_8)),
                textEntry.sha256);

        File clip = new File(vault, "aud_test.m4a");
        byte[] audioBytes = new byte[]{1, 2, 3, 4, 5, 6};
        try (FileOutputStream out = new FileOutputStream(clip)) {
            out.write(audioBytes);
        }
        SafeEvidenceStore.Entry audioEntry = SafeEvidenceStore.addMedia(
                vault, "audio", clip, "audio/mp4", "Audio recording", 4);
        assertNotNull(audioEntry);
        assertEquals("audio", audioEntry.type);
        assertEquals(6L, audioEntry.sizeBytes);
        assertEquals(4, audioEntry.durationSec);
        assertEquals(SafeEvidenceStore.sha256Hex(audioBytes), audioEntry.sha256);
        assertNotNull(SafeEvidenceStore.resolveMediaFile(vault, audioEntry));

        List<SafeEvidenceStore.Entry> loaded = SafeEvidenceStore.load(vault);
        assertEquals(2, loaded.size());
        assertEquals(audioEntry.id, loaded.get(0).id);
        assertEquals(textEntry.id, loaded.get(1).id);

        String export = SafeEvidenceStore.formatExportText(loaded);
        assertTrue(export.contains("SHA-256: " + audioEntry.sha256));
        assertTrue(export.contains("Yelled threats in hallway"));
        assertTrue(export.contains(textEntry.timestampUtc));

        assertTrue(SafeEvidenceStore.deleteEntry(vault, audioEntry.id));
        assertFalse(clip.exists());
        assertEquals(1, SafeEvidenceStore.load(vault).size());

        SafeEvidenceStore.clearAll(vault);
        assertTrue(SafeEvidenceStore.load(vault).isEmpty());
        assertNull(SafeEvidenceStore.resolveMediaFile(vault, audioEntry));
    }
}
