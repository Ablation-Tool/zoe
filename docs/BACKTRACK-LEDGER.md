# Documentation Gaps, Hygiene Findings & Backtrack Ledger

**Last Audited:** November 25, 2026 (`Ablation-Tool/zoe` + companion repositories)  
**Purpose:** Keep an honest, prioritized register of every completed documentation pass, structural fix, pending sibling subsystem, and manual operator auth task (`CONSTITUTION.md` Articles II.2 & IV.4).

---

## 1. Completed & Verified (All Priority 1 + Priority 2 Items Done!)

### A. Creative Epicurean Edition, Visual Plates & Organized Library
- Created **[`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md)** (*The Zoe & Ablation Epicurean*, inspired by Charles Ranhofer's 1894 *The Epicurean*, complete with 4 custom copperplate vector SVG plates in `assets/readme/zoe-epicurean-*.svg`, Kitchen Brigades, 5 Mother Stocks, 21 Numbered Receipts No. 6-26, and 5 Complete Bills of Fare).
- Created **[`INDEX.md`](INDEX.md)** (9-shelf organized documentation map across the entire monorepo and all 5 companion repositories).
- Repaired **23 active broken local links** across `guiai-lab/docs/RESILIENCE.md` (2), `guiai-lab/docs/UNIFIED.md` (7), `mobile/ZAPPS.md` (1), `components/Zoe-Autonomy/README.md` (4), `components/Zoe-Autonomy/EVALUATION.md` (1), `research/papers/zoe-research/L5-INTEGRATED-COGNITIVE-CORE.md` (2), `research/papers/zoe-research/L5-PHASE3-LIVE-AGENTIC-SYNTHESIS.md` (5), `research/papers/zoe-research/README.md` (1), plus `research/papers/zoe-research/dorothy/README.md` (1).
- Preserved SHA-256 integrity on **`research/papers/zoe-research/TEMPORAL-DYNAMICS-AND-GROOVE-FORENSICS.md`**: this monograph is cryptographically sealed inside `evidence/l3-research/l3-cycles-report.json`, so its original bytes remain verbatim (`verify_l3_research.py` `14/14 PASS`, `15/15` SHA-256 cited sources OK).

### B. Priority 1 Missing Guides (4 / 4 Complete)
- **P1-1 DONE:** Created **[`docs/ZOE-GEM-OS.md`](ZOE-GEM-OS.md)** (UEFI framebuffer desktop, Two-Key Hardware UMA Airlock, Pixel 7 `panther` ARM64 profiles, Braille Studio, 8 GEM eras / 10 ViewMAX schemes, 9-Realm Zoeverse, 9 Sisters, `zoe gemos` CLI, and `8/8` verifier).
- **P1-2 DONE:** Created **[`docs/ZOE-AND-CLARA.md`](ZOE-AND-CLARA.md)** (equal L1-L5 peer architecture, Theorem 15 `ECHO_CHAMBER_WARNING` & `ABSTAIN` guards, `:8768` web table, `< 1 MB` standalone zip bundle, and `8/8` verifier).
- **P1-3 DONE:** Created **[`docs/ACCESSIBILITY.md`](ACCESSIBILITY.md)** (top-level Ablation + GEM disability-first quick-card covering WCAG AA 4.5:1 / AAA 7.0:1, Okabe-Ito colorblind palette, 85%-200% zoom, `Ctrl++`/`Ctrl+-`/`Ctrl+0`, reduced motion, 2px focus ring, ATK screen reader labels, OS sync, and atomic `<= 16 KiB` `accessibility.json`).
- **P1-4 DONE:** Created **[`research/papers/zoe-research/L5-PHASE4-EMBODIED-STEM-LAYERING.md`](../research/papers/zoe-research/L5-PHASE4-EMBODIED-STEM-LAYERING.md)** (`20/20` verified, `max_delta = 0.0`) and **[`research/papers/zoe-research/L5-PHASE5-FRONTIER-ARC-FALSIFICATION.md`](../research/papers/zoe-research/L5-PHASE5-FRONTIER-ARC-FALSIFICATION.md)** (`22/22` verified, `max_delta = 0.0`), closing the chronological L5 monograph bridge from Phase 1 through Phase 6.

### C. Priority 2 Hygiene, Links, Case-Collision & CI Scope (5 / 5 Complete)
- **P2-1 DONE (`mobile/SAFECONVERT.md`):** Updated all 10 Android Java source & test links to point directly to their live standalone files in [`Ablation-Tool/SafeConvert`](https://github.com/Ablation-Tool/SafeConvert) (`research/zoetic/safeconvert/*.java`), eliminating every 404.
- **P2-2 DONE (Archival Snapshots & Dorothy README):** Added explicit frozen-archive provenance banner to [`research/papers/zoe-research/modules/README.md`](../research/papers/zoe-research/modules/README.md) pointing readers to live CI-verified docs while preserving frozen archive hashes untouched, and fixed the broken prospectus PDF link in [`research/papers/zoe-research/dorothy/README.md`](../research/papers/zoe-research/dorothy/README.md).
- **P2-3 DONE (`Ablation-Tool/ablation/docs/` Case-Collision Fix):** Renamed `docs/index.md` to `docs/documentation-index.md` in `Ablation-Tool/ablation` (and updated `tools/publish_wiki.py`, `.github/wiki/navigation.json`, `docs/reference-modules/documentation-wiki.md`, and `tests/test_wiki_publishing.py`) so Windows NTFS and macOS APFS checkouts never experience `INDEX.md` vs `index.md` case collisions while preserving the exact `Documentation-Index` Wiki slug.
- **P2-4 DONE (Expanded CI Link Scope):** Expanded [`scripts/verify_observatory_and_packages.py`](../scripts/verify_observatory_and_packages.py) to audit all active docs across `README.md`, `docs/`, `guiai-lab/docs/`, `mobile/`, `desktop/`, `dorothy-brain-observatory/`, and `components/Zoe-Autonomy/` on every GitHub Actions push (`0` broken links).
- **P2-5 DONE (Safe Legacy Em-Dash Sweep):** Replaced all 85 legacy em dashes (`U+2014`) across the 9 unsealed active docs (`README.md`, `docs/AGI-ROADMAP.md`, `docs/CAPABILITY-ATLAS.md`, `docs/PORTFOLIO-UPGRADES.md`, `mobile/README.md`, `mobile/SAFECONVERT.md`, `mobile/ZAPPS.md`, `mobile/TRINITY.md`, `dorothy-brain-observatory/README.md`) without disturbing a single SHA-256-sealed file.

### D. Newly Landed Sibling Subsystems Documented (`cc967172` & `c473f211`)
- Documented Google DeepMind Science (`deepmind_science.py`), native `google-antigravity` SDK Hooks (`deepmind_sdk_hooks.py`), Artline 2.0 Brainstorm Studio (`zoe_artline_brainstorm.py`), Clean-Room Retro Art Studio (`zoe_retro_art_studio.py`), Page A-2 Wombats Optional-Physics Room (`zoe_wombats_physics_room.py`), ADC-12 Duodecimal Shorthand (`zoe_artline_duodecimal.py`), and `zoe-artline` CLI (`zoe_artline_cli.py`) across [`CAPABILITY-ATLAS.md`](CAPABILITY-ATLAS.md) (§25), [`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md) (Receipts No. 24-26), and [`INDEX.md`](INDEX.md).

---

## 2. Remaining Queue (Still In-Flight Sibling Merges & Manual Auth Tasks)

### A. Remaining Unmerged Local Sibling Worktrees (Document Once Pushed to `main`)
Once active sibling sessions finish pushing the remaining Reconciled Showcase modules to `main`, add corresponding entries to [`INDEX.md`](INDEX.md), [`CAPABILITY-ATLAS.md`](CAPABILITY-ATLAS.md), and [`ZOE-COOKBOOK.md`](ZOE-COOKBOOK.md):
- **9-Sister & 3-Sister Council Showcase** (`zoe_sisters_showcase.py`, `test_zoe_sisters_showcase.py`)
- **Roman Empire 10-Wing Fusion, Hex Mesh & EDDMS** (`zoe_rome_fusion.py`, `zoe_hex_mesh.py`, `zoe_eddms.py`)
- **Ablation Ecosystem ON/OFF Bridge & 4-Tier E2E Showcase Suite** (`zoe_ablation_bridge.py`, `scripts/run_ecosystem_ablation_re.py`, `tests/e2e_zoe_showcase/`)

### B. Manual Operator Checklist (Requires Browser / Account Auth)
1. **Custom Domain DNS (`nuclide-research.com`):** Add the GitHub domain-verification TXT record in Squarespace Domains DNS under `Ablation-Tool` so `https://nuclide-research.com` binds cleanly to the already-live `Ablation-Tool/nuclide-research.com` GitHub Pages site.
2. **GitHub Sponsors Tiers (`Ablation-Tool`):** Run `gh auth refresh -s user` in a browser-authenticated terminal, then execute `python3 scripts/setup_sponsors_tiers.py --apply` inside `Ablation-Tool/Ablation-Tool`.
3. **Sync Local Monorepo Checkout:** Once sibling terminals complete their commits in `/media/cowboy/research/zoe-monorepo`, run `git pull --rebase origin main` so the local workspace pulls in all green CI fixes, P1 guides, P2 hygiene repairs, and Epicurean plates cleanly.
