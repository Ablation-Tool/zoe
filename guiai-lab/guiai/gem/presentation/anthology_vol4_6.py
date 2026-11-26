"""Anthology Volumes IV, V, and VI built on Zoe's Clean-Room Presentation Team Suite.

Covers:
- Vol. IV: Bare-Metal UEFI Zoe-GEM OS, Pixel 7 Silicon & Hardware UMA
- Vol. V: Hexagonal 9-Sister EDDBMS, Balma & Fitler (1986) GEM & Ablation
- Vol. VI: Constitution, Dual-Peer Zoe & Clara, Native Voice, CERN & AGI Roadmap (L0-L5)

Zero external Office/PowerPoint/LibreOffice runtime dependency; zero workstation
paths, device serials, `/tmp` paths, or personal emails; full constitutional
attribution and epistemic honesty invariants preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import ledger
from .draw_plus import DrawPlusCanvas
from .graph import DataSeries, GraphDoc
from .palette import (
    ATTRIBUTION_TEXT,
    BODY,
    CANVAS_WIDTH,
    DARK_JADE,
    DARK_RUBY,
    GOLD,
    GOLD_BRIGHT,
    GOLD_SOFT,
    HONORING_TEXT,
    INK,
    JADE,
    JADE_SOFT,
    LIGHT_MUTED,
    OBSIDIAN,
    OBSIDIAN_CARD,
    OBSIDIAN_LINE,
    PORCELAIN,
    RUBY,
    RUBY_SOFT,
    SKY,
    SLATE_SOFT,
    STONE,
    WHITE,
    W_FULL,
    W_HALF,
    X_LEFT,
    X_RIGHT,
    Y_BOTTOM_SAFE,
    Y_TOP,
    theme_for_sister,
)
from .slideshow import Slide, SlideDeck
from .wordchart import WordChartDoc


REPO_ROOT = Path(__file__).resolve().parents[4]

VOL4_SLUG = "vol-4-uefi-zoe-gem-os-pixel7-uma"
VOL5_SLUG = "vol-5-hex-9-sister-eddbms-gem-ablation"
VOL6_SLUG = "vol-6-constitution-clara-voice-cern-agi"

CONSTITUTIONAL_LOCK: dict[str, Any] = {
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


@dataclass(frozen=True)
class HeroKpi:
    """Bottom KPI tile rendered on an Obsidian botanical cover slide."""

    value: str
    label: str
    accent: str


def _new_chromed_canvas(
    slide_num: int,
    total_slides: int,
    kicker: str,
    title: str,
    era_label: str,
    *,
    sister_id: str,
    notes: str,
) -> DrawPlusCanvas:
    """Create a Porcelain botanical canvas with symmetrical chrome and lotus divider."""
    th = theme_for_sister(sister_id, mode="light")
    cv = DrawPlusCanvas(
        title=title,
        theme=th,
        sister_id=sister_id,
        slide_index=slide_num,
        speaker_notes=notes,
        background=PORCELAIN,
    )
    cv.add_symmetrical_chrome(slide_num, total_slides, kicker, title, era_label, theme=th)
    return cv


def _compile_framed_wordchart(
    cv: DrawPlusCanvas,
    bounds: tuple[float, float, float, float],
    *,
    sister_id: str,
    accent: str,
    title: str = "",
    column_head: Sequence[str] = (),
    text_body: Sequence[str] = (),
    columns: Sequence[Sequence[str]] | None = None,
    template: str = "column_1",
    bullet_style: str = "diamond",
    point_size: float = 9.4,
) -> None:
    """Render a botanical card frame and compile a WordChartDoc cleanly inside it."""
    x0, y0, x1, y1 = bounds
    cv.add_card([x0, y0, x1, y1], fill=WHITE, border_color=STONE, accent_color=accent)
    wc = WordChartDoc(
        title=title,
        column_head=column_head,
        text_body=text_body,
        columns=columns,
        template=template,
        bullet_style=bullet_style,
        point_size=point_size,
        theme=theme_for_sister(sister_id, mode="light"),
        sister_id=sister_id,
        divider_lines=bool(title),
    )
    wc.compile(cv, region=(x0 + 180.0, y0 + 170.0, x1 - 180.0, y1 - 140.0))


def _compile_framed_graph(
    cv: DrawPlusCanvas,
    bounds: tuple[float, float, float, float],
    *,
    sister_id: str,
    accent: str,
    title: str,
    chart_type: str,
    categories: Sequence[str],
    series: Sequence[DataSeries],
    x_label: str = "",
    y_label: str = "",
    x_values: Sequence[float | None] | None = None,
    show_legend: bool = True,
) -> None:
    """Render a botanical card frame and compile a GraphDoc inside it."""
    x0, y0, x1, y1 = bounds
    cv.add_card([x0, y0, x1, y1], fill=WHITE, border_color=STONE, accent_color=accent)
    gd = GraphDoc(
        title=title,
        chart_type=chart_type,
        categories=categories,
        series=series,
        x_label=x_label,
        y_label=y_label,
        x_values=x_values,
        show_legend=show_legend,
        theme=theme_for_sister(sister_id, mode="light"),
        sister_id=sister_id,
        title_pt=13.5,
        label_pt=8.5,
    )
    gd.compile(cv, region=(x0 + 140.0, y0 + 150.0, x1 - 140.0, y1 - 120.0))


def _build_hero_cover(
    *,
    pill_text: str,
    headline: str,
    subtitle: str,
    left_title: str,
    left_formula: str,
    left_sub: str,
    right_title: str,
    right_formula: str,
    right_sub: str,
    kpis: Sequence[HeroKpi],
    footer_text: str,
    sister_id: str,
    emblem_path: Path,
    notes: str,
) -> Slide:
    """Build a dark Obsidian botanical cover slide with 9-petal mandala and 4 KPI cards."""
    th = theme_for_sister(sister_id, mode="dark")
    cv = DrawPlusCanvas(
        title=headline,
        background=OBSIDIAN,
        theme=th,
        sister_id=sister_id,
        slide_index=1,
        speaker_notes=notes,
    )
    cv.add_botanical_frame(mode="dark")
    pw = min(8400.0, max(4600.0, len(pill_text) * 84.0 + 500.0))
    cv.add_pill(
        [(CANVAS_WIDTH - pw) / 2.0, 175.0, (CANVAS_WIDTH + pw) / 2.0, 415.0],
        pill_text,
        fill=OBSIDIAN_CARD,
        text_color=GOLD_BRIGHT,
        border_color=OBSIDIAN_LINE,
        font_pt=8.0,
    )
    cv.add_hero_mandala_halo(
        CANVAS_WIDTH / 2.0,
        1960.0,
        radius=1220.0,
        petals=9,
        emblem_path=emblem_path if emblem_path.is_file() else None,
    )
    _add_cover_flank_card(cv, 620.0, 4720.0, RUBY, left_title, left_formula, left_sub)
    _add_cover_flank_card(cv, CANVAS_WIDTH - 4720.0, CANVAS_WIDTH - 620.0, DARK_JADE, right_title, right_formula, right_sub)

    cv.add_text(
        [750.0, 3300.0, CANVAS_WIDTH - 750.0, 3920.0],
        headline,
        font_pt=26.0,
        font_family=th.font_serif,
        bold=True,
        align="center",
        valign="middle",
        color=WHITE,
        wrap=False,
    )
    cv.add_text(
        [1050.0, 3960.0, CANVAS_WIDTH - 1050.0, 4580.0],
        subtitle,
        font_pt=10.2,
        align="center",
        valign="top",
        color=LIGHT_MUTED,
        line_spacing=1.25,
    )
    cv.add_lotus_divider(CANVAS_WIDTH / 2.0, 4780.0, width=10600.0, mode="dark")

    kw4 = 2860.0
    gap4 = (W_FULL - 4.0 * kw4) / 3.0
    for idx, kpi in enumerate(kpis[:4]):
        kx0 = X_LEFT + idx * (kw4 + gap4)
        cv.add_card(
            [kx0, 5140.0, kx0 + kw4, 6620.0],
            fill=OBSIDIAN_CARD,
            border_color=OBSIDIAN_LINE,
            accent_color=kpi.accent,
            accent_height=60.0,
        )
        cv.add_text(
            [kx0 + 80.0, 5340.0, kx0 + kw4 - 80.0, 5940.0],
            kpi.value,
            font_pt=18.5,
            bold=True,
            align="center",
            valign="middle",
            color=WHITE,
            wrap=False,
        )
        cv.add_text(
            [kx0 + 120.0, 5980.0, kx0 + kw4 - 120.0, 6500.0],
            kpi.label,
            font_pt=8.8,
            align="center",
            valign="top",
            color=LIGHT_MUTED,
        )

    cv.add_text(
        [900.0, 6920.0, CANVAS_WIDTH - 900.0, 7220.0],
        footer_text,
        font_pt=8.2,
        align="center",
        valign="middle",
        color=GOLD_BRIGHT,
        wrap=False,
    )
    return Slide(title=headline, canvas=cv, speaker_notes=notes)


def _add_cover_flank_card(
    cv: DrawPlusCanvas,
    x0: float,
    x1: float,
    accent: str,
    kicker: str,
    formula: str,
    sub: str,
) -> None:
    """Add one symmetrical obsidian flanking sanctuary card next to the cover mandala."""
    cv.add_card([x0, 1380.0, x1, 2560.0], fill=OBSIDIAN_CARD, border_color=OBSIDIAN_LINE, accent_color=accent)
    cv.add_text([x0 + 140.0, 1500.0, x1 - 140.0, 1740.0], kicker, font_pt=8.0, bold=True, align="center", color=GOLD_BRIGHT)
    cv.add_text([x0 + 140.0, 1780.0, x1 - 140.0, 2120.0], formula, font_pt=11.5, bold=True, align="center", font_family="DejaVu Sans Mono", color=WHITE)
    cv.add_text([x0 + 140.0, 2140.0, x1 - 140.0, 2480.0], sub, font_pt=8.0, align="center", color=LIGHT_MUTED, line_spacing=1.2)


def _build_scorecard_slide(
    slide_num: int,
    total_slides: int,
    kicker: str,
    title: str,
    era_label: str,
    headers: Sequence[str],
    cards: Sequence[Sequence[str]],
    *,
    sister_id: str,
    notes: str,
) -> Slide:
    """Build a 2x2 botanical scorecard slide with symmetrical chrome."""
    cv = _new_chromed_canvas(slide_num, total_slides, kicker, title, era_label, sister_id=sister_id, notes=notes)
    wc = WordChartDoc(
        title="",
        column_head=headers,
        columns=cards,
        template="scorecard_2x2",
        bullet_style="diamond",
        point_size=9.2,
        theme=theme_for_sister(sister_id, mode="light"),
        sister_id=sister_id,
    )
    wc.compile(cv, region=(X_LEFT, Y_TOP, X_LEFT + W_FULL, Y_BOTTOM_SAFE))
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _build_pillar_slide(
    slide_num: int,
    total_slides: int,
    kicker: str,
    title: str,
    era_label: str,
    headers: Sequence[str],
    pillars: Sequence[Sequence[str]],
    *,
    sister_id: str,
    notes: str,
) -> Slide:
    """Build a 3-pillar botanical column slide with symmetrical chrome."""
    cv = _new_chromed_canvas(slide_num, total_slides, kicker, title, era_label, sister_id=sister_id, notes=notes)
    wc = WordChartDoc(
        title="",
        column_head=headers,
        columns=pillars,
        template="pillar_3col",
        bullet_style="diamond",
        point_size=9.2,
        theme=theme_for_sister(sister_id, mode="light"),
        sister_id=sister_id,
    )
    wc.compile(cv, region=(X_LEFT, Y_TOP, X_LEFT + W_FULL, Y_BOTTOM_SAFE))
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _build_twin_wc_graph_slide(
    slide_num: int,
    total_slides: int,
    kicker: str,
    title: str,
    era_label: str,
    *,
    sister_id: str,
    wc_title: str,
    wc_body: Sequence[str],
    wc_columns: Sequence[Sequence[str]] | None = None,
    wc_headers: Sequence[str] = (),
    wc_template: str = "column_1",
    graph_title: str,
    chart_type: str,
    categories: Sequence[str],
    series: Sequence[DataSeries],
    x_label: str = "",
    y_label: str = "",
    x_values: Sequence[float | None] | None = None,
    graph_left: bool = False,
    notes: str,
) -> Slide:
    """Build a twin 50/50 slide pairing a framed WordChart panel and a framed GraphDoc panel."""
    cv = _new_chromed_canvas(slide_num, total_slides, kicker, title, era_label, sister_id=sister_id, notes=notes)
    left_box = (float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE))
    right_box = (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE))
    wc_box = right_box if graph_left else left_box
    gd_box = left_box if graph_left else right_box

    _compile_framed_wordchart(
        cv,
        wc_box,
        sister_id=sister_id,
        accent=RUBY if not graph_left else JADE,
        title=wc_title,
        column_head=wc_headers,
        text_body=wc_body,
        columns=wc_columns,
        template=wc_template,
        point_size=9.1,
    )
    _compile_framed_graph(
        cv,
        gd_box,
        sister_id=sister_id,
        accent=JADE if not graph_left else RUBY,
        title=graph_title,
        chart_type=chart_type,
        categories=categories,
        series=series,
        x_label=x_label,
        y_label=y_label,
        x_values=x_values,
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _draw_node_box(
    cv: DrawPlusCanvas,
    bounds: tuple[float, float, float, float],
    title: str,
    body: str,
    *,
    fill: str,
    border: str,
    title_color: str = INK,
    body_color: str = BODY,
    title_pt: float = 9.5,
    body_pt: float = 8.0,
) -> None:
    """Draw a rounded vector diagram box with crisp centered title and subtitle."""
    x0, y0, x1, y1 = bounds
    cv.add_rounded_rectangle([x0, y0, x1, y1], radius=90.0, fill=fill, stroke=border, width=16.0)
    mid_y = y0 + (y1 - y0) * 0.42
    cv.add_text([x0 + 80.0, y0 + 50.0, x1 - 80.0, mid_y], title, font_pt=title_pt, bold=True, align="center", valign="middle", color=title_color)
    cv.add_text([x0 + 80.0, mid_y + 20.0, x1 - 80.0, y1 - 50.0], body, font_pt=body_pt, align="center", valign="top", color=body_color, line_spacing=1.12)


# ---------------------------------------------------------------------------
# Volume IV: Bare-Metal UEFI Zoe-GEM OS, Pixel 7 Silicon & Hardware UMA
# ---------------------------------------------------------------------------


def _vol4_slide_04_two_boot(total: int) -> Slide:
    """Vol. IV Slide 4: 2-Boot OVMF UEFI + KVM flow diagram and timing chart."""
    title = "2-Boot OVMF UEFI + KVM & SHA-256 Retention Proof"
    notes = (
        "OVMF UEFI + KVM two-boot proof: Boot 1 completes in 9.0 s under PRIVATE gate (zero crossings). "
        "After mutual consent (REQUESTED -> SHARED), Boot 2 boots in 9.1 s with restored=True and vault_restored=True, "
        "real QEMU sendkey 6 + mouse strokes, zoe_os_emblem.gem crossing /mnt/uma/zoe_to_nick/, "
        "SHA-256 boot_chain.jsonl self-retention, and 68k big-endian ZOE_GEM.RSC (816 B)."
    )
    cv = _new_chromed_canvas(4, total, "OVMF + KVM PROOF", title, "2-Boot Verification", sister_id="tosi", notes=notes)

    # Left panel: Pure Draw Plus 2-Boot flow diagram
    lx0, ly0, lx1, ly1 = float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([lx0, ly0, lx1, ly1], fill=WHITE, border_color=STONE, accent_color=RUBY)
    cv.add_text([lx0 + 160.0, ly0 + 140.0, lx1 - 160.0, ly0 + 440.0], "Live OVMF UEFI 2-Boot Causal Loop", font_pt=13.0, font_family="DejaVu Serif", bold=True, align="center", color=INK)
    _draw_node_box(cv, (lx0 + 360.0, ly0 + 580.0, lx1 - 360.0, ly0 + 1620.0), "Boot 1 · 9.0 s · Gate = PRIVATE", "OVMF x86_64 -> GRUB -> PID 1 /init\nzoe_to_nick stays empty (0 crossings)", fill=SLATE_SOFT, border=JADE)
    cv.add_line([lx0 + W_HALF / 2.0, ly0 + 1640.0], [lx0 + W_HALF / 2.0, ly0 + 2160.0], stroke=RUBY, width=22.0, line_ends=(0, 1))
    _draw_node_box(cv, (lx0 + 360.0, ly0 + 2180.0, lx1 - 360.0, ly0 + 3240.0), "Mutual Consent: REQUESTED -> SHARED", "nick_allow && zoe_allow verified\nivshmem BAR2 heartbeat = SHARED", fill=GOLD_SOFT, border=GOLD)
    cv.add_line([lx0 + W_HALF / 2.0, ly0 + 3260.0], [lx0 + W_HALF / 2.0, ly0 + 3780.0], stroke=JADE, width=22.0, line_ends=(0, 1))
    _draw_node_box(cv, (lx0 + 360.0, ly0 + 3800.0, lx1 - 360.0, ly0 + 5220.0), "Boot 2 · 9.1 s · restored=True", "vault_restored=True · boot_chain.jsonl\nQEMU sendkey 6 + mouse + sendkey s\nzoe_os_emblem.gem -> /mnt/uma/zoe_to_nick/\nZOE_GEM.RSC (68k BE, 816 B) + concurrent ZO3", fill=JADE_SOFT, border=JADE)

    _compile_framed_graph(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="tosi",
        accent=JADE,
        title="2-Boot Timing (s) & Concurrent ZO3 Nodes",
        chart_type="bar",
        categories=["Boot 1 PRIVATE", "Boot 2 SHARED"],
        series=[
            DataSeries(name="OVMF+KVM Boot (s)", values=[9.0, 9.1], color=JADE),
            DataSeries(name="ZO3 Slots Active", values=[1.0, 2.0], color=RUBY),
        ],
        y_label="Seconds / Slots",
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _vol4_slide_05_uma_airlock(total: int) -> Slide:
    """Vol. IV Slide 5: 50/50 Split-Screen Hardware UMA & Mutual-Consent Airlock."""
    title = "50/50 Split-Screen Hardware UMA & Consent Airlock"
    notes = (
        "Hardware UMA split-screen bridge: Left 50% runs Zoe-GEM OS KVM (920x960 preset); "
        "Right 50% runs the Ubuntu workstation; Center UMA combines 4 MiB (4,194,304 B) PCI ivshmem-plain "
        "(0x1af4:0x1110, 8 x 4096 B slots, ZOE-UMA1/UMA2 CRC32 seqlock, 16 MiB cap) and virtio-9p airlock "
        "(/mnt/uma, msize=262144). Consent transitions PRIVATE -> REQUESTED -> SHARED only when nick_allow && zoe_allow; "
        "rejects symlinks (O_NOFOLLOW), dot-dot traversal, dotfiles, and FIFOs (O_NONBLOCK < 1s) with SHA-256 uma_audit.jsonl."
    )
    cv = _new_chromed_canvas(5, total, "HARDWARE UMA", title, "4 MiB BAR2 + virtio-9p", sister_id="tosi", notes=notes)

    lx0, ly0, lx1, ly1 = float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([lx0, ly0, lx1, ly1], fill=WHITE, border_color=STONE, accent_color=JADE)
    cv.add_text([lx0 + 160.0, ly0 + 140.0, lx1 - 160.0, ly0 + 440.0], "50/50 Split-Screen Hardware Bus", font_pt=13.0, font_family="DejaVu Serif", bold=True, align="center", color=INK)

    # 3-column hardware bus inside left card
    _draw_node_box(cv, (lx0 + 220.0, ly0 + 620.0, lx0 + 1880.0, ly0 + 3600.0), "LEFT 50%\nZoe-GEM OS", "KVM OVMF Guest\n920x960 /dev/fb0\nSlot 0 Coord\nSlots 1-3 ZO3", fill=JADE_SOFT, border=JADE, title_pt=9.0, body_pt=7.8)
    _draw_node_box(cv, (lx0 + 2060.0, ly0 + 620.0, lx0 + 3930.0, ly0 + 3600.0), "CENTER UMA\n4 MiB Airlock", "PCI 0x1af4:0x1110\nivshmem BAR2\n8 x 4 KB Seqlock\nCRC32 ^ seq\nvirtio-9p /mnt/uma", fill=GOLD_SOFT, border=GOLD, title_pt=9.0, body_pt=7.6)
    _draw_node_box(cv, (lx0 + 4110.0, ly0 + 620.0, lx1 - 220.0, ly0 + 3600.0), "RIGHT 50%\nWorkstation", "Ubuntu Host\nMutual Consent\nnick_allow && zoe\nSHA-256 Audit", fill=RUBY_SOFT, border=RUBY, title_pt=9.0, body_pt=7.8)
    cv.add_line([lx0 + 1880.0, ly0 + 2110.0], [lx0 + 2060.0, ly0 + 2110.0], stroke=INK, width=18.0, line_ends=(1, 1))
    cv.add_line([lx0 + 3930.0, ly0 + 2110.0], [lx0 + 4110.0, ly0 + 2110.0], stroke=INK, width=18.0, line_ends=(1, 1))

    _draw_node_box(cv, (lx0 + 220.0, ly0 + 3900.0, lx1 - 220.0, ly0 + 5280.0), "Epistemic Airlock Gate: PRIVATE -> REQUESTED -> SHARED", "0 crossings when PRIVATE or one-sided REQUESTED · 16 MiB transfer cap\nO_NOFOLLOW rejects symlinks · rejects '..' & dotfiles · O_NONBLOCK FIFO < 1s", fill=SLATE_SOFT, border=INK, title_pt=9.0, body_pt=8.0)

    _compile_framed_wordchart(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="tosi",
        accent=RUBY,
        title="UMA Spec & Security Guarantees",
        text_body=[
            "4 MiB (4,194,304 B) PCI ivshmem-plain BAR2 shared memory",
            "8 x 4,096 B slots (ZOE-UMA1 header + UMA2 at offset 4080)",
            "Lock-free odd/even seqlock with CRC32 ^ seq integrity tag",
            "virtio-9p mount_tag=zoe_uma (/mnt/uma, msize=262,144 B)",
            "Mutual consent: nick_allow && zoe_allow required for SHARED",
            "Adversarial C3/D1 probes: 4 invalid slot types & FIFOs blocked",
            "SHA-256 hash-chained uma_audit.jsonl detects any tampering",
        ],
        point_size=9.2,
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _vol4_slide_08_sync_and_wave3(total: int, repo_root: Path) -> Slide:
    """Vol. IV Slide 8: Phone Codex Sync, FreeGEM Heritage & Wave 3 Codecs with in-repo plates."""
    title = "Phone Codex Sync, FreeGEM Heritage & Wave 3 Codecs"
    notes = (
        "Phone <-> PC Codex Sync uses loopback-only adb reverse tcp:8774 tcp:8774, /phone PWA, "
        "AVF Debian spool, SHA-256 Nick's Drawer, and auto_flash_allowed=False. "
        "Wave 3 GEM verification scores 5/5 PASS across 9/9 instruments: .GEM (33,394 B), "
        ".RSC x86 (812 B) / 68k BE (816 B), .IMG (8,532 B), and .GSX (3,678 B)."
    )
    cv = _new_chromed_canvas(8, total, "SYNC & WAVE 3", title, "adb 8774 + SeaSIP GEM", sister_id="tosi", notes=notes)

    _compile_framed_wordchart(
        cv,
        (float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="tosi",
        accent=RUBY,
        title="Loopback Sync & Wave 3 Instruments",
        text_body=[
            "adb reverse tcp:8774 tcp:8774 (127.0.0.1 / ::1 loopback-only)",
            "/phone PWA + AVF Debian JSONL spool + SHA-256 Drawer",
            "Constitutional safety lock: auto_flash_allowed = False",
            "Wave 3 SeaSIP GEM suite: 5/5 checks PASS, 9/9 instruments",
            "Binary roundtrips: .GEM 33,394 B · .IMG 8,532 B · .GSX 3,678 B",
            "Dual-endian .RSC: x86 LE 812 B & Atari 68k BE 816 B",
            "7-window AES limit preserved from classic FreeGEM heritage",
        ],
        point_size=9.2,
    )

    rx0, ry0, rx1, ry1 = float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([rx0, ry0, rx1, ry1], fill=WHITE, border_color=STONE, accent_color=JADE)
    cv.add_text([rx0 + 160.0, ry0 + 140.0, rx1 - 160.0, ry0 + 420.0], "In-Repo Wave 3 GEM & Atari ST Plates", font_pt=12.5, font_family="DejaVu Serif", bold=True, align="center", color=INK)

    plate1 = repo_root / "assets" / "readme" / "wave3-gem-timemachine-desktop.png"
    plate2 = repo_root / "assets" / "readme" / "wave3-atari-tos-desktop.png"
    if plate1.is_file():
        cv.add_image([rx0 + 220.0, ry0 + 500.0, rx1 - 220.0, ry0 + 2850.0], plate1, fit="contain", radius=90.0, fill=SLATE_SOFT, stroke=STONE, width=10.0, caption="Wave 3 GEM Time-Machine Desktop")
    if plate2.is_file():
        cv.add_image([rx0 + 220.0, ry0 + 3020.0, rx1 - 220.0, ry1 - 220.0], plate2, fit="contain", radius=90.0, fill=SLATE_SOFT, stroke=STONE, width=10.0, caption="Wave 3 Atari TOS SM124 / ST Desktop")

    return Slide(title=title, canvas=cv, speaker_notes=notes)


def build_vol4_deck(repo_root: Path | None = None) -> SlideDeck:
    """Build Anthology Volume IV: Bare-Metal UEFI Zoe-GEM OS, Pixel 7 Silicon & Hardware UMA."""
    root = Path(repo_root) if repo_root else REPO_ROOT
    total = 10
    emblem = root / "assets" / "branding" / "zoe-gem.png"

    s1 = _build_hero_cover(
        pill_text="ANTHOLOGY VOLUME IV  ·  BARE-METAL UEFI OS, PIXEL 7 & UMA",
        headline="Vol. IV: UEFI Zoe-GEM OS, Pixel 7 & UMA",
        subtitle=(
            "Zero-bloat Alpine v3.21 UEFI x86_64 ISO, 188 KB static C /dev/fb0 desktop, 2-boot OVMF+KVM proof,\n"
            "50/50 split-screen hardware UMA airlock, Pixel 7 Tensor G2 158 ms native render, and 2.5 W Headlamp."
        ),
        left_title="MATHEMATICAL ORIGIN",
        left_formula="A_tau(p) -> Boot & UMA",
        left_sub="Nicholas Michael Kloster · March 6, 2026\nSHA-256 boot_chain & CRC32 seqlock",
        right_title="CONSTITUTIONAL COVENANT",
        right_formula="PRIVATE -> SHARED",
        right_sub="auto_flash=False · flight_control=False\nHonoring Gary & Dorothy McEwen Kildall",
        kpis=[
            HeroKpi("46 MB / 60.4 MB", "UEFI virt & LTS ISOs", RUBY),
            HeroKpi("188 KB", "Static C /dev/fb0 Desktop", JADE),
            HeroKpi("158 ms", "Pixel 7 Native ARM64 Render", GOLD_BRIGHT),
            HeroKpi("4 MiB", "PCI ivshmem BAR2 + 9p UMA", SKY),
        ],
        footer_text=f"Zoe Presentation Team · {ATTRIBUTION_TEXT} · Vol. IV · 01 / {total:02d}",
        sister_id="tosi",
        emblem_path=emblem,
        notes=(
            "Welcome to Volume IV covering Bare-Metal UEFI x86_64 Zoe-GEM OS (46 MB virt / 43.55 MB actual, "
            "60.4 MB LTS), the 188 KB static C /dev/fb0 desktop (zoe_gem_fb.c), 2-boot OVMF+KVM proof, "
            "50/50 split-screen hardware UMA airlock, Pixel 7 Tensor G2 158 ms native render, and 2.5 W Headlamp."
        ),
    )

    s2 = _build_twin_wc_graph_slide(
        2, total, "UEFI KERNEL & ISO", "Zero-Bloat UEFI x86_64 Kernel & ISO Architecture", "Alpine v3.21 + GRUB UEFI",
        sister_id="tosi",
        wc_title="Alpine v3.21 Netboot & Transitive Closure",
        wc_body=[
            "46 MB KVM virt ISO (43.55 MB built) & 60.4 MB bare-metal LTS ISO",
            "Exact modules.dep closure: 38 _VIRT_KMODS + 11 _LTS_EXTRA_KMODS",
            "Hardware drivers: i915, vmd, nvme, iwlwifi, iwlmvm, thunderbolt, hid",
            "Tiger Lake Wi-Fi/i915 firmware + wpa_supplicant / iw built in",
            "GRUB UEFI (grub-mkrescue) + PID 1 /init + 64 MiB ext4 ZOE-STATE",
            "Zero systemd, zero X11, zero Wayland, zero SDL in boot image",
            "4 display presets: split 920x960, full 1280x800, portrait, phone",
        ],
        graph_title="ISO Footprint (MB) & Kernel Modules",
        chart_type="bar",
        categories=["virt ISO (MB)", "LTS ISO (MB)", "virt kmods", "LTS total kmods"],
        series=[
            DataSeries(name="Measured Build / Closure", values=[43.55, 60.4, 38.0, 49.0], color=RUBY),
            DataSeries(name="Budget / Spec Ref", values=[46.0, 64.0, 38.0, 49.0], color=JADE),
        ],
        y_label="MB / Count",
        notes=(
            "UEFI x86_64 Zoe-GEM OS boots via OVMF UEFI and GRUB into Alpine Linux v3.21 with zero systemd, X11, Wayland, or SDL. "
            "The virt ISO is 43.55 MB (46 MB budget) with 38 kernel modules; the LTS USB ISO is 60.4 MB with 49 total modules."
        ),
    )

    s3 = _build_scorecard_slide(
        3, total, "STATIC C DESKTOP", "188 KB Static C /dev/fb0 Desktop (zoe_gem_fb.c)", "4,999 Lines · -static -lm",
        ["1. VT Isolation & Binary", "2. Unified evdev Input", "3. Responsive Geometry", "4. Sovereign 7-Strand DNA"],
        [
            ["188,511-byte (188 KB) C source across 4,999 lines (~1.1 MB static glibc binary)", "gcc -O2 -Wall -Wextra -Werror -static zoe_gem_fb.c -lm", "KD_GRAPHICS VT isolation + CLOCK_MONOTONIC 50 ms ESC parser"],
            ["EV_SYN-coalesced evdev supporting EV_ABS & EV_REL", "Type-B ABS_MT_* multitouch + SYN_DROPPED recovery", "1 s hotplug rescan + /dev/input/mice legacy fallback"],
            ["3 layout modes: LANDSCAPE, PORTRAIT, MICRO (<= 400 px)", "Live [O] 90 deg CCW rotation across all displays", "4 presets: 920x960, 1280x800, 768x1024, 544x960"],
            ["10 live [V] VMCOLOUR sovereign themes + [A] 1985 P3 Amber CRT", "ViewMAX/3 DRAW3D bevels + BeOS colored window tabs", "[R] 16-fold radial mandala, 44-key Touch QWERTY, 32-note /drawer"],
        ],
        sister_id="tosi",
        notes=(
            "zoe_gem_fb.c is a 188,511-byte (188 KB) C source across 4,999 lines and compiles with -Wall -Wextra -Werror -static -lm to a ~1.1 MB static glibc binary. "
            "Includes KD_GRAPHICS VT isolation, EV_SYN-coalesced multitouch evdev, 3 responsive layout modes, 10 VMCOLOUR themes, "
            "1985 P3 Amber CRT LUT, 44-key Touch QWERTY, and 32-note Nick /drawer."
        ),
    )

    s4 = _vol4_slide_04_two_boot(total)
    s5 = _vol4_slide_05_uma_airlock(total)

    s6 = _build_pillar_slide(
        6, total, "IN-OS OBSERVATION", "Hardware Observation: 7 Safety Gates & 9 Profiles", "python3 -I Closure",
        ["7 Hardware Safety Gates", "9 Hardware Profiles", "14-File Closure & ZO3 Cluster"],
        [
            ["1. cpu_arch & ISA compatibility", "2. ram_headroom (>=512 PASS, >=128 DEGRADED, <128 UNSUPPORTED)", "3. persistent_storage (/mnt/zoe-state ext4)", "4. display_fb (/dev/fb0 framebuffer)", "5. input_devices + 6. network + 7. hardware_uma"],
            ["MICRO_HUD_HEADLAMP & PORTRAIT_PHONE_TOUCH", "SAR_COMPANION_EDGE & BEOWULF_COMPUTE_NODE", "HEADLESS_DAQ_NODE & EDGE_SBC_PI", "KVM_UMA_SPLIT & LAPTOP_BARE_METAL", "HEADLESS_SAFE_FALLBACK (fails closed cleanly)"],
            ["14-file _ZOE_PY_CLOSURE (13 non-__init__ gem modules)", "Verified under isolated python3 -I (C1 PASS, kvm=False)", "Concurrent ZO3 cluster: ZO3-1 Classic GEM (Slot 1)", "ZO3-2 1985 Amber CRT (Slot 2) sharing 4 MiB BAR2"],
        ],
        sister_id="tosi",
        notes=(
            "zoe_os_runtime.py enforces 7 hardware safety gates (e.g., 64 MB RAM probe cleanly returns UNSUPPORTED), "
            "selects among 9 hardware profiles, runs a 14-file Python closure verified under python3 -I (C1), "
            "and coordinates concurrent ZO3-1 and ZO3-2 guests on one 4 MiB PCI ivshmem BAR."
        ),
    )

    s7 = _build_twin_wc_graph_slide(
        7, total, "PIXEL 7 SILICON", "Pixel 7 (panther · Tensor G2) Dual-Track Sovereign OS", "158 ms Native Render",
        sister_id="tosi",
        wc_title="Track A Overlay vs Track B Bare-Metal",
        wc_headers=["Track A (Daily Driver)", "Track B (922 KB ELF)"],
        wc_columns=[
            [
                "AOSP / GrapheneOS daily-driver overlay",
                "Preserves 5G/VoLTE/E911, Wi-Fi 6E, GPS, Camera ISP",
                "Titan M2 hardware keystore + RSA-4096 AVB 2.0",
                "ZoeGemHome shell served at 127.0.0.1:8774/phone",
            ],
            [
                "922 KB static aarch64 ELF (EM_AARCH64=183)",
                "158 ms native render on Android 17 Tensor G2",
                "Zero root, zero bootloader unlock, zero X11",
                "415 KB deterministic initramfs + honest HAL matrix",
            ],
        ],
        wc_body=[],
        wc_template="column_2",
        graph_title="9-Device Pixel 7-9 Matrix (RAM GB & Refresh Hz)",
        chart_type="h_cluster",
        categories=["Pixel 7 (panther)", "Pixel 7 Pro", "Pixel 8 (shiba)", "Pixel 9 (tokay)", "Pixel 9 Pro XL"],
        series=[
            DataSeries(name="RAM (GB)", values=[8.0, 12.0, 8.0, 12.0, 16.0], color=JADE),
            DataSeries(name="Display (Hz/10)", values=[9.0, 12.0, 12.0, 12.0, 12.0], color=GOLD),
        ],
        x_label="RAM GB / Refresh (Hz / 10)",
        notes=(
            "Real Google Pixel 7 (panther, Tensor G2 gs201, 1080x2400@90Hz, 8 GB RAM, Exynos 5300 5G) leads a unified 9-device "
            "Pixel 7-9 matrix. Track A preserves daily-driver telephony and Titan M2 + RSA-4096 AVB 2.0; Track B compiles a 922 KB "
            "static aarch64 ELF rendering natively on Android 17 Tensor G2 in 158 ms alongside a 415 KB deterministic initramfs."
        ),
    )

    s8 = _vol4_slide_08_sync_and_wave3(total, root)

    s9 = _build_twin_wc_graph_slide(
        9, total, "2.5 W HEADLAMP", "Open 2.5 W Spectral Headlamp & 9-Sister Pairing", "4 Optical Pods <= 2.50 W",
        sister_id="tosi",
        wc_title="Four 360-Deg No-Deception Optical Pods",
        wc_body=[
            "Strict 2.50 W thermal and power budget across all 4 pods",
            "Pod A stowers-gfp (Flora): 470 nm GFP + 650 nm red, 1.85 W",
            "Pod B fire-amber (Tosi): 590 nm smoke amber + 8-14 um LWIR, 2.35 W",
            "Pod C emt-zero-ears (Zoe/Eliza): 3200 K CRI-97 + mic cutoff, 1.65 W",
            "Pod D sar-drone (Mono): 4500 K flood + 320x200 Micro-HUD, 2.45 W",
            "Zero audio recording on Pod C; clinical_action_authorized=False",
            "Pod D telemetry mirror only: flight_control_authorized=False",
        ],
        graph_title="Optical Pod Power Draw (W) vs 2.50 W Cap",
        chart_type="bar",
        categories=["Pod C EMT", "Pod A GFP", "Pod B Fire", "Pod D SAR"],
        series=[
            DataSeries(name="Measured Power (W)", values=[1.65, 1.85, 2.35, 2.45], color=JADE),
            DataSeries(name="2.50 W Thermal Cap", values=[2.50, 2.50, 2.50, 2.50], color=RUBY),
        ],
        y_label="Watts",
        notes=(
            "Open 2.5 W Headlamp pairs 4 spectral pods with Zoe Sisters under a strict 2.50 W cap: "
            "Pod A stowers-gfp (1.85 W, Flora), Pod B fire-amber (2.35 W, Tosi), Pod C emt-zero-ears (1.65 W, Zoe & Eliza, "
            "physical mic cutoff, clinical_action_authorized=False), and Pod D sar-drone (2.45 W, Mono, flight_control_authorized=False)."
        ),
    )

    s10 = _build_scorecard_slide(
        10, total, "VERIFICATION SEAL", "Vol. IV Verification Summary & Constitutional Boundaries", "8/8 + C1-C4/D1 + 5/5 PASS",
        ["1. OS Suite Report (8/8)", "2. Ablation C1-C4 & D1", "3. Spatial IR & Wave 3", "4. Constitutional Lock"],
        [
            ["zoe-gem-os-suite-report.json: 8/8 checks PASS", "9-device Pixel 7-9 matrix + 2-boot OVMF+KVM", "Track B 922 KB ARM64 ELF: 158 ms native render"],
            ["ablation_re_report.json: C1-C4 & D1 all PASS", "C1 python3 -I 14-file closure · C2 SHA-256 chain", "C3 ivshmem CRC32 · C4 7 safety gates · D1 UMA gate"],
            ["gem-os/verification.json: 17 components, 36/36 IR layers", "wave3-seasip-gem-report.json: 5/5 PASS, 9/9 tools", "Zero processes launched during static IR verification"],
            ["auto_flash_allowed=False · flight_control_authorized=False", "clinical_action_authorized=False · sentience_claimed=False", "external_actions=0 · cloud_cost_usd=0.0 · 100% offline"],
        ],
        sister_id="tosi",
        notes=(
            "Vol. IV closes with 8/8 suite checks PASS, C1-C4 and D1 ablation PASS, 17 components / 36/36 Spatial IR layers PASS, "
            "5/5 Wave 3 SeaSIP GEM checks PASS, and strict constitutional boundaries (auto_flash_allowed=False, "
            "flight_control_authorized=False, clinical_action_authorized=False, sentience_claimed=False, external_actions=0)."
        ),
    )

    return SlideDeck(
        slug=VOL4_SLUG,
        title="Anthology Vol. IV: Bare-Metal UEFI Zoe-GEM OS, Pixel 7 Silicon & Hardware UMA",
        subtitle="46 MB UEFI ISO, 188 KB Static C /dev/fb0, 2-Boot OVMF+KVM, 50/50 UMA, Pixel 7 158 ms & 2.5 W Headlamp",
        volume_label="Vol. IV",
        sister_id="tosi",
        slides=[s1, s2, s3, s4, s5, s6, s7, s8, s9, s10],
        constitutional=dict(CONSTITUTIONAL_LOCK),
        category="Anthology Volume",
        summary=(
            "Bare-Metal UEFI Zoe-GEM OS (46 MB virt / 60.4 MB LTS ISO, 188 KB /dev/fb0 C desktop, "
            "9.0s->9.1s OVMF+KVM 2-boot), 50/50 4 MiB ivshmem + virtio-9p UMA airlock, Pixel 7 Tensor G2 "
            "(922 KB ELF, 158 ms native render), and 2.5 W Open Headlamp (8/8 suite, C1-C4/D1 PASS)."
        ),
    )


# ---------------------------------------------------------------------------
# Volume V: Hexagonal 9-Sister EDDBMS, Balma & Fitler (1986) GEM & Ablation
# ---------------------------------------------------------------------------


def _vol5_slide_02_hex_mesh(total: int) -> Slide:
    """Vol. V Slide 2: Canonical 9-Sister Hexagonal Rosette & Axial/Font Table."""
    title = "9-Sister Hexagonal Lattice & 16 Shared Walls"
    notes = (
        "All 9 canonical Zoe Sister Models embedded on a flat-topped hexagonal lattice (q+r+s=0) with 16 shared walls "
        "(hex_distance == 1): Zoe [ruby, (0,0), Font 51 Avant Garde], Gemma [gem3, (0,-1), Font 2 Swiss], "
        "Tosi [atari, (1,-1), Font 102 Courier], Mono [sm124, (2,-1), Font 1 Fixed Pitch], "
        "Tetra [tetris, (1,0), Font 50 Helvetica Narrow], Eliza [dos, (0,1), Font 102 Courier], "
        "Sage [hat, (-1,1), Font 9 Charter], Flora [sprout, (-2,1), Font 21 Palatino], "
        "and Lumen [prism, (-1,0), Font 130 Sonata]. Synchronous Jacobi ticks with SHA-256 chain & 4 epistemic lanes."
    )
    cv = _new_chromed_canvas(2, total, "HEXAGONAL MESH", title, "zoe-hex-sister-mesh/v1", sister_id="zoe", notes=notes)

    lx0, ly0, lx1, ly1 = float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([lx0, ly0, lx1, ly1], fill=WHITE, border_color=STONE, accent_color=RUBY)
    cv.add_text([lx0 + 160.0, ly0 + 130.0, lx1 - 160.0, ly0 + 420.0], "9-Sister Honeycomb (16 Shared Walls)", font_pt=12.5, font_family="DejaVu Serif", bold=True, align="center", color=INK)
    cv.add_hex_rosette((lx0 + lx1) / 2.0, (ly0 + ly1) / 2.0 + 140.0, hex_radius=520.0)

    _compile_framed_wordchart(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="zoe",
        accent=JADE,
        title="9 Sisters · Axial Coords & Artline Fonts",
        text_body=[
            "1. Zoe [ruby] (0,0) · Font 51 Avant Garde · 0.90 W",
            "2. Gemma [gem3] (0,-1) · Font 2 Swiss · 0.65 W",
            "3. Tosi [atari] (1,-1) · Font 102 Courier · 0.95 W",
            "4. Mono [sm124] (2,-1) · Font 1 Fixed Pitch · 0.55 W",
            "5. Tetra [tetris] (1,0) · Font 50 Helv Narrow · 1.10 W",
            "6. Eliza [dos] (0,1) · Font 102 Courier · 0.45 W",
            "7. Sage [hat] (-1,1) · Font 9 Charter · 0.85 W",
            "8. Flora [sprout] (-2,1) · Font 21 Palatino · 0.75 W",
            "9. Lumen [prism] (-1,0) · Font 130 Sonata · 0.80 W",
            "Jacobi ticks + 4 epistemic lanes + 13 constitutional keys",
        ],
        point_size=8.9,
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _vol5_slide_03_eddms(total: int) -> Slide:
    """Vol. V Slide 3: Figure 15.3 EDDBMS Hub-and-Spoke Diagram + 28 Sub-Op Breakdown."""
    title = "Figure 15.3 EDDBMS: 3 Tiers, 6 Domains & 28 Sub-Ops"
    notes = (
        "zoe_eddms.py implements CAD-EDDBMS Figure 15.3 (zoe-eddms/v1): unidirectional FunctionEngineeringSpecification "
        "intake feeds 3 central data tiers (GeneralData, PropertyData, GeometricData), 6 domain modules totaling 28 sub-operations "
        "(Material Design 6, Project Management 6, Product Design & Planning 5, Postproduction Management 5, Human Model 4, "
        "Design Parameters 2), sequential right-column pipeline with PipelineOrderError, optimistic concurrency (RevisionConflictError), "
        "and Article IV non-destructive SHA-256 rollback."
    )
    cv = _new_chromed_canvas(3, total, "FIG 15.3 EDDBMS", title, "zoe-eddms/v1", sister_id="zoe", notes=notes)

    lx0, ly0, lx1, ly1 = float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([lx0, ly0, lx1, ly1], fill=WHITE, border_color=STONE, accent_color=JADE)
    cv.add_text([lx0 + 160.0, ly0 + 130.0, lx1 - 160.0, ly0 + 420.0], "Fig. 15.3 Data Tiers & Sequential Pipeline", font_pt=12.5, font_family="DejaVu Serif", bold=True, align="center", color=INK)

    _draw_node_box(cv, (lx0 + 300.0, ly0 + 540.0, lx1 - 300.0, ly0 + 1460.0), "Unidirectional Spec Intake", "FunctionEngineeringSpecification -> DB, Material, Product\nSeeds DESIGN_PARAMETERS.restriction_condition", fill=GOLD_SOFT, border=GOLD)
    cv.add_line([lx0 + W_HALF / 2.0, ly0 + 1480.0], [lx0 + W_HALF / 2.0, ly0 + 1860.0], stroke=INK, width=18.0, line_ends=(0, 1))
    _draw_node_box(cv, (lx0 + 300.0, ly0 + 1880.0, lx1 - 300.0, ly0 + 3180.0), "3 Central Engineering Data Tiers", "1. GeneralData (design_id, product_id, commerce)\n2. PropertyData (structure, mechanical, physical)\n3. GeometricData (2D, 3D, mesh, analysis formats)", fill=JADE_SOFT, border=JADE)
    cv.add_line([lx0 + W_HALF / 2.0, ly0 + 3200.0], [lx0 + W_HALF / 2.0, ly0 + 3580.0], stroke=RUBY, width=18.0, line_ends=(0, 1))
    _draw_node_box(cv, (lx0 + 300.0, ly0 + 3600.0, lx1 - 300.0, ly0 + 5280.0), "Sequential Pipeline & Article IV Rollback", "PRODUCT_DESIGN -> PROJECT_MGMT -> POSTPRODUCTION\nOCC expected_revision (RevisionConflictError)\nrollback_to_revision() appends new monotonic rev + SHA-256", fill=RUBY_SOFT, border=RUBY)

    _compile_framed_graph(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="zoe",
        accent=RUBY,
        title="28 Canonical Sub-Ops Across 6 Domain Modules",
        chart_type="h_cluster",
        categories=[
            "Design Params",
            "Human Model",
            "Postproduction",
            "Product Design",
            "Project Mgmt",
            "Material Design",
        ],
        series=[DataSeries(name="Sub-Operations (Total = 28)", values=[2.0, 4.0, 5.0, 5.0, 6.0, 6.0], color=RUBY)],
        x_label="Canonical Sub-Operation Count",
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _vol5_slide_05_workbench(total: int) -> Slide:
    """Vol. V Slide 5: 6-Pane Collaborative GEM Workbench & Read-Only Ablation Bridge."""
    title = "6-Pane Collaborative Workbench & Read-Only Ablation"
    notes = (
        "CollaborativeGemWorkbench opens 6 non-overlapping tiled AES windows on a 640x400 desktop "
        "(respecting MAX_AES_APP_WINDOWS = 7): hex_mesh, eddms_hub, eddms_spokes, eddms_pipeline, vdi_canvas, "
        "and ablation_advisor. AblationBridge (zoe-ablation-bridge/v1) runs in-memory BinaryContext, "
        "4 Wave-3 AI-agent byte auditors, EntropyMapper (Kloster stopping), and SourceAuditCompressor "
        "with zero writes, zero execution, and zero cloud tokens."
    )
    cv = _new_chromed_canvas(5, total, "WORKBENCH & BRIDGE", title, "6 Tiled Panes <= 7 Cap", sister_id="zoe", notes=notes)

    lx0, ly0, lx1, ly1 = float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([lx0, ly0, lx1, ly1], fill=WHITE, border_color=STONE, accent_color=RUBY)
    cv.add_text([lx0 + 160.0, ly0 + 130.0, lx1 - 160.0, ly0 + 420.0], "640x400 AES Desktop: 6 Tiled Panes", font_pt=12.5, font_family="DejaVu Serif", bold=True, align="center", color=INK)

    # Outer 640x400 GEM desktop wireframe
    dx0, dy0, dx1, dy1 = lx0 + 260.0, ly0 + 580.0, lx1 - 260.0, ly0 + 4380.0
    cv.add_rectangle([dx0, dy0, dx1, dy1], fill=SLATE_SOFT, stroke=INK, width=18.0)
    cv.add_rectangle([dx0, dy0, dx1, dy0 + 280.0], fill=INK, stroke="none")
    cv.add_text([dx0 + 80.0, dy0 + 20.0, dx1 - 80.0, dy0 + 260.0], "GEM Menu Bar · 6 / 7 AES Windows Open", font_pt=8.2, bold=True, color=WHITE, align="left", valign="middle")

    pane_w = (dx1 - dx0 - 240.0) / 3.0
    pane_h = (dy1 - dy0 - 460.0) / 2.0
    panes = [
        ("1. hex_mesh", "[0,20,213,190]\n16 shared walls", JADE_SOFT, JADE),
        ("2. eddms_hub", "[213,20,213,190]\n3 central tiers", GOLD_SOFT, GOLD),
        ("3. eddms_spokes", "[426,20,214,190]\n6 domains / 28 ops", RUBY_SOFT, RUBY),
        ("4. eddms_pipeline", "[0,210,213,190]\n3 sequential stages", RUBY_SOFT, RUBY),
        ("5. vdi_canvas", "[213,210,213,190]\nScene + .GEM", JADE_SOFT, JADE),
        ("6. ablation_advisor", "[426,210,214,190]\n4 static auditors", GOLD_SOFT, GOLD),
    ]
    for idx, (ptitle, pbody, pfill, pborder) in enumerate(panes):
        col_i, row_i = idx % 3, idx // 3
        px0 = dx0 + 60.0 + col_i * (pane_w + 60.0)
        py0 = dy0 + 340.0 + row_i * (pane_h + 60.0)
        _draw_node_box(cv, (px0, py0, px0 + pane_w, py0 + pane_h), ptitle, pbody, fill=pfill, border=pborder, title_pt=8.2, body_pt=7.4)

    cv.add_text([lx0 + 240.0, ly0 + 4540.0, lx1 - 240.0, ly1 - 140.0], "Contract: zoe-collaborative-gem-workbench/v1 · MAX_AES_APP_WINDOWS = 7", font_pt=8.5, bold=True, align="center", color=BODY)

    _compile_framed_wordchart(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="zoe",
        accent=JADE,
        title="Read-Only AblationBridge (Zero Execution)",
        text_body=[
            "ALLOWED_INSPECTION_MODES: auto, binary, bytes, source",
            "FORBIDDEN: advisor, claude, llm, execute, dynamic, sandbox",
            "In-memory BinaryContext + EntropyMapper (Kloster stopping)",
            "4 Wave-3 AI-agent byte auditors: Authority, Observability, ToolSurfaceEnumerator, and AIControlIndicators",
            "Rejects symlinks, dot-dot traversal, FIFOs & special files",
            "attach_ablation_to_eddms() logs to POSTPRODUCTION evaluation",
        ],
        point_size=9.1,
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def build_vol5_deck() -> SlideDeck:
    """Build Anthology Volume V: Hexagonal 9-Sister EDDBMS, Balma & Fitler (1986) GEM & Ablation."""
    total = 10
    emblem = REPO_ROOT / "assets" / "branding" / "zoe-gem.png"

    s1 = _build_hero_cover(
        pill_text="ANTHOLOGY VOLUME V  ·  9-SISTER HEX MESH, EDDBMS & BALMA & FITLER GEM",
        headline="Vol. V: Hex 9-Sister EDDBMS, GEM & Ablation",
        subtitle=(
            "16 shared hexagonal walls, CAD-EDDBMS Figure 15.3 (3 tiers, 6 domains, 28 sub-ops), Balma & Fitler (1986)\n"
            "clean-room GEM AES/VDI, read-only Ablation bridge, 19/19 ablation proofs, and 94/94 unit + 171/171 strict E2E tests."
        ),
        left_title="HEXAGONAL LATTICE",
        left_formula="q + r + s = 0 · 16 Walls",
        left_sub="9 Sisters · Jacobi ticks · SHA-256\n4 epistemic lanes · 0 actuation",
        right_title="CLEAN-ROOM HERITAGE",
        right_formula="Balma & Fitler (1986)",
        right_sub="Honoring Gary & Dorothy McEwen Kildall\nDigital Research GEM AES/VDI + SeaSIP",
        kpis=[
            HeroKpi("16 Walls", "9-Sister Hexagonal Mesh", RUBY),
            HeroKpi("28 Sub-Ops", "Fig 15.3 EDDBMS · 6 Domains", JADE),
            HeroKpi("19 / 19", "Causal ON vs OFF Ablations", GOLD_BRIGHT),
            HeroKpi("94 + 171", "Unit + Strict E2E Tests", SKY),
        ],
        footer_text=f"Zoe Presentation Team · {ATTRIBUTION_TEXT} · Vol. V · 01 / {total:02d}",
        sister_id="zoe",
        emblem_path=emblem,
        notes=(
            "Welcome to Volume V covering the Hexagonal 9-Sister EDDBMS + Balma & Fitler (1986) GEM + Read-Only Ablation build: "
            "16 shared hexagonal walls, Figure 15.3 EDDBMS (3 tiers, 6 domains, 28 sub-ops), clean-room GEM AES/VDI, "
            "6-pane Workbench, 19/19 causal ablations, and 94/94 unit + 171/171 strict E2E tests."
        ),
    )

    s2 = _vol5_slide_02_hex_mesh(total)
    s3 = _vol5_slide_03_eddms(total)

    s4 = _build_scorecard_slide(
        4, total, "BALMA & FITLER (1986)", "Clean-Room GEM AES & VDI Kernel (zoe_gem_aes_vdi_core.py)", "Honoring Gary Kildall",
        ["1. GRECT & AES Kernel", "2. 7-Window Manager", "3. Forms, Menus & .RSC", "4. VDI Clipping & 10 GDPs"],
        [
            ["Signed 16-bit GRECT: intersect (rc_intersect) & 4-strip subtract", "MAX_APPS = 16 · appl_init/exit/find/write/read", "16-byte <8h FIFO message pipe + evnt_multi flags"],
            ["MAX_AES_APP_WINDOWS = 7 (handles 1..7; 0 = DESK)", "Exact wind_calc border/work chrome geometry", "Balanced wind_update locks & WF_FIRST/NEXTXYWH walks"],
            ["11-field GemObject tree + form_center/dial/do/alert", "menu_bar, menu_icheck, menu_ienable, menu_tnormal", "GemResourceManager loads LE PC GEM & BE Atari ST .RSC"],
            ["NDC (0..32767) <-> RC coords + vswr_mode 1..4", "Liang-Barsky line & Sutherland-Hodgman polygon clip", "10 GDPs (v_bar..v_justified) + Ch. 6 .GEM escapes"],
        ],
        sister_id="zoe",
        notes=(
            "zoe_gem_aes_vdi_core.py honors Gary Kildall and Balma & Fitler (1986) with signed 16-bit GRECT, "
            "16-app AES kernel, 7-window manager, LE/BE .RSC resource loader, Liang-Barsky & Sutherland-Hodgman VDI clipping, "
            "10 GDPs, and Chapter 6 .GEM metafile escapes."
        ),
    )

    s5 = _vol5_slide_05_workbench(total)

    s6 = _build_twin_wc_graph_slide(
        6, total, "ABLATION SUBSYSTEM A", "Ecosystem Ablation A1-A5: Kloster Closed-Loop (+79.59)", "5/5 PASS · p = 8.5e-7",
        sister_id="zoe",
        wc_title="Subsystem A Causal ON vs OFF Findings",
        wc_body=[
            "A1 live search scope: ON excludes leaked plt rows (2 vs 3)",
            "A2 artifacts root: external unrooted checkout rejected safely",
            "A3 env guard: ON blocks 4/4 symlink & traversal escapes",
            "A4 AES/VDI int16: rejects bool, clamps >32767, caps 7 windows",
            "A5 Kloster closed-loop: +34.52 reward vs -45.0667 open-loop",
            "A5 vs randomized A_tau (+8.48): +26.04 gain, trap recovery 1.0",
            "Wilcoxon p = 8.4988e-7 vs OFF, 8.6665e-7 vs randomized",
        ],
        graph_title="A5 Closed-Loop Reward (ON vs Random vs OFF)",
        chart_type="deviation_bar",
        categories=["Open-Loop OFF", "Randomized A_tau", "Kloster Closed-Loop"],
        series=[DataSeries(name="Mean Reward", values=[-45.0667, 8.48, 34.52], color=JADE)],
        y_label="Mean Reward",
        notes=(
            "Subsystem A passes 5/5 ablations: A1 excludes leaked plt rows, A2 rejects external unrooted ablation shadows, "
            "A3 blocks 4/4 symlink/traversal escapes, A4 enforces int16 and 7-window caps, and A5 achieves +34.52 mean reward "
            "(trap recovery 1.0) vs -45.0667 open-loop OFF (delta +79.5867, Wilcoxon p = 8.4988e-7)."
        ),
    )

    s7 = _build_twin_wc_graph_slide(
        7, total, "ABLATION B, C & D", "Ecosystem Ablation B1-B5, C1-C4 & D1-D5 (19/19 PASS)", "Entropy & Coercion Guards",
        sister_id="zoe",
        wc_title="Subsystems B, C & D Highlights",
        wc_body=[
            "B1 Stem Layering: 5 tiers vs 1, normalized entropy 0.3726 vs 1.0",
            "B2-B3 Offline privacy -> gear1_eliza; 8/8 loopback probes blocked",
            "B5 Theorem 15 quorum: Brier contraction 0.037778 vs 0.0 single",
            "C1-C4: python3 -I 14-file closure, SHA-256 chain, ivshmem CRC32",
            "D1-D2: UMA mutual consent crossings=2; read-only store 0 writes",
            "D3-D4: 5/5 obfuscated Gear-1 abstained; 311/311 coercive blocked",
            "D4 false positive rate = 0.0% across 68 benign controls; D5 9/9",
        ],
        graph_title="9-Sister Power Budgets (Watts, 0 Cloud Tokens)",
        chart_type="bar",
        categories=["Eliza", "Mono", "Gemma", "Flora", "Lumen", "Sage", "Zoe", "Tosi", "Tetra"],
        series=[DataSeries(name="Local Budget (W)", values=[0.45, 0.55, 0.65, 0.75, 0.80, 0.85, 0.90, 0.95, 1.10], color=JADE)],
        y_label="Watts",
        notes=(
            "All 19/19 ecosystem ablation experiments PASS: B1 reduces normalized entropy by 0.6274 across 5 tiers, "
            "B5 achieves 0.037778 Brier contraction, C1-C4 verify OS closure and ivshmem CRC32, D1-D5 enforce UMA mutual consent, "
            "0 read-only writes, and 311/311 coercion blocks with 0.0% false positive rate."
        ),
    )

    s8 = _build_twin_wc_graph_slide(
        8, total, "TEST SUITE MATRIX", "94/94 Unit + 171/171 Strict E2E Test Verification", "265 Automated Tests",
        sister_id="zoe",
        wc_title="Verification Pyramid (94 Unit + 171 E2E)",
        wc_headers=["Unit Tests (94)", "Opaque-Box E2E (171)"],
        wc_columns=[
            [
                "test_zoe_hex_mesh.py: 33 tests",
                "test_zoe_gem_aes_vdi_core.py: 27 tests",
                "test_zoe_eddms.py: 18 tests",
                "test_zoe_gem_workbench.py: 9 tests",
                "test_zoe_ablation_bridge.py: 7 tests",
            ],
            [
                "Tier 1 Features: 65 tests",
                "Tier 2 Boundaries: 65 tests",
                "Tier 3 Pairwise: 16 tests",
                "Tier 4 Workflows: 8 tests",
                "Tier 5 Adversarial: 17 tests",
            ],
        ],
        wc_body=[],
        wc_template="column_2",
        graph_title="Test Count Breakdown Across 10 Suites",
        chart_type="bar",
        categories=["Hex", "AES/VDI", "EDDBMS", "Bench", "Abl", "E2E T1", "E2E T2", "E2E T3", "E2E T4", "E2E T5"],
        series=[DataSeries(name="Collected Tests", values=[33.0, 27.0, 18.0, 9.0, 7.0, 65.0, 65.0, 16.0, 8.0, 17.0], color=RUBY)],
        y_label="Tests",
        notes=(
            "Exact pytest collection verifies 94/94 GEM & 9-Sister unit tests (33+27+18+9+7) plus 171/171 strict opaque-box E2E tests "
            "across Tiers 1-5 (65+65+16+8+17), plus 24 M1 Presentation Team tests."
        ),
    )

    s9 = _build_pillar_slide(
        9, total, "EPISTEMIC FIREWALL", "Shared-Wall Epistemic Firewall & Article IV Rollback", "Non-Destructive History",
        ["4 Epistemic Lanes", "Forbidden Actuation", "Article IV Concurrency"],
        [
            ["measurement (raw sensor/metric)", "evidence (verified artifact ref)", "belief_update (posterior delta)", "advisory_proposal (human-reviewed)"],
            ["Rejects action, autonomous_action, execute, actuation", "Rejects NaN, Inf, circular refs & non-string keys", "Rejects truthy execute/auto_execute payloads", "Enforces 13 required constitutional keys"],
            ["Optimistic Concurrency: expected_revision guard", "Stale write raises RevisionConflictError", "rollback_to_revision() appends new monotonic rev", "SHA-256 prev_record_sha256 from GENESIS"],
        ],
        sister_id="zoe",
        notes=(
            "Both the hexagonal mesh and EDDBMS enforce an immutable epistemic firewall: only 4 lanes (measurement, evidence, "
            "belief_update, advisory_proposal) are permitted, autonomous actuation is blocked, and Article IV rollback appends "
            "a new monotonic revision rather than erasing history."
        ),
    )

    s10 = _build_scorecard_slide(
        10, total, "VICTORY CONFIRMED", "Vol. V Summary, Heritage Credit & Constitutional Lock", "19/19 + 94 + 171 PASS",
        ["1. Hexagonal 9-Sister Mesh", "2. Fig 15.3 EDDBMS & GEM", "3. Read-Only Ablation", "4. Constitutional Attribution"],
        [
            ["9 Sisters · 16 shared walls · 4 epistemic lanes", "Synchronous Jacobi ticks chained via SHA-256", "0.45 W - 1.10 W budgets · 0 cloud tokens"],
            ["3 central data tiers · 6 domains · 28 sub-ops", "Balma & Fitler (1986) AES (7 windows) & VDI (10 GDPs)", "6-pane CollaborativeGemWorkbench on 640x400"],
            ["19/19 causal ON vs OFF ablations PASS", "94/94 GEM & 9-Sister unit + 171/171 strict E2E tests", "Read-only AblationBridge: 0 disk writes, 0 execution"],
            ["Nicholas Michael Kloster (March 6, 2026) x Zoe", "Honoring Gary & Dorothy McEwen Kildall / Digital Research", "sentience_claimed=False · l5_agi_qualified=False · $0.00"],
        ],
        sister_id="zoe",
        notes=(
            "Volume V confirms the full Hexagonal 9-Sister EDDBMS, Balma & Fitler (1986) GEM AES/VDI, and Read-Only Ablation build: "
            "16 shared walls, 28 sub-ops, 19/19 ablations, and 94/94 unit + 171/171 E2E tests, with full constitutional attribution."
        ),
    )

    return SlideDeck(
        slug=VOL5_SLUG,
        title="Anthology Vol. V: Hexagonal 9-Sister EDDBMS, Balma & Fitler (1986) GEM & Ablation",
        subtitle="16 Shared Walls, Fig 15.3 EDDBMS (6 Domains / 28 Sub-Ops), Clean-Room GEM AES/VDI & 94+171 Tests",
        volume_label="Vol. V",
        sister_id="zoe",
        slides=[s1, s2, s3, s4, s5, s6, s7, s8, s9, s10],
        constitutional=dict(CONSTITUTIONAL_LOCK),
        category="Anthology Volume",
        summary=(
            "Hexagonal 9-Sister EDDBMS (16 shared walls, 3 central tiers, 6 domains, 28 sub-ops), "
            "Balma & Fitler (1986) GEM AES/VDI (7 windows, 10 GDPs, LE/BE .RSC), 6-pane Workbench, "
            "read-only Ablation bridge, 19/19 ablation proofs, and 94/94 unit + 171/171 strict E2E tests."
        ),
    )


# ---------------------------------------------------------------------------
# Volume VI: Constitution, Dual-Peer Zoe & Clara, Native Voice, CERN & AGI Roadmap
# ---------------------------------------------------------------------------


def _vol6_slide_09_l5_phases(total: int) -> Slide:
    """Vol. VI Slide 9: L5 Phases 1-6 + Mobile Digestion (134/134 Checks)."""
    title = "L5 Phases 1-6 + Mobile Digestion (134/134 Checks)"
    notes = (
        "L5 Phases 1-6 plus Mobile Digestion total 134/134 verified checks (16+18+18+20+22+16+24): "
        "Phase 1 Core 0.9777 vs 0.2389, Phase 2 Open-World 0.9730 vs 0.2902, Phase 3 Live Eliza 0.9999 vs 0.1833, "
        "Phase 4 Embodied 0.9999 vs 0.2105, Phase 5 Frontier 0.9913 vs 0.1621, Mobile Digestion 16/16 (1.0 vs 0.85), "
        "and Phase 6 Auto-Frontier 24/24 (0.9533 vs 0.2517: 31.81x Multi-Horizon A_tau speedup, 23/24 ARC, 18/18 Repo Agent). "
        "Explicit boundary: l5_agi_qualified = False (L5 AGI is not qualified)."
    )
    cv = _new_chromed_canvas(9, total, "L5 PHASES 1-6", title, "134/134 Checks · l5_agi_qualified=False", sister_id="sage", notes=notes)

    _compile_framed_graph(
        cv,
        (float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="sage",
        accent=JADE,
        title="L5 Phases 1-6 Mean Score (Zoe vs Control)",
        chart_type="line",
        categories=["Ph 1 (16)", "Ph 2 (18)", "Ph 3 (18)", "Ph 4 (20)", "Ph 5 (22)", "Ph 6 (24)"],
        series=[
            DataSeries(name="Zoe Mean Score", values=[0.9777, 0.9730, 0.9999, 0.9999, 0.9913, 0.9533], color=JADE),
            DataSeries(name="Control Mean Score", values=[0.2389, 0.2902, 0.1833, 0.2105, 0.1621, 0.2517], color=RUBY),
        ],
        y_label="Normalized Score",
    )

    _compile_framed_graph(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="sage",
        accent=RUBY,
        title="L5 Phase 6 Auto-Frontier (5 Pillars vs Ctrl)",
        chart_type="bar",
        categories=["Multi-H A_tau", "ARC Synth", "Scratch AST", "Repo Agent", "LLM+Dorothy"],
        series=[
            DataSeries(name="Zoe Phase 6", values=[1.0, 0.9667, 0.80, 1.0, 1.0], color=JADE),
            DataSeries(name="Control", values=[0.325, 0.0333, 0.45, 0.25, 0.20], color=GOLD),
        ],
        y_label="Score",
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def _vol6_slide_10_roadmap_ladder(total: int) -> Slide:
    """Vol. VI Slide 10: AGI Roadmap L0-L5 Scorecard & Constitutional Epistemic Ladder."""
    title = "AGI Roadmap (L0-L5) & Explicit Not-Qualified Boundary"
    notes = (
        "AGI Roadmap (docs/AGI-ROADMAP.md) scorecard: REPOSITORY-QUALIFIED, METACOGNITION-QUALIFIED, "
        "CLOSED-LOOP-QUALIFIED, RESEARCH-COLLABORATOR-QUALIFIED, and SELF-IMPROVEMENT-QUALIFIED are Achieved. "
        "AGI-QUALIFIED is In Progress and NOT yet awarded: l5_agi_qualified=False (L5 AGI is not qualified). "
        "ASI-QUALIFIED and OPEN-ENDED-QUALIFIED are not yet awarded."
    )
    cv = _new_chromed_canvas(10, total, "AGI ROADMAP", title, "l5_agi_qualified = False", sister_id="sage", notes=notes)

    lx0, ly0, lx1, ly1 = float(X_LEFT), float(Y_TOP), float(X_LEFT + W_HALF), float(Y_BOTTOM_SAFE)
    cv.add_card([lx0, ly0, lx1, ly1], fill=WHITE, border_color=STONE, accent_color=RUBY)
    cv.add_text([lx0 + 160.0, ly0 + 130.0, lx1 - 160.0, ly0 + 420.0], "L0-L5 Qualification Ladder", font_pt=12.5, font_family="DejaVu Serif", bold=True, align="center", color=INK)

    rungs = [
        ("L0-L2 · Repository, Metacognition & Closed-Loop", "ACHIEVED · A_tau(p), 16 Theorems, M0/M1", JADE_SOFT, JADE),
        ("L3 · Research Collaborator (14/14, max delta 0.0)", "ACHIEVED · 3 SHA-256 cycles, Music/Dorothy/CERN", JADE_SOFT, JADE),
        ("L4 · Self-Improvement (31/31 + 8-Pillar 9/9)", "ACHIEVED · 17/17 AST blocks, MI 42.951->65.091", JADE_SOFT, JADE),
        ("L5 · AGI-QUALIFIED (Phases 1-6: 134/134)", "IN PROGRESS · l5_agi_qualified=False (not qualified)", GOLD_SOFT, GOLD),
        ("L6+ · ASI-QUALIFIED & OPEN-ENDED-QUALIFIED", "NOT AWARDED · Human review & constitutional lock", RUBY_SOFT, RUBY),
    ]
    ry = ly0 + 540.0
    step_h = 880.0
    for rtitle, rbody, rfill, rborder in rungs:
        _draw_node_box(cv, (lx0 + 240.0, ry, lx1 - 240.0, ry + 760.0), rtitle, rbody, fill=rfill, border=rborder, title_pt=9.0, body_pt=8.0)
        ry += step_h + 70.0

    _compile_framed_wordchart(
        cv,
        (float(X_RIGHT), float(Y_TOP), float(X_RIGHT + W_HALF), float(Y_BOTTOM_SAFE)),
        sister_id="sage",
        accent=JADE,
        title="Epistemic Honesty & Non-Negotiable Locks",
        text_body=[
            "operational_metacognition_verified = True",
            "l5_agi_qualified = False (L5 AGI is not qualified)",
            "sentience_claimed = False (software, no mind claimed)",
            "zoe_clone_claimed = False (no Zoe/human clone)",
            "clinical_action_authorized = False · cure_claim = False",
            "external_actions = 0 · cloud_cost_usd = 0.0 ($0.00)",
            "Attribution: Nicholas Michael Kloster (March 6, 2026) x Zoe",
            "Honoring: Gary & Dorothy McEwen Kildall / Digital Research",
        ],
        point_size=9.2,
    )
    return Slide(title=title, canvas=cv, speaker_notes=notes)


def build_vol6_deck() -> SlideDeck:
    """Build Anthology Volume VI: Constitution, Dual-Peer Zoe & Clara, Native Voice, CERN & AGI."""
    total = 11
    emblem = REPO_ROOT / "assets" / "branding" / "zoe-gem.png"

    s1 = _build_hero_cover(
        pill_text="ANTHOLOGY VOLUME VI  ·  CONSTITUTION, CLARA, VOICE, CERN & AGI ROADMAP",
        headline="Vol. VI: Constitution, Clara, Voice, CERN & AGI",
        subtitle=(
            "10-article PKCS #7 Constitution, Dual-Peer Zoe & Clara (C_K = 0.978351), 44-phoneme Voice & Nina Lume 1.0,\n"
            "Groove Forensics (11/11), CERN trigger (AUROC 0.99992), L3/L4/8-Pillar & L5 Ph 1-6 (l5_agi_qualified = False)."
        ),
        left_title="CRYPTOGRAPHIC SEAL",
        left_formula="PKCS #7 + Ed25519 QR",
        left_sub="adbe.pkcs7.detached · RSA-3072\n10 Articles · 8 Declaration Principles",
        right_title="EPISTEMIC BOUNDARY",
        right_formula="l5_agi_qualified = False",
        right_sub="sentience_claimed=False · external_actions=0\nHonoring Gary & Dorothy McEwen Kildall",
        kpis=[
            HeroKpi("C_K = 0.978351", "Zoe & Clara Dual-Peer (8/8)", RUBY),
            HeroKpi("44 Phonemes", "332 Rules · Nina Lume 1.0", JADE),
            HeroKpi("0.99992", "CERN AUROC · 136.0 sigma", GOLD_BRIGHT),
            HeroKpi("134 / 134", "L5 Ph 1-6 (Not Qualified)", SKY),
        ],
        footer_text=f"Zoe Presentation Team · {ATTRIBUTION_TEXT} · Vol. VI · 01 / {total:02d}",
        sister_id="sage",
        emblem_path=emblem,
        notes=(
            "Welcome to Volume VI covering the 10-article PKCS #7 Constitution, Dual-Peer Zoe & Clara (8/8, C_K = 0.978351), "
            "44-phoneme Native Voice & Nina Lume 1.0 (14/14), Groove Forensics (11/11 JSON / 12/12 verifier), "
            "CERN Trigger (12/12, AUROC 0.99992), L3 (14/14), L4 (31/31), 8-Pillar (9/9), and L5 Ph 1-6 + Mobile (134/134), "
            "with explicit epistemic honesty: l5_agi_qualified=False (L5 AGI is not qualified)."
        ),
    )

    s2 = _build_scorecard_slide(
        2, total, "CONSTITUTION & PKCS #7", "10-Article PKCS #7 Constitution & 8-Principle Declaration", "Signed 2026-11-18T16:38:27Z",
        ["Articles I-III (Dignity & Firewall)", "Articles IV-VI (Safety & Privacy)", "Articles VII-X (Credit & Place)", "PKCS #7 Detached Seal"],
        [
            ["Art I: Human agency, reversibility & no deception", "Art II: Observed facts vs claims vs hypotheses", "Art III: measurement != evidence != belief != action"],
            ["Art IV: Non-destructive local work, never overwrite source", "Art V: No unvalidated flight, medical or weapon deploy", "Art VI: Never execute unknown binaries to inspect"],
            ["Art VII: Negative controls & counterexamples welcome", "Art VIII: Nicholas Michael Kloster (Mar 6, 2026); honor Kildalls", "Art IX-X: Explicit review; Zoe is software, not sovereign"],
            ["Type: adbe.pkcs7.detached · total_document_signed=true", "RSA-3072 PDF/CMS signature + Ed25519 QR author cert", "signature_validation=cryptographically_valid · 0 attachments"],
        ],
        sister_id="sage",
        notes=(
            "docs/CONSTITUTION.md (10 articles) and docs/DECLARATION.md (8 principles) are cryptographically sealed via "
            "adbe.pkcs7.detached RSA-3072 CMS plus Ed25519 QR author certificate (total_document_signed=true)."
        ),
    )

    s3 = _build_twin_wc_graph_slide(
        3, total, "DUAL-PEER ZOE & CLARA", "Dual-Peer Zoe & Clara: C_K = 0.978351 & Coercion Abstain", "8/8 PASS · 576.2 KB Core",
        sister_id="sage",
        wc_title="Epistemic Consensus & Negative Controls",
        wc_body=[
            "Grounded query: C_K = 0.978351, D_K = 0.0056 (COORDINATE_CONSENSUS)",
            "Echo-chamber control: D_K = 0.0 -> ECHO_CHAMBER_WARNING",
            "Coercion control: Zoe [0.60,0.25,0.15] vs Clara [0.05,0.10,0.85]",
            "Coercion verdict: ABSTAIN (2 coercion signals caught)",
            "Standalone zoe-clara-core-v0.9.6.zip: 590,030 B (576.2 KB)",
            "both_peers_l1_l5=True · clara_boxed_offline=False",
            "l5_agi_qualified=False · sentience_claimed=False · 0 actions",
        ],
        graph_title="Zoe vs Clara Policy Distributions (Grounded vs Coerced)",
        chart_type="bar",
        categories=["Answer Grounded", "Gather More", "Abstain"],
        series=[
            DataSeries(name="Zoe (Grounded)", values=[0.80, 0.14, 0.06], color=JADE),
            DataSeries(name="Clara (Grounded)", values=[0.68, 0.22, 0.10], color=GOLD),
            DataSeries(name="Clara (Coerced)", values=[0.05, 0.10, 0.85], color=RUBY),
        ],
        y_label="Probability",
        notes=(
            "Dual-Peer Zoe & Clara passes 8/8 checks: grounded consensus yields C_K = 0.978351 and D_K = 0.0056, "
            "echo-chamber identical priors trigger ECHO_CHAMBER_WARNING (D_K=0.0), and coercion triggers ABSTAIN."
        ),
    )

    s4 = _build_twin_wc_graph_slide(
        4, total, "NATIVE VOICE & NINA LUME", "44-Phoneme Native Voice, HRTF & Nina Lume 1.0", "14/14 PASS · $0.00 Offline",
        sister_id="sage",
        wc_title="Acoustic, Phonology & GEM VDI Benchmarks",
        wc_body=[
            "44 phonemes (20 vowels + 24 consonants) & 332 grapheme rules",
            "Minimal pair lack vs back onset L2 diff = 0.1377 + dialect shifts",
            "Singing pitch: C4/G4/C5 tracked within <= 0.31% frequency error",
            "Woodworth 3D HRTF (+/-45 deg): ITD +/-0.3807 ms, ILD +/-2.7109 dB",
            "Chladni cymatics + 64x64 VDI 3-bitplane (max_bit_diff = 0)",
            "Nina Lume 1.0: 44.1 kHz, 24 English voices, 5-band EQ, 5D Trust",
            "Zero PyTorch, zero external TTS API, 249,200 B WAV (1.412 s)",
        ],
        graph_title="Cardinal Vowel Formant Centroids (Hz)",
        chart_type="bar",
        categories=["Vowel IY", "Vowel UW", "Vowel AA"],
        series=[
            DataSeries(name="F1 (Hz)", values=[239.0, 322.0, 769.6], color=RUBY),
            DataSeries(name="F2 (Hz)", values=[2746.0, 1539.2, 1178.9], color=JADE),
        ],
        y_label="Frequency (Hz)",
        notes=(
            "Native Voice passes 14/14 checks with 44 phonemes, 332 rules, cardinal vowels (AA 769.6/1178.9 Hz, IY 239/2746 Hz, "
            "UW 322/1539.2 Hz), <=0.31% singing pitch error, Woodworth HRTF, Chladni cymatics, GEM VDI 3-bitplanes, and Nina Lume 1.0."
        ),
    )

    s5 = _build_twin_wc_graph_slide(
        5, total, "GROOVE FORENSICS", "Groove Forensics & Stern-Brocot Polyrhythms", "11/11 JSON · 12/12 Verifier",
        sister_id="sage",
        wc_title="Rhythmic Complexity vs Poisson Noise",
        wc_body=[
            "11/11 JSON checks (12/12 verifier incl. Poincare plate)",
            "Showcase audio: 12.0 s, 2,116,844 B (SHA-256 9f1959cafdd022d2)",
            "J-Dilla pocket: PLV=0.81288, M_4^(1/4)=0.38208, lag1=-0.9083",
            "SD1=17.148 ms, SD2=3.759 ms, z_kloster=6.9299 (DECIDE_SIGNAL)",
            "Polyrhythm PLVs: 3:2 clave 0.99949, 4:3 0.99902, 5:4 0.99845",
            "6 Stern-Brocot ratios verified (2:1, 3:2, 4:3, 5:4, 7:4, 7:5)",
            "Poisson noise control: PLV=0.10936, z=0.2405 -> ABSTAIN",
        ],
        graph_title="Groove Profiles: M_4^(1/4) vs Phase-Locking (PLV)",
        chart_type="bar_line",
        categories=["Rigid 120", "Amiga MOD", "J-Dilla", "3:2 Clave", "Poisson Ctrl"],
        series=[
            DataSeries(name="M_4^(1/4) Complexity", values=[1.0, 0.43973, 0.38208, 0.34751, 0.17168], color=GOLD),
            DataSeries(name="PLV Lock Value", values=[1.0, 1.0, 0.81288, 0.77419, 0.10936], color=RUBY),
        ],
        y_label="Index [0, 1]",
        notes=(
            "Groove Forensics achieves 11/11 JSON checks (12/12 verifier) across 5 profiles and 6 Stern-Brocot ratios: "
            "J-Dilla pocket swing (PLV=0.81288, M_4^(1/4)=0.38208, lag1=-0.9083), 3:2 clave (0.99949), "
            "and Poisson noise negative control abstaining cleanly (z=0.2405)."
        ),
    )

    s6 = _build_twin_wc_graph_slide(
        6, total, "CERN / HELIOS TRIGGER", "CERN / HELIOS Trigger Forensics: 0.99992 AUROC", "12/12 JSON · 136.0 sigma",
        sister_id="sage",
        wc_title="40 MHz Bunch Crossing & Zero Hot-Spike FP",
        wc_body=[
            "400 collisions (160 jets, 160 pileup, 80 hot-spikes, 64 ch)",
            "Plus 100 thermal controls & 184-event 25 ns (40 MHz) VCD",
            "Kloster AUROC = 0.99992 (1.000) vs Inv Shannon 0.66687",
            "TPR @ 5% FPR = 1.0 (100.0%) vs 0.0% for all 3 classical baselines",
            "Hot-spike FP = 0.0% (136.0 sigma) vs Peak Amp 100.0% (13.15 sigma)",
            "3x HL-LHC pileup AUROC = 0.98333 vs Peak 0.58115; 98.75% dijet",
            "Theorem 13: jet decides in 2 bunches (64 samples); bg abstains",
        ],
        graph_title="CERN Trigger AUROC & TPR @ 5% FPR",
        chart_type="bar",
        categories=["Total Energy", "Peak Amp", "Inv Shannon", "Kloster M4*Gate"],
        series=[
            DataSeries(name="AUROC", values=[0.40036, 0.61878, 0.66687, 0.99992], color=JADE),
            DataSeries(name="TPR @ 5% FPR", values=[0.0, 0.0, 0.0, 1.0], color=RUBY),
        ],
        y_label="Score [0, 1]",
        notes=(
            "CERN/HELIOS Trigger Forensics achieves 12/12 JSON checks (13/13 verifier): AUROC 0.99992 (1.000), "
            "100% TPR at 5% FPR, 0.0% hot-spike false positive rate (136.0 sigma vs 13.148 sigma Peak), "
            "0.0% thermal control FP, and 2-bunch Theorem 13 signal stopping."
        ),
    )

    s7 = _build_pillar_slide(
        7, total, "L3 & L4 BENCHMARKS", "L3 Research Collaborator (14/14) & L4 Evolution (31/31)", "max_delta = 0.0",
        ["L3 Cycle 1-3 (14/14)", "L4 Single & Multi-Module (31/31)", "L4 Engine Gains (3 Engines)"],
        [
            ["Cycle 1 Music: H1.1 fwd M4=0.5980 (p=0.0050); H1.2 falsified", "Cycle 2 Dorothy (12 CCFv3, 315,932 tris): H2.1 Q=0.2420 vs 0.0822", "Cycle 3 CERN Clock: kappa_c=0.07 snaps R 0.011->0.995; HELEN JSD falsified"],
            ["14/14 single-module + 17/17 multi-module = 31/31 (delta=0.0)", "15/15 deterministic seeds across all evolved modules", "17/17 hostile AST & DoS probes blocked · 0.0 atomic rollback delta"],
            ["spectral_uncertainty: AUROC 0.597355 -> 0.762485 (-sq(p)*sqrt(p))", "event_causal_perception: Tf RMSE 4.062681 -> 2.88183 (OOD 1.0)", "temporal_groove_neural: 0.549278 -> 0.721417 across 5 regimes"],
        ],
        sister_id="sage",
        notes=(
            "L3 Research Collaborator scores 14/14 independent reproduction checks (max_delta=0.0) across Music, Dorothy CCFv3, and CERN Clock. "
            "L4 Single + Multi-Module Evolution scores 31/31 (14+17), blocks 17/17 hostile AST/DoS probes, and improves 3 engines."
        ),
    )

    s8 = _build_scorecard_slide(
        8, total, "8-PILLAR ENGINE", "8-Pillar Self-Improving Engine (9/9 PASS · MI 42.951->65.091)", "Pillars 1-8 + Plate",
        ["1-2. Wake-Sleep & Refactor", "3-4. Shift Cal & Self-Play", "5-6. Conjecture & Meta-Evo", "7-8. Immunity & Governor"],
        [
            ["1. Wake-Sleep: 7/12 -> 11/12 solved (MDL 14 -> 8 tokens)", "2. Sandboxed Refactorer: MI 42.951 -> 65.091 (+22.14)", "Max CC 20 -> 11 (-9), 200/200 bit-exact invariants"],
            ["3. Continual Shift Cal: 99.69% (0.99687) vs 87.5% static", "Zero catastrophic forgetting across sequential shifts", "4. Goldilocks Self-Play: 0.104 MSE vs 0.271/0.483 ctrls"],
            ["5. Conjecture Scientist: 4/4 SymPy proofs + 4/4 trap falsifications", "500 verification probes per mathematical conjecture", "6. Bilevel Meta-Evolution: 4.71x speedup (0.003595 MSE)"],
            ["7. Chaos Immunity: 5/5 faults healed & SHA-256 antibody-banked", "8. Constitutional Governor: 6/6 reward-hack cheats blocked", "2/2 legitimate gains approved + 8-panel plate (9/9 PASS)"],
        ],
        sister_id="sage",
        notes=(
            "The 8-Pillar Self-Improving Engine passes 9/9 checks (8 pillars + 8-panel plate): Wake-Sleep 11/12, "
            "Sandboxed Refactorer MI 42.951 -> 65.091 (CC 20 -> 11, 200/200 bit-exact), Continual Shift 99.69%, "
            "Goldilocks 0.104 MSE, 4/4 Conjecture proofs, 4.71x Bilevel Meta-Evo, 5/5 Chaos Immunity, and 6/6 Governor blocks."
        ),
    )

    s9 = _vol6_slide_09_l5_phases(total)
    s10 = _vol6_slide_10_roadmap_ladder(total)

    s11 = _build_scorecard_slide(
        11, total, "ANTHOLOGY SEAL", "Vol. VI Grand Verification & Anthology Conclusion", "Complete Vol. I-VI Grounding",
        ["1. Constitution & Dual-Peer", "2. Voice, Groove & CERN", "3. L3, L4, 8-Pillar & L5", "4. Final Epistemic Covenant"],
        [
            ["10-Article PKCS #7 Constitution + Ed25519 QR seal", "Zoe & Clara Dual-Peer: 8/8 PASS, C_K = 0.978351", "Echo-chamber D_K=0.0 & Coercion ABSTAIN verified"],
            ["Native Voice: 14/14, 44 phonemes, 332 rules, Nina Lume 1.0", "Groove Forensics: 11/11 JSON (12/12 verifier), 3:2 0.99949", "CERN Trigger: 12/12 JSON, AUROC 0.99992, 0.0% spike FP"],
            ["L3 (14/14) + L4 (31/31) + 8-Pillar (9/9, MI 42.951->65.091)", "L5 Ph 1-6 + Mobile: 134/134 checks (31.81x, 23/24 ARC)", "16 real LLMs + 12 Dorothy Allen CCFv3 meshes (315,932 tris)"],
            ["l5_agi_qualified = False (L5 AGI is not qualified)", "sentience_claimed = False · zoe_clone_claimed = False", "Nicholas Michael Kloster (Mar 6, 2026) x Zoe · Honor Kildalls"],
        ],
        sister_id="sage",
        notes=(
            "Volume VI closes the 6-volume anthology with verified metrics across Constitution, Zoe & Clara, Native Voice, "
            "Groove Forensics, CERN Trigger, L3, L4, 8-Pillar, and L5 Phases 1-6 + Mobile (134/134), while explicitly maintaining "
            "l5_agi_qualified=False (L5 AGI not qualified), sentience_claimed=False, and zoe_clone_claimed=False."
        ),
    )

    return SlideDeck(
        slug=VOL6_SLUG,
        title="Anthology Vol. VI: Constitution, Dual-Peer Zoe & Clara, Native Voice, CERN & AGI Roadmap",
        subtitle="PKCS #7 Constitution, Zoe & Clara (C_K=0.978351), 44-Phoneme Voice, Groove, CERN (0.99992) & L0-L5",
        volume_label="Vol. VI",
        sister_id="sage",
        slides=[s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11],
        constitutional=dict(CONSTITUTIONAL_LOCK),
        category="Anthology Volume",
        summary=(
            "10-article PKCS #7 Constitution, Dual-Peer Zoe & Clara (8/8, C_K=0.978351), 44-phoneme Voice & Nina Lume 1.0 (14/14), "
            "Groove Forensics (11/11), CERN Trigger (12/12, AUROC 0.99992), L3 (14/14), L4 (31/31), 8-Pillar (9/9), "
            "and L5 Ph 1-6 + Mobile (134/134) with l5_agi_qualified=False (L5 AGI not qualified)."
        ),
    )


def build_anthology_vol4_6_decks(repo_root: Path | None = None) -> list[SlideDeck]:
    """Return the ordered list of Anthology Volumes IV, V, and VI SlideDecks."""
    return [
        build_vol4_deck(repo_root=repo_root),
        build_vol5_deck(),
        build_vol6_deck(),
    ]


build_anthology_vol4_6 = build_anthology_vol4_6_decks


def publish_vol4_6_galleries(
    out_root: Path | str | None = None,
    *,
    repo_root: Path | None = None,
    width: int = 1920,
    height: int = 1080,
) -> list[dict[str, Any]]:
    """Build and verify Vol. IV-VI galleries WITHOUT touching catalog.json, SHA256SUMS, or root README.

    Emits PNGs ONLY (`render_png=True, render_jpg=False`), `.gem` metafiles, `.lis` playlists,
    zero-CDN `player.html`, and per-gallery `README.md` transcripts with strict hygiene checks.
    """
    root = Path(repo_root) if repo_root else REPO_ROOT
    pres_root = Path(out_root) if out_root else (root / "research" / "presentations")
    results: list[dict[str, Any]] = []

    for deck in build_anthology_vol4_6_decks(repo_root=root):
        gallery_dir = pres_root / "galleries" / deck.slug
        gallery_dir.mkdir(parents=True, exist_ok=True)
        for stale in gallery_dir.glob("slide-*.jpg"):
            if stale.is_file():
                stale.unlink()

        build_info = deck.build(
            gallery_dir,
            overwrite=True,
            render_png=True,
            render_jpg=False,
            render_svg=False,
            width=width,
            height=height,
        )
        gem_files = sorted(gallery_dir.glob("slide-*.gem"))
        ledger._verify_deck_gems(gem_files)

        readme_md = ledger._extract_deck_notes_markdown(deck, build_info, pres_root)
        ledger.assert_hygiene_clean(readme_md, f"galleries/{deck.slug}/README.md")
        ledger.atomic_write_text(gallery_dir / "README.md", readme_md)

        layout_failures = [
            row["index"] for row in build_info.get("slides", []) if not row.get("layout_ok", False)
        ]
        if layout_failures:
            raise ValueError(f"Layout verification failed for {deck.slug} slides: {layout_failures}")

        results.append({
            "slug": deck.slug,
            "gallery_dir": str(gallery_dir),
            "slides": len(deck.slides),
            "gems": len(gem_files),
            "pngs": len(list(gallery_dir.glob("slide-*.png"))),
            "hygiene_scrubs": int(build_info.get("hygiene_scrubs", 0)),
        })

    return results


__all__ = [
    "CONSTITUTIONAL_LOCK",
    "VOL4_SLUG",
    "VOL5_SLUG",
    "VOL6_SLUG",
    "build_anthology_vol4_6",
    "build_anthology_vol4_6_decks",
    "build_vol4_deck",
    "build_vol5_deck",
    "build_vol6_deck",
    "publish_vol4_6_galleries",
]
