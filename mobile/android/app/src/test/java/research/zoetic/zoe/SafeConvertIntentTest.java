package research.zoetic.zoe;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class SafeConvertIntentTest {
    @Test
    public void allowsOnlyExplicitSafeExternalSchemes() {
        assertTrue(SafeConvertActivity.isAllowedExternalScheme("tel:18007997233"));
        assertTrue(SafeConvertActivity.isAllowedExternalScheme("sms:88788?body=START"));
        assertTrue(SafeConvertActivity.isAllowedExternalScheme("mailto:hotline@thehotline.org"));
        assertTrue(SafeConvertActivity.isAllowedExternalScheme("https://lawhelp.org"));
        assertTrue(SafeConvertActivity.isAllowedExternalScheme("geo:0,0?q=emergency+room+hospital"));

        assertFalse(SafeConvertActivity.isAllowedExternalScheme("http://example.com"));
        assertFalse(SafeConvertActivity.isAllowedExternalScheme("javascript:alert(1)"));
        assertFalse(SafeConvertActivity.isAllowedExternalScheme("file:///etc/passwd"));
        assertFalse(SafeConvertActivity.isAllowedExternalScheme("intent://foo"));
        assertFalse(SafeConvertActivity.isAllowedExternalScheme(null));
        assertFalse(SafeConvertActivity.isAllowedExternalScheme(""));
    }

    @Test
    public void mapsIsoCountriesAndLanguagesToSafeConvertPacks() {
        assertEquals("US", SafeConvertActivity.mapIsoCountryToRegion("US"));
        assertEquals("US", SafeConvertActivity.mapIsoCountryToRegion(""));
        assertEquals("UK", SafeConvertActivity.mapIsoCountryToRegion("gb"));
        assertEquals("EU", SafeConvertActivity.mapIsoCountryToRegion("DE"));
        assertEquals("EU", SafeConvertActivity.mapIsoCountryToRegion("FR"));
        assertEquals("EU", SafeConvertActivity.mapIsoCountryToRegion("ES"));
        assertEquals("CA", SafeConvertActivity.mapIsoCountryToRegion("CA"));
        assertEquals("AU", SafeConvertActivity.mapIsoCountryToRegion("AU"));
        assertEquals("MX", SafeConvertActivity.mapIsoCountryToRegion("MX"));
        assertEquals("IN", SafeConvertActivity.mapIsoCountryToRegion("IN"));
        assertEquals("GLOBAL", SafeConvertActivity.mapIsoCountryToRegion("JP"));

        assertEquals("en", SafeConvertActivity.normalizeLangCode("en-US"));
        assertEquals("es", SafeConvertActivity.normalizeLangCode("es-MX"));
        assertEquals("fr", SafeConvertActivity.normalizeLangCode("fr-FR"));
        assertEquals("de", SafeConvertActivity.normalizeLangCode("de-DE"));
        assertEquals("pt", SafeConvertActivity.normalizeLangCode("pt-BR"));
        assertEquals("en", SafeConvertActivity.normalizeLangCode("ja"));
    }

    @Test
    public void parsesSmsTargetAndDecodedDistressBody() {
        assertArrayEquals(
                new String[]{"88788", "START"},
                SafeConvertActivity.parseSmsTargetAndBody("sms:88788?body=START"));
        assertArrayEquals(
                new String[]{"+15551234567", "blue sky"},
                SafeConvertActivity.parseSmsTargetAndBody("sms:+15551234567?body=blue%20sky"));
        assertArrayEquals(
                new String[]{"741741", ""},
                SafeConvertActivity.parseSmsTargetAndBody("sms:741741"));
    }

    @Test
    public void sanitizesContactsJsonForPrivateStorage() {
        assertEquals("[]", SafeConvertActivity.sanitizeContactsJson("  [] "));
        assertEquals("[{\"name\":\"Mom\"}]", SafeConvertActivity.sanitizeContactsJson("[{\"name\":\"Mom\"}]"));
        assertNull(SafeConvertActivity.sanitizeContactsJson("{}"));
        assertNull(SafeConvertActivity.sanitizeContactsJson("alert(1)"));
        assertNull(SafeConvertActivity.sanitizeContactsJson(""));
        assertNull(SafeConvertActivity.sanitizeContactsJson(null));

        StringBuilder tooLong = new StringBuilder("[");
        for (int i = 0; i < 4200; i++) {
            tooLong.append('a');
        }
        tooLong.append(']');
        assertNull(SafeConvertActivity.sanitizeContactsJson(tooLong.toString()));
    }
}
