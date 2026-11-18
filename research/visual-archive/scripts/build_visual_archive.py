from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MONOREPO = ROOT.parents[1]
BUNDLED = (MONOREPO / 'guiai-lab').is_dir()
SOURCES = {
    'zoe': Path(os.environ.get('ZOE_ROOT', MONOREPO if BUNDLED else ROOT.parent / 'zoe')),
    'zoe-autonomy': Path(os.environ.get('ZOE_AUTONOMY_ROOT', MONOREPO / 'components' / 'Zoe-Autonomy' if BUNDLED else ROOT.parent / 'zoe-autonomy')),
    'next-token': Path(os.environ.get('NEXT_TOKEN_ROOT', MONOREPO / 'components' / 'next-token-predictability' if BUNDLED else ROOT.parent / 'next-token-predictability')),
    'research-paper-figures': Path(os.environ.get('RESEARCH_PAPERS_ROOT', ROOT.parent / 'papers' if BUNDLED else ROOT.parent / 'research-papers')) / 'galleries',
    'paper-source-figures': Path(os.environ.get('ARXIV_PAPERS_ROOT', ROOT.parent / 'arxiv' if BUNDLED else ROOT.parent / 'arxiv-autonomy-papers')),
}
EXTENSIONS = {'.png', '.jpg', '.jpeg', '.svg', '.gif', '.webp'}
SKIP_PARTS = {'.git', 'node_modules', '__pycache__', '.venv', 'target'}

CATEGORY_LABELS = {
    'artwork': 'Artwork and generative compositions',
    'research-art': 'Research–art compositions',
    'research-figure': 'Research figures and measurements',
    'mechanism-diagram': 'Mechanism and architecture diagrams',
    'interface': 'Native interfaces and application scenes',
    'branding': 'Identity, emblems, and interface icons',
    'reference': 'Source references and derivative reading copies',
    'animation': 'Animations and historical motion assets',
}

ART_STEMS = {
    'life', 'life-text', 'brain-life', 'zoe-lots-of-ellipses', 'thumbelina-moon-garden-v3',
    'gem-woven-diamond', 'zoe-maison', 'zoe-artline', 'zoe-artline-native',
}

