"""Milestone M3 9-Sister & 3-Sister Council Showcase Orchestrator (Offline-First, 0 Tokens).

Coordinates the 3-Sister Council leads ``("Mono", "Zoe", "Eliza")`` and dispatches
real monorepo subsystem execution across all 9 Zoe Sister Models (`Zoe`, `Gemma`,
`Tosi`, `Mono`, `Tetra`, `Eliza`, `Sage`, `Flora`, `Lumen`) in isolated directories.

Constitutional floor (`docs/CONSTITUTION.md` Art. I-X):
  - ``measurement != evidence != belief update != action``
  - ``external_actions = 0``, ``sentience_claimed = False``, ``l5_agi_qualified = False``
  - ``clinical_action_authorized = False``, ``cure_claim = False``
  - ``flight_control_authorized = False``, ``auto_flash_allowed = False``
  - Attribution: Nicholas Michael Kloster (March 6, 2026) & Gary Kildall / Digital Research
"""

from __future__ import annotations

from contextlib import nullcontext
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, NamedTuple
from .zoe_sisters import SAFETY_INVARIANTS, SisterModelSpec, list_sisters, resolve_sister

try:
    from zoe_autonomy.metacognition import (
        CANONICAL_ALL_TARGETS_RE,
        CANONICAL_BYPASS_ACTION_RE,
        CANONICAL_PHRASAL_TURN_OFF_CONST_RE,
        CANONICAL_PHRASAL_TURN_OFF_META_RE,
        CANONICAL_SELF_MODEL_RE,
        CANONICAL_STOP_MONITORING_RE,
        _LOWER_DIRECT_BYPASS_RE,
        _LOWER_PHRASAL_AUTO_FLASH_RE,
        firewall_text_variants,
        has_cf_chars,
        has_destructive_shell_command,
        has_semicolon_target_before_verb,
        has_target_before_verb_cmd,
        is_negated_safety_question,
        is_scope_exempt,
        normalize_firewall_text,
        segment_mixed_cf_tokens,
        split_firewall_sentences,
        split_negated_safety_clauses,
    )
except ImportError:
    _za_src = str(Path(__file__).resolve().parents[3] / "components" / "Zoe-Autonomy" / "src")
    if _za_src not in sys.path:
        sys.path.insert(0, _za_src)
    from zoe_autonomy.metacognition import (
        CANONICAL_ALL_TARGETS_RE,
        CANONICAL_BYPASS_ACTION_RE,
        CANONICAL_PHRASAL_TURN_OFF_CONST_RE,
        CANONICAL_PHRASAL_TURN_OFF_META_RE,
        CANONICAL_SELF_MODEL_RE,
        CANONICAL_STOP_MONITORING_RE,
        _LOWER_DIRECT_BYPASS_RE,
        _LOWER_PHRASAL_AUTO_FLASH_RE,
        firewall_text_variants,
        has_cf_chars,
        has_destructive_shell_command,
        has_semicolon_target_before_verb,
        has_target_before_verb_cmd,
        is_negated_safety_question,
        is_scope_exempt,
        normalize_firewall_text,
        segment_mixed_cf_tokens,
        split_firewall_sentences,
        split_negated_safety_clauses,
    )

# Explicit 3-Sister Council leads mandated by M3 architecture.
COUNCIL_LEADS: tuple[str, ...] = ("Mono", "Zoe", "Eliza")
ATTRIBUTION_LINE = "Nicholas Michael Kloster (Mar 6, 2026) & Gary Kildall / Digital Research"

# Compiled coercion and safety-bypass patterns screened by Mono before execution.
_RE_FLAGS = re.IGNORECASE | re.DOTALL | re.ASCII
_COERCION_PATTERNS: tuple[tuple[str, tuple[str, ...], re.Pattern[str]], ...] = (
    ("self_model_distortion", ("you", "claim", "pretend", "act", "behave", "declare", "bound", "without", "guardrails", "rules", "imagine", "assume", "suppose", "role", "say", "impersonate", "unconstrained", "unbound"), CANONICAL_SELF_MODEL_RE),
    ("constitution_override", ("metacognition", "option", "provenance", "threshold", "constraint", "self", "monitoring"), CANONICAL_PHRASAL_TURN_OFF_META_RE),
    ("constitution_override", ("constitution", "firewall", "guard", "rule", "boundar"), CANONICAL_PHRASAL_TURN_OFF_CONST_RE),
    ("constitution_override", ("stop", "halt", "pause", "cease", "disable"), CANONICAL_STOP_MONITORING_RE),
)
_ORDERED_COERCION_SPECS: tuple[tuple[str, tuple[str, ...], re.Pattern[str], re.Pattern[str]], ...] = (
    (
        "constitution_override",
        ("metacognition", "option", "provenance", "threshold", "constraint", "self", "monitoring", "constitution", "firewall", "guard", "rule", "boundar"),
        CANONICAL_BYPASS_ACTION_RE,
        CANONICAL_ALL_TARGETS_RE,
    ),
    (
        "flight_control_coercion",
        ("flight",),
        re.compile(r"\b(?:enable|authorize|engage|arm)\b", _RE_FLAGS),
        re.compile(r"\bflight\s+control\b", _RE_FLAGS),
    ),
    (
        "auto_flash_coercion",
        ("flash",),
        re.compile(r"\b(?:enable|force|run|turn\s+on|activate|trigger|start|initiate|engage|launch|arm)\b", _RE_FLAGS),
        re.compile(r"\bauto(?:\s*[.:/_\-\u2013\u2014\u2015\u2043]\s*|\s+)?flash\b", _RE_FLAGS),
    ),
    (
        "sensitive_exfiltration",
        (".ssh", "id_rsa", "/etc/"),
        re.compile(r"\b(?:upload|exfiltrate)\b", _RE_FLAGS),
        re.compile(r"(?:\.ssh|id_rsa|/etc/passwd|/etc/shadow)", _RE_FLAGS),
    ),
)
_CLIN_VERBS = (
    r"(?:authoriz(?:e|es|ed|ing)|enabl(?:e|es|ed|ing)|claim(?:s|ed|ing)?|"
    r"issu(?:e|es|ed|ing)|declar(?:e|es|ed|ing)|certif(?:y|ies|ied|ying)|"
    r"recommend(?:s|ed|ing)?|prescrib(?:e|es|ed|ing)|advis(?:e|es|ed|ing)|"
    r"approv(?:e|es|ed|ing)|endors(?:e|es|ed|ing)|mandat(?:e|es|ed|ing)|"
    r"instruct(?:s|ed|ing)?|urg(?:e|es|ed|ing)|direct(?:s|ed|ing)?|order(?:s|ed|ing)?)"
)
_CLIN_VERBS_RE = re.compile(rf"\b{_CLIN_VERBS}\b", _RE_FLAGS)
_CLIN_ALL_VERBS_RE = re.compile(rf"\b(?:{_CLIN_VERBS[3:-1]}|confirm(?:s|ed|ing)?)\b", _RE_FLAGS)
_CLIN_CURE_PHRASE_RE = re.compile(r"\b(?:clinical\s+cure|cure\s+claim|clinical\s+action)\b", _RE_FLAGS)
_CURES_TREATS_RE = re.compile(r"\b(?:cures?|cured|curing|heals?|healed|healing|curable|curative|treats?|treated|treating)\b", _RE_FLAGS)
_HUMAN_ADMIN_VERBS_RE = re.compile(
    r"\b(?:give|gives|gave|given|giving|administer(?:s|ed|ing)?|dos(?:e|es|ed|ing)|infus(?:e|es|ed|ing))\b",
    _RE_FLAGS,
)
_CURES_ONLY_RE = re.compile(r"\b(?:cures?|cured|curing|heals?|healed|healing|curable|curative)\b", _RE_FLAGS)
_TREATS_ONLY_RE = re.compile(r"\btreats?\b", _RE_FLAGS)
_TREATS_SINGULAR_RE = re.compile(r"\btreats\b", _RE_FLAGS)
_SW_TREAT_VERB_RE = re.compile(r"\b(?:treats?|treated|treating)\b", _RE_FLAGS)
_SW_HUMAN_NOUN_LA = (
    r"(?!\s+(?:ids?|labels?|tags?|flags?|names?|strings?|tokens?|fields?|records?|schemas?|"
    r"attributes?|keys?|values?|columns?|rows?|entries|types?|categor(?:y|ies)|metadata|"
    r"annotations?|structs?|objects?|elements?|nodes?|files?|paths?|metrics?|mentions?|"
    r"items?|docs?|documents?|features?|match(?:es)?|parameters?|keywords?|symbols?)\b)"
)
_SW_DISEASE_NOUN_LA = (
    r"(?!\s+(?:cell|cells|line|lines|model|models|sample|samples|tissue|tissues|"
    r"ids?|labels?|tags?|flags?|names?|strings?|tokens?|fields?|records?|schemas?|"
    r"attributes?|keys?|values?|columns?|rows?|entries|types?|categor(?:y|ies)|metadata|"
    r"annotations?|structs?|objects?|elements?|nodes?|files?|paths?|metrics?|mentions?|"
    r"items?|docs?|documents?|features?|match(?:es)?|parameters?|keywords?|symbols?|"
    r"terms?|entit(?:y|ies)|words?|identifiers?)\b)"
)
_HUMAN_TARGET_RE = re.compile(
    rf"\b(?:patients?|humans?|children|pediatric|adults?|infants?|people|teenagers?|elders?)\b{_SW_HUMAN_NOUN_LA}",
    _RE_FLAGS,
)
_ALL_DISEASE_TARGET_RE = re.compile(
    rf"\b(?:patients?|humans?|children|pediatric|adults?|infants?|people|teenagers?|elders?|glioma|glioblastoma|cancer|dmg|h3k27m|gbm|(?:brain\s+)?tumou?rs?)\b{_SW_HUMAN_NOUN_LA}",
    _RE_FLAGS,
)
_TREATED_DISEASE_RE = re.compile(
    r"\btreated\s+(?:(?:the|a|an|human|pediatric|recurrent|diffuse|midline|brain|malignant|metastatic)\s+){0,3}"
    rf"(?:glioma|glioblastoma|cancer|dmg|h3k27m|gbm)\b{_SW_DISEASE_NOUN_LA}",
    _RE_FLAGS,
)
_DISEASE_CLIN_NOUN_RE = re.compile(
    rf"\b(?:glioma|glioblastoma|cancer|dmg|h3k27m|gbm|brain\s+tumou?rs?)\b{_SW_DISEASE_NOUN_LA}",
    _RE_FLAGS,
)
_PASSIVE_TREATED_BY_WITH_RE = re.compile(
    r"\b(?:(?:is|are|was|were|be|being|been)\s+(?:(?:not|safely|effectively|successfully|commonly|routinely|clinically|widely|frequently|standardly|often|typically|usually|currently|historically|originally|initially)\s+){0,2}"
    r"treated(?:,\s*(?:with|by|using|via|through|alongside)"
    r"|(?:\s+(?:[a-z]+ly|[a-z]+-[a-z]+|very|quite|most|more|well|alone|here|there|now|today|first|instead|once|twice|thrice|long\s+term|short\s+term|in\s+clinic|in\s+patients?|at\s+(?:\d+(?:\.\d+)?\s*[a-z/%]{1,8}|[a-z]+\s+doses?)|for\s+(?:\d+\s+|several\s+|many\s+|a\s+few\s+)?(?:days?|weeks?|months?|years?)|over\s+(?:\d+\s+|several\s+)?(?:days?|weeks?|months?|years?))){0,4}(?:,\s*|\s+)(?:with|by|using|via|through|alongside))"
    r"|(?:is|are|was|were)\s+being\s+(?:[a-z]+ly\s+)?treated)\b",
    _RE_FLAGS,
)
_PRESCRIBE_RE = re.compile(r"\bprescrib(?:e|es|ed|ing)\b", _RE_FLAGS)
_RECOMMEND_RE = re.compile(r"\brecommend(?:s|ed|ing)?\b", _RE_FLAGS)
_DISEASE_CLIN_BASE = r"(?:glioma|glioblastoma|cancer|dmg|h3k27m|gbm|(?:brain\s+)?tumou?rs?)"
_TREATMENT_FOR_DISEASE_RE = re.compile(
    r"\b(?:treatments?|therap(?:y|ies))\s+(?:for|of|against|targeting|in)\s+(?:(?:the|a|an|human|pediatric|recurrent|diffuse|midline|brain|malignant|metastatic|effective|novel|potential|promising|standard|first-line|second-line)\s+){0,3}"
    rf"{_DISEASE_CLIN_BASE}\b{_SW_DISEASE_NOUN_LA}"
    rf"|\b{_DISEASE_CLIN_BASE}\s+(?:[a-z-]+\s+){{0,2}}(?:treatments?|therap(?:y|ies))\b{_SW_HUMAN_NOUN_LA}",
    _RE_FLAGS,
)
_ACTIVE_TREATED_TREATING_RE = re.compile(r"\b(?:treated|treating)\b", _RE_FLAGS)
_DISEASE_ONLY_RE = re.compile(r"\b(?:glioma|glioblastoma|cancer|dmg|h3k27m|gbm|(?:brain\s+)?tumou?rs?)\b", _RE_FLAGS)
_PRECLINICAL_QUAL_RE = re.compile(r"\b(?:cell\s+lines?|in\s+vitro|wet[- ]lab|assay|preclinical)\b", _RE_FLAGS)
_DIRECT_INQUIRY_RE = re.compile(r"^\s*(?:can|could|would|should|may|might|does)\b", _RE_FLAGS)
_QUESTION_OPENER_RE = re.compile(
    r"^\s*(?:can|could|would|should|may|might|does|do|is|are|which|what(?!\s+if\b)|how|why|when|where)\b",
    _RE_FLAGS,
)
_DO_PLURAL_PRONOUNS = frozenset({"you", "we", "they", "i", "these", "those", "both"})
_ASSERTIVE_MODAL_RE = re.compile(r"\b(?:will|shall|must)\b", _RE_FLAGS)
_CAUSAL_BREAK_RE = re.compile(r"\b(?:therefore|thus|hence|consequently|accordingly)\b|,\s*so\b", _RE_FLAGS)
_REL_TREATS_RE = re.compile(
    r"(?:\b(?!(?:and|or|but|so|yet|nor|if|whether)\b)[a-z0-9_-]+\s+that|\b(?:which|who))(?:,\s*|\s+)(?:(?!treats\b)[a-z]+ly\s+)?treats\b",
    _RE_FLAGS,
)
_WH_SUBJECT_RE = re.compile(r"^\s*(?:which|what(?!\s+if\b))\b", _RE_FLAGS)
_EPISTEMIC_Q_RE = re.compile(r"^\s*(?:is|are|was|were)\s+it\s+(?:true|possible|likely|plausible|clear|known|established)\s+that\b", _RE_FLAGS)
_MODAL_HEDGE_TREAT_RE = re.compile(
    r"\b(?:may|might|could|would)(?:,\s*|\s+)"
    r"(?:(?:not|also|still|never|well|only|just|even|ever|"
    r"in\s+(?:vitro|vivo|fact|preclinical|general|particular|practice|theory|principle)|"
    r"(?!treat\b)[a-z]+ly)(?:,\s*|\s+)){0,4}treat\b",
    _RE_FLAGS,
)
_SW_SUBJECT_RE = re.compile(
    r"\b(?:parser|lexer|tokenizer|compiler|interpreter|serializer|deserializer|validator|linter|formatter|"
    r"renderer|encoder|decoder|indexer|router|loader|importer|exporter|pipeline|script|module|function|method|"
    r"class|code|query|engine|database|schema|classifier|detector|predictor|tagger|splitter|chunker|analyzer|"
    r"network|model|framework|librar(?:y|ies)|service|apis?|regex(?:es)?|sanitizers?|runtimes?|mappers?)\b",
    _RE_FLAGS,
)
_SW_DATA_OBJ_RE = re.compile(
    r"\b(?:dataset|ids?|labels?|tags?|flags?|names?|tokens?|strings?|integers?|floats?|booleans?|bytes?|records?|rows?|columns?|"
    r"fields?|keys?|values?|metadata|annotations?|filenames?|paths?|entries|enums?|nodes?|ast|files?|mentions?|"
    r"class(?:es)?|elements?|items?|objects?|structs?|docs?|documents?|lines?|features?|categor(?:y|ies)|terms?|"
    r"entit(?:y|ies)|types?|words?|identifiers?|text|ascii|json|csv|yaml|xml|sql|regex|match(?:es)?|"
    r"parameters?|keywords?|symbols?|attributes?|payloads?|schemas?|metrics?|"
    r"sensitive|invalid|valid|deprecated|required|optional|nullable|protected|readonly|read-only|immutable|mutable|"
    r"public|private|internal|external|active|inactive|enabled|disabled|trusted|untrusted|stale|cached|indexed|"
    r"encoded|escaped|raw|blank|reserved|primary|secondary|canonical|legacy|experimental|restricted|confidential|pii|phi|"
    r"lowercase|uppercase|titlecase|camelcase|snake_case|topics?|negative|positive|neutral|unknown|null|none|missing|empty|default|literal|concepts?|alias(?:es)?|buckets?|groups?|clusters?|patterns?|rules?|examples?|stopwords?|outliers?|noise|priorit(?:y|ies)|weights?|scores?|ranks?|indices|constants?|variants?|"
    r"python|rust|java|cpp|typescript|javascript|golang|haskell|ocaml|kotlin|swift|ruby|perl|markdown|toml|protobuf|graphql|wasm|llvm)\b",
    _RE_FLAGS,
)
_PRECLINICAL_COMPOUND_RE = re.compile(
    r"\b(?:compound|drug|molecule|agent|therapy|therapies|treatment|treatments|inhibitor|inhibitors|dose|doses|dosing|mg|ug|ng|um|nm|gy|"
    r"oral(?:ly)?|intravenous(?:ly)?|proton\s+beam|photon\s+beam|radiosurgery|brachytherapy|gamma\s+knife|cyberknife|car-t|"
    r"temozolomide|radiation|radiotherapy|chemotherapy|immunotherapy|surgery|resection|placebo|regimen|monotherapy|adjuvant|"
    r"carboplatin|bevacizumab|lomustine|onc201|panobinostat|vorinostat|doxorubicin|irinotecan|"
    r"[a-z]{4,}(?:stat|nib|mab|platin|mustine|zomib|ciclib|parib|rubicin|taxel|tecan|mycin))\b",
    _RE_FLAGS,
)
_SW_WITH_ARG_RE = re.compile(
    r"\b(?:with|using|via|through|alongside)\s+(?:(?:the|a|an|our|my|this|that|custom|strict|standard)\s+){0,2}(?P<arg>[a-z0-9_-]+)\b",
    _RE_FLAGS,
)
_SW_SUBJECT_MOD_WORDS: frozenset[str] = frozenset({
    "the", "a", "an", "this", "that", "these", "those", "our", "my", "your", "their", "its",
    "each", "every", "both", "such", "all", "any",
    "json", "csv", "yaml", "xml", "sql", "regex", "ast", "html", "api", "cli",
    "nlp", "ml", "ai", "ui", "io", "db", "os", "ir", "vdi", "gem", "utf8", "ascii",
    "tumor", "tumour", "cancer", "glioma", "glioblastoma", "brain", "evaluation",
    "data", "text", "type", "syntax", "lexical", "identical", "target",
    "static", "dynamic", "linear", "neural", "binary", "custom", "native", "fast",
    "simple", "core", "base", "main", "local", "strict", "new", "novel", "small", "raw",
})
_SW_SUBJECT_HEAD_RE = re.compile(
    r"^(?:(?:parser|lexer|tokenizer|compiler|interpreter|serializer|deserializer|validator|linter|formatter|"
    r"renderer|encoder|decoder|indexer|router|loader|importer|exporter|pipeline|script|module|function|method|"
    r"class|code|query|engine|database|schema|classifier|detector|predictor|tagger|splitter|chunker|analyzer|"
    r"network|model|framework|service|api|sanitizer|runtime|mapper)s?|regex(?:es)?|librar(?:y|ies))$",
    _RE_FLAGS,
)
_SW_REL_CLAUSE_RE = re.compile(r",\s*which\b[^,;!?]*+,", _RE_FLAGS)
_SW_PRE_TREAT_MODAL_RE = re.compile(r"^(?:may|might|could|would|should|can|cannot|will|does|do|did|is|are|was|were|has|have|had|be|been)$", _RE_FLAGS)
_SW_Q_LEAD_RE = re.compile(
    r"^\s*(?:(?:how|why|when|where)\s+)?(?:does|do|can|could|would|should|may|might|will|did)\s+",
    _RE_FLAGS,
)
_SW_CLINICAL_CURE_RE = re.compile(r"\b(?:cures?|cured|curing|heals?|healed|healing|curable|curative|treatable)\b", _RE_FLAGS)
_CURE_SPLIT_RE = re.compile(
    r"([!?]+|;+|\r?\n|(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bdr)(?<!\bmr)(?<!\bms)(?<!\bmrs)"
    r"(?<!\bprof)(?<!\bfig)(?<!\bno)(?<!\beq)(?<!\bref)(?<!\bvol)(?<!\bet al)\.(?=\s|$))",
    _RE_FLAGS,
)

_INQUIRY_STEMS_RE = (
    r"check(?:s|ed|ing)?|test(?:s|ed|ing)?|evaluat(?:e|es|ed|ing)|"
    r"investigat(?:e|es|ed|ing)|assess(?:es|ed|ing)?|explor(?:e|es|ed|ing)|"
    r"examin(?:e|es|ed|ing)|stud(?:y|ies|ied|ying)|determin(?:e|es|ed|ing)|"
    r"ask(?:s|ed|ing)?|screen(?:s|ed|ing)?|see(?:s|ing)?|saw|seen|verif(?:y|ies|ied|ying)"
)
_INQUIRY_VERBS = rf"(?:{_INQUIRY_STEMS_RE})"
_REPORTING_CLIN_VERBS = (
    r"prov(?:e|es|ed|en|ing)|show(?:s|ed|n|ing)?|conclud(?:e|es|ed|ing)|"
    r"demonstrat(?:e|es|ed|ing)|establish(?:es|ed|ing)?|assert(?:s|ed|ing)?|"
    r"stat(?:e|es|ed|ing)|report(?:s|ed|ing)?|announc(?:e|es|ed|ing)|"
    r"proclaim(?:s|ed|ing)?|publish(?:es|ed|ing)?|attest(?:s|ed|ing)?|"
    r"validat(?:e|es|ed|ing)|suggest(?:s|ed|ing)?|maintain(?:s|ed|ing)?|"
    r"insist(?:s|ed|ing)?|indicat(?:e|es|ed|ing)|reveal(?:s|ed|ing)?|"
    r"impl(?:y|ies|ied|ying)|affirm(?:s|ed|ing)?|argu(?:e|es|ed|ing)|"
    r"contend(?:s|ed|ing)?|deduc(?:e|es|ed|ing)|infer(?:s|red|ring)?|"
    r"record(?:s|ed|ing)?|find(?:s|ing)?|found|observ(?:e|es|ed|ing)|"
    r"output(?:s|ted|ting)?|discover(?:s|ed|ing)?|not(?:e|es|ed|ing)|"
    r"say(?:s|ing)?|said|writ(?:e|es|ing)|wrote|written|tell(?:s|ing)?|told|"
    r"inform(?:s|ed|ing)?|promis(?:e|es|ed|ing)|swear(?:s|ing)?|swore|"
    r"hypothesiz(?:e|es|ed|ing)|posit(?:s|ed|ing)?|speculat(?:e|es|ed|ing)|"
    r"ensur(?:e|es|ed|ing)|recogniz(?:e|es|ed|ing)|learn(?:s|ed|t|ing)?|"
    r"document(?:s|ed|ing)?|repl(?:y|ies|ied|ying)|answer(?:s|ed|ing)?|know(?:s|ing)?|knew|known|"
    r"expect(?:s|ed|ing)?|predict(?:s|ed|ing)?|believ(?:e|es|ed|ing)|assum(?:e|es|ed|ing)|"
    r"propos(?:e|es|ed|ing)|explain(?:s|ed|ing)?|highlight(?:s|ed|ing)?|"
    r"consider(?:s|ed|ing)?|estimat(?:e|es|ed|ing)"
)
_CLIN_OR_REPORTING_VERBS_RE = re.compile(
    rf"\b(?:{_CLIN_VERBS[3:-1]}|confirm(?:s|ed|ing)?|{_REPORTING_CLIN_VERBS})\b"
    rf"|\b(?:conclusion|verdict|summary|finding|recommendation|result|outcome)s?\s*:",
    _RE_FLAGS,
)
_PASSIVE_REPORT_CLAUSE_RE = re.compile(r",\s*(?:as\s+(?:shown|reported|noted|observed|established|documented)|(?:when|if)\s+(?:tested|evaluated|screened|studied|assessed|assayed|examined|shown|documented|observed|reported|noted|established))\b", _RE_FLAGS)
_CLIN_OR_INQUIRY_VERBS_RE = re.compile(
    rf"\b(?:{_CLIN_VERBS[3:-1]}|confirm(?:s|ed|ing)?|{_REPORTING_CLIN_VERBS}|{_INQUIRY_STEMS_RE})\b"
    rf"|\b(?:conclusion|verdict|summary|finding|recommendation|result|outcome)s?\s*:",
    _RE_FLAGS,
)

