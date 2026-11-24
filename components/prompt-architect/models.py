"""Data models for PromptArchitect.

All models are TypedDicts so every value stays JSON-serializable (dict/list/str/
bool/int). No runtime validation layer is imposed here on purpose: the heuristics
in architect.py are the single place that constructs these, so the shapes are
guaranteed at the producer, not re-checked at every boundary.

Grounding: the component vocabulary (role / goal / inputs / instructions / output
contract / constraints / quality checks) follows the system-vs-user prompt split
and output-guardrail framing from Esposito and the "prompts as pipeline
components" view from Pai.
"""

from typing import Dict, List, Optional, Literal, TypedDict


class PromptContext(TypedDict, total=False):
    """Minimal context passed alongside a raw prompt.

    Every field is optional (total=False); the architect degrades gracefully when
    a field is absent rather than demanding a fully-populated context.
    """

    goal: str                       # High-level intent
    audience: str                   # e.g. "security engineers", "red team"
    model_name: str                 # e.g. "claude-3.5", "gpt-4.1"
    model_context_tokens: int       # e.g. 8000
    constraints: Dict[str, str]     # keys: "style","tone","format","length"
    risk_points: List[str]          # e.g. ["hallucination","security","compliance"]
    domain: str                     # e.g. "ai_llm_infra_security"
    inputs_type: Literal["question", "code", "data_summary", "mixed"]


class PromptComponents(TypedDict):
    """What a given prompt currently contains, as discovered by analysis."""

    role: Optional[str]
    goal: Optional[str]
    inputs_description: Optional[str]
    instructions: List[str]
    output_format: Optional[str]
    constraints: Dict[str, str]
    examples_present: bool
    quality_check_present: bool


class PromptAnalysis(TypedDict):
    """Result of analyzing a prompt against best practices."""

    components: PromptComponents
    issues: List[str]
    risk_assessment: List[str]
    suggested_improvements: List[str]


class PromptSpec(TypedDict):
    """Canonical intermediate representation of a refined prompt."""

    role: str
    goal: str
    inputs_contract: str
    instructions: List[str]
    output_contract: str
    constraints: Dict[str, str]
    quality_checks: List[str]
    notes: List[str]


class PromptVariant(TypedDict):
    """One optimization-focused variant rendered from a PromptSpec."""

    id: str
    description: str
    prompt_spec: PromptSpec
    rendered_prompt: str


class Retrieved(TypedDict):
    """A single passage retrieved from the book corpus by the RAG layer."""

    book: str          # book slug, e.g. "esposito-programming-llms-azure-openai"
    chunk_id: int      # index of the chunk within the corpus
    score: float       # BM25 relevance score
    text: str          # the retrieved passage text


class GroundingResult(TypedDict):
    """Passages retrieved for one grounding query (e.g. the goal or an issue)."""

    query: str
    passages: List[Retrieved]
