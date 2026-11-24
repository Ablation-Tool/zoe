# SessionStart hook

`assessment-protocol.sh` prints a short methodology reminder at the start of
every Claude Code session. The point is to make the method unmissable so it is
never re-derived from scratch and never skipped because it was not loaded.

The method is the default operating logic for assessment, recon, and AI-infra
work. The reminder is a banner, not a gate. It says four things:

- Verification is the load-bearing stage. A scan produces candidates;
  verification produces findings.
- The methodology and the chain are active by default for assessment work.
- Post the chain checklist first, then run it, every step, in order.
- A null result is a logged result, never a silent skip.

It references the canon at `docs/METHODOLOGY.md` and the runner at
`chain/run-chain.sh` by relative path. It carries no identity, no private
paths, and no targets.

## What it prints

```
  NuClide method - active by default for assessment, recon, and AI-infra work.

  Verification is the load-bearing stage. A scan produces candidates. Verification produces findings.
  A 200 is identity, not auth. A dork hit is not an instance. Earn the label with a read of real data.
  Blocked access is "surface open, access not exercised", never an asserted finding.

  Post the chain checklist first. Then run it. Every step, in order. Mark each one as it runs.
  Discover -> Active-Banner -> Fingerprint -> [ VERIFY ] -> Attribute -> Classify -> Ledger -> Score -> Codify
  Canon: docs/METHODOLOGY.md     Runner: chain/run-chain.sh

  Null result = logged result, never a skip. If a step is genuinely N/A, say why in one line.
  Primary source over framing. Codify every survey into a numbered insight.

  STOP-and-check: about to write a curl or urllib probe loop? A chain step already covers it.
  Session continuity: read SESSION.md in the project root at start, update it at end.
```

Color is emitted only to an interactive terminal and is suppressed when
`NO_COLOR` is set. The script is POSIX `sh` and shellcheck-clean.

## Wire it into settings.json

Claude Code reads hooks from `~/.claude/settings.json` (global) or a project
`.claude/settings.json` (per repo). Add the `SessionStart` block below. Use the
absolute path to your checkout, or a path relative to where Claude Code runs.

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh /ABSOLUTE/PATH/TO/nuclide-method/claude/hooks/assessment-protocol.sh"
          }
        ]
      }
    ]
  }
}
```

Replace `/ABSOLUTE/PATH/TO` with your checkout location. To scope the reminder
to one repo instead of every session, put the same block in that repo's
`.claude/settings.json` and point the command at a relative path.

## Verify

```sh
sh claude/hooks/assessment-protocol.sh   # render the banner once
sh -n claude/hooks/assessment-protocol.sh # syntax check
```

Start a new Claude Code session and confirm the banner appears.
