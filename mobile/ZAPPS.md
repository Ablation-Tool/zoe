# Zoe (beta) — Complete Zapps & Capabilities Guide (`v0.9.5-beta`)

Welcome to **Zoe (beta)** (`v0.9.5-beta`) — a free, offline-first, privacy-respecting mobile companion for **Android** and **Apple** (`iPhone`, `iPad`, and `iPhone Duo Fold`), containing **15 Core Home Zapps** plus **8 Specialized Field Kit Instruments** (**23 built-in tools** total).

> **Constitutional Promise — No Deception (`CONSTITUTION.md`):**
> - **Explicit Opt-In Only:** Nothing listens, watches, saves, transmits, or executes an external action until you explicitly tap. Every camera, microphone, GPS, AR, BLE, and network lane starts strictly **OFF**.
> - **Private by Default:** App-private storage uses `android:allowBackup="false"` and `android:fullBackupContent="false"` with zero ads, zero analytics, and zero tracking SDKs.
> - **Strict Epistemic Boundaries:** `measurement ≠ evidence ≠ belief update ≠ action`. Zoe is transparent open-source software — not conscious, not sentient, not a clinical/medical/legal authority, and not AGI (`sentience_claimed = False`, `zoe_clone_claimed = False`, `l5_agi_qualified = False`, `clinical_action_authorized = False`).

---

## Everyday Navigation & Accessibility

Zoe uses a calm, symmetrical **Google Gemini Material 3 Expressive** interface (`16dp` outer rails, `8dp` gutters, `20dp` concentric cards) designed for effortless scanning and motor comfort for adults and children, including people with disabilities:

- **Zoe GEM-Ellipsis Home Button:** Tap the **GEM-Ellipsis emblem** in the top bar from **any screen** to return straight to the Home screen. On Home, tapping it exits Arrange mode and scrolls smoothly back to the top.
- **Focused Top 3 + `Explore more`:** Home surfaces your **Top 3 favorite Zapps** as spacious pill cards above the fold so cognitive load stays calm, with the rest organized cleanly under **Explore more**.
- **`Arrange` Toggle:** Tap **Arrange** on Home to pin (`★`) any Zapp to `#1`, reorder Zapps up (`↑`) or down (`↓`), or **Reset** anytime.
- **Floating Bottom Action Capsule (`+ | Ask Zoe | 👁 | Explore Orb`):** Anchored in the ergonomic lower thumb zone for one-tap access to Quick Menu, Talk, Guided Vision, or **Zoe Explore's Iridescent Aurora Live Voice Orb**.
- **Appearance, Motion & Comfort:** Follows system **Dark / Light** theme automatically (plus a 1-tap Sun/Moon toggle), handles Portrait↔Landscape rotation seamlessly across **all 20 Android Activities** without losing session state, delivers subtle Apple/Pixel press-spring physics & tactile haptics on controls, provides `>= 48dp/pt` touch targets with TalkBack / VoiceOver labels, and includes an optional **Comfort Mode** (slower speech rate and reduced/calmer motion).

---

## 15 Core Home Zapps — Overview Table

