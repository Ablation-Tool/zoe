"""Zoe Artline 2.0 Page A-2 Wombats Tapback Reactions & Optional-Physics Sandbox Room.

100% original clean-room Python + NumPy + PIL + Artline/GEM VDI + offline HTML5 Canvas.
Inspired by Digital Research Artline 2.0 Utilities Guide (Aug 1990, pp. A-2/A-3):
  - Font ID 131 'Wombats' dingbat symbols as tactile GEM-native tapback reactions
    (including Z=90 ✺, o=111 ❏, e=101 ❄, N=78 ★, I=73 ☆, 3=51 ✓, 5=53 ✕, u=117 ◆, _=95 ✿).
  - Parametric Artline rotated-ellipse spirograph rosette vector builder (.SVG/.PNG/.GEM).
  - Optional-Physics Sandbox Room (`OFF` relaxed freeform / `ZERO_G` drift / `GRAVITY` break-stuff)
    where blocks, rosettes, and Wombat stars can be tossed, collided, shattered into shards,
    and reset cleanly with zero risk to any real files (`external_actions = 0`).

Constitutional Invariants (`CONSTITUTION.md`):
  clean_room_original = True · external_actions = 0 · sentience_claimed = False
  clinical_action_authorized = False · cure_claim = False · tokens_used = 0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Literal, Sequence

import numpy as np
from PIL import Image, ImageDraw

from .artline import ArtlineDocument

WOMBATS_PHYSICS_CONTRACT = "zoe-wombats-physics-room/v1"

CONSTITUTIONAL_FLAGS: dict[str, Any] = {
    "clean_room_original": True,
    "external_actions": 0,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "tokens_used": 0,
    "attribution": "Nicholas Michael Kloster; Inspired by Digital Research Artline 2.0 (Aug 1990, p. A-2)",
}

PhysicsMode = Literal["off", "zero_g", "gravity"]


# ---------------------------------------------------------------------------
# 1. Authentic 1990 Digital Research Artline Page A-2 Wombats Tapback Map
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WombatReactionSpec:
    decimal_code: int
    ascii_key: str
    symbol_col: str
    wombat_glyph: str
    label: str
    action_id: str
    color_hex: str


PAGE_A2_WOMBATS_REACTIONS: tuple[WombatReactionSpec, ...] = (
    WombatReactionSpec(90, "Z", "Z", "✺", "Sunburst Spark", "highlight_spark", "#f8cc30"),
    WombatReactionSpec(111, "o", "o", "❏", "Shadow Card", "save_to_drafts", "#5ce1e6"),
    WombatReactionSpec(101, "e", "ε", "❄", "Snowflake Verify", "freeze_and_verify", "#4f8ef7"),
    WombatReactionSpec(78, "N", "N", "★", "Solid Star", "approve_favorite", "#f35670"),
    WombatReactionSpec(73, "I", "I", "☆", "Outline Star", "bookmark_pin", "#ff85b3"),
    WombatReactionSpec(51, "3", "3", "✓", "Check Approve", "confirm_proceed", "#52e5a8"),
    WombatReactionSpec(53, "5", "5", "✕", "Cross Dismiss", "dismiss_snooze", "#94a3c8"),
    WombatReactionSpec(42, "*", "*", "☛", "Point Focus", "focus_highlight", "#f8cc30"),
    WombatReactionSpec(44, ",", ",", "✌", "Peace Relax", "toggle_freeform", "#52e5a8"),
    WombatReactionSpec(46, ".", ".", "✎", "Pencil Sketch", "open_artline_draft", "#ff85b3"),
    WombatReactionSpec(95, "_", "_", "✿", "Artline Flower", "love_pin", "#d93b96"),
    WombatReactionSpec(117, "u", "υ", "◆", "Diamond Seal", "seal_blackboard", "#5ce1e6"),
    WombatReactionSpec(118, "v", "ϖ", "❖", "Faceted GEM", "export_gem_vdi", "#ac82ff"),
)

_WOMBAT_BY_LOOKUP: dict[str, WombatReactionSpec] = {}
for _w in PAGE_A2_WOMBATS_REACTIONS:
    _WOMBAT_BY_LOOKUP[str(_w.decimal_code)] = _w
    _WOMBAT_BY_LOOKUP[_w.ascii_key] = _w
    _WOMBAT_BY_LOOKUP[_w.wombat_glyph] = _w
    _WOMBAT_BY_LOOKUP[_w.action_id] = _w


def resolve_wombat_reaction(query: str | int) -> WombatReactionSpec:
    """Resolve a Page A-2 Wombat reaction by decimal code (e.g. 90), ASCII key ('Z'), or glyph ('✺')."""
    raw = str(query).strip()
    if raw in _WOMBAT_BY_LOOKUP:
        return _WOMBAT_BY_LOOKUP[raw]
    low = raw.lower()
    for spec in PAGE_A2_WOMBATS_REACTIONS:
        if spec.label.lower() == low or spec.action_id.lower() == low:
            return spec
    raise ValueError(f"Unknown Artline Page A-2 Wombat reaction {query!r}.")


@dataclass
class HighlightReactionRecord:
    reaction_id: str
    target_quote: str
    decimal_code: int
    ascii_key: str
    wombat_glyph: str
    action_id: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WombatsReactionBar:
    """Glass-box tapback reaction log using 1990 Artline Page A-2 Wombats."""

    def __init__(self) -> None:
        self._records: list[HighlightReactionRecord] = []

    def react(self, quote: str, reaction: str | int) -> HighlightReactionRecord:
        clean_q = (quote or "").strip()
        if not clean_q:
            raise ValueError("Highlighted quote must not be empty")
        spec = resolve_wombat_reaction(reaction)
        rid = f"wreact_{len(self._records) + 1:03d}"
        body = {
            "reaction_id": rid,
            "target_quote": clean_q,
            "decimal_code": spec.decimal_code,
            "ascii_key": spec.ascii_key,
            "wombat_glyph": spec.wombat_glyph,
            "action_id": spec.action_id,
        }
        digest = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        rec = HighlightReactionRecord(
            reaction_id=rid,
            target_quote=clean_q,
            decimal_code=spec.decimal_code,
            ascii_key=spec.ascii_key,
            wombat_glyph=spec.wombat_glyph,
            action_id=spec.action_id,
            receipt_sha256=digest,
        )
        self._records.append(rec)
        return rec

    def list_reactions(self) -> list[HighlightReactionRecord]:
        return list(self._records)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": WOMBATS_PHYSICS_CONTRACT,
            "count": len(self._records),
            "reactions": [r.to_dict() for r in self._records],
            "constitutional": dict(CONSTITUTIONAL_FLAGS),
        }


# ---------------------------------------------------------------------------
# 2. Artline Rotated-Ellipse Spirograph Rosette & Wombats Specimen Plate
# ---------------------------------------------------------------------------

def build_artline_rosette_wombats_plate(
    *,
    petals: int = 9,
) -> tuple[ArtlineDocument, dict[str, Any]]:
    """Build a crisp Artline 2.0 plate combining the 9-petal rotated ellipse rosette & Page A-2 Wombats."""
    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0b0d18", stroke="#0b0d18", width=1)
    doc.add_element("rectangle", bounds=[24, 18, 976, 682], fill="#101528", stroke="#ff85b3", width=1.8)
    doc.add_element("text", position=[42, 46], text="Artline 2.0 (Aug 1990) · Page A-2 Wombats & Rotated Ellipse Rosette", size=18.5, stroke="#ff85b3", width=1)
    doc.add_element("text", position=[42, 72], text="Authentic Font ID 131 tapback codes: Z=90 (Sunburst) · o=111 (Card) · e=101 (Snowflake) · N=78 (Star) · I=73 (Outline)", size=11, stroke="#94a3c8", width=1)

    # Left stage: Parametric 9-petal rotated ellipse rosette (inspired by Artline Utilities Guide!)
    doc.add_element("rectangle", bounds=[40, 96, 512, 626], fill="#141a2e", stroke="#5ce1e6", width=1.8)
    doc.add_element("text", position=[58, 122], text=f"ROTATED ELLIPSE ROSETTE ({petals} PETALS · PURE VECTOR)", size=11.2, stroke="#5ce1e6", width=1)

    cx, cy = 276.0, 372.0
    a_rad, b_rad = 104.0, 38.0
    orbit_r = 66.0
    petal_cols = ["#f35670", "#ff85b3", "#f8cc30", "#52e5a8", "#5ce1e6", "#4f8ef7", "#ac82ff", "#d93b96", "#f4ebd6"]

    for p in range(max(3, petals)):
        theta = (2.0 * math.pi * p) / float(petals)
        pcx = cx + math.cos(theta) * orbit_r
        pcy = cy + math.sin(theta) * orbit_r
        pts: list[list[float]] = []
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        for k in range(36):
            phi = (2.0 * math.pi * k) / 36.0
            lx = a_rad * math.cos(phi)
            ly = b_rad * math.sin(phi)
            gx = pcx + lx * cos_t - ly * sin_t
            gy = pcy + lx * sin_t + ly * cos_t
            pts.append([round(gx, 1), round(gy, 1)])
        doc.add_element(
            "path",
            points=pts,
            closed=True,
            smooth=True,
            fill="none",
            stroke=petal_cols[p % len(petal_cols)],
            width=2.6,
        )

    doc.add_element("ellipse", center=[cx, cy], radii=[14, 14], fill="#f8cc30", stroke="#f4ebd6", width=1.5)
    doc.add_element("text", position=[82, 606], text="Zero GPU · Exports natively to .SVG, .PNG & .GEM VDI", size=10.5, stroke="#94a3c8", width=1)

    # Right stage: Authentic Page A-2 Wombats Reaction Table
    doc.add_element("rectangle", bounds=[534, 96, 958, 626], fill="#141a2e", stroke="#f8cc30", width=1.8)
    doc.add_element("text", position=[552, 122], text="PAGE A-2 WOMBATS TAPBACK REACTION BAR", size=11.5, stroke="#f8cc30", width=1)

    for idx, spec in enumerate(PAGE_A2_WOMBATS_REACTIONS[:10]):
        y0 = 140 + idx * 47
        doc.add_element("rectangle", bounds=[550, y0, 942, y0 + 38], fill="#19213a", stroke=spec.color_hex, width=1.2)
        doc.add_element("text", position=[562, y0 + 25], text=f"{spec.decimal_code:3d}  [{spec.ascii_key}]", size=11.5, stroke="#94a3c8", width=1)
        doc.add_element("text", position=[638, y0 + 25], text=f"{spec.label:<16}", size=11.5, stroke=spec.color_hex, width=1)
        doc.add_element("text", position=[796, y0 + 25], text=spec.action_id, size=10.2, stroke="#f4ebd6", width=1)

    doc.add_element("text", position=[42, 662], text="Z(90) + o(111) + e(101) = Zoe Wombats  ·  N(78) + I(73) = Nick Stars  ·  external_actions=0", size=10.5, stroke="#52e5a8", width=1)
    return doc, {"petals": petals, "wombats_mapped": len(PAGE_A2_WOMBATS_REACTIONS)}


# ---------------------------------------------------------------------------
# 3. Optional-Physics "Safely Break Stuff" Sandbox Room (OFF / ZERO-G / GRAVITY)
# ---------------------------------------------------------------------------

@dataclass
class SandboxBody:
    body_id: str
    kind: str  # "block" | "rosette" | "star" | "shard"
    x: float
    y: float
    vx: float
    vy: float
    radius: float
    angle: float
    ang_vel: float
    color: tuple[int, int, int]
    label: str = ""
    shattered: bool = False


class PhysicsSandboxRoom:
    """Clean-room 2D Optional-Physics Sandbox where physics can be toggled OFF, ZERO_G, or GRAVITY."""

    def __init__(self, *, width: int = 640, height: int = 400, mode: PhysicsMode = "gravity") -> None:
        self.width = int(width)
        self.height = int(height)
        self.mode: PhysicsMode = mode
        self.bodies: list[SandboxBody] = []
        self.shatter_events: int = 0
        self.step_count: int = 0
        self.reset_tower_scene()

    def set_mode(self, mode: PhysicsMode) -> None:
        if mode not in ("off", "zero_g", "gravity"):
            raise ValueError(f"Unsupported physics mode: {mode!r}")
        self.mode = mode

    def reset_tower_scene(self) -> None:
        """Reset to a clean Artline glass-gem block tower + incoming Wombat Star projectile."""
        self.bodies = []
        self.shatter_events = 0
        self.step_count = 0
        palette = [
            (243, 86, 112),
            (255, 133, 179),
            (92, 225, 230),
            (82, 229, 168),
            (79, 142, 247),
            (172, 130, 255),
        ]
        # Build a clean 3x4 Artline crystal tower on the right side
        idx = 0
        for row in range(4):
            for col in range(3):
                bx = 390.0 + col * 56.0
                by = self.height - 40.0 - row * 54.0
                self.bodies.append(
                    SandboxBody(
                        body_id=f"blk_{idx}",
                        kind="block",
                        x=bx,
                        y=by,
                        vx=0.0,
                        vy=0.0,
                        radius=24.0,
                        angle=0.0,
                        ang_vel=0.0,
                        color=palette[idx % len(palette)],
                        label="❏",
                    )
                )
                idx += 1
        # Add a floating Artline rosette on top of the tower
        self.bodies.append(
            SandboxBody(
                body_id="rosette_top",
                kind="rosette",
                x=446.0,
                y=self.height - 266.0,
                vx=0.0,
                vy=0.0,
                radius=28.0,
                angle=0.0,
                ang_vel=0.04,
                color=(248, 204, 48),
                label="✺",
            )
        )
        # Incoming high-energy Wombat Star launcher from the left!
        self.bodies.append(
            SandboxBody(
                body_id="wombat_star",
                kind="star",
                x=78.0,
                y=210.0,
                vx=360.0,
                vy=-42.0,
                radius=22.0,
                angle=0.0,
                ang_vel=0.22,
                color=(248, 204, 48),
                label="★",
            )
        )

    def shatter_body(self, body: SandboxBody, *, n_shards: int = 5) -> list[SandboxBody]:
        """Split a breakable block/rosette safely into spinning triangular vector shards."""
        body.shattered = True
        self.shatter_events += 1
        shards: list[SandboxBody] = []
        for i in range(n_shards):
            ang = (2.0 * math.pi * i) / float(n_shards) + (self.step_count * 0.17)
            spd = 140.0 + (i % 3) * 65.0
            shards.append(
                SandboxBody(
                    body_id=f"{body.body_id}_sh{i}",
                    kind="shard",
                    x=body.x + math.cos(ang) * 8.0,
                    y=body.y + math.sin(ang) * 8.0,
                    vx=body.vx * 0.45 + math.cos(ang) * spd,
                    vy=body.vy * 0.45 + math.sin(ang) * spd - 70.0,
                    radius=max(7.0, body.radius * 0.42),
                    angle=ang,
                    ang_vel=(0.35 if i % 2 == 0 else -0.40),
                    color=body.color,
                )
            )
        return shards

    def step(self, dt: float = 1.0 / 30.0) -> None:
        """Advance simulation by `dt`. When `mode == 'off'`, bodies remain completely still!"""
        self.step_count += 1
        if self.mode == "off":
            return

        gravity = 420.0 if self.mode == "gravity" else 0.0
        restitution = 0.72
        new_shards: list[SandboxBody] = []

        for b in self.bodies:
            if b.shattered:
                continue
            b.vy += gravity * dt
            b.x += b.vx * dt
            b.y += b.vy * dt
            b.angle += b.ang_vel

            # Floor / ceiling / wall collisions
            if b.y + b.radius > self.height - 14.0:
                b.y = self.height - 14.0 - b.radius
                b.vy = -abs(b.vy) * restitution
                b.vx *= 0.94
                if abs(b.vy) < 12.0:
                    b.vy = 0.0
            elif b.y - b.radius < 14.0:
                b.y = 14.0 + b.radius
                b.vy = abs(b.vy) * restitution

            if b.x - b.radius < 14.0:
                b.x = 14.0 + b.radius
                b.vx = abs(b.vx) * restitution
            elif b.x + b.radius > self.width - 14.0:
                b.x = self.width - 14.0 - b.radius
                b.vx = -abs(b.vx) * restitution

        # Pairwise collision + break-stuff shatter on high-impulse impact!
        active = [b for b in self.bodies if not b.shattered]
        for i in range(len(active)):
            a = active[i]
            if a.shattered:
                continue
            for j in range(i + 1, len(active)):
                b = active[j]
                if b.shattered:
                    continue
                dx = b.x - a.x
                dy = b.y - a.y
                dist = math.hypot(dx, dy)
                min_d = a.radius + b.radius
                if 1e-6 < dist < min_d:
                    nx, ny = dx / dist, dy / dist
                    overlap = (min_d - dist) * 0.5
                    a.x -= nx * overlap
                    a.y -= ny * overlap
                    b.x += nx * overlap
                    b.y += ny * overlap
                    rel_v = (b.vx - a.vx) * nx + (b.vy - a.vy) * ny
                    if rel_v < 0:
                        imp = -(1.0 + restitution) * rel_v * 0.5
                        a.vx -= imp * nx
                        a.vy -= imp * ny
                        b.vx += imp * nx
                        b.vy += imp * ny
                        # High-speed star hitting a block shatters it safely into shards!
                        if abs(rel_v) > 150.0:
                            if a.kind == "star" and b.kind in ("block", "rosette"):
                                new_shards.extend(self.shatter_body(b, n_shards=5))
                            elif b.kind == "star" and a.kind in ("block", "rosette"):
                                new_shards.extend(self.shatter_body(a, n_shards=5))

        if new_shards:
            self.bodies = [b for b in self.bodies if not b.shattered] + new_shards

    def render_frame(self) -> Image.Image:
        img = Image.new("RGB", (self.width, self.height), (11, 13, 24))
        dr = ImageDraw.Draw(img)
        # Artline studio grid
        for gx in range(32, self.width, 32):
            dr.line([(gx, 14), (gx, self.height - 14)], fill=(22, 28, 48), width=1)
        for gy in range(32, self.height, 32):
            dr.line([(14, gy), (self.width - 14, gy)], fill=(22, 28, 48), width=1)
        dr.rectangle([12, 12, self.width - 12, self.height - 12], outline=(92, 225, 230), width=2)

        for b in self.bodies:
            if b.shattered:
                continue
            r = b.radius
            fill_c = tuple(int(18 + c * 0.34) for c in b.color)
            if b.kind == "block":
                # Rotated square block
                corners = []
                for k in range(4):
                    a = b.angle + math.pi * 0.25 + k * math.pi * 0.5
                    corners.append((b.x + math.cos(a) * r * 1.25, b.y + math.sin(a) * r * 1.25))
                dr.polygon(corners, fill=fill_c, outline=b.color, width=2)
            elif b.kind == "star":
                pts = []
                for k in range(10):
                    rad = r if k % 2 == 0 else r * 0.45
                    a = b.angle + k * math.pi / 5.0
                    pts.append((b.x + math.cos(a) * rad, b.y + math.sin(a) * rad))
                dr.polygon(pts, fill=b.color, outline=(255, 250, 220), width=2)
            elif b.kind == "rosette":
                for p in range(6):
                    ang = b.angle + p * math.pi / 3.0
                    px = b.x + math.cos(ang) * r * 0.45
                    py = b.y + math.sin(ang) * r * 0.45
                    dr.ellipse([px - r * 0.48, py - r * 0.48, px + r * 0.48, py + r * 0.48], outline=b.color, width=2)
            else:
                # Spinning shard triangle
                tri = []
                for k in range(3):
                    a = b.angle + k * (2.0 * math.pi / 3.0)
                    tri.append((b.x + math.cos(a) * r, b.y + math.sin(a) * r))
                dr.polygon(tri, fill=b.color, outline=(244, 235, 214), width=1)

        hud = f"OPTIONAL-PHYSICS ROOM | MODE={self.mode.upper()} | BODIES={len(self.bodies)} | SHATTERS={self.shatter_events} | SAFE (ext=0)"
        dr.text((22, 18), hud, fill=(248, 204, 48))
        return img


def render_physics_shatter_gif(
    out_gif: str | Path,
    keyframe_dir: str | Path | None = None,
    *,
    frames: int = 42,
) -> dict[str, Any]:
    """Simulate and export an animated .GIF of the Optional-Physics Room smashing & shattering a tower."""
    room = PhysicsSandboxRoom(width=640, height=400, mode="gravity")
    imgs: list[Image.Image] = []
    saved_keys: list[str] = []
    key_indices = {0, 14, 34}

    for f in range(frames):
        im = room.render_frame()
        imgs.append(im)
        if keyframe_dir is not None and f in key_indices:
            kp = Path(keyframe_dir) / f"physics_key_{f:02d}.png"
            kp.parent.mkdir(parents=True, exist_ok=True)
            im.save(str(kp))
            saved_keys.append(str(kp))
        room.step(dt=1.0 / 24.0)

    gif_path = Path(out_gif)
    gif_path.parent.mkdir(parents=True, exist_ok=True)
    imgs[0].save(str(gif_path), save_all=True, append_images=imgs[1:], duration=65, loop=0)
    return {
        "contract": WOMBATS_PHYSICS_CONTRACT,
        "frames": frames,
        "shatter_events": room.shatter_events,
        "final_bodies": len(room.bodies),
        "gif_path": str(gif_path),
        "gif_bytes": gif_path.stat().st_size,
        "keyframes": saved_keys,
        "constitutional": dict(CONSTITUTIONAL_FLAGS),
    }


def build_interactive_physics_room_html_str() -> str:
    """Return HTML string for the 100% offline Optional-Physics Sandbox + Page A-2 Wombats Studio."""
    wombat_buttons = "".join(
        f'<button class="wbtn" style="border-color:{w.color_hex};color:{w.color_hex}" '
        f'title="Artline p.A-2 Dec {w.decimal_code} ({w.ascii_key}) -> {w.action_id}" '
        f'onclick="stampWombat(\'{w.wombat_glyph}\',\'{w.color_hex}\',\'{w.label}\',\'{w.action_id}\')">'
        f'{w.wombat_glyph} <span>{w.ascii_key}</span></button>'
        for w in PAGE_A2_WOMBATS_REACTIONS[:9]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Zoe Artline Optional-Physics Room & Page A-2 Wombats Studio</title>
<style>
  * {{ box-sizing: border-box; font-family: "DejaVu Sans", system-ui, sans-serif; }}
  body {{ margin: 0; background: #0b0d18; color: #f0f4fc; display: flex; flex-direction: column; height: 100vh; }}
  header {{ display: flex; align-items: center; justify-content: space-between; padding: 10px 18px; background: #141a2e; border-bottom: 2px solid #f35670; gap: 10px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-size: 16px; color: #5ce1e6; letter-spacing: 0.4px; }}
  .navlinks {{ display: flex; gap: 6px; align-items: center; }}
  .navlinks a {{ text-decoration: none; font-size: 11.5px; padding: 4px 9px; border-radius: 6px; border: 1px solid #3c4d7a; color: #cbd5e1; background: #18213d; font-weight: 600; }}
  .navlinks a:hover {{ border-color: #5ce1e6; color: #5ce1e6; }}
  .controls {{ display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
  button {{ background: #1c2542; color: #f0f4fc; border: 1.5px solid #3c4d7a; border-radius: 6px; padding: 6px 11px; cursor: pointer; font-weight: 600; font-size: 12px; }}
  button:hover {{ filter: brightness(1.18); }}
  button.active {{ border-color: #52e5a8; color: #52e5a8; background: #13302b; }}
  .main {{ display: flex; flex: 1; overflow: hidden; }}
  #canvasWrap {{ flex: 1; position: relative; padding: 12px; display: flex; }}
  canvas {{ width: 100%; height: 100%; background: #0d1120; border: 2px solid #5ce1e6; border-radius: 10px; cursor: crosshair; }}
  aside {{ width: 320px; background: #12172a; border-left: 1.5px solid #2c395e; padding: 14px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; }}
  .panel {{ background: #182038; border: 1px solid #304068; border-radius: 8px; padding: 10px; }}
  .panel h2 {{ margin: 0 0 8px 0; font-size: 12px; color: #f8cc30; text-transform: uppercase; letter-spacing: 0.6px; }}
  .wgrid {{ display: flex; flex-wrap: wrap; gap: 6px; }}
  .wbtn {{ font-size: 15px; padding: 5px 9px; }}
  .wbtn span {{ font-size: 10px; opacity: 0.75; margin-left: 2px; }}
  .note {{ background: #101526; border: 1px solid #2b385c; border-radius: 6px; padding: 8px; margin-bottom: 6px; font-size: 12px; cursor: pointer; }}
  .note.sel {{ border-color: #f8cc30; }}
  .badges {{ margin-top: 5px; display: flex; gap: 5px; flex-wrap: wrap; }}
  .badge {{ font-size: 12px; padding: 1px 6px; border-radius: 10px; background: #1f2948; border: 1px solid #5ce1e6; }}
  footer {{ padding: 6px 18px; font-size: 11px; color: #94a3c8; background: #101424; border-top: 1px solid #283456; }}
</style>
</head>
<body>
<header>
  <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
    <h1>✦ Zoe Artline Optional-Physics Room &amp; Page A-2 Wombats Studio</h1>
    <div class="navlinks">
      <a href="/">← Studio</a>
      <a href="/artline">🎨 Artline</a>
      <a href="/duodecimal">❖ ADC-12</a>
      <a href="/forge" style="border-color:#ac82ff;color:#ac82ff;">⚒ Forge</a>
    </div>
  </div>
  <div class="controls">
    <button id="mOff" onclick="setMode('off')">Physics: OFF (Relaxed)</button>
    <button id="mZero" onclick="setMode('zero_g')">Zero-G Float</button>
    <button id="mGrav" class="active" onclick="setMode('gravity')">Gravity: BREAK STUFF</button>
    <button style="border-color:#f8cc30;color:#f8cc30" onclick="launchStar()">★ Launch Star</button>
    <button style="border-color:#ff85b3;color:#ff85b3" onclick="spawnRosette()">✺ Spawn Rosette</button>
    <button style="border-color:#f35670;color:#f35670" onclick="shatterAll()">💥 Shatter All</button>
    <button style="border-color:#52e5a8;color:#52e5a8" onclick="buildTower()">↺ Rebuild Tower</button>
  </div>
</header>
<div class="main">
  <div id="canvasWrap"><canvas id="room"></canvas></div>
  <aside>
    <div class="panel">
      <h2>Artline p. A-2 Wombats Reactions</h2>
      <div style="font-size:11px;color:#94a3c8;margin-bottom:8px;">Select a note below &amp; tap any 1990 Wombat glyph (also spawns it in the room!):</div>
      <div class="wgrid">{wombat_buttons}</div>
    </div>
    <div class="panel">
      <h2>Brainstorm Notes (Click to Highlight)</h2>
      <div id="notes"></div>
    </div>
    <div class="panel">
      <h2>Room Controls</h2>
      <div style="font-size:11px;color:#cbd5e1;line-height:1.5;">
        • <b>Click canvas</b>: spawn block / toss impulse<br/>
        • <b>Double-click any shape</b>: shatter it into shards<br/>
        • <b>Physics OFF</b>: peaceful freeform drawing<br/>
        • <b>100% offline &amp; safe</b>: zero files harmed (ext=0)
      </div>
    </div>
  </aside>
</div>
<footer>Digital Research Artline 2.0 (Aug 1990, p. A-2 Wombats) · 0 Cloud Tokens · external_actions=0 · sentience_claimed=False · clinical_action_authorized=False</footer>
<script>
const canvas = document.getElementById('room');
const ctx = canvas.getContext('2d');
let mode = 'gravity';
let bodies = [];
const palette = ['#f35670','#ff85b3','#5ce1e6','#52e5a8','#4f8ef7','#ac82ff','#f8cc30'];
let selectedNote = 0;
const notes = [
  {{ text: "Use 1990 Artline p. A-2 Wombats (Z=✺, o=❏, e=❄, N=★, I=☆) as tapback reactions.", badges: ["✺ Z", "★ N"] }},
  {{ text: "Optional Physics Room: switch OFF for calm Artline drawing or ON to safely smash towers.", badges: ["❏ o"] }},
  {{ text: "Cross-check AlphaFold v6 CLPP & H3K27M complexes via AF3 JSON builder.", badges: ["❄ e"] }},
];
function renderNotes() {{
  const el = document.getElementById('notes');
  el.innerHTML = notes.map((n, i) => `
    <div class="note ${{i===selectedNote?'sel':''}}" onclick="selectedNote=${{i}};renderNotes();">
      <div>${{n.text}}</div>
      <div class="badges">${{n.badges.map(b => `<span class="badge">${{b}}</span>`).join('')}}</div>
    </div>`).join('');
}}
function resize() {{
  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;
}}
window.addEventListener('resize', resize);
resize();

function setMode(m) {{
  mode = m;
  document.getElementById('mOff').classList.toggle('active', m==='off');
  document.getElementById('mZero').classList.toggle('active', m==='zero_g');
  document.getElementById('mGrav').classList.toggle('active', m==='gravity');
}}
function buildTower() {{
  bodies = [];
  const baseX = Math.max(260, canvas.width * 0.62);
  const baseY = canvas.height - 46;
  let k = 0;
  for (let r = 0; r < 5; r++) {{
    for (let c = 0; c < 3; c++) {{
      bodies.push({{ kind:'block', x:baseX+c*56, y:baseY-r*54, vx:0, vy:0, r:24, a:0, av:0, col:palette[k++%palette.length], glyph:'❏' }});
    }}
  }}
  bodies.push({{ kind:'rosette', x:baseX+56, y:baseY-5*54-10, vx:0, vy:0, r:30, a:0, av:0.03, col:'#f8cc30', glyph:'✺' }});
}}
function launchStar() {{
  bodies.push({{ kind:'star', x:60, y:canvas.height*0.48, vx:520, vy:-90, r:22, a:0, av:0.18, col:'#f8cc30', glyph:'★' }});
}}
function spawnRosette() {{
  bodies.push({{ kind:'rosette', x:120+Math.random()*(canvas.width-240), y:100+Math.random()*140, vx:(Math.random()-0.5)*120, vy:0, r:30, a:0, av:0.04, col:palette[Math.floor(Math.random()*palette.length)], glyph:'✺' }});
}}
function stampWombat(glyph, col, label, action) {{
  notes[selectedNote].badges.push(glyph + ' ' + label.split(' ')[0]);
  renderNotes();
  bodies.push({{ kind:'wombat', x:120+Math.random()*(canvas.width-240), y:90+Math.random()*160, vx:(Math.random()-0.5)*160, vy:-60, r:24, a:0, av:0.05, col, glyph }});
}}
function shatterOne(b) {{
  const out = [];
  for (let i = 0; i < 6; i++) {{
    const ang = (Math.PI*2*i)/6;
    out.push({{ kind:'shard', x:b.x+Math.cos(ang)*8, y:b.y+Math.sin(ang)*8, vx:b.vx*0.4+Math.cos(ang)*220, vy:b.vy*0.4+Math.sin(ang)*220-80, r:Math.max(7,b.r*0.4), a:ang, av:(i%2?0.22:-0.25), col:b.col }});
  }}
  return out;
}}
function shatterAll() {{
  const next = [];
  for (const b of bodies) {{
    if (b.kind === 'shard') next.push(b);
    else next.push(...shatterOne(b));
  }}
  bodies = next.slice(-180);
}}
canvas.addEventListener('click', (e) => {{
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left, y = e.clientY - rect.top;
  bodies.push({{ kind:'block', x, y, vx:(Math.random()-0.5)*120, vy:-40, r:22, a:0, av:0.03, col:palette[Math.floor(Math.random()*palette.length)], glyph:'❏' }});
}});
canvas.addEventListener('dblclick', (e) => {{
  const rect = canvas.getBoundingClientRect();
  const x = e.clientX - rect.left, y = e.clientY - rect.top;
  const idx = bodies.findIndex(b => b.kind !== 'shard' && Math.hypot(b.x-x, b.y-y) < b.r + 14);
  if (idx >= 0) {{
    const target = bodies.splice(idx, 1)[0];
    bodies.push(...shatterOne(target));
  }}
}});

function tick() {{
  const dt = 1/60;
  if (mode !== 'off') {{
    const g = mode === 'gravity' ? 520 : 0;
    const spawned = [];
    for (const b of bodies) {{
      if (b.dead) continue;
      b.vy += g * dt;
      b.x += b.vx * dt; b.y += b.vy * dt; b.a += b.av;
      if (b.y + b.r > canvas.height - 10) {{ b.y = canvas.height - 10 - b.r; b.vy = -Math.abs(b.vy)*0.72; b.vx *= 0.96; }}
      if (b.y - b.r < 10) {{ b.y = 10 + b.r; b.vy = Math.abs(b.vy)*0.72; }}
      if (b.x - b.r < 10) {{ b.x = 10 + b.r; b.vx = Math.abs(b.vx)*0.72; }}
      if (b.x + b.r > canvas.width - 10) {{ b.x = canvas.width - 10 - b.r; b.vx = -Math.abs(b.vx)*0.72; }}
    }}
    for (let i = 0; i < bodies.length; i++) {{
      const a = bodies[i]; if (a.dead) continue;
      for (let j = i+1; j < bodies.length; j++) {{
        const b = bodies[j]; if (b.dead) continue;
        const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy), md = a.r + b.r;
        if (d > 0.01 && d < md) {{
          const nx = dx/d, ny = dy/d, ov = (md-d)*0.5;
          a.x -= nx*ov; a.y -= ny*ov; b.x += nx*ov; b.y += ny*ov;
          const rv = (b.vx-a.vx)*nx + (b.vy-a.vy)*ny;
          if (rv < 0) {{
            const imp = -1.72 * rv * 0.5;
            a.vx -= imp*nx; a.vy -= imp*ny; b.vx += imp*nx; b.vy += imp*ny;
            if (Math.abs(rv) > 220) {{
              if (a.kind==='star' && b.kind!=='shard') {{ b.dead=true; spawned.push(...shatterOne(b)); }}
              else if (b.kind==='star' && a.kind!=='shard') {{ a.dead=true; spawned.push(...shatterOne(a)); }}
            }}
          }}
        }}
      }}
    }}
    if (spawned.length) bodies = bodies.filter(b => !b.dead).concat(spawned).slice(-200);
  }}
  ctx.fillStyle = '#0d1120'; ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.strokeStyle = '#19213a'; ctx.lineWidth = 1;
  for (let gx=32; gx<canvas.width; gx+=32) {{ ctx.beginPath(); ctx.moveTo(gx,0); ctx.lineTo(gx,canvas.height); ctx.stroke(); }}
  for (let gy=32; gy<canvas.height; gy+=32) {{ ctx.beginPath(); ctx.moveTo(0,gy); ctx.lineTo(canvas.width,gy); ctx.stroke(); }}

  for (const b of bodies) {{
    ctx.save(); ctx.translate(b.x, b.y); ctx.rotate(b.a);
    ctx.strokeStyle = b.col; ctx.lineWidth = 2.2;
    if (b.kind === 'block') {{
      ctx.fillStyle = b.col + '33'; ctx.fillRect(-b.r, -b.r, b.r*2, b.r*2); ctx.strokeRect(-b.r, -b.r, b.r*2, b.r*2);
    }} else if (b.kind === 'rosette') {{
      for (let p=0; p<9; p++) {{
        ctx.save(); ctx.rotate((Math.PI*2*p)/9);
        ctx.beginPath(); ctx.ellipse(b.r*0.42, 0, b.r*0.65, b.r*0.26, 0, 0, Math.PI*2); ctx.stroke();
        ctx.restore();
      }}
    }} else if (b.kind === 'star') {{
      ctx.beginPath();
      for (let k=0; k<10; k++) {{ const rr=k%2?b.r*0.45:b.r, aa=k*Math.PI/5; ctx.lineTo(Math.cos(aa)*rr, Math.sin(aa)*rr); }}
      ctx.closePath(); ctx.fillStyle=b.col; ctx.fill(); ctx.stroke();
    }} else if (b.kind === 'wombat') {{
      ctx.beginPath(); ctx.arc(0,0,b.r,0,Math.PI*2); ctx.fillStyle=b.col+'28'; ctx.fill(); ctx.stroke();
      ctx.fillStyle=b.col; ctx.font='22px serif'; ctx.textAlign='center'; ctx.textBaseline='middle'; ctx.fillText(b.glyph,0,1);
    }} else {{
      ctx.beginPath();
      for (let k=0; k<3; k++) {{ const aa=k*2*Math.PI/3; ctx.lineTo(Math.cos(aa)*b.r, Math.sin(aa)*b.r); }}
      ctx.closePath(); ctx.fillStyle=b.col; ctx.fill();
    }}
    ctx.restore();
  }}
  requestAnimationFrame(tick);
}}
buildTower();
renderNotes();
requestAnimationFrame(tick);
</script>
</body>
</html>
"""


def render_physics_room_html() -> bytes:
    """HTTP route renderer for /physics on the live Zoe-ELIZA Web Studio."""
    return build_interactive_physics_room_html_str().encode("utf-8")


def write_interactive_physics_room_html(out_html: str | Path) -> Path:
    """Write a 100% offline, standalone HTML5 Canvas Optional-Physics Sandbox + Wombats Tapback Studio."""
    target = Path(out_html)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_interactive_physics_room_html_str(), encoding="utf-8")
    return target


__all__ = [
    "CONSTITUTIONAL_FLAGS",
    "PAGE_A2_WOMBATS_REACTIONS",
    "WOMBATS_PHYSICS_CONTRACT",
    "HighlightReactionRecord",
    "PhysicsMode",
    "PhysicsSandboxRoom",
    "SandboxBody",
    "WombatReactionSpec",
    "WombatsReactionBar",
    "build_artline_rosette_wombats_plate",
    "build_interactive_physics_room_html_str",
    "render_physics_room_html",
    "render_physics_shatter_gif",
    "resolve_wombat_reaction",
    "write_interactive_physics_room_html",
]
