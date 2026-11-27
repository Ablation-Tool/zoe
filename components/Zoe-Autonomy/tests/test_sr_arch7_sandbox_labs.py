"""Tests for Architecture #7: Reality-Anchored Sandbox Labs (`sandbox_labs.py`)."""

from __future__ import annotations

import functools
import http.server
import json
from pathlib import Path
import socketserver
import sys
import threading
from typing import Any
from unittest import mock

import numpy as np
import pytest
import z3

REPO_ROOT = Path(__file__).resolve().parents[3]
ZOE_AUTONOMY_SRC = REPO_ROOT / "components" / "Zoe-Autonomy" / "src"
if str(ZOE_AUTONOMY_SRC) not in sys.path:
    sys.path.insert(0, str(ZOE_AUTONOMY_SRC))

from zoe_autonomy.shared_reasoning import RealitySandboxLab  # noqa: E402
from zoe_autonomy.shared_reasoning.sandbox_labs import (  # noqa: E402
    SANDBOX_LABS_CONTRACT,
    SandboxLabVerdict,
    post_verdict_to_blackboard,
)


def _assert_verdict_shape(verdict: SandboxLabVerdict) -> None:
    doc = verdict.to_dict()
    assert doc["contract"] == SANDBOX_LABS_CONTRACT
    for key in (
        "lab_name",
        "passed",
        "ground_truth",
        "counterexample",
        "evidence_source",
        "limitations",
        "elapsed_ms",
    ):
        assert key in doc
    assert isinstance(verdict.elapsed_ms, float)
    assert verdict.elapsed_ms >= 0.0
    assert len(verdict.limitations) >= 1
    assert verdict.measurement_sha256
    assert doc["constitutional"]["external_actions"] == 0
    assert doc["constitutional"]["sentience_claimed"] is False
    assert doc["constitutional"]["l5_agi_qualified"] is False
    assert doc["constitutional"]["zoe_clone_claimed"] is False
    assert doc["constitutional"]["attribution"] == "Nicholas Michael Kloster, March 6, 2026"


# ---------------------------------------------------------------------------
# 1. SymPy Lab
# ---------------------------------------------------------------------------


def test_sympy_identity_proof_and_false_claim_counterexample() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    v_true = lab.verify_sympy_identity("(x + y)**2", "x**2 + 2*x*y + y**2")
    _assert_verdict_shape(v_true)
    assert v_true.lab_name == "sympy_lab"
    assert v_true.passed is True
    assert v_true.counterexample is None
    assert v_true.ground_truth["simplified_residual"] == "0"
    assert "sympy==" in v_true.evidence_source

    v_trig = lab.verify_sympy_identity("sin(x)**2 + cos(x)**2", "1")
    _assert_verdict_shape(v_trig)
    assert v_trig.passed is True

    v_false = lab.verify_sympy_identity("(x + y)**2", "x**2 + y**2")
    _assert_verdict_shape(v_false)
    assert v_false.passed is False
    assert v_false.counterexample is not None
    assign = v_false.counterexample["assignment"]
    assert assign["x"] * assign["y"] != 0
    assert v_false.counterexample["lhs_value"] != v_false.counterexample["rhs_value"]
    assert v_false.counterexample["residual"] != "0"


