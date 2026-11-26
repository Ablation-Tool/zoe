# Zoe Fieldglass — Phone-to-Telemetry & Specimen Field Instrument

**Live Interactive Showcase (15 Specimens):** [https://nicholas-michael-kloster.github.io/fieldglass/](https://nicholas-michael-kloster.github.io/fieldglass/)
**Standalone Repo & DIY Teaching Guide:** [https://github.com/Nicholas-Michael-Kloster/fieldglass](https://github.com/Nicholas-Michael-Kloster/fieldglass) · [HOW_IT_WORKS.md](https://github.com/Nicholas-Michael-Kloster/fieldglass/blob/main/HOW_IT_WORKS.md)

## Overview

`guiai.gem.zoe_fieldglass` connects real-world 4K phone captures directly to Zoe's native GEM modules (`guiai.gem.chiasm`, `guiai.gem.zoe_braille_studio`, and `guiai.gem.render`):

1. **Sharpest 4K Frame Auto-Selection** — discrete 2D Laplacian edge variance (`laplacian_sharpness`) picks the crispest frame in any video window.
2. **Perspective Deskew + Gaussian Illumination Division** — flattens angled book/specimen photos and erases uneven lamp shadows (`gray / gaussian_filter(gray, sigma=45)`).
3. **Scalable Vector SVG + 2×4 Unicode Braille** — two-tone `contourf` archival engraving + `BrailleCanvas` Bayer-dithered terminal specimens.
4. **Live Kloster $A_{\tau}(p_t)$ Telemetry & Causal Chiasm** — measures $A_{\tau}(p) = |\{x \in X : p(x) > \tau\}| = \sum_{x \in X} \mathbf{1}[p(x) > \tau]$ alongside Shannon $H_1$, Rényi $H_2$, quartic purity $M_4^{1/4}$, and `guiai.gem.chiasm` Persistent Filtration Tomography.
5. **Loopback USB Phone Showcase** — Range-capable `127.0.0.1` HTTP server + `adb reverse` for zero-cloud playback on Android/Pixel devices.

## CLI Usage

```bash
# Module info & showcase URLs
zoe-fieldglass info

# Print any image as 2x4 Unicode Braille
zoe-fieldglass braille path/to/specimen.png --cols 64

# Clean lighting + trace vector SVG + export Braille
zoe-fieldglass plate path/to/specimen.png -o out/ --title "FIG. 30 · SPIRANTHES ELATA"

# Serve showcase locally over loopback (with HTTP 206 video Range scrubbing)
zoe-fieldglass serve out/ --port 8776
```

## Constitutional Invariants
- `tokens_used = 0` · `auto_flash_allowed = False` · `clinical_action_authorized = False` · `flight_control_authorized = False` · `sentience_claimed = False` · `executed = False`.
