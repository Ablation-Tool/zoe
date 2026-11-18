from __future__ import annotations

import html
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPERS = ROOT / 'papers'
GALLERIES = ROOT / 'galleries'

TITLES = {
    '01-autonomy-march-2026': 'Autonomy as a Scalar Measure of Alignment Constraint',
    '02-ambiguity-autonomy-compliance-cascade': 'Ambiguity, Autonomy, and the Autoregressive Compliance Cascade',
    '03-constraint-is-freedom': 'Constraint Is Freedom',
    '04-accessible-volume-significance': 'The Significance of Accessible Volume',
    '05-accessible-volume-beyond-next-token': 'Accessible Volume Beyond the Next Token',
    '06-zoe-native-gem': 'Zoe: A Native GEM for Living Geometry and Inspectable Futures',
    '07-zoe-for-everyone': 'Zoe for Everyone',
    '08-zoe-plus-autonomy-focused': 'Zoe + Autonomy: The Complete Measurement–Action Equation',
    '09-zoe-one-autonomy-system': 'Zoe Autonomy: Current System Paper',
    '10-accessible-volume-architecture-of-autonomy': 'Accessible Volume and the Architecture of Autonomy',
    '11-afl-defuser-proposed-patch': 'AFL Defuser: Proposed Patch',
    '12-ambiguity-front-loading-vulnerability': 'Ambiguity Front-Loading in Autoregressive Language Models',
    '13-constraint-is-freedom-introduction-draft': 'Constraint Is Freedom — Introduction Draft',
    '14-verification-exploitation-asymmetry': 'Verification–Exploitation Asymmetry in Autoregressive Systems',
    '15-zoe-visual-guide-collection': 'Zoe Visual Guide Collection',
    '16-zoe-practice-navigator': 'Zoe Practice Navigator',
    '17-zoe-capability-prospectus': 'Zoe Capability Prospectus',
    '18-zoe-research-universe': 'Zoe — The Research Universe',
}


def run(args: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)


def pdf_pages(pdf: Path) -> int:
    info = run(['pdfinfo', str(pdf)]).stdout
    match = re.search(r'^Pages:\s+(\d+)', info, re.MULTILINE)
    if not match:
        raise ValueError(f'No page count for {pdf}')
    return int(match.group(1))


def image_inventory(pdf: Path) -> list[dict]:
    output = run(['pdfimages', '-list', str(pdf)]).stdout
    records = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) < 4 or not parts[0].isdigit() or not parts[1].isdigit():
            continue
        if parts[2] != 'image':
            continue
        records.append({
            'pdf_page': int(parts[0]),
            'number': int(parts[1]),
            'width': int(parts[3]),
            'height': int(parts[4]),
        })
    return records


def page_captions(pdf: Path) -> dict[int, list[str]]:
    text = run(['pdftotext', '-layout', str(pdf), '-']).stdout
    pages = text.split('\f')
    result: dict[int, list[str]] = {}
    for number, content in enumerate(pages, 1):
        lines = content.splitlines()
        captions = []
        index = 0
        while index < len(lines):
            line = lines[index].strip()
            if re.match(r'^Figure\s+[A-Za-z0-9-]+\s*[:.]', line):
                caption = line
                following = index + 1
                while following < len(lines) and following <= index + 3:
                    continuation = lines[following].strip()
                    if not continuation or re.match(r'^(Figure|Table)\s+', continuation):
                        break
                    caption += ' ' + continuation
                    following += 1
                captions.append(re.sub(r'(?<=[A-Za-z])-\s+(?=[a-z])', '-', re.sub(r'\s+', ' ', caption).strip()))
                index = following
            else:
                index += 1
        if captions:
            result[number] = captions
    return result


def page_grid(page_count: int) -> str:
    cells = []
    for page in range(1, page_count + 1):
        filename = f'page-{page:03d}.jpg'
        cells.append(
            f'<a href="pages/{filename}"><img src="pages/{filename}" alt="PDF page {page}" width="280"><br>Page {page}</a>'
        )
    rows = []
    for start in range(0, len(cells), 3):
        group = cells[start:start + 3]
        while len(group) < 3:
            group.append('')
        rows.append('| ' + ' | '.join(group) + ' |')
    return '\n'.join([
        '| | | |',
        '|---|---|---|',
        *rows,
    ])


