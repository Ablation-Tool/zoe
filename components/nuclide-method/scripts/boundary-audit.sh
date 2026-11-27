#!/usr/bin/env bash
# Local mirror of .github/workflows/boundary-audit.yml.
# Fails (exit 1) if any redaction-boundary check trips. Run it with `make audit`.
# The repo teaches verification as the load-bearing stage, so the repo verifies itself.

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)" || exit 1
fail=0
emit() { printf '%s\n' "$*"; }
SELF='scripts/boundary-audit\.sh|\.github/workflows/boundary-audit\.yml'

# 1. No tracked secrets, state, or bulk scan data.
hits=$(git ls-files | grep -iE '(\.db$|\.db\.bak|state\.json|tokens\.json|ssh_key|\.ndjson$|\.json\.gz$|_gmail_drafts)' || true)
if [ -n "$hits" ]; then emit "FAIL  secrets/state/bulk-data tracked:"; emit "$hits"; fail=1; else emit "PASS  no secrets, state, or bulk data tracked"; fi

# 2. No machine-readable IP or target lists.
hits=$(git ls-files | grep -iE '(^|/)(ips?[-_.].*\.txt|targets?[-_.].*\.txt|confirmed-ips|.*-dossiers\.json)$' || true)
if [ -n "$hits" ]; then emit "FAIL  IP/target list tracked:"; emit "$hits"; fail=1; else emit "PASS  no machine-readable IP or target lists"; fi

# 3. No em dashes (U+2014), the loudest tell.
em=$(printf '\xe2\x80\x94')
hits=$(git ls-files | xargs grep -Il "$em" 2>/dev/null || true)
if [ -n "$hits" ]; then emit "FAIL  em-dash (U+2014) in:"; emit "$hits"; fail=1; else emit "PASS  no em dashes"; fi

# 4. Only RFC 5737 documentation IPs, loopback, RFC 1918 private, or the bind-all
#    sentinel in tracked text. Allow-set kept identical to the CI workflow's.
bad=$(git ls-files -- '*.md' '*.sh' '*.txt' '*.cff' '*.example' '*.yml' \
  | xargs grep -IohE '\b([0-9]{1,3}\.){3}[0-9]{1,3}\b' 2>/dev/null \
  | grep -vE '^(192\.0\.2\.|198\.51\.100\.|203\.0\.113\.|0\.0\.0\.0|127\.|10\.|192\.168\.|172\.1[6-9]\.|172\.2[0-9]\.|172\.3[0-1]\.|255\.255\.)' | sort -u || true)
if [ -n "$bad" ]; then emit "FAIL  non-documentation IPv4 present:"; emit "$bad"; fail=1; else emit "PASS  only RFC 5737 / loopback / RFC 1918 IPs in prose"; fi

# 5. No researcher PII. Override the pattern with PII_PATTERN if you fork the firm voice.
PII_PATTERN=${PII_PATTERN:-'@gmail|staff sergeant|enlisted'}
hits=$(git ls-files | xargs grep -IliE "$PII_PATTERN" 2>/dev/null | grep -vE "$SELF" || true)
if [ -n "$hits" ]; then emit "FAIL  possible researcher PII in:"; emit "$hits"; fail=1; else emit "PASS  no researcher PII tokens"; fi

# 6. No disclosure-routing artifacts.
hits=$(git ls-files | grep -iE '(_gmail_drafts|ready-to-send|recipients?\.(json|txt|csv))' || true)
if [ -n "$hits" ]; then emit "FAIL  disclosure-routing file tracked:"; emit "$hits"; fail=1; else emit "PASS  no disclosure-routing files"; fi

emit ""
if [ "$fail" -ne 0 ]; then emit "boundary-audit: FAIL"; exit 1; fi
emit "boundary-audit: PASS"
