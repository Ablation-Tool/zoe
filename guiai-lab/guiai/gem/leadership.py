from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import textwrap

from .atlas import _line, _scene, _text
from .field import _canonical
from .geometry import verify
from .patchbay import _bounded_path, _sha
from .practice import PracticeLog, demo_log
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


CATALOG_URL = "https://history.army.mil/Publications/Publications-Catalog/Publications-by-Number/"
DECLARATION_URL = "https://en.wikipedia.org/wiki/Declaration_on_the_Protection_of_Women_and_Children_in_Emergency_and_Armed_Conflict"
PERSONAL_QUOTE = "There are two types of leaders, the ones you HAVE to follow, and the ones you WANT to follow. You get to decide which one you become"
PERSONAL_ATTRIBUTION = "Nicholas Michael Kloster, recalling advice from his 1SG · personal experience, not a leadership classification"
LIBRARY = {
    "soldier-statesmen": {"filename": "71-25.pdf", "title": "Soldier-Statesmen of the Constitution", "authors": "Robert K. Wright Jr. and Morris J. MacGregor Jr.", "publication": "CMH Pub 71-25", "pages": 316, "lens": "Civic responsibility"},
    "heritage": {"filename": "Army History and Heritiage.pdf", "title": "Army History and Heritage", "authors": "Paul E. Funk II; Mark L. Bradley, general editor", "publication": "CMH Pub 69-6-1", "pages": 313, "lens": "Institutional memory"},
    "care": {"filename": "Demands of Humanity: Army Medical Disaster Relief\n.pdf", "title": "The Demands of Humanity: Army Medical Disaster Relief", "authors": "Gaines M. Foster", "publication": "CMH Pub 40-3", "pages": 204, "lens": "Care in action"},
    "nco": {"filename": "The Story of the Noncommissioned Officer Corps - The Backbone of the Army.pdf", "title": "The Story of the Noncommissioned Officer Corps: The Backbone of the Army", "publication": "CMH Pub 70-38", "pages": 370, "lens": "Mentorship"},
    "support": {"filename": "a soldier supporting soldiers.pdf", "title": "A Soldier Supporting Soldiers", "authors": "Joseph M. Heiser Jr.", "publication": "CMH Pub 70-40", "pages": 336, "lens": "Support and logistics"},
    "protection": {"filename": "very important.pdf", "title": "The Geneva Conventions of 12 August 1949", "authors": "International Committee of the Red Cross", "publication": "ICRC", "pages": 224, "lens": "Protection and dignity"},
}
EXTERNAL_READING = (
    {"title": "The Women's Army Corps", "authors": "Mattie E. Treadwell", "publication": "CMH Pub 11-8", "catalog": CATALOG_URL, "local_file_claimed": False},
    {"title": "The Women's Army Corps, 1945-1978", "authors": "Bettie J. Morden", "publication": "CMH Pub 30-14", "catalog": CATALOG_URL, "local_file_claimed": False},
    {"title": "Declaration on the Protection of Women and Children in Emergency and Armed Conflict", "publication": "United Nations General Assembly, 1974", "catalog": DECLARATION_URL, "local_file_claimed": False, "distinct_from_geneva_conventions": True},
)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _pages(path):
    if not shutil.which("pdfinfo"):
        return None
    completed = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=10)
    if completed.returncode:
        return None
    for line in completed.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":", 1)[1].strip())
    return None


def _personal_source(path):
    path, size = _bounded_path(path)
    return {"path": str(path), "bytes": size, "sha256": _sha(path), "bundled": False}


