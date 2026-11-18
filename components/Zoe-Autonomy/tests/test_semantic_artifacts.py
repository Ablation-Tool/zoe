from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from zoe_autonomy.semantic_artifacts import analyze_artifact, save_semantic_report, verify_semantic_report

ZOE_ROOT = Path(os.environ.get("ZOE_ROOT", ""))
ABLATION_ROOT = Path(os.environ.get("ABLATION_ROOT", "/home/cowboy/_projects/ablation"))
SOURCE = r'''#include <string.h>
#include <stdlib.h>
struct packet { char tag[8]; char payload[16]; };
__attribute__((noinline)) void copy_payload(struct packet *p, const char *input) { strcpy(p->payload, input); }
__attribute__((noinline)) int parse_header(const char *input) {
    struct packet p;
    if (input == NULL) return -1;
    copy_payload(&p, input);
    return p.payload[0];
}
__attribute__((noinline)) size_t safe_length(const char *input) { return input == NULL ? 0 : strlen(input); }
int main(int argc, char **argv) { return argc > 1 ? parse_header(argv[1]) : (int)safe_length("x"); }
'''


@unittest.skipUnless(
    ZOE_ROOT.is_dir() and ABLATION_ROOT.is_dir() and shutil.which("gcc"),
    "requires Zoe, canonical Ablation, and gcc",
)
class SemanticArtifactCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        root = Path(cls.temporary.name)
        source = root / "target.c"
        source.write_text(SOURCE, encoding="utf-8")
        cls.artifact = root / "target-o2"
        subprocess.run(["gcc", "-O2", "-s", "-o", str(cls.artifact), str(source)], check=True)
        cls.report = analyze_artifact(
            ZOE_ROOT,
            cls.artifact,
            state_root=root / "state",
            ablation_root=ABLATION_ROOT,
        )

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def test_direct_call_evidence_guides_guarded_inspection(self):
        report = self.report
        self.assertTrue(report["overall"]["passed"])
        self.assertEqual(report["overall"]["failed_checks"], [])
        dangerous = [item for item in report["direct_evidence"].values() if item["dangerous_calls"]]
        self.assertEqual(len(dangerous), 1)
        self.assertEqual(dangerous[0]["dangerous_calls"][0]["target"], "strcpy")
        self.assertEqual(report["autonomy_event"]["value"]["selected_candidate"], "semantic-inspect")
        self.assertTrue(report["event_memory"]["chain_valid"])
        self.assertFalse(report["semantic_support"]["automatic_vulnerability_claim"])
        self.assertTrue(report["semantic_support"]["limited_support"])
        self.assertTrue(any(
            edge["relation"] == "jmp" and edge["to"] == "api:strcpy"
            for edge in report["semantic_graph"]["edges"]
        ))
        self.assertEqual(report["autonomy_event"]["external_actions"] if "external_actions" in report["autonomy_event"] else 0, 0)

    def test_saved_report_verifies_and_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "semantic.json"
            save_semantic_report(self.report, path)
            self.assertTrue(verify_semantic_report(path)["verified"])
            with self.assertRaises(FileExistsError):
                save_semantic_report(self.report, path)
            edited = json.loads(path.read_text(encoding="utf-8"))
            edited["semantic_support"]["automatic_vulnerability_claim"] = True
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_semantic_report(edited)


if __name__ == "__main__":
    unittest.main()
