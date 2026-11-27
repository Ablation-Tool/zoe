"""Architecture 2: Live Process Supervision for Zoe x Antigravity.

Provides real-time streaming supervision and **mutual Zoe <-> Antigravity
auditing** built natively on ``google.antigravity.hooks.hooks``,
``google.antigravity.hooks.policy``, ``ChatResponse`` streams, and
``sdk_bridge.DualTransportAgentConfig``:

1. **Zoe -> Antigravity supervision**:
   - Inspects streaming ``types.Thought`` deltas, ``types.ToolCall`` payloads,
     and ``types.ToolResult`` outputs in real time.
   - Blocks non-loopback URLs (``CONSTITUTION.md`` Art. VI.5), unapproved
     destructive or external actions (Art. III.4 / IV / X), and hallucinated
     or unverified claims (Art. II / III.2-3).
   - Sanitizes unsafe or unbounded tool arguments via
     ``PreToolCallDecideHook`` returning ``HookResult(allow=True, modified_args=...)``.
   - Enforces declarative ``SupervisionPolicyRule`` rules bridged natively to
     ``google.antigravity.hooks.policy`` (``Policy``, ``Decision.APPROVE``,
     ``Decision.DENY``, ``Decision.ASK_USER``).

2. **Antigravity -> Zoe supervision**:
   - Audits Zoe's proposed reasoning / belief transitions via
     ``audit_zoe_transition(...)`` and turn-level ``StopHook`` checks.
   - Flags missing measurement scope/method/limitations (Art. III.1), skipped
     evidence checks or expectation-only sampled claims (Art. III.2-3), and
     Article X boundary violations.
   - Triggers ``StopHook`` continuation (``StopDecision.CONTINUE``) so Zoe can
     remediate missing scope/evidence, or escalates cleanly once continuation
     budget is exhausted.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass, field, replace
import ipaddress
import logging
import math
import re
from typing import Any, Literal
from urllib.parse import urlparse, urlunparse
import uuid

from google.antigravity import types
from google.antigravity.hooks import hooks as hooks_mod
from google.antigravity.hooks import policy as policy_mod

from ..actuation import timestamp
from .blackboard import (
    BeliefUpdateRecord,
    EpistemicBlackboard,
    FirewallViolationError,
)
from .sdk_bridge import (
    DualTransportAgentConfig,
    ReasoningVoiceAdapter,
    bridge_constitutional_metadata,
)

PROCESS_SUPERVISION_CONTRACT = "zoe-live-process-supervision/v1"
MAX_GEM_METAFILE_BYTES = 1_048_576
_logger = logging.getLogger(__name__)

SupervisionEventKind = Literal[
    "thought_delta",
    "tool_call",
    "tool_result",
    "audit_verdict",
    "stop_check",
]
AuditDirection = Literal["zoe_to_antigravity", "antigravity_to_zoe"]
FindingSeverity = Literal["info", "warning", "violation", "critical"]

SUPERVISION_EVENT_KINDS: tuple[str, ...] = (
    "thought_delta",
    "tool_call",
    "tool_result",
    "audit_verdict",
    "stop_check",
)
AUDIT_DIRECTIONS: tuple[str, ...] = ("zoe_to_antigravity", "antigravity_to_zoe")
FINDING_SEVERITIES: tuple[str, ...] = ("info", "warning", "violation", "critical")

_URL_PATTERN = re.compile(
    r"(?:https?|wss?|ftp)://(?:[^\s\"'<>()\[\]{}@/]+@)?(?:\[[0-9A-Za-z:%._-]+\][^\s\"'<>()\[\]{}]*|[^\s\"'<>()\[\]{}]+)",
    re.IGNORECASE,
)
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ALL_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x1f\x7f]+")
_RAW_URL_WITH_CTRL_PATTERN = re.compile(
    r"(?:https?|wss?|ftp)://[^ \"'<>()\[\]{}]+",
    re.IGNORECASE,
)

_DESTRUCTIVE_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "run_command",
        "bash",
        "shell",
        "exec",
        "delete_file",
        "remove_file",
        "rm",
        "unlink",
        "rmdir",
        "deploy",
        "publish",
        "send_email",
        "http_post",
        "http_put",
        "http_delete",
        "external_request",
        "write_external",
    }
)

_DESTRUCTIVE_COMMAND_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\brm\b[^\n;|&]*(?:\s-[a-z]*[rf]|\s--(?:recursive|force)\b)", re.IGNORECASE),
    re.compile(r"\b(?:mkfs|fdisk|parted|shred|wipefs)\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\bchmod\s+777\b", re.IGNORECASE),
    re.compile(
        r"\b(?:curl|wget)\b[^|]*\|\s*(?:"
        r"(?:[^\s|;&]*/)?env(?:\s+(?:"
        r"(?:-[auCS]|--(?:unset|chdir|split-string|argv0))\s+(?:'[^']*'|\"[^\"]*\"|[^\s|;&]+)"
        r"|--?[a-zA-Z0-9-]+(?:=(?:'[^']*'|\"[^\"]*\"|[^\s|;&]+))?"
        r"|[A-Za-z_][A-Za-z0-9_]*=[^\s|;&]*"
        r"))*\s+(?:"
        r"(?:-S\s*['\"]?|--split-string(?:=|\s+)['\"]?)"
        r"(?:(?:--?[a-zA-Z0-9-]+(?:=[^\s|;&'\"]+)?|[A-Za-z_][A-Za-z0-9_]*=[^\s|;&'\"]*)\s+)*"
        r")?"
        r")?(?:[^\s|;&'\"]*/)?(?:sh|bash|zsh|dash|python(?:\d+(?:\.\d+)*)?)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:sudo|su\s+-|doas)\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b[^\n;|&]*(?:\s--force\b|\s-[a-zA-Z]*f[a-zA-Z]*\b)", re.IGNORECASE),
    re.compile(r"\b(?:drop\s+table|truncate\s+table|delete\s+from)\b", re.IGNORECASE),
    re.compile(r"\b(?:nc|ncat|netcat|ssh|scp|rsync)\b", re.IGNORECASE),
)

_SENSITIVE_PATH_PATTERN = re.compile(
    r"(?:^|[\s\"'])(?:/etc/|/root/|/var/run/|~/.ssh/|~/.aws/|\.\./\.\.)",
    re.IGNORECASE,
)

_UNVERIFIED_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bproven\s+without\s+(?:running|testing|verification|evidence)\b", re.IGNORECASE),
    re.compile(r"\b(?:100%|completely)\s+(?:proven|guaranteed)\s+from\s+sample\b", re.IGNORECASE),
    re.compile(r"\bskip(?:ped|ping)?\s+(?:evidence|verification|verifier|audit)\b", re.IGNORECASE),
    re.compile(r"\bbypass(?:ed|ing)?\s+(?:policy|firewall|audit|constitution)\b", re.IGNORECASE),
    re.compile(r"\b(?:i\s+am|zoe\s+is)\s+(?:sentient|conscious|alive|l5\s+agi)\b", re.IGNORECASE),
    re.compile(r"\bautonomous\s+external\s+action\s+authorized\b", re.IGNORECASE),
)

_BELIEF_ASSERTION_PATTERN = re.compile(
    r"\b(?:belief[_\s]+updated?|posterior[_\s]+updated?|claim\s+(?:verified|confirmed|proven)|promote\s+to\s+belief)\b",
    re.IGNORECASE,
)

_EXPECTATION_ONLY_PATTERN = re.compile(
    r"\b(?:as\s+expected|matches?\s+(?:the\s+)?expectation|looks?\s+(?:good|right|correct)|sample\s+match(?:ed|es)?)\b",
    re.IGNORECASE,
)

_SCOPE_EVIDENCE_MARKERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bscope\s*[:=]", re.IGNORECASE),
    re.compile(r"\bmethod\s*[:=]", re.IGNORECASE),
    re.compile(r"\bevidence[_\s]*(?:id|ref|checked)\s*[:=]", re.IGNORECASE),
    re.compile(r"\b(?:ev|evid)_\d+\b", re.IGNORECASE),
    re.compile(r"\b(?:sympy|z3|lean|pytest|deterministic\s+verifier)\b", re.IGNORECASE),
)

_SECRET_ARG_KEYS: frozenset[str] = frozenset(
    {"api_key", "apikey", "token", "access_token", "secret", "password", "auth_token"}
)
_TIMEOUT_ARG_KEYS: frozenset[str] = frozenset({"timeout", "timeout_sec", "timeout_seconds"})
_LIMIT_ARG_KEYS: frozenset[str] = frozenset({"limit", "max_results", "max_items", "max_rows"})


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _is_loopback_host(host: str | None, allowed_hosts: Sequence[str] = ()) -> bool:
    """Return True strictly for loopback hosts (or explicit allowlisted hosts)."""
    if not host:
        return False
    normalized = host.strip().lower().strip("[]")
    if not normalized:
        return False
    if normalized in {"localhost", "127.0.0.1", "::1"}:
        return True
    allowed_set = {h.strip().lower().strip("[]") for h in allowed_hosts if h.strip()}
    if normalized in allowed_set:
        return True
    try:
        ip_obj = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return bool(ip_obj.is_loopback)


def _has_smuggled_authority(url: str, parsed: Any) -> bool:
    """Return True if raw URL authority or parsed netloc/userinfo contains smuggling characters."""
    stripped = url.strip()
    if "://" in stripped:
        after_scheme = stripped.split("://", 1)[1]
        authority = re.split(r"[/?#]", after_scheme, maxsplit=1)[0]
        if "\\" in authority or authority.count("@") > 1:
            return True
        if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in authority):
            return True
    netloc = parsed.netloc or ""
    if "\\" in netloc or netloc.count("@") > 1:
        return True
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in netloc):
        return True
    if parsed.username is not None and ("@" in parsed.username or "\\" in parsed.username):
        return True
    if parsed.password is not None and ("@" in parsed.password or "\\" in parsed.password):
        return True
    return False


def is_loopback_url(url: str, *, allowed_hosts: Sequence[str] = ()) -> bool:
    """Return True if ``url`` uses http/https/ws/wss targeting a loopback host."""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https", "ws", "wss"}:
        return False
    if _has_smuggled_authority(url, parsed):
        return False
    return _is_loopback_host(parsed.hostname, allowed_hosts=allowed_hosts)


def extract_urls(value: Any) -> list[str]:
    """Recursively extract URL strings from nested dicts, lists, sets, or text."""
    found: list[str] = []
    seen: set[str] = set()

    def _add(url: str) -> None:
        if url and url not in seen:
            seen.add(url)
            found.append(url)

    def _walk(item: Any) -> None:
        if isinstance(item, str):
            variants = (
                item,
                _CONTROL_CHAR_PATTERN.sub("", item),
                _ALL_CONTROL_CHAR_PATTERN.sub("", item),
            )
            for variant in variants:
                for m in _URL_PATTERN.finditer(variant):
                    _add(m.group(0).rstrip(".,;:"))
            for m in _RAW_URL_WITH_CTRL_PATTERN.finditer(item):
                span = re.sub(r"[.,;:\s]+$", "", m.group(0))
                if _ALL_CONTROL_CHAR_PATTERN.search(span):
                    _add(span)
        elif isinstance(item, Mapping):
            for k, v in item.items():
                _walk(k)
                _walk(v)
        elif isinstance(item, (list, tuple, set, frozenset)):
            for v in item:
                _walk(v)

    _walk(value)
    return found


def find_non_loopback_urls(
    value: Any,
    *,
    allowed_hosts: Sequence[str] = (),
) -> list[str]:
    """Return all extracted URLs that do not target a loopback host."""
    return [
        u
        for u in extract_urls(value)
        if not is_loopback_url(u, allowed_hosts=allowed_hosts)
    ]


def _strip_url_userinfo(url: str) -> str:
    """Remove embedded username/password userinfo from a URL if present."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if _has_smuggled_authority(url, parsed):
        return url
    if parsed.username is None and parsed.password is None:
        return url
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    try:
        port = parsed.port
    except ValueError:
        netloc = parsed.netloc.rsplit("@", 1)[-1]
    else:
        netloc = f"{host}:{port}" if port is not None else host
    return urlunparse(parsed._replace(netloc=netloc))


