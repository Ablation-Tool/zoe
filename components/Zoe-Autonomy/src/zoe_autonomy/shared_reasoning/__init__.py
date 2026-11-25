"""Zoe x Antigravity Shared-Reasoning Architectures (1-9) package.

Exports the M2 dual-transport ``google.antigravity`` SDK bridge immediately
and provides clean lazy resolution for Arch 1-9 submodules and the unified
``SharedReasoningOrchestrator``.
"""

from __future__ import annotations

import importlib
from types import ModuleType
from typing import TYPE_CHECKING, Any

from . import sdk_bridge
from .sdk_bridge import (
    ATTRIBUTION_TEXT,
    SDK_BRIDGE_CONTRACT,
    VALID_MODES,
    BridgeTurnResult,
    CallableVoiceAdapter,
    DualTransportAgentConfig,
    DualTransportStrategy,
    OfflineAntigravityConnection,
    ReasoningVoiceAdapter,
    TransportResolution,
    VoiceResponse,
    ZoeAntigravityBridge,
    ZoeOfflineVoiceAdapter,
    bridge_constitutional_metadata,
    run_coro_sync,
)

if TYPE_CHECKING:
    from .alpha_evolve import (
        AlphaEvolveLoop,
        AlphaEvolveResult,
        AntigravityProgramMutator,
        CandidateProgram,
        EvolutionaryArchive,
        TestCase,
        VerificationReport,
        ZoeDeterministicVerifier,
    )
    from .blackboard import (
        ActionProposalRecord,
        BeliefUpdateRecord,
        EpistemicBlackboard,
        EvidenceRecord,
        FirewallViolationError,
        MeasurementRecord,
        TamperDetectedError,
    )
    from .counterpoint_chairs import (
        ChairVoice,
        ColdAuditVerdict,
        CounterpointChairsEngine,
        CounterpointRelayResult,
        CounterpointRotationSchedule,
        FrozenChairPacket,
        ProblemChair,
        SwapLedgerEntry,
        default_counterpoint_voices,
    )
    from .distillation import (
        DistillationRegressionError,
        DistillationRejectedError,
        DistilledArtifact,
        DistilledInlineSkill,
        DistilledRuleRegistry,
        System2To1Distiller,
        System2Trace,
    )
    from .gem_aes_vdi import (
        GEM_AES_VDI_CONTRACT,
        GEM_ART_II_3_NOTICE,
        GEM_HISTORICAL_CREDIT,
        MAX_AES_APP_WINDOWS,
        MAX_GEM_METAFILE_BYTES,
        MN_SELECTED,
        MU_BUTTON,
        MU_KEYBD,
        MU_M1,
        MU_M2,
        MU_MESAG,
        MU_TIMER,
        WM_CLOSED,
        WM_FULLED,
        WM_MOVED,
        WM_NEWTOP,
        WM_REDRAW,
        WM_TOPPED,
        WM_UNTOPPED,
        GemEventMultiQueue,
        GemEventResult,
        GemFormAlert,
        GemVdiWorkstation,
        GemWindowManager,
        build_default_atari_rsc,
        build_form_alert,
        inspect_gem_rsc,
    )
    from .human_steering import (
        ForkPointReport,
        HumanSteeringDetector,
        VerifiedPathOption,
    )
    from .mcts_kloster import (
        ForkCandidate,
        KlosterMCTSSearch,
        MCTSBranchTrajectory,
        MCTSSearchResult,
        ThoughtCandidate,
        ThoughtNode,
    )
    from .orchestrator import (
        SHARED_REASONING_ORCHESTRATOR_CONTRACT,
        SharedReasoningOrchestrator,
        SharedReasoningRunReport,
        SharedReasoningTaskSpec,
    )
    from .process_supervision import (
        LiveProcessSupervisor,
        MutualAuditFinding,
        SupervisionEvent,
        SupervisionPolicyRule,
        ZoeTransitionProposal,
    )
    from .quorum import (
        FourPeerQuorumEngine,
        FourPeerQuorumResult,
        FourPeerRouteResult,
        PeerConfidenceVector,
        evaluate_four_peer_quorum,
        quorum_from_dual_peer_balance,
        route_with_four_peer_quorum,
    )
    from .sandbox_labs import (
        RealitySandboxLab,
        SandboxLabVerdict,
        post_verdict_to_blackboard,
    )

