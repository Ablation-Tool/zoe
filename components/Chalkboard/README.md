# Chalkboard

Chalkboard is a collection of ideas, templates, and prompts. It is a scratchpad repository, not a product: reusable material that other projects and people can copy, adapt, and keep.

Chalkboard's original templates and prompts are free for anyone to take and use themselves. No attribution is required for that original material. Included Zoe components retain their own licenses and notices.

## Zoe · allgems

**Zoe is the GEM, but the GEM is not Zoe. Zoe is allgems.** The complete Zoe component is included in `zoe/`: its native Cognitive Field, Bayesian memory, geometry, replayable knowledge graph, unified hub, and the other GEM source trees. Chalkboard supplies its templates and prompts as the host content library, so `components/Chalkboard` is not duplicated. The imported Zoe revision is recorded in `zoe/ZOE-SOURCE.json`.

Install and inspect the unified hub:

```bash
python -m pip install ./zoe/guiai-lab
export ZOE_ROOT="$PWD/zoe"
export ZOE_CHALKBOARD_ROOT="$PWD"
zoe
zoe list
zoe show chalkboard
```

`zoe show chalkboard` inspects this checkout without starting a process. Chalkboard remains a content library, not a GUI or an AI agent. Other component launches are explicit. Newly generated unified evidence is not included in the import. See [Zoe's architecture and verification guide](zoe/guiai-lab/docs/UNIFIED.md) and the [native hub screenshot](zoe/guiai-lab/docs/images/gem-unified-native.png).

---

## Contents

<details>
<summary>Templates</summary>

**Templates**

Ready-to-use file templates. Copy the file into your own repository and replace the placeholders.

| Template | Path | Description |
|:---|:---|:---|
| [Streamlined README](templates/README.template.md) | [1](templates/README.template.md) | The Ablation-style README layout: collapsible categories, capability tables linked to implementation files, plain language, no banners or shields. |

</details>

<details>
<summary>Ideas & Prompts</summary>

**Ideas & Prompts**

Reusable prompts for directing AI agents. Copy the prompt into your own workflow and fill in the placeholders.

| Prompt | Path | Description |
|:---|:---|:---|
| [Software Capabilities Audit](prompts/software-capabilities-audit.md) | [1](prompts/software-capabilities-audit.md) | Directs an AI agent to reverse-engineer an unknown tool purely from code and behavior: infer its purpose, catalog real capabilities, verify docs against reality, and report gaps, risks, and next steps. |

</details>

## Setup & About

<details>
<summary>How to Use</summary>

1. Open the item you want.
2. Copy it into your own repository.
3. Replace the placeholders and delete the sections you do not need.

No installation, no dependencies, no attribution required.

</details>

<details>
<summary>Responsible Use & Contact</summary>

Material here is provided as-is. Review anything you copy before publishing or running it.

Report bugs or suggest additions through [GitHub Issues](https://github.com/Ablation-Tool/Chalkboard/issues).

</details>
