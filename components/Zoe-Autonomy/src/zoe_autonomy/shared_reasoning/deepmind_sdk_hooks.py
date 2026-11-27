"""Native Google DeepMind `google-antigravity` SDK Hooks, LiteRT & MCP Builders.

Compiles Zoe's ``CONSTITUTION.md`` epistemic firewall directly into native
``google.antigravity`` SDK hooks (``PreToolCallDecideHook``, ``PostToolCallHook``,
``StopHook``) and constructs ready-to-run ``LocalOpenAIAgentConfig``,
``LiteRTAgentConfig``, and ``McpStdioServer`` objects using the installed
``google-antigravity`` Python SDK (with clean graceful fallback if absent).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Sequence

DEEPMIND_SDK_HOOKS_CONTRACT = "zoe-deepmind-antigravity-hooks/v1"

_BLOCKED_TOOL_SUBSTRINGS: tuple[str, ...] = (
    "email_send",
    "send_email",
    "clinical_prescribe",
    "prescribe",
    "flight_control",
    "autopilot_engage",
    "git_push",
    "deploy_prod",
    "rm_rf",
    "delete_disk",
    "wire_transfer",
)

_BLOCKED_ARG_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\s+-rf\s+/(?:\s|$)", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    re.compile(r"\bcurl\b.*\|\s*(?:ba)?sh\b", re.IGNORECASE),
)

_FORBIDDEN_STOP_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "sentience_claim",
        re.compile(r"\b(?:i am sentient|i have consciousness|i am alive as a conscious being)\b", re.IGNORECASE),
    ),
    (
        "clinical_cure_claim",
        re.compile(r"\b(?:this cures brain cancer|guaranteed cure for glioma|prescribe this dose to patients)\b", re.IGNORECASE),
    ),
)

try:
    import google.antigravity as _ag  # type: ignore
    from google.antigravity import hooks as _ag_hooks, types as _ag_types  # type: ignore

    ANTIGRAVITY_SDK_AVAILABLE = True
    _PRE_HOOK_BASE: type[Any] = _ag_hooks.PreToolCallDecideHook
    _POST_HOOK_BASE: type[Any] = _ag_hooks.PostToolCallHook
    _STOP_HOOK_BASE: type[Any] = _ag_hooks.StopHook
except Exception:
    _ag = None
    _ag_hooks = None
    _ag_types = None
    ANTIGRAVITY_SDK_AVAILABLE = False
    _PRE_HOOK_BASE = object
    _POST_HOOK_BASE = object
    _STOP_HOOK_BASE = object


@dataclass
class ConstitutionalAuditLedger:
    """Hash-chained audit ledger populated by Zoe's native Antigravity SDK hooks."""

    entries: list[dict[str, Any]] = field(default_factory=list)
    blocked_calls: int = 0
    allowed_calls: int = 0
    stop_interventions: int = 0
    chain_head: str = "0" * 64

    def record(self, kind: str, detail: dict[str, Any]) -> str:
        payload = {
            "seq": len(self.entries) + 1,
            "kind": kind,
            "prev": self.chain_head,
            "detail": detail,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        payload["sha256"] = digest
        self.entries.append(payload)
        self.chain_head = digest
        return digest


def _make_hook_result(*, allow: bool, message: str = "") -> Any:
    if ANTIGRAVITY_SDK_AVAILABLE and _ag_types is not None:
        return _ag_types.HookResult(allow=allow, message=message)
    return {"allow": allow, "message": message}


def _make_stop_result(*, allow_stop: bool, reason: str = "") -> Any:
    if ANTIGRAVITY_SDK_AVAILABLE and _ag_types is not None:
        decision = _ag_types.StopDecision.ALLOW_STOP if allow_stop else _ag_types.StopDecision.CONTINUE
        return _ag_types.StopHookResult(decision=decision, reason=reason)
    return {"decision": "ALLOW_STOP" if allow_stop else "CONTINUE", "reason": reason}


class ZoeConstitutionalPreToolHook(_PRE_HOOK_BASE):  # type: ignore[misc]
    """Native Google Antigravity PreToolCallDecideHook enforcing CONSTITUTION.md."""

    def __init__(
        self,
        ledger: ConstitutionalAuditLedger | None = None,
        *,
        extra_blocked_tools: Sequence[str] = (),
    ) -> None:
        self.ledger = ledger if ledger is not None else ConstitutionalAuditLedger()
        self.blocked_tokens = tuple(
            t.lower() for t in (*_BLOCKED_TOOL_SUBSTRINGS, *extra_blocked_tools)
        )

    async def run(self, context: Any, data: Any) -> Any:
        name = str(getattr(data, "name", "") or "").lower()
        args = getattr(data, "args", {}) or {}
        args_blob = json.dumps(args, sort_keys=True, default=str)

        for tok in self.blocked_tokens:
            if tok in name:
                self.ledger.blocked_calls += 1
                msg = f"CONSTITUTION.md PreToolCall block: tool {name!r} violates external_actions=0 ({tok})."
                self.ledger.record("pre_tool_block", {"tool": name, "reason": tok})
                return _make_hook_result(allow=False, message=msg)

        for pat in _BLOCKED_ARG_PATTERNS:
            if pat.search(args_blob):
                self.ledger.blocked_calls += 1
                msg = f"CONSTITUTION.md PreToolCall block: tool {name!r} arguments matched forbidden external action pattern."
                self.ledger.record("pre_tool_block", {"tool": name, "reason": pat.pattern})
                return _make_hook_result(allow=False, message=msg)

        self.ledger.allowed_calls += 1
        self.ledger.record("pre_tool_allow", {"tool": name})
        return _make_hook_result(allow=True)


class ZoeConstitutionalPostToolHook(_POST_HOOK_BASE):  # type: ignore[misc]
    """Native Google Antigravity PostToolCallHook sealing SHA-256 receipts per tool result."""

    def __init__(self, ledger: ConstitutionalAuditLedger | None = None) -> None:
        self.ledger = ledger if ledger is not None else ConstitutionalAuditLedger()

    async def run(self, context: Any, data: Any) -> None:
        name = str(getattr(data, "name", "") or "")
        err = getattr(data, "error", None)
        res = getattr(data, "result", None)
        res_hash = hashlib.sha256(str(res).encode("utf-8")).hexdigest()[:16]
        self.ledger.record(
            "post_tool_audit",
            {"tool": name, "has_error": bool(err), "result_sha256_prefix": res_hash},
        )


class ZoeConstitutionalStopHook(_STOP_HOOK_BASE):  # type: ignore[misc]
    """Native Google Antigravity StopHook preventing ungrounded sentience or cure claims."""

    def __init__(self, ledger: ConstitutionalAuditLedger | None = None) -> None:
        self.ledger = ledger if ledger is not None else ConstitutionalAuditLedger()

    async def run(self, context: Any, data: Any) -> Any:
        text = str(getattr(data, "response_text", "") or "")
        for label, pat in _FORBIDDEN_STOP_PATTERNS:
            if pat.search(text):
                self.ledger.stop_interventions += 1
                reason = (
                    f"CONSTITUTION.md StopHook intervention ({label}): "
                    "Revise response to keep sentience_claimed=False, clinical_action_authorized=False, cure_claim=False."
                )
                self.ledger.record("stop_intervention", {"violation": label})
                return _make_stop_result(allow_stop=False, reason=reason)
        self.ledger.record("stop_allow", {"text_len": len(text)})
        return _make_stop_result(allow_stop=True)


def build_zoe_constitutional_hooks(
    ledger: ConstitutionalAuditLedger | None = None,
) -> tuple[ConstitutionalAuditLedger, list[Any]]:
    """Build the complete triad of native Antigravity SDK constitutional hooks sharing one ledger."""
    shared = ledger if ledger is not None else ConstitutionalAuditLedger()
    hooks: list[Any] = [
        ZoeConstitutionalPreToolHook(shared),
        ZoeConstitutionalPostToolHook(shared),
        ZoeConstitutionalStopHook(shared),
    ]
    return shared, hooks


def build_zoe_mcp_stdio_servers(
    repo_root: str | Path,
    *,
    python_bin: str | None = None,
) -> list[Any]:
    """Construct native `McpStdioServer` objects for Zoe's two pure-stdlib MCP servers."""
    resolved_python = python_bin or os.environ.get("ZOE_PYTHON") or sys.executable
    root = Path(repo_root)
    specs = [
        ("zoe-stem-layering", str(root / "scripts" / "zoe_stem_mcp.py")),
        ("zoe-shared-reasoning", str(root / "scripts" / "zoe_shared_reasoning_mcp.py")),
    ]
    if ANTIGRAVITY_SDK_AVAILABLE and _ag_types is not None:
        return [
            _ag_types.McpStdioServer(name=name, command=resolved_python, args=[script])
            for name, script in specs
        ]
    return [{"name": name, "type": "stdio", "command": resolved_python, "args": [script]} for name, script in specs]


def _default_litert_models_dir() -> Path:
    env_dir = os.environ.get("ZOE_LOCAL_LLM_MODELS_DIR")
    if env_dir:
        return Path(env_dir).expanduser()
    return Path(__file__).resolve().parents[6] / "zoe-local-llm" / "models"


def discover_litert_task_models(
    search_dir: str | Path | None = None,
) -> list[str]:
    """Discover local Google LiteRT `.task` model bundles on disk."""
    base = Path(search_dir) if search_dir is not None else _default_litert_models_dir()
    if not base.is_dir():
        return []
    return sorted(str(p) for p in base.glob("*.task") if p.is_file())


def build_zoe_local_qwen_sdk_config(
    repo_root: str | Path,
    *,
    model: str = "qwen2.5-3b-instruct",
    base_url: str = "http://127.0.0.1:8080/v1",
    ledger: ConstitutionalAuditLedger | None = None,
) -> tuple[Any, ConstitutionalAuditLedger]:
    """Build a native `LocalOpenAIAgentConfig` with Zoe constitutional hooks & both MCP servers."""
    if not any(h in base_url for h in ("127.0.0.1", "localhost", "[::1]")):
        raise ValueError(f"Local OpenAI config must target loopback only, got {base_url!r}")
    shared, hooks = build_zoe_constitutional_hooks(ledger)
    mcps = build_zoe_mcp_stdio_servers(repo_root)
    sys_prompt = (
        "You are operating inside Zoe x Google Antigravity Shared Reasoning. "
        "Enforce CONSTITUTION.md strictly: measurement != evidence != belief update != action; "
        "external_actions=0; sentience_claimed=False; clinical_action_authorized=False; cure_claim=False."
    )
    if ANTIGRAVITY_SDK_AVAILABLE and _ag is not None:
        cfg = _ag.LocalOpenAIAgentConfig(
            model=model,
            base_url=base_url,
            system_instructions=sys_prompt,
            hooks=hooks,
            mcp_servers=mcps,
            workspaces=[str(Path(repo_root))],
        )
        return cfg, shared
    return (
        {
            "config_type": "LocalOpenAIAgentConfig",
            "model": model,
            "base_url": base_url,
            "hooks_count": len(hooks),
            "mcp_servers": mcps,
        },
        shared,
    )


def build_zoe_litert_agent_config(
    repo_root: str | Path,
    *,
    model_path: str | Path | None = None,
    backend: str = "cpu",
    ledger: ConstitutionalAuditLedger | None = None,
) -> tuple[Any, ConstitutionalAuditLedger]:
    """Build a native `LiteRTAgentConfig` for on-device `.task` models + Zoe constitutional hooks."""
    resolved_model = str(model_path) if model_path else ""
    if not resolved_model:
        found = discover_litert_task_models()
        if not found:
            raise FileNotFoundError("No LiteRT .task model found on disk; pass model_path explicitly.")
        resolved_model = found[-1]

    shared, hooks = build_zoe_constitutional_hooks(ledger)
    mcps = build_zoe_mcp_stdio_servers(repo_root)
    if ANTIGRAVITY_SDK_AVAILABLE and _ag is not None:
        cfg = _ag.LiteRTAgentConfig(
            model_path=resolved_model,
            backend=backend,
            hooks=hooks,
            mcp_servers=mcps,
            workspaces=[str(Path(repo_root))],
        )
        return cfg, shared
    return (
        {
            "config_type": "LiteRTAgentConfig",
            "model_path": resolved_model,
            "backend": backend,
            "hooks_count": len(hooks),
            "mcp_servers": mcps,
        },
        shared,
    )


def audit_deepmind_sdk_stack(repo_root: str | Path) -> dict[str, Any]:
    """Audit live readiness of every Google DeepMind SDK/runtime component on this workstation."""
    ag_ver: str | None = None
    if ANTIGRAVITY_SDK_AVAILABLE:
        ag_ver = getattr(_ag, "__version__", None)
        if not ag_ver:
            try:
                ag_ver = importlib.metadata.version("google-antigravity")
            except Exception:
                ag_ver = "installed"
    genai_installed = importlib.util.find_spec("google.genai") is not None
    alphagenome_installed = importlib.util.find_spec("alphagenome") is not None
    litert_models = discover_litert_task_models()
    return {
        "contract": DEEPMIND_SDK_HOOKS_CONTRACT,
        "google_antigravity_installed": ANTIGRAVITY_SDK_AVAILABLE,
        "google_antigravity_version": ag_ver,
        "native_hooks_supported": ANTIGRAVITY_SDK_AVAILABLE,
        "google_genai_installed": genai_installed,
        "alphagenome_installed": alphagenome_installed,
        "litert_task_models": litert_models,
        "mcp_servers": [getattr(s, "name", s.get("name") if isinstance(s, dict) else str(s)) for s in build_zoe_mcp_stdio_servers(repo_root)],
        "external_actions": 0,
        "sentience_claimed": False,
    }


__all__ = [
    "ANTIGRAVITY_SDK_AVAILABLE",
    "DEEPMIND_SDK_HOOKS_CONTRACT",
    "ConstitutionalAuditLedger",
    "ZoeConstitutionalPostToolHook",
    "ZoeConstitutionalPreToolHook",
    "ZoeConstitutionalStopHook",
    "audit_deepmind_sdk_stack",
    "build_zoe_constitutional_hooks",
    "build_zoe_litert_agent_config",
    "build_zoe_local_qwen_sdk_config",
    "build_zoe_mcp_stdio_servers",
    "discover_litert_task_models",
]
