"""Unified 42-Component Zoe-GEM OS Architecture Registry, Spotlight Launcher & Airlock.

Transforms all 42 Wave 1 & Wave 2 components from `config/portfolio-upgrades.lock.json`
into cohesive native Zoe-GEM OS Kernel Drivers (`*.SYS`), Desk Accessories (`*.ACC`),
and GEM Applications (`*.APP`) across 5 Suites and the 9 Sisters hexagonal grid.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from ..model import Scene
from ..zoe_hex_mesh import DEFAULT_SISTER_COORDS

CONTRACT = "zoe-gem-os-unification/v1"
REPO_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_REL = Path("config/zoe-os-unification.json")

UNIFIED_OS_LAYERS: dict[str, tuple[str, str]] = {
    "unified-os": ("zoe", "Zoe-GEM OS · Unified 42-Component One-OS Architecture (5 Suites · 9 Sisters)"),
    "suite1-kernel": ("kevlar", "Zoe-GEM OS Suite 1 · Kernel Firewall, Policy & Stewardship (SYSCALL/VAULT/EXPORT)"),
    "suite2-telemetry": ("autonomy", "Zoe-GEM OS Suite 2 · Defensive Telemetry, Compliance & Audit Bench (JOURNAL/SCUBA/SYSMAP)"),
    "suite3-forensics": ("ablation", "Zoe-GEM OS Suite 3 · Forensics, Binary Analysis & Disclosure Lab (INTAKE/AUDIT/CEROTTO/CVD)"),
    "suite4-cognition": ("research", "Zoe-GEM OS Suite 4 · Cognitive Metacognition, Memory & Reasoning Core (VOLUME/MEMBUS/GLASSBOX)"),
    "suite5-studio": ("zoe", "Zoe-GEM OS Suite 5 · Voice, Audio Defense, Color, Biology & Visual Studio (LUME/CHROMA/SPOTLIGHT)"),
}

# Authentic Digital Research GEM/3 & ViewMAX palette colors
_C_BG = "#ffffff"
_C_INK = "#000000"
_C_CHROME = "#adaaad"
_C_MUTED = "#525552"
_C_BLUE = "#0000ad"
_C_TEAL = "#00aaad"
_C_GREEN = "#00aa00"
_C_CRIMSON = "#ad0000"
_C_GOLD = "#adaa00"
_C_PURPLE = "#ad00ad"

_SUITE_ACCENT: dict[int, str] = {
    1: _C_CRIMSON,
    2: _C_BLUE,
    3: _C_TEAL,
    4: _C_PURPLE,
    5: _C_GREEN,
}


def load_os_unification_manifest(repo_root: Path | None = None) -> dict[str, Any]:
    """Load the canonical 42-component Zoe-GEM OS unification manifest."""
    root = Path(repo_root or REPO_ROOT).resolve()
    manifest_path = root / MANIFEST_REL
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data


def list_unified_components(
    repo_root: Path | None = None,
    *,
    suite: int | None = None,
    sister: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    """List unified OS components with optional filtering by suite, sister, or unit kind."""
    root = Path(repo_root or REPO_ROOT).resolve()
    data = load_os_unification_manifest(root)
    sister_q = (sister or "").strip().lower()
    kind_q = (kind or "").strip().lower()
    out: list[dict[str, Any]] = []
    for item in data.get("components", []):
        if suite is not None and int(item["suite"]) != int(suite):
            continue
        if sister_q and str(item.get("sister", "")).lower() != sister_q:
            continue
        if kind_q and str(item.get("kind", "")).lower() != kind_q:
            continue
        enriched = dict(item)
        src = root / str(item["source_path"])
        enriched["source_present"] = src.is_dir()
        coords = DEFAULT_SISTER_COORDS.get(str(item.get("sister", "")).lower())
        enriched["sister_coords"] = list(coords) if coords is not None else [0, 0]
        out.append(enriched)
    return out


def os_suite_status(repo_root: Path | None = None) -> dict[str, Any]:
    """Summarize the 5 Zoe-GEM OS suites, distinct OS units, and live source availability."""
    root = Path(repo_root or REPO_ROOT).resolve()
    data = load_os_unification_manifest(root)
    comps = list_unified_components(root)
    present_count = sum(1 for c in comps if c["source_present"])

    distinct_by_kind: dict[str, set[str]] = {"sys": set(), "acc": set(), "app": set()}
    sisters_covered: set[str] = set()
    suite_summaries: list[dict[str, Any]] = []

    for c in comps:
        k = str(c["kind"]).lower()
        if k in distinct_by_kind:
            distinct_by_kind[k].add(str(c["os_unit"]))
        sisters_covered.add(str(c["sister"]).lower())

    for s in data.get("suites", []):
        sid = int(s["id"])
        s_comps = [c for c in comps if int(c["suite"]) == sid]
        suite_summaries.append({
            "id": sid,
            "slug": s["slug"],
            "name": s["name"],
            "component_count": len(s_comps),
            "present_count": sum(1 for c in s_comps if c["source_present"]),
            "os_units": sorted({str(c["os_unit"]) for c in s_comps}),
            "primary_sisters": list(s.get("primary_sisters", [])),
        })

    return {
        "contract": CONTRACT,
        "system_name": data.get("system_name", "Zoe-GEM OS (GEMZ)"),
        "canonical_repository": data.get("canonical_repository", "https://github.com/Nicholas-Michael-Kloster/Zoe"),
        "total_components": len(comps),
        "sources_present": present_count,
        "all_sources_present": present_count == len(comps) and len(comps) == 42,
        "suite_count": len(suite_summaries),
        "distinct_units": {
            "sys": sorted(distinct_by_kind["sys"]),
            "acc": sorted(distinct_by_kind["acc"]),
            "app": sorted(distinct_by_kind["app"]),
        },
        "distinct_unit_counts": {k: len(v) for k, v in distinct_by_kind.items()},
        "sisters_covered": sorted(sisters_covered),
        "suites": suite_summaries,
        "constitutional_invariants": dict(data.get("constitutional_invariants", {})),
    }


def _tokenize(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9_]+", text.lower()) if len(tok) >= 2}


def spotlight_route(query: str, repo_root: Path | None = None, *, limit: int = 5) -> dict[str, Any]:
    """SPOTLIGHT.ACC semantic router: match plain-English goals to Zoe-GEM OS units."""
    root = Path(repo_root or REPO_ROOT).resolve()
    comps = list_unified_components(root)
    q_clean = str(query or "").strip()
    q_tokens = _tokenize(q_clean)
    q_lower = q_clean.lower()

    scored: list[tuple[float, dict[str, Any]]] = []
    for c in comps:
        score = 0.0
        src_id = str(c["source_id"]).lower()
        os_unit = str(c["os_unit"]).lower()
        sister = str(c["sister"]).lower()
        title = str(c["role_title"]).lower()
        summary = str(c["summary"]).lower()
        kws = {str(k).lower() for k in c.get("keywords", [])}

        if q_lower and (q_lower == src_id or q_lower == os_unit or q_lower in os_unit):
            score += 12.0
        for tok in q_tokens:
            if tok == src_id or tok == os_unit.split(".")[0]:
                score += 6.0
            if tok == sister:
                score += 2.5
            if tok in kws:
                score += 4.0
            elif any(tok in kw or kw in tok for kw in kws if len(tok) >= 3):
                score += 2.0
            if tok in title:
                score += 2.5
            if tok in summary:
                score += 1.2
        if score > 0.0:
            scored.append((round(score, 2), c))

    scored.sort(key=lambda pair: (-pair[0], int(pair[1]["index"])))
    top = [
        {
            "score": sc,
            "index": c["index"],
            "source_id": c["source_id"],
            "os_unit": c["os_unit"],
            "kind": c["kind"],
            "role_title": c["role_title"],
            "sister": c["sister"],
            "sister_coords": c["sister_coords"],
            "suite": c["suite"],
            "gem_layer": c["gem_layer"],
            "source_present": c["source_present"],
            "summary": c["summary"],
        }
        for sc, c in scored[: max(1, int(limit))]
    ]
    return {
        "contract": "zoe-spotlight-acc/v1",
        "query": q_clean,
        "match_count": len(top),
        "matches": top,
        "loopback_only": True,
        "external_actions": 0,
    }


def run_export_airlock(repo_root: Path | None = None, *, fail_on: str = "MEDIUM") -> dict[str, Any]:
    """EXPORT.ACC airlock: run github-tos-audit offline against the repository."""
    root = Path(repo_root or REPO_ROOT).resolve()
    audit_dir = root / "components" / "github-tos-audit"
    if str(audit_dir) not in sys.path:
        sys.path.insert(0, str(audit_dir))
    import github_tos_audit as gta

    rel_paths = gta.tracked_files(root)
    stats = gta.ScanStats()
    findings: list[Any] = []
    findings += gta.check_text(root, rel_paths, ["credentials", "malware", "dmca", "export"], int(2 * 1024 * 1024), stats)
    findings += gta.check_sensitive_files(rel_paths)
    findings += gta.check_vendors(root, fetch=False)
    findings += gta.check_binaries(root, rel_paths)

    allowlist, warnings = gta.load_allowlist(root)
    fail_ord = gta.SEVERITY_ORDER.get(fail_on.upper(), 2)
    kept: list[Any] = []
    suppressed: list[tuple[Any, str]] = []
    for f in findings:
        if f.verified()[0] == gta.VERIFY_STATUS_REJECTED:
            continue
        reason = gta.suppression_reason(f, allowlist)
        if reason is not None:
            suppressed.append((f, reason))
        else:
            kept.append(f)

    kept_at_or_above = [f for f in kept if gta.SEVERITY_ORDER[f.severity] <= fail_ord]
    exit_code = 1 if kept_at_or_above else 0
    return {
        "contract": "zoe-export-acc/v1",
        "repository": str(root),
        "fail_on": fail_on.upper(),
        "exit_code": exit_code,
        "ok": exit_code == 0,
        "files_scanned": stats.scanned,
        "unsuppressed_count": len(kept),
        "unsuppressed_at_or_above_fail_on": len(kept_at_or_above),
        "suppressed_allowlisted_count": len(suppressed),
        "allowlist_entries": len(allowlist),
        "warnings": warnings,
        "unsuppressed_samples": [f.as_dict() for f in kept[:10]],
        "loopback_only": True,
        "external_actions": 0,
    }


def verify_unified_os(repo_root: Path | None = None, *, include_airlock: bool = True) -> dict[str, Any]:
    """Run complete offline verification of the 42-component Zoe-GEM OS unification."""
    root = Path(repo_root or REPO_ROOT).resolve()
    status = os_suite_status(root)
    comps = list_unified_components(root)

    indices = [int(c["index"]) for c in comps]
    source_ids = [str(c["source_id"]) for c in comps]
    valid_sisters = all(str(c["sister"]) in DEFAULT_SISTER_COORDS for c in comps)
    inv = status["constitutional_invariants"]
    honest = (
        inv.get("sentience_claimed") is False
        and inv.get("l5_agi_qualified") is False
        and inv.get("clinical_action_authorized") is False
        and inv.get("cure_claim") is False
        and inv.get("auto_flash_allowed") is False
        and inv.get("external_actions") == 0
    )

    checks: dict[str, bool] = {
        "exact_42_components": len(comps) == 42 and indices == list(range(1, 43)),
        "unique_source_ids": len(set(source_ids)) == 42,
        "all_42_sources_present": bool(status["all_sources_present"]),
        "all_5_suites_populated": len(status["suites"]) == 5 and all(s["component_count"] > 0 for s in status["suites"]),
        "valid_9_sister_seats": valid_sisters,
        "constitutional_invariants": honest,
    }

    airlock: dict[str, Any] | None = None
    if include_airlock:
        airlock = run_export_airlock(root)
        checks["export_airlock_clean"] = bool(airlock["ok"])

    return {
        "contract": CONTRACT,
        "ok": all(checks.values()),
        "checks": checks,
        "status": status,
        "airlock": airlock,
    }


def unified_os_document(module: str = "unified-os", repo_root: Path | None = None) -> tuple[Scene, dict[str, Any]]:
    """Build a verified Digital Research GEM Spatial IR scene for Zoe-GEM OS unification."""
    root = Path(repo_root or REPO_ROOT).resolve()
    status = os_suite_status(root)
    comps = list_unified_components(root)

    suite_filter: int | None = None
    for s in status["suites"]:
        if module == s["slug"]:
            suite_filter = int(s["id"])
            break

    title = UNIFIED_OS_LAYERS.get(module, UNIFIED_OS_LAYERS["unified-os"])[1]
    accent = _SUITE_ACCENT.get(suite_filter or 0, _C_BLUE)
    counts = status["distinct_unit_counts"]
    info = (
        f"Components: {status['sources_present']}/{status['total_components']}  |  "
        f"Drivers (*.SYS): {counts['sys']}  |  Accessories (*.ACC): {counts['acc']}  |  "
        f"Apps (*.APP): {counts['app']}  |  Sisters: {len(status['sisters_covered'])}/9  |  Offline $0.00"
    )

    objects: list[dict[str, Any]] = [
        {
            "id": "gem_menubar",
            "type": "rectangle",
            "role": "menubar",
            "bounds": [0, 0, 12800, 360],
            "fill": _C_CHROME,
            "stroke": _C_INK,
            "width": 16,
        },
        {
            "id": "gem_menu_left",
            "type": "text",
            "role": "menu_text",
            "position": [180, 240],
            "text": "Desk   File   View   Suites   Sisters   Airlock",
            "size": 150,
            "stroke": _C_INK,
        },
        {
            "id": "gem_menu_right",
            "type": "text",
            "role": "menu_badge",
            "position": [9400, 240],
            "text": "Zoe-GEM OS · 42/42 Unified",
            "size": 140,
            "stroke": _C_BLUE,
        },
        {
            "id": "gem_window_frame",
            "type": "rectangle",
            "role": "window",
            "bounds": [240, 500, 12560, 7380],
            "fill": _C_BG,
            "stroke": _C_INK,
            "width": 20,
        },
        {
            "id": "gem_window_titlebar",
            "type": "rectangle",
            "role": "titlebar",
            "bounds": [240, 500, 12560, 880],
            "fill": accent,
            "stroke": _C_INK,
            "width": 20,
        },
        {
            "id": "gem_window_title_text",
            "type": "text",
            "role": "title",
            "position": [420, 740],
            "text": title,
            "size": 160,
            "stroke": _C_BG,
        },
        {
            "id": "gem_info_bar",
            "type": "rectangle",
            "role": "infobar",
            "bounds": [240, 880, 12560, 1180],
            "fill": _C_CHROME,
            "stroke": _C_INK,
            "width": 12,
        },
        {
            "id": "gem_info_text",
            "type": "text",
            "role": "info",
            "position": [420, 1080],
            "text": info,
            "size": 125,
            "stroke": _C_INK,
        },
    ]

    card_ids: list[str] = []
    if suite_filter is None:
        coords_grid = [
            (460, 1340, 4220, 4080),
            (4520, 1340, 8280, 4080),
            (8580, 1340, 12340, 4080),
            (1800, 4300, 6240, 7120),
            (6560, 4300, 11000, 7120),
        ]
        for s, (x1, y1, x2, y2) in zip(status["suites"], coords_grid):
            sid = int(s["id"])
            s_acc = _SUITE_ACCENT[sid]
            cid = f"suite_card_{sid}"
            card_ids.append(cid)
            objects.extend([
                {
                    "id": cid,
                    "type": "rectangle",
                    "role": "suite_card",
                    "bounds": [x1, y1, x2, y2],
                    "fill": _C_BG,
                    "stroke": _C_INK,
                    "width": 18,
                },
                {
                    "id": f"suite_hdr_{sid}",
                    "type": "rectangle",
                    "role": "suite_header",
                    "bounds": [x1, y1, x2, y1 + 320],
                    "fill": s_acc,
                    "stroke": _C_INK,
                    "width": 16,
                },
                {
                    "id": f"suite_title_{sid}",
                    "type": "text",
                    "role": "suite_title",
                    "position": [x1 + 120, y1 + 215],
                    "text": f"Suite {sid} · {s['name'][:30]}",
                    "size": 125,
                    "stroke": _C_BG,
                },
                {
                    "id": f"suite_meta_{sid}",
                    "type": "text",
                    "role": "suite_meta",
                    "position": [x1 + 120, y1 + 520],
                    "text": f"{s['present_count']}/{s['component_count']} live · {', '.join(s['primary_sisters'])}",
                    "size": 110,
                    "stroke": _C_MUTED,
                },
            ])
            s_comps = [c for c in comps if int(c["suite"]) == sid]
            row_y = y1 + 760
            for c in s_comps[:9]:
                label = f"{c['index']:02d}. {c['source_id']} -> {c['os_unit']}"
                objects.append({
                    "id": f"suite_{sid}_item_{c['index']}",
                    "type": "text",
                    "role": "component_row",
                    "position": [x1 + 140, row_y],
                    "text": label[:42],
                    "size": 110,
                    "stroke": _C_INK,
                })
                row_y += 205
    else:
        s_comps = [c for c in comps if int(c["suite"]) == suite_filter]
        card_w = 5760
        card_h = 1000
        for idx, c in enumerate(s_comps):
            col = idx % 2
            row = idx // 2
            x1 = 460 + col * (card_w + 360)
            y1 = 1320 + row * (card_h + 180)
            if y1 + card_h > 7280:
                break
            cid = f"comp_card_{c['index']}"
            card_ids.append(cid)
            objects.extend([
                {
                    "id": cid,
                    "type": "rectangle",
                    "role": "component_card",
                    "bounds": [x1, y1, x1 + card_w, y1 + card_h],
                    "fill": _C_BG,
                    "stroke": _C_INK,
                    "width": 16,
                },
                {
                    "id": f"comp_badge_{c['index']}",
                    "type": "rectangle",
                    "role": "unit_badge",
                    "bounds": [x1, y1, x1 + 1280, y1 + card_h],
                    "fill": _C_CHROME,
                    "stroke": _C_INK,
                    "width": 12,
                },
                {
                    "id": f"comp_unit_{c['index']}",
                    "type": "text",
                    "role": "unit_name",
                    "position": [x1 + 120, y1 + 420],
                    "text": str(c["os_unit"]),
                    "size": 125,
                    "stroke": accent,
                },
                {
                    "id": f"comp_sis_{c['index']}",
                    "type": "text",
                    "role": "sister_name",
                    "position": [x1 + 120, y1 + 680],
                    "text": str(c["sister"]).upper(),
                    "size": 110,
                    "stroke": _C_INK,
                },
                {
                    "id": f"comp_hdr_{c['index']}",
                    "type": "text",
                    "role": "component_title",
                    "position": [x1 + 1400, y1 + 300],
                    "text": f"#{c['index']:02d} {c['source_id']} · {c['role_title']}"[:44],
                    "size": 110,
                    "stroke": _C_INK,
                },
                {
                    "id": f"comp_sum_{c['index']}",
                    "type": "text",
                    "role": "component_summary",
                    "position": [x1 + 1400, y1 + 560],
                    "text": str(c["summary"])[:52],
                    "size": 95,
                    "stroke": _C_MUTED,
                },
                {
                    "id": f"comp_src_{c['index']}",
                    "type": "text",
                    "role": "component_source",
                    "position": [x1 + 1400, y1 + 800],
                    "text": f"{c['source_path']} ({'OK' if c['source_present'] else 'MISSING'})"[:52],
                    "size": 95,
                    "stroke": _C_GREEN if c["source_present"] else _C_CRIMSON,
                },
            ])

    constraints: list[dict[str, Any]] = [{"type": "inside_canvas", "object": "*"}]
    if len(card_ids) > 1:
        constraints.append({"type": "nonoverlap", "objects": card_ids})

    scene = Scene.from_dict({
        "schema_version": 1,
        "id": f"zoe-os-{module}",
        "title": title,
        "prompt": "Zoe is Creative Intelligence of Western origin meaning 'life.'",
        "canvas": {"width": 12800, "height": 7600},
        "objects": objects,
        "constraints": constraints,
    })
    report = {
        "contract": CONTRACT,
        "module": module,
        "suite_filter": suite_filter,
        "status": status,
    }
    return scene, report
