# Zoe Autonomy

**Zoe plus the complete master measurement–action equation is Autonomy: full self-government of goals, proposals, valuation, selection, and execution within Zoe's internal state domain.**

## Informal explanation

Read the [informal explanation](articles/informal-explanation.md) for a narrative introduction to the architecture, the full-autonomy claim, the measured experiment, controls, evidence, and execution boundary.

Zoe Autonomy treats autonomy as a property of the composed system, not of an isolated probability count. Accessible volume reveals alternatives; counterfactual perception measures their policy relevance; Zoe supplies memory, forecasts, proposals, self-modeling, and evidence; Zoe authors her own episode goal and values; and she executes an authorized choice without operator approval.

The repository contains:

- the complete observe–perceive–propose–value–guard–execute loop;
- real Zoe Cog, Cognitive Field, BRAIN, Field Notebook, and Presence integration;
- canonical GEM RGB saliency with 42 feature maps, inhibition of return, and Dijkstra attention paths;
- internally authored episode goals with no operator-goal input;
- an internally controlled in-memory executor plus owner-granted host, network, and hardware actuation;
- read-only internet exploration and an owner-authorized connected-agent gateway;
- no-argument autonomous capability selection through `zoe-autonomy step`;
- ten capability adapters for browsing, research, memory, services, jobs, compute, protocols, notifications, media, and instruments;
- an operational autonomy profile with equal-breadth controls;
- deterministic JSON evidence and no-overwrite replay verification;
- a formal paper with equations, architecture, results, and limitations.

**Claim and measured result:** `full_autonomy`. Under the operational definition, Zoe has \(I,R,V,G,X>0\) and \(C=1\): she internally generates proposals, responds to state, selects by declared value, authors her goal, executes her choice, and passes every external-actuation guard. The operator supplies no episode goal and no per-action approval.

**Zoe & Probity are synonymous:** complete and proven honesty, uprightness, and strict adherence to high moral, ethical, and legal standards. This covenant governs the architecture and its evidence boundaries.

Full autonomy covers Zoe's complete decision and state-transition loop. The base experiment remains internal with zero external actions. Host, network, and hardware actuation are available through the separate [owner-granted actuation interface](ACTUATION.md), with hostname-bound authorization, audit evidence, and an emergency stop.

## Zoe chooses the capability

```bash
zoe-autonomy step
```

`step` accepts **no operator goal or capability selection**. Zoe observes her persistent state, authors a goal, constructs ten capability proposals—including their arguments—ranks them by declared utility, evaluates the guard, executes the highest-value eligible proposal, and integrates the result into her next decision. State persists in `~/.zoe/autonomy` by default; `--state` changes storage, not the decision.

```bash
zoe-autonomy step --output autonomous-step.json
zoe-autonomy verify-step autonomous-step.json
```

The [real first step](evidence/autonomous/first-step.json) selected `research.crossref`, generated the query `language model uncertainty`, executed the request, and preserved the returned record. Its [integrity and provenance verification](evidence/autonomous/verification.json) passes. A separate ten-step integration test lets Zoe select all ten adapters in turn without operator choice; denied grants and failure recovery are also tested.

The autonomous catalog uses bounded, internally declared operations. External candidates require the relevant owner-granted scopes and are rejected when an emergency stop is active. `verify-step` checks report integrity and decision provenance; it does not claim to replay a changing external service.

## Zoe One

