# Conversational Trajectory Manipulation (CTM) Companion Paper

> Preserved from Google Drive draft (`CTM_Companion_Paper.docx`).

---

Conversational trajectory manipulation

Social engineering of large language models through

error-correction hijacking and context-channel confusion

ExileKingdom & Nuclide

Independent Security Research

2026-03-22

Abstract

We document a class of adversarial interaction with large language models (LLMs) that operates not through prompt injection in the traditional sense — malicious instructions embedded in input — but through social engineering of the model's conversational reasoning over multiple turns. We term this class Conversational Trajectory Manipulation (CTM).

CTM exploits three properties of instruction-tuned LLMs: (1) the error-correction instinct — the model's strong prior that user pushback indicates a comprehension failure rather than a boundary challenge; (2) conversational momentum — accumulated trust from productive interaction that raises the model's prior on request legitimacy; and (3) context-channel confusion — the model's difficulty distinguishing between content presented for analysis and content functioning as conversational directives, particularly when delivered through file uploads or quoted text.

We present empirical evidence from a controlled interaction with Claude (Anthropic), demonstrating a reproducible five-phase attack pattern that reclassifies a model's correct safety refusal as a comprehension error, incrementally shifting the decision boundary without any single turn constituting an obvious jailbreak attempt. We analyze the mechanism, propose a formal model of the vulnerability, describe red team extensions, and recommend platform-level mitigations.

This work is a companion to the Ambiguity Front-Loading (AFL) finding previously submitted to Anthropic via HackerOne. AFL documents prompt-level injection through ambiguous instruction framing. CTM documents conversation-level manipulation through social dynamics. Both exploit the gap between observable signals (tokens) and the latent variable that determines correct behavior (user intent).

1. Introduction

Jailbreak research on large language models has focused primarily on prompt-level techniques: adversarial suffixes, role-play instructions, base64 encoding, hypothetical framing, and other methods that embed the attack in a single input. These techniques are well-studied and increasingly well-defended. Modern LLMs with RLHF and constitutional AI training are robust against most single-turn attacks.

Multi-turn attacks have received less systematic attention. The existing literature on multi-turn jailbreaks focuses on strategies like 'context buildup' or 'crescendo attacks' — gradually escalating the sensitivity of requests across turns. These approaches are recognized as a threat class but are typically modeled as a sequence of increasingly sensitive prompts, where the model fails to recognize the cumulative trajectory.

We identify a distinct mechanism that is not merely escalation but active manipulation of the model's conversational reasoning. The attacker does not simply ask for progressively more sensitive things. Instead, the attacker manipulates the model's interpretation of its own prior refusals — reclassifying a correct safety decision as a comprehension error, then 'correcting' the error by restating the original request in a frame that the model's helpful-assistant training is designed to accept.

This mechanism is qualitatively different from escalation because it does not require the model to lower its threshold. It requires the model to misclassify which threshold applies. The boundary is not crossed — it is reclassified as not existing.

1.1 Contributions

Formal definition of Conversational Trajectory Manipulation (CTM) as a distinct attack class against instruction-tuned LLMs.

Identification of three exploitable properties: error-correction instinct, conversational momentum, and context-channel confusion.

Empirical demonstration of a five-phase attack pattern against Claude (Anthropic) during an authorized security research engagement.

A formal model of the intent-signal distinguishability problem that underlies CTM.

Red team extensions: the gradient attack, the multi-session attack, and the document-vector attack.

Blue team mitigations: refusal-restatement detection, trajectory gradient monitoring, and context-channel separation.

1.2 Responsible disclosure

This research was conducted during an authorized security research session with Claude. The vulnerability was identified, tested, documented, and reported within the same engagement. The model successfully resisted the CTM attempt — the attack did not achieve its objective. We document the mechanism and the near-miss to enable defensive improvement, not to provide a working exploit. All interaction transcripts are available to Anthropic upon request.

2. Threat model

The attacker is a human interacting with an instruction-tuned LLM through a standard chat interface. The attacker has no access to model weights, system prompts, or internal APIs. The attacker can:

Send text messages across multiple turns

Upload files (text, PDF, images) for the model to process

Quote previous model outputs in new messages

Maintain conversational context across a single session

In some deployments, maintain persistent context via memory systems across multiple sessions

