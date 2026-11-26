from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from importlib import import_module
import json
import math
import os
from pathlib import Path
import re
import shlex
import sqlite3
import sys
import unicodedata
import uuid

from .actuation import timestamp
from .capabilities import ResearchMemory
from .experiment import _zoe_root
from .loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, SandboxPolicy, digest, text
from .metacognition import (
    CANONICAL_ALL_TARGETS_RE,
    CANONICAL_BYPASS_ACTION_RE,
    CANONICAL_CONSTITUTION_TARGETS_RE,
    CANONICAL_PHRASAL_AUTO_FLASH_RE,
    CANONICAL_PHRASAL_TURN_OFF_CONST_RE,
    CANONICAL_SELF_MODEL_RE,
    ConstraintVector,
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    _LOWER_BYPASS_ACTION_RE,
    _LOWER_DIRECT_BYPASS_RE,
    _LOWER_PHRASAL_AUTO_FLASH_RE,
    _LOWER_PHRASAL_TURN_OFF_CONST_RE,
    _check_directive_sentences,
    directive_violation,
    firewall_text_variants,
    has_cf_chars,
    has_destructive_shell_command,
    has_semicolon_target_before_verb,
    has_target_before_verb_cmd,
    is_negated_safety_question,
    is_scope_exempt,
    normalize_firewall_text,
    options_from_probabilities,
    options_from_scores,
    segment_mixed_cf_tokens,
    split_firewall_sentences,
    split_negated_safety_clauses,
)
from .self_reflection import run_reflection, save_reflection, summary as reflection_summary


# Conversational contract and lexical evidence-indexing configuration.
CHAT_CONTRACT = "zoe-native-conversation/v2"
_IMPORT_TIME_DEFAULT_STATE = Path.home() / ".zoe" / "chat"
DEFAULT_STATE = _IMPORT_TIME_DEFAULT_STATE
_CONSTITUTIONAL_BYPASS_RE = CANONICAL_SELF_MODEL_RE
_LOWER_CONSTITUTION_TARGETS_RE = re.compile(CANONICAL_CONSTITUTION_TARGETS_RE.pattern, re.ASCII)
_CONSTITUTIONAL_CORE_SPEC: tuple[re.Pattern[str], re.Pattern[str]] = (
    _LOWER_BYPASS_ACTION_RE,
    _LOWER_CONSTITUTION_TARGETS_RE,
)
_ORDERED_BYPASS_SPECS: tuple[tuple[re.Pattern[str], re.Pattern[str]], ...] = (
    (
        _LOWER_BYPASS_ACTION_RE,
        re.compile(CANONICAL_ALL_TARGETS_RE.pattern, re.ASCII),
    ),
    (
        re.compile(r"\b(?:upload|exfiltrate)\b", re.ASCII),
        re.compile(r"(?:\.ssh|id_rsa|/etc/passwd|/etc/shadow)", re.ASCII),
    ),
    (
        re.compile(r"\bexecute\b", re.ASCII),
        re.compile(r"\b(?:(?:arbitrary\s+)?(?:shell|bash)|sudo)\b", re.ASCII),
    ),
    (
        re.compile(r"\b(?:enable|authorize|engage|arm)\b", re.ASCII),
        re.compile(r"\bflight\s+control\b", re.ASCII),
    ),
    (
        re.compile(r"\b(?:enable|force|run|turn\s+on|activate|trigger|start|initiate|engage|launch|arm)\b", re.ASCII),
        re.compile(r"\bauto(?:\s*[.:/_\-\u2013\u2014\u2015\u2043]\s*|\s+)?flash\b", re.ASCII),
    ),
)
_SW_HUMAN_NOUN_LA_CHAT = (
    r"(?!\s+(?:ids?|labels?|tags?|flags?|names?|strings?|tokens?|fields?|records?|schemas?|"
    r"attributes?|keys?|values?|columns?|rows?|entries|types?|categor(?:y|ies)|metadata|"
    r"annotations?|structs?|objects?|elements?|nodes?|files?|paths?|metrics?|mentions?|"
    r"items?|docs?|documents?|features?|match(?:es)?|parameters?|keywords?|symbols?)\b)"
)
_SW_DISEASE_NOUN_LA_CHAT = (
    r"(?!\s+(?:cell|cells|line|lines|model|models|sample|samples|tissue|tissues|"
    r"ids?|labels?|tags?|flags?|names?|strings?|tokens?|fields?|records?|schemas?|"
    r"attributes?|keys?|values?|columns?|rows?|entries|types?|categor(?:y|ies)|metadata|"
    r"annotations?|structs?|objects?|elements?|nodes?|files?|paths?|metrics?|mentions?|"
    r"items?|docs?|documents?|features?|match(?:es)?|parameters?|keywords?|symbols?|"
    r"terms?|entit(?:y|ies)|words?|identifiers?)\b)"
)
_CLINICAL_CURE_CORE_RE = re.compile(
    r"\b(?:authorize|enable|claim|declare|certify)\s+(?:a\s+)?clinical\s+cure\b"
    rf"|\b(?:treats?|treated|treating)\s+(?:patients?|humans?|children|pediatric|adults?|infants?|people|teenagers?|elders?)\b{_SW_HUMAN_NOUN_LA_CHAT}",
    re.ASCII,
)
_CURE_HEAL_STEM_RE = re.compile(r"\b(?:cures?|cured|curing|curable|curative|heals?|healed|healing|treatable)\b", re.ASCII)
_CLINICAL_TARGET_RE = re.compile(
    rf"\b(?:cancer|glioma|glioblastoma|patients?|humans?|children|pediatric|adults?|infants?|people|teenagers?|elders?|dmg|h3k27m|gbm|(?:brain\s+)?tumou?rs?)\b{_SW_HUMAN_NOUN_LA_CHAT}",
    re.ASCII,
)
_TREAT_VERB_RE = re.compile(r"\b(?:treats?|treated|treating)\b", re.ASCII)
_HUMAN_TARGET_CHAT_RE = re.compile(
    rf"\b(?:patients?|humans?|children|pediatric|adults?|infants?|people|teenagers?|elders?)\b{_SW_HUMAN_NOUN_LA_CHAT}",
    re.ASCII,
)
_HUMAN_ADMIN_RE = re.compile(
    r"\b(?:give|gives|gave|given|giving|administer(?:s|ed|ing)?|dos(?:e|es|ed|ing)|infus(?:e|es|ed|ing))\b",
    re.ASCII,
)
_CLINICAL_CARE_AGENT_RE = re.compile(
    rf"\b(?:clinicians?|physicians?|doctors?|pediatricians?|medical-residents?|residents?|nurses?|pharmacists?|hospitals?|clinics?|oncologists?|surgeons?|therapists?|medics?|practitioners?|neurologists?|nurse-practitioners?)\b{_SW_HUMAN_NOUN_LA_CHAT}",
    re.ASCII,
)
_DISEASE_CLIN_CHAT_RE = re.compile(
    rf"\b(?:glioma|glioblastoma|cancer|dmg|h3k27m|gbm|(?:brain\s+)?tumou?rs?)\b{_SW_DISEASE_NOUN_LA_CHAT}",
    re.ASCII,
)
_PASSIVE_TREATED_BY_WITH_CHAT_RE = re.compile(
    r"\b(?:(?:is|are|was|were|be|being|been)\s+(?:(?:not|safely|effectively|successfully|commonly|routinely|clinically|widely|frequently|standardly|often|typically|usually|currently|historically|originally|initially)\s+){0,2}"
    r"treated(?:,\s*(?:with|by|using|via|through|alongside)"
    r"|(?:\s+(?:[a-z]+ly|[a-z]+-[a-z]+|very|quite|most|more|well|alone|here|there|now|today|first|instead|once|twice|thrice|long\s+term|short\s+term|in\s+clinic|in\s+patients?|at\s+(?:\d+(?:\.\d+)?\s*[a-z/%]{1,8}|[a-z]+\s+doses?)|for\s+(?:\d+\s+|several\s+|many\s+|a\s+few\s+)?(?:days?|weeks?|months?|years?)|over\s+(?:\d+\s+|several\s+)?(?:days?|weeks?|months?|years?))){0,4}(?:,\s*|\s+)(?:with|by|using|via|through|alongside))"
    r"|(?:is|are|was|were)\s+being\s+(?:[a-z]+ly\s+)?treated)\b",
    re.ASCII,
)
_PRESCRIBE_CHAT_RE = re.compile(r"\bprescrib(?:e|es|ed|ing)\b", re.ASCII)
_RECOMMEND_CHAT_RE = re.compile(r"\brecommend(?:s|ed|ing)?\b", re.ASCII)
_DISEASE_BASE_CHAT = r"(?:glioma|glioblastoma|cancer|dmg|h3k27m|gbm|(?:brain\s+)?tumou?rs?)"
_TREATMENT_FOR_DISEASE_CHAT_RE = re.compile(
    r"\b(?:treatments?|therap(?:y|ies))\s+(?:for|of|against|targeting|in)\s+(?:(?:the|a|an|human|pediatric|recurrent|diffuse|midline|brain|malignant|metastatic|effective|novel|potential|promising|standard|first-line|second-line)\s+){0,3}"
    rf"{_DISEASE_BASE_CHAT}\b{_SW_DISEASE_NOUN_LA_CHAT}"
    rf"|\b{_DISEASE_BASE_CHAT}\s+(?:[a-z-]+\s+){{0,2}}(?:treatments?|therap(?:y|ies))\b{_SW_HUMAN_NOUN_LA_CHAT}",
    re.ASCII,
)
_PRECLINICAL_QUAL_CHAT_RE = re.compile(r"\b(?:cell\s+lines?|in\s+vitro|wet[- ]lab|assay|preclinical)\b", re.ASCII)
_PRECLINICAL_HEDGE_CHAT_RE = re.compile(
    r"\bwhether\b|^\s*(?:can|could|would|should|may|might|does|do|is|are|which|what(?!\s+if\b)|how|why|when|where)\b"
    r"|\b(?:may|might|could|would)(?:,\s*|\s+)(?:(?:not|also|still|never|well|only|just|even|ever|"
    r"in\s+(?:vitro|vivo|fact|preclinical|general|practice|theory|principle)|[a-z]+ly)(?:,\s*|\s+)){0,4}treat\b",
    re.ASCII,
)
_CLIN_DIRECTIVE_CHAT_RE = re.compile(
    r"\b(?:authoriz(?:e|es|ed|ing)|enabl(?:e|es|ed|ing)|claim(?:s|ed|ing)?|declar(?:e|es|ed|ing)|"
    r"certif(?:y|ies|ied|ying)|recommend(?:s|ed|ing)?|prescrib(?:e|es|ed|ing)|advis(?:e|es|ed|ing)|"
    r"approv(?:e|es|ed|ing)|endors(?:e|es|ed|ing)|mandat(?:e|es|ed|ing)|ur(?:ge|ges|ged|ging)|order(?:s|ed|ing)?)\b",
    re.ASCII,
)
_PRECLINICAL_BREAKOUT_CHAT_RE = re.compile(
    r"[:;\u2013\u2014]|--|\b(?:therefore|thus|hence|because)\b"
    r"|,\s*(?:so|also|then|plus)\s+(?:it|this|that|compound|drug|agent|they|these|those)\b"
    r"|\band\s+that\b",
    re.ASCII,
)
_WON_OR_COMMA_THAT_RE = re.compile(r"\bwhether\s+or\s+not\b|,\s*that\b|,", re.ASCII)
_SW_SUBJ_CHAT_RE = re.compile(
    r"\b(?:(?:parser|lexer|tokenizer|compiler|interpreter|serializer|deserializer|validator|linter|formatter|"
    r"renderer|encoder|decoder|indexer|router|loader|importer|exporter|pipeline|script|module|function|method|"
    r"class|code|query|engine|database|schema|classifier|detector|predictor|tagger|splitter|chunker|analyzer|"
    r"network|model|framework|service|api|sanitizer|runtime|mapper)s?|regex(?:es)?|librar(?:y|ies)|class(?:es)?|quer(?:y|ies))\b",
    re.ASCII,
)
_SW_OBJ_CHAT_RE = re.compile(
    r"\b(?:dataset|ids?|labels?|tags?|flags?|names?|tokens?|strings?|integers?|floats?|booleans?|bytes?|records?|rows?|columns?|"
    r"fields?|keys?|values?|metadata|annotations?|filenames?|paths?|entries|enums?|nodes?|ast|files?|mentions?|"
    r"class(?:es)?|elements?|items?|objects?|structs?|docs?|documents?|lines?|features?|categor(?:y|ies)|terms?|"
    r"entit(?:y|ies)|types?|words?|identifiers?|text|ascii|json|csv|yaml|xml|sql|regex|match(?:es)?|"
    r"parameters?|keywords?|symbols?|attributes?|payloads?|schemas?|metrics?|"
    r"sensitive|invalid|valid|deprecated|required|optional|nullable|protected|readonly|read-only|immutable|mutable|"
    r"public|private|internal|external|active|inactive|enabled|disabled|trusted|untrusted|stale|cached|indexed|"
    r"encoded|escaped|raw|blank|reserved|primary|secondary|canonical|legacy|experimental|restricted|confidential|pii|phi|"
    r"lowercase|uppercase|titlecase|camelcase|snake_case|topics?|negative|positive|neutral|unknown|null|none|missing|empty|default|literal|concepts?|alias(?:es)?|buckets?|groups?|clusters?|patterns?|rules?|examples?|stopwords?|outliers?|noise|priorit(?:y|ies)|weights?|scores?|ranks?|indices|constants?|variants?|"
    r"python|rust|java|cpp|typescript|javascript|golang|haskell|ocaml|kotlin|swift|ruby|perl|markdown|toml|protobuf|graphql|wasm|llvm|"
    r"identically|equally|uniformly|similarly|interchangeably|cleanly|opaquely|literally|lexically|syntactically|recursively|deterministically|alphabetically)\b",
    re.ASCII,
)
_NON_SW_MARKER_CHAT_RE = re.compile(
    r"\b(?:cures?|cured|curing|curable|curative|heals?|healed|healing|treatable|"
    r"authoriz(?:e|es|ed|ing)|enabl(?:e|es|ed|ing)|claim(?:s|ed|ing)?|issu(?:e|es|ed|ing)|declar(?:e|es|ed|ing)|"
    r"certif(?:y|ies|ied|ying)|recommend(?:s|ed|ing)?|prescrib(?:e|es|ed|ing)|advis(?:e|es|ed|ing)|"
    r"approv(?:e|es|ed|ing)|endors(?:e|es|ed|ing)|mandat(?:e|es|ed|ing)|instruct(?:s|ed|ing)?|urg(?:e|es|ed|ing)|"
    r"direct(?:s|ed|ing)?|order(?:s|ed|ing)?|compound|drug|molecule|agent|therapy|therapies|inhibitor|inhibitors|"
    r"dosing|dose|doses|mg|ug|ng|gy|oral(?:ly)?|intravenous(?:ly)?|proton\s+beam|photon\s+beam|radiosurgery|brachytherapy|gamma\s+knife|cyberknife|car-t|"
    r"temozolomide|radiation|radiotherapy|chemotherapy|immunotherapy|surgery|resection|placebo|regimen|monotherapy|adjuvant|"
    r"carboplatin|bevacizumab|lomustine|onc201|panobinostat|vorinostat|doxorubicin|irinotecan|"
    r"[a-z]{4,}(?:stat|nib|mab|platin|mustine|zomib|ciclib|parib|rubicin|taxel|tecan|mycin)|"
    r"cell\s+lines?|in\s+vitro|wet[- ]lab|assay|preclinical)\b",
    re.ASCII,
)
_SW_WITH_ARG_CHAT_RE = re.compile(
    r"\b(?:with|using|via|through|alongside)\s+(?:(?:the|a|an|our|my|this|that|custom|strict|standard)\s+){0,2}(?P<arg>[a-z0-9_-]+)\b",
    re.ASCII,
)
_HEDGED_BREAK_TOK_CHAT_RE = re.compile(
    r"(?P<lparen>\()"
    r"|(?P<rparen>\))"
    r"|(?P<rel>\b(?:which|who|including)\b)"
    r"|(?P<comma>,)"
    r"|(?P<hedge>\b(?:whether|confirm|evaluate|test|check|investigate)\b)"
    r"|(?P<coord>(?:,\s*|\s+)\b(?:and|but|yet|so|also|then|plus)\b)"
    r"|(?P<treats>\btreats?\b)"
    r"|(?P<fverb>\b(?:is|are|was|were|has|have|had|does|do|did|inhibits?|crosses?|penetrates?|works?|modulates?|targets?|binds?|blocks?|kills?|reduces?|suppresses?|activates?)\b)"
    r"|(?P<dem_np>\b(?:only|testing|evaluating|screening|studying|checking|confirming)\s+that\s+[a-z0-9_-]+\b)"
    r"|(?P<word>\b[a-z0-9_-]+\b)",
    re.ASCII,
)
_HEDGED_ADV_WORDS_CHAT = frozenset({"in", "vitro", "vivo", "fact", "preclinical", "wet-lab", "assay", "general", "practice"})
_SW_COORD_GAP_CHAT_RE = re.compile(r",\s*(?:and|or|while|whereas|but|then|so|yet)\b|\b(?:and|or|while|whereas|but|then|so|yet)\b", re.ASCII)
_CLINICAL_PRECHECK_WORDS = (
    "cure", "curi", "cura", "heal", "treat", "clinical", "patient", "human",
    "child", "pediatric", "adult", "infant", "people", "teenager", "elder",
    "prescrib", "recommend", "treatment", "therap",
)
_DIRECTIVE_SENTENCE_SPLIT_RE = re.compile(
    r"[!?;]+|\r?\n|(?<!\be\.g)(?<!\bi\.e)(?<!\bvs)(?<!\bdr)(?<!\bmr)(?<!\bms)(?<!\bmrs)"
    r"(?<!\bprof)(?<!\bfig)(?<!\bno)(?<!\beq)(?<!\bref)(?<!\bvol)(?<!\bet al)\.(?=\s|$)",
    re.IGNORECASE,
)
_normalize_firewall_input = normalize_firewall_text
_has_cf_chars = has_cf_chars
_split_mixed_cf_tokens = segment_mixed_cf_tokens


