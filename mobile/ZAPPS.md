# Zoe (beta) — Complete Zapps Guide

Welcome to **Zoe (beta)** (`v0.9.3-beta`) — a free, offline-first, privacy-respecting companion app for **Android** and **Apple** (`iPhone`, `iPad`, and `iPhone Duo Fold`).

> **Core Promise (`CONSTITUTION.md`):** Nothing listens, watches, saves, or uploads until you explicitly tap. Every sensor starts idle, all app data stays private on your device (`allowBackup="false"`), and there are zero ads or tracking SDKs.

---

## Everyday Navigation & Accessibility

Zoe uses a calm, spacious **Google Gemini Material 3 Expressive** interface engineered for effortless scanning and motor comfort for both adults and children with disabilities:

- **Zoe GEM-Ellipsis Home Button:** Tap the **GEM-Ellipsis logo** in the top bar (or inside a Zapp) from **any screen** to jump straight back to the Zoe Home screen. On Home, tapping the GEM logo exits Arrange mode and smoothly scrolls back to the top.
- **Focused Top 3 + `More Zapps`:** Home surfaces your **Top 3 favorite Zapps** as spacious `74dp` / `74pt` pill cards above the fold, keeping cognitive load calm and clear, with all other Zapps tucked cleanly inside **More Zapps**.
- **`Explore | Arrange` Toggle:** Tap **Arrange** right on the Home screen to pin (`★`) any Zapp to `#1`, move Zapps up (`↑`) or down (`↓`), or tap **Reset** anytime.
- **Floating Bottom Action Capsule (`+ | Ask Zoe | 👁 | Live Talk`):** Always sits in the ergonomic lower thumb zone for one-tap access to Quick Menu, Talk with Zoe, Guided Vision, or Voice.
- **Appearance & Comfort:** Follows your phone's **Dark / Light** theme automatically (with a 1-tap Sun/Moon override in the top bar), uses `>= 48dp` / `48pt` touch targets, full TalkBack / VoiceOver labels, and an optional **Comfort Mode** (slower speech rate & gentler motion) inside the `=` / `+` Quick Menu.

---

## Home Zapps (15 Core Zapps)

