from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from zoe_autonomy.semantic_artifacts import (
    _ablation_root,
    _git_revision,
    analyze_artifact,
    save_semantic_report,
    verify_semantic_report,
)

ZOE_ROOT = Path(os.environ["ZOE_ROOT"]) if os.environ.get("ZOE_ROOT") else Path(__file__).resolve().parents[3]
ABLATION_ROOT = Path(os.environ["ABLATION_ROOT"]) if os.environ.get("ABLATION_ROOT") else (ZOE_ROOT / "components" / "ablation")
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
            ablation_root=None,
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
        self.assertTrue(report["checks"]["live_scope_excludes_plt"])
        self.assertTrue(report["checks"]["uncertainty_preserved"])
        self.assertTrue(report["checks"]["external_actions_zero"])
        self.assertEqual(report["autonomy_event"]["external_actions"] if "external_actions" in report["autonomy_event"] else 0, 0)

    def test_saved_report_verifies_and_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "semantic.json"
            save_semantic_report(self.report, path)
            self.assertTrue(verify_semantic_report(path)["verified"])
            with self.assertRaises(FileExistsError):
                save_semantic_report(self.report, path)
            with self.assertRaisesRegex(ValueError, ".json"):
                save_semantic_report(self.report, Path(directory) / "semantic.txt")
            edited = json.loads(path.read_text(encoding="utf-8"))
            edited["semantic_support"]["automatic_vulnerability_claim"] = True
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                verify_semantic_report(edited)

    def test_validation_guards_on_query_and_missing_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                analyze_artifact(ZOE_ROOT, Path(directory) / "does-not-exist", state_root=Path(directory) / "s")
            for bad_query in ("", "   ", "x" * 2001):
                with self.assertRaisesRegex(ValueError, "1-2000"):
                    analyze_artifact(ZOE_ROOT, self.artifact, query=bad_query, state_root=Path(directory) / "s")


class AblationRootResolutionCase(unittest.TestCase):
    def _make_synthetic_ablation(self, base: Path) -> Path:
        target = base / "ablation" / "analyzers"
        target.mkdir(parents=True, exist_ok=True)
        (base / "ablation" / "__init__.py").write_text("", encoding="utf-8")
        (target / "__init__.py").write_text("", encoding="utf-8")
        (target / "semantic_search.py").write_text("# synthetic\n", encoding="utf-8")
        return base

    def test_default_resolves_monorepo_components_ablation(self):
        import sys
        from unittest.mock import patch

        expected = (ZOE_ROOT / "components" / "ablation").resolve()
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ABLATION_ROOT", None)
            os.environ.pop("ZOE_ABLATION_ROOT", None)
            resolved = _ablation_root(zoe_root=ZOE_ROOT)
            self.assertEqual(resolved, expected)
            self.assertEqual(sys.path[0], str(expected))

    def test_env_and_explicit_override_and_non_git_revision(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env_ab = self._make_synthetic_ablation(root / "env_ab")
            exp_ab = self._make_synthetic_ablation(root / "exp_ab")
            try:
                with patch.dict(os.environ, {"ABLATION_ROOT": str(env_ab)}):
                    self.assertEqual(_ablation_root(), env_ab.resolve())
                    self.assertEqual(_ablation_root(path=exp_ab), exp_ab.resolve())
                    self.assertEqual(_git_revision(exp_ab), "untracked")
            finally:
                # Restore sys.path / sys.modules to canonical monorepo ablation
                _ablation_root(path=ABLATION_ROOT)

    def test_fallback_when_in_repo_absent_and_error_when_incomplete(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fake_zoe = root / "fake_zoe"
            fake_zoe.mkdir()
            fallback_ab = self._make_synthetic_ablation(root / "fallback_ab")
            try:
                with patch.dict(os.environ, {"ZOE_ABLATION_ROOT": str(fallback_ab)}):
                    os.environ.pop("ABLATION_ROOT", None)
                    self.assertEqual(_ablation_root(zoe_root=fake_zoe), fallback_ab.resolve())
                incomplete = root / "incomplete"
                incomplete.mkdir()
                with self.assertRaisesRegex(ValueError, "incomplete"):
                    _ablation_root(path=incomplete)
            finally:
                _ablation_root(path=ABLATION_ROOT)

    def test_evicts_preloaded_shadow_ablation_module(self):
        import sys
        import types
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as td:
            shadow_ab = self._make_synthetic_ablation(Path(td) / "shadow_ablation")
            fake_mod = types.ModuleType("ablation")
            fake_mod.__file__ = str(shadow_ab / "ablation" / "__init__.py")
            fake_sub = types.ModuleType("ablation.analyzers")
            fake_sub.__file__ = str(shadow_ab / "ablation" / "analyzers" / "__init__.py")
            sys.modules["ablation"] = fake_mod
            sys.modules["ablation.analyzers"] = fake_sub
            try:
                with patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("ABLATION_ROOT", None)
                    resolved = _ablation_root(zoe_root=ZOE_ROOT)
                    self.assertEqual(resolved, (ZOE_ROOT / "components" / "ablation").resolve())
                    self.assertNotIn("ablation.analyzers", sys.modules)
            finally:
                _ablation_root(path=ABLATION_ROOT)


if __name__ == "__main__":
    unittest.main()
