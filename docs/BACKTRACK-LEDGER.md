# Documentation Gaps, Hygiene Findings & Backtrack Ledger

**Last Audited:** November 25, 2026 (`Ablation-Tool/zoe` + companion repositories)  
**Purpose:** Keep an honest, prioritized register of every missing guide, broken archival link, pending subsystem doc, and cross-platform hygiene trap so we can backtrack methodically without losing anything (`CONSTITUTION.md` Articles II.2 & IV.4).

---

## 1. Completed in This Documentation Pass (Done & Verified)

- Created **[`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md)** (*The Zoe & Ablation Epicurean*, inspired by Charles Ranhofer's 1894 Delmonico's classic *The Epicurean*, complete with an 1894 copperplate-style frontispiece SVG, kitchen brigade, 5 mother stocks, 18 numbered receipts, and 5 complete evening bills of fare).
- Created **[`INDEX.md`](INDEX.md)** (shelf-by-shelf documentation map organizing all guides across `docs/`, `guiai-lab/docs/`, `mobile/`, `desktop/`, `dorothy-brain-observatory/`, `components/`, and `research/`).
- Repaired **24 broken local links** across active documentation caused by the root-streamlining move (`CONSTITUTION.md`, `DECLARATION.md`, `AGI-ROADMAP.md`, `CAPABILITY-ATLAS.md`, `MONOREPO.md`, `one-system.json`, `components.lock.json`, `evaluation.json`) in:
  - `guiai-lab/docs/RESILIENCE.md` (2 fixed)
  - `guiai-lab/docs/UNIFIED.md` (7 fixed)
  - `mobile/ZAPPS.md` (1 fixed)
  - `components/Zoe-Autonomy/README.md` (4 fixed)
  - `components/Zoe-Autonomy/EVALUATION.md` (1 fixed)
  - `research/papers/zoe-research/L5-INTEGRATED-COGNITIVE-CORE.md` (2 fixed)
  - `research/papers/zoe-research/L5-PHASE3-LIVE-AGENTIC-SYNTHESIS.md` (5 fixed)
  - `research/papers/zoe-research/README.md` (1 fixed)
  - `research/papers/zoe-research/TEMPORAL-DYNAMICS-AND-GROOVE-FORENSICS.md` (1 fixed)

---

## 2. Priority 1: Missing Guides for Live Shipped Subsystems (Backtrack Next)

| # | Missing Document / Guide | What Exists Today in Code | Why It Matters Later |
|:---|:---|:---|:---|
| **P1-1** | **Dedicated Zoe-GEM OS & Hardware UMA Field Guide** (`docs/ZOE-GEM-OS.md`) | Code & 8/8 verifier live (`zoe_uma.py`, `zoe_pixel_os.py`, `zoe_phone_codex_sync.py`, `zoe_braille_studio.py`, `zoe_gem_themes.py`, `zoe_sisters.py`, `zoe_universe.py`, `gemos_view.py`); only summarized in `CAPABILITY-ATLAS.md` §24 and brief `guiai-lab/docs/GEM-OS.md` | Gives builders and users one clear guide for UEFI QEMU builds, mutual-consent UMA airlock keys, Pixel 7 `panther` Track A/B boundaries, Braille Studio, and Zoeverse |
| **P1-2** | **Dedicated Dual-Peer Zoe & Clara Guide** (`docs/ZOE-AND-CLARA.md`) | Full engine (`zoe_clara.py`), 525 KB standalone zip bundle, `:8768` web UI, and `8/8` verifier (`verify_zoe_clara.py`) are live, but only covered in `README.md` & Cookbook Recipe 1 | Documents how equal L1-L5 peers avoid echo-chamber drift (Theorem 15), how to bundle/ship the standalone 525 KB core, and how online/offline modes work |
| **P1-3** | **Ablation GEM Accessibility Quick-Card** (`docs/ACCESSIBILITY.md`) | Full WCAG AA/AAA accessibility engine (`accessibility.py`, `safety.py`, `gtk_app.py`, `app.py`, `test_accessibility.py`) is shipped and synced to both `zoe` and `ablation`, documented inside `components/ablation/gem-lab/README.md` | Makes disability-first design (`Ctrl++` zoom, Okabe-Ito colorblind, AAA high contrast, reduced motion, 2px focus ring, ATK screen reader, OS sync) discoverable at top-level `docs/` |
| **P1-4** | **L5 Phase 4 & L5 Phase 5 Technical Papers** (`research/papers/zoe-research/L5-PHASE4-*.md`, `L5-PHASE5-*.md`) | Engines (`l5_phase4_embodied.py`, `l5_phase5_frontier.py`), verifiers, and evidence reports exist, and Papers 1, 2, 3, and 6 exist, leaving a visible gap between Phase 3 and Phase 6 | Closes the chronological gap in the L5 monograph sequence so readers moving from Phase 3 to Phase 6 see how embodied stem-layering (Phase 4) and ARC/falsification (Phase 5) bridge them |

---

## 3. Priority 2: Broken Links & Structural Issues to Backtrack On

| # | Location | Exact Issue Found in Audit | Recommended Backtrack Action |
|:---|:---|:---|:---|
| **P2-1** | `mobile/SAFECONVERT.md` (10 broken Android Java links) | Links to `android/app/src/main/java/research/zoetic/zoe/SafeBeaconMesh.java`, `SafeConvertActivity.java`, `SafeEvidenceStore.java`, `SafeVaultLock.java`, and their 5 unit/Espresso tests, which moved out when SafeConvert became standalone at `Ablation-Tool/SafeConvert` (Apple Swift & shared HTML remain in `mobile/`) | Update `mobile/SAFECONVERT.md` to point Android Java source links cleanly to `https://github.com/Ablation-Tool/SafeConvert` (or restore a mirrored stub note) so zero links 404 on GitHub |
| **P2-2** | `research/papers/zoe-research/docs/{native,cern,neurogarden}/` (~100 broken relative links in archival copies) | Frozen archival snapshots of older docs still reference relative `images/*.png`, `../reference-modules/*.md`, and `zoe-visual-guides.pdf` paths that live in `guiai-lab/docs/` or `components/ablation/docs/` rather than inside `research/papers/zoe-research/docs/` | Decide whether to (a) add a clear frozen-archive banner noting canonical live paths in `guiai-lab/docs/` and `components/`, or (b) rewrite relative links to point to canonical files; also fix `research/papers/zoe-research/dorothy/README.md` link `../papers/17-zoe-capability-prospectus.pdf` |
| **P2-3** | `Ablation-Tool/ablation/docs/` (**Windows/macOS Case Collision Risk**) | Both `docs/INDEX.md` (84 KB, actively updated Nov 25) and `docs/index.md` (2 KB, older Nov 5 file) exist simultaneously in `Ablation-Tool/ablation/docs/` | On case-insensitive filesystems (Windows NTFS / macOS APFS), git checkouts of `Ablation-Tool/ablation` will experience dirty-tree collisions between `INDEX.md` and `index.md`. Merge or remove the legacy lowercase `docs/index.md` on a dedicated pass in `Ablation-Tool/ablation` |
| **P2-4** | `scripts/verify_observatory_and_packages.py` link scope | Currently audits `README.md` + `docs/*.md` (`1,455` links, `0` broken), so broken links in `guiai-lab/docs/*.md`, `mobile/*.md`, `components/Zoe-Autonomy/*.md`, and `research/papers/zoe-research/*.md` were invisible to CI | Expand the link check (once P2-1 is cleaned up) to cover `guiai-lab/docs/`, `mobile/`, and `components/Zoe-Autonomy/` so broken cross-doc links can never sneak back in |
| **P2-5** | Remaining em-dash (`U+2014`) cleanup across older legacy docs | Found lingering em dashes in `README.md` (2), `docs/AGI-ROADMAP.md` (8), `docs/CAPABILITY-ATLAS.md` (7), `docs/PORTFOLIO-UPGRADES.md` (15), `mobile/README.md` (8), `mobile/SAFECONVERT.md` (13), `mobile/ZAPPS.md` (22), `mobile/TRINITY.md` (6), `dorothy-brain-observatory/README.md` (4) | Run a careful prose sweep replacing em dashes with clean punctuation (`:`, commas, parentheses, or hyphens) without altering any SHA-256-sealed files |

---

## 4. Priority 3: Upcoming In-Flight Subsystems & Operator Tasks

### A. In-Flight Sibling Worktrees (Document Immediately After Merge)
Active parallel engineering sessions in the local monorepo workspace are finishing the Reconciled Showcase milestones (`M1-M4`, tracked in local `docs/RECONCILED_SHOWCASE_PLAN.md`). Once merged and pushed to `main`, add entries to [`INDEX.md`](INDEX.md), [`CAPABILITY-ATLAS.md`](CAPABILITY-ATLAS.md), and new recipes to [`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md) for:
- **9-Sister & 3-Sister Council Showcase** (`zoe_sisters_showcase.py`, `test_zoe_sisters_showcase.py`)
- **Roman Empire 10-Wing Fusion & Retro Art / Artline Brainstorm Studios** (`zoe_rome_fusion.py`, `zoe_retro_art_studio.py`, `zoe_artline_brainstorm.py`, `zoe_hex_mesh.py`, `zoe_eddms.py`)
- **Ablation Ecosystem ON/OFF Bridge & DeepMind Science Hooks** (`zoe_ablation_bridge.py`, `deepmind_science.py`, `deepmind_sdk_hooks.py`, `scripts/run_ecosystem_ablation_re.py`, `evidence/ecosystem-ablation/`)
- **Hardened `ChatStore(read_only=True)`, `LumeCli`, `UmaBridge`, and 4-Tier E2E Showcase Suite** (`tests/e2e_zoe_showcase/`)

### B. Manual Operator Checklist (Requires Browser / Account Auth)
1. **Custom Domain DNS (`nuclide-research.com`):** Add the GitHub domain-verification TXT record in Squarespace Domains DNS under `Ablation-Tool` so `https://nuclide-research.com` binds cleanly to the already-live `Ablation-Tool/nuclide-research.com` GitHub Pages site.
2. **GitHub Sponsors Tiers (`Ablation-Tool`):** Run `gh auth refresh -s user` in a browser-authenticated terminal, then execute `python3 scripts/setup_sponsors_tiers.py --apply` inside `Ablation-Tool/Ablation-Tool`.
3. **Sync Local Monorepo Checkout:** Once sibling terminals complete their M1-M4 commits in `/media/cowboy/research/zoe-monorepo`, run `git pull --rebase origin main` so the local workspace pulls in the green CI fixes (`1fa60eca..25ed9706`) and this documentation update cleanly.