| # | Zapp | Plain-English Purpose | Platforms | Network & Sensors |
|:-:|:---|:---|:---|:---|
| **1** | **Guided Vision** | Look around with your camera, read text/labels aloud, &amp; **teach Zoe unfamiliar objects** via offline contour memory + silent CPC-filtered patent structural priors | Android · Apple | Offline OCR, labels &amp; on-device Sobel contour memory (`VisionPriorStore`); camera stays OFF until **Start camera**; opt-in **Patent prior** filters to physical CPC classes (`A47/B25/F16/G01/G02/H01`) &amp; improves recognition silently in both Guided Vision &amp; Zoe Explore |
| **2** | **Talk** | Hybrid bubble chat with **Smart `⚡ Auto` Router**, **Zoe Local**, **Opt-In Live Web Grounding**, **`+ Attach` Photo & Video**, Native Voice & **Multi-AI Streaming** | Android · Apple | **Offline-first by default** (`Web: off` until tapped); attaches photos & 3-frame video analysis offline, runs MediaPipe LiteRT `.task` models locally, fetches zero-key HTTPS DuckDuckGo + Wikipedia citations on demand, & streams multi-turn BYOK (**Gemini, Claude, ChatGPT, Grok, Local OpenAI**) |
| **3** | **Zoe Explore** | Clean, uncluttered 60fps breathing **Voice Orb**, **`✦ AR Space`** (ARCore / ARKit 6DoF floating 3D Zoe prism), **`Live + Cam`** simultaneous sight + voice, &amp; opt-in **`"Hi Zoe"`** wake-word | Android · Apple | Mic, camera, ARCore/ARKit &amp; `"Hi Zoe"` start **strictly OFF** until tapped; rotation-resilient, silently enriched by Guided Vision's offline learned visual memory + AR physical scale + exact stamped OCR patent IDs (zero noisy popups) |
| **4** | **Creative Studio** | **Scientific-Aesthetic Image Lab** (**Ernst Haeckel** *Kunstformen der Natur*, **August Weismann**, **Jean-Baptiste Lamarck**, & **Google Patents** orthographic blueprints + photo editor) + native offline **H.264 MP4 Video Maker** | Android · Apple | **100% offline mathematical plate synthesis, editing & MP4 encoding** ($D_n$ radiolarian phyllotaxis $137.508^\circ$, logarithmic spirals $r=ae^{b\theta}$, mitotic spindles, orthographic blueprints, zero watermarks); optional BYOK AI art automatically grounded by active scientific baseline |
| **5** | **Zoe Arcade** | 4 ad-free offline games: **GEM Memory**, **Tic-Tac-Toe**, **Kloster Signal**, & **20 Questions** | Android · Apple | **100% offline, zero ads, zero tracking** — musical harmonic chimes, Kid Mode & Unbeatable Minimax AI, strict $A_\tau(p)$ puzzle, & mystery trivia |
| **6** | **Privacy Vault** | Signal-grade **AES-256-GCM** encrypted chat vault, **ECDH/HKDF E2EE**, & **60-digit Safety Number** | Android · Apple | Hardware AndroidKeyStore / Apple CryptoKit P-256 ECDH + HKDF-SHA256 + Symmetric Chain Ratchet + AES-256-GCM at-rest encryption & 1-tap share via Signal |
| **7** | **Trip Journal** | Save field sightings, photos, and private travel/research notes | Android *(Apple planned)* | Private on-device storage; optional explicit export or workstation sync |
| **8** | **Eliza-GEM Studio** | Interactive Chladni sound-shape synth, **Sing Zoe**, **Closed-Loop L5 Digestion (`Feed & Digest into Zoe Lab`)**, and Workstation Lab Bridge | Android · Apple Core (`MobileDigestionCore`) | Chladni & **Sing Zoe** are **100% offline**; Lab Bridge & **Feed & Digest** (`/api/digest/mobile`) connect only on tap (`127.0.0.1:8765` or HTTPS) with strict privacy firewall (`SafeConvert`, `Privacy Vault`, raw photos & chat bodies hard-excluded) |
| **9** | **Maps & Safety** | Active OS GPS, compass, Google Maps & Apple Maps handoffs, Personal Safety & Flashlight | Android · Apple | Starts **strictly idle**; opt-in one-shot or live OS GPS + compass + Geocoder (stops automatically on exit); native Apple `MapKit` on iOS; zero Maps API keys or tracking SDKs |
| **10** | **Accessible Volume** | Calculate Nicholas Michael Kloster's strict threshold equation $A_\tau(p)$ | Android · Apple | **100% offline** math — zero permissions |
| **11** | **Trinity** | Synchronize Phone + Laptop + Tiny Zoe in one shared measurement deck | Android · Apple | Explicit user-initiated local bridge (`127.0.0.1:8767` / private LAN pairing) |
| **12** | **Field Kit** | Houses 8 specialized camera, audio, radio, GPS, and protocol instruments | Android | Every instrument inside starts **strictly idle** |
| **13** | **Device Field** | Check real battery, thermal state, sensor counts, speech engine & speaker | Android · Apple | Local public OS APIs only — zero network |
| **14** | **SafeConvert** | Clean offline unit converter with an international (8-region, 5-language) discreet safety companion (type variants of `911` — e.g., `911`, `9.11`, `919`, `119`, `999`, `111` — in the converter to open), trauma-informed post-incident care, calming art/math/story studio, Young Child Easy Picture Mode, SHA-256 vault & offline BLE Help Beacon Mesh | Android · Apple | **100% offline zero-network WebView**; opt-in 1-shot GPS locator & offline Bluetooth LE rotating-tag beacon start strictly OFF and stop instantly on `✕ EXIT` — see [Complete SafeConvert Guide](SAFECONVERT.md) |
| **15** | **Researcher Guide** | Built-in offline guide explaining Zoe's architecture, verification & boundaries | Android | **100% offline** documentation |

---

### Detailed Breakdown of Every Home Zapp

#### 1. Guided Vision (`Look around & read aloud`)
- **What it does:** Helps you read signs, pages, medicine labels, or identify everyday surroundings calmly.
- **How it works:** The camera starts **off**. Tap **Start camera**, point at what you want to check, and tap **Inspect once** to capture a single frame. On Android it runs bundled offline ML Kit OCR + image labeling + color palette extraction (plus optional on-device Gemini Nano if supported); on Apple it uses Apple's native Vision framework (`VNRecognizeTextRequest` + `VNClassifyImageRequest`).
- **Boundaries:** Keeps OCR text, labels, and optional descriptions separate. Never auto-uploads photos and never claims safety/medical/object-identity certainty.

