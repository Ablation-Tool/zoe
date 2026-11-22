# Zoe Mobile Security Model (`v0.9.4-beta`)

## Core Rule

Use **documented public OS APIs and signed/verifiable boundaries — never unauthorized reverse engineering, root exploits, or SIM exploitation**. SIM/eUICC/baseband access is not a plugin sandbox and is not part of this implementation.

No software system is guaranteed secure. This document records Zoe's actual attack surfaces, implemented controls, and honest blockers that remain before treating any build as a hardened production release.

---

## Current Implemented Security & Privacy Boundaries

- **Boot Integrity:** The audited Google Pixel 7 reports verified boot green and a locked bootloader. Zoe relies strictly on documented public Android/iOS APIs and never requires unlocking, rooting, or bypassing OS protections.
- **Explicit Opt-In Sensors & Storage:** No camera, microphone, GPS, ARCore/ARKit, BLE, or Accessibility capture starts automatically on app launch. No photos, videos, or audio are written automatically; compact **Trip Journal** thumbnails, **Creative Studio** exports/MP4s, and **SafeConvert** Private Safety Log audio/video recordings are stored **only when the user explicitly taps Save/Record/Export**, inside app-private storage excluded from cloud backups (`android:allowBackup="false"`, `android:fullBackupContent="false"`).
- **SafeConvert Discreet Safety Sandbox (`mobile/SAFECONVERT.md`):**
  - Zero-network local WebView (`setBlockNetworkLoads(true)`, `setAllowContentAccess(false)`, `setAllowFileAccessFromFileURLs(false)`, `setAllowUniversalAccessFromFileURLs(false)`, `MIXED_CONTENT_NEVER_ALLOW`), zero external scripts/CDNs/analytics.
  - Hidden safety companion opens on typing **variants of `911`** (`911`, `991`, `919`, `199`, `119`, `191`, `999`, `111`, including decimals/leading zeros like `9.11` or `0.911`).
  - Sets `WindowManager.LayoutParams.FLAG_SECURE` on Android while revealed (blocking screenshots/Recents previews) and covers the view with a `UIVisualEffectView` blur shield on iOS `willResignActive`.
  - Optional 4–32 character `PBKDF2` passcode lock (`SafeVaultLock.java`) auto-locks on exit; 6 panic-exit triggers (`✕ EXIT`, top bar tap, `ESC`, Back, 90-second idle, app switch/lock) immediately cut voice TTS (`< 10 ms`), halt BLE beacons/scans, wipe Calm Art & ephemeral chat, and snap back to the Unit Converter cover.
  - **Offline BLE Help Beacon Guardrails:** Starts strictly OFF, rotates 15-minute SHA-256 ephemeral tags, enforces a hard **30-minute auto-expiry timer**, supports 1-tap key revocation/rotation, and discloses honest `~30–80 m` peer-to-peer BLE range.
  - **Honest Local Threat Limit:** App-private storage and screen shields cannot protect against a rooted/compromised OS, physical coercion, or someone actively watching over your shoulder.
- **Privacy Vault (`ZoeSignalCrypto.java` / `ZoeSignalAndWakeCore.swift`):**
  - Uses `AndroidKeyStore AES-256-GCM` for chat/vault at-rest encryption and `P-256 ECDH + HKDF-SHA256 + Symmetric Chain Ratchet + AES-256-GCM` with a 60-digit Safety Number for peer-to-peer sealed envelopes.
  - **Honest Audit Limit:** Built on standard platform crypto APIs, but has **not** undergone an independent third-party cryptographic security audit.
- **Closed-Loop Mobile ↔ Workstation L5 Digestion Privacy Firewall (`MobileDigestionBundle.java` / `MobileDigestionCore.swift` / `l5_mobile_digestion.py`):**
  - Runs **only** on explicit user tap (`Feed & Digest Lab`) over USB loopback (`http://127.0.0.1:8765`) or a user-configured HTTPS endpoint (cleartext to remote non-loopback hosts is strictly rejected).
  - Enforces a **double-sided client + server privacy firewall** (server returns HTTP 400 `PrivacyFirewallError` on violation) that hard-excludes **SafeConvert** (notes, vault, contacts, BLE keys), **Privacy Vault** (E2EE keys, envelopes), **raw photos/thumbnails**, and **private chat message bodies** (only aggregated non-sensitive routing metrics and user-explicit `remember`/`relay` notes, textual Trip metadata, and compact Sobel/HoG-16/Radial-8 vectors are included).
