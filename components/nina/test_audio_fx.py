"""Unit and audio-filter integration tests for Nina's voice profiles and equalizer."""

import asyncio
import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import audio_fx
import lume_header
import tts as _tts


class AudioFXTests(unittest.TestCase):
    def test_repo_profiles_has_24_female_voices(self):
        store = audio_fx.ProfileStore()
        fem = store.list_female_profiles()
        self.assertGreaterEqual(len(fem), 24)
        self.assertIn("ZoeNatasha-3D", fem)
        self.assertIn("ZoeNative-3D", fem)
        self.assertIn("ZoeNative-Mono", fem)
        self.assertEqual(store.default_voice, "zoe")
        self.assertEqual(store.preferred_voice_id, "ZoeNatasha-3D")
        for vid, cfg in fem.items():
            self.assertIn("pitch", cfg)
            self.assertIn("rate", cfg)
            self.assertIn("eq", cfg)
            self.assertIn("effect", cfg)
            self.assertIn(cfg["effect"], store.list_effect_presets())
            eq = audio_fx.normalize_eq(cfg["eq"])
            self.assertEqual(set(eq.keys()), {"warmth", "body", "mid", "presence", "air"})

    def test_native_zoe_app_voice_synthesis_and_default_voice(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_file = Path(tmp) / "user_profiles.json"
            store = audio_fx.ProfileStore(user_path=user_file)
            store.save_default_voice("ZoeNative-3D")
            self.assertEqual(store.preferred_voice_id, "ZoeNative-3D")
            self.assertEqual(store.default_voice, "zoe-app")

        if _tts.has_native_zoe_voice():
            async def _run():
                comm = _tts.Communicate("Hello from Zoe.", "ZoeNative-3D", pitch="-8Hz", rate="+0%")
                chunks = [ch["data"] async for ch in comm.stream() if ch["type"] == "audio"]
                return b"".join(chunks)

            wav_bytes = asyncio.run(_run())
            self.assertTrue(wav_bytes.startswith(b"RIFF"))
            self.assertGreater(len(wav_bytes), 4000)

        # Verify Zoe Native x Natasha 3D DSP fusion stage directly (offline-deterministic)
        import numpy as np
        t = np.linspace(0.0, 0.5, 22050, endpoint=False)
        fake_natasha = 0.4 * np.sin(2.0 * np.pi * 210.0 * t)
        fused_wav = _tts._fuse_with_zoe_native_dsp(fake_natasha, sample_rate=44100)
        self.assertTrue(fused_wav.startswith(b"RIFF"))
        self.assertGreater(len(fused_wav), 40000)

    def test_layered_overrides_and_export_import(self):
        with tempfile.TemporaryDirectory() as tmp:
            user_file = Path(tmp) / "user_profiles.json"
            export_file = Path(tmp) / "shared_preset.json"
            store = audio_fx.ProfileStore(user_path=user_file)

            orig = store.get_voice_profile("en-US-AvaMultilingualNeural", tuned=True)
            self.assertEqual(orig["pitch"], -4)

            store.save_voice_override(
                "en-US-AvaMultilingualNeural",
                {
                    "pitch": -8,
                    "rate": 5,
                    "volume": 3,
                    "eq": {"warmth": 4.0, "body": -2.0, "mid": 0.0, "presence": 2.5, "air": 3.0},
                    "effect": "cathedral",
                },
            )
            overridden = store.get_voice_profile("en-US-AvaMultilingualNeural", tuned=True)
            self.assertEqual(overridden["pitch"], -8)
            self.assertEqual(overridden["effect"], "cathedral")
            self.assertEqual(overridden["eq"]["warmth"], 4.0)

            repo_def = store.get_repo_voice_default("en-US-AvaMultilingualNeural")
            self.assertEqual(repo_def["pitch"], -4)

            store.save_custom_profile(
                "midnight_test",
                {
                    "voice_id": "en-IE-EmilyNeural",
                    "pitch": -3,
                    "rate": -4,
                    "volume": 0,
                    "eq": {"warmth": 2.0, "body": -1.0, "mid": 0.5, "presence": 1.5, "air": 2.0},
                    "effect": "fireside",
                },
            )
            custom = store.get_custom_profile("MIDNIGHT_TEST")
            self.assertIsNotNone(custom)
            self.assertEqual(custom["voice_id"], "en-IE-EmilyNeural")
            self.assertEqual(custom["effect"], "fireside")

            store.export_profile(export_file, custom)
            loaded = store.import_profile(export_file)
            self.assertEqual(loaded["voice_id"], "en-IE-EmilyNeural")
            self.assertEqual(loaded["eq"]["warmth"], 2.0)

            store.reset_voice_override("en-US-AvaMultilingualNeural")
            reloaded = store.get_voice_profile("en-US-AvaMultilingualNeural", tuned=True)
            self.assertEqual(reloaded["pitch"], -4)

    def test_parse_helpers(self):
        self.assertEqual(audio_fx.format_pitch(-4), "-4Hz")
        self.assertEqual(audio_fx.format_pitch(0), "+0Hz")
        self.assertEqual(audio_fx.format_rate(15), "+15%")
        self.assertEqual(audio_fx.format_volume(-5), "-5%")
        self.assertEqual(audio_fx.parse_signed_int("-6Hz", "Hz"), -6)
        self.assertEqual(audio_fx.parse_signed_int("+12%", "%"), 12)

        eq1 = audio_fx.parse_eq_arg("1.5,-1,0,2,20")
        self.assertEqual(eq1, {"warmth": 1.5, "body": -1.0, "mid": 0.0, "presence": 2.0, "air": 12.0})

        eq2 = audio_fx.parse_eq_arg("warmth=3.5,air=-15")
        self.assertEqual(eq2, {"warmth": 3.5, "body": 0.0, "mid": 0.0, "presence": 0.0, "air": -12.0})

        with self.assertRaises(ValueError):
            audio_fx.parse_eq_arg("1,2,3")
        with self.assertRaises(ValueError):
            audio_fx.parse_eq_arg("bass=2")
        with self.assertRaises(ValueError):
            audio_fx.parse_signed_int("loud", "Hz")

    def test_build_filtergraph(self):
        store = audio_fx.ProfileStore()
        self.assertEqual(audio_fx.build_filtergraph(audio_fx.DEFAULT_EQ, "flat", store=store), "")
        fg = audio_fx.build_filtergraph(
            {"warmth": 1.5, "body": -1.0, "mid": 0.0, "presence": 2.0, "air": 3.5},
            "zoe_velvet",
            store=store,
        )
        self.assertIn("equalizer=f=120", fg)
        self.assertNotIn("equalizer=f=1200", fg)
        self.assertIn("acompressor=", fg)
        self.assertIn("alimiter=", fg)

    def test_all_effect_presets_in_mpv_and_ffmpeg(self):
        store = audio_fx.ProfileStore()
        gen = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=24000:duration=1",
                "-ac", "1", "-f", "mp3", "pipe:1",
            ],
            capture_output=True,
        )
        self.assertEqual(gen.returncode, 0, "ffmpeg failed to synthesize test MP3 clip")
        raw_mp3 = gen.stdout
        self.assertGreater(len(raw_mp3), 1000)

        eq = {"warmth": 1.5, "body": -1.0, "mid": 0.5, "presence": 2.0, "air": 3.0}
        with tempfile.TemporaryDirectory() as tmp:
            for key in store.list_effect_presets():
                fg = audio_fx.build_filtergraph(eq, key, store=store)
                p_mpv = subprocess.run(
                    ["mpv", "--no-video", "--ao=null", f"--af=lavfi=[{fg}]", "-"],
                    input=raw_mp3,
                    capture_output=True,
                )
                self.assertEqual(
                    p_mpv.returncode, 0,
                    f"mpv failed for preset {key}: {p_mpv.stderr.decode(errors='replace')}",
                )
                out_mp3 = Path(tmp) / f"{key}.mp3"
                ok = audio_fx.apply_ffmpeg_filter(raw_mp3, fg, out_mp3)
                self.assertTrue(ok, f"ffmpeg failed for preset {key}")
                self.assertGreater(out_mp3.stat().st_size, 500)

    def test_lume_header_pixel_art_and_svg(self):
        rows = lume_header.ZOE_GEM_PIXELS
        self.assertGreaterEqual(len(rows), 14)
        widths = {len(r) for r in rows}
        self.assertEqual(widths, {23})
        for r in rows:
            for ch in r:
                self.assertIn(ch, lume_header.PALETTE)

        colored = lume_header.render_terminal_header(color=True)
        self.assertIn("\x1b[38;2;", colored)
        self.assertNotIn("Zoe", colored)
        self.assertGreaterEqual(len(colored.splitlines()), 7)

        plain = lume_header.render_terminal_header(color=False)
        self.assertNotIn("\x1b[", plain)
        self.assertIn("◠ ◡ ◠", plain)

        svg_path = Path(__file__).resolve().parent / "assets" / "lume-header.svg"
        self.assertTrue(svg_path.exists())
        tree = ET.parse(svg_path)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn("Lume 1.0", svg_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
