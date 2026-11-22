# SafeConvert — Documentation, Privacy Architecture & Safety Boundaries

**SafeConvert** is a built-in Zapp inside **Zoe (beta)** (`v0.9.3-beta`, available on both **Android** and **Apple** iOS/iPadOS/iPhone Duo Fold) designed for two simultaneous goals:

1. **On the surface:** A fast, genuinely useful, zero-ad, 100% offline **Unit Converter** styled seamlessly in Zoe's calm Google Gemini Material 3 Expressive Dark/Light theme.
2. **Beneath the surface:** A discreet, completely offline **international personal safety companion, trauma-informed post-incident guide, calming & children's studio, SHA-256 private proof vault, and offline Bluetooth LE Help Beacon & Blind Encrypted Relay Mesh** built to help adults and children worldwide — including people whose phones may be checked or monitored.

> **How to Access the Hidden Safety Companion:** Open **SafeConvert** and type any **variant of `911`** into the unit converter number field:
> - **Accepted 3-digit `9`/`1` variants:** `911`, `991`, `919`, `199`, `119`, `191`, `999`, or `111`
> - **Decimals & leading zeros work too:** e.g., `9.11`, `91.1`, `0.911`, `1.19`, or `9.99` (helpful if you want it to look like an ordinary measurement while typing)
> - **Instant Return to Cover:** Tap **`✕ EXIT`**, tap the top bar, press **Back / `ESC`**, switch apps, or leave it idle for 90 seconds to clear ephemeral state and snap immediately back to the Unit Converter.

---

## 1. Layer One — Everyday Unit Converter (Cover Screen)

When you open **SafeConvert**, it looks and functions strictly like a clean, modern everyday unit converter:

- **Four Real Conversion Categories:**
  - **Length:** Inches, Feet, Yards, Miles, Centimeters, Meters, Kilometers
  - **Weight:** Ounces, Pounds, Grams, Kilograms
  - **Temperature:** Fahrenheit, Celsius
  - **Volume:** Cups, Pints, Quarts, Gallons, Liters
- **Ergonomic Design Matching Zoe:** Automatically matches Zoe's Obsidian Velvet Dark Mode or pure Light Mode, with rounded pill category tabs, generous `>= 48dp/pt` inputs, instant `↕ Swap`, and a tappable top-right **Zoe GEM-Ellipsis** Home logo.
- **Zero False Triggers:** Everyday numbers and decimals (`0`, `0.00`, `0.5`, `112`, etc.) convert normally and never accidentally reveal the safety layer.
- **Zero Network & Zero Tracking:** Runs 100% from local bundled assets with zero external scripts, zero CDNs, zero ads, and zero analytics.

---

## 2. Layer Two — Discreet Offline Safety Companion (What's Inside)

Once opened, SafeConvert reveals a calm, high-contrast, easy-to-read offline safety workspace with five major pillars:

### A. International Regions & Languages *(8 Regional Packs · 5 Languages)*
- **Offline Auto-Detection + Instant Manual Override:** Detects your region offline via SIM/network/locale (or via an opt-in 1-shot **📍 Detect** GPS check) and lets you switch anytime across **8 verified regional packs**:
  - **US (`911`)**, **EU / Europe (`112`, Pan-EU Child Helpline `116 111`, Victim Support Europe `116 006`, DE `116 016`, FR `3919`, ES `016`)**, **UK (`999` / `112` + Silent Solution `55`, Refuge `0808 2000 247`, Childline `0800 1111`, clarifying NHS non-emergency `111`)**, **Canada (`911`, `988`, Kids Help Phone, ShelterSafe)**, **Australia (`000`, `1800RESPECT`, Kids Helpline)**, **México / LATAM (`911`, Red Nacional de Refugios, Línea de la Vida)**, **India (`112`, `181`, Childline `1098`)**, and **Global (`112` / `911`, `findahelpline.com`, `hotpeachpages.net`)**.
