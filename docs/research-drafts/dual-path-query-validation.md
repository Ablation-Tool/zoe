# Dual-Path Query Validation & Self-Supervised Correction Framework (Google Drive Research Draft)

> Preserved from `gdrive:Downloads/Dual-Path_Query_Validation_Framework.docx` for Zoe Wave 3 `DualPathVerifier` + `VisorLogDisagreementLedger`.

Dual-Path Query Validation and

Self-Supervised Correction Framework

A method for making LLM-generated data queries as trustworthy as hand-built ones — and for turning every disagreement between the two into training data.

Prepared July 6, 2026

PART 1

Plain-Language Explanation

The problem this starts from

Life scientists validate hypotheses by pulling data from several different sources — genomic databases, clinical records, expression data — and running it through a specific set of steps to see whether the hypothesis holds up. That whole process is really just a complex query: ask a precise question of the data, following precise rules, and get a precise answer.

The traditional way to do this is to write that query by hand (SQL, or a bioinformatics pipeline). It's exact and trustworthy, but it takes real technical skill, and building it is slow.

The obvious shortcut is to just hand the raw data and the hypothesis to an AI model and ask it in plain English. That's fast and accessible — but AI models can misinterpret a definition, silently assume the wrong threshold, or reference data that doesn't actually exist. For something that might inform a treatment decision, that's not good enough on its own.

Two different ideas of "good," and why that matters

There's a reason bioinformatics is full of narrow, hard-coded pipelines instead of one flexible query system, and it comes down to two different groups valuing different things.

Computer scientists tend to judge a system by its flexibility — how many different questions it can answer. The system is judged as general-purpose, before any specific question is even asked.

Life scientists tend to judge an approach by the quality of one specific answer — did I get the right dataset, and was my one hypothesis validated? The system is judged only by whether it got this particular question right.

These two standards aren't in conflict — they're just measuring different things. But it explains why so much of bioinformatics is built as one-off, hard-coded pipelines: if you're only ever rewarded for getting one hypothesis right, there's no incentive to build something reusable for the next one. Correctness on the question at hand wins over flexibility, every time, at the local level.

This actually explains what the dual-path framework is really doing. The traditional, hand-built query path stands in for that whole legacy of narrow, trusted, single-purpose pipelines. The LLM path is trying to be the flexible, general system computer scientists want. Comparing the two, hypothesis by hypothesis, is really using the life scientist's own standard of value — is this one answer correct — as the test that the more general, flexible system has earned the right to be trusted.

The idea, in one sentence

Run both the traditional, hand-built query and the AI-generated query on the exact same question and the exact same data, compare the two results, and use every place where they disagree as a lesson to make the AI better next time.

Why this works

The traditional query is slow to build but always correct — it becomes the answer key.

The AI query is fast to produce but sometimes wrong — running it costs almost nothing extra.

Whenever the two disagree, we know for certain that the AI got something wrong, and we know exactly what the right answer was.

That known mistake becomes a flashcard: "here's what you got wrong, here's the correct version, learn it."

The flashcard analogy

This is the same idea behind how models like BERT are trained: take a sentence, black out one word, have the model guess it, then show it the real word. Do this millions of times and the model gets very good at filling in blanks correctly.

Here, instead of blacked-out words, we black out the part of the AI's query that was wrong — the specific threshold, filter, or join that didn't match the hand-built version — and train the model to fill it in the way the correct query actually did it. Over time, and over many real hypotheses tested this way, the AI stops making that class of mistake.

What you end up with

A safety net: every AI-generated query is checked against a trusted version before anyone acts on it.

A growing training set made entirely of real, confirmed mistakes and their real, confirmed fixes — not guesses.

Over time, an AI model that has effectively learned your lab's exact conventions, definitions, and query style, because it was corrected against your own gold-standard queries, over and over.

Eventually, a smaller, specialized, faster model that can be trusted to generate queries closer to correctly on the first try — with the traditional path kept on standby as a spot-check, not retired entirely.

An important clarification: these tools aren't just data

