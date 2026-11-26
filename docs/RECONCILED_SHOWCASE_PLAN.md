# Zoe Ecosystem Reconciled Showcase Plan

**Status:** Canonical M1 Reconciled Blueprint (`zoe-monorepo`)  
**Workspace:** `<workspace-root>/zoe-monorepo`  
**Attribution:** Operational Metacognition $A_\tau(p)$ originated by **Nicholas Michael Kloster alone (March 6, 2026)**; honoring **Gary Kildall** and **Dorothy McEwen Kildall** (Digital Research GEM).

---

## 1. Constitutional Lock (`docs/CONSTITUTION.md` Articles I–X)

Every workflow, subsystem bridge, and showcase slice in this plan is bound by `docs/CONSTITUTION.md` (Articles I–X) and enforces the following runtime invariants:

1. **Epistemic Firewall (Article III):**
   ```text
   measurement ≠ evidence ≠ belief update ≠ action
   ```
   Measurements declare input, method, scope, and limitations (`Art. III.1`); only explicit evidence decisions update belief state (`Art. III.2`); sampled outcomes never become proof by matching expectation (`Art. III.3`); recommendations stay review-required (`Art. III.4`); hash chains provide tamper evidence only, not authentication (`Art. III.5`).
2. **Hard Runtime Safety Flags (Articles I, II, IV, V, X):**
   - `external_actions = 0` (autonomous external execution disabled; human steward retains final word).
   - `sentience_claimed = False`, `zoe_clone_claimed = False`, `l5_agi_qualified = False`.
   - `clinical_action_authorized = False`, `cure_claim = False` (Milestone 1 neurology/brain-cancer work is preclinical computational research only).
   - `flight_control_authorized = False`, `auto_flash_allowed = False`.
   - `loopback_only = True` for local model/UI probes (`127.0.0.1`, `localhost`, `::1`).
   - No-overwrite contracts on explicit exports/snapshots (`Art. IV.2, IV.5`); no automatic transcript notebook or covert metacognition monitor.
3. **Protected User State (Never Mutated by Builds/Tests):**
   - `~/.zoe/chat/session.json`
   - `~/.zoe/uma-bridge/uma_state.json`
   - `~/.zoe/os-build/zoe-gem-os.iso`
   - `~/.zoe/os-build/zoe-gem-os-lts.iso`
   - `~/.zoe/os-build/zoe-state.img`
   All automated tests and verification harnesses must use isolated temporary directories or environment overrides (`ZOE_CHAT_STATE`, `ZOE_UMA_DIR`, `ZOE_UMA_SHM`) and leave zero local servers or KVM VMs running after verification.
4. **Mount & Tooling Constraint:**
   Because the workspace filesystem may be mounted `fuseblk` (without POSIX `+x` execute bits), Python and CLI checks execute via `$ZOE_PYTHON` (or `python3`) and `zoe`.

---

## 2. Source Baseline & Discrepancy Reconciliation Matrix

This plan reconciles:
- **Live User Session & State:** `~/.zoe/chat/session.json` (`zoe-native-conversation/v2`, `id=7e14d61949d74b3e`, `turns=9`, `stopped=false`), `~/.zoe/chat/evolution/adopted_genome.json` (`zoe-self-stewardship-handover/v1`, `active_generation=3`, `active_name="deep_kappa_m8_blend"`, `active_heldout_mean=0.79762`, `consecutive_self_adopted_generations=3`, `stewardship_handover_active=true`, Gen 4 `overfit_entropy_spike` safely rolled back as `REJECTED_ROLLED_BACK`), and `~/.zoe/uma-bridge/uma_state.json` (`zoe-uma/v1`, `nick_allow=false`, `zoe_allow=false`, `gate="PRIVATE"`, `reason="privacy_by_default"`).
- **Three PowerPoint Chronicles:**
  1. `GEMZ_and_Zoe_Complete_Chronicle_Mar6_Nov24_2026.pptx` (13 slides: $A_\tau(p)$, 16 SymPy theorems, 18 papers, 55-component monorepo, L0–L4 + L5 Phases 1–6, C1–C28, Dorothy 3D Brain, Wave 1–3 upgrades, UEFI Zoe-GEM OS + Pixel 7 ARM64 + UMA, Sovereign Empire v0.9.0-beta.1 with 9 sister models, 9 Shared-Reasoning architectures, and Slide 13 open loose ends).
  2. `Zoe-Antigravity-Status-Report.pptx` (8 slides: Musical Math Chairs WAV/rotation, 9 Shared-Reasoning architectures, Digital Research GEM `gem_aes_vdi.py`, `chat.py` wiring, `scripts/zoe_shared_reasoning_mcp.py`, offline/CI test pass).
  3. `Zoe_Sisters_GEM_OS_Architecture.pptx` (10 slides: earlier 4-Sister GEM Desktop prototype `A: Clara`, `B: Dorothy`, `C: Helen`, `D: Eliza.ACC` citing `zoe_gem_desktop.py`, `zoe_sisters_gem_worlds.py`, `222/222` checks).
