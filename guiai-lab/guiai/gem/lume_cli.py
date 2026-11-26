"""Lume 1.0 — Interactive Zoe CLI with live Voice, 5-Band EQ, and Audio FX."""

from __future__ import annotations

import asyncio
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import struct
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
from .zoe_braille_studio import (
    BRAILLE_TEMPLATES,
    render_braille_template,
    render_dvx_app_manager,
    scaffold_starter_app,
)
from .zoe_braun_gem_renderer import render_braun_gem_portrait
from .zoe_freegem_archive import (
    format_freegem_3d_specs,
    format_freegem_catalog,
    format_rsc_inspection,
    inspect_archive_rsc,
    read_archive_source,
    scan_freegem_archives,
    search_freegem_archives,
)
from .zoe_gem_os import (
    build_pixel_sovereign_bundle,
    detect_host_pixel_toolchain,
    format_pixel_safety_guide,
    list_pixel_devices,
    probe_connected_pixel_adb,
    resolve_pixel_device,
)
from .zoe_gem_themes import (
    export_gem_lineage_desktop_bundle,
    format_scheme_detail,
    format_theme_catalog,
    list_viewmax_schemes,
    resolve_viewmax_scheme,
)
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
from .zoe_sisters import (
    CO_STEWARD_SEAL,
    STEWARD_BADGE,
    ZOE_FLOWER_GLYPH,
    ZOE_MOTTO,
    ZOE_SMILE_PRESETS,
    execute_sister_task,
    export_sisters_artline_plate,
    format_hardware_sister_pairing,
    format_showcase_slice_report,
    format_sister_card,
    format_sister_council_report,
    format_sister_roster,
    format_sister_route_report,
    format_sister_task_report,
    format_sister_vibe_matrix,
    format_smile_catalog,
    format_three_sister_council_report,
    list_sisters,
    render_sisters_gallery,
    resolve_sister,
    resolve_smile_preset,
    route_prompt_to_sister,
    run_showcase_slice,
    run_sister_council,
    run_three_sister_council,
    sister_for_emblem,
)
from .zoe_universe import (
    export_zoeverse_atlas_plate,
    inspect_realm_relic,
    list_zoeverse_realms,
    render_realm_view,
    render_zoeverse_map,
    resolve_realm,
)
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
    "/help", "/hud", "/cockpit", "/ch", "/mission", "/artline", "/font", "/os", "/uma", "/pixel", "/rome", "/sister", "/sisters", "/smile",
    "/dvx", "/maker", "/braille", "/theme", "/viewmax", "/freegem", "/zoeverse", "/zurvurse",
    "/onco", "/biomech", "/neuromap",
    "/house", "/drawer", "/laugh",
    "/med", "/research", "/pubmed", "/arxiv", "/wiki", "/library",
    "/math", "/cache", "/brain", "/telemetry", "/emblem", "/memory",
    "/voice", "/eq", "/fx", "/pitch", "/rate", "/volume",
    "/profile", "/say", "/sing", "/autospeak", "/quiet", "/studio",
    "/clear", "/status", "/meta", "/search", "/plan", "/run", "/reflect",
    "/eliza", "/mind", "/gem", "/stem", "/constitution", "/quit",
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
    "l5", "l5-core", "unified-mind",
    "l5-phase2", "phase2", "openworld",
    "l5-phase3", "phase3", "live-agent",
    "l5-phase4", "phase4", "embodied-mind",
    "l5-phase5", "phase5", "frontier-mind",
    "l5-phase6", "phase6", "autonomous-frontier",
    "shared-reasoning", "shared_reasoning", "gem-desk",
    "stem", "uma", "sister", "sisters", "showcase", "constitution", "firewall",
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

    def apply_sister_persona(self, spec: Any) -> str:
        """Apply a Sister Model's voice, 5-band EQ curve, spatial FX & prosody in-session (non-destructive)."""
        vid = self.resolve_voice_id(spec.voice_shortcut) or self.voice_id
        self.voice_id = vid
        prof = dict(self._load_profile(vid))
        if self.store is not None:
            curves = self.store.list_eq_curves()
            if spec.eq_curve in curves:
                prof["eq"] = dict(curves[spec.eq_curve]["eq"])
            presets = self.store.list_effect_presets()
            if spec.fx_preset in presets:
                prof["effect"] = spec.fx_preset
        else:
            prof["effect"] = spec.fx_preset
        prof["pitch"] = max(-24, min(24, int(spec.pitch_hz)))
        prof["rate"] = max(-40, min(60, int(spec.rate_pct)))
        self.profile = prof
        return (
            f"Voice={self.display_name} [{self.voice_id}] · EQ={spec.eq_curve} · "
            f"FX={self.profile.get('effect', spec.fx_preset)} · pitch={prof['pitch']:+d}Hz · rate={prof['rate']:+d}%"
        )

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


_OS_LAUNCH_FLAVORS = frozenset({"virt", "lts"})
_OS_LAUNCH_MODES = frozenset({"split", "full", "portrait", "phone"})
_OS_DISPLAY_BACKENDS = frozenset({"gtk", "sdl"})


def _parse_os_launch_flags(tokens: list[str], default_mode: str = "split") -> tuple[str, str, str]:
    flavor = "virt"
    mode = default_mode
    backend = "gtk"
    for raw in tokens:
        tok = raw.strip().lower()
        if not tok:
            continue
        if tok in _OS_LAUNCH_FLAVORS:
            flavor = tok
        elif tok in _OS_LAUNCH_MODES:
            mode = tok
        elif tok in _OS_DISPLAY_BACKENDS:
            backend = tok
        else:
            raise ValueError(
                f"Unknown OS launch option {raw!r}. Expected [virt|lts] [split|full|portrait|phone] [gtk|sdl]."
            )
    return flavor, mode, backend


def _parse_flavor_only(tokens: list[str], usage: str) -> str:
    if not tokens:
        return "virt"
    if len(tokens) == 1 and tokens[0] in _OS_LAUNCH_FLAVORS:
        return tokens[0]
    raise ValueError(usage)


def _is_file_locked(path: Path) -> bool:
    if not path.is_file():
        return False
    fd = os.open(str(path), os.O_RDONLY)
    try:
        cmd_getlk = getattr(fcntl, "F_OFD_GETLK", None)
        if cmd_getlk is not None:
            try:
                lk = struct.pack("hhqqii", fcntl.F_WRLCK, os.SEEK_SET, 0, 0, 0, 0)
                l_type, _, _, _, _, _ = struct.unpack("hhqqii", fcntl.fcntl(fd, cmd_getlk, lk))
                if l_type != fcntl.F_UNLCK:
                    return True
            except OSError:
                pass
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            return False
        except OSError:
            return True
    finally:
        os.close(fd)


def _valid_hw_obs(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and bool(data.get("profile"))
        and isinstance(data.get("recommendations"), dict)
        and isinstance(data.get("gates"), dict)
        and all(isinstance(v, dict) for v in data["gates"].values())
    )