#### 2. Talk (`Hybrid Chat, Local LLM, Web & Council`)
- **What it does:** A calm, transparent hybrid chat-first bubble interface blending **offline privacy** with **opt-in online capability**:
  - **Top Live Brain Switcher & Smart `⚡ Auto` Router:** Switch in one tap between **`⚡ Auto`** (routes memory/device actions to `<5 ms` `Zoe Stem`, uses your configured online frontier model if keyed, or streams locally via `Zoe Local 1.5B` with automatic offline fallback), **`Zoe Local`** (Android MediaPipe GenAI running open-weight 0.5B / 1.5B / 135M LiteRT `.task` packs offline with fresh-session sampling & live streaming), **`Web: off/on`** (opt-in zero-key HTTPS DuckDuckGo + Wikipedia grounding with clickable `🔗 Source ↗` chips right on the reply card), **`Zoe Stem`**, **`Lab Brain`**, and **`Cloud AI`** (multi-turn SSE streaming for optional **Google Gemini, Anthropic Claude, OpenAI ChatGPT, xAI Grok**, or any local OpenAI-compatible server).
  - **Collapsible Glass-Box Telemetry:** Every Zoe reply card includes an expandable `✦ Glass-Box Telemetry` readout showing live stem tier, Kloster $A_{0.08}(p)$, latency, citation, and constitutional honesty flags (`sentience_claimed=false`, `clone_claimed=false`).
  - **Approval-Gated Multi-Step Action Plans:** Ask compound phone commands like *"Navigate to nearest hospital and set a 5 minute timer"* — Zoe splits them into numbered tap-to-approve steps (`Step 1`, `Step 2`, ...) and **never auto-executes** anything without your tap.
  - **Zero-Key Native AI Handoffs & Multi-AI Council:** Tap **`Ask AI ↗`** to send your prompt straight into installed **Claude** (`claude://` prefill), **Grok**, **ChatGPT**, **Gemini**, or **Share Sheet (Meta Muse)** — or run **In-App Multi-AI Council** to compare replies side-by-side with a lexical agreement score.
  - **Private Multi-Thread History & Native Voice:** Persistent private chat threads (`allowBackup="false"`), `remember` / `relay` / `recall` SHA-256 memory, **Caption mode**, installed OS voices or **Zoe Synth** (44.1 kHz Rosenberg-Klatt), and **`Sing Zoe`**.

#### 3. Trip Journal (`Your saved notes & photos`)
- **What it does:** Private on-device notebook for saving Guided Vision inspections, color palettes, field observations, and timestamped trip entries.
- **Privacy:** Stored strictly in app-private storage (`allowBackup="false"`). Nothing leaves the device unless you tap **Export** or explicitly sync with your workstation.

#### 4. Eliza-GEM Studio (`Sound shapes & local lab`)
- **What it does:** Combines two offline creative sound instruments with your live workstation research bridge:
  - **Chladni Cymatics Resonance Pad (100% offline):** Touch and drag across either the **Square Atelier** plate or the **Languidou Bronze Rose Disc** to sweep physical nodal eigenmodes visually and tap **Play Chladni Chord** to hear the live harmonic chord synthesized on-device.
  - **Sing Zoe (Native Voice) (100% offline):** Sings Zoe's warm soprano theme directly via the 44.1 kHz Rosenberg-Klatt synthesizer.
  - **Eliza-GEM Workstation Bridge & Closed-Loop L5 Digestion (explicit connect):** Connects over loopback USB (`http://127.0.0.1:8765` via `adb reverse`) or remote HTTPS to chat with workstation Gear 1 ELIZA / Gear 2 Local Qwen2.5-3B, pin lab relays, **Feed & Digest into Zoe Lab** (`/api/digest/mobile` — sends privacy-firewalled learned visual prototypes, Brain notes, textual Trip sightings, and aggregated Kloster $A_\tau(p)$ telemetry while hard-excluding SafeConvert, Privacy Vault, raw photos, and private chat transcripts, consolidates & enriches prototypes against the Haeckel/Lamarck/CPC atlas, evaluates empirical gain vs. control with zero forgetting, and syncs refined priors back to the phone while preserving `l5_agi_qualified=false`), and inspect or live-run the **L5 Phase 5 Frontier**, **L5 Phase 4 Embodied**, and **L5 Phase 3 Agentic** scorecards.
  - **Cloud AI Key drawer:** Optional, locally stored Gemini API key and model selector (never backed up to cloud; HTTPS only when you tap).

