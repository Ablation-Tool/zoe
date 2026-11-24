# Worked Example: A Population Survey That Breaks the Thesis

**Lane taught:** population-survey method · auth-on-default falsification (the interesting negative)

**Platform class:** an open-source conversational AI framework that ships an unauthenticated REST webhook channel by default. Generic stand-in for any chatbot platform where authentication is opt-in rather than opt-out.

This example walks the full population-survey pipeline against one platform class and shows the survey doing the one thing a survey is built to do: testing the thesis and breaking it. The thesis says open-source AI infrastructure trends toward authentication-on-by-default. This platform inverts that. It ships open and asks the operator to close it. That makes it the most valuable kind of result the program can return, a genuine counterexample, not a clean confirmation.

All hosts below are illustrative. Real target identifiers have been removed. IPs are RFC5737 documentation addresses. The teaching content is the method, the dorks-as-technique, the read-only probe, and the two population rates.

---

## 1. What the survey is testing

The framework documents its own default plainly: no token, no cookie, no key on the chat webhook unless the operator adds one. The platform ships permissive by deliberate design choice, not by a neglected default. That is the exact shape of the inverted platform described in the thesis.

So the survey has a real prediction on the table before the first probe:

- If the auth-on-default thesis held for this class, we would expect a meaningful share of instances to be auth-gated, and the share to rise across newer versions.
- If the platform truly inverts the default, we expect the auth-gated share to be near zero across all versions, and the open share to track only the difference between production and development deployments.

The survey is built to tell those two worlds apart. The number it produces either confirms the thesis or breaks it. The finding and the test are the same act.

---

## 2. Corpus construction (Discover)

Three vendor-unique dorks select the population. The point of a dork here is not volume. It is a marker no unrelated server emits, so the corpus is the platform and not a pile of false positives.

| Dork (technique) | What it keys on |
|---|---|
| `port:5005 http.html:"<vendor-banner>"` | default service port plus the vendor banner string in the HTTP body |
| `http.html:"/webhooks/rest/webhook"` | the platform's unique webhook path appearing in any served HTML |
| `http.title:"<vendor>"` | the vendor name in the page title |

Each dork keys on something only this platform produces. The webhook path in particular is a strong marker: no other framework serves that exact route. Run all three, union the results, dedup on IP. That union is the corpus.

Two discipline notes that carry across every survey:

- **Quote raw hits and marker-confirmed hits separately.** A dork's raw page count is a candidate count, not a finding count. The corpus size after dedup is the only number that feeds the next stage.
- **A zero-result dork is a logged result.** If a dork returns nothing, that is data about the population's banner surface, not a dead end. Record it and move on.

The deduped corpus for this worked example: call it **N hosts**. Every rate below is computed against that N.

---

## 3. Identity marker (Fingerprint)

The platform identity is a three-conjunct marker. One signal alone false-positives. All three together are zero-false-positive.

```
1. service reachable on the default port (or behind a reverse proxy on 80/443)
2. GET /            -> body contains the vendor version banner ("Hello from <vendor>: X.Y.Z")
3. POST /webhooks/rest/webhook -> 200, body is a JSON array carrying a recipient_id key
```

The version banner is the primary fingerprint. No standard HTTP server, framework, or middleware emits that string, and it carries the exact version, which scopes any later CVE work for free.

The webhook response schema is the secondary marker. The response echoes the caller-supplied sender value back in a `recipient_id` field. That echo shape is unique to this platform.

This is the conjunctive-marker discipline: require all three before you call a host the platform. A single-signal fingerprint is how a survey ends up confident, reproducible, and wrong.

---

## 4. The read-only probe (Verify)

Verification is the load-bearing stage. The dorks produced candidates. This probe produces findings, and nothing short of it earns a finding label.

The probe is a single read-only POST to the webhook with a throwaway message:

```
POST /webhooks/rest/webhook
{"sender":"probe","message":"hello"}
```

Outcome mapping:

- **200 plus a JSON array carrying `recipient_id`** -> confirmed platform, no auth required. This is the 200-with-data read. It is a finding.
- **401 or 403** -> an auth-configured instance. Surface present, access not exercised. Logged as auth-gated, not as a finding.
- **404 or a non-matching body** -> a false positive from the dork. Dropped from the corpus.

Two read-only secondary probes confirm and enrich without ever leaving read territory:

- `GET /` confirms the version banner.
- `GET /status` returns a model-file name and a training-job counter. The model-file name can disclose internal deployment naming conventions. No auth required to read it.

The restraint line is firm. The probe sends one benign greeting and reads the structured response. It does not submit real data, does not drive a conversation, does not collect. The schema and the banner are the evidence. The names are the finding.

---

## 5. The two population rates (the result)

This is the heart of the example. A population survey produces an outer pair of rates, both computed against the same N.

```
Open rate        = confirmed-open / N
Auth-gated rate  = auth-gated     / N
```

For this worked example the rates came back in the neighborhood of:

```
Open rate        ~ 50%   (half the corpus answered the read-only probe with data)
Auth-gated rate  ~ 0%    (essentially no host in the corpus returned 401/403)
```

Read both rates together. They are not redundant, they answer different questions.