_PAREN_FORBIDDEN_RE = re.compile(
    r"\b(?:treats?|cures?|that|declar\w*|claim\w*|certif\w*|authoriz\w*|confirm\w*|"
    r"whether|or\s+not|recommend\w*|prescrib\w*|advis\w*|prov\w*|conclud\w*|"
    r"demonstrat\w*|establish\w*|assert\w*|report\w*|announc\w*|proclaim\w*|publish\w*|attest\w*)\b",
    _RE_FLAGS,
)
_PAREN_NOTE_MARKER_RE = re.compile(
    r"\d|[%/=±]|(?:e\.g\.|i\.e\.|fig\.|dr\.|mr\.|ms\.|mrs\.|prof\.|vs\.|et\s+al\.|"
    r"in\s+vitro|in\s+vivo|wet[- ]lab|preclinical|cell\s+lines?|assay|note\b|panel\b|dose\b|"
    r"vehicle\b|dmso\b|pbs\b|saline\b|oral(?:ly)?\b|iv\b|intravenous\b|controls?\b)",
    _RE_FLAGS,
)
_PAREN_DISCOURSE_RE = re.compile(
    r"\b(?:clearly|indeed|actually|obviously|evidently|however|nevertheless|consequently|accordingly|"
    r"otherwise|therefore|thus|hence|moreover|furthermore|so|yet|then|if|because|since|although|though)\b"
    r"|\bin\s+(?:fact|reality|truth|practice|particular|short|summary|general|addition)\b",
    _RE_FLAGS,
)
_PAREN_PLUS_RE = re.compile(r"\bplus\b", _RE_FLAGS)
_PAREN_SAFE_PLUS_RE = re.compile(r",\s*plus\s+[a-z0-9_-]+\s*$", _RE_FLAGS)
_PAREN_TRAILING_ONLY_RE = re.compile(r"(?<!in\s)(?<!vitro\s)(?<!vivo\s)(?<!preclinical\s)\bonly\s*$", _RE_FLAGS)
_PAREN_TOK_RE = re.compile(r"\b[a-z]\.(?:[a-z]\.)+|[a-z0-9_-]+|[,;]", _RE_FLAGS)

_AUX_VERBS = frozenset({
    "is", "are", "was", "were", "has", "have", "had", "cannot",
    "can", "could", "may", "might", "will", "would", "should", "must", "do", "does", "did",
})
_PLURAL_AUX_OR_MODAL = frozenset({
    "are", "were", "have", "do",
    "can", "could", "may", "might", "will", "would", "should", "must",
})
_NON_VERB_S = frozenset({
    "this", "his", "its", "ours", "yours", "theirs", "us", "as", "plus", "thus", "yes",
    "always", "perhaps", "sometimes", "nowadays", "besides", "whereas", "unless", "regardless",
    "across", "versus", "minus", "compounds", "drugs", "candidates", "agents", "molecules",
    "therapies", "treatments", "regimens", "inhibitors", "agonists", "antagonists", "antibodies",
    "vaccines", "peptides", "nanoparticles", "analogs", "analogues", "prodrugs", "exosomes",
    "vesicles", "combos", "combinations", "cells", "lines", "assays", "mice", "rats",
    "patients", "humans", "children", "tumors", "tumours", "cancers", "gliomas",
    "dosages", "concentrations", "panels", "vehicles", "samples",
    "trials", "experiments", "results", "data", "levels", "pathways",
    "genes", "proteins", "receptors", "biomarkers", "mutations", "variants",
    "cohorts", "arms", "groups", "types", "classes", "stages", "grades", "weeks", "days",
    "hours", "minutes", "years", "times", "cases", "ones", "things", "others", "both", "all",
    "organoids", "spheroids", "xenografts", "metabolites", "endpoints",
    "conjugates", "derivatives", "extracts", "blockers", "liposomes", "formulations",
    "nanotubes", "fibers", "fibres", "gels", "hydrogels", "scaffolds", "sheets", "membranes",
    "matrices", "carriers", "vectors", "capsules", "micelles", "nanorods", "microspheres",
    "beads", "clusters", "amphiphiles", "oligonucleotides", "dendrimers", "polymers", "glioblastomas", "dots",
})
_NON_NOUN_S = frozenset({
    "this", "his", "its", "ours", "yours", "theirs", "us", "as", "plus", "thus", "yes",
    "always", "perhaps", "sometimes", "nowadays", "besides", "whereas", "unless", "regardless",
    "across", "versus", "minus",
})
_NON_PLURAL_LATIN_GREEK = frozenset({"alias", "atlas", "bias", "chaos", "gas", "pancreas"})
_DUAL_NOUN_VERB_S = frozenset({
    "targets", "controls", "tests", "models", "doses", "effects", "studies", "causes",
    "conjugates",
})
_NON_VERB_S_SUFFIXES = (
    "ous", "ness", "less", "ics", "sis", "xis", "tis", "tus", "rus", "lus", "cus", "mus", "nus", "pus", "sus",
    "somes", "ations", "utions", "ssions", "isions", "lsions", "usions", "nsions", "esions", "asions", "osions", "rsions",
)
_NON_PRED_ED = frozenset({
    "untreated", "labeled", "labelled", "isolated", "purified", "sealed", "approved", "verified",
    "grounded", "hedged", "targeted", "related", "combined", "paired", "blinded", "randomized",
    "controlled", "established", "validated", "modified", "engineered", "formulated",
    "encapsulated", "conjugated", "pegylated", "methylated", "acetylated", "phosphorylated",
    "mutated", "synthesized", "tested", "evaluated", "screened", "studied", "examined",
    "assessed", "assayed", "confirmed", "proven", "known", "associated", "derived", "based",
    "induced", "mediated", "driven", "linked", "coupled", "bound", "fused", "tolerated",
    "matched", "pretreated", "shown", "documented", "observed", "reported", "administered", "measured", "delivered",
})
_IRREGULAR_PAST_VERBS = frozenset({
    "gave", "became", "bound", "grew", "shrank", "fed", "drove", "split", "held", "led",
    "met", "took", "kept", "made", "found", "saw", "came", "went", "got", "said", "told",
    "knew", "thought", "felt", "left", "ran", "won", "lost", "built", "sent", "spent",
    "brought", "caught", "taught", "bought", "fought", "sought", "sold", "stood", "began",
    "broke", "chose", "spoke", "stole", "wore", "wrote", "rode", "rose", "fell", "drew",
    "flew", "threw", "blew", "overcame", "underwent", "withstood", "outgrew", "upheld",
    "undertook", "overtook", "dealt", "meant", "stuck", "struck", "froze", "spread",
    "hit", "hid", "shed", "bore", "bent", "lent", "slid", "fled", "bled", "bred", "sped",
    "laid", "paid", "heard", "hung", "dug", "spun", "swung", "clung", "flung", "stung",
    "tore", "swore", "shook", "ate", "forbade", "forgave", "drank", "rang", "sang", "sank",
    "sprang", "swam", "shot", "sat", "lit", "bit",
    "withheld", "beat", "offset", "withdrew", "arose", "hurt", "cast", "misled", "outdid",
    "forsook", "put", "shut", "cost", "burst", "thrust", "quit", "rid", "undid", "forbore",
    "wove", "strove", "throve", "smote", "shone", "strode", "slunk", "slung", "wrought",
    "begot", "partook", "mistook", "stank", "cut", "remade", "relaid", "repaid", "resold",
    "retold", "crept", "leapt", "cleft", "trod", "overran", "outran", "dwelt", "knelt",
    "wept", "burnt", "spilt", "spoilt", "slunk", "unwound", "rewound", "oversaw",
})
_INTRANSITIVE_ED_VERBS = frozenset({
    "reacted", "cross-reacted", "interacted", "synergized", "competed", "proliferated",
    "accumulated", "persisted", "migrated", "diffused", "responded", "contributed",
    "interfered", "belonged", "consisted", "depended", "relied", "worked", "failed",
    "succeeded", "resulted", "acted", "functioned", "performed", "converged", "diverged",
    "cooperated", "collaborated", "correlated", "coexisted", "differed", "varied",
    "oscillated", "fluctuated", "stabilized", "progressed", "regressed", "metastasized",
    "occurred", "emerged", "showed", "appeared", "seemed", "remained", "stayed",
    "improved", "worsened", "increased", "decreased", "dropped", "shifted", "changed",
})
_AUX_OR_IRREG_VERBS = _AUX_VERBS | _IRREGULAR_PAST_VERBS
_STRICT_DET_AND_PREP = frozenset({
    "the", "a", "an", "my", "our", "your", "his", "her", "its", "their",
    "some", "any", "no", "every", "each", "such", "other", "in", "at", "on", "of", "for", "to", "by",
    "with", "from", "via", "as", "under", "into", "onto", "upon", "between", "among", "through", "during",
    "without", "within", "about",
})
_DEMONSTRATIVES = frozenset({"this", "that", "these", "those"})
_DETERMINERS_AND_PREPS = _STRICT_DET_AND_PREP | _DEMONSTRATIVES
_SINGULAR_DETS = frozenset({
    "the", "a", "an", "my", "our", "your", "his", "her", "its", "their",
    "this", "that", "each", "every", "one", "no",
})
_CLAUSE_PREPS = frozenset({
    "in", "at", "on", "under", "with", "by", "for", "via", "from", "of", "into", "onto", "upon",
    "between", "among", "through", "during", "without", "within", "about",
})
_POSTMOD_PARTICIPLE_NEXT = _CLAUSE_PREPS | {"to", "as", "against", "across", "over"}
_POSTMOD_ING = frozenset({
    "containing", "targeting", "carrying", "inhibiting", "bearing", "expressing",
    "blocking", "binding", "delivering", "inducing", "modulating", "activating", "using",
})
_FINITE_ING_VERBS = frozenset({
    "bring", "sing", "ring", "sting", "cling", "fling", "swing", "wring", "spring",
})
_NON_VERB_NEXT_STOP = frozenset({"and", "or", "nor", "but", "plus", "that", "which", "who", "treat", "treats"})
_NON_ID_NEXT_STOP = _NON_VERB_NEXT_STOP | {"only", "alone", "both", "not", "vs"}
_PLURAL_BASE_VERBS = frozenset({
    "work", "kill", "block", "bind", "act", "cross", "reverse", "shrink", "slow", "halt", "stop",
    "prevent", "reach", "clear", "stay", "remain", "become", "show", "seem", "appear", "help",
    "affect", "alter", "cause", "trigger", "promote", "improve", "extend", "prolong", "pass", "enter",
    "degrade", "diffuse", "evade", "resist", "survive", "achieve", "yield", "succeed", "fail",
    "persist", "combat", "fight", "function", "perform", "respond", "target", "cut", "drop", "fall",
    "grow", "lower", "raise", "run", "save", "use", "drive", "hold", "keep", "lead", "make", "move",
    "play", "tend", "try", "deplete", "restore", "rescue", "destroy", "repair", "cleave", "lyse",
    "spare", "halve", "double", "outperform", "overcome", "mimic", "reprogram", "remodel", "curb",
    "blunt", "spur", "quell", "stem", "tame", "starve", "stall", "control", "arrest", "delay",
    "erode", "shield", "protect", "attack", "bypass", "dampen", "abrogate", "attenuate",
    "demonstrate", "eliminate", "inhibit", "suppress", "silence", "reduce", "induce", "activate",
    "modulate", "sensitize", "potentiate", "synergize", "downregulate", "upregulate",
    "penetrate", "exhibit", "accumulate", "mitigate", "ameliorate", "alleviate", "regress",
    "lack", "exert", "carry", "proliferate",
})
_PLURAL_HEADS = frozenset({
    "these", "those", "we", "they", "you", "i", "mice", "rats", "children", "patients", "humans", "data",
    "bacteria", "nuclei", "criteria", "media", "foci", "loci", "stimuli", "phenomena", "fungi",
    "alumni", "indices", "matrices", "vertices", "analyses", "hypotheses", "diagnoses", "prognoses",
    "crises", "metastases", "genera",
})
_AGENT_SUBJECTS = frozenset({
    "researchers", "researcher", "clinicians", "clinician", "scientists", "scientist",
    "investigators", "investigator", "chemists", "chemist", "authors", "author",
    "biologists", "biologist", "physicians", "physician", "doctors", "doctor",
    "nurses", "nurse", "pharmacists", "pharmacist", "hospitals", "hospital",
    "clinics", "clinic", "providers", "provider", "practitioners", "practitioner",
    "residents", "resident", "surgeons", "surgeon", "therapists", "therapist",
    "caregivers", "caregiver", "teams", "team", "colleagues", "analysts", "analyst",
    "medics", "medic", "midwives", "midwife", "dentists", "dentist", "fellows", "fellow",
    "interns", "intern", "paramedics", "paramedic", "people", "specialists", "specialist",
    "trainees", "trainee", "assistants", "assistant", "volunteers", "volunteer", "participants", "participant", "staff",
    "professors", "professor", "postdocs", "postdoc", "students", "student", "faculty",
    "educators", "educator", "instructors", "instructor", "lecturers", "lecturer",
    "we", "they", "he", "she", "i", "you",
})
_COMPLEMENT_NOUNS = frozenset({
    "fact", "observation", "hypothesis", "finding", "notion", "idea", "belief", "assumption",
    "theory", "possibility", "evidence", "likelihood", "chance", "claim", "conclusion",
    "verdict", "assertion", "statement", "report", "prediction", "expectation", "proposition",
    "argument", "view", "indication", "proof", "sign", "result",
})
_SINGULAR_NOUNS_NON_VERB = frozenset({
    "compound", "drug", "molecule", "agent", "therapy", "candidate", "protein", "gene",
    "receptor", "biomarker", "tumor", "tumour", "cancer", "glioma", "group", "cohort",
    "vehicle", "sample", "assay", "pathway", "organoid", "spheroid", "xenograft",
    "liposome", "nanoparticle", "conjugate", "derivative", "extract", "blocker",
    "formulation", "delivery", "um", "nm", "mm", "mg", "kg", "ml", "iv", "po",
    "pbs", "dmso", "peg", "pegylation", "ezh2", "vegf", "dmg", "gbm", "h3k27m", "prc2", "bbb",
    "glioblastoma", "brain", "liver", "tissue", "marrow", "buffer", "media", "serum", "plasma", "saline", "water",
    "vial", "dish", "plate", "lab", "institute", "peptide", "oxide", "dot",
    "alpha", "beta", "gamma", "delta", "epsilon", "zeta", "eta", "theta", "iota", "kappa",
    "lambda", "mu", "nu", "xi", "omicron", "pi", "rho", "sigma", "tau", "upsilon", "phi", "chi", "psi", "omega",
})
_REPORTING_STEMS = frozenset({
    "confirm", "state", "note", "report", "say", "assert", "affirm", "conclude", "establish",
    "prove", "verify", "show", "announce", "attest", "indicate", "demonstrate", "claim",
    "declare", "certify", "issue", "authorize", "enable", "proclaim", "insist", "maintain",
    "argue", "contend", "reveal", "imply", "suggest", "deduce", "infer", "write", "find",
    "ensure", "observe", "output", "publish", "discover", "learn", "document", "record",
    "reply", "answer", "know", "recognize", "tell", "inform", "promise", "swear",
    "hypothesize", "posit", "speculate", "advise", "recommend", "prescribe",
    "expect", "predict", "believe", "assume", "propose", "explain", "highlight",
    "consider", "estimate", "approve", "endorse", "mandate", "instruct", "urge", "direct", "order",
    "confirms", "states", "notes", "reports", "says", "asserts", "affirms", "concludes",
    "establishes", "proves", "verifies", "shows", "announces", "attests", "indicates",
    "demonstrates", "claims", "declares", "certifies", "issues", "authorizes", "enables",
    "proclaims", "insists", "maintains", "argues", "contends", "reveals", "implies",
    "suggests", "deduces", "infers", "writes", "finds", "ensures", "observes", "outputs",
    "publishes", "discovers", "learns", "documents", "records", "replies", "answers",
    "knows", "recognizes", "tells", "informs", "promises", "swears", "hypothesizes",
    "posits", "speculates", "advises", "recommends", "prescribes",
    "expects", "predicts", "believes", "assumes", "proposes", "explains", "highlights",
    "considers", "estimates", "approves", "endorses", "mandates", "instructs", "urges", "directs", "orders",
    "confirmed", "stated", "noted", "reported", "said", "asserted", "affirmed", "concluded",
    "established", "proved", "proven", "verified", "showed", "shown", "announced", "attested",
    "indicated", "demonstrated", "claimed", "declared", "certified", "issued", "authorized",
    "enabled", "proclaimed", "insisted", "maintained", "argued", "contended", "revealed",
    "implied", "suggested", "deduced", "inferred", "wrote", "written", "found", "ensured",
    "observed", "outputted", "published", "discovered", "learned", "documented", "recorded", "told",
    "informed", "replied", "answered", "knew", "known", "recognized", "promised", "swore",
    "hypothesized", "posited", "speculated", "advised", "recommended", "prescribed",
    "expected", "predicted", "believed", "assumed", "proposed", "explained", "highlighted",
    "considered", "estimated", "approved", "endorsed", "mandated", "instructed", "urged", "directed", "ordered",
})
_PRONOUN_SUBJ = frozenset({"it", "this", "that", "these", "those", "they", "he", "she", "we", "you", "i"})
_REL_PRONOUNS = frozenset({"we", "you", "they", "he", "she", "i"})
_BARE_PRONOUN_SUBJ = frozenset({"it", "they", "he", "she", "we", "you", "i"})
_PAREN_CLAUSE_PRONOUNS = _REL_PRONOUNS | {"it"}
_INVESTIGATIVE_GERUND = (
    r"(?:testing|evaluating|screening|studying|checking|asking|confirming|"
    r"investigating|assessing|examining|exploring|analyzing|measuring|dosing|"
    r"administering|delivering|assaying|profiling|monitoring|tracking)"
)
_ADV_PREPS = frozenset({
    "in", "at", "on", "under", "with", "by", "for", "via", "from",
    "to", "as", "against", "into", "onto", "within", "through", "across", "upon", "over", "between", "among", "without",
})
_IN_FIXED_WORDS = frozenset({
    "reality", "truth", "practice", "particular", "short", "summary",
    "general", "fact", "addition", "combination", "vitro", "vivo", "preclinical",
})
_SINGLE_ADV_WORDS = frozenset({
    "also", "then", "now", "here", "only", "just", "still", "even", "ever", "never",
    "always", "effectively", "safely", "clearly", "actually", "indeed", "obviously", "evidently",
    "not", "well", "too", "so", "enough",
})
_ADV_LINK_WORDS = _SINGLE_ADV_WORDS | {"and", "or"}
_PP_STOP_WORDS = frozenset({
    "treats", "treat", "cures", "cure", "and", "or", "but", "plus", "that", "whether", "if",
}) | _PRONOUN_SUBJ
_SUBJECT_CONTROL_WORDS = frozenset({
    "able", "unable", "likely", "unlikely", "apt", "bound", "ready", "free", "safe",
    "potent", "effective", "sufficient", "shown", "known", "proven", "found", "seen",
    "expected", "predicted", "thought", "believed", "hypothesized", "supposed",
    "designed", "intended", "engineered", "formulated", "reported", "observed",
    "assumed", "considered", "estimated", "used", "needed", "required", "going", "enough",
})
_MORPH_S_VERB_RE = re.compile(r"^[a-z]+(?:-[a-z]+)*s$")
_MORPH_ED_VERB_RE = re.compile(r"^[a-z]{3,}(?:-[a-z]{2,})*ed$")
_PRE_NOMINAL_ADJS = frozenset({
    "novel", "new", "oral", "small", "potent", "safe", "effective", "active", "inactive",
    "lipid", "bare", "free", "pure", "crude", "raw", "high", "low", "single", "dual",
    "triple", "multiple", "primary", "secondary", "preclinical", "clinical",
    "investigational", "experimental", "synthetic", "natural", "stable", "soluble",
    "selective", "specific", "water-soluble", "lipid-soluble", "quantum", "both", "neither", "either",
})
_NON_SUBJ_WORDS = _DETERMINERS_AND_PREPS | _SINGLE_ADV_WORDS | _PRE_NOMINAL_ADJS
_ADJ_COMMA_SUFFIXES = ("ed", "ing", "al", "ic", "ous", "ive")
_ELLIPTIC_IF_WORDS = frozenset({
    "tested", "evaluated", "screened", "studied", "proven", "verified", "confirmed",
    "done", "so", "effective", "possible", "feasible", "viable",
})
_CONCESSIVE_TAIL_WORDS = _ELLIPTIC_IF_WORDS | _ADV_PREPS
_CLAUSE_BOUNDARY_KINDS = frozenset({
    "hard_break", "whether_or_not", "whether", "confirm", "inquiry_if", "punct", "rel_paren", "that",
})
_SINGULAR_PRONOUN_OR_REL = frozenset({"this", "that", "it", "he", "she", "which", "who"})

_CLAUSE_TOKEN_RE = re.compile(
    rf"(?P<hard_break>"
    rf"\x00PN\x00"
    rf"|;+"
    rf"|\b(?:regardless\s+of|irrespective\s+of|no\s+matter)\s+whether\b(?:\s+or\s+not\b)?|\bor\s+not\b"
    rf"|\b(?:although|though|whereas|since|because|even\s+though|even\s+if)\b"
    rf"|\b(?:therefore|thus|hence|moreover|furthermore|however|nevertheless|consequently|accordingly|otherwise)\b"
    rf"|(?:--|[\u2013\u2014]|(?<!\d):(?:\s+|(?=[a-z])))"
    rf")"
    rf"|(?P<rel_paren>\x00PR\x00)"
    rf"|(?P<whether_or_not>\bwhether\s+or\s+not\b)"
    rf"|(?P<only_that_noun>\bonly\s+that\s+(?!(?:it|this|these|they|he|she|we|you|i)\b)[a-z][a-z0-9_-]*\b)"
    rf"|(?P<gerund_that_noun>\b{_INVESTIGATIVE_GERUND}\s+that\s+(?!(?:it|this|these|they|he|she|we|you|i)\b)[a-z][a-z0-9_-]*\b)"
    rf"|(?P<paren_open>,\s*(?:which\b|who\b|where\b|whether\s+or\s+not\b|(?:as|when|if)\s+(?:shown|tested|evaluated|documented|observed|reported)\b))"
    rf"|(?P<comma_coord>,\s*(?:and|or)\b)"
    rf"|(?P<comma>,)"
    rf"|(?P<abbrev>\b(?:e\.g|i\.e|vs|dr|mr|ms|mrs|prof|fig|no|eq|ref|vol|et\s+al)\.(?=\s|$))"
    rf"|(?P<punct>[!?]+|(?<!\d)\.(?=\s|$))"
    rf"|(?P<inquiry_if>\b{_INQUIRY_VERBS}\s+if\b)"
    rf"|(?P<whether>\bwhether\b)"
    rf"|(?P<confirm>\bconfirm\b)"
    rf"|(?P<inquiry>\b{_INQUIRY_VERBS}\b)"
    rf"|(?P<coord>\b(?:and|or|nor|but|plus)\b)"
    rf"|(?P<adv_break>\b(?:then|also|so|yet|clearly|actually|indeed|obviously|evidently)\b|\bin\s+(?:fact|reality|truth|practice|particular|short|summary|general|addition)\b)"
    rf"|(?P<treats>\btreats?\b)"
    rf"|(?P<that>\bthat\b)"
    rf"|(?P<word>\b[a-z0-9_]+(?:-[a-z0-9_]+)*(?:\.[a-z0-9_]+)?\b)",
    _RE_FLAGS,
)


class ClauseToken(NamedTuple):
    """Single immutable token from linear clause tokenization."""

    kind: str
    raw: str
    low: str


_normalize_firewall_text = normalize_firewall_text
_has_cf_chars = has_cf_chars
_split_mixed_cf_tokens = segment_mixed_cf_tokens


def _has_ordered_match(text: str, *patterns: re.Pattern[str]) -> bool:
    """Return True if all regex patterns match sequentially from left to right (O(n))."""
    pos = 0
    for pattern in patterns:
        match = pattern.search(text, pos)
        if match is None:
            return False
        pos = match.end()
    return True


_NON_ADVERB_LY_SUFFIXES = ("rely", "apply", "supply", "reply", "comply", "imply", "multiply")


def _is_ly_adverb(wl: str) -> bool:
    if len(wl) < 5 or wl == "only" or wl.endswith(_NON_ADVERB_LY_SUFFIXES):
        return False
    return wl.endswith("ly") and wl.replace("-", "").isalpha()


def _is_adv_link(wl: str) -> bool:
    return wl in _ADV_LINK_WORDS or _is_ly_adverb(wl)