| # | Zapp | Plain-English Purpose | Platform Status *(Honest Scope)* | Sensors, Storage & Network |
|:-:|:---|:---|:---|:---|
| **1** | **Guided Vision** | Point your camera to read text (OCR), preview captured frame thumbnails, identify objects aloud, & **teach Zoe unfamiliar objects** offline | Android *(Pixel 7 verified)* · Apple *(SwiftUI source + `ZoeCore` tested)* | Camera starts **OFF**; bundled offline ML Kit OCR/labels + 18-archetype clean-room Haeckel/Lamarck/CPC Offline Visual Atlas (`8.4 KB`) + `< 0.1 ms` RAM-cached `VisionPriorStore`; optional AICore Gemini Nano & opt-in CPC physical `Patent prior` (HTTPS only on tap) |
| **2** | **Talk** | Hybrid chat with **Smart `⚡ Auto` Router**, **Zero-Prefill KV-Clone Local LLM**, **`< 2 ms` Math/Units/Clock**, inline `**bold**`/`code` formatting, Opt-In Web Grounding, **`+ Attach` Photo/Video**, & **Multi-AI Streaming** | Android *(Pixel 7 verified)* · Apple *(SwiftUI source + `ZoeCore` tested)* | **100% offline by default** (`Web: off` until tapped); local MediaPipe LiteRT `.task` models (GPU-first + CPU fallback + native `MPImage` vision packs), zero-key DuckDuckGo/Wikipedia citations on tap, optional BYOK streaming (**Gemini, Claude, ChatGPT, Grok, Local OpenAI**), encrypted on-device threads (`AES-256-GCM`) |
| **3** | **Zoe Explore** | Zero-allocation 60fps **Iridescent Fluid Aurora Voice Orb**, **`✦ AR Space`** (ARCore / ARKit 6DoF floating 3D Zoe prism), **`Live + Cam`**, & opt-in **`"Hi Zoe"`** wake-word | Android *(Pixel 7 verified)* · Apple *(SwiftUI / ARKit source + `ArExploreCore` tested)* | Mic, camera, ARCore/ARKit & `"Hi Zoe"` start **strictly OFF**; silently enriched by Guided Vision's learned offline prototypes, AR physical scale, & exact stamped OCR patent IDs (zero noisy popups) |
| **4** | **Creative Studio** | **Creative Studio Pro** — **10 HD (`1280×960`) Scientific Plates** (Atelier, Haeckel, Ammonite, Weismann, Lamarck, Patent Blueprint, Chladni, Fibonacci Phyllotaxis, **Voronoi Crystal**, **Lissajous Orbit**), **12 filters** (**Golden Hour**, **Cyber Neon**, **Matte Film**), live **✎ Draw** Bezier vector ink bar, live **Tune sliders**, 16-step Undo, hold-to-compare, Gallery save &amp; exact-CFR **720×720 30fps HD MP4 Video Maker** (6 styles) | Android *(Pixel 7 verified)* · Apple *(SwiftUI Canvas + `CreativeAndArcadeCore` tested)* | **100% offline** HD plates, vector ink drawing, editing &amp; 30fps H.264 MP4 synthesis (zero watermarks); saves to Photos/Movies ONLY when you tap; optional BYOK Gemini Imagen / OpenAI AI Art grounded by active plate |
| **5** | **Zoe Arcade** | 4 ad-free offline games: **GEM Memory**, **Tic-Tac-Toe** (with winning-line glow), **Kloster Signal** (live graphical bar visualizer + threshold haptic detents), &amp; **20 Questions** | Android *(Pixel 7 verified)* · Apple *(SwiftUI + `CreativeAndArcadeCore` tested)* | **100% offline, zero ads, zero tracking** — musical harmonic chimes, Kid Mode &amp; Minimax AI, strict $A_\tau(p)$ graphical puzzle, &amp; mystery trivia |
| **6** | **Privacy Vault** | Signal-inspired **AES-256-GCM** encrypted storage, **P-256 ECDH / HKDF-SHA256** E2EE envelopes, & **60-digit Safety Number** | Android *(Pixel 7 verified)* · Apple *(CryptoKit SwiftUI + `ZoeSignalAndWakeCore` tested)* | Hardware `AndroidKeyStore` / Apple CryptoKit keys; never uploads keys or envelopes automatically; **hard-excluded** from workstation digestion |
| **7** | **Trip Journal** | Save field sightings, OCR snippets, color palettes, compact thumbnails & private research notes | Android *(Pixel 7 verified)* · Apple *(planned)* | App-private storage (`allowBackup="false"`); saves thumbnails ONLY when you explicitly tap Save; raw photos are never uploaded during workstation digestion |
| **8** | **Eliza-GEM Studio** | Offline **Chladni Cymatics** resonance pad, **Sing Zoe**, **Closed-Loop L5 Digestion (`Feed & Digest Lab`)**, & Workstation Bridge | Android *(Pixel 7 verified)* · Apple Core (`MobileDigestionCore` tested) | Chladni & **Sing Zoe** (`44.1 kHz`) run **100% offline**; Lab Bridge & **`Feed & Digest Lab`** (`/api/digest/mobile`) connect ONLY on explicit tap (`127.0.0.1:8765` or HTTPS) with strict privacy firewall |
| **9** | **Maps & Safety** | Active OS GPS, compass, Geocoder, Google/Apple Maps handoffs, Personal Safety / Medical ID & Flashlight | Android *(Pixel 7 verified)* · Apple *(SwiftUI + `MapKit` + `OsToolsBridge` tested)* | Starts **strictly idle** and stops automatically on exit; zero Maps API keys or tracking SDKs; never auto-dials emergency services |
| **10** | **Accessible Volume** | Calculate Nicholas Michael Kloster's strict threshold equation $A_\tau(p) = \sum_x \mathbf{1}[p(x) > \tau]$ | Android *(Pixel 7 verified)* · Apple *(SwiftUI + `ZoeCore` tested)* | **100% offline** math — zero permissions; equality is strictly excluded (`p(x) > τ`) |
| **11** | **Trinity** | Synchronize **Phone + Laptop + Tiny Zoe** in one hash-verified three-plane measurement deck | Android *(Pixel 7 verified)* · Apple *(SwiftUI source + `TrinityModels` tested)* | Explicit user-initiated loopback (`127.0.0.1:8767`) or private-LAN pairing; zero cloud, camera, or mic |
| **12** | **Field Kit** | Houses **8 specialized camera, audio, radio, GPS, accessibility & protocol instruments** | Android *(Pixel 7 verified)* | Every instrument inside starts **strictly idle** until its explicit action button is tapped |
| **13** | **Device Field** | Check real local battery, thermal state, sensor counts, speech engine availability & speaker check | Android *(Pixel 7 verified)* · Apple *(SwiftUI source)* | Public OS APIs only — zero network; never invents unavailable OS metrics |
| **14** | **SafeConvert** | Clean offline Unit Converter whose hidden **international safety companion** opens by typing **variants of `911`** (`911`, `9.11`, `919`, `119`, `999`, `111`), with 8 regions, 5 languages, calming studio, SHA-256 proof vault & Offline BLE Help Beacon Mesh | Android *(Pixel 7 verified)* · Apple *(WKWebView + `SafeBeaconMeshCore` tested)* | **100% offline zero-network WebView**; opt-in 1-shot GPS & BLE beacon (`~30–80 m`, 30-min auto-expiry) start OFF & shut off immediately on `✕ EXIT`; **hard-excluded** from workstation digestion — see [SAFECONVERT.md](SAFECONVERT.md) |
| **15** | **Researcher Guide** | Built-in offline walkthrough of Zoe's architecture, build/verification steps & epistemic limits | Android *(Pixel 7 verified)* | **100% offline** reference inside the app |

