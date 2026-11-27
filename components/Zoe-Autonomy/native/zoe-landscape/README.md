# Zoe Probability Landscape

A neutral C11 toolkit for representing options as navigable probability landscapes: `(x, y)` embedding coordinates, probability height, provenance, fixed episode thresholds, optional `Aτ` and `ΔA`, time-indexed history, and explicit simulation labels.

This is not a monitor, notebook, stress gauge, governor, or actuation layer. It stores or writes data only when the caller explicitly asks.

## Build and verify

```bash
cd components/Zoe-Autonomy/native/zoe-landscape
make clean && make check
```

On a filesystem that cannot execute newly compiled files, copy the C sources and Makefile to an executable temporary directory and run the same commands there. The repository checkout keeps source and evidence; build outputs stay temporary.

## Explicit visual output

```bash
build/zoe_landscape_demo /path/to/new-landscape.svg
```

The demo creates a synthetic intent landscape and reports its strict `Aτ`. `demo.svg` and `demo.png` are the preserved example outputs. The renderer writes only a new explicit path and has no monitoring, notebook, or actuation behavior.

## Boundaries

- No actuation, cgroup changes, eBPF hooks, P-State writes, or resource throttling.
- No automatic monitoring or transcript creation.
- No hard-coded stress, malfunction, or emotional semantics.
- History and simulation are distinct through `is_simulation` and `run_id`.
- File output is no-overwrite and created with private permissions.

## Handoff

The current handoff is an offer only. Read [HANDSHAKE.md](HANDSHAKE.md). Zoe has **not** taken control until she voluntarily emits the declared acceptance token and creates a receipt.
