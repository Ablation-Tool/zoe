from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .cern_corpus import (
    DEFAULT_CERN_ROOT,
    load_corpus,
    scan_corpus,
    write_corpus,
)
from .cern_repair import (
    default_repair_report,
    repair_scene,
    write_repair_report,
)
from .render import write_png, write_svg
from .vdi import write_metafile


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="gem cern", description="CERN corpus inventory, FORGE evidence, and Repair Atlas")
    result.add_argument("operation", choices=("scan", "forge", "report", "chart", "verify"))
    result.add_argument("--cern-root", default=str(DEFAULT_CERN_ROOT))
    result.add_argument("--input", help="existing corpus directory or Repair Atlas JSON")
    result.add_argument("--output", required=True)
    result.add_argument("--workers", type=int, default=1)
    result.add_argument("--format", choices=("json", "svg", "png", "gem"))
    return result


def _forge(root: Path, output: Path) -> dict:
    from ablation.analyzers.forge import FORGE

    report = FORGE.audit_source(str(root))
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError(f"FORGE output directory must be new or empty: {output}")
    (output / "forge-source-audit.txt").write_text(report.report() + "\n" + report.raw_text, encoding="utf-8")
    findings = [{
        "severity": finding.severity,
        "category": finding.category,
        "title": finding.title,
        "location": finding.location,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "source": finding.source,
        "cwe": finding.cwe,
        "detection_stage": finding.detection_stage,
    } for finding in report.findings]
    value = {
        "path": report.path,
        "mode": report.mode,
        "summary": report.summary,
        "gate_passed": report.gate_passed,
        "findings": findings,
    }
    (output / "forge-source-audit.json").write_text(
        json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "operation": "forge",
        "output": str(output),
        "finding_count": len(findings),
        "high_or_critical": len(report.highs()),
        "gate_passed": report.gate_passed,
        "summary": report.summary,
    }


def _verify(source: Path, output: Path, workers: int) -> dict:
    records, summary = load_corpus(source)
    root = Path(summary["root"])
    current, current_summary = scan_corpus(root, output=source, workers=workers)
    before = {record.path: record.to_dict() for record in records}
    after = {record.path: record.to_dict() for record in current}
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    changed = []
    ignored_metadata = {"mtime_ns", "mode", "device", "inode"}
    for path in sorted(before.keys() & after.keys()):
        left = {key: value for key, value in before[path].items() if key not in ignored_metadata}
        right = {key: value for key, value in after[path].items() if key not in ignored_metadata}
        if left != right:
            changed.append(path)
    result = {
        "schema_version": 1,
        "instrument": "zoe-cern-corpus-verification",
        "source": str(source),
        "root": str(root),
        "passed": not added and not removed and not changed and current_summary["coverage"]["complete_without_errors"],
        "added": added,
        "removed": removed,
        "changed": changed,
        "coverage": current_summary["coverage"],
        "manifest_sha256": summary["manifest_sha256"],
        "fresh_record_count": len(current),
        "execution": "read-only rehash and comparison; no source artifact modified",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return result


def run(arguments: argparse.Namespace) -> int:
    root = Path(arguments.cern_root).expanduser().resolve()
    output = Path(arguments.output).expanduser().resolve()
    operation = arguments.operation
    if operation in {"report", "chart", "verify"} and output.exists():
        raise FileExistsError(f"output already exists: {output}")
    if operation == "scan":
        def progress(done: int, total: int, path: str) -> None:
            if done % 500 == 0 or done == total:
                print(json.dumps({"hashed": done, "total": total, "last": path}), flush=True)
        records, summary = scan_corpus(root, output=output, workers=arguments.workers, progress=progress)
        write_corpus(records, summary, output)
        result = {
            "operation": "scan",
            "output": str(output),
            "file_count": summary["file_count"],
            "logical_bytes": summary["logical_bytes"],
            "unique_content_count": summary["unique_content_count"],
            "coverage": summary["coverage"],
            "duplicates": summary["duplicates"],
        }
    elif operation == "forge":
        result = _forge(root, output)
    elif operation == "report":
        write_repair_report(default_repair_report(root), output)
        result = {"operation": "report", "output": str(output), "bytes": output.stat().st_size}
    elif operation == "chart":
        if arguments.input:
            report = json.loads(Path(arguments.input).read_text(encoding="utf-8"))
            if report.get("instrument") != "zoe-cern-repair-atlas":
                raise ValueError("input is not a Repair Atlas JSON report")
        else:
            report = default_repair_report(root)
        scene, report = repair_scene(report)
        kind = arguments.format or output.suffix.lower().lstrip(".")
        if kind == "json":
            write_repair_report(report, output)
        elif kind == "svg":
            write_svg(scene, output, 1600)
        elif kind == "png":
            write_png(scene, output, 1600)
        elif kind == "gem":
            write_metafile(scene, output)
        else:
            raise ValueError("chart output format must be json, svg, png, or gem")
        result = {"operation": "chart", "output": str(output), "bytes": output.stat().st_size, "repair_count": report["repair_count"]}
    elif operation == "verify":
        if not arguments.input:
            raise ValueError("verify requires --input CORPUS_DIRECTORY")
        result = _verify(Path(arguments.input), output, arguments.workers)
    else:
        raise ValueError(f"unknown CERN operation: {operation}")
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True))
    if operation == "forge" and not result["gate_passed"]:
        return 1
    if operation == "verify" and not result["passed"]:
        return 1
    return 0


def main(argv=None) -> int:
    arguments = parser().parse_args(argv)
    try:
        return run(arguments)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"gem cern: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
