package research.zoetic.zoe;

import java.util.Arrays;

final class CellSimulator {
    static final int MAX_PROBABILITIES = 64;
    static final int MAX_REQUEST_BYTES = 135;
    static final int BUDGET_BYTES = 1_900_000;
    private static final int SCALE = 1 << 15;
    private static final int SUCCESS = 0x9000;
    private static final int WRONG_LENGTH = 0x6700;
    private static final int DATA_INVALID = 0x6984;
    private static final int INCORRECT_P1P2 = 0x6a86;
    private static final int INS_NOT_SUPPORTED = 0x6d00;
    private static final int CLA_NOT_SUPPORTED = 0x6e00;
    private static final byte[] INFO = {
        1, MAX_PROBABILITIES,
        0x5a, 0x4f, 0x45, 0x2f, 0x4e, 0x55,
        0x43, 0x4c, 0x49, 0x44, 0x45,
        1
    };

    byte[] transmit(byte[] command) {
        if (command == null) {
            throw new IllegalArgumentException("APDU command is required");
        }
        if (command.length < 4) {
            return status(WRONG_LENGTH);
        }
        if (command[0] != (byte) 0x80) {
            return status(CLA_NOT_SUPPORTED);
        }
        if (command[2] != 0 || command[3] != 0) {
            return status(INCORRECT_P1P2);
        }
        if (command[1] == 0x01) {
            return command.length == 4 ? response(INFO, SUCCESS) : status(WRONG_LENGTH);
        }
        if (command[1] != 0x02) {
            return status(INS_NOT_SUPPORTED);
        }
        if (command.length < 5 || command.length > MAX_REQUEST_BYTES) {
            return status(WRONG_LENGTH);
        }
        int length = command[4] & 0xff;
        if (length < 4 || length > 130 || (length & 1) != 0 || command.length != length + 5) {
            return status(WRONG_LENGTH);
        }
        int tau = unsignedShort(command, 5);
        if (tau > SCALE) {
            return status(DATA_INVALID);
        }
        int accessible = 0;
        int count = 0;
        long total = 0;
        for (int offset = 7; offset < command.length; offset += 2) {
            int probability = unsignedShort(command, offset);
            if (probability > SCALE) {
                return status(DATA_INVALID);
            }
            total += probability;
            if (probability > tau) {
                accessible++;
            }
            count++;
        }
        if (total != SCALE) {
            return status(DATA_INVALID);
        }
        byte[] data = new byte[8];
        writeShort(data, 0, accessible);
        writeShort(data, 2, count - accessible);
        writeShort(data, 4, count);
        writeShort(data, 6, tau);
        return response(data, SUCCESS);
    }

    private static byte[] status(int status) {
        return new byte[]{(byte) (status >>> 8), (byte) status};
    }

    private static byte[] response(byte[] data, int status) {
        byte[] response = Arrays.copyOf(data, data.length + 2);
        response[response.length - 2] = (byte) (status >>> 8);
        response[response.length - 1] = (byte) status;
        return response;
    }

    private static int unsignedShort(byte[] data, int offset) {
        return ((data[offset] & 0xff) << 8) | (data[offset + 1] & 0xff);
    }

    private static void writeShort(byte[] data, int offset, int value) {
        data[offset] = (byte) (value >>> 8);
        data[offset + 1] = (byte) value;
    }
}