- **Governance & Architecture Docs:** `docs/AGI-ROADMAP.md`, `docs/CONSTITUTION.md`, `docs/CAPABILITY-ATLAS.md`, `docs/SHARED_REASONING_ARCHITECTURES.md`.

### Discrepancy Reconciliation Matrix

| Domain / Area | Session / PPTX / Doc Claim | Verified Monorepo Reality | Isolated Discrepancy / Hole | Resolution Milestone |
|---|---|---|---|---|
| **Zoe Sisters Roster & Council** | `Zoe_Sisters_GEM_OS_Architecture.pptx` describes 4 worlds (`Clara, Dorothy, Helen, Eliza.ACC`, `zoe_sisters_gem_worlds.py`, `zoe_gem_desktop.py`); Chronicle Slide 11 describes 9 multi-sensory sister models | `guiai-lab/guiai/gem/zoe_sisters.py` defines **9** `SisterModelSpec`s (`Zoe, Gemma, Tosi, Mono, Tetra, Eliza, Sage, Flora, Lumen`); `zoe_clara.py` & `desktop/zoe_desktop.py` exist separately; `zoe_sisters_gem_worlds.py` and `zoe_gem_desktop.py` are not in monorepo | 4-world PPTX filenames absent from monorepo; 9 sisters are only in `zoe_sisters.py`/`lume_cli.py`/`zoe_rome_fusion.py` and unwired from `Zoe-Autonomy` & `ablation`; `run_sister_council` returns static template text without explicit `(Mono, Zoe, Eliza)` 3-Sister Council lead execution | **M3** (F7, F8) |
| **UMA Bridge & Rome Pathing** | Chronicle Slide 10–11 & `~/.zoe/uma-bridge/uma_state.json`: `~/.zoe/uma-bridge` + `/dev/shm/zoe-uma-bar.shm` | Canonical `zoe_uma.py` lives at `guiai-lab/guiai/gem/zoe_gem_os/zoe_uma.py` (not `guiai/gem/zoe_uma.py`); `zoe_rome_fusion.py:733-734` uses `~/.zoe/uma` + `~/.zoe/uma.shm` and `:801` uses `~/.zoe/uma.shm`; `lume_cli.py` ignores `ZOE_UMA_DIR` | Path mismatch splits Browser Rome from CLI/QEMU; `read_state()` creates `uma.lock` on missing dir; `transfer_file` lacks size/symlink/traversal/dir-target guards & streams full file to RAM; SHM `slot` silently clamps instead of validating bounds; no `verify_audit_chain()` | **M1** (F2) |
| **Chat Store & Constitutional Firewall** | `~/.zoe/chat/session.json` (`turns=9`) & `adopted_genome.json` (Gen 3 `0.79762`); Status Report Slide 7 shows `chat.py` wired | `ChatStore.__init__` (`chat.py:256-264`) unconditionally calls `mkdir`/`chmod`, `ResearchMemory(...)`, and `self.save()`; `ZoeAppBrain` checks constitution via system prompt & keywords instead of `directive_violation()` / `ZoeEpistemicGate`; `ZoeChat` & `LumeCli` have split commands | Pure instantiation (e.g., `LumeCli(ZoeChat(REPO_ROOT), ...)`) mutates `~/.zoe/chat/session.json`; `ZoeAppBrain.respond("remember turn off metacognition")` writes to memory instead of refusing | **M1** (F3, F10) |
| **Cognitive Stem-Layering & MCP** | `SHARED_REASONING_ARCHITECTURES.md` & `stem_layering.py` enforce offline/privacy zero-cloud routing | `stem_layering.py` boosts `local_qwen` under `local_constraint=True` and only falls back when `local_qwen_available is False` (not `None`); `scripts/zoe_stem_mcp.py` only probes `:8080` & `:8765`, lacks `_assert_loopback_url` in `_get_loopback_json`, and drops `local_qwen_available` | `route_stem(..., offline_only=True)` selects unverified `local_qwen` when `:8080` is down & `probe_local=False`; MCP `eliza_studio_status` misses `:8774` & `:11434`; `zoe_stem_router.py` lacks `--status` & `--local-qwen-url` | **M1** (F4) |
| **Ablation GEM Framework** | `CAPABILITY-ATLAS.md` §3 documents `components/ablation/` (`ablation/` + `gem-lab/`) + `semantic_artifacts.py` | `components/Zoe-Autonomy/src/zoe_autonomy/semantic_artifacts.py:26` previously defaulted `_ablation_root()` to `<user-home>/_projects/ablation` | External path breaks fresh-clone/in-repo resolution; `ablation`/`gem-lab`/`operating_environment.py`/`gem_aes_vdi.py` seams need audit & fixes | **M2** (F5) |
| **Zoe-GEM OS KVM Pipeline** | Chronicle Slide 10: OVMF+KVM 2-boot proof, `/os verify`, Pixel 7 ARM64 | `guiai-lab/guiai/gem/zoe_gem_os/builder.py` (`_ZOE_PY_CLOSURE`) omits `zoe_sisters.py`; `lume_cli.py` `/os verify` has no static/dry-run inspection path independent of live QEMU | Missing sister module in ISO closure; no headless dry-run `/os verify` validation path for non-KVM verification | **M2** (F6) |
| **Scale & Capability Claims** | `CAPABILITY-ATLAS.md` documents 17 engines / 36 GEM layers (`EXTENDED_LAYERS` now 58); Chronicle lists 55 components; `AGI-ROADMAP.md` lists L0–L4 achieved + L5 Phases 1–6 | Core engines, 9 Shared-Reasoning architectures (`shared_reasoning/`), `ablation/`, `zoe_sisters.py`, and `zoe_gem_os/` are present on disk | Subsystems operate as vertical islands without a unified 9-Sister + `(Mono, Zoe, Eliza)` showcase slice or cross-system ON/OFF ablation suite | **M3–M4** (F7–F9) |