---

## Detailed Breakdown of All 15 Home Zapps

### 1. Guided Vision (`Look around & read aloud`)
- **What it does:** Helps you read signs, pages, labels, or identify unfamiliar physical objects calmly, and lets Zoe genuinely learn new objects offline over time.
- **How it works:**
  - Camera starts **OFF** until you tap **Start camera** (bounded 720p CameraX analysis on Android; `AVCaptureSession` on Apple).
  - Tapping **Inspect once** runs bundled offline OCR + image labeling + zero-GC primitive color palette extraction (`FramePalette`) + optional quiet public AICore Gemini Nano description (with 5-second atomic timeout guard; transparently reports unavailable status like `601-BINDING_FAILURE` rather than fabricating a description).
  - **Self-Improving Structural Visual Memory (`VisionPriorStore`):** Extracts an illumination-invariant Sobel contour signature (HoG-16, Radial-8, dHash-64, aspect ratio, bilateral symmetry) and checks user-taught prototypes first (`< 0.1 ms` RAM-cached offline), then falls back at a stricter threshold to the bundled **18-archetype clean-room Haeckel/Lamarck/CPC Offline Visual Atlas (`zoe_visual_atlas.json`, `8.4 KB`)**.
  - **Teach Zoe & Opt-In CPC Patent Prior:** Tap **Teach Zoe** to label an object offline (repeated confirmations refine the prototype via L2-normalized running mean), or enable optional **Patent prior** (explicit HTTPS lookup filtered to physical CPC classes `A47/B25/F16/G01/G02/H01`) to reinforce structural recognition silently across both Guided Vision and Zoe Explore.
