from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from guiai.gem.cli import main as gem_main
from guiai.gem.evidence_view import main as evidence_main
from guiai.gem.geometry import verify
from guiai.gem.patchbay import _sha
from guiai.gem.runner import verify_vdi
from guiai.gem.unified_cli import main as zoe_main
from guiai.gem.video_library import (
    MAX_OUTPUT, MAX_SNIPPET, VideoLibrary, export_video_library_scene,
    load_video_report, save_video_report, validate_youtube_url,
    video_library_scene, worked_video_report,
)


ORIGINAL = Path("/home/cowboy/.local/bin/vidlib")
ORIGINAL_IMPLEMENTATION = ORIGINAL.with_suffix(".py")


def write_transcript(root, channel, title, topic="timing", url="https://www.youtube.com/watch?v=synthetic"):
    path = root / channel / f"{title}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'''---
title: "{title}"
channel: "{channel}"
date: 20261107
url: {url}
duration: 3m 0s
reading_time: 1 min read (80 words)
pulled: 2026-11-07
---

# {title}

**{channel}** · November 07, 2026 · 3m 0s video → 1 min read

A {topic} reference explains an observation boundary. It is not a hardware measurement.
''' + " bounded context" * 80 + "\n", encoding="utf-8")
    return path


def make_fake_vidlib(root):
    executable = root / "fake vidlib"
    executable.write_text(r'''#!/usr/bin/env python3
import json
from pathlib import Path
import sys
import time

args = sys.argv[1:]
library = Path(args[args.index("--out") + 1])
library.mkdir(parents=True, exist_ok=True)
if "--search" in args:
    query = args[args.index("--search") + 1]
    if query == "slow":
        time.sleep(30)
    if query == "fail":
        print("synthetic search failure", file=sys.stderr)
        sys.exit(7)
    print("x" * 20000)
    sys.exit(0)
if "--index" in args:
    entries = sorted(path for path in library.rglob("*.md") if path.name != "index.md")
    text = "# fake vidlib index\n" + "\n".join(path.name for path in entries) + "\n"
    (library / "index.md").write_text(text, encoding="utf-8")
    print("index rebuilt")
    sys.exit(0)
url = next((value for value in args if value.startswith("https://")), "")
if "fail" in url:
    print("e" * 20000, file=sys.stderr)
    sys.exit(7)
