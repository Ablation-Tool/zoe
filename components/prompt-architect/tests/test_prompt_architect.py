"""Regression tests for PromptArchitect.

Pure stdlib (`unittest`) so the package stays dependency-free:

    python -m unittest discover -s prompt_architect/tests -v

Covers the public API contract, the three fixes (goal-verb recall, goal-threaded
instruction fallback, format-aware cot variant, prompt-eng-topical grounding),
JSON-serializability, and the RAG layer.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from prompt_architect import BookCorpus, PromptArchitect
from prompt_architect.architect import _PROMPT_ENG_BOOKS


def _ctx(**over):
    base = {
        "audience": "data engineers",
        "model_context_tokens": 8000,
        "constraints": {"format": "json", "tone": "neutral"},
        "risk_points": ["hallucination", "security", "compliance"],
        "domain": "data_pipeline_security",
        "inputs_type": "mixed",
    }
    base.update(over)
    return base


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.a = PromptArchitect()

    def test_analyze_shape(self):
        an = self.a.analyze("do a thing", _ctx())
        self.assertEqual(
            set(an), {"components", "issues", "risk_assessment", "suggested_improvements"}
        )

    def test_detects_all_issues_on_sloppy_prompt(self):
        an = self.a.analyze("look at the json and pull out anything sensitive", _ctx())
        joined = " ".join(an["issues"]).lower()
        for needle in ("role", "format", "instructions", "quality check"):
            self.assertIn(needle, joined)

    def test_security_risk_fires_on_code_request(self):
        an = self.a.analyze("write some code to flag records", _ctx())
        self.assertTrue(any("security" in r.lower() for r in an["risk_assessment"]))

    def test_security_risk_suppressed_when_bounded(self):
        an = self.a.analyze(
            "write read-only code, do not execute anything", _ctx()
        )
        self.assertFalse(any("security risk" in r.lower() for r in an["risk_assessment"]))


class TestGoalExtraction(unittest.TestCase):
    """Fix #1: 'look at ...' and friends must register as the goal."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_look_verb_now_recognized(self):
        an = self.a.analyze("look at the data and find issues", _ctx(domain=""))
        self.assertIsNotNone(an["components"]["goal"])
        self.assertIn("look at the data", an["components"]["goal"].lower())

    def test_pull_verb_recognized(self):
        an = self.a.analyze("pull out the sensitive fields", _ctx(domain=""))
        self.assertIsNotNone(an["components"]["goal"])

    def test_word_boundary_no_prefix_false_match(self):
        # A bare opener fires; a longer word that merely starts with a verb must not.
        ctx = _ctx(domain="")
        self.assertIsNotNone(self.a.analyze("scan the logs", ctx)["components"]["goal"])
        for text in ("Scanning the logs revealed a leak",
                     "Finding nemo is a movie",
                     "Designers love whitespace"):
            self.assertIsNone(
                self.a.analyze(text, ctx)["components"]["goal"], msg=text
            )

    def test_instruction_fallback_uses_goal_not_literal_the_task(self):
        # Fix #1b: with no detectable goal, step 2 must not read "achieve: the task".
        r = self.a.refine("xyzzy plugh", _ctx(), ground=False)
        step2 = r["prompt_spec"]["instructions"][1]
        self.assertNotIn("achieve: the task", step2)

    def test_instruction_fallback_embeds_real_goal(self):
        r = self.a.refine("look at the json and flag secrets", _ctx(), ground=False)
        steps = " ".join(r["prompt_spec"]["instructions"]).lower()
        self.assertIn("look at the json", steps)


