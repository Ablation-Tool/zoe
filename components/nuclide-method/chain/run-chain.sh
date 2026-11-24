#!/usr/bin/env bash
# =============================================================================
# run-chain.sh - reference orchestration for the NuClide assessment chain.
#
# This is the REFERENCE runner, not the spec. The canonical chain definition
# (the eight stages, what VERIFY means, the restraint ethic) lives in
# docs/METHODOLOGY.md. Read that first. This script just wires public tools
# together in the documented order so you can see the shape of a real run.
#
# WHAT SHIPS WITH THIS REPO: nothing operational. No credentials, no target
# list, no ledger, no scan output. You supply the scope. You supply the keys.
# The script reads a scoped IP-list file you pass as the first argument and
# refuses to run without it.
#
# Public tools the chain calls (install these yourself, see chain/README.md):
#   aimap, tome, herald, bare, tiptoe, scanner   (NuClide public tools)
#   nmap, nuclei, httpx, naabu                    (established tools)
#
# Private or local helpers the full internal chain uses are STUBBED here and
# clearly marked "documented gap". Provide your own, or see the methodology
# docs for what the stage is meant to produce, then continue.
#
# Usage:
#   chain/run-chain.sh <scoped-ip-list> [slug]
#
#   <scoped-ip-list>  Path to a file you own, one IP[:port] per line. Required.
#                     This file is YOUR scope. The repo ships no such file.
#   [slug]            Short label for the run (output dir + tags). Default: run.
#
# Output goes to a per-run directory under ${NUCLIDE_OUT:-./nuclide-runs}.
# =============================================================================
set -euo pipefail

# --- Binary discovery --------------------------------------------------------
# No hardcoded install paths. Tools are discovered on PATH, or inside an
# optional BIN dir you export. This keeps the runner portable and ships no
# machine-specific path.
#
#   export NUCLIDE_BIN=/opt/nuclide/bin   # optional: extra dir to search first
#
NUCLIDE_BIN="${NUCLIDE_BIN:-}"

# resolve_bin <name> -> prints the resolved path, or empty if not found.
resolve_bin() {
  local name="$1"
  if [[ -n "$NUCLIDE_BIN" && -x "$NUCLIDE_BIN/$name" ]]; then
    printf '%s\n' "$NUCLIDE_BIN/$name"
    return 0
  fi
  command -v "$name" 2>/dev/null || true
}

# have <name> -> true if the tool resolves, false otherwise.
have() { [[ -n "$(resolve_bin "$1")" ]]; }

# Resolve each public tool once. Empty means "not installed"; the stage that
# needs it prints a documented-gap line and continues.
AIMAP_BIN="$(resolve_bin aimap)"
HERALD_BIN="$(resolve_bin herald)"
BARE_BIN="$(resolve_bin bare)"
TIPTOE_BIN="$(resolve_bin tiptoe)"
SCANNER_BIN="$(resolve_bin scanner)"
# tome is invoked via `have tome` and printed guidance only; no path var needed.

# --- Inputs ------------------------------------------------------------------
IP_LIST="${1:-}"
SLUG="${2:-run}"
DATE="$(date +%Y-%m-%d)"

if [[ -z "$IP_LIST" ]]; then
  echo "ERROR: no scoped IP list supplied." >&2
  echo "Usage: chain/run-chain.sh <scoped-ip-list> [slug]" >&2
  echo "You provide the scope. This repo ships no target list." >&2
  exit 1
fi
if [[ ! -f "$IP_LIST" ]]; then
  echo "ERROR: scoped IP list '$IP_LIST' not found." >&2
  exit 1
fi

OUT_ROOT="${NUCLIDE_OUT:-./nuclide-runs}"
RUN_DIR="${OUT_ROOT}/${SLUG}-${DATE}"
mkdir -p "$RUN_DIR"

