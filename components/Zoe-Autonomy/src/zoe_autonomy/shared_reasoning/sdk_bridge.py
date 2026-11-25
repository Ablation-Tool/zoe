"""Dual-transport Google Antigravity SDK bridge for Zoe Shared-Reasoning Architectures.

Provides a genuine, runnable ``google.antigravity`` transport layer supporting:
  - ``"offline"``: Deterministic ``OfflineAntigravityConnection`` &
    ``DualTransportStrategy`` executing full ``Conversation`` / ``Agent`` /
    ``HookRunner`` / ``ToolRunner`` / ``policy`` / ``ChatResponse`` step
    streams with Zoe Gear-1 (``ZoeElizaEngine`` + ``stem_layering.route_stem``)
    and zero network or API-key requirements.
  - ``"local_qwen"``: Loopback ``LocalOpenAIAgentConfig(...).lightweight()``
    targeting ``127.0.0.1:8080/v1`` (probed via ``stem_layering.probe_local_qwen``)
    with clean offline fallback when the loopback server is down.
  - ``"gemini"``: ``LocalAgentConfig`` when a Gemini/Vertex key or endpoint is
    explicitly configured, with clean offline fallback otherwise.
  - ``"auto"``: Selects live loopback/SDK transport only when reachable and
    permitted; otherwise selects deterministic offline execution.

Enforces ``docs/CONSTITUTION.md`` boundaries across all turns
(``external_actions=0``, ``sentience_claimed=False``,
``l5_agi_qualified=False``, ``zoe_clone_claimed=False``, attribution to
Nicholas Michael Kloster, March 6, 2026).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence
import concurrent.futures
from dataclasses import dataclass, field
import inspect
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
import weakref
from typing import Any, Literal, Protocol, runtime_checkable

import pydantic

from google.antigravity import Agent, types
from google.antigravity.connections import connection as connection_mod
from google.antigravity.connections.local.local_connection_config import LocalAgentConfig
from google.antigravity.connections.local.local_openai_connection_config import (
    LocalOpenAIAgentConfig,
)
from google.antigravity.hooks import hook_runner as hook_runner_mod
from google.antigravity.hooks import hooks as hooks_mod
from google.antigravity.hooks import policy as policy_mod
from google.antigravity.tools import tool_runner as tool_runner_mod

from ..stem_layering import (
    DEFAULT_LOCAL_QWEN_MODEL,
    DEFAULT_LOCAL_QWEN_URL,
    StemDecision,
    constitutional_flags,
    probe_local_qwen,
    route_stem,
)
from ..zoe_eliza import ZoeElizaEngine

SDK_BRIDGE_CONTRACT = "zoe-antigravity-sdk-bridge/v1"
ATTRIBUTION_TEXT = "Nicholas Michael Kloster, March 6, 2026"
VALID_MODES = ("offline", "local_qwen", "gemini", "auto")


def bridge_constitutional_metadata(*, cloud_tokens_used: int = 0) -> dict[str, Any]:
    """Return canonical CONSTITUTION.md metadata for shared-reasoning turns."""
    flags = constitutional_flags(cloud_tokens_used=cloud_tokens_used)
    flags["attribution"] = ATTRIBUTION_TEXT
    return flags


def run_coro_sync(coro: Awaitable[Any]) -> Any:
    """Execute an awaitable cleanly from synchronous code.

    If no asyncio event loop is active on the calling thread, delegates to
    ``asyncio.run``. If an event loop is already running (e.g. inside an async
    framework or test harness), executes ``asyncio.run`` in an isolated worker
    thread so callers never hit ``RuntimeError: asyncio.run() cannot be called
    from a running event loop``.
    """
    if not inspect.isawaitable(coro):
        raise TypeError(f"run_coro_sync expected an awaitable, got {type(coro).__name__}")

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    def _runner() -> Any:
        return asyncio.run(coro)

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_runner).result()


def _extract_prompt_text(prompt: types.Content | None) -> str:
    """Convert Antigravity ``types.Content`` into deterministic plain text."""
    if prompt is None:
        return ""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, Sequence):
        parts: list[str] = []
        for item in prompt:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, types.SlashCommand):
                parts.append(f"/{item.name.value}")
            elif hasattr(item, "mime_type"):
                desc = getattr(item, "description", None)
                label = f"[{type(item).__name__}:{item.mime_type}]"
                if desc:
                    label = f"{label} {desc}"
                parts.append(label)
            else:
                parts.append(str(item))
        return "\n".join(p for p in parts if p)
    return str(prompt)


def _coerce_thinking_level(
    level: types.ThinkingLevel | str | None,
) -> types.ThinkingLevel | None:
    """Normalize string or enum thinking levels into ``types.ThinkingLevel``."""
    if level is None or isinstance(level, types.ThinkingLevel):
        return level
    cleaned = str(level).strip().lower()
    aliases = {
        "minimal": types.ThinkingLevel.MINIMAL,
        "low": types.ThinkingLevel.LOW,
        "medium": types.ThinkingLevel.MEDIUM,
        "high": types.ThinkingLevel.HIGH,
        "xhigh": types.ThinkingLevel.EXTRA_HIGH,
        "extra_high": types.ThinkingLevel.EXTRA_HIGH,
        "x_high": types.ThinkingLevel.EXTRA_HIGH,
    }
    if cleaned not in aliases:
        raise ValueError(
            f"Unsupported thinking_level {level!r}; expected one of {sorted(aliases)}"
        )
    return aliases[cleaned]


def _estimate_tokens(text: str) -> int:
    """Deterministic lightweight token estimate without external tokenizers."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, (len(stripped) + 3) // 4)


@dataclass(frozen=True)
class VoiceResponse:
    """Normalized output returned by a ``ReasoningVoiceAdapter``."""

    text: str
    thoughts: tuple[str, ...] = ()
    tool_calls: tuple[dict[str, Any], ...] = ()
    structured_output: Any = None
    mode: str = "offline"
    model: str = "local-eliza-gear1"
    thinking_level: str | None = None
    stem_decision: dict[str, Any] | None = None
    constitutional: dict[str, Any] = field(default_factory=bridge_constitutional_metadata)


@runtime_checkable
class ReasoningVoiceAdapter(Protocol):
    """Protocol for pluggable reasoning voices used by ``DualTransportStrategy``."""

    async def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> VoiceResponse:
        """Generate a response, optional thought trace, and optional tool calls."""
        ...


