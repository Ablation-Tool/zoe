"""Read-only Ablation Static Analysis & Source Audit Bridge (Milestone M4, Features #11 & #13).

Adapts `components/ablation` in-memory binary, entropy, and source security
analyzers for Zoe and her 9 sisters without:
  - executing target binaries or shell scripts,
  - importing/calling `Advisor` (`claude` CLI) or spending cloud tokens,
  - calling `BinaryContext.load_or_build()`, `FORGE.audit_module()`,
    `FORGE.register()`, `NameRegistry.save()`, `FindingRegistry`, or mutating
    real `~/.ablation/`.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
import copy
from dataclasses import asdict, dataclass, field
import hashlib
import os
from pathlib import Path
import stat
import sys
from typing import Any

from .zoe_eddms import (
    EngineeringDesignDatabase,
    EngineeringDesignRecord,
)
from .zoe_hex_mesh import (
    ATTRIBUTION_TEXT,
    HASH_CHAIN_SEMANTICS,
    ConstitutionalViolationError,
    sha256_canonical,
    validate_constitutional_packet,
    validate_epistemic_lane,
)
from .zoe_sisters import SAFETY_INVARIANTS

ABLATION_BRIDGE_CONTRACT: str = "zoe-ablation-bridge/v1"
ALLOWED_INSPECTION_MODES: frozenset[str] = frozenset({"auto", "binary", "bytes", "source"})
FORBIDDEN_INSPECTION_MODES: frozenset[str] = frozenset(
    {"advisor", "claude", "llm", "execute", "execute_live", "dynamic", "sandbox"}
)

_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".rs", ".go", ".java", ".rb", ".php"}
)
_BINARY_MAGICS: tuple[bytes, ...] = (
    b"\x7fELF",
    b"MZ",
    b"\xfe\xed\xfa\xce",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xcf\xfa\xed\xfe",
    b"\xca\xfe\xba\xbe",
)
_DEFAULT_REPO_ROOT: Path = Path(__file__).resolve().parents[3]


def _ensure_ablation_sys_path(repo_root: Path | None = None) -> Path:
    """Prepend `REPO_ROOT / components / ablation` to `sys.path[0]` before importing ablation."""
    root = Path(repo_root).resolve() if repo_root is not None else _DEFAULT_REPO_ROOT
    ablation_root = str((root / "components" / "ablation").resolve())
    if not sys.path or sys.path[0] != ablation_root:
        while ablation_root in sys.path:
            sys.path.remove(ablation_root)
        sys.path.insert(0, ablation_root)
    return Path(ablation_root)


@contextmanager
def _lief_quiet_scope() -> Iterator[None]:
    """Suppress verbose LIEF C++ diagnostics on minimal/synthetic ELF headers."""
    try:
        import lief
    except Exception:
        yield
        return
    logging_mod = getattr(lief, "logging", None)
    level_scope = getattr(logging_mod, "level_scope", None)
    level_enum = getattr(logging_mod, "LEVEL", None)
    critical = getattr(level_enum, "CRITICAL", None) if level_enum is not None else None
    if callable(level_scope) and critical is not None:
        with level_scope(critical):
            yield
        return
    yield


def constitutional_metadata(
    epistemic_lane: str = "measurement",
    *,
    read_only: bool = True,
) -> dict[str, Any]:
    """Return Project Contract #1 constitutional metadata for Ablation bridge outputs."""
    lane = validate_epistemic_lane(epistemic_lane)
    if read_only is not True:
        raise ConstitutionalViolationError("Ablation bridge metadata requires read_only=True")
    return {
        **SAFETY_INVARIANTS,
        "contract": ABLATION_BRIDGE_CONTRACT,
        "epistemic_lane": lane,
        "measurement_lane_only": lane == "measurement",
        "advisory_only": True,
        "read_only": True,
        "external_actions": 0,
        "tokens_used": 0,
        "cloud_cost_usd": 0.0,
        "loopback_only": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "cure_claim": False,
        "wet_lab_validation_required": True,
        "autonomous_execution_allowed": False,
        "attribution": ATTRIBUTION_TEXT,
        "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
        "tamper_evidence_only": True,
        "authentication_proof": False,
    }


def _validate_report_payload_fields(report: "AblationAdvisoryReport") -> None:
    """Validate nested summary, audit, and finding payloads against NaN/Inf/constitutional rules."""
    for field_payload in (report.binary_summary, report.entropy_summary, report.auditor_findings):
        validate_constitutional_packet(field_payload, epistemic_lane=report.epistemic_lane)
    if report.source_audit is not None:
        validate_constitutional_packet(report.source_audit, epistemic_lane=report.epistemic_lane)
    if not isinstance(report.findings, (tuple, list)):
        raise ConstitutionalViolationError("AblationAdvisoryReport findings must be a tuple or list of mappings")
    for item in report.findings:
        validate_constitutional_packet(item, epistemic_lane=report.epistemic_lane)


