# Zoe Desktop App (Linux, Windows & Apple macOS)

**Zoe is a Research Partner.** The Zoe Desktop App puts the **Dorothy 3D Brain Observatory** at the center of your desktop on **Linux**, **Windows 10/11**, and **Apple macOS** with zero tracking, zero ads, and zero cloud requirements.

## Included on Every Desktop Platform

- **Dorothy 3D Brain Centerpiece:** `240,376` stereotaxic triangles (ICBM152, AAL-116, 32 Pauli CIT168 deep nuclei, Circle of Willis, 12 Cranial Nerves, DTI white-matter tracts) + live synchronized `0.74 mm` MNI152 T1-MRI slices.
- **7 Real-Time GPU Shaders & Simulators:** Tissue SSS, Lobe Atlas, AAL-116, GLSL Fresnel Glass X-Ray, Connectome Neon, Dorothy Continuum $A_\tau(p)$, CAD Wireframe, 5 Functional Neural Circuits, 4 Cerebrovascular Stroke Territory Simulators, 19-electrode 10-20 EEG Cap, and 3D Millimeter Caliper.
- **Ask Zoe Neuroscience Q&A:** Direct brain questions linked to 1-tap `Fly to 3D`, plus **Videos & Gallery**, **25 Verified Plates**, and the **52 Brodmann + 12 Cranial Nerves Atlas**.

## 1. Linux Desktop (`zoe-desktop-v0.9.6-linux.tar.gz`)

Runs in a native **GTK 3 + WebKit2GTK** WebGL2 desktop window (automatically falls back to standalone Chrome/Chromium app window if WebKitGTK is absent).

```bash
tar -xzf zoe-desktop-v0.9.6-linux.tar.gz
cd ZoeDesktop
./zoe-desktop                       # Launch Zoe Desktop immediately
./install-desktop-shortcut.sh       # Optional: add Zoe to your app menu & Desktop
```

Or run directly from a git clone:

```bash
python3 desktop/zoe_desktop.py
```

## 2. Windows 10/11 Desktop (`zoe-desktop-v0.9.6-windows-x64.zip`)

Requires **zero Python, zero .NET, and zero external runtimes**. Uses Windows built-in PowerShell loopback serving with HTTP `206` byte-range video scrubbing and opens a standalone Microsoft Edge app window.

1. Extract `zoe-desktop-v0.9.6-windows-x64.zip`.
2. Double-click **`Launch Zoe.bat`**.
3. The portable native Win32 C++17 companion **`ZoeTrinity.exe`** (for Pixel/Apple local pairing) is also bundled in the same folder (source in [`mobile/windows/`](../mobile/windows/README.md)).

## 3. Apple macOS Desktop (`zoe-desktop-v0.9.6-macos.zip`)

Includes a ready-to-run **`Zoe.app`** bundle plus the native Apple `AppKit + WKWebView` Swift source (`ZoeMacApp.swift`).

1. Extract `zoe-desktop-v0.9.6-macos.zip`.
2. Double-click **`Zoe.app`** (or right-click -> **Open** on first run while unsigned).
3. Optional: compile the pure native Swift `WKWebView` binary directly on macOS:

```bash
swiftc -O ZoeMacApp.swift -framework Cocoa -framework WebKit -o Zoe.app/Contents/MacOS/Zoe
```

## Reproducible Packaging

Rebuild all three desktop packages and SHA-256 checksums from source:

```bash
python3 desktop/zoe_desktop.py --self-test
python3 desktop/build_desktop_packages.py
```