def test_sympy_calculus_and_equation_solving() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    v_diff_ok = lab.verify_sympy_equation(
        "3*x**2 + cos(x)",
        verify_derivative_of="x**3 + sin(x)",
        wrt="x",
    )
    assert v_diff_ok.passed is True
    assert v_diff_ok.counterexample is None

    v_diff_bad = lab.verify_sympy_equation(
        "3*x**2 - cos(x)",
        verify_derivative_of="x**3 + sin(x)",
        wrt="x",
    )
    assert v_diff_bad.passed is False
    assert v_diff_bad.counterexample is not None
    assert v_diff_bad.ground_truth["exact_derivative"] == "3*x**2 + cos(x)"

    v_int_ok = lab.verify_sympy_calculus("integrate", "3*x**2 + 2*x", "x**3 + x**2 + 7", variable="x")
    assert v_int_ok.passed is True

    v_int_bad = lab.verify_sympy_calculus("integrate", "3*x**2", "x**2", variable="x")
    assert v_int_bad.passed is False
    assert v_int_bad.counterexample is not None

    v_roots_ok = lab.verify_sympy_equation(
        "x**2 - 5*x + 6 = 0",
        solve_for="x",
        candidate_solutions=[2, 3],
    )
    assert v_roots_ok.passed is True
    assert v_roots_ok.ground_truth["exact_solutions"] == [2, 3]

    v_roots_bad = lab.verify_sympy_equation(
        "x**2 - 5*x + 6 = 0",
        solve_for="x",
        candidate_solutions=[2, 4],
    )
    assert v_roots_bad.passed is False
    assert v_roots_bad.counterexample["invalid_candidate"] == 4
    assert v_roots_bad.counterexample["residual"] == "2"


def test_sympy_rejects_unsafe_ast() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)
    with pytest.raises(ValueError, match="Disallowed"):
        lab.verify_sympy_identity("__import__('os').system('id')", "0")


# ---------------------------------------------------------------------------
# 2. Z3 SMT Lab
# ---------------------------------------------------------------------------


def test_z3_invariant_proof_and_counterexample_extraction() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # Universal proof using string DSL: x >= 2 => x^2 >= 4
    v_proven = lab.check_z3_invariant(
        assumptions=["x >= 2"],
        invariant="x**2 >= 4",
        variables={"x": "Int"},
    )
    _assert_verdict_shape(v_proven)
    assert v_proven.lab_name == "z3_smt_lab"
    assert v_proven.passed is True
    assert v_proven.ground_truth["status"] == "unsat"
    assert v_proven.ground_truth["invariant_proven"] is True
    assert v_proven.counterexample is None

    # Violated invariant: x >= 0 => x^2 > x (fails at x=0 and x=1)
    v_violated = lab.check_z3_invariant(
        assumptions=["x >= 0"],
        invariant="x**2 > x",
        variables={"x": "Int"},
    )
    _assert_verdict_shape(v_violated)
    assert v_violated.passed is False
    assert v_violated.ground_truth["status"] == "sat"
    assert v_violated.counterexample is not None
    x_val = v_violated.counterexample["model"]["x"]
    assert x_val >= 0 and not (x_val**2 > x_val)

    # Programmatic Z3 BoolRef constraint checks (SAT + UNSAT)
    p = z3.Real("p")
    q = z3.Real("q")
    v_sat = lab.verify_z3_constraint(
        [p >= 0, q >= 0, p + q == 1, p > q],
        expect_sat=True,
    )
    assert v_sat.passed is True
    assert v_sat.ground_truth["status"] == "sat"
    model = v_sat.ground_truth["model"]
    assert abs((model["p"] + model["q"]) - 1.0) < 1e-9
    assert model["p"] > model["q"]

    v_unsat = lab.verify_z3_constraint(
        ["x > 10", "x < 5"],
        variables={"x": "Int"},
        expect_sat=False,
    )
    assert v_unsat.passed is True
    assert v_unsat.ground_truth["status"] == "unsat"


# ---------------------------------------------------------------------------
# 3. Monorepo / AST / Pytest / Git Lab
# ---------------------------------------------------------------------------