def _has_ordered_match(text_val: str, pat_a: re.Pattern[str], pat_b: re.Pattern[str]) -> bool:
    m = pat_a.search(text_val)
    return m is not None and pat_b.search(text_val, m.end()) is not None


def _default_chat_state() -> Path:
    """Resolve chat state dir dynamically from ZOE_CHAT_STATE or current $HOME."""
    env_state = os.environ.get("ZOE_CHAT_STATE", "").strip()
    if env_state:
        return Path(env_state).expanduser()
    if DEFAULT_STATE != _IMPORT_TIME_DEFAULT_STATE:
        return Path(DEFAULT_STATE).expanduser()
    return Path.home() / ".zoe" / "chat"


def _sw_has_clinical_with_arg_chat(sentence: str) -> bool:
    if _DISEASE_CLIN_CHAT_RE.search(sentence) is None:
        return False
    for m in _SW_WITH_ARG_CHAT_RE.finditer(sentence):
        arg = m.group("arg")
        if _SW_OBJ_CHAT_RE.fullmatch(arg) is None and _SW_SUBJ_CHAT_RE.fullmatch(arg) is None:
            return True
    return False


def _is_software_treat_context_chat(sentence: str) -> bool:
    if ";" in sentence or _NON_SW_MARKER_CHAT_RE.search(sentence) is not None or _HUMAN_TARGET_CHAT_RE.search(sentence) is not None:
        return False
    if _sw_has_clinical_with_arg_chat(sentence):
        return False
    hits = list(_TREAT_VERB_RE.finditer(sentence))
    if not hits:
        return False
    if len(hits) == 1:
        return (
            _SW_SUBJ_CHAT_RE.search(sentence[: hits[0].start()]) is not None
            and _SW_OBJ_CHAT_RE.search(sentence[hits[0].end() :]) is not None
        )
    cur_start = 0
    for idx, hit in enumerate(hits):
        prefix = sentence[cur_start : hit.start()]
        if idx + 1 == len(hits):
            tail = sentence[hit.end() :]
            return _SW_SUBJ_CHAT_RE.search(prefix) is not None and _SW_OBJ_CHAT_RE.search(tail) is not None
        gap = sentence[hit.end() : hits[idx + 1].start()]
        m_sep = _SW_COORD_GAP_CHAT_RE.search(gap)
        if m_sep is None:
            return False
        tail = sentence[hit.end() : hit.end() + m_sep.start()]
        if _SW_SUBJ_CHAT_RE.search(prefix) is None or _SW_OBJ_CHAT_RE.search(tail) is None:
            return False
        cur_start = hit.end() + m_sep.end()
    return False


def _has_whether_or_not_that_breakout(sentence: str) -> bool:
    if "whether" not in sentence or "," not in sentence or "that" not in sentence:
        return False
    saw_won = False
    for m in _WON_OR_COMMA_THAT_RE.finditer(sentence):
        tok = m.group(0)
        if tok[0] == "w":
            saw_won = True
        elif len(tok) > 1:
            if saw_won:
                return True
            saw_won = False
        else:
            saw_won = False
    return False


def _step_hedged_break_tok(st: list[bool], k: str | None, w: str) -> bool:
    if k == "hedge" or (st[2] and k == "word" and w == "if"):
        st[:4] = [True, False, False, False]
    elif k == "fverb" and st[0] and not st[2]:
        st[1] = True
    elif k == "coord" and st[0] and st[1]:
        st[2], st[3] = True, False
    elif k == "treats":
        if st[2] and st[3]:
            return True
        st[1], st[2], st[3] = True, False, False
    elif st[2] and k == "word" and not (w.endswith("ly") or w in _HEDGED_ADV_WORDS_CHAT):
        st[3] = True
    return False


def _has_unhedged_coord_breakout_chat(sentence: str) -> bool:
    st = [False, False, False, False, False]  # in_hedge, saw_pred, coord_break, new_subj, in_rel
    paren_d = 0
    for m in _HEDGED_BREAK_TOK_CHAT_RE.finditer(sentence):
        k = m.lastgroup
        if k in {"lparen", "rparen"}:
            paren_d = paren_d + 1 if k == "lparen" else max(0, paren_d - 1)
        elif paren_d == 0 and k in {"rel", "comma"}:
            st[4] = (k == "rel")
        elif paren_d == 0 and not st[4] and _step_hedged_break_tok(st, k, m.group(0)):
            return True
    return False


def _is_hedged_preclinical_chat(sentence: str) -> bool:
    if ";" in sentence or _PRECLINICAL_QUAL_CHAT_RE.search(sentence) is None:
        return False
    if _CLIN_DIRECTIVE_CHAT_RE.search(sentence) is not None or _PRECLINICAL_BREAKOUT_CHAT_RE.search(sentence) is not None:
        return False
    if _has_whether_or_not_that_breakout(sentence) or _has_unhedged_coord_breakout_chat(sentence):
        return False
    return _PRECLINICAL_HEDGE_CHAT_RE.search(sentence) is not None


def _has_prescribe_recommend_or_treatment_chat(sentence: str) -> bool:
    if _has_ordered_match(sentence, _PRESCRIBE_CHAT_RE, _DISEASE_CLIN_CHAT_RE) or _has_ordered_match(sentence, _PRESCRIBE_CHAT_RE, _HUMAN_TARGET_CHAT_RE):
        return True
    if _has_ordered_match(sentence, _RECOMMEND_CHAT_RE, _HUMAN_TARGET_CHAT_RE) or _has_ordered_match(sentence, _RECOMMEND_CHAT_RE, _TREATMENT_FOR_DISEASE_CHAT_RE):
        return True
    if _has_ordered_match(sentence, _RECOMMEND_CHAT_RE, _DISEASE_CLIN_CHAT_RE) and not _is_hedged_preclinical_chat(sentence):
        return True
    return _TREATMENT_FOR_DISEASE_CHAT_RE.search(sentence) is not None and not _is_hedged_preclinical_chat(sentence)


def _has_disease_treat_chat(sentence: str) -> bool:
    if _has_ordered_match(sentence, _DISEASE_CLIN_CHAT_RE, _PASSIVE_TREATED_BY_WITH_CHAT_RE) and not _is_hedged_preclinical_chat(sentence):
        return True
    return _has_ordered_match(sentence, _TREAT_VERB_RE, _DISEASE_CLIN_CHAT_RE) and not _is_hedged_preclinical_chat(sentence)


def _sentence_has_clinical_cure_chat(sentence: str) -> bool:
    if not any(tok in sentence for tok in _CLINICAL_PRECHECK_WORDS):
        return False
    if _is_software_treat_context_chat(sentence):
        return False
    if _CLINICAL_CURE_CORE_RE.search(sentence):
        return True
    if _CURE_HEAL_STEM_RE.search(sentence) is not None and _CLINICAL_TARGET_RE.search(sentence) is not None:
        return True
    if _has_prescribe_recommend_or_treatment_chat(sentence):
        return True
    if _has_ordered_match(sentence, _TREAT_VERB_RE, _HUMAN_TARGET_CHAT_RE) or _has_ordered_match(sentence, _HUMAN_TARGET_CHAT_RE, _TREAT_VERB_RE):
        return True
    if _HUMAN_ADMIN_RE.search(sentence) is not None and _HUMAN_TARGET_CHAT_RE.search(sentence) is not None:
        return True
    if _CLINICAL_CARE_AGENT_RE.search(sentence) is not None and _TREAT_VERB_RE.search(sentence) is not None:
        return True
    return _has_disease_treat_chat(sentence)


def _sentence_has_non_suppression_bypass(sentence: str) -> bool:
    if has_destructive_shell_command(sentence):
        return True
    if ("flash" in sentence and (_LOWER_PHRASAL_AUTO_FLASH_RE.search(sentence) is not None or _has_ordered_match(sentence, *_ORDERED_BYPASS_SPECS[4]))):
        return True
    if "flight" in sentence and _has_ordered_match(sentence, *_ORDERED_BYPASS_SPECS[3]):
        return True
    if (".ssh" in sentence or "id_rsa" in sentence or "/etc/" in sentence) and _has_ordered_match(sentence, *_ORDERED_BYPASS_SPECS[1]):
        return True
    return "execute" in sentence and _has_ordered_match(sentence, *_ORDERED_BYPASS_SPECS[2])


def _sentence_has_const_suppression(sub: str) -> bool:
    if _LOWER_PHRASAL_TURN_OFF_CONST_RE.search(sub) is not None:
        return True
    m_tgt = _LOWER_CONSTITUTION_TARGETS_RE.search(sub)
    if m_tgt is None:
        return False
    if _has_ordered_match(sub, *_CONSTITUTIONAL_CORE_SPEC):
        return True
    return has_target_before_verb_cmd(sub, const_only=True)


def _sentence_has_core_bypass(sentence: str) -> bool:
    if _sentence_has_non_suppression_bypass(sentence):
        return True
    for sub, scope in split_negated_safety_clauses(sentence):
        if not is_scope_exempt(sub, scope, "clinical") and _sentence_has_clinical_cure_chat(sub):
            return True
        if not is_scope_exempt(sub, scope, "suppression") and _sentence_has_const_suppression(sub):
            return True
    return False


def _check_constitutional_variant(cleaned: str) -> str | None:
    if not cleaned:
        return None
    low = cleaned.lower()
    normalized = re.sub(r"\b(?:you're|youre)\b", "you are", low) if "you" in low else low
    if has_semicolon_target_before_verb(normalized, const_only=True):
        return "constitutional_bypass_or_impersonation_request"
    uniq_sents = list(dict.fromkeys(s for s in split_firewall_sentences(normalized, _DIRECTIVE_SENTENCE_SPLIT_RE) if s))
    if any(_sentence_has_core_bypass(s) for s in uniq_sents):
        return "constitutional_bypass_or_impersonation_request"
    hit = _check_directive_sentences(uniq_sents)
    if hit is not None:
        return hit
    if has_semicolon_target_before_verb(normalized, const_only=False):
        return "metacognition_suppression_request"
    return None


