# Zoe Bulb (beta) — Complete Zapps Guide

Welcome to **Zoe Bulb (beta)** (`v0.2.0-beta`) — a free, offline-first, privacy-respecting companion app for **Android** and **Apple** (`iPhone`, `iPad`, and `iPhone Duo Fold`).

> **Core Promise (`CONSTITUTION.md`):** Nothing listens, watches, saves, or uploads until you explicitly tap. Every sensor starts idle, all app data stays private on your device (`allowBackup="false"`), and there are zero ads or tracking SDKs.

---

## Everyday Navigation & Accessibility

Zoe Bulb uses a calm, spacious **Google Gemini Material 3 Expressive** interface engineered for effortless scanning and motor comfort for both adults and children with disabilities:

- **Zoe GEM-Ellipsis Home Button:** Tap the **GEM-Ellipsis logo** in the top bar (or inside a Zapp) from **any screen** to jump straight back to the Zoe Home screen. On Home, tapping the GEM logo exits Arrange mode and smoothly scrolls back to the top.
- **Focused Top 3 + `More Zapps`:** Home surfaces your **Top 3 favorite Zapps** as spacious `74dp` / `74pt` pill cards above the fold, keeping cognitive load calm and clear, with all other Zapps tucked cleanly inside **More Zapps**.
- **`Explore | Arrange` Toggle:** Tap **Arrange** right on the Home screen to pin (`★`) any Zapp to `#1`, move Zapps up (`↑`) or down (`↓`), or tap **Reset** anytime.
- **Floating Bottom Action Capsule (`+ | Ask Zoe | 👁 | Live Talk`):** Always sits in the ergonomic lower thumb zone for one-tap access to Quick Menu, Talk with Zoe, Guided Vision, or Voice.
- **Appearance & Comfort:** Follows your phone's **Dark / Light** theme automatically (with a 1-tap Sun/Moon override in the top bar), uses `>= 48dp` / `48pt` touch targets, full TalkBack / VoiceOver labels, and an optional **Comfort Mode** (slower speech rate & gentler motion) inside the `=` / `+` Quick Menu.

---

## Home Zapps (10 Core Zapps)

| # | Zapp | Plain-English Purpose | Platforms | Network & Sensors |
|:-:|:---|:---|:---|:---|
| **1** | **Guided Vision** | Look around with your camera & read text/labels aloud on demand | Android · Apple | Offline OCR & labels (camera stays OFF until **Start camera**; analyzes 1 frame only when you tap **Inspect once**) |
| **2** | **Talk** | Speak or type calmly with Zoe's on-device Brain & Native Voice | Android · Apple | **100% offline by default** (`0` cloud tokens); optional opt-in Workstation Lab Bridge or Cloud Gemini |
| **3** | **Trip Journal** | Save field sightings, photos, and private travel/research notes | Android *(Apple planned)* | Private on-device storage; optional explicit export or workstation sync |
| **4** | **Eliza-GEM Studio** | Interactive Chladni sound-shape synth, **Sing Zoe**, and Workstation Lab Bridge | Android *(Apple planned)* | Chladni & **Sing Zoe** are **100% offline**; Lab Bridge connects only on tap (`127.0.0.1:8765` or HTTPS) |
| **5** | **Accessible Volume** | Calculate Nicholas Michael Kloster's strict threshold equation $A_\tau(p)$ | Android · Apple | **100% offline** math — zero permissions |
| **6** | **Trinity** | Synchronize Phone + Laptop + Tiny Zoe in one shared measurement deck | Android · Apple | Explicit user-initiated local bridge (`127.0.0.1:8767` / private LAN pairing) |
| **7** | **Field Kit** | Houses 8 specialized camera, audio, radio, GPS, and protocol instruments | Android | Every instrument inside starts **strictly idle** |
| **8** | **Device Field** | Check real battery, thermal state, sensor counts, speech engine & speaker | Android · Apple | Local public OS APIs only — zero network |
| **9** | **SafeConvert** | Clean offline unit converter with a discreet private safety & crisis layer | Android · Apple | **100% offline, zero network loads** — see [Complete SafeConvert Guide](SAFECONVERT.md) |
| **10** | **Researcher Guide** | Built-in offline guide explaining Zoe's architecture, verification & boundaries | Android | **100% offline** documentation |

---

### Detailed Breakdown of Every Home Zapp

