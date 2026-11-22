package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public class NetworkSpeedTestTest {
    @Test
    public void rateUsesBitsAndActualElapsedTime() {
        assertEquals(8.0, NetworkSpeedTest.megabitsPerSecond(1_000_000, 1_000_000_000L), 1e-12);
        assertEquals(1.0, NetworkSpeedTest.megabitsPerSecond(125_000, 1_000_000_000L), 1e-12);
        assertThrows(IllegalArgumentException.class,
                () -> NetworkSpeedTest.megabitsPerSecond(1, 0));
    }
}
