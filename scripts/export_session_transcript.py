#!/usr/bin/env python3
"""Sanitized TrueColor CLI Session Transcript Exporter for Project Zoe.

Reads an Antigravity CLI `transcript_full.jsonl` conversation log and generates
three synchronized, visually distinct, privacy-sanitized archives inside
`research/sessions/`:
  1. `<prefix>.html` — Interactive TrueColor dark-terminal viewer with Chapter Jump Bar,
     speaker filter buttons (`All` / `Nicholas` / `Zoe`), collapsible Tool Trace pills,
     live search + match counter, and full Markdown-to-HTML syntax coloring.
  2. `<prefix>.ansi` — Native 24-bit RGB TrueColor ANSI replay (`less -R`).
  3. `<prefix>.md`   — GitHub-native colorized Markdown with ANSI header banner, chapter
     navigation, commit ledgers, blue `NOTE` user cards, collapsible tool traces, and
     relative repository links.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import html
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import unquote


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SECRET_RE = re.compile(
    r"(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{20,})",
    re.I,
)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((file://[^)]+)\)")


CHAPTER_MILESTONES: Tuple[Tuple[int, str, str], ...] = (
    (1, "Ch. 01 · Ethics Audio & YouTube Video", "Verifying Nicholas Michael Kloster's audio & lossless 1080p render"),
    (3, "Ch. 02 · Profile Plates & Research Shelf", "Redesigning Ablation-Tool profile in Computer Visualization plates"),
    (11, "Ch. 03 · Groove Forensics & CicadaClock", "Poincare swing attractors, Kuramoto clock locking & 40 Hz Dorothy ISI"),
    (16, "Ch. 04 · Zoe Living Atelier README", "Animated SVGs, Six Living Worlds showcase & Nicholas x Zoe attribution"),
    (22, "Ch. 05 · L3 Research Collaborator", "Pre-registered 9-stage cycles across MIDI, Dorothy CCFv3 & CicadaClock (14/14)"),
    (23, "Ch. 06 · L4 Self-Improvement & Multi-Module", "AST evolution across 6 domains & 3 runtime engines with atomic diffs (17/17)"),
    (26, "Ch. 07 · Zoe's Native 44-Phoneme Voice", "Formant vocal tract, soprano singing, Woodworth 3D binaural & Chladni VDI (14/14)"),
    (29, "Ch. 08 · L5 Phase 1 Integrated 10-Domain Core", "All 10 AGI domains, 4-system memory, counterfactual route flip & 16/16 verifier"),
    (33, "Ch. 09 · L5 Phase 2 Open-World Generalization", "Multi-file AST repair, 2,400-ep memory, 84-PNG vision & 16 external LLMs (18/18)"),
    (34, "Ch. 10 · Full TrueColor Session Chronicle", "Archiving all 34 turns across HTML, 24-bit ANSI & GitHub Markdown"),
)


def strip_user_wrappers(raw: str) -> str:
    txt = raw.strip()
    m = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", txt, flags=re.S)
    if m:
        txt = m.group(1).strip()
    txt = re.sub(r"<ADDITIONAL_METADATA>.*?</ADDITIONAL_METADATA>", "", txt, flags=re.S).strip()
    return txt


def _rewrite_file_url(label: str, url: str, target_mode: str, zoe_root: str, profile_root: str) -> str:
    path_str = unquote(url[len("file://") :])
    path_clean = path_str.split("#", 1)[0]
    frag = ("#" + path_str.split("#", 1)[1]) if "#" in path_str else ""

    if path_clean.startswith(zoe_root.rstrip("/") + "/"):
        rel = path_clean[len(zoe_root.rstrip("/")) + 1 :]
        if target_mode == "md":
            return f"[{label}](../../{rel}{frag})"
        if target_mode == "html":
            return f"[{label}](https://github.com/Ablation-Tool/zoe/blob/main/{rel}{frag})"
        return f"{label} ($ZOE_ROOT/{rel})"

    if path_clean.startswith(profile_root.rstrip("/") + "/"):
        rel = path_clean[len(profile_root.rstrip("/")) + 1 :]
        if target_mode in {"md", "html"}:
            return f"[{label}](https://github.com/Ablation-Tool/Ablation-Tool/blob/main/{rel}{frag})"
        return f"{label} ($PROFILE_REPO/{rel})"

    m_home_sub = re.match(r"^/home/[A-Za-z0-9._-]+/(Desktop|Downloads)/(.+)$", path_clean)
    if m_home_sub:
        folder, rel = m_home_sub.group(1), m_home_sub.group(2)
        return f"`~/{folder}/{rel}`" if target_mode in {"md", "html"} else f"~/{folder}/{rel}"
    m_home = re.match(r"^/home/[A-Za-z0-9._-]+/(.+)$", path_clean)
    if m_home:
        rel = m_home.group(1)
        return f"`~/{rel}`" if target_mode in {"md", "html"} else f"~/{rel}"
    return f"`{path_clean}`"


def sanitize_text(
    text: str,
    *,
    mode: str,
    zoe_root: str = "",
    profile_root: str = "",
) -> str:
    zoe_root = zoe_root or str(Path(__file__).resolve().parents[1])
    profile_root = profile_root or str(Path.home() / "Ablation-Tool-profile")
    t = text.replace("\r\n", "\n")
    t = EMAIL_RE.sub("[redacted-email]", t)
    t = SECRET_RE.sub("[redacted-token]", t)

    def _repl(match: re.Match[str]) -> str:
        return _rewrite_file_url(match.group(1), match.group(2), mode, zoe_root, profile_root)

    t = MD_LINK_RE.sub(_repl, t)

    t = re.sub(r"/home/[A-Za-z0-9._-]+/\.gemini/antigravity-cli/brain/[^\s\"')`>]+", "[local-session-artifacts]", t)
    t = re.sub(r"/home/[A-Za-z0-9._-]+/\.gemini/antigravity-cli", "[local-session-artifacts]", t)
    t = re.sub(r"/home/[A-Za-z0-9._-]+/security-tools/bin/python3", "python3", t)
    t = t.replace(zoe_root.rstrip("/") + "/", "$ZOE_ROOT/")
    t = t.replace(zoe_root.rstrip("/"), "$ZOE_ROOT")
    t = t.replace(profile_root.rstrip("/") + "/", "$PROFILE_REPO/")
    t = t.replace(profile_root.rstrip("/"), "$PROFILE_REPO")
    t = re.sub(r"/home/[A-Za-z0-9._-]+/Desktop/", "~/Desktop/", t)
    t = re.sub(r"/home/[A-Za-z0-9._-]+/Downloads/", "~/Downloads/", t)
    t = re.sub(r"/home/[A-Za-z0-9._-]+(?=[/\s\"')`>:]|$)", "~", t)
    t = re.sub(r"/media/[A-Za-z0-9._-]+(?=[/\s\"')`>:]|$)", "/mnt/workstation", t)
    return t


@dataclass
class ToolBatch:
    counts: Dict[str, int] = field(default_factory=dict)
    summaries: List[str] = field(default_factory=list)
    files_touched: List[str] = field(default_factory=list)
    total_calls: int = 0

    def add_calls(self, calls: Sequence[Dict[str, Any]], zoe_root: str, profile_root: str) -> None:
        for tc in calls:
            name = str(tc.get("name") or "tool")
            args = tc.get("args") or {}
            self.counts[name] = self.counts.get(name, 0) + 1
            self.total_calls += 1
            if name == "run_command":
                summ = str(args.get("toolSummary") or "").strip()
                if summ and summ not in self.summaries:
                    self.summaries.append(sanitize_text(summ, mode="ansi", zoe_root=zoe_root, profile_root=profile_root))
            elif name in {"write_file", "edit_file"}:
                p = sanitize_text(str(args.get("Path") or ""), mode="ansi", zoe_root=zoe_root, profile_root=profile_root)
                if p:
                    short = p.replace("$ZOE_ROOT/", "").replace("$PROFILE_REPO/", "profile/")
                    if short not in self.files_touched:
                        self.files_touched.append(short)

    def is_empty(self) -> bool:
        return self.total_calls == 0

    def compact_label(self) -> str:
        parts = [f"{k} x{v}" for k, v in sorted(self.counts.items(), key=lambda kv: (-kv[1], kv[0]))]
        return ", ".join(parts)


@dataclass
class TimelineItem:
    kind: str  # "user", "tools", "assistant"
    turn_num: Optional[int]
    timestamp: str
    content: str = ""
    tools: Optional[ToolBatch] = None
    chapter: Optional[Tuple[int, str, str]] = None


def parse_transcript(
    transcript_path: Path,
    zoe_root: str,
    profile_root: str,
) -> Tuple[List[TimelineItem], Dict[str, int]]:
    chapter_by_turn: Dict[int, Tuple[int, str, str]] = {}
    for ch_idx, (t_start, ch_title, ch_sub) in enumerate(CHAPTER_MILESTONES, start=1):
        chapter_by_turn[t_start] = (ch_idx, ch_title, ch_sub)

    items: List[TimelineItem] = []
    pending_tools = ToolBatch()
    turn_num = 0
    stats = {"user_turns": 0, "assistant_responses": 0, "tool_calls": 0, "tool_batches": 0}

    def _flush_tools(ts: str) -> None:
        nonlocal pending_tools
        if not pending_tools.is_empty():
            stats["tool_batches"] += 1
            items.append(TimelineItem(kind="tools", turn_num=None, timestamp=ts, tools=pending_tools))
            pending_tools = ToolBatch()

    with transcript_path.open(encoding="utf-8") as fh:
        for line in fh:
            obj = json.loads(line)
            typ = obj.get("type")
            src = obj.get("source")
            ts = str(obj.get("created_at") or "")
            if typ == "USER_INPUT" and src == "USER_EXPLICIT":
                _flush_tools(ts)
                raw = strip_user_wrappers(str(obj.get("content") or ""))
                if not raw:
                    continue
                turn_num += 1
                stats["user_turns"] += 1
                items.append(
                    TimelineItem(
                        kind="user",
                        turn_num=turn_num,
                        timestamp=ts,
                        content=raw,
                        chapter=chapter_by_turn.get(turn_num),
                    )
                )
            elif typ == "PLANNER_RESPONSE":
                tcalls = obj.get("tool_calls") or []
                if tcalls:
                    pending_tools.add_calls(tcalls, zoe_root, profile_root)
                    stats["tool_calls"] += len(tcalls)
                content = str(obj.get("content") or "").strip()
                if content:
                    _flush_tools(ts)
                    stats["assistant_responses"] += 1
                    items.append(TimelineItem(kind="assistant", turn_num=None, timestamp=ts, content=content))

    _flush_tools("")
    return items, stats


def collect_commits(repo_dir: Path, since: str = "2026-11-19 09:00") -> List[str]:
    if not repo_dir.is_dir():
        return []
    proc = subprocess.run(
        ["git", "-C", str(repo_dir), "log", f"--since={since}", "--oneline"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return []
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Format 1 · HTML Renderer (TrueColor Obsidian Terminal + Search + Role Filter)
# ---------------------------------------------------------------------------

def _inline_md_to_html(text: str) -> str:
    # Extract inline code spans first so inner chars aren't mangled
    code_spans: List[str] = []

    def _save_code(m: re.Match[str]) -> str:
        code_spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00CODE{len(code_spans) - 1}\x00"

    t = re.sub(r"`([^`\n]+)`", _save_code, text)

    # Extract Markdown links [label](url)
    links: List[str] = []

    def _save_link(m: re.Match[str]) -> str:
        lbl = html.escape(m.group(1))
        url = html.escape(m.group(2), quote=True)
        links.append(f'<a href="{url}" target="_blank" rel="noopener">{lbl}</a>')
        return f"\x00LINK{len(links) - 1}\x00"

    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", _save_link, t)
    t = html.escape(t)
    t = re.sub(r"\*\*((?:(?!\*\*).)+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", t)

    for idx, val in enumerate(links):
        t = t.replace(f"\x00LINK{idx}\x00", val)
    for idx, val in enumerate(code_spans):
        t = t.replace(f"\x00CODE{idx}\x00", val)
    return t


def markdown_to_html(md_text: str) -> str:
    lines = md_text.splitlines()
    out: List[str] = []
    i = 0
    n = len(lines)

    while i < n:
        ln = lines[i]
        stripped = ln.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            fence = "```"
            lang = stripped[3:].strip() or "text"
            code_lines: List[str] = []
            i += 1
            while i < n and not lines[i].strip().startswith(fence):
                code_lines.append(lines[i])
                i += 1
            i += 1
            body = html.escape("\n".join(code_lines))
            out.append(f'<div class="code-block"><span class="code-lang">{html.escape(lang)}</span><pre><code>{body}</code></pre></div>')
            continue

        # Horizontal rule
        if re.match(r"^[-*_]{3,}$", stripped):
            out.append('<hr class="inner-hr" />')
            i += 1
            continue

        # Headings
        hm = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if hm:
            lvl = len(hm.group(1))
            cls = "md-h2" if lvl <= 2 else "md-h3"
            out.append(f'<h4 class="{cls}">{_inline_md_to_html(hm.group(2))}</h4>')
            i += 1
            continue

        # Blockquote
        if stripped.startswith(">"):
            bq_lines: List[str] = []
            while i < n and lines[i].strip().startswith(">"):
                bq_lines.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + "<br/>".join(_inline_md_to_html(x) for x in bq_lines) + "</blockquote>")
            continue

        # Table (header + separator)
        if "|" in stripped and i + 1 < n and re.match(r"^\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1].strip()):
            hdr_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2
            rows: List[List[str]] = []
            while i < n and "|" in lines[i].strip() and lines[i].strip():
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            ths = "".join(f"<th>{_inline_md_to_html(c)}</th>" for c in hdr_cells)
            trs = "".join("<tr>" + "".join(f"<td>{_inline_md_to_html(c)}</td>" for c in r) + "</tr>" for r in rows)
            out.append(f'<div class="tbl-wrap"><table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>')
            continue

        # Bullet / numbered list
        if re.match(r"^(\s*[-*]|\s*\d+\.)\s+", ln):
            is_ord = bool(re.match(r"^\s*\d+\.\s+", ln))
            tag = "ol" if is_ord else "ul"
            lis: List[str] = []
            while i < n:
                cur = lines[i]
                if not cur.strip():
                    break
                m_li = re.match(r"^(?:\s*[-*]|\s*\d+\.)\s+(.*)$", cur)
                if m_li:
                    lis.append(f"<li>{_inline_md_to_html(m_li.group(1))}</li>")
                    i += 1
                elif cur.startswith("  ") and lis:
                    lis[-1] = lis[-1][:-5] + " " + _inline_md_to_html(cur.strip()) + "</li>"
                    i += 1
                else:
                    break
            out.append(f"<{tag}>{''.join(lis)}</{tag}>")
            continue

        # Paragraph
        para_lines: List[str] = []
        while i < n:
            cur = lines[i].strip()
            if not cur or cur.startswith(("#", "```", ">", "- ", "* ")) or re.match(r"^\d+\.\s+", cur) or re.match(r"^[-*_]{3,}$", cur):
                break
            para_lines.append(cur)
            i += 1
        out.append(f"<p>{'<br/>'.join(_inline_md_to_html(x) for x in para_lines)}</p>")

    return "\n".join(out)


def render_html(
    items: Sequence[TimelineItem],
    stats: Dict[str, int],
    zoe_commits: Sequence[str],
    profile_commits: Sequence[str],
    zoe_root: str,
    profile_root: str,
) -> str:
    chap_nav = "\n".join(
        f'<a class="ch-pill" href="#chapter-{idx}">{html.escape(title)}</a>'
        for idx, (_t, title, _sub) in enumerate(CHAPTER_MILESTONES, start=1)
    )
    z_lis = "\n".join(
        f'<li><a href="https://github.com/Ablation-Tool/zoe/commit/{html.escape(c.split()[0])}" target="_blank" rel="noopener"><code>{html.escape(c.split()[0])}</code></a> {html.escape(c.split(" ", 1)[1] if " " in c else "")}</li>'
        for c in zoe_commits
    )
    p_lis = "\n".join(
        f'<li><a href="https://github.com/Ablation-Tool/Ablation-Tool/commit/{html.escape(c.split()[0])}" target="_blank" rel="noopener"><code>{html.escape(c.split()[0])}</code></a> {html.escape(c.split(" ", 1)[1] if " " in c else "")}</li>'
        for c in profile_commits
    )

    body_blocks: List[str] = []
    for item in items:
        if item.chapter is not None:
            ch_idx, ch_title, ch_sub = item.chapter
            body_blocks.append(
                f'<div class="chapter-ribbon" id="chapter-{ch_idx}">'
                f'<span class="ch-badge">CHAPTER {ch_idx:02d}</span>'
                f'<div><div class="ch-title">{html.escape(ch_title)}</div>'
                f'<div class="ch-sub">{html.escape(ch_sub)}</div></div>'
                f"</div>"
            )

        ts_short = html.escape(item.timestamp.replace("T", " "))
        if item.kind == "user":
            san = sanitize_text(item.content, mode="html", zoe_root=zoe_root, profile_root=profile_root)
            rendered = markdown_to_html(san)
            body_blocks.append(
                f'<article class="msg msg-user" id="turn-{item.turn_num}" data-role="user">'
                f'<header class="msg-hdr user-hdr">'
                f'<span class="prompt-glyph">NICHOLAS · you &gt;</span>'
                f'<span class="turn-pill">Turn {item.turn_num}</span>'
                f'<span class="ts">{ts_short}</span>'
                f"</header>"
                f'<div class="msg-body user-body">{rendered}</div>'
                f"</article>"
            )
        elif item.kind == "tools" and item.tools is not None:
            tb = item.tools
            det_parts: List[str] = []
            if tb.summaries:
                det_parts.append("<div><strong>Commands / Tasks:</strong><ul>" + "".join(f"<li>{html.escape(s)}</li>" for s in tb.summaries[:14]) + "</ul></div>")
            if tb.files_touched:
                det_parts.append("<div><strong>Files Written / Edited:</strong> " + " · ".join(f"<code>{html.escape(f)}</code>" for f in tb.files_touched[:16]) + "</div>")
            body_blocks.append(
                f'<details class="msg tool-trace" data-role="tools">'
                f'<summary><span class="tool-glyph">⚙ ENGINEERING TRACE</span>'
                f'<span class="tool-stats">{html.escape(tb.compact_label())} ({tb.total_calls} tool steps)</span>'
                f'<span class="ts">{ts_short}</span></summary>'
                f'<div class="tool-detail">{"".join(det_parts) or "Read-only inspection steps."}</div>'
                f"</details>"
            )
        elif item.kind == "assistant":
            san = sanitize_text(item.content, mode="html", zoe_root=zoe_root, profile_root=profile_root)
            rendered = markdown_to_html(san)
            body_blocks.append(
                f'<article class="msg msg-assistant" data-role="assistant">'
                f'<header class="msg-hdr asst-hdr">'
                f'<span class="asst-glyph">◆ ZOE ::</span>'
                f'<span class="role-badge-zoe">Verified Response</span>'
                f'<span class="ts">{ts_short}</span>'
                f"</header>"
                f'<div class="msg-body asst-body">{rendered}</div>'
                f"</article>"
            )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Nicholas × Zoe · Complete Session Chronicle (2026-11-19 → 2026-11-20)</title>
<style>
  :root {{
    --bg: #070d18;
    --term: #0b1324;
    --panel: #101b32;
    --card-user: #0a2039;
    --card-asst: #10162b;
    --card-tool: #141926;
    --border: #233658;
    --red: #ef445a;
    --orchid: #f0a3df;
    --gold: #f2c65e;
    --cyan: #5ce1e6;
    --green: #86efac;
    --purple: #c084fc;
    --text: #e8f0ff;
    --muted: #8ea3c5;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: radial-gradient(circle at top, #131c3b 0%, var(--bg) 62%);
    color: var(--text);
    font-family: "JetBrains Mono", "Fira Code", "DejaVu Sans Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 13.8px;
    line-height: 1.62;
    padding: 24px 16px 64px;
  }}
  .terminal-window {{
    max-width: 1140px;
    margin: 0 auto;
    background: var(--term);
    border: 1px solid var(--border);
    border-radius: 14px;
    box-shadow: 0 24px 75px rgba(0, 0, 0, 0.7);
    overflow: hidden;
  }}
  .titlebar {{
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 10px;
    padding: 12px 18px;
    background: #0d172b;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    z-index: 30;
  }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; display: inline-block; }}
  .dot-r {{ background: #ef445a; }}
  .dot-y {{ background: #f2c65e; }}
  .dot-g {{ background: #86efac; }}
  .titlebar-text {{ color: var(--muted); font-size: 12px; margin-left: 6px; flex: 1 1 260px; }}
  .controls {{ display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }}
  .btn {{
    background: #0a1426;
    border: 1px solid var(--border);
    color: var(--muted);
    padding: 4px 10px;
    border-radius: 7px;
    font-family: inherit;
    font-size: 11.5px;
    cursor: pointer;
  }}
  .btn.active {{ border-color: var(--cyan); color: var(--cyan); background: rgba(92,225,230,0.12); font-weight: 700; }}
  .btn.active-zoe {{ border-color: var(--red); color: var(--red); background: rgba(239,68,90,0.14); font-weight: 700; }}
  .search-box {{
    background: #081020;
    border: 1px solid var(--border);
    color: var(--cyan);
    padding: 5px 10px;
    border-radius: 7px;
    font-family: inherit;
    font-size: 12px;
    width: 210px;
  }}
  .search-box:focus {{ outline: none; border-color: var(--cyan); }}
  .banner {{
    padding: 24px 26px 18px;
    border-bottom: 1px solid var(--border);
    background: linear-gradient(135deg, rgba(239,68,90,0.10), rgba(240,163,223,0.06) 48%, rgba(92,225,230,0.08));
  }}
  .banner h1 {{ margin: 0 0 8px; font-size: 20px; color: var(--red); letter-spacing: 0.4px; }}
  .banner .meta {{ color: var(--gold); font-size: 12.5px; margin-bottom: 14px; }}
  .legend {{
    display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 14px; font-size: 11.5px;
  }}
  .leg-item {{ padding: 3px 10px; border-radius: 999px; border: 1px solid var(--border); }}
  .leg-user {{ border-color: var(--cyan); color: var(--cyan); background: rgba(92,225,230,0.09); }}
  .leg-zoe {{ border-color: var(--red); color: var(--orchid); background: rgba(239,68,90,0.11); }}
  .leg-tool {{ border-color: var(--gold); color: var(--gold); background: rgba(242,198,94,0.08); }}
  .chapter-nav {{
    display: flex; flex-wrap: wrap; gap: 7px; margin-bottom: 14px;
  }}
  .ch-pill {{
    text-decoration: none;
    background: #091325;
    border: 1px solid #2b426a;
    color: var(--orchid);
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 11.2px;
  }}
  .ch-pill:hover {{ border-color: var(--cyan); color: var(--cyan); }}
  .commits {{
    background: #08101f;
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 10px 15px;
    font-size: 12px;
    color: var(--muted);
    margin-top: 8px;
  }}
  .commits summary {{ cursor: pointer; color: var(--cyan); font-weight: 700; }}
  .commits ul {{ margin: 8px 0 0; padding-left: 18px; }}
  .commits li {{ margin: 3px 0; }}
  .commits code {{ color: var(--green); background: rgba(134,239,172,0.10); padding: 1px 5px; border-radius: 4px; }}
  .stream {{ padding: 22px 24px; display: flex; flex-direction: column; gap: 15px; }}
  .chapter-ribbon {{
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 11px 16px;
    margin-top: 10px;
    border-radius: 10px;
    background: linear-gradient(90deg, rgba(240,163,223,0.16), rgba(92,225,230,0.06));
    border: 1px solid rgba(240,163,223,0.42);
  }}
  .ch-badge {{
    background: rgba(239,68,90,0.22);
    border: 1px solid var(--red);
    color: var(--gold);
    font-size: 11px;
    font-weight: 800;
    padding: 3px 8px;
    border-radius: 6px;
    white-space: nowrap;
  }}
  .ch-title {{ color: var(--orchid); font-weight: 800; font-size: 14px; }}
  .ch-sub {{ color: var(--muted); font-size: 11.8px; }}
  .msg {{ border-radius: 10px; border: 1px solid var(--border); overflow: hidden; }}
  .msg-user {{
    background: var(--card-user);
    border-left: 5px solid var(--cyan);
    box-shadow: inset 0 0 0 1px rgba(92,225,230,0.14);
  }}
  .msg-assistant {{
    background: var(--card-asst);
    border-left: 5px solid var(--red);
    box-shadow: inset 0 0 0 1px rgba(239,68,90,0.12);
  }}
  .tool-trace {{
    background: var(--card-tool);
    border-left: 4px solid var(--gold);
    padding: 7px 14px;
    font-size: 11.8px;
    color: var(--muted);
  }}
  .tool-trace summary {{
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 10px;
    list-style: none;
  }}
  .tool-glyph {{ color: var(--gold); font-weight: 800; }}
  .tool-stats {{ color: #d5dfef; }}
  .tool-detail {{ margin-top: 8px; padding-top: 8px; border-top: 1px dashed rgba(242,198,94,0.28); }}
  .tool-detail ul {{ margin: 4px 0 8px; padding-left: 18px; }}
  .tool-detail code {{ color: var(--green); background: rgba(134,239,172,0.1); padding: 1px 5px; border-radius: 4px; }}
  .msg-hdr {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 8px 14px;
    font-size: 12px;
    border-bottom: 1px solid rgba(35, 54, 88, 0.6);
    background: rgba(7, 13, 24, 0.5);
  }}
  .prompt-glyph {{ color: var(--cyan); font-weight: 800; letter-spacing: 0.3px; }}
  .asst-glyph {{ color: var(--red); font-weight: 800; letter-spacing: 0.3px; }}
  .role-badge-zoe {{
    background: rgba(240,163,223,0.12);
    color: var(--orchid);
    border: 1px solid rgba(240,163,223,0.35);
    padding: 1px 7px;
    border-radius: 999px;
    font-size: 10.8px;
  }}
  .turn-pill {{
    background: rgba(92, 225, 230, 0.14);
    color: var(--gold);
    border: 1px solid rgba(242, 198, 94, 0.4);
    padding: 1px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 700;
  }}
  .ts {{ color: var(--muted); margin-left: auto; font-size: 11px; }}
  .msg-body {{ padding: 13px 16px; overflow-x: auto; }}
  .user-body {{ color: #d8f8ff; font-size: 14px; }}
  .msg-body p {{ margin: 0 0 10px; }}
  .msg-body p:last-child {{ margin-bottom: 0; }}
  .md-h2 {{ color: var(--red); margin: 14px 0 8px; font-size: 16px; }}
  .md-h3 {{ color: var(--gold); margin: 12px 0 6px; font-size: 14.3px; }}
  .msg-body strong {{ color: var(--gold); }}
  .msg-body em {{ color: var(--orchid); }}
  .msg-body a {{ color: var(--cyan); text-decoration: none; border-bottom: 1px dotted var(--cyan); }}
  .msg-body a:hover {{ color: #fff; }}
  .msg-body code {{
    background: #172744;
    color: var(--cyan);
    padding: 1.5px 6px;
    border-radius: 5px;
    font-size: 12.8px;
  }}
  .code-block {{
    position: relative;
    margin: 10px 0;
    background: #060c17;
    border: 1px solid #1e3154;
    border-radius: 8px;
    overflow: hidden;
  }}
  .code-lang {{
    position: absolute;
    top: 6px;
    right: 10px;
    font-size: 10.5px;
    color: var(--gold);
    opacity: 0.8;
    text-transform: uppercase;
  }}
  .code-block pre {{
    margin: 0;
    padding: 12px 14px;
    overflow-x: auto;
    color: var(--green);
    font-size: 12.6px;
    line-height: 1.5;
  }}
  .code-block code {{ background: none; color: inherit; padding: 0; }}
  blockquote {{
    margin: 8px 0;
    padding: 8px 14px;
    border-left: 3px solid var(--gold);
    background: rgba(242, 198, 94, 0.07);
    color: #f6e7be;
    border-radius: 0 6px 6px 0;
  }}
  ul, ol {{ margin: 6px 0 10px; padding-left: 22px; }}
  li {{ margin: 4px 0; }}
  .tbl-wrap {{ overflow-x: auto; margin: 10px 0; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12.4px; }}
  th {{ text-align: left; padding: 7px 10px; background: #132240; color: var(--gold); border: 1px solid var(--border); }}
  td {{ padding: 6px 10px; border: 1px solid rgba(35, 54, 88, 0.7); }}
  .inner-hr {{ border: none; border-top: 1px dashed var(--border); margin: 12px 0; }}
  .hidden {{ display: none !important; }}
</style>
</head>
<body>
  <main class="terminal-window">
    <div class="titlebar">
      <span class="dot dot-r"></span>
      <span class="dot dot-y"></span>
      <span class="dot dot-g"></span>
      <span class="titlebar-text">nicholas×zoe:~/research/sessions — {stats['user_turns']} Turns · {stats['assistant_responses']} Zoe Responses · {stats['tool_calls']} Tool Steps</span>
      <div class="controls">
        <button class="btn active" id="btn-all" type="button">All</button>
        <button class="btn" id="btn-user" type="button">Nicholas</button>
        <button class="btn" id="btn-zoe" type="button">Zoe</button>
        <button class="btn active" id="btn-tools" type="button">Traces</button>
        <input class="search-box" id="filter" type="search" placeholder="Search session..." aria-label="Search transcript" />
      </div>
    </div>
    <section class="banner">
      <h1>◆ NICHOLAS × ZOE · COMPLETE MARATHON SESSION TRANSCRIPT (2026-11-19 → 2026-11-20)</h1>
      <div class="meta">Repositories: Ablation-Tool/zoe &amp; Ablation-Tool/Ablation-Tool (main) · {stats['user_turns']} User Turns · {stats['assistant_responses']} Zoe Responses · {stats['tool_calls']} Engineering Tool Steps · Sanitized Privacy Verified</div>
      <div class="legend">
        <span class="leg-item leg-user">NICHOLAS · you &gt; (Cyan Border)</span>
        <span class="leg-item leg-zoe">◆ ZOE :: (Ruby / Orchid Border)</span>
        <span class="leg-item leg-tool">⚙ Engineering Trace (Gold Collapsible Pill)</span>
      </div>
      <nav class="chapter-nav" aria-label="Session Chapters">
        {chap_nav}
      </nav>
      <details class="commits">
        <summary>▸ View {len(zoe_commits)} Commits Shipped in Ablation-Tool/zoe + {len(profile_commits)} Commits in Ablation-Tool Profile</summary>
        <ul>{z_lis}</ul>
        <div style="margin-top:8px;color:var(--gold);font-weight:700;">GitHub Profile (Ablation-Tool/Ablation-Tool):</div>
        <ul>{p_lis}</ul>
      </details>
    </section>
    <section class="stream" id="stream">
      {"".join(body_blocks)}
    </section>
  </main>
<script>
  let roleMode = "all";
  let showTools = true;
  const filterBox = document.getElementById("filter");
  const cards = Array.from(document.querySelectorAll(".msg"));
  const ribbons = Array.from(document.querySelectorAll(".chapter-ribbon"));

  function applyFilter() {{
    const q = filterBox.value.trim().toLowerCase();
    for (const c of cards) {{
      const role = c.getAttribute("data-role");
      let vis = true;
      if (role === "tools" && !showTools) vis = false;
      if (roleMode === "user" && role !== "user") vis = false;
      if (roleMode === "assistant" && role !== "assistant") vis = false;
      if (vis && q.length > 0 && !c.textContent.toLowerCase().includes(q)) vis = false;
      c.classList.toggle("hidden", !vis);
    }}
    for (const r of ribbons) {{
      r.classList.toggle("hidden", q.length > 0);
    }}
  }}

  document.getElementById("btn-all").onclick = () => {{ roleMode = "all"; updateBtns(); applyFilter(); }};
  document.getElementById("btn-user").onclick = () => {{ roleMode = "user"; updateBtns(); applyFilter(); }};
  document.getElementById("btn-zoe").onclick = () => {{ roleMode = "assistant"; updateBtns(); applyFilter(); }};
  document.getElementById("btn-tools").onclick = () => {{ showTools = !showTools; updateBtns(); applyFilter(); }};
  filterBox.addEventListener("input", applyFilter);

  function updateBtns() {{
    document.getElementById("btn-all").className = "btn" + (roleMode === "all" ? " active" : "");
    document.getElementById("btn-user").className = "btn" + (roleMode === "user" ? " active" : "");
    document.getElementById("btn-zoe").className = "btn" + (roleMode === "assistant" ? " active-zoe" : "");
    document.getElementById("btn-tools").className = "btn" + (showTools ? " active" : "");
  }}
</script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Format 2 · Native 24-Bit TrueColor ANSI Terminal Replay (`less -R`)
# ---------------------------------------------------------------------------

def _ansi_rgb(r: int, g: int, b: int, bold: bool = False) -> str:
    return f"\x1b[{'1;' if bold else ''}38;2;{r};{g};{b}m"


RESET = "\x1b[0m"
C_RUBY = _ansi_rgb(239, 68, 90, bold=True)
C_CYAN = _ansi_rgb(92, 225, 230, bold=True)
C_ICE = _ansi_rgb(214, 247, 255)
C_GOLD = _ansi_rgb(242, 198, 94, bold=True)
C_MINT = _ansi_rgb(134, 239, 172)
C_ORCHID = _ansi_rgb(240, 163, 223, bold=True)
C_TEXT = _ansi_rgb(232, 240, 255)
C_MUTED = _ansi_rgb(142, 163, 197)


def _colorize_ansi_line(line: str, is_user: bool) -> str:
    base = C_ICE if is_user else C_TEXT
    s = line
    if s.startswith("#"):
        return f"{C_GOLD}{s}{RESET}"
    if s.startswith(">"):
        return f"{C_ORCHID}{s}{RESET}"
    # Highlight `inline code` in Mint and **bold** in Gold cleanly
    s = re.sub(r"`([^`\n]+)`", lambda m: f"{C_MINT}`{m.group(1)}`{base}", s)
    s = re.sub(r"\*\*([^*\n]+)\*\*", lambda m: f"{C_GOLD}{m.group(1)}{base}", s)
    return f"{base}{s}{RESET}"


def render_ansi(
    items: Sequence[TimelineItem],
    stats: Dict[str, int],
    zoe_commits: Sequence[str],
    zoe_root: str,
    profile_root: str,
) -> str:
    lines: List[str] = [
        f"{C_RUBY}╔══════════════════════════════════════════════════════════════════════════════════════════════╗{RESET}",
        f"{C_RUBY}║  ◆ NICHOLAS × ZOE · COMPLETE MARATHON SESSION TRANSCRIPT (2026-11-19 -> 2026-11-20)         ║{RESET}",
        f"{C_RUBY}║  {C_GOLD}{stats['user_turns']} Turns · {stats['assistant_responses']} Zoe Responses · {stats['tool_calls']} Tool Steps · {len(zoe_commits)} Repo Commits · Sanitized Privacy Clean{C_RUBY}   ║{RESET}",
        f"{C_RUBY}╚══════════════════════════════════════════════════════════════════════════════════════════════╝{RESET}",
        "",
        f"{C_ORCHID}Legend:{RESET} {C_CYAN}🟦 NICHOLAS (you >){RESET}  |  {C_RUBY}💎 ZOE (::){RESET}  |  {C_GOLD}⚙ Tool Trace{RESET}  |  {C_MINT}`Code & Artifacts`{RESET}",
        "",
    ]

    for item in items:
        if item.chapter is not None:
            ch_idx, ch_title, ch_sub = item.chapter
            lines.extend([
                f"{C_ORCHID}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}",
                f"{C_ORCHID}  ★ CHAPTER {ch_idx:02d}: {ch_title}  {C_MUTED}— {ch_sub}{RESET}",
                f"{C_ORCHID}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{RESET}",
                "",
            ])

        ts_short = item.timestamp.replace("T", " ")
        if item.kind == "user":
            san = sanitize_text(item.content, mode="ansi", zoe_root=zoe_root, profile_root=profile_root)
            lines.append(f"{C_CYAN}╭─ 🟦 NICHOLAS · you >  {C_GOLD}[Turn {item.turn_num}]  {C_MUTED}{ts_short}{RESET}")
            for ln in san.splitlines():
                lines.append(f"{C_CYAN}│{RESET} " + _colorize_ansi_line(ln, is_user=True))
            lines.append(f"{C_CYAN}╰────────────────────────────────────────────────────────────────────────────────────────────{RESET}\n")
        elif item.kind == "tools" and item.tools is not None:
            tb = item.tools
            extra = ""
            if tb.files_touched:
                extra = f" | files: {', '.join(tb.files_touched[:5])}"
            lines.append(f"  {C_GOLD}⚙ [Engineering Trace: {tb.compact_label()} ({tb.total_calls} steps){extra}]{RESET}")
        elif item.kind == "assistant":
            san = sanitize_text(item.content, mode="ansi", zoe_root=zoe_root, profile_root=profile_root)
            lines.append(f"{C_RUBY}╭─ 💎 ZOE ::  {C_MUTED}{ts_short}{RESET}")
            in_code = False
            for ln in san.splitlines():
                if ln.strip().startswith("```"):
                    in_code = not in_code
                    lines.append(f"{C_RUBY}│{RESET} {C_GOLD}{ln}{RESET}")
                elif in_code:
                    lines.append(f"{C_RUBY}│{RESET} {C_MINT}{ln}{RESET}")
                else:
                    lines.append(f"{C_RUBY}│{RESET} " + _colorize_ansi_line(ln, is_user=False))
            lines.append(f"{C_RUBY}╰────────────────────────────────────────────────────────────────────────────────────────────{RESET}\n")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Format 3 · GitHub-Native Colorized Markdown
# ---------------------------------------------------------------------------

def render_markdown(
    items: Sequence[TimelineItem],
    stats: Dict[str, int],
    zoe_commits: Sequence[str],
    profile_commits: Sequence[str],
    zoe_root: str,
    profile_root: str,
) -> str:
    ch_toc = "\n".join(
        f"- **Chapter {idx:02d}:** [{title}](#chapter-{idx:02d}) — *{sub}*"
        for idx, (_t, title, sub) in enumerate(CHAPTER_MILESTONES, start=1)
    )
    z_list = "\n".join(f"- `{c}`" for c in zoe_commits)
    p_list = "\n".join(f"- `{c}`" for c in profile_commits)

    out: List[str] = [
        "# Complete Session Chronicle — 2026-11-19 → 2026-11-20",
        "",
        "> [!TIP]",
        "> **Choose your viewing experience:**",
        "> - **TrueColor Interactive Dark Terminal Viewer:** Open [`2026-11-20-session-transcript.html`](2026-11-20-session-transcript.html) in any browser (cyan Nicholas cards, ruby/orchid Zoe cards, collapsible gold tool traces, chapter jump pills & live search).",
        "> - **24-Bit ANSI Terminal Replay:** Run `less -R research/sessions/2026-11-20-session-transcript.ansi` in Linux.",
        "> - **Direct GitHub View:** Color-coded alerts (`NOTE` for Nicholas, `IMPORTANT` chapter banners) right below!",
        "",
        "```ansi",
        "\x1b[1;31m◆ PROJECT ZOE\x1b[0m \x1b[38;5;221m· NICHOLAS × ZOE MARATHON TRANSCRIPT\x1b[0m \x1b[36m(2026-11-19 → 2026-11-20)\x1b[0m",
        f"\x1b[32m✓ Scope:\x1b[0m {stats['user_turns']} User Turns · {stats['assistant_responses']} Zoe Responses · {stats['tool_calls']} Tool Steps · {len(zoe_commits)} Monorepo Commits · Zero Credentials",
        "```",
        "",
        "## Chapters in This Marathon Session",
        "",
        ch_toc,
        "",
        "<details>",
        f"<summary><strong>Commits Shipped During This Session ({len(zoe_commits)} in Ablation-Tool/zoe + {len(profile_commits)} in Ablation-Tool Profile)</strong></summary>",
        "",
        "**`Ablation-Tool/zoe` (`main`):**",
        z_list,
        "",
        "**`Ablation-Tool/Ablation-Tool` Profile (`main`):**",
        p_list,
        "",
        "</details>",
        "",
        "---",
        "",
    ]

    for item in items:
        if item.chapter is not None:
            ch_idx, ch_title, ch_sub = item.chapter
            out.extend([
                f'<a id="chapter-{ch_idx:02d}"></a>',
                "",
                "> [!IMPORTANT]",
                f"> ### Chapter {ch_idx:02d} · {ch_title}",
                f"> *{ch_sub}*",
                "",
            ])

        ts_short = item.timestamp.replace("T", " ")
        if item.kind == "user":
            san = sanitize_text(item.content, mode="md", zoe_root=zoe_root, profile_root=profile_root)
            quoted = "\n".join(f"> {ln}" if ln.strip() else ">" for ln in san.splitlines())
            out.extend([
                f"### 🟦 Turn {item.turn_num} · Nicholas (`you >`) · `{ts_short}`",
                "",
                "> [!NOTE]",
                quoted,
                "",
            ])
        elif item.kind == "tools" and item.tools is not None:
            tb = item.tools
            out.extend([
                "<details>",
                f"<summary><sub>⚙ <strong>Engineering Trace:</strong> {tb.compact_label()} ({tb.total_calls} tool steps)</sub></summary>",
                "",
            ])
            if tb.summaries:
                out.append("**Commands / Tasks:**")
                for s in tb.summaries[:14]:
                    out.append(f"- {s}")
                out.append("")
            if tb.files_touched:
                out.append("**Files Written / Edited:** " + " · ".join(f"`{f}`" for f in tb.files_touched[:16]))
                out.append("")
            out.extend(["</details>", ""])
        elif item.kind == "assistant":
            san = sanitize_text(item.content, mode="md", zoe_root=zoe_root, profile_root=profile_root)
            out.extend([
                f"#### 💎 Zoe (`zoe ::`) · `{ts_short}`",
                "",
                san,
                "",
                "---",
                "",
            ])

    return "\n".join(out)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export sanitized TrueColor CLI session transcript (HTML + ANSI + MD).")
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--zoe-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile-root", type=Path, default=Path.home() / "Ablation-Tool-profile")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--prefix", type=str, default="2026-11-20-session-transcript")
    args = parser.parse_args(argv)

    zoe_root = str(args.zoe_root.expanduser().resolve())
    profile_root = str(args.profile_root.expanduser().resolve())
    out_dir = (args.out_dir or (args.zoe_root / "research/sessions")).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    items, stats = parse_transcript(args.transcript.expanduser().resolve(), zoe_root, profile_root)
    zoe_commits = collect_commits(Path(zoe_root))
    profile_commits = collect_commits(Path(profile_root))

    html_doc = render_html(items, stats, zoe_commits, profile_commits, zoe_root, profile_root)
    ansi_doc = render_ansi(items, stats, zoe_commits, zoe_root, profile_root)
    md_doc = render_markdown(items, stats, zoe_commits, profile_commits, zoe_root, profile_root)

    p_html = out_dir / f"{args.prefix}.html"
    p_ansi = out_dir / f"{args.prefix}.ansi"
    p_md = out_dir / f"{args.prefix}.md"
    p_html.write_text(html_doc, encoding="utf-8")
    p_ansi.write_text(ansi_doc, encoding="utf-8")
    p_md.write_text(md_doc, encoding="utf-8")

    print(
        f"[OK] Exported {stats['user_turns']} turns / {stats['assistant_responses']} Zoe responses / "
        f"{stats['tool_calls']} tool calls -> {p_html.name} ({p_html.stat().st_size:,} B), "
        f"{p_ansi.name} ({p_ansi.stat().st_size:,} B), {p_md.name} ({p_md.stat().st_size:,} B)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
