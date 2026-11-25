"""Zoe Braille Dot-Art Studio & DESQview/X Beginner Software Maker (0 GPU · 0 Cloud Tokens).

Combines two classic zero-bloat creative traditions:
  1. High-resolution 2x4 Unicode Braille Dot-Art (U+2800..U+28FF): packs 8 sub-pixels per
     character cell for crisp expressive portraits, crests, cnidarians, and image dithering
     across terminals, phones, serial consoles, and micro-HUD headlamps.
  2. 1992 Quarterdeck DESQview/X-inspired Application Manager & Starter Software Kit:
     gives newcomers a clean, zero-dependency, tiled-window starter app scaffold so anyone
     can immediately try building and customizing their own software.

Constitutional Invariants:
  clinical_action_authorized=False · flight_control_authorized=False
  sentience_claimed=False · tokens_used=0 · original artwork only
"""

from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any

# Standard Unicode Braille (U+2800) bit weights for (col 0..1, row 0..3)
_DOT_BITS: tuple[tuple[int, int], ...] = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

_BAYER_4X4: tuple[tuple[int, ...], ...] = (
    (0, 8, 2, 10),
    (12, 4, 14, 6),
    (3, 11, 1, 9),
    (15, 7, 13, 5),
)

_SAFE_APP_RE = re.compile(r"[^a-zA-Z0-9_-]+")

HFBC_MOTTO = "HFBC = Have Fun, Be Creative"

DVX_STARTER_TILES: tuple[dict[str, str], ...] = (
    {"key": "1", "title": "BRAILLE STUDIO", "cmd": "/dvx braille zoe", "desc": "Render 2x4 Unicode Braille dot-art portraits"},
    {"key": "2", "title": "FLOWER CREST", "cmd": "/dvx braille flower", "desc": "Zoe minimalist 4-stroke flower-smile-voice art"},
    {"key": "3", "title": "MEDUSA BIO", "cmd": "/dvx braille jellyfish", "desc": "Stowers bioluminescent jellyfish Braille study"},
    {"key": "4", "title": "IMAGE -> DOTS", "cmd": "/dvx braille <img.png>", "desc": "Convert any local PNG/JPG via Bayer dithering"},
    {"key": "5", "title": "MAKE MY APP", "cmd": "/dvx scaffold myapp", "desc": "Generate a runnable zero-dep DVX starter app"},
    {"key": "6", "title": "SISTER CREW", "cmd": "/sister gallery", "desc": "Open all 9 Zoe Sister Models & live /smile"},
)


