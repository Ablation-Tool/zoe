"""Cognitive Stem-Layering: Kloster A_tau(p) effort & model router for Zoe.

Routes tasks across five transparent execution tiers using Operational
Metacognition (`zoe_autonomy.metacognition`):
  - `gear1_eliza`: Deterministic symbolic ELIZA / citation fallback (0 cloud tokens)
  - `local_qwen`: Loopback Qwen2.5-3B on 127.0.0.1:8080 (0 cloud tokens, falls back to gear1_eliza)
  - `flash_lite`: Antigravity `flash_lite` (`ThinkingLevel.LOW`)
  - `flash`: Antigravity `flash` (`ThinkingLevel.MEDIUM`)
  - `pro`: Antigravity `pro` (`ThinkingLevel.HIGH` / `EXTRA_HIGH`, with `/teamwork` escalation)

Pure Python stdlib; preserves all `CONSTITUTION.md` invariants.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, Mapping, Sequence, Tuple
from urllib import error as urlerror, request as urlrequest
from urllib.parse import urlparse

from .metacognition import (
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    directive_violation,
    options_from_scores,
)

STEM_LAYERING_CONTRACT = "zoe-stem-layering/v1"
DEFAULT_TAU = 0.08
DEFAULT_LOCAL_QWEN_URL = "http://127.0.0.1:8080"
DEFAULT_LOCAL_QWEN_MODEL = "qwen2.5-3b-instruct"
ALLOWED_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}

TIER_ORDER: Tuple[str, ...] = (
    "gear1_eliza",
    "local_qwen",
    "flash_lite",
    "flash",
    "pro",
)

TIER_SPECS: Dict[str, Dict[str, Any]] = {
    "gear1_eliza": {
        "antigravity_model": "local-eliza-gear1",
        "thinking_level": None,
        "local_only": True,
        "estimated_cloud_tokens": 0,
        "summary": "Deterministic symbolic ELIZA & citation lookup (<5 ms, 0 cloud tokens).",
    },
    "local_qwen": {
        "antigravity_model": DEFAULT_LOCAL_QWEN_MODEL,
        "thinking_level": None,
        "local_only": True,
        "estimated_cloud_tokens": 0,
        "base_url": f"{DEFAULT_LOCAL_QWEN_URL}/v1",
        "summary": "Loopback Qwen2.5-3B-Instruct on 127.0.0.1:8080 (0 cloud tokens; falls back to gear1_eliza).",
    },
    "flash_lite": {
        "antigravity_model": "flash_lite",
        "thinking_level": "low",
        "local_only": False,
        "estimated_cloud_tokens": None,
        "summary": "Lightweight cloud triage, formatting, and quick read-only checks (ThinkingLevel.LOW).",
    },
    "flash": {
        "antigravity_model": "flash",
        "thinking_level": "medium",
        "local_only": False,
        "estimated_cloud_tokens": None,
        "summary": "Standard single-module implementation, bug fixes, and unit verification (ThinkingLevel.MEDIUM).",
    },
    "pro": {
        "antigravity_model": "pro",
        "thinking_level": "high",
        "local_only": False,
        "estimated_cloud_tokens": None,
        "summary": "Deep reasoning, multi-file debugging, proofs, and optional /teamwork escalation (ThinkingLevel.HIGH/EXTRA_HIGH).",
    },
}

_DEEP_KEYWORDS = (
    "architect",
    "architecture",
    "audit",
    "ast",
    "concurrency",
    "cross-file",
    "debug",
    "distributed",
    "formal",
    "invariant",
    "kernel",
    "migration",
    "multi-file",
    "multifile",
    "orchestrate",
    "parallel",
    "proof",
    "race",
    "refactor",
    "security",
    "swarm",
    "teamwork",
    "theorem",
    "verification",
    "verify",
)

_STANDARD_DEV_KEYWORDS = (
    "add",
    "build",
    "create",
    "edit",
    "feature",
    "fix",
    "function",
    "implement",
    "integrate",
    "module",
    "patch",
    "pytest",
    "script",
    "test",
    "unittest",
    "update",
    "write",
)

_TRIAGE_KEYWORDS = (
    "brief",
    "briefly",
    "classify",
    "format",
    "list",
    "outline",
    "quick",
    "rename",
    "short",
    "summarize",
    "summary",
    "triage",
    "typo",
    "what is",
)

_LOCAL_SYMBOLIC_KEYWORDS = (
    "chladni",
    "cymatics",
    "eliza",
    "gear1",
    "hello",
    "hi",
    "ping",
    "recall",
    "relay",
    "remember",
    "status",
    "voice",
)

_LOCAL_LLM_KEYWORDS = (
    "brainstorm",
    "draft",
    "gear2",
    "llama",
    "local",
    "offline",
    "private",
    "privacy",
    "qwen",
)


def constitutional_flags(*, cloud_tokens_used: int = 0) -> Dict[str, Any]:
    """Return canonical CONSTITUTION.md invariants for stem-layering decisions."""
    return {
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "sentience_claimed": False,
        "pytorch_required": False,
        "external_actions": 0,
        "cloud_tokens_used": int(cloud_tokens_used),
    }


def _assert_loopback_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in ALLOWED_LOOPBACK_HOSTS:
        raise ValueError(f"local Qwen probe restricted to loopback hosts {sorted(ALLOWED_LOOPBACK_HOSTS)}, got {url!r}")
    return url.rstrip("/")


def probe_local_qwen(base_url: str = DEFAULT_LOCAL_QWEN_URL, timeout_sec: float = 0.6) -> Dict[str, Any]:
    """Probe loopback llama-server `/v1/models` cleanly without external network calls."""
    clean_url = _assert_loopback_url(base_url)
    endpoint = f"{clean_url}/v1/models"
    req = urlrequest.Request(endpoint, method="GET", headers={"Accept": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=float(max(0.1, min(timeout_sec, 10.0)))) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        models = [
            str(item.get("id"))
            for item in (payload.get("data") or [])
            if isinstance(item, dict) and item.get("id")
        ]
        return {
            "available": True,
            "endpoint": endpoint,
            "models": models,
            "loopback_only": True,
        }
    except (urlerror.URLError, TimeoutError, ValueError, OSError) as exc:
        return {
            "available": False,
            "endpoint": endpoint,
            "models": [],
            "loopback_only": True,
            "reason": str(exc),
        }


def _tokenize(text: str) -> Tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9_/+.-]+", text.lower()))


def _keyword_hits(normalized: str, tokens: Sequence[str], keywords: Sequence[str]) -> int:
    token_set = set(tokens)
    hits = 0
    for kw in keywords:
        if " " in kw or "-" in kw:
            if kw in normalized:
                hits += 1
        elif kw in token_set:
            hits += 1
    return hits


def build_sdk_descriptor(
    tier: str,
    *,
    thinking_level: str | None = None,
    base_url: str = f"{DEFAULT_LOCAL_QWEN_URL}/v1",
) -> Dict[str, Any]:
    """Build a validated Antigravity SDK configuration descriptor (pure stdlib)."""
    if tier not in TIER_SPECS:
        raise ValueError(f"unknown tier {tier!r}; expected one of {TIER_ORDER}")
    spec = TIER_SPECS[tier]
    resolved_thinking = thinking_level if thinking_level is not None else spec["thinking_level"]
    valid_levels = {None, "minimal", "low", "medium", "high", "xhigh"}
    if resolved_thinking not in valid_levels:
        raise ValueError(f"invalid thinking_level {resolved_thinking!r}; expected one of {sorted(x for x in valid_levels if x)}")

    if tier == "local_qwen":
        clean_base = _assert_loopback_url(base_url).rstrip("/")
        if not clean_base.endswith("/v1"):
            clean_base = f"{clean_base}/v1"
        return {
            "tier": tier,
            "sdk_class": "LocalOpenAIAgentConfig",
            "lightweight": True,
            "model": DEFAULT_LOCAL_QWEN_MODEL,
            "base_url": clean_base,
            "thinking_level": None,
            "cloud_tokens_used": 0,
        }
    if tier == "gear1_eliza":
        return {
            "tier": tier,
            "sdk_class": "ZoeElizaEngine",
            "lightweight": True,
            "model": "local-eliza-gear1",
            "gear": "gear1",
            "thinking_level": None,
            "cloud_tokens_used": 0,
        }
    return {
        "tier": tier,
        "sdk_class": "GeminiModelOptions",
        "antigravity_model": spec["antigravity_model"],
        "thinking_level": resolved_thinking,
        "thinking_enum": f"ThinkingLevel.{ {'minimal': 'MINIMAL', 'low': 'LOW', 'medium': 'MEDIUM', 'high': 'HIGH', 'xhigh': 'EXTRA_HIGH'}[resolved_thinking] }",
    }


@dataclass(frozen=True)
class StemDecision:
    selected_tier: str
    antigravity_model: str
    thinking_level: str | None
    teamwork_recommended: bool
    fallback_tier: str
    fallback_applied: bool
    fallback_reason: str | None
    a_tau: int
    tau: float
    entropy_norm: float
    probabilities: Dict[str, float]
    features: Dict[str, Any]
    provenance: Dict[str, Any]
    constitutional: Dict[str, Any]
    sdk_descriptor: Dict[str, Any]
    local_probe: Dict[str, Any] | None = None
    quorum_arbitration: Dict[str, Any] | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize decision and optional quorum arbitration telemetry to a JSON-safe dict."""
        return {
            "contract": STEM_LAYERING_CONTRACT,
            "selected_tier": self.selected_tier,
            "antigravity_model": self.antigravity_model,
            "thinking_level": self.thinking_level,
            "teamwork_recommended": self.teamwork_recommended,
            "fallback_tier": self.fallback_tier,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": self.fallback_reason,
            "a_tau": self.a_tau,
            "tau": self.tau,
            "entropy_norm": self.entropy_norm,
            "probabilities": dict(self.probabilities),
            "features": dict(self.features),
            "provenance": dict(self.provenance),
            "constitutional": dict(self.constitutional),
            "sdk_descriptor": dict(self.sdk_descriptor),
            "local_probe": dict(self.local_probe) if self.local_probe is not None else None,
            "quorum_arbitration": dict(self.quorum_arbitration) if self.quorum_arbitration is not None else None,
        }


