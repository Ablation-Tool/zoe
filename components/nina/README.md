<p align="center">
  <img src="assets/lume-header.svg" alt="Lume 1.0 — Zoe Voice Studio &amp; Nina Neural TTS" width="100%" />
</p>

# Lume 1.0 — nina

Read text aloud using open source neural TTS.

**Lume 1.0** brings Zoe's smiling ruby GEM identity to Nina — delivering high-quality, natural-sounding voices on Linux through a CLI, a desktop GUI with a live Voice Studio & 5-band Equalizer, and a browser extension. Load a book, paste text, sculpt your own voice EQ curve, or read any webpage — no API key, no account required.

- **CLI** — pipe any text to `nina` with tuned female voice profiles, custom EQ, and creative audio effects
- **Desktop GUI & Voice Studio** — paste text or load a book, shape a live 5-band EQ curve, audition effects, and save/share presets
- **Browser extension** — one click reads any webpage aloud with a floating toolbar

---

## Install

```bash
sudo apt install mpv
# Optional: needed when exporting EQ/effect-processed MP3 files with `nina -o`
sudo apt install ffmpeg

git clone https://github.com/sshpie/nina
cd nina
pip install -r requirements.txt
chmod +x nina.py nina_gui.py
ln -s "$PWD/nina.py" ~/.local/bin/nina
```

---

## Zoe × Natasha 3D Fusion & Fine-Tuned Female Voices

Lume 1.0 fuses **Zoe's first-principles 44.1 kHz 3D binaural App voice engine** (`guiai/gem/zoe_voice.py` — Rosenberg-Klatt soprano formant glow, lyrical shimmer, and Woodworth 3D binaural HRTF + Schroeder room acoustics) with **Natasha (`en-AU`)** as the signature default voice **`zoe`** (`★ Zoe × Natasha (Native 3D)`), alongside standalone offline **`zoe-app`** (`ZoeNative-3D`) and all **24 acoustically calibrated female English voices**:

- **`zoe`** (`★ Zoe × Natasha (Native 3D)`) is the default voice across CLI and GUI (with automatic offline fallback to `ZoeNative-3D` when disconnected).
- **`zoe-app`** (`★ Zoe Native · App 44.1kHz 3D`) runs Zoe's 100% offline first-principles voice & soprano singing straight through the live 5-band Equalizer and all creative Audio FX.
- Pick any voice right inside the **Voice Studio & Equalizer** and click **⭐ Set Default** (or run `nina -v <voice> --set-default`) to choose your own personal default voice.
- Pass `--raw` on the CLI or toggle **Enable Fine-Tuning & EQ** in the GUI to hear any voice unprocessed.

---

## CLI usage

```bash
# Read text with Zoe's default tuned voice
nina "The quick brown fox jumps over the lazy dog"

# Pipe from stdin
cat article.txt | nina

# Switch voices (all 24 female voices are pre-tuned)
nina -v helen "Hello from Helen"
nina -v libby "Hello from Libby"
nina -v guy "Hello from Guy"

# Try a creative audio effect or custom preset
nina -v zoe -e cathedral "Starlight gathers over the quiet hills."
nina -v zoe_noir "It was a rainy Tuesday night downtown."

# Customize pitch, speed, and 5-band EQ (120Hz, 350Hz, 1.2kHz, 3.2kHz, 9kHz)
nina -v zoe -p -6Hz -r "-5%" --eq "2.5,-1.5,0,2,4" "Custom velvet tone."
nina -v aria --eq "warmth=3,air=4" -e fireside "Cozy evening reading."

# Bypass all fine-tuning, EQ, and effects
nina -v helen --raw "Dry unprocessed output."

# Save EQ/effect-processed audio to MP3 (uses ffmpeg when filters are active)
nina -v zoe -e podcast_pro -o output.mp3 "Save this as studio audio"

# Show the Lume 1.0 terminal header
nina --header
python3 lume_header.py

# List all voices, tuned female profiles, and creative effects
nina --list
nina --list-female
nina --list-effects

# Save your own reusable presets or update a voice's personal default
nina -v zoe -p -5Hz --eq "2,-1,0,2,4" -e whisper_asmr --save-profile midnight_zoe
nina -v helen -p -2Hz -e fireside --tune-voice
```

