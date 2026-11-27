package research.zoetic.zoe;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class OsToolsBridgeTest {
    @Test
    public void buildsValidGoogleAndAppleMapsUrlsAndCompassCardinals() {
        assertEquals(
                "https://www.google.com/maps/search/?api=1&query=36.617700,-121.916600",
                OsToolsBridge.googleMapsPinUrl(36.6177, -121.9166));
        assertEquals(
                "https://maps.apple.com/?ll=36.617700,-121.916600&q=Pacific%20Grove",
                OsToolsBridge.appleMapsPinUrl(36.6177, -121.9166, "Pacific Grove"));
        assertEquals(
                "google.navigation:q=Monterey%20Bay",
                OsToolsBridge.androidNavigationUri("Monterey Bay."));
        assertEquals(
                "geo:36.617700,-121.916600?q=hospital",
                OsToolsBridge.androidGeoSearchUri("hospital", 36.6177, -121.9166, true));
        assertEquals("https://www.google.com/maps", OsToolsBridge.googleMapsPinUrl(Double.NaN, 0));

        assertEquals("N", OsToolsBridge.compassCardinal(0));
        assertEquals("E", OsToolsBridge.compassCardinal(90));
        assertEquals("SW", OsToolsBridge.compassCardinal(225));
        assertEquals("NW", OsToolsBridge.compassCardinal(-45));

        String shared = OsToolsBridge.formatShareLocationMessage(36.6177, -121.9166, 9.2f, "Pacific Grove, CA");
        assertTrue(shared.contains("Google Maps:"));
        assertTrue(shared.contains("Apple Maps:"));
        assertTrue(shared.contains("Pacific Grove, CA"));
    }

    @Test
    public void parsesBuiltInPhoneActionIntentsWithoutAutoExecuting() {
        OsToolsBridge.ActionSuggestion nav = OsToolsBridge.parseActionIntent("Navigate to Memorial Hospital!");
        assertEquals(OsToolsBridge.ActionKind.NAVIGATE, nav.kind);
        assertEquals("Memorial Hospital", nav.query);
        assertFalse(nav.autoExecuted);

        OsToolsBridge.ActionSuggestion search = OsToolsBridge.parseActionIntent("find pharmacy nearby");
        assertEquals(OsToolsBridge.ActionKind.MAP_SEARCH, search.kind);
        assertEquals("pharmacy nearby", search.query);
        assertFalse(search.autoExecuted);

        OsToolsBridge.ActionSuggestion safety = OsToolsBridge.parseActionIntent("Open personal safety app");
        assertEquals(OsToolsBridge.ActionKind.OPEN_SAFETY, safety.kind);
        assertFalse(safety.autoExecuted);

        OsToolsBridge.ActionSuggestion torch = OsToolsBridge.parseActionIntent("turn on flashlight");
        assertEquals(OsToolsBridge.ActionKind.TOGGLE_TORCH, torch.kind);
        assertFalse(torch.autoExecuted);

        OsToolsBridge.ActionSuggestion timer = OsToolsBridge.parseActionIntent("set a 5 minute timer");
        assertEquals(OsToolsBridge.ActionKind.SET_TIMER, timer.kind);
        assertEquals(300, timer.seconds);

        OsToolsBridge.ActionSuggestion alarm = OsToolsBridge.parseActionIntent("set alarm for 6:30 am");
        assertEquals(OsToolsBridge.ActionKind.SET_ALARM, alarm.kind);
        assertEquals(6, alarm.hour);
        assertEquals(30, alarm.minute);

        ZoeBrainEngine brain = new ZoeBrainEngine(null);
        ZoeBrainEngine.BrainReply reply = brain.respond("directions to Central Park");
        assertEquals("device_tool_route", reply.mode);
        assertTrue(reply.reply.contains("Nothing opens"));
    }
}
