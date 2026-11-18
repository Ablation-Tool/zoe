#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ADAPT = {
    'Audio', 'BayesFilters', 'BPnnet', 'Beowulf', 'CINNIC', 'Cell', 'Channels', 'Component',
    'FeatureMatching', 'Features', 'Fitting', 'Foveator', 'GA', 'GenericUtils', 'Geometry',
    'Gist', 'Image', 'Landmark', 'Learn', 'Media', 'ModelNeuron', 'Neuro', 'ObjRec',
    'Parallel', 'Raster', 'SIFT', 'Simulation', 'SpaceVariant', 'Surprise', 'TIGS',
    'Transport', 'Util', 'VFAT', 'Video', 'nub', 'rutz',
}
REFERENCE = {
    'AppEye', 'AppMedia', 'AppNeuro', 'AppPsycho', 'Apps', 'CMapDemo', 'Demo', 'GameBoard',
    'Gesture', 'INVT', 'Psycho', 'TestSuite', 'Vgames',
}
OPTIONAL = {
    'App3DEye', 'AppDevices', 'AppGUI', 'ArmControl', 'BO', 'BeoSub', 'Beobot', 'Controllers',
    'CmuCam', 'Devices', 'Embedded', 'Envision', 'GUI', 'MBARI', 'Nerdcam', 'NeovisionII',
    'QtUtil', 'RCBot', 'Robots', 'SalGlasses', 'Script', 'SeaBee', 'pbot', 'plugins', 'tcl',
}
BLOCKED = {
    'CUDA': 'Configure found no cuda_runtime.h or CUDA toolkit on this host.',
    'CUDASIFT': 'CUDA SIFT requires the unavailable CUDA toolkit and compatible GPU toolchain.',
    'Ice': 'Configure found no Ice library or slice2cpp/slice2java generators.',
    'Matlab': 'Configure found no mex executable or MATLAB root.',
    'Qt': 'Configure found no Qt3 development kit; use Zoe native interfaces instead of adding a legacy GUI dependency.',
    'Qt4': 'Configure found no Qt4 development kit; use Zoe native interfaces instead of adding a legacy GUI dependency.',
}
DO_NOT_ADOPT = {
    'Corba': 'CORBA is superseded here by Zoe\'s existing MCP/ACP and local evidence protocols; the required omniORB libraries are also unavailable.',
    'HMAX': 'The iLab README itself reports unsatisfactory natural-image performance and excludes HMAX from the Brain module; retain it as a research reference, not Zoe\'s production recognizer.',
}
INTEGRATION = {
    'BayesFilters': 'Forward ensembles and uncertainty; the local UKF compatibility patch remains separately reviewed.',
    'Beowulf': 'Distributed execution architecture and nonnegative graph search; no cluster-runtime claim.',
    'Cell': 'SPU instruction and execution imagery, not a Cell SDK runtime.',
    'Channels': 'Visual feature channels and sparse modular event encoding.',
    'Component': 'Composable, guarded event-causal modules with explicit checkpoints.',
    'Gist': 'Low-dimensional scene signatures; no unvalidated semantic scene category claim.',
    'HMAX': 'Research comparison only.',
    'Image': 'Image/event transforms, spatial coherence, and reconstructed scene state.',
    'Neuro': 'VisualCortex/Brain/VisualBuffer-inspired shared event state and attention.',
    'NeovisionII': 'Optional smart-camera architecture; Ice-generated services are not currently buildable.',
    'ObjRec': 'Future validated landmark/object experiments; conspicuity is not called object recognition.',
    'SIFT': 'Future validated landmark matching experiments, not generic semantic recognition.',
    'Simulation': 'Time-expanded prediction and reversible event execution.',
    'Surprise': 'Prediction-minus-observation surprise and independent uncertainty.',
    'TestSuite': 'Reference tests and independent Zoe comparisons.',
}
REASON = {
    'Adapt for Zoe': 'Reusable mathematics or architecture with new Zoe-specific validation; no wholesale runtime claim.',
    'Run as reference': 'Reference source, example, experiment, or test used for comparison rather than directly adopted.',
    'Optional integration': 'Usable only with the declared external dependency, dataset, sensor, hardware, or owner-granted scope.',
    'Blocked': 'A concrete current dependency, compatibility, or hardware constraint prevents use on this host.',
    'Do not adopt': 'The source or its own documentation supplies a technical reason not to use this as a production Zoe component.',
}


def directory_rule(name):
    if name in BLOCKED:
        return 'Blocked', BLOCKED[name]
    if name in DO_NOT_ADOPT:
        return 'Do not adopt', DO_NOT_ADOPT[name]
    if name in ADAPT:
        return 'Adapt for Zoe', REASON['Adapt for Zoe']
    if name in OPTIONAL:
        return 'Optional integration', REASON['Optional integration']
    if name in REFERENCE:
        return 'Run as reference', REASON['Run as reference']
    raise ValueError(f'unclassified iLab source directory: {name}')


