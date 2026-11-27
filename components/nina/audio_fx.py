"""Audio equalizer, creative effect presets, and voice profile persistence for Nina."""

from __future__ import annotations

import copy
import json
import re
import subprocess
from pathlib import Path
from typing import Any

REPO_PROFILES_FILE = Path(__file__).resolve().parent / "voice_profiles.json"
USER_PROFILES_FILE = Path.home() / ".config" / "nina" / "voice_profiles.json"

EQ_BANDS: list[dict[str, Any]] = [
    {"key": "warmth",   "freq": 120,  "q": 1.0, "label": "Warmth",   "hz_label": "120 Hz"},
    {"key": "body",     "freq": 350,  "q": 1.0, "label": "Body",     "hz_label": "350 Hz"},
    {"key": "mid",      "freq": 1200, "q": 1.0, "label": "Mid",      "hz_label": "1.2 kHz"},
    {"key": "presence", "freq": 3200, "q": 1.1, "label": "Presence", "hz_label": "3.2 kHz"},
    {"key": "air",      "freq": 9000, "q": 0.9, "label": "Air",      "hz_label": "9 kHz"},
]

DEFAULT_EQ: dict[str, float] = {b["key"]: 0.0 for b in EQ_BANDS}

MALE_SHORTCUTS: dict[str, str] = {
    "guy":     "en-US-GuyNeural",
    "ryan":    "en-GB-RyanNeural",
    "william": "en-AU-WilliamNeural",
    "connor":  "en-IE-ConnorNeural",
    "alex":    "en-US-AndrewNeural",
    "brian":   "en-US-BrianNeural",
}


def clamp(val: float, lo: float, hi: float) -> float:
    """Clamp numeric value cleanly between lo and hi."""
    return max(lo, min(hi, val))


def format_pitch(hz: int | float) -> str:
    """Format an integer pitch offset like '-4Hz' or '+0Hz'."""
    val = int(round(hz))
    return f"{val:+d}Hz"


def format_rate(pct: int | float) -> str:
    """Format an integer speed offset like '-4%' or '+15%'."""
    val = int(round(pct))
    return f"{val:+d}%"


def format_volume(pct: int | float) -> str:
    """Format an integer volume offset like '+0%' or '+10%'."""
    val = int(round(pct))
    return f"{val:+d}%"


