package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.util.Arrays;
import java.util.List;

public class ZappLayoutStoreTest {
    @Test
    public void normalizesDeduplicatesAndAppendsMissingDefaults() {
        List<String> normalized = ZappLayoutStore.normalizeOrder(
                Arrays.asList("safeconvert", "invalid_id", "kit", "safeconvert"));
        assertEquals("safeconvert", normalized.get(0));
        assertEquals("kit", normalized.get(1));
        assertEquals(ZappLayoutStore.DEFAULT_ORDER.size(), normalized.size());
    }

    @Test
    public void supportsPinToTopMoveUpMoveDownAndSerialization() {
        List<String> order = ZappLayoutStore.moveToTop(ZappLayoutStore.DEFAULT_ORDER, "safeconvert");
        assertEquals("safeconvert", order.get(0));

        order = ZappLayoutStore.moveToTop(order, "kit");
        assertEquals("kit", order.get(0));
        assertEquals("safeconvert", order.get(1));

        order = ZappLayoutStore.moveDown(order, "kit");
        assertEquals("safeconvert", order.get(0));
        assertEquals("kit", order.get(1));

        order = ZappLayoutStore.moveUp(order, "kit");
        assertEquals("kit", order.get(0));

        List<String> roundTrip = ZappLayoutStore.deserialize(ZappLayoutStore.serialize(order));
        assertEquals(order, roundTrip);
    }
}