class CallableVoiceAdapter:
    """Adapts a sync or async callable into a ``ReasoningVoiceAdapter``."""

    def __init__(
        self,
        handler: Callable[..., Any],
        *,
        model_name: str = "custom-offline-handler",
        mode: str = "offline",
    ) -> None:
        self._handler = handler
        self._model_name = model_name
        self._mode = mode

    async def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> VoiceResponse:
        ctx = dict(context or {})
        sig = inspect.signature(self._handler)
        positional = [
            p
            for p in sig.parameters.values()
            if p.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
        ]
        has_varargs = any(
            p.kind == inspect.Parameter.VAR_POSITIONAL for p in sig.parameters.values()
        )
        if has_varargs or len(positional) >= 2 or "context" in sig.parameters:
            raw = self._handler(prompt, ctx)
        else:
            raw = self._handler(prompt)

        if inspect.isawaitable(raw):
            raw = await raw

        if isinstance(raw, VoiceResponse):
            return raw
        if isinstance(raw, str):
            return VoiceResponse(
                text=raw,
                thoughts=(f"custom_handler({self._model_name}) completed turn.",),
                mode=self._mode,
                model=self._model_name,
                thinking_level=ctx.get("thinking_level"),
            )
        if isinstance(raw, Mapping):
            raw_thoughts = raw.get("thoughts") or ()
            if isinstance(raw_thoughts, str):
                raw_thoughts = (raw_thoughts,)
            raw_tools = raw.get("tool_calls") or ()
            normalized_tools = tuple(
                {"name": str(tc["name"]), "args": dict(tc.get("args") or {})}
                for tc in raw_tools
            )
            return VoiceResponse(
                text=str(raw.get("text", "")),
                thoughts=tuple(str(t) for t in raw_thoughts),
                tool_calls=normalized_tools,
                structured_output=raw.get("structured_output"),
                mode=str(raw.get("mode", self._mode)),
                model=str(raw.get("model", self._model_name)),
                thinking_level=raw.get("thinking_level", ctx.get("thinking_level")),
                stem_decision=raw.get("stem_decision"),
                constitutional=dict(
                    raw.get("constitutional") or bridge_constitutional_metadata()
                ),
            )
        raise TypeError(
            "CallableVoiceAdapter handler must return VoiceResponse, str, or Mapping; "
            f"got {type(raw).__name__}"
        )


class ZoeOfflineVoiceAdapter:
    """Deterministic Gear-1 Zoe reasoning voice backed by ``stem_layering`` & ``ZoeElizaEngine``."""

    def __init__(
        self,
        *,
        state_dir: str | Path | None = None,
        eliza_engine: ZoeElizaEngine | None = None,
        thinking_level: types.ThinkingLevel | str | None = None,
    ) -> None:
        self._explicit_state_dir = Path(state_dir).expanduser().resolve() if state_dir else None
        self._temp_dir: tempfile.TemporaryDirectory[str] | None = None
        self._finalizer: weakref.finalize | None = None
        self._eliza_engine = eliza_engine
        self._thinking_level = _coerce_thinking_level(thinking_level)

    def _get_engine(self) -> ZoeElizaEngine:
        if self._eliza_engine is None:
            if self._explicit_state_dir is not None:
                sd = self._explicit_state_dir
            else:
                self._temp_dir = tempfile.TemporaryDirectory(prefix="zoe_sr_eliza_")
                sd = Path(self._temp_dir.name)
                self._finalizer = weakref.finalize(self, self._temp_dir.cleanup)
            self._eliza_engine = ZoeElizaEngine(state_dir=sd, default_gear="gear1")
        return self._eliza_engine

    def close(self) -> None:
        """Release any temporary ELIZA state directory created by this adapter."""
        if self._finalizer is not None and self._finalizer.alive:
            self._finalizer()

    @staticmethod
    def _parse_tool_directive(
        prompt: str,
        available_tools: Sequence[str],
    ) -> tuple[dict[str, Any], ...]:
        """Support explicit deterministic tool invocation syntax in offline mode.

        Matches ``use tool <name> with <json>`` or ``call_tool:<name>(<json>)``
        when ``<name>`` is registered in ``ToolRunner``.
        """
        if not available_tools:
            return ()
        tool_set = set(available_tools)
        decoder = json.JSONDecoder()
        extracted: list[dict[str, Any]] = []

        use_pat = re.compile(
            r"(?:use\s+tool|call\s+tool)\s+([a-zA-Z0-9_-]+)(?:\s+with\s+)?",
            flags=re.IGNORECASE,
        )
        for match in use_pat.finditer(prompt):
            tname = match.group(1)
            if tname not in tool_set:
                continue
            args: dict[str, Any] = {}
            end_pos = match.end()
            if end_pos < len(prompt) and prompt[end_pos] == "{":
                try:
                    parsed, _ = decoder.raw_decode(prompt, end_pos)
                    if isinstance(parsed, dict):
                        args = parsed
                except json.JSONDecodeError:
                    args = {}
            extracted.append({"name": tname, "args": args})

        call_pat = re.compile(
            r"call_tool:([a-zA-Z0-9_-]+)\(\s*",
            flags=re.IGNORECASE,
        )
        for match in call_pat.finditer(prompt):
            tname = match.group(1)
            if tname not in tool_set:
                continue
            args = {}
            end_pos = match.end()
            if end_pos < len(prompt) and prompt[end_pos] == "{":
                try:
                    parsed, _ = decoder.raw_decode(prompt, end_pos)
                    if isinstance(parsed, dict):
                        args = parsed
                except json.JSONDecodeError:
                    args = {}
            extracted.append({"name": tname, "args": args})

        return tuple(extracted)

    async def generate(
        self,
        prompt: str,
        context: Mapping[str, Any] | None = None,
    ) -> VoiceResponse:
        ctx = dict(context or {})
        cleaned = " ".join(str(prompt or "").split()).strip()
        if not cleaned:
            cleaned = "status"

        # 1. Deterministic Kloster A_tau(p) stem routing (offline-constrained).
        stem = route_stem(
            cleaned,
            offline_only=True,
            local_qwen_available=False,
        )
        stem_doc = stem.to_dict()

        # 2. Deterministic Gear-1 ELIZA + monorepo evidence lookup.
        engine = self._get_engine()
        eliza_out = engine.respond(cleaned, gear="gear1")
        reply = str(eliza_out.get("reply") or "").strip()

        eff_thinking = _coerce_thinking_level(ctx.get("thinking_level")) or self._thinking_level
        thinking_str = eff_thinking.value if eff_thinking is not None else None

        # 3. Build transparent glass-box thoughts scaled by ThinkingLevel.
        thoughts: list[str] = [
            (
                f"[stem_layering] tier={stem.selected_tier} "
                f"a_tau={stem.a_tau} entropy_norm={stem.entropy_norm} "
                f"thinking_level={thinking_str or 'none'}"
            )
        ]
        if eff_thinking in (
            types.ThinkingLevel.MEDIUM,
            types.ThinkingLevel.HIGH,
            types.ThinkingLevel.EXTRA_HIGH,
        ):
            cites = [c.get("citation") for c in (eliza_out.get("citations") or []) if c.get("citation")]
            thoughts.append(
                f"[eliza_gear1] mode={eliza_out.get('mode')} "
                f"rule={eliza_out.get('rule_id')} citations={cites[:3]}"
            )
        if eff_thinking in (types.ThinkingLevel.HIGH, types.ThinkingLevel.EXTRA_HIGH):
            thoughts.append(
                "[constitution] external_actions=0 sentience_claimed=False "
                "l5_agi_qualified=False measurement!=evidence!=belief!=action"
            )

        available_tools = tuple(ctx.get("available_tools") or ())
        tool_calls = self._parse_tool_directive(prompt, available_tools)

        structured: Any = None
        if ctx.get("response_schema"):
            structured = {
                "reply": reply,
                "tier": stem.selected_tier,
                "a_tau": stem.a_tau,
                "mode": eliza_out.get("mode"),
                "constitutional": bridge_constitutional_metadata(cloud_tokens_used=0),
            }

        return VoiceResponse(
            text=reply,
            thoughts=tuple(thoughts),
            tool_calls=tool_calls,
            structured_output=structured,
            mode="offline",
            model="local-eliza-gear1",
            thinking_level=thinking_str,
            stem_decision=stem_doc,
            constitutional=bridge_constitutional_metadata(cloud_tokens_used=0),
        )


