---
name: vuln-report
description: Writing guide for vulnerability disclosure reports. Apply when drafting, editing, or reviewing coordinated disclosure documents, CVE descriptions, PSIRT submissions, or security advisories. Enforces 70 rules synthesized from nine technical writing books.
tools: [Read, Edit, Write]
---

# Vulnerability Report Writing Guide

70 rules for coordinated disclosure reports, synthesized from nine technical writing books: *Plain Style* (Lauchman, AMACOM 2008), *Docs for Developers* (Bhatti et al., Apress 2021), *Technical Writing for Software Developers* (Chinchilla, Packt 2024), *Technical Writing, 2nd Ed.* (Laplante, CRC Press 2018), *The Truth About the New Rules of Business Writing* (Canavor/Meirowitz, Pearson 2008), *A Practical Guide to Business Writing* (Al Maskari, Wiley 2012), *Style Guide for Business Writing* (Thomsett, De Gruyter 2017), *Plain Language in Government Writing* (Myers, Berrett-Koehler 2020), and *Technical Writing for Developers* (Hall, Apress 2024).

---

## Core Principle

**Style is judgment about the reader, not decoration.** Security engineers, PSIRT analysts, and legal reviewers read functionally: they hunt for the bottom line, skim everything else, and stop reading the moment the prose makes them work. A finding that takes three paragraphs to reach its point is a finding that does not get read.

Good writing works hard so the reader does not have to.

---

## Reader Expectations in Security Disclosures

Security disclosures receive a functional reading. The reader expects:

1. **The bottom line in the first sentence.** State the vulnerability before the evidence. The PSIRT analyst does not read like a mystery novel reader — she skips to the conclusion. Put the conclusion first.
2. **Economy of expression.** No one reads "performed a thorough and complete investigation of" when "investigated" will do.
3. **Words she already knows.** "Heap overflow" is better than "memory allocation boundary violation condition." Jargon shared within the profession is fine; invented jargon is not.
4. **Conformance to standard English.** Spelling errors, grammar mistakes, and punctuation failures stop her from reading your ideas and start her editing your prose. That is not what you want.

---

## Part 1 — Sentence Construction

### 1. Write with verbs, not nouns

Convert nominalized verbs back to verbs. The verb is where the finding lives.

| Wordy (avoid) | Concise (prefer) |
|---|---|
| Exploitation of the vulnerability was performed | We exploited the vulnerability |
| Made a determination that the function is vulnerable | Determined that the function is vulnerable |
| Performed an analysis of the binary | Analyzed the binary |
| Gave a demonstration of code execution | Demonstrated code execution |
| The function performs allocation of memory without bounds checking | The function allocates memory without checking bounds |

**Rule:** When you see perform, make, give, do, provide, or have followed by a noun, replace the pair with the embedded verb.

### 2. State what the subject does, not what it is

Minimize `is/are/was/were`. Tell the reader what the subject does.

| Avoid | Prefer |
|---|---|
| The parser is in violation of safe string handling requirements | The parser violates safe string handling requirements |
| The function is responsible for the corruption | The function corrupts the buffer |
| The credential is susceptible to interception | An attacker can intercept the credential |

### 3. Avoid smothered verbs

Smothered verbs end in `-ion`, `-ment`, `-ance`, `-ence`. Restore the verb.

| Smothered | Restored |
|---|---|
| Performed exploitation of | Exploited |
| Performed verification of | Verified |
| Made the determination | Determined |
| Conducted enumeration of | Enumerated |
| Provided confirmation that | Confirmed that |
| Conducted authentication bypass | Bypassed authentication |

### 4. Reveal the verb early

Subject and verb belong together. Every word between them is delay.

| Delayed verb | Verb revealed early |
|---|---|
| The function, present in all versions prior to 9.2, which handles incoming DHCP options without length validation, overflows. | The function overflows because it handles incoming DHCP options without validating length. All versions prior to 9.2 are affected. |

### 5. Use active or passive based on what deserves emphasis

Do not avoid passive voice — place the most important idea as subject.

- **Active when the actor matters:** `The parser writes beyond the buffer boundary.`
- **Passive when the result matters:** `The buffer is overwritten before the return address.`
- **Avoid divine passive to dodge accountability:** Write "We did not test firmware versions after 9.6" — not "Versions after 9.6 were not tested."

### 6. Assert — avoid negation chains

Negations leave meaning up in the air.

| Avoid | Prefer |
|---|---|
| The function does not perform bounds checking | The function skips bounds checking |
| Authentication is not enforced | Authentication is absent |
| The value is not validated before use | The value reaches `memcpy` unvalidated |
| Not unlikely to allow code execution | Likely allows code execution |

Two negatives do not clarify — they confuse. Write what is true, not what is not false.

---

## Part 2 — Word Order and Emphasis

### 7. Bottom line first — always

Every finding section, every paragraph, every sentence: lead with the conclusion.

**Wrong order (mystery novel):**
> During analysis of the firmware binary, we identified a function at address 0x294ef0. This function processes network-supplied data. The length parameter is derived from a user-controlled field. The function passes this length directly to `memcpy`. This allows an attacker to write past the destination buffer.

**Right order (bottom line first):**
> Address `0x294ef0` contains a `memcpy` call with a user-controlled length, enabling heap overflow. The length originates from a network-supplied packet field and reaches `memcpy` without bounds checking.

### 8. Put modifiers beside the word they modify

Loose modifiers produce unintended meanings and slow readers.

| Ambiguous | Clear |
|---|---|
| The attacker can execute code on the device remotely without authentication | Without authentication, the attacker can execute code remotely on the device |
| We confirmed the vulnerability was exploitable during testing in a lab environment | In a lab environment, we confirmed the vulnerability is exploitable |
| The credential transmitted over the network is intercepted by an attacker using Wireshark | Using Wireshark, an attacker can intercept the credential transmitted over the network |

### 9. Subject–verb–object order

This order stresses the right idea and minimizes misreading. Keep subject and verb close.

### 10. Use parallel structure for finding lists

Findings of equal importance should use identical structures.

**Not parallel:**
> - Unauthenticated access to the admin interface
> - The session token can be predicted
> - Logging is insufficient and events are missing

