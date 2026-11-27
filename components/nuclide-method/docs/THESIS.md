# The Thesis

This document states the research hypothesis that the method exists to test. It is the framing no single-tool README carries. A README tells you how a tool runs. This tells you what the runs are for.

## The hypothesis, stated plainly

> Open-source AI and LLM infrastructure trends toward authentication-on-by-default across generations, under disclosure pressure. The drift is rightward over time. Some platforms invert the trend and ship with authentication opt-in. Those are the interesting negatives.

That is a claim about the world. It can be wrong. We treat it as a hypothesis, not a slogan, and the whole program is built to confirm it or break it.

A short vocabulary keeps the rest of this precise:

- **Auth-permissive default.** The platform ships so that the data layer is reachable with no authentication. Registration open, no key required, configuration readable on a public endpoint. The operator must add a control, not remove one.
- **Auth-on default.** The inverse. The platform ships closed. The operator must deliberately open it.
- **The rightward shift.** Across a platform's release history, the default posture moves from permissive toward closed. New major versions ship more locked down than the ones they replace.
- **Disclosure pressure.** Public surveys plus upstream reports to maintainers. The mechanism we believe drives the shift.

## Why it is a hypothesis and not a slogan

A slogan is unfalsifiable. "Secure by default is better" cannot be wrong. Our claim can be wrong in named ways:

1. A new-generation platform ships auth-on by default at version one, with no disclosure pressure behind it. The rightward shift would not be a shift, it would be a starting point, and the disclosure-pressure mechanism would lose its load.
2. A platform under heavy public disclosure stays permissive across two or three minor-version cycles with no change. The pressure-moves-the-rate claim fails.
3. The posture turns out to track the version cohort, not the platform cohort. If a 2024 release and a 2026 release of unrelated platforms share a rate while two releases of the same platform diverge, the framing is wrong about what the unit of analysis is.

Each of these is checkable against the corpus. A hypothesis you cannot lose is not a hypothesis. This one you can lose.

## The interesting negatives

A platform that ships auth-on by default does not weaken the thesis. It confirms it by contrapositive.

The claim is "trends toward auth-on under disclosure pressure." A platform that is already closed is the trend's destination, not a counterexample to it. A survey that returns zero open instances is a positive result for the program even though it is a negative result for the scan. It is the shape we predicted the cohort would move into.

So the negatives are filed as confirmations and they are published. A survey of a platform that comes back clean is worth writing up for the same reason a closed valve is worth logging on a P&ID. The absence is data. It tells you the control held. The only survey that teaches nothing is the one that was never run, and a null result is a logged result, never a skipped one.

The genuine counterexample, the thing that would actually break the thesis, is the inverted platform: same open-source lineage as the permissive cohort, but auth opt-in, permissive by deliberate design choice rather than by neglected default. That is the case we hunt for. Finding one would not embarrass the program. It would be the most valuable single result it could produce, because it would tell us the cohort framing is incomplete.

## Why this makes it a research program, not a scan

A scan answers "what is open right now." A research program answers "why is it open, what class of mistake put it there, and does the rate move when you push on it."

The difference is structural:

- **The thesis is testable.** Every survey is run as a test of it. The question on the table is never only "what did we find on this platform." It is also "does this platform confirm the cohort pattern or break it." The finding and the test are the same act.
- **The corpus is the evidence base.** One survey is an anecdote. The value is in the accumulation. A platform rate means nothing alone and everything next to twenty others. The corpus is what lets a single number become a claim about a cohort. Each survey is codified into a numbered insight so the evidence compounds instead of evaporating.
- **The mechanism is named and tracked.** We do not only measure the rate. We predict that disclosure pressure moves it, within two to three minor-version cycles, and we watch the release history to see whether it does. That is the part a scan cannot have. A scan has no theory of why the number is what it is or what would change it.
- **Negative results are first-class.** In a scan, an empty result is a wasted run. In this program it is a confirmation by contrapositive and it gets written up. A method that treats null as failure cannot run a research program, because half the confirmations are nulls.

## The discipline that keeps it honest

A hypothesis is only worth holding if the evidence under it is real. Two rules carry that weight.

**Verification is the load-bearing stage.** A scanner produces candidates. Verification produces findings. The scan is the easy part. Most of the codified failure modes in this program are verification-stage failures, not discovery-stage ones. At population scale, skipped verification does not fail randomly. It fails systematically: confident, reproducible, wrong numbers that look exactly like right ones. A finding is a 200-with-data read, exercised and recorded. Anything short of that is "surface open, access not exercised," and it is labeled that way, not promoted to a finding to make the table look fuller.

**The restraint ethic governs every survey.** Enumerate metadata, do not exfiltrate. The names are the finding. A field list, a schema, a config key returned on a public endpoint, that is the evidence, and it is enough. Payloads are sampled minimally and only to confirm severity, never to collect. The program proves exposure without becoming the breach it documents. That restraint is not a constraint on the research. It is what makes the research publishable.

## The shape of a survey

Every survey runs the same pipeline, in the same order, against a platform population:

```
Discover -> Fingerprint -> VERIFY -> Attribute -> Classify -> Ledger -> Score -> Codify
                            ^^^^^^
                            load-bearing
```

These are the numbered stages. The Active-Banner prefilter sits between Discover
and Fingerprint; the full form is in [METHODOLOGY.md](METHODOLOGY.md).

Discover finds the population. Fingerprint identifies the platform. Verify turns candidates into findings or refutes them. Attribute ties exposures to operators where the public record allows. Classify sorts by category and severity. Ledger records every observation, including the nulls. Score rates the cohort. Codify extracts the numbered insight that feeds the next survey.

The output of a survey is two things: a rate for the platform, and an insight for the method. The rates build the evidence base. The insights build the method that produces the next rate. The program is the loop between them.

## What success looks like

The program succeeds if, over enough surveys, three things hold:

1. The cohort pattern is visible. New-generation platforms cluster by category in their default posture, and the clustering is stable enough to predict the next platform's rate before the survey runs.
2. The rightward shift is measurable. A platform's posture is more closed in its later releases than its earlier ones, and the movement tracks disclosure pressure rather than calendar time alone.
3. The negatives line up. The clean surveys and the closed platforms sit where the thesis predicts they should, as the destination of the trend, not as noise against it.

And it succeeds in a different and better way if any of those breaks, in a named manner, against a real platform in the corpus. A broken thesis that names its own counterexample is a result. That is the whole point of stating it as a hypothesis. We would rather lose the claim cleanly than keep it by never testing it.

## In one paragraph

Open-source AI and LLM infrastructure trends toward authentication-on by default across generations under disclosure pressure. The claim is falsifiable, the surveys test it, the corpus is the evidence, the negatives confirm it by contrapositive and get published, and verification is the stage that keeps the numbers honest. That is a research program. A scan would just tell you what is open today.
