from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets" / "branding" / "zoe-gem.svg"
MASTER = ROOT / "assets" / "branding" / "zoe-gem.png"
GEM = ROOT / "components" / "ablation"
GEM_ROOT = GEM / "assets" / "branding" / "woven-diamond"
PACKAGED = GEM / "gem-lab" / "gem" / "icons"


def render(size, path):
    with Image.open(MASTER) as image:
        image = image.convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
        image.save(path, format="PNG", optimize=True)


def main():
    with tempfile.TemporaryDirectory(prefix="zoe-gem-render-") as directory:
        rendered = Path(directory) / "zoe-gem.png"
        subprocess.run([
            "rsvg-convert", str(SOURCE), "--keep-aspect-ratio",
            "--width", "940", "--height", "580",
            "--page-width", "1024", "--page-height", "1024",
            "--left", "42", "--top", "222",
            "--format", "png", "--output", str(rendered),
        ], check=True)
        shutil.copyfile(rendered, MASTER)

    render(512, ROOT / "mobile" / "android" / "app" / "src" / "main" / "res" / "drawable" / "zoe_eye.png")
    apple = ROOT / "mobile" / "apple" / "Zoe" / "Assets.xcassets" / "AppIcon.appiconset"
    for path in apple.glob("zoe-icon-*.png"):
        render(int(path.stem.removeprefix("zoe-icon-")), path)

    for name in ("gem-woven-diamond.svg",):
        for path in (GEM_ROOT / "source" / name, GEM_ROOT / "linux" / "hicolor" / "scalable" / "apps" / name, PACKAGED / name):
            shutil.copyfile(SOURCE, path)
    for name in ("favicon.svg",):
        shutil.copyfile(SOURCE, GEM_ROOT / "web" / name)

    for path in (GEM_ROOT / "png").glob("gem-woven-diamond-*.png"):
        size = int(path.stem.removeprefix("gem-woven-diamond-").split("x")[0])
        render(size, path)
    for path in (GEM_ROOT / "linux" / "hicolor").glob("*x*/apps/gem-woven-diamond.png"):
        size = int(path.parent.parent.name.split("x")[0])
        render(size, path)
    for path in (GEM_ROOT / "macos" / "gem-woven-diamond.iconset").glob("icon_*.png"):
        size = int(path.stem.split("_")[1].split("x")[0])
        if path.stem.endswith("@2x"):
            size *= 2
        render(size, path)

    web_sizes = {
        "android-chrome-192x192.png": 192,
        "android-chrome-512x512.png": 512,
        "apple-touch-icon.png": 180,
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "maskable-icon-512.png": 512,
    }
    for name, size in web_sizes.items():
        render(size, GEM_ROOT / "web" / name)

    with Image.open(MASTER) as image:
        image = image.convert("RGBA")
        ico = GEM_ROOT / "windows" / "gem-woven-diamond.ico"
        image.save(ico, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
        image.save(GEM_ROOT / "macos" / "gem-woven-diamond.icns", format="ICNS")
        image.save(GEM_ROOT / "web" / "favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])

    render(512, PACKAGED / "gem-woven-diamond.png")
    render(32, PACKAGED / "gem-woven-diamond-32.png")
    shutil.copyfile(GEM_ROOT / "windows" / "gem-woven-diamond.ico", PACKAGED / "gem-woven-diamond.ico")
    shutil.copyfile(GEM_ROOT / "macos" / "gem-woven-diamond.icns", PACKAGED / "gem-woven-diamond.icns")
    print(f"Rendered Zoe's official GEM emblem from {SOURCE}")


if __name__ == "__main__":
    main()
