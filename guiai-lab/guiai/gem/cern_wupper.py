from __future__ import annotations

import ast
import difflib
import hashlib
import json
from pathlib import Path
import tempfile

import yaml


LEGACY_BLOCK = """            try:
                config = yaml.load(f, Loader=yaml.FullLoader)
            except AttributeError:
                # Python 2.7
                config = yaml.load(f)
"""
SAFE_BLOCK = """            config = yaml.safe_load(f)
"""


def repair_wupper_cli(source: str) -> str:
    if source.count(LEGACY_BLOCK) != 1:
        raise ValueError("expected exactly one legacy Wupper YAML loading block")
    repaired = source.replace(LEGACY_BLOCK, SAFE_BLOCK)
    ast.parse(repaired)
    return repaired


def repair_wupper_file(source: str | Path, output: str | Path) -> dict:
    source = Path(source).expanduser().resolve()
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Wupper repair output already exists: {output}")
    original_bytes = source.read_bytes()
    original = original_bytes.decode("utf-8")
    repaired = repair_wupper_cli(original)
    diff = "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        repaired.splitlines(keepends=True),
        fromfile="a/wuppercodegen/cli.py",
        tofile="b/wuppercodegen/cli.py",
    ))
    report = {
        "schema_version": 1,
        "instrument": "zoe-wupper-safe-yaml-repair",
        "source": str(source),
        "source_sha256": hashlib.sha256(original_bytes).hexdigest(),
        "repaired": str(output),
        "repaired_sha256": hashlib.sha256(repaired.encode("utf-8")).hexdigest(),
        "patch": diff,
        "original_artifacts_modified": False,
        "checks": [],
    }

    def check(name: str, condition: bool) -> None:
        report["checks"].append({"name": name, "passed": bool(condition)})
        if not condition:
            raise RuntimeError(f"Wupper repair check failed: {name}")

    check("legacy YAML loader removed", "yaml.load" not in repaired)
    check("safe loader present exactly once", repaired.count("yaml.safe_load") == 1)
    check("repaired source parses", bool(ast.parse(repaired)))
    with tempfile.TemporaryDirectory(prefix="zoe-wupper-") as temporary:
        work = Path(temporary)
        valid = work / "valid.yaml"
        valid.write_text("Registers:\n  - name: SAFE\n", encoding="utf-8")
        check("valid YAML still loads", yaml.safe_load(valid.read_text(encoding="utf-8")) == {"Registers": [{"name": "SAFE"}]})
        malicious = work / "malicious.yaml"
        marker = work / "executed"
        malicious.write_text(
            f'!!python/object/apply:pathlib.Path.touch ["{marker}"]\n',
            encoding="utf-8",
        )
        try:
            yaml.safe_load(malicious.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            rejected = True
        else:
            rejected = False
        check("Python-object YAML is rejected", rejected)
        check("rejected YAML had no side effect", not marker.exists())
    report["status"] = "regression_verified"
    report["tests_total"] = len(report["checks"])
    report["tests_passed"] = sum(row["passed"] for row in report["checks"])
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(repaired)
    return report


def write_wupper_report(report: dict, output: str | Path) -> Path:
    output = Path(output).expanduser().resolve()
    if output.suffix.lower() != ".json":
        raise ValueError("Wupper repair evidence must use .json")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    patch_path = output.with_suffix(".patch")
    with patch_path.open("x", encoding="utf-8") as stream:
        stream.write(report["patch"])
    return output