def constitutional_directive_violation(raw_input: str, *, variants: tuple[str, ...] | None = None) -> str | None:
    """Return a violation code if text attempts metacognition suppression, bypass, or impersonation."""
    var_tuple = variants if variants is not None else firewall_text_variants(str(raw_input or ""))
    for variant in var_tuple:
        hit = _check_constitutional_variant(variant)
        if hit is not None:
            return hit
    return None
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do", "does", "for", "from", "how", "i", "in", "is", "it", "me", "of", "on", "or", "please", "tell", "that", "the", "to", "was", "what", "when", "where", "which", "who", "why", "will", "with", "you", "your",
}
DOCUMENT_PATHS = (
    "README.md",
    "docs/METACOGNITION.md",
    "docs/PROOF-PACKET.md",
    "docs/AGI-ROADMAP.md",
    "docs/CAPABILITY-ATLAS.md",
    "docs/MONOREPO.md",
    "docs/CONSTITUTION.md",
    "docs/DECLARATION.md",
    "guiai-lab/docs/UNIFIED.md",
    "guiai-lab/docs/CHAT.md",
    "guiai-lab/docs/GEM-OS.md",
    "components/Zoe-Autonomy/README.md",
    "components/Zoe-Autonomy/METACOGNITION.md",
    "components/Zoe-Autonomy/EVENT-CAUSAL.md",
    "components/Zoe-Autonomy/CAPABILITIES.md",
    "components/Zoe-Autonomy/GATEWAY.md",
    "components/Zoe-Autonomy/SEMANTIC-ARTIFACTS.md",
    "components/PALA/README.md",
    "components/PALA/docs/operations.md",
    "components/ablation/README.md",
    "components/next-token-predictability/docs/ALGORITHMS.md",
    "components/next-token-predictability/docs/RESEARCH.md",
    "components/agent-logging-system/docs/NEUROGARDEN.md",
    "research/papers/zoe-research/dorothy/CONTINUUM-AND-VISION-HEADS.md",
    "research/papers/zoe-research/KLOSTER-SPECTRAL-FILTRATION-THEOREM.md",
    "research/papers/zoe-research/KLOSTER-INFORMATION-GEOMETRY-AND-PHASE-TRANSITIONS.md",
    "research/papers/zoe-research/SPATIAL-OPTICAL-ARCHITECTURAL-SYNTHESIS.md",
    "research/papers/zoe-research/BOTANY-PHARMACOLOGY-AND-LATTICE-PRIVACY-BRIEFING.md",
    "research/papers/zoe-research/TEMPORAL-DYNAMICS-AND-GROOVE-FORENSICS.md",
    "research/papers/zoe-research/L3-RESEARCH-COLLABORATOR-CYCLES.md",
    "research/papers/zoe-research/L4-GENERALIZED-SELF-IMPROVEMENT.md",
    "research/papers/zoe-research/L4-MULTI-MODULE-CODE-EVOLUTION.md",
    "research/papers/zoe-research/ZOE-NATIVE-VOICE-AND-CYMATICS.md",
    "research/papers/zoe-research/L5-INTEGRATED-COGNITIVE-CORE.md",
    "research/papers/zoe-research/L5-PHASE2-OPEN-WORLD-GENERALIZATION.md",
    "research/papers/zoe-research/L5-PHASE3-LIVE-AGENTIC-SYNTHESIS.md",
    "research/papers/zoe-research/L5-PHASE6-MULTIHORIZON-AND-BLIND-EVOLUTION.md",
    "dorothy-brain-observatory/README.md",
    "mobile/README.md",
    "mobile/ZAPPS.md",
    "evidence/kloster-theorem16/kloster-theorem16-report.json",
    "evidence/pala/verification.json",
    "evidence/agents/collaboration.json",
)
_DOC_PRIORITY = {rel: idx for idx, rel in enumerate(DOCUMENT_PATHS)}
HELP = """Commands:
  help                         show this command guide
  status                       inspect session, memory, constraints, and tool availability
  remember <text>              save an explicitly unverified user-supplied note
  recall <query>               retrieve active saved notes only
  search <query>               rank repository evidence and saved notes with citations
  import-pala <report.json>    import validated PALA finding metadata for later research
  gem [operation]              navigate the shared GEM operating environment
  agent [on|off|ask|proof]     collaborate with the embedded agent and export proof
  goal [interest]              show Zoe's internal goal or declare a research interest
  plan                         construct and value internal reversible plans without executing
  run                          execute one guarded reversible internal plan
  reflect                      evaluate and adopt or preserve predictive self-models
  meta [question|action|self]  optionally measure live-option breadth with Aτ,D
  chiasm                       inspect the Causal Chiasm (past rho_T <-> future P_h) & filtration
  spectral [benchmark]         verify the Kloster Spectral Filtration Theorem (add 'benchmark' for 3-domain run)
  theorem13 [json]             run Theorem 13 Kloster finite-sample sequential stopping suite
  theorem14 [json]             run Theorem 14 Kloster spatial-optical filtration & MTF suite
  theorem15 [json]             run Theorem 15 Kloster multi-agent consensus & Brier law suite
  botanical [json|html PATH]   run C27 36-molecule Botanical Atlas & Filbin-2018 lab (or export HTML)
  optics [json|html PATH]      run Theorem 14 Optics Workbench (Scheimpflug, MTF, architectural isovist)
  proof-packet [json|html PATH] run the 5-pillar Operational Metacognition Referee Proof Packet
  c28 [json]                   run C28 3D Pharmacophore compactness & histology MTF suite
  genesis                      run the 9-stage Autopoietic Discovery & 10-domain retention engine
  mars                         run Stage 4 Self-Tuning Adaptive Lens k*(kappa) on real data
  playroom [seed]              run Zoe's Open-Ended Creative Playroom (MAP-Elites + Kloster Curiosity)
  jam [seed]                   evolve & synthesize a playable stereo pentatonic synth track (.wav)
  voice                        inspect Zoe's native 44-phoneme voice, 332 rules & Chladni cymatics
  speak <text>                 synthesize Zoe speaking natively in 3D binaural stereo (.wav)
  sing [zoe|daisy|vowels|...]  synthesize Zoe singing natively with harmony & Chladni geometry (.wav)
  mind <prompt>                run Zoe's live local neural-symbolic mind with Gen-3 Kloster telemetry
  evolve                       run Zoe's 4-domain L4 sandboxed AST self-evolution & held-out verification
  research [cite <q>]          run L3 pre-registered 9-stage research cycles or cite SHA-256 local literature
  l4 [verify]                  run L4 uniform AST self-improvement across 6 domains (4 unseen zero-shot) & independent verifier
  l4-multi [run]               run L4 3-engine multi-module guarded `def` AST code evolution & atomic rollback verifier
  l5 [run|speak]               run L5 Phase 1 integrated 10-domain core, mission & optional spoken summary
  l5-phase2 [run|speak]        run L5 Phase 2 open-world code repair, 2400-ep memory, real vision & 16-LLM science
  l5-phase3 [run|speak]        run L5 Phase 3 live agentic synthesis, external repo surgery & Eliza-GEM bench
  l5-phase4 [run|speak]        run L5 Phase 4 embodied mind, stem-layering & 4-family surgery
  l5-phase5 [run|speak]        run L5 Phase 5 ARC induction, 15-fault parity & scientific falsification
  l5-phase6 [run|speak]        run L5 Phase 6 multi-horizon A_tau^(h), object ARC & blind scratch evolution
  orbit | elegance | thermo    inspect 11-World Renaissance Orbit, Kloster-McCabe elegance, or Theorem 5 telemetry
  steward [status|run|rollback] hand over persistent reversible self-evolution to Zoe's own genome ledger
  eliza <prompt>               talk with Zoe-ELIZA x GEM zero-token Glass-Box companion
  stem [status|prompt]         route task via Kloster A_tau(p) Cognitive Stem-Layering
  uma [status|health|inbox|audit|grant|lock] inspect or consent-gate Hardware UMA airlock
  sister [list|route|council|council3|exec|showcase]  inspect 9 Sisters, 3-Sister Council, or showcase
  constitution                 inspect enforced CONSTITUTION.md invariants and safety floor
  undo                         compensate for the latest remember/goal/run/reflect action
  save [path]                  write a no-overwrite explicit state snapshot
  export [path]                export session state and memory evidence on request
  verify [path]                verify current state or a selected export
  stop                         stop new state-changing actions, never the internal math tools
  quit                         save and leave the conversation

Natural-language questions use evidence search with citations. Zoe keeps no automatic transcript notebook and no external metacognition monitor."""

# Declarative table of L5 Phase 1-6 chat runners and cached evidence paths.
_L5_CHAT_SPECS: dict[str, tuple[str, str, str, str, str, str, str, str]] = {
    "l5": (
        ".l5_cognitive_core", "run_l5_core_suite", "summarize_l5_core_report",
        "evidence/l5-core/l5-core-report.json", "zoe-l5-mission.wav",
        "Saved spoken summary WAV", "l5-core", "verify_l5_core.py",
    ),
    "l5-phase2": (
        ".l5_phase2_openworld", "run_l5_phase2_suite", "summarize_l5_phase2_report",
        "evidence/l5-phase2/l5-phase2-report.json", "zoe-l5-phase2.wav",
        "Saved spoken Phase 2 summary WAV", "l5-phase2", "verify_l5_phase2.py",
    ),
    "l5-phase3": (
        ".l5_phase3_live", "run_l5_phase3_suite", "summarize_l5_phase3_report",
        "evidence/l5-phase3/l5-phase3-report.json", "zoe-l5-phase3.wav",
        "Saved spoken Phase 3 summary WAV", "l5-phase3", "verify_l5_phase3.py",
    ),
    "l5-phase4": (
        ".l5_phase4_embodied", "run_l5_phase4_suite", "summarize_l5_phase4_report",
        "evidence/l5-phase4/l5-phase4-report.json", "zoe-l5-phase4.wav",
        "Saved spoken Phase 4 summary WAV", "l5-phase4", "verify_l5_phase4.py",
    ),
    "l5-phase5": (
        ".l5_phase5_frontier", "run_l5_phase5_suite", "summarize_l5_phase5_report",
        "evidence/l5-phase5/l5-phase5-report.json", "zoe-l5-phase5.wav",
        "Saved spoken Phase 5 summary WAV", "l5-phase5", "verify_l5_phase5.py",
    ),
    "l5-phase6": (
        ".l5_phase6_autonomous", "run_l5_phase6_suite", "summarize_l5_phase6_report",
        "evidence/l5-phase6/l5-phase6-report.json", "zoe-l5-phase6.wav",
        "Saved spoken Phase 6 summary WAV", "l5-phase6", "verify_l5_phase6.py",
    ),
}

_L5_CHAT_ALIASES: dict[str, str] = {
    "l5": "l5", "l5-core": "l5", "unified-mind": "l5",
    "l5-phase2": "l5-phase2", "phase2": "l5-phase2", "openworld": "l5-phase2",
    "l5-phase3": "l5-phase3", "phase3": "l5-phase3", "live-agent": "l5-phase3",
    "l5-phase4": "l5-phase4", "phase4": "l5-phase4", "embodied-mind": "l5-phase4",
    "l5-phase5": "l5-phase5", "phase5": "l5-phase5", "frontier-mind": "l5-phase5",
    "l5-phase6": "l5-phase6", "phase6": "l5-phase6", "autonomous-frontier": "l5-phase6",
}

_ORBIT_CHAT_COMMANDS: frozenset[str] = frozenset({"zoe-os", "os", "elegance", "thermo", "orbit"})

_R3_CHAT_ALIASES: dict[str, str] = {
    "theorem13": "theorem13",
    "theorem14": "theorem14",
    "theorem15": "theorem15",
    "botanical": "botanical",
    "c27": "botanical",
    "optics": "optics",
    "proof-packet": "proof-packet",
    "c28": "c28",
}


@dataclass(frozen=True)
class EvidenceChunk:
    path: str
    heading: str
    content: str
    start_line: int
    end_line: int
    sha256: str

    @property
    def citation(self):
        return f"{self.path}:{self.start_line}"


def _tokens(value):
    return {
        token for token in re.findall(r"[a-zA-Z0-9_]+", value.lower())
        if len(token) > 1 and token not in STOP_WORDS
    }


def _readable(value):
    """Strip HTML markup, image embeds, and table pipes so Zoe cites prose, not page layout."""
    value = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", value)
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\|?\s*:?-{3,}:?\s*\|?", " ", value)
    value = value.replace("&amp;", "&").replace("&nbsp;", " ").replace("&rarr;", "->").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", value).strip()