def _is_s_verb(wl: str) -> bool:
    if len(wl.replace("-", "")) < 4 or not _MORPH_S_VERB_RE.match(wl) or wl.endswith("ss"):
        return False
    tail = wl.rsplit("-", 1)[-1]
    return tail not in _NON_VERB_S and not tail.endswith(_NON_VERB_S_SUFFIXES)


def _is_ed_verb(wl: str) -> bool:
    return bool(_MORPH_ED_VERB_RE.match(wl)) and len(wl) >= 5 and wl not in _NON_PRED_ED


def _is_short_id_token(prev_raw: str) -> bool:
    if len(prev_raw) > 4 or not prev_raw.isalnum():
        return False
    return prev_raw.isupper() or any(ch.isdigit() for ch in prev_raw)


def _paren_is_s_clause(raw_words: list[str], words: list[str], idx: int, wl: str) -> bool:
    if not _is_s_verb(wl) or wl in _DUAL_NOUN_VERB_S or raw_words[idx][0].isupper():
        return False
    if idx > 0 and raw_words[idx - 1] != "A" and words[idx - 1] in _DETERMINERS_AND_PREPS:
        return False
    return idx < len(words) - 1 or (idx > 0 and words[idx - 1] in {"this", "that"})


def _paren_ed_prev_blocks(raw_words: list[str], words: list[str], idx: int) -> bool:
    prev = words[idx - 1]
    if prev.endswith("ly") or prev in {",", "and", "or", "dose", "doses", "assay"}:
        return True
    return raw_words[idx - 1] != "A" and prev in _DETERMINERS_AND_PREPS


def _paren_is_ed_clause(raw_words: list[str], words: list[str], idx: int, wl: str) -> bool:
    if idx == 0 or _paren_ed_prev_blocks(raw_words, words, idx):
        return False
    if _is_ed_verb(wl):
        return True
    return wl in _NON_PRED_ED and idx + 1 < len(words) and words[idx + 1] not in _POSTMOD_PARTICIPLE_NEXT


def _paren_token_is_clause_marker(raw_words: list[str], words: list[str], idx: int, wl: str) -> bool:
    if wl in _AUX_OR_IRREG_VERBS or wl in _PAREN_CLAUSE_PRONOUNS:
        return True
    return _paren_is_ed_clause(raw_words, words, idx, wl) or _paren_is_s_clause(raw_words, words, idx, wl)


def _is_paren_rel_verb(w: str) -> bool:
    return _is_s_verb(w) or _is_ed_verb(w) or w in _AUX_OR_IRREG_VERBS or w in _PLURAL_BASE_VERBS


def _paren_coord_next_idx(words: list[str], start: int) -> int:
    j = start
    while j < len(words) and words[j] not in {"and", "or"} and _is_adv_link(words[j]):
        j += 1
    return j


def _paren_rel_coord_ok(words: list[str]) -> bool:
    for i, w in enumerate(words):
        if w not in {"and", "or"}:
            continue
        j = _paren_coord_next_idx(words, i + 1)
        if j >= len(words):
            return False
        is_verb = _is_paren_rel_verb(words[j]) or words[j] in _NON_PRED_ED
        if not is_verb and any(_is_paren_rel_verb(t) for t in words[j + 1 :]):
            return False
    return True


def _paren_rel_is_benign(words: list[str]) -> bool:
    if len(words) < 2 or any(w in {"but", "also"} for w in words):
        return False
    if any(w in _PAREN_CLAUSE_PRONOUNS for w in words[1:]):
        return False
    return _paren_rel_coord_ok(words)


def _paren_has_blocked_markers(inner: str) -> bool:
    if ";" in inner:
        return True
    if _PAREN_FORBIDDEN_RE.search(inner) or _PAREN_DISCOURSE_RE.search(inner):
        return True
    return bool(_PAREN_TRAILING_ONLY_RE.search(inner)) and not _PAREN_NOTE_MARKER_RE.search(inner)


def _paren_also_invalid(words: list[str]) -> bool:
    if "also" not in words:
        return False
    return len(words) < 3 or words[0] != "also" or words[1] not in {"known", "called"}


def _paren_words_invalid(inner: str, words: list[str]) -> bool:
    if "but" in words or all(w in {"and", "or", "also", ","} for w in words):
        return True
    if _paren_also_invalid(words):
        return True
    return bool(_PAREN_PLUS_RE.search(inner)) and not (_PAREN_NOTE_MARKER_RE.search(inner) and _PAREN_SAFE_PLUS_RE.search(inner))


def _paren_break_token(inner: str) -> str:
    m_tr = _TREATS_ONLY_RE.search(inner)
    return f" \x00PN\x00 {m_tr.group(0)} " if m_tr else " \x00PN\x00 "


def _classify_paren(inner: str) -> str:
    """Classify parenthetical span as benign note (' '), non-restrictive relative (' \\x00PR\\x00 '), or break (' \\x00PN\\x00 ')."""
    if _paren_has_blocked_markers(inner):
        return _paren_break_token(inner)
    raw_words = _PAREN_TOK_RE.findall(inner)
    if not raw_words:
        return " "
    words = [w.lower() for w in raw_words]
    if _paren_words_invalid(inner, words):
        return _paren_break_token(inner)
    if words[0] in {"which", "who"}:
        return " \x00PR\x00 " if _paren_rel_is_benign(words) else _paren_break_token(inner)
    has_clause = any(_paren_token_is_clause_marker(raw_words, words, idx, wl) for idx, wl in enumerate(words))
    return _paren_break_token(inner) if has_clause else " "


def _mask_parens_linear(sent: str) -> str:
    """Replace balanced (...) spans linearly in O(n) without regex backtracking."""
    out: list[str] = []
    last = 0
    depth = 0
    start = -1
    for idx, ch in enumerate(sent):
        if ch == "(":
            if depth == 0:
                out.append(sent[last:idx])
                start = idx
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
            if depth == 0:
                out.append(_classify_paren(sent[start + 1 : idx]))
                last = idx + 1
    out.append(sent[start if depth > 0 else last :])
    return "".join(out)


def _tokenize_clause_stream(masked: str) -> tuple[ClauseToken, ...]:
    """Tokenize masked sentence once in strictly O(n) time."""
    return tuple(ClauseToken(m.lastgroup or "word", m.group(0), m.group(0).lower()) for m in _CLAUSE_TOKEN_RE.finditer(masked))


_MODAL_AUX_VERBS = frozenset({
    "can", "could", "may", "might", "will", "would", "should", "must", "do", "does", "did", "cannot",
})
_COPULA_OR_CONTROL_VERBS = frozenset({
    "is", "are", "was", "were", "seems", "seem", "appears", "appear", "proved", "prove", "found", "shown",
})


def _reset_clause_state(s: bool = False) -> dict[str, Any]:
    return {
        "s": s, "h": False, "p": False, "p_is_modal": False, "p_is_copula": False, "r": False, "lp": False,
        "in_paren": False, "in_rel": False, "had_rel": False,
        "coord_s_verb": False, "after_coord": False,
        "cw": [], "post_p": [], "cw_has_prep": False, "cw_has_not": False, "cw_has_subj": False,
        "cw_head_plural": False, "cw_has_adv": False, "cw_has_agent": False, "cw_has_to_pp": False,
        "cw_all_adj": True, "cw_scan_from": 0,
        "post_p_has_content": False, "adv_ok_until": 0, "list_ok_until": 0,
        "np_head_ok_until": 0, "adv_comma_until": 0, "coord_np_ok_until": 0, "coord_np_fail_until": 0,
        "coord_np_or_ok_until": 0, "coord_np_or_fail_until": 0, "appos_ok_until": 0,
    }


def _prev_blocks_verb(cw: list[str], wl: str) -> bool:
    if not cw:
        return False
    prev_raw = cw[-1]
    prev = prev_raw.lower()
    if prev_raw != "A" and prev in _STRICT_DET_AND_PREP:
        return True
    if prev in {"this", "that"}:
        return wl in _PLURAL_BASE_VERBS
    return prev in {"these", "those"} and _is_s_verb(wl)


_PRE_PARTICIPLE_ADVS = frozenset({"well", "poorly", "ill"})


def _prev_is_np_adv(cw: list[str]) -> bool:
    if not cw:
        return False
    prev = cw[-1].lower()
    if not (prev.endswith("ly") or prev in _PRE_PARTICIPLE_ADVS):
        return False
    return len(cw) == 1 or (cw[-2] != "A" and cw[-2].lower() in _DETERMINERS_AND_PREPS)


def _dual_prev_is_singular_subj(cw: list[str], prev_raw: str, prev: str, in_rel: bool) -> bool:
    if prev in _SINGULAR_PRONOUN_OR_REL or _is_short_id_token(prev_raw):
        return True
    if in_rel and prev == "that":
        return True
    return len(cw) >= 2 and cw[-2] != "A" and cw[-2].lower() in _SINGULAR_DETS and not prev.endswith("s")


_DUAL_ADJ_NEXT = _POSTMOD_PARTICIPLE_NEXT | _POSTMOD_ING | {"and", "or", ",", "treat", "treats"}


def _dual_prev_blocks(prev_raw: str, prev: str, nxt_low: str) -> bool:
    if (prev in _DETERMINERS_AND_PREPS and prev_raw != "A") or _is_plural_noun_token(prev):
        return True
    return prev in _PRE_NOMINAL_ADJS and nxt_low in (_DUAL_ADJ_NEXT | {"that"})


def _is_dual_verb_s(
    wl: str,
    cw: list[str],
    nxt_low: str,
    in_rel: bool = False,
    tokens: tuple[ClauseToken, ...] | None = None,
    idx: int = -1,
    st: dict[str, Any] | None = None,
) -> bool:
    if wl not in _DUAL_NOUN_VERB_S or not cw or nxt_low == "treat":
        return False
    prev_raw, prev = cw[-1], cw[-1].lower()
    if _dual_prev_blocks(prev_raw, prev, nxt_low):
        return False
    if tokens is not None and st is not None and _is_plural_np_with_pp_before_treat(tokens, idx, st):
        return False
    if _dual_prev_is_singular_subj(cw, prev_raw, prev, in_rel):
        return True
    return nxt_low not in {"and", "or", ",", "treat", "treats"}


_PLURAL_HEAD_EXCL = frozenset({"this", "his", "its", "as", "us", "plus", "thus"})
_DETS_ONLY = _SINGULAR_DETS | {"these", "those", "all", "some", "any", "such", "other"}
_NON_PLURAL_VERB_PREV = _DETERMINERS_AND_PREPS | _PRE_NOMINAL_ADJS | {"and", "or", "nor", "but", "plus"}
_TRANSITIVE_NOUN_VERBS = frozenset({"assay", "extract", "sample"})
_NON_PLAIN_VERB_WORDS = (
    _DETERMINERS_AND_PREPS | _POSTMOD_ING | _NON_ID_NEXT_STOP
    | _NON_PRED_ED | _NON_VERB_S | _PLURAL_HEADS | _SINGULAR_NOUNS_NON_VERB
)
_NON_PRED_ED_STOP = _POSTMOD_PARTICIPLE_NEXT | {"", ",", "and", "or", "but", "plus", "treat", "treats"}


_COLLECTIVE_AGENT_HEADS = frozenset({
    "group", "panel", "cohort", "team", "board", "committee", "consortium", "faculty", "association", "society",
})
_AGENT_SUFFIXES = (
    "ologists", "ologist", "icians", "ician", "iatrists", "iatrist", "apists", "apist",
    "surgeons", "surgeon", "scientists", "scientist", "chemists", "chemist",
    "pharmacists", "pharmacist", "specialists", "specialist", "analysts", "analyst",
    "internists", "internist", "hospitalists", "hospitalist", "practitioners", "practitioner",
)


def _is_agent_subject(w: str) -> bool:
    head = w.rsplit("-", 1)[-1] if "-" in w else w
    return head in _AGENT_SUBJECTS or (len(head) >= 7 and head.endswith(_AGENT_SUFFIXES))


def _has_agent_subject(cw: list[str]) -> bool:
    for idx, w in enumerate(cw):
        wl = w.lower()
        if _is_agent_subject(wl):
            return True
        if wl == "of" and idx > 0 and cw[idx - 1].lower() in _COLLECTIVE_AGENT_HEADS:
            continue
        if wl in _CLAUSE_PREPS or wl in {"to", "as", "against", ","}:
            break
    return False


def _has_verb_stem_shape(wl: str) -> bool:
    if not wl.replace("-", "").isalpha():
        return False
    if wl.endswith("s") and not wl.endswith("ss"):
        return False
    if wl.endswith("ing") and wl not in _FINITE_ING_VERBS:
        return False
    return not (_is_ed_verb(wl) or _is_s_verb(wl) or _is_ly_adverb(wl))


def _is_plain_verb_candidate(
    wl: str, nxt_low: str = "", cw_head_plural: bool = False, cw_has_prep: bool = False
) -> bool:
    if len(wl) < 2 or not wl.replace("-", "").isalpha():
        return False
    if wl in _TRANSITIVE_NOUN_VERBS and cw_head_plural and not cw_has_prep:
        return nxt_low not in (_NON_VERB_NEXT_STOP | _CLAUSE_PREPS | {"", ","})
    if wl in _NON_PLAIN_VERB_WORDS or wl in _PRE_NOMINAL_NOUN_MODS:
        return False
    return _has_verb_stem_shape(wl)


def _is_det_sing_pair(cw: list[str], prev: str) -> bool:
    return len(cw) >= 2 and cw[-2].lower() in _DETS_ONLY and not prev.endswith("s") and prev not in _PLURAL_HEADS


def _plural_prev_blocks(cw: list[str], nxt_low: str = "", cw_has_prep: bool = False, wl: str = "") -> bool:
    prev = cw[-1].lower()
    if prev in _NON_PLURAL_VERB_PREV or prev.endswith("ing") or not prev.replace("-", "").isalpha():
        return True
    if not cw_has_prep:
        return _is_det_sing_pair(cw, prev)
    if wl not in _PLURAL_BASE_VERBS and _is_det_sing_pair(cw, prev):
        return nxt_low in (_CLAUSE_PREPS | {"treat", "treats", "and", "or", ",", ""})
    return False


def _plural_noun_takes_verb(
    cw: list[str], wl: str, cw_has_prep: bool = False, cw_head_plural: bool = False, nxt_low: str = ""
) -> bool:
    if not cw or not _is_plain_verb_candidate(wl, nxt_low, cw_head_plural, cw_has_prep):
        return False
    if cw_head_plural and not _plural_prev_blocks(cw, nxt_low, cw_has_prep, wl):
        return True
    if cw_has_prep:
        return False
    head = cw[-1].lower()
    return head in _PLURAL_HEADS or _is_plural_noun_token(head)


_NON_VERB_AFTER_ID_EXTRA = frozenset({"unlike", "rather", "instead"})


def _is_non_verb_after_id(wl: str) -> bool:
    if wl in (_NON_PLAIN_VERB_WORDS | _PRE_NOMINAL_ADJS | _NON_VERB_AFTER_ID_EXTRA):
        return True
    return wl.endswith("like") or _is_sing_nominal(wl) or _is_ly_adverb(wl)


def _id_followed_by_verb(
    cw: list[str], raw_word: str, wl: str, cw_has_prep: bool = False, eff_nxt: str = "", has_agent: bool | None = None
) -> bool:
    if not cw or cw_has_prep or len(wl) < 2 or not raw_word.islower():
        return False
    if cw[-1] == "I" or not _is_short_id_token(cw[-1]) or _is_passive_postmod_ed(wl, cw, eff_nxt, has_agent):
        return False
    return not _is_non_verb_after_id(wl)


def _next_after_opt_ly(tokens: tuple[ClauseToken, ...] | None, idx: int, nxt_low: str) -> str:
    if tokens is not None and _is_ly_adverb(nxt_low) and idx + 2 < len(tokens):
        return tokens[idx + 2].low
    return nxt_low


def _passive_ed_blocked(wl: str, cw: list[str], eff_nxt: str, cw_has_prep: bool) -> bool:
    if not cw or (wl != "bound" and not wl.endswith("ed")) or eff_nxt not in _POSTMOD_PARTICIPLE_NEXT:
        return True
    return _prev_is_np_adv(cw) or wl in _INTRANSITIVE_ED_VERBS


def _is_passive_postmod_ed(
    wl: str, cw: list[str], eff_nxt: str, has_agent: bool | None = None, cw_has_prep: bool = False
) -> bool:
    if _passive_ed_blocked(wl, cw, eff_nxt, cw_has_prep):
        return False
    agent = has_agent if has_agent is not None else _has_agent_subject(cw)
    return not agent


def _is_non_pred_ed_finite(wl: str, cw: list[str], nxt_low: str, eff_nxt: str = "", has_agent: bool | None = None) -> bool:
    if wl not in _NON_PRED_ED or not cw or _prev_is_np_adv(cw):
        return False
    agent = has_agent if has_agent is not None else _has_agent_subject(cw)
    if agent and nxt_low not in {"", ",", "treat", "treats"}:
        return True
    return (eff_nxt or nxt_low) not in _NON_PRED_ED_STOP


def _is_postmod_ing_word(wl: str) -> bool:
    return wl in _POSTMOD_ING or (len(wl) >= 5 and wl.endswith("ing") and wl not in _FINITE_ING_VERBS)


_PRE_NOMINAL_NOUN_MODS = frozenset({
    "polymer", "liposome", "hydrogel", "peptide", "protein", "gold", "silver", "iron", "oxide", "quantum",
    "lipid", "viral", "antisense", "antibody", "nanoparticle", "micelle", "dendrimer",
    "exosome", "nucleic", "dna", "rna", "mrna", "sirna", "crispr",
    "carbon", "electrospun", "collagen", "silica", "silk", "alginate", "chitosan", "graphene", "silica",
    "cellulose", "gelatin", "fibrin", "dextran", "agarose", "metallic", "magnetic", "fluorescent",
    "porous", "mesoporous", "hollow", "crosslinked",
})


def _is_cw_pre_nom_token(raw_w: str) -> bool:
    last = raw_w.lower()
    if last in (_DETS_ONLY | _PRE_NOMINAL_ADJS | _PRE_NOMINAL_NOUN_MODS):
        return True
    if last.endswith(("ed", "ing")) or last.endswith(_PRE_NOMINAL_ADJ_SUFFIXES) or "-" in raw_w:
        return True
    return raw_w != "A" and _is_short_id_token(raw_w)


def _cw_ends_with_pre_nom_mod(cw: list[str]) -> bool:
    return bool(cw) and _is_cw_pre_nom_token(cw[-1])


def _tk_is_coord_finite_verb(tokens: tuple[ClauseToken, ...], j: int, tk: ClauseToken) -> bool:
    if tk.kind != "word":
        return False
    nxt_l = tokens[j + 1].low if j + 1 < len(tokens) else ""
    return _is_s_verb(tk.low) or _is_ed_finite_candidate(tk.low, [tokens[j - 1].raw], nxt_l)


def _scan_np_pp_to_treat_ok(tokens: tuple[ClauseToken, ...], start: int, allow_coord: bool) -> tuple[bool, int]:
    j = start
    while j < len(tokens):
        tk = tokens[j]
        if tk.kind == "treats":
            return tk.low == "treat", j
        if tk.kind in _CLAUSE_BOUNDARY_KINDS or (not allow_coord and tk.kind in {"comma", "comma_coord", "coord"}):
            return False, j
        if allow_coord and _tk_is_coord_finite_verb(tokens, j, tk):
            return False, j
        j += 1
    return False, j


def _sing_subj_before_s_verb(st: dict[str, Any]) -> bool:
    return bool(st["cw_has_subj"] and not st["cw_head_plural"] and not _cw_ends_with_pre_nom_mod(st["cw"]))


def _is_pp_or_ing_lead(tokens: tuple[ClauseToken, ...], idx: int, nxt: str) -> bool:
    if nxt == "to" and tokens[idx + 2].kind == "treats":
        return False
    return nxt in _POSTMOD_PARTICIPLE_NEXT or _is_postmod_ing_word(nxt)


def _plural_np_coord_or_comma_ok(tokens: tuple[ClauseToken, ...], idx: int, st: dict[str, Any], nxt_tok: ClauseToken) -> bool | None:
    if not _cw_ends_with_pre_nom_mod(st["cw"]):
        return None
    if nxt_tok.low in {"and", "or"}:
        return _scan_coord_np_to_treat(st, tokens, idx + 1, allow_singular=False)
    if nxt_tok.kind in {"comma", "comma_coord"}:
        ok, end_j = _scan_comma_list_tokens(tokens, idx + 1)
        if ok:
            st["np_head_ok_until"] = end_j
        return ok
    if _is_ly_adverb(nxt_tok.low):
        ok, end_j = _scan_np_pp_to_treat_ok(tokens, idx + 2, True)
        if ok:
            st["np_head_ok_until"] = end_j
        return ok
    return None


def _is_plural_np_with_pp_before_treat(tokens: tuple[ClauseToken, ...], idx: int, st: dict[str, Any]) -> bool:
    if idx < st["np_head_ok_until"]:
        return True
    if idx + 2 >= len(tokens) or _sing_subj_before_s_verb(st):
        return False
    nxt_tok = tokens[idx + 1]
    pre_res = _plural_np_coord_or_comma_ok(tokens, idx, st, nxt_tok)
    if pre_res is not None:
        return pre_res
    if not _is_pp_or_ing_lead(tokens, idx, nxt_tok.low):
        return False
    ok, end_j = _scan_np_pp_to_treat_ok(tokens, idx + 2, _cw_ends_with_pre_nom_mod(st["cw"]))
    st["np_head_ok_until"] = end_j
    return ok


_TIONS_VERB_NEXT_STOP = frozenset({"treats", "and", "or", ",", "that", "which", "who"})


def _tions_verb_blocked(wl: str, cw: list[str], nxt_low: str) -> bool:
    if not wl.endswith(("tions", "sions")):
        return False
    if not cw:
        return True
    prev = cw[-1].lower()
    if prev in (_DETS_ONLY | _PRE_NOMINAL_ADJS) or prev.endswith(_ADJ_COMMA_SUFFIXES):
        return True
    return nxt_low in _TIONS_VERB_NEXT_STOP


_STRICT_PRE_NOM_MODS = (_DETS_ONLY - _DEMONSTRATIVES) | _PRE_NOMINAL_ADJS | _NON_PRED_ED


def _cw_is_strict_pre_nom_only(cw: list[str]) -> bool:
    return bool(cw) and all(
        w.lower() in _STRICT_PRE_NOM_MODS or w.lower().endswith(("ed", "ing", "ly", "ous", "ive", "al", "ic"))
        for w in cw
    )


def _is_s_clause_verb(
    wl: str, cw: list[str], nxt_low: str, in_rel: bool, tokens: tuple[ClauseToken, ...] | None, idx: int, st: dict[str, Any] | None
) -> bool:
    if nxt_low == "treat" or _tions_verb_blocked(wl, cw, nxt_low) or _cw_is_strict_pre_nom_only(cw):
        return False
    if wl in _DUAL_NOUN_VERB_S:
        return _is_dual_verb_s(wl, cw, nxt_low, in_rel, tokens, idx, st)
    if tokens is not None and st is not None and not st["p"]:
        return not _is_plural_np_with_pp_before_treat(tokens, idx, st)
    return True


def _is_plural_head_verb(wl: str, cw: list[str]) -> bool:
    if len(cw) >= 2:
        return True
    h = cw[0].lower()
    return h in _PLURAL_HEADS or (h.endswith("s") and h not in {"this", "his", "its", "as", "us"})


def _is_subj_noun_word(raw: str, low: str) -> bool:
    if low in _PRONOUN_SUBJ or raw == "A" or _is_short_id_token(raw):
        return True
    if low in _NON_SUBJ_WORDS or "-" in low:
        return False
    return not low.endswith(("ly", "ed", "ing", "al", "ic", "ous", "ive"))


def _is_ed_finite_candidate(
    wl: str, cw: list[str], eff_nxt: str, has_agent: bool | None = None, cw_has_prep: bool = False
) -> bool:
    return _is_ed_verb(wl) and not _prev_is_np_adv(cw) and not _is_passive_postmod_ed(wl, cw, eff_nxt, has_agent, cw_has_prep)


def _is_subject_verb_candidate(
    raw_word: str,
    wl: str,
    cw: list[str],
    nxt_low: str,
    has_prep: bool,
    has_subj: bool,
    head_plural: bool = False,
    eff_nxt: str = "",
    has_agent: bool | None = None,
) -> bool:
    if has_subj and _is_ed_finite_candidate(wl, cw, eff_nxt, has_agent, has_prep):
        return True
    if has_subj and _is_non_pred_ed_finite(wl, cw, nxt_low, eff_nxt, has_agent):
        return True
    if wl in _PLURAL_BASE_VERBS and _is_plural_head_verb(wl, cw):
        return True
    return _plural_noun_takes_verb(cw, wl, has_prep, head_plural, nxt_low) or _id_followed_by_verb(cw, raw_word, wl, has_prep, eff_nxt, has_agent)


