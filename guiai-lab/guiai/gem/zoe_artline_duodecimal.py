"""Artline Duodecimal Classification System (ADC-12) — 4-Column GEM Shorthand Library.

100% original clean-room Python + Artline/GEM VDI + offline HTML5 Card Catalog.
Inspired by Digital Research Artline 2.0 Utilities Guide (Aug 1990, pp. A-2 & A-3),
where every character slot carries four synchronized columns:
  1. Decimal (plus Base-12 Duodecimal call address — note Page A-2 ends at 143 = EE_12
     and Page A-3 starts at 144 = 100_12, one exact gross = 12^2!)
  2. International (fast keyboard-typable shorthand character)
  3. Symbol (Font ID 128 — Greek, Math & Logic notation)
  4. Wombats (Font ID 131 — crisp visual stamp / highlight badge)

Organizes conversation highlights, engineering artifacts, math proofs, and creative
brainstorms into 12 Duodecimal Major Classes (`000_12` through `E00_12`, using standard
Dozenal digits 0-9, X=10, E=11) with 12 subdivisions each — like a Base-12 Dewey Decimal
System built purely on GEM & Artline typography.

Constitutional Invariants (`CONSTITUTION.md`):
  clean_room_original = True · external_actions = 0 · sentience_claimed = False
  clinical_action_authorized = False · cure_claim = False · tokens_used = 0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .artline import ArtlineDocument

ADC12_CONTRACT = "zoe-artline-duodecimal/v1"
DOZENAL_DIGITS = "0123456789XE"

CONSTITUTIONAL_FLAGS: dict[str, Any] = {
    "clean_room_original": True,
    "external_actions": 0,
    "sentience_claimed": False,
    "l5_agi_qualified": False,
    "clinical_action_authorized": False,
    "cure_claim": False,
    "tokens_used": 0,
    "attribution": (
        "Concept by Nicholas Michael Kloster; grounded in Digital Research Artline 2.0 "
        "Utilities Guide (Aug 1990, pp. A-2/A-3)"
    ),
}


# ---------------------------------------------------------------------------
# 1. Pure Base-12 (Duodecimal / Dozenal) Math Utilities
# ---------------------------------------------------------------------------

def to_duodecimal(value: int, *, min_width: int = 1) -> str:
    """Convert a non-negative integer to base-12 using standard digits 0-9, X (10), E (11)."""
    n = int(value)
    if n < 0:
        raise ValueError(f"Duodecimal catalog index must be >= 0, got {value}")
    if n == 0:
        return "0".rjust(min_width, "0")
    out: list[str] = []
    while n > 0:
        n, rem = divmod(n, 12)
        out.append(DOZENAL_DIGITS[rem])
    return "".join(reversed(out)).rjust(min_width, "0")


def from_duodecimal(text: str) -> int:
    """Parse a base-12 string (accepts X/A/↊ for 10, E/B/↋ for 11, optional '_12' or '₁₂' suffix)."""
    clean = (
        str(text)
        .strip()
        .upper()
        .replace("_12", "")
        .replace("₁₂", "")
        .replace("↊", "X")
        .replace("↋", "E")
        .replace("A", "X")
        .replace("B", "E")
    )
    if not clean:
        raise ValueError(f"Empty duodecimal value: {text!r}")
    total = 0
    for ch in clean:
        idx = DOZENAL_DIGITS.find(ch)
        if idx < 0:
            raise ValueError(f"Invalid duodecimal digit {ch!r} in {text!r}")
        total = total * 12 + idx
    return total


# ---------------------------------------------------------------------------
# 2. Authentic 1990 Artline pp. A-2 / A-3 4-Column Duodecimal Catalog (ADC-12)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ADC12Entry:
    """One Artline Duodecimal Classification entry anchored to Pages A-2 or A-3."""

    call_code: str          # e.g. "100", "310", "X00", "E00" (Base-12 Dewey call number)
    major_digit: str        # "0".."9", "X", "E"
    class_name: str         # Human-readable major class or subdivision name
    decimal_code: int       # Authentic Artline Utilities Guide Decimal column (32..255)
    international: str      # Authentic Artline Column 2: International
    symbol: str             # Authentic Artline Column 3: Symbol (Font ID 128)
    wombat: str             # Authentic Artline Column 4: Wombats (Font ID 131)
    page_ref: str           # "A-2" (32..143) or "A-3" (144..255)
    shorthand_use: str      # When to apply this highlight/label in chat or workspace
    color_hex: str          # Palette accent for studio & deck display
    is_major: bool = True

    @property
    def artline_dozenal(self) -> str:
        """Base-12 representation of the Artline Decimal table row."""
        return to_duodecimal(self.decimal_code, min_width=2)

    @property
    def call_badge(self) -> str:
        """Compact chat shorthand tag, e.g. '[100₁₂ · Z · ✺]'."""
        return f"[{self.call_code}₁₂ · {self.international} · {self.wombat}]"

    @property
    def four_column_stamp(self) -> str:
        """Full 4-column Artline stamp showing Decimal/Base-12 | International | Symbol | Wombats."""
        return (
            f"[{self.call_code}₁₂ | Dec {self.decimal_code} ({self.artline_dozenal}₁₂) | "
            f"Int {self.international} | Sym {self.symbol} | Wom {self.wombat}]"
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["artline_dozenal"] = self.artline_dozenal
        d["call_badge"] = self.call_badge
        d["four_column_stamp"] = self.four_column_stamp
        return d


# 12 Major Duodecimal Classes (000_12 .. E00_12) — every single row verified against pp. A-2 & A-3
ADC12_MAJOR_CLASSES: tuple[ADC12Entry, ...] = (
    ADC12Entry("000", "0", "Core & Architecture", 118, "v", "ϖ", "❖", "A-2", "System rules, GEM/Artline structure, meta-schema", "#ac82ff", True),
    ADC12Entry("100", "1", "Ideas & Brain-Blasts", 90, "Z", "Z", "✺", "A-2", "New creative sparks, wild concepts, brainstorm prompts", "#f8cc30", True),
    ADC12Entry("200", "2", "Decisions & Approvals", 51, "3", "3", "✓", "A-2", "Locked choices, green-lit plans, confirmed direction", "#52e5a8", True),
    ADC12Entry("300", "3", "Science, Math & Proof", 83, "S", "Σ", "✶", "A-2", "Kloster math, SymPy/Z3, AlphaFold, oncology analysis", "#4f8ef7", True),
    ADC12Entry("400", "4", "Art, Visuals & Decks", 46, ".", ".", "✎", "A-2", "Artline vectors, PowerPoints, sprites, GIFs, layouts", "#ff85b3", True),
    ADC12Entry("500", "5", "Code & Clean-Room Build", 108, "l", "λ", "●", "A-2", "Implementation, refactoring, build->RE->rebuild loops", "#5ce1e6", True),
    ADC12Entry("600", "6", "Verify, Test & Freeze", 101, "e", "ε", "❄", "A-2", "Pytest/mypy checks, visual audits, frozen ground truth", "#6cb4ff", True),
    ADC12Entry("700", "7", "Drafts & Bookmarks", 111, "o", "o", "❏", "A-2", "Glass-box scratchpad cards, save-for-later notes", "#7be0d6", True),
    ADC12Entry("800", "8", "Actions & Next Steps", 42, "*", "*", "☛", "A-2", "Immediate next task, focus pointer, execution queue", "#ffb347", True),
    ADC12Entry("900", "9", "Priority & Favorites", 78, "N", "N", "★", "A-2", "Top-priority anchors, must-keep breakthroughs", "#f35670", True),
    ADC12Entry("X00", "X", "Guards, Stops & Cuts", 53, "5", "5", "✕", "A-2", "Hard 'no', constitutional boundary, trim/reject", "#e8687a", True),
    ADC12Entry("E00", "E", "Play, Physics & Freeform", 44, ",", ",", "✌", "A-2", "Optional-Physics Room, relaxed sandbox, zero pressure", "#88f0b8", True),
)

# 24 Curated Duodecimal Subdivisions spanning Pages A-2 and A-3 (144 = 100_12 boundary!)
ADC12_SUBCLASSES: tuple[ADC12Entry, ...] = (
    # 000 Core & Architecture
    ADC12Entry("010", "0", "Seal & Invariant", 117, "u", "υ", "◆", "A-2", "Immutable blackboard seal or SHA-256 receipt", "#ac82ff", False),
    ADC12Entry("020", "0", "Attribution & License", 211, "Š", "©", "⑩", "A-3", "Clean-room provenance & Digital Research homage", "#ac82ff", False),
    # 100 Ideas & Brain-Blasts
    ADC12Entry("110", "1", "Open Question / Pin", 73, "I", "I", "☆", "A-2", "Open question to revisit or explore together", "#f8cc30", False),
    ADC12Entry("120", "1", "Inference / Link", 92, "\\", "∴", "✳", "A-2", "Cross-domain insight connecting two threads", "#f8cc30", False),
    # 200 Decisions & Approvals
    ADC12Entry("210", "2", "Heavy Sign-Off", 52, "4", "4", "✔", "A-2", "Final user sign-off on commit, push, or release", "#52e5a8", False),
    ADC12Entry("220", "2", "Love / Keep Forever", 95, "_", "_", "✿", "A-2", "Aesthetic favorite to preserve as studio standard", "#d93b96", False),
    # 300 Science, Math & Proof
    ADC12Entry("310", "3", "Kloster Threshold A_tau", 116, "t", "τ", "▼", "A-2", "Complexity metric, routing tier, stem-layering", "#4f8ef7", False),
    ADC12Entry("320", "3", "Oncology / Preclinical", 57, "9", "9", "✚", "A-2", "DMG/GBM molecular hypotheses (non-clinical R&D)", "#4f8ef7", False),
    ADC12Entry("330", "3", "Universal Proof", 34, '"', "∀", "✂", "A-2", "Universal invariant or Z3 formal proof check", "#4f8ef7", False),
    ADC12Entry("340", "3", "Gradient / Dynamics", 209, "Ó", "∇", "❽", "A-3", "Differential dynamics, PDEs, energy landscapes", "#4f8ef7", False),
    ADC12Entry("350", "3", "Partial Derivative", 182, "À", "∂", "❶", "A-3", "Sensitivity analysis, perturbation, local gradient", "#4f8ef7", False),
    # 400 Art, Visuals & Decks
    ADC12Entry("410", "4", "Vector Rosette / Curve", 89, "Y", "Ψ", "✹", "A-2", "Parametric geometry, Artline splines, spirographs", "#ff85b3", False),
    ADC12Entry("420", "4", "Delta / Visual Polish", 68, "D", "Δ", "✤", "A-2", "Layout fix, visual inspection diff, alignment pass", "#ff85b3", False),
    # 500 Code & Clean-Room Build
    ADC12Entry("510", "5", "Trim / Refactor", 33, "!", "!", "✂", "A-2", "Cut boilerplate, simplify code, clean refactor", "#5ce1e6", False),
    ADC12Entry("520", "5", "Existential Witness", 36, "$", "∃", "✂", "A-2", "Minimal working proof-of-concept / witness test", "#5ce1e6", False),
    # 600 Verify, Test & Freeze
    ADC12Entry("610", "6", "Exact Identity Match", 186, "‡", "≡", "❺", "A-3", "Bit-exact hash match, deterministic replay PASS", "#6cb4ff", False),
    ADC12Entry("620", "6", "Root Verification", 214, "Ú", "√", "↔", "A-3", "Square-root / structural integrity check passed", "#6cb4ff", False),
    # 700 Drafts & Bookmarks
    ADC12Entry("710", "7", "Inbox / Handoff Note", 41, ")", ")", "✉", "A-2", "Message, summary, or artifact queued for review", "#7be0d6", False),
    ADC12Entry("720", "7", "Step Sequence Badge", 172, "›", "←", "①", "A-3", "Ordered numbered step in multi-stage workflow", "#7be0d6", False),
    # 800 Actions & Next Steps
    ADC12Entry("810", "8", "Ship / Launch / Deploy", 40, "(", "(", "✈", "A-2", "Package, deploy to Pixel 7, or launch service", "#ffb347", False),
    ADC12Entry("820", "8", "Pipeline Arrow", 212, "š", "™", "➔", "A-3", "Forward execution handoff to next stage or tool", "#ffb347", False),
    ADC12Entry("830", "8", "Logical Implication", 222, "Þ", "⇒", "➜", "A-3", "If-then trigger or automated downstream consequence", "#ffb347", False),
    # 900 Priority & Favorites
    ADC12Entry("910", "9", "Diamond Anchor", 70, "F", "Φ", "✦", "A-2", "Golden-ratio or flagship deliverable milestone", "#f35670", False),
    # X00 Guards, Stops & Cuts
    ADC12Entry("X10", "X", "Mismatch / Inequality", 185, "§", "≠", "❹", "A-3", "Boundary reminder (e.g. measurement != evidence)", "#e8687a", False),
    # E00 Play, Physics & Freeform
    ADC12Entry("E10", "E", "Unbounded Explore", 165, "Ñ", "∞", "❦", "A-3", "Open-ended sandbox play with zero deadlines", "#88f0b8", False),
)

ADC12_CATALOG: tuple[ADC12Entry, ...] = ADC12_MAJOR_CLASSES + ADC12_SUBCLASSES

_BY_KEY: dict[str, ADC12Entry] = {}
for _entry in ADC12_CATALOG:
    _BY_KEY[_entry.call_code] = _entry
    _BY_KEY[f"{_entry.call_code}_12"] = _entry
    _BY_KEY[f"{_entry.call_code}₁₂"] = _entry
    _BY_KEY[str(_entry.decimal_code)] = _entry
    _BY_KEY[_entry.international] = _entry
    _BY_KEY[_entry.symbol] = _entry
    _BY_KEY[_entry.wombat] = _entry
    if _entry.is_major:
        _BY_KEY[_entry.major_digit] = _entry
        _BY_KEY[f"/{_entry.call_code}"] = _entry


def resolve_adc12(query: str | int) -> ADC12Entry:
    """Resolve an ADC-12 tag by Base-12 call code ('100', 'X00'), Decimal (90), Int ('Z'), Symbol ('Σ'), Wombat ('✺'), or name."""
    raw = str(query).strip()
    if raw in _BY_KEY:
        return _BY_KEY[raw]
    upper = raw.upper().lstrip("/@")
    if upper in _BY_KEY:
        return _BY_KEY[upper]
    low = raw.lower()
    for entry in ADC12_CATALOG:
        if entry.class_name.lower() == low or low in entry.class_name.lower():
            return entry
    raise ValueError(f"Unknown Artline Duodecimal (ADC-12) tag: {query!r}")


# ---------------------------------------------------------------------------
# 3. Conversation Shorthand Highlighter (Glass-Box Stamped Index)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HighlightedExcerpt:
    excerpt_id: str
    speaker: str
    quote: str
    call_code: str
    decimal_code: int
    artline_dozenal: str
    international: str
    symbol: str
    wombat: str
    class_name: str
    compact_shorthand: str
    four_column_stamp: str
    receipt_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArtlineDuodecimalIndexer:
    """Indexes highlighted chat replies & ideas using 4-column Artline Duodecimal call numbers."""

    def __init__(self) -> None:
        self._items: list[HighlightedExcerpt] = []

    def highlight(self, quote: str, tag: str | int, *, speaker: str = "user") -> HighlightedExcerpt:
        clean_quote = (quote or "").strip()
        if not clean_quote:
            raise ValueError("Highlighted quote must not be empty.")
        entry = resolve_adc12(tag)
        eid = f"adc12_{len(self._items) + 1:03d}"
        payload = {
            "excerpt_id": eid,
            "speaker": speaker,
            "quote": clean_quote,
            "call_code": entry.call_code,
            "decimal_code": entry.decimal_code,
            "international": entry.international,
            "symbol": entry.symbol,
            "wombat": entry.wombat,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        rec = HighlightedExcerpt(
            excerpt_id=eid,
            speaker=speaker,
            quote=clean_quote,
            call_code=entry.call_code,
            decimal_code=entry.decimal_code,
            artline_dozenal=entry.artline_dozenal,
            international=entry.international,
            symbol=entry.symbol,
            wombat=entry.wombat,
            class_name=entry.class_name,
            compact_shorthand=f"{entry.call_badge} {clean_quote}",
            four_column_stamp=entry.four_column_stamp,
            receipt_sha256=digest,
        )
        self._items.append(rec)
        return rec

    def filter_by_major(self, major_digit: str) -> list[HighlightedExcerpt]:
        key = str(major_digit).strip().upper()[:1]
        return [item for item in self._items if item.call_code.startswith(key)]

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": ADC12_CONTRACT,
            "count": len(self._items),
            "page_a2_end_dozenal": to_duodecimal(143),
            "page_a3_start_dozenal": to_duodecimal(144),
            "excerpts": [item.to_dict() for item in self._items],
            "constitutional": dict(CONSTITUTIONAL_FLAGS),
        }


# ---------------------------------------------------------------------------
# 4. Artline 2.0 Vector Library Card Plate (.SVG / .PNG / .GEM)
# ---------------------------------------------------------------------------

def build_adc12_reference_plate() -> tuple[ArtlineDocument, dict[str, Any]]:
    """Build a crisp Artline 2.0 4-column Duodecimal Library Card Plate."""
    doc = ArtlineDocument()
    doc.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#0b0d18", stroke="#0b0d18", width=1)
    doc.add_element("rectangle", bounds=[20, 16, 980, 684], fill="#101528", stroke="#5ce1e6", width=1.8)
    doc.add_element(
        "text",
        position=[40, 44],
        text="ARTLINE DUODECIMAL CLASSIFICATION (ADC-12) · BASE-12 GEM LIBRARY SHORTHAND",
        size=16.5,
        stroke="#f8cc30",
        width=1,
    )
    doc.add_element(
        "text",
        position=[40, 68],
        text="4 Authentic 1990 Artline Columns: Decimal/Base-12 | International | Symbol | Wombats   (p.A-2 ends 143=EE_12 · p.A-3 starts 144=100_12)",
        size=10.5,
        stroke="#94a3c8",
        width=1,
    )

    # 2x6 card grid for the 12 Duodecimal Major Classes
    for idx, entry in enumerate(ADC12_MAJOR_CLASSES):
        col = idx // 6
        row = idx % 6
        x0 = 36 + col * 474
        y0 = 88 + row * 94
        doc.add_element("rectangle", bounds=[x0, y0, x0 + 454, y0 + 82], fill="#151d36", stroke=entry.color_hex, width=1.6)
        doc.add_element("rectangle", bounds=[x0 + 10, y0 + 10, x0 + 96, y0 + 72], fill="#0d1224", stroke=entry.color_hex, width=1.2)
        doc.add_element("text", position=[x0 + 22, y0 + 38], text=f"{entry.call_code}", size=17, stroke=entry.color_hex, width=1)
        doc.add_element("text", position=[x0 + 24, y0 + 60], text=f"Dec {entry.decimal_code:3d}", size=9.5, stroke="#94a3c8", width=1)
        doc.add_element("text", position=[x0 + 110, y0 + 30], text=entry.class_name, size=13.5, stroke="#f4ebd6", width=1)
        doc.add_element(
            "text",
            position=[x0 + 110, y0 + 50],
            text=f"Base-12: {entry.artline_dozenal}_12  |  Int: '{entry.international}'  |  Page {entry.page_ref}",
            size=10.2,
            stroke=entry.color_hex,
            width=1,
        )
        doc.add_element("text", position=[x0 + 110, y0 + 69], text=entry.shorthand_use[:54], size=9.6, stroke="#94a3c8", width=1)

    doc.add_element(
        "text",
        position=[40, 668],
        text="Zero occultism · 100% Digital Research GEM / Artline (Aug 1990, pp. A-2/A-3) · Clean-Room Base-12 Library Science · ext=0",
        size=10.2,
        stroke="#52e5a8",
        width=1,
    )
    return doc, {
        "major_classes": len(ADC12_MAJOR_CLASSES),
        "subclasses": len(ADC12_SUBCLASSES),
        "total_entries": len(ADC12_CATALOG),
    }


# ---------------------------------------------------------------------------
# 5. Offline Interactive HTML5 Artline Duodecimal Card Catalog & Tagger
# ---------------------------------------------------------------------------

def build_interactive_adc12_catalog_html_str() -> str:
    """Return HTML string for the 100% offline Artline Duodecimal (Base-12) Shorthand Catalog."""
    catalog_json = json.dumps([e.to_dict() for e in ADC12_CATALOG], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Artline Duodecimal Classification (ADC-12) — GEM 4-Column Shorthand Catalog</title>
<style>
  * {{ box-sizing: border-box; font-family: "DejaVu Sans", system-ui, sans-serif; }}
  body {{ margin: 0; background: #0b0d18; color: #f0f4fc; min-height: 100vh; display: flex; flex-direction: column; }}
  header {{ background: #141a2e; border-bottom: 2px solid #f8cc30; padding: 14px 22px; display: flex; justify-content: space-between; align-items: center; gap: 14px; flex-wrap: wrap; }}
  header h1 {{ margin: 0; font-size: 18px; color: #5ce1e6; }}
  header .sub {{ font-size: 12px; color: #94a3c8; margin-top: 3px; }}
  .navlinks {{ display: flex; gap: 7px; align-items: center; flex-wrap: wrap; }}
  .navlinks a {{ text-decoration: none; font-size: 11.5px; padding: 4px 9px; border-radius: 6px; border: 1px solid #3c4d7a; color: #cbd5e1; background: #18213d; font-weight: 600; }}
  .navlinks a:hover {{ border-color: #f8cc30; color: #f8cc30; }}
  .pill {{ font-size: 11px; padding: 4px 10px; border-radius: 999px; border: 1px solid #52e5a8; color: #52e5a8; background: #102a24; font-weight: 700; }}
  .layout {{ display: grid; grid-template-columns: 1.45fr 1fr; gap: 16px; padding: 16px 22px; flex: 1; }}
  @media (max-width: 1020px) {{ .layout {{ grid-template-columns: 1fr; }} }}
  .panel {{ background: #12182c; border: 1.5px solid #2b385c; border-radius: 10px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }}
  .panel h2 {{ margin: 0; font-size: 13px; text-transform: uppercase; letter-spacing: 0.7px; color: #f8cc30; }}
  .controls {{ display: flex; gap: 8px; flex-wrap: wrap; }}
  input[type="text"], textarea {{ background: #0d1222; color: #f0f4fc; border: 1.5px solid #354672; border-radius: 7px; padding: 8px 10px; font-size: 13px; width: 100%; }}
  button {{ background: #1b2442; color: #f0f4fc; border: 1.5px solid #3c4f7f; border-radius: 7px; padding: 6px 11px; cursor: pointer; font-weight: 600; font-size: 12px; }}
  button:hover {{ filter: brightness(1.18); }}
  button.active {{ border-color: #f8cc30; color: #f8cc30; background: #292313; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.5px; }}
  th {{ text-align: left; padding: 7px 8px; background: #19223d; color: #5ce1e6; border-bottom: 1.5px solid #32446e; font-size: 11px; text-transform: uppercase; }}
  td {{ padding: 7px 8px; border-bottom: 1px solid #1e2948; vertical-align: middle; }}
  tr.row {{ cursor: pointer; }}
  tr.row:hover {{ background: #1a2442; }}
  tr.row.sel {{ background: #232d52; outline: 1px solid #f8cc30; }}
  .code {{ font-family: "DejaVu Sans Mono", monospace; font-weight: 700; }}
  .glyph {{ font-size: 17px; text-align: center; }}
  .stamp-card {{ background: #0e1324; border-left: 4px solid #5ce1e6; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; }}
  .stamp-meta {{ font-family: "DejaVu Sans Mono", monospace; font-size: 11.5px; color: #f8cc30; margin-bottom: 4px; }}
  .stamp-quote {{ font-size: 13px; color: #f0f4fc; }}
  .converter {{ display: flex; gap: 8px; align-items: center; background: #161f38; padding: 9px 12px; border-radius: 8px; border: 1px solid #2e3e66; font-size: 12.5px; }}
  footer {{ padding: 8px 22px; background: #101424; border-top: 1px solid #263354; font-size: 11px; color: #94a3c8; }}
</style>
</head>
<body>
<header>
  <div>
    <h1>❖ Artline Duodecimal Classification (ADC-12) — 4-Column GEM Shorthand</h1>
    <div class="sub">Digital Research Artline Utilities Guide (Aug 1990, pp. A-2 &amp; A-3) · Page A-2 ends at 143 (EE₁₂) · Page A-3 starts at 144 (100₁₂ = 12²)</div>
  </div>
  <div class="navlinks">
    <a href="/">← Studio</a>
    <a href="/artline">🎨 Artline</a>
    <a href="/physics">✺ Physics Room</a>
    <span class="pill">BASE-12 DEWEY · 0 CLOUD TOKENS</span>
  </div>
</header>

<div class="layout">
  <section class="panel">
    <h2>4-Column Artline Catalog (Decimal/Base-12 · International · Symbol · Wombats)</h2>
    <div class="controls">
      <input id="search" type="text" placeholder="Filter by call code (100, X00), Decimal (90), Int (Z), Symbol (Σ), Wombat (✺), or domain..." oninput="renderTable()" style="flex:1;min-width:220px;" />
      <button id="fAll" class="active" onclick="setFilter('all')">All (37)</button>
      <button id="fMajor" onclick="setFilter('major')">12 Major Classes</button>
      <button id="fSub" onclick="setFilter('sub')">Subdivisions</button>
    </div>
    <div style="overflow:auto;max-height:540px;">
      <table>
        <thead>
          <tr>
            <th>ADC-12</th>
            <th>Decimal / Base-12</th>
            <th>Int</th>
            <th>Symbol</th>
            <th>Wombats</th>
            <th>Class &amp; Shorthand Meaning</th>
          </tr>
        </thead>
        <tbody id="tbody"></tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>Live Reply Highlighter &amp; Chat Shorthand Stamper</h2>
    <div class="converter">
      <span style="color:#5ce1e6;font-weight:700;">Base-12 Check:</span>
      <input id="decIn" type="text" value="144" style="width:74px;text-align:center;" oninput="updateConv()" />
      <span id="dozOut" class="code" style="color:#52e5a8;">= 100₁₂ (Page A-3 start!)</span>
    </div>
    <div>
      <div style="font-size:11.5px;color:#94a3c8;margin-bottom:5px;">Type or paste a message excerpt, select any ADC-12 row on the left, then stamp it:</div>
      <textarea id="quoteInput" rows="3">ours would be a duodecimal (base-12) classification system based on GEM and Artline</textarea>
    </div>
    <div class="controls">
      <button style="border-color:#52e5a8;color:#52e5a8;" onclick="stampExcerpt()">✓ Stamp Highlight</button>
      <button style="border-color:#5ce1e6;color:#5ce1e6;" onclick="copyAll()">❏ Copy Chat Shorthand</button>
      <button style="border-color:#f35670;color:#f35670;" onclick="clearStamps()">✕ Clear Log</button>
      <span id="copyMsg" style="font-size:11.5px;color:#52e5a8;align-self:center;"></span>
    </div>
    <h2>Stamped Highlights (Glass-Box Shorthand Log)</h2>
    <div id="stamps" style="overflow:auto;max-height:330px;"></div>
  </section>
</div>

<footer>Concept by Nicholas Michael Kloster · Digital Research Artline 2.0 (Aug 1990, pp. A-2/A-3) · 0 Cloud Tokens · external_actions=0 · sentience_claimed=False · clinical_action_authorized=False</footer>

<script>
const CATALOG = {catalog_json};
let filterMode = 'all';
let selectedCode = '100';
const stamps = [
  {{ code: '100', dec: 90, doz: '76', intl: 'Z', sym: 'Z', wom: '✺', col: '#f8cc30', name: 'Ideas & Brain-Blasts', quote: 'Ours would be a duodecimal (base-12) classification system.' }},
  {{ code: '000', dec: 118, doz: '9X', intl: 'v', sym: 'ϖ', wom: '❖', col: '#ac82ff', name: 'Core & Architecture', quote: 'Four Artline columns: Decimal, International, Symbol, Wombats.' }},
  {{ code: 'X00', dec: 53, doz: '45', intl: '5', sym: '5', wom: '✕', col: '#e8687a', name: 'Guards, Stops & Cuts', quote: 'No weird symbology or occult stuff — pure GEM & Artline.' }},
];

function toDozenal(n) {{
  if (isNaN(n) || n < 0) return '?';
  const d = '0123456789XE';
  if (n === 0) return '0';
  let s = '';
  while (n > 0) {{ s = d[n % 12] + s; n = Math.floor(n / 12); }}
  return s;
}}
function updateConv() {{
  const v = parseInt(document.getElementById('decIn').value, 10);
  const el = document.getElementById('dozOut');
  if (isNaN(v) || v < 0) {{ el.textContent = 'Enter non-negative integer'; return; }}
  const note = v === 143 ? ' (End of Page A-2!)' : (v === 144 ? ' (Page A-3 start = 12²!)' : '');
  el.textContent = '= ' + toDozenal(v) + '₁₂' + note;
}}
function setFilter(m) {{
  filterMode = m;
  document.getElementById('fAll').classList.toggle('active', m==='all');
  document.getElementById('fMajor').classList.toggle('active', m==='major');
  document.getElementById('fSub').classList.toggle('active', m==='sub');
  renderTable();
}}
function renderTable() {{
  const q = document.getElementById('search').value.trim().toLowerCase();
  const rows = CATALOG.filter(e => {{
    if (filterMode === 'major' && !e.is_major) return false;
    if (filterMode === 'sub' && e.is_major) return false;
    if (!q) return true;
    return [e.call_code, String(e.decimal_code), e.artline_dozenal, e.international, e.symbol, e.wombat, e.class_name, e.shorthand_use]
      .some(x => String(x).toLowerCase().includes(q));
  }});
  document.getElementById('tbody').innerHTML = rows.map(e => `
    <tr class="row ${{e.call_code===selectedCode?'sel':''}}" onclick="selectedCode='${{e.call_code}}';renderTable();">
      <td class="code" style="color:${{e.color_hex}}">${{e.call_code}}₁₂</td>
      <td class="code">${{e.decimal_code}} <span style="color:#94a3c8">(${{e.artline_dozenal}}₁₂ · ${{e.page_ref}})</span></td>
      <td class="code" style="text-align:center">${{e.international}}</td>
      <td class="glyph" style="color:#5ce1e6">${{e.symbol}}</td>
      <td class="glyph" style="color:${{e.color_hex}}">${{e.wombat}}</td>
      <td><b>${{e.class_name}}</b><div style="font-size:11px;color:#94a3c8">${{e.shorthand_use}}</div></td>
    </tr>`).join('');
}}
function renderStamps() {{
  document.getElementById('stamps').innerHTML = stamps.map(s => `
    <div class="stamp-card" style="border-left-color:${{s.col}}">
      <div class="stamp-meta">[${{s.code}}₁₂ · Dec ${{s.dec}} (${{s.doz}}₁₂) · Int ${{s.intl}} · Sym ${{s.sym}} · Wom ${{s.wom}}] — ${{s.name}}</div>
      <div class="stamp-quote">“${{s.quote}}”</div>
    </div>`).join('');
}}
function stampExcerpt() {{
  const q = document.getElementById('quoteInput').value.trim();
  if (!q) return;
  const e = CATALOG.find(x => x.call_code === selectedCode) || CATALOG[0];
  stamps.unshift({{ code: e.call_code, dec: e.decimal_code, doz: e.artline_dozenal, intl: e.international, sym: e.symbol, wom: e.wombat, col: e.color_hex, name: e.class_name, quote: q }});
  renderStamps();
}}
function clearStamps() {{ stamps.length = 0; renderStamps(); }}
function copyAll() {{
  const text = stamps.map(s => `[${{s.code}}₁₂ · ${{s.intl}} · ${{s.sym}} · ${{s.wom}}] "${{s.quote}}"`).join('\\n');
  navigator.clipboard?.writeText(text).then(() => {{
    document.getElementById('copyMsg').textContent = 'Copied to clipboard!';
    setTimeout(() => document.getElementById('copyMsg').textContent = '', 2000);
  }});
}}
renderTable();
renderStamps();
updateConv();
</script>
</body>
</html>
"""


def render_adc12_catalog_html() -> bytes:
    """HTTP route renderer for /duodecimal on the live Zoe-ELIZA Web Studio."""
    return build_interactive_adc12_catalog_html_str().encode("utf-8")


def write_interactive_adc12_catalog_html(out_html: str | Path) -> Path:
    """Write a 100% offline HTML5 Artline Duodecimal (Base-12) Shorthand Catalog & Reply Highlighter."""
    target = Path(out_html)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_interactive_adc12_catalog_html_str(), encoding="utf-8")
    return target


__all__ = [
    "ADC12_CATALOG",
    "ADC12_CONTRACT",
    "ADC12_MAJOR_CLASSES",
    "ADC12_SUBCLASSES",
    "CONSTITUTIONAL_FLAGS",
    "DOZENAL_DIGITS",
    "ADC12Entry",
    "ArtlineDuodecimalIndexer",
    "HighlightedExcerpt",
    "build_adc12_reference_plate",
    "build_interactive_adc12_catalog_html_str",
    "from_duodecimal",
    "render_adc12_catalog_html",
    "resolve_adc12",
    "to_duodecimal",
    "write_interactive_adc12_catalog_html",
]
