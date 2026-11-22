package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

public class TripJournalStoreTest {
    @Test
    public void roundTripsEntriesAndFormatsRelayAndExport() {
        TripJournalStore.Entry entry = new TripJournalStore.Entry(
                "trip-1",
                "2026-11-21 16:40:00",
                "Stained glass inside old Porsche",
                "PURPLE PHOENIX",
                "Art 92% · Car 88%",
                "Light 38% · Contrast 42% · Warm light\nPalette: Amber #D49030",
                "A dark car illuminated from inside.",
                "",
                "trip-1.jpg",
                false);
        String json = TripJournalStore.toJson(Collections.singletonList(entry));
        List<TripJournalStore.Entry> decoded = TripJournalStore.fromJson(json);
        assertEquals(1, decoded.size());
        assertEquals("trip-1", decoded.get(0).id);
        assertEquals("Stained glass inside old Porsche", decoded.get(0).note);
        assertFalse(decoded.get(0).syncedToRelay);

        String relayNote = TripJournalStore.formatRelayNote(entry);
        assertTrue(relayNote.contains("PURPLE PHOENIX"));
        assertTrue(relayNote.contains("Stained glass inside old Porsche"));

        String exported = TripJournalStore.formatExport(decoded);
        assertTrue(exported.contains("Zoe Trip Field Journal"));
        assertTrue(exported.contains("Amber #D49030"));
    }

    @Test
    public void boundsRetainedEntriesToForty() {
        List<TripJournalStore.Entry> many = new ArrayList<>();
        for (int i = 0; i < TripJournalStore.MAX_ENTRIES + 5; i++) {
            many.add(new TripJournalStore.Entry(
                    "id-" + i, "2026-11-21 12:00:00", "Note " + i,
                    "", "", "", "", "", "", false));
        }
        List<TripJournalStore.Entry> bounded = TripJournalStore.trimBounded(many);
        assertEquals(TripJournalStore.MAX_ENTRIES, bounded.size());
        assertEquals("id-0", bounded.get(0).id);
    }
}
