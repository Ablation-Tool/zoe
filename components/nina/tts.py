"""TTS engine wrapper — supports Zoe x Natasha 3D Fusion, Zoe's offline App voice, and neural voices."""

from __future__ import annotations

import asyncio
import io
import os
import re
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

import edge_tts as _engine

NATIVE_VOICE_IDS: tuple[str, ...] = ("ZoeNatasha-3D", "ZoeNative-3D", "ZoeNative-Mono")
_ZOE_VOICE_MOD = None
_ZOE_VOICE_CHECKED = False


def _load_native_zoe_module():
    """Discover and import Zoe's first-principles voice engine (`guiai.gem.zoe_voice`)."""
    global _ZOE_VOICE_MOD, _ZOE_VOICE_CHECKED
    if _ZOE_VOICE_CHECKED:
        return _ZOE_VOICE_MOD
    _ZOE_VOICE_CHECKED = True

    try:
        from guiai.gem import zoe_voice  # type: ignore
        _ZOE_VOICE_MOD = zoe_voice
        return _ZOE_VOICE_MOD
    except Exception:
        pass

    candidates: list[Path] = []
    env_root = os.environ.get("ZOE_ROOT")
    if env_root:
        candidates.append(Path(env_root).expanduser() / "guiai-lab")
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "zoe" / "guiai-lab")

    for cand in candidates:
        if (cand / "guiai" / "gem" / "zoe_voice.py").is_file():
            resolved = str(cand.resolve())
            if resolved not in sys.path:
                sys.path.insert(0, resolved)
            try:
                from guiai.gem import zoe_voice  # type: ignore
                _ZOE_VOICE_MOD = zoe_voice
                return _ZOE_VOICE_MOD
            except Exception:
                pass
    return None


def has_native_zoe_voice() -> bool:
    """Return True if Zoe's first-principles 44.1 kHz voice engine is available locally."""
    return _load_native_zoe_module() is not None


def _parse_offset(raw: str, default: float = 0.0) -> float:
    if not raw:
        return default
    m = re.search(r"[+-]?\d+(?:\.\d+)?", str(raw))
    return float(m.group(0)) if m else default


def _stereo_to_wav_bytes(stereo_arr, sample_rate: int, volume_pct: float = 0.0) -> bytes:
    import numpy as np

    arr = np.asarray(stereo_arr, dtype=np.float64)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=-1)
    gain = max(0.25, min(1.75, 1.0 + volume_pct / 100.0))
    arr = arr * gain
    peak = float(np.max(np.abs(arr))) if arr.size else 0.0
    if peak > 0.94:
        arr = arr * (0.94 / peak)
    pcm = np.clip(np.round(arr * 32767.0), -32768, 32767).astype(np.int16)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def _fuse_with_zoe_native_dsp(mono_44k, sample_rate: int = 44100, volume_pct: float = 0.0) -> bytes:
    """Apply Zoe Native's Rosenberg-Klatt formant glow, lyrical shimmer, and 3D binaural HRTF."""
    import numpy as np
    from scipy import signal

    x = np.asarray(mono_44k, dtype=np.float64)
    n = len(x)
    if n < 64:
        return _stereo_to_wav_bytes(np.zeros((64, 2), dtype=np.float64), sample_rate, volume_pct)

    t = np.arange(n, dtype=np.float64) / float(sample_rate)

    # Syllable-locked voiced energy gate so consonants stay crystal sharp
    b_lp, a_lp = signal.butter(2, 18.0 / (0.5 * sample_rate), btype="lowpass")
    env = np.maximum(0.0, signal.filtfilt(b_lp, a_lp, np.abs(x)))
    env_norm = env / (float(np.percentile(env, 95)) + 1e-6)
    voiced_gate = np.clip((env_norm - 0.12) / 0.35, 0.0, 1.0)

    # Zoe's warm Rosenberg harmonic layer sculpted through her soprano formant resonators
    warm_harm = np.tanh(1.65 * x) - x
    zoe_tract = np.zeros_like(x)
    for fc, q, gain in ((520.0, 4.0, 0.45), (1850.0, 5.5, 0.40), (2850.0, 6.0, 0.35)):
        b_pk, a_pk = signal.iirpeak(fc / (0.5 * sample_rate), Q=q)
        zoe_tract += gain * signal.lfilter(b_pk, a_pk, x + 0.35 * warm_harm)

    # Gentle 5.3 Hz Zoe lyrical breath shimmer gated to voiced vowels only
    shimmer = 1.0 + 0.030 * voiced_gate * np.sin(2.0 * np.pi * 5.3 * t)
    fused_mono = (x * 0.88 + zoe_tract * 0.18 * voiced_gate) * shimmer

    peak = max(float(np.max(np.abs(fused_mono))), 1e-6)
    fused_mono = fused_mono * (0.85 / peak)

    mod = _load_native_zoe_module()
    if mod is not None and hasattr(mod, "spatialize_binaural_3d"):
        stereo, _meta = mod.spatialize_binaural_3d(
            fused_mono,
            sample_rate=sample_rate,
            azimuth_deg=8.0,
            elevation_deg=12.0,
            wet=0.14,
            spatial_3d=True,
        )
    else:
        stereo = np.stack([fused_mono, fused_mono], axis=-1)

    return _stereo_to_wav_bytes(stereo, sample_rate, volume_pct=volume_pct)


