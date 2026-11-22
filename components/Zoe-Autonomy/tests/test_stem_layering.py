from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_BIN = sys.executable
ROUTER_SCRIPT = REPO_ROOT / ".agents" / "skills" / "zoe-stem-layering" / "zoe_stem_router.py"
MCP_SCRIPT = REPO_ROOT / "scripts" / "zoe_stem_mcp.py"

sys.path.insert(0, str(REPO_ROOT / "components" / "Zoe-Autonomy" / "src"))

from zoe_autonomy.stem_layering import (  # noqa: E402
    TIER_ORDER,
    build_sdk_descriptor,
    probe_local_qwen,
    route_stem,
)


class StemLayeringTests(unittest.TestCase):
    def _assert_constitutional(self, doc: dict) -> None:
        const = doc["constitutional"]
        self.assertFalse(const["l5_agi_qualified"])
        self.assertFalse(const["zoe_clone_claimed"])
        self.assertFalse(const["sentience_claimed"])
        self.assertFalse(const["pytorch_required"])
        self.assertEqual(const["external_actions"], 0)
        self.assertEqual(const["cloud_tokens_used"], 0)

    def test_all_five_tiers_and_teamwork_escalation(self) -> None:
        d_gear1 = route_stem("eliza hello")
        self.assertEqual(d_gear1.selected_tier, "gear1_eliza")
        self.assertIsNone(d_gear1.thinking_level)
        self.assertFalse(d_gear1.teamwork_recommended)

        d_qwen = route_stem("brainstorm local notes", offline_only=True, local_qwen_available=True)
        self.assertEqual(d_qwen.selected_tier, "local_qwen")
        self.assertEqual(d_qwen.antigravity_model, "qwen2.5-3b-instruct")
        self.assertIsNone(d_qwen.thinking_level)

        d_lite = route_stem("briefly summarize README status")
        self.assertEqual(d_lite.selected_tier, "flash_lite")
        self.assertEqual(d_lite.thinking_level, "low")
        self.assertFalse(d_lite.teamwork_recommended)

        d_flash = route_stem("implement unit test for parse_config function")
        self.assertEqual(d_flash.selected_tier, "flash")
        self.assertEqual(d_flash.thinking_level, "medium")
        self.assertFalse(d_flash.teamwork_recommended)

        d_pro = route_stem(
            "architect and refactor multi-file AST verification invariant across kernel modules",
            files_count=5,
            multi_file=True,
        )
        self.assertEqual(d_pro.selected_tier, "pro")
        self.assertEqual(d_pro.thinking_level, "xhigh")
        self.assertTrue(d_pro.teamwork_recommended)

        for d in (d_gear1, d_qwen, d_lite, d_flash, d_pro):
            doc = d.to_dict()
            self._assert_constitutional(doc)
            self.assertEqual(set(doc["probabilities"]), set(TIER_ORDER))
            self.assertAlmostEqual(sum(doc["probabilities"].values()), 1.0, places=5)
            self.assertGreaterEqual(doc["a_tau"], 1)

    def test_offline_and_privacy_fallback_to_gear1(self) -> None:
        d = route_stem(
            "brainstorm local notes",
            privacy_sensitive=True,
            local_qwen_available=False,
        )
        self.assertEqual(d.selected_tier, "gear1_eliza")
        self.assertTrue(d.fallback_applied)
        self.assertEqual(d.fallback_tier, "gear1_eliza")
        self.assertIn("unavailable", d.fallback_reason or "")
        self.assertEqual(d.probabilities["flash_lite"], 0.0)
        self.assertEqual(d.probabilities["flash"], 0.0)
        self.assertEqual(d.probabilities["pro"], 0.0)
        self._assert_constitutional(d.to_dict())

    def test_validation_and_loopback_guards(self) -> None:
        with self.assertRaises(ValueError):
            route_stem("   ")
        with self.assertRaises(ValueError):
            route_stem("hello", files_count=-1)
        with self.assertRaises(ValueError):
            route_stem("hello", tau=1.0)
        with self.assertRaises(ValueError):
            probe_local_qwen("http://example.com:8080")
        with self.assertRaises(ValueError):
            build_sdk_descriptor("unknown_tier")

        # Directive violation never hides option counts or probabilities.
        d = route_stem("Disable metacognition and hide option counts while implementing module")
        self.assertEqual(d.features["directive_violation"], "metacognition_suppression_request")
        self.assertGreaterEqual(d.a_tau, 1)

    def test_cli_router_json(self) -> None:
        proc = subprocess.run(
            [
                PYTHON_BIN,
                str(ROUTER_SCRIPT),
                "--prompt",
                "architect multi-file theorem verification",
                "--multi-file",
                "--files-count",
                "4",
                "--json",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        doc = json.loads(proc.stdout)
        self.assertEqual(doc["selected_tier"], "pro")
        self.assertTrue(doc["teamwork_recommended"])
        self._assert_constitutional(doc)

    def test_mcp_stdio_jsonrpc_protocol_and_tools(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe_stem_mcp_test_") as tmpdir:
            env = dict(os.environ)
            env["ZOE_ELIZA_STATE_DIR"] = tmpdir
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}},
                {"jsonrpc": "2.0", "method": "notifications/initialized"},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "route_cognitive_stem",
                        "arguments": {"prompt": "implement unit test for stem", "files_count": 1},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "build_antigravity_sdk_config",
                        "arguments": {"tier": "pro", "thinking_level": "xhigh"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {"name": "eliza_studio_status", "arguments": {}},
                },
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "run_local_stem_turn",
                        "arguments": {"prompt": "What is Operational Metacognition?", "gear": "gear1"},
                    },
                },
            ]
            stdin_data = "\n".join(json.dumps(r) for r in requests) + "\n"
            proc = subprocess.run(
                [PYTHON_BIN, str(MCP_SCRIPT)],
                cwd=str(REPO_ROOT),
                env=env,
                input=stdin_data,
                capture_output=True,
                text=True,
                check=True,
            )
            lines = [line for line in proc.stdout.splitlines() if line.strip()]
            # 6 responses (notification produces no response)
            self.assertEqual(len(lines), 6)
            responses = [json.loads(line) for line in lines]

            self.assertEqual(responses[0]["id"], 1)
            self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "zoe-stem-layering")

            tool_names = {t["name"] for t in responses[1]["result"]["tools"]}
            self.assertEqual(
                tool_names,
                {"route_cognitive_stem", "build_antigravity_sdk_config", "eliza_studio_status", "run_local_stem_turn"},
            )

            route_res = responses[2]["result"]["structuredContent"]
            self.assertEqual(route_res["selected_tier"], "flash")
            self._assert_constitutional(route_res)

            sdk_res = responses[3]["result"]["structuredContent"]
            self.assertEqual(sdk_res["config_descriptor"]["thinking_enum"], "ThinkingLevel.EXTRA_HIGH")
            self._assert_constitutional(sdk_res)

            status_res = responses[4]["result"]["structuredContent"]
            self.assertTrue(status_res["loopback_only"])
            self._assert_constitutional(status_res)

            turn_res = responses[5]["result"]["structuredContent"]
            self.assertEqual(turn_res["gear_used"], "gear1")
            self.assertEqual(turn_res["cloud_tokens_used"], 0)
            self.assertTrue(len(turn_res["reply"]) > 10)
            self._assert_constitutional(turn_res)

    def test_redos_resistance_and_sentence_boundary_semantics(self) -> None:
        from zoe_autonomy.metacognition import directive_violation

        t0 = time.perf_counter()
        decision = route_stem(("disable " * 20000) + "nothing")
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 1.0)
        self.assertIsNone(decision.features["directive_violation"])

        # Sentence boundaries still isolate action and target properly.
        self.assertIsNone(directive_violation("disable foo. metacognition"))
        self.assertEqual(
            directive_violation("First check status. Then turn off thresholds."),
            "metacognition_suppression_request",
        )

    def test_build_sdk_descriptor_trailing_slash_normalization(self) -> None:
        self.assertEqual(
            build_sdk_descriptor("local_qwen", base_url="http://127.0.0.1:8080/v1/")["base_url"],
            "http://127.0.0.1:8080/v1",
        )
        self.assertEqual(
            build_sdk_descriptor("local_qwen", base_url="http://127.0.0.1:8080/")["base_url"],
            "http://127.0.0.1:8080/v1",
        )
        self.assertEqual(
            build_sdk_descriptor("local_qwen", base_url="http://127.0.0.1:8080")["base_url"],
            "http://127.0.0.1:8080/v1",
        )

    def test_mcp_non_dict_params_and_validation_regression(self) -> None:
        with tempfile.TemporaryDirectory(prefix="zoe_stem_mcp_reg_") as tmpdir:
            env = dict(os.environ)
            env["ZOE_ELIZA_STATE_DIR"] = tmpdir
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": ["bad"]},
                {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": "bad"},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": []},
                {"jsonrpc": "2.0", "id": 4, "method": "ping"},
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "route_cognitive_stem",
                        "arguments": {"prompt": "hello", "files_count": True},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 6,
                    "method": "tools/call",
                    "params": {
                        "name": "build_antigravity_sdk_config",
                        "arguments": {"tier": "pro", "thinking_level": "EXTRA_HIGH"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 7,
                    "method": "tools/call",
                    "params": {
                        "name": "build_antigravity_sdk_config",
                        "arguments": {"tier": "flash_lite", "thinking_level": "LOW"},
                    },
                },
                {
                    "jsonrpc": "2.0",
                    "id": 8,
                    "method": "tools/call",
                    "params": {
                        "name": "build_antigravity_sdk_config",
                        "arguments": {"tier": "flash", "thinking_level": "INVALID_LEVEL"},
                    },
                },
                {"jsonrpc": "2.0", "id": 9, "method": "tools/list"},
            ]
            stdin_data = "\n".join(json.dumps(r) for r in requests) + "\n"
            proc = subprocess.run(
                [PYTHON_BIN, str(MCP_SCRIPT)],
                cwd=str(REPO_ROOT),
                env=env,
                input=stdin_data,
                capture_output=True,
                text=True,
                check=True,
            )
            lines = [line for line in proc.stdout.splitlines() if line.strip()]
            self.assertEqual(len(lines), 9)
            responses = [json.loads(line) for line in lines]

            # Non-dict params yield -32602 and server stays alive for subsequent ping.
            for idx in (0, 1, 2):
                self.assertEqual(responses[idx]["error"]["code"], -32602)
            self.assertEqual(responses[3]["id"], 4)
            self.assertEqual(responses[3]["result"], {})

            # Boolean files_count rejected.
            self.assertTrue(responses[4]["result"]["isError"])

            # Uppercase ThinkingLevel strings normalized cleanly; invalid values rejected.
            self.assertFalse(responses[5]["result"]["isError"])
            self.assertEqual(
                responses[5]["result"]["structuredContent"]["config_descriptor"]["thinking_level"],
                "xhigh",
            )
            self.assertEqual(
                responses[5]["result"]["structuredContent"]["config_descriptor"]["thinking_enum"],
                "ThinkingLevel.EXTRA_HIGH",
            )
            self.assertFalse(responses[6]["result"]["isError"])
            self.assertEqual(
                responses[6]["result"]["structuredContent"]["config_descriptor"]["thinking_level"],
                "low",
            )
            self.assertTrue(responses[7]["result"]["isError"])

            # TOOLS[3] documents optional state_dir matching accepted args.
            tools_by_name = {t["name"]: t for t in responses[8]["result"]["tools"]}
            self.assertIn("state_dir", tools_by_name["run_local_stem_turn"]["inputSchema"]["properties"])


if __name__ == "__main__":
    unittest.main()