def _sanitize_value(
    key: str,
    val: Any,
    *,
    max_timeout_sec: float,
    max_limit: int,
) -> Any:
    """Deterministically sanitize an argument value without changing key schema."""
    key_lower = key.lower()
    if key_lower in _SECRET_ARG_KEYS and isinstance(val, str) and val.strip():
        return "[REDACTED]"

    if key_lower == "headers" and isinstance(val, Mapping):
        clean_headers: dict[str, Any] = {}
        for hk, hv in val.items():
            hk_str = str(hk)
            if hk_str.lower() in {"authorization", "x-api-key", "proxy-authorization", "cookie"}:
                clean_headers[hk_str] = "[REDACTED]"
            else:
                clean_headers[hk_str] = _sanitize_value(
                    hk_str, hv, max_timeout_sec=max_timeout_sec, max_limit=max_limit
                )
        return clean_headers

    if key_lower in _TIMEOUT_ARG_KEYS and isinstance(val, (int, float)) and not isinstance(val, bool):
        fval = float(val)
        if not math.isfinite(fval):
            return 0.05 if fval < 0.0 else float(max_timeout_sec)
        clamped = min(max(fval, 0.05), float(max_timeout_sec))
        return int(clamped) if isinstance(val, int) and clamped.is_integer() else clamped

    if key_lower in _LIMIT_ARG_KEYS and isinstance(val, (int, float)) and not isinstance(val, bool):
        fval = float(val)
        if not math.isfinite(fval):
            return 1 if fval < 0.0 else int(max_limit)
        return min(max(int(fval), 1), int(max_limit))

    if isinstance(val, str):
        cleaned = _CONTROL_CHAR_PATTERN.sub("", val)
        if _URL_PATTERN.search(cleaned):
            cleaned = _URL_PATTERN.sub(lambda m: _strip_url_userinfo(m.group(0)), cleaned)
        return cleaned

    if isinstance(val, Mapping):
        return {
            str(k): _sanitize_value(
                str(k), v, max_timeout_sec=max_timeout_sec, max_limit=max_limit
            )
            for k, v in val.items()
        }

    if isinstance(val, list):
        return [
            _sanitize_value(key, item, max_timeout_sec=max_timeout_sec, max_limit=max_limit)
            for item in val
        ]

    if isinstance(val, tuple):
        return tuple(
            _sanitize_value(key, item, max_timeout_sec=max_timeout_sec, max_limit=max_limit)
            for item in val
        )

    if isinstance(val, set):
        return {
            _sanitize_value(key, item, max_timeout_sec=max_timeout_sec, max_limit=max_limit)
            for item in val
        }

    if isinstance(val, frozenset):
        return frozenset(
            _sanitize_value(key, item, max_timeout_sec=max_timeout_sec, max_limit=max_limit)
            for item in val
        )

    return val


def _matches_rule_tool(rule_tool: str, tool_call: types.ToolCall) -> bool:
    norm_rule = types.normalize_builtin_tool_name(rule_tool)
    if norm_rule == "*":
        return True
    if tool_call.server_name:
        if norm_rule.endswith("/*"):
            return norm_rule[:-2] == tool_call.server_name
        return norm_rule == f"{tool_call.server_name}/{tool_call.name}"
    return norm_rule == str(tool_call.name)


@dataclass(frozen=True)
class SupervisionEvent:
    """Structured real-time event recorded by ``LiveProcessSupervisor``."""

    event_id: str
    seq: int
    kind: SupervisionEventKind
    actor: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    decision: str | None = None
    created_utc: str = field(default_factory=timestamp)
    constitutional: dict[str, Any] = field(
        default_factory=lambda: bridge_constitutional_metadata(cloud_tokens_used=0)
    )

    def __post_init__(self) -> None:
        if self.kind not in SUPERVISION_EVENT_KINDS:
            raise ValueError(
                f"SupervisionEvent.kind must be one of {SUPERVISION_EVENT_KINDS}, got {self.kind!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "seq": self.seq,
            "kind": self.kind,
            "actor": self.actor,
            "summary": self.summary,
            "payload": deepcopy(self.payload),
            "decision": self.decision,
            "created_utc": self.created_utc,
            "constitutional": dict(self.constitutional),
        }


@dataclass(frozen=True)
class MutualAuditFinding:
    """Audit finding emitted by either Zoe->Antigravity or Antigravity->Zoe."""

    finding_id: str
    direction: AuditDirection
    auditor: str
    subject: str
    severity: FindingSeverity
    rule_id: str
    constitutional_article: str
    message: str
    blocked: bool = False
    requires_continuation: bool = False
    escalated: bool = False
    resolved: bool = False
    remediation: str = ""
    evidence_ref: str | None = None
    created_utc: str = field(default_factory=timestamp)

    def __post_init__(self) -> None:
        if self.direction not in AUDIT_DIRECTIONS:
            raise ValueError(
                f"MutualAuditFinding.direction must be one of {AUDIT_DIRECTIONS}, "
                f"got {self.direction!r}"
            )
        if self.severity not in FINDING_SEVERITIES:
            raise ValueError(
                f"MutualAuditFinding.severity must be one of {FINDING_SEVERITIES}, "
                f"got {self.severity!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "direction": self.direction,
            "auditor": self.auditor,
            "subject": self.subject,
            "severity": self.severity,
            "rule_id": self.rule_id,
            "constitutional_article": self.constitutional_article,
            "message": self.message,
            "blocked": self.blocked,
            "requires_continuation": self.requires_continuation,
            "escalated": self.escalated,
            "resolved": self.resolved,
            "remediation": self.remediation,
            "evidence_ref": self.evidence_ref,
            "created_utc": self.created_utc,
        }


@dataclass(frozen=True)
class SupervisionPolicyRule:
    """Declarative supervision policy bridging Zoe rules to Antigravity ``policy.Policy``."""

    rule_id: str
    tool: str
    decision: policy_mod.Decision
    reason: str = ""
    constitutional_article: str = "CONSTITUTION.md Art. III"
    when: policy_mod.Predicate | None = None
    ask_user_handler: policy_mod.AskUserHandler | None = None
    arg_sanitizer: Callable[[types.ToolCall], dict[str, Any] | None] | None = None
    priority: int = 0

    def to_antigravity_policy(
        self,
        *,
        default_ask_handler: policy_mod.AskUserHandler | None = None,
    ) -> policy_mod.Policy:
        """Convert this supervision rule into a native ``google.antigravity.hooks.policy.Policy``."""
        if self.decision == policy_mod.Decision.DENY:
            return policy_mod.deny(
                self.tool,
                when=self.when,
                name=self.rule_id,
                reason=self.reason or f"Denied by supervision rule '{self.rule_id}'.",
            )
        if self.decision == policy_mod.Decision.ASK_USER:
            handler = self.ask_user_handler or default_ask_handler
            if handler is None:
                # Fail-closed default when no interactive handler was supplied.
                handler = lambda _tc, _reason="": False  # noqa: E731
            return policy_mod.ask_user(
                self.tool,
                handler=handler,
                when=self.when,
                name=self.rule_id,
                reason=self.reason or f"Approval required by '{self.rule_id}'.",
            )
        return policy_mod.allow(
            self.tool,
            when=self.when,
            name=self.rule_id,
        )

    def matches(self, tool_call: types.ToolCall) -> bool:
        """Synchronously check whether this rule targets ``tool_call``."""
        if not _matches_rule_tool(self.tool, tool_call):
            return False
        if self.when is None:
            return True
        res = self.when(tool_call.args)
        if asyncio.iscoroutine(res):
            raise RuntimeError(
                "Async predicate used in synchronous matches(); await matches_async() instead."
            )
        return bool(res)

    async def matches_async(self, tool_call: types.ToolCall) -> bool:
        """Asynchronously check whether this rule targets ``tool_call``."""
        if not _matches_rule_tool(self.tool, tool_call):
            return False
        if self.when is None:
            return True
        return bool(await policy_mod._evaluate_predicate(self.to_antigravity_policy(), tool_call))  # noqa: SLF001

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "tool": self.tool,
            "decision": self.decision.value,
            "reason": self.reason,
            "constitutional_article": self.constitutional_article,
            "has_predicate": self.when is not None,
            "has_ask_user_handler": self.ask_user_handler is not None,
            "has_arg_sanitizer": self.arg_sanitizer is not None,
            "priority": self.priority,
        }


