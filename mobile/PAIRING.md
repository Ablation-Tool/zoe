# Zoe QR Pairing

**A matching static QR image would only prove that someone copied it.** Zoe Pair uses a fresh signed ceremony so two people can verify that they completed the same session and hold the corresponding private keys.

## What each side has

- A persistent **Ed25519 identity key** for signatures and fingerprints.
- A fresh **X25519 ephemeral key** for this session's shared secret.
- A signed public offer containing a random session ID, nonce, public keys, and a ten-minute expiration.
- Private identity/session files created with owner-only permissions (`0600` on POSIX).

The QR contains only the signed public offer. Private keys and the derived shared secret are never placed in the QR, verification image, or public verification JSON.

## Ceremony

Install the explicitly declared dependencies:

```bash
python -m pip install -r mobile/tools/requirements-pairing.txt
```

### 1. Initiator creates an offer

```bash
python mobile/tools/zoe_pair.py begin \
  --identity /private/path/zoe-identity.json \
  --name Zoe \
  --output /private/path/zoe-offer
```

The command prints a 32-character session ID and creates `zoe-offer.json`, `zoe-offer.png`, and a separate owner-only session-secret file. Share the public JSON or QR, never the secret files.

### 2. Peer joins the same session

```bash
python mobile/tools/zoe_pair.py begin \
  --identity /private/path/nick-identity.json \
  --name Nick \
  --output /private/path/nick-offer \
  --session INITIATOR_SESSION_ID
```

### 3. Both complete and compare

```bash
python mobile/tools/zoe_pair.py complete \
  --identity /private/path/nick-identity.json \
  --mine /private/path/nick-offer \
  --theirs /path/to/zoe-offer.json
```

Both sides independently verify both Ed25519 signatures, session equality, expiration, unique nonces, and unique ephemeral keys. X25519 derives the shared secret. A keyed SHA-256 transcript produces a **120-bit base32 verification phrase**. The two combined verification PNGs should be byte-identical because offers are canonically ordered before rendering.

Compare the phrase and image through an independent channel. Do not use the same potentially compromised channel as your only identity check.

### 4. Explicitly accept trust

After comparing, rerun `complete` with `--accept-sas PHRASE`:

```bash
python mobile/tools/zoe_pair.py complete \
  --identity /private/path/nick-identity.json \
  --mine /private/path/nick-offer \
  --theirs /path/to/zoe-offer.json \
  --accept-sas PHRASE
```

No trusted-peer record is created by scanning, completing, or merely viewing the phrase. A wrong phrase stores nothing. Existing verification outputs are never overwritten. Once a name has a trusted fingerprint, a later offer with that name and a different fingerprint is rejected.

## Security boundaries

- A copied public QR cannot produce a new valid shared phrase without the private ephemeral key.
- Active substitution or relay of offers changes the transcript and should change the phrase. The independent comparison is what detects a man-in-the-middle; QR scanning alone does not.
- Self-signed identity keys do not automatically prove a real-world identity. Confirm the identity fingerprint through a channel you already trust before the first acceptance.
- Ephemeral session keys provide session secrecy for the derived value; the long-term identity key signs rather than encrypts.
- Expiration limits offer lifetime but does not prevent a live relay. Nonces are not a replacement for the comparison.
- This is **pairing only**, not an encrypted file-transfer protocol, anonymous identity system, certificate authority, revocation service, or guarantee that the peer's later actions are safe.
- If an identity seed is compromised, stop using it and re-review trusted peers. There is no production revocation UI yet.

## Document author certificates

`zoe_author.py` uses the same persistent Ed25519 identity to sign an exact document hash and public author statement. This is separate from the expiring pairing offer: no session secret or shared Diffie–Hellman value is embedded in the author certificate.

```bash
python mobile/tools/zoe_author.py sign \
  --identity /private/path/zoe-identity.json \
  --document /path/to/zoe-constitution-signed.pdf \
  --output /path/to/zoe-constitution-signed \
  --related-json /path/to/public-related-artifacts.json

python mobile/tools/zoe_author.py verify \
  --certificate /path/to/zoe-constitution-signed.author.json \
  --document /path/to/zoe-constitution-signed.pdf
```

Verification checks the Ed25519 signature, identity fingerprint, document name, and exact document bytes. Related public metadata can bind PDF signing-certificate, detached-CMS, sealed-source, and source-record hashes into the signed author certificate.

The Constitution package in `evidence/constitution/` demonstrates two independent layers: an RSA-3072 PDF/CMS signature through `pdf-signature-toolkit`, and the Ed25519 QR author certificate. NSS could not import the Ed25519 private key directly for PDF signing, so the QR identity signs the author certificate rather than the PDF's CMS object. That implementation limit is disclosed rather than hidden. Self-signed certificates and author statements remain reviewable evidence, not independent identity or timestamp proof.

## Verification

```bash
python -m pytest mobile/tools/test_zoe_pair.py mobile/tools/test_zoe_author.py -v
```

Eight tests cover real QR decoding, byte-identical combined images, signature tampering, expiration, session mismatch, explicit trust acceptance, changed identities, identity-file permissions, and exact-document author verification. No real identity or peer trust is used by the tests.

## Post-quantum status

X25519, Ed25519, and RSA-3072 are not post-quantum secure, and QKD is not a drop-in replacement. The separate [QKD and post-quantum pairing research guide](../components/agent-logging-system/docs/QUANTUM.md) records the current audit and a hybrid ML-KEM/ML-DSA research path. It does not implement a migration or change the security claims of the current protocol.