### Voice shortcuts

| Shortcut | Locale | Style |
|----------|--------|-------|
| `zoe` | en-US | Warm, expressive, silky-air studio voice (default) |
| `ava` | en-US | Rich poise with lifted top-end air |
| `helen` | en-IE | Warm Irish cadence with crisp storytelling presence |
| `emma` / `emma-ml` | en-US | Conversational, airy clarity |
| `aria` | en-US | News, clear, softened upper-mids |
| `jenny` | en-US | Gentle, lifted conversational tone |
| `michelle` | en-US | Deep velvety tone balanced with shimmer |
| `ana` | en-US | Soft, mellow lowered pitch |
| `libby` | en-GB | Lively British female |
| `sonia` | en-GB | Poised British female |
| `maisie` | en-GB | Bright British tone grounded with warmth |
| `natasha` | en-AU | Sunny Australian female |
| `clara` | en-CA | Clear Canadian female |
| `molly` | en-NZ | Relaxed New Zealand female |
| `yan` | en-HK | Focused Hong Kong English female |
| `neerja` / `neerja-exp` | en-IN | Rounded, expressive Indian English female |
| `asilia` | en-KE | Balanced East African English female |
| `ezinne` | en-NG | Poised Nigerian English female |
| `rosa` | en-PH | Warm Philippine English female |
| `luna` | en-SG | Smooth Singaporean English female |
| `imani` | en-TZ | Softened Tanzanian English female |
| `leah` | en-ZA | Warm South African English female |
| `alex` | en-US | Warm, confident male |
| `brian` | en-US | Casual male |
| `guy` | en-US | News, authoritative male |
| `ryan` | en-GB | British male |
| `william` | en-AU | Australian male |
| `connor` | en-IE | Irish male |

Full voice IDs also work: `nina -v en-US-BrianMultilingualNeural "..."` — run `nina --list` to see all English and international voices.

---

## Creative Effect Presets & 5-Band Equalizer

Nina shapes playback in real time through `mpv` audio filter chains (and exports identically via `ffmpeg` when using `-o`):

- **5-Band Graphic EQ (`-12` to `+12 dB`)**: **Warmth** (`120 Hz`), **Body** (`350 Hz`), **Mid** (`1.2 kHz`), **Presence** (`3.2 kHz`), and **Air** (`9 kHz`).

| Effect Preset | Character |
|---------------|-----------|
| `zoe_velvet` | Intimate warm studio compression with a whisper of room air |
| `flat` | Clean / Dry (EQ bands still apply unless `--raw` is used) |
| `podcast_pro` | Punchy broadcast compression and crystal articulation |
| `fireside` | Cozy rolled-off highs and gentle warmth for long listening |
| `cathedral` | Spacious ethereal multi-tap reverb for poetry and storytelling |
| `vintage_radio` | Classic 1940s noir tube-radio bandpass and tight compression |
| `cyber_holo` | Futuristic sci-fi shimmer with subtle phaser and space |
| `whisper_asmr` | Ultra-close intimate dynamics with soft breathy presence |
| `vinyl_lofi` | Warm analog tape rolloff with relaxed dynamics |
| `stage_chorus` | Subtle shimmering flanger and soft echo for dreamy narration |

Example creative custom profiles included out of the box: `zoe_noir`, `zoe_starlight`, and `zoe_holo` (use with `nina -v zoe_noir "..."` or pick them in the GUI).

---

## Desktop GUI & Voice Studio

```bash
python3 nina_gui.py
```

Pick a voice from the dropdown, set speed and quick **Effect** preset, then:

