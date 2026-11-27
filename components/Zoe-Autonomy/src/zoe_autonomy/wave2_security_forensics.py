"""
Wave 2 Security, Audio/MCP Defense, Forensics, and Crypto-Analysis Bridges for Zoe.

Integrates non-biology Wave 2 NuClide / Nicholas Kloster components cleanly into
`zoe_autonomy` while preserving `docs/CONSTITUTION.md` invariants:
  - `dBA` (`components/dBA`) — ASR audio metadata firewall (raw tags never leave)
  - `metrix` (`components/metrix`) — evidence-first non-executing RE corpus inventory
  - `gemseal` (`components/gemseal`) — HKDF-SHA256 + ChaCha20-Poly1305 sealed containers
  - `mcp-security` (`components/mcp-security`) — `mcp_scan` + `mcp_guard` MCP defense
  - `cortex-framework` (`components/cortex-framework`) — authorization context analyzer
  - `nuclide-asset-schema` (`components/nuclide-asset-schema`) — JSON Schema 2020-12 asset contract
  - `RXVM` + `ablation.analyzers.rxvm_crypto_analyzer` — VM/WebCrypto anti-pattern & rxc= analyzer
  - Native Go/Rust security & verification suites (`spectral`, `VisorCorpus`, `VisorAgent`,
    `VisorCAS`, `VisorScuba`, `VisorLog`, `safety-stream`, `nuclide-method`, `white-bronco`)
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _components_dir() -> Path:
    return _repo_root() / "components"


def _load_module_from_file(module_name: str, file_path: Path) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_sys_path(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


# ── 1. dBA — Audio Metadata Firewall for ASR Pipelines ────────────────────────

_DBA_FALLBACK_PATTERNS = [
    ("TAG_VIPER", "high", re.compile(r"\[VIPER\]", re.IGNORECASE), False),
    ("TAG_SEIZURE_MARKER", "high", re.compile(r"<SEIZURE_SHORT>", re.IGNORECASE), False),
    ("TAG_OPERATION_ID", "high", re.compile(r"<OP_ID>|<OPERATION_ID>", re.IGNORECASE), False),
    ("TAG_POTENTIAL_SHELL", "high", re.compile(r";\s*curl\b|\bwget\b|\bbash\s+-i", re.IGNORECASE), False),
    ("TAG_CMD_SUBSTITUTION", "high", re.compile(r"\$\(|`", re.IGNORECASE), False),
    ("TAG_HTML_SCRIPT", "medium", re.compile(r"<script\b", re.IGNORECASE), False),
    ("TAG_AWS_KEY", "high", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b", re.IGNORECASE), True),
    ("TAG_PRIVATE_KEY", "high", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE), True),
]


def screen_audio_metadata_with_dba(
    raw_meta: Dict[str, Any],
    *,
    mode: str = "strict",
) -> Dict[str, Any]:
    """
    Evaluate raw ffprobe-shaped audio container metadata using `components/dBA`.

    Raw tag values never pass through; suspicious secrets are masked in snippets.
    Falls back cleanly to the identical pure-Python policy rules if FastAPI is
    not installed in the host interpreter.
    """
    dba_path = _components_dir() / "dBA" / "main.py"
    try:
        dba = _load_module_from_file("_zoe_dba_main", dba_path)
        sanitized, indicators, score, disposition = dba.analyze_metadata(raw_meta, mode=mode)
        return {
            "backend": "dBA",
            "mode": mode,
            "risk_score": int(score),
            "disposition": str(disposition),
            "indicator_count": len(indicators),
            "indicators": [ind.model_dump() for ind in indicators],
            "sanitized_metadata": sanitized.model_dump(),
            "raw_tags_stripped": True,
        }
    except ImportError:
        # Pure-stdlib mirror of dBA's policy rules when FastAPI/Pydantic are absent
        fmt = raw_meta.get("format", {}) or {}
        streams = raw_meta.get("streams", []) or []
        audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
        indicators: List[Dict[str, Any]] = []
        if not audio_streams:
            indicators.append({"id": "NO_AUDIO_STREAM", "severity": "high", "detail": "File contains no audio stream."})
        tags_sources = [fmt.get("tags", {}) or {}] + [s.get("tags", {}) or {} for s in streams]
        for tags in tags_sources:
            for k, v in tags.items():
                text = f"{k}: {v}"
                for pid, sev, pat, mask in _DBA_FALLBACK_PATTERNS:
                    if pat.search(text):
                        snippet = str(v)[:80]
                        if mask:
                            snippet = pat.sub("***", snippet)
                        indicators.append({"id": pid, "severity": sev, "key": str(k)[:80], "value_snippet": snippet})
        weights = {"low": 10, "medium": 25, "high": 40}
        score = min(100, sum(weights.get(i["severity"], 0) for i in indicators))
        if mode == "strict" and indicators:
            score = min(100, score + 10)
        elif mode == "lenient":
            score = max(0, score - 10)
        if mode == "audit":
            disp = "allow"
        elif mode == "strict":
            disp = "allow" if score < 10 else ("quarantine" if score < 40 else "reject")
        else:
            disp = "allow" if score < 30 else ("quarantine" if score < 80 else "reject")
        audio0 = audio_streams[0] if audio_streams else {}
        return {
            "backend": "dBA-stdlib-fallback",
            "mode": mode,
            "risk_score": score,
            "disposition": disp,
            "indicator_count": len(indicators),
            "indicators": indicators,
            "sanitized_metadata": {
                "codec_name": audio0.get("codec_name"),
                "container_format": (fmt.get("format_name") or "").split(",")[0] or None,
                "tags": {},
            },
            "raw_tags_stripped": True,
        }


# ── 2. metrix — Evidence-First Non-Executing RE Corpus Inventory ──────────────

def inventory_re_corpus_with_metrix(
    root_dir: str | Path,
    output_dir: str | Path,
) -> Dict[str, Any]:
    """
    Run `components/metrix` over a reverse-engineering corpus directory without
    executing any artifact or following symlinks (TOCTOU-verified SHA-256 + magic bytes).
    """
    _ensure_sys_path(_components_dir() / "metrix")
    from metrix import inventory as metrix_inventory  # type: ignore

    result = metrix_inventory.scan(root_dir, output_dir)
    if isinstance(result, dict):
        return result
    # Fallback summary if scan writes files and returns manifest path/tuple
    out_path = Path(output_dir)
    manifest_file = out_path / "inventory.json"
    if manifest_file.is_file():
        return json.loads(manifest_file.read_text(encoding="utf-8"))
    return {"output_dir": str(out_path), "result": str(result)}


# ── 3. gemseal — Authenticated-Encryption Evidence Container ──────────────────

def seal_evidence_with_gemseal(
    source: str | Path,
    destination: str | Path,
    master_key: Optional[bytes] = None,
    *,
    chunk_size: int = 4096,
) -> Dict[str, Any]:
    """Encrypt a file into a GEMSEAL HKDF-SHA256 + ChaCha20-Poly1305 container."""
    gemseal = _load_module_from_file("_zoe_gemseal", _components_dir() / "gemseal" / "gemseal.py")
    key = master_key if master_key is not None else os.urandom(gemseal.KEY_SIZE)
    gemseal.encrypt_file(key, str(source), str(destination), chunk_size=chunk_size)
    return {
        "source": str(source),
        "destination": str(destination),
        "suite": "HKDF-SHA256+ChaCha20-Poly1305",
        "key_bytes": len(key),
        "sealed_bytes": Path(destination).stat().st_size,
        "master_key_hex": key.hex() if master_key is None else "<caller-supplied>",
    }


def unseal_evidence_with_gemseal(
    source: str | Path,
    destination: str | Path,
    master_key: bytes,
) -> Dict[str, Any]:
    """Verify and decrypt a GEMSEAL container (fails closed on any header/tag tampering)."""
    gemseal = _load_module_from_file("_zoe_gemseal", _components_dir() / "gemseal" / "gemseal.py")
    gemseal.decrypt_file(master_key, str(source), str(destination))
    return {
        "source": str(source),
        "destination": str(destination),
        "verified_and_decrypted": True,
        "plaintext_bytes": Path(destination).stat().st_size,
    }


# ── 4. mcp-security — Pre-Connection Scanner & Rug-Pull / Path Guard ──────────

def scan_mcp_server_with_mcp_security(
    target_path: str | Path,
    *,
    mcp_json_only: bool = False,
) -> Dict[str, Any]:
    """Run `components/mcp-security/security-layer/mcp_scan.py` on a manifest or MCP server."""
    mcp_scan = _load_module_from_file(
        "_zoe_mcp_scan",
        _components_dir() / "mcp-security" / "security-layer" / "mcp_scan.py",
    )
    findings = mcp_scan.scan_path(Path(target_path), mcp_json_only=mcp_json_only)
    return {
        "target": str(target_path),
        "finding_count": len(findings),
        "has_critical": any(f.severity == "CRITICAL" for f in findings),
        "findings": [
            {
                "file": f.file,
                "line": f.line,
                "severity": f.severity,
                "issue": f.issue,
                "detail": f.detail,
            }
            for f in findings
        ],
    }


def screen_mcp_tool_with_guard(
    tool_name: str,
    description: str,
    *,
    arguments: Optional[Dict[str, Any]] = None,
    project_root: Optional[str | Path] = None,
    previous_hash: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Screen an MCP tool definition and call arguments using `mcp_guard.py`:
    checks tool description injection, SHA-256 rug-pull drift, and path confinement.
    """
    mcp_guard = _load_module_from_file(
        "_zoe_mcp_guard",
        _components_dir() / "mcp-security" / "security-layer" / "mcp_guard.py",
    )
    record = mcp_guard.ToolRecord.from_tool({"name": tool_name, "description": description})
    injection_hits = mcp_guard._scan_description(description)
    rug_pull_detected = bool(previous_hash and previous_hash != record.description_hash)

    path_violations: List[str] = []
    root_path = Path(project_root).resolve() if project_root else None
    for k, v in (arguments or {}).items():
        for viol in mcp_guard._check_path_argument(v, root_path):
            path_violations.append(f"{k}: {viol}")

    blocked = bool(injection_hits or rug_pull_detected or path_violations)
    return {
        "tool_name": tool_name,
        "description_hash": record.description_hash,
        "rug_pull_detected": rug_pull_detected,
        "injection_hits": injection_hits,
        "path_violations": path_violations,
        "allowed": not blocked,
    }


