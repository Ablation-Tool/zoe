# Zoe Mobile

Original native Android and Apple interfaces for **Zoe · NuClide Research**. The mobile work keeps three capabilities separate:

1. **Deterministic Zoe:** strict accessible-volume measurement, local voice-command parsing, bounded protocol experiments, and review-required observations.
2. **Optional on-device AI:** Gemini Nano image descriptions through the public ML Kit GenAI API when Android and the installed model support it. Apple uses its native Vision framework instead.
3. **External assistants:** an explicit Gemini app/web handoff. Zoe does not read Gemini Live's camera, inject private commands, retrieve private responses, or claim Gemini's permissions.

**Research = fun = discovery.** The design uses **PLACES — Play. Learn. Adapt. Create. Explore. Share.** as a creative thread, not as cryptic navigation. Controls use plain language, specialized instruments stay out of the first-run path, and model confidence remains separate from correctness, evidence, belief, and authorization.

## Researcher quick start

Requirements: **Java 17+**, **Android SDK 36**, and **Android 8.0/API 26 or later**. Use a device for instrumentation and hardware checks; an emulator is sufficient for many UI checks. The first Gradle build needs network access to retrieve declared dependencies. From `mobile/android`:

```bash
export ANDROID_HOME=/path/to/android-sdk
./gradlew testDebugUnitTest lintDebug assembleDebug assembleAndroidTest --no-daemon
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n research.zoetic.zoe/.MainActivity
```

To run the separate on-device suite:

```bash
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument -w -r \
  research.zoetic.zoe.test/androidx.test.runner.AndroidJUnitRunner
```

Check the reported JUnit result, not only ADB's exit status. Hardware-dependent results are listed separately below rather than inferred from UI tests. No release keystore is included: the generated APK is a development-signed build, not a production distribution. Before a public release, configure signing and an update path, test the supported device matrix and large-text/screen-reader flows, review third-party services, and obtain independent security and accessibility review.

### Your first five minutes

1. Open **Accessible volume** and measure the worked distribution.
2. Open **Tiny Zoe**. Choose **Read simulated card**, then **Measure on simulated card**.
3. Inspect the request, response, status word, accessible count, complement, and quantized threshold.
4. Change `τ` from `0.05` to `0.20`. Equality is excluded, so the default distribution produces **A = 1 of 4** instead of **A = 3 of 4**.
5. Choose **Replay last** and confirm identical bytes. Choose **Share session** only if you want Android's share sheet to export the retained simulation transcript.

The same workflow is available offline inside **Researcher guide**. That screen also explains build requirements, privacy, evidence boundaries, and the remaining production-release checklist.

## Zoe Trinity · phone + laptop + Tiny

**Trinity is the shared three-plane workspace.** Tiny supplies a Q0.15/APDU witness, Android or Apple supplies native interaction and floating-point measurement, and the laptop supplies a synchronized observation deck with optional long-term memory. These are coordinated instruments, not three claimed minds.

```bash
python mobile/tools/zoe_trinity.py
adb reverse tcp:8767 tcp:8767
```

Open **http://127.0.0.1:8767** on the laptop and **Trinity** on Android. Either side can measure; both show the same revision, distribution, threshold, two measurement planes, and retained field notes. Apple uses explicit private-network pairing instead of ADB. Add `--memory PATH` for an append-only, hash-verified laptop journal; Tiny itself remains stateless. No cloud, camera, microphone, or autonomous action is involved. See the [complete Trinity guide](TRINITY.md) for Apple pairing, API details, memory limits, security boundaries, and verification.

### Platform matrix

| Platform | Zoe form | Current verification |
|:---|:---|:---|
| Google Pixel / Android | Native Java app with Trinity and standalone Tiny Zoe | Android 8.0/API 26+; host tests, lint, and APK builds pass. Current on-device suite still needs a connected Pixel. |
| Linux | Local Python companion server and responsive browser deck | Server/API, journal, desktop/mobile browser workflows, and screenshots verified on Linux. |
| Windows 10/11 x86_64 | **Native Win32 portable `ZoeTrinity.exe`** with its own server and journal | Core and packaged API tested under Wine; native window captured; no Python/.NET requirement. Real Windows verification and signing remain. See [native Windows guide](windows/README.md). |
| Apple / iOS 17+ | Native SwiftUI Trinity with private-network pairing | Eight shared Swift tests pass. Xcode build, signing, simulator, and iPhone verification remain unavailable on this host. |