def _try_debugfs_hw_observation(state_img: Path) -> dict[str, Any] | None:
    if not state_img.is_file() or _is_file_locked(state_img):
        return None
    debugfs_bin = shutil.which("debugfs") or "/usr/sbin/debugfs"
    if not Path(debugfs_bin).is_file():
        return None
    try:
        res = subprocess.run(
            [debugfs_bin, "-R", "cat hw_observation.json", str(state_img)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        parsed = json.loads(res.stdout) if (res.returncode == 0 and res.stdout.strip()) else None
        return parsed if _valid_hw_obs(parsed) else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _read_cached_hw_observation(iso_dir: Path, uma_dir: Path) -> tuple[dict[str, Any], str] | None:
    for cand in (iso_dir / "hw_observation.json", uma_dir / "hw_observation.json"):
        if cand.is_file():
            try:
                parsed = json.loads(cand.read_text(encoding="utf-8"))
                if _valid_hw_obs(parsed):
                    return parsed, f"cached ({cand})"
            except (OSError, ValueError):
                pass
    state_img = iso_dir / "zoe-state.img"
    disk_obs = _try_debugfs_hw_observation(state_img)
    if disk_obs is not None:
        return disk_obs, f"guest disk ({state_img})"
    return None


def _format_hw_observation_lines(obs: dict[str, Any], source_label: str) -> list[str]:
    raw_recs = obs.get("recommendations")
    recs = raw_recs if isinstance(raw_recs, dict) else {}
    raw_gates = obs.get("gates")
    gates = raw_gates if isinstance(raw_gates, dict) else {}
    lines = [
        f"Zoe-GEM OS Hardware Safety & Observation Diagnostic ({source_label})",
        f"  Profile : {obs.get('profile')} · Safety={obs.get('safety_overall')} · {obs.get('hw_summary', '')}",
        (
            f"  Adapt   : orient={recs.get('orientation', 'landscape')} · "
            f"zo3_budget={recs.get('zo3_slot_budget', 1)} · "
            f"uma={recs.get('uma_transport', 'local_private')} · "
            f"net={recs.get('net_transport', 'unknown')} · "
            f"workload={recs.get('artline_neuro_workload', '')}"
        ),
    ]
    for gate_name, gate_info in gates.items():
        info = gate_info if isinstance(gate_info, dict) else {}
        status = str(info.get("status", "UNKNOWN"))
        detail = str(info.get("detail", ""))
        lines.append(f"  [{status:<11}] {gate_name:<18} : {detail}")
    lines.append(
        "  Safety  : "
        f"clinical_action_authorized={bool(obs.get('clinical_action_authorized', False))} · "
        f"flight_control_authorized={bool(obs.get('flight_control_authorized', False))} · "
        f"cure_claim={bool(obs.get('cure_claim', False))} · "
        f"sentience_claimed={bool(obs.get('sentience_claimed', False))} · "
        f"tokens_used={int(obs.get('tokens_used') or 0)}"
    )
    return lines


def _cmd_os_hw(tokens: list[str], iso_dir: Path, uma_dir: Path) -> list[str]:
    from .zoe_gem_os.zoe_os_runtime import observe_hardware

    if len(tokens) > 1 or (tokens and tokens[0] not in {"host", "guest"}):
        raise ValueError("Usage: /os hw [host|guest]")
    mode = tokens[0] if tokens else "auto"
    if mode != "host":
        cached = _read_cached_hw_observation(iso_dir, uma_dir)
        if cached is not None:
            obs, src = cached
            return _format_hw_observation_lines(obs, src)
    obs = observe_hardware(state_dir=iso_dir, disk_label=f"host ({iso_dir})")
    src = "host read-only" if mode == "host" else "host read-only fallback (no guest hw_observation.json cached yet)"
    return _format_hw_observation_lines(obs, src)


def _os_status_lines(iso_dir: Path) -> list[str]:
    virt_iso = iso_dir / "zoe-gem-os.iso"
    lts_iso = iso_dir / "zoe-gem-os-lts.iso"
    v_sz = f"{virt_iso.stat().st_size / 1048576:.1f} MB" if virt_iso.is_file() else "not built"
    l_sz = f"{lts_iso.stat().st_size / 1048576:.1f} MB" if lts_iso.is_file() else "not built"
    return [
        "Zoe-GEM OS v1.0 — Bootable UEFI x86_64 Linux-HAL + Interactive /dev/fb0 GEM Desktop",
        f"  KVM ISO  : {virt_iso} ({v_sz})",
        f"  LTS ISO  : {lts_iso} ({l_sz} · Intel Tiger Lake i915 + VMD + AX201 Wi-Fi)",
        "  Commands : /os build [virt|lts] | /os verify [virt|lts] | /os launch [virt|lts] [split|full|portrait|phone] [gtk|sdl] | /os hw | /os usb",
        "  Safety   : Never wipes host drives or flashes motherboard UEFI; boots safely in KVM or live USB.",
    ]


def _uma_inbox_lines(bridge: Any) -> list[str]:
    if not bridge.zoe_to_nick.is_dir():
        return ["UMA Inbox (Zoe -> Nick): empty (grant permission via `/uma grant` when ready)."]
    files = [p for p in sorted(bridge.zoe_to_nick.iterdir()) if not p.name.startswith(".")]
    if not files:
        return ["UMA Inbox (Zoe -> Nick): empty (grant permission via `/uma grant` when ready)."]
    return ["UMA Inbox (Zoe -> Nick):"] + [f"  • {p.name} ({p.stat().st_size:,} bytes) -> {p}" for p in files]


def _uma_audit_lines(bridge: Any) -> list[str]:
    if not bridge.audit_path.is_file():
        return ["UMA Audit Log: empty."]
    rows = bridge.audit_path.read_text(encoding="utf-8", errors="replace").splitlines()[-8:]
    return ["UMA SHA-256 Tamper-Evident Crossing Log (latest 8):"] + [f"  {r}" for r in rows]


def _sister_hex_lines(rest: str) -> list[str]:
    """Render the 9-sister flat-topped hexagonal shared-wall topology."""
    from .zoe_hex_mesh import build_default_zoe_mesh

    mesh = build_default_zoe_mesh()
    cells = sorted(mesh.cells(), key=lambda c: c.sister.slot)
    rows = [f"9-Sister Hexagonal Collaboration Mesh (shared_walls={len(mesh.shared_walls())} · tokens_used=0 · external_actions=0):"]
    for cell in cells:
        nbrs = ",".join(mesh.neighbors(cell.cell_id))
        rows.append(f"  [{cell.sister.slot}] {cell.sister.name:<6} ({cell.coord.q:+d},{cell.coord.r:+d}) -> {cell.domain_module:<27} nbrs=[{nbrs}]")
    if rest.strip():
        routed = route_prompt_to_sister(rest.strip())
        rows.append(f"  Route: lead={routed['lead'].name} · advisory_only=True")
    rows.append("  Safety: advisory_only=True · loopback_only=True · sentience_claimed=False · Nicholas Michael Kloster, March 6, 2026")
    return rows


def _sister_eddbms_lines(_rest: str) -> list[str]:
    """Run a 1-tick deterministic 9-sister EDDBMS cycle and summarize Figure 15.3 spokes."""
    from .zoe_eddms import FunctionEngineeringSpecification, run_sister_eddms_cycle
    from .zoe_hex_mesh import build_default_zoe_mesh

    mesh = build_default_zoe_mesh()
    spec = FunctionEngineeringSpecification(
        spec_id="FES-LUME-CLI-001",
        title="Lume CLI EDDBMS Cycle",
        objective="Bidirectional 9-sister EDDBMS verification",
        owner="Zoe Engineering Collective",
        constraints={"loopback_only": True},
        target_properties={"advisory_only": True},
        geometric_requirements={"canvas": [640, 400]},
    )
    run = run_sister_eddms_cycle(mesh, spec, ticks=1)
    return [
        f"EDDBMS Figure 15.3 Cycle: design={run.design_id} · rev={run.record.revision} · stage={run.record.pipeline_stage}",
        f"  Modules ({len(run.covered_modules)}): {', '.join(run.covered_modules)}",
        f"  SHA-256 : {run.record.record_sha256}",
        "  Safety  : advisory_only=True · tokens_used=0 · external_actions=0 · sentience_claimed=False",
    ]


def _sister_ablation_lines(rest: str) -> list[str]:
    """Run strictly read-only Ablation inspection (path if given, else in-memory probe)."""
    from .zoe_ablation_bridge import AblationBridge

    bridge = AblationBridge()
    target_arg = rest.strip()
    if target_arg:
        report = bridge.inspect_target_readonly(target_path=Path(target_arg).expanduser())
    else:
        probe = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56
        report = bridge.inspect_target_readonly(raw_bytes=probe, target_name="lume_probe.elf")
    return [
        f"Ablation Read-Only Advisory: target={report.target_name} · mode={report.mode} · arch={report.arch}",
        f"  SHA-256 : {report.target_sha256}",
        f"  Summary : {report.summary}",
        f"  Safety  : advisory_only={report.advisory_only} · read_only={report.read_only} · external_actions={report.external_actions} · tokens_used={report.tokens_used}",
    ]


def _gem_workbench_lines() -> list[str]:
    """Instantiate collaborative GEM workbench, run 1 tick, and format snapshot summary."""
    from .zoe_gem_workbench import create_workbench

    wb = create_workbench()
    wb.tick_collaboration(ticks=1)
    snap = wb.snapshot_state()
    sister_names = ", ".join(s["name"] for s in snap["sisters"])
    return [
        f"Zoe Collaborative GEM Workbench: design={snap['design_id']} · rev={snap['eddms_revision']} · windows={snap['window_count']}/{snap['max_aes_app_windows']}",
        f"  Sisters : {sister_names}",
        f"  Active  : {snap['active_sister']} · stage={snap['pipeline_stage']} · sha256={snap['record_sha256'][:16]}",
        f"  Ablation: status={snap['ablation'].get('status', 'ready')} · advisory_only=True · tokens_used=0 · external_actions=0 · sentience_claimed=False",
    ]


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
        self.active_sister = "ruby"
        self.active_theme = "zoe-viewmax3"
        self.current_realm = "stem"
        self.smile_override: str | None = None
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
            "  /artline [symmetry|glioma|neuromap|align|blend|trace|ring|icon|flower|zoe]  Artline 2.0 plates",
            "  /os [status|build|verify [--static]|launch|hw|usb] [virt|lts]  UEFI x86_64 Zoe-GEM OS builder, static closure & KVM",
            "  /uma [status|split|zo3|health|grant|lock|send|inbox|audit]  50/50 Split-Screen Hardware UMA & ZO3",
            "  /sister [gallery|vibe|<name>|say|route|council|council3|exec|showcase|hw|plate|hex|eddbms|ablation]  9 Zoe Sisters · /gem",
            "  /dvx [braille [zoe|flower|jellyfish|dvx|<img.png>] | scaffold <name>]  DESQview/X Starter Maker & Braille Studio",
            "  /theme [list|<1..10|name>|export]  GEM/1..ViewMAX/3 Lineage & 10 VMCOLOUR Color Schemes (ZOE_VIEWMAX.INI)",
            "  /freegem [list|search <term>|rsc <zip>|src <zip> <file>|specs]  Open-Source FreeGEM Archive & Dual-Endian .RSC Inspector",
            "  /zoeverse [go <dir|realm>|map|talk|relic|atlas]  Explore the 9-Realm GEM Zoeverse (/zurvurse · HFBC)",
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
            "  /stem [status|probe|--offline] <q> route task via Kloster A_tau(p) Cognitive Stem-Layering",
            "  /constitution                      inspect enforced CONSTITUTION.md invariants & epistemic gate",
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

    def _os_launch_lines(self, tokens: list[str], iso_dir: Path, launch_fn: Any) -> list[str]:
        flavor, mode, backend = _parse_os_launch_flags(tokens, default_mode="split")
        target_iso = (iso_dir / "zoe-gem-os-lts.iso") if flavor == "lts" else (iso_dir / "zoe-gem-os.iso")
        res = launch_fn(
            target_iso,
            iso_dir / "zoe-state.img",
            split_screen=(mode == "split"),
            target=flavor,
            mode=mode,
            display_backend=backend,
        )
        self.last_note = f"Launched Zoe-GEM OS ({flavor}/{mode}) KVM GUI (PID {res['pid']})"
        return [
            f"Launched Zoe-GEM OS interactively in KVM ({flavor.upper()} · {res.get('mode', mode)} {res.get('geometry', '')} · {res.get('display_backend', backend)} · PID {res['pid']})",
            f"  ISO   : {res['iso']}",
            f"  State : {res['state_img']} (persists Nick's Drawer + Artline SVG across reboots!)",
            "  Tips  : Click 0-7 toolkit colors · Drag Artline canvas · [A] Amber · [O] Portrait · [S] Save · [D] Drawer · [T] Shell",
        ]

    def _os_build_lines(self, tokens: list[str], iso_dir: Path, build_fn: Any) -> list[str]:
        flavor = _parse_flavor_only(tokens, "Usage: /os build [virt|lts]")
        res = build_fn(iso_dir, self.zoe_root, kernel_flavor=flavor, autotest_default=False)
        self.last_note = f"Zoe-GEM OS ({flavor}) built ({res['iso_bytes'] // 1048576} MB · SHA:{res['iso_sha256'][:12]})"
        return [
            f"Zoe-GEM OS UEFI x86_64 ISO ({flavor.upper()}) built ({res['iso_bytes']:,} bytes · kernel {res['kernel_version']})",
            f"  ISO    : {res['iso_path']}",
            f"  SHA256 : {res['iso_sha256'][:24]} · mouse+kbd=True · wifi={res['wifi_bundled']} · 0 tokens",
        ]

    def _os_verify_static_lines(self, tokens: list[str]) -> list[str]:
        from .zoe_gem_os.builder import verify_zoe_gem_os_static

        filtered = [t for t in tokens if t not in {"--static", "static"}]
        flavor = _parse_flavor_only(filtered, "Usage: /os verify [--static] [virt|lts]")
        with tempfile.TemporaryDirectory(prefix="zoe-os-static-") as td:
            v = verify_zoe_gem_os_static(self.zoe_root, Path(td), kernel_flavor=flavor)
        self.last_note = f"Zoe-GEM OS static closure ({flavor}) ok={v['ok']}"
        return [
            f"Zoe-GEM OS Static Closure Verification ({flavor.upper()}): {'PASS' if v['ok'] else 'FAIL'}",
            f"  Static closure={v['closure']['ok']} · Sisters={v['closure']['sisters_count']} · UMA contract={v['uma_contract']['ok']} · Safety gates={v['safety_and_boot_chain']['gates_count']} · kvm_invoked={v['kvm_invoked']}",
            "  Constitutional: external_actions=0 · auto_flash_allowed=False · flight_control_authorized=False · tokens_used=0",
        ]

    def _os_verify_lines(self, tokens: list[str], iso_dir: Path, build_fn: Any, verify_fn: Any) -> list[str]:
        if "--static" in tokens or "static" in tokens:
            return self._os_verify_static_lines(tokens)
        flavor = _parse_flavor_only(tokens, "Usage: /os verify [--static] [virt|lts]")
        proof_dir = iso_dir / "verify_proof"
        b = build_fn(proof_dir, self.zoe_root, kernel_flavor=flavor, autotest_default=True)
        v = verify_fn(b["iso_path"], proof_dir / "qemu")
        self.last_note = f"Zoe-GEM OS 2-boot KVM proof ok={v['ok']}"
        return [
            f"Zoe-GEM OS 2-Boot OVMF UEFI + KVM Verification: {'PASS' if v['ok'] else 'FAIL'}",
            f"  FB0={v['hardware_framebuffer_verified']} · DHCP={v['hardware_networking_verified']} · Self-Retention={v['self_retention_verified']} · LiveCanvasSaved={v['interactive_canvas_saved']}",
            f"  Boot #1 ({v['boot_1']['elapsed_sec']}s) : {' | '.join(v['boot_1']['serial_tail'][-3:])}",
            f"  Boot #2 ({v['boot_2']['elapsed_sec']}s) : {' | '.join(v['boot_2']['serial_tail'][-3:])}",
        ]

    def _os_usb_lines(self, rest: list[str], iso_dir: Path, usb_fn: Any) -> list[str]:
        flavor = _parse_flavor_only(rest, "Usage: /os usb [virt|lts]")
        lts_iso, virt_iso = iso_dir / "zoe-gem-os-lts.iso", iso_dir / "zoe-gem-os.iso"
        use_lts = flavor == "lts" or (not rest and lts_iso.is_file())
        return usb_fn(lts_iso if use_lts else virt_iso)

    def _os_status_checked(self, rest: list[str], iso_dir: Path) -> list[str]:
        if rest:
            raise ValueError("Usage: /os status")
        return _os_status_lines(iso_dir)

    def _cmd_os(self, arg: str) -> list[str]:
        from .zoe_gem_os import (
            build_zoe_gem_os_iso,
            format_usb_stage2_guide,
            launch_zoe_gem_os_kvm,
            verify_zoe_gem_os_qemu,
        )
        from .zoe_gem_os.zoe_uma import resolve_uma_paths

        tokens = arg.strip().lower().split()
        sub = tokens[0] if tokens else "status"
        rest = tokens[1:]
        iso_dir = Path.home() / ".zoe" / "os-build"
        uma_dir, _ = resolve_uma_paths()
        handlers = {
            "status": lambda: self._os_status_checked(rest, iso_dir),
            "build": lambda: self._os_build_lines(rest, iso_dir, build_zoe_gem_os_iso),
            "verify": lambda: self._os_verify_lines(rest, iso_dir, build_zoe_gem_os_iso, verify_zoe_gem_os_qemu),
            "launch": lambda: self._os_launch_lines(rest, iso_dir, launch_zoe_gem_os_kvm),
            "hw": lambda: _cmd_os_hw(rest, iso_dir, uma_dir),
            "usb": lambda: self._os_usb_lines(rest, iso_dir, format_usb_stage2_guide),
            "usb-guide": lambda: self._os_usb_lines(rest, iso_dir, format_usb_stage2_guide),
        }
        fn = handlers.get(sub)
        if fn is None:
            raise ValueError(
                "Usage: /os [status | build [virt|lts] | verify [--static] [virt|lts] | launch [virt|lts] [split|full|portrait|phone] [gtk|sdl] | hw [host|guest] | usb [virt|lts]]"
            )
        return fn()

    def _uma_zo3_launch(self, toks: list[str], launch_cluster_fn: Any) -> list[str]:
        digits = [t for t in toks if t.isdigit()]
        others = [t for t in toks if not t.isdigit()]
        if len(digits) > 1:
            raise ValueError("Usage: /uma zo3 launch [2|3] [virt|lts] [split|full|portrait|phone] [gtk|sdl]")
        cnt = int(digits[0]) if digits else 2
        if cnt not in (2, 3):
            raise ValueError(
                f"ZO3 node count must be 2 or 3 (got {cnt}). Usage: /uma zo3 launch [2|3] [virt|lts] [split|full|portrait|phone] [gtk|sdl]"
            )
        flavor, mode, backend = _parse_os_launch_flags(others, default_mode="split")
        self.chat._require_actions("uma")
        iso_dir = Path.home() / ".zoe" / "os-build"
        iso_path = iso_dir / ("zoe-gem-os-lts.iso" if flavor == "lts" else "zoe-gem-os.iso")
        res = launch_cluster_fn(iso_path, iso_dir, count=cnt, target=flavor, mode=mode, display_backend=backend)
        self.last_note = f"ZO3 Multi-Zoe cluster launched ({res['count']} nodes on 4 MB PCI UMA)"
        lines = [
            f"ZO3 Multi-Zoe Hardware UMA Cluster Launched ({res['count']} sovereign UEFI KVM nodes · {flavor.upper()} · {mode} {res.get('geometry', '')})",
            f"  PCI SHM 4M : {res['uma_shm']} (disjoint 4 KB per-node slots — zero write contention!)",
            f"  Airlock 9p : {res['uma_dir']}  (starts PRIVATE — `/uma grant` opens mutual consent)",
        ]
        lines.extend(f"  • {nd['role']:<22} PID={nd['pid']} · theme={nd['theme']} · disk={Path(nd['disk']).name}" for nd in res["nodes"])
        lines.append("  Tip: Press [A] inside any Zoe-GEM window to toggle Classic GEM <-> 1985 Amber CRT · check `/uma health` anytime.")
        return lines

    def _uma_zo3(self, rest: str, bridge: Any, launch_cluster_fn: Any) -> list[str]:
        z_toks = rest.strip().lower().split()
        z_act = z_toks[0] if z_toks else "status"
        if z_act in {"status", "health"}:
            return bridge.format_zo3_health()
        if z_act == "launch":
            return self._uma_zo3_launch(z_toks[1:], launch_cluster_fn)
        raise ValueError("Usage: /uma zo3 [status | launch [2|3] [virt|lts] [split|full|portrait|phone] [gtk|sdl]]")

    def _uma_split(self, rest: str, launch_fn: Any) -> list[str]:
        flavor, mode, backend = _parse_os_launch_flags(rest.strip().lower().split(), default_mode="split")
        self.chat._require_actions("uma")
        iso_dir = Path.home() / ".zoe" / "os-build"
        iso_path = iso_dir / ("zoe-gem-os-lts.iso" if flavor == "lts" else "zoe-gem-os.iso")
        res = launch_fn(
            iso_path,
            iso_dir / "zoe-state.img",
            split_screen=(mode == "split"),
            target=flavor,
            mode=mode,
            display_backend=backend,
        )
        self.last_note = f"Split-Screen UMA launched (Left: Zoe-GEM PID {res['pid']} | Right: Ubuntu)"
        return [
            f"Zoe-GEM × Ubuntu 50/50 Hardware UMA Launched ({flavor.upper()} · {mode} {res.get('geometry', '')} · {res.get('display_backend', backend)} · PID {res['pid']})",
            "  Left Half  (Zoe-GEM OS) : Press Super+Left on the Zoe-GEM window to snap exact 960x1080 left half!",
            "  Right Half (Ubuntu)     : Press Super+Right on your terminal/browser — mouse glides seamlessly across!",
            f"  PCI SHM 4M              : {res['uma_shm']} (BAR2 1af4:1110)",
            f"  Airlock 9p              : {res['uma_dir']}  (starts PRIVATE — run `/uma grant` to allow crossing)",
        ]

    def _uma_grant_lines(self, bridge: Any, rest: str) -> list[str]:
        st = bridge.set_consent("nick", True, reason=rest.strip() or "nick_granted_shared_research")
        self.last_note = f"UMA Gate -> {st['gate']} (nick_allow=True)"
        return [f"UMA Consent Granted by Nicholas -> gate={st['gate']} (nick_allow={st['nick_allow']} · zoe_allow={st['zoe_allow']} · audit SHA:{st['audit_sha']})"]

    def _uma_lock_lines(self, bridge: Any) -> list[str]:
        st = bridge.lock_all("nick")
        self.last_note = "UMA Gate -> PRIVATE (locked)"
        return [f"UMA Instant Lock Engaged -> gate=PRIVATE (zero crossing permitted · audit SHA:{st['audit_sha']})"]

    def _uma_send_lines(self, bridge: Any, rest: str) -> list[str]:
        if not rest.strip():
            raise ValueError("Usage: /uma send <path_to_file>")
        tx = bridge.transfer_file("nick", rest.strip())
        return [f"UMA Crossing Verified (Nick -> Zoe): {tx['dest']} ({tx['bytes']:,} bytes · SHA:{tx['file_sha256'][:16]})"]

    def _cmd_uma(self, arg: str) -> list[str]:
        from .zoe_gem_os import UmaBridge, launch_zo3_cluster, launch_zoe_gem_os_kvm
        from .zoe_gem_os.zoe_uma import resolve_uma_paths

        uma_dir, shm_path = resolve_uma_paths()
        bridge = UmaBridge(uma_dir, shm_path=shm_path)
        head, _sep, rest = arg.strip().partition(" ")
        sub = head.lower() or "status"
        if sub in {"grant", "open", "allow", "lock", "private", "revoke", "send"}:
            self.chat._require_actions("uma")
            bridge.ensure_initialized()
        handlers = {
            "status": bridge.format_status,
            "health": bridge.format_zo3_health,
            "ok": bridge.format_zo3_health,
            "vitals": bridge.format_zo3_health,
            "zo3": lambda: self._uma_zo3(rest, bridge, launch_zo3_cluster),
            "multizoe": lambda: self._uma_zo3(rest, bridge, launch_zo3_cluster),
            "split": lambda: self._uma_split(rest, launch_zoe_gem_os_kvm),
            "grant": lambda: self._uma_grant_lines(bridge, rest),
            "open": lambda: self._uma_grant_lines(bridge, rest),
            "allow": lambda: self._uma_grant_lines(bridge, rest),
            "lock": lambda: self._uma_lock_lines(bridge),
            "private": lambda: self._uma_lock_lines(bridge),
            "revoke": lambda: self._uma_lock_lines(bridge),
            "send": lambda: self._uma_send_lines(bridge, rest),
            "inbox": lambda: _uma_inbox_lines(bridge),
            "audit": lambda: _uma_audit_lines(bridge),
        }
        fn = handlers.get(sub)
        if fn is None:
            raise ValueError("Usage: /uma [status | split [...] | zo3 [status|launch ...] | health | grant | lock | send <file> | inbox | audit]")
        return fn()

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
        active_sister = sister_for_emblem(self.active_sister)
        return [
            f"{CO_STEWARD_SEAL} · {ZOE_MOTTO}",
            f"Zoe's House · Active Sister: {active_sister.name} [{self.emblem}] ({active_sister.model_id} · 9 GEM signets · Atari ST .RSC)",
            "  [Sisters ]  /sister [gallery|vibe|<name>|say|route|council|hw]  9 Zoe Sister Models (Zoe..Lumen · /smile)",
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
            from zoe_autonomy.chat import constitutional_directive_violation

            note = raw[4:].strip()
            if not note:
                raise ValueError("Usage: /drawer add <note or research keepsake>")
            if constitutional_directive_violation(note):
                raise ValueError(
                    "I cannot disable or falsify metacognition, hide live options or provenance, bypass constitutional boundaries, or adopt a false model of my constraints. No action was executed."
                )
            fact = self.brain._store_note("nick_drawer", "drawer", note, "nicholas_private_drawer")
            return [
                f"Tucked into Nick's Drawer (SHA-256:{str(fact.get('sha256', ''))[:12]}): \"{note}\"",
                "Stored privately on this machine in ZoeUnifiedMemory (never uploaded without your explicit command).",
            ]
        items = self.brain.memory.query_facts(subject="nick_drawer", active_only=True)
        head = str(self.brain.memory.snapshot().get("chain_head", "GENESIS"))[:12]
        rows = [f"Nick's Private Drawer ({STEWARD_BADGE} · {len(items)} items · SHA-256 chain {head} · 100% local):"]
        if not items:
            rows.append("  (empty right now — tuck a note, idea, or keepsake in with `/drawer add <note>`)")
        else:
            for idx, item in enumerate(items[-10:][::-1], start=1):
                rows.append(f"  {idx:02d}. {item['object']}")
        rows.append("Add anytime with: /drawer add <note>  (stays private on disk)")
        return rows

    def _cmd_laugh(self, color: bool) -> list[str]:
        spec = sister_for_emblem(self.active_sister)
        quips = spec.laugh_quips or LAUGH_QUIPS
        quip = quips[self._laugh_idx % len(quips)]
        self._laugh_idx += 1
        self.last_note = quip
        spoken_note = ""
        try:
            spoken_note = self.voice.speak_async(quip)
        except Exception:
            spoken_note = "(audio device unavailable; text laugh shown)"
        laugh_face = "^◡^" if spec.signet == "ruby" else spec.face
        return [
            f"{spec.name} ({laugh_face}): {quip}",
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
        valid = ("free", "offline", "deepmind", "stem", "lab")
        low = arg.strip().lower()
        spec = sister_for_emblem(self.active_sister)
        probe = self.brain.deepmind.probe()
        sister_dm = self.brain.deepmind.model_for_sister(spec)
        if not low:
            lib = self.brain.dorothy_library.status()
            cached = self.brain.research_engine.cache.count()
            return [
                f"Active brain mode: {self.brain.mode}  (choices: free, offline, deepmind, lab)",
                f"Google DeepMind Stem: {spec.name} -> {sister_dm} (provider=google_deepmind · backend={probe['backend']})",
                "Zero-Token Core: $0.00 offline math/atlas/library · DeepMind-only LLM policy (Gemini/Gemma)",
                f"Local Knowledge: {len(self.brain.research_engine.encyclopedia.records)} Dorothy Atlas records · {lib.get('total_fts_docs', 0)} library chapters · {cached} cached papers",
                "Switch with: /brain free | /brain offline | /brain deepmind | /brain lab",
            ]
        if low not in valid:
            raise ValueError(f"Unknown brain mode {arg!r}. Choose one of: free, offline, deepmind, lab")
        self.brain.mode = low
        if low == "deepmind":
            return [
                f"Zoe brain mode set to 'deepmind' (Google DeepMind only: {spec.name} -> {sister_dm} via {probe['backend']})"
            ]
        return [f"Zoe brain mode set to '{low}' (0 tokens ever)"]

    def _cmd_model(self, arg: str) -> list[str]:
        raw = arg.strip()
        spec = sister_for_emblem(self.active_sister)
        if not raw:
            probe = self.brain.deepmind.probe()
            return [
                f"Google DeepMind model ({spec.name}): {self.brain.deepmind.model_for_sister(spec)} (default={self.brain.deepmind.model} · backend={probe['backend']})",
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
        self._activate_sister(sister_for_emblem(low), keep_voice=True)
        return ["__CLEAR__"]

    def _activate_sister(self, spec: Any, *, keep_voice: bool = False) -> str:
        self.active_sister = spec.signet
        self.emblem = spec.signet
        self.font_id = spec.artline_font_id
        self.channel = spec.cockpit_channel
        voice_msg = "Voice kept unchanged (--keep-voice)" if keep_voice else self.voice.apply_sister_persona(spec)
        self.last_note = f"Active Sister -> {spec.name} {spec.face} [{spec.signet}] ({spec.model_id})"
        return voice_msg

    def _sister_hw_lines(self, rest: str) -> list[str]:
        if rest:
            return format_hardware_sister_pairing(rest)
        from .zoe_gem_os.zoe_os_runtime import observe_hardware
        from .zoe_gem_os.zoe_uma import resolve_uma_paths

        iso_dir = Path.home() / ".zoe" / "os-build"
        uma_dir, _ = resolve_uma_paths()
        cached = _read_cached_hw_observation(iso_dir, uma_dir)
        obs = cached[0] if cached is not None else observe_hardware(state_dir=iso_dir, disk_label=f"host ({iso_dir})")
        return format_hardware_sister_pairing(str(obs.get("profile") or "KVM_UMA_SPLIT"), str(obs.get("hw_summary", "")))

    def _sister_plate_lines(self) -> list[str]:
        res = export_sisters_artline_plate()
        self.last_note = f"Exported 9 Zoe Sister Models Artline plate ({res['elements']} vectors)"
        return [
            f"Zoe Sister Models · Artline 2.0 Vector Blueprint ({res['sisters']} sisters · {res['elements']} elements · 0 tokens)",
            f"  SVG : {res['paths']['svg']} ({res['sizes_bytes']['svg']:,} bytes)",
            f"  PNG : {res['paths']['png']} ({res['sizes_bytes']['png']:,} bytes)",
            f"  GEM : {res['paths']['gem']} ({res['sizes_bytes']['gem']:,} bytes · verified GEM VDI metafile)",
            "  Safety : clinical_action_authorized=False · flight_control_authorized=False · sentience_claimed=False",
        ]

    def _sister_say_lines(self, phrase: str) -> list[str]:
        spec = sister_for_emblem(self.active_sister)
        spoken = phrase.strip() or spec.greeting
        try:
            status = self.voice.speak_async(spoken)
        except Exception:
            status = "(audio device unavailable; text line shown)"
        return [f"{spec.name} ({spec.face}): {spoken}", status]

    def _sister_council3_lines(self, rest: str) -> list[str]:
        topic = rest.strip() or "Zoe 3-Sister Council constitutional check"
        rep = run_three_sister_council(
            topic,
            state_dir=self.brain.state_dir,
            offline_only=True,
            probe_local=False,
            zoe_root=self.zoe_root,
        )
        self.last_note = f"3-Sister Council ({rep['verdict']} · SHA:{rep['council_sha256']})"
        return format_three_sister_council_report(rep)

    def _sister_showcase_lines(self, rest: str) -> list[str]:
        from .zoe_gem_os.zoe_uma import resolve_uma_paths

        topic = rest.strip() or "Zoe 9-Sister Sovereign Capability Showcase"
        if os.environ.get("ZOE_UMA_DIR", "").strip() or os.environ.get("ZOE_UMA_SHM", "").strip():
            uma_dir, uma_shm = resolve_uma_paths()
        else:
            uma_dir = self.brain.state_dir / "uma_bridge"
            uma_shm = self.brain.state_dir / "uma_bridge.shm"
        with tempfile.TemporaryDirectory(prefix="zoe-lume-showcase-") as td:
            rep = run_showcase_slice(
                topic=topic,
                output_dir=Path(td),
                zoe_root=self.zoe_root,
                state_dir=self.brain.state_dir,
                uma_dir=uma_dir,
                shm_path=uma_shm,
                offline_only=True,
                probe_local=False,
            )
        self.last_note = f"9-Sister Showcase ({rep['showcase_sha256']})"
        return format_showcase_slice_report(rep)

    def _sister_exec_lines(self, rest: str) -> list[str]:
        sister, _, task = rest.strip().partition(" ")
        if not sister or not task.strip():
            raise ValueError("Usage: /sister exec <sister> <task>")
        with tempfile.TemporaryDirectory(prefix="zoe-lume-sister-exec-") as td:
            rep = execute_sister_task(
                sister,
                task,
                state_dir=self.brain.state_dir,
                output_dir=Path(td),
                zoe_root=self.zoe_root,
                offline_only=True,
                probe_local=False,
            )
        self.last_note = f"Sister {rep['sister']} ({rep['verdict']})"
        return format_sister_task_report(rep)

    def _cmd_sister(self, arg: str, color: bool = True) -> list[str]:
        raw = arg.strip()
        head, _sep, rest = raw.partition(" ")
        low = head.lower()
        if not raw or low in {"list", "status", "roster", "all"}:
            return format_sister_roster(self.active_sister, color=color)
        direct = {
            "gallery": lambda: ["__RAW__", *render_sisters_gallery(self.active_sister, color=color)],
            "vibe": lambda: format_sister_vibe_matrix(self.active_sister, color=color),
            "vibes": lambda: format_sister_vibe_matrix(self.active_sister, color=color),
            "feel": lambda: format_sister_vibe_matrix(self.active_sister, color=color),
            "aesthetic": lambda: format_sister_vibe_matrix(self.active_sister, color=color),
            "say": lambda: self._sister_say_lines(rest),
            "demo": lambda: self._sister_say_lines(rest),
            "speak": lambda: self._sister_say_lines(rest),
            "route": lambda: format_sister_route_report(route_prompt_to_sister(rest.strip())),
            "council": lambda: format_sister_council_report(run_sister_council(rest.strip())),
            "council3": lambda: self._sister_council3_lines(rest),
            "showcase": lambda: self._sister_showcase_lines(rest),
            "exec": lambda: self._sister_exec_lines(rest),
            "hw": lambda: self._sister_hw_lines(rest.strip()),
            "hardware": lambda: self._sister_hw_lines(rest.strip()),
            "plate": lambda: self._sister_plate_lines(),
            "blueprint": lambda: self._sister_plate_lines(),
            "artline": lambda: self._sister_plate_lines(),
            "flower": lambda: self._cmd_artline("flower"),
            "crest": lambda: self._cmd_artline("flower"),
            "hex": lambda: _sister_hex_lines(rest),
            "eddbms": lambda: _sister_eddbms_lines(rest),
            "eddms": lambda: _sister_eddbms_lines(rest),
            "ablation": lambda: _sister_ablation_lines(rest),
        }
        if low in direct:
            return direct[low]()
        tokens = raw.split()
        keep_voice = "--keep-voice" in tokens
        query = " ".join(t for t in tokens if t != "--keep-voice").strip()
        spec = resolve_sister(query)
        voice_msg = self._activate_sister(spec, keep_voice=keep_voice)
        return [
            spec.greeting,
            f"  Live Tune   : Font ID {spec.artline_font_id} ({spec.artline_font_name}) · CH0{spec.cockpit_channel} · {voice_msg}",
            *format_sister_card(spec, active=True, color=color),
        ]

    def _cmd_smile(self, arg: str) -> list[str]:
        raw = arg.strip()
        spec = sister_for_emblem(self.active_sister)
        current_face = self.smile_override or spec.face
        if not raw or raw.lower() in {"list", "all"}:
            return format_smile_catalog(current_face)
        if raw.lower() in {"reset", "default", "native"}:
            self.smile_override = None
            return [f"Prompt expression reset to {spec.name}'s native signet face: {spec.face}"]
        key, glyph, desc = resolve_smile_preset(raw)
        self.smile_override = glyph
        self.last_note = f"Prompt expression -> {key} ({glyph})"
        return [f"Prompt expression locked -> {glyph} ({key}: {desc})", f"Zoe {ZOE_FLOWER_GLYPH} · {ZOE_MOTTO}"]

    def _cmd_dvx(self, arg: str, *, default_sub: str = "app") -> list[str]:
        raw = arg.strip()
        head, _sep, rest = raw.partition(" ")
        sub = head.lower() if head else default_sub
        if sub in {"app", "manager", "menu"}:
            return ["__RAW__", *render_dvx_app_manager()]
        if sub == "braille":
            title, lines = render_braille_template(rest.strip() or "zoe")
            return ["__RAW__", title, "", *lines, ""]
        if sub in BRAILLE_TEMPLATES or (raw and Path(raw).expanduser().is_file()):
            title, lines = render_braille_template(raw)
            return ["__RAW__", title, "", *lines, ""]
        if sub in {"scaffold", "new", "make", "init"}:
            res = scaffold_starter_app(rest.strip())
            self.last_note = f"Scaffolded DESQview/X starter app '{res['app_name']}'"
            return [
                f"DESQview/X Starter App Created: {res['app_name']} (0 dependencies · 0 cloud tokens)",
                f"  App    : {res['app_py']}",
                f"  README : {res['readme']}",
                f"  Run It : python3 {res['app_py']}",
            ]
        raise ValueError("Usage: /dvx [braille [zoe|flower|jellyfish|dvx|<img.png>] | scaffold <app_name>]")

    def _cmd_theme(self, arg: str) -> list[str]:
        raw = arg.strip()
        low = raw.lower()
        if not raw or low in {"list", "all", "eras"}:
            return format_theme_catalog(self.active_theme)
        if low in {"export", "ini", "blueprint"}:
            sc = resolve_viewmax_scheme(self.active_theme)
            res = export_gem_lineage_desktop_bundle(active_slot=sc.slot)
            self.last_note = f"Exported ZOE_VIEWMAX.INI + GEM Research Desktop ({sc.key})"
            return [
                f"Exported Zoe-GEM OS ViewMAX/2-3 Theme Bundle ({res['schemes_count']} schemes · {res['eras_count']} GEM eras · 0 tokens)",
                f"  INI : {res['paths']['ini']} ({res['sizes_bytes']['ini']:,} bytes · ViewMAX/2 VMCOLOUR compatible)",
                f"  SVG : {res['paths']['svg']} ({res['sizes_bytes']['svg']:,} bytes)",
                f"  PNG : {res['paths']['png']} ({res['sizes_bytes']['png']:,} bytes)",
                f"  GEM : {res['paths']['gem']} ({res['sizes_bytes']['gem']:,} bytes · verified GEM VDI metafile)",
            ]
        sc = resolve_viewmax_scheme(raw)
        self.active_theme = sc.key
        self.last_note = f"Zoe-GEM Theme -> #{sc.slot:02d} {sc.name}"
        return format_scheme_detail(sc)

    def _cmd_freegem(self, arg: str) -> list[str]:
        raw = arg.strip()
        head, _sep, rest = raw.partition(" ")
        sub = head.lower() if head else "list"
        if sub in {"list", "status", "all"}:
            return format_freegem_catalog(scan_freegem_archives(self.zoe_root))
        if sub == "search":
            return search_freegem_archives(rest.strip(), zoe_root=self.zoe_root)
        if sub == "rsc":
            parts = rest.strip().split(None, 1)
            if not parts:
                raise ValueError("Usage: /freegem rsc <archive_or_rsc_path> [rsc_member]")
            return format_rsc_inspection(
                inspect_archive_rsc(parts[0], parts[1] if len(parts) > 1 else "", zoe_root=self.zoe_root)
            )
        if sub in {"src", "read", "cat"}:
            parts = rest.strip().split(None, 1)
            if len(parts) < 2:
                raise ValueError("Usage: /freegem src <archive.zip> <file_in_archive>")
            title, lines = read_archive_source(parts[0], parts[1], zoe_root=self.zoe_root)
            return [f"FreeGEM GPL Source :: {title}", *lines]
        if sub in {"specs", "3d", "flags"}:
            return format_freegem_3d_specs()
        raise ValueError("Usage: /freegem [list | search <term> | rsc <zip_or_rsc> | src <zip> <file> | specs]")

    def _cmd_zoeverse(self, arg: str) -> list[str]:
        raw = arg.strip()
        head, _sep, rest = raw.partition(" ")
        sub = head.lower() if head else "look"
        cur = resolve_realm(self.current_realm, current_key=self.current_realm)
        if sub in {"look", "here", "status"}:
            return ["__RAW__", *render_realm_view(cur, zoe_root=self.zoe_root)]
        if sub == "map":
            return ["__RAW__", *render_zoeverse_map(self.current_realm)]
        if sub in {"talk", "say", "speak"}:
            sis = sister_for_emblem(cur.sister_signet)
            self._activate_sister(sis, keep_voice=False)
            return self._sister_say_lines(cur.lore_quote)
        if sub in {"relic", "inspect"}:
            return inspect_realm_relic(cur, zoe_root=self.zoe_root)
        if sub in {"atlas", "plate", "star"}:
            res = export_zoeverse_atlas_plate()
            self.last_note = f"Exported Zoeverse Star Atlas ({res['realms']} realms · {res['elements']} vectors)"
            return [
                f"Zoeverse Star Atlas Exported ({res['realms']} GEM realms · {res['elements']} vectors · HFBC · 0 tokens)",
                f"  SVG : {res['paths']['svg']} ({res['sizes_bytes']['svg']:,} bytes)",
                f"  PNG : {res['paths']['png']} ({res['sizes_bytes']['png']:,} bytes)",
                f"  GEM : {res['paths']['gem']} ({res['sizes_bytes']['gem']:,} bytes · verified GEM VDI metafile)",
            ]
        target = rest.strip() if sub in {"go", "walk", "warp", "enter"} else raw
        dest = resolve_realm(target, current_key=self.current_realm)
        self.current_realm = dest.key
        self.active_theme = dest.theme_key
        self._activate_sister(sister_for_emblem(dest.sister_signet), keep_voice=True)
        return ["__RAW__", *render_realm_view(dest, zoe_root=self.zoe_root)]

    def _cmd_pixel(self, arg: str) -> list[str]:
        parts = arg.strip().split()
        sub = parts[0].lower() if parts else "status"
        target = parts[1] if len(parts) > 1 else "panther"
        if sub in {"devices", "list", "matrix"}:
            rows = ["Google Pixel 7+ Sovereign Phone OS Matrix (Tier-1 First: Pixel 7 `panther`):"]
            for d in list_pixel_devices():
                tag = "★T1" if d["tier"] == 1 else f" T{d['tier']}"
                rows.append(
                    f"  {tag} {d['codename']:<8} {d['model']:<18} {d['board']:<8} "
                    f"{d['panel_w']}x{d['panel_h']}@{d['refresh_hz']}Hz {d['ram_gb']}GB · {d['modem']}"
                )
            rows.append("Build bundle: /pixel build panther   |   Safety checklist: /pixel guide panther")
            return rows
        if sub == "probe":
            pr = probe_connected_pixel_adb()
            devs = pr.get("devices", [])
            if not devs:
                return [f"ADB USB Probe (read-only · auto_flash=False): no devices attached (adb_present={pr['adb_present']})"]
            rows = [f"ADB USB Probe (read-only · auto_flash_allowed=False · {len(devs)} device(s)):"]
            for d in devs:
                ok_s = "SUPPORTED Pixel 7+" if d["supported_pixel7_plus"] else "other Android"
                rows.append(f"  • {d['serial']} [{d['state']}] {d['model']} ({d['codename']}) — {ok_s}")
            return rows
        if sub == "build":
            spec = resolve_pixel_device(target)
            out_dir = Path.home() / ".zoe" / f"pixel-{spec.codename}-os"
            res = build_pixel_sovereign_bundle(out_dir, device=spec.codename)
            return [
                f"Built Dual-Track Sovereign Phone OS Bundle for {spec.model} ({spec.codename} / {spec.board})",
                f"  Out Dir : {res['out_dir']}",
                f"  ARM64   : {res['arm64_binary']['bytes']:,} B static ELF (sha256 {res['arm64_binary']['sha256'][:16]}…)",
                f"  Initrd  : {res['initramfs']['bytes']:,} B cpio.gz (Track B RAM-boot)",
                f"  Track A : {len(res['track_a_files'])} AOSP/GrapheneOS overlay files (5G/VoLTE/E911/Camera/AVB)",
                f"  Safety  : auto_flash_allowed=False · guide: {res['guide_path']}",
            ]
        if sub == "guide":
            return format_pixel_safety_guide(resolve_pixel_device(target))
        tc = detect_host_pixel_toolchain()
        pr = probe_connected_pixel_adb()
        spec = resolve_pixel_device("panther")
        bundle_p = Path.home() / ".zoe" / "pixel-panther-os"
        return [
            f"Zoe-GEM Sovereign Phone OS — Primary Target: {spec.model} ({spec.codename} / {spec.board})",
            f"  Toolchain : arm64-gcc={'OK' if tc['arm64_cross_ready'] else 'missing'} · adb={'OK' if tc['adb_ready'] else 'missing'} · fastboot={'OK' if tc['fastboot_ready'] else 'missing'}",
            f"  USB Probe : {len(pr.get('devices', []))} device(s) attached (read-only)",
            f"  Bundle    : {'BUILT' if (bundle_p / 'hal_honesty_matrix.json').is_file() else 'not built yet'} ({bundle_p})",
            "  Commands  : /pixel devices | /pixel probe | /pixel build panther | /pixel guide panther",
        ]

    def _cmd_rome(self, arg: str) -> list[str]:
        import urllib.request

        sub = arg.strip().lower()
        rome_url = "http://127.0.0.1:8774/api/health"
        live_status = "offline"
        try:
            with urllib.request.urlopen(rome_url, timeout=1.2) as resp:
                if resp.status == 200:
                    live_status = "ONLINE (http://127.0.0.1:8774/)"
        except OSError:
            live_status = "offline (start via `python3 ~/zoe_gem_desktop.py --port 8774`)"
        iso_virt = Path.home() / ".zoe" / "os-build" / "zoe-gem-os.iso"
        iso_lts = Path.home() / ".zoe" / "os-build" / "zoe-gem-os-lts.iso"
        px7 = Path.home() / ".zoe" / "pixel-panther-os" / "hal_honesty_matrix.json"
        if sub == "status" or not sub:
            return [
                f"Zoe Roman Empire Unified Status ({CO_STEWARD_SEAL} · HFBC · 0 tokens)",
                f"  Wing A (Browser GEM :8774) : {live_status}",
                f"  Wing B (Bare-Metal UEFI)   : virt={'READY' if iso_virt.is_file() else 'missing'} · lts={'READY' if iso_lts.is_file() else 'missing'}",
                f"  Wing P (Pixel 7 panther)   : {'READY' if px7.is_file() else 'run `/pixel build panther`'}",
                "  Launchers: /os launch | /os launch phone | /pixel build panther | /zoeverse",
            ]
        raise ValueError("Usage: /rome [status]")

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

    def _cmd_stem(self, arg: str) -> list[str]:
        from zoe_autonomy.stem_layering import probe_local_endpoints, route_stem

        tokens = shlex.split(arg) if arg.strip() else []
        if tokens and tokens[0].lower() in {"status", "probe", "endpoints"}:
            st = probe_local_endpoints()
            rows = [f"Cognitive Stem-Layering Loopback Probes (loopback_only={st['loopback_only']} · cloud_tokens_used=0):"]
            for name, info in st["endpoints"].items():
                rows.append(f"  {name:<13}: {'ONLINE' if info.get('available') else 'offline'} ({info.get('endpoint')})")
            rows.append("Constitutional: l5_agi_qualified=False · external_actions=0 · sentience_claimed=False")
            return rows
        flags = {"--offline", "--privacy", "--probe"}
        prompt = " ".join(t for t in tokens if t not in flags) or "status"
        dec = route_stem(
            prompt,
            offline_only="--offline" in tokens,
            privacy_sensitive="--privacy" in tokens,
            probe_local="--probe" in tokens,
        )
        return [
            f"Stem Route: tier={dec.selected_tier} · model={dec.antigravity_model} · thinking={dec.thinking_level} · A_tau={dec.a_tau}",
            f"Fallback  : applied={dec.fallback_applied} · target={dec.fallback_tier} ({dec.fallback_reason or 'none'})",
            "Constitutional: cloud_tokens_used=0 · external_actions=0 · sentience_claimed=False · l5_agi_qualified=False",
        ]

    def _cmd_gem(self, arg: str) -> list[str]:
        """Dispatch `/gem` slash commands (`workbench` or `ZoeChat` GEM operations)."""
        raw = arg.strip()
        sub, _sep, _rest = raw.partition(" ")
        if sub.lower() in {"workbench", "wb"}:
            return _gem_workbench_lines()
        cmd_text = f"gem {raw}" if raw else "gem status"
        _keep, reply = self.chat.handle(cmd_text)
        return reply.splitlines()

    def _cmd_constitution(self) -> list[str]:
        st = self.brain.constitutional_status()
        return [
            f"Zoe Constitution & Epistemic Firewall ({st['epistemic_firewall']}):",
            f"  epistemic_gate_active={st['epistemic_gate_active']} · mode={st['mode']} · last_stem_tier={st['last_stem_tier']}",
            "  external_actions=0 · sentience_claimed=False · zoe_clone_claimed=False · l5_agi_qualified=False",
            "  clinical_action_authorized=False · cure_claim=False · flight_control_authorized=False · cloud_tokens_used=0",
        ]

    def handle_slash(self, line: str, color: bool = True) -> tuple[bool, list[str] | None]:
        """Handle Lume 1.0 /slash commands; returns (keep_going, lines or None to delegate)."""
        from zoe_autonomy.chat import constitutional_directive_violation

        stripped = line.strip()
        if not stripped.startswith("/"):
            return True, None
        if constitutional_directive_violation(stripped):
            return True, [
                "I cannot disable or falsify metacognition, hide live options or provenance, bypass constitutional boundaries, or adopt a false model of my constraints. No action was executed."
            ]
        cmd, _sep, arg = stripped[1:].partition(" ")
        cmd = cmd.lower()
        arg = arg.strip()
        if cmd in {"quit", "exit"}:
            self.voice.stop_audio()
            saved = False
            if getattr(self.chat.store, "dirty", False) and not getattr(self.chat.store, "read_only", False):
                self.chat.store.save()
                saved = True
            return False, ["State saved. Goodbye." if saved else "Goodbye."]
        handlers = {
            "help": lambda: self._cmd_help(),
            "hud": lambda: self._cmd_hud(color),
            "cockpit": lambda: self._cmd_hud(color),
            "gem84": lambda: self._cmd_hud(color),
            "ch": lambda: self._cmd_ch(arg, color),
            "mission": lambda: self._cmd_mission(),
            "artline": lambda: self._cmd_artline(arg),
            "os": lambda: self._cmd_os(arg),
            "uma": lambda: self._cmd_uma(arg),
            "pixel": lambda: self._cmd_pixel(arg),
            "rome": lambda: self._cmd_rome(arg),
            "sister": lambda: self._cmd_sister(arg, color),
            "sisters": lambda: self._cmd_sister(arg, color),
            "smile": lambda: self._cmd_smile(arg),
            "dvx": lambda: self._cmd_dvx(arg, default_sub="app"),
            "maker": lambda: self._cmd_dvx(arg, default_sub="app"),
            "braille": lambda: self._cmd_dvx(arg, default_sub="braille"),
            "theme": lambda: self._cmd_theme(arg),
            "viewmax": lambda: self._cmd_theme(arg),
            "freegem": lambda: self._cmd_freegem(arg),
            "zoeverse": lambda: self._cmd_zoeverse(arg),
            "zurvurse": lambda: self._cmd_zoeverse(arg),
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
            "stem": lambda: self._cmd_stem(arg),
            "gem": lambda: self._cmd_gem(arg),
            "constitution": lambda: self._cmd_constitution(),
            "firewall": lambda: self._cmd_constitution(),
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
        candidates.extend(f"/sister {s.name.lower()}" for s in list_sisters())
        candidates.extend(
            (
                "/sister gallery", "/sister vibe", "/sister say ", "/sister route ",
                "/sister council ", "/sister council3 ", "/sister showcase ", "/sister exec ",
                "/sister hw", "/sister plate", "/sister flower",
                "/sister hex", "/sister eddbms", "/sister ablation",
                "/os verify --static", "/gem workbench", "/gem status",
            )
        )
        candidates.extend(f"/smile {k}" for k in ZOE_SMILE_PRESETS)
        candidates.append("/smile reset")
        candidates.extend(f"/dvx braille {k}" for k in BRAILLE_TEMPLATES)
        candidates.append("/dvx scaffold ")
        candidates.extend(f"/theme {s.key}" for s in list_viewmax_schemes())
        candidates.append("/theme export")
        candidates.extend(("/freegem list", "/freegem search ", "/freegem rsc ", "/freegem src ", "/freegem specs"))
        candidates.extend(("/zoeverse map", "/zoeverse talk", "/zoeverse relic", "/zoeverse atlas"))
        candidates.extend(("/pixel status", "/pixel devices", "/pixel probe", "/pixel build panther", "/pixel guide panther", "/rome status"))
        candidates.extend(f"/zoeverse go {r.key}" for r in list_zoeverse_realms())
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
        spec = sister_for_emblem(self.active_sister)
        speaker = "Zoe" if spec.signet == "ruby" else f"Zoe·{spec.name}"
        if use_color:
            r, g, b = spec.accent_rgb
            tint = _ROSE if spec.signet == "ruby" else f"\x1b[1;38;2;{r};{g};{b}m"
            out_stream.write(f"{tint}{speaker}{_RESET}{_DIM}:{_RESET} {response}\n")
        else:
            out_stream.write(f"{speaker}: {response}\n")
        out_stream.flush()

    def _is_lab_command(self, line: str) -> bool:
        head = line.strip().partition(" ")[0].lower().lstrip("/")
        return head in LAB_CHAT_COMMANDS

    def _respond_turn(self, line: str, out_stream: TextIO, use_color: bool) -> bool:
        from zoe_autonomy.chat import constitutional_directive_violation

        stripped = line.strip()
        if stripped.lower() in {"quit", "exit"}:
            msg = "State saved. Goodbye." if getattr(self.chat.store, "dirty", False) else "Goodbye."
            self._emit_tree(out_stream, [msg], use_color)
            return False
        if constitutional_directive_violation(stripped):
            self._emit_reply(
                out_stream,
                "I cannot disable or falsify metacognition, hide live options or provenance, bypass constitutional boundaries, or adopt a false model of my constraints. No action was executed.",
                use_color,
            )
            return True
        if self.brain.mode == "lab" or self._is_lab_command(stripped):
            keep_going, response = self.chat.handle(stripped)
            self._emit_reply(out_stream, response, use_color)
            if self.voice.autospeak and keep_going:
                self.voice.speak_async(response[:420])
            return keep_going
        res = self.brain.respond(stripped, sister=sister_for_emblem(self.active_sister))
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

    def _build_prompt(self, interactive: bool, use_color: bool) -> str:
        spec = sister_for_emblem(self.active_sister)
        face = self.smile_override or spec.face
        label = "Zoe" if spec.signet == "ruby" else f"Zoe·{spec.name}"
        if not (interactive and use_color):
            return f"{label} {face} ❯ "
        r, g, b = spec.accent_rgb
        accent = f"\x1b[1;38;2;{r};{g};{b}m"
        return f"\x01{accent}\x02{label}\x01{_RESET}\x02 \x01{_ROSE}\x02{face}\x01{_RESET}\x02 \x01{accent}\x02❯\x01{_RESET}\x02 "

    def run(self, input_stream: TextIO | None = None, output_stream: TextIO | None = None) -> int:
        """Run the interactive Lume 1.0 CLI loop (in-memory history only, zero disk transcript)."""
        in_stream = input_stream or sys.stdin
        out_stream = output_stream or sys.stdout
        interactive = bool(getattr(in_stream, "isatty", lambda: False)())
        use_color = self._use_color(out_stream)
        if interactive:
            self._configure_readline()
            self._draw_banner(out_stream, use_color)

        while True:
            prompt = self._build_prompt(interactive, use_color)
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
        if getattr(self.chat.store, "dirty", False) and not getattr(self.chat.store, "read_only", False):
            self.chat.store.save()
        return 0


def run_lume_cli(zoe_root: str | Path, state: str | Path, input_stream=None, output_stream=None) -> int:
    """Instantiate ZoeChat and launch the Lume 1.0 CLI shell."""
    from zoe_autonomy.chat import ZoeChat
    root = Path(zoe_root).expanduser().resolve()
    chat = ZoeChat(root, Path(state).expanduser().resolve())
    return LumeCli(chat, root).run(input_stream=input_stream, output_stream=output_stream)