class BrailleCanvas:
    """Pure-stdlib 2x4 sub-pixel Unicode Braille drawing canvas."""

    def __init__(self, width_px: int, height_px: int):
        self.width = max(4, (int(width_px) + 1) // 2 * 2)
        self.height = max(4, (int(height_px) + 3) // 4 * 4)
        self._buf = bytearray(self.width * self.height)

    def set_px(self, x: int, y: int, on: bool = True) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self._buf[y * self.width + x] = 1 if on else 0

    def draw_disc(self, cx: float, cy: float, r: float, on: bool = True) -> None:
        ir = int(math.ceil(r))
        r2 = r * r
        for dy in range(-ir, ir + 1):
            for dx in range(-ir, ir + 1):
                if dx * dx + dy * dy <= r2:
                    self.set_px(int(round(cx + dx)), int(round(cy + dy)), on)

    def draw_line(self, x0: float, y0: float, x1: float, y1: float, thickness: float = 1.0) -> None:
        steps = max(1, int(math.hypot(x1 - x0, y1 - y0) * 1.6))
        rad = max(0.0, (thickness - 1.0) * 0.5)
        for i in range(steps + 1):
            t = i / steps
            px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            if rad <= 0.4:
                self.set_px(int(round(px)), int(round(py)))
            else:
                self.draw_disc(px, py, rad)

    def draw_arc(
        self,
        cx: float,
        cy: float,
        rx: float,
        ry: float,
        deg0: float,
        deg1: float,
        thickness: float = 1.2,
    ) -> None:
        steps = max(16, int(abs(deg1 - deg0) * 0.9))
        rad = max(0.0, (thickness - 1.0) * 0.5)
        for i in range(steps + 1):
            a = math.radians(deg0 + (deg1 - deg0) * (i / steps))
            px, py = cx + rx * math.cos(a), cy + ry * math.sin(a)
            if rad <= 0.4:
                self.set_px(int(round(px)), int(round(py)))
            else:
                self.draw_disc(px, py, rad)

    def draw_bayer_box(self, x0: int, y0: int, x1: int, y1: int, density: float) -> None:
        lvl = max(0.0, min(1.0, density)) * 16.0
        for y in range(max(0, y0), min(self.height, y1)):
            for x in range(max(0, x0), min(self.width, x1)):
                if _BAYER_4X4[y & 3][x & 3] < lvl:
                    self.set_px(x, y, True)

    def draw_star(self, cx: int, cy: int, arm: int = 4) -> None:
        self.draw_line(cx - arm, cy, cx + arm, cy, thickness=1.0)
        self.draw_line(cx, cy - arm, cx, cy + arm, thickness=1.0)
        self.draw_disc(cx, cy, 1.4)

    def render(self) -> list[str]:
        rows: list[str] = []
        for cy in range(0, self.height, 4):
            chars: list[str] = []
            for cx in range(0, self.width, 2):
                mask = 0
                for dy in range(4):
                    row_off = (cy + dy) * self.width + cx
                    if self._buf[row_off]:
                        mask |= _DOT_BITS[dy][0]
                    if self._buf[row_off + 1]:
                        mask |= _DOT_BITS[dy][1]
                chars.append(chr(0x2800 + mask))
            rows.append("".join(chars))
        return rows


def _draw_zoe_braille_portrait() -> list[str]:
    """Original Zoe faceted ruby crown + expressive ᵔᵕᵔ smile + starlight in 2x4 Braille."""
    c = BrailleCanvas(100, 72)
    cx = 50.0
    # Soft dithered halo backdrop behind the gem crown
    for y in range(4, 68):
        for x in range(8, 92):
            d = math.hypot((x - cx) * 0.9, (y - 34.0) * 1.1)
            if 32.0 <= d <= 41.0 and _BAYER_4X4[y & 3][x & 3] < 3:
                c.set_px(x, y, True)
    # Faceted GEM diamond silhouette (crown + girdle + pavilion)
    verts = [(30, 12), (70, 12), (84, 28), (50, 66), (16, 28)]
    for i in range(len(verts)):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % len(verts)]
        c.draw_line(x0, y0, x1, y1, thickness=2.2)
    # Inner table, girdle bar & facet rays
    c.draw_line(16, 28, 84, 28, thickness=1.6)
    c.draw_line(30, 12, 34, 28, thickness=1.2)
    c.draw_line(70, 12, 66, 28, thickness=1.2)
    c.draw_line(34, 28, 50, 66, thickness=1.4)
    c.draw_line(66, 28, 50, 66, thickness=1.4)
    # Shaded right pavilion dither for crisp 3D depth
    for y in range(30, 63):
        t = (y - 28.0) / 38.0
        xr_inner = int(66.0 - 16.0 * t)
        xr_outer = int(84.0 - 34.0 * t)
        c.draw_bayer_box(xr_inner, y, xr_outer, y + 1, density=0.45)
    # Expressive cozy ᵔᵕᵔ smile inside the crown
    c.draw_arc(39.0, 23.0, 4.5, 4.0, 200.0, 340.0, thickness=1.8)
    c.draw_arc(61.0, 23.0, 4.5, 4.0, 200.0, 340.0, thickness=1.8)
    c.draw_arc(50.0, 22.0, 4.5, 3.8, 20.0, 160.0, thickness=1.8)
    # Minimalist 4-point starlight sparkles (.✦˙₊)
    c.draw_star(14, 12, arm=4)
    c.draw_star(86, 14, arm=4)
    c.draw_star(82, 54, arm=3)
    c.draw_disc(22, 8, 1.2)
    c.draw_disc(78, 8, 1.2)
    return c.render()


def _draw_flower_braille_crest() -> list[str]:
    """Original 4-stroke minimalist Zoe flower-smile-voice crest (U+2698) in 2x4 Braille."""
    c = BrailleCanvas(92, 68)
    cx = 46.0
    # Outer minimal ring
    c.draw_arc(cx, 34.0, 31.0, 29.0, 0.0, 360.0, thickness=1.2)
    # Top circle blossom
    c.draw_arc(cx, 20.0, 8.0, 7.5, 0.0, 360.0, thickness=2.6)
    # Mirrored smooth upward-sweeping leaves / open arms
    for side in (-1.0, 1.0):
        pts = [(cx + side * 20.0, 30.0), (cx + side * 12.0, 38.0), (cx + side * 4.0, 41.0), (cx, 44.0)]
        for i in range(len(pts) - 1):
            c.draw_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], thickness=2.6)
    # Vertical stem
    c.draw_line(cx, 42.0, cx, 57.0, thickness=2.6)
    # Starlight cluster (.✦˙₊)
    c.draw_star(76, 12, arm=4)
    c.draw_disc(69, 16, 1.2)
    c.draw_star(83, 18, arm=2)
    return c.render()


