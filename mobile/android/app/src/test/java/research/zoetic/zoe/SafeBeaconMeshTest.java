package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

public class SafeBeaconMeshTest {
    @Test
    public void beaconPayloadRoundTripsForBothBlindRelayAndLocalSosModes() {
        byte[] secret = Arrays.copyOf("zoe-beacon-test-secret-key-00001".getBytes(StandardCharsets.UTF_8), 32);
        long t0 = 1_760_000_000_000L;

        byte[] blindPkt = SafeBeaconMesh.buildBeaconPayload(secret, SafeBeaconMesh.MODE_BLIND_RELAY, t0);
        assertEquals(SafeBeaconMesh.PACKET_LEN, blindPkt.length);
        SafeBeaconMesh.ParsedBeacon parsedBlind = SafeBeaconMesh.parseBeaconPayload(blindPkt, -68, t0);
        assertNotNull(parsedBlind);
        assertFalse(parsedBlind.isLocalSos());
        assertEquals(32, parsedBlind.rotatingTagHex.length());
        assertTrue(parsedBlind.approxMeters > 0.5 && parsedBlind.approxMeters < 40.0);

        byte[] sosPkt = SafeBeaconMesh.buildBeaconPayload(secret, SafeBeaconMesh.MODE_LOCAL_SOS, t0);
        SafeBeaconMesh.ParsedBeacon parsedSos = SafeBeaconMesh.parseBeaconPayload(sosPkt, -59, t0);
        assertNotNull(parsedSos);
        assertTrue(parsedSos.isLocalSos());
        assertEquals(1.0, parsedSos.approxMeters, 0.2);
    }

    @Test
    public void rotatingTagChangesEvery15MinutesAndTamperedPacketsAreRejected() {
        byte[] secret = Arrays.copyOf("zoe-beacon-test-secret-key-00002".getBytes(StandardCharsets.UTF_8), 32);
        long t0 = 1_760_000_000_000L;
        long tNext = t0 + SafeBeaconMesh.ROTATION_WINDOW_MS;

        byte[] p1 = SafeBeaconMesh.buildBeaconPayload(secret, SafeBeaconMesh.MODE_BLIND_RELAY, t0);
        byte[] p2 = SafeBeaconMesh.buildBeaconPayload(secret, SafeBeaconMesh.MODE_BLIND_RELAY, tNext);
        SafeBeaconMesh.ParsedBeacon b1 = SafeBeaconMesh.parseBeaconPayload(p1, -70, t0);
        SafeBeaconMesh.ParsedBeacon b2 = SafeBeaconMesh.parseBeaconPayload(p2, -70, tNext);
        assertNotNull(b1);
        assertNotNull(b2);
        assertNotEquals(b1.rotatingTagHex, b2.rotatingTagHex);

        // Flip 1 bit -> integrity check must reject!
        p1[10] ^= 0x01;
        assertNull(SafeBeaconMesh.parseBeaconPayload(p1, -70, t0));
    }

    @Test
    public void autoExpiryIsStrictlyCappedAt30Minutes() {
        assertEquals(30L * 60L * 1000L, SafeBeaconMesh.MAX_BEACON_DURATION_MS);
        assertEquals(-1.0, SafeBeaconMesh.estimateDistanceMeters(5), 0.001);
    }
}