- **Paste text** and press **▶ Play**
- **Filter voices** by text or toggle **Female voices only**
- **🎛 Studio / EQ** opens the live **Voice Studio & Equalizer**:
  - Interactive **5-band EQ curve canvas** — drag points directly on the curve or adjust the 5 vertical sliders
  - **Voice Prosody** sliders for **Pitch** (`Hz`), **Pace** (`%`), and **Volume** (`%`)
  - **EQ Curves** & **Audio Effects** selectors plus **🎲 Surprise Me** for creative random combinations
  - **🎧 Preview Tuned** vs **🔊 Compare Raw** for instant A/B listening without interrupting book playback
  - **💾 Save for Voice**, **★ Save Preset…**, **↺ Zoe's Tune**, **Flat**, and **📥 Import / 📤 Export** JSON presets
- **Clipboard** button pulls whatever is in your clipboard directly into the text area
- **Open Book** loads a TXT, PDF, EPUB, or a directory of Markdown files

### Book reader

The GUI includes a full book reader with chapter navigation:

- Supports TXT, PDF, EPUB, and directory-based books (Markdown files)
- Chapter picker dropdown and ◀ ▶ buttons to navigate
- **Vertical bookmark bar** — stacked tab markers on the right edge of the text area; click any tab to jump to that chapter; current chapter highlighted in blue
- Auto-advances to the next chapter when TTS finishes
- Saves your reading position per book between sessions
- Stop button cuts audio immediately

Point **Open Book** at any of these formats or point it at a folder of numbered Markdown chapter files.

---

## Editing & Contributing Voice Profiles on the Repo

All default calibrations, EQ curves, creative effect filter chains, and custom recipes live in [`voice_profiles.json`](voice_profiles.json) right in the repository root.

- **Personal tweaks (`~/.config/nina/voice_profiles.json`)**: When you save overrides or custom presets from the CLI (`--tune-voice` / `--save-profile`) or the GUI Studio, Nina writes only your changes to `~/.config/nina/voice_profiles.json` and merges them cleanly on top of the repo defaults. You can also **Export** any profile to a `.json` file to share it.
- **Sharing with everyone on the repo**: Edit `voice_profiles.json` directly (or merge your exported JSON into `eq_curves`, `effect_presets`, `female_profiles`, or `custom_profiles`) and open a pull request so everyone gets your voice calibration or creative audio effect!

---

## Browser extension

Load `extension/` as an unpacked extension in Chrome, Brave, or any Chromium browser.

- **Keyboard shortcut:** `Ctrl+Shift+U` toggles the read-aloud bar on any page
- **Popup:** click the Nina icon in the toolbar to set default voice and speed, then click **▶ Read This Page**

The floating bar shows:
- ▶ / ⏸ Play/Pause
- « / » Back/Forward
- Voice picker (English voices from the browser's speech synthesis engine)
- Speed selector (0.75× – 2×)
- Chunk progress counter

### O'Reilly Learning support

The extension automatically detects O'Reilly Learning pages and waits for the JavaScript-rendered content to load before extracting text. If you see "NINA - Loading content..." for more than a few seconds, the page may not have loaded yet — wait for the chapter content to appear in the browser, then try activating Nina again.

---

## Bookmarklet

For browsers without extension support, copy `bookmarklet.txt` and save it as a bookmark URL. Click it on any page to inject the read-aloud toolbar.

**Install:** Copy the contents of `bookmarklet.txt`, create a new bookmark in your browser, paste it as the URL.

**Use:** Click the bookmark on any article page. Click it again to close the bar.

---

## Dependencies

| Package | Purpose |
|---------|---------|
| see `requirements.txt` | Neural speech synthesis + book format support |
| `mpv` | Audio playback & live equalizer/effect filtering |
| `ffmpeg` *(optional)* | Offline MP3 export (`nina -o`) with EQ & effect chains |
| `pypdf` | PDF text extraction |
| `ebooklib` | EPUB parsing |
| `beautifulsoup4` | HTML stripping inside EPUB files |

All Python dependencies (including book format support) are in `requirements.txt`:
```bash
pip install -r requirements.txt
```

---

## How it works

The CLI and GUI convert text to speech using a neural synthesis library and pipe the audio stream directly to `mpv` with dynamic audio filtergraphs — no API key, no account, no browser required.

The browser extension and bookmarklet use the Web Speech API built into Chromium browsers for in-page reading.