- **Honest Boundaries:** Keeps OCR text, labels, visual contour matches, and AI descriptions strictly separate. Never auto-uploads photos and never claims safety, medical, or object-identity certainty.

### 2. Talk (`Hybrid Chat, Zero-Prefill Local LLM, Web & Council`)
- **What it does:** A transparent, bubble-based hybrid chat blending **offline privacy** with **opt-in online capabilities**:
  - **Smart `⚡ Auto` Router & Live Brain Switcher:** Switch in one tap between **`⚡ Auto`**, **`Zoe Stem`** (`< 5 ms` offline glass-box brain with `< 2 ms` deterministic recursive-descent Math, Exact Unit Conversion, and Real-Time Device Clock), **`Zoe Local`** (Android MediaPipe `tasks-genai:0.10.35` running user-imported `.task` models offline with **GPU-first + automatic CPU fallback**, **zero-prefill KV-cache `cloneSession()`**, instant `cancelGenerateResponseAsync()` barge-in, and native **`addImage(MPImage)`** vision-language support when a multimodal pack is loaded), **`Web: off/on`** (opt-in zero-key HTTPS DuckDuckGo + Wikipedia citations rendered as clickable `🔗 Source ↗` chips), **`Lab Brain`** (workstation Eliza-GEM bridge), and **`Cloud AI`** (multi-turn SSE streaming for optional user-supplied BYOK **Gemini, Claude, ChatGPT, Grok**, or local OpenAI-compatible servers).
  - **Multimodal `+ Attach` Photo & Video:** Runs parallel offline ML Kit OCR + image labeling (plus 3-frame video sampling) and passes live frames directly into multimodal local or user-approved cloud models.
  - **Collapsible Glass-Box Telemetry:** Every reply includes an expandable telemetry badge showing active stem tier, Kloster $A_{0.08}(p)$ option breadth, latency, citation, and constitutional honesty flags (`sentience_claimed=false`, `clone_claimed=false`).
  - **Approval-Gated Action Plans:** Compound device requests (e.g., *"Navigate to the pharmacy and set a 5 minute timer"*) produce numbered tap-to-approve buttons (`Step 1`, `Step 2`, ...) and **never auto-execute**.
  - **Encrypted Private History & Voice:** Multi-thread chat history encrypted at rest (`AndroidKeyStore AES-256-GCM`), SHA-256 `remember`/`relay`/`recall` memory, **Caption mode**, OS voices or **Zoe Native Synth** (`44.1 kHz` Rosenberg-Klatt), and **`Sing Zoe`**.

### 3. Zoe Explore (`Live Voice Orb, ✦ AR Space & Live + Cam`)
- **What it does:** Clean, uncluttered real-time multimodal exploration combining a 60fps breathing **Voice Orb**, simultaneous **`Live + Cam`** sight + voice, optional **`"Hi Zoe"`** wake-word listening, and **`✦ AR Space`**.
- **How it works:**
  - Mic, camera, ARCore/ARKit, and `"Hi Zoe"` start **strictly OFF** until tapped.
  - **ARCore (Android) / ARKit (Apple) 6DoF Space:** Tracks real physical planes, floats a luminous 3D Zoe GEM prism that glides to tapped surfaces (60fps zero-GC `FloatBuffer` pipeline), remembers discovered room locations, and asks curious spoken questions aloud with abbreviation-safe sentence streaming and instant voice barge-in.
  - **Silent Guided Vision Transfer:** Automatically queries `VisionPriorStore` + Offline Visual Atlas silently (`< 0.1 ms`) and pairs real AR physical scale + stamped OCR patent IDs without cluttering the screen with raw patent popups.
  - Survives Portrait↔Landscape rotation seamlessly without dropping active voice/camera state.

