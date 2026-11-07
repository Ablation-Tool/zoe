from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import wave

from guiai.gem.atlas import default_document
from guiai.gem.cli import main as gem_main
from guiai.gem.evidence import (
    EvidenceIndex, demo_index, export_navigator, navigator_scene, save_evidence_report,
    shadow_finding, write_navigator_gallery,
)
from guiai.gem.evidence_view import main as evidence_main
from guiai.gem.geometry import verify
from guiai.gem.patchbay import _sha
from guiai.gem.runner import verify_vdi
from guiai.gem.twin import export_wav, load_timeline, save_timeline, timing_replay
from guiai.gem.unified_cli import main as zoe_main


GALLERY = Path("/media/cowboy/research/CERN/Boutique/10-accessible/galleries/document-images")
INDEX = GALLERY / "index.json"
FINDINGS = Path("/media/cowboy/research/CERN/analysis/felix-flx155/findings.json")


try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from guiai.gem.atlas_view import AtlasWindow
    HAS_GTK = bool(os.environ.get("DISPLAY"))
except (ImportError, ValueError):
    HAS_GTK = False


def make_gallery(root):
    corpus = root
    gallery = corpus / "10-accessible" / "galleries" / "document-images"
    document = corpus / "docs/example.pdf"
    document.parent.mkdir(parents=True)
    document.write_bytes(b"source document")
    image = gallery / "C1-foundational/C1-N1-Slate-reference-guide--deadbeef.png"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"preview")
    (gallery / "legacy.png").symlink_to(image.relative_to(gallery))
    record = {
        "bytes": 15,
        "color": "Slate",
        "complexity": 1,
        "complexity_name": "foundational",
        "document": "docs/example.pdf",
        "document_sha256": _sha(document),
        "format": ".pdf",
        "image": "C1-foundational/C1-N1-Slate-reference-guide--deadbeef.png",
        "label": "C1-N1-Slate-reference-guide--deadbeef",
        "legacy_image": "legacy.png",
        "novelty": 1,
        "novelty_name": "established-reference",
        "original": "docs/example.pdf",
        "preview_sha256": _sha(image),
        "purpose": "reference-guide",
        "what": "Example document",
        "why": "A synthetic source identity example.",
    }
    document_data = {
        "schema_version": 2,
        "document_count": 1,
        "image_count": 1,
        "files": [record],
        "distribution": {
            "color": {"Slate": 1}, "complexity": {"1": 1},
            "novelty": {"1": 1}, "purpose": {"reference-guide": 1},
        },
    }
    (gallery / "index.json").write_text(json.dumps(document_data), encoding="utf-8")
    return gallery, document, image