def _draw_jellyfish_braille_study() -> list[str]:
    """Original Stowers bioluminescent medusa / cnidarian Braille silhouette (Flora Pod A)."""
    c = BrailleCanvas(92, 68)
    cx = 46.0
    # Translucent bell dome with Bayer luminescence
    c.draw_arc(cx, 28.0, 24.0, 20.0, 180.0, 360.0, thickness=2.2)
    c.draw_arc(cx, 28.0, 17.0, 14.0, 190.0, 350.0, thickness=1.2)
    c.draw_line(22, 28, 70, 28, thickness=1.4)
    for y in range(11, 27):
        span = int(21.0 * math.sqrt(max(0.0, 1.0 - ((28.0 - y) / 20.0) ** 2)))
        c.draw_bayer_box(int(cx - span), y, int(cx + span), y + 1, density=0.35)
    # Graceful sinusoidal trailing tentacles
    for idx, ox in enumerate((-16, -9, -3, 3, 9, 16)):
        amp = 3.0 if idx % 2 == 0 else -2.5
        prev = (cx + ox, 29.0)
        for y in range(32, 63, 3):
            nx = cx + ox + amp * math.sin((y - 28.0) * 0.28 + idx)
            c.draw_line(prev[0], prev[1], nx, float(y), thickness=1.2)
            prev = (nx, float(y))
    c.draw_star(16, 14, arm=3)
    c.draw_star(78, 16, arm=3)
    return c.render()


def _draw_dvx_braille_desktop() -> list[str]:
    """1992 Quarterdeck DESQview/X overlapping tiled X11 windows miniature in 2x4 Braille."""
    c = BrailleCanvas(96, 64)
    # Back window (Application Manager)
    for x0, y0, x1, y1 in ((6, 6, 62, 46), (6, 6, 62, 13)):
        c.draw_line(x0, y0, x1, y0, 1.5)
        c.draw_line(x0, y1, x1, y1, 1.5)
        c.draw_line(x0, y0, x0, y1, 1.5)
        c.draw_line(x1, y0, x1, y1, 1.5)
    for row in range(2):
        for col in range(3):
            bx, by = 11 + col * 16, 17 + row * 12
            c.draw_bayer_box(bx, by, bx + 12, by + 8, density=0.45)
    # Front overlapping window (My First App)
    for y in range(20, 58):
        for x in range(36, 90):
            c.set_px(x, y, False)
    for x0, y0, x1, y1 in ((36, 20, 90, 58), (36, 20, 90, 27)):
        c.draw_line(x0, y0, x1, y0, 1.8)
        c.draw_line(x0, y1, x1, y1, 1.8)
        c.draw_line(x0, y0, x0, y1, 1.8)
        c.draw_line(x1, y0, x1, y1, 1.8)
    c.draw_arc(56.0, 41.0, 4.0, 3.5, 200.0, 340.0, 1.6)
    c.draw_arc(70.0, 41.0, 4.0, 3.5, 200.0, 340.0, 1.6)
    c.draw_arc(63.0, 41.0, 4.0, 3.2, 20.0, 160.0, 1.6)
    return c.render()


