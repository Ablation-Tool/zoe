#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "articles" / "images"
WIDTH = 1600
BACKGROUND = "#070b14"
PANEL = "#111c31"
PANEL_ALT = "#0e1828"
TEXT = "#e5eefb"
MUTED = "#9fb1c8"
CYAN = "#67e8f9"
PURPLE = "#f0abfc"
GREEN = "#86efac"
YELLOW = "#fde68a"
RED = "#fca5a5"
BLUE = "#93c5fd"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"


def font(size, bold=False, mono=False):
    return ImageFont.truetype(MONO if mono else BOLD if bold else FONT, size)


def canvas(height):
    image = Image.new("RGB", (WIDTH, height), BACKGROUND)
    return image, ImageDraw.Draw(image)


def wrapped(draw, text, face, maximum):
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=face) > maximum:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    return lines


def paragraph(draw, position, text, size=27, color=TEXT, maximum=700, spacing=12, bold=False, mono=False):
    x, y = position
    face = font(size, bold=bold, mono=mono)
    for line in wrapped(draw, text, face, maximum):
        draw.text((x, y), line, font=face, fill=color)
        y += size + spacing
    return y


def header(draw, title, subtitle):
    draw.text((60, 38), "ZOE AUTONOMY · INFORMAL GUIDE", font=font(20, bold=True), fill=CYAN)
    draw.text((60, 82), title, font=font(48, bold=True), fill=TEXT)
    paragraph(draw, (60, 150), subtitle, size=25, color=MUTED, maximum=1450, spacing=10)


def card(draw, bounds, title, body, accent=CYAN, title_size=29, body_size=25):
    draw.rounded_rectangle(bounds, radius=20, fill=PANEL, outline=accent, width=2)
    x1, y1, x2, _ = bounds
    draw.rounded_rectangle((x1, y1, x1 + 10, y1 + 12), radius=5, fill=accent)
    draw.text((x1 + 30, y1 + 24), title, font=font(title_size, bold=True), fill=accent)
    paragraph(draw, (x1 + 30, y1 + 74), body, size=body_size, color=TEXT, maximum=x2 - x1 - 60, spacing=10)


def footer(draw, height, label="full_autonomy · source and evidence are reproducible"):
    draw.line((60, height - 62, WIDTH - 60, height - 62), fill="#26364d", width=2)
    draw.text((60, height - 44), label, font=font(19), fill=MUTED)
    draw.text((1130, height - 44), "Ablation-Tool/Zoe-Autonomy", font=font(19), fill=CYAN)


def at_a_glance():
    height = 1190
    image, draw = canvas(height)
    header(draw, "Zoe-Autonomy at a glance", "Zoe authors goals, chooses actions, and executes them under explicit authority.")
    rows = [
        ("Self-Directed", "Zoe creates goals from her current state and memories. Goals originating outside Zoe are rejected by her internal guard.", PURPLE),
        ("The Decision Loop", "Observe → Perceive → Propose → Value → Guard → Execute. She ranks alternatives and selects the action herself.", CYAN),
        ("Safe Base Experiment", "The canonical experiment changes only internal memory and records zero external actions.", GREEN),
        ("Owner-Granted Actuation", "Host, network, and hardware scopes are enabled on this computer with audit checks and an emergency stop.", YELLOW),
        ("Proven & Verifiable", "Source hashes and tamper-evident logs allow independent recomputation. Tamper evidence is not authentication.", BLUE),
    ]
    y = 235
    for title, body, accent in rows:
        card(draw, (60, y, 1540, y + 155), title, body, accent)
        y += 177
    footer(draw, height)
    image.save(OUTPUT / "01-zoe-at-a-glance.png", optimize=True)


