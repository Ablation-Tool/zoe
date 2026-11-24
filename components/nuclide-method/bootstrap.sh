#!/bin/sh
# bootstrap.sh - one-command setup for the NuClide Method.
#
# What it does:
#   1. Checks for go and git.
#   2. go installs the public NuClide tools (see TOOLS below).
#   3. Optionally copies claude/PROTOCOL.md and claude/hooks/ into ~/.claude.
#   4. Prints next steps and points at docs/QUICKSTART.md.
#
# Design rules:
#   - POSIX sh. No bashisms. shellcheck-clean.
#   - No sudo. No hardcoded personal paths. Installs land in your Go bin dir.
#   - Idempotent. Re-running is safe.
#   - Fail-soft per tool. One bad install warns and the run continues.
#
# Usage:
#   ./bootstrap.sh            # install tools, then ask about the Claude config
#   ./bootstrap.sh --claude   # also copy the Claude config without asking
#   ./bootstrap.sh --no-claude# skip the Claude config without asking
#   ./bootstrap.sh --help     # this help

set -eu

# ---------------------------------------------------------------------------
# Tool list. Import paths for `go install`.
#
# This is the install set. It is NOT the authoritative arsenal list. Verify it
# against docs/ARSENAL.md before you trust it. Tools get added and renamed; the
# doc is the source of truth, this variable is a convenience.
#
# Override on the command line if you want a subset:
#   TOOLS="github.com/nuclide-research/aimap@latest" ./bootstrap.sh
# ---------------------------------------------------------------------------
#
# This set is the go-installable subset only. Source-build and non-Go tools
# (tome, scanner, VisorSD, menlohunt, BARE, and the Python tools) are NOT here;
# see docs/ARSENAL.md to build them.
TOOLS="${TOOLS:-\
github.com/nuclide-research/aimap@latest \
github.com/nuclide-research/herald@latest \
github.com/nuclide-research/tiptoe@latest \
github.com/nuclide-research/JAXEN@latest \
github.com/nuclide-research/VisorPlus@latest \
github.com/nuclide-research/VisorLog@latest \
github.com/nuclide-research/VisorScuba@latest \
github.com/nuclide-research/VisorGoose@latest \
github.com/nuclide-research/visor/cmd/visor@latest \
github.com/nuclide-research/VisorBishop/cmd/visorbishop@latest \
github.com/nuclide-research/VisorGraph/cmd/visorgraph@latest \
github.com/nuclide-research/VisorCorpus/cmd/visorcorpus@latest \
}"

# VisorRAG also builds a binary named 'visor', which would clobber the umbrella
# 'visor' tool in TOOLS above. It is installed separately, below, as 'visorrag'
# so both tools coexist.
VISORRAG="github.com/nuclide-research/VisorRAG/cmd/visor@latest"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
say()  { printf '%s\n' "$*"; }
ok()   { printf '  [ ok ]  %s\n' "$*"; }
warn() { printf '  [warn]  %s\n' "$*" >&2; }
die()  { printf '  [fail]  %s\n' "$*" >&2; exit 1; }

usage() {
	sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'
	exit 0
}

# Resolve the directory this script lives in, so it works from any cwd.
# Unset CDPATH first so `cd` cannot print an unexpected path.
unset CDPATH
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)

# ---------------------------------------------------------------------------
# Argument parse
# ---------------------------------------------------------------------------
CLAUDE_CHOICE=ask
for arg in "$@"; do
	case "$arg" in
		--claude)    CLAUDE_CHOICE=yes ;;
		--no-claude) CLAUDE_CHOICE=no ;;
		-h|--help)   usage ;;
		*) warn "unknown argument: $arg (ignored)" ;;
	esac
done

# ---------------------------------------------------------------------------
# Step 1. Prerequisites
# ---------------------------------------------------------------------------
say "NuClide Method - bootstrap"
say "=========================="
say ""
say "Step 1. Checking prerequisites."

command -v go >/dev/null 2>&1 || die "go not found. Install Go 1.21+ from https://go.dev/dl/ and re-run."
ok "go found: $(go version)"

command -v git >/dev/null 2>&1 || die "git not found. Install git and re-run."
ok "git found: $(git --version)"

# Resolve the Go bin dir without assuming a personal path.
GOBIN=$(go env GOBIN)
if [ -z "$GOBIN" ]; then
	GOBIN="$(go env GOPATH)/bin"
fi
ok "Go tools install to: $GOBIN"

