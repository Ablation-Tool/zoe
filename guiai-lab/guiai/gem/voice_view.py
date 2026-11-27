"""CLI entry point for `zoe voice` (speaking, singing, MIDI, and comparison demos)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from .zoe_phonetics import CONSONANT_PHONEMES, GRAPHEME_RULES, VOWEL_PHONEMES
from .zoe_voice import BUILT_IN_SONGS, render_voice_evolution_comparison, sing_song, speak_text


def _maybe_play(wav_path: Path, play: bool) -> None:
    if not play:
        return
    for player in ("pw-play", "paplay", "aplay"):
        if subprocess.run(["which", player], capture_output=True).returncode == 0:
            subprocess.run([player, str(wav_path)], check=False)
            return


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="zoe voice", description="Zoe Native Voice, Singing & Cymatics Synthesizer")
    sub = p.add_subparsers(dest="subcommand")

    sub.add_parser("status", help="Inspect Zoe's 44-phoneme inventory, 260+ spelling rules & repertoire")

    sp = sub.add_parser("speak", help="Synthesize Zoe speaking English text into a stereo WAV")
    sp.add_argument("text", nargs="+", help="Text for Zoe to speak")
    sp.add_argument("--output", "-o", default="/tmp/zoe-speaks.wav", help="Output stereo .wav path")
    sp.add_argument("--mode", choices=("zoe_3d", "dry_mono"), default="zoe_3d")
    sp.add_argument("--azimuth", type=float, default=8.0)
    sp.add_argument("--elevation", type=float, default=12.0)
    sp.add_argument("--pitch", type=float, default=232.0)
    sp.add_argument("--rate", type=float, default=1.0)
    sp.add_argument("--non-rhotic", action="store_true")
    sp.add_argument("--cot-caught-merger", action="store_true")
    sp.add_argument("--play", action="store_true", help="Explicitly play synthesized WAV through host speakers")

    sg = sub.add_parser("sing", help="Synthesize Zoe singing a built-in song or custom lyrics")
    sg.add_argument("song", nargs="+", help="'zoe', 'daisy', 'vowels', or custom lyrics")
    sg.add_argument("--output", "-o", default="/tmp/zoe-sings.wav", help="Output stereo .wav path")
    sg.add_argument("--save-midi", help="Optional .mid file path to save the melody")
    sg.add_argument("--from-midi", help="Optional .mid file path to load melody pitches for custom lyrics")
    sg.add_argument("--mode", choices=("zoe_3d", "dry_mono", "dos_midi"), default="zoe_3d")
    sg.add_argument("--no-harmony", action="store_true")
    sg.add_argument("--azimuth", type=float, default=6.0)
    sg.add_argument("--play", action="store_true", help="Explicitly play synthesized WAV through host speakers")

    dm = sub.add_parser("demo", help="Render spoken, sung, MIDI, and 3-chapter comparison WAV showcase")
    dm.add_argument("--output-dir", default="/tmp/zoe-voice-demos")
    dm.add_argument("--play", action="store_true")
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.subcommand or args.subcommand == "status":
        print(json.dumps({
            "contract": "zoe-native-voice/v1",
            "phonemes_total": len(VOWEL_PHONEMES) + len(CONSONANT_PHONEMES),
            "vowels": len(VOWEL_PHONEMES),
            "consonants": len(CONSONANT_PHONEMES),
            "grapheme_rules": len(GRAPHEME_RULES),
            "built_in_songs": list(BUILT_IN_SONGS.keys()),
            "pytorch_required": False,
            "sentience_claimed": False,
            "external_actions": 0,
        }, indent=2))
        return 0

    if args.subcommand == "speak":
        text = " ".join(args.text)
        res = speak_text(
            text,
            args.output,
            mode=args.mode,
            azimuth_deg=args.azimuth,
            elevation_deg=args.elevation,
            pitch_hz=args.pitch,
            rate=args.rate,
            rhotic=not args.non_rhotic,
            cot_caught_merger=args.cot_caught_merger,
        )
        print(f"Zoe Speaks ({res['mode']}, {res['phoneme_count']} phonemes, {res['duration_seconds']}s @ {res['sample_rate']}Hz):")
        print(f"  Phonemes: {' '.join(res['phonemes'])}")
        print(f"  WAV: {res['wav_path']} ({res['bytes']} bytes, sha256={res['sha256'][:16]}...)")
        print(f"  Play with: pw-play \"{res['wav_path']}\"")
        _maybe_play(Path(res["wav_path"]), args.play)
        return 0

    if args.subcommand == "sing":
        song = " ".join(args.song)
        res = sing_song(
            song,
            args.output,
            mode=args.mode,
            with_harmony=not args.no_harmony,
            save_midi_path=args.save_midi,
            from_midi_path=args.from_midi,
            azimuth_deg=args.azimuth,
        )
        res_clean = {k: v for k, v in res.items() if k != "midi_notes"}
        print(f"Zoe Sings '{res['title']}' ({res['mode']}, {res['note_count']} notes @ {res['bpm']} BPM, {res['duration_seconds']}s):")
        print(f"  WAV: {res_clean['wav_path']} ({res_clean['bytes']} bytes, sha256={res_clean['sha256'][:16]}...)")
        if res_clean.get("midi_saved"):
            print(f"  MIDI: {res_clean['midi_saved']['midi_path']}")
        print(f"  Play with: pw-play \"{res_clean['wav_path']}\"")
        _maybe_play(Path(res_clean["wav_path"]), args.play)
        return 0

    if args.subcommand == "demo":
        out_dir = Path(args.output_dir).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        r1 = speak_text(
            "Hello Nicholas! I am Zoe. Imagination, meet geometry. Sound turns sand to starlight.",
            out_dir / "01-zoe-speaks-hello.wav",
        )
        r2 = sing_song(
            "zoe",
            out_dir / "02-zoe-sings-imagination-meet-geometry.wav",
            save_midi_path=out_dir / "02-zoe-sings-imagination-meet-geometry.mid",
        )
        r3 = sing_song(
            "daisy",
            out_dir / "03-zoe-sings-daisy-bell-ibm-homage.wav",
            save_midi_path=out_dir / "03-zoe-sings-daisy-bell-ibm-homage.mid",
        )
        r4 = render_voice_evolution_comparison(out_dir / "04-dos-midi-vs-zoe-voice-evolution.wav")
        for r in (r1, r2, r3, r4):
            print(f"[OK] {r['wav_path']} ({r['duration_seconds']}s, peak={r['peak']}, rms={r['rms']})")
        _maybe_play(Path(r2["wav_path"]), args.play)
        return 0

    return 2