def test_python_ast_sandbox_valid_hostile_and_counterexample() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    src = "def score(x, y):\n    s = sq(x) + sq(y)\n    return s"
    v_ok = lab.verify_python_ast_sandbox(
        src,
        expected_name="score",
        expected_args=("x", "y"),
        test_cases=[({"x": 3.0, "y": 4.0}, 25.0), ({"x": 1.0, "y": 2.0}, 5.0)],
    )
    _assert_verdict_shape(v_ok)
    assert v_ok.passed is True
    assert v_ok.ground_truth["test_cases_run"] == 2

    v_mismatch = lab.verify_python_ast_sandbox(
        src,
        expected_name="score",
        expected_args=("x", "y"),
        test_cases=[({"x": 3.0, "y": 4.0}, 99.0)],
    )
    assert v_mismatch.passed is False
    assert v_mismatch.counterexample["expected"] == 99.0
    assert v_mismatch.counterexample["actual"] == 25.0

    v_hostile_blocked = lab.verify_python_ast_sandbox(
        "def evil(x):\n    import os\n    return x",
        expected_blocked=True,
    )
    assert v_hostile_blocked.passed is True
    assert v_hostile_blocked.ground_truth["blocked"] is True


def test_repo_command_sandbox_readonly_and_allowlist() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    v_git = lab.verify_repo_command(["git", "rev-parse", "--is-inside-work-tree"])
    _assert_verdict_shape(v_git)
    assert v_git.lab_name == "repo_command_lab"
    assert v_git.passed is True
    assert v_git.ground_truth["stdout"].strip() == "true"

    # Mutating / arbitrary shell commands must be rejected before spawning.
    for forbidden in (
        ["git", "reset", "--hard"],
        ["bash", "-c", "echo pwned"],
        ["ruff", "check", "--fix", "."],
        ["python3", "-c", "print(1)"],
    ):
        v_rej = lab.verify_repo_command(forbidden)
        assert v_rej.passed is False
        assert v_rej.ground_truth["executed"] is False
        assert "rejected_reason" in v_rej.counterexample


# ---------------------------------------------------------------------------
# 4. Dataset Invariant Lab
# ---------------------------------------------------------------------------


def test_dataset_invariants_pass_and_violating_counterexamples(tmp_path: Path) -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    good_rows = [
        {"step": 1, "p0": 0.2, "p1": 0.8},
        {"step": 2, "p0": 0.5, "p1": 0.5},
        {"step": 3, "p0": 0.1, "p1": 0.9},
    ]
    invariants = [
        {"kind": "non_empty", "min_rows": 3, "required_columns": ["step", "p0", "p1"]},
        {"kind": "finite"},
        {"kind": "range", "column": "p0", "min": 0.0, "max": 1.0},
        {"kind": "simplex", "columns": ["p0", "p1"], "target": 1.0, "atol": 1e-6},
        {"kind": "monotonic_increasing", "column": "step", "strict": True},
        {"kind": "mean_range", "column": "p0", "min": 0.1, "max": 0.5},
    ]
    v_ok = lab.verify_dataset_invariants(good_rows, invariants, dataset_name="simplex_trace")
    _assert_verdict_shape(v_ok)
    assert v_ok.passed is True
    assert v_ok.counterexample is None
    assert v_ok.ground_truth["invariants_passed"] == len(invariants)

    bad_rows = [
        {"step": 1, "p0": 0.2, "p1": 0.8},
        {"step": 1, "p0": 0.6, "p1": 0.6},  # breaks strict monotonicity & simplex sum (1.2 != 1.0)
        {"step": 3, "p0": float("nan"), "p1": 0.5},
    ]
    v_bad = lab.verify_dataset_invariants(bad_rows, invariants, dataset_name="corrupted_trace")
    assert v_bad.passed is False
    assert v_bad.counterexample is not None
    assert v_bad.ground_truth["invariants_passed"] < len(invariants)

    # Also verify CSV file loading + ndarray support
    csv_path = tmp_path / "sample.csv"
    csv_path.write_text("t,x\n0,1.0\n1,2.0\n2,3.0\n", encoding="utf-8")
    v_csv = lab.verify_dataset_invariants(
        csv_path,
        [{"kind": "monotonic_increasing", "column": "t", "strict": True}],
    )
    assert v_csv.passed is True

    arr = np.array([[0.25, 0.75], [0.4, 0.6]])
    v_arr = lab.verify_dataset_invariants(arr, [{"kind": "simplex", "target": 1.0}])
    assert v_arr.passed is True


