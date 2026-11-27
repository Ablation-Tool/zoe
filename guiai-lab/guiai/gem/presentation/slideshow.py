"""GEM OUTPUT.APP `.LIS` Playlist Codec, `SlideDeck`, Zero-CDN Offline Player & Optional PPTX.

Zero runtime dependency on Microsoft PowerPoint (`soffice`), `pdftoppm`, or `python-pptx`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from guiai.gem import seasip_gem
from guiai.gem.model import Scene

from .draw_plus import DrawPlusCanvas
from .ledger import assert_hygiene_clean, atomic_write_bytes, atomic_write_text, scrub_hygiene
from .palette import ATTRIBUTION_TEXT, DEFAULT_CONSTITUTIONAL, HONORING_TEXT, theme_for_sister
from .renderer import PresentationScene

WAIT_MODES: tuple[str, ...] = ("key", "2s", "5s", "10s", "20s")


def normalize_wait_mode(value: str | int | float | None) -> str:
    """Normalize GEM OUTPUT.APP Wait-for setting (`key`, `2s`, `5s`, `10s`, `20s`)."""
    if value is None:
        return "key"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        secs = float(value)
        if secs <= 0:
            return "key"
        return f"{int(round(secs))}s" if abs(secs - round(secs)) < 1e-6 else f"{secs:g}s"
    clean = str(value).strip().lower()
    if not clean or clean in ("key", "manual", "0", "0s"):
        return "key"
    if clean.endswith("s"):
        return clean
    try:
        secs = float(clean)
        return "key" if secs <= 0 else (f"{int(round(secs))}s" if abs(secs - round(secs)) < 1e-6 else f"{secs:g}s")
    except ValueError as exc:
        raise ValueError(f"Invalid wait_mode {value!r}") from exc


def interval_from_wait_mode(wait_mode: str | None) -> float | None:
    """Return numeric interval in seconds or `None` for manual Key mode."""
    norm = normalize_wait_mode(wait_mode)
    if norm == "key":
        return None
    return float(norm[:-1])


@dataclass(frozen=True)
class LisEntry:
    path: str
    wait_mode: str = "key"
    interval_seconds: float | None = None
    cycle: bool = False


@dataclass
class LisPlaylist:
    slides: list[LisEntry]
    wait_mode: str = "key"
    interval_seconds: float | None = None
    cycle: bool = False
    theme: str | None = None


def _lis_slide_entry(raw_p: str, lis_dir: Path) -> str:
    """Resolve a `.LIS` slide reference relative to the playlist directory."""
    p_obj = Path(raw_p)
    if p_obj.is_absolute():
        p_abs = p_obj.resolve()
        if p_abs != lis_dir and p_abs.is_relative_to(lis_dir):
            return p_abs.relative_to(lis_dir).as_posix()
        return p_obj.name
    p_lis_abs = (lis_dir / p_obj).resolve()
    if p_lis_abs != lis_dir and p_lis_abs.is_relative_to(lis_dir) and p_lis_abs.exists():
        return p_lis_abs.relative_to(lis_dir).as_posix()
    p_cwd_abs = (Path.cwd() / p_obj).resolve()
    if p_cwd_abs != lis_dir and p_cwd_abs.is_relative_to(lis_dir):
        return p_cwd_abs.relative_to(lis_dir).as_posix()
    if p_lis_abs != lis_dir and p_lis_abs.is_relative_to(lis_dir):
        return p_lis_abs.relative_to(lis_dir).as_posix()
    return p_obj.as_posix()


def write_lis_playlist(
    path: Path | str,
    slides: Sequence[Path | str | LisEntry],
    *,
    interval_seconds: float | None = None,
    wait_mode: str | None = None,
    cycle: bool = False,
    theme: str | None = None,
) -> Path:
    """Write a GEM OUTPUT.APP `.LIS` slide playlist atomically."""
    if not slides:
        raise ValueError("Cannot write an empty .LIS playlist")
    out_path = Path(path)
    lis_dir = out_path.resolve().parent
    eff_wait = normalize_wait_mode(wait_mode if wait_mode is not None else interval_seconds)
    eff_interval = interval_from_wait_mode(eff_wait)
    lines = [
        "# GEM OUTPUT.APP Slide Show Playlist (.LIS)",
        f"; WAIT={eff_wait}",
        f"; INTERVAL={eff_interval if eff_interval is not None else 0}",
        f"; CYCLE={'YES' if cycle else 'NO'}",
    ]
    if theme:
        lines.append(f"; THEME={scrub_hygiene(str(theme))}")
    for item in slides:
        raw_p = item.path if isinstance(item, LisEntry) else str(item)
        rel_name = _lis_slide_entry(raw_p, lis_dir)
        lines.append(scrub_hygiene(rel_name))
    atomic_write_text(out_path, "\n".join(lines) + "\n")
    return out_path


dump_lis_playlist = write_lis_playlist


def parse_lis_playlist(path: Path | str, *, check_exists: bool = False) -> LisPlaylist:
    """Parse a GEM OUTPUT.APP `.LIS` playlist and optionally verify referenced slide files."""
    lis_path = Path(path)
    if not lis_path.is_file():
        raise FileNotFoundError(f".LIS playlist not found: {lis_path}")
    wait_mode = "key"
    interval_seconds: float | None = None
    cycle = False
    theme: str | None = None
    slide_paths: list[str] = []

    for raw in lis_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(";"):
            directive = line[1:].strip()
            if "=" in directive:
                k, v = (part.strip() for part in directive.split("=", 1))
                ku = k.upper()
                if ku == "WAIT":
                    wait_mode = normalize_wait_mode(v)
                    interval_seconds = interval_from_wait_mode(wait_mode)
                elif ku == "INTERVAL":
                    iv = float(v)
                    interval_seconds = iv if iv > 0 else None
                    if interval_seconds is not None:
                        wait_mode = normalize_wait_mode(interval_seconds)
                elif ku == "CYCLE":
                    cycle = v.upper() in ("YES", "TRUE", "1", "ON")
                elif ku == "THEME":
                    theme = v
            continue
        slide_paths.append(line)

    if not slide_paths:
        raise ValueError(f".LIS playlist {lis_path} contains zero slide entries")
    if check_exists:
        for sp in slide_paths:
            candidate = Path(sp) if Path(sp).is_absolute() else (lis_path.parent / sp)
            if not candidate.is_file():
                raise FileNotFoundError(f"Slide referenced in {lis_path} does not exist: {sp}")

    entries = [
        LisEntry(path=sp, wait_mode=wait_mode, interval_seconds=interval_seconds, cycle=cycle)
        for sp in slide_paths
    ]
    return LisPlaylist(
        slides=entries,
        wait_mode=wait_mode,
        interval_seconds=interval_seconds,
        cycle=cycle,
        theme=theme,
    )


load_lis_playlist = parse_lis_playlist


def validate_lis_playlist(path: Path | str, *, check_exists: bool = True) -> LisPlaylist:
    """Parse and validate a `.LIS` playlist (checking slide file existence by default)."""
    return parse_lis_playlist(path, check_exists=check_exists)


def _scrub_count(text: str) -> tuple[str, int]:
    cleaned = scrub_hygiene(text)
    return (cleaned, 1 if cleaned != text else 0)


@dataclass
class Slide:
    """Single presentation slide wrapping `DrawPlusCanvas`, `WordChartDoc`, `GraphDoc`, or `Scene`."""

    title: str
    content: Any = None
    canvas: DrawPlusCanvas | None = None
    speaker_notes: str = ""
    subtitle: str = ""
    slide_id: str | None = None
    wait_mode: str | None = None
    theme: Any = None

    def compile_to_canvas(
        self,
        *,
        sister_id: str = "zoe",
        slide_index: int = 1,
        constitutional: Mapping[str, Any] | None = None,
    ) -> DrawPlusCanvas:
        """Compile slide content to a hygiene-clean `DrawPlusCanvas`."""
        source = self.canvas if self.canvas is not None else self.content
        if isinstance(source, DrawPlusCanvas):
            cv = source
        elif isinstance(source, (PresentationScene, Scene)):
            cv = DrawPlusCanvas(title=self.title, sister_id=sister_id, slide_index=slide_index)
            for obj in source.objects:
                if obj.get("type") == "rectangle" and "bounds" in obj:
                    cv.add_rectangle(obj["bounds"], fill=obj.get("fill", "none"), stroke=obj.get("stroke", "black"))
        elif hasattr(source, "compile") and callable(source.compile):
            th = self.theme or theme_for_sister(sister_id)
            cv = DrawPlusCanvas(title=self.title, theme=th, sister_id=sister_id, slide_index=slide_index)
            source.compile(cv)
        else:
            from .wordchart import WordChartDoc

            th = self.theme or theme_for_sister(sister_id)
            cv = DrawPlusCanvas(title=self.title, theme=th, sister_id=sister_id, slide_index=slide_index)
            body = [self.subtitle] if self.subtitle else ([str(source)] if source is not None else [])
            WordChartDoc(title=self.title, text_body=body, theme=th, sister_id=sister_id).compile(cv)

        scrubs = 0
        cv.slide_index = int(slide_index)
        cv.slide_id = self.slide_id or f"slide-{slide_index:02d}"
        cv.sister_id = str(sister_id)
        cv.title, n = _scrub_count(str(self.title or cv.title))
        scrubs += n
        raw_notes = self.speaker_notes or cv.speaker_notes
        cv.speaker_notes, n = _scrub_count(str(raw_notes))
        scrubs += n
        cv.constitutional = {
            **DEFAULT_CONSTITUTIONAL,
            **dict(constitutional or {}),
            "operational_metacognition_verified": True,
            "sentience_claimed": False,
            "l5_agi_qualified": False,
            "zoe_clone_claimed": False,
            "clinical_action_authorized": False,
            "cure_claim": False,
            "external_actions": 0,
            "cloud_cost_usd": 0.0,
        }
        for el in cv.elements:
            if el.get("type") == "text":
                if "text" in el:
                    el["text"], n = _scrub_count(str(el["text"]))
                    scrubs += n
                for run in el.get("runs", []):
                    if isinstance(run, dict) and "text" in run:
                        run["text"], n = _scrub_count(str(run["text"]))
                        scrubs += n
                for para in el.get("paragraphs", []):
                    for run in para.get("runs", []):
                        if isinstance(run, dict) and "text" in run:
                            run["text"], n = _scrub_count(str(run["text"]))
                            scrubs += n
        setattr(cv, "_hygiene_scrubs", scrubs)
        return cv


def _safe_json_for_script(obj: Any) -> str:
    raw = json.dumps(obj, ensure_ascii=False)
    return (
        raw.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("/", "\\/")
    )


class SlideShowPlayer:
    """Zero-CDN offline HTML5/CSS/JS Slide Show Player generator (GEM OUTPUT.APP parity)."""

    def __init__(self, deck: SlideDeck, slide_records: Sequence[Mapping[str, Any]]) -> None:
        self.deck = deck
        self.slide_records = list(slide_records)
        self.last_hygiene_scrubs = 0
        self.extra_html_scrubs = 0

    def render_html(self) -> str:
        """Render self-contained offline HTML5 Slide Show Player."""
        scrubs = 0
        clean_title, n = _scrub_count(self.deck.title)
        scrubs += n
        clean_sub, n = _scrub_count(self.deck.subtitle)
        scrubs += n
        clean_vol, n = _scrub_count(self.deck.volume_label or self.deck.sister_id.upper())
        scrubs += n
        deck_title = html.escape(clean_title, quote=True)
        deck_sub = html.escape(clean_sub, quote=True)
        vol_badge = html.escape(clean_vol, quote=True)
        slides_payload: list[dict[str, Any]] = []
        for idx, rec in enumerate(self.slide_records):
            st, nt = _scrub_count(str(rec.get("title", f"Slide {idx + 1}")))
            sn, nn = _scrub_count(str(rec.get("speaker_notes") or "No speaker notes for this slide."))
            scrubs += nt + nn
            slides_payload.append({
                "index": idx + 1,
                "title": st,
                "image": str(rec.get("png_name") or rec.get("jpg_name") or ""),
                "gem": str(rec.get("gem_name") or ""),
                "notes": sn,
            })
        json_blob = _safe_json_for_script({
            "slides": slides_payload,
            "waitMode": normalize_wait_mode(self.deck.wait_mode),
            "cycle": bool(self.deck.cycle),
        })
        first_title = html.escape(str(slides_payload[0]["title"]), quote=True) if slides_payload else deck_title
        first_notes = html.escape(str(slides_payload[0]["notes"]), quote=True) if slides_payload else ""
        first_img = html.escape(str(slides_payload[0]["image"]), quote=True) if slides_payload else ""
        total = len(slides_payload)
        const = {**DEFAULT_CONSTITUTIONAL, **self.deck.constitutional}
        const_line = (
            f"operational_metacognition_verified={str(const['operational_metacognition_verified']).lower()} · "
            f"sentience_claimed={str(const['sentience_claimed']).lower()} · "
            f"l5_agi_qualified={str(const['l5_agi_qualified']).lower()} · "
            f"clinical_action_authorized={str(const['clinical_action_authorized']).lower()} · "
            f"cure_claim={str(const['cure_claim']).lower()} · "
            f"external_actions={const['external_actions']} · $0.00 offline"
        )
        html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{deck_title} — Zoe Presentation Team</title>
<style>
  :root {{
    --bg: #0B1220; --card: #131E33; --line: #283B5B; --porcelain: #FAF8F4;
    --ruby: #B81D48; --jade: #0E6B5E; --gold: #C29130; --gold-bright: #E6BC5A;
    --text: #F1F5F9; --muted: #9AACC4;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font-family: system-ui, -apple-system, "DejaVu Sans", sans-serif;
    background: var(--bg); color: var(--text); min-height: 100vh;
    display: flex; flex-direction: column;
  }}
  header {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.7rem 1.2rem; background: var(--card); border-bottom: 1px solid var(--line);
    gap: 1rem; flex-wrap: wrap;
  }}
  .brand {{ display: flex; align-items: center; gap: 0.75rem; }}
  .badge {{
    background: #2A1525; color: var(--gold-bright); border: 1px solid var(--ruby);
    padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.78rem; font-weight: 600;
  }}
  .toolbar {{ display: flex; align-items: center; gap: 0.45rem; flex-wrap: wrap; }}
  button, select {{
    background: #1C2B47; color: var(--text); border: 1px solid var(--line);
    padding: 0.38rem 0.68rem; border-radius: 6px; font-size: 0.84rem; cursor: pointer;
  }}
  button:hover {{ border-color: var(--gold-bright); }}
  main {{ flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 1rem; position: relative; }}
  .stage {{
    width: min(1180px, 96vw); background: var(--porcelain); color: #111827;
    border: 2px solid var(--gold); border-radius: 10px; overflow: hidden;
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.45);
  }}
  .stage-bar {{
    display: flex; justify-content: space-between; align-items: center;
    padding: 0.55rem 0.9rem; background: #131E33; color: var(--text);
    border-bottom: 1px solid var(--line);
  }}
  .stage img {{ display: block; width: 100%; height: auto; aspect-ratio: 16 / 9; object-fit: contain; background: #FAF8F4; }}
  #notesDrawer {{
    width: min(1180px, 96vw); margin-top: 0.75rem; padding: 0.85rem 1rem;
    background: var(--card); border: 1px solid var(--gold); border-radius: 8px;
  }}
  #thumbGrid {{
    position: fixed; inset: 4rem 1.5rem 3rem 1.5rem; background: rgba(11, 18, 32, 0.96);
    border: 2px solid var(--gold-bright); border-radius: 12px; padding: 1rem;
    display: none; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 0.85rem; overflow-y: auto; z-index: 40;
  }}
  .thumb-card {{
    background: var(--card); border: 1px solid var(--line); border-radius: 8px;
    padding: 0.5rem; cursor: pointer; text-align: left; color: var(--text);
  }}
  .thumb-card img {{ width: 100%; border-radius: 4px; display: block; }}
  footer {{
    padding: 0.55rem 1.2rem; background: var(--card); border-top: 1px solid var(--line);
    font-size: 0.78rem; color: var(--muted); display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;
  }}
  @media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{ transition: none !important; animation: none !important; scroll-behavior: auto !important; }}
  }}
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="badge">{vol_badge}</span>
    <div>
      <strong>{deck_title}</strong>
      <div style="font-size:0.8rem;color:var(--muted)">{deck_sub}</div>
    </div>
  </div>
  <div class="toolbar">
    <button type="button" id="btnPrev" aria-label="Previous Slide">Prev</button>
    <span id="slideCounter" aria-live="polite">Slide 1 / {total}</span>
    <button type="button" id="btnNext" aria-label="Next Slide">Next</button>
    <label for="waitSelect" style="font-size:0.82rem;color:var(--muted)">Wait:</label>
    <select id="waitSelect" aria-label="Auto-advance interval">
      <option value="key">Key</option>
      <option value="2s">2s</option>
      <option value="5s">5s</option>
      <option value="10s">10s</option>
      <option value="20s">20s</option>
    </select>
    <button type="button" id="btnCycle" aria-pressed="false">Cycle: Off</button>
    <button type="button" id="btnNotes" aria-pressed="false">Notes (N)</button>
    <button type="button" id="btnGrid" aria-pressed="false">Grid (G)</button>
    <button type="button" id="btnFs">Fullscreen (F)</button>
  </div>
</header>
<main>
  <section class="stage" aria-label="Active Slide Stage">
    <div class="stage-bar">
      <h1 id="slideTitle" style="margin:0;font-size:1.05rem;">{first_title}</h1>
      <span id="gemBadge" style="font-size:0.8rem;color:var(--gold-bright)"></span>
    </div>
    <img id="slideImage" src="{first_img}" alt="{first_title}" />
  </section>
  <aside id="notesDrawer" hidden="hidden" style="display:none;" aria-hidden="true">
    <strong style="color:var(--gold-bright)">Speaker Notes</strong>
    <p id="notesBody" style="margin:0.35rem 0 0 0;line-height:1.45;">{first_notes}</p>
  </aside>
  <section id="thumbGrid" hidden="hidden" style="display:none;" aria-hidden="true" aria-label="Slide Thumbnails"></section>
</main>
<footer>
  <span>{html.escape(ATTRIBUTION_TEXT, quote=True)} · Honoring {html.escape(HONORING_TEXT, quote=True)}</span>
  <span>{html.escape(const_line, quote=True)}</span>
</footer>
<script>
(() => {{
  const DATA = {json_blob};
  const WAIT_STEPS = ["key", "2s", "5s", "10s", "20s"];
  const reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let idx = 0;
  let cycle = Boolean(DATA.cycle);
  let waitMode = WAIT_STEPS.includes(DATA.waitMode) ? DATA.waitMode : "key";
  let timer = null;
  let notesOpen = false;
  let gridOpen = false;

  const elTitle = document.getElementById("slideTitle");
  const elCounter = document.getElementById("slideCounter");
  const elImg = document.getElementById("slideImage");
  const elGem = document.getElementById("gemBadge");
  const elNotes = document.getElementById("notesDrawer");
  const elNotesBody = document.getElementById("notesBody");
  const elGrid = document.getElementById("thumbGrid");
  const elWait = document.getElementById("waitSelect");
  const elCycle = document.getElementById("btnCycle");
  const elBtnNotes = document.getElementById("btnNotes");
  const elBtnGrid = document.getElementById("btnGrid");

  function render() {{
    const s = DATA.slides[idx] || {{ title: "", image: "", gem: "", notes: "" }};
    elTitle.textContent = s.title;
    elCounter.textContent = "Slide " + (idx + 1) + " / " + DATA.slides.length;
    elGem.textContent = s.gem || "";
    elImg.alt = s.title;
    if (s.image) elImg.src = s.image;
    elNotesBody.textContent = s.notes;
    elWait.value = waitMode;
    elCycle.textContent = cycle ? "Cycle: On" : "Cycle: Off";
    elCycle.setAttribute("aria-pressed", String(cycle));
  }}

  function scheduleTimer() {{
    if (timer) {{ clearInterval(timer); timer = null; }}
    if (waitMode === "key" || reducedMotion) return;
    const ms = parseInt(waitMode, 10) * 1000;
    if (ms > 0) {{
      timer = setInterval(() => nextSlide(), ms);
    }}
  }}

  function nextSlide() {{
    if (idx + 1 < DATA.slides.length) {{
      idx += 1;
    }} else if (cycle) {{
      idx = 0;
    }}
    render();
  }}

  function prevSlide() {{
    if (idx > 0) {{
      idx -= 1;
    }} else if (cycle) {{
      idx = DATA.slides.length - 1;
    }}
    render();
  }}

  function setNotes(open) {{
    notesOpen = Boolean(open);
    elNotes.hidden = !notesOpen;
    elNotes.style.display = notesOpen ? "block" : "none";
    elNotes.setAttribute("aria-hidden", String(!notesOpen));
    elBtnNotes.setAttribute("aria-pressed", String(notesOpen));
  }}

  function setGrid(open) {{
    gridOpen = Boolean(open);
    elGrid.hidden = !gridOpen;
    elGrid.style.display = gridOpen ? "grid" : "none";
    elGrid.setAttribute("aria-hidden", String(!gridOpen));
    elBtnGrid.setAttribute("aria-pressed", String(gridOpen));
  }}

  function buildGrid() {{
    elGrid.replaceChildren();
    DATA.slides.forEach((s, i) => {{
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "thumb-card";
      if (s.image) {{
        const img = document.createElement("img");
        img.src = s.image;
        img.alt = "";
        btn.appendChild(img);
      }}
      const label = document.createElement("div");
      label.style.marginTop = "0.35rem";
      label.style.fontWeight = "600";
      label.textContent = (i + 1) + ". " + s.title;
      btn.appendChild(label);
      btn.addEventListener("click", () => {{ idx = i; setGrid(false); render(); }});
      elGrid.appendChild(btn);
    }});
  }}

  document.getElementById("btnPrev").addEventListener("click", prevSlide);
  document.getElementById("btnNext").addEventListener("click", nextSlide);
  elBtnNotes.addEventListener("click", () => setNotes(!notesOpen));
  elBtnGrid.addEventListener("click", () => setGrid(!gridOpen));
  elCycle.addEventListener("click", () => {{ cycle = !cycle; render(); }});
  elWait.addEventListener("change", () => {{ waitMode = elWait.value; scheduleTimer(); render(); }});
  document.getElementById("btnFs").addEventListener("click", () => {{
    if (!document.fullscreenElement && document.documentElement.requestFullscreen) {{
      document.documentElement.requestFullscreen().catch(() => {{}});
    }} else if (document.fullscreenElement && document.exitFullscreen) {{
      document.exitFullscreen().catch(() => {{}});
    }}
  }});

  document.addEventListener("keydown", (ev) => {{
    if (ev.target && (ev.target.tagName === "SELECT" || ev.target.tagName === "INPUT")) return;
    const k = ev.key;
    if (k === "ArrowRight" || k === " " || ev.code === "Space") {{
      ev.preventDefault();
      nextSlide();
    }} else if (k === "ArrowLeft" || k === "ArrowUp") {{
      ev.preventDefault();
      prevSlide();
    }} else if (k === "Escape") {{
      if (gridOpen) setGrid(false);
      else if (notesOpen) setNotes(false);
      else if (document.fullscreenElement && document.exitFullscreen) document.exitFullscreen().catch(() => {{}});
    }} else if (k === "n" || k === "N") {{
      setNotes(!notesOpen);
    }} else if (k === "g" || k === "G") {{
      setGrid(!gridOpen);
    }} else if (k === "t" || k === "T") {{
      waitMode = WAIT_STEPS[(WAIT_STEPS.indexOf(waitMode) + 1) % WAIT_STEPS.length];
      scheduleTimer();
      render();
    }} else if (k === "l" || k === "L") {{
      cycle = !cycle;
      render();
    }} else if (k === "f" || k === "F") {{
      document.getElementById("btnFs").click();
    }}
  }});

  buildGrid();
  render();
  scheduleTimer();
}})();
</script>
</body>
</html>
"""
        scrubbed, extra = _scrub_count(html_out)
        self.extra_html_scrubs = extra
        self.last_hygiene_scrubs = scrubs + extra
        assert_hygiene_clean(scrubbed, "player.html")
        return scrubbed