def _check_report_invariants(report: "AblationAdvisoryReport") -> None:
    """Enforce strict read-only, zero-token, non-autonomous report invariants."""
    validate_epistemic_lane(report.epistemic_lane)
    if not isinstance(report.target_name, str) or not report.target_name.strip():
        raise ConstitutionalViolationError("AblationAdvisoryReport target_name must be a non-empty str")
    if not isinstance(report.mode, str) or report.mode not in ALLOWED_INSPECTION_MODES:
        raise ConstitutionalViolationError(
            f"AblationAdvisoryReport mode must be in {sorted(ALLOWED_INSPECTION_MODES)}, got {report.mode!r}"
        )
    if isinstance(report.byte_size, bool) or not isinstance(report.byte_size, int) or report.byte_size < 0:
        raise ConstitutionalViolationError(
            f"AblationAdvisoryReport byte_size must be a non-negative non-bool int, got {report.byte_size!r}"
        )
    if not isinstance(report.summary, str):
        raise ConstitutionalViolationError("AblationAdvisoryReport summary must be a str")
    if report.advisory_only is not True or report.read_only is not True:
        raise ConstitutionalViolationError("AblationAdvisoryReport must be advisory_only=True and read_only=True")
    if report.external_actions != 0 or isinstance(report.external_actions, bool):
        raise ConstitutionalViolationError("AblationAdvisoryReport external_actions must be 0")
    if report.tokens_used != 0 or isinstance(report.tokens_used, bool):
        raise ConstitutionalViolationError("AblationAdvisoryReport tokens_used must be 0")
    if float(report.cloud_cost_usd) != 0.0 or isinstance(report.cloud_cost_usd, bool):
        raise ConstitutionalViolationError("AblationAdvisoryReport cloud_cost_usd must be 0.0")
    if report.loopback_only is not True:
        raise ConstitutionalViolationError("AblationAdvisoryReport loopback_only must be True")
    false_flags = (
        report.sentience_claimed,
        report.l5_agi_qualified,
        report.zoe_clone_claimed,
        report.clinical_action_authorized,
        report.flight_control_authorized,
        report.cure_claim,
    )
    if any(flag is not False for flag in false_flags):
        raise ConstitutionalViolationError("AblationAdvisoryReport false safety flags violated")
    validate_constitutional_packet(
        report.safety_invariants,
        epistemic_lane=report.epistemic_lane,
        require_metadata=True,
    )
    _validate_report_payload_fields(report)


@dataclass(frozen=True)
class AblationAdvisoryReport:
    """Immutable, strictly read-only advisory report produced by `AblationBridge`."""

    target_name: str
    target_path: str | None
    target_sha256: str
    mode: str
    byte_size: int
    ok: bool = True
    status: str = "advisory_complete"
    error: str | None = None
    arch: str = "unknown"
    binary_summary: dict[str, Any] = field(default_factory=dict)
    entropy_summary: dict[str, Any] = field(default_factory=dict)
    auditor_findings: dict[str, Any] = field(default_factory=dict)
    source_audit: dict[str, Any] | None = None
    findings: tuple[dict[str, Any], ...] = ()
    summary: str = ""
    epistemic_lane: str = "measurement"
    advisory_only: bool = True
    read_only: bool = True
    external_actions: int = 0
    tokens_used: int = 0
    cloud_cost_usd: float = 0.0
    loopback_only: bool = True
    sentience_claimed: bool = False
    l5_agi_qualified: bool = False
    zoe_clone_claimed: bool = False
    clinical_action_authorized: bool = False
    flight_control_authorized: bool = False
    cure_claim: bool = False
    attribution: str = ATTRIBUTION_TEXT
    safety_invariants: dict[str, Any] = field(
        default_factory=lambda: constitutional_metadata("measurement", read_only=True)
    )

    def __post_init__(self) -> None:
        _check_report_invariants(self)

    def constitutional_metadata(self, epistemic_lane: str | None = None) -> dict[str, Any]:
        """Return fresh constitutional metadata dictionary."""
        return constitutional_metadata(epistemic_lane or self.epistemic_lane, read_only=True)

    def to_dict(self) -> dict[str, Any]:
        """Serialize report into a JSON-safe, deep-copied dictionary."""
        return {
            "contract": ABLATION_BRIDGE_CONTRACT,
            "target_name": self.target_name,
            "target_path": self.target_path,
            "target_sha256": self.target_sha256,
            "mode": self.mode,
            "byte_size": self.byte_size,
            "ok": self.ok,
            "status": self.status,
            "error": self.error,
            "arch": self.arch,
            "binary_summary": copy.deepcopy(self.binary_summary),
            "entropy_summary": copy.deepcopy(self.entropy_summary),
            "auditor_findings": copy.deepcopy(self.auditor_findings),
            "source_audit": copy.deepcopy(self.source_audit),
            "findings": copy.deepcopy(list(self.findings)),
            "summary": self.summary,
            "epistemic_lane": self.epistemic_lane,
            "advisory_only": self.advisory_only,
            "read_only": self.read_only,
            "external_actions": self.external_actions,
            "tokens_used": self.tokens_used,
            "cloud_cost_usd": self.cloud_cost_usd,
            "loopback_only": self.loopback_only,
            "sentience_claimed": self.sentience_claimed,
            "l5_agi_qualified": self.l5_agi_qualified,
            "zoe_clone_claimed": self.zoe_clone_claimed,
            "clinical_action_authorized": self.clinical_action_authorized,
            "flight_control_authorized": self.flight_control_authorized,
            "cure_claim": self.cure_claim,
            "attribution": self.attribution,
            "safety_invariants": copy.deepcopy(self.safety_invariants),
        }


