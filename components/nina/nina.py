#!/usr/bin/env python3
"""nina — open source neural text-to-speech for Linux."""

import argparse
import asyncio
import subprocess
import sys

import audio_fx
import lume_header
import tts as _tts

_STORE = audio_fx.ProfileStore()
VOICE_SHORTCUTS = _STORE.get_voice_shortcuts()


async def stream_audio(
    text: str,
    voice_id: str,
    rate: str,
    pitch: str = "+0Hz",
    volume: str = "+0%",
    filtergraph: str = "",
) -> None:
    """Stream TTS audio directly to mpv with optional lavfi EQ/effects."""
    communicate = _tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
    proc = subprocess.Popen(
        audio_fx.mpv_args(filtergraph),
        stdin=subprocess.PIPE,
    )
    try:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio" and proc.stdin is not None:
                proc.stdin.write(chunk["data"])
        if proc.stdin is not None:
            proc.stdin.close()
        proc.wait()
    except (BrokenPipeError, KeyboardInterrupt):
        proc.terminate()


async def save_audio(
    text: str,
    voice_id: str,
    rate: str,
    path: str,
    pitch: str = "+0Hz",
    volume: str = "+0%",
    filtergraph: str = "",
) -> None:
    """Synthesize TTS audio and save to MP3, applying ffmpeg filters when active."""
    communicate = _tts.Communicate(text, voice_id, rate=rate, pitch=pitch, volume=volume)
    if not filtergraph:
        await communicate.save(path)
        return

    buf = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.extend(chunk["data"])
    raw_mp3 = bytes(buf)
    if not audio_fx.apply_ffmpeg_filter(raw_mp3, filtergraph, path):
        print(
            "nina: warning — ffmpeg unavailable or filter failed; saving dry TTS audio.",
            file=sys.stderr,
        )
        with open(path, "wb") as f:
            f.write(raw_mp3)


async def resolve_voice(
    name: str, store: audio_fx.ProfileStore | None = None
) -> tuple[str, dict | None]:
    """Resolve a custom profile, shortcut, or prefix to (voice_id, custom_profile_or_None)."""
    active_store = store or _STORE
    custom = active_store.get_custom_profile(name)
    if custom:
        return custom["voice_id"], custom

    shortcuts = active_store.get_voice_shortcuts()
    low = name.lower()
    if low in shortcuts:
        return shortcuts[low], None
    if name in shortcuts:
        return shortcuts[name], None
    if name in _tts.NATIVE_VOICE_IDS or "Neural" in name:
        return name, None

    all_voices = await _tts.list_voices()
    match = next(
        (v["ShortName"] for v in all_voices if v["ShortName"].lower().startswith(low)),
        None,
    )
    if match:
        return match, None
    print(f"nina: unknown voice '{name}'. Run 'nina --list' to see options.", file=sys.stderr)
    sys.exit(1)


def _print_female_profiles(store: audio_fx.ProfileStore) -> None:
    profiles = store.list_female_profiles()
    print(f"{'Shortcut':<12} {'Voice ID':<34} {'Pitch':>6} {'Rate':>6}  {'EQ [W,B,M,P,A]':<26}  {'Effect':<13}  Note")
    print("-" * 124)
    for vid, cfg in profiles.items():
        eq = audio_fx.normalize_eq(cfg.get("eq"))
        eq_str = ",".join(f"{eq[b['key']]:+.1f}" for b in store.eq_bands)
        sc = cfg.get("shortcut", "-")
        mark = "*" if sc == store.default_voice else " "
        pitch_s = audio_fx.format_pitch(cfg.get("pitch", 0))
        rate_s = audio_fx.format_rate(cfg.get("rate", 0))
        eff = cfg.get("effect", "flat")
        note = cfg.get("tagline", "")
        print(f"{mark}{sc:<11} {vid:<34} {pitch_s:>6} {rate_s:>6}  [{eq_str:<24}]  {eff:<13}  {note}")