---

## 3. Prioritized Roadmap

| Milestone | Features | Priority Focus | Dependencies | Exit Criteria |
|---|---|---|---|---|
| **M1** | F1, F2, F3, F4, F10 | Reconciled Plan doc; UMA/Rome canonical path unification & airlock hardening; non-mutating `ChatStore` init + `ZoeAppBrain` `directive_violation()`/`ZoeEpistemicGate` + `ZoeChat`/`LumeCli` bridge; `stem_layering` offline fallback + 4-endpoint loopback probes | None | M1 pytest suites pass; `chat.py` Grade A (`MI >= 60, max_cc <= 20`) & 0 Grade C/D repo-wide; `verify_l5_phase4.py` 20/20; `verify-one-system.py --chat` pass; 5 protected SHA-256s unchanged |
| **M2** | F5, F6, F10 | Fix `semantic_artifacts._ablation_root()` to resolve `<zoe_root>/components/ablation`; audit & fix `ablation`/`gem-lab`/`operating_environment.py`/`gem_aes_vdi.py`; add `zoe_sisters` to `_ZOE_PY_CLOSURE` & static/dry-run `/os verify` + clean KVM/temp-dir teardown guards | None (parallel with M1) | Ablation & Zoe-GEM OS pipeline unit tests pass; zero stray VMs or temp mutations |
| **M3** | F7, F8, F10 | Wire all 9 sisters (`Zoe, Gemma, Tosi, Mono, Tetra, Eliza, Sage, Flora, Lumen`) + explicit **3-Sister Council (`Mono, Zoe, Eliza`)** into `Zoe-Autonomy`, `ablation`, `zoe_uma`, `stem_layering`, `gem_aes_vdi`, and `zoe_os_runtime`; deliver runnable E2E capability showcase slice + CLI/API hooks | M1, M2 | End-to-end 9-sister + 3-Sister Council showcase slice executes real AI tasks across subsystems with `CONSTITUTION.md` enforcement & passing tests |
| **M4** | F9, F10 | Execute ON/OFF ablation and reverse-engineering experiments with comparative metrics across (1) Ablation GEM, (2) Stem-Layering, (3) Zoe-GEM OS KVM, and (4) UMA Bridge/Chat; isolate & fix remaining holes; record evidence under `evidence/ecosystem-ablation/` | M3 | Reproducible ablation/RE metrics & regression tests pass |
| **E2E** | F11 | Requirement-driven opaque-box 4-tier E2E test suite (`tests/e2e_zoe_showcase/`) verifying all features via isolated temp environments | Parallel | Tier 1–4 E2E suite ready (`TEST_READY.md`) |
| **Final** | F12 | Full E2E Tier 1–4 + Tier 5 adversarial; 16-check `verify_l5_core.py`; `SHA256SUMS.orbit`; 9-stage L3 `verify_l3_research.py`; static `/os verify`; Agent-as-Judge rubric; Whole-Project Audit; post-run protected checksums & clean process check | M4, E2E | 100% gate pass, 0 running services/VMs, all 5 protected SHA-256s identical to baseline |

