package research.nuclide.zoe.card;

import javacard.framework.APDU;
import javacard.framework.Applet;
import javacard.framework.ISO7816;
import javacard.framework.ISOException;
import javacard.framework.Util;

public final class ZoeCard extends Applet {
    private static final byte CLA = (byte) 0x80;
    private static final byte INS_INFO = 0x01;
    private static final byte INS_MEASURE = 0x02;
    private static final byte MAX_PROBABILITIES = 64;
    private static final short MAX_DATA_LENGTH = 130;
    private static final short Q15_ONE = (short) 0x8000;
    private static final byte[] INFO = {
        1, MAX_PROBABILITIES,
        0x5a, 0x4f, 0x45, 0x2f, 0x4e, 0x55,
        0x43, 0x4c, 0x49, 0x44, 0x45,
        1
    };

    private ZoeCard() {
        register();
    }

    public static void install(byte[] buffer, short offset, byte length) {
        new ZoeCard();
    }

    public void process(APDU apdu) {
        if (selectingApplet()) {
            return;
        }
        byte[] buffer = apdu.getBuffer();
        if (buffer[ISO7816.OFFSET_CLA] != CLA) {
            ISOException.throwIt(ISO7816.SW_CLA_NOT_SUPPORTED);
        }
        if (buffer[ISO7816.OFFSET_P1] != 0 || buffer[ISO7816.OFFSET_P2] != 0) {
            ISOException.throwIt(ISO7816.SW_INCORRECT_P1P2);
        }
        byte instruction = buffer[ISO7816.OFFSET_INS];
        if (instruction == INS_INFO) {
            info(apdu, buffer);
        } else if (instruction == INS_MEASURE) {
            measure(apdu, buffer);
        } else {
            ISOException.throwIt(ISO7816.SW_INS_NOT_SUPPORTED);
        }
    }

    private void info(APDU apdu, byte[] buffer) {
        if (apdu.setIncomingAndReceive() != 0) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }
        short length = (short) INFO.length;
        Util.arrayCopyNonAtomic(INFO, (short) 0, buffer, (short) 0, length);
        apdu.setOutgoingAndSend((short) 0, length);
    }

    private void measure(APDU apdu, byte[] buffer) {
        short length = apdu.setIncomingAndReceive();
        if (length < 4 || length > MAX_DATA_LENGTH || (length & 1) != 0) {
            ISOException.throwIt(ISO7816.SW_WRONG_LENGTH);
        }
        short offset = ISO7816.OFFSET_CDATA;
        short tau = readQ15(buffer, offset);
        if (tau < 0 && tau != Q15_ONE) {
            ISOException.throwIt(ISO7816.SW_DATA_INVALID);
        }
        short accessible = 0;
        short count = 0;
        short sumHigh = 0;
        short sumLow = 0;
        short end = (short) (offset + length);
        for (offset += 2; offset < end; offset += 2) {
            short probability = readQ15(buffer, offset);
            if (probability < 0 && probability != Q15_ONE) {
                ISOException.throwIt(ISO7816.SW_DATA_INVALID);
            }
            short previous = sumLow;
            sumLow += probability;
            if ((sumLow & 0xffff) < (previous & 0xffff)) {
                sumHigh++;
            }
            if ((probability & 0xffff) > (tau & 0xffff)) {
                accessible++;
            }
            count++;
        }
        if (sumHigh != 0 || sumLow != Q15_ONE) {
            ISOException.throwIt(ISO7816.SW_DATA_INVALID);
        }
        writeShort(buffer, (short) 0, accessible);
        writeShort(buffer, (short) 2, (short) (count - accessible));
        writeShort(buffer, (short) 4, count);
        writeShort(buffer, (short) 6, tau);
        apdu.setOutgoingAndSend((short) 0, (short) 8);
    }

    private static short readQ15(byte[] buffer, short offset) {
        return (short) (((buffer[offset] & 0xff) << 8) | (buffer[(short) (offset + 1)] & 0xff));
    }

    private static void writeShort(byte[] buffer, short offset, short value) {
        buffer[offset] = (byte) (value >>> 8);
        buffer[(short) (offset + 1)] = (byte) value;
    }
}