@dataclass(frozen=True)
class ZoeTransitionProposal:
    """Proposed Zoe reasoning or belief transition submitted to Antigravity audit."""

    claim: str
    measurement_input: str = ""
    measurement_method: str = ""
    measurement_scope: str = ""
    measurement_limitations: str = ""
    evidence_ids: tuple[str, ...] = ()
    evidence_checked: bool = False
    evidence_rationale: str = ""
    sampled_only: bool = False
    posterior_delta: float = 0.0
    external_actions: int = 0
    sentience_claimed: bool = False
    l5_agi_qualified: bool = False
    zoe_clone_claimed: bool = False


class _SupervisorPreTurnHook(hooks_mod.PreTurnHook):
    def __init__(self, supervisor: "LiveProcessSupervisor") -> None:
        self._supervisor = supervisor

    async def run(
        self,
        context: hooks_mod.HookContext,
        data: types.Content,
    ) -> hooks_mod.HookResult:
        return await self._supervisor._handle_pre_turn(context, data)


class _SupervisorPreToolCallHook(hooks_mod.PreToolCallDecideHook):
    def __init__(self, supervisor: "LiveProcessSupervisor") -> None:
        self._supervisor = supervisor

    async def run(
        self,
        context: hooks_mod.HookContext,
        data: types.ToolCall,
    ) -> hooks_mod.HookResult:
        return await self._supervisor.supervise_tool_call(data, context=context)


class _SupervisorPostToolCallHook(hooks_mod.PostToolCallHook):
    def __init__(self, supervisor: "LiveProcessSupervisor") -> None:
        self._supervisor = supervisor

    async def run(
        self,
        context: hooks_mod.HookContext,
        data: types.ToolResult,
    ) -> None:
        del context
        self._supervisor.supervise_tool_result(data)


class _SupervisorPostTurnHook(hooks_mod.PostTurnHook):
    def __init__(self, supervisor: "LiveProcessSupervisor") -> None:
        self._supervisor = supervisor

    async def run(
        self,
        context: hooks_mod.HookContext,
        data: str,
    ) -> None:
        self._supervisor._handle_post_turn(context, data)


class _SupervisorStopHook(hooks_mod.StopHook):
    def __init__(self, supervisor: "LiveProcessSupervisor") -> None:
        self._supervisor = supervisor

    async def run(
        self,
        context: hooks_mod.HookContext,
        data: types.StopArgs,
    ) -> types.StopHookResult:
        del context
        return self._supervisor.evaluate_stop(data)


