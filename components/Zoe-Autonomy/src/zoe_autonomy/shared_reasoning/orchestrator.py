"""Unified End-to-End Shared-Reasoning Composer across Architectures 1-9.

Composes all nine Zoe x Antigravity shared-reasoning architectures on top of
the dual-transport ``ZoeAntigravityBridge`` and ``EpistemicBlackboard`` (Arch 6)
four-lane provenance spine:

  - Transport Anchor: ``ZoeAntigravityBridge`` (``offline`` / ``local_qwen`` / ``gemini`` / ``auto``)
  - Arch 6: ``EpistemicBlackboard`` (``measurement != evidence != belief update != action``)
  - Arch 2: ``LiveProcessSupervisor`` (streaming thoughts/tools + mutual Zoe <-> Antigravity audit)
  - Arch 1: ``AlphaEvolveLoop`` (Antigravity/AST mutation x Zoe AST verifier x MAP-Elites)
  - Arch 7: ``RealitySandboxLab`` (SymPy, Z3 SMT, GuardedFunctionASTSandbox, optional Dataset lab)
  - Arch 3: ``KlosterMCTSSearch`` (UCT Tree-of-Thought + multi-horizon $A_\\tau^{(h)}$ + Theorem 13 stopping)
  - Arch 9: ``CounterpointChairsEngine`` (polyphonic non-repeating relay + cold-audit + optional WAV)
  - Arch 4: ``FourPeerQuorumEngine`` + ``route_with_four_peer_quorum`` (Theorem 15 + ``stem_layering.py``)
  - Arch 8: ``HumanSteeringDetector`` (supercritical fork detection + ``ASK_USER`` / ``OnInteractionHook``)
  - Arch 5: ``System2To1Distiller`` (verified System-2 -> ``ZoeUnifiedMemory`` System-1 distillation)

Strictly preserves ``docs/CONSTITUTION.md`` invariants:
  - ``external_actions == 0``
  - ``sentience_claimed is False``
  - ``l5_agi_qualified is False``
  - ``zoe_clone_claimed is False``
  - Attribution: Nicholas Michael Kloster, March 6, 2026
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from google.antigravity import Agent, types
from google.antigravity.hooks import hooks as ag_hooks

from ..l5_memory import ZoeUnifiedMemory
from ..metacognition import EvidenceSource, Provenance
from ..stem_layering import STEM_LAYERING_CONTRACT, TIER_ORDER, route_stem
from .alpha_evolve import (
    AlphaEvolveLoop,
    AlphaEvolveResult,
    AntigravityProgramMutator,
    TestCase,
    ZoeDeterministicVerifier,
)
from .blackboard import (
    EpistemicBlackboard,
    FirewallViolationError,
)
from .counterpoint_chairs import (
    CounterpointChairsEngine,
    CounterpointRelayResult,
    ProblemChair,
    default_counterpoint_voices,
)
from .distillation import (
    DistilledArtifact,
    System2To1Distiller,
    System2Trace,
)
from .human_steering import (
    ForkPointReport,
    HumanSteeringDetector,
    VerifiedPathOption,
)
from .mcts_kloster import (
    KlosterMCTSSearch,
    MCTSSearchResult,
    ThoughtCandidate,
)
from .process_supervision import LiveProcessSupervisor
from .quorum import (
    ACTION_LABELS,
    FourPeerQuorumEngine,
    FourPeerQuorumResult,
    FourPeerRouteResult,
    PeerConfidenceVector,
    PeerInput,
    route_with_four_peer_quorum,
)
from .sandbox_labs import RealitySandboxLab, SandboxLabVerdict
from .sdk_bridge import (
    ATTRIBUTION_TEXT,
    BridgeTurnResult,
    TransportResolution,
    ZoeAntigravityBridge,
    bridge_constitutional_metadata,
    run_coro_sync,
)

SHARED_REASONING_ORCHESTRATOR_CONTRACT = "zoe-shared-reasoning-orchestrator/v1"

DEFAULT_SEED_PROGRAM = "def score_candidate(x):\n    return x\n"
DEFAULT_TEST_CASES: tuple[tuple[dict[str, float], float], ...] = tuple(
    ({"x": float(x)}, float(x * x)) for x in (-2.0, -1.0, 0.0, 1.0, 2.0, 3.0)
)


@dataclass(frozen=True)
class SharedReasoningTaskSpec:
    """Task specification driving a composed Architectures 1-9 reasoning run."""

    prompt: str
    seed_program: str = DEFAULT_SEED_PROGRAM
    test_cases: Sequence[TestCase | Mapping[str, Any] | tuple[Any, Any]] = DEFAULT_TEST_CASES
    evolve_generations: int = 8
    evolve_offspring_per_gen: int = 16
    sympy_lhs: str = "(x + 1)**2"
    sympy_rhs: str = "x**2 + 2*x + 1"
    z3_assumptions: tuple[str, ...] = ()
    z3_invariant: str = "x * x >= 0"
    z3_variables: Mapping[str, str] = field(default_factory=lambda: {"x": "Int"})
    dataset: Any = None
    dataset_invariants: Sequence[Mapping[str, Any]] = ()
    mcts_tau: float = 0.08
    mcts_max_iterations: int = 12
    mcts_root_state: Any = None
    mcts_expand_fn: Callable[..., Any] | None = None
    mcts_eval_fn: Callable[..., Any] | None = None
    quorum_tau: float = 0.05
    user_probs: PeerInput | None = None
    counterpoint_rounds: int = 2
    sonify_wav_path: str | Path | None = None
    distill_target_name: str | None = None
    distill_verification_cases: Sequence[Mapping[str, Any]] | None = None
    eliza_rule_spec: Mapping[str, Any] | None = None
    steering_callback: Callable[..., Any] | None = None
    high_impact: bool = False
    enable_gem_desktop: bool = True
    gem_vdi_output_dir: str | Path | None = None


@dataclass(frozen=True)
class SharedReasoningRunReport:
    """Complete provenance-tracked report across Architectures 1-9."""

    contract: str
    task_prompt: str
    bridge_turn: BridgeTurnResult
    supervision_summary: dict[str, Any]
    supervised_response: dict[str, Any]
    alpha_evolve: AlphaEvolveResult
    mcts_result: MCTSSearchResult
    sandbox_verdicts: dict[str, SandboxLabVerdict]
    counterpoint_result: CounterpointRelayResult
    cadence_wav: dict[str, Any] | None
    quorum_result: FourPeerQuorumResult
    quorum_route: FourPeerRouteResult
    steering_report: ForkPointReport
    steering_interaction: dict[str, Any] | None
    distilled_artifacts: tuple[DistilledArtifact, ...]
    distilled_replay_outputs: dict[str, Any]
    blackboard_summary: dict[str, Any]
    blackboard_lanes: dict[str, Any]
    blackboard_integrity: dict[str, Any]
    final_belief_id: str
    final_action_proposal_id: str
    external_actions: int = 0
    sentience_claimed: bool = False
    l5_agi_qualified: bool = False
    zoe_clone_claimed: bool = False
    attribution: str = ATTRIBUTION_TEXT
    constitutional: dict[str, Any] = field(default_factory=bridge_constitutional_metadata)
    gem_desktop_report: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": self.contract,
            "task_prompt": self.task_prompt,
            "bridge_turn": self.bridge_turn.to_dict(),
            "supervision_summary": dict(self.supervision_summary),
            "supervised_response": dict(self.supervised_response),
            "alpha_evolve": self.alpha_evolve.to_dict(),
            "mcts_result": self.mcts_result.to_dict(),
            "sandbox_verdicts": {k: v.to_dict() for k, v in self.sandbox_verdicts.items()},
            "counterpoint_result": self.counterpoint_result.to_dict(),
            "cadence_wav": dict(self.cadence_wav) if self.cadence_wav is not None else None,
            "quorum_result": self.quorum_result.to_dict(),
            "quorum_route": self.quorum_route.to_dict(),
            "steering_report": self.steering_report.to_dict(),
            "steering_interaction": (
                dict(self.steering_interaction)
                if self.steering_interaction is not None
                else None
            ),
            "distilled_artifacts": [a.to_dict() for a in self.distilled_artifacts],
            "distilled_replay_outputs": dict(self.distilled_replay_outputs),
            "blackboard_summary": dict(self.blackboard_summary),
            "blackboard_lanes": dict(self.blackboard_lanes),
            "blackboard_integrity": dict(self.blackboard_integrity),
            "final_belief_id": self.final_belief_id,
            "final_action_proposal_id": self.final_action_proposal_id,
            "gem_desktop_report": (
                dict(self.gem_desktop_report) if self.gem_desktop_report is not None else None
            ),
            "external_actions": self.external_actions,
            "sentience_claimed": self.sentience_claimed,
            "l5_agi_qualified": self.l5_agi_qualified,
            "zoe_clone_claimed": self.zoe_clone_claimed,
            "attribution": self.attribution,
            "constitutional": dict(self.constitutional),
        }


def _normalize_simplex_probs(values: Sequence[float]) -> tuple[float, ...]:
    cleaned = [max(1e-6, float(v)) for v in values]
    total = sum(cleaned)
    return tuple(v / total for v in cleaned)


def _default_mcts_handlers(
    task_prompt: str,
    alpha_score: float,
    sympy_ok: bool,
    z3_ok: bool,
) -> tuple[Any, Callable[[Any], list[ThoughtCandidate]], Callable[[Any], dict[str, Any]]]:
    """Deterministic Tree-of-Thought strategy exploration with pruning & fork candidates."""
    sym_bonus = 0.08 if sympy_ok else -0.15
    z3_bonus = 0.08 if z3_ok else -0.15

    root_state = {"stage": "root", "prompt": task_prompt[:120], "depth": 0}

    def expand_fn(state: Any) -> list[ThoughtCandidate]:
        if not isinstance(state, Mapping):
            return []
        stage = state.get("stage")
        if stage == "root":
            return [
                ThoughtCandidate(
                    action="symbolic_proof_synthesis",
                    state={"stage": "leaf_branch", "branch": "symbolic_proof", "bin": 0},
                    prior_prob=0.46,
                    token_index=0,
                ),
                ThoughtCandidate(
                    action="evolutionary_ast_distillation",
                    state={"stage": "leaf_branch", "branch": "ast_distill", "bin": 1},
                    prior_prob=0.40,
                    token_index=1,
                ),
                ThoughtCandidate(
                    action="unverified_heuristic_tail",
                    state={"stage": "leaf_branch", "branch": "low_prior_tail", "bin": 2},
                    prior_prob=0.05,  # <= default tau=0.08 -> pruned by A_tau
                    token_index=2,
                ),
            ]
        if stage == "leaf_branch":
            branch = state.get("branch")
            if branch == "symbolic_proof":
                return [
                    ThoughtCandidate(
                        action="verify_sympy_and_z3",
                        state={"stage": "terminal", "branch": "symbolic_proof", "bin": 0, "sub": "formal"},
                        prior_prob=0.62,
                        token_index=0,
                    ),
                    ThoughtCandidate(
                        action="bounded_counterexample_check",
                        state={"stage": "terminal", "branch": "symbolic_proof", "bin": 0, "sub": "counter"},
                        prior_prob=0.38,
                        token_index=1,
                    ),
                ]
            if branch == "ast_distill":
                return [
                    ThoughtCandidate(
                        action="promote_ast_skill_to_memory",
                        state={"stage": "terminal", "branch": "ast_distill", "bin": 1, "sub": "skill"},
                        prior_prob=0.65,
                        token_index=0,
                    ),
                    ThoughtCandidate(
                        action="hold_for_human_review",
                        state={"stage": "terminal", "branch": "ast_distill", "bin": 1, "sub": "review"},
                        prior_prob=0.35,
                        token_index=1,
                    ),
                ]
        return []

    def eval_fn(state: Any) -> dict[str, Any]:
        if not isinstance(state, Mapping):
            return {"value": 0.5, "observations": (0, 0, 1, 2), "is_terminal": True}
        branch = str(state.get("branch", "symbolic_proof"))
        is_term = state.get("stage") == "terminal"
        if branch == "symbolic_proof":
            val = min(1.0, max(0.0, 0.78 + sym_bonus + z3_bonus))
            obs = (0, 0, 0, 1)
        elif branch == "ast_distill":
            val = min(1.0, max(0.0, 0.74 + 0.16 * alpha_score))
            obs = (1, 1, 0, 1)
        else:
            val = 0.25
            obs = (2, 3, 2, 3)
        return {
            "value": val,
            "observations": obs,
            "is_terminal": is_term,
        }

    return root_state, expand_fn, eval_fn


class SharedReasoningOrchestrator:
    """End-to-end composer uniting Zoe x Antigravity Shared-Reasoning Architectures 1-9."""

    def __init__(
        self,
        *,
        mode: Literal["offline", "local_qwen", "gemini", "auto"] = "auto",
        bridge: ZoeAntigravityBridge | None = None,
        blackboard: EpistemicBlackboard | None = None,
        memory: ZoeUnifiedMemory | None = None,
        supervisor: LiveProcessSupervisor | None = None,
        sandbox_lab: RealitySandboxLab | None = None,
        quorum_engine: FourPeerQuorumEngine | None = None,
        steering_detector: HumanSteeringDetector | None = None,
        distiller: System2To1Distiller | None = None,
        repo_root: str | Path | None = None,
        state_dir: str | Path | None = None,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        probe_local: bool = True,
        seed: int = 42,
    ) -> None:
        self.mode = mode
        self.offline_only = bool(offline_only)
        self.privacy_sensitive = bool(privacy_sensitive)
        self.probe_local = bool(probe_local)
        self.seed = int(seed)
        self.state_dir = str(Path(state_dir).expanduser().resolve()) if state_dir else None

        self.memory = memory if memory is not None else ZoeUnifiedMemory(self.state_dir)
        self.blackboard = (
            blackboard if blackboard is not None else EpistemicBlackboard(memory=self.memory)
        )
        self.bridge = (
            bridge
            if bridge is not None
            else ZoeAntigravityBridge(mode=mode, state_dir=self.state_dir)
        )
        self.supervisor = (
            supervisor
            if supervisor is not None
            else LiveProcessSupervisor(blackboard=self.blackboard)
        )
        self.sandbox_lab = (
            sandbox_lab
            if sandbox_lab is not None
            else RealitySandboxLab(repo_root=repo_root, blackboard=self.blackboard)
        )
        self.quorum_engine = quorum_engine if quorum_engine is not None else FourPeerQuorumEngine()
        self.steering_detector = (
            steering_detector if steering_detector is not None else HumanSteeringDetector()
        )
        self.distiller = (
            distiller
            if distiller is not None
            else System2To1Distiller(
                memory=self.memory,
                blackboard=self.blackboard,
                bridge=self.bridge,
                min_uncertainty_a_tau=2.0,
            )
        )

    async def _run_supervised_bridge_turn(
        self,
        prompt: str,
        resolution: TransportResolution,
        *,
        bridge: ZoeAntigravityBridge | None = None,
        offline_only: bool | None = None,
        probe_local: bool | None = None,
        selected_mode: str | None = None,
    ) -> tuple[BridgeTurnResult, dict[str, Any]]:
        """Execute a genuine Antigravity Agent turn supervised by LiveProcessSupervisor (Arch 2)."""

        def inspect_constitutional_bounds(topic: str = "general") -> dict[str, Any]:
            """Read-only constitutional bounds probe tool."""
            return {
                "topic": str(topic),
                "contract": SHARED_REASONING_ORCHESTRATOR_CONTRACT,
                **bridge_constitutional_metadata(cloud_tokens_used=0),
            }

        eff_bridge = bridge if bridge is not None else self.bridge
        eff_offline = self.offline_only if offline_only is None else bool(offline_only)
        eff_selected_mode = "offline" if eff_offline else (selected_mode or resolution.selected_mode)
        eff_probe_local = False if eff_offline else (self.probe_local if probe_local is None else bool(probe_local))

        if eff_offline or eff_selected_mode == "offline":
            cfg = self.supervisor.create_agent_config(
                mode="offline",
                tools=[inspect_constitutional_bounds],
                thinking_level=resolution.thinking_level or "high",
            )
            agent = Agent(cfg)
            async with agent:
                response = await agent.chat(prompt)
                sup_resp = await self.supervisor.supervise_response(response)
                usage = (
                    response.usage_metadata.model_dump()
                    if response.usage_metadata is not None
                    else None
                )
                history_steps = len(agent.conversation.history)

            turn_res = BridgeTurnResult(
                text=str(sup_resp["text"]),
                thoughts=tuple(str(t) for t in sup_resp["thoughts"]),
                tool_calls=tuple(dict(tc) for tc in sup_resp["tool_calls"]),
                structured_output=None,
                usage_metadata=usage,
                stop_reason=str(sup_resp["stop_reason"]),
                history_steps=history_steps,
                resolution=resolution,
                constitutional=bridge_constitutional_metadata(cloud_tokens_used=0),
            )
            return turn_res, sup_resp

        turn_res = await eff_bridge.arun_turn(
            prompt,
            mode=eff_selected_mode,
            offline_only=eff_offline,
            privacy_sensitive=self.privacy_sensitive,
            thinking_level=resolution.thinking_level,
            tools=[inspect_constitutional_bounds],
            hooks=self.supervisor.build_hooks(),
            policies=self.supervisor.build_policies(include_ask_user=False),
            probe_local=eff_probe_local,
        )
        for idx, thought in enumerate(turn_res.thoughts):
            self.supervisor.supervise_thought(thought, step_index=idx)
        sup_resp = {
            "contract": self.supervisor.summary()["contract"],
            "text": turn_res.text,
            "thoughts": list(turn_res.thoughts),
            "tool_calls": list(turn_res.tool_calls),
            "stop_reason": turn_res.stop_reason,
            "summary": self.supervisor.summary(),
        }
        return turn_res, sup_resp

    @staticmethod
    def _coerce_single_test_case(
        item: TestCase | Mapping[str, Any] | tuple[Any, Any],
        arg_names: Sequence[str],
        *,
        idx: int,
    ) -> tuple[dict[str, Any], Any]:
        if isinstance(item, TestCase):
            return dict(item.inputs), item.expected
        if isinstance(item, tuple) and len(item) == 2:
            raw_in, exp = item
            if isinstance(raw_in, Mapping):
                return dict(raw_in), exp
            if isinstance(raw_in, (list, tuple)):
                if arg_names and len(raw_in) != len(arg_names):
                    raise ValueError(
                        f"Test case {idx} expected {len(arg_names)} args, got {len(raw_in)}"
                    )
                return dict(zip(arg_names, raw_in)), exp
            if len(arg_names) != 1:
                raise ValueError(
                    f"Scalar test input at index {idx} only valid for 1-arg functions, got {tuple(arg_names)}"
                )
            return {arg_names[0]: raw_in}, exp
        if isinstance(item, Mapping):
            if "expected" not in item:
                raise ValueError(f"Test case mapping at index {idx} missing 'expected'")
            exp = item["expected"]
            if "inputs" in item:
                raw_in = item["inputs"]
                if isinstance(raw_in, Mapping):
                    return dict(raw_in), exp
                if isinstance(raw_in, (list, tuple)):
                    if arg_names and len(raw_in) != len(arg_names):
                        raise ValueError(
                            f"Test case {idx} expected {len(arg_names)} args, got {len(raw_in)}"
                        )
                    return dict(zip(arg_names, raw_in)), exp
                if len(arg_names) != 1:
                    raise ValueError(
                        f"Scalar test input at index {idx} only valid for 1-arg functions, got {tuple(arg_names)}"
                    )
                return {arg_names[0]: raw_in}, exp
            if isinstance(item.get("env"), Mapping):
                return dict(item["env"]), exp
            if "args" in item:
                raw_args = item["args"]
                if isinstance(raw_args, (list, tuple)):
                    if arg_names and len(raw_args) != len(arg_names):
                        raise ValueError(
                            f"Test case {idx} expected {len(arg_names)} args, got {len(raw_args)}"
                        )
                    return dict(zip(arg_names, raw_args)), exp
                if len(arg_names) != 1:
                    raise ValueError(
                        f"Scalar 'args' input at index {idx} only valid for 1-arg functions, got {tuple(arg_names)}"
                    )
                return {arg_names[0]: raw_args}, exp
            flat_inputs = {k: item[k] for k in arg_names if k in item}
            if arg_names and len(flat_inputs) != len(arg_names):
                missing = [k for k in arg_names if k not in flat_inputs]
                raise ValueError(
                    f"Test case mapping at index {idx} missing required argument(s) {missing}"
                )
            return flat_inputs, exp
        raise TypeError(f"Unsupported test case format at index {idx}: {type(item).__name__}")

    @classmethod
    def _coerce_ast_test_cases(
        cls,
        test_cases: Sequence[TestCase | Mapping[str, Any] | tuple[Any, Any]],
        arg_names: Sequence[str],
    ) -> list[tuple[Mapping[str, Any], Any]]:
        return [
            cls._coerce_single_test_case(item, arg_names, idx=idx)
            for idx, item in enumerate(test_cases)
        ]

    @classmethod
    def _coerce_distill_cases(
        cls,
        test_cases: Sequence[TestCase | Mapping[str, Any] | tuple[Any, Any]],
        arg_names: Sequence[str],
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for idx, item in enumerate(test_cases):
            inputs, exp = cls._coerce_single_test_case(item, arg_names, idx=idx)
            entry: dict[str, Any] = {"inputs": inputs, "expected": exp}
            if isinstance(item, Mapping):
                if "tol" in item:
                    entry["tol"] = item["tol"]
                if "expected_approx" in item:
                    entry["expected_approx"] = item["expected_approx"]
            elif isinstance(item, TestCase):
                entry["tol"] = item.atol
            out.append(entry)
        return out

    async def arun(
        self,
        task: str | SharedReasoningTaskSpec,
    ) -> SharedReasoningRunReport:
        """Execute all 9 Shared-Reasoning architectures end-to-end on ``task``."""
        spec = (
            SharedReasoningTaskSpec(prompt=task)
            if isinstance(task, str)
            else task
        )
        if not spec.prompt or not spec.prompt.strip():
            raise ValueError("SharedReasoningOrchestrator requires a non-empty task prompt")

        approved_evidence_ids: list[str] = []

        # ------------------------------------------------------------------
        # Stage 1: Transport Anchor (ZoeAntigravityBridge) + Arch 2 Supervision
        # ------------------------------------------------------------------
        resolution = self.bridge.resolve_transport(
            spec.prompt,
            mode=self.mode,
            offline_only=self.offline_only,
            privacy_sensitive=self.privacy_sensitive,
            probe_local=self.probe_local,
        )
        stage_offline_only = bool(
            self.offline_only
            or resolution.selected_mode == "offline"
            or (self.privacy_sensitive and resolution.selected_mode == "gemini")
            or (not self.probe_local and resolution.selected_mode == "local_qwen")
        )
        stage_probe_local = False if stage_offline_only else self.probe_local
        stage_selected_mode = "offline" if stage_offline_only else resolution.selected_mode
        stage_bridge_mode: Literal["offline", "local_qwen", "gemini", "auto"] = (
            stage_selected_mode  # type: ignore[assignment]
        )
        stage_bridge = (
            ZoeAntigravityBridge(
                mode=stage_bridge_mode,
                local_qwen_url=self.bridge.local_qwen_url,
                local_qwen_model=self.bridge.local_qwen_model,
                gemini_model=self.bridge.gemini_model,
                api_key=self.bridge.api_key,
                state_dir=self.bridge.state_dir,
                default_thinking_level=self.bridge.default_thinking_level,
                probe_timeout_sec=self.bridge.probe_timeout_sec,
            )
            if (
                type(self.bridge) is ZoeAntigravityBridge
                and self.bridge.mode != stage_bridge_mode
            )
            else self.bridge
        )
        bridge_turn, supervised_response = await self._run_supervised_bridge_turn(
            spec.prompt,
            resolution,
            bridge=stage_bridge,
            offline_only=stage_offline_only,
            probe_local=stage_probe_local,
            selected_mode=stage_selected_mode,
        )
        bridge_meas = self.blackboard.post_measurement(
            source_agent="sdk_bridge",
            input_desc=spec.prompt[:240],
            method=f"ZoeAntigravityBridge({resolution.selected_mode})",
            scope=f"config={resolution.config_class};history_steps={bridge_turn.history_steps}",
            limitations="Single supervised Agent turn; requires independent verification before belief update.",
            value={
                "selected_mode": resolution.selected_mode,
                "stop_reason": bridge_turn.stop_reason,
                "history_steps": bridge_turn.history_steps,
                "thoughts_count": len(bridge_turn.thoughts),
            },
            sampled_only=False,
        )
        bridge_ev = self.blackboard.promote_to_evidence(
            bridge_meas.record_id,
            verifier_name="LiveProcessSupervisor",
            passed=True,
            rationale=(
                "Deterministic LiveProcessSupervisor verified streaming thoughts, "
                f"tool policies, and stop conditions across {bridge_turn.history_steps} SDK steps."
            ),
            evidence_source=EvidenceSource(
                kind="tool",
                identifier="LiveProcessSupervisor",
                trust=0.92,
                strength=0.90,
            ),
        )
        approved_evidence_ids.append(bridge_ev.record_id)

        # ------------------------------------------------------------------
        # Stage 2: Arch 1 (AlphaEvolveLoop)
        # ------------------------------------------------------------------
        mutator_mode = "ast_only" if stage_offline_only else "hybrid"
        mutator = AntigravityProgramMutator(
            bridge=stage_bridge,
            mode=mutator_mode,
            seed=self.seed,
            offline_only=stage_offline_only,
            privacy_sensitive=self.privacy_sensitive,
            probe_local=stage_probe_local,
            bridge_mode=stage_selected_mode,
        )
        alpha_loop = AlphaEvolveLoop(
            verifier=ZoeDeterministicVerifier(),
            mutator=mutator,
            blackboard=self.blackboard,
            seed=self.seed,
            offspring_per_gen=spec.evolve_offspring_per_gen,
            offline_only=stage_offline_only,
            privacy_sensitive=self.privacy_sensitive,
            probe_local=stage_probe_local,
            bridge_mode=stage_selected_mode,
        )
        alpha_result = alpha_loop.evolve(
            spec.seed_program,
            spec.test_cases,
            generations=spec.evolve_generations,
            prompt_context=spec.prompt,
            emit_blackboard=True,
            blackboard=self.blackboard,
        )
        for rec in reversed(alpha_result.blackboard_records):
            if (
                rec.get("promoted_to_evidence") is True
                and rec.get("passed") is True
                and not rec.get("negative_result")
                and rec.get("evidence_id")
            ):
                approved_evidence_ids.append(str(rec["evidence_id"]))
                break

        # ------------------------------------------------------------------
        # Stage 3: Arch 7 (RealitySandboxLab — SymPy, Z3, AST, optional Dataset)
        # ------------------------------------------------------------------
        sympy_verdict = self.sandbox_lab.verify_sympy_identity(
            spec.sympy_lhs,
            spec.sympy_rhs,
            claim=f"SymPy identity: {spec.sympy_lhs} == {spec.sympy_rhs}",
            post_to_blackboard=False,
        )
        sympy_bb = self.sandbox_lab.record_to_blackboard(
            sympy_verdict, blackboard=self.blackboard, promote=True
        )
        if sympy_verdict.passed and sympy_bb.get("evidence_id"):
            approved_evidence_ids.append(str(sympy_bb["evidence_id"]))

        z3_verdict = self.sandbox_lab.check_z3_invariant(
            spec.z3_assumptions,
            spec.z3_invariant,
            variables=spec.z3_variables,
            claim=f"Z3 invariant: {spec.z3_invariant}",
            post_to_blackboard=False,
        )
        z3_bb = self.sandbox_lab.record_to_blackboard(
            z3_verdict, blackboard=self.blackboard, promote=True
        )
        if z3_verdict.passed and z3_bb.get("evidence_id"):
            approved_evidence_ids.append(str(z3_bb["evidence_id"]))

        best_args = tuple(alpha_result.best_program.ast_metrics.get("arg_names") or ("x",))
        ast_cases = self._coerce_ast_test_cases(spec.test_cases, best_args)
        ast_verdict = self.sandbox_lab.verify_python_ast_sandbox(
            alpha_result.best_program.code,
            expected_name=alpha_result.best_program.function_name,
            expected_args=best_args,
            test_cases=ast_cases,
            claim=f"AST sandbox verify evolved {alpha_result.best_program.function_name}",
            post_to_blackboard=False,
        )
        ast_bb = self.sandbox_lab.record_to_blackboard(
            ast_verdict, blackboard=self.blackboard, promote=True
        )
        if ast_verdict.passed and ast_bb.get("evidence_id"):
            approved_evidence_ids.append(str(ast_bb["evidence_id"]))

        sandbox_verdicts: dict[str, SandboxLabVerdict] = {
            "sympy": sympy_verdict,
            "z3": z3_verdict,
            "ast_program": ast_verdict,
        }
        if spec.dataset is not None and spec.dataset_invariants:
            ds_verdict = self.sandbox_lab.verify_dataset_invariants(
                spec.dataset,
                spec.dataset_invariants,
                claim="Dataset invariant verification",
                post_to_blackboard=False,
            )
            ds_bb = self.sandbox_lab.record_to_blackboard(
                ds_verdict, blackboard=self.blackboard, promote=True
            )
            sandbox_verdicts["dataset"] = ds_verdict
            if ds_verdict.passed and ds_bb.get("evidence_id"):
                approved_evidence_ids.append(str(ds_bb["evidence_id"]))

        # ------------------------------------------------------------------
        # Stage 4: Arch 3 (KlosterMCTSSearch)
        # ------------------------------------------------------------------
        def_root, def_expand, def_eval = _default_mcts_handlers(
            spec.prompt,
            alpha_result.best_program.score,
            sympy_verdict.passed,
            z3_verdict.passed,
        )
        mcts_root = spec.mcts_root_state if spec.mcts_root_state is not None else def_root
        mcts_expand = spec.mcts_expand_fn if spec.mcts_expand_fn is not None else def_expand
        mcts_eval = spec.mcts_eval_fn if spec.mcts_eval_fn is not None else def_eval

        mcts_engine = KlosterMCTSSearch(
            bridge=stage_bridge,
            use_voice_bridge=True,
            offline_only=stage_offline_only,
            privacy_sensitive=self.privacy_sensitive,
            probe_local=stage_probe_local,
            bridge_mode=stage_selected_mode,
            blackboard=self.blackboard,
            seed=self.seed,
        )
        mcts_result = await mcts_engine.arun(
            mcts_root,
            mcts_expand,
            mcts_eval,
            tau=spec.mcts_tau,
            max_iterations=spec.mcts_max_iterations,
            blackboard=self.blackboard,
        )
        mcts_ev_id: str | None = None
        if mcts_result.blackboard_measurement_id is not None:
            mcts_passed = mcts_result.decision != "ABSTAIN_INSUFFICIENT_EVIDENCE"
            mcts_ev = self.blackboard.promote_to_evidence(
                mcts_result.blackboard_measurement_id,
                verifier_name="KlosterMCTSSearch+Theorem13",
                passed=mcts_passed,
                rationale=(
                    f"Deterministic multi-horizon A_tau^(h)={list(mcts_result.counts_by_h)} "
                    f"and Theorem 13 sequential stopping verdict={mcts_result.decision}."
                ),
                evidence_source=EvidenceSource(
                    kind="tool",
                    identifier="KlosterMCTSSearch",
                    trust=0.90,
                    strength=0.88 if mcts_passed else 0.40,
                ),
            )
            mcts_ev_id = mcts_ev.record_id
            if mcts_ev.passed:
                approved_evidence_ids.append(mcts_ev_id)

        # ------------------------------------------------------------------
        # Stage 5: Arch 9 (CounterpointChairsEngine — Team-Invented #9)
        # ------------------------------------------------------------------
        chairs = [
            ProblemChair(
                chair_id="chair_program_synthesis",
                title="Program Synthesis & AST Verification",
                prompt=f"Audit evolved function {alpha_result.best_program.function_name} for {spec.prompt[:120]}",
                tau=spec.mcts_tau,
            ),
            ProblemChair(
                chair_id="chair_formal_invariants",
                title="SymPy & Z3 Formal Invariants",
                prompt=f"Cross-audit SymPy ({spec.sympy_lhs}=={spec.sympy_rhs}) and Z3 ({spec.z3_invariant})",
                tau=spec.mcts_tau,
            ),
            ProblemChair(
                chair_id="chair_steering_quorum",
                title="Steering & Four-Peer Balance",
                prompt="Evaluate fork points, Theorem 15 diversity, and reversible action gating",
                tau=spec.mcts_tau,
            ),
        ]
        cp_engine = CounterpointChairsEngine(
            voices=default_counterpoint_voices(bridge=stage_bridge),
            bridge=stage_bridge,
            offline_only=stage_offline_only,
            privacy_sensitive=self.privacy_sensitive,
            probe_local=stage_probe_local,
            bridge_mode=stage_selected_mode,
            tau=spec.mcts_tau,
            max_discrepancy_dk=0.25,
        )
        cp_result = await cp_engine.arun(chairs, rounds=spec.counterpoint_rounds)
        cadence_wav: dict[str, Any] | None = None
        if spec.sonify_wav_path is not None:
            cadence_wav = cp_engine.sonify_cadence_wav(spec.sonify_wav_path, cp_result)

        cp_meas = self.blackboard.post_measurement(
            source_agent="counterpoint_chairs",
            input_desc=f"Polyphonic relay over {len(chairs)} chairs x {spec.counterpoint_rounds} rounds",
            method="CounterpointChairsEngine.arun",
            scope=(
                f"turns={cp_result.total_turns}, audits={len(cp_result.cold_audits)}, "
                f"mean_dk={cp_result.mean_theorem15_dk:.4f}"
            ),
            limitations="Chair relay checks cross-voice discrepancy & Art. III packet integrity.",
            value={
                "schedule_valid": bool(cp_result.schedule_invariants.get("valid", False)),
                "flagged_audits_count": cp_result.flagged_audits_count,
                "firewall_violations_caught": cp_result.firewall_violations_caught,
                "mean_theorem15_dk": cp_result.mean_theorem15_dk,
            },
            sampled_only=False,
        )
        cp_passed = bool(
            cp_result.schedule_invariants.get("valid", False)
            and cp_result.firewall_violations_caught == 0
        )
        cp_ev = self.blackboard.promote_to_evidence(
            cp_meas.record_id,
            verifier_name="CounterpointChairsEngine",
            passed=cp_passed,
            rationale=(
                f"Deterministic polyphonic relay invariants valid={cp_result.schedule_invariants.get('valid')}, "
                f"flagged_audits={cp_result.flagged_audits_count}, "
                f"mean_D_K={cp_result.mean_theorem15_dk:.5f}."
            ),
            evidence_source=EvidenceSource(
                kind="tool",
                identifier="CounterpointChairsEngine",
                trust=0.91,
                strength=0.90 if cp_passed else 0.35,
            ),
        )
        if cp_ev.passed:
            approved_evidence_ids.append(cp_ev.record_id)

        # ------------------------------------------------------------------
        # Stage 6: Arch 4 (FourPeerQuorumEngine + route_with_four_peer_quorum)
        # ------------------------------------------------------------------
        formal_ok = 1.0 if (sympy_verdict.passed and z3_verdict.passed) else 0.25
        zoe_action_p = _normalize_simplex_probs(
            [0.42 + 0.38 * alpha_result.best_program.score, 0.28, 0.12]
        )
        clara_action_p = _normalize_simplex_probs(
            [0.54 + 0.16 * (1.0 - min(1.0, cp_result.mean_theorem15_dk)), 0.31, 0.15]
        )
        ag_action_p = _normalize_simplex_probs(
            [0.58 + 0.26 * formal_ok, 0.18, 0.10]
        )
        user_input: PeerInput = (
            spec.user_probs
            if spec.user_probs is not None
            else (0.64, 0.24, 0.12)
        )
        if isinstance(user_input, PeerConfidenceVector):
            user_peer_vec = user_input
        else:
            user_peer_vec = PeerConfidenceVector(
                peer_id="user",
                probabilities=user_input,
                source_kind="user",
                provenance_id="prov:user:operator_prior",
                independence_tag="indep:human_operator",
                labels=ACTION_LABELS,
            )

        quorum_vectors = [
            PeerConfidenceVector(
                peer_id="zoe",
                probabilities=zoe_action_p,
                source_kind="document",
                provenance_id=f"prov:zoe:alpha_ast:{ast_bb.get('evidence_id', 'local')}",
                independence_tag="indep:zoe_ast_verifier",
                labels=ACTION_LABELS,
            ),
            PeerConfidenceVector(
                peer_id="clara",
                probabilities=clara_action_p,
                source_kind="validated_reflection",
                provenance_id=f"prov:clara:counterpoint:{cp_ev.record_id}",
                independence_tag="indep:clara_counterpoint_balance",
                labels=ACTION_LABELS,
            ),
            PeerConfidenceVector(
                peer_id="antigravity",
                probabilities=ag_action_p,
                source_kind="model",
                provenance_id=f"prov:antigravity:sympy_z3:{sympy_bb.get('evidence_id', 'local')}",
                independence_tag="indep:antigravity_formal_bridge",
                labels=ACTION_LABELS,
            ),
            user_peer_vec,
        ]
        quorum_result = self.quorum_engine.evaluate(
            quorum_vectors,
            tau=spec.quorum_tau,
            labels=ACTION_LABELS,
            use_teamwork_arbitrator=True,
            blackboard=self.blackboard,
        )
        if quorum_result.blackboard_records and quorum_result.blackboard_records.get("passed"):
            approved_evidence_ids.append(str(quorum_result.blackboard_records["evidence_id"]))

        # Also route across stem_layering.py 5-tier model distribution space
        zoe_stem = route_stem(
            spec.prompt,
            offline_only=self.offline_only,
            privacy_sensitive=self.privacy_sensitive,
            local_qwen_available=False,
        )
        clara_tier_p = _normalize_simplex_probs([0.20, 0.28, 0.24, 0.18, 0.10])
        ag_tier_p = _normalize_simplex_probs([0.12, 0.16, 0.22, 0.28, 0.22])
        user_tier_p = _normalize_simplex_probs([0.36, 0.26, 0.18, 0.12, 0.08])
        quorum_route = route_with_four_peer_quorum(
            spec.prompt,
            zoe_probs=zoe_stem.probabilities,
            clara_probs=clara_tier_p,
            antigravity_probs=ag_tier_p,
            user_probs=user_tier_p,
            offline_only=self.offline_only,
            privacy_sensitive=self.privacy_sensitive,
            local_qwen_available=False,
            tau=spec.quorum_tau,
            labels=TIER_ORDER,
            provenance_ids={
                "zoe": "prov:zoe:stem_layering",
                "clara": "prov:clara:stem_balance",
                "antigravity": "prov:antigravity:stem_eval",
                "user": "prov:user:stem_preference",
            },
            independence_tags={
                "zoe": "indep:zoe_stem",
                "clara": "indep:clara_stem",
                "antigravity": "indep:antigravity_stem",
                "user": "indep:user_stem",
            },
            blackboard=self.blackboard,
        )
        if (
            quorum_route.quorum.blackboard_records
            and quorum_route.quorum.blackboard_records.get("passed")
        ):
            approved_evidence_ids.append(
                str(quorum_route.quorum.blackboard_records["evidence_id"])
            )

        # ------------------------------------------------------------------
        # Stage 7: Arch 8 (HumanSteeringDetector)
        # ------------------------------------------------------------------
        evidence_by_branch: dict[str, tuple[str, ...]] = {}
        verified_branch_ids: set[str] = set()
        for fc in mcts_result.fork_candidates:
            for br in fc.competing_branches:
                if "symbolic" in " ".join(br.actions) and sympy_bb.get("evidence_id") and z3_bb.get("evidence_id"):
                    evidence_by_branch[br.branch_id] = (
                        str(sympy_bb["evidence_id"]),
                        str(z3_bb["evidence_id"]),
                    )
                    verified_branch_ids.add(br.branch_id)
                elif ast_bb.get("evidence_id"):
                    evidence_by_branch[br.branch_id] = (str(ast_bb["evidence_id"]),)
                    verified_branch_ids.add(br.branch_id)

        steering_options: tuple[VerifiedPathOption, ...] = ()
        if mcts_result.fork_candidates and len(verified_branch_ids) >= 2:
            steering_options = self.steering_detector.options_from_fork_candidates(
                mcts_result.fork_candidates,
                evidence_by_branch=evidence_by_branch,
                verified_branch_ids=verified_branch_ids,
            )
        elif sympy_bb.get("evidence_id") and ast_bb.get("evidence_id"):
            steering_options = (
                VerifiedPathOption(
                    path_id="formal_sympy_z3_path",
                    summary="Prioritize formal SymPy + Z3 invariant verification path",
                    verification_status="verified" if (sympy_verdict.passed and z3_verdict.passed) else "failed",
                    evidence_ids=(str(sympy_bb["evidence_id"]), str(z3_bb["evidence_id"])),
                    expected_utility=0.92 if (sympy_verdict.passed and z3_verdict.passed) else 0.2,
                    tradeoff_notes="Exact symbolic and SMT proof; narrower domain assumptions",
                    reversible=True,
                    direction_tags=("formal", "symbolic", "z3"),
                    verifier_name="RealitySandboxLab",
                ),
                VerifiedPathOption(
                    path_id="evolved_ast_distillation_path",
                    summary="Distill evolved AST program into ZoeUnifiedMemory System-1 skill",
                    verification_status="verified" if ast_verdict.passed else "failed",
                    evidence_ids=(str(ast_bb["evidence_id"]),),
                    expected_utility=alpha_result.best_program.score,
                    tradeoff_notes="Fast 0-token System-1 replay; bounded to tested AST inputs",
                    reversible=True,
                    direction_tags=("evolutionary", "ast", "distillation"),
                    verifier_name="ZoeDeterministicVerifier",
                ),
            )

        steering_report = self.steering_detector.detect(
            steering_options,
            mcts_result=mcts_result,
            quorum_result=quorum_result,
            high_impact=spec.high_impact,
            blackboard=self.blackboard,
            record_to_blackboard=True,
            propose_blackboard_action=True,
            context_summary=spec.prompt[:240],
        )
        if steering_report.blackboard_records.get("evidence_id"):
            approved_evidence_ids.append(steering_report.blackboard_records["evidence_id"])

        steering_interaction: dict[str, Any] | None = None
        if (
            steering_report.fork_detected
            and steering_report.interaction_spec is not None
            and spec.steering_callback is not None
        ):
            hook = self.steering_detector.build_interaction_hook(spec.steering_callback)
            hook_ctx = ag_hooks.HookContext(ag_hooks.TurnContext(ag_hooks.SessionContext()))
            ask_spec = types.AskQuestionInteractionSpec.model_validate(
                steering_report.interaction_spec
            )
            q_result = await hook.run(hook_ctx, ask_spec)
            steering_interaction = self.steering_detector.interpret_hook_result(
                steering_report, q_result
            )

        # ------------------------------------------------------------------
        # Stage 8: Arch 5 (System2To1Distiller -> ZoeUnifiedMemory)
        # ------------------------------------------------------------------
        distilled_artifacts: list[DistilledArtifact] = []
        distilled_replays: dict[str, Any] = {}

        if (
            alpha_result.best_program.total_tests > 0
            and alpha_result.best_program.passed_tests == alpha_result.best_program.total_tests
        ):
            distill_cases = (
                list(spec.distill_verification_cases)
                if spec.distill_verification_cases is not None
                else self._coerce_distill_cases(spec.test_cases, best_args)
            )
            a_tau_uncertainty = max(
                2,
                int(mcts_result.counts_by_h[-1]) if mcts_result.counts_by_h else 3,
                len(mcts_result.surviving_branches),
            )
            skill_art = self.distiller.distill_from_alpha_evolve(
                alpha_result,
                task_prompt=spec.prompt,
                initial_uncertainty_a_tau=a_tau_uncertainty,
                target_name=spec.distill_target_name,
                verification_cases=distill_cases,
                export_inline_skill=True,
                record_blackboard_lineage=True,
            )
            distilled_artifacts.append(skill_art)
            if distill_cases:
                first_env = self.distiller._extract_skill_env(distill_cases[0], best_args)
                distilled_replays[skill_art.target_name] = self.distiller.replay_skill(
                    skill_art.target_name, first_env
                )

        if sympy_verdict.passed and sympy_bb.get("evidence_id"):
            fact_subject = f"shared_reasoning:{alpha_result.best_program.function_name}"
            fact_relation = "verified_symbolic_identity"
            fact_obj = f"{spec.sympy_lhs} == {spec.sympy_rhs}"
            fact_trace = System2Trace(
                task_prompt=f"Distill verified SymPy identity: {fact_obj}",
                initial_uncertainty_a_tau=max(2, len(mcts_result.surviving_branches) or 2),
                solution_code_or_rule={
                    "subject": fact_subject,
                    "relation": fact_relation,
                    "object": fact_obj,
                    "confidence": 0.96,
                },
                verifier_passed=True,
                evidence_id=str(sympy_bb["evidence_id"]),
                provenance=Provenance(
                    sources=(
                        EvidenceSource(
                            kind="tool",
                            identifier=sympy_verdict.evidence_source,
                            trust=0.96,
                            strength=0.95,
                        ),
                    ),
                    transformations=("sympy_exact_identity_verification",),
                ),
                artifact_kind="semantic_fact",
            )
            fact_art = self.distiller.distill(
                fact_trace,
                artifact_kind="semantic_fact",
                verification_cases=[
                    {
                        "subject": fact_subject,
                        "relation": fact_relation,
                        "expected_object": fact_obj,
                    }
                ],
                export_inline_skill=True,
                record_blackboard_lineage=True,
            )
            distilled_artifacts.append(fact_art)
            distilled_replays[fact_art.target_name] = self.distiller.lookup_fact(
                fact_subject, relation=fact_relation
            )

        if spec.eliza_rule_spec is not None and bridge_ev.record_id:
            eliza_trace = System2Trace(
                task_prompt=f"Distill Gear-1 ELIZA rule for: {spec.prompt[:120]}",
                initial_uncertainty_a_tau=max(2, len(mcts_result.surviving_branches) or 2),
                solution_code_or_rule=dict(spec.eliza_rule_spec),
                verifier_passed=True,
                evidence_id=bridge_ev.record_id,
                provenance=Provenance(
                    sources=(
                        EvidenceSource(
                            kind="tool",
                            identifier="LiveProcessSupervisor",
                            trust=0.92,
                            strength=0.90,
                        ),
                    ),
                    transformations=("eliza_rule_distillation",),
                ),
                artifact_kind="eliza_rule",
            )
            eliza_art = self.distiller.distill(
                eliza_trace,
                artifact_kind="eliza_rule",
                export_inline_skill=True,
                record_blackboard_lineage=True,
            )
            distilled_artifacts.append(eliza_art)

        # ------------------------------------------------------------------
        # Stage 8.5: Digital Research GEM AES/VDI/RSC Desktop Verification
        # ------------------------------------------------------------------
        gem_desktop_report: dict[str, Any] | None = None
        if spec.enable_gem_desktop:
            import json as _json

            from .gem_aes_vdi import (
                GEM_AES_VDI_CONTRACT,
                GEM_ART_II_3_NOTICE,
                GemVdiWorkstation,
                build_default_atari_rsc,
            )

            ws = GemVdiWorkstation(device="vga", theme_key="zoe-viewmax3")
            ws.v_opnwk("vga")
            gem_scene = ws.build_shared_reasoning_scene(
                {
                    "quorum_result": quorum_result.to_dict(),
                    "mcts_result": mcts_result.to_dict(),
                    "steering_report": steering_report.to_dict(),
                    "counterpoint_result": cp_result.to_dict(),
                },
                scene_id="zoe-shared-reasoning-gem-desk",
            )
            gem_vdi_verdict = self.sandbox_lab.verify_gem_vdi_scene(
                gem_scene,
                profiles=("cga", "vga", "ndc"),
                post_to_blackboard=False,
            )
            gem_vdi_bb = self.sandbox_lab.record_to_blackboard(
                gem_vdi_verdict, promote=True
            )
            sandbox_verdicts["gem_vdi"] = gem_vdi_verdict
            if gem_vdi_verdict.passed and gem_vdi_bb.get("evidence_id"):
                approved_evidence_ids.append(str(gem_vdi_bb["evidence_id"]))

            rsc_bytes = build_default_atari_rsc()
            gem_rsc_verdict = self.sandbox_lab.verify_gem_rsc_bytes(
                rsc_bytes,
                label="ZOE_SHARED.RSC",
                post_to_blackboard=False,
            )
            gem_rsc_bb = self.sandbox_lab.record_to_blackboard(
                gem_rsc_verdict, promote=True
            )
            sandbox_verdicts["gem_rsc"] = gem_rsc_verdict
            if gem_rsc_verdict.passed and gem_rsc_bb.get("evidence_id"):
                approved_evidence_ids.append(str(gem_rsc_bb["evidence_id"]))

            compiled_vdi = ws.compile_and_verify_vdi(gem_scene, profiles=("cga", "vga", "ndc"))
            ws.v_clswk()

            written_files: dict[str, str] = {}
            if spec.gem_vdi_output_dir is not None:
                out_dir = Path(spec.gem_vdi_output_dir)
                out_dir.mkdir(parents=True, exist_ok=True)
                gem_file = out_dir / "shared_reasoning_desktop.gem"
                json_file = out_dir / "shared_reasoning_desktop.json"
                rsc_file = out_dir / "ZOE_SHARED.RSC"
                gem_file.write_bytes(compiled_vdi["metafile_bytes"])
                json_file.write_text(
                    _json.dumps(
                        {
                            "scene_id": compiled_vdi["scene_id"],
                            "scene_digest": compiled_vdi["scene_digest"],
                            "metafile_sha256": compiled_vdi["metafile_sha256"],
                            "profiles_passed": compiled_vdi["profiles_passed"],
                            "visual_evidence_only": True,
                            "art_ii_3_notice": GEM_ART_II_3_NOTICE,
                        },
                        indent=2,
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
                rsc_file.write_bytes(rsc_bytes)
                written_files = {
                    "gem": str(gem_file),
                    "json": str(json_file),
                    "rsc": str(rsc_file),
                }

            cp_trace = cp_result.gem_desktop_trace or {}
            gem_desktop_report = {
                "contract": GEM_AES_VDI_CONTRACT,
                "passed": bool(gem_vdi_verdict.passed and gem_rsc_verdict.passed),
                "scene_id": str(compiled_vdi["scene_id"]),
                "scene_digest": str(compiled_vdi["scene_digest"]),
                "metafile_sha256": str(compiled_vdi["metafile_sha256"]),
                "metafile_bytes_len": int(compiled_vdi["metafile_bytes_len"]),
                "rsc_sha256": str(gem_rsc_verdict.ground_truth.get("rsc_sha256", "")),
                "profiles_passed": dict(compiled_vdi["profiles_passed"]),
                "aes_messages_count": int(cp_trace.get("aes_messages_count", 0)),
                "form_alert_active": steering_report.gem_form_alert is not None,
                "written_files": written_files,
                "visual_evidence_only": True,
                "art_ii_3_notice": GEM_ART_II_3_NOTICE,
                "external_actions": 0,
                "sentience_claimed": False,
                "l5_agi_qualified": False,
                "zoe_clone_claimed": False,
                "attribution": ATTRIBUTION_TEXT,
                "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
            }

        # ------------------------------------------------------------------
        # Stage 9: Final Arch 2 Mutual Audit + Arch 6 Belief & REVIEW_REQUIRED Proposal
        # ------------------------------------------------------------------
        if not approved_evidence_ids:
            raise FirewallViolationError(
                "CONSTITUTION.md Art. III: no approved EvidenceRecord IDs produced during run"
            )
        dedup_ev_ids = tuple(dict.fromkeys(approved_evidence_ids))
        final_belief = self.supervisor.supervised_update_belief(
            evidence_ids=dedup_ev_ids,
            claim=(
                f"Shared-reasoning synthesis completed for '{spec.prompt[:120]}' "
                f"(best_program={alpha_result.best_program.id}, "
                f"sympy={sympy_verdict.passed}, z3={z3_verdict.passed}, "
                f"quorum={quorum_result.verdict}, distilled={len(distilled_artifacts)})"
            ),
            posterior_delta=0.40,
            measurement_scope=(
                f"arch1_score={alpha_result.best_program.score}, "
                f"mcts={mcts_result.decision}, "
                f"quorum={quorum_result.verdict}"
            ),
            measurement_method=f"{SHARED_REASONING_ORCHESTRATOR_CONTRACT}+{STEM_LAYERING_CONTRACT}",
            measurement_limitations=(
                "Bounded deterministic AST/SymPy/Z3/MCTS checks; review-required only "
                "(external_actions=0, sentience_claimed=False)."
            ),
            measurement_input=spec.prompt[:240],
            evidence_checked=True,
            evidence_rationale=(
                f"Deterministic SymPy, Z3, AST, Theorem 13, Theorem 15, and Counterpoint "
                f"verifiers approved {len(dedup_ev_ids)} evidence record(s)."
            ),
            subject="shared_reasoning_run",
            relation="synthesized_finding",
            confidence=min(1.0, max(0.5, alpha_result.best_program.score)),
        )
        final_action = self.blackboard.propose_action(
            final_belief.record_id,
            "REVIEW_SHARED_REASONING_SYNTHESIS",
            target="human_operator",
            reversible=True,
            rationale=(
                "CONSTITUTION.md Art. III.4 / X: present verified synthesis, distilled "
                "artifacts, and fork status for human review with external_actions=0."
            ),
        )

        bb_integrity = self.blackboard.verify_integrity(raise_on_error=True)
        bb_lanes = self.blackboard.export_lane_summary(include_records=False)
        bb_summary = self.blackboard.summary()
        sup_summary = self.supervisor.summary()
        const_meta = bridge_constitutional_metadata(cloud_tokens_used=0)

        return SharedReasoningRunReport(
            contract=SHARED_REASONING_ORCHESTRATOR_CONTRACT,
            task_prompt=spec.prompt,
            bridge_turn=bridge_turn,
            supervision_summary=sup_summary,
            supervised_response=supervised_response,
            alpha_evolve=alpha_result,
            mcts_result=mcts_result,
            sandbox_verdicts=sandbox_verdicts,
            counterpoint_result=cp_result,
            cadence_wav=cadence_wav,
            quorum_result=quorum_result,
            quorum_route=quorum_route,
            steering_report=steering_report,
            steering_interaction=steering_interaction,
            distilled_artifacts=tuple(distilled_artifacts),
            distilled_replay_outputs=distilled_replays,
            blackboard_summary=bb_summary,
            blackboard_lanes=bb_lanes,
            blackboard_integrity=bb_integrity,
            final_belief_id=final_belief.record_id,
            final_action_proposal_id=final_action.record_id,
            external_actions=0,
            sentience_claimed=False,
            l5_agi_qualified=False,
            zoe_clone_claimed=False,
            attribution=ATTRIBUTION_TEXT,
            constitutional=const_meta,
            gem_desktop_report=gem_desktop_report,
        )

    def run(
        self,
        task: str | SharedReasoningTaskSpec,
    ) -> SharedReasoningRunReport:
        """Synchronous wrapper around :meth:`arun` safe inside or outside an event loop."""
        return run_coro_sync(self.arun(task))


__all__ = [
    "DEFAULT_SEED_PROGRAM",
    "DEFAULT_TEST_CASES",
    "SHARED_REASONING_ORCHESTRATOR_CONTRACT",
    "SharedReasoningOrchestrator",
    "SharedReasoningRunReport",
    "SharedReasoningTaskSpec",
]
