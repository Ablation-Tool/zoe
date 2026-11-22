package research.zoetic.zoe;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;
import static org.junit.Assert.fail;

import org.junit.Test;

public final class CellSessionTest {
    private final CellSession session = new CellSession();

    @Test
    public void historyIsBoundedAndReplayIsDeterministic() {
        for (int index = 0; index < 15; index++) {
            session.transact(CellCodec.infoRequest());
        }
        assertEquals(12, session.history().size());
        assertEquals(4, session.history().get(0).ordinal());
        CellSession.Transaction last = session.history().get(11);
        CellSession.Transaction replay = session.replay();
        assertEquals(16, replay.ordinal());
        assertArrayEquals(last.request(), replay.request());
        assertArrayEquals(last.response(), replay.response());
        assertEquals(12, session.history().size());
    }

    @Test
    public void transactionsUseDefensiveCopies() {
        byte[] request = CellCodec.infoRequest();
        CellSession.Transaction transaction = session.transact(request);
        request[1] = 0x02;
        assertEquals(1, transaction.request()[1]);
        byte[] requestCopy = transaction.request();
        requestCopy[1] = 0x02;
        assertEquals(1, transaction.request()[1]);
        byte[] responseCopy = transaction.response();
        responseCopy[0] = 0x7f;
        assertEquals(1, transaction.response()[0]);
        assertArrayEquals(transaction.response(), session.replay().response());
    }

    @Test
    public void exportPreservesBytesAndTheSimulationBoundary() {
        session.transact(CellCodec.infoRequest());
        CellCodec.EncodedMeasurement measurement = CellCodec.encode(
                new double[]{0.70, 0.20, 0.08, 0.02}, 0.05);
        session.transact(measurement.apdu);
        String export = session.exportText();
        assertTrue(export.contains("request: 80010000"));
        assertTrue(export.contains("request: 800200000A0666599A199A0A3D028F"));
        assertTrue(export.contains("response: 00030001000406669000"));
        assertTrue(export.contains("not physical-card evidence"));
        assertTrue(export.contains("Nicholas Michael Kloster alone, March 6, 2026"));
        assertTrue(export.contains("Retained transactions: 2"));
    }

    @Test
    public void emptyExportInventsNoMeasurements() {
        String export = session.exportText();
        assertTrue(export.contains("No transactions."));
        assertTrue(export.contains("Retained transactions: 0"));
    }

    @Test
    public void resetClearsHistoryAndReplay() {
        session.transact(CellCodec.infoRequest());
        session.reset();
        assertTrue(session.history().isEmpty());
        assertNull(session.replay());
    }

    @Test
    public void hexadecimalConsoleIsBoundedAndValidated() {
        assertArrayEquals(CellCodec.infoRequest(), CellCodec.parseCommand("80 01:00 00"));
        assertArrayEquals(CellCodec.infoRequest(), CellCodec.parseCommand("80010000"));
        assertEquals("80010000", CellCodec.hex(CellCodec.infoRequest()));
        assertThrows(() -> CellCodec.parseCommand(""));
        assertThrows(() -> CellCodec.parseCommand("0"));
        assertThrows(() -> CellCodec.parseCommand("GG"));
        assertThrows(() -> CellCodec.parseCommand("80".repeat(136)));
    }

    @Test
    public void errorResponsesRemainInspectableAndReplayable() {
        CellSession.Transaction rejected = session.transact(CellCodec.parseCommand("80020000"));
        assertEquals(0x6700, rejected.status());
        assertEquals(1, session.history().size());
        assertEquals(rejected.summary(), session.replay().summary().replace("#2", "#1"));
    }

    @Test
    public void nullAndOversizedRequestsCannotAllocateHistory() {
        assertThrows(() -> session.transact(null));
        assertThrows(() -> session.transact(new byte[136]));
        assertTrue(session.history().isEmpty());
        assertThrows(() -> CellCodec.status(new byte[]{0}));
    }

    @Test
    public void arbitraryCommandsFailClosedAndReplayIdentically() {
        java.util.Random random = new java.util.Random(20261107);
        for (int length = 0; length <= CellSimulator.MAX_REQUEST_BYTES; length++) {
            for (int sample = 0; sample < 32; sample++) {
                byte[] request = new byte[length];
                random.nextBytes(request);
                CellSession.Transaction transaction = session.transact(request);
                int status = transaction.status();
                assertTrue(status == 0x9000 || status == 0x6700 || status == 0x6984
                        || status == 0x6a86 || status == 0x6d00 || status == 0x6e00);
                assertTrue(transaction.response().length <= 16);
                assertArrayEquals(transaction.response(), session.replay().response());
                assertTrue(session.history().size() <= 12);
            }
        }
    }

    @Test
    public void hostileTextNeverEscapesTheBoundedCodec() {
        java.util.Random random = new java.util.Random(0x5a4f45);
        String alphabet = "0123456789abcdefABCDEFxyz :-\t";
        for (int sample = 0; sample < 1000; sample++) {
            int length = random.nextInt(601);
            StringBuilder input = new StringBuilder(length);
            for (int index = 0; index < length; index++) {
                input.append(alphabet.charAt(random.nextInt(alphabet.length())));
            }
            try {
                byte[] command = CellCodec.parseCommand(input.toString());
                assertTrue(command.length <= CellSimulator.MAX_REQUEST_BYTES);
                assertArrayEquals(command, CellCodec.parseCommand(CellCodec.hex(command)));
            } catch (IllegalArgumentException expected) {
            }
        }
        assertThrows(() -> CellCodec.parseCommand("80".repeat(1_000_000)));
    }

    private static void assertThrows(Runnable action) {
        try {
            action.run();
            fail("Expected invalid input to be rejected");
        } catch (IllegalArgumentException expected) {
        }
    }
}
