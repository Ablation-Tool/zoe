"""PromptArchitect - expert prompt-engineering assistant.

A library that treats prompts as structured artifacts (role, goal, input/output
contracts, constraints, self-checks) and analyzes, refines, and diversifies them
into production-ready forms.

Design grounding (conceptual ground truth, not runtime dependencies):
  - Esposito, *Programming LLMs with Azure OpenAI*: system-vs-user prompts,
    instruction formatting, output guardrails.
  - Pai, *Designing LLM Applications*: prompts as pipeline components,
    planner/worker/critic roles, evaluation-aware design.
  - Farris, *How LLMs Work*: context windows -> why length/ordering/clarity matter.
  - Cronin, *Decoding LLMs*: capability limits -> when to split tasks, hallucination
    mitigation at the prompt level.
  - Chinchilla / Bhatti et al.: clear, technically precise writing for engineers.

Everything returned is JSON-serializable (dict/list/str/bool/int).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .corpus import BookCorpus, BookScope, Retriever
from .models import (
    GroundingResult,
    PromptAnalysis,
    PromptComponents,
    PromptContext,
    PromptSpec,
    PromptVariant,
    Retrieved,
)

# Rough chars-per-token heuristic for the context-window pressure check. Real
# tokenizers vary (Farris); ~4 chars/token is the standard back-of-envelope.
_CHARS_PER_TOKEN = 4

# Persona declarations ("act as ...", "you are a ...") are expected near the start
# of a line; we only scan this many leading characters for an embedded role marker
# so a mid-sentence mention deep in a paragraph is not misread as the role.
_ROLE_SCAN_PREFIX_CHARS = 60

# The two titles in the corpus that are squarely about prompt design (Esposito's
# instruction-formatting / output-guardrail chapters; Pai's prompts-as-pipeline-
# components chapters). The goal-grounding query - "how to structure a prompt to
# <goal>" - is scoped to these so it retrieves prompting guidance rather than a
# task-keyword match from a tangential book (e.g. the docs-writing or build-from-
# scratch titles). Issue queries stay corpus-wide; they are already on-subject.
_PROMPT_ENG_BOOKS = (
    "esposito-programming-llms-azure-openai",
    "pai-designing-llm-applications",
)

# Signal phrases used by the extraction heuristics. Kept as module constants so a
# reader can audit and extend the detection surface in one place.
_ROLE_MARKERS = ("you are", "act as", "assume the role of", "you're a", "you are a")
_OUTPUT_MARKERS = (
    "return json", "output must", "respond in", "respond with", "use the following schema",
    "output format", "format your", "reply in", "answer in", "as a json", "valid json",
    "in markdown", "as markdown",
)
_QUALITY_MARKERS = (
    "before you answer", "before responding", "before returning", "verify that",
    "double-check", "double check", "make sure", "ensure that", "self-check", "sanity check",
)
_EXAMPLE_MARKERS = ("example:", "for example", "e.g.", "few-shot", "example input", "example output")
# The exact section labels the renderer emits (see the template in __init__).
# Section tracking in the extractors keys off THIS set, not a bare [A-Z ]+ match,
# so a human-written [NOTE]/[CONTEXT]/[DATA] token in a RAW prompt is never
# mistaken for a rendered section header (which would otherwise suppress the raw
# marker and bullet scans and drop the prompt's real output contract or steps).
_RENDER_HEADERS = frozenset(
    ("ROLE", "GOAL", "INPUTS", "INSTRUCTIONS", "OUTPUT", "CONSTRAINTS", "QUALITY CHECK")
)
# Imperative verbs that open an instruction step when prompts are written as prose.
# Kept broad on purpose: goal extraction and the instruction fallback both key off
# this set, so missing a common opener ("look at...", "pull out...") silently drops
# the prompt's real intent. Recall matters more than precision here.
_INSTRUCTION_VERBS = (
    "summarize", "analyze", "extract", "identify", "list", "generate", "write", "produce",
    "classify", "explain", "describe", "compare", "evaluate", "review", "find", "map",
    "rank", "translate", "convert", "validate", "check", "create", "compute",
    # Common prompt openers the original set missed.
    "look", "examine", "inspect", "scan", "detect", "flag", "parse", "pull", "gather",
    "collect", "fetch", "retrieve", "audit", "assess", "monitor", "build", "design",
    "refactor", "optimize", "debug", "test", "fix", "search", "enumerate", "discover",
    "draft", "outline", "plan", "recommend", "suggest", "propose", "score", "label",
    "tag", "transform", "normalize", "format", "render", "calculate", "count", "measure",
    "sort", "filter", "group", "merge", "split", "report", "give", "tell", "show",
    "determine", "categorize", "annotate", "redact", "highlight",
)
# Word-boundary lookup built from the same source: startswith() on the tuple is a
# raw character-prefix test, so "scan"/"map"/"find"/"list" silently swallow
# "Scanning"/"Mapping"/"Finding nemo"/"Listen". Match the first whitespace token
# instead, stripping only trailing clause punctuation.
_INSTRUCTION_VERB_SET = frozenset(_INSTRUCTION_VERBS)


def _opens_with_instruction_verb(low: str) -> bool:
    """True when the first whitespace token of `low` is an instruction verb.

    Word-boundary replacement for `low.startswith(_INSTRUCTION_VERBS)`: keeps the
    recall win (bare openers "look", "pull", "tell" still fire) while dropping
    prefix false matches ("Scanning", "Finding", "Designers", "Reportedly").
    """
    head = low.split(None, 1)
    return bool(head) and head[0].rstrip(",:;.!?") in _INSTRUCTION_VERB_SET


class PromptArchitect:
    """Analyze, refine, and diversify prompts at a production level of quality."""

    def __init__(
        self, books_dir: Optional[str] = None, retriever: Optional[Retriever] = None
    ) -> None:
        """Initialize templates, heuristic defaults, and the (lazy) RAG corpus.

        The heuristics are pure functions of their inputs. The book corpus is
        optional and lazy: it is only built on the first grounding call, so
        analyze/refine without grounding cost nothing and never touch disk.

        Pass `retriever` to inject a prebuilt corpus (or an alternate backend
        implementing the same `search` contract); otherwise `books_dir` (default:
        the bundled `books/`) is used to build a BM25 `BookCorpus` on demand.
        """
        self._default_length = "medium"
        self._books_dir = books_dir
        self._corpus: Optional[Retriever] = retriever
        self._render_template = (
            "[ROLE]\n{role}\n\n"
            "[GOAL]\n{goal}\n\n"
            "[INPUTS]\n{inputs_contract}\n\n"
            "[INSTRUCTIONS]\n{instructions}\n\n"
            "[OUTPUT]\n{output_contract}\n\n"
            "[CONSTRAINTS]\n{constraints}\n\n"
            "[QUALITY CHECK]\nBefore returning your final answer:\n{quality_checks}"
        )

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def analyze(self, prompt: str, context: PromptContext) -> PromptAnalysis:
        """Analyze a raw prompt against best practices.

        Returns a PromptAnalysis (components, issues, risk_assessment,
        suggested_improvements). Pure inspection - never mutates the prompt.
        """
        components = self._extract_components(prompt, context)
        issues = self._detect_issues(prompt, components, context)
        risk_assessment = self._assess_risk(prompt, components, context)
        suggested = self._suggest_improvements(issues, components, context)
        return PromptAnalysis(
            components=components,
            issues=issues,
            risk_assessment=risk_assessment,
            suggested_improvements=suggested,
        )

    def refine(
        self, prompt: str, context: PromptContext, ground: bool = True, k: int = 2
    ) -> Dict[str, Any]:
        """Refine a raw prompt into a structured PromptSpec and rendered string.

        Returns: prompt_spec, rendered_prompt, analysis_before, analysis_after,
        change_log (human-readable diff), and grounding (RAG passages from the
        book corpus supporting the refinement).

        When `ground` is True (default) the goal and each detected issue are used
        as retrieval queries against the bundled books, k passages each. If the
        corpus is unavailable (books/ missing), grounding degrades to an empty
        list and a note - it never raises out of refine.
        """
        analysis_before = self.analyze(prompt, context)
        spec = self._build_spec(prompt, analysis_before["components"], context)
        rendered = self._render_prompt(spec)
        analysis_after = self.analyze(rendered, context)
        change_log = self._change_log(
            analysis_before["components"], analysis_after["components"], spec
        )
        grounding = self._ground_refinement(spec, analysis_before, k) if ground else []
        if grounding:
            spec["notes"].append(
                "Grounded against the bundled book corpus; see refine()['grounding'] "
                f"for {sum(len(g['passages']) for g in grounding)} supporting passages."
            )
        return {
            "prompt_spec": spec,
            "rendered_prompt": rendered,
            "analysis_before": analysis_before,
            "analysis_after": analysis_after,
            "change_log": change_log,
            "grounding": grounding,
        }

    def ground(
        self, query: str, k: int = 5, book: Optional[str] = None
    ) -> List[Retrieved]:
        """Retrieve the top-k book passages relevant to `query` (RAG entry point).

        Optionally scope to one book slug. Raises FileNotFoundError if the book
        corpus cannot be located.
        """
        return self.corpus.search(query, k=k, book=book)

    def generate_variants(
        self, prompt: str, context: PromptContext, n: int = 3
    ) -> Dict[str, Any]:
        """Generate up to N structured variants from the refined base.

        Returns: base_spec (from refine) and variants (each a PromptVariant with a
        distinct optimization focus). n is clamped to the number of canonical
        variant builders available.
        """
        refined = self.refine(prompt, context, ground=False)
        base_spec: PromptSpec = refined["prompt_spec"]

        builders = [
            self._variant_cot,
            self._variant_concise_strict,
            self._variant_fewshot_skeleton,
        ]
        n = max(0, min(n, len(builders)))

        variants: List[PromptVariant] = []
        for build in builders[:n]:
            spec = build(base_spec, context)
            variants.append(
                PromptVariant(
                    id=spec["_id"],
                    description=spec["_description"],
                    prompt_spec=spec["spec"],
                    rendered_prompt=self._render_prompt(spec["spec"]),
                )
            )
        return {"base_spec": base_spec, "variants": variants}

    # ------------------------------------------------------------------ #
    # RAG corpus (lazy)
    # ------------------------------------------------------------------ #

    @property
    def corpus(self) -> Retriever:
        """Lazily build the book corpus on first grounding request.

        Returns whatever retriever is in use: the default BM25 BookCorpus (built on
        demand) or an injected backend that satisfies the Retriever protocol. The
        build()/_built lifecycle is BookCorpus-specific - not part of the protocol -
        so it is only invoked when the retriever actually is a BookCorpus.
        """
        if self._corpus is None:
            self._corpus = BookCorpus(self._books_dir).build()
        elif isinstance(self._corpus, BookCorpus) and not self._corpus._built:
            self._corpus.build()
        return self._corpus

    def _ground_refinement(
        self,
        spec: PromptSpec,
        analysis: PromptAnalysis,
        k: int,
    ) -> List[GroundingResult]:
        """Retrieve supporting passages for the refinement's prompt-engineering moves.

        Best-effort: if the corpus is missing, returns [] rather than raising, so
        refine() stays robust whether or not the books are present.
        """
        try:
            corpus = self.corpus
        except (FileNotFoundError, ValueError):
            return []
        results: List[GroundingResult] = []
        for q, scope in self._grounding_queries(spec, analysis):
            passages = corpus.search(q, k=k, book=scope)
            if passages:
                results.append(GroundingResult(query=q, passages=passages))
        return results

    @staticmethod
    def _grounding_queries(
        spec: PromptSpec, analysis: PromptAnalysis
    ) -> List[Tuple[str, BookScope]]:
        """Build (query, book_scope) retrieval pairs (de-duplicated by query).

        The book corpus is about prompt engineering, not the user's task domain, so
        grounding on the raw goal text retrieves task-keyword matches (code, data)
        instead of prompting guidance. Two defenses: the goal query is anchored with
        a prompt-design frame AND scoped to the two prompt-engineering titles
        (_PROMPT_ENG_BOOKS), so even the frame's task words cannot pull in a
        tangential book. The detected issues are already prompt-eng-topical, so they
        stay corpus-wide (scope None) and may match any title.
        """
        queries: List[Tuple[str, BookScope]] = []
        goal = spec["goal"].strip().rstrip(".")
        if goal and not goal.lower().startswith("complete the requested task"):
            queries.append(
                (
                    f"prompt engineering: how to structure an LLM prompt to {goal[:140]}",
                    _PROMPT_ENG_BOOKS,
                )
            )
        queries.extend((issue, None) for issue in analysis["issues"][:3])
        seen, out = set(), []
        for q, scope in queries:
            key = q.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append((q, scope))
        return out

    # ------------------------------------------------------------------ #
    # Extraction helpers (analyze)
    # ------------------------------------------------------------------ #

    def _extract_components(
        self, prompt: str, context: PromptContext
    ) -> PromptComponents:
        return PromptComponents(
            role=self._extract_role(prompt),
            goal=self._extract_goal(prompt, context),
            inputs_description=self._extract_inputs_description(prompt),
            instructions=self._extract_instructions(prompt),
            output_format=self._extract_output_format(prompt),
            constraints=self._extract_constraints(prompt, context),
            examples_present=self._contains_any(prompt, _EXAMPLE_MARKERS),
            quality_check_present=self._detect_quality_check(prompt),
        )

    def _extract_role(self, prompt: str) -> Optional[str]:
        """Find an explicit persona line ('You are ...', 'Act as ...')."""
        for line in self._lines(prompt):
            low = line.lower()
            for marker in _ROLE_MARKERS:
                if low.startswith(marker) or f" {marker}" in f" {low}"[:_ROLE_SCAN_PREFIX_CHARS]:
                    return line.strip().rstrip(".") if line.strip() else None
        return None

    def _extract_goal(self, prompt: str, context: PromptContext) -> Optional[str]:
        """Prefer an explicit goal; else infer the first imperative sentence."""
        ctx_goal = context.get("goal")
        if ctx_goal and ctx_goal.strip():
            return ctx_goal.strip()
        for sentence in self._sentences(prompt):
            low = sentence.lower().lstrip("- *0123456789.) ")
            if _opens_with_instruction_verb(low):
                return sentence.strip()
        return None

    def _extract_inputs_description(self, prompt: str) -> Optional[str]:
        for line in self._lines(prompt):
            low = line.lower()
            if any(k in low for k in ("you will receive", "input:", "inputs:", "given the", "you are given")):
                return line.strip()
        return None

    def _extract_instructions(self, prompt: str) -> List[str]:
        """Pull atomic steps from numbered/bulleted lists or imperative sentences.

        Skips bullets inside our own rendered [CONSTRAINTS] / [OUTPUT] / [QUALITY
        CHECK] sections so re-analysis of a rendered prompt does not miscount
        constraint and self-check lines as task instructions.
        """
        steps: List[str] = []
        non_instruction_section = False
        for line in self._lines(prompt):
            stripped = line.strip()
            header = re.match(r"^\[([A-Z ]+)\]$", stripped)
            if header and header.group(1) in _RENDER_HEADERS:
                non_instruction_section = header.group(1) not in ("INSTRUCTIONS",)
                continue
            if non_instruction_section:
                continue
            if re.match(r"^(\d+[.)]|[-*•])\s+", stripped):
                steps.append(re.sub(r"^(\d+[.)]|[-*•])\s+", "", stripped))
        if steps:
            return steps
        # No list markup: fall back to imperative sentences.
        for sentence in self._sentences(prompt):
            low = sentence.lower().lstrip("- *")
            if _opens_with_instruction_verb(low):
                steps.append(sentence.strip())
        return steps

    def _extract_output_format(self, prompt: str) -> Optional[str]:
        """Find the output-format declaration.

        Section-aware, like _extract_instructions: in a rendered prompt the first
        content line of the [OUTPUT] block IS the contract, even when it carries no
        output marker (e.g. "Return a single JSON object ..."). Lines inside other
        rendered sections are skipped so a QUALITY CHECK bullet that happens to say
        "output format" is never mistaken for the contract. In a raw prompt (no
        [SECTION] headers) we fall back to scanning for an _OUTPUT_MARKERS phrase.
        """
        section: Optional[str] = None
        for line in self._lines(prompt):
            stripped = line.strip()
            header = re.match(r"^\[([A-Z ]+)\]$", stripped)
            if header and header.group(1) in _RENDER_HEADERS:
                section = header.group(1)
                continue
            if section == "OUTPUT":
                return stripped  # rendered [OUTPUT] block: this line is the contract
            if section is not None:
                continue  # inside some other rendered section: not the output format
            if self._contains_any(stripped.lower(), _OUTPUT_MARKERS):
                return stripped  # raw prompt: marker scan
        return None

    def _extract_constraints(
        self, prompt: str, context: PromptContext
    ) -> Dict[str, str]:
        """Merge context constraints with anything inferable from the prompt text.

        Context wins on conflict - it is the caller's explicit intent.
        """
        constraints: Dict[str, str] = {}
        low = prompt.lower()
        if any(w in low for w in ("concise", "brief", "terse", "short")):
            constraints["length"] = "short"
        if any(w in low for w in ("detailed", "comprehensive", "thorough")):
            constraints["length"] = "long"
        if "no marketing" in low or "technical" in low:
            constraints["style"] = "concise, technical, no marketing"
        if "json" in low:
            constraints["format"] = "json"
        elif "markdown" in low:
            constraints["format"] = "markdown"
        constraints.update(context.get("constraints", {}))
        return constraints

    def _detect_quality_check(self, prompt: str) -> bool:
        return self._contains_any(prompt, _QUALITY_MARKERS)

    # ------------------------------------------------------------------ #
    # Issue / risk / suggestion helpers (analyze)
    # ------------------------------------------------------------------ #

    def _detect_issues(
        self, prompt: str, components: PromptComponents, context: PromptContext
    ) -> List[str]:
        issues: List[str] = []
        if not components["role"]:
            issues.append("No explicit ROLE; model may infer an inconsistent persona.")
        if not components["goal"] and not context.get("goal"):
            issues.append("No explicit GOAL; task is ambiguous.")
        ctx_format = context.get("constraints", {}).get("format")
        if not components["output_format"] and ctx_format:
            issues.append(
                "Context specifies format but prompt does not; risk of inconsistent outputs."
            )
        if len(components["instructions"]) <= 1:
            issues.append(
                "No clear stepwise INSTRUCTIONS; complex tasks should be broken into steps."
            )
        if not components["quality_check_present"]:
            issues.append("No QUALITY CHECK; model is not asked to self-verify before answering.")
        ctx_tokens = context.get("model_context_tokens")
        if ctx_tokens:
            approx_tokens = len(prompt) / _CHARS_PER_TOKEN
            if approx_tokens > ctx_tokens:
                issues.append(
                    "Prompt length may exceed or stress context window; consider summarizing "
                    "or splitting tasks."
                )
        return issues

    def _assess_risk(
        self, prompt: str, components: PromptComponents, context: PromptContext
    ) -> List[str]:
        risks: List[str] = []
        risk_points = context.get("risk_points", [])
        low = prompt.lower()
        if "hallucination" in risk_points:
            grounded = components["quality_check_present"] or any(
                k in low for k in ("cite", "source", "uncertain", "assumption", "do not fabricate")
            )
            if not grounded:
                risks.append(
                    "Hallucination risk: no request to state uncertainty or separate facts "
                    "from assumptions."
                )
        if "security" in risk_points:
            touches_code = context.get("inputs_type") in ("code", "mixed") or any(
                k in low for k in ("code", "execute", "run ", "shell", "command", "http", "url")
            )
            bounded = any(k in low for k in ("do not execute", "sandbox", "read-only", "no external"))
            if touches_code and not bounded:
                risks.append(
                    "Security risk: prompt does not bound where code can be executed or what "
                    "domains can be accessed."
                )
        if "compliance" in risk_points and not components["output_format"]:
            risks.append(
                "Compliance risk: unstructured output makes auditing and redaction harder."
            )
        return risks

    def _suggest_improvements(
        self, issues: List[str], components: PromptComponents, context: PromptContext
    ) -> List[str]:
        suggestions: List[str] = []
        if not components["role"]:
            suggestions.append(
                "Add a ROLE section that states who the model is and what expertise it has."
            )
        if not components["output_format"]:
            suggestions.append(
                "Add an OUTPUT section with explicit format (e.g. markdown with specific "
                "headings, or JSON with fixed keys)."
            )
        if len(components["instructions"]) <= 1:
            suggestions.append(
                "Break the task into ordered, atomic INSTRUCTIONS the model can follow in sequence."
            )
        if not components["quality_check_present"]:
            suggestions.append(
                "Add a QUALITY CHECK section asking the model to verify format and coverage "
                "before returning."
            )
        if not components["examples_present"]:
            suggestions.append(
                "No example detected; add a short few-shot example (a representative input plus "
                "the exact expected output) to lock in format and style."
            )
        if "hallucination" in context.get("risk_points", []):
            suggestions.append(
                "Instruct the model to mark assumptions explicitly and state uncertainty."
            )
        return suggestions

    # ------------------------------------------------------------------ #
    # Spec construction (refine)
    # ------------------------------------------------------------------ #

    def _build_spec(
        self, prompt: str, components: PromptComponents, context: PromptContext
    ) -> PromptSpec:
        # Resolve the goal once so the instruction fallback can reuse it instead of
        # degrading to a literal "the task" when no goal was detected.
        goal = self._spec_goal(prompt, components, context)
        return PromptSpec(
            role=self._spec_role(components, context),
            goal=goal,
            inputs_contract=self._spec_inputs(components, context),
            instructions=self._spec_instructions(components, context, goal),
            output_contract=self._spec_output(components, context),
            constraints=self._spec_constraints(components, context),
            quality_checks=self._spec_quality_checks(context),
            notes=[
                "Generated by PromptArchitect from the original prompt; structure follows "
                "system/user-prompt and pipeline-component patterns (Esposito, Pai).",
            ],
        )

    def _spec_role(self, components: PromptComponents, context: PromptContext) -> str:
        if components["role"]:
            # Reuse but normalize: ensure it reads as a clean declarative line.
            role = components["role"]
            return role if role.lower().startswith("you are") else f"You are {role}"
        audience = context.get("audience", "expert practitioners")
        domain = context.get("domain", "").replace("_", " ").strip()
        if domain:
            return (
                f"You are a senior {domain} specialist and technical writer who produces "
                f"precise, actionable output for {audience}."
            )
        return (
            f"You are a senior subject-matter expert and technical writer who produces "
            f"precise, actionable output for {audience}."
        )

    def _spec_goal(
        self, prompt: str, components: PromptComponents, context: PromptContext
    ) -> str:
        ctx_goal = context.get("goal")
        if ctx_goal and ctx_goal.strip():
            return ctx_goal.strip()
        if components["goal"]:
            return components["goal"]
        # Last resort: synthesize one clear sentence from the prompt's first line.
        # Strip a leading list marker so a bulleted first line ("- do the thing",
        # "1. do the thing") does not become the rendered [GOAL] verbatim. Anchored
        # to real marker shapes, NOT a character class: a char-class lstrip would
        # eat meaningful leading alphanumerics from a real goal ("3D-render ...",
        # "401k contribution rules ...", "2FA bypass ...").
        first = next((ln.strip() for ln in self._lines(prompt) if ln.strip()), "")
        first = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", first).strip()
        return first or "Complete the requested task accurately and completely."

    def _spec_inputs(self, components: PromptComponents, context: PromptContext) -> str:
        if components["inputs_description"]:
            return components["inputs_description"]
        inputs_type = context.get("inputs_type", "mixed")
        templates = {
            "question": "You will receive a natural-language question to answer.",
            "code": "You will receive source code and an optional description of intent.",
            "data_summary": (
                "You will receive a structured summary of data (records, metrics, or findings) "
                "with optional metadata such as severity, sector, and category."
            ),
            "mixed": (
                "You will receive mixed input: natural-language context plus optional code or "
                "structured data. Treat each part according to its type."
            ),
        }
        return templates.get(inputs_type, templates["mixed"])

    def _spec_instructions(
        self, components: PromptComponents, context: PromptContext, goal: str
    ) -> List[str]:
        if len(components["instructions"]) >= 2:
            # Normalize to a reasonable working set (2-7 steps; Cronin: split tasks).
            return [self._clean_step(s) for s in components["instructions"][:7]]
        # Reuse the resolved goal; only fall back to a generic phrasing if it is empty
        # or itself the generic placeholder (avoids "achieve: Complete the task...").
        goal_text = goal.strip().rstrip(".")
        if not goal_text or goal_text.lower().startswith("complete the requested task"):
            core = "Perform the core work the task requires."
        else:
            core = f"Perform the core work required to achieve: {goal_text}."
        return [
            "Read the inputs carefully and extract the key entities, facts, and intent.",
            core,
            "Organize the result according to the OUTPUT contract below.",
        ]

    def _spec_output(self, components: PromptComponents, context: PromptContext) -> str:
        # Read the MERGED constraints (context + format inferred from prompt text via
        # _extract_constraints), not context alone. Otherwise "return the result as json"
        # sets constraints.format=json but the OUTPUT block defaults to markdown - the
        # exact OUTPUT/CONSTRAINTS contradiction this tool exists to catch. The cot and
        # concise_strict variants already read merged constraints; this aligns the base
        # contract (and fewshot, which inherits it) with them.
        fmt = self._spec_constraints(components, context).get("format", "").lower()
        if fmt == "json":
            return (
                "Return a single JSON object. Use clear, fixed keys with consistent value types. "
                "Do not include commentary outside the JSON."
            )
        if fmt == "markdown":
            return (
                "Respond in markdown with clear H2 (##) section headings and bullet lists. "
                "Each required topic gets its own section."
            )
        if components["output_format"]:
            return components["output_format"]
        return (
            "Respond in structured markdown with clear headings and bullet lists so the result "
            "is easy to scan."
        )

    def _spec_constraints(
        self, components: PromptComponents, context: PromptContext
    ) -> Dict[str, str]:
        merged: Dict[str, str] = {
            "style": "concise, technical, no marketing",
            "tone": "neutral",
            "length": self._default_length,
        }
        merged.update(components["constraints"])
        merged.update(context.get("constraints", {}))
        return merged

    def _spec_quality_checks(self, context: PromptContext) -> List[str]:
        checks = [
            "Verify that the response follows the specified output format and includes all "
            "required sections or fields.",
        ]
        risk_points = context.get("risk_points", [])
        if "hallucination" in risk_points:
            checks.append(
                "Clearly mark any assumptions or speculative content; do not present them as facts."
            )
        if "security" in risk_points:
            checks.append("Ensure no unsafe instructions or secrets are fabricated or exposed.")
        if "compliance" in risk_points:
            checks.append("Confirm the output contains no data that should be redacted or withheld.")
        return checks

    # ------------------------------------------------------------------ #
    # Rendering
    # ------------------------------------------------------------------ #

    def _render_prompt(self, spec: PromptSpec) -> str:
        instructions = "\n".join(
            f"{i}. {step}" for i, step in enumerate(spec["instructions"], start=1)
        )
        constraints = "\n".join(
            [
                f"- Style: {spec['constraints'].get('style', 'unspecified')}",
                f"- Tone: {spec['constraints'].get('tone', 'unspecified')}",
                f"- Length: {spec['constraints'].get('length', 'unspecified')}",
                f"- Format: {spec['constraints'].get('format', 'unspecified')}",
            ]
        )
        quality = "\n".join(f"- {c}" for c in spec["quality_checks"])
        return self._render_template.format(
            role=spec["role"],
            goal=spec["goal"],
            inputs_contract=spec["inputs_contract"],
            instructions=instructions,
            output_contract=spec["output_contract"],
            constraints=constraints,
            quality_checks=quality,
        )

    # ------------------------------------------------------------------ #
    # Change log (refine)
    # ------------------------------------------------------------------ #

    def _change_log(
        self,
        before: PromptComponents,
        after: PromptComponents,
        spec: PromptSpec,
    ) -> List[str]:
        log: List[str] = []
        if not before["role"] and after["role"]:
            log.append("Added explicit role definition.")
        if not before["output_format"] and after["output_format"]:
            # Report the format the spec actually rendered (merged constraints), not
            # the context-only value - otherwise a format inferred from the prompt
            # text shows as "structured" while the OUTPUT block is JSON/markdown.
            fmt = spec["constraints"].get("format", "structured")
            log.append(f"Specified {fmt} output with explicit structure.")
        if len(after["instructions"]) > len(before["instructions"]):
            log.append(
                f"Expanded instructions from {len(before['instructions'])} to "
                f"{len(after['instructions'])} ordered steps."
            )
        if not before["quality_check_present"] and after["quality_check_present"]:
            log.append("Introduced a quality check to reduce format drift and hallucination risk.")
        if not log:
            log.append("Prompt already well-structured; normalized into canonical sections.")
        return log

    # ------------------------------------------------------------------ #
    # Variant builders (generate_variants)
    # ------------------------------------------------------------------ #
    # Each returns {"_id", "_description", "spec"}; generate_variants renders it.

    def _variant_cot(self, base: PromptSpec, context: PromptContext) -> Dict[str, Any]:
        spec = self._copy_spec(base)
        fmt = spec["constraints"].get("format", "").lower()
        if fmt == "json":
            # Expressing reasoning as markdown headings would contradict a JSON output
            # contract; carry the reasoning as a JSON field instead.
            spec["instructions"] = spec["instructions"] + [
                "Reason through the task step by step, then place that reasoning in a top-level "
                "\"reasoning\" array (one string per step) and put the conclusions in the "
                "remaining result keys.",
            ]
            spec["output_contract"] = (
                "Return a single JSON object with a top-level \"reasoning\" array (your "
                "step-by-step working, one string per step) alongside the required result keys. "
                "Keep all reasoning inside that array; emit no prose outside the JSON."
            )
        else:
            spec["instructions"] = spec["instructions"] + [
                "First, reason through the task step by step in a 'Reasoning' section. Then give "
                "your conclusions in a 'Final Answer' section.",
            ]
            spec["output_contract"] = (
                "Produce two sections: '## Reasoning' (your step-by-step working) followed by "
                "'## Final Answer' (the conclusions only). " + base["output_contract"]
            )
        spec["notes"] = base["notes"] + ["Variant: chain-of-thought emphasis."]
        return {
            "_id": "cot",
            "_description": "Emphasizes step-by-step reasoning then a clear final answer.",
            "spec": spec,
        }

    def _variant_concise_strict(
        self, base: PromptSpec, context: PromptContext
    ) -> Dict[str, Any]:
        spec = self._copy_spec(base)
        # Default to '' (not 'markdown') so the branch matches the other builders and
        # an unrecognized/custom format is not silently rewritten to markdown.
        fmt = spec["constraints"].get("format", "").lower()
        if fmt == "json":
            spec["output_contract"] = (
                "Output MUST be a single valid JSON object with a fixed set of keys and no "
                "additional keys or surrounding text."
            )
        elif fmt == "markdown":
            spec["output_contract"] = (
                "Output MUST be markdown containing only the required H2 sections, with no "
                "introductory or trailing commentary."
            )
        else:
            # No recognized format: the base contract may be a caller-supplied custom
            # line (e.g. "a CSV table with columns id,name,score"). Preserve it and
            # only tighten it, rather than substituting an unrelated markdown assertion.
            spec["output_contract"] = (
                base["output_contract"].rstrip(".")
                + ". Emit only that output with no extra commentary, preamble, or trailing notes."
            )
        spec["constraints"] = {**spec["constraints"], "length": "short"}
        spec["quality_checks"] = spec["quality_checks"] + [
            f"Ensure the output is syntactically valid {fmt or 'output'} and contains no "
            "extra commentary.",
        ]
        spec["notes"] = base["notes"] + ["Variant: format-strict, no visible reasoning."]
        return {
            "_id": "concise_strict",
            "_description": "Deterministic, machine-friendly output with strict format and no reasoning.",
            "spec": spec,
        }

    def _variant_fewshot_skeleton(
        self, base: PromptSpec, context: PromptContext
    ) -> Dict[str, Any]:
        spec = self._copy_spec(base)
        spec["instructions"] = spec["instructions"] + [
            "Follow the structure and style of the provided example(s) closely when generating "
            "your output.",
        ]
        spec["notes"] = base["notes"] + [
            "Variant: few-shot skeleton. Replace the placeholder example with real examples in "
            "production.",
            "[EXAMPLES]\n[EXAMPLE INPUT]\n<representative input here>\n"
            "[EXAMPLE OUTPUT]\n<expected output in the required format here>",
        ]
        spec["output_contract"] = (
            base["output_contract"]
            + " Match the example's structure exactly."
        )
        return {
            "_id": "fewshot_skeleton",
            "_description": "Encourages consistent output via demonstration (few-shot pattern).",
            "spec": spec,
        }

    # ------------------------------------------------------------------ #
    # Small utilities
    # ------------------------------------------------------------------ #

    @staticmethod
    def _copy_spec(spec: PromptSpec) -> PromptSpec:
        """Deep-ish copy so variant mutation never leaks back into the base spec."""
        return PromptSpec(
            role=spec["role"],
            goal=spec["goal"],
            inputs_contract=spec["inputs_contract"],
            instructions=list(spec["instructions"]),
            output_contract=spec["output_contract"],
            constraints=dict(spec["constraints"]),
            quality_checks=list(spec["quality_checks"]),
            notes=list(spec["notes"]),
        )

    @staticmethod
    def _clean_step(step: str) -> str:
        return re.sub(r"\s+", " ", step).strip().rstrip(".") + "."

    @staticmethod
    def _contains_any(text: str, markers) -> bool:
        low = text.lower()
        return any(m in low for m in markers)

    @staticmethod
    def _lines(text: str) -> List[str]:
        return [ln for ln in text.splitlines() if ln.strip()]

    @staticmethod
    def _sentences(text: str) -> List[str]:
        # Split on sentence terminators and newlines; keep non-empty fragments.
        parts = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [p.strip() for p in parts if p.strip()]


if __name__ == "__main__":
    import json

    architect = PromptArchitect()

    raw_prompt = "Summarize the AI/LLM exposures we found and tell the engineers what to fix."
    ctx: PromptContext = {
        "goal": "Summarize AI/LLM infrastructure exposures for security engineers",
        "audience": "security engineers",
        "model_name": "claude-3.5",
        "model_context_tokens": 8000,
        "constraints": {"style": "concise, technical, no marketing", "format": "markdown",
                        "length": "medium", "tone": "neutral"},
        "risk_points": ["hallucination", "security"],
        "domain": "ai_llm_infra_security",
        "inputs_type": "data_summary",
    }

    print("=== ANALYZE ===")
    print(json.dumps(architect.analyze(raw_prompt, ctx), indent=2))

    print("\n=== REFINE ===")
    refined = architect.refine(raw_prompt, ctx)
    print(json.dumps({k: v for k, v in refined.items() if k != "rendered_prompt"}, indent=2))
    print("\n--- rendered_prompt ---\n" + refined["rendered_prompt"])

    print("\n=== VARIANTS ===")
    variants = architect.generate_variants(raw_prompt, ctx, n=3)
    for v in variants["variants"]:
        print(f"\n--- {v['id']}: {v['description']} ---")
        print(v["rendered_prompt"])

    print("\n=== GROUNDING (RAG over books) ===")
    for g in refined["grounding"]:
        print(f"\nQ: {g['query']}")
        for p in g["passages"]:
            print(f"  [{p['score']:.2f}] {p['book']}")
            print("    " + p["text"][:160].replace("\n", " ") + "...")

    print("\n=== DIRECT RETRIEVAL ===")
    for r in architect.ground("how to specify json output schema", k=2):
        print(f"  [{r['score']:.2f}] {r['book']}: {r['text'][:120]}...")
