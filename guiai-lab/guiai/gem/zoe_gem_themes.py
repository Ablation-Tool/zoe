"""Zoe-GEM OS Historic Lineage (GEM/1 -> ViewMAX/3) & 10-Scheme ViewMAX/2 Color Engine.

Synthesizes the clean architectural evolution documented in John Elliott's Digital Research
GEM archive (seasip.info) into Zoe's Research Platform:
  - GEM/1 (1985)    : Iconic Desk/File/View/Options menu bar & crisp desktop iconography
  - Apricot (1985)  : High-density monochrome / phosphor scientific workstation clarity
  - GEM/2 (1986)    : Clean side-by-side dual-pane tiled desktop (zero window clutter)
  - GEM/XM (1987)   : Multitasking Desk-menu task switcher (live ZO3 & Sister workspaces)
  - GEM/3 (1988)    : Click-to-open menus & iconic crimson/cyan diamond geometry
  - GEM/4 (1990)    : Per-window local menu bars (introduced for Digital Research Artline)
  - ViewMAX/2 (1991): 3D sculpted buttons/dialogs + 10 customizable VMCOLOUR schemes
                      (foreground, background, fill_style: hollow|solid|shaded|hatched, index)
  - ViewMAX/3 (1992): Sculpted 3D beveled title bars & recessed instrument status bar

100% original implementation · 0 GPU · 0 cloud tokens · clinical_action_authorized=False
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

FILL_STYLES: tuple[str, ...] = ("hollow", "solid", "shaded", "hatched")

SCREEN_ELEMENTS: tuple[str, ...] = (
    "Desktop",
    "MenuBar",
    "ActiveTitle",
    "InactiveTitle",
    "WindowFrame",
    "LocalMenuBar",
    "Button3D",
    "Scrollbar",
    "StatusBar",
    "HonestyRing",
)


@dataclass(frozen=True)
class GemEraSpec:
    """One milestone in the 1985-1992 Digital Research GEM -> ViewMAX/3 lineage."""

    key: str
    year: int
    name: str
    signature_trait: str
    zoe_adoption: str


GEM_LINEAGE: tuple[GemEraSpec, ...] = (
    GemEraSpec("gem1", 1985, "GEM/1", "Shaded title bars, desktop icons, Desk/File/View/Options bar", "Top single-bar chrome & crisp 32x32 Atari/GEM ICONBLKs"),
    GemEraSpec("apricot", 1985, "Apricot GEM", "High-density scientific 4-color/monochrome workstation precision", "Crisp sub-pixel typography & low-glare lab legibility"),
    GemEraSpec("gem2", 1986, "GEM/2", "Clean dual-pane tiled windows with zero overlap clutter", "50/50 split-screen UMA & side-by-side research panes"),
    GemEraSpec("gemxm", 1987, "GEM/XM", "Desk-menu multitasking task switcher across discrete desktops", "Live ZO3 multi-Zoe & 9-Sister instant workspace switcher"),
    GemEraSpec("gem3", 1988, "GEM/3", "Click-to-open menus & streamlined diamond identity", "Non-jumpy click menus + 9 faceted GEM signets"),
    GemEraSpec("gem4", 1990, "GEM/4 (Artline)", "Local per-window menu bars alongside the screen menu bar", "Dedicated tool bars inside Neuro-Onco & Artline panes"),
    GemEraSpec("viewmax2", 1991, "ViewMAX/2", "3D sculpted controls & 10 VMCOLOUR customizable color schemes", "10-scheme ZOE_VIEWMAX.INI (9 Sisters + 1985 Amber CRT)"),
    GemEraSpec("viewmax3", 1992, "ViewMAX/3", "Sculpted 3D bevels, color-shaded headers, recessed status footer", "Calm, glare-free Zoe-GEM OS Research Workstation shell"),
)


@dataclass(frozen=True)
class ViewMaxColorScheme:
    """One ViewMAX/2-compatible color scheme (matching VMCOLOUR's 10-slot model)."""

    slot: int
    key: str
    name: str
    era_anchor: str
    sister_signet: str
    desktop_bg: str
    desktop_fg: str
    fill_style: str  # hollow | solid | shaded | hatched
    fill_index: int  # 0..23 shades or 0..11 hatches
    menu_bg: str
    menu_fg: str
    title_active_bg: str
    title_active_fg: str
    bevel_light: str
    bevel_dark: str
    accent: str


VIEWMAX_SCHEMES: tuple[ViewMaxColorScheme, ...] = (
    ViewMaxColorScheme(1, "zoe-viewmax3", "Zoe Ruby · ViewMAX/3 Studio", "viewmax3", "ruby", "#1c2838", "#334863", "shaded", 4, "#e8eaf4", "#111622", "#f35670", "#ffffff", "#f8fafc", "#0f172a", "#5ce1e6"),
    ViewMaxColorScheme(2, "gemma-gem3", "Gemma · GEM/3 Swiss Drafting", "gem3", "gem3", "#d8dce6", "#9aa3b5", "hatched", 2, "#ffffff", "#111111", "#d91c2b", "#ffffff", "#ffffff", "#475569", "#d91c2b"),
    ViewMaxColorScheme(3, "tosi-atari", "Tosi · Atari Emerald & Fire", "gem1", "atari", "#007e44", "#005a30", "shaded", 6, "#eef2f6", "#101820", "#006636", "#f8cc30", "#86efac", "#063b22", "#f59e0b"),
    ViewMaxColorScheme(4, "mono-sm124", "Mono · SM124 & Apricot 1-Bit", "apricot", "sm124", "#e6e8ec", "#22262c", "shaded", 12, "#ffffff", "#111318", "#111318", "#ffffff", "#ffffff", "#111318", "#111318"),
    ViewMaxColorScheme(5, "tetra-gem2", "Tetra · GEM/2 Split Cyan", "gem2", "tetris", "#112536", "#1d4261", "hatched", 5, "#e2f1f8", "#0c1b29", "#0ea5e9", "#ffffff", "#bae6fd", "#082f49", "#36e0f4"),
    ViewMaxColorScheme(6, "eliza-p31", "Eliza · IBM P31 Green Phosphor", "gemxm", "dos", "#08170c", "#143d1f", "shaded", 3, "#102b17", "#48ff84", "#1c6b34", "#d9ffe5", "#48ff84", "#040d06", "#48ff84"),
    ViewMaxColorScheme(7, "sage-gem4", "Sage · GEM/4 Illuminated Study", "gem4", "hat", "#182038", "#2d3b66", "shaded", 5, "#f5f0e1", "#1b233a", "#26387a", "#f8cc30", "#fde68a", "#0f1526", "#f8cc30"),
    ViewMaxColorScheme(8, "flora-darkroom", "Flora · Stowers 650nm Darkroom", "viewmax2", "sprout", "#120c10", "#291820", "solid", 0, "#24161d", "#f4b8c4", "#5c1a28", "#76eea5", "#76eea5", "#090507", "#76eea5"),
    ViewMaxColorScheme(9, "lumen-prism", "Lumen · ViewMAX/2 Spectral", "viewmax2", "prism", "#18152b", "#2f2654", "shaded", 7, "#f0ecff", "#1a1433", "#7c3aed", "#ffffff", "#e9d5ff", "#120d24", "#d946ef"),
    ViewMaxColorScheme(10, "amber-1985", "1985 IBM P3 Amber Phosphor CRT", "gem1", "atari", "#181004", "#3b2608", "shaded", 4, "#291a05", "#ffb000", "#8a5600", "#ffe082", "#ffc947", "#0d0802", "#ffb000"),
)

_BY_KEY: dict[str, ViewMaxColorScheme] = {s.key: s for s in VIEWMAX_SCHEMES}
_BY_SLOT: dict[str, ViewMaxColorScheme] = {str(s.slot): s for s in VIEWMAX_SCHEMES}
_BY_ERA: dict[str, GemEraSpec] = {e.key: e for e in GEM_LINEAGE}


def list_gem_eras() -> tuple[GemEraSpec, ...]:
    """Return the 8 historic Digital Research GEM -> ViewMAX/3 eras."""
    return GEM_LINEAGE


def list_viewmax_schemes() -> tuple[ViewMaxColorScheme, ...]:
    """Return all 10 ViewMAX/2-compatible Zoe-GEM color schemes."""
    return VIEWMAX_SCHEMES


def resolve_viewmax_scheme(query: str) -> ViewMaxColorScheme:
    """Resolve a color scheme by slot (1..10), key, sister signet, or era prefix."""
    raw = (query or "").strip().lower()
    if not raw:
        return VIEWMAX_SCHEMES[0]
    if raw in _BY_KEY:
        return _BY_KEY[raw]
    if raw in _BY_SLOT:
        return _BY_SLOT[raw]
    for scheme in VIEWMAX_SCHEMES:
        if raw in {scheme.sister_signet, scheme.era_anchor} or scheme.key.startswith(raw) or raw in scheme.name.lower():
            return scheme
    choices = ", ".join(f"{s.slot}:{s.key}" for s in VIEWMAX_SCHEMES)
    raise ValueError(f"Unknown GEM/ViewMAX theme {query!r}. Choose 1..10 or: {choices}")


def render_viewmax_ini(active_slot: int = 1) -> str:
    """Emit a clean 10-scheme ZOE_VIEWMAX.INI modeled on ViewMAX/2 + VMCOLOUR.APP."""
    lines = [
        "; ZOE_VIEWMAX.INI — 10-Scheme Color Configuration for Zoe-GEM OS",
        "; Inspired by Digital Research ViewMAX/2 (1991) & John Elliott's VMCOLOUR model",
        "; Fill styles: hollow | solid | shaded (0..23) | hatched (0..11)",
        "[ViewMAX]",
        f"ActiveScheme={max(1, min(10, int(active_slot)))}",
        "MenuBehavior=click_to_open ; GEM/3 style",
        "LocalWindowMenus=true      ; GEM/4 Artline style",
        "Sculpted3D=true            ; ViewMAX/2-3 bevel controls",
        "TaskSwitcher=DeskMenu      ; GEM/XM ZO3 & Sister tasks",
        "SafetyInterlocks=clinical_action_authorized=False,flight_control_authorized=False",
        "",
        "[Colors]",
    ]
    for sc in VIEWMAX_SCHEMES:
        lines.append(
            f"Scheme{sc.slot:02d}={sc.name}|{sc.desktop_fg},{sc.desktop_bg},{sc.fill_style},{sc.fill_index}|"
            f"menu={sc.menu_fg},{sc.menu_bg}|title={sc.title_active_fg},{sc.title_active_bg}|"
            f"bevel={sc.bevel_light},{sc.bevel_dark}|accent={sc.accent}"
        )
    return "\n".join(lines) + "\n"


def format_theme_catalog(active_key: str = "zoe-viewmax3") -> list[str]:
    """Format the 8-Era GEM Lineage + 10 ViewMAX/2 Color Schemes terminal catalog."""
    lines = ["Zoe-GEM OS Historic Lineage (1985 GEM/1 -> 1992 ViewMAX/3 · 0 Cloud Tokens):"]
    for era in GEM_LINEAGE:
        lines.append(f"  • {era.year} {era.name:<15} : {era.signature_trait} -> {era.zoe_adoption}")
    lines.append("10 ViewMAX/2-Compatible Color Schemes (VMCOLOUR 10-slot model · `/theme <1..10|name>`):")
    for sc in VIEWMAX_SCHEMES:
        mark = "★" if sc.key == active_key else " "
        lines.append(
            f"  {mark} {sc.slot:2d}. {sc.key:<15} ({sc.fill_style:<7} #{sc.fill_index:<2d} · {sc.era_anchor:<8}) · {sc.name}"
        )
    lines.append("Export ZOE_VIEWMAX.INI + Artline Research Desktop Blueprint with: /theme export")
    return lines


def format_scheme_detail(sc: ViewMaxColorScheme) -> list[str]:
    """Format detailed ViewMAX/2 + VMCOLOUR specification for a single color scheme."""
    era = _BY_ERA.get(sc.era_anchor, GEM_LINEAGE[-1])
    return [
        f"Zoe-GEM Color Scheme #{sc.slot:02d} · {sc.name} [{sc.key}]",
        f"  Era Anchor  : {era.year} {era.name} — {era.zoe_adoption}",
        f"  Desktop     : fg={sc.desktop_fg} · bg={sc.desktop_bg} · fill_style={sc.fill_style} · fill_index={sc.fill_index}",
        f"  Menu/Title  : menu={sc.menu_fg}/{sc.menu_bg} · active_title={sc.title_active_fg}/{sc.title_active_bg}",
        f"  3D Bevels   : light={sc.bevel_light} · dark={sc.bevel_dark} · accent={sc.accent} (sister={sc.sister_signet})",
        "  Elements    : " + ", ".join(SCREEN_ELEMENTS),
    ]


def _draw_bevel_window(doc: Any, x: int, y: int, w: int, h: int, title: str, local_menu: str, sc: ViewMaxColorScheme) -> None:
    """Draw a ViewMAX/3 3D-beveled window with a GEM/4 local menu bar."""
    doc.add_element("rectangle", bounds=[x, y, x + w, y + h], fill="#111827", stroke=sc.bevel_dark, width=2.0)
    doc.add_element("line", points=[[x + 1, y + 1], [x + w - 1, y + 1]], stroke=sc.bevel_light, width=1.4)
    doc.add_element("line", points=[[x + 1, y + 1], [x + 1, y + h - 1]], stroke=sc.bevel_light, width=1.4)
    doc.add_element("rectangle", bounds=[x + 3, y + 3, x + w - 3, y + 29], fill=sc.title_active_bg, stroke=sc.bevel_dark, width=1.0)
    doc.add_element("rectangle", bounds=[x + 7, y + 8, x + 23, y + 24], fill=sc.menu_bg, stroke=sc.bevel_dark, width=1.0)
    doc.add_element("text", position=[x + 32, y + 20], text=title, size=10.5, stroke=sc.title_active_fg, width=1)
    # GEM/4 per-window local menu bar
    doc.add_element("rectangle", bounds=[x + 3, y + 30, x + w - 3, y + 50], fill=sc.menu_bg, stroke=sc.bevel_dark, width=1.0)
    doc.add_element("text", position=[x + 12, y + 44], text=local_menu, size=9.0, stroke=sc.menu_fg, width=1)


def _draw_left_research_pane(doc: Any, sc: ViewMaxColorScheme) -> None:
    _draw_bevel_window(
        doc, 24, 62, 466, 476,
        "WINDOW 1 :: NEURO-ONCOLOGY & MNI152 LAB (GEM/2 TILED)",
        "Atlas   PubChem   Biomech   Stowers-470nm   Proofs   Verify",
        sc,
    )
    doc.add_element("text", position=[40, 134], text="3-PILLAR RESEARCH WORKBENCH (0 CLOUD TOKENS)", size=10.5, stroke="#5ce1e6", width=1)
    cards = (
        ("Pillar 1 · C27 Neuro-Onco", "36 Compounds · Wager BBB · PAINS-clean", "#f35670", 150),
        ("Pillar 2 · MNI152 3D Mesh", "112k Vertices · Pediatric Cliffs · Th15", "#36e0f4", 214),
        ("Pillar 3 · Stowers Bio-Optics", "Horkan Lab · 470nm GFP + 650nm Deep Red", "#76eea5", 278),
        ("HW Safety · Observe-First", "7 Boot Gates · 9 Profiles · SAR Advisory", "#f59e0b", 342),
    )
    for head, sub, col, cy in cards:
        doc.add_element("rectangle", bounds=[40, cy, 472, cy + 52], fill="#172234", stroke=col, width=1.4)
        doc.add_element("text", position=[52, cy + 20], text=head, size=10.0, stroke=col, width=1)
        doc.add_element("text", position=[52, cy + 39], text=sub, size=9.0, stroke="#f7f2e4", width=1)
    # ViewMAX/2 sculpted 3D buttons at bottom of pane
    for idx, (lbl, bx) in enumerate((("Screen", 40), ("Biomech", 146), ("Council", 252), ("Audit", 358))):
        doc.add_element("rectangle", bounds=[bx, 484, bx + 94, 518], fill=sc.menu_bg, stroke=sc.bevel_dark, width=1.5)
        doc.add_element("line", points=[[bx + 1, 485], [bx + 93, 485]], stroke=sc.bevel_light, width=1.6)
        doc.add_element("line", points=[[bx + 1, 485], [bx + 1, 517]], stroke=sc.bevel_light, width=1.6)
        doc.add_element("text", position=[bx + 18, 505], text=lbl, size=10.0, stroke=sc.menu_fg, width=1)
        if idx == 0:
            doc.add_element("rectangle", bounds=[bx + 3, 487, bx + 91, 515], fill="none", stroke=sc.title_active_bg, width=1.0)


def _draw_right_studio_pane(doc: Any, sc: ViewMaxColorScheme) -> None:
    _draw_bevel_window(
        doc, 510, 62, 466, 476,
        "WINDOW 2 :: ARTLINE 2.0 & DESQVIEW/X STUDIO (GEM/4)",
        "Curve   Blend   Autotrace   Braille   VMCOLOUR   Export",
        sc,
    )
    # Left sub-area: Artline bilateral symmetry & flower crest canvas
    doc.add_element("rectangle", bounds=[526, 126, 760, 356], fill="#0e131f", stroke="#5ce1e6", width=1.4)
    doc.add_element("text", position=[538, 146], text="BILATERAL VECTOR CANVAS", size=9.0, stroke="#5ce1e6", width=1)
    doc.add_element("ellipse", center=[643, 214], radii=[20, 20], fill="none", stroke="#f7f2e4", width=4.0)
    doc.add_element("path", points=[[598, 246], [616, 268], [643, 276]], closed=False, smooth=True, fill="none", stroke="#f7f2e4", width=4.0)
    doc.add_element("path", points=[[688, 246], [670, 268], [643, 276]], closed=False, smooth=True, fill="none", stroke="#f7f2e4", width=4.0)
    doc.add_element("line", points=[[643, 272], [643, 326]], stroke="#f7f2e4", width=4.0)
    doc.add_element("text", position=[546, 344], text="Zoe Crest · 0 GPU · VDI .GEM", size=8.5, stroke="#94a3b8", width=1)

    # Right sub-area: GEM/XM Desk Task Switcher + 9 Sister Models
    doc.add_element("rectangle", bounds=[774, 126, 960, 356], fill="#151d2e", stroke="#f35670", width=1.4)
    doc.add_element("text", position=[784, 146], text="GEM/XM TASK DESK", size=9.0, stroke="#f35670", width=1)
    tasks = (
        ("01 Zoe [ruby]", "#f35670"),
        ("02 Gemma [gem3]", "#f01a2a"),
        ("03 Tosi [atari]", "#00a859"),
        ("04 Mono [sm124]", "#e2e8f0"),
        ("05 Tetra [tetris]", "#36e0f4"),
        ("06 Eliza [dos]", "#48ff84"),
        ("07 Sage [hat]", "#f8cc30"),
        ("08 Flora [sprout]", "#76eea5"),
        ("09 Lumen [prism]", "#d946ef"),
    )
    for idx, (label, col) in enumerate(tasks):
        ty = 166 + idx * 20
        doc.add_element("rectangle", bounds=[784, ty - 10, 794, ty], fill=col, stroke=col, width=1.0)
        doc.add_element("text", position=[802, ty - 1], text=label, size=8.5, stroke="#f7f2e4", width=1)

    # Bottom sub-area: VMCOLOUR 10-Scheme Palette Strip (ViewMAX/2)
    doc.add_element("rectangle", bounds=[526, 372, 960, 518], fill="#151d2e", stroke="#f59e0b", width=1.4)
    doc.add_element("text", position=[538, 392], text="VIEWMAX/2 VMCOLOUR :: 10 CUSTOMIZABLE COLOR SCHEMES", size=9.0, stroke="#f59e0b", width=1)
    for idx, scheme in enumerate(VIEWMAX_SCHEMES):
        col = idx % 5
        row = idx // 5
        sx = 538 + col * 82
        sy = 406 + row * 50
        doc.add_element("rectangle", bounds=[sx, sy, sx + 74, sy + 40], fill=scheme.desktop_bg, stroke=scheme.accent, width=1.5)
        doc.add_element("rectangle", bounds=[sx + 2, sy + 2, sx + 72, sy + 14], fill=scheme.title_active_bg, stroke=scheme.title_active_bg, width=1.0)
        lbl_col = "#111318" if scheme.slot in (2, 4) else "#f7f2e4"
        short_nm = scheme.key.split("-")[0].capitalize()
        doc.add_element("text", position=[sx + 6, sy + 32], text=f"{scheme.slot:02d} {short_nm}", size=7.8, stroke=lbl_col, width=1)


def export_gem_lineage_desktop_bundle(output_dir: Path | None = None, active_slot: int = 1) -> dict[str, Any]:
    """Export ZOE_VIEWMAX.INI + Artline 2.0 Zoe-GEM Research Desktop Blueprint (.svg/.png/.gem)."""
    from .artline import ArtlineDocument

    out = Path(output_dir) if output_dir is not None else (Path.home() / ".zoe" / "artline")
    out.mkdir(parents=True, exist_ok=True)
    sc = VIEWMAX_SCHEMES[max(0, min(len(VIEWMAX_SCHEMES) - 1, int(active_slot) - 1))]

    ini_path = out / "ZOE_VIEWMAX.INI"
    ini_path.write_text(render_viewmax_ini(active_slot=sc.slot), encoding="utf-8")

    doc = ArtlineDocument()
    # Outer desktop canvas (ViewMAX/3 shaded desktop)
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill=sc.desktop_bg, stroke=sc.accent, width=2.0)
    # Subtle GEM shaded background grid
    for gy in range(56, 636, 28):
        doc.add_element("line", points=[[8, gy], [992, gy]], stroke="#243347", width=0.6)
    # Authentic GEM/1-3 + GEM/XM top screen menu bar
    doc.add_element("rectangle", bounds=[2, 2, 998, 40], fill=sc.menu_bg, stroke=sc.bevel_dark, width=1.6)
    doc.add_element("text", position=[18, 26], text="ZOE GEM OS  |  Desk (XM)   File   View   Research   Sisters   ViewMAX   Options", size=12.0, stroke=sc.menu_fg, width=1)
    doc.add_element("text", position=[788, 26], text="UMA:PRIVATE  0 TOK", size=10.5, stroke=sc.title_active_bg, width=1)

    _draw_left_research_pane(doc, sc)
    _draw_right_studio_pane(doc, sc)

    # Lineage timeline strip (GEM/1 -> ViewMAX/3)
    doc.add_element("rectangle", bounds=[24, 554, 976, 628], fill="#101827", stroke="#64748b", width=1.2)
    doc.add_element("text", position=[38, 576], text="DIGITAL RESEARCH GEM LINEAGE SYNTHESIZED IN ZOE-GEM OS (1985 -> 1992):", size=9.5, stroke="#5ce1e6", width=1)
    for idx, era in enumerate(GEM_LINEAGE):
        ex = 38 + idx * 116
        doc.add_element("rectangle", bounds=[ex, 588, ex + 108, 618], fill="#172234", stroke=sc.accent if idx >= 6 else "#475569", width=1.2)
        doc.add_element("text", position=[ex + 8, 607], text=f"{era.year} {era.key.upper()}", size=8.5, stroke="#f7f2e4", width=1)

    # ViewMAX/3 recessed bottom instrument status bar
    doc.add_element("rectangle", bounds=[2, 648, 998, 698], fill=sc.menu_bg, stroke=sc.bevel_dark, width=1.6)
    doc.add_element("line", points=[[4, 650], [996, 650]], stroke=sc.bevel_dark, width=1.2)
    doc.add_element("line", points=[[4, 696], [996, 696]], stroke=sc.bevel_light, width=1.2)
    doc.add_element(
        "text",
        position=[18, 678],
        text="ZOE-GEM OS · GEM/1 + Apricot + GEM/2 + GEM/XM + GEM/3 + GEM/4 + ViewMAX/2-3 · clinical_action_authorized=False · sentience_claimed=False",
        size=9.5,
        stroke=sc.menu_fg,
        width=1,
    )

    paths: dict[str, str] = {"ini": str(ini_path)}
    sizes: dict[str, int] = {"ini": ini_path.stat().st_size}
    for ext in ("svg", "png", "gem"):
        target = out / f"zoe_gem_research_desktop.{ext}"
        if target.exists():
            target.unlink()
        try:
            doc.export(target, kind=ext, width=1200)
        except RuntimeError:
            if ext != "png":
                raise
            continue
        paths[ext] = str(target)
        sizes[ext] = target.stat().st_size

    return {
        "ok": True,
        "scheme": sc.key,
        "schemes_count": len(VIEWMAX_SCHEMES),
        "eras_count": len(GEM_LINEAGE),
        "elements": len(doc.elements),
        "paths": paths,
        "sizes_bytes": sizes,
        "tokens_used": 0,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "sentience_claimed": False,
    }