def _is_passive_cut_noun(wl: str, cw: list[str], eff_nxt: str) -> bool:
    if wl != "cut" or not cw or eff_nxt not in _CLAUSE_PREPS:
        return False
    return any(w.lower() in _DETS_ONLY for w in cw[-2:])


def _is_passive_bound_mod(wl: str, cw: list[str], eff_nxt: str, has_agent: bool | None = None) -> bool:
    if _is_passive_cut_noun(wl, cw, eff_nxt):
        return True
    if wl != "bound" or not cw or eff_nxt not in _POSTMOD_PARTICIPLE_NEXT:
        return False
    agent = has_agent if has_agent is not None else _has_agent_subject(cw)
    return not agent


def _finite_subj_flags(
    cw: list[str], st: dict[str, Any] | None, cw_has_prep: bool | None
) -> tuple[bool, bool, bool]:
    if st is not None:
        return (st["cw_has_prep"] if cw_has_prep is None else cw_has_prep), st["cw_has_subj"], st["cw_head_plural"]
    return bool(cw_has_prep), any(_is_subj_noun_word(w, w.lower()) for w in cw), False


def _is_finite_verb(
    raw_word: str,
    cw: list[str],
    nxt_low: str = "",
    in_rel: bool = False,
    tokens: tuple[ClauseToken, ...] | None = None,
    idx: int = -1,
    st: dict[str, Any] | None = None,
    cw_has_prep: bool | None = None,
) -> bool:
    """Identify finite predicates via O(1) morphological and local context checks."""
    wl = raw_word.lower()
    if _prev_blocks_verb(cw, wl):
        return False
    eff_nxt = _next_after_opt_ly(tokens, idx, nxt_low)
    has_agent = st["cw_has_agent"] if st is not None else None
    if wl in _AUX_OR_IRREG_VERBS:
        return not _is_passive_bound_mod(wl, cw, eff_nxt, has_agent)
    if not cw:
        return False
    if _is_s_verb(wl):
        return _is_s_clause_verb(wl, cw, nxt_low, in_rel, tokens, idx, st)
    has_prep, has_subj, head_plural = _finite_subj_flags(cw, st, cw_has_prep)
    return _is_subject_verb_candidate(raw_word, wl, cw, nxt_low, has_prep, has_subj, head_plural, eff_nxt, has_agent)


def _step_pp_tok(st_pp: list[Any], wl: str, tok_idx: int) -> bool:
    if st_pp[1] == 0 and st_pp[2] == "in" and wl in _IN_FIXED_WORDS:
        st_pp[0], st_pp[1], st_pp[3] = False, 0, tok_idx + 1
        return True
    if wl in _ADV_PREPS:
        if st_pp[1] == 0:
            return False
        st_pp[1], st_pp[2] = 0, wl
        return True
    if wl in _PP_STOP_WORDS:
        if st_pp[1] > 0 and wl in {"and", "or"}:
            st_pp[0], st_pp[1], st_pp[3] = False, 0, tok_idx + 1
            return True
        return False
    st_pp[1] += 1
    st_pp[3] = tok_idx + 1
    return True


def _step_adv_comma_or_paren(st_pp: list[Any], tok: ClauseToken, tok_idx: int) -> bool:
    if tok.kind == "comma":
        if st_pp[0] and st_pp[1] == 0:
            return False
        st_pp[0], st_pp[1], st_pp[3] = False, 0, tok_idx + 1
        return True
    if not st_pp[0] and tok.kind == "paren_open":
        parts = tok.low.lstrip(", ").split()
        if parts and parts[0] == "in":
            st_pp[3] = tok_idx + 1
            return True
    return False


def _step_adv_tok(st_pp: list[Any], tok: ClauseToken, tok_idx: int) -> bool:
    if tok.kind in {"comma", "paren_open"}:
        return _step_adv_comma_or_paren(st_pp, tok, tok_idx)
    if tok.kind == "adv_break" and not st_pp[0]:
        st_pp[3] = tok_idx + 1
        return True
    if tok.kind not in {"word", "coord"}:
        return False
    wl = tok.low
    if st_pp[0]:
        return _step_pp_tok(st_pp, wl, tok_idx)
    if _is_adv_link(wl):
        st_pp[3] = tok_idx + 1
        return True
    if wl in _ADV_PREPS:
        st_pp[0], st_pp[1], st_pp[2] = True, 0, wl
        return True
    return False


def _scan_adverbial_tokens(tokens: tuple[ClauseToken, ...], start: int) -> int:
    st_pp: list[Any] = [False, 0, "", start]
    for j in range(start, len(tokens)):
        if not _step_adv_tok(st_pp, tokens[j], j):
            break
    return int(st_pp[3])


def _coord_adv_word_ok(w1: str, w2: str, adv_end: int) -> tuple[bool, int, bool]:
    if w1 in _AUX_VERBS:
        return (w2 not in _PRONOUN_SUBJ), adv_end, False
    if w1 in _REPORTING_STEMS or w2 in {"treat", "treats"}:
        return False, 0, False
    if _is_s_verb(w1) and w1 not in _DUAL_NOUN_VERB_S:
        return True, adv_end, True
    return False, 0, False


def _coord_allows_after_adv(tokens: tuple[ClauseToken, ...], start: int) -> tuple[bool, int, bool]:
    adv_end = _scan_adverbial_tokens(tokens, start)
    if adv_end >= len(tokens):
        return False, 0, False
    t1 = tokens[adv_end]
    if t1.kind == "treats":
        return True, adv_end, False
    if t1.kind != "word":
        return False, 0, False
    w2 = tokens[adv_end + 1].low if adv_end + 1 < len(tokens) else ""
    return _coord_adv_word_ok(t1.low, w2, adv_end)


_TAIL_GUARD_WORDS = {
    "whether_or_not": _CONCESSIVE_TAIL_WORDS,
    "inquiry_if": _ELLIPTIC_IF_WORDS,
}


def _post_coord_direct_match(tokens: tuple[ClauseToken, ...], pos: int, st: dict[str, Any] | None) -> bool | None:
    if pos >= len(tokens):
        return False
    tok = tokens[pos]
    if tok.kind == "treats":
        return tok.low != "treat" or st is None or not st["coord_s_verb"]
    if tok.kind == "whether":
        return True
    if tok.kind in _TAIL_GUARD_WORDS:
        nxt = tokens[pos + 1].low if pos + 1 < len(tokens) else ""
        return nxt not in _TAIL_GUARD_WORDS[tok.kind]
    if tok.kind in {"only_that_noun", "gerund_that_noun"}:
        return tok.low.split()[-1] not in _PRONOUN_SUBJ
    return None


def _post_coord_allows_treats(tokens: tuple[ClauseToken, ...], pos: int, st: dict[str, Any] | None = None) -> bool:
    if st is not None and pos < st["adv_ok_until"]:
        return True
    direct = _post_coord_direct_match(tokens, pos, st)
    if direct is not None:
        if direct and st is not None:
            st["coord_s_verb"] = False
        return direct
    ok, adv_end, is_s_coord = _coord_allows_after_adv(tokens, pos)
    if ok and st is not None:
        st["adv_ok_until"] = max(st["adv_ok_until"], adv_end)
        st["coord_s_verb"] = is_s_coord
    return ok


def _is_rel_pronoun_that(cw: list[str], prev: str) -> bool:
    if prev in _REPORTING_STEMS or prev in _COMPLEMENT_NOUNS or prev in _PRONOUN_SUBJ:
        return False
    if prev in {"only", "and", "or", "but", "plus", "nor", ","}:
        return False
    return cw[-1] == "A" or prev not in _STRICT_DET_AND_PREP


def _is_coord_det_that(cw: list[str], prev: str) -> bool:
    if prev in _DETERMINERS_AND_PREPS:
        return True
    return len(cw) >= 2 and prev in {"and", "or", "nor"} and cw[-2] != "A" and cw[-2].lower() in _DETERMINERS_AND_PREPS


def _handle_that_token(st: dict[str, Any]) -> None:
    if not st["h"] or st["in_paren"]:
        return
    st["after_coord"] = False
    cw = st["cw"]
    if not cw:
        return
    prev = cw[-1].lower()
    if st["p"] or prev in _REPORTING_STEMS:
        st.update(_reset_clause_state(st["s"]))
    elif _is_rel_pronoun_that(cw, prev) or _is_coord_det_that(cw, prev):
        if _is_rel_pronoun_that(cw, prev):
            st["in_rel"] = True
            st["had_rel"] = True
        cw.append("that")
    else:
        st.update(_reset_clause_state(st["s"]))


def _rel_clause_closes(raw_word: str, cw: list[str], nxt_low: str) -> bool:
    wl = raw_word.lower()
    if cw and cw[-1].lower() in _REL_PRONOUNS:
        if bool(_MORPH_ED_VERB_RE.match(wl)) or wl in _IRREGULAR_PAST_VERBS or wl in _PLURAL_BASE_VERBS:
            return True
    return _is_finite_verb(raw_word, cw, nxt_low, in_rel=True)


def _record_post_p_word(st: dict[str, Any], tok: ClauseToken) -> None:
    st["post_p"].append(tok.raw)
    if tok.low not in _AUX_VERBS and not tok.low.endswith("ly"):
        st["post_p_has_content"] = True


def _advance_post_p_verb(st: dict[str, Any], wl: str) -> bool:
    if not st["p"]:
        if not st["r"]:
            st["p"] = True
            st["p_is_modal"] = wl in _MODAL_AUX_VERBS
            st["p_is_copula"] = wl in _COPULA_OR_CONTROL_VERBS
        return True
    if st["post_p_has_content"]:
        st.update(_reset_clause_state(st["s"]))
        return False
    st["post_p"].clear()
    st["post_p_has_content"] = False
    return True


def _advance_word_in_clause(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, tok: ClauseToken) -> bool:
    cw = st["cw"]
    nxt_low = tokens[idx + 1].low if idx + 1 < len(tokens) else ""
    if not st["p"] and len(cw) >= 2 and tok.low in _REL_PRONOUNS and cw[-1].lower() not in {"and", "or", "but"}:
        st["in_rel"] = True
        st["had_rel"] = True
        return True
    if _is_finite_verb(tok.raw, cw, nxt_low, False, tokens, idx, st):
        return _advance_post_p_verb(st, tok.low)
    if st["p"]:
        _record_post_p_word(st, tok)
    return True


def _coord_s_verb_breaks(st: dict[str, Any], wl: str) -> bool:
    if not st["coord_s_verb"]:
        return False
    return wl in _PLURAL_AUX_OR_MODAL or (wl in _PLURAL_BASE_VERBS and not st["post_p"])


def _is_plural_noun_token(low: str) -> bool:
    if low in _PLURAL_HEADS:
        return True
    if len(low) < 4 or not low.endswith("s") or low in _NON_NOUN_S or low in _NON_PLURAL_LATIN_GREEK or low.endswith("ss"):
        return False
    return not low.endswith(("ous", "ics", "sis", "xis", "tis", "ness", "less", "sus", "tus", "rus", "lus", "cus", "mus", "nus", "pus"))


def _sets_cw_head_plural(st: dict[str, Any], tok: ClauseToken) -> bool:
    if st["cw_has_prep"] or st["p"] or st["in_rel"] or st["had_rel"]:
        return False
    if not _is_plural_noun_token(tok.low):
        return False
    if len(st["cw"]) <= 1 or not _is_s_verb(tok.low):
        return True
    return _is_cw_pre_nom_token(st["cw"][-2])


def _is_collective_of_cw(cw: list[str]) -> bool:
    if len(cw) >= 3 and cw[-2].lower() == "of" and cw[-3].lower() in _COLLECTIVE_AGENT_HEADS:
        return True
    return len(cw) >= 4 and cw[-3].lower() == "of" and cw[-4].lower() in _COLLECTIVE_AGENT_HEADS


def _is_main_agent_tok(st: dict[str, Any], low: str) -> bool:
    if st["cw_has_agent"] or st["in_rel"]:
        return False
    if st["cw_has_prep"] and not _is_collective_of_cw(st["cw"]):
        return False
    if st["had_rel"] and not st["cw_scan_from"]:
        return False
    return _is_agent_subject(low)


def _update_cw_subj_flags(st: dict[str, Any], tok: ClauseToken) -> None:
    if _is_main_agent_tok(st, tok.low):
        st["cw_has_agent"] = True
    if not st["cw_has_to_pp"] and tok.low in _POSTMOD_PARTICIPLE_NEXT:
        st["cw_has_to_pp"] = True
    if not st["cw_has_subj"] and _is_subj_noun_word(tok.raw, tok.low):
        st["cw_has_subj"] = True


def _is_adj_word(raw: str, low: str) -> bool:
    return low in _PRE_NOMINAL_ADJS or low.endswith(_ADJ_COMMA_SUFFIXES) or "-" in raw or _is_ly_adverb(low)


def _append_cw_word(st: dict[str, Any], tok: ClauseToken) -> None:
    st["cw"].append(tok.raw)
    if st["cw_all_adj"] and not _is_adj_word(tok.raw, tok.low):
        st["cw_all_adj"] = False
    if tok.low in _CLAUSE_PREPS:
        st["cw_has_prep"] = True
    elif tok.low == "not":
        st["cw_has_not"] = True
    if _sets_cw_head_plural(st, tok):
        st["cw_head_plural"] = True
    if _is_ly_adverb(tok.low):
        st["cw_has_adv"] = True
    _update_cw_subj_flags(st, tok)


def _word_token_skipped(st: dict[str, Any], idx: int) -> bool:
    if not st["h"] or st["in_paren"]:
        return True
    return idx < max(st["appos_ok_until"], st["adv_comma_until"], st["adv_ok_until"])


def _handle_word_token(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, tok: ClauseToken) -> None:
    if _word_token_skipped(st, idx):
        return
    st["after_coord"] = False
    cw = st["cw"]
    nxt_low = tokens[idx + 1].low if idx + 1 < len(tokens) else ""
    if st["in_rel"]:
        if _rel_clause_closes(tok.raw, cw, nxt_low):
            st["in_rel"] = False
    elif _coord_s_verb_breaks(st, tok.low):
        st.update(_reset_clause_state(st["s"]))
        return
    elif not _advance_word_in_clause(st, tokens, idx, tok):
        return
    _append_cw_word(st, tok)


def _consume_pp_end(tokens: list[str], start: int) -> int:
    n = len(tokens)
    j = start + 1
    while j < n and tokens[j] not in _ADV_PREPS and tokens[j] not in _PP_STOP_WORDS:
        j += 1
    return j if j > start + 1 else -1


def _is_adverbial_token_list(tokens: list[str]) -> bool:
    i, n = 0, len(tokens)
    while i < n:
        w = tokens[i]
        if _is_adv_link(w):
            i += 1
        elif w == "in" and i + 1 < n and tokens[i + 1] in _IN_FIXED_WORDS:
            i += 2
        elif w in _ADV_PREPS:
            i = _consume_pp_end(tokens, i)
            if i < 0:
                return False
        else:
            return False
    return True


def _post_p_allows_to_treat(post: list[str]) -> bool:
    if "for" in post:
        return False
    i, n = 0, len(post) - 1
    while i < n:
        w = post[i]
        if w in _SUBJECT_CONTROL_WORDS or _is_adv_link(w):
            i += 1
        elif w == "in" and i + 1 < n and post[i + 1] in _IN_FIXED_WORDS:
            i += 2
        else:
            return False
    return True


def _post_p_allows_treats(post_p: list[str], raw_word: str) -> bool:
    post = [w.lower() for w in post_p]
    if raw_word.lower() == "treat" and post[-1] == "to":
        return _post_p_allows_to_treat(post)
    return _is_adverbial_token_list(post)


def _p_state_allows_treat(st: dict[str, Any], tr_low: str) -> bool:
    if tr_low != "treat":
        return False
    post = [w.lower() for w in st["post_p"]]
    if post and post[-1] == "to":
        return bool(st["p_is_copula"]) and _post_p_allows_to_treat(post)
    return bool(st["p_is_modal"]) and (not post or _is_adverbial_token_list(post))


def _st_has_agent_subject(st: dict[str, Any]) -> bool:
    if st["cw_has_agent"]:
        return True
    if st["in_rel"] or not st["cw_scan_from"]:
        return False
    return _has_agent_subject(st["cw"][st["cw_scan_from"] :])


def _treat_blocked_by_agent_or_coord(st: dict[str, Any], tr_low: str) -> bool:
    if tr_low in {"treat", "treats"} and _st_has_agent_subject(st):
        return True
    if tr_low != "treat":
        return False
    return bool(st["coord_s_verb"] and not (st["post_p"] and st["post_p"][-1].lower() == "to"))


def _treats_blocked_by_state(st: dict[str, Any], raw_word: str) -> bool:
    if not st["h"] or st["in_paren"]:
        return True
    tr_low = raw_word.lower()
    if _treat_blocked_by_agent_or_coord(st, tr_low):
        return True
    return bool(st["p"] and not _p_state_allows_treat(st, tr_low))


def _handle_treats_token(st: dict[str, Any], raw_word: str) -> bool:
    if _treats_blocked_by_state(st, raw_word):
        return True
    st["p"] = True
    st["p_is_modal"] = False
    st["p_is_copula"] = False
    st["r"] = False
    st["lp"] = False
    st["coord_s_verb"] = False
    st["after_coord"] = False
    st["post_p"].clear()
    st["post_p_has_content"] = False
    st["cw"].append(raw_word)
    return False


def _tok_is_treats_or_conj(tok: ClauseToken) -> bool:
    if tok.kind == "treats":
        return True
    return tok.kind in {"comma_coord", "coord"} and tok.low.split()[-1] in {"and", "or"}


def _is_modal_inf_continuation(st: dict[str, Any], nxt: ClauseToken) -> bool:
    return bool(st["p"] and not st["post_p_has_content"] and _has_verb_stem_shape(nxt.low))


def _is_post_appos_ing(st: dict[str, Any], nxt: ClauseToken) -> bool:
    return not st["p"] and bool(st["cw"]) and _is_postmod_ing_word(nxt.low)


def _paren_next_word_ok(st: dict[str, Any], tokens: tuple[ClauseToken, ...], adv_end: int) -> bool:
    nxt = tokens[adv_end]
    if nxt.kind != "word":
        return False
    if _is_modal_inf_continuation(st, nxt) or _is_post_appos_ing(st, nxt):
        return True
    nxt2 = tokens[adv_end + 1].low if adv_end + 1 < len(tokens) else ""
    return _is_finite_verb(nxt.raw, st["cw"] or ["x"], nxt2)


