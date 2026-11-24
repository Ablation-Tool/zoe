# Worked Examples

Four surveys, sanitized to class level. The lesson is public. The victim is not.

Each file below started as a real assessment. We stripped every live target: no
real address, no real domain, no operator name, no machine-readable host list.
What stays is the method, the discipline lane it teaches, and the verification
tier the finding actually earned. Read them as method, not as a target list.
Every example here carries no live target.

The four cover the four corners of the work. One is a finding proved from source
with no probe. One is a population survey that breaks the program's own thesis.
One is a database read held at metadata. One is a model-server class anchored to
a published CVE. Different target classes, different verification tiers, one
discipline running through all four.

Start with [00-sample-run.txt](00-sample-run.txt) for the shape of a full chain
run over a documentation-only scope. The four worked surveys below each go deep
on one corner of that run.

| File | Target class | Discipline lane taught | Verification tier |
|---|---|---|---|
| [01-zep-ce-empty-apisecret.md](01-zep-ce-empty-apisecret.md) | Commercial | Code-only, read the source not the target | inner-A / outer-0 |
| [02-rasa-population-survey.md](02-rasa-population-survey.md) | Chatbot framework | Population survey, auth-on-default falsification | outer-2 |
| [03-scylladb-schema-only.md](03-scylladb-schema-only.md) | Database | Restraint, metadata not exfiltration | access-surface verified |
| [04-ollama-api-create-class.md](04-ollama-api-create-class.md) | Model server | Unauth model server, CVE-anchored | class-level |

## How to read the tier column

The tier is the honest ceiling of each finding, not a severity score.

- **inner-A / outer-0** (01): the control flow is confirmed against the source,
  the logic is reproduced in a standalone harness, and no live host was touched.
  Surface open by code reading, access not exercised. The label refuses the word
  "exploitable" because the binary was never exercised.
- **outer-2** (02): the read-only probe ran across a deduped population and
  produced two rates against the same N. A population statement, earned, not a
  single-host anecdote.
- **access-surface verified** (03): the open port answered and the schema came
  back. We confirmed the access surface and stopped. No record contents pulled.
  Metadata is the finding; the rows are not the evidence.
- **class-level** (04): the finding is stated about the platform class and
  anchored to a published CVE, not asserted against a named deployment.

## The thread

Verification is the load-bearing stage in all four. A scanner produces a
candidate. The work in each file is what turns that candidate into a finding,
and what each file declines to claim is as load-bearing as what it proves. The
restraint ethic governs throughout: deepen the proof, do not widen the scope,
and let the names be the finding.

---

*Prepared by NuClide Research. Contact: nuclide-research.com. Genericized
teaching examples. All operator and host identifiers removed. All illustrative
addresses are RFC5737 documentation ranges.*