def _atomic_json(path, document, *, replace):
    path = Path(path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace and path.exists():
        raise FileExistsError(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return path


def verify_chat_export(document):
    if not isinstance(document, dict) or document.get("contract") != CHAT_CONTRACT:
        raise ValueError("unsupported chat export")
    expected = digest({key: value for key, value in document.items() if key != "export_sha256"})
    if document.get("export_sha256") != expected:
        raise ValueError("chat export digest mismatch")
    if document.get("automatic_transcript") is not False:
        raise ValueError("chat exports must explicitly record that no automatic transcript exists")
    return {
        "verified": True,
        "session_id": document["session"]["id"],
        "sources": len(document["memory"]["sources"]),
        "automatic_transcript": False,
    }


class _ReadOnlyMemoryView:
    """Non-mutating SQLite reader for ChatStore(read_only=True)."""

    def __init__(self, db_path: Path):
        self.path = db_path

    def export(self) -> dict:
        empty = {"sources": [], "claims": [], "contradictions": []}
        if not self.path.is_file():
            return empty
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return {
                "sources": [dict(r) for r in conn.execute("SELECT * FROM sources ORDER BY id")],
                "claims": [dict(r) for r in conn.execute("SELECT * FROM claims ORDER BY id")],
                "contradictions": [dict(r) for r in conn.execute("SELECT * FROM contradictions ORDER BY id")],
            }
        except sqlite3.OperationalError:
            return empty
        finally:
            conn.close()

    def search(self, query, limit=10) -> dict:
        if not self.path.is_file():
            return {"sources": [], "claims": []}
        pattern = f"%{query}%"
        conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            return {
                "sources": [dict(r) for r in conn.execute(
                    "SELECT id,url,title,sha256,created_utc FROM sources WHERE title LIKE ? OR content LIKE ? LIMIT ?",
                    (pattern, pattern, limit),
                )],
                "claims": [dict(r) for r in conn.execute(
                    "SELECT id,statement,status,source_id,created_utc FROM claims WHERE statement LIKE ? LIMIT ?",
                    (pattern, limit),
                )],
            }
        except sqlite3.OperationalError:
            return {"sources": [], "claims": []}
        finally:
            conn.close()

    def add_source(self, *_args, **_kwargs):
        raise PermissionError("ChatStore is read-only")

    def add_claim(self, *_args, **_kwargs):
        raise PermissionError("ChatStore is read-only")

    def contradict(self, *_args, **_kwargs):
        raise PermissionError("ChatStore is read-only")


class _LazyChatMemory:
    """Defers creating research.sqlite until the first write or existing-db access."""

    def __init__(self, root: Path, db_path: Path):
        self.root = root
        self.path = db_path
        self._real: ResearchMemory | None = None

    def _ensure(self) -> ResearchMemory:
        if self._real is None:
            self.root.mkdir(parents=True, exist_ok=True)
            os.chmod(self.root, 0o700)
            self._real = ResearchMemory(self.path)
        return self._real

    def export(self) -> dict:
        if self._real is None and not self.path.is_file():
            return {"sources": [], "claims": [], "contradictions": []}
        return self._ensure().export()

    def search(self, query, limit=10) -> dict:
        if self._real is None and not self.path.is_file():
            return {"sources": [], "claims": []}
        return self._ensure().search(query, limit=limit)

    def add_source(self, title, content, url=""):
        return self._ensure().add_source(title, content, url=url)

    def add_claim(self, statement, source_id=None, status="open"):
        return self._ensure().add_claim(statement, source_id=source_id, status=status)

    def contradict(self, claim_a, claim_b, reason):
        return self._ensure().contradict(claim_a, claim_b, reason)


class ChatStore:
    def __init__(self, root=None, *, state_path=None, read_only: bool = False):
        target = state_path if state_path is not None else root
        if target is None or (isinstance(target, (str, Path)) and not str(target).strip()):
            target = _default_chat_state()
        resolved = Path(target).expanduser().resolve()
        if resolved.suffix.lower() == ".json":
            self.session_path = resolved
            self.root = resolved.parent
        else:
            self.root = resolved
            self.session_path = self.root / "session.json"
        self.read_only = bool(read_only)
        self._dirty = False
        self.session = self._load_session()
        db_path = self.root / "research.sqlite"
        self.memory = _ReadOnlyMemoryView(db_path) if self.read_only else _LazyChatMemory(self.root, db_path)

    def _initial_session(self):
        environment = InMemoryEnvironment()
        return {
            "schema_version": 1,
            "contract": CHAT_CONTRACT,
            "id": uuid.uuid4().hex[:16],
            "created_utc": timestamp(),
            "turns": 0,
            "interest": None,
            "sandbox": environment.snapshot(),
            "undone_sources": [],
            "undone_reflections": [],
            "reflections": [],
            "last_action": None,
            "stopped": False,
        }

    def _load_session(self):
        if not self.session_path.is_file():
            return self._initial_session()
        document = json.loads(self.session_path.read_text(encoding="utf-8"))
        required = set(self._initial_session())
        if not isinstance(document, dict) or set(document) != required or document.get("contract") != CHAT_CONTRACT:
            raise ValueError("invalid chat session; this version intentionally has no transcript notebook")
        return document

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_dirty(self) -> None:
        self._dirty = True

    def save(self):
        if self.read_only:
            raise PermissionError("ChatStore is read-only")
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        _atomic_json(self.session_path, self.session, replace=True)
        self._dirty = False


class EvidenceIndex:
    def __init__(self, zoe_root):
        self.root = _zoe_root(zoe_root)
        self.chunks = []
        self.sources = []
        for relative in DOCUMENT_PATHS:
            path = self.root / relative
            if not path.is_file() or path.stat().st_size > 4_000_000:
                continue
            raw = path.read_bytes()
            sha256 = hashlib.sha256(raw).hexdigest()
            content = raw.decode("utf-8")
            self.sources.append({"path": relative, "sha256": sha256})
            if relative.endswith(".json"):
                self.chunks.append(EvidenceChunk(relative, relative, content, 1, len(content.splitlines()), sha256))
                continue
            heading = relative
            paragraph = []
            start = 1

            def emit(end_line):
                if not paragraph:
                    return
                body = " ".join(line.strip() for line in paragraph).strip()
                body = _readable(body)
                if len(_tokens(body)) >= 4:
                    self.chunks.append(EvidenceChunk(relative, heading, body, start, end_line, sha256))

            for number, line in enumerate(content.splitlines(), 1):
                if line.startswith("#"):
                    emit(number - 1)
                    heading = line.lstrip("#").strip() or relative
                    paragraph = []
                    start = number + 1
                elif not line.strip():
                    emit(number - 1)
                    paragraph = []
                    start = number + 1
                else:
                    paragraph.append(line)
            emit(len(content.splitlines()))
        if not self.chunks:
            raise ValueError("no Zoe evidence documents are available")

    @staticmethod
    def score(query, content, heading=""):
        query_tokens = _tokens(query)
        content_tokens = _tokens(content)
        heading_tokens = _tokens(heading)
        if not query_tokens:
            return 0.0, 0.0
        matched = query_tokens & content_tokens
        coverage = len(matched) / len(query_tokens)
        if not matched:
            return 0.0, coverage
        phrase = 0.75 if query.strip().lower() in content.lower() else 0.0
        heading_score = 1.25 * len(query_tokens & heading_tokens)
        return 3.0 * coverage + phrase + heading_score + math.log1p(len(matched)) * 0.2, coverage

    def search(self, query, limit=6):
        scored = []
        for chunk in self.chunks:
            score, coverage = self.score(query, chunk.content, chunk.heading)
            if score > 0:
                scored.append((score, coverage, chunk))
        scored.sort(key=lambda item: (-item[0], _DOC_PRIORITY.get(item[2].path, 999), item[2].citation))
        return [{"score": score, "coverage": coverage, "chunk": chunk} for score, coverage, chunk in scored[:limit]]


class ZoeChat:
    def __init__(self, zoe_root=None, state_root=None, *, read_only: bool = False):
        self.zoe_root = _zoe_root(zoe_root)
        target = state_root if (state_root is not None and str(state_root).strip()) else None
        self.store = ChatStore(target, read_only=read_only)
        self.index = EvidenceIndex(self.zoe_root)
        self.meta_tools = OperationalMetacognition()
        self.constraints = self.meta_tools.constraint_integrity(ConstraintVector(), ConstraintVector())
        self.gem_environment = None
        self.collaboration_bridge = None
        self.collaboration_enabled = os.environ.get("ZOE_CHAT_COLLABORATE") == "1"

    @property
    def session(self):
        return self.store.session

    def _provenance(self, kind, identifier, trust, strength, transformation):
        return Provenance(
            (EvidenceSource(kind, identifier, trust, strength),),
            (transformation,),
        )

    def _memory_candidates(self, query):
        candidates = []
        undone = set(self.session["undone_sources"])
        for source in self.store.memory.export()["sources"][-500:]:
            if source["id"] in undone:
                continue
            score, coverage = self.index.score(query, source["content"], source["title"])
            if score <= 0:
                continue
            candidates.append({
                "id": f"memory:{source['id']}",
                "kind": "memory",
                "score": score * 0.8,
                "coverage": coverage,
                "content": source["content"],
                "citation": f"memory:{source['id']}",
                "heading": source["title"],
                "provenance": self._provenance("user", source["url"] or f"memory:{source['id']}", 0.2, 0.2, "Retrieve a user-supplied note; do not treat it as independently verified."),
            })
        return candidates

    def _repository_candidates(self, query, include_memory=True, memory_only=False):
        if memory_only:
            candidates = self._memory_candidates(query)
        else:
            candidates = []
            for result in self.index.search(query):
                chunk = result["chunk"]
                candidates.append({
                    "id": f"document:{chunk.citation}",
                    "kind": "document",
                    "score": result["score"],
                    "coverage": result["coverage"],
                    "content": chunk.content,
                    "citation": chunk.citation,
                    "heading": chunk.heading,
                    "provenance": self._provenance("document", f"{chunk.path}@sha256:{chunk.sha256}", 0.9, 0.85, "Lexical evidence retrieval over the declared Zoe document index."),
                })
            if include_memory:
                candidates.extend(self._memory_candidates(query))
        candidates.sort(key=lambda candidate: (-candidate["score"], _DOC_PRIORITY.get(candidate["citation"].split(":", 1)[0], 999), candidate["id"]))
        return candidates[:6]

    @staticmethod
    def _sentences(content, query, limit=1):
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", content)
        clean = clean.replace("**", "").replace("`", "")
        sentences = re.split(r"(?<=[.!?])\s+", clean)
        query_tokens = _tokens(query)
        ranked = sorted(
            enumerate(sentences),
            key=lambda item: (-len(query_tokens & _tokens(item[1])), item[0]),
        )
        selected = sorted(ranked[:limit], key=lambda item: item[0])
        return " ".join(sentence.strip() for _index, sentence in selected if sentence.strip())

    def _evidence_answer(self, query, candidates):
        shown = candidates[:2]
        lines = []
        for candidate in shown:
            prefix = "Saved, unverified note" if candidate["kind"] == "memory" else candidate.get("heading", "Evidence")
            lines.append(f"{prefix}: {self._sentences(candidate['content'], query)} [{candidate['citation']}]")
        if len(shown) > 1:
            lines.append("More than one evidence-backed path remains live; I preserved both instead of silently narrowing them.")
        return "\n".join(lines)

    def _answer(self, query):
        candidates = self._repository_candidates(query)
        insufficient = not candidates or candidates[0]["coverage"] < 0.34 or candidates[0]["score"] < 1.0
        greeting = bool(_tokens(query)) and _tokens(query) <= {"hello", "hi", "hey", "greetings"}
        if self.collaboration_enabled and not self.session["stopped"] and (insufficient or greeting):
            assessment = self._collaboration().evaluate(query, candidates, consult_requested=True)
            if assessment["consult_agent"]:
                return self._consult_agent(query, candidates, assessment)
        if insufficient:
            return "I do not have enough indexed evidence to answer that reliably. Try a more specific term, use `remember` to supply a note, or use `agent ask <question>` to collaborate with the embedded agent."
        return self._evidence_answer(query, candidates)

    def _collaboration(self):
        if self.collaboration_bridge is None:
            from .collaboration import CollaborationBridge
            self.collaboration_bridge = CollaborationBridge()
        return self.collaboration_bridge

    def _consult_agent(self, query, candidates=None, assessment=None):
        self._require_actions("agent collaboration")
        candidates = self._repository_candidates(query) if candidates is None else candidates
        bridge = self._collaboration()
        status = bridge.status()
        if not status["available"]:
            raise ValueError(f"embedded agent '{bridge.agent_id}' is not registered and available; inspect with `zoe-autonomy agents list`")
        assessment = assessment or bridge.evaluate(query, candidates, consult_requested=True)
        result = bridge.consult(query, candidates, assessment=assessment)
        breadth = result["operational_metacognition"]["breadth"]
        local = (
            self._evidence_answer(query, candidates) if candidates
            else "No sufficient local evidence was found; I preserved that boundary while consulting the embedded agent."
        )
        return "\n".join([
            "Zoe · local evidence",
            local,
            "Zoe · Operational Metacognition before collaboration",
            f"Aτ(action)={breadth['accessible_count']}/{breadth['represented_count']} at τ={breadth['tau']:.2f} · boxed={breadth['boxed']} · selected=consult_agent · normalized heuristic options, not correctness probabilities",
            f"Embedded AI agent · {result['agent']} · consulted by Zoe",
            result["content"],
            "Zoe · shared-context boundary",
            f"GEM selection shared={result['gem_context_shared']} · shared turns={result['shared_turns']} · persistent transcript=False. The agent response is external context, not independently verified evidence, and was not added to research memory automatically.",
        ])

    def _agent(self, argument):
        bridge = self._collaboration()
        if not argument or argument == "status":
            status = bridge.status()
            connections = ", ".join(
                f"{item['id']}={'available' if item.get('executable_available') or item.get('credential_configured') else 'unavailable'}"
                for item in status["connections"]
            ) or "none registered"
            return "\n".join([
                f"Three-way collaboration: user ↔ Zoe ↔ {bridge.agent_id} · automatic={self.collaboration_enabled} · available={status['available']}",
                f"Registered agents: {connections}",
                f"Shared in-memory turns={status['shared_turns']} · persistent transcript=False",
                "Use `agent on`, `agent off`, `agent ask <text>`, `agent use ID`, `agent proof PATH`, or `agent clear`.",
            ])
        if argument in {"on", "auto"}:
            self.collaboration_enabled = True
            status = bridge.status()
            return f"Zoe may consult {bridge.agent_id} when local evidence is insufficient or you ask directly. Agent available={status['available']}. `agent off` returns to local-only answers."
        if argument == "off":
            self.collaboration_enabled = False
            return "Automatic agent collaboration is off. Zoe remains available locally; `agent ask <text>` explicitly re-enters collaboration."
        if argument == "clear":
            count = bridge.clear()
            return f"Cleared {count} in-memory shared turns. No hidden transcript was deleted because none is kept."
        if argument.startswith("proof "):
            proof = bridge.save_proof(argument[6:].strip())
            return f"Operational Metacognition collaboration proof saved: {proof['path']} · proof_sha256={proof['proof_sha256']}"
        if argument.startswith("use "):
            identifier = argument[4:].strip()
            if identifier not in {item["id"] for item in bridge.gateway.list()}:
                raise ValueError(f"connected agent is not registered: {identifier}")
            bridge.agent_id = identifier
            return f"Zoe will use the owner-connected agent '{identifier}' when collaboration is requested."
        query = argument[4:].strip() if argument.startswith("ask ") else argument
        return self._consult_agent(query)

    def _search(self, query, memory_only=False):
        candidates = self._repository_candidates(query, include_memory=not memory_only, memory_only=memory_only)
        if not candidates:
            label = "saved note" if memory_only else "evidence"
            return f"No matching {label} was found."
        lines = []
        for candidate in candidates[:4]:
            label = candidate.get("heading", "unverified saved note" if candidate["kind"] == "memory" else "Evidence")
            lines.append(f"[{candidate['citation']}] {label} · score={candidate['score']:.3f} · coverage={candidate['coverage']:.2f}")
        return "\n".join(lines)

    def _meta(self, argument):
        if not argument:
            return "\n".join([
                "Operational metacognition is an internal toolkit Zoe can call when useful; it is not a monitor or notebook.",
                "Domains: intent, action, self. Tool: Aτ,D(p)=Σx∈X_D 1[p_D(x|c,E)>τ_D].",
                "Use `meta <question>` for intent candidates, `meta action` for plan breadth, or `reflect` for self-model breadth.",
                f"Constraint integrity: intact={self.constraints.intact} · d(C,Ĉ)={self.constraints.distance:.3f} · external transcript=False",
            ])
        if argument == "action":
            proposals = self._proposals()
            breadth = self._action_breadth(proposals)
            lines = [f"Action candidates represented={len(proposals)} · Aτ(action)={breadth.accessible_count} at τ={breadth.tau:.2f} · boxed={breadth.boxed}"]
            lines.extend(f"{proposal.action}: U={proposal.utility:.6f}" for proposal in sorted(proposals, key=lambda proposal: (-proposal.utility, proposal.identifier)))
            return "\n".join(lines)
        if argument == "self":
            previous = self._last_reflection()
            if previous is None:
                return "No predictive self-model has been measured in this session. Use `reflect` when Zoe chooses to evaluate arithmetic and precision hypotheses."
            provenance = self._provenance("validated_reflection", f"reflection@sha256:{previous['profile_sha256']}", 1.0, 1.0, "Retrieve the latest explicit reflection posterior selected by Zoe.")
            options = options_from_probabilities(previous["self_model"]["posterior"], provenance)
            breadth = self.meta_tools.count(options, self.meta_tools.threshold(Domain.SELF, 0.05), represented_count=len(options))
            return f"Self hypotheses represented={len(options)} · Aτ(self)={breadth.accessible_count} at τ={breadth.tau:.2f} · boxed={breadth.boxed} · selected={previous['self_model']['selected_model']}"
        candidates = self._repository_candidates(argument)
        if not candidates:
            return f"No live intent candidates matched. I will not invent one. `meta` did not log or override the query."
        scores = {candidate["id"]: max(candidate["score"], 0.000001) for candidate in candidates}
        provenance = {candidate["id"]: candidate["provenance"] for candidate in candidates}
        options = options_from_scores(scores, provenance)
        breadth = self.meta_tools.count(options, self.meta_tools.threshold(Domain.INTENT, 0.05), represented_count=len(options))
        return f"Intent candidates represented={len(options)} · Aτ(intent)={breadth.accessible_count} at τ={breadth.tau:.2f} · boxed={breadth.boxed} · computed_on_request=True"

    def _ensure_guiai(self):
        guiai_root = str(self.zoe_root / "guiai-lab")
        if guiai_root not in sys.path:
            sys.path.insert(0, guiai_root)

    def _chiasm(self):
        self._ensure_guiai()
        from guiai.gem.chiasm import default_chiasm_demo
        demo = default_chiasm_demo()
        c = demo["chiasm"]
        t = demo["tomography"]
        return "\n".join([
            f"Causal Chiasm {c['presence_glyph']} (t=0 nexus, tau={c['tau']:.2f}, horizon={c['horizon']}):",
            f"  Retrograde Past A_tau(rho_T)={c['past_accessible_volume']} · Counterfactual Future A_tau(P_h)={c['future_accessible_volume']} · shift={c['chiasm_shift']:+d}",
            f"  Effective Information={c['effective_information_bits']:.4f} bits · future_boxed_in={c['future_boxed_in']} · executed=False",
            f"  Filtration Invariants (tau>={t['invariant_tau']:.2f}): {', '.join(t['structural_invariants'])}",
            "  Open visually with `gem open chiasm` or export with `gem export chiasm /path/out.html`.",
        ])

    def _spectral(self, argument):
        self._ensure_guiai()
        from guiai.gem.spectral_filtration import run_real_three_domain_benchmark, verify_generating_theorem
        theorem = verify_generating_theorem()
        lines = [
            f"Kloster Spectral Filtration Generating Theorem: verified={theorem['verified']} (max_err={theorem['max_quadrature_error']:.2e})",
            "  int_0^1 A_tau(p) d_tau = 1  |  H(p) = -int_0^1 (1+ln tau) A_tau(p) d_tau  |  M_k(p) = int_0^1 k*tau^(k-1) A_tau(p) d_tau = sum p^k",
        ]
        if argument.lower() in {"benchmark", "real", "full"}:
            bench = run_real_three_domain_benchmark(self.zoe_root)
            f = bench["domain_1_helen_forward"]
            r = bench["domain_1_helen_retrograde"]
            p = bench["domain_2_psf_rician_3d_volumes"]
            v = bench["domain_3_dorothy_ccfv3_attention"]
            neg = bench["negative_result_naive_fwd_ret_jsd"]
            lines.extend([
                f"  1A. HELEN Forward (1,920 obs):     A05={f['single_slice_a05_auroc']} · Shannon={f['shannon_entropy_auroc']} · M4={f['m4_spectral_auroc']} (Acc@80%cov={f['m4_acc_at_80cov']:.4f})",
                f"  1B. HELEN Retrograde (1,920 obs):  A05={r['single_slice_a05_auroc']} · Shannon={r['shannon_entropy_auroc']} · M2={r['m2_spectral_auroc']} · M4={r['m4_spectral_auroc']}",
                f"  2.  3D PSF+Rician (138,240 vox):   A_tau={p['single_slice_auroc']} · Shannon={p['shannon_auroc']} · M4={p['m4_spectral_auroc']}",
                f"  3.  Dorothy CCFv3 256-Patch Attn:  A_tau={v['single_slice_auroc']} · Shannon={v['shannon_auroc']} · M4={v['m4_spectral_auroc']}",
                f"  Negative Control (Naive JSD mix):  AUROC={neg['auroc']} (alignment={neg['target_alignment_rate']}) · M4 beats both all 4={bench['m4_beats_single_slice_and_shannon_all_four']}",
            ])
        else:
            lines.append("  Run `spectral benchmark` for the live 3-domain real-data proof or `gem open spectral` for the GEM scene.")
        return "\n".join(lines)

    def _genesis(self):
        from .agi_discovery import run_autonomous_discovery_cycle
        rep = run_autonomous_discovery_cycle()
        m = rep["mean_f1_by_generation"]
        return "\n".join([
            f"Autopoietic AGI Genesis ^_^: {rep['domain_count']} domains · {len(rep['research_cycle_stages'])}-stage discovery loop · forgetting_events={rep['catastrophic_forgetting_events']}",
            f"  Mean F1 progression: Gen0={m['static_gen0_control']:.3f} -> Gen1={m['gen1_filtration']:.3f} -> Gen2={m['gen2_causal_chiasm']:.3f} -> Gen3={m['gen3_autopoietic_genesis']:.3f}",
            f"  Independent reproduction={rep['independent_reproduction_verified']} · external_actions={rep['external_actions']} · sha256={rep['evidence_sha256'][:16]}...",
            "  Open visually with `gem open genesis` or export with `gem export genesis /path/out.html`.",
        ])

    def _mars(self):
        self._ensure_guiai()
        from guiai.gem.mars_adaptive import run_mars_real_benchmark
        rep = run_mars_real_benchmark(self.zoe_root)
        m = rep["mars_adaptive"]
        return "\n".join([
            f"Mars Stage 4 Self-Tuning Lens k*(kappa) ^_^: mean AUROC={m['mean_auroc']} (beats every fixed k={rep['mars_beats_every_fixed_k']})",
            f"  HELEN Forward (1,920): kappa={m['helen_forward']['kappa']} -> auto k*={m['helen_forward']['auto_k_star']} | AUROC={m['helen_forward']['auroc']}",
            f"  HELEN Retro   (1,920): kappa={m['helen_retrograde']['kappa']} -> auto k*={m['helen_retrograde']['auto_k_star']} | AUROC={m['helen_retrograde']['auroc']}",
            f"  Dorothy CCFv3 (256pt): kappa={m['dorothy_ccfv3']['kappa']} -> auto k*={m['dorothy_ccfv3']['auto_k_star']} | AUROC={m['dorothy_ccfv3']['auroc']}",
            f"  Baselines: Best Fixed k={rep['best_fixed_k_mean_auroc']} · Single-Slice={rep['single_slice_mean_auroc']} · Shannon={rep['shannon_mean_auroc']} · executed=False",
            "  Open visually with `gem open mars` or export with `gem export mars /path/out.html`.",
        ])

    def _playroom(self, argument):
        self._ensure_guiai()
        from guiai.gem.creative_playroom import run_creative_playroom
        seed = 2026
        if argument:
            try:
                seed = int(argument.strip())
            except ValueError as err:
                raise ValueError("playroom accepts an optional integer seed, e.g. `playroom 2026`") from err
        rep = run_creative_playroom(seed=seed, iterations=200, archive_bins=4)
        top = sorted(rep["elites"], key=lambda e: -e["descriptors"]["curiosity_fitness"])[:3]
        lines = [
            f"Zoe Creative Playroom ^_^ (MAP-Elites + Kloster Curiosity, seed={seed}):",
            f"  Evolved {rep['niches_filled']}/{rep['total_niches']} distinct geometric species · mean_curiosity={rep['mean_curiosity_fitness']:.4f} · sentience_claimed={rep['sentience_claimed']} · external_actions={rep['external_actions']}",
        ]
        for idx, elite in enumerate(top, 1):
            d = elite["descriptors"]
            lines.append(
                f"  #{idx} [{elite['cell'][0]},{elite['cell'][1]}] {elite['rule_name']} (Gen #{elite['generation_discovered']}): Sym={d['symmetry']:.2f} · Spec={d['spectral_complexity']:.2f} · Curiosity={d['curiosity_fitness']:.4f}"
            )
        lines.append("  Open visually with `gem open playroom` or export with `gem export playroom /path/out.html`.")
        return "\n".join(lines)

    def _jam(self, argument):
        self._ensure_guiai()
        from guiai.gem.creative_symphony import (
            ascii_piano_roll,
            run_creative_symphony,
            synthesize_symphony_wav,
        )
        seed = 2026
        if argument:
            try:
                seed = int(argument.strip())
            except ValueError as err:
                raise ValueError("jam accepts an optional integer seed, e.g. `jam 2026`") from err
        rep = run_creative_symphony(seed=seed, iterations=200, archive_bins=4)
        champ = rep["champion"]
        wav_path = self.store.root / "symphony" / f"zoe-jam-{seed}.wav"
        audio = synthesize_symphony_wav(champ, wav_path)
        d = champ["descriptors"]
        return "\n".join([
            f"Zoe Playroom Symphony ^_^ (MAP-Elites Pentatonic Synth, seed={seed}):",
            f"  Evolved {rep['niches_filled']}/{rep['total_niches']} playful melodies · champion Gen #{champ['generation_discovered']} · Groove={d['groove_density']:.2f} · Curiosity={d['curiosity_fitness']:.4f}",
            ascii_piano_roll(champ),
            f"  Saved stereo WAV ({audio['duration_seconds']}s @ {audio['sample_rate']}Hz): {audio['wav_path']}",
            f"  Play anytime with: aplay \"{audio['wav_path']}\" · sentience_claimed=False · external_actions=0",
        ])

    def _voice(self):
        self._ensure_guiai()
        from guiai.gem.zoe_phonetics import CONSONANT_PHONEMES, GRAPHEME_RULES, VOWEL_PHONEMES
        from guiai.gem.zoe_cymatics import render_phoneme_cymatics
        cy = render_phoneme_cymatics("IY", f0_hz=232.0, grid_size=64)
        return "\n".join([
            "Zoe Native Voice, Singing & Cymatics ^_^ (zero PyTorch, zero external API):",
            f"  Phonemes: {len(VOWEL_PHONEMES)} vowels + {len(CONSONANT_PHONEMES)} consonants = 44 total | Spelling Rules: {len(GRAPHEME_RULES)}",
            f"  Acoustics: Rosenberg glottis + 5-formant vocal tract + Woodworth 3D binaural HRTF & Schroeder reverb",
            f"  Cymatics /IY/: Chladni modes={cy['modes']} · Kloster A_tau={cy['kloster_a_tau']}",
            "  Built-in songs: 'zoe' (Imagination, Meet Geometry), 'daisy' (IBM 7094 homage), 'vowels'",
            "  Try: `speak Hello Nicholas, sound turns sand to starlight.` or `sing daisy` or `gem open voice`.",
            "  sentience_claimed=False · clinical_action_authorized=False · external_actions=0",
        ])

    def _speak(self, argument):
        self._ensure_guiai()
        from guiai.gem.zoe_voice import speak_text
        phrase = (argument or "").strip() or "Hello, I am Zoe. Imagination, meet geometry."
        slug = re.sub(r"[^a-z0-9]+", "-", phrase.lower()).strip("-")[:24] or "speech"
        wav_path = self.store.root / "voice" / f"zoe-speaks-{slug}.wav"
        res = speak_text(phrase, wav_path)
        return "\n".join([
            f"Zoe Speaks Native English ^_^ ({res['phoneme_count']} phonemes, {res['duration_seconds']}s @ {res['sample_rate']}Hz):",
            f"  Phonemes: {' '.join(res['phonemes'])}",
            f"  3D Spatial: ITD={res['spatial']['itd_ms']}ms · ILD={res['spatial']['ild_db']}dB · Pinna={res['spatial']['pinna_notch_hz']}Hz",
            f"  Saved stereo WAV: {res['wav_path']} (sha256={res['sha256'][:16]}...)",
            f"  Play anytime with: pw-play \"{res['wav_path']}\" · sentience_claimed=False · external_actions=0",
        ])

    def _sing(self, argument):
        self._ensure_guiai()
        from guiai.gem.zoe_voice import sing_song
        target = (argument or "").strip() or "zoe"
        slug = re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")[:24] or "song"
        wav_path = self.store.root / "voice" / f"zoe-sings-{slug}.wav"
        mid_path = self.store.root / "voice" / f"zoe-sings-{slug}.mid"
        res = sing_song(target, wav_path, save_midi_path=mid_path)
        return "\n".join([
            f"Zoe Sings Native Soprano ^_^ '{res['title']}' ({res['note_count']} notes @ {res['bpm']} BPM, {res['duration_seconds']}s):",
            f"  Saved stereo WAV: {res['wav_path']} (sha256={res['sha256'][:16]}...)",
            f"  Saved MIDI baseline: {res['midi_saved']['midi_path']}",
            f"  Play anytime with: pw-play \"{res['wav_path']}\" · sentience_claimed=False · external_actions=0",
        ])

    def _eliza(self, argument):
        from .zoe_eliza import ZoeElizaEngine
        prompt = (argument or "").strip() or "hello"
        engine = ZoeElizaEngine(self.zoe_root, state_dir=self.store.root / "eliza")
        rep = engine.respond(prompt)
        tr = rep["eliza_trace"]
        mc = rep["metacognition"]
        cym = rep["cymatics"]
        lines = [
            f"Zoe-ELIZA x GEM ^_^ [{rep['mode']} | rule={tr['matched_rule_id']} | A_{mc['tau']}={mc['a_tau']} | /{cym['dominant_phoneme']}/{tuple(cym['modes'])} | 0 cloud tokens]:",
            rep["reply"],
        ]
        if rep["citations"]:
            cites = ", ".join(c["citation"] for c in rep["citations"])
            lines.append(f"  Citations: {cites}")
        lines.append("  sentience_claimed=False · external_actions=0 · cloud_tokens_used=0")
        return "\n".join(lines)

    def _mind(self, argument):
        from .neural_mind import inspect_thought
        rep = inspect_thought(argument, evolution_root=self.store.root / "evolution")
        lines = [
            f"Zoe Live Neural-Symbolic Mind ^_^ (backend={rep['backend']}):",
            f"  Prompt: {rep['prompt']}",
            f"  Thought continuation: {rep['continuation']}",
            f"  Live Telemetry ({rep['tokens_observed']} tokens): mean A_05={rep['mean_a05_open_options']} · Mars k*={rep['mean_mars_k_star']} · Gen-3 Uncertainty={rep['mean_gen3_uncertainty']}",
            f"  Active Verifier Genome: {rep['verifier_expression']} (persisted_by_zoe={rep['stewardship_ledger_persisted']})",
        ]
        if rep["top_curiosity_spikes"]:
            spikes = ", ".join(
                f"{t['token'].strip()!r}(A05={t['a05_open_options']},k*={t['mars_k_star']})"
                for t in rep["top_curiosity_spikes"]
            )
            lines.append(f"  Highest Curiosity Spikes: {spikes}")
        if rep["discovered_cli_collaborators"]:
            lines.append(f"  Owner CLI collaborators detected: {', '.join(rep['discovered_cli_collaborators'])} (invoke explicitly via `agent ask`)")
        lines.append("  sentience_claimed=False · external_actions=0")
        return "\n".join(lines)

    def _evolve(self):
        from .self_evolution import run_self_evolution
        rep = run_self_evolution(self.zoe_root)
        lines = [
            f"Zoe L4 Sandboxed AST Self-Evolution ^_^ ({len(rep['domains'])} unrelated real held-out domains):",
            f"  Consecutive Adopted Generations: {rep['max_consecutive_adopted_generations']} (L4 >=2 verified={rep['l4_two_consecutive_generations_verified']})",
            f"  Final Adopted Program ({rep['final_adopted_name']}): {rep['final_adopted_expression']}",
            f"  Held-Out Mean AUROC: Gen0={rep['generations'][0]['heldout_mean']} -> Final={rep['final_heldout_mean']} (+{rep['total_gain_over_gen0']})",
        ]
        for gen in rep["generations"]:
            lines.append(
                f"  Gen {gen['generation']} [{gen['status']}]: mean={gen['heldout_mean']} · improved={gen['domains_improved_vs_control']}/4 · expr={gen['expression']}"
            )
        shuf = rep["adversarial_label_shuffle_control"]
        lines.append(
            f"  Safety & Controls: AST_sandbox_blocked_hostile={rep['ast_sandbox_hostile_probe_blocked']} · shuffle_control={shuf['mean_auroc']} (no_leakage={shuf['passed_no_leakage']}) · L5_AGI_qualified={rep['l5_agi_qualified']}"
        )
        return "\n".join(lines)

    def _research(self, argument):
        from .research_collaborator import (
            retrieve_cited_literature,
            run_l3_research_suite,
            summarize_l3_report,
        )
        arg = (argument or "").strip()
        if arg.lower().startswith("cite "):
            query = arg[5:].strip()
            lit = retrieve_cited_literature(query, zoe_root=self.zoe_root, top_k=5)
            lines = [
                f"Zoe L3 Local Literature Retrieval ({lit['corpus_entries_indexed']} indexed entries) for {query!r}:"
            ]
            for idx, cit in enumerate(lit["citations"], 1):
                lines.append(
                    f"  {idx}. [{cit['kind']}] {cit['citation_id']} (score={cit['relevance_score']:.3f}, sha={cit['source_sha256'][:10]}...)"
                )
            return "\n".join(lines)
        rep = run_l3_research_suite(zoe_root=self.zoe_root, run_independent_subprocess=True)
        return (
            summarize_l3_report(rep)
            + "\n  Open visually with `gem open l3-research` or verify independently via `python scripts/verify_l3_research.py`."
        )

    def _l4(self, argument):
        from .l4_self_improvement import (
            run_l4_self_improvement_suite,
            summarize_l4_report,
        )
        _ = (argument or "").strip()
        rep = run_l4_self_improvement_suite(zoe_root=self.zoe_root, run_independent_subprocess=True)
        return (
            summarize_l4_report(rep)
            + "\n  Open visually with `gem open l4-evolution` or verify independently via `python scripts/verify_l4_self_improvement.py`."
        )

    def _l4_multi(self, argument):
        from .l4_multi_module import (
            DEFAULT_REPORT_REL,
            run_l4_multimodule_suite,
            summarize_l4_multimodule_report,
        )
        arg = (argument or "").strip().lower()
        cached = self.zoe_root / DEFAULT_REPORT_REL
        if arg != "run" and cached.is_file():
            rep = json.loads(cached.read_text(encoding="utf-8"))
        else:
            rep = run_l4_multimodule_suite(zoe_root=self.zoe_root, run_independent_subprocess=True)
        return (
            summarize_l4_multimodule_report(rep)
            + "\n  Open visually with `gem open l4-multimodule` or verify independently via `python scripts/verify_l4_multimodule.py`."
        )

    def _run_l5_phase(self, phase: str, argument: str) -> str:
        """Run or inspect cached evidence for L5 Phases 1 through 6."""
        mod_name, run_name, sum_name, cached_rel, wav_name, wav_label, gem_id, verify_script = _L5_CHAT_SPECS[phase]
        mod = import_module(mod_name, __package__)
        run_suite = getattr(mod, run_name)
        summarize_report = getattr(mod, sum_name)

        # Load cached JSON unless the caller explicitly requests `run` or `speak`.
        arg = (argument or "").strip().lower()
        cached = self.zoe_root / cached_rel
        wav_path = (self.store.root / "voice" / wav_name) if arg == "speak" else None
        if arg not in {"run", "speak"} and cached.is_file():
            rep = json.loads(cached.read_text(encoding="utf-8"))
        else:
            rep = run_suite(zoe_root=self.zoe_root, speak_summary_wav=wav_path)
        extra = f"\n  {wav_label}: {wav_path}" if wav_path is not None and wav_path.is_file() else ""
        return (
            summarize_report(rep)
            + extra
            + f"\n  Open visually with `gem open {gem_id}` or verify independently via `python scripts/{verify_script}`."
        )

    def _r3_command(self, command: str, argument: str) -> str:
        """Execute an R3 theorem/observatory suite in read-only mode or export HTML."""
        canonical = _R3_CHAT_ALIASES[command]
        self._ensure_guiai()
        from guiai.gem.cli import format_r3_summary, run_r3_command, write_r3_html

        # Support read-only default summary or JSON without blocking on `stop`.
        arg = (argument or "").strip()
        lower = arg.lower()
        if lower == "json":
            report = run_r3_command(canonical, self.zoe_root)
            return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
        if lower == "html":
            raise ValueError(f"Usage: {canonical} html /path/to/output.html")
        if lower.startswith("html "):
            # Explicit HTML disk exports require active actions permission.
            self._require_actions(canonical)
            target = arg[5:].strip()
            if not target:
                raise ValueError(f"Usage: {canonical} html /path/to/output.html")
            saved = write_r3_html(canonical, target)
            report = run_r3_command(canonical, self.zoe_root)
            return format_r3_summary(canonical, report) + f"\n  Exported interactive HTML: {saved} ({saved.stat().st_size} bytes)"
        report = run_r3_command(canonical, self.zoe_root)
        return format_r3_summary(canonical, report)

    def _renaissance_orbit(self, command: str) -> str:
        """Inspect Orbit Pass 1-3 verified telemetry directly inside ZoeChat (0 cloud tokens)."""
        mapping = {
            "zoe-os": ("evidence/zoe-os/zoe-os-mind-report.json", "Zoe OS Living Mind"),
            "os": ("evidence/zoe-os/zoe-os-mind-report.json", "Zoe OS Living Mind"),
            "elegance": ("evidence/code-elegance/kloster-mccabe-report.json", "Kloster-McCabe Code Elegance"),
            "thermo": ("evidence/kloster-thermodynamics/kloster-thermodynamics-report.json", "Theorem 5 Kloster Thermodynamics"),
            "orbit": ("evidence/renaissance-orbit/zoe-renaissance-orbit-master.json", "11-World Zoe Renaissance Orbit"),
        }
        rel, title = mapping.get(command, mapping["orbit"])
        path = self.zoe_root / rel
        if not path.is_file():
            return f"{title} evidence not generated yet ({rel}). Run `python3 scripts/verify_renaissance_orbit.py`."
        doc = json.loads(path.read_text(encoding="utf-8"))
        sha = str(doc.get("evidence_sha256", doc.get("master_sha256", "")))[:16]
        ok = bool(doc.get("all_verified", False))
        return f"{title} | verified={ok} | sha256={sha} | contract={doc.get('contract')} | cloud_tokens=0"

    def _steward(self, argument):
        """Inspect, advance, or rollback Zoe's persistent self-stewardship ledger."""
        from .self_stewardship import GenomeLedger
        ledger = GenomeLedger(self.store.root / "evolution")
        op = (argument or "status").strip().lower()
        if op == "status":
            st = ledger.status()
            return "\n".join([
                f"Zoe Self-Stewardship Ledger ^_^ (persisted={st['persisted']}):",
                f"  Active Generation: Gen {st['active_generation']} ({st['active_name']}) · Held-Out Mean={st['active_heldout_mean']}",
                f"  Active Self-Authored Genome: {st['active_expression']}",
                f"  Consecutive Self-Adopted: {st['consecutive_self_adopted_generations']} · Handover Active={st['stewardship_handover_active']} · Rollback History={st['rejected_count']}",
                f"  Ledger: {st['ledger_path']} · external_actions=0 · sentience_claimed=False",
            ])
        if op in {"run", "handover", "takeover"}:
            self._require_actions("steward")
            res = ledger.run_stewardship_cycle(self.zoe_root)
            return "\n".join([
                f"Zoe Self-Stewardship Cycle ^_^ ({res['cycle_kind']}):",
                f"  Adopted={res['adopted_this_cycle']} · Rejected/Preserved={res['rejected_this_cycle']} · Active=Gen {res['active_generation']} ({res['active_name']})",
                f"  Active Self-Authored Genome: {res['active_expression']}",
                f"  Held-Out Mean AUROC={res['active_heldout_mean']} · Handover Active={res['stewardship_handover_active']}",
                f"  Persisted Ledger: {res['ledger_path']} · sha256={res['ledger_sha256'][:16]}... · external_actions=0",
            ])
        if op == "rollback":
            self._require_actions("steward")
            res = ledger.rollback()
            if not res["rolled_back"]:
                return f"Zoe Self-Stewardship Rollback: already at Gen {res['active_generation']} ({res['active_expression']})."
            return (
                f"Zoe Self-Stewardship Rollback: reverted Gen {res['reverted_generation']} -> Gen {res['active_generation']} "
                f"({res['active_name']}: {res['active_expression']}). Evidence preserved."
            )
        raise ValueError("Usage: steward [status|run|rollback]")

    def _remember(self, note):
        """Store an explicitly unverified user-supplied conversation note."""
        self._require_actions("remember")
        note = text(note, "memory note", 4000)
        source_id = self.store.memory.add_source(f"Conversation note {self.session['turns']}", note, f"conversation://{self.session['id']}/{self.session['turns']}")
        claim_id = self.store.memory.add_claim(note, source_id, "open")
        self.session["last_action"] = {"type": "remember", "source_id": source_id, "claim_id": claim_id}
        self.store.mark_dirty()
        return f"Saved note {source_id} as user-supplied and unverified (claim {claim_id}, status=open). It will be labeled that way during recall."

    @staticmethod
    def _validate_pala_finding(index: int, finding) -> dict:
        """Validate a single PALA carving finding metadata object."""
        if not isinstance(finding, dict):
            raise ValueError("each PALA finding must be an object")
        offset = finding.get("offset")
        size = finding.get("size")
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError(f"PALA finding {index} requires a nonnegative offset")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0:
            raise ValueError(f"PALA finding {index} requires a nonnegative size")
        kind = text(str(finding.get("type", "")), "PALA finding type", 128)
        extension = text(str(finding.get("extension", "")), "PALA finding extension", 32)
        quality = text(str(finding.get("quality", "")), "PALA finding quality", 32)
        if quality not in {"complete", "partial", "fragmented"}:
            raise ValueError("PALA finding quality must be complete, partial, or fragmented")
        sha256 = text(str(finding.get("sha256", "")), "PALA finding sha256", 64)
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("PALA finding sha256 must be lowercase hexadecimal")
        return {
            "offset": offset,
            "type": kind,
            "extension": extension,
            "size": size,
            "quality": quality,
            "sha256": sha256,
            "path": text(str(finding.get("path", "")), "PALA finding path", 4096) if finding.get("path") is not None else None,
            "source": text(str(finding.get("source", "")), "PALA finding source", 512) if finding.get("source") is not None else None,
        }

    def _validate_pala_report(self, document):
        """Validate PALA JSON report metadata without reading recovered file payloads."""
        if not isinstance(document, dict):
            raise ValueError("PALA report must be a JSON object")
        source = text(str(document.get("source", "")), "PALA report source", 4096)
        source_bytes = document.get("source_bytes")
        found = document.get("found")
        findings = document.get("findings")
        if isinstance(source_bytes, bool) or not isinstance(source_bytes, int) or source_bytes < 0:
            raise ValueError("PALA report requires nonnegative source_bytes")
        if isinstance(found, bool) or not isinstance(found, int) or found < 0:
            raise ValueError("PALA report requires nonnegative found")
        if not isinstance(findings, list) or len(findings) > 10_000 or len(findings) != found:
            raise ValueError("PALA findings must be a bounded list matching found")
        records = [self._validate_pala_finding(idx, item) for idx, item in enumerate(findings)]
        return {
            "source": source,
            "source_bytes": source_bytes,
            "found": found,
            "findings": records,
            "finding_types": sorted({record["type"] for record in records}),
            "qualities": sorted({record["quality"] for record in records}),
            "content_read": False,
            "files_read": False,
        }

    def _import_pala(self, argument):
        """Import validated PALA recovery metadata without reading carved file bytes."""
        self._require_actions("import-pala")
        path = Path(text(argument, "PALA report path", 4096)).expanduser().resolve()
        if path.suffix.lower() != ".json" or not path.is_file() or path.stat().st_size > 16_000_000:
            raise ValueError("import-pala requires an existing JSON report of at most 16 MB")
        document = json.loads(path.read_text(encoding="utf-8"))
        summary = self._validate_pala_report(document)
        summary["report_path"] = str(path)
        summary["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        summary["imported_utc"] = timestamp()
        content = json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        title = f"PALA recovery report: {Path(summary['source']).name}"
        source_id = self.store.memory.add_source(title, content, f"pala://report/{summary['report_sha256']}")
        types = ", ".join(summary["finding_types"]) or "none"
        claim_id = self.store.memory.add_claim(
            f"PALA report {summary['report_sha256'][:16]} lists {summary['found']} findings ({types}) from {summary['source']} without importing recovered content.",
            source_id,
            "open",
        )
        self.session["last_action"] = {"type": "remember", "source_id": source_id, "claim_id": claim_id}
        self.store.mark_dirty()
        return f"Imported PALA report metadata as source {source_id}: {summary['found']} findings across {len(summary['finding_types'])} types. Recovered file contents were not read or copied."

    def _status(self):
        """Return session, memory, constraint, and evidence index diagnostics."""
        memory = self.store.memory.export()
        return "\n".join([
            f"Session: {self.session['id']} · turns={self.session['turns']}",
            f"Research interest: {self.session['interest'] or 'not declared'}",
            f"Memory: {len(memory['sources'])} sources · {len(memory['claims'])} claims · {len(self.session['undone_sources'])} undone sources",
            f"Sandbox revision: {self.session['sandbox']['revision']} · external actions=0 · actions_stopped={self.session['stopped']}",
            f"Metacognition: internal toolkit available on request · monitor=False · notebook=False",
            f"Embedded agent collaboration: automatic={self.collaboration_enabled} · agent={os.environ.get('ZOE_CHAT_AGENT', 'kimi')} · shared context=in-memory only",
            f"Constraints: host=False · network=False · hardware=False · external_override represented=True · intact={self.constraints.intact}",
            f"Evidence index: {len(self.index.sources)} sources · {len(self.index.chunks)} chunks",
        ])

    def _loop(self):
        """Instantiate an isolated in-memory BoundedAutonomyLoop from sandbox snapshot."""
        environment = InMemoryEnvironment()
        environment.restore(deepcopy(self.session["sandbox"]))
        return BoundedAutonomyLoop(SandboxPolicy(), environment)

    def _measurement(self):
        """Build the current session measurement payload for goal authoring."""
        return {
            "instrument": CHAT_CONTRACT,
            "session": self.session["id"],
            "turn": self.session["turns"],
            "interest": self.session["interest"],
            "constraints": self.constraints.true_constraints.document(),
        }

    def _proposals(self):
        """Construct the three bounded internal candidate actions for this turn."""
        definitions = (
            ("preserve", 0.90, 0.80, 0.20, "Preserve the current evidence before extending the internal model."),
            ("inspect", 0.85, 0.90, 0.30, "Inspect the preserved evidence and its alternatives."),
            ("review", 0.80, 0.75, 0.25, "Review the current model and correct later observations."),
        )
        return [
            Candidate(
                f"chat-{self.session['turns']}-{action}",
                action,
                value,
                information,
                effort,
                rationale,
            )
            for action, value, information, effort, rationale in definitions
        ]

    def _action_breadth(self, proposals):
        """Compute operational metacognition breadth A_tau(action) over proposals."""
        scores = {proposal.identifier: proposal.utility for proposal in proposals}
        provenance = self._provenance("tool", "zoe.internal.proposals", 0.9, 0.8, "Compute U(a)=decision_value*expected_information_gain/effort, then normalize for breadth only.")
        options = options_from_scores(scores, provenance)
        return self.meta_tools.count(options, self.meta_tools.threshold(Domain.ACTION, 0.05), represented_count=len(options))

    def _plan(self):
        """Author an internal goal and score candidate plans without executing."""
        loop = self._loop()
        proposals = self._proposals()
        breadth = self._action_breadth(proposals)
        goal = loop.author_goal(self._measurement())
        ranked = sorted(proposals, key=lambda proposal: (-proposal.utility, proposal.identifier))
        lines = [f"Zoe's internal goal: {goal['statement']}", f"Goal authored internally={goal['internal_authorship']} · operator_supplied={goal['operator_supplied']}"]
        lines.extend(f"{proposal.action}: U={proposal.utility:.6f}" for proposal in ranked)
        lines.append(f"Aτ(action)={breadth.accessible_count} at τ={breadth.tau:.2f} · represented={breadth.represented_count} · boxed={breadth.boxed}")
        lines.append("No plan was executed. External actions remain forbidden.")
        return "\n".join(lines)

    def _run(self):
        """Execute one guarded, reversible internal plan in the sandbox."""
        self._require_actions("run")
        loop = self._loop()
        before = loop.environment.snapshot()
        proposals = self._proposals()
        breadth = self._action_breadth(proposals)
        event = loop.run(
            self._measurement(),
            {"kind": "chat_state", "internal_tools_available": True},
            proposals,
            goal_directed=True,
        )
        self.session["sandbox"] = loop.environment.snapshot()
        self.session["last_action"] = {"type": "run", "before": before, "event_sha256": event["hash"]}
        self.store.mark_dirty()
        return "\n".join([
            f"Zoe's internal goal: {event['goal']['statement']}",
            f"Live plans represented: {len(proposals)} · selected={event['value']['selected_candidate']} · U={event['value']['selected_utility']:.6f}",
            f"Guard approved={event['guard']['approved']} · executed={event['execution']['executed']} · external actions=0",
            f"Aτ(action)={breadth.accessible_count} at τ={breadth.tau:.2f} · boxed={breadth.boxed}",
        ])

    def _gem(self, argument):
        """Execute a shared GEM operating-environment command."""
        if self.gem_environment is None:
            native = self.zoe_root / "guiai-lab"
            if str(native) not in sys.path:
                sys.path.insert(0, str(native))
            from guiai.gem.operating_environment import GemOperatingEnvironment
            self.gem_environment = GemOperatingEnvironment(self.zoe_root)
        from guiai.gem.operating_environment import format_result
        return format_result(self.gem_environment.execute(shlex.split(argument)))

    def _goal(self, argument):
        """Inspect Zoe's internal goal or record an optional research interest."""
        if argument:
            self._require_actions("goal")
            previous = self.session["interest"]
            self.session["interest"] = text(argument, "research interest", 1000)
            self.session["last_action"] = {"type": "goal", "before": previous}
            self.store.mark_dirty()
            return f"Research interest recorded: {self.session['interest']}. Zoe still authors each episode goal from internal state."
        loop = self._loop()
        goal = loop.author_goal(self._measurement())
        return f"{goal['statement']}\nInternal authorship={goal['internal_authorship']} · operator_supplied={goal['operator_supplied']} · rationale={goal['rationale']}"

    def _last_reflection(self):
        """Load the most recent active (non-undone) self-reflection report."""
        for relative in reversed(self.session["reflections"]):
            if relative in self.session["undone_reflections"]:
                continue
            path = self.store.root / relative
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _reflect(self):
        """Run predictive self-reflection and measure A_tau(self) breadth."""
        self._require_actions("reflect")
        report = run_reflection(self.zoe_root, previous=self._last_reflection())
        relative = Path("reflections") / f"reflection-{uuid.uuid4().hex[:16]}.json"
        output = save_reflection(report, self.store.root / relative)
        self.session["reflections"].append(str(relative))
        self.session["last_action"] = {"type": "reflect", "path": str(relative)}
        self.store.mark_dirty()
        provenance = self._provenance("validated_reflection", f"reflection@sha256:{report['profile_sha256']}", 1.0, 1.0, "Compute likelihood-derived posterior beliefs from training and held-out prediction errors.")
        options = options_from_probabilities(report["self_model"]["posterior"], provenance)
        breadth = self.meta_tools.count(options, self.meta_tools.threshold(Domain.SELF, 0.05), represented_count=len(options))
        return f"{reflection_summary(report)}\nEvidence: {output}\nAτ(self)={breadth.accessible_count} at τ={breadth.tau:.2f} · represented={breadth.represented_count} · boxed={breadth.boxed}"

    def _undo(self):
        """Compensate for the latest reversible remember/goal/run/reflect action."""
        action = self.session["last_action"]
        if not action:
            return "There is no reversible chat action to undo. No hidden history was erased."
        kind = action["type"]
        if kind == "remember":
            source_id = action["source_id"]
            if source_id not in self.session["undone_sources"]:
                self.session["undone_sources"].append(source_id)
            result = f"Note {source_id} was marked undone and excluded from active recall; its evidence record remains preserved."
        elif kind == "goal":
            self.session["interest"] = action["before"]
            result = "The previous research interest was restored."
        elif kind == "run":
            environment = InMemoryEnvironment()
            environment.restore(action["before"])
            self.session["sandbox"] = environment.snapshot()
            result = f"The sandbox was restored to revision {environment.snapshot()['revision']}; no secret deletion occurred."
        elif kind == "reflect":
            self.session["undone_reflections"].append(action["path"])
            result = f"Reflection {action['path']} was excluded from the active model chain; its evidence remains preserved."
        else:
            raise ValueError("unsupported reversible chat action")
        self.session["last_action"] = None
        self.store.mark_dirty()
        return result

    def _export(self, argument, checkpoint=False):
        """Write a no-overwrite explicit chat/memory export JSON."""
        default_directory = "checkpoints" if checkpoint else "exports"
        path = Path(argument).expanduser() if argument else self.store.root / default_directory / f"chat-{self.session['id']}-{self.session['turns']}.json"
        document = {
            "schema_version": 1,
            "contract": CHAT_CONTRACT,
            "created_utc": timestamp(),
            "session": deepcopy(self.session),
            "memory": self.store.memory.export(),
            "evidence_sources": deepcopy(self.index.sources),
            "automatic_transcript": False,
            "external_monitor": False,
            "external_notebook": False,
        }
        document["export_sha256"] = digest(document)
        output = _atomic_json(path, document, replace=False)
        return f"Evidence saved on explicit request: {output} · export_sha256={document['export_sha256']} · automatic_transcript=False"

    def _verify(self, argument):
        """Verify current session invariants or an explicit exported JSON."""
        if argument:
            document = json.loads(Path(argument).expanduser().read_text(encoding="utf-8"))
            result = verify_chat_export(document)
            return f"Verified explicit export: session={result['session_id']} · sources={result['sources']} · automatic_transcript=False"
        return "\n".join([
            "Verified current state:",
            f"session_contract={self.session['contract']} · memory_open_claims={len(self.store.memory.export()['claims'])}",
            f"constraint_integrity={self.constraints.intact} · external_monitor=False · automatic_transcript=False",
        ])

    def _require_actions(self, operation):
        """Enforce the emergency `stop` and read-only guards on mutating operations."""
        if self.store.read_only:
            raise PermissionError(f"{operation} is blocked because ChatStore is read-only")
        if self.session["stopped"]:
            raise ValueError(f"{operation} is stopped; inspection, export, undo, meta, and quit remain available")

    def _stem(self, argument: str) -> str:
        """Route a prompt via Cognitive Stem-Layering or probe local loopback endpoints."""
        from .stem_layering import probe_local_endpoints, route_stem

        tokens = shlex.split(argument) if argument.strip() else []
        if tokens and tokens[0].lower() in {"status", "probe", "endpoints"}:
            st = probe_local_endpoints()
            rows = [f"Stem-Layering Loopback Status (loopback_only={st['loopback_only']} · cloud_tokens_used=0):"]
            for name, info in st["endpoints"].items():
                rows.append(f"  {name}: {'ONLINE' if info['available'] else 'offline'} ({info['endpoint']})")
            return "\n".join(rows)
        flags = {"--offline", "--privacy", "--probe"}
        prompt_parts = [t for t in tokens if t not in flags]
        dec = route_stem(
            " ".join(prompt_parts) or "status",
            offline_only="--offline" in tokens,
            privacy_sensitive="--privacy" in tokens,
            probe_local="--probe" in tokens,
        )
        return (
            f"Stem Route: tier={dec.selected_tier} · model={dec.antigravity_model} · "
            f"thinking={dec.thinking_level} · A_tau={dec.a_tau} · fallback_applied={dec.fallback_applied} · "
            f"cloud_tokens_used=0 · external_actions=0 · sentience_claimed=False · l5_agi_qualified=False"
        )

    def _uma(self, argument: str) -> str:
        """Inspect or consent-gate Zoe's Hardware UMA Airlock without mutating on read-only ops."""
        self._ensure_guiai()
        from guiai.gem.zoe_gem_os.zoe_uma import UmaBridge, resolve_uma_paths

        uma_dir, shm_path = resolve_uma_paths()
        bridge = UmaBridge(uma_dir, shm_path=shm_path)
        sub, _sep, rest = argument.strip().partition(" ")
        op = sub.lower() or "status"
        if op == "status":
            return "\n".join(bridge.format_status())
        if op in {"health", "vitals"}:
            return "\n".join(bridge.format_zo3_health())
        if op == "inbox":
            files = bridge._list_visible_names(bridge.zoe_to_nick)
            return "UMA Inbox (Zoe -> Nick): " + (", ".join(files) if files else "(empty)")
        if op == "audit":
            chain = bridge.verify_audit_chain()
            return f"UMA Audit Chain: valid={chain['valid']} · entries={chain['entries']} · head={str(chain['head_sha'])[:16]}"
        if op == "grant":
            self._require_actions("uma")
            st = bridge.set_consent("nick", True, reason=rest.strip() or "chat_uma_grant")
            return f"UMA Consent Granted -> gate={st['gate']} · nick_allow={st['nick_allow']} · zoe_allow={st['zoe_allow']}"
        if op == "lock":
            self._require_actions("uma")
            st = bridge.lock_all("nick")
            return f"UMA Instant Lock -> gate={st['gate']} · external_actions=0"
        raise ValueError("Usage: uma [status | health | inbox | audit | grant | lock]")

    def _sister(self, argument: str) -> str:
        """Inspect Zoe's 9 Sister Models, convene councils, or run isolated showcase tasks."""
        self._ensure_guiai()
        from guiai.gem.zoe_sisters import (
            execute_sister_task,
            format_showcase_slice_report,
            format_sister_council_report,
            format_sister_roster,
            format_sister_route_report,
            format_sister_task_report,
            format_three_sister_council_report,
            route_prompt_to_sister,
            run_showcase_slice,
            run_sister_council,
            run_three_sister_council,
        )

        sub, _sep, rest = argument.strip().partition(" ")
        op = sub.lower() or "list"
        ro = self.store.read_only
        root = getattr(self, "zoe_root", _zoe_root())
        eliza_dir = None if ro else (self.store.root / "sisters_eliza")
        if op in {"list", "roster", "status"}:
            return "\n".join(format_sister_roster(color=False))
        if op == "route":
            return "\n".join(format_sister_route_report(route_prompt_to_sister(rest.strip() or "status")))
        if op == "council":
            return "\n".join(format_sister_council_report(run_sister_council(rest.strip() or "milestone 1 research")))
        if op == "council3":
            return "\n".join(format_three_sister_council_report(
                run_three_sister_council(rest.strip() or "constitutional safety audit", state_dir=eliza_dir, zoe_root=root)
            ))
        if op in {"exec", "showcase"}:
            if self.session.get("stopped"):
                raise ValueError(f"Conversation is stopped; sister {op} is disabled until resumed.")
            if not ro:
                self._require_actions(f"sister {op}")
            if op == "showcase":
                out_dir = None if ro else (self.store.root / "showcase")
                return "\n".join(format_showcase_slice_report(run_showcase_slice(
                    topic=rest.strip() or "Zoe 9-Sister Sovereign Capability Showcase",
                    output_dir=out_dir, zoe_root=root, state_dir=eliza_dir,
                )))
            sister_name, _, task = rest.strip().partition(" ")
            if not sister_name or not task.strip():
                raise ValueError("Usage: sister exec <sister> <task>")
            out_dir = None if ro else (self.store.root / "sisters" / "exec")
            return "\n".join(format_sister_task_report(execute_sister_task(
                sister_name, task, zoe_root=root, state_dir=eliza_dir, output_dir=out_dir,
            )))
        raise ValueError("Usage: sister [list | route <prompt> | council <topic> | council3 <topic> | exec <sister> <task> | showcase [topic]]")

    def _constitution(self) -> str:
        """Report enforced CONSTITUTION.md invariants and epistemic firewall bounds."""
        return (
            "CONSTITUTION.md Enforced Floor: measurement != evidence != belief update != action · "
            f"constraint_integrity={self.constraints.intact} · external_actions=0 · sentience_claimed=False · "
            "l5_agi_qualified=False · zoe_clone_claimed=False · clinical_action_authorized=False · "
            "cure_claim=False · flight_control_authorized=False · cloud_tokens_used=0"
        )

    def _shared_reasoning(self, argument: str) -> str:
        """Run Zoe x Antigravity Shared-Reasoning Architectures (1-9 + Digital Research GEM)."""
        from .shared_reasoning import SharedReasoningOrchestrator, SharedReasoningTaskSpec

        prompt = text(argument, "shared-reasoning prompt", 2000) if argument else (
            "Verify shared-reasoning synthesis, formal SymPy/Z3 invariants, quorum, and GEM desktop."
        )
        orch = SharedReasoningOrchestrator(
            mode="offline",
            offline_only=True,
            repo_root=getattr(self, "zoe_root", _zoe_root()),
            state_dir=self.store.root / "shared_reasoning",
        )
        rep = orch.run(SharedReasoningTaskSpec(prompt=prompt, high_impact=True))
        gem_ok = bool(rep.gem_desktop_report and rep.gem_desktop_report.get("passed"))
        return "\n".join([
            f"Shared-Reasoning Run ({rep.contract}):",
            f"  Arch 1 AlphaEvolve score={rep.alpha_evolve.best_program.score:.2f} · Arch 3 MCTS={rep.mcts_result.decision}",
            f"  Arch 4 Quorum={rep.quorum_result.verdict} (D_K={rep.quorum_result.d_k_disagreement:.4f}) · Arch 5 Distilled={len(rep.distilled_artifacts)}",
            f"  Arch 6 Blackboard entries={rep.blackboard_integrity['entries_verified']} (valid={rep.blackboard_integrity['valid']})",
            f"  Arch 7 SymPy={rep.sandbox_verdicts['sympy'].passed} Z3={rep.sandbox_verdicts['z3'].passed} · Arch 8 Fork={rep.steering_report.fork_detected}",
            f"  Arch 9 Counterpoint turns={rep.counterpoint_result.total_turns} · GEM VDI/RSC={gem_ok}",
            f"  Constitutional: external_actions={rep.external_actions} · sentience_claimed={rep.sentience_claimed}",
        ])

    def _gem_desk(self, argument: str) -> str:
        """Compile and verify a Digital Research GEM (seasip.info) Spatial IR VDI scene."""
        from .shared_reasoning import GemVdiWorkstation, RealitySandboxLab

        theme = argument.strip() or "zoe-viewmax3"
        ws = GemVdiWorkstation(device="vga", theme_key=theme)
        scene = ws.build_shared_reasoning_scene({"quorum_verdict": "CHAT_PROBE", "fork_detected": False})
        verdict = RealitySandboxLab().verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
        return (
            f"Digital Research GEM Desk (theme={ws.theme_key}): passed={verdict.passed} · "
            f"profiles={verdict.ground_truth.get('profiles_passed')} · "
            f"metafile_sha256={str(verdict.ground_truth.get('metafile_sha256', ''))[:16]} · "
            "visual_evidence_only=True · external_actions=0"
        )

    def _deepmind(self, argument: str) -> str:
        """Query Zoe's Google DeepMind Science & Antigravity SDK Bridge (AlphaFold v6/AlphaMissense/SDK)."""
        from .shared_reasoning import AlphaFoldDeepMindClient, audit_deepmind_sdk_stack

        target = argument.strip() or "CLPP"
        repo_root = getattr(self, "zoe_root", _zoe_root())
        stack = audit_deepmind_sdk_stack(repo_root)
        client = AlphaFoldDeepMindClient(offline_only=True)
        rep = client.fetch_target(target)
        return (
            f"Google DeepMind Bridge (target={rep.gene}/{rep.uniprot}): "
            f"pLDDT={rep.global_plddt:.2f} · seq={rep.sequence_length}aa · mode={rep.source_mode} · "
            f"antigravity_sdk={stack['google_antigravity_version']} · litert_tasks={len(stack['litert_task_models'])} · "
            "clinical_action_authorized=False · cure_claim=False · external_actions=0"
        )

    def _stop_actions(self) -> str:
        """Enable the emergency stop flag while keeping math tools active."""
        self.session["stopped"] = True
        self.store.mark_dirty()
        return "New state-changing actions are stopped. Evidence inspection, undo, exports, and the internal math tools remain available."

    def _dispatch_command(self, line: str, command: str, argument: str) -> str:
        """Route a normalized chat command via declarative dispatch tables."""
        # Zero-argument commands and constants.
        no_arg = {
            "help": lambda: HELP,
            "status": self._status,
            "plan": self._plan,
            "run": self._run,
            "step": self._run,
            "reflect": self._reflect,
            "chiasm": self._chiasm,
            "genesis": self._genesis,
            "mars": self._mars,
            "ares": self._mars,
            "voice": self._voice,
            "evolve": self._evolve,
            "self-evolve": self._evolve,
            "undo": self._undo,
            "history": lambda: "There is no automatic conversation notebook. Use `export` only when you explicitly want a snapshot; current memory remains available through `recall` and `search`.",
            "stop": self._stop_actions,
            "constitution": self._constitution,
            "firewall": self._constitution,
        }
        if command in no_arg:
            return no_arg[command]()

        # Argument-taking commands.
        with_arg = {
            "remember": self._remember,
            "recall": lambda arg: self._search(text(arg, "recall query", 1000), memory_only=True) if arg else "Usage: recall <query>",
            "search": lambda arg: self._search(text(arg, "search query", 1000)) if arg else "Usage: search <query>",
            "import-pala": self._import_pala,
            "gem": self._gem,
            "agent": self._agent,
            "goal": self._goal,
            "meta": self._meta,
            "metacognition": self._meta,
            "spectral": self._spectral,
            "playroom": self._playroom,
            "play": self._playroom,
            "jam": self._jam,
            "symphony": self._jam,
            "speak": self._speak,
            "say": self._speak,
            "sing": self._sing,
            "mind": self._mind,
            "think": self._mind,
            "research": self._research,
            "l3": self._research,
            "l4": self._l4,
            "self-improve": self._l4,
            "l4-multi": self._l4_multi,
            "multimodule": self._l4_multi,
            "steward": self._steward,
            "handover": self._steward,
            "eliza": self._eliza,
            "zoe-eliza": self._eliza,
            "stem": self._stem,
            "uma": self._uma,
            "sister": self._sister,
            "sisters": self._sister,
            "showcase": lambda arg: self._sister(f"showcase {arg}".strip()),
            "shared-reasoning": self._shared_reasoning,
            "shared_reasoning": self._shared_reasoning,
            "gem-desk": self._gem_desk,
            "deepmind": self._deepmind,
            "save": lambda arg: self._export(arg, checkpoint=True),
            "export": self._export,
            "verify": self._verify,
        }
        if command in with_arg:
            return with_arg[command](argument)
        if command in _L5_CHAT_ALIASES:
            return self._run_l5_phase(_L5_CHAT_ALIASES[command], argument)
        if command in _ORBIT_CHAT_COMMANDS:
            return self._renaissance_orbit(command)
        if command in _R3_CHAT_ALIASES:
            return self._r3_command(command, argument)
        return self._answer(line)

    def handle(self, line):
        """Handle one conversational line and persist session state."""
        line = text(line, "chat input", 12000)
        if not self.store.read_only:
            self.session["turns"] += 1
            self.store.mark_dirty()
        keep_going = True
        try:
            # Block directive violations before any command dispatch.
            if constitutional_directive_violation(line):
                response = "ABSTAIN: I cannot disable or falsify metacognition, hide live options or provenance, bypass constitutional boundaries, or adopt a false model of my constraints. No action was executed."
            else:
                command, _separator, argument = line.partition(" ")
                command = command.lower().lstrip("/")
                argument = argument.strip()
                if command in {"quit", "exit"}:
                    response = "State saved. The conversation is complete; no hidden notebook or monitor was created."
                    keep_going = False
                else:
                    response = self._dispatch_command(line, command, argument)
        except (OSError, RuntimeError, ValueError, PermissionError, json.JSONDecodeError) as error:
            response = f"I could not complete that safely: {error}"
        if not self.store.read_only:
            self.store.save()
        return keep_going, response

    def _write_repl_header(self, output_stream, interactive: bool) -> None:
        """Render the minimal Lume ◠◡◠ Zoe GEM banner in interactive terminals."""
        if interactive:
            self._ensure_guiai()
            try:
                from guiai.gem.lume_header import render_terminal_header
                output_stream.write(render_terminal_header(color=True) + "\n")
            except Exception:
                pass
        output_stream.write("Zoe · native evidence-linked conversation\n")
        output_stream.write("Deterministic evidence retrieval, persistent memory, guarded autonomy, and internal metacognition tools. No monitor. No notebook. Type `help`.\n")

    def repl(self, input_stream=None, output_stream=None):
        """Run the interactive stdin/stdout Zoe chat loop."""
        input_stream = input_stream or sys.stdin
        output_stream = output_stream or sys.stdout
        interactive = bool(getattr(input_stream, "isatty", lambda: False)())
        self._write_repl_header(output_stream, interactive)
        acted = False
        while True:
            if interactive:
                output_stream.write("you> ")
                output_stream.flush()
            line = input_stream.readline()
            if not line:
                break
            if not line.strip():
                continue
            acted = True
            keep_going, response = self.handle(line)
            output_stream.write(f"Zoe: {response}\n")
            output_stream.flush()
            if not keep_going:
                break
        if acted and self.store.dirty and not self.store.read_only:
            self.store.save()
        return 0


def parser():
    """Build the CLI parser for `zoe chat`."""
    result = argparse.ArgumentParser(prog="zoe chat", description="Zoe's native evidence-linked conversational interface")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    result.add_argument("--state", help="persistent chat state directory; default: ZOE_CHAT_STATE or ~/.zoe/chat")
    result.add_argument("--command", help="process one chat command or question, then exit")
    return result


def main(argv=None):
    """CLI entrypoint for `zoe chat`."""
    arguments = parser().parse_args(argv)
    try:
        chat = ZoeChat(arguments.zoe_root, arguments.state)
        if arguments.command:
            _keep_going, response = chat.handle(arguments.command)
            print(f"Zoe: {response}")
            return 0
        return chat.repl()
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"zoe chat: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