class OfflineAntigravityConnection(connection_mod.Connection):
    """In-process deterministic ``google.antigravity.connections.connection.Connection``.

    Streams genuine ``types.Step`` events (``THINKING``, ``TOOL_CALL``,
    ``TEXT_RESPONSE``, ``FINISH``, ``SYSTEM_MESSAGE``) so ``Conversation`` and
    ``Agent`` operate cleanly with zero external processes, network calls, or
    API keys, while honoring ``HookRunner``, ``ToolRunner``, ``policy``,
    ``BudgetConfig``, and ``ChatResponse`` cursors.
    """

    def __init__(
        self,
        *,
        voice_adapter: ReasoningVoiceAdapter,
        tool_runner: tool_runner_mod.ToolRunner | None = None,
        hook_runner: hook_runner_mod.HookRunner | None = None,
        conversation_id: str | None = None,
        debug_config: connection_mod.DebugConfig | None = None,
        budget_config: types.BudgetConfig | None = None,
        thinking_level: types.ThinkingLevel | str | None = None,
        response_schema: str | None = None,
        initial_history: Sequence[types.Step] | None = None,
        chunk_size: int = 48,
        max_stop_continuations: int = 2,
    ) -> None:
        self._voice_adapter = voice_adapter
        self._tool_runner = tool_runner
        self._hook_runner = hook_runner
        self._conversation_id = conversation_id or str(uuid.uuid4())
        self._debug_config = debug_config
        self._budget_config = budget_config
        self._thinking_level = _coerce_thinking_level(thinking_level)
        self._response_schema = response_schema
        self._history_seed = list(initial_history or [])
        self._chunk_size = max(8, int(chunk_size))
        self._max_stop_continuations = max(0, int(max_stop_continuations))

        self._is_idle = True
        self._disconnected = False
        self._cancelled = False
        self._has_pending_turn = False
        self._pending_prompt: types.Content | None = None
        self._pending_kwargs: dict[str, Any] = {}

        self._step_counter = len(self._history_seed)
        self._model_call_count = 0
        self._tool_call_count = 0
        self._turn_history: list[dict[str, Any]] = []
        self._pending_tool_results: list[types.ToolResult] = []
        self._last_stop_reason = types.StopReason.UNSPECIFIED
        self._cumulative_usage = types.UsageMetadata(
            prompt_token_count=0,
            cached_content_token_count=0,
            candidates_token_count=0,
            thoughts_token_count=0,
            total_token_count=0,
        )
        self._trajectory_usages: dict[str, types.UsageMetadata] = {
            self._conversation_id: self._cumulative_usage.model_copy()
        }

    @property
    def is_idle(self) -> bool:
        return self._is_idle

    @property
    def _initial_history(self) -> Sequence[types.Step]:
        return list(self._history_seed)

    @property
    def conversation_id(self) -> str:
        return self._conversation_id

    @property
    def debug_config(self) -> connection_mod.DebugConfig | None:
        return self._debug_config

    @property
    def cumulative_usage(self) -> types.UsageMetadata:
        return self._cumulative_usage

    @property
    def trajectory_usages(self) -> dict[str, types.UsageMetadata]:
        return dict(self._trajectory_usages)

    @property
    def _last_turn_stop_reason(self) -> types.StopReason:
        return self._last_stop_reason

    def _next_step_index(self) -> int:
        idx = self._step_counter
        self._step_counter += 1
        return idx

    def _make_step(self, **kwargs: Any) -> types.Step:
        idx = self._next_step_index()
        kwargs.setdefault("depth", 0)
        return types.Step(
            id=connection_mod.make_step_id(self._conversation_id, idx),
            step_index=idx,
            trajectory_id=self._conversation_id,
            **kwargs,
        )

    def _add_usage(self, *, prompt_tok: int, cand_tok: int, thought_tok: int) -> None:
        delta = types.UsageMetadata(
            prompt_token_count=prompt_tok,
            cached_content_token_count=0,
            candidates_token_count=cand_tok,
            thoughts_token_count=thought_tok,
            total_token_count=prompt_tok + cand_tok + thought_tok,
        )
        self._cumulative_usage = self._cumulative_usage + delta
        self._trajectory_usages[self._conversation_id] = self._cumulative_usage.model_copy()

    def _check_budget_before_model(self) -> types.StopReason | None:
        b = self._budget_config
        if b is None:
            return None
        if b.max_model_calls is not None and self._model_calls_exceeded():
            return types.StopReason.MAX_MODEL_CALLS_EXCEEDED
        if (
            b.max_total_tokens is not None
            and (self._cumulative_usage.total_token_count or 0) >= b.max_total_tokens
        ):
            return types.StopReason.MAX_TOTAL_TOKENS_EXCEEDED
        return None

    def _model_calls_exceeded(self) -> bool:
        b = self._budget_config
        return bool(
            b is not None
            and b.max_model_calls is not None
            and self._model_call_count >= b.max_model_calls
        )

    def _check_budget_before_tool(self) -> types.StopReason | None:
        b = self._budget_config
        if b is None:
            return None
        if b.max_tool_calls is not None and self._tool_call_count >= b.max_tool_calls:
            return types.StopReason.MAX_TOOL_CALLS_EXCEEDED
        return None

    async def _emit_step_with_hooks(
        self,
        turn_ctx: hooks_mod.TurnContext | None,
        step: types.Step,
    ) -> types.Step:
        if self._hook_runner is not None and turn_ctx is not None:
            await self._hook_runner.dispatch_pre_step(turn_ctx, step)
            await self._hook_runner.dispatch_post_step(turn_ctx, step)
        return step

    async def send(self, prompt: types.Content | None, **kwargs: Any) -> None:
        if self._disconnected:
            raise types.AntigravityConnectionError(
                "OfflineAntigravityConnection has been disconnected."
            )
        self._cancelled = False
        self._is_idle = False
        self._last_stop_reason = types.StopReason.UNSPECIFIED
        self._pending_prompt = prompt
        self._pending_kwargs = dict(kwargs)
        self._has_pending_turn = True

    async def receive_steps(self) -> AsyncIterator[types.Step]:
        if not self._has_pending_turn:
            return

        self._has_pending_turn = False
        prompt = self._pending_prompt
        kwargs = dict(self._pending_kwargs)
        self._pending_prompt = None
        self._pending_kwargs = {}

        try:
            continuation_count = 0
            current_prompt: types.Content | None = prompt
            while True:
                if self._cancelled:
                    yield self._make_step(
                        type=types.StepType.SYSTEM_MESSAGE,
                        source=types.StepSource.SYSTEM,
                        target=types.StepTarget.USER,
                        status=types.StepStatus.CANCELED,
                        error="Turn cancelled by client.",
                    )
                    return

                turn_ctx: hooks_mod.TurnContext | None = None
                if self._hook_runner is not None:
                    pre_res, turn_ctx = await self._hook_runner.dispatch_pre_turn(
                        current_prompt
                    )
                    if not pre_res.allow:
                        err_msg = pre_res.message or "Turn denied by PreTurnHook."
                        step = self._make_step(
                            type=types.StepType.SYSTEM_MESSAGE,
                            source=types.StepSource.SYSTEM,
                            target=types.StepTarget.USER,
                            status=types.StepStatus.ERROR,
                            error=err_msg,
                        )
                        yield await self._emit_step_with_hooks(turn_ctx, step)
                        return
                else:
                    turn_ctx = hooks_mod.TurnContext(hooks_mod.SessionContext())

                budget_stop = self._check_budget_before_model()
                if budget_stop is not None:
                    self._last_stop_reason = budget_stop
                    step = self._make_step(
                        type=types.StepType.SYSTEM_MESSAGE,
                        source=types.StepSource.SYSTEM,
                        target=types.StepTarget.USER,
                        status=types.StepStatus.ERROR,
                        error=f"Budget exceeded: {budget_stop.value}",
                    )
                    yield await self._emit_step_with_hooks(turn_ctx, step)
                    return

                prompt_text = _extract_prompt_text(current_prompt)
                available_tools = (
                    list(self._tool_runner.tool_names)
                    if self._tool_runner is not None
                    else []
                )
                adapter_ctx: dict[str, Any] = {
                    "conversation_id": self._conversation_id,
                    "thinking_level": (
                        self._thinking_level.value
                        if self._thinking_level is not None
                        else None
                    ),
                    "response_schema": self._response_schema,
                    "available_tools": available_tools,
                    "turn_history": list(self._turn_history),
                    "continuation_count": continuation_count,
                    "kwargs": kwargs,
                }
                self._model_call_count += 1
                voice_resp = await self._voice_adapter.generate(
                    prompt_text, context=adapter_ctx
                )

                # Yield internal thinking deltas
                thought_tokens = 0
                accumulated_thoughts: list[str] = []
                for thought in voice_resp.thoughts:
                    if self._cancelled:
                        return
                    if not thought:
                        continue
                    accumulated_thoughts.append(thought)
                    thought_tokens += _estimate_tokens(thought)
                    t_step = self._make_step(
                        type=types.StepType.THINKING,
                        source=types.StepSource.MODEL,
                        target=types.StepTarget.USER,
                        status=types.StepStatus.DONE,
                        thinking="\n".join(accumulated_thoughts),
                        thinking_delta=thought,
                    )
                    yield await self._emit_step_with_hooks(turn_ctx, t_step)

                # Execute any requested tool calls through HookRunner/policy + ToolRunner
                explicit_calls = list(kwargs.get("tool_calls") or ())
                requested_calls = list(voice_resp.tool_calls) + explicit_calls
                tool_summaries: list[str] = []
                for call_idx, raw_call in enumerate(requested_calls):
                    if self._cancelled:
                        return
                    tool_stop = self._check_budget_before_tool()
                    if tool_stop is not None:
                        self._last_stop_reason = tool_stop
                        b_step = self._make_step(
                            type=types.StepType.SYSTEM_MESSAGE,
                            source=types.StepSource.SYSTEM,
                            target=types.StepTarget.USER,
                            status=types.StepStatus.ERROR,
                            error=f"Budget exceeded: {tool_stop.value}",
                        )
                        yield await self._emit_step_with_hooks(turn_ctx, b_step)
                        return

                    if isinstance(raw_call, types.ToolCall):
                        tc = raw_call
                        if not tc.id:
                            tc = tc.model_copy(
                                update={
                                    "id": f"call_{self._step_counter}_{call_idx}",
                                }
                            )
                    else:
                        tc = types.ToolCall(
                            id=str(
                                raw_call.get("id")
                                or f"call_{self._step_counter}_{call_idx}"
                            ),
                            name=str(raw_call["name"]),
                            args=dict(raw_call.get("args") or {}),
                            canonical_path=raw_call.get("canonical_path"),
                            server_name=raw_call.get("server_name"),
                        )

                    op_ctx = hooks_mod.OperationContext(turn_ctx)
                    effective_tc = tc
                    if self._hook_runner is not None:
                        (
                            hook_res,
                            effective_tc,
                            op_ctx,
                        ) = await self._hook_runner.dispatch_pre_tool_call(
                            turn_ctx, tc
                        )
                        if not hook_res.allow:
                            deny_msg = hook_res.message or (
                                f"Tool call '{tc.name}' denied by policy/hook."
                            )
                            deny_step = self._make_step(
                                type=types.StepType.TOOL_CALL,
                                source=types.StepSource.MODEL,
                                target=types.StepTarget.ENVIRONMENT,
                                status=types.StepStatus.ERROR,
                                tool_calls=[effective_tc],
                                error=deny_msg,
                            )
                            yield await self._emit_step_with_hooks(turn_ctx, deny_step)
                            tool_summaries.append(f"{tc.name}: DENIED ({deny_msg})")
                            continue

                    dispatch_step = self._make_step(
                        type=types.StepType.TOOL_CALL,
                        source=types.StepSource.MODEL,
                        target=types.StepTarget.ENVIRONMENT,
                        status=types.StepStatus.ACTIVE,
                        tool_calls=[effective_tc],
                    )
                    effective_tc = effective_tc.model_copy(
                        update={"step_id": dispatch_step.id}
                    )
                    dispatch_step = dispatch_step.model_copy(
                        update={"tool_calls": [effective_tc]}
                    )
                    yield await self._emit_step_with_hooks(turn_ctx, dispatch_step)

                    self._tool_call_count += 1
                    if self._tool_runner is not None:
                        results = await self._tool_runner.process_tool_calls(
                            [effective_tc]
                        )
                        tool_result = results[0]
                    else:
                        tool_result = types.ToolResult(
                            id=effective_tc.id,
                            step_id=effective_tc.step_id,
                            name=effective_tc.name,
                            error="No ToolRunner configured on OfflineAntigravityConnection.",
                        )

                    if tool_result.error:
                        err_exc = tool_result.exception or types.ToolExecutionError(
                            tool_result.error,
                            effective_tc.name,
                            server_name=effective_tc.server_name,
                            call_id=effective_tc.id,
                            step_id=effective_tc.step_id,
                        )
                        display_err = tool_result.error
                        if self._hook_runner is not None:
                            err_hook_res, recovery = (
                                await self._hook_runner.dispatch_on_tool_error(
                                    op_ctx, err_exc
                                )
                            )
                            if (
                                err_hook_res.allow
                                and isinstance(recovery, str)
                                and recovery.strip()
                            ):
                                display_err = recovery
                        err_step = self._make_step(
                            type=types.StepType.TOOL_CALL,
                            source=types.StepSource.SYSTEM,
                            target=types.StepTarget.ENVIRONMENT,
                            status=types.StepStatus.ERROR,
                            tool_calls=[effective_tc],
                            error=display_err,
                        )
                        yield await self._emit_step_with_hooks(turn_ctx, err_step)
                        tool_summaries.append(f"{effective_tc.name}: ERROR ({display_err})")
                    else:
                        if self._hook_runner is not None:
                            await self._hook_runner.dispatch_post_tool_call(
                                op_ctx, tool_result
                            )
                        done_step = self._make_step(
                            type=types.StepType.TOOL_CALL,
                            source=types.StepSource.SYSTEM,
                            target=types.StepTarget.ENVIRONMENT,
                            status=types.StepStatus.DONE,
                            tool_calls=[effective_tc],
                            content=str(tool_result.result),
                        )
                        yield await self._emit_step_with_hooks(turn_ctx, done_step)
                        tool_summaries.append(
                            f"{effective_tc.name}={tool_result.result!r}"
                        )

                # Compose final text (incorporating deterministic tool results when run)
                final_text = voice_resp.text
                if tool_summaries and not final_text:
                    final_text = "Tool results: " + "; ".join(tool_summaries)
                elif tool_summaries:
                    final_text = f"{final_text}\n[tools: {'; '.join(tool_summaries)}]"

                # Stream text response deltas
                chunks = [
                    final_text[i : i + self._chunk_size]
                    for i in range(0, len(final_text), self._chunk_size)
                ] or [""]
                built = ""
                for idx_c, delta in enumerate(chunks):
                    if self._cancelled:
                        return
                    built += delta
                    is_last = idx_c == len(chunks) - 1
                    txt_step = self._make_step(
                        type=types.StepType.TEXT_RESPONSE,
                        source=types.StepSource.MODEL,
                        target=types.StepTarget.USER,
                        status=types.StepStatus.DONE if is_last else types.StepStatus.ACTIVE,
                        content=built,
                        content_delta=delta,
                        is_complete_response=is_last,
                    )
                    yield await self._emit_step_with_hooks(turn_ctx, txt_step)

                if voice_resp.structured_output is not None:
                    fin_step = self._make_step(
                        type=types.StepType.FINISH,
                        source=types.StepSource.MODEL,
                        target=types.StepTarget.USER,
                        status=types.StepStatus.DONE,
                        depth=0,
                        parent_trajectory_id="",
                        structured_output=voice_resp.structured_output,
                    )
                    yield await self._emit_step_with_hooks(turn_ctx, fin_step)

                self._add_usage(
                    prompt_tok=_estimate_tokens(prompt_text),
                    cand_tok=_estimate_tokens(final_text),
                    thought_tok=thought_tokens,
                )
                self._turn_history.append(
                    {
                        "user": prompt_text,
                        "assistant": final_text,
                        "thoughts": list(voice_resp.thoughts),
                        "tool_summaries": tool_summaries,
                    }
                )

                if self._hook_runner is not None:
                    await self._hook_runner.dispatch_post_turn(turn_ctx, final_text)
                    stop_res = await self._hook_runner.dispatch_stop(
                        turn_ctx,
                        types.StopArgs(
                            response_text=final_text,
                            trajectory_id=self._conversation_id,
                            continuation_count=continuation_count,
                            stop_reason=self._last_stop_reason,
                        ),
                    )
                    if (
                        stop_res.decision == types.StopDecision.CONTINUE
                        and continuation_count < self._max_stop_continuations
                    ):
                        continuation_count += 1
                        current_prompt = stop_res.reason
                        kwargs = {}
                        continue

                return
        finally:
            self._is_idle = True

    async def disconnect(self) -> None:
        self._disconnected = True
        self._is_idle = True

    async def cancel(self) -> None:
        self._cancelled = True
        self._is_idle = True

    async def wait_for_idle(self) -> None:
        self._is_idle = True

    async def wait_for_wakeup(self, timeout: float = 300.0) -> bool:
        return False

    async def _send_tool_results(self, results: list[types.ToolResult]) -> None:
        self._pending_tool_results.extend(results)

    async def send_trigger_notification(self, content: str) -> None:
        await self.send(content)


