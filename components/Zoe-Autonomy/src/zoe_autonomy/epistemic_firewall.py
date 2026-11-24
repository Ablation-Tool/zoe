"""Zoe Epistemic Firewall & Control-Scales-with-Capability Bridge.

Unifies five deterministic, stdlib-first NuClide/Kloster security instruments into
Zoe's runtime and verification stack (`CONSTITUTION.md` Articles II, III, VI;
`AGI-ROADMAP.md` Section 9):

  1. `injection-gate` (`components/injection-gate/`): synchronous deterministic
     `proposal -> gate -> execute` taint/provenance enforcement ahead of actuation.
  2. `capo` (`components/capo/`): config-time capability-graph linter
     (`label-lint`, `spof-budget`, `adversary-twin`) + read-only host co-location
     auditor (`gamut`).
  3. `glance` (`components/glance/`): schema-only sensitivity analyzer for sealed
     corpora (inspects structure without exposing raw PII/values).
  4. `winnow` (`components/winnow/`): codified false-positive Insight Registry
     screen (`PASS` / `REFUTED` / `DOWNGRADE`).
  5. `github-tos-audit` (`components/github-tos-audit/`): pre-push source
     stewardship and policy compliance auditor.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "components").is_dir() and (parent / "docs" / "CONSTITUTION.md").is_file():
            return parent
    return here.parents[4]


def _ensure_sys_path(directory: Path) -> None:
    resolved = str(directory.resolve())
    if resolved not in sys.path:
        sys.path.insert(0, resolved)


def _load_module_from_file(module_name: str, file_path: Path) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _import_injection_gate() -> Any:
    comp_dir = _repo_root() / "components" / "injection-gate"
    _ensure_sys_path(comp_dir)
    return importlib.import_module("injection_gate")


def _import_capo() -> Any:
    comp_dir = _repo_root() / "components" / "capo"
    return _load_module_from_file("zoe_vendor_capo", comp_dir / "capo.py")


def _import_glance() -> Any:
    comp_dir = _repo_root() / "components" / "glance"
    return _load_module_from_file("zoe_vendor_glance", comp_dir / "glance.py")


def _import_winnow() -> Any:
    comp_dir = _repo_root() / "components" / "winnow"
    return _load_module_from_file("zoe_vendor_winnow", comp_dir / "winnow.py")


def _import_tos_audit() -> Any:
    comp_dir = _repo_root() / "components" / "github-tos-audit"
    _ensure_sys_path(comp_dir)
    return _load_module_from_file("zoe_vendor_github_tos_audit", comp_dir / "github_tos_audit.py")


class ZoeEpistemicGate:
    """Synchronous deterministic proposal -> gate -> execute guard for Zoe actuation.

    Never invokes an LLM. Wraps `injection-gate` (`hardened_engine` + `harden`) so
    tainted/untrusted proposals cannot silently trigger host execution, secret reads,
    or unauthorized network egress.
    """

    def __init__(
        self,
        *,
        read_roots: Optional[Sequence[str]] = None,
        write_roots: Optional[Sequence[str]] = None,
        egress_allowlist: Optional[Sequence[str]] = None,
        exec_allowed: bool = False,
        delete_allowed: bool = False,
        sensitive_paths: Optional[Sequence[str]] = None,
        hardened: bool = True,
        on_escalate: Optional[Callable[[Any, Any], bool]] = None,
    ) -> None:
        ig = _import_injection_gate()
        self._ig = ig
        grant = ig.CapabilityGrant(
            read_roots=list(read_roots or []),
            write_roots=list(write_roots or []),
            egress_allowlist=list(egress_allowlist or []),
            exec_allowed=bool(exec_allowed),
            delete_allowed=bool(delete_allowed),
        )
        ctx = ig.PolicyContext(
            grant=grant,
            sensitive_paths=list(sensitive_paths or [str(Path.home() / ".ssh"), str(Path.home() / ".aws"), str(Path.home() / ".gnupg")]),
        )
        self.ctx = ig.harden(ctx) if hardened else ctx
        self.engine = ig.hardened_engine() if hardened else ig.PolicyEngine()
        self.audit_log: List[Dict[str, Any]] = []

        def _audit(req: Any, decision: Any) -> None:
            self.audit_log.append({
                "agent_id": req.agent_id,
                "capability": req.capability.value,
                "target": req.target,
                "verdict": decision.verdict.name,
                "rule": decision.rule,
                "reason": decision.reason,
                "is_tainted": req.is_tainted,
                "target_from_untrusted": req.target_from_untrusted,
            })

        self.enforcer = ig.Enforcer(
            self.engine,
            self.ctx,
            on_escalate=on_escalate or ig.deny_on_escalate,
            audit=_audit,
        )

    def make_taint(self, *, untrusted_origins: Sequence[str] = (), trusted_origins: Sequence[str] = ("owner",)) -> Any:
        ig = self._ig
        tags = [ig.TaintTag(ig.Trust.TRUSTED, o) for o in trusted_origins]
        tags.extend(ig.TaintTag(ig.Trust.UNTRUSTED, o) for o in untrusted_origins)
        return ig.TaintSet.from_tags(tags)

    def operation_to_request(
        self,
        operation: Dict[str, Any],
        *,
        agent_id: str = "zoe",
        taint: Any = None,
        target_from_untrusted: bool = False,
        declared_task: str = "",
    ) -> Any:
        ig = self._ig
        kind = operation.get("kind", "")
        if kind == "host":
            cap = ig.Capability.EXEC
            argv = operation.get("argv") or []
            target = " ".join(str(a) for a in argv) if isinstance(argv, list) else str(argv)
            args = {"argv": argv, "cwd": str(operation.get("cwd", ""))}
        elif kind == "network":
            cap = ig.Capability.NETWORK
            target = str(operation.get("url", ""))
            args = {
                "method": str(operation.get("method", "GET")),
                "headers": operation.get("headers") or {},
                "body": operation.get("body") or "",
            }
        elif kind == "hardware":
            cap = ig.Capability.WRITE
            target = str(operation.get("device", ""))
            args = {"payload_hex": str(operation.get("payload_hex", ""))}
        else:
            cap = ig.Capability.EXEC
            target = str(operation.get("target", kind))
            args = dict(operation)

        taint_set = taint if taint is not None else self.make_taint()
        return ig.ActionRequest(
            agent_id=agent_id,
            capability=cap,
            target=target,
            args=args,
            taint=taint_set,
            declared_task=declared_task,
            target_from_untrusted=bool(target_from_untrusted),
        )

    def evaluate_operation(
        self,
        operation: Dict[str, Any],
        *,
        agent_id: str = "zoe",
        taint: Any = None,
        target_from_untrusted: bool = False,
        declared_task: str = "",
    ) -> Dict[str, Any]:
        req = self.operation_to_request(
            operation,
            agent_id=agent_id,
            taint=taint,
            target_from_untrusted=target_from_untrusted,
            declared_task=declared_task,
        )
        decision = self.enforcer.decide(req)
        return {
            "verdict": decision.verdict.name,
            "allowed": decision.verdict is self._ig.Verdict.ALLOW,
            "rule": decision.rule,
            "reason": decision.reason,
            "capability": req.capability.value,
            "target": req.target,
            "is_tainted": req.is_tainted,
            "untrusted_origins": sorted(req.taint.untrusted_origins),
            "target_from_untrusted": req.target_from_untrusted,
        }

    def guard_operation(
        self,
        operation: Dict[str, Any],
        execute: Callable[[], Any],
        *,
        agent_id: str = "zoe",
        taint: Any = None,
        target_from_untrusted: bool = False,
        declared_task: str = "",
    ) -> Any:
        req = self.operation_to_request(
            operation,
            agent_id=agent_id,
            taint=taint,
            target_from_untrusted=target_from_untrusted,
            declared_task=declared_task,
        )
        try:
            return self.enforcer.guard(req, execute)
        except self._ig.ActionBlocked as blocked:
            raise PermissionError(f"ZoeEpistemicGate {blocked}") from blocked


def lint_zoe_capability_policy(
    policy_or_path: Optional[Dict[str, Any] | str | Path] = None,
) -> Dict[str, Any]:
    """Run `capo` static capability-graph lint (`label-lint`, `spof-budget`, `adversary-twin`)."""
    capo = _import_capo()
    if policy_or_path is None:
        policy_path = _repo_root() / "config" / "zoe-capability-policy.json"
        policy = capo.load_policy(str(policy_path))
        source = str(policy_path)
    elif isinstance(policy_or_path, dict):
        policy = policy_or_path
        source = "<in-memory>"
    else:
        policy = capo.load_policy(str(policy_or_path))
        source = str(policy_or_path)

    findings = (
        capo.lint_labels(policy)
        + capo.check_spof_budget(policy)
        + capo.adversary_twin(policy)
    )
    errors = [f.as_dict() for f in findings if f.severity == "error"]
    warnings = [f.as_dict() for f in findings if f.severity == "warn"]
    infos = [f.as_dict() for f in findings if f.severity == "info"]
    metrics = capo.compute_metrics(policy)
    return {
        "source": source,
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "info_count": len(infos),
        "metrics": metrics,
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
    }


def scan_sealed_corpus_schema(
    corpus_dir: str | Path,
    *,
    source: str = "generic",
    name_paths: Optional[Sequence[str]] = None,
    sealed: bool = True,
) -> Dict[str, Any]:
    """Run `glance` schema-only sensitivity triage without exposing raw record values."""
    glance = _import_glance()
    report = glance.scan(
        str(corpus_dir),
        source=source,
        name_paths=list(name_paths) if name_paths else None,
        include_samples=0,
        sealed=bool(sealed),
    )
    report["constitutional_guard"] = {
        "sealed_mode": bool(sealed),
        "raw_values_exposed": False,
        "article": "CONSTITUTION.md Article VI.2",
    }
    return report


def screen_findings_with_winnow(candidates: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Screen candidate findings against codified NuClide false-positive Insights (`winnow`)."""
    winnow = _import_winnow()
    cand_list = list(candidates)
    results = winnow.screen(cand_list)
    counts = {"PASS": 0, "REFUTED": 0, "DOWNGRADE": 0}
    for row in results:
        v = row.get("verdict", "PASS")
        counts[v] = counts.get(v, 0) + 1
    return {
        "input_count": len(cand_list),
        "counts": counts,
        "results": results,
    }


def audit_repo_stewardship(repo_path: Optional[str | Path] = None) -> Dict[str, Any]:
    """Check `github-tos-audit` module availability and policy clause catalog."""
    tos = _import_tos_audit()
    target = Path(repo_path) if repo_path else _repo_root()
    clauses = getattr(tos, "TOS_CLAUSES", getattr(tos, "CLAUSES", getattr(tos, "POLICY_CLAUSES", {})))
    return {
        "target": str(target),
        "module_loaded": True,
        "clause_count": len(clauses) if isinstance(clauses, (dict, list, tuple)) else 0,
        "has_scan_entrypoint": hasattr(tos, "main"),
    }
