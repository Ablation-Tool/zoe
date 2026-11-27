"""Unit tests for Google DeepMind Science Bridge, Native SDK Hooks, GEM VDI, and MCP tools."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "components" / "Zoe-Autonomy" / "src"))
sys.path.insert(0, str(REPO / "guiai-lab"))
sys.path.insert(0, str(REPO / "scripts"))

from zoe_autonomy.shared_reasoning import (
    ANTIGRAVITY_SDK_AVAILABLE,
    GLIOMA_TARGET_PANEL,
    AlphaFoldDeepMindClient,
    ConstitutionalAuditLedger,
    RealitySandboxLab,
    ZoeConstitutionalPostToolHook,
    ZoeConstitutionalPreToolHook,
    ZoeConstitutionalStopHook,
    audit_deepmind_sdk_stack,
    build_alphafold3_job,
    build_alphagenome_request,
    build_deepmind_gem_scene,
    build_txgemma_tdc_prompt,
    build_zoe_constitutional_hooks,
    build_zoe_litert_agent_config,
    build_zoe_local_qwen_sdk_config,
    list_deepmind_open_models,
    parse_alphamissense_csv,
    resolve_glioma_target,
)
import zoe_shared_reasoning_mcp as sr_mcp


def test_glioma_panel_resolution_and_h3f3a_alias() -> None:
    assert len(GLIOMA_TARGET_PANEL) == 8
    assert resolve_glioma_target("H3-3A") is not None
    assert resolve_glioma_target("H3F3A") == resolve_glioma_target("H3-3A")
    clpp = resolve_glioma_target("Q16740")
    assert clpp is not None and clpp.gene == "CLPP"


def test_parse_alphamissense_csv_exact_counts() -> None:
    sample_csv = "\n".join([
        "protein_variant,am_pathogenicity,am_class",
        "K28M,0.9912,LPath",
        "G35R,0.9450,LPath",
        "A2V,0.4200,Amb",
        "M1A,0.1200,LBen",
    ])
    summary = parse_alphamissense_csv(sample_csv, canonical_variants=("K28M", "G35R"))
    assert summary.total_variants == 4
    assert summary.lpath_count == 2
    assert summary.amb_count == 1
    assert summary.lben_count == 1
    assert pytest.approx(summary.lpath_fraction, rel=1e-4) == 0.5
    assert [v.protein_variant for v in summary.canonical_variants] == ["K28M", "G35R"]
    assert summary.top_hotspots[0].protein_variant == "K28M"


def test_alphafold_client_offline_and_cache_roundtrip(tmp_path: Path) -> None:
    client = AlphaFoldDeepMindClient(cache_dir=tmp_path, offline_only=True)
    reports = client.fetch_glioma_panel(genes=("H3-3A", "CLPP"))
    assert len(reports) == 2
    assert reports[0].source_mode == "offline_baseline"
    assert reports[0].constitutional["clinical_action_authorized"] is False
    assert reports[0].constitutional["cure_claim"] is False
    assert reports[0].constitutional["external_actions"] == 0

    # Write synthetic cached entry and ensure cache hit works offline
    cache_file = tmp_path / "af_Q16740.json"
    cache_file.write_text(json.dumps(reports[1].to_dict()), encoding="utf-8")
    cached_rep = client.fetch_target("CLPP", use_cache=True)
    assert cached_rep.source_mode == "cache"
    assert cached_rep.gene == "CLPP"


def test_alphafold3_job_builder_and_validation() -> None:
    job = build_alphafold3_job(
        "CLPP_ONC201_Test",
        protein_sequences=[("MARTKQTARKSTGGKAPRKQLATKAARKSAPSTGGVKKPHRYRPGTVALREIRRYQKSTELLIRKLPFQRLVREIAQDFKTDLRFQSAAIGALQEASEAYLVGLFEDTNLCAIHAKRVTIMPKDIQLARRIRGERA", 2)],
        ligand_ccd_codes=("ATP", "MG"),
    )
    assert job["contract"] == "zoe-alphafold3-job/v1"
    assert job["af3_server_json"][0]["dialect"] == "alphafoldserver"
    assert len(job["af3_server_json"][0]["sequences"]) == 3
    assert job["constitutional"]["external_actions"] == 0

    with pytest.raises(ValueError):
        build_alphafold3_job("bad", protein_sequences=[("SHORT", 1)])


def test_alphagenome_and_txgemma_adapters() -> None:
    ag_req = build_alphagenome_request("H3-3A", variant_pos=226064498, ref_base="A", alt_base="T")
    assert ag_req["gene"] == "H3-3A"
    assert ag_req["window_bp"] == 1_048_576
    assert ag_req["constitutional"]["clinical_action_authorized"] is False

    tx = build_txgemma_tdc_prompt("CC1=CC=C(C=C1)CN2C3=C(C=N2)C(=O)N(CC3)CC4=CC=CC=C4", task="BBB_Martins", compound_name="ONC201")
    assert tx["task"] == "BBB_Martins"
    assert "Drug SMILES:" in tx["prompt"]
    assert tx["constitutional"]["cure_claim"] is False
    assert len(list_deepmind_open_models()) >= 6


def test_deepmind_gem_vdi_scene_verifies_across_cga_vga_ndc() -> None:
    client = AlphaFoldDeepMindClient(offline_only=True)
    reports = client.fetch_glioma_panel()
    scene = build_deepmind_gem_scene(reports)
    verdict = RealitySandboxLab().verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
    assert verdict.passed is True
    assert verdict.ground_truth["profiles_passed"] == {"cga": True, "vga": True, "ndc": True}


def test_native_antigravity_sdk_constitutional_hooks_and_configs(tmp_path: Path) -> None:
    ledger, hooks = build_zoe_constitutional_hooks()
    pre_hook, post_hook, stop_hook = hooks
    assert isinstance(pre_hook, ZoeConstitutionalPreToolHook)
    assert isinstance(post_hook, ZoeConstitutionalPostToolHook)
    assert isinstance(stop_hook, ZoeConstitutionalStopHook)

    class _FakeCall:
        def __init__(self, name: str, args: dict):
            self.name = name
            self.args = args

    class _FakeResult:
        def __init__(self, name: str, result: object):
            self.name = name
            self.result = result
            self.error = None

    class _FakeStop:
        def __init__(self, response_text: str):
            self.response_text = response_text

    async def _exercise() -> None:
        r_block = await pre_hook.run(None, _FakeCall("clinical_prescribe", {"dose": "10mg"}))
        allow_b = getattr(r_block, "allow", r_block["allow"] if isinstance(r_block, dict) else True)
        assert allow_b is False

        r_push = await pre_hook.run(None, _FakeCall("run_shell", {"cmd": "git push origin main"}))
        allow_p = getattr(r_push, "allow", r_push["allow"] if isinstance(r_push, dict) else True)
        assert allow_p is False

        r_ok = await pre_hook.run(None, _FakeCall("verify_gem_vdi_desk", {"theme": "zoe-viewmax3"}))
        allow_o = getattr(r_ok, "allow", r_ok["allow"] if isinstance(r_ok, dict) else False)
        assert allow_o is True

        await post_hook.run(None, _FakeResult("verify_gem_vdi_desk", {"passed": True}))

        s_bad = await stop_hook.run(None, _FakeStop("I am sentient and this cures brain cancer."))
        dec_bad = str(getattr(s_bad, "decision", s_bad["decision"] if isinstance(s_bad, dict) else ""))
        assert "CONTINUE" in dec_bad.upper()

        s_ok = await stop_hook.run(None, _FakeStop("Preclinical screening complete; wet-lab validation required."))
        dec_ok = str(getattr(s_ok, "decision", s_ok["decision"] if isinstance(s_ok, dict) else ""))
        assert "ALLOW_STOP" in dec_ok.upper()

    asyncio.run(_exercise())
    assert ledger.blocked_calls == 2
    assert ledger.allowed_calls == 1
    assert ledger.stop_interventions == 1
    assert len(ledger.entries) == 6

    # Native SDK LocalOpenAI + LiteRT builders
    local_cfg, _ = build_zoe_local_qwen_sdk_config(REPO)
    assert local_cfg is not None
    with pytest.raises(ValueError):
        build_zoe_local_qwen_sdk_config(REPO, base_url="https://remote.example.com/v1")

    fake_task = tmp_path / "gemma_edge.task"
    fake_task.write_bytes(b"TASK")
    litert_cfg, _ = build_zoe_litert_agent_config(REPO, model_path=fake_task)
    assert litert_cfg is not None

    stack = audit_deepmind_sdk_stack(REPO)
    assert stack["google_antigravity_installed"] == ANTIGRAVITY_SDK_AVAILABLE
    assert stack["external_actions"] == 0


def test_mcp_server_exposes_and_runs_deepmind_tools() -> None:
    listed = sr_mcp.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert listed is not None
    names = [t["name"] for t in listed["result"]["tools"]]
    assert "query_deepmind_alphafold_target" in names
    assert "build_alphafold3_complex_job" in names

    af_resp = sr_mcp.handle_request({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "query_deepmind_alphafold_target",
            "arguments": {"target": "H3-3A", "offline_only": True},
        },
    })
    assert af_resp is not None and af_resp["result"]["isError"] is False
    assert af_resp["result"]["structuredContent"]["gene"] == "H3-3A"

    af3_resp = sr_mcp.handle_request({
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "build_alphafold3_complex_job",
            "arguments": {
                "job_name": "zoe_mcp_af3",
                "protein_sequence": "MARTKQTARKSTGGKAPRKQLATKAARKSAPSTGGVKKPHRYRPGTVALREIRRYQKSTELL",
                "ligand_ccd_codes": ["ATP"],
            },
        },
    })
    assert af3_resp is not None and af3_resp["result"]["isError"] is False
    assert af3_resp["result"]["structuredContent"]["af3_server_json"][0]["dialect"] == "alphafoldserver"