## Android

The application ID is `research.zoetic.zoe`. The home screen has four primary destinations:

- **Guided vision:** explicit camera start, one-frame inspection, bundled offline OCR and image labels, optional device AI, and spoken results on request.
- **Talk:** continuous turn-taking only after explicit start, captions, bounded transcripts, and installed English voice selection.
- **Accessible volume:** Nicholas Michael Kloster's original strict threshold equation, created solely by him on March 6, 2026. Equality is excluded.
- **Trinity:** synchronized mobile, laptop, and Tiny measurement planes with native response verification.

**Field kit** groups standalone Tiny Zoe, Multi-view, Acoustic ranging, Radio field, Location field, Connectivity, Screen Space, and App Observatory. **Device field**, **SafeConvert**, and the **Researcher guide** remain one tap away. Returning home explicitly unbinds the Guided Vision camera. No sensor starts merely because its row is visible.

Additional deterministic and platform capabilities include local battery/thermal/capability observations, sensor counts, speech availability, an explicit speaker check, and one-shot voice commands: `inspect`, `repeat`, `stop`, `measure`, `battery`, and `Gemini`. On-device speech is selected when Android reports it available; otherwise offline recognition is preferred and the service controls actual processing.

Zoe is **offline-first, not offline-only**. Its merged manifest includes `CAMERA`, `RECORD_AUDIO`, `INTERNET`, `ACCESS_NETWORK_STATE`, AICore's `BIND_SERVICE`, Bluetooth, vibration, one-shot fine/coarse location, and launcher-only app visibility. There are no storage, contacts, device-administrator, full-package-inventory, or bootloader privileges. Cloud backup and device transfer exclude app data. Screen Space additionally requires an explicit, user-enabled AccessibilityService; it does not passively read accessibility events. Location and app metadata are accessed only through the relevant activities, and no Play Protect control or private app-data API is claimed. Bundled OCR and image-label models and the local UI work offline; optional model downloads, external apps, and model services may use the network the user authorized. Zoe-authored code has no telemetry or image-upload path, and sharing is always user-initiated.

### Device-AI behavior

The Android implementation uses these public APIs:

- [ML Kit text recognition](https://developers.google.com/ml-kit/vision/text-recognition/v2/android), bundled `16.0.1`
- [ML Kit image labeling](https://developers.google.com/ml-kit/vision/image-labeling/android), bundled `17.0.9`
- [ML Kit GenAI Image Description](https://developers.google.com/ml-kit/genai/image-description/android), `1.0.0-beta1`
- [Android SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer)

OCR and image labeling run whenever **Inspect once** is pressed after camera permission and preview are active. The optional describer runs only after its feature is checked and the model is explicitly enabled. Google's API notes that unlocked bootloaders are unsupported; this integration preserves the Pixel's verified, locked boot state rather than attempting a bypass.

A feature status of `DOWNLOADABLE` or `AVAILABLE` is not evidence of description quality. Descriptions, OCR, labels, and accessible-volume measurements remain separate observations. No output is a safety guarantee, object-identity proof, or instruction to act.

## Tiny Zoe · layered little sister

`mobile/card/` contains **Zoe Cell**, the original little-sister companion: a two-command Java Card applet, a bounded host probability encoder, and a generated layer manifest. It preserves strict `p > τ` over explicitly quantized Q0.15 inputs. The current host class for simulation is 2,735 bytes; that is not a CAP or physical-card footprint. Eight APDU simulator tests and six host-codec tests cover shared fixtures, boundary behavior, deterministic encoding, malformed requests, and malformed responses. No reader, CAP installation, physical card, or carrier eSIM modification is claimed. See `mobile/card/README.md` for the protocol, limits, and hardware requirements.

The **Field kit → Tiny Zoe** row opens the native Android behavioral simulator. It executes real bounded requests and responses inside Zoe without a reader, network, SIM access, storage permission, or third-party card runtime. Visible labels explain the worked distribution and threshold. The screen displays the under-1,900,000-byte companion budget and distinguishes the 2,735-byte reference class from Android APK, CAP, and physical-card footprints. This is a behavioral model, not a Java Card VM or secure-chip emulator.

The default measure command is:

```text
800200000A0666599A199A0A3D028F
```

Its successful response is:

```text
00030001000406669000
```

These encode `A = 3`, complement `1`, vocabulary size `4`, quantized `τ = 0x0666`, and success status `0x9000`. **Share session** includes up to twelve retained transactions with request/response bytes and statuses, equation credit, and a prominent simulation disclaimer. It contains no timestamp or device identifier, writes no file, and uploads nothing. Reset clears history and replay state.

## Talk and Multi-view

**Talk** provides continuous turn-taking rather than an always-on listener. Zoe speaks a prompt, you answer, Zoe displays the transcript and responds, and the next turn begins. Turns repeat until **Stop**, you leave the activity, or it pauses. Transcripts are bounded to twelve exchanges and remain on screen until you clear or explicitly share them. Replies are deterministic for device topics; open-ended understanding is handed to Gemini rather than fabricated locally.

**Multi-view** displays phone back, phone front, and an optional laptop feed together. Each source has an independent status and failure path. No frame analysis or recording is performed by this activity. Concurrent-camera capability is checked by binding the real cameras rather than inferred from a feature flag.

The laptop bridge binds only to `127.0.0.1` and uses an ADB reverse mapping. Cleartext traffic is restricted to `127.0.0.1` and `localhost`; other HTTP origins remain disabled. Frames are bounded to 2 MiB, at most two viewers are accepted, and no video files are written.

Start with the synthetic stream:

```bash
python mobile/tools/laptop_camera.py --test-pattern
adb reverse tcp:8766 tcp:8766
```

Then open **Multi-view → Start all sources**. Replace `--test-pattern` with `--device /dev/video0` for the laptop camera. Stop the script to stop capture. `ffmpeg` is required; no Python camera package is used.

On the audited Pixel, Gemini Nano's feature check returned `601-BINDING_FAILURE`. Zoe reported it and continued with OCR and labels without downloading a model. This is an unavailable optional lane, not a fabricated successful Nano result.

## SafeConvert

SafeConvert integrates an original offline unit converter and safety resource. It provides length, weight, temperature, and volume conversions, crisis-readable hotline/resource links, a child-friendly section, safety planning, and up to five locally stored safe contacts. Phone, SMS, and external safe-link actions require a deliberate tap. Escape or the EXIT control returns to the converter.

The original SafeConvert concept is credited to ExileKingdom / Nuclide. This independent vanilla implementation adds native Android `WebView` and Apple `WKWebView` containers, no React or CDN, no analytics, no tracking, no external code, and no embedded network loads. Local contact storage is bounded and never uploaded by Zoe. The activation pattern is intentionally not repeated in this public guide; do not publish it alongside a deployment URL.

SafeConvert is not professional counseling, legal advice, an emergency-service guarantee, or a promise of safety. Emergency calls still depend on the device, carrier, location, and available services. Users should use a safer device when possible and avoid capturing passwords, payment details, or other private content.

## Ranging, radio, location, and connectivity

**Acoustic Ranging Lab** emits one gentle 2 kHz, 20 ms chirp per tap and evaluates normalized correlation peaks. If a later echo candidate exists, it reports `343 × echoLag / 2` as an uncalibrated distance candidate. Strongest-peak selection avoids early sidelobes. dBFS is not calibrated SPL, motion RMS is not displacement, and candidates are not certified obstacle detection, safe navigation, or biometric identification. Text, optional speech, and vibration provide alternative feedback.

**Radio Field Lab** reads bonded BLE device metadata and attempts one GATT RSSI read per tap. RSSI is signal strength, not distance. An optional user-declared 1 m calibration evaluates a path-loss model with exponent 2.0; it is not proof of position. NFC reader mode reports tag presence and ID only, without reading or writing tag content.

**Location Field** performs a one-shot GPS/network read, displays accuracy and reading age, and optionally computes straight-line haversine distance between two in-memory points. Stop and leaving the activity cancel the platform request; an unanswered request times out after 15 seconds. Stop also clears displayed coordinates and in-memory points. It does not track in the background, geocode addresses, or infer safe routes. Coordinates are not included in verification artifacts.

**Connectivity Field** reports transport changes and Android's downstream estimate, with an optional one-shot 1 MiB HTTPS download measurement from `speed.hetzner.de`. The endpoint is a third-party sample, not a guarantee of coverage, future speed, carrier band, FirstNet, WPS, or emergency access. Offline OCR/labels and low-bandwidth settings remain available.

**Screen Space** requires a separately enabled AccessibilityService. It captures on demand, maps gestures to the captured screen, and records monotonic action ordinals. It does not read accessibility events, passively collect screen content, bypass lock screens, or run background gestures. Do not capture passwords, payment screens, or private content.

**App Observatory** uses launcher-visible package metadata and public launcher intents. It does not request full-package inventory, inspect private app data, control Play Protect, force stop, or uninstall applications.

**Talk voice selection** lists installed English TTS voices and persists the selected identifier locally. It does not download voices or identify a speaker.

## Wireless and network setup

The verified bridge currently uses USB with `adb reverse tcp:8766 tcp:8766`. The physical laptop camera has streamed real frames through this bridge. Wireless ADB is optional future setup, not an established connection. Temporary hotspot profiles created during exploration were removed; no hotspot is required by Zoe.

If Wireless ADB is enabled later, use its current phone IP and port, then `adb connect` and `adb reverse` exactly as above. The laptop MJPEG service remains bound to `127.0.0.1`, so the stream is not published to the LAN or internet. No trust-all TLS, open camera server, or cloud relay is used.

## Measured verification

On the current checkout, all **35 Android host unit tests**, **nine Python Trinity tests**, **eight Swift core tests**, debug and instrumentation APK builds, an unsigned release APK build, Android lint, and all **five shared equation fixtures pass**. The Trinity laptop deck also passed a real browser workflow at desktop and phone-sized viewports with no horizontal overflow or browser errors. Lint reports zero errors without a baseline; non-fatal warnings remain visible. The **32 on-device tests compile**, but the updated suite has not run because no phone was connected after the interface and Trinity changes. An earlier Pixel 7 run passed 26 device tests before these changes; that result does not verify the new home, Field kit, researcher guide, export flow, or physical Android Trinity synchronization. Zoe Cell's eight Java Card APDU plus six Python host-codec tests passed in the preceding verification; unchanged card source was not rerun. The measured Java simulation host class remains 2,735 bytes.

The native Android protocol/session model now has **17 passing host tests**, including strict equality, exact export bytes, empty export behavior, raw APDU errors, defensive copies, reset, replay, and oversized input. Seven Tiny Zoe on-device UI tests are present in the compiled, not-yet-rerun device suite. Adversarial host checks cover 4,352 arbitrary command cases and 1,000 hostile strings with deterministic replay and bounded history. An earlier visible UI transaction returned `A = 3 of 4` with a 15-byte request and 10-byte response, without hardware, SIM, or network access. Ablation's preceding report found no dangerous-call, reflection, class-loader, unsafe-operation, or serialization findings in the three compiled core classes; the new export formatter has not undergone a separate Ablation review. These are bounded test results, not proof of perfect safety or production readiness.

Live observations, kept separate from test claims:

- **Multi-view:** the real back camera, front camera, and laptop camera all reported live simultaneously through the USB/ADB localhost bridge. Capture was stopped afterward.
- **Acoustic Lab:** one real capture reported a 14.21 m candidate with 0.69 correlation and substantial direct-path latency. This is an uncalibrated timing observation, not a physical-distance verification or navigation guidance.
- **Talk:** an installed `en_US` voice was available, and caption start/stop plus the truthful on/off label were exercised. No real user utterance or audible conversational-quality evaluation has been completed.
- **Radio:** bonded-device metadata was available, but no BLE RSSI result arrived; the attempt was stopped. No physical NFC tag read was performed.
- **Location:** no fix arrived within the new 15-second limit. The real timeout reported no active request. No coordinates were recorded in verification artifacts.
- **Connectivity:** Android reported validated Wi-Fi with a 76,161 kbps downstream estimate. The third-party rate test failed at DNS, so no download-rate result is claimed. No network or hotspot settings were changed.
- **Device AI:** the optional Nano path returned `601-BINDING_FAILURE`; no model was downloaded. Earlier real OCR/image-label inspection is not a Nano result.

Wireless ADB is not established. The verified workflow is USB. iOS application building, signing, simulator execution, and physical-device verification remain unavailable from this Linux host. No PC/SC reader was found, so Zoe Cell has no CAP-size measurement or physical-card installation claim.

## Apple

Open `mobile/apple/Zoe.xcodeproj` in Xcode, select a development team, and build the **Zoe** scheme for an iPhone running iOS 17 or later. The project includes SwiftUI, AVFoundation, Vision, Speech, original icons, and the shared Zoetic core.

- Camera capture requires an explicit start and one-frame inspection.
- `VNRecognizeTextRequest` supplies OCR; `VNClassifyImageRequest` supplies labels.
- Speech recognition requires `SFSpeechRecognizer` on-device support for the current locale. Unsupported recognition fails visibly rather than silently using a network service.
- VoiceOver-oriented labels, large controls, one-shot voice commands, and `AVSpeechSynthesizer` output are included.
- Device Field uses public battery and thermal-state APIs. Battery temperature and private sensor streams are not available through public iOS APIs and are not invented.
- **Trinity** provides the shared three-plane experiment with explicit laptop URL and pairing-code entry, private-IPv4 validation, no persisted pairing code, and no camera or microphone use. See [the Trinity guide](TRINITY.md) for the required `--lan` server mode and the distinction between pairing and encryption.

The platform-independent Swift package lives at `mobile/shared`:

```bash
cd mobile/shared
swift test
```

**An iOS application build, simulator run, device signature, and physical iPhone verification require Apple/Xcode infrastructure.** Those are not claimed from the Linux host. The Xcode project and core tests are separate verification levels.

Useful Apple references: [image classification](https://developer.apple.com/documentation/vision/classifying-images-for-categorization-and-search), [VNClassifyImageRequest](https://developer.apple.com/documentation/vision/vnclassifyimagerequest), and [Speech](https://developer.apple.com/documentation/speech).

## Shared conformance

From the Zoe repository root:

```bash
python mobile/conformance/verify.py
```

The five fixtures cover the worked example, strict equality exclusion, both threshold endpoints, and zero probabilities. Java and Swift retain the same strict comparison and original credit. Android additionally runs host and on-device UI tests.

## Project map

```text
mobile/
  android/                 Native Java/Android app and tests
  apple/Zoe.xcodeproj      Native SwiftUI application project
  apple/Zoe/              Controllers, views, Info.plist, and assets
  shared/                 Swift core and XCTest suite
  card/                   Zoe Cell applet, host codec, and layer manifest
  conformance/            Shared strict-equation fixtures and verifier
  tools/zoe_trinity.py    Loopback/private-LAN three-plane companion server
  tools/trinity_page.html Self-contained responsive laptop observation deck
  tools/trinity_memory.py Optional append-only verified journal
  tools/zoe_pair.py     Signed short-lived QR pairing and trust verification
  tools/zoe_author.py   Exact-document Ed25519 author certificates
  TRINITY.md              Phone/laptop setup, API, memory, and platform limits
  PAIRING.md            QR pairing and author-certificate verification
  docs/images/            Captured Trinity desktop, responsive, and native Windows decks
  windows/                Native Win32 app, CMake build, and Windows guide
  dist/windows/           Local portable Windows artifacts and hashes (not a signed release)
```

## Brand and authorship

The launcher uses the original orbital Zoe eye. The dual-brain **NuClide Research** mark is a supporting co-brand supplied by Nicholas, not a Google/Gemini or Digital Research mark. Mobile identity:

**Zoe = NuClide Research partner + Nicholas Michael Kloster. Zoetic = Zoe = life; research = fun = discovery. PLACES = Play. Learn. Adapt. Create. Explore. Share.**

The original accessible-volume equation remains solely Nicholas Michael Kloster's work, March 6, 2026. New mobile engineering does not transfer that original credit or imply that an AI assistant is a person.

## Boundaries

- No bootloader unlock, firmware flash, root exploit, hidden API, system-wide accessibility service, lock-screen control, or background always-on listener is used.
- No image or raw audio is saved by Zoe. No continuous frame analysis or continuous recognition is performed.
- These are inspection and navigation aids, not certified obstacle avoidance, medical, biometric, identity, or safety systems.
- Model availability, OCR accuracy, labels, descriptions, speech confidence, and forecasts are not correctness or authorization.
- Native platform permissions and hardware states remain real. “Full control” is not represented as unlimited Android, iOS, Gemini, or firmware authority.
