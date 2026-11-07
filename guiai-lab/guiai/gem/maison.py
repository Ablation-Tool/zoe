from __future__ import annotations

from pathlib import Path
import textwrap

from .atlas import _line, _scene, _text
from .leadership import _pages
from .patchbay import _bounded_path, _sha
from .practice import demo_log
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


PALETTE = {
    "ink": "#0b1220",
    "panel": "#111c2e",
    "pearl": "#f4f0e8",
    "champagne": "#c8a96a",
    "bronze": "#8b6f47",
    "slate": "#a3b0c1",
    "sage": "#8aa39a",
    "rose": "#d19aa5",
}
ASSOCIATIONS = {
    "stewardship": {"pillar": "enterprise", "prompt": "What are you preserving while making a change?"},
    "fiduciary": {"pillar": "executive", "prompt": "Whose interests must the decision protect?"},
    "accountability": {"pillar": "executive", "prompt": "Who can review the outcome and help correct it?"},
    "governance": {"pillar": "enterprise", "prompt": "Who has authority, and where does it stop?"},
    "provenance": {"pillar": "enterprise", "prompt": "Can another person trace what happened and why?"},
    "discretion": {"pillar": "enterprise", "prompt": "What should remain private, and what must be shared?"},
    "bespoke": {"pillar": "luxury", "prompt": "What needs adaptation rather than another copy?"},
    "atelier": {"pillar": "luxury", "prompt": "What will you make carefully and inspect together?"},
    "patina": {"pillar": "luxury", "prompt": "What has experience changed without erasing the original?"},
    "hallmark": {"pillar": "luxury", "prompt": "Where is the evidence of care in the details?"},
    "gravitas": {"pillar": "executive", "prompt": "Can the decision be quiet and still be clear?"},
    "flagship": {"pillar": "luxury", "prompt": "What is the smallest complete example of excellent work?"},
    "counsel": {"pillar": "executive", "prompt": "Who can challenge the plan without becoming its enemy?"},
    "archive": {"pillar": "enterprise", "prompt": "What should your future self be able to find and understand?"},
    "custodian": {"pillar": "enterprise", "prompt": "What must remain intact while you improve it?"},
    "execution": {"pillar": "executive", "prompt": "What will you actually do next, and what will you notice?"},
    "protocol": {"pillar": "enterprise", "prompt": "Which boundaries keep the work legible and reversible?"},
    "heritage": {"pillar": "luxury", "prompt": "What deserves to endure without becoming a museum piece?"},
}


def inspect_reference(path):
    path, size = _bounded_path(path)
    return {
        "path": str(path),
        "name": path.name,
        "bytes": size,
        "sha256": _sha(path),
        "pages": _pages(path),
        "title": "One Hundred Executive Associations · supplied brainstorm",
        "role": "association prompts, not doctrine or leadership evidence",
        "source_text_bundled": False,
    }


def association(word):
    if not isinstance(word, str):
        raise ValueError("association must be text")
    word = word.strip().lower()
    if word not in ASSOCIATIONS:
        raise ValueError(f"unknown Maison association: {word}")
    return word, ASSOCIATIONS[word]


def maison_review(log, word="stewardship", reference=None):
    word, definition = association(word)
    review = log.review()
    return {
        "word": word,
        "pillar": definition["pillar"],
        "prompt": definition["prompt"],
        "practice": review,
        "reference": reference,
        "score": None,
        "autonomous_action": False,
        "summary": f"{word.upper()} · {definition['prompt']}\n{review['summary']}\nExecutive clarity · luxury restraint · enterprise evidence · no leadership score",
    }