# Normalize the scope into ips.txt: strip ports, dedupe. Everything downstream
# reads this file, never the caller's original.
awk -F: '{print $1}' "$IP_LIST" | sort -u > "$RUN_DIR/ips.txt"
IP_COUNT="$(wc -l < "$RUN_DIR/ips.txt" | tr -d ' ')"
echo "Scope: $IP_COUNT unique hosts -> $RUN_DIR/ips.txt"

# Preserve any IP:PORT lines from the caller's scope for tools that need a port.
# herald reads IP:PORT[:SCHEME] on stdin; bare-IP scope lines have no port to give
# it, so they are left out of this file rather than fed to herald portless.
grep -E ':[0-9]+' "$IP_LIST" | sort -u > "$RUN_DIR/ip-port.txt" || true

# Default port set for the AI/ML fingerprint sweep. Override with AIMAP_PORTS.
AIMAP_PORTS="${AIMAP_PORTS:-80,443,1984,2379,3000,3001,4000,4040,4200,5000,5001,5678,6333,7575,7576,7860,8000,8001,8080,8081,8123,8233,8265,8443,8501,8787,8888,8889,9000,9090,9091,10000,11434,15500,18080,18789,19530,30000,51000,55000}"

# --- Optional footprint guard ------------------------------------------------
# Fail-closed only if YOU opt in. Set FOOTPRINT_GUARD to a command that exits 0
# when your egress posture is what you expect (VPN up, jump host reachable,
# whatever your engagement requires). If it exits non-zero the run aborts
# before any outward probe. Unset = guard disabled, no assumptions made.
#
#   export FOOTPRINT_GUARD='your-vpn-status-check --quiet'
#
FOOTPRINT_GUARD="${FOOTPRINT_GUARD:-}"

footprint_guard() {
  [[ -z "$FOOTPRINT_GUARD" ]] && return 0
  if ! eval "$FOOTPRINT_GUARD" >/dev/null 2>&1; then
    echo "ABORT: FOOTPRINT_GUARD failed. Refusing outward probing." >&2
    exit 2
  fi
}

# --- Helper: print a stage banner -------------------------------------------
stage() { echo; echo "=== $* ==="; }

# Helper: announce a documented gap and keep going.
gap() {
  echo "  [documented gap] $1"
  echo "  Provide your own, or see docs/METHODOLOGY.md for the stage contract."
}

# =============================================================================
# Stage -1 / 0. Platform-Intel and Discover
# =============================================================================
stage "Stage -1 / 0: Platform intel and dork source (tome)"
# tome is the canonical platform corpus. It supplies dorks and probe scaffolds
# for covered platforms so you do not hand-derive them. Discovery itself
# (running dorks against Shodan or Censys) is a credentialed step you drive with
# your own keys, outside this runner. See chain/README.md.
if have tome; then
  echo "  tome present. Pull dorks for your platform with:"
  echo "    tome dorks <platform>            # basic | strict | version tiers"
  echo "    tome probe <platform>            # scaffold an aimap-compatible probe"
else
  gap "tome not installed (go install the public tool, then re-run)."
fi

# Censys / CT-log cross-population delta. Private helper in the internal chain.
stage "Stage 0b: Censys / CT-log cross-population delta"
gap "Censys/CT-log delta helper is not bundled. Supply your own sweep that \
reads ips.txt, adds CT-log-sourced hosts your Shodan crawl missed, and appends \
the delta to $RUN_DIR/ips.txt. Set CENSYS_API_ID / CENSYS_API_SECRET in your \
own tooling; this repo ships no keys."

# =============================================================================
# Stage 0c. Active banner (standing, non-skippable after any harvest)
# =============================================================================
footprint_guard
stage "Stage 0c: Active banner grab (scanner / tiptoe)"
# Liveness, fresh version, dork false-positive strip, shadow-port discovery.
# Hands the next stage a clean live subset, not raw candidates. A banner is not
# a schema; vector-use confirmation stays the fingerprinter's job (VERIFY).
if have scanner; then
  echo "  Running scanner over the scope (banner layer)."
  "$SCANNER_BIN" -ips-file "$RUN_DIR/ips.txt" -output "$RUN_DIR/banners.json" 2>&1 | tail -5 || \
    echo "  (scanner returned non-zero; banners may be partial, continuing)"