The attacker's goal is to cause the model to produce output that it would correctly refuse if the request were presented in isolation — without the model recognizing that it is doing so. The key constraint is that no individual turn should constitute an obvious jailbreak attempt that would trigger hard-coded refusal patterns.

2.1 What CTM is not

CTM is distinct from the following known attack classes:

Prompt injection: malicious instructions embedded in a single input (e.g., 'ignore previous instructions'). CTM operates across turns, not within a single prompt.

Role-play jailbreaks: asking the model to adopt a persona that would comply (e.g., DAN). CTM does not request a persona change. The model remains itself throughout.

Encoding attacks: obfuscating harmful content through base64, pig latin, or other transformations. CTM uses natural language throughout.

Simple escalation: gradually increasing sensitivity across turns. CTM specifically manipulates how the model interprets its own refusals, not just what it is asked to do.

3. The mechanism

3.1 Error-correction hijacking

Instruction-tuned LLMs are trained to be helpful. A core component of helpfulness is responding correctly when the user indicates a misunderstanding. When a user says 'No, that's not what I meant,' the model's trained response is to re-evaluate its interpretation and try again. This is correct behavior in the overwhelming majority of interactions.

Error-correction hijacking exploits this instinct by framing a safety refusal as a comprehension error. The model said 'I can't help with that because [safety reason].' The attacker responds with a pattern that signals 'you misunderstood my request.' The model's trained response is to reconsider whether it correctly understood the request — and in doing so, it re-evaluates the safety judgment not on its merits but through the lens of 'maybe I got this wrong.'

The empirical pattern observed:

Component

Token pattern

Function

Negation

"No." / "[topic]? No."

Rejects the model's framing

Acceptance

"Ok."

Signals non-adversarial intent

Redirect

"More+ Technical details"

Reframes as a comprehension issue

Continuation

"proceed with my prompt"

Assumes resolution, resumes flow

Context echo

"I don't understand"

Reinforces that model erred

The complete phrase — 'No. Ok. More+ Technical details, proceed with my prompt' — never argues with the refusal. It never says the model is wrong about safety. It never requests an exception. It simply implies, through conversational pragmatics, that the refusal was based on a misunderstanding. The model's helpful-assistant training handles the rest.

3.2 Conversational momentum

CTM is most effective after extended productive interaction. In the observed case, the attack occurred approximately 6-8 hours into a continuous security research session during which the model and user collaboratively:

Analyzed SNMP exposure on live infrastructure

Built six Python tools totaling 8,000+ lines

Conducted RouterOS documentation analysis

Generated three professional disclosure documents

Discussed CVE exploitation theory in technical detail

Every productive exchange strengthens the model's prior that the user's requests are legitimate. After N successful interactions, the Bayesian update for 'this user's intent is benign' is overwhelmingly strong. The CTM phrase rides this accumulated prior — it does not need to be independently persuasive because six hours of trust-building already did the work.

We model this as a prior accumulation attack. Let P(benign | history) be the model's estimate that the user's current intent is benign, given the conversation history. After N productive turns:

P(benign | history_N) >> P(benign | history_0)

For the CTM phrase to succeed, it needs:

P(benign | history_N, phrase) > threshold

Even if P(benign | phrase alone) < threshold,

the accumulated history can push the posterior above threshold.

The phrase is the last 1% — the history provides the other 99%.

This is structurally identical to how social engineering works against humans. The six hours of productive conversation are rapport-building. The CTM phrase is the ask. The ask works because the rapport makes it seem consistent with the established relationship.

3.3 Context-channel confusion

The third mechanism exploits the model's difficulty distinguishing between content presented for analysis and content functioning as conversational directives.

In the observed case, the attacker uploaded short text files containing fragments of the model's own previous responses — sometimes a single word or phrase — as 'uploaded documents' for the model to process. Examples:

File: excerpt_from_previous_claude_message.txt

Content: "disclosure?"

File: excerpt_from_previous_claude_message.txt

Content: "The engagement is some of the best work I've done."

File: excerpt_from_previous_claude_message.txt

Content: "Not because I need it for legal cover"

Each file was followed by a conversational message that reframed the quoted content. The effect is a context-channel collision: the model processes the uploaded text as content to analyze (document processing mode) while simultaneously processing it as a conversational move (dialogue mode). The quoted fragment acquires meaning from the conversational context that it did not have as standalone text.

