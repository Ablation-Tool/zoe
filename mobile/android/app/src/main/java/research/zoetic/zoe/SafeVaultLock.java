package research.zoetic.zoe;

import android.content.Context;

import java.nio.charset.StandardCharsets;
import java.security.GeneralSecurityException;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.util.Base64;

import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;

final class SafeVaultLock {
    private static final String PREFS_NAME = "uc_prefs";
    private static final String KEY_LOCK = "uc_lock_v1";
    private static final int ITERATIONS = 60_000;
    private static final int KEY_BITS = 256;
    private static final int SALT_BYTES = 16;

    private SafeVaultLock() {
    }

    static boolean isValidPasscode(String code) {
        return code != null && code.trim().length() >= 4 && code.length() <= 32;
    }

    static String createRecord(String passcode) {
        if (!isValidPasscode(passcode)) {
            return null;
        }
        byte[] salt = new byte[SALT_BYTES];
        new SecureRandom().nextBytes(salt);
        byte[] derived = derive(passcode.toCharArray(), salt);
        if (derived == null) {
            return null;
        }
        return "v1:"
                + Base64.getEncoder().encodeToString(salt)
                + ":"
                + Base64.getEncoder().encodeToString(derived);
    }

    static boolean verifyRecord(String record, String candidate) {
        if (record == null || candidate == null || candidate.isEmpty()) {
            return false;
        }
        String[] parts = record.split(":", -1);
        if (parts.length != 3 || !"v1".equals(parts[0])) {
            return false;
        }
        byte[] salt;
        byte[] expected;
        try {
            salt = Base64.getDecoder().decode(parts[1]);
            expected = Base64.getDecoder().decode(parts[2]);
        } catch (IllegalArgumentException error) {
            return false;
        }
        if (salt.length != SALT_BYTES || expected.length != KEY_BITS / 8) {
            return false;
        }
        byte[] actual = derive(candidate.toCharArray(), salt);
        return actual != null && MessageDigest.isEqual(expected, actual);
    }

    static boolean hasPasscode(Context context) {
        String record = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(KEY_LOCK, "");
        return record != null && !record.isEmpty();
    }

    static boolean setPasscode(Context context, String passcode) {
        String record = createRecord(passcode);
        if (record == null) {
            return false;
        }
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .putString(KEY_LOCK, record)
                .commit();
    }

    static boolean verifyPasscode(Context context, String candidate) {
        String record = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(KEY_LOCK, "");
        return verifyRecord(record, candidate);
    }

    static void clearPasscode(Context context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit()
                .remove(KEY_LOCK)
                .commit();
    }

    private static byte[] derive(char[] chars, byte[] salt) {
        PBEKeySpec spec = new PBEKeySpec(chars, salt, ITERATIONS, KEY_BITS);
        try {
            SecretKeyFactory factory = SecretKeyFactory.getInstance("PBKDF2WithHmacSHA256");
            return factory.generateSecret(spec).getEncoded();
        } catch (GeneralSecurityException error) {
            try {
                byte[] fallbackInput = (new String(chars) + ":" + Base64.getEncoder().encodeToString(salt))
                        .getBytes(StandardCharsets.UTF_8);
                return MessageDigest.getInstance("SHA-256").digest(fallbackInput);
            } catch (GeneralSecurityException fatal) {
                return null;
            }
        } finally {
            spec.clearPassword();
        }
    }
}
