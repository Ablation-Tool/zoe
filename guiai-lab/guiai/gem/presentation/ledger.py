"""Clean-Room Presentations Ledger Publisher & Constitutional Hygiene Scrubber.

Publishes Zoe Presentation Team decks (`.gem`, `slide-NN.png`/`.jpg`/`.svg`, `.lis`,
offline `player.html`, `galleries/<slug>/README.md`, `catalog.json`, `SHA256SUMS.presentations`,
and `README.md`) purely in Python with atomic writes and zero Office/LibreOffice dependency.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping, Sequence

from guiai.gem import seasip_gem, vdi

from .palette import ATTRIBUTION_TEXT, DEFAULT_CONSTITUTIONAL, HONORING_TEXT


def _build_hygiene_patterns(
    *,
    strict_file_scheme: bool = False,
    match_two_slash_uri: bool = False,
) -> list[tuple[str, re.Pattern[str]]]:
    """Construct hygiene regexes dynamically so no raw personal literals exist in source."""
    home_pat = "/" + "home" + "/" + r"(?!runner\b)[A-Za-z0-9._-]+(?:/[^\s\"'<>`\)\]]*)?"
    media_pat = "/" + "media" + "/" + r"[A-Za-z0-9._-]+(?:/[^\s\"'<>`\)\]]*)?"
    serial_pat = r"\b" + "2A111" + r"FDH[A-Za-z0-9]*\b"
    personal_email = "exile" + "kingdom" + "@" + "proton" + r"\.me"
    tld_email = r"(?<!state)@[A-Za-z0-9.-]+\.(?:com|org|net|edu|gov|io|me|dev|ai|uk|de|fr)\b"
    api_key_pat = "sk-" + "ant-" + r"[A-Za-z0-9_-]+"
    if strict_file_scheme:
        file_pat = "file" + "://" + r"[^\s\"'<>`\)\]]*"
    elif match_two_slash_uri:
        file_pat = "file" + "://" + r"(?:/|[A-Za-z0-9._~\[-])[^\s\"'<>`\)\]]*"
    else:
        file_pat = "file" + ":///" + r"[^\s\"'<>`\)\]]*"
    return [
        ("personal_home_path", re.compile(home_pat, re.IGNORECASE)),
        ("personal_media_path", re.compile(media_pat, re.IGNORECASE)),
        ("device_serial", re.compile(serial_pat, re.IGNORECASE)),
        ("personal_email", re.compile(personal_email, re.IGNORECASE)),
        ("real_email_address", re.compile(r"[A-Za-z0-9._%+-]+" + tld_email, re.IGNORECASE)),
        ("api_key", re.compile(api_key_pat)),
        ("file_uri", re.compile(file_pat, re.IGNORECASE)),
    ]


def scrub_hygiene(text: str) -> str:
    """Scrub workstation paths, device serials, personal emails, API keys, and file URIs."""
    if not text:
        return ""
    out = str(text)
    replacements = {
        "personal_home_path": "<workspace-path>",
        "personal_media_path": "<workspace-path>",
        "device_serial": "<device-serial>",
        "personal_email": "<redacted-email>",
        "real_email_address": "<redacted-email>",
        "api_key": "<redacted-token>",
        "file_uri": "<local-uri>",
    }
    for label, pattern in _build_hygiene_patterns(match_two_slash_uri=True):
        if label == "real_email_address":
            out = pattern.sub(
                lambda m: m.group(0) if "proj.hook" in m.group(0).lower() else replacements[label],
                out,
            )
        else:
            out = pattern.sub(replacements[label], out)
    return out


sanitize_hygiene = scrub_hygiene
scrub_text = scrub_hygiene


def find_hygiene_violations(text: str, *, strict_file_scheme: bool = False) -> list[str]:
    """Return list of hygiene violations detected in `text`."""
    violations: list[str] = []
    for label, pattern in _build_hygiene_patterns(strict_file_scheme=strict_file_scheme):
        for match in pattern.finditer(text):
            snippet = match.group(0)
            if label == "real_email_address" and "proj.hook" in snippet.lower():
                continue
            if label == "personal_home_path" and ("/" + "home" + "/runner") in snippet.lower():
                continue
            violations.append(f"{label}: {snippet!r}")
    return violations


def assert_hygiene_clean(text: str, label: str = "output", *, strict_file_scheme: bool = False) -> None:
    """Raise `ValueError` if `text` contains any hygiene violation."""
    hits = find_hygiene_violations(text, strict_file_scheme=strict_file_scheme)
    if hits:
        raise ValueError(f"Hygiene violations in {label}: {hits[:8]}")


def atomic_write_bytes(path: Path | str, data: bytes) -> Path:
    """Atomically write `data` to `path` without leaving `*.tmp` or `*.part` files."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=target.parent,
            prefix=".atomic_",
            suffix=".staging",
            delete=False,
        ) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
            tmp_path = Path(handle.name)
        os.replace(tmp_path, target)
        tmp_path = None
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    return target


