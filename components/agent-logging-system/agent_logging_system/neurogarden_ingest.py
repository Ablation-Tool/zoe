"""Unified Book Ingestion Pipeline: Catalog, SHA-256 Provenance, & 4-Head Plate Dissection.

Chains Neurogarden cataloging with Zoe's 4-Head Vision & Global Self-Attention Dissector:
  1. Hashes all HTML chapters and extracted scientific figures (SHA-256).
  2. Selects key scientific plates and renders 6-panel 4-Head Self-Attention dissections.
  3. Emits a bounded, non-overwriting JSON review manifest with `clinical_action_authorized=False`
     and `fully_read_claimed=False`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List

from .neurogarden_vision_heads import render_multihead_dissection


CONTRACT = "zoe-neurogarden-book-ingest/v1"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_book_directory(
    book_dir: str | Path,
    output_dir: str | Path,
    max_plates: int = 2,
    grid_n: int = 16,
) -> Dict[str, object]:
    """
    Catalogs a local extracted book folder, hashes chapters & images, runs the
    4-Head Vision Dissector on top scientific plates, and writes an epistemic
    review manifest without overwriting existing files.
    """
    src = Path(book_dir).expanduser().resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"Book directory not found: {src}")
    if not 0 <= max_plates <= 16:
        raise ValueError("max_plates must be between 0 and 16")

    out = Path(output_dir).expanduser().resolve()
    manifest_path = out / "ingest-manifest.json"
    if manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing manifest: {manifest_path}")
    out.mkdir(parents=True, exist_ok=True)

    html_files = sorted(p for p in src.glob("*.html") if p.is_file())
    images_dir = src / "images"
    image_files: List[Path] = []
    if images_dir.is_dir():
        for ext in ("*.png", "*.jpg", "*.jpeg"):
            image_files.extend(images_dir.glob(ext))
    image_files.sort(key=lambda p: p.stat().st_size, reverse=True)

    chapters = [
        {
            "filename": p.name,
            "bytes": p.stat().st_size,
            "sha256": _sha256_file(p),
            "review_status": "queued_for_human_review",
        }
        for p in html_files
    ]

    dissected_plates = []
    for idx, img_path in enumerate(image_files[:max_plates]):
        dissect_out = out / f"plate_{idx+1:02d}_{img_path.stem}_4head.png"
        telemetry = render_multihead_dissection(
            img_path,
            dissect_out,
            grid_n=grid_n,
            title_label=f"{src.name} :: {img_path.name}",
        )
        dissected_plates.append({
            "source_image": img_path.name,
            "source_sha256": _sha256_file(img_path),
            "dissection_png": dissect_out.name,
            "dissection_sha256": _sha256_file(dissect_out),
            "telemetry": telemetry,
        })

    manifest = {
        "contract": CONTRACT,
        "book_folder": src.name,
        "source_path": str(src),
        "chapter_count": len(chapters),
        "image_count": len(image_files),
        "dissected_plate_count": len(dissected_plates),
        "chapters": chapters,
        "dissected_plates": dissected_plates,
        "fully_read_claimed": False,
        "clinical_action_authorized": False,
        "human_review_required": True,
    }
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Zoe Unified Book Ingest & 4-Head Plate Dissector")
    parser.add_argument("--book-dir", type=Path, required=True, help="Path to extracted book folder")
    parser.add_argument("--out", type=Path, required=True, help="Output directory for manifest & dissections")
    parser.add_argument("--max-plates", type=int, default=2, help="Number of top plates to dissect (0-16)")
    parser.add_argument("--grid", type=int, default=16, help="Patch grid size NxN")
    args = parser.parse_args()

    manifest = ingest_book_directory(args.book_dir, args.out, max_plates=args.max_plates, grid_n=args.grid)
    print(json.dumps({
        "contract": manifest["contract"],
        "book_folder": manifest["book_folder"],
        "chapter_count": manifest["chapter_count"],
        "image_count": manifest["image_count"],
        "dissected_plate_count": manifest["dissected_plate_count"],
        "manifest": str(args.out.expanduser().resolve() / "ingest-manifest.json"),
    }, indent=2))


if __name__ == "__main__":
    main()