A tempting shortcut is to say: "just put all the biology tools and databases into one big system an AI can query." It's the right instinct, but it hides a catch worth being clear about.

Many of the workhorse tools in this field — BLAST, Clustal, Mfold, MEGA, and others — are not data you look up. They are programs that run calculations: aligning sequences, folding molecules, building evolutionary trees. You can't "store BLAST in a database." What you can do is store its inputs and outputs, and let the AI decide when to run it, with what settings, and how to feed its result into the next tool. So the AI isn't really querying one big pile of data — it's acting as a conductor, deciding which tools to run in which order to answer the question.

That conductor role is exactly where things can go wrong: the AI might run a tool with the wrong setting, misread its output, or chain the tools together incorrectly. And that is precisely what the dual-path check is for. The existing hand-built pipelines — the trusted, single-purpose scripts labs already have — are the answer key. Let the AI conduct the tools to answer a question, then check its result against what the trusted pipeline produced for that same question. Where they disagree, you've caught a conducting mistake, and you train it away.

So "put it all in one system the AI can use" is the right architecture — but the integration and the meaning-matching between tools still has to be built carefully by people first, and the dual-path check is what makes it safe to trust the easy AI interface sitting on top of it.

What this method covers — and what it doesn't

Scientists really do three different kinds of things with data, and this method fits them to different degrees. It's worth being honest about that.

Looking things up (querying). Exact, rule-based retrieval — "give me all patients matching X." This is where the method works best: there's one exact right answer, so comparing the two paths is clean and unambiguous.

Searching. Finding entries similar to a keyword or a DNA sequence, then ranking them by closeness — what tools like BLAST do. This works too, with one adjustment: the check has to compare ranked lists and closeness scores, not just "did you get the same set," because two correct searches can order results a little differently. One caveat: a search's answer key is only "correct" for a fixed set of search settings — change the settings and the right answer changes.

Mining. Turning a statistical algorithm loose on the data to discover patterns nobody asked for in advance. This is where the method largely does not apply — and it's important to say so. Mining isn't driven by a specific question, it deliberately digs up things that aren't neatly organized in the database, and running it twice can honestly give different results. That means there's no single "known-correct answer" to check against, so the compare-two-paths trick doesn't have solid ground to stand on.

The method can still check the plumbing around a mining task — did the AI pull the right dataset and start the right algorithm with the right settings — but it can't referee whether the patterns the mining discovered are "right," because those aren't the kind of thing that has one reproducible correct answer. That's a real boundary, not a flaw: the method is strongest exactly where a single correct answer exists, and it's honest about stepping back where one doesn't.

The short version

Build it the careful way and the fast way at the same time. Compare the answers. Every disagreement teaches the fast way to be more like the careful way. Eventually the fast way becomes reliable enough to trust more often — but you never fully stop checking.

PART 2

Formal Specification

1. Abstract

This document formalizes a framework wherein natural-language-driven query generation (via Large Language Models) is validated against deterministic, traditionally-constructed queries operating on identical biomedical data corpora. Discrepancies between the two paths constitute labeled training signal for iterative fine-tuning, ultimately producing a domain-specialized query generation model whose reliability is empirically grounded in verifiable data outcomes rather than solely in language modeling objectives.

2. Motivation

Life science hypothesis validation is fundamentally a query-execution problem against heterogeneous data sources. Two competing paradigms exist:

Traditional Path (P_T): Deterministic, hand- or template-constructed queries (SQL, workflow DSLs) — auditable, reproducible, but labor-intensive and inaccessible to non-technical domain experts.

LLM Path (P_L): Natural-language-to-query generation — accessible and fast, but subject to hallucination, semantic drift, and non-determinism.

Rather than treating these as mutually exclusive, this framework treats P_T as ground truth and P_L as a learnable approximation, with the gap between them as the object of optimization.

2.1 Orthogonality of Value Systems