**Parallel:**
> - Admin interface allows unauthenticated access (CWE-306)
> - Session token is predictable (CWE-340)
> - Audit log omits authentication events (CWE-778)

Apply the same parallel rule to bullet lists of impacts, recommendations, and affected versions.

### 11. Length dilutes; brevity emphasizes

Isolate the most critical finding. Put it in a short sentence. Put that sentence in a paragraph by itself.

> Unauthenticated remote code execution is possible on all devices running firmware prior to 9.14.

That sentence should not share a paragraph with the background story.

---

## Part 3 — Word Choice

### 12. Use the precise verb — never "impact" or "affect" alone

"Impact" and "affect" are Rorschach cards — the reader supplies the meaning.

| Vague | Precise |
|---|---|
| This vulnerability impacts the device | This vulnerability allows code execution on the device |
| The flaw affects authentication | The flaw bypasses authentication |
| Exploitation would negatively impact availability | Exploitation crashes the service (DoS) |
| This could impact sensitive data | This exposes credentials stored in `/etc/shadow` |

### 13. Name the exact capability

Every finding must state exactly what an attacker can do. Not "could lead to security issues" — "allows unauthenticated read of `/etc/passwd`."

Capability verbs for findings:
- `execute` — remote/local code execution
- `read` — unauthorized file/memory read
- `write` — unauthorized file/memory write
- `bypass` — authentication/authorization bypass
- `crash` / `terminate` — denial of service
- `disclose` — information disclosure
- `escalate` — privilege escalation
- `intercept` — man-in-the-middle

### 14. Avoid "may" when you mean "can" or "does"

`May` is ambiguous — it can mean "is permitted to" or "possibly will."

| Ambiguous | Clear |
|---|---|
| An attacker may execute arbitrary code | An attacker can execute arbitrary code |
| The value may be controlled by an attacker | An attacker controls the value |
| Exploitation may allow privilege escalation | Exploitation allows privilege escalation |

Use `may` only when genuinely uncertain. Use `can` when the capability exists. Use `does` when confirmed.

### 15. Avoid "could potentially allow" constructions

This phrase hedges a proven finding into meaninglessness. If you reproduced the vulnerability, say so.

| Hedge (avoid) | Direct (prefer) |
|---|---|
| This could potentially allow an attacker to gain elevated privileges | We reproduced privilege escalation from a guest account |
| A malicious actor could potentially exploit this to execute code | We executed arbitrary code; see PoC in §3.2 |

When genuinely uncertain, say so directly: "We did not confirm exploitability; the pattern suggests possible overflow."

### 16. Use consistent terms throughout

Varying terms to avoid repetition misleads the reader.

If it is a "session token" in the executive summary, it is a "session token" in the finding, the impact section, and the recommendation — not a "cookie," "credential," "authentication identifier," or "bearer token" unless those distinctions matter.

**Rule:** Call each thing by its exact technical name and keep that name throughout the document.

### 17. Define on first use; then use the abbreviation

Write "Cross-Site Scripting (XSS)" the first time; "XSS" thereafter. Write "Common Vulnerabilities and Exposures (CVE)" the first time; "CVE" thereafter.

Do not introduce an abbreviation you will not use again.

### 18. Avoid redundant security qualifiers

| Redundant | Meaning |
|---|---|
| Pre-auth unauthenticated access | Unauthenticated access |
| Remote network-based exploitation | Remote exploitation |
| User-supplied attacker-controlled input | Attacker-controlled input |
| Completely compromised system takeover | Full system compromise |
| Successful exploitation of this vulnerability | Exploitation |

### 19. Word problems specific to security writing

| Problem word | Issue | Alternative |
|---|---|---|
| `trivial` (to exploit) | Subjective; PSIRT will want to verify | "requires no authentication" / "requires no prior knowledge" |
| `critical` / `severe` | Reserve for CVSS ≥ 9.0 | Use CVSS score; let the score speak |
| `arbitrary` code execution | Correct term — keep it | N/A |
| `arbitrary` file read/write | Correct — keep it | N/A |
| `sensitive` data | Vague — specify | "credentials" / "private keys" / "patient records" |
| `full compromise` | Acceptable if accurate | Clarify scope: "full device compromise" vs. "full account compromise" |
| `bypass` without object | Incomplete | "bypass authentication" / "bypass ASLR" |
| `vector` (attack) | Overused | "attack path" / "exploit path" / name the specific path |
| `surface` (attack) | Jargon that hides meaning | State what is exposed |

---

## Part 4 — Document Structure

### 20. Executive summary: severity cluster pattern

Open with a single sentence grouping findings by severity.

> This disclosure documents four critical vulnerabilities in [Product] [Version] that allow an unauthenticated remote attacker to execute code (F1, F3), read arbitrary files (F2), and deny service to all connected clients (F4).

Follow with one paragraph per severity tier. The PSIRT analyst can stop reading after the summary and still know exactly what she is dealing with.

### 21. Per-finding structure

Each finding must answer four questions in this order:

1. **What is the bug?** One sentence: the exact flaw and location.
2. **What can an attacker do?** One sentence: the capability, no hedging.
3. **How do we know?** Evidence: file path, offset, class name, function name. PoC command or code block.
4. **How do you fix it?** Specific remediation, not "validate all inputs."

**Example (correct order):**

> **F1 — Stack Overflow in `parse_option()` (CWE-121, CVSSv3 9.8)**
>
> `parse_option()` at `0x00401A20` copies a network-supplied option value into a fixed 256-byte stack buffer without checking length, allowing a remote unauthenticated attacker to overwrite the return address and execute arbitrary code.
>
> The vulnerable call is `strncpy(buf, opt_val, opt_len)` where `opt_len` is taken directly from the packet and `buf` is 256 bytes. With `opt_len > 256`, the overflow overwrites the saved return pointer. No canary or RELRO is present.
>
> **PoC:** `python3 poc_f1.py <target_ip>` — spawns a reverse shell on port 4444.
>
> **Remediation:** Validate `opt_len ≤ sizeof(buf)` before the copy, or replace `strncpy` with a bounds-checked alternative. Enabling stack canaries and RELRO on the affected binary would significantly raise the exploitation cost.

### 22. Titles: what and where, not how it feels

