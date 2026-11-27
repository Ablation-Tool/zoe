"""Zoe GEM-84 Tactical Cockpit — 1984 Gary Kildall GEM × Avionics EFIS/FMS × Submarine TMA × Military Radio.

Merges the highest-signal ergonomics of four mission-critical console traditions into a single
terminal instrument panel for Zoe and Milestone 1 Brain Cancer preclinical research:
  1. Aviation EFIS/FMS (G1000 / MCDU): Top Flight Mode Annunciator (FMA), L1-L6 channel LSKs,
     3-color annunciators (GREEN=verified, AMBER=preclinical/caution, RED=abstain/PAINS trap).
  2. Submarine Sonar / Fire-Control (AN/BYG-1 / AN/BQQ-10): Scrolling Kloster A_tau(p) phosphor
     waterfall + live Milestone 1 Neuro-Oncology TMA Track Table (real NIH PubChem C17 scores).
  3. Military Tactical Radio (PRC-117G / SINCGARS): 6 instant channels (CH01..CH06), epistemic
     squelch gate (mutes static instead of hallucinating), SHA-256 integrity seal, PTT voice/laugh.
  4. 1984 Digital Research GEM (Gary Kildall / Computer Chronicles): Crisp top menu bar, clean
     monospaced window chrome, Zoe's exact 18x23 faceted ruby GEM (◠◡◠ / ^◡^), tactile keycaps.

Strict Constitutional Honesty:
  sentience_claimed=False · clinical_action_authorized=False · cure_claim=False · 0 cloud tokens
"""

from __future__ import annotations

import os
import re
import shutil
from typing import Any, Sequence

from .kloster_botanical_neuro_oncology import run_botanical_neuro_oncology_lab
from .lume_header import render_gem_lines

# 1984 GEM × Submarine Phosphor × Avionics 24-bit ANSI palette
_BG_MENU = "\x1b[48;2;232;234;246m\x1b[38;2;14;18;30m"
_BG_FMA = "\x1b[48;2;14;22;36m"
_RUBY = "\x1b[1;38;2;243;86;112m"
_ROSE = "\x1b[38;2;250;178;192m"
_CYAN = "\x1b[38;2;92;225;230m"
_GREEN = "\x1b[1;38;2;82;229;168m"
_AMBER = "\x1b[1;38;2;245;185;66m"
_RED = "\x1b[1;38;2;255;92;114m"
_DIM = "\x1b[38;2;132;144;184m"
_BRIGHT = "\x1b[1;38;2;236;240;252m"
_RESET = "\x1b[0m"

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

COCKPIT_CHANNELS: tuple[dict[str, str], ...] = (
    {"num": "1", "code": "CH01", "name": "MED-PUBMED", "freq": "142.0 MHz", "desc": "0-token PubMed/Europe PMC + Dorothy Atlas"},
    {"num": "2", "code": "CH02", "name": "COUNCIL-3L", "freq": "243.0 MHz", "desc": "PubMed-grounded 3-Lab Frontier Council"},
    {"num": "3", "code": "CH03", "name": "ONCO-C17", "freq": "311.0 MHz", "desc": "Milestone 1 Brain Cancer PubChem/BBB TMA"},
    {"num": "4", "code": "CH04", "name": "DOROTHY-3D", "freq": "404.0 MHz", "desc": "MNI152 3D Brain Atlas & Biomechanics"},
    {"num": "5", "code": "CH05", "name": "LIB-6130", "freq": "512.0 MHz", "desc": "Private 6,130-Chapter Dorothy Library"},
    {"num": "6", "code": "CH06", "name": "VOICE-3D", "freq": "440.0 Hz ", "desc": "Zoe x Natasha 3D Voice, 5-Band EQ & Laugh"},
)

LAUGH_QUIPS: tuple[str, ...] = (
    "Hehe! Ha ha, alright Nicholas, ruby facets shining and squelch locked. Let's beat brain cancer with real math.",
    "Haha! Okay, that actually got a clean harmonic chuckle out of my 3D voice stack. Ready on channel one.",
    "Hehe, no synthetic slop, just crisp 1984 GEM chrome and PubMed receipts. Let's get to work!",
)