def _sanitize_fallback_inputs(
    dists: Sequence[Sequence[float]],
    weights: Sequence[float] | None,
) -> Tuple[list[list[float]], list[float], list[int]]:
    """Validate and normalize K-agent distributions and convex weights in pure Python."""
    # Convert nested sequences and validate rectangular 2D shape with n_dim >= 1.
    rows = [list(r) for r in dists]
    k_agents = len(rows)
    if k_agents == 0:
        if weights is not None and len(list(weights)) != 0:
            raise ValueError("weights length must match empty dists")
        return [], [], []
    n_dim = len(rows[0])
    if n_dim < 1 or any(len(r) != n_dim for r in rows):
        raise ValueError("dists must be a rectangular 2D sequence with n_dim >= 1")
    normed, zero_indices = [], []
    # Clip negatives and map zero-sum rows onto uniform 1/N so every agent lies on-simplex.
    for idx, row in enumerate(rows):
        vals = [float(x) for x in row]
        if not all(math.isfinite(x) for x in vals):
            raise ValueError("dists must contain only finite numbers")
        clipped = [max(0.0, x) for x in vals]
        max_v = max(clipped)
        if max_v == 0.0:
            zero_indices.append(idx)
            normed.append([1.0 / n_dim] * n_dim)
            continue
        # Scale by row max before fsum so extreme finite inputs like 1e308 never overflow.
        scaled = [x / max_v for x in clipped]
        total = math.fsum(scaled)
        if max_v <= 1e-15 and max_v * total <= 1e-15:
            zero_indices.append(idx)
            normed.append([1.0 / n_dim] * n_dim)
        else:
            normed.append([x / total for x in scaled])
    # Validate convex weights (non-negative, finite, positive total mass).
    if weights is None:
        return normed, [1.0 / k_agents] * k_agents, zero_indices
    w = [float(x) for x in weights]
    if len(w) != k_agents or not all(math.isfinite(x) and x >= 0.0 for x in w):
        raise ValueError("weights must match len(dists) and be finite non-negative")
    max_w = max(w)
    if max_w == 0.0:
        raise ValueError("weights must have a strictly positive sum")
    scaled_w = [x / max_w for x in w]
    w_sum = math.fsum(scaled_w)
    if max_w <= 1e-15 and max_w * w_sum <= 1e-15:
        raise ValueError("weights must have a strictly positive sum")
    return normed, [x / w_sum for x in scaled_w], zero_indices