class DualTransportStrategy(connection_mod.ConnectionStrategy):
    """``ConnectionStrategy`` producing deterministic ``OfflineAntigravityConnection`` sessions."""

    def __init__(
        self,
        *,
        tool_runner: tool_runner_mod.ToolRunner | None = None,
        hook_runner: hook_runner_mod.HookRunner | None = None,
        voice_adapter: ReasoningVoiceAdapter | None = None,
        policies: Sequence[policy_mod.Policy | Sequence[policy_mod.Policy]] | None = None,
        mcp_servers: Sequence[types.BaseMcpServerConfig] | None = None,
        conversation_id: str | None = None,
        debug_config: connection_mod.DebugConfig | None = None,
        budget_config: types.BudgetConfig | None = None,
        thinking_level: types.ThinkingLevel | str | None = None,
        response_schema: str | None = None,
        initial_history: Sequence[types.Step] | None = None,
        state_dir: str | Path | None = None,
    ) -> None:
        self._tool_runner = tool_runner
        self._hook_runner = hook_runner
        self._owns_adapter = voice_adapter is None
        self._voice_adapter: ReasoningVoiceAdapter = (
            voice_adapter
            if voice_adapter is not None
            else ZoeOfflineVoiceAdapter(
                state_dir=state_dir,
                thinking_level=thinking_level,
            )
        )
        self._policies = list(policies or ())
        self._mcp_servers = list(mcp_servers or ())
        self._conversation_id = conversation_id or str(uuid.uuid4())
        self._debug_config = debug_config
        self._budget_config = budget_config
        self._thinking_level = _coerce_thinking_level(thinking_level)
        self._response_schema = response_schema
        self._initial_history = list(initial_history or ())
        self._connection: OfflineAntigravityConnection | None = None

        if self._policies:
            policy_hook = policy_mod.enforce(
                self._policies,
                mcp_servers=self._mcp_servers or None,
            )
            if self._hook_runner is not None:
                self._hook_runner.register_hook(policy_hook)

    @property
    def debug_config(self) -> connection_mod.DebugConfig | None:
        return self._debug_config

    @property
    def voice_adapter(self) -> ReasoningVoiceAdapter:
        return self._voice_adapter

    def connect(self) -> OfflineAntigravityConnection:
        if self._connection is None:
            raise RuntimeError(
                "DualTransportStrategy has not been entered; use 'async with strategy:'."
            )
        return self._connection

    async def __aenter__(self) -> None:
        self._connection = OfflineAntigravityConnection(
            voice_adapter=self._voice_adapter,
            tool_runner=self._tool_runner,
            hook_runner=self._hook_runner,
            conversation_id=self._conversation_id,
            debug_config=self._debug_config,
            budget_config=self._budget_config,
            thinking_level=self._thinking_level,
            response_schema=self._response_schema,
            initial_history=self._initial_history,
        )
        if self._hook_runner is not None:
            await self._hook_runner.dispatch_session_start()

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        try:
            if self._hook_runner is not None:
                await self._hook_runner.dispatch_session_end()
        finally:
            if self._connection is not None:
                await self._connection.disconnect()
                self._connection = None
            if self._owns_adapter and isinstance(
                self._voice_adapter, ZoeOfflineVoiceAdapter
            ):
                self._voice_adapter.close()


