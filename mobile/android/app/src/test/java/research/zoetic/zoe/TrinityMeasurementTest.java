package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public final class TrinityMeasurementTest {
    @Test
    public void sharedFixturesRemainStrict() {
        double[] example = {0.70, 0.20, 0.08, 0.02};
        assertEquals(3, new TrinityMeasurement(example, 0.05).result().accessible);
        assertEquals(1, new TrinityMeasurement(example, 0.20).result().accessible);
        assertEquals(0, new TrinityMeasurement(new double[]{0.25, 0.25, 0.25, 0.25}, 1).result().accessible);
    }

    @Test
    public void requestJsonIsDeterministicAndBounded() {
        String json = TrinityMeasurement.measureJson("android", new double[]{0.5, 0.5}, 0.5);
        assertEquals("{\"source\":\"android\",\"probabilities\":[0.5,0.5],\"tau\":0.5}", json);
        assertEquals("{\"source\":\"laptop\"}", TrinityMeasurement.resetJson("laptop"));
    }

    @Test
    public void invalidInputsAndSourcesAreRejected() {
        assertThrows(() -> new TrinityMeasurement(new double[65], 0.5));
        assertThrows(() -> new TrinityMeasurement(new double[]{0.5, 0.4}, 0.5));
        assertThrows(() -> new TrinityMeasurement(new double[]{Double.NaN}, 0.5));
        assertThrows(() -> TrinityMeasurement.measureJson("tiny", new double[]{1}, 0));
        assertThrows(() -> TrinityMeasurement.resetJson("unknown"));
    }

    @Test
    public void distributionUsesDefensiveCopies() {
        double[] values = {0.5, 0.5};
        TrinityMeasurement measurement = new TrinityMeasurement(values, 0.25);
        values[0] = 0;
        double[] copy = measurement.probabilities();
        copy[1] = 0;
        assertEquals(2, measurement.result().accessible);
        assertTrue(measurement.probabilities()[0] == 0.5 && measurement.probabilities()[1] == 0.5);
    }

    private static void assertThrows(Runnable action) {
        try {
            action.run();
            throw new AssertionError("Expected invalid input to be rejected");
        } catch (IllegalArgumentException expected) {
        }
    }
}
