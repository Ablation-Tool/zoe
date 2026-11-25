# Zoe × Antigravity Shared-Reasoning Architectures (1–9)

## Overview

The `zoe_autonomy.shared_reasoning` package (`components/Zoe-Autonomy/src/zoe_autonomy/shared_reasoning/`) implements nine composed reasoning architectures uniting Zoe's deterministic verification, memory, and Kloster metacognition (`A_τ(p)`, Theorem 13, Theorem 15) with the `google.antigravity` Python SDK (`Agent`, `Conversation`, `ChatResponse`, `hooks`, `policy`, `LocalOpenAIAgentConfig`, `ThinkingLevel`).

All modules execute deterministically offline by default (0 cloud tokens, CI-safe) while supporting live local loopback (`127.0.0.1:8080` `LocalOpenAIAgentConfig`) and optional Gemini transport under `docs/CONSTITUTION.md`.

---

## Dual-Transport SDK Bridge (`sdk_bridge.py`)

`ZoeAntigravityBridge` provides a single transport abstraction over `google.antigravity`:

- **`"offline"`**: Uses `DualTransportAgentConfig` → `DualTransportStrategy` → `OfflineAntigravityConnection(Connection)` backed by `ZoeOfflineVoiceAdapter` (`ZoeElizaEngine` Gear 1 + `stem_layering.route_stem`). Streams genuine `types.Step` events (`THINKING`, `TOOL_CALL`, `TEXT_RESPONSE`, `FINISH`) and enforces `HookRunner`, `ToolRunner`, `policy`, and `BudgetConfig` in-process with zero external processes or network calls.
- **`"local_qwen"`**: Probes `127.0.0.1:8080` via `stem_layering.probe_local_qwen`; when reachable, builds `LocalOpenAIAgentConfig(...).lightweight()` targeting loopback Qwen2.5-3B-Instruct. Falls back cleanly to `"offline"` when unreachable.
- **`"gemini"`**: Builds `LocalAgentConfig` with `ThinkingLevel` (`MINIMAL`..`EXTRA_HIGH`) only when API credentials are configured and `privacy_sensitive=False`; otherwise falls back cleanly to `"offline"`.
- **`"auto"`**: Prefers loopback `local_qwen` (or `gemini` when permitted and routed to cloud tiers) and falls back deterministically to `"offline"` when endpoints are unavailable.

---

## Architectures 1–8 + Team-Invented Architecture #9

### Architecture 1: AlphaEvolve / FunSearch Loop (`alpha_evolve.py`)
- **Classes**: `AlphaEvolveLoop`, `AntigravityProgramMutator`, `ZoeDeterministicVerifier`, `EvolutionaryArchive`, `CandidateProgram`, `TestCase`, `VerificationReport`, `AlphaEvolveResult`.
- **Mechanism**: Evolves pure Python functions across a multi-island MAP-Elites archive (`EvolutionaryArchive`) using Boltzmann/tournament parent selection, cross-island exemplars, and `ZoeAntigravityBridge` mutation with deterministic AST-mutation fallback. Every candidate is strictly gated and compiled through `GuardedFunctionASTSandbox` (`l4_multi_module.py`), recording both winning evidence and rejected/unsafe AST probes onto `EpistemicBlackboard`.

### Architecture 2: Live Process Supervision (`process_supervision.py`)
- **Classes**: `LiveProcessSupervisor`, `SupervisionEvent`, `MutualAuditFinding`, `SupervisionPolicyRule`, `ZoeTransitionProposal`.
- **Mechanism**: Implements **bidirectional mutual auditing** natively on `google.antigravity.hooks.hooks` and `policy`:
  1. **Zoe → Antigravity**: Inspects streaming `types.Thought` deltas, denies non-loopback URLs (`CONSTITUTION.md` Art. VI.5) and destructive/external tool calls (`Art. III.4/X`), and sanitizes secrets/timeouts/bounds via `PreToolCallDecideHook`.
  2. **Antigravity → Zoe**: Audits proposed belief transitions (`audit_zoe_transition`, `supervised_update_belief`) for measurement scope/method/limitations (`Art. III.1`), approved `EvidenceRecord` IDs (`Art. III.2`), and sampled-only expectation shortcuts (`Art. III.3`), triggering `StopHook` continuations (`StopDecision.CONTINUE`) when remediation is required.

