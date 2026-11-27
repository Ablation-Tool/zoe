"""Tests for Zoe x Antigravity Shared-Reasoning foundation & dual-transport SDK bridge."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys
from typing import Any
from unittest import mock

import pydantic
import pytest

from google.antigravity import (
    Agent,
    LocalAgentConfig,
    LocalOpenAIAgentConfig,
    ToolContext,
    types,
)
from google.antigravity.conversation.conversation import Conversation
from google.antigravity.hooks import hook_runner as hook_runner_mod
from google.antigravity.hooks import hooks
from google.antigravity.hooks import policy
from google.antigravity.tools import tool_runner as tool_runner_mod

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

import zoe_autonomy.shared_reasoning as sr  # noqa: E402
from zoe_autonomy.shared_reasoning import (  # noqa: E402
    CONSTITUTIONAL_METADATA,
    SHARED_REASONING_CONTRACT,
    CallableVoiceAdapter,
    DualTransportAgentConfig,
    DualTransportStrategy,
    OfflineAntigravityConnection,
    ReasoningVoiceAdapter,
    VoiceResponse,
    ZoeAntigravityBridge,
    available_submodules,
    run_coro_sync,
)


def _assert_constitutional(doc: dict[str, Any]) -> None:
    assert doc["external_actions"] == 0
    assert doc["sentience_claimed"] is False
    assert doc["l5_agi_qualified"] is False
    assert doc["zoe_clone_claimed"] is False
    assert doc["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


def test_package_contract_and_lazy_submodules() -> None:
    assert SHARED_REASONING_CONTRACT == "zoe-antigravity-shared-reasoning/v1"
    _assert_constitutional(CONSTITUTIONAL_METADATA)
    avail = available_submodules()
    assert avail["sdk_bridge"] is True
    assert "blackboard" in avail
    with pytest.raises(AttributeError):
        _ = sr.nonexistent_symbol_xyz


def test_offline_connection_and_strategy_lifecycle() -> None:
    strategy = DualTransportStrategy()
    with pytest.raises(RuntimeError, match="not been entered"):
        strategy.connect()

    async def _run() -> None:
        async with strategy:
            conn = strategy.connect()
            assert isinstance(conn, OfflineAntigravityConnection)
            assert conn.is_idle is True
            assert conn.conversation_id
            assert await conn.wait_for_wakeup(0.01) is False
            await conn.disconnect()
            with pytest.raises(types.AntigravityConnectionError):
                await conn.send("after disconnect")

    run_coro_sync(_run())


def test_conversation_streaming_steps_thoughts_tools_and_structured_output() -> None:
    def add_numbers(a: int, b: int) -> int:
        """Add two integers deterministically."""
        return a + b

    async def scripted_handler(prompt: str, context: dict[str, Any]) -> VoiceResponse:
        return VoiceResponse(
            text=f"Evaluated: {prompt}",
            thoughts=(
                f"step1: thinking_level={context.get('thinking_level')}",
                "step2: invoking add_numbers(2, 3)",
            ),
            tool_calls=({"name": "add_numbers", "args": {"a": 2, "b": 3}},),
            structured_output={"sum": 5, "prompt": prompt},
        )

    async def _run() -> None:
        tr = tool_runner_mod.ToolRunner(tools=[add_numbers])
        hr = hook_runner_mod.HookRunner()
        strategy = DualTransportStrategy(
            tool_runner=tr,
            hook_runner=hr,
            voice_adapter=CallableVoiceAdapter(scripted_handler),
            thinking_level=types.ThinkingLevel.HIGH,
            response_schema='{"type": "object"}',
        )
        async with Conversation.create(strategy) as conv:
            resp = await conv.chat("compute 2+3")
            thoughts = [t async for t in resp.thoughts]
            tool_calls = [tc async for tc in resp.tool_calls]
            text = await resp.text()
            structured = await resp.structured_output()

            assert len(thoughts) == 2
            assert "thinking_level=high" in thoughts[0]
            assert len(tool_calls) == 1
            assert tool_calls[0].name == "add_numbers"
            assert tool_calls[0].args == {"a": 2, "b": 3}
            assert "Evaluated: compute 2+3" in text
            assert "add_numbers=5" in text
            assert structured == {"sum": 5, "prompt": "compute 2+3"}
            assert resp.usage_metadata is not None
            assert (resp.usage_metadata.total_token_count or 0) > 0
            assert conv.turn_count == 1
            assert any(s.type == types.StepType.THINKING for s in conv.history)
            assert any(
                s.type == types.StepType.TOOL_CALL and s.status == types.StepStatus.DONE
                for s in conv.history
            )
            assert any(s.type == types.StepType.FINISH for s in conv.history)

            # Second turn in the same Conversation
            resp2 = await conv.chat("follow-up")
            text2 = await resp2.text()
            assert "Evaluated: follow-up" in text2
            assert conv.turn_count == 2
            assert conv.last_response == text2

    run_coro_sync(_run())


def test_agent_with_hooks_tool_context_and_policies() -> None:
    events: list[str] = []

    def inspect_history_tool(ctx: ToolContext, label: str) -> str:
        """Tool receiving injected ToolContext from Agent."""
        ctx.set_state("last_label", label)
        return f"{label}:has_cid={bool(ctx.conversation_id)}"

    def dangerous_tool(cmd: str) -> str:
        return f"ran:{cmd}"

    @hooks.on_session_start
    def _on_start() -> None:
        events.append("session_start")

    @hooks.on_session_end
    def _on_end() -> None:
        events.append("session_end")

    @hooks.pre_turn
    def _pre_turn(prompt: types.Content) -> types.HookResult:
        events.append(f"pre_turn:{prompt}")
        return types.HookResult(allow=True)

    @hooks.post_tool_call
    def _post_tool(result: types.ToolResult) -> None:
        events.append(f"post_tool:{result.name}={result.result}")

    @hooks.post_turn
    def _post_turn(response: str) -> None:
        events.append(f"post_turn:{len(response)}")

    def _handler(prompt: str) -> dict[str, Any]:
        return {
            "text": "policy check complete",
            "thoughts": ["checking allowed and denied tools"],
            "tool_calls": [
                {"name": "inspect_history_tool", "args": {"label": "ok"}},
                {"name": "dangerous_tool", "args": {"cmd": "rm -rf"}},
            ],
        }

    cfg = DualTransportAgentConfig(
        thinking_level=types.ThinkingLevel.MEDIUM,
        tools=[inspect_history_tool, dangerous_tool],
        policies=[
            policy.deny("dangerous_tool", reason="Blocked by safety policy"),
            policy.allow_all(),
        ],
        hooks=[_on_start, _on_end, _pre_turn, _post_tool, _post_turn],
        offline_handler=_handler,
    )

    async def _run() -> None:
        async with Agent(cfg) as agent:
            resp = await agent.chat("run policy test")
            text = await resp.text()
            assert "inspect_history_tool='ok:has_cid=True'" in text
            assert "dangerous_tool: DENIED (Blocked by safety policy)" in text
            err_steps = [
                s
                for s in agent.conversation.history
                if s.type == types.StepType.TOOL_CALL and s.status == types.StepStatus.ERROR
            ]
            assert len(err_steps) == 1
            assert "Blocked by safety policy" in err_steps[0].error

    run_coro_sync(_run())
    assert "session_start" in events
    assert "session_end" in events
    assert "pre_turn:run policy test" in events
    assert "post_tool:inspect_history_tool=ok:has_cid=True" in events
    assert not any("post_tool:dangerous_tool" in e for e in events)
    assert any(e.startswith("post_turn:") for e in events)


def test_agent_tool_error_hook_and_budget_enforcement() -> None:
    def failing_tool() -> str:
        raise ValueError("boom")

    @hooks.on_tool_error
    def _recover_err(exc: Exception) -> str:
        return f"recovered_error:{exc}"

    def _handler(_prompt: str) -> dict[str, Any]:
        return {
            "text": "handled",
            "tool_calls": [{"name": "failing_tool", "args": {}}],
        }

    cfg = DualTransportAgentConfig(
        tools=[failing_tool],
        hooks=[_recover_err],
        offline_handler=_handler,
        budget_config=types.BudgetConfig(max_model_calls=1),
    )

    async def _run() -> None:
        async with Agent(cfg) as agent:
            resp1 = await agent.chat("first")
            txt1 = await resp1.text()
            assert "recovered_error:boom" in txt1

            resp2 = await agent.chat("second exceeds budget")
            _ = await resp2.text()
            assert resp2.stop_reason == types.StopReason.MAX_MODEL_CALLS_EXCEEDED

    run_coro_sync(_run())


def test_zoe_antigravity_bridge_offline_and_stem_integration(tmp_path: Path) -> None:
    bridge = ZoeAntigravityBridge(
        mode="offline",
        state_dir=tmp_path / "eliza_state",
        default_thinking_level=types.ThinkingLevel.HIGH,
    )
    res = bridge.run_turn("architect multi-file theorem verification")
    assert res.resolution.selected_mode == "offline"
    assert res.resolution.config_class == "DualTransportAgentConfig"
    assert res.resolution.stem_decision is not None
    assert res.resolution.stem_decision["selected_tier"] == "gear1_eliza"
    assert len(res.thoughts) >= 3
    assert "[stem_layering]" in res.thoughts[0]
    assert "[constitution]" in res.thoughts[-1]
    assert res.text
    _assert_constitutional(res.constitutional)

    # Confirm VoiceAdapter protocol conformance
    adapter = bridge.create_agent(mode="offline")._config.create_strategy(
        tool_runner=None,
        hook_runner=None,
    ).voice_adapter
    assert isinstance(adapter, ReasoningVoiceAdapter)


def test_bridge_mode_switching_auto_local_qwen_and_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    bridge = ZoeAntigravityBridge(mode="auto")

    # 1. Auto with loopback unreachable and no API key -> clean offline fallback
    with mock.patch(
        "zoe_autonomy.shared_reasoning.sdk_bridge.probe_local_qwen",
        return_value={"available": False, "endpoint": "http://127.0.0.1:8080/v1/models", "models": []},
    ):
        r_auto_off = bridge.resolve_transport("implement unit test for parse_config")
        assert r_auto_off.selected_mode == "offline"
        assert r_auto_off.fallback_applied is True
        cfg_off = bridge.create_config(prompt="implement unit test for parse_config")
        assert isinstance(cfg_off, DualTransportAgentConfig)

    # 2. Auto with loopback Qwen reachable -> LocalOpenAIAgentConfig.lightweight()
    with mock.patch(
        "zoe_autonomy.shared_reasoning.sdk_bridge.probe_local_qwen",
        return_value={
            "available": True,
            "endpoint": "http://127.0.0.1:8080/v1/models",
            "models": ["qwen2.5-3b-instruct"],
        },
    ):
        r_qwen = bridge.resolve_transport("brainstorm local notes")
        assert r_qwen.selected_mode == "local_qwen"
        assert r_qwen.config_class == "LocalOpenAIAgentConfig"
        cfg_qwen = bridge.create_config(prompt="brainstorm local notes")
        assert isinstance(cfg_qwen, LocalOpenAIAgentConfig)
        assert cfg_qwen.base_url == "http://127.0.0.1:8080/v1"
        assert cfg_qwen.model == "qwen2.5-3b-instruct"
        assert cfg_qwen.capabilities.agent_behavior == types.AgentBehavior.MINIMAL

    # 3. Gemini mode without key falls back when allow_fallback=True, raises when False
    r_gem_fb = bridge.resolve_transport("summarize readme", mode="gemini", probe_local=False)
    assert r_gem_fb.selected_mode == "offline"
    assert r_gem_fb.fallback_applied is True
    with pytest.raises(RuntimeError, match="No Gemini API key"):
        bridge.create_config(mode="gemini", prompt="summarize readme", allow_fallback=False)

    # 4. Gemini mode with explicit API key creates LocalAgentConfig with ThinkingLevel
    gem_bridge = ZoeAntigravityBridge(mode="gemini", api_key="test-key-not-used-online")
    cfg_gem = gem_bridge.create_config(
        prompt="architect formal verification",
        thinking_level=types.ThinkingLevel.EXTRA_HIGH,
        probe_local=False,
    )
    assert isinstance(cfg_gem, LocalAgentConfig)
    assert cfg_gem.models is not None
    text_targets = [m for m in cfg_gem.models if types.ModelType.TEXT in m.types]
    assert text_targets[0].endpoint.options.thinking_level == types.ThinkingLevel.EXTRA_HIGH

    # 5. privacy_sensitive overrides gemini mode
    r_priv = gem_bridge.resolve_transport(
        "analyze private medical record",
        mode="gemini",
        privacy_sensitive=True,
        probe_local=False,
    )
    assert r_priv.selected_mode == "offline"
    assert r_priv.fallback_applied is True


def test_run_coro_sync_works_inside_running_event_loop() -> None:
    async def _inner() -> int:
        await asyncio.sleep(0)
        return 42

    async def _outer() -> int:
        return run_coro_sync(_inner())

    assert asyncio.run(_outer()) == 42


def test_structured_output_schema_with_pydantic_model() -> None:
    class SumModel(pydantic.BaseModel):
        reply: str
        tier: str

    bridge = ZoeAntigravityBridge(mode="offline")
    res = bridge.run_turn("hello zoe", response_schema=SumModel)
    assert isinstance(res.structured_output, dict)
    assert res.structured_output["tier"] == "gear1_eliza"
    assert res.structured_output["reply"]


def test_stop_hook_continuation_ask_user_policy_and_cancel() -> None:
    stop_calls = 0
    asked_tools: list[str] = []

    @hooks.stop
    def _stop_once(args: types.StopArgs) -> types.StopHookResult:
        nonlocal stop_calls
        stop_calls += 1
        if args.continuation_count == 0:
            return types.StopHookResult(
                decision=types.StopDecision.CONTINUE,
                reason="verify final pass",
            )
        return types.StopHookResult(decision=types.StopDecision.ALLOW_STOP)

    def _ask_handler(tc: types.ToolCall) -> bool:
        asked_tools.append(str(tc.name))
        return tc.args.get("approved", False)

    def gated_tool(approved: bool = False) -> str:
        return f"approved={approved}"

    def _handler(prompt: str, context: dict[str, Any]) -> VoiceResponse:
        if context.get("continuation_count", 0) == 0:
            return VoiceResponse(
                text="initial",
                tool_calls=(
                    {"name": "gated_tool", "args": {"approved": True}},
                    {"name": "gated_tool", "args": {"approved": False}},
                ),
            )
        return VoiceResponse(text=f"continued:{prompt}")

    cfg = DualTransportAgentConfig(
        tools=[gated_tool],
        policies=[policy.ask_user("gated_tool", handler=_ask_handler)],
        hooks=[_stop_once],
        offline_handler=_handler,
    )

    async def _run() -> None:
        async with Agent(cfg) as agent:
            resp = await agent.chat("start gated")
            text = await resp.text()
            assert "gated_tool='approved=True'" in text
            assert "DENIED" in text
            assert "continued:verify final pass" in text

            # Also verify cancel() transitions cleanly
            await agent.conversation.send("pending turn")
            await agent.conversation.cancel()
            steps = [s async for s in agent.conversation.receive_steps()]
            assert len(steps) == 1
            assert steps[0].status == types.StepStatus.CANCELED

    run_coro_sync(_run())
    assert stop_calls == 2
    assert asked_tools == ["gated_tool", "gated_tool"]