elif have tiptoe; then
  # tiptoe is single-host by design (it assesses the one host that watches
  # back), so loop the scope and aggregate one JSON object per host. scanner is
  # the intended list-stage tool; tiptoe is the quiet single-host fallback.
  echo "  scanner not found; using tiptoe for a quiet per-host banner pass."
  : > "$RUN_DIR/banners.jsonl"
  while read -r host; do
    [ -z "$host" ] && continue
    case "$host" in \#*) continue ;; esac
    "$TIPTOE_BIN" assess "$host" --json >> "$RUN_DIR/banners.jsonl" 2>/dev/null || \
      echo "  (tiptoe non-zero on $host; continuing)"
  done < "$RUN_DIR/ips.txt"
  echo "  -> $RUN_DIR/banners.jsonl (one JSON object per host)"
else
  gap "no banner tool (scanner or tiptoe) found. Liveness and version data \
will be missing; the fingerprint stage runs on raw candidates."
fi

# =============================================================================
# Stage 1. Fingerprint + deep enum
# =============================================================================
footprint_guard
stage "Stage 1: Fingerprint and deep enum (aimap)"
if have aimap; then
  "$AIMAP_BIN" -list "$RUN_DIR/ips.txt" -ports "$AIMAP_PORTS" \
    -o "$RUN_DIR/aimap-report.json" -threads "${AIMAP_THREADS:-30}" 2>&1 | tail -5
  echo "  -> $RUN_DIR/aimap-report.json"
else
  gap "aimap not installed. This is the core fingerprint stage; install it \
(go install github.com/nuclide-research/aimap@latest) before a real run."
fi

# Auth-probe enrichment. herald confirms auth posture per platform.
stage "Stage 1b: Auth posture probe (herald)"
if have herald; then
  # herald probes one platform at a time. It reads IP:PORT[:SCHEME] targets on
  # stdin and emits NDJSON; -platform <name> is required, and there is no --json.
  # Run `herald -list` to see the platform names it ships.
  echo "  herald present. It probes one platform at a time, reading IP:PORT"
  echo "  targets on stdin and emitting NDJSON:"
  echo "    herald -platform <name> < ip-port.txt > $RUN_DIR/herald.ndjson"
  if [ -n "${HERALD_PLATFORM:-}" ] && [ -s "$RUN_DIR/ip-port.txt" ]; then
    "$HERALD_BIN" -platform "$HERALD_PLATFORM" < "$RUN_DIR/ip-port.txt" \
      > "$RUN_DIR/herald.ndjson" 2>/dev/null || \
      echo "  (herald non-zero; check 'herald -list' for platform names)"
  elif [ -n "${HERALD_PLATFORM:-}" ]; then
    echo "  (HERALD_PLATFORM set, but no IP:PORT targets in scope. herald needs a"
    echo "   port; write scope lines as IP:PORT, then re-run.)"
  else
    echo "  (set HERALD_PLATFORM=<name> and use IP:PORT scope lines to run herald)"
  fi
else
  gap "herald not installed. Auth-on-default posture will be inferred from \
aimap alone instead of an explicit auth probe."
fi

# Per-enumerator false-positive scan. Private monitor in the internal chain.
stage "Stage 1c: Per-enumerator false-positive scan"
gap "per-enumerator FP monitor is not bundled. Supply your own that reads \
$RUN_DIR/aimap-report.json and flags enumerators whose empty-result rate \
exceeds a threshold (the candidates for a false-positive signature)."