playlist = "--playlist" in args
name = "playlist-reference" if playlist else "video-reference"
path = library / "synthetic-channel" / f"{name}.md"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(f"""---
title: \"{name}\"
channel: \"Synthetic Channel\"
date: 20261107
url: {url}
duration: 1m 0s
reading_time: 1 min read
pulled: 2026-11-07
---

Synthetic {name} about timing. No real network transport occurred in this fixture.
""", encoding="utf-8")
(library / "index.md").write_text("# fake vidlib index\n", encoding="utf-8")
print(json.dumps({"fixture_saved": str(path), "playlist": playlist}))
''', encoding="utf-8")
    executable.chmod(0o755)
    return executable


class VideoLibraryCase(unittest.TestCase):
    def test_missing_library_is_structured_and_does_not_create(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "missing"
            for operation in ("search", "index"):
                with self.subTest(operation=operation):
                    library = VideoLibrary(root, executable="definitely-no-vidlib")
                    report = library.search("timing") if operation == "search" else library.rebuild_index()
                    self.assertEqual(report["status"], "missing-library")
                    self.assertFalse(report["vidlib_invoked"])
                    self.assertFalse(report["network_attempted"])
                    self.assertFalse(report["executed"])
                    self.assertFalse(report["tool"]["available"])
                    self.assertEqual(report["results"], [])
                    self.assertFalse(root.exists())
            self.assertEqual(VideoLibrary(root).search("timing")["query"], "timing")
            root.mkdir()
            with self.assertRaises(FileNotFoundError):
                VideoLibrary(root, executable="definitely-no-vidlib").search("timing")

    def test_url_validation_happens_before_process_or_directory_creation(self):
        invalid = (
            "http://www.youtube.com/watch?v=example",
            "https://youtube.com.example.org/watch?v=example",
            "https://user@youtube.com/watch?v=example",
            "https://youtube.com:444/watch?v=example",
            "https://example.org/watch?v=example",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "library"
            with mock.patch("guiai.gem.video_library._invoke") as invoke:
                for url in invalid:
                    with self.subTest(url=url), self.assertRaises(ValueError):
                        VideoLibrary(root).fetch(url)
                with self.assertRaisesRegex(ValueError, "--playlist"):
                    VideoLibrary(root).fetch("https://www.youtube.com/playlist?list=example")
                with self.assertRaisesRegex(ValueError, "playlist URL"):
                    VideoLibrary(root).fetch("https://www.youtube.com/watch?v=example", playlist=True)
                invoke.assert_not_called()
            self.assertFalse(root.exists())
            self.assertEqual(validate_youtube_url("https://youtu.be/example"), "https://youtu.be/example")
            for query in ("", "  ", "x" * 257):
                with self.assertRaises(ValueError):
                    VideoLibrary(root).search(query)
            with self.assertRaises(ValueError):
                VideoLibrary(root, limit=0)
            with self.assertRaises(ValueError):
                VideoLibrary(root, timeout=0)

    def test_fake_search_index_and_explicit_fetch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library_path = root / "library"
            executable = make_fake_vidlib(root)
            first = write_transcript(library_path, "clocks", "first", "timing")
            write_transcript(library_path, "clocks", "second", "TIMING")
            library = VideoLibrary(library_path, executable, limit=1)
            search = library.search("timing")
            self.assertEqual(search["returncode"], 0)
            self.assertTrue(search["vidlib_invoked"])
            self.assertFalse(search["network_requested"])
            self.assertFalse(search["network_attempted"])
            self.assertFalse(search["executed"])
            self.assertEqual(search["total_matches"], 2)
            self.assertEqual(search["returned_count"], 1)
            self.assertLessEqual(len(search["results"][0]["snippet"]), MAX_SNIPPET)
            self.assertEqual(search["results"][0]["source_sha256"], _sha(first))
            self.assertTrue(search["source_hashes_verified"])
            self.assertFalse(search["source_text_bundled"])
            self.assertLessEqual(len(search["stdout"]), MAX_OUTPUT)
            self.assertTrue(search["stdout_truncated"])

            indexed = library.rebuild_index()
            self.assertTrue(indexed["executed"])
            self.assertTrue(indexed["library_changed"])
            self.assertFalse(indexed["network_attempted"])
            self.assertEqual(indexed["total_matches"], 2)
            self.assertEqual(indexed["library"]["index_sha256"], _sha(library_path / "index.md"))

            fetched = library.fetch("https://www.youtube.com/watch?v=example")
            self.assertTrue(fetched["network_attempted"])
            self.assertTrue(fetched["remote_fetch_succeeded"])
            self.assertTrue(fetched["transcript_downloaded"])
            self.assertTrue(fetched["executed"])
            self.assertEqual(fetched["changed_count"], 1)
            self.assertEqual(fetched["results"][0]["source_url"], "https://www.youtube.com/watch?v=example")
            self.assertFalse(fetched["hardware_accessed"])
            self.assertFalse(fetched["measurement"])
            self.assertFalse(fetched["action_authorized"])

            playlist = library.fetch("https://www.youtube.com/playlist?list=example", playlist=True)
            self.assertTrue(playlist["playlist"])
            self.assertEqual(playlist["changed_count"], 1)
            self.assertEqual(playlist["results"][0]["title"], "playlist-reference")

    def test_exit_codes_timeout_and_bounded_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library_path = root / "library"
            write_transcript(library_path, "clocks", "first")
            executable = make_fake_vidlib(root)
            failed = VideoLibrary(library_path, executable).search("fail")
            self.assertEqual(failed["returncode"], 7)
            self.assertEqual(failed["status"], "command-failed")
            timed_out = VideoLibrary(library_path, executable, timeout=1).search("slow")
            self.assertEqual(timed_out["returncode"], 124)
            self.assertTrue(timed_out["timed_out"])
            self.assertLessEqual(len(timed_out["stderr"]), MAX_OUTPUT)
            failed_fetch = VideoLibrary(library_path, executable).fetch("https://www.youtube.com/watch?v=fail")
            self.assertEqual(failed_fetch["returncode"], 7)
            self.assertTrue(failed_fetch["network_attempted"])
            self.assertFalse(failed_fetch["remote_fetch_succeeded"])
            self.assertFalse(failed_fetch["transcript_downloaded"])
            self.assertTrue(failed_fetch["executed"])
            self.assertTrue(failed_fetch["stderr_truncated"])
            self.assertLessEqual(len(failed_fetch["stderr"]), MAX_OUTPUT)

    def test_report_roundtrip_tamper_detection_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library_path = root / "library"
            source = write_transcript(library_path, "clocks", "first")
            executable = make_fake_vidlib(root)
            report = VideoLibrary(library_path, executable).rebuild_index()
            output = root / "video-report.json"
            save_video_report(report, output)
            loaded = load_video_report(output)
            self.assertEqual(loaded["digest"], report["digest"])
            with self.assertRaises(FileExistsError):
                save_video_report(report, output)
            source.write_text(source.read_text(encoding="utf-8") + "edited\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                load_video_report(output)
            tampered = json.loads(output.read_text(encoding="utf-8"))
            tampered["results"][0]["title"] = "edited title"
            output.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                load_video_report(output, verify_sources=False)
            worked = worked_video_report()
            self.assertTrue(worked["synthetic_example"])
            self.assertFalse(worked["vidlib_invoked"])
            worked_path = root / "worked.json"
            save_video_report(worked, worked_path)
            self.assertEqual(load_video_report(worked_path, verify_sources=False)["digest"], worked["digest"])
            with self.assertRaisesRegex(ValueError, "worked-example"):
                load_video_report(worked_path)

    def test_cli_forwarding_output_and_original_exit_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library_path = root / "library"
            write_transcript(library_path, "clocks", "first")
            executable = make_fake_vidlib(root)
            for index, entrypoint in enumerate((evidence_main, gem_main, zoe_main)):
                with self.subTest(entrypoint=entrypoint.__module__):
                    output = root / f"report-{index}.json"
                    arguments = ["video", "--library", str(library_path), "--vidlib", str(executable), "--search", "timing", "--output", str(output)]
                    if entrypoint is not evidence_main:
                        arguments.insert(0, "evidence")
                    with contextlib.redirect_stdout(io.StringIO()) as stdout:
                        self.assertEqual(entrypoint(arguments), 0)
                    printed = json.loads(stdout.getvalue())
                    self.assertEqual(printed["operation"], "search")
                    self.assertEqual(load_video_report(output)["total_matches"], 1)
            with contextlib.redirect_stdout(io.StringIO()):
                code = evidence_main(["video", "--library", str(library_path), "--vidlib", str(executable), "--url", "https://www.youtube.com/watch?v=fail"])
            self.assertEqual(code, 7)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(evidence_main(["video", "--library", str(library_path), "--search", "timing", "--playlist"]), 2)
            occupied = root / "occupied.json"
            occupied.write_text("keep", encoding="utf-8")
            with mock.patch("guiai.gem.evidence_view.VideoLibrary") as constructor, contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(evidence_main(["video", "--library", str(library_path), "--url", "https://www.youtube.com/watch?v=example", "--output", str(occupied)]), 2)
            constructor.assert_not_called()
            self.assertEqual(occupied.read_text(encoding="utf-8"), "keep")

    def test_transcript_symlink_cannot_escape_library(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library_path = root / "library"
            outside = write_transcript(root / "outside", "clocks", "first")
            (library_path / "clocks").mkdir(parents=True)
            (library_path / "clocks/link.md").symlink_to(outside)
            with mock.patch("guiai.gem.video_library._invoke") as invoke, self.assertRaisesRegex(ValueError, "outside"):
                VideoLibrary(library_path, make_fake_vidlib(root)).search("timing")
            invoke.assert_not_called()

    def test_verified_scene_exports_and_cli_scene(self):
        scene, summary = video_library_scene()
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        self.assertTrue(summary["synthetic_example"])
        self.assertFalse(summary["transcript_is_measurement"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for suffix in ("svg", "png", "gem"):
                output = root / f"vidlib.{suffix}"
                self.assertEqual(export_video_library_scene(output), output)
                self.assertTrue(output.is_file())
                with self.assertRaises(FileExistsError):
                    export_video_library_scene(output)
            scene_path = root / "empty.svg"
            with contextlib.redirect_stdout(io.StringIO()):
                code = evidence_main(["video", "--library", str(root / "missing"), "--search", "timing", "--scene-output", str(scene_path)])
            self.assertEqual(code, 0)
            self.assertTrue(scene_path.is_file())


@unittest.skipUnless(ORIGINAL.is_file() and os.access(ORIGINAL, os.X_OK) and ORIGINAL_IMPLEMENTATION.is_file(), "the original vidlib executable is unavailable")
class OriginalVidlibCase(unittest.TestCase):
    def test_json3_markdown_search_and_index_without_network(self):
        specification = importlib.util.spec_from_file_location("original_vidlib_for_zoe_tests", ORIGINAL_IMPLEMENTATION)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json3 = root / "transcript.en.json3"
            json3.write_text(json.dumps({"events": [
                {"tStartMs": 1000, "dDurationMs": 1200, "segs": [{"utf8": "Timing "}, {"utf8": "evidence"}]},
                {"tStartMs": 2600, "dDurationMs": 900, "segs": [{"utf8": " remains cited reference text."}]},
            ]}), encoding="utf-8")
            segments = module.parse_json3(json3)
            self.assertEqual(segments[0], {"text": "Timing evidence", "start": 1.0, "end": 2.2})
            markdown = module.generate_markdown(
                {"title": "Synthetic Clock Note", "channel": "Zoe Tests", "upload_date": "20261107", "duration": 3},
                [segment["text"] for segment in segments],
                "https://www.youtube.com/watch?v=synthetic",
            )
            source = root / "library/zoe-tests/synthetic-clock-note.md"
            source.parent.mkdir(parents=True)
            source.write_text(markdown, encoding="utf-8")
            library = VideoLibrary(root / "library", ORIGINAL)
            found = library.search("Timing evidence")
            self.assertEqual(found["returncode"], 0, found["stderr"])
            self.assertEqual(found["total_matches"], 1)
            self.assertFalse(found["network_requested"])
            self.assertFalse(found["network_attempted"])
            self.assertFalse(found["executed"])
            self.assertEqual(found["tool"]["implementation_sha256"], _sha(ORIGINAL_IMPLEMENTATION))
            indexed = library.rebuild_index()
            self.assertEqual(indexed["returncode"], 0, indexed["stderr"])
            self.assertTrue(indexed["executed"])
            self.assertFalse(indexed["network_attempted"])
            self.assertIn("Synthetic Clock Note", (root / "library/index.md").read_text(encoding="utf-8"))
            output = root / "original-search.json"
            save_video_report(found, output)
            self.assertEqual(load_video_report(output)["results"][0]["source_sha256"], _sha(source))


if __name__ == "__main__":
    unittest.main()