| Bad title | Good title |
|---|---|
| Critical Security Vulnerability | Unauthenticated RCE in DHCP Parser |
| Serious Authentication Issue | Authentication Bypass in Admin API (CVE-XXXX-XXXX) |
| Memory Safety Concern | Heap Overflow in `parse_tlv()` Leading to Code Execution |
| Multiple Security Issues | Four Vulnerabilities in [Product] 9.x: RCE, Auth Bypass, LFI, DoS |

The title is the first thing a PSIRT analyst reads. It must tell them what to escalate.

### 23. CVSS vectors: provide them, explain them

State the CVSS base score and vector. Then translate the vector into English for non-expert readers:

> CVSSv3.1 Base Score: **9.8 (Critical)**
> Vector: `CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H`
> Meaning: Exploitable over the network, no authentication required, no user interaction required, full confidentiality/integrity/availability impact.

### 24. Disclosure timeline: specific dates, no vague language

| Vague | Specific |
|---|---|
| Reported to vendor | 2025-03-14 — Initial disclosure sent to security@vendor.com |
| Vendor acknowledged | 2025-03-21 — Vendor confirmed receipt and assigned case ID VND-2025-0042 |
| Patch released | 2025-06-01 — Vendor released firmware 9.16 |
| Public disclosure | 2025-06-15 — This report published |

---

## Part 5 — Anti-Patterns to Eliminate

These patterns appear constantly in security reports and make readers work harder than necessary.

### 25. The three-paragraph warm-up

Do not open a finding with background. Readers skip it.

> ~~"This finding was discovered during the analysis phase of our research engagement. During this phase, our team performed a comprehensive analysis of the target binary using multiple analysis techniques..."~~

Cut to the finding.

### 26. The discovery narrative

The reader does not need to know how you found the bug — only what the bug is and what it does.

> ~~"While analyzing traffic between the client and server, we noticed an anomaly in the packet structure that led us to investigate further, at which point we identified that..."~~

State the vulnerability. Provide evidence. Move on.

### 27. Padding the impact section

Every sentence in the impact section must name a specific, concrete consequence.

> ~~"Successful exploitation of this vulnerability could have significant security implications for affected organizations, potentially compromising the confidentiality, integrity, and/or availability of sensitive data and system resources."~~

This says nothing. Replace it with what an attacker actually gets.

### 28. Hedge-stacking

Do not stack hedges. Each hedge weakens the finding.

> ~~"This vulnerability could potentially allow an attacker to possibly gain unauthorized access to certain system resources in some configurations."~~

If you confirmed it, say you confirmed it. If you did not, state the specific uncertainty.

### 29. Passive-voice actor concealment

Do not use passive voice to hide who found, tested, or failed to test something.

> ~~"It was observed that the function lacks validation."~~
> ~~"Testing was performed on firmware version 9.14."~~

Write: "We observed..." / "We tested firmware version 9.14."

---

## Part 6 — Audience, Process, and Code Evidence

### 30. Audience first: three questions before you write

Before writing any section, answer:

1. **Who is reading?** PSIRT analyst? Vendor engineer? CVE reviewer? Legal team? Each has different background knowledge.
2. **What do they want to accomplish?** Triage severity? Reproduce the bug? Write a patch? Assign a CVE?
3. **Why?** To protect their customers? For compliance? To assess litigation risk?

For disclosures: the primary reader is a PSIRT analyst who needs to know whether this is real, what it does, how fast to act, and how to fix it. Write for that reader first.

### 31. Curse of knowledge — write for the reader's knowledge level, not yours

The curse of knowledge: once you know something deeply, you cannot remember not knowing it. This causes writers to skip steps the reader needs.

For disclosure writing:
- Assume the reader knows their product — do not explain what their own software does.
- Do not assume they know your toolchain, methodology, or intermediate analysis steps.
- Do not assume they can read your exploit without explanation.
- State prerequisites explicitly: "This requires network access to the management port (default 8443)."

### 32. Content types — use the right type for each section

Four content types exist for different reader goals:

| Type | Reader goal | Use in disclosures |
|---|---|---|
| Conceptual | Understand what/why | Executive summary, vulnerability background |
| Procedural | Follow steps to do something | Reproduction steps, remediation instructions |
| Reference | Look up specific values | CVSS vectors, CWE numbers, affected versions, timeline |
| Troubleshooting | Diagnose and fix errors | Rarely applicable; do not default to this format |

Match the content type to the reader's goal in each section. A reproduction guide is procedural — numbered steps in order. A CVSS table is reference — do not add narrative to it.

### 33. F-pattern reading — front-load every section

Readers skim in an F shape: they read the first two lines fully, then scan the left edge of subsequent lines looking for anchor words. Most of the body text is never read.

Consequences for disclosure reports:
- The most important information belongs in the first paragraph of the report, the first sentence of each finding, and the first sentence of each paragraph.
- Do not bury the CVSS score in the third paragraph.
- Do not save the attacker capability for the conclusion.
- Subheadings are scan anchors — they determine whether a reader enters that section at all.

### 34. Four editing passes — run them in sequence

Do not mix concerns. Run four sequential passes:

1. **Technical accuracy** — Are all facts correct? Offsets, version numbers, CVE assignments, CVSS vectors?
2. **Completeness** — Can a PSIRT analyst reproduce this from what you wrote? Is anything missing?
3. **Structure** — Is information in the right order? Does bottom-line-first hold throughout every section?
4. **Clarity and brevity** — Are there weasel words, hedge-stacks, passive-voice concealment, smothered verbs?

Running clarity edits before structure edits wastes effort — clear sentences in the wrong order still mislead.

### 35. Code evidence — explain why, not what

Code in a disclosure report demonstrates exploitability. Rules:

- **Explain what the code proves**, not what each line does. "This PoC sends an oversized DHCP option, triggering the overflow at `0x00401A20`, and spawns a reverse shell." Not a line-by-line walkthrough.
- **Test every PoC** before including it. An exploit that does not work destroys credibility faster than any prose error.
- **Use descriptive placeholder strings**: `<TARGET_IP>`, `<AUTH_TOKEN>`, `<SESSION_COOKIE>`. Never `foo`, `bar`, `test`, or `AAAA`. Descriptive names tell the reader what to substitute.
- **Show only the minimum code** needed to demonstrate the vulnerability. Strip scaffolding.
- **Show the output** if output is the evidence. A screenshot or terminal dump of a root shell is stronger than a description of one.