class EvidenceModelCase(unittest.TestCase):
    def test_index_identity_filter_curriculum_and_tamper(self):
        with tempfile.TemporaryDirectory() as directory:
            gallery, document, image = make_gallery(Path(directory))
            index = EvidenceIndex.load(gallery / "index.json", verify=True)
            self.assertTrue(index.source_hashes_verified)
            self.assertEqual(index.query("example")["returned_count"], 1)
            self.assertEqual(index.curriculum(1)["level_name"], "foundational")
            self.assertFalse(index.curriculum(1)["complexity_is_person_rating"])
            self.assertEqual(index.query("example", complexity=4)["total_matches"], 0)
            document.write_bytes(b"changed source")
            with self.assertRaisesRegex(ValueError, "source hash mismatch"):
                EvidenceIndex.load(gallery / "index.json", verify=True)
            data = json.loads((gallery / "index.json").read_text(encoding="utf-8"))
            data["files"][0]["label"] = "invalid"
            (gallery / "index.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(ValueError):
                EvidenceIndex.load(gallery / "index.json")

    def test_demo_bridge_ladder_manifest_review_and_scene(self):
        index = demo_index()
        for identifier in range(1, 8):
            bridge = index.bridge(identifier)
            self.assertTrue(bridge["proposal_only"])
            self.assertFalse(bridge["executed"])
            self.assertFalse(bridge["hardware_connection_claimed"])
        retrieved = index.retrieve("missing-evidence")
        self.assertTrue(retrieved["decline_to_act"])
        self.assertFalse(retrieved["llm_called"])
        self.assertFalse(retrieved["executed"])
        ladder = index.ladder()
        self.assertEqual(len(ladder["observations"]), 12)
        self.assertFalse(ladder["direct_hardware_bridge"])
        self.assertFalse(ladder["equivalence_claimed"])
        self.assertEqual({row["source_model"] for row in ladder["observations"]}, {"LCB", "STAR/Flink"})
        manifest = index.manifest()
        self.assertIn("fcheck -w", manifest["blocked_operations"])
        self.assertIn("fpepo with a data word", manifest["blocked_operations"])
        self.assertFalse(manifest["shell_execution"])
        self.assertFalse(manifest["driver_loading"])
        self.assertFalse(manifest["register_writes"])
        review = index.design_review()
        self.assertEqual(len(review["checklist"]), 4)
        self.assertFalse(review["hardware_connection_claimed"])
        scene, _ = navigator_scene(index, 4)
        self.assertTrue(verify(scene).passed, verify(scene).text())
        self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())
        scene, _ = default_document("evidence")
        self.assertTrue(verify(scene).passed)
        with self.assertRaises(ValueError):
            index.ladder(["invented-operation"])
        with self.assertRaises(ValueError):
            index.bridge(8)

    def test_replay_roundtrip_audio_and_exports(self):
        first = timing_replay()
        second = timing_replay()
        self.assertEqual(first["digest"], second["digest"])
        self.assertEqual(first["observations"], second["observations"])
        self.assertEqual(first["descriptors"], second["descriptors"])
        self.assertEqual(len(first["observations"]), 64)
        self.assertTrue(any(event["dma_status"] == "backpressure" for event in first["observations"]))
        self.assertTrue(all(not event["hardware_accessed"] for event in first["observations"] if "hardware_accessed" in event))
        self.assertFalse(first["hardware_accessed"])
        self.assertFalse(first["measured"])
        self.assertFalse(first["physical_connection_claimed"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            save_timeline(first, root / "timeline.json")
            self.assertEqual(load_timeline(root / "timeline.json")["digest"], first["digest"])
            tampered = json.loads((root / "timeline.json").read_text(encoding="utf-8"))
            tampered["observations"][0]["sequence"] = 99
            (root / "timeline.json").write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_timeline(root / "timeline.json")
            wav_a, report_a = export_wav(first, root / "a.wav")
            wav_b, report_b = export_wav(second, root / "b.wav")
            self.assertEqual(wav_a.read_bytes(), wav_b.read_bytes())
            self.assertEqual(report_a["sha256"], report_b["sha256"])
            self.assertFalse(report_a["live_detector_sound"])
            self.assertFalse(report_a["alarm"])
            self.assertFalse(report_a["autoplay"])
            with wave.open(str(wav_a), "rb") as stream:
                self.assertEqual(stream.getframerate(), 8000)
                self.assertEqual(stream.getnchannels(), 1)
                self.assertEqual(stream.getnframes(), 25600)
            with self.assertRaises(FileExistsError):
                export_wav(first, wav_a)
            for suffix in ("svg", "png", "gem"):
                output = root / f"evidence.{suffix}"
                self.assertEqual(export_navigator(output, timeline=first), output)
                with self.assertRaises(FileExistsError):
                    export_navigator(output, timeline=first)
            report = root / "report.json"
            save_evidence_report({"instrument": "test", "executed": False}, report)
            self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["digest"])
            with self.assertRaises(FileExistsError):
                save_evidence_report({"instrument": "test", "executed": False}, report)


class PackagedEvidenceCase(unittest.TestCase):
    def test_timeline_and_wav_reproduce_exactly(self):
        root = Path(__file__).resolve().parents[2] / "guiai-lab/docs/examples"
        timeline = load_timeline(root / "evidence-twin.json")
        self.assertEqual(timeline["event_count"], 4)
        with tempfile.TemporaryDirectory() as directory:
            output, report = export_wav(timeline, Path(directory) / "recreated.wav")
            self.assertEqual(output.read_bytes(), (root / "evidence-sonification.wav").read_bytes())
            self.assertEqual(report["sha256"], "065c7a80aa0412b31195dbb09ad49deb7cb44a0c2c9e2f12c122e7879d9c516c")
            self.assertEqual(report["duration_seconds"], 0.2)
            self.assertFalse(report["live_detector_sound"])


@unittest.skipUnless(INDEX.is_file(), "the categorized CERN gallery is unavailable")
class CernEvidenceCase(unittest.TestCase):
    def test_real_retrieval_bridges_and_verification(self):
        index = EvidenceIndex.load(INDEX, verify=True)
        self.assertEqual(len(index.records), 226)
        self.assertEqual(index.distribution()["complexity"], {"1": 40, "2": 49, "3": 125, "4": 12})
        counts = [len(index.bridge(identifier)["components"]) for identifier in range(1, 8)]
        self.assertEqual(counts, [5, 5, 4, 0, 0, 3, 0])
        self.assertEqual(sum(counts), 17)
        for identifier in range(1, 8):
            self.assertTrue(all(component["exists"] for component in index.bridge(identifier)["components"]))
        retrieval = index.retrieve("TIM3C_Clock_Flow")
        self.assertEqual(retrieval["observations"][0]["label"], "C3-N1-Amber-clock-timing--78d93846")
        self.assertFalse(retrieval["llm_called"])
        self.assertFalse(retrieval["executed"])
        self.assertTrue(index.retrieve("definitely-not-a-document")["decline_to_act"])
        curriculum = index.curriculum(4, "FELIX")
        self.assertTrue(curriculum["examples"])
        self.assertFalse(curriculum["complexity_is_person_rating"])
        self.assertEqual(index.manifest()["default_mode"], "observe-only")
        self.assertFalse(index.design_review()["hardware_connection_claimed"])

    def test_real_timeline_audio_gallery_and_shadow(self):
        index = EvidenceIndex.load(INDEX)
        timeline = timing_replay(index=index)
        self.assertEqual(len(timeline["source_bridge"]["components"]), 5)
        self.assertTrue(timeline["observations"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gallery, selection = write_navigator_gallery(index, root / "gallery.html", "TIM3C_Clock_Flow", limit=1)
            self.assertEqual(selection["returned_count"], 1)
            text = gallery.read_text(encoding="utf-8")
            self.assertIn("C3-integrated/C3-N1-Amber-clock-timing--78d93846.png", text)
            self.assertIn("96e9f0a51d3ba1e3b9a1fa5ece05688341f220ada54cf451fdbbfe68263d0611", text)
            wav, audio = export_wav(timeline, root / "evidence.wav")
            self.assertFalse(audio["live_detector_sound"])
            self.assertFalse(audio["alarm"])
        finding = shadow_finding(FINDINGS)
        self.assertEqual(finding["observation"]["wns_ns"], -0.096)
        self.assertFalse(finding["observation"]["timing_met"])
        self.assertFalse(finding["llm_called"])
        self.assertFalse(finding["executed"])

    def test_all_cli_workflows(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outputs = {
                "scene": root / "scene.svg", "query": root / "query.json", "bridge": root / "bridge.json",
                "curriculum": root / "curriculum.json", "verify": root / "verify.json",
                "timeline": root / "timeline.json", "audio": root / "timeline.wav",
                "ladder": root / "ladder.json", "manifest": root / "manifest.json",
                "shadow": root / "shadow.json", "gallery": root / "gallery.html",
            }
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(evidence_main(["scene", "--index", str(INDEX), "--replay", "--output", str(outputs["scene"])]), 0)
                self.assertEqual(evidence_main(["query", "--index", str(INDEX), "--query", "TIM3C_Clock_Flow", "--output", str(outputs["query"])]), 0)
                self.assertEqual(evidence_main(["bridge", "--index", str(INDEX), "--id", "1", "--output", str(outputs["bridge"])]), 0)
                self.assertEqual(evidence_main(["curriculum", "--index", str(INDEX), "--level", "1", "--output", str(outputs["curriculum"])]), 0)
                self.assertEqual(evidence_main(["verify", "--index", str(INDEX), "--output", str(outputs["verify"])]), 0)
                self.assertEqual(evidence_main(["twin", "--index", str(INDEX), "--events", "4", "--output", str(outputs["timeline"]), "--wav", str(outputs["audio"])]), 0)
                self.assertEqual(evidence_main(["ladder", "--output", str(outputs["ladder"])]), 0)
                self.assertEqual(evidence_main(["manifest", "--index", str(INDEX), "--output", str(outputs["manifest"])]), 0)
                self.assertEqual(evidence_main(["shadow", "--finding", str(FINDINGS), "--output", str(outputs["shadow"])]), 0)
                self.assertEqual(evidence_main(["gallery", "--index", str(INDEX), "--query", "TIM3C_Clock_Flow", "--limit", "1", "--output", str(outputs["gallery"])]), 0)
                self.assertEqual(gem_main(["evidence", "scene", "--output", str(root / "gem.svg")]), 0)
                self.assertEqual(zoe_main(["evidence", "scene", "--output", str(root / "zoe.svg")]), 0)
            verification = json.loads(outputs["verify"].read_text(encoding="utf-8"))
            self.assertEqual(verification["document_count"], 226)
            self.assertEqual(verification["compatibility_links_verified"], 226)
            self.assertEqual(verification["bridge_links_verified"], 17)
            self.assertEqual(verification["missing_bridge_targets"], [])
            self.assertTrue(verification["source_hashes_verified"])
            self.assertTrue(outputs["timeline"].is_file())
            self.assertTrue(outputs["audio"].is_file())
            self.assertIn("Zoe Evidence Navigator", outputs["scene"].read_text(encoding="utf-8"))


@unittest.skipUnless(HAS_GTK, "native evidence tests require GTK, Cairo, and an X11 DISPLAY")
class EvidenceNativeCase(unittest.TestCase):
    def test_load_verify_replay_query_and_exports(self):
        window = AtlasWindow("evidence")
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                window.controls["evidence_index_path"].set_text(str(INDEX))
                window.load_evidence_index()
                self.assertEqual(len(window.evidence_index.records), 226)
                window.verify_evidence_index()
                self.assertTrue(window.evidence_index.source_hashes_verified)
                window.controls["evidence_bridge"].set_active_id("2")
                window.controls["evidence_query"].set_text("TIM3C_Clock_Flow")
                window.present_evidence()
                self.assertEqual(window.navigator_bridge_id, 2)
                self.assertEqual(window.navigator_query, "TIM3C_Clock_Flow")
                window.replay_evidence_timeline()
                self.assertEqual(window.navigator_timeline["event_count"], 64)
                self.assertTrue(verify(window.scene).passed)
                index = window.evidence_index
                window.controls["evidence_index_path"].set_text(str(root / "missing.json"))
                window.load_evidence_index()
                self.assertIs(window.evidence_index, index)
                self.assertIn("Gallery index load failed", window.summary.get_text())
                wav = root / "evidence.wav"
                window.export_current(wav)
                self.assertTrue(wav.is_file())
                with self.assertRaises(FileExistsError):
                    window.export_current(wav)
                svg = window.export_current(root / "evidence.svg")
                self.assertTrue(svg.is_file())
        finally:
            window.destroy()


if __name__ == "__main__":
    unittest.main()