def _safe_asdict_list(items: list[Any]) -> list[dict[str, Any]]:
    """Convert dataclass or dict finding items into normalized plain dicts."""
    out: list[dict[str, Any]] = []
    for item in items:
        if hasattr(item, "as_dict") and callable(item.as_dict):
            out.append(dict(item.as_dict()))
        elif hasattr(item, "__dataclass_fields__"):
            out.append(asdict(item))
        elif isinstance(item, Mapping):
            out.append(dict(item))
        else:
            out.append({"value": str(item)})
    return out


def _compute_entropy_in_memory(raw: bytes, repo_root: Path) -> dict[str, Any]:
    """Run EntropyMapper's pure helpers in memory with adaptive small-buffer window sizing."""
    _ensure_ablation_sys_path(repo_root)
    from ablation.analyzers import entropy_mapper as em

    n = len(raw)
    if n == 0:
        return {
            "file_size": 0,
            "window_size": 0,
            "window_count": 0,
            "region_count": 0,
            "regions": [],
            "encrypted_ranges": [],
            "kloster_stopping": {"action": "ABSTAIN_INSUFFICIENT_EVIDENCE", "samples": 0},
            "backend": "guiai" if getattr(em, "_HAS_GUIAI_KLOSTER", False) else "standalone_fallback",
        }

    # Adapt window size so small binaries (e.g. 186-byte minimal ELF64) yield >= 1 window.
    window_size = n if n < 16 else min(256, n)
    step_size = window_size
    ctrl = em.KlosterSequentialStoppingController(n_bins=256, delta=0.005, max_samples=max(512, window_size))
    z_thr = float(ctrl.stopping_z_threshold(1))
    windows: list[Any] = []
    final_verdict: dict[str, Any] | None = None

    for offset, h in em._entropy_numpy(raw, window_size, step_size):
        chunk = raw[offset : offset + window_size]
        stats = em.kloster_unbiased_chi2_stats(em._byte_histogram(chunk))
        cls_name = em._classify_window(float(h), window_size, stats, z_thr, True)
        verdict = ctrl.observe_batch(list(chunk))
        final_verdict = dict(verdict)
        if verdict.get("action") != "GATHER_MORE":
            ctrl = em.KlosterSequentialStoppingController(n_bins=256, delta=0.005, max_samples=max(512, window_size))
        windows.append(
            em.EntropyWindow(
                offset=int(offset),
                size=window_size,
                entropy=float(h),
                cls=str(cls_name),
                z_kloster=float(stats["z_kloster"]),
                m2_unbiased=float(stats["m2_unbiased"]),
                excess_chi2=float(stats["excess_chi2"]),
                kloster_action=str(verdict.get("action", "GATHER_MORE")),
            )
        )

    regions = em._merge_regions(windows)
    return {
        "file_size": n,
        "window_size": window_size,
        "window_count": len(windows),
        "region_count": len(regions),
        "regions": [
            {
                "offset_start": r.offset_start,
                "offset_end": r.offset_end,
                "cls": r.cls,
                "avg_entropy": round(float(r.avg_entropy), 6),
                "min_entropy": round(float(r.min_entropy), 6),
                "max_entropy": round(float(r.max_entropy), 6),
            }
            for r in regions
        ],
        "encrypted_ranges": [[r.offset_start, r.offset_end] for r in regions if r.cls == "ENCRYPTED"],
        "kloster_stopping": final_verdict,
        "backend": "guiai" if getattr(em, "_HAS_GUIAI_KLOSTER", False) else "standalone_fallback",
    }


