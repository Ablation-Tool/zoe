# Zoe Portfolio Upgrades: Waves 1 & 2 (42 Integrated Self-Authored Repositories)

Forty-two self-authored NuClide / Nicholas Kloster repositories have been integrated directly into Zoe (`config/portfolio-upgrades.lock.json`: 11 Wave 1 + 31 Wave 2 non-biology components) with zero nested `.git` submodules and zero regressions to existing Zoe verification suites.

All integrations preserve Zoe's constitutional invariants (`docs/CONSTITUTION.md`):
- `measurement != evidence != belief update != action`
- `sentience_claimed = False`, `l5_agi_qualified = False`, `zoe_clone_claimed = False`
- `cure_claim = False`, `clinical_action_authorized = False` (Milestone 1 preclinical boundary)

---

## Wave 1 (11 Components)

### Track 1: Epistemic Firewall and Control Scales with Capability (`AGI-ROADMAP.md` §9)

| Component | Path | Zoe Integration |
|---|---|---|
| `injection-gate` | `components/injection-gate/` | `ZoeEpistemicGate` in `zoe_autonomy.epistemic_firewall`, wired synchronously into `ActuationPolicy.execute(...)` (`actuation.py`). Never calls a model; blocks tainted/untrusted shell exec, credential reads, and untrusted-sink egress before side effects occur. |
| `capo` | `components/capo/` | `lint_zoe_capability_policy()` validates `config/zoe-capability-policy.json` (`label-lint`, `spof-budget`, `adversary-twin` BFS across Zoe's 9 trust planes). Proves `0` errors and `0` catastrophic untrusted-to-privileged pivots. |
| `glance` | `components/glance/` | `scan_sealed_corpus_schema()` runs schema-only sensitivity triage without exposing raw values (`CONSTITUTION.md` Article VI.2). |
| `winnow` | `components/winnow/` | `screen_findings_with_winnow()` filters scanner/research candidates against codified NuClide false-positive Insights (`PASS` / `REFUTED` / `DOWNGRADE`). |
| `github-tos-audit` | `components/github-tos-audit/` | `audit_repo_stewardship()` provides pre-push ToS/AUP source stewardship auditing across all 7 verbatim `TOS_CLAUSES` (`CONSTITUTION.md` Article VI.3). |

### Track 2: Cognition, Analogical Transfer, Color-CUSUM, and Calibration (`AGI-ROADMAP.md` §3, §4, §6)

| Component | Path | Zoe Integration |
|---|---|---|
| `farg-analogy-cognition` | `components/farg-analogy-cognition/` | `run_farg_metacognitive_analogy()` and `farg_coherence_to_temperature()` in `zoe_autonomy.cognitive_upgrades` pair Hofstadter/FARG `Slipnet` opposite-gated reframing and endogenous temperature $T = T_{\text{floor}} + (T_{\text{max}} - T_{\text{floor}})(1-c)^\gamma$ with Operational Metacognition $A_\tau(p)$. |
| `nuclide-color-framework-v2` | `components/nuclide-color-framework-v2/` | `ZoeColorCascadeGuard` brings centered Lyapunov energy $E(x)$, fidelity coherence $C_{\text{fid}}$, perceptually uniform OKLab calibration (`#2DB2BF` Home / `#D9581E` Cascade), 3D SVD metamerism verification ($\Delta E_{\text{OK}} \approx 0$), and directional Page CUSUM compliance-collapse detection; wired directly into `DualPeerSession.ask(...)` (`zoe_clara.py`). |
| `pcse` | `components/pcse/` | `ZoeCalibrationTracker` produces portable 8-dim calibration vectors, 7-dim unit L2 embeddings, cosine similarity, and deterministic SHA-256 drift fingerprints across sessions. |

### Track 3: Grounded Research & Citation Verification

| Component | Path | Zoe Integration |
|---|---|---|
| `bio-bert` | `components/bio-bert/` | `screen_dorothy_sequence_homology()` in `zoe_autonomy.dorothy_research_upgrades` adds offline conjunctive k-gram Jaccard (+ optional ESM2/DNABERT-2) homology screening with explicit `cure_claim = False` and `clinical_action_authorized = False` stamps. |
| `domain-research` | `components/domain-research/` | `ApprovedDomainAllowlist` parses the vetted ~490-domain allowlist (`references/trustworthy-domains.md`) with strict parent-domain boundary matching, wired optionally into `ResearchConnector(..., enforce_allowlist=True)` (`capabilities.py`). |
| `warrant` | `components/warrant/` | `build_warrant_grounded_plan()` builds and verifies Librarian book-cited `Plan`/`PlanNode`/`Principle` structures, and `WarrantAdapter.wrap_agent(...)` (`components/agent-logging-system/agent_logging_system/adapters/warrant_adapter.py`) intercepts live reasoning, generation, and citation checks. |

---

## Wave 2 (31 Strictly Non-Biology Components + New Ablation RXVM Crypto Analyzer)

### Track 4: Custom-VM Crypto Analysis, Forensics, Audio/MCP Defense & Sealed Storage (`zoe_autonomy.wave2_security_forensics`)

| Component | Path | Zoe Integration |
|---|---|---|
| `RXVM` + `rxvm_crypto_analyzer` | `components/RXVM/`, `components/ablation/ablation/analyzers/rxvm_crypto_analyzer.py` | New `ablation` analyzer enriched with the deeper Google Drive RXVM artifacts (`rxvm_crypto_layer_analysis.pdf`, `payload_0_crypto_annotated.txt`, resolved April 19 `ANALYSIS.md` & `a10_model.py`, `rxc_decrypt.py`, `rxvm_disasm.py`): detects hybrid xxHash32 `PRIME32_1` + Murmur3 `fmix32` (`0xDEADBEEF`), predictable `SHA-256(sid)`/`SHA-256(rid)` AES-CBC derivation, RC4 fallbacks (`rx.ep4`), 4-byte LE timestamp prefixes, `DEBUG`-gated `__erk`/`__eri`/`__er` leaks, full `rxc=` cookie/metric/`float16` decoding, and extracted quantized-MLP BatchNorm-beta saturation auditing (`analyze_quantization_saturation`); plus `foxhound.py` offline ONNX model registry. |
| `beam_obfuscation_analyzer` + `research-drafts` | `components/ablation/ablation/analyzers/beam_obfuscation_analyzer.py`, `docs/research-drafts/` | Strict EA IFF 85 `.beam` container obfuscation analyzer (size mismatch, chunk boundaries, rogue IDs, atom Shannon entropy & zero-width chars, atom starvation, stripped `Line`, poisoned zlib `LitT`/`Dbgi`/`Abst`), plus 6 preserved non-biology Google Drive architecture & security drafts (`ctm-companion-paper.md`, `verification-exploitation-asymmetry.md`, `binary-analysis-and-space-reduction.md`, `beam-iff-obfuscation-detection.md`, `angr-scoped-symbolic-execution.md`, `project-overmatch-vectorized-disassembler.md`). |
| `dBA` | `components/dBA/` | `screen_audio_metadata_with_dba()` runs ASR/Whisper audio-container metadata firewalling (`allow`/`quarantine`/`reject`, raw tag values never leak). |
| `metrix` | `components/metrix/` | `inventory_re_corpus_with_metrix()` provides evidence-first non-executing RE corpus inventory (TOCTOU-verified SHA-256, magic-byte format/arch detection, symlink-safe). |
| `gemseal` | `components/gemseal/` | `seal_evidence_with_gemseal()` / `unseal_evidence_with_gemseal()` wrap HKDF-SHA256 + ChaCha20-Poly1305 record-chained authenticated containers with tamper rejection. |
| `mcp-security` | `components/mcp-security/` | `scan_mcp_server_with_mcp_security()` + `screen_mcp_tool_with_guard()` + `kevlar.policy.verify_tool_manifest_hash()` add `.mcp.json` injection scanning, PAL path-confinement checks, and SHA-256 tool rug-pull detection. |
| `cortex-framework` | `components/cortex-framework/` | `analyze_authorization_context_with_cortex()` validates authorization-context boundaries (*what code does vs. what it assumes the right to do*). |
| `nuclide-asset-schema` | `components/nuclide-asset-schema/` | `validate_asset_record_with_schema()` validates asset/service/finding records against JSON Schema 2020-12 (`visor-asset.schema.json`). |
| `spectral` | `components/spectral/` | Rust signature-based AI/LLM forensic artifact scanner. |
| `VisorCorpus`, `VisorAgent`, `VisorCAS`, `VisorScuba`, `VisorLog`, `safety-stream` | `components/Visor*/`, `components/safety-stream/` | Go adversarial prompt corpus & mutators, real tool-use injection HIT/MISS benchmark, blake3 false-positive CAS ledger, OPA/Rego 17-control compliance scorer, append-only SQLite findings ledger, and live SSE safety-reasoning dashboard. |
| `nuclide-method`, `white-bronco` | `components/nuclide-method/`, `components/white-bronco/` | Verification-first assessment methodology and Coordinated Vulnerability Disclosure (CVD) LaTeX templates & PSIRT guide. |

### Track 5: Voice Studio, Capability Routing, Prompting, Role Taxonomy & Alignment Theory (`zoe_autonomy.wave2_platform_upgrades`)

| Component | Path | Zoe Integration |
|---|---|---|
| `nina` *(Lume 1.0)* | `components/nina/` | `build_nina_voice_filtergraph()` brings Lume 1.0 Zoe Voice Studio 5-band EQ, audio FX, and offline neural TTS backing `lume_cli.py`. |
| `fieldwork` | `components/fieldwork/` | `find_zoe_capability()` provides zero-dependency semantic problem-to-component routing across all 54 integrated Zoe components. |
| `prompt-architect` | `components/prompt-architect/` | `refine_prompt_with_architect()` analyzes and refines raw prompts into structured role/goal/contract/quality-check specifications (with optional BM25 book grounding). |
| `wardrobe`, `operator-doctrine` | `components/wardrobe/`, `components/operator-doctrine/` | `select_dcwf_agent_roles()` loads DoD DCWF work-role atoms for structured multi-agent specialization. |
| `nuclide-atlas` | `components/nuclide-atlas/` | `evaluate_atlas_stack_risk()` runs deterministic risk badges (`exposed.no_auth`, `unencrypted.public_http`, `unbounded.max_tokens`, `no_rerank.high_k`, `open_prompt.no_filters`) over LLM stack topologies. |
| `AvailGate`, `chainsaw-cli` | `components/AvailGate/`, `components/chainsaw-cli/` | Local persistent coding-agent research session CLI and corpus-agnostic collective-brain router. |
| `ALIGNMENT-UNDER-PRESSURE`, `constraint-is-freedom`, `rhythm-lab` | `components/ALIGNMENT-UNDER-PRESSURE/`, `components/constraint-is-freedom/`, `components/rhythm-lab/` | Output-distribution constraint-strength & thresholded output-space volume theory plus real MIDI accessible-volume surprise calibration. |
| `Claude-Savant`, `Claude-4.7`, `rag-pipeline-demo`, `ti-bd-gh` | `components/Claude-Savant/`, `components/Claude-4.7/`, `components/rag-pipeline-demo/`, `components/ti-bd-gh/` | Tiered external memory scaling, sentinel-driven structured extraction patterns, interactive 4-stage RAG debugger, and zero-JS interactive animated SVG block diagrams. |

---

## Verification

```bash
# Wave 1
python3 scripts/verify_portfolio_upgrades.py
PYTHONPATH=components/Zoe-Autonomy/src:components/agent-logging-system python3 -m pytest -q components/Zoe-Autonomy/tests/test_portfolio_upgrades.py

# Wave 2
python3 scripts/verify_wave2_upgrades.py
PYTHONPATH=components/Zoe-Autonomy/src:components/ablation:components/kevlar python3 -m pytest -q components/Zoe-Autonomy/tests/test_wave2_upgrades.py
```

Evidence artifacts:
- `evidence/portfolio-upgrades/portfolio-upgrades-report.json`
- `evidence/portfolio-upgrades/wave2-upgrades-report.json`

## Wave 3 Vault Upgrades (5 Strictly Non-Biology Inventions)

Integrated directly from unpublished Google Drive vault research without modifying `config/components.lock.json`:

1. **5-Dim Continuous `TrustEngine` (`zoe_autonomy/trust_gradient.py` → `DualPeerSession` + `components/nina/audio_fx.py`)**: Scores `Source → Layer → Pattern → Prediction → Output` trust in `[0.0, 1.0]`, strictly enforces `output_trust <= source_trust` (clamping coercion turns to `<= 0.15`), and maps epistemic uncertainty directly into Lume 1.0 `ffmpeg`/`mpv` audio clarity (wide dry clarity vs. narrow reverb haze).
2. **4 Unpublished AI-Agent Binary Auditors (`components/ablation/ablation/analyzers/`)**: `AgentAuthorityAudit`, `AgentObservabilityAudit`, `AgentToolSurfaceEnumerator`, and `AIControlIndicators` (plus unified `audit_ai_agent_binary()` bridge) enabling Zoe to statically audit other compiled AI agent binaries for confused-deputy authority surplus, missing HITL/logging sinks, hidden `.rodata` JSON tool schemas, and AI-generated code markers.
3. **Dual-Path Verification & Masked-Diff Flywheel (`DualPathVerifier` + `VisorLogDisagreementLedger`)**: Runs a trusted deterministic query path in parallel with an LLM query path, holds LLM disagreements (`measurement != belief update`), and writes BERT-style `[MASK]` slot correction flashcards natively into `VisorLog`'s SQLite `events` schema.
4. **Eq. 2 Slow-Drift Cascade + `vec2text` Vector-Privacy + MCP Subdir/Filter Guards**: Adds `observe_compliance_step()` to `ZoeColorCascadeGuard` (catching depth-1 `+1 token/step` cascades that evade breadth spike alarms), `seal_embedding_records()` / `audit_embedding_storage_policy()` in `components/gemseal/gemseal.py`, and `check_mcp_path_confinement()` + `sanitize_vector_filter_value()` in `components/kevlar/policy.py`.
5. **Email Allowlist Guardrail + ROS Confirm-Before-Move Gate + Lock-Free Bloom/CAS Dedup**: Adds SQLite `AgentEmailGuardrail` and robotics deadman/confirm-before-move enforcement onto `ActuationPolicy`, plus lock-free `BloomCASDedup` (`sync/atomic`, zero mutexes) in `components/VisorCAS/cas/fastdedup.go`.

- **Wave 3 Verification:** `python3 scripts/verify_wave3_upgrades.py` → `evidence/portfolio-upgrades/wave3-upgrades-report.json`
- **Wave 3 Tests:** `python3 -m pytest components/Zoe-Autonomy/tests/test_wave3_upgrades.py` & `go test -race ./...` in `components/VisorCAS`

### Wave 3 Digital Research GSX / GEM / Atari TOS / ViewMAX Rebuild (`seasip.info/Gem` + `toastytech.com/guis`)

All 5 Wave 3 Vault upgrades are rebuilt as native Digital Research GSX/GEM/TOS/ViewMAX instruments combining John Elliott's GEM Information Archive (`https://www.seasip.info/Gem/index.html`) with Nathan Lineback's ToastyTech GUI Gallery historical lineage (`http://toastytech.com/guis/indexgem.html`):

- **Spec-Exact GEM & GSX Codecs (`guiai-lab/guiai/gem/seasip_gem.py` + `vdi.py`):** Exact 16-color GEM/3 & GEM/5 palettes (`#FFFFFF`..`#AD00AD`, `#00756B` teal, `#FFC300` gold), 16-byte (`<8h`) AES messages, PC GEM 7-window `GemAesDesk` manager, AES Fn 52 `form_alert`, dual-endian binary `.RSC` resource compiler/parser (**Intel x86 PC GEM `<`** AND **Motorola 68000 Atari TOS `>`**, cross-verified with `zoe_freegem_archive.inspect_rsc_bytes`), big-endian 4-plane RLE `.IMG`/`XIMG` bitmap codec, `.GEM` VDI metafile spec validator, and **1982 Digital Research GSX-86 NDC `0..32767` (bottom-left origin)** binary call stream codec (`.gsx`).
- **9 Verified GEM Instruments (`guiai-lab/guiai/gem/wave3_gem_instruments.py`):** Wired via `EXTENDED_LAYERS` in `operating_environment.py` (preserving core `17` components and `36` atlas layers):
  - `wave3` (`wave3-desk`): Unified 5-window OpenGEM / ViewMAX 3D Security Desktop
  - `wave3-trust` (`trust-acc`): `TRUST.ACC` (5D Continuous `TrustEngine` + `nina` Lume clarity)
  - `wave3-auditors` (`audit-app`): `AUDIT.APP` (4 Unpublished `ablation` AI-Agent Binary Auditors)
  - `wave3-dualpath` (`verify-app`): `VERIFY.APP` (Dual-Path Query Validation + `VisorLog` `[MASK]` Flywheel)
  - `wave3-guards` (`guard-acc`): `GUARD.ACC` (Eq. 2 Slow-Drift + `gemseal` `vec2text` + `kevlar` MCP/Filter)
  - `wave3-actuation` (`actuate-app`): `ACTUATE.APP` (Email Allowlist + ROS Deadman + `VisorCAS` Bloom/CAS)
  - `wave3-gsx` (`gsx-graph`): **1982 Digital Research GSX-86** DR-Graph vector telemetry plotter (`NDC 0..32767`)
  - `wave3-tos` (`tos-desk`): **1985 Atari TOS 1.0** "Little Green Desktop" with Filing-Cabinet Drawers, Trash Can, overlapping windows, and Motorola 68k big-endian `.RSC`
  - `wave3-gem2` (`gem2-tiled`): **1986–88 GEM 2.0 / 3.11** post-Apple-lawsuit layout (2 permanently open fixed-size tiled panes, zero desktop icons, `Desk` menu moved to far right)
- **Native Exports & Time-Machine Desktop:** `GemOperatingEnvironment.export()` exports verified `.gem`, dual-endian `.rsc` (x86 LE + 68k BE for `wave3-tos`), `.img`, `.gsx`, `.svg`, `.json`, and the 5-era interactive HTML desktop (`CALC.ACC`, `FORM_ALERT.ACC`, `Desktop Info`, Quarantine Trash, hover-vs-click menus, and dynamic `Desk`-left/right switching) with strict no-overwrite enforcement (`python3 scripts/verify_wave3_seasip_gem.py` → `evidence/gem-os/wave3-seasip-gem-report.json`, tests in `guiai-lab/stress/test_wave3_seasip_gem.py`).
