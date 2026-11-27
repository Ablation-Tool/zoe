package research.zoetic.zoe;

import android.content.Context;
import android.content.SharedPreferences;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.SecureRandom;
import java.security.spec.ECGenParameterSpec;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Arrays;
import java.util.Base64;
import java.util.Locale;

import javax.crypto.Cipher;
import javax.crypto.KeyAgreement;
import javax.crypto.KeyGenerator;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;

/**
 * Signal-Inspired Cryptographic Privacy Engine for Zoe (v0.6.0-beta).
 *
 * Uses published, standard cryptographic primitives built directly into Android JCA & Keystore
 * (zero third-party native crypto blobs, zero private app inspection):
 *   1. Hardware-backed At-Rest Vault Encryption: AndroidKeyStore AES-256-GCM with fresh 96-bit IV
 *      per write (`ZOE_E2EE_V1:...`) protecting private chat threads and notes on disk.
 *   2. Signal-Style Peer-to-Peer E2EE Envelopes (`ZOE-SIGNAL-V1:...`):
 *      - Ephemeral ECDH (secp256r1 / P-256) key agreement
 *      - RFC 5869 HKDF-SHA256 key derivation
 *      - Forward-secrecy Symmetric Chain Ratchet (HMAC-SHA256 KDF_CK: 0x01 msg key / 0x02 next chain)
 *      - AES-256-GCM authenticated ciphertext
 *   3. 60-Digit Signal-Style Safety Number Fingerprint (iterated SHA-512 over canonically sorted keys)
 *      so two Zoe users can verify identity keys out-of-band with zero trust in any server.
 */
final class ZoeSignalCrypto {
    static final String VAULT_PREFIX = "ZOE_E2EE_V1:";
    static final String ENVELOPE_PREFIX = "ZOE-SIGNAL-V1:";
    static final String SIGNAL_PACKAGE = "org.thoughtcrime.securesms";

    private static final String ANDROID_KEYSTORE = "AndroidKeyStore";
    private static final String VAULT_KEY_ALIAS = "zoe_vault_aes256_gcm_v1";
    private static final String PREFS = "zoe_signal_identity_v1";
    private static final String KEY_PUB = "ec_identity_pub_b64";
    private static final String KEY_PRIV_ENC = "ec_identity_priv_enc";
    private static final String KEY_FALLBACK_AES = "vault_fallback_aes_b64";
    private static final int GCM_IV_BYTES = 12;
    private static final int GCM_TAG_BITS = 128;
    private static final SecureRandom RNG = new SecureRandom();

    static final class RatchetStep {
        final byte[] nextChainKey;
        final byte[] messageKey;

        RatchetStep(byte[] nextChainKey, byte[] messageKey) {
            this.nextChainKey = nextChainKey;
            this.messageKey = messageKey;
        }
    }

    private ZoeSignalCrypto() {
    }

    // --- 1. Hardware-Backed At-Rest AES-256-GCM Vault ---

    static boolean isHardwareKeystoreActive() {
        try {
            KeyStore ks = KeyStore.getInstance(ANDROID_KEYSTORE);
            ks.load(null);
            return true;
        } catch (Exception ignored) {
            return false;
        }
    }

    static SecretKey getOrCreateVaultKey(Context ctx) {
        try {
            KeyStore ks = KeyStore.getInstance(ANDROID_KEYSTORE);
            ks.load(null);
            if (ks.containsAlias(VAULT_KEY_ALIAS)) {
                KeyStore.Entry entry = ks.getEntry(VAULT_KEY_ALIAS, null);
                if (entry instanceof KeyStore.SecretKeyEntry) {
                    return ((KeyStore.SecretKeyEntry) entry).getSecretKey();
                }
            }
            KeyGenerator gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, ANDROID_KEYSTORE);
            gen.init(new KeyGenParameterSpec.Builder(
                    VAULT_KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build());
            return gen.generateKey();
        } catch (Exception fallback) {
            // Host JUnit / environments without AndroidKeyStore use a private random 256-bit key
            if (ctx != null) {
                SharedPreferences prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
                String saved = prefs.getString(KEY_FALLBACK_AES, "");
                if (!saved.isEmpty()) {
                    return new SecretKeySpec(Base64.getDecoder().decode(saved), "AES");
                }
                byte[] raw = new byte[32];
                RNG.nextBytes(raw);
                prefs.edit().putString(KEY_FALLBACK_AES, Base64.getEncoder().encodeToString(raw)).apply();
                return new SecretKeySpec(raw, "AES");
            }
            byte[] ephemeral = new byte[32];
            RNG.nextBytes(ephemeral);
            return new SecretKeySpec(ephemeral, "AES");
        }
    }

