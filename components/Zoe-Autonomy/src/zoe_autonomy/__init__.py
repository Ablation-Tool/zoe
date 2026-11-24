"""Operational full self-governing autonomy through Zoe and Operational Metacognition."""

from .actuation import ActuationPolicy
from .agents import AgentGateway
from .explore import WebExplorer
from .metrics import accessible_volume, effective_perception, kl_divergence_bits
from .loop import BoundedAutonomyLoop, Candidate, InMemoryEnvironment, SandboxPolicy
from .self_reflection import run_reflection, verify_reflection


def __getattr__(name):
    if name == "EventCausalEngine":
        from .event_autonomy import EventCausalEngine
        return EventCausalEngine
    if name in {
        "ZoeEpistemicGate",
        "lint_zoe_capability_policy",
        "scan_sealed_corpus_schema",
        "screen_findings_with_winnow",
        "audit_repo_stewardship",
    }:
        from . import epistemic_firewall
        return getattr(epistemic_firewall, name)
    if name in {
        "farg_coherence_to_temperature",
        "run_farg_metacognitive_analogy",
        "ZoeColorCascadeGuard",
        "ZoeCalibrationTracker",
    }:
        from . import cognitive_upgrades
        return getattr(cognitive_upgrades, name)
    if name in {
        "screen_dorothy_sequence_homology",
        "ApprovedDomainAllowlist",
        "build_warrant_grounded_plan",
    }:
        from . import dorothy_research_upgrades
        return getattr(dorothy_research_upgrades, name)
    if name in {
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
    }:
        from . import wave2_security_forensics
        return getattr(wave2_security_forensics, name)
    if name in {
        "build_nina_voice_filtergraph",
        "list_foxhound_onnx_models",
        "find_zoe_capability",
        "refine_prompt_with_architect",
        "select_dcwf_agent_roles",
        "evaluate_atlas_stack_risk",
        "wave2_research_and_platform_catalog",
    }:
        from . import wave2_platform_upgrades
        return getattr(wave2_platform_upgrades, name)
    if name == "TrustEngine":
        from .trust_gradient import TrustEngine
        return TrustEngine
    if name in {
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
    }:
        from . import wave3_vault_upgrades
        return getattr(wave3_vault_upgrades, name)
    raise AttributeError(name)

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