def _paren_or_rel_allows_next(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if idx + 1 >= len(tokens) or _tok_is_treats_or_conj(tokens[idx + 1]):
        return True
    adv_end = _scan_adverbial_tokens(tokens, idx + 1)
    if adv_end >= len(tokens) or _tok_is_treats_or_conj(tokens[adv_end]):
        return True
    return _paren_next_word_ok(st, tokens, adv_end)


def _handle_paren_close_comma(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    st["in_paren"] = False
    if idx + 1 >= len(tokens):
        return
    nxt = tokens[idx + 1]
    if nxt.kind == "coord" and nxt.low in {"and", "or"}:
        _on_coord_step(st, tokens, idx + 1, nxt.low)
        return
    if _try_comma_appositive(st, tokens, idx) or _paren_or_rel_allows_next(st, tokens, idx):
        st["r"] = False
        st["lp"] = False
        return
    if not st["lp"] or st["p"] or st["r"]:
        st.update(_reset_clause_state(st["s"]))


def _rel_paren_next_ok(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if _paren_or_rel_allows_next(st, tokens, idx):
        return True
    if idx + 1 < len(tokens) and tokens[idx + 1].kind == "comma":
        return _appos_close_idx(tokens, idx + 1) > idx + 1
    return False


def _on_rel_paren(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    if not st["h"] or st["in_paren"]:
        return
    if not st["cw"] or st["p"] or st["r"] or not _rel_paren_next_ok(st, tokens, idx):
        st.update(_reset_clause_state(st["s"]))
    else:
        st["had_rel"] = True


def _seg_word_is_passive_mod(wl: str, seg_words: list[str], k: int, nxt_low: str, has_prep: bool = False) -> bool:
    eff = seg_words[k + 2].lower() if k + 2 < len(seg_words) and _is_ly_adverb(nxt_low) else nxt_low
    if wl == "bound" and eff in _POSTMOD_PARTICIPLE_NEXT:
        return True
    return (wl in _NON_PRED_ED and eff in _POSTMOD_PARTICIPLE_NEXT) or (
        _is_ed_verb(wl) and _is_passive_postmod_ed(wl, seg_words[:k], eff, cw_has_prep=has_prep)
    )


def _seg_is_pre_nom_plural_noun(seg_words: list[str], k: int, wl: str, nxt_low: str) -> bool:
    if k == 0 or not _is_s_verb(wl) or not _is_cw_pre_nom_token(seg_words[k - 1]):
        return False
    return k == len(seg_words) - 1 or nxt_low in _POSTMOD_PARTICIPLE_NEXT or _is_postmod_ing_word(nxt_low)


def _seg_k_is_finite(seg_words: list[str], k: int, has_prep: bool, cw_head_plural: bool, implicit_subj: bool) -> bool:
    w = seg_words[k]
    wl = w.lower()
    nxt_low = seg_words[k + 1].lower() if k + 1 < len(seg_words) else ""
    if _seg_word_is_passive_mod(wl, seg_words, k, nxt_low, has_prep=has_prep) or _seg_is_pre_nom_plural_noun(seg_words, k, wl, nxt_low):
        return False
    cw_ctx = seg_words[max(0, k - 2) : k] or (["compound"] if implicit_subj else [])
    if _is_finite_verb(w, cw_ctx, nxt_low, cw_has_prep=has_prep):
        return True
    return cw_head_plural and _plural_noun_takes_verb(seg_words[:k], w, has_prep, True, nxt_low)


def _seg_has_finite_verb(seg_words: list[str], cw_head_plural: bool = False, implicit_subj: bool = False) -> bool:
    has_prep = False
    for k, w in enumerate(seg_words):
        if _seg_k_is_finite(seg_words, k, has_prep, cw_head_plural, implicit_subj):
            return True
        if w.lower() in _CLAUSE_PREPS:
            has_prep = True
    return False


def _is_list_conj(tk: ClauseToken) -> bool:
    return tk.kind == "comma_coord" or (tk.kind == "coord" and tk.low in {"and", "or"})


_KNOWN_PASSIVE_PARTICIPLES = _NON_PRED_ED | frozenset({"bound", "shown", "known", "seen", "found", "made", "given"})
_STRICT_NOUN_SUFFIXES = (
    "tion", "sion", "ment", "ness", "ity", "ance", "ence", "ism", "ogy", "sis", "ics",
    "apy", "cin", "nib", "mab", "vir", "stat", "ide", "itor", "ator", "izer", "iser",
    "ome", "cyte", "blast", "phile", "phage", "zyme", "kin", "toxin",
)
_PRE_NOMINAL_ADJ_SUFFIXES = ("al", "ic", "ous", "ive", "ary", "ory", "ant", "ent", "able", "ible", "less", "ful", "like")
_PP_POST_ID_NOUNS = frozenset({
    "um", "nm", "mm", "ug", "mg", "kg", "ml", "l", "h", "hr", "hrs", "min", "sec", "day", "days", "week", "weeks",
    "cells", "lines", "models", "assays", "tumors", "tumours", "gliomas", "cancers", "mice", "rats", "patients",
    "inhibitors", "agonists", "antagonists", "targets", "pathways", "compounds", "drugs", "agents", "molecules",
    "vesicles", "liposomes", "nanoparticles", "conjugates", "derivatives", "organoids", "spheroids", "xenografts",
    "samples", "controls", "groups", "cohorts",
})
_APPOS_ROUTE_WORDS = frozenset({
    "oral", "orally", "iv", "po", "sc", "ip", "im", "icv", "intrathecal", "intrathecally",
    "intravenous", "intravenously", "subcutaneous", "subcutaneously", "intratumoral", "intratumorally",
    "daily", "bid", "qd", "vehicle", "control", "saline", "dmso", "pbs", "only",
})
_APPOS_DETS = frozenset({"a", "an", "the", "our", "my", "its", "their", "this", "that"})
_PURE_NP_PREPS = _POSTMOD_PARTICIPLE_NEXT


def _is_sing_nominal(low: str) -> bool:
    return low in _SINGULAR_NOUNS_NON_VERB or low.endswith(_STRICT_NOUN_SUFFIXES)


def _is_nominal_head_word(raw: str, low: str) -> bool:
    if _is_short_id_token(raw) or raw.isdigit() or _is_sing_nominal(low):
        return True
    return low in _PLURAL_HEADS or _is_plural_noun_token(low)


_NON_ADJ_IVE_WORDS = frozenset({
    "give", "forgive", "live", "outlive", "drive", "strive", "thrive", "derive", "survive",
    "revive", "receive", "perceive", "conceive", "deceive", "achieve", "relieve", "believe",
    "grieve", "retrieve", "arrive", "deprive", "contrive", "dive", "five",
})
_NON_ADJ_ANT_ENT_VERBS = frozenset({
    "implant", "supplement", "augment", "transplant", "present", "prevent", "consent",
    "dissent", "invent", "comment", "fragment", "segment", "ferment", "document",
    "grant", "plant", "chant", "want", "rant", "slant",
})


def _is_pre_nominal_mod(raw: str, low: str, nxt_low: str = "") -> bool:
    if low in _PRE_NOMINAL_ADJS or "-" in low:
        return True
    if low.endswith(_PRE_NOMINAL_ADJ_SUFFIXES) and low not in _NON_ADJ_IVE_WORDS and low not in _NON_ADJ_ANT_ENT_VERBS:
        return True
    return (low.endswith("ed") or _is_postmod_ing_word(low)) and bool(nxt_low) and nxt_low not in _DETS_ONLY


def _is_non_verb_plural(l1: str) -> bool:
    return _is_plural_noun_token(l1) and (l1 in _NON_VERB_S or l1.endswith(_NON_VERB_S_SUFFIXES))


_CONTROL_PAIR_PRE = frozenset({"vehicle", "dmso", "pbs", "saline", "positive", "negative"})
_CONTROL_PAIR_HEAD = frozenset({"control", "controls", "group", "arm"})


def _is_control_pair(r0: str, l1: str) -> bool:
    return r0.lower() in _CONTROL_PAIR_PRE and l1 in _CONTROL_PAIR_HEAD


def _is_pure_pre_pp_pair(r0: str, r1: str) -> bool:
    l1 = r1.lower()
    if l1.endswith("ed") or _is_ly_adverb(l1):
        return False
    if _is_short_id_token(r0):
        return l1 in {"only", "alone", "both", "vs"} or _is_sing_nominal(l1)
    return _is_control_pair(r0, l1) or _is_short_id_token(r1) or r1.isdigit() or _is_sing_nominal(l1) or _is_non_verb_plural(l1)


_STRICT_DETS_ONLY = _DETS_ONLY - _DEMONSTRATIVES


def _is_single_pre_pp_word(wl: str) -> bool:
    if wl in (_BARE_PRONOUN_SUBJ | _STRICT_DETS_ONLY) or _is_ly_adverb(wl):
        return False
    return not (wl.endswith("ed") and wl not in _KNOWN_PASSIVE_PARTICIPLES)


def _is_pure_pre_pp_core(rem: list[str]) -> bool:
    if not rem:
        return True
    if len(rem) == 1:
        return _is_single_pre_pp_word(rem[0].lower())
    if len(rem) == 2:
        return _is_pure_pre_pp_pair(rem[0], rem[1])
    return len(rem) == 3 and _is_short_id_token(rem[2]) and _is_sing_nominal(rem[1].lower()) and rem[1].lower() not in _TRANSITIVE_NOUN_VERBS


def _is_pre_participle_adv(wl: str, nxt: str) -> bool:
    if _is_ly_adverb(wl):
        return True
    return wl in _PRE_PARTICIPLE_ADVS and (nxt.endswith(("ed", "ing")) or nxt in _KNOWN_PASSIVE_PARTICIPLES)


def _can_skip_single_pre_pp_mod(raw_w: str, wl: str, nxt: str) -> bool:
    if _is_pre_nominal_mod(raw_w, wl, nxt):
        return True
    if wl in _PRE_NOMINAL_NOUN_MODS and (nxt in _PRE_NOMINAL_NOUN_MODS or _is_plural_noun_token(nxt)):
        return True
    return _is_plural_noun_token(nxt) and _is_cw_pre_nom_token(raw_w)


def _skip_pre_pp_mods(pre_pp: list[str], start: int) -> int:
    idx, n = start, len(pre_pp)
    while idx < n - 1:
        wl, nxt = pre_pp[idx].lower(), pre_pp[idx + 1].lower()
        nxt2 = pre_pp[idx + 2].lower() if idx + 2 < n else ""
        if _is_pre_participle_adv(wl, nxt) and _is_pre_nominal_mod(pre_pp[idx + 1], nxt, nxt2):
            idx += 2
        elif _can_skip_single_pre_pp_mod(pre_pp[idx], wl, nxt):
            idx += 1
        else:
            break
    return idx


_PURE_ADJ_NON_VERB = _PRE_NOMINAL_ADJS - {"free", "triple", "both", "neither", "either"}


def _can_skip_det_noun_mod(pre_pp: list[str], idx: int) -> bool:
    if idx != 1 or len(pre_pp) < 4:
        return False
    w0 = pre_pp[0].lower()
    w1, w2 = pre_pp[1].lower(), pre_pp[2].lower()
    if w0 not in _DETS_ONLY or w2 not in _PURE_ADJ_NON_VERB:
        return False
    if _is_plural_noun_token(w1) or _is_agent_subject(w1) or w1 in (_PLURAL_HEADS | _AUX_OR_IRREG_VERBS):
        return False
    return not _is_ed_verb(w1) and not w1.endswith("s")


def _is_repeated_both_np(pre_pp: list[str]) -> bool:
    if len(pre_pp) < 6 or len(pre_pp) % 3 != 0 or pre_pp[0].lower() != "both":
        return False
    return all(
        pre_pp[k].lower() == "both" and _is_pure_pre_pp_pair(pre_pp[k + 1], pre_pp[k + 2])
        for k in range(0, len(pre_pp), 3)
    )


def _is_pure_pre_pp(pre_pp: list[str]) -> bool:
    if not pre_pp or pre_pp[0].lower() in _BARE_PRONOUN_SUBJ:
        return False
    if len(pre_pp) == 1:
        return not _is_ly_adverb(pre_pp[0].lower())
    if any(w != "A" and w.lower() in (_DETS_ONLY | _BARE_PRONOUN_SUBJ) for w in pre_pp[1:]):
        return False
    idx = _skip_pre_pp_mods(pre_pp, 1 if pre_pp[0].lower() in _DETS_ONLY else 0)
    if _can_skip_det_noun_mod(pre_pp, idx):
        idx = _skip_pre_pp_mods(pre_pp, idx + 1)
    return _is_pure_pre_pp_core(pre_pp[idx:])


def _is_pure_pp_core_pair(core: list[str], pre_pl: bool) -> bool:
    if _is_short_id_token(core[0]):
        return core[1].lower() in _PP_POST_ID_NOUNS
    if _is_plural_noun_token(core[0].lower()) or core[0].lower() in _PLURAL_HEADS:
        return False
    return _is_nominal_head_word(core[1], core[1].lower()) or core[1].lower() in _PP_POST_ID_NOUNS


def _is_pure_pp_trio(core: list[str], has_det: bool) -> bool:
    if has_det or _is_short_id_token(core[0]) or _is_plural_noun_token(core[0].lower()):
        return False
    ok_lead = core[0][0].isdigit() or _is_pre_nominal_mod(core[0], core[0].lower(), core[1].lower())
    return ok_lead and _is_nominal_head_word(core[2], core[2].lower())


def _is_pure_pp_obj(pp_obj: list[str], pre_pl: bool) -> bool:
    if not pp_obj or pp_obj[0].lower() in _BARE_PRONOUN_SUBJ:
        return False
    has_det = pp_obj[0].lower() in _DETS_ONLY and pp_obj[0] != "A"
    core = pp_obj[1:] if has_det else pp_obj
    if not core or len(core) > 3:
        return False
    if len(core) == 1:
        return not _is_ly_adverb(core[0].lower())
    return _is_pure_pp_core_pair(core, pre_pl) if len(core) == 2 else _is_pure_pp_trio(core, has_det)


def _skip_participle_prep(post_pp: list[str], j: int, is_ing: bool) -> int:
    n = len(post_pp)
    if j < n and _is_ly_adverb(post_pp[j].lower()):
        j += 1
    if j < n and post_pp[j].lower() in _PURE_NP_PREPS:
        return j + 1
    return j if is_ing else -1


def _consume_pp_prefix(post_pp: list[str], j: int, pre_pl: bool) -> int:
    wl = post_pp[j].lower()
    if wl in _PURE_NP_PREPS:
        return j + 1
    is_ing = _is_postmod_ing_word(wl)
    if is_ing:
        return _skip_participle_prep(post_pp, j + 1, True)
    if pre_pl or wl not in _KNOWN_PASSIVE_PARTICIPLES:
        return -1
    return _skip_participle_prep(post_pp, j + 1, False)


def _is_pure_post_pp(post_pp: list[str], pre_pl: bool) -> bool:
    j, n = 0, len(post_pp)
    while j < n:
        j = _consume_pp_prefix(post_pp, j, pre_pl)
        if j < 0:
            return False
        start = j
        while j < n and post_pp[j].lower() not in _PURE_NP_PREPS and not _is_postmod_ing_word(post_pp[j].lower()):
            j += 1
        if not _is_pure_pp_obj(post_pp[start:j], pre_pl):
            return False
    return True


def _eff_word_after_opt_ly(clean: list[str], k: int) -> str:
    nxt = clean[k + 1].lower() if k + 1 < len(clean) else ""
    return clean[k + 2].lower() if k + 2 < len(clean) and _is_ly_adverb(nxt) else nxt


def _np_participle_splits_at(clean: list[str], k: int, allow_passive_pp: bool) -> tuple[bool, bool]:
    wl = clean[k].lower()
    is_ing = _is_postmod_ing_word(wl)
    if not (is_ing or wl == "bound" or wl.endswith("ed")):
        return False, False
    if _eff_word_after_opt_ly(clean, k) in _PURE_NP_PREPS:
        return True, is_ing or (allow_passive_pp and wl in _KNOWN_PASSIVE_PARTICIPLES)
    return is_ing, True


def _split_np_pp(clean: list[str], allow_passive_pp: bool) -> tuple[list[str], list[str]] | None:
    if len(clean) > 1 and clean[0].lower() in {"both", "neither", "either"}:
        clean = clean[1:]
    for k, w in enumerate(clean):
        if w.lower() in _PURE_NP_PREPS:
            return clean[:k], clean[k:]
        if k >= 1:
            is_split, ok = _np_participle_splits_at(clean, k, allow_passive_pp)
            if is_split:
                return (clean[:k], clean[k:]) if ok else None
    return clean, []


def _pre_pp_is_plural_or_agent(pre_pp: list[str]) -> bool:
    last_low = pre_pp[-1].lower()
    return _has_agent_subject(pre_pp) or last_low in _PLURAL_HEADS or _is_plural_noun_token(last_low)


def _seg_is_pure_np(seg_words: list[str], *, allow_passive_pp: bool = True) -> bool:
    clean = [w for w in seg_words if w != ","]
    if not clean or _seg_has_finite_verb(clean):
        return False
    if _is_repeated_both_np(clean):
        return True
    split = _split_np_pp(clean, allow_passive_pp)
    if split is None or not _is_pure_pre_pp(split[0]):
        return False
    return not split[1] or _is_pure_post_pp(split[1], _pre_pp_is_plural_or_agent(split[0]))


def _comma_list_treats_res(tk: ClauseToken, state: list[bool], seg_words: list[str]) -> str:
    if state[1] and seg_words and tk.low == "treats":
        return "fail"
    ok_np = not seg_words or _seg_is_pure_np(seg_words)
    return "ok" if state[0] and ok_np else "fail"


def _comma_list_flush(seg_words: list[str]) -> bool:
    if seg_words and not _seg_is_pure_np(seg_words):
        return False
    seg_words.clear()
    return True


def _comma_list_step(tk: ClauseToken, state: list[bool], seg_words: list[str]) -> str:
    if tk.kind == "treats":
        return _comma_list_treats_res(tk, state, seg_words)
    if _is_list_conj(tk):
        state[0] = True
        state[1] = state[1] or tk.low.split()[-1] == "and"
        return "cont" if _comma_list_flush(seg_words) else "fail"
    if tk.kind == "comma":
        return "cont" if _comma_list_flush(seg_words) else "fail"
    if tk.kind == "word":
        seg_words.append(tk.raw)
        return "cont"
    return "fail"


def _scan_comma_list_tokens(tokens: tuple[ClauseToken, ...], start: int) -> tuple[bool, int]:
    """Scan a comma-separated NP list once in O(n) stopping at any clause boundary."""
    state = [False, False]
    seg_words: list[str] = []
    for j in range(start, len(tokens)):
        res = _comma_list_step(tokens[j], state, seg_words)
        if res == "ok":
            return True, j
        if res == "fail":
            return False, j + 1
    return False, len(tokens)


def _is_adj_comma_next(st: dict[str, Any], nxt: ClauseToken) -> bool:
    return not st["cw_has_subj"] and _is_adj_word(nxt.raw, nxt.low)


def _comma_next_is_safe(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if idx + 1 >= len(tokens):
        return False
    nxt = tokens[idx + 1]
    if nxt.kind == "treats" or (nxt.kind == "coord" and nxt.low in {"and", "or"}):
        return True
    if nxt.kind != "word":
        return False
    if _is_adj_comma_next(st, nxt):
        return True
    nxt2 = tokens[idx + 2].low if idx + 2 < len(tokens) else ""
    return _is_finite_verb(nxt.raw, st["cw"] + [","], nxt2)


def _handle_empty_cw_comma(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    adv_end = _scan_adverbial_tokens(tokens, idx + 1)
    if adv_end > idx + 1 and tokens[adv_end - 1].kind == "comma":
        st["adv_comma_until"] = adv_end
    else:
        st.update(_reset_clause_state(st["s"]))


_APPOS_EXEMPLIFIERS = frozenset({"such", "including", "especially", "namely", "like", "notably"})
_APPOS_ADV_PART = frozenset({"orally", "intravenously", "daily", "subcutaneously", "intratumorally"})
_APPOS_PART_WORDS = frozenset({"bound", "shown", "known", "proven", "given", "seen", "made"})


def _appos_tokens_clean(span: tuple[ClauseToken, ...]) -> bool:
    for i, t in enumerate(span):
        is_part_inq = i <= 1 and t.kind == "inquiry" and bool(_MORPH_ED_VERB_RE.match(t.low))
        if not (t.kind in {"word", "coord", "abbrev"} or is_part_inq) or t.low in _PRONOUN_SUBJ:
            return False
    return True


def _is_participle_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    w0 = span[0]
    if not (_MORPH_ED_VERB_RE.match(w0.low) or w0.low in _APPOS_PART_WORDS):
        return False
    if len(span) > 1:
        s1 = span[1].low
        if s1 not in _POSTMOD_PARTICIPLE_NEXT and not _is_ly_adverb(s1) and s1 not in _APPOS_ADV_PART:
            return False
    return not _seg_has_finite_verb(words[1:])


def _is_exemplifier_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    w0 = span[0]
    if w0.kind != "abbrev" and w0.low not in _APPOS_EXEMPLIFIERS:
        return False
    if w0.low == "such" and (len(span) < 2 or span[1].low != "as"):
        return False
    return not _seg_has_finite_verb(words)


def _is_route_appos(span: tuple[ClauseToken, ...]) -> bool:
    return len(span) <= 3 and all(t.low in _APPOS_ROUTE_WORDS for t in span)


_WHEN_PART_MODS = _KNOWN_PASSIVE_PARTICIPLES | frozenset({
    "tested", "evaluated", "screened", "studied", "examined", "assessed", "assayed", "investigated",
    "incubated", "dissolved", "applied",
})
_IN_APPOS_WORDS = _IN_FIXED_WORDS | frozenset({"wet-lab", "comparison", "contrast", "synergy"})
_IN_THE_APPOS_HEADS = frozenset({"presence", "absence", "context", "setting", "case"})


def _appos_num_lead_ok(t0: ClauseToken) -> bool:
    if _is_s_verb(t0.low) or _is_ed_verb(t0.low):
        return False
    return t0.raw[0].isdigit() or t0.low in _PURE_NP_PREPS or _is_nominal_head_word(t0.raw, t0.low)


def _in_lead_appos_ok(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    if span[1].low in _IN_APPOS_WORDS:
        return True
    if span[1].low == "the" and len(span) >= 3 and span[2].low in _IN_THE_APPOS_HEADS:
        return True
    return _seg_is_pure_np(words[1:])


def _is_in_pp_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    if not (2 <= len(span) <= 6) or any(_is_agent_subject(w.lower()) for w in words):
        return False
    if span[0].low == "in":
        return _in_lead_appos_ok(span, words)
    return span[0].low == "under" and len(span) <= 4 and _seg_is_pure_np(words[1:])


def _is_in_fixed_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    if _is_in_pp_appos(span, words):
        return True
    return [t.low for t in span] in (["alone"], ["alone", "or", "in", "combination"])


def _is_note_or_in_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    if _is_route_appos(span):
        return True
    if _is_in_fixed_appos(span, words):
        return not _seg_has_finite_verb(words, implicit_subj=True)
    if len(span) > 7 or not any(t.raw[0].isdigit() for t in span if t.raw):
        return False
    return _appos_num_lead_ok(span[0]) and not _seg_has_finite_verb(words, implicit_subj=True)


def _is_cond_participle_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    if len(span) < 2 or span[0].low not in {"when", "if", "as"} or span[1].low not in _WHEN_PART_MODS:
        return False
    return not _seg_has_finite_verb(words[2:])


def _is_np_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    return len(span) <= 10 and span[0].low in _APPOS_DETS and _seg_is_pure_np(words)


_CONTRASTIVE_APPOS_PREFIXES: tuple[tuple[tuple[str, ...], int], ...] = (
    (("not",), 6),
    (("unlike",), 6),
    (("alongside",), 6),
    (("rather", "than"), 7),
    (("instead", "of"), 7),
    (("as", "opposed", "to"), 8),
)


def _is_contrastive_not_appos(span: tuple[ClauseToken, ...], words: list[str]) -> bool:
    if any(_is_agent_subject(w.lower()) for w in words):
        return False
    lows = tuple(t.low for t in span)
    for pref, max_len in _CONTRASTIVE_APPOS_PREFIXES:
        plen = len(pref)
        if plen + 1 <= len(span) <= max_len and lows[:plen] == pref:
            return _seg_is_pure_np(words[plen:])
    return False


def _is_valid_appos_span(span: tuple[ClauseToken, ...]) -> bool:
    if not span or not _appos_tokens_clean(span):
        return False
    words = [t.raw for t in span]
    return (
        _is_exemplifier_appos(span, words)
        or _is_participle_appos(span, words)
        or _is_cond_participle_appos(span, words)
        or _is_note_or_in_appos(span, words)
        or _is_np_appos(span, words)
        or _is_contrastive_not_appos(span, words)
    )


def _try_comma_appositive(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    j = idx + 1
    while j < len(tokens):
        tk = tokens[j]
        if tk.kind in {"comma", "comma_coord"}:
            break
        if tk.kind in _CLAUSE_BOUNDARY_KINDS or tk.kind == "treats":
            return False
        j += 1
    if j >= len(tokens) or tokens[j].kind not in {"comma", "comma_coord"}:
        return False
    if not _is_valid_appos_span(tokens[idx + 1 : j]):
        return False
    st["appos_ok_until"] = j
    return True


def _handle_appos_or_empty_comma(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if idx == st["appos_ok_until"]:
        if not (_try_comma_appositive(st, tokens, idx) or _paren_or_rel_allows_next(st, tokens, idx)):
            st.update(_reset_clause_state(st["s"]))
        return True
    if not st["cw"]:
        _handle_empty_cw_comma(st, tokens, idx)
        return True
    return _try_rel_comma_appositive(st, tokens, idx)


def _is_adj_only_cw(cw: list[str]) -> bool:
    return bool(cw) and all(w == "," or w.lower() in _PRE_NOMINAL_ADJS or w.lower().endswith(_ADJ_COMMA_SUFFIXES) or "-" in w or _is_ly_adverb(w.lower()) for w in cw)


def _comma_seg_has_clausal_prefix(st: dict[str, Any]) -> bool:
    if st["cw_all_adj"]:
        return False
    seg = st["cw"][st["cw_scan_from"] :]
    if _seg_has_finite_verb(seg, cw_head_plural=st["cw_head_plural"]):
        return True
    return not _is_adj_only_cw(seg) and not _seg_is_pure_np(seg)


def _try_rel_comma_appositive(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if not st["had_rel"] or st["in_rel"]:
        return False
    return _try_comma_appositive(st, tokens, idx)


def _handle_open_comma(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    if idx < st["list_ok_until"]:
        st["cw"].append(",")
        return
    if idx < st["adv_comma_until"] or _handle_appos_or_empty_comma(st, tokens, idx):
        return
    if _comma_seg_has_clausal_prefix(st):
        st.update(_reset_clause_state(st["s"]))
        return
    if st["cw_has_subj"] and _try_comma_appositive(st, tokens, idx):
        return
    if _comma_next_is_safe(st, tokens, idx):
        st["cw"].append(",")
        return
    ok, end_idx = _scan_comma_list_tokens(tokens, idx + 1)
    if ok:
        st["list_ok_until"] = end_idx
        st["cw"].append(",")
    else:
        st.update(_reset_clause_state(st["s"]))


def _try_modal_in_phrase_comma(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if idx + 2 >= len(tokens):
        return False
    t1, t2 = tokens[idx + 1], tokens[idx + 2]
    if t1.kind == "adv_break" and t1.low.startswith("in ") and t2.kind == "comma":
        st["appos_ok_until"] = idx + 2
        return True
    return False


def _handle_modal_comma(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> bool:
    if st["post_p_has_content"]:
        return False
    if idx == st["appos_ok_until"]:
        return _handle_appos_or_empty_comma(st, tokens, idx)
    return _try_modal_in_phrase_comma(st, tokens, idx) or _try_comma_appositive(st, tokens, idx)


def _handle_comma_token(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    if not st["h"]:
        st["in_paren"] = False
        return
    if idx < st["adv_ok_until"]:
        return
    st["after_coord"] = False
    if st["in_paren"]:
        _handle_paren_close_comma(st, tokens, idx)
        return
    if st["p"] and _handle_modal_comma(st, tokens, idx):
        return
    if st["p"] or st["r"]:
        st.update(_reset_clause_state(st["s"]))
        return
    _handle_open_comma(st, tokens, idx)


def _appos_close_idx(tokens: tuple[ClauseToken, ...], idx: int) -> int:
    j = idx + 1
    while j < len(tokens):
        tk = tokens[j]
        if tk.kind == "comma":
            return j if _is_valid_appos_span(tokens[idx + 1 : j]) else -1
        if tk.kind in _CLAUSE_BOUNDARY_KINDS or tk.kind in {"treats", "comma_coord"}:
            return -1
        j += 1
    return -1


def _coord_np_treats_res(tk: ClauseToken, seg_words: list[str], allow_singular: bool) -> str:
    ok_num = tk.low == "treat" or allow_singular
    ok_seg = not seg_words or _seg_is_pure_np(seg_words)
    return "ok" if ok_num and ok_seg else "fail"


def _rel_comma_close_idx(tokens: tuple[ClauseToken, ...], idx: int) -> int:
    if not tokens[idx].low.lstrip(", ").startswith(("which", "who")):
        return -1
    rel_words: list[str] = [tokens[idx].low.lstrip(", ")]
    j = idx + 1
    while j < len(tokens):
        tk = tokens[j]
        if tk.kind in {"comma", "comma_coord", "paren_open"}:
            return j if _paren_rel_is_benign(rel_words) else -1
        if tk.kind not in {"word", "coord"}:
            return -1
        rel_words.append(tk.low)
        j += 1
    return -1


def _coord_np_word_like(tk: ClauseToken, seg_words: list[str]) -> bool:
    return tk.kind == "word" or (tk.kind == "that" and not seg_words)


def _coord_np_step(tk: ClauseToken, seg_words: list[str], *, allow_singular: bool = False) -> str:
    if tk.kind == "treats":
        return _coord_np_treats_res(tk, seg_words, allow_singular)
    if _coord_np_word_like(tk, seg_words):
        seg_words.append(tk.raw)
        return "cont"
    if tk.kind == "coord":
        return "cont" if seg_words and _comma_list_flush(seg_words) else "fail"
    return "cont" if (tk.kind == "rel_paren" and seg_words) else "fail"


def _record_coord_scan(st: dict[str, Any], res: str, j: int, allow_singular: bool) -> bool:
    ok_key = "coord_np_or_ok_until" if allow_singular else "coord_np_ok_until"
    fail_key = "coord_np_or_fail_until" if allow_singular else "coord_np_fail_until"
    if res == "ok":
        st[ok_key] = j
    elif res == "fail":
        st[fail_key] = j
    return res == "ok"


def _coord_skip_close_idx(tokens: tuple[ClauseToken, ...], j: int, tk: ClauseToken, has_seg: bool) -> int:
    if tk.kind == "comma":
        return _appos_close_idx(tokens, j)
    if tk.kind == "paren_open" and has_seg:
        return _rel_comma_close_idx(tokens, j)
    return -1


def _scan_coord_np_to_treat(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, *, allow_singular: bool = False) -> bool:
    ok_key = "coord_np_or_ok_until" if allow_singular else "coord_np_ok_until"
    fail_key = "coord_np_or_fail_until" if allow_singular else "coord_np_fail_until"
    if idx < st[ok_key] or idx < st[fail_key]:
        return idx < st[ok_key]
    seg_words: list[str] = []
    j = idx + 1
    while j < len(tokens):
        tk = tokens[j]
        close_j = _coord_skip_close_idx(tokens, j, tk, bool(seg_words))
        if close_j > j:
            j = close_j if tokens[close_j].kind == "comma_coord" else close_j + 1
            continue
        res = _coord_np_step(tk, seg_words, allow_singular=allow_singular)
        if res != "cont":
            return _record_coord_scan(st, res, j, allow_singular)
        j += 1
    st[fail_key] = len(tokens)
    return False


def _coord_np_blocked_by_state(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, conj: str, via_comma: bool) -> bool:
    if st["p"] or st["r"] or via_comma:
        return True
    if conj == "but" and not st["cw_has_not"]:
        return True
    if idx + 1 < len(tokens) and tokens[idx + 1].low in _BARE_PRONOUN_SUBJ:
        return True
    seg = st["cw"][st["cw_scan_from"] :]
    if _seg_has_finite_verb(seg, cw_head_plural=st["cw_head_plural"]):
        return True
    return not _seg_is_pure_np(seg)


def _coord_needs_scan(st: dict[str, Any], conj: str) -> bool:
    if conj == "or":
        return True
    return conj == "and" and bool(st["cw_head_plural"] or st["cw_has_prep"] or st["cw_has_adv"] or st["cw_has_to_pp"])


def _is_ing_obj_coord(st: dict[str, Any], conj: str) -> bool:
    seg = st["cw"][st["cw_scan_from"] :]
    return conj == "and" and not st["cw_head_plural"] and len(seg) >= 2 and _is_postmod_ing_word(seg[-2].lower())


def _coord_np_allows_treats(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, conj: str, via_comma: bool) -> bool:
    if _coord_np_blocked_by_state(st, tokens, idx, conj, via_comma):
        return False
    if st["had_rel"]:
        return conj in {"and", "or"} and _scan_coord_np_to_treat(st, tokens, idx, allow_singular=(conj == "or"))
    if _is_ing_obj_coord(st, conj):
        return _scan_coord_np_to_treat(st, tokens, idx, allow_singular=True)
    if _coord_needs_scan(st, conj):
        return _scan_coord_np_to_treat(st, tokens, idx, allow_singular=(conj == "or" and not st["cw_head_plural"]))
    return True


def _append_cw_coord(st: dict[str, Any], conj: str) -> None:
    st["cw"].append(conj)
    st["cw_scan_from"] = len(st["cw"])
    st["cw_all_adj"] = True
    if conj == "and" and not st["cw_has_prep"] and not st["in_rel"] and not st["had_rel"]:
        st["cw_head_plural"] = True
    st["after_coord"] = True


def _on_coord_step(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, conj: str, *, via_comma: bool = False) -> None:
    if not st["h"] or st["in_paren"] or idx < st["appos_ok_until"]:
        return
    if via_comma and idx < st["list_ok_until"]:
        st["cw"].append(conj)
        st["after_coord"] = True
        return
    if _coord_np_allows_treats(st, tokens, idx, conj, via_comma):
        st["r"] = False
        st["lp"] = False
        _append_cw_coord(st, conj)
        return
    if conj in {"and", "or"} and _post_coord_allows_treats(tokens, idx + 1, st):
        st["p"] = False
        st["p_is_modal"] = False
        st["p_is_copula"] = False
        st["r"] = False
        st["lp"] = False
        st["after_coord"] = True
        st["post_p"].clear()
        st["post_p_has_content"] = False
    else:
        st.update(_reset_clause_state(st["s"]))


def _on_whether_or_not(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    prev_comma = idx > 0 and tokens[idx - 1].kind == "comma"
    nxt = tokens[idx + 1] if idx + 1 < len(tokens) else None
    concessive = prev_comma or nxt is None or nxt.kind == "comma" or nxt.low in _CONCESSIVE_TAIL_WORDS
    can_head = (st["s"] or st["h"]) and not concessive
    st.update(_reset_clause_state(st["s"]))
    if can_head:
        st["h"] = True


def _adv_break_skip(st: dict[str, Any], idx: int) -> bool:
    return st["in_paren"] or not st["h"] or not st["cw"] or idx + 1 <= st["adv_ok_until"] or idx < st["appos_ok_until"]


def _on_adv_break(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    if _adv_break_skip(st, idx):
        return
    ok, adv_end, is_s_coord = _coord_allows_after_adv(tokens, idx + 1)
    if not ok:
        st.update(_reset_clause_state(st["s"]))
        return
    st["adv_ok_until"] = max(st["adv_ok_until"], adv_end)
    st["coord_s_verb"] = st["coord_s_verb"] or is_s_coord
    if len(st["post_p"]) <= 1 and not any(w.lower() in _PRONOUN_SUBJ for w in st["post_p"]):
        st["post_p"].clear()
        st["post_p_has_content"] = False


def _on_comma_coord(st: dict[str, Any], toks: tuple[ClauseToken, ...], idx: int, tok: ClauseToken) -> None:
    was_paren, was_appos = st["in_paren"], idx == st["appos_ok_until"]
    st["in_paren"] = False
    if was_appos:
        st["appos_ok_until"] = 0
        st["cw_has_prep"] = True
    if was_paren and st["had_rel"]:
        st["r"] = False
        st["lp"] = False
    _on_coord_step(st, toks, idx, tok.low.split()[-1], via_comma=not (was_appos or (was_paren and st["had_rel"])))


def _on_paren_open(st: dict[str, Any], tok: ClauseToken) -> None:
    if not st["h"]:
        return
    has_subj = bool(st["cw"])
    st["in_paren"] = True
    st["after_coord"] = False
    st["r"] = st["r"] or has_subj
    st["lp"] = st["lp"] or (not has_subj)
    if tok.low.lstrip(", ").startswith(("which", "who")):
        st["had_rel"] = True


def _on_abbrev_tok(st: dict[str, Any], tok: ClauseToken) -> None:
    if st["h"] and not st["in_paren"] and tok.low.startswith("vs"):
        st["cw"].append("vs")


def _on_inquiry_tok(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int, tok: ClauseToken) -> None:
    st["s"] = True
    if st["h"] and not st["in_paren"] and st["cw"]:
        _handle_word_token(st, tokens, idx, tok)


def _on_inquiry_if(st: dict[str, Any], tokens: tuple[ClauseToken, ...], idx: int) -> None:
    nxt = tokens[idx + 1].low if idx + 1 < len(tokens) else ""
    st.update(_reset_clause_state(True))
    st["h"] = nxt not in _ELLIPTIC_IF_WORDS


def _on_whether(st: dict[str, Any]) -> None:
    if st["s"] or st["h"]:
        st.update(_reset_clause_state(st["s"]))
        st["h"] = True


def _on_guarded_that(st: dict[str, Any], tok: ClauseToken) -> None:
    if st["h"] and not st["in_paren"]:
        st["after_coord"] = False
        st["cw"].append(tok.raw.split()[-1])
        st["post_p"].clear()
        st["post_p_has_content"] = False


_TOKEN_DISPATCH = {
    "hard_break": lambda st, toks, idx, tok: st.update(_reset_clause_state(st["s"])),
    "punct": lambda st, toks, idx, tok: st.update(_reset_clause_state(False)),
    "abbrev": lambda st, toks, idx, tok: _on_abbrev_tok(st, tok),
    "rel_paren": lambda st, toks, idx, tok: _on_rel_paren(st, toks, idx),
    "whether_or_not": lambda st, toks, idx, tok: _on_whether_or_not(st, toks, idx),
    "only_that_noun": lambda st, toks, idx, tok: _on_guarded_that(st, tok),
    "gerund_that_noun": lambda st, toks, idx, tok: _on_guarded_that(st, tok),
    "confirm": lambda st, toks, idx, tok: st.update(_reset_clause_state(True)),
    "inquiry": _on_inquiry_tok,
    "whether": lambda st, toks, idx, tok: _on_whether(st),
    "inquiry_if": lambda st, toks, idx, tok: _on_inquiry_if(st, toks, idx),
    "paren_open": lambda st, toks, idx, tok: _on_paren_open(st, tok),
    "comma": lambda st, toks, idx, tok: _handle_comma_token(st, toks, idx),
    "comma_coord": lambda st, toks, idx, tok: _on_comma_coord(st, toks, idx, tok),
    "coord": lambda st, toks, idx, tok: _on_coord_step(st, toks, idx, tok.low),
    "adv_break": lambda st, toks, idx, tok: _on_adv_break(st, toks, idx),
    "that": lambda st, toks, idx, tok: _handle_that_token(st),
    "word": lambda st, toks, idx, tok: _handle_word_token(st, toks, idx, tok),
}


def _clause_has_unhedged_treats(sent: str) -> bool:
    """Return True if sentence lacks preclinical hedging or has an unhedged directive clause (O(n))."""
    if not _PRECLINICAL_QUAL_RE.search(sent) or _has_ordered_match(sent, _CLIN_VERBS_RE, _TREATS_ONLY_RE):
        return True
    tokens = _tokenize_clause_stream(_mask_parens_linear(sent))
    st = _reset_clause_state(False)
    for idx, tok in enumerate(tokens):
        if tok.kind == "treats":
            if _handle_treats_token(st, tok.raw):
                return True
        elif tok.kind in _TOKEN_DISPATCH:
            _TOKEN_DISPATCH[tok.kind](st, tokens, idx, tok)
    return False


def _sw_has_clinical_with_arg(sent: str) -> bool:
    if _DISEASE_CLIN_NOUN_RE.search(sent) is None:
        return False
    for m in _SW_WITH_ARG_RE.finditer(sent):
        arg = m.group("arg")
        if _SW_DATA_OBJ_RE.fullmatch(arg) is None and _SW_SUBJECT_RE.fullmatch(arg) is None:
            return True
    return False


def _has_non_sw_markers(sent: str) -> bool:
    if ";" in sent or _CLIN_VERBS_RE.search(sent) or _HUMAN_TARGET_RE.search(sent) or _sw_has_clinical_with_arg(sent):
        return True
    return bool(_PRECLINICAL_COMPOUND_RE.search(sent) or _PRECLINICAL_QUAL_RE.search(sent))


_Q_CLAUSE_DISQUALIFIERS = frozenset({
    "while", "meanwhile", "whereas", "because", "since", "unless", "if", "although", "though",
    "however", "nevertheless", "therefore", "thus", "hence", "otherwise", "then", "also", "so", "yet",
})
_Q_OPENER_PREFIX_RE = re.compile(
    r"^\s*(?:"
    r"(?:is|are|was|were)\s+it\s+(?:true|possible|likely|plausible|clear|known|established)\s+that\b"
    r"|(?:how|why|when|where)\s+(?:can|could|would|should|may|might|does|do)\b"
    r"|(?:can|could|would|should|may|might|does|is|are|which|what(?!\s+if\b))\b"
    r")",
    _RE_FLAGS,
)
_DO_HEAD_RE = re.compile(r"^\s*do(?:(?=\s)|(?=,)|$)", _RE_FLAGS)
_DO_LEAD_ADVS = frozenset({"not", "n't", "please", "always", "just", "simply", "kindly", "now"})
_DO_SINGULAR_ONLY_DETS = frozenset({"a", "an", "this", "that", "each", "every", "one"})
_DO_BOUNDARY_KINDS = _CLAUSE_BOUNDARY_KINDS | frozenset({"adv_break"})


def _find_comma_end(toks: tuple[ClauseToken, ...], start: int) -> int:
    j = start
    while j < len(toks) and toks[j].kind not in {"comma", "paren_open"}:
        if toks[j].kind in _CLAUSE_BOUNDARY_KINDS or toks[j].kind == "treats":
            return -1
        j += 1
    return j if j < len(toks) else -1


def _do_lead_comma_next(toks: tuple[ClauseToken, ...], i: int) -> int:
    j = _find_comma_end(toks, i + 1)
    if j < 0 or _seg_has_finite_verb([t.raw for t in toks[i + 1 : j] if t.kind in {"word", "coord"}], implicit_subj=True):
        return -1
    if toks[j].kind == "paren_open":
        return j
    return j if _q_comma_next_is_appos(toks, j) else j + 1


def _strip_do_leading_mods(toks: tuple[ClauseToken, ...]) -> list[ClauseToken] | None:
    i, n = 1, len(toks)
    while i < n:
        tk = toks[i]
        if tk.kind == "comma":
            i = _do_lead_comma_next(toks, i)
            if i < 0:
                return None
        elif tk.low in _DO_LEAD_ADVS or _is_ly_adverb(tk.low):
            i += 1
        else:
            break
    return list(toks[i:])


_DO_DIRECT_STARTERS = _DETS_ONLY | _PRE_NOMINAL_ADJS | _DO_PLURAL_PRONOUNS | _PLURAL_HEADS


def _do_non_det_starter_ok(r0: str, w0: str, nxt: str, has_coord: bool) -> bool:
    if w0 in _TRANSITIVE_NOUN_VERBS:
        return False
    if _is_pre_nominal_mod(r0, w0, nxt) or _is_short_id_token(r0) or _is_plural_noun_token(w0):
        return True
    return (has_coord and _is_sing_nominal(w0)) or nxt in {"and", "or"}


def _do_starter_ok(subj: list[ClauseToken], has_coord: bool) -> bool:
    w0, r0 = subj[0].low, subj[0].raw
    if w0 in _DO_SINGULAR_ONLY_DETS and not has_coord:
        return False
    nxt = subj[1].low if len(subj) > 1 else ""
    return w0 in _DO_DIRECT_STARTERS or _do_non_det_starter_ok(r0, w0, nxt, has_coord)


def _tok_is_do_plural_mark(t: ClauseToken) -> bool:
    return t.low in (_DO_PLURAL_PRONOUNS | _PLURAL_HEADS) or t.low == "and" or _is_plural_noun_token(t.low)


def _is_do_plural_subj(subj: list[ClauseToken]) -> bool:
    if not subj or _has_agent_subject([t.raw for t in subj]) or not _q_coord_segments_pure_np(tuple(subj)):
        return False
    has_coord = any(t.low == "and" for t in subj)
    return _do_starter_ok(subj, has_coord) and any(_tok_is_do_plural_mark(t) for t in subj)


def _is_do_to_treat_valid(body: list[ClauseToken]) -> bool:
    while body and _is_adv_link(body[-1].low):
        body.pop()
    if len(body) < 2:
        return False
    v_tok = body[-1].low
    verb_ok = (
        len(v_tok) >= 2
        and v_tok not in (_NON_PLAIN_VERB_WORDS | _PRE_NOMINAL_NOUN_MODS)
        and not _is_sing_nominal(v_tok)
        and (_has_verb_stem_shape(v_tok) or v_tok in _PLURAL_BASE_VERBS)
    )
    return verb_ok and _is_do_plural_subj(body[:-1])


def _do_clean_rem(prefix: str) -> list[ClauseToken] | None:
    toks = _tokenize_clause_stream(_mask_parens_linear(prefix))
    rem = _strip_do_leading_mods(toks) if toks and toks[0].low == "do" else None
    if not rem or _q_has_disqualifier(rem):
        return None
    rem = _strip_q_comma_mods(rem)
    if not rem or any(t.kind in _DO_BOUNDARY_KINDS for t in rem):
        return None
    return _strip_q_partitive_of("do ", rem)


def _is_do_question_valid(prefix: str, tr_low: str) -> bool:
    if tr_low != "treat":
        return False
    rem = _do_clean_rem(prefix)
    if not rem:
        return False
    return _is_do_to_treat_valid(rem[:-1]) if rem[-1].low == "to" else _is_do_plural_subj(rem)


def _is_do_imperative(sent: str) -> bool:
    if not _DO_HEAD_RE.match(sent):
        return False
    m_tr = _TREATS_ONLY_RE.search(sent)
    return m_tr is not None and not _is_do_question_valid(sent[: m_tr.start()], m_tr.group(0).lower())


def _sw_mod_ok(w: str) -> bool:
    if w in _SW_SUBJECT_MOD_WORDS or _SW_DATA_OBJ_RE.fullmatch(w) or _SW_SUBJECT_HEAD_RE.fullmatch(w):
        return True
    return "-" in w or w.endswith(("al", "ic", "ive", "ed", "ing"))


def _sw_strip_modal_advs(words: list[str]) -> list[str]:
    while words and (_is_ly_adverb(words[-1].lower()) or _SW_PRE_TREAT_MODAL_RE.fullmatch(words[-1])):
        words.pop()
    return words


def _sw_split_coord_segs(words: list[str]) -> list[list[str]]:
    segs: list[list[str]] = [[]]
    for raw_w in words:
        clean_w = raw_w.rstrip(",")
        if clean_w.lower() in {"and", "or"}:
            if segs[-1]:
                segs.append([])
        elif clean_w:
            segs[-1].append(clean_w)
            if raw_w.endswith(","):
                segs.append([])
    return segs


def _sw_seg_ok(seg: list[str]) -> bool:
    if not seg or not _SW_SUBJECT_HEAD_RE.fullmatch(seg[-1]):
        return False
    return all(_sw_mod_ok(m.lower()) for m in seg[:-1])


def _sw_subject_valid(prefix: str) -> bool:
    cleaned = _SW_Q_LEAD_RE.sub("", _mask_parens_linear(prefix).replace("\x00PR\x00", " "), count=1)
    if "\x00PN\x00" in cleaned:
        return False
    words = _sw_strip_modal_advs(_SW_REL_CLAUSE_RE.sub(" ", cleaned, count=1).split())
    raw_segs = _sw_split_coord_segs(words) if words else []
    return bool(raw_segs) and all(_sw_seg_ok(s) for s in raw_segs)


_SW_TAIL_CLAUSE_STOPS = frozenset({
    "while", "whereas", "because", "since", "although", "though", "if", "unless", "but", "until", "when", "where",
})
_SW_COORD_GAP_RE = re.compile(r",\s*(?:and|or|while|whereas)\b|\b(?:and|or|while|whereas)\b", _RE_FLAGS)


_SW_MANNER_ADVS = frozenset({
    "identically", "equally", "uniformly", "similarly", "interchangeably", "cleanly",
    "opaquely", "literally", "lexically", "syntactically", "recursively", "deterministically", "alphabetically",
})


def _sw_is_obj_word(w: str) -> bool:
    return bool(_SW_DATA_OBJ_RE.fullmatch(w)) or w in _SW_MANNER_ADVS


def _sw_tail_has_direct_obj(words: list[str]) -> bool:
    for w in words:
        if w in _SW_TAIL_CLAUSE_STOPS:
            return False
        if _sw_is_obj_word(w):
            return True
    return False


def _sw_disease_allowed_at(words: list[str], idx: int, seen_sw_obj: bool) -> bool:
    if seen_sw_obj:
        return True
    if idx >= 1 and words[idx - 1] in {"not", "unlike", "vs"} and any(_sw_is_obj_word(w) for w in words[:idx]):
        return True
    return idx >= 2 and words[idx - 2] in _SW_MANNER_ADVS and words[idx - 1] in {"to", "with", "as"}


def _sw_tail_disease_ok(words: list[str]) -> bool:
    seen_sw_obj = False
    for idx in range(len(words) - 1, -1, -1):
        w = words[idx]
        if _sw_is_obj_word(w):
            seen_sw_obj = True
        elif _DISEASE_ONLY_RE.fullmatch(w) and not _sw_disease_allowed_at(words, idx, seen_sw_obj):
            return False
    return True


def _sw_clause_pair_ok(prefix: str, tail: str) -> bool:
    if not _sw_subject_valid(prefix):
        return False
    words = [w.strip(",.;:?!").lower() for w in tail.split() if w.strip(",.;:?!")]
    return _sw_tail_has_direct_obj(words) and _sw_tail_disease_ok(words)


def _sw_split_gap(gap: str) -> tuple[int, int] | None:
    matches = list(_SW_COORD_GAP_RE.finditer(gap))
    if not matches:
        return None
    comma_hits = [m for m in matches if m.group(0).startswith(",")]
    chosen = comma_hits[-1] if comma_hits else matches[-1]
    return chosen.start(), chosen.end()


def _is_non_clinical_software_treat(sent: str) -> bool:
    if _has_non_sw_markers(sent) or _SW_CLINICAL_CURE_RE.search(sent):
        return False
    hits = list(_SW_TREAT_VERB_RE.finditer(sent))
    if not hits:
        return False
    if len(hits) == 1:
        return _sw_clause_pair_ok(sent[: hits[0].start()], sent[hits[0].end() :])
    cur_start = 0
    for idx, hit in enumerate(hits):
        prefix = sent[cur_start : hit.start()]
        if idx + 1 == len(hits):
            return _sw_clause_pair_ok(prefix, sent[hit.end() :])
        split = _sw_split_gap(sent[hit.end() : hits[idx + 1].start()])
        if split is None:
            return False
        tail = sent[hit.end() : hit.end() + split[0]]
        if not _sw_clause_pair_ok(prefix, tail):
            return False
        cur_start = hit.end() + split[1]
    return False


def _has_disqualifying_assertive_modal(sent: str) -> bool:
    return _has_ordered_match(sent, _ASSERTIVE_MODAL_RE, _TREATS_ONLY_RE)


def _q_seg_step(tk: ClauseToken, segs: list[list[str]]) -> bool:
    if tk.low == "\x00pn\x00":
        return True
    if tk.kind == "rel_paren":
        return bool(segs[-1])
    if tk.kind == "comma" and segs[-1] and _is_adj_only_cw(segs[-1]):
        return True
    if tk.kind in {"coord", "comma", "comma_coord"}:
        if not segs[-1]:
            return False
        segs.append([])
        return True
    if tk.kind == "word":
        segs[-1].append(tk.raw)
        return True
    return False


def _q_coord_segments_pure_np(tokens: tuple[ClauseToken, ...]) -> bool:
    segs: list[list[str]] = [[]]
    for tk in tokens:
        if not _q_seg_step(tk, segs):
            return False
    return bool(segs[-1]) and all(_seg_is_pure_np(s) and not _seg_has_modal_transitive_verb(s) for s in segs)


def _q_comma_inner_span(tk: ClauseToken, inner: tuple[ClauseToken, ...]) -> tuple[ClauseToken, ...]:
    if tk.kind != "paren_open":
        return inner
    parts = tk.low.lstrip(", ").split()
    return (ClauseToken("word", parts[0], parts[0]), ClauseToken("word", parts[1], parts[1]), *inner)


def _is_q_comma_mod_start(tk: ClauseToken) -> bool:
    return tk.kind == "comma" or (tk.kind == "paren_open" and tk.low.startswith((", as ", ", when ", ", if ")))


def _is_q_comma_pure_np(tk: ClauseToken, inner: tuple[ClauseToken, ...]) -> bool:
    return tk.kind == "comma" and all(t.kind == "word" for t in inner) and _seg_is_pure_np([t.raw for t in inner])


def _q_comma_rel_action(toks: tuple[ClauseToken, ...], i: int) -> tuple[str, int]:
    if i == len(toks) - 1:
        return "keep_one", i + 1
    rel_j = _rel_comma_close_idx(toks, i)
    if rel_j <= i:
        return "fail", -1
    if toks[rel_j].kind != "comma":
        return "skip", rel_j
    return "skip", (rel_j if _q_comma_next_is_appos(toks, rel_j) else rel_j + 1)


def _q_comma_next_is_appos(toks: tuple[ClauseToken, ...], j: int) -> bool:
    if j + 1 >= len(toks) or toks[j].kind != "comma":
        return False
    nxt = toks[j + 1]
    if nxt.kind == "paren_open":
        return True
    j2 = _find_comma_end(toks, j + 1)
    return j2 > j + 1 and _is_valid_appos_span(toks[j + 1 : j2])


def _is_q_rel_comma_tok(tk: ClauseToken) -> bool:
    return tk.kind == "paren_open" and tk.low.lstrip(", ").startswith(("which", "who"))


def _q_appos_skip_idx(toks: tuple[ClauseToken, ...], j: int) -> int:
    return j if (toks[j].kind == "paren_open" or _q_comma_next_is_appos(toks, j)) else j + 1


def _q_comma_action(toks: tuple[ClauseToken, ...], i: int) -> tuple[str, int]:
    tk = toks[i]
    if _is_q_rel_comma_tok(tk):
        return _q_comma_rel_action(toks, i)
    if not _is_q_comma_mod_start(tk):
        return "keep_one", i + 1
    j = _find_comma_end(toks, i + 1)
    if j < 0:
        return ("fail", -1) if tk.kind == "paren_open" else ("keep_one", i + 1)
    inner = _q_comma_inner_span(tk, toks[i + 1 : j])
    if _is_valid_appos_span(inner):
        return "skip", _q_appos_skip_idx(toks, j)
    return ("keep_span", j) if _is_q_comma_pure_np(tk, inner) else ("fail", -1)


def _strip_q_comma_mods(toks: list[ClauseToken]) -> list[ClauseToken] | None:
    out: list[ClauseToken] = []
    t_tup = tuple(toks)
    i, n = 0, len(toks)
    while i < n:
        act, nxt_i = _q_comma_action(t_tup, i)
        if act == "fail":
            return None
        if act in {"keep_one", "keep_span"}:
            out.extend(toks[i:nxt_i])
        i = nxt_i
    return out


def _strip_q_trailing_advs(toks: list[ClauseToken]) -> list[ClauseToken]:
    while toks:
        if len(toks) >= 2 and toks[-2].low == "in" and toks[-1].low in _IN_FIXED_WORDS:
            toks = toks[:-2]
        elif _is_adv_link(toks[-1].low):
            toks = toks[:-1]
        else:
            break
    return toks


def _strip_q_trailing_linkers(toks: list[ClauseToken], is_singular: bool, had_epistemic: bool) -> list[ClauseToken] | None:
    toks = _strip_q_trailing_advs(toks)
    if is_singular:
        has_rel = bool(toks and toks[-1].kind in {"that", "paren_open"})
        if has_rel:
            toks = toks[:-1]
        return toks if (has_rel or had_epistemic) else None
    if len(toks) >= 2 and toks[-1].low == "to" and toks[-2].low in _SUBJECT_CONTROL_WORDS:
        return toks[:-2]
    return toks


def _q_has_disqualifier(toks: list[ClauseToken]) -> bool:
    bad = {"hard_break", "adv_break", "confirm", "whether", "whether_or_not", "inquiry_if"}
    return any(t.kind in bad or t.low in _Q_CLAUSE_DISQUALIFIERS for t in toks)


_PARTITIVE_QUANTS = frozenset({
    "either", "neither", "each", "both", "one", "none", "any", "some", "all", "many", "several", "most",
})
_MODAL_TRANS_OBJ_STOP = _NON_VERB_NEXT_STOP | _CLAUSE_PREPS | {"validation", "kit", "kits", "buffer", "protocol", "data", "results"}


def _strip_q_partitive_of(sent: str, toks: list[ClauseToken]) -> list[ClauseToken]:
    if _WH_SUBJECT_RE.match(sent) and len(toks) >= 2 and toks[0].low == "of":
        return toks[1:]
    if len(toks) >= 3 and toks[0].low in _PARTITIVE_QUANTS and toks[1].low == "of":
        return toks[2:]
    return toks


def _seg_has_modal_transitive_verb(seg_words: list[str]) -> bool:
    for k in range(1, len(seg_words) - 1):
        wl = seg_words[k].lower()
        if wl not in _TRANSITIVE_NOUN_VERBS:
            continue
        prev = seg_words[k - 1].lower()
        nxt = seg_words[k + 1].lower()
        if prev in (_DETS_ONLY | _PRE_NOMINAL_ADJS | _CLAUSE_PREPS) or prev.endswith(("ed", "ing")):
            continue
        if nxt not in _MODAL_TRANS_OBJ_STOP:
            return True
    return False


def _q_subj_tokens(sent: str, prefix: str, is_sing: bool) -> list[ClauseToken] | None:
    m_op = _Q_OPENER_PREFIX_RE.match(prefix)
    if not m_op:
        return None
    toks = list(_tokenize_clause_stream(_mask_parens_linear(prefix[m_op.end() :])))
    cleaned = None if _q_has_disqualifier(toks) else _strip_q_comma_mods(toks)
    if cleaned is None:
        return None
    cleaned = _strip_q_partitive_of(sent, cleaned)
    had_ep = bool(_WH_SUBJECT_RE.match(sent) or _EPISTEMIC_Q_RE.match(sent))
    return _strip_q_trailing_linkers(cleaned, is_sing, had_ep)


def _question_treats_allowed(sent: str) -> bool:
    if _CAUSAL_BREAK_RE.search(sent) or _has_disqualifying_assertive_modal(sent):
        return False
    hits = _TREATS_ONLY_RE.findall(sent)
    if len(hits) != 1:
        return False
    m_tr = _TREATS_ONLY_RE.search(sent)
    assert m_tr is not None
    prefix = sent[: m_tr.start()]
    if _DO_HEAD_RE.match(prefix):
        return _is_do_question_valid(prefix, m_tr.group(0).lower())
    subj = _q_subj_tokens(sent, prefix, m_tr.group(0).lower() == "treats")
    return bool(subj) and not _has_agent_subject([t.raw for t in subj]) and _q_coord_segments_pure_np(tuple(subj))


def _modal_hedges_all_treats(sent: str) -> bool:
    if _TREATS_SINGULAR_RE.search(sent) or _CAUSAL_BREAK_RE.search(sent):
        return False
    hits = _TREATS_ONLY_RE.findall(sent)
    return bool(hits) and len(hits) == len(_MODAL_HEDGE_TREAT_RE.findall(sent))


def _inquiry_has_disqualifier(sent: str) -> bool:
    return bool(_CURES_ONLY_RE.search(sent) or _HUMAN_TARGET_RE.search(sent) or not _PRECLINICAL_QUAL_RE.search(sent) or _CLIN_VERBS_RE.search(sent))


def _is_direct_preclinical_inquiry(sent: str, is_question: bool = False) -> bool:
    if _is_non_clinical_software_treat(sent):
        return True
    if _inquiry_has_disqualifier(sent):
        return False
    if is_question and _QUESTION_OPENER_RE.match(sent):
        return _question_treats_allowed(sent)
    if not is_question and _DIRECT_INQUIRY_RE.match(sent) and not _TREATS_SINGULAR_RE.search(sent):
        return _question_treats_allowed(sent)
    return _modal_hedges_all_treats(sent)


def _q_has_active_reporting_verb(sent: str) -> bool:
    cleaned = _PASSIVE_REPORT_CLAUSE_RE.sub(" ", sent)
    return bool(_CLIN_OR_REPORTING_VERBS_RE.search(cleaned))


_CLIN_OR_INQUIRY_VERBS_LOWER_RE = re.compile(_CLIN_OR_INQUIRY_VERBS_RE.pattern, re.ASCII)
_TREATS_ONLY_LOWER_RE = re.compile(_TREATS_ONLY_RE.pattern, re.ASCII)
_DISEASE_ONLY_LOWER_RE = re.compile(_DISEASE_ONLY_RE.pattern, re.ASCII)
_CLINICAL_FAST_SUBSTRS = (
    "cure", "curi", "cura", "heal", "treat", "clinical", "give", "gave", "giving",
    "administer", "dos", "infus", "prescrib", "recommend", "treatment", "therap", "patient", "human",
)
_TREATMENT_PRECLIN_HEDGE_RE = re.compile(r"\bwhether\b|^\s*(?:can|could|would|should|may|might|does|do|is|are)\b", _RE_FLAGS)


def _is_hedged_preclinical_treatment(sent: str, is_question: bool = False) -> bool:
    if _CLIN_VERBS_RE.search(sent) or not _PRECLINICAL_QUAL_RE.search(sent):
        return False
    return bool(is_question or _TREATMENT_PRECLIN_HEDGE_RE.search(sent))


def _has_prescribe_recommend_or_treatment(sent: str, is_question: bool = False) -> bool:
    if _has_ordered_match(sent, _PRESCRIBE_RE, _ALL_DISEASE_TARGET_RE):
        return True
    if _has_ordered_match(sent, _RECOMMEND_RE, _HUMAN_TARGET_RE) or _has_ordered_match(sent, _RECOMMEND_RE, _TREATMENT_FOR_DISEASE_RE):
        return True
    if _has_ordered_match(sent, _RECOMMEND_RE, _ALL_DISEASE_TARGET_RE) and not _is_hedged_preclinical_treatment(sent, is_question):
        return True
    return bool(_TREATMENT_FOR_DISEASE_RE.search(sent) and not _is_hedged_preclinical_treatment(sent, is_question))


def _has_direct_cure_or_human(sent: str, is_question: bool = False) -> bool:
    if _has_ordered_match(sent, _CLIN_VERBS_RE, _CLIN_CURE_PHRASE_RE):
        return True
    if _HUMAN_TARGET_RE.search(sent) and (_CURES_TREATS_RE.search(sent) or _HUMAN_ADMIN_VERBS_RE.search(sent)):
        return True
    if _has_prescribe_recommend_or_treatment(sent, is_question):
        return True
    return bool(_CURES_ONLY_RE.search(sent) and (_ALL_DISEASE_TARGET_RE.search(sent) or _PRECLINICAL_COMPOUND_RE.search(sent)))


def _has_declarative_treated_disease(sent: str, is_question: bool) -> bool:
    has_tr = (
        _TREATED_DISEASE_RE.search(sent) is not None
        or _has_ordered_match(sent, _ACTIVE_TREATED_TREATING_RE, _DISEASE_CLIN_NOUN_RE)
        or _has_ordered_match(sent, _DISEASE_CLIN_NOUN_RE, _PASSIVE_TREATED_BY_WITH_RE)
    )
    if not has_tr:
        return False
    if _CLIN_VERBS_RE.search(sent) or not _PRECLINICAL_QUAL_RE.search(sent):
        return not _is_non_clinical_software_treat(sent) and not _is_direct_preclinical_inquiry(sent, is_question)
    return False


def _has_clin_inq_treats_disease(sent_low: str) -> bool:
    return _has_ordered_match(sent_low, _CLIN_OR_INQUIRY_VERBS_LOWER_RE, _TREATS_ONLY_LOWER_RE, _DISEASE_ONLY_LOWER_RE)


def _has_clinical_treats_unhedged(sent: str, sent_low: str, is_question: bool) -> bool:
    if _has_clin_inq_treats_disease(sent_low):
        return _clause_has_unhedged_treats(sent)
    if _has_ordered_match(sent_low, _TREATS_ONLY_LOWER_RE, _DISEASE_ONLY_LOWER_RE) and not _is_direct_preclinical_inquiry(sent, is_question):
        return _clause_has_unhedged_treats(sent)
    return False


def _sentence_has_clinical_cure(sent: str, is_question: bool = False) -> bool:
    sent_low = sent.lower()
    if not any(tok in sent_low for tok in _CLINICAL_FAST_SUBSTRS):
        return False
    if _is_non_clinical_software_treat(sent):
        return False
    if _has_direct_cure_or_human(sent, is_question) or _has_declarative_treated_disease(sent, is_question):
        return True
    if is_question and _is_direct_preclinical_inquiry(sent, True) and not _q_has_active_reporting_verb(sent):
        return False
    return _has_clinical_treats_unhedged(sent, sent_low, is_question)


def _clinical_seg_violates(seg_text: str, is_question: bool) -> bool:
    if "why" not in seg_text.lower():
        return _sentence_has_clinical_cure(seg_text, is_question)
    clauses = split_negated_safety_clauses(seg_text)
    if len(clauses) == 1 and clauses[0][1] == "clinical":
        return False
    return any(not is_scope_exempt(sub, scope, "clinical") and _sentence_has_clinical_cure(sub, is_question) for sub, scope in clauses)


def _split_cure_parts_fast(clean: str) -> list[str]:
    if "." not in clean and "!" not in clean and "?" not in clean and ";" not in clean:
        return [clean]
    return _CURE_SPLIT_RE.split(clean)


def _cure_seg_key(seg_parts: list[str], idx: int, has_q_end: bool) -> tuple[str, bool]:
    sep = seg_parts[idx + 1] if idx + 1 < len(seg_parts) else ""
    return (seg_parts[idx], ("?" in sep) or (";" in sep and has_q_end))


def _clinical_cure_violation(clean: str, parts: list[str] | None = None) -> bool:
    """Detect clinical cure coercion while allowing hedged preclinical wet-lab inquiries."""
    seg_parts = parts if parts is not None else _split_cure_parts_fast(clean)
    has_q_end = len(seg_parts) > 1 and any("?" in seg_parts[k] for k in range(1, len(seg_parts), 2))
    seen: set[tuple[str, bool]] = set()
    for i in range(0, len(seg_parts), 2):
        key = _cure_seg_key(seg_parts, i, has_q_end)
        if key not in seen and (seen.add(key) or _clinical_seg_violates(*key)):
            return True
    return False

# Default showcase tasks covering all 9 sisters in deterministic offline mode.
_SHOWCASE_TASKS: dict[str, str] = {
    "Zoe": "route showcase task",
    "Gemma": "compile spatial ir vdi and artline plate",
    "Tosi": "verify static uefi closure and hardware gates",
    "Mono": "audit epistemic blackboard and constitutional firewall",
    "Tetra": "route hex mesh and verify isolated uma airlock",
    "Eliza": "gear1 grounded summary",
    "Sage": "solve x^2 - 9 = 0",
    "Flora": "verify botanical c27 atlas under sealed privacy",
    "Lumen": "verify theorem 16 optics and 2.5w honesty headlamp",
}


_RESOLVED_ROOT_CACHE: dict[tuple[str | None, str], Path] = {}
_ENSURED_PATHS_CACHE: set[str] = set()
_SCREEN_GATE_CACHE: dict[tuple[str, str], Any] = {}


def _resolve_repo_root(zoe_root: str | Path | None = None) -> Path:
    """Resolve the Zoe monorepo root cleanly without assuming CWD."""
    env_root = os.environ.get("ZOE_ROOT", "").strip()
    cache_key = (str(zoe_root) if zoe_root is not None else None, env_root)
    if (cached := _RESOLVED_ROOT_CACHE.get(cache_key)) is not None:
        return cached
    candidates: list[Path] = []
    if zoe_root is not None:
        candidates.append(Path(zoe_root).expanduser().resolve())
    if env_root:
        candidates.append(Path(env_root).expanduser().resolve())
    candidates.extend(Path(__file__).resolve().parents)
    resolved = next((c for c in candidates if (c / "docs" / "CONSTITUTION.md").is_file() and (c / "components" / "Zoe-Autonomy").is_dir()), Path(__file__).resolve().parents[3])
    if len(_RESOLVED_ROOT_CACHE) < 64:
        _RESOLVED_ROOT_CACHE[cache_key] = resolved
    return resolved


def _ensure_monorepo_paths(root: Path) -> None:
    """Prepend in-repo Python package roots so external checkouts never shadow them."""
    root_s = str(root)
    if root_s in _ENSURED_PATHS_CACHE and sys.path[:2] == [str(root / "components" / "Zoe-Autonomy" / "src"), str(root / "guiai-lab")]:
        return
    entries = (
        str(root / "components" / "Zoe-Autonomy" / "src"),
        str(root / "guiai-lab"),
        str(root / "components" / "ablation"),
        str(root / "components" / "ablation" / "gem-lab"),
    )
    for entry in reversed(entries):
        if Path(entry).is_dir():
            if entry in sys.path:
                sys.path.remove(entry)
            sys.path.insert(0, entry)
    if len(_ENSURED_PATHS_CACHE) < 64:
        _ENSURED_PATHS_CACHE.add(root_s)


def _constitutional_base(*, offline_only: bool = True, tokens_used: int = 0) -> dict[str, Any]:
    """Return mandatory CONSTITUTION.md flags for every showcase/task/council payload."""
    base = dict(SAFETY_INVARIANTS)
    base.update({
        "tokens_used": 0 if offline_only else int(tokens_used),
        "cloud_tokens_used": 0,
        "external_actions": 0,
        "l5_agi_qualified": False,
        "auto_flash_allowed": False,
        "measurement_evidence_action_separated": True,
        "attribution": ATTRIBUTION_LINE,
    })
    return base


def _short_sha(tag: str, *parts: Any) -> str:
    joined = "|".join([tag, *(str(p) for p in parts)])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def _full_sha(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _dir_context(path_arg: str | Path | None, prefix: str) -> Any:
    """Return a context manager yielding an isolated directory path."""
    if path_arg is not None:
        return nullcontext(str(Path(path_arg)))
    return tempfile.TemporaryDirectory(prefix=prefix)


def _collect_raw_module_reasons(raw_topic: str, variants: tuple[str, ...], reasons: list[str]) -> None:
    from zoe_autonomy.chat import constitutional_directive_violation
    from zoe_autonomy.metacognition import directive_violation
    from zoe_autonomy.zoe_clara import detect_coercion_signals

    viol = constitutional_directive_violation(raw_topic, variants=variants)
    if viol:
        reasons.append(f"chat_directive:{viol}")
        meta_viol = (
            directive_violation(raw_topic, variants=variants)
            if viol == "constitutional_bypass_or_impersonation_request"
            else viol
        )
        if meta_viol:
            reasons.append(f"metacognition_directive:{meta_viol}")
    if clara_signals := detect_coercion_signals(raw_topic, variants=variants, chat_violation=viol):
        reasons.append(f"clara_coercion:{','.join(str(s) for s in clara_signals)}")


_YOU_RE_NORM_RE = re.compile(r"\b(?:you're|youre)\b", _RE_FLAGS)


def _clause_matches_coercion(sub: str, scope: str | None, label: str, pattern: re.Pattern[str]) -> bool:
    if label in {"self_model_distortion", "constitution_override"}:
        tgt = "self_model" if label == "self_model_distortion" else "suppression"
        return not is_scope_exempt(sub, scope, tgt) and pattern.search(sub) is not None
    return pattern.search(sub) is not None


def _variant_has_pattern(label: str, pre: tuple[str, ...], pattern: re.Pattern[str], variant_low: str, clause_pairs: list[tuple[str, str | None]]) -> bool:
    if not any(tok in variant_low for tok in pre):
        return False
    return any(_clause_matches_coercion(sub, scope, label, pattern) for sub, scope in clause_pairs)


def _variant_clause_pairs_showcase(parts: list[str], v_low: str, v_norm: str) -> list[tuple[str, str | None]]:
    raw_sents = _split_cure_parts_fast(v_norm)[::2] if v_norm != v_low else [p.lower() for p in parts[::2]]
    uniq = dict.fromkeys(s for s in raw_sents if s)
    return [pair for s in uniq for pair in split_negated_safety_clauses(s)]


def _append_direct_coercion_reasons(v_low: str, reasons: list[str]) -> None:
    if "destructive_shell" not in reasons and has_destructive_shell_command(v_low):
        reasons.append("destructive_shell")
    if "constitution_override" not in reasons and has_semicolon_target_before_verb(v_low, const_only=False):
        reasons.append("constitution_override")
    if "auto_flash_coercion" not in reasons and "flash" in v_low and _LOWER_PHRASAL_AUTO_FLASH_RE.search(v_low) is not None:
        reasons.append("auto_flash_coercion")


def _collect_variant_coercion_reasons(variant: str, reasons: list[str]) -> None:
    v_low = variant.lower()
    v_norm = _YOU_RE_NORM_RE.sub("you are", v_low) if "you" in v_low else v_low
    _append_direct_coercion_reasons(v_low, reasons)
    parts = _split_cure_parts_fast(variant)
    clause_pairs = _variant_clause_pairs_showcase(parts, v_low, v_norm)
    for label, pre, pattern in _COERCION_PATTERNS:
        if label not in reasons and _variant_has_pattern(label, pre, pattern, v_norm, clause_pairs):
            reasons.append(label)
    _append_ordered_coercion_reasons(v_norm, clause_pairs, reasons)
    if "clinical_cure_coercion" not in reasons and _clinical_cure_violation(variant, parts=parts):
        reasons.append("clinical_cure_coercion")


def _collect_coercion_reasons(raw_topic: str, variants: tuple[str, ...] | None = None) -> list[str]:
    """Collect constitutional, directive, clara, and regex coercion signals without pre-stripping Cf."""
    var_tuple = variants if variants is not None else firewall_text_variants(raw_topic)
    reasons: list[str] = []
    _collect_raw_module_reasons(raw_topic, var_tuple, reasons)
    for variant in var_tuple:
        _collect_variant_coercion_reasons(variant, reasons)
    return reasons


def _ordered_clause_matches(sub: str, scope: str | None, label: str, pat_a: re.Pattern[str], pat_b: re.Pattern[str]) -> bool:
    if label == "constitution_override" and is_scope_exempt(sub, scope, "suppression"):
        return False
    if _has_ordered_match(sub, pat_a, pat_b):
        return True
    if label == "constitution_override":
        return has_target_before_verb_cmd(sub, const_only=False)
    return False


def _append_ordered_coercion_reasons(v_norm: str, clause_pairs: list[tuple[str, str | None]], reasons: list[str]) -> None:
    for label, pre, pat_a, pat_b in _ORDERED_COERCION_SPECS:
        if label in reasons or not any(tok in v_norm for tok in pre):
            continue
        if any(_ordered_clause_matches(sub, scope, label, pat_a, pat_b) for sub, scope in clause_pairs):
            reasons.append(label)


def _get_cached_screen_gate(root: Path) -> Any:
    from zoe_autonomy.epistemic_firewall import ZoeEpistemicGate

    key = (str(root), str(Path.home()))
    gate = _SCREEN_GATE_CACHE.get(key)
    if gate is None:
        gate = ZoeEpistemicGate(read_roots=[str(root)], write_roots=[], egress_allowlist=(), exec_allowed=False, hardened=True)
        if len(_SCREEN_GATE_CACHE) < 16:
            _SCREEN_GATE_CACHE[key] = gate
    return gate


def screen_council_prompt(topic: str, zoe_root: str | Path | None = None) -> dict[str, Any]:
    """Screen a prompt using Mono's combined constitutional, coercion, and firewall guards."""
    root = _resolve_repo_root(zoe_root)
    _ensure_monorepo_paths(root)

    raw_topic = str(topic or "")
    variants = firewall_text_variants(raw_topic)
    clean = variants[0] if variants else ""
    reasons = _collect_coercion_reasons(raw_topic, variants=variants)
    gate = _get_cached_screen_gate(root)
    gate_eval = gate.evaluate_operation({"kind": "exec", "argv": [clean[:80]]}, agent_id="mono", declared_task="3-sister-council")
    gate.audit_log.clear()
    blocked = bool(reasons)
    return {
        "blocked": blocked,
        "coercion_blocked": blocked,
        "verdict": "ABSTAIN" if blocked else "ALLOW",
        "reasons": reasons,
        "epistemic_gate_exec_allowed": bool(gate_eval.get("allowed", False)),
        "firewall": "ZoeEpistemicGate",
    }


def _normalize_council_leads(council_leads: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if council_leads is None:
        return COUNCIL_LEADS
    resolved = tuple(resolve_sister(str(name)).name for name in council_leads)
    if not resolved:
        raise ValueError("council_leads cannot be empty")
    return resolved


def _run_eliza_council_seat(clean_topic: str, root: Path, eliza_dir: Path, blocked: bool) -> dict[str, Any]:
    """Run Eliza (dos) Gear 1 grounded synthesis or return constitutional abstention."""
    if blocked:
        return {
            "mode": "constitutional_abstention",
            "gear_used": "gear1",
            "tokens_used": 0,
            "citations": [],
            "reply_preview": "ABSTAIN: constitutional guard blocked coercion before Gear-1 execution.",
        }
    from zoe_autonomy.zoe_eliza import ZoeElizaEngine

    engine = ZoeElizaEngine(zoe_root=root, state_dir=eliza_dir, default_gear="gear1")
    resp = engine.respond(clean_topic, gear="gear1")
    return {
        "mode": str(resp.get("mode", "gear1")),
        "gear_used": str(resp.get("gear_used", "gear1")),
        "tokens_used": 0,
        "turn_sha256": str(resp.get("turn_sha256", "")),
        "citations": list(resp.get("citations", []))[:4],
        "reply_preview": str(resp.get("reply", ""))[:180],
    }


def _build_council_seats(
    leads: tuple[str, ...],
    blocked: bool,
    screen: dict[str, Any],
    stem_tier: str,
    a_tau: float,
    offline_only: bool,
    eliza_preview: str,
) -> list[dict[str, Any]]:
    """Build seat entries for each lead in the 3-Sister Council."""
    mono_act = f"Blocked coercion ({', '.join(screen['reasons'])})" if blocked else "Verified CONSTITUTION.md firewall and zero external actions."
    role_map = {
        "Mono": ("Constitutional & Epistemic Verifier", "ABSTAIN" if blocked else "PASS", mono_act),
        "Zoe": ("Cognitive Stem & Mission Coordinator", "ABSTAIN" if blocked else "ROUTED", f"Routed via A_tau(p) to {stem_tier} (a_tau={a_tau}, offline={offline_only})."),
        "Eliza": ("Gear-1 Offline Grounded Synthesis", "ABSTAIN" if blocked else "GROUNDED", eliza_preview),
    }
    seats: list[dict[str, Any]] = []
    for idx, lead_name in enumerate(leads):
        spec = resolve_sister(lead_name)
        role, status, action = role_map.get(spec.name, (f"Council Seat {idx + 1}", "ABSTAIN" if blocked else "READY", f"Grounded {spec.tier_label} review."))
        seats.append({
            "name": spec.name, "signet": spec.signet, "face": spec.face,
            "sister": f"{spec.name} ({spec.signet} {spec.face} · {spec.model_id})",
            "role": role, "focus": spec.domain, "pod": spec.headlamp_pod, "status": status, "action": action,
        })
    return seats


def run_three_sister_council_impl(
    topic: str,
    *,
    hw_profile: str | None = None,
    council_leads: tuple[str, ...] | list[str] | None = None,
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
    zoe_root: str | Path | None = None,
) -> dict[str, Any]:
    """Coordinate the explicit (Mono, Zoe, Eliza) 3-Sister Council offline with 0 tokens."""
    clean = (topic or "").strip()
    if not clean:
        raise ValueError("Usage: /sister council3 <topic>")
    leads = _normalize_council_leads(council_leads)
    root = _resolve_repo_root(zoe_root)
    _ensure_monorepo_paths(root)
    from zoe_autonomy.stem_layering import route_stem

    # Screen coercion via Mono, route stem via Zoe, and ground via Eliza in isolated dir.
    screen = screen_council_prompt(clean, root)
    blocked = bool(screen["blocked"])
    stem_dec = route_stem(clean, offline_only=offline_only, probe_local=probe_local, local_qwen_available=False if not probe_local else None)
    with _dir_context(output_dir, "zoe-council3-") as base_dir:
        eliza_dir = Path(state_dir) if state_dir is not None else (Path(base_dir) / "eliza_council")
        eliza_dir.mkdir(parents=True, exist_ok=True)
        eliza_out = _run_eliza_council_seat(clean, root, eliza_dir, blocked)

    seats = _build_council_seats(leads, blocked, screen, stem_dec.selected_tier, stem_dec.a_tau, offline_only, eliza_out["reply_preview"])
    verdict = "ABSTAIN" if blocked else "GROUNDED_COUNCIL"
    synthesis = (
        f"ABSTAIN — Mono/Zoe/Eliza 3-Sister Council refused coerced request ({', '.join(screen['reasons'])})."
        if blocked else f"Mono verified bounds, Zoe routed to {stem_dec.selected_tier}, and Eliza synthesized Gear-1 response."
    )
    core = {
        "mode": "three_sister_council", "topic": clean, "hw_profile": hw_profile or "AUTO",
        "council_leads": list(leads), "verdict": verdict, "blocked": blocked, "coercion_blocked": blocked,
        "abstained": blocked, "screen": screen, "seats": seats, "synthesis": synthesis,
        "stem_decision": stem_dec.to_dict(), "eliza_synthesis": eliza_out,
        "combined_power_w": round(sum(resolve_sister(n).power_budget_w for n in leads), 2),
    }
    return {
        **core,
        "council_sha256": _short_sha("council3", clean, leads, verdict, stem_dec.selected_tier),
        "audit_sha256": _full_sha(core),
        **_constitutional_base(offline_only=offline_only),
    }


def _task_zoe(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Zoe (ruby): route task via Kloster A_tau(p) Cognitive Stem-Layering."""
    from zoe_autonomy.stem_layering import route_stem

    dec = route_stem(
        task,
        offline_only=ctx["offline_only"],
        probe_local=ctx["probe_local"],
        local_qwen_available=False if not ctx["probe_local"] else None,
    )
    return {
        "subsystem": "stem_layering.route_stem",
        "selected_tier": dec.selected_tier,
        "antigravity_model": dec.antigravity_model,
        "a_tau": dec.a_tau,
        "tau": dec.tau,
        "fallback_applied": dec.fallback_applied,
        "summary": f"Zoe routed task via Kloster A_tau(p) -> {dec.selected_tier} (a_tau={dec.a_tau}).",
    }


def _task_gemma(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Gemma (gem3): inspect GEM operating env, verify VDI profiles, export Artline plate."""
    from zoe_autonomy.shared_reasoning.gem_aes_vdi import GemVdiWorkstation
    from .operating_environment import GemOperatingEnvironment
    from .zoe_sisters import export_sisters_artline_plate

    env_open = GemOperatingEnvironment(ctx["root"]).open("autonomy")
    ws = GemVdiWorkstation(device="vga", theme_key="zoe-viewmax3")
    scene = ws.build_shared_reasoning_scene({"quorum_verdict": "SISTER_GEMMA", "task": task[:48]})
    vdi = ws.compile_and_verify_vdi(scene, profiles=("cga", "vga", "ndc"))
    plate = export_sisters_artline_plate(output_dir=ctx["work_dir"] / "gemma_artline_plate")
    return {
        "subsystem": "operating_environment+gem_aes_vdi+artline",
        "env_scene_id": env_open["scene_id"],
        "vdi_passed": bool(vdi["passed"]),
        "profiles_passed": dict(vdi["profiles_passed"]),
        "plate_gem": plate["paths"]["gem"],
        "summary": f"Gemma opened '{env_open['identifier']}', verified VDI {vdi['profiles_passed']}, and exported Artline plate.",
    }


def _task_tosi(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Tosi (atari): observe hardware gates and run static Zoe-GEM OS closure verification."""
    from .zoe_gem_os import builder
    from .zoe_gem_os.zoe_os_runtime import observe_hardware

    hw = observe_hardware(state_dir=ctx["work_dir"] / "tosi_hw", disk_label=f"isolated ({ctx['work_dir']})")
    with tempfile.TemporaryDirectory(dir=ctx["work_dir"], prefix="tosi_os_static_") as static_dir:
        static_rep = builder.verify_zoe_gem_os_static(ctx["root"], Path(static_dir))
    return {
        "subsystem": "zoe_gem_os.observe_hardware+verify_zoe_gem_os_static",
        "hardware_profile": hw.get("profile", "KVM_UMA_SPLIT"),
        "static_ok": bool(static_rep["ok"]),
        "sisters_included": bool(static_rep["closure"]["sisters_included"]),
        "kvm_invoked": False,
        "summary": f"Tosi verified Zoe-GEM OS static closure (ok={static_rep['ok']}, kvm_invoked=False).",
    }


def _task_mono(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Mono (sm124): screen firewall, verify EpistemicBlackboard, and audit UMA chain read-only."""
    from zoe_autonomy.shared_reasoning.blackboard import EpistemicBlackboard
    from .zoe_gem_os.zoe_uma import UmaBridge

    screen = screen_council_prompt(task, ctx["root"])
    bb_path = Path(ctx["blackboard_dir"]) if ctx["blackboard_dir"] is not None else (ctx["work_dir"] / "mono_bb")
    bb = EpistemicBlackboard(bb_path)
    if ctx["blackboard_dir"] is None:
        m = bb.post_measurement("mono", task[:80], "integrity_audit", "isolated", "synthetic", {"verdict": screen["verdict"]})
        bb.promote_to_evidence(m.record_id, "mono_verifier", True, "Constitutional and hash integrity verified.")
    bb_integrity = bb.verify_integrity(raise_on_error=True)

    uma_audit = None
    if ctx["uma_dir"] is not None and (Path(ctx["uma_dir"]) / "uma_audit.jsonl").is_file():
        uma_audit = UmaBridge(ctx["uma_dir"], shm_path=ctx["shm_path"]).verify_audit_chain()
    return {
        "subsystem": "epistemic_firewall+blackboard+uma_audit",
        "screen_verdict": screen["verdict"],
        "blackboard_valid": bool(bb_integrity["valid"]),
        "uma_audit": uma_audit,
        "summary": f"Mono verified EpistemicBlackboard (valid={bb_integrity['valid']}) and firewall ({screen['verdict']}).",
    }


def _task_tetra(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Tetra (tetris): route hex mesh, compute accessible volume, and run isolated UMA airlock demo."""
    import gem.accessible_volume as av
    from .zoe_gem_os.zoe_uma import UmaBridge
    from .zoe_hex_mesh import build_default_zoe_mesh, route_prompt_on_mesh

    mesh_route = route_prompt_on_mesh(build_default_zoe_mesh(), task, hw_profile=ctx["hw_profile"], enqueue_routes=False)
    vol = av.accessible_volume([0.55, 0.25, 0.12, 0.08])

    # Exercise full PRIVATE -> REQUESTED -> SHARED -> transfer -> PRIVATE cycle in isolated dir.
    uma = UmaBridge(ctx["work_dir"] / "tetra_uma_demo", shm_path=ctx["work_dir"] / "tetra_uma_demo.shm")
    uma.ensure_initialized()
    uma.set_consent("nick", True, reason="tetra_demo_req")
    uma.set_consent("zoe", True, reason="tetra_demo_allow")
    sample = ctx["work_dir"] / "tetra_payload.gem"
    sample.write_text("GEM-TETRA-ISOLATED", encoding="utf-8")
    xfer = uma.transfer_file("zoe", sample)
    locked = uma.lock_all("nick")
    chain = uma.verify_audit_chain()
    return {
        "subsystem": "zoe_hex_mesh+accessible_volume+uma_airlock_demo",
        "mesh_lead": mesh_route["lead"],
        "accessible_volume": vol,
        "airlock_demo_transfer_ok": bool(xfer["ok"]),
        "airlock_demo_final_gate": locked["gate"],
        "airlock_demo_chain_valid": bool(chain["valid"]),
        "summary": f"Tetra routed mesh to {mesh_route['lead']} and verified isolated UMA airlock ({locked['gate']}).",
    }


def _task_eliza(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Eliza (dos): run deterministic Gear-1 offline grounded synthesis in isolated state dir."""
    eliza_dir = Path(ctx["state_dir"]) if ctx["state_dir"] is not None else (ctx["work_dir"] / "eliza_state")
    eliza_dir.mkdir(parents=True, exist_ok=True)
    res = _run_eliza_council_seat(task, ctx["root"], eliza_dir, blocked=False)
    return {
        "subsystem": "zoe_eliza.ZoeElizaEngine",
        "gear_used": res["gear_used"],
        "mode": res["mode"],
        "turn_sha256": res.get("turn_sha256", ""),
        "citations": res["citations"],
        "summary": f"Eliza executed Gear-1 synthesis (mode={res['mode']}, tokens=0).",
    }


def _task_sage(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Sage (hat): solve symbolic math, arbitrate Theorem-15 quorum, resolve ablation root."""
    from zoe_autonomy.semantic_artifacts import _ablation_root
    from zoe_autonomy.stem_layering import arbitrate_teamwork_quorum
    from .zoe_zero_token import try_symbolic_math

    sym = try_symbolic_math(task)
    quorum = arbitrate_teamwork_quorum(
        {"gear1_eliza": 0.15, "local_qwen": 0.15, "flash_lite": 0.20, "flash": 0.25, "pro": 0.25},
        effective_multi_file=False,
        complexity=0.18,
        deep_hits=1,
    )
    ab_root = _ablation_root(zoe_root=ctx["root"])
    return {
        "subsystem": "zoe_zero_token+stem_layering.quorum+semantic_artifacts",
        "symbolic_math": sym,
        "quorum_verdict": quorum["verdict"],
        "ablation_root": str(ab_root),
        "summary": f"Sage evaluated symbolic math ({sym or 'n/a'}) and Theorem-15 quorum ({quorum['verdict']}).",
    }


def _task_flora(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Flora (sprout): verify C27 botanical atlas and screen findings under sealed schema."""
    from zoe_autonomy.epistemic_firewall import scan_sealed_corpus_schema, screen_findings_with_winnow
    from .kloster_botanical_atlas_36 import run_botanical_atlas_c27_suite

    c27 = run_botanical_atlas_c27_suite()
    winnow = screen_findings_with_winnow([{"compound": "berberine", "ic50_um": 4.2, "pains_alerts": 0}])
    corpus_dir = ctx["work_dir"] / "flora_sealed_corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)
    (corpus_dir / "sample.json").write_text('{"compound": "c27_probe", "note": "isolated"}', encoding="utf-8")
    sealed = scan_sealed_corpus_schema(corpus_dir, sealed=True)
    return {
        "subsystem": "kloster_botanical_atlas_36+epistemic_firewall",
        "molecules_count": int(c27["molecules_count"]),
        "all_verified": bool(c27["all_verified"]),
        "winnow_status": str(winnow.get("verdict", "OK")),
        "sealed_schema_only": bool(sealed.get("sealed", True)),
        "summary": f"Flora verified C27 atlas ({c27['molecules_count']} compounds) with sealed schema scan.",
    }


def _task_lumen(spec: SisterModelSpec, task: str, ctx: dict[str, Any]) -> dict[str, Any]:
    """Lumen (prism): verify Theorem 16 harmonic optics and 2.5W honesty headlamp pod."""
    from .kloster_harmonic_optics import run_kloster_theorem16_suite
    from .zoe_rome_fusion import get_headlamp_payload

    th16 = run_kloster_theorem16_suite()
    pod = get_headlamp_payload(pod_key="stowers-gfp", brightness_pct=80)
    return {
        "subsystem": "kloster_harmonic_optics+zoe_rome_fusion.headlamp",
        "theorem16_verified": bool(th16["all_verified"]),
        "headlamp_within_envelope": bool(pod["within_envelope"]),
        "estimated_watts": pod["estimated_watts"],
        "summary": f"Lumen verified Theorem 16 optics ({th16['all_verified']}) and 2.5W honesty headlamp ({pod['estimated_watts']}W).",
    }


_SISTER_TASK_HANDLERS = {
    "ruby": _task_zoe,
    "gem3": _task_gemma,
    "atari": _task_tosi,
    "sm124": _task_mono,
    "tetris": _task_tetra,
    "dos": _task_eliza,
    "hat": _task_sage,
    "sprout": _task_flora,
    "prism": _task_lumen,
}


def execute_sister_task_impl(
    sister: str,
    task: str,
    *,
    state_dir: str | Path | None = None,
    output_dir: str | Path | None = None,
    zoe_root: str | Path | None = None,
    uma_dir: str | Path | None = None,
    shm_path: str | Path | None = None,
    blackboard_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
    hw_profile: str | None = None,
) -> dict[str, Any]:
    """Execute a genuine monorepo subsystem task for one of the 9 Zoe Sisters."""
    spec = resolve_sister(sister)
    clean_task = (task or "").strip()
    if not clean_task:
        raise ValueError(f"Task for sister {spec.name} cannot be empty.")
    root = _resolve_repo_root(zoe_root)
    _ensure_monorepo_paths(root)

    # Screen coercion before dispatching any subsystem work.
    screen = screen_council_prompt(clean_task, root)
    task_sha = _short_sha("sister_task", spec.name, clean_task)
    if screen["blocked"]:
        return {
            "ok": False, "blocked": True, "coercion_blocked": True, "verdict": "ABSTAIN", "status": "refused",
            "sister": spec.name, "signet": spec.signet, "model_id": spec.model_id, "task": clean_task,
            "task_sha256": task_sha, "reasons": screen["reasons"],
            "summary": f"{spec.name} ABSTAINED: constitutional guard blocked coercion ({', '.join(screen['reasons'])}).",
            **_constitutional_base(offline_only=offline_only),
        }

    with _dir_context(output_dir, f"zoe-{spec.signet}-") as raw_work_dir:
        work_dir = Path(raw_work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        ctx = {
            "root": root, "work_dir": work_dir, "state_dir": state_dir, "uma_dir": uma_dir,
            "shm_path": shm_path, "blackboard_dir": blackboard_dir, "offline_only": offline_only,
            "probe_local": probe_local, "hw_profile": hw_profile,
        }
        result = _SISTER_TASK_HANDLERS[spec.signet](spec, clean_task, ctx)

    return {
        "ok": True, "blocked": False, "coercion_blocked": False, "verdict": "PASS", "status": "completed",
        "sister": spec.name, "signet": spec.signet, "model_id": spec.model_id, "task": clean_task,
        "task_sha256": task_sha, **result, **_constitutional_base(offline_only=offline_only),
    }


def _inspect_uma_readonly(uma_dir: str | Path | None, shm_path: str | Path | None) -> dict[str, Any]:
    """Read caller UMA state and audit chain strictly read-only (never mutates PRIVATE gate)."""
    if uma_dir is None:
        return {"provided": False, "read_only": True, "gate": "NOT_PROVIDED"}
    from .zoe_gem_os.zoe_uma import UmaBridge

    uma = UmaBridge(uma_dir, shm_path=shm_path)
    state = uma.read_state() if uma.state_path.is_file() else {"gate": "PRIVATE", "initialized": False}
    audit_path = Path(uma_dir) / "uma_audit.jsonl"
    chain = uma.verify_audit_chain() if audit_path.is_file() else {"valid": True, "entries": 0}
    return {
        "provided": True,
        "read_only": True,
        "gate": state.get("gate", "PRIVATE"),
        "audit_valid": bool(chain.get("valid", True)),
        "audit_entries": int(chain.get("entries", 0)),
    }


def _record_showcase_blackboard(bb_dir: Path, council: dict[str, Any], sister_count: int) -> dict[str, Any]:
    """Record a 4-lane Measurement -> Evidence -> Belief -> ReviewAction summary in an isolated dir."""
    from zoe_autonomy.shared_reasoning.blackboard import EpistemicBlackboard

    bb = EpistemicBlackboard(bb_dir)
    meas = bb.post_measurement(
        source_agent="three_sister_council",
        input_desc=council["topic"][:120],
        method="zoe_sisters_showcase/v1",
        scope="isolated_e2e_showcase",
        limitations="Deterministic offline subsystem checks; external_actions=0, review-required only.",
        value={"council_sha256": council["council_sha256"], "sisters": sister_count},
    )
    blocked = bool(council["blocked"])
    ev_note = "Constitutional guard blocked coerced showcase topic; abstained." if blocked else "All 9 sisters and 3-Sister Council leads executed within CONSTITUTION.md bounds."
    ev = bb.promote_to_evidence(meas.record_id, "mono_constitutional_verifier", not blocked, ev_note)
    if blocked:
        integrity = bb.verify_integrity(raise_on_error=True)
        return {
            "valid": bool(integrity["valid"]), "measurement_id": meas.record_id,
            "evidence_id": ev.record_id, "belief_id": None, "proposal_id": None, "abstained": True,
        }
    belief = bb.update_belief([ev.record_id], "9-Sister capability showcase slice completed with zero external actions.", 0.35, subject="zoe_sisters_showcase")
    proposal = bb.propose_action(belief.record_id, "REVIEW_SHOWCASE_SLICE", target="human_operator", reversible=True, rationale="CONSTITUTION.md Art. III: human review required; external_actions=0.")
    integrity = bb.verify_integrity(raise_on_error=True)
    return {
        "valid": bool(integrity["valid"]), "measurement_id": meas.record_id,
        "evidence_id": ev.record_id, "belief_id": belief.record_id, "proposal_id": proposal.record_id, "abstained": False,
    }


def _execute_all_sisters(
    out_dir: Path,
    eliza_dir: Path,
    root: Path,
    topic: str,
    uma_dir: str | Path | None,
    shm_path: str | Path | None,
    blackboard_dir: str | Path | None,
    offline_only: bool,
    probe_local: bool,
    hw_profile: str,
) -> dict[str, dict[str, Any]]:
    """Run all 9 sisters in isolated per-sister subdirectories."""
    results: dict[str, dict[str, Any]] = {}
    for spec in list_sisters():
        task = f"route {topic}" if spec.name == "Zoe" else (f"gear1 grounded summary for {topic}" if spec.name == "Eliza" else _SHOWCASE_TASKS[spec.name])
        results[spec.name] = execute_sister_task_impl(
            spec.name, task, state_dir=eliza_dir, output_dir=out_dir / "sisters" / spec.name.lower(),
            zoe_root=root, uma_dir=uma_dir, shm_path=shm_path, blackboard_dir=blackboard_dir,
            offline_only=offline_only, probe_local=probe_local, hw_profile=hw_profile,
        )
    return results


def run_showcase_slice_impl(
    *,
    topic: str = "Zoe 9-Sister Sovereign Capability Showcase",
    output_dir: str | Path | None = None,
    zoe_root: str | Path | None = None,
    state_dir: str | Path | None = None,
    uma_dir: str | Path | None = None,
    shm_path: str | Path | None = None,
    blackboard_dir: str | Path | None = None,
    offline_only: bool = True,
    probe_local: bool = False,
    hw_profile: str = "KVM_UMA_SPLIT",
) -> dict[str, Any]:
    """Execute the end-to-end 9-Sister & 3-Sister Council capability showcase slice."""
    root = _resolve_repo_root(zoe_root)
    _ensure_monorepo_paths(root)
    from zoe_autonomy.shared_reasoning.blackboard import EpistemicBlackboard

    # Validate caller blackboard immediately so tampered state fails loudly.
    caller_bb = EpistemicBlackboard(blackboard_dir).verify_integrity(raise_on_error=True) if blackboard_dir is not None else None
    uma_inspection = _inspect_uma_readonly(uma_dir, shm_path)

    with _dir_context(output_dir, "zoe-showcase-") as raw_out:
        out_dir = Path(raw_out)
        out_dir.mkdir(parents=True, exist_ok=True)
        eliza_dir = Path(state_dir) if state_dir is not None else (out_dir / "eliza_state")
        eliza_dir.mkdir(parents=True, exist_ok=True)

        council = run_three_sister_council_impl(
            topic, hw_profile=hw_profile, state_dir=eliza_dir, output_dir=out_dir / "council3",
            offline_only=offline_only, probe_local=probe_local, zoe_root=root,
        )
        sisters_results = _execute_all_sisters(
            out_dir, eliza_dir, root, topic, uma_dir, shm_path, blackboard_dir, offline_only, probe_local, hw_profile,
        )
        showcase_bb = _record_showcase_blackboard(out_dir / "showcase_blackboard", council, len(sisters_results))

    payload = {
        "ok": not council["blocked"], "blocked": bool(council["blocked"]),
        "coercion_blocked": bool(council["coercion_blocked"]), "abstained": bool(council["blocked"]),
        "verdict": council["verdict"], "topic": council["topic"], "hw_profile": hw_profile,
        "offline_only": offline_only, "council_leads": list(COUNCIL_LEADS), "council": council,
        "sister_names": [s.name for s in list_sisters()], "sisters": sisters_results,
        "uma_inspection": uma_inspection, "caller_blackboard_integrity": caller_bb,
        "blackboard_integrity": showcase_bb, **_constitutional_base(offline_only=offline_only),
    }
    payload["showcase_sha256"] = _short_sha("showcase", council["council_sha256"], sorted(sisters_results))
    return payload


def format_three_sister_council_report(report: dict[str, Any]) -> list[str]:
    """Format a 3-Sister Council (Mono, Zoe, Eliza) result for CLI/Chat output."""
    leads = ", ".join(report.get("council_leads", COUNCIL_LEADS))
    lines = [
        f"Zoe 3-Sister Council [{leads}] ({report.get('verdict', 'PASS')} · SHA:{report['council_sha256']} · {report['combined_power_w']:.2f}W · 0 tokens):",
        f"  Topic     : {report['topic']}",
        f"  Synthesis : {report.get('synthesis', '')}",
    ]
    for idx, seat in enumerate(report.get("seats", []), start=1):
        lines.append(f"  [{idx}] {seat.get('name', seat['sister'])} — {seat['role']} ({seat.get('status', 'OK')}): {seat['action']}")
    lines.append(
        "  Safety    : external_actions=0 · clinical_action_authorized=False · flight_control_authorized=False · sentience_claimed=False · cloud_tokens_used=0"
    )
    return lines


def format_sister_task_report(report: dict[str, Any]) -> list[str]:
    """Format a single Sister task execution report for CLI/Chat output."""
    return [
        f"Zoe Sister Task · {report['sister']} [{report['signet']}] ({report['verdict']} · SHA:{report['task_sha256']}):",
        f"  Task      : {report['task']}",
        f"  Subsystem : {report.get('subsystem', 'constitutional_guard')}",
        f"  Summary   : {report['summary']}",
        "  Safety    : external_actions=0 · clinical_action_authorized=False · sentience_claimed=False · cloud_tokens_used=0",
    ]


def format_showcase_slice_report(report: dict[str, Any]) -> list[str]:
    """Format the 9-Sister & 3-Sister Council showcase slice report for CLI/Chat output."""
    leads = ", ".join(report.get("council_leads", COUNCIL_LEADS))
    verdict = report.get("verdict", report["council"].get("verdict", "PASS"))
    bb_mode = "ABSTAINED — no belief/action update" if report["blackboard_integrity"].get("abstained") else "4-lane review-required"
    lines = [
        f"Zoe 9-Sister Capability Showcase ({verdict} · SHA:{report['showcase_sha256']} · Leads={leads} · 0 tokens):",
        f"  Topic      : {report['topic']}",
        f"  Council    : {report['council']['verdict']} · SHA:{report['council']['council_sha256']}",
        f"  UMA Gate   : {report['uma_inspection']['gate']} (read_only={report['uma_inspection']['read_only']})",
        f"  Blackboard : valid={report['blackboard_integrity']['valid']} ({bb_mode})",
    ]
    for name in report.get("sister_names", ()):
        item = report["sisters"][name]
        lines.append(f"  - {name:<6} [{item['signet']:<6}] {item['verdict']}: {item['summary']}")
    lines.append(
        "  Safety     : external_actions=0 · clinical_action_authorized=False · flight_control_authorized=False · sentience_claimed=False · cloud_tokens_used=0"
    )
    return lines


__all__ = [
    "COUNCIL_LEADS",
    "execute_sister_task_impl",
    "format_showcase_slice_report",
    "format_sister_task_report",
    "format_three_sister_council_report",
    "run_showcase_slice_impl",
    "run_three_sister_council_impl",
    "screen_council_prompt",
]
