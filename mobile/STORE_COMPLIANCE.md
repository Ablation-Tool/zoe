# Zoe · Store Compliance Checklist (Google Play + Apple App Store)

Zoe is **free ($0.00)**, has **no ads, no analytics, no tracking, no accounts and no in-app purchases**.
Everything runs on device. Network use is optional and user-initiated (Eliza-GEM bridge, Trinity laptop, optional Gemini key).

## Already done in this repo

| Area | Android (`mobile/android`) | Apple (`mobile/apple`) |
|---|---|---|
| Target / SDK | `targetSdk 36` (meets the Aug 31 2026 Play requirement) | iOS 17 deployment target, Swift 5 |
| Version | `0.2.0` (code 2) | `0.2.0` (build 2) |
| Backup / data | `allowBackup=false`, data-extraction rules exclude everything | Preferences only (theme, layout, Zapp order, voice) in app container |
| Privacy manifest | n/a | `Zoe/PrivacyInfo.xcprivacy`: no tracking, no collected data, UserDefaults reason `CA92.1` |
| Permissions | Camera, mic, location, BLE are runtime and user-initiated. Legacy `BLUETOOTH*` capped at `maxSdkVersion=30` | Usage strings for camera, mic, speech, local network are specific and honest |
| Network | Cleartext only to `127.0.0.1` / `localhost` | `NSAllowsLocalNetworking` only (no arbitrary loads) |
| Encryption | HTTPS only | `ITSAppUsesNonExemptEncryption=false` |
| Large screens / foldables | `resizeableActivity=true`, no orientation lock, borderless Google Gemini-inspired ergonomic layout + floating thumb-zone action capsule, state restored on rotate/fold | `UIRequiresFullScreen=false`, multiple scenes, `NavigationSplitView` when width is regular (unfolded iPhone Duo / iPad), `NavigationStack` + floating Gemini action capsule when compact (iPhone / folded cover), selection kept in `@SceneStorage`, controls stay clear of the fold crease |
| Accessibility | TalkBack headings, single-focus 62dp ergonomic rows, 48–54dp touch targets, plain child-friendly language, System Dark/Light + 1-tap toggle, Comfort mode (slower speech & reduced motion) | VoiceOver labels and header traits, 48–62pt targets, Dynamic Type, System Dark/Light + 1-tap toggle |
| Accessibility service | Prominent disclosure + explicit consent dialog before opening settings; `canRetrieveWindowContent=false` | n/a |
| Icons | Zoe GEM-Ellipsis (pure white Google-family adaptive icon + monochrome Material You vector) | Full `AppIcon` set (18 opaque RGB sizes, pure white Zoe GEM-Ellipsis, 1024 marketing icon) |
| Screen privacy | `FLAG_SECURE` in SafeConvert | Blur shield when the app leaves the foreground |

## Google Play Console (you do these in the browser)

1. Create the app: **Free**, category *Tools* (or *Education*).
2. **Data safety**: *No data collected, no data shared*. Camera, mic and location are processed on device only.
3. **Permissions declaration for AccessibilityService**: purpose is optional assistive one-shot screen capture and explicit single gestures the user starts. Attach a short screen recording showing the disclosure, consent button, and the feature. `ZoeAccessibilityService` is not flagged as an accessibility tool, so keep it to user-initiated, deterministic actions only.
4. Provide a public **privacy policy URL** stating the above.
5. Upload a signed **AAB** (`./gradlew bundleRelease` with your upload key; enrol in Play App Signing).
6. Screenshots: phone, and **foldable / tablet** screenshots (dedicated foldable screenshots become mandatory in April 2027).
7. Content rating questionnaire, target audience (13+ suggested because SafeConvert covers personal-safety resources).
8. Plan for **API 37** (August 2027): no orientation or resizability opt-outs are used, so this is a version bump.

## Apple App Store Connect (needs a Mac with Xcode)

1. Open `mobile/apple/Zoe.xcodeproj`, set your **Team** and keep bundle id `research.zoetic.zoe`.
2. Product → Archive → Distribute → App Store Connect.
3. App Privacy: **Data Not Collected**. Tracking: **No**.
4. Price: **Free**. Age rating: complete the questionnaire.
5. Screenshots for 6.9" iPhone, iPad, and **iPhone Duo / Fold** (outer display and unfolded inner display).
6. Review notes: camera and microphone start only after a tap; speech recognition is on-device only; Trinity needs a laptop companion you control (demo steps in `README`).
7. Test in the Xcode simulator at compact and regular widths and while resizing in Split View to confirm the layout and scene state continuity.

## Honest limits

* The Apple code could not be compiled on this Linux machine (no Swift toolchain). Plist, privacy manifest, asset catalog, and project-file integrity were validated by script, but please build once in Xcode and fix any compiler nit.
* "iPhone Duo / Fold" behaviour is implemented with Apple's public adaptive APIs (size classes, split view, scene storage). Re-test on the real device or simulator when it ships.
