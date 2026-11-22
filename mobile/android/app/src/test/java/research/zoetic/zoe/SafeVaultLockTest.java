package research.zoetic.zoe;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertTrue;

import org.junit.Test;

public class SafeVaultLockTest {
    @Test
    public void validatesPasscodeLengthAndRejectsWeakInputs() {
        assertFalse(SafeVaultLock.isValidPasscode(null));
        assertFalse(SafeVaultLock.isValidPasscode(""));
        assertFalse(SafeVaultLock.isValidPasscode("123"));
        assertFalse(SafeVaultLock.isValidPasscode("   abc"));
        assertTrue(SafeVaultLock.isValidPasscode("7429"));
        assertTrue(SafeVaultLock.isValidPasscode("my quiet harbor 2026"));

        assertNull(SafeVaultLock.createRecord("12"));
    }

    @Test
    public void derivesSaltedPbkdf2HashesAndVerifiesConstantTime() {
        String first = SafeVaultLock.createRecord("7429");
        String second = SafeVaultLock.createRecord("7429");
        assertNotNull(first);
        assertNotNull(second);
        assertTrue(first.startsWith("v1:"));
        assertNotEquals("Each salt should produce a distinct record", first, second);

        assertTrue(SafeVaultLock.verifyRecord(first, "7429"));
        assertTrue(SafeVaultLock.verifyRecord(second, "7429"));
        assertFalse(SafeVaultLock.verifyRecord(first, "0000"));
        assertFalse(SafeVaultLock.verifyRecord(first, ""));
        assertFalse(SafeVaultLock.verifyRecord("malformed", "7429"));
        assertFalse(SafeVaultLock.verifyRecord(null, "7429"));
    }
}