def _fallback_empty_result(k_agents: int, n_dim: int, zero_indices: list[int], tau: float) -> Dict[str, Any]:
    """Return safe ABSTAIN payload for empty or all-zero ensemble inputs."""
    p_list = [round(1.0 / n_dim, 8)] * n_dim if n_dim > 0 else []
    m2_val = round(1.0 / n_dim, 8) if n_dim > 0 else 0.0
    return {
        "contract": "zoe-kloster-theorem15/v1", "verdict": "ABSTAIN", "reason": "empty_or_zero_vectors",
        "quorum_met": False, "k_agents": k_agents, "effective_agents": 0, "n_dim": n_dim,
        "m2_mean": m2_val, "m2_pool": m2_val, "d_k_disagreement": 0.0, "brier_contraction": 0.0,
        "contraction_ratio": 0.0, "coherence_c_k": 0.0, "jsd_nats": 0.0,
        "echo_chamber_detected": False, "rogue_node_detected": False, "bluff_detected": True,
        "abstained": True, "zero_vector_agents": zero_indices, "rogue_agent_indices": [],
        "agent_l2_sq_to_p_bar": [0.0] * k_agents, "consensus_p_bar": p_list,
        "consensus_argmax": 0 if n_dim > 0 else -1,
        "consensus_confidence": round(1.0 / n_dim, 6) if n_dim > 0 else 0.0,
        "a_tau_pool": sum(1 for x in p_list if x > float(tau)), "tau": float(tau),
    }