SHARED_REASONING_CONTRACT = "zoe-antigravity-shared-reasoning/v1"

CONSTITUTIONAL_METADATA: dict[str, Any] = {
    "external_actions": 0,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "zoe_clone_claimed": False,
    "attribution": "Nicholas Michael Kloster, March 6, 2026",
}

_LAZY_SUBMODULES: tuple[str, ...] = (
    "alpha_evolve",
    "process_supervision",
    "mcts_kloster",
    "quorum",
    "distillation",
    "blackboard",
    "sandbox_labs",
    "human_steering",
    "counterpoint_chairs",
    "gem_aes_vdi",
    "orchestrator",
)

# Map Arch 1-9 & Composer public symbols -> owning submodule for clean lazy re-export.
_LAZY_SYMBOLS: dict[str, str] = {
    # Arch 1
    "AlphaEvolveLoop": "alpha_evolve",
    "AlphaEvolveResult": "alpha_evolve",
    "AntigravityProgramMutator": "alpha_evolve",
    "CandidateProgram": "alpha_evolve",
    "EvolutionaryArchive": "alpha_evolve",
    "TestCase": "alpha_evolve",
    "VerificationReport": "alpha_evolve",
    "ZoeDeterministicVerifier": "alpha_evolve",
    # Arch 2
    "LiveProcessSupervisor": "process_supervision",
    "MutualAuditFinding": "process_supervision",
    "SupervisionEvent": "process_supervision",
    "SupervisionPolicyRule": "process_supervision",
    "ZoeTransitionProposal": "process_supervision",
    # Arch 3
    "ForkCandidate": "mcts_kloster",
    "KlosterMCTSSearch": "mcts_kloster",
    "MCTSBranchTrajectory": "mcts_kloster",
    "MCTSSearchResult": "mcts_kloster",
    "ThoughtCandidate": "mcts_kloster",
    "ThoughtNode": "mcts_kloster",
    # Arch 4
    "FourPeerQuorumEngine": "quorum",
    "FourPeerQuorumResult": "quorum",
    "FourPeerRouteResult": "quorum",
    "PeerConfidenceVector": "quorum",
    "evaluate_four_peer_quorum": "quorum",
    "quorum_from_dual_peer_balance": "quorum",
    "route_with_four_peer_quorum": "quorum",
    # Arch 5
    "DistillationRegressionError": "distillation",
    "DistillationRejectedError": "distillation",
    "DistilledArtifact": "distillation",
    "DistilledInlineSkill": "distillation",
    "DistilledRuleRegistry": "distillation",
    "System2To1Distiller": "distillation",
    "System2Trace": "distillation",
    # Arch 6
    "ActionProposalRecord": "blackboard",
    "BeliefUpdateRecord": "blackboard",
    "EpistemicBlackboard": "blackboard",
    "EvidenceRecord": "blackboard",
    "FirewallViolationError": "blackboard",
    "MeasurementRecord": "blackboard",
    "TamperDetectedError": "blackboard",
    # Arch 7
    "RealitySandboxLab": "sandbox_labs",
    "SandboxLabVerdict": "sandbox_labs",
    "post_verdict_to_blackboard": "sandbox_labs",
    # Arch 8
    "ForkPointReport": "human_steering",
    "HumanSteeringDetector": "human_steering",
    "VerifiedPathOption": "human_steering",
    # Arch 9
    "ChairVoice": "counterpoint_chairs",
    "ColdAuditVerdict": "counterpoint_chairs",
    "CounterpointChairsEngine": "counterpoint_chairs",
    "CounterpointRelayResult": "counterpoint_chairs",
    "CounterpointRotationSchedule": "counterpoint_chairs",
    "FrozenChairPacket": "counterpoint_chairs",
    "ProblemChair": "counterpoint_chairs",
    "SwapLedgerEntry": "counterpoint_chairs",
    "default_counterpoint_voices": "counterpoint_chairs",
    # Digital Research GEM (seasip.info AES/VDI/RSC/ViewMAX)
    "GEM_AES_VDI_CONTRACT": "gem_aes_vdi",
    "GEM_ART_II_3_NOTICE": "gem_aes_vdi",
    "GEM_HISTORICAL_CREDIT": "gem_aes_vdi",
    "MAX_AES_APP_WINDOWS": "gem_aes_vdi",
    "MAX_GEM_METAFILE_BYTES": "gem_aes_vdi",
    "MN_SELECTED": "gem_aes_vdi",
    "MU_BUTTON": "gem_aes_vdi",
    "MU_KEYBD": "gem_aes_vdi",
    "MU_M1": "gem_aes_vdi",
    "MU_M2": "gem_aes_vdi",
    "MU_MESAG": "gem_aes_vdi",
    "MU_TIMER": "gem_aes_vdi",
    "WM_CLOSED": "gem_aes_vdi",
    "WM_FULLED": "gem_aes_vdi",
    "WM_MOVED": "gem_aes_vdi",
    "WM_NEWTOP": "gem_aes_vdi",
    "WM_REDRAW": "gem_aes_vdi",
    "WM_TOPPED": "gem_aes_vdi",
    "WM_UNTOPPED": "gem_aes_vdi",
    "GemEventMultiQueue": "gem_aes_vdi",
    "GemEventResult": "gem_aes_vdi",
    "GemFormAlert": "gem_aes_vdi",
    "GemVdiWorkstation": "gem_aes_vdi",
    "GemWindowManager": "gem_aes_vdi",
    "build_default_atari_rsc": "gem_aes_vdi",
    "build_form_alert": "gem_aes_vdi",
    "inspect_gem_rsc": "gem_aes_vdi",
    # Composer
    "SHARED_REASONING_ORCHESTRATOR_CONTRACT": "orchestrator",
    "SharedReasoningOrchestrator": "orchestrator",
    "SharedReasoningRunReport": "orchestrator",
    "SharedReasoningTaskSpec": "orchestrator",
}