---

## 4. End-to-End 9-Sister + 3-Sister Council (`Mono, Zoe, Eliza`) Showcase Slice Architecture

The showcase slice connects four vertical layers without rewriting core modules from scratch:

```text
  [Layer 1: Constitutional Governance & Epistemic Firewall]
    docs/CONSTITUTION.md (Art. I-X) · directive_violation() · ZoeEpistemicGate
    EpistemicBlackboard (measurement != evidence != belief update != action)
                                     │
                                     ▼
  [Layer 2: Cognitive Routing, Memory & Airlock]
    stem_layering.route_stem() (A_tau(p) 5-tier + Theorem 15 quorum + 0-token offline fallback)
    ZoeAppBrain <-> ZoeChat <-> LumeCli · UmaBridge (~/.zoe/uma-bridge & /dev/shm/zoe-uma-bar.shm)
                                     │
                                     ▼
  [Layer 3: Domain Execution Engines]
    Ablation AIARE & GEM Lab (components/ablation/, semantic_artifacts.py)
    Shared Reasoning 1-9 & Digital Research GEM VDI/RSC (shared_reasoning/, gem_aes_vdi.py)
    Zoe-GEM OS Runtime & Framebuffer (zoe_gem_os/, builder.py, zoe_os_runtime.py)
                                     │
                                     ▼
  [Layer 4: 9-Sister & 3-Sister Council Orchestration (zoe_sisters.py)]
    3-Sister Council Leads:
      • Mono  (sm124 — Monochrome Verifier, Safety & Theorem 15 / Epistemic Audit)
      • Zoe   (ruby  — Core Coordinator, Dorothy 3D & Kloster A_tau(p) Synthesis)
      • Eliza (dos   — Gear 1 Symbolic Companion, Evidence Citations & Zero-Token Fallback)
    Specialist Sisters Dispatched on Concrete AI Tasks:
      • Gemma (gem3  — GEM Desktop VDI/RSC & Artline Geometry)
      • Tosi  (atari — Atari TOS / FreeGEM .RSC & Binary Resource Inspection)
      • Tetra (tetris — Ablation AIARE Reverse Engineering & Multi-Node Compute)
      • Sage  (hat   — Formal SymPy / Z3 Proofs & Research Synthesis)
      • Flora (sprout — Botanical C27 / Preclinical Neuro-Oncology Screening)
      • Lumen (prism — Optical MTF / Spectral Analysis & Native Voice/Cymatics)
```

