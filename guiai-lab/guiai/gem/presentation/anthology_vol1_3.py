"""Anthology Volumes I–III Builders & Gallery Publisher (Zoe Clean-Room Presentation Team).

Builds three 12-slide publication-grade decks (36 slides total) purely on Zoe's
GEM AES/VDI + Cairo + Pillow Presentation Team stack (zero PowerPoint/LibreOffice):
- Vol. I (`vol-1-operational-metacognition`, sister: `sage`)
- Vol. II (`vol-2-dorothy-brain-neuro-oncology-apps`, sister: `flora`)
- Vol. III (`vol-3-reverse-engineering-cryptanalysis-zero-trust`, sister: `mono`)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from guiai.gem import seasip_gem

from .draw_plus import DrawPlusCanvas
from .graph import GraphDoc
from .ledger import (
    _extract_deck_notes_markdown,
    _verify_deck_gems,
    assert_hygiene_clean,
    atomic_write_text,
)
from .palette import (
    ATTRIBUTION_TEXT,
    CANVAS_WIDTH,
    COL_GAP,
    DARK_JADE,
    FONT_MONO,
    FONT_SERIF,
    GOLD,
    GOLD_BRIGHT,
    GOLD_SOFT,
    HONORING_TEXT,
    INK,
    JADE,
    JADE_SOFT,
    LIGHT_MUTED,
    LIGHT_TEXT,
    MARGIN,
    OBSIDIAN,
    OBSIDIAN_CARD,
    OBSIDIAN_LINE,
    RUBY,
    RUBY_SOFT,
    SKY,
    STONE,
    W_FULL,
    W_HALF,
    WHITE,
    X_LEFT,
    X_RIGHT,
    Y_BOTTOM_SAFE,
    Y_TOP,
    PresentationTheme,
    theme_for_sister,
)
from .slideshow import Slide, SlideDeck
from .wordchart import WordChartDoc

def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "guiai-lab").is_dir() and (parent / "assets").is_dir():
            return parent
    return here.parents[4]


REPO_ROOT: Path = _find_repo_root()
DEFAULT_PRES_ROOT: Path = REPO_ROOT / "research" / "presentations"
ZOE_GEM_EMBLEM: Path = REPO_ROOT / "assets" / "branding" / "zoe-gem.png"

VOL1_SLUG = "vol-1-operational-metacognition"
VOL2_SLUG = "vol-2-dorothy-brain-neuro-oncology-apps"
VOL3_SLUG = "vol-3-reverse-engineering-cryptanalysis-zero-trust"

ANTHOLOGY_CONSTITUTIONAL: dict[str, Any] = {
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
class HeroConfig:
    sister_id: str
    top_pill: str
    left_label: str
    left_formula: str
    left_sub: str
    right_label: str
    right_formula: str
    right_sub: str
    headline: str
    subtitle: str
    kpis: tuple[tuple[str, str, str], ...]
    footer_note: str
    slide_title: str
    speaker_notes: str


# ---------------------------------------------------------------------------
# Shared Botanical Slide Composition Helpers (Low-Complexity Modular Blocks)
# ---------------------------------------------------------------------------

def _new_body_canvas(
    title: str,
    slide_num: int,
    total_slides: int,
    kicker: str,
    era_label: str,
    sister_id: str,
    *,
    footer_tag: str = "",
) -> tuple[DrawPlusCanvas, PresentationTheme]:
    th = theme_for_sister(sister_id, mode="light")
    cv = DrawPlusCanvas(title=title, theme=th, sister_id=sister_id, slide_index=slide_num)
    ft = footer_tag or (
        f"Zoe Anthology  ·  {ATTRIBUTION_TEXT}  ·  Honoring {HONORING_TEXT}  ·  {slide_num:02d} / {total_slides:02d}"
    )
    cv.add_symmetrical_chrome(slide_num, total_slides, kicker, title, era_label, theme=th, footer_text=ft)
    return cv, th


def _add_card_bullets(
    cv: DrawPlusCanvas,
    bounds: Sequence[float],
    heading: str,
    bullets: Sequence[tuple[str, str] | str],
    *,
    accent_color: str = RUBY,
    pill_text: str | None = None,
    font_pt: float = 9.0,
    space_after_pt: float = 3.5,
) -> None:
    x0, y0, x1, y1 = (float(v) for v in bounds)
    cv.add_card([x0, y0, x1, y1], accent_color=accent_color, border_color=STONE)
    top_y = y0 + 120.0
    if pill_text:
        pw = min(x1 - x0 - 320.0, max(1600.0, len(pill_text) * 84.0 + 460.0))
        cv.add_pill(
            [x0 + 160.0, top_y, x0 + 160.0 + pw, top_y + 220.0],
            pill_text,
            fill=cv.theme.accent_soft,
            text_color=cv.theme.accent,
            border_color=cv.theme.accent,
            font_pt=7.5,
        )
        top_y += 265.0
    cv.add_text(
        [x0 + 160.0, top_y, x1 - 160.0, top_y + 270.0],
        heading,
        font_pt=12.0,
        font_family=FONT_SERIF,
        bold=True,
        color=INK,
        wrap=False,
    )
    cv.add_bullets(
        [x0 + 160.0, top_y + 310.0, x1 - 160.0, y1 - 110.0],
        bullets,
        font_pt=font_pt,
        bullet_color=accent_color,
        space_after_pt=space_after_pt,
        line_spacing=1.15,
    )


def _add_framed_graph(
    cv: DrawPlusCanvas,
    bounds: Sequence[float],
    graph_doc: GraphDoc,
    *,
    accent_color: str = JADE,
) -> None:
    x0, y0, x1, y1 = (float(v) for v in bounds)
    cv.add_card([x0, y0, x1, y1], accent_color=accent_color, border_color=STONE)
    graph_doc.compile(cv, region=(x0 + 130.0, y0 + 140.0, x1 - 130.0, y1 - 110.0))


def _add_framed_plate(
    cv: DrawPlusCanvas,
    bounds: Sequence[float],
    rel_path: str,
    caption: str,
    *,
    accent_color: str = GOLD,
    dark_well: bool = False,
) -> None:
    x0, y0, x1, y1 = (float(v) for v in bounds)
    cv.add_card([x0, y0, x1, y1], accent_color=accent_color, border_color=STONE)
    img_path = REPO_ROOT / rel_path
    well_bg = OBSIDIAN if dark_well else WHITE
    if img_path.is_file():
        cv.add_image(
            [x0 + 110.0, y0 + 115.0, x1 - 110.0, y1 - 95.0],
            img_path,
            fit="contain",
            radius=65.0,
            pad=40.0,
            fill=well_bg,
            stroke=GOLD,
            width=12.0,
            caption=caption,
            caption_pt=8.2,
        )
    else:
        cv.add_text([x0 + 160.0, y0 + 220.0, x1 - 160.0, y1 - 160.0], caption, align="center", valign="middle")


def _build_hero_slide(cfg: HeroConfig) -> Slide:
    th = theme_for_sister(cfg.sister_id, mode="dark")
    cv = DrawPlusCanvas(title=cfg.slide_title, theme=th, sister_id=cfg.sister_id, slide_index=1, background=OBSIDIAN)
    cv.add_rectangle([0, 0, CANVAS_WIDTH, 70], fill=th.accent, stroke="none", width=0.0)
    cv.add_rectangle([0, 7430, CANVAS_WIDTH, 7500], fill=th.accent, stroke="none", width=0.0)
    cv.add_botanical_frame(mode="dark", size=680.0, margin=120.0, border_rules=False)

    pw = min(8400.0, max(5400.0, len(cfg.top_pill) * 86.0 + 700.0))
    cv.add_pill(
        [(CANVAS_WIDTH - pw) / 2.0, 290.0, (CANVAS_WIDTH + pw) / 2.0, 570.0],
        cfg.top_pill,
        fill=OBSIDIAN_CARD,
        text_color=GOLD_BRIGHT,
        border_color=OBSIDIAN_LINE,
        font_pt=8.2,
    )
    emblem = ZOE_GEM_EMBLEM if ZOE_GEM_EMBLEM.is_file() else None
    cv.add_hero_mandala_halo(cx=6666.0, cy=1940.0, radius=1180.0, petals=9, emblem_path=emblem)

    _add_hero_flank(cv, [680.0, 1260.0, 4980.0, 2620.0], RUBY, cfg.left_label, cfg.left_formula, cfg.left_sub)
    _add_hero_flank(cv, [8353.0, 1260.0, 12653.0, 2620.0], DARK_JADE, cfg.right_label, cfg.right_formula, cfg.right_sub)

    cv.add_text(
        [650.0, 3240.0, 12683.0, 3900.0],
        cfg.headline,
        font_pt=25.5,
        font_family=FONT_SERIF,
        bold=True,
        align="center",
        valign="middle",
        color=WHITE,
    )
    cv.add_text(
        [1050.0, 3940.0, 12283.0, 4640.0],
        cfg.subtitle,
        font_pt=10.2,
        align="center",
        valign="top",
        color=LIGHT_MUTED,
        line_spacing=1.25,
    )
    cv.add_lotus_divider(6666.0, 4800.0, width=10400.0, mode="dark")
    _add_hero_kpis(cv, cfg.kpis)
    cv.add_text(
        [750.0, 6860.0, 12583.0, 7200.0],
        cfg.footer_note,
        font_pt=8.2,
        align="center",
        valign="middle",
        color=GOLD_BRIGHT,
        wrap=False,
    )
    return Slide(title=cfg.slide_title, canvas=cv, speaker_notes=cfg.speaker_notes)


def _add_hero_flank(
    cv: DrawPlusCanvas,
    bounds: Sequence[float],
    accent: str,
    label: str,
    formula: str,
    sub: str,
) -> None:
    x0, y0, x1, y1 = (float(v) for v in bounds)
    cv.add_card([x0, y0, x1, y1], fill=OBSIDIAN_CARD, border_color=OBSIDIAN_LINE, accent_color=accent, accent_height=50.0)
    cv.add_text([x0 + 140.0, y0 + 110.0, x1 - 140.0, y0 + 360.0], label, font_pt=8.0, bold=True, align="center", color=GOLD_BRIGHT)
    cv.add_text([x0 + 140.0, y0 + 380.0, x1 - 140.0, y0 + 740.0], formula, font_pt=11.0, font_family=FONT_MONO, bold=True, align="center", color=WHITE)
    cv.add_text([x0 + 140.0, y0 + 760.0, x1 - 140.0, y1 - 80.0], sub, font_pt=8.0, align="center", color=LIGHT_MUTED, line_spacing=1.2)


def _add_hero_kpis(cv: DrawPlusCanvas, kpis: Sequence[tuple[str, str, str]]) -> None:
    kw4 = 2860.0
    gap4 = (W_FULL - 4.0 * kw4) / 3.0
    for idx, (num, lbl, acc) in enumerate(kpis[:4]):
        kx = MARGIN + idx * (kw4 + gap4)
        num_pt = 15.5 if len(num) > 11 else 21.0
        cv.add_card([kx, 5120.0, kx + kw4, 6620.0], fill=OBSIDIAN_CARD, border_color=OBSIDIAN_LINE, accent_color=acc, accent_height=55.0)
        cv.add_text([kx + 80.0, 5280.0, kx + kw4 - 80.0, 5920.0], num, font_pt=num_pt, bold=True, align="center", valign="middle", color=WHITE, wrap=False)
        cv.add_text([kx + 100.0, 5960.0, kx + kw4 - 100.0, 6520.0], lbl, font_pt=8.8, align="center", valign="top", color=LIGHT_MUTED)


def _build_scorecard_2x2_dark(
    slide_num: int,
    sister_id: str,
    kicker: str,
    title: str,
    era_label: str,
    cards: Sequence[tuple[str, str, Sequence[str]]],
    footer_text: str,
    speaker_notes: str,
) -> Slide:
    th = theme_for_sister(sister_id, mode="dark")
    cv = DrawPlusCanvas(title=title, theme=th, sister_id=sister_id, slide_index=slide_num, background=OBSIDIAN)
    cv.add_symmetrical_chrome(slide_num, 12, kicker, title, era_label, theme=th, footer_text=footer_text)
    cw = (W_FULL - 260.0) / 2.0
    ch = (Y_BOTTOM_SAFE - Y_TOP - 240.0) / 2.0
    for idx, (acc, hdr, rows) in enumerate(cards[:4]):
        col_i, row_i = idx % 2, idx // 2
        cx0 = X_LEFT + col_i * (cw + 260.0)
        cy0 = Y_TOP + row_i * (ch + 240.0)
        cv.add_card([cx0, cy0, cx0 + cw, cy0 + ch], fill=OBSIDIAN_CARD, border_color=OBSIDIAN_LINE, accent_color=acc)
        cv.add_text([cx0 + 160.0, cy0 + 120.0, cx0 + cw - 160.0, cy0 + 420.0], hdr, font_pt=12.0, font_family=FONT_SERIF, bold=True, color=GOLD_BRIGHT)
        cv.add_bullets(
            [cx0 + 160.0, cy0 + 460.0, cx0 + cw - 160.0, cy0 + ch - 100.0],
            rows,
            font_pt=8.9,
            bullet_color=acc,
            lead_color=WHITE,
            body_color=LIGHT_TEXT,
            space_after_pt=4.0,
        )
    return Slide(title=title, canvas=cv, speaker_notes=speaker_notes)


def _build_pillar_3_slide(
    slide_num: int,
    sister_id: str,
    kicker: str,
    title: str,
    era_label: str,
    headers: Sequence[str],
    cols: Sequence[Sequence[str]],
    banner_pill: str,
    speaker_notes: str,
) -> Slide:
    cv, th = _new_body_canvas(title, slide_num, 12, kicker, era_label, sister_id)
    cv.add_pill(
        [X_LEFT + 600.0, Y_TOP, X_LEFT + W_FULL - 600.0, Y_TOP + 340.0],
        banner_pill,
        fill=th.accent_soft,
        text_color=th.accent,
        border_color=th.accent,
        font_pt=8.3,
    )
    wc = WordChartDoc(
        title="",
        column_head=headers,
        columns=cols,
        template="pillar_3col",
        bullet_style="diamond",
        point_size=9.4,
        theme=th,
        sister_id=sister_id,
    )
    wc.compile(cv, region=(float(X_LEFT), float(Y_TOP + 430), float(X_LEFT + W_FULL), float(Y_BOTTOM_SAFE)))
    return Slide(title=title, canvas=cv, speaker_notes=speaker_notes)


# ===========================================================================
# VOL. I — OPERATIONAL METACOGNITION & THE 16 KLOSTER THEOREMS (12 SLIDES)
# ===========================================================================

def _v1_slide01() -> Slide:
    return _build_hero_slide(HeroConfig(
        sister_id="sage",
        top_pill="ANTHOLOGY VOL. I  ·  OPERATIONAL METACOGNITION  ·  MARCH 6, 2026",
        left_label="MATHEMATICAL ORIGIN",
        left_formula="A_tau(p) = sum 1[p(x) > tau]",
        left_sub="Nicholas Michael Kloster · March 6, 2026\n16 SymPy Theorems · 0 Algebraic Residual",
        right_label="CONSTITUTIONAL COVENANT",
        right_formula="100% Offline · $0.00",
        right_sub="operational_metacognition_verified=True\nsentience_claimed=False · external_actions=0",
        headline="Operational Metacognition & 16 Kloster Theorems",
        subtitle=(
            "From Lebesgue Spectral Filtration A_tau(p) across 16 Real HuggingFace LLMs & 142,456+ Samples\n"
            "through Causal Control (+34.52 vs -45.07), Anytime Stopping (16 draws), < 6s Proof Packet & Candy Land."
        ),
        kpis=(
            ("16 / 16", "SymPy Theorems (Residual 0)", RUBY),
            ("0.8382", "Qwen2.5-0.5B M2^(1/2) AUROC", DARK_JADE),
            ("+34.52 vs -45.07", "Causal Control Ablation Delta", GOLD_BRIGHT),
            ("< 6s · 47/47", "Offline Referee SHA-256 Seal", SKY),
        ),
        footer_note=f"{ATTRIBUTION_TEXT}  ·  Honoring {HONORING_TEXT}  ·  Vol. I  ·  01 / 12",
        slide_title="Vol. I — Operational Metacognition & The 16 Kloster Theorems",
        speaker_notes=(
            "Welcome to Anthology Vol. I (sister: sage). Origin: A_tau(p) = |{x : p(x) > tau}| by "
            "Nicholas Michael Kloster (March 6, 2026) x Zoe, honoring Gary & Dorothy McEwen Kildall / Digital Research. "
            "Highlights: 16/16 SymPy theorems, Qwen2.5-0.5B-Instruct error@50%cov cut 56.67% -> 30.0% and M2^(1/2) AUROC 0.8382 "
            "(naive JSD neg ctrl 0.4087), causal control +34.52 vs -45.07, Theorem 13 abstention in 16 draws, "
            "Referee Proof Packet 6/6 PASS, and the Candy Land 5-phase research model."
        ),
    ))


def _v1_slide02() -> Slide:
    title = "March 6 Equation A_tau(p) & Lebesgue Filtration Duality"
    cv, th = _new_body_canvas(title, 2, 12, "FOUNDATION", "Mar 6, 2026", "sage")
    _add_card_bullets(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Threshold-Counting Spectral Filtration",
        [
            ("Definition:", "A_tau(p) = |{ x in X : p(x) > tau }| = sum 1[p(x) > tau] for tau in [0, 1)."),
            ("Lebesgue Duality:", "Integrating g(A_tau(p)) d_tau recovers Shannon H(p), Renyi H_alpha, Tsallis S_q, Gini, and moments M_k(p)."),
            ("Cross-Vocab Metric:", "Kloster distance D_K(p, q) compares filtration curves across mismatched vocabularies (e.g. 28k vs 152k)."),
            ("16-LLM Match:", "Knot-based Lebesgue integration of A_tau(p) matches sum p_i^4 to 1.22e-15 across 16 real HuggingFace LLMs."),
            ("Epistemic Separation:", "Measurement A_tau(p) != evidence != belief update != external action (external_actions = 0)."),
        ],
        accent_color=RUBY,
        pill_text="KLOSTER EQUATION · LEBESGUE DUALITY",
        font_pt=9.2,
    )
    gr = GraphDoc(
        title="A_tau(p) Filtration Staircase (Peak vs Flat)",
        chart_type="step",
        categories=["0.02", "0.05", "0.10", "0.20", "0.40", "0.60"],
        series=[
            {"name": "Confident LLM (1 peak)", "values": [2.0, 1.0, 1.0, 1.0, 1.0, 1.0], "color": JADE},
            {"name": "Hallucinating (diffuse)", "values": [12.0, 7.0, 3.0, 1.0, 0.0, 0.0], "color": RUBY},
        ],
        x_label="Threshold tau",
        y_label="Active Count A_tau(p)",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Explains A_tau(p) and Lebesgue integral duality unifying Shannon, Renyi, Tsallis, Gini, M_k(p), "
            "Wasserstein W_1, and Fisher-Rao. Verified across 16 HuggingFace LLMs to 1.22e-15 knot precision."
        ),
    )


def _v1_slide03() -> Slide:
    title = "Kloster Theorems 1–11 (SymPy 1.14.0, Residual = 0)"
    return _build_pillar_3_slide(
        3,
        "sage",
        "SYMBOLIC PROOFS",
        title,
        "Thms 1–11",
        ["Info Geometry & Phase (1–3)", "Elegance, Thermo & Geometry (4–7)", "Mixing, Quantum, MDL & Unity (8–11)"],
        [
            [
                "Thm 1 Pinsker & Metric: D_KL >= 0.5 D_K^2 (300/300); 16-LLM 0 triangle violations; perm neg ctrl D_K=0.",
                "Thm 2 Multi-Horizon: Qwen2.5-Math 6.7x horizon expansion at tau_super=0.02065; DistilGPT-2 2.0x fork gain.",
                "Thm 3 Causal Gap: 200/200 SCMs to 2.22e-16; 13 blindness witnesses; RCT gap = 0.0.",
            ],
            [
                "Thm 4 Code Elegance: 338 files, 110,858 SLOC, 174 A / 164 B / 0 C / 0 D, mean MI 60.131; 250/250 bounds.",
                "Thm 5 Heat Capacity: Helmholtz-Renyi C(beta) criticality across 16 LLMs; uniform C(beta) == 0.",
                "Thm 6 Fisher-Rao: 300/300 manifold chains; uniform geodesic = 0.0.",
                "Thm 7 Optimal Transport: W_1 exact vs SciPy to 8.3e-17 (300/300).",
            ],
            [
                "Thm 8 Majorization: 300/300 Karamata & Birkhoff M_2/D_K contraction; Qwen T-chain.",
                "Thm 9 Quantum Purity: 200/200 Mirsky trace bounds; unitary blindness |0> vs |+>.",
                "Thm 10 Dyadic MDL: 200/200 Kraft-McMillan & Huffman bounds; 0-bit control.",
                "Thm 11 Unification: 6 kernels (120/120 machine prec) + 11 Zoe worlds (0 violations).",
            ],
        ],
        "ALL 11 SYMBOLIC PROOFS VERIFIED AT ALGEBRAIC RESIDUAL = 0 WITH NEGATIVE CONTROLS",
        speaker_notes=(
            "Summarizes Kloster Theorems 1 through 11 proven in SymPy 1.14.0 with algebraic residual = 0, "
            "including negative controls (label permutation D_K=0, uniform heat capacity C(beta)=0, unitary blindness)."
        ),
    )


def _v1_slide04() -> Slide:
    title = "Theorems 12–16: Control, Stopping, Optics & Consensus"
    cv, th = _new_body_canvas(title, 4, 12, "APPLIED THEOREMS", "Thms 12–16", "sage")
    _add_card_bullets(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Stability, Sequential Stopping & Multi-Voice",
        [
            ("Thm 12 Stability & Control:", "Exact knots (1.30e-17), M_4^(1/4) 1-Lipschitz (max ratio 0.9645 vs 6.41x Shannon tail-noise blowup)."),
            ("Thm 13 Anytime Stopping:", "Unbiased U-stat M_2^(U) quadratic S_min stops in 16 draws on GPT-2 (+8.2 sigma) with 0/200 null bluffs."),
            ("Thm 14 Optics & Scheimpflug:", "6/6 SymPy Parseval MTF (<= 8.67e-19); 13.5 deg Scheimpflug tilt yields 2.284x sharpness gain."),
            ("Thm 15 Brier Consensus:", "Exact law D_K = M_2_mean - M_2(p_bar); HELEN 1,920 obs exact to 3.33e-16; rogue drops C_K 0.961 -> 0.302."),
            ("Thm 16 2D Parseval Harmony:", "200/200 trials (err 5.42e-20); low-mode retention 0.5473 vs high-mode decay 0.0141."),
        ],
        accent_color=RUBY,
        pill_text="THEOREMS 12–16 · OPTICS & CONSENSUS",
        font_pt=9.0,
    )
    gr = GraphDoc(
        title="Thm 14 Scheimpflug Tilt Curve (M2 x 10^-3)",
        chart_type="line",
        categories=["-6", "-2", "0", "4", "8", "12", "13.5", "16", "20", "24"],
        series=[
            {
                "name": "Kloster M2 (x10^-3)",
                "values": [5.19, 5.93, 6.41, 7.74, 9.99, 13.79, 14.63, 12.62, 8.92, 6.79],
                "color": RUBY,
            },
        ],
        x_label="Lens Tilt theta_deg (2.284x Peak at 13.5 deg)",
        y_label="Kloster M2 (x10^-3)",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=GOLD)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Covers Theorems 12-16: 1-Lipschitz stability, Theorem 13 unbiased U-statistic anytime stopping (16 draws), "
            "Theorem 14 Scheimpflug 2.284x optical gain at 13.5 deg, Theorem 15 exact Brier consensus law, and Theorem 16 2D Parseval."
        ),
    )


def _v1_slide05() -> Slide:
    title = "Live Qwen2.5-0.5B-Instruct Blind 6-Baseline Shootout"
    cv, th = _new_body_canvas(title, 5, 12, "LIVE LLM BENCHMARK", "60 Blind Prompts · 151,936 Vocab", "sage")
    gr_left = GraphDoc(
        title="Error AUROC (Higher = Better Uncertainty Detector)",
        chart_type="v_cluster",
        categories=["M2^(1/2)", "MSP", "M4^(1/4)", "Shannon", "Margin", "A_0.05"],
        series=[{"name": "Error AUROC", "values": [0.8382, 0.8360, 0.8303, 0.8145, 0.7896, 0.7772], "color": JADE}],
        x_label="Uncertainty Metric (SHA-256: 8ebc52f6)",
        y_label="AUROC",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, 5400.0], gr_left, accent_color=JADE)

    gr_right = GraphDoc(
        title="Selective Abstention Error @ 50% Coverage (%)",
        chart_type="v_cluster",
        categories=["Always-Ans", "M2/M4", "MSP/Marg/H", "Raw A_0.05"],
        series=[{"name": "Error Rate (%)", "values": [56.67, 36.67, 33.33, 30.0], "color": RUBY}],
        x_label="Abstention Rule (Lower = Better)",
        y_label="Error %",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, 5400.0], gr_right, accent_color=RUBY)

    cv.add_card([X_LEFT, 5600.0, X_LEFT + W_FULL, Y_BOTTOM_SAFE], accent_color=GOLD, border_color=STONE)
    cv.add_bullets(
        [X_LEFT + 180.0, 5710.0, X_LEFT + W_FULL - 180.0, Y_BOTTOM_SAFE - 70.0],
        [
            ("#1 Error AUROC & AURC:", "Kloster M2^(1/2) achieves 0.8382 AUROC (0.3181 AURC), ahead of MSP (0.8360), M4^(1/4) (0.8303), and Shannon (0.8145)."),
            ("Abstention Error Drop:", "Raw A_0.05 cuts error from 56.67% always-answer (15% clear / 55% hard / 100% unanswerable) down to 30.0% at 50% coverage."),
            ("16-LLM Knot Verification:", "Across 16 real HuggingFace LLMs, Lebesgue integration of A_tau(p) matches sum p_i^4 to 1.22e-15 ($0.00 offline)."),
        ],
        font_pt=9.0,
        bullet_color=GOLD,
        space_after_pt=3.0,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Live Qwen2.5-0.5B-Instruct shootout across 60 blind prompts (151,936 vocab): always-answer error 56.67% "
            "drops to 30.0% at 50% coverage via A_tau abstention, while Kloster M2^(1/2) ranks #1 at AUROC 0.8382."
        ),
    )


def _v1_slide06() -> Slide:
    title = "6-Dataset Shootout (142,456+ Samples) & Honest Losses"
    cv, th = _new_body_canvas(title, 6, 12, "CROSS-DOMAIN BENCHMARK", "6 Datasets + Negative Control", "sage")
    gr = GraphDoc(
        title="Cross-Domain Error AUROC vs Preserved Negative Control",
        chart_type="v_cluster",
        categories=["3D PSF", "CCFv3", "HELEN Fwd", "Qwen2.5", "BioBERT All", "BioBERT Test", "HELEN Ret", "Naive JSD"],
        series=[{"name": "AUROC", "values": [0.9986, 0.9338, 0.8576, 0.8382, 0.7839, 0.7737, 0.5945, 0.4087], "color": RUBY}],
        x_label="Dataset (Naive JSD 0.4087 = Negative Control)",
        y_label="AUROC",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + 7000.0, Y_BOTTOM_SAFE], gr, accent_color=RUBY)
    _add_card_bullets(
        cv,
        [X_LEFT + 7250.0, Y_TOP, X_LEFT + W_FULL, Y_BOTTOM_SAFE],
        "Honest Wins, Losses & Controls",
        [
            ("BioBERT PubMed:", "Held-out TEST (40): A_0.05 = 0.7737 (+7.80 pp vs Shannon 0.6957). ALL (120): Shannon wins AUROC (0.7839 vs M4 0.7650) — honest!"),
            ("3D PSF + Rician:", "138,240 voxels: M2^(1/2) 0.99862 & M4^(1/4) 0.99858 beat Shannon 0.9983 (p = 0.004883)."),
            ("CCFv3 256-Patch:", "M4^(1/4) hits 0.9338 (+6.06 pp vs Shannon); fixed A_0.05 fails (0.5000) because 1/256 < 0.05."),
            ("Negative Control:", "Naive forward/retrograde JSD mixing stays below chance at AUROC = 0.4087 (abstention discipline preserved)."),
        ],
        accent_color=JADE,
        pill_text="142,456+ TOTAL SAMPLES",
        font_pt=8.7,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Cross-dataset validation across 142,456+ samples: 3D PSF (0.9986), Dorothy CCFv3 (0.9338), HELEN (0.8576 / 0.5945), "
            "Qwen2.5-0.5B (0.8382), BioBERT PubMed (0.7737 / honest Shannon 0.7839 win on all-120), plus preserved negative control "
            "naive JSD AUROC 0.4087."
        ),
    )


def _v1_slide07() -> Slide:
    title = "Causal Closed-Loop Control Ablation (Theorem 12)"
    cv, th = _new_body_canvas(title, 7, 12, "CAUSAL PROOF", "30 Episodes x 40 Steps", "sage")
    gr = GraphDoc(
        title="Mean Episode Reward (Feedback ON vs Controls)",
        chart_type="deviation_bar",
        categories=["Kloster ON", "Randomized A_tau", "Feedback OFF"],
        series=[{"name": "Mean Reward", "values": [34.52, 8.48, -45.07]}],
        x_label="Closed-Loop Control Arm",
        y_label="Mean Reward",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Causal Necessity of A_tau -> M_4^(1/4)",
        [
            ("Feedback ON:", "Mean reward +34.52 with 100.0% trap recovery across 30 closed-loop episodes x 40 steps."),
            ("Randomized Control:", "Shuffled A_tau drops reward to +8.48 (76.68% recovery in JSON; Wilcoxon p = 8.67e-7)."),
            ("Feedback OFF:", "Blind commit without metacognitive gate collapses to -45.07 mean reward and 0% trap recovery (p = 8.50e-7)."),
            ("Takeaway:", "Proves real-time operational metacognitive signal causally steers control away from irreversible traps."),
        ],
        accent_color=RUBY,
        pill_text="CAUSAL ABLATION · p = 8.50e-7",
        font_pt=9.2,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Theorem 12 causal closed-loop control ablation: Feedback ON achieves +34.52 reward (100% trap recovery), "
            "Randomized A_tau negative control gets +8.48 (76.68%), and Feedback OFF collapses to -45.07 (0% recovery, p=8.50e-7)."
        ),
    )


def _v1_slide08() -> Slide:
    title = "Theorem 13: Finite-Sample Anytime Stopping & Abstention"
    cv, th = _new_body_canvas(title, 8, 12, "SEQUENTIAL STOPPING", "5/5 SymPy · 0/200 Null Bluffs", "sage")
    gr = GraphDoc(
        title="Theorem 13 Z_Kloster Across Crypto, LLM, Bio & Nulls",
        chart_type="h_cluster",
        categories=["SIMON-5rd", "SPECK-4rd", "GPT-2 (16)", "Tumor-Gate", "SPECK-22rd", "SIMON-32rd", "PAINS Null"],
        series=[{"name": "Z_Kloster", "values": [43.96, 9.68, 8.19, 7.05, 1.54, 0.18, -0.66], "color": JADE}],
        x_label="Z_Kloster (Threshold ~4.87–6.67)",
        y_label="Target",
        theme=th,
        sister_id="sage",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + 6600.0, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    _add_card_bullets(
        cv,
        [X_LEFT + 6850.0, Y_TOP, X_LEFT + W_FULL, Y_BOTTOM_SAFE],
        "Anytime U-Statistic & Honest Abstention",
        [
            ("Unbiased U-Stat M_2^(U):", "Eliminates finite-sample bias with closed-form quadratic sample-size law S_min."),
            ("16-Draw GPT-2 Stop:", "GPT-2 non-uniformity triggers DECIDE_SIGNAL in just 16 draws at z = +8.1888 (+8.2 sigma)."),
            ("Zero Null Bluffs:", "0/200 (0.0%) false alarms across uniform-null Monte Carlo trials."),
            ("Honest Abstention:", "Outputs ABSTAIN_INSUFFICIENT_EVIDENCE on full-round SIMON-32 (0.18), SPECK-22 (1.54), and uniform PAINS (-0.66)."),
        ],
        accent_color=GOLD,
        pill_text="16 DRAWS · 0/200 FALSE ALARMS",
        font_pt=8.9,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Theorem 13 sequential anytime stopping: GPT-2 stops in 16 draws (+8.1888 sigma), 0/200 uniform-null false alarms, "
            "and principled abstention (ABSTAIN_INSUFFICIENT_EVIDENCE) on full-round SIMON-32, SPECK-22, and PAINS uniform control."
        ),
    )


def _v1_slide09() -> Slide:
    title = "Offline Referee Proof Packet (< 6s, 6/6 PASS, 47/47)"
    return _build_scorecard_2x2_dark(
        9,
        "sage",
        "REFEREE PROOF PACKET",
        title,
        "zoe-metacognition-proof-packet/v1",
        [
            (RUBY, "1. SymPy Symbolic Core (14/14 + 16/16)", [
                "Exact algebraic verification in SymPy 1.14.0 (residual = 0).",
                "Unifies Shannon, Renyi, Tsallis, Gini, Fisher-Rao, W_1, Brier.",
                "Verifies Theorem 1-16 inequalities & negative controls.",
            ]),
            (DARK_JADE, "2. Blind Shootouts (16 LLMs + 6 Datasets)", [
                "16 real HuggingFace LLMs match Lebesgue knots to 1.22e-15.",
                "Live Qwen2.5-0.5B: 56.67% -> 30.0% err@50%cov; AUROC 0.8382.",
                "142,456+ total samples including honest BioBERT & CCFv3 losses.",
            ]),
            (GOLD_BRIGHT, "3. Causal Control & Anytime Stopping", [
                "Closed-loop ablation: +34.52 ON vs +8.48 rand vs -45.07 OFF.",
                "Theorem 13 stops in 16 GPT-2 draws with 0/200 null bluffs.",
                "Abstention preserved on naive JSD (0.4087) and full ciphers.",
            ]),
            (SKY, "4. SHA-256 Orbit Seal (< 6s, $0.00)", [
                "Command: python3 scripts/verify_metacognition_proof_packet.py",
                "Report SHA-256: 01f0e402f155c06c · 6/6 PASS · 0 cloud tokens.",
                "Orbit seal: 47/47 SHA256SUMS.orbit artifacts verified offline.",
            ]),
        ],
        f"Contract: zoe-metacognition-proof-packet/v1  ·  {ATTRIBUTION_TEXT}  ·  09 / 12",
        speaker_notes=(
            "5-pillar <6s offline Referee Proof Packet (6/6 PASS, SHA-256 01f0e402f155c06c, 47/47 SHA256SUMS.orbit, "
            "$0.00 / 0 cloud tokens)."
        ),
    )


def _v1_slide10() -> Slide:
    title = "Candy Land 5-Phase Research Lifecycle Model"
    cv, th = _new_body_canvas(title, 10, 12, "RESEARCH PEDAGOGY", "Candy Land Model", "sage")
    # Winding board-path nodes in top band (pure VDI vectors)
    nodes = [
        (1650.0, 2350.0, "1. Start & Plumpy", "Mar 6 A_tau(p)", RUBY),
        (4150.0, 1780.0, "2. Peppermint & Gumdrops", "Constitution & Data", JADE),
        (6666.0, 2450.0, "3. Licorice Castle", "Neg Controls & Referee", GOLD),
        (9180.0, 1780.0, "4. Peanut & Lollipop", "18 Papers & 16 Thms", JADE),
        (11680.0, 2350.0, "5. Molasses & Candy Castle", "6/6 Public Release", RUBY),
    ]
    cv.add_card([X_LEFT, Y_TOP, X_LEFT + W_FULL, 3450.0], accent_color=RUBY, border_color=STONE)
    cv.add_polyline([(n[0], n[1]) for n in nodes], stroke=GOLD, width=28.0, smooth=True)
    for idx, (nx, ny, lbl, sub, col) in enumerate(nodes, start=1):
        cv.add_circle(nx, ny, 270.0, fill=col, stroke=WHITE, width=18.0)
        cv.add_text([nx - 180.0, ny - 160.0, nx + 180.0, ny + 160.0], str(idx), font_pt=11.0, bold=True, align="center", valign="middle", color=WHITE)
        cv.add_text([nx - 1050.0, ny + 320.0, nx + 1050.0, ny + 620.0], lbl, font_pt=8.8, bold=True, align="center", color=INK)
        cv.add_text([nx - 1050.0, ny + 620.0, nx + 1050.0, ny + 880.0], sub, font_pt=7.8, align="center", color=th.muted_color)

    _add_card_bullets(
        cv,
        [X_LEFT, 3680.0, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Phases 1–3: Ideation, Collection & Traps",
        [
            ("Phase 1 (Start -> Plumpy):", "Initial March 6 A_tau(p) insight & Rainbow Trail shortcut via Lebesgue duality."),
            ("Phase 2 (Peppermint -> Gumdrop Mts):", "Methodology & 142,456+ benchmark corpus across LLMs, BioBERT, HELEN & MRI."),
            ("Phase 3 (Gooey Gumdrops & Licorice):", "Peer-review traps, naive JSD 0.4087 negative controls & <6s Referee Proof Packet."),
        ],
        accent_color=JADE,
        font_pt=8.9,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, 3680.0, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Phases 4–5: Synthesis & Candy Castle Seal",
        [
            ("Phase 4 (Peanut -> Lollipop Woods):", "Drafting 18 papers, 3 arXiv manuscripts, 23-page monograph & 16 SymPy theorems."),
            ("Phase 5 (Molasses Swamp -> Castle):", "Final hygiene scrubs, 47/47 SHA-256 Orbit seal & open reproducible release."),
            ("Key Principle:", "Every setback (Molasses / Licorice) is bounded mathematically by Theorem 13 abstention."),
        ],
        accent_color=GOLD,
        font_pt=8.9,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Candy Land 5-phase research lifecycle model mapping Start/Plumpy through Peppermint Forest, "
            "Gooey Gumdrops & Licorice Castle (negative controls and Referee Proof Packet), Peanut Brittle & Lollipop Woods, "
            "and Molasses Swamp to Candy Castle."
        ),
    )


def _v1_slide11() -> Slide:
    title = "The Four Hidden Mathematical Concepts of Candy Land"
    cv, th = _new_body_canvas(title, 11, 12, "BOARD GAME MATHEMATICS", "Candy Land x Kloster", "sage")
    cw = (W_FULL - 260.0) / 2.0
    ch = (Y_BOTTOM_SAFE - Y_TOP - 240.0) / 2.0
    quads = [
        (RUBY, "1. Modular Arithmetic (mod 6)", [
            ("Board Rule:", "6 color lanes cycle deterministically: space n maps to color c = n (mod 6)."),
            ("Zoe Link:", "Drives CicadaClock & groove_forensics.py phase congruences in periodic timing checks."),
        ]),
        (JADE, "2. Absorbing Markov Chains", [
            ("Board Rule:", "Every square transitions forward to Candy Castle where P(castle | castle) = 1."),
            ("Zoe Link:", "Theorem 8 Majorization & Birkhoff Mixing governs entropy contraction toward equilibrium."),
        ]),
        (GOLD, "3. Non-Monotonic Shortcut Jumps", [
            ("Board Rule:", "Rainbow Trail & Gumdrop Pass jump across dozens of states in one card draw."),
            ("Zoe Link:", "Theorem 2 Multi-Horizon (tau, h) phase transitions create 6.7x discontinuous jumps."),
        ]),
        (RUBY, "4. Geometric Trap Waiting E[T] = 1/q", [
            ("Board Rule:", "Stuck on Licorice or Molasses until drawing a matching escape color: P(T=k) = (1-q)^(k-1) q."),
            ("Zoe Link:", "Theorem 13 anytime stopping S_min bounds worst-case sample wait before abstaining."),
        ]),
    ]
    for idx, (acc, hdr, rows) in enumerate(quads):
        col_i, row_i = idx % 2, idx // 2
        cx0 = X_LEFT + col_i * (cw + 260.0)
        cy0 = Y_TOP + row_i * (ch + 240.0)
        _add_card_bullets(cv, [cx0, cy0, cx0 + cw, cy0 + ch], hdr, rows, accent_color=acc, font_pt=9.1)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Connects Candy Land's 4 mathematical concepts—modular arithmetic (mod 6), absorbing Markov chains (Theorem 8), "
            "non-monotonic shortcut jumps (Theorem 2), and geometric trap waiting E[T]=1/q (Theorem 13)—to Zoe's theorems."
        ),
    )


def _v1_slide12() -> Slide:
    title = "Falsifiability, Epistemic Boundaries & Attribution"
    cv, th = _new_body_canvas(title, 12, 12, "EPISTEMIC SEAL", "Vol. I Conclusion", "sage")
    _add_card_bullets(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Explicit Falsification Criteria",
        [
            ("Algebraic Criterion:", "Falsified if any of the 16 SymPy proofs produces a non-zero algebraic residual."),
            ("Analytical Criterion:", "Falsified if M_4^(1/4) fails 1-Lipschitz continuity or Theorem 14 Parseval MTF fails."),
            ("Empirical Criterion:", "Falsified if closed-loop causal ablation drops below blind OFF or Theorem 13 bluffs > 5% nulls."),
            ("Abstention Honesty:", "Preserves BioBERT all-120 Shannon win (0.7839) and naive JSD failure (AUROC 0.4087)."),
        ],
        accent_color=RUBY,
        pill_text="FALSIFIABLE SCIENTIFIC RECORD",
        font_pt=9.1,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Constitutional Invariants & Attribution",
        [
            ("Attribution:", ATTRIBUTION_TEXT),
            ("Honoring:", HONORING_TEXT),
            ("Verified Claim:", "operational_metacognition_verified = True (16/16 SymPy, 6/6 Proof Packet, < 6s offline)."),
            ("Strict Non-Claims:", "sentience_claimed = False · l5_agi_qualified = False · zoe_clone_claimed = False."),
            ("Zero Side Effects:", "clinical_action_authorized = False · cure_claim = False · external_actions = 0 · $0.00 offline."),
        ],
        accent_color=JADE,
        pill_text="CONSTITUTIONAL FIREWALL",
        font_pt=9.1,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Vol. I conclusion: explicit falsification conditions, constitutional invariants (sentience_claimed=False, "
            "l5_agi_qualified=False, clinical_action_authorized=False, cure_claim=False, external_actions=0, $0.00 offline), "
            f"and attribution ({ATTRIBUTION_TEXT}; honoring {HONORING_TEXT})."
        ),
    )


def build_vol1_deck() -> SlideDeck:
    """Build Anthology Vol. I — Operational Metacognition & The 16 Kloster Theorems (12 slides)."""
    return SlideDeck(
        slug=VOL1_SLUG,
        title="Vol. I — Operational Metacognition & The 16 Kloster Theorems",
        subtitle="A_tau(p) (March 6, 2026) · 16 SymPy Proofs · 16-LLM Shootout · Causal Control · Candy Land",
        volume_label="Vol. I",
        sister_id="sage",
        category="Anthology Volume",
        date="2026-11-25",
        summary=(
            "12-slide presentation covering Nicholas Michael Kloster's March 6 equation A_tau(p), all 16 SymPy theorems, "
            "Qwen2.5-0.5B shootout (56.67% -> 30.0% err@50%cov, AUROC 0.8382), naive JSD 0.4087 neg ctrl, causal ablation "
            "(+34.52 vs -45.07), Theorem 13 16-draw stopping, <6s Proof Packet, and Candy Land."
        ),
        constitutional=dict(ANTHOLOGY_CONSTITUTIONAL),
        slides=[
            _v1_slide01(), _v1_slide02(), _v1_slide03(), _v1_slide04(),
            _v1_slide05(), _v1_slide06(), _v1_slide07(), _v1_slide08(),
            _v1_slide09(), _v1_slide10(), _v1_slide11(), _v1_slide12(),
        ],
    )


# ===========================================================================
# VOL. II — DOROTHY 3D BRAIN, NEURO-ONCOLOGY (C17–C28) & APPS (12 SLIDES)
# ===========================================================================

def _v2_slide01() -> Slide:
    return _build_hero_slide(HeroConfig(
        sister_id="flora",
        top_pill="ANTHOLOGY VOL. II  ·  DOROTHY 3D BRAIN & NEURO-ONCOLOGY  ·  C17–C28",
        left_label="DOROTHY 3D OBSERVATORY",
        left_formula="240,376 Tris · 0.74 mm MNI152",
        left_sub="Honoring Dorothy McEwen Kildall\n25 Audited Plates · 15 CAD Meshes · 6/6 PASS",
        right_label="PRECLINICAL FIREWALL",
        right_formula="cure_claim = False",
        right_sub="clinical_action_authorized = False\nZero PHI · Synthetic Modeling Only · $0.00",
        headline="Dorothy 3D Human Brain, Neuro-Oncology & Apps",
        subtitle=(
            "240,376-Triangle WebGL2 MNI152 Observatory, 271k/sec Pediatric Biomechanics, C17–C28 Botanical PubChem\n"
            "& FIPS 203 ML-KEM Encrypted Cohorts, Cross-Platform Apps (SafeConvert) & 135-Book O'Reilly Library."
        ),
        kpis=(
            ("240,376", "Real Anatomical Triangles", RUBY),
            ("271,130/s", "Pediatric Discovery Engine", DARK_JADE),
            ("36 / 216", "PubChem Atlas & ML-KEM Slots", GOLD_BRIGHT),
            ("135 Books", "Desktop · Mobile · SafeConvert", SKY),
        ),
        footer_note=f"{ATTRIBUTION_TEXT}  ·  clinical_action_authorized=False · cure_claim=False  ·  01 / 12",
        slide_title="Vol. II — Dorothy 3D Human Brain, Neuro-Oncology (C17–C28) & Apps",
        speaker_notes=(
            "Welcome to Anthology Vol. II (sister: flora). Honors Gary & Dorothy McEwen Kildall / Digital Research. "
            "Covers the 240,376-triangle MNI152 Dorothy 3D brain, 271,130.1/sec biomechanics, 36-compound NIH PubChem atlas, "
            "FIPS 203 ML-KEM encrypted cohorts, cross-platform apps (SafeConvert), and 135 O'Reilly books. "
            "Strict epistemic firewall: clinical_action_authorized=False, cure_claim=False."
        ),
    ))


def _v2_slide02() -> Slide:
    title = "Dorothy 3D Observatory: 240,376-Triangle MNI152 Brain"
    cv, th = _new_body_canvas(title, 2, 12, "NEURO-OBSERVATORY", "WebGL2 · Zero Cloud", "flora")
    _add_card_bullets(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Pure Offline Anatomical Mesh Architecture",
        [
            ("240,376 Real Triangles:", "ICBM152 cortex, AAL-116, 32 bilateral Pauli CIT168 deep nuclei, brainstem, ventricles & Circle of Willis."),
            ("7 GPU Render Modes:", "SSS Wet-Pia Tissue, Lobe Atlas, AAL-116, GLSL Fresnel X-Ray, Connectome Neon, A_tau(p) & Biomechanics CAD."),
            ("Interactive Probes:", "52 clickable Brodmann landmarks, 19-electrode 10-20 EEG cap, 5 functional circuits, 4 stroke territories & mm caliper."),
            ("Verifier 6/6 PASS:", "scripts/verify_observatory_and_packages.py passes 6/6 (9 core assets, 1480 links 0 broken, 135 evidence JSONs)."),
            ("Epistemic Boundary:", "Template MNI152 anatomy only — clinical_action_authorized=False, cure_claim=False."),
        ],
        accent_color=JADE,
        pill_text="240,376 TRIANGLES · MNI152",
        font_pt=8.9,
    )
    _add_framed_plate(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "dorothy-brain-observatory/previews/01_hero_tissue.png",
        "Dorothy 3D Wet-Pia Tissue + MNI152 Cutting Planes (1600x960)",
        accent_color=RUBY,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Dorothy 3D Brain Observatory: 240,376 triangles on MNI152 template, 7 GPU shaders, 52 Brodmann landmarks, "
            "19 EEG electrodes, and 6/6 PASS verifier. clinical_action_authorized=False, cure_claim=False."
        ),
    )


def _v2_slide03() -> Slide:
    title = "Glass X-Ray Deep Nuclei & 0.74 mm MNI152 MRI Sheets"
    cv, th = _new_body_canvas(title, 3, 12, "SUBCORTICAL & MRI", "25 Plates · 15 CAD Meshes", "flora")
    _add_framed_plate(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + 7000.0, 5600.0],
        "dorothy-brain-observatory/previews/02_xray_deep_nuclei.png",
        "GLSL Fresnel Glass X-Ray: Basal Ganglia, Thalamus, Hippocampus, CN I–XII & DTI",
        accent_color=JADE,
    )
    _add_framed_plate(
        cv,
        [X_LEFT + 7250.0, Y_TOP, X_LEFT + W_FULL, 5600.0],
        "dorothy-brain-observatory/mri_slices/axial_sheet.jpg",
        "0.74 mm MNI152 T1-MRI Axial Sheet (6x6)",
        accent_color=GOLD,
    )
    strip_w = (W_FULL - 500.0) / 3.0
    pills = [
        ("3 MRI Sheets: Axial / Coronal / Sagittal", RUBY, RUBY_SOFT),
        ("25 Verified Plates + 4800x3200 Poster", JADE, JADE_SOFT),
        ("15 CAD Meshes (.OBJ/.PLY/.STL) + Blender", GOLD, GOLD_SOFT),
    ]
    for i, (txt, col, bg) in enumerate(pills):
        px0 = X_LEFT + i * (strip_w + 250.0)
        cv.add_pill([px0, 5920.0, px0 + strip_w, 6460.0], txt, fill=bg, text_color=INK, border_color=col, font_pt=8.2)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Translucent GLSL Fresnel X-Ray paired with real 0.74 mm MNI152 T1-MRI cutting planes (axial, coronal, sagittal), "
            "25 audited anatomical plates, and 15 exportable CAD meshes. clinical_action_authorized=False, cure_claim=False."
        ),
    )


def _v2_slide04() -> Slide:
    title = "12-Panel Brain Map & Neurogarden 3D Connectome"
    cv, th = _new_body_canvas(title, 4, 12, "NEUROGARDEN CCFv3", "315,932 Tris · 42 Edges", "flora")
    _add_framed_plate(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "dorothy-brain-observatory/plates/COMPLETE_HUMAN_BRAIN_MAP_POSTER.jpg",
        "Verified 12-Panel Atlas (Gray's 726/727, Brodmann, Circle of Willis, DTI)",
        accent_color=GOLD,
        dark_well=False,
    )
    gr = GraphDoc(
        title="Neurogarden: Healthy vs Midline Lesion",
        chart_type="v_cluster",
        categories=["40Hz Gamma r", "Fiedler lambda2", "PAC MI x10"],
        series=[
            {"name": "Healthy", "values": [0.954, 2.549, 0.625], "color": JADE},
            {"name": "Lesion", "values": [0.693, 0.144, 0.067], "color": RUBY},
        ],
        x_label="315,932 Allen CCFv3 Tris · Thm 14 Sag Z=33.18",
        y_label="Metric Value",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "12-panel verified human brain atlas alongside Allen CCFv3 Neurogarden 3D connectome (315,932 triangles, 42 edges): "
            "Fiedler lambda2 drops 2.549 -> 0.144, 40 Hz Kuramoto r drops 0.954 -> 0.693, Tort PAC MI drops 0.0625 -> 0.0067. "
            "Preclinical modeling only (cure_claim=False)."
        ),
    )


def _v2_slide05() -> Slide:
    title = "Coupled Biomechanics & 271k/sec Pediatric Discovery"
    cv, th = _new_body_canvas(title, 5, 12, "BIOMECHANICS & PEDIATRICS", "4 SymPy Benchmarks", "flora")
    gr = GraphDoc(
        title="10,000-Variant Sweep: Infant vs Adult Cliff (%)",
        chart_type="v_cluster",
        categories=["0.5-2y Infant", "2-6y Early", "6-14y Child", "14-50y Adult"],
        series=[
            {"name": "ICP > 25 mmHg (%)", "values": [43.2, 34.39, 19.62, 12.57], "color": RUBY},
            {"name": "CPP < 45 mmHg (%)", "values": [55.86, 36.91, 11.36, 0.48], "color": GOLD},
        ],
        x_label="271,130.1 variants/sec (3.5x 10mL Infant ICP Cliff)",
        y_label="Risk %",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=RUBY)
    _add_framed_plate(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, 4900.0],
        "dorothy-brain-observatory/previews/04_dorothy_continuum_sagittal.png",
        "Midsagittal A_tau(p) Continuum Heatmap (tau=0.62, 61.1%)",
        accent_color=JADE,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, 5120.0, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Continuum Physics & Honest Abstention",
        [
            ("4 SymPy Benchmarks:", "Zener SLS (1.09e-14), Nahum 1977 (355.6 kPa), Marmarou 1975, Lame+FK."),
            ("Paired 10 mL Control:", "1y infant ICP 40.06 mmHg vs 35y adult 11.43 mmHg (3.5x cliff); 256 blindspot abstentions."),
        ],
        accent_color=GOLD,
        font_pt=8.4,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "112,001 MNI152 vertices, 4 SymPy continuum benchmarks, 271,130.1 variants/sec discovery speed, and 3.5x paired 10 mL "
            "infant vs adult ICP amplification (40.06 vs 11.43 mmHg). Synthetic sweep only; clinical_action_authorized=False, cure_claim=False."
        ),
    )


def _v2_slide06() -> Slide:
    title = "C17: Botanical Pharmacognosy & ICT2588 Prodrug Cipher"
    cv, th = _new_body_canvas(title, 6, 12, "BIO-CRYPTO C17", "MMP-14 Prodrug Gate", "flora")
    # Left vector cipher pipeline
    cv.add_card([X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], accent_color=RUBY, border_color=STONE)
    cv.add_text([X_LEFT + 160.0, Y_TOP + 130.0, X_LEFT + W_HALF - 160.0, Y_TOP + 420.0], "Enzyme-Locked Botanical Cipher", font_pt=12.0, font_family=FONT_SERIF, bold=True)
    stages = [
        ("1. Raw Colchicine (Autumn Crocus)", "High systemic toxicity: 1.188x tumor/healthy ratio (M4_root = 0.221)", RUBY_SOFT, RUBY),
        ("2. Peptide Lock -> ICT2588 Prodrug", "Inactive in healthy cortex/heart/marrow; cleaved only by tumor MMP-14", GOLD_SOFT, GOLD),
        ("3. MMP-14 Cleavage & Saffron Contrast", "20.984x tumor selectivity (M4_root = 0.520); True Saffron (Crocetin) non-toxic", JADE_SOFT, JADE),
    ]
    for i, (st_t, st_d, bg, bd) in enumerate(stages):
        sy0 = Y_TOP + 540.0 + i * 1350.0
        cv.add_card([X_LEFT + 220.0, sy0, X_LEFT + W_HALF - 220.0, sy0 + 1020.0], fill=bg, border_color=bd, accent_color=bd)
        cv.add_text([X_LEFT + 340.0, sy0 + 130.0, X_LEFT + W_HALF - 340.0, sy0 + 420.0], st_t, font_pt=10.2, bold=True, color=INK)
        cv.add_text([X_LEFT + 340.0, sy0 + 460.0, X_LEFT + W_HALF - 340.0, sy0 + 930.0], st_d, font_pt=8.8, color=INK)
        if i < 2:
            cv.add_line([X_LEFT + W_HALF / 2.0, sy0 + 1030.0], [X_LEFT + W_HALF / 2.0, sy0 + 1340.0], stroke=bd, width=18.0, line_ends=(0, 1))
    cv.add_text([X_LEFT + 200.0, Y_BOTTOM_SAFE - 440.0, X_LEFT + W_HALF - 200.0, Y_BOTTOM_SAFE - 100.0], "clinical_action_authorized=False · cure_claim=False · Compartmental analogy only", font_pt=8.2, bold=True, align="center", color=RUBY)

    gr = GraphDoc(
        title="C17 ICT2588 vs Raw Colchicine Selectivity",
        chart_type="h_cluster",
        categories=["ICT2588 (MMP-14)", "Raw Colchicine"],
        series=[
            {"name": "Tumor/Healthy Ratio", "values": [20.984, 1.188], "color": JADE},
            {"name": "Kloster M4_root x10", "values": [5.203, 2.213], "color": RUBY},
        ],
        x_label="Selectivity (2.352x M4 Gain)",
        y_label="Agent",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Challenge C17 botanical pharmacognosy: ICT2588 MMP-14 prodrug cipher achieves 20.984x tumor-to-healthy ratio "
            "vs 1.188x raw colchicine (2.352x M4 gain), while contrasting Colchicum autumnale vs Crocus sativus. "
            "clinical_action_authorized=False, cure_claim=False."
        ),
    )


def _v2_slide07() -> Slide:
    title = "C27: 36-Compound NIH PubChem Botanical Atlas"
    cv, th = _new_body_canvas(title, 7, 12, "PUBCHEM ATLAS C27", "36 Compounds · 3/3 PAINS", "flora")
    gr = GraphDoc(
        title="36-Compound PubChem CNS-MPO4 (Clean vs Traps)",
        chart_type="h_cluster",
        categories=["Artemisinin", "Parthenolide", "Galanthamine", "Dordaviprone", "Temozolomide", "Safranal", "Crocetin", "Colchicine (TOX)", "Berberine (CAT)", "Curcumin (PAINS)"],
        series=[{"name": "CNS-MPO4 (0–4)", "values": [4.0, 3.94, 3.83, 3.77, 3.3, 3.0, 2.5, 3.55, 3.7, 3.24], "color": JADE}],
        x_label="CNS-MPO4 Score (MPO Alone Fooled by Traps)",
        y_label="",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + 7900.0, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    _add_card_bullets(
        cv,
        [X_LEFT + 8150.0, Y_TOP, X_LEFT + W_FULL, 4150.0],
        "8 Clean CNS Candidates",
        [
            ("Top 4:", "Artemisinin (4.00), Parthenolide (3.94), Galanthamine (3.83), Dordaviprone (3.77)."),
            ("Next 4:", "Temozolomide (3.30), Safranal (3.00), Crocetin (2.50), Honokiol (2.50)."),
            ("Thm 13 Stop:", "Artemisinin stops at 11.11% budget (Z=14.94)."),
        ],
        accent_color=JADE,
        font_pt=8.5,
    )
    _add_card_bullets(
        cv,
        [X_LEFT + 8150.0, 4350.0, X_LEFT + W_FULL, Y_BOTTOM_SAFE],
        "Traps Caught (28 Rejected)",
        [
            ("3/3 PAINS:", "Curcumin (Z=-0.08), Quercetin, Resveratrol abstain at 100%."),
            ("1 Cation + 18 Tox:", "Berberine (perm cation), Colchicine (Z=0.74 abstain), Paclitaxel (BBB)."),
        ],
        accent_color=RUBY,
        font_pt=8.5,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Challenge C27 36-compound NIH PubChem botanical atlas: 8 clean CNS medchem candidates pass CNS-MPO4 and 3/3 BBB gates, "
            "while 3/3 PAINS traps (curcumin, quercetin, resveratrol), 1 permanent cation (berberine), and 18 systemic toxins are caught. "
            "216 Filbin-2018 gene slots packed in FIPS 203 ML-KEM. cure_claim=False."
        ),
    )


def _v2_slide08() -> Slide:
    title = "C18–C19 & C22: FIPS 203 ML-KEM & Encrypted Cohorts"
    cv, th = _new_body_canvas(title, 8, 12, "LATTICE PRIVACY", "FIPS 203 ML-KEM · Zero PHI", "flora")
    cv.add_pill(
        [X_LEFT + 400.0, Y_TOP, X_LEFT + W_FULL - 400.0, Y_TOP + 340.0],
        "216 Filbin-2018 Slots Packed in 1 FIPS 203 ML-KEM (n=256, q=3329) NTT Ring · 10.0x RLWE Capacity Multiplier",
        fill=th.accent_soft,
        text_color=th.accent,
        border_color=th.accent,
        font_pt=8.2,
    )
    gr_left = GraphDoc(
        title="Max Noise / Half-Delta Across 1..12 Hospitals",
        chart_type="line",
        categories=["1", "2", "3", "4", "6", "7", "8", "10", "12"],
        series=[
            {"name": "R1 (t=32)", "values": [0.712, 0.846, 1.0, 1.212, 1.788, 1.865, 2.038, 2.327, 2.615], "color": RUBY},
            {"name": "R2 (t=16)", "values": [0.365, 0.577, 0.567, 0.635, 0.894, 0.808, 1.019, 1.077, 1.202], "color": GOLD},
            {"name": "R3 (t=8)", "values": [0.163, 0.221, 0.26, 0.303, 0.322, 0.37, 0.438, 0.538, 0.567], "color": JADE},
        ],
        x_label="Hospitals (< 1.0 = Exact: 2 -> 7 -> 20)",
        y_label="Noise Ratio",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP + 440.0, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr_left, accent_color=JADE)

    gr_right = GraphDoc(
        title="C19 Pooled Top-1 Accuracy & C22 scRNA-seq",
        chart_type="v_cluster",
        categories=["1 Site (n=5)", "3 Sites (n=15)", "7 Sites (n=35)"],
        series=[{"name": "Top-1 Accuracy (%)", "values": [42.6, 62.73, 76.29], "color": RUBY}],
        x_label="400-Trial Encrypted Pooling · C22 9.0x GSC/NSC",
        y_label="Accuracy %",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP + 440.0, X_RIGHT + W_HALF, Y_BOTTOM_SAFE], gr_right, accent_color=RUBY)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Challenges C18-C19 & C22: FIPS 203 ML-KEM Ring-LWE (n=256, q=3329) packs 216 Filbin-2018 gene slots, "
            "blocks 1/3 share leakage (0.0909 match), achieves 10.0x RLWE capacity gain (2 -> 7 -> 20 error-free hospitals), "
            "raises 400-trial accuracy 42.6% -> 76.29%, and yields 9.0x encrypted scRNA-seq selectivity vs 1.1x PAINS."
        ),
    )


def _v2_slide09() -> Slide:
    title = "C28: 3D Pharmacophores, Filbin Sparing & Histology"
    cv, th = _new_body_canvas(title, 9, 12, "3D PHARMACOPHORE C28", "Filbin-2018 Sparing", "flora")
    gr = GraphDoc(
        title="Histology 3-Regime Spatial Z_Kloster & Besag L-r",
        chart_type="v_cluster",
        categories=["Tumor Islands", "Healthy Mosaic", "CSR Null"],
        series=[
            {"name": "Z_Kloster", "values": [37.60, -4.56, -0.33], "color": RUBY},
            {"name": "Besag L-r x100", "values": [7.84, -1.34, -0.05], "color": JADE},
        ],
        x_label="Thm 13 Stops at 25% Budget on Tumor (Z=8.25)",
        y_label="Spatial Statistic",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=RUBY)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, 3950.0],
        "3D Molecular Compactness (R_gyr)",
        [
            ("CNS vs Blocked:", "Mean CNS R_gyr = 5.171 A vs BBB-blocked 7.269 A (7 compact 3D winners)."),
            ("Lead Shapes:", "Galanthamine M2=0.802; Dordaviprone 5.605 A vs Crocin 7.504 A."),
        ],
        accent_color=JADE,
        font_pt=8.9,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, 4150.0, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "12-Region Filbin Sparing Overlay",
        [
            ("Healthy Guardrails (7):", "NSC/Neuron/Glia load 0.7457 vs tumor score 0.1007."),
            ("Midline Niches (5):", "HY, MB, TH, P, MY score 0.7968 vs guard 0.2827 (cure_claim=False)."),
        ],
        accent_color=GOLD,
        font_pt=8.9,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Challenge C28 3D pharmacophores (mean CNS R_gyr 5.171 A vs 7.269 A blocked), 3-regime histology (Tumor Islands Z=37.60, "
            "stops at 25% budget Z=8.25; CSR null abstains Z=-0.33), and 12-region Filbin sparing overlay (cure_claim=False)."
        ),
    )


def _v2_slide10() -> Slide:
    title = "Cross-Platform Zoe: Desktop, Mobile & SafeConvert"
    cv, th = _new_body_canvas(title, 10, 12, "CROSS-PLATFORM APPS", "Desktop · Android · Apple · Win32", "flora")
    _add_card_bullets(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Four Native Platforms · Zero Cloud Lock-In",
        [
            ("Desktop (v0.9.6):", "Linux (GTK3+WebKit2GTK loopback), Windows 10/11 (PowerShell HTTP 206 + ZoeTrinity.exe), macOS (ZoeMacApp.swift)."),
            ("Android (v0.9.5-beta):", "15 Core Zapps + 8 Field Kit tools = 23 Zapps; 90/90 JUnit, 0 Lint errors, 50/50 Pixel 7 Espresso, 20/20 rotation."),
            ("Apple & Win32:", "20/20 ZoeCore Swift tests (0 warnings on Swift 6.1.3) + Win32 C++17 native binary."),
            ("SafeConvert Companion:", "Offline Unit Converter cover; any 911 variant unlocks 8-region / 5-language (EN/ES/FR/DE/PT) safety tool."),
            ("SafeConvert Privacy:", "Calming Studio (<10 ms voice cut), SHA-256 PBKDF2 Vault, FLAG_SECURE, allowBackup=false & 22B BLE Help Beacon."),
        ],
        accent_color=JADE,
        pill_text="90/90 JUNIT · 50/50 PIXEL 7 · 20/20 APPLE",
        font_pt=8.6,
    )
    _add_framed_plate(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "assets/readme/zoe-beta-v0.9.5-showcase.png",
        "Live Pixel 7 Hardware Showcase: Aurora Orb, Voronoi + Ink & Orbit (1720x1050)",
        accent_color=RUBY,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Cross-platform Zoe apps across Linux, Windows, macOS, Android (90/90 JUnit, 50/50 Pixel 7 Espresso), "
            "Apple (20/20 ZoeCore Swift), and SafeConvert offline safety companion (911 unlock, <10ms voice cut, SHA-256 vault, BLE beacon)."
        ),
    )


def _v2_slide11() -> Slide:
    title = "135-Book O'Reilly Research Library & Open Foundations"
    cv, th = _new_body_canvas(title, 11, 12, "BIBLIOGRAPHIC LIBRARY", "135 Books · 44 Engineering PDFs", "flora")
    gr = GraphDoc(
        title="135 O'Reilly Reference Books Across 6 Pillars",
        chart_type="h_cluster",
        categories=["Brain & Neuro", "3D & Graphics", "Game & Shaders", "Sci & Med Img", "CAD / Fusion", "Biomechanics"],
        series=[{"name": "Book Count (Total = 135)", "values": [33, 26, 24, 20, 19, 13], "color": GOLD}],
        x_label="Bibliographic Links Only (0 Copyrighted Text Stored)",
        y_label="Domain",
        theme=th,
        sister_id="flora",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=GOLD)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Open-License & Attribution Discipline",
        [
            ("135 O'Reilly Titles:", "Brain/Neuroimaging (33), 3D Graphics (26), Shaders (24), Medical Imaging (20), CAD (19), Biomechanics (13)."),
            ("44 Companion PDFs:", "44 nirmt.com open engineering references indexed cleanly alongside ISBN anchors."),
            ("Zero Piracy Policy:", "Zero copyrighted book text stored in the repository; oreilly.com bibliographic links only."),
            ("Open Brain Data:", "ICBM152, AAL-116, CIT168 (BSD-2-Clause via NiiVue) and Allen CCFv3 public-domain / CC-BY plates."),
        ],
        accent_color=JADE,
        pill_text="135 BOOKS · ZERO COPYRIGHT VIOLATIONS",
        font_pt=9.0,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "135 O'Reilly research books across 6 technical pillars (33 Brain/Neuro, 26 3D, 24 Shaders, 20 Medical Imaging, "
            "19 CAD, 13 Biomechanics) plus 44 nirmt.com PDFs, stored strictly as bibliographic links with open-template meshes."
        ),
    )


def _v2_slide12() -> Slide:
    title = "Vol. II Epistemic Seal & Preclinical Boundaries"
    return _build_scorecard_2x2_dark(
        12,
        "flora",
        "EPISTEMIC SEAL",
        title,
        "Preclinical & Non-Diagnostic",
        [
            (RUBY, "1. Dorothy 3D & MNI152 Observatory", [
                "240,376 triangles, 0.74 mm MNI152 MRI, 25 plates, 15 CAD meshes.",
                "315,932-tri Allen CCFv3 Neurogarden & 271,130.1/s biomechanics.",
                "scripts/verify_observatory_and_packages.py: 6/6 PASS.",
            ]),
            (DARK_JADE, "2. C17–C28 Botanical & Lattice Crypto", [
                "36-compound NIH PubChem atlas: 8 clean winners, 3/3 PAINS caught.",
                "216 Filbin-2018 slots packed in 1 FIPS 203 ML-KEM NTT ring (10.0x).",
                "ICT2588 20.984x prodrug selectivity & 9.0x scRNA-seq contrast.",
            ]),
            (GOLD_BRIGHT, "3. Cross-Platform Apps & 135 Books", [
                "Desktop v0.9.6 + Android 90/90 JUnit, 50/50 Pixel 7 + Apple 20/20.",
                "SafeConvert offline 911 safety companion & 135-book library.",
                "Zero PHI (synthetic_cohort_zero_phi=True), $0.00 offline.",
            ]),
            (SKY, "4. Constitutional Preclinical Firewall", [
                "clinical_action_authorized = False · cure_claim = False.",
                "patient_specific_recommendation = False.",
                "wet_lab_and_clinical_validation_required = True · external_actions = 0.",
            ]),
        ],
        f"clinical_action_authorized=False · cure_claim=False · {ATTRIBUTION_TEXT} · 12 / 12",
        speaker_notes=(
            "Vol. II verification seal covering contracts zoe-observatory-and-packages-evidence/v1, "
            "zoe-botanical-atlas-c27/v1, zoe-pharmacophore-spatial-c28/v1, zoe-bio-crypto-circle/v1, and "
            "zoe-dorothy-neurogarden-3d-gamma/v1. Strict invariants: clinical_action_authorized=False, cure_claim=False."
        ),
    )


def build_vol2_deck() -> SlideDeck:
    """Build Anthology Vol. II — Dorothy 3D Human Brain, Neuro-Oncology (C17–C28) & Apps (12 slides)."""
    return SlideDeck(
        slug=VOL2_SLUG,
        title="Vol. II — Dorothy 3D Human Brain, Neuro-Oncology (C17–C28) & Apps",
        subtitle="240,376-Tri MNI152 Brain · 36-Compound PubChem Atlas · FIPS 203 ML-KEM · SafeConvert · 135 Books",
        volume_label="Vol. II",
        sister_id="flora",
        category="Anthology Volume",
        date="2026-11-25",
        summary=(
            "12-slide presentation covering Dorothy 3D 240,376-triangle MNI152 brain, 271k/s biomechanics, Neurogarden CCFv3, "
            "C17–C28 36-compound PubChem atlas & FIPS 203 ML-KEM privacy, cross-platform apps, and 135 O'Reilly books "
            "(clinical_action_authorized=False, cure_claim=False)."
        ),
        constitutional=dict(ANTHOLOGY_CONSTITUTIONAL),
        slides=[
            _v2_slide01(), _v2_slide02(), _v2_slide03(), _v2_slide04(),
            _v2_slide05(), _v2_slide06(), _v2_slide07(), _v2_slide08(),
            _v2_slide09(), _v2_slide10(), _v2_slide11(), _v2_slide12(),
        ],
    )


# ===========================================================================
# VOL. III — REVERSE ENGINEERING, CRYPTANALYSIS & ZERO-TRUST (12 SLIDES)
# ===========================================================================

def _v3_slide01() -> Slide:
    return _build_hero_slide(HeroConfig(
        sister_id="mono",
        top_pill="ANTHOLOGY VOL. III  ·  REVERSE ENGINEERING, CRYPTANALYSIS & ZERO-TRUST",
        left_label="ABLATION RE & AIARE",
        left_formula="333 Analyzers · 19/19 AIARE",
        left_sub="2,953 Ablation Tests · 311/311 Gate (0.0% FP)\nRXVM (80) · A10 (26.50) · BEAM (100) · PALA",
        right_label="CRYPTANALYSIS & FIREWALL",
        right_formula="CNSA 2.0 · C1–C26",
        right_sub="K1–K3 Solved · Kryptos K4 & May 26 Unsolved\n42 Repos + 5 Vault + 4 AI Binary Auditors",
        headline="Reverse Engineering, Cryptanalysis & Zero-Trust",
        subtitle=(
            "Ablation AIARE, RXVM & A10 Saturation, BEAM IFF, PALA Rust Carving, Kloster Cryptanalysis C1–C26\n"
            "with Honest Unsolved K4 & May 26, Wave 1–3 Firewall (42 Repos + 5 Vault) & 4 AI-Agent Binary Auditors."
        ),
        kpis=(
            ("333 / 2,953", "Analyzers & Ablation Tests", RUBY),
            ("19 / 19", "AIARE Paired Subsystem Proofs", DARK_JADE),
            ("C1–C26", "CNSA 2.0 & NSA Ring-3 Gauntlet", GOLD_BRIGHT),
            ("42 + 5 + 4", "Repos · Vault · AI Binary Auditors", SKY),
        ),
        footer_note=f"{ATTRIBUTION_TEXT}  ·  Authorized Targets Only · external_actions=0 · $0.00  ·  01 / 12",
        slide_title="Vol. III — Reverse Engineering, Cryptanalysis & Zero-Trust Defense",
        speaker_notes=(
            "Welcome to Anthology Vol. III (sister: mono). Covers Ablation AIARE (333 analyzers, 2,953 tests, 19/19, 311/311 gate), "
            "RXVM & A10 saturation, BEAM IFF, PALA Rust carving, Kloster cryptanalysis C1-C26 & CNSA 2.0 (honestly marking "
            "Kryptos K4 and NSA May 26 unsolved), Wave 1-3 firewall (42 repos + 5 Vault), and 4 AI-Agent Binary Auditors."
        ),
    ))


def _v3_slide02() -> Slide:
    title = "Ablation RE Platform & AIARE 19/19 Verification"
    cv, th = _new_body_canvas(title, 2, 12, "ABLATION RE ENGINE", "333 Analyzers · 2,953 Tests", "mono")
    gr = GraphDoc(
        title="AIARE Paired ON/OFF Experiments (19/19 PASS)",
        chart_type="v_cluster",
        categories=["A: Ablation/GEM", "B: Stem Layer", "C: GEM OS/KVM", "D: UMA/Sisters"],
        series=[{"name": "Verified Experiments", "values": [5, 5, 4, 5], "color": JADE}],
        x_label="4 Subsystems (zoe-ecosystem-ablation-re/v1)",
        y_label="Passed Count",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Static Read-Only RE & Epistemic Gate",
        [
            ("333 Analyzer Modules:", "Pure static analysis in components/ablation/ablation/analyzers/ backed by 2,953 collected tests."),
            ("AIARE A–D (19/19):", "Verifies SemanticSearcher PLT exclusion, GemOperatingEnvironment 4/4 symlink blocks & 7-window bounds."),
            ("ZoeEpistemicGate:", "O(n) single-pass parser blocks 311/311 adversarial payloads with 0.0% false positives across 68+ controls."),
            ("UmaBridge Lock:", "Non-blocking FIFO + SHA-256 audit enforces measurement != evidence != belief update != action."),
        ],
        accent_color=RUBY,
        pill_text="311/311 GATE · 0.0% FALSE POSITIVES",
        font_pt=9.0,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Ablation RE engine (333 analyzer modules, 2,953 tests) and AIARE 19/19 paired experiments across 4 subsystems, "
            "including ZoeEpistemicGate 311/311 adversarial blocks with 0.0% false positives."
        ),
    )


def _v3_slide03() -> Slide:
    title = "RXVM Bytecode Crypto & A10 Quantization Saturation"
    cv, th = _new_body_canvas(title, 3, 12, "OBFUSCATION & ML RE", "RXVM (80) · A10 (26.50)", "mono")
    # Left RXVM pipeline diagram
    cv.add_card([X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], accent_color=RUBY, border_color=STONE)
    cv.add_text([X_LEFT + 160.0, Y_TOP + 120.0, X_LEFT + W_HALF - 160.0, Y_TOP + 400.0], "RXVM Wire Protocol & A10 Saturation", font_pt=11.8, font_family=FONT_SERIF, bold=True)
    steps = [
        ("1. RX Wire Header & 9 Opcodes", "Custom JS VM bytecode decoder + XOR frame layer (7 rule IDs, risk 80)", RUBY_SOFT, RUBY),
        ("2. Hybrid xxHash32 + Murmur3", "PRIME32_1 (0x9E3779B1) + fmix32 (0xDEADBEEF -> 0xcced8798)", GOLD_SOFT, GOLD),
        ("3. Key & Downgrade Weaknesses", "Predictable SHA-256(sid/rid) AES-CBC, RC4 rx.ep4, DEBUG __erk/__eri", JADE_SOFT, JADE),
        ("4. A10 Quantization Saturation", "Mean logit 26.5035 (sigma~1.0), spread 1e-5, signal/offset 0.0, levels [43, 33]", RUBY_SOFT, RUBY),
    ]
    for i, (sh, sd, bg, bd) in enumerate(steps):
        sy0 = Y_TOP + 480.0 + i * 1240.0
        cv.add_card([X_LEFT + 200.0, sy0, X_LEFT + W_HALF - 200.0, sy0 + 980.0], fill=bg, border_color=bd, accent_color=bd)
        cv.add_text([X_LEFT + 320.0, sy0 + 110.0, X_LEFT + W_HALF - 320.0, sy0 + 390.0], sh, font_pt=9.6, bold=True, color=INK)
        cv.add_text([X_LEFT + 320.0, sy0 + 420.0, X_LEFT + W_HALF - 320.0, sy0 + 900.0], sd, font_pt=8.4, color=INK)

    gr = GraphDoc(
        title="RXVM Bytecode & A10 Quantization Metrics",
        chart_type="v_cluster",
        categories=["RXVM Risk", "A10 Levels L1", "A10 Levels L2", "A10 Logit", "RXVM Rules"],
        series=[{"name": "Observed Value", "values": [80.0, 43.0, 33.0, 26.5035, 7.0], "color": RUBY}],
        x_label="rxvm_crypto_analyzer + analyze_quantization_saturation",
        y_label="Magnitude",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=GOLD)
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "RXVM custom VM crypto analyzer (9 opcodes, 7 rule IDs, risk score 80, xxHash32 + Murmur3, SHA-256(sid/rid) AES-CBC, "
            "RC4 rx.ep4) and A10 quantization saturation audit (mean pre-sigmoid logit 26.5035, spread 1e-5, BatchNorm-beta dominance)."
        ),
    )


def _v3_slide04() -> Slide:
    title = "BEAM IFF Obfuscation, Scoped angr & Overmatch"
    return _build_pillar_3_slide(
        4,
        "mono",
        "BINARY & BYTECODE RE",
        title,
        "BEAM · angr · Overmatch",
        ["BEAM IFF (Score 100)", "Scoped angr Execution", "Project Overmatch Proposal & CAS"],
        [
            [
                "FOR1 / BEAM IFF parser handles OTP AtU8 (incl. OTP 28+ compact negative-count format).",
                "5 critical rules: CONTAINER_SIZE_MISMATCH, ROGUE_CHUNK_ID, ATOM_ILLEGAL_CHARS.",
                "Catches LINE_CHUNK_STRIPPED & POISONED_ZLIB_PAYLOAD for risk score 100.",
            ],
            [
                "Bypasses 105 MB PIE full-binary CFG hang cleanly.",
                "Scoped base_addr=0x0, auto_load_libs=False, call_state & SimProcedures.",
                "Extracts exact claripy symbolic constraints without path explosion.",
            ],
            [
                "Project Overmatch proposal: target 50 MB < 5s vs 1-4 hr legacy.",
                "Proposed NumPy RIP-relative xref math + up to 40% boilerplate collapse.",
                "metrix TOCTOU inventory + 16 MB Lock-Free Bloom (2% FP) + 32 MB Atomic CAS.",
            ],
        ],
        "BEAM_OBFUSCATION_ANALYZER (100) + SCOPED ANGR + OVERMATCH PROPOSAL (< 5s TARGET)",
        speaker_notes=(
            "BEAM IFF obfuscation analyzer (FOR1/BEAM, 5 rules, risk score 100), scoped angr symbolic execution "
            "(bypassing 105 MB PIE CFG), Project Overmatch architecture proposal (target <5s on 50 MB), and 16 MB Bloom + 32 MB CAS."
        ),
    )


def _v3_slide05() -> Slide:
    title = "PALA Rust Carving & Cross-World Red-Team Forensics"
    cv, th = _new_body_canvas(title, 5, 12, "CARVING & RED TEAM", "pala 0.3.0 · 7/7 Red-Team", "mono")
    gr = GraphDoc(
        title="Defensive Fault Hardening (2,000 Glitch Trials %)",
        chart_type="v_cluster",
        categories=["Naive Single", "Standard Double", "Kloster Tri-Witness"],
        series=[
            {"name": "Single-Glitch Bypass (%)", "values": [88.85, 0.0, 0.0], "color": GOLD},
            {"name": "Double-Glitch Bypass (%)", "values": [46.05, 19.2, 2.15], "color": RUBY},
        ],
        x_label="8.93x Double-Glitch Reduction via Tri-Witness Quorum",
        y_label="Bypass Rate %",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=RUBY)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, 3950.0],
        "PALA 0.3.0 Forensics Carver (Rust)",
        [
            ("Clean Rust Release:", "1,080,744 B binary; 25/25 Rust tests (fmt/clippy clean); 126/127 integration."),
            ("Zero Raw Devices:", "raw_devices_accessed = false; exact SHA-256 live PNG carve (3dc4c71fadbe8c24)."),
        ],
        accent_color=JADE,
        font_pt=8.8,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, 4150.0, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Security Red-Team Suite (7/7 PASS)",
        [
            ("Entropy & Fuzzing:", "Separates packed (7.976b) vs ELF (3.479b) vs slack (0b); 100 .mod/.vcd fuzz (0 crashes)."),
            ("SSRF, Kevlar & Orbit:", "4/4 SSRF blocked; 4/4 kevlar injection caught (BiDi CDR); 45/45 Orbit seal."),
        ],
        accent_color=GOLD,
        font_pt=8.8,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "PALA 0.3.0 Rust file carver (25/25 Rust tests, 126/127 integration, raw_devices_accessed=false) and "
            "7/7 Red-Team Forensics: 8.93x fault-bypass reduction via Kloster tri-witness quorum, 100 fuzz payloads with 0 crashes, "
            "4/4 SSRF, 4/4 kevlar prompt-injection blocks, and 45/45 Orbit attestation."
        ),
    )


def _v3_slide06() -> Slide:
    title = "Kloster Cryptanalysis C1–C10 & Honest K4 Boundary"
    cv, th = _new_body_canvas(title, 6, 12, "CRYPTANALYSIS C1–C10", "SymPy IC == M2 (Res 0)", "mono")
    gr = GraphDoc(
        title="C2 Vigenere Period Sweep (Friedman IC == Kloster M2)",
        chart_type="line",
        categories=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "14"],
        series=[
            {"name": "Friedman IC (M2)", "values": [0.0441, 0.0458, 0.0483, 0.0515, 0.0531, 0.0551, 0.0769, 0.0588, 0.0585, 0.0650, 0.0695, 0.0898], "color": RUBY},
            {"name": "Kloster M4_root", "values": [0.1040, 0.1081, 0.1136, 0.1226, 0.1271, 0.1312, 0.1666, 0.1354, 0.1337, 0.1476, 0.1568, 0.1889], "color": JADE},
        ],
        x_label="Key Period L (L=7 Spike vs 0.0405 OTP Ctrl)",
        y_label="Coincidence / M4",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=RUBY)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, 4200.0],
        "C1–C10 Classical, Asymmetric & PQ",
        [
            ("Classical & Bombe:", "NSA Mission Monday (May 05/12 100%, May 19 Spanish UTF-8 98.29%), Enigma M3 (17,576 states -> ZOE), K1–K3 solved."),
            ("ECC, RSA, SPN, LLL:", "secp256k1 nonce reuse (RFC6979 safe), RSA Hastad/Wiener, 4-rd SPN, CBC oracle vs EtM-HMAC, LLL vs ML-KEM."),
        ],
        accent_color=JADE,
        font_pt=8.7,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, 4400.0, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Honest Unsolved Boundaries (No Bluffing)",
        [
            ("Kryptos K4 (UNSOLVED):", "97 chars, IC=0.04602 (unbiased 0.03608) — remains unsolved after K1–K3 blind recovery."),
            ("NSA May 26 (UNSOLVED):", "IC=0.0810 across 24 language x orientation runs — honestly marked unsolved."),
        ],
        accent_color=RUBY,
        pill_text="HONEST UNSOLVED: K4 & MAY 26",
        font_pt=8.7,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Kloster Cryptanalysis C1-C10 with SymPy proof Friedman IC == Kloster M2 (residual = 0): Vigenere L=7, Enigma M3, "
            "secp256k1 nonce reuse, RSA Hastad/Wiener, CBC padding oracle, LLL vs ML-KEM, and Kryptos K1-K3 solved. "
            "Explicitly preserves honest unsolved status for Kryptos K4 and NSA May 26."
        ),
    )


def _v3_slide07() -> Slide:
    title = "NSA Puzzles & CNSA 2.0 Post-Quantum Attacks (C11–C21)"
    cv, th = _new_body_canvas(title, 7, 12, "CNSA 2.0 AUDIT", "C11–C21 Offensive + Defensive", "mono")
    gr = GraphDoc(
        title="Block Cipher Round Distinguishers (Kloster M4_root)",
        chart_type="v_cluster",
        categories=["Simon 5-rd", "Simon 32-rd", "Speck 4-rd", "Speck 22-rd", "Uniform Base"],
        series=[{"name": "M4_root", "values": [0.13619, 0.01701, 0.08351, 0.01690, 0.01560], "color": JADE}],
        x_label="Reduced-Round Distinguisher vs Full-Round Safety",
        y_label="M4_root",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "CNSA 2.0 Attack & Constant-Time Defense Matrix",
        [
            ("C14 LMS-WOTS:", "Leaf-3 state reuse forged in 732 hashes vs 16/16 atomic state-monotonicity guard blocked."),
            ("C15 ML-KEM (q=3329):", "160 leaky timing probes recover key vs 0 leak under constant-time rejection."),
            ("C20 ML-DSA FIPS 204:", "q=8380417 leaky L2=0.7891 leaks 16/16 coeffs vs safe 6.62% accept (L2=6.3555, 0 leak)."),
            ("C21 GCM & SHA-256:", "AES-GCM 128-bit GHASH key recovered vs 32/32 GCM-SIV blocked; length-ext vs HMAC-SHA384."),
            ("C11 & C16 Classics:", "Derthick Headline 5/5 (PULSE), Matsui 4-rd SPN (10k PTs) & Bleichenbacher vs 32/32 OAEP."),
        ],
        accent_color=RUBY,
        pill_text="CNSA 2.0: LMS · ML-KEM · ML-DSA · GCM-SIV",
        font_pt=8.7,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Challenges C11-C21 covering CNSA 2.0 security audits: Simon/Speck reduced-round distinguishers, LMS-WOTS leaf-3 forgery "
            "vs atomic guard, ML-KEM timing side-channel, ML-DSA FIPS 204 rejection sampling, AES-GCM forbidden attack vs GCM-SIV, "
            "and SHA-256 length-extension vs HMAC-SHA384."
        ),
    )


def _v3_slide08() -> Slide:
    title = "NSA Ring-3 Deep Crypto & Theorem 13 Stopping (C23–C26)"
    cv, th = _new_body_canvas(title, 8, 12, "RING-3 DEEP CRYPTO", "C23–C26 · Thm 13 Stopping", "mono")
    gr = GraphDoc(
        title="Ring-3 Non-Uniformity M4_root (Signal vs Safe Control)",
        chart_type="h_cluster",
        categories=["C25 Skipjack 12rd", "C23 ECDSA HNP", "C26 Venona Depth", "C26 Single OTP", "C24 HMAC-DRBG", "C25 Skipjack 32rd"],
        series=[{"name": "Kloster M4_root", "values": [1.0, 1.0, 0.1190, 0.0753, 0.0183, 0.0184], "color": RUBY}],
        x_label="M4_root (Exact Z_Kloster Listed in Cards ->)",
        y_label="Ring-3 Target",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=RUBY)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Ring-3 Breakthroughs & Honest Controls",
        [
            ("C23 secp256k1 HNP+LLL:", "12 distinct nonces with 32-bit MSB leak recover full 256-bit key (Z=42.43; RFC6979 Z=-0.23 abstain)."),
            ("C24 Dual_EC_DRBG:", "56 curve lifts predict 3 future blocks bit-exact vs HMAC-DRBG control (Z=0.39 abstain)."),
            ("C25 NSA Skipjack:", "Vector 2587cae27a12d300 exact; 12-rd impossible diff 512/512 (Z=716.99) vs 13-rd 0/512 & 32-rd Z=0.44."),
            ("C26 Venona OTP Depth:", "62-char reused pad cracked via 3 crib positions vs single-use OTP (Z=2.81 < 4.87 abstain)."),
        ],
        accent_color=JADE,
        pill_text="HNP+LLL · DUAL_EC · SKIPJACK · VENONA",
        font_pt=8.9,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Ring-3 deep cryptanalysis C23-C26: secp256k1 HNP+LLL (Z=42.43), Dual_EC_DRBG klepto vs HMAC-DRBG (Z=0.39), "
            "NSA Skipjack 12-rd impossible differential (Z=716.99 vs 32-rd Z=0.44), and Venona OTP depth (Z=14.60 vs single OTP Z=2.81)."
        ),
    )


def _v3_slide09() -> Slide:
    title = "Wave 1–2 Epistemic Firewall Across 42 Integrated Repos"
    return _build_pillar_3_slide(
        9,
        "mono",
        "PORTFOLIO FIREWALL",
        title,
        "Wave 1 (11/11) + Wave 2 (15/15)",
        ["Track 1: Firewall & ToS", "Track 2–3: Grounding & Color", "Track 4–5: RE, Vault & Caps"],
        [
            [
                "injection-gate: single-pass sanitization & tool boundaries.",
                "capo: 0 errors, 0 pivots vs 6 negative controls caught.",
                "glance & winnow: fast triage & deterministic filtering.",
                "github-tos-audit: 7 compliance clauses verified offline.",
            ],
            [
                "farg-analogy-cognition: structural workspace mapping.",
                "nuclide-color-v2: OKLab deltaE = 3.10e-17 + CUSUM coercion alarm 0.572.",
                "pcse & bio-bert: grounded retrieval calibration.",
                "domain-research (406 vetted domains) & warrant provenance.",
            ],
            [
                "RXVM, BEAM & dBA (risk score 100 reject) + metrix.",
                "gemseal (HKDF-SHA256 + ChaCha20-Poly1305) & kevlar MCP rug-pull guard.",
                "cortex (12/9/12 buckets), Visor*, safety-stream, nina, spectral.",
                "fieldwork (54 caps), prompt-architect, wardrobe (1,281 DCWF atoms).",
            ],
        ],
        "42 INTEGRATED REPOS (0 NESTED .git)  ·  11/11 WAVE 1 + 15/15 WAVE 2 VERIFIER CHECKS PASSING",
        speaker_notes=(
            "Wave 1 (11/11) and Wave 2 (15/15) portfolio upgrades across 42 integrated repositories (zero nested .git), "
            "covering injection-gate, capo, nuclide-color-v2, domain-research (406 domains), RXVM, BEAM, dBA, gemseal, "
            "kevlar, and 1,281 DCWF atoms."
        ),
    )


def _v3_slide10() -> Slide:
    title = "Wave 3 Vault: TrustEngine, Dual-Path, Vec2Text & ROS"
    cv, th = _new_body_canvas(title, 10, 12, "WAVE 3 VAULT", "6/6 Checks · Go Race Clean", "mono")
    gr = GraphDoc(
        title="Wave 3 TrustEngine & Verification Metrics",
        chart_type="v_cluster",
        categories=["Clean Trust", "Coerced Cap", "Drafts", "Findings", "Vault Mods", "High Sev"],
        series=[{"name": "Wave 3 Metric", "values": [0.8659, 0.15, 10.0, 7.0, 5.0, 4.0], "color": JADE}],
        x_label="5-Dim TrustEngine (0.8659 vs 0.15 Coerced) + Vault",
        y_label="Score / Count",
        theme=th,
        sister_id="mono",
    )
    _add_framed_graph(cv, [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE], gr, accent_color=JADE)
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "Five Wave-3 Security Hardening Upgrades",
        [
            ("1. 5-Dim TrustEngine:", "output <= source bound (0.8659 clean vs 0.15 coerced cap) + Lume EQ audio haze."),
            ("2. 4 AI-Agent Auditors:", "Detects capability surplus, missing syslog/HITL, .rodata tools & AI package markers."),
            ("3. DualPathVerifier:", "P_T vs P_L divergence -> VisorLog [MASK] flashcard flywheel (THRESHOLD_MISMATCH held)."),
            ("4. Slow-Drift & Vec2Text:", "Eq. 2 cascade + gemseal vec2text recovery + kevlar SSH/filter/injection guards."),
            ("5. Email, ROS & VisorCAS:", "AgentEmailGuardrail + 46-DoF ROS deadman interlock + Go BloomCASDedup (go test -race 0)."),
        ],
        accent_color=GOLD,
        pill_text="WAVE 3 VAULT · 6/6 VERIFIED",
        font_pt=8.7,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Wave 3 Vault (6/6 PASS): 5-dim TrustEngine (0.8659 clean vs 0.15 coerced), 4 AI-Agent Binary Auditors, "
            "DualPathVerifier + VisorLog [MASK] flywheel, Eq. 2 slow-drift + gemseal vec2text + kevlar guards, "
            "and AgentEmailGuardrail + 46-DoF ROS deadman + Go VisorCAS (go test -race exit 0)."
        ),
    )


def _v3_slide11() -> Slide:
    title = "4 AI-Agent Binary Auditors & SeaSIP GEM/GSX Rebuild"
    cv, th = _new_body_canvas(title, 11, 12, "AUDITORS & SEASIP GEM", "7 Findings · 9/9 GEM Scenes", "mono")
    _add_card_bullets(
        cv,
        [X_LEFT, Y_TOP, X_LEFT + W_HALF, Y_BOTTOM_SAFE],
        "Four AI-Agent Binary Auditors (7 Findings, 4 HIGH)",
        [
            ("1. AgentAuthorityAudit:", "Flags PLT capability surplus (system/exec/curl) exceeding declared manifest."),
            ("2. AgentObservabilityAudit:", "Detects missing syslog, HITL confirmation & immutable audit trail hooks."),
            ("3. AgentToolSurfaceEnumerator:", "Extracts embedded .rodata JSON tool schemas & unrestricted shell bindings."),
            ("4. AIControlIndicators:", "Catches AI-generated binary markers, hallucinated package names & unsafe stubs."),
        ],
        accent_color=RUBY,
        pill_text="components/ablation/ablation/analyzers/",
        font_pt=9.0,
    )
    _add_card_bullets(
        cv,
        [X_RIGHT, Y_TOP, X_RIGHT + W_HALF, Y_BOTTOM_SAFE],
        "SeaSIP GEM / GSX Clean-Room Fidelity (5/5, 9/9)",
        [
            ("Spec-Exact .GEM:", "33,394-byte binary metafile (893 VDI records) passing seasip_gem verification."),
            ("Dual-Endian .RSC:", "812 B x86 Little-Endian & 816 B Motorola 68000 Big-Endian Atari TOS resources."),
            ("GEM .IMG & GSX-86:", "8,532 B XIMG RLE bit-plane raster + 3,678 B GSX-86 vector plotter (154 NDC calls)."),
            ("AES Window Limit:", "Enforces authentic 7-window Digital Research AES ceiling (8/8 Wave-3 SeaSIP tests)."),
        ],
        accent_color=JADE,
        pill_text="WAVE 3 SEASIP GEM / GSX (8/8 PASS)",
        font_pt=9.0,
    )
    return Slide(
        title=title,
        canvas=cv,
        speaker_notes=(
            "Four AI-Agent Binary Auditors (AgentAuthorityAudit, AgentObservabilityAudit, AgentToolSurfaceEnumerator, "
            "AIControlIndicators: 7 findings, 4 HIGH) alongside SeaSIP GEM/GSX clean-room rebuild (5/5 checks, 9/9 scenes, "
            "812B x86 LE & 816B 68k BE .RSC, 154 GSX-86 NDC calls)."
        ),
    )


def _v3_slide12() -> Slide:
    title = "Vol. III Verification Seal & Constitutional Zero-Trust"
    return _build_scorecard_2x2_dark(
        12,
        "mono",
        "ZERO-TRUST SEAL",
        title,
        "Vol. III Conclusion",
        [
            (RUBY, "1. Ablation RE & AIARE", [
                "333 analyzers + 2,953 tests + 19/19 AIARE paired experiments.",
                "RXVM (80), A10 saturation (26.5035), BEAM (100), scoped angr, Overmatch draft.",
                "PALA 0.3.0 (25/25 Rust, raw_devices_accessed=false).",
            ]),
            (DARK_JADE, "2. Cryptanalysis C1–C26 & CNSA 2.0", [
                "SymPy Friedman IC == Kloster M2 (residual = 0).",
                "CNSA 2.0 LMS, ML-KEM, ML-DSA, GCM-SIV, SHA-384 + Ring-3 Skipjack.",
                "Honest unsolved benchmarks: Kryptos K4 (97 ch) & NSA May 26.",
            ]),
            (GOLD_BRIGHT, "3. Zero-Trust Portfolio & Auditors", [
                "42 integrated repos (11/11 W1 + 15/15 W2) + 5 Wave-3 Vault (6/6).",
                "4 AI-Agent Binary Auditors (7 findings, 4 HIGH) + 311/311 gate (0% FP).",
                "8.93x tri-witness fault reduction + SeaSIP GEM/GSX (5/5, 9/9).",
            ]),
            (SKY, "4. Constitutional & Hygiene Invariants", [
                "Zero personal paths, zero serials, zero emails, zero raw IPs.",
                "authorized_targets_only = True · external_actions = 0 · $0.00 offline.",
                "operational_metacognition_verified = True · sentience_claimed = False.",
            ]),
        ],
        f"authorized_targets_only=True · external_actions=0 · {ATTRIBUTION_TEXT} · 12 / 12",
        speaker_notes=(
            "Vol. III verification seal covering zoe-ecosystem-ablation-re/v1, zoe-kloster-cryptanalysis-gauntlet/v2, "
            "zoe-nsa-research-puzzle-pack/v1, zoe-cnsa2-scrna-ring2/v1, zoe-nsa-ring3-deep-crypto/v1, "
            "zoe-security-forensics-redteam/v1, and zoe-wave3-seasip-gem-verification/v1. "
            "Kryptos K4 and NSA May 26 explicitly remain unsolved."
        ),
    )


def build_vol3_deck() -> SlideDeck:
    """Build Anthology Vol. III — Reverse Engineering, Cryptanalysis & Zero-Trust Defense (12 slides)."""
    return SlideDeck(
        slug=VOL3_SLUG,
        title="Vol. III — Reverse Engineering, Cryptanalysis & Zero-Trust Defense",
        subtitle="Ablation AIARE (19/19) · RXVM/BEAM/PALA · CNSA 2.0 C1–C26 · Wave 1–3 & 4 AI Binary Auditors",
        volume_label="Vol. III",
        sister_id="mono",
        category="Anthology Volume",
        date="2026-11-25",
        summary=(
            "12-slide presentation covering Ablation AIARE (333 analyzers, 2,953 tests, 19/19), RXVM & A10 saturation, "
            "BEAM IFF, PALA Rust carving, CNSA 2.0 & Kloster C1–C26 (honest unsolved Kryptos K4 & May 26), "
            "Wave 1–3 firewall (42 repos + 5 Vault), 4 AI-Agent Binary Auditors, and SeaSIP GEM/GSX."
        ),
        constitutional=dict(ANTHOLOGY_CONSTITUTIONAL),
        slides=[
            _v3_slide01(), _v3_slide02(), _v3_slide03(), _v3_slide04(),
            _v3_slide05(), _v3_slide06(), _v3_slide07(), _v3_slide08(),
            _v3_slide09(), _v3_slide10(), _v3_slide11(), _v3_slide12(),
        ],
    )


def build_anthology_vol1_3() -> list[SlideDeck]:
    """Return Anthology Volumes I–III as a list of `SlideDeck` objects."""
    return [build_vol1_deck(), build_vol2_deck(), build_vol3_deck()]


def _publish_single_gallery(deck: SlideDeck, root: Path) -> dict[str, Any]:
    gallery_dir = root / "galleries" / deck.slug
    if gallery_dir.is_dir():
        for stale in gallery_dir.glob("slide-*.*"):
            if stale.is_file():
                stale.unlink()

    build_info = deck.build(
        gallery_dir,
        overwrite=True,
        render_png=True,
        render_jpg=False,
        render_svg=False,
        width=1920,
        height=1080,
    )
    gem_files = sorted(gallery_dir.glob("slide-*.gem"))
    _verify_deck_gems(gem_files)
    for gf in gem_files:
        chk = seasip_gem.verify_seasip_gem_metafile(gf.read_bytes())
        if not chk.get("valid"):
            raise ValueError(f"Invalid .gem metafile {gf}: {chk}")

    bad_layouts = [r["index"] for r in build_info["slides"] if not r.get("layout_ok")]
    if bad_layouts:
        raise ValueError(f"Layout verification failed for {deck.slug} slides: {bad_layouts}")

    readme_md = _extract_deck_notes_markdown(deck, build_info, root)
    assert_hygiene_clean(readme_md, f"galleries/{deck.slug}/README.md")
    atomic_write_text(gallery_dir / "README.md", readme_md)

    png_files = sorted(gallery_dir.glob("slide-*.png"))
    return {
        "slug": deck.slug,
        "gallery_dir": str(gallery_dir),
        "slides": len(deck.slides),
        "gem_count": len(gem_files),
        "png_count": len(png_files),
        "layout_ok": True,
    }


def publish_vol1_3_galleries(pres_root: Path | str | None = None) -> list[dict[str, Any]]:
    """Build and verify ONLY Vol. I–III galleries without touching shared M4 ledger files."""
    root = Path(pres_root) if pres_root is not None else DEFAULT_PRES_ROOT
    return [_publish_single_gallery(deck, root) for deck in build_anthology_vol1_3()]


__all__ = [
    "ANTHOLOGY_CONSTITUTIONAL",
    "DEFAULT_PRES_ROOT",
    "VOL1_SLUG",
    "VOL2_SLUG",
    "VOL3_SLUG",
    "build_anthology_vol1_3",
    "build_vol1_deck",
    "build_vol2_deck",
    "build_vol3_deck",
    "publish_vol1_3_galleries",
]