### 36. Callout types — use sparingly and correctly

Use callouts when information cannot be placed inline without breaking the reader's path:

- **Warning**: data loss, irreversible action, risk of harm. Use at the start of any PoC that causes a crash, data loss, or service interruption.
- **Note**: supplemental information useful only in specific conditions. "This PoC was tested on firmware 9.14 only; behavior on earlier versions was not verified."
- **Tip**: optional efficiency improvement. Rare in disclosures.

Do not use three callouts in sequence. That is a wall of callouts, not a structured section.

### 37. Weasel words — remove from all technical writing

These words appear constantly and always weaken the finding:

| Word | Problem | Fix |
|---|---|---|
| `simply` / `easy` / `just` | Patronizing; if it is easy, the reader will find that out | Delete |
| `very` | Accentuates what you already said; adds nothing | Delete |
| `basically` / `actually` / `really` | Filler | Delete |
| `so` (sentence-opener) | Spoken filler, written habit | Delete or restructure |
| `in order to` | Wordy | Replace with `to` |
| `in many cases` | Wordy | Replace with `often` |
| `at the present time` | Wordy | Replace with `now` |
| `in some cases` | Wordy | Replace with `sometimes` |

Adverbs and adjectives in technical writing almost always add noise, not meaning. The noun and verb carry the meaning. Remove qualifiers unless they change the technical meaning.

### 38. Confidence markers — state what you confirmed

Writing without confidence is writing that conceals. Three causes of unconfident prose in disclosures:
1. Not knowing the finding well enough to state it plainly
2. Pressure to soften or hedge a confirmed vulnerability
3. Habit (passive voice feels safer)

Write what you confirmed. State what you did not test as a gap statement: "We did not confirm exploitability beyond a crash; the pattern is consistent with a use-after-free." Do not soften confirmed findings.

### 39. Page structure — visual hierarchy for multi-finding reports

- One document title (h1) per report
- Each finding is a section (h2): `## F1 — Stack Overflow in parse_option() (CWE-121, CVSSv3 9.8)`
- Sub-sections within a finding are h3: `### Technical Details`, `### Proof of Concept`, `### Remediation`
- Use **bullet lists** for capabilities, impacts, and affected versions — these are unordered sets
- Use **numbered lists** for reproduction steps — order matters
- Use **tables** for CVSS vectors, affected versions, and disclosure timelines
- Break paragraphs every 100–200 words; whitespace reduces cognitive load for dense technical content
- Do not bury key facts inside long paragraphs — if a finding title is the only thing the reader reads, it must still convey severity

### 40. Reference text — descriptive, not generic

Every cross-reference must describe what the reader gets from following it.

| Generic (avoid) | Descriptive (prefer) |
|---|---|
| See here | See reproduction steps in §3.2 |
| Click here for details | Full CVSS vector breakdown in §5 |
| See the CVE | CVE-2025-12345 (heap overflow in `parse_tlv`) |
| See above | See §2.1, "Affected Versions" |

This applies to references within the report, external CVE citations, and vendor advisory links.

---

## Part 7 — Additional Anti-Patterns

### 41. Showing off technical vocabulary

Do not use the disclosure to demonstrate expertise through complex prose, invented jargon, or unexplained acronyms. The reader's goal is to understand the finding. Dense or obscure writing signals insecurity, not competence.

If a term is not standard in the field, define it or replace it. If a sentence requires a reader to look something up, that sentence is too complex.

### 42. Inconsistent naming between sections

If the finding calls a function `parse_option()`, the PoC comment must call it `parse_option()`. If the CVSS description says "heap overflow," the executive summary must say "heap overflow" — not "memory corruption issue" or "buffer safety vulnerability."

Synonym substitution for prose variety has no place in technical disclosure. Every substitution makes the reader ask whether you mean the same thing.

### 43. Reproducing what the product does instead of what the vulnerability does

Do not open a finding with an explanation of how the product feature works. The PSIRT analyst knows their product. Open with what is wrong with it.

> ~~"The DHCP server processes incoming Option 82 packets. These packets contain a relay agent information field that the server parses..."~~

Start with: "The DHCP server's Option 82 parser lacks length validation, allowing heap overflow."

---

## Part 8 — Precision, Tone, and the 5 Cs

### 44. The 5 Cs: apply to every disclosure report

Technical writing must satisfy five qualities (from IEEE 830, adapted by Laplante):

| Quality | In disclosure reports |
|---|---|
| **Correct** | All versions, offsets, CVSS scores, CVE IDs, and function names are verified accurate |
| **Clear** | Each sentence has exactly one interpretation; no clause can be read two ways |
| **Complete** | A PSIRT analyst can reproduce the finding without asking for clarification |
| **Consistent** | One name per concept throughout the entire document |
| **Changeable** | Document is structured so updates (new version numbers, patch dates) can be made in one place |

Run the 5 Cs as a post-draft review: can you find any violation of each property?

### 45. Precise quantities — replace hedging words with numbers

Vague frequency and quantity words are imprecise. Replace them with measurements when you have them.

| Vague | Precise alternative |
|---|---|
| A few affected versions | Versions 9.0–9.13 (14 releases) |
| Many configurations are vulnerable | All configurations with port 8443 exposed to the network |
| The leak occasionally occurs | The leak occurs on every request with `opt_len > 256` |
| Some data is exposed | Credentials stored in `/etc/shadow` are fully readable |
| Frequently exploited | Exploited in all 47 test attempts |

When you cannot provide a precise number, say so explicitly: "We tested 3 of 12 affected firmware branches; the remaining 9 were not assessed."

Hedging words that must be replaced with a probability or a measurement, or removed:

- `likely`, `almost`, `probably`, `maybe`, `might be` — state the probability or remove
- `frequently`, `often`, `sometimes`, `rarely` — state the rate or range
- `some`, `many`, `most`, `a few` — state the count or percentage

### 46. "Very" + adjective is never the right choice

Replace every `very [adjective]` pair with a single stronger word. The word `very` signals that the adjective was insufficient — choose a better adjective.