def main():
    parser = argparse.ArgumentParser(description='Classify every archived iLab source and web artifact for Zoe')
    parser.add_argument('--archive', type=Path, default=Path('/media/cowboy/research/ilab-invt'))
    parser.add_argument('--repository', type=Path, default=Path(__file__).resolve().parents[1])
    arguments = parser.parse_args()
    archive = arguments.archive.expanduser().resolve()
    repository = arguments.repository.expanduser().resolve()
    source = json.loads((archive / 'analysis/source-inventory.json').read_text(encoding='utf-8'))
    web = json.loads((archive / 'analysis/web-artifacts.json').read_text(encoding='utf-8'))
    source_directories = sorted(name[4:] for name in source['directories'] if name.startswith('src/'))
    missing = sorted(set(source_directories) - ADAPT - REFERENCE - OPTIONAL - set(BLOCKED) - set(DO_NOT_ADOPT))
    if missing:
        raise ValueError(f'unclassified iLab directories: {missing}')
    rules = {name: directory_rule(name) for name in source_directories}
    files = []
    for item in source['files']:
        parts = Path(item['path']).parts
        if len(parts) < 3 or parts[1] != 'src':
            status, reason = 'Run as reference', REASON['Run as reference']
            directory = parts[1] if len(parts) > 1 else parts[0]
        else:
            directory = parts[2]
            status, reason = rules[directory]
        files.append({
            **item,
            'source_directory': directory,
            'status': status,
            'reason': reason,
            'zoe_integration': INTEGRATION.get(directory, REASON[status]),
        })
    artifacts = []
    for item in web['artifacts']:
        if item['status'] == 'failed':
            status, reason = 'Blocked', item['error']
        elif item['url'].startswith('https://ilab.usc.edu/packages/'):
            status, reason = 'Optional integration', 'Archived package is retained for reference; installation requires a separately verified compatible platform and dependency chain.'
        else:
            status, reason = 'Run as reference', REASON['Run as reference']
        artifacts.append({**item, 'classification': status, 'classification_reason': reason})
    directory_documents = []
    for name in source_directories:
        status, reason = rules[name]
        directory = source['directories']['src/' + name]
        directory_documents.append({
            'directory': 'src/' + name,
            'status': status,
            'reason': reason,
            'zoe_integration': INTEGRATION.get(name, REASON[status]),
            'files': directory['files'],
            'code_lines': directory['code_lines'],
            'class_count': directory['class_count'],
            'declared_program_count': len(directory['declared_programs']),
        })
    document = {
        'schema_version': 1,
        'instrument': 'zoe-complete-ilab-integration-catalog/v1',
        'coverage': {
            'archive_entries': source['archive_entries'],
            'source_files': len(files),
            'source_directories': len(source_directories),
            'declared_programs': source['declared_program_count'],
            'source_images': source['image_count'],
            'web_artifacts': len(artifacts),
            'web_downloaded_bytes': web['downloaded_bytes'],
            'web_failed_artifacts': web['failed_count'],
            'every_source_file_classified': len(files) == source['file_count'],
            'every_web_artifact_classified': len(artifacts) == web['artifact_count'],
        },
        'archive': {
            'source_tarball': str(archive / 'source/saliency-current.tar.bz2'),
            'source_sha256': source['archive_sha256'],
            'virtualbox_image': str(archive / 'source/Mandriva-2010-pwp-i586-iLab.7z'),
            'website': str(archive / 'website'),
        },
        'licensing': {
            'code_license': 'GPL version 2 or any later version, compatible with Zoe\'s GPL-3.0-only distribution when notices and source obligations are preserved',
            'patent_notice': 'The 2014 source carries a pending-patent notice; later records show expired status, not a legal opinion',
            'references': [
                {'id': 'US8098886B2', 'status': 'Expired - Lifetime, expires 2024-05-28', 'url': 'https://patents.google.com/patent/US8098886B2/en'},
                {'id': 'US8515131B2', 'status': 'Expired - Fee Related, effective 2025-08-20', 'url': 'https://patents.google.com/patent/US8515131B2/en'},
            ],
        },
        'reference_build': {
            'source': '/home/cowboy/_temp/ilab-build',
            'reviewed_patches': [
                'src/Image/PixelsTypes.H: mutable HSL temporaries and green-channel wrap correction',
                'src/BayesFilters/UKF.C: local determinant and Cholesky implementations replacing unavailable LAPACK calls',
                'src/Component/ModelParamBase.C: explicit pthread.h include',
            ],
            'current_result': 'Blocked during core build at src/Image/JPEGUtil.C because jpeglib.h is unavailable; configure also reports libpng and other optional dependencies missing',
            'log': str(archive / 'analysis/build-core-patched.log'),
            'complete_toolkit_built': False,
        },
        'status_counts': dict(sorted(Counter(item['status'] for item in directory_documents).items())),
        'directories': directory_documents,
        'files': files,
        'web_artifacts': artifacts,
    }
    output = repository / 'evidence/ilab/catalog.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    lines = [
        '# Complete iLab integration catalog',
        '',
        'This is the use/blocker assessment for every archived iLab source file, source directory, and mirrored web artifact. `Adapt for Zoe` means the mathematics or architecture has a Zoe-specific integration path with new tests; it does not mean the entire legacy program is executed. No artifact is silently omitted.',
        '',
        '## Coverage',
        '',
        f"- Source archive: **{source['archive_entries']} entries**, **{len(files)} files**, **{len(source_directories)} source directories**, **{source['declared_program_count']} declared programs**, and **{source['image_count']} source images**.",
        f"- Web mirror: **{len(artifacts)} artifacts** and **{web['downloaded_bytes']:,} downloaded bytes**.",
        f"- Mirror failures: **{web['failed_count']}** artifacts, each retained in `evidence/ilab/catalog.json` with its exact HTTP error.",
        f"- Reference VirtualBox image: archived at `{archive / 'source/Mandriva-2010-pwp-i586-iLab.7z'}`.",
        f"- Full source and web artifacts remain on the research drive at `{archive}` rather than being injected into Git.",
        '',
        '## What Zoe can use and improve',
        '',
        'The event-causal engine uses iLab-inspired visual channels, VisualCortex/Brain modularity, temporal surprise, visual memory, component composition, exact graph planning, SPU/Beowulf execution imagery, and reference tests. New Zoe code supplies the missing causal loop: reconstructed event scenes influence goals, candidate futures, values, and reversible actions. SIFT, HMAX, gist, object recognition, DVS hardware, neuromorphic deployment, and physical robotics remain separately validated or optional rather than being claimed as completed capabilities.',
        '',
        '## What Zoe cannot currently use, and why',
        '',
        '- **Full legacy core build:** currently blocked at `src/Image/JPEGUtil.C` because `jpeglib.h` is unavailable. Configure also reports libpng, FFTW, SDL, OpenCV, Qt, Ice, MATLAB, CUDA, LAPACK, and other optional dependencies missing. The precise log is `analysis/build-core-patched.log` on the research drive.',
        '- **CUDA and CUDASIFT:** no CUDA development toolkit or compatible configured toolchain was found.',
        '- **Qt3/Qt4:** no corresponding development kit was found; Zoe keeps its existing native interfaces.',
        '- **Ice and MATLAB:** required generators and runtime roots are absent.',
        '- **Physical robots, cameras other than `/dev/video0`, servos, GPS, sonar, FireWire, embedded devices, and proprietary middleware:** require the actual device, protocol, owner grant, and independent safety validation.',
        '- **CORBA:** technically unsuitable for Zoe\'s existing MCP/ACP architecture and missing its legacy runtime.',
        '- **HMAX as production recognition:** iLab\'s own README reports unsatisfactory natural-image performance and excludes it from the Brain module.',
        '- **Broken or forbidden web links:** all failures remain marked `Blocked` with exact 403/404 evidence; the source tree still supplies the underlying code for many malformed Doxygen links.',
        '',
        '## Licensing and patent evidence',
        '',
        'The code is GPL version 2 or later. Zoe remains GPL-3.0-only and retains copyright, license, provenance, and modification notices. The 2014 pending-patent notice is historical evidence, not the current legal conclusion: [US8098886B2](https://patents.google.com/patent/US8098886B2/en) lists `Expired - Lifetime` with expiration 2024-05-28, and [US8515131B2](https://patents.google.com/patent/US8515131B2/en) lists `Expired - Fee Related` effective 2025-08-20. These records are not legal advice or an exhaustive patent clearance.',
        '',
        '## Every source directory',
        '',
        '| Directory | Files | Classes | Programs | Status | Reason and Zoe path |',
        '|---|---:|---:|---:|---|---|',
    ]
    for item in directory_documents:
        lines.append(
            f"| `{item['directory']}` | {item['files']} | {item['class_count']} | {item['declared_program_count']} | **{item['status']}** | {item['reason']} {item['zoe_integration']} |"
        )
    lines.extend([
        '',
        '## Machine-readable coverage',
        '',
        '`evidence/ilab/catalog.json` contains every source-file SHA-256, classification, reason, Zoe path, and every mirrored web artifact including all failures. Regenerate with `python scripts/build-ilab-catalog.py`.',
        '',
    ])
    (repository / 'ILAB-INTEGRATION.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(document['coverage'], indent=2, sort_keys=True))
    print(json.dumps(document['status_counts'], indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
