from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.geometry import verify
from guiai.gem.leadership import export_leadership, inspect_library, leadership_scene, search_library
from guiai.gem.leadership_view import main as leadership_main
from guiai.gem.practice import PracticeLog, _digest, demo_log
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main


ROOT = Path("/home/cowboy/Desktop/Leadership")


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


class PracticeCase(unittest.TestCase):
    def test_practice_advice_failure_learning_and_variety(self):
        log = PracticeLog()
        self.assertEqual(log.next_question(), "What will you try, and what will you notice?")
        event = log.add_practice(
            "A simple decision needs to be made.",
            "I make the decision without asking for context.",
            "The decision works technically but confuses someone.",
            "Ask for context before choosing.",
            frame=["simple", "decision"],
            timestamp="2026-11-06T10:00:00+00:00",
        )
        self.assertEqual(event["sequence"], 1)
        self.assertFalse(event["execution_authorized"])
        self.assertIn("perspective", log.next_question())
        log.add_practice(
            "A difficult conversation needs a different approach.",
            "I repeat my point more loudly.",
            "The other person stops offering information.",
            "Ask a question and listen before replying.",
            frame=["simple", "decision"],
            advice="A colleague suggests listening first.",
            mistake="I treated volume as clarity.",
            learning="Hearing a concern is not agreeing with it.",
            support="Time for both people to speak.",
            unknown="What concern has not been expressed?",
            stop_condition="Pause if the exchange becomes disrespectful.",
            timestamp="2026-11-06T11:00:00+00:00",
        )
        log.add_practice(
            "The same situation happens again.",
            "I ask and listen.",
            "I understand a constraint I had missed.",
            "Change the setting and compare what happens.",
            frame=["simple", "decision"],
            advice="Remember to ask.",
            mistake="I initially forgot the lesson.",
            learning="Context changed the decision.",
            support="A quiet place to talk.",
            unknown="Will this work with someone else?",
            stop_condition="Stop if the other person wants space.",
            timestamp="2026-11-06T12:00:00+00:00",
        )
        self.assertIn("one condition", log.next_question())
        log.add_practice(
            "A complex request arrives.",
            "I ask for help instead of guarding the task.",
            "The work improves and another person grows.",
            "Review what made shared ownership useful.",
            frame=["complex", "support"],
            advice="Share the context.",
            mistake="I waited too long to ask.",
            learning="Help can create capability rather than dependency.",
            support="Clear priorities.",
            unknown="Which part still needs practice?",
            stop_condition="Pause if the request exceeds safe capacity.",
            timestamp="2026-11-06T13:00:00+00:00",
        )
        self.assertIn("smallest useful next experiment", log.next_question())
        before = dict(log.events[0])
        log.add_correction(1, "I can ask for context without surrendering responsibility.", timestamp="2026-11-06T14:00:00+00:00")
        self.assertEqual(log.events[0], before)
        self.assertEqual(log.events[-1]["kind"], "correction")
        self.assertEqual(log.events[-1]["corrects"], 1)
        self.assertEqual(log.review()["score"], None)
        self.assertFalse(log.review()["autonomous_action"])
        with self.assertRaises(ValueError):
            log.add_practice("", "action", "outcome", "next")
        with self.assertRaises(ValueError):
            log.add_practice("situation", "action", "outcome", "next", frame=list("abcdefg"))
        with self.assertRaises(ValueError):
            log.add_correction(999, "Not attached to evidence")
        with self.assertRaises(ValueError):
            log.add_practice("s", "a", "o", "n", timestamp="2026-11-06T14:00:00")

    def test_chain_roundtrip_tamper_and_no_overwrite(self):
        log = demo_log()
        self.assertTrue(log.synthetic)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "practice.json"
            log.save(path)
            self.assertEqual(PracticeLog.load(path).document(), log.document())
            with self.assertRaises(FileExistsError):
                log.save(path)
            tampered = log.document()
            tampered["events"][0]["action"] = "edited action"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                PracticeLog.load(path)
            tampered = log.document()
            tampered["events"][1]["previous_hash"] = "0" * 64
            tampered["digest"] = _digest({key: value for key, value in tampered.items() if key != "digest"})
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(ValueError):
                PracticeLog.load(path)
            tampered = log.document()
            tampered["events"][0]["event_hash"] = "0" * 64
            tampered["digest"] = _digest({key: value for key, value in tampered.items() if key != "digest"})
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "event hash mismatch"):
                PracticeLog.load(path)

    def test_scene_exports_and_cli_practice_correction(self):
        scene, report = leadership_scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertIsNone(report["score"])
        scene, _ = default_document("leadership")
        self.assertTrue(verify(scene).passed)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ("svg", "png", "gem"):
                output = root / f"garden.{suffix}"
                self.assertEqual(export_leadership(output), output)
                with self.assertRaises(FileExistsError):
                    export_leadership(output)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(leadership_main(["practice", "--situation", "A small task", "--action", "I tried", "--outcome", "It missed", "--next-try", "Ask for feedback", "--output", str(root / "one.json")]), 0)
                self.assertEqual(leadership_main(["practice", "--input", str(root / "one.json"), "--situation", "A harder task", "--action", "I asked", "--outcome", "I learned", "--next-try", "Change one condition", "--advice", "Ask early", "--mistake", "I waited", "--learning", "Context matters", "--support", "Time", "--unknown", "What else changed?", "--stop-condition", "Pause if trust suffers", "--output", str(root / "two.json")]), 0)
                self.assertEqual(leadership_main(["correct", "--input", str(root / "two.json"), "--sequence", "1", "--learning", "Feedback is part of the attempt", "--output", str(root / "three.json")]), 0)
                self.assertEqual(gem_main(["leadership", "scene", "--input", str(root / "three.json"), "--output", str(root / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["leadership", "scene", "--input", str(root / "three.json"), "--output", str(root / "zoe.svg")]), 0)
            loaded = PracticeLog.load(root / "three.json")
            self.assertEqual(len(loaded.events), 3)
            self.assertEqual(loaded.events[-1]["kind"], "correction")
            self.assertFalse(loaded.events[-1]["execution_authorized"])
            self.assertIn("Zoe Leadership Garden", (root / "gem.svg").read_text(encoding="utf-8"))
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(leadership_main(["practice", "--situation", "s", "--action", "a", "--outcome", "o", "--next-try", "n", "--output", str(root / "one.json")]), 2)

    def test_packaged_worked_example(self):
        example = Path(__file__).resolve().parents[2] / "guiai-lab/docs/examples/leadership-practice.json"
        log = PracticeLog.load(example)
        self.assertTrue(log.synthetic)
        self.assertTrue(log.review()["synthetic_example"])
        self.assertEqual(log.review()["event_label"], "worked-example events")
        self.assertEqual(len(log.events), 3)

    def test_search_validation(self):
        with self.assertRaises(ValueError):
            search_library(ROOT, "")
        with self.assertRaises(ValueError):
            search_library(ROOT, "women", 0)


@unittest.skipUnless(ROOT.is_dir(), "the user-supplied leadership library is unavailable")
class LeadershipLibraryCase(unittest.TestCase):
    def test_actual_reference_catalog_and_personal_boundaries(self):
        report = inspect_library(ROOT)
        self.assertEqual(len(report["documents"]), 6)
        self.assertEqual({document["id"]: document["pages"] for document in report["documents"]}, {
            "soldier-statesmen": 316,
            "heritage": 313,
            "care": 204,
            "nco": 370,
            "support": 336,
            "protection": 224,
        })
        self.assertEqual(len(report["external_reading"]), 3)
        self.assertTrue(all(not row["local_file_claimed"] for row in report["external_reading"]))
        self.assertTrue(report["external_reading"][-1]["distinct_from_geneva_conventions"])
        self.assertFalse(report["books_replace_practice"])
        self.assertFalse(report["personal_photo_bundled"])
        self.assertFalse(report["personal_sources"]["note"]["bundled"])
        self.assertFalse(report["personal_sources"]["photo"]["bundled"])
        self.assertIn("Leadership Development.txt", report["personal_sources"]["note"]["path"])
        scene, _ = leadership_scene(demo_log(), report)
        self.assertTrue(verify(scene).passed, verify(scene).text())

    def test_actual_pdf_snippets_and_cli(self):
        result = search_library(ROOT, "women", 3)
        self.assertEqual(result["snippet_count"], 3)
        self.assertEqual(result["documents_searched"], 6)
        self.assertTrue(result["complete_extraction"])
        self.assertFalse(result["ocr_performed"])
        for snippet in result["snippets"]:
            self.assertGreater(snippet["pdf_page"], 0)
            self.assertIn("women", snippet["text"].casefold())
            self.assertEqual(len(snippet["source_sha256"]), 64)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(leadership_main(["library", "--root", str(ROOT), "--output", str(root / "library.json")]), 0)
                self.assertEqual(leadership_main(["search", "--root", str(ROOT), "--query", "women", "--limit", "2", "--output", str(root / "snippets.json")]), 0)
            library = json.loads((root / "library.json").read_text(encoding="utf-8"))
            self.assertEqual(len(library["documents"]), 6)
            self.assertEqual(json.loads((root / "snippets.json").read_text(encoding="utf-8"))["snippet_count"], 2)


@unittest.skipUnless(HAS_GTK, "native leadership tests require GTK, Cairo, and an X11 DISPLAY")
class LeadershipNativeCase(unittest.TestCase):
    def test_record_save_load_library_and_error_preservation(self):
        window = AtlasWindow("leadership")
        try:
            original_count = len(window.leadership_log.events)
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                values = {
                    "leadership_situation": "A real small choice",
                    "leadership_action": "I asked for context",
                    "leadership_outcome": "The next step became clearer",
                    "leadership_next_try": "Ask even earlier",
                    "leadership_mistake": "I initially assumed",
                    "leadership_advice": "Listen first",
                    "leadership_learning": "Context changes the plan",
                    "leadership_support": "A few quiet minutes",
                    "leadership_unknown": "What else is unknown?",
                    "leadership_stop": "Pause if trust suffers",
                }
                for key, value in values.items():
                    window.controls[key].set_text(value)
                window.record_leadership_practice()
                self.assertEqual(len(window.leadership_log.events), original_count + 1)
                self.assertIn("no leadership score", window.summary.get_text())
                previous = window.leadership_log
                window.controls["leadership_action"].set_text("")
                window.record_leadership_practice()
                self.assertIs(window.leadership_log, previous)
                self.assertIn("Practice was not recorded", window.summary.get_text())
                log_path = root / "practice.json"
                window.export_current(log_path)
                self.assertTrue(log_path.is_file())
                with self.assertRaises(FileExistsError):
                    window.export_current(log_path)
                window.controls["leadership_log_path"].set_text(str(root / "missing.json"))
                scene = window.scene
                window.load_leadership_log()
                self.assertIs(window.leadership_log, previous)
                self.assertIs(window.scene, scene)
                self.assertIn("Practice log load failed", window.summary.get_text())
                window.controls["leadership_log_path"].set_text(str(log_path))
                window.load_leadership_log()
                self.assertEqual(len(window.leadership_log.events), original_count + 1)
                self.assertEqual(window.leadership_log_path, str(log_path))
                if ROOT.is_dir():
                    window.controls["leadership_library_root"].set_text(str(ROOT))
                    window.inspect_leadership_library()
                    self.assertEqual(len(window.leadership_library["documents"]), 6)
                svg = window.export_current(root / "garden.svg")
                self.assertTrue(svg.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
