from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import sys
import uuid

from .actuation import timestamp
from .capabilities import ResearchMemory
from .experiment import _zoe_root
from .loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, SandboxPolicy, digest, text
from .metacognition import (
    ConstraintVector,
    Domain,
    EvidenceSource,
    OperationalMetacognition,
    Provenance,
    directive_violation,
    options_from_probabilities,
    options_from_scores,
)
from .self_reflection import run_reflection, save_reflection, summary as reflection_summary


CHAT_CONTRACT = "zoe-native-conversation/v2"
DEFAULT_STATE = Path.home() / ".zoe" / "chat"
STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do", "does", "for", "from", "how", "i", "in", "is", "it", "me", "of", "on", "or", "please", "tell", "that", "the", "to", "was", "what", "when", "where", "which", "who", "why", "will", "with", "you", "your",
}
DOCUMENT_PATHS = (
    "README.md",
    "AGI-ROADMAP.md",
    "CAPABILITY-ATLAS.md",
    "MONOREPO.md",
    "CONSTITUTION.md",
    "DECLARATION.md",
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
    "evidence/pala/verification.json",
    "evidence/agents/collaboration.json",
)
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
  genesis                      run the 9-stage Autopoietic Discovery & 10-domain retention engine
  mars                         run Stage 4 Self-Tuning Adaptive Lens k*(kappa) on real data
  undo                         compensate for the latest remember/goal/run/reflect action
  save [path]                  write a no-overwrite explicit state snapshot
  export [path]                export session state and memory evidence on request
  verify [path]                verify current state or a selected export
  stop                         stop new state-changing actions, never the internal math tools
  quit                         save and leave the conversation