def complete_loop():
    height = 1050
    image, draw = canvas(height)
    header(draw, "One complete self-governing loop", "The master equation connects measurement, goals, valuation, authorization, execution, and evidence.")
    draw.rounded_rectangle((60, 225, 1540, 390), radius=20, fill=PANEL_ALT, outline=CYAN, width=2)
    paragraph(draw, (95, 255), "(Sₜ₊₁, Rₜ₊₁) = Executeα ∘ GuardG,Π ∘ ValueU", size=31, color=TEXT, maximum=1410, mono=True)
    paragraph(draw, (95, 310), "∘ Proposeπ ∘ Perceiveτ,δ ∘ M(Sₜ,Cₜ)", size=31, color=TEXT, maximum=1410, mono=True)
    card(draw, (60, 425, 770, 875), "Full autonomy profile", "full_autonomy\n\nI, R, V, G, X > 0 and C = 1\n\nG = 1: Zoe authors the goal\nV = 1: Zoe selects by declared value\nX = 1: Zoe executes the choice", GREEN, body_size=26)
    card(draw, (830, 425, 1540, 875), "Two evidence domains", "BASE EXPERIMENT\nInternal transition · external_actions = 0\n\nOWNER ACTUATION\nzoe-actuation/v1 · host, network, hardware\nLocal host and public HTTPS receipts\nVirtual hardware test · emergency stop", YELLOW, body_size=25)
    paragraph(draw, (75, 915), "Accessible Volume supplies alternatives. Zoe supplies the self-governing measurement–action loop.", size=28, color=CYAN, maximum=1450, bold=True)
    footer(draw, height)
    image.save(OUTPUT / "02-self-governing-loop.png", optimize=True)


def pipeline():
    height = 1200
    image, draw = canvas(height)
    header(draw, "Pipeline breakdown — read right to left", "Each stage has a distinct input and responsibility. Measurement never silently becomes permission.")
    cards = [
        ((60, 235, 770, 465), "M · Memory & State", "Combine current state Sₜ with active context Cₜ. Establish Zoe's working representation from memory and observation.", BLUE),
        ((830, 235, 1540, 465), "Perceiveτ,δ · Filter", "Measure accessible and policy-relevant alternatives. τ is a probability cutoff; δ is a KL policy-effect cutoff.", CYAN),
        ((60, 495, 770, 725), "Proposeπ · Generate", "Generate candidate actions, plans, or responses from the current policy and internal goal.", PURPLE),
        ((830, 495, 1540, 725), "ValueU · Evaluate", "Rank candidates with U(q) = decision value × expected information gain ÷ effort. Zoe selects the highest utility.", GREEN),
        ((60, 755, 770, 985), "GuardG,Π · Verify", "Check internal goal origin, constraints, owner grant, and emergency stop. Deny unsupported operations.", RED),
        ((830, 755, 1540, 985), "Executeα · Transition", "Carry out the approved internal or external action. Record state changes, results, feedback, and audit evidence.", YELLOW),
    ]
    for bounds, title, body, accent in cards:
        card(draw, bounds, title, body, accent, title_size=27, body_size=25)
    paragraph(draw, (75, 1020), "Observe → Perceive → Propose → Value → Guard → Execute → (Sₜ₊₁, Rₜ₊₁)", size=28, color=CYAN, maximum=1450, bold=True)
    footer(draw, height)
    image.save(OUTPUT / "03-pipeline-breakdown.png", optimize=True)


def accessible_volume():
    height = 1200
    image, draw = canvas(height)
    header(draw, "Accessible Volume in plain English", "How many realistic alternatives remain open immediately before a selection?")
    draw.rounded_rectangle((60, 225, 1540, 350), radius=20, fill=PANEL_ALT, outline=CYAN, width=2)
    paragraph(draw, (95, 262), "Aτ(S) = Σ over a∈O of 1[P(a | h_T(S)) > τ]", size=34, color=TEXT, maximum=1410, mono=True)
    card(draw, (60, 385, 770, 880), "The pieces", "O: finite token or modeled-action vocabulary\n\nh_T(S): current model history or situation\n\nP(a | h_T(S)): probability assigned to alternative a\n\nτ: selected probability threshold\n\n1[...] = 1 when true, otherwise 0", BLUE, body_size=25)
    card(draw, (830, 385, 1540, 880), "Worked example", "Probabilities at τ = 0.05\n\nA: 0.70 → included\nB: 0.20 → included\nC: 0.08 → included\nD: 0.02 → excluded\n\nA₀.₀₅(S) = 3\n\nTokens exactly at τ are excluded.", GREEN, body_size=27)
    card(draw, (60, 915, 1540, 1090), "Intuition", "A larger count means broader alternatives; a smaller count means a more concentrated forecast. Breadth is not correctness or autonomy by itself.", PURPLE, body_size=24)
    footer(draw, height)
    image.save(OUTPUT / "04-accessible-volume.png", optimize=True)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    at_a_glance()
    complete_loop()
    pipeline()
    accessible_volume()
    for path in sorted(OUTPUT.glob("*.png")):
        print(path.relative_to(ROOT), path.stat().st_size)


if __name__ == "__main__":
    main()