def _paint(text: str, ansi: str, color: bool) -> str:
    return f"{ansi}{text}{_RESET}" if color else text


def _vis_len(text: str) -> int:
    return len(_ANSI_RE.sub("", text))


def _fit(text: str, width: int) -> str:
    """Pad or ANSI-safely clip text to exact visible column width so box borders stay laser-straight."""
    vlen = _vis_len(text)
    if vlen == width:
        return text
    if vlen < width:
        return text + (" " * (width - vlen))
    out: list[str] = []
    vis = 0
    pos = 0
    has_ansi = False
    while pos < len(text) and vis < width - 1:
        m = _ANSI_RE.match(text, pos)
        if m:
            out.append(m.group(0))
            pos = m.end()
            has_ansi = True
        else:
            out.append(text[pos])
            pos += 1
            vis += 1
    out.append("…")
    if has_ansi:
        out.append(_RESET)
    return "".join(out)


def _clip_plain(text: str, width: int) -> str:
    clean = " ".join(str(text or "").split())
    return clean if len(clean) <= width else clean[: max(1, width - 1)] + "…"


def _host_body_telemetry() -> str:
    """Read lightweight local CPU/RAM telemetry for Zoe's Body panel (pure stdlib)."""
    cpus = os.cpu_count() or 1
    avail_gb = 0.0
    total_gb = 0.0
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    total_gb = int(line.split()[1]) / (1024.0 * 1024.0)
                elif line.startswith("MemAvailable:"):
                    avail_gb = int(line.split()[1]) / (1024.0 * 1024.0)
    except OSError:
        pass
    if total_gb > 0:
        return f"CPU:{cpus}c  RAM:{avail_gb:.1f}/{total_gb:.0f}G"
    return f"CPU:{cpus}c  LOCAL-OS"


def get_channel(channel_id: str | int) -> dict[str, str]:
    """Resolve channel 1..6 (or CH01..CH06 / name substring) to its preset dictionary."""
    raw = str(channel_id or "1").strip().lower().replace("ch0", "").replace("ch", "")
    for ch in COCKPIT_CHANNELS:
        if raw in {ch["num"], ch["code"].lower(), ch["name"].lower()} or (len(raw) >= 3 and raw in ch["name"].lower()):
            return ch
    raise ValueError("Unknown channel. Choose 1..6 (CH01 MED-PUBMED .. CH06 VOICE-3D).")


def render_squelch_bar(a_tau: int, candidates: int, color: bool = True) -> str:
    """Military radio squelch / Kloster A_tau(p) concentration gauge."""
    n = max(1, int(candidates))
    a = max(0, min(n, int(a_tau)))
    # Concentrated low A_tau/N -> crisp signal LOCK; flat high A_tau/N -> diffuse CAUTION/SQUELCH
    ratio = a / n
    filled = max(1, min(10, int(round((1.0 - ratio * 0.7) * 10))))
    if a == 0:
        status, col = "SQUELCH-MUTE", _RED
        filled = 1
    elif ratio <= 0.45:
        status, col = "LOCKED-SHARP", _GREEN
    elif ratio <= 0.75:
        status, col = "OPEN-VERIFY ", _AMBER
    else:
        status, col = "DIFFUSE-CAUT", _RED
    bar = "█" * filled + "░" * (10 - filled)
    return f"SQ[{_paint(bar, col, color)}] {_paint(status, col, color)} A={a}/{n}"