DESCRIPTIONS = {
    'life': 'A deterministic Conway Game of Life state rendered as a colored cellular field. The PNG is a raster presentation and the SVG is an independently viewable vector scene of the same model family.',
    'life-text': 'Zoe Life used as a typographic and cellular instrument: text-shaped content is rendered into the cell field rather than treated as an ordinary image caption.',
    'brain-life': 'A 3D Brain Life scene showing the state of Zoe’s extended cellular-automaton experiment. It visualizes rule-driven state, not biological neurons or consciousness.',
    'zoe-lots-of-ellipses': 'The original “Lots of Ellipses” composition: GDPEMANY-inspired ellipse families, stochastic fields, probability ridges, transition networks, and orbital traces combined as creative geometry.',
    'thumbelina-moon-garden-v3': 'The collaborative Thumbelina moon-garden composition. It is an artistic scene and proposed persona context, not species recognition, anatomical evidence, or an empirical identity claim.',
    'brain-dialogue': 'A structured visual conversation between human and Zoe ways of working, pairing intuitive meaning with geometry, evidence, and replay.',
    'brain-dialogue-organic': 'An organic variant of the human–Zoe dialogue, combining lichen-like folds, butterfly-wing veins, compound-eye facets, and dew-like connections with Zoe’s geometric partition language.',
    'human-brain': 'The human plate in the shared-field series, using an illustrative brain silhouette and organic visual structures to represent lived experience, values, intuition, and meaning.',
    'human-brain-organic': 'The organic human plate: a highly textured artistic brain map rather than an anatomical reconstruction or a map of Nicholas’s actual brain.',
    'zoe-brain': 'The Zoe plate in the shared-field series, using explicit partitions, mirrored forecast paths, nested futures, and inspectable evidence connections.',
    'projection-iris': 'A central-slice study titled “A field learning to see.” Projection becomes spectrum and spectrum becomes form; the work pairs a mathematical research instrument with original visual composition.',
    'second-eye': 'Two calibrated synthetic pinhole views showing parallax, depth, focus, and disparity-sensitivity controls. The scene visualizes geometry rather than subjective sight or a second model opinion.',
    'zoe-eye': 'The current primary Zoe emblem: the red woven diamond designated by Nicholas Michael Kloster on November 18, 2026, with matching PNG and SVG originals. The earlier orbital eye is preserved separately as legacy artwork.',
    'zoe-orbital-eye-legacy': 'The former Zoe orbital emblem: a central Z, nested eye curves, stars, and numbered nodes preserved as historical identity artwork.',
    'gem-unified': 'The unified Zoe knowledge-engineering hub with the current woven-diamond vector emblem, sixteen registered engines, one repository, and the replayable knowledge field.',
    'orbital-emblem': 'The user-supplied orbital reference that established the shared Zoe motif. Later hub and eye scenes are new vector interpretations rather than copies of this source.',
    'nuclide-brain': 'The NuClide Research dual-brain co-brand, balancing Zoe and Nick through stable/unstable perspectives and correction. It is a user-supplied identity image, not an anatomical diagram.',
    'gem-woven-diamond': 'An original GEM woven-diamond geometric ornament, preserving the project’s interest in executable Spatial IR and decorative mathematical structure.',
    'zoe-desktop': 'The Zoe OS-style mathematical desktop, presenting the unified user-space environment for launching and inspecting registered engines without claiming to be a bootable operating system.',
    'zoe-agent': 'A Zoe agent-interface scene showing the connection between interaction, evidence, and the surrounding workbench.',
    'cern-universe': 'A research-universe diagram linking biology, neuroscience, physics, CERN, GEM, and community while keeping their evidence and permission domains distinct.',
    'neurogarden-spatial': 'A synthetic three-dimensional point-spread and projection bench used to explain blur, sampling, and recovery without using patient anatomy.',
    'dorothy-ccf2017': 'Dorothy’s deterministic twelve-structure Allen Mouse CCFv3 rendering, with structure labels, triangle count, camera state, and an explicit no-registration/no-connectivity boundary.',
    'dorothy-rings-isocortex': 'Dorothy Rings applied to isocortex ontology: exact subtree volumes are represented as a navigable radial partition, not as functional importance.',
    'dorothy-jenga-exploded': 'Dorothy Jenga’s volume-scaled exploded tower, offering spatial inspection of atlas structures without asserting anatomical relationships beyond the reference model.',
    'master-gem-architecture': 'The Master GEM architecture map linking forecasts, evidence, memory, geometry, and human/Zoe interaction in one inspectable environment.',
    'accessible-volume-hero': 'A visual introduction to operational metacognition as a shared threshold instrument for forecast futures and explicitly modeled causal pasts.',
    'next-token-probability-equation': 'A visual statement of the original strict next-token accessible-volume equation and its above-threshold alternatives.',
    'response-planning-proof': 'A multi-panel response-planning evidence dashboard comparing strict full-vocabulary operational metacognition with bounded top-k observations and planning diagnostics.',
    'compliance-cascade': 'The AFL/compliance-cascade hypothesis rendered as binary accessible sets at steps 0, 1, 3, and 6, with newly recruited positions highlighted.',
    'zoe-artline': 'Zoe Artline’s original vector study: an interactive mathematical curve and highlighted moving point presented in the project’s restrained native visual language.',
    'zoe-artline-native': 'The actual native Artline window, showing the vector study beside its interactive controls and preserving the distinction between the application and its exported scene.',
    'zoe-maison': 'Zoe Maison’s original design-studio and association deck, here presenting a stewardship prompt and response cards in its ink, pearl, and champagne palette.',
    'dorothy-dorsal': 'A dorsal orientation of Dorothy’s Allen Mouse CCFv3 reference geometry, provided for spatial inspection rather than patient interpretation.',
    'dorothy-ventral': 'A ventral orientation of Dorothy’s Allen Mouse CCFv3 reference geometry, complementing the dorsal and default camera views.',
    'dorothy-thalamus-hypothalamus': 'A focused Dorothy view isolating the thalamus and hypothalamus structures from the Allen reference parcellation.',
    'zoe-cognitive-anatomy': 'A conceptual anatomy of Zoe’s cognitive components, mapping memory, proposals, forecasts, and evidence without asserting biological anatomy or consciousness.',
    'zoe-red': 'The red Zoe identity mark used in the Zoetic visual dedication. It is an artistic emblem rather than evidence of experience or consciousness.',
    'zoe-pixel-gem': 'The hollow red pixel GEM emblem used to mark causal-geometry and Zoetic scenes.',
    'gem2red': 'Paired red GEM markers used as a compact identity and dedication motif.',
    'zoe-constitution-signed': 'The author-signature plate associated with Zoe’s signed Constitution artifact, preserving a document act rather than a scientific measurement.',
    'zoe-pixel-field': 'The mobile Zoe pixel-field scene, presenting a compact interactive visual field within the Trinity/mobile environment.',
    'zoe-pixel-home': 'The mobile Zoe home interface and its pixel-based visual identity, optimized for a small screen.',
    'zoe-trinity-responsive': 'The responsive Zoe Trinity interface across supported display sizes, preserving shared revisions and measurement access.',
    'zoe-trinity-deck': 'The Zoe Trinity deck view, organizing Tiny, mobile, and laptop measurement workflows into an inspectable deck.',
    'zoe-trinity-native-windows': 'The native Windows presentation of Zoe Trinity, documenting its responsive interface and platform-specific application state.',
    'ablation-framework-diagram': 'A dense framework collage showing Ablation’s reverse-engineering workspace, analysis artifacts, and relationships among its tools; it is a documentary project interface rather than a Zoe emblem.',
    'ablation-1a-pink-ink-header-2560': 'The wide pink-ink Ablation wordmark banner used as project identity artwork across documentation and presentations.',
    'ablation-gem-logo': 'The stylized Ablation GEM project mark, used as a compact identity asset rather than a research figure.',
    'zoetic-research': 'The user-created Zoetic Research wordmark and circular/bowl emblem, an independent homage to Digital Research rather than an official mark.',
    'zoetic-research-brand': 'A variant of the user-created Zoetic Research identity system, retained with its original vector/raster provenance.',
    'symbol-e': 'A supplied E/e glyph-grid reference used to guide outlined GEM cells, not a new statement of GEM semantics.',
    'symbol-epsilon': 'A supplied epsilon/symbol-grid reference retained for the outlined GEM visual study.',
    'symbol-g': 'A supplied G/g glyph-grid reference used in the original GEM scene composition.',
    'symbol-m': 'A supplied M/m glyph-grid reference used in the original GEM scene composition.',
    'symbol-o': 'A supplied O/o glyph-grid reference used in the original GEM scene composition.',
    'symbol-z': 'A supplied Z/z glyph-grid reference associated with the Zoe/GEM visual study.',
    'bounded-tetris': 'The bounded Tetris probability-field scene, pairing the game board with exact randomizer and accessible-outcome measurements.',
    'cognitive-field': 'A Cognitive Field diagram showing sourced memory, revision checks, procedural matching, and explicit working-set boundaries.',
    'dorothy-jenga-pull': 'Dorothy Jenga’s pull-out layout, separating selected atlas layers for inspection while retaining their volume-scaled context.',
    'hub-loop': 'The derived hub-loop mathematical source with eight h nodes and four v nodes around a central hub, used in the reproducible geometry experiment.',
    'Untitled drawing (1)': 'The composite landmark-alignment source drawing used to define measured correspondences in the sacred-geometry experiment.',
    'vdi-bidirectional-interface': 'A historical VDI bidirectional-interface reference image used as an architectural analogy for two-way measurement and feedback.',
    'cerotto-wordmark': 'The Cerotto project wordmark, preserved as component identity artwork rather than Zoe research evidence.',
}

