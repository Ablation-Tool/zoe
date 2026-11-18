# Reproduction guide

Start with saved evidence. Fresh model inference is optional and requires separate public model downloads and their documented runtime dependencies.

## Verify saved model evidence

From this repository:

```bash
python scripts/verify-model-comparison.py \
  --manifest evidence/comparison/model-comparison-cases.json \
  --evidence evidence/comparison

python scripts/verify-biobert-optimization.py
```

The first command independently checks threshold counts, target ranks, entropy, top-ten mass, token ordering, and raw-array hashes for all sixteen comparison cases. **It also regenerates the summary JSON and CSV, including a fresh timestamp.** Run it in a working copy when the reference artifacts must remain byte-for-byte unchanged. The second command recomputes the BioBERT optimization and original/adaptive metrics from the frozen cases and raw distributions without writing that evidence. No model weights are downloaded by these verification commands.

The [long-form research archive](./RESEARCH.md#reproduction-procedure) contains the original inference environments, exact public model identifiers, immutable revisions, and baseline/XLNet procedures. The [evidence guide](../evidence/README.md) separates canonical results from historical context.

## Inspect the integrated Zoe proof of concept

The primary significance paper now includes a substantive Zoe chapter and embeds the complete [Zoe paper](../evidence/zoe-integration/zoe.pdf), its source, core implementation files, worked field and Cognitive Field memories, license, notices, and [hash manifest](../evidence/zoe-integration/provenance.json). The manifest pins these copies to Zoe revision `8fcdcfe4`. The embedded Zoe source retains its original repository-relative paths; rebuild it from a Zoe checkout rather than treating the copied source as a standalone distribution.

The Zoe chapter covers the epistemic firewall, Bayesian updates, bounded symbolic memory, mirrored observations, exact toy continuations, Cog's actual bigram smoothing and reverse-count construction, native geometry, CERN evidence, and guarded updates. These are later engineering contributions with separately preserved authorship and verification scope, not changes to the original equation or new claims of creativity, consciousness, correctness, or hardware validation.

## Reproduce the Zoe repository audit

The November 7 audit targeted [Zoe `8fcdcfe4`](https://github.com/Ablation-Tool/zoe/commit/8fcdcfe49959761f87c746e808c168a1100a9707). Its [report](../evidence/zoe-audit/report.json), [audit script](../scripts/audit-zoe.py), and focused test logs are preserved. Run the numerical, source, chain, and documentation checks against a Zoe checkout and supply the preserved logs to reproduce the recorded test classification:

```bash
python scripts/audit-zoe.py \
  --zoe-root /path/to/zoe \
  --audit-date 2026-11-07 \
  --test-log evidence/zoe-audit/headless-and-components.txt \
  --test-log evidence/zoe-audit/native-unified.txt \
  --output reproduced-zoe-audit.json
```

The script writes only the new report path and refuses to overwrite it. It does not invoke the summary-writing comparison verifier, download model weights, perform fresh inference, run firmware acceptance plans, or contact hardware. The report is point-in-time evidence: after this paper update, the standalone research checkout intentionally differs from Zoe's older bundled snapshot. The native log records the confirmed stale 11-versus-12 link assertion rather than claiming a native all-pass.

The headless/component command used for the preserved log was:

```bash
cd /path/to/zoe
env -u DISPLAY GEM_COMPONENT_TESTS=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=guiai-lab /usr/bin/python3 -m unittest \
  stress.unified_stress stress.zoe_workbench_stress stress.cern_stress -v
```

The isolated native check used `guiai-lab/stress/nested_x11.sh` with `stress.unified_stress.UnifiedNativeCase`. It currently fails at `stress/unified_stress.py:220`: the implementation adds a declared source link while the assertion retains the old count. This is an open test-maintenance finding; the audit does not modify Zoe or weaken the assertion.
## Verify the response-planning visual proof

```bash
python scripts/visualize-response-planning.py
python scripts/verify-response-planning.py
```

The generator recomputes every measurement from the saved raw probability distributions and the frozen Zoe and GEM reports, then renders `evidence/response-planning/response-planning-proof.png` and `.svg`. Output is deterministic: repeated runs produce byte-for-byte identical artifacts. The verifier independently recomputes the statistics, checks semantic content inside the SVG, and confirms the SHA-256 hash of every generated artifact against its manifest. No model weights are downloaded. The dashboard documents measured accessible-volume behavior; it does not validate any response-length or autonomy policy.

## Verify the unified workbench

From the [graphics-environment-manager](https://github.com/Ablation-Tool/graphics-environment-manager) checkout:

```bash
python -m gem workbench check \
  --output workbench-verification.json

python -m gem hourglass \
  --output accessible-q-volume.svg
```

The workbench checks all 17 operations, including the mirrored brain. The hourglass command checks and renders the silent-AND example, strict threshold equality, labeled filtrations, and the two-way record. Both refuse to overwrite existing evidence. The original Zoe research modules and [Qualia JSON demonstration](https://github.com/Ablation-Tool/zoe) remain in their research repository.

## Open the mirrored brain

```bash
python -m gem os
```

Choose **Observe mirrored pair** or **Observe next mirrored pair**. Both observations enter the field notebook without changing a posterior. Exporting SVG, PNG, or GEM VDI records an export count but leaves `executed=False`.

Headless alternatives:

```bash
python -m gem os --output zoe-mirror.svg
python -m gem os --module field --output zoe-field.svg
python -m gem notebook --output zoe-field.json
```

## Search the GEM manual library

From the same GEM checkout, create an explicit local index of the supplied GEM manuals:

```bash
python -m gem library index \
  --root /media/cowboy/research/GEM/Books \
  --database /home/cowboy/_temp/zoe-os-library/gem-manuals-canonical.sqlite

export GEM_LIBRARY=/home/cowboy/_temp/zoe-os-library/gem-manuals-canonical.sqlite
python -m gem library stats --database "$GEM_LIBRARY"
python -m gem library search --database "$GEM_LIBRARY" --query VDI
python -m gem os --module library
```

The [library guide](https://github.com/Ablation-Tool/graphics-environment-manager/blob/main/docs/LIBRARY.md) records supported formats, text limits, image-only documents, and source-opening boundaries. Existing index files are not overwritten. Manuals and document text are never executed as commands.

## Run native verification

From the GEM checkout, with its documented research dependencies configured:

```bash
python stress/run_stress.py
python stress/native_stress.py
python stress/gem_stress.py
python -m unittest tools.test_workbench tools.test_library tools.test_unlock_guard tools.test_eye

stress/nested_x11.sh env PYTHONPATH=. \
  /usr/bin/python3 -m unittest tools.test_workbench tools.test_library tools.test_unlock_guard tools.test_eye
```

The nested launcher creates an isolated X11 display for native GTK, pointer, keyboard, and export checks. It does not certify every graphics driver, display server, or external VDI consumer.

## Optional inference and rhythm experiments

- **Baseline and XLNet:** follow [the original reproduction procedure](./RESEARCH.md#reproduction-procedure).
- **Sixteen comparisons:** use `scripts/run-model-comparison.py` with the frozen manifest and a writable cache, then run the verifier above.
- **BioBERT:** use `scripts/prepare-biobert-cases.py` only when creating new cases; then `biobert-accessible-volume.py`, `optimize-biobert.py`, and the verifier in that order.
- **Rhythms and HOP:** see the [companion paper's reproduction appendix](../paper/accessible-volume-beyond-next-token.pdf) and the experiment guides under [`evidence/`](../evidence/README.md). HOP also requires the original extracted `learn-music-theory/004_Chapter_1.html` and `classical-geometry-euclidean/007_c01.htm.html` texts under `FOLIO_OUTPUT`. Those original corpus files are not present on this host, so its full inference was not rerun; its saved negative baseline is retained.

Exact multi-horizon continuation enumeration grows as $|O|^h$. Use small defined vocabularies for exact checks and label every restricted or sampled approximation. Never treat a high-volume forecast as permission to act.
