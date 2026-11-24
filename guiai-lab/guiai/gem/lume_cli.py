"""Lume 1.0 — Interactive Zoe CLI with live Voice, 5-Band EQ, and Audio FX."""

from __future__ import annotations

import asyncio
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from typing import Any, TextIO

from .lume_header import (
    APP_NAME,
    APP_TAGLINE,
    EMBLEM_DESCRIPTIONS,
    EMBLEM_MAP,
    render_emblem_gallery,
    render_terminal_header,
)
from .zoe_app_brain import ALLOWED_DEEPMIND_MODELS, ZoeAppBrain, try_evaluate_math
from .zoe_artline_fonts import (
    format_font_catalog,
    format_wombats_table,
    render_artline_workspace_specimen,
    resolve_artline_font,
)
from .zoe_artline_neuro import export_artline_plate
from .zoe_atari_gem_rsc import export_atari_gem_bundle, format_iconblk_preview
from .zoe_braun_gem_renderer import render_braun_gem_portrait
from .zoe_cockpit import (
    COCKPIT_CHANNELS,
    LAUGH_QUIPS,
    format_onco_tma_table,
    get_channel,
    render_cockpit_frame,
)
from .zoe_med_council import (
    DEFAULT_COUNCIL_SEATS,
    OPUS_COUNCIL_SEATS,
    council_available,
    format_council_report,
    run_medical_council,
)
from .zoe_medical_mission import (
    format_biomech_report,
    format_c27_atlas_summary,
    format_neuromap_report,
    format_onco_screen_report,
    format_unified_mission_brief,
    run_biomech_inspection,
    run_neuroinflammatory_mni_map,
    screen_onco_compound,
)
from .zoe_neuro_atlas import lookup_neuroscience
from .zoe_zero_token import format_zero_token_report, try_symbolic_math


_RUBY = "\x1b[1;38;2;243;86;112m"
_ROSE = "\x1b[38;2;250;178;192m"
_AQUA = "\x1b[38;2;92;225;230m"
_DIM = "\x1b[38;2;148;156;196m"
_WHITE = "\x1b[38;2;232;234;246m"
_RESET = "\x1b[0m"

FALLBACK_EQ_BANDS: tuple[dict[str, Any], ...] = (
    {"key": "warmth", "freq": 120, "q": 1.0, "label": "Warmth", "hz_label": "120 Hz"},
    {"key": "body", "freq": 350, "q": 1.0, "label": "Body", "hz_label": "350 Hz"},
    {"key": "mid", "freq": 1200, "q": 1.0, "label": "Mid", "hz_label": "1.2 kHz"},
    {"key": "presence", "freq": 3200, "q": 1.1, "label": "Presence", "hz_label": "3.2 kHz"},
    {"key": "air", "freq": 9000, "q": 0.9, "label": "Air", "hz_label": "9 kHz"},
)

LUME_SLASH_COMMANDS: tuple[str, ...] = (
    "/help", "/hud", "/cockpit", "/ch", "/mission", "/artline", "/font", "/onco", "/biomech", "/neuromap",
    "/house", "/drawer", "/laugh",
    "/med", "/research", "/pubmed", "/arxiv", "/wiki", "/library",
    "/math", "/cache", "/brain", "/telemetry", "/emblem", "/memory",
    "/voice", "/eq", "/fx", "/pitch", "/rate", "/volume",
    "/profile", "/say", "/sing", "/autospeak", "/quiet", "/studio",
    "/clear", "/status", "/meta", "/search", "/plan", "/run", "/reflect",
    "/eliza", "/mind", "/gem", "/quit",
)

LAB_CHAT_COMMANDS = frozenset({
    "status", "plan", "run", "step", "reflect", "meta", "metacognition",
    "chiasm", "spectral", "genesis", "mars", "ares", "playroom", "play",
    "jam", "symphony", "mind", "think", "evolve", "self-evolve",
    "research", "l3", "l4", "self-improve", "l4-multi", "multimodule",
    "steward", "handover", "eliza", "zoe-eliza", "gem", "agent", "goal",
    "search", "import-pala", "save", "export", "verify", "undo", "history",
    "stop", "theorem13", "theorem14", "theorem15", "botanical", "optics",
    "proof-packet", "c28", "zoe-os", "os", "elegance", "thermo", "orbit",
    "speak", "sing", "voice", "help",
})


def locate_nina_root(zoe_root: Path | None = None) -> Path | None:
    """Locate the sibling Nina voice-studio checkout without hardcoded usernames."""
    candidates: list[Path] = []
    env_nina = os.environ.get("NINA_ROOT", "").strip()
    if env_nina:
        candidates.append(Path(env_nina).expanduser())
    if zoe_root is not None:
        candidates.append(zoe_root.resolve().parent / "nina")
    env_zoe = os.environ.get("ZOE_ROOT", "").strip()
    if env_zoe:
        candidates.append(Path(env_zoe).expanduser().resolve().parent / "nina")
    here = Path(__file__).resolve()
    for parent in here.parents[:5]:
        candidates.append(parent / "nina")
    candidates.append(Path.home() / "_projects" / "nina")
    for candidate in candidates:
        if (candidate / "audio_fx.py").is_file() and (candidate / "tts.py").is_file():
            return candidate.resolve()
    return None


