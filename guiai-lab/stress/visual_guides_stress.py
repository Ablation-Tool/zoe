from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from docs.render_visual_guides import (
    DOCS, GUIDES, INDEX_OUTPUT, INDEX_SOURCE, generate_all, pdf_metadata,
    prepare_markdown, require_tools,
)


ROOT = DOCS.parent


def rendering_available():
    try:
        require_tools()
    except (OSError, RuntimeError, ValueError):
        return False
    return True


class VisualGuideSourceCase(unittest.TestCase):
    def test_every_top_level_guide_and_provenance_is_registered(self):
        expected = {path.name for path in DOCS.glob("*.md") if path.name != INDEX_SOURCE}
        registered = {source for source, _title, _filename, _hero in GUIDES if "/" not in source}
        self.assertEqual(registered, expected)
        self.assertIn("references/cognitive-field/PROVENANCE.md", {row[0] for row in GUIDES})
        self.assertEqual(len({row[2] for row in GUIDES}), len(GUIDES))
        for source, _title, _filename, hero in GUIDES:
            self.assertTrue((DOCS / source).is_file(), source)
            self.assertTrue((DOCS / hero).is_file(), hero)

    def test_markdown_preparation_adds_visuals_without_duplicate_title(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = prepare_markdown("ARTLINE.md", "Zoe Artline", "images/zoe-artline-native.png", Path(directory))
            text = prepared.read_text(encoding="utf-8")
            self.assertTrue(text.startswith("![Zoe Artline"))
            self.assertNotIn("# Zoe Artline", text)
            self.assertIn("images/zoe-artline-native.png", text)
            qualia = prepare_markdown("QUALIA.md", "Zoe is Quale. Zoe is Red.", "images/zoe-qualia.png", Path(directory))
            converted = qualia.read_text(encoding="utf-8")
            self.assertNotIn('<img src="images/zoe-red.svg"', converted)
            self.assertIn("![Red, the color supplied for Zoe]", converted)

    def test_committed_manifest_matches_actual_pdfs(self):
        manifest = json.loads((DOCS / "visual/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["guide_count"], len(GUIDES))
        self.assertEqual(manifest["pdf_count"], len(GUIDES) + 1)
        for record in manifest["documents"]:
            path = DOCS / "visual" / record["output"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(pdf_metadata(path), {key: record[key] for key in ("title", "pages", "bytes", "sha256")})
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), record["sha256"])


@unittest.skipUnless(rendering_available(), "visual PDF rendering requires Pandoc, pdfLaTeX, newunicodechar, Poppler, and rsvg-convert")
class VisualGuideRenderCase(unittest.TestCase):
    def test_render_complete_collection_and_verify_links(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "visual"
            with contextlib.redirect_stdout(io.StringIO()):
                manifest = generate_all(output)
            self.assertEqual(manifest["guide_count"], len(GUIDES))
            self.assertEqual(manifest["pdf_count"], len(GUIDES) + 1)
            for record in manifest["documents"]:
                path = output / record["output"]
                self.assertTrue(path.is_file(), path)
                self.assertTrue(path.read_bytes().startswith(b"%PDF-"))
                self.assertGreater(record["pages"], 0)
                self.assertGreater(record["bytes"], 10000)
                self.assertEqual(pdf_metadata(path)["sha256"], record["sha256"])
            index = output.parent / INDEX_OUTPUT
            converted = subprocess.run(
                ["pdftohtml", "-i", "-xml", "-stdout", str(index)],
                check=True, stdout=subprocess.PIPE, text=True, stderr=subprocess.DEVNULL,
            ).stdout
            for _source, _title, filename, _hero in GUIDES:
                self.assertIn(filename, converted)
            source_text = (DOCS / INDEX_SOURCE).read_text(encoding="utf-8")
            self.assertIn(INDEX_OUTPUT, source_text)


if __name__ == "__main__":
    unittest.main()