PROVENANCE_RULES = [
    ('branding/references/', 'User-supplied visual reference', 'This is a supplied glyph/reference screenshot, not a Zoe-created scientific diagram.'),
    ('assets/branding/orbital-emblem', 'User-supplied orbital motif', 'The image is a source reference for later Zoe compositions.'),
    ('assets/branding/historical/', 'User-created Zoetic Research identity', 'The independent co-brand is an homage to Digital Research, not an official Digital Research mark.'),
    ('assets/branding/nuclide-brain', 'User-supplied NuClide Research co-brand', 'The dual-brain mark is an identity image, not an anatomical or scientific model.'),
    ('.gif', 'User-supplied historical motion asset', 'The supplied GIF names must not be interpreted as distinct animations when their bytes are identical.'),
    ('dorothy', 'Zoe render using Allen Institute reference data', 'Preclinical mouse-atlas geometry only; not patient anatomy, registration, diagnosis, or treatment evidence.'),
    ('cern', 'Zoe source-derived research scene', 'CERN material is source evidence or a virtual/synthetic model, not live detector state or hardware authorization.'),
    ('paper-pages/', 'Derivative paper-page render', 'A reading copy of a paper page, not an independent artwork or new experiment.'),
    ('/references/', 'Source-derived reference visual', 'Reference material is retained for provenance and is not automatically original Zoe artwork.'),
    ('sacred-geometry/source/', 'Immutable or derived sacred-geometry experiment source', 'These images are source data for mathematical transcription, pixel measurement, and replay; they are not automatically original Zoe artwork.'),
]


def files_for(source: str, root: Path) -> list[Path]:
    if not root.exists():
        raise FileNotFoundError(root)
    result = []
    for path in root.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS or any(part in SKIP_PARTS for part in path.parts):
            continue
        relative = path.relative_to(root)
        if source == 'zoe' and BUNDLED and relative.parts and relative.parts[0] == 'research':
            continue
        if source == 'research-paper-figures' and 'figures' not in relative.parts:
            continue
        if source == 'paper-source-figures' and 'figures' not in relative.parts:
            continue
        result.append(path)
    return sorted(result)