case ":${PATH}:" in
	*":${GOBIN}:"*) ok "Go bin dir is on PATH." ;;
	*) warn "Go bin dir is NOT on PATH. Add it: export PATH=\"\$PATH:${GOBIN}\"" ;;
esac

# ---------------------------------------------------------------------------
# Step 2. Install the public tools. Fail-soft per tool.
# ---------------------------------------------------------------------------
say ""
say "Step 2. Installing public NuClide tools."
say "  Verify this list against docs/ARSENAL.md. The doc is the source of truth."
say ""

installed=0
failed=0
failed_list=""

for tool in $TOOLS; do
	say "==> go install $tool"
	if go install "$tool" >/dev/null 2>&1; then
		ok "$tool"
		installed=$((installed + 1))
	else
		warn "$tool did not install. Skipping and continuing."
		failed=$((failed + 1))
		failed_list="${failed_list} ${tool}"
	fi
done

say ""
say "  Installed: ${installed}    Skipped: ${failed}"
if [ "$failed" -gt 0 ]; then
	warn "Skipped tools (re-run later, or check the import path in docs/ARSENAL.md):"
	for t in $failed_list; do warn "  $t"; done
fi

# Install VisorRAG as 'visorrag'. Its binary is named 'visor' and would
# otherwise overwrite the umbrella visor tool. Build into a temp GOBIN, then
# move it into place under the distinct name.
say ""
say "==> go install VisorRAG (as visorrag, to avoid clobbering the umbrella visor)"
RAG_TMP=$(mktemp -d)
if GOBIN="$RAG_TMP" go install "$VISORRAG" >/dev/null 2>&1 && [ -f "$RAG_TMP/visor" ]; then
	mv "$RAG_TMP/visor" "$GOBIN/visorrag"
	ok "VisorRAG installed as visorrag"
else
	warn "VisorRAG did not install. Re-run later, or check docs/ARSENAL.md."
fi
rm -rf "$RAG_TMP"

# ---------------------------------------------------------------------------
# Step 3. Optional Claude config copy.
# ---------------------------------------------------------------------------
say ""
say "Step 3. Claude config (optional)."

CLAUDE_HOME="${HOME}/.claude"
SRC_PROTOCOL="${SCRIPT_DIR}/claude/PROTOCOL.md"
SRC_HOOKS="${SCRIPT_DIR}/claude/hooks"

do_claude_copy() {
	mkdir -p "$CLAUDE_HOME"

	if [ -f "$SRC_PROTOCOL" ]; then
		cp "$SRC_PROTOCOL" "${CLAUDE_HOME}/PROTOCOL.md"
		ok "Copied PROTOCOL.md to ${CLAUDE_HOME}/PROTOCOL.md"
	else
		warn "No claude/PROTOCOL.md in this repo. Nothing to copy."
	fi

	if [ -d "$SRC_HOOKS" ]; then
		mkdir -p "${CLAUDE_HOME}/hooks"
		# Copy hook files individually so an empty dir is a clean no-op.
		copied=0
		for hook in "$SRC_HOOKS"/*; do
			[ -e "$hook" ] || continue
			cp "$hook" "${CLAUDE_HOME}/hooks/"
			copied=$((copied + 1))
		done
		if [ "$copied" -gt 0 ]; then
			ok "Copied ${copied} hook file(s) to ${CLAUDE_HOME}/hooks/"
		else
			warn "claude/hooks/ is empty. Nothing to copy."
		fi
	else
		warn "No claude/hooks/ in this repo. Nothing to copy."
	fi
}

case "$CLAUDE_CHOICE" in
	yes)
		do_claude_copy
		;;
	no)
		say "  Skipped (--no-claude)."
		;;
	ask)
		printf '  Copy claude/PROTOCOL.md and claude/hooks/ into %s ? [y/N] ' "$CLAUDE_HOME"
		# Read from the terminal. Default no on EOF or empty.
		if [ -t 0 ]; then
			read -r reply || reply=""
		else
			reply=""
		fi
		case "$reply" in
			[Yy]*) do_claude_copy ;;
			*) say "  Skipped. Re-run with --claude to copy later." ;;
		esac
		;;
esac

# ---------------------------------------------------------------------------
# Step 4. Next steps.
# ---------------------------------------------------------------------------
say ""
say "Done."
say ""
say "Next steps:"
say "  1. Read docs/QUICKSTART.md. Your first survey in 10 minutes."
say "  2. Confirm your authorization and scope before any active probe."
say "  3. Run a survey:  make chain IPS=your-scope.txt"
say ""
say "Authorization is the gate. Operate only within formal engagement scope, on"
say "designated targets. See DISCLAIMER.md."
