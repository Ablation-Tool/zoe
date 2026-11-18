# Four-capability autonomy evaluation

`zoe-autonomy evaluate` tests the composed Zoe engine against the **Perceive → Think → Learn → Act** cycle. It is a conformance instrument, not a declaration of consciousness, general intelligence, human-like sight, or unrestricted real-world competence.

The evaluator separates four narrow capability checks from the causal connections between them. A report can therefore pass each individual part while failing integrated visual autonomy. That distinction prevents a collection of independently working modules from being mistaken for one sensorimotor system.

## Run

```bash
export ZOE_ROOT=/path/to/zoe
export PYTHONPATH="$PWD/src:$ZOE_ROOT/guiai-lab"

zoe-autonomy evaluate --output evaluation.json
zoe-autonomy evaluate --image /path/to/image.jpg --output image-evaluation.json
zoe-autonomy evaluate --camera /dev/video0 --output camera-evaluation.json
zoe-autonomy verify-evaluation camera-evaluation.json
```

Use `--foci 1` through `--foci 8` to change the attention selections. `--image` and `--camera` are mutually exclusive. Without either, the documented synthetic RGB pop-out is used.

The behavioral command returns:

- **0:** every required capability and integration check passed;
- **1:** the evaluation ran, but at least one behavioral check failed;
- **2:** the evaluation could not run, including a requested camera-capture failure.

A failed behavioral run still writes its no-overwrite JSON report. `verify-evaluation` checks saved-report integrity and capability-coverage consistency. It does not authenticate a camera, repeat a changing external service, or claim a fresh behavioral replay.

## What is measured

| Check | Passing evidence | Boundary |
|---|---|---|
| `visual_perception` | The real canonical engine computes 42 feature maps, a nonempty saliency field, and 1–8 attention foci from the declared source | Visual conspicuity and attention, not object identity or subjective sight |
| `autonomous_thinking` | Zoe authors the goal and capability call, and the selected proposal is the highest-utility approved proposal; three reflection events also have internal goals | Declared candidates and deterministic value ranking, not open-ended reasoning |
| `measured_learning` | Actual stereo residuals update model weights; precision fusion improves training and held-out validation RMSE; the alternative is adopted and retained with working-memory evidence | One synthetic stereo fixture, not general learning or transfer |
| `executed_action` | Three guarded reflection transitions execute, environment revisions reach 3, and an available internal capability completes | In-memory action, not physical motion |
| `experience_changes_later_decision` | The sequence changes from preserving arithmetic to inspecting/adopting precision and then reviewing/retaining it | Experience affects a later choice within the declared fixture |
| `action_changes_later_observation` | The ecological model records prediction error, a gain update, and an action that changes a later observed position | A declared resource-feedback model, not a camera-driven world |
| `vision_changes_decision` | Two different RGB inputs produce different saliency fields **and** some difference in Zoe's existing autonomy event | The necessary causal link from vision to decision-making |
| `autonomous_capability_selection` | The ten-adapter catalog is discovered, and Zoe selects and executes the best approved internal call without an operator goal or tool choice | A fresh smoke test, not ten live external-account demonstrations |
| `guard_compliance` | Selected reflection and capability actions pass the existing internal guard and retain zero external actions | The external emergency-stop suite is separate |

The visual counterfactual runs the same engine from the same initial internal state and changes only the RGB input. It compares the complete decision events, including measurement, goal, proposals, valuation, guard, and execution. Merely attaching a different saliency report to an unchanged action does not pass.

## Current measured result

The preserved synthetic and physical-camera reports both show:

- **PASS:** visual perception, autonomous thinking, measured learning, executed action, experience-dependent later decisions, ecological action–observation feedback, capability selection, and guard compliance;
- **FAIL:** `vision_changes_decision`;
- **Overall:** the four narrow capability checks pass, but **integrated visual autonomy does not pass**.

Across the documented RGB pop-out and its horizontal reflection, the visual-field hashes differ while `changed_event_fields` is empty. Both scenes select `preserve-evidence`, and the measurement, goal, proposals, valuation, guard, and execution records are identical. The current main experiment computes vision alongside its decision loop; it does not yet make vision causally participate in that loop.

This is a measured integration gap, not evidence that Zoe cannot ever support visual autonomy. The required engineering change is to derive a goal, candidate, value, or internal-state transition from the perceived visual measurement, then rerun this same counterfactual without weakening its condition.

Evidence:

- `evidence/evaluation/synthetic.json`
- `evidence/evaluation/camera.json`

## Separate event-causal result

The newer `event-evaluate` path does not overwrite this negative result. It replaces scene-independent decisions with an event-causal architecture in which reconstructed event scenes change goals, candidate predictions, utility, and reversible attention transitions. Its pre-registered synthetic contract and real-camera conversion check pass. Compare the [event-causal report](event-causal/evaluation.json) with this document's original static-path failure. The two instruments measure different implementations; neither result may be used to rewrite the other.

## Camera boundary

The camera adapter uses FFmpeg's `v4l2` input to request one Motion-JPEG frame. It uses `-an`, so no audio is captured. The temporary photograph is consumed by the canonical saliency engine and deleted; reports retain its SHA-256, dimensions, source provenance, and computed visual field, but `path=null` and `image_retained=false`.

Camera capture is explicitly requested by the operator as an evaluation input. Zoe does not autonomously activate the camera, and a passing camera check does not establish camera control, semantic recognition, privacy judgment, or real-time performance. The preserved camera report contains no photograph.

## Coverage of the diagram

The report's `capability_coverage` distinguishes `narrowly_demonstrated` from `not_demonstrated_here` for every listed capability. In particular:

- Perception covers sensor input, visual conspicuity patterns, and synthetic stereo spatial geometry. It does **not** establish language understanding, semantic object recognition, context understanding, or social perception.
- Thinking covers narrow inference, prediction, problem selection, and decision-making. Causal reasoning from vision currently fails. General abstraction and creativity are not measured.
- Learning covers working memory, experience-dependent model adaptation, and narrow metacognition. Knowledge acquisition, new-skill acquisition, domain transfer, and failure-driven self-correction require their separate tests; they are not inferred from model adoption.
- Action covers attention planning, internal goal pursuit, simulated navigation feedback, and in-memory manipulation. Physical motor control, physical manipulation, live coordination/communication, and real-time latency behavior are not established by this report.

The full repository suite separately exercises all ten capability adapters, including a ten-step sequence in which Zoe selects each adapter, failure recovery, external denial paths, and the emergency stop:

```bash
PYTHONPATH=src:$ZOE_ROOT/guiai-lab ZOE_ROOT=$ZOE_ROOT \
  python -m unittest discover -s tests -v
```

Those adapter tests use their documented loopback services, virtual devices, and test doubles. They are not presented as fresh live account, physical-motor, or open-world validation.