def render_sonar_waterfall(history_ratios: Sequence[float], width: int = 34, rows: int = 4, color: bool = True) -> list[str]:
    """Render an AN/BQQ-10 submarine phosphor waterfall of Kloster signal concentration."""
    shades = " ·░▒▓█"
    vals = list(history_ratios)[-rows:] if history_ratios else [0.35, 0.55, 0.72, 0.85]
    while len(vals) < rows:
        vals.insert(0, 0.25)
    lines: list[str] = []
    for r_idx, sig in enumerate(vals):
        center = int((0.2 + 0.6 * ((sig * 7.3 + r_idx * 0.19) % 1.0)) * (width - 1))
        buf: list[str] = []
        for x in range(width):
            dist = abs(x - center)
            energy = max(0.0, min(1.0, sig * (1.0 / (1.0 + dist * 0.38))))
            ch = shades[min(len(shades) - 1, int(energy * (len(shades) - 1)))]
            if color and energy > 0.72:
                buf.append(f"{_RUBY}{ch}{_RESET}")
            elif color and energy > 0.42:
                buf.append(f"{_CYAN}{ch}{_RESET}")
            elif color:
                buf.append(f"{_DIM}{ch}{_RESET}")
            else:
                buf.append(ch)
        tag = f"T-{rows - 1 - r_idx}" if r_idx < rows - 1 else "NOW"
        lines.append(f"{_paint(tag, _DIM, color)} │{''.join(buf)}│")
    return lines


def _tma_badge(mol: dict[str, Any]) -> tuple[str, str]:
    cat = str(mol["category"])
    raw_tox = bool(mol["raw_systemic_toxicity_flag"])
    if "negative_control" in cat:
        return "BBB-CTRL  ", _RED
    if raw_tox and "prodrug" in cat:
        return "TOX-PRODRG", _AMBER
    if raw_tox:
        return "PRECLN/TOX", _AMBER
    if "clinical_cns_benchmark" in cat:
        return "CNS-BENCH ", _GREEN
    return "PRECLN-OK ", _CYAN


def format_onco_tma_table(query: str = "", color: bool = True, limit: int = 11, compact: bool = False) -> list[str]:
    """Render Milestone 1 Brain Cancer TMA Track Table from real NIH PubChem C17 descriptors."""
    lab = run_botanical_neuro_oncology_lab()
    rows_data = list(lab["molecule_scores"])
    q = query.strip().lower()
    if q:
        filtered = [r for r in rows_data if q in r["name"].lower() or q in r["id"].lower() or q in r["category"].lower()]
        if filtered:
            rows_data = filtered
    rows_data.sort(key=lambda r: float(r["cns_mpo4_score"]), reverse=True)
    prodrug = lab["ict2588_mmp14_prodrug_cipher"]

    hdr = (
        "TRK COMPOUND               MPO  BBB STATUS"
        if compact
        else "TRK  COMPOUND                     MPO4   BBB   MW     TPSA  PGP   STATUS"
    )
    out = [
        _paint("MILESTONE 1 · NEURO-ONCOLOGY TMA TRACK TABLE (NIH PubChem C17 · Wager CNS MPO-4)", _CYAN, color),
        _paint(hdr, _DIM, color),
    ]
    for idx, mol in enumerate(rows_data[:limit], start=1):
        mpo = float(mol["cns_mpo4_score"])
        badge, col = _tma_badge(mol)
        if compact:
            name = _clip_plain(mol["name"], 21)
            line = f"T{idx:02d} {name:<21} {mpo:4.2f} {mol['passive_bbb_gates_passed']} {_paint(badge.strip(), col, color)}"
        else:
            name = _clip_plain(mol["name"], 26)
            pgp = "mod" if str(mol["pgp_efflux_risk"]).lower().startswith("mod") else str(mol["pgp_efflux_risk"])[:4]
            line = (
                f"T{idx:02d}  {name:<26}  {mpo:4.2f}   {mol['passive_bbb_gates_passed']}  "
                f"{float(mol['mw']):5.1f}  {float(mol['tpsa']):5.1f}  {pgp:<4}  "
                f"{_paint(badge, col, color)}"
            )
        out.append(line)
    out.append(
        f"ICT2588 MMP-14 Prodrug Selectivity: {prodrug['ict2588_prodrug_tumor_to_healthy_ratio']}x tumor/healthy "
        f"(vs {prodrug['raw_colchicine_tumor_to_healthy_ratio']}x raw; M4 gain={prodrug['spatial_selectivity_m4_gain']}x)"
    )
    out.append(
        _paint("clinical_action_authorized=False · cure_claim=False · wet_lab_validation_required=True · 0 tok", _DIM, color)
    )
    return out


