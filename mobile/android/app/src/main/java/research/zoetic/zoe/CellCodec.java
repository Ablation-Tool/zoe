package research.zoetic.zoe;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

final class CellCodec {
    static final int SCALE = 1 << 15;
    private static final BigDecimal SCALE_DECIMAL = BigDecimal.valueOf(SCALE);

    private CellCodec() {
    }

    static byte[] infoRequest() {
        return new byte[]{(byte) 0x80, 0x01, 0, 0};
    }

    static EncodedMeasurement encode(double[] probabilities, double tau) {
        if (probabilities == null || probabilities.length < 1
                || probabilities.length > CellSimulator.MAX_PROBABILITIES) {
            throw new IllegalArgumentException("Distribution must contain 1 to 64 probabilities");
        }
        if (!Double.isFinite(tau) || tau < 0 || tau > 1) {
            throw new IllegalArgumentException("Tau must be between 0 and 1");
        }
        double total = 0;
        BigDecimal[] scaled = new BigDecimal[probabilities.length];
        int[] units = new int[probabilities.length];
        for (int index = 0; index < probabilities.length; index++) {
            double probability = probabilities[index];
            if (!Double.isFinite(probability) || probability < 0 || probability > 1) {
                throw new IllegalArgumentException("Probabilities must be between 0 and 1");
            }
            total += probability;
            scaled[index] = BigDecimal.valueOf(probability).multiply(SCALE_DECIMAL);
            units[index] = scaled[index].intValue();
        }
        if (Math.abs(total - 1.0) > 1e-8) {
            throw new IllegalArgumentException("Probabilities must sum to 1 within 1e-8");
        }
        int remaining = SCALE - Arrays.stream(units).sum();
        int[] order = new int[units.length];
        for (int index = 0; index < order.length; index++) {
            order[index] = index;
        }
        for (int index = 1; index < order.length; index++) {
            int current = order[index];
            BigDecimal fraction = scaled[current].remainder(BigDecimal.ONE);
            int position = index - 1;
            while (position >= 0 && scaled[order[position]].remainder(BigDecimal.ONE).compareTo(fraction) < 0) {
                order[position + 1] = order[position];
                position--;
            }
            order[position + 1] = current;
        }
        for (int index = 0; index < remaining; index++) {
            units[order[index]]++;
        }
        int threshold = BigDecimal.valueOf(tau).multiply(SCALE_DECIMAL)
                .setScale(0, RoundingMode.HALF_EVEN).intValue();
        byte[] apdu = new byte[7 + units.length * 2];
        apdu[0] = (byte) 0x80;
        apdu[1] = 0x02;
        apdu[4] = (byte) (apdu.length - 5);
        writeShort(apdu, 5, threshold);
        for (int index = 0; index < units.length; index++) {
            writeShort(apdu, 7 + index * 2, units[index]);
        }
        return new EncodedMeasurement(threshold, units, apdu);
    }

    static byte[] parseCommand(String text) {
        if (text == null || text.isEmpty() || text.length() > 600) {
            throw new IllegalArgumentException("Enter a bounded hexadecimal APDU command");
        }
        String normalized = text.replaceAll("[\\s:]+", "");
        if (normalized.isEmpty() || normalized.length() > CellSimulator.MAX_REQUEST_BYTES * 2
                || (normalized.length() & 1) != 0) {
            throw new IllegalArgumentException("APDU must contain 1 to 135 bytes as hexadecimal");
        }
        byte[] command = new byte[normalized.length() / 2];
        for (int index = 0; index < command.length; index++) {
            int high = Character.digit(normalized.charAt(index * 2), 16);
            int low = Character.digit(normalized.charAt(index * 2 + 1), 16);
            if (high < 0 || low < 0) {
                throw new IllegalArgumentException("APDU contains a non-hexadecimal character");
            }
            command[index] = (byte) ((high << 4) | low);
        }
        return command;
    }

    static String hex(byte[] value) {
        StringBuilder result = new StringBuilder(value.length * 2);
        for (byte item : value) {
            result.append(String.format("%02X", item & 0xff));
        }
        return result.toString();
    }

    static int status(byte[] response) {
        if (response == null || response.length < 2) {
            throw new IllegalArgumentException("Incomplete card response");
        }
        return unsignedShort(response, response.length - 2);
    }

    static String decodeInfo(byte[] response) {
        requireSuccess(response);
        if (response.length != 16 || response[0] != 1
                || response[1] != CellSimulator.MAX_PROBABILITIES || response[13] != 1) {
            throw new IllegalArgumentException("Invalid Zoe Cell information response");
        }
        return new String(response, 2, 11, StandardCharsets.US_ASCII)
                + " · protocol 1 · Q0.15 · maximum 64 probabilities";
    }

    static Measurement decodeMeasurement(byte[] response) {
        requireSuccess(response);
        if (response.length != 10) {
            throw new IllegalArgumentException("A measurement response must contain ten bytes");
        }
        int accessible = unsignedShort(response, 0);
        int complement = unsignedShort(response, 2);
        int size = unsignedShort(response, 4);
        int tau = unsignedShort(response, 6);
        if (size < 1 || size > CellSimulator.MAX_PROBABILITIES
                || accessible + complement != size || tau > SCALE) {
            throw new IllegalArgumentException("Invalid measurement counts or threshold");
        }
        return new Measurement(accessible, complement, size, tau);
    }

    private static void requireSuccess(byte[] response) {
        if (response == null || response.length < 2) {
            throw new IllegalArgumentException("Incomplete card response");
        }
        int status = unsignedShort(response, response.length - 2);
        if (status != 0x9000) {
            throw new IllegalArgumentException(String.format("Card returned status 0x%04X", status));
        }
    }

    private static int unsignedShort(byte[] data, int offset) {
        return ((data[offset] & 0xff) << 8) | (data[offset + 1] & 0xff);
    }

    private static void writeShort(byte[] data, int offset, int value) {
        data[offset] = (byte) (value >>> 8);
        data[offset + 1] = (byte) value;
    }

    static final class EncodedMeasurement {
        final int tau;
        final int[] probabilities;
        final byte[] apdu;

        EncodedMeasurement(int tau, int[] probabilities, byte[] apdu) {
            this.tau = tau;
            this.probabilities = probabilities;
            this.apdu = apdu;
        }
    }

    static final class Measurement {
        final int accessible;
        final int complement;
        final int vocabularySize;
        final int tau;

        Measurement(int accessible, int complement, int vocabularySize, int tau) {
            this.accessible = accessible;
            this.complement = complement;
            this.vocabularySize = vocabularySize;
            this.tau = tau;
        }
    }
}