| Avoid | Use instead |
|---|---|
| very large | enormous |
| very small | minimal / negligible |
| very clear | unambiguous |
| very fast | immediate |
| very old | legacy |
| very severe | critical |
| very simple | trivial |
| very complex | intricate |
| very dangerous | critical / lethal |

When a measured value is available, use it: not "very fast" — "executes in under 5 milliseconds."

### 47. Useless phrases — remove every instance

These phrases appear frequently and add zero information to any sentence:

- `as a matter of fact`
- `for what it is worth`
- `all in all`
- `that being said`
- `in fact` (unless "in fact" contradicts a prior claim)
- `that in itself`
- `I personally think that`
- `it should be noted that`
- `it is important to mention that`
- `needless to say`

If any of these appear before a claim, delete the phrase and keep the claim.

### 48. Anthropomorphic writing — systems cannot feel or fail "miserably"

Do not project human states onto systems, functions, or processes.

| Anthropomorphic (avoid) | Technical (prefer) |
|---|---|
| The function misbehaved | The function returned an incorrect value |
| The system was confused by the input | The parser did not handle the malformed input |
| The exploit was clever enough to bypass | The exploit bypassed |
| The vulnerability is hiding in the parser | The vulnerability is located in the parser |

Systems fail, crash, return incorrect values, or behave unexpectedly. They do not feel, think, decide, or intend.

### 49. Third-person for disclosure of research findings

Disclosure of research findings is written in the third person — not because it is a rule, but because it places the author as an impartial observer and removes personal stakes from the account.

| First-person (acceptable in informal context) | Third-person (preferred for disclosure) |
|---|---|
| We observed the overflow at offset 0x1a4 | The overflow occurs at offset 0x1a4 |
| We tested firmware 9.14 and confirmed exploitation | Firmware 9.14 was tested; exploitation was confirmed |
| We did not test versions after 9.6 | Versions after 9.6 were not assessed |

Exception: When clearly attributing scope limitations or researcher actions, first-person is clearer and more accountable: "We tested only the hosted version; the on-premises variant was not assessed."

### 50. Problem report elements — every finding must have all six

Technical reporting standards identify six required elements for any problem report. Map them to your finding:

| Problem report element | Finding equivalent |
|---|---|
| Name of the problem | Finding title: `F1 — Stack Overflow in parse_option()` |
| Product identification | Affected product, version, and build |
| Description with detail | Technical description, function name, offset, root cause |
| Date discovered | Discovery date (or disclosure date if different) |
| Conditions under which it occurred | Prerequisites, network position, authentication state |
| Expected vs. actual results | Expected: bounds check; Actual: unchecked `memcpy` |
| Severity rating | CVSS base score and vector |

A finding that omits any of these is incomplete and will require follow-up.

---

## Part 9: Report Planning and Precision Writing

*From: The Truth About the New Rules of Business Writing — Natalie Canavor, Claire Meirowitz, Pearson, 2008. Chapters 6, 20, 29.*

### 51. Plan before writing: state goal, audience, tone, and content explicitly

Before drafting any disclosure report or finding, articulate four things in writing:

1. **Goal** — what action do you want the recipient to take? (Patch, assign CVE, publish advisory, escalate to PSIRT?)
2. **Audience** — who reads this first, and who reads the executive summary only? (Engineer, PSIRT coordinator, executive?)
3. **Tone** — technical and objective; no enthusiasm, no alarm, no advocacy
4. **Content** — what does the reader need to decide whether to act?

This planning step determines what to include and, more importantly, what to exclude. Once the goal is clear, content that does not serve that goal is cut. The result is a shorter, more persuasive document.

**Contrast:**

| Without goal-first planning | With goal-first planning |
|---|---|
| Full timeline of researcher activity | Timeline condensed to: discovery date, vendor notification, vendor response |
| Complete technical background on the product | One sentence identifying the affected component |
| List of all tested firmware versions | The affected version range and the first unaffected version |

The more precisely the goal is defined, the less has to be written.

### 52. Executive summary: write it last, treat it as a call to action

The executive summary is written after the report is complete. It is not a table of contents or a shortened version of the report. It is a document that can stand alone if separated from the report.

Requirements:
- A title that states the finding, not just "Executive Summary"
- A lead that states what action the recipient should take and why
- A middle that explains what was found and what supports the recommendation
- Conclusions and the recommended next step

Length: no more than 10% of the report's total length.

**Contrast:**

| Passive summary (avoid) | Call-to-action summary (prefer) |
|---|---|
| "This report describes vulnerabilities found in Product X during research conducted in Q3." | "Product X contains two critical vulnerabilities that allow unauthenticated remote code execution. Immediate patching is required." |
| "The researcher identified several issues across multiple components." | "Three stack overflows in the XML parser permit complete device compromise from the LAN segment. CVE assignment and public advisory are recommended within 90 days." |

If the report has multiple audiences (engineering, legal, executive), write a separate executive summary for each, addressing the "what's in it for me" question specific to that audience.

### 53. Replace state-of-being chains with single active verbs

State-of-being constructions ("is a [noun] of", "was used as", "are capable of") dilute meaning and add words. Replace each with a single active verb.

| State-of-being (avoid) | Active verb (prefer) |
|---|---|
| The vulnerability is a bypass of the authentication check | The vulnerability bypasses the authentication check |
| The function is capable of reading arbitrary memory | The function reads arbitrary memory |
| The input is processed by the parser without validation | The parser processes input without validation |
| The exploit is a demonstration of the overflow | The exploit demonstrates the overflow |
| The handler was the cause of the crash | The handler caused the crash |

Finding the active verb requires identifying who or what acts and what the action is. If no single verb exists, the sentence may be describing two separate things — split it.

### 54. Technical terminology is not jargon

Specialized technical terms carry dictionary-precise meaning shared across a community of experts. Jargon is industry buzzword usage where no shared meaning exists.

The distinction matters for disclosure writing: use technical terms without apology; avoid jargon.

| Technical term (use it) | Why it is precise |
|---|---|
| Stack-based buffer overflow | Dictionary definition in CWE-121; exact meaning |
| Use-after-free | CWE-416; maps directly to the memory-safety class |
| CVSS base score 9.8 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H) | Defined scoring system; each field has one interpretation |
| Unauthenticated RCE | Compound of defined terms; unambiguous to any engineer |