- The **open rate near 50%** is the production-versus-development split. Half the instances are live bots taking traffic. Half are dev or stale deployments that did not answer with data. That spread is expected for any framework with a low barrier to standing up a test instance.
- The **auth-gated rate near 0%** is the thesis test, and it is the load-bearing number. If this platform obeyed auth-on-default, this rate would be non-trivial and would climb with version. It does not. Across every version present in the corpus, almost nothing is gated.

A near-zero auth-gated rate across an entire platform population is not noise. At population scale it is a structural statement about the platform's default. It says the burden is on the operator to opt in to authentication, and most operators do not.

---

## 6. Why this breaks the thesis (and why that is the point)

The thesis predicts a rightward drift toward auth-on-by-default under disclosure pressure. This platform is the named counterexample the program hunts for: same open-source lineage as the permissive cohort, but permissive by deliberate design, auth opt-in, with the near-zero auth-gated rate holding flat across versions instead of climbing.

That does not embarrass the program. It is the single most valuable result a survey can return. A clean confirmation tells you the cohort moved the way you expected. A genuine inversion tells you the cohort framing is incomplete, which is the only finding that can actually change the framing. The thesis is falsifiable, and here is a survey that falsifies it for one class. That is the whole reason the thesis is written as a hypothesis and not a slogan.

Filed as a candidate insight:

> This platform class inverts the auth-on-default pattern. It ships no-auth and requires opt-in. The population auth-gated rate is near zero and does not rise across versions. The auth-on-default thesis does not hold for open-source chatbot frameworks that default to zero authentication.

That insight is the codify step. One survey is an anecdote. This number means something only next to the other platform rates in the corpus, where it sits as the outlier that pins down the edge of the thesis.

---

## 7. What the open hosts exposed (severity, kept generic)

The point of the severity work is to show what a near-zero auth-gated rate costs in practice, without naming a single operator. The corpus carried, across its open hosts, every one of the following classes. Each is described as a class, not a host.

- **Unauthenticated message injection into live bots.** Any caller can inject arbitrary messages into an active conversation and read the bot's responses, including operator-specific branding, personas, and service logic. Severity: high, because it is population-level unauthenticated access to production endpoints.
- **Backend error propagation.** Some hosts returned a raw backend error string (a failed environment-variable or database lookup) on every probe. The exception text reaches an unauthenticated caller and leaks internal dependency and function naming. Severity: medium.
- **Sensitive-flow bots reachable unauthenticated.** Some bots front sensitive intake flows (for example a document or media validation flow that advertises its own waiting state). An unauthenticated caller can enumerate accepted formats and probe the validation logic. Severity: high.
- **LLM system-prompt disclosure.** At least one host returned its raw LLM system prompt, template key and all, inside the webhook response text field. The action layer passed the prompt prefix straight to the response channel without sanitization. Any unauthenticated caller reads the system prompt, which is a direct prompt-injection attack surface. Severity: high.

None of these required a credential. None required more than the same read-only probe from Section 4. That is the cost of inverting the default at population scale.

---

## 8. Negative space (what the survey could not close)

Honest surveys log their own gaps. For this example:

- **Population coverage is a lower bound.** The corpus came from three dorks at a fixed page depth. Full pagination on the primary port dork would likely return more. The population estimate is a floor, not a ceiling.
- **One disclosure-class host went unresponsive after first contact.** The system-prompt finding was confirmed on the first response. The host then stopped answering, possibly rate-limited. The finding stands on the one verified read; nothing was inferred past it.
- **Several passive-enrichment tools returned zero nodes** for hosts with no upstream scan record to seed from. A zero from a passive engine is a logged gap, not a finding and not a contradiction.

---

## 9. Tool gaps this survey surfaced

A survey that runs the full chain also tests the chain. Two gaps generalize past this platform:

- **The fingerprint registry had no entry for this platform class.** The active fingerprinter ran against every confirmed-open host and detected zero AI services, because it never probed `GET /` for the version banner or the webhook route for the response schema. The fix is the three-conjunct marker from Section 3, added as a registry entry. Until then the scanner is structurally blind to the entire class.
- **A downstream classifier mislabeled every webhook-unauth finding** as a different, unrelated unauthenticated-service class, because its template hardcoded one platform's name for any finding ingested with `authenticated:false`. The structural fix is a `finding_class` field on the node schema, read by the message template, plus a dedicated rule for the `webhook_unauth` class. A classifier that cannot name the class it found will name it wrong at population scale.

Both gaps are the kind a survey is supposed to find. The scanner missing a class is a tool-humility result: you learn why the scanner was silent and you fix the root, you do not paper over it.

---

## 10. The method, in one breath

```
Discover   three vendor-unique dorks -> union -> dedup -> corpus of N
Fingerprint  three-conjunct marker (port + version banner + webhook schema)
Verify     one read-only POST per host -> 200-with-data = finding; 401/403 = auth-gated; other = drop
Score      two rates against N: open ~ prod/dev split; auth-gated = thesis test
Codify     near-zero auth-gated rate breaks auth-on-default for this class -> numbered insight
```

The survey produced two numbers. The open rate told us how many bots were live. The auth-gated rate told us the thesis does not hold here. The second number is why the survey was worth running, and the reason it gets published instead of filed. A null result is a logged result. An inverted platform is the result you hope for.

---

*Prepared by NuClide Research. Contact: nuclide-research.com. This is a genericized teaching example; all operator and host identifiers have been removed and all IPs are RFC5737 documentation addresses.*
