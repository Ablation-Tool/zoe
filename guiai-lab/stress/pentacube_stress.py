from __future__ import annotations

from collections import Counter
import contextlib
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.field import _canonical
from guiai.gem.geometry import verify
from guiai.gem.pentacube import (
    FACE_TILINGS, FACES, HOME_SHA256, HOME_STICKERS, NORMALS, PIECE_NAMES,
    PentacubeGame, face_cell, face_position, inverse_move, move_text, parse_moves,
    permute_stickers, rhyme_for_move, validate_move, validate_stickers,
)
from guiai.gem.pentacube_reference import inspect_reference, load_reference_report, save_reference_report
from guiai.gem.pentacube_view import main as pentacube_main
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


TETRIS = Path("/media/cowboy/research/tetris-ibm-pc/Tetris.exe")
TETRIS_ZIP = TETRIS.with_name("Tetris3.zip")
GSX = Path("/media/cowboy/research/DigitalResearch/gsx80_86_src.zip")
ATARI = Path("/home/cowboy/_temp/zoe-atari_tools.zip")


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gdk, Gtk
    from guiai.gem.atlas_view import AtlasWindow
    from guiai.gem.pentacube_view import PentacubeWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


def digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


class PentacubeModelCase(unittest.TestCase):
    def test_home_exact_cover_shape_counts_and_face_roundtrip(self):
        self.assertEqual(len(HOME_STICKERS), 150)
        self.assertTrue(validate_stickers(HOME_STICKERS))
        self.assertEqual({row["patch"] for row in HOME_STICKERS}, set(range(30)))
        self.assertEqual({row["name"] for row in HOME_STICKERS}, set(PIECE_NAMES))
        counts = Counter(row["name"] for row in HOME_STICKERS)
        self.assertEqual(counts, Counter({"P": 20, "I": 15, "L": 15, "T": 15, "V": 15, "Y": 15, "F": 10, "N": 10, "U": 10, "W": 10, "X": 10, "Z": 5}))
        for face in FACES:
            self.assertEqual(len(FACE_TILINGS[face]), 5)
            for row in range(5):
                for column in range(5):
                    position = face_position(face, row, column)
                    self.assertEqual(face_cell(face, position, NORMALS[face]), (row, column))
        self.assertEqual(HOME_SHA256, "672d23c2f8e997bb57f738c5f51ae4c496a3450ab290a03d258632748eee1166")
        solved = PentacubeGame(scramble=0)
        self.assertTrue(solved.measurements()["solved"])
        self.assertEqual(solved.measurements()["recovered_regions"], 30)
        self.assertEqual(solved.measurements()["rho"], 1.0)
        self.assertEqual(solved.hint(), None)

    def test_all_turns_are_permutations_with_inverse_and_order_four(self):
        for face in FACES:
            for depth in (1, 2):
                for inverse in (False, True):
                    move = {"face": face, "depth": depth, "inverse": inverse}
                    changed = permute_stickers(HOME_STICKERS, move)
                    self.assertTrue(validate_stickers(changed))
                    self.assertEqual(permute_stickers(changed, inverse_move(move)), HOME_STICKERS)
                    state = changed
                    for _ in range(3):
                        state = permute_stickers(state, move)
                    self.assertEqual(state, HOME_STICKERS)
                    if not inverse:
                        displaced = sum(a["position"] != b["position"] or a["normal"] != b["normal"] for a, b in zip(HOME_STICKERS, changed))
                        self.assertEqual(displaced, 44 if depth == 1 else 20)
        game = PentacubeGame(scramble=0)
        for face in FACES:
            original = game.board()[face][0][0]["home"]
            game.turn(face)
            self.assertEqual(game.board()[face][0][4]["home"], original)
            game.undo()
            self.assertTrue(game.measurements()["solved"])

    def test_history_hint_reset_solution_and_rhyme(self):
        first = PentacubeGame("repeatable", 12)
        second = PentacubeGame("repeatable", 12)
        self.assertEqual(first._state_digest(), second._state_digest())
        self.assertNotEqual(first._state_digest(), PentacubeGame("different", 12)._state_digest())
        before = first._state_digest()
        hint = first.hint()
        self.assertEqual(first._state_digest(), before)
        self.assertFalse(hint["executed"])
        self.assertFalse(hint["optimal"])
        self.assertIn("choice", rhyme_for_move(hint["move"]))
        initial_scramble = first._state_digest()
        first.apply(hint["move"])
        self.assertNotEqual(first._state_digest(), before)
        self.assertTrue(first.undo())
        self.assertEqual(first._state_digest(), initial_scramble)
        first.turn("F")
        first.turn("R", 2, True)
        self.assertTrue(first.reset())
        self.assertEqual(first._state_digest(), initial_scramble)
        self.assertEqual(len(first.history), 0)
        for move in first.solution_moves():
            first.apply(move)
        self.assertTrue(first.measurements()["solved"])
        self.assertTrue(first.measurements()["valid_permutation"])
        self.assertFalse(first.measurements()["intelligence_measured"])
        self.assertFalse(first.undo() is None)

    def test_replay_roundtrip_tamper_detection_and_no_overwrite(self):
        game = PentacubeGame("replay", 8)
        for move in parse_moves("F,R2',U,L'"):
            game.apply(move)
        game.undo()
        game.reset()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "session.json"
            game.save(path)
            loaded = PentacubeGame.replay(path)
            self.assertTrue(loaded.replay_verified)
            self.assertEqual(loaded._state_digest(), game._state_digest())
            with self.assertRaises(FileExistsError):
                game.save(path)
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["events"][0]["action"] = "reset"
            tampered["events"][0]["arguments"] = {}
            event = tampered["events"][0]
            event["hash"] = digest({key: value for key, value in event.items() if key != "hash"})
            tampered["digest"] = digest({key: value for key, value in tampered.items() if key != "digest"})
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "diverges"):
                PentacubeGame.replay(path)
            tampered["digest"] = "0" * 64
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                PentacubeGame.replay(path)

    def test_scene_exports_default_document_and_forwarded_cli(self):
        game = PentacubeGame("scene", 3)
        game.turn("F")
        hint = game.hint()
        self.assertTrue(verify(game.scene(hint)).passed)
        self.assertTrue(verify_vdi(game.scene(hint)).passed)
        scene, report = default_document("pentacube")
        self.assertTrue(verify(scene).passed)
        self.assertFalse(report["intelligence_measured"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ("svg", "png", "gem"):
                output = root / f"cube.{suffix}"
                game.export(output, hint=hint)
                self.assertTrue(output.is_file())
                with self.assertRaises(FileExistsError):
                    game.export(output)
            for index, entrypoint in enumerate((pentacube_main, gem_main, zoe_main)):
                arguments = ["--seed", "cli", "--scramble", "3", "--moves", "F,R2'", "--hint", "--rhyme", "--output", str(root / f"session-{index}.json")]
                if entrypoint is not pentacube_main:
                    arguments.insert(0, "pentacube")
                with contextlib.redirect_stdout(io.StringIO()) as stdout:
                    self.assertEqual(entrypoint(arguments), 0)
                self.assertTrue(PentacubeGame.replay(root / f"session-{index}.json").replay_verified)
                self.assertIn("choice", stdout.getvalue())

    def test_invalid_moves_states_and_bounds(self):
        for move in (None, {}, {"face": "Q", "depth": 1, "inverse": False}, {"face": "F", "depth": 0, "inverse": False}, {"face": "F", "depth": True, "inverse": False}, {"face": "F", "depth": 1, "inverse": 1}):
            with self.assertRaises(ValueError):
                validate_move(move)
        for text in ("F3", "F,,R", "F R", "Q", "F" * 2049):
            with self.assertRaises(ValueError):
                parse_moves(text)
        with self.assertRaises(ValueError):
            PentacubeGame("seed", 65)
        with self.assertRaises(ValueError):
            PentacubeGame("", 1)
        invalid = deepcopy(HOME_STICKERS)
        invalid[0]["position"] = invalid[1]["position"]
        with self.assertRaises(ValueError):
            permute_stickers(invalid, {"face": "F", "depth": 1, "inverse": False})
        self.assertEqual(move_text(parse_moves("R2'")[0]), "R2'")
        bounded = PentacubeGame("bounded", 0)
        bounded.turn("F")
        bounded.events = [deepcopy(bounded.events[0]) for _ in range(4096)]
        before = bounded._state_digest()
        for action in (lambda: bounded.turn("R"), bounded.undo, bounded.reset):
            with self.assertRaisesRegex(ValueError, "event bound"):
                action()
            self.assertEqual(bounded._state_digest(), before)


class HistoricalReferenceCase(unittest.TestCase):
    def test_synthetic_mz_zip_integrity_tamper_and_unsafe_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            header = struct.pack("<13H", 256, 1, 0, 16, 0, 0, 0, 0x4000, 0, 0x100, 0, 28, 0)
            mz = root / "tiny.exe"
            mz.write_bytes(b"MZ" + header + bytes(256 - 28))
            report = inspect_reference(mz, "https://example.org/tiny.exe")
            self.assertEqual(report["kind"], "dos-mz-executable")
            self.assertEqual(report["format"]["header_bytes"], 256)
            self.assertEqual(report["format"]["entry_linear"], 256)
            self.assertTrue(report["format"]["declared_size_matches"])
            archive = root / "source.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("source/hello.txt", "bounded evidence")
            zipped = inspect_reference(archive)
            self.assertEqual(zipped["format"]["file_count"], 1)
            self.assertEqual(zipped["format"]["members"][0]["sha256"], hashlib.sha256(b"bounded evidence").hexdigest())
            output = root / "reference.json"
            save_reference_report(zipped, output)
            self.assertEqual(load_reference_report(output)["sha256"], zipped["sha256"])
            with self.assertRaises(FileExistsError):
                save_reference_report(zipped, output)
            archive.write_bytes(archive.read_bytes() + b"changed")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                load_reference_report(output)
            unsafe = root / "unsafe.zip"
            with zipfile.ZipFile(unsafe, "w") as stream:
                stream.writestr("../escape.txt", "no extraction")
            with self.assertRaisesRegex(ValueError, "unsafe"):
                inspect_reference(unsafe)
            pdf = root / "tiny.pdf"
            pdf.write_bytes(b"%PDF-1.4\nSynthetic reference only; no page tree is asserted.")
            pdf_report = inspect_reference(pdf)
            self.assertEqual(pdf_report["kind"], "pdf-document")
            self.assertEqual(pdf_report["format"]["version"], "1.4")
            self.assertFalse(pdf_report["format"]["page_tree_verified"])

    @unittest.skipUnless(TETRIS.is_file() and TETRIS_ZIP.is_file() and GSX.is_file(), "local Tetris and GSX references are unavailable")
    def test_real_tetris_gsx_and_optional_atari_evidence(self):
        tetris = inspect_reference(TETRIS, "https://vadim.oversigma.com/Tetris3.zip")
        self.assertEqual(tetris["bytes"], 25744)
        self.assertEqual(tetris["sha256"], "d72cb451e63f32bfd3838b5e9ddc52954988b8fbb2b0c5087fef36b2f29085e6")
        self.assertEqual(tetris["format"]["relocation_count"], 459)
        self.assertEqual(tetris["format"]["header_bytes"], 1872)
        self.assertTrue(tetris["format"]["declared_size_matches"])
        self.assertFalse(tetris["payloads_executed"])
        archive = inspect_reference(TETRIS_ZIP)
        self.assertEqual(archive["format"]["members"][0]["sha256"], tetris["sha256"])
        gsx = inspect_reference(GSX, "https://ftpmirror.your.org/pub/misc/bitsavers/bits/DigitalResearch/gsx80_86_src.zip")
        self.assertEqual(gsx["sha256"], "22303ae5a75188e9d45fe91b7261497033ead882da0df8172331c88e6e560158")
        self.assertEqual(gsx["format"]["member_count"], 823)
        self.assertFalse(gsx["format"]["contents_extracted"])
        if ATARI.is_file():
            atari = inspect_reference(ATARI, "https://ftpmirror.your.org/pub/misc/bitsavers/bits/Atari/arcade/atari_tools.zip")
            self.assertEqual(atari["sha256"], "56b246c16e87e9d36efa5b4c81ad5104b91a6073e618b9853ef0f94d08ea3ac6")
            self.assertEqual(atari["format"]["member_count"], 137)
            self.assertFalse(atari["firmware_identified"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "tetris.json"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pentacube_main(["--reference", str(TETRIS), "--source-url", "https://vadim.oversigma.com/Tetris3.zip", "--output", str(output)]), 0)
            self.assertEqual(load_reference_report(output)["sha256"], tetris["sha256"])


@unittest.skipUnless(HAS_GTK, "native Pentacube tests require GTK, Cairo, and an X11 DISPLAY")
class PentacubeNativeCase(unittest.TestCase):
    def test_native_turn_hint_replay_rhyme_logo_and_exports(self):
        window = PentacubeWindow(PentacubeGame("native", 4), show_hint=True, rhyme=True)
        window.show_all()
        try:
            self.assertIsNotNone(window.logo)
            baseline = window.game._state_digest()
            self.assertTrue(window.undo() is False)
            self.assertTrue(window.turn("F"))
            self.assertTrue(window.undo())
            self.assertEqual(window.game._state_digest(), baseline)
            hint = window.hint()
            self.assertEqual(window.game._state_digest(), baseline)
            self.assertIsNotNone(hint)
            self.assertTrue(window.apply_hint())
            self.assertNotEqual(window.game._state_digest(), baseline)
            window.reset()
            self.assertEqual(window.game._state_digest(), baseline)
            event = Gdk.EventKey()
            event.keyval = Gdk.keyval_from_name("F")
            self.assertTrue(window.canvas.on_key(window.canvas, event))
            event.keyval = Gdk.keyval_from_name("f")
            self.assertTrue(window.canvas.on_key(window.canvas, event))
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                session = root / "session.json"
                window.game.save(session)
                self.assertTrue(window.load_path(session))
                previous = window.game
                bad = root / "bad.json"
                bad.write_text("not json", encoding="utf-8")
                self.assertFalse(window.load_path(bad))
                self.assertIs(window.game, previous)
                for suffix in ("svg", "png", "gem"):
                    self.assertTrue(window.export_current(root / f"native.{suffix}", suffix).is_file())
            window.seed.set_text("native-new")
            window.scramble.set_value(0)
            window.new_button.clicked()
            self.assertTrue(window.game.measurements()["solved"])
            self.assertIn("hip hooray", window.summary.get_text())
        finally:
            window.destroy()

    def test_atlas_preview_and_dedicated_window(self):
        atlas = AtlasWindow("pentacube")
        try:
            window = atlas.open_builtin("pentacube")
            self.assertIs(window, atlas.open_builtin("pentacube"))
            self.assertTrue(verify(atlas.scene).passed)
            self.assertFalse(atlas.report["intelligence_measured"])
            self.assertEqual(window.game.measurements()["stickers"], 150)
        finally:
            atlas.destroy()


if __name__ == "__main__":
    unittest.main()
