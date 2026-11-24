# Security Policy

`nuclide-method` is a methodology repository. It ships documentation, templates,
shell scripts, and a reference chain runner. It runs no service and holds no user
data. There is still a way to report a problem, and there is a clear line on what
this project will and will not help you do.

## Reporting a vulnerability in this repository

If you find a security issue in the repository itself, a flaw in
`chain/run-chain.sh`, `bootstrap.sh`, the CI boundary audit, or anything that
could leak data or run unintended commands, report it privately.

- Contact: **nuclide-research.com**.
- Do not open a public issue for a security flaw in the tooling.
- Include the file, the behavior, and a minimal reproduction. A working proof is
  worth more than a description.

We acknowledge reports and work the fix in the open once a patch exists.

## Reporting an exposed system you found with this method

This method finds exposed third-party infrastructure. If you found a real exposed
system by running it, that disclosure does not route through this repository.

- Route the disclosure to the **operator** of the affected system, through their
  published security contact, their WHOIS `OrgAbuseEmail`, or the relevant
  national CERT.
- Practice responsible disclosure. Report metadata, not exfiltrated data. Names
  are the finding.
- Do not file the exposed system, its address, or its operator in this repo, in
  an issue, or in a pull request. The repository teaches the method and ships no
  live target data, by design.

## Authorization

You may run this method only against targets you are authorized to test, under a
formal engagement scope, on designated targets, with written permission. See
[DISCLAIMER.md](DISCLAIMER.md). A report that describes unauthorized testing will
not be accepted.