### Architecture 3: MCTS / Tree-of-Thought with Kloster Stopping (`mcts_kloster.py`)
- **Classes**: `KlosterMCTSSearch`, `MCTSSearchResult`, `ThoughtNode`, `ThoughtCandidate`, `MCTSBranchTrajectory`, `ForkCandidate`.
- **Mechanism**: Runs UCT Tree-of-Thought search with async parallel sibling evaluation (`asyncio.gather`), exact multi-horizon accessible volume `A_τ^(h)` (`exact_multihorizon_accessible_volume` & `tight_strict_upper_bound(tau) = ceil(1/tau) - 1`), prefix pruning for `P(u) <= tau`, Theorem 13 anytime-valid sequential stopping (`KlosterSequentialStoppingController` emitting `DECIDE_SIGNAL`, `GATHER_MORE`, or `ABSTAIN_INSUFFICIENT_EVIDENCE`), and `ForkCandidate` emission for Arch 8.

### Architecture 4: Theorem 15 Anti-Echo-Chamber Four-Peer Quorum (`quorum.py`)
- **Classes / Functions**: `FourPeerQuorumEngine`, `PeerConfidenceVector`, `FourPeerQuorumResult`, `FourPeerRouteResult`, `evaluate_four_peer_quorum`, `route_with_four_peer_quorum`, `quorum_from_dual_peer_balance`.
- **Mechanism**: Collects simplex confidence vectors from four heterogeneous peers (`zoe`, `clara`, `antigravity`, `user`), each carrying `source_kind`, `provenance_id`, and `independence_tag`. Integrates with `stem_layering.arbitrate_teamwork_quorum` and `stem_layering.route_stem` to compute Theorem 15 Kloster-Jensen disagreement `D_K`, coherence `C_K`, and exact Brier wisdom-of-crowds contraction, detecting cloned echo chambers (`ECHO_CHAMBER_WARNING`), missing provenance, monopoly weights, and rogue outliers (`ABSTAIN`).

### Architecture 5: System-2 → System-1 Distillation (`distillation.py`)
- **Classes**: `System2To1Distiller`, `System2Trace`, `DistilledArtifact`, `DistilledRuleRegistry`, `DistilledInlineSkill`.
- **Mechanism**: Distills high-uncertainty (`initial_uncertainty_a_tau >= min_uncertainty_a_tau`), independently verified System-2 solutions into Zoe's zero-cloud-token System-1 stores:
  - Procedural skills via `ZoeUnifiedMemory.register_skill` (AST-sandboxed via `GuardedFunctionASTSandbox`),
  - Semantic facts via `ZoeUnifiedMemory.record_fact(..., evidence_approved=True)`,
  - Conversational/routing rules via `DistilledRuleRegistry` (`zoe_eliza.ElizaRule`),
  - `google.antigravity.InlineSkill` descriptors (`DistilledInlineSkill`), with pre/post-commit regression checks and atomic `rollback(token)`.

### Architecture 6: Shared Epistemic Blackboard (`blackboard.py`)
- **Classes**: `EpistemicBlackboard`, `MeasurementRecord`, `EvidenceRecord`, `BeliefUpdateRecord`, `ActionProposalRecord`, `FirewallViolationError`, `TamperDetectedError`.
- **Mechanism**: Enforces `CONSTITUTION.md` Article III's strict four-lane separation:
  ```text
  measurement != evidence != belief update != action
  ```
  Illegal shortcuts (such as `measurement -> update_belief`, `evidence -> propose_action`, or promoting sampled-only outcomes via expectation-only rationale) raise `FirewallViolationError`. Negative results are preserved openly (`negative_result=True`). Every mutation is chained with SHA-256 (`tamper_evidence_only=True, authentication_proof=False`).

### Architecture 7: Reality-Anchored Sandbox Labs (`sandbox_labs.py`)
- **Classes / Functions**: `RealitySandboxLab`, `SandboxLabVerdict`, `post_verdict_to_blackboard`, `safe_parse_sympy_expr`.
- **Mechanism**: Provides deterministic ground-truth checks with concrete counterexamples and honest capability reporting (never simulating absent binaries):
  - **SymPy Lab**: symbolic identities, equations, derivatives/integrals (`sympy`).
  - **Z3 SMT Lab**: satisfiability & universal invariant proofs via UNSAT of negated invariant (`z3`).
  - **AST / Repo Lab**: `GuardedFunctionASTSandbox` + bounded read-only `git`/`pytest`/`mypy`/`ruff` subprocess checks.
  - **Dataset Invariant Lab**: finite/range/simplex/conservation/monotonicity/uniqueness checks.
  - **Loopback HTTP & Capability Probes**: `127.0.0.1`/`localhost`/`::1` HTTP checks and honest `lean`/`playwright` availability probes.