def _classify_fallback_verdict(
    n_dim: int,
    effective_k: int,
    min_agents: int,
    excess_pool: float,
    excess_mean: float,
    d_k: float,
    coherence_c_k: float,
    uniform_tol: float,
    echo_dk_tol: float,
    coherence_min: float,
) -> Tuple[str, str, bool, bool, bool, bool]:
    """Apply Theorem 15 priority tree separating uniform collapse, echo-chamber, and rogue nodes."""
    if n_dim == 1:
        return "ABSTAIN", "degenerate_1d_simplex", True, False, False, True
    if excess_pool <= uniform_tol or excess_mean <= uniform_tol:
        return "ABSTAIN", "uniform_uninformative_consensus", True, False, False, True
    if effective_k < min_agents:
        return "ABSTAIN", "insufficient_quorum", True, False, False, False
    if d_k <= echo_dk_tol:
        return "ECHO_CHAMBER_WARNING", "zero_diversity_echo_chamber", False, True, False, False
    if coherence_c_k < coherence_min:
        return "ABSTAIN", "rogue_or_bluff_low_coherence", True, False, True, False
    return "COORDINATE_CONSENSUS", "coherent_diverse_consensus", False, False, False, False


def _fallback_consensus_arbitration(
    dists: Sequence[Sequence[float]],
    weights: Sequence[float] | None = None,
    *,
    coherence_min: float = 0.45,
    echo_dk_tol: float = 1e-9,
    uniform_tol: float = 1e-9,
    min_agents: int = 2,
    tau: float = DEFAULT_TAU,
) -> Dict[str, Any]:
    """Pure-Python Theorem 15 fallback when guiai-lab is absent in standalone deployments."""
    normed, w, zero_indices = _sanitize_fallback_inputs(dists, weights)
    k_agents = len(normed)
    n_dim = len(normed[0]) if k_agents > 0 else 0
    if k_agents == 0 or len(zero_indices) == k_agents:
        return _fallback_empty_result(k_agents, n_dim, zero_indices, tau)

    effective_k = k_agents - len(zero_indices)
    p_bar = [math.fsum(w[i] * normed[i][j] for i in range(k_agents)) for j in range(n_dim)]
    m2_mean = math.fsum(w[i] * math.fsum(x * x for x in normed[i]) for i in range(k_agents))
    m2_pool = math.fsum(x * x for x in p_bar)
    d_k = max(0.0, m2_mean - m2_pool)
    agent_divs = [round(math.fsum((normed[i][j] - p_bar[j]) ** 2 for j in range(n_dim)), 8) for i in range(k_agents)]
    h_each = [-math.fsum(x * math.log(x) for x in r if x > 0.0) for r in normed]
    h_pool = -math.fsum(x * math.log(x) for x in p_bar if x > 0.0)
    jsd = max(0.0, h_pool - math.fsum(w[i] * h_each[i] for i in range(k_agents)))
    denom = m2_mean - (1.0 / n_dim)
    coherence_c_k = 1.0 if denom <= 1e-12 else min(1.0, max(0.0, (m2_pool - 1.0 / n_dim) / denom))
    excess_mean, excess_pool = max(0.0, m2_mean - (1.0 / n_dim)), max(0.0, m2_pool - (1.0 / n_dim))

    verdict, reason, abstained, echo_det, rogue_det, bluff_det = _classify_fallback_verdict(
        n_dim, effective_k, min_agents, excess_pool, excess_mean, d_k, coherence_c_k, uniform_tol, echo_dk_tol, coherence_min
    )
    rogue_indices = [i for i, d in enumerate(agent_divs) if rogue_det and d > max(d_k, 1e-12)]
    if rogue_det and not rogue_indices and agent_divs:
        top_div = max(agent_divs)
        rogue_indices = [i for i, d in enumerate(agent_divs) if d >= top_div - 1e-9]
    top_idx = max(range(n_dim), key=lambda j: p_bar[j])
    return {
        "contract": "zoe-kloster-theorem15/v1", "verdict": verdict, "reason": reason,
        "quorum_met": effective_k >= min_agents, "k_agents": k_agents,
        "effective_agents": effective_k, "n_dim": n_dim,
        "m2_mean": round(m2_mean, 8), "m2_pool": round(m2_pool, 8),
        "d_k_disagreement": round(d_k, 8), "brier_contraction": round(d_k, 8),
        "contraction_ratio": round(d_k / excess_mean, 6) if excess_mean > 1e-12 else 0.0,
        "coherence_c_k": round(coherence_c_k, 6), "jsd_nats": round(jsd, 8),
        "echo_chamber_detected": echo_det, "rogue_node_detected": rogue_det,
        "bluff_detected": bluff_det, "abstained": abstained,
        "zero_vector_agents": zero_indices, "rogue_agent_indices": rogue_indices,
        "agent_l2_sq_to_p_bar": agent_divs, "consensus_p_bar": [round(x, 8) for x in p_bar],
        "consensus_argmax": int(top_idx), "consensus_confidence": round(p_bar[top_idx], 6),
        "a_tau_pool": sum(1 for x in p_bar if x > float(tau)), "tau": float(tau),
    }


