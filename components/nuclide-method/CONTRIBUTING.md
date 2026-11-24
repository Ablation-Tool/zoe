# Contributing

This is a public repo about a methodology, not a dump of live target data. The single rule that makes that possible: nothing you commit may identify a real target. Read this before opening a PR.

## The public-visibility contract

Every contribution carries this contract. A PR that breaks it does not merge.

- **Never commit a real target.** No real IPv4 or IPv6 of a scanned host. No real domain or hostname. No operator, victim, or organization name. No rDNS or PTR. No real TLS or SSH fingerprint. No machine-readable IP list or target list.
- **Illustrative addresses use the documentation ranges only.** RFC 5737 for IPs: `192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`. `example.com` and `example.org` for domains. If a writeup needs a host, use a doc address. Always.
- **Sanitize to class level.** A finding describes the *class* of exposure (an unauthenticated vector DB, a claimable admin state, a PII-shaped schema), not the specific store. Report the schema and the field names, never the records.
- **No researcher PII.** No personal name, no personal email, no pseudonym. The contact string is `nuclide-research.com`. The voice is the firm: we and our, never a first person.
- **No disclosure routing in the repo.** Recipient names, abuse addresses, and CC chains stay out of public files.

## Every finding carries a verification tier

A scan produces candidates. A finding requires a verified read. State the tier explicitly so a reader knows what was actually exercised:

- **Verified** - a 200-with-data read confirmed the exposure. The artifact backs the claim.
- **Surface open, access not exercised** - the port or endpoint answered, but access was blocked or deliberately not driven to a read. This is not a confirmed finding. Say so.
- **Candidate** - a scanner or dork flagged it; nothing has been confirmed.

No tier label without the evidence to back it. A blocked read is never reported as a confirmed finding.

## How to contribute

1. Start from a template in [`templates/`](templates/). Survey writeups, insight entries, and finding records each have a shape. Match it.
2. Sanitize as you write, not after. Swap real addresses for RFC 5737 doc ranges at the moment you type them.
3. Run the local boundary audit before you push:
   ```
   make audit
   make lint
   ```
   `audit` mirrors the CI checks. `lint` runs shellcheck and the em-dash sweep.
4. Open the PR. The CI boundary-audit must pass. It rejects real-looking IPs, real-looking domains, PII patterns, and the em-dash tell. A red check blocks the merge.

## The insight series grows by PR

The methodology is a numbered insight series. Each survey extracts a numbered insight; the surveys produce data, the insights produce the methodology. New insights land as PRs against that series. Claim the next free number, write the entry from the template, cite the survey that produced it, and keep it sanitized to class level like everything else.

## Code of conduct

Participation is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). Be the kind of collaborator you would want to review your work.