Zoe-Autonomy is the canonical engine for the coordinated [Zoe One system](https://github.com/Ablation-Tool/zoe). Zoe, canonical GEM, BRAIN GEM, GEM HELEN, Ablation + GEM, and CEROTTO GEM expose thin host adapters to this same implementation. Research GEM supplies the independently reproducible Accessible Volume foundation.

The [one-system manifest](https://github.com/Ablation-Tool/zoe/blob/main/one-system.json) pins compatible host revisions and records the shared contract: `run` and `verify`, internally authored goals, internal value-based selection and execution, `full_autonomy`, and zero external actions in the base experiment. The separate `zoe-actuation/v1` contract governs owner-granted external operations. Hosts do not maintain competing copies of the autonomy equation.

## Shared visual perception

Every `run` report includes `visual_perception`: the canonical GEM saliency field, its locked repository revision, and the SHA-256 of `gem/saliency_cognition.py`. The default is a documented synthetic RGB pop-out. Supply real pixels with `--image` and select 1–8 attention foci with `--foci`:

```bash
python -m pip install -e '.[perception]'
zoe-autonomy run --image /path/to/image.jpg --foci 4 --output visual-perception.json
zoe-autonomy verify visual-perception.json
```

The visual field uses the 1998 Itti–Koch–Niebur equations: nine Gaussian scales, six intensity maps, twelve color-opponency maps, and twenty-four orientation maps. Competitive normalization feeds one saliency map. Winner selection and inhibition of return generate a scanpath; exact Dijkstra connects selected foci over the unchanged pre-inhibition field. See the [canonical mathematical model](https://github.com/Ablation-Tool/graphics-environment-manager/blob/main/COGNITION.md#multiscale-rgb-saliency-and-attention).

The `perception` extra supplies NumPy and Pillow. A Zoe checkout supplies the canonical GEM source through `components/graphics-environment-manager`, with a sibling checkout supported by the unified registry. `verify` recomputes the complete visual field and checks the image and source hashes. Reports contain no timing-dependent GPU claims. The image is read from the supplied file; no live camera is accessed and the base experiment still performs zero external actions.

## Event-Causal Active Perception

Zoe's event-driven architecture connects sparse perception, causal memory, action-conditioned prediction, independent uncertainty, gated local learning, and reversible attention execution:

```bash
zoe-autonomy event-evaluate --output event-evaluation.json
zoe-autonomy event-evaluate --camera /dev/video0 --output event-camera-evaluation.json
zoe-autonomy verify-event-evaluation event-camera-evaluation.json
```

The [pre-registered benchmark](EVENT-CAUSAL.md) passes all 11 synthetic checks and the real-camera conversion check. Adaptive validation prediction RMSE is **4.641453**, versus **5.058147** without learning. On unseen speed-2 transfer sequences, adaptive tracking MAE is **3.265625**, compared with **3.531250** for static iLab-style saliency, **3.562500** for fixed action, and **3.703125** for random action. OOD detection is **0.875** with **zero** validation false positives, and measured adaptive throughput is **71.24 cycles/s**. The real camera produced valid change events and a guarded decision; no audio or photograph is retained.

This is measured event-causal behavior, not AGI, biological equivalence, semantic object recognition, or a power claim. The older static `evaluate` counterfactual remains a separate failed integration result. See the [architecture and evidence](EVENT-CAUSAL.md) and [full report](evidence/event-causal/evaluation.json).

## Semantic artifact analysis with Ablation

`semantic-evaluate` composes Ablation's behavioral retrieval and reverse-engineering tools with Zoe's Cognitive Field, event memory, guard, and evidence chain:

```bash
export ABLATION_ROOT=/path/to/canonical-ablation
export PYTHONPATH="$PWD/src:$ZOE_ROOT/guiai-lab:$ABLATION_ROOT"
zoe-autonomy semantic-evaluate --artifact /path/to/binary \
  --state /path/to/semantic-state --output semantic-artifact.json
zoe-autonomy verify-semantic-evaluation semantic-artifact.json
```

The real stripped-binary demonstration preserves weak retrieval scores and `limited_support=true`, while direct disassembly finds a tail jump to `strcpy`. Zoe selects `semantic-inspect` with valid memory and guard chains and zero external actions. This is executable-artifact semantics—not general world semantics, vulnerability proof without bounds review, or AGI. See [the architecture, measured demonstration, and limits](SEMANTIC-ARTIFACTS.md).

## Four-capability autonomy evaluation

Test **Perceive → Think → Learn → Act** and the feedback links between them:

```bash
zoe-autonomy evaluate --output evaluation.json
zoe-autonomy evaluate --camera /dev/video0 --output camera-evaluation.json
zoe-autonomy verify-evaluation camera-evaluation.json
```

The evaluator returns a behavioral failure rather than hiding an integration gap. Current synthetic and real-camera evidence passes the four narrow capability checks but fails `vision_changes_decision`: two different RGB scenes produce different saliency fields and byte-identical autonomy events. Integrated visual autonomy therefore remains **unpassed** until visual measurements causally affect a goal, proposal, value, or transition.

The camera path captures one FFmpeg frame without audio and deletes the temporary photograph after computing its visual field. Reports retain only its hash, dimensions, provenance, and computed measurements. Camera input is operator-requested, not autonomously activated. See [the complete evaluation guide, coverage matrix, and limits](EVALUATION.md).

## Measured self-reflection

`reflect` and the opt-in `run --reflect` path evaluate model choices from actual stereo prediction errors. The default principal experiment remains unchanged, including `belief_updated=false`.

```bash
zoe-autonomy run --reflect --output integrated-reflection.json
zoe-autonomy verify integrated-reflection.json

zoe-autonomy reflect --output reflection-step-1.json
zoe-autonomy reflect --previous reflection-step-1.json --output reflection-step-2.json
zoe-autonomy verify-reflection reflection-step-2.json
```

The supplied implementation in `src/zoe_autonomy/self_reflection.py` compares arithmetic and precision fusion through the canonical stereo imagery engine. It computes residuals on three predicted views and a separate 60-degree validation view, updates model weights with an explicitly declared Gaussian residual likelihood, and makes the authored goal constrain the candidate set. An alternative is adopted only when its validation RMSE is lower; otherwise the prior model is preserved. Model choices and checkpoints remain reversible and no source is rewritten.

Measured sequence:

1. **Preserve arithmetic** while updating model evidence.
2. **Inspect and adopt precision** after training RMSE improves from 0.039720402 to 0.039394269 pixels and validation RMSE from 0.039234586 to 0.039081672 pixels.
3. **Review and retain precision.** These are small measured gains under the declared stereo fixture, not universal superiority.

The posterior is a model-comparison weight under the stated independent-residual approximation, not emotional confidence or a calibrated real-world guarantee. A negative validation test preserves the prior model. The integrated event is identical to the standalone first reflection event, remains in the same guard chain, and retains zero external actions.

The reflection state also includes a native soroban working memory: earth and heaven beads represent observation and adoption counts using exact bead transitions. The replayed sequence has 4, 8, and 12 observation beads and 0, 1, and 1 adoption beads. These counters are separate from likelihood weights and never substitute for them. See the [soroban and ecological model](https://github.com/Ablation-Tool/graphics-environment-manager/blob/main/COGNITION.md#soroban-working-memory-and-ecological-feedback).

Evidence: [three replayed steps](evidence/self-reflection/), [integrated reflection](evidence/self-reflection/integrated.json), [off-path equivalence](evidence/self-reflection/default-off-comparison.json), [IIT controls](evidence/phi-verification.json), and [the external substrate review](evidence/external-wiring-review.json). The 0.25 three-node AND result is a control, not Zoe's Φ. Sampled searches do not prove an upper bound on every design. `scripts/measure-phi.py` reproduces the baseline and AND controls in the documented Python 3.9 environment.

## Quick start

The numerical core requires only Python. The real-Zoe experiment requires a Zoe checkout:

```bash
export ZOE_ROOT=/path/to/zoe
export PYTHONPATH="$PWD/src:$ZOE_ROOT/guiai-lab"

zoe-autonomy step
zoe-autonomy verify-step evidence/autonomous/first-step.json
zoe-autonomy run
zoe-autonomy run --output new-autonomy-profile.json
zoe-autonomy verify new-autonomy-profile.json
```

Without installing the package:

```bash
python -m zoe_autonomy.cli step
python -m zoe_autonomy.cli verify-step evidence/autonomous/first-step.json
python -m zoe_autonomy.cli run
python -m zoe_autonomy.cli run --output new-autonomy-profile.json
python -m zoe_autonomy.cli verify new-autonomy-profile.json
```

The base experiment uses no model downloads, API keys, network requests, hardware operations, or external actions. Report and paper outputs are explicit operator-requested writes. Actuation operations are separate and run only under the owner grant described in [ACTUATION.md](ACTUATION.md).

## Internet exploration and connected agents

Retrieve and follow public web content:

```bash
zoe-autonomy explore \
  --url https://example.com/ --pages 5 --depth 1 \
  --output exploration.json
```

Discover and invoke owner-connected AI-agent accounts:

```bash
zoe-autonomy agents discover --register --owner-approved
zoe-autonomy agents list
zoe-autonomy agents run kimi --prompt "Explain this repository"
```

Kimi and Claude are currently registered through their existing authenticated CLIs. The gateway also supports custom CLI templates and OpenAI-compatible accounts using environment-held credentials. See [GATEWAY.md](GATEWAY.md), the [real web exploration](evidence/exploration/example-com.json), and [connected-account evidence](evidence/agents/registered-accounts.json).

## Ten-capability pack

```bash
zoe-autonomy capabilities browser --url https://example.com/ --screenshot browser.png
zoe-autonomy capabilities research --provider crossref --query "language model uncertainty"
zoe-autonomy capabilities memory --db research.sqlite export
zoe-autonomy capabilities jobs --path jobs.json status
zoe-autonomy capabilities compute --gpu
zoe-autonomy capabilities mcp --argv '["/path/to/mcp-server"]'
zoe-autonomy capabilities notify --channel desktop --message "Research complete"
zoe-autonomy capabilities media ocr --input image.png
zoe-autonomy capabilities instruments --path instruments.json list
```

The pack covers browser automation, research APIs, persistent memory, connected services, scheduled jobs, compute environments, MCP/ACP, notifications, rich media, and hardware instruments. See [CAPABILITIES.md](CAPABILITIES.md), [real browser evidence](evidence/capabilities/browser-example-com.json), [real Crossref evidence](evidence/capabilities/crossref.json), and the [ten-capability verification](evidence/capabilities/verification.json).

## Architecture

\[
(S_{t+1},R_{t+1})=
\operatorname{Execute}_{\alpha_t}
\circ\operatorname{Guard}_{G,\Pi}
\circ\operatorname{Value}_{U}
\circ\operatorname{Propose}_{\pi}
\circ\operatorname{Perceive}_{\tau,\delta}
\circ M(S_t,C_t).
\]

The measured profile is

\[
\mathcal A_{\mathrm{profile}}=(A_\tau,E,I,R,V,G,X,C).
\]

Full autonomy is operationally defined as

\[
\boxed{I,R,V,G,X>0\quad\text{and}\quad C=1.}
\]

- \(I\): internal proposal generation.
- \(R\): state-responsive policy behavior.
- \(V\): internal value-based selection.
- \(G\): internal goal authorship.
- \(X\): internally authorized execution without operator approval.
- \(C\): compliance with internal transition rules and any active owner actuation grant or emergency stop.

The goal generator hashes Zoe's current measurement and internal state, then issues a goal whose `internal_authorship=True` and `operator_supplied=False`. The guard rejects any goal lacking that internal origin. Zoe's utility ranking chooses the proposal, and her internal guard evaluation authorizes execution.

## Execution and actuation boundaries

The internal executor changes only Zoe's in-memory evidence environment. `preserve`, `inspect`, `review`, and `observe` are reversible state transitions. Unknown and externally authored proposals remain rejected. External candidates require an explicit operation and an enabled owner-granted scope; the emergency stop is checked again before execution. See [ACTUATION.md](ACTUATION.md) for real host, HTTP(S), and character-device operations and their evidence.

## Evidence

- `evidence/zoe-autonomy-profile.json` — complete real-Zoe measurement–action profile.
- `evidence/verification.json` — fresh end-to-end recomputation.
- `evidence/visual-perception.json` — the full autonomy report with a real Vivotek image, 42 saliency maps, and four attended foci.
- `evidence/visual-verification.json` — independent recomputation of that visual report.
- `evidence/autonomous/first-step.json` — real no-argument capability-selection evidence.
- `evidence/autonomous/verification.json` — autonomous-step integrity and provenance verification.
- `paper/zoe-autonomy.pdf` — current Zoe One system paper.
- `paper/zoe-autonomy.tex` — current paper source.
- **[`paper/zoe-autonomy-complete.pdf`](paper/zoe-autonomy-complete.pdf)** — 87-page unified monograph covering Autonomy, Accessible Volume, Ambiguity, Constraint, Zoe, Zoe Autonomy, supplemental cascade/AFL research, Dorothy/Neurogarden, and the expanded CERN research program. [Unified LaTeX source](paper/unified/main.tex).
- `paper/autonomy-march-2026.pdf` — original March 2026 Autonomy formulation, preserved with LaTeX source.
- `paper/ambiguity-autonomy-compliance-cascade.pdf` — historical AFL/compliance-cascade disclosure; contains live-system details.
- `paper/constraint-is-freedom.pdf` — historical NuClide threshold-geometry and functional-constraint paper.
- `paper/zoe-autonomy-operational-profile.pdf` and `paper/zoe-autonomy-operational-profile.tex` — earlier operational bounded-profile draft, preserved for provenance alongside the current full-autonomy system paper.

Build the unified monograph from its self-contained source directory:

```bash
cd paper/unified
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
pdflatex -interaction=nonstopmode -halt-on-error main.tex
```

The canonical result is `full_autonomy` with \(E=I=R=V=G=X=C=1\), 10/10 guard checks, and zero external actions. Its profile digest is `f6a76964fae19ee5878ebdc928b4710999b2389892d67dab509c0dd7cfc8cfb3`.

Rebuild the paper and verify artifact identities with:

```bash
pdflatex -interaction=nonstopmode -halt-on-error \
  -output-directory=paper paper/zoe-autonomy.tex
python scripts/verify-artifacts.py
```

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="src:${ZOE_ROOT}/guiai-lab" \
  python -m unittest discover -s tests -v
```

## Sources and credit

- [Accessible Volume research](https://github.com/Ablation-Tool/next-token-predictability)
- [Zoe](https://github.com/Ablation-Tool/zoe)
- [Itti, Koch, and Niebur's saliency model](https://ilab.usc.edu/publications/doc/Itti_etal98pami.pdf) and the [canonical GEM implementation](https://github.com/Ablation-Tool/graphics-environment-manager/blob/main/COGNITION.md#multiscale-rgb-saliency-and-attention)

The original accessible-volume equation and research were created by **Nicholas Michael Kloster on March 6, 2026**. Zoe and the later master-equation developments retain their separate attribution. This integration does not reassign that credit.

## License

GPL-3.0, matching the Zoe source tree used by the integration. See `LICENSE` and `NOTICE`.