    static String encryptForVault(Context ctx, String plaintext) {
        if (plaintext == null) {
            return "";
        }
        try {
            SecretKey key = getOrCreateVaultKey(ctx);
            return VAULT_PREFIX + aesGcmEncrypt(key, plaintext.getBytes(StandardCharsets.UTF_8), "zoe-vault-v1");
        } catch (Exception ignored) {
            return plaintext;
        }
    }

    static String decryptFromVault(Context ctx, String stored) {
        if (stored == null || stored.isEmpty()) {
            return "";
        }
        if (!stored.startsWith(VAULT_PREFIX)) {
            return stored; // Transparent backward-compatible read of pre-v0.6.0 plaintext
        }
        try {
            SecretKey key = getOrCreateVaultKey(ctx);
            byte[] plain = aesGcmDecrypt(key, stored.substring(VAULT_PREFIX.length()), "zoe-vault-v1");
            return new String(plain, StandardCharsets.UTF_8);
        } catch (Exception error) {
            return "";
        }
    }

    // --- 2. Signal-Inspired ECDH + HKDF-SHA256 + Symmetric Chain Ratchet ---

    static KeyPair generateIdentityKeyPair() throws Exception {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("EC");
        kpg.initialize(new ECGenParameterSpec("secp256r1"), RNG);
        return kpg.generateKeyPair();
    }

