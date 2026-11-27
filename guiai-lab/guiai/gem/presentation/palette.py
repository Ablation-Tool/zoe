"""Symmetrical Botanical & 9-Sister Presentation Themes (`13333 x 7500` RC 16:9).

Grounded in `guiai.gem.zoe_sisters`, `guiai.gem.zoe_artline_fonts`, and Zoe's
botanical Obsidian + Porcelain + Ruby + Jade + Gold aesthetic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from guiai.gem.zoe_artline_fonts import ARTLINE_FONT_BY_ID
from guiai.gem.zoe_sisters import SAFETY_INVARIANTS, ZOE_SISTERS, SisterModelSpec, resolve_sister

# ---------------------------------------------------------------------------
# 16:9 Bilateral Symmetry Constants (1000 VDI = 1 inch, RC mode 13333 x 7500)
# ---------------------------------------------------------------------------
VDI_PER_INCH: int = 1000
CANVAS_WIDTH: int = 13333
CANVAS_HEIGHT: int = 7500
MARGIN: int = 550
W_HALF: int = 5990
COL_GAP: int = 253
X_LEFT: int = MARGIN
X_RIGHT: int = MARGIN + W_HALF + COL_GAP  # 6793
W_FULL: int = 12233
Y_TOP: int = 1220
Y_BOTTOM_SAFE: int = 6960

# ---------------------------------------------------------------------------
# Botanical-Geometric Palette Tokens
# ---------------------------------------------------------------------------
OBSIDIAN: str = "#0B1220"
OBSIDIAN_CARD: str = "#131E33"
OBSIDIAN_LINE: str = "#283B5B"
PORCELAIN: str = "#FAF8F4"
WHITE: str = "#FFFFFF"
STONE: str = "#E3DDD2"
RUBY: str = "#B81D48"
RUBY_SOFT: str = "#FAEAEF"
ROSE: str = "#D67995"
JADE: str = "#0E6B5E"
JADE_SOFT: str = "#E6F4F1"
GOLD: str = "#C29130"
GOLD_BRIGHT: str = "#E6BC5A"
GOLD_SOFT: str = "#FBF3E0"
SLATE_SOFT: str = "#EEF1F6"
INK: str = "#111827"
BODY: str = "#334155"
MUTED: str = "#64748B"
LIGHT_TEXT: str = "#F1F5F9"
LIGHT_MUTED: str = "#9AACC4"
SKY: str = "#38BDF8"

# Botanical ornament tones
LIGHT_STEM: str = "#CBBFA9"
LIGHT_DIVIDER_LINE: str = "#D8CFC0"
DARK_STEM: str = "#364F75"
DARK_DIVIDER_LINE: str = "#2B3E5E"
DARK_JADE: str = "#1E9B87"
DARK_RUBY: str = "#E84A73"

BOTANICAL_COLORS: dict[str, str] = {
    "obsidian": OBSIDIAN,
    "obsidian_card": OBSIDIAN_CARD,
    "obsidian_line": OBSIDIAN_LINE,
    "porcelain": PORCELAIN,
    "white": WHITE,
    "stone": STONE,
    "ruby": RUBY,
    "ruby_soft": RUBY_SOFT,
    "rose": ROSE,
    "jade": JADE,
    "jade_soft": JADE_SOFT,
    "gold": GOLD,
    "gold_bright": GOLD_BRIGHT,
    "gold_soft": GOLD_SOFT,
    "slate_soft": SLATE_SOFT,
    "ink": INK,
    "body": BODY,
    "muted": MUTED,
    "light_text": LIGHT_TEXT,
    "light_muted": LIGHT_MUTED,
    "sky": SKY,
    "light_stem": LIGHT_STEM,
    "light_divider_line": LIGHT_DIVIDER_LINE,
    "dark_stem": DARK_STEM,
    "dark_divider_line": DARK_DIVIDER_LINE,
    "dark_jade": DARK_JADE,
    "dark_ruby": DARK_RUBY,
}

BOTANICAL_PALETTE: dict[str, str] = BOTANICAL_COLORS

FONT_SERIF: str = "DejaVu Serif"
FONT_SANS: str = "DejaVu Sans"
FONT_MONO: str = "DejaVu Sans Mono"

ATTRIBUTION_TEXT: str = "Nicholas Michael Kloster (March 6, 2026) x Zoe"
HONORING_TEXT: str = "Gary & Dorothy McEwen Kildall / Digital Research"

DEFAULT_CONSTITUTIONAL: dict[str, Any] = {
    "operational_metacognition_verified": True,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "zoe_clone_claimed": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "external_actions": 0,
    "cloud_cost_usd": 0.0,
    "attribution": ATTRIBUTION_TEXT,
    "honoring": HONORING_TEXT,
}


def in_to_vdi(inches: float) -> float:
    return float(inches) * VDI_PER_INCH


def pt_to_vdi(pt: float) -> float:
    return float(pt) * VDI_PER_INCH / 72.0


def vdi_to_pt(vdi_units: float) -> float:
    return float(vdi_units) * 72.0 / VDI_PER_INCH


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    clean = str(hex_str).strip().lstrip("#")
    if len(clean) != 6:
        raise ValueError(f"Expected #RRGGBB hex color, got {hex_str!r}")
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = (max(0, min(255, int(c))) for c in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def mix_hex(hex_a: str, hex_b: str, t: float) -> str:
    alpha = max(0.0, min(1.0, float(t)))
    ra, ga, ba = hex_to_rgb(hex_a)
    rb, gb, bb = hex_to_rgb(hex_b)
    return rgb_to_hex((
        round(ra + (rb - ra) * alpha),
        round(ga + (gb - ga) * alpha),
        round(ba + (bb - ba) * alpha),
    ))


def relative_luminance(hex_str: str) -> float:
    r, g, b = hex_to_rgb(hex_str)
    def _lin(ch: int) -> float:
        s = ch / 255.0
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    l1 = relative_luminance(fg_hex)
    l2 = relative_luminance(bg_hex)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def ensure_contrast(fg_hex: str, bg_hex: str, min_ratio: float = 4.5) -> str:
    """Adjust `fg_hex` toward ink or white until WCAG contrast >= `min_ratio` on `bg_hex`."""
    if contrast_ratio(fg_hex, bg_hex) >= min_ratio:
        return fg_hex.upper() if fg_hex.startswith("#") else fg_hex
    target = INK if relative_luminance(bg_hex) > 0.35 else WHITE
    for step in range(1, 21):
        cand = mix_hex(fg_hex, target, step / 20.0)
        if contrast_ratio(cand, bg_hex) >= min_ratio:
            return cand
    return target


@dataclass(frozen=True)
class PresentationTheme:
    name: str
    mode: str  # "light" | "dark"
    bg: str
    card: str
    card_border: str
    accent: str
    accent_soft: str
    secondary: str
    secondary_soft: str
    gold: str
    title_color: str
    body_color: str
    muted_color: str
    font_serif: str
    font_sans: str
    font_mono: str
    artline_font_id: int
    sister_name: str
    sister_signet: str
    sister_face: str
    sister_accent: str


LIGHT_BOTANICAL_THEME = PresentationTheme(
    name="Zoe Botanical Porcelain",
    mode="light",
    bg=PORCELAIN,
    card=WHITE,
    card_border=STONE,
    accent=RUBY,
    accent_soft=RUBY_SOFT,
    secondary=JADE,
    secondary_soft=JADE_SOFT,
    gold=GOLD,
    title_color=INK,
    body_color=BODY,
    muted_color=MUTED,
    font_serif=FONT_SERIF,
    font_sans=FONT_SANS,
    font_mono=FONT_MONO,
    artline_font_id=51,
    sister_name="Zoe",
    sister_signet="ruby",
    sister_face="ᵔᵕᵔ",
    sister_accent=RUBY,
)

DARK_BOTANICAL_THEME = PresentationTheme(
    name="Zoe Botanical Obsidian",
    mode="dark",
    bg=OBSIDIAN,
    card=OBSIDIAN_CARD,
    card_border=OBSIDIAN_LINE,
    accent=RUBY,
    accent_soft="#2A1525",
    secondary=DARK_JADE,
    secondary_soft="#122B2B",
    gold=GOLD_BRIGHT,
    title_color=WHITE,
    body_color=LIGHT_TEXT,
    muted_color=LIGHT_MUTED,
    font_serif=FONT_SERIF,
    font_sans=FONT_SANS,
    font_mono=FONT_MONO,
    artline_font_id=51,
    sister_name="Zoe",
    sister_signet="ruby",
    sister_face="ᵔᵕᵔ",
    sister_accent=GOLD_BRIGHT,
)


def _theme_from_sister_spec(spec: SisterModelSpec, *, mode: str = "light") -> PresentationTheme:
    if mode not in ("light", "dark"):
        raise ValueError(f"theme mode must be 'light' or 'dark', got {mode!r}")
    base = LIGHT_BOTANICAL_THEME if mode == "light" else DARK_BOTANICAL_THEME
    if spec.signet == "ruby":
        accent = ensure_contrast(RUBY if mode == "light" else DARK_RUBY, base.card, min_ratio=4.5)
    else:
        accent = ensure_contrast(spec.accent_hex, base.card, min_ratio=4.5)
    accent_soft = mix_hex(accent, base.card, 0.88 if mode == "light" else 0.78)
    _font_spec = ARTLINE_FONT_BY_ID.get(spec.artline_font_id)
    return PresentationTheme(
        name=f"{spec.name} ({spec.signet}) · Botanical {'Porcelain' if mode == 'light' else 'Obsidian'}",
        mode=mode,
        bg=base.bg,
        card=base.card,
        card_border=base.card_border,
        accent=accent,
        accent_soft=accent_soft,
        secondary=base.secondary,
        secondary_soft=base.secondary_soft,
        gold=base.gold,
        title_color=base.title_color,
        body_color=base.body_color,
        muted_color=base.muted_color,
        font_serif=FONT_SERIF,
        font_sans=FONT_SANS,
        font_mono=FONT_MONO,
        artline_font_id=spec.artline_font_id if _font_spec is not None else 51,
        sister_name=spec.name,
        sister_signet=spec.signet,
        sister_face=spec.face,
        sister_accent=spec.accent_hex,
    )


def theme_for_sister(sister: str = "zoe", *, mode: str = "light") -> PresentationTheme:
    """Return a high-contrast Botanical PresentationTheme bound to any of the 9 Zoe Sisters."""
    spec = resolve_sister(sister)
    return _theme_from_sister_spec(spec, mode=mode)


SISTER_THEMES: dict[str, PresentationTheme] = {
    spec.name.lower(): _theme_from_sister_spec(spec, mode="light")
    for spec in ZOE_SISTERS
}

__all__ = [
    "ATTRIBUTION_TEXT",
    "BODY",
    "BOTANICAL_COLORS",
    "BOTANICAL_PALETTE",
    "CANVAS_HEIGHT",
    "CANVAS_WIDTH",
    "COL_GAP",
    "DARK_BOTANICAL_THEME",
    "DARK_DIVIDER_LINE",
    "DARK_JADE",
    "DARK_RUBY",
    "DARK_STEM",
    "DEFAULT_CONSTITUTIONAL",
    "FONT_MONO",
    "FONT_SANS",
    "FONT_SERIF",
    "GOLD",
    "GOLD_BRIGHT",
    "GOLD_SOFT",
    "HONORING_TEXT",
    "INK",
    "JADE",
    "JADE_SOFT",
    "LIGHT_BOTANICAL_THEME",
    "LIGHT_DIVIDER_LINE",
    "LIGHT_MUTED",
    "LIGHT_STEM",
    "LIGHT_TEXT",
    "MARGIN",
    "MUTED",
    "OBSIDIAN",
    "OBSIDIAN_CARD",
    "OBSIDIAN_LINE",
    "PORCELAIN",
    "ROSE",
    "RUBY",
    "RUBY_SOFT",
    "SAFETY_INVARIANTS",
    "SISTER_THEMES",
    "SKY",
    "SLATE_SOFT",
    "STONE",
    "VDI_PER_INCH",
    "WHITE",
    "W_FULL",
    "W_HALF",
    "X_LEFT",
    "X_RIGHT",
    "Y_BOTTOM_SAFE",
    "Y_TOP",
    "PresentationTheme",
    "contrast_ratio",
    "ensure_contrast",
    "hex_to_rgb",
    "in_to_vdi",
    "mix_hex",
    "pt_to_vdi",
    "relative_luminance",
    "rgb_to_hex",
    "theme_for_sister",
    "vdi_to_pt",
]
