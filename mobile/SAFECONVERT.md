# SafeConvert — Documentation, Privacy Architecture & Safety Boundaries

**SafeConvert** is a built-in Zapp inside **Zoe Bulb (beta)** (available on both **Android** and **Apple** iOS/iPadOS/iPhone Duo Fold) designed for two simultaneous goals:

1. **On the surface:** A fast, genuinely useful, zero-ad, 100% offline **Unit Converter** styled seamlessly in Zoe Bulb's calm Google Gemini Material 3 Expressive Dark/Light theme.
2. **Beneath the surface:** A discreet, completely offline **personal safety companion, calming aid, crisis resource directory, and SHA-256 private proof vault** built to help adults and children who may be experiencing abuse, coercion, or crisis — including people whose phones may be checked or monitored.

> **Important Public Safety Note:** To protect people who rely on SafeConvert in unsafe households, the exact discreet activation sequence is **intentionally omitted from public deployment guides and social posts**. Developers auditing the repository can inspect the exact mechanism directly in [`mobile/shared/safeconvert/index.html`](shared/safeconvert/index.html), and users see a quiet reminder inside SafeConvert's private safety layer once opened.

---

## 1. Layer One — Everyday Unit Converter (Cover Screen)

When you open **SafeConvert**, it looks and functions strictly like a clean, modern everyday unit converter:

- **Four Real Conversion Categories:**
  - **Length:** Inches, Feet, Yards, Miles, Centimeters, Meters, Kilometers
  - **Weight:** Ounces, Pounds, Grams, Kilograms
  - **Temperature:** Fahrenheit, Celsius
  - **Volume:** Cups, Pints, Quarts, Gallons, Liters
- **Ergonomic Design Matching Zoe Bulb:** Automatically matches Zoe Bulb's Obsidian Velvet Dark Mode or pure Light Mode (synced live with Zoe's in-app appearance toggle on Android and system Dark/Light appearance on Apple), with rounded pill category tabs, generous `>= 48dp/pt` inputs, instant `↕ Swap`, and a tappable top-right **Zoe GEM-Ellipsis** Home logo.
- **Zero False Triggers:** Everyday numbers and decimals (`0`, `0.00`, `0.5`, `112`, etc.) convert normally and never accidentally reveal the safety layer.
- **Zero Network & Zero Tracking:** Runs 100% from local bundled assets with zero external scripts, zero CDNs, zero ads, and zero analytics.

---

## 2. Layer Two — Discreet Offline Safety Companion (What's Inside)

Once opened, SafeConvert reveals a calm, high-contrast, easy-to-read offline safety workspace with four core pillars:

### A. My Safe People *(Private Trusted Contacts)*
- Store up to **5 trusted contacts** (name, phone number, and a custom distress message or code word like *"Call me now"*, *"I need help, come now"*, or *"Blue sky"*).
- Stored strictly in **app-private storage** (never added to your phone's main Contacts app and excluded from cloud backup via `allowBackup="false"`).
- **One-tap actions:** Tap **Send text** to pre-fill your distress message in your SMS app, or **Call** to open the phone dialer (nothing sends or dials without your deliberate tap).
- Edit, delete any single contact, or **Erase all saved contacts** with a clean two-step confirmation.

### B. Talk to Zoe & Calming Tools *(100% Offline · Ephemeral)*
Designed for moments of panic, fear, verbal abuse, or overwhelm:
- **`PRIVATE · USER + ZOE ONLY` Boundary:** Chat messages run **100% offline** via deterministic supportive responses (zero cloud servers, zero AI logs) and **clear automatically** the moment you exit unless you explicitly tap **+ Save to Safety Log** on a specific note.
- **Breathe (4-4-6):** Interactive guided visual breathing orb (`IN · 4s` → `HOLD · 4s` → `OUT · 6s`) to steady breathing at your own pace.
- **5-4-3-2-1 Calm:** Simple sensory grounding card for acute anxiety or panic.
- **Quick One-Tap Distress Chips:** Plain-language prompts (*"I'm feeling really sad"*, *"I'm scared right now"*, *"They yelled at me"*, *"I just need to calm down"*) so someone shaking or too overwhelmed to type can get immediate calm guidance and crisis buttons.

### C. Private Safety Log & Proof Vault *(UTC Timestamped · SHA-256 Verified)*
Helps document incidents safely and privately when someone needs an intact record for advocates, shelters, or legal protection orders:
- **Timestamped Text Notes:** Write dates, exact threats or words spoken, witnesses, or injuries — automatically stamped with UTC time and a cryptographic **SHA-256 digest**.
- **Explicit Audio & Video Recording (Android Native Vault):**
  - Tap **● Record audio** (AAC `.m4a`, 44.1 kHz) or **● Record video** (`.mp4`) to capture private evidence.
  - Recording starts **ONLY when you press Record** — never passively in the background. If you tap **✕ EXIT** while recording audio, active audio stops and saves cleanly.
  - Files are saved strictly in **app-private storage** — they **never appear in your phone's public Photos / Gallery app**.
- **Optional Private Vault Passcode Lock:**
  - Set an optional 4–32 character passcode (`PBKDF2` / salted hash via [`SafeVaultLock.java`](android/app/src/main/java/research/zoetic/zoe/SafeVaultLock.java)).
  - **Auto-locks automatically every time you exit or leave the screen** — and you can still add new notes/recordings even while the vault is locked so prior entries stay hidden.
- **Explicit Permission Gate Before Sharing:**
  - Nothing in the Safety Log ever leaves the vault automatically.
  - Tapping **Share** or **Share full Safety Log** opens a second explicit confirmation banner (**Grant permission & share** vs **Keep private**) before invoking the OS share sheet.
  - Includes one-item delete and **Erase entire Safety Log** with explicit confirmation.

### D. Six Crisis, Child, Safety-Plan & Legal Help Sections
Every section opens calmly as a clear accordion with large readable text and one-tap `tel:` / `sms:` / `mailto:` / `https:` links (never auto-triggered):
1. **I need help right now:** National Domestic Violence Hotline (`1-800-799-7233`), Text `START` to `88788`, Crisis Text Line (`HOME` to `741741`), `988` Suicide & Crisis Lifeline (call or text), and `911`.
2. **I'm a kid and I'm scared:** Childhelp National Hotline (`1-800-422-4453`), clear reassuring messages (*"You are not in trouble."* / *"This is not your fault."*), and guidance on reaching a trusted teacher, counselor, neighbor, or `911`.
3. **I need to make a plan to leave:** 5 clear step-by-step safety planning actions (trusted person, code word, essential documents, knowing exits, shelter essentials for children & pets).
4. **I think my phone is being watched:** Practical checklist for safer devices, private browsing, unrecognized disguised apps, Google Location Sharing / Android Unknown Tracker Alerts, physical trackers (AirTags/Tiles), and safe password changes.
5. **Can I get legal help?:** Plain-English guidance on free protection / restraining orders, courthouse victim advocates, evidence preservation, legal protection regardless of immigration status, and an explicit tap-only link to `lawhelp.org`.
6. **More numbers to call or text:** DV Hotline, Childhelp, Love Is Respect (`1-866-331-9474` / Text `LOVEIS` to `22522`), RAINN Sexual Assault Hotline (`1-800-656-4673`), Deaf / Hard of Hearing Video Phone (`1-855-812-1001`), confidential hotline email, and `911`.

---

## 3. Built-In Privacy, Anti-Surveillance & Panic-Exit Architecture

SafeConvert enforces multiple defense-in-depth protections automatically:

| Protection | How It Works |
|:---|:---|
| **Instant Panic Exit (6 Triggers)** | Tap **`✕ EXIT`**, tap the **top bar**, press **`ESC`**, press **Android Back**, wait **90 seconds idle**, or **switch apps / lock screen** (`onUserLeaveHint` / `onStop`) — SafeConvert immediately clears ephemeral chat, locks any passcode-protected vault, clears inputs, and snaps straight back to the Unit Converter cover. |
| **Screenshot & App-Switcher Shield** | On Android, revealing the safety layer dynamically sets `WindowManager.LayoutParams.FLAG_SECURE` (blocking screenshots, screen recorders, and Android Recents previews) and clears it cleanly on exit. On Apple, `SafeConvertViewController` covers the view with a thick `UIVisualEffectView` blur shield on `willResignActiveNotification`. |
| **Zero-Network WebView Sandbox** | Android `WebView` sets `setBlockNetworkLoads(true)`, `setAllowContentAccess(false)`, `setAllowFileAccessFromFileURLs(false)`, `setAllowUniversalAccessFromFileURLs(false)`, `MIXED_CONTENT_NEVER_ALLOW`, and intercepts every request outside `file:///android_asset/safeconvert/`. Apple `WKWebView` allows only local `file://` loads and explicit user-tapped `tel:`, `sms:`, `mailto:`, and `https:` links. |
| **Zero Cloud Backup** | Android sets `android:allowBackup="false"` and `android:fullBackupContent="false"` so private contacts, passcode hashes, and Safety Log evidence are excluded from automatic cloud backups or device transfers. |

---

## 4. Verification & Source Files

SafeConvert is continuously verified by automated unit tests and real hardware instrumentation tests on Pixel 7:

- **Shared Vanilla HTML/CSS/JS (mirrored byte-identical across platforms):**
  - [`mobile/shared/safeconvert/index.html`](shared/safeconvert/index.html)
  - [`mobile/android/app/src/main/assets/safeconvert/index.html`](android/app/src/main/assets/safeconvert/index.html)
  - [`mobile/apple/Zoe/Resources/safeconvert/index.html`](apple/Zoe/Resources/safeconvert/index.html)
- **Android Native Host & Vault:**
  - [`SafeConvertActivity.java`](android/app/src/main/java/research/zoetic/zoe/SafeConvertActivity.java) · [`SafeEvidenceStore.java`](android/app/src/main/java/research/zoetic/zoe/SafeEvidenceStore.java) · [`SafeVaultLock.java`](android/app/src/main/java/research/zoetic/zoe/SafeVaultLock.java)
- **Apple Native Host:**
  - [`SafeConvertViewController.swift`](apple/Zoe/SafeConvertViewController.swift)
- **Automated Tests:**
  - **9/9 Pixel 7 Hardware Espresso Tests:** [`SafeConvertActivityTest.java`](android/app/src/androidTest/java/research/zoetic/zoe/SafeConvertActivityTest.java) (local no-CDN load, unit conversion accuracy across all 4 categories + Swap, zero false-trigger checks on normal decimals, emergency-code reveal & legal section, safe-contact persistence + `FLAG_SECURE` toggle, Talk to Zoe calming + SHA-256 timestamped proof persistence, passcode auto-lock on exit + explicit share permission gate, and clean cover-only exit).
  - **Android Host Unit Tests:** [`SafeConvertIntentTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeConvertIntentTest.java) · [`SafeEvidenceStoreTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeEvidenceStoreTest.java) · [`SafeVaultLockTest.java`](android/app/src/test/java/research/zoetic/zoe/SafeVaultLockTest.java).

---

## 5. Honest Safety Boundaries & Credits

- **Not Counseling, Legal Advice, or an Emergency Guarantee:** SafeConvert is an offline information, calming, and documentation tool — not professional therapy, legal representation, or a guarantee of physical safety. Emergency calls and texts still depend on your device, carrier, signal, and local emergency services.
- **Recording Laws:** One-party vs. two-party audio/video recording consent laws vary by state and country. Use recording tools only when safe and lawful for your situation.
- **Device Hygiene:** If you suspect your phone is compromised or actively monitored, use a safer device (such as a library computer or a trusted friend's phone) whenever possible, and avoid storing passwords or banking details inside notes.
- **Credit:** The original SafeConvert concept is credited to **ExileKingdom / Nuclide**. This independent zero-dependency vanilla implementation adds native Android `WebView` / Apple `WKWebView` containers, `FLAG_SECURE` / iOS blur shields, SHA-256 private vault storage, optional passcode lock, offline calming tools, and Zoe Bulb's accessible Material 3 Expressive design.
