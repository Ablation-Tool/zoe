# Update the portfolio

The JSON catalog is the source of truth for CLI output and the generated résumé. Keep descriptions concrete: name the problem, the action, and the result a reader can inspect.

Each project needs:

- `id`: unique lowercase slug.
- `name`, `category`, `summary`, and `problem`: nonempty strings.
- `methods`, `tags`, and `languages`: nonempty lists of strings.
- `url`: an HTTPS source link.
- `evidence_status`: `owner-reported` or `verified`.

Verified entries also need `verification.source`, `verification.checked_on`, and `verification.notes`. Explain exactly what the source proves. Do not convert an unverified portfolio statement into a verified record by copying it.

Run `python3 -m fieldwork validate` and `python3 -m unittest discover -s tests -v` after edits. Regenerate `RESUME.md` with `python3 -m fieldwork resume > RESUME.md` when profile data changes. Keep the README's selected-project count in sync.

Do not add private engagement notes, client secrets, or personal account credentials. Contact details should be the public professional address.
