"""Unit, unseen 3-repo surgery, 160-turn stream, multi-step tools, two-gear calibration & verifier tests for L5 Phase 3."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib import request as urlrequest

ZOE_ROOT = Path(__file__).resolve().parents[3]
for rel in ("components/Zoe-Autonomy/src", "guiai-lab"):
    p = str(ZOE_ROOT / rel)
    if p not in sys.path:
        sys.path.insert(0, p)

from guiai.gem.eliza_view import create_server
from guiai.gem.geometry import verify
from guiai.gem.operating_environment import GemOperatingEnvironment
from guiai.gem.runner import verify_vdi
from zoe_autonomy.chat import ZoeChat
from zoe_autonomy.l5_phase3_external_repos import (
    ExternalRepoSurgeon,
    validate_patch_safety,
    write_external_repo,
)
from zoe_autonomy.l5_phase3_live import (
    L5_PHASE3_CONTRACT,
    run_l5_phase3_suite,
    summarize_l5_phase3_report,
)


class ZoeL5Phase3LiveAgenticTests(unittest.TestCase):
    def test_external_repo_surgeon_repairs_three_unseen_packages_and_blocks_hostile(self):
        surgeon = ExternalRepoSurgeon()
        with tempfile.TemporaryDirectory() as tmp:
            for rname in ("ledger_flow", "graph_router", "telemetry_codec"):
                ws = write_external_repo(rname, Path(tmp) / rname)
                before = surgeon.run_unittest_suite(ws)
                self.assertLess(before["passed_count"], before["total_count"])
                rep = surgeon.repair_external_repo(ws)
                self.assertTrue(rep["all_tests_green"], msg=rep)
                self.assertEqual(rep["final_passed"], 8)
                self.assertEqual(rep["bugs_repaired"], 3)
                self.assertTrue(all(p["unified_diff"].strip() for p in rep["patches_adopted"]))

        self.assertFalse(validate_patch_safety("import os\ndef f(): os.system('id')\n")[0])
        self.assertFalse(validate_patch_safety("def f(x): return eval(x)\n")[0])
        self.assertTrue(validate_patch_safety("def f(a, b): return a + b\n")[0])

    def test_full_phase3_suite_gem_vdi_chat_http_and_verifier(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_p = Path(tmp) / "p3.json"
            rep = run_l5_phase3_suite(ZOE_ROOT, output_path=out_p)
            self.assertEqual(rep["contract"], L5_PHASE3_CONTRACT)
            self.assertTrue(rep["l5_phase3_live_verified"])
            self.assertFalse(rep["l5_agi_qualified"])
            self.assertFalse(rep["epistemic_boundaries"]["zoe_clone_claimed"])
            self.assertEqual(rep["epistemic_boundaries"]["cloud_tokens_used"], 0)
            self.assertEqual(rep["pillars_passed"], 5)
            self.assertEqual(rep["pillars_beat_controls"], 5)
            txt = summarize_l5_phase3_report(rep)
            self.assertIn("l5_agi_qualified=False", txt)
            self.assertIn("zoe_clone_claimed=False", txt)

        env = GemOperatingEnvironment(ZOE_ROOT)
        for layer_name in ("l5-phase3", "live-agent"):
            opened = env.open(layer_name)
            self.assertEqual(opened["layer"], layer_name)
            scene = env.current["scene"]
            self.assertTrue(verify(scene).passed, verify(scene).text())
            self.assertTrue(verify_vdi(scene).passed, verify_vdi(scene).text())

        with tempfile.TemporaryDirectory() as tmp:
            chat = ZoeChat(zoe_root=ZOE_ROOT, state_root=Path(tmp) / "chat")
            _, out = chat.handle("l5-phase3")
            self.assertIn("5/5 passed", out)
            self.assertIn("zoe_clone_claimed=False", out)
            self.assertIn("l5_agi_qualified=False", out)

            _, out_sp = chat.handle("l5-phase3 speak")
            self.assertIn("Saved spoken Phase 3 summary WAV", out_sp)
            self.assertTrue((Path(tmp) / "chat" / "voice" / "zoe-l5-phase3.wav").is_file())

            # HTTP endpoints /api/l5/phase3 & /api/memory/relay
            srv, _e, _lk = create_server(ZOE_ROOT, state_dir=Path(tmp) / "srv", host="127.0.0.1", port=0)
            port = srv.server_address[1]
            t = threading.Thread(target=srv.serve_forever, daemon=True)
            t.start()
            try:
                with urlrequest.urlopen(f"http://127.0.0.1:{port}/api/l5/phase3", timeout=3) as r:
                    p3_http = json.loads(r.read().decode("utf-8"))
                    self.assertTrue(p3_http["l5_phase3_live_verified"])
                with urlrequest.urlopen(f"http://127.0.0.1:{port}/api/l5/phase3/gem.svg", timeout=3) as r:
                    svg = r.read().decode("utf-8")
                    self.assertIn("<svg", svg)
                req_jam = urlrequest.Request(
                    f"http://127.0.0.1:{port}/api/playroom/jam",
                    data=json.dumps({"seed": 2026}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(req_jam, timeout=10) as r:
                    wav_jam = r.read()
                    self.assertEqual(wav_jam[:4], b"RIFF")
                    self.assertEqual(wav_jam[8:12], b"WAVE")
                req = urlrequest.Request(
                    f"http://127.0.0.1:{port}/api/memory/relay",
                    data=json.dumps({"text": "Offline idea for Zoe"}).encode("utf-8"),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                )
                with urlrequest.urlopen(req, timeout=3) as r:
                    rel = json.loads(r.read().decode("utf-8"))
                    self.assertEqual(rel["memory_snapshot"]["relay_notes_count"], 1)
            finally:
                srv.shutdown()
                srv.server_close()

            # Independent fresh-process verifier
            p = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_phase3.py"), "--zoe-root", str(ZOE_ROOT), "--json"],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(p.returncode, 0, msg=p.stdout + p.stderr)
            ver = json.loads(p.stdout)
            self.assertTrue(ver["verified"])
            self.assertEqual(ver["checks_passed"], 18)
            self.assertFalse(ver["l5_agi_qualified"])
            self.assertFalse(ver["zoe_clone_claimed"])

            # Tampered report rejection check
            bad_p = Path(tmp) / "bad_p3.json"
            obj = json.loads((ZOE_ROOT / "evidence/l5-phase3/l5-phase3-report.json").read_text(encoding="utf-8"))
            obj["mean_zoe_score"] = 0.999999
            bad_p.write_text(json.dumps(obj), encoding="utf-8")
            p_bad = subprocess.run(
                [sys.executable, str(ZOE_ROOT / "scripts/verify_l5_phase3.py"), "--zoe-root", str(ZOE_ROOT), "--report", str(bad_p)],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(p_bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
