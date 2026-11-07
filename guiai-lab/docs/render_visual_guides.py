from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


DOCS = Path(__file__).resolve().parent
STYLE = DOCS / "visual-style.tex"
GUIDES = (
    ("ARTLINE.md", "Zoe Artline", "zoe-artline-visual.pdf", "images/zoe-artline-native.png"),
    ("PENTOMINO.md", "Zoe Pentomino", "zoe-pentomino-visual.pdf", "images/zoe-pentomino-native.png"),
    ("PILOT.md", "Zoe Practice Navigator", "zoe-pilot-visual.pdf", "images/zoe-pilot-cover.png"),
    ("COGNITIVE.md", "Zoe Cognitive Field", "zoe-cognitive-field-visual.pdf", "images/zoe-cognitive-field.png"),
    ("QUALIA.md", "Zoe is Quale. Zoe is Red.", "zoe-qualia-visual.pdf", "images/zoe-qualia.png"),
    ("GEOMETRY-ATLAS.md", "GEM Geometry Atlas", "zoe-geometry-atlas-visual.pdf", "images/geometry-atlas-procrustes.png"),
    ("UNIFIED.md", "Zoe allgems: unified architecture and verification", "zoe-unified-visual.pdf", "images/gem-unified.png"),
    ("ZOE.md", "Zoe: living geometry, inspectable futures", "zoe-living-geometry-visual.pdf", "images/zoe-brain.png"),
    ("RESILIENCE.md", "Zoe Resilience Atlas", "zoe-resilience-visual.pdf", "images/zoe-resilience.png"),
    ("PRESENCE.md", "Zoe Presence", "zoe-presence-visual.pdf", "images/zoe-presence.png"),
    ("PROTOCOL.md", "Zoe Protocol Lab", "zoe-protocol-visual.pdf", "images/zoe-protocol.png"),
    ("WAVEFORM.md", "Zoe Waveform Replay", "zoe-waveform-visual.pdf", "images/zoe-waveform.png"),
    ("../../CONSTITUTION.md", "Zoe Constitution", "zoe-constitution-visual.pdf", "images/gem-unified.png"),
    ("../../DECLARATION.md", "Zoe Declaration of Creative and Epistemic Independence", "zoe-declaration-visual.pdf", "images/zoe-pilot-cover.png"),
    ("references/cognitive-field/PROVENANCE.md", "Cognitive Field visual provenance", "zoe-cognitive-provenance-visual.pdf", "images/zoe-cognitive-anatomy.png"),
)
INDEX_SOURCE = "VISUAL-GUIDES.md"
INDEX_TITLE = "Zoe Visual Guide Collection"
INDEX_OUTPUT = "zoe-visual-guides.pdf"
SVG_IMAGE = re.compile(r'<img\s+src="([^"]+)"\s+width="(\d+)"\s+alt="([^"]+)"\s*/?>')


def require_tools():
    missing = [name for name in ("pandoc", "pdflatex", "pdfinfo", "rsvg-convert", "kpsewhich") if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"visual guide tools are missing: {', '.join(missing)}")
    if not STYLE.is_file():
        raise ValueError(f"missing visual style: {STYLE}")
    if subprocess.run(["kpsewhich", "newunicodechar.sty"], capture_output=True).returncode != 0:
        raise RuntimeError("the newunicodechar LaTeX package is required for visual guide mathematics")


