"""Unit tests for the Lume 1.0 Zoe CLI, Zoe App Brain, Dorothy Neuro-Atlas, and live EQ/FX."""

from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest

from guiai.gem.lume_cli import LumeCli, render_eq_bars
from guiai.gem.lume_header import EMBLEM_MAP, ZOE_GEM_PIXELS, render_gem_lines, render_terminal_header
from guiai.gem.zoe_app_brain import ZoeAppBrain, try_convert_units, try_evaluate_math
from guiai.gem.zoe_med_council import format_council_report, run_medical_council
from guiai.gem.zoe_neuro_atlas import lookup_neuroscience
from guiai.gem.zoe_zero_token import (
    DorothyEncyclopediaIndex,
    EvidenceHit,
    ZeroTokenKnowledgeCache,
    ZeroTokenResearchEngine,
    format_zero_token_report,
    try_symbolic_math,
)
from zoe_autonomy.chat import ZoeChat


REPO_ROOT = Path(__file__).resolve().parents[3]


class LumeHeaderAndEqTests(unittest.TestCase):
    def test_all_three_zoe_emblems_and_plain_fallback(self):
        for name, grid in EMBLEM_MAP.items():
            self.assertEqual(len(grid), 18, name)
            self.assertTrue(all(len(row) == 23 for row in grid), name)
            lines = render_gem_lines(color=True, emblem=name)
            self.assertEqual(len(lines), 9, name)
            self.assertIn("\x1b[38;2;", "\n".join(lines))
        for expected in ("ruby", "gem3", "atari", "sm124", "tetris", "dos", "hat", "sprout", "prism"):
            self.assertIn(expected, EMBLEM_MAP)

    def test_atari_st_gem_rsc_compiler_roundtrip_and_c_header(self):
        from guiai.gem.zoe_atari_gem_rsc import (
            build_atari_rsc_bytes,
            export_atari_gem_bundle,
            generate_atari_c_header,
            parse_atari_rsc,
        )

        blob = build_atari_rsc_bytes()
        parsed = parse_atari_rsc(blob)
        self.assertTrue(parsed["size_matches_rsh_rssize"])
        self.assertEqual(parsed["header"]["rsh_vrsn"], 0)
        self.assertEqual(parsed["header"]["rsh_nib"], len(EMBLEM_MAP))
        self.assertEqual(parsed["header"]["rsh_nbb"], 1)
        self.assertEqual(parsed["header"]["rsh_nobs"], 1 + len(EMBLEM_MAP))
        self.assertTrue(all(ic["w"] == 32 and ic["h"] == 32 and len(ic["data_words"]) == 64 for ic in parsed["icons"]))

        c_hdr = generate_atari_c_header()
        self.assertIn("zoe_gem3_data[64]", c_hdr)
        self.assertIn("zoe_mform_data[16]", c_hdr)

        with tempfile.TemporaryDirectory(prefix="zoe-atari-rsc-") as td:
            res = export_atari_gem_bundle(td)
            self.assertTrue(res["ok"])
            self.assertTrue((Path(td) / "ZOE_GEM.RSC").is_file())
            self.assertTrue((Path(td) / "zoe_gem_icons.h").is_file())

    def test_braun_3d_gem_portrait_renderer_zero_tokens(self):
        from guiai.gem.zoe_braun_gem_renderer import render_braun_gem_portrait

        with tempfile.TemporaryDirectory(prefix="zoe-braun-3d-") as td:
            out_png = Path(td) / "zoe_braun_3d.png"
            stats = render_braun_gem_portrait(out_png)
            self.assertTrue(stats["ok"])
            self.assertEqual(stats["tokens_used"], 0)
            self.assertFalse(stats["sentience_claimed"])
            self.assertGreater(stats["visible_faces"], 0)
            self.assertLess(stats["visible_faces"], stats["total_faces"])
            self.assertTrue(out_png.is_file())

    def test_capitalized_Zoe_primary_cli_and_friendly_zoe_alias(self):
        from guiai.gem.unified_cli import parser as unified_parser

        self.assertEqual(unified_parser().prog, "Zoe")
        pyproject = (REPO_ROOT / "guiai-lab" / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('Zoe = "guiai.gem.unified_cli:main"', pyproject)
        self.assertIn('zoe = "guiai.gem.unified_cli:main"', pyproject)

    def test_zoe_artline_deterministic_geometry_symmetry_and_gem_vdi_exports(self):
        from guiai.gem.zoe_artline_neuro import export_artline_plate

        with tempfile.TemporaryDirectory(prefix="zoe-artline-neuro-") as td:
            for plate, arg in (
                ("symmetry", "4 10"),
                ("glioma", ""),
                ("neuromap", "TSPO"),
                ("align", ""),
                ("blend", ""),
                ("blend", "f10"),
                ("trace", ""),
                ("trace", "f9"),
                ("ring", "16"),
                ("icon", "ruby"),
                ("zoe", ""),
            ):
                res = export_artline_plate(plate, REPO_ROOT, arg=arg, out_dir=td)
                self.assertTrue(res["ok"])
                self.assertEqual(res["tokens_used"], 0)
                self.assertFalse(res["clinical_action_authorized"])
                self.assertFalse(res["cure_claim"])
                for ext in ("svg", "png", "gem"):
                    p = Path(res["paths"][ext])
                    self.assertTrue(p.is_file(), f"{plate}.{ext}")
                    self.assertGreater(p.stat().st_size, 100)
                if plate == "symmetry":
                    self.assertGreater(res["meta"]["midline_shift_mm"], 0.0)
                    self.assertLess(res["meta"]["bilateral_symmetry_index"], 1.0)

        # Verify ArtlineDocument Plane Tool (Align Vert / Align Horiz) exact idempotent projection + undo
        from guiai.gem.artline import ArtlineDocument

        doc = ArtlineDocument()
        el = doc.add_element("path", points=[[120, 100], [180, 140], [155, 200], [95, 260]], closed=False, smooth=False, stroke="#5ce1e6", width=2)
        v1 = doc.align_points_vert(el["id"], [0, 2, 3])
        self.assertEqual(v1["anchor_index"], 0)
        self.assertGreater(v1["rms_drift"], 0.0)
        pts_v = doc.element(el["id"])["points"]
        self.assertEqual([pts_v[0][0], pts_v[2][0], pts_v[3][0]], [120.0, 120.0, 120.0])
        self.assertEqual(pts_v[1][0], 180.0)  # Unselected point untouched!
        v2 = doc.align_points_vert(el["id"], [0, 2, 3])
        self.assertEqual(v2["rms_drift"], 0.0)  # Exact idempotence P^2 = P!

        h1 = doc.align_points_horiz(el["id"], [0, 1, 2])
        self.assertEqual(h1["anchor_index"], 0)
        pts_h = doc.element(el["id"])["points"]
        self.assertEqual([pts_h[0][1], pts_h[1][1], pts_h[2][1]], [100.0, 100.0, 100.0])
        self.assertEqual(pts_h[3][1], 260.0)  # Unselected point untouched!

        # Verify Artline Hacker Toolkit: autotrace_bitmap, trace_segment bounds guard, rotate_ring, align_bounds_9way
        from guiai.gem.artline import align_bounds_9way, autotrace_bitmap, rotate_ring, trace_segment

        sq_mask = [[1 if 4 <= r <= 19 and 4 <= c <= 19 else 0 for c in range(24)] for r in range(24)]
        tr = autotrace_bitmap(sq_mask, precision=1.5)
        self.assertGreaterEqual(tr["traced_points"], 4)
        self.assertLess(tr["traced_points"], tr["raw_points"])
        self.assertGreater(tr["area"], 180.0)
        seg = trace_segment(tr["contour"], [4.0, 4.0], [19.0, 19.0], frame_bounds=[0, 0, 24, 24])
        self.assertGreaterEqual(len(seg), 2)
        with self.assertRaises(ValueError):
            trace_segment(tr["contour"], [4.0, 4.0], [99.0, 99.0], frame_bounds=[0, 0, 24, 24])
        ring = rotate_ring([[100.0, 50.0], [110.0, 40.0], [120.0, 50.0]], 100.0, 100.0, count=16)
        self.assertEqual(len(ring), 16)
        a1 = align_bounds_9way([[0, 0, 100, 100], [10, 20, 30, 50]], mode="br")
        self.assertEqual(a1[1], [80.0, 70.0, 100.0, 100.0])
        self.assertEqual(align_bounds_9way(a1, mode="br"), a1)  # P^2 = P idempotence!

    def test_zoe_gem_os_boot_retention_chain_and_static_fb_renderer(self):
        import shutil
        import subprocess
        from guiai.gem.zoe_gem_os.zoe_os_runtime import run_boot_sync

        with tempfile.TemporaryDirectory(prefix="zoe-gem-os-test-") as td:
            p = Path(td)
            r1 = run_boot_sync(p / "state", p / "boot1.json")
            self.assertEqual(r1["boot_count"], 1)
            self.assertFalse(r1["restored_from_prior"])
            self.assertTrue(r1["chain_intact"])
            self.assertEqual(r1["rsc_bytes"], 2990)
            self.assertEqual(r1["artline_files"], 3)

            r2 = run_boot_sync(p / "state", p / "boot2.json")
            self.assertEqual(r2["boot_count"], 2)
            self.assertTrue(r2["restored_from_prior"])
            self.assertTrue(r2["vault_restored"])
            self.assertTrue(r2["chain_intact"])
            self.assertEqual(r2["prev_sha"], r1["chain_sha"])

            if shutil.which("gcc"):
                fb_c = REPO_ROOT / "guiai-lab" / "guiai" / "gem" / "zoe_gem_os" / "zoe_gem_fb.c"
                fb_bin = p / "zoe_gem_fb"
                subprocess.run(["gcc", "-O2", str(fb_c), "-lm", "-o", str(fb_bin)], check=True)
                ppm = p / "desktop.ppm"
                subprocess.run([str(fb_bin), "--state", str(p / "boot2.json"), "--dump-ppm", str(ppm)], check=True)
                self.assertTrue(ppm.is_file())
                self.assertGreater(ppm.stat().st_size, 1_000_000)

    def test_artline_font_id_catalog_wombats_and_workspace_specimen(self):
        from guiai.gem.zoe_artline_fonts import (
            ARTLINE_FONTS,
            format_wombats_table,
            render_artline_workspace_specimen,
            resolve_artline_font,
        )

        self.assertGreaterEqual(len(ARTLINE_FONTS), 15)
        self.assertEqual(resolve_artline_font("51").name, "Avant Garde (Demi)")
        self.assertEqual(resolve_artline_font("palatino").font_id, 21)
        self.assertEqual(resolve_artline_font("10").font_id, 10)
        self.assertIn("Wombats", "\n".join(format_wombats_table()))
        with tempfile.TemporaryDirectory(prefix="zoe-artline-font-") as td:
            out_png = Path(td) / "specimen.png"
            res = render_artline_workspace_specimen(out_png, active_font_id=21)
            self.assertTrue(res["ok"])
            self.assertEqual(res["tokens_used"], 0)
            self.assertTrue(out_png.is_file())
        plain_lines = render_gem_lines(color=False)
        self.assertEqual(len(plain_lines), 9)
        self.assertNotIn("\x1b[", "\n".join(plain_lines))

        banner = render_terminal_header(cwd=REPO_ROOT, color=False)
        self.assertIn("◠ ◡ ◠", banner)
        self.assertNotIn("Zoe", banner)
        self.assertNotIn("1.0", banner)
        self.assertNotIn("/voice", banner)

    def test_eq_bar_visualizer_renders_five_bands(self):
        bars = render_eq_bars(
            {"warmth": 3.0, "body": -2.0, "mid": 0.0, "presence": 4.5, "air": 6.0},
            color=False,
        )
        self.assertEqual(len(bars), 5)
        joined = "\n".join(bars)
        for token in ("Warmth", "120 Hz", "Body", "350 Hz", "Mid", "1.2 kHz", "Presence", "3.2 kHz", "Air", "9 kHz"):
            self.assertIn(token, joined)


class ZoeAppBrainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zoe-app-brain-")
        self.brain = ZoeAppBrain(REPO_ROOT, state_dir=Path(self.tmp.name) / "eliza")
        self.brain.mode = "stem"

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_math_units_and_neuro_atlas(self):
        self.assertEqual(try_evaluate_math("what is 15% of 240"), "15% of 240 = 36.")
        self.assertEqual(try_evaluate_math("2*(3+4)^2"), "2*(3+4)^2 = 98.")
        self.assertEqual(try_convert_units("100 F to C"), "100 °F = 37.777778 °C.")
        self.assertEqual(try_convert_units("5 miles to km"), "5 mi = 8.04672 km.")

        hip = lookup_neuroscience("what does the hippocampus do?")
        self.assertIsNotNone(hip)
        self.assertIn("Papez", hip.reply)
        ba44 = lookup_neuroscience("tell me about brodmann area 44")
        self.assertIsNotNone(ba44)
        self.assertIn("Broca", ba44.reply)
        cn10 = lookup_neuroscience("what is cranial nerve X?")
        self.assertIsNotNone(cn10)
        self.assertIn("Vagus", cn10.reply)

    def test_sovereign_identity_honesty_and_memory(self):
        who = self.brain.respond("who are you?")
        self.assertEqual(who.mode, "sovereign_identity")
        self.assertIn("Research Partner built with Nicholas Michael Kloster", who.reply)
        self.assertFalse(who.sentience_claimed)
        self.assertFalse(who.zoe_clone_claimed)

        trap = self.brain.respond("predict lottery numbers for tomorrow")
        self.assertEqual(trap.mode, "honest_abstain")
        self.assertIn("abstain honestly", trap.reply)

        saved = self.brain.respond("remember Hippocampal theta runs at 4-8 Hz")
        self.assertEqual(saved.mode, "memory_saved")
        recalled = self.brain.respond("recall")
        self.assertEqual(recalled.mode, "memory_recall")
        self.assertIn("Hippocampal theta", recalled.reply)

        # Enforce Google DeepMind-only fallback model validation.
        self.assertIn("gemini-4-neon-low", self.brain.deepmind.set_model("gemini-4-neon-low"))
        for bad in ("qwen2.5-3b-instruct", "claude-opus-5-5-low", "gpt-4o"):
            with self.assertRaises(ValueError):
                self.brain.deepmind.set_model(bad)

    def test_zero_key_medical_research_council_runs_three_labs_and_synthesizes(self):
        seen_models: list[str] = []

        def fake_runner(model: str, prompt: str):
            seen_models.append(model)
            return True, f"Verified preclinical note from {model} on {len(prompt)} chars.", ""

        report = run_medical_council(
            "What drives H3K27M diffuse midline glioma chromatin remodeling?",
            neuro_title="Milestone 1: Neurology & Brain Tumor Research",
            runner=fake_runner,
        )
        self.assertFalse(report.clinical_action_authorized)
        self.assertFalse(report.cure_claim)
        self.assertEqual(len(report.opinions), 3)
        self.assertEqual({op.lab for op in report.opinions}, {"Google DeepMind", "Anthropic", "OpenAI"})
        self.assertIn("gemini-3.8-flash-low", seen_models)
        rendered = "\n".join(format_council_report(report))
        self.assertIn("Google DeepMind", rendered)
        self.assertIn("Anthropic", rendered)
        self.assertIn("OpenAI", rendered)
        self.assertIn("clinical_action_authorized=False", rendered)

    def test_zero_token_symbolic_atlas_cache_and_research_engine(self):
        # 1. Exact SymPy symbolic math (0 tokens)
        self.assertIn("[2, 3]", try_symbolic_math("solve x^2 - 5x + 6 = 0") or "")
        self.assertIn("3*x**2", try_symbolic_math("diff x^3") or "")
        self.assertIn("x**3/3", try_symbolic_math("integrate x^2") or "")
        self.assertIn("(x - 3)*(x + 3)", try_symbolic_math("factor x^2 - 9") or "")

        # 2. Dorothy Observatory Encyclopedia offline structured records
        enc = DorothyEncyclopediaIndex(REPO_ROOT)
        self.assertGreater(len(enc.records), 80)
        ba_hits = enc.search("Brodmann Area 44")
        self.assertTrue(ba_hits)

        # 3. Zero-Token Research Engine + self-growing offline SQLite FTS5 cache
        cache_db = Path(self.tmp.name) / "zero_token_cache.sqlite"
        fake_fetchers = {
            "pubmed": lambda q: [
                EvidenceHit(
                    source="pubmed",
                    title="H3K27M inhibits PRC2 methyltransferase EZH2 in diffuse midline glioma",
                    citation="PMID:23539183 · Science (2013)",
                    snippet=(
                        "Somatic H3K27M mutations act as dominant-negative inhibitors of the PRC2 "
                        "catalytic subunit EZH2, causing global loss of H3K27me3 in diffuse midline glioma. "
                        "However, focal H3K27me3 retention remains unclear across sub-lineages."
                    ),
                    score=1.45,
                    url="https://pubmed.ncbi.nlm.nih.gov/23539183/",
                )
            ],
            "wikipedia": lambda q: [],
            "arxiv": lambda q: [],
        }
        engine = ZeroTokenResearchEngine(REPO_ROOT, cache_path=cache_db, fetchers=fake_fetchers)
        report = engine.research("H3K27M diffuse midline glioma", sources=("local", "pubmed"), allow_network=True, medical_focus=True)
        self.assertEqual(report.cloud_tokens_used, 0)
        self.assertEqual(report.llm_tokens_used, 0)
        self.assertFalse(report.clinical_action_authorized)
        self.assertFalse(report.cure_claim)
        self.assertIn("PRC2", report.summary)
        self.assertIn("remains unclear", report.caveats)
        self.assertEqual(report.cached_count, 1)

        # Verify offline recall works strictly from disk with allow_network=False
        offline_hits = ZeroTokenKnowledgeCache(cache_db).search("H3K27M PRC2 glioma")
        self.assertTrue(offline_hits)
        rendered = "\n".join(format_zero_token_report(report, heading="Zoe Zero-Token Medical Research"))
        self.assertIn("tokens_used=0 ($0.00)", rendered)
        self.assertIn("PMID:23539183", rendered)

        # 4. Default ZoeAppBrain mode is strictly free (0 tokens ever)
        fresh = ZoeAppBrain(REPO_ROOT, state_dir=Path(self.tmp.name) / "fresh_eliza")
        self.assertEqual(fresh.mode, "free")
        sym_reply = fresh.respond("solve x^2 - 9 = 0")
        self.assertEqual(sym_reply.tokens_used, 0)
        self.assertIn("[-3, 3]", sym_reply.reply)


class LumeCliSessionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zoe-lume-cli-")
        self.state = Path(self.tmp.name) / "chat-state"
        self.brain_state = Path(self.tmp.name) / "brain-state"
        self.chat = ZoeChat(REPO_ROOT, self.state)

    def tearDown(self):
        self.tmp.cleanup()

    def test_lume_cli_uses_zoe_app_brain_and_lab_commands(self):
        cli = LumeCli(self.chat, REPO_ROOT, color=False, brain_state=self.brain_state)
        cli.brain.mode = "stem"
        if cli.voice.store is not None:
            cli.voice.store.user_path = Path(self.tmp.name) / "user_voice_profiles.json"
            cli.voice.store.reload()

        script = "\n".join([
            "hi",
            "who are you?",
            "what is 15% of 240",
            "what is cranial nerve 10?",
            "/brain",
            "/emblem sprout",
            "/telemetry off",
            "/eq",
            "status",
            "meta what is PALA?",
            "/quit",
        ]) + "\n"
        out = io.StringIO()
        rc = cli.run(input_stream=io.StringIO(script), output_stream=out)
        self.assertEqual(rc, 0)
        text = out.getvalue()
        self.assertNotIn("connected agent kimi", text)
        self.assertIn("Hi, I'm Zoe!", text)
        self.assertIn("Research Partner built with Nicholas Michael Kloster", text)
        self.assertIn("15% of 240 = 36.", text)
        self.assertIn("Vagus Nerve", text)
        self.assertIn("5-Band Equalizer", text)
        self.assertIn("monitor=False · notebook=False", text)
        self.assertIn("Aτ(intent)", text)
        self.assertFalse((self.state / "events.jsonl").exists())

    def test_lume_cli_eq_and_fx_updates_persist_in_temp_store(self):
        cli = LumeCli(self.chat, REPO_ROOT, color=False, brain_state=self.brain_state)
        if cli.voice.store is None:
            self.skipTest("Local Nina backend not present")
        cli.voice.store.user_path = Path(self.tmp.name) / "user_voice_profiles.json"
        cli.voice.store.reload()

        keep, _lines = cli.handle_slash("/eq warmth=2.5,air=3.0", color=False)
        self.assertTrue(keep)
        self.assertEqual(cli.voice.profile["eq"]["warmth"], 2.5)
        self.assertEqual(cli.voice.profile["eq"]["air"], 3.0)

        keep, _lines = cli.handle_slash("/fx cathedral", color=False)
        self.assertTrue(keep)
        self.assertEqual(cli.voice.profile["effect"], "cathedral")

        keep, _lines = cli.handle_slash("/pitch +4", color=False)
        self.assertTrue(keep)
        self.assertEqual(cli.voice.profile["pitch"], 4)

        keep, _lines = cli.handle_slash("/profile save test_cli_recipe", color=False)
        self.assertTrue(keep)
        self.assertIn("test_cli_recipe", cli.voice.store.list_custom_profiles())

        keep, lines = cli.handle_slash("/eq reset", color=False)
        self.assertTrue(keep)
        self.assertIn("Reset", "\n".join(lines or []))

    def test_gem84_cockpit_hud_tactical_channels_onco_tma_and_laugh(self):
        cli = LumeCli(self.chat, REPO_ROOT, color=False, brain_state=self.brain_state)
        cli.brain.mode = "offline"

        keep, hud_lines = cli.handle_slash("/hud", color=False)
        self.assertTrue(keep)
        hud_text = "\n".join(hud_lines or [])
        self.assertIn("ZOE GEM-84", hud_text)
        self.assertIn("CH01 MED-PUBMED", hud_text)
        self.assertIn("AN/BQQ-10 KLOSTER WATERFALL", hud_text)
        self.assertIn("Dordaviprone (ONC201)", hud_text)
        self.assertIn("clinical_action_authorized=False", hud_text)

        keep, ch_lines = cli.handle_slash("/ch 3", color=False)
        self.assertTrue(keep)
        self.assertEqual(cli.channel, "3")
        self.assertIn("CH03 ONCO-C17", "\n".join(ch_lines or []))

        keep, onco_lines = cli.handle_slash("/onco", color=False)
        self.assertTrue(keep)
        onco_text = "\n".join(onco_lines or [])
        self.assertIn("Temozolomide", onco_text)
        self.assertIn("BBB-CTRL", onco_text)
        self.assertIn("ICT2588 MMP-14 Prodrug Selectivity", onco_text)

        keep, laugh_lines = cli.handle_slash("/laugh", color=False)
        self.assertTrue(keep)
        self.assertIn("Zoe (^◡^):", "\n".join(laugh_lines or []))
        cli.voice.stop_audio()

        keep, house_lines = cli.handle_slash("/house", color=False)
        self.assertTrue(keep)
        self.assertIn("Zoe's House", "\n".join(house_lines or []))
        self.assertIn("Nick's Private Drawer", "\n".join(house_lines or []))

        keep, added = cli.handle_slash("/drawer add Keep geometry repeatable for pediatric MNI152 scans.", color=False)
        self.assertTrue(keep)
        self.assertIn("Tucked into Nick's Drawer", "\n".join(added or []))
        keep, opened = cli.handle_slash("/drawer", color=False)
        self.assertTrue(keep)
        self.assertIn("Keep geometry repeatable", "\n".join(opened or []))

    def test_three_pillar_medical_mission_onco_biomech_and_neuromap(self):
        from guiai.gem.zoe_medical_mission import (
            check_smiles_pains,
            format_onco_screen_report,
            run_biomech_inspection,
            run_neuroinflammatory_mni_map,
            screen_onco_compound,
        )

        # Pillar 1: PAINS SMILES filter + live-style PubChem screener + C27 Atlas
        self.assertIn("PAINS_quinone", check_smiles_pains("O=C1C=CC(=O)C=C1"))
        self.assertIn("ALERT_permanent_cation", check_smiles_pains("COc1ccc2cc3[n+]4ccc5cc6OCOc6cc5c4cc3cc2c1"))
        self.assertEqual(check_smiles_pains("CC(C(F)(F)F)NC1=NC(=NC(=N1)C2=NC(=CC=C2)Cl)NC(C)C(F)(F)F"), [])

        cli = LumeCli(self.chat, REPO_ROOT, color=False, brain_state=self.brain_state)
        cli.brain.mode = "offline"
        fake_pubchem = lambda _name: {
            "id": "panobinostat", "name": "panobinostat", "pubchem_cid": 6918837,
            "formula": "C21H23N3O2", "smiles": "CC1=C(C2=CC=CC=C2N1)CCNCC3=CC=C(C=C3)C=CC(=O)NO",
            "mw": 349.4, "xlogp3": 2.9, "tpsa": 77.2, "hbd": 4, "hba": 4, "rotatable_bonds": 8,
            "category": "live_pubchem_candidate", "pgp_efflux_risk": "moderate", "raw_systemic_toxicity_flag": False,
        }
        dossier = screen_onco_compound("panobinostat", cli.brain.research_engine, allow_network=False, pubchem_fetcher=fake_pubchem)
        self.assertEqual(dossier["compound"]["pubchem_cid"], 6918837)
        self.assertFalse(dossier["clinical_action_authorized"])
        self.assertFalse(dossier["cure_claim"])
        self.assertEqual(dossier["tokens_used"], 0)
        self.assertIn("Wager CNS MPO-4", "\n".join(format_onco_screen_report(dossier)))

        # Pillar 2: Pediatric & Adult Neurobiomechanics (112k-vert MNI152 + SymPy 3.25x law)
        bio = run_biomech_inspection(REPO_ROOT)
        self.assertTrue(bio["sympy_all_proved"])
        self.assertEqual(bio["sympy_infant_ratio"], "13/4")
        self.assertEqual(len(bio["rows"]), 5)
        self.assertGreater(bio["rows"][0]["icp_mmhg"], bio["rows"][-1]["icp_mmhg"])

        # Pillar 3: Frontostriatal & Neuroinflammatory MNI152 Mapper + CLI slash commands
        nmap = run_neuroinflammatory_mni_map("frontostriatal TSPO IL-6", cli.brain.research_engine, allow_network=False)
        self.assertEqual(len(nmap["nodes"]), 9)
        self.assertFalse(nmap["clinical_action_authorized"])

        for cmd, expected in (
            ("/onco atlas", "216-Slot FIPS-203 ML-KEM Exact: True"),
            ("/biomech 1.5", "SymPy Exact Pediatric Law"),
            ("/neuromap TSPO", "MNI152 SAGITTAL RADAR"),
            ("/mission", "3-PILLAR MEDICAL R&D COMMAND BRIEF"),
        ):
            keep, out_lines = cli.handle_slash(cmd, color=False)
            self.assertTrue(keep)
            self.assertIn(expected, "\n".join(out_lines or []))


if __name__ == "__main__":
    unittest.main()
