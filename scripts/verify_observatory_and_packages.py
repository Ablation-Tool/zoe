#!/usr/bin/env python3
"""Offline Verifier for Dorothy 3D Human Brain Observatory, Desktop/Mobile Packaging & Research Ledger."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OBS = ROOT / "dorothy-brain-observatory"
DESK = ROOT / "desktop"
REPORT_PATH = ROOT / "evidence" / "dorothy-brain-observatory" / "observatory-verification.json"

CORE_OBS_FILES = (
    "index.html",
    "sw.js",
    "manifest.webmanifest",
    "assets/observatory.js",
    "assets/zoe_neuro_qa.js",
    "assets/three.min.js",
    "data/brain_meshes.js",
    "data/atlas_encyclopedia.js",
    "data/library_vault.js",
)

LINK_RE = re.compile(r'(?:href|src)="([^"]+)"|\]\(([^)]+)\)')


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _check_observatory_core() -> tuple[bool, dict]:
    records = {}
    all_ok = True
    for rel in CORE_OBS_FILES:
        fp = OBS / rel
        exists = fp.is_file() and fp.stat().st_size > 100
        all_ok = all_ok and exists
        records[rel] = {
            "exists": exists,
            "bytes": fp.stat().st_size if exists else 0,
            "sha256_16": _sha256_file(fp)[:16] if exists else "",
        }
    return all_ok, records


def _check_plates_cad_and_media() -> tuple[bool, dict]:
    plates_dir = OBS / "plates"
    plate_imgs = sorted(
        p.name for p in plates_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".png", ".jpg", ".svg") and not p.name.startswith("COMPLETE_")
    )
    poster_ok = (plates_dir / "COMPLETE_HUMAN_BRAIN_MAP_POSTER.jpg").is_file()
    mri_sheets = sorted(p.name for p in (OBS / "mri_slices").glob("*_sheet.jpg"))
    cad_meshes = sorted(
        p.name for p in (OBS / "3d_models").iterdir()
        if p.is_file() and p.suffix.lower() in (".obj", ".ply", ".stl")
    )
    blender_ok = (OBS / "3d_models" / "import_dorothy_brain.py").is_file()
    previews = OBS / "previews"
    tours_ok = (
        (previews / "web_brain_tour.gif").is_file()
        and (previews / "zoe_app_research_partner_tour.gif").is_file()
        and (previews / "complete_anatomical_mapping_human_brain.jpg").is_file()
        and (previews / "03_exploded_lobe_atlas.png").is_file()
    )
    ok = (
        len(plate_imgs) >= 25
        and poster_ok
        and len(mri_sheets) == 3
        and len(cad_meshes) == 15
        and blender_ok
        and tours_ok
    )
    return ok, {
        "plates_count": len(plate_imgs),
        "poster_exists": poster_ok,
        "mri_sheets_count": len(mri_sheets),
        "cad_meshes_count": len(cad_meshes),
        "blender_importer_exists": blender_ok,
        "tour_media_verified": tours_ok,
    }


def _check_desktop_self_test() -> tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, str(DESK / "zoe_desktop.py"), "--self-test"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    detail = (proc.stdout.strip() or proc.stderr.strip()).splitlines()[-1] if (proc.stdout or proc.stderr) else ""
    return proc.returncode == 0 and "PASS" in proc.stdout, detail


def _check_cross_platform_sources() -> tuple[bool, dict]:
    items = {
        "desktop_builder": (DESK / "build_desktop_packages.py").is_file(),
        "desktop_macos_swift": (DESK / "macos" / "ZoeMacApp.swift").is_file(),
        "android_project": (ROOT / "mobile" / "android" / "app" / "build.gradle").is_file(),
        "apple_xcode_project": (ROOT / "mobile" / "apple" / "Zoe.xcodeproj" / "project.pbxproj").is_file(),
        "windows_native_cpp": (ROOT / "mobile" / "windows" / "native" / "tests.cpp").is_file(),
        "safeconvert_doc": (ROOT / "mobile" / "SAFECONVERT.md").is_file(),
    }
    return all(items.values()), items


def _check_orbit_seal() -> tuple[bool, dict]:
    sums_path = ROOT / "evidence" / "renaissance-orbit" / "SHA256SUMS.orbit"
    lines = [
        ln.strip() for ln in sums_path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    matched = 0
    mismatched = []
    for line in lines:
        expected_hex, rel_path = line.split(None, 1)
        fp = ROOT / rel_path
        if fp.is_file() and _sha256_file(fp) == expected_hex:
            matched += 1
        else:
            mismatched.append(rel_path)
    return matched == len(lines) and len(lines) >= 47, {
        "verified": matched,
        "total": len(lines),
        "mismatched": mismatched,
    }


def _check_docs_and_evidence_integrity() -> tuple[bool, dict]:
    doc_files = (
        [ROOT / "README.md"]
        + sorted((ROOT / "docs").glob("*.md"))
        + sorted((ROOT / "guiai-lab" / "docs").glob("*.md"))
        + sorted((ROOT / "mobile").glob("*.md"))
        + sorted((ROOT / "desktop").glob("*.md"))
        + sorted((ROOT / "dorothy-brain-observatory").glob("*.md"))
        + sorted((ROOT / "components" / "Zoe-Autonomy").glob("*.md"))
    )
    broken_links = []
    checked_links = 0
    for md_path in doc_files:
        text = md_path.read_text(encoding="utf-8")
        for m in LINK_RE.finditer(text):
            raw = (m.group(1) or m.group(2) or "").strip()
            if not raw or raw.startswith(("#", "http://", "https://", "mailto:", "file://")):
                continue
            target_part = raw.split("#", 1)[0].split("?", 1)[0]
            if not target_part:
                continue
            checked_links += 1
            resolved = (md_path.parent / target_part).resolve()
            if not resolved.exists():
                broken_links.append(f"{md_path.relative_to(ROOT)} -> {raw}")

    json_files = sorted((ROOT / "evidence").rglob("*.json"))
    invalid_jsons = []
    for jf in json_files:
        if jf == REPORT_PATH:
            continue
        try:
            json.loads(jf.read_text(encoding="utf-8"))
        except Exception as exc:
            invalid_jsons.append(f"{jf.relative_to(ROOT)}: {exc}")

    ok = len(broken_links) == 0 and len(invalid_jsons) == 0 and len(doc_files) >= 10
    return ok, {
        "markdown_docs_checked": len(doc_files),
        "local_links_checked": checked_links,
        "broken_links_count": len(broken_links),
        "broken_links_sample": broken_links[:10],
        "evidence_json_files_valid": len(json_files) - len(invalid_jsons),
        "invalid_json_files": invalid_jsons[:10],
    }


def run_checks() -> int:
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {name} ({detail})")

    core_ok, core_data = _check_observatory_core()
    record("01_dorothy_human_brain_core_assets", core_ok, f"{len(CORE_OBS_FILES)} core assets")

    media_ok, media_data = _check_plates_cad_and_media()
    record(
        "02_plates_mri_cad_and_tours",
        media_ok,
        f"plates={media_data['plates_count']} mri={media_data['mri_sheets_count']} cad={media_data['cad_meshes_count']}",
    )

    desk_ok, desk_detail = _check_desktop_self_test()
    record("03_desktop_loopback_and_http206_stream", desk_ok, "loopback_200_and_206_verified" if desk_ok else desk_detail)

    plat_ok, plat_data = _check_cross_platform_sources()
    record("04_cross_platform_packaging_manifests", plat_ok, f"{sum(plat_data.values())}/{len(plat_data)} present")

    orbit_ok, orbit_data = _check_orbit_seal()
    record("05_sha256sums_orbit_seal", orbit_ok, f"{orbit_data['verified']}/{orbit_data['total']} OK")

    docs_ok, docs_data = _check_docs_and_evidence_integrity()
    record(
        "06_docs_links_and_evidence_json_integrity",
        docs_ok,
        f"docs={docs_data['markdown_docs_checked']} links={docs_data['local_links_checked']} broken={docs_data['broken_links_count']} jsons={docs_data['evidence_json_files_valid']}",
    )

    passed = sum(1 for c in checks if c["passed"])
    report = {
        "contract": "zoe-observatory-and-packages-evidence/v1",
        "verifier": "scripts/verify_observatory_and_packages.py",
        "passed": passed,
        "total": len(checks),
        "all_pass": passed == len(checks),
        "constitutional_flags": {
            "clinical_action_authorized": False,
            "cure_claim": False,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "zoe_clone_claimed": False,
            "external_actions": 0,
        },
        "observatory_core": core_data,
        "plates_and_cad": media_data,
        "cross_platform_sources": plat_data,
        "orbit_seal": orbit_data,
        "documentation_and_evidence_audit": docs_data,
        "checks": checks,
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    sealed = dict(report)
    sealed["evidence_sha256"] = digest
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(sealed, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"\nDOROTHY OBSERVATORY & PACKAGES VERIFIER: {passed}/{len(checks)} PASS | SHA-256={digest[:16]}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(run_checks())
