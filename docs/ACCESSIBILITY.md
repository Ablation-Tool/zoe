# Ablation + GEM Accessibility Guide (Disability-First Quick-Card)

**Scope:** Native GTK/VTE & Tk Graphical Workbench in [`components/ablation/gem-lab/`](../components/ablation/gem-lab/README.md) (synced identically with standalone [`Ablation-Tool/ablation`](https://github.com/Ablation-Tool/ablation))
**Core Engine:** [`accessibility.py`](../components/ablation/gem-lab/gem/accessibility.py) · [`safety.py`](../components/ablation/gem-lab/gem/safety.py) · [`test_accessibility.py`](../components/ablation/gem-lab/tests/test_accessibility.py)
**Constitutional Alignment:** [`CONSTITUTION.md`](CONSTITUTION.md) (Human Agency, Transparency, Reversibility)

---

## 1. Why Accessibility Is a Mother Stock

Reverse-engineering workbenches should never force anyone to squint at low-contrast grey-on-black hex dumps, guess meaning from red/green dots alone, or fight microscopic hit targets. Ablation + GEM treats disability-first ergonomics as a first-class engineering invariant across Linux (GTK 3 / VTE + ATK), macOS, and Windows (Tk).

---

## 2. Quick-Reference Keyboard & Visual Controls

| Feature | Setting / Control | Verified Range or Target |
| :--- | :--- | :--- |
| **Live Text Zoom** | `Ctrl++` (zoom in) · `Ctrl+-` (zoom out) · `Ctrl+0` (reset) | **85% to 200%** (`0.85, 1.0, 1.15, 1.3, 1.5, 1.75, 2.0`, WCAG 1.4.4) |
| **Color Palettes** | `system` · `colorblind` (Okabe-Ito safe) · `high-contrast` | **4.5:1 WCAG AA** standard · **7.0:1 WCAG AAA** high-contrast |
| **Line Spacing** | Configurable vertical breathing room | **1.0x to 2.0x** (`1.0, 1.2, 1.4, 1.6, 1.8, 2.0`) |
| **Dyslexia-Friendly Spacing** | Extra letter spacing toggle (`dyslexia_spacing`) | `+1px` letter spacing across labels, entries, text & tree views |
| **Reduced Motion** | `reduced_motion` toggle | `transition-duration: 0ms; animation-duration: 0ms;` (WCAG 2.3.3) |
| **High-Visibility Focus Ring** | `focus_ring` (enabled by default) | `2px solid` outline with `2px` offset (WCAG 2.4.7) |
| **Screen-Reader Metadata** | `apply_atk_metadata(...)` on GTK widgets | Descriptive ATK names, descriptions, and status roles |
| **Panel Shortcuts** | `Alt+S` Settings · `Alt+O` OS Optimization · `Alt+A` a11y Optimization · `Esc` Close | Keyboard-first navigation with text-based Lab tree alternative |

---

## 3. Non-Color Semantics & Contrast Verification

GEM enforces **color-independent meaning** throughout its workspace:

- Tree statuses (`not_started`, `in_progress`, `partial`, `blocked`, `reviewed`, `complete_scoped`, `rejected`, `not_applicable`) remain explicit text rather than relying solely on tile hue or icon color.
- Diagnostic reports pair `PASS` and `REVIEW` text badges, bold subjects, and clear section headings with live contrast checks via `evaluate_accessibility(...)`.
- `contrast_ratio(foreground, background)` computes exact WCAG 2.1 relative luminance and checks `pass`, `review`, and `accent` text colors against the active background (`4.5:1` for AA; `7.0:1` for AAA in `high-contrast` mode).

---

## 4. One-Click OS Accessibility Sync & Atomic Persistence

GEM reads host accessibility preferences cleanly without third-party dependencies (`detect_system_accessibility()`):

- **Linux (GNOME / Gio):** Reads `org.gnome.desktop.interface` (`accent-color`, `enable-animations`, `text-scaling-factor`, `gtk-theme`) and `org.gnome.desktop.a11y.interface` (`high-contrast`).
- **macOS:** Reads `AppleAccentColor` and `com.apple.universalaccess` (`increaseContrast`, `reduceMotion`) via `/usr/bin/defaults`.
- **Windows:** Reads `HKCU\Software\Microsoft\Windows\DWM` (`AccentColor`), `Control Panel\Accessibility\HighContrast`, `TextScaleFactor`, and `MinAnimate`.

Preferences are persisted atomically to `<session_root>/accessibility.json` using strict schema validation (`validate_accessibility_settings`), rejecting unknown keys, non-finite numbers, or files larger than **`16 KiB`** (`MAX_SETTINGS_BYTES = 16 * 1024`), and falling back safely to `DEFAULT_SETTINGS` without silently corrupting session state.

---

## 5. Built-In a11y Optimization & Honest Boundaries

Pressing **`Alt+A`** (or clicking Zoe's red-and-white GEM emblem in the titlebar and selecting **a11y Optimization**) runs a read-only audit and prints exact `[PASS]` / `[REVIEW]` checks before proposing any remediation. Nothing is changed without explicit approval (**Allow Permission** vs **Deny Permission**).

**Honest Boundary (Built Right Into the Audit):**
> Automated contrast, focus-ring, zoom, and ATK metadata checks **do not replace manual validation** with Orca, NVDA, Narrator, VoiceOver, or the user's real assistive technology setup.

---

## 6. Run the Accessibility Test Suite Offline

```bash
PYTHONPATH=components/ablation/gem-lab python3 -m unittest discover -s components/ablation/gem-lab/tests -p "test_accessibility.py" -v
```

See also: [`components/ablation/gem-lab/README.md`](../components/ablation/gem-lab/README.md) · [`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md) (Mother Stock No. 4) · [`INDEX.md`](INDEX.md).