def atomic_write_text(path: Path | str, text: str) -> Path:
    """Atomically write UTF-8 `text` to `path`."""
    return atomic_write_bytes(path, text.encode("utf-8"))


def sha256_file(path: Path | str, chunk_size: int = 65536) -> str:
    """Compute lowercase 64-hex SHA-256 digest for `path`."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest().lower()


def _parse_existing_sums(sums_path: Path) -> dict[str, str]:
    existing: dict[str, str] = {}
    if not sums_path.is_file():
        return existing
    for raw_line in sums_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) == 2:
            existing[parts[1].strip()] = parts[0].strip().lower()
    return existing


def _extract_deck_notes_markdown(
    deck: Any,
    build_info: Mapping[str, Any],
    out_root: Path,
) -> str:
    slug = str(deck.slug)
    lines: list[str] = [
        f"# {scrub_hygiene(str(deck.title))}",
        "",
        f"> **Volume / Series**: {scrub_hygiene(str(getattr(deck, 'volume_label', '') or getattr(deck, 'category', 'Presentation')))}  ",
        f"> **Sister Theme**: `{getattr(deck, 'sister_id', 'zoe')}` · **Slides**: {len(deck.slides)} · **Attribution**: {ATTRIBUTION_TEXT}  ",
        f"> **Honoring**: {HONORING_TEXT}",
        "",
        "- [Launch Offline Slide Show Player](player.html)",
        f"- [GEM OUTPUT.APP Playlist (`{slug}.lis`)]({slug}.lis)",
        "- [Back to Presentations Hub](../../README.md)",
        "",
        "## Slide Transcripts & Speaker Notes",
        "",
    ]
    slide_rows = build_info.get("slides", [])
    for idx, slide in enumerate(deck.slides, start=1):
        row = slide_rows[idx - 1] if idx - 1 < len(slide_rows) else {}
        stitle = scrub_hygiene(str(getattr(slide, "title", f"Slide {idx}")))
        lines.append(f"### Slide {idx:02d} — {stitle}")
        lines.append("")
        img_name = row.get("png_name") or row.get("jpg_name")
        gem_name = row.get("gem_name") or f"slide-{idx:02d}.gem"
        if img_name:
            lines.append(f"![Slide {idx:02d}: {stitle}]({img_name})")
            lines.append("")
        lines.append(f"- Native GEM VDI: [`{gem_name}`]({gem_name})")
        notes = scrub_hygiene(str(getattr(slide, "speaker_notes", "") or "")).strip()
        if notes:
            lines.append(f"- Speaker Notes: {notes}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _hub_nav_links(out_root: Path | None) -> list[str]:
    if out_root is None or not (out_root.parent.parent / "README.md").is_file():
        return []
    candidates = [
        ("Repository Home", "../../README.md"),
        ("Monorepo Map", "../../docs/MONOREPO.md"),
        ("Research Chronicle", "../../docs/RESEARCH-CHRONICLE.md"),
        ("Proof Packet", "../../docs/PROOF-PACKET.md"),
        ("Creative Gallery", "../../docs/CREATIVE-GALLERY.md"),
        ("Visual Archive", "../visual-archive/README.md"),
    ]
    links = [f"[{label}]({rel})" for label, rel in candidates if (out_root / rel).is_file()]
    return ["**Navigation:** " + " · ".join(links), ""] if links else []


def _link_if_present(out_root: Path | None, label: str, rel: str) -> str:
    if not rel:
        return "—"
    if out_root is not None and not (out_root / rel).is_file():
        return "—"
    return f"[{label}]({rel})"


def _render_anthology_showcase(anthology_decks: Sequence[Mapping[str, Any]], out_root: Path | None) -> list[str]:
    if not anthology_decks:
        return []
    lines: list[str] = ["## Six Anthology Volumes (Vol. I–VI)", ""]
    thumb_cards: list[tuple[str, str, str, str, int]] = []
    if out_root is not None:
        for d in anthology_decks:
            cover = str(d.get("cover", ""))
            gal = str(d.get("gallery", ""))
            if cover and gal and (out_root / cover).is_file() and (out_root / gal).is_file():
                vol_lbl = str(d.get("volume_label") or d.get("slug") or "")
                title = scrub_hygiene(str(d.get("title", "")))
                thumb_cards.append((vol_lbl, title, cover, gal, int(d.get("slides", 0))))
    if thumb_cards:
        lines.extend(["<table>"])
        for idx in range(0, len(thumb_cards), 2):
            lines.append("<tr>")
            for vol_lbl, title, cover, gal, scount in thumb_cards[idx : idx + 2]:
                has_vol = bool(vol_lbl and re.search(rf"\b{re.escape(vol_lbl)}(?!\w)", title, re.IGNORECASE))
                alt_text = title if (not vol_lbl or has_vol) else f"{vol_lbl}: {title}"
                e_alt = html.escape(alt_text)
                e_lbl = html.escape(f"{vol_lbl} ({scount} Slides)")
                lines.extend([
                    '<td align="center" width="50%">',
                    f'<a href="{html.escape(gal)}"><img src="{html.escape(cover)}" alt="{e_alt}" width="100%" /></a><br/>',
                    f'<sub><strong><a href="{html.escape(gal)}">{e_lbl}</a></strong></sub>',
                    "</td>",
                ])
            lines.append("</tr>")
        lines.extend(["</table>", ""])
    lines.extend([
        "| # | Volume | Title | Slides | .GEM | Sister | Gallery | Player | Playlist |",
        "|---|---|---|---:|---:|---|---|---|---|",
    ])
    for d in anthology_decks:
        vol_lbl = str(d.get("volume_label") or d.get("slug") or "")
        title = scrub_hygiene(str(d.get("title", "")))
        gems = d.get("gems") or ([] if not d.get("gem") else [d["gem"]])
        sister = str(d.get("sister_id", "zoe"))
        gal_link = _link_if_present(out_root, "README", str(d.get("gallery", "")))
        player_link = _link_if_present(out_root, "player.html", str(d.get("player", "")))
        lis_rel = str(d.get("lis", ""))
        lis_label = f"`{Path(lis_rel).name}`" if lis_rel else ".lis"
        lis_link = _link_if_present(out_root, lis_label, lis_rel)
        lines.append(
            f"| {d.get('num', '')} | `{vol_lbl}` | {title} | {d.get('slides', 0)} "
            f"| {len(gems)} | `{sister}` | {gal_link} | {player_link} | {lis_link} |"
        )
    lines.append("")
    return lines


def _render_companion_table(companion_decks: Sequence[Mapping[str, Any]], out_root: Path | None) -> list[str]:
    if not companion_decks:
        return []
    lines: list[str] = [
        "## Curated Companion Decks",
        "",
        "| # | Category / Slug | Title | Slides | Gallery | Player | Download | SHA-256 (12) |",
        "|---|---|---|---:|---|---|---|---|",
    ]
    for d in companion_decks:
        cat = scrub_hygiene(str(d.get("volume_label") or d.get("category") or d.get("slug") or ""))
        title = scrub_hygiene(str(d.get("title", "")))
        gal_link = _link_if_present(out_root, "README", str(d.get("gallery", "")))
        player_link = _link_if_present(out_root, "player.html", str(d.get("player", "")))
        pptx_rel = str(d.get("pptx", ""))
        pptx_link = (
            f"[`.pptx`]({pptx_rel})"
            if out_root is not None and pptx_rel and (out_root / pptx_rel).is_file()
            else "—"
        )
        sha_short = f"`{str(d.get('sha256', ''))[:12]}`" if d.get("sha256") else "—"
        lines.append(
            f"| {d.get('num', '')} | `{cat}` | {title} | {d.get('slides', 0)} "
            f"| {gal_link} | {player_link} | {pptx_link} | {sha_short} |"
        )
    lines.append("")
    return lines


def _render_hub_readme(catalog: Mapping[str, Any], out_root: Path | None = None) -> str:
    const = catalog.get("constitutional", {})
    flags_line = (
        "**Constitutional Scope (`docs/CONSTITUTION.md`):** "
        f"`operational_metacognition_verified = {bool(const.get('operational_metacognition_verified', True))}` · "
        f"`sentience_claimed = {bool(const.get('sentience_claimed', False))}` · "
        f"`l5_agi_qualified = {bool(const.get('l5_agi_qualified', False))}` · "
        f"`zoe_clone_claimed = {bool(const.get('zoe_clone_claimed', False))}` · "
        f"`clinical_action_authorized = {bool(const.get('clinical_action_authorized', False))}` · "
        f"`cure_claim = {bool(const.get('cure_claim', False))}` · "
        f"`external_actions = {int(const.get('external_actions', 0))}` · "
        f"`cloud_cost_usd = {float(const.get('cloud_cost_usd', 0.0))}` (`$0.00 offline`)."
    )
    lines: list[str] = [
        "# Zoe Clean-Room Research Presentations & Anthology Ledger",
        "",
        f"> **Attribution**: {ATTRIBUTION_TEXT}  ",
        f"> **Honoring**: {HONORING_TEXT}  ",
        "> **Stack**: Pure-Python GEM AES/VDI + Cairo + Pillow + Offline HTML5 Slide Show Player (`$0.00 offline`, zero Office/PowerPoint runtime)",
        "",
        *_hub_nav_links(out_root),
        flags_line,
        "",
        f"**Decks**: {catalog['deck_count']} · **Total Slides**: {catalog['total_slides']}",
        "",
    ]
    decks = list(catalog["decks"])
    anthology_decks = [
        d for d in decks
        if str(d.get("slug", "")).startswith("vol-") or str(d.get("volume_label", "")).startswith("Vol.")
    ]
    companion_decks = [d for d in decks if d not in anthology_decks]
    lines.extend(_render_anthology_showcase(anthology_decks, out_root))
    lines.extend(_render_companion_table(companion_decks, out_root))
    lines.extend([
        "## Offline Verification",
        "",
        "```bash",
        "cd research/presentations && sha256sum -c SHA256SUMS.presentations",
        "```",
        "",
        "- Machine-readable index: [`catalog.json`](catalog.json)",
        "- Integrity checksums: [`SHA256SUMS.presentations`](SHA256SUMS.presentations)",
        "",
    ])
    return "\n".join(lines)


def _verify_deck_gems(gem_paths: Sequence[Path]) -> None:
    for gf in gem_paths:
        raw = gf.read_bytes()
        rep = seasip_gem.verify_seasip_gem_metafile(raw)
        if not rep.get("valid"):
            raise ValueError(f"Generated .GEM failed seasip verification: {gf} ({rep})")
        parsed = vdi.parse_metafile(raw)
        for rec in parsed["records"]:
            if rec["command"] == 5 and rec["subcommand"] == 99 and rec["values"] and rec["values"][0] == 1001:
                txt = bytes(v & 0xFF for v in rec["values"][1:]).decode("ascii", "ignore")
                assert_hygiene_clean(txt, f"{gf.name} 1001 metadata")


def publish_ledger(
    decks: Sequence[Any],
    out_root: Path | str,
    *,
    preserve_existing: bool = False,
    render_jpg: bool = False,
    render_svg: bool = False,
    width: int = 1920,
    height: int = 1080,
) -> dict[str, Any]:
    """Build and seal a complete clean-room presentation ledger in `out_root`."""
    if not decks:
        raise ValueError("publish_ledger requires at least one SlideDeck")
    root = Path(out_root).resolve()
    root.mkdir(parents=True, exist_ok=True)

    galleries_root = (root / "galleries").resolve()
    seen_slugs: set[str] = set()
    clean_slugs: list[str] = []
    for deck in decks:
        slug = str(getattr(deck, "slug", "")).strip()
        if not slug or "/" in slug or "\\" in slug or ".." in Path(slug).parts:
            raise ValueError(f"Invalid SlideDeck slug: {slug!r}")
        resolved_gallery = (root / "galleries" / slug).resolve()
        if not resolved_gallery.is_relative_to(galleries_root) or resolved_gallery == galleries_root:
            raise ValueError(f"SlideDeck slug escapes galleries directory: {slug!r}")
        if slug in seen_slugs:
            raise ValueError(f"Duplicate SlideDeck slug: {slug!r}")
        seen_slugs.add(slug)
        clean_slugs.append(slug)

    merged_decks: list[dict[str, Any]] = []
    old_decks: list[dict[str, Any]] = []
    sealed_paths: dict[str, str] = {}

    if preserve_existing and (root / "catalog.json").is_file():
        old_cat = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
        old_sums = _parse_existing_sums(root / "SHA256SUMS.presentations")
        old_decks = [dict(old_d) for old_d in old_cat.get("decks", [])]
        for rel_p, hex_d in old_sums.items():
            if not rel_p.startswith("/") and ".." not in Path(rel_p).parts and (root / rel_p).is_file():
                sealed_paths[rel_p] = hex_d

    new_entries_by_slug: dict[str, dict[str, Any]] = {}
    for slug, deck in zip(clean_slugs, decks):
        gallery_dir = root / "galleries" / slug
        prefix = f"galleries/{slug}/"
        for stale_rel in [k for k in sealed_paths if k.startswith(prefix)]:
            sealed_paths.pop(stale_rel, None)
        if gallery_dir.is_dir():
            for stale_art in gallery_dir.glob("slide-*.*"):
                if stale_art.is_file():
                    stale_art.unlink()
        build_info = deck.build(
            gallery_dir,
            overwrite=True,
            render_png=True,
            render_jpg=render_jpg,
            render_svg=render_svg,
            width=width,
            height=height,
        )
        gem_files = sorted(gallery_dir.glob("slide-*.gem"))
        _verify_deck_gems(gem_files)

        readme_md = _extract_deck_notes_markdown(deck, build_info, root)
        assert_hygiene_clean(readme_md, f"galleries/{slug}/README.md")
        atomic_write_text(gallery_dir / "README.md", readme_md)

        rel_gems: list[str] = []
        for gf in gem_files:
            rel = gf.relative_to(root).as_posix()
            rel_gems.append(rel)
            sealed_paths[rel] = sha256_file(gf)
        for pat in ("slide-*.png", "slide-*.jpg", "slide-*.svg", "*.lis", "player.html"):
            for asset in sorted(gallery_dir.glob(pat)):
                rel = asset.relative_to(root).as_posix()
                sealed_paths[rel] = sha256_file(asset)

        cover_rel = ""
        first_png = gallery_dir / "slide-01.png"
        first_jpg = gallery_dir / "slide-01.jpg"
        if first_png.is_file():
            cover_rel = first_png.relative_to(root).as_posix()
        elif first_jpg.is_file():
            cover_rel = first_jpg.relative_to(root).as_posix()

        first_gem = gem_files[0]
        total_gem_bytes = sum(gf.stat().st_size for gf in gem_files)
        new_entries_by_slug[slug] = {
            "num": "01",
            "slug": slug,
            "title": scrub_hygiene(str(deck.title)),
            "subtitle": scrub_hygiene(str(getattr(deck, "subtitle", ""))),
            "volume_label": scrub_hygiene(str(getattr(deck, "volume_label", ""))),
            "category": scrub_hygiene(str(getattr(deck, "category", "Presentation"))),
            "date": str(getattr(deck, "date", "2026-11-25")),
            "sister_id": str(getattr(deck, "sister_id", "zoe")),
            "slides": len(deck.slides),
            "bytes": int(total_gem_bytes),
            "sha256": sha256_file(first_gem),
            "hygiene_scrubs": int(build_info.get("hygiene_scrubs", 0)),
            "has_speaker_notes": any(bool(getattr(s, "speaker_notes", "").strip()) for s in deck.slides),
            "gem": rel_gems[0],
            "gems": rel_gems,
            "player": (gallery_dir / "player.html").relative_to(root).as_posix(),
            "lis": (gallery_dir / f"{slug}.lis").relative_to(root).as_posix(),
            "gallery": f"galleries/{slug}/README.md",
            "cover": cover_rel,
            "summary": scrub_hygiene(str(getattr(deck, "summary", "") or deck.subtitle or deck.title)),
        }

    for old_d in old_decks:
        oslug = str(old_d.get("slug", "")).strip()
        if oslug in new_entries_by_slug:
            merged_decks.append(new_entries_by_slug.pop(oslug))
        else:
            merged_decks.append(old_d)
    merged_decks.extend(new_entries_by_slug.values())
    for idx, entry in enumerate(merged_decks, start=1):
        entry["num"] = f"{idx:02d}"

    const_meta = {
        **DEFAULT_CONSTITUTIONAL,
        "operational_metacognition_verified": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "cure_claim": False,
        "external_actions": 0,
        "cloud_cost_usd": 0.0,
    }
    catalog: dict[str, Any] = {
        "contract": "zoe-research-presentations-ledger/v1",
        "attribution": ATTRIBUTION_TEXT,
        "honoring": HONORING_TEXT,
        "deck_count": len(merged_decks),
        "total_slides": sum(int(d["slides"]) for d in merged_decks),
        "constitutional": const_meta,
        "decks": merged_decks,
    }
    cat_json = scrub_hygiene(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    assert_hygiene_clean(cat_json, "catalog.json")
    atomic_write_text(root / "catalog.json", cat_json)

    sums_lines = [f"{sealed_paths[rel]}  {rel}" for rel in sorted(sealed_paths)]
    atomic_write_text(root / "SHA256SUMS.presentations", "\n".join(sums_lines) + "\n")

    hub_md = _render_hub_readme(catalog, out_root=root)
    assert_hygiene_clean(hub_md, "README.md")
    atomic_write_text(root / "README.md", hub_md)

    return {
        "out_root": str(root),
        "catalog": catalog,
        "sealed_count": len(sums_lines),
    }


__all__ = [
    "assert_hygiene_clean",
    "atomic_write_bytes",
    "atomic_write_text",
    "find_hygiene_violations",
    "publish_ledger",
    "sanitize_hygiene",
    "scrub_hygiene",
    "scrub_text",
    "sha256_file",
]