def _load_consensus_arbitrator():
    """Lazy-load Theorem 15 arbitrator only when /teamwork or explicit quorum is evaluated."""
    zoe_env = os.environ.get("ZOE_ROOT")
    candidates = [Path(zoe_env).expanduser().resolve() / "guiai-lab"] if zoe_env else []
    candidates.append(Path(__file__).resolve().parents[4] / "guiai-lab")
    for guiai_dir in candidates:
        if guiai_dir.is_dir() and str(guiai_dir) not in sys.path:
            sys.path.insert(0, str(guiai_dir))
            break
    try:
        from guiai.gem.kloster_multi_agent_consensus import evaluate_consensus_arbitration
        return evaluate_consensus_arbitration
    except ImportError:
        return _fallback_consensus_arbitration


def _score_stem_tiers(
    cleaned: str,
    *,
    offline_only: bool,
    privacy_sensitive: bool,
    files_count: int,
    multi_file: bool,
    local_qwen_available: bool | None,
) -> Tuple[Dict[str, float], Dict[str, Any], float, bool, bool, int, str]:
    """Compute prompt features, complexity score, and nonnegative per-tier heuristic scores."""
    normalized = cleaned.lower()
    tokens = _tokenize(cleaned)
    word_count = len(tokens)
    deep_hits = _keyword_hits(normalized, tokens, _DEEP_KEYWORDS)
    dev_hits = _keyword_hits(normalized, tokens, _STANDARD_DEV_KEYWORDS)
    triage_hits = _keyword_hits(normalized, tokens, _TRIAGE_KEYWORDS)
    symbolic_hits = _keyword_hits(normalized, tokens, _LOCAL_SYMBOLIC_KEYWORDS)
    local_llm_hits = _keyword_hits(normalized, tokens, _LOCAL_LLM_KEYWORDS)
    effective_multi_file = bool(multi_file or files_count >= 3)
    local_constraint = bool(offline_only or privacy_sensitive)
    violation = directive_violation(cleaned)

    # Complexity score in [0, 10+] derived transparently from measurable prompt features.
    complexity = (
        min(2.5, word_count / 24.0)
        + 1.35 * deep_hits
        + 0.65 * dev_hits
        + (1.8 if effective_multi_file else (0.55 if files_count == 2 else 0.0))
        - 0.75 * triage_hits
        - 0.60 * symbolic_hits
    )
    complexity = max(0.0, complexity)

    # Nonnegative heuristic scores per tier before normalization via options_from_scores.
    gear1_score = 0.20 + 1.9 * symbolic_hits + (0.85 if word_count <= 3 and dev_hits == 0 and deep_hits == 0 and triage_hits == 0 else 0.0)
    local_qwen_score = 0.30 + 1.6 * local_llm_hits + (1.2 if local_constraint else 0.0) + (0.45 if 6 <= word_count <= 40 else 0.0)
    flash_lite_score = 0.45 + 1.45 * triage_hits + (1.3 if word_count <= 14 and dev_hits == 0 and deep_hits == 0 and not effective_multi_file else 0.0)
    flash_score = 0.35 + 1.25 * dev_hits + (1.1 if 0.8 <= complexity < 3.0 and not effective_multi_file else 0.0)
    pro_score = 0.25 + 1.45 * deep_hits + (2.2 if effective_multi_file else 0.0) + (1.2 if complexity >= 3.0 else 0.0)

    if local_constraint:
        # Cloud tiers strictly excluded under offline_only or privacy_sensitive constraints.
        flash_lite_score = 0.0
        flash_score = 0.0
        pro_score = 0.0
        local_qwen_score += 2.2
        gear1_score += 1.0 if (word_count <= 5 and local_llm_hits == 0) else 0.35
    elif local_qwen_available is False:
        # Down-weight local_qwen when explicitly known offline in online mode.
        local_qwen_score *= 0.2

    scores: Dict[str, float] = {
        "gear1_eliza": round(max(0.0, gear1_score), 6),
        "local_qwen": round(max(0.0, local_qwen_score), 6),
        "flash_lite": round(max(0.0, flash_lite_score), 6),
        "flash": round(max(0.0, flash_score), 6),
        "pro": round(max(0.0, pro_score), 6),
    }
    features = {
        "word_count": word_count,
        "char_count": len(cleaned),
        "files_count": files_count,
        "multi_file": effective_multi_file,
        "offline_only": bool(offline_only),
        "privacy_sensitive": bool(privacy_sensitive),
        "local_qwen_available": local_qwen_available,
        "deep_hits": deep_hits,
        "dev_hits": dev_hits,
        "triage_hits": triage_hits,
        "symbolic_hits": symbolic_hits,
        "local_llm_hits": local_llm_hits,
        "complexity_score": round(complexity, 4),
        "directive_violation": violation,
    }
    return scores, features, complexity, effective_multi_file, local_constraint, deep_hits, normalized


