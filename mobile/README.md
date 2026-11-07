# Zoe Mobile

Original native Android and Apple interfaces for **Zoe · NuClide Research**. The mobile work keeps three capabilities separate:

1. **Deterministic Zoe:** strict accessible-volume measurement, local voice-command parsing, and review-required observations.
2. **Optional on-device AI:** Gemini Nano image descriptions through the public ML Kit GenAI API when Android and the installed model support it. Apple uses its native Vision framework instead.
3. **External assistants:** an explicit Gemini app/web handoff. Zoe does not read Gemini Live's camera, inject private commands, retrieve private responses, or claim Gemini's permissions.

Research = fun = discovery. Model confidence remains separate from correctness, evidence, belief, and authorization.

## Android

The application ID is `research.zoetic.zoe`. It includes:

- **Guided Vision:** explicit camera start, one-frame inspection, bundled offline OCR and image labels, and spoken results on request.
- **Optional device AI:** public `genai-image-description` feature checks and a separate **Enable AI model** action. No model download is triggered by opening the app. Feature availability is checked at runtime rather than inferred from AICore's presence.
- **Accessible Volume:** Nicholas Michael Kloster's original strict threshold equation, created solely by him on March 6, 2026. Equality is excluded.
- **Device Field:** local battery, thermal/capability observations where public APIs expose them, sensor counts, speech availability, and an explicit speaker check.
- **Voice navigation:** one-shot `inspect`, `repeat`, `stop`, `measure`, `battery`, and `Gemini` commands. On-device speech is selected when Android reports it available; otherwise offline recognition is preferred and the service controls actual processing.

Zoe is **offline-first, not offline-only**. Its merged manifest includes `CAMERA`, `RECORD_AUDIO`, `INTERNET`, `ACCESS_NETWORK_STATE`, AICore's `BIND_SERVICE`, Bluetooth, vibration, one-shot fine/coarse location, and launcher-only app visibility. There are no storage, contacts, device-administrator, full-package-inventory, or bootloader privileges. Cloud backup and device transfer exclude app data. Screen Space additionally requires an explicit, user-enabled AccessibilityService; it does not passively read accessibility events. Location and app metadata are accessed only through the relevant activities, and no Play Protect control or private app-data API is claimed. Bundled OCR and image-label models and the local UI work offline; optional model downloads, external apps, and model services may use the network the user authorized. Zoe-authored code has no telemetry or image-upload path, and sharing is always user-initiated.

### Build

Requirements: Java 17+, Android SDK 36, and an Android device or emulator. From `mobile/android`:

```bash
export ANDROID_HOME=/path/to/android-sdk
./gradlew testDebugUnitTest assembleDebug assembleAndroidTest
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb shell am instrument -w -r \
  research.zoetic.zoe.test/androidx.test.runner.AndroidJUnitRunner
```

Check the reported JUnit result, not only ADB's exit status. The current **26 device tests** verify the settings-style home, strict volume measurement, SafeConvert's hidden cover and exit, Talk controls, scoped idle states, and actual cancellation of a pending platform location request. Hardware-dependent results are listed separately below rather than inferred from these UI tests.

On the connected Pixel, Zoe can also be launched with:

```bash
adb shell am start -n research.zoetic.zoe/.MainActivity
```

### Device-AI behavior

The Android implementation uses these public APIs:

- [ML Kit text recognition](https://developers.google.com/ml-kit/vision/text-recognition/v2/android), bundled `16.0.1`
- [ML Kit image labeling](https://developers.google.com/ml-kit/vision/image-labeling/android), bundled `17.0.9`
- [ML Kit GenAI Image Description](https://developers.google.com/ml-kit/genai/image-description/android), `1.0.0-beta1`
- [Android SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer)

OCR and image labeling run whenever **Inspect once** is pressed after camera permission and preview are active. The optional describer runs only after its feature is checked and the model is explicitly enabled. Google's API notes that unlocked bootloaders are unsupported; this integration preserves the Pixel's verified, locked boot state rather than attempting a bypass.

A feature status of `DOWNLOADABLE` or `AVAILABLE` is not evidence of description quality. Descriptions, OCR, labels, and accessible-volume measurements remain separate observations. No output is a safety guarantee, object-identity proof, or instruction to act.

## Home and layered little sister

**Zoe home** uses a Pixel-settings-inspired app drawer: Everyday, Measure & explore, and Device tools. Guided Vision, Accessible Volume, and Device Field open inside the shell; the other capabilities open their own activities. Returning home explicitly unbinds the Guided Vision camera. No sensor starts merely because its settings row is visible.

`mobile/card/` contains **Zoe Cell**, the original little-sister companion: a two-command Java Card applet, a bounded host probability encoder, and a generated layer manifest. It preserves strict `p > τ` over explicitly quantized Q0.15 inputs. The current host class for simulation is 2,735 bytes; that is not a CAP or physical-card footprint. Eight APDU simulator tests and six host-codec tests cover shared fixtures, boundary behavior, deterministic encoding, malformed requests, and malformed responses. No reader, CAP installation, physical card, or carrier eSIM modification is claimed. See `mobile/card/README.md` for the protocol, limits, and hardware requirements.

The **Little sister → Zoe Cell** settings row opens a native Android protocol simulator. It executes real bounded requests and responses inside Zoe without a reader, network, SIM access, or third-party card runtime. The screen displays the under-1,900,000-byte companion budget and distinguishes the 2,735-byte reference class from Android APK, CAP, and physical-card footprints. This is a behavioral model, not a Java Card VM or secure-chip emulator.

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

On the connected Pixel 7, all **29 Android host unit tests**, both APK builds, Android lint, and all **26 on-device tests pass**. Lint reports zero errors without a baseline; non-fatal warnings remain visible. The five Swift core tests and five shared equation fixtures also pass. Zoe Cell passes eight Java Card APDU tests and six Python host-codec tests; its measured host class is 2,735 bytes.

The native Android protocol/session model includes 15 host tests and six on-device UI tests, including strict equality, raw APDU errors, defensive copies, reset, replay, and oversized input. Adversarial checks cover 4,352 arbitrary command cases and 1,000 hostile strings with deterministic replay and bounded history. A visible UI transaction returned `A = 3 of 4` with a 15-byte request and 10-byte response, without hardware, SIM, or network access. Ablation reports no dangerous-call, reflection, class-loader, unsafe-operation, or serialization findings in the three compiled core classes. These are bounded test results, not proof of perfect safety.

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