- **Localized School Helpers & Legal Protections:** Adapts school-adult terminology to local systems (e.g., EU teacher/class tutor/school nurse/social worker; UK Designated Safeguarding Lead; US school counselor) AND updates legal guidance to local orders (**US Restraining/Protection Orders**, **EU European Protection Order**, **UK Non-Molestation & Occupation Orders**, **CA Peace Bond / EPO**, **AU AVO/DVO**, **MX Órdenes de Protección**, **IN PWDVA 2005 / NALSA**).
- **5 Interface Languages:** Instant offline switching across **English (`EN`)**, **Español (`ES`)**, **Français (`FR`)**, **Deutsch (`DE`)**, and **Português (`PT`)**.

### B. My Safe People *(Private Trusted Contacts)*
- Store up to **5 trusted contacts** (name, phone number, and a custom distress message or code word like *"Call me now"*, *"I need help, come now"*, or *"Blue sky"*).
- Stored strictly in **app-private storage** (never added to your phone's main Contacts app and excluded from cloud backup via `allowBackup="false"`).
- **One-tap actions:** Tap **Send text** to pre-fill your distress message in your SMS app, or **Call** to open the phone dialer (nothing sends or dials without your deliberate tap).

### C. Talk to Zoe, Calming Studio & Private SHA-256 Proof Vault
- **`PRIVATE · USER + ZOE ONLY` Boundary:** Chat messages run **100% offline** with localized crisis buttons and **clear automatically** when you exit unless you explicitly save a note.
- **Expanded Calming Studio (100% Offline · Auto-Clears on Exit):**
  - **Breathe (4-4-6):** Visual breathing orb (`IN · 4s` → `HOLD · 4s` → `OUT · 6s`).
  - **5-4-3-2-1 Calm:** Sensory grounding card for acute panic.
  - **🎨 Calm Art Pad:** Interactive multi-color finger drawing canvas that auto-erases completely when you tap **✕ EXIT**.
  - **🧩 Easy Math & Patterns:** Zero-timer, zero-stress gentle grounding puzzles to interrupt panic spirals.
  - **📖 Stories Read by Zoe:** 3 original soothing offline stories (*The Quiet Lighthouse*, *Little Moss and the Slow Cloud*, *The Lantern Garden*). Opens **silent by default**; tapping **🔊 Have Zoe read aloud** requires explicit quiet-room/headphones confirmation before speaking softly, and **✕ EXIT** cuts voice immediately in `<10 ms`.
- **Private Safety Log & Proof Vault (UTC Timestamped · SHA-256 Verified):**
  - Timestamped text notes, explicit **● Record audio** (`.m4a`) & **● Record video** (`.mp4`) saved strictly in app-private storage (never in the public phone Gallery), optional 4–32 character `PBKDF2` passcode lock (`SafeVaultLock.java`) that auto-locks on exit, and a two-step **Grant permission & share** gate before anything ever leaves the vault.

### D. Trauma-Informed Medical Care, Closest Help Spots, Kids Mode & Moderated Support
- **After an Assault or Incident (Medical & Care):** Zero-shame post-incident checklist covering forensic evidence preservation (before showering/changing if possible, separate **paper bags** — never plastic — if clothing was changed, SANE/SARC/ER forensic exams without requiring an immediate police report, and 1-tap jump to Nearest ER or Private SHA-256 Safety Log).
- **Closest Help Spots & Safe Locator:** One-tap native Maps links (`geo:` / Apple Maps) for **Nearest Hospital / ER**, **Police Station**, **24-Hour Pharmacy**, and **Public Library**. **Confidential DV shelters are never plotted on public maps** to protect survivor safety — instead, SafeConvert connects you to regional 24/7 confidential intake lines. Includes an opt-in **one-shot GPS Locator** that reads coordinates once, stops immediately, and prepares a dual Google + Apple Maps SMS pin to your Safe People.
- **I'm a Kid and I'm Scared + 🌟 Easy Picture Mode (Young Kids):** Big-icon, 4–6 word early-reader cards (*"You are NOT in trouble"*, *"This is NOT your fault"*, regional trusted school grown-ups), a full-width **"Show this screen to a safe adult"** card, quiet-room-gated gentle read-aloud, and 1-tap jump to Calm Art & Stories.
- **Safe Support Groups & Moderated Chats:** Explains honestly why SafeConvert intentionally does **not** run unvetted anonymous peer chat rooms (preserving the zero-network sandbox and preventing abuser/predator infiltration) and links to verified, human-moderated regional survivor chats & forums.

### E. Offline Help Beacon & Blind Encrypted Relay Mesh *(Bluetooth LE · AirTag Style)*
Built in [`SafeBeaconMesh.java`](android/app/src/main/java/research/zoetic/zoe/SafeBeaconMesh.java) and mirrored in [`SafeBeaconMeshCore.swift`](shared/Sources/ZoeCore/SafeBeaconMeshCore.swift) for moments with **zero cell signal or Wi-Fi**:
- **Mode 1 — Blind E2EE Relay Beacon (AirTag / Find My Style):** Broadcasts a 22-byte signed BLE packet containing a **15-minute rotating SHA-256 ephemeral tag** (`SHA-256(secret || epoch)`). Nearby Zoe phones cannot identify who you are.
- **Mode 2 — Local SOS Mesh Alert:** Opt-in short-range (`~30–80 m`) signed BLE emergency ping that alerts nearby actively-scanning Zoe phones with approximate RSSI distance (`~X.X m`) and local emergency guidance.
- **Strict Anti-Stalkerware Guardrails (`CONSTITUTION.md`):**
  - Starts **strictly OFF** — never advertises or scans silently in the background.
  - **Hard 30-minute auto-expiry timer** prevents covert persistent tracking.
  - **Instant radio shutoff** on **✕ EXIT**, app switch, or lock screen.
  - **1-tap Rotate / Revoke All Keys** immediately replaces the 32-byte device secret and permanently invalidates all previous beacon tags.
  - **Honest Scope:** Clearly discloses Bluetooth LE peer-to-peer range (`~30–80 m` between Zoe devices — not Apple's global iPhone Find My network).

---

## 3. Built-In Privacy, Anti-Surveillance & Panic-Exit Architecture

| Protection | How It Works |
|:---|:---|
| **Instant Panic Exit (6 Triggers)** | Tap **`✕ EXIT`**, tap the **top bar**, press **`ESC`**, press **Android Back**, wait **90 seconds idle**, or **switch apps / lock screen** (`onUserLeaveHint` / `onStop`) — SafeConvert immediately cuts calm voice TTS (`<10 ms`), stops BLE beacons/scans, clears the Calm Art canvas, clears ephemeral chat & GPS display, locks any passcode-protected vault, and snaps straight back to the Unit Converter cover. |
| **Screenshot & App-Switcher Shield** | On Android, revealing the safety layer dynamically sets `WindowManager.LayoutParams.FLAG_SECURE` (blocking screenshots, screen recorders, and Android Recents previews) and clears it cleanly on exit. On Apple, `SafeConvertViewController` cuts speech, calls `exitHelp()`, and covers the view with a thick `UIVisualEffectView` blur shield on `willResignActiveNotification`. |
| **Zero-Network WebView Sandbox** | Android `WebView` sets `setBlockNetworkLoads(true)`, `setAllowContentAccess(false)`, `setAllowFileAccessFromFileURLs(false)`, `setAllowUniversalAccessFromFileURLs(false)`, `MIXED_CONTENT_NEVER_ALLOW`, and intercepts every request outside `file:///android_asset/safeconvert/`. External handoffs allow ONLY user-tapped `tel:`, `sms:`, `mailto:`, `geo:`, and `https:` schemes. |
| **Zero Cloud Backup** | Android sets `android:allowBackup="false"` and `android:fullBackupContent="false"` so private contacts, beacon keys, passcode hashes, and Safety Log evidence are excluded from automatic cloud backups or device transfers. |

---

## 4. Verification & Source Files

- **Shared Vanilla HTML/CSS/JS (mirrored byte-identical across platforms):**
  - [`mobile/shared/safeconvert/index.html`](shared/safeconvert/index.html)
  - [`mobile/android/app/src/main/assets/safeconvert/index.html`](android/app/src/main/assets/safeconvert/index.html)
  - [`mobile/apple/Zoe/Resources/safeconvert/index.html`](apple/Zoe/Resources/safeconvert/index.html)
- **Android Native Host, Proof Vault & Offline BLE Mesh:**
  - [`SafeConvertActivity.java`](android/app/src/main/java/research/zoetic/zoe/SafeConvertActivity.java) · [`SafeBeaconMesh.java`](android/app/src/main/java/research/zoetic/zoe/SafeBeaconMesh.java) · [`SafeEvidenceStore.java`](android/app/src/main/java/research/zoetic/zoe/SafeEvidenceStore.java) · [`SafeVaultLock.java`](android/app/src/main/java/research/zoetic/zoe/SafeVaultLock.java)
- **Apple Native Host & Cross-Platform BLE Core:**
  - [`SafeConvertViewController.swift`](apple/Zoe/SafeConvertViewController.swift) · [`SafeBeaconMeshCore.swift`](shared/Sources/ZoeCore/SafeBeaconMeshCore.swift)
- **Automated Tests:**
  - **Pixel 7 Hardware Espresso Tests:** [`SafeConvertActivityTest.java`](android/app/src/androidTest/java/research/zoetic/zoe/SafeConvertActivityTest.java) (all cover conversions, zero false triggers, international region switching US→EU `112`/`116 111`→UK `999`/`0808 2000 247`, Spanish/English UI switch, post-incident forensic care, Closest Help Spots `geo:` links & confidential shelter notice, Young Child Easy Picture Mode, Calm Art/Math/Zoe Stories + mandatory sound-safety gate, SHA-256 vault + passcode lock, and Offline BLE Help Beacon key rotation).
  - **Android & Swift Unit Tests:** [`SafeConvertIntentTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeConvertIntentTest.java) · [`SafeBeaconMeshTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeBeaconMeshTest.java) · [`SafeEvidenceStoreTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeEvidenceStoreTest.java) · [`SafeVaultLockTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeVaultLockTest.java) · [`ZoeCoreTests.swift`](shared/Tests/ZoeCoreTests/ZoeCoreTests.swift).

---

## 5. Honest Safety Boundaries & Credits

- **Not Counseling, Legal Advice, or an Emergency Guarantee:** SafeConvert is an offline information, calming, documentation, and short-range BLE signaling tool — not professional therapy, legal representation, or a guarantee of physical safety. Emergency calls and texts still depend on your device, carrier, signal, and local emergency services.
- **BLE Range Boundaries:** Offline Bluetooth LE beacons typically reach `~30–80 m` between active Zoe phones depending on walls and terrain; they do not use Apple's proprietary global Find My network.
- **Recording Laws:** One-party vs. two-party audio/video recording consent laws vary by state and country. Use recording tools only when safe and lawful for your situation.
- **Credit:** The original SafeConvert concept is credited to **ExileKingdom / Nuclide**. This independent zero-dependency implementation adds native Android `WebView` / Apple `WKWebView` containers, `FLAG_SECURE` / iOS blur shields, 8-region / 5-language international support, trauma-informed post-incident medical care, Closest Help Spots & opt-in GPS locator, Calm Art/Math/Zoe Story Studio, Young Child Easy Picture Mode, SHA-256 private vault storage, optional passcode lock, and the offline rotating-tag BLE Help Beacon & Mesh.
