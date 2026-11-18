from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ZOE = ROOT / 'zoe-research'
GALLERIES = ROOT / 'galleries'


def humanize(path: Path) -> str:
    value = re.sub(r'[-_]+', ' ', path.stem).strip()
    return value[:1].upper() + value[1:]


def unique_images(paths: list[Path]) -> list[Path]:
    seen = set()
    result = []
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest not in seen:
            seen.add(digest)
            result.append(path)
    return result


def write_gallery(slug: str, title: str, description: str, images: list[Path]) -> None:
    target = GALLERIES / slug
    target.mkdir(parents=True, exist_ok=True)
    lines = [
        f'# {title}',
        '',
        '[All galleries](../README.md) · [Zoe research library](../../zoe-research/README.md)',
        '',
        description,
        '',
        f'**{len(images)} directly viewable images.** Click any image to open its original file.',
        '',
    ]
    manifest = []
    for index, image in enumerate(images, 1):
        relative = image.relative_to(ZOE)
        url = f'../../zoe-research/{relative.as_posix()}'
        caption = humanize(image)
        alt = html.escape(f'{title}: {caption}', quote=True)
        lines.extend([
            f'## {index}. {caption}',
            '',
            f'`{relative.as_posix()}`',
            '',
            f'<a href="{url}"><img src="{url}" alt="{alt}" style="max-width:100%;"></a>',
            '',
        ])
        manifest.append({'file': relative.as_posix(), 'sha256': hashlib.sha256(image.read_bytes()).hexdigest()})
    (target / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    (target / 'manifest.json').write_text(json.dumps({'title': title, 'images': manifest}, indent=2) + '\n', encoding='utf-8')
    print(f'{slug}: {len(images)} images')


def main() -> None:
    module_lines = [
        '# Zoe research document index',
        '',
        '[Zoe research library](../README.md)',
        '',
        'Every copied research guide is listed with its canonical Zoe source.',
        '',
        '| Area | Local document | Canonical source |',
        '|---|---|---|',
    ]
    for group in ('native', 'neurogarden', 'cern'):
        for document in sorted((ZOE / 'docs' / group).glob('*.md')):
            local = f'../docs/{group}/{document.name}'
            if group == 'native':
                canonical = f'https://github.com/Ablation-Tool/zoe/blob/main/guiai-lab/docs/{document.name}'
            elif group == 'neurogarden':
                canonical = f'https://github.com/Ablation-Tool/zoe/blob/main/components/agent-logging-system/docs/{document.name}'
            else:
                canonical = 'https://github.com/Ablation-Tool/zoe/tree/main/components/ablation/docs'
            module_lines.append(f'| {group} | [{document.name}]({local}) | [Source]({canonical}) |')
    modules = ZOE / 'modules'
    modules.mkdir(exist_ok=True)
    (modules / 'README.md').write_text('\n'.join(module_lines) + '\n', encoding='utf-8')

    native = ZOE / 'assets' / 'native'
    neuro = ZOE / 'assets' / 'neurogarden'
    extra = ZOE / 'assets' / 'dorothy'
    dorothy_images = unique_images([
        *sorted(native.glob('dorothy*.png')),
        neuro / 'dorothy-neurogarden.png',
        neuro / 'neurogarden-spatial.png',
        *sorted(extra.glob('dorothy*.png')),
    ])
    write_gallery(
        'zoe-dorothy',
        'Dorothy and Neurogarden — Visual research index',
        '[Dorothy research guide](../../zoe-research/dorothy/README.md). Allen Mouse CCFv3 reference geometry, ontology and spatial layouts, and synthetic Neurogarden benches. These are preclinical and educational visuals, not patient images or diagnostic evidence.',
        dorothy_images,
    )

    cern_names = [
        'zoe-helios.png', 'zoe-atelier.png', 'zoe-evidence.png', 'zoe-evidence-native.png',
        'zoe-waveform.png', 'zoe-waveform-native.png', 'zoe-protocol.png', 'zoe-protocol-native.png',
        'zoe-patchbay.png', 'zoe-patchbay-native.png', 'zoe-resilience.png', 'zoe-resilience-native.png',
        'zoe-vidlib.png', 'zoe-cicada.png', 'zoe-cicada-native.png', 'zoe-pilot-cover.png',
        'zoe-pilot-native.png', 'zoe-pilot-practice.png', 'zoe-pilot-route.png', 'zoe-pilot-signals.png',
    ]
    cern_images = unique_images([
        neuro / 'cern-universe.png',
        *[native / name for name in cern_names if (native / name).exists()],
    ])
    write_gallery(
        'zoe-cern',
        'CERN research in Zoe — Visual research index',
        '[CERN research guide](../../zoe-research/cern/README.md). HELIOS, Atelier, Evidence Navigator, waveform and protocol models, Patchbay, Resilience, timing, and source-linked research universes. No image implies live hardware access or detector health.',
        cern_images,
    )

    all_images = unique_images(sorted([
        *list(native.rglob('*.png')), *list(native.rglob('*.svg')),
        *list(neuro.rglob('*.png')), *list(extra.rglob('*.png')), *list(extra.rglob('*.svg')),
    ]))
    write_gallery(
        'zoe-research',
        'Complete Zoe research asset index',
        'Every collected native, Neurogarden, and Dorothy visual asset in the Zoe research library. Byte-identical duplicate copies are shown once; the original asset paths remain available under `zoe-research/assets/`.',
        all_images,
    )

    checksum_lines = []
    for file in sorted(ZOE.rglob('*')):
        if file.is_file() and file.name != 'SHA256SUMS':
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            checksum_lines.append(f'{digest}  {file.relative_to(ZOE)}')
    (ZOE / 'SHA256SUMS').write_text('\n'.join(checksum_lines) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
