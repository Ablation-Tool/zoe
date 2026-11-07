# Zoe CERN Workbench handover

Zoe now discovers and controls the CERN console, HELIOS, and Atelier through the `cern-console` component. The component preserves the original GEM workbench and the read-only CERN and Digital Research evidence collections.

## Start and open

```bash
cd /home/cowboy/_projects/zoe
export PYTHONPATH=guiai-lab
zoe list
zoe launch cern-console
zoe launch cern-console -- open helios
zoe launch cern-console -- open atelier
```

`zoe launch cern-console` attaches to a healthy existing server on port 8765 or starts a new loopback server on a free port. `open` additionally opens the requested target in the browser. No process or browser opens while inspecting the component list or manifest.

The checkout defaults to `/media/cowboy/research/GEM/cern-console`. Override it with `ZOE_CERN_CONSOLE` or the direct CLI's `--checkout` option.

## Process boundary

The bridge writes Zoe-owned process metadata to `guiai-lab/evidence/cern-console/runtime.json`. It stops only processes that it started and whose command still matches `run.py` in the expected checkout. It does not stop an attached user-owned server.

```bash
python3 -m guiai.gem.zoe_workbench_cli health
python3 -m guiai.gem.zoe_workbench_cli stop
```

Direct HELIOS and Atelier links use `http://127.0.0.1:<port>/#helios` and `#atelier`.

## Verify and export

```bash
python3 -m guiai.gem.zoe_workbench_cli verify
python3 -m guiai.gem.zoe_workbench_cli verify --live
python3 -m guiai.gem.zoe_workbench_cli manifest /tmp/zoe-cern-handover.json
```

The default verification runs the complete Python suite and all three JavaScript model suites without opening a display or booting QEMU. `--live` explicitly adds the isolated XTEST and DR-DOS tests. Manifest paths must be new JSON files and are never overwritten.

The component includes:

- All 9,968 CERN inventory records and 226 document previews.
- FELIX firmware groups, LCB and STAR/Flink logical models, and evidence capsules.
- HELIOS, MERIDIAN, and FLINT virtual systems.
- Atelier keyboard, relative mouse, absolute tablet, vector editing, and input event replay.
- XTEST input, PTY-based Summa firmware, and the expanded resident DOS INT 33h test driver.
- GEM, COO, and EPS import and export, including the original `EVENTS.GEM` sample.

## Evidence and compatibility boundaries

The CERN corpus and original manuals remain read-only. XTEST and serial emission are opt-in. Verification does not inject events into the user's desktop, access physical hardware, access `/dev/uinput`, or escalate privileges.

The DOS handler implements functions 0, 3, 4, 7, and 8 with a second live packet test. It is not a complete Microsoft mouse replacement or an Artline integration. No Artline executable was found, so full application-level Artline compatibility remains unclaimed. GEM, COO, and EPS support is limited to the documented and tested vector subset.

## Implementation and tests

- `guiai/gem/zoe_workbench.py`: health, lifecycle, manifest, browser targets, and verification.
- `guiai/gem/zoe_workbench_cli.py`: direct command interface.
- `guiai/gem/unified.py`: component registration and layout.
- `guiai/gem/atlas_view.py`: native unified controls and refresh.
- `stress/zoe_workbench_stress.py`: registration, ownership, CLI, native controls, and verification tests.

Run the integration suite with:

```bash
PYTHONPATH=guiai-lab python3 -m unittest stress.zoe_workbench_stress -v
```

The native control test additionally requires the project's private-X11 wrapper.

## Verified handover results

The handover was exercised through the real CLI and native hub:

- 39/39 Zoe stress tests passed under private X11.
- 20/20 GEM stress tests passed under private X11.
- 5/5 CERN corpus stress tests passed.
- The workbench integration tests passed, including attach/start, Zoe-owned stop, direct browser targets, manifest output, and native controls.
- 75 Python tests and both isolated live tests passed through `verify --live`.
- All three JavaScript model suites passed.
- 130 browser checks passed across the original CERN console, HELIOS, and Atelier.
- `zoe launch cern-console` attached to the healthy existing console and returned verified health.
- Direct `#helios` and `#atelier` navigation worked, including same-document hash changes.
- The no-overwrite handover manifest was generated at `/tmp/zoe-workbench-handover.json`.

The component starts no process during inspection. Browser opening and XTEST/serial emission require explicit user actions. The tests stopped only Zoe-owned servers; the attached console remained running.
