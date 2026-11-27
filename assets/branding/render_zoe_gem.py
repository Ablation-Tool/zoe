from __future__ import annotations

import base64
from pathlib import Path
import shutil

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "assets" / "branding" / "zoe-gem.png"
VECTOR = ROOT / "assets" / "branding" / "zoe-gem.svg"
GEM = ROOT / "components" / "ablation"
GEM_ROOT = GEM / "assets" / "branding" / "woven-diamond"
PACKAGED = GEM / "gem-lab" / "gem" / "icons"


def square(size):
    with Image.open(SOURCE) as source:
        source = source.convert("RGBA")
        height = round(size * source.height / source.width)
        resized = source.resize((size, height), Image.Resampling.LANCZOS)
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        image.paste(resized, (0, (size - height) // 2))
        return image


def render(size, path):
    square(size).save(path, format="PNG", optimize=True)


def write_vector_editions():
    encoded = base64.b64encode(SOURCE.read_bytes()).decode("ascii")
    with Image.open(SOURCE) as source:
        width, height = source.size
    document = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">\n'
        '  <title id="title">Zoe GEM official emblem</title>\n'
        '  <desc id="description">Zoe’s exact official PNG artwork preserved in an SVG container.</desc>\n'
        f'  <image id="gem3red" width="47" height="29" xlink:href="data:image/png;base64,{encoded}"/>\n'
        '</svg>\n'
    )
    for path in (
        VECTOR,
        GEM_ROOT / "source" / "gem-woven-diamond.svg",
        GEM_ROOT / "linux" / "hicolor" / "scalable" / "apps" / "gem-woven-diamond.svg",
        GEM_ROOT / "web" / "favicon.svg",
        PACKAGED / "gem-woven-diamond.svg",
    ):
        path.write_text(document, encoding="utf-8")


def main():
    write_vector_editions()
    render(512, ROOT / "mobile" / "android" / "app" / "src" / "main" / "res" / "drawable" / "zoe_eye.png")
    apple = ROOT / "mobile" / "apple" / "Zoe" / "Assets.xcassets" / "AppIcon.appiconset"
    for path in apple.glob("zoe-icon-*.png"):
        render(int(path.stem.removeprefix("zoe-icon-")), path)

    for path in (GEM_ROOT / "png").glob("gem-woven-diamond-*.png"):
        render(int(path.stem.removeprefix("gem-woven-diamond-").split("x")[0]), path)
    for path in (GEM_ROOT / "linux" / "hicolor").glob("*x*/apps/gem-woven-diamond.png"):
        render(int(path.parent.parent.name.split("x")[0]), path)
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

    image = square(1024)
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