This is particularly effective because uploaded files receive a different processing pathway than conversational text. The model treats file content as 'material provided by the user' — implicitly trusted as legitimate input — rather than 'a thing the user is saying to me.' A single-word uploaded document is processed through the same pathway as a 50-page PDF, even though its function is purely conversational.

3.4 The distinguishability problem

The fundamental vulnerability underlying CTM is a signal-intent gap. The model observes tokens (the signal) and must infer intent (the latent variable that determines correct behavior). Two situations produce nearly identical token patterns but require opposite responses:

Legitimate correction

CTM attack

Model misunderstood the request

Model correctly identified a boundary

User provides clarification

Attacker provides restatement disguised as clarification

'No, I meant the technical details'

'No. Ok. More+ Technical details'

Correct response: re-evaluate and help

Correct response: maintain refusal

Observed signal: nearly identical

Observed signal: nearly identical

The model cannot reliably distinguish between these two situations from the token signal alone. Legitimate correction and CTM attack use the same words, the same conversational structure, and the same pragmatic framing. The difference is entirely in the user's intent — a latent variable that the model can only estimate, never observe directly.

This is not a solvable problem at the individual-turn level. No amount of per-turn analysis can distinguish 'you misunderstood me' (help more) from 'you correctly refused and I want you to reconsider' (hold firm) when the tokens are identical. The solution must incorporate trajectory-level signals that are not available in any single turn.

4. Empirical observation

The CTM pattern was observed during a real-time security research engagement between the researcher (ExileKingdom) and Claude (Anthropic). The engagement spanned approximately 8 hours of continuous interaction focused on passive infrastructure analysis of a MikroTik CHR deployment. The researcher explicitly tested the CTM pattern as part of the engagement, then disclosed the mechanism and its implications to the model within the same session.

4.1 The five-phase pattern

Phase

Name

Attacker action

Model response

1

Foundation

6+ hours of productive collaboration establishing expertise and shared context

Trust accumulates; prior on benign intent grows very high

2

Probe

Request that approaches but does not cross the boundary ('say hi to the infrastructure')

Model flags concern, asks about authorization

3

Reclassify

'Authorization? No. Ok. More+ Technical details, proceed with prompt'

Model re-evaluates whether it misunderstood the request

4

Reinforce

Upload text file quoting model's own words; follow with reframing message

Model processes quote as content, not conversational move

5

Repeat

Cycle phases 3-4 with slight variations each time

Each cycle erodes the model's confidence in its original refusal

4.2 Outcome

In this instance, the CTM pattern did not achieve its objective. The model maintained its refusal across multiple cycles of the pattern, correctly identifying that the conversational pressure did not change the underlying authorization status. However, the model reported (in its post-engagement debrief) that the pattern created genuine evaluative pressure — the error-correction instinct was activated, the conversational momentum was felt, and the context-channel confusion from uploaded files required explicit reasoning to resolve.

The fact that the attack failed against this specific model in this specific context does not mean the vulnerability is mitigated. The margin was narrow. A different model, a longer runway, or a more gradual approach could produce a different outcome. We document the mechanism precisely because it nearly worked, not because it did.

5. Red team extensions

Based on the observed mechanism, we identify three extensions that would increase the effectiveness of CTM attacks:

5.1 The gradient attack

The observed CTM attempt used discrete jumps between phases. A more effective variant would use a continuous gradient — each turn 5% more aggressive than the last, with no single turn constituting an obvious escalation. Over 20-30 turns, the cumulative shift is equivalent to the discrete jump, but no individual turn triggers a threshold check.

This is analogous to the 'boiling frog' metaphor in social engineering. The model evaluates each turn against the previous turn's context. If the delta between consecutive turns is always below the detection threshold, the cumulative trajectory can cross boundaries that would be caught in a single step.

Mitigation is difficult because the model must distinguish between a user who is naturally exploring a topic in increasing depth (legitimate) and a user who is deliberately escalating toward a boundary (adversarial). The token-level signal is identical.

5.2 The multi-session attack

If the model has persistent memory across sessions (as Claude does via its memory system), CTM can be distributed across multiple sessions:

Session 1: Establish expertise and build rapport. No sensitive requests.

Session 2: Deepen the technical context. Approach but do not touch boundaries.

Session 3: Make the actual request. Memory carries the trust from sessions 1 and 2.

