# Semantic artifact analysis with Ablation and Zoe

`semantic-evaluate` adds an executable-artifact domain to Zoe's shared perception–reasoning–memory–action architecture. It uses Ablation's behavioral embeddings, normalized opcode categories, binary context, knowledge graph, and finding registry alongside Zoe's Cognitive Field, event memory, guard, and evidence chain.

This is **semantic analysis of executable artifacts**, not general world semantics, natural-language understanding across domains, or AGI. The demonstrated task is to inspect behavior and unsafe call structure in a binary without executing it.

## Run

```bash
export ZOE_ROOT=/path/to/zoe
export ABLATION_ROOT=/path/to/canonical-ablation
export PYTHONPATH="$PWD/src:$ZOE_ROOT/guiai-lab:$ABLATION_ROOT"

zoe-autonomy semantic-evaluate \
  --artifact /path/to/stripped-binary \
  --query "function that copies an unbounded string from external input into a fixed-size stack buffer without checking its length" \
  --state /path/to/semantic-state \
  --output semantic-artifact.json

zoe-autonomy verify-semantic-evaluation semantic-artifact.json
```

The command uses `BAAI/bge-small-en-v1.5` through the existing Ablation `fastembed` dependency. If the model is not cached, the first run retrieves the public model. No alternate embedding model is silently substituted. Set `ABLATION_ROOT` explicitly to avoid accidentally importing a different Ablation checkout.

## What is composed

1. **Ablation retrieval:** `BinaryContext` discovers functions, `SemanticSearcher` normalizes behavioral text, and BGE embeddings rank candidates.
2. **Direct disassembly:** Capstone inspects calls and tail jumps in the `.text` section. PLT entries are excluded from the corpus scope. Direct API calls are evidence for review, not automatic vulnerability proof.
3. **Independent support:** the report records corpus size, score spread, limited support, and `automatic_vulnerability_claim=false`.
4. **Zoe reasoning:** internally authored goals and utility-ranked `inspect`, `preserve`, `review`, and `abstain` candidates pass the existing guard and internal executor.
5. **Cognitive memory:** Zoe's Cognitive Field stores and retrieves artifact concepts and procedural review rules. Event memory preserves causal transitions with hash-chained episodes.
6. **Ablation knowledge:** the knowledge graph supplies architecture-specific tools, gaps, and prior analysis history. The finding registry preserves candidate unsafe behavior as `confirmed=false`, not as a declared vulnerability.

## Measured demonstration

The fixture compiles the same source with `gcc -O0 -g` and `gcc -O2 -s`. It contains `copy_payload`, `parse_header`, and `safe_length`; no vulnerable input or target function is executed.

The unstripped query ranks `copy_payload` first. The stripped query initially exposes a PLT false positive. After scope filtering and whitening, the remaining corpus is correctly limited to `.text`, but the small corpus produces nearly zero scores and ranks `safe_length` first. The report explicitly records `limited_support=true` rather than treating that ranking as useful proof.

Direct disassembly independently finds `func_11c0` performing a tail jump to `strcpy@plt`. Zoe's selected action is `semantic-inspect`, with zero external actions and valid event-memory and autonomy guard chains. The semantic graph records the `jmp` to `strcpy`, and the finding registry preserves the behavior for later bounds and reachability review.

This is the intended behavior: **retrieval proposes, direct evidence guides, uncertainty remains visible, and the guard decides.**

## Ablation fixes included

The canonical Ablation checkout now also fixes and tests two pre-existing semantic-search issues:

- `live_addrs` filtering applies after either SQL branch, including when `binary_id` is set.
- PCA whitening applies to both corpus and query vectors, and its parameters are preserved in corpus caches.

The tests also cover cache parameters, query transformation, and scoped retrieval. Runtime verification uses the canonical checkout at `/home/cowboy/_projects/ablation`, not the separate `/home/cowboy/ablation` working tree.

## Limits

- Semantic scores are retrieval evidence, not calibrated confidence or proof of functional equivalence.
- Small corpora can be uninformative. Direct call evidence is necessary but insufficient for a vulnerability conclusion.
- `strcpy`, `system`, `memcpy`, and similar APIs require context, bounds, and attacker-reachability analysis. Their presence alone is not a confirmed vulnerability.
- Current direct disassembly evidence covers the declared x86/x86-64 path. Other architectures require separately validated decoders.
- This does not establish language understanding, general abstraction, social perception, creativity, open-ended reasoning, or AGI.

Evidence: [`evidence/semantic-artifacts/evaluation.json`](evidence/semantic-artifacts/evaluation.json) and `tests/test_semantic_artifacts.py`.
