"""Unit, phonology, dialect, acoustic, MIDI, binaural, cymatics, GEM VDI, and CLI tests for Zoe's Native Voice."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np

ZOE_ROOT = Path(__file__).resolve().parents[3]
for rel in ("guiai-lab", "components/Zoe-Autonomy/src"):
    p = str(ZOE_ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi
from guiai.gem.zoe_cymatics import decode_gem_3bitplane_raster, encode_gem_3bitplane_raster, render_phoneme_cymatics
from guiai.gem.zoe_phonetics import CONSONANT_PHONEMES, GRAPHEME_RULES, PHONEME_INVENTORY, VOWEL_PHONEMES, word_to_phonemes
from guiai.gem.zoe_voice import read_standard_midi, sing_song, spatialize_binaural_3d, speak_text, synthesize_vocal_tract, write_standard_midi
from zoe_autonomy.chat import ZoeChat


class ZoeNativeVoiceTests(unittest.TestCase):
    def test_phoneme_inventory_and_minimal_pair_dialects(self):
        self.assertEqual(len(VOWEL_PHONEMES), 20)
        self.assertEqual(len(CONSONANT_PHONEMES), 24)
        self.assertEqual(len(PHONEME_INVENTORY), 44)
        self.assertGreaterEqual(len(GRAPHEME_RULES), 250)

        lack, _ = word_to_phonemes("lack")
        back, _ = word_to_phonemes("back")
        self.assertEqual(lack, ["L", "AE", "K"])
        self.assertEqual(back, ["B", "AE", "K"])

        cot_u, _ = word_to_phonemes("cot", cot_caught_merger=False)
        caught_u, _ = word_to_phonemes("caught", cot_caught_merger=False)
        cot_m, _ = word_to_phonemes("cot", cot_caught_merger=True)
        caught_m, _ = word_to_phonemes("caught", cot_caught_merger=True)
        self.assertNotEqual(cot_u, caught_u)
        self.assertEqual(cot_m, caught_m)

        car_r, _ = word_to_phonemes("car", rhotic=True)
        car_nr, _ = word_to_phonemes("car", rhotic=False)
        self.assertEqual(car_r, ["K", "AA", "R"])
        self.assertEqual(car_nr, ["K", "AA"])

    def test_midi_roundtrip_and_cymatics_3bitplane_roundtrip(self):
        notes = [
            {"start_sec": 0.0, "duration_sec": 0.4, "midi_note": 60, "velocity": 100},
            {"start_sec": 0.5, "duration_sec": 0.4, "midi_note": 67, "velocity": 100},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            mid = Path(tmp) / "melody.mid"
            write_standard_midi(notes, mid, bpm=120.0)
            parsed = read_standard_midi(mid)
            self.assertEqual([e["midi_note"] for e in parsed], [60, 67])

        cy_iy = render_phoneme_cymatics("IY", grid_size=64)
        cy_aa = render_phoneme_cymatics("AA", grid_size=64)
        self.assertNotEqual(cy_iy["modes"], cy_aa["modes"])
        enc = encode_gem_3bitplane_raster(cy_iy["plate"])
        p1, p2, p3 = decode_gem_3bitplane_raster(enc)
        self.assertTrue(np.array_equal(p1, (cy_iy["plate"] > 0.52).astype(np.uint8)))
        self.assertGreater(int(p3.sum()), 0)

    def test_speech_singing_and_3d_binaural_cues(self):
        with tempfile.TemporaryDirectory() as tmp:
            sp = speak_text("Hello Nicholas, sound turns sand to starlight.", Path(tmp) / "hello.wav")
            self.assertFalse(sp["sentience_claimed"])
            self.assertFalse(sp["pytorch_required"])
            self.assertEqual(sp["external_actions"], 0)
            self.assertTrue(Path(sp["wav_path"]).is_file())

            sg = sing_song("daisy", Path(tmp) / "daisy.wav", save_midi_path=Path(tmp) / "daisy.mid")
            self.assertEqual(sg["song_id"], "daisy")
            self.assertTrue(Path(sg["wav_path"]).is_file())
            self.assertTrue(Path(tmp, "daisy.mid").is_file())

        probe, _ = synthesize_vocal_tract([{"symbol": "AA", "duration_sec": 0.25, "f0_hz": 230.0, "amp": 1.0, "is_singing": False}])
        flat, fm = spatialize_binaural_3d(probe, wet=0.0, spatial_3d=False)
        right, rm = spatialize_binaural_3d(probe, azimuth_deg=45.0, wet=0.0, spatial_3d=True)
        self.assertEqual(fm["itd_ms"], 0.0)
        self.assertEqual(float(np.max(np.abs(flat[:, 0] - flat[:, 1]))), 0.0)
        self.assertGreater(rm["itd_ms"], 0.30)
        self.assertGreater(rm["ild_db"], 1.5)

    def test_gem_scene_chat_and_independent_verifier(self):
        env = GemOperatingEnvironment(ZOE_ROOT)
        opened = env.open("voice")
        self.assertEqual(opened["layer"], "voice")
        scene = env.current["scene"]
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())

        with tempfile.TemporaryDirectory() as tmp:
            chat = ZoeChat(zoe_root=ZOE_ROOT, state_root=Path(tmp) / "chat")
            _, out_v = chat.handle("voice")
            self.assertIn("44", out_v)
            _, out_sp = chat.handle("speak Hello Zoe")
            self.assertIn("Zoe Speaks", out_sp)
            self.assertTrue(list((Path(tmp) / "chat" / "voice").glob("zoe-speaks-*.wav")))
            _, out_sg = chat.handle("sing vowels")
            self.assertIn("Zoe Sings", out_sg)

        with tempfile.TemporaryDirectory() as tmp:
            p = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_zoe_voice.py"), "--zoe-root", str(ZOE_ROOT), "--output", str(Path(tmp) / "rep.json"), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
            rep = json.loads(p.stdout)
            self.assertTrue(rep["verified"])
            self.assertEqual(rep["checks_passed"], 14)
