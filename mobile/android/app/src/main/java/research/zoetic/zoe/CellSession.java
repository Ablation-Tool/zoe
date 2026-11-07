package research.zoetic.zoe;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

final class CellSession {
    private static final int MAX_HISTORY = 12;
    private final ArrayDeque<Transaction> history = new ArrayDeque<>();
    private CellSimulator simulator = new CellSimulator();
    private byte[] lastRequest;
    private byte[] lastResponse;
    private int ordinal;

    Transaction transact(byte[] request) {
        if (request == null || request.length > CellSimulator.MAX_REQUEST_BYTES) {
            throw new IllegalArgumentException("APDU request must contain at most 135 bytes");
        }
        byte[] boundedRequest = request.clone();
        byte[] response = simulator.transmit(boundedRequest);
        lastRequest = boundedRequest.clone();
        lastResponse = response.clone();
        Transaction transaction = new Transaction(++ordinal, boundedRequest, response);
        history.addLast(transaction);
        if (history.size() > MAX_HISTORY) {
            history.removeFirst();
        }
        return transaction;
    }

    Transaction replay() {
        return lastRequest == null ? null : transact(lastRequest);
    }

    List<Transaction> history() {
        return Collections.unmodifiableList(new ArrayList<>(history));
    }

    void reset() {
        simulator = new CellSimulator();
        history.clear();
        lastRequest = null;
        lastResponse = null;
        ordinal = 0;
    }

    static final class Transaction {
        private final int ordinal;
        private final byte[] request;
        private final byte[] response;

        Transaction(int ordinal, byte[] request, byte[] response) {
            this.ordinal = ordinal;
            this.request = request.clone();
            this.response = response.clone();
        }

        int ordinal() {
            return ordinal;
        }

        byte[] request() {
            return request.clone();
        }

        byte[] response() {
            return response.clone();
        }

        int status() {
            return CellCodec.status(response);
        }

        String summary() {
            String instruction = request.length > 1
                    ? String.format(Locale.US, "%02X", request[1]) : "--";
            return String.format(Locale.US, "#%d · INS %s · %d B → %d B · SW %04X",
                    ordinal, instruction, request.length, response.length, status());
        }
    }
}