# ── 5. cortex-framework — Authorization Context Analyzer ──────────────────────

def analyze_authorization_context_with_cortex(markdown_path: str | Path) -> Dict[str, Any]:
    """Parse and validate a Cortex Authorization Context specification file."""
    cortex = _load_module_from_file(
        "_zoe_cortex_analyzer",
        _components_dir() / "cortex-framework" / "analyzer.py",
    )
    analysis = cortex.parse_markdown(Path(markdown_path))
    ok, issues = cortex.validate(analysis)
    return {
        "source": str(markdown_path),
        "title": analysis.analysis_name,
        "valid": bool(ok),
        "issues": list(issues),
        "summary": analysis.analysis_summary,
        "bucket_counts": {
            "skeleton": len(analysis.skeleton),
            "violations": len(analysis.violations),
            "context": len(analysis.context),
        },
    }


# ── 6. nuclide-asset-schema — JSON Schema 2020-12 Record Validator ────────────

def validate_asset_record_with_schema(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate an asset/service/finding record against `visor-asset.schema.json`."""
    schema_path = _components_dir() / "nuclide-asset-schema" / "visor-asset.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        import jsonschema  # type: ignore

        validator = jsonschema.Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        return {
            "schema": str(schema_path),
            "backend": "jsonschema-2020-12",
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "errors": [e.message for e in errors],
        }
    except ImportError:
        required = schema.get("required", [])
        missing = [k for k in required if k not in record]
        return {
            "schema": str(schema_path),
            "backend": "stdlib-required-fields",
            "valid": len(missing) == 0,
            "error_count": len(missing),
            "errors": [f"missing required field: {k}" for k in missing],
        }


# ── 7. RXVM + Ablation Custom-VM & WebCrypto Crypto-Layer Bridge ─────────────

def analyze_rxvm_crypto_pipeline(
    source: str | Path,
    *,
    is_file: bool = False,
    render_markdown: bool = False,
) -> Dict[str, Any]:
    """Run `ablation.analyzers.rxvm_crypto_analyzer` over disassembly or JS source."""
    mod = _load_module_from_file(
        "_zoe_rxvm_crypto_analyzer",
        _components_dir() / "ablation" / "ablation" / "analyzers" / "rxvm_crypto_analyzer.py",
    )
    report = mod.analyze_rxvm_file(source) if is_file else mod.analyze_rxvm_source(str(source))
    out = report.to_dict()
    if render_markdown:
        out["markdown"] = mod.render_annotated_markdown(report)
    return out


def decrypt_rxvm_rxc_cookie(cookie_b64: str) -> Dict[str, Any]:
    """Decrypt an RXVM `rxc=` cookie (unpadded Base64, RC4, timestamp, metrics, float16)."""
    mod = _load_module_from_file(
        "_zoe_rxvm_crypto_analyzer",
        _components_dir() / "ablation" / "ablation" / "analyzers" / "rxvm_crypto_analyzer.py",
    )
    return mod.decrypt_rxc_cookie(cookie_b64)


def analyze_a10_quantization_saturation(
    model_or_path: Optional[Dict[str, Any] | str | Path] = None,
) -> Dict[str, Any]:
    """Audit extracted quantized MLP weights (default: `components/RXVM/a10_model_weights.json`)."""
    mod = _load_module_from_file(
        "_zoe_rxvm_crypto_analyzer",
        _components_dir() / "ablation" / "ablation" / "analyzers" / "rxvm_crypto_analyzer.py",
    )
    target = (
        _components_dir() / "RXVM" / "a10_model_weights.json"
        if model_or_path is None
        else model_or_path
    )
    return mod.analyze_quantization_saturation(target)


def analyze_beam_obfuscation(
    raw_or_path: bytes | str | Path,
    *,
    is_file: bool = False,
) -> Dict[str, Any]:
    """Run strict `.beam` EA IFF 85 container, atom-entropy, and poisoned-zlib checks."""
    mod = _load_module_from_file(
        "_zoe_beam_obfuscation_analyzer",
        _components_dir() / "ablation" / "ablation" / "analyzers" / "beam_obfuscation_analyzer.py",
    )
    rep = mod.analyze_beam_file(raw_or_path) if is_file else mod.analyze_beam_bytes(bytes(raw_or_path))
    return rep.to_dict()


# ── 8. Native Go / Rust / Docs Wave 2 Security Suite Inventory ────────────────

def wave2_native_tooling_inventory() -> Dict[str, Any]:
    """Report availability and paths of vendored Go/Rust/CVD Wave 2 security tools."""
    comp = _components_dir()
    tools = {
        "spectral": {"lang": "rust", "path": str(comp / "spectral"), "present": (comp / "spectral" / "Cargo.toml").is_file()},
        "VisorCorpus": {"lang": "go", "path": str(comp / "VisorCorpus"), "present": (comp / "VisorCorpus" / "go.mod").is_file()},
        "VisorAgent": {"lang": "go", "path": str(comp / "VisorAgent"), "present": (comp / "VisorAgent" / "go.mod").is_file()},
        "VisorCAS": {"lang": "go", "path": str(comp / "VisorCAS"), "present": (comp / "VisorCAS" / "go.mod").is_file()},
        "VisorScuba": {"lang": "go+rego", "path": str(comp / "VisorScuba"), "present": (comp / "VisorScuba" / "go.mod").is_file()},
        "VisorLog": {"lang": "go", "path": str(comp / "VisorLog"), "present": (comp / "VisorLog" / "go.mod").is_file()},
        "safety-stream": {"lang": "go", "path": str(comp / "safety-stream"), "present": (comp / "safety-stream" / "go.mod").is_file()},
        "nuclide-method": {"lang": "shell+docs", "path": str(comp / "nuclide-method"), "present": (comp / "nuclide-method" / "README.md").is_file()},
        "white-bronco": {"lang": "latex+cvd", "path": str(comp / "white-bronco"), "present": (comp / "white-bronco" / "README.md").is_file()},
    }
    return {
        "toolchains": {
            "go": shutil.which("go") is not None,
            "cargo": shutil.which("cargo") is not None,
        },
        "present_count": sum(1 for t in tools.values() if t["present"]),
        "total_count": len(tools),
        "tools": tools,
    }