### 4. Creative Studio (`Creative Studio Pro — HD Image Lab, Vector Ink & 30fps MP4 Video Maker`)
- **What it does:** 100% offline HD mathematical art synthesis, finger-painted Bezier vector ink drawing, full non-destructive photo editing, and exact-CFR 720×720 30fps H.264 MP4 video rendering — grounded in factual geometry and natural history.
- **How it works:**
  - **10 HD (`1280×960`) Scientific-Aesthetic Baseline Plates (`ScientificVisualSubstrate`):** Renders deterministic mathematical plates inspired by **Atelier**, **Ernst Haeckel** (*Kunstformen der Natur* $D_n$ radiolarian symmetry & logarithmic ammonite spirals), **August Weismann** (cellular mitotic spindles), **Jean-Baptiste Lamarck** (morphospace branching & phyllotaxis), **Orthographic Patent Blueprints**, **Ernst Chladni** standing-wave nodal interference plates, **Fibonacci Phyllotaxis** ($137.508^\circ$ golden-angle `(13, 21)` parastichy spirals), **Georgy Voronoi** stained-glass cellular crystal tessellations, and **Jules Lissajous** harmonic phase curves.
  - **Non-Destructive Photo Lab & Live `✎ Draw` Ink Layer:** **12 archival & film filters** (including **Golden Hour**, **Cyber Neon**, **Matte Film**, **Vellum** & **Blueprint**), active-chip selection highlights, collapsible **✎ Draw** finger-painting bar (6 color swatches, `S / M / L` quadratic-Bezier nibs, `Clear Ink`, full Undo support), collapsible **Tune ▾** sliders (**Brightness, Contrast, Warmth, Saturation, Vignette**), **16-step Undo**, **Hold-to-Compare Before/After**, 90° rotate, horizontal flip, `1:1 / 4:5 / 16:9` crops, privacy blur, plain-English command bar, direct **Save to Photos** (`Pictures/Zoe Studio`), PNG Share, and optional BYOK **Google Gemini Imagen / OpenAI** AI Art grounded by the active plate.
  - **Exact-CFR 30fps HD MP4 Video Maker:** Live animated `▶ Preview` / `⏸ Pause` (plus 1-tap toggle right on the preview canvas), **6 offline animated styles** (**Chladni Wave**, **Photo Story Reel** with cosine-eased Ken Burns, **Starlight GEM**, **Haeckel Living**, **Patent Kinetic**, and **Lissajous Orbit**), 4 color palettes, selectable `4s / 6s / 8s HD` durations, real `720×720 @ 30fps` monotonic-timestamp H.264 `.mp4` encoding via Android `MediaCodec`/`MediaMuxer`, direct **Save to Movies** (`Movies/Zoe Studio`), and MP4 Share.

### 5. Zoe Arcade (`4 Ad-Free Offline Games`)
- **What it does:** Calm, playful, completely offline games built for adults and kids with zero ads, zero loot boxes, and zero tracking:
  1. **GEM Memory:** Harmonic musical pattern recall with gentle chimes.
  2. **Tic-Tac-Toe:** Switchable **Kid Mode** and **Unbeatable Minimax AI**.
  3. **Kloster Signal:** Interactive puzzle teaching strict threshold filtering $A_\tau(p)$.
  4. **20 Questions:** Offline mystery deduction game.

### 6. Privacy Vault (`Signal-Inspired E2EE & Encrypted Storage`)
- **What it does:** Provides hardware-backed local encryption and peer-to-peer sealed message envelopes with verifiable Safety Numbers.
- **How it works:**
  - Generates hardware-backed keys (`AndroidKeyStore` on Android; Apple `CryptoKit` on iOS), performs **P-256 ECDH + HKDF-SHA256 + Symmetric Chain Ratchet + AES-256-GCM** sealing/unsealing, computes a **60-digit Safety Number** for out-of-band key verification, and offers 1-tap sharing via Signal or Android/iOS Share Sheet.
- **Honest Boundary:** **Hard-excluded** from workstation L5 digestion. While built on standard cryptographic primitives, it has **not** undergone an independent third-party cryptographic security audit and is not a substitute for audited Signal messaging in high-risk adversarial environments.

### 7. Trip Journal (`Private Field Sightings & Notes`)
- **What it does:** Private on-device notebook for saving Guided Vision inspections, OCR text, object labels, color palettes, compact thumbnails, and timestamped field notes.
- **Privacy:** Stored strictly in app-private storage (`allowBackup="false"`). Thumbnails are saved ONLY when you tap **Save**, and **never uploaded** during workstation digestion (only user-consented textual metadata is included if you run `Feed & Digest Lab`).

