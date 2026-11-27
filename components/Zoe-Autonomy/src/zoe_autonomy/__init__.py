"""Operational full self-governing autonomy through Zoe and Operational Metacognition."""

from importlib import import_module

from .actuation import ActuationPolicy
from .agents import AgentGateway
from .explore import WebExplorer
from .loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, SandboxPolicy
from .metrics import accessible_volume, effective_perception, kl_divergence_bits
from .self_reflection import run_reflection, verify_reflection


# Declarative lazy export table mapping public symbol names to submodules.
_LAZY_EXPORT_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("event_autonomy", ("EventCausalEngine",)),
    ("trust_gradient", ("TrustEngine",)),
    (
        "epistemic_firewall",
        (
            "ZoeEpistemicGate",
            "lint_zoe_capability_policy",
            "scan_sealed_corpus_schema",
            "screen_findings_with_winnow",
            "audit_repo_stewardship",
        ),
    ),
    (
        "cognitive_upgrades",
        (
            "farg_coherence_to_temperature",
            "run_farg_metacognitive_analogy",
            "ZoeColorCascadeGuard",
            "ZoeCalibrationTracker",
        ),
    ),
    (
        "dorothy_research_upgrades",
        (
            "screen_dorothy_sequence_homology",
            "ApprovedDomainAllowlist",
            "build_warrant_grounded_plan",
        ),
    ),
    (
        "wave2_security_forensics",
        (
            "screen_audio_metadata_with_dba",
            "inventory_re_corpus_with_metrix",
            "seal_evidence_with_gemseal",
            "unseal_evidence_with_gemseal",
            "scan_mcp_server_with_mcp_security",
            "screen_mcp_tool_with_guard",
            "analyze_authorization_context_with_cortex",
            "validate_asset_record_with_schema",
            "analyze_rxvm_crypto_pipeline",
            "decrypt_rxvm_rxc_cookie",
            "analyze_a10_quantization_saturation",
            "analyze_beam_obfuscation",
            "wave2_native_tooling_inventory",
        ),
    ),
    (
        "wave2_platform_upgrades",
        (
            "build_nina_voice_filtergraph",
            "list_foxhound_onnx_models",
            "find_zoe_capability",
            "refine_prompt_with_architect",
            "select_dcwf_agent_roles",
            "evaluate_atlas_stack_risk",
            "wave2_research_and_platform_catalog",
        ),
    ),
    (
        "wave3_vault_upgrades",
        (
            "build_lume_trust_audio_cue",
            "audit_ai_agent_binary",
            "DualPathVerifier",
            "MaskedQueryCorrectionExample",
            "VisorLogDisagreementLedger",
            "seal_embeddings_with_gemseal",
            "unseal_embeddings_with_gemseal",
            "audit_embedding_file_privacy",
            "check_mcp_path_with_kevlar",
            "sanitize_vector_filter_with_kevlar",
            "AgentEmailGuardrail",
            "evaluate_robotics_motion_gate",
            "wave3_vault_inventory",
        ),
    ),
)

_LAZY_EXPORTS: dict[str, str] = {
    symbol: module_name
    for module_name, symbols in _LAZY_EXPORT_GROUPS
    for symbol in symbols
}


def __getattr__(name: str):
    """Lazily resolve optional subsystem symbols without import-time overhead."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(f".{module_name}", __name__)
    return getattr(module, name)


__all__ = [
    "ActuationPolicy",
    "AgentGateway",
    "WebExplorer",
    "accessible_volume",
    "effective_perception",
    "kl_divergence_bits",
    "BoundedAutonomyLoop",
    "Candidate",
    "InMemoryEnvironment",
    "SandboxPolicy",
    "run_reflection",
    "verify_reflection",
    "EventCausalEngine",
]

__version__ = "0.8.1"