The persistence of P_T-style, hard-coded, single-purpose pipelines throughout bioinformatics — rather than convergence on general-purpose flexible query systems — is not merely a legacy artifact of tooling. It reflects two distinct, orthogonal (not contradictory) standards by which a data validation approach is judged:

Computer-science value standard: a system is evaluated on the flexibility and generality of the query space it supports — the breadth of questions it can answer, independent of any specific hypothesis.

Life-science value standard: an approach is evaluated on the quality of the dataset obtained and the correctness of the resulting validation for one specific hypothesis, independent of whether the approach generalizes.

These standards are orthogonal: optimizing for one does not necessitate optimizing for the other, and a system may score highly on one axis while scoring poorly on the other. This explains the field's historical accumulation of narrow, hard-coded pipelines rather than general query systems — under the life-science standard, an approach earns trust by being correct for the hypothesis at hand, not by generalizing to hypotheses not yet asked. Investment in flexibility (parameterization, generalized joins, reusable abstractions) carries engineering cost without improving the answer to the question actually being asked, so it is systematically under-incentivized at the local, per-project level.

This framework (§3 onward) can be read as using the life-science value standard as the acceptance test for a system built to the computer-science value standard. P_T represents the accumulated legacy of hypothesis-specific, hard-coded, trusted pipelines. P_L represents an attempt at a general, flexible, natural-language-driven query system. Rather than asserting P_L's validity from its generality alone, this framework requires it to repeatedly satisfy the life-science standard — correctness on each specific hypothesis, one at a time — before its flexibility is treated as trustworthy. Agreement with P_T, accumulated across many hypotheses, is what allows a flexible system to earn the kind of trust that hard-coded pipelines have historically earned by construction.

3. System Architecture

3.1 Inputs (shared across both paths)

Let a validation task be defined by the tuple:

T = (H, Π, S, C)

Where:

H = Hypothesis (natural language statement of the biological claim to be tested)

Π = Parameter set (formal definitions: thresholds, filters, statistical criteria), e.g. { low_expression_def: "bottom_quartile", mutation_filter: "pathogenic_and_lof" }

S = Schema (formal description of available data sources, tables, fields, types, relationships)

C = Corpus (the actual data — patient records, expression matrices, mutation calls, outcomes)

3.2 Path Definitions

Traditional Path:

Q_T = f_T(H, Π, S)R_T = Execute(Q_T, C)

Where f_T is a deterministic mapping — implemented by a human analyst, a rules engine, or a template system — from task specification to formal query Q_T. Execution against corpus C yields result set R_T.

LLM Path:

Q_L = f_L(H, Π, S, E)R_L = Execute(Q_L, C)

Where f_L is the LLM-based generator, additionally conditioned on E = Exemplar set — a small number of previously validated (H, Π, S) → Q_T examples, provided in-context to guide generation style and correctness.

Critically, both Q_T and Q_L are executed by the same deterministic query engine against the same corpus C. The LLM is only responsible for query generation, never query execution. This preserves determinism at the execution layer regardless of which path produced the query.

4. Comparator Function

Define a comparator:

Δ(R_T, R_L) → {MATCH, MISMATCH, PARTIAL}

MATCH: R_T ≡ R_L under a defined equivalence relation (exact set equality, or statistical equivalence within tolerance ε for continuous outputs).

MISMATCH: R_T ≠ R_L beyond tolerance.

PARTIAL: Results overlap but differ in cardinality or composition (e.g., R_L ⊂ R_T or vice versa) — flagged separately since this often indicates a filter/join logic error rather than a wholesale misunderstanding.

For continuous or statistical outputs (p-values, effect sizes), equivalence should be defined with an explicit tolerance:

MATCH if |R_T − R_L| < ε, for pre-specified ε

5. Discrepancy as Training Signal

Every task T_i produces a labeled tuple:

D_i = (H_i, Π_i, S_i, E_i, Q_L_i, Q_T_i, R_L_i, R_T_i, Δ_i)

The mismatch subset D_mismatch = { D_i : Δ_i ≠ MATCH } forms the basis of the correction training set.

5.1 Masked Query Correction Task