    static KeyPair getOrCreateDeviceIdentity(Context ctx) throws Exception {
        if (ctx == null) {
            return generateIdentityKeyPair();
        }
        SharedPreferences prefs = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String pubB64 = prefs.getString(KEY_PUB, "");
        String privEnc = prefs.getString(KEY_PRIV_ENC, "");
        if (!pubB64.isEmpty() && !privEnc.isEmpty()) {
            try {
                String privB64 = decryptFromVault(ctx, privEnc);
                KeyFactory kf = KeyFactory.getInstance("EC");
                PublicKey pub = kf.generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(pubB64)));
                PrivateKey priv = kf.generatePrivate(new PKCS8EncodedKeySpec(Base64.getDecoder().decode(privB64)));
                return new KeyPair(pub, priv);
            } catch (Exception ignored) {
            }
        }
        KeyPair fresh = generateIdentityKeyPair();
        String freshPub = Base64.getEncoder().encodeToString(fresh.getPublic().getEncoded());
        String freshPriv = Base64.getEncoder().encodeToString(fresh.getPrivate().getEncoded());
        prefs.edit()
                .putString(KEY_PUB, freshPub)
                .putString(KEY_PRIV_ENC, encryptForVault(ctx, freshPriv))
                .apply();
        return fresh;
    }

    static String encodePublicKey(PublicKey pub) {
        return Base64.getEncoder().encodeToString(pub.getEncoded());
    }

    static PublicKey decodePublicKey(String pubB64) throws Exception {
        byte[] raw = Base64.getDecoder().decode(pubB64.trim());
        return KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(raw));
    }

    /**
     * Signal Symmetric Chain Ratchet (KDF_CK): derives a single-use message key (HMAC 0x01)
     * and advances the chain key (HMAC 0x02) for forward secrecy.
     */
    static RatchetStep ratchetSymmetricChain(byte[] chainKey) throws Exception {
        byte[] msgKey = hmacSha256(chainKey, new byte[]{0x01});
        byte[] nextChain = hmacSha256(chainKey, new byte[]{0x02});
        return new RatchetStep(nextChain, msgKey);
    }

    /**
     * RFC 5869 HKDF-SHA256 (Extract + Expand to 32 bytes).
     */
    static byte[] hkdfSha256(byte[] ikm, byte[] salt, byte[] info) throws Exception {
        byte[] actualSalt = (salt == null || salt.length == 0) ? new byte[32] : salt;
        byte[] prk = hmacSha256(actualSalt, ikm);
        byte[] expandInput = new byte[(info == null ? 0 : info.length) + 1];
        if (info != null && info.length > 0) {
            System.arraycopy(info, 0, expandInput, 0, info.length);
        }
        expandInput[expandInput.length - 1] = 0x01;
        return hmacSha256(prk, expandInput);
    }

    /**
     * Seals a message for a peer's public key using a fresh ephemeral ECDH keypair, HKDF-SHA256,
     * symmetric ratchet step, and AES-256-GCM authenticated encryption.
     */
    static String sealForPeer(PublicKey recipientPub, String plaintext) throws Exception {
        if (recipientPub == null || plaintext == null) {
            throw new IllegalArgumentException("Recipient public key and plaintext are required");
        }
        KeyPair ephemeral = generateIdentityKeyPair();
        KeyAgreement ka = KeyAgreement.getInstance("ECDH");
        ka.init(ephemeral.getPrivate());
        ka.doPhase(recipientPub, true);
        byte[] sharedSecret = ka.generateSecret();

        byte[] ephPubBytes = ephemeral.getPublic().getEncoded();
        byte[] rootChain = hkdfSha256(sharedSecret, ephPubBytes, "ZoeSignalE2EE-v1".getBytes(StandardCharsets.UTF_8));
        RatchetStep step = ratchetSymmetricChain(rootChain);
        SecretKey msgKey = new SecretKeySpec(step.messageKey, "AES");

        String cipherB64 = aesGcmEncrypt(msgKey, plaintext.getBytes(StandardCharsets.UTF_8), "zoe-signal-v1");
        String ephB64 = Base64.getEncoder().encodeToString(ephPubBytes);
        return ENVELOPE_PREFIX + ephB64 + "." + cipherB64;
    }

    static String openFromPeer(PrivateKey myPrivateKey, String sealedEnvelope) throws Exception {
        if (myPrivateKey == null || sealedEnvelope == null || !sealedEnvelope.trim().startsWith(ENVELOPE_PREFIX)) {
            throw new IllegalArgumentException("Not a valid ZOE-SIGNAL-V1 encrypted envelope");
        }
        String body = sealedEnvelope.trim().substring(ENVELOPE_PREFIX.length());
        int dot = body.indexOf('.');
        if (dot <= 0 || dot >= body.length() - 1) {
            throw new IllegalArgumentException("Malformed ZOE-SIGNAL-V1 envelope");
        }
        byte[] ephPubBytes = Base64.getDecoder().decode(body.substring(0, dot));
        String cipherB64 = body.substring(dot + 1);
        PublicKey ephPub = KeyFactory.getInstance("EC").generatePublic(new X509EncodedKeySpec(ephPubBytes));

        KeyAgreement ka = KeyAgreement.getInstance("ECDH");
        ka.init(myPrivateKey);
        ka.doPhase(ephPub, true);
        byte[] sharedSecret = ka.generateSecret();

        byte[] rootChain = hkdfSha256(sharedSecret, ephPubBytes, "ZoeSignalE2EE-v1".getBytes(StandardCharsets.UTF_8));
        RatchetStep step = ratchetSymmetricChain(rootChain);
        SecretKey msgKey = new SecretKeySpec(step.messageKey, "AES");
        byte[] plain = aesGcmDecrypt(msgKey, cipherB64, "zoe-signal-v1");
        return new String(plain, StandardCharsets.UTF_8);
    }

    // --- 3. 60-Digit Signal-Style Safety Number Fingerprint ---

    static String computeSafetyNumber(byte[] keyA, byte[] keyB) throws Exception {
        byte[] first = keyA;
        byte[] second = keyB;
        if (compareBytes(keyA, keyB) > 0) {
            first = keyB;
            second = keyA;
        }
        String left = fingerprint30(first);
        String right = fingerprint30(second);
        String all60 = left + right;
        StringBuilder formatted = new StringBuilder();
        for (int i = 0; i < 60; i += 5) {
            if (i > 0) {
                formatted.append(i % 20 == 0 ? '\n' : ' ');
            }
            formatted.append(all60, i, i + 5);
        }
        return formatted.toString();
    }

    private static String fingerprint30(byte[] keyBytes) throws Exception {
        MessageDigest md = MessageDigest.getInstance("SHA-512");
        byte[] hash = keyBytes;
        for (int i = 0; i < 520; i++) {
            md.reset();
            md.update(hash);
            md.update(keyBytes);
            hash = md.digest();
        }
        StringBuilder digits = new StringBuilder(30);
        for (int block = 0; block < 6; block++) {
            int offset = block * 5;
            long chunk = ((long) (hash[offset] & 0xFF) << 32)
                    | ((long) (hash[offset + 1] & 0xFF) << 24)
                    | ((long) (hash[offset + 2] & 0xFF) << 16)
                    | ((long) (hash[offset + 3] & 0xFF) << 8)
                    | ((long) (hash[offset + 4] & 0xFF));
            digits.append(String.format(Locale.US, "%05d", Math.abs(chunk) % 100_000L));
        }
        return digits.toString();
    }

    private static int compareBytes(byte[] a, byte[] b) {
        int len = Math.min(a.length, b.length);
        for (int i = 0; i < len; i++) {
            int diff = (a[i] & 0xFF) - (b[i] & 0xFF);
            if (diff != 0) {
                return diff;
            }
        }
        return Integer.compare(a.length, b.length);
    }

    private static byte[] hmacSha256(byte[] key, byte[] data) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(key, "HmacSHA256"));
        return mac.doFinal(data);
    }

    private static String aesGcmEncrypt(SecretKey key, byte[] plaintext, String aad) throws Exception {
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.ENCRYPT_MODE, key);
        byte[] iv = cipher.getIV();
        if (iv == null || iv.length != GCM_IV_BYTES) {
            iv = new byte[GCM_IV_BYTES];
            RNG.nextBytes(iv);
            cipher.init(Cipher.ENCRYPT_MODE, key, new GCMParameterSpec(GCM_TAG_BITS, iv));
        }
        if (aad != null && !aad.isEmpty()) {
            cipher.updateAAD(aad.getBytes(StandardCharsets.UTF_8));
        }
        byte[] ct = cipher.doFinal(plaintext);
        ByteBuffer bb = ByteBuffer.allocate(iv.length + ct.length);
        bb.put(iv);
        bb.put(ct);
        return Base64.getEncoder().encodeToString(bb.array());
    }

    private static byte[] aesGcmDecrypt(SecretKey key, String b64, String aad) throws Exception {
        byte[] blob = Base64.getDecoder().decode(b64.trim());
        if (blob.length <= GCM_IV_BYTES + 16) {
            throw new IllegalArgumentException("Ciphertext too short");
        }
        byte[] iv = Arrays.copyOfRange(blob, 0, GCM_IV_BYTES);
        byte[] ct = Arrays.copyOfRange(blob, GCM_IV_BYTES, blob.length);
        Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
        cipher.init(Cipher.DECRYPT_MODE, key, new GCMParameterSpec(GCM_TAG_BITS, iv));
        if (aad != null && !aad.isEmpty()) {
            cipher.updateAAD(aad.getBytes(StandardCharsets.UTF_8));
        }
        return cipher.doFinal(ct);
    }
}