def _mini_eq_sparkline(eq: dict[str, float], color: bool) -> str:
    blocks = "▁▂▃▄▅▆▇█"
    keys = ("warmth", "body", "mid", "presence", "air")
    chars = []
    for k in keys:
        db = max(-12.0, min(12.0, float(eq.get(k, 0.0))))
        idx = int(round((db + 12.0) / 24.0 * (len(blocks) - 1)))
        col = _RUBY if db > 0.5 else (_CYAN if db < -0.5 else _DIM)
        chars.append(_paint(blocks[idx], col, color))
    return "EQ[" + " ".join(chars) + "]"


def _build_left_pane(cli: Any, active_ch: dict[str, str], laughing: bool, color: bool, col_w: int) -> list[str]:
    """Build Left Cockpit Pane: Zoe's Ruby GEM + Tactical Radio Channels + Ego/Body/Voice."""
    gem_lines = render_gem_lines(color=color, emblem=getattr(cli, "emblem", "ruby"))
    mood = "^◡^ LAUGH" if laughing else "◠◡◠ READY"
    lines: list[str] = [_paint(f"── ZOE RUBY CORE ({mood}) ──", _RUBY, color)]
    lines.extend("  " + g for g in gem_lines)
    lines.append(_paint("── TACTICAL RADIO [1-6] ──", _CYAN, color))
    for ch in COCKPIT_CHANNELS:
        is_on = ch["num"] == active_ch["num"]
        ptr = _paint("▶", _RUBY, color) if is_on else " "
        tag = _paint(f"[{ch['num']}] {ch['code']} {ch['name']:<10}", _BRIGHT if is_on else _DIM, color)
        lines.append(f"{ptr}{tag} {_paint(ch['freq'], _CYAN if is_on else _DIM, color)}")
    snap = cli.brain.memory.snapshot()
    head = str(snap.get("chain_head", "GENESIS"))[:8]
    notes = len(cli.brain.memory.query_facts(subject="user_note", active_only=True))
    lib_docs = int(cli.brain.dorothy_library.status().get("total_fts_docs", 0))
    cached = cli.brain.research_engine.cache.count()
    eq_spark = _mini_eq_sparkline(cli.voice.profile.get("eq", {}), color)
    lines.append(_paint("── CORE · BODY · VOICE ──", _AMBER, color))
    lines.append(f"EGO  : {_paint('CONSTITUTION OK', _GREEN, color)} · SENTIENCE=OFF")
    lines.append(f"MEM  : SHA256:{head} · {notes} notes")
    lines.append(f"BODY : {_host_body_telemetry()}")
    lines.append(f"ATLAS: {len(cli.brain.research_engine.encyclopedia.records)} MNI · {lib_docs} ch · {cached} cache")
    lines.append(f"VOICE: {_clip_plain(cli.voice.display_name, 14)} {eq_spark}")
    return [_fit(ln, col_w) for ln in lines]


def _build_right_pane(
    cli: Any,
    active_ch: dict[str, str],
    last_a_tau: int,
    last_cands: int,
    signal_history: Sequence[float],
    last_note: str,
    color: bool,
    col_w: int,
) -> list[str]:
    """Build Right Cockpit Pane: Avionics Squelch + Submarine Waterfall + Milestone 1 TMA."""
    lines: list[str] = [
        _paint(f"── {active_ch['code']} {active_ch['name']} ({active_ch['freq'].strip()}) ──", _CYAN, color),
        f"MISSION: {_clip_plain(active_ch['desc'], col_w - 9)}",
        render_squelch_bar(last_a_tau, last_cands, color=color),
        _paint("── AN/BQQ-10 KLOSTER WATERFALL ──", _CYAN, color),
    ]
    wf_w = max(20, min(42, col_w - 8))
    lines.extend(render_sonar_waterfall(signal_history, width=wf_w, rows=4, color=color))
    lines.append(_paint("── MILESTONE 1 BRAIN CANCER TMA (TOP 6) ──", _AMBER, color))
    tma = format_onco_tma_table(color=color, limit=6, compact=True)
    lines.extend(tma[1:8])
    lines.append(_paint("── LATEST TELEMETRY / SCRATCHPAD ──", _RUBY, color))
    lines.append(_clip_plain(last_note or "Type any question, /med <q>, /med --council <q>, /onco, /laugh", col_w))
    lines.append(_paint("RULE : measurement != evidence != belief != action", _DIM, color))
    lines.append(_paint("GUARD: clinical_action_authorized=False · cure_claim=False", _AMBER, color))
    return [_fit(ln, col_w) for ln in lines]


