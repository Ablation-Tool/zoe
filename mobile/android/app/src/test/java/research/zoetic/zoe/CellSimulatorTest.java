package research.zoetic.zoe;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

public final class CellSimulatorTest {
    private final CellSimulator simulator = new CellSimulator();

    @Test
    public void informationUsesTheBoundedProtocol() {
        byte[] response = simulator.transmit(CellCodec.infoRequest());
        assertTrue(CellCodec.decodeInfo(response).startsWith("ZOE/NUCLIDE"));
        assertEquals(16, response.length);
    }

    @Test
    public void sharedFixturesPreserveStrictThreshold() {
        double[] example = {0.70, 0.20, 0.08, 0.02};
        assertEquals(3, measure(example, 0.05).accessible);
        assertEquals(1, measure(example, 0.20).accessible);
        assertEquals(4, measure(new double[]{0.25, 0.25, 0.25, 0.25}, 0).accessible);
        assertEquals(0, measure(new double[]{0.25, 0.25, 0.25, 0.25}, 1).accessible);
        assertEquals(1, measure(new double[]{1, 0, 0}, 0).accessible);
    }

    @Test
    public void maximumVectorUsesExactly135Bytes() {
        double[] probabilities = new double[64];
        for (int index = 0; index < probabilities.length; index++) {
            probabilities[index] = 1.0 / 64;
        }
        CellCodec.EncodedMeasurement encoded = CellCodec.encode(probabilities, 0);
        assertEquals(CellSimulator.MAX_REQUEST_BYTES, encoded.apdu.length);
        assertEquals(64, simulator.transmit(encoded.apdu).length == 10
                ? CellCodec.decodeMeasurement(simulator.transmit(encoded.apdu)).accessible : -1);
        assertEquals(CellCodec.SCALE, java.util.Arrays.stream(encoded.probabilities).sum());
    }

    @Test
    public void quantizationAndRepeatabilityMatch() {
        CellCodec.EncodedMeasurement first = CellCodec.encode(new double[]{0.1, 0.2, 0.3, 0.4}, 0.2);
        CellCodec.EncodedMeasurement second = CellCodec.encode(new double[]{0.1, 0.2, 0.3, 0.4}, 0.2);
        assertArrayEquals(first.apdu, second.apdu);
        assertArrayEquals(first.probabilities, second.probabilities);
        assertEquals(2, CellCodec.decodeMeasurement(simulator.transmit(first.apdu)).accessible);
    }

    @Test
    public void malformedHeadersReturnIsoStatuses() {
        assertEquals(0x6700, status(new byte[]{0}));
        assertEquals(0x6e00, status(new byte[]{0, 1, 0, 0}));
        assertEquals(0x6d00, status(new byte[]{(byte) 0x80, 0x7f, 0, 0}));
        assertEquals(0x6a86, status(new byte[]{(byte) 0x80, 1, 1, 0}));
        assertEquals(0x6700, status(new byte[]{(byte) 0x80, 2, 0, 0, 4, 0, 0, 0}));
    }

    @Test
    public void invalidDistributionsReturnDataInvalid() {
        CellCodec.EncodedMeasurement encoded = CellCodec.encode(new double[]{0.5, 0.5}, 0.5);
        byte[] invalidSum = encoded.apdu.clone();
        invalidSum[invalidSum.length - 1] = 1;
        assertEquals(0x6984, status(invalidSum));
        byte[] invalidProbability = encoded.apdu.clone();
        invalidProbability[7] = (byte) 0x80;
        invalidProbability[8] = 1;
        assertEquals(0x6984, status(invalidProbability));
        byte[] invalidTau = encoded.apdu.clone();
        invalidTau[5] = (byte) 0x80;
        invalidTau[6] = 1;
        assertEquals(0x6984, status(invalidTau));
    }

    @Test
    public void invalidInputsAndResponsesAreRejected() {
        assertThrows(() -> CellCodec.encode(new double[]{0.5, 0.4}, 0.5));
        assertThrows(() -> CellCodec.encode(new double[65], 0.5));
        assertThrows(() -> CellCodec.encode(new double[]{1}, -0.1));
        assertThrows(() -> CellCodec.decodeMeasurement(new byte[]{0, 0}));
        assertThrows(() -> CellCodec.decodeMeasurement(new byte[10]));
    }

    private CellCodec.Measurement measure(double[] probabilities, double tau) {
        return CellCodec.decodeMeasurement(simulator.transmit(CellCodec.encode(probabilities, tau).apdu));
    }

    private int status(byte[] request) {
        byte[] response = simulator.transmit(request);
        return ((response[response.length - 2] & 0xff) << 8) | (response[response.length - 1] & 0xff);
    }

    private static void assertThrows(Runnable action) {
        try {
            action.run();
            fail("Expected an invalid command or response to be rejected");
        } catch (IllegalArgumentException expected) {
        }
    }
}
