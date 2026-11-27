# Vulnerability Disclosure Submission Guide

Field-tested rules for writing reports that PSIRT teams can act on. Low-quality
submissions get deprioritized or rejected outright -- these rules prevent that.

---

## 1. Validate before sending

**Never send implied findings.**

A finding exists when you can demonstrate it. If your analysis shows a pattern that
*could* be vulnerable but you have not confirmed it with a working PoC or verified
static trace, it is a candidate -- not a finding. Send candidates only if you
explicitly label them as unverified and explain what additional access would be
needed to confirm.

Checklist before submitting each finding:

- [ ] Reproduced on a clean build of the stated affected version
- [ ] CVSS score calculated and justified (use CVSS 3.1 or 4.0)
- [ ] Affected version range is as specific as possible (not "all versions")
- [ ] You have ruled out the simple mitigations (default-off, auth-required, non-default config)
- [ ] Disclosure timeline clearly stated in the cover email

---

## 2. Chains are not vulnerabilities (to PSIRT)

**Cisco PSIRT explicitly refuses to assign CVEs to chained vulnerabilities.**
CISA ICS-CERT and most other enterprise PSIRTs follow the same policy.

A chain is a sequence of bugs that together produce high impact. Each bug in the
chain must stand on its own:

- If Step 1 is exploitable alone, it gets its own finding + CVE.
- If Step 1 is only exploitable in combination with Step 2, neither step will be
  acknowledged as a vulnerability unless each independently meets the exploitability
  bar.

**What to do instead:**

- Decompose the chain. Submit each component as a standalone finding.
- In the body of each finding, include a *Chain Context* section that explains how
  the finding compounds with others -- but make the primary finding self-contained.
- Do not title a finding "Authentication Bypass + RCE Chain". Title it
  "Authentication Bypass in [Component]" and separately "Remote Code Execution in
  [Component]", each with independent PoC.

---

## 3. Write reproducible steps for an engineering team

PSIRT reviewers are not security researchers. They forward your report to an
engineering team that must reproduce the finding on the exact version you specified.
If they cannot reproduce it, the case closes.

**Reproduction step requirements:**

1. **Environment setup**: exact version string, OS, config flags, default vs. custom.
2. **Pre-conditions**: required access level (unauthenticated / user / admin), network
   position (LAN / WAN / VPN).
3. **Steps**: numbered. One action per step. No skipped steps.
4. **Expected vs. observed**: what the output should be vs. what it actually is.
5. **Verification**: how to confirm success (error message, return value, observable
   side effect).

Bad example:
> Send a malformed packet to port 443. The device crashes.

Good example:
```
Environment: FortiWeb 7.4.2, default config, HTTPS management enabled on port 443.
Pre-condition: Network-adjacent, unauthenticated.

Steps:
1. Install the tool: pip install requests
2. Run: python3 poc.py --target <ip> --port 443
3. Observe the response: HTTP 500 with traceback in body.
4. Verify: Check /var/log/crashlog -- a core dump entry dated within 5 seconds of
   the request confirms the crash.

Expected: HTTP 400 or 403.
Observed: HTTP 500 with Python traceback including memory address.
```

---

## 4. PoC requirements

- **Self-contained script**: one file, no external dependencies that require a login.
  Dependencies from PyPI/npm are fine if they are public.
- **Benign proof only**: demonstrate the vulnerability condition without destructive
  payload. For RCE: show command output (`id`, `whoami`, `echo`) -- not a reverse
  shell or data exfil.
- **Comment the critical lines**: annotate the line(s) that trigger the vulnerability.
  The engineering team needs to know *where* to look in their source.
- **Test the PoC fresh before sending**: run it on the stated version, capture the
  actual output, and include that output verbatim in the report.

---

## 5. YARA rules

Include a YARA rule for every binary finding. Vendor SOC teams run detection before
their engineering team begins reproduction -- a working YARA rule accelerates triage
from weeks to days.

Minimum YARA rule requirements:

```yara
rule Vendor_Product_FindingID : finding
{
    meta:
        description = "Detects vulnerable [component] in [Product] <= [version]"
        author      = "[Researcher]"
        date        = "[YYYY-MM-DD]"
        cvss        = "[score]"
        reference   = "Coordinated disclosure -- pre-publication"

    strings:
        // Anchor the match: byte sequence at the vulnerable function entry point
        $vuln_fn = { 55 48 89 E5 48 83 EC ?? 48 89 BD ?? ?? FF FF }

        // Version string to scope the match to affected versions
        $ver = "v7.4.2" ascii

    condition:
        $ver and $vuln_fn
}
```