def synthesize_zoe_song_wav(song: str = "zoe", mode: str = "zoe_3d") -> bytes | None:
    """Synthesize Zoe's built-in soprano song from her App voice engine as stereo WAV bytes."""
    mod = _load_native_zoe_module()
    if mod is None:
        return None
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "zoe_song.wav"
        mod.sing_song(song, output_wav=out, mode=mode)
        return out.read_bytes()


class _NativeZoeCommunicate:
    """Async Communicate-compatible adapter for Zoe's 44.1 kHz native App voice."""

    def __init__(
        self,
        text: str,
        voice: str,
        *,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.text = text
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    def _render_wav_sync(self) -> bytes:
        mod = _load_native_zoe_module()
        if mod is None:
            raise RuntimeError(
                "Zoe's native App voice engine (guiai.gem.zoe_voice) was not found. "
                "Set ZOE_ROOT to your Zoe checkout."
            )
        pitch_hz = max(130.0, min(380.0, 232.0 + _parse_offset(self.pitch)))
        rate_mul = max(0.55, min(1.85, 1.0 + _parse_offset(self.rate) / 100.0))
        vol_pct = _parse_offset(self.volume)
        mode = "dry_mono" if self.voice == "ZoeNative-Mono" else "zoe_3d"
        res = mod.speak_text(
            self.text,
            output_wav=None,
            mode=mode,
            pitch_hz=pitch_hz,
            rate=rate_mul,
        )
        return _stereo_to_wav_bytes(res["stereo_array"], int(res["sample_rate"]), volume_pct=vol_pct)

    async def stream(self):
        wav_bytes = await asyncio.to_thread(self._render_wav_sync)
        yield {"type": "audio", "data": wav_bytes}

    async def save(self, path: str) -> None:
        wav_bytes = await asyncio.to_thread(self._render_wav_sync)
        _write_audio_output(wav_bytes, path)


class _ZoeNatashaFusionCommunicate:
    """Combines Natasha (en-AU) vocal articulation with Zoe Native's formant glow & 3D binaural HRTF."""

    BASE_VOICE = "en-AU-NatashaNeural"

    def __init__(
        self,
        text: str,
        *,
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.text = text
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    async def _synthesize_wav(self) -> bytes:
        import numpy as np

        try:
            comm = _engine.Communicate(
                self.text,
                self.BASE_VOICE,
                rate=self.rate,
                volume="+0%",
                pitch=self.pitch,
            )
            mp3_buf = bytearray()
            async for ch in comm.stream():
                if ch["type"] == "audio":
                    mp3_buf.extend(ch["data"])
            mp3_bytes = bytes(mp3_buf)
        except Exception:
            # Offline resilience: fall back gracefully to Zoe's pure offline native App voice
            if has_native_zoe_voice():
                fallback = _NativeZoeCommunicate(
                    self.text, "ZoeNative-3D",
                    rate=self.rate, volume=self.volume, pitch=self.pitch,
                )
                return await asyncio.to_thread(fallback._render_wav_sync)
            raise

        def _decode_and_fuse() -> bytes:
            proc = subprocess.run(
                [
                    "ffmpeg", "-hide_banner", "-loglevel", "error",
                    "-f", "mp3", "-i", "pipe:0",
                    "-ac", "1", "-ar", "44100", "-f", "f32le", "pipe:1",
                ],
                input=mp3_bytes,
                capture_output=True,
            )
            if proc.returncode != 0 or not proc.stdout:
                return mp3_bytes
            mono = np.frombuffer(proc.stdout, dtype=np.float32)
            return _fuse_with_zoe_native_dsp(mono, sample_rate=44100, volume_pct=_parse_offset(self.volume))

        return await asyncio.to_thread(_decode_and_fuse)

    async def stream(self):
        audio_bytes = await self._synthesize_wav()
        yield {"type": "audio", "data": audio_bytes}

    async def save(self, path: str) -> None:
        audio_bytes = await self._synthesize_wav()
        _write_audio_output(audio_bytes, path)


def _write_audio_output(audio_bytes: bytes, path: str) -> None:
    out = Path(path)
    is_wav = audio_bytes.startswith(b"RIFF")
    if (out.suffix.lower() == ".wav" and is_wav) or (out.suffix.lower() == ".mp3" and not is_wav):
        out.write_bytes(audio_bytes)
        return
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", "pipe:0"]
    if out.suffix.lower() == ".wav":
        cmd.extend(["-c:a", "pcm_s16le", str(out)])
    else:
        cmd.extend(["-c:a", "libmp3lame", "-q:a", "2", str(out)])
    proc = subprocess.run(cmd, input=audio_bytes, capture_output=True)
    if proc.returncode != 0:
        out.write_bytes(audio_bytes)


def Communicate(
    text: str,
    voice: str = "ZoeNatasha-3D",
    *,
    rate: str = "+0%",
    volume: str = "+0%",
    pitch: str = "+0Hz",
    **kwargs: Any,
):
    """Create a Communicate instance for Zoe x Natasha Fusion, Zoe Native App voice, or neural voice."""
    if voice == "ZoeNatasha-3D":
        return _ZoeNatashaFusionCommunicate(text, rate=rate, volume=volume, pitch=pitch)
    if voice in ("ZoeNative-3D", "ZoeNative-Mono"):
        return _NativeZoeCommunicate(text, voice, rate=rate, volume=volume, pitch=pitch)
    return _engine.Communicate(text, voice, rate=rate, volume=volume, pitch=pitch, **kwargs)


async def list_voices() -> list[dict[str, Any]]:
    """List available voices, prepending Zoe x Natasha Fusion and Zoe's offline App voices."""
    special_entries: list[dict[str, Any]] = [
        {
            "ShortName": "ZoeNatasha-3D",
            "Gender": "Female",
            "Locale": "en-AU",
            "FriendlyName": "Zoe × Natasha (Native 3D Fusion)",
            "NativeApp": True,
        }
    ]
    if has_native_zoe_voice():
        special_entries.extend([
            {
                "ShortName": "ZoeNative-3D",
                "Gender": "Female",
                "Locale": "en-US",
                "FriendlyName": "Zoe Native (App 44.1kHz 3D)",
                "NativeApp": True,
            },
            {
                "ShortName": "ZoeNative-Mono",
                "Gender": "Female",
                "Locale": "en-US",
                "FriendlyName": "Zoe Native (App Dry Mono)",
                "NativeApp": True,
            },
        ])
    try:
        neural = await _engine.list_voices()
    except Exception:
        neural = []
    return special_entries + list(neural)