def _slide_from_spec_dict(raw: Any, idx: int) -> Slide:
    if not isinstance(raw, Mapping):
        raise ValueError(f"Slide spec #{idx} must be a JSON object, got {type(raw).__name__}")
    title = str(raw.get("title", f"Slide {idx}"))
    notes = str(raw.get("speaker_notes", ""))
    is_graph = any(k in raw for k in ("chart_type", "csv", "dif", "prn", "json", "series"))
    if is_graph:
        from .graph import GraphDoc

        ct = str(raw.get("chart_type", "bar"))
        if "csv" in raw:
            doc = GraphDoc.from_csv(raw["csv"], title=title, chart_type=ct)
        elif "dif" in raw:
            doc = GraphDoc.from_dif(raw["dif"], title=title, chart_type=ct)
        elif "prn" in raw:
            doc = GraphDoc.from_prn(raw["prn"], title=title, chart_type=ct)
        elif "json" in raw:
            doc = GraphDoc.from_json(raw["json"], title=title, chart_type=ct, metric_key=raw.get("metric_key"))
        else:
            doc = GraphDoc(
                title=title,
                chart_type=ct,
                categories=raw.get("categories", ()),
                series=raw.get("series", ()),
                x_label=str(raw.get("x_label", "")),
                y_label=str(raw.get("y_label", "")),
            )
        return Slide(title=title, content=doc, speaker_notes=notes)

    from .wordchart import WordChartDoc

    wc = WordChartDoc(
        title=title,
        column_head=raw.get("column_head", ()),
        text_body=raw.get("text_body", ()),
        columns=raw.get("columns"),
        footer=raw.get("footer", ""),
        template=str(raw.get("template", "column_1")),
        bullet_style=str(raw.get("bullet_style", "none")),
        speaker_notes=notes,
    )
    return Slide(title=title, content=wc, speaker_notes=notes)


