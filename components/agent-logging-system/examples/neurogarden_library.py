#!/usr/bin/env python3
"""Catalog an extracted HTML library without copying book prose or calling a network."""
import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path


class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ignored = 0
        self.current_link = None
        self.heading = None
        self.headings = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.ignored += 1
        if self.ignored:
            return
        if tag in {"h1", "h2", "title"}:
            self.heading = [tag, []]
        if tag == "a":
            self.current_link = [dict(attrs).get("href", ""), []]

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.ignored:
            self.ignored -= 1
        if self.heading is not None and tag == self.heading[0]:
            text = " ".join("".join(self.heading[1]).split())
            if text:
                self.headings.append(text)
            self.heading = None
        if tag == "a" and self.current_link is not None:
            href, pieces = self.current_link
            text = " ".join("".join(pieces).split())
            if text:
                self.links.append({"text": text, "href": href})
            self.current_link = None

    def handle_data(self, data):
        if self.ignored:
            return
        if self.heading is not None:
            self.heading[1].append(data)
        if self.current_link is not None:
            self.current_link[1].append(data)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized(value):
    return "".join(character for character in value.lower() if character.isalnum())


def subjects(title):
    value = title.lower()
    if "humor" in value:
        return ["creativity", "communication", "neuroscience-of-humor"]
    if "bioinformatics" in value or "genome" in value:
        return ["bioinformatics", "sequence-analysis"]
    if "imaging" in value or "tomography" in value or "ultrasound" in value:
        return ["biomedical-imaging", "reconstruction", "sampling"]
    if "matlab" in value or "gpu" in value:
        return ["scientific-computing"]
    if "nano" in value or "sensor" in value:
        return ["nanotechnology", "sensors"]
    if "fuzzy" in value or "neutrosophic" in value:
        return ["medical-data-analysis"]
    if "gpt" in value:
        return ["language-models"]
    return ["research-reference"]


def parse_file(path):
    parser = DocumentParser()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    return parser


def catalog_book(directory):
    html = sorted(directory.glob("*.html"))
    record = {
        "folder": directory.name,
        "intentional": True,
        "status": "cataloged" if html else "waiting-for-content",
        "citation_scope": "reference-only; medical claims require qualified human review",
        "html_files": len(html),
        "image_files": len(list((directory / "images").glob("*"))) if (directory / "images").is_dir() else 0,
    }
    if not html:
        return record
    title_files = [path for path in html if "title" in path.name.lower() or "halftitle" in path.name.lower()]
    title = ""
    title_file = None
    for path in title_files:
        parser = parse_file(path)
        headings = [" ".join(parser.headings[:2])] if parser.headings else []
        candidates = [text for text in headings + [link["text"] for link in parser.links] if len(text) > 8]
        if candidates:
            title = max(candidates, key=len)
            title_file = path
            break
    toc_files = [path for path in html if "toc" in path.name.lower() or "navigation" in path.name.lower()]
    toc_entries = []
    for path in toc_files[:1]:
        toc_entries = parse_file(path).links[:256]
    record.update({
        "title": title or directory.name,
        "title_source": title_file.name if title_file else None,
        "title_sha256": sha256(title_file) if title_file else None,
        "toc_source": toc_files[0].name if toc_files else None,
        "toc_sha256": sha256(toc_files[0]) if toc_files else None,
        "toc": toc_entries,
    })
    record["subjects"] = subjects(record["title"])
    folder_subject = directory.name.split("(", 1)[0].strip()
    record["folder_title_matches"] = normalized(folder_subject) in normalized(record["title"]) \
        or normalized(record["title"]) in normalized(folder_subject)
    record["corpus_sha256"] = hashlib.sha256(
        "\n".join(f"{path.name}:{sha256(path)}" for path in html).encode("utf-8")
    ).hexdigest()
    if not record["folder_title_matches"]:
        record["warning"] = "folder/title metadata mismatch; intentional collection entry preserved"
    return record


def main():
    parser = argparse.ArgumentParser(description="Catalog an extracted Neurogarden HTML library")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, help="new JSON path; never overwrites")
    args = parser.parse_args()
    root = args.root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("library root must be a directory")
    books = [catalog_book(path) for path in sorted(root.iterdir()) if path.is_dir()]
    document = {
        "schema": "neurogarden-library-v1",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "scope": "metadata and TOC catalog only; not a claim that books were fully read",
        "books": books,
        "warnings": [book["warning"] for book in books if "warning" in book],
    }
    payload = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(payload)
    print(json.dumps({
        "books": len(books),
        "cataloged": sum(book["status"] == "cataloged" for book in books),
        "waiting": sum(book["status"] == "waiting-for-content" for book in books),
        "warnings": len(document["warnings"]),
        "output": str(args.output) if args.output else None,
    }, indent=2))


if __name__ == "__main__":
    main()