Use conjunctive matchers (`$ver AND $vuln_fn`) to avoid false positives. The version
anchor is critical -- a rule that hits every binary is noise.

For source-level findings add a strings-based rule instead of byte patterns:

```yara
    strings:
        $dangerous_call = "strcpy(" ascii
        $scope_fn       = "parse_user_input" ascii
    condition:
        $scope_fn and $dangerous_call
```

---

## 6. CVSS scoring

Use CVSS 3.1. Include the full vector string.

Quick reference for common findings:

| Finding type | Typical vector |
|---|---|
| Unauthenticated RCE (network) | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H = 9.8 CRITICAL |
| Auth bypass (network) | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N = 9.1 CRITICAL |
| Unauth info disclosure (network) | AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N = 7.5 HIGH |
| Local privilege escalation | AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H = 7.8 HIGH |
| Stack buffer overflow (local) | AV:L/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:H = 7.0 HIGH |

Use the [CVSS 3.1 calculator](https://www.first.org/cvss/calculator/3.1) and include
the URL in your report so the vendor can verify your score.

---

## 7. Sections every finding must include

Structure each finding identically. PSIRT teams process hundreds of reports -- a
predictable structure means faster triage.

```
### [F001] [Finding Title]

**CVSS 3.1:** [score] [SEVERITY] | [vector string]
**CWE:** CWE-[number]: [name]
**Affected:** [Vendor] [Product] [version range]
**Attack type:** [Network / Local / Physical] | [Pre-auth / Post-auth]

#### Overview
[2-3 sentences: what the vulnerability is, where it lives, what an attacker can do.]

#### Technical Evidence
[Static analysis trace, binary offsets, or source line references.
For binary: function name, offset within binary, relevant instruction sequence.]

#### Proof of Concept
[Paste PoC code or commands. Include actual output from your test run.]

#### Reproduction Steps
[Numbered steps as described in section 3 above.]

#### YARA Rule
[Paste rule as described in section 5 above.]

#### Remediation
[Specific fix: sanitize at line X, add bounds check, enforce auth before Y, etc.]
```

---

## 8. What NOT to send

- **Theoretical findings**: "this pattern might allow..." -- confirm it first.
- **CVE duplicates**: search the vendor's advisory page and NVD before submitting.
- **Findings against EOL versions only**: vendors will not patch. Note EOL status and
  submit anyway if the installed base is significant.
- **Shodan/Censys exposure reports**: "your product is exposed on the internet" is
  not a vulnerability -- it's a deployment observation. Vendors will close it immediately.
- **Configuration hardening suggestions**: not a vulnerability. Separate doc.
- **Chains labeled as a single finding**: see section 2.

---

## 9. Cover email template

```
Subject: [VENDOR PRODUCT] - Coordinated Vulnerability Disclosure

To: [PSIRT email or form]

I am reporting [N] security vulnerabilities in [Vendor] [Product] versions [range].
All findings were identified through [static analysis / binary reverse engineering /
source code review]. No live production systems were accessed.

Disclosure timeline: I intend to publish findings on [DATE], approximately [N] days
from this report. Please confirm receipt within 7 days.

Attachments:
- disclosure-report.pdf (findings, PoC, YARA rules, reproduction steps)

I am available at [contact] for coordination.

[Researcher name]
[Affiliation]
```

Keep the cover email short. The detail is in the PDF.

---

## 10. After sending

| Day | Action |
|---|---|
| 0 | Send report. Start disclosure clock. |
| 7 | If no acknowledgment: send one follow-up to same address. |
| 14 | If still no response: escalate to CISA VINCE-NT or CERT/CC as coordinator. |
| 45–90 | Default disclosure window. Agree on extension only if vendor has a credible patch ETA. |
| Patch day | Coordinate publish date. Do not publish until vendor advisory is live (unless window expired). |

Extend the window by 30 days maximum for a documented, credible patch in progress.
Never extend indefinitely. A vendor advisory without a patch is acceptable for public
disclosure if the window has expired.
