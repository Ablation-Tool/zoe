#!/usr/bin/env python3
"""Pure-stdlib JSON-RPC 2.0 stdio MCP server for Zoe Cognitive Stem-Layering.

Exposes four focused tools on stdio (newline-delimited JSON-RPC; logs to stderr):
  - route_cognitive_stem
  - build_antigravity_sdk_config
  - eliza_studio_status
  - run_local_stem_turn
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List
from urllib import error as urlerror, request as urlrequest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ZOE_AUTONOMY_SRC = _REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if _ZOE_AUTONOMY_SRC.is_dir() and str(_ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(_ZOE_AUTONOMY_SRC))

from zoe_autonomy.stem_layering import (  # noqa: E402
    DEFAULT_LOCAL_QWEN_MODEL,
    DEFAULT_LOCAL_QWEN_URL,
    build_sdk_descriptor,
    constitutional_flags,
    probe_local_qwen,
    route_stem,
)
from zoe_autonomy.zoe_eliza import LocalLLMBridge, ZoeElizaEngine  # noqa: E402

SERVER_NAME = "zoe-stem-layering"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
ELIZA_STUDIO_URL = "http://127.0.0.1:8765"

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "route_cognitive_stem",
        "description": (
            "Route a task across Zoe's 5 Cognitive Stem-Layering tiers "
            "(gear1_eliza, local_qwen, flash_lite, flash, pro + /teamwork) "
            "using Kloster Operational Metacognition A_tau(p)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Task or prompt to route."},
                "offline_only": {"type": "boolean", "default": False},
                "privacy_sensitive": {"type": "boolean", "default": False},
                "files_count": {"type": "integer", "minimum": 0, "default": 1},
                "multi_file": {"type": "boolean", "default": False},
                "probe_local": {"type": "boolean", "default": False},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "build_antigravity_sdk_config",
        "description": (
            "Construct or validate an Antigravity SDK config descriptor "
            "(GeminiModelOptions with ThinkingLevel or LocalOpenAIAgentConfig.lightweight() "
            "for Qwen2.5-3B on 127.0.0.1:8080). Lazy-imports google.antigravity if installed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "tier": {
                    "type": "string",
                    "enum": ["gear1_eliza", "local_qwen", "flash_lite", "flash", "pro"],
                },
                "thinking_level": {
                    "type": ["string", "null"],
                    "enum": ["minimal", "low", "medium", "high", "xhigh", None],
                    "default": None,
                },
            },
            "required": ["tier"],
        },
    },
    {
        "name": "eliza_studio_status",
        "description": (
            "Loopback health probe of local llama-server (127.0.0.1:8080/v1/models) "
            "and Eliza-GEM Studio (127.0.0.1:8765/api/status)."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "run_local_stem_turn",
        "description": (
            "Execute a strictly loopback zero-cloud-token conversational turn via "
            "LocalLLMBridge (127.0.0.1:8080) or ZoeElizaEngine Gear 1 fallback."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "User message for local execution."},
                "gear": {
                    "type": "string",
                    "enum": ["auto", "gear1", "gear2", "local_qwen"],
                    "default": "auto",
                },
                "state_dir": {
                    "type": ["string", "null"],
                    "description": "Optional override directory for Zoe Eliza session state.",
                    "default": None,
                },
            },
            "required": ["prompt"],
        },
    },
]


def _get_loopback_json(url: str, timeout_sec: float = 0.8) -> Dict[str, Any]:
    req = urlrequest.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with urlrequest.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"available": True, "url": url, "data": data}
    except (urlerror.URLError, TimeoutError, ValueError, OSError) as exc:
        return {"available": False, "url": url, "reason": str(exc)}


def tool_route_cognitive_stem(args: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(args.get("prompt") or "")
    raw_fc = args.get("files_count", 1)
    if isinstance(raw_fc, bool):
        raise ValueError("files_count must be a nonnegative integer, not bool")
    files_count = int(raw_fc)
    decision = route_stem(
        prompt,
        offline_only=bool(args.get("offline_only", False)),
        privacy_sensitive=bool(args.get("privacy_sensitive", False)),
        files_count=files_count,
        multi_file=bool(args.get("multi_file", False)),
        probe_local=bool(args.get("probe_local", False)),
    )
    return decision.to_dict()


def tool_build_antigravity_sdk_config(args: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(args.get("tier") or "")
    thinking_level = args.get("thinking_level")
    if isinstance(thinking_level, str):
        normalized_level = thinking_level.strip().lower()
        alias_map = {
            "extra_high": "xhigh",
            "x_high": "xhigh",
        }
        thinking_level = alias_map.get(normalized_level, normalized_level)
    descriptor = build_sdk_descriptor(tier, thinking_level=thinking_level)

    sdk_installed = False
    sdk_payload: Dict[str, Any] | None = None
    try:
        from google.antigravity.connections.local.local_openai_connection_config import (  # type: ignore[import-not-found]
            LocalOpenAIAgentConfig,
        )
        from google.antigravity.models import GeminiModelOptions, ThinkingLevel  # type: ignore[import-not-found]

        sdk_installed = True
        if tier == "local_qwen":
            cfg = LocalOpenAIAgentConfig(
                model=DEFAULT_LOCAL_QWEN_MODEL,
                base_url=f"{DEFAULT_LOCAL_QWEN_URL}/v1",
            ).lightweight()
            sdk_payload = {"constructed_type": type(cfg).__name__, "model": cfg.model, "base_url": cfg.base_url}
        elif tier in {"flash_lite", "flash", "pro"}:
            lvl_str = descriptor["thinking_level"]
            opts = GeminiModelOptions(thinking_level=ThinkingLevel(lvl_str))
            sdk_payload = {"constructed_type": type(opts).__name__, "thinking_level": str(opts.thinking_level)}
        else:
            sdk_payload = {"constructed_type": "ZoeElizaEngine", "gear": "gear1"}
    except ImportError:
        sdk_installed = False

    return {
        "sdk_installed": sdk_installed,
        "sdk_payload": sdk_payload,
        "config_descriptor": descriptor,
        "constitutional": constitutional_flags(cloud_tokens_used=0),
    }


def tool_eliza_studio_status(_args: Dict[str, Any]) -> Dict[str, Any]:
    qwen_probe = probe_local_qwen(DEFAULT_LOCAL_QWEN_URL, timeout_sec=0.8)
    studio_probe = _get_loopback_json(f"{ELIZA_STUDIO_URL}/api/status", timeout_sec=0.8)
    studio_summary: Dict[str, Any] | None = None
    if studio_probe["available"] and isinstance(studio_probe.get("data"), dict):
        d = studio_probe["data"]
        studio_summary = {
            "contract": d.get("contract"),
            "default_gear": d.get("default_gear"),
            "indexed_sources": d.get("indexed_sources"),
            "indexed_chunks": d.get("indexed_chunks"),
        }
    return {
        "loopback_only": True,
        "llama_server": qwen_probe,
        "eliza_studio": {
            "available": studio_probe["available"],
            "endpoint": studio_probe["url"],
            "summary": studio_summary,
            "reason": studio_probe.get("reason"),
        },
        "constitutional": constitutional_flags(cloud_tokens_used=0),
    }


def tool_run_local_stem_turn(args: Dict[str, Any]) -> Dict[str, Any]:
    prompt = str(args.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt must not be empty")
    gear_arg = str(args.get("gear") or "auto").lower()
    if gear_arg not in {"auto", "gear1", "gear2", "local_qwen"}:
        raise ValueError(f"invalid gear {gear_arg!r}; expected auto|gear1|gear2|local_qwen")

    if gear_arg == "gear1":
        resolved_gear = "gear1"
    elif gear_arg in {"gear2", "local_qwen"}:
        resolved_gear = "gear2"
    else:
        qwen = probe_local_qwen(DEFAULT_LOCAL_QWEN_URL, timeout_sec=0.6)
        resolved_gear = "gear2" if qwen["available"] else "gear1"

    state_dir = args.get("state_dir") or os.environ.get("ZOE_ELIZA_STATE_DIR")
    bridge = LocalLLMBridge(llama_server_url=DEFAULT_LOCAL_QWEN_URL, preferred_model=DEFAULT_LOCAL_QWEN_MODEL)
    engine = ZoeElizaEngine(
        _REPO_ROOT,
        state_dir=state_dir,
        default_gear=resolved_gear,
        llm_bridge=bridge,
    )
    res = engine.respond(prompt, gear=resolved_gear)
    return {
        "reply": res["reply"],
        "mode": res["mode"],
        "gear_requested": res["gear_requested"],
        "gear_used": res["gear_used"],
        "gear2_note": res.get("gear2_note"),
        "latency_ms": res["latency_ms"],
        "metacognition": res["metacognition"],
        "citations": [{"citation": c["citation"], "score": c["score"]} for c in res.get("citations", [])],
        "cloud_tokens_used": 0,
        "external_actions": 0,
        "constitutional": constitutional_flags(cloud_tokens_used=0),
    }


_TOOL_DISPATCH = {
    "route_cognitive_stem": tool_route_cognitive_stem,
    "build_antigravity_sdk_config": tool_build_antigravity_sdk_config,
    "eliza_studio_status": tool_eliza_studio_status,
    "run_local_stem_turn": tool_run_local_stem_turn,
}


def handle_request(req: Dict[str, Any]) -> Dict[str, Any] | None:
    req_id = req.get("id")
    method = req.get("method")

    # Notifications have no id and expect no response.
    if req_id is None:
        return None

    def ok(result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, message: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    raw_params = req.get("params")
    if raw_params is None:
        params: Dict[str, Any] = {}
    elif not isinstance(raw_params, dict):
        return err(-32602, "params must be a JSON object")
    else:
        params = raw_params

    if method == "initialize":
        proto = str(params.get("protocolVersion") or DEFAULT_PROTOCOL_VERSION)
        return ok(
            {
                "protocolVersion": proto,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        )
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        raw_arguments = params.get("arguments")
        arguments = {} if raw_arguments is None else raw_arguments
        if name not in _TOOL_DISPATCH:
            return err(-32602, f"Unknown tool: {name!r}")
        if not isinstance(arguments, dict):
            return err(-32602, "Tool arguments must be a JSON object")
        try:
            payload = _TOOL_DISPATCH[name](arguments)
            return ok(
                {
                    "content": [{"type": "text", "text": json.dumps(payload, indent=2, sort_keys=True)}],
                    "structuredContent": payload,
                    "isError": False,
                }
            )
        except Exception as exc:  # noqa: BLE001
            error_payload = {"error": str(exc)}
            return ok(
                {
                    "content": [{"type": "text", "text": json.dumps(error_payload, indent=2)}],
                    "structuredContent": error_payload,
                    "isError": True,
                }
            )
    return err(-32601, f"Method not found: {method!r}")


def serve_stdio() -> int:
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        raw = line.strip()
        if not raw:
            continue
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as exc:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"Parse error: {exc}"}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue
        if not isinstance(req, dict):
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue
        try:
            resp = handle_request(req)
        except Exception as exc:  # noqa: BLE001
            req_id = req.get("id")
            if req_id is not None:
                resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32603, "message": f"Internal error: {exc}"}}
            else:
                resp = None
        if resp is not None:
            sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    print(f"[{SERVER_NAME}] starting stdio MCP server", file=sys.stderr)
    raise SystemExit(serve_stdio())
