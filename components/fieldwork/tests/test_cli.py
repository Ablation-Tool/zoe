import contextlib
import copy
import io
import json
import unittest

from fieldwork.cli import load, main, rank, resume, validate


class PortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_firmware_match_is_relevant_and_explainable(self):
        result = rank(self.data["projects"], "help reverse engineer stripped firmware binaries")
        self.assertEqual(result[0]["project"]["id"], "ablation")
        self.assertIn("firmware", result[0]["matched_terms"])
        self.assertIn("binary", result[0]["matched_terms"])

    def test_agent_permissions_match(self):
        result = rank(self.data["projects"], "AI agent permissions and prompt injection")
        self.assertEqual(result[0]["project"]["id"], "injection-gate")

    def test_empty_and_unrelated_query_do_not_invent_matches(self):
        for query in ("", "the and of", "underwater basketweaving"):
            self.assertEqual(rank(self.data["projects"], query), [])

    def test_duplicate_and_unsubstantiated_verification_rejected(self):
        data = copy.deepcopy(self.data)
        data["projects"].append(copy.deepcopy(data["projects"][0]))
        data["projects"][0]["evidence_status"] = "verified"
        errors = validate(data)
        self.assertTrue(any("Duplicate" in error for error in errors))
        self.assertTrue(any("verified entries require" in error for error in errors))

    def test_bad_shapes_fail_cleanly(self):
        self.assertTrue(validate([]))
        for key in ("person", "provenance", "projects"):
            data = copy.deepcopy(self.data)
            data[key] = None
            self.assertTrue(validate(data))

    def test_filters_and_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(main(["projects", "--language", "rust", "--json"]), 0)
        result = json.loads(out.getvalue())
        self.assertEqual([p["id"] for p in result["projects"]], ["spectral"])

    def test_missing_project_returns_failure(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(["show", "missing"]), 1)

    def test_resume_focus_and_provenance(self):
        text = resume(self.data, "firmware", 1)
        self.assertIn("https://github.com/Ablation-Tool/ablation", text)
        self.assertNotIn("safeconvert", text)
        self.assertIn("not been independently verified", text)
        self.assertIn("Nicholas Kloster", text)

    def test_invalid_limit_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["match", "firmware", "--limit", "0"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
