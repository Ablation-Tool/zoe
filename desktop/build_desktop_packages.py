#!/usr/bin/env python3
"""Build portable Zoe Desktop release packages for Linux, Windows, and Apple macOS.

Packages ONLY public Dorothy 3D Brain Observatory assets (zero private/copyrighted
books, zero local user paths) into reproducible archives with SHA-256 checksums:
  - zoe-desktop-v0.9.6-linux.tar.gz
  - zoe-desktop-v0.9.6-windows-x64.zip
  - zoe-desktop-v0.9.6-macos.zip
"""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import tarfile
import tempfile
import zipfile
from pathlib import Path

VERSION = "v0.9.6"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(131072), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_public_observatory(root: Path, dest_obs: Path) -> None:
    """Copy the verified public mobile/desktop Dorothy 3D Brain Observatory bundle."""
    src_obs = root / "mobile" / "android" / "app" / "src" / "main" / "assets" / "dorothy_brain_observatory"
    if not (src_obs / "index.html").is_file():
        raise FileNotFoundError(f"Missing public observatory bundle at {src_obs}")
    shutil.copytree(src_obs, dest_obs)
    # Use the latest desktop/web zoe_neuro_qa.js (includes ?tab=/?q= and <- Home navigation)
    shutil.copy2(
        root / "dorothy-brain-observatory" / "assets" / "zoe_neuro_qa.js",
        dest_obs / "assets" / "zoe_neuro_qa.js",
    )


def add_dir_to_zip(zf: zipfile.ZipFile, src_dir: Path, prefix: str) -> None:
    for item in sorted(src_dir.rglob("*")):
        rel = item.relative_to(src_dir).as_posix()
        arc = f"{prefix}/{rel}"
        if item.is_dir():
            continue
        zi = zipfile.ZipInfo(arc)
        zi.compress_type = zipfile.ZIP_DEFLATED
        mode = item.stat().st_mode
        zi.external_attr = (mode & 0xFFFF) << 16
        with item.open("rb") as fh:
            zf.writestr(zi, fh.read())


def build_linux_package(root: Path, staging: Path, out_dir: Path) -> Path:
    pkg = staging / "ZoeDesktop-Linux"
    pkg.mkdir(parents=True)
    copy_public_observatory(root, pkg / "dorothy_brain_observatory")
    shutil.copy2(root / "desktop" / "zoe_desktop.py", pkg / "zoe_desktop.py")
    shutil.copy2(root / "desktop" / "desktop_home.html", pkg / "desktop_home.html")
    shutil.copy2(root / "desktop" / "README.md", pkg / "README.md")
    shutil.copy2(root / "assets" / "branding" / "zoe-gem.png", pkg / "icon.png")
    shutil.copy2(root / "desktop" / "linux" / "zoe-desktop", pkg / "zoe-desktop")
    shutil.copy2(root / "desktop" / "linux" / "install-desktop-shortcut.sh", pkg / "install-desktop-shortcut.sh")
    for script in (pkg / "zoe-desktop", pkg / "install-desktop-shortcut.sh", pkg / "zoe_desktop.py"):
        script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    archive = out_dir / f"zoe-desktop-{VERSION}-linux.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(pkg, arcname="ZoeDesktop")
    return archive


def build_windows_package(root: Path, staging: Path, out_dir: Path) -> Path:
    pkg = staging / "ZoeDesktop-Windows"
    pkg.mkdir(parents=True)
    copy_public_observatory(root, pkg / "dorothy_brain_observatory")
    shutil.copy2(root / "desktop" / "desktop_home.html", pkg / "desktop_home.html")
    shutil.copy2(root / "desktop" / "zoe_desktop.py", pkg / "zoe_desktop.py")
    shutil.copy2(root / "desktop" / "README.md", pkg / "README.md")
    shutil.copy2(root / "assets" / "branding" / "zoe-gem.png", pkg / "icon.png")
    shutil.copy2(root / "desktop" / "windows" / "Launch Zoe.bat", pkg / "Launch Zoe.bat")
    shutil.copy2(root / "desktop" / "windows" / "ZoeDesktop.ps1", pkg / "ZoeDesktop.ps1")

    win_trinity = root / "mobile" / "dist" / "windows" / "ZoeTrinity.exe"
    if win_trinity.is_file():
        shutil.copy2(win_trinity, pkg / "ZoeTrinity.exe")

    archive = out_dir / f"zoe-desktop-{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        add_dir_to_zip(zf, pkg, "ZoeDesktop")
    return archive


def build_macos_package(root: Path, staging: Path, out_dir: Path) -> Path:
    pkg = staging / "ZoeDesktop-macOS"
    app = pkg / "Zoe.app"
    macos_dir = app / "Contents" / "MacOS"
    res_desk = app / "Contents" / "Resources" / "desktop"
    res_obs = app / "Contents" / "Resources" / "dorothy_brain_observatory"
    macos_dir.mkdir(parents=True)
    res_desk.mkdir(parents=True)

    shutil.copy2(root / "desktop" / "macos" / "Info.plist", app / "Contents" / "Info.plist")
    launcher = macos_dir / "Zoe"
    shutil.copy2(root / "desktop" / "macos" / "launch_macos.sh", launcher)
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    shutil.copy2(root / "desktop" / "zoe_desktop.py", res_desk / "zoe_desktop.py")
    shutil.copy2(root / "desktop" / "desktop_home.html", res_desk / "desktop_home.html")
    shutil.copy2(root / "assets" / "branding" / "zoe-gem.png", res_desk / "icon.png")
    shutil.copy2(root / "desktop" / "macos" / "ZoeMacApp.swift", pkg / "ZoeMacApp.swift")
    shutil.copy2(root / "desktop" / "README.md", pkg / "README.md")
    copy_public_observatory(root, res_obs)

    archive = out_dir / f"zoe-desktop-{VERSION}-macos.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        add_dir_to_zip(zf, pkg, "ZoeDesktop-macOS")
    return archive


def main() -> int:
    root = repo_root()
    out_dir = Path(os.environ.get("ZOE_DESKTOP_OUT", "/tmp/zoe-desktop-dist"))
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="zoe-desk-stage-") as tmp:
        staging = Path(tmp)
        artifacts = [
            build_linux_package(root, staging, out_dir),
            build_windows_package(root, staging, out_dir),
            build_macos_package(root, staging, out_dir),
        ]

    sums_path = out_dir / f"zoe-desktop-{VERSION}-SHA256SUMS.txt"
    lines = []
    for art in artifacts:
        digest = sha256_file(art)
        mb = art.stat().st_size / (1024 * 1024)
        lines.append(f"{digest}  {art.name}")
        print(f"Built {art.name} ({mb:.2f} MB) SHA-256={digest}")
    sums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote checksums: {sums_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