### Architecture 8: High-Leverage Human Steering (`human_steering.py`)
- **Classes**: `HumanSteeringDetector`, `VerifiedPathOption`, `ForkPointReport`.
- **Mechanism**: Filters out unverified/failed/sampled-only branches and raises `ASK_USER` (`AskQuestionInteractionSpec` + `OnInteractionHook`) **only** when `>= 2` independently verified paths diverge meaningfully and at least one trigger fires (supercritical multi-horizon `A_τ^(h)` branching, high Theorem 15 `D_K`, `OptionShift` narrowing, or an irreversible/high-impact boundary). Always preserves options to select, reject all, stop, or request a reversible alternative with `external_actions=0`.

### Architecture 9 (Team-Invented): Counterpoint Chairs (`counterpoint_chairs.py`)
- **Classes / Functions**: `CounterpointChairsEngine`, `ProblemChair`, `ChairVoice`, `CounterpointRotationSchedule`, `FrozenChairPacket`, `ColdAuditVerdict`, `SwapLedgerEntry`, `CounterpointRelayResult`, `default_counterpoint_voices`.
- **Mechanism**: Directly mirrors the Musical Math Chairs theme to prevent single-agent fixation, confirmation bias, and sunk-cost drift:
  1. Heterogeneous voices (`antigravity`, `zoe`, `clara`, `sandbox_lab`) rotate across multiple `ProblemChair`s on a cyclic non-repeating counterpoint schedule (`beat_quantum_s`, `step_budget`, or `A_τ(p)` marginal-gain drop).
  2. Each handoff freezes the chair's 4-lane `EpistemicBlackboard` state into a SHA-256 `FrozenChairPacket`.
  3. The incoming voice performs a mandatory **Cold Audit** (`acold_audit_packet`), quarantining unverified claims, flagging sunk-cost stagnation, and running a Theorem 15 cross-voice discrepancy check.
  4. `sonify_cadence_wav` renders a 16-bit PCM WAV cadence encoding rotation tension (`D_K`, firewall flags) and tonic-fifth resolution.

---

## Unified Composer (`orchestrator.py`)

`SharedReasoningOrchestrator` (`SharedReasoningTaskSpec` → `SharedReasoningRunReport`) composes all 9 architectures in a single provenance-chained execution pipeline:

1. Resolves transport via `ZoeAntigravityBridge` (`offline` / `local_qwen` / `gemini` / `auto`) and runs a supervised `Agent` turn under `LiveProcessSupervisor` (Arch 2).
2. Evolves candidate solutions with `AlphaEvolveLoop` (Arch 1).
3. Verifies mathematical, SMT, AST, and optional dataset invariants with `RealitySandboxLab` (Arch 7).
4. Explores strategy branches with `KlosterMCTSSearch` (Arch 3).
5. Cross-audits problem seats via `CounterpointChairsEngine` (Arch 9).
6. Arbitrates 4-peer consensus (`zoe`, `clara`, `antigravity`, `user`) and `stem_layering.py` tier routing via `FourPeerQuorumEngine` + `route_with_four_peer_quorum` (Arch 4).
7. Detects high-leverage verified forks via `HumanSteeringDetector` (Arch 8).
8. Distills verified solutions into `ZoeUnifiedMemory` System-1 skills, facts, and rules via `System2To1Distiller` (Arch 5).
9. Commits final mutual-audited `BeliefUpdateRecord` and `REVIEW_REQUIRED` `ActionProposalRecord` (`external_actions=0`) onto `EpistemicBlackboard` (Arch 6) and verifies hash-chain integrity.

---

## Digital Research GEM Integration (`seasip.info/Gem/index.html`)

The `gem_aes_vdi.py` bridge (`zoe_autonomy.shared_reasoning.gem_aes_vdi`, contract `zoe-gem-aes-vdi/v1`) connects Zoe's original pure-stdlib Digital Research GEM / FreeGEM / ViewMAX stack (`guiai/gem/seasip_gem.py`, `vdi.py`, `model.py`, `geometry.py`, `runner.py`, `zoe_atari_gem_rsc.py`, `zoe_gem_themes.py`) directly into Architectures 1–9: **zero third-party GPL/open-source code copied**:

- **`GemEventMultiQueue` & `GemWindowManager`**: Deterministic 16-byte (`<8h`) AES message queue (`evnt_multi` with `MU_MESAG | MU_TIMER | MU_KEYBD | MU_BUTTON`), authentic PC GEM 7-application-window limit (`MAX_AES_APP_WINDOWS = 7`), GEM/2 non-overlapping tiling, and `MN_SELECTED` menu dispatch.
- **`GemFormAlert` & `build_form_alert`**: Spec-exact GEM AES Function 52 `[icon][lines][buttons]` strings paired with compiled `.RSC` object trees (`G_BOX` / `G_STRING` / `G_BUTTON`), automatically generated by **Arch 8** (`HumanSteeringDetector.build_gem_form_alert`) on active verified forks.
- **`GemVdiWorkstation`**: Compiles shared-reasoning desktop Spatial IR scenes (`10000x6000` canvas) to binary `.GEM` VDI metafiles and verifies geometric invariants & VDI round-trips across **CGA (`320x200`), VGA (`640x480`), and NDC (`32767x32767`)**.
- **Cross-Architecture Hooks**:
  - **Arch 2 (`process_supervision.py`)**: `audit_gem_payload` blocks out-of-range VDI coordinates (`[-32768, 32767]`), oversize metafiles (`> MAX_GEM_METAFILE_BYTES`), and GEMDOS/POSIX path traversal.
  - **Arch 1, 3, 4, 5, 6**: Visual-only Spatial IR exporters (`to_gem_spatial_ir`) and `System2To1Distiller.distill_gem_rule`.
  - **Arch 7 (`sandbox_labs.py`)**: `verify_gem_vdi_scene` and `verify_gem_rsc_bytes` with concrete counterexamples on invalid coordinates or corrupt binaries.
  - **Arch 9 (`counterpoint_chairs.py`)**: Emits `gem_desktop_trace` recording AES window cycling and `WM_TOPPED`/`MN_SELECTED` swap events.
  - **Composer (`orchestrator.py`)**: Stage 8.5 compiles & verifies `.GEM` + `.RSC` outputs and populates `gem_desktop_report` (writing artifacts only to an explicit `gem_vdi_output_dir`).
- **Constitutional Guarantees (`CONSTITUTION.md` Art. II.3, VII.5, VIII.1–2)**: All GEM scenes, dialogs, and metafiles carry `visual_evidence_only=True`, `external_actions=0`, and `sentience_claimed=False`, honoring **Gary Kildall & Digital Research GEM contributors** alongside **Nicholas Michael Kloster (March 6, 2026)**.

---

## Constitutional Guarantees (`docs/CONSTITUTION.md`)

- `measurement != evidence != belief update != action` (enforced by `EpistemicBlackboard` and `LiveProcessSupervisor`).
- `external_actions == 0`, `requires_human_review == True`, `autonomous_execution_allowed == False`.
- `sentience_claimed == False`, `l5_agi_qualified == False`, `zoe_clone_claimed == False`.
- Attribution preserved across all contracts: **Nicholas Michael Kloster, March 6, 2026**.
- Hash chains (`blackboard_sha256`, `entry_sha256`, `packet_sha256`) provide tamper evidence only (`tamper_evidence_only=True`, `authentication_proof=False`).

---

## Musical Math Chairs Session Evidence (`evidence/musical_math_chairs/`)

- `generate_music.py` + `musical_chairs_theme.wav` + `music_evidence.json`: Deterministic 44.1 kHz stereo PCM WAV generated and played via PipeWire (`2026-11-24T07:11:40Z`), strictly prior to Slot 1 (`2026-11-24T07:19:45Z`).
- `ROTATION_LOG.md`: Timestamped ~30-second rotation across items 1–9 covering all 9 architectures with zero consecutive item repeats on swap.

---

## Verification Commands

```bash
# Unit + Composer E2E tests (Arch 1-9 + Orchestrator)
/home/cowboy/security-tools/bin/python3 -m pytest components/Zoe-Autonomy/tests/test_sr_*.py -v

# Strict static type checking
/home/cowboy/security-tools/bin/python3 -m mypy --ignore-missing-imports components/Zoe-Autonomy/src/zoe_autonomy/shared_reasoning/

# Standalone end-to-end verifier (Arch 1-9, firewall, music WAV, rotation log)
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab /home/cowboy/security-tools/bin/python3 scripts/verify_shared_reasoning.py --json

# Existing Zoe constitutional & Kloster theorem invariants
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab /home/cowboy/security-tools/bin/python3 scripts/verify_zoe_clara.py
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab /home/cowboy/security-tools/bin/python3 scripts/verify_zoe_eliza.py
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab /home/cowboy/security-tools/bin/python3 scripts/verify_kloster_theorem13.py
PYTHONPATH=components/Zoe-Autonomy/src:guiai-lab /home/cowboy/security-tools/bin/python3 scripts/verify_theorem15_and_c28.py
```