@dataclass
class SlideDeck:
    """Presentation deck compiling slides into `.gem`, PNG/JPG/SVG, `.lis`, and `player.html`."""

    slug: str
    title: str
    subtitle: str = ""
    volume_label: str = ""
    sister_id: str = "zoe"
    slides: Sequence[Slide] = field(default_factory=list)
    constitutional: dict[str, Any] = field(default_factory=dict)
    wait_mode: str = "key"
    cycle: bool = False
    theme: Any = None
    category: str = "Presentation"
    date: str = "2026-11-25"
    summary: str = ""

    def __post_init__(self) -> None:
        clean_slug = str(self.slug or "").strip()
        if not clean_slug or clean_slug in {".", ".."} or "/" in clean_slug or "\\" in clean_slug or ".." in clean_slug:
            raise ValueError(f"Invalid deck slug: {self.slug!r}")
        self.slug = clean_slug
        self.wait_mode = normalize_wait_mode(self.wait_mode)

    @classmethod
    def from_spec(cls, spec: Mapping[str, Any] | Path | str) -> SlideDeck:
        if isinstance(spec, (Path, str)):
            sp = Path(spec)
            if not sp.is_file():
                raise FileNotFoundError(f"Deck spec not found: {sp}")
            data = json.loads(sp.read_text(encoding="utf-8"))
        else:
            data = spec
        if not isinstance(data, Mapping):
            raise ValueError(f"Deck spec root must be a JSON object, got {type(data).__name__}")
        raw_slides = data.get("slides", [])
        if not isinstance(raw_slides, list):
            raise ValueError(f"Deck spec 'slides' must be a list, got {type(raw_slides).__name__}")
        slides = [s if isinstance(s, Slide) else _slide_from_spec_dict(s, i) for i, s in enumerate(raw_slides, start=1)]
        return cls(
            slug=str(data.get("slug", "zoe-deck")),
            title=str(data.get("title", "Zoe Presentation")),
            subtitle=str(data.get("subtitle", "")),
            volume_label=str(data.get("volume_label", "")),
            sister_id=str(data.get("sister_id", "zoe")),
            slides=slides,
            constitutional=dict(data.get("constitutional", {})),
            wait_mode=str(data.get("wait_mode", "key")),
            cycle=bool(data.get("cycle", False)),
            category=str(data.get("category", "Presentation")),
            date=str(data.get("date", "2026-11-25")),
            summary=str(data.get("summary", "")),
        )

    def build(
        self,
        out_dir: Path | str,
        *,
        overwrite: bool = True,
        render_png: bool = True,
        render_jpg: bool = False,
        render_svg: bool = False,
        width: int = 1920,
        height: int = 1080,
    ) -> dict[str, Any]:
        """Compile all slides to `.gem`, PNG/JPG/SVG, `.lis`, and offline `player.html`."""
        if not self.slides:
            raise ValueError(f"SlideDeck {self.slug!r} cannot be built with zero slides")
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        if not overwrite:
            blocked = [out / "player.html", out / f"{self.slug}.lis", *out.glob("slide-*.gem")]
            if any(p.exists() for p in blocked):
                raise FileExistsError(f"Output directory already contains presentation artifacts: {out}")

        slide_records: list[dict[str, Any]] = []
        gem_paths: list[Path] = []
        hygiene_scrubs = sum(
            1 for val in (self.title, self.subtitle, self.volume_label, self.category, self.summary)
            if val and scrub_hygiene(str(val)) != str(val)
        )

        for idx, slide in enumerate(self.slides, start=1):
            cv = slide.compile_to_canvas(
                sister_id=self.sister_id,
                slide_index=idx,
                constitutional=self.constitutional,
            )
            hygiene_scrubs += int(getattr(cv, "_hygiene_scrubs", 0))
            gem_bytes = cv.to_gem_bytes()
            chk = seasip_gem.verify_seasip_gem_metafile(gem_bytes)
            if not chk.get("valid"):
                raise ValueError(f"Slide {idx} .GEM failed verification: {chk}")
            gem_name = f"slide-{idx:02d}.gem"
            gem_path = atomic_write_bytes(out / gem_name, gem_bytes)
            gem_paths.append(gem_path)

            png_name = ""
            jpg_name = ""
            svg_name = ""
            if render_png:
                png_name = f"slide-{idx:02d}.png"
                cv.render_png(out / png_name, width=width, height=height)
            if render_jpg:
                jpg_name = f"slide-{idx:02d}.jpg"
                cv.render_jpg(out / jpg_name, width=width, height=height)
            if render_svg:
                svg_name = f"slide-{idx:02d}.svg"
                cv.render_svg(out / svg_name, width=width)

            report = cv.verify_layout()
            slide_records.append({
                "index": idx,
                "title": cv.title,
                "speaker_notes": cv.speaker_notes,
                "gem_name": gem_name,
                "png_name": png_name,
                "jpg_name": jpg_name,
                "svg_name": svg_name,
                "layout_ok": report.ok,
            })

        lis_path = write_lis_playlist(
            out / f"{self.slug}.lis",
            [gp.name for gp in gem_paths],
            wait_mode=self.wait_mode,
            cycle=self.cycle,
            theme=self.sister_id,
        )
        player = SlideShowPlayer(self, slide_records)
        player_html = player.render_html()
        hygiene_scrubs += player.extra_html_scrubs
        player_path = atomic_write_text(out / "player.html", player_html)
        return {
            "slug": self.slug,
            "out_dir": str(out),
            "slides": slide_records,
            "lis_path": str(lis_path),
            "player_path": str(player_path),
            "hygiene_scrubs": hygiene_scrubs,
        }