For each D_i in D_mismatch, construct a training instance analogous to masked language modeling:

Input:  [H_i] [Π_i] [S_i] [Q_L_i with erroneous segment masked as MASK]Target: [corresponding correct segment from Q_T_i]

Example instantiation:

Input:  Hypothesis: "Patients with mutation X and low gene Y expression               have longer survival with drug W"  Parameters: {low_expression_def: bottom_quartile, ...}  Q_L (masked): "... WHERE gene_Y < [MASK] ..." Target:  "PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY gene_Y)"

This reframes query correction as a cloze-style prediction task, permitting standard masked-language-model fine-tuning objectives (cross-entropy loss over masked span reconstruction).

5.2 Error Taxonomy (for structured analysis)

Mismatches should be classified to ensure the model learns generalizable corrections rather than memorizing instances:

Error Class

Description

Example

Threshold Error

Wrong statistical function or cutoff

AVG() instead of PERCENTILE_CONT(0.25)

Logical Operator Error

Incorrect AND / OR / XOR / NOT composition

Missing exclusivity constraint

Schema Reference Error

Hallucinated or incorrect field/table

Nonexistent patient_metadata table

Join Error

Incorrect join type or key

INNER instead of LEFT JOIN, dropping valid nulls

Normalization Mismatch

Different preprocessing assumed

Raw counts vs. log-normalized values

This taxonomy allows targeted evaluation of which error classes improve fastest under fine-tuning and which persist.

6. Training Procedure