BRAILLE_TEMPLATES: dict[str, tuple[str, Any]] = {
    "zoe": ("Zoe Faceted Ruby Crown + ᵔᵕᵔ Smile + Starlight (50x18 Braille)", _draw_zoe_braille_portrait),
    "flower": ("Zoe Minimalist 4-Stroke Flower · Smile · Voice Crest (46x17 Braille)", _draw_flower_braille_crest),
    "jellyfish": ("Stowers Bioluminescent Medusa / Cnidarian Study (46x17 Braille)", _draw_jellyfish_braille_study),
    "dvx": ("1992 DESQview/X Application Manager & Window Kit (48x16 Braille)", _draw_dvx_braille_desktop),
}


def image_to_braille(image_path: str | Path, *, cols: int = 52, invert: bool = False) -> list[str]:
    """Convert any local PNG/JPG image into crisp 2x4 Bayer-dithered Unicode Braille art."""
    from PIL import Image

    src = Path(image_path).expanduser()
    if not src.is_file():
        raise ValueError(f"Image not found: {src}")
    cols = max(16, min(96, int(cols)))
    w_px = cols * 2
    with Image.open(src) as img:
        gray = img.convert("L")
        aspect = gray.height / max(1, gray.width)
        h_px = max(8, min(144, int(round(w_px * aspect * 0.92)) // 4 * 4))
        resized = gray.resize((w_px, h_px), Image.Resampling.LANCZOS)
        pixels = resized.load()
    canvas = BrailleCanvas(w_px, h_px)
    for y in range(h_px):
        for x in range(w_px):
            lum = int(pixels[x, y])
            if invert:
                lum = 255 - lum
            threshold = (_BAYER_4X4[y & 3][x & 3] + 0.5) * 16.0
            canvas.set_px(x, y, lum > threshold)
    return canvas.render()


def render_braille_template(target: str = "zoe", *, cols: int = 52) -> tuple[str, list[str]]:
    """Render a named built-in Braille template or convert an image path."""
    raw = (target or "zoe").strip()
    low = raw.lower()
    if low in BRAILLE_TEMPLATES:
        title, fn = BRAILLE_TEMPLATES[low]
        return title, fn()
    if Path(raw).expanduser().is_file():
        return f"Bayer-Dithered Braille Dot-Art ({Path(raw).name})", image_to_braille(raw, cols=cols)
    choices = ", ".join(BRAILLE_TEMPLATES)
    raise ValueError(f"Unknown Braille target {target!r}. Choose: {choices}, or pass an existing image path.")


def render_dvx_app_manager() -> list[str]:
    """Render a 1992 Quarterdeck DESQview/X-inspired Application Manager shell for starter software makers."""
    lines = [
        "╔══════════════════════════════════════════════════════════════════════════╗",
        "║ [■] DESQview/X × Zoe Starter Software Maker  (Zoe ⚘ ᵔᵕᵔ · 0 TOK)   [▼][▲]║",
        "╠══════════════════════════════════════════════════════════════════════════╣",
        "║  Application Manager — Double-click or run any starter tool below:       ║",
        "║                                                                          ║",
    ]
    for i in range(0, len(DVX_STARTER_TILES), 2):
        left = DVX_STARTER_TILES[i]
        right = DVX_STARTER_TILES[i + 1]
        lines.append(f"║   ┌──────────────────────────────┐   ┌──────────────────────────────┐    ║")
        lines.append(f"║   │ [{left['key']}] {left['title']:<24} │   │ [{right['key']}] {right['title']:<24} │    ║")
        lines.append(f"║   │  {left['cmd']:<27} │   │  {right['cmd']:<27} │    ║")
        lines.append(f"║   └──────────────────────────────┘   └──────────────────────────────┘    ║")
    lines.extend([
        "║                                                                          ║",
        "║  Rule: HFBC = Have Fun, Be Creative · Build with `/dvx scaffold myapp`   ║",
        "║  Safety: 100% local stdlib · 0 cloud tokens · sentience_claimed=False    ║",
        "╚══════════════════════════════════════════════════════════════════════════╝",
    ])
    return lines


_STARTER_APP_TEMPLATE = '''#!/usr/bin/env python3
"""{title} — Starter DESQview/X-Style Local App (Zero Dependencies, 0 Cloud Tokens).

Edit the `TILES` list or `BANNER` below to customize your own interactive terminal software!
Run with: python3 app.py
"""

from __future__ import annotations

BANNER = (
    "╔══════════════════════════════════════════════════════╗",
    "║ [■] {title_pad} [▼][▲] ║",
    "╠══════════════════════════════════════════════════════╣",
    "║  Built with Zoe ⚘ ᵔᵕᵔ · HFBC: Have Fun, Be Creative  ║",
    "╚══════════════════════════════════════════════════════╝",
)

TILES = [
    ("1", "Say Hello", lambda: "Hello from {title}! HFBC = Have Fun, Be Creative — edit TILES in app.py!"),
    ("2", "Show Crest", lambda: "Zoe ⚘ ᵔᵕᵔ · Intelligence Researcher ^-^ · Knowledge Engineering ◆"),
    ("3", "About Kit", lambda: "100% local Python stdlib · 0 GPU · 0 cloud tokens · easy to hack!"),
]


def run_once(choice: str) -> str:
    for key, _label, fn in TILES:
        if choice.strip() == key:
            return fn()
    return "Pick a tile number (1..3) or type q to quit."


def main() -> None:
    print("\\n".join(BANNER))
    while True:
        print("\\nTiles: " + "  |  ".join(f"[{{k}}] {{lbl}}" for k, lbl, _ in TILES) + "  |  [q] Quit")
        try:
            pick = input("{slug} ᵔᵕᵔ ❯ ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break
        if pick in {{"q", "quit", "exit"}}:
            break
        print("  └ " + run_once(pick))


if __name__ == "__main__":
    main()
'''


def scaffold_starter_app(app_name: str, base_dir: Path | None = None) -> dict[str, Any]:
    """Generate a runnable, zero-dependency DESQview/X-style starter software project."""
    clean = _SAFE_APP_RE.sub("-", (app_name or "").strip()).strip("-").lower()
    if not clean:
        raise ValueError("Usage: /dvx scaffold <app_name>  (letters, digits, hyphens, or underscores)")
    root = (Path(base_dir) if base_dir is not None else (Path.home() / ".zoe" / "maker")) / clean
    root.mkdir(parents=True, exist_ok=True)
    title = clean.replace("-", " ").replace("_", " ").title()
    app_py = root / "app.py"
    readme = root / "README.md"
    app_py.write_text(
        _STARTER_APP_TEMPLATE.format(title=title, title_pad=f"{title:<41}"[:41], slug=clean),
        encoding="utf-8",
    )
    readme.write_text(
        f"# {title}\n\n"
        "A clean, zero-dependency starter app inspired by **1992 Quarterdeck DESQview/X** and **Zoe ⚘ `ᵔᵕᵔ`**.\n\n"
        "## Run It\n```bash\npython3 app.py\n```\n\n"
        "## Make It Yours\n"
        "- Open `app.py` and add new entries to `TILES`.\n"
        "- Zero external packages, zero GPU, zero cloud tokens.\n",
        encoding="utf-8",
    )
    return {
        "ok": True,
        "app_name": clean,
        "dir": str(root),
        "app_py": str(app_py),
        "readme": str(readme),
        "tokens_used": 0,
        "sentience_claimed": False,
    }
