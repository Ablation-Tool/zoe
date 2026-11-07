# Zoe Mobile security model

## Rule

Use **signed cartridges, not SIM exploitation**. SIM/eUICC/baseband access is not a plugin sandbox and is not part of this implementation. A future Zoe cartridge can be a signed package with an identifier, semantic version, artifact hash, author/publisher key, and a small declared capability set. It must not grant itself hardware, network, accessibility, location, contacts, firmware, or lock-screen privileges.

No system is guaranteed secure. This document records current attack surfaces and the controls required before treating a build as production-ready.

## Current security boundaries

- **Boot:** the audited Pixel reports verified boot green and a locked bootloader. Do not unlock, flash, root, or use DSU/GSI experiments on the primary phone.
- **Screen Space:** disabled until the user enables the AccessibilityService. Captures and gestures require explicit actions. No passive accessibility-event feed or background gestures are implemented. It is not a sandbox against a malicious user-enabled service.
- **SafeConvert:** no React/CDN, analytics, tracking, or embedded network loads. Local JavaScript is required for conversion and the hidden workflow; file-to-network and universal file access are blocked. The crisis panel uses both a CSS hidden class and the native HTML `hidden` property; normal use presents only the converter. Hotline/SMS/safe-link actions require a tap. Safe contacts are local to the app, limited to five, and not uploaded by Zoe. Backup and device-transfer rules exclude app data. Local storage is not encrypted storage or protection from a rooted/physical-device attacker, screenshots, or an observant person.
- **Camera and microphone:** no capture on startup. Inspection and conversation require explicit actions. Frames and raw audio are not written by Zoe. Device AI, speech engines, and other apps retain their own trust and network behavior.
- **Models:** OCR/labels/descriptions/forecasts are outputs to inspect, not truth, identity, consciousness, correctness, or authorization. A prompt or image can be adversarial. Do not let model output trigger hardware, firmware, accessibility, or external actions automatically.
- **Network:** the app has user-authorized Internet access, but no Zoe-authored telemetry or image-upload path. Third-party model services, speech services, HTTPS endpoints, and Gemini have separate data boundaries. No trust-all certificates, open camera server, or cloud relay is used.
- **Bluetooth/NFC/location/package visibility:** bounded, user-initiated observations. RSSI and acoustic candidates are not positions or identity. App Observatory is limited to launcher-visible apps rather than `QUERY_ALL_PACKAGES`; public metadata is not private app data and cannot control Play Protect.
- **Memory chains:** canonical JSON SHA-256 chains provide tamper evidence, not authentication or proof of authorship.
- **Builds:** debug signatures are development identities, not production trust anchors. A release pipeline, release keys, signing provenance, and revocation process are still required.

## Tiny Zoe simulator boundaries

The native Zoe Cell simulator is a local behavioral protocol model, not a secure element or an authentication system. Its activity is not exported and adds no hardware, SIM, NFC, Bluetooth, network, storage, or accessibility capability. It does not load code, hold keys, access secrets, or claim a secure chip, trusted clock, or cryptographic identity.

- APDU commands are limited to 135 bytes and probability vectors to 64 entries. Raw hexadecimal input is bounded before normalization; probability and threshold text have separate size limits.
- The last twelve transaction summaries remain in memory only. Request/response arrays are defensively copied, and reset clears history, replay state, and displayed results.
- Replay repeats only a local simulated request. It cannot execute an external action or convert a measurement into evidence, belief, or authorization.
- Malformed commands and unsupported instructions return bounded status responses. Invalid text is rejected before a transaction is created.
- Host tests exercise every APDU length from 0–135 bytes, deterministic replay, mutation attempts, hostile strings, and oversized input. Device tests cover raw errors, identical replay bytes, reset, and UI rejection.

Passing these tests is not proof of perfect safety, absence of exploits, physical-card security, or production readiness. Any future physical transport requires a separate threat model, authorization checks, and hardware verification.

## Cartridge requirements for future modules

1. **Signed manifest:** schema version, cartridge ID, semantic version, source/revision, artifact hash, publisher key fingerprint, and requested capabilities.
2. **Verified activation:** verify signature, artifact bytes, trusted key, and revocation status before loading. Do not execute a package merely because it has a valid-looking signature or filename.
3. **Least privilege:** empty default capability set. Separate read/write, network, camera, microphone, location, accessibility, and external-launch permissions. Ask for each independently at activation and retain a denial path.
4. **No arbitrary execution:** no `eval`, shell strings, hidden download, dynamic native loader, or code fetched at launch. Prefer reviewed Java/Swift implementations and static manifests.
5. **Isolation:** per-cartridge storage, process, resource limits, cancellation, and no implicit evidence or permission transfer between cartridges. A shared source graph is context, not authority.
6. **Update safety:** reproducible builds, dependency lockfiles, SBOM/provenance, A/B or rollback support, expiry/revocation, downgrade protection, and no silent updates.
7. **Accessible failure:** unsupported, revoked, corrupt, or unavailable modules fail closed with a readable explanation and a working offline path.

## Red-team review checklist

- Malformed or oversized manifests, probability arrays, images, audio, MJPEG frames, VCD files, NFC payloads, and location values.
- Replay/downgrade attacks, revoked keys, stale certificates, duplicate package IDs, dependency confusion, and manifest substitution.
- Prompt injection, image-based instruction injection, misleading labels, model overconfidence, and attempts to turn forecasts into commands.
- WebView navigation escape, cleartext/network bypass, malicious safe-contact input, localStorage theft, URL injection, and unvalidated hotline links.
- Accessibility gesture replay, coordinate confusion, overlay/tapjacking, screenshot disclosure, password/payment capture, and lock-screen attempts.
- Camera/microphone/location/battery/Bluetooth/NFC privacy leakage, RF side channels, unsafe haptics/audio volume, and denial of service.
- ADB exposure, stale IPs, unauthorized pairing, open hotspot misuse, port binding mistakes, and unbounded stream clients.
- State restoration after cancellation, rotation, process death, permission denial, revoked service, network loss, and low memory.

Every finding needs a reproduction, affected boundary, evidence, mitigation, and regression test. Passing tests alone do not prove security.

## Current production blockers

- No production signing/revocation pipeline or cartridge sandbox is implemented.
- Zoe Cell has no CAP conversion, physical-card memory measurement, reader integration, or physical installation. Host class size is not on-card usage; do not target a CAC or carrier eSIM.
- Accessibility and package/location permissions are high-impact and must remain optional and reviewable.
- Local SafeConvert contacts and transcripts are not protected against a rooted/physical attacker or someone watching the screen.
- Third-party model/speech/Gemini behavior and network paths are not fully audited.
- Wireless ADB is not established. Do not leave TCP ADB or hotspot access enabled after testing.
- iOS build/signing/device verification has not run; Android host/device tests are not a security certification.

Blue-team rule: make the boundary explicit. Red-team rule: try to cross it. Do not confuse a creative feature with a security guarantee.