def inspect_library(root):
    root = Path(root)
    if not root.is_dir():
        raise ValueError("leadership reference root must be an existing directory")
    documents = []
    for identifier, source in LIBRARY.items():
        path = root / source["filename"]
        if not path.is_file():
            raise ValueError(f"missing reference document: {path}")
        path, size = _bounded_path(path)
        documents.append({
            "id": identifier,
            "title": source["title"],
            "authors": source.get("authors"),
            "publication": source["publication"],
            "lens": source["lens"],
            "path": str(path),
            "bytes": size,
            "sha256": _sha(path),
            "pages": _pages(path),
            "expected_pages": source["pages"],
            "local_file": True,
            "content_role": "reference-not-a-leadership-score",
        })
    personal = {}
    for key, filename in (("note", "Leadership Development.txt"), ("photo", "The Story of the Noncommissioned Officer Corps- The Backbone of the Army.png")):
        path = root / filename
        if path.is_file():
            personal[key] = _personal_source(path)
    return {
        "schema_version": 1,
        "instrument": "zoe-leadership-library",
        "root": str(root),
        "documents": documents,
        "external_reading": list(EXTERNAL_READING),
        "personal_sources": personal,
        "catalog": CATALOG_URL,
        "books_replace_practice": False,
        "personal_photo_bundled": False,
        "summary": f"{len(documents)} reference documents · {len(EXTERNAL_READING)} external reading links\nBooks can offer advice and counterexamples; they cannot complete a practice repetition.\nPersonal sources remain local and are not copied into Zoe.",
    }


def search_library(root, query, max_snippets=12):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 100:
        raise ValueError("library search requires 1-100 characters")
    if isinstance(max_snippets, bool) or not isinstance(max_snippets, int) or not 1 <= max_snippets <= 32:
        raise ValueError("snippet limit must be between 1 and 32")
    query = query.strip().casefold()
    if not shutil.which("pdftotext"):
        raise RuntimeError("leadership text search requires pdftotext")
    library = inspect_library(root)
    snippets = []
    errors = []
    for source in library["documents"]:
        if len(snippets) >= max_snippets:
            break
        with tempfile.TemporaryDirectory(prefix="zoe-leadership-text-") as directory:
            output = Path(directory) / "extract.txt"
            completed = subprocess.run(["pdftotext", "-layout", source["path"], str(output)], capture_output=True, text=True, timeout=30)
            if completed.returncode:
                errors.append({"id": source["id"], "error": completed.stderr[-500:]})
                continue
            if output.stat().st_size > 8 * 1024 * 1024:
                errors.append({"id": source["id"], "error": "extracted text exceeds 8 MiB"})
                continue
            for page, text in enumerate(output.read_text(encoding="utf-8", errors="replace").split("\f"), 1):
                compact = " ".join(text.split())
                position = compact.casefold().find(query)
                if position < 0:
                    continue
                start = max(0, position - 120)
                end = min(len(compact), position + len(query) + 180)
                snippets.append({
                    "source_id": source["id"],
                    "title": source["title"],
                    "pdf_page": page,
                    "text": ("..." if start else "") + compact[start:end] + ("..." if end < len(compact) else ""),
                    "source_sha256": source["sha256"],
                    "ocr_performed": False,
                })
                if len(snippets) >= max_snippets:
                    break
    return {
        "schema_version": 1,
        "instrument": "zoe-leadership-search",
        "query": query,
        "documents_searched": len(library["documents"]),
        "snippets": snippets,
        "snippet_count": len(snippets),
        "truncated": len(snippets) >= max_snippets,
        "complete_extraction": not errors,
        "errors": errors,
        "ocr_performed": False,
        "summary": f"{len(snippets)} extracted snippets · {len(errors)} extraction errors\nPage references are PDF page numbers, not printed page labels. No new OCR or leadership inference was performed.",
    }


def _wrap(text, width=38):
    return textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False)