### 8. Eliza-GEM Studio (`Offline Chladni, Sing Zoe & Closed-Loop L5 Digestion`)
- **What it does:** Pairs offline acoustic instruments with your explicit workstation research & continual self-improvement bridge:
  - **Chladni Cymatics Pad (100% offline):** Touch and drag the **Square Atelier** or **Languidou Bronze Rose Disc** to sweep physical nodal eigenmodes visually and play real synthesized harmonic chords.
  - **Sing Zoe (100% offline):** Sings Zoe's soprano theme using the native `44.1 kHz` Rosenberg-Klatt synthesizer.
  - **Closed-Loop Mobile ↔ Workstation L5 Digestion (`Feed & Digest Lab`, explicit tap):** Connects over USB loopback (`http://127.0.0.1:8765` via `adb reverse`) or user-configured HTTPS to `POST /api/digest/mobile`:
    - **Strict Double-Sided Privacy Firewall:** Both phone (`MobileDigestionBundle` / Swift `MobileDigestionCore`) and workstation (`validate_privacy_firewall`, returning HTTP 400 on violation) hard-exclude **SafeConvert**, **Privacy Vault**, **raw photos/thumbnails**, and **private chat message bodies**.
    - **Real Consolidation & Bidirectional Feedback:** Merges mobile-learned `VisionPriorStore` prototypes with the 18-archetype Haeckel/Lamarck/CPC atlas, digests Brain notes & textual Trip sightings into SHA-256 `ZoeUnifiedMemory` for immediate workstation recall, calibrates Kloster $\tau^*$ from aggregated routing metrics, verifies empirical gain vs. an undigested control with `100%` zero-forgetting atlas retention, and **syncs refined visual prototypes back to the phone** without downgrading stronger local user-confirmed entries.
    - **Honest AGI Telemetry:** Always reports `l5_agi_qualified = false`, `zoe_clone = false`, and explicit remaining AGI gaps.
  - **Workstation L5 Scorecards & Cloud AI Key Drawer:** Inspect or live-run L5 Phases 3, 4 & 5 on your workstation, pin Lab Relays, or optionally store a local Gemini API key (`allowBackup="false"`).

### 9. Maps & Safety (`Live OS GPS, Dual Maps & Personal Safety`)
- **What it does:** Uses built-in OS GPS, compass, Geocoder, native Google/Apple Maps handoffs, Personal Safety / Medical ID, and hardware Flashlight with **zero Maps API keys and zero tracking SDKs**.
- **Boundaries:** Starts strictly idle, pauses automatically when you leave the screen, never fabricates street addresses offline, and never auto-dials emergency numbers (`tel:911` opens the dialer for your deliberate tap).

### 10. Accessible Volume (`Operational Metacognition Calculator`)
- **What it does:** Interactive calculator for **Nicholas Michael Kloster's** strict threshold equation $A_\tau(p) = |\{x \in X : p(x) > \tau\}|$ (originated March 6, 2026). Equality is strictly excluded (`p(x) > τ`), explicitly separating forecast option breadth from correctness or authorization.

### 11. Trinity (`Three-Plane Phone + Laptop + Tiny Zoe Deck`)
- **What it does:** Synchronizes **Tiny Zoe** (quantized Q0.15 APDU witness), **Phone** (floating-point native UI), and **Laptop** (local observation deck + optional hash-verified journal), verifying identical accessible volume and revision hashes across all three. See [TRINITY.md](TRINITY.md).

### 12. Field Kit (`8 Specialized Hardware & Protocol Lab Tools`)
- Cleanly keeps 8 advanced instruments out of the everyday Home view so first-time users never feel overwhelmed. See the **Field Kit Instruments** table below.

### 13. Device Field (`Real Local Device Observations`)
- Displays unfabricated public OS observations (battery %, charging state, thermal status, sensor counts, on-device speech availability) plus an explicit **Speaker check** button.