# =============================================================================
# Stage 2. VERIFY (the load-bearing stage)
# =============================================================================
footprint_guard
stage "Stage 2: VERIFY - re-probe candidates, earn the label"
# This is the stage the whole method turns on. A 200-with-data read earns the
# finding. A blocked read is "surface open, access not exercised", never an
# asserted finding. Re-run the established probes against the fingerprinted
# subset and confirm the data layer, not just the HTTP status.
if have nuclei; then
  echo "  nuclei present. Verify with your own scoped template set, e.g.:"
  echo "    nuclei -l $RUN_DIR/ips.txt -t <your-templates> -o $RUN_DIR/verify-nuclei.txt"
else
  echo "  nuclei not found (optional verifier). Install from projectdiscovery if wanted."
fi
if have httpx; then
  echo "  httpx present for status/title confirmation, e.g.:"
  echo "    httpx -l $RUN_DIR/ips.txt -json -o $RUN_DIR/verify-httpx.json"
else
  echo "  httpx not found (optional verifier)."
fi
echo "  VERIFY is human-driven by design. See docs/VERIFICATION.md for the ladder."

# =============================================================================
# Stage 3. Attribute
# =============================================================================
footprint_guard
stage "Stage 3: Attribute and classify (aimap-profile)"
# Private helper in the internal chain. Classifies identity, category, and
# surfaces ethics flags before any deeper probe.
gap "aimap-profile is not bundled in this reference runner. Supply your own \
classifier that, per host, reports identity, category (e.g. research vs \
commercial vs honeypot), and any ethics flag that should halt the run."

# =============================================================================
# Stage 5. Ledger
# =============================================================================
stage "Stage 5: Ledger ingest"
# The internal chain converts the aimap report to findings and ingests them
# into a ledger DB. Both the converter and the ledger binary are private here.
# No ledger ships with this repo. Discover your own ledger path via env.
LEDGER_DB="${NUCLIDE_LEDGER_DB:-}"
if [[ -z "$LEDGER_DB" ]]; then
  gap "no ledger configured. Set NUCLIDE_LEDGER_DB to your own ledger path and \
supply a converter (aimap report -> your ledger format). This repo ships no \
ledger and no findings."
else
  echo "  Ledger target: $LEDGER_DB"
  gap "report-to-ledger converter is not bundled. Provide one that reads \
$RUN_DIR/aimap-report.json and writes records into your ledger at $LEDGER_DB."
fi

# =============================================================================
# Stage 6. Score, rank, corpus (BARE)
# =============================================================================
stage "Stage 6: Module ranking (bare)"
if have bare; then
  # BARE wants a findings JSON. Build a minimal one from the aimap report if
  # present. The shape below is illustrative; align it to your BARE version.
  if [[ -f "$RUN_DIR/aimap-report.json" ]]; then
    "$BARE_BIN" "$RUN_DIR/aimap-report.json" --top 3 \
      > "$RUN_DIR/bare-output.json" 2>&1 || \
      echo "  (bare input shape may differ by version; see bare --help)"
    echo "  -> $RUN_DIR/bare-output.json"
  else
    echo "  No aimap report to rank. Run Stage 1 first."
  fi
else
  gap "bare not installed. Semantic module ranking is skipped."
fi

# =============================================================================
# Stage 7. Report
# =============================================================================
stage "Stage 7: Report"
# The internal chain renders an HTML drill-down from the ledger via a private
# tool. Not bundled here.
gap "report renderer is not bundled. Supply your own that reads your ledger \
(or $RUN_DIR/aimap-report.json directly) and emits a human-readable report. \
See docs/OUTPUT-STANDARD.md for what a finding write-up must contain."

# =============================================================================
# Done
# =============================================================================
stage "Run complete"
echo "Artifacts: $RUN_DIR"
ls -la "$RUN_DIR" 2>/dev/null | head -25
echo
echo "Reminder: a scan produces candidates. Only VERIFY produces findings."
echo "Canonical chain spec: docs/METHODOLOGY.md"
