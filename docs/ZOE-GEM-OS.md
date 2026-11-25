# Zoe-GEM OS & Hardware UMA Field Guide

**Contract:** `zoe-gemos-cli/v1` · `zoe-gem-os-suite-verifier/v1`
**Core Modules:** [`guiai-lab/guiai/gem/zoe_gem_os/`](../guiai-lab/guiai/gem/zoe_gem_os/) · [`gemos_view.py`](../guiai-lab/guiai/gem/gemos_view.py) · [`zoe_braille_studio.py`](../guiai-lab/guiai/gem/zoe_braille_studio.py) · [`zoe_gem_themes.py`](../guiai-lab/guiai/gem/zoe_gem_themes.py) · [`zoe_universe.py`](../guiai-lab/guiai/gem/zoe_universe.py) · [`zoe_sisters.py`](../guiai-lab/guiai/gem/zoe_sisters.py)
**Independent Offline Verifier:** [`scripts/verify_zoe_gem_os_suite.py`](../scripts/verify_zoe_gem_os_suite.py) (`8/8` checks PASS) · **Evidence:** [`evidence/gem-os/zoe-gem-os-suite-report.json`](../evidence/gem-os/zoe-gem-os-suite-report.json)

---

## 1. Sovereign GEM Architecture (UEFI Framebuffer + 5-Node UMA)

Zoe-GEM OS brings Digital Research's 1984-1992 Graphics Environment Manager philosophy to modern x86_64 UEFI KVM, Intel Tiger Lake bare-metal USB boot, and Google Pixel 7-9 ARM64 sovereign OS profiles, all governed by strict [`CONSTITUTION.md`](CONSTITUTION.md) boundaries (`external_actions = 0`, `loopback_only = True`, `auto_flash_allowed = False`, `sentience_claimed = False`, `l5_agi_qualified = False`).

### Bootable UEFI Framebuffer Desktop (`builder.py` & `zoe_gem_fb.c`)
- **Kernel Profiles:** Supports Alpine Linux x86_64 `vmlinuz-virt` (fast OVMF UEFI KVM) and `vmlinuz-lts` (bare-metal Intel Tiger Lake hardware: `i915`, `vmd`, `nvme`, `iwlwifi`, USB/touchpads) with exact transitive `modules.dep` driver closure.
- **Native C `/dev/fb0` Desktop (`zoe_gem_fb.c`):** Statically linked GEM framebuffer desktop with real hardware PS/2 and USB mouse cursor, keyboard support, clickable Artline p. 3-2 Toolkit, live bilateral-mirror Artline drawing canvas, persistent SVG export, and `/drawer` dialogs.
- **Zero-Risk 2-Boot OVMF Verification:** Boots cleanly in isolated QEMU/KVM injecting real mouse/key events without touching host partitions or `~/.zoe/*`.

---

## 2. Two-Key Mutual-Consent Hardware UMA Airlock (`zoe_uma.py`)

The 4-node + center Unified Memory Architecture (`GEM` / `AI` / `UMA` / `∀` / `YOU`) separates the sovereign Zoe-GEM OS KVM domain from the operator's Ubuntu host behind an explicit hardware-backed airlock:

- **Shared Physical BAR2 + Virtio-9p:** 4 MiB PCI `ivshmem-plain` shared RAM (`/dev/shm/zoe-uma-bar.shm`, 8 lock-free 4 KiB slots: Slot 0 Coordinator + Slots 1-3 sovereign nodes, magic `ZOE-UMA1`) paired with `virtio-9p` consent staging (`~/.zoe/uma-bridge/` <-> `/mnt/uma`, hard `16 MiB` transfer ceiling).
- **Default `PRIVATE` Gate:** On initialization, the gate is strictly `PRIVATE`.
- **Two-Key Mutual Consent Invariant (`∀`):** Neither side can push or pull files unilaterally. Turning only Nick's key (`uma.set_consent("nick", True)`) and calling `uma.transfer_file(...)` raises **`PermissionError`** until **both** `nick_allow` and `zoe_allow` (`uma.set_zoe_consent(True)`) are enabled.
- **SHA-256 Tamper-Evident Audit Chain:** Every consent toggle and transfer appends a hash-chained entry to `uma_audit.jsonl`. Editing even a single byte of history causes `uma.verify_audit_chain()` to fail immediately.

