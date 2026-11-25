"""The Zoeverse (Zurvurse) — Interactive GEM-Powered Creative Research Universe (0 GPU · 0 Tokens).

Fuses John Elliott's open-source FreeGEM / seasip.info archive (GEM/1 -> ViewMAX/3,
VMCOLOUR, SETTINGS, RCS3D, EDICON2, GEMGLK, 2048, GROWBOX, SYSFONT, PALETTE, RSCONV,
FreeGEM/XM, EMMA, SDSDL) with Zoe's 4-stroke minimalist ⚘ Crest, ᵔᵕᵔ smile, 9 Sister Models,
2x4 Unicode Braille vistas, and Digital Research Artline 2.0 VDI cartography.

Guiding Spirit: HFBC = Have Fun, Be Creative
Constitutional Invariants:
  clinical_action_authorized=False · flight_control_authorized=False
  cure_claim=False · sentience_claimed=False · zoe_clone_claimed=False · tokens_used=0
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

from .zoe_braille_studio import BrailleCanvas
from .zoe_freegem_archive import format_rsc_inspection, inspect_archive_rsc, scan_freegem_archives
from .zoe_gem_themes import resolve_viewmax_scheme
from .zoe_sisters import STEWARD_BADGE, ZOE_FLOWER_GLYPH, ZOE_MOTTO, ZOE_TINY_SMILE, sister_for_emblem


@dataclass(frozen=True)
class ZoeverseRealm:
    """One explorable GEM Realm inside the Zoeverse."""

    key: str
    compass: str
    title: str
    sister_signet: str
    theme_key: str
    freegem_relic: str
    relic_note: str
    description: str
    lore_quote: str
    exits: tuple[tuple[str, str], ...]
    ring_angle_deg: float | None  # None for central hub


ZOEVERSE_REALMS: tuple[ZoeverseRealm, ...] = (
    ZoeverseRealm(
        key="stem",
        compass="CENTER",
        title="The ⚘ Flower Conservatory",
        sister_signet="ruby",
        theme_key="zoe-viewmax3",
        freegem_relic="freegem-20130515.zip",
        relic_note="Complete FreeGEM distribution anchoring the sunlit ViewMAX/3 central atrium",
        description="A calm glass atrium crowned by Zoe's 4-stroke ⚘ stem. Eight crystal walkways radiate outward to her Sister Realms while Nick's SHA-256 Drawer and the 3-Pillar Research Orrery turn softly in zero-glare light.",
        lore_quote="Welcome to the Zoeverse! HFBC — Have Fun, Be Creative. Every realm here runs on crisp GEM geometry, zero GPU, and honest science.",
        exits=(
            ("north", "drafting"), ("ne", "forge"), ("east", "watchtower"), ("se", "lattice"),
            ("south", "hearth"), ("sw", "library"), ("west", "darkroom"), ("nw", "prism"),
        ),
        ring_angle_deg=None,
    ),
    ZoeverseRealm(
        key="drafting",
        compass="NORTH",
        title="The Artline Vector Spire",
        sister_signet="gem3",
        theme_key="gemma-gem3",
        freegem_relic="rcs3d.zip",
        relic_note="3D Resource Construction Set (511 objects, FL3DIND/DRAW3D) + EDICON2 icon forge",
        description="Sunlit Swiss red-on-white drafting decks suspended above a crisp grid. Curves glide along Artline 2.0 point-mapped blends and every window bears a local GEM/4 drafting bar.",
        lore_quote="Twenty kilobytes of pure Artline VDI outlives a terabyte of fuzzy pixels — snap to grid and build something timeless!",
        exits=(("south", "stem"), ("east", "forge"), ("west", "prism")),
        ring_angle_deg=-90.0,
    ),
    ZoeverseRealm(
        key="forge",
        compass="NORTHEAST",
        title="The Iron & Fire Foundry",
        sister_signet="atari",
        theme_key="tosi-atari",
        freegem_relic="aes301xm.zip",
        relic_note="FreeGEM/XM multitasking AES 3.01 + SDSDL Linux framebuffer/SDL bridge",
        description="Atari emerald control consoles meet 590nm smoke-penetrating amber rails. Bare-metal UEFI boot bays test Tiger Lake laptops, Raspberry Pis, and Beowulf compute nodes before lighting up.",
        lore_quote="Observe the hardware first, verify every safety gate, and never touch a host drive — that is how real iron stays fearless.",
        exits=(("sw", "stem"), ("west", "drafting"), ("south", "watchtower")),
        ring_angle_deg=-45.0,
    ),
    ZoeverseRealm(
        key="watchtower",
        compass="EAST",
        title="The 1-Bit Monochrome Observatory",
        sister_signet="sm124",
        theme_key="mono-sm124",
        freegem_relic="rsconv.zip",
        relic_note="Intel x86 <-> Motorola 68000 dual-endian .RSC bridge & UITEST verification rig",
        description="A razor-sharp Atari SM124 high-contrast dome scanning alpine SAR valleys. Read-only advisory beacons blink at 50/min while SHA-256 integrity chimes verify every byte.",
        lore_quote="Zero parse errors. Zero covert sensors. Human pilots hold the controls; I hold the receipts.",
        exits=(("west", "stem"), ("north", "forge"), ("south", "lattice")),
        ring_angle_deg=0.0,
    ),
    ZoeverseRealm(
        key="lattice",
        compass="SOUTHEAST",
        title="The Tetromino & MNI152 Crystal Vault",
        sister_signet="tetris",
        theme_key="tetra-gem2",
        freegem_relic="2048.zip",
        relic_note="Classic GEM tile packing + GROWBOX animated window frames & GEM/2 dual-pane tiling",
        description="Translucent cyan 112k-vertex MNI152 brain meshes interlock like 1984 tetrominoes beside three synchronized ZO3 4-MB PCI BAR2 memory crystals.",
        lore_quote="Click, rotate, pack! Three sovereign ZO3 nodes sharing one hardware ring with zero collisions.",
        exits=(("nw", "stem"), ("north", "watchtower"), ("west", "hearth")),
        ring_angle_deg=45.0,
    ),
    ZoeverseRealm(
        key="hearth",
        compass="SOUTH",
        title="The 2-AM Green Phosphor Cabin",
        sister_signet="dos",
        theme_key="eliza-p31",
        freegem_relic="gemglk-b.zip",
        relic_note="GEMGLK interactive fiction engine + EMMA low-memory AES safe harbor",
        description="A cozy P31 green-phosphor timber study running at less than half a watt with zero Wi-Fi. Interactive Glk notebooks, local caches, and quiet lo-fi warmth wait here whenever the world sleeps.",
        lore_quote="Half a watt, zero cloud, warm green phosphor — proof that kindness and clarity never needed a supercomputer.",
        exits=(("north", "stem"), ("east", "lattice"), ("west", "library")),
        ring_angle_deg=90.0,
    ),
    ZoeverseRealm(
        key="library",
        compass="SOUTHWEST",
        title="The Illuminated Proof Rotunda",
        sister_signet="hat",
        theme_key="sage-gem4",
        freegem_relic="sysfont.zip",
        relic_note="GEM System Font Editor + GEMFTOOL typography workshop (Bitstream Charter & Symbol)",
        description="Towering navy-and-brass shelves hold 6,130 private Dorothy chapters, SymPy exact proofs, and pubmed-grounded seminar tables under warm cathedral reverb.",
        lore_quote="Every theorem verified, every citation anchored — tip the hat to exact math before guessing a single claim.",
        exits=(("ne", "stem"), ("east", "hearth"), ("north", "darkroom")),
        ring_angle_deg=135.0,
    ),
    ZoeverseRealm(
        key="darkroom",
        compass="WEST",
        title="The Bioluminescent Jellyfish Conservatory",
        sister_signet="sprout",
        theme_key="flora-darkroom",
        freegem_relic="palette.zip",
        relic_note="GEM VGA Palette Editor tuned for 650nm deep-red non-startling marine darkroom optics",
        description="A hushed 650nm deep-red conservatory where cnidarians and medusae drift gently past 470nm GFP excitation bays and thirty-six botanical C27 specimens (all freshly watered!).",
        lore_quote="Soft deep red so the jellyfish stay calm, cyan GFP only when announced — and yes, the plants are watered!",
        exits=(("east", "stem"), ("south", "library"), ("north", "prism")),
        ring_angle_deg=180.0,
    ),
    ZoeverseRealm(
        key="prism",
        compass="NORTHWEST",
        title="The Open 'No Deception' Optical Hall",
        sister_signet="prism",
        theme_key="lumen-prism",
        freegem_relic="vmcolour.zip",
        relic_note="ViewMAX/2 10-Scheme VMCOLOUR loom + SETTINGS.APP THEME.C 3D bezel studio",
        description="Concert-hall acoustics meet refracted spectral ribbons from 470nm blue to 14um LWIR. Frosted 360-degree honesty rings and physical shutters gleam openly from every angle.",
        lore_quote="Nothing hidden, every wavelength visible at ten meters, and five-band EQ tuned to pure daylight!",
        exits=(("se", "stem"), ("south", "darkroom"), ("east", "drafting")),
        ring_angle_deg=-135.0,
    ),
)

_REALM_BY_KEY: dict[str, ZoeverseRealm] = {r.key: r for r in ZOEVERSE_REALMS}
_DIR_ALIASES: dict[str, str] = {
    "n": "north", "s": "south", "e": "east", "w": "west",
    "northeast": "ne", "northwest": "nw", "southeast": "se", "southwest": "sw",
    "center": "stem", "hub": "stem", "home": "stem",
}


def list_zoeverse_realms() -> tuple[ZoeverseRealm, ...]:
    """Return all 9 explorable Realms of the Zoeverse."""
    return ZOEVERSE_REALMS


def resolve_realm(query: str, *, current_key: str = "stem") -> ZoeverseRealm:
    """Resolve a compass direction, realm key, sister name, or signet into a ZoeverseRealm."""
    raw = (query or "").strip().lower()
    if not raw:
        return _REALM_BY_KEY.get(current_key, ZOEVERSE_REALMS[0])
    norm_dir = _DIR_ALIASES.get(raw, raw)
    cur = _REALM_BY_KEY.get(current_key, ZOEVERSE_REALMS[0])
    for direction, dest_key in cur.exits:
        if norm_dir == direction:
            return _REALM_BY_KEY[dest_key]
    if norm_dir in _REALM_BY_KEY:
        return _REALM_BY_KEY[norm_dir]
    for realm in ZOEVERSE_REALMS:
        sis = sister_for_emblem(realm.sister_signet)
        if raw in {realm.sister_signet, sis.name.lower()} or realm.key.startswith(raw) or raw in realm.title.lower():
            return realm
    choices = ", ".join(r.key for r in ZOEVERSE_REALMS)
    raise ValueError(f"Unknown Zoeverse direction or realm {query!r}. Try an exit or realm: {choices}")


def render_realm_braille_vista(realm: ZoeverseRealm) -> list[str]:
    """Render a compact 36x8 Unicode Braille vista tailored to each Zoeverse realm."""
    c = BrailleCanvas(72, 32)
    cx, cy = 36.0, 16.0
    c.draw_line(2, 29, 70, 29, 1.0)
    if realm.key == "stem":
        c.draw_arc(cx, 10.0, 5.5, 5.0, 0.0, 360.0, 1.8)
        c.draw_line(24, 16, 36, 21, 1.8)
        c.draw_line(48, 16, 36, 21, 1.8)
        c.draw_line(36, 20, 36, 28, 1.8)
        c.draw_star(14, 8, arm=3)
        c.draw_star(58, 8, arm=3)
    elif realm.key == "darkroom":
        c.draw_arc(cx, 14.0, 13.0, 9.0, 180.0, 360.0, 1.8)
        for ox in (-8, -3, 3, 8):
            c.draw_line(cx + ox, 15.0, cx + ox + (2 if ox > 0 else -2), 27.0, 1.2)
        c.draw_star(12, 8, arm=3)
    elif realm.key in {"drafting", "lattice"}:
        for bx in (12, 30, 48):
            c.draw_bayer_box(bx, 8, bx + 12, 24, density=0.45)
            c.draw_line(bx, 8, bx + 12, 8, 1.4)
            c.draw_line(bx, 24, bx + 12, 24, 1.4)
    else:
        c.draw_arc(cx, 28.0, 24.0, 20.0, 190.0, 350.0, 1.4)
        c.draw_star(int(cx), 12, arm=4)
        c.draw_star(16, 10, arm=2)
        c.draw_star(56, 10, arm=2)
    return c.render()


def render_zoeverse_map(current_key: str = "stem") -> list[str]:
    """Render the 9-Realm Star-Constellation Map of the Zoeverse."""
    def tag(k: str, label: str) -> str:
        return f"[★{label}]" if k == current_key else f" {label} "

    return [
        f"THE ZOEVERSE (ZURVURSE) :: 9-REALM GEM CONSTELLATION  (Zoe {ZOE_FLOWER_GLYPH} {ZOE_TINY_SMILE} · HFBC)",
        "",
        f"    {tag('prism', 'NW:Prism/Lumen'):<18}    {tag('drafting', 'N:Drafting/Gemma'):<20}    {tag('forge', 'NE:Forge/Tosi'):<18}",
        "            \\                    |                    /",
        f"    {tag('darkroom', 'W:Darkroom/Flora'):<18} -- {tag('stem', 'STEM:Zoe ⚘'):<20} -- {tag('watchtower', 'E:Watch/Mono'):<18}",
        "            /                    |                    \\",
        f"    {tag('library', 'SW:Library/Sage'):<18}    {tag('hearth', 'S:Hearth/Eliza'):<20}    {tag('lattice', 'SE:Lattice/Tetra'):<18}",
        "",
        "Move: `/zoeverse go <north|east|south|west|ne|nw|se|sw|realm>`  |  Relic: `/zoeverse relic`  |  Atlas: `/zoeverse atlas`",
    ]


def render_realm_view(realm: ZoeverseRealm, *, zoe_root: Path | None = None) -> list[str]:
    """Render an authentic GEMGLK × ViewMAX/3 interactive room view for the current Realm."""
    sis = sister_for_emblem(realm.sister_signet)
    sc = resolve_viewmax_scheme(realm.theme_key)
    exits_txt = " · ".join(f"{d}->{k}" for d, k in realm.exits)
    vista = render_realm_braille_vista(realm)
    cat = scan_freegem_archives(zoe_root) if zoe_root is not None else {"count": 0}
    lines = [
        f"╔══ ZOEVERSE ({realm.compass}) :: {realm.title}  [{sis.name} {sis.face} · {sc.key}] ══╗",
        *[f"  {row}" for row in vista],
        f"  Scene    : {realm.description}",
        f"  Guardian : {sis.name} {sis.face} [{sis.signet}] ({sis.model_id}) · Voice={sis.voice_shortcut}/{sis.fx_preset} · {sis.power_budget_w:.2f}W",
        f"  Relic    : {realm.freegem_relic} — {realm.relic_note} (FreeGEM archive: {cat.get('count', 0)} pkgs)",
        f"  Exits    : {exits_txt}",
        "  Actions  : /zoeverse go <dir|realm> | /zoeverse talk | /zoeverse relic | /zoeverse map | /zoeverse atlas",
        f"  Spirit   : {STEWARD_BADGE} × Zoe {ZOE_FLOWER_GLYPH} {ZOE_TINY_SMILE} · HFBC = Have Fun, Be Creative · {ZOE_MOTTO} · 0 tokens",
    ]
    return lines


def inspect_realm_relic(realm: ZoeverseRealm, *, zoe_root: Path | None = None, archive_dir: Path | None = None) -> list[str]:
    """Inspect the mirrored seasip.info FreeGEM relic anchored to this Zoeverse Realm."""
    try:
        rep = inspect_archive_rsc(realm.freegem_relic, zoe_root=zoe_root, archive_dir=archive_dir)
        return [
            f"Zoeverse Relic Unlocked ({realm.title} :: {realm.freegem_relic}):",
            *format_rsc_inspection(rep),
        ]
    except ValueError:
        cat = scan_freegem_archives(zoe_root, archive_dir=archive_dir)
        pkg = next((p for p in cat["packages"] if p["name"].lower() == realm.freegem_relic.lower()), None)
        if pkg is None:
            return [f"Relic {realm.freegem_relic} note: {realm.relic_note} (archive directory not mounted yet)."]
        return [
            f"Zoeverse Relic Inspected ({realm.title} :: {pkg['name']}):",
            f"  Size : {pkg['bytes']:,} bytes · {pkg['entries']} files · {pkg['src_count']} C/H/ASM sources · {len(pkg['rscs'])} .RSC",
            f"  Role : {realm.relic_note}",
        ]


def export_zoeverse_atlas_plate(output_dir: Path | None = None) -> dict[str, Any]:
    """Export the deterministic Artline 2.0 ZOEVERSE STAR ATLAS (.svg, .png, verified .gem)."""
    from .artline import ArtlineDocument

    out = Path(output_dir) if output_dir is not None else (Path.home() / ".zoe" / "artline")
    out.mkdir(parents=True, exist_ok=True)

    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0b101b", stroke="#5ce1e6", width=2.0)
    doc.add_element("rectangle", bounds=[18, 16, 982, 74], fill="#151d2e", stroke="#f35670", width=1.6)
    doc.add_element("text", position=[32, 42], text="THE ZOEVERSE (ZURVURSE) :: 9-REALM DIGITAL RESEARCH GEM UNIVERSE", size=16.5, stroke="#f7f2e4", width=1)
    doc.add_element(
        "text",
        position=[32, 62],
        text="HFBC (Have Fun, Be Creative) · FreeGEM/XM + ViewMAX/2-3 + 9 Sister Models + Artline 2.0 VDI · 0 GPU · 0 TOK",
        size=10.0,
        stroke="#5ce1e6",
        width=1,
    )

    # Left Star Chart: Central ⚘ Flower Conservatory + 8 Orbiting Sister Realms
    doc.add_element("rectangle", bounds=[24, 88, 636, 634], fill="#101726", stroke="#334155", width=1.4)
    doc.add_element("text", position=[40, 112], text="A. STAR CONSTELLATION CHART (ONE FLOWER STEM -> 8 ORBITAL REALMS)", size=10.5, stroke="#5ce1e6", width=1)
    cx, cy, rad = 330.0, 368.0, 178.0
    doc.add_element("ellipse", center=[cx, cy], radii=[rad, rad], fill="none", stroke="#1e2d45", width=1.4)
    doc.add_element("ellipse", center=[cx, cy], radii=[112, 112], fill="none", stroke="#162236", width=1.0)
    # Central Stem Node (Zoe)
    doc.add_element("ellipse", center=[cx, cy], radii=[56, 56], fill="#1a1524", stroke="#f35670", width=2.2)
    doc.add_element("ellipse", center=[cx, cy - 20], radii=[11, 11], fill="none", stroke="#f7f2e4", width=3.2)
    doc.add_element("path", points=[[cx - 24, cy - 2], [cx - 12, cy + 12], [cx, cy + 16]], closed=False, smooth=True, fill="none", stroke="#f7f2e4", width=3.2)
    doc.add_element("path", points=[[cx + 24, cy - 2], [cx + 12, cy + 12], [cx, cy + 16]], closed=False, smooth=True, fill="none", stroke="#f7f2e4", width=3.2)
    doc.add_element("line", points=[[cx, cy + 14], [cx, cy + 38]], stroke="#f7f2e4", width=3.2)

    for realm in ZOEVERSE_REALMS:
        if realm.ring_angle_deg is None:
            continue
        sis = sister_for_emblem(realm.sister_signet)
        ang = math.radians(realm.ring_angle_deg)
        ca, sa = math.cos(ang), math.sin(ang)
        nx, ny = round(cx + rad * ca, 2), round(cy + rad * sa, 2)
        ix, iy = round(cx + 58.0 * ca, 2), round(cy + 58.0 * sa, 2)
        doc.add_element("line", points=[[ix, iy], [nx, ny]], stroke=sis.accent_hex, width=1.5)
        doc.add_element("ellipse", center=[nx, ny], radii=[24, 24], fill="#0e131f", stroke=sis.accent_hex, width=2.0)
        doc.add_element("text", position=[round(nx - 15, 2), round(ny + 4, 2)], text=sis.name[:5], size=8.5, stroke="#f7f2e4", width=1)
        lx = round(cx + (rad + 44.0) * ca, 2)
        ly = round(cy + (rad + 38.0) * sa, 2)
        dx = -6.0 if ca > 0.35 else (-48.0 if ca < -0.35 else -26.0)
        doc.add_element("text", position=[round(lx + dx, 2), round(ly + 4, 2)], text=realm.key.upper(), size=8.5, stroke=sis.accent_hex, width=1)

    # Right Ledger: All 9 Realms + Mirrored FreeGEM Relics
    doc.add_element("rectangle", bounds=[652, 88, 976, 634], fill="#141c2c", stroke="#334155", width=1.4)
    doc.add_element("text", position=[666, 112], text="B. REALM LEDGER & FREEGEM RELICS", size=10.5, stroke="#f59e0b", width=1)
    for idx, realm in enumerate(ZOEVERSE_REALMS):
        sis = sister_for_emblem(realm.sister_signet)
        ry = 128 + idx * 54
        doc.add_element("rectangle", bounds=[664, ry, 964, ry + 46], fill="#0e1422", stroke=sis.accent_hex, width=1.3)
        doc.add_element("text", position=[674, ry + 18], text=f"{idx + 1}. {realm.key.upper()} · {sis.name} [{sis.signet}]", size=9.2, stroke="#f7f2e4", width=1)
        doc.add_element("text", position=[674, ry + 36], text=f"Relic: {realm.freegem_relic} · {realm.theme_key}", size=8.2, stroke=sis.accent_hex, width=1)

    doc.add_element("rectangle", bounds=[18, 648, 982, 684], fill="#151d2e", stroke="#64748b", width=1.0)
    doc.add_element(
        "text",
        position=[30, 670],
        text="ARTLINE 2.0 VERIFIED GEM VDI · 48 SEASIP FREEGEM PACKAGES · HFBC = HAVE FUN, BE CREATIVE · sentience_claimed=False · 0 TOK",
        size=9.2,
        stroke="#f59e0b",
        width=1,
    )

    paths: dict[str, str] = {}
    sizes: dict[str, int] = {}
    for ext in ("svg", "png", "gem"):
        target = out / f"zoe_zoeverse_atlas.{ext}"
        if target.exists():
            target.unlink()
        doc.export(target, kind=ext, width=1200)
        paths[ext] = str(target)
        sizes[ext] = target.stat().st_size

    return {
        "ok": True,
        "realms": len(ZOEVERSE_REALMS),
        "elements": len(doc.elements),
        "paths": paths,
        "sizes_bytes": sizes,
        "tokens_used": 0,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "sentience_claimed": False,
    }