class TestRefine(unittest.TestCase):
    def setUp(self):
        self.a = PromptArchitect()

    def test_refine_shape(self):
        r = self.a.refine("summarize findings", _ctx(), ground=False)
        self.assertEqual(
            set(r),
            {
                "prompt_spec",
                "rendered_prompt",
                "analysis_before",
                "analysis_after",
                "change_log",
                "grounding",
            },
        )

    def test_rendered_has_all_sections(self):
        r = self.a.refine("summarize findings", _ctx(), ground=False)
        for section in ("[ROLE]", "[GOAL]", "[INPUTS]", "[INSTRUCTIONS]",
                        "[OUTPUT]", "[CONSTRAINTS]", "[QUALITY CHECK]"):
            self.assertIn(section, r["rendered_prompt"])

    def test_change_log_reports_honest_instruction_count(self):
        # The section-aware extractor must not count constraint/quality bullets.
        r = self.a.refine("summarize findings", _ctx(), ground=False)
        after = r["analysis_after"]["components"]["instructions"]
        self.assertLessEqual(len(after), 7)

    def test_ground_false_yields_empty_grounding(self):
        r = self.a.refine("summarize findings", _ctx(), ground=False)
        self.assertEqual(r["grounding"], [])


class TestVariants(unittest.TestCase):
    def setUp(self):
        self.a = PromptArchitect()

    def test_three_variant_ids(self):
        v = self.a.generate_variants("summarize findings", _ctx())
        self.assertEqual([x["id"] for x in v["variants"]], ["cot", "concise_strict", "fewshot_skeleton"])

    def test_cot_json_has_no_markdown_heading_contradiction(self):
        # Fix #2: JSON format must not get '## Reasoning' markdown headings.
        v = self.a.generate_variants("summarize findings", _ctx(constraints={"format": "json"}))
        cot = next(x for x in v["variants"] if x["id"] == "cot")
        oc = cot["prompt_spec"]["output_contract"]
        self.assertNotIn("##", oc)
        self.assertIn("reasoning", oc.lower())
        self.assertIn("json", oc.lower())

    def test_cot_markdown_keeps_section_headings(self):
        v = self.a.generate_variants("summarize findings", _ctx(constraints={"format": "markdown"}))
        cot = next(x for x in v["variants"] if x["id"] == "cot")
        self.assertIn("## Reasoning", cot["prompt_spec"]["output_contract"])

    def test_variant_does_not_mutate_base(self):
        v = self.a.generate_variants("summarize findings", _ctx())
        base_oc = v["base_spec"]["output_contract"]
        # Mutating a variant spec must not have leaked back into base_spec.
        self.assertNotIn("reasoning", base_oc.lower().replace("reasoning risk", ""))

    def test_n_clamped(self):
        v = self.a.generate_variants("summarize findings", _ctx(), n=99)
        self.assertEqual(len(v["variants"]), 3)
        v0 = self.a.generate_variants("summarize findings", _ctx(), n=0)
        self.assertEqual(len(v0["variants"]), 0)