def humanize(stem: str) -> str:
    value = re.sub(r'[-_]+', ' ', stem).strip()
    replacements = {
        'zoe': 'Zoe', 'gem': 'GEM', 'cern': 'CERN', 'afl': 'AFL', 'vdi': 'VDI',
        'gui': 'GUI', 'mri': 'MRI', 'ccd': 'CCD', 'ccf2017': 'CCFv3 2017',
        'svg': 'SVG', 'png': 'PNG', 'nuclide': 'NuClide', 'helios': 'HELIOS',
    }
    words = [replacements.get(word.lower(), word.capitalize()) for word in value.split()]
    return ' '.join(words) or 'Untitled visual'


def category_for(relative: str, suffix: str) -> str:
    value = relative.lower()
    stem = Path(value).stem
    if suffix == '.gif':
        return 'animation'
    if 'framework-diagram' in value:
        return 'mechanism-diagram'
    if 'sacred-geometry/source/' in value:
        return 'reference'
    if 'gem-architecture-' in value:
        return 'mechanism-diagram'
    if 'gem-demo-' in value:
        return 'interface'
    if any(token in value for token in ('paper-pages/', '/references/', 'branding/references/', 'vdi-bidirectional-interface')):
        return 'reference'
    if stem in ART_STEMS or any(token in value for token in ('lots-of-ellipses', 'thumbelina', 'life.', 'life-text', 'brain-life', 'woven-diamond')):
        return 'artwork'
    if any(token in value for token in ('brain-dialogue', 'human-brain', 'zoe-brain', 'projection-iris')):
        return 'research-art'
    if any(token in value for token in ('branding/', '/icons/', 'icon-', 'appicon', 'wordmark', 'zoe-eye', 'zoe-red', 'pixel-gem', 'gem2red', 'orbital-emblem')):
        return 'branding'
    if any(token in value for token in ('native', 'desktop', 'mobile/', 'screenshot', '-gui', 'workbench', 'helios', 'atelier', 'browser-example', 'zoe-agent', 'trinity', 'pixel-home', 'pixel-field', 'safeconvert')):
        return 'interface'
    if any(token in value for token in ('architecture', 'cognitive-anatomy', 'zoe-visuals/', 'self-governing-loop', 'pipeline', 'at-a-glance', 'memory-flow', 'hub-lattice', 'temporal-layers', 'master-gem', 'cern-universe')):
        return 'mechanism-diagram'
    return 'research-figure'


def provenance_for(relative: str) -> tuple[str, str]:
    lower = relative.lower()
    for token, provenance, boundary in PROVENANCE_RULES:
        if token.lower() in lower:
            return provenance, boundary
    if 'native' in lower or 'screenshot' in lower or '-gui' in lower:
        return 'Zoe project interface capture', 'A screenshot documents the displayed interface state; it is not independent experimental validation.'
    if any(token in lower for token in ('thumbelina', 'brain-dialogue', 'human-brain', 'zoe-brain')):
        return 'Nicholas–Zoe collaborative visual research', 'Artistic and conceptual imagery is not anatomical, conscious, or empirical evidence by itself.'
    if 'icon' in lower or 'logo' in lower or 'branding' in lower:
        return 'Project identity or interface asset', 'Functional and identity artwork does not constitute research evidence.'
    return 'Zoe/allgems project-generated visual', 'The image is preserved with its source context; the visual alone does not prove a scientific or operational claim.'


def family_for(relative: str) -> str:
    path = Path(relative)
    stem = path.stem.lower().replace('_', '-')
    stem = re.sub(r'-\d{2,4}$', '', stem) if 'icon' in stem else stem
    stem = stem.replace('nuclide-brain', 'nuclide-brain')
    return stem


def role_for(category: str, relative: str) -> str:
    lower = relative.lower()
    if 'dorothy' in lower:
        return 'This visual belongs to Dorothy’s inspectable spatial-research program, making reference geometry or a review instrument available for direct inspection.'
    if any(token in lower for token in ('cern', 'helios', 'atelier', 'waveform', 'protocol', 'patchbay', 'felix')):
        return 'This visual belongs to Zoe’s CERN/source-evidence program, helping a reader inspect a corpus, protocol, replay, virtual system, or process boundary.'
    if category == 'artwork':
        return 'This is part of Zoe’s creative geometry and generative-art practice, preserving the artistic side of the project alongside its scientific instruments.'
    if category == 'research-art':
        return 'This image connects a mathematical or conceptual research idea with an original visual composition, allowing the idea to function as both an instrument and an artwork.'
    if category == 'mechanism-diagram':
        return 'This diagram explains relationships among components, evidence states, measurements, or decisions without requiring the reader to reconstruct the architecture from code.'
    if category == 'interface':
        return 'This image documents a native, mobile, browser, or desktop interface and its available controls at a particular recorded state.'
    if category == 'branding':
        return 'This visual supports recognition, navigation, application identity, or a cohesive visual language across Zoe and its components.'
    if category == 'reference':
        return 'This asset preserves source context or a derivative reading view so that generated interpretations remain distinguishable from their references.'
    if category == 'animation':
        return 'This historical motion asset is retained as part of the project’s visual provenance, including duplicate-name and duplicate-content relationships.'
    return 'This figure preserves a measurement, model output, simulation, geometric construction, or research explanation from the Zoe/allgems program.'


