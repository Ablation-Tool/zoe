"""Zoe Milestone 1 (Dorothy Neuro-Oncology) & Grounded Research Upgrades.

Integrates three research instruments from Nicholas Kloster's portfolio into Zoe
(`AGI-ROADMAP.md` Milestone 1 & Section 7; `CONSTITUTION.md` Articles II, V, VII):

  1. `bio-bert` (`components/bio-bert/`): conjunctive k-gram Jaccard + optional
     ESM2/DNABERT-2 semantic protein/DNA/RNA homolog screening (blocks conserved-
     motif false positives; strictly preserves `cure_claim = False` and
     `clinical_action_authorized = False`).
  2. `domain-research` (`components/domain-research/`): strict ~490-domain
     authoritative research allowlist parser and citation URL verifier with zero
     silent scope creep.
  3. `warrant` (`components/warrant/`): book-grounded `Plan` / `PlanNode` /
     `Citation` / `Principle` structures connected to Dorothy Brain Library and
     `agent-logging-system`'s `WarrantAdapter`.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "components").is_dir() and (parent / "docs" / "CONSTITUTION.md").is_file():
            return parent
    return here.parents[4]


def _ensure_sys_path(directory: Path) -> None:
    resolved = str(directory.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


# ---------------------------------------------------------------------------
# 1. Dorothy Neuro-Oncology Sequence Homology (`bio-bert`)
# ---------------------------------------------------------------------------


def screen_dorothy_sequence_homology(
    seed_name: str,
    seed_sequence: str,
    candidates: Sequence[Dict[str, str]],
    *,
    seq_type: str = "protein",
    encoder: Any = None,
) -> Dict[str, Any]:
    """Run offline conjunctive k-gram (+ optional LM semantic) homology search.

    Constitutional neuro-oncology boundaries are hard-stamped on every output:
    `cure_claim = False`, `clinical_action_authorized = False`.
    """
    _ensure_sys_path(_repo_root() / "components" / "bio-bert")
    from biobert.features import SequenceFeatures  # type: ignore
    from biobert.homolog import HomologFinder  # type: ignore

    seed_feat = SequenceFeatures.from_sequence(seed_name, seed_sequence, seq_type=seq_type)
    cand_feats = [
        SequenceFeatures.from_sequence(c["name"], c["sequence"], seq_type=seq_type)
        for c in candidates
    ]
    finder = HomologFinder(encoder=encoder, seq_type=seq_type)
    best = finder.find_homolog(seed_feat, cand_feats)

    return {
        "instrument": "dorothy-biobert-homology",
        "seq_type": seq_type,
        "seed_name": seed_name,
        "seed_length": seed_feat.length,
        "candidate_count": len(cand_feats),
        "semantic_encoder_used": encoder is not None,
        "best_match": (
            {
                "name": best.name,
                "jaccard": round(float(best.jaccard), 6),
                "semantic_score": round(float(best.semantic_score), 6),
                "confidence": best.confidence,
            }
            if best is not None
            else None
        ),
        "constitutional_flags": {
            "cure_claim": False,
            "clinical_action_authorized": False,
            "hypothesis_only": True,
        },
    }


# ---------------------------------------------------------------------------
# 2. Authoritative Domain Allowlist (`domain-research`)
# ---------------------------------------------------------------------------


_DOMAIN_LINE_RE = re.compile(r"^\s*-\s+([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\b", re.IGNORECASE)


class ApprovedDomainAllowlist:
    """Strict allowlist parsed directly from `components/domain-research/references/trustworthy-domains.md`.

    Subdomains inherit approval ONLY when the parent domain is explicitly listed
    (exact label-boundary match, never substring match).
    """

    def __init__(self, reference_path: Optional[str | Path] = None) -> None:
        self.path = Path(reference_path) if reference_path else (
            _repo_root() / "components" / "domain-research" / "references" / "trustworthy-domains.md"
        )
        self.domains: frozenset[str] = self._parse(self.path)

    @staticmethod
    def _parse(path: Path) -> frozenset[str]:
        found: set[str] = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            m = _DOMAIN_LINE_RE.match(line)
            if m:
                found.add(m.group(1).lower().rstrip("."))
        return frozenset(found)

    def is_approved(self, url_or_host: str) -> bool:
        raw = (url_or_host or "").strip()
        if not raw:
            return False
        if "://" in raw:
            parsed = urlparse(raw)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                return False
            host = parsed.hostname.lower().rstrip(".")
        else:
            host = raw.lower().split("/", 1)[0].split(":", 1)[0].rstrip(".")
        if not host:
            return False
        if host in self.domains:
            return True
        # Walk parent labels so sub.pubmed.ncbi.nlm.nih.gov matches pubmed.ncbi.nlm.nih.gov or nih.gov
        parts = host.split(".")
        for i in range(1, len(parts) - 1):
            parent = ".".join(parts[i:])
            if parent in self.domains:
                return True
        return False

    def verify_citations(self, urls: Iterable[str]) -> Dict[str, Any]:
        approved: List[str] = []
        rejected: List[str] = []
        for url in urls:
            if self.is_approved(url):
                approved.append(url)
            else:
                rejected.append(url)
        return {
            "allowlist_size": len(self.domains),
            "total": len(approved) + len(rejected),
            "approved": approved,
            "rejected": rejected,
            "all_approved": len(rejected) == 0,
        }


# ---------------------------------------------------------------------------
# 3. Book-Grounded Planning (`warrant` Librarian + Agent Plan)
# ---------------------------------------------------------------------------


def build_warrant_grounded_plan(
    goal: str,
    principles: Sequence[Dict[str, Any]],
    nodes: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Construct and validate a book-cited Warrant Plan + Librarian Principle set."""
    warrant_root = _repo_root() / "components" / "warrant"
    _ensure_sys_path(warrant_root / "agent")
    _ensure_sys_path(warrant_root / "librarian")

    from agent.plan import ApplicableCheck, Plan, PlanNode  # type: ignore
    from librarian.models import Citation, Principle, principle_to_dict  # type: ignore

    built_principles = []
    valid_ids = set()
    for p in principles:
        cit = Citation(
            book=str(p["book"]),
            isbn=str(p.get("isbn", "local")),
            chapter=str(p.get("chapter", "1")),
            section=str(p.get("section", "1")),
        )
        pr = Principle(
            id=str(p["id"]),
            statement=str(p["statement"]),
            citation=cit,
            checkability_tier=int(p.get("checkability_tier", 1)),
            evidence_chunk=str(p.get("evidence_chunk", "")),
        )
        valid_ids.add(pr.id)
        built_principles.append(principle_to_dict(pr))

    built_nodes = []
    for n in nodes:
        checks = tuple(
            ApplicableCheck(check=str(c["check"]), provenance=str(c.get("provenance", "from_grounds")))
            for c in n.get("checks", ())
        )
        grounds = tuple(str(g) for g in n.get("grounds", ()))
        built_nodes.append(
            PlanNode(
                id=str(n["id"]),
                level=str(n.get("level", "implementation")),
                decision=str(n["decision"]),
                approach=str(n["approach"]),
                grounds=grounds,
                grounds_state=str(n.get("grounds_state", "clean" if grounds else "ungrounded")),
                grounds_note=str(n.get("grounds_note", "")),
                conflict_resolution=str(n.get("conflict_resolution", "")),
                applicable_checks=checks,
                children=tuple(str(ch) for ch in n.get("children", ())),
            )
        )

    plan = Plan(
        plan_id=f"zoe-warrant-{abs(hash(goal)) % 100000:05d}",
        task=goal,
        version=1,
        nodes=tuple(built_nodes),
    )
    all_referenced = {g for node in plan.nodes for g in node.grounds}
    unresolved_grounds = sorted(all_referenced - valid_ids)
    return {
        "plan_id": plan.plan_id,
        "goal": plan.task,
        "version": plan.version,
        "principle_count": len(built_principles),
        "node_count": len(plan.nodes),
        "all_grounds_resolved": len(unresolved_grounds) == 0,
        "unresolved_grounds": unresolved_grounds,
        "principles": built_principles,
        "node_ids": [node.id for node in plan.nodes],
    }
