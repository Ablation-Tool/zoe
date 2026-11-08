# QKD and post-quantum pairing research

**Goal:** compare quantum key distribution (QKD) with post-quantum cryptography (PQC), then plan a careful migration for Zoe Pairing. The current implementation is **not post-quantum ready**.

## The distinction

| Question | Quantum key distribution | Post-quantum algorithms |
|---|---|---|
| What supplies security? | Quantum physical properties and an authenticated classical channel | Mathematical problems designed to resist classical and quantum attacks |
| Where does it run? | Special-purpose quantum hardware and dedicated links | Existing classical computers and networks |
| Is authentication automatic? | No; source authentication needs asymmetric cryptography or preplaced keys | Digital-signature algorithms can provide authentication |
| Main practical concerns | Distance, photon loss, trusted relays, cost, hardware imperfections, validation, side channels, denial of service, and upgrades | Implementation correctness, parameter sets, side channels, payload sizes, protocol composition, downgrade handling, and migration complexity |
| Is safety guaranteed? | No; theoretical guarantees depend on implementation and assumptions | No; standardized algorithms still require correct protocols, implementations, and review |

NSA describes QKD as a partial solution requiring source authentication, special-purpose equipment, trusted-relay and infrastructure review, hardware validation, and denial-of-service analysis. It does not support QKD for National Security Systems unless those limitations are overcome. ([NSA QKD limitations](https://www.nsa.gov/Cybersecurity/Quantum-Key-Distribution-QKD-and-Quantum-Cryptography-QC/))

NIST has finalized **ML-KEM (FIPS 203)**, **ML-DSA (FIPS 204)**, and **SLH-DSA (FIPS 205)** for key establishment and digital signatures. These are standardized algorithms, not blanket guarantees that every implementation or protocol is secure. ([NIST standards announcement](https://www.nist.gov/news-events/news/2024/08/nist-releases-first-3-finalized-post-quantum-encryption-standards))

## Current Zoe audit

- **Session establishment:** X25519 is vulnerable to Shor's algorithm on a sufficiently capable quantum computer.
- **Identity and author signatures:** Ed25519 is likewise vulnerable.
- **Constitution PDF/CMS:** RSA-3072 is vulnerable.
- **QKD is not a drop-in replacement:** the current QR/JSON pairing flow has no quantum channel, special-purpose hardware, or QKD-specific protocol validation.
- **Verification phrase:** a hash-derived phrase is not proof of post-quantum security, identity, or a trusted timestamp. Independent-channel comparison remains necessary.

`post_quantum_pairing_review()` preserves these limitations explicitly:

```python
from agent_logging_system.neurogarden_lab import post_quantum_pairing_review

review = post_quantum_pairing_review()
assert review["post_quantum_ready"] is False
assert review["migration_implemented"] is False
assert review["qkd_deployed"] is False
assert review["network_called"] is False
```

## Hybrid research path

1. **Session establishment:** evaluate X25519 + ML-KEM so an attacker must defeat both independent exchanges rather than only the legacy one.
2. **Identity and author signatures:** evaluate Ed25519 + ML-DSA for pairing offers and author certificates. SLH-DSA remains a separate standards-backed alternative to evaluate, not a silent substitute.
3. **Protocol composition:** authenticate the complete algorithm suite and transcript. Test legacy-only, post-quantum-only, mixed, reordered, duplicated, missing, and downgrade offers.
4. **Payloads:** measure larger public keys, ciphertexts, and signatures before choosing QR capacity or a JSON-first exchange. Do not truncate cryptographic objects to fit a graphic.
5. **Implementation:** use reviewed libraries and known-answer tests. Check private-seed handling, side channels, decoding, error behavior, and resource bounds rather than inventing primitives.
6. **Human verification:** retain independent-channel fingerprint and verification-phrase comparison. New algorithms do not prove real-world identity, trustworthiness, or safety.
7. **Migration evidence:** keep `post_quantum_ready=False` and `migration_implemented=False` until a complete reviewed workflow exists and the tests that cover both algorithms and downgrade behavior pass.

No QKD hardware, production migration, security certification, or new encrypted file-transfer protocol is created by this guide. It is a comparison and research plan, not an authorization to deploy.

## Sources

- [FIPS 203 · ML-KEM](https://csrc.nist.gov/pubs/fips/203/final)
- [FIPS 204 · ML-DSA](https://csrc.nist.gov/pubs/fips/204/final)
- [FIPS 205 · SLH-DSA](https://csrc.nist.gov/pubs/fips/205/final)
- [NSA · QKD and quantum cryptography limitations](https://www.nsa.gov/Cybersecurity/Quantum-Key-Distribution-QKD-and-Quantum-Cryptography-QC/)
- [Zoe's current pairing protocol](../../mobile/PAIRING.md)