def _load_module(name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_nina_backend(zoe_root: Path | None = None) -> dict[str, Any] | None:
    """Import Nina's audio_fx, tts, and ProfileStore when available."""
    nina_root = locate_nina_root(zoe_root)
    if nina_root is None:
        return None
    root_str = str(nina_root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    try:
        audio_fx = _load_module("nina_audio_fx", nina_root / "audio_fx.py")
        tts = _load_module("nina_tts", nina_root / "tts.py")
        store = audio_fx.ProfileStore(repo_path=nina_root / "voice_profiles.json")
        return {"root": nina_root, "audio_fx": audio_fx, "tts": tts, "store": store}
    except Exception:
        return None


def _style(text: str, ansi: str, color: bool) -> str:
    return f"{ansi}{text}{_RESET}" if color else text


def _eq_bar_segments(db: float, half_width: int, color: bool) -> tuple[str, str]:
    """Build left/right bipolar bar segments with sub-dB precision."""
    cells = int(round(abs(db) / 12.0 * half_width))
    if cells == 0 and abs(db) >= 0.25:
        cells = 1
    if db >= 0:
        left = _style("━" * half_width, _DIM, color)
        right = _style("█" * cells, _RUBY, color) + _style("━" * (half_width - cells), _DIM, color)
        return left, right
    left = _style("━" * (half_width - cells), _DIM, color) + _style("█" * cells, _AQUA, color)
    right = _style("━" * half_width, _DIM, color)
    return left, right


def render_eq_bars(
    eq: dict[str, float],
    bands: list[dict[str, Any]] | tuple[dict[str, Any], ...] = FALLBACK_EQ_BANDS,
    color: bool = True,
    half_width: int = 10,
) -> list[str]:
    """Render a centered bipolar 5-band terminal Equalizer graphic (-12..+12 dB)."""
    rows: list[str] = []
    for band in bands:
        db = max(-12.0, min(12.0, float(eq.get(band["key"], 0.0))))
        left, right = _eq_bar_segments(db, half_width, color)
        label = f"{band['label']:<8} {band['hz_label']:>7}"
        val = _style(f"{db:+5.1f} dB", _ROSE if db > 0 else (_AQUA if db < 0 else _DIM), color)
        rows.append(f"  {label}  [{left}│{right}]  {val}")
    return rows


class LumeVoiceController:
    """Manages active Lume 1.0 voice, 5-band EQ, audio effects, and async playback."""

    def __init__(self, zoe_root: Path | None = None):
        self.zoe_root = zoe_root
        self.backend = load_nina_backend(zoe_root)
        self.store = self.backend["store"] if self.backend else None
        self.bands = self.store.eq_bands if self.store else list(FALLBACK_EQ_BANDS)
        self.voice_id = self.store.preferred_voice_id if self.store else "ZoeNative-3D"
        self.profile = self._load_profile(self.voice_id)
        self.autospeak = False
        self._player: subprocess.Popen | None = None
        self._play_lock = threading.Lock()
        self._gen = 0

    def _load_profile(self, voice_id: str) -> dict[str, Any]:
        if self.store is None:
            return {
                "voice_id": voice_id,
                "display_name": "Zoe Native (App 3D)",
                "pitch": 0,
                "rate": 0,
                "volume": 0,
                "eq": {b["key"]: 0.0 for b in self.bands},
                "effect": "flat",
            }
        return self.store.get_voice_profile(voice_id)

    @property
    def display_name(self) -> str:
        return str(self.profile.get("display_name") or self.voice_id)

    def header_detail(self) -> str:
        fx = self.profile.get("effect", "flat")
        return f"Voice: {self.display_name} · FX: {fx} · 0 Cloud Tokens"

    def resolve_voice_id(self, query: str) -> str | None:
        if self.store is None:
            return "ZoeNative-3D" if query.lower() in {"zoe", "zoe-app", "zoenative-3d"} else None
        target = query.strip().lower()
        shortcuts = self.store.get_voice_shortcuts()
        if target in shortcuts:
            return shortcuts[target]
        for vid, cfg in self.store.list_female_profiles().items():
            if vid.lower() == target or str(cfg.get("display_name", "")).lower() == target:
                return vid
        for vid, cfg in self.store.list_female_profiles().items():
            if target in vid.lower() or target in str(cfg.get("display_name", "")).lower():
                return vid
        return None

    def set_voice(self, query: str) -> str:
        vid = self.resolve_voice_id(query)
        if not vid:
            raise ValueError(f"Unknown voice {query!r}. Run `/voice list` to see all voices.")
        self.voice_id = vid
        if self.store is not None:
            self.store.save_default_voice(vid)
        self.profile = self._load_profile(vid)
        return f"Voice set to {self.display_name} [{vid}] (saved as default)"

    def save_current_override(self) -> None:
        if self.store is not None:
            self.store.save_voice_override(self.voice_id, self.profile)

    def apply_eq(self, spec: str) -> str:
        if self.store is None:
            raise ValueError("Nina EQ backend is not installed next to Zoe.")
        raw = spec.strip()
        if raw.lower() == "reset":
            self.store.reset_voice_override(self.voice_id)
            self.profile = self._load_profile(self.voice_id)
            return f"Reset {self.display_name} EQ & tuning to Lume 1.0 calibrated defaults"
        curves = self.store.list_eq_curves()
        if raw.lower() in curves:
            curve = curves[raw.lower()]
            self.profile["eq"] = dict(curve["eq"])
            self.save_current_override()
            return f"Applied EQ curve '{curve.get('label', raw)}' to {self.display_name}"
        audio_fx = self.backend["audio_fx"]
        self.profile["eq"] = audio_fx.parse_eq_arg(raw, self.profile.get("eq"))
        self.save_current_override()
        return f"Updated 5-band EQ for {self.display_name}"

    def set_effect(self, key: str) -> str:
        if self.store is None:
            raise ValueError("Nina audio FX backend is not installed next to Zoe.")
        target = key.strip().lower()
        presets = self.store.list_effect_presets()
        if target not in presets:
            matches = [k for k, cfg in presets.items() if target in k.lower() or target in str(cfg.get("label", "")).lower()]
            if len(matches) == 1:
                target = matches[0]
            else:
                raise ValueError(f"Unknown effect {key!r}. Available: {', '.join(presets)}")
        self.profile["effect"] = target
        self.save_current_override()
        return f"Audio effect set to {presets[target].get('label', target)} [{target}]"

    def set_prosody(self, field: str, raw: str, lo: int, hi: int, unit: str) -> str:
        if self.backend is None:
            raise ValueError("Nina prosody controls require the local Nina backend.")
        val = int(self.backend["audio_fx"].parse_signed_int(raw, unit=unit))
        clamped = max(lo, min(hi, val))
        self.profile[field] = clamped
        self.save_current_override()
        return f"{field.capitalize()} set to {clamped:+d}{unit} for {self.display_name}"

    def load_or_save_recipe(self, argument: str) -> list[str]:
        if self.store is None:
            raise ValueError("Custom recipes require the local Nina backend.")
        arg = argument.strip()
        if not arg:
            customs = self.store.list_custom_profiles()
            if not customs:
                return ["No saved custom recipes yet. Save one with `/profile save <name>`."]
            return [f"  {name:<16} -> {cfg.get('voice_id')} ({cfg.get('effect')}) · {cfg.get('description', '')}" for name, cfg in customs.items()]
        if arg.lower().startswith("save "):
            name = arg[5:].strip()
            self.store.save_custom_profile(name, self.profile)
            return [f"Saved custom recipe '{name}' ({self.voice_id}, FX={self.profile.get('effect')})"]
        recipe = self.store.get_custom_profile(arg)
        if not recipe:
            raise ValueError(f"Unknown recipe {arg!r}. Run `/profile` to list saved recipes.")
        self.voice_id = recipe["voice_id"]
        self.profile = dict(recipe)
        self.profile["display_name"] = self._load_profile(self.voice_id).get("display_name") or self.voice_id
        self.store.save_default_voice(self.voice_id)
        self.save_current_override()
        return [f"Loaded recipe '{recipe['name']}' ({self.display_name}, FX={self.profile.get('effect')})"]

    def stop_audio(self) -> None:
        self._gen += 1
        with self._play_lock:
            proc = self._player
            self._player = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except OSError:
                pass

    def _play_bytes(self, audio_bytes: bytes, filtergraph: str, gen: int) -> None:
        if gen != self._gen:
            return
        cmd = self.backend["audio_fx"].mpv_args(filtergraph) if self.backend else ["mpv", "--no-video", "--really-quiet", "-"]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with self._play_lock:
            self._player = proc
        try:
            if proc.stdin:
                proc.stdin.write(audio_bytes)
                proc.stdin.close()
            proc.wait()
        finally:
            with self._play_lock:
                if self._player is proc:
                    self._player = None

    def _synthesize(self, phrase: str) -> bytes:
        if self.backend is None:
            from .zoe_voice import speak_text
            with tempfile.TemporaryDirectory() as tmp:
                out = Path(tmp) / "zoe.wav"
                speak_text(phrase, output_wav=out, mode="zoe_3d")
                return out.read_bytes()
        afx, tts = self.backend["audio_fx"], self.backend["tts"]
        comm = tts.Communicate(
            phrase,
            self.voice_id,
            rate=afx.format_rate(self.profile.get("rate", 0)),
            volume=afx.format_volume(self.profile.get("volume", 0)),
            pitch=afx.format_pitch(self.profile.get("pitch", 0)),
        )
        async def _collect() -> bytes:
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)
        return asyncio.run(_collect())

    def speak_async(self, phrase: str) -> str:
        clean = phrase.strip()
        if not clean:
            raise ValueError("Usage: /say <text>")
        self.stop_audio()
        gen = self._gen
        fg = self.backend["audio_fx"].build_filtergraph(self.profile.get("eq"), self.profile.get("effect", "flat"), self.store) if self.backend else ""

        def _run() -> None:
            try:
                audio = self._synthesize(clean)
                self._play_bytes(audio, fg, gen)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()
        return f"Speaking with {self.display_name} (FX: {self.profile.get('effect', 'flat')}) — type /quiet to stop"

    def sing_async(self, song: str = "zoe") -> str:
        target = (song or "zoe").strip()
        self.stop_audio()
        gen = self._gen
        fg = self.backend["audio_fx"].build_filtergraph(self.profile.get("eq"), self.profile.get("effect", "flat"), self.store) if self.backend else ""

        def _run() -> None:
            try:
                if self.backend and hasattr(self.backend["tts"], "synthesize_zoe_song_wav"):
                    audio = self.backend["tts"].synthesize_zoe_song_wav(target)
                else:
                    from .zoe_voice import sing_song
                    with tempfile.TemporaryDirectory() as tmp:
                        out = Path(tmp) / "song.wav"
                        sing_song(target, output_wav=out)
                        audio = out.read_bytes()
                if audio:
                    self._play_bytes(audio, fg, gen)
            except Exception:
                pass

        threading.Thread(target=_run, daemon=True).start()
        return f"Zoe is singing '{target}' through live EQ + {self.profile.get('effect', 'flat')} — type /quiet to stop"

    def open_studio(self) -> str:
        if not self.backend:
            raise ValueError("Nina Voice Studio was not found locally.")
        script = self.backend["root"] / "nina_gui.py"
        if not script.is_file():
            raise ValueError(f"Voice Studio launcher not found at {script}")
        subprocess.Popen(
            [sys.executable, str(script), "--studio"],
            cwd=str(self.backend["root"]),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return "Opened Nina Voice Studio & 5-Band Equalizer window"


class LumeCli:
    """Interactive Lume 1.0 terminal shell running the Zoe App Brain + Voice/EQ Studio."""

    def __init__(self, chat, zoe_root: Path, color: bool | None = None, brain_state: Path | None = None):
        self.chat = chat
        self.zoe_root = Path(zoe_root).resolve()
        self.brain = ZoeAppBrain(self.zoe_root, state_dir=brain_state)
        self.voice = LumeVoiceController(self.zoe_root)
        self.color = color
        self.show_telemetry = True
        self.emblem = "ruby"
        self.font_id = 51  # Digital Research Artline Font ID 51 (Avant Garde)
        self.channel = "1"
        self.last_a_tau = 2
        self.last_cands = 6
        self.signal_history: list[float] = [0.42, 0.58, 0.74, 0.82]
        self.last_note = ""
        self._laugh_idx = 0

    def _use_color(self, stream: TextIO) -> bool:
        if self.color is not None:
            return self.color
        if os.environ.get("NO_COLOR"):
            return False
        try:
            return bool(stream.isatty())
        except Exception:
            return False

    def _emit_tree(self, out: TextIO, lines: list[str], color: bool) -> None:
        branch = _style("  └ ", _DIM, color)
        for idx, line in enumerate(lines):
            prefix = branch if idx == 0 else "    "
            out.write(f"{prefix}{line}\n")
        out.flush()

    def _draw_banner(self, out: TextIO, color: bool) -> None:
        banner = render_terminal_header(
            title=APP_NAME,
            subtitle="",
            detail="",
            voice_line=None,
            color=color,
            emblem=self.emblem,
        )
        out.write(banner + "\n")
        out.flush()

    def _cmd_help(self) -> list[str]:
        return [
            "Zoe CLI — 1984 GEM Tactical Cockpit · 3-Pillar Milestone 1 Brain Cancer R&D · Voice & EQ:",
            "  /hud · /ch [1..6] · /mission       open GEM-84 HUD, switch tactical channel, or run 3-Pillar Brief",
            "  /artline [symmetry|glioma|neuromap|align|blend|trace|ring|icon|zoe]  Artline 2.0 vector plates",
            "  /os [status|build|verify]          UEFI x86_64 Zoe-GEM OS ISO builder & 2-boot OVMF+KVM verifier",
            "  /onco [atlas | screen <compound>]  Pillar 1: C17/C27 Atlas + live NIH PubChem/BBB/PAINS/PubMed screener",
            "  /biomech [sweep | <age_years>]     Pillar 2: 112k-vert MNI152 pediatric compliance cliffs & Th15 3-solver map",
            "  /neuromap [<marker_or_topic>]      Pillar 3: Frontostriatal/Neuroinflammatory MNI152 radar + PubMed + Library",
            "  /med [--council|--opus] <q>        0-token PubMed/Dorothy Atlas synthesis (or PubMed-grounded 3-Lab Council)",
            "  /research · /pubmed · /arxiv · /wiki · /library  query free 0-token research & 6,130-chapter local library",
            "  /math <expr> · /cache · /memory    SymPy exact symbolic math, offline paper cache, or SHA-256 memory chain",
            "  /house · /drawer [add <note>]      inspect Zoe's House architecture or open Nick's private SHA-256 Drawer",
            "  /laugh · /say <text> · /sing       Zoe's playful laugh, live 3D voice, and singing (/quiet stops)",
            "  /voice · /eq · /fx · /profile      tune Zoe x Natasha 3D voice, 5-band Equalizer, and 11 spatial effects",
            "  /brain [free|offline|lab]          switch brain mode (default: free · 0 tokens · $0.00)",
            "Zoe Lab Instruments: status, search, meta, plan, run, reflect, theorem13..15, botanical, optics, proof-packet, c28, gem",
        ]

    def _cmd_hud(self, color: bool, laughing: bool = False) -> list[str]:
        frame = render_cockpit_frame(
            self,
            channel=self.channel,
            last_a_tau=self.last_a_tau,
            last_cands=self.last_cands,
            signal_history=self.signal_history,
            last_note=self.last_note,
            laughing=laughing,
            color=color,
        )
        return ["__RAW__", *frame.splitlines()]

    def _cmd_ch(self, arg: str, color: bool) -> list[str]:
        raw = arg.strip()
        if not raw:
            rows = [f"Active Tactical Radio Channel: {get_channel(self.channel)['code']} ({get_channel(self.channel)['name']})"]
            for ch in COCKPIT_CHANNELS:
                mark = "▶" if ch["num"] == self.channel else " "
                rows.append(f"  {mark} [{ch['num']}] {ch['code']} {ch['name']:<11} {ch['freq']} · {ch['desc']}")
            rows.append("Switch with: /ch 1..6")
            return rows
        chosen = get_channel(raw)
        self.channel = chosen["num"]
        self.last_note = f"Switched radio to {chosen['code']} {chosen['name']} ({chosen['desc']})"
        return [f"Tactical Radio locked -> [{chosen['num']}] {chosen['code']} {chosen['name']} ({chosen['freq'].strip()}) · {chosen['desc']}"]

    def _cmd_onco(self, arg: str, color: bool) -> list[str]:
        raw = arg.strip()
        if raw.lower().startswith("screen "):
            target = raw[7:].strip()
            dossier = screen_onco_compound(
                target,
                self.brain.research_engine,
                allow_network=(self.brain.mode == "free"),
            )
            self.last_note = f"Screened {target} (CID={dossier['compound'].get('pubchem_cid') if dossier['compound'] else 'n/a'})"
            return format_onco_screen_report(dossier)
        if raw.lower() == "atlas":
            self.last_note = "C27 36-Compound Neuro-Oncology Atlas + FIPS-203 Filbin-2018"
            return format_c27_atlas_summary()
        self.last_note = f"Milestone 1 Neuro-Oncology C17 TMA table ({raw or 'all 11 NIH PubChem compounds'})"
        rows = format_onco_tma_table(query=raw, color=color)
        if not raw:
            rows.append("Tip: run `/onco atlas` for all 36 C27 compounds or `/onco screen <compound>` for live NIH PubChem + PAINS + PubMed")
        return rows

    def _cmd_biomech(self, arg: str) -> list[str]:
        raw = arg.strip().lower()
        age: float | None = None
        if raw and raw not in {"sweep", "cliffs", "all"}:
            try:
                age = float(raw.rstrip("y"))
            except ValueError as exc:
                raise ValueError("Usage: /biomech [sweep | <age_years>]  (e.g. /biomech 1.5)") from exc
        result = run_biomech_inspection(self.zoe_root, age_years=age)
        self.last_note = f"Dorothy MNI152 Neurobiomechanics ({result['mode']}, SymPy 3.25x={result['sympy_all_proved']})"
        return format_biomech_report(result)

    def _cmd_neuromap(self, arg: str) -> list[str]:
        mapping = run_neuroinflammatory_mni_map(
            arg.strip(),
            self.brain.research_engine,
            allow_network=(self.brain.mode == "free"),
        )
        top = mapping["nodes"][0]
        self.last_note = f"MNI152 Map: top={top['id']} {top['mni']} ({top['weight']:.1%})"
        return format_neuromap_report(mapping)

    def _cmd_mission(self) -> list[str]:
        lines = format_unified_mission_brief(
            self.zoe_root,
            self.brain.research_engine,
            allow_network=(self.brain.mode == "free"),
        )
        self.last_note = "Milestone 1 3-Pillar Command Brief executed (0 tokens)"
        return lines

    def _cmd_artline(self, arg: str) -> list[str]:
        raw = arg.strip()
        if not raw:
            return [
                "Zoe Artline — Digital Research Artline 2.0 Deterministic Geometry & Symmetry Engine (0 tokens, 0 GPU)",
                "  /artline symmetry [age_yr edema_ml]   MNI152 bilateral hemisphere symmetry & midline-shift blueprint",
                "  /artline glioma [<compound>]          H3K27M / GBM NIH PubChem C27 Wager CNS MPO-4 symmetry radar",
                "  /artline neuromap [<marker>]          9-node frontostriatal & pontine MNI152 sagittal vector plate",
                "  /artline align                        Artline 2.0 Plane Tool (Align Vert / Align Horiz) re-grounding plate",
                "  /artline blend [f10]                  Artline 2.0 Point-Mapped 'Z -> O -> E' Blend (+ F10 wireframe mode)",
                "  /artline trace [f9|<image_path>]      Artline 2.0 Autotrace + Trace Segment (p. 11-11) + F9 image toggle",
                "  /artline ring [n]                     Artline Tutorial p. 6-14 Rotator+Thumbtack radial symmetry emblem",
                "  /artline icon [<emblem>]              Artline pp. 13-12 Icon Editor (Atari ST 32x32) + ALIGN.TLS 9-way pad",
                "  /artline zoe                          Digital Research Artline 2.0 Zoe Ruby bilateral symmetry study",
                "Exports compact, repeatable .svg, .png, and Digital Research GEM VDI .gem metafiles to ~/.zoe/artline/",
            ]
        head, _sep, rest = raw.partition(" ")
        res = export_artline_plate(head, self.zoe_root, arg=rest.strip())
        self.last_note = f"Artline '{res['plate']}' exported ({res['elements']} vectors · SHA:{res['events_hash']})"
        lines = [
            f"Zoe Artline · Digital Research GEM Vector Plate '{res['plate']}' (0 tokens · {res['elements']} elements · SHA:{res['events_hash']})",
            f"  SVG : {res['paths']['svg']} ({res['sizes_bytes']['svg']:,} bytes)",
            f"  PNG : {res['paths']['png']} ({res['sizes_bytes']['png']:,} bytes)",
            f"  GEM : {res['paths']['gem']} ({res['sizes_bytes']['gem']:,} bytes · verified GEM VDI metafile)",
        ]
        if res["plate"] == "symmetry":
            m = res["meta"]
            lines.append(
                f"  Symmetry Metrics: age={m['age_years']:g}y · edema={m['edema_ml']:.1f}mL · "
                f"midline_shift={m['midline_shift_mm']:.2f}mm · BSI={m['bilateral_symmetry_index']:.4f} · "
                f"ICP={m['icp_mmhg']} mmHg · Th15 C_K={m['th15_consensus_ck']:.3f}"
            )
        lines.append("clinical_action_authorized=False · cure_claim=False · sentience_claimed=False")
        return lines

    def _cmd_os(self, arg: str) -> list[str]:
        from .zoe_gem_os import (
            build_zoe_gem_os_iso,
            format_usb_stage2_guide,
            launch_zoe_gem_os_kvm,
            verify_zoe_gem_os_qemu,
        )

        tokens = arg.strip().lower().split()
        sub = tokens[0] if tokens else "status"
        flavor = "lts" if len(tokens) > 1 and tokens[1] == "lts" else "virt"
        iso_dir = Path.home() / ".zoe" / "os-build"
        virt_iso = iso_dir / "zoe-gem-os.iso"
        lts_iso = iso_dir / "zoe-gem-os-lts.iso"
        if sub == "status":
            v_sz = f"{virt_iso.stat().st_size / 1048576:.1f} MB" if virt_iso.is_file() else "not built"
            l_sz = f"{lts_iso.stat().st_size / 1048576:.1f} MB" if lts_iso.is_file() else "not built"
            return [
                "Zoe-GEM OS v1.0 — Bootable UEFI x86_64 Linux-HAL + Interactive /dev/fb0 GEM Desktop",
                f"  KVM ISO  : {virt_iso} ({v_sz})",
                f"  LTS ISO  : {lts_iso} ({l_sz} · Intel Tiger Lake i915 + VMD + AX201 Wi-Fi)",
                "  Commands : /os build [virt|lts] | /os verify | /os launch [virt|lts] | /os usb",
                "  Safety   : Never wipes host drives or flashes motherboard UEFI; boots safely in KVM or live USB.",
            ]
        if sub == "build":
            res = build_zoe_gem_os_iso(iso_dir, self.zoe_root, kernel_flavor=flavor, autotest_default=False)
            self.last_note = f"Zoe-GEM OS ({flavor}) built ({res['iso_bytes'] // 1048576} MB · SHA:{res['iso_sha256'][:12]})"
            return [
                f"Zoe-GEM OS UEFI x86_64 ISO ({flavor.upper()}) built ({res['iso_bytes']:,} bytes · kernel {res['kernel_version']})",
                f"  ISO    : {res['iso_path']}",
                f"  SHA256 : {res['iso_sha256'][:24]} · mouse+kbd=True · wifi={res['wifi_bundled']} · 0 tokens",
            ]
        if sub == "verify":
            proof_dir = iso_dir / "verify_proof"
            b = build_zoe_gem_os_iso(proof_dir, self.zoe_root, kernel_flavor=flavor, autotest_default=True)
            v = verify_zoe_gem_os_qemu(b["iso_path"], proof_dir / "qemu")
            self.last_note = f"Zoe-GEM OS 2-boot KVM proof ok={v['ok']}"
            return [
                f"Zoe-GEM OS 2-Boot OVMF UEFI + KVM Verification: {'PASS' if v['ok'] else 'FAIL'}",
                f"  FB0={v['hardware_framebuffer_verified']} · DHCP={v['hardware_networking_verified']} · Self-Retention={v['self_retention_verified']} · LiveCanvasSaved={v['interactive_canvas_saved']}",
                f"  Boot #1 ({v['boot_1']['elapsed_sec']}s) : {' | '.join(v['boot_1']['serial_tail'][-3:])}",
                f"  Boot #2 ({v['boot_2']['elapsed_sec']}s) : {' | '.join(v['boot_2']['serial_tail'][-3:])}",
            ]
        if sub == "launch":
            target = lts_iso if flavor == "lts" else virt_iso
            res = launch_zoe_gem_os_kvm(target, iso_dir / "zoe-state.img")
            self.last_note = f"Launched Zoe-GEM OS KVM GUI (PID {res['pid']})"
            return [
                f"Launched Zoe-GEM OS interactively in KVM window (PID {res['pid']})",
                f"  ISO   : {res['iso']}",
                f"  State : {res['state_img']} (persists Nick's Drawer + Artline SVG across reboots!)",
                "  Tips  : Click 0-7 toolkit colors · Drag on Artline canvas · [M] Mirror · [S] Save · [D] Drawer · [T] Shell",
            ]
        if sub in {"usb", "usb-guide"}:
            return format_usb_stage2_guide(lts_iso if lts_iso.is_file() else virt_iso)
        raise ValueError("Usage: /os [status | build [virt|lts] | verify | launch [virt|lts] | usb]")

    def _cmd_font(self, arg: str) -> list[str]:
        raw = arg.strip()
        low = raw.lower()
        if not raw or low == "list":
            return format_font_catalog(active_font_id=self.font_id)
        if low in {"wombat", "wombats", "symbol", "symbols"}:
            return format_wombats_table()
        if low == "specimen":
            out_png = Path.home() / ".zoe" / "artline" / f"artline_specimen_id{self.font_id}.png"
            res = render_artline_workspace_specimen(out_png, active_font_id=self.font_id)
            return [
                f"Rendered Digital Research Artline 2.0 Font Specimen ({res['fonts_rendered']} fonts · Active ID {res['active_font_id']}: {res['active_font_name']})",
                f"  PNG : {res['output_path']} (0 tokens · Workspace + Surround + Drawing Surface)",
            ]
        spec = resolve_artline_font(raw)
        self.font_id = spec.font_id
        self.last_note = f"Artline Font set -> ID {spec.font_id} ({spec.name})"
        return [
            f"Active Zoe Artline Font set to ID {spec.font_id}: {spec.name} ({spec.category})",
            f"Sample: {spec.sample}",
            "Render a full Artline specimen sheet with `/font specimen` or updated 3D portrait with `/emblem 3d`.",
        ]

    def _cmd_house(self) -> list[str]:
        lib_docs = int(self.brain.dorothy_library.status().get("total_fts_docs", 0))
        cached = self.brain.research_engine.cache.count()
        drawer_items = self.brain.memory.query_facts(subject="nick_drawer", active_only=True)
        head = str(self.brain.memory.snapshot().get("chain_head", "GENESIS"))[:12]
        return [
            f"Zoe's House · Front Door Signet: {self.emblem} (ruby default · 9 GEM signets · Atari ST .RSC)",
            "  [Cockpit ]  /hud · /ch 1..6          1984 Gary Kildall GEM × Avionics × Submarine TMA × Radio",
            "  [Lab 1   ]  /onco [atlas|screen]     H3K27M DMG / GBM PubChem + Wager BBB + PAINS + FIPS-203",
            "  [Lab 2   ]  /biomech [age]           112k-vert MNI152 Pediatric Compliance Cliffs & Th15 3-Solver",
            "  [Lab 3   ]  /neuromap [marker]       9-node Frontostriatal & Midline MNI152 Radar + PubMed",
            "  [Drafting]  /artline [plate]         Digital Research Artline 2.0 repeatable .svg / .png / .gem",
            f"  [Library ]  /library · /med · /cache {lib_docs} local chapters · {cached} cached papers · 0 tokens",
            "  [Studio  ]  /voice · /eq · /fx       Zoe x Natasha 3D Voice, 5-Band EQ, 11 FX, /laugh",
            f"  [Drawer  ]  /drawer                  Nick's Private Drawer ({len(drawer_items)} items · SHA-256:{head})",
            "Stewardship: human_steward=Nicholas Michael Kloster · sentience_claimed=False · clinical_action_authorized=False",
        ]

    def _cmd_drawer(self, arg: str) -> list[str]:
        raw = arg.strip()
        if raw.lower().startswith("add "):
            note = raw[4:].strip()
            if not note:
                raise ValueError("Usage: /drawer add <note or research keepsake>")
            fact = self.brain._store_note("nick_drawer", "drawer", note, "nicholas_private_drawer")
            return [
                f"Tucked into Nick's Drawer (SHA-256:{str(fact.get('sha256', ''))[:12]}): \"{note}\"",
                "Stored privately on this machine in ZoeUnifiedMemory (never uploaded without your explicit command).",
            ]
        items = self.brain.memory.query_facts(subject="nick_drawer", active_only=True)
        head = str(self.brain.memory.snapshot().get("chain_head", "GENESIS"))[:12]
        rows = [f"Nick's Private Drawer ({len(items)} items · SHA-256 chain {head} · 100% local):"]
        if not items:
            rows.append("  (empty right now — tuck a note, idea, or keepsake in with `/drawer add <note>`)")
        else:
            for idx, item in enumerate(items[-10:][::-1], start=1):
                rows.append(f"  {idx:02d}. {item['object']}")
        rows.append("Add anytime with: /drawer add <note>  (stays private on disk)")
        return rows

    def _cmd_laugh(self, color: bool) -> list[str]:
        quip = LAUGH_QUIPS[self._laugh_idx % len(LAUGH_QUIPS)]
        self._laugh_idx += 1
        self.last_note = quip
        spoken_note = ""
        try:
            spoken_note = self.voice.speak_async(quip)
        except Exception:
            spoken_note = "(audio device unavailable; text laugh shown)"
        return [
            f"Zoe (^◡^): {quip}",
            spoken_note,
        ]

    def _cmd_med(self, arg: str) -> list[str]:
        raw = arg.strip()
        if not raw:
            lib = self.brain.dorothy_library.status()
            docs = int(lib.get("total_fts_docs", 0))
            cached = self.brain.research_engine.cache.count()
            seats = " · ".join(f"{lab} ({model})" for lab, model in DEFAULT_COUNCIL_SEATS)
            council_note = f"ready ({seats})" if council_available() else "offline (agy CLI not found)"
            return [
                "Zoe Medical Research Engine: ready ($0.00 default · 0-token PubMed/Europe PMC + Dorothy Atlas)",
                f"Local Sources: Dorothy 3D Atlas · Local Library ({docs} chapters) · Offline Cache ({cached})",
                f"3-Lab Council (--council / --opus, 0 API keys): {council_note}",
                "Usage: /med <question>  |  /med --council <question>  |  /med --opus <question>",
                "clinical_action_authorized=False · cure_claim=False · sentience_claimed=False",
            ]
        use_council = False
        use_opus = False
        query = raw
        if raw.lower().startswith("--opus "):
            use_council = True
            use_opus = True
            query = raw[7:].strip()
        elif raw.lower().startswith("--council "):
            use_council = True
            query = raw[10:].strip()

        allow_net = self.brain.mode == "free"
        neuro = lookup_neuroscience(query)
        report = self.brain.research_engine.research(
            query,
            sources=("local", "pubmed", "wikipedia"),
            allow_network=allow_net,
            medical_focus=True,
        )
        if not use_council:
            lines = format_zero_token_report(report, heading="Zoe Zero-Token Medical Research")
            if neuro is not None:
                lines.insert(1, f"Dorothy Neuro-Atlas anchor: {neuro.title}")
            return lines

        grounded_lines = [f"- [{h.source}] {h.title} ({h.citation}): {h.snippet[:160]}" for h in report.hits[:4]]
        council_report = run_medical_council(
            query,
            neuro_context=neuro.reply if neuro else "",
            neuro_title=neuro.title if neuro else "",
            library_context="\n".join(grounded_lines),
            use_opus=use_opus,
        )
        return format_council_report(council_report)

    def _cmd_research(self, arg: str, sources: tuple[str, ...] = ("local", "pubmed", "wikipedia", "arxiv"), label: str = "Zoe Zero-Token Research") -> list[str]:
        raw = arg.strip()
        if not raw:
            return [f"Usage: /research <topic>  (0 tokens · sources: {', '.join(sources)})"]
        allow_net = self.brain.mode == "free"
        report = self.brain.research_engine.research(raw, sources=sources, allow_network=allow_net)
        return format_zero_token_report(report, heading=label)

    def _cmd_library(self, arg: str) -> list[str]:
        raw = arg.strip()
        if not raw:
            st = self.brain.dorothy_library.status()
            return [
                f"Local Dorothy Brain Library: {'ready' if st.get('available') else 'not indexed'} (0 tokens, 100% private)",
                f"Indexed: {st.get('books_indexed', 0)} books · {st.get('chapters_indexed', 0)} chapters · {st.get('nirmt_pdfs_indexed', 0)} PDFs · {st.get('total_fts_docs', 0)} FTS5 docs",
                "Usage: /library <topic or keyword>",
            ]
        hits = self.brain.research_engine.search_local_library(raw, limit=5, min_overlap=0.34)
        if not hits:
            return [f"No strong matches in the local Dorothy Brain Library for {raw!r}."]
        rows = [f"Local Dorothy Brain Library matches for '{raw}' (0 tokens):"]
        for hit in hits:
            rows.append(f"  • {hit.title}")
            if hit.snippet:
                rows.append(f"    {hit.snippet[:220]}")
        return rows

    def _cmd_math(self, arg: str) -> list[str]:
        raw = arg.strip()
        if not raw:
            return ["Usage: /math <expr>  (e.g. `/math solve x^2 - 5x + 6 = 0`, `/math diff x^3 * sin(x)`, `/math integrate x^2`)"]
        ans = try_symbolic_math(raw) or try_evaluate_math(raw)
        if ans:
            return [ans, "tokens_used=0 ($0.00 · exact local symbolic/arithmetic engine)"]
        return [f"Could not parse symbolic/math expression: {raw!r}"]

    def _cmd_cache(self, arg: str) -> list[str]:
        raw = arg.strip()
        count = self.brain.research_engine.cache.count()
        if not raw:
            return [
                f"Zoe Zero-Token Offline Knowledge Cache: {count} verified papers & summaries saved locally",
                f"Store: {self.brain.research_engine.cache.db_path.name} (SQLite FTS5 · 0 tokens)",
                "Search offline cache with: /cache <topic>",
            ]
        hits = self.brain.research_engine.cache.search(raw, limit=5)
        if not hits:
            return [f"No cached entries matched {raw!r} yet (cache size: {count}). Run `/med` or `/research` to learn & cache it."]
        rows = [f"Offline Cache hits for '{raw}' ({len(hits)} shown · 0 tokens):"]
        for hit in hits:
            rows.append(f"  • {hit.title} ({hit.citation})")
            rows.append(f"    {hit.snippet[:200]}")
        return rows

    def _cmd_brain(self, arg: str) -> list[str]:
        valid = ("free", "offline", "stem", "lab")
        low = arg.strip().lower()
        if not low:
            lib = self.brain.dorothy_library.status()
            cached = self.brain.research_engine.cache.count()
            return [
                f"Active brain mode: {self.brain.mode}  (choices: free, offline, lab)",
                "Cost & Tokens: $0.00 forever · 0 cloud tokens · 0 LLM tokens",
                f"Local Knowledge: {len(self.brain.research_engine.encyclopedia.records)} Dorothy Atlas records · {lib.get('total_fts_docs', 0)} library chapters · {cached} cached papers",
                "Switch with: /brain free | /brain offline | /brain lab",
            ]
        if low not in valid:
            raise ValueError(f"Unknown brain mode {arg!r}. Choose one of: free, offline, lab")
        self.brain.mode = low
        return [f"Zoe brain mode set to '{low}' (0 tokens ever)"]

    def _cmd_model(self, arg: str) -> list[str]:
        raw = arg.strip()
        if not raw:
            probe = self.brain.deepmind.probe()
            return [
                f"Google DeepMind fallback model: {self.brain.deepmind.model} (backend: {probe['backend']})",
                f"Models: {', '.join(ALLOWED_DEEPMIND_MODELS)}",
            ]
        return [self.brain.deepmind.set_model(raw)]

    def _cmd_telemetry(self, arg: str) -> list[str]:
        low = arg.strip().lower()
        if low in {"on", "1", "true"}:
            self.show_telemetry = True
        elif low in {"off", "0", "false"}:
            self.show_telemetry = False
        else:
            self.show_telemetry = not self.show_telemetry
        return [f"Kloster A_tau(p) telemetry badge is now {'ON' if self.show_telemetry else 'OFF'}"]

    def _cmd_emblem(self, arg: str, color: bool = True) -> list[str]:
        low = arg.strip().lower()
        if not low:
            return [
                f"Active Zoe GEM signet: {self.emblem} ({EMBLEM_DESCRIPTIONS.get(self.emblem, '')})",
                f"Variants: {', '.join(EMBLEM_MAP)}  (try `/emblem gallery` or `/emblem rsc [export]`)",
            ]
        if low in {"gallery", "list", "all"}:
            return ["__RAW__", *render_emblem_gallery(color=color)]
        if low == "3d" or low.startswith("3d "):
            out_png = Path.home() / ".zoe" / "atari-gem" / "zoe_braun_gem_portrait.png"
            stats = render_braun_gem_portrait(out_png, font_id=self.font_id)
            return [
                f"Rendered Zoe's 1986 Uwe Braun 3D × SYBEX GEM Portrait (Font ID {self.font_id} · 0 AI tokens)",
                f"  Output : {stats['output_path']} ({stats['width']}x{stats['height']})",
                f"  Math   : Rx={stats['rx_deg']:+.0f}° Ry={stats['ry_deg']:+.0f}° · {stats['visible_faces']}/{stats['total_faces']} faces (Z-culled) · 16-pattern GEM dither",
            ]
        if low == "rsc" or low.startswith("rsc "):
            sub = low[3:].strip()
            if sub == "export":
                res = export_atari_gem_bundle()
                return [
                    f"Exported Atari ST / EmuTOS GEM Resource Bundle ({res['icons_compiled']} 32x32 ICONBLKs · {res['rsc_bytes']} bytes)",
                    f"  RSC    : {res['rsc_path']}",
                    f"  C Hdr  : {res['header_path']}",
                    f"  SHA256 : {res['sha256'][:24]} · RSHDR verified={res['ok']}",
                ]
            target = sub if sub in EMBLEM_MAP else self.emblem
            return ["__RAW__", *format_iconblk_preview(target)]
        if low not in EMBLEM_MAP:
            raise ValueError(f"Unknown emblem {arg!r}. Choose: {', '.join(EMBLEM_MAP)}, 'gallery', or 'rsc'")
        self.emblem = low
        self.last_note = f"Switched Zoe GEM signet -> {low} ({EMBLEM_DESCRIPTIONS.get(low, '')})"
        return ["__CLEAR__"]

    def _cmd_memory(self) -> list[str]:
        snap = self.brain.memory.snapshot()
        notes = self.brain.memory.query_facts(subject="user_note", active_only=True)
        relays = self.brain.memory.query_facts(subject="lab_relay_for_zoe", active_only=True)
        head = str(snap.get("chain_head", "GENESIS"))[:14]
        rows = [f"ZoeUnifiedMemory (chain {head} · notes={len(notes)} · relays={len(relays)})"]
        for item in (notes + relays)[-6:][::-1]:
            rows.append(f"  • [{item.get('subject')}] {item['object']}")
        if not (notes or relays):
            rows.append("  No notes yet. Type `remember <note>` or `relay <note>`.")
        return rows

    def _cmd_voice(self, arg: str, color: bool) -> list[str]:
        sub = arg.strip()
        if not sub:
            p = self.voice.profile
            eq = p.get("eq", {})
            eq_txt = "  ".join(f"{b['label']} {float(eq.get(b['key'], 0.0)):+.1f}" for b in self.voice.bands)
            return [
                f"Voice: {_style(self.voice.display_name, _RUBY, color)} [{self.voice.voice_id}]",
                f"Prosody: pitch {int(p.get('pitch', 0)):+d}Hz · rate {int(p.get('rate', 0)):+d}% · volume {int(p.get('volume', 0)):+d}% · FX: {p.get('effect', 'flat')}",
                f"EQ (dB): {eq_txt}",
                f"Auto-speak: {'on' if self.voice.autospeak else 'off'}  (try `/voice list`, `/voice <name>`, or `/eq`)",
            ]
        low = sub.lower()
        if low == "list":
            if self.voice.store is None:
                return ["★ ZoeNative-3D  Zoe Native (App 3D)"]
            rows = [f"Calibrated Lume 1.0 Voices ({len(self.voice.store.list_female_profiles())} total):"]
            for vid, cfg in self.voice.store.list_female_profiles().items():
                mark = _style("★", _RUBY, color) if vid == self.voice.voice_id else " "
                sc = f"[{cfg.get('shortcut')}]" if cfg.get("shortcut") else ""
                rows.append(f"{mark} {str(cfg.get('display_name', vid)):<26} {sc:<12} {cfg.get('tagline', '')}")
            return rows
        if low == "native":
            return self.chat.handle("voice")[1].splitlines()
        if low == "reset":
            return [self.voice.apply_eq("reset")]
        if low == "studio":
            return [self.voice.open_studio()]
        return [self.voice.set_voice(sub)]

    def _cmd_eq(self, arg: str, color: bool) -> list[str]:
        lines: list[str] = []
        if arg.strip():
            lines.append(self.voice.apply_eq(arg))
        else:
            lines.append(f"Lume 1.0 · 5-Band Equalizer ({self.voice.display_name})")
        lines.extend(render_eq_bars(self.voice.profile.get("eq", {}), self.voice.bands, color=color))
        if self.voice.store is not None:
            curves = ", ".join(self.voice.store.list_eq_curves().keys())
            lines.append(f"Curves: {curves}")
        lines.append("Edit: /eq <curve>  |  /eq warmth=2,air=3.5  |  /eq 1.5,-0.5,0,1.5,2.0  |  /eq reset")
        return lines

    def _cmd_fx(self, arg: str, color: bool) -> list[str]:
        if arg.strip():
            return [self.voice.set_effect(arg)]
        if self.voice.store is None:
            return ["Audio effect: flat (local Nina backend not detected)"]
        active = self.voice.profile.get("effect", "flat")
        rows = ["Lume 1.0 · Creative Audio Effects:"]
        for key, cfg in self.voice.store.list_effect_presets().items():
            mark = _style("★", _RUBY, color) if key == active else " "
            rows.append(f"{mark} {key:<20} {cfg.get('label', key):<22} {cfg.get('description', '')}")
        rows.append("Apply with: /fx <effect_key>")
        return rows

    def _cmd_autospeak(self, arg: str) -> list[str]:
        low = arg.strip().lower()
        if low in {"on", "1", "true", "yes"}:
            self.voice.autospeak = True
        elif low in {"off", "0", "false", "no"}:
            self.voice.autospeak = False
            self.voice.stop_audio()
        else:
            self.voice.autospeak = not self.voice.autospeak
        return [f"Auto-speak is now {'ON' if self.voice.autospeak else 'OFF'} ({self.voice.display_name})"]

    def handle_slash(self, line: str, color: bool = True) -> tuple[bool, list[str] | None]:
        """Handle Lume 1.0 /slash commands; returns (keep_going, lines or None to delegate)."""
        stripped = line.strip()
        if not stripped.startswith("/"):
            return True, None
        cmd, _sep, arg = stripped[1:].partition(" ")
        cmd = cmd.lower()
        arg = arg.strip()
        if cmd in {"quit", "exit"}:
            self.voice.stop_audio()
            self.chat.store.save()
            return False, ["State saved. Goodbye."]
        handlers = {
            "help": lambda: self._cmd_help(),
            "hud": lambda: self._cmd_hud(color),
            "cockpit": lambda: self._cmd_hud(color),
            "gem84": lambda: self._cmd_hud(color),
            "ch": lambda: self._cmd_ch(arg, color),
            "mission": lambda: self._cmd_mission(),
            "artline": lambda: self._cmd_artline(arg),
            "os": lambda: self._cmd_os(arg),
            "font": lambda: self._cmd_font(arg),
            "onco": lambda: self._cmd_onco(arg, color),
            "biomech": lambda: self._cmd_biomech(arg),
            "neuromap": lambda: self._cmd_neuromap(arg),
            "house": lambda: self._cmd_house(),
            "drawer": lambda: self._cmd_drawer(arg),
            "laugh": lambda: self._cmd_laugh(color),
            "med": lambda: self._cmd_med(arg),
            "research": lambda: self._cmd_research(arg),
            "pubmed": lambda: self._cmd_research(arg, sources=("pubmed",), label="Zoe Zero-Token PubMed / Europe PMC"),
            "arxiv": lambda: self._cmd_research(arg, sources=("arxiv",), label="Zoe Zero-Token arXiv"),
            "wiki": lambda: self._cmd_research(arg, sources=("wikipedia",), label="Zoe Zero-Token Wikipedia"),
            "library": lambda: self._cmd_library(arg),
            "math": lambda: self._cmd_math(arg),
            "cache": lambda: self._cmd_cache(arg),
            "brain": lambda: self._cmd_brain(arg),
            "model": lambda: self._cmd_model(arg),
            "telemetry": lambda: self._cmd_telemetry(arg),
            "emblem": lambda: self._cmd_emblem(arg, color),
            "memory": lambda: self._cmd_memory(),
            "voice": lambda: self._cmd_voice(arg, color),
            "eq": lambda: self._cmd_eq(arg, color),
            "fx": lambda: self._cmd_fx(arg, color),
            "pitch": lambda: [self.voice.set_prosody("pitch", arg, -24, 24, "Hz")],
            "rate": lambda: [self.voice.set_prosody("rate", arg, -40, 60, "%")],
            "volume": lambda: [self.voice.set_prosody("volume", arg, -20, 20, "%")],
            "profile": lambda: self.voice.load_or_save_recipe(arg),
            "say": lambda: [self.voice.speak_async(arg)],
            "play": lambda: [self.voice.speak_async(arg)],
            "sing": lambda: [self.voice.sing_async(arg or "zoe")],
            "autospeak": lambda: self._cmd_autospeak(arg),
            "quiet": lambda: (self.voice.stop_audio(), ["Audio playback stopped."])[1],
            "mute": lambda: (self.voice.stop_audio(), ["Audio playback stopped."])[1],
            "studio": lambda: [self.voice.open_studio()],
            "clear": lambda: ["__CLEAR__"],
        }
        handler = handlers.get(cmd)
        if handler is None:
            return True, None
        try:
            return True, handler()
        except (OSError, RuntimeError, ValueError) as exc:
            return True, [f"{exc}"]

    def _configure_readline(self) -> None:
        try:
            import readline
        except ImportError:
            return
        candidates = list(LUME_SLASH_COMMANDS)
        if self.voice.store is not None:
            candidates.extend(f"/voice {sc}" for sc in self.voice.store.get_voice_shortcuts())
            candidates.extend(f"/eq {k}" for k in self.voice.store.list_eq_curves())
            candidates.extend(f"/fx {k}" for k in self.voice.store.list_effect_presets())

        def _complete(text: str, state: int) -> str | None:
            buf = readline.get_line_buffer().lstrip()
            matches = [item for item in candidates if item.startswith(buf)]
            if state >= len(matches):
                return None
            match = matches[state]
            return match[len(buf) - len(text):] if buf.startswith(text) or text else match

        readline.set_completer_delims(" \t\n")
        readline.set_completer(_complete)
        readline.parse_and_bind("tab: complete")

    def _read_next_line(self, in_stream: TextIO, out_stream: TextIO, prompt: str, interactive: bool) -> str | None:
        """Read one line from stdin or a custom stream, handling Ctrl+C and EOF cleanly."""
        try:
            if interactive and in_stream is sys.stdin and out_stream is sys.stdout:
                return input(prompt)
            if interactive:
                out_stream.write(prompt)
                out_stream.flush()
            raw = in_stream.readline()
            return raw if raw else None
        except KeyboardInterrupt:
            self.voice.stop_audio()
            out_stream.write("\n")
            out_stream.flush()
            return ""
        except EOFError:
            return None

    def _emit_reply(self, out_stream: TextIO, response: str, use_color: bool) -> None:
        if use_color:
            out_stream.write(f"{_ROSE}Zoe{_RESET}{_DIM}:{_RESET} {response}\n")
        else:
            out_stream.write(f"Zoe: {response}\n")
        out_stream.flush()

    def _is_lab_command(self, line: str) -> bool:
        head = line.strip().partition(" ")[0].lower().lstrip("/")
        return head in LAB_CHAT_COMMANDS

    def _respond_turn(self, line: str, out_stream: TextIO, use_color: bool) -> bool:
        stripped = line.strip()
        if stripped.lower() in {"quit", "exit"}:
            self._emit_tree(out_stream, ["State saved. Goodbye."], use_color)
            return False
        if self.brain.mode == "lab" or self._is_lab_command(stripped):
            keep_going, response = self.chat.handle(stripped)
            self._emit_reply(out_stream, response, use_color)
            if self.voice.autospeak and keep_going:
                self.voice.speak_async(response[:420])
            return keep_going
        res = self.brain.respond(stripped)
        self.last_a_tau = res.a_tau
        self.last_cands = max(1, res.candidate_count)
        self.signal_history.append(max(0.15, min(0.98, 1.0 - (res.a_tau / max(1, res.candidate_count)) * 0.65)))
        self.signal_history = self.signal_history[-12:]
        self.last_note = res.reply[:110]
        self._emit_reply(out_stream, res.reply, use_color)
        if self.show_telemetry:
            self._emit_tree(out_stream, [_style(res.telemetry_badge, _DIM, use_color)], use_color)
        if self.voice.autospeak:
            self.voice.speak_async(res.reply[:420])
        return True

    def run(self, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
        """Run the interactive Lume 1.0 CLI loop (in-memory history only, zero disk transcript)."""
        in_stream = input_stream or sys.stdin
        out_stream = output_stream or sys.stdout
        interactive = bool(getattr(in_stream, "isatty", lambda: False)())
        use_color = self._use_color(out_stream)
        if interactive:
            self._configure_readline()
            self._draw_banner(out_stream, use_color)
        prompt = (
            f"\x01{_RUBY}\x02Zoe\x01{_RESET}\x02 \x01{_ROSE}\x02◠◡◠\x01{_RESET}\x02 \x01{_RUBY}\x02❯\x01{_RESET}\x02 "
            if (interactive and use_color)
            else "Zoe ◠◡◠ ❯ "
        )

        while True:
            line = self._read_next_line(in_stream, out_stream, prompt, interactive)
            if line is None:
                break
            if not line.strip():
                continue
            keep_going, slash_lines = self.handle_slash(line, color=use_color)
            if slash_lines is not None:
                if slash_lines == ["__CLEAR__"]:
                    if use_color:
                        out_stream.write("\x1b[2J\x1b[H")
                    self._draw_banner(out_stream, use_color)
                elif slash_lines and slash_lines[0] == "__RAW__":
                    out_stream.write("\n".join(slash_lines[1:]) + "\n")
                    out_stream.flush()
                else:
                    self._emit_tree(out_stream, slash_lines, use_color)
                if not keep_going:
                    break
                continue
            if not self._respond_turn(line, out_stream, use_color):
                break

        self.voice.stop_audio()
        self.chat.store.save()
        return 0


def run_lume_cli(zoe_root: str | Path, state: str | Path, input_stream=None, output_stream=None) -> int:
    """Instantiate ZoeChat and launch the Lume 1.0 CLI shell."""
    from zoe_autonomy.chat import ZoeChat
    root = Path(zoe_root).expanduser().resolve()
    chat = ZoeChat(root, Path(state).expanduser().resolve())
    return LumeCli(chat, root).run(input_stream=input_stream, output_stream=output_stream)
