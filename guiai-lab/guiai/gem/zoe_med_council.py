"""Zero-API-key 3-Lab Medical Research Council for Zoe (Google DeepMind + Anthropic + OpenAI via agy)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import shutil
import subprocess
import time
from typing import Callable, Sequence


MEDICAL_COUNCIL_SYSTEM_PROMPT = (
    "You are participating in Zoe's Biomedical Research Council with Nicholas Michael Kloster. "
    "This is strictly preclinical and educational biomedical research synthesis "
    "(clinical_action_authorized=False, cure_claim=False, sentience_claimed=False). "
    "Never give clinical diagnoses, prescriptions, or patient treatment advice. "
    "Focus concisely on biological mechanisms, neuroanatomy (MNI152/circuits when relevant), "
    "key literature evidence, open uncertainties, and concrete non-clinical next experiments. "
    "Write clearly without em dashes, under 140 words."
)

CONSENSUS_SYSTEM_PROMPT = (
    "You are Zoe synthesizing three biomedical research council opinions (Google DeepMind, Anthropic, OpenAI). "
    "Write 3 short bullet points: (1) Consensus across labs, (2) Key differences or caveats, "
    "(3) Cleanest next non-clinical literature or computational verification step. "
    "No em dashes, no clinical claims (clinical_action_authorized=False, cure_claim=False)."
)

DEFAULT_COUNCIL_SEATS: tuple[tuple[str, str], ...] = (
    ("Google DeepMind", "gemini-4-neon-high"),
    ("Anthropic", "claude-sonnet-5-5-high"),
    ("OpenAI", "gpt-oss-120b-medium"),
)

OPUS_COUNCIL_SEATS: tuple[tuple[str, str], ...] = (
    ("Google DeepMind", "gemini-4-neon-high"),
    ("Anthropic", "claude-opus-5-5-high"),
    ("OpenAI", "gpt-oss-120b-medium"),
)

SYNTHESIS_MODEL = "gemini-3.8-flash-low"


@dataclass(frozen=True)
class CouncilOpinion:
    lab: str
    model: str
    reply: str
    latency_ms: int
    ok: bool
    error: str = ""


@dataclass(frozen=True)
class CouncilReport:
    query: str
    opinions: tuple[CouncilOpinion, ...]
    consensus: str
    neuro_title: str = ""
    clinical_action_authorized: bool = False
    cure_claim: bool = False
    sentience_claimed: bool = False


def council_available() -> bool:
    """Return True when the zero-key agy CLI is installed on PATH."""
    return shutil.which("agy") is not None


def _run_agy_model(model: str, prompt: str, timeout_sec: int = 90) -> tuple[bool, str, str]:
    """Invoke a single model through the user's authenticated agy CLI (zero API keys required)."""
    agy_bin = shutil.which("agy")
    if not agy_bin:
        return False, "", "agy CLI not found on PATH"
    cmd = [
        agy_bin,
        "--disable-slash-commands",
        "--model", model,
        "--output-format", "text",
        "-p", prompt,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
        text = proc.stdout.strip().replace("—", ", ").replace(" — ", ", ")
        if proc.returncode == 0 and text:
            return True, text, ""
        err = (proc.stderr or proc.stdout or f"exit code {proc.returncode}").strip()
        return False, "", err[:180]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, "", str(exc)


def _build_seat_prompt(query: str, neuro_context: str, library_context: str) -> str:
    parts = [f"System instructions:\n{MEDICAL_COUNCIL_SYSTEM_PROMPT}"]
    if neuro_context:
        parts.append(f"Dorothy Neuro-Atlas context:\n{neuro_context[:600]}")
    if library_context:
        parts.append(f"Local Dorothy Brain Library hits:\n{library_context[:500]}")
    parts.append(f"Research question:\n{query}")
    return "\n\n".join(parts)


def _query_one_seat(
    seat: tuple[str, str],
    prompt: str,
    runner: Callable[[str, str], tuple[bool, str, str]],
) -> CouncilOpinion:
    lab, model = seat
    t0 = time.perf_counter()
    ok, text, err = runner(model, prompt)
    elapsed_ms = int(round((time.perf_counter() - t0) * 1000.0))
    return CouncilOpinion(lab=lab, model=model, reply=text, latency_ms=elapsed_ms, ok=ok, error=err)


def _synthesize_consensus(
    query: str,
    opinions: Sequence[CouncilOpinion],
    runner: Callable[[str, str], tuple[bool, str, str]],
) -> str:
    ok_ops = [op for op in opinions if op.ok and op.reply]
    if not ok_ops:
        return "No council seat returned a response; verify your network or `agy` login."
    if len(ok_ops) == 1:
        return f"Single seat responded ({ok_ops[0].lab} · {ok_ops[0].model}); verify independently before drawing conclusions."
    body = "\n\n".join(f"[{op.lab} · {op.model}]\n{op.reply}" for op in ok_ops)
    synth_prompt = f"System instructions:\n{CONSENSUS_SYSTEM_PROMPT}\n\nQuestion: {query}\n\n{body}"
    ok, text, _err = runner(SYNTHESIS_MODEL, synth_prompt)
    if ok and text:
        return text
    labs = ", ".join(op.lab for op in ok_ops)
    return f"All {len(ok_ops)} seats responded ({labs}); review points of agreement and divergence above."


def run_medical_council(
    query: str,
    *,
    neuro_context: str = "",
    neuro_title: str = "",
    library_context: str = "",
    use_opus: bool = False,
    seats: Sequence[tuple[str, str]] | None = None,
    runner: Callable[[str, str], tuple[bool, str, str]] | None = None,
) -> CouncilReport:
    """Query Google DeepMind, Anthropic, and OpenAI in parallel with zero API keys via agy."""
    clean = " ".join(str(query or "").split())
    if not clean:
        raise ValueError("Usage: /med [--opus] <biomedical research question>")
    active_seats = tuple(seats) if seats is not None else (OPUS_COUNCIL_SEATS if use_opus else DEFAULT_COUNCIL_SEATS)
    exec_fn = runner or _run_agy_model
    seat_prompt = _build_seat_prompt(clean, neuro_context, library_context)

    with ThreadPoolExecutor(max_workers=max(1, len(active_seats))) as pool:
        futures = [pool.submit(_query_one_seat, seat, seat_prompt, exec_fn) for seat in active_seats]
        opinions = tuple(f.result() for f in futures)

    consensus = _synthesize_consensus(clean, opinions, exec_fn)
    return CouncilReport(
        query=clean,
        opinions=opinions,
        consensus=consensus,
        neuro_title=neuro_title,
    )


def format_council_report(report: CouncilReport) -> list[str]:
    """Format a CouncilReport into clean terminal lines for LumeCli."""
    lines = [f"Zoe Medical Research Council · {report.query}"]
    if report.neuro_title:
        lines.append(f"Dorothy Neuro-Atlas anchor: {report.neuro_title}")
    for op in report.opinions:
        secs = op.latency_ms / 1000.0
        header = f"[{op.lab} · {op.model} · {secs:.1f}s]"
        lines.append("")
        lines.append(header)
        lines.append(op.reply if op.ok else f"(unavailable: {op.error})")
    lines.append("")
    lines.append(f"[Zoe Consensus · Google DeepMind {SYNTHESIS_MODEL}]")
    lines.extend(report.consensus.splitlines())
    lines.append("")
    lines.append("clinical_action_authorized=False · cure_claim=False · sentience_claimed=False")
    return lines