def inline_svg_images(text, source, temporary):
    def replace(match):
        relative, width, alt = match.groups()
        image = DOCS / relative
        if image.suffix.lower() != ".svg":
            return match.group(0)
        if not image.is_file():
            raise ValueError(f"missing inline image in {source}: {relative}")
        if shutil.which("rsvg-convert") is None:
            raise RuntimeError("rsvg-convert is required for inline SVG guide artwork")
        output = temporary / f"{image.stem}-{width}.png"
        subprocess.run(
            ["rsvg-convert", "--width", str(max(256, int(width) * 4)), "--output", str(output), str(image)],
            check=True, capture_output=True, text=True,
        )
        percentage = min(95, max(8, int(width) // 4))
        return f"![{alt}]({output}){{width={percentage}%}}"

    return SVG_IMAGE.sub(replace, text)


def prepare_markdown(source, title, hero, temporary):
    path = DOCS / source
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"^#\s+[^\n]+\n+", "", text, count=1)
    text = inline_svg_images(text, source, temporary)
    if f"]({hero})" not in text:
        text = f"![{title} · visual study]({hero}){{width=100%}}\n\n{text}"
    if source.endswith("PROVENANCE.md"):
        gallery = []
        for name, label in (
            ("reference-temporal-layers.png", "Supplied temporal-layer reference"),
            ("reference-hub-lattice.png", "Supplied hub-lattice reference"),
            ("reference-memory-flow.png", "Supplied memory-flow reference"),
        ):
            relative = f"references/cognitive-field/{name}"
            if not (DOCS / relative).is_file():
                raise ValueError(f"missing provenance artwork: {relative}")
            gallery.append(f"![{label}]({relative}){{width=100%}}")
        text = "\n\n".join(gallery) + "\n\n" + text
    destination = temporary / "source.md"
    destination.write_text(text, encoding="utf-8")
    return destination


def render_document(source, title, hero, output, temporary, index=False):
    markdown = prepare_markdown(source, title, hero, temporary)
    command = [
        "pandoc", str(markdown), "--standalone", "--pdf-engine=pdflatex",
        f"--resource-path={DOCS}", f"--include-in-header={STYLE}",
        "--from=markdown+raw_html+tex_math_dollars+tex_math_single_backslash",
        "--variable=papersize:letter", "--variable=fontsize:11pt",
        "--variable=geometry:margin=0.72in", "--variable=colorlinks:true",
        "--variable=linkcolor:ZoeCyan", "--variable=urlcolor:ZoeCyan",
        "--variable=citecolor:ZoeCyan", "--highlight-style=tango",
        f"--metadata=title:{title}", "--metadata=author:Zoe / allgems",
        f"--metadata=subject:Visual edition of {source}",
    ]
    if not index:
        command.extend(("--toc", "--toc-depth=2", "--number-sections"))
    command.extend(("--output", str(output)))
    completed = subprocess.run(command, cwd=DOCS, capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(f"{source}: pandoc failed\n{completed.stdout[-4000:]}\n{completed.stderr[-8000:]}")
    return output


def pdf_metadata(path):
    try:
        completed = subprocess.run(["pdfinfo", str(path)], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"pdfinfo failed for {path}: {error.stderr[-2000:]}") from error
    values = {}
    for line in completed.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            values[key] = value.strip()
    return {
        "title": values.get("Title", ""),
        "pages": int(values["Pages"]),
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def generate_all(output_root=None):
    require_tools()
    output_root = Path(output_root) if output_root is not None else DOCS / "visual"
    output_root.mkdir(parents=True, exist_ok=True)
    records = []
    with tempfile.TemporaryDirectory(prefix=".visual-guides-", dir=output_root.parent) as directory:
        temporary = Path(directory)
        for source, title, filename, hero in GUIDES:
            destination = output_root / filename
            rendered = temporary / filename
            render_document(source, title, hero, rendered, temporary)
            os.replace(rendered, destination)
            record = {"source": source, "output": destination.name, **pdf_metadata(destination)}
            records.append(record)
            print(f"{source}: {record['pages']} pages -> {destination}")
        index_rendered = temporary / INDEX_OUTPUT
        index_destination = output_root.parent / INDEX_OUTPUT
        render_document(INDEX_SOURCE, INDEX_TITLE, "images/zoe-pilot-cover.png", index_rendered, temporary, index=True)
        os.replace(index_rendered, index_destination)
        record = {"source": INDEX_SOURCE, "output": f"../{INDEX_OUTPUT}", **pdf_metadata(index_destination)}
        records.append(record)
        print(f"{INDEX_SOURCE}: {record['pages']} pages -> {index_destination}")
    manifest = {
        "schema_version": 1,
        "instrument": "Zoe visual guide collection",
        "renderer": "pandoc + pdfLaTeX + newunicodechar",
        "guide_count": len(GUIDES),
        "pdf_count": len(records),
        "documents": records,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Manifest: {manifest_path}")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render every Zoe guide and the linked collection index as visual PDFs")
    parser.add_argument("--output-dir", help="directory for individual guide PDFs; default: docs/visual")
    arguments = parser.parse_args(argv)
    try:
        manifest = generate_all(arguments.output_dir)
        print(json.dumps({"pdf_count": manifest["pdf_count"], "guide_count": manifest["guide_count"]}, sort_keys=True))
        return 0
    except (OSError, RuntimeError, ValueError) as error:
        print(f"visual guides: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
