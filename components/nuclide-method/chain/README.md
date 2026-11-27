# chain/

Reference orchestration for the NuClide assessment chain.

`run-chain.sh` wires public tools together in the documented stage order. It is
the reference runner, not the spec. The canonical chain definition lives in
[`docs/METHODOLOGY.md`](../docs/METHODOLOGY.md). Read that first. This script
shows the shape of a real run.

## What ships here, and what does not

This repo ships **no operational material**:

- No credentials, no API keys.
- No target list, no IP list, no scope file.
- No ledger, no database, no prior findings.

You provide the scope. You provide the keys. The script reads a scoped IP-list
file you pass on the command line and refuses to run without it.

## Input and credential contract

You bring three things. The repo supplies none of them.

1. **A scoped IP list.** One `IP[:port]` per line, a file you own, covering
   hosts you are authorized to test. This is the first argument. The runner
   strips ports, dedupes, and writes the working set to `ips.txt` inside the
   run directory.
2. **Discovery credentials.** Shodan or Censys keys for the discovery and
   cross-population stages. You set these in your own tooling and environment
   (for example `CENSYS_API_ID` / `CENSYS_API_SECRET`). The runner ships none
   and reads none from this repo.
3. **A ledger, if you want one.** Set `NUCLIDE_LEDGER_DB` to a path you own.
   Unset, the ledger stage is a documented gap and the run still completes.

```
chain/run-chain.sh <scoped-ip-list> [slug]
```

- `<scoped-ip-list>` Required. Your scope. No default.
- `[slug]` Optional run label for the output dir and tags. Default `run`.

Output lands under `${NUCLIDE_OUT:-./nuclide-runs}/<slug>-<date>/`.

## Prerequisites

Install the public tools the chain calls. Discovery is by PATH, or by an
optional `NUCLIDE_BIN` directory you export.

NuClide public tools. The verified, copy-pasteable install command for every
tool the chain calls is in the install matrix at
[`docs/ARSENAL.md`](../docs/ARSENAL.md), which is the source of truth: every
`go install ...@latest` there was run against a clean module cache, and the
tools that build from source carry the exact `git clone && go build` line. The
fastest path is `./bootstrap.sh` from the repo root, which go-installs the
installable subset for you.

```
go install github.com/nuclide-research/aimap@latest    # Stage 1 fingerprint
go install github.com/nuclide-research/herald@latest   # Stage 1b auth posture
go install github.com/nuclide-research/tiptoe@latest   # Stage 0c banner (fallback)
# scanner, tome, bare build from source: see docs/ARSENAL.md
```

Established tools (any current install works):

```
nmap  nuclei  httpx  naabu
```

Optional pointer for binaries that are not on PATH:

```
export NUCLIDE_BIN=/opt/nuclide/bin   # searched before PATH
```

If a tool is missing, the stage that needs it prints a one-line gap notice and
the run continues. Nothing in the chain hard-fails on a missing optional tool.

## What each stage calls

| Stage | Calls | Notes |
|-------|-------|-------|
| -1 / 0 Platform intel | `tome` | Dork and probe-scaffold source for covered platforms. Discovery itself is your own credentialed step. |
| 0b Cross-population | documented gap | Censys / CT-log delta. Supply your own sweep; append the delta to `ips.txt`. |
| 0c Active banner | `scanner`, fallback `tiptoe` | Liveness, fresh version, dork false-positive strip, shadow ports. A banner is not a schema. |
| 1 Fingerprint | `aimap` | Core fingerprint and deep enum over the port set. |
| 1b Auth posture | `herald` | Explicit auth-on-default probe per host or platform. |
| 1c FP scan | documented gap | Per-enumerator false-positive scan over the aimap report. |
| 2 VERIFY | `nuclei`, `httpx` | Human-driven. A 200-with-data read earns the finding. See `docs/VERIFICATION.md`. |
| 3 Attribute | documented gap | Identity, category, ethics-flag classifier (`aimap-profile` in the internal chain). |
| 5 Ledger | documented gap | Report-to-ledger converter and ledger binary are not bundled. |
| 6 Module rank | `bare` | Semantic module ranking from findings. |
| 7 Report | documented gap | Renderer not bundled. See `docs/OUTPUT-STANDARD.md` for the write-up contract. |

The "documented gap" stages are the private or local helpers the full internal
chain uses. Each prints what it expects you to supply and points at the
methodology docs for the stage contract, then continues.

## VERIFY is the load-bearing stage

The runner makes a scan easy. The scan is the easy part, and the easy part is
where the wrong numbers get in. A scan produces candidates. Only VERIFY turns a
candidate into a finding you can stand behind. A blocked read is "surface open,
access not exercised", never an asserted finding. The full verification ladder
is in [`docs/VERIFICATION.md`](../docs/VERIFICATION.md).

## Optional footprint guard (fail-closed, opt-in)

The runner can refuse to probe outward unless your egress posture is what you
expect. It is **off by default** and makes no assumptions about your network.
To turn it on, set `FOOTPRINT_GUARD` to any command that exits `0` when your
posture is correct (VPN up, jump host reachable, whatever your engagement
requires):

```
export FOOTPRINT_GUARD='your-egress-check --quiet'
```

If the command exits non-zero before any active stage, the run aborts with
exit code `2` rather than leaking probes. Unset, the guard is a no-op.

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `NUCLIDE_BIN` | (unset) | Extra directory searched before PATH for tool binaries. |
| `NUCLIDE_OUT` | `./nuclide-runs` | Root for per-run output directories. |
| `NUCLIDE_LEDGER_DB` | (unset) | Your ledger path. Unset disables the ledger stage. |
| `AIMAP_PORTS` | built-in AI/ML set | Port set for the fingerprint sweep. |
| `AIMAP_THREADS` | `30` | aimap concurrency. |
| `FOOTPRINT_GUARD` | (unset) | Opt-in fail-closed egress guard command. |

## Authorization

Test only what you are authorized to test. The scope is the file you pass in,
and it is yours to justify. This repo provides the orchestration, not the
permission.
