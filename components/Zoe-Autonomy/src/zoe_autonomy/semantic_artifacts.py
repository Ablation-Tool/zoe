from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

from .event_memory import KeyValueEventMemory
from .experiment import _source_identity, _zoe_root
from .loop import BoundedAutonomyLoop, Candidate, SandboxPolicy, digest

INSTRUMENT = "zoe-semantic-artifact-evaluation/v1"
DEFAULT_QUERY = "function that copies an unbounded string from external input into a fixed-size stack buffer without checking its length"
DANGEROUS_APIS = {
    "strcpy", "strcat", "sprintf", "vsprintf", "gets", "system", "popen",
    "execl", "execlp", "execle", "execv", "execvp", "execvpe", "popen",
}
MEMORY_APIS = {"memcpy", "memmove", "memset", "bcopy"}


def _ablation_root(path=None):
    value = path or os.environ.get("ABLATION_ROOT") or "/home/cowboy/_projects/ablation"
    root = Path(value).expanduser().resolve()
    if not (root / "ablation/analyzers/semantic_search.py").is_file():
        raise ValueError(f"Ablation source checkout is incomplete: {root}")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _git_revision(root):
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, timeout=10,
    ).stdout.strip()


def _direct_evidence(ctx, artifact):
    import capstone
    import lief

    binary = lief.parse(str(artifact))
    text = binary.get_section(".text")
    if text is None:
        raise ValueError("artifact has no .text section")
    architecture = {
        "x86_64": (capstone.CS_ARCH_X86, capstone.CS_MODE_64),
        "x86_32": (capstone.CS_ARCH_X86, capstone.CS_MODE_32),
        "arm64": (capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM),
        "arm32": (capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM),
    }.get(ctx.arch)
    if architecture is None:
        return {}, "disassembly evidence is not implemented for this architecture"
    engine = capstone.Cs(*architecture)
    engine.detail = True
    starts = sorted({int(va) for va in ctx.func_starts if text.virtual_address <= va < text.virtual_address + text.size})
    names = ctx.names_map()
    evidence = {}
    for index, start in enumerate(starts):
        stop = starts[index + 1] if index + 1 < len(starts) else text.virtual_address + text.size
        offset = start - text.virtual_address
        code = bytes(text.content)[offset:stop - text.virtual_address]
        calls = []
        for instruction in engine.disasm(code, start):
            if instruction.mnemonic not in {"call", "jmp", "bl", "b", "blx", "bx"}:
                continue
            if not instruction.operands:
                continue
            target = int(instruction.operands[0].imm)
            if target in ctx.plt:
                calls.append({"target_va": target, "target": ctx.plt[target], "instruction": instruction.mnemonic})
        for target, label in ctx.callees_of(start):
            calls.append({"target_va": target, "target": label, "instruction": "call"})
        unique = {(item["target_va"], item["target"], item["instruction"]): item for item in calls}
        evidence[start] = {
            "va": start,
            "name": names.get(start, ctx.name(start)),
            "direct_calls": sorted(unique.values(), key=lambda item: (item["target_va"], item["instruction"])),
            "dangerous_calls": [
                item for item in unique.values()
                if item["target"].split("@")[0].lower() in DANGEROUS_APIS | MEMORY_APIS
            ],
        }
    return evidence, None


def _semantic_graph(artifact_sha, candidates, direct):
    nodes = [{"id": f"artifact:{artifact_sha}", "type": "artifact", "sha256": artifact_sha}]
    edges = []
    for candidate in candidates:
        va = candidate["va"]
        function_id = f"function:{va:x}"
        nodes.append({"id": function_id, "type": "function", "name": candidate["name"], "semantic_score": candidate["score"]})
        edges.append({"from": f"artifact:{artifact_sha}", "to": function_id, "relation": "contains"})
        for call in direct.get(va, {}).get("direct_calls", []):
            target_id = f"api:{call['target']}"
            nodes.append({"id": target_id, "type": "api", "name": call["target"]})
            edges.append({"from": function_id, "to": target_id, "relation": call["instruction"]})
            if call in direct[va]["dangerous_calls"]:
                edges.append({"from": function_id, "to": target_id, "relation": "requires_bounds_review"})
    return {"nodes": nodes, "edges": edges}


def _cognitive_document(root, direct):
    from guiai.gem.cognitive import CognitiveField

    field = CognitiveField(working_capacity=4)
    dangerous = [(va, item) for va, item in direct.items() if item["dangerous_calls"]]
    if dangerous:
        va, evidence = dangerous[0]
        calls = ", ".join(call["target"] for call in evidence["dangerous_calls"])
        representation = field.encode(
            f"Function 0x{va:x} directly reaches {calls}; this requires bounds review, not an assumption of safe behavior.",
            "Ablation disassembly evidence", ["artifact", "review", "unsafe_call"],
        )
        field.store_active(representation["id"])
        retrieval = field.retrieve("d-1", 1)
        field.add_rule("Review direct unsafe calls", ["artifact", "review"], "Inspect direct unsafe calls before accepting a semantic match.")
        match = field.match_rules()
        proposal = field.propose_performance(match["id"], "Use disassembly evidence to guide the next reversible inspection.")
        return field.document(), {"retrieval": retrieval, "proposal": proposal}
    representation = field.encode("No direct dangerous API call is present in the analyzed scope.", "Ablation disassembly evidence", ["artifact", "review"])
    field.store_active(representation["id"])
    return field.document(), {"retrieval": field.retrieve("d-1", 1)}