def export_pptx(deck: SlideDeck, output_path: Path | str, *, slide_dir: Path | str | None = None) -> Path:
    """Strictly optional, lazy-imported `.pptx` compatibility export (never used at core runtime)."""
    try:
        from pptx import Presentation  # type: ignore[import-untyped]
        from pptx.util import Inches  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("Optional `python-pptx` package is required only for export_pptx()") from exc

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]
    img_root = Path(slide_dir) if slide_dir is not None else None

    for idx, slide in enumerate(deck.slides, start=1):
        pslide = prs.slides.add_slide(blank_layout)
        if img_root is not None and (img_root / f"slide-{idx:02d}.png").is_file():
            pslide.shapes.add_picture(str(img_root / f"slide-{idx:02d}.png"), Inches(0), Inches(0), prs.slide_width, prs.slide_height)
        else:
            tx = pslide.shapes.add_textbox(Inches(0.8), Inches(0.6), Inches(11.7), Inches(1.5))
            tx.text_frame.text = scrub_hygiene(slide.title)
        if slide.speaker_notes:
            pslide.notes_slide.notes_text_frame.text = scrub_hygiene(slide.speaker_notes)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


__all__ = [
    "WAIT_MODES",
    "LisEntry",
    "LisPlaylist",
    "Slide",
    "SlideDeck",
    "SlideShowPlayer",
    "dump_lis_playlist",
    "export_pptx",
    "interval_from_wait_mode",
    "load_lis_playlist",
    "normalize_wait_mode",
    "parse_lis_playlist",
    "validate_lis_playlist",
    "write_lis_playlist",
]