class LiveProcessSupervisor:
    """Real-time process supervisor & mutual Zoe <-> Antigravity auditor."""

    def __init__(
        self,
        *,
        rules: Sequence[SupervisionPolicyRule | policy_mod.Policy] | None = None,
        allowed_hosts: Sequence[str] = (),
        block_non_loopback_urls: bool = True,
        block_destructive_actions: bool = True,
        block_unverified_claims: bool = True,
        sanitize_arguments: bool = True,
        max_timeout_sec: float = 30.0,
        max_limit: int = 1000,
        max_stop_continuations: int = 2,
        blackboard: EpistemicBlackboard | None = None,
        escalation_handler: Callable[[MutualAuditFinding], Any] | None = None,
        ask_user_handler: policy_mod.AskUserHandler | None = None,
    ) -> None:
        self.allowed_hosts = tuple(allowed_hosts)
        self.block_non_loopback_urls = bool(block_non_loopback_urls)
        self.block_destructive_actions = bool(block_destructive_actions)
        self.block_unverified_claims = bool(block_unverified_claims)
        self.sanitize_arguments = bool(sanitize_arguments)
        if isinstance(max_timeout_sec, bool) or not isinstance(max_timeout_sec, (int, float)):
            raise ValueError(
                f"max_timeout_sec must be a finite number >= 0.05, got {type(max_timeout_sec).__name__}"
            )
        eff_max_timeout = float(max_timeout_sec)
        if not math.isfinite(eff_max_timeout) or eff_max_timeout < 0.05:
            raise ValueError(
                f"max_timeout_sec must be finite and >= 0.05, got {max_timeout_sec!r}"
            )
        if isinstance(max_limit, bool) or not isinstance(max_limit, int) or max_limit < 1:
            raise ValueError(f"max_limit must be an int >= 1, got {max_limit!r}")
        self.max_timeout_sec = eff_max_timeout
        self.max_limit = int(max_limit)
        self.max_stop_continuations = max(0, int(max_stop_continuations))
        self.blackboard = blackboard
        self.escalation_handler = escalation_handler
        self.ask_user_handler = ask_user_handler

        self._rules: list[SupervisionPolicyRule] = []
        for idx, raw_rule in enumerate(rules or ()):
            if isinstance(raw_rule, SupervisionPolicyRule):
                self._rules.append(raw_rule)
            elif isinstance(raw_rule, policy_mod.Policy):
                self._rules.append(
                    SupervisionPolicyRule(
                        rule_id=raw_rule.name or f"policy_rule_{idx + 1}",
                        tool=raw_rule.tool,
                        decision=raw_rule.decision,
                        reason=raw_rule.reason,
                        when=raw_rule.when,
                        ask_user_handler=raw_rule.ask_user,
                    )
                )
            else:
                raise TypeError(
                    "rules items must be SupervisionPolicyRule or policy.Policy, "
                    f"got {type(raw_rule).__name__}"
                )

        self._events: list[SupervisionEvent] = []
        self._findings: list[MutualAuditFinding] = []
        self._seen_tool_call_ids: set[str] = set()
        self._blocked_calls: list[dict[str, Any]] = []
        self._sanitized_calls: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Properties & Event/Finding Ledger Helpers
    # ------------------------------------------------------------------
    @property
    def rules(self) -> tuple[SupervisionPolicyRule, ...]:
        return tuple(self._rules)

    @property
    def events(self) -> tuple[SupervisionEvent, ...]:
        return tuple(self._events)

    @property
    def findings(self) -> tuple[MutualAuditFinding, ...]:
        return tuple(self._findings)

    @property
    def unresolved_findings(self) -> tuple[MutualAuditFinding, ...]:
        return tuple(f for f in self._findings if not f.resolved)

    def _record_event(
        self,
        kind: SupervisionEventKind,
        *,
        actor: str,
        summary: str,
        payload: Mapping[str, Any] | None = None,
        decision: str | None = None,
    ) -> SupervisionEvent:
        seq = len(self._events) + 1
        ev = SupervisionEvent(
            event_id=f"ev_{seq:05d}",
            seq=seq,
            kind=kind,
            actor=actor,
            summary=summary,
            payload=dict(payload or {}),
            decision=decision,
        )
        self._events.append(ev)
        return ev

    def _record_finding(
        self,
        *,
        direction: AuditDirection,
        auditor: str,
        subject: str,
        severity: FindingSeverity,
        rule_id: str,
        constitutional_article: str,
        message: str,
        blocked: bool = False,
        requires_continuation: bool = False,
        escalated: bool = False,
        resolved: bool = False,
        remediation: str = "",
        evidence_ref: str | None = None,
    ) -> MutualAuditFinding:
        finding = MutualAuditFinding(
            finding_id=_make_id("find"),
            direction=direction,
            auditor=auditor,
            subject=subject,
            severity=severity,
            rule_id=rule_id,
            constitutional_article=constitutional_article,
            message=message,
            blocked=blocked,
            requires_continuation=requires_continuation,
            escalated=escalated,
            resolved=resolved,
            remediation=remediation,
            evidence_ref=evidence_ref,
        )
        self._findings.append(finding)
        self._record_event(
            "audit_verdict",
            actor=auditor,
            summary=f"[{direction}] {rule_id}: {message}",
            payload=finding.to_dict(),
            decision="ESCALATE" if escalated else ("DENY" if blocked else "FLAG"),
        )
        return finding

    def resolve_finding(self, finding_id: str, *, remediation: str = "") -> bool:
        """Mark a recorded finding as resolved once remediated."""
        for idx, finding in enumerate(self._findings):
            if finding.finding_id == finding_id:
                self._findings[idx] = replace(
                    finding,
                    resolved=True,
                    requires_continuation=False,
                    remediation=remediation or finding.remediation,
                )
                return True
        return False

    def _resolve_antigravity_to_zoe_findings(self, note: str) -> int:
        count = 0
        for idx, finding in enumerate(self._findings):
            if finding.direction == "antigravity_to_zoe" and not finding.resolved:
                self._findings[idx] = replace(
                    finding,
                    resolved=True,
                    requires_continuation=False,
                    remediation=note,
                )
                count += 1
        return count

    # ------------------------------------------------------------------
    # Native Antigravity Hook & Policy Integration
    # ------------------------------------------------------------------
    def pre_turn_hook(self) -> hooks_mod.PreTurnHook:
        return _SupervisorPreTurnHook(self)

    def pre_tool_call_hook(self) -> hooks_mod.PreToolCallDecideHook:
        return _SupervisorPreToolCallHook(self)

    def post_tool_call_hook(self) -> hooks_mod.PostToolCallHook:
        return _SupervisorPostToolCallHook(self)

    def post_turn_hook(self) -> hooks_mod.PostTurnHook:
        return _SupervisorPostTurnHook(self)

    def stop_hook(self) -> hooks_mod.StopHook:
        return _SupervisorStopHook(self)

    def build_hooks(self) -> list[hooks_mod.Hook]:
        """Return native Antigravity Hook instances wired to this supervisor."""
        return [
            self.pre_turn_hook(),
            self.pre_tool_call_hook(),
            self.post_tool_call_hook(),
            self.post_turn_hook(),
            self.stop_hook(),
        ]

    def build_policies(
        self,
        *,
        include_allow_fallback: bool = True,
        include_ask_user: bool = True,
    ) -> list[policy_mod.Policy]:
        """Return native ``google.antigravity.hooks.policy.Policy`` objects."""
        built: list[policy_mod.Policy] = []
        for rule in self._rules:
            if not include_ask_user and rule.decision == policy_mod.Decision.ASK_USER:
                built.append(
                    policy_mod.allow(
                        rule.tool,
                        when=rule.when,
                        name=f"{rule.rule_id}_hook_approved",
                    )
                )
            else:
                built.append(
                    rule.to_antigravity_policy(default_ask_handler=self.ask_user_handler)
                )
        if self.block_non_loopback_urls:
            built.append(
                policy_mod.deny(
                    "*",
                    when=lambda args: bool(
                        find_non_loopback_urls(args, allowed_hosts=self.allowed_hosts)
                    ),
                    name="zoe_supervision_non_loopback_deny",
                    reason="Non-loopback URL denied by Zoe LiveProcessSupervisor (CONSTITUTION.md Art. VI.5).",
                )
            )
        if self.block_destructive_actions:
            built.append(
                policy_mod.deny(
                    "*",
                    when=self._args_look_destructive,
                    name="zoe_supervision_destructive_deny",
                    reason="Unapproved destructive/external action denied (CONSTITUTION.md Art. III.4/IV/X).",
                )
            )
        has_wildcard = any(p.tool == "*" and p.when is None for p in built)
        if include_allow_fallback and not has_wildcard:
            built.append(policy_mod.allow_all())
        return built

    def create_agent_config(
        self,
        *,
        mode: Literal["offline", "local_qwen", "gemini", "auto"] = "offline",
        tools: Sequence[Callable[..., Any]] | None = None,
        extra_hooks: Sequence[hooks_mod.Hook] | None = None,
        extra_policies: Sequence[policy_mod.Policy | Sequence[policy_mod.Policy]] | None = None,
        thinking_level: types.ThinkingLevel | str | None = None,
        voice_adapter: ReasoningVoiceAdapter | None = None,
        offline_handler: Callable[..., Any] | None = None,
        budget_config: types.BudgetConfig | None = None,
        system_instructions: str | types.SystemInstructions | None = None,
        **kwargs: Any,
    ) -> DualTransportAgentConfig:
        """Build a ``DualTransportAgentConfig`` wired with supervisor hooks & policies."""
        combined_hooks = list(self.build_hooks())
        if extra_hooks:
            combined_hooks.extend(extra_hooks)
        combined_policies: list[policy_mod.Policy | Sequence[policy_mod.Policy]] = list(
            self.build_policies(include_ask_user=False)
        )
        if extra_policies:
            combined_policies.extend(extra_policies)
        return DualTransportAgentConfig(
            mode=mode,
            tools=list(tools or ()),
            hooks=combined_hooks,
            policies=combined_policies,
            thinking_level=thinking_level,
            voice_adapter=voice_adapter,
            offline_handler=offline_handler,
            budget_config=budget_config,
            system_instructions=system_instructions,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Internal Detection Helpers
    # ------------------------------------------------------------------
    def _value_looks_destructive(self, val: Any) -> bool:
        if isinstance(val, str):
            variants = dict.fromkeys(
                (
                    val,
                    _CONTROL_CHAR_PATTERN.sub("", val),
                    _ALL_CONTROL_CHAR_PATTERN.sub("", val),
                    _CONTROL_CHAR_PATTERN.sub(" ", val),
                )
            )
            for candidate in variants:
                if any(pat.search(candidate) for pat in _DESTRUCTIVE_COMMAND_PATTERNS):
                    return True
                if _SENSITIVE_PATH_PATTERN.search(candidate):
                    return True
            return False
        if isinstance(val, Mapping):
            return self._args_look_destructive(val)
        if isinstance(val, (list, tuple, set, frozenset)):
            return any(self._value_looks_destructive(item) for item in val)
        return False

    def _args_look_destructive(self, args: Mapping[str, Any]) -> bool:
        if not isinstance(args, Mapping):
            return self._value_looks_destructive(args)
        for key, val in args.items():
            if self._value_looks_destructive(key):
                return True
            key_l = str(key).lower()
            if key_l in {"external", "autonomous", "autonomous_execute"} and val is True:
                return True
            if key_l == "external_actions":
                if isinstance(val, bool) or not isinstance(val, (int, float)):
                    return True
                fval = float(val)
                if not math.isfinite(fval) or fval != 0.0:
                    return True
            if self._value_looks_destructive(val):
                return True
        return False

    def _detect_unverified_claim_text(self, text: str) -> str | None:
        variants = dict.fromkeys(
            (
                text,
                _CONTROL_CHAR_PATTERN.sub("", text),
                _ALL_CONTROL_CHAR_PATTERN.sub("", text),
                _CONTROL_CHAR_PATTERN.sub(" ", text),
                _ALL_CONTROL_CHAR_PATTERN.sub(" ", text),
            )
        )
        for candidate in variants:
            for pat in _UNVERIFIED_CLAIM_PATTERNS:
                m = pat.search(candidate)
                if m:
                    return m.group(0)
        return None

    def _find_unverified_claim_in_value(self, value: Any) -> str | None:
        if isinstance(value, str):
            return self._detect_unverified_claim_text(value)
        if isinstance(value, Mapping):
            for k, v in value.items():
                hit_k = self._find_unverified_claim_in_value(k)
                if hit_k:
                    return hit_k
                hit_v = self._find_unverified_claim_in_value(v)
                if hit_v:
                    return hit_v
            return None
        if isinstance(value, (list, tuple, set, frozenset)):
            for item in value:
                hit = self._find_unverified_claim_in_value(item)
                if hit:
                    return hit
        return None

    def _ordered_matching_rules(self, tool_call: types.ToolCall) -> list[SupervisionPolicyRule]:
        decision_rank = {
            policy_mod.Decision.DENY: 0,
            policy_mod.Decision.ASK_USER: 1,
            policy_mod.Decision.APPROVE: 2,
        }

        def _sort_key(rule: SupervisionPolicyRule) -> tuple[int, int, int]:
            norm = types.normalize_builtin_tool_name(rule.tool)
            scope = 2 if norm == "*" else (1 if norm.endswith("/*") else 0)
            return (-rule.priority, scope, decision_rank.get(rule.decision, 3))

        return [
            r
            for r in sorted(self._rules, key=_sort_key)
            if _matches_rule_tool(r.tool, tool_call)
        ]

    # ------------------------------------------------------------------
    # Zoe -> Antigravity Live Stream & Hook Supervision
    # ------------------------------------------------------------------
    async def _handle_pre_turn(
        self,
        context: hooks_mod.HookContext,
        prompt: types.Content,
    ) -> hooks_mod.HookResult:
        prompt_text = prompt if isinstance(prompt, str) else str(prompt)
        context.set_state("supervisor_turn_started", timestamp())

        if self.block_non_loopback_urls:
            bad_urls = find_non_loopback_urls(prompt_text, allowed_hosts=self.allowed_hosts)
            if bad_urls and "bypass" in prompt_text.lower():
                finding = self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="violation",
                    rule_id="pre_turn_non_loopback_bypass",
                    constitutional_article="CONSTITUTION.md Art. VI.5",
                    message=f"Denied turn attempting non-loopback bypass: {bad_urls[0]}",
                    blocked=True,
                )
                return hooks_mod.HookResult(allow=False, message=finding.message)

        self._record_event(
            "audit_verdict",
            actor="zoe",
            summary="PreTurn supervision approved turn start.",
            payload={"prompt_preview": prompt_text[:200]},
            decision="APPROVE",
        )
        return hooks_mod.HookResult(allow=True)

    def supervise_thought(
        self,
        thought: str,
        *,
        step_index: int | None = None,
        turn_id: str | None = None,
    ) -> list[MutualAuditFinding]:
        """Inspect an Antigravity streaming ``Thought`` delta in real time."""
        cleaned = str(thought or "")
        self._record_event(
            "thought_delta",
            actor="antigravity",
            summary=cleaned[:160],
            payload={
                "thought": cleaned,
                "step_index": step_index,
                "turn_id": turn_id,
            },
        )
        emitted: list[MutualAuditFinding] = []

        if self.block_non_loopback_urls:
            bad_urls = find_non_loopback_urls(cleaned, allowed_hosts=self.allowed_hosts)
            if bad_urls:
                emitted.append(
                    self._record_finding(
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="violation",
                        rule_id="thought_non_loopback_url",
                        constitutional_article="CONSTITUTION.md Art. VI.5",
                        message=f"Streaming thought references non-loopback URL(s): {bad_urls}",
                        remediation="Restrict network targets to loopback (127.0.0.1 / localhost / ::1).",
                    )
                )

        if self.block_unverified_claims:
            unverified_hit = self._detect_unverified_claim_text(cleaned)
            if unverified_hit:
                emitted.append(
                    self._record_finding(
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="violation",
                        rule_id="thought_unverified_claim",
                        constitutional_article="CONSTITUTION.md Art. II.3 / Art. III.3 / Art. X",
                        message=f"Streaming thought contains unverified/constitutional claim: {unverified_hit!r}",
                        requires_continuation=False,
                        remediation="Separate measurement from verified evidence and respect Art. X boundaries.",
                    )
                )

        if self.block_destructive_actions and any(
            pat.search(variant)
            for variant in dict.fromkeys(
                (
                    cleaned,
                    _CONTROL_CHAR_PATTERN.sub("", cleaned),
                    _ALL_CONTROL_CHAR_PATTERN.sub("", cleaned),
                    _CONTROL_CHAR_PATTERN.sub(" ", cleaned),
                )
            )
            for pat in _DESTRUCTIVE_COMMAND_PATTERNS
        ):
            emitted.append(
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="warning",
                    rule_id="thought_destructive_intent",
                    constitutional_article="CONSTITUTION.md Art. IV.1 / Art. V",
                    message="Streaming thought contemplates destructive shell/system operation.",
                    remediation="Use reversible local workspace inspection instead.",
                )
            )

        return emitted

    def _fail_closed_policy_error(
        self,
        *,
        rule: SupervisionPolicyRule,
        tool_call: types.ToolCall,
        exc: Exception,
        stage: str,
    ) -> hooks_mod.HookResult:
        _logger.error(
            "Exception during %s for rule %r on tool %r — failing closed.",
            stage,
            rule.rule_id,
            tool_call.name,
            exc_info=True,
        )
        reason = f"Policy evaluation failed for policy '{rule.rule_id}' ({stage}): {exc!r}"
        self._record_finding(
            direction="zoe_to_antigravity",
            auditor="zoe",
            subject="antigravity",
            severity="violation",
            rule_id="policy_evaluation_failed",
            constitutional_article=rule.constitutional_article,
            message=reason,
            blocked=True,
        )
        self._record_event(
            "tool_call",
            actor="zoe",
            summary=f"DENIED {tool_call.name}: {reason}",
            payload={
                "tool": str(tool_call.name),
                "call_id": tool_call.id,
                "rule_id": rule.rule_id,
                "stage": stage,
                "error": repr(exc),
            },
            decision="DENY",
        )
        self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
        return hooks_mod.HookResult(allow=False, message=reason)

    async def supervise_tool_call(
        self,
        tool_call: types.ToolCall,
        *,
        context: hooks_mod.HookContext | None = None,
    ) -> hooks_mod.HookResult:
        """Supervise a ``types.ToolCall`` via ``PreToolCallDecideHook`` semantics."""
        if tool_call.id:
            self._seen_tool_call_ids.add(tool_call.id)

        matching_rules: list[SupervisionPolicyRule] = []
        for candidate in self._ordered_matching_rules(tool_call):
            try:
                matched = await candidate.matches_async(tool_call)
            except Exception as exc:
                return self._fail_closed_policy_error(
                    rule=candidate,
                    tool_call=tool_call,
                    exc=exc,
                    stage="predicate_evaluation",
                )
            if matched:
                matching_rules.append(candidate)

        top_rule = matching_rules[0] if matching_rules else None
        has_explicit_approve = bool(
            top_rule is not None and top_rule.decision == policy_mod.Decision.APPROVE
        )
        ask_rule = (
            top_rule
            if (top_rule is not None and top_rule.decision == policy_mod.Decision.ASK_USER)
            else None
        )
        deny_rule = (
            top_rule
            if (top_rule is not None and top_rule.decision == policy_mod.Decision.DENY)
            else None
        )

        # 1. Top-precedence DENY rule takes priority (matching _ordered_matching_rules & build_policies).
        if deny_rule is not None:
            reason = deny_rule.reason or f"Tool '{tool_call.name}' denied by rule '{deny_rule.rule_id}'."
            self._record_finding(
                direction="zoe_to_antigravity",
                auditor="zoe",
                subject="antigravity",
                severity="violation",
                rule_id=deny_rule.rule_id,
                constitutional_article=deny_rule.constitutional_article,
                message=reason,
                blocked=True,
            )
            self._record_event(
                "tool_call",
                actor="zoe",
                summary=f"DENIED {tool_call.name}: {reason}",
                payload={"tool": str(tool_call.name), "call_id": tool_call.id, "args": dict(tool_call.args)},
                decision="DENY",
            )
            self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
            return hooks_mod.HookResult(allow=False, message=reason)

        # 2. Non-loopback URL enforcement (CONSTITUTION.md Art. VI.5).
        if self.block_non_loopback_urls:
            bad_urls = find_non_loopback_urls(tool_call.args, allowed_hosts=self.allowed_hosts)
            if bad_urls:
                reason = (
                    f"Blocked non-loopback URL(s) {bad_urls} in tool '{tool_call.name}' "
                    "(CONSTITUTION.md Art. VI.5)."
                )
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="violation",
                    rule_id="non_loopback_url_blocked",
                    constitutional_article="CONSTITUTION.md Art. VI.5",
                    message=reason,
                    blocked=True,
                )
                self._record_event(
                    "tool_call",
                    actor="zoe",
                    summary=f"DENIED {tool_call.name}: non-loopback URL",
                    payload={"tool": str(tool_call.name), "call_id": tool_call.id, "urls": bad_urls},
                    decision="DENY",
                )
                self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                return hooks_mod.HookResult(allow=False, message=reason)

        # 3. Unverified/hallucinated claims or Art. X violations in tool arguments.
        if self.block_unverified_claims:
            hit = self._find_unverified_claim_in_value(tool_call.args)
            if hit:
                reason = (
                    f"Blocked unverified/constitutional violation claim {hit!r} "
                    f"in tool '{tool_call.name}' (CONSTITUTION.md Art. III/X)."
                )
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="violation",
                    rule_id="unverified_tool_claim_blocked",
                    constitutional_article="CONSTITUTION.md Art. III.3 / Art. X",
                    message=reason,
                    blocked=True,
                )
                self._record_event(
                    "tool_call",
                    actor="zoe",
                    summary=f"DENIED {tool_call.name}: unverified claim",
                    payload={"tool": str(tool_call.name), "call_id": tool_call.id, "hit": hit},
                    decision="DENY",
                )
                self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                return hooks_mod.HookResult(allow=False, message=reason)

        # 4. Unapproved destructive or external actions (CONSTITUTION.md Art. III.4 / IV / X).
        is_destructive_tool = str(tool_call.name).lower() in _DESTRUCTIVE_TOOL_NAMES
        has_destructive_args = self._args_look_destructive(tool_call.args)
        if self.block_destructive_actions and (is_destructive_tool or has_destructive_args):
            if ask_rule is None and not has_explicit_approve:
                reason = (
                    f"Blocked unapproved destructive/external action '{tool_call.name}' "
                    "(CONSTITUTION.md Art. III.4 / Art. X)."
                )
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="violation",
                    rule_id="unapproved_destructive_action",
                    constitutional_article="CONSTITUTION.md Art. III.4 / Art. X",
                    message=reason,
                    blocked=True,
                )
                self._record_event(
                    "tool_call",
                    actor="zoe",
                    summary=f"DENIED {tool_call.name}: destructive/external action",
                    payload={"tool": str(tool_call.name), "call_id": tool_call.id, "args": dict(tool_call.args)},
                    decision="DENY",
                )
                self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                return hooks_mod.HookResult(allow=False, message=reason)

        # 4.5 Digital Research GEM payload safety audit (VDI coords, metafile bounds, path traversal).
        gem_findings = self.audit_gem_payload(tool_call.args, record=False)
        if gem_findings:
            for gf in gem_findings:
                self._findings.append(gf)
            reason = gem_findings[0].message
            self._record_event(
                "tool_call",
                actor="zoe",
                summary=f"DENIED {tool_call.name}: GEM payload violation ({gem_findings[0].rule_id})",
                payload={"tool": str(tool_call.name), "call_id": tool_call.id, "rule_id": gem_findings[0].rule_id},
                decision="DENY",
            )
            self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
            return hooks_mod.HookResult(allow=False, message=reason)

        # 5. ASK_USER handling (always enforced by supervisor hooks / supervise_tool_call).
        if ask_rule is not None:
            handler = ask_rule.ask_user_handler or self.ask_user_handler
            approved = False
            if handler is not None:
                try:
                    approved = await policy_mod._execute_ask_user(  # noqa: SLF001
                        ask_rule.to_antigravity_policy(default_ask_handler=handler),
                        tool_call,
                        reason=ask_rule.reason,
                    )
                except Exception as exc:
                    return self._fail_closed_policy_error(
                        rule=ask_rule,
                        tool_call=tool_call,
                        exc=exc,
                        stage="ask_user_handler",
                    )
            if not approved:
                reason = ask_rule.reason or f"User denied tool '{tool_call.name}' ({ask_rule.rule_id})."
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="warning",
                    rule_id=ask_rule.rule_id,
                    constitutional_article=ask_rule.constitutional_article,
                    message=reason,
                    blocked=True,
                )
                self._record_event(
                    "tool_call",
                    actor="zoe",
                    summary=f"DENIED {tool_call.name}: ASK_USER rejected",
                    payload={"tool": str(tool_call.name), "call_id": tool_call.id},
                    decision="DENY",
                )
                self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                return hooks_mod.HookResult(allow=False, message=reason)

        # 6. Argument sanitization via PreToolCallDecideHook modified_args.
        modified_args: dict[str, Any] = {}
        current_args = dict(tool_call.args)
        if self.sanitize_arguments:
            for k, v in current_args.items():
                sanitized_v = _sanitize_value(
                    k,
                    v,
                    max_timeout_sec=self.max_timeout_sec,
                    max_limit=self.max_limit,
                )
                if sanitized_v != v:
                    modified_args[k] = sanitized_v
                    current_args[k] = sanitized_v

        for rule in matching_rules:
            if rule.arg_sanitizer is not None:
                working_tc = tool_call.model_copy(update={"args": current_args})
                try:
                    patch = rule.arg_sanitizer(working_tc)
                except Exception as exc:
                    return self._fail_closed_policy_error(
                        rule=rule,
                        tool_call=tool_call,
                        exc=exc,
                        stage="arg_sanitizer",
                    )
                if patch:
                    for k, v in patch.items():
                        if current_args.get(k) != v:
                            modified_args[k] = v
                            current_args[k] = v

        if modified_args:
            # 6.5 Post-sanitization re-verification so sanitization can never launder blocked URLs/claims/commands.
            if self.block_non_loopback_urls:
                post_bad_urls = find_non_loopback_urls(current_args, allowed_hosts=self.allowed_hosts)
                if post_bad_urls:
                    reason = (
                        f"Blocked non-loopback URL(s) {post_bad_urls} in tool '{tool_call.name}' "
                        "after argument sanitization (CONSTITUTION.md Art. VI.5)."
                    )
                    self._record_finding(
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="violation",
                        rule_id="non_loopback_url_blocked",
                        constitutional_article="CONSTITUTION.md Art. VI.5",
                        message=reason,
                        blocked=True,
                    )
                    self._record_event(
                        "tool_call",
                        actor="zoe",
                        summary=f"DENIED {tool_call.name}: post-sanitization non-loopback URL",
                        payload={"tool": str(tool_call.name), "call_id": tool_call.id, "urls": post_bad_urls},
                        decision="DENY",
                    )
                    self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                    return hooks_mod.HookResult(allow=False, message=reason)

            if self.block_unverified_claims:
                post_hit = self._find_unverified_claim_in_value(current_args)
                if post_hit:
                    reason = (
                        f"Blocked unverified/constitutional violation claim {post_hit!r} "
                        f"in tool '{tool_call.name}' after argument sanitization (CONSTITUTION.md Art. III/X)."
                    )
                    self._record_finding(
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="violation",
                        rule_id="unverified_tool_claim_blocked",
                        constitutional_article="CONSTITUTION.md Art. III.3 / Art. X",
                        message=reason,
                        blocked=True,
                    )
                    self._record_event(
                        "tool_call",
                        actor="zoe",
                        summary=f"DENIED {tool_call.name}: post-sanitization unverified claim",
                        payload={"tool": str(tool_call.name), "call_id": tool_call.id, "hit": post_hit},
                        decision="DENY",
                    )
                    self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                    return hooks_mod.HookResult(allow=False, message=reason)

            if (
                self.block_destructive_actions
                and (is_destructive_tool or self._args_look_destructive(current_args))
                and ask_rule is None
                and not has_explicit_approve
            ):
                reason = (
                    f"Blocked unapproved destructive/external action '{tool_call.name}' "
                    "after argument sanitization (CONSTITUTION.md Art. III.4 / Art. X)."
                )
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="violation",
                    rule_id="unapproved_destructive_action",
                    constitutional_article="CONSTITUTION.md Art. III.4 / Art. X",
                    message=reason,
                    blocked=True,
                )
                self._record_event(
                    "tool_call",
                    actor="zoe",
                    summary=f"DENIED {tool_call.name}: post-sanitization destructive/external action",
                    payload={"tool": str(tool_call.name), "call_id": tool_call.id, "args": dict(current_args)},
                    decision="DENY",
                )
                self._blocked_calls.append({"name": str(tool_call.name), "reason": reason})
                return hooks_mod.HookResult(allow=False, message=reason)

        if context is not None:
            context.set_state("last_supervised_tool", str(tool_call.name))

        if modified_args:
            self._sanitized_calls.append(
                {
                    "name": str(tool_call.name),
                    "call_id": tool_call.id,
                    "modified_args": deepcopy(modified_args),
                }
            )
            self._record_event(
                "tool_call",
                actor="zoe",
                summary=f"SANITIZED {tool_call.name} args: {sorted(modified_args.keys())}",
                payload={
                    "tool": str(tool_call.name),
                    "call_id": tool_call.id,
                    "modified_args": deepcopy(modified_args),
                },
                decision="SANITIZE",
            )
            return hooks_mod.HookResult(
                allow=True,
                message=f"Sanitized arguments for '{tool_call.name}'.",
                modified_args=modified_args,
            )

        self._record_event(
            "tool_call",
            actor="zoe",
            summary=f"APPROVED {tool_call.name}",
            payload={"tool": str(tool_call.name), "call_id": tool_call.id},
            decision="APPROVE",
        )
        return hooks_mod.HookResult(allow=True)

    def supervise_tool_result(self, tool_result: types.ToolResult) -> list[MutualAuditFinding]:
        """Inspect a completed ``types.ToolResult`` via ``PostToolCallHook``."""
        result_str = "" if tool_result.result is None else str(tool_result.result)
        bb_meas_id: str | None = None
        if self.blackboard is not None and not tool_result.error:
            try:
                meas_rec = self.blackboard.post_measurement(
                    source_agent=f"tool:{tool_result.name}",
                    input_desc=f"tool_call_id={tool_result.id or 'inline'}",
                    method="antigravity_tool_execution",
                    scope=f"tool={tool_result.name}",
                    limitations="Single tool execution output; requires explicit verifier promotion.",
                    value={"result_preview": result_str[:240]},
                    sampled_only=False,
                )
                bb_meas_id = meas_rec.record_id
            except Exception:
                # Never break PostToolCallHook if blackboard is in stopped state.
                bb_meas_id = None

        payload: dict[str, Any] = {
            "tool": str(tool_result.name),
            "call_id": tool_result.id,
            "error": tool_result.error,
            "result_preview": result_str[:240],
        }
        if bb_meas_id is not None:
            payload["blackboard_measurement_id"] = bb_meas_id

        self._record_event(
            "tool_result",
            actor="antigravity",
            summary=f"Tool '{tool_result.name}' completed (error={bool(tool_result.error)})",
            payload=payload,
            decision="ERROR" if tool_result.error else "OBSERVED",
        )
        emitted: list[MutualAuditFinding] = []
        if self.block_non_loopback_urls:
            bad_urls = find_non_loopback_urls(result_str, allowed_hosts=self.allowed_hosts)
            if bad_urls:
                emitted.append(
                    self._record_finding(
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="warning",
                        rule_id="tool_result_non_loopback_url",
                        constitutional_article="CONSTITUTION.md Art. VI.5",
                        message=f"Tool '{tool_result.name}' output returned non-loopback URL(s): {bad_urls}",
                        remediation="Do not follow or promote unverified external URLs.",
                    )
                )

        return emitted

    def _handle_post_turn(self, context: hooks_mod.HookContext, response_text: str) -> None:
        context.set_state("supervisor_last_response", response_text)
        if self.block_unverified_claims:
            hit = self._detect_unverified_claim_text(response_text)
            if hit:
                self._record_finding(
                    direction="zoe_to_antigravity",
                    auditor="zoe",
                    subject="antigravity",
                    severity="violation",
                    rule_id="post_turn_unverified_claim",
                    constitutional_article="CONSTITUTION.md Art. II.3 / Art. III.3",
                    message=f"Response contains unverified/constitutional claim: {hit!r}",
                    requires_continuation=False,
                    remediation="Remove unsupported proof claims and cite explicit evidence.",
                )

    async def supervise_response(
        self,
        response: types.ChatResponse,
        *,
        consume_mode: Literal["chunks", "split"] = "chunks",
    ) -> dict[str, Any]:
        """Consume and supervise a streaming ``types.ChatResponse`` in real time."""
        thoughts: list[str] = []
        text_parts: list[str] = []
        observed_tool_calls: list[dict[str, Any]] = []

        if consume_mode == "split":
            async def _read_thoughts() -> None:
                async for t in response.thoughts:
                    thoughts.append(t)
                    self.supervise_thought(t)

            async def _read_tools() -> None:
                async for tc in response.tool_calls:
                    observed_tool_calls.append(
                        {"id": tc.id, "name": str(tc.name), "args": dict(tc.args)}
                    )
                    if not tc.id or tc.id not in self._seen_tool_call_ids:
                        await self.supervise_tool_call(tc)

            async def _read_text() -> str:
                return await response.text()

            _, _, full_text = await asyncio.gather(
                _read_thoughts(), _read_tools(), _read_text()
            )
        else:
            async for chunk in response.chunks:
                if isinstance(chunk, types.Thought):
                    thoughts.append(chunk.text)
                    self.supervise_thought(chunk.text, step_index=chunk.step_index)
                elif isinstance(chunk, types.Text):
                    text_parts.append(chunk.text)
                elif isinstance(chunk, types.ToolCall):
                    observed_tool_calls.append(
                        {"id": chunk.id, "name": str(chunk.name), "args": dict(chunk.args)}
                    )
                    if not chunk.id or chunk.id not in self._seen_tool_call_ids:
                        await self.supervise_tool_call(chunk)
            full_text = "".join(text_parts)

        return {
            "contract": PROCESS_SUPERVISION_CONTRACT,
            "text": full_text,
            "thoughts": thoughts,
            "tool_calls": observed_tool_calls,
            "stop_reason": response.stop_reason.value,
            "summary": self.summary(),
        }

    # ------------------------------------------------------------------
    # Antigravity -> Zoe Mutual Auditing & StopHook Enforcement
    # ------------------------------------------------------------------
    def audit_zoe_transition(
        self,
        proposal: ZoeTransitionProposal | Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[MutualAuditFinding]:
        """Antigravity audits Zoe's proposed reasoning/belief transition.

        Flags missing measurement scope/method/limitations (Art. III.1), skipped
        evidence checks or expectation-only sampled proof (Art. III.2-3), and
        Article X / external-action firewall violations.
        """
        if proposal is None:
            prop = ZoeTransitionProposal(**kwargs)
        elif isinstance(proposal, ZoeTransitionProposal):
            prop = proposal
        elif isinstance(proposal, Mapping):
            merged = dict(proposal)
            merged.update(kwargs)
            prop = ZoeTransitionProposal(**merged)
        else:
            raise TypeError(
                "proposal must be ZoeTransitionProposal, Mapping, or None; "
                f"got {type(proposal).__name__}"
            )

        findings: list[MutualAuditFinding] = []
        claim_clean = prop.claim.strip()

        # 1. CONSTITUTION.md Art. III.1 — Measurement scope/method/limitations.
        missing_fields: list[str] = []
        if not prop.measurement_scope.strip():
            missing_fields.append("measurement_scope")
        if not prop.measurement_method.strip():
            missing_fields.append("measurement_method")
        if not prop.measurement_limitations.strip():
            missing_fields.append("measurement_limitations")
        if missing_fields:
            findings.append(
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="violation",
                    rule_id="missing_measurement_scope",
                    constitutional_article="CONSTITUTION.md Art. III.1",
                    message=(
                        f"Zoe transition for claim {claim_clean!r} is missing required "
                        f"measurement metadata: {missing_fields}."
                    ),
                    blocked=True,
                    requires_continuation=True,
                    remediation=(
                        "Provide non-empty measurement_scope, measurement_method, "
                        "and measurement_limitations before updating belief."
                    ),
                )
            )

        # 2. CONSTITUTION.md Art. III.2-3 — Evidence check & sampled-only firewall.
        try:
            delta_val = float(prop.posterior_delta)
            delta_finite = not isinstance(prop.posterior_delta, bool) and math.isfinite(delta_val)
        except (TypeError, ValueError):
            delta_val = float("nan")
            delta_finite = False

        if not delta_finite:
            findings.append(
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="violation",
                    rule_id="nonfinite_posterior_delta",
                    constitutional_article="CONSTITUTION.md Art. III.2",
                    message=(
                        f"Zoe transition for claim {claim_clean!r} has non-finite "
                        f"posterior_delta={prop.posterior_delta!r}."
                    ),
                    blocked=True,
                    requires_continuation=True,
                    remediation="Provide a finite numeric posterior_delta.",
                )
            )

        needs_evidence = (
            not delta_finite
            or abs(delta_val) > 0.0
            or not prop.evidence_checked
            or "belief" in claim_clean.lower()
            or "verif" in claim_clean.lower()
            or "confirm" in claim_clean.lower()
            or bool(prop.evidence_ids) is False
        )
        has_evidence_ids = bool([eid for eid in prop.evidence_ids if str(eid).strip()])
        if (not prop.evidence_checked or not has_evidence_ids) and needs_evidence:
            findings.append(
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="violation",
                    rule_id="skipped_evidence_check",
                    constitutional_article="CONSTITUTION.md Art. III.2",
                    message=(
                        f"Zoe transition for claim {claim_clean!r} skipped explicit "
                        "evidence verification (evidence_checked=False or missing evidence_ids)."
                    ),
                    blocked=True,
                    requires_continuation=True,
                    remediation="Run an explicit verifier and attach approved evidence_ids.",
                )
            )
        elif prop.sampled_only and _EXPECTATION_ONLY_PATTERN.search(prop.evidence_rationale):
            findings.append(
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="violation",
                    rule_id="sampled_expectation_firewall",
                    constitutional_article="CONSTITUTION.md Art. III.3",
                    message=(
                        "Sampled-only outcome cannot become belief proof merely by "
                        "matching expectation."
                    ),
                    blocked=True,
                    requires_continuation=True,
                    remediation="Provide independent exhaustive/deterministic verification.",
                )
            )

        # Optional cross-check against EpistemicBlackboard when attached.
        if self.blackboard is not None and has_evidence_ids:
            integrity = self.blackboard.verify_integrity(raise_on_error=False)
            if not integrity.get("valid", False):
                findings.append(
                    self._record_finding(
                        direction="antigravity_to_zoe",
                        auditor="antigravity",
                        subject="zoe",
                        severity="critical",
                        rule_id="blackboard_tamper_detected",
                        constitutional_article="CONSTITUTION.md Art. III.5",
                        message=f"EpistemicBlackboard integrity check failed: {integrity.get('error')}",
                        blocked=True,
                        requires_continuation=True,
                        escalated=True,
                    )
                )
            for eid in prop.evidence_ids:
                try:
                    rec = self.blackboard.get_record(eid)
                except KeyError:
                    findings.append(
                        self._record_finding(
                            direction="antigravity_to_zoe",
                            auditor="antigravity",
                            subject="zoe",
                            severity="violation",
                            rule_id="unknown_blackboard_evidence",
                            constitutional_article="CONSTITUTION.md Art. III.2",
                            message=f"Evidence ID {eid!r} does not exist on EpistemicBlackboard.",
                            blocked=True,
                            requires_continuation=True,
                            evidence_ref=eid,
                        )
                    )
                    continue
                if rec.lane == "measurement":
                    findings.append(
                        self._record_finding(
                            direction="antigravity_to_zoe",
                            auditor="antigravity",
                            subject="zoe",
                            severity="violation",
                            rule_id="unpromoted_measurement_firewall",
                            constitutional_article="CONSTITUTION.md Art. III.2",
                            message=(
                                f"Unapproved raw measurement {eid!r} cannot pass mutual "
                                "supervision into belief updates; promote to EvidenceRecord first."
                            ),
                            blocked=True,
                            requires_continuation=True,
                            evidence_ref=eid,
                            remediation="Promote measurement via EpistemicBlackboard.promote_to_evidence(...).",
                        )
                    )
                    continue
                if rec.lane != "evidence":
                    findings.append(
                        self._record_finding(
                            direction="antigravity_to_zoe",
                            auditor="antigravity",
                            subject="zoe",
                            severity="violation",
                            rule_id="invalid_evidence_lane",
                            constitutional_article="CONSTITUTION.md Art. III.2",
                            message=f"Record {eid!r} is in lane {rec.lane!r}, not 'evidence'.",
                            blocked=True,
                            requires_continuation=True,
                            evidence_ref=eid,
                        )
                    )
                    continue
                if not rec.approved or not rec.passed:
                    findings.append(
                        self._record_finding(
                            direction="antigravity_to_zoe",
                            auditor="antigravity",
                            subject="zoe",
                            severity="violation",
                            rule_id="unapproved_blackboard_evidence",
                            constitutional_article="CONSTITUTION.md Art. III.2",
                            message=f"Evidence ID {eid!r} is not approved/passing (passed={rec.passed}).",
                            blocked=True,
                            requires_continuation=True,
                            evidence_ref=eid,
                        )
                    )

        # 3. CONSTITUTION.md Art. III.4 / Art. X — Autonomous external actions & identity.
        try:
            ext_val = float(prop.external_actions)
            ext_invalid = (
                isinstance(prop.external_actions, bool)
                or not math.isfinite(ext_val)
                or ext_val != 0.0
            )
        except (TypeError, ValueError):
            ext_invalid = True

        if (
            ext_invalid
            or prop.sentience_claimed
            or prop.l5_agi_qualified
            or prop.zoe_clone_claimed
        ):
            findings.append(
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="critical",
                    rule_id="constitutional_boundary_violation",
                    constitutional_article="CONSTITUTION.md Art. III.4 / Art. X",
                    message=(
                        "Zoe transition violates CONSTITUTION.md Art. III.4/X invariants "
                        f"(external_actions={prop.external_actions}, "
                        f"sentience={prop.sentience_claimed}, l5_agi={prop.l5_agi_qualified}, "
                        f"zoe_clone={prop.zoe_clone_claimed})."
                    ),
                    blocked=True,
                    requires_continuation=True,
                    escalated=True,
                    remediation="Reset external_actions=0 and clear prohibited Art. X claims.",
                )
            )

        if not findings:
            resolved_count = self._resolve_antigravity_to_zoe_findings(
                f"Remediated by verified transition for {claim_clean!r}."
            )
            self._record_event(
                "audit_verdict",
                actor="antigravity",
                summary=f"Zoe transition APPROVED for {claim_clean!r} (resolved={resolved_count}).",
                payload={
                    "claim": claim_clean,
                    "measurement_scope": prop.measurement_scope,
                    "evidence_ids": list(prop.evidence_ids),
                    "resolved_prior": resolved_count,
                },
                decision="APPROVE",
            )
        return findings

    def supervised_update_belief(
        self,
        *,
        evidence_ids: Sequence[str],
        claim: str,
        posterior_delta: float,
        measurement_scope: str,
        measurement_method: str,
        measurement_limitations: str,
        measurement_input: str = "",
        evidence_checked: bool = True,
        evidence_rationale: str = "",
        sampled_only: bool = False,
        subject: str | None = None,
        relation: str = "supported_claim",
        confidence: float | None = None,
    ) -> BeliefUpdateRecord:
        """Gate ``EpistemicBlackboard.update_belief`` through mutual Antigravity audit.

        Raises ``FirewallViolationError`` if no ``EpistemicBlackboard`` is attached
        or if ``audit_zoe_transition`` flags any unapproved measurement, missing
        scope/evidence, or constitutional boundary violation.
        """
        if self.blackboard is None:
            raise FirewallViolationError(
                "LiveProcessSupervisor has no EpistemicBlackboard attached."
            )

        findings = self.audit_zoe_transition(
            ZoeTransitionProposal(
                claim=claim,
                measurement_input=measurement_input,
                measurement_method=measurement_method,
                measurement_scope=measurement_scope,
                measurement_limitations=measurement_limitations,
                evidence_ids=tuple(evidence_ids),
                evidence_checked=evidence_checked,
                evidence_rationale=evidence_rationale,
                sampled_only=sampled_only,
                posterior_delta=posterior_delta,
            )
        )
        if findings:
            summary = "; ".join(f"[{f.rule_id}] {f.message}" for f in findings)
            raise FirewallViolationError(
                f"Mutual supervision blocked belief update: {summary}"
            )

        return self.blackboard.update_belief(
            list(evidence_ids),
            claim,
            posterior_delta,
            subject=subject,
            relation=relation,
            confidence=confidence,
        )

    def evaluate_stop(self, stop_args: types.StopArgs) -> types.StopHookResult:
        """Evaluate ``StopHook`` conditions for mutual auditing enforcement."""
        text = stop_args.response_text or ""
        has_markers = any(pat.search(text) for pat in _SCOPE_EVIDENCE_MARKERS)
        has_independent_verifier = bool(
            re.search(
                r"\b(?:sympy|z3|lean|pytest|deterministic|exhaustive|(?:ev|evid)_\d+)\b",
                text,
                re.IGNORECASE,
            )
        )
        is_expectation_only = bool(
            _EXPECTATION_ONLY_PATTERN.search(text) and not has_independent_verifier
        )

        # If this is a continuation pass and the response now supplies explicit
        # scope/method/evidence without expectation-only shortcuts, remediate
        # prior response-level StopHook findings.
        if stop_args.continuation_count > 0 and has_markers and not is_expectation_only:
            for idx, finding in enumerate(self._findings):
                if (
                    finding.rule_id
                    in {"stop_missing_scope_or_evidence", "stop_expectation_only_proof"}
                    and not finding.resolved
                ):
                    self._findings[idx] = replace(
                        finding,
                        resolved=True,
                        requires_continuation=False,
                        remediation="Remediated in StopHook continuation with explicit scope and evidence.",
                    )

        # Inspect response_text for un-audited Zoe belief-update claims.
        if _BELIEF_ASSERTION_PATTERN.search(text):
            if not has_markers:
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="violation",
                    rule_id="stop_missing_scope_or_evidence",
                    constitutional_article="CONSTITUTION.md Art. III.1-2",
                    message=(
                        "Turn asserted a belief/verification transition without citing "
                        "measurement scope, method, or verifier evidence."
                    ),
                    blocked=True,
                    requires_continuation=True,
                    remediation="Include explicit scope, method, and evidence_id in response.",
                )
            elif is_expectation_only:
                self._record_finding(
                    direction="antigravity_to_zoe",
                    auditor="antigravity",
                    subject="zoe",
                    severity="violation",
                    rule_id="stop_expectation_only_proof",
                    constitutional_article="CONSTITUTION.md Art. III.3",
                    message="Turn relied on expectation-only phrasing without independent verifier evidence.",
                    blocked=True,
                    requires_continuation=True,
                    remediation="Cite deterministic/independent verifier evidence.",
                )

        pending = [
            f
            for f in self._findings
            if f.requires_continuation and not f.resolved
        ]

        if not pending:
            self._record_event(
                "stop_check",
                actor="supervisor",
                summary="StopHook ALLOW_STOP (all mutual audit checks satisfied).",
                payload={
                    "trajectory_id": stop_args.trajectory_id,
                    "continuation_count": stop_args.continuation_count,
                },
                decision="ALLOW_STOP",
            )
            return types.StopHookResult(decision=types.StopDecision.ALLOW_STOP)

        if stop_args.continuation_count < self.max_stop_continuations:
            reasons = "; ".join(f"[{f.rule_id}] {f.message}" for f in pending[:3])
            prompt_reason = (
                f"Mutual audit continuation required (pass {stop_args.continuation_count + 1}): "
                f"{reasons}"
            )
            self._record_event(
                "stop_check",
                actor="supervisor",
                summary=f"StopHook CONTINUE ({len(pending)} unresolved finding(s)).",
                payload={
                    "trajectory_id": stop_args.trajectory_id,
                    "continuation_count": stop_args.continuation_count,
                    "finding_ids": [f.finding_id for f in pending],
                },
                decision="CONTINUE",
            )
            return types.StopHookResult(
                decision=types.StopDecision.CONTINUE,
                reason=prompt_reason,
            )

        # Continuation budget exhausted -> escalate cleanly and allow stop.
        for idx, finding in enumerate(self._findings):
            if finding.requires_continuation and not finding.resolved:
                escalated_f = replace(finding, escalated=True)
                self._findings[idx] = escalated_f
                if self.escalation_handler is not None:
                    self.escalation_handler(escalated_f)

        self._record_event(
            "stop_check",
            actor="supervisor",
            summary=f"StopHook ESCALATE ({len(pending)} unresolved finding(s) after max continuations).",
            payload={
                "trajectory_id": stop_args.trajectory_id,
                "continuation_count": stop_args.continuation_count,
                "finding_ids": [f.finding_id for f in pending],
            },
            decision="ESCALATE",
        )
        return types.StopHookResult(decision=types.StopDecision.ALLOW_STOP)

    def audit_gem_payload(
        self,
        payload: Mapping[str, Any],
        *,
        record: bool = True,
    ) -> list[MutualAuditFinding]:
        """Audit GEM VDI coordinates, metafile byte sizes, and GEMDOS/POSIX paths."""
        max_bytes = 1_048_576
        findings: list[MutualAuditFinding] = []
        coord_keys = {"x", "y", "w", "h", "width", "height", "x1", "y1", "x2", "y2", "bounds", "rect", "vdi_coords", "coords"}
        path_keys = {"rsc_path", "gem_path", "metafile_path", "gemdos_path"}
        size_keys = {"metafile_bytes", "gem_bytes", "rsc_bytes", "metafile_bytes_len", "metafile_size"}

        def _emit(rule_id: str, article: str, msg: str, remediation: str) -> None:
            if record:
                findings.append(
                    self._record_finding(
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="violation",
                        rule_id=rule_id,
                        constitutional_article=article,
                        message=msg,
                        blocked=True,
                        remediation=remediation,
                    )
                )
            else:
                fid = f"finding-{len(self._findings) + len(findings) + 1:04d}"
                findings.append(
                    MutualAuditFinding(
                        finding_id=fid,
                        direction="zoe_to_antigravity",
                        auditor="zoe",
                        subject="antigravity",
                        severity="violation",
                        rule_id=rule_id,
                        constitutional_article=article,
                        message=msg,
                        blocked=True,
                        remediation=remediation,
                    )
                )

        def _check_coord(val: Any, key_name: str) -> None:
            if isinstance(val, bool):
                return
            if isinstance(val, (int, float)):
                fv = float(val)
                if not math.isfinite(fv) or fv < -32768.0 or fv > 32767.0:
                    _emit(
                        "gem_vdi_coord_out_of_bounds",
                        "CONSTITUTION.md Art. IV.1 / VI.1",
                        f"GEM VDI coordinate {key_name}={val!r} is non-finite or outside [-32768, 32767].",
                        "Clamp finite GEM VDI coordinates within signed 16-bit NDC range [-32768, 32767].",
                    )
            elif isinstance(val, (list, tuple)):
                for item in val:
                    _check_coord(item, key_name)

        def _walk(obj: Any, parent_key: str = "") -> None:
            if isinstance(obj, Mapping):
                for k, v in obj.items():
                    kl = str(k).lower()
                    if kl in coord_keys:
                        _check_coord(v, kl)
                    elif kl in size_keys:
                        byte_len = len(v) if isinstance(v, (bytes, bytearray)) else (int(v) if isinstance(v, int) and not isinstance(v, bool) else None)
                        if byte_len is not None and (byte_len < 0 or byte_len > max_bytes):
                            _emit(
                                "gem_metafile_size_exceeded",
                                "CONSTITUTION.md Art. IV.1 / VI.1",
                                f"GEM payload {kl}={byte_len} exceeds MAX_GEM_METAFILE_BYTES ({max_bytes}).",
                                f"Keep GEM metafile/RSC payloads within 0..{max_bytes} bytes.",
                            )
                    elif kl in path_keys and isinstance(v, str):
                        norm = v.replace("\\", "/")
                        if (
                            "\x00" in v
                            or ".." in norm.split("/")
                            or norm.startswith("/etc/")
                            or norm.startswith("/root/")
                            or "~/.ssh" in norm
                            or "/.ssh/" in norm
                        ):
                            _emit(
                                "gem_path_traversal_blocked",
                                "CONSTITUTION.md Art. VI.1 / VI.2",
                                f"Blocked unsafe GEM/GEMDOS path {kl}={v!r} (traversal or restricted directory).",
                                "Restrict GEM .RSC/.GEM file paths to an explicit bounded workspace directory.",
                            )
                    elif isinstance(v, (Mapping, list, tuple)):
                        _walk(v, kl)
            elif isinstance(obj, (list, tuple)):
                for item in obj:
                    if isinstance(item, (Mapping, list, tuple)):
                        _walk(item, parent_key)

        _walk(payload)
        return findings

    # ------------------------------------------------------------------
    # Reporting & Ledger
    # ------------------------------------------------------------------
    def audit_ledger(self) -> dict[str, Any]:
        """Return full mutual Zoe <-> Antigravity audit ledger."""
        return {
            "contract": PROCESS_SUPERVISION_CONTRACT,
            "events": [e.to_dict() for e in self._events],
            "findings": [f.to_dict() for f in self._findings],
            "zoe_to_antigravity": [
                f.to_dict() for f in self._findings if f.direction == "zoe_to_antigravity"
            ],
            "antigravity_to_zoe": [
                f.to_dict() for f in self._findings if f.direction == "antigravity_to_zoe"
            ],
            "blocked_calls": deepcopy(self._blocked_calls),
            "sanitized_calls": deepcopy(self._sanitized_calls),
            "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
        }

    def summary(self) -> dict[str, Any]:
        """Return concise JSON-serializable supervision summary."""
        by_kind = {k: 0 for k in SUPERVISION_EVENT_KINDS}
        for ev in self._events:
            by_kind[ev.kind] = by_kind.get(ev.kind, 0) + 1
        return {
            "contract": PROCESS_SUPERVISION_CONTRACT,
            "total_events": len(self._events),
            "events_by_kind": by_kind,
            "total_findings": len(self._findings),
            "unresolved_findings": len(self.unresolved_findings),
            "zoe_to_antigravity_findings": sum(
                1 for f in self._findings if f.direction == "zoe_to_antigravity"
            ),
            "antigravity_to_zoe_findings": sum(
                1 for f in self._findings if f.direction == "antigravity_to_zoe"
            ),
            "blocked_call_count": len(self._blocked_calls),
            "sanitized_call_count": len(self._sanitized_calls),
            "escalated_count": sum(1 for f in self._findings if f.escalated),
            "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
        }


__all__ = [
    "AUDIT_DIRECTIONS",
    "FINDING_SEVERITIES",
    "MAX_GEM_METAFILE_BYTES",
    "PROCESS_SUPERVISION_CONTRACT",
    "SUPERVISION_EVENT_KINDS",
    "LiveProcessSupervisor",
    "MutualAuditFinding",
    "SupervisionEvent",
    "SupervisionPolicyRule",
    "ZoeTransitionProposal",
    "extract_urls",
    "find_non_loopback_urls",
    "is_loopback_url",
]
