import json
import os
from pathlib import Path
import subprocess
import sys
import sysconfig


ROOT = Path(__file__).resolve().parents[1]
ZOE_ROOT = ROOT.parent.parent


def test_ablation_is_bundled_in_the_unified_zoe_repository():
    sys.path.insert(0, str(ZOE_ROOT / "guiai-lab"))
    from guiai.gem.unified import ComponentRegistry

    registry = ComponentRegistry(ZOE_ROOT)
    for identifier in ("ablation", "gem-lab"):
        source = registry.source(identifier)
        assert source["mode"] == "bundled"
        assert source["path"] == ROOT
        assert source["available"] is True
    manifest = registry.manifest()
    assert manifest["identity"] == "Zoe is allgems"
    assert manifest["repository_count"] == 1
    assert manifest["source_project_count"] == 13
    assert len(manifest["components"]) == 17
    assert all(row["source"]["source_present"] for row in manifest["components"])


def test_zoe_cli_uses_unified_sources():
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ZOE_ROOT / "guiai-lab")
    environment["ZOE_ROOT"] = str(ZOE_ROOT)
    environment["ZOE_PYTHON"] = sys.executable
    environment["ZOE_PYTHON_DEPENDENCIES"] = sysconfig.get_paths()["purelib"]
    result = subprocess.run(
        [sys.executable, "-m", "guiai.gem.unified_cli", "list"],
        cwd=ROOT, env=environment, check=True, capture_output=True, text=True,
    )
    rows = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(rows) == 17
    assert all("present" in line for line in rows)
    launch = subprocess.run(
        [sys.executable, "-m", "guiai.gem.unified_cli", "launch", "ablation", "--", "--help"],
        cwd=ROOT, env=environment, capture_output=True, text=True,
    )
    assert launch.returncode == 0, launch.stdout + launch.stderr
    assert "usage:" in launch.stdout
    lock = json.loads((ZOE_ROOT / "config" / "components.lock.json").read_text(encoding="utf-8"))
    assert lock["repository_count"] == 1
    assert lock["components"]["ablation"]["path"] == "components/ablation"
    assert lock["components"]["ablation"]["revision"] == "fa8377ea5fa009967a3bf3b837c342347678409b"