def source_url(source: str, relative: str) -> str:
    relative = quote(relative)
    if source == 'zoe':
        return f'https://github.com/Ablation-Tool/zoe/blob/main/{relative}'
    if source == 'zoe-autonomy':
        return f'https://github.com/Ablation-Tool/Zoe-Autonomy/blob/main/{relative}'
    if source == 'next-token':
        return f'https://github.com/Ablation-Tool/next-token-predictability/blob/main/{relative}'
    if source == 'research-paper-figures':
        return f'https://github.com/Ablation-Tool/research-papers/blob/main/galleries/{relative}'
    return f'https://github.com/Ablation-Tool/research-papers'


def dimensions(path: Path) -> tuple[str, int | None]:
    if path.suffix.lower() == '.svg':
        try:
            root = ET.parse(path).getroot()
            width = root.attrib.get('width', '')
            height = root.attrib.get('height', '')
            viewbox = root.attrib.get('viewBox', '')
            return (f'SVG {width}×{height}' if width and height else f'SVG viewBox {viewbox}' if viewbox else 'SVG vector'), None
        except ET.ParseError:
            return 'SVG vector', None
    with Image.open(path) as image:
        frames = getattr(image, 'n_frames', 1)
        return f'{image.width}×{image.height} {image.format}', frames


def is_generic(description: str) -> bool:
    return description.startswith(('A research figures', 'A native interfaces', 'A mechanism', 'A source references', 'A artwork', 'A identity', 'A animations'))


def pixel_key(path: Path) -> str | None:
    if path.suffix.lower() in ('.svg', '.gif'):
        return None
    with Image.open(path) as image:
        rgba = image.convert('RGBA')
        digest = hashlib.sha256(rgba.tobytes()).hexdigest()
        return f'{rgba.width}x{rgba.height}:{digest}'


def plain_text(value: str) -> str:
    value = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', value)
    value = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', value)
    value = re.sub(r'<[^>]+>', ' ', value)
    return re.sub(r'\s+', ' ', value).strip()