| Jargon (avoid) | Problem |
|---|---|
| "Critical security concern" | No defined meaning; severity is unspecified |
| "Advanced persistent threat actor" | Overloaded; means different things to different readers |
| "Security posture" | Describes nothing measurable |
| "Enterprise-grade risk" | No unit; not actionable |

When the audience includes non-engineers (executives, legal), define technical terms on first use with a parenthetical: "a stack overflow (a condition where a program writes data beyond the boundary of its allocated stack region)."

---

## Part 10 — Graphical Elements and Visual Evidence

*From: Technical Writing, 2nd Edition — Phillip A. Laplante, CRC Press, 2018. Chapter 7.*

### 55. Every figure requires three elements — all mandatory

A figure without all three of these elements is incomplete:

1. **Caption with a unique number.** "Figure 3: Heap layout before and after the overflow at offset 0x1a4." The number is how the text refers to it.
2. **Text callout before the figure appears.** "Figure 3 shows the heap layout immediately before the overflow." The reader must be told to look before they see it.
3. **Follow-up discussion after the figure.** The figure does not speak for itself. Explain what the reader should notice and why it matters.

Dropping any one of these forces the reader to guess your intent.

### 56. Tables follow the same caption and callout conventions as figures

Tables are numbered separately from figures (Table 1, Table 2) but follow identical rules: a descriptive caption, a callout in the preceding text, and a discussion after the table that interprets the data. Keep tables flat: avoid nested column headers. Every column must have a header. Every row must be complete — no merged cells spanning rows.

### 57. Number only elements you will reference by number

Assign a number (Figure N, Table N, Equation N) only to elements that will be cited by that number somewhere in the document body. An element that appears once with no cross-reference can remain unnumbered. Do not number elements sequentially by habit — number them because they will be referenced.

---

## Part 11 — Disclosure Emails as Permanent Records

*From: Technical Writing, 2nd Edition — Phillip A. Laplante, CRC Press, 2018. Chapter 9.*

### 58. A disclosure submission email is a legal record

Every email sent to security@vendor.com, a CVE numbering authority, or a coordinator enters a chain of custody. Courts, coordinating bodies, and legal teams retain these messages as evidence in dispute resolution and timeline disputes. Write every sentence as if it will be read by a judge. Imprecise claims, informal language, and hedged statements become liabilities. Apply the same precision standards as the report itself.

### 59. Subject lines must be searchable

A PSIRT inbox receives hundreds of submissions. A vague subject line buries your report.

| Avoid | Use instead |
|---|---|
| Vulnerability Report | Unauthenticated RCE in [Product] v9.x (CVSSv3 9.8) — Coordinated Disclosure |
| Security Issue | Stack Overflow in DHCP Parser — [Vendor] [Product] — CVE Request |
| Bug in Product | Memory Corruption in parse_option() — [Product] 9.0-9.13 |

Every subject line must include: vendor/product name, vulnerability class, version range, CVE if assigned, and severity signal.

### 60. Email body fits on one screen; end with a deadline

The disclosure email body is a cover letter. It is not the report. The body contains: one sentence stating the finding, one sentence on severity and impact, one sentence identifying the attachment, and one sentence that is a specific call to action with a calendar deadline.

> "We have identified an unauthenticated stack overflow in [Product] v9.0-9.13 (CVSSv3 9.8, CWE-121). The attached disclosure report includes full technical detail, proof-of-concept code, and CVSS vector breakdown. Please confirm receipt and provide a case number by [date + 7 days]."

If the email body requires scrolling, move the excess to the report attachment.

---

## Part 12 — Collaboration and Voice Consistency

*From: Technical Writing, 2nd Edition — Phillip A. Laplante, CRC Press, 2018. Chapter 10.*

### 61. Multi-author reports must achieve one voice

A disclosure report written by two or more researchers will betray its origins in sentence rhythm, vocabulary density, and technical register — unless someone enforces uniformity. The diagnostic tool: run Flesch-Kincaid Grade Level on each section. Any section that differs from the document-wide baseline by more than 20% was written by a different author and needs harmonization. Consistent vocabulary, sentence length distribution, and technical depth are the targets. Stylistic preference is not.

### 62. One author holds final editing authority

Democratic editing produces documents where every author's preferences survive, creating inconsistency at scale. Designate one author as the final authority before drafting begins. That author's job is not to impose personal preference but to enforce the document's established conventions: term consistency, voice, rhythm, and the rules in this guide. Every other author defers after the final pass.

---

## Part 13 — Sentence Rhythm and the Breath Principle

*From: Style Guide for Business Writing — Michael C. Thomsett, De Gruyter, 2017. Sections R (Rhythm) and S (Sentences). Extended by the user's observation on AI writing cadence.*

### 63. Vary sentence length within every paragraph

Human writing originates in physiology. Sentences are shaped by breath, pause, and emphasis — the natural rhythms of speech translated to the page. AI-generated prose lacks this origin and produces uniformly similar sentence lengths, creating a flat, synthetic cadence that trained readers notice immediately.

Fix it deliberately: mix three sentence lengths within each paragraph.

- **Short sentences (under 10 words)** deliver impact. They stop the reader.
- **Medium sentences (10-20 words)** carry the main technical content, structured for clarity.
- **Longer sentences (20-plus words)** build context, add qualification, and connect related ideas with subordinate clauses that would fragment if broken apart.

A paragraph of uniformly short sentences reads as terse or evasive. A paragraph of uniformly long sentences is exhausting. Variety creates the rhythm that makes technical prose readable.

### 64. Read every paragraph aloud before finalizing

The aloud test catches uniform cadence that silent reading misses. If you read a paragraph straight through without natural pause or variation in pitch, the paragraph has mechanical rhythm. Rewrite it. If a sentence makes you run out of breath before the period, it is too long. If three consecutive sentences end at the same syllabic beat, they are the same length — break the pattern.

This is the single fastest diagnostic for AI-sounding prose. Apply it to every paragraph, not just the ones that feel uncertain.

### 65. Use "must" for requirements; "should" for recommendations only

| Word | Meaning in disclosure writing |
|---|---|
| **must** | Required; no valid alternative exists |
| **should** | Recommended; the reader may have reasons to deviate |
| **may** | Permitted but not required |
| **shall** | Ambiguous — avoid entirely |

