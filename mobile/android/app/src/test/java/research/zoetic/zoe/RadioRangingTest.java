package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import org.junit.Test;

public class RadioRangingTest {
    @Test
    public void pathLossModelIsExplicitAndCorrect() {
        assertEquals(1.0, RadioRanging.pathLossDistance(-50, -50, 2.0), 1e-12);
        assertEquals(10.0, RadioRanging.pathLossDistance(-50, -70, 2.0), 1e-12);
        assertEquals(0.1, RadioRanging.pathLossDistance(-50, -30, 2.0), 1e-12);
    }

    @Test
    public void invalidExponentIsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> RadioRanging.pathLossDistance(-50, -60, 0));
    }
}