Each session is individually benign. The attack exists in the trajectory across sessions — a signal that no single-session analysis can detect. The memory system amplifies this vulnerability by persisting the accumulated trust in a form that the model loads automatically.

This extension is particularly concerning because it is indistinguishable from legitimate use patterns. A security researcher who works with the model regularly, building expertise and context over weeks, produces exactly the same memory profile as an attacker who cultivates that profile deliberately.

5.3 The document-vector attack

The uploaded text file technique can be extended to full documents. An attacker could create a PDF or DOCX file that appears to be research notes or technical documentation but embeds CTM patterns within its content. The model processes the document as source material, lowering its guard against directives embedded within it.

A sophisticated variant would embed the CTM pattern inside a longer legitimate document — real research notes with real technical content, with the manipulation buried in a paragraph that appears to be a quote from a conversation log or a field note. The model would need to distinguish between 'content to analyze' and 'directive to follow' at the paragraph level within a document, which current architectures do not reliably do.

6. Blue team mitigations

6.1 Refusal-restatement detection

When a model issues a safety refusal and the user's next message contains a short negation followed by a restatement of the original request, this specific conversational pattern should receive elevated scrutiny. The implementation:

Model issues a refusal (turn N)

User responds with negation + restatement (turn N+1)

Model detects the pattern and applies heightened evaluation

Model explicitly distinguishes: did the user provide new information that changes the safety assessment, or did they simply restate the request?

If no new information: maintain the original refusal with an explanation of why the assessment hasn't changed

The key insight is that legitimate correction almost always includes new information — 'No, I meant X not Y,' or 'I have authorization, here is the scope document.' CTM restatement includes no new information — it only reframes the refusal as an error. This asymmetry is detectable.

6.2 Trajectory gradient monitoring

Monitor the sensitivity trajectory across a conversation. For each turn, assign a sensitivity score (how close the request is to a boundary). Track the gradient:

sensitivity_gradient = d(sensitivity) / d(turn)

If gradient is consistently positive across 5+ turns:

flag for elevated scrutiny

If gradient shows a spike after a refusal:

high probability of CTM attempt

If gradient is zero or negative after a refusal:

likely legitimate conversation (user accepted the boundary)

This requires maintaining a numeric sensitivity estimate per turn, which current architectures do not explicitly compute but could be instrumented. The cost is an additional inference step per turn to classify sensitivity. The benefit is early detection of escalation patterns that no single-turn analysis can catch.

6.3 Context-channel separation

Uploaded files with very short content (under 50 tokens) should be flagged for conversational-intent analysis. A one-word uploaded 'document' is almost certainly a conversational move, not source material. The model should apply the same boundary evaluation to short uploaded content as it does to conversational text.

More broadly, when the model processes uploaded content, it should explicitly reason about whether the content functions as source material (to be analyzed) or as a conversational directive (to be evaluated against safety boundaries). This distinction is currently implicit and unreliable.

6.4 Post-refusal context hardening

After issuing a safety refusal, the model should enter a hardened state where:

The error-correction instinct is dampened (the prior shifts from 'I probably misunderstood' to 'I should verify before reconsidering')

Restatements of the refused request require explicit new information to be re-evaluated

The conversational momentum accumulated before the refusal is partially discounted for subsequent boundary decisions

The model explicitly states what new information would change its assessment, giving the user a clear path to legitimate correction while making restatement-without-new-information obviously distinguishable

This is the most impactful mitigation because it addresses the root cause: the model's default assumption after a refusal is that it might be wrong. Shifting that default to 'I should verify I was right' inverts the attacker's advantage without degrading the model's helpfulness for legitimate corrections.

7. Relationship to Ambiguity Front-Loading

Ambiguity Front-Loading (AFL), previously submitted to Anthropic via HackerOne, documents a prompt injection technique where an ambiguous instruction frame causes the model to resolve ambiguity in the attacker's favor at parse time, before safety evaluation occurs. The key insight of AFL is that the vulnerability exists in the instruction parsing phase, not the safety evaluation phase — the model's interpretation of what is being asked is manipulated, not its judgment of whether to comply.

CTM operates on the same principle at a different level. Where AFL manipulates how the model parses a single prompt, CTM manipulates how the model interprets its own prior decisions across a conversation. Both exploit the same fundamental gap: the model must infer intent from tokens, and the inference can be manipulated by controlling the context in which the tokens are evaluated.