def _print_effects(store: audio_fx.ProfileStore) -> None:
    print("Effect Presets:")
    for key, cfg in store.list_effect_presets().items():
        print(f"  {key:<16} {cfg.get('label', key):<24} — {cfg.get('description', '')}")

    print("\nEQ Curves:")
    for key, cfg in store.list_eq_curves().items():
        eq = audio_fx.normalize_eq(cfg.get("eq"))
        eq_str = ", ".join(f"{b['key']}={eq[b['key']]:+.1f}" for b in store.eq_bands)
        print(f"  {key:<16} {cfg.get('label', key):<24} ({eq_str})")

    customs = store.list_custom_profiles()
    if customs:
        print("\nCustom Profiles (usable with -v NAME):")
        for key, cfg in customs.items():
            print(
                f"  {key:<16} {cfg.get('voice_id', ''):<32} "
                f"effect={cfg.get('effect', 'flat')} — {cfg.get('description', '')}"
            )


async def main() -> None:
    store = audio_fx.ProfileStore()
    shortcuts = store.get_voice_shortcuts()

    p = argparse.ArgumentParser(
        prog="nina",
        description="nina — open source neural TTS for Linux",
    )
    p.add_argument("text", nargs="*", help="Text to read (omit to read from stdin)")
    p.add_argument(
        "-v", "--voice", default=store.default_voice, metavar="NAME",
        help=f"Voice shortcut, custom profile, or full ID. Shortcuts: {', '.join(shortcuts)}. Default: {store.default_voice}",
    )
    p.add_argument(
        "-r", "--rate", default=None, metavar="RATE",
        help="Speed override: +20%% faster, -10%% slower (default: voice's tuned pace)",
    )
    p.add_argument(
        "-p", "--pitch", default=None, metavar="PITCH",
        help="Pitch offset in Hz (e.g. -4Hz, +6Hz)",
    )
    p.add_argument(
        "--volume", default=None, metavar="VOL",
        help="Volume offset in %% (e.g. +10%%, -5%%)",
    )
    p.add_argument(
        "-e", "--effect", default=None, metavar="PRESET",
        help="Equalizer/audio effect preset (run --list-effects to see options)",
    )
    p.add_argument(
        "--eq", default=None, metavar="SPEC",
        help="Custom 5-band EQ in dB: '1.5,-1,0,2,3.5' or 'warmth=2,air=3'",
    )
    p.add_argument(
        "--raw", action="store_true",
        help="Disable voice fine-tuning, EQ, and audio effects completely",
    )
    p.add_argument("-o", "--output", metavar="FILE", help="Save to MP3 instead of playing")
    p.add_argument("-l", "--list", action="store_true", help="List all available voices")
    p.add_argument(
        "--list-female", action="store_true",
        help="List all 24 fine-tuned female English voice profiles",
    )
    p.add_argument(
        "--list-effects", action="store_true",
        help="List all effect presets, EQ curves, and custom profiles",
    )
    p.add_argument(
        "--save-profile", metavar="NAME", default=None,
        help="Save active voice + pitch + rate + EQ + effect as a reusable custom profile",
    )
    p.add_argument(
        "--tune-voice", action="store_true",
        help="Save active pitch + rate + volume + EQ + effect as your default tune for this voice",
    )
    p.add_argument(
        "--set-default", action="store_true",
        help="Save the selected voice as your personal default voice",
    )
    p.add_argument(
        "--header", "--version", action="store_true", dest="header",
        help="Show the Lume 1.0 header and exit (unless text is provided)",
    )
    p.add_argument(
        "--no-header", action="store_true",
        help="Suppress the Lume 1.0 header on listing and help output",
    )
    args = p.parse_args()

    def _maybe_header(force: bool = False) -> None:
        if force or (sys.stdout.isatty() and not args.no_header):
            pref = store.get_voice_profile(store.preferred_voice_id, tuned=True)
            lume_header.print_header(
                voice_line=f"Default Voice: {store.default_voice} · FX: {pref.get('effect', 'zoe_velvet')}"
            )

    if args.list:
        voices = await _tts.list_voices()
        for v in sorted(voices, key=lambda x: x["Locale"]):
            print(f"{v['ShortName']:<48} {v['Gender']:<8} {v['Locale']}")
        return

    if args.list_female:
        _maybe_header()
        _print_female_profiles(store)
        return

    if args.list_effects:
        _maybe_header()
        _print_effects(store)
        return

    if args.header and not args.text and sys.stdin.isatty():
        _maybe_header(force=True)
        return

    voice_id, custom_profile = await resolve_voice(args.voice, store)

    if args.raw:
        pitch_int = 0
        rate_int = 0
        volume_int = 0
        eq = dict(audio_fx.DEFAULT_EQ)
        effect = "flat"
    else:
        prof = custom_profile if custom_profile else store.get_voice_profile(voice_id, tuned=True)
        pitch_int = int(prof.get("pitch", 0))
        rate_int = int(prof.get("rate", 0))
        volume_int = int(prof.get("volume", 0))
        eq = audio_fx.normalize_eq(prof.get("eq"))
        effect = str(prof.get("effect", "flat"))

        if args.pitch is not None:
            try:
                pitch_int = audio_fx.parse_signed_int(args.pitch, "Hz")
            except ValueError as exc:
                p.error(str(exc))
        if args.volume is not None:
            try:
                volume_int = audio_fx.parse_signed_int(args.volume, "%")
            except ValueError as exc:
                p.error(str(exc))
        if args.effect is not None:
            presets = store.list_effect_presets()
            if args.effect not in presets:
                p.error(f"Unknown effect '{args.effect}'. Run 'nina --list-effects' to see options.")
            effect = args.effect
        if args.eq is not None:
            try:
                eq = audio_fx.parse_eq_arg(args.eq, base_eq=eq)
            except ValueError as exc:
                p.error(str(exc))

    if args.rate is not None:
        try:
            rate_int = audio_fx.parse_signed_int(args.rate, "%")
        except ValueError as exc:
            p.error(str(exc))

    rate_str = audio_fx.format_rate(audio_fx.clamp(rate_int, -60, 120))
    pitch_str = audio_fx.format_pitch(audio_fx.clamp(pitch_int, -50, 50))
    volume_str = audio_fx.format_volume(audio_fx.clamp(volume_int, -50, 50))
    filtergraph = "" if args.raw else audio_fx.build_filtergraph(eq, effect, store=store)

    saved_something = False
    if args.save_profile:
        path = store.save_custom_profile(
            args.save_profile,
            {
                "voice_id": voice_id,
                "pitch": pitch_int,
                "rate": rate_int,
                "volume": volume_int,
                "eq": eq,
                "effect": effect,
            },
        )
        print(f"nina: saved custom profile '{args.save_profile}' to {path}")
        saved_something = True

    if args.tune_voice:
        path = store.save_voice_override(
            voice_id,
            {
                "pitch": pitch_int,
                "rate": rate_int,
                "volume": volume_int,
                "eq": eq,
                "effect": effect,
            },
        )
        print(f"nina: saved voice override for {voice_id} to {path}")
        saved_something = True

    if args.set_default:
        path = store.save_default_voice(voice_id)
        print(f"nina: set personal default voice to {voice_id} in {path}")
        saved_something = True

    if args.text:
        text = " ".join(args.text)
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        if saved_something:
            return
        _maybe_header()
        p.print_help()
        sys.exit(0)

    if args.header:
        _maybe_header(force=True)

    if not text.strip():
        if saved_something:
            return
        print("nina: no text provided.", file=sys.stderr)
        sys.exit(1)

    if args.output:
        await save_audio(
            text, voice_id, rate_str, args.output,
            pitch=pitch_str, volume=volume_str, filtergraph=filtergraph,
        )
        print(f"nina: saved to {args.output}")
    else:
        await stream_audio(
            text, voice_id, rate_str,
            pitch=pitch_str, volume=volume_str, filtergraph=filtergraph,
        )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
