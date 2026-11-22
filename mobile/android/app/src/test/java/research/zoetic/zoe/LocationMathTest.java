package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public class LocationMathTest {
    @Test
    public void zeroAndOneDegreeDistancesAreCorrect() {
        assertEquals(0, LocationMath.haversineMeters(40, -73, 40, -73), 1e-9);
        assertEquals(111195, LocationMath.haversineMeters(0, 0, 1, 0), 100);
        assertEquals(111195, LocationMath.haversineMeters(0, 0, 0, 1), 100);
    }

    @Test
    public void invalidCoordinatesAreRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> LocationMath.haversineMeters(91, 0, 0, 0));
    }
}
