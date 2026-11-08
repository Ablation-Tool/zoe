"""Bounded, source-linked corpus ingestion without claiming comprehension."""
from dataclasses import dataclass
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re

EXPECTED_BOOKS = 35
MAX_SNIPPET = 280
NON_CONTENT = {
    "cover", "title", "titlepage", "halftitle", "copyright", "imprint", "eula",
    "index", "toc", "navigation", "seriespage", "abbreviations", "signup", "author_bios",
}
TERMS = {
    "alignment": ("alignment", "needleman", "smith–waterman", "smith-waterman"),
    "sampling": ("sampling", "nyquist", "voxel", "pixel size"),
    "psf": ("point spread", "psf", "partial volume"),
    "mtf": ("modulation transfer", "mtf", "optical transfer"),
    "reconstruction": ("reconstruction", "radon", "backprojection", "tomography"),
    "inverse-problems": ("inverse problem", "regularization", "deconvolution"),
    "mri-safety": ("mri safety", "specific absorption", "projectile", "gradient safety"),
    "radiation-safety": ("radiation exposure", "radiation protection", "dose", "sv"),
    "detectors": ("detector", "photon-counting", "pileup", "scintillator"),
    "bioinformatics": ("bioinformatics", "sequence", "genome", "protein"),
    "optimization": ("optimization", "gradient descent", "evolutionary", "fuzzy"),
    "gpu": ("gpu", "cuda", "parallel computing"),
    "matlab": ("matlab", "simulink"),
    "geometry": ("riemannian", "geometric", "geometry", "mesh"),
    "uncertainty": ("uncertainty", "neutrosophic", "probability", "noise"),
    "humor": ("humor", "humour", "creativity", "laughter"),
    "imaging": ("imaging", "image", "microscopy", "tomographic"),
}
STOP_WORDS = NON_CONTENT
BOOK_ARTIFACTS = {
    "GPT-3": {
        "001_nav.html": "navigation",
        "002_xhtml-0-0.html": "title page",
        "003_xhtml-0-1.html": "copyright",
        "004_xhtml-0-2.html": "dedication",
        "005_xhtml-0-3.html": "praise",
        "007_xhtml-0-5.html": "contents",
        "015_xhtml-0-13.html": "acknowledgements",
        "016_xhtml-0-14.html": "author biography",
        "017_xhtml-0-15.html": "author biography",
    },
    "MATLAB Numerical Calculations": {
        "003_9781484203477_FM_6_Contents_at_a_Glance.html": "contents at a glance",
        "004_9781484203477_FM_5_Contents.html": "contents",
        "005_9781484203477_FM_3_About_the_Author.html": "author biography",
        "006_9781484203477_FM_4_Preface.html": "also available",
    },
    "Windows 98 Unleashed": {
        "001_0672312352_pref01.html": "author biography",
        "002_0672312352_pref02.html": "acknowledgements",
        "003_0672312352_pref03.html": "preface",
        "004_0672312352_part01.html": "part divider",
        "038_0672312352_part02.html": "part divider",
        "098_0672312352_part03.html": "part divider",
        "135_0672312352_part04.html": "part divider",
        "186_0672312352_part05.html": "part divider",
        "208_0672312352_part06.html": "part divider",
        "239_0672312352_part07.html": "part divider",
        "309_0672312352_bvdidx.html": "index",
    },
}


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(value):
    return " ".join(value.split())


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignored = 0
        self.heading = None
        self.headings = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "math"}:
            self.ignored += 1
        if self.ignored:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            self.heading = [tag, []]
        if tag in {"p", "li", "tr", "section", "div"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "math"} and self.ignored:
            self.ignored -= 1
        if self.heading is not None and tag == self.heading[0]:
            value = normalized("".join(self.heading[1]))
            if value:
                self.headings.append(value)
            self.heading = None

    def handle_data(self, data):
        if self.ignored:
            return
        self.parts.append(data)
        if self.heading is not None:
            self.heading[1].append(data)


