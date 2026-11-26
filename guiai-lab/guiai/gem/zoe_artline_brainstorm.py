"""Zoe Artline Brainstorming Studio — Deterministic Visual State Morphing & 4 Artline 2.0 Concepts.

Extends Digital Research GEM / Artline 2.0 (`ArtlineDocument` -> `.svg`, `.png`, `.gem`)
with a glass-box visual state machine, 4 new 18x23 TrueColor visual-state sprites
(`brain`, `bulb`, `helix`, `chess`), a transparent human-in-the-loop Drafts/Scratchpad
Drawer (with Quiet Mode), and 4 distinct Artline vector brainstorming studio concepts:
  1. `desk`   — The Brain & Bulb Morphing Desk + Transparent Drafts Drawer
  2. `chess`  — The Artline Chessboard & Counterpoint Fencing Stage
  3. `sector` — The Artline Research Spaceship Cockpit (Sector 07)
  4. `mondo`  — The "Mondo" Freeform Artline Creative Playground & Pinboard

Constitutional Invariants (`CONSTITUTION.md`):
  glass_box_transparent = True · hidden_private_thoughts = False
  external_actions = 0 · sentience_claimed = False
  clinical_action_authorized = False · cure_claim = False · tokens_used = 0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence

from .artline import ArtlineDocument, blend_polygons
from .lume_header import PALETTE as BASE_PALETTE, _pixel_cell

ARTLINE_BRAINSTORM_CONTRACT = "zoe-artline-brainstorm-studio/v1"

CONSTITUTIONAL_FLAGS: dict[str, Any] = {
    "glass_box_transparent": True,
    "hidden_private_thoughts": False,
    "external_actions": 0,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "tokens_used": 0,
    "attribution": "Nicholas Michael Kloster; Digital Research GEM / Artline (Gary Kildall)",
}

# Digital Research Artline 2.0 Palette
_BG = "#0b0d18"
_CARD = "#141a2e"
_VIOLET = "#261447"
_GRID = "#2c244f"
_MAGENTA = "#d93b96"
_CYAN = "#5ce1e6"
_CREAM = "#f4ebd6"
_RUBY = "#f35670"
_AMBER = "#f8cc30"
_MINT = "#52e5a8"
_SLATE = "#94a3c8"
_BLUE = "#4f8ef7"
_PINK = "#ff85b3"

# ---------------------------------------------------------------------------
# 4 New 18x23 TrueColor State Sprites (Deterministic Visual Morphing Catalog)
# ---------------------------------------------------------------------------

STATE_PALETTE: dict[str, tuple[int, int, int] | None] = {
    **BASE_PALETTE,
    "W": (255, 252, 236),  # Bright luminous ivory-white specular highlight
    "S": (255, 138, 186),  # Cortex soft rose
    "K": (217, 59, 150),   # Cortex deep magenta sulcus
    "D": (132, 34, 96),    # Cortex shadow ridge
    "L": (255, 232, 118),  # Bulb luminous core
    "A": (248, 196, 44),   # Bulb warm amber filament
    "U": (84, 156, 255),   # Helix / Chess cobalt
    "C": (56, 224, 244),   # Helix / Spark cyan
    "Z": (148, 163, 196),  # Metallic bulb screw base / steel foil
    "Q": (86, 98, 128),    # Dark metallic base shade
}

# 1. brain: Pretty bilateral cortex with luminous gyri/sulci and cyan neural sparks
BRAIN_PIXELS: tuple[str, ...] = (
    ".......................",
    ".....SSSS.....SSSS.....",
    "...SSFFFFSS.SSFFFFSS...",
    "..SFFSSSSKSSSKSSSSFFS..",
    ".SFSSKKSSSSKSSSSKKSSFS.",
    ".SFSKSSFFSSKSSFFSSKSFS.",
    "SFSSKSSSSKSSSKSSSSKSSFS",
    "SFSSSKKKSSCKCSSKKKSSSFS",
    "SFSSSSSSKSSKSSKSSSSSSFS",
    ".SFSSKKSSSKKSSSKKSSFS..",
    ".SFDSSSSSSK.KSSSSSSDFS.",
    "..SFDDSSKK...KKSSDDFS..",
    "...SSDDDK.....KDDDSS...",
    ".....DDD..CCC..DDD.....",
    "..........CVC..........",
    "..........CV...........",
    ".......................",
    ".......................",
)

# 2. bulb: Glowing golden lightbulb with radiating cyan/gold idea sparks
BULB_PIXELS: tuple[str, ...] = (
    "...........Y...........",
    "....C......Y......C....",
    ".....C..YYYYYYY..C.....",
    ".......YYLLLLLYY.......",
    "......YLLWWWWLLY.......",
    "..Y..YLWWYYYYWWLY..Y...",
    ".....YLWYYAAYYWLY......",
    ".....YLWYYAAYYWLY......",
    ".....YLLWYYYYWLLY......",
    "..C...YLLYYYYLLY...C...",
    ".......YYAAAAYY........",
    "........YAAAAY.........",
    "........ZZZZZZ.........",
    "........QQQQQQ.........",
    "........ZZZZZZ.........",
    ".........QQQQ..........",
    "..........ZZ...........",
    ".......................",
)

# 3. helix: Google DeepMind AlphaFold / AlphaMissense double helix
HELIX_PIXELS: tuple[str, ...] = (
    ".......................",
    ".....CCC.......RRR.....",
    "......CCCYYYYYRRR......",
    ".......CCCSSSRRR.......",
    ".........CCRRR.........",
    "..........RRR..........",
    ".........RRCCC.........",
    ".......RRRGGGCCC.......",
    "......RRRYYYYYCCC......",
    ".....RRR.......CCC.....",
    "......RRRYYYYYCCC......",
    ".......RRRSSSCCC.......",
    ".........RRCCC.........",
    "..........CCC..........",
    ".........CCRRR.........",
    ".......CCCGGGRRR.......",
    "......CCCYYYYYRRR......",
    ".......................",
)

# 4. chess: Artline Knight / Counterpoint Fencing Duel Emblem
CHESS_PIXELS: tuple[str, ...] = (
    ".......................",
    ".........YYYYY.........",
    "........YUUUUUY........",
    ".......YUUWWUUUY.......",
    "......YUUCWUUUUUY......",
    ".....YUUUUUUUUUUUY.....",
    ".....YUUUUYUUUUUUY.....",
    "......YYYY.YUUUUUY.....",
    "..........YUUUUUY......",
    ".........YUUUUUUY......",
    "........YUUUUUUUUY.....",
    ".......YUUUUUUUUUUY....",
    "......YUUUUUUUUUUUUY...",
    "......YYYYYYYYYYYYYY...",
    ".....ZZZZZZZZZZZZZZZZ..",
    ".....QQQQQQQQQQQQQQQQ..",
    "....YYYYYYYYYYYYYYYYYY.",
    ".......................",
)

STATE_SPRITE_MAP: dict[str, tuple[str, ...]] = {
    "brain": BRAIN_PIXELS,
    "bulb": BULB_PIXELS,
    "helix": HELIX_PIXELS,
    "chess": CHESS_PIXELS,
}

STATE_DESCRIPTIONS: dict[str, str] = {
    "brain": "Pretty Brain — active during Dorothy MNI152, neuro-oncology & brain-library analysis",
    "bulb": "Glowing Bulb — lights up when a pipeline surfaces a new unverified draft idea or anomaly",
    "helix": "Double Helix — active during Google DeepMind AlphaFold v6 / AlphaMissense / AF3 runs",
    "chess": "Artline Knight — active during Counterpoint Chairs & 4-Peer Quorum hypothesis duels",
    "ruby": "Ruby GEM — default idle / steady ready state",
}


def render_state_sprite_terminal(state: str, *, color: bool = True) -> list[str]:
    """Render one visual state sprite (`brain`, `bulb`, `helix`, `chess`) to 9 terminal lines."""
    key = (state or "brain").strip().lower()
    rows = STATE_SPRITE_MAP.get(key, BRAIN_PIXELS)
    if not color:
        return ["".join("#" if ch != "." else " " for ch in r) for r in rows[::2]]
    width = len(rows[0])
    lines: list[str] = []
    for row_idx in range(0, len(rows), 2):
        top = rows[row_idx]
        bot = rows[row_idx + 1] if row_idx + 1 < len(rows) else "." * width
        parts: list[str] = []
        active = ""
        for c in range(width):
            cell, active = _pixel_cell(STATE_PALETTE.get(top[c]), STATE_PALETTE.get(bot[c]), active)
            parts.append(cell)
        if active:
            parts.append("\x1b[0m")
        lines.append("".join(parts))
    return lines


def render_state_sprite_png(state: str, out_path: str | Path, *, pixel_scale: int = 16) -> Path:
    """Render one crisp nearest-neighbor PNG preview of a visual state sprite."""
    from PIL import Image  # type: ignore

    key = (state or "brain").strip().lower()
    rows = STATE_SPRITE_MAP.get(key, BRAIN_PIXELS)
    h, w = len(rows), len(rows[0])
    img = Image.new("RGBA", (w, h), (14, 18, 32, 255))
    px = img.load()
    assert px is not None
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            rgb = STATE_PALETTE.get(ch)
            if rgb is not None:
                px[x, y] = (rgb[0], rgb[1], rgb[2], 255)
    big = img.resize((w * pixel_scale, h * pixel_scale), Image.Resampling.NEAREST)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    big.save(str(target))
    return target


@dataclass(frozen=True)
class VisualStateSnapshot:
    """Deterministic UI avatar state derived strictly from active module/pipeline telemetry."""

    state: str
    badge_label: str
    reason: str
    draft_count: int
    quiet_mode: bool
    bulb_alert_visible: bool
    constitutional: dict[str, Any] = field(default_factory=lambda: dict(CONSTITUTIONAL_FLAGS))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def resolve_visual_state(
    *,
    active_module: str = "",
    has_unreviewed_draft: bool = False,
    quiet_mode: bool = False,
    draft_count: int = 0,
) -> VisualStateSnapshot:
    """Deterministically select the UI visual state sprite from real software state.

    Zero autonomous agency or sentience claims: every state transition is a pure,
    auditable function of `(active_module, has_unreviewed_draft, quiet_mode)`.
    """
    mod = (active_module or "").strip().lower()
    bulb_visible = bool(has_unreviewed_draft and not quiet_mode)

    if any(k in mod for k in ("dorothy", "mni152", "brain", "neuro", "biomech", "glioma")):
        st, badge, rsn = "brain", "DOROTHY BRAIN MODE", f"Active module `{active_module}` targets neuroscience/MNI152."
    elif any(k in mod for k in ("alphafold", "alphamissense", "alphagenome", "deepmind", "helix", "protein")):
        st, badge, rsn = "helix", "DEEPMIND STRUCTURAL", f"Active module `{active_module}` targets structural biology."
    elif any(k in mod for k in ("counterpoint", "quorum", "chess", "fencing", "debate", "mcts")):
        st, badge, rsn = "chess", "COUNTERPOINT DUEL", f"Active module `{active_module}` runs hypothesis comparison."
    elif bulb_visible:
        st, badge, rsn = "bulb", "NEW DRAFT READY", "Unreviewed draft queued in transparent Scratchpad Drawer."
    else:
        st, badge, rsn = "ruby", "STEADY READY", "Idle / general research workbench state."

    return VisualStateSnapshot(
        state=st,
        badge_label=badge,
        reason=rsn,
        draft_count=max(0, int(draft_count)),
        quiet_mode=bool(quiet_mode),
        bulb_alert_visible=bulb_visible,
    )


@dataclass
class DraftIdeaEntry:
    """Transparent, inspectable draft hypothesis stored in the Scratchpad Drawer."""

    draft_id: str
    title: str
    summary: str
    source_module: str
    visual_state: str
    status: str = "unverified_draft"  # unverified_draft | reviewed | promoted | dismissed
    receipt_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IdeaScratchpadDrawer:
    """Glass-box transparent Drafts Drawer (never hidden/private; human-approved only)."""

    def __init__(self, *, quiet_mode: bool = False) -> None:
        self.quiet_mode = bool(quiet_mode)
        self._drafts: list[DraftIdeaEntry] = []

    def add_draft(
        self,
        title: str,
        summary: str,
        *,
        source_module: str = "shared_reasoning",
        visual_state: str = "bulb",
    ) -> DraftIdeaEntry:
        clean_title = (title or "").strip()
        clean_summary = (summary or "").strip()
        if not clean_title or not clean_summary:
            raise ValueError("Draft title and summary must not be empty")
        draft_id = f"draft_{len(self._drafts) + 1:03d}"
        body = {
            "draft_id": draft_id,
            "title": clean_title,
            "summary": clean_summary,
            "source_module": source_module,
            "visual_state": visual_state,
            "status": "unverified_draft",
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        entry = DraftIdeaEntry(receipt_sha256=digest, **body)
        self._drafts.append(entry)
        return entry

    def set_status(self, draft_id: str, new_status: str) -> DraftIdeaEntry:
        valid = {"unverified_draft", "reviewed", "promoted", "dismissed"}
        if new_status not in valid:
            raise ValueError(f"Invalid draft status {new_status!r}; choose from {sorted(valid)}")
        for d in self._drafts:
            if d.draft_id == draft_id:
                d.status = new_status
                return d
        raise KeyError(f"Unknown draft_id: {draft_id!r}")

    def list_drafts(self) -> list[DraftIdeaEntry]:
        """Return every draft transparently (glass_box_transparent=True)."""
        return list(self._drafts)

    def unreviewed_count(self) -> int:
        return sum(1 for d in self._drafts if d.status == "unverified_draft")

    def current_visual_state(self, active_module: str = "") -> VisualStateSnapshot:
        return resolve_visual_state(
            active_module=active_module,
            has_unreviewed_draft=self.unreviewed_count() > 0,
            quiet_mode=self.quiet_mode,
            draft_count=len(self._drafts),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": ARTLINE_BRAINSTORM_CONTRACT,
            "quiet_mode": self.quiet_mode,
            "total_drafts": len(self._drafts),
            "unreviewed_count": self.unreviewed_count(),
            "drafts": [d.to_dict() for d in self._drafts],
            "constitutional": dict(CONSTITUTIONAL_FLAGS),
        }


# ---------------------------------------------------------------------------
# Artline 2.0 Vector Studio Chrome & Helper Primitives
# ---------------------------------------------------------------------------

def _artline_frame(doc: ArtlineDocument, title: str, subtitle: str, badge: str, accent: str) -> None:
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill=_BG, stroke=_BG, width=1)
    # Subtle Artline violet diagonal drafting field
    doc.add_element(
        "path",
        points=[[480, 650], [990, 92], [990, 650]],
        closed=True,
        smooth=False,
        fill="#1a1336",
        stroke="#362466",
        width=1.2,
    )
    # Precision drafting grid
    for gx in range(60, 980, 60):
        doc.add_element("line", points=[[gx, 96], [gx, 642]], stroke="#1f2240", width=0.6)
    for gy in range(110, 640, 60):
        doc.add_element("line", points=[[36, gy], [964, gy]], stroke="#1f2240", width=0.6)

    # Top Digital Research Artline 2.0 emblem + title
    doc.add_element("rectangle", bounds=[32, 18, 64, 50], fill="#2e538f", stroke=_CREAM, width=1.5)
    doc.add_element("ellipse", center=[48, 34], radii=[10, 10], fill=_CREAM, stroke=_CREAM, width=1)
    doc.add_element("ellipse", center=[45, 34], radii=[7, 7], fill="#2e538f", stroke="#2e538f", width=1)
    doc.add_element("text", position=[76, 38], text="Digital Research · Zoe Artline 2.0 Studio", size=14, stroke=_CREAM, width=1)
    doc.add_element("text", position=[76, 68], text=title[:58], size=21, stroke=accent, width=1)
    doc.add_element("text", position=[36, 92], text=subtitle[:98], size=11, stroke=_SLATE, width=1)

    # Top-right state pill
    doc.add_element("rectangle", bounds=[736, 22, 966, 56], fill=_CARD, stroke=accent, width=1.8)
    doc.add_element("text", position=[752, 44], text=badge[:26], size=12, stroke=accent, width=1)

    # Constitutional footer
    doc.add_element("line", points=[[32, 654], [968, 654]], stroke=accent, width=1.6)
    doc.add_element(
        "text",
        position=[36, 678],
        text="GLASS-BOX UI · external_actions=0 · sentience_claimed=False · clinical_action_authorized=False · 0 GPU / 0 TOKENS",
        size=10.5,
        stroke=_AMBER,
        width=1,
    )


def _draw_artline_brain(doc: ArtlineDocument, cx: float, cy: float, scale: float = 1.0) -> None:
    """Draw a smooth Artline Bézier bilateral 'Pretty Brain' vector centerpiece."""
    def _pt(dx: float, dy: float) -> list[float]:
        return [round(cx + dx * scale, 1), round(cy + dy * scale, 1)]

    # Soft luminous aura rings
    doc.add_element("ellipse", center=[cx, cy], radii=[148 * scale, 128 * scale], fill="#151b38", stroke=_CYAN, width=1.2)
    doc.add_element("ellipse", center=[cx, cy], radii=[128 * scale, 110 * scale], fill="#1d183f", stroke=_MAGENTA, width=1.0)

    # Left hemisphere smooth Bézier lobe
    left_lobe = [
        _pt(-6, -92), _pt(-64, -86), _pt(-108, -42), _pt(-114, 16),
        _pt(-92, 68), _pt(-44, 92), _pt(-6, 84),
    ]
    right_lobe = [[round(2 * cx - p[0], 1), p[1]] for p in left_lobe]
    doc.add_element("path", points=left_lobe, closed=True, smooth=True, fill="#3b1d52", stroke=_PINK, width=3.0)
    doc.add_element("path", points=right_lobe, closed=True, smooth=True, fill="#222a54", stroke=_CYAN, width=3.0)

    # Graceful cortical gyri curves inside both hemispheres
    gyri_l1 = [_pt(-24, -64), _pt(-66, -46), _pt(-48, -14), _pt(-84, 8)]
    gyri_l2 = [_pt(-26, 22), _pt(-68, 34), _pt(-44, 62)]
    gyri_r1 = [[round(2 * cx - p[0], 1), p[1]] for p in gyri_l1]
    gyri_r2 = [[round(2 * cx - p[0], 1), p[1]] for p in gyri_l2]
    doc.add_element("path", points=gyri_l1, closed=False, smooth=True, fill="none", stroke=_MAGENTA, width=2.4)
    doc.add_element("path", points=gyri_l2, closed=False, smooth=True, fill="none", stroke=_PINK, width=2.2)
    doc.add_element("path", points=gyri_r1, closed=False, smooth=True, fill="none", stroke=_CYAN, width=2.4)
    doc.add_element("path", points=gyri_r2, closed=False, smooth=True, fill="none", stroke=_MINT, width=2.2)

    # Corpus callosum luminous bridge & stem
    doc.add_element("line", points=[_pt(-14, -10), _pt(14, -10)], stroke=_AMBER, width=2.5)
    doc.add_element("line", points=[_pt(-14, 12), _pt(14, 12)], stroke=_AMBER, width=2.5)
    doc.add_element("path", points=[_pt(-14, 86), _pt(-10, 120), _pt(10, 120), _pt(14, 86)], closed=True, smooth=False, fill="#2b3860", stroke=_CYAN, width=1.8)

    # Glowing neural nodes
    for dx, dy, col in [(-62, -46, _AMBER), (-48, 38, _MINT), (62, -46, _AMBER), (48, 38, _PINK), (0, -2, _CREAM)]:
        doc.add_element("ellipse", center=_pt(dx, dy), radii=[6 * scale, 6 * scale], fill=col, stroke=_BG, width=1.2)


def _draw_artline_bulb(doc: ArtlineDocument, cx: float, cy: float, scale: float = 1.0) -> None:
    """Draw a glowing Artline vector lightbulb with radiating golden sparks."""
    # Halo glow
    doc.add_element("ellipse", center=[cx, cy - 8 * scale], radii=[52 * scale, 52 * scale], fill="#2b261c", stroke=_AMBER, width=1.2)
    # Radiating rays
    for deg in (-150, -120, -90, -60, -30, 0, 180):
        rad = math.radians(deg)
        x0 = cx + math.cos(rad) * 44 * scale
        y0 = (cy - 8 * scale) + math.sin(rad) * 44 * scale
        x1 = cx + math.cos(rad) * 62 * scale
        y1 = (cy - 8 * scale) + math.sin(rad) * 62 * scale
        doc.add_element("line", points=[[round(x0, 1), round(y0, 1)], [round(x1, 1), round(y1, 1)]], stroke=_AMBER, width=2.2)
    # Glass globe + bright core
    doc.add_element("ellipse", center=[cx, cy - 10 * scale], radii=[34 * scale, 36 * scale], fill=_AMBER, stroke=_CREAM, width=2.2)
    doc.add_element("ellipse", center=[cx, cy - 12 * scale], radii=[18 * scale, 20 * scale], fill="#fff4b8", stroke="#fff4b8", width=1)
    # Filament V
    doc.add_element(
        "path",
        points=[
            [cx - 8 * scale, cy + 16 * scale],
            [cx - 6 * scale, cy - 8 * scale],
            [cx, cy + 2 * scale],
            [cx + 6 * scale, cy - 8 * scale],
            [cx + 8 * scale, cy + 16 * scale],
        ],
        closed=False,
        smooth=False,
        fill="none",
        stroke="#c25900",
        width=2.2,
    )
    # Screw base
    doc.add_element("rectangle", bounds=[cx - 16 * scale, cy + 22 * scale, cx + 16 * scale, cy + 32 * scale], fill="#94a3c8", stroke=_CREAM, width=1.2)
    doc.add_element("rectangle", bounds=[cx - 14 * scale, cy + 32 * scale, cx + 14 * scale, cy + 41 * scale], fill="#64748b", stroke=_CREAM, width=1.2)
    doc.add_element("rectangle", bounds=[cx - 9 * scale, cy + 41 * scale, cx + 9 * scale, cy + 47 * scale], fill="#475569", stroke=_CREAM, width=1.0)


# ---------------------------------------------------------------------------
# 4 Artline Brainstorming Studio Concept Plates
# ---------------------------------------------------------------------------

def build_artline_brainstorm_desk_plate() -> tuple[ArtlineDocument, dict[str, Any]]:
    """Concept 1: The Brain & Bulb Morphing Desk + Transparent Drafts Drawer."""
    doc = ArtlineDocument()
    _artline_frame(
        doc,
        title="Concept 1: Brain & Bulb Morphing Desk",
        subtitle="Deterministic visual state avatar (Brain / Bulb / Helix / Chess / Ruby) + Glass-Box Drafts Drawer",
        badge="MODE: BRAIN + BULB",
        accent=_PINK,
    )

    # Left stage: Active Morphing Visual Avatar Stage (Pretty Brain)
    doc.add_element("rectangle", bounds=[36, 112, 488, 524], fill=_CARD, stroke=_PINK, width=2.0)
    doc.add_element("rectangle", bounds=[36, 112, 488, 144], fill="#2a1642", stroke=_PINK, width=1.5)
    doc.add_element("text", position=[52, 133], text="ACTIVE STATE REPRESENTATION: DOROTHY BRAIN", size=12, stroke=_CREAM, width=1)
    _draw_artline_brain(doc, 262.0, 326.0, scale=1.08)
    doc.add_element("text", position=[54, 496], text="Trigger: Dorothy MNI152 / H3K27M module active (deterministic)", size=10.5, stroke=_CYAN, width=1)

    # Bottom-left state morphing strip
    doc.add_element("rectangle", bounds=[36, 540, 488, 636], fill=_CARD, stroke=_CYAN, width=1.5)
    doc.add_element("text", position=[52, 562], text="STATE MORPHING RAIL (SWITCHES AUTOMATICALLY BY TASK):", size=10.5, stroke=_CYAN, width=1)
    states = [("RUBY", _RUBY, "Idle"), ("BRAIN", _PINK, "Neuro"), ("BULB", _AMBER, "Draft"), ("HELIX", _BLUE, "AF-v6"), ("CHESS", _MINT, "Duel")]
    for idx, (lbl, col, sub) in enumerate(states):
        x0 = 52 + idx * 86
        doc.add_element("rectangle", bounds=[x0, 574, x0 + 78, 624], fill="#1d2440", stroke=col, width=1.8 if lbl in ("BRAIN", "BULB") else 1.0)
        doc.add_element("text", position=[x0 + 14, 595], text=lbl, size=10.5, stroke=col, width=1)
        doc.add_element("text", position=[x0 + 16, 614], text=sub, size=9.5, stroke=_SLATE, width=1)

    # Top-right: Glowing Bulb Notification Panel (Non-Intrusive + Quiet Mode)
    doc.add_element("rectangle", bounds=[512, 112, 964, 304], fill=_CARD, stroke=_AMBER, width=2.0)
    doc.add_element("rectangle", bounds=[512, 112, 964, 144], fill="#332814", stroke=_AMBER, width=1.5)
    doc.add_element("text", position=[528, 133], text="IDEA BULB CUE  [QUIET MODE: OFF]  [CLICK TO OPEN]", size=11.5, stroke=_AMBER, width=1)
    _draw_artline_bulb(doc, 594.0, 224.0, scale=0.88)
    doc.add_element("text", position=[670, 178], text="New Draft Queued (Unverified)", size=14, stroke=_AMBER, width=1)
    doc.add_element("text", position=[670, 204], text="Source: AlphaMissense + Kloster MCTS", size=11, stroke=_CREAM, width=1)
    doc.add_element("text", position=[670, 228], text="Cross-check CLPP Y118A & H3K27M", size=11, stroke=_SLATE, width=1)
    doc.add_element("text", position=[670, 248], text="in AlphaFold 3 complex batch.", size=11, stroke=_SLATE, width=1)
    doc.add_element("rectangle", bounds=[670, 262, 774, 290], fill="#1b3a2e", stroke=_MINT, width=1.4)
    doc.add_element("text", position=[688, 281], text="[ INSPECT ]", size=10.5, stroke=_MINT, width=1)
    doc.add_element("rectangle", bounds=[788, 262, 902, 290], fill="#242942", stroke=_SLATE, width=1.2)
    doc.add_element("text", position=[802, 281], text="[ SNOOZE ]", size=10.5, stroke=_SLATE, width=1)

    # Bottom-right: Transparent Drafts / Scratchpad Drawer
    doc.add_element("rectangle", bounds=[512, 322, 964, 636], fill=_CARD, stroke=_MINT, width=2.0)
    doc.add_element("rectangle", bounds=[512, 322, 964, 354], fill="#14302a", stroke=_MINT, width=1.5)
    doc.add_element("text", position=[528, 343], text="TRANSPARENT DRAFTS DRAWER (GLASS-BOX · 0 HIDDEN)", size=11.5, stroke=_MINT, width=1)

    draft_rows = [
        ("draft_001", "UNVERIFIED", _AMBER, "Compare H3-3A K28M vs ACVR1 R206H AF3 complex"),
        ("draft_002", "REVIEWED", _CYAN, "Test MNI152 pediatric compliance at 12 mL edema"),
        ("draft_003", "PROMOTED", _MINT, "Add ONC201 TxGemma BBB_Martins screen to C27"),
    ]
    for idx, (did, st, col, txt) in enumerate(draft_rows):
        y0 = 372 + idx * 82
        doc.add_element("rectangle", bounds=[530, y0, 946, y0 + 68], fill="#1a2138", stroke=col, width=1.4)
        doc.add_element("text", position=[544, y0 + 24], text=f"{did}  [{st}]", size=11.5, stroke=col, width=1)
        doc.add_element("text", position=[544, y0 + 48], text=txt, size=11.0, stroke=_CREAM, width=1)

    return doc, {"concept": "desk", "title": "Brain & Bulb Morphing Desk", "states": 5}


def build_artline_chess_fencing_plate() -> tuple[ArtlineDocument, dict[str, Any]]:
    """Concept 2: The Artline Chessboard & Counterpoint Fencing Stage."""
    doc = ArtlineDocument()
    _artline_frame(
        doc,
        title="Concept 2: Artline Chessboard & Fencing Stage",
        subtitle="Counterpoint Chairs & 4-Peer Quorum duels — hypotheses tested move by move",
        badge="MODE: CHESS / FENCING",
        accent=_MINT,
    )

    # Left: 8x8 Artline Vector Chessboard (Hypothesis Board)
    bx0, by0, cell = 44, 134, 48
    doc.add_element("rectangle", bounds=[bx0 - 8, by0 - 24, bx0 + 8 * cell + 8, by0 + 8 * cell + 20], fill=_CARD, stroke=_CYAN, width=2.0)
    doc.add_element("text", position=[bx0, by0 - 8], text="COUNTERPOINT HYPOTHESIS CHESSBOARD (8x8)", size=11.5, stroke=_CYAN, width=1)
    for r in range(8):
        for c in range(8):
            sq_col = "#243154" if (r + c) % 2 == 0 else "#101628"
            x = bx0 + c * cell
            y = by0 + r * cell
            doc.add_element("rectangle", bounds=[x, y, x + cell, y + cell], fill=sq_col, stroke="#34466e", width=0.8)

    # Highlighted tactical move vector arrows on the chessboard
    doc.add_element("line", points=[[bx0 + 1.5 * cell, by0 + 6.5 * cell], [bx0 + 2.5 * cell, by0 + 4.5 * cell]], stroke=_AMBER, width=3.2)
    doc.add_element("line", points=[[bx0 + 2.5 * cell, by0 + 4.5 * cell], [bx0 + 4.5 * cell, by0 + 3.5 * cell]], stroke=_MINT, width=3.2)
    doc.add_element("line", points=[[bx0 + 6.5 * cell, by0 + 1.5 * cell], [bx0 + 4.5 * cell, by0 + 3.5 * cell]], stroke=_RUBY, width=3.2)

    # Geometric Artline chess tokens
    pieces = [
        (1, 6, "N", _AMBER, "MCTS"),
        (4, 3, "Q", _MINT, "PROOF"),
        (6, 1, "K", _RUBY, "CRITIC"),
        (2, 4, "B", _CYAN, "Z3"),
    ]
    for c, r, sym, col, _tag in pieces:
        px = bx0 + c * cell + cell / 2
        py = by0 + r * cell + cell / 2
        doc.add_element("ellipse", center=[px, py], radii=[16, 16], fill=_BG, stroke=col, width=2.5)
        doc.add_element("text", position=[px - 5, py + 5], text=sym, size=14, stroke=col, width=1)

    # Right top: Artline Fencing Piste (En Garde Hypothesis Bout)
    doc.add_element("rectangle", bounds=[464, 110, 964, 366], fill=_CARD, stroke=_AMBER, width=2.0)
    doc.add_element("rectangle", bounds=[464, 110, 964, 142], fill="#302614", stroke=_AMBER, width=1.5)
    doc.add_element("text", position=[480, 131], text="FENCING PISTE: HYPOTHESIS A vs. ADVERSARIAL CRITIC", size=11.5, stroke=_AMBER, width=1)

    # Piste strip + center en-garde line
    doc.add_element("rectangle", bounds=[486, 260, 942, 294], fill="#1b243e", stroke=_SLATE, width=1.6)
    doc.add_element("line", points=[[714, 250], [714, 304]], stroke=_AMBER, width=2.2)
    doc.add_element("line", points=[[598, 260], [598, 294]], stroke=_CYAN, width=1.4)
    doc.add_element("line", points=[[830, 260], [830, 294]], stroke=_RUBY, width=1.4)

    # Crossed Artline fencing foils above center line
    doc.add_element("line", points=[[580, 240], [790, 166]], stroke=_CYAN, width=3.0)
    doc.add_element("ellipse", center=[592, 236], radii=[10, 14], fill="none", stroke=_CYAN, width=2.2)
    doc.add_element("line", points=[[848, 240], [638, 166]], stroke=_RUBY, width=3.0)
    doc.add_element("ellipse", center=[836, 236], radii=[10, 14], fill="none", stroke=_RUBY, width=2.2)
    # Clash spark
    doc.add_element("ellipse", center=[714, 194], radii=[12, 12], fill=_AMBER, stroke=_CREAM, width=1.8)
    doc.add_element("text", position=[490, 174], text="HYP-A (Cyan)", size=12, stroke=_CYAN, width=1)
    doc.add_element("text", position=[490, 194], text="ClpP Agonist", size=10.5, stroke=_SLATE, width=1)
    doc.add_element("text", position=[828, 174], text="CRITIC (Ruby)", size=12, stroke=_RUBY, width=1)
    doc.add_element("text", position=[828, 194], text="Off-Target Test", size=10.5, stroke=_SLATE, width=1)
    doc.add_element("text", position=[552, 332], text="Bout Score: SymPy=PASS · Z3=PASS · Kloster D_K=0.0047", size=11, stroke=_MINT, width=1)

    # Right bottom: Move Ledger & Audit Judge
    doc.add_element("rectangle", bounds=[464, 384, 964, 636], fill=_CARD, stroke=_MINT, width=2.0)
    doc.add_element("text", position=[482, 412], text="REFEREE LEDGER (SYMPY / Z3 / BLACKBOARD)", size=12, stroke=_MINT, width=1)
    moves = [
        ("1. e4 · Propose", "AlphaEvolve submits candidate invariant (score 1.00)", _CYAN),
        ("2. ...c5 · Parry", "Cold Auditor checks edge boundary & NaN rejection", _RUBY),
        ("3. Nf3 · Riposte", "SymPy + Z3 verify formal proof; 0 violations", _AMBER),
        ("4. 1-0 · Seal", "Blackboard logs SHA-256 receipt; human approves next", _MINT),
    ]
    for idx, (mv, desc, col) in enumerate(moves):
        yy = 442 + idx * 46
        doc.add_element("rectangle", bounds=[482, yy - 14, 946, yy + 22], fill="#192038", stroke=col, width=1.1)
        doc.add_element("text", position=[494, yy + 8], text=f"{mv}: {desc}", size=10.5, stroke=col, width=1)

    return doc, {"concept": "chess", "title": "Artline Chessboard & Fencing Stage", "squares": 64}


def build_artline_spaceship_sector_plate() -> tuple[ArtlineDocument, dict[str, Any]]:
    """Concept 3: The Artline Research Spaceship Cockpit (Sector 07)."""
    doc = ArtlineDocument()
    _artline_frame(
        doc,
        title="Concept 3: Artline Spaceship Cockpit · Sector 07",
        subtitle="Artline Starbridge uniting Dorothy Brain, DeepMind AlphaFold & Proof Core",
        badge="SECTOR 07 · BRIDGE",
        accent=_CYAN,
    )

    # Curved starbridge canopy arch
    canopy = [[60, 210], [220, 124], [500, 108], [780, 124], [940, 210]]
    doc.add_element("path", points=canopy, closed=False, smooth=True, fill="none", stroke=_CYAN, width=2.8)
    doc.add_element("path", points=[[120, 232], [500, 138], [880, 232]], closed=False, smooth=True, fill="none", stroke="#3d5c99", width=1.4)

    # Center Viewport: Dorothy MNI152 Brain Hologram
    doc.add_element("rectangle", bounds=[326, 174, 674, 496], fill="#101830", stroke=_CYAN, width=2.2)
    doc.add_element("text", position=[360, 198], text="CENTER VIEWPORT · DOROTHY MNI152", size=12, stroke=_CYAN, width=1)
    _draw_artline_brain(doc, 500.0, 344.0, scale=0.88)
    doc.add_element("text", position=[362, 476], text="112,001 verts · 135 Books Local · 0 Cloud", size=10.5, stroke=_MINT, width=1)

    # Left Console Bay: Google DeepMind AlphaFold / AlphaMissense Radar
    doc.add_element("rectangle", bounds=[36, 224, 304, 520], fill=_CARD, stroke=_BLUE, width=2.0)
    doc.add_element("text", position=[52, 248], text="PORT BAY · DEEPMIND RADAR", size=11.5, stroke=_BLUE, width=1)
    for r_rad in (78, 54, 30):
        doc.add_element("ellipse", center=[170, 366], radii=[r_rad, r_rad], fill="none", stroke="#35528a", width=1.2)
    doc.add_element("line", points=[[92, 366], [248, 366]], stroke="#35528a", width=1.0)
    doc.add_element("line", points=[[170, 288], [170, 444]], stroke="#35528a", width=1.0)
    # Radar blips for real targets
    for bx, by, lbl, col in [(144, 336, "H3", _RUBY), (204, 344, "CLPP", _CYAN), (186, 404, "IDH1", _MINT), (128, 392, "EZH2", _AMBER)]:
        doc.add_element("ellipse", center=[bx, by], radii=[6, 6], fill=col, stroke=_CREAM, width=1)
        doc.add_element("text", position=[bx + 9, by + 4], text=lbl, size=9.5, stroke=col, width=1)
    doc.add_element("text", position=[52, 476], text="8 Targets Live · 78,432 Variants", size=10.2, stroke=_CREAM, width=1)
    doc.add_element("text", position=[52, 498], text="AF-v6 Mean pLDDT: 80.87", size=10.2, stroke=_CYAN, width=1)

    # Right Console Bay: Bulb Idea Beacon & SymPy/Z3 Proof Thrusters
    doc.add_element("rectangle", bounds=[696, 224, 964, 520], fill=_CARD, stroke=_AMBER, width=2.0)
    doc.add_element("text", position=[712, 248], text="STARBOARD · IDEA & PROOF", size=11.5, stroke=_AMBER, width=1)
    _draw_artline_bulb(doc, 830.0, 336.0, scale=0.72)
    doc.add_element("text", position=[716, 412], text="SymPy Proof Core:  ONLINE", size=10.8, stroke=_MINT, width=1)
    doc.add_element("text", position=[716, 436], text="Z3 Formal Guard:   ONLINE", size=10.8, stroke=_MINT, width=1)
    doc.add_element("text", position=[716, 460], text="Qwen2.5-3B :8080:  LIVE", size=10.8, stroke=_CYAN, width=1)
    doc.add_element("text", position=[716, 484], text="Zoe-ELIZA :8765:   LIVE", size=10.8, stroke=_CYAN, width=1)
    doc.add_element("text", position=[716, 506], text="Draft Queue: 3 Inspectable", size=10.5, stroke=_AMBER, width=1)

    # Lower Helm Strip: Artline Control Gauges
    doc.add_element("rectangle", bounds=[36, 538, 964, 636], fill=_CARD, stroke=_MAGENTA, width=1.8)
    gauges = [
        ("KLOSTER A_tau", "0.08 LOCK", _CYAN),
        ("QUORUM D_K", "0.0047 OK", _MINT),
        ("BLACKBOARD", "45 SEALED", _BLUE),
        ("SDK HOOKS", "ACTIVE", _AMBER),
        ("EXT ACTIONS", "0 (SAFE)", _RUBY),
    ]
    for idx, (k, v, col) in enumerate(gauges):
        x0 = 54 + idx * 182
        doc.add_element("rectangle", bounds=[x0, 554, x0 + 166, 620], fill="#192038", stroke=col, width=1.4)
        doc.add_element("text", position=[x0 + 14, 578], text=k, size=10.0, stroke=_SLATE, width=1)
        doc.add_element("text", position=[x0 + 14, 604], text=v, size=13.0, stroke=col, width=1)

    return doc, {"concept": "sector", "title": "Artline Spaceship Cockpit Sector 07", "bays": 4}


def build_artline_mondo_playground_plate() -> tuple[ArtlineDocument, dict[str, Any]]:
    """Concept 4: The 'Mondo' Freeform Artline Playground & Creative Pinboard."""
    doc = ArtlineDocument()
    _artline_frame(
        doc,
        title="Concept 4: 'Mondo' Artline Playground & Pinboard",
        subtitle="1990 Digital Research Artline blend waves + freeform visual pinboard",
        badge="MODE: MONDO STUDIO",
        accent=_AMBER,
    )

    # Signature Artline 2.0 geometric blend ribbon sweeping diagonally across canvas
    poly_a = [[56, 588], [132, 540], [186, 594], [110, 622]]
    poly_b = [[816, 134], [910, 120], [946, 184], [852, 198]]
    steps = blend_polygons(poly_a, poly_b, steps=7)
    ribbon_cols = [_MAGENTA, _RUBY, _AMBER, _MINT, _CYAN, _BLUE, _MAGENTA, _PINK, _CREAM]
    for idx, poly in enumerate(steps):
        doc.add_element("path", points=poly, closed=True, smooth=False, fill="none", stroke=ribbon_cols[idx % len(ribbon_cols)], width=1.6)

    # Pinboard Card 1 (Top-Left): Brain Sketch Card
    doc.add_element("rectangle", bounds=[44, 120, 356, 366], fill=_CARD, stroke=_PINK, width=2.2)
    doc.add_element("ellipse", center=[200, 126], radii=[8, 8], fill=_RUBY, stroke=_CREAM, width=1.5)
    doc.add_element("text", position=[60, 152], text="PIN 01 · BRAIN MORPH", size=12, stroke=_PINK, width=1)
    _draw_artline_brain(doc, 200.0, 260.0, scale=0.66)

    # Pinboard Card 2 (Center-Top): Glowing Idea Bulb Card
    doc.add_element("rectangle", bounds=[386, 146, 650, 376], fill=_CARD, stroke=_AMBER, width=2.2)
    doc.add_element("ellipse", center=[518, 152], radii=[8, 8], fill=_AMBER, stroke=_CREAM, width=1.5)
    doc.add_element("text", position=[404, 178], text="PIN 02 · IDEA SPARK", size=12, stroke=_AMBER, width=1)
    _draw_artline_bulb(doc, 518.0, 268.0, scale=0.78)
    doc.add_element("text", position=[406, 356], text="Click Bulb -> Scratchpad", size=10.5, stroke=_CREAM, width=1)

    # Pinboard Card 3 (Top-Right): Retro GEM Vector Palette & Tool Dock
    doc.add_element("rectangle", bounds=[680, 122, 956, 366], fill=_CARD, stroke=_CYAN, width=2.2)
    doc.add_element("ellipse", center=[818, 128], radii=[8, 8], fill=_CYAN, stroke=_CREAM, width=1.5)
    doc.add_element("text", position=[696, 154], text="PIN 03 · ARTLINE TOOLS", size=12, stroke=_CYAN, width=1)
    tools = [
        ("Bézier Pen", _PINK),
        ("Blend Wave", _AMBER),
        ("Mirror Axis", _MINT),
        ("State Morph", _CYAN),
        ("Export .GEM", _BLUE),
    ]
    for ti, (tn, tc) in enumerate(tools):
        ty = 180 + ti * 34
        doc.add_element("rectangle", bounds=[698, ty, 938, ty + 26], fill="#1a223c", stroke=tc, width=1.2)
        doc.add_element("text", position=[714, ty + 18], text=f"[ {tn} ]", size=10.5, stroke=tc, width=1)

    # Pinboard Card 4 (Bottom-Left): Freeform Sticky Notes
    doc.add_element("rectangle", bounds=[116, 404, 520, 624], fill="#1f1c36", stroke=_MINT, width=2.0)
    doc.add_element("ellipse", center=[318, 410], radii=[8, 8], fill=_MINT, stroke=_CREAM, width=1.5)
    doc.add_element("text", position=[136, 438], text="PIN 04 · VISUAL BRAINSTORM NOTES", size=12, stroke=_MINT, width=1)
    doc.add_element("text", position=[136, 470], text="• Swap visual avatar cleanly by active module", size=11, stroke=_CREAM, width=1)
    doc.add_element("text", position=[136, 498], text="• Export every sketch to .SVG + .PNG + .GEM VDI", size=11, stroke=_CREAM, width=1)
    doc.add_element("text", position=[136, 526], text="• Keep Drafts Drawer 100% visible & editable", size=11, stroke=_CREAM, width=1)
    doc.add_element("text", position=[136, 554], text="• Toggle Quiet Mode anytime for focus sessions", size=11, stroke=_AMBER, width=1)
    doc.add_element("text", position=[136, 594], text="0 GPU · 0 Cloud Tokens · Pure Vector Math", size=10.5, stroke=_CYAN, width=1)

    # Pinboard Card 5 (Bottom-Right): Linked Research Portals
    doc.add_element("rectangle", bounds=[552, 404, 956, 624], fill="#1a2138", stroke=_MAGENTA, width=2.0)
    doc.add_element("ellipse", center=[754, 410], radii=[8, 8], fill=_MAGENTA, stroke=_CREAM, width=1.5)
    doc.add_element("text", position=[572, 438], text="PIN 05 · CONNECTED ZOE SECTORS", size=12, stroke=_MAGENTA, width=1)
    portals = [
        ("Dorothy 3D Brain Observatory", _PINK),
        ("Google DeepMind AlphaFold v6", _BLUE),
        ("Counterpoint Chairs & Quorum", _MINT),
        ("Digital Research GEM / Artline", _AMBER),
    ]
    for pi, (pn, pc) in enumerate(portals):
        py = 468 + pi * 36
        doc.add_element("rectangle", bounds=[572, py - 14, 936, py + 14], fill=_BG, stroke=pc, width=1.2)
        doc.add_element("text", position=[586, py + 5], text=f"-> {pn}", size=10.8, stroke=pc, width=1)

    return doc, {"concept": "mondo", "title": "Mondo Artline Playground & Pinboard", "pins": 5}


BRAINSTORM_CONCEPTS: dict[str, Any] = {
    "desk": build_artline_brainstorm_desk_plate,
    "chess": build_artline_chess_fencing_plate,
    "sector": build_artline_spaceship_sector_plate,
    "mondo": build_artline_mondo_playground_plate,
}


def export_brainstorm_plate(
    concept: str,
    *,
    out_dir: str | Path,
    formats: Sequence[str] = ("svg", "png", "gem"),
) -> dict[str, Any]:
    """Build and export one Artline Brainstorming Studio concept plate (.svg, .png, .gem)."""
    key = (concept or "desk").strip().lower()
    if key not in BRAINSTORM_CONCEPTS:
        raise ValueError(f"Unknown concept {concept!r}. Choose from: {sorted(BRAINSTORM_CONCEPTS)}")
    doc, meta = BRAINSTORM_CONCEPTS[key]()
    dest = Path(out_dir).expanduser().resolve()
    dest.mkdir(parents=True, exist_ok=True)

    paths: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for ext in formats:
        target = dest / f"artline_brainstorm_{key}.{ext}"
        if target.exists():
            target.unlink()
        doc.export(target, kind=ext)
        paths[ext] = str(target)
        sizes[ext] = target.stat().st_size

    return {
        "contract": ARTLINE_BRAINSTORM_CONTRACT,
        "concept": key,
        "title": meta["title"],
        "elements": len(doc.elements),
        "paths": paths,
        "sizes_bytes": sizes,
        "meta": meta,
        "constitutional": dict(CONSTITUTIONAL_FLAGS),
    }


def export_all_brainstorm_concepts(out_dir: str | Path) -> list[dict[str, Any]]:
    """Export all 4 Artline Brainstorming Studio concepts (.svg, .png, .gem)."""
    return [export_brainstorm_plate(key, out_dir=out_dir) for key in ("desk", "chess", "sector", "mondo")]


def render_concept_svg_bytes(concept: str = "desk") -> bytes:
    """Render one Artline Brainstorming concept plate directly to UTF-8 SVG bytes."""
    import tempfile

    key = (concept or "desk").strip().lower()
    if key not in BRAINSTORM_CONCEPTS:
        key = "desk"
    doc, _meta = BRAINSTORM_CONCEPTS[key]()
    with tempfile.TemporaryDirectory(prefix="zoe_artline_svg_") as td:
        p = Path(td) / f"{key}.svg"
        doc.export(p, kind="svg")
        return p.read_bytes()


def render_artline_studio_html() -> bytes:
    """HTTP route renderer for /artline on the live Zoe-ELIZA :8765 Web Studio."""
    states_json = json.dumps(
        [
            {"id": k, "desc": STATE_DESCRIPTIONS[k]}
            for k in ("ruby", "brain", "bulb", "helix", "chess")
            if k in STATE_DESCRIPTIONS
        ],
        ensure_ascii=False,
    )
    html = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Zoe Artline 2.0 Brainstorm Studio — Live GEM Vector Desk</title>
<style>
  * {{ box-sizing: border-box; font-family: "DejaVu Sans", system-ui, sans-serif; }}
  body {{ margin: 0; background: #0b0d18; color: #f0f4fc; min-height: 100vh; display: flex; flex-direction: column; }}
  header {{ background: #141a2e; border-bottom: 2px solid #ff85b3; padding: 12px 20px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-size: 17px; color: #5ce1e6; }}
  .navlinks {{ display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }}
  .navlinks a {{ text-decoration: none; font-size: 12px; padding: 5px 10px; border-radius: 6px; border: 1px solid #3c4d7a; color: #cbd5e1; background: #18213d; font-weight: 600; }}
  .navlinks a:hover {{ border-color: #ff85b3; color: #ff85b3; }}
  .layout {{ display: grid; grid-template-columns: 1.55fr 1fr; gap: 16px; padding: 16px 20px; flex: 1; }}
  @media (max-width: 1020px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: #12182c; border: 1.5px solid #2b385c; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }}
  .panel h2 {{ margin: 0; font-size: 12.5px; text-transform: uppercase; letter-spacing: 0.7px; color: #f8cc30; }}
  .tabs {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  button {{ background: #1b2442; color: #f0f4fc; border: 1.5px solid #3c4f7f; border-radius: 7px; padding: 6px 12px; cursor: pointer; font-weight: 600; font-size: 12px; }}
  button:hover {{ filter: brightness(1.18); }}
  button.active {{ border-color: #5ce1e6; color: #5ce1e6; background: #102a38; }}
  #plateFrame {{ width: 100%; border-radius: 8px; border: 1.5px solid #30426e; background: #090c16; min-height: 420px; display: flex; align-items: center; justify-content: center; overflow: hidden; }}
  #plateFrame img {{ width: 100%; height: auto; display: block; }}
  .state-card {{ background: #0e1324; border: 1px solid #2d3c63; border-radius: 7px; padding: 9px 11px; margin-bottom: 6px; cursor: pointer; }}
  .state-card.sel {{ border-color: #f8cc30; background: #1a213b; }}
  .draft {{ background: #0e1324; border-left: 3px solid #52e5a8; border-radius: 6px; padding: 8px 10px; margin-bottom: 6px; font-size: 12px; }}
  input {{ background: #0d1222; color: #f0f4fc; border: 1.5px solid #354672; border-radius: 7px; padding: 7px 10px; font-size: 12.5px; width: 100%; }}
  footer {{ padding: 8px 20px; background: #101424; border-top: 1px solid #263354; font-size: 11px; color: #94a3c8; }}
</style>
</head>
<body>
<header>
  <h1>🎨 Zoe Artline 2.0 Brainstorm Studio · Live GEM Vector Workbench</h1>
  <div class="navlinks">
    <a href="/">← Studio</a>
    <a href="/physics" style="border-color:#ff85b3;color:#ff85b3;">✺ Physics Room</a>
    <a href="/duodecimal" style="border-color:#f8cc30;color:#f8cc30;">❖ ADC-12 Catalog</a>
    <a href="/forge" style="border-color:#ac82ff;color:#ac82ff;">⚒ Forge</a>
    <a href="/orbit" style="border-color:#5ce1e6;color:#5ce1e6;">✦ Orbit</a>
  </div>
</header>
<div class="layout">
  <section class="panel">
    <h2>Live Compiled Artline 2.0 Concept Plates (0 GPU · Pure Vector SVG)</h2>
    <div class="tabs">
      <button id="t_desk" class="active" onclick="loadConcept('desk')">1. Brainstorming Desk</button>
      <button id="t_chess" onclick="loadConcept('chess')">2. Chess / Fencing Stage</button>
      <button id="t_sector" onclick="loadConcept('sector')">3. Spaceship Sector</button>
      <button id="t_mondo" onclick="loadConcept('mondo')">4. Mondo Playground</button>
    </div>
    <div id="plateFrame"><img id="plateImg" src="/api/artline/desk.svg" alt="Artline 2.0 Vector Plate" /></div>
  </section>
  <section class="panel">
    <h2>Deterministic Visual State Indicators (Glass-Box)</h2>
    <div id="states"></div>
    <h2>Glass-Box Drafts Drawer (Human-Reviewed Only)</h2>
    <div style="display:flex;gap:6px;">
      <input id="draftIn" type="text" placeholder="Queue a new transparent brainstorm draft..." />
      <button style="border-color:#52e5a8;color:#52e5a8;white-space:nowrap;" onclick="addDraft()">+ Queue</button>
    </div>
    <div id="drafts"></div>
  </section>
</div>
<footer>Digital Research Artline 2.0 Studio · 0 Cloud Tokens · external_actions=0 · sentience_claimed=False · clinical_action_authorized=False</footer>
<script>
const STATES = {states_json};
let activeState = 'brain';
const drafts = [
  {{ title: 'ADC-12 Base-12 Dewey Shorthand', status: 'promoted', badge: '[100₁₂ · Z · ✺]' }},
  {{ title: 'Optional-Physics Safe Shatter Room', status: 'promoted', badge: '[E00₁₂ · , · ✌]' }},
  {{ title: 'Cross-link AlphaFold v6 CLPP plate', status: 'unverified_draft', badge: '[300₁₂ · S · ✶]' }},
];
function loadConcept(key) {{
  ['desk','chess','sector','mondo'].forEach(k => {{
    document.getElementById('t_' + k).classList.toggle('active', k === key);
  }});
  document.getElementById('plateImg').src = '/api/artline/' + key + '.svg?t=' + Date.now();
}}
function renderStates() {{
  document.getElementById('states').innerHTML = STATES.map(s => `
    <div class="state-card ${{s.id===activeState?'sel':''}}" onclick="activeState='${{s.id}}';renderStates();">
      <b style="color:#5ce1e6;text-transform:uppercase;">${{s.id}}</b>
      <div style="font-size:11.5px;color:#94a3c8;margin-top:2px;">${{s.desc}}</div>
    </div>`).join('');
}}
function renderDrafts() {{
  document.getElementById('drafts').innerHTML = drafts.map(d => `
    <div class="draft">
      <div style="color:#f8cc30;font-family:monospace;font-size:11px;">${{d.badge}} · ${{d.status}}</div>
      <div style="margin-top:2px;">${{d.title}}</div>
    </div>`).join('');
}}
function addDraft() {{
  const el = document.getElementById('draftIn');
  const txt = el.value.trim();
  if (!txt) return;
  drafts.unshift({{ title: txt, status: 'unverified_draft', badge: '[700₁₂ · o · ❏]' }});
  el.value = '';
  renderDrafts();
}}
renderStates();
renderDrafts();
</script>
</body>
</html>
"""
    return html.encode("utf-8")


__all__ = [
    "ARTLINE_BRAINSTORM_CONTRACT",
    "BRAINSTORM_CONCEPTS",
    "BRAIN_PIXELS",
    "BULB_PIXELS",
    "CHESS_PIXELS",
    "CONSTITUTIONAL_FLAGS",
    "HELIX_PIXELS",
    "STATE_DESCRIPTIONS",
    "STATE_PALETTE",
    "STATE_SPRITE_MAP",
    "DraftIdeaEntry",
    "IdeaScratchpadDrawer",
    "VisualStateSnapshot",
    "build_artline_brainstorm_desk_plate",
    "build_artline_chess_fencing_plate",
    "build_artline_mondo_playground_plate",
    "build_artline_spaceship_sector_plate",
    "export_all_brainstorm_concepts",
    "export_brainstorm_plate",
    "render_artline_studio_html",
    "render_concept_svg_bytes",
    "render_state_sprite_png",
    "render_state_sprite_terminal",
    "resolve_visual_state",
]