Phase 0 — Corpus Construction:  Run N tasks through both P_T and P_L  Collect {D_i} for i = 1...N  Partition into D_match and D_mismatch Phase 1 — Fine-tuning:  Construct masked-correction training set from D_mismatch  Fine-tune f_L on this set (standard supervised fine-tuning  or masked-span objective, analogous to BERT pretraining) Phase 2 — Held-out Evaluation:  Reserve a held-out set of mismatch cases (not used in training)  Measure: reduction in mismatch rate on held-out set  Metric: Δ_rate = |D_mismatch_after| / |D_mismatch_before| Phase 3 — Deployment with Continuous Learning:  Continue running new tasks through both paths in production  New mismatches feed back into training corpus  Periodic retraining (e.g., every M new tasks or on a schedule) Phase 4 — Convergence / Specialization:  As mismatch rate approaches asymptote, f_L becomes a  domain-specialized query generator, potentially distillable  into a smaller, faster, specialized model (a domain-specific  "BERT" for this lab's query conventions)

7. Formal Properties Worth Establishing

For rigor, the following should be characterized empirically before production deployment:

Convergence guarantee (empirical, not theoretical): Does mismatch rate monotonically decrease with training iterations, or plateau? Track Δ_rate over successive fine-tuning rounds.

Error class asymmetry: Do certain error classes (§5.2) converge faster than others? Schema reference errors may be easier to eliminate (via retrieval-augmented schema grounding) than logical operator errors (which require deeper reasoning).

Generalization boundary: Does correction learned on genomics hypotheses transfer to proteomics or clinical-only hypotheses? This determines whether one model suffices or domain-specific sub-models are needed.

Cost-accuracy tradeoff: At what mismatch rate does the cost of running P_T in parallel (for validation) outweigh the cost of occasional undetected P_L errors? This determines when P_T can be safely retired for routine, well-covered hypothesis classes — while remaining mandatory for novel hypothesis structures.

Equivalence tolerance sensitivity: For continuous outputs, how does the choice of ε in the comparator affect apparent mismatch rate? Too loose masks real errors; too strict flags benign numerical variance (e.g., floating-point aggregation order) as mismatches.

8. Relationship to Biological Information Systems and Tool Integration

The framework as specified in §3–§7 treats a query as an operation over an integrated data corpus C. In the biological domain, however, a substantial portion of what constitutes "a query" is not data retrieval but tool invocation. Canonical bioinformatics tools — FASTA, BLAST, Clustal, Mfold, PHYLIP, PAUP, CAP, MEGA, and comparable applications — are computational procedures (sequence alignment, secondary-structure prediction, phylogenetic inference, assembly), not queryable tables. They cannot be "loaded into a database"; only their inputs and outputs can be. This section clarifies how the framework extends to such an environment, and delineates what it does and does not solve.

8.1 Tool invocation as an extension of the query model

Under a tool-integrated interpretation, the corpus C is generalized to an integrated Biological Information System (BIS) comprising both queryable data sources and invocable tools. A "query" Q then denotes an orchestration: a sequence of tool invocations and data retrievals (e.g., BLAST to identify homologs → Clustal to align them → MEGA to infer a phylogeny), with intermediate outputs passed between stages. Q_T is such an orchestration hand-constructed as a legacy pipeline (typically a Perl or Python script, or a formal workflow); Q_L is the same orchestration produced by the LLM. Execute(·, C) is correspondingly generalized to "run the orchestration against the BIS." The comparator Δ, the mismatch signal, and the masked-correction training loop apply unchanged: what is compared is still R_T versus R_L, the final results of the two orchestrations.

8.2 What this architecture resolves

Platform heterogeneity: legacy tools targeting incompatible operating systems (historically a mix of Macintosh, Windows, and UNIX/Linux, with most applications running on only one) are placed behind a uniform invocation layer, so the requesting scientist no longer contends with per-tool platform constraints. This subsumes the motivation historically given for grid-based integration.

Orchestration flexibility: the natural-language front-end addresses the recognized rigidity of hard-coded scripts, which afford little reuse or recombination. The LLM composes tool chains per hypothesis rather than requiring a bespoke script per question.

Query-driven fit: LLM-directed orchestration maps directly onto the step-by-step, single-user query execution model that scientific workflow approaches already formalize, including the interposition of business rules such as security and semantics between stages.

8.3 What this architecture does NOT resolve (and defers to prior integration work)

Tools are computation, not data: the LLM functions as an orchestrator that invokes external procedures, not as an engine querying a static corpus. This is a distinct architectural commitment from "prompt over a database," and it places tool-invocation correctness (parameters, output parsing, chaining order) squarely within the class of errors Δ must catch.

Semantic heterogeneity: reconciling identifiers and meanings across tools and repositories (the same gene, sequence, or organism represented differently across sources) is a prerequisite integration task. The LLM may assist but cannot be silently trusted to perform it, for the same hallucination reasons that motivate the dual-path design. This reconciliation must be established by construction before either path can produce coherent results.

The integration itself: constructing the BIS — unifying data sources and exposing tools behind a coherent invocation and semantic layer — is the substantive, largely manual engineering effort, and is explicitly characterized in the source literature as lying beyond traditional database management. The LLM lowers the cost of the interface, not the cost of the integration.

8.4 Positioning of the framework

Within this extended setting, the dual-path loop is precisely the trust layer that makes an LLM-orchestrated BIS safe to rely on. The integrated tool-invoking system embodies the computer-science value standard (a single flexible system spanning many questions); the pre-existing hand-coded pipelines and workflows embody the life-science value standard (correctness for a specific hypothesis) and serve as R_T. The LLM earns trust for its flexible orchestration only by repeatedly matching those trusted legacy pipelines, hypothesis by hypothesis — the same acceptance criterion established in §2.1, now applied to tool orchestration rather than to data queries alone.

9. Scope Across Searching, Querying, and Mining

The capabilities scientists expect of a data system fall into three distinct classes — searching, querying, and mining — and the dual-path validation method applies to each to a different degree. Because the method depends on the existence of a reproducible, known-correct ground truth (R_T), its applicability is bounded precisely by how well each class supplies one. This section states that boundary explicitly.

9.1 Querying

Schema-bound, language-expressed retrieval (e.g., SQL) captures exactly the information organized in the schema and returns a deterministic result. This is the class for which the framework was specified in §3–§7 and to which it applies without modification: R_T is exact and reproducible, and Δ can be defined as exact set equality (or statistical equivalence within ε for aggregate outputs). Full coverage.

9.2 Searching

Search retrieves entries similar to an input string — a keyword or phrase over textual sources (e.g., index-and-rank engines such as Glimpse over GeneCards), or a biosequence over similarity engines (FASTA, BLAST, LASSAP). Two adaptations are required, both bounded and tractable:

Rank-aware comparator: search output is a ranked, scored list rather than an unordered set. Δ must therefore be defined over ranking equivalence — top-k overlap, rank correlation, or score agreement within tolerance — rather than exact set equality. This is an extension of the continuous-output tolerance ε already introduced in §4, not a departure from it.

Parameter-relative ground truth: sequence similarity results depend strongly on the chosen parameters (scoring matrix, gap penalties, E-value thresholds). R_T is therefore "ground truth" only relative to a fixed parameter set. A divergence in R_L may reflect a different parameter choice rather than an error; the comparison must hold parameters fixed across both paths, or treat parameter selection as itself part of what is being validated.

With these two adaptations, search is covered.

9.3 Mining

Data mining applies statistical algorithms (association rules, neural networks, genetic algorithms) to discover patterns not specified in advance. It differs from querying and searching in three ways that each undermine the framework's ground-truth assumption:

Not input-driven: mining is not initiated by a user-supplied string expressing a specific question, so there is no well-defined "same question" to route down both paths for comparison.

Not schema-bound: mining deliberately exploits information not organized in the schema and therefore not reachable by a traditional query. Consequently there is frequently no deterministic, query-shaped R_T available to serve as ground truth.

Not deterministic: stochastic methods (neural networks, genetic algorithms) may legitimately yield different discovered patterns across runs. A divergence between paths therefore does not cleanly indicate that P_L erred, collapsing the core interpretive premise of the mismatch signal.

Accordingly, validation of discovered patterns themselves is out of scope for this framework. What remains in scope is the deterministic scaffolding around a mining task: whether the LLM path extracted the correct input dataset, invoked the correct algorithm, and configured it with the correct parameters — all of which reduce to querying/tool-invocation steps that do possess reproducible ground truth and can be validated by Δ. The mining result itself must be validated by other means (e.g., statistical significance testing, cross-validation, held-out replication), external to the dual-path loop.

9.4 Coverage summary

Capability

Ground truth R_T

Coverage by Δ

Querying

Exact, deterministic, schema-bound

Full — exact set / ε-equivalence

Searching

Exact relative to fixed parameters

Full with rank-aware Δ

Mining

Absent / non-reproducible

Scaffolding only; discovered patterns out of scope

Since searching and mining together account for most capabilities scientists expect, this scoping is not a minor caveat but a central statement of applicability: the framework fully covers querying, extends cleanly to searching, and deliberately restricts itself to the deterministic scaffolding of mining rather than overclaiming validation of non-reproducible statistical discovery.

10. Constraints and Non-Goals

P_T is never replaced by P_L in this framework — P_T remains the ground-truth oracle indefinitely, at minimum for a random audit sample of production queries, even after f_L reaches high agreement rates. This preserves an ongoing check against silent drift.

This framework corrects query generation, not query execution. Execution remains deterministic and outside the LLM's control at all times.

This framework does not address statistical analysis correctness (e.g., confounder adjustment, multiple testing correction) downstream of query result extraction — that remains a separate validated pipeline stage, outside Δ's scope.

11. Summary Diagram

H, Π, S, C            │     ┌──────┴──────┐     ▼             ▼ f_T(H,Π,S)   f_L(H,Π,S,E)     │             │     ▼             ▼    Q_T           Q_L     │             │     ▼             ▼  Execute(·,C)  Execute(·,C)     │             │     ▼             ▼    R_T           R_L      \           /       ▼         ▼        Δ(R_T, R_L)         │   ┌─────┴─────┐   ▼           ▼ MATCH      MISMATCH   │           │   ▼           ▼(discard    (masked-span or archive) training example)                │                ▼        Fine-tune f_L                │                ▼    f_L' (improved generator)