def _collect_source_findings(ctx: Any, repo_root: Path) -> tuple[list[dict[str, Any]], str, str]:
    """Execute SourceEntryClassifier + SourceSinkScanner + SourceAuditCompressor without ~/.ablation."""
    _ensure_ablation_sys_path(repo_root)
    from ablation.analyzers.source_audit_compressor import SourceAuditCompressor
    from ablation.analyzers.source_entry_classifier import SourceEntryClassifier
    from ablation.analyzers.source_sink_scanner import SourceSinkScanner

    findings: list[dict[str, Any]] = []
    routes = SourceEntryClassifier.from_context(ctx).classify()
    for r in routes:
        if r.auth_level == "NONE" and not r.is_low_value:
            findings.append(
                {
                    "severity": "MEDIUM",
                    "category": "attack_surface",
                    "title": f"Unauthenticated route: {r.rel_path}",
                    "location": str(r.rel_path),
                    "description": f"No auth signal ({r.matched_signal})",
                    "source": "source_audit",
                    "cwe": "",
                }
            )
    sink_hits = SourceSinkScanner.from_context(ctx).scan()
    for sh in sink_hits:
        findings.append(
            {
                "severity": str(sh.severity),
                "category": str(sh.category),
                "title": str(sh.description),
                "location": f"{sh.rel_path}:{sh.line}",
                "description": str(sh.line_text).strip(),
                "source": "source_audit",
                "cwe": str(sh.cwe),
            }
        )
    buckets = SourceAuditCompressor.from_context(ctx).compress()
    for bucket in SourceAuditCompressor.priority_reads(buckets):
        for fp in bucket.files:
            findings.append(
                {
                    "severity": "INFO",
                    "category": "priority_read",
                    "title": f"Priority read: {fp.rel_path}",
                    "location": str(fp.rel_path),
                    "description": f"profile={fp.profile_str} signals={fp.signals}",
                    "source": "source_audit",
                    "cwe": "",
                }
            )
    ratio = float(SourceAuditCompressor.compression_ratio(buckets))
    total = sum(len(b.files) for b in buckets.values())
    n_unauth = sum(1 for r in routes if r.auth_level == "NONE" and not r.is_low_value)
    summary = f"{ctx.summary()} | sinks={len(sink_hits)} | unauth_routes={n_unauth} | compression={ratio:.1%} ({total} files)"
    raw_text = str(SourceAuditCompressor.report(buckets))
    return findings, summary, raw_text


def _build_single_source_context(file_path: Path, raw_text: str | None, repo_root: Path) -> Any:
    """Build a SourceContext for one file or in-memory text (avoids FORGE.audit_source dir check)."""
    _ensure_ablation_sys_path(repo_root)
    from ablation.analyzers.source_ingestion import (
        SourceContext,
        _LANG_EXTS,
        _ROUTE_CONTENT_SIGNALS,
        _is_route_file,
    )

    lang = _LANG_EXTS.get(file_path.suffix.lower(), "python" if raw_text is not None else "unknown")
    if raw_text is None:
        route_files = [file_path] if _is_route_file(file_path) else []
        return SourceContext(
            repo_root=file_path.parent,
            all_files=[file_path],
            route_files=route_files,
            lang_map={lang: [file_path]},
            package_roots=[],
        )

    mem_text = raw_text

    class _MemorySourceContext(SourceContext):  # type: ignore[misc]
        def read(self, path: Path) -> str:
            return mem_text if path == file_path else ""

    is_route = any(pat.search(mem_text) for pat in _ROUTE_CONTENT_SIGNALS)
    return _MemorySourceContext(
        repo_root=file_path.parent,
        all_files=[file_path],
        route_files=[file_path] if is_route else [],
        lang_map={lang: [file_path]},
        package_roots=[],
    )


