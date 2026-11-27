package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class AcousticRangingTest {
    @Test
    public void syntheticEchoHasCorrectLagAndDistance() {
        int sampleRate = 48_000;
        short[] reference = AcousticRanging.chirp(sampleRate, 2000, 0.020, 0.08);
        short[] recorded = new short[sampleRate];
        add(recorded, reference, 4800, 1.0);
        add(recorded, reference, 9600, 0.5);
        AcousticRanging.Measurement result = AcousticRanging.analyze(recorded, reference, sampleRate);
        assertEquals(0.1, result.directLagSeconds, 0.002);
        assertEquals(0.1, result.echoLagSeconds, 0.002);
        assertEquals(17.15, result.candidateDistanceMeters, 0.1);
        assertTrue(result.correlation >= 0.25);
    }

    @Test
    public void silenceHasNoDistanceCandidate() {
        short[] reference = AcousticRanging.chirp(48_000, 2000, 0.020, 0.08);
        AcousticRanging.Measurement result = AcousticRanging.analyze(new short[48_000], reference, 48_000);
        assertNull(result.directLagSeconds);
        assertNull(result.candidateDistanceMeters);
    }

    private static void add(short[] destination, short[] source, int offset, double gain) {
        for (int index = 0; index < source.length; index++) {
            destination[offset + index] += (short) Math.round(source[index] * gain);
        }
    }
}
