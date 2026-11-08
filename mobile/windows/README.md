# Zoe Trinity · native Windows

**A real Win32 x86_64 desktop application—not a browser wrapper, Python launcher, .NET app, or Electron bundle.** The portable `ZoeTrinity.exe` contains the three-plane measurement kernel, native interface, optional verified journal, and bounded Android/Apple phone-link server. Python is required only for the separate browser-deck implementation, not for this app.

## Run on Windows

Requirements: **64-bit Windows 10 or 11**. No compiler, Python, .NET, LLVM runtime, or administrator installation is required by the portable application.

1. Copy `ZoeTrinity.exe` to a folder you trust.
2. Open it. The local phone-link server starts **off**.
3. Measure locally with **Measure together**, or choose **Start local link** to allow phone connections.
4. Use **Export JSON** for an explicit file export.

The executable is currently unsigned. Windows SmartScreen or antivirus may warn about an unrecognized new binary; do not bypass a warning unless you independently trust and verify the artifact. Compare its SHA-256 hash with `SHA256SUMS.txt`. Production code signing and a real Windows installer remain release work.

## Google Pixel + Windows

With ADB installed and the Pixel connected over USB:

```bat
adb reverse tcp:8767 tcp:8767
```

Choose **Start local link** in Windows Zoe Trinity, then open **Trinity** in Zoe on the Pixel and choose **Connect laptop**. Either side can measure. The Windows server binds to `127.0.0.1` by default; ADB reverse maps the phone's loopback port without exposing a LAN listener.

Remove the mapping afterward if desired:

```bat
adb reverse --remove tcp:8767
```

## Apple + Windows trusted Wi-Fi

Use an explicit private Windows IPv4 address and a pairing code of at least 16 characters:

```bat
set ZOE_TRINITY_PAIR=choose-a-long-local-pairing-code
ZoeTrinity.exe --lan 192.168.1.10 --start-server
```

Replace the example IP with the Windows machine's actual address. In Apple Trinity, enter that URL and pairing code. Pairing is not encryption; use only a trusted local network and non-sensitive experiments. No hotspot, firewall rule, VPN, or public relay is created by Zoe. Windows may separately prompt for network firewall permission; the user controls that decision.

For a console-free local server without the desktop window:

```bat
ZoeTrinity.exe --headless
```

Add `--duration 60` for an automatic stop after 60 seconds. Close the desktop window or interrupt the headless process to stop the server.

## Optional long-term memory

Tiny remains stateless. Add a laptop journal explicitly:

```bat
ZoeTrinity.exe --memory "%USERPROFILE%\Documents\zoe-trinity.jsonl"
```

The journal is append-only, sequence-linked, SHA-256-hashed canonical JSON, bounded to 10,000 events and 64 MiB. Loading verifies every hash and recomputes every measurement. **Fresh view** appends a reset rather than deleting history. Hash chaining is tamper evidence, not authentication or encryption. On Windows, file access is governed by the containing folder's NTFS ACL; the POSIX `0600` claim used on Linux does not apply. Choose a private folder and use one server process per journal.

## Native interface

The Win32/GDI interface uses Georgia and Consolas, porcelain panels, the Zoe orbital eye, chalice/hourglass geometry, and PLACES microcopy. Standard Windows edit controls and buttons remain in the interaction path. No camera, microphone, accessibility capture, telemetry, cloud account, model download, or autonomous action is used by Trinity.

## Build reproducibly

The implementation is C++17 in `native/`:

- `json.*` — bounded JSON parser and canonical serializer.
- `sha256.*` — SHA-256 for journal integrity.
- `trinity_core.*` — exact decimal/Q0.15 measurement, state, and journal recovery.
- `http_server.*` — bounded Winsock phone-link API with Host/Origin/protocol/pair checks.
- `win_main.cpp` — native window, controls, geometry, and explicit exports.

Cross-compile from Linux with CMake and LLVM-MinGW:

```bash
export ZOE_MINGW_ROOT=/path/to/llvm-mingw
mobile/windows/build-windows.sh
```

For a Windows-artifact test run under Wine:

```bash
RUN_WINE_TESTS=1 mobile/windows/build-windows.sh
```

The verified development toolchain was [LLVM-MinGW 20261104 / LLVM 23.1.5](https://github.com/mstorsjo/llvm-mingw/releases/tag/20261104), UCRT Ubuntu x86_64 archive, SHA-256 `919380403de87dca3c581c2053230cd298af5e891286628ba0613b7fed370926`. The script writes portable artifacts to `mobile/dist/windows`.

A native Linux core build also runs the same tests without Wine:

```bash
cmake -S mobile/windows -B /tmp/zoe-native -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/zoe-native
ctest --test-dir /tmp/zoe-native --output-on-failure
```

## Verification boundaries

Current development checks cover native core suites on Linux and Windows/Wine, exact shared APDU fixtures, concurrent submissions, journal tamper rejection, the actual Windows server API under Wine, and a captured native window. Ablation reports no suspicious PE markers; a separate PE import listing shows Windows system and UCRT dependencies rather than LLVM runtime DLLs.

**Wine is not Windows.** The portable app still needs a real Windows 10/11 run, signing, SmartScreen reputation, supported-device checks, large-text/accessibility review, and a physical Pixel-to-Windows connection. Apple still requires Xcode and an iPhone. No production release or perfect-security claim is made.
