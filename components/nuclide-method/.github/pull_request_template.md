## What this PR adds

<!-- One or two lines. A survey writeup, a numbered insight, a tool doc, or a fix. -->

## Public-visibility contract

This repository is public and ships no live target data, by design. Confirm every
box before you request review. A PR that trips the CI boundary audit will not merge.

- [ ] No real target IPs or domains. Every address is an RFC 5737 documentation
      range (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`) or `example.com`.
- [ ] No operator, victim, or organization names. The finding describes a class,
      not a specific host.
- [ ] No disclosure routing. No recipient, no abuse address, no CC list.
- [ ] Every finding states an explicit verification tier and does not upgrade it.
- [ ] No researcher PII and no first-person voice. The repository speaks as a lab.
- [ ] No em dashes. `make audit` and `make lint` pass locally.
- [ ] The only hard coverage number is the corpus size. Other figures are slots
      or clearly illustrative ranges.

## Verification

<!-- How did you confirm the change? For a survey: the verification tier and the
     evidence shape. For a tool fix: the command you ran and its output. -->