def parse_signed_int(raw: str | int | float, unit: str = "") -> int:
    """Parse strings like '-4Hz', '+15%', '0', or integers into a signed int."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return int(round(raw))
    if not isinstance(raw, str):
        raise ValueError(f"Invalid value: {raw!r}")
    s = raw.strip()
    if unit:
        s = re.sub(rf"{re.escape(unit)}$", "", s, flags=re.IGNORECASE).strip()
    s = re.sub(r"(?:hz|%)$", "", s, flags=re.IGNORECASE).strip()
    if not re.fullmatch(r"[+-]?\d+", s):
        raise ValueError(f"Expected signed integer (e.g. +0{unit}, -4{unit}), got {raw!r}")
    return int(s)


def normalize_eq(eq: dict[str, Any] | None) -> dict[str, float]:
    """Return a clean 5-band EQ dict clamped to [-12.0, 12.0] dB."""
    out = dict(DEFAULT_EQ)
    if not isinstance(eq, dict):
        return out
    for key in DEFAULT_EQ:
        if key in eq:
            out[key] = round(clamp(float(eq[key]), -12.0, 12.0), 2)
    return out


def parse_eq_arg(raw: str, base_eq: dict[str, float] | None = None) -> dict[str, float]:
    """Parse a 5-band EQ spec from '1.5,-1,0,2,3.5' or 'warmth=2,air=3.5'."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("EQ specification cannot be empty.")
    text = raw.strip()
    band_keys = [b["key"] for b in EQ_BANDS]

    if "=" in text:
        out = normalize_eq(base_eq)
        for token in text.split(","):
            part = token.strip()
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"Invalid key=value token in EQ spec: {part!r}")
            k, v = part.split("=", 1)
            key = k.strip().lower()
            if key not in DEFAULT_EQ:
                raise ValueError(f"Unknown EQ band {key!r}. Valid bands: {', '.join(band_keys)}")
            out[key] = round(clamp(float(v.strip()), -12.0, 12.0), 2)
        return out

    parts = [p.strip() for p in text.split(",")]
    if len(parts) != len(band_keys):
        raise ValueError(
            f"Positional EQ spec must have {len(band_keys)} comma-separated numbers "
            f"({', '.join(band_keys)}), got {len(parts)}"
        )
    out = {}
    for key, val in zip(band_keys, parts):
        out[key] = round(clamp(float(val), -12.0, 12.0), 2)
    return out


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override dictionary into a deep copy of base."""
    result = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


class ProfileStore:
    """Loads repo voice profiles and layers user customizations on top."""

    def __init__(
        self,
        repo_path: str | Path = REPO_PROFILES_FILE,
        user_path: str | Path = USER_PROFILES_FILE,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.user_path = Path(user_path)
        self._repo_data: dict[str, Any] = {}
        self._user_data: dict[str, Any] = {}
        self._data: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        """Reload repository defaults and merge user overrides cleanly."""
        if self.repo_path.exists():
            self._repo_data = json.loads(self.repo_path.read_text(encoding="utf-8"))
        else:
            self._repo_data = {
                "version": 1,
                "default_voice": "zoe",
                "preferred_voice_id": "en-US-AvaMultilingualNeural",
                "eq_bands": copy.deepcopy(EQ_BANDS),
                "eq_curves": {"flat": {"label": "Flat (0 dB)", "eq": dict(DEFAULT_EQ)}},
                "effect_presets": {
                    "flat": {"label": "Clean / Dry", "description": "Unprocessed audio", "filters": []}
                },
                "female_profiles": {},
                "custom_profiles": {},
            }

        self._user_data = {}
        if self.user_path.exists():
            try:
                loaded = json.loads(self.user_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self._user_data = loaded
            except Exception:
                self._user_data = {}

        self._data = _deep_merge(self._repo_data, self._user_data)

    def _save_user_data(self) -> Path:
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_path.write_text(
            json.dumps(self._user_data, indent=2) + "\n",
            encoding="utf-8",
        )
        self._data = _deep_merge(self._repo_data, self._user_data)
        return self.user_path

    @property
    def default_voice(self) -> str:
        return str(self._data.get("default_voice", "zoe"))

    @property
    def preferred_voice_id(self) -> str:
        return str(self._data.get("preferred_voice_id", "ZoeNatasha-3D"))

    @property
    def eq_bands(self) -> list[dict[str, Any]]:
        bands = self._data.get("eq_bands")
        return copy.deepcopy(bands) if isinstance(bands, list) and bands else copy.deepcopy(EQ_BANDS)

    def list_female_profiles(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._data.get("female_profiles", {}))

    def list_effect_presets(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._data.get("effect_presets", {}))

    def list_eq_curves(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._data.get("eq_curves", {}))

    def list_custom_profiles(self) -> dict[str, dict[str, Any]]:
        return copy.deepcopy(self._data.get("custom_profiles", {}))

    def get_voice_shortcuts(self) -> dict[str, str]:
        """Build full shortcut -> voice_id map from calibrated profiles and male aliases."""
        shortcuts = dict(MALE_SHORTCUTS)
        for vid, cfg in self._data.get("female_profiles", {}).items():
            sc = cfg.get("shortcut")
            if sc:
                shortcuts[str(sc).lower()] = vid
        shortcuts.setdefault("zoe", self.preferred_voice_id)
        shortcuts.setdefault("ava-ml", "en-US-AvaMultilingualNeural")
        return shortcuts

    def get_display_names(self) -> dict[str, str]:
        """Return mapping of ShortName or ShortName fragment -> friendly GUI label."""
        names: dict[str, str] = {"AndrewNeural": "Alex"}
        for vid, cfg in self._data.get("female_profiles", {}).items():
            dn = cfg.get("display_name")
            if dn:
                names[vid] = str(dn)
                frag = vid.split("-")[-1]
                if vid == "en-IE-EmilyNeural":
                    names[frag] = str(dn)
        return names

    def _normalize_profile_dict(
        self, voice_id: str, raw: dict[str, Any] | None, *, is_tuned: bool
    ) -> dict[str, Any]:
        src = raw or {}
        return {
            "voice_id": voice_id,
            "pitch": int(round(clamp(float(src.get("pitch", 0)), -50, 50))),
            "rate": int(round(clamp(float(src.get("rate", 0)), -60, 120))),
            "volume": int(round(clamp(float(src.get("volume", 0)), -50, 50))),
            "eq": normalize_eq(src.get("eq")),
            "effect": str(src.get("effect", "flat" if not is_tuned else "zoe_velvet")),
            "tagline": str(src.get("tagline", src.get("description", ""))),
            "display_name": src.get("display_name"),
            "is_tuned_default": is_tuned,
        }

    def get_repo_voice_default(self, voice_id: str) -> dict[str, Any]:
        """Return the unmodified repo default for a voice (flat if not in female_profiles)."""
        fem = self._repo_data.get("female_profiles", {})
        if voice_id in fem:
            return self._normalize_profile_dict(voice_id, fem[voice_id], is_tuned=True)
        return self._normalize_profile_dict(voice_id, None, is_tuned=False)

    def get_voice_profile(self, voice_id: str, tuned: bool = True) -> dict[str, Any]:
        """Return effective merged profile (repo + user override), or raw flat settings."""
        if not tuned:
            return {
                "voice_id": voice_id,
                "pitch": 0,
                "rate": 0,
                "volume": 0,
                "eq": dict(DEFAULT_EQ),
                "effect": "flat",
                "tagline": "Raw unprocessed voice",
                "display_name": None,
                "is_tuned_default": False,
            }
        fem = self._data.get("female_profiles", {})
        overrides = self._data.get("voice_overrides", {})
        base = copy.deepcopy(fem.get(voice_id, {}))
        is_tuned = voice_id in fem or voice_id in overrides
        if voice_id in overrides and isinstance(overrides[voice_id], dict):
            base = _deep_merge(base, overrides[voice_id])
        if not base:
            return self._normalize_profile_dict(voice_id, None, is_tuned=False)
        return self._normalize_profile_dict(voice_id, base, is_tuned=is_tuned)

    def get_custom_profile(self, name: str) -> dict[str, Any] | None:
        """Case-insensitive lookup in custom_profiles."""
        if not name:
            return None
        target = name.strip().lower()
        for k, v in self._data.get("custom_profiles", {}).items():
            if k.lower() == target:
                out = copy.deepcopy(v)
                out["name"] = k
                out["eq"] = normalize_eq(out.get("eq"))
                return out
        return None

    def save_default_voice(self, voice_id: str, shortcut: str | None = None) -> Path:
        """Persist the user's chosen default voice in the user config file."""
        self._user_data["preferred_voice_id"] = str(voice_id)
        if shortcut:
            self._user_data["default_voice"] = str(shortcut)
        else:
            # Find shortcut if this voice has one, else store voice_id directly
            found = None
            for sc, vid in self.get_voice_shortcuts().items():
                if vid == voice_id:
                    found = sc
                    break
            self._user_data["default_voice"] = found or str(voice_id)
        return self._save_user_data()

    def save_voice_override(self, voice_id: str, settings: dict[str, Any]) -> Path:
        """Persist fine-tuning overrides for a voice into the user config file."""
        overrides = self._user_data.setdefault("voice_overrides", {})
        overrides[voice_id] = {
            "pitch": int(round(clamp(float(settings.get("pitch", 0)), -50, 50))),
            "rate": int(round(clamp(float(settings.get("rate", 0)), -60, 120))),
            "volume": int(round(clamp(float(settings.get("volume", 0)), -50, 50))),
            "eq": normalize_eq(settings.get("eq")),
            "effect": str(settings.get("effect", "flat")),
        }
        return self._save_user_data()

    def reset_voice_override(self, voice_id: str) -> None:
        """Remove any user override for voice_id so repo defaults apply again."""
        overrides = self._user_data.get("voice_overrides")
        if isinstance(overrides, dict) and voice_id in overrides:
            del overrides[voice_id]
            if not overrides:
                del self._user_data["voice_overrides"]
            self._save_user_data()

    def save_custom_profile(self, name: str, settings: dict[str, Any]) -> Path:
        """Save a named voice + EQ + effect recipe into user custom_profiles."""
        clean_name = re.sub(r"\s+", "_", name.strip())
        if not clean_name:
            raise ValueError("Profile name cannot be empty.")
        customs = self._user_data.setdefault("custom_profiles", {})
        customs[clean_name] = {
            "voice_id": str(settings.get("voice_id", self.preferred_voice_id)),
            "pitch": int(round(clamp(float(settings.get("pitch", 0)), -50, 50))),
            "rate": int(round(clamp(float(settings.get("rate", 0)), -60, 120))),
            "volume": int(round(clamp(float(settings.get("volume", 0)), -50, 50))),
            "eq": normalize_eq(settings.get("eq")),
            "effect": str(settings.get("effect", "zoe_velvet")),
            "description": str(settings.get("description", f"Custom profile '{clean_name}'")),
        }
        return self._save_user_data()

    def save_eq_curve(self, name: str, label: str, eq: dict[str, float]) -> Path:
        """Save a reusable 5-band EQ curve into user eq_curves."""
        clean_name = re.sub(r"\s+", "_", name.strip().lower())
        if not clean_name:
            raise ValueError("Curve name cannot be empty.")
        curves = self._user_data.setdefault("eq_curves", {})
        curves[clean_name] = {
            "label": label.strip() or clean_name,
            "eq": normalize_eq(eq),
        }
        return self._save_user_data()

    def export_profile(self, path: str | Path, payload: dict[str, Any]) -> None:
        """Export a single voice/EQ profile as clean shareable JSON."""
        out_path = Path(path)
        clean = {
            "voice_id": str(payload.get("voice_id", self.preferred_voice_id)),
            "pitch": int(round(clamp(float(payload.get("pitch", 0)), -50, 50))),
            "rate": int(round(clamp(float(payload.get("rate", 0)), -60, 120))),
            "volume": int(round(clamp(float(payload.get("volume", 0)), -50, 50))),
            "eq": normalize_eq(payload.get("eq")),
            "effect": str(payload.get("effect", "zoe_velvet")),
        }
        if payload.get("name"):
            clean["name"] = str(payload["name"])
        if payload.get("description"):
            clean["description"] = str(payload["description"])
        out_path.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")

    def import_profile(self, path: str | Path) -> dict[str, Any]:
        """Load and validate an exported JSON profile."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Profile JSON must be an object.")
        return {
            "voice_id": str(raw.get("voice_id", self.preferred_voice_id)),
            "pitch": int(round(clamp(float(raw.get("pitch", 0)), -50, 50))),
            "rate": int(round(clamp(float(raw.get("rate", 0)), -60, 120))),
            "volume": int(round(clamp(float(raw.get("volume", 0)), -50, 50))),
            "eq": normalize_eq(raw.get("eq")),
            "effect": str(raw.get("effect", "flat")),
            "name": raw.get("name"),
            "description": raw.get("description", ""),
        }


def build_filtergraph(
    eq: dict[str, float] | None,
    effect_key: str = "flat",
    store: ProfileStore | None = None,
    extra_filters: list[str] | None = None,
) -> str:
    """Build an mpv/ffmpeg lavfi filtergraph string for EQ + creative effects."""
    active_store = store or ProfileStore()
    bands = active_store.eq_bands
    clean_eq = normalize_eq(eq)

    filters: list[str] = []
    has_positive_boost = False
    for band in bands:
        key = band["key"]
        gain = clean_eq.get(key, 0.0)
        if abs(gain) >= 0.05:
            if gain > 0:
                has_positive_boost = True
            filters.append(
                f"equalizer=f={band['freq']}:t=q:w={band['q']}:g={gain:.2f}"
            )

    presets = active_store.list_effect_presets()
    preset = presets.get(effect_key) or presets.get("flat") or {}
    for flt in preset.get("filters", []):
        if flt:
            filters.append(flt)

    if extra_filters:
        for flt in extra_filters:
            if flt:
                filters.append(flt)

    if has_positive_boost and not any(f.startswith("alimiter") for f in filters):
        filters.append("alimiter=limit=0.95")

    return ",".join(filters)


def mpv_args(filtergraph: str = "") -> list[str]:
    """Return mpv command arguments with optional lavfi EQ/effect chain."""
    args = ["mpv", "--no-video", "--really-quiet", "--audio-display=no"]
    if filtergraph:
        args.append(f"--af=lavfi=[{filtergraph}]")
    args.append("-")
    return args


def build_trust_lume_cue(
    output_trust: float,
    *,
    base_eq: dict[str, float] | None = None,
    effect_key: str = "flat",
    store: ProfileStore | None = None,
) -> dict[str, Any]:
    """Encode continuous output_trust [0.0, 1.0] into Lume 1.0 voice audio cues.

    High trust -> dry, full stereo clarity.
    Low trust  -> narrower stereo image, reduced volume, and echo/reverb haze
                  so epistemic uncertainty is directly audible without muting.
    """
    trust = clamp(float(output_trust), 0.0, 1.0)
    uncertainty = 1.0 - trust
    delay_ms = round(30.0 + uncertainty * 120.0, 2)
    decay = round(0.1 + uncertainty * 0.3, 4)
    iterations = 2 + int(uncertainty * 4)
    stereo_width = round(0.3 + trust * 0.7, 4)
    gain_scale = round(0.45 + 0.55 * trust, 4)
    extra_m = round(0.25 + trust * 0.95, 3)

    trust_filters: list[str] = [
        f"volume={gain_scale:.3f}",
        f"extrastereo=m={extra_m:.3f}",
    ]
    if trust < 0.75:
        trust_filters.append(f"aecho=0.8:0.88:{int(round(delay_ms))}:{decay:.3f}")

    fg = build_filtergraph(
        eq=base_eq,
        effect_key=effect_key,
        store=store,
        extra_filters=trust_filters,
    )
    clarity = (
        "clear_and_confident"
        if trust > 0.7
        else "hazy_and_uncertain"
        if trust < 0.4
        else "moderate_clarity"
    )
    return {
        "output_trust": round(trust, 4),
        "clarity": clarity,
        "gain_scale": gain_scale,
        "stereo_width": stereo_width,
        "reverb": {
            "delay_ms": delay_ms,
            "decay": decay,
            "iterations": iterations,
        },
        "trust_filters": trust_filters,
        "filtergraph": fg,
        "mpv_args": mpv_args(fg),
    }


def apply_ffmpeg_filter(audio_bytes: bytes, filtergraph: str, output_path: str | Path) -> bool:
    """Process MP3 or WAV audio bytes through ffmpeg with filtergraph and write output_path."""
    out = Path(output_path)
    if not filtergraph and out.suffix.lower() != ".mp3":
        out.write_bytes(audio_bytes)
        return True
    try:
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", "pipe:0",
        ]
        if filtergraph:
            cmd.extend(["-af", filtergraph])
        if out.suffix.lower() == ".wav":
            cmd.extend(["-c:a", "pcm_s16le", str(out)])
        else:
            cmd.extend(["-c:a", "libmp3lame", "-q:a", "2", str(out)])
        proc = subprocess.run(cmd, input=audio_bytes, capture_output=True)
        return proc.returncode == 0
    except FileNotFoundError:
        return False
