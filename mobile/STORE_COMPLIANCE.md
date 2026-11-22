# Zoe (beta) · Store Compliance Checklist (Google Play + Apple App Store · `v0.9.4-beta`)

Zoe is **free ($0.00)**, has **no ads, no analytics, no tracking SDKs, no accounts, and no in-app purchases**.
Core functionality runs offline on-device. Every network lane is **explicitly user-initiated and off by default** (opt-in Eliza-GEM / Closed-Loop L5 Digestion bridge, Trinity laptop bridge, opt-in DuckDuckGo/Wikipedia web citations, opt-in CPC Google Patents lookup, optional user-supplied BYOK AI keys, and optional Connectivity speed check).

## Already Implemented in This Repository (`v0.9.4-beta`)

| Area | Android (`mobile/android`) | Apple (`mobile/apple` + `mobile/shared`) |
|:---|:---|:---|
| Target / SDK | `targetSdk 36` (`compileSdk 36`, `minSdk 26`, Java 17) | iOS 17+ deployment target, Swift 6 (`ZoeCore` verified on Swift 6.1.3) |
| Version | `0.9.4` (`versionCode 15`) | `0.9.4` (`CURRENT_PROJECT_VERSION 15`) |
| Backup & Data Safety | `allowBackup="false"`, `fullBackupContent="false"`, `data_extraction_rules.xml` excludes all app data | App-private container only; `PrivacyInfo.xcprivacy` declares no tracking & no collected data |
| Privacy Firewall | Client + server firewall hard-excludes `SafeConvert`, `Privacy Vault`, raw photos & private chat bodies from `/api/digest/mobile` | Mirrors identical `MobileDigestionCore.assertOutgoingFirewall()` guarantees in Swift 6 |
| Permissions | Camera, mic, GPS, BLE, and ARCore are runtime and explicit tap only; legacy `BLUETOOTH*` capped at `maxSdkVersion=30` | Specific, honest `Info.plist` usage strings for camera, mic, speech, location, BLE & local network |
| Network Security | `network_security_config.xml` blocks cleartext everywhere except `127.0.0.1` / `localhost` | `NSAllowsLocalNetworking` only (no arbitrary HTTP loads) |
| Encryption | HTTPS for all remote endpoints; `AndroidKeyStore AES-256-GCM` + `P-256 ECDH` in Privacy Vault | CryptoKit E2EE; note export-compliance review for standard encryption if distributing outside exempt categories |
| Large Screens & Foldables | `resizeableActivity="true"`, no orientation lock, `configChanges` rotation continuity across **all 20 Android Activities**, symmetrical `16dp`/`8dp` M3 layout | `UIRequiresFullScreen=false`, adaptive `NavigationSplitView` / `NavigationStack` keeping controls clear of fold crease |
| Accessibility | TalkBack labels, `>= 48dp` touch targets, plain language, System Dark/Light + 1-tap toggle, Comfort Mode (slower speech & calmer motion) | VoiceOver labels, `>= 48pt` targets, Dynamic Type, System Dark/Light + 1-tap toggle |
| Accessibility Service | Prominent disclosure + explicit consent dialog before opening settings; `canRetrieveWindowContent="false"` | n/a |
| Screen Privacy | Dynamic `FLAG_SECURE` when SafeConvert safety layer is open | `UIVisualEffectView` blur shield + instant voice/exit cutoff on `willResignActive` |
| Icons | Pure-white **Zoe GEM-Ellipsis** adaptive + monochrome Material You icon | Complete 18-size opaque RGB `AppIcon` catalog + 1024 marketing icon |

## Google Play Console Steps (Manual Release Tasks)

1. Create the listing as **Free** (*Tools* or *Education*).
2. **Data Safety:** Declare *No data collected, no data shared by developer*. Document that optional user-configured endpoints (BYOK AI keys, opt-in web search, optional workstation bridge) transmit only on deliberate user tap.
3. **AccessibilityService Declaration:** Explain that `ZoeAccessibilityService` powers optional, user-triggered one-shot screen inspection/gestures inside **Field Kit → Screen Space** (not passive background monitoring) and attach a short screen recording of the disclosure and consent flow.
4. **BLE & Location Declarations:** Explain opt-in Maps & Safety / Location Field and SafeConvert's opt-in 1-shot GPS + short-range (`30-min` auto-expiring) offline BLE Help Beacon.
5. Publish a public **Privacy Policy URL** matching `CONSTITUTION.md` and `mobile/SECURITY.md`.
6. Sign a release **AAB** (`./gradlew bundleRelease` with a dedicated production upload keystore + Play App Signing — never ship the debug APK to Play Store).
7. Capture phone, tablet, and foldable screenshots and complete the content-rating questionnaire (`13+` recommended due to SafeConvert personal-safety & trauma-care guidance).

## Apple App Store Connect Steps (Requires macOS + Xcode)

1. Open `mobile/apple/Zoe.xcodeproj` in Xcode on macOS, assign your Apple Developer Team, and retain bundle ID `research.zoetic.zoe`.
2. Build, run UI/device checks on real iPhone, iPad, and foldable/split-screen widths, and resolve any iOS SDK / Swift 6 UI compiler nits.
3. Review App Store encryption export compliance (`ITSAppUsesNonExemptEncryption`) accurately for CryptoKit E2EE before submission.
4. Complete App Privacy (*Data Not Collected*, *Tracking: No*), age rating, and App Review notes explaining SafeConvert (`911` variants unlock), idle-by-default sensors, and optional workstation companion setup.

## Honest Remaining Limits

- **Swift Core vs. Xcode App Build:** On this Linux host, the shared Swift package (`mobile/shared`, `ZoeCore`) compiles cleanly under Swift 6.1.3 and passes **`20/20` unit tests (`0` warnings)**. Full Xcode compilation of the iOS SwiftUI app, Apple code signing, simulator execution, and physical iPhone/iPad testing **have not been run** and require macOS + Xcode.
- **No Production Signing or Third-Party Audit Yet:** Current GitHub release APKs are development-signed debug builds; independent security and accessibility audits remain before any public store release.