def load_submodule(name: str) -> ModuleType:
    """Import and cache a ``shared_reasoning`` submodule by name."""
    if name not in _LAZY_SUBMODULES and name != "sdk_bridge":
        raise ImportError(f"Unknown shared_reasoning submodule: {name!r}")
    module = importlib.import_module(f"{__name__}.{name}")
    globals()[name] = module
    return module


def available_submodules() -> dict[str, bool]:
    """Report availability of ``sdk_bridge`` and Arch 1-9 submodules without raising."""
    status: dict[str, bool] = {"sdk_bridge": True}
    for sub in _LAZY_SUBMODULES:
        try:
            importlib.import_module(f"{__name__}.{sub}")
            status[sub] = True
        except ImportError:
            status[sub] = False
    return status


def __getattr__(name: str) -> Any:
    if name in _LAZY_SUBMODULES:
        try:
            return load_submodule(name)
        except ImportError as exc:
            raise AttributeError(
                f"module {__name__!r} submodule {name!r} is not yet available: {exc}"
            ) from exc
    if name in _LAZY_SYMBOLS:
        sub = _LAZY_SYMBOLS[name]
        try:
            mod = load_submodule(sub)
        except ImportError as exc:
            raise AttributeError(
                f"module {__name__!r} attribute {name!r} requires submodule {sub!r}: {exc}"
            ) from exc
        if hasattr(mod, name):
            val = getattr(mod, name)
            globals()[name] = val
            return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "ATTRIBUTION_TEXT",
    "CONSTITUTIONAL_METADATA",
    "SHARED_REASONING_CONTRACT",
    "SDK_BRIDGE_CONTRACT",
    "VALID_MODES",
    "BridgeTurnResult",
    "CallableVoiceAdapter",
    "DualTransportAgentConfig",
    "DualTransportStrategy",
    "OfflineAntigravityConnection",
    "ReasoningVoiceAdapter",
    "TransportResolution",
    "VoiceResponse",
    "ZoeAntigravityBridge",
    "ZoeOfflineVoiceAdapter",
    "available_submodules",
    "bridge_constitutional_metadata",
    "load_submodule",
    "run_coro_sync",
    "sdk_bridge",
    *_LAZY_SYMBOLS.keys(),
]