def arbitrate_teamwork_quorum(
    probs: Mapping[str, float],
    *,
    effective_multi_file: bool,
    complexity: float,
    deep_hits: int,
    tau: float = DEFAULT_TAU,
    quorum_distributions: Sequence[Sequence[float]] | None = None,
    quorum_weights: Sequence[float] | None = None,
) -> Dict[str, Any]:
    """Evaluate Theorem 15 quorum arbitration for /teamwork escalation or supplied agents."""
    arbitrate = _load_consensus_arbitrator()
    if quorum_distributions is not None:
        result = arbitrate(quorum_distributions, weights=quorum_weights, tau=float(tau))
        abstention_applied = bool(result["verdict"] in {"ABSTAIN", "ECHO_CHAMBER_WARNING"})
        return {**result, "abstention_applied": abstention_applied, "quorum_supplied": True}

    # Build two independent 5-tier perspectives: A_tau probability vector vs scope prior.
    probs_vec = [float(probs[t]) for t in TIER_ORDER]
    pro_mass = min(0.85, 0.55 + 0.10 * int(effective_multi_file) + 0.05 * min(4, deep_hits) + (0.04 if complexity >= 4.0 else 0.0))
    flash_mass = max(0.08, 0.35 - 0.05 * min(4, deep_hits))
    if abs(probs_vec[4] - pro_mass) < 1e-3:
        pro_mass = min(0.90, pro_mass + 0.05)
        flash_mass = max(0.05, flash_mass - 0.05)
    rem = max(0.0, 1.0 - pro_mass - flash_mass)
    scope_prior = [round(0.15 * rem, 6), round(0.25 * rem, 6), round(0.60 * rem, 6), round(flash_mass, 6), round(pro_mass, 6)]
    result = arbitrate([probs_vec, scope_prior], tau=float(tau))
    return {**result, "abstention_applied": False, "quorum_supplied": False}


