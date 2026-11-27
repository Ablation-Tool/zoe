# Quickstart: your first survey in 10 minutes

This is the fast path from a clean machine to a verified finding. It does not
re-explain the method. For the why, read
[METHODOLOGY.md](METHODOLOGY.md) and
[VERIFICATION.md](VERIFICATION.md). This page is the how.

---

## Authorization comes first. Read this before anything else.

You may run this method only against targets you are authorized to test.

- Operate inside a formal engagement scope, on designated targets, with written
  permission. No exceptions.
- Your scope file lists only hosts you are allowed to probe. A host that is not
  in scope does not get touched, not even a banner grab.
- The illustrative addresses in this doc are RFC 5737 documentation ranges
  (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`). They route nowhere on
  purpose. Replace them with your authorized scope. Do not copy them as live
  targets.

If you cannot point at the authorization, stop here. There is no step two
without it. See [DISCLAIMER.md](../DISCLAIMER.md).

---

## Prerequisites

| Need | Why | Check |
|---|---|---|
| Go 1.21+ | The tools install with `go install` | `go version` |
| git | Tool fetch and repo work | `git --version` |
| make | The verb layer over the chain | `make --version` |
| A scope file | The hosts you are authorized to probe | you write it |

No sudo. No root. The tools install into your Go bin dir.

---

## Step 1. Bootstrap (about 3 minutes)

From the repo root:

```sh
./bootstrap.sh
```

This checks for `go` and `git`, installs the public NuClide tools, and offers to
copy the Claude config into `~/.claude`. It is idempotent and fail-soft. A tool
that does not install warns and the run continues, so one bad fetch never blocks
the rest.

Confirm your Go bin dir is on PATH. The script prints the exact dir. If it warns
that the dir is not on PATH, add it:

```sh
export PATH="$PATH:$(go env GOPATH)/bin"
```

Verify a couple of tools resolve:

```sh
command -v aimap
command -v herald
```

The install list in `bootstrap.sh` is a convenience, not the authority. Verify
it against [ARSENAL.md](ARSENAL.md). The doc is the source of truth for which
tools exist and what they are called.

---

## Step 2. Write your scope file (about 2 minutes)

A scope file is one host per line. Nothing else. These are RFC 5737 examples;
replace every line with a host you are authorized to test.

```sh
cat > my-scope.txt <<'EOF'
192.0.2.10
192.0.2.42
198.51.100.7
203.0.113.0/24
EOF
```

Rules for the scope file:

- One target per line. IPs or CIDRs.
- Every line is a host you have written permission to probe. If you are not
  sure a line is in scope, it is not in scope. Delete it.
- The file stays local. It is gitignored. A machine-readable target list never
  belongs in a public repo.

---

## Step 3. Run the chain (about 3 minutes for a small scope)

The chain is the assessment pipeline behind one verb. Point it at your scope:

```sh
make chain IPS=my-scope.txt
```

`IPS` is the scope-file argument. The chain runs discover, active-banner,
fingerprint, verify, attribute, classify, ledger, score, and codify in order.
Verify is the load-bearing stage. Everything before it produces candidates.
Verify is what turns a candidate into a finding.

Run `make help` to see every target.

---

## Step 4. Read the output

The chain prints a per-stage summary and writes to the local ledger. Read it
with three questions in mind:

1. **What answered?** A host with an open port and a banner is a candidate, not
   a finding. Note it and move on.
2. **What verified?** A `200`-with-data read, or a schema returned, is the
   evidence. That is the finding. Without it you have a surface, not a finding.
3. **What got blocked?** A port that answered but refused access is "surface
   open, access not exercised." Record it as exactly that. It is not a
   confirmed finding, and you do not call it one.

A null result is a logged result. Zero verified findings across a clean scope is
a real outcome, written down, not a failed run.

---

## Step 5. Write the finding

Start from the template. Do not freehand a finding.

```sh
mkdir -p findings
cp templates/FINDING-REPORT.md findings/001-my-finding.md
```

The `findings/` directory is gitignored. A finding you write stays local until you
have sanitized it to class level and chosen to contribute it.

Fill in what the template asks: what the exposure is, why it matters, how it
chains, the fix, and the references. Sanitize as you write. Swap any real
address for an RFC 5737 doc range the moment you type it. The finding describes
the class of exposure, not the specific store. The schema and the field names
are the evidence. The records are not.

---

## Step 6. Verify before you claim anything

This is the step that separates a finding from a guess.

- A claim of "exposed" needs a `200`-with-data read behind it. If you have the
  artifact, the finding is **Verified**.
- If the port answered but the read was blocked, the finding is **surface open,
  access not exercised**. Say that, in those words.
- If only a scanner or a dork flagged it, the finding is a **candidate**. Mark
  it candidate. Do not promote it.

Do not write "exploitable" until you have exercised the path and have the
artifact. The label has to match what you actually did. A blocked read reported
as a confirmed finding is the failure this whole method exists to prevent.

---

## What to do next

- Re-run after a fix window to confirm the exposure is closed.
- Extract the lesson. Every survey produces a numbered insight. See
  [INSIGHTS.md](INSIGHTS.md) for the series and how to add to it.
- Read the worked examples in [`examples/`](../examples/) for four findings at
  four verification tiers, sanitized to class level.

---

*Prepared by NuClide Research. Contact: nuclide-research.com. Authorized testing
only. All illustrative addresses are RFC 5737 documentation ranges.*