Every remediation step, reproduction prerequisite, and submission requirement that is not optional gets "must." Using "should" for a mandatory remediation allows the vendor to defer it as optional. This applies equally to requirements you place on yourself: "We must confirm on a clean build" is clearer than "We should confirm."

### 66. Remove hedging qualifiers from confirmed findings

These words signal uncertainty. They are appropriate when uncertainty exists. They are not appropriate in front of confirmed findings.

Hedging qualifiers to remove from confirmed technical claims: *apparently, in general, seems to indicate, in many instances, ordinarily, as a rule, commonly, usually, normally, generally.*

| Hedged (avoid) | Direct (prefer) |
|---|---|
| The vulnerability apparently allows remote code execution | The vulnerability allows remote code execution |
| In general, the parser fails to validate length | The parser does not validate length |
| This seems to indicate a use-after-free condition | This is a use-after-free condition (CWE-416) |
| The function ordinarily handles this correctly | The function does not handle this input |

When genuine uncertainty exists, state the specific boundary: "We confirmed exploitation on firmware 9.0-9.13. Behavior on 9.14 was not tested." Do not replace stated uncertainty with hedging qualifiers that make confirmed findings sound tentative.

---

## Part 14 — Plain Language Standards

*From: Plain Language in Government Writing: A Step-by-Step Guide — Judith Myers, Berrett-Koehler, 2020. Chapters 4-5.*

### 67. Target Fog Index 10-11 for PSIRT-facing documents

The Gunning Fog Index measures reading difficulty. For coordinated disclosure to a professional audience, target a Fog Index of 10-11.

**Formula:** (average words per sentence + count of words with 3 or more syllables per 100 words) × 0.4 = Fog Index

A Fog Index of 10-11 corresponds to a college-educated reader reading at a professional level. A score above 15 indicates prose that is difficult for most readers regardless of expertise.

Practical target: average sentence length of 15-18 words. Sentences averaging over 25 words push the index into the 15-plus zone. Prune long sentences or split them.

### 68. Loosen noun sandwiches with prepositions

A noun sandwich is a chain of three or more nouns used as consecutive modifiers. Readers must parse the chain to find which noun modifies which — a slow and error-prone process for technical content.

| Noun sandwich (avoid) | Loosened with prepositions (prefer) |
|---|---|
| firmware vulnerability exploitation path | path for exploiting a firmware vulnerability |
| embedded system memory allocation error | error in memory allocation on embedded systems |
| underground mine worker safety procedures development | development of safety procedures for workers in underground mines |
| authentication bypass mitigation strategy | strategy for mitigating authentication bypass |
| stack overflow detection tool configuration | configuration of the tool for detecting stack overflows |

When you see three or more nouns in a row, insert prepositions to show the relationships. The sentence will be longer but significantly clearer.

### 69. Default to present tense

Present tense is immediate, active, and shorter than compound past or future constructions. Use it as the default for technical description, vulnerability behavior, and impact statements.

| Compound tense (avoid) | Present tense (prefer) |
|---|---|
| The function was found to be allocating memory without bounds checking | The function allocates memory without bounds checking |
| The parser has been shown to be vulnerable to | The parser is vulnerable to |
| Exploitation was able to be demonstrated at offset 0x1a4 | Exploitation occurs at offset 0x1a4 |

Reserve past tense for historical facts: discovery date, test conditions, what the researcher observed. Reserve future tense for remediation timelines only: "Patch availability is expected by [date]."

---

## Part 15 — Document Planning: The PRC Framework

*From: A Practical Guide to Business Writing — Khaled Al Maskari, Wiley, 2012. Chapter 1.*

### 70. Define Purpose, Reader, and Content before drafting any document

Before writing a single sentence, answer three questions in writing:

1. **Purpose** — What action do you want the reader to take? (Patch the system. Assign a CVE. Escalate to executive leadership. Coordinate a public advisory.) The purpose determines what to include and what to cut. If content does not serve the purpose, remove it.

2. **Reader** — Who reads this, and what do they already know? A PSIRT engineer reads for technical precision; an executive reads for business impact; legal reads for liability exposure. Define the primary reader and the secondary reader separately. Write for the primary reader; do not dilute the document trying to serve both equally.

3. **Content** — Given the purpose and the reader, what information do they need to act? Not everything you found, not everything you know, not everything that might be relevant. Only what they need to decide and act.

This framework eliminates the most common failure mode in disclosure writing: documents that include everything the researcher knows rather than everything the reader needs.

---

## Quick Reference Checklist

Before submitting a disclosure report, verify each item:

- [ ] Title names the vulnerability type and location, not how it feels
- [ ] Executive summary clusters findings by severity in one sentence
- [ ] Each finding opens with the bug and capability — not background
- [ ] Every finding states exactly what an attacker can do (no "may impact")
- [ ] Every verb is precise — no "affect," "impact," "support" without a specific meaning
- [ ] Every modifier is placed beside the word it modifies
- [ ] Parallel lists use parallel grammatical structures
- [ ] Terms are consistent throughout (no synonym substitution for variety)
- [ ] Abbreviations are defined on first use
- [ ] CVSS vectors are present and translated into plain English
- [ ] Timeline uses specific dates, not relative language
- [ ] Passive voice is used deliberately, not by default
- [ ] No smothered verbs (perform/make/give + noun → verb)
- [ ] No negation chains ("not unlikely" → "likely")
- [ ] No hedge-stacking ("could potentially allow" → confirmed claim or stated uncertainty)
- [ ] No weasel words: simple, easy, just, very, basically, actually
- [ ] Every PoC tested and working; placeholder strings are descriptive
- [ ] Reproduction steps are numbered and procedural (not narrative)
- [ ] Key facts appear in the first sentence of each section (F-pattern)
- [ ] Four editing passes completed: accuracy, completeness, structure, clarity
- [ ] 5 Cs satisfied: correct, clear, complete, consistent, changeable
- [ ] No anthropomorphic language (systems don't feel, think, or misbehave)
- [ ] No "very [adjective]" — replaced with single precise word or measurement
- [ ] No useless phrases (that being said / as a matter of fact / needless to say / etc.)
- [ ] Quantities are precise: counts, versions, rates — not "some" or "many"
- [ ] All findings include: title, product/version, description, date, conditions, expected vs. actual, severity
- [ ] Executive summary written last, states the required action in the lead sentence
- [ ] Goal/audience/tone/content defined before drafting; content not serving the goal is removed
- [ ] No state-of-being chains ("is a bypass of" → "bypasses")
- [ ] Technical terms used precisely; jargon avoided or defined for non-technical audiences
- [ ] Every figure has caption, text callout before it appears, and follow-up discussion after
- [ ] Tables use flat structure; no nested headers; all cells populated
- [ ] Numbers assigned only to figures/tables/equations referenced by number in the text
- [ ] Disclosure submission email subject line includes: product, vulnerability class, version, CVE if assigned, severity
- [ ] Email body fits one screen; ends with a specific call to action and calendar deadline
- [ ] Multi-author report: Flesch-Kincaid Grade Level checked across sections; no section diverges by more than 20% from baseline
- [ ] One author designated as final editing authority
- [ ] Every paragraph contains a mix of short, medium, and long sentences
- [ ] Every paragraph read aloud; no uniform cadence or mechanical rhythm
- [ ] Every mandatory action uses "must"; "should" used only for optional recommendations
- [ ] No hedging qualifiers before confirmed technical claims (apparently, in general, seems to indicate, ordinarily, etc.)
- [ ] Fog Index checked; target 10-11; average sentence length 15-18 words
- [ ] No noun sandwiches of three or more consecutive nouns; prepositions inserted to show relationships
- [ ] Present tense used for technical description and vulnerability behavior; past tense only for historical facts
- [ ] Purpose, Reader, and Content defined before drafting; content not serving the purpose removed

---

## Source

Synthesized from:

- *Plain Style: Techniques for Simple, Concise, Emphatic Business Writing* — Richard Lauchman, AMACOM, 2008. Chapters 1–5.
  - Ch. 1: The Problem With Style (10 precepts of business writing)
  - Ch. 2: Practical Thinking (11 assumptions fostering plain writing)
  - Ch. 3: On Being Concise (verb-based writing, smothered verbs, redundancy, noun strings)
  - Ch. 4: On Being Emphatic (SVO order, modifiers, parallel structure, punctuation)
  - Ch. 5: On Choosing Words (precision, connotation, jargon, word problems)

- *Docs for Developers: An Engineer's Field Guide to Technical Writing* — Jared Bhatti, Zachary Sarah Corleissen, Jen Lambourne, David Nunez, Heidi Waterhouse, Apress, 2021. Chapters 1–5.
  - Ch. 1: Understanding your audience (curse of knowledge, friction log, user research)
  - Ch. 2: Planning documentation (content types, documentation plan)
  - Ch. 3: Drafting documentation (outlines, skimming patterns, one goal per document)
  - Ch. 4: Editing documentation (four editing passes, callout types, plussing technique)
  - Ch. 5: Integrating code samples (explain-concise-clear-usable-trustworthy principles)

- *Technical Writing for Software Developers* — Chris Chinchilla, Packt Publishing, 2024. Chapters 1–4.
  - Ch. 1: The Why, Who, and How of Tech Writing (audience analysis, three Ws, documentation ecosystem)
  - Ch. 2: Understanding Different Types of Documentation (QuickStart, tutorials, reference, API docs)
  - Ch. 3: Language and the Fundamental Mechanics of Explaining (active vs. passive, weasel words, consistency, confidence)
  - Ch. 4: Page Structure and How It Aids Reading (semantic markup, whitespace, lists, admonitions, navigation)

- *Technical Writing, 2nd Edition* — Phillip A. Laplante, CRC Press, 2018. Chapters 1, 2, 3, 6.
  - Ch. 1: The Nature of Technical Writing (precision, no emotional response, taxonomy: technical reporting)
  - Ch. 2: Technical Writing Basics (5 Cs, conciseness, precision/hedging, universal quantification, negatives, clichés, anthropomorphic writing, "very", useless phrases)
  - Ch. 3: The Writing Process (brainstorm/draft/revise/edit/publish; third-person for research findings; word replacement in copyediting)
  - Ch. 6: Technical Reporting (procedures structure, problem report elements, executive summary)

- *The Truth About the New Rules of Business Writing* — Natalie Canavor, Claire Meirowitz, Pearson, 2008. Chapters 6, 20, 29, 51.
  - Ch. 6: Cut to the chase: Put the bottom line on top (goal/audience/tone/content planning framework)
  - Ch. 20: Passive thinking and jargon undermine clarity (divine passive, state-of-being verbs, jargon vs. specialized knowledge)
  - Ch. 29: Good reports generate action (executive summary as call to action, planning framework, audience-specific summaries)
  - Ch. 51: Clarity is next to godliness (punctuation mechanics for precision)

- *A Practical Guide to Business Writing: Writing Well in English for Native and Non-Native Speakers* — Khaled Al Maskari, Wiley, 2012. Chapters 1, 3, 4.
  - Ch. 1: The PRC framework (Purpose, Reader, Content) as a pre-drafting discipline
  - Ch. 3: Email writing principles; email as a permanent record
  - Ch. 4: Common writing errors; positive language; impersonal constructions for opinions

- *Style Guide for Business Writing* — Michael C. Thomsett, De Gruyter, 2017. Sections R and S.
  - Section R: Redundancy, Rhythm, Reports, Run-on sentences (sentence rhythm variation; the read-aloud test)
  - Section S: Sentences, Style and tone, Similar words (sentence length discipline; flat cadence as a diagnostic signal)

- *Plain Language in Government Writing: A Step-by-Step Guide* — Judith Myers, Berrett-Koehler, 2020. Chapters 4-5.
  - Ch. 4: Voice and tone; active vs. passive voice; "must" vs. "shall" vs. "should"; removing hedging qualifiers
  - Ch. 5: Clarity and conciseness; Fog Index; noun sandwiches; present tense as the default

- *Technical Writing for Developers* — Jim Hall, Apress, 2024. Introduction and Chapter 1.
  - Introduction: The role of technical writing in software and systems documentation
  - Ch. 1: Audience analysis and toolchain selection for developer-facing documentation

Applied to coordinated vulnerability disclosure writing for PSIRT submissions, CVE documentation, and published security advisories.