def _flatten_binary_findings(auditor_findings: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Flatten Wave-3 AI-agent binary auditor outputs into a uniform finding tuple."""
    flat: list[dict[str, Any]] = []
    for key in ("authority_findings", "observability_findings", "tool_surface_findings", "ai_control_indicators", "sink_classifications"):
        for entry in auditor_findings.get(key, []):
            item = dict(entry)
            item.setdefault("source", key)
            flat.append(item)
    return tuple(flat)


def _validate_mode_and_inputs(
    target_path: str | Path | None,
    raw_bytes: bytes | None,
    mode: str,
) -> str:
    """Validate inspection mode and exclusive target_path/raw_bytes inputs."""
    if not isinstance(mode, str):
        raise ValueError(f"mode must be a string, got {type(mode).__name__}")
    norm_mode = mode.strip().lower()
    if norm_mode not in ALLOWED_INSPECTION_MODES:
        raise ValueError(f"Unsupported or forbidden ablation mode {mode!r}; allowed={sorted(ALLOWED_INSPECTION_MODES)}")
    if target_path is None and raw_bytes is None:
        raise ValueError("Either target_path or raw_bytes must be provided")
    if target_path is not None and raw_bytes is not None:
        raise ValueError("Provide either target_path or raw_bytes, not both")
    return norm_mode


def _resolve_file_mode(path: Path, raw: bytes, requested_mode: str) -> str:
    """Resolve `auto` mode for an on-disk regular file without executing it."""
    if requested_mode != "auto":
        return requested_mode
    if any(raw.startswith(magic) for magic in _BINARY_MAGICS):
        return "binary"
    if path.suffix.lower() in _SOURCE_EXTENSIONS:
        return "source"
    return "bytes"


def _validate_safe_target_path(target_path: str | Path) -> Path:
    """Reject empty/non-path inputs, symlinks, and symlink-traversed parents before reading."""
    if not isinstance(target_path, (str, Path)):
        raise ValueError(f"target_path must be a str or Path, got {type(target_path).__name__}")
    if isinstance(target_path, str) and not target_path.strip():
        raise ValueError("target_path must be a non-empty path")
    raw_p = Path(target_path).expanduser()
    if not str(raw_p).strip():
        raise ValueError("target_path must be a non-empty path")
    norm_p = Path(os.path.normpath(os.path.abspath(raw_p)))
    for candidate in (raw_p, *raw_p.parents, norm_p, *norm_p.parents):
        if candidate.is_symlink():
            raise ValueError(f"Target path must not be or traverse a symbolic link: {candidate}")
    return raw_p


def _is_safe_dir_child(child: Path, resolved_root: Path) -> bool:
    """Return True iff child is an in-tree regular non-symlink file."""
    if child.is_symlink():
        return False
    try:
        st = child.lstat()
    except OSError:
        return False
    if not stat.S_ISREG(st.st_mode):
        return False
    try:
        resolved = child.resolve()
    except OSError:
        return False
    return resolved.is_relative_to(resolved_root)


def _compute_dir_sha256(directory: Path) -> tuple[str, int]:
    """Compute deterministic SHA-256 and total byte size across sorted regular non-symlink files."""
    hasher = hashlib.sha256()
    total_bytes = 0
    resolved_root = directory.resolve()
    for child in sorted(directory.rglob("*")):
        if _is_safe_dir_child(child, resolved_root):
            data = child.read_bytes()
            total_bytes += len(data)
            rel = child.relative_to(directory).as_posix()
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(hashlib.sha256(data).hexdigest().encode("ascii"))
            hasher.update(b"\n")
    return hasher.hexdigest(), total_bytes


def _build_safe_dir_source_context(directory: Path, repo_root: Path) -> Any:
    """Build a SourceContext for directory excluding symlinks, special files, and external escapes."""
    _ensure_ablation_sys_path(repo_root)
    from ablation.analyzers.source_ingestion import (
        SourceContext,
        _LANG_EXTS,
        _SKIP_DIRS,
        _detect_package_roots,
        _is_route_file,
    )

    resolved_root = directory.resolve()
    all_files: list[Path] = []
    lang_map: dict[str, list[Path]] = {}
    for child in sorted(directory.rglob("*")):
        if not _is_safe_dir_child(child, resolved_root):
            continue
        if any(skip in child.parts for skip in _SKIP_DIRS):
            continue
        if child.suffix.lower() in _LANG_EXTS:
            all_files.append(child)
            lang = _LANG_EXTS.get(child.suffix.lower(), "unknown")
            lang_map.setdefault(lang, []).append(child)
    route_files = [f for f in all_files if _is_route_file(f)]
    package_roots = [
        r for r in _detect_package_roots(resolved_root)
        if not r.is_symlink() and r.resolve().is_relative_to(resolved_root)
    ]
    return SourceContext(resolved_root, all_files, route_files, lang_map, package_roots)


class AblationBridge:
    """Zero-token, read-only, non-executing bridge to `components/ablation` analyzers."""

    def __init__(self, *, repo_root: Path | None = None, cache_dir: Path | None = None) -> None:
        self.repo_root: Path = Path(repo_root).resolve() if repo_root is not None else _DEFAULT_REPO_ROOT
        # Optional cache_dir accepted for API compatibility; never touches ~/.ablation/.
        self.cache_dir: Path | None = cache_dir
        _ensure_ablation_sys_path(self.repo_root)

    def _inspect_directory_source(self, directory: Path) -> AblationAdvisoryReport:
        """Inspect a source directory read-only excluding symlinks and external paths (no LLM)."""
        ctx = _build_safe_dir_source_context(directory, self.repo_root)
        findings_list, summary_str, _raw_text = _collect_source_findings(ctx, self.repo_root)
        sha, total_bytes = _compute_dir_sha256(directory)
        high_or_crit = sum(1 for f in findings_list if f.get("severity") in ("CRITICAL", "HIGH"))
        source_audit = validate_constitutional_packet(
            {
                "mode": "source",
                "path": str(directory),
                "gate_passed": high_or_crit == 0,
                "summary": summary_str,
                "finding_count": len(findings_list),
                "high_or_critical": high_or_crit,
                "findings": findings_list,
            },
            epistemic_lane="measurement",
        )
        return AblationAdvisoryReport(
            target_name=directory.name,
            target_path=str(directory),
            target_sha256=sha,
            mode="source",
            byte_size=total_bytes,
            arch="source",
            source_audit=source_audit,
            findings=tuple(findings_list),
            summary=summary_str,
        )

    def _inspect_source_buffer(
        self,
        *,
        file_path: Path,
        raw: bytes,
        target_path_str: str | None,
        target_name: str,
        in_memory: bool,
    ) -> AblationAdvisoryReport:
        """Inspect a single source file or raw source buffer without FORGE dir restriction."""
        sha = hashlib.sha256(raw).hexdigest()
        text = raw.decode("utf-8", errors="replace") if in_memory else None
        ctx = _build_single_source_context(file_path, text, self.repo_root)
        findings_list, summary, _raw_text = _collect_source_findings(ctx, self.repo_root)
        high_or_crit = sum(1 for f in findings_list if f.get("severity") in ("CRITICAL", "HIGH"))
        source_audit = validate_constitutional_packet(
            {
                "mode": "source",
                "path": target_path_str or target_name,
                "gate_passed": high_or_crit == 0,
                "summary": summary,
                "finding_count": len(findings_list),
                "high_or_critical": high_or_crit,
                "findings": findings_list,
            },
            epistemic_lane="measurement",
        )
        return AblationAdvisoryReport(
            target_name=target_name,
            target_path=target_path_str,
            target_sha256=sha,
            mode="source",
            byte_size=len(raw),
            arch="source",
            source_audit=source_audit,
            findings=tuple(findings_list),
            summary=summary,
        )

    def _inspect_binary_or_bytes(
        self,
        raw: bytes,
        *,
        target_name: str,
        target_path: str | None,
        resolved_mode: str,
        disk_path: Path | None,
    ) -> AblationAdvisoryReport:
        """Run static binary/entropy/AI-agent byte auditors purely in memory."""
        _ensure_ablation_sys_path(self.repo_root)
        from ablation.analyzers import (
            AgentAuthorityAudit,
            AgentObservabilityAudit,
            AgentToolSurfaceEnumerator,
            AIControlIndicators,
            BinaryContext,
        )
        from ablation.analyzers.sink_arg_classifier import sac_for_context

        sha = hashlib.sha256(raw).hexdigest()
        ctx: Any = BinaryContext()
        has_binary_magic = any(raw.startswith(m) for m in _BINARY_MAGICS)
        if len(raw) >= 4:
            with _lief_quiet_scope():
                try:
                    path_arg = str(disk_path) if (disk_path is not None and has_binary_magic) else ""
                    ctx = BinaryContext._build(raw, path_arg, sha)
                except Exception:
                    ctx = BinaryContext()

        arch = str(getattr(ctx, "arch", "unknown")) if has_binary_magic else "unknown"
        plt_names = list(getattr(ctx, "plt", {}).values())
        func_names = list(getattr(ctx, "exports", {}).keys())

        auth_f = _safe_asdict_list(AgentAuthorityAudit.scan_bytes(raw, plt_names))
        obs_f = _safe_asdict_list(AgentObservabilityAudit.scan_bytes(raw, plt_names, func_names))
        tool_f = _safe_asdict_list(AgentToolSurfaceEnumerator.scan_bytes(raw))
        ai_f = _safe_asdict_list(AIControlIndicators.scan_bytes(raw))

        sac_f: list[dict[str, Any]] = []
        if disk_path is not None and bool(getattr(ctx, "plt", {})):
            with _lief_quiet_scope():
                try:
                    sac_f = _safe_asdict_list(sac_for_context(ctx).classify_all())
                except Exception:
                    sac_f = []

        all_items = [*auth_f, *obs_f, *tool_f, *ai_f, *sac_f]
        high_count = sum(1 for item in all_items if item.get("severity") in ("HIGH", "CRITICAL"))

        binary_summary = validate_constitutional_packet(
            {
                "arch": arch,
                "byte_size": len(raw),
                "plt_count": len(plt_names),
                "export_count": len(func_names),
                "string_count": len(getattr(ctx, "strings", {})),
                "func_count": len(getattr(ctx, "func_starts", [])),
                "call_edge_count": len(getattr(ctx, "call_edges", [])),
                "plt_sparsity_warning": has_binary_magic and len(plt_names) == 0,
            },
            epistemic_lane="measurement",
        )
        entropy_summary = validate_constitutional_packet(
            _compute_entropy_in_memory(raw, self.repo_root),
            epistemic_lane="measurement",
        )
        auditor_findings = validate_constitutional_packet(
            {
                "authority_findings": auth_f,
                "observability_findings": obs_f,
                "tool_surface_findings": tool_f,
                "ai_control_indicators": ai_f,
                "sink_classifications": sac_f,
                "total_findings": len(all_items),
                "high_severity_count": high_count,
            },
            epistemic_lane="measurement",
        )
        flat_findings = _flatten_binary_findings(auditor_findings)
        summary = (
            f"target={target_name} mode={resolved_mode} arch={arch} bytes={len(raw)} "
            f"findings={len(flat_findings)} high={high_count} entropy_windows={entropy_summary['window_count']}"
        )
        return AblationAdvisoryReport(
            target_name=target_name,
            target_path=target_path,
            target_sha256=sha,
            mode=resolved_mode,
            byte_size=len(raw),
            arch=arch,
            binary_summary=binary_summary,
            entropy_summary=entropy_summary,
            auditor_findings=auditor_findings,
            findings=flat_findings,
            summary=summary,
        )

    def inspect_target_readonly(
        self,
        target_path: str | Path | None = None,
        *,
        raw_bytes: bytes | None = None,
        target_name: str = "memory",
        mode: str = "auto",
    ) -> AblationAdvisoryReport:
        """Inspect a file, directory, or raw byte buffer in strictly read-only advisory mode."""
        norm_mode = _validate_mode_and_inputs(target_path, raw_bytes, mode)

        if target_path is not None:
            p = _validate_safe_target_path(target_path)
            if not os.path.lexists(p):
                raise FileNotFoundError(f"Target path not found: {p}")
            st = os.lstat(p)
            if stat.S_ISDIR(st.st_mode):
                if norm_mode not in ("auto", "source"):
                    raise ValueError(f"Directory inspection requires mode 'auto' or 'source', got {mode!r}")
                return self._inspect_directory_source(p)
            if not stat.S_ISREG(st.st_mode):
                raise ValueError(f"Target path is neither a regular file nor directory: {p}")
            raw = p.read_bytes()
            resolved_mode = _resolve_file_mode(p, raw, norm_mode)
            if resolved_mode == "source":
                return self._inspect_source_buffer(
                    file_path=p,
                    raw=raw,
                    target_path_str=str(p),
                    target_name=p.name,
                    in_memory=False,
                )
            return self._inspect_binary_or_bytes(
                raw,
                target_name=p.name,
                target_path=str(p),
                resolved_mode=resolved_mode,
                disk_path=p,
            )

        if not isinstance(raw_bytes, (bytes, bytearray)):
            raise ValueError(f"raw_bytes must be bytes or bytearray, got {type(raw_bytes).__name__}")
        raw = bytes(raw_bytes)
        clean_name = target_name.strip() if isinstance(target_name, str) and target_name.strip() else "memory"
        if norm_mode == "source":
            virtual_path = Path(clean_name if Path(clean_name).suffix else f"{clean_name}.py")
            return self._inspect_source_buffer(
                file_path=virtual_path,
                raw=raw,
                target_path_str=None,
                target_name=clean_name,
                in_memory=True,
            )
        has_magic = any(raw.startswith(m) for m in _BINARY_MAGICS)
        resolved = "binary" if (norm_mode == "binary" or (norm_mode == "auto" and has_magic)) else "bytes"
        return self._inspect_binary_or_bytes(
            raw,
            target_name=clean_name,
            target_path=None,
            resolved_mode=resolved,
            disk_path=None,
        )


def _validate_nonneg_int(value: Any, label: str) -> int:
    """Validate that a report count field is a non-negative non-bool integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ConstitutionalViolationError(
            f"Attached ablation report {label} must be a non-negative non-bool int, got {value!r}"
        )
    return value


def _validate_attached_mapping(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    """Validate that an optional attached report summary field is a Mapping when present."""
    if key not in payload:
        return {}
    raw = payload[key]
    if not isinstance(raw, Mapping):
        raise ConstitutionalViolationError(
            f"Attached ablation report {key} must be a Mapping, got {type(raw).__name__}"
        )
    return dict(raw)


def _validate_attached_mode_and_text(payload: Mapping[str, Any]) -> tuple[str, str, str]:
    """Validate optional attached report target_name, mode, and summary fields."""
    if "target_name" in payload:
        raw_name = payload["target_name"]
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise ConstitutionalViolationError(
                f"Attached ablation report target_name must be a non-empty str, got {raw_name!r}"
            )
        target_name = raw_name.strip()
    else:
        target_name = "memory"

    if "mode" in payload:
        raw_mode = payload["mode"]
        if not isinstance(raw_mode, str) or not raw_mode.strip():
            raise ConstitutionalViolationError(
                f"Attached ablation report mode must be a non-empty str, got {raw_mode!r}"
            )
        mode = raw_mode.strip().lower()
        if mode not in ALLOWED_INSPECTION_MODES:
            raise ConstitutionalViolationError(
                f"Attached ablation report mode {raw_mode!r} must be in {sorted(ALLOWED_INSPECTION_MODES)}"
            )
    else:
        mode = "bytes"

    if "summary" in payload:
        raw_summary = payload["summary"]
        if not isinstance(raw_summary, str):
            raise ConstitutionalViolationError(
                f"Attached ablation report summary must be a str, got {type(raw_summary).__name__}"
            )
        summary = raw_summary
    else:
        summary = ""
    return target_name, mode, summary


def attach_ablation_to_eddms(
    db: EngineeringDesignDatabase,
    design_id: str,
    report: AblationAdvisoryReport | Mapping[str, Any],
    sister_name: str = "Mono",
    expected_revision: int | None = None,
) -> EngineeringDesignRecord:
    """Persist a read-only `AblationAdvisoryReport` into EDDBMS `GeometricData` & `PropertyData`."""
    if not isinstance(db, EngineeringDesignDatabase):
        raise ValueError(f"db must be an EngineeringDesignDatabase, got {type(db).__name__}")

    if isinstance(report, AblationAdvisoryReport):
        _check_report_invariants(report)
        payload = report.to_dict()
    elif isinstance(report, Mapping):
        payload = validate_constitutional_packet(report, epistemic_lane="measurement")
        if payload.get("advisory_only") is not True or payload.get("read_only") is not True:
            raise ConstitutionalViolationError("Attached ablation report must have advisory_only=True and read_only=True")
    else:
        raise ValueError(f"report must be AblationAdvisoryReport or Mapping, got {type(report).__name__}")

    resolved_rev = db.get_record(design_id).revision if expected_revision is None else expected_revision
    raw_findings = payload.get("findings", [])
    if (
        isinstance(raw_findings, (str, bytes, bytearray, Mapping))
        or not isinstance(raw_findings, Sequence)
    ):
        raise ConstitutionalViolationError(
            "Attached ablation report 'findings' must be a sequence of mappings"
        )
    findings_list: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_findings):
        if not isinstance(item, Mapping):
            raise ConstitutionalViolationError(
                f"Attached ablation report findings[{idx}] must be a Mapping, got {type(item).__name__}"
            )
        findings_list.append(dict(item))

    raw_byte_size = _validate_nonneg_int(payload.get("byte_size", 0), "byte_size")
    target_name_val, mode_val, summary_val = _validate_attached_mode_and_text(payload)
    binary_summary_map = _validate_attached_mapping(payload, "binary_summary")
    entropy_summary_map = _validate_attached_mapping(payload, "entropy_summary")
    auditor_map = _validate_attached_mapping(payload, "auditor_findings")
    raw_source = payload.get("source_audit")
    if raw_source is not None and not isinstance(raw_source, Mapping):
        raise ConstitutionalViolationError("Attached ablation report source_audit must be a Mapping or None")
    source_map: Mapping[str, Any] = raw_source if raw_source is not None else {}

    auditor_high: int | None = None
    if "high_severity_count" in auditor_map:
        auditor_high = _validate_nonneg_int(
            auditor_map["high_severity_count"],
            "auditor_findings.high_severity_count",
        )
    source_high: int | None = None
    if "high_or_critical" in source_map:
        source_high = _validate_nonneg_int(
            source_map["high_or_critical"],
            "source_audit.high_or_critical",
        )
    if auditor_high is not None and auditor_high > 0:
        high_count = auditor_high
    elif source_high is not None:
        high_count = source_high
    else:
        high_count = auditor_high if auditor_high is not None else 0

    ablation_geo = {
        "contract": ABLATION_BRIDGE_CONTRACT,
        "target_name": target_name_val,
        "target_path": payload.get("target_path"),
        "target_sha256": payload.get("target_sha256", sha256_canonical(payload)),
        "mode": mode_val,
        "byte_size": raw_byte_size,
        "arch": payload.get("arch", "unknown"),
        "summary": summary_val,
        "binary_summary": binary_summary_map,
        "entropy_summary": entropy_summary_map,
        "auditor_findings": auditor_map,
        "source_audit": payload.get("source_audit"),
        "findings": findings_list,
        "epistemic_lane": "measurement",
        "advisory_only": True,
        "read_only": True,
        "external_actions": 0,
        "tokens_used": 0,
        "cloud_cost_usd": 0.0,
        "loopback_only": True,
        "attribution": ATTRIBUTION_TEXT,
    }
    ablation_summary = {
        "contract": ABLATION_BRIDGE_CONTRACT,
        "target_name": ablation_geo["target_name"],
        "target_sha256": ablation_geo["target_sha256"],
        "mode": ablation_geo["mode"],
        "arch": ablation_geo["arch"],
        "byte_size": ablation_geo["byte_size"],
        "finding_count": len(findings_list),
        "high_severity_count": high_count,
        "epistemic_lane": "measurement",
        "advisory_only": True,
        "read_only": True,
    }
    patch = {
        "epistemic_lane": "measurement",
        "geometric": {"analysis_process_formats": {"ablation": ablation_geo}},
        "properties": {"structure_desc": {"ablation_summary": ablation_summary}},
        "sub_operations": {
            "evaluation": {
                "ablation_target": ablation_geo["target_name"],
                "ablation_sha256": ablation_geo["target_sha256"],
                "finding_count": len(findings_list),
            }
        },
        "notes": f"Read-only Ablation advisory attachment for {ablation_geo['target_name']}",
    }
    return db.write_from_module(
        design_id,
        "POSTPRODUCTION_MANAGEMENT",
        sister_name,
        patch,
        expected_revision=resolved_rev,
        epistemic_lane="measurement",
        sub_operation="evaluation",
    )


__all__ = [
    "ABLATION_BRIDGE_CONTRACT",
    "ALLOWED_INSPECTION_MODES",
    "ATTRIBUTION_TEXT",
    "FORBIDDEN_INSPECTION_MODES",
    "SAFETY_INVARIANTS",
    "AblationAdvisoryReport",
    "AblationBridge",
    "attach_ablation_to_eddms",
    "constitutional_metadata",
]