**Canonical Showcase Flow:**
1. User/operator submits an AI task through `LumeCli`, `ZoeChat`, or `run_showcase_slice(...)` (`zoe_sisters.py` in M3).
2. `directive_violation()` and `ZoeEpistemicGate` screen the request before any memory or tool dispatch.
3. `stem_layering.route_stem()` computes $A_\tau(p)$ and routes cleanly (`gear1_eliza` fallback when offline/unprobed).
4. The **3-Sister Council (`Mono`, `Zoe`, `Eliza`)** coordinates task decomposition (`Zoe`), zero-token grounded retrieval/symbolic check (`Eliza`), and constitutional/Theorem-15 verification (`Mono`), dispatching specialist tasks across the 9 sisters (`Gemma`, `Tosi`, `Tetra`, `Sage`, `Flora`, `Lumen`) into `components/ablation/`, `shared_reasoning/`, `gem_aes_vdi`, and `UmaBridge` (strictly `PRIVATE` unless mutual `nick_allow && zoe_allow`).
5. Outputs return structured, SHA-256 tamper-evidenced records stamped with `external_actions=0`, `sentience_claimed=False`, `l5_agi_qualified=False`, `clinical_action_authorized=False`, `cure_claim=False`, and `flight_control_authorized=False`.

---

## 5. Verification Matrix

| Check / Suite | Scope | Command (Always Isolated State / Zero Servers Left Running) |
|---|---|---|
| **M1 Unit & Regression Suite** | Stem-layering, ChatStore/ZoeChat, LumeCli/ZoeAppBrain, UMA/Rome path unification & airlock | `python3 -m pytest components/Zoe-Autonomy/tests/test_stem_layering.py components/Zoe-Autonomy/tests/test_chat.py components/Zoe-Autonomy/tests/test_lume_cli.py components/Zoe-Autonomy/tests/test_uma_bridge_fixes.py components/Zoe-Autonomy/tests/test_eliza_routes.py components/Zoe-Autonomy/tests/test_bridge5_theorem15.py components/Zoe-Autonomy/tests/test_sr_composer_e2e.py -v` |
| **Elegance & Complexity Gate** | `chat.py` Grade A (`MI >= 60.0`, `max_cc <= 20`) & 0 Grade C/D repo-wide | `python3 -m pytest components/Zoe-Autonomy/tests/test_cli_and_chat_commands.py -k "not test_readme_and_proof_packet_links_and_counts" -v` |
| **L5 Phase 4 Verifier** | 20/20 independent checks (stem-layering, Eliza, memory, GEM, ZoeChat) | `python3 scripts/verify_l5_phase4.py --zoe-root . --json` |
| **One-System Chat Verifier** | Isolated `zoe_autonomy.chat` end-to-end & no hidden notebooks | `python3 scripts/verify-one-system.py --chat` |
| **Target Ecosystem Suites (Final Gate)** | 16-check L5 Core, SHA-256 Orbit seal, 9-stage L3 cycles, Shared Reasoning | `python3 scripts/verify_l5_core.py --zoe-root . --json`, `sha256sum -c evidence/renaissance-orbit/SHA256SUMS.orbit`, `python3 scripts/verify_l3_research.py`, `python3 scripts/verify_shared_reasoning.py --json` |
| **Protected State & Hygiene Check** | 5 protected `~/.zoe/*` files identical to pre-run baseline; 0 running `llama-server` / `zoe eliza serve` / `qemu` | `sha256sum ~/.zoe/chat/session.json ~/.zoe/uma-bridge/uma_state.json ~/.zoe/os-build/zoe-gem-os.iso ~/.zoe/os-build/zoe-gem-os-lts.iso ~/.zoe/os-build/zoe-state.img` |
