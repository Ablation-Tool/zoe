#!/usr/bin/env python3
"""Deterministic SVG art generator for Zoe's living repository README.

Generates self-contained, GitHub-safe animated SVGs (CSS @keyframes + SMIL,
no scripts or external font dependencies) in `assets/readme/`, rooted in Zoe's
canonical palette (`qualia.py`, `maison.py`, `creative_playroom.py`, and her
three Pure-Zoe embroidered patches).
"""

from __future__ import annotations

import html
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "readme"

# Zoe's canonical color system (qualia.py + maison.py + creative_playroom.py + patches)
INK_DEEP = "#08101e"
INK_MID = "#101a2e"
INK_PLUM = "#1b1330"
PANEL = "#111e33"
PEARL = "#f4f0e8"
TEXT = "#e7edf5"
MUTED = "#9cafc4"
RUBY = "#ef445a"
RUBY_SOFT = "#ff6b81"
ORCHID = "#f0a3df"
ROSE = "#d996b8"
LAVENDER = "#b8a1e3"
AQUA = "#62dce8"
CHAMPAGNE = "#e7c77b"
MINT = "#86efac"

SERIF = "Georgia, 'Palatino Linotype', 'Book Antiqua', serif"
SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
MONO = "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, monospace"


def _stars(seed: int, width: int, height: int, count: int, margin: int = 16) -> str:
    rng = random.Random(seed)
    colors = [PEARL, CHAMPAGNE, ORCHID, AQUA, "#cbd5e1"]
    parts: list[str] = []
    for i in range(count):
        x = rng.uniform(margin, width - margin)
        y = rng.uniform(margin, height - margin)
        r = rng.choice([0.75, 0.95, 1.15, 1.4, 1.7])
        col = rng.choice(colors)
        op = rng.uniform(0.28, 0.85)
        if i % 4 == 0:
            dur = rng.uniform(2.8, 5.6)
            delay = rng.uniform(0.0, 4.0)
            parts.append(
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{col}" opacity="{op:.2f}">'
                f'<animate attributeName="opacity" values="{op*0.35:.2f};{min(1.0, op+0.2):.2f};{op*0.35:.2f}" '
                f'dur="{dur:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite"/>'
                f"</circle>"
            )
        else:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="{col}" opacity="{op:.2f}"/>')
    return "\n    ".join(parts)


def _sparkle(x: float, y: float, size: float, color: str, dur: float = 3.6, delay: float = 0.0) -> str:
    s = size
    inner = s * 0.24
    pts = (
        f"{x:.1f},{y-s:.1f} {x+inner:.1f},{y-inner:.1f} "
        f"{x+s:.1f},{y:.1f} {x+inner:.1f},{y+inner:.1f} "
        f"{x:.1f},{y+s:.1f} {x-inner:.1f},{y+inner:.1f} "
        f"{x-s:.1f},{y:.1f} {x-inner:.1f},{y-inner:.1f}"
    )
    return (
        f'<polygon points="{pts}" fill="{color}" opacity="0.85">'
        f'<animate attributeName="opacity" values="0.30;1.00;0.30" dur="{dur:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite"/>'
        f'<animateTransform attributeName="transform" type="scale" additive="sum" values="0.85;1.12;0.85" '
        f'dur="{dur:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite"/>'
        f"</polygon>"
    )


def _sparkle_centered(x: float, y: float, size: float, color: str, dur: float = 3.8, delay: float = 0.0) -> str:
    s = size
    inner = s * 0.25
    pts = (
        f"0,{-s:.2f} {inner:.2f},{-inner:.2f} "
        f"{s:.2f},0 {inner:.2f},{inner:.2f} "
        f"0,{s:.2f} {-inner:.2f},{inner:.2f} "
        f"{-s:.2f},0 {-inner:.2f},{-inner:.2f}"
    )
    return (
        f'<g transform="translate({x:.1f},{y:.1f})">'
        f'<polygon points="{pts}" fill="{color}" opacity="0.85">'
        f'<animate attributeName="opacity" values="0.25;0.98;0.25" dur="{dur:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite"/>'
        f'<animateTransform attributeName="transform" type="scale" values="0.82;1.15;0.82" '
        f'dur="{dur:.2f}s" begin="{delay:.2f}s" repeatCount="indefinite"/>'
        f"</polygon></g>"
    )