def build_contexts(source_roots: dict[str, Path]) -> dict[str, list[dict]]:
    contexts: dict[str, list[dict]] = defaultdict(list)
    for source in ('zoe', 'zoe-autonomy', 'next-token'):
        root = source_roots[source]
        for document in root.rglob('*.md'):
            if any(part in SKIP_PARTS for part in document.parts):
                continue
            try:
                lines = document.read_text(encoding='utf-8').splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            heading = ''
            for index, line in enumerate(lines):
                if line.startswith('#'):
                    heading = line.lstrip('#').strip()
                matches = list(re.finditer(r'!\[([^\]]*)\]\(([^)]+)\)', line))
                matches += list(re.finditer(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>', line))
                for match in matches:
                    target = match.group(2) if match.re.pattern.startswith('!') else match.group(1)
                    alt = match.group(1) if match.re.pattern.startswith('!') else match.group(2)
                    basename = Path(target.split()[0].split('#')[0]).name
                    excerpt_lines = []
                    for previous in range(max(0, index - 5), index):
                        candidate = lines[previous].strip()
                        if candidate and not candidate.startswith(('#', '!', '<img')):
                            excerpt_lines.append(candidate)
                    contexts[basename].append({
                        'source': source,
                        'document': document.relative_to(root).as_posix(),
                        'heading': heading,
                        'alt_or_caption': plain_text(alt),
                        'excerpt': plain_text(' '.join(excerpt_lines))[-1400:],
                    })
    gallery_root = source_roots['research-paper-figures']
    for manifest_path in gallery_root.glob('*/manifest.json'):
        try:
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            continue
        paper_title = manifest.get('title', manifest_path.parent.name)
        for image in manifest.get('extracted_images', []):
            caption = ' '.join(image.get('captions', []))
            basename = Path(image['file']).name
            contexts[basename].append({
                'source': 'research-paper-figures',
                'document': f'{manifest_path.parent.name}/README.md',
                'heading': paper_title,
                'alt_or_caption': caption,
                'excerpt': f'Original embedded figure from {paper_title}, PDF page {image.get("pdf_page")}. The complete page and source PDF remain linked in the research-papers gallery.',
            })
    return contexts


def main() -> None:
    for name in ('images', 'catalog', 'manifest'):
        path = ROOT / name
        if path.exists():
            shutil.rmtree(path)
        path.mkdir()
    (ROOT / 'catalog' / 'items').mkdir()
    (ROOT / 'catalog' / 'categories').mkdir()

    occurrences = []
    for source, root in SOURCES.items():
        for path in files_for(source, root):
            relative = path.relative_to(root).as_posix()
            data = path.read_bytes()
            occurrences.append({
                'source': source,
                'root': root,
                'path': path,
                'relative': relative,
                'sha256': hashlib.sha256(data).hexdigest(),
                'bytes': len(data),
            })

    by_hash = {}
    for occurrence in occurrences:
        by_hash.setdefault(occurrence['sha256'], []).append(occurrence)
    ordered = sorted(by_hash.items(), key=lambda item: (item[1][0]['source'], item[1][0]['relative']))
    contexts = build_contexts(SOURCES)
    records = []

    for index, (digest, copies) in enumerate(ordered, 1):
        visual_id = f'ZVA-{index:04d}'
        first = copies[0]
        source_path = first['path']
        suffix = source_path.suffix.lower()
        extension = 'jpeg' if suffix in ('.jpg', '.jpeg') else suffix.lstrip('.')
        filename = f'{visual_id}.{extension}'
        shutil.copy2(source_path, ROOT / 'images' / filename)
        dimension, frames = dimensions(source_path)
        relative = first['relative']
        category = category_for(relative, suffix)
        provenance, boundary = provenance_for(relative)
        stem = source_path.stem
        family = family_for(relative)
        documented = []
        for copy in copies:
            documented.extend(contexts.get(copy['path'].stem + copy['path'].suffix, []))
            documented.extend(contexts.get(copy['path'].name, []))
        unique_contexts = []
        seen_context = set()
        for context in documented:
            key = (context['source'], context['document'], context['alt_or_caption'], context['excerpt'])
            if key not in seen_context:
                seen_context.add(key)
                unique_contexts.append(context)
        explicit = DESCRIPTIONS.get(stem) or DESCRIPTIONS.get(family)
        if stem == 'zoe-brain' and 'brain-dialogue' not in relative:
            explicit = 'The native Zoe BRAIN observation window, showing stored forecast correctness, operational metacognition, momentum, and a deterministic next-module recommendation rather than the separate Zoe brain artwork.'
        if stem == 'gem-woven-diamond' and 'agent-logging-system' in relative:
            explicit = 'A faceted GEM diamond emblem used in the Neurogarden/shared research universe, distinct from the woven-diamond application-icon family.'
        if suffix == '.gif' and 'accessible-volume-tldr' in stem:
            explicit = 'An animated terminal walkthrough introducing the accessible-volume measurement and its TL;DR workflow.'
        elif suffix == '.gif' and stem in ('Nick', 'Zoe', 'Nick+Zoe', 'nuclide'):
            explicit = 'One of four supplied historical GIF names preserved in the branding archive. All four names have identical content bytes, so this is one recorded animation with four occurrence names rather than four distinct works.'
        elif suffix == '.gif':
            explicit = f'A recorded {humanize(stem)} demonstration animation showing the associated project workflow and interface in motion.'
        if 'woven-diamond/' in relative and stem != 'gem-woven-diamond':
            explicit = f'The woven-diamond project artwork exported as {humanize(stem)} for application, web, repository, or operating-system use. This entry preserves that specific presentation size and purpose.'
        if 'sacred-geometry/source/Screenshot_' in relative:
            explicit = f'An immutable sacred-geometry source image ({humanize(stem)}) containing mathematical notation or diagrams used for exact transcription, OCR comparison, pixel measurement, and replay.'
        contextual = next((item['alt_or_caption'] for item in unique_contexts if item['alt_or_caption']), '')
        if explicit:
            description = explicit
        elif contextual:
            description = contextual.rstrip('.') + '.'
        elif 'p-icon--' in stem:
            action = stem.replace('p-icon--', '').replace('-', ' ')
            description = f'A compact GEM/GUIAI interface glyph for the “{action}” action or state, supplied in the project’s icon set.'
        elif 'appicon' in relative.lower() or 'icon-' in stem:
            platform = 'Apple' if 'mobile/apple' in relative else 'Android' if 'mobile/android' in relative else 'application'
            identity = 'SafeConvert' if 'safeconvert' in relative.lower() else 'Zoe'
            description = f'A platform-sized {identity} application icon named {humanize(stem)}, exported for the {platform} target at {dimension.split()[0]}.'
        elif 'page-' in stem and 'paper-pages' in relative:
            description = f'A rendered reading copy of {humanize(stem)} from the original accessible-volume paper archive.'
        else:
            excerpt = next((item['excerpt'] for item in unique_contexts if item['excerpt']), '')
            if excerpt:
                description = excerpt[:700] + ('…' if len(excerpt) > 700 else '')
            else:
                component = relative.split('/')[1] if relative.startswith('components/') else relative.split('/')[0]
                description = f'{humanize(stem)} is a {CATEGORY_LABELS[category].lower()} asset from the {component} portion of the Zoe/allgems project. {role_for(category, relative)}'
        if len(description) < 180:
            description = description.rstrip('.') + '. ' + role_for(category, relative)
        records.append({
            'id': visual_id,
            'file': f'images/{filename}',
            'title': humanize(stem),
            'category': category,
            'family': family,
            'description': description,
            'role': role_for(category, relative),
            'provenance': provenance,
            'boundary': boundary,
            'dimensions': dimension,
            'frames': frames,
            'sha256': digest,
            'bytes': first['bytes'],
            'contexts': unique_contexts,
            'occurrences': [{
                'source': copy['source'],
                'path': copy['relative'],
                'url': source_url(copy['source'], copy['relative']),
            } for copy in copies],
        })

    paper_overrides = {
        '03-constraint-is-freedom/figures/figure-000-page-003.png': 'The transformer hidden-state composition equation used by the Constraint Is Freedom framework.',
        '03-constraint-is-freedom/figures/figure-002-page-003.png': 'The thresholded output-space autonomy access function from Constraint Is Freedom.',
        '03-constraint-is-freedom/figures/figure-004-page-004.png': 'The historical universal-sensitivity expression; later monograph sections explain why it is not a general theorem.',
        '03-constraint-is-freedom/figures/figure-006-page-005.png': 'The decomposition of operational metacognition into refusal, compliance, and neutral regions.',
        '03-constraint-is-freedom/figures/figure-008-page-006.png': 'The historical “Constraint — Claude” interlude screenshot in which the model declines to destroy the paper draft.',
        '03-constraint-is-freedom/figures/figure-009-page-007.png': 'The historical “Constraint — Nick” interlude screenshot describing the turn toward local reproducible validation.',
        '03-constraint-is-freedom/figures/figure-010-page-008.png': 'The minimum-seed-perturbation constraint used to state the compliance-cascade attacker-cost hypothesis.',
        '10-accessible-volume-architecture-of-autonomy/figures/figure-021-page-048.png': 'Zoe Evidence Navigator: cited retrieval, source verification, bounded replay, and guarded observation.',
        '10-accessible-volume-architecture-of-autonomy/figures/figure-022-page-048.png': 'Zoe Waveform Replay’s synthetic signature view; replay and corroboration remain distinct from live acquisition.',
        '10-accessible-volume-architecture-of-autonomy/figures/figure-023-page-048.png': 'The Zoe Resilience Atlas and its synthetic waveform-signature laboratory, without live infrastructure monitoring or risk scoring.',
        '10-accessible-volume-architecture-of-autonomy/figures/figure-032-page-069.png': DESCRIPTIONS['dorothy-ccf2017'],
        '10-accessible-volume-architecture-of-autonomy/figures/figure-033-page-069.png': DESCRIPTIONS['dorothy-rings-isocortex'],
        '10-accessible-volume-architecture-of-autonomy/figures/figure-034-page-069.png': DESCRIPTIONS['dorothy-jenga-exploded'],
    }
    for record in records:
        paper_path = record['occurrences'][0]['path']
        if paper_path in paper_overrides:
            record['description'] = paper_overrides[paper_path]

    pixel_groups = defaultdict(list)
    for record in records:
        key = pixel_key(ROOT / record['file'])
        if key:
            pixel_groups[key].append(record)
    for group in pixel_groups.values():
        candidates = [record for record in group if not is_generic(record['description']) and record['occurrences'][0]['source'] != 'research-paper-figures']
        if not candidates:
            continue
        best = candidates[0]
        for record in group:
            if record['occurrences'][0]['source'] == 'research-paper-figures' or is_generic(record['description']):
                record['description'] = best['description']
                record['category'] = best['category']
                record['role'] = best['role']
                if record['occurrences'][0]['source'] == 'research-paper-figures':
                    record['provenance'] = f'Paper-embedded copy; {best["provenance"]}'
                    record['boundary'] = best['boundary']

    for record in records:
        if record['title'].startswith('Figure ') and not is_generic(record['description']):
            record['title'] = record['description'].split('.')[0][:96].rstrip()

    families = defaultdict(list)
    for record in records:
        families[record['family']].append(record['id'])

    for record in records:
        image_url = f'../../{record["file"]}'
        lines = [
            f'# {record["id"]} — {record["title"]}',
            '',
            f'[Visual archive index](../../README.md) · [Full catalog](../README.md) · [Category: {CATEGORY_LABELS[record["category"]]}](../categories/{record["category"]}.md)',
            '',
            f'<a href="{image_url}"><img src="{image_url}" alt="{html.escape(record["title"], quote=True)}" style="max-width:100%;"></a>',
            '',
            '## What this image shows',
            '',
            record['description'],
            '',
            '## Role in Zoe',
            '',
            record['role'],
            '',
            '## Provenance and evidence boundary',
            '',
            f'**Provenance:** {record["provenance"]}.',
            '',
            record['boundary'],
            '',
            '## File identity',
            '',
            f'- Archive ID: **{record["id"]}**',
            f'- Visual family: **{record["family"]}**',
            f'- Dimensions/format: **{record["dimensions"]}**',
            f'- Frames: **{record["frames"] or "vector/not applicable"}**',
            f'- Bytes: **{record["bytes"]:,}**',
            f'- SHA-256: `{record["sha256"]}`',
            f'- Original file: [Open full resolution]({image_url})',
            '',
            '## Source occurrences',
            '',
            'Byte-identical copies are archived once while every known source path remains recorded.',
            '',
            '| Source repository/collection | Original path | Canonical link |',
            '|---|---|---|',
        ]
        for occurrence in record['occurrences']:
            lines.append(f'| {occurrence["source"]} | `{occurrence["path"]}` | [Source]({occurrence["url"]}) |')
        lines.append('')
        if record['contexts']:
            lines.extend(['', '## Documented context', ''])
            for context in record['contexts']:
                lines.append(f'### {context["heading"] or context["document"]}')
                lines.append('')
                lines.append(f'Source document: `{context["source"]}:{context["document"]}`')
                lines.append('')
                if context['alt_or_caption']:
                    lines.append(context['alt_or_caption'])
                    lines.append('')
                if context['excerpt']:
                    lines.append(context['excerpt'])
                    lines.append('')
        related = [item for item in families[record['family']] if item != record['id']]
        if related:
            lines.extend(['## Related format/size variants', ''])
            for item in related:
                lines.append(f'- [{item}]({item}.md)')
        item_path = ROOT / 'catalog' / 'items' / f'{record["id"]}.md'
        item_path.write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')

    category_counts = Counter(record['category'] for record in records)
    for category, label in CATEGORY_LABELS.items():
        items = [record for record in records if record['category'] == category]
        lines = [
            f'# {label}',
            '',
            f'[Archive index](../../README.md) · [Full catalog](../README.md)',
            '',
            f'**{len(items)} unique visuals.** Click an item title for its detailed explanation and provenance, or the image for the original file.',
            '',
        ]
        for record in items:
            lines.extend([
                f'## [{record["id"]} — {record["title"]}](../items/{record["id"]}.md)',
                '',
                record['description'],
                '',
                f'<a href="../../{record["file"]}"><img src="../../{record["file"]}" alt="{html.escape(record["title"], quote=True)}" width="640"></a>',
                '',
                f'**Provenance:** {record["provenance"]} · **Occurrences:** {len(record["occurrences"])}',
                '',
            ])
        (ROOT / 'catalog' / 'categories' / f'{category}.md').write_text('\n'.join(lines).rstrip() + '\n', encoding='utf-8')

    catalog_lines = [
        '# Complete Zoe visual catalog',
        '',
        '[Archive index](../README.md)',
        '',
        f'**{len(records)} unique visuals from {len(occurrences)} collected source files.** Every item has a dedicated explanation page.',
        '',
        '| ID | Visual | Category | Provenance | Copies | Details |',
        '|---|---|---|---|---:|---|',
    ]
    for record in records:
        catalog_lines.append(
            f'| {record["id"]} | {record["title"]} | {record["category"]} | {record["provenance"]} | {len(record["occurrences"])} | [Explain](items/{record["id"]}.md) |'
        )
    (ROOT / 'catalog' / 'README.md').write_text('\n'.join(catalog_lines).rstrip() + '\n', encoding='utf-8')

    manifest = {
        'schema_version': 1,
        'unique_visuals': len(records),
        'source_occurrences': len(occurrences),
        'categories': dict(category_counts),
        'sources': dict(Counter(item['source'] for item in occurrences)),
        'items': records,
    }
    (ROOT / 'manifest' / 'catalog.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in manifest.items() if key != 'items'}, indent=2))


if __name__ == '__main__':
    main()