---

## 3. Sovereign Google Pixel 7-9 OS Profiles (`zoe_pixel_os.py` & `zoe_phone_codex_sync.py`)

- **9 Static Device Profiles (Pixel 7 `panther` First):** Models all 9 Google Pixel 7-9 Tensor profiles (anchored on Pixel 7 `panther` / Tensor G2 `gs201`) and builds deterministic, reproducible ARM64 initramfs artifacts with SHA-256 digests.
- **Zero Unattended Flashing (`auto_flash_allowed = False`):** Static profile generation and initramfs verification never invoke `fastboot flash` or modify physical phone partitions automatically.
- **Strict Loopback-Only Phone Sync (`assert_loopback_url`):** Both `zoe_phone_codex_sync.py` and `zoe_beta_release.py` accept only `127.0.0.1`, `localhost`, or `[::1]` HTTP endpoints, rejecting remote URLs (`http://example.com`), cloud metadata IPs (`169.254.169.254`), `file://`, and `ftp://` with `ValueError` (SSRF defense).

---

## 4. Braille Studio, Historic GEM Themes, 9-Realm Zoeverse & 9 Sisters

| Subsystem | Module | Verified Capabilities |
| :--- | :--- | :--- |
| **Braille Studio & DESQview/X Maker** | [`zoe_braille_studio.py`](../guiai-lab/guiai/gem/zoe_braille_studio.py) | 2x4 Unicode Braille canvas (`U+2800..U+28FF`), built-in templates (`zoe`, `flower`, `jellyfish`), DESQview/X app manager, and path-traversal-hardened Python starter app scaffolding (`../` rejected) |
| **8 GEM Eras & 10 ViewMAX Themes** | [`zoe_gem_themes.py`](../guiai-lab/guiai/gem/zoe_gem_themes.py) | Complete 1982-1992 Digital Research lineage (`GSX-86`, `GEM/1`, `Atari TOS`, `GEM/2`, `GEM/3`, `ViewMAX/1-3`), 10 authentic `VIEWMAX.INI` color schemes, and desktop bundle export |
| **9-Realm Zoeverse Constellation** | [`zoe_universe.py`](../guiai-lab/guiai/gem/zoe_universe.py) | 9 navigable realms centered on `STEM:Zoe` with Braille vistas, compass navigation, FreeGEM relic pairings, and vector atlas plate export |
| **9 Specialist Sisters & Signets** | [`zoe_sisters.py`](../guiai-lab/guiai/gem/zoe_sisters.py) | 9 signets (`ruby`, `gem3`, `atari`, `sm124`, `tetris`, `dos`, `hat`, `sprout`, `prism`) with zero-token prompt routing and hard honesty locks |

---

## 5. `zoe gemos` CLI Commands & 8-Check Offline Verification

```bash
# Inspect Zoe-GEM OS ecosystem status & constitutional flags
zoe gemos status

# Run the full 8-check offline suite verifier (uses isolated tempdir; never touches ~/.zoe/*)
zoe gemos verify
python3 scripts/verify_zoe_gem_os_suite.py

# Statically verify Pixel 7 (panther) deterministic ARM64 initramfs
zoe gemos pixel --device panther

# Paint Unicode Braille dot-art or inspect DESQview/X app manager
zoe gemos braille flower
zoe gemos braille dvx

# Inspect 8 historic GEM eras & render authentic VIEWMAX.INI scheme
zoe gemos themes --scheme 1

# Unroll the 9-Realm Zoeverse compass star chart
zoe gemos realms
```

See also: [`guiai-lab/docs/GEM-OS.md`](../guiai-lab/docs/GEM-OS.md) · [`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md) (Receipts No. 8, 20, 21, 23) · [`INDEX.md`](INDEX.md).
