# Zoe unified architecture and verification

The authoritative architecture and verification guide is maintained at [`guiai-lab/docs/UNIFIED.md`](../../../../../guiai-lab/docs/UNIFIED.md).

Zoe is one repository containing twelve runtime source projects, sixteen registered engines, twelve imported upstream histories, the complete paper collection, the visual archive, and arXiv submission sources. A fresh clone requires no sibling checkouts, submodules, or runtime source downloads.

## Canonical references

- [Zoe mission and quick start](../../../../../README.md)
- [Complete capability atlas](../../../../../CAPABILITY-ATLAS.md)
- [AGI/ASI acceptance roadmap](../../../../../AGI-ROADMAP.md)
- [Monorepo layout and imported revisions](../../../../../MONOREPO.md)
- [Runtime and evidence contract](../../../../../one-system.json)
- [Imported source locks](../../../../../components.lock.json)
- [Declaration](../../../../../DECLARATION.md)
- [Constitution](../../../../../CONSTITUTION.md)

## Current identity

`assets/branding/zoe-eye.{png,svg}` is the red woven-diamond Zoe emblem designated by Nicholas Michael Kloster on November 18, 2026. The former orbital eye remains preserved as `zoe-orbital-eye-legacy.{png,svg}` and in the historical visual archive. See [identity provenance](../../../../../assets/branding/PROVENANCE.md).

The [current unified Spatial IR scene](../../../../../guiai-lab/docs/images/gem-unified.svg) uses a symmetric woven-diamond vector interpretation. The [actual native hub screenshot](../../../../../guiai-lab/docs/images/gem-unified-native.png) preserves the interface evidence recorded before the identity change.

## One-checkout verification

From the Zoe root:

```bash
export ZOE_ROOT="$PWD"
python scripts/verify-one-system.py
python scripts/verify-one-system.py --reflect
python scripts/verify-one-system.py --image /path/to/image.jpg --foci 4
```

The verifier resolves all components inside this repository, checks imported revisions as Git ancestors, invokes the canonical engine and five hosts, and requires identical autonomy profiles, 42 saliency maps, replayable evidence, and zero external base actions.

Component processes, dependencies, evidence, and authorization remain distinct even though their source now has one canonical home.
