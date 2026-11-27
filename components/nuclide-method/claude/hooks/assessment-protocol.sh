#!/usr/bin/env sh
# assessment-protocol.sh - NuClide method SessionStart hook.
#
# Prints a short reminder at the start of each Claude Code session so the
# methodology is unmissable and never re-derived from scratch. The method is
# the default operating logic for assessment work, not a mode you switch into.
#
# Wire-up and sample output: see README.md in this directory.
# Canon: docs/METHODOLOGY.md   Runner: chain/run-chain.sh

# Colors degrade to plain text when the terminal does not support them.
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ]; then
  C=$(printf '\033[1;36m'); Y=$(printf '\033[1;33m')
  D=$(printf '\033[2m');    B=$(printf '\033[1m')
  R=$(printf '\033[1;31m'); N=$(printf '\033[0m')
else
  C=''; Y=''; D=''; B=''; R=''; N=''
fi

printf '\n'
printf '  %s%sNuClide method%s %s- active by default for assessment, recon, and AI-infra work.%s\n' "$C" "$B" "$N" "$D" "$N"
printf '\n'
printf '  %s%sVerification is the load-bearing stage.%s %sA scan produces candidates. Verification produces findings.%s\n' "$Y" "$B" "$N" "$D" "$N"
printf '  %sA 200 is identity, not auth. A dork hit is not an instance. Earn the label with a read of real data.%s\n' "$D" "$N"
printf '  %sBlocked access is "surface open, access not exercised", never an asserted finding.%s\n' "$D" "$N"
printf '\n'
printf '  %s%sPost the chain checklist first.%s %sThen run it. Every step, in order. Mark each one as it runs.%s\n' "$C" "$B" "$N" "$D" "$N"
printf '  %sDiscover -> Active-Banner -> Fingerprint -> [ VERIFY ] -> Attribute -> Classify -> Ledger -> Score -> Codify%s\n' "$D" "$N"
printf '  %sCanon: docs/METHODOLOGY.md     Runner: chain/run-chain.sh%s\n' "$D" "$N"
printf '\n'
printf '  %sNull result = logged result, never a skip.%s %sIf a step is genuinely N/A, say why in one line.%s\n' "$R" "$N" "$D" "$N"
printf '  %sPrimary source over framing. Codify every survey into a numbered insight.%s\n' "$D" "$N"
printf '\n'
printf '  %sSTOP-and-check: about to write a curl or urllib probe loop? A chain step already covers it.%s\n' "$D" "$N"
printf '  %sSession continuity: read SESSION.md in the project root at start, update it at end.%s\n' "$D" "$N"
printf '\n'
