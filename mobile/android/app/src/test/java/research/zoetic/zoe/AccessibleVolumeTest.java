package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public class AccessibleVolumeTest {
    private static final double[] EXAMPLE = {0.70, 0.20, 0.08, 0.02};

    @Test
    public void workedExampleUsesStrictThreshold() {
        AccessibleVolume.Result result = AccessibleVolume.measure(EXAMPLE, 0.05);
        assertEquals(3, result.accessible);
        assertEquals(1, result.complement);
        assertEquals(0.75, result.normalized, 0.0);
    }

    @Test
    public void equalityIsExcluded() {
        assertEquals(1, AccessibleVolume.measure(EXAMPLE, 0.20).accessible);
        assertEquals(4, AccessibleVolume.measure(new double[]{0.25, 0.25, 0.25, 0.25}, 0.0).accessible);
        assertEquals(0, AccessibleVolume.measure(new double[]{0.25, 0.25, 0.25, 0.25}, 1.0).accessible);
        assertEquals(1, AccessibleVolume.measure(new double[]{1.0, 0.0, 0.0}, 0.0).accessible);
    }

    @Test
    public void parserAcceptsCommaAndWhitespace() {
        assertEquals(4, AccessibleVolume.parse("0.70, 0.20 0.08,0.02").length);
    }

    @Test
    public void invalidDistributionsAreRejected() {
        assertThrows(IllegalArgumentException.class, () -> AccessibleVolume.measure(new double[]{0.5, 0.4}, 0.05));
        assertThrows(IllegalArgumentException.class, () -> AccessibleVolume.measure(new double[]{Double.NaN, 1.0}, 0.05));
        assertThrows(IllegalArgumentException.class, () -> AccessibleVolume.measure(new double[]{-0.1, 1.1}, 0.05));
        assertThrows(IllegalArgumentException.class, () -> AccessibleVolume.measure(EXAMPLE, -0.1));
        assertThrows(IllegalArgumentException.class, () -> AccessibleVolume.parse("not-a-number"));
        assertThrows(IllegalArgumentException.class, () -> AccessibleVolume.parse(""));
    }
}