def _finding_memory(state_root, direct, artifact_sha, model):
    from ablation.analyzers.finding_registry import FindingRegistry

    registry = FindingRegistry(state_root / "findings.db")
    registry.build_embeddings(model)
    dangerous = [(va, item) for va, item in direct.items() if item["dangerous_calls"]]
    if not dangerous:
        return {"registered": False, "reason": "No direct dangerous API call was found"}
    va, evidence = dangerous[0]
    description = (
        f"Function 0x{va:x} directly reaches "
        + ", ".join(call["target"] for call in evidence["dangerous_calls"])
        + ". Candidate unsafe behavior requires bounds and reachability review."
    )
    vector = next(model.embed([description]))
    identifier = registry.register(
        vendor="zoe-local",
        product="semantic-artifact",
        title=f"Direct unsafe API call at 0x{va:x}",
        description=description,
        cwe_class="CWE-120",
        severity="HIGH",
        embedding=vector,
        func_addr=va,
        binary=artifact_sha,
        source="zoe-semantic-artifact-evaluation",
        confirmed=False,
    )
    similar = registry.find_similar(vector, top_k=5, min_sim=.70)
    return {
        "registered": True,
        "id": identifier,
        "confirmed": False,
        "description": description,
        "similar_findings": similar,
        "scope": "Candidate unsafe behavior is preserved for later review, not declared a confirmed vulnerability",
    }


def analyze_artifact(zoe_root, artifact_path, query=DEFAULT_QUERY, state_root=None, ablation_root=None):
    root = _zoe_root(zoe_root)
    ablation = _ablation_root(ablation_root)
    artifact = Path(artifact_path).expanduser().resolve(strict=True)
    if artifact.stat().st_size > 64 * 1024 * 1024:
        raise ValueError("artifact exceeds the 64 MiB analysis limit")
    if not isinstance(query, str) or not query.strip() or len(query) > 2000:
        raise ValueError("semantic query must contain 1-2000 characters")
    from fastembed import TextEmbedding
    from ablation.analyzers.binary_context import BinaryContext
    from ablation.analyzers.knowledge_graph import KnowledgeGraph
    from ablation.analyzers.semantic_search import SemanticSearcher

    ctx = BinaryContext.load_or_build(str(artifact), force_rebuild=True)
    existing = ctx.names_map()
    missing = {va: (f"func_{va:x}", "function-start-analysis") for va in ctx.func_starts if va not in existing}
    if missing:
        ctx.set_names_bulk(missing)
    direct, evidence_error = _direct_evidence(ctx, artifact)
    searcher = SemanticSearcher.from_context(ctx)
    live = set(direct)
    searcher.build_corpus(live_addrs=live, force=True)
    matches = [dict(vars(result)) for result in searcher.query(query, top_k=5)]
    for match in matches:
        match["direct_evidence"] = direct.get(match["va"], {})
    state = Path(state_root).expanduser().resolve() if state_root else Path.cwd() / ".zoe" / "semantic-artifacts"
    state.mkdir(parents=True, exist_ok=True)
    model = TextEmbedding("BAAI/bge-small-en-v1.5")
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    graph = _semantic_graph(artifact_sha, matches, direct)
    dangerous = [item for item in direct.values() if item["dangerous_calls"]]
    scores = [match["score"] for match in matches]
    support = {
        "corpus_size": len(searcher._meta),
        "score_spread": max(scores) - min(scores) if scores else 0.0,
        "limited_support": len(searcher._meta) < 8,
        "direct_evidence_functions": len(dangerous),
        "automatic_vulnerability_claim": False,
        "scope": "Semantic similarity is advisory; direct calls require separate bounds and reachability review",
    }
    proposals = []
    for action, value, information, effort, rationale in (
        ("inspect", .95 if dangerous else .55, .9, .5, "Inspect direct disassembly evidence and the semantic candidate graph."),
        ("preserve", .75 if dangerous else .5, .8, .7, "Preserve the candidate evidence with explicit uncertainty and no vulnerability declaration."),
        ("review", .65, .75, .6, "Review tool history and independent uncertainty before choosing the next analysis."),
        ("abstain", .99 if not matches else .05, 1.0, 1.0, "Abstain when no semantic candidates or direct evidence are available."),
    ):
        proposals.append(Candidate(f"semantic-{action}", action, value, information, effort, rationale))
    loop = BoundedAutonomyLoop(policy=SandboxPolicy(allowed_actions=("inspect", "preserve", "review", "abstain")))
    measurement = {
        "instrument": INSTRUMENT,
        "artifact_sha256": artifact_sha,
        "query": query,
        "semantic_support": support,
        "direct_evidence_functions": len(dangerous),
    }
    perception = {
        "domain": "executable artifact semantics",
        "semantic_retrieval": "normalized behavior embeddings plus direct disassembly evidence",
        "general_world_semantics_claimed": False,
    }
    event = loop.run(measurement, perception, proposals)
    memory = KeyValueEventMemory(state / "event-memory")
    memory.add_episode(
        [match["score"] for match in matches] or [0.0],
        event["value"]["selected_candidate"],
        {"semantic_support": support, "direct_evidence": dangerous, "artifact_sha256": artifact_sha},
        {"domain": "executable artifact semantics"},
    )
    cognitive, cognitive_evidence = _cognitive_document(root, direct)
    graph_db = KnowledgeGraph.open()
    knowledge_context = graph_db.get_context_for_binary(ctx.arch, "elf")
    recommendations = graph_db.get_recommendations_for_task(query, arch=ctx.arch)
    graph_db.close()
    finding = _finding_memory(state, direct, artifact_sha, model)
    checks = {
        "semantic_retrieval_executed": bool(matches),
        "live_scope_excludes_plt": all(item["va"] not in ctx.plt for item in searcher._meta),
        "direct_disassembly_evidence_present": bool(direct) and evidence_error is None,
        "autonomous_goal_and_guard": event["goal"]["internal_authorship"] and event["guard"]["approved"] and event["execution"]["executed"],
        "memory_chain_valid": memory._chain_valid(),
        "uncertainty_preserved": support["automatic_vulnerability_claim"] is False,
        "external_actions_zero": loop.external_actions == 0,
    }
    report = {
        "schema_version": 1,
        "instrument": INSTRUMENT,
        "zoe_source": _source_identity(root),
        "ablation_source": {
            "revision": _git_revision(ablation),
            "semantic_search_sha256": hashlib.sha256((ablation / "ablation/analyzers/semantic_search.py").read_bytes()).hexdigest(),
        },
        "artifact": {"path": str(artifact), "sha256": artifact_sha, "arch": ctx.arch, "function_starts": len(ctx.func_starts)},
        "query": query,
        "semantic_support": support,
        "semantic_matches": matches,
        "direct_evidence": direct,
        "semantic_graph": graph,
        "autonomy_event": event,
        "cognitive_memory": cognitive,
        "cognitive_evidence": cognitive_evidence,
        "event_memory": memory.document(),
        "knowledge_context": knowledge_context,
        "knowledge_recommendations": recommendations,
        "finding_memory": finding,
        "checks": checks,
        "overall": {"passed": all(checks.values()), "failed_checks": [name for name, passed in checks.items() if not passed]},
        "scope": [
            "This demonstrates executable-artifact semantics, retrieval, direct call evidence, memory, and guarded reasoning, not general world semantics or AGI.",
            "Semantic scores are retrieval evidence, not vulnerability proof or calibrated confidence.",
            "No target function or vulnerable input is executed by this analysis.",
        ],
    }
    report["evaluation_sha256"] = digest(report)
    return report


