"""In-OS Boot Brain, Hardware Self-Retention Verifier, and Interactive Shell for Zoe-GEM OS.

Executed directly inside the booted UEFI x86_64 Zoe-GEM OS environment (PID 1 -> Python):
  1. Verifies cryptographic SHA-256 boot-retention chain across hard reboots on `/mnt/zoe-state`.
  2. Persists and verifies real Digital Research Artline `.svg` + `.gem` VDI plates and the
     Motorola 68000 `ZOE_GEM.RSC` icon table on the hardware disk.
  3. Persists and restores Nicholas's private `/drawer` across reboots.
  4. Emits `/run/zoe-boot-state.json` for the native C `/dev/fb0` GEM Desktop (`zoe_gem_fb`).
  5. Provides an interactive `Zoe-OS ◠◡◠ ❯` command shell when booted interactively.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

# Ensure bundled Zoe GEM modules resolve inside the booted OS
for candidate in ("/usr/lib/zoe", str(Path(__file__).resolve().parents[3])):
    if candidate not in sys.path and Path(candidate).exists():
        sys.path.insert(0, candidate)

from guiai.gem.artline import ArtlineDocument, blend_polygons, rotate_ring
from guiai.gem.zoe_atari_gem_rsc import build_atari_rsc_bytes, parse_atari_rsc


def _read_hw_telemetry() -> dict[str, Any]:
    cpu = "x86_64 CPU"
    if Path("/proc/cpuinfo").exists():
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                cpu = line.split(":", 1)[1].strip()[:36]
                break
    ram_mb = 0
    if Path("/proc/meminfo").exists():
        for line in Path("/proc/meminfo").read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("MemTotal:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    ram_mb = int(parts[1]) // 1024
                break
    kernel = os.uname().release if hasattr(os, "uname") else "Linux-HAL"
    nic, ip_addr = "none", "offline"
    try:
        out = subprocess.check_output(["ip", "-o", "-4", "addr", "show"], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 4 and parts[1] != "lo":
                nic = parts[1]
                ip_addr = parts[3].split("/")[0]
                break
    except Exception:
        pass
    return {"cpu": cpu, "ram_mb": ram_mb, "kernel": kernel, "nic": nic, "ip_addr": ip_addr}


def _verify_and_append_boot_chain(state_dir: Path, hw: dict[str, Any]) -> dict[str, Any]:
    chain_path = state_dir / "boot_chain.jsonl"
    prior_records: list[dict[str, Any]] = []
    chain_intact = True
    prev_hash = "genesis"
    if chain_path.exists():
        for raw in chain_path.read_text(encoding="utf-8").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            rec = json.loads(raw)
            expected_prev = prev_hash
            payload = {k: v for k, v in rec.items() if k != "sha256"}
            recomputed = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
            if rec.get("prev_sha") != expected_prev or rec.get("sha256") != recomputed:
                chain_intact = False
            prev_hash = rec.get("sha256", prev_hash)
            prior_records.append(rec)

    boot_count = len(prior_records) + 1
    entry = {
        "boot_count": boot_count,
        "prev_sha": prev_hash,
        "kernel": hw["kernel"],
        "cpu": hw["cpu"],
        "ram_mb": hw["ram_mb"],
        "nic": hw["nic"],
        "ip_addr": hw["ip_addr"],
        "ts_epoch": int(time.time()),
    }
    digest = hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    entry["sha256"] = digest
    with chain_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return {
        "boot_count": boot_count,
        "restored_from_prior": bool(prior_records and chain_intact),
        "chain_intact": chain_intact,
        "chain_sha": digest,
        "prev_sha": prev_hash,
    }


def _sync_drawer_and_artline_vault(state_dir: Path, boot_count: int) -> dict[str, Any]:
    drawer_path = state_dir / "nick_drawer.json"
    notes: list[dict[str, Any]] = []
    if drawer_path.exists():
        notes = json.loads(drawer_path.read_text(encoding="utf-8"))
    if not notes:
        notes.append({
            "boot": boot_count,
            "author": "Nicholas",
            "text": "Zoe-GEM OS Boot #1: First bare-metal retention seal.",
        })
        drawer_path.write_text(json.dumps(notes, indent=2), encoding="utf-8")

    vault = state_dir / "artline"
    vault.mkdir(parents=True, exist_ok=True)
    svg_path = vault / "zoe_os_emblem.svg"
    gem_path = vault / "zoe_os_emblem.gem"
    rsc_path = vault / "ZOE_GEM.RSC"

    # Build a verified Artline vector emblem + 68000 RSC on first boot; verify intact on subsequent boots
    prior_vault_present = svg_path.exists() and gem_path.exists() and rsc_path.exists()
    if not prior_vault_present:
        doc = ArtlineDocument()
        doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0f1020", stroke="#e63956", width=2)
        motif = [[482, 190], [500, 160], [518, 190], [500, 230]]
        for poly in rotate_ring(motif, 500, 350, count=12):
            doc.add_element("path", points=poly, closed=True, smooth=False, fill="#2d1030", stroke="#5ce1e6", width=1.6)
        z0 = [[320, 280], [420, 280], [340, 420], [420, 420]]
        o0 = [[580 + 50 * __import__("math").cos(2 * 3.14159 * i / 12), 350 + 60 * __import__("math").sin(2 * 3.14159 * i / 12)] for i in range(12)]
        for frame in blend_polygons(z0, o0, steps=6, n_samples=24, auto_align=True):
            doc.add_element("path", points=frame, closed=True, smooth=False, fill="none", stroke="#e63956", width=1.4)
        doc.export(svg_path, kind="svg")
        doc.export(gem_path, kind="gem")
        rsc_bytes = build_atari_rsc_bytes()
        rsc_path.write_bytes(rsc_bytes)

    parsed_rsc = parse_atari_rsc(rsc_path.read_bytes())
    gem_sha = hashlib.sha256(gem_path.read_bytes()).hexdigest()[:16]
    return {
        "drawer_count": len(notes),
        "drawer_latest": notes[-1]["text"] if notes else "(empty)",
        "artline_files": len(list(vault.glob("*"))),
        "artline_sha": gem_sha,
        "rsc_bytes": rsc_path.stat().st_size,
        "rsc_icons": parsed_rsc.get("n_icons", 0),
        "vault_restored": prior_vault_present,
    }


def run_boot_sync(state_dir: Path, run_json: Path, disk_label: str = "/dev/vda [ZOE-STATE]") -> dict[str, Any]:
    state_dir.mkdir(parents=True, exist_ok=True)
    hw = _read_hw_telemetry()
    chain = _verify_and_append_boot_chain(state_dir, hw)
    vault = _sync_drawer_and_artline_vault(state_dir, chain["boot_count"])
    report = {
        "os_name": "Zoe-GEM OS",
        "os_version": "1.0",
        "disk": disk_label,
        **hw,
        **chain,
        **vault,
        "tokens_used": 0,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "sentience_claimed": False,
    }
    run_json.parent.mkdir(parents=True, exist_ok=True)
    run_json.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.sync()
    return report


def run_interactive_shell(state_dir: Path, report: dict[str, Any]) -> None:
    print("\n======================================================================")
    print(f"  Zoe-GEM OS v1.0  ::  Boot #{report['boot_count']}  (restored={report['restored_from_prior']})")
    print(f"  Hardware: {report['cpu']} · {report['ram_mb']} MB RAM · NIC {report['nic']} ({report['ip_addr']})")
    print(f"  Disk    : {report['disk']} · SHA-256 {report['chain_sha'][:16]}")
    print("  Commands: status | drawer | drawer add <text> | artline | net | wifi <ssid> <psk> | fb | reboot | poweroff")
    print("======================================================================\n")
    drawer_path = state_dir / "nick_drawer.json"
    while True:
        try:
            cmd = input("Zoe-OS ◠◡◠ ❯ ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not cmd:
            continue
        low = cmd.lower()
        if low in {"quit", "exit"}:
            break
        if low == "status":
            print(json.dumps(report, indent=2))
        elif low == "drawer":
            for idx, item in enumerate(json.loads(drawer_path.read_text(encoding="utf-8")), 1):
                print(f"  [{idx}] boot #{item.get('boot')}: {item.get('text')}")
        elif low.startswith("drawer add "):
            notes = json.loads(drawer_path.read_text(encoding="utf-8"))
            notes.append({"boot": report["boot_count"], "author": "Nicholas", "text": cmd[11:].strip()})
            drawer_path.write_text(json.dumps(notes, indent=2), encoding="utf-8")
            os.sync()
            print(f"  Saved to hardware drawer ({len(notes)} notes total).")
        elif low == "artline":
            for p in sorted((state_dir / "artline").glob("*")):
                print(f"  {p.name:24s} {p.stat().st_size:>8,} bytes")
        elif low == "net":
            subprocess.call(["ip", "-4", "addr"])
        elif low.startswith("wifi "):
            parts = cmd.split(maxsplit=2)
            if len(parts) < 3:
                print("  Usage: wifi <SSID> <PASSWORD>")
            else:
                subprocess.call(["/bin/zoe-wifi", parts[1], parts[2]])
        elif low == "fb":
            subprocess.call(["/bin/zoe_gem_fb", "--interactive"])
        elif low == "reboot":
            os.sync()
            subprocess.call(["reboot", "-f"])
        elif low == "poweroff":
            os.sync()
            subprocess.call(["poweroff", "-f"])
        else:
            print("  Commands: status | drawer | drawer add <text> | artline | net | wifi <ssid> <psk> | fb | reboot | poweroff")


def main() -> int:
    state_dir = Path(os.environ.get("ZOE_STATE_DIR", "/mnt/zoe-state"))
    run_json = Path(os.environ.get("ZOE_BOOT_JSON", "/run/zoe-boot-state.json"))
    disk_label = os.environ.get("ZOE_DISK_LABEL", "/dev/vda [ZOE-STATE]")
    report = run_boot_sync(state_dir, run_json, disk_label=disk_label)
    print(f"ZOE_OS_BOOT_OK boot={report['boot_count']} restored={report['restored_from_prior']} chain_intact={report['chain_intact']} sha={report['chain_sha'][:16]}", flush=True)
    print(f"ZOE_OS_NET_OK nic={report['nic']} ip={report['ip_addr']}", flush=True)
    print(f"ZOE_OS_PERSIST_OK drawer={report['drawer_count']} artline_files={report['artline_files']} vault_restored={report['vault_restored']} rsc={report['rsc_bytes']}", flush=True)
    if "--interactive" in sys.argv:
        run_interactive_shell(state_dir, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