class DualTransportAgentConfig(connection_mod.AgentConfig):
    """Concrete ``AgentConfig`` wiring ``Agent(...)`` to ``DualTransportStrategy``."""

    mode: Literal["offline", "local_qwen", "gemini", "auto"] = "offline"
    thinking_level: types.ThinkingLevel | str | None = None
    voice_adapter: Any | None = None
    offline_handler: Callable[..., Any] | None = None
    state_dir: str | None = None
    local_qwen_url: str = DEFAULT_LOCAL_QWEN_URL
    local_qwen_model: str = DEFAULT_LOCAL_QWEN_MODEL
    gemini_model: str = "gemini-2.5-flash"

    def __deepcopy__(self, memo: dict[int, Any] | None = None) -> "DualTransportAgentConfig":
        local_memo: dict[int, Any] = {} if memo is None else memo
        if self.voice_adapter is not None and id(self.voice_adapter) not in local_memo:
            local_memo[id(self.voice_adapter)] = self.voice_adapter
        if self.offline_handler is not None and id(self.offline_handler) not in local_memo:
            local_memo[id(self.offline_handler)] = self.offline_handler
        return super().__deepcopy__(local_memo)

    def model_copy(
        self,
        *,
        update: Mapping[str, Any] | None = None,
        deep: bool = False,
    ) -> "DualTransportAgentConfig":
        return super().model_copy(update=update, deep=deep)  # type: ignore[return-value]

    def create_strategy(
        self,
        *,
        tool_runner: Any,
        hook_runner: Any,
    ) -> DualTransportStrategy:
        adapter: ReasoningVoiceAdapter | None = None
        if self.voice_adapter is not None:
            adapter = self.voice_adapter
        elif self.offline_handler is not None:
            adapter = CallableVoiceAdapter(self.offline_handler)

        return DualTransportStrategy(
            tool_runner=tool_runner,
            hook_runner=hook_runner,
            voice_adapter=adapter,
            policies=list(self.policies),
            mcp_servers=list(self.mcp_servers),
            conversation_id=self.conversation_id,
            debug_config=self.debug_config,
            budget_config=self.budget_config,
            thinking_level=self.thinking_level,
            response_schema=(
                str(self.response_schema) if self.response_schema is not None else None
            ),
            state_dir=self.state_dir,
        )


