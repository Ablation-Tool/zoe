from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from guiai.gem.cli import main as gem_main
from guiai.gem.cog import Cog, _digest, demo_cog, text_from_html, tokenize
from guiai.gem.patchbay_view import main as patchbay_main
from guiai.gem.unified_cli import main as zoe_main


BOOK = Path("/home/cowboy/captures/build-a-llm/011_chapter-3.html")


class CogModelCase(unittest.TestCase):
    def test_probabilities_forward_backward_and_limits(self):
        model = demo_cog()
        distribution = model.distribution("inspect")
        self.assertAlmostEqual(sum(item["probability"] for item in distribution), 1.0)
        self.assertEqual(distribution[0]["token"], "<s>")
        self.assertEqual(next(item["count"] for item in distribution if item["token"] == "the"), 1)
        self.assertEqual(max(distribution, key=lambda item: item["probability"])["token"], "the")
        forward = model.walk("inspect", steps=6, tau=0.05)
        backward = model.walk("update", steps=6, reverse=True)
        self.assertEqual(forward["direction"], "forward")
        self.assertEqual(backward["direction"], "backward")
        self.assertTrue(forward["text"].startswith("inspect the artifact"))
        self.assertEqual(backward["text"], "inspect the update")
        self.assertFalse(forward["command_authorized"])
        self.assertFalse(forward["fact_claimed"])
        self.assertTrue(forward["review_required"])
        self.assertTrue(all(step["distribution_sha256"] for step in forward["steps"]))
        for arguments in ({"steps": 0}, {"steps": 33}, {"steps": True}, {"tau": -1}, {"tau": 1}):
            with self.assertRaises(ValueError):
                model.walk("inspect", **arguments)
        with self.assertRaises(ValueError):
            model.distribution("inspect", alpha=0)
        with self.assertRaises(ValueError):
            Cog.train([])
        with self.assertRaises(ValueError):
            Cog.train([("", "empty")])
        self.assertEqual(model.distribution("unseen-token")[2]["token"], "<unk>")

    def test_html_source_identity_roundtrip_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.html"
            source.write_text("<html><style>hidden tokens</style><body><p>Inspect the artifact.</p><script>ignore this</script></body></html>", encoding="utf-8")
            model = Cog.from_paths([source])
            self.assertNotIn("hidden", model.vocabulary)
            self.assertNotIn("ignore", model.vocabulary)
            self.assertEqual(model.documents[0]["file_sha256"], hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(model.documents[0]["file_bytes"], source.stat().st_size)
            self.assertIn("inspect", model.vocabulary)
            path = Path(directory) / "cog.json"
            self.assertEqual(model.save(path), path)
            loaded = Cog.load(path)
            self.assertEqual(loaded.document(), model.document())
            self.assertEqual(loaded.walk("inspect")["text"], model.walk("inspect")["text"])
            with self.assertRaises(FileExistsError):
                model.save(path)
            document = model.document()
            document["total_tokens"] = "invalid"
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                Cog.load(path)
            document["digest"] = _digest({key: value for key, value in document.items() if key != "digest"})
            path.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaises(ValueError):
                Cog.load(path)
            self.assertEqual(tokenize("A token, and 2.5."), ["a", "token", ",", "and", "2.5", "."])
            self.assertNotIn("script", text_from_html("<script>bad()</script>plain"))

    def test_cli_training_model_reuse_and_forwarding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {}
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(patchbay_main(["cog", "--model-output", str(root / "model.json"), "--output", str(root / "direct.json")]), 0)
                self.assertEqual(patchbay_main(["cog", "--model", str(root / "model.json"), "--prompt", "inspect", "--reverse", "update", "--output", str(root / "loaded.json")]), 0)
                self.assertEqual(gem_main(["patchbay", "cog", "--output", str(root / "gem.json")]), 0)
                self.assertEqual(zoe_main(["patchbay", "cog", "--output", str(root / "zoe.json")]), 0)
            for name in ("direct.json", "loaded.json", "gem.json", "zoe.json"):
                outputs[name] = json.loads((root / name).read_text(encoding="utf-8"))
                self.assertFalse(outputs[name]["command_authorized"])
                self.assertEqual(outputs[name]["accessible_volume_credit"], "Nicholas Michael Kloster alone, March 6, 2026")
            self.assertEqual(outputs["direct.json"]["forward"]["text"], outputs["loaded.json"]["forward"]["text"])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(patchbay_main(["cog", "missing.txt", "--model", str(root / "model.json")]), 2)


@unittest.skipUnless(BOOK.is_file(), "the user-supplied LLM book capture is unavailable")
class CogBookCase(unittest.TestCase):
    def test_real_attention_chapter(self):
        model = Cog.from_paths([BOOK])
        self.assertEqual(model.total_tokens, 14206)
        self.assertEqual(len(model.vocabulary), 512)
        self.assertEqual(model.documents[0]["file_sha256"], hashlib.sha256(BOOK.read_bytes()).hexdigest())
        forward = model.walk("attention", steps=4)
        backward = model.walk("attention", steps=4, reverse=True)
        self.assertTrue(forward["steps"])
        self.assertTrue(backward["steps"])
        self.assertTrue(all(step["accessible_volume"] >= 1 for step in forward["steps"]))
        self.assertFalse(forward["fact_claimed"])


if __name__ == "__main__":
    unittest.main()