#### 5. Maps & Safety (`Live GPS, Google & Apple Maps, Personal Safety`)
- **What it does:** Harnesses your phone's built-in GPS, compass, geocoder, Maps apps, Personal Safety / Medical ID, and hardware flashlight with **zero Maps API keys and zero tracking SDKs**.
- **How it works:**
  - Starts **strictly idle** until you tap **Locate once** or toggle **Live location: on** (automatically pauses GPS & compass the moment you leave the screen).
  - Displays live coordinates, accuracy, altitude, speed (km/h & mph), compass heading (`N/NE/E/...`), OS street address (via Android `Geocoder` / Apple `CLGeocoder`, never fabricated offline), and Point 1 → Point 2 straight-line distance. On Apple, also renders a live native **`MapKit`** pin map right inside Zoe.
  - **Dual Maps Handoff:** One-tap **Navigate**, **Search Maps**, **Open Pin / Directions**, and **Share Live Pin** (sends a universal message containing both Google Maps and Apple Maps pin links).
  - **Built-In Phone Safety & Tools:** Launches Pixel's **Personal Safety** (`com.google.android.apps.safetyhub` / Android Emergency Info) on Android or **Health / Medical ID** + Emergency SOS guidance on Apple, alongside one-tap **SafeConvert**, hardware **Flashlight**, and **Emergency Dialer** (`tel:911`, never auto-dials).

#### 6. Accessible Volume (`Count open choices clearly`)
- **What it does:** Interactive calculator for **Operational Metacognition** ($A_\tau(p) = |\{x : p(x) > \tau\}|$), originated by **Nicholas Michael Kloster on March 6, 2026**.
- **Why it matters:** Measures *how many alternatives remain open* strictly above threshold $\tau$ (equality is excluded) — explicitly separating forecast breadth from correctness or action authorization.

#### 7. Trinity (`Link phone & computer`)
- **What it does:** Synchronizes three measurement planes — **Tiny Zoe** (quantized Q0.15 APDU witness), **Phone** (floating-point native UI), and **Laptop** (observation deck + optional hash-verified journal) — verifying identical accessible volume and revision hashes across all three. See [TRINITY.md](TRINITY.md).

#### 8. Field Kit (`Cameras, GPS & sensor tools`)
- **What it does:** Cleanly organizes **8 specialized hardware, radio, and protocol lab tools** out of the first-run home screen so beginners never feel overwhelmed. See the full **Field Kit Instruments** table below.

#### 9. Device Field (`Battery & speaker check`)
- **What it does:** Displays real, unfabricated local device observations (battery percentage/charging state, thermal status, sensor counts, on-device speech availability) plus an explicit **Speaker check** button. Never invents unavailable OS metrics.

#### 10. SafeConvert (`Units & private safety helper`)
- **What it does:** Presents a calm, fast, ad-free **Unit Converter** (Length, Weight, Temperature, Volume) styled to match Zoe seamlessly — while containing a completely offline, panic-exit-protected **private safety companion & SHA-256 proof vault** for adults and children who may be in danger or have a monitored phone.
- **How to open the hidden safety companion:** Type any **variant of `911`** into the unit converter input (`911`, `991`, `919`, `199`, `119`, `191`, `999`, or `111` — decimals and leading zeros like `9.11` or `0.911` also work). Tap **`✕ EXIT`** or press Back anytime to snap instantly back to the converter.
- **Read the full guide:** **[`mobile/SAFECONVERT.md`](SAFECONVERT.md)** — documents every single feature, privacy shield, calming tool, hotline directory, proof vault lock, and honest safety boundary in detail.

#### 11. Researcher Guide (`How Zoe works & limits`)
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
