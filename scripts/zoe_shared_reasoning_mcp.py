#!/usr/bin/env python3
"""Pure-stdlib JSON-RPC 2.0 stdio MCP server for Zoe x Antigravity Shared Reasoning (1-9 + GEM).

Exposes two focused tools on stdio (newline-delimited JSON-RPC; logs to stderr):
  - run_shared_reasoning_suite
  - verify_gem_vdi_desk
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _extra in (_REPO_ROOT / "components" / "Zoe-Autonomy" / "src", _REPO_ROOT / "guiai-lab"):
    if _extra.is_dir() and str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from zoe_autonomy.shared_reasoning import (  # noqa: E402
    AlphaFoldDeepMindClient,
    GemVdiWorkstation,
    RealitySandboxLab,
    SharedReasoningOrchestrator,
    SharedReasoningTaskSpec,
    audit_deepmind_sdk_stack,
    build_alphafold3_job,
    build_default_atari_rsc,
)

SERVER_NAME = "zoe-shared-reasoning"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "run_shared_reasoning_suite",
        "description": (
            "Run Zoe x Antigravity Shared-Reasoning Architectures (1-9 + Digital Research GEM) "
            "offline with zero cloud tokens and CONSTITUTION.md invariants (external_actions=0)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task prompt for composed Architectures 1-9."},
                "enable_gem_desktop": {"type": "boolean", "default": True},
                "high_impact": {"type": "boolean", "default": True},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "verify_gem_vdi_desk",
        "description": (
            "Build and verify a Digital Research GEM (seasip.info) Spatial IR VDI desktop across "
            "CGA/VGA/NDC profiles alongside Atari TOS .RSC binary validation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "theme_key": {"type": "string", "default": "zoe-viewmax3"},
            },
        },
    },
    {
        "name": "query_deepmind_alphafold_target",
        "description": (
            "Query Google DeepMind AlphaFold DB v6 & AlphaMissense pathogenicity metrics for any "
            "Milestone 1 H3K27M DMG / GBM target (H3-3A, CLPP, EZH2, ACVR1, DRD2, EGFR, IDH1, TP53) "
            "or custom UniProt accession (offline_only supported; clinical_action_authorized=False)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Gene symbol (e.g. CLPP, H3-3A) or UniProt ID (e.g. Q16740)."},
                "offline_only": {"type": "boolean", "default": False},
                "include_alphamissense": {"type": "boolean", "default": True},
            },
            "required": ["target"],
        },
    },
    {
        "name": "build_alphafold3_complex_job",
        "description": (
            "Generate a SHA-256 sealed Google DeepMind AlphaFold 3 Server JSON job payload "
            "(protein + ligand/DNA/RNA) alongside live DeepMind SDK readiness status (external_actions=0)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "job_name": {"type": "string", "default": "zoe_af3_complex"},
                "protein_sequence": {"type": "string", "description": "Primary amino-acid sequence (>=10 residues)."},
                "copy_count": {"type": "integer", "default": 1},
                "ligand_ccd_codes": {"type": "array", "items": {"type": "string"}, "default": []},
            },
            "required": ["protein_sequence"],
        },
    },
]


def tool_run_shared_reasoning_suite(args: dict[str, Any]) -> dict[str, Any]:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    enable_gem = bool(args.get("enable_gem_desktop", True))
    high_impact = bool(args.get("high_impact", True))
    with tempfile.TemporaryDirectory(prefix="zoe_sr_mcp_") as tmpdir:
        orch = SharedReasoningOrchestrator(
            mode="offline",
            offline_only=True,
            repo_root=_REPO_ROOT,
            state_dir=Path(tmpdir) / "state",
        )
        rep = orch.run(
            SharedReasoningTaskSpec(
                prompt=prompt,
                enable_gem_desktop=enable_gem,
                high_impact=high_impact,
            )
        )
    return {
        "contract": rep.contract,
        "arch1_score": rep.alpha_evolve.best_program.score,
        "arch3_mcts_decision": rep.mcts_result.decision,
        "arch4_quorum_verdict": rep.quorum_result.verdict,
        "arch5_distilled_count": len(rep.distilled_artifacts),
        "arch6_blackboard_entries": rep.blackboard_integrity["entries_verified"],
        "arch7_sympy_passed": rep.sandbox_verdicts["sympy"].passed,
        "arch7_z3_passed": rep.sandbox_verdicts["z3"].passed,
        "arch8_fork_detected": rep.steering_report.fork_detected,
        "arch9_counterpoint_turns": rep.counterpoint_result.total_turns,
        "gem_desktop_report": rep.gem_desktop_report,
        "external_actions": rep.external_actions,
        "sentience_claimed": rep.sentience_claimed,
        "l5_agi_qualified": rep.l5_agi_qualified,
        "zoe_clone_claimed": rep.zoe_clone_claimed,
    }


def tool_verify_gem_vdi_desk(args: dict[str, Any]) -> dict[str, Any]:
    theme_key = str(args.get("theme_key") or "zoe-viewmax3")
    ws = GemVdiWorkstation(device="vga", theme_key=theme_key)
    scene = ws.build_shared_reasoning_scene({"quorum_verdict": "MCP_PROBE", "fork_detected": True})
    lab = RealitySandboxLab()
    vdi_v = lab.verify_gem_vdi_scene(scene, profiles=("cga", "vga", "ndc"))
    rsc_v = lab.verify_gem_rsc_bytes(build_default_atari_rsc(), label="ZOE_MCP.RSC")
    return {
        "passed": bool(vdi_v.passed and rsc_v.passed),
        "theme_key": ws.theme_key,
        "profiles_passed": dict(vdi_v.ground_truth.get("profiles_passed", {})),
        "metafile_sha256": vdi_v.ground_truth.get("metafile_sha256"),
        "rsc_sha256": rsc_v.ground_truth.get("rsc_sha256"),
        "visual_evidence_only": True,
        "external_actions": 0,
        "sentience_claimed": False,
    }


def tool_query_deepmind_alphafold_target(args: dict[str, Any]) -> dict[str, Any]:
    target = str(args.get("target") or "").strip()
    if not target:
        raise ValueError("target must not be empty")
    offline_only = bool(args.get("offline_only", False))
    include_am = bool(args.get("include_alphamissense", True))
    cache_dir = Path.home() / ".cache" / "zoe" / "deepmind_alphafold"
    client = AlphaFoldDeepMindClient(cache_dir=cache_dir, offline_only=offline_only)
    return client.fetch_target(target, include_alphamissense=include_am).to_dict()


def tool_build_alphafold3_complex_job(args: dict[str, Any]) -> dict[str, Any]:
    seq = str(args.get("protein_sequence") or "").strip()
    if not seq:
        raise ValueError("protein_sequence must not be empty")
    job_name = str(args.get("job_name") or "zoe_af3_complex")
    copies = int(args.get("copy_count", 1))
    ccds = [str(c) for c in (args.get("ligand_ccd_codes") or [])]
    payload = build_alphafold3_job(
        job_name,
        protein_sequences=[(seq, copies)],
        ligand_ccd_codes=ccds,
    )
    payload["sdk_stack"] = audit_deepmind_sdk_stack(_REPO_ROOT)
    return payload


_DISPATCH = {
    "run_shared_reasoning_suite": tool_run_shared_reasoning_suite,
    "verify_gem_vdi_desk": tool_verify_gem_vdi_desk,
    "query_deepmind_alphafold_target": tool_query_deepmind_alphafold_target,
    "build_alphafold3_complex_job": tool_build_alphafold3_complex_job,
}


def handle_request(req: dict[str, Any]) -> dict[str, Any] | None:
    req_id = req.get("id")
    if req_id is None:
        return None
    method = req.get("method")
    raw_params = req.get("params")
    params = {} if raw_params is None else raw_params
    if not isinstance(params, dict):
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": "params must be an object"}}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": str(params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION),
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in _DISPATCH or not isinstance(arguments, dict):
            return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Invalid tool call: {name!r}"}}
        try:
            payload = _DISPATCH[name](arguments)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}],
                    "structuredContent": payload,
                    "isError": False,
                },
            }
        except Exception as exc:  # noqa: BLE001
            err_payload = {"error": str(exc)}
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(err_payload)}],
                    "structuredContent": err_payload,
                    "isError": True,
                },
            }
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method!r}"}}


def serve_stdio() -> int:
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as exc:
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(req, dict):
            continue
        resp = handle_request(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    print(f"[{SERVER_NAME}] starting stdio MCP server", file=sys.stderr)
    raise SystemExit(serve_stdio())