- **Opt-In Network Boundaries:**
  - Cleartext HTTP is blocked everywhere except loopback (`127.0.0.1` / `localhost`) via `network_security_config.xml` and `ElizaGemClient.validateEndpoint()`.
  - All external network lanes are **off by default and explicit tap only**: optional DuckDuckGo/Wikipedia live web citations (`Web: off` default), optional CPC Google Patents structural lookup, optional user-supplied BYOK AI APIs (Gemini/Claude/ChatGPT/Grok), optional 1 MiB Connectivity speed test, and optional user-configured HTTPS lab bridge. Zero Zoe telemetry or analytics exist.
- **Screen Space (`ZoeAccessibilityService`):** Disabled until manually enabled in Android Settings; `canRetrieveWindowContent="false"`; captures and gestures execute only on explicit button tap with zero passive event monitoring.
- **Models & Epistemic Firewall:** OCR, image labels, visual contour matches, local LLM outputs, and cloud replies are untrusted observations — never ground truth, identity proof, or authorization to execute hardware/external actions automatically. Compound device actions require explicit step-by-step user taps.
- **Memory Chains:** Canonical JSON SHA-256 hash chains provide local tamper evidence, not cryptographic authorship authentication.
- **Debug Builds:** Published beta APKs are development-signed debug builds, not production trust anchors.

---

## Tiny Zoe Simulator Boundaries

The native **Zoe Cell** simulator (`CellActivity`) is a local behavioral protocol model, not a secure element or authentication system. Its activity is `exported="false"` and uses no hardware, SIM, NFC, Bluetooth, network, storage, or accessibility permissions.

- APDU commands are bounded to 135 bytes and probability vectors to 64 entries.
- At most 12 transaction summaries remain in memory only, with defensive array copies and full reset clearing.
- Malformed commands and hostile strings fail closed with bounded status responses.

---

## Cartridge Requirements for Future Modules

1. **Signed Manifest:** Schema version, cartridge ID, semantic version, artifact hash, publisher key fingerprint, and minimal declared capability set.
2. **Verified Activation:** Verify signature, artifact bytes, trusted key, and revocation status before loading.
3. **Least Privilege:** Empty default capability set; independent runtime opt-in per sensor/network lane with graceful denial.
4. **No Arbitrary Dynamic Execution:** No `eval`, shell injection, hidden downloads, or unverified dynamic code loading.
5. **Isolation:** Per-module storage, bounded memory/timeouts, and no implicit permission transfer.
6. **Update Safety:** Reproducible builds, dependency lockfiles, SBOM/provenance, and downgrade protection.
7. **Accessible Failure:** Unsupported, corrupt, or offline modules fail closed with clear plain-language explanations.

---

## Red-Team Review Checklist

- Malformed/oversized manifests, probability arrays, images, audio, MJPEG frames, NFC payloads, and digestion bundles.
- Privacy-firewall bypass attempts (nested `safeconvert`/`privacy_vault`/base64 image/PEM private key injection into `/api/digest/mobile` — verified blocked `5/5` + HTTP 400 in `scripts/verify_mobile_digestion.py`).
- Prompt injection, image-based instruction injection, and attempts to turn model output into unapproved OS actions.
- WebView navigation escape, cleartext/network bypass, malicious safe-contact input, and unvalidated hotline/URI links.
- Accessibility gesture replay, coordinate confusion, overlay/tapjacking, and screenshot/Recents leakage.
- BLE side-channel tracking risk, stale ephemeral tags, unsafe audio volume in quiet rooms, and lock-screen exposure.
- Lifecycle state preservation across rotation, process death, permission revocation, and network loss.

---

## Honest Remaining Production Blockers

- **No production release signing / key-rotation pipeline** (current beta APKs are debug-signed).
- **No independent third-party security or cryptographic audit** of Privacy Vault, SafeConvert, or the Digestion bridge.
- **Apple iOS build, signing, simulator, and physical-device verification** remain unexecuted on this Linux host (only the shared `ZoeCore` Swift package passes `20/20` tests on Linux Swift 6.1.3).
- **Zoe Cell** has no CAP conversion, physical smart-card memory measurement, or reader installation claim.
- **Accessibility, BLE, and Location permissions** are high-impact and require full Play Store / App Store review justification.
- **Local SafeConvert data** cannot defend against a rooted/compromised device or physical coercion.
- **Third-party model/speech/BYOK cloud services** retain their own privacy policies and network boundaries whenever explicitly enabled by the user.

*Blue-team rule: make every boundary explicit. Red-team rule: try to cross it. Never confuse passing tests or creative features with a security guarantee.*