def save_semantic_report(report, output):
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported semantic-artifact report")
    if digest({key: value for key, value in report.items() if key != "evaluation_sha256"}) != report.get("evaluation_sha256"):
        raise ValueError("semantic-artifact report digest mismatch")
    path = Path(output).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("semantic-artifact reports must use .json paths")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def verify_semantic_report(report_or_path):
    if isinstance(report_or_path, (str, os.PathLike)):
        path = Path(report_or_path).expanduser().resolve(strict=True)
        if path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError("semantic-artifact report exceeds 64 MiB")
        report = json.loads(path.read_text(encoding="utf-8"))
    else:
        report = report_or_path
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported semantic-artifact report")
    if digest({key: value for key, value in report.items() if key != "evaluation_sha256"}) != report.get("evaluation_sha256"):
        raise ValueError("semantic-artifact report digest mismatch")
    expected = all(report["checks"].values())
    if report["overall"]["passed"] != expected:
        raise ValueError("semantic-artifact overall result is inconsistent")
    return {
        "verified": True,
        "instrument": INSTRUMENT,
        "evaluation_sha256": report["evaluation_sha256"],
        "passed": expected,
        "failed_checks": deepcopy(report["overall"]["failed_checks"]),
        "verification_scope": "Saved-report integrity and result consistency, not a fresh binary analysis",
    }


def semantic_summary(report):
    matches = report["semantic_matches"]
    first = matches[0] if matches else None
    lines = [
        f"Semantic artifact evaluation: {'PASS' if report['overall']['passed'] else 'FAIL'}",
        f"Artifact: {report['artifact']['path']} · {report['artifact']['arch']} · {report['semantic_support']['corpus_size']} scoped functions",
        f"Direct evidence functions: {report['semantic_support']['direct_evidence_functions']} · limited_support={report['semantic_support']['limited_support']}",
        f"Selected action: {report['autonomy_event']['value']['selected_candidate']} · external actions=0",
    ]
    if first:
        lines.append(f"Top retrieval: 0x{first['va']:x} {first['name']} · score={first['score']:.6f} · not vulnerability proof")
    if report["overall"]["failed_checks"]:
        lines.append("Failed checks: " + ", ".join(report["overall"]["failed_checks"]))
    return "\n".join(lines)