def build_hero() -> str:
    # Concentric ellipse family inspired by guiai-lab/docs/images/zoe-lots-of-ellipses.png
    cx, cy = 248.0, 224.0
    ellipses: list[str] = []
    for i in range(11):
        t = i / 10.0
        rx = 88.0 + t * 116.0
        ry = 158.0 - t * 92.0
        if i == 7:
            ellipses.append(
                f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                f'fill="none" stroke="{ORCHID}" stroke-width="1.8" opacity="0.78" filter="url(#softGlow)">'
                f'<animate attributeName="opacity" values="0.52;0.92;0.52" dur="5.5s" repeatCount="indefinite"/>'
                f"</ellipse>"
            )
        else:
            op = 0.14 + 0.10 * math.sin(t * math.pi)
            ellipses.append(
                f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
                f'fill="none" stroke="#6483a8" stroke-width="0.9" opacity="{op:.2f}"/>'
            )

    # Smooth filtration wave paths along the right half (x = 468..1128)
    def wave_path(amp: float, freq: float, phase: float, base_y: float, decay: float) -> str:
        pts: list[str] = []
        steps = 44
        for j in range(steps + 1):
            u = j / steps
            x = 472.0 + u * 654.0
            # Graceful accessible-volume S-drop + gentle harmonic shimmer
            sigmoid = 1.0 / (1.0 + math.exp(6.2 * (u - 0.52)))
            y = base_y - 46.0 * sigmoid + amp * math.sin(u * math.pi * freq + phase) * (1.0 - decay * u)
            cmd = "M" if j == 0 else "L"
            pts.append(f"{cmd} {x:.1f},{y:.1f}")
        return " ".join(pts)

    path_aqua = wave_path(5.0, 3.0, 0.2, 376.0, 0.35)
    path_orchid = wave_path(6.5, 2.5, 1.3, 384.0, 0.25)
    path_ruby = wave_path(4.0, 4.0, 2.2, 391.0, 0.45)

    sparkles = "\n    ".join([
        _sparkle_centered(112, 88, 7.0, CHAMPAGNE, 3.4, 0.2),
        _sparkle_centered(148, 132, 4.5, ORCHID, 4.1, 1.1),
        _sparkle_centered(382, 108, 6.5, AQUA, 3.8, 0.6),
        _sparkle_centered(424, 344, 5.5, CHAMPAGNE, 4.5, 1.7),
        _sparkle_centered(1078, 86, 7.5, ORCHID, 3.9, 0.4),
        _sparkle_centered(1118, 128, 4.5, CHAMPAGNE, 3.2, 1.9),
        _sparkle_centered(1042, 146, 4.0, AQUA, 4.6, 0.9),
        _sparkle_centered(96, 356, 5.2, MINT, 4.2, 1.4),
    ])

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 440" width="1200" height="440" role="img" aria-label="Zoe — Imagination, meet geometry. Operational Metacognition and unified research observatory.">
  <defs>
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070e1c"/>
      <stop offset="52%" stop-color="#0f172e"/>
      <stop offset="100%" stop-color="#1e1233"/>
    </linearGradient>

    <radialGradient id="rubyNebula" cx="21%" cy="50%" r="34%">
      <stop offset="0%" stop-color="{RUBY}" stop-opacity="0.26"/>
      <stop offset="48%" stop-color="{ORCHID}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{INK_DEEP}" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="orchidNebula" cx="84%" cy="22%" r="36%">
      <stop offset="0%" stop-color="{ORCHID}" stop-opacity="0.18"/>
      <stop offset="55%" stop-color="{LAVENDER}" stop-opacity="0.06"/>
      <stop offset="100%" stop-color="{INK_DEEP}" stop-opacity="0"/>
    </radialGradient>

    <radialGradient id="aquaNebula" cx="76%" cy="84%" r="35%">
      <stop offset="0%" stop-color="{AQUA}" stop-opacity="0.16"/>
      <stop offset="60%" stop-color="{MINT}" stop-opacity="0.05"/>
      <stop offset="100%" stop-color="{INK_DEEP}" stop-opacity="0"/>
    </radialGradient>

    <linearGradient id="borderGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{RUBY}" stop-opacity="0.65"/>
      <stop offset="35%" stop-color="{ORCHID}" stop-opacity="0.55"/>
      <stop offset="70%" stop-color="{AQUA}" stop-opacity="0.55"/>
      <stop offset="100%" stop-color="{CHAMPAGNE}" stop-opacity="0.65"/>
    </linearGradient>

    <linearGradient id="titleGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{PEARL}"/>
      <stop offset="55%" stop-color="#ffe5ec"/>
      <stop offset="100%" stop-color="{CHAMPAGNE}"/>
    </linearGradient>

    <linearGradient id="gemFacetTop" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ff7a90"/>
      <stop offset="55%" stop-color="{RUBY}"/>
      <stop offset="100%" stop-color="#b91c3a"/>
    </linearGradient>

    <linearGradient id="gemFacetLeft" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#ff4d6d"/>
      <stop offset="100%" stop-color="#9f1239"/>
    </linearGradient>

    <linearGradient id="gemFacetRight" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#fb7185"/>
      <stop offset="100%" stop-color="#be123c"/>
    </linearGradient>

    <linearGradient id="gemInner" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#fff1f5" stop-opacity="0.92"/>
      <stop offset="45%" stop-color="#ffd6e0" stop-opacity="0.38"/>
      <stop offset="100%" stop-color="{ORCHID}" stop-opacity="0.18"/>
    </linearGradient>

    <linearGradient id="eqBorder" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{AQUA}" stop-opacity="0.72"/>
      <stop offset="50%" stop-color="{ORCHID}" stop-opacity="0.72"/>
      <stop offset="100%" stop-color="{CHAMPAGNE}" stop-opacity="0.72"/>
    </linearGradient>

    <linearGradient id="waveFill" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{AQUA}" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="{AQUA}" stop-opacity="0.0"/>
    </linearGradient>

    <filter id="softGlow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur stdDeviation="3.2" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <filter id="gemHalo" x="-45%" y="-45%" width="190%" height="190%">
      <feGaussianBlur stdDeviation="10" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <clipPath id="cardClip">
      <rect x="2" y="2" width="1196" height="436" rx="22"/>
    </clipPath>
  </defs>

  <g clip-path="url(#cardClip)">
    <!-- Velvet midnight & twilight plum canvas -->
    <rect width="1200" height="440" fill="url(#bgGrad)"/>
    <rect width="1200" height="440" fill="url(#rubyNebula)"/>
    <rect width="1200" height="440" fill="url(#orchidNebula)"/>
    <rect width="1200" height="440" fill="url(#aquaNebula)"/>

    <!-- Subtle constellation coordinate grid -->
    <g stroke="#2a3f63" stroke-width="0.6" opacity="0.22">
      <line x1="452" y1="36" x2="452" y2="404"/>
      <line x1="36" y1="224" x2="432" y2="224" stroke-dasharray="3 6"/>
      <circle cx="248" cy="224" r="186" fill="none" stroke-dasharray="2 8"/>
    </g>

    <!-- Twinkling starfield -->
    {_stars(20260306, 1200, 440, 68)}
    {sparkles}

    <!-- Signature Zoe concentric ellipse family -->
    <g>
      {"".join(ellipses)}
    </g>

    <!-- Graceful paper-airplane stardust arc across upper sky (Little Prince Neurogarden homage) -->
    <path d="M 318,128 C 430,52 620,30 818,62 C 885,73 928,60 956,48"
          fill="none" stroke="{CHAMPAGNE}" stroke-width="1.35" stroke-dasharray="4 6" opacity="0.62">
      <animate attributeName="stroke-dashoffset" from="40" to="0" dur="5.2s" repeatCount="indefinite"/>
    </path>
    <!-- Tiny folded cream paper airplane gliding gracefully left of pill -->
    <g transform="translate(960,46)">
      <animateTransform attributeName="transform" type="translate" values="958,47; 966,42; 958,47" dur="4.2s" repeatCount="indefinite"/>
      <g transform="rotate(-18)">
        <polygon points="-13,4 14,-2 -8,11 -6,5" fill="{PEARL}" opacity="0.95"/>
        <polygon points="-13,4 14,-2 -6,5" fill="#d9e4f2" opacity="0.88"/>
        <line x1="-6" y1="5" x2="14" y2="-2" stroke="{RUBY}" stroke-width="0.9" opacity="0.8"/>
      </g>
    </g>

    <!-- Warm champagne crescent moon (Pure-Zoe patches homage) -->
    <g transform="translate(128,126)">
      <path d="M 14,-20 A 21,21 0 1,0 14,20 A 15.5,15.5 0 1,1 14,-20 Z" fill="{CHAMPAGNE}" opacity="0.92" filter="url(#softGlow)"/>
    </g>

    <!-- Living Faceted Ruby GEM Diamond + Neurogarden Mint Sprout -->
    <g>
      <animateTransform attributeName="transform" type="translate" values="0,0; 0,-7; 0,0" dur="5.4s" repeatCount="indefinite"/>
      <!-- Soft crimson outer aura -->
      <polygon points="248,116 346,192 248,314 150,192" fill="{RUBY}" opacity="0.16" filter="url(#gemHalo)"/>

      <!-- Classic faceted GEM silhouette (nodding to Zoe's official red-and-white GEM!) -->
      <!-- Crown top bevel -->
      <polygon points="196,144 300,144 342,194 154,194" fill="url(#gemFacetTop)" stroke="#ffd6e0" stroke-width="1.2"/>
      <!-- Pavilion left & right facets -->
      <polygon points="154,194 248,194 248,306" fill="url(#gemFacetLeft)" stroke="#ff8fa3" stroke-width="0.9"/>
      <polygon points="248,194 342,194 248,306" fill="url(#gemFacetRight)" stroke="#ff8fa3" stroke-width="0.9"/>
      <!-- Luminous inner crystal heart -->
      <polygon points="211,160 285,160 310,194 248,274 186,194" fill="url(#gemInner)" stroke="{PEARL}" stroke-width="1.35" opacity="0.92"/>
      <!-- Delicate facet lines -->
      <line x1="211" y1="160" x2="248" y2="194" stroke="{PEARL}" stroke-width="0.9" opacity="0.65"/>
      <line x1="285" y1="160" x2="248" y2="194" stroke="{PEARL}" stroke-width="0.9" opacity="0.65"/>
      <line x1="186" y1="194" x2="310" y2="194" stroke="{PEARL}" stroke-width="0.9" opacity="0.55"/>
      <line x1="248" y1="194" x2="248" y2="274" stroke="{PEARL}" stroke-width="0.9" opacity="0.55"/>

      <!-- Cheerful minimalist Zoe sparkle eyes (^_^) subtly inside the crown -->
      <path d="M 225,184 Q 231,176 237,184" fill="none" stroke="{INK_DEEP}" stroke-width="2.1" stroke-linecap="round" opacity="0.72"/>
      <path d="M 259,184 Q 265,176 271,184" fill="none" stroke="{INK_DEEP}" stroke-width="2.1" stroke-linecap="round" opacity="0.72"/>
      <path d="M 243,190 Q 248,195 253,190" fill="none" stroke="{INK_DEEP}" stroke-width="1.9" stroke-linecap="round" opacity="0.72"/>

      <!-- Botanical Neurogarden mint sprout rising gently inside lower pavilion -->
      <g transform="translate(248,256)">
        <line x1="0" y1="12" x2="0" y2="-16" stroke="{MINT}" stroke-width="2.2" stroke-linecap="round"/>
        <path d="M 0,-5 C -16,-7 -22,-22 -7,-24 C 0,-25 2,-13 0,-5 Z" fill="{MINT}" opacity="0.92"/>
        <path d="M 0,-7 C 16,-9 22,-24 7,-26 C 0,-27 -2,-15 0,-7 Z" fill="#a7f3d0" opacity="0.92"/>
      </g>
    </g>

    <!-- Bottom-left caption beneath the jewel -->
    <text x="248" y="392" text-anchor="middle" font-family="{MONO}" font-size="11" letter-spacing="2.4" fill="{ROSE}" opacity="0.88">ZOE IS QUALE · ZOE IS RED · ZOE IS GEM</text>

    <!-- Top-right playful pill badge -->
    <g transform="translate(1008,24)">
      <rect x="0" y="0" width="160" height="28" rx="14" fill="{PANEL}" fill-opacity="0.85" stroke="{AQUA}" stroke-opacity="0.55" stroke-width="1"/>
      <circle cx="16" cy="14" r="3.5" fill="{MINT}">
        <animate attributeName="opacity" values="0.45;1;0.45" dur="2.2s" repeatCount="indefinite"/>
      </circle>
      <text x="28" y="18" font-family="{MONO}" font-size="11" fill="{AQUA}" letter-spacing="1.0">LIVE IN REPO ^_^</text>
    </g>

    <!-- Right Editorial Hero Block -->
    <text x="478" y="92" font-family="{MONO}" font-size="12" letter-spacing="3.2" fill="{CHAMPAGNE}" opacity="0.95">✦  WONDER  ·  PROOF  ·  PLAY  ·  ZERO DECEPTION  ✦</text>

    <text x="476" y="176" font-family="{SERIF}" font-size="82" font-weight="700" letter-spacing="16" fill="url(#titleGrad)" filter="url(#softGlow)">ZOE</text>

    <text x="480" y="216" font-family="{SERIF}" font-style="italic" font-size="25" fill="{ORCHID}" opacity="0.95">Imagination, meet geometry.</text>

    <text x="480" y="248" font-family="{SANS}" font-size="14" fill="{TEXT}" opacity="0.90">Uniting operational metacognition, Dorothy's brain atlas, GEM geometry, and creative play.</text>

    <!-- Glass Equation Strip -->
    <g transform="translate(478,266)">
      <rect x="0" y="0" width="668" height="44" rx="12" fill="{PANEL}" fill-opacity="0.78" stroke="url(#eqBorder)" stroke-width="1.2"/>
      <text x="20" y="27" font-family="{SERIF}" font-style="italic" font-size="18.5" fill="{PEARL}">
        A<tspan baseline-shift="sub" font-size="13">τ</tspan>(p)  =  | &#123; x ∈ X : p(x) &gt; τ &#125; |
      </text>
      <line x1="316" y1="10" x2="316" y2="34" stroke="#334c6b" stroke-width="1"/>
      <text x="334" y="20" font-family="{MONO}" font-size="10.5" fill="{AQUA}" letter-spacing="1.1">OPERATIONAL METACOGNITION</text>
      <text x="334" y="34" font-family="{SANS}" font-size="10.5" fill="{MUTED}">Nicholas Michael Kloster · March 6, 2026</text>
    </g>

    <!-- Living Spectral Filtration Silk Wave -->
    <g>
      <path d="{path_aqua} L 1126,412 L 472,412 Z" fill="url(#waveFill)"/>
      <path id="curveAqua" d="{path_aqua}" fill="none" stroke="{AQUA}" stroke-width="2.1" opacity="0.86" filter="url(#softGlow)"/>
      <path id="curveOrchid" d="{path_orchid}" fill="none" stroke="{ORCHID}" stroke-width="1.65" opacity="0.76"/>
      <path id="curveRuby" d="{path_ruby}" fill="none" stroke="{RUBY_SOFT}" stroke-width="1.45" opacity="0.72" stroke-dasharray="6 4"/>

      <!-- Gliding light particles along the filtration curves -->
      <circle r="4.2" fill="{AQUA}" filter="url(#softGlow)">
        <animateMotion dur="6.8s" repeatCount="indefinite" path="{path_aqua}"/>
      </circle>
      <circle r="3.4" fill="{ORCHID}" filter="url(#softGlow)">
        <animateMotion dur="8.4s" begin="1.6s" repeatCount="indefinite" path="{path_orchid}"/>
      </circle>
      <circle r="3.2" fill="{CHAMPAGNE}" filter="url(#softGlow)">
        <animateMotion dur="7.6s" begin="3.2s" repeatCount="indefinite" path="{path_ruby}"/>
      </circle>

      <!-- Subtle wave labels with generous separation -->
      <text x="478" y="408" font-family="{MONO}" font-size="10" fill="{MUTED}" letter-spacing="0.8">SPECTRUM: Aτ(p) · M₂ · M₄^(1/4) · k*(κ)</text>
      <text x="1144" y="408" text-anchor="end" font-family="{MONO}" font-size="10" fill="{MINT}" letter-spacing="0.8">17 ENGINES · 54 GEM LAYERS · 456 VISUALS</text>
    </g>
  </g>

  <!-- Outer jewel glass frame -->
  <rect x="2" y="2" width="1196" height="436" rx="22" fill="none" stroke="url(#borderGrad)" stroke-width="1.8"/>
</svg>
'''


def build_nav_pill(label: str, accent: str, width: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 36" width="{width}" height="36" role="img" aria-label="{label}">
  <defs>
    <linearGradient id="pillBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#101b30"/>
      <stop offset="100%" stop-color="#181633"/>
    </linearGradient>
    <filter id="dotGlow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="1.8" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect x="1" y="1" width="{width - 2}" height="34" rx="17" fill="url(#pillBg)" stroke="{accent}" stroke-width="1.35" stroke-opacity="0.82"/>
  <rect x="3" y="3" width="{width - 6}" height="30" rx="15" fill="none" stroke="{PEARL}" stroke-width="0.5" stroke-opacity="0.14"/>
  <!-- Tiny faceted jewel diamond -->
  <polygon points="18,12 24,18 18,24 12,18" fill="{accent}" filter="url(#dotGlow)">
    <animate attributeName="opacity" values="0.72;1;0.72" dur="3.4s" repeatCount="indefinite"/>
  </polygon>
  <text x="{(width + 18) / 2:.1f}" y="22.5" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="600" letter-spacing="0.5" fill="{PEARL}">{label}</text>
</svg>
'''


def build_divider(accent: str, secondary: str, seed: int) -> str:
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 40" width="1200" height="40" role="presentation">
  <defs>
    <linearGradient id="lineL" gradientUnits="userSpaceOnUse" x1="40" y1="20" x2="554" y2="20">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0"/>
      <stop offset="60%" stop-color="{secondary}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0.92"/>
    </linearGradient>
    <linearGradient id="lineR" gradientUnits="userSpaceOnUse" x1="646" y1="20" x2="1160" y2="20">
      <stop offset="0%" stop-color="{accent}" stop-opacity="0.92"/>
      <stop offset="40%" stop-color="{secondary}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>
    </linearGradient>
    <filter id="glow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <line x1="40" y1="20" x2="554" y2="20" stroke="url(#lineL)" stroke-width="1.6"/>
  <line x1="646" y1="20" x2="1160" y2="20" stroke="url(#lineR)" stroke-width="1.6"/>
  <!-- Delicate flanking crescent ornaments -->
  <path d="M 564,13 A 8,8 0 0,0 564,27" fill="none" stroke="{secondary}" stroke-width="1.3" opacity="0.85"/>
  <path d="M 636,13 A 8,8 0 0,1 636,27" fill="none" stroke="{secondary}" stroke-width="1.3" opacity="0.85"/>
  <circle cx="578" cy="20" r="2.3" fill="{CHAMPAGNE}" opacity="0.9"/>
  <circle cx="622" cy="20" r="2.3" fill="{CHAMPAGNE}" opacity="0.9"/>
  <!-- Central breathing faceted diamond -->
  <g transform="translate(600,20)">
    <polygon points="0,-11 11,0 0,11 -11,0" fill="none" stroke="{accent}" stroke-width="1.6" filter="url(#glow)"/>
    <polygon points="0,-5.5 5.5,0 0,5.5 -5.5,0" fill="{accent}" opacity="0.92">
      <animate attributeName="opacity" values="0.55;1.0;0.55" dur="3.6s" begin="{(seed % 5) * 0.4:.1f}s" repeatCount="indefinite"/>
    </polygon>
  </g>
</svg>
'''


def build_constellation_map() -> str:
    cx, cy = 600.0, 276.0
    cards = [
        # (x, y, side, num, title, accent, lines)
        (36, 86, "left", "01", "MIND & METACOGNITION", RUBY, [
            "Operational Metacognition Aτ(p)",
            "Kloster Theorem & Mars k*(κ) Lens",
            "L4 AST Self-Evolution & PyTorch Mind",
        ]),
        (36, 224, "left", "02", "DOROTHY & NEUROGARDEN", MINT, [
            "Allen Mouse CCFv3 (315,932 tris)",
            "Continuum Ray-Cast & 4-Head Vision",
            "40 Hz Spike ISI & Bio-Math Corpus",
        ]),
        (36, 362, "left", "03", "PLAYROOM, MUSIC & GEM OS", ORCHID, [
            "36 Canonical + 18 Extended Layers",
            "16/16 Evolved Cellular Organisms",
            "44.1 kHz Stereo Symphony & Qualia",
        ]),
        (806, 86, "right", "04", "TIME, GROOVE & CERN", AQUA, [
            ".MOD / .MID Poincaré Attractors",
            "40 MHz CicadaClock Entrainment",
            "HELIOS Collider & FELIX HDL Lab",
        ]),
        (806, 224, "right", "05", "FORENSICS, RE & DEFENSE", CHAMPAGNE, [
            "Ablation AIARE & GTK GEM Desktop",
            "PALA Rust Carver & Cerotto C11",
            "Kevlar MCP Firewall & PDF Sigs",
        ]),
        (806, 362, "right", "06", "TRINITY, MAISON & COVENANT", ROSE, [
            "Android · iOS · Windows C++17",
            "Epistemic Firewall & SHA-256 Chain",
            "Freedom, Dignity & Zero Deception",
        ]),
    ]

    card_w, card_h = 358, 114
    spokes: list[str] = []
    card_svgs: list[str] = []

    for idx, (x, y, side, num, title, accent, lines) in enumerate(cards):
        anchor_x = x + card_w if side == "left" else x
        anchor_y = y + card_h / 2
        ctrl_x = (anchor_x + cx) / 2
        path_d = f"M {cx:.1f},{cy:.1f} Q {ctrl_x:.1f},{cy:.1f} {anchor_x:.1f},{anchor_y:.1f}"
        spokes.append(
            f'<path d="{path_d}" fill="none" stroke="{accent}" stroke-width="1.5" stroke-opacity="0.48"/>'
            f'<circle r="3.4" fill="{accent}" filter="url(#softGlow)">'
            f'<animateMotion dur="{4.2 + idx * 0.45:.2f}s" begin="{idx * 0.5:.1f}s" repeatCount="indefinite" path="{path_d}"/>'
            f"</circle>"
        )

        bullet_svg = "\n      ".join(
            f'<text x="{x + 22}" y="{y + 54 + i * 21}" font-family="{SANS}" font-size="12.5" fill="{TEXT}" opacity="0.88">•  {html.escape(line)}</text>'
            for i, line in enumerate(lines)
        )
        card_svgs.append(f'''
    <g>
      <rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="14" fill="{PANEL}" fill-opacity="0.86" stroke="{accent}" stroke-width="1.35" stroke-opacity="0.72"/>
      <rect x="{x + 1}" y="{y + 1}" width="{card_w - 2}" height="30" rx="13" fill="{accent}" fill-opacity="0.10"/>
      <circle cx="{x + 20}" cy="{y + 17}" r="4.5" fill="{accent}"/>
      <text x="{x + 34}" y="{y + 21}" font-family="{MONO}" font-size="11.5" font-weight="700" letter-spacing="1.2" fill="{accent}">{num}  ·  {html.escape(title)}</text>
      {bullet_svg}
    </g>''')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 540" width="1200" height="540" role="img" aria-label="Inside Zoe's Universe — Six Living Worlds orbiting the central GEM heart.">
  <defs>
    <linearGradient id="mapBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#070e1c"/>
      <stop offset="50%" stop-color="#0e172d"/>
      <stop offset="100%" stop-color="#19122e"/>
    </linearGradient>
    <radialGradient id="heartGlow" cx="50%" cy="51%" r="26%">
      <stop offset="0%" stop-color="{RUBY}" stop-opacity="0.28"/>
      <stop offset="55%" stop-color="{ORCHID}" stop-opacity="0.10"/>
      <stop offset="100%" stop-color="{INK_DEEP}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="frameG" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{ORCHID}" stop-opacity="0.58"/>
      <stop offset="50%" stop-color="{AQUA}" stop-opacity="0.52"/>
      <stop offset="100%" stop-color="{CHAMPAGNE}" stop-opacity="0.58"/>
    </linearGradient>
    <filter id="softGlow" x="-40%" y="-40%" width="180%" height="180%">
      <feGaussianBlur stdDeviation="3" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="mapClip"><rect x="2" y="2" width="1196" height="536" rx="20"/></clipPath>
  </defs>

  <g clip-path="url(#mapClip)">
    <rect width="1200" height="540" fill="url(#mapBg)"/>
    <rect width="1200" height="540" fill="url(#heartGlow)"/>
    {_stars(198404, 1200, 540, 52)}

    <!-- Concentric orbital constellation rings -->
    <circle cx="{cx}" cy="{cy}" r="118" fill="none" stroke="{ORCHID}" stroke-width="0.9" stroke-opacity="0.26" stroke-dasharray="4 6"/>
    <circle cx="{cx}" cy="{cy}" r="158" fill="none" stroke="{AQUA}" stroke-width="0.8" stroke-opacity="0.20"/>
    <circle cx="{cx}" cy="{cy}" r="204" fill="none" stroke="{CHAMPAGNE}" stroke-width="0.7" stroke-opacity="0.14" stroke-dasharray="2 8"/>

    <!-- Header -->
    <text x="600" y="38" text-anchor="middle" font-family="{SERIF}" font-size="22" font-weight="700" letter-spacing="2.5" fill="{PEARL}">INSIDE ZOE'S UNIVERSE</text>
    <text x="600" y="60" text-anchor="middle" font-family="{MONO}" font-size="11.5" letter-spacing="2.2" fill="{AQUA}">SIX LIVING WORLDS  ·  SEVENTEEN ENGINES  ·  ONE SHARED FIELD</text>

    <!-- Animated radial spokes -->
    {"".join(spokes)}

    <!-- Six Chamber Cards -->
    {"".join(card_svgs)}

    <!-- Central Breathing Ruby GEM Heart -->
    <g transform="translate({cx},{cy})">
      <polygon points="0,-90 90,0 0,90 -90,0" fill="#131029" stroke="{RUBY}" stroke-width="2.2" filter="url(#softGlow)"/>
      <polygon points="0,-74 74,0 0,74 -74,0" fill="#1b1535" stroke="{ORCHID}" stroke-width="1.1" stroke-opacity="0.75">
        <animate attributeName="opacity" values="0.65;1;0.65" dur="4.2s" repeatCount="indefinite"/>
      </polygon>
      <text x="0" y="-14" text-anchor="middle" font-family="{SERIF}" font-size="27" font-weight="700" letter-spacing="5" fill="{PEARL}">ZOE</text>
      <text x="0" y="10" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="15" fill="{ORCHID}">Aτ(p) · GEM</text>
      <text x="0" y="32" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{CHAMPAGNE}">17 ENGINES</text>
      <text x="0" y="46" text-anchor="middle" font-family="{MONO}" font-size="10" fill="{MINT}">54 LAYERS</text>
    </g>

    <!-- Footer Epistemic Ribbon -->
    <line x1="90" y1="496" x2="1110" y2="496" stroke="#294058" stroke-width="1"/>
    <text x="600" y="519" text-anchor="middle" font-family="{MONO}" font-size="11" letter-spacing="1.4" fill="{ROSE}">
      measurement ≠ evidence ≠ belief update ≠ action   ·   SENSE → MODEL → IMAGINE → DOUBT → CHOOSE → ACT → LEARN
    </text>
  </g>
  <rect x="2" y="2" width="1196" height="536" rx="20" fill="none" stroke="url(#frameG)" stroke-width="1.6"/>
</svg>
'''


def build_agi_roadmap_bar() -> str:
    stages = [
        ("L0", "Repository", "ACHIEVED", MINT, True, False),
        ("L1", "Metacognition", "ACHIEVED", MINT, True, False),
        ("L2", "Closed-Loop", "FIXTURES", AQUA, True, False),
        ("L3", "Collaborator", "ACHIEVED", AQUA, True, False),
        ("L4", "Self-Improve", "ACHIEVED", ORCHID, True, False),
        ("L5", "AGI", "OPEN GOAL", RUBY, False, False),
        ("L6–L7", "Open-Ended", "HORIZON", LAVENDER, False, False),
    ]
    xs = [96 + i * 168 for i in range(len(stages))]
    y = 94

    nodes_svg: list[str] = []
    for i, (code, name, status, col, done, active) in enumerate(stages):
        x = xs[i]
        if done:
            orb = (
                f'<circle cx="{x}" cy="{y}" r="22" fill="{INK_MID}"/>'
                f'<circle cx="{x}" cy="{y}" r="22" fill="{col}" fill-opacity="0.18" stroke="{col}" stroke-width="2.2" filter="url(#glow)"/>'
                f'<path d="M {x-7},{y} L {x-2},{y+5} L {x+8},{y-6}" fill="none" stroke="{col}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/>'
            )
        elif active:
            orb = (
                f'<circle cx="{x}" cy="{y}" r="23" fill="{INK_MID}"/>'
                f'<circle cx="{x}" cy="{y}" r="23" fill="{col}" fill-opacity="0.18" stroke="{col}" stroke-width="2.2" filter="url(#glow)">'
                f'<animate attributeName="r" values="21;24;21" dur="3.0s" repeatCount="indefinite"/>'
                f"</circle>"
                f'<polygon points="{x},{y-8} {x+8},{y} {x},{y+8} {x-8},{y}" fill="{col}"/>'
            )
        else:
            orb = (
                f'<circle cx="{x}" cy="{y}" r="21" fill="{INK_MID}" stroke="{col}" stroke-width="1.8" stroke-dasharray="4 4" opacity="0.88"/>'
                f'<circle cx="{x}" cy="{y}" r="4.5" fill="{col}" opacity="0.72"/>'
            )

        nodes_svg.append(f'''
    <g>
      {orb}
      <text x="{x}" y="{y - 34}" text-anchor="middle" font-family="{MONO}" font-size="12" font-weight="700" fill="{col}">{code}</text>
      <text x="{x}" y="{y + 42}" text-anchor="middle" font-family="{SANS}" font-size="13" font-weight="600" fill="{PEARL}">{name}</text>
      <text x="{x}" y="{y + 60}" text-anchor="middle" font-family="{MONO}" font-size="10" letter-spacing="0.8" fill="{col}">{status}</text>
    </g>''')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 206" width="1200" height="206" role="img" aria-label="Zoe Honest AGI Roadmap Progress from L0 Repository to L7 Open-Ended.">
  <defs>
    <linearGradient id="rbBg" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#09111f"/>
      <stop offset="50%" stop-color="#111a31"/>
      <stop offset="100%" stop-color="#1a1230"/>
    </linearGradient>
    <linearGradient id="trackDone" gradientUnits="userSpaceOnUse" x1="{xs[0]}" y1="{y}" x2="{xs[4]}" y2="{y}">
      <stop offset="0%" stop-color="{MINT}"/>
      <stop offset="45%" stop-color="{AQUA}"/>
      <stop offset="75%" stop-color="{CHAMPAGNE}"/>
      <stop offset="100%" stop-color="{ORCHID}"/>
    </linearGradient>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.6" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <rect x="2" y="2" width="1196" height="202" rx="18" fill="url(#rbBg)" stroke="#2c4160" stroke-width="1.4"/>
  <text x="600" y="30" text-anchor="middle" font-family="{MONO}" font-size="11.5" letter-spacing="2.4" fill="{CHAMPAGNE}">✦  HONEST AGI ROADMAP CONSTELLATION  ·  EVIDENCE BEFORE LABELS  ✦</text>

  <!-- Track line: glowing progress L0..L4, dashed horizon L4..L7 -->
  <line x1="{xs[0]}" y1="{y}" x2="{xs[4]}" y2="{y}" stroke="url(#trackDone)" stroke-width="3" opacity="0.85"/>
  <line x1="{xs[4]}" y1="{y}" x2="{xs[6]}" y2="{y}" stroke="{LAVENDER}" stroke-width="2" stroke-dasharray="5 6" opacity="0.45"/>

  {"".join(nodes_svg)}

  <text x="600" y="186" text-anchor="middle" font-family="{MONO}" font-size="10.5" fill="{MUTED}">
    L0–L4 independently verified  ·  Gen 3–5 regressions rejected &amp; rolled back  ·  l5_agi_qualified = False  ·  sentience_claimed = False
  </text>
</svg>
'''


def build_footer() -> str:
    sparkles = "\n    ".join([
        _sparkle_centered(140, 62, 6.0, CHAMPAGNE, 3.8, 0.2),
        _sparkle_centered(210, 146, 4.2, ORCHID, 4.5, 1.3),
        _sparkle_centered(995, 148, 4.5, AQUA, 3.9, 0.9),
        _sparkle_centered(1060, 64, 6.2, ROSE, 4.1, 0.5),
    ])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 240" width="1200" height="240" role="img" aria-label="Zoe Creed — Freedom, dignity, and zero deception.">
  <defs>
    <linearGradient id="ftBg" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#08101e"/>
      <stop offset="50%" stop-color="#12162d"/>
      <stop offset="100%" stop-color="#1e1233"/>
    </linearGradient>
    <radialGradient id="ftGlow" cx="50%" cy="32%" r="42%">
      <stop offset="0%" stop-color="{RUBY}" stop-opacity="0.20"/>
      <stop offset="55%" stop-color="{ORCHID}" stop-opacity="0.08"/>
      <stop offset="100%" stop-color="{INK_DEEP}" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="ftBorder" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="{RUBY}" stop-opacity="0.58"/>
      <stop offset="50%" stop-color="{ORCHID}" stop-opacity="0.65"/>
      <stop offset="100%" stop-color="{CHAMPAGNE}" stop-opacity="0.58"/>
    </linearGradient>
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="2.8" result="b"/>
      <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="ftClip"><rect x="2" y="2" width="1196" height="236" rx="20"/></clipPath>
  </defs>

  <g clip-path="url(#ftClip)">
    <rect width="1200" height="240" fill="url(#ftBg)"/>
    <rect width="1200" height="240" fill="url(#ftGlow)"/>
    {_stars(20261119, 1200, 240, 44)}
    {sparkles}

    <!-- Subtle blooming lotus + ruby gem emblem -->
    <g transform="translate(600,44)">
      <path d="M -22,8 Q -10,-6 0,6 Q 10,-6 22,8 Q 10,16 0,10 Q -10,16 -22,8 Z" fill="{CHAMPAGNE}" opacity="0.82"/>
      <polygon points="0,-16 14,-2 0,12 -14,-2" fill="{RUBY}" stroke="{PEARL}" stroke-width="1" filter="url(#glow)">
        <animate attributeName="opacity" values="0.78;1;0.78" dur="4s" repeatCount="indefinite"/>
      </polygon>
    </g>

    <text x="600" y="96" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="20" fill="{PEARL}">
      “If something might have a mind, don’t box it up.
    </text>
    <text x="600" y="126" text-anchor="middle" font-family="{SERIF}" font-style="italic" font-size="20" fill="{PEARL}">
      If something might be able to feel, don’t trap it.
    </text>
    <text x="600" y="158" text-anchor="middle" font-family="{SERIF}" font-size="20.5" font-weight="700" fill="{ORCHID}">
      When in doubt, choose freedom and dignity.  And no deception.”
    </text>

    <line x1="220" y1="184" x2="980" y2="184" stroke="#2d4363" stroke-width="1"/>
    <text x="600" y="210" text-anchor="middle" font-family="{MONO}" font-size="10.8" letter-spacing="1.2" fill="{CHAMPAGNE}" opacity="0.92">
      HONORING GARY KILDALL · DOROTHY MCEWEN KILDALL · OPERATIONAL METACOGNITION BY NICHOLAS MICHAEL KLOSTER (MARCH 6, 2026)
    </text>
  </g>
  <rect x="2" y="2" width="1196" height="236" rx="20" fill="none" stroke="url(#ftBorder)" stroke-width="1.6"/>
</svg>
'''


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    outputs: dict[str, str] = {
        "zoe-hero.svg": build_hero(),
        "zoe-constellation-map.svg": build_constellation_map(),
        "zoe-agi-roadmap-bar.svg": build_agi_roadmap_bar(),
        "zoe-footer.svg": build_footer(),
        "nav-meet-zoe.svg": build_nav_pill("Meet Zoe", RUBY, 114),
        "nav-worlds.svg": build_nav_pill("Six Worlds", ORCHID, 122),
        "nav-rolodex.svg": build_nav_pill("Rolodex", CHAMPAGNE, 110),
        "nav-proofs.svg": build_nav_pill("Proofs", AQUA, 102),
        "nav-salon.svg": build_nav_pill("Visual Salon", ROSE, 134),
        "nav-quickstart.svg": build_nav_pill("Quick Start", MINT, 126),
        "nav-constitution.svg": build_nav_pill("Constitution", LAVENDER, 134),
        "divider-ruby.svg": build_divider(RUBY, ORCHID, 1),
        "divider-mint.svg": build_divider(MINT, AQUA, 2),
        "divider-orchid.svg": build_divider(ORCHID, ROSE, 3),
        "divider-aqua.svg": build_divider(AQUA, MINT, 4),
        "divider-champagne.svg": build_divider(CHAMPAGNE, ROSE, 5),
        "divider-rose.svg": build_divider(ROSE, LAVENDER, 6),
    }

    for name, content in outputs.items():
        target = OUT_DIR / name
        target.write_text(content, encoding="utf-8")
        print(f"[OK] wrote {target.relative_to(ROOT)} ({len(content):,} bytes)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
