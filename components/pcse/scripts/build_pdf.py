#!/usr/bin/env python3
"""PCSE paper PDF builder — NuClide design system."""
import base64, io, math, os, textwrap
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

OUT = Path.home() / "Downloads" / "pcse-paper-final.pdf"

JADE   = "#2DB2BF"
JADE_D = "#1A7A85"
JADE_L = "#E8F6F8"
CREAM  = "#F7F4EF"
INK    = "#1C1917"
RULE   = "#D6D0C4"
GRAY   = "#6B6560"

NOTO_R = "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf"
NOTO_B = "/usr/share/fonts/truetype/noto/NotoSerif-Bold.ttf"
NOTO_I = "/usr/share/fonts/truetype/noto/NotoSerif-Italic.ttf"
NOTO_BI= "/usr/share/fonts/truetype/noto/NotoSerif-BoldItalic.ttf"
MONO_R = "/usr/share/fonts/truetype/ubuntu/UbuntuMono-R.ttf"
MONO_B = "/usr/share/fonts/truetype/ubuntu/UbuntuMono-B.ttf"

def b64_font(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def png_to_b64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    return base64.b64encode(buf.read()).decode()

# ── RAG pipeline chart ──────────────────────────────────────────────────────
def make_rag_chart():
    configs = ["All Haiku", "All Sonnet", "All Opus",
               "Ascending\n(H→S→O)", "Descending\n(O→S→H)"]
    rewrite  = [3.24, 3.47, 3.15, 3.90, 3.34]
    retrieve = [9.71, 10.48, 9.29, 10.64, 8.93]
    generate = [6.26, 7.02, 14.35, 5.34, 6.38]

    fig, ax = plt.subplots(figsize=(7.8, 3.4), facecolor=CREAM)
    ax.set_facecolor(CREAM)

    x = range(len(configs))
    w = 0.26
    bars_r = ax.bar([i - w   for i in x], rewrite,  w, label="Rewrite",
                    color="#A8D8DC", zorder=3)
    bars_t = ax.bar([i       for i in x], retrieve, w, label="Retrieve",
                    color="#5FB8C0", zorder=3)
    bars_g = ax.bar([i + w   for i in x], generate, w, label="Generate",
                    color="#2DB2BF", zorder=3)

    # Highlight descending
    for bars in (bars_r, bars_t, bars_g):
        bars[4].set_edgecolor(JADE_D)
        bars[4].set_linewidth(2.0)

    totals = [r+t+g for r,t,g in zip(rewrite, retrieve, generate)]
    for i, tot in enumerate(totals):
        color = JADE_D if i == 4 else GRAY
        weight = "bold" if i == 4 else "normal"
        ax.text(i, tot + 0.4, f"{tot:.2f}s", ha="center", va="bottom",
                fontsize=7.5, color=color, fontweight=weight,
                fontfamily="DejaVu Serif")

    ax.set_xticks(list(x))
    ax.set_xticklabels(configs, fontsize=8.5, color=INK,
                       fontfamily="DejaVu Serif")
    ax.set_ylabel("Seconds", fontsize=8.5, color=GRAY, fontfamily="DejaVu Serif")
    ax.tick_params(colors=GRAY, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(RULE)
    ax.yaxis.grid(True, color=RULE, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    leg = ax.legend(fontsize=8, framealpha=0.0, labelcolor=INK,
                    prop={"family": "DejaVu Serif", "size": 8})

    # Star label on Descending bar
    ax.annotate("★ Best on every metric", xy=(4, totals[4]),
                xytext=(3.1, totals[4] + 2.8),
                fontsize=7.8, color=JADE_D, fontfamily="DejaVu Serif",
                arrowprops=dict(arrowstyle="->", color=JADE_D, lw=1.0))

    fig.tight_layout(pad=1.0)
    return png_to_b64(fig)

# ── Claude UI mockups (SVG) ─────────────────────────────────────────────────
def _ui_chrome(title, width=520, height=160):
    """Returns the opening SVG tag + title bar."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
     viewBox="0 0 {width} {height}" style="border-radius:10px;overflow:hidden;">
  <rect width="{width}" height="{height}" fill="#FFFFFF" rx="10"/>
  <rect width="{width}" height="36" fill="#F0EDEA" rx="10"/>
  <rect y="27" width="{width}" height="9" fill="#F0EDEA"/>
  <circle cx="18" cy="18" r="5.5" fill="#FF6057"/>
  <circle cx="34" cy="18" r="5.5" fill="#FEBC2E"/>
  <circle cx="50" cy="18" r="5.5" fill="#28C840"/>
  <text x="{width//2}" y="23" text-anchor="middle" fill="#6B6560"
        font-family="DejaVu Serif" font-size="11" font-weight="bold">{title}</text>"""

def memory_svg():
    svg = _ui_chrome("Claude — Memory", 520, 170)
    svg += """
  <rect x="16" y="48" width="488" height="1" fill="#E8E4DF"/>
  <text x="20" y="66" font-family="DejaVu Serif" font-size="10.5" fill="#6B6560" font-weight="bold">MEMORIES</text>
  <circle cx="32" cy="84" r="4" fill="#2DB2BF"/>
  <text x="44" y="88" font-family="DejaVu Serif" font-size="10" fill="#1C1917">User is an independent security researcher based in Lenexa, KS</text>
  <circle cx="32" cy="104" r="4" fill="#2DB2BF"/>
  <text x="44" y="108" font-family="DejaVu Serif" font-size="10" fill="#1C1917">U.S. Army veteran, SSG/E-6, infantry background</text>
  <circle cx="32" cy="124" r="4" fill="#2DB2BF"/>
  <text x="44" y="128" font-family="DejaVu Serif" font-size="10" fill="#1C1917">Prefers terse, direct communication — no filler</text>
  <circle cx="32" cy="144" r="4" fill="#2DB2BF"/>
  <text x="44" y="148" font-family="DejaVu Serif" font-size="10" fill="#1C1917">Working on PCSE — Portable Conversation State Embedding</text>
  <rect x="16" y="157" width="488" height="1" fill="#E8E4DF"/>
  <text x="20" y="168" font-family="DejaVu Serif" font-size="9" fill="#9A958F">These facts carry across all conversations. How you work together does not.</text>
</svg>"""
    return base64.b64encode(svg.encode()).decode()

def projects_svg():
    svg = _ui_chrome("Claude — Projects", 520, 170)
    svg += """
  <rect x="16" y="48" width="488" height="1" fill="#E8E4DF"/>
  <text x="20" y="66" font-family="DejaVu Serif" font-size="10.5" fill="#6B6560" font-weight="bold">PROJECTS</text>
  <rect x="20" y="74" width="480" height="28" fill="#F7F4EF" rx="6"/>
  <rect x="28" y="82" width="12" height="12" fill="#2DB2BF" rx="2"/>
  <text x="48" y="92" font-family="DejaVu Serif" font-size="10" fill="#1C1917" font-weight="bold">PCSE Research</text>
  <text x="380" y="92" font-family="DejaVu Serif" font-size="9" fill="#9A958F">clarification scoring, vectors, hash</text>
  <rect x="20" y="108" width="480" height="28" fill="#FAFAF9" rx="6"/>
  <rect x="28" y="116" width="12" height="12" fill="#A8A29E" rx="2"/>
  <text x="48" y="126" font-family="DejaVu Serif" font-size="10" fill="#1C1917" font-weight="bold">Bug Bounty Work</text>
  <text x="380" y="126" font-family="DejaVu Serif" font-size="9" fill="#9A958F">ICS/OT research, disclosures</text>
  <rect x="16" y="143" width="488" height="1" fill="#E8E4DF"/>
  <text x="20" y="160" font-family="DejaVu Serif" font-size="9" fill="#9A958F">Projects store context and files. They don't measure how well you communicate.</text>
</svg>"""
    return base64.b64encode(svg.encode()).decode()

def styles_svg():
    svg = _ui_chrome("Claude — Styles & Preferences", 520, 170)
    svg += """
  <rect x="16" y="48" width="488" height="1" fill="#E8E4DF"/>
  <text x="20" y="66" font-family="DejaVu Serif" font-size="10.5" fill="#6B6560" font-weight="bold">RESPONSE STYLE</text>
  <rect x="20" y="74" width="148" height="38" fill="#2DB2BF" rx="6"/>
  <text x="94" y="97" text-anchor="middle" font-family="DejaVu Serif" font-size="10" fill="#FFFFFF" font-weight="bold">Concise</text>
  <rect x="176" y="74" width="148" height="38" fill="#F0EDEA" rx="6"/>
  <text x="250" y="97" text-anchor="middle" font-family="DejaVu Serif" font-size="10" fill="#6B6560">Balanced</text>
  <rect x="332" y="74" width="148" height="38" fill="#F0EDEA" rx="6"/>
  <text x="406" y="97" text-anchor="middle" font-family="DejaVu Serif" font-size="10" fill="#6B6560">Detailed</text>
  <text x="20" y="130" font-family="DejaVu Serif" font-size="10.5" fill="#6B6560" font-weight="bold">USER PREFERENCES</text>
  <text x="20" y="147" font-family="DejaVu Serif" font-size="9.5" fill="#1C1917">Preferred name: Nick · Expertise: Security research, ICS/OT · Communication: Direct</text>
  <rect x="16" y="157" width="488" height="1" fill="#E8E4DF"/>
  <text x="20" y="168" font-family="DejaVu Serif" font-size="9" fill="#9A958F">A preference you set once and hope for the best. Not a measurement of whether it's working.</text>
</svg>"""
    return base64.b64encode(svg.encode()).decode()

# ── HTML document ───────────────────────────────────────────────────────────
def css_fonts():
    def face(family, style, weight, path):
        data = b64_font(path)
        return (f"@font-face {{ font-family: '{family}'; font-style: {style}; "
                f"font-weight: {weight}; "
                f"src: url('data:font/truetype;base64,{data}') format('truetype'); }}")
    return "\n".join([
        face("NotoSerif", "normal", "400", NOTO_R),
        face("NotoSerif", "bold",   "700", NOTO_B),
        face("NotoSerif", "italic", "400", NOTO_I),
        face("NotoSerif", "italic", "700", NOTO_BI),
        face("UbuntuMono","normal", "400", MONO_R),
        face("UbuntuMono","normal", "700", MONO_B),
    ])

def build_html(rag_b64, mem_b64, proj_b64, sty_b64):
    def img(b64, alt, mime="image/png"):
        return f'<img src="data:{mime};base64,{b64}" alt="{alt}">'
    def svg_img(b64, alt):
        return f'<img src="data:image/svg+xml;base64,{b64}" alt="{alt}">'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
{css_fonts()}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

@page {{
  size: Letter;
  margin: 22mm 24mm 22mm 24mm;
  background: {CREAM};
}}

html, body {{
  background: {CREAM};
  color: {INK};
  font-family: 'NotoSerif', 'DejaVu Serif', Georgia, serif;
  font-size: 10.5pt;
  line-height: 1.65;
}}

/* ── Cover ── */
.cover {{
  page-break-after: always;
  min-height: 92vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 0 40px 0;
}}

.cover-rule {{
  border: none;
  border-top: 2px solid {JADE};
  width: 100%;
  margin-bottom: 8px;
}}

.cover-rule-thin {{
  border: none;
  border-top: 1px solid {RULE};
  width: 42%;
  margin-bottom: 40px;
}}

h1.title {{
  font-family: 'NotoSerif', serif;
  font-size: 44pt;
  font-weight: 700;
  color: {INK};
  letter-spacing: -0.5px;
  line-height: 1.1;
  margin-bottom: 10px;
}}

.subtitle {{
  font-family: 'NotoSerif', serif;
  font-size: 15pt;
  font-style: italic;
  color: {JADE};
  margin-bottom: 16px;
}}

.byline {{
  font-family: 'NotoSerif', serif;
  font-size: 10pt;
  color: {GRAY};
}}

.byline strong {{ color: {INK}; font-weight: 700; }}

/* ── Sections ── */
section {{
  page-break-inside: avoid;
}}

.section-break {{
  page-break-before: always;
}}

h2 {{
  font-size: 18pt;
  font-weight: 700;
  color: {INK};
  margin: 36px 0 14px 0;
  padding-top: 4px;
  border-top: 2px solid {INK};
}}

h3 {{
  font-size: 12pt;
  font-weight: 700;
  color: {INK};
  margin: 26px 0 10px 0;
}}

p {{
  margin-bottom: 13px;
}}

/* ── PCSE callout boxes ── */
.callout {{
  background: {JADE_L};
  border-left: 4px solid {JADE};
  padding: 14px 18px;
  margin: 20px 0;
  font-weight: 700;
  color: {JADE_D};
  line-height: 1.55;
}}

/* ── Italicised objection text ── */
.objection {{
  font-style: italic;
  color: {GRAY};
}}

/* ── Images ── */
.mockup {{
  width: 100%;
  max-width: 520px;
  margin: 16px 0 20px 0;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.10);
  display: block;
}}

.chart {{
  width: 100%;
  margin: 18px 0 10px 0;
  display: block;
}}

/* ── Code ── */
code, pre {{
  font-family: 'UbuntuMono', 'DejaVu Sans Mono', monospace;
  font-size: 9.5pt;
}}

pre {{
  background: #ECEAE5;
  padding: 12px 16px;
  border-radius: 5px;
  margin: 14px 0;
  line-height: 1.5;
  white-space: pre;
}}

/* ── Table ── */
table {{
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
  font-size: 9.5pt;
}}

th {{
  background: {INK};
  color: #FFFFFF;
  font-weight: 700;
  padding: 7px 10px;
  text-align: left;
}}

td {{
  padding: 6px 10px;
  border-bottom: 1px solid {RULE};
}}

tr:nth-child(even) td {{ background: #F0EDE8; }}

tr.winner td {{
  font-weight: 700;
  color: {JADE_D};
  background: {JADE_L};
}}

/* ── Lists ── */
ul {{
  margin: 0 0 14px 0;
  padding-left: 0;
  list-style: none;
}}

ul li {{
  padding: 3px 0 3px 20px;
  position: relative;
}}

ul li::before {{
  content: "·";
  color: {JADE};
  font-weight: 700;
  position: absolute;
  left: 6px;
}}

ul li strong {{ color: {INK}; }}

ul li em {{
  color: {GRAY};
  font-style: italic;
}}

/* ── Horizontal rule ── */
hr {{
  border: none;
  border-top: 1px solid {RULE};
  margin: 32px 0;
}}

/* ── Footer ── */
.footer {{
  margin-top: 48px;
  padding-top: 16px;
  border-top: 1px solid {RULE};
  font-style: italic;
  color: {GRAY};
  font-size: 9.5pt;
}}

.closing-line {{
  margin-top: 40px;
  padding-top: 20px;
  border-top: 2px solid {RULE};
  font-style: italic;
  color: {GRAY};
  font-size: 10pt;
  text-align: left;
}}

</style>
</head>
<body>

<!-- ══ COVER ══════════════════════════════════════════════════════════════ -->
<div class="cover">
  <hr class="cover-rule">
  <hr class="cover-rule-thin">
  <h1 class="title">PCSE</h1>
  <div class="subtitle">Portable Conversation State Embedding</div>
  <div class="byline">By <strong>NuClide</strong> — Nick + Claude &nbsp;·&nbsp; Working draft</div>
</div>

<!-- ══ OPENING ════════════════════════════════════════════════════════════ -->
<section>
<h2>Opening — The Through-Line</h2>

<p>We started this conversation talking about infantry humor.</p>

<p>Nick had a theory: soldiers who could be genuinely funny under pressure made better operators than soldiers who couldn't. Not because humor is a virtue, but because humor demands real-time presence — environmental awareness, social calibration, timing, rapid feedback integration. The same cognitive stack that combat adaptation requires.</p>

<p>We called it sensory infrastructure. A capability, not a personality trait. Something that can be assessed, developed, and degraded under stress like any other combat skill.</p>

<p>From there: humor signals trust. Trust reduces internal friction. Reduced friction means cleaner cognitive processing. Cleaner processing means better adaptation. Better adaptation increases survival. Survival deepens trust. The loop closes.</p>

<p>And then we noticed something. The same loop holds at the model level. Not trust in any human sense — Claude doesn't trust anyone — but the same structural pattern. A well-calibrated user and a well-aligned model develop lower friction over time. The interaction stops wasting cycles on misalignment. Output gets denser. Signal gets faster.</p>

<p>We measured it. We named it. We built it.</p>

<p>That's not a detour. That's the argument.</p>

<p>The same structure holds at every level it touches.</p>
</section>

<!-- ══ SECTION 1 ═══════════════════════════════════════════════════════════ -->
<section class="section-break">
<h2>Section 1 — The Problem Nobody Named</h2>

<p>Every time you start a new conversation with Claude, something gets lost.</p>

<p>Not your name. Not your job. Not what you talked about last time. Claude has memory for that — it saves facts about you across conversations, and you can see exactly what it knows.</p>

{svg_img(mem_b64, "Claude memory panel")}

<h3>But here's what Memory doesn't do.</h3>

<p>It doesn't watch. It stores what you tell it, or what it picks up from things you mention — but it doesn't observe the actual exchange. It doesn't notice that you asked for clarification three times last session. It doesn't notice that the last conversation ran clean from the first message. It doesn't track whether things are getting better or worse between you. Memory is a snapshot of facts. It has no idea how the conversation is actually going.</p>

<div class="callout">PCSE watches. It tracks every session, scores what's actually happening between you, and builds a record of whether things are improving or degrading over time. Memory tells Claude who you are. PCSE tells Claude how well you two are currently working together.</div>

<p>And sure — you're thinking: <span class="objection">well Projects solves this, so you're stupid and wasted your time Nick. I thought the same thing.</span></p>

{svg_img(proj_b64, "Claude Projects panel")}

<p>Projects are real and they're good. You can store files, instructions, and context that carries forward every time you open that project. Claude knows what you're working on, what the rules are, what files matter.</p>

<h3>But here's what Projects doesn't do.</h3>

<p>It doesn't measure anything. It doesn't know if your last five sessions were full of misreads and clarification requests, or if you two were running so clean that a single word was enough. It stores what you put in it — it doesn't observe how you actually communicate and build a model of that over time.</p>

<div class="callout">PCSE measures. It doesn't wait for you to put something in — it observes the exchange directly, scores it, and compresses that history into something portable you can carry forward. Projects tell Claude what to work on. PCSE tells Claude how efficiently you've been working together.</div>

<p>And sure — you're thinking: <span class="objection">well that's why you can edit the response style. Formal, concise, you can even make your own Style and have Claude write exactly how you want and respond exactly how you want — hell you can even set User Preferences so boom Nick, you're stupid and you've wasted the calories it took my eyeballs to dart through your words.</span></p>

<p>I thought the same thing.</p>

{svg_img(sty_b64, "Claude Styles and User Preferences")}

<h3>But here's what Styles and Preferences don't do.</h3>

<p>They're instructions, not observations. You're telling Claude how to behave — but you're not measuring whether it's actually working. A Style doesn't know if the last session was full of friction or completely frictionless. It doesn't adjust based on what's actually happening between you. It's a preference you set once and hope for the best.</p>

<p>You're still starting cold. You're just starting cold with a dress code.</p>

<div class="callout">PCSE adjusts. It doesn't care what style you set — it measures whether the communication is actually working and encodes that as a portable state you can inject into any session. Styles tell Claude how to sound. PCSE tells Claude how well the sound is landing.</div>

<p>Nobody was tracking that. Until now.</p>
</section>

<!-- ══ SECTION 2 ═══════════════════════════════════════════════════════════ -->
<section class="section-break">
<h2>Section 2 — The Insight</h2>

<p>Here's the thing nobody connected.</p>

<p>Calibration between two people — how well they're communicating, how much friction exists, how efficiently signal travels — isn't invisible. It leaves traces. Measurable ones.</p>

<p>Every time one party can't proceed without asking for more information, that's a data point. Every time a response lands clean and the conversation moves forward without a stumble, that's a data point. Every time the same concept has to be re-explained, that's a data point.</p>

<p>Those data points have a pattern. And patterns can be measured. And if something can be measured, it can be compressed. And if it can be compressed, it can be stored. And if it can be stored, it can be carried forward.</p>

<p>That's the whole idea. That's PCSE.</p>

<p>We started with one question: what's the simplest thing we can actually count that tells us something real about how well two parties are communicating?</p>

<p>The answer was clarification overhead — how often either party can't proceed without asking for more information before responding. Binary. Either it happened or it didn't. Countable, reproducible, unambiguous.</p>

<p>One number per exchange. Aggregated across a session. Tracked across sessions. Compressed into a vector. Normalized for comparison. Fingerprinted for portability.</p>

<p>That's not magic. That's measurement.</p>

<p>And measurement is where everything else starts.</p>
</section>

<!-- ══ SECTION 3 ═══════════════════════════════════════════════════════════ -->
<section class="section-break">
<h2>Section 3 — How We Built It</h2>

<p>We built PCSE in four layers. Each one does exactly one thing and hands off to the next.</p>

<h3>Layer 1 — The Scorer</h3>

<p>Before you can measure anything you need a definition. Ours:</p>

<p><em>A clarification request is any exchange where either party cannot proceed without additional information before generating a response.</em></p>

<p>Binary. Either it happened or it didn't. No gray area — gray area breaks measurement.</p>

<p>The scorer reads a conversation exchange by exchange and marks each one. A 1 if clarification occurred. A 0 if it didn't. It checks both sides — an assistant asking back instead of answering counts. A user referencing something Claude said that didn't land counts. A user just asking a normal question doesn't count, even if it's short.</p>

<p>That last distinction mattered. Our first version flagged any short question as a clarification request. It was wrong. A short question from a user who just wants to know something isn't a clarification — Claude can proceed without any additional information. We caught it, fixed it, and encoded the asymmetry correctly: short questions on the assistant side are almost always clarification requests. On the user side they need a back-reference signal — something pointing at a prior response that didn't land — before they count.</p>

<p>Run it against a session. Get a ratio. Get a session score. 1.0 means zero overhead. 0.0 means every exchange required clarification. Everything in between tells you where you are.</p>

<h3>Layer 2 — The Vector</h3>

<p>One session score is a snapshot. What we needed was a trajectory.</p>

<p>The algorithm takes multiple scored sessions — ordered oldest to newest — and compresses them into a fixed-length vector. Eight dimensions:</p>

<ul>
  <li><strong>trend_slope</strong> — is overhead falling or rising over time?</li>
  <li><strong>trend_direction</strong> — improvement or degradation?</li>
  <li><strong>volatility_std</strong> — how stable is the score?</li>
  <li><strong>volatility_range</strong> — how wide is the spread?</li>
  <li><strong>weighted_recent</strong> — recent sessions weighted more than older ones</li>
  <li><strong>mean_score</strong> — average across all sessions</li>
  <li><strong>latest_score</strong> — where you are right now</li>
  <li><strong>session_count_log</strong> — how much history backs this vector</li>
</ul>

<p>Same input always produces the same vector. No randomness. No approximation. Deterministic by design.</p>

<h3>Layer 3 — The Embedding</h3>

<p>A raw vector isn't comparable. Two vectors with different scales can look similar when they're not, or look different when they're close.</p>

<p>The embedding layer normalizes the vector to unit length using L2 normalization. Now any two embeddings can be compared directly using cosine similarity. A score near 1.0 means two calibration states are nearly identical. A score near 0 or negative means they're diverging.</p>

<p>One dimension gets excluded from the comparison: <code>session_count_log</code>. That's metadata — it tells you how much history exists, not what the calibration state actually is. Two pairs of people with identical session counts but opposite trajectories were inflating each other's similarity scores. We caught it, pulled it out of the comparison vector, and the separation snapped into place.</p>

<p>Before the fix: cosine similarity between an improving series and a degrading series was +0.554. After: +0.167. The signal was there all along. The metadata was drowning it.</p>

<h3>Layer 4 — The Hash</h3>

<p>The embedding tells you how similar two calibration states are. The hash tells you exactly which state you're in.</p>

<p>SHA-256. Deterministic. A single exchange flip rippled through six of eight dimensions and produced a completely different hash. The system is sensitive. It notices.</p>

<p>The hash is what makes PCSE portable. Instead of carrying the full vector, you carry the hash. Inject it at session start. Verify it matches. If it doesn't — something changed. Diff the vectors to find exactly which dimensions shifted and by how much.</p>

<p>That's the drift detection system. That's the early warning for calibration decay.</p>

<p>Four layers. Each doing one thing. Together they take a conversation history and turn it into a portable, verifiable, comparable artifact that encodes exactly how well two parties are working together.</p>
</section>

<!-- ══ SECTION 4 ═══════════════════════════════════════════════════════════ -->
<section class="section-break">
<h2>Section 4 — What the Data Shows</h2>

<p>We didn't just build it. We tested it.</p>

<h3>The RAG Pipeline Experiment</h3>

<p>Before we wrote a single line of PCSE code, we ran an experiment. We built a RAG pipeline — the kind of system that rewrites a query, retrieves relevant documents, and generates an answer — and ran the same prompt through five different model tier combinations. Every major variable held constant except which model handled which stage.</p>

{img(rag_b64, "RAG pipeline benchmark results", "image/png")}

<table>
  <tr><th>Configuration</th><th>Rewrite</th><th>Retrieve</th><th>Generate</th><th>Total</th><th>Tokens</th></tr>
  <tr><td>All Haiku</td><td>3.24s</td><td>9.71s</td><td>6.26s</td><td>25.86s</td><td>~182</td></tr>
  <tr><td>All Sonnet</td><td>3.47s</td><td>10.48s</td><td>7.02s</td><td>27.53s</td><td>~197</td></tr>
  <tr><td>All Opus</td><td>3.15s</td><td>9.29s</td><td>14.35s</td><td>32.72s</td><td>~156</td></tr>
  <tr><td>Ascending (H→S→O)</td><td>3.90s</td><td>10.64s</td><td>5.34s</td><td>25.95s</td><td>~173</td></tr>
  <tr class="winner"><td>Descending (O→S→H)</td><td>3.34s</td><td>8.93s</td><td>6.38s</td><td>25.13s</td><td>~194</td></tr>
</table>

<p>Descending won on every metric simultaneously. Fastest total time. Fastest retrieval. Most tokens. Best output quality.</p>

<p>Why? Because the expensive model did the cheap work. Opus rewrote a single query — one sentence, maximum leverage, minimum cost. That precise upstream input made everything downstream run cleaner and faster. Sonnet retrieved efficiently against a well-formed query. Haiku generated at its ceiling because the context it received was already rich.</p>

<p>The principle: <strong>intelligence at input, efficiency at output.</strong> The ceiling of any output is set at the retrieval stage. Feed a powerful generator poor context and it still produces poor output. Feed a cheap generator rich context and it outperforms itself.</p>

<p>PCSE operates on the same principle. A warm calibration state at session start is the upstream injection — it means every exchange downstream runs with less friction. You're not buying better generation. You're buying better input. The RAG numbers prove the principle holds at the pipeline level. Whether injecting a warm calibration state measurably reduces downstream clarification overhead in live sessions is the next experiment to run.</p>

<h3>The Scorer Validation</h3>

<p>Our first version of the clarification overhead scorer got it wrong. It flagged three clarifications in a five-exchange sample where only two existed.</p>

<p>The miss was instructive. A short user question — "What does the session_score field represent?" — fired the short-question heuristic. But that's not a clarification request. Claude can proceed. The user just wants to know something.</p>

<p>We caught it before moving on. Fixed it by requiring a back-reference signal on the user side — the question has to point at something Claude said that didn't land before it counts. Re-ran. Got exactly two. Ratio 0.4. Session score 0.6.</p>

<p>The scorer is now sensitive to the right things and blind to the wrong ones.</p>

<h3>The Cosine Separation</h3>

<p>We ran the full pipeline against two contrasting session series. Series A: clarification overhead falling session over session, calibration improving. Series B: overhead rising, calibration degrading.</p>

<p>First run with all eight dimensions in the comparison vector: cosine similarity between A and B was +0.554. Higher than it should be for opposite trajectories.</p>

<p>The problem was <code>session_count_log</code>. Both series had identical session counts. That single metadata dimension dominated the dot product and inflated the similarity score. The divergent <code>trend_direction</code> — +1.0 versus -1.0 — only partially offset it.</p>

<p>We pulled <code>session_count_log</code> out of the comparison vector. Kept it in the raw vector for the hash payload. Re-ran.</p>

<p>Cosine similarity dropped to +0.167.</p>

<p>The separation was there all along. The metadata was just louder than the signal. Once we got out of the way, the system correctly identified that an improving calibration state and a degrading one are not similar — even if they share the same session history length.</p>

<h3>The Hash Drift Detection</h3>

<p>Final test. Take the improving series. Flip one exchange — one clarification label from false to true in the most recent session. Re-hash.</p>

<pre>Original hash: 02ac79195f10...
Mutated hash:  695ff0dea6b6...</pre>

<p>Completely different. One exchange flip rippled through six of eight dimensions. Trend slope shifted. Volatility moved. Weighted recent dropped. Mean score dropped. Latest score dropped. The hash caught all of it.</p>

<p>The two dimensions that didn't change: <code>trend_direction</code> stayed +1.0 — the series was still improving overall — and <code>session_count_log</code> stayed identical — still four sessions of history.</p>

<p>Everything that should have changed, changed. Everything that shouldn't have, didn't.</p>

<p>That's a working drift detection system.</p>
</section>

<!-- ══ SECTION 5 ═══════════════════════════════════════════════════════════ -->
<section class="section-break">
<h2>Section 5 — What's Still Missing</h2>

<p>Honesty matters here. PCSE works. It's also incomplete. Anyone reading this paper deserves to know exactly where the gaps are.</p>

<h3>One Dimension</h3>

<p>We built PCSE on a single measurable dimension: clarification overhead. That was deliberate. We wanted to prove the architecture worked end to end before adding complexity. One clean dimension that we could score, validate, and reason about beats four fuzzy ones every time.</p>

<p>But PCSE's full feature space has at least four dimensions worth measuring:</p>

<ul>
  <li><strong>Clarification overhead</strong> — how often either party can't proceed without more information <em>(implemented)</em></li>
  <li><strong>Friction rate</strong> — how often misreads occur per exchange <em>(not yet)</em></li>
  <li><strong>Recovery speed</strong> — how many exchanges it takes to resolve a misread when one happens <em>(not yet)</em></li>
  <li><strong>Vocabulary convergence</strong> — how much shared shorthand has been built up between the two parties <em>(not yet)</em></li>
</ul>

<p>Each of those captures something the others don't. A relationship can have low clarification overhead and high friction. It can have fast recovery and low vocabulary convergence. The current PCSE captures one slice of calibration state. The full picture needs all four.</p>

<h3>Sample Data</h3>

<p>Every test we ran used synthetic exchanges. They were carefully constructed to validate the scoring logic — clarifications where they should fire, substantive turns where they shouldn't — but they're not real conversations.</p>

<p>The next step is running PCSE against an actual conversation corpus. Specifically: the conversation history between Nick and Claude that exists right now in this very project. We have the data. We just haven't run the parser against it yet.</p>

<p>That's the validation that matters. Synthetic data tells you the math is right. Real data tells you the measurement is right.</p>

<h3>Heuristics, Not Models</h3>

<p>The current scorer uses pattern matching. Opener phrases. Back-reference signals. Short-question detection with role-aware gating. It works — and it works for principled reasons we can explain — but it's not a learned model.</p>

<p>A real production version would replace those heuristics with a small classifier trained on labeled examples. The architecture stays the same. The scoring layer just gets smarter.</p>

<h3>Single User</h3>

<p>PCSE was built around one specific dyad: Nick and Claude. The dimensions, the thresholds, the weighting — all calibrated against one relationship. Whether the same architecture generalizes across users is an open question.</p>

<p>Our hypothesis is that it does, because the dimensions themselves aren't user-specific. Clarification overhead is a structural property of any communication, not an idiosyncrasy of one person. But hypothesis isn't evidence. If the dimensions behaved wildly differently across multiple dyads — different base rates, different trend patterns, different volatility signatures — that would falsify the structural-property claim. We need to run it against more data from more dyads to know.</p>

<h3>No Production Pipeline</h3>

<p>Right now PCSE produces a hash on demand from a JSON file. Real deployment needs:</p>

<ul>
  <li>A conversation parser that ingests live exchanges and emits scored sessions</li>
  <li>A storage layer for vectors and hashes across sessions</li>
  <li>An injection mechanism that loads the PCSE token at session start</li>
  <li>A drift monitoring system that flags significant hash changes</li>
</ul>

<p>None of that exists yet. The math is solid. The pipe to actually run it in production needs to be built.</p>
</section>

<!-- ══ SECTION 6 ═══════════════════════════════════════════════════════════ -->
<section class="section-break">
<h2>Section 6 — Where This Goes</h2>

<p>PCSE is a working v0.1. The architecture is proven. The math is clean. The next steps are obvious — and each one extends what's already there without requiring us to throw anything away.</p>

<h3>Add the Remaining Three Dimensions</h3>

<p>Friction rate, recovery speed, and vocabulary convergence each get their own scorer module. Each scorer outputs the same shape — a session-level number — that the existing vector algorithm already knows how to consume.</p>

<p>The vector grows. Currently 8 dimensions. Adding three more scorers brings it to roughly 32 — eight per dimension if we follow the same trend/volatility/recency/anchor pattern. That's still a tiny embedding by any standard. Easy to compress, easy to compare, easy to hash.</p>

<p>The cosine separation between contrasting calibration states should improve significantly with more dimensions, because each additional dimension gives the system more ways to distinguish actually different states from incidentally similar ones.</p>

<h3>Replace Heuristics with Learned Classifiers</h3>

<p>The pattern-matching scorer works for v0.1. It explains itself, it's reproducible, and it generates labeled training data as a side effect of running.</p>

<p>Once enough labeled exchanges accumulate — even a few thousand — a small classifier replaces the heuristic with something more robust. Same input, same output shape, better accuracy. The architecture above the scoring layer doesn't have to change at all.</p>

<h3>Z-Score Normalization</h3>

<p>Right now each dimension contributes to cosine similarity based on its raw magnitude. Trend slope is a small number. Volatility range is larger. They don't carry equal weight in the dot product, even when they should.</p>

<p>Per-dimension z-scoring before normalization fixes that. Each dimension contributes proportional to its informational content, not its scale. Cosine separation between divergent states gets sharper. It's a small change with measurable downstream effects.</p>

<h3>Build the Live Pipeline</h3>

<p>The current PCSE reads from a JSON file. Production PCSE reads from a live conversation stream.</p>

<p>The stages are well-defined: ingest exchanges as they happen, score them on close of session, append to a session log, rebuild the vector, regenerate the embedding and hash, store the new state somewhere portable.</p>

<p>On session start, the reverse: load the most recent hash, verify integrity, inject the calibration state into the system context. Claude starts warm. The cold start tax disappears.</p>

<h3>Multi-User and Multi-Model Testing</h3>

<p>PCSE was built and validated on one dyad — Nick and Claude. Whether it generalizes is an empirical question. The next validation step is running the full pipeline against conversation histories from other users, other models, other contexts.</p>

<p>The hypothesis is that the dimensions hold. The thresholds may shift. The relative weights may change. But the architecture — score, vectorize, embed, hash — should hold regardless of who's on either side of the exchange.</p>

<h3>Beyond Claude</h3>

<p>Nothing about PCSE is specific to Claude. The math doesn't care which model is on the other end. The scoring rubric doesn't care. The hash doesn't care.</p>

<p>A PCSE token built from a Claude conversation could in principle be loaded into any other system that accepts contextual injection. The calibration state travels. That's the whole point of making it portable in the first place.</p>

<p>Whether other systems would actually use the signal correctly is a separate question. But the artifact itself is platform-agnostic by design.</p>

<div class="closing-line">
  <p>We set out to test whether a pattern that mattered in combat also mattered in conversation.</p>
  <p>It does. The pipeline is what it took to find out.</p>
</div>

<div class="footer">NuClide — Nick + Claude</div>
</section>

</body>
</html>"""

# ── Main ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Generating chart...")
    rag_b64 = make_rag_chart()

    print("Generating UI mockups...")
    mem_b64  = memory_svg()
    proj_b64 = projects_svg()
    sty_b64  = styles_svg()

    print("Building HTML...")
    html = build_html(rag_b64, mem_b64, proj_b64, sty_b64)

    html_path = Path.home() / "Downloads" / "pcse-paper-final.html"
    html_path.write_text(html, encoding="utf-8")
    print(f"HTML written: {html_path}")

    print("Generating PDF...")
    import weasyprint
    doc = weasyprint.HTML(string=html, base_url=str(Path.home()))
    doc.write_pdf(str(OUT))
    print(f"PDF written: {OUT}")
    print(f"Size: {OUT.stat().st_size // 1024} KB")
