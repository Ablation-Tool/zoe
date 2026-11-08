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

    String exportText() {
        List<Transaction> transactions = history();
        StringBuilder text = new StringBuilder()
                .append("Zoe Cell · simulated protocol session\n")
                .append("Native Android behavioral model; no hardware, SIM, storage, or network used.\n")
                .append("No external action authorized. This is not physical-card evidence.\n")
                .append("Strict p > tau; equality excluded. Unsigned Q0.15 probabilities sum to 32768.\n")
                .append("Original equation: Nicholas Michael Kloster alone, March 6, 2026.\n")
                .append("Retained transactions: ").append(transactions.size())
                .append(" of an in-memory maximum of 12; oldest entries are evicted.\n");
        if (transactions.isEmpty()) {
            text.append("\nNo transactions.\n");
            return text.toString();
        }
        for (Transaction transaction : transactions) {
            text.append("\n#").append(transaction.ordinal())
                    .append("\nrequest: ").append(CellCodec.hex(transaction.request()))
                    .append("\nresponse: ").append(CellCodec.hex(transaction.response()))
                    .append("\nstatus: ").append(String.format(Locale.US, "0x%04X", transaction.status()))
                    .append('\n');
        }
        return text.toString();
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