def leadership_scene(log=None, library=None):
    log = log or demo_log()
    review = log.review()
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#0b1516", "fill": "#0b1516", "width": 1}]
    objects.append(_text("title", [42, 55], "Zoe Leadership Garden", 32, "#a7f3d0"))
    objects.append(_text("subtitle", [44, 86], "Do · notice · advice · miss · learn · adapt", 16, "#c7d2d1"))
    objects.append(_text("skill", [44, 111], "Adaptive · perishable · always in practice", 13, "#8fb3a9"))
    objects.append(_text("garden-caption", [133, 151], "Practice, not a badge", 16, "#a7f3d0"))
    center = [315, 385]
    positions = [[315, 220], [458, 315], [458, 455], [315, 525], [172, 455], [172, 315]]
    labels = ["DO", "NOTICE", "ADVICE", "MISS", "LEARN", "ADAPT"]
    colors = ["#67e8f9", "#a7f3d0", "#fde68a", "#fda4af", "#c4b5fd", "#a7f3d0"]
    for index, position in enumerate(positions):
        following = positions[(index + 1) % len(positions)]
        objects.append(_line(f"loop-{index}", position, following, "#47706a", 3))
    objects.append({"id": "garden-center", "type": "ellipse", "center": center, "radii": [82, 63], "stroke": "#a7f3d0", "fill": "#143630", "width": 2})
    objects.append(_text("center-people", [270, 380], "People", 23, "#a7f3d0"))
    objects.append(_text("center-rank", [263, 410], "before rank", 19, "#c7d2d1"))
    for index, (position, label, color) in enumerate(zip(positions, labels, colors)):
        objects.append({"id": f"petal-{index}", "type": "ellipse", "center": position, "radii": [54, 42], "stroke": color, "fill": "#102729", "width": 2})
        objects.append(_text(f"petal-label-{index}", [position[0] - len(label) * 5, position[1] + 6], label, 13, color))
    objects.append(_text("garden-tending", [148, 610], "The garden needs tending, not domination.", 13, "#8fb3a9"))
    objects.append(_text("advice-title", [596, 151], "Advice from experience", 21, "#fde68a"))
    for index, line in enumerate(_wrap(f'“{PERSONAL_QUOTE}”', 40)):
        objects.append(_text(f"personal-quote-{index}", [596, 190 + index * 24], line, 14, "#f3f4f6"))
    for index, line in enumerate(_wrap(PERSONAL_ATTRIBUTION, 42)[:3]):
        objects.append(_text(f"personal-attribution-{index}", [596, 307 + index * 20], line, 11, "#8fb3a9"))
    objects.append(_text("honesty", [596, 398], "No deception", 25, "#fda4af"))
    objects.append(_text("honesty-scope", [596, 427], "Not even a flattering score.", 13, "#c7d2d1"))
    objects.append(_text("next-title", [596, 474], "Next small experiment", 16, "#a7f3d0"))
    for index, line in enumerate(_wrap(review["next_question"], 42)[:4]):
        objects.append(_text(f"next-question-{index}", [596, 505 + index * 23], line, 13, "#f3f4f6"))
    objects.append(_text("practice-count", [596, 609], f"{review['practice_events']} {review['event_label']} · {review['corrections']} corrections · no score", 12, "#8fb3a9"))
    shelf = f"Reference shelf: {len(library['documents'])} documents" if library else "Books advise. Practice makes the rep."
    objects.append(_text("reference-shelf", [596, 648], shelf, 12, "#8fb3a9"))
    objects.append(_text("garden-boundary", [596, 674], "Experience is the curriculum.", 13, "#c7d2d1"))
    objects.append(_text("boundary", [44, 730], "Failure is information, not identity · no leadership score · no automatic action", 14, "#fda4af"))
    scene = _scene("zoe-leadership-garden", 1000, 760, objects, "Zoe Leadership Garden · practice, advice, failure, learning, adaptation")
    return scene, {**review, "library": library, "summary": review["summary"] + "\nNo deception · people before rank · books do not replace practice", "autonomous_action": False}


def export_leadership(path, log=None, library=None, kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("leadership export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("leadership export directory does not exist")
    scene, _ = leadership_scene(log, library)
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