def content_file(path, book=None):
    if book in BOOK_ARTIFACTS and path.name in BOOK_ARTIFACTS[book]:
        return False
    stem = path.stem.lower()
    return not any(stem == word or stem.endswith("_" + word) or word in stem for word in STOP_WORDS)


def chapter(path, book):
    parser = TextParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = normalized(" ".join(parser.parts))
    words = text.split()
    lowered = text.lower()
    index_terms = {name: sum(lowered.count(term) for term in terms)
                   for name, terms in TERMS.items()}
    index_terms = {name: count for name, count in index_terms.items() if count}
    title = parser.headings[0] if parser.headings else path.stem
    return {
        "id": path.stem,
        "title": title[:240],
        "source": f"{book}/{path.name}",
        "sha256": sha256(path),
        "word_count": len(words),
        "headings": parser.headings[:16],
        "index_terms": index_terms,
        "snippet": text[:MAX_SNIPPET],
        "status": "extracted",
    }


def book(path):
    html = sorted(path.glob("*.html"))
    chapters = [chapter(file, path.name) for file in html if content_file(file, path.name)]
    excluded = [
        {
            "source": f"{path.name}/{file.name}",
            "reason": BOOK_ARTIFACTS.get(path.name, {}).get(file.name, "filename classification"),
        }
        for file in html if not content_file(file, path.name)
    ]
    return {
        "folder": path.name,
        "status": "cataloged" if html else "waiting-for-content",
        "html_files": len(html),
        "excluded_artifacts": excluded,
        "chapters": chapters,
    }


def merge_reviews(document, reviews):
    if not reviews:
        return
    for book in document["books"]:
        for chapter in book["chapters"]:
            review = reviews.get(chapter["source"])
            if review is None:
                continue
            if review.get("source_sha256") != chapter["sha256"]:
                raise ValueError(f"review source changed: {chapter['source']}")
            required = ("concepts", "application", "limitations", "reviewed_at")
            if any(not review.get(field) for field in required):
                raise ValueError(f"incomplete review: {chapter['source']}")
            if not review.get("use") and not review.get("no_tool_rationale"):
                raise ValueError(f"review needs use or no-tool rationale: {chapter['source']}")
            chapter["status"] = "reviewed"
            chapter["review"] = review


def coverage(document):
    chapters = [chapter for book in document["books"] for chapter in book["chapters"]]
    reviewed = [chapter for chapter in chapters if chapter["status"] == "reviewed"]
    present = len(document["books"])
    document["coverage"] = {
        "expected_books": EXPECTED_BOOKS,
        "present_books": present,
        "missing_books": max(0, EXPECTED_BOOKS - present),
        "extra_books": max(0, present - EXPECTED_BOOKS),
        "chapters": len(chapters),
        "reviewed_chapters": len(reviewed),
        "pending_chapters": len(chapters) - len(reviewed),
        "words": sum(chapter["word_count"] for chapter in chapters),
        "understood": present >= EXPECTED_BOOKS and len(chapters) == len(reviewed) and bool(chapters),
        "boundary": "Extraction and indexing are not comprehension; reviewed status requires concepts, application, limitations, and demonstrated use or no-tool rationale.",
    }
    return document


def build(root, reviews=None):
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("corpus root must be a directory")
    document = {
        "schema": "neurogarden-corpus-v1",
        "expected_collection": root.name,
        "books": [book(path) for path in sorted(root.iterdir()) if path.is_dir()],
    }
    merge_reviews(document, reviews or {})
    return coverage(document)


def load_reviews(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("schema") != "neurogarden-reviews-v1" or not isinstance(document.get("reviews"), dict):
        raise ValueError("unsupported review document")
    return document["reviews"]


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Ingest extracted books with explicit comprehension boundaries")
    parser.add_argument("root", type=Path)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    document = build(args.root, load_reviews(args.reviews) if args.reviews else None)
    if args.output.exists():
        raise FileExistsError("refusing to overwrite corpus output")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(document, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(json.dumps(document["coverage"], indent=2))


if __name__ == "__main__":
    main()