def _wrap(text, width=44):
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def maison_scene(log=None, word="stewardship", reference=None):
    log = log or demo_log()
    review = maison_review(log, word, reference)
    objects = [
        {"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": PALETTE["ink"], "fill": PALETTE["ink"], "width": 1},
        {"id": "frame", "type": "rectangle", "bounds": [28, 28, 972, 732], "stroke": PALETTE["bronze"], "fill": "none", "width": 1},
        {"id": "monogram", "type": "rectangle", "bounds": [50, 51, 84, 89], "stroke": PALETTE["champagne"], "fill": "none", "width": 1},
        _text("monogram-z", [62, 80], "Z", 26, PALETTE["champagne"]),
        _text("title", [110, 77], "Zoe Maison", 33, PALETTE["pearl"]),
        _text("subtitle", [112, 107], "Executive · Luxury · Enterprise", 14, PALETTE["champagne"]),
        _line("title-rule", [50, 133], [950, 133], PALETTE["bronze"], 1),
        _text("pillar", [72, 184], review["pillar"].upper(), 12, PALETTE["sage"]),
        _text("association", [70, 231], review["word"].upper(), 36, PALETTE["champagne"]),
    ]
    for index, line in enumerate(_wrap(review["prompt"], 49)[:3]):
        objects.append(_text(f"association-prompt-{index}", [72, 280 + index * 29], line, 18, PALETTE["pearl"]))
    objects.append(_text("association-boundary", [72, 360], "A question for the work, not a command for a person.", 13, PALETTE["slate"]))
    cards = (
        ("executive", "Decide with context", "Who bears the consequences—and who can review?"),
        ("luxury", "Make fewer, better things", "Where is the care in the detail?"),
        ("enterprise", "Preserve the evidence", "Can someone trace, verify, and reverse the work?"),
    )
    for index, (pillar, title, prompt) in enumerate(cards):
        x = 60 + index * 303
        objects.append({"id": f"pillar-card-{pillar}", "type": "rectangle", "bounds": [x, 402, x + 280, 554], "stroke": PALETTE["panel"], "fill": PALETTE["panel"], "width": 1})
        objects.append(_line(f"pillar-rule-{pillar}", [x, 402], [x + 280, 402], PALETTE["champagne"], 2))
        objects.append(_text(f"pillar-title-{pillar}", [x + 16, 436], pillar.upper(), 12, PALETTE["champagne"]))
        objects.append(_text(f"pillar-action-{pillar}", [x + 16, 469], title, 16, PALETTE["pearl"]))
        for row, line in enumerate(_wrap(prompt, 33)[:3]):
            objects.append(_text(f"pillar-prompt-{pillar}-{row}", [x + 16, 502 + row * 19], line, 11, PALETTE["slate"]))
    practice = review["practice"]
    objects.append(_text("current-label", [72, 603], "CURRENT PRACTICE", 12, PALETTE["sage"]))
    objects.append(_text("current-events", [72, 633], f"{practice['practice_events']} {practice['event_label']} · {practice['corrections']} corrections · no score", 13, PALETTE["slate"]))
    for index, line in enumerate(_wrap(practice["next_question"], 72)[:2]):
        objects.append(_text(f"current-next-{index}", [72, 668 + index * 25], line, 15, PALETTE["pearl"]))
    if reference:
        source = f"Association reference · SHA-256 {reference['sha256'][:24]}... · no doctrine inferred"
    else:
        source = "Curated association prompts · no document loaded · no doctrine inferred"
    objects.append(_text("reference", [72, 724], source, 11, PALETTE["sage"]))
    scene = _scene("zoe-maison", 1000, 760, objects, "Zoe Maison · executive clarity, luxury restraint, enterprise evidence")
    return scene, review


def export_maison(path, log=None, word="stewardship", reference=None, kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("Maison export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("Maison export directory does not exist")
    scene, _ = maison_scene(log, word, reference)
    check = verify_vdi(scene) if kind == "gem" else verify(scene)
    if not check.passed:
        raise ValueError(check.text())
    if kind == "gem":
        write_metafile(scene, path)
    elif kind == "svg":
        write_svg(scene, path, width)
    else:
        write_png(scene, path, width)
    return path