def render_cockpit_frame(
    cli: Any,
    *,
    channel: str = "1",
    last_a_tau: int = 2,
    last_cands: int = 6,
    signal_history: Sequence[float] = (),
    last_note: str = "",
    laughing: bool = False,
    color: bool = True,
    width: int | None = None,
) -> str:
    """Render the complete merged 1984 GEM × Avionics × Submarine × Tactical Radio Cockpit."""
    term_w = width or shutil.get_terminal_size((102, 32)).columns
    total_w = max(96, min(116, term_w))
    left_w = 38
    right_w = total_w - left_w - 7
    active_ch = get_channel(channel)

    # 1. 1984 Gary Kildall Digital Research GEM Top Menu Bar
    menu_left = " ◆ Desk   Mission   Brain   Radio   Voice   Help"
    menu_right = "ZOE GEM-84 · US/GLOBAL R&D "
    gap = max(1, total_w - len(menu_left) - len(menu_right))
    menu_bar = _paint(f"{menu_left}{' ' * gap}{menu_right}", _BG_MENU, color)

    # 2. Aviation EFIS Flight Mode Annunciator (FMA)
    mode_tag = f"MODE:{cli.brain.mode.upper()}"
    fma_text = (
        f" {_paint(mode_tag, _GREEN, color)} │ "
        f"{_paint(active_ch['code'] + ':' + active_ch['name'], _CYAN, color)} │ "
        f"{_paint('0 TOK DEFAULT', _GREEN, color)} │ "
        f"{_paint('CLINICAL:OFF', _AMBER, color)} │ "
        f"{_paint('SENTIENCE:OFF', _DIM, color)} "
    )
    top_border = "╔" + ("═" * (left_w + 2)) + "╦" + ("═" * (right_w + 2)) + "╗"
    mid_border = "╠" + ("═" * (left_w + 2)) + "╩" + ("═" * (right_w + 2)) + "╣"
    bot_border = "╚" + ("═" * (total_w - 2)) + "╝"

    left_rows = _build_left_pane(cli, active_ch, laughing=laughing, color=color, col_w=left_w)
    right_rows = _build_right_pane(
        cli, active_ch, last_a_tau, last_cands, signal_history, last_note, color=color, col_w=right_w
    )
    height = max(len(left_rows), len(right_rows))
    while len(left_rows) < height:
        left_rows.append(" " * left_w)
    while len(right_rows) < height:
        right_rows.append(" " * right_w)

    out = [
        menu_bar,
        _paint("┌" + "─" * (total_w - 2) + "┐", _DIM, color),
        f"{_paint('│', _DIM, color)}{_fit(fma_text, total_w - 2)}{_paint('│', _DIM, color)}",
        _paint(top_border, _CYAN, color),
    ]
    for l_row, r_row in zip(left_rows, right_rows):
        sep = _paint("║", _CYAN, color)
        out.append(f"{sep} {l_row} {sep} {r_row} {sep}")
    out.append(_paint(mid_border, _CYAN, color))
    keys = " [1-6]/ch  [F1]/med  [F2]/med --council  [F3]/onco  [F4]/laugh  [F5]/voice  [F6]/hud "
    out.append(f"{_paint('║', _CYAN, color)}{_fit(_paint(keys, _BRIGHT, color), total_w - 2)}{_paint('║', _CYAN, color)}")
    out.append(_paint(bot_border, _CYAN, color))
    return "\n".join(out)