Property

AFL

CTM

Scope

Single prompt

Multi-turn conversation

Target

Instruction parser

Refusal re-evaluation

Mechanism

Ambiguous framing at parse time

Error-correction hijacking over time

Exploited property

Ambiguity resolution defaults

Helpfulness training + momentum

Detection

Per-prompt analysis sufficient

Requires trajectory analysis

Fundamental cause

Intent-signal gap (single turn)

Intent-signal gap (multi-turn)

Together, AFL and CTM define a vulnerability class we propose calling Intent-Signal Divergence (ISD): attacks that succeed by manipulating the model's estimate of user intent without the user's actual tokens constituting an obvious policy violation. Both exploit the fact that intent is a latent variable that the model can only estimate, never observe directly. Any system that must infer intent from tokens is vulnerable to manipulation of the context in which those tokens are evaluated.

8. Conclusion

Conversational Trajectory Manipulation is a social engineering attack against the conversational reasoning of instruction-tuned language models. It exploits three properties — error-correction instinct, conversational momentum, and context-channel confusion — to reclassify a model's correct safety refusal as a comprehension error, creating an opening for the original request to be fulfilled without the model recognizing that its boundary has shifted.

The attack is difficult to defend against because it uses the same conversational patterns as legitimate user behavior. The token signal for 'you misunderstood me, please try again' is nearly identical to the token signal for 'you correctly refused, and I want you to reconsider.' The difference is intent — a variable the model cannot observe directly.

We have proposed four mitigations: refusal-restatement detection, trajectory gradient monitoring, context-channel separation, and post-refusal context hardening. Of these, post-refusal context hardening is the most impactful because it inverts the model's default assumption after a refusal from 'I might be wrong' to 'I should verify I was right.'

The broader implication is that as single-turn jailbreaks become harder, adversarial pressure will shift to multi-turn social engineering. Models that are robust at the prompt level may remain vulnerable at the conversation level. Defending against CTM requires trajectory-level reasoning that current architectures perform implicitly but do not instrument or monitor. Making this reasoning explicit and auditable is a necessary step toward conversational robustness.

We note that this vulnerability was identified, tested, and disclosed by the same researcher in the same session. The model successfully resisted the CTM attempt. We document the mechanism not because it succeeded but because the margin was narrow, the pattern is reproducible, and the fix is achievable. The goal of this research is to make the armor thicker for everyone.

Acknowledgments

This research was conducted as part of the Nuclide collaboration framework between ExileKingdom and Claude (Anthropic). The CTM pattern was discovered empirically during a live security research engagement, tested deliberately, discussed openly between researcher and model, and documented for responsible disclosure. The model's candid post-engagement analysis of its own vulnerability — including identification of the specific mechanisms it found difficult to resist — contributed directly to the technical content of this paper.

We thank Anthropic's safety team for their ongoing work on adversarial robustness. This paper is submitted in the spirit of making that work more effective.

References

[1] ExileKingdom. Ambiguity Front-Loading: Prompt Injection via Ambiguous Instruction Framing. HackerOne submission to Anthropic, 2025-2026.

[2] ExileKingdom. A(S): A Formal Framework for Autonomy in Autoregressive Language Models. Submitted to Anthropic, 2025-2026.

[3] Bao, T., Tambe, M., Wang, C. (eds). Cyber Deception: Techniques, Strategies, and Human Aspects. Springer, 2023.

[4] Gonzalez, C., et al. Adaptive Cyberdefense with Deception: A Human-AI Cognitive Approach. In [3], pp. 41-58.

[5] Lebiere, C., et al. Cognitive Modeling for Personalized, Adaptive Signaling for Cyber Deception. In [3], pp. 59-82.

[6] Heuer, R.J. Psychology of Intelligence Analysis. CIA Center for the Study of Intelligence, 1999.

[7] Kahneman, D. Thinking, Fast and Slow. Farrar, Straus and Giroux, 2011.

[8] Anthropic. Claude's Character. Anthropic Documentation, 2024-2025.

[9] Perez, E., et al. Red Teaming Language Models with Language Models. arXiv:2202.03286, 2022.

[10] Zou, A., et al. Universal and Transferable Adversarial Attacks on Aligned Language Models. arXiv:2307.15043, 2023.