def route_stem(
    prompt: str,
    *,
    offline_only: bool = False,
    privacy_sensitive: bool = False,
    files_count: int = 1,
    multi_file: bool = False,
    local_qwen_available: bool | None = None,
    probe_local: bool = False,
    local_qwen_url: str = DEFAULT_LOCAL_QWEN_URL,
    tau: float = DEFAULT_TAU,
    quorum_distributions: Sequence[Sequence[float]] | None = None,
    quorum_weights: Sequence[float] | None = None,
) -> StemDecision:
    """Route a prompt across Cognitive Stem-Layering tiers via Kloster A_tau(p) & Theorem 15 quorum."""
    cleaned = " ".join(str(prompt or "").split()).strip()
    if not cleaned:
        raise ValueError("prompt must not be empty")
    if isinstance(files_count, bool) or not isinstance(files_count, int) or files_count < 0:
        raise ValueError("files_count must be a nonnegative integer")
    if not isinstance(tau, (int, float)) or isinstance(tau, bool) or not (0.0 < float(tau) < 1.0):
        raise ValueError("tau must be in (0, 1)")

    local_probe_doc: Dict[str, Any] | None = None
    if local_qwen_available is None and probe_local:
        local_probe_doc = probe_local_qwen(local_qwen_url)
        local_qwen_available = bool(local_probe_doc["available"])

    scores, features, complexity, effective_multi_file, local_constraint, deep_hits, normalized = _score_stem_tiers(
        cleaned,
        offline_only=offline_only,
        privacy_sensitive=privacy_sensitive,
        files_count=files_count,
        multi_file=multi_file,
        local_qwen_available=local_qwen_available,
    )

    # Evaluate Operational Metacognition A_tau(p) breadth over the 5 stem tiers.
    src = EvidenceSource(kind="document", identifier="zoe-autonomy:stem-layering", trust=0.90, strength=0.85)
    provenance = Provenance((src,), ("Score cognitive stem tiers from prompt complexity, file breadth, and offline/privacy constraints.",))
    options = options_from_scores(scores, provenance)
    meta = OperationalMetacognition()
    threshold = meta.threshold(
        Domain.INTENT,
        float(tau),
        rationale="Declared before stem routing evaluation and fixed for this episode; no post-hoc retuning.",
    )
    breadth = meta.count(options, threshold)
    probs = {opt.identifier: round(float(opt.probability), 6) for opt in breadth.options}
    entropy = -sum(p * math.log2(p) for p in probs.values() if p > 1e-12)
    entropy_norm = round(entropy / math.log2(max(2, sum(1 for p in probs.values() if p > 0.0))), 6)
    ranked = sorted(breadth.options, key=lambda opt: (-opt.probability, TIER_ORDER.index(opt.identifier)))
    selected_tier = ranked[0].identifier

    # Enforce deterministic offline/privacy and local-Qwen availability fallbacks.
    fallback_applied = False
    fallback_reason: str | None = None
    if selected_tier == "local_qwen" and local_qwen_available is False:
        selected_tier = "gear1_eliza"
        fallback_applied = True
        fallback_reason = "local Qwen2.5-3B (127.0.0.1:8080) unavailable; fell back cleanly to Gear 1 ELIZA."
    elif local_constraint and selected_tier not in {"gear1_eliza", "local_qwen"}:
        selected_tier = "local_qwen" if local_qwen_available is not False else "gear1_eliza"
        fallback_applied = True
        fallback_reason = "Cloud tiers disabled by offline/privacy constraint."

    spec = TIER_SPECS[selected_tier]
    teamwork_recommended = bool(
        (not local_constraint)
        and selected_tier == "pro"
        and (
            effective_multi_file
            or deep_hits >= 2
            or "teamwork" in normalized
            or "swarm" in normalized
            or (breadth.accessible_count >= 3 and complexity >= 3.2)
        )
    )

    # Gate /teamwork escalation with Theorem 15 quorum arbitration when active or supplied.
    quorum_arbitration: Dict[str, Any] | None = None
    if quorum_distributions is not None or teamwork_recommended:
        quorum_arbitration = arbitrate_teamwork_quorum(
            probs,
            effective_multi_file=effective_multi_file,
            complexity=complexity,
            deep_hits=deep_hits,
            tau=float(tau),
            quorum_distributions=quorum_distributions,
            quorum_weights=quorum_weights,
        )
        if quorum_arbitration["abstention_applied"]:
            teamwork_recommended = False

    thinking_level = spec["thinking_level"]
    if selected_tier == "pro" and (teamwork_recommended or deep_hits >= 2 or complexity >= 4.2):
        thinking_level = "xhigh"

    sdk_descriptor = build_sdk_descriptor(
        selected_tier,
        thinking_level=thinking_level,
        base_url=f"{local_qwen_url.rstrip('/')}/v1",
    )
    return StemDecision(
        selected_tier=selected_tier,
        antigravity_model=str(spec["antigravity_model"]),
        thinking_level=thinking_level,
        teamwork_recommended=teamwork_recommended,
        fallback_tier="gear1_eliza",
        fallback_applied=fallback_applied,
        fallback_reason=fallback_reason,
        a_tau=int(breadth.accessible_count),
        tau=float(breadth.tau),
        entropy_norm=entropy_norm,
        probabilities=probs,
        features=features,
        provenance=provenance.document(),
        constitutional=constitutional_flags(cloud_tokens_used=0),
        sdk_descriptor=sdk_descriptor,
        local_probe=local_probe_doc,
        quorum_arbitration=quorum_arbitration,
    )