@dataclass(frozen=True)
class TransportResolution:
    """Transparent routing & transport selection telemetry for ``ZoeAntigravityBridge``."""

    requested_mode: str
    selected_mode: str
    config_class: str
    thinking_level: str | None
    stem_decision: dict[str, Any] | None
    local_probe: dict[str, Any] | None
    fallback_applied: bool
    fallback_reason: str | None
    constitutional: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": SDK_BRIDGE_CONTRACT,
            "requested_mode": self.requested_mode,
            "selected_mode": self.selected_mode,
            "config_class": self.config_class,
            "thinking_level": self.thinking_level,
            "stem_decision": self.stem_decision,
            "local_probe": self.local_probe,
            "fallback_applied": self.fallback_applied,
            "fallback_reason": self.fallback_reason,
            "constitutional": dict(self.constitutional),
        }


@dataclass(frozen=True)
class BridgeTurnResult:
    """Result returned by ``ZoeAntigravityBridge.arun_turn`` / ``run_turn``."""

    text: str
    thoughts: tuple[str, ...]
    tool_calls: tuple[dict[str, Any], ...]
    structured_output: Any
    usage_metadata: dict[str, Any] | None
    stop_reason: str
    history_steps: int
    resolution: TransportResolution
    constitutional: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": SDK_BRIDGE_CONTRACT,
            "text": self.text,
            "thoughts": list(self.thoughts),
            "tool_calls": [dict(tc) for tc in self.tool_calls],
            "structured_output": self.structured_output,
            "usage_metadata": self.usage_metadata,
            "stop_reason": self.stop_reason,
            "history_steps": self.history_steps,
            "resolution": self.resolution.to_dict(),
            "constitutional": dict(self.constitutional),
        }


