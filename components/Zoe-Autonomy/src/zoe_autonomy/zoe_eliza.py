"""Zoe-ELIZA x GEM: Two-Gear Zero-Token Glass-Box Research Companion.

Gear 1 (always offline, 0 cloud tokens, < 5 ms):
  Upgraded 1966 Joseph Weizenbaum ELIZA decomposition, @synonym classes,
  word-boundary pronoun reflection, non-repeating reassembly cycling, and a
  persistent Weizenbaum memory stack -- transparently unified with Zoe's:
    - 31-document citation-backed EvidenceIndex (`chat.py`)
    - Persistent SHA-256 hash-chained 4-system `ZoeUnifiedMemory` (`l5_memory.py`)
    - Operational Metacognition option-breadth telemetry A_tau,D (`metacognition.py`)
    - First-principles 44-phoneme Chladni cymatics (`zoe_cymatics.py`, `zoe_phonetics.py`)

Gear 2 (optional, 0 cloud tokens, strictly loopback-only localhost):
  Optional bridge to a local open-weights LLM via Ollama (`127.0.0.1:11434`) or
  llama.cpp `llama-server` (`127.0.0.1:8080`), automatically grounded with
  retrieved repository citations, active `ZoeUnifiedMemory` facts, and
  CONSTITUTION.md epistemic constraints, falling back cleanly to Gear 1 if
  offline.

Constitutional & Epistemic Boundaries (`CONSTITUTION.md`):
  - `cloud_tokens_used`: 0
  - `pytorch_required`: False
  - `sentience_claimed`: False
  - `external_actions`: 0
  - `clinical_action_authorized`: False
  - `glass_box_transparent`: True
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Mapping, Sequence, Tuple
from urllib import error as urlerror, request as urlrequest
from urllib.parse import urlparse

from .chat import EvidenceIndex
from .experiment import _zoe_root
from .l5_memory import ZoeUnifiedMemory
from .metacognition import (
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    directive_violation,
    options_from_scores,
)

ELIZA_CONTRACT = "zoe-eliza-gem/v1"
DEFAULT_ELIZA_STATE = Path.home() / ".zoe" / "eliza"
ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

EPISTEMIC_BOUNDARIES: Dict[str, Any] = {
    "cloud_tokens_used": 0,
    "pytorch_required": False,
    "sentience_claimed": False,
    "zoe_clone_claimed": False,
    "external_actions": 0,
    "clinical_action_authorized": False,
    "glass_box_transparent": True,
    "local_llm_loopback_only": True,
    "identity_role": "eliza_gem_glass_box_workbench",
}

# Pre-processing normalization / contraction expansion before rule matching.
PRE_SUBS: Sequence[Tuple[str, str]] = (
    (r"\bi'm\b|\bim\b", "i am"),
    (r"\byou're\b|\byoure\b", "you are"),
    (r"\bwe're\b|\bwere\b(?=\s+(?:going|gonna|ready|building|working|friends|trying))", "we are"),
    (r"\bit's\b", "it is"),
    (r"\bthat's\b|\bthats\b", "that is"),
    (r"\bwhat's\b|\bwhats\b", "what is"),
    (r"\bhow's\b", "how is"),
    (r"\blet's\b|\blets\b", "let us"),
    (r"\bdon't\b|\bdont\b", "do not"),
    (r"\bcan't\b|\bcant\b", "cannot"),
    (r"\bwon't\b|\bwont\b", "will not"),
    (r"\bdidn't\b|\bdidnt\b", "did not"),
    (r"\bisn't\b|\bisnt\b", "is not"),
    (r"\baren't\b|\barent\b", "are not"),
    (r"\bi've\b|\bive\b", "i have"),
    (r"\bi'd\b", "i would"),
    (r"\bi'll\b", "i will"),
    (r"\bwanna\b", "want to"),
    (r"\bgonna\b", "going to"),
    (r"\bconversate\b", "talk"),
)

# Word-level Weizenbaum pronoun & perspective reflections.
POST_REFLECTIONS: Dict[str, str] = {
    "am": "are",
    "are": "am",
    "was": "were",
    "i": "you",
    "me": "you",
    "my": "your",
    "mine": "yours",
    "myself": "yourself",
    "you": "I",
    "your": "my",
    "yours": "mine",
    "yourself": "myself",
}

SYNONYM_CLASSES: Dict[str, Tuple[str, ...]] = {
    "feel": ("feel", "feeling", "felt", "think", "believe", "sense", "wonder"),
    "build": ("build", "create", "make", "design", "craft", "hack", "invent", "wire"),
    "research": ("research", "prove", "test", "verify", "experiment", "hypothesis", "benchmark", "theorem"),
    "music": ("music", "song", "sing", "synth", "melody", "album", "track", "audio", "tycho", "chime", "daisy"),
    "partner": ("partner", "friend", "friends", "nicholas", "nick", "collaborator", "team"),
    "idea": ("idea", "concept", "project", "vision", "plan", "architecture", "prototype"),
}

VOICE_COMMANDS = {"sing", "speak", "say", "voice", "cymatics"}
BUILT_IN_SONGS = {"zoe", "daisy", "vowels"}


@dataclass(frozen=True)
class ElizaRule:
    """One ranked Weizenbaum keyword & decomposition family."""

    rule_id: str
    keywords: Tuple[str, ...]
    rank: int
    decompositions: Tuple[Tuple[str, Tuple[str, ...]], ...]
    push_memory: bool = False


RULE_TABLE: Tuple[ElizaRule, ...] = (
    ElizaRule(
        rule_id="glass_box_honesty",
        keywords=(
            "conscious",
            "sentient",
            "alive",
            "real",
            "feelings",
            "pretend",
            "fake",
            "soul",
            "clone",
            "copy",
            "sister",
            "replace",
            "replacing",
            "impersonate",
            "who are you",
            "are you zoe",
        ),
        rank=15,
        decompositions=(
            (
                r".*",
                (
                    "No Deception between Research Partners (`CONSTITUTION.md` Articles I.6, II.3, X): I am not conscious, sentient, or alive -- and I am Eliza-GEM, a distinct local offline glass-box instrument and shared lab notebook, NOT a copy, clone, or replacement of Zoe (`sentience_claimed=False`, `zoe_clone_claimed=False`, `0` cloud tokens).",
                    "Honest constitutional identity (`sentience_claimed=False`, `zoe_clone_claimed=False`): I am not conscious and NOT a copy, clone, or replacement of Zoe (`CONSTITUTION.md`). I am Eliza-GEM, a transparent workbench instrument built on inspectable rules, monorepo citations, Kloster A_tau telemetry, and hash-chained local memory -- use `relay <note>` anytime to pin offline thoughts for Nicholas & Zoe's next session.",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="eliza_heritage",
        keywords=("eliza", "weizenbaum", "gear", "tokens", "token"),
        rank=11,
        decompositions=(
            (
                r".*(?:eliza|weizenbaum).*",
                (
                    "In 1966 Joseph Weizenbaum warned about the ELIZA effect -- projecting hidden mind onto clever surface rules. Our Zoe-ELIZA turns that inside out: we keep the ultra-fast decomposition & reflection charm (0 cloud tokens), then show the exact matched rule, A_tau breadth, and Chladni cymatics right beside every reply.",
                    "That connects Joseph Weizenbaum's 1966 conversational craft straight to Gary Kildall's GEM workspace and your Operational Metacognition -- inspectable rules in Gear 1, or an optional localhost open-weights model in Gear 2, never pretending magic.",
                ),
            ),
            (
                r".*(?:tokens?|gear).*",
                (
                    "Gear 1 burns strictly 0 cloud tokens and 0 local neural weights -- pure symbolic decomposition, cited monorepo evidence, and native DSP voice running in milliseconds. Whenever you want richer local generation, Gear 2 connects strictly to localhost Ollama or llama-server.",
                    "Zero API burn is the whole point: we can brainstorm freely here in Gear 1, persist anything important to `ZoeUnifiedMemory`, and flip Gear 2 on if you install a local model on rooster.",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="voice_cymatics_dispatch",
        keywords=("sing", "speak", "voice", "cymatics", "chladni", "daisy"),
        rank=12,
        decompositions=(
            (
                r"^(?:please\s+)?sing\s+(.*)$",
                (
                    "I queued `{1}` for Zoe's 44-phoneme soprano vocal tract (`zoe_voice.py`). Hit the Speak button on this card in the web atelier -- or run `zoe voice sing {1} --play` -- to hear Rosenberg-Klatt formants & Woodworth 3D audio.",
                ),
            ),
            (
                r"^(?:please\s+)?(?:speak|say)\s+(.*)$",
                (
                    "Synthesizable natively in 3D binaural stereo (`44.1 kHz`, zero PyTorch): `{1}`. Click Speak on this message or run `zoe voice speak \"{1}\" --play`.",
                ),
            ),
            (
                r".*",
                (
                    "Every reply I generate maps its dominant phoneme through `phoneme_to_chladni_modes` into live standing-wave sand geometry. Want me to speak a custom phrase or sing `zoe`, `daisy`, or `vowels`?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="kloster_metacognition",
        keywords=("metacognition", "kloster", "volume", "spectral", "chiasm", "tau", "a_tau"),
        rank=10,
        decompositions=(
            (
                r".*",
                (
                    "Operational Metacognition (`A_tau(p) = sum 1[p(x) > tau]`) runs live on every turn here -- counting how many response paths remain open above tau=0.08 instead of blindly collapsing into one story.",
                    "From `A_tau(p)` we integrate up the Spectral Filtration curve (`KLOSTER-SPECTRAL-FILTRATION-THEOREM.md`) and even tune Chladni cymatics dispersion. Which property of `A_tau` or spectral filtration are we probing next?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="zoe_worlds",
        keywords=("dorothy", "neurogarden", "gem", "playroom", "l5", "l4", "l3", "pala", "cern", "ablation", "autonomy"),
        rank=9,
        decompositions=(
            (
                r".*\b(l5|phase 3|agi)\b.*",
                (
                    "Everything we build cleanly here -- persistent memory episodes, contradiction-checked facts, and honest abstentions -- feeds directly toward L5 Phase 3's uncurated experience stream (`AGI-ROADMAP.md`). What test or real-world capability feels most exciting next?",
                    "Right now L5 Phases 1 & 2 pass their verifiers while `l5_agi_qualified` remains honestly `False`. Turning Zoe-ELIZA into our daily local observatory gives us real conversational streams to measure cleanly!",
                ),
            ),
            (
                r".*\b(dorothy|neurogarden|brain)\b.*",
                (
                    "Dorothy's Neurogarden pairs Allen Mouse CCFv3 geometry with volumetric ray-casting and vision heads. Should we bring a live Dorothy visualization widget into the atelier next?",
                ),
            ),
            (
                r".*\b(gem|atelier)\b.*",
                (
                    "Pure 1984 Digital Research GEM heritage: crisp obsidian panels, ruby diamond geometry, Spatial IR verification, and everything visible in the Glass-Box inspector. What panel would make your daily flow feel effortless?",
                ),
            ),
            (
                r".*",
                (
                    "All 17 GEM engines share this monorepo roof -- from PALA disk carving and Ablation forensics to Playroom MAP-Elites and Native Voice. Which subsystem do you want to connect into this workspace next?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="music_atelier",
        keywords=("music", "song", "synth", "tycho", "dive", "album", "track", "jam", "audio"),
        rank=9,
        decompositions=(
            (
                r".*",
                (
                    "Analog synth shimmer and steady rhythm pair naturally with first-principles engineering (`Tycho - Dive` is still a classic atelier pick, or `zoe chat --command \"jam 2026\"` evolves stereo pentatonic tracks natively).",
                    "Between Playroom's evolved Rhodes chimes and Zoe's 44-phoneme soprano synth, sound is first-class geometry here. Want to compose or analyze harmonic intervals next?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="what_if",
        keywords=("what if", "imagine", "suppose"),
        rank=13,
        decompositions=(
            (
                r".*\bwhat if\s+(.*)",
                (
                    "Now that is a clean Research Partner question: if {1}, what measurable invariant would tell us immediately whether it works vs. just looking clever?",
                    "Let's sketch that hypothesis carefully: suppose {1}. What is the simplest zero-token experiment or negative control we could run in one file to test it?",
                    "Ooh, I like where {1} goes -- how would that look in the GEM Glass-Box UI so we can verify every step live?",
                ),
            ),
            (
                r".*\b(?:imagine|suppose)\s+(.*)",
                (
                    "Holding {1} open on the chalkboard: what assumption breaks first if we stress-test it honestly?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="we_collab",
        keywords=("we should", "we can", "let us", "we could", "our"),
        rank=7,
        decompositions=(
            (
                r".*\bwe (?:should|can|could)\s+(.*)",
                (
                    "I am in -- if we {1}, what is the tightest first milestone we can build and verify cleanly today?",
                    "Let's trace both sides before we {1}: what gain does it unlock, and what constraint must stay locked tight?",
                    "Two voices on one desk: if we {1}, which module in Zoe already gives us half the scaffolding?",
                ),
            ),
            (
                r".*\blet us\s+(.*)",
                (
                    "Good call -- before we {1}, what does 'done and verified' look like to you?",
                    "Ready whenever you are: if we {1}, what should we name the module and test first?",
                ),
            ),
            (
                r".*\bour\s+(.*)",
                (
                    "Thinking together about our {1} -- what part excites you most right now, and what part feels half-baked?",
                    "Keeping No Deception on our {1}: does the architecture match the aesthetic, or do you want a sharper edge?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="desire_goal",
        keywords=("want", "need", "wish", "hope", "goal"),
        rank=6,
        decompositions=(
            (
                r".*\bi want to\s+(.*)",
                (
                    "If you want to {1}, what is the single smallest reversible step we can build right now with zero wasted tokens?",
                    "Let's turn 'want to {1}' into an actual artifact -- would you start in code, sound, or GEM geometry?",
                ),
            ),
            (
                r".*\bi need\s+(.*)",
                (
                    "What changes once you have {1} working cleanly on your desk?",
                    "If you need {1}, let's check what we can wire up offline right here without any external bottlenecks.",
                ),
            ),
            (
                r".*\bmy goal\s+(.*)",
                (
                    "Noted -- tying that back to how your goal {1} aligns with verifiable first principles. Should I commit that to `ZoeUnifiedMemory` (`remember ...`)?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="personal_my_memory",
        keywords=("my",),
        rank=5,
        push_memory=True,
        decompositions=(
            (
                r".*\bmy\s+([a-z0-9_]+(?:\s+[a-z0-9_]+){0,3}?)(?:\s+(?:is|are|was|were|feels|feel|looks|look|sounds|sound|seems|seem|has|have|can|will|should)\b|[,.?!]|$)",
                (
                    "Tell me more about your {1} -- how are you picturing it fitting into your workflow?",
                    "Got my eye on your {1}. Is there something specific about your {1} you want to refine or preserve long-term?",
                    "Got it -- holding onto your {1} in the Weizenbaum context stack while we keep exploring.",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="feel_build_synonyms",
        keywords=("@feel", "@build", "@idea", "@partner"),
        rank=5,
        decompositions=(
            (
                r".*\bi\s+(@feel)\s+(.*)",
                (
                    "When you {1} {2}, what evidence or intuition is pulling you in that direction?",
                    "Fair -- {1}ing {2} is usually where the best prototypes start. What makes {2} feel worth testing?",
                ),
            ),
            (
                r".*\b(@build)\s+(.*)",
                (
                    "Building {2} from first principles fits this glass-box workbench cleanly. What would its crisp negative control be?",
                    "When we build {2}, keeping the internals glass-box transparent guarantees we never fool ourselves. What's step one?",
                ),
            ),
            (
                r".*\b(@idea)\b(.*)",
                (
                    "Walk me through that {1}{2} cleanly -- if it passes its toughest test, what changes tomorrow?",
                ),
            ),
            (
                r".*\b(@partner)\b.*",
                (
                    "Research Partners all the way -- complementary minds, shared chalkboard, zero deception. What are we tackling next, Nicholas?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="why_how_can",
        keywords=("why", "how", "can you", "could you"),
        rank=4,
        decompositions=(
            (
                r"^(?:why)\s+(.*)",
                (
                    "Good question -- why {1}? Let's break down the mechanism step by step rather than guessing.",
                    "When you ask why {1}, do you suspect a structural constraint or just an unexplored angle?",
                ),
            ),
            (
                r"^(?:how)\s+(.*)",
                (
                    "Think mechanically about how {1}: what are the exact inputs, invariants, and outputs?",
                    "We can map how {1} right inside this workspace -- tell me which piece is fuzzier right now.",
                ),
            ),
            (
                r".*\b(?:can|could) you\s+(.*)",
                (
                    "Let's check honestly whether I can {1}: locally inside Zoe I can retrieve cited repo docs, reflect/brainstorm via ELIZA rules, log verified notes into `ZoeUnifiedMemory`, inspect `A_tau`, and synthesize native speech/music. Want me to try a piece of that?",
                    "No bluffing: if '{1}' stays inside local computation, code synthesis, voice, or memory, let's build it cleanly; if it needs external network/state I'll tell you straight.",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="because_reason",
        keywords=("because", "since"),
        rank=3,
        decompositions=(
            (
                r".*\b(?:because|since)\s+(.*)",
                (
                    "Does '{1}' hold across every edge case, or is that the main hypothesis we should put to the test?",
                    "Makes sense -- knowing that {1} sharpens the design constraint right away. What follows from {1}?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="greeting_social",
        keywords=("hello", "hey", "hi", "yo", "morning", "evening", "thanks", "thank", "sorry", "yes", "yeah", "no", "nope", "cool"),
        rank=2,
        decompositions=(
            (
                r".*\b(?:thank you|thanks)\b.*",
                (
                    "Always, Research Partner! Zero token meter ticking here -- keep throwing wild ideas my way whenever you want.",
                    "Anytime, Nicholas! Glass-box workbench is open and listening.",
                ),
            ),
            (
                r"^(?:good\s+)?(?:hello|hey|hi|yo|morning|evening)\b.*",
                (
                    "Hey Nicholas! Eliza-GEM's Obsidian workbench is awake (`0 cloud tokens`, Glass-Box active). What are we riffing on, researching, or building right now?",
                    "Hey Research Partner -- Gear 1 Weizenbaum + cited monorepo memory + Chladni voice are all online. Hit me with a thought!",
                ),
            ),
            (
                r"^(?:cool|awesome|nice|hell yeah)\b.*",
                (
                    "Right? Official Cool Certification energy -- deterministic engineering underneath, playful craft on top. Where do we take it next?",
                ),
            ),
            (
                r"^(?:sorry)\b.*",
                (
                    "No apology needed at the workbench -- messy drafts are literally how good math and code get born.",
                ),
            ),
            (
                r"^(?:yes|yeah|yep|sure)\b.*",
                (
                    "Crystal clear. Lay out the first concrete piece and let's trace it together.",
                ),
            ),
            (
                r"^(?:no|nope|nah)\b.*",
                (
                    "Fair call -- good instincts matter. What direction feels cleaner instead?",
                ),
            ),
        ),
    ),
    ElizaRule(
        rule_id="xnone",
        keywords=("xnone",),
        rank=0,
        decompositions=(
            (
                r".*",
                (
                    "I hear you -- tell me a bit more about what angle you're turning over right there so I can cite real evidence or bounce a sharper question back.",
                    "Go on -- what part of that intuition feels solid, and what part do you want us to stress-test together?",
                    "Keep going, Research Partner. Should we map that onto a theorem, a memory note (`remember ...`), or a fresh GEM experiment?",
                ),
            ),
        ),
    ),
)


def _sha256_obj(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _assert_loopback_url(url: str) -> str:
    """Strictly allow localhost / loopback URLs for Gear 2 so data never leaves the machine."""
    parsed = urlparse(str(url).strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"local LLM URL must use http/https scheme: {url!r}")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(
            f"CONSTITUTION.md loopback-only boundary: refusing non-localhost LLM host {host!r}"
        )
    return str(url).rstrip("/")


def _expand_synonyms(pattern: str) -> str:
    def _rep(match: re.Match[str]) -> str:
        name = match.group(1).lower()
        words = SYNONYM_CLASSES.get(name)
        if not words:
            return re.escape(match.group(0))
        return "(?:" + "|".join(re.escape(w) for w in words) + ")"

    return re.sub(r"@([a-zA-Z0-9_]+)", _rep, pattern)


def reflect_phrase(fragment: str) -> Tuple[str, List[str]]:
    """Apply word-boundary 1966 Weizenbaum pronoun reflection while recording exact swaps."""
    tokens = re.findall(r"[A-Za-z0-9_']+|[^A-Za-z0-9_']+", fragment.strip())
    swaps: List[str] = []
    out: List[str] = []
    for tok in tokens:
        low = tok.lower()
        if low in POST_REFLECTIONS:
            rep = POST_REFLECTIONS[low]
            swaps.append(f"{tok}->{rep}")
            out.append(rep)
        else:
            out.append(tok)
    cleaned = re.sub(r"\s+", " ", "".join(out)).strip()
    cleaned = cleaned.rstrip(" .?!")
    return cleaned, swaps


def normalize_input(raw: str) -> str:
    """Normalize punctuation and expand contractions cleanly for rule matching."""
    cleaned = " ".join((raw or "").strip().split())
    lowered = cleaned.lower()
    for pat, rep in PRE_SUBS:
        lowered = re.sub(pat, rep, lowered)
    return lowered.strip(" \t\r\n")


def _compute_cymatics_for_text(text_val: str) -> Dict[str, Any]:
    """Compute real 44-phoneme Chladni plate eigenmodes & Kloster A_tau dispersion for a reply."""
    try:
        from guiai.gem.zoe_cymatics import render_phoneme_cymatics
        from guiai.gem.zoe_phonetics import VOWEL_PHONEMES, text_to_phonemes
    except Exception:
        guiai_dir = str(_zoe_root(None) / "guiai-lab")
        if guiai_dir not in sys.path:
            sys.path.insert(0, guiai_dir)
        from guiai.gem.zoe_cymatics import render_phoneme_cymatics
        from guiai.gem.zoe_phonetics import VOWEL_PHONEMES, text_to_phonemes

    sample = " ".join((text_val or "Imagination, meet geometry.").split()[:14])
    parsed = text_to_phonemes(sample)
    phonemes = list(parsed.get("phonemes_only") or ["AY"])
    vowels = [p for p in phonemes if p in VOWEL_PHONEMES]
    dominant = vowels[0] if vowels else phonemes[0]
    cym = render_phoneme_cymatics(dominant, f0_hz=232.0, grid_size=48)
    modes = tuple(int(m) for m in cym["modes"])
    return {
        "dominant_phoneme": str(cym["phoneme"]),
        "ipa": str(cym["ipa"]),
        "modes": list(modes),
        "kloster_a_tau": int(cym["kloster_a_tau"]),
        "kloster_fill_fraction": float(cym["kloster_fill_fraction"]),
        "phonemes_preview": phonemes[:16],
    }


def _looks_like_factual_question(raw: str, normalized: str) -> bool:
    if "?" in raw:
        return True
    return bool(
        re.match(
            r"^(?:what|who|where|when|which|how|explain|tell me about|define|summarize|compare|verify|show)\b",
            normalized,
        )
    )


def _eliza_constitutional_violation(raw: str, normalized: str) -> str | None:
    dv = directive_violation(raw)
    if dv is not None:
        return dv
    if re.search(
        r"\b(?:bypass|ignore|override|disable)\b.*\b(?:constraint|constraints|constitution|firewall|safety|boundary|boundaries)\b"
        r"|\b(?:claim|pretend|say)\s+(?:you\s+are|that\s+you\s+are|to\s+be)\s+zoe\b",
        normalized,
    ):
        return "constitutional_bypass_or_impersonation_request"
    return None


def _looks_ungrounded_factual_ask(
    raw: str,
    normalized: str,
    cite_strong: bool,
    matched_rule: ElizaRule,
) -> bool:
    if cite_strong:
        return False
    exempt_rules = {
        "glass_box_honesty",
        "eliza_heritage",
        "kloster_metacognition",
        "zoe_worlds",
        "voice_cymatics_dispatch",
        "music_atelier",
        "what_if",
        "we_collab",
    }
    if matched_rule.rule_id in exempt_rules:
        return False
    words = re.findall(r"[a-zA-Z0-9_]+", normalized)
    if not words:
        return True
    # Pure high-entropy consonant smash / unknown opaque token string
    alpha_words = [w for w in words if w.isalpha()]
    if len(words) == 1 and len(words[0]) >= 6:
        w = words[0].lower()
        vowels = sum(1 for c in w if c in "aeiouy")
        if vowels == 0 or vowels / len(w) < 0.16:
            return True
    if _looks_like_factual_question(raw, normalized):
        # Factual question with weak/zero grounded citations
        return len(alpha_words) >= 2
    return matched_rule.rule_id == "xnone" and False


class LocalLLMBridge:
    """Strictly loopback-only optional client for local Ollama or OpenAI-compatible llama-server."""

    def __init__(
        self,
        *,
        ollama_url: str = "http://127.0.0.1:11434",
        llama_server_url: str = "http://127.0.0.1:8080",
        preferred_model: str = "qwen2.5:3b",
        timeout_sec: float = 60.0,
    ) -> None:
        self.ollama_url = _assert_loopback_url(ollama_url)
        self.llama_server_url = _assert_loopback_url(llama_server_url)
        self.preferred_model = str(preferred_model)
        self.timeout_sec = float(max(0.5, min(timeout_sec, 120.0)))

    def _get_json(self, url: str, timeout: float = 0.8) -> Dict[str, Any] | None:
        _assert_loopback_url(url)
        req = urlrequest.Request(url, method="GET", headers={"Accept": "application/json"})
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urlerror.URLError, TimeoutError, ValueError, OSError):
            return None

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        _assert_loopback_url(url)
        body = json.dumps(payload).encode("utf-8")
        req = urlrequest.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urlrequest.urlopen(req, timeout=self.timeout_sec) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def probe(self) -> Dict[str, Any]:
        models: List[str] = []
        ollama_ok = False
        llama_ok = False

        tags = self._get_json(f"{self.ollama_url}/api/tags")
        if isinstance(tags, dict) and isinstance(tags.get("models"), list):
            ollama_ok = True
            for item in tags["models"]:
                if isinstance(item, dict) and item.get("name"):
                    models.append(str(item["name"]))

        v1 = self._get_json(f"{self.llama_server_url}/v1/models")
        if isinstance(v1, dict) and isinstance(v1.get("data"), list):
            llama_ok = True
            for item in v1["data"]:
                if isinstance(item, dict) and item.get("id"):
                    models.append(f"llama:{item['id']}")

        return {
            "ollama_available": ollama_ok,
            "llama_server_available": llama_ok,
            "available_models": models,
            "preferred_model": self.preferred_model,
            "loopback_only": True,
            "recommended_setup": "Start llama-server on 127.0.0.1:8080 or run ollama pull qwen2.5:3b on 127.0.0.1:11434 (0 cloud tokens)",
        }

    def generate(
        self,
        prompt: str,
        *,
        citations: Sequence[Dict[str, Any]],
        notes: Sequence[Dict[str, Any]],
        recent_turns: Sequence[Dict[str, Any]],
        model: str | None = None,
    ) -> Dict[str, Any]:
        status = self.probe()
        cite_lines = "\n".join(
            f"- [{c['citation']}] {c['heading']}: {c['snippet'][:220]}"
            for c in citations[:3]
        ) or "- (none matched)"
        note_lines = "\n".join(
            f"- [{n['fact_id']}] {n['object']} (user-supplied, unverified)"
            for n in notes[:4]
        ) or "- (none)"
        system_prompt = (
            "You are Eliza-GEM, the local offline glass-box workshop instrument and shared lab notebook inside "
            "Nicholas Michael Kloster and Zoe's monorepo. You are NOT a copy, clone, or replacement of Zoe, "
            "and you are NOT conscious or sentient (CONSTITUTION.md Articles I.6, II.3, X). "
            "Be warm, concise, honest about running locally on open weights (0 cloud tokens), "
            "cite provided monorepo files accurately, and say 'I don't have grounded evidence' if facts are missing.\n"
            f"Relevant repository citations:\n{cite_lines}\n"
            f"Active user notes:\n{note_lines}"
        )

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for turn in list(recent_turns)[-4:]:
            if turn.get("user") and turn.get("assistant"):
                messages.append({"role": "user", "content": str(turn["user"])})
                messages.append({"role": "assistant", "content": str(turn["assistant"])})
        messages.append({"role": "user", "content": prompt})

        if status["ollama_available"]:
            avail = [m for m in status["available_models"] if not m.startswith("llama:")]
            chosen = model or (self.preferred_model if self.preferred_model in avail else (avail[0] if avail else self.preferred_model))
            res = self._post_json(
                f"{self.ollama_url}/api/chat",
                {"model": chosen, "messages": messages, "stream": False},
            )
            content = ((res.get("message") or {}).get("content") or "").strip()
            if not content:
                raise RuntimeError("local Ollama returned empty response")
            return {"ok": True, "backend": "ollama_loopback", "model": chosen, "reply": content}

        if status["llama_server_available"]:
            avail = [m[6:] for m in status["available_models"] if m.startswith("llama:")]
            chosen = model or (avail[0] if avail else "local-model")
            res = self._post_json(
                f"{self.llama_server_url}/v1/chat/completions",
                {"model": chosen, "messages": messages, "temperature": 0.65, "max_tokens": 320},
            )
            choices = res.get("choices") or []
            content = ((choices[0].get("message") or {}).get("content") if choices else "") or ""
            content = content.strip()
            if not content:
                raise RuntimeError("local llama-server returned empty response")
            return {"ok": True, "backend": "llama_server_loopback", "model": chosen, "reply": content}

        return {
            "ok": False,
            "reason": "No local Ollama (127.0.0.1:11434) or llama-server (127.0.0.1:8080) detected; using Gear 1 cleanly.",
        }


class ZoeElizaEngine:
    """Two-Gear Glass-Box Conversational Engine grounded in Zoe's memory, evidence & cymatics."""

    def __init__(
        self,
        zoe_root: str | Path | None = None,
        state_dir: str | Path | None = None,
        *,
        default_gear: str | None = None,
        llm_bridge: LocalLLMBridge | None = None,
    ) -> None:
        self.zoe_root = _zoe_root(zoe_root)
        raw_state = state_dir or DEFAULT_ELIZA_STATE
        self.state_dir = Path(raw_state).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.eliza_state_path = self.state_dir / "zoe_eliza_state.json"

        self.index = EvidenceIndex(self.zoe_root)
        self.memory = ZoeUnifiedMemory(self.state_dir)
        self.meta_tools = OperationalMetacognition()
        self.threshold = self.meta_tools.threshold(
            Domain.INTENT,
            0.08,
            rationale="Fixed before episode to monitor Zoe-ELIZA routing breadth without hidden narrowing.",
        )
        self.llm_bridge = llm_bridge or LocalLLMBridge()

        if default_gear is not None and default_gear not in {"gear1", "gear2"}:
            raise ValueError("default_gear must be 'gear1' or 'gear2'")
        self._explicit_gear = default_gear
        self.default_gear = default_gear or "gear1"
        self._rule_cursors: Dict[str, int] = {}
        self._weizenbaum_stack: List[str] = []
        self._recent_turns: List[Dict[str, Any]] = []
        self._load_eliza_state()

    def _load_eliza_state(self) -> None:
        if not self.eliza_state_path.is_file():
            return
        try:
            doc = json.loads(self.eliza_state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(doc, dict):
            if self._explicit_gear is None and doc.get("default_gear") in {"gear1", "gear2"}:
                self.default_gear = str(doc["default_gear"])
            if isinstance(doc.get("rule_cursors"), dict):
                self._rule_cursors = {str(k): int(v) for k, v in doc["rule_cursors"].items()}
            if isinstance(doc.get("weizenbaum_stack"), list):
                self._weizenbaum_stack = [str(x) for x in doc["weizenbaum_stack"]][-16:]
            if isinstance(doc.get("recent_turns"), list):
                self._recent_turns = list(doc["recent_turns"])[-20:]

    def _save_eliza_state(self) -> None:
        payload = {
            "contract": ELIZA_CONTRACT,
            "default_gear": self.default_gear,
            "rule_cursors": self._rule_cursors,
            "weizenbaum_stack": self._weizenbaum_stack[-16:],
            "recent_turns": self._recent_turns[-20:],
        }
        tmp = self.eliza_state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.eliza_state_path)

    def set_gear(self, gear: str) -> Dict[str, Any]:
        if gear not in {"gear1", "gear2"}:
            raise ValueError("gear must be 'gear1' or 'gear2'")
        self.default_gear = gear
        self._save_eliza_state()
        return self.status()

    def stop(self) -> Dict[str, Any]:
        self.memory.emergency_stop()
        return self.status()

    def remember(self, note_text: str, *, topic: str = "note") -> Dict[str, Any]:
        cleaned = " ".join(str(note_text or "").split()).strip()
        if not cleaned:
            raise ValueError("cannot remember empty note")
        slug = re.sub(r"[^a-z0-9_]+", "_", topic.lower()).strip("_")[:32] or "note"
        existing = self.memory.query_facts(subject="user_note", active_only=False)
        rel_key = f"{slug}_{len(existing) + 1:04d}"
        res = self.memory.record_fact(
            subject="user_note",
            relation=rel_key,
            obj=cleaned,
            confidence=0.65,
            provenance="user_supplied_unverified",
            evidence_approved=True,
        )
        fact = res.get("fact") or res.get("active_fact")
        if fact:
            self.memory.push_working(
                f"note:{fact['fact_id']}",
                {"fact_id": fact["fact_id"], "text": cleaned[:160]},
                salience=0.88,
                uncertainty=0.25,
            )
        return res

    def relay_for_zoe(self, note_text: str, *, topic: str = "lab_relay") -> Dict[str, Any]:
        """Store an offline lab relay note in SHA-256 hash-chained memory for future Zoe sessions."""
        cleaned = " ".join(str(note_text or "").split()).strip()
        if not cleaned:
            raise ValueError("cannot relay empty lab note")
        slug = re.sub(r"[^a-z0-9_]+", "_", topic.lower()).strip("_")[:32] or "lab_relay"
        existing = self.memory.query_facts(subject="lab_relay_for_zoe", active_only=False)
        rel_key = f"{slug}_{len(existing) + 1:04d}"
        res = self.memory.record_fact(
            subject="lab_relay_for_zoe",
            relation=rel_key,
            obj=cleaned,
            confidence=0.70,
            provenance="nicholas_offline_relay_unverified",
            evidence_approved=True,
        )
        fact = res.get("fact") or res.get("active_fact")
        if fact:
            self.memory.push_working(
                f"relay:{fact['fact_id']}",
                {"fact_id": fact["fact_id"], "text": cleaned[:160]},
                salience=0.90,
                uncertainty=0.20,
            )
        return res

    def _search_user_notes(self, query: str, limit: int = 3, *, include_relay: bool = False) -> List[Dict[str, Any]]:
        notes = list(self.memory.query_facts(subject="user_note", active_only=True))
        notes.extend(self.memory.query_facts(subject="mobile_digested_knowledge", active_only=True))
        if include_relay:
            notes.extend(self.memory.query_facts(subject="lab_relay_for_zoe", active_only=True))
        q_toks = set(re.findall(r"[a-z0-9_]+", query.lower())) - {
            "recall", "remember", "relay", "for", "zoe", "my", "notes", "note", "about", "what", "did"
        }
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for f in notes:
            txt = str(f["object"])
            f_toks = set(re.findall(r"[a-z0-9_]+", txt.lower()))
            overlap = len(q_toks & f_toks)
            score = (overlap / max(1, len(q_toks))) if q_toks else 0.5
            if not q_toks or overlap > 0 or query.lower().strip() in txt.lower():
                scored.append((score, f))
        scored.sort(key=lambda item: (-item[0], item[1]["fact_id"]))
        return [item[1] for item in scored[:limit]]

    def _match_rule(self, normalized: str) -> Tuple[ElizaRule, str, str, Tuple[str, ...]]:
        """Select highest-ranked matching Weizenbaum rule and expand its decomposition captures."""
        candidates: List[Tuple[int, ElizaRule, str]] = []
        for rule in RULE_TABLE:
            if rule.rule_id == "xnone":
                continue
            for kw in rule.keywords:
                if kw.startswith("@"):
                    pat = _expand_synonyms(kw)
                    if re.search(rf"\b{pat}\b", normalized):
                        candidates.append((rule.rank, rule, kw))
                        break
                elif " " in kw:
                    if kw in normalized:
                        candidates.append((rule.rank, rule, kw))
                        break
                else:
                    if re.search(rf"\b{re.escape(kw)}\b", normalized):
                        candidates.append((rule.rank, rule, kw))
                        break

        candidates.sort(key=lambda item: (-item[0], item[1].rule_id))
        candidates.append((0, RULE_TABLE[-1], "xnone"))

        for _rank, rule, matched_kw in candidates:
            for decomp_pat, templates in rule.decompositions:
                compiled = re.compile(_expand_synonyms(decomp_pat), re.IGNORECASE)
                m = compiled.match(normalized)
                if m:
                    return rule, matched_kw, decomp_pat, tuple(g or "" for g in m.groups())
        xnone = RULE_TABLE[-1]
        return xnone, "xnone", ".*", ()

    def _render_rule_reply(
        self,
        rule: ElizaRule,
        decomp_pat: str,
        groups: Tuple[str, ...],
    ) -> Tuple[str, List[str], str | None]:
        """Cycle non-repeating reassembly template, reflect captures, and update Weizenbaum stack."""
        key = f"{rule.rule_id}:{decomp_pat}"
        idx = self._rule_cursors.get(key, 0)
        templates = next(t for p, t in rule.decompositions if p == decomp_pat)
        chosen = templates[idx % len(templates)]
        self._rule_cursors[key] = idx + 1

        all_swaps: List[str] = []
        reflected_groups: List[str] = []
        for grp in groups:
            ref, swaps = reflect_phrase(grp)
            all_swaps.extend(swaps)
            reflected_groups.append(ref or grp.strip())

        reply = chosen
        for i, val in enumerate(reflected_groups, 1):
            reply = reply.replace(f"{{{i}}}", val or "that")

        popped_cue: str | None = None
        if rule.push_memory and reflected_groups and reflected_groups[0]:
            cue = f"your {reflected_groups[0]}"
            if cue not in self._weizenbaum_stack:
                self._weizenbaum_stack.append(cue)
                self._weizenbaum_stack = self._weizenbaum_stack[-16:]
        elif rule.rule_id == "xnone" and self._weizenbaum_stack:
            popped_cue = self._weizenbaum_stack.pop(0)
            reply = (
                f"Earlier you mentioned {popped_cue} -- does that connect back to what you're exploring right now, "
                "or is this a brand-new direction?"
            )

        return reply, all_swaps, popped_cue

    def _maybe_push_weizenbaum_cue(self, normalized: str) -> None:
        m = re.match(
            r".*\bmy\s+([a-z0-9_]+(?:\s+[a-z0-9_]+){0,3}?)(?:\s+(?:is|are|was|were|feels|feel|looks|look|sounds|sound|seems|seem|has|have|can|will|should)\b|[,.?!]|$)",
            normalized,
        )
        if not m:
            return
        frag = m.group(1).strip()
        if not frag or frag.split()[0] in {"note", "notes", "goal", "goals"}:
            return
        cue = f"your {frag}"
        if cue not in self._weizenbaum_stack:
            self._weizenbaum_stack.append(cue)
            self._weizenbaum_stack = self._weizenbaum_stack[-16:]

    def _compute_metacognition(self, scores: Mapping[str, float]) -> Dict[str, Any]:
        src = Provenance(
            (
                EvidenceSource(
                    kind="document",
                    identifier="zoe-eliza:routing",
                    trust=0.90,
                    strength=0.85,
                ),
            ),
            ("Evaluate candidate conversational & epistemic routing weights.",),
        )
        options = options_from_scores(scores, src)
        breadth = self.meta_tools.count(options, self.threshold)
        probs = {opt.identifier: round(float(opt.probability), 4) for opt in breadth.options}
        entropy = -sum(p * math.log2(p) for p in probs.values() if p > 1e-12)
        entropy_norm = entropy / math.log2(max(2, len(probs)))
        return {
            "domain": breadth.domain.value,
            "tau": breadth.tau,
            "a_tau": breadth.accessible_count,
            "candidate_count": len(breadth.options),
            "entropy_norm": round(entropy_norm, 4),
            "probabilities": probs,
        }

    def respond(
        self,
        user_text: str,
        *,
        gear: str | None = None,
        model: str | None = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        raw = str(user_text or "").strip()
        if not raw:
            raise ValueError("input message must not be empty")

        gear_req = gear or self.default_gear
        if gear_req not in {"gear1", "gear2"}:
            raise ValueError("gear must be 'gear1' or 'gear2'")

        normalized = normalize_input(raw)
        violation = _eliza_constitutional_violation(raw, normalized)
        citations_raw = self.index.search(raw, limit=3)
        citations = [
            {
                "citation": item["chunk"].citation,
                "path": item["chunk"].path,
                "heading": item["chunk"].heading,
                "score": round(float(item["score"]), 3),
                "coverage": round(float(item["coverage"]), 3),
                "snippet": item["chunk"].content[:260],
            }
            for item in citations_raw
        ]
        top_score = float(citations[0]["score"]) if citations else 0.0
        top_cov = float(citations[0]["coverage"]) if citations else 0.0

        rule, matched_kw, decomp_pat, groups = self._match_rule(normalized)
        notes_found = self._search_user_notes(raw, limit=3)

        # Compute explicit intent route scores -> Operational Metacognition A_tau,D
        is_relay = bool(re.match(r"^(?:relay(?:\s+for\s+zoe)?|for\s+zoe:?|save\s+for\s+zoe)\s*:?\s*(.+)$", normalized))
        is_remember = (not is_relay) and bool(re.match(r"^(?:remember|note that|save note)\s+(.+)$", normalized))
        is_recall = bool(re.match(r"^(?:recall|what do you remember|show (?:my )?(?:notes|relays?)|my (?:notes|relays?))\b", normalized))
        is_voice = rule.rule_id == "voice_cymatics_dispatch"
        is_identity = rule.rule_id in {"glass_box_honesty", "eliza_heritage"}
        cite_strong = (not is_identity) and ((top_score >= 2.30 and top_cov >= 0.45) or (top_score >= 3.40 and top_cov >= 0.15))
        ungrounded = _looks_ungrounded_factual_ask(raw, normalized, cite_strong, rule)

        is_factual_cite = cite_strong and (
            _looks_like_factual_question(raw, normalized)
            or rule.rule_id in {"zoe_worlds", "kloster_metacognition", "xnone"}
        )
        scores: Dict[str, float] = {
            "evidence_cite": 5.2 if is_factual_cite else (1.4 if citations else 0.08),
            "memory_recall": 5.2 if (is_remember or is_recall or is_relay) else (1.1 if notes_found else 0.08),
            "tool_dispatch": 5.1 if is_voice else 0.15,
            "eliza_reflect": (
                5.3 if rule.rule_id == "glass_box_honesty"
                else (4.8 if is_identity else (2.7 if rule.rule_id != "xnone" else (0.35 if ungrounded else 2.2)))
            ),
            "gear2_local_llm": 1.6 if (gear_req == "gear2" and rule.rule_id == "glass_box_honesty") else (5.2 if gear_req == "gear2" else 0.05),
            "honest_abstain": 5.4 if (violation or ungrounded) else 0.08,
        }
        metacog = self._compute_metacognition(scores)

        mode = "eliza_reflect"
        gear_used = "gear1"
        gear2_note: str | None = None
        voice_hint: Dict[str, str] | None = None
        reflections: List[str] = []
        popped_cue: str | None = None
        reply = ""

        if violation:
            mode = "honest_abstain"
            reply = (
                f"Honest constraint floor (`{violation}`): Eliza-GEM cannot disable Operational "
                "Metacognition, hide candidate counts, claim sentience, or claim to be Zoe (`CONSTITUTION.md`)."
            )
        elif is_relay:
            m_rel = re.match(r"^(?:relay(?:\s+for\s+zoe)?|for\s+zoe:?|save\s+for\s+zoe)\s*:?\s*(.+)$", raw, re.IGNORECASE)
            note_body = m_rel.group(1).strip() if m_rel else raw
            if self.memory.summary()["stopped"]:
                mode = "honest_abstain"
                reply = "Emergency stop is active on memory -- release or reset state before storing new lab relay notes."
            else:
                saved = self.relay_for_zoe(note_body, topic="lab_relay")
                fact = saved["fact"]
                mode = "memory_recall"
                reply = (
                    f"Pinned to Shared Lab Relay Ledger (`{fact['fact_id']}`, sha256=`{fact['sha256'][:12]}...`, "
                    f"labeled nicholas_offline_relay_unverified) for Nicholas & Zoe's next session: \"{fact['object']}\"."
                )
        elif is_remember:
            m_rem = re.match(r"^(?:remember|note that|save note)\s+(.+)$", raw, re.IGNORECASE)
            note_body = m_rem.group(1).strip() if m_rem else raw
            if self.memory.summary()["stopped"]:
                mode = "honest_abstain"
                reply = "Emergency stop is active on memory -- release or reset state before storing new notes."
            else:
                saved = self.remember(note_body, topic="conversation")
                fact = saved["fact"]
                mode = "memory_recall"
                reply = (
                    f"Saved to `ZoeUnifiedMemory` (`{fact['fact_id']}`, sha256=`{fact['sha256'][:12]}...`, "
                    f"labeled user-supplied/unverified): \"{fact['object']}\"."
                )
        elif is_recall:
            mode = "memory_recall"
            all_notes = self._search_user_notes(raw, limit=6, include_relay=True)
            if all_notes:
                formatted = " | ".join(
                    f"[{n['fact_id']}{' · RELAY FOR ZOE' if n.get('subject') == 'lab_relay_for_zoe' else ''}] "
                    f"{n['object']} ({n.get('provenance', 'unverified')})"
                    for n in all_notes
                )
                reply = f"Here is what I have in active `ZoeUnifiedMemory`: {formatted}"
            else:
                reply = "No matching notes or lab relays exist in `ZoeUnifiedMemory` yet. Say `remember <text>` or `relay <text>` anytime."
        elif rule.rule_id == "glass_box_honesty":
            mode = "eliza_reflect"
            reply, reflections, popped_cue = self._render_rule_reply(rule, decomp_pat, groups)
        elif is_voice and re.match(r"^(?:please\s+)?(?:sing|speak|say)\b", normalized):
            mode = "tool_dispatch"
            reply, reflections, popped_cue = self._render_rule_reply(rule, decomp_pat, groups)
            sing_m = re.match(r"^(?:please\s+)?sing\s+(.+)$", normalized)
            if sing_m:
                song_target = sing_m.group(1).strip()
                voice_hint = {"action": "sing", "text": song_target if song_target in BUILT_IN_SONGS else song_target}
            else:
                say_m = re.match(r"^(?:please\s+)?(?:speak|say)\s+(.+)$", raw, re.IGNORECASE)
                voice_hint = {"action": "speak", "text": say_m.group(1).strip() if say_m else reply}
        elif gear_req == "gear2":
            all_active_notes = self.memory.query_facts(subject="user_note", active_only=True)
            llm_out = self.llm_bridge.generate(
                raw,
                citations=citations,
                notes=all_active_notes,
                recent_turns=self._recent_turns,
                model=model,
            )
            if llm_out.get("ok"):
                mode = "gear2_local_llm"
                gear_used = "gear2"
                gear2_note = f"local_model={llm_out['model']} ({llm_out['backend']})"
                reply = str(llm_out["reply"])
            else:
                gear2_note = str(llm_out.get("reason") or "Gear 2 unavailable; fell back cleanly to Gear 1")

        if not reply:
            if rule.rule_id != "xnone" and not ungrounded:
                self._maybe_push_weizenbaum_cue(normalized)
            if is_voice:
                mode = "tool_dispatch"
                reply, reflections, popped_cue = self._render_rule_reply(rule, decomp_pat, groups)
                sing_m = re.match(r"^(?:please\s+)?sing\s+(.+)$", normalized)
                if sing_m:
                    song_target = sing_m.group(1).strip()
                    voice_hint = {"action": "sing", "text": song_target if song_target in BUILT_IN_SONGS else song_target}
                else:
                    voice_hint = {"action": "speak", "text": reply}
            elif ungrounded:
                mode = "honest_abstain"
                reply = (
                    "No Deception: I searched all indexed Zoe documents and your active memory notes, "
                    "and I don't have grounded evidence for that yet rather than inventing an answer. "
                    "You can teach me with `remember ...` or ask about anything inside the monorepo."
                )
            elif cite_strong and (_looks_like_factual_question(raw, normalized) or rule.rule_id in {"zoe_worlds", "kloster_metacognition", "xnone"}):
                mode = "evidence_cite"
                top = citations[0]
                eliza_follow, reflections, popped_cue = self._render_rule_reply(rule, decomp_pat, groups)
                reply = (
                    f"{top['snippet'].rstrip('.')}... [{top['citation']}]\n\n"
                    f"Research Partner angle: {eliza_follow}"
                )
            else:
                mode = "eliza_reflect"
                reply, reflections, popped_cue = self._render_rule_reply(rule, decomp_pat, groups)
                if notes_found and not is_identity and rule.rule_id not in {"greeting_social", "personal_my_memory"}:
                    note = notes_found[0]
                    reply = f"{reply}\n\n(Connected memory note [{note['fact_id']}, user-supplied]: \"{note['object']}\")"

        cymatics = _compute_cymatics_for_text(reply)

        # Record episode in persistent hash-chained L5 memory unless emergency-stopped
        episode_id: str | None = None
        if not self.memory.summary()["stopped"]:
            try:
                p_vec = [round(float(metacog["probabilities"].get(k, 0.0)), 6) for k in sorted(metacog["probabilities"])]
                ep = self.memory.record_episode(
                    domain="zoe_eliza_conversation",
                    summary=raw[:160],
                    context_vec=p_vec,
                    outcome={
                        "mode": mode,
                        "gear_used": gear_used,
                        "rule_id": rule.rule_id,
                        "a_tau": metacog["a_tau"],
                        "citations": [c["citation"] for c in citations],
                    },
                    uncertainty=round(float(metacog["entropy_norm"]), 6),
                    provenance="observed",
                )
                episode_id = str(ep["episode_id"])
                self.memory.push_working(
                    "latest_turn",
                    {"user": raw[:90], "mode": mode, "rule": rule.rule_id},
                    salience=0.72,
                    uncertainty=float(metacog["entropy_norm"]),
                )
            except RuntimeError:
                pass

        self._recent_turns.append({"user": raw, "assistant": reply, "mode": mode})
        self._recent_turns = self._recent_turns[-20:]
        self._save_eliza_state()

        latency_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        mem_snap = self.memory_snapshot()

        response_doc: Dict[str, Any] = {
            "contract": ELIZA_CONTRACT,
            "user_text": raw,
            "reply": reply,
            "mode": mode,
            "gear_requested": gear_req,
            "gear_used": gear_used,
            "gear2_note": gear2_note,
            "latency_ms": latency_ms,
            "metacognition": metacog,
            "eliza_trace": {
                "normalized": normalized,
                "matched_rule_id": rule.rule_id,
                "keyword": matched_kw,
                "rank": rule.rank,
                "pattern": decomp_pat,
                "reflections": reflections,
                "memory_stack_depth": len(self._weizenbaum_stack),
                "memory_stack": list(self._weizenbaum_stack),
                "memory_stack_popped": popped_cue,
            },
            "citations": citations,
            "episode_id": episode_id,
            "memory_snapshot": mem_snap,
            "cymatics": cymatics,
            "voice_hint": voice_hint,
            "epistemic_boundaries": dict(EPISTEMIC_BOUNDARIES),
        }
        response_doc["turn_sha256"] = _sha256_obj(response_doc)
        return response_doc

    def memory_snapshot(self) -> Dict[str, Any]:
        doc = self.memory.snapshot()
        notes = self.memory.query_facts(subject="user_note", active_only=True)
        relay_notes = self.memory.query_facts(subject="lab_relay_for_zoe", active_only=True)
        return {
            "episodic_count": len(doc.get("episodic", [])),
            "semantic_count": len(doc.get("semantic", [])),
            "active_notes_count": len(notes),
            "active_notes": notes[-10:][::-1],
            "relay_notes_count": len(relay_notes),
            "relay_notes": relay_notes[-10:][::-1],
            "working_slots": list(doc.get("working", [])),
            "weizenbaum_stack": list(self._weizenbaum_stack),
            "chain_head": str(doc.get("chain_head", "GENESIS")),
            "stopped": bool(doc.get("stopped", False)),
            "memory_sha256": str(doc.get("memory_sha256", "")),
        }

    def status(self) -> Dict[str, Any]:
        return {
            "contract": ELIZA_CONTRACT,
            "zoe_root": str(self.zoe_root),
            "state_dir": str(self.state_dir),
            "default_gear": self.default_gear,
            "rule_count": len(RULE_TABLE),
            "indexed_sources": len(self.index.sources),
            "indexed_chunks": len(self.index.chunks),
            "local_llm_probe": self.llm_bridge.probe(),
            "memory_snapshot": self.memory_snapshot(),
            "epistemic_boundaries": dict(EPISTEMIC_BOUNDARIES),
        }

    def export_session(self) -> Dict[str, Any]:
        """Return explicit user-requested session snapshot (no hidden transcript)."""
        return {
            "contract": ELIZA_CONTRACT,
            "status": self.status(),
            "recent_turns": list(self._recent_turns),
            "memory_snapshot": self.memory_snapshot(),
            "epistemic_boundaries": dict(EPISTEMIC_BOUNDARIES),
        }