#### 1. Guided Vision (`Look around & read aloud`)
- **What it does:** Helps you read signs, pages, medicine labels, or identify everyday surroundings calmly.
- **How it works:** The camera starts **off**. Tap **Start camera**, point at what you want to check, and tap **Inspect once** to capture a single frame. On Android it runs bundled offline ML Kit OCR + image labeling + color palette extraction (plus optional on-device Gemini Nano if supported); on Apple it uses Apple's native Vision framework (`VNRecognizeTextRequest` + `VNClassifyImageRequest`).
- **Boundaries:** Keeps OCR text, labels, and optional descriptions separate. Never auto-uploads photos and never claims safety/medical/object-identity certainty.

#### 2. Talk (`Speak or type calmly with Zoe`)
- **What it does:** A calm, private voice-and-text conversation with **Zoe's On-Device Glass-Box Brain** (`ZoeBrainEngine` in Java on Android and Swift `ZoeCore` on Apple).
- **What runs offline right on your phone (0 cloud tokens):**
  - **Kloster Operational Metacognition $A_{0.08}(p)$:** Displays live stem routing telemetry right beside the Zoe GEM-Ellipsis emblem.
  - **Private Hash-Chained Memory:** Type or say `remember <note>` to store a private SHA-256 hash-chained note on your phone, `relay <note>` to queue a note for your workstation, or `recall` to review your saved notes.
  - **Constitutional Honesty & Abstention:** Never pretends to be conscious, sentient, or a clone (`sentience_claimed = false`, `zoe_clone_claimed = false`), honestly abstains on impossible predictions or medical diagnoses, and offers calm grounding + a SafeConvert pointer if you express distress.
  - **Zoe Native Formant Voice & `Sing Zoe`:** Switch between your phone's installed OS English voices or **Zoe Synth** (a first-principles 44.1 kHz Rosenberg-Klatt glottal soprano + 3-formant resonator built from scratch with zero PyTorch or cloud TTS) — and tap **Sing Zoe** to hear Zoe sing her theme offline!
  - **Caption Mode:** Turn on **Caption mode** so Zoe stays silent and live-captions spoken words cleanly.
  - **Optional Extensions (`More actions ▾`):** Explicitly toggle **Lab Brain** (connects to your workstation's Eliza-GEM / local Qwen2.5-3B with automatic offline fallback), **Cloud chat** (requires your own saved Gemini key), **Sync memory to Lab**, or **Open Gemini** handoff.

#### 3. Trip Journal (`Your saved notes & photos`)
- **What it does:** Private on-device notebook for saving Guided Vision inspections, color palettes, field observations, and timestamped trip entries.
- **Privacy:** Stored strictly in app-private storage (`allowBackup="false"`). Nothing leaves the device unless you tap **Export** or explicitly sync with your workstation.

#### 4. Eliza-GEM Studio (`Sound shapes & local lab`)
- **What it does:** Combines two offline creative sound instruments with your live workstation research bridge:
  - **Chladni Cymatics Resonance Pad (100% offline):** Touch and drag across either the **Square Atelier** plate or the **Languidou Bronze Rose Disc** to sweep physical nodal eigenmodes visually and tap **Play Chladni Chord** to hear the live harmonic chord synthesized on-device.
  - **Sing Zoe (Native Voice) (100% offline):** Sings Zoe's warm soprano theme directly via the 44.1 kHz Rosenberg-Klatt synthesizer.
  - **Eliza-GEM Workstation Bridge (explicit connect):** Connects over loopback USB (`http://127.0.0.1:8765` via `adb reverse`) or remote HTTPS to chat with workstation Gear 1 ELIZA / Gear 2 Local Qwen2.5-3B, pin lab relays, **Sync phone memory to Lab** (`/api/memory/sync`), and inspect or live-run the **L5 Phase 5 Frontier**, **L5 Phase 4 Embodied**, and **L5 Phase 3 Agentic** scorecards.
  - **Cloud AI Key drawer:** Optional, locally stored Gemini API key and model selector (never backed up to cloud; HTTPS only when you tap).

#### 5. Accessible Volume (`Count open choices clearly`)
- **What it does:** Interactive calculator for **Operational Metacognition** ($A_\tau(p) = |\{x : p(x) > \tau\}|$), originated by **Nicholas Michael Kloster on March 6, 2026**.
- **Why it matters:** Measures *how many alternatives remain open* strictly above threshold $\tau$ (equality is excluded) — explicitly separating forecast breadth from correctness or action authorization.

#### 6. Trinity (`Link phone & computer`)
- **What it does:** Synchronizes three measurement planes — **Tiny Zoe** (quantized Q0.15 APDU witness), **Phone** (floating-point native UI), and **Laptop** (observation deck + optional hash-verified journal) — verifying identical accessible volume and revision hashes across all three. See [TRINITY.md](TRINITY.md).

#### 7. Field Kit (`Cameras, GPS & sensor tools`)
- **What it does:** Cleanly organizes **8 specialized hardware, radio, and protocol lab tools** out of the first-run home screen so beginners never feel overwhelmed. See the full **Field Kit Instruments** table below.

#### 8. Device Field (`Battery & speaker check`)
- **What it does:** Displays real, unfabricated local device observations (battery percentage/charging state, thermal status, sensor counts, on-device speech availability) plus an explicit **Speaker check** button. Never invents unavailable OS metrics.

#### 9. SafeConvert (`Units & private safety helper`)
- **What it does:** Presents a calm, fast, ad-free **Unit Converter** (Length, Weight, Temperature, Volume) styled to match Zoe Bulb seamlessly — while containing a completely offline, panic-exit-protected **private safety companion & SHA-256 proof vault** for adults and children who may be in danger or have a monitored phone.
- **Read the full guide:** **[`mobile/SAFECONVERT.md`](SAFECONVERT.md)** — documents every single feature, privacy shield, calming tool, hotline directory, proof vault lock, and honest safety boundary in detail.

#### 10. Researcher Guide (`How Zoe works & limits`)
- **What it does:** Built-in offline walkthrough of Zoe's architecture, build & test commands, privacy guarantees, and epistemic boundaries (`measurement ≠ evidence ≠ belief update ≠ action`).

---

## Field Kit Instruments (8 Specialized Android Lab Tools)

Every tool inside **Field Kit** starts strictly **idle** and activates only when you press its explicit action button:

| Instrument | What It Does | Honest Scope & Privacy Boundary |
|:---|:---|:---|
| **Multi-view** | Displays Back camera, Front camera, and optional loopback Laptop MJPEG stream side-by-side (`127.0.0.1:8766` via `adb reverse`). | Live preview only — zero recording, zero frame upload, cleartext restricted strictly to loopback. |
| **Acoustic Ranging** | Emits one gentle 2 kHz, 20 ms chirp per tap and measures normalized echo correlation peaks (`343 × lag / 2`). | Uncalibrated timing candidate — not certified obstacle avoidance, SPL metrology, or navigation guidance. |
| **Tiny Zoe** | Native Android behavioral simulator for the **Zoe Cell** Java Card APDU protocol (`8002...` → `0003...9000`). | Bounded behavioral model — no SIM, NFC card, or carrier modification. |
| **Radio Field** | Reads bonded Bluetooth LE device metadata / one-tap GATT RSSI and NFC tag presence/ID. | RSSI is signal strength, not certified position; never reads or writes NFC tag payload contents. |
| **Location Field** | One-shot GPS/network fix with accuracy/age readout and optional straight-line haversine distance between 2 in-memory points. | 15-second timeout; Stop or leaving cancels and clears coordinates; **zero background tracking**. |
| **Connectivity** | Reports active transport/bandwidth estimate with an optional one-shot 1 MiB HTTPS speed sample (`speed.hetzner.de`). | Network check only on tap; never guarantees coverage or emergency service availability. |
| **Screen Space** | Opt-in AccessibilityService tool for explicit user-triggered screen captures and mapped gesture coordinates. | Requires manual Android Accessibility opt-in; never passively reads screen text, monitors events, or bypasses lock screens. |
| **App Observatory** | Lists launcher-visible installed app metadata using public launcher intents. | Read-only; never reads private app data, modifies Play Protect, or force-stops/uninstalls apps. |

---

## Further Reading

- **[Complete SafeConvert Documentation (`mobile/SAFECONVERT.md`)](SAFECONVERT.md)** — Deep dive into SafeConvert's cover converter, safe contacts, Talk to Zoe calming tools, SHA-256 proof vault, passcode lock, and privacy shields.
- **[Mobile Build & Architecture Guide (`mobile/README.md`)](README.md)** — Android Gradle, Apple Xcode, Swift `ZoeCore`, and conformance tests.
- **[Store Compliance Checklist (`mobile/STORE_COMPLIANCE.md`)](STORE_COMPLIANCE.md)** — Google Play & Apple App Store privacy, accessibility, and foldable guidelines.
- **[Zoe Constitution (`CONSTITUTION.md`)](../CONSTITUTION.md)** — Non-negotiable dignity, honesty, and epistemic boundaries.
