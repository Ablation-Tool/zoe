from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.field import _canonical
from guiai.gem.geometry import verify
from guiai.gem.pentomino import (
    HEIGHT, PIECE_NAMES, WIDTH, PentominoGame, benchmark_budgets,
    oriented_cells, orientations, solve_tiling,
)
from guiai.gem.pentomino_view import main as pentomino_main
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


try:
    import gi
    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gdk, Gtk
    from guiai.gem.pentomino_view import PentominoWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


def completed_game(mode="practice", seed="test-complete"):
    now = [0.0]
    game = PentominoGame(seed, mode, seconds=300, interval=3600, clock=lambda: now[0])
    for placement in solve_tiling(game._bag):
        now[0] += .1
        if placement["reflected"] != game.current["reflected"]:
            assert game.flip()
        rotation = (placement["rotation"] - game.current["rotation"]) % 4
        if rotation:
            assert game.rotate(rotation)
        assert game.move(placement["x"] - game.current["x"], placement["y"] - game.current["y"])
        assert game.place()
    assert game.status == "won"
    return game


def buttons(widget):
    if isinstance(widget, Gtk.Button):
        yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from buttons(child)


class PentominoModelCase(unittest.TestCase):
    def test_twelve_free_pieces_and_normalized_transformations(self):
        expected = {"F": 8, "I": 2, "L": 8, "P": 8, "T": 4, "U": 4, "V": 4, "W": 4, "X": 1, "Y": 8, "Z": 4, "N": 8}
        self.assertEqual(set(PIECE_NAMES), set("FILPTUVWXYZN"))
        self.assertEqual(sum(len(SHAPES) for SHAPES in [PIECE_NAMES]), 12)
        for name in PIECE_NAMES:
            self.assertEqual(len(oriented_cells(name)), 5)
            self.assertEqual(min(x for x, _ in oriented_cells(name)), 0)
            self.assertEqual(min(y for _, y in oriented_cells(name)), 0)
            self.assertEqual(len(orientations(name)), expected[name])
            for variant in orientations(name):
                self.assertEqual(variant["cells"], oriented_cells(name, variant["rotation"], variant["reflected"]))
                self.assertEqual(len(set(variant["cells"])), 5)
        self.assertEqual(oriented_cells("X", 0), oriented_cells("X", 3, True))
        with self.assertRaises(ValueError):
            oriented_cells("unknown")
        with self.assertRaises(ValueError):
            solve_tiling(["I"] * 12)

    def test_seeded_and_masked_visibility_collision_and_gravity(self):
        first = PentominoGame("repeatable", clock=lambda: 0)
        second = PentominoGame("repeatable", clock=lambda: 0)
        self.assertEqual(first._bag, second._bag)
        self.assertEqual(first.next_piece, first._bag[1])
        masked = PentominoGame(mode="masked", clock=lambda: 0)
        self.assertIsNone(masked.next_piece)
        public = masked.document()
        self.assertIsNone(public["seed"])
        self.assertEqual(public["order"], [masked.current["name"]])
        self.assertNotIn(masked._seed, _canonical(public))
        self.assertFalse(masked.place())
        self.assertFalse(masked.drop())
        self.assertFalse(first.move(-WIDTH, 0))
        original_y = first.current["y"]
        self.assertTrue(first.move(0, -original_y))
        self.assertTrue(first.place())
        self.assertEqual(first.measurements()["filled_cells"], 5)
        now = [0.0]
        gravity = PentominoGame(seconds=30, interval=.8, clock=lambda: now[0])
        start = gravity.current["y"]
        now[0] = .8
        gravity.tick()
        self.assertEqual(gravity.current["y"], start + 1)
        for _ in range(12):
            if gravity.used:
                break
            now[0] += .8
            gravity.tick()
        self.assertEqual(len(gravity.fixed), 5)
        self.assertTrue(any(event["action"] == "tick" for event in gravity.events))
        self.assertEqual(gravity.measurements()["holes"], 2)
        timeout_now = [0.0]
        timed = PentominoGame(seconds=1, interval=3600, clock=lambda: timeout_now[0])
        timeout_now[0] = 1
        timed.tick()
        self.assertEqual(timed.status, "timed_out")
        self.assertEqual(timed.remaining, 0)
        self.assertTrue(timed.measurements()["timed_out"])
        self.assertFalse(timed.drop())
        blocked = PentominoGame(clock=lambda: 0)
        blocked.fixed = {(x, y): "I" for y in range(HEIGHT) for x in range(WIDTH)}
        blocked._spawn()
        self.assertEqual(blocked.status, "lost")

    def test_completed_games_replay_and_tamper_detection(self):
        for mode in ("practice", "masked"):
            game = completed_game(mode)
            self.assertEqual(game.measurements()["filled_cells"], 60)
            self.assertEqual(game.measurements()["full_row_count"], 10)
            self.assertEqual(game.measurements()["holes"], 0)
            self.assertTrue(game.measurements()["all_pieces_tiled"])
            self.assertIsNotNone(game.document()["seed"])
            self.assertEqual(game.document()["order"], game._bag)
            restored = PentominoGame.replay(game.document())
            self.assertTrue(restored.replay_verified)
            self.assertEqual(restored.fixed, game.fixed)
            final_elapsed = game.elapsed
            game._clock = lambda: 100.0
            self.assertEqual(game.document()["elapsed"], final_elapsed)
            self.assertTrue(PentominoGame.replay(game.document()).replay_verified)
            tampered = game.document()
            tampered["events"][0]["arguments"]["steps"] = 2
            previous = None
            for event in tampered["events"]:
                event["previous_hash"] = previous
                event["hash"] = hashlib.sha256(_canonical({key: value for key, value in event.items() if key != "hash"}).encode("utf-8")).hexdigest()
                previous = event["hash"]
            with self.assertRaisesRegex(ValueError, "replay diverges|invalid pentomino replay action"):
                PentominoGame.replay(tampered)
            edited = game.document()
            edited["events"][-1]["accepted"] = False
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                PentominoGame.replay(edited)
            edited = game.document()
            edited["seed_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "seed digest"):
                PentominoGame.replay(edited)
        with tempfile.TemporaryDirectory() as directory:
            active = PentominoGame(clock=lambda: 0)
            active_path = Path(directory) / "active.json"
            active.save(active_path)
            with self.assertRaisesRegex(ValueError, "completed games"):
                PentominoGame.replay(active_path)
            with self.assertRaises(FileExistsError):
                active.save(active_path)
            game = completed_game()
            path = Path(directory) / "complete.json"
            game.save(path)
            self.assertTrue(PentominoGame.replay(path).replay_verified)
            reordered = game.document()
            reordered["events"][0], reordered["events"][1] = reordered["events"][1], reordered["events"][0]
            with self.assertRaisesRegex(ValueError, "hash-chain mismatch"):
                PentominoGame.replay(reordered)

    def test_scene_exports_cli_and_controlled_budget_comparison(self):
        game = completed_game()
        self.assertTrue(verify(game.scene()).passed, verify(game.scene()).text())
        self.assertTrue(verify_vdi(game.scene()).passed, verify_vdi(game.scene()).text())
        with tempfile.TemporaryDirectory() as directory:
            for suffix in ("json", "svg", "png", "gem"):
                path = Path(directory) / f"pentomino.{suffix}"
                output = game.save(path) if suffix == "json" else game.export(path)
                self.assertEqual(output, path)
                self.assertGreater(path.stat().st_size, 0)
                with self.assertRaises(FileExistsError):
                    game.save(path) if suffix == "json" else game.export(path)
            comparison = Path(directory) / "comparison.json"
            replayed = Path(directory) / "replayed.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(pentomino_main(["--compare", "--output", str(comparison)]), 0)
                self.assertEqual(pentomino_main([str(Path(directory) / "pentomino.json"), "--output", str(replayed)]), 0)
                self.assertEqual(gem_main(["pentomino", "--output", str(Path(directory) / "gem-command.svg")]), 0)
                self.assertEqual(zoe_main(["pentomino", "--output", str(Path(directory) / "zoe-command.svg")]), 0)
            report = json.loads(comparison.read_text(encoding="utf-8"))
            self.assertEqual(report, benchmark_budgets())
            self.assertEqual([(row["budget_seconds"], row["pieces_placed"], row["status"]) for row in report["budgets"]], [(1, 0, "timed_out"), (5, 4, "timed_out"), (20, 12, "won"), (300, 12, "won")])
            self.assertIn("do not identify an optimal", report["conclusion"])
        scene, report = default_document("pentomino")
        self.assertTrue(verify(scene).passed)
        self.assertFalse(report["intelligence_measured"])
        self.assertFalse(report["optimal_time_claimed"])


@unittest.skipUnless(HAS_GTK, "native Pentomino tests require GTK, Cairo, and an X11 DISPLAY")
class PentominoNativeCase(unittest.TestCase):
    def test_native_keyboard_buttons_clock_replay_and_exports(self):
        now = [0.0]
        game = PentominoGame("native", seconds=30, interval=3600, clock=lambda: now[0])
        window = PentominoWindow(game)
        window.show_all()
        window.stop()
        try:
            self.assertTrue(window.action("move", 0, -game.current["y"]))
            self.assertTrue(window.action("rotate", 1))
            self.assertTrue(window.action("flip"))
            self.assertTrue(window.action("place"))
            self.assertEqual(len(game.fixed), 5)
            key = Gdk.EventKey()
            key.keyval = Gdk.keyval_from_name("Down")
            self.assertTrue(window.canvas.on_key(window.canvas, key))
            now[0] = 30
            self.assertFalse(window.on_tick())
            self.assertEqual(game.status, "timed_out")
            self.assertIsNotNone(game.document()["seed"])
            window.seed.set_text("native-new")
            window.mode.set_active_id("masked")
            window.seconds.set_value(120)
            window.new_button.clicked()
            window.stop()
            self.assertEqual(window.game.mode, "masked")
            self.assertIsNone(window.game.next_piece)
            with tempfile.TemporaryDirectory() as directory:
                saved = Path(directory) / "native.json"
                exported = Path(directory) / "native.svg"
                with mock.patch.object(window, "choose_path", side_effect=[saved, exported]):
                    next(button for button in buttons(window) if button.get_label() == "Save session JSON").clicked()
                    next(button for button in buttons(window) if button.get_label() == "Export SVG").clicked()
                self.assertTrue(saved.is_file())
                self.assertTrue(exported.is_file())
                complete = completed_game()
                replay = Path(directory) / "replay.json"
                complete.save(replay)
                with mock.patch.object(window, "choose_path", return_value=replay):
                    next(button for button in buttons(window) if button.get_label() == "Open and verify completed replay").clicked()
                self.assertTrue(window.game.replay_verified)
                self.assertEqual(window.game.status, "won")
                comparison = Path(directory) / "budgets.json"
                with mock.patch.object(window, "choose_path", return_value=comparison):
                    next(button for button in buttons(window) if "Compare" in button.get_label()).clicked()
                self.assertTrue(comparison.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