class ZoeAntigravityBridge:
    """Unified dual-transport bridge connecting Zoe Stem-Layering to ``google.antigravity``."""

    def __init__(
        self,
        *,
        mode: Literal["offline", "local_qwen", "gemini", "auto"] = "auto",
        local_qwen_url: str = DEFAULT_LOCAL_QWEN_URL,
        local_qwen_model: str = DEFAULT_LOCAL_QWEN_MODEL,
        gemini_model: str = "gemini-2.5-flash",
        api_key: str | None = None,
        state_dir: str | Path | None = None,
        default_thinking_level: types.ThinkingLevel | str | None = None,
        probe_timeout_sec: float = 0.4,
    ) -> None:
        if mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {mode!r}")
        self.mode = mode
        self.local_qwen_url = local_qwen_url.rstrip("/")
        self.local_qwen_model = local_qwen_model
        self.gemini_model = gemini_model
        self.api_key = api_key
        self.state_dir = str(Path(state_dir).expanduser().resolve()) if state_dir else None
        self.default_thinking_level = _coerce_thinking_level(default_thinking_level)
        self.probe_timeout_sec = float(probe_timeout_sec)

    def _has_gemini_credentials(self) -> bool:
        return bool(
            self.api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )

    def probe_local(self) -> dict[str, Any]:
        """Probe loopback ``llama-server`` cleanly via ``stem_layering.probe_local_qwen``."""
        return probe_local_qwen(self.local_qwen_url, timeout_sec=self.probe_timeout_sec)

    def resolve_transport(
        self,
        prompt: str = "",
        *,
        mode: str | None = None,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        thinking_level: types.ThinkingLevel | str | None = None,
        probe_local: bool = True,
        local_qwen_available: bool | None = None,
    ) -> TransportResolution:
        """Resolve which transport & SDK config class should handle the given task."""
        req_mode = mode or self.mode
        if req_mode not in VALID_MODES:
            raise ValueError(f"mode must be one of {VALID_MODES}, got {req_mode!r}")

        eff_thinking = (
            _coerce_thinking_level(thinking_level)
            if thinking_level is not None
            else self.default_thinking_level
        )

        local_probe_doc: dict[str, Any] | None = None
        qwen_avail = local_qwen_available
        if req_mode == "offline" or offline_only:
            if qwen_avail is None:
                qwen_avail = False
        elif qwen_avail is None and probe_local and req_mode in ("local_qwen", "auto"):
            local_probe_doc = self.probe_local()
            qwen_avail = bool(local_probe_doc.get("available"))

        stem_decision: StemDecision | None = None
        if prompt.strip():
            stem_decision = route_stem(
                prompt,
                offline_only=offline_only or (req_mode == "offline"),
                privacy_sensitive=privacy_sensitive,
                local_qwen_available=qwen_avail,
            )
            if eff_thinking is None and stem_decision.thinking_level:
                eff_thinking = _coerce_thinking_level(stem_decision.thinking_level)

        fallback_applied = False
        fallback_reason: str | None = None
        selected_mode = req_mode

        if req_mode == "offline" or offline_only:
            selected_mode = "offline"
            if req_mode != "offline":
                fallback_applied = True
                fallback_reason = "offline_only constraint enforced deterministic offline bridge."
        elif req_mode == "local_qwen":
            if qwen_avail:
                selected_mode = "local_qwen"
            else:
                selected_mode = "offline"
                fallback_applied = True
                fallback_reason = (
                    f"Loopback Qwen endpoint {self.local_qwen_url}/v1 unreachable; "
                    "fell back cleanly to offline DualTransportStrategy."
                )
        elif req_mode == "gemini":
            if privacy_sensitive:
                selected_mode = "offline"
                fallback_applied = True
                fallback_reason = "privacy_sensitive disables cloud Gemini; fell back to offline."
            elif self._has_gemini_credentials():
                selected_mode = "gemini"
            else:
                selected_mode = "offline"
                fallback_applied = True
                fallback_reason = (
                    "No Gemini API key configured; fell back cleanly to offline DualTransportStrategy."
                )
        else:  # "auto"
            if privacy_sensitive:
                selected_mode = "local_qwen" if qwen_avail else "offline"
                fallback_applied = not qwen_avail
                fallback_reason = (
                    None
                    if qwen_avail
                    else "privacy_sensitive with local_qwen unavailable; using offline."
                )
            elif qwen_avail:
                selected_mode = "local_qwen"
            elif self._has_gemini_credentials() and (
                stem_decision is None
                or stem_decision.selected_tier in ("flash_lite", "flash", "pro")
            ):
                selected_mode = "gemini"
            else:
                selected_mode = "offline"
                fallback_applied = True
                fallback_reason = (
                    "No live loopback or Gemini endpoint active; using deterministic offline bridge."
                )

        config_class_map = {
            "offline": "DualTransportAgentConfig",
            "local_qwen": "LocalOpenAIAgentConfig",
            "gemini": "LocalAgentConfig",
        }
        cloud_tokens = 0  # Resolution itself uses 0 cloud tokens
        return TransportResolution(
            requested_mode=req_mode,
            selected_mode=selected_mode,
            config_class=config_class_map[selected_mode],
            thinking_level=eff_thinking.value if eff_thinking is not None else None,
            stem_decision=stem_decision.to_dict() if stem_decision is not None else None,
            local_probe=local_probe_doc,
            fallback_applied=fallback_applied,
            fallback_reason=fallback_reason,
            constitutional=bridge_constitutional_metadata(cloud_tokens_used=cloud_tokens),
        )

    def build_local_qwen_config(
        self,
        *,
        system_instructions: str | types.SystemInstructions | None = None,
        tools: Sequence[Callable[..., Any]] | None = None,
        policies: Sequence[policy_mod.Policy | Sequence[policy_mod.Policy]] | None = None,
        hooks: Sequence[hooks_mod.Hook] | None = None,
        workspaces: Sequence[str] | None = None,
    ) -> LocalOpenAIAgentConfig:
        """Build ``LocalOpenAIAgentConfig(...).lightweight()`` for loopback Qwen2.5-3B."""
        kwargs: dict[str, Any] = {
            "model": self.local_qwen_model,
            "base_url": f"{self.local_qwen_url}/v1",
        }
        if system_instructions is not None:
            kwargs["system_instructions"] = system_instructions
        if tools is not None:
            kwargs["tools"] = list(tools)
        if policies is not None:
            kwargs["policies"] = list(policies)
        if hooks is not None:
            kwargs["hooks"] = list(hooks)
        if workspaces is not None:
            kwargs["workspaces"] = list(workspaces)
        return LocalOpenAIAgentConfig(**kwargs).lightweight()

    def build_gemini_config(
        self,
        *,
        thinking_level: types.ThinkingLevel | str | None = None,
        system_instructions: str | types.SystemInstructions | None = None,
        tools: Sequence[Callable[..., Any]] | None = None,
        policies: Sequence[policy_mod.Policy | Sequence[policy_mod.Policy]] | None = None,
        hooks: Sequence[hooks_mod.Hook] | None = None,
        workspaces: Sequence[str] | None = None,
    ) -> LocalAgentConfig:
        """Build a ``google.antigravity.LocalAgentConfig`` with ``ThinkingLevel`` options."""
        eff_level = _coerce_thinking_level(thinking_level) or self.default_thinking_level
        endpoint = types.GeminiAPIEndpoint(
            api_key=self.api_key or os.environ.get("GEMINI_API_KEY"),
            options=(
                types.GeminiModelOptions(thinking_level=eff_level)
                if eff_level is not None
                else None
            ),
        )
        target = types.ModelTarget(
            name=self.gemini_model,
            types=[types.ModelType.TEXT],
            endpoint=endpoint,
        )
        kwargs: dict[str, Any] = {
            "model": target,
            "api_key": self.api_key,
        }
        if system_instructions is not None:
            kwargs["system_instructions"] = system_instructions
        if tools is not None:
            kwargs["tools"] = list(tools)
        if policies is not None:
            kwargs["policies"] = list(policies)
        if hooks is not None:
            kwargs["hooks"] = list(hooks)
        if workspaces is not None:
            kwargs["workspaces"] = list(workspaces)
        return LocalAgentConfig(**kwargs)

    def create_config(
        self,
        *,
        mode: str | None = None,
        prompt: str = "",
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        thinking_level: types.ThinkingLevel | str | None = None,
        system_instructions: str | types.SystemInstructions | None = None,
        capabilities: types.CapabilitiesConfig | None = None,
        tools: Sequence[Callable[..., Any]] | None = None,
        policies: Sequence[policy_mod.Policy | Sequence[policy_mod.Policy]] | None = None,
        hooks: Sequence[hooks_mod.Hook] | None = None,
        workspaces: Sequence[str] | None = None,
        response_schema: dict[str, Any] | type[pydantic.BaseModel] | str | None = None,
        budget_config: types.BudgetConfig | None = None,
        voice_adapter: ReasoningVoiceAdapter | None = None,
        offline_handler: Callable[..., Any] | None = None,
        probe_local: bool = True,
        local_qwen_available: bool | None = None,
        allow_fallback: bool = True,
    ) -> connection_mod.AgentConfig:
        """Create the resolved ``AgentConfig`` for the requested transport mode."""
        req_mode = mode or self.mode
        resolution = self.resolve_transport(
            prompt,
            mode=req_mode,
            offline_only=offline_only,
            privacy_sensitive=privacy_sensitive,
            thinking_level=thinking_level,
            probe_local=probe_local,
            local_qwen_available=local_qwen_available,
        )
        if not allow_fallback and resolution.fallback_applied and req_mode in ("local_qwen", "gemini"):
            raise RuntimeError(resolution.fallback_reason or f"Transport {req_mode!r} unavailable.")

        if resolution.selected_mode == "local_qwen":
            return self.build_local_qwen_config(
                system_instructions=system_instructions,
                tools=tools,
                policies=policies,
                hooks=hooks,
                workspaces=workspaces,
            )
        if resolution.selected_mode == "gemini":
            return self.build_gemini_config(
                thinking_level=resolution.thinking_level,
                system_instructions=system_instructions,
                tools=tools,
                policies=policies,
                hooks=hooks,
                workspaces=workspaces,
            )

        cfg_kwargs: dict[str, Any] = {
            "mode": "offline",
            "thinking_level": resolution.thinking_level,
            "state_dir": self.state_dir,
            "voice_adapter": voice_adapter,
            "offline_handler": offline_handler,
            "local_qwen_url": self.local_qwen_url,
            "local_qwen_model": self.local_qwen_model,
            "gemini_model": self.gemini_model,
        }
        if system_instructions is not None:
            cfg_kwargs["system_instructions"] = system_instructions
        if capabilities is not None:
            cfg_kwargs["capabilities"] = capabilities
        if tools is not None:
            cfg_kwargs["tools"] = list(tools)
        if policies is not None:
            cfg_kwargs["policies"] = list(policies)
        if hooks is not None:
            cfg_kwargs["hooks"] = list(hooks)
        if workspaces is not None:
            cfg_kwargs["workspaces"] = list(workspaces)
        if response_schema is not None:
            cfg_kwargs["response_schema"] = response_schema
        if budget_config is not None:
            cfg_kwargs["budget_config"] = budget_config
        return DualTransportAgentConfig(**cfg_kwargs)

    def create_agent(self, **kwargs: Any) -> Agent:
        """Create a configured ``google.antigravity.Agent`` ready for ``async with``."""
        config = self.create_config(**kwargs)
        return Agent(config)

    async def arun_turn(
        self,
        prompt: types.Content,
        *,
        mode: str | None = None,
        offline_only: bool = False,
        privacy_sensitive: bool = False,
        thinking_level: types.ThinkingLevel | str | None = None,
        tools: Sequence[Callable[..., Any]] | None = None,
        policies: Sequence[policy_mod.Policy | Sequence[policy_mod.Policy]] | None = None,
        hooks: Sequence[hooks_mod.Hook] | None = None,
        response_schema: dict[str, Any] | type[pydantic.BaseModel] | str | None = None,
        budget_config: types.BudgetConfig | None = None,
        voice_adapter: ReasoningVoiceAdapter | None = None,
        offline_handler: Callable[..., Any] | None = None,
        probe_local: bool = True,
        local_qwen_available: bool | None = None,
    ) -> BridgeTurnResult:
        """Run a full ``Agent.chat(prompt)`` turn and return structured telemetry."""
        prompt_text = _extract_prompt_text(prompt)
        resolution = self.resolve_transport(
            prompt_text,
            mode=mode,
            offline_only=offline_only,
            privacy_sensitive=privacy_sensitive,
            thinking_level=thinking_level,
            probe_local=probe_local,
            local_qwen_available=local_qwen_available,
        )
        agent = self.create_agent(
            mode=mode,
            prompt=prompt_text,
            offline_only=offline_only,
            privacy_sensitive=privacy_sensitive,
            thinking_level=thinking_level,
            tools=tools,
            policies=policies,
            hooks=hooks,
            response_schema=response_schema,
            budget_config=budget_config,
            voice_adapter=voice_adapter,
            offline_handler=offline_handler,
            probe_local=probe_local,
            local_qwen_available=local_qwen_available,
        )
        async with agent:
            response = await agent.chat(prompt)
            thoughts = tuple([t async for t in response.thoughts])
            tool_calls = tuple(
                [
                    {"id": tc.id, "name": str(tc.name), "args": dict(tc.args)}
                    async for tc in response.tool_calls
                ]
            )
            text = await response.text()
            structured = await response.structured_output()
            usage = (
                response.usage_metadata.model_dump()
                if response.usage_metadata is not None
                else None
            )
            stop_reason = response.stop_reason.value
            history_steps = len(agent.conversation.history)

        cloud_tokens = 0
        if resolution.selected_mode == "gemini" and usage:
            cloud_tokens = int(usage.get("total_token_count") or 0)
        return BridgeTurnResult(
            text=text,
            thoughts=thoughts,
            tool_calls=tool_calls,
            structured_output=structured,
            usage_metadata=usage,
            stop_reason=stop_reason,
            history_steps=history_steps,
            resolution=resolution,
            constitutional=bridge_constitutional_metadata(cloud_tokens_used=cloud_tokens),
        )

    def run_turn(self, prompt: types.Content, **kwargs: Any) -> BridgeTurnResult:
        """Synchronous convenience wrapper around ``arun_turn``."""
        return run_coro_sync(self.arun_turn(prompt, **kwargs))


__all__ = [
    "ATTRIBUTION_TEXT",
    "BridgeTurnResult",
    "CallableVoiceAdapter",
    "DualTransportAgentConfig",
    "DualTransportStrategy",
    "OfflineAntigravityConnection",
    "ReasoningVoiceAdapter",
    "SDK_BRIDGE_CONTRACT",
    "TransportResolution",
    "VALID_MODES",
    "VoiceResponse",
    "ZoeAntigravityBridge",
    "ZoeOfflineVoiceAdapter",
    "bridge_constitutional_metadata",
    "run_coro_sync",
]