class TestRAG(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = PromptArchitect()

    def test_ground_returns_relevant_passages(self):
        hits = self.a.ground("how to specify a json output schema", k=3)
        self.assertTrue(hits)
        self.assertTrue(all(h["score"] > 0 for h in hits))
        self.assertEqual(set(hits[0]), {"book", "chunk_id", "score", "text"})

    def test_ground_book_scope(self):
        hits = self.a.ground("context window tokens", k=2, book="farris-how-llms-work")
        self.assertTrue(hits)
        self.assertEqual({h["book"] for h in hits}, {"farris-how-llms-work"})

    def test_empty_query_returns_empty(self):
        self.assertEqual(self.a.ground("   ", k=3), [])

    def test_corpus_chunk_count_stable(self):
        c = BookCorpus().build()
        self.assertGreater(c.num_chunks, 1000)
        self.assertEqual(len(c.books()), 7)

    def test_refine_grounding_is_prompt_eng_topical(self):
        # Fix #3: grounding queries should be framed for prompt engineering.
        r = self.a.refine("look at the json and flag secrets", _ctx())
        self.assertTrue(r["grounding"])
        first_q = r["grounding"][0]["query"].lower()
        self.assertIn("prompt", first_q)


class TestOutputContractFix(unittest.TestCase):
    """Fix #2: the base OUTPUT contract must agree with the merged constraints,
    including a format inferred from the prompt text (not just context)."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_base_output_contract_agrees_with_prompt_inferred_format(self):
        # No format in context; the prompt text alone says JSON.
        ctx = _ctx(constraints={})
        r = self.a.refine("Extract the fields and return the result as json.", ctx, ground=False)
        spec = r["prompt_spec"]
        self.assertEqual(spec["constraints"].get("format"), "json")
        oc = spec["output_contract"].lower()
        self.assertIn("json", oc)
        # The markdown default must not leak through when JSON was requested.
        self.assertNotIn("markdown", oc)

    def test_fewshot_inherits_corrected_output_contract(self):
        ctx = _ctx(constraints={})
        v = self.a.generate_variants("Extract the fields and return the result as json.", ctx)
        fs = next(x for x in v["variants"] if x["id"] == "fewshot_skeleton")
        self.assertIn("json", fs["prompt_spec"]["output_contract"].lower())


class TestGroundingQueries(unittest.TestCase):
    """Fix #3 internals: goal query is prompt-eng-scoped; issues stay corpus-wide
    and are capped; the placeholder goal is skipped."""

    def _spec(self, goal):
        return {
            "role": "r", "goal": goal, "inputs_contract": "i", "instructions": [],
            "output_contract": "o", "constraints": {}, "quality_checks": [], "notes": [],
        }

    def _analysis(self, issues):
        return {"components": {}, "issues": issues, "risk_assessment": [], "suggested_improvements": []}

    def test_goal_query_is_prompt_eng_scoped(self):
        qs = PromptArchitect._grounding_queries(self._spec("flag secrets in json"), self._analysis([]))
        self.assertEqual(len(qs), 1)
        q, scope = qs[0]
        self.assertIn("prompt engineering", q.lower())
        self.assertEqual(tuple(scope), _PROMPT_ENG_BOOKS)

    def test_placeholder_goal_query_is_skipped(self):
        qs = PromptArchitect._grounding_queries(
            self._spec("Complete the requested task accurately."),
            self._analysis(["issue one", "issue two"]),
        )
        self.assertTrue(all("prompt engineering" not in q.lower() for q, _ in qs))
        self.assertTrue(all(scope is None for _, scope in qs))

    def test_issue_queries_capped_at_three_and_corpus_wide(self):
        qs = PromptArchitect._grounding_queries(
            self._spec("Complete the requested task accurately."),
            self._analysis([f"issue {i}" for i in range(5)]),
        )
        self.assertEqual(len(qs), 3)  # placeholder goal skipped, 5 issues -> 3
        self.assertTrue(all(scope is None for _, scope in qs))

    def test_refine_goal_grounding_passages_are_prompt_eng_books(self):
        r = self.a.refine("look at the json and flag secrets", _ctx())  # noqa: F841
        first = r["grounding"][0]
        self.assertTrue(first["passages"])
        self.assertTrue(all(p["book"] in _PROMPT_ENG_BOOKS for p in first["passages"]))

    def setUp(self):
        self.a = PromptArchitect()


class TestCorpusScope(unittest.TestCase):
    """BookCorpus.search book scope: single slug, iterable, empty, and BM25 order."""

    @classmethod
    def setUpClass(cls):
        cls.c = BookCorpus().build()

    def test_iterable_scope_limits_to_given_books(self):
        slugs = list(_PROMPT_ENG_BOOKS)
        hits = self.c.search("prompt instruction format", k=8, book=slugs)
        self.assertTrue(hits)
        self.assertTrue(set(h["book"] for h in hits).issubset(set(slugs)))

    def test_empty_scope_returns_empty_not_corpus_wide(self):
        self.assertEqual(self.c.search("prompt", k=5, book=[]), [])

    def test_single_slug_scope_still_works(self):
        hits = self.c.search("context window tokens", k=3, book="farris-how-llms-work")
        self.assertTrue(hits)
        self.assertEqual({h["book"] for h in hits}, {"farris-how-llms-work"})

    def test_stopword_only_query_returns_empty(self):
        self.assertEqual(self.c.search("the and of to with", k=5), [])

    def test_scores_are_descending(self):
        hits = self.c.search("json output schema guardrails", k=8)
        scores = [h["score"] for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_cache_round_trip_is_identical(self):
        # A fresh corpus over the same dir loads the pickle cache and must return
        # byte-identical results to the in-memory build.
        warm = BookCorpus().build()
        q = "few-shot examples improve output"
        a, b = self.c.search(q, k=5), warm.search(q, k=5)
        self.assertEqual(a, b)


class TestDegradation(unittest.TestCase):
    """Missing corpus must degrade, not raise, when grounding is requested."""

    def test_missing_books_dir_yields_empty_grounding(self):
        with tempfile.TemporaryDirectory() as empty:
            a = PromptArchitect(books_dir=empty)
            r = a.refine("summarize findings", _ctx(), ground=True)
            self.assertEqual(r["grounding"], [])  # best-effort, no FileNotFoundError


class TestExactnessAndEdges(unittest.TestCase):
    def setUp(self):
        self.a = PromptArchitect()

    def test_reanalysis_instruction_count_matches_spec(self):
        # Round-trip fidelity: re-analyzing the rendered prompt recovers exactly the
        # instruction steps the spec declared (no over- or under-count).
        r = self.a.refine("summarize findings", _ctx(), ground=False)
        spec_n = len(r["prompt_spec"]["instructions"])
        after_n = len(r["analysis_after"]["components"]["instructions"])
        self.assertEqual(after_n, spec_n)

    def test_concise_strict_defaults_to_markdown(self):
        v = self.a.generate_variants("summarize findings", _ctx(constraints={}))
        cs = next(x for x in v["variants"] if x["id"] == "concise_strict")
        oc = cs["prompt_spec"]["output_contract"].lower()
        self.assertIn("markdown", oc)
        self.assertNotIn("json", oc)

    def test_context_window_overflow_is_flagged(self):
        # A long prompt against a tiny window must raise the context-window issue.
        an = self.a.analyze("word " * 200, _ctx(model_context_tokens=10))
        self.assertTrue(any("context window" in i.lower() for i in an["issues"]))

    def test_context_window_ok_when_within_budget(self):
        an = self.a.analyze("summarize this", _ctx(model_context_tokens=8000))
        self.assertFalse(any("context window" in i.lower() for i in an["issues"]))


class TestVariantMutationSafety(unittest.TestCase):
    """Review #2 / verification re-review: guard the _copy_spec deep copy directly.

    The end-to-end no-growth checks below are necessary but not sufficient: the
    variant builders rebind every field they touch (list concatenation, dict
    unpack), so they pass even if _copy_spec shares the base's mutable objects by
    reference. test_copy_spec_isolates_mutable_fields is the load-bearing guard:
    it mutates the copy's lists/dict IN PLACE, which only stays isolated from the
    base when _copy_spec actually copies them. Revert any list(...)/dict(...) in
    _copy_spec to a bare reference and that test fails; these two still pass."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_copy_spec_isolates_mutable_fields(self):
        base = self.a.refine("summarize findings", _ctx(), ground=False)["prompt_spec"]
        copy = PromptArchitect._copy_spec(base)
        # In-place mutation of every mutable field of the copy.
        copy["instructions"].append("LEAK")
        copy["quality_checks"].append("LEAK")
        copy["notes"].append("LEAK")
        copy["constraints"]["LEAK"] = "x"
        # None of it may bleed back into the base spec.
        self.assertNotIn("LEAK", base["instructions"])
        self.assertNotIn("LEAK", base["quality_checks"])
        self.assertNotIn("LEAK", base["notes"])
        self.assertNotIn("LEAK", base["constraints"])
        # And the copy is a distinct object per mutable field.
        self.assertIsNot(copy["instructions"], base["instructions"])
        self.assertIsNot(copy["constraints"], base["constraints"])

    def test_base_list_fields_unchanged_after_variants(self):
        # A separate refine fixes the canonical base shape; generating variants must
        # not have grown base_spec's instructions/notes.
        canonical = self.a.refine("summarize findings", _ctx(), ground=False)["prompt_spec"]
        n_instr, n_notes = len(canonical["instructions"]), len(canonical["notes"])
        v = self.a.generate_variants("summarize findings", _ctx())
        self.assertEqual(len(v["base_spec"]["instructions"]), n_instr)
        self.assertEqual(len(v["base_spec"]["notes"]), n_notes)

    def test_base_constraints_dict_not_mutated(self):
        v = self.a.generate_variants("summarize findings", _ctx())
        # concise_strict sets length=short on its own copy; base must keep medium.
        self.assertEqual(v["base_spec"]["constraints"].get("length"), "medium")


class TestChangeLogContent(unittest.TestCase):
    """Review #4 / #13: change_log content (not just length) and the format label."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_change_log_describes_each_real_addition(self):
        r = self.a.refine("summarize findings", _ctx(constraints={"format": "json"}), ground=False)
        log = " ".join(r["change_log"]).lower()
        self.assertIn("role", log)
        self.assertIn("json output", log)       # #13: inferred/merged format label
        self.assertIn("quality check", log)
        self.assertIn("ordered steps", log)

    def test_change_log_format_label_matches_prompt_inferred_format(self):
        # No format in context; prompt text alone implies JSON. Label must say json.
        r = self.a.refine("Summarize the findings. Return the result as json.", {}, ground=False)
        fmt_lines = [l for l in r["change_log"] if "output with explicit" in l]
        self.assertTrue(fmt_lines)
        self.assertIn("json", fmt_lines[0].lower())
        self.assertNotIn("structured output", fmt_lines[0].lower())


class TestConstraintsMerge(unittest.TestCase):
    """Review #9 / #10: constraint precedence at extract and spec levels."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_context_format_wins_over_prompt_inferred(self):
        an = self.a.analyze("return the result as json", _ctx(constraints={"format": "markdown"}))
        self.assertEqual(an["components"]["constraints"]["format"], "markdown")

    def test_spec_constraints_three_level_precedence(self):
        # defaults(length=medium) < prompt(length=short via "concise") < context(tone).
        # NB: style is NOT asserted here. The spec-level default style is byte-identical
        # to the prompt-inferred value, so a spec-level style check is vacuous (it passes
        # even with the inference deleted). The real guard is at the components level in
        # test_prompt_inferred_style_surfaces_in_components below.
        r = self.a.refine("be concise and technical", _ctx(constraints={"tone": "formal"}), ground=False)
        c = r["prompt_spec"]["constraints"]
        self.assertEqual(c["tone"], "formal")   # context overrides default neutral
        self.assertEqual(c["length"], "short")  # prompt overrides default medium

    def test_prompt_inferred_style_surfaces_in_components(self):
        # At the components level the spec-level default does not mask inference, so this
        # actually guards _extract_constraints' style block: delete it and the 'with'
        # case loses its style key and this fails.
        with_style = self.a.analyze("write a technical breakdown", {})["components"]["constraints"]
        self.assertEqual(with_style.get("style"), "concise, technical, no marketing")
        without = self.a.analyze("write a breakdown of the data", {})["components"]["constraints"]
        self.assertNotIn("style", without)


class TestComponentExtraction(unittest.TestCase):
    """Review #5 / #11 / #20 / #21: extractors with no prior coverage."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_role_extracted_and_normalized(self):
        an = self.a.analyze("You are a senior security analyst.\nSummarize the data.", _ctx())
        self.assertIsNotNone(an["components"]["role"])
        self.assertIn("senior security analyst", an["components"]["role"].lower())
        r = self.a.refine("Act as a SQL expert.\nOptimize the query.", _ctx(), ground=False)
        self.assertTrue(r["prompt_spec"]["role"].lower().startswith("you are"))

    def test_rendered_json_output_block_not_confused_with_qc_bullet(self):
        # Review #5: re-analysis must read the [OUTPUT] block, not the QC bullet that
        # literally contains the words "output format".
        r = self.a.refine("Summarize findings.", _ctx(constraints={"format": "json"}), ground=False)
        of = r["analysis_after"]["components"]["output_format"]
        self.assertIsNotNone(of)
        self.assertIn("json object", of.lower())
        self.assertNotIn("verify that", of.lower())

    def test_explicit_inputs_description_detected(self):
        an = self.a.analyze("Input: a list of CVE records to triage", _ctx())
        self.assertIsNotNone(an["components"]["inputs_description"])

    def test_inputs_type_selects_template(self):
        code = self.a.refine("classify the records", _ctx(inputs_type="code"), ground=False)
        self.assertIn("source code", code["prompt_spec"]["inputs_contract"].lower())
        ques = self.a.refine("classify the records", _ctx(inputs_type="question"), ground=False)
        self.assertIn("question", ques["prompt_spec"]["inputs_contract"].lower())

    def test_examples_present_detection_and_suggestion(self):
        with_ex = self.a.analyze("Summarize. For example: input X gives output Y.", _ctx())
        self.assertTrue(with_ex["components"]["examples_present"])
        self.assertFalse(any("few-shot example" in s.lower() for s in with_ex["suggested_improvements"]))
        no_ex = self.a.analyze("Summarize the data.", _ctx())
        self.assertFalse(no_ex["components"]["examples_present"])
        self.assertTrue(any("few-shot example" in s.lower() for s in no_ex["suggested_improvements"]))


class TestVariantOutputContracts(unittest.TestCase):
    """Review #6 / #12: concise_strict JSON branch and custom-format preservation."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_concise_strict_json_branch(self):
        v = self.a.generate_variants("summarize findings", _ctx(constraints={"format": "json"}))
        cs = next(x for x in v["variants"] if x["id"] == "concise_strict")
        oc = cs["prompt_spec"]["output_contract"].lower()
        self.assertIn("json", oc)
        self.assertNotIn("markdown", oc)
        self.assertIn("valid json", " ".join(cs["prompt_spec"]["quality_checks"]).lower())

    def test_concise_strict_preserves_custom_output_contract(self):
        # A custom (non-json/non-markdown) base contract must survive, not be replaced
        # with an unrelated markdown-H2 assertion.
        prompt = "Output format: a CSV table with columns id,name,score"
        v = self.a.generate_variants(prompt, _ctx(constraints={}))
        cs = next(x for x in v["variants"] if x["id"] == "concise_strict")
        oc = cs["prompt_spec"]["output_contract"]
        self.assertIn("csv", oc.lower())
        self.assertNotIn("H2", oc)


class TestGoalEdges(unittest.TestCase):
    """Review #14: a whitespace-only context goal must not pass through verbatim."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_whitespace_context_goal_not_passed_through(self):
        r = self.a.refine("do something useful here", _ctx(goal="   "), ground=False)
        self.assertTrue(r["prompt_spec"]["goal"].strip())
        self.assertNotEqual(r["prompt_spec"]["goal"], "   ")

    def test_bulleted_first_line_fallback_is_stripped(self):
        # No detectable goal verb, list-marker first line -> marker stripped from goal.
        r = self.a.refine("- zzz qqq mmm", _ctx(domain="", goal=""), ground=False)
        self.assertFalse(r["prompt_spec"]["goal"].startswith("-"))


class TestCorpusConfig(unittest.TestCase):
    """Review #15: degenerate chunking config fails loud instead of blowing up the index."""

    def test_overlap_ge_chunk_words_raises(self):
        with self.assertRaises(ValueError):
            BookCorpus(chunk_words=5, overlap=10)
        with self.assertRaises(ValueError):
            BookCorpus(chunk_words=5, overlap=5)

    def test_invalid_chunk_words_raises(self):
        with self.assertRaises(ValueError):
            BookCorpus(chunk_words=0)


class TestRetrieverInjection(unittest.TestCase):
    """Review #19 / #22: injected retrievers honor the Retriever protocol contract."""

    def test_injected_unbuilt_bookcorpus_is_built_on_demand(self):
        c = BookCorpus()
        self.assertFalse(c._built)
        a = PromptArchitect(retriever=c)
        self.assertTrue(a.ground("json schema", k=2))
        self.assertTrue(c._built)

    def test_protocol_retriever_without_build_is_used_as_is(self):
        # A non-BookCorpus retriever must be used directly; the BookCorpus-only
        # build()/_built lifecycle must never be invoked on it. `_built = False`
        # would trip the old getattr-based build() call and crash (no build method).
        class FakeRetriever:
            _built = False

            def search(self, query, k=5, book=None):
                return [{"book": "fake", "chunk_id": 0, "score": 2.0, "text": "x"}]

        a = PromptArchitect(retriever=FakeRetriever())
        hits = a.ground("anything", k=1)
        self.assertEqual(hits[0]["book"], "fake")


class TestGroundContract(unittest.TestCase):
    """Review #3: ground() propagates FileNotFoundError when the corpus is absent."""

    def test_ground_raises_when_corpus_missing(self):
        with tempfile.TemporaryDirectory() as empty:
            a = PromptArchitect(books_dir=empty)
            with self.assertRaises(FileNotFoundError):
                a.ground("anything", k=2)


class TestCacheBehavior(unittest.TestCase):
    """Review #7 / #16 / #23: signature keys on per-book content; corrupt cache rebuilds."""

    @staticmethod
    def _mini_corpus(d, books):
        for name, txt in books.items():
            (Path(d) / name).mkdir()
            (Path(d) / name / "_combined.md").write_text(txt, encoding="utf-8")

    @staticmethod
    def _freeze_mtime(d, when=1700000000):
        # Hold size (equal-length content) and mtime constant so the ONLY signature
        # input left varying is the sha256 content digest. Without this, st_mtime_ns
        # (bumped on every write) or st_size silently carries the test and the digest
        # is never the discriminator it claims to guard.
        for p in Path(d).glob("*/_combined.md"):
            os.utime(p, (when, when))

    def test_signature_distinguishes_same_basename_books_by_content(self):
        with tempfile.TemporaryDirectory() as d:
            # 11-byte contents, swapped below -> size identical before and after.
            self._mini_corpus(d, {"alpha": "aaa bbb ccc", "beta": "ddd eee fff"})
            c = BookCorpus(books_dir=d)
            paths = sorted(Path(d).glob("*/_combined.md"))
            self._freeze_mtime(d)
            sig_before = c._signature(paths)
            # Swap the two same-basename files' content. Size and mtime held equal, so
            # only the content digest can change the signature. Drop the digest from
            # _signature and sig_before == sig_after -> this assertion fails.
            (Path(d) / "alpha" / "_combined.md").write_text("ddd eee fff", encoding="utf-8")
            (Path(d) / "beta" / "_combined.md").write_text("aaa bbb ccc", encoding="utf-8")
            self._freeze_mtime(d)
            sig_after = c._signature(sorted(Path(d).glob("*/_combined.md")))
            self.assertNotEqual(sig_before, sig_after)

    def test_content_change_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "alpha" / "_combined.md"
            # 22-byte content; "omega" appears only after the edit.
            self._mini_corpus(d, {"alpha": "alpha beta gamma delta"})
            self._freeze_mtime(d)
            c1 = BookCorpus(books_dir=d).build()
            self.assertEqual(c1.search("omega", k=1), [])  # token absent in v1
            # Same byte length (22) and same frozen mtime: only the digest differs.
            p.write_text("alpha beta gamma omega", encoding="utf-8")
            self._freeze_mtime(d)
            c2 = BookCorpus(books_dir=d).build()  # must rebuild, not serve stale cache
            self.assertTrue(c2.search("omega", k=1))  # fresh index sees the new token

    def test_corrupt_cache_rebuilds_silently(self):
        with tempfile.TemporaryDirectory() as d:
            self._mini_corpus(d, {"alpha": "prompt output json schema few-shot tokens grounding"})
            c1 = BookCorpus(books_dir=d).build()
            self.assertGreater(c1.num_chunks, 0)
            cache = Path(d) / ".rag_cache.json"
            self.assertTrue(cache.is_file())
            cache.write_text("{ not valid json ::::", encoding="utf-8")
            c2 = BookCorpus(books_dir=d).build()  # must not raise
            self.assertGreater(c2.num_chunks, 0)


class TestSectionAwareExtractorRegressions(unittest.TestCase):
    """Verification re-review #1: a human-written all-caps bracketed token in a RAW
    prompt ([NOTE], [CONTEXT], ...) must not be mistaken for a rendered section
    header. Section tracking only fires on the renderer's own labels; otherwise the
    raw output-marker scan and the instruction-bullet scan are wrongly suppressed."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_bracket_token_does_not_hide_raw_output_contract(self):
        p = (
            "Process the data.\n[NOTE]\n"
            "Return the answer as a JSON object with fixed keys.\n"
            "Respond in valid JSON only."
        )
        self.assertIsNotNone(self.a._extract_output_format(p))
        an = self.a.analyze(p, _ctx(constraints={"format": "json"}, risk_points=["compliance"]))
        self.assertIsNotNone(an["components"]["output_format"])
        self.assertFalse(any("compliance risk" in r.lower() for r in an["risk_assessment"]))
        self.assertFalse(any("prompt does not" in i.lower() for i in an["issues"]))

    def test_rendered_output_section_still_resolves(self):
        rp = "[OUTPUT]\nReturn a single JSON object.\n[QUALITY CHECK]\nVerify the output format."
        self.assertEqual(self.a._extract_output_format(rp), "Return a single JSON object.")

    def test_bracket_token_does_not_hide_numbered_steps(self):
        p = "Do the task.\n[NOTE]\n1. read the input\n2. extract entities\n3. return the result"
        self.assertEqual(len(self.a._extract_instructions(p)), 3)


class TestGoalMarkerStripRegression(unittest.TestCase):
    """Verification re-review #3: the leading list-marker strip in _spec_goal must
    remove only real marker shapes ('- ', '1. '), never eat the leading characters
    of a genuine goal ('3D-render ...', '401k ...', '2FA ...')."""

    def setUp(self):
        self.a = PromptArchitect()

    def test_leading_alphanumerics_preserved(self):
        for g in (
            "3D-render the scene from the input mesh.",
            "401k contribution rules summary.",
            "2FA bypass analysis for the login flow.",
        ):
            r = self.a.refine(g, {}, ground=False)
            self.assertEqual(r["prompt_spec"]["goal"], g)

    def test_real_list_marker_still_stripped(self):
        self.assertEqual(
            self.a.refine("- do the thing", {}, ground=False)["prompt_spec"]["goal"],
            "do the thing",
        )
        self.assertEqual(
            self.a.refine("1. do the thing", {}, ground=False)["prompt_spec"]["goal"],
            "do the thing",
        )


class TestJSONSerializable(unittest.TestCase):
    def setUp(self):
        self.a = PromptArchitect()

    def test_all_returns_json_safe(self):
        ctx = _ctx()
        p = "look at the json and pull out anything sensitive and write code to flag it"
        json.dumps(self.a.analyze(p, ctx))
        json.dumps(self.a.refine(p, ctx))
        json.dumps(self.a.generate_variants(p, ctx))
        json.dumps(self.a.ground("json schema", k=2))


if __name__ == "__main__":
    unittest.main(verbosity=2)