### 14. SafeConvert (`Unit Converter & Hidden International Safety Companion`)
- **What it does:** Presents a fast, ad-free **Unit Converter** (Length, Weight, Temperature, Volume) matching Zoe's theme — while containing a 100% offline, panic-exit-protected **international safety companion, trauma-informed medical/forensic care guide, calming & young-child studio, SHA-256 private proof vault, and offline Bluetooth LE Help Beacon Mesh**.
- **How to open the hidden safety companion:** Type any **variant of `911`** into the unit converter input (`911`, `991`, `919`, `199`, `119`, `191`, `999`, or `111` — decimals and leading zeros like `9.11`, `91.1`, or `0.911` also work). Tap **`✕ EXIT`**, tap the top bar, press **Back / `ESC`**, or switch apps anytime to immediately cut voice/BLE, wipe ephemeral canvas/chat, lock any passcode vault, and return to the converter.
- **Read the complete guide:** **[`mobile/SAFECONVERT.md`](SAFECONVERT.md)**.

### 15. Researcher Guide (`Built-In Offline Architecture & Limits`)
- Offline reference inside Zoe explaining the first-five-minutes walkthrough, build/verification commands, privacy rules, and honest production-readiness limits.

---

## 8 Specialized Field Kit Instruments (Android Lab Tools)

Every tool inside **Field Kit** starts strictly **idle** and activates only when you press its explicit action button:

| Instrument | What It Does | Honest Scope & Privacy Boundary |
|:---|:---|:---|
| **Multi-view** | Displays Back camera, Front camera, and optional loopback Laptop MJPEG stream side-by-side (`127.0.0.1:8766` via `adb reverse`). | Live preview only — zero recording, zero frame upload, cleartext restricted strictly to loopback. |
| **Acoustic Ranging** | Emits one gentle 2 kHz, 20 ms chirp per tap and measures normalized echo correlation peaks (`343 × lag / 2`). | Uncalibrated timing candidate — not certified obstacle avoidance, SPL metrology, or navigation guidance. |
| **Tiny Zoe** | Native Android behavioral simulator for the **Zoe Cell** Java Card APDU protocol (`8002...` → `0003...9000`). | Bounded behavioral model — no SIM, NFC card, or carrier modification. |
| **Radio Field** | Reads bonded Bluetooth LE device metadata / one-tap GATT RSSI and NFC tag presence/ID. | RSSI is signal strength, not certified position; never reads or writes NFC tag payload contents. |
| **Location Field** | One-shot GPS/network fix with accuracy/age readout and optional straight-line haversine distance between 2 in-memory points. | 15-second timeout; Stop or leaving cancels and clears coordinates; **zero background tracking**. |
| **Connectivity** | Reports active transport/bandwidth estimate with an optional one-shot 1 MiB HTTPS download measurement from `speed.hetzner.de`. | Network check only on tap; never guarantees coverage or emergency service availability. |
| **Screen Space** | Opt-in AccessibilityService tool for explicit user-triggered screen captures and mapped gesture coordinates. | Requires manual Android Accessibility opt-in; never passively reads screen text, monitors events, or bypasses lock screens. |
| **App Observatory** | Lists launcher-visible installed app metadata using public launcher intents. | Read-only; never reads private app data, modifies Play Protect, or force-stops/uninstalls apps. |

---

## Further Reading

- **[Complete SafeConvert Documentation (`mobile/SAFECONVERT.md`)](SAFECONVERT.md)** — Unit Converter cover, `911` variant access, 8 international regions, 5 languages, calming studio, SHA-256 proof vault, passcode lock, Offline BLE Help Beacon Mesh, and honest safety limits.
- **[Mobile Build, Architecture & Verification Ledger (`mobile/README.md`)](README.md)** — Android Gradle, Pixel 7 live hardware results, Apple Xcode & Swift 6.1.3 `ZoeCore`, Trinity, and honest remaining gaps.
- **[Mobile Security Model (`mobile/SECURITY.md`)](SECURITY.md)** — Threat model, privacy firewalls, cartridge rules, and production blockers.
- **[Store Compliance Checklist (`mobile/STORE_COMPLIANCE.md`)](STORE_COMPLIANCE.md)** — Google Play & Apple App Store privacy, accessibility, and foldable guidelines.
- **[Zoe Constitution (`CONSTITUTION.md`)](../docs/CONSTITUTION.md)** — Non-negotiable dignity, honesty, and epistemic boundaries.