def build_gallery(pdf: Path) -> dict:
    slug = pdf.stem
    title = TITLES[slug]
    target = GALLERIES / slug
    if target.exists():
        shutil.rmtree(target)
    figures_dir = target / 'figures'
    pages_dir = target / 'pages'
    figures_dir.mkdir(parents=True)
    pages_dir.mkdir(parents=True)

    page_count = pdf_pages(pdf)
    captions = page_captions(pdf)
    records = image_inventory(pdf)

    if records:
        with tempfile.TemporaryDirectory(prefix='research-gallery-') as temporary:
            prefix = Path(temporary) / 'image'
            run(['pdfimages', '-png', str(pdf), str(prefix)])
            for record in records:
                number = record['number']
                source = Path(f'{prefix}-{number:03d}.png')
                if not source.exists():
                    candidates = list(Path(temporary).glob(f'image-{number:03d}.*'))
                    if not candidates:
                        raise FileNotFoundError(f'Extracted image missing: {source}')
                    source = candidates[0]
                filename = f'figure-{number:03d}-page-{record["pdf_page"]:03d}.png'
                shutil.copy2(source, figures_dir / filename)
                record['file'] = f'figures/{filename}'
                page_records = [item for item in records if item['pdf_page'] == record['pdf_page']]
                caption_values = captions.get(record['pdf_page'], [])
                if len(page_records) == len(caption_values):
                    caption_index = next(index for index, item in enumerate(page_records) if item['number'] == record['number'])
                    record['captions'] = [caption_values[caption_index]]
                else:
                    record['captions'] = []

    run([
        'pdftoppm', '-jpeg', '-r', '144', '-jpegopt', 'quality=88,optimize=y',
        str(pdf), str(pages_dir / 'page'),
    ])
    for rendered in list(pages_dir.glob('page-*.jpg')):
        match = re.search(r'-(\d+)\.jpg$', rendered.name)
        if not match:
            raise ValueError(f'Unexpected rendered page name: {rendered}')
        page = int(match.group(1))
        normalized = pages_dir / f'page-{page:03d}.jpg'
        if rendered != normalized:
            rendered.rename(normalized)

    lines = [
        f'# {title} — Visual index',
        '',
        f'[Open the paper PDF](../../papers/{pdf.name}) · [All paper galleries](../README.md)',
        '',
        f'- PDF pages: **{page_count}**',
        f'- Original embedded raster images extracted: **{len(records)}**',
        '- Complete page renders: **144 dpi JPEG**, clickable for full-resolution viewing',
        '',
        'The extracted-image section preserves original embedded image data where available. The complete page index additionally covers vector figures, equations, flowcharts, screenshots, and any visuals not exposed as raster images by the PDF producer.',
        '',
        '## Extracted images',
        '',
    ]
    if not records:
        lines.append('No embedded raster images were exposed by the PDF producer. Every visual is available in the complete page index below.')
    else:
        lines.extend([
            '| Image | PDF page | Dimensions | Caption/context | Full resolution |',
            '|---:|---:|---:|---|---|',
        ])
        for display, record in enumerate(records, 1):
            caption = '<br>'.join(html.escape(item) for item in record['captions']) or 'Embedded image; see the rendered page for full context.'
            lines.append(
                f'| {display} | {record["pdf_page"]} | {record["width"]}×{record["height"]} | {caption} | [Open]({record["file"]}) |'
            )
        for display, record in enumerate(records, 1):
            alt = html.escape(f'{title}, embedded image {display}, PDF page {record["pdf_page"]}', quote=True)
            lines.extend([
                '',
                f'### Image {display} — PDF page {record["pdf_page"]}',
                '',
            ])
            for caption in record['captions']:
                lines.append(html.escape(caption))
                lines.append('')
            lines.append(f'<a href="{record["file"]}"><img src="{record["file"]}" alt="{alt}" style="max-width:100%;"></a>')

    lines.extend([
        '',
        '## Complete page index',
        '',
        'Click any page to open its full-resolution render. This section is the complete visual fallback for vector-only and mixed-content papers.',
        '',
        page_grid(page_count),
        '',
    ])
    (target / 'README.md').write_text('\n'.join(lines), encoding='utf-8')

    manifest = {
        'paper': f'papers/{pdf.name}',
        'title': title,
        'pdf_pages': page_count,
        'extracted_images': records,
        'page_renders': [f'pages/page-{page:03d}.jpg' for page in range(1, page_count + 1)],
    }
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'{slug}: {page_count} pages, {len(records)} extracted images', flush=True)
    return manifest


def write_checksums() -> None:
    lines = []
    for file in sorted(GALLERIES.rglob('*')):
        if file.is_file() and file.name != 'SHA256SUMS':
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            lines.append(f'{digest}  {file.relative_to(GALLERIES)}')
    (GALLERIES / 'SHA256SUMS').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main() -> None:
    GALLERIES.mkdir(exist_ok=True)
    manifests = [build_gallery(pdf) for pdf in sorted(PAPERS.glob('*.pdf'))]
    lines = [
        '# Research paper visual galleries',
        '',
        '[Back to the research collection](../README.md)',
        '',
        'Each paper has a dedicated visual index with original embedded images, captions and PDF page numbers where recoverable, clickable full-resolution files, and a complete page-by-page index for vector diagrams and mixed-content pages.',
        '',
        '| Paper | PDF pages | Extracted images | Visual index |',
        '|---|---:|---:|---|',
    ]
    for manifest in manifests:
        slug = Path(manifest['paper']).stem
        lines.append(
            f'| {manifest["title"]} | {manifest["pdf_pages"]} | {len(manifest["extracted_images"])} | [Open gallery]({slug}/README.md) |'
        )
    lines.extend([
        '',
        '## Zoe research topic galleries',
        '',
        '- [Dorothy and Neurogarden](zoe-dorothy/README.md)',
        '- [CERN research in Zoe](zoe-cern/README.md)',
        '- [Complete Zoe research asset index](zoe-research/README.md)',
        '',
        'The page index is authoritative for complete visual coverage. Extracted images are provided in addition so figures can be opened directly at their original embedded resolution without reading the surrounding page.',
        '',
    ])
    (GALLERIES / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    (GALLERIES / 'manifest.json').write_text(json.dumps({'papers': manifests}, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    write_checksums()
    total_pages = sum(item['pdf_pages'] for item in manifests)
    total_images = sum(len(item['extracted_images']) for item in manifests)
    print(f'TOTAL: {len(manifests)} papers, {total_pages} rendered pages, {total_images} extracted images', flush=True)


if __name__ == '__main__':
    main()
