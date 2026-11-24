# Claude Operating-Protocol Adopter Kit

Inherit the operating loop, not just the docs. This kit loads the NuClide
methodology into an AI coding agent (Claude Code or similar) so the agent runs
the chain at session start instead of reading about it later.

It carries no identity and no private paths. There is no researcher name, no
email, no machine, no internal directory layout, no disclosure routing. The only
contact string is nuclide-research.com. The protocol is the method, stripped to
what a stranger can adopt and run.

---

## What is in here

```
claude/
  PROTOCOL.md      The operating loop. The chain checklist, the modes, the
                   orchestration pattern, the STOP-and-check rule, the
                   verification reminder, and pointers into ../docs/.
  hooks/           Optional session-start hooks (see "Session start" below).
  README.md        This file.
```

`PROTOCOL.md` is the load. The deeper why lives in [../docs/](../docs/), which
`PROTOCOL.md` points into at every stage.

---

## What it does

When loaded, the protocol makes the methodology the default operating logic for
any research, assessment, recon, investigation, or AI-infra task. Concretely:

- The agent reaches for the chain first, not a curl loop.
- Verification is treated as the load-bearing stage. A scan produces candidates.
  A finding requires a verified 200-with-data read.
- A null result is logged, not dropped.
- Every survey closes by codifying one numbered Insight.
- The restraint ethic governs: enumerate metadata, do not exfiltrate.

It does not force the chain onto unrelated tasks (website builds, tool
development, writing, ordinary coding). For those, the operating modes and the
orchestration pattern still apply. The assessment chain does not.

---

## Install into your own `~/.claude`

The protocol is a context file. Load it the same way you load any standing
instruction.

**Option A. Global, all projects.** Point your global Claude instructions at this
file, or paste its contents into your `~/.claude/CLAUDE.md`. Keep the
`../docs/` pointers working by cloning this repo somewhere stable and adjusting
the relative paths to that clone, or copy `docs/` alongside the protocol.

```
# from a clone of this repo
mkdir -p ~/.claude
cp claude/PROTOCOL.md ~/.claude/nuclide-protocol.md
# then reference ~/.claude/nuclide-protocol.md from your ~/.claude/CLAUDE.md
```

**Option B. Per project.** Drop the protocol into a project's `.claude/`
directory so it loads only for that repo.

```
# from a clone of this repo, run inside your target project
mkdir -p .claude
cp /path/to/nuclide-method/claude/PROTOCOL.md .claude/nuclide-protocol.md
```

Either way, the agent reads it at session start. The protocol references
`../docs/` with relative paths, so keep `docs/` reachable from wherever you place
`PROTOCOL.md`, or update the links to point at your clone.

---

## Session start

At session start the protocol does three things:

1. **Loads the default operating logic.** The chain is active for assessment
   work. No trigger word required, though the trigger words ("assessment",
   "survey X", "investigate <target>") remove all ambiguity.
2. **Reads session continuity.** It looks for `SESSION.md` in the active project
   root and any working-memory index, so prior-session state is read, not
   reconstructed.
3. **Posts the chain checklist on the first assessment action.** Before any
   probing, the agent posts the full chain and marks each step as it runs.

If you want this wired to fire automatically, the optional hooks in `hooks/`
re-post the protocol at session start. They are optional. The protocol works as a
plain context file without them.

---

## Public tools vs documented stage roles

The chain in `PROTOCOL.md` names public tools where a public tool fills the role
(nmap, httpx, nuclei, recongraph, aimap, aimap-profile, BARE). Where a stage was
run by private tooling, the chain shows the documented stage role instead (for
example "ACTIVE-BANNER", "LEDGER", "REPORT"), so the loop runs with any
equivalent tool in that role. The stage roles correspond to the eight-stage
pipeline in [../docs/METHODOLOGY.md](../docs/METHODOLOGY.md); the checklist adds
operational sub-steps with their own IDs. You can run the whole chain with public
tooling plus whatever fills the ledger, scoring, and reporting roles in your own
setup.

---

## Carries no identity, no private paths

By design:

- No researcher name, no email, no location, no background.
- No private absolute paths, no internal database paths, no machine names.
- No disclosure-recipient routing. Disclosure is handled by the restraint ethic
  and the operator-or-CERT posture in [../docs/RESTRAINT-ETHIC.md](../docs/RESTRAINT-ETHIC.md),
  not by an embedded recipient list.
- No live target data in any artifact. Illustrative addresses use RFC5737
  documentation ranges. Illustrative domains use example.com / example.org.

If you fork this, keep that boundary. It is what makes the kit safe to run in
public.

---

*NuClide Research. Authorized-testing-only methodology. Operate within formal
engagement scope, on designated targets. Contact: nuclide-research.com.*