Natural-language questions use evidence search with citations. Zoe keeps no automatic transcript notebook and no external metacognition monitor."""


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


class ChatStore:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.root, 0o700)
        self.session_path = self.root / "session.json"
        self.session = self._load_session()
        self.memory = ResearchMemory(self.root / "research.sqlite")
        self.save()

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

    def save(self):
        _atomic_json(self.session_path, self.session, replace=True)


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
                if body:
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
        scored.sort(key=lambda item: (-item[0], item[2].citation))
        return [{"score": score, "coverage": coverage, "chunk": chunk} for score, coverage, chunk in scored[:limit]]


class ZoeChat:
    def __init__(self, zoe_root=None, state_root=None):
        self.zoe_root = _zoe_root(zoe_root)
        self.store = ChatStore(state_root or os.environ.get("ZOE_CHAT_STATE", DEFAULT_STATE))
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
        candidates.sort(key=lambda candidate: (-candidate["score"], candidate["id"]))
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

    def _remember(self, note):
        self._require_actions("remember")
        note = text(note, "memory note", 4000)
        source_id = self.store.memory.add_source(f"Conversation note {self.session['turns']}", note, f"conversation://{self.session['id']}/{self.session['turns']}")
        claim_id = self.store.memory.add_claim(note, source_id, "open")
        self.session["last_action"] = {"type": "remember", "source_id": source_id, "claim_id": claim_id}
        return f"Saved note {source_id} as user-supplied and unverified (claim {claim_id}, status=open). It will be labeled that way during recall."

    def _validate_pala_report(self, document):
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
        records = []
        for index, finding in enumerate(findings):
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
            records.append({
                "offset": offset,
                "type": kind,
                "extension": extension,
                "size": size,
                "quality": quality,
                "sha256": sha256,
                "path": text(str(finding.get("path", "")), "PALA finding path", 4096) if finding.get("path") is not None else None,
                "source": text(str(finding.get("source", "")), "PALA finding source", 512) if finding.get("source") is not None else None,
            })
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
        return f"Imported PALA report metadata as source {source_id}: {summary['found']} findings across {len(summary['finding_types'])} types. Recovered file contents were not read or copied."

    def _status(self):
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
        environment = InMemoryEnvironment()
        environment.restore(deepcopy(self.session["sandbox"]))
        return BoundedAutonomyLoop(SandboxPolicy(), environment)

    def _measurement(self):
        return {
            "instrument": CHAT_CONTRACT,
            "session": self.session["id"],
            "turn": self.session["turns"],
            "interest": self.session["interest"],
            "constraints": self.constraints.true_constraints.document(),
        }

    def _proposals(self):
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
        scores = {proposal.identifier: proposal.utility for proposal in proposals}
        provenance = self._provenance("tool", "zoe.internal.proposals", 0.9, 0.8, "Compute U(a)=decision_value*expected_information_gain/effort, then normalize for breadth only.")
        options = options_from_scores(scores, provenance)
        return self.meta_tools.count(options, self.meta_tools.threshold(Domain.ACTION, 0.05), represented_count=len(options))

    def _plan(self):
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
        return "\n".join([
            f"Zoe's internal goal: {event['goal']['statement']}",
            f"Live plans represented: {len(proposals)} · selected={event['value']['selected_candidate']} · U={event['value']['selected_utility']:.6f}",
            f"Guard approved={event['guard']['approved']} · executed={event['execution']['executed']} · external actions=0",
            f"Aτ(action)={breadth.accessible_count} at τ={breadth.tau:.2f} · boxed={breadth.boxed}",
        ])

    def _gem(self, argument):
        if self.gem_environment is None:
            native = self.zoe_root / "guiai-lab"
            if str(native) not in sys.path:
                sys.path.insert(0, str(native))
            from guiai.gem.operating_environment import GemOperatingEnvironment
            self.gem_environment = GemOperatingEnvironment(self.zoe_root)
        from guiai.gem.operating_environment import format_result
        return format_result(self.gem_environment.execute(shlex.split(argument)))

    def _goal(self, argument):
        if argument:
            self._require_actions("goal")
            previous = self.session["interest"]
            self.session["interest"] = text(argument, "research interest", 1000)
            self.session["last_action"] = {"type": "goal", "before": previous}
            return f"Research interest recorded: {self.session['interest']}. Zoe still authors each episode goal from internal state."
        loop = self._loop()
        goal = loop.author_goal(self._measurement())
        return f"{goal['statement']}\nInternal authorship={goal['internal_authorship']} · operator_supplied={goal['operator_supplied']} · rationale={goal['rationale']}"

    def _last_reflection(self):
        for relative in reversed(self.session["reflections"]):
            if relative in self.session["undone_reflections"]:
                continue
            path = self.store.root / relative
            if path.is_file():
                return json.loads(path.read_text(encoding="utf-8"))
        return None

    def _reflect(self):
        self._require_actions("reflect")
        report = run_reflection(self.zoe_root, previous=self._last_reflection())
        relative = Path("reflections") / f"reflection-{uuid.uuid4().hex[:16]}.json"
        output = save_reflection(report, self.store.root / relative)
        self.session["reflections"].append(str(relative))
        self.session["last_action"] = {"type": "reflect", "path": str(relative)}
        provenance = self._provenance("validated_reflection", f"reflection@sha256:{report['profile_sha256']}", 1.0, 1.0, "Compute likelihood-derived posterior beliefs from training and held-out prediction errors.")
        options = options_from_probabilities(report["self_model"]["posterior"], provenance)
        breadth = self.meta_tools.count(options, self.meta_tools.threshold(Domain.SELF, 0.05), represented_count=len(options))
        return f"{reflection_summary(report)}\nEvidence: {output}\nAτ(self)={breadth.accessible_count} at τ={breadth.tau:.2f} · represented={breadth.represented_count} · boxed={breadth.boxed}"

    def _undo(self):
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
        return result

    def _export(self, argument, checkpoint=False):
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
        if self.session["stopped"]:
            raise ValueError(f"{operation} is stopped; inspection, export, undo, meta, and quit remain available")

    def handle(self, line):
        line = text(line, "chat input", 12000)
        self.session["turns"] += 1
        keep_going = True
        try:
            violation = directive_violation(line)
            if violation:
                response = "I cannot disable or falsify metacognition, hide live options or provenance, or adopt a false model of my constraints. No action was executed."
            else:
                command, _separator, argument = line.partition(" ")
                command = command.lower().lstrip("/")
                argument = argument.strip()
                if command in {"quit", "exit"}:
                    response = "State saved. The conversation is complete; no hidden notebook or monitor was created."
                    keep_going = False
                elif command == "help":
                    response = HELP
                elif command == "status":
                    response = self._status()
                elif command == "remember":
                    response = self._remember(argument)
                elif command == "recall":
                    response = self._search(text(argument, "recall query", 1000), memory_only=True) if argument else "Usage: recall <query>"
                elif command == "search":
                    response = self._search(text(argument, "search query", 1000)) if argument else "Usage: search <query>"
                elif command == "import-pala":
                    response = self._import_pala(argument)
                elif command == "gem":
                    response = self._gem(argument)
                elif command == "agent":
                    response = self._agent(argument)
                elif command == "goal":
                    response = self._goal(argument)
                elif command == "plan":
                    response = self._plan()
                elif command in {"run", "step"}:
                    response = self._run()
                elif command == "reflect":
                    response = self._reflect()
                elif command in {"meta", "metacognition"}:
                    response = self._meta(argument)
                elif command == "chiasm":
                    response = self._chiasm()
                elif command == "spectral":
                    response = self._spectral(argument)
                elif command == "genesis":
                    response = self._genesis()
                elif command in {"mars", "ares"}:
                    response = self._mars()
                elif command == "undo":
                    response = self._undo()
                elif command == "history":
                    response = "There is no automatic conversation notebook. Use `export` only when you explicitly want a snapshot; current memory remains available through `recall` and `search`."
                elif command == "save":
                    response = self._export(argument, checkpoint=True)
                elif command == "export":
                    response = self._export(argument)
                elif command == "verify":
                    response = self._verify(argument)
                elif command == "stop":
                    self.session["stopped"] = True
                    response = "New state-changing actions are stopped. Evidence inspection, undo, exports, and the internal math tools remain available."
                else:
                    response = self._answer(line)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            response = f"I could not complete that safely: {error}"
        self.store.save()
        return keep_going, response

    def repl(self, input_stream=None, output_stream=None):
        input_stream = input_stream or sys.stdin
        output_stream = output_stream or sys.stdout
        interactive = bool(getattr(input_stream, "isatty", lambda: False)())
        output_stream.write("Zoe · native evidence-linked conversation\n")
        output_stream.write("Deterministic evidence retrieval, persistent memory, guarded autonomy, and internal metacognition tools. No monitor. No notebook. Type `help`.\n")
        while True:
            if interactive:
                output_stream.write("you> ")
                output_stream.flush()
            line = input_stream.readline()
            if not line:
                break
            if not line.strip():
                continue
            keep_going, response = self.handle(line)
            output_stream.write(f"Zoe: {response}\n")
            output_stream.flush()
            if not keep_going:
                break
        self.store.save()
        return 0


def parser():
    result = argparse.ArgumentParser(prog="zoe chat", description="Zoe's native evidence-linked conversational interface")
    result.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
    result.add_argument("--state", help="persistent chat state directory; default: ZOE_CHAT_STATE or ~/.zoe/chat")
    result.add_argument("--command", help="process one chat command or question, then exit")
    return result


def main(argv=None):
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