# ---------------------------------------------------------------------------
# 5. Loopback Observatory & Honest Capability Probes
# ---------------------------------------------------------------------------


def test_loopback_http_verification_and_external_rejection() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    class _Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/health":
                payload = json.dumps({"status": "ok", "observatory": "dorothy"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
            else:
                self.send_response(404)
                self.end_headers()

    class _ThreadedHTTP(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = _ThreadedHTTP(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        v_ok = lab.verify_loopback_http(
            f"http://127.0.0.1:{port}/health",
            expected_status=200,
            expected_substrings=("dorothy",),
            expected_headers={"content-type": "application/json"},
        )
        _assert_verdict_shape(v_ok)
        assert v_ok.lab_name == "loopback_http_lab"
        assert v_ok.passed is True
        assert v_ok.ground_truth["status"] == 200

        v_404 = lab.verify_loopback_http(
            f"http://127.0.0.1:{port}/missing",
            expected_status=200,
            min_bytes=0,
        )
        assert v_404.passed is False
        assert v_404.counterexample["status"] == 404
    finally:
        server.shutdown()
        server.server_close()

    # Non-loopback host must be blocked with zero network call.
    v_ext = lab.verify_loopback_http("https://example.com/")
    assert v_ext.passed is False
    assert "loopback" in v_ext.counterexample["reason"].lower()


def test_honest_capability_reporting_when_lean_and_chromium_absent() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    # Simulate absent lean & chromium cleanly (and matches real host where lean/chromium are absent).
    with mock.patch("zoe_autonomy.shared_reasoning.sandbox_labs.shutil.which", return_value=None):
        v_lean_probe = lab.probe_lean_capability()
        _assert_verdict_shape(v_lean_probe)
        assert v_lean_probe.available is False
        assert v_lean_probe.passed is False
        assert v_lean_probe.ground_truth["lean_available"] is False
        assert any("lean" in lim.lower() for lim in v_lean_probe.limitations)

        v_lean_check = lab.verify_lean_proof("theorem t : 1 + 1 = 2 := rfl")
        _assert_verdict_shape(v_lean_check)
        assert v_lean_check.available is False
        assert v_lean_check.passed is False
        assert v_lean_check.counterexample == {"missing_binary": "lean"}

    # Real host probe: verify no fake pass if Chromium is absent
    v_browser = lab.probe_browser_capability(test_url="http://127.0.0.1:8765")
    _assert_verdict_shape(v_browser)
    assert v_browser.ground_truth["browser_executed"] is False
    if not v_browser.available:
        assert v_browser.passed is False
        assert any("chromium" in lim.lower() for lim in v_browser.limitations)

    caps = lab.probe_all_capabilities()
    assert caps["sympy"]["available"] is True
    assert caps["z3"]["available"] is True
    assert caps["loopback_http"]["available"] is True


# ---------------------------------------------------------------------------
# 6. Arch 6 EpistemicBlackboard Integration Readiness
# ---------------------------------------------------------------------------


def test_blackboard_post_measurement_and_promote_to_evidence() -> None:
    class _FakeBlackboard:
        def __init__(self) -> None:
            self.measurements: list[dict[str, Any]] = []
            self.evidences: list[dict[str, Any]] = []

        def post_measurement(
            self,
            *,
            source: str,
            method: str,
            scope: str,
            limitations: list[str],
            payload: dict[str, Any],
        ) -> dict[str, Any]:
            rec = {
                "measurement_id": f"m-{len(self.measurements) + 1}",
                "source": source,
                "method": method,
                "scope": scope,
                "limitations": limitations,
                "payload": payload,
            }
            self.measurements.append(rec)
            return rec

        def promote_to_evidence(
            self,
            measurement_id: str,
            verifier_name: str,
            passed: bool,
            rationale: str,
        ) -> dict[str, Any]:
            rec = {
                "evidence_id": f"e-{len(self.evidences) + 1}",
                "measurement_id": measurement_id,
                "verifier_name": verifier_name,
                "passed": passed,
                "rationale": rationale,
            }
            self.evidences.append(rec)
            return rec

    bb = _FakeBlackboard()
    lab = RealitySandboxLab(repo_root=REPO_ROOT, blackboard=bb)

    v_pass = lab.verify_sympy_identity("(a - b)*(a + b)", "a**2 - b**2", post_to_blackboard=True)
    v_fail = lab.check_z3_invariant(["x >= 0"], "x > 0", variables={"x": "Int"})
    res = post_verdict_to_blackboard(v_fail, bb, promote=True)

    assert v_pass.passed is True
    assert v_fail.passed is False
    assert len(bb.measurements) == 2
    assert len(bb.evidences) == 2
    assert bb.evidences[0]["passed"] is True
    assert bb.evidences[1]["passed"] is False
    assert res["measurement_id"] == "m-2"


def test_real_epistemic_blackboard_integration_firewall_and_negative_results(
    tmp_path: Path,
) -> None:
    from zoe_autonomy.shared_reasoning.blackboard import (
        EpistemicBlackboard,
        FirewallViolationError,
    )

    bb = EpistemicBlackboard(tmp_path / "bb")
    lab = RealitySandboxLab(repo_root=REPO_ROOT, blackboard=bb)

    # 1. Passing SymPy identity -> measurement + approved passing evidence -> belief update succeeds
    v_sym_pass = lab.verify_sympy_identity(
        "(x + y)**2",
        "x**2 + 2*x*y + y**2",
        claim="Binomial square identity holds symbolically",
    )
    res_sym_pass = post_verdict_to_blackboard(v_sym_pass, bb, promote=True)
    ev_sym_pass = res_sym_pass["evidence"]
    assert ev_sym_pass.passed is True
    assert ev_sym_pass.approved is True
    assert ev_sym_pass.negative_result is False
    bel_sym = bb.update_belief(
        [res_sym_pass["evidence_id"]],
        "Binomial square identity verified by SymPy",
        0.4,
    )
    assert bel_sym.evidence_ids == (res_sym_pass["evidence_id"],)

    # 2. Failing SymPy claim (with counterexample) -> negative evidence -> belief update BLOCKED
    v_sym_fail = lab.verify_sympy_identity(
        "(x + y)**2",
        "x**2 + y**2",
        claim="False linearity of square",
    )
    res_sym_fail = post_verdict_to_blackboard(v_sym_fail, bb, promote=True)
    ev_sym_fail = res_sym_fail["evidence"]
    assert ev_sym_fail.passed is False
    assert ev_sym_fail.approved is False
    assert ev_sym_fail.negative_result is True
    assert "counterexample=" in ev_sym_fail.rationale
    with pytest.raises(FirewallViolationError, match="did not pass"):
        bb.update_belief(
            [res_sym_fail["evidence_id"]],
            "Attempt to promote falsified SymPy claim",
            0.3,
        )

    # 3. Passing & Failing Z3 invariants posted directly via post_to_blackboard=True
    v_z3_pass = lab.check_z3_invariant(
        ["x >= 2"],
        "x**2 >= 4",
        variables={"x": "Int"},
        claim="x >= 2 implies x^2 >= 4",
        post_to_blackboard=True,
    )
    assert v_z3_pass.passed is True
    z3_pass_ev = bb.list_evidence()[-1]
    assert z3_pass_ev.passed is True
    bel_z3 = bb.update_belief(
        [z3_pass_ev.evidence_id],
        "Z3 proved x >= 2 => x^2 >= 4",
        0.35,
    )
    assert bel_z3.evidence_ids == (z3_pass_ev.evidence_id,)

    v_z3_fail = lab.check_z3_invariant(
        ["x >= 0"],
        "x**2 > x",
        variables={"x": "Int"},
        claim="False claim: x >= 0 implies x^2 > x",
        post_to_blackboard=True,
    )
    assert v_z3_fail.passed is False
    z3_fail_ev = bb.list_evidence()[-1]
    assert z3_fail_ev.passed is False
    assert z3_fail_ev.negative_result is True
    with pytest.raises(FirewallViolationError, match="did not pass"):
        bb.update_belief(
            [z3_fail_ev.evidence_id],
            "Attempt to promote falsified Z3 invariant",
            0.3,
        )

    # 4. Unavailable binary (Lean absent) also posts negative evidence and cannot update beliefs
    with mock.patch("zoe_autonomy.shared_reasoning.sandbox_labs.shutil.which", return_value=None):
        v_lean_unavail = lab.verify_lean_proof("theorem one : 1 = 1 := rfl", post_to_blackboard=True)
    assert v_lean_unavail.available is False
    assert v_lean_unavail.passed is False
    lean_ev = bb.list_evidence()[-1]
    assert lean_ev.passed is False
    assert lean_ev.negative_result is True
    with pytest.raises(FirewallViolationError, match="did not pass"):
        bb.update_belief([lean_ev.evidence_id], "Lean unavailable cannot prove theorem", 0.2)

    integrity = bb.verify_integrity()
    assert integrity["valid"] is True
    assert integrity["tamper_detected"] is False
    summary = bb.summary()
    assert summary["measurements_count"] == 5
    assert summary["evidence_passed_count"] == 2
    assert summary["negative_results_count"] == 3
    assert summary["belief_updates_count"] == 2
    assert summary["constitutional"]["external_actions"] == 0


def test_regression_loopback_http_redirect_ssrf_blocked_and_same_origin_allowed() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    target_hits: list[str] = []

    class _DisallowedTargetHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            target_hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"secret")

    class _RedirectorHandler(http.server.BaseHTTPRequestHandler):
        redirect_map: dict[str, str] = {}

        def log_message(self, format: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            if self.path == "/health":
                payload = json.dumps({"status": "ok", "observatory": "dorothy"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                return
            if self.path in self.redirect_map:
                self.send_response(302)
                self.send_header("Location", self.redirect_map[self.path])
                self.end_headers()
                return
            self.send_response(404)
            self.end_headers()

    class _ThreadedHTTP(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    forbidden_server = _ThreadedHTTP(("127.0.0.2", 0), _DisallowedTargetHandler)
    forbidden_port = forbidden_server.server_address[1]
    other_port_server = _ThreadedHTTP(("127.0.0.1", 0), _DisallowedTargetHandler)
    other_port = other_port_server.server_address[1]

    class _ConfiguredRedirector(_RedirectorHandler):
        redirect_map = {
            "/redir-127-0-0-2": f"http://127.0.0.2:{forbidden_port}/secret",
            "/redir-external": "https://example.com/exfil",
            "/redir-file": "file:///etc/passwd",
            "/redir-cross-port": f"http://127.0.0.1:{other_port}/internal",
            "/redir-same-origin": "/health",
        }

    redir_server = _ThreadedHTTP(("127.0.0.1", 0), _ConfiguredRedirector)
    redir_port = redir_server.server_address[1]

    threads = [
        threading.Thread(target=s.serve_forever, daemon=True)
        for s in (forbidden_server, other_port_server, redir_server)
    ]
    for t in threads:
        t.start()

    try:
        # 1. Redirect to 127.0.0.2 must be blocked BEFORE any socket connection to 127.0.0.2.
        v_127_2 = lab.verify_loopback_http(f"http://127.0.0.1:{redir_port}/redir-127-0-0-2")
        assert v_127_2.passed is False
        assert v_127_2.ground_truth.get("redirect_blocked") is True
        assert "127.0.0.2" in v_127_2.counterexample["rejected_url"]

        # 2. Redirect to external host must be blocked.
        v_ext = lab.verify_loopback_http(f"http://127.0.0.1:{redir_port}/redir-external")
        assert v_ext.passed is False
        assert v_ext.ground_truth.get("redirect_blocked") is True

        # 3. Redirect to file:// must be blocked even if 302 were in expected_status.
        v_file = lab.verify_loopback_http(
            f"http://127.0.0.1:{redir_port}/redir-file",
            expected_status=(200, 302),
        )
        assert v_file.passed is False
        assert v_file.ground_truth.get("redirect_blocked") is True

        # 4. Cross-port redirect on 127.0.0.1 must be blocked BEFORE contacting other_port.
        v_port = lab.verify_loopback_http(f"http://127.0.0.1:{redir_port}/redir-cross-port")
        assert v_port.passed is False
        assert v_port.ground_truth.get("redirect_blocked") is True

        # Zero requests reached either disallowed target socket.
        assert target_hits == []

        # 5. Same-origin loopback redirect succeeds legitimately.
        v_ok = lab.verify_loopback_http(
            f"http://127.0.0.1:{redir_port}/redir-same-origin",
            expected_status=200,
            expected_substrings=("dorothy",),
        )
        assert v_ok.passed is True
        assert v_ok.ground_truth["status"] == 200
    finally:
        for s in (redir_server, forbidden_server, other_port_server):
            s.shutdown()
            s.server_close()


def test_regression_git_sandbox_rejects_flag_and_branch_bypasses() -> None:
    lab = RealitySandboxLab(repo_root=REPO_ROOT)

    disallowed_git_cmds = (
        ["git", "--git-dir=/tmp/evil", "status"],
        ["git", "--work-tree=/tmp/evil", "status"],
        ["git", "--exec-path=/tmp/evil", "status"],
        ["git", "--exec-path", "/tmp/evil", "status"],
        ["git", "--config-env=FOO=BAR", "status"],
        ["git", "-ccore.fsmonitor=evil", "status"],
        ["git", "-C/tmp", "status"],
        ["git", "--namespace=ns", "status"],
        ["git", "branch", "-D", "__nonexistent_probe__"],
        ["git", "branch", "-d", "__nonexistent_probe__"],
        ["git", "branch", "--delete", "__nonexistent_probe__"],
        ["git", "branch", "-m", "a", "b"],
        ["git", "branch", "-M", "a", "b"],
        ["git", "branch", "--move", "a", "b"],
        ["git", "branch", "-c", "a", "b"],
        ["git", "branch", "-C", "a", "b"],
        ["git", "branch", "--copy", "a", "b"],
        ["git", "branch", "--edit-description"],
        ["git", "branch", "--set-upstream-to=origin/main"],
        ["git", "branch", "-u", "origin/main"],
        ["git", "branch", "--unset-upstream"],
        ["git", "branch", "--create-reflog"],
        ["git", "branch", "-f", "new_branch"],
        ["git", "branch", "--force", "new_branch"],
        ["git", "branch", "new_branch_positional"],
        ["git", "diff", "--output=/tmp/evil.patch"],
        ["git", "log", "--output=/tmp/evil.log"],
        ["git", "show", "--ext-diff"],
    )
    for argv in disallowed_git_cmds:
        cmd, reason = lab._validate_repo_argv(argv)
        assert cmd == [] and reason is not None, f"Expected rejection for {argv!r}"
        verdict = lab.verify_repo_command(argv)
        assert verdict.passed is False
        assert verdict.ground_truth["executed"] is False

    # Legitimate read-only git inspection invocations remain allowed.
    allowed_git_cmds = (
        ["git", "status", "--short"],
        ["git", "rev-parse", "--is-inside-work-tree"],
        ["git", "branch", "--show-current"],
        ["git", "branch", "--list"],
        ["git", "branch", "-a", "-v"],
        ["git", "branch", "--list", "main"],
        ["git", "log", "-n", "1", "--oneline"],
        ["git", "ls-files", "-o"],
    )
    for argv in allowed_git_cmds:
        cmd, reason = lab._validate_repo_argv(argv)
        assert reason is None and cmd == argv, f"Expected {argv!r} to be allowed, got {reason!r}"


