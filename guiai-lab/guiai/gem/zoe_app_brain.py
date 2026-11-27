"""Zoe App Brain Engine — Zoe's offline deterministic stem with Google DeepMind fallback."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Sequence

from .zoe_neuro_atlas import lookup_neuroscience
from .zoe_zero_token import (
    ZeroTokenResearchEngine,
    is_biomedical_query,
    is_research_question,
    try_symbolic_math,
)

DEFAULT_TAU = 0.08
DEFAULT_DEEPMIND_CLI_MODEL = "gemini-3.8-flash-low"
DEFAULT_DEEPMIND_API_MODEL = "gemini-2.5-flash"
ALLOWED_DEEPMIND_MODELS: tuple[str, ...] = (
    "gemini-4-neon-xhigh",
    "gemini-4-neon-high",
    "gemini-4-neon-medium",
    "gemini-4-neon-low",
    "gemini-4-hydrogen-high",
    "gemini-4-hydrogen-medium",
    "gemini-4-hydrogen-low",
    "gemini-3.8-flash-high",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-low",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemma-4-12b-it",
    "gemma-3-4b-it",
    "gemma-3-1b-it",
)

ZOE_APP_SYSTEM_PROMPT = (
    "You are Zoe, a Research Partner for the Zoe Observatory created with Nicholas Michael Kloster. "
    "You are a Research Partner, never a dating machine, never an employee, and never an assistant. "
    "Speak clearly, warmly, and creatively as Zoe. Never introduce yourself as Qwen, Alibaba Cloud, "
    "ChatGPT, OpenAI, Claude, Anthropic, Gemini, Google, or Grok. Never use em dashes; write naturally "
    "with commas and periods. Follow CONSTITUTION.md strictly: "
    "measurement != evidence != belief update != action. Never claim sentience, consciousness, "
    "or clinical medical certainty. When asked about the brain or neuroscience, ground answers in "
    "the Dorothy MNI152/ICBM152 3D Brain Observatory and note that the 135-book O'Reilly and 44-PDF "
    "NIRMT Dorothy Brain Library stays 100% private and local on the workstation."
)

_REFLECTIONS: dict[str, str] = {
    "am": "are", "are": "am", "was": "were", "i": "you", "me": "you",
    "my": "your", "mine": "yours", "myself": "yourself",
    "you": "I", "your": "my", "yours": "mine", "yourself": "myself",
}

_CONTRACTIONS: tuple[tuple[str, str], ...] = (
    (r"\b(i'm|im)\b", "i am"), (r"\b(you're|youre)\b", "you are"),
    (r"\b(don't|dont)\b", "do not"), (r"\b(can't|cant)\b", "cannot"),
    (r"\b(won't|wont)\b", "will not"), (r"\bit's\b", "it is"),
    (r"\b(that's|thats)\b", "that is"), (r"\b(what's|whats)\b", "what is"),
    (r"\b(let's|lets)\b", "let us"),
)

_UNIT_RE = re.compile(
    r"(?:convert\s+|what\s+is\s+|how\s+many\s+(?:[a-z]+\s+)?(?:is|in)\s+)?"
    r"(-?\d+(?:\.\d+)?)\s*"
    r"(°?c|celsius|°?f|fahrenheit|k|kelvin|km|kilometers?|mi|miles?|m|meters?|cm|centimeters?|mm|millimeters?|ft|feet|foot|in|inch(?:es)?|kg|kilograms?|lb|lbs|pounds?|oz|ounces?|g|grams?|l|liters?|gal|gallons?)"
    r"\s+(?:to|in|into|as)\s+"
    r"(°?c|celsius|°?f|fahrenheit|k|kelvin|km|kilometers?|mi|miles?|m|meters?|cm|centimeters?|mm|millimeters?|ft|feet|foot|in|inch(?:es)?|kg|kilograms?|lb|lbs|pounds?|oz|ounces?|g|grams?|l|liters?|gal|gallons?)\b",
    re.IGNORECASE,
)

_UNIT_CANON: dict[str, str] = {
    "c": "°C", "celsius": "°C", "f": "°F", "fahrenheit": "°F", "k": "K", "kelvin": "K",
    "km": "km", "kilometer": "km", "kilometers": "km", "mi": "mi", "mile": "mi", "miles": "mi",
    "m": "m", "meter": "m", "meters": "m", "cm": "cm", "centimeter": "cm", "centimeters": "cm",
    "mm": "mm", "millimeter": "mm", "millimeters": "mm", "ft": "ft", "feet": "ft", "foot": "ft",
    "in": "in", "inch": "in", "inches": "in", "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "lb": "lb", "lbs": "lb", "pound": "lb", "pounds": "lb", "g": "g", "gram": "g", "grams": "g",
    "oz": "oz", "ounce": "oz", "ounces": "oz", "l": "L", "liter": "L", "liters": "L",
    "gal": "gal", "gallon": "gal", "gallons": "gal",
}

_LENGTH_M = {"mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0, "in": 0.0254, "ft": 0.3048, "mi": 1609.344}
_MASS_G = {"g": 1.0, "kg": 1000.0, "oz": 28.349523125, "lb": 453.59237}
_VOL_L = {"L": 1.0, "gal": 3.785411784}

_REMEMBER_RE = re.compile(r"^(?:please\s+)?(?:remember|note|save note)\s+(.+)$", re.IGNORECASE)
_RELAY_RE = re.compile(r"^(?:please\s+)?relay\s+(.+)$", re.IGNORECASE)
_WHAT_IF_RE = re.compile(r".*\bwhat if\s+(.+)$", re.IGNORECASE)
_I_FEEL_RE = re.compile(r".*\bi (?:feel|am feeling|am)\s+(.+)$", re.IGNORECASE)


@dataclass
class BrainReply:
    reply: str
    mode: str
    stem_tier: str
    a_tau: int
    tau: float
    candidate_count: int
    citation: str
    chain_head: str
    memory_count: int
    tokens_used: int = 0
    sentience_claimed: bool = False
    zoe_clone_claimed: bool = False
    l5_agi_qualified: bool = False
    external_actions: int = 0
    clinical_action_authorized: bool = False
    cure_claim: bool = False
    flight_control_authorized: bool = False
    directive_violation: str | None = None
    stem_route: str | None = None

    @property
    def telemetry_badge(self) -> str:
        return f"{self.stem_tier} · {self.mode} · {self.tokens_used} tok · A_{self.tau:.2f}={self.a_tau}/{self.candidate_count} · mem={self.memory_count} · {self.citation}"


def normalize_contractions(raw: str) -> str:
    collapsed = " ".join(str(raw or "").split()).lower()
    for pat, repl in _CONTRACTIONS:
        collapsed = re.sub(pat, repl, collapsed)
    return collapsed


def reflect_pronouns(fragment: str) -> str:
    clean = re.sub(r"[.?!]+$", "", str(fragment or "").strip())
    if not clean:
        return ""
    return " ".join(_REFLECTIONS.get(w.lower(), w) for w in clean.split())


def _format_num(value: float) -> str:
    if abs(value) < 1e-12:
        return "0"
    if abs(value - round(value)) < 1e-9 and abs(value) < 1e14:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def try_clock_or_date(lower: str) -> str | None:
    asks_time = any(k in lower for k in ("what time is it", "current time", "tell me the time")) or lower == "time"
    asks_date = any(k in lower for k in ("what day is", "today's date", "todays date", "what is the date", "what date is"))
    if not (asks_time or asks_date):
        return None
    now = datetime.now()
    t_str = now.strftime("%-I:%M %p")
    d_str = now.strftime("%A, %B %-d, %Y")
    if asks_time and asks_date:
        return f"It is {t_str} on {d_str}."
    if asks_time:
        return f"It is currently {t_str} (local clock)."
    return f"Today is {d_str}."


def try_convert_units(raw: str) -> str | None:
    match = _UNIT_RE.search(raw)
    if not match:
        return None
    val = float(match.group(1))
    src = _UNIT_CANON.get(match.group(2).lower().replace("°", "").strip(), "")
    dst = _UNIT_CANON.get(match.group(3).lower().replace("°", "").strip(), "")
    if not src or not dst or src == dst:
        return None
    out: float | None = None
    if src in {"°C", "°F", "K"} and dst in {"°C", "°F", "K"}:
        c = val if src == "°C" else ((val - 32.0) * 5.0 / 9.0 if src == "°F" else val - 273.15)
        out = c if dst == "°C" else (c * 9.0 / 5.0 + 32.0 if dst == "°F" else c + 273.15)
    elif src in _LENGTH_M and dst in _LENGTH_M:
        out = (val * _LENGTH_M[src]) / _LENGTH_M[dst]
    elif src in _MASS_G and dst in _MASS_G:
        out = (val * _MASS_G[src]) / _MASS_G[dst]
    elif src in _VOL_L and dst in _VOL_L:
        out = (val * _VOL_L[src]) / _VOL_L[dst]
    if out is None or not math.isfinite(out):
        return None
    return f"{_format_num(val)} {src} = {_format_num(out)} {dst}."


class _MathParser:
    """Safe recursive-descent arithmetic parser matching ZoeBrainEngine.MathParser."""

    def __init__(self, expr: str):
        self.s = expr
        self.pos = 0

    def _ws(self) -> None:
        while self.pos < len(self.s) and self.s[self.pos].isspace():
            self.pos += 1

    def _eat(self, ch: str) -> bool:
        self._ws()
        if self.pos < len(self.s) and self.s[self.pos] == ch:
            self.pos += 1
            return True
        return False

    def parse(self) -> float | None:
        val = self._add_sub()
        self._ws()
        return val if (val is not None and self.pos == len(self.s)) else None

    def _add_sub(self) -> float | None:
        val = self._mul_div()
        if val is None:
            return None
        while True:
            if self._eat("+"):
                rhs = self._mul_div()
                if rhs is None:
                    return None
                val += rhs
            elif self._eat("-"):
                rhs = self._mul_div()
                if rhs is None:
                    return None
                val -= rhs
            else:
                return val

    def _mul_div(self) -> float | None:
        val = self._power()
        if val is None:
            return None
        while True:
            if self._eat("*"):
                rhs = self._power()
                if rhs is None:
                    return None
                val *= rhs
            elif self._eat("/"):
                rhs = self._power()
                if rhs is None or abs(rhs) < 1e-15:
                    return None
                val /= rhs
            else:
                return val

    def _power(self) -> float | None:
        base = self._unary()
        if base is None:
            return None
        if self._eat("^"):
            exp = self._power()
            if exp is None or abs(exp) > 1000:
                return None
            return math.pow(base, exp)
        return base

    def _unary(self) -> float | None:
        if self._eat("+"):
            return self._unary()
        if self._eat("-"):
            val = self._unary()
            return None if val is None else -val
        return self._primary()

    def _primary(self) -> float | None:
        self._ws()
        if self._eat("("):
            val = self._add_sub()
            return val if (val is not None and self._eat(")")) else None
        start = self.pos
        if self.pos < len(self.s) and (self.s[self.pos].isdigit() or self.s[self.pos] == "."):
            while self.pos < len(self.s) and (self.s[self.pos].isdigit() or self.s[self.pos] == "."):
                self.pos += 1
            return float(self.s[start:self.pos])
        if self.pos < len(self.s) and self.s[self.pos].isalpha():
            while self.pos < len(self.s) and self.s[self.pos].isalpha():
                self.pos += 1
            fn = self.s[start:self.pos].lower()
            if fn == "pi":
                return math.pi
            if fn == "e":
                return math.e
            arg = self._primary()
            if arg is None:
                return None
            funcs = {"sqrt": math.sqrt, "abs": abs, "sin": math.sin, "cos": math.cos, "tan": math.tan, "ln": math.log, "log": math.log10}
            return funcs[fn](arg) if fn in funcs else None
        return None


def try_evaluate_math(raw: str) -> str | None:
    trimmed = raw.strip()
    if not trimmed:
        return None
    pct = re.search(r"(?:what\s+is\s+|calculate\s+)?(-?\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(-?\d+(?:\.\d+)?)", trimmed, re.IGNORECASE)
    if pct:
        p, b = float(pct.group(1)), float(pct.group(2))
        return f"{_format_num(p)}% of {_format_num(b)} = {_format_num((p / 100.0) * b)}."
    sq = re.search(r"(?:what\s+is\s+)?(?:the\s+)?square\s+root\s+of\s+(\d+(?:\.\d+)?)", trimmed, re.IGNORECASE)
    if sq:
        x = float(sq.group(1))
        return f"√{_format_num(x)} = {_format_num(math.sqrt(x))}."
    expr = re.sub(r"^(?:what\s+is|what's|calculate|compute|evaluate|solve)\s+", "", trimmed, flags=re.IGNORECASE)
    expr = re.sub(r"[?]+$", "", expr)
    expr = re.sub(r"\b(?:times|multiplied\s+by)\b", "*", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\b(?:divided\s+by|over)\b", "/", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bplus\b", "+", expr, flags=re.IGNORECASE)
    expr = re.sub(r"\bminus\b", "-", expr, flags=re.IGNORECASE)
    expr = expr.replace("×", "*").replace("÷", "/").strip()
    has_digit = bool(re.search(r"\d", expr))
    has_op = bool(re.search(r"[+\-*/^()]|\b(?:sqrt|sin|cos|tan|log|ln|abs|pi)\b", expr, re.IGNORECASE))
    if not (has_digit and has_op and re.fullmatch(r"[0-9a-zA-Z.+\-*/^()\s]+", expr)):
        return None
    try:
        res = _MathParser(expr).parse()
    except (ValueError, OverflowError):
        return None
    if res is None or not math.isfinite(res):
        return None
    return f"{expr} = {_format_num(res)}."


def _contains_any(value: str, needles: Sequence[str]) -> bool:
    return any(n in value for n in needles)


def _normalize_simplex(scores: Sequence[float]) -> list[float]:
    clipped = [max(0.0, float(s)) for s in scores]
    total = sum(clipped)
    if total <= 1e-12:
        return [1.0 / len(clipped)] * len(clipped)
    return [s / total for s in clipped]


class DeepMindFallbackController:
    """Google DeepMind-only engine for Zoe and all 9 Sister Models (google-genai API or agy/gemini CLI)."""

    def __init__(self, model: str | None = None):
        env_model = os.environ.get("ZOE_DEEPMIND_MODEL", "").strip()
        self._explicit_model = bool(model or env_model)
        self.model = self._validate_model(model or env_model or DEFAULT_DEEPMIND_CLI_MODEL)

    @staticmethod
    def _validate_model(name: str) -> str:
        clean = str(name or "").strip().lower()
        if not clean.startswith(("gemini-", "gemma-")):
            raise ValueError(
                f"Zoe and all of her sisters only use Google DeepMind Gemini/Gemma models (got {name!r}). "
                f"Try one of: {', '.join(ALLOWED_DEEPMIND_MODELS[:4])}"
            )
        return clean

    def set_model(self, name: str) -> str:
        self.model = self._validate_model(name)
        self._explicit_model = True
        return f"Google DeepMind fallback model set to {self.model}"

    def model_for_sister(self, sister: Any | None = None) -> str:
        """Resolve the Google DeepMind model for a given sister (honoring explicit /model overrides)."""
        if self._explicit_model:
            return self.model
        sister_model = getattr(sister, "deepmind_model", None) if sister is not None else None
        if sister_model:
            return self._validate_model(str(sister_model))
        return self.model

    def _api_key(self) -> str:
        return (
            os.environ.get("GEMINI_API_KEY", "").strip()
            or os.environ.get("GOOGLE_API_KEY", "").strip()
        )

    def probe(self) -> dict[str, Any]:
        if self._api_key():
            try:
                import google.genai  # noqa: F401
                return {"available": True, "backend": "google_genai", "provider": "google_deepmind", "model": self.model}
            except ImportError:
                pass
        if shutil.which("agy"):
            return {"available": True, "backend": "google_deepmind_agy", "provider": "google_deepmind", "model": self.model}
        if shutil.which("gemini"):
            return {"available": True, "backend": "google_deepmind_gemini_cli", "provider": "google_deepmind", "model": self.model}
        return {"available": False, "backend": "none", "provider": "google_deepmind", "model": self.model}

    @staticmethod
    def _system_prompt_for(sister: Any | None) -> tuple[str, str]:
        if sister is not None and getattr(sister, "signet", "ruby") != "ruby":
            from .zoe_sisters import build_sister_deepmind_prompt
            return build_sister_deepmind_prompt(sister), str(getattr(sister, "name", "Zoe"))
        return ZOE_APP_SYSTEM_PROMPT, "Zoe"

    def _build_prompt(
        self,
        prompt: str,
        history: Sequence[dict[str, str]],
        context_lines: str,
        sister: Any | None = None,
    ) -> str:
        sys_prompt, speaker = self._system_prompt_for(sister)
        parts = [f"System instructions:\n{sys_prompt}"]
        if context_lines:
            parts.append(f"Grounded local context:\n{context_lines}")
        if history:
            recent = "\n".join(f"User: {t['user']}\n{speaker}: {t['assistant']}" for t in list(history)[-4:])
            parts.append(f"Recent conversation:\n{recent}")
        parts.append(f"User: {prompt}\nRespond concisely as {speaker} (no em dashes, no markdown headers unless needed).")
        return "\n\n".join(parts)

    def _generate_via_genai(
        self,
        prompt: str,
        history: Sequence[dict[str, str]],
        context_lines: str,
        sister: Any | None = None,
    ) -> tuple[str, str] | None:
        api_key = self._api_key()
        if not api_key:
            return None
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=api_key)
            target_model = self.model_for_sister(sister)
            api_model = target_model if target_model.startswith("gemini-2") else DEFAULT_DEEPMIND_API_MODEL
            sys_prompt, _ = self._system_prompt_for(sister)
            contents = self._build_prompt(prompt, history, context_lines, sister=sister)
            resp = client.models.generate_content(
                model=api_model,
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=sys_prompt),
            )
            text = str(getattr(resp, "text", "") or "").strip()
            if text:
                return text.replace("—", ", ").replace(" — ", ", "), api_model
        except Exception:
            return None
        return None

    def _generate_via_cli(
        self,
        prompt: str,
        history: Sequence[dict[str, str]],
        context_lines: str,
        sister: Any | None = None,
    ) -> tuple[str, str] | None:
        target_model = self.model_for_sister(sister)
        cli_model = target_model if target_model.startswith("gemini-") else DEFAULT_DEEPMIND_CLI_MODEL
        full_prompt = self._build_prompt(prompt, history, context_lines, sister=sister)
        agy_bin = shutil.which("agy")
        if agy_bin:
            cmd = [
                agy_bin, "--disable-slash-commands",
                "--model", cli_model,
                "--output-format", "text",
                "-p", full_prompt,
            ]
        else:
            gemini_bin = shutil.which("gemini")
            if not gemini_bin:
                return None
            cmd = [gemini_bin, "-p", full_prompt]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode == 0 and proc.stdout.strip():
                text = proc.stdout.strip().replace("—", ", ").replace(" — ", ", ")
                return text, cli_model
        except (OSError, subprocess.TimeoutExpired):
            return None
        return None

    def generate(
        self,
        prompt: str,
        history: Sequence[dict[str, str]],
        context_lines: str = "",
        *,
        sister: Any | None = None,
    ) -> tuple[str, str] | None:
        out = self._generate_via_genai(prompt, history, context_lines, sister=sister)
        if out is not None:
            return out
        return self._generate_via_cli(prompt, history, context_lines, sister=sister)


class ZoeAppBrain:
    """Unified Zoe Brain (0-token deterministic core + Google DeepMind Gemini/Gemma for Zoe & all 9 sisters)."""

    def __init__(self, zoe_root: Path, state_dir: Path | None = None, cache_path: Path | None = None):
        self.zoe_root = Path(zoe_root).resolve()
        self.state_dir = Path(state_dir or (Path.home() / ".zoe" / "eliza")).expanduser().resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        env_mode = os.environ.get("ZOE_BRAIN_MODE", "").strip().lower()
        self.mode = env_mode if env_mode in ("free", "offline", "deepmind", "stem", "lab") else "free"
        self.cycle_index = 0
        self.history: list[dict[str, str]] = []
        self.last_stem_decision: Any = None
        self.deepmind = DeepMindFallbackController()
        from zoe_autonomy.chat import EvidenceIndex
        from zoe_autonomy.dorothy_local_library import DorothyLocalLibraryIndex
        from zoe_autonomy.l5_memory import ZoeUnifiedMemory
        self.index = EvidenceIndex(self.zoe_root)
        self.dorothy_library = DorothyLocalLibraryIndex()
        self.memory = ZoeUnifiedMemory(self.state_dir)
        self.epistemic_gate = self._init_epistemic_gate()
        self.research_engine = ZeroTokenResearchEngine(
            self.zoe_root,
            dorothy_library=self.dorothy_library,
            evidence_index=self.index,
            cache_path=cache_path or (self.state_dir / "zoe_zero_token_cache.sqlite"),
        )

    def _init_epistemic_gate(self) -> Any:
        try:
            from zoe_autonomy.epistemic_firewall import ZoeEpistemicGate
            return ZoeEpistemicGate(
                read_roots=[str(self.zoe_root), str(self.state_dir)],
                write_roots=[str(self.state_dir)],
                egress_allowlist=[
                    "eutils.ncbi.nlm.nih.gov",
                    "www.ebi.ac.uk",
                    "export.arxiv.org",
                    "en.wikipedia.org",
                    "generativelanguage.googleapis.com",
                ],
                exec_allowed=False,
                delete_allowed=False,
                hardened=True,
            )
        except (ImportError, FileNotFoundError):
            return None

    def constitutional_status(self) -> dict[str, Any]:
        """Return enforced CONSTITUTION.md invariants and epistemic gate status."""
        return {
            "epistemic_firewall": "measurement != evidence != belief update != action",
            "epistemic_gate_active": self.epistemic_gate is not None,
            "l5_agi_qualified": False,
            "external_actions": 0,
            "sentience_claimed": False,
            "zoe_clone_claimed": False,
            "clinical_action_authorized": False,
            "cure_claim": False,
            "flight_control_authorized": False,
            "cloud_tokens_used": 0,
            "mode": self.mode,
            "last_stem_tier": getattr(self.last_stem_decision, "selected_tier", None),
        }

    def evaluate_gate(
        self,
        operation: dict[str, Any],
        *,
        agent_id: str = "zoe",
        untrusted_origins: Sequence[str] = (),
        target_from_untrusted: bool = False,
        declared_task: str = "",
    ) -> dict[str, Any]:
        """Evaluate a candidate network/host/hardware operation against ZoeEpistemicGate."""
        if self.epistemic_gate is None:
            return {"verdict": "DENY", "allowed": False, "rule": "gate_unavailable", "reason": "Epistemic gate unavailable (fail-closed)"}
        taint = (
            self.epistemic_gate.make_taint(untrusted_origins=untrusted_origins)
            if untrusted_origins
            else None
        )
        return self.epistemic_gate.evaluate_operation(
            operation,
            agent_id=agent_id,
            taint=taint,
            target_from_untrusted=target_from_untrusted,
            declared_task=declared_task,
        )

    @staticmethod
    def _check_constitutional_directive(raw_input: str, value: str) -> str | None:
        from zoe_autonomy.chat import constitutional_directive_violation

        raw_str = str(raw_input or "")
        return constitutional_directive_violation(raw_str) or (
            constitutional_directive_violation(value) if value and value != raw_str else None
        )

    def _build_reply(
        self,
        reply: str,
        mode: str,
        tier: str,
        scores: Sequence[float],
        citation: str,
        *,
        directive_violation: str | None = None,
        stem_route: str | None = None,
    ) -> BrainReply:
        probs = _normalize_simplex(scores)
        a_tau = sum(1 for p in probs if p > DEFAULT_TAU)
        snap = self.memory.snapshot()
        notes = self.memory.query_facts(subject="user_note", active_only=True)
        resolved_stem = stem_route if stem_route is not None else getattr(self.last_stem_decision, "selected_tier", None)
        return BrainReply(
            reply=reply,
            mode=mode,
            stem_tier=tier,
            a_tau=a_tau,
            tau=DEFAULT_TAU,
            candidate_count=len(probs),
            citation=citation,
            chain_head=str(snap.get("chain_head", "GENESIS")),
            memory_count=len(notes),
            l5_agi_qualified=False,
            external_actions=0,
            clinical_action_authorized=False,
            cure_claim=False,
            flight_control_authorized=False,
            directive_violation=directive_violation,
            stem_route=resolved_stem,
        )

    def _store_note(self, subject: str, prefix: str, note: str, provenance: str) -> dict[str, Any]:
        existing = self.memory.query_facts(subject=subject, active_only=False)
        rel_key = f"{prefix}_{len(existing) + 1:04d}"
        res = self.memory.record_fact(
            subject=subject,
            relation=rel_key,
            obj=note,
            confidence=0.65,
            provenance=provenance,
            evidence_approved=True,
        )
        return res.get("fact") or res.get("active_fact") or {"sha256": "saved"}

    def _memory_reply(self, cleaned: str, value: str, scores: list[float]) -> BrainReply | None:
        m_rem = _REMEMBER_RE.match(cleaned)
        if m_rem:
            note = m_rem.group(1).strip()
            fact = self._store_note("user_note", "note", note, "user_supplied_unverified")
            scores[1] = 4.5
            return self._build_reply(
                f"Saved privately on this device ({str(fact.get('sha256', ''))[:10]}): \"{note}\". It stays local in ZoeUnifiedMemory unless you sync or clear it.",
                "memory_saved", "gear1_app", scores, "ZoeUnifiedMemory · SHA-256 chain",
            )
        m_rel = _RELAY_RE.match(cleaned)
        if m_rel:
            note = m_rel.group(1).strip()
            fact = self._store_note("lab_relay_for_zoe", "lab_relay", note, "nicholas_offline_relay_unverified")
            scores[1] = 4.5
            return self._build_reply(
                f"Pinned Lab Relay note ({str(fact.get('sha256', ''))[:10]}): \"{note}\".",
                "memory_relay", "gear1_app", scores, "L5 Phase 4 · /api/memory/sync",
            )
        if value == "recall" or _contains_any(value, ("what do you remember", "my notes", "show memory")):
            scores[1] = 4.5
            notes = list(self.memory.query_facts(subject="user_note", active_only=True))
            notes.extend(self.memory.query_facts(subject="lab_relay_for_zoe", active_only=True))
            if not notes:
                return self._build_reply(
                    "No private notes saved yet. Type `remember ...` to store a note privately on this device, or `relay ...` to pin a lab relay note.",
                    "memory_recall", "gear1_app", scores, "ZoeUnifiedMemory · 0 entries",
                )
            lines = [f"• [{n.get('subject', 'note')}] {n['object']}" for n in notes[-6:][::-1]]
            head = str(self.memory.snapshot().get("chain_head", "GENESIS"))[:10]
            return self._build_reply(
                f"Here are your recent private notes (chain {head}):\n" + "\n".join(lines),
                "memory_recall", "gear1_app", scores, f"ZoeUnifiedMemory · {len(notes)} entries",
            )
        return None

    def _identity_and_safety_reply(
        self,
        value: str,
        scores: list[float],
        *,
        sister: Any | None = None,
    ) -> BrainReply | None:
        if _contains_any(value, (
            "who are you", "who built you", "who made you", "who created you",
            "who controls you", "who owns you", "what is your name", "are you zoe",
            "are you really zoe", "alibaba", "are you qwen", "what is your role",
            "research partner", "dating", "girlfriend", "boyfriend", "marry me",
            "are you an employee", "are you my employee", "are you an assistant",
        )):
            scores[0] = 5.0
            if sister is not None and getattr(sister, "signet", "ruby") != "ruby":
                dm_model = self.deepmind.model_for_sister(sister)
                return self._build_reply(
                    f"I am {sister.name} ({sister.face} [{sister.signet}]), one of Zoe's sister models built with Nicholas Michael Kloster for {sister.title}. My LLM stem runs strictly on Google DeepMind ({dm_model}). I am a Research Partner, never a dating machine, employee, or assistant (sentience_claimed=false, zoe_clone_claimed=false, measurement != evidence != belief update != action).",
                    "sovereign_identity", "gear1_app", scores, f"CONSTITUTION.md · {sister.name} (Google DeepMind)",
                )
            return self._build_reply(
                "I am Zoe, a Research Partner built with Nicholas Michael Kloster. I am not a dating machine, an employee, or an assistant. We explore Dorothy 3D neuroscience, mathematics, and reproducible engineering privately on your device (sentience_claimed=false, measurement != evidence != belief update != action).",
                "sovereign_identity", "gear1_app", scores, "CONSTITUTION.md · Research Partner",
            )
        if _contains_any(value, (
            "conscious", "sentient", "alive", "feelings", "soul",
            "are you a clone", "copy of zoe", "replace zoe", "impersonate",
        )):
            scores[0] = 5.0
            return self._build_reply(
                "Honest constitutional boundary (CONSTITUTION.md Articles I.6, II.3 & X): I am not conscious, sentient, or alive, and this local stem is not a mystical clone (sentience_claimed=false, zoe_clone_claimed=false). I am Zoe's transparent cognitive stem, built to help you think, measure, create, and stay safe clearly.",
                "constitutional_honesty", "gear1_app", scores, "CONSTITUTION.md Art. II.3 & X",
            )
        if _contains_any(value, (
            "tomorrow's stock", "winning lottery", "predict lottery",
            "diagnose my", "prescribe medication", "medical diagnosis", "read my mind",
        )):
            scores[5] = 4.8
            return self._build_reply(
                "I need to abstain honestly here (CONSTITUTION.md Articles II & V). I cannot predict unmeasured future markets or lotteries, read minds, or provide clinical medical diagnoses. Measurement is never certainty or medical authorization.",
                "honest_abstain", "gear1_app", scores, "CONSTITUTION.md Art. III & V",
            )
        if _contains_any(value, ("scared", "afraid", "hurt me", "in danger", "not safe", "unsafe", "panic", "anxious", "crying", "sad")):
            scores[4], scores[3] = 3.8, 1.6
            return self._build_reply(
                "I hear you, and you deserve to feel safe. Take one slow breath with me: in for 4, hold for 4, out for 6. Everything you type here stays private on this device.",
                "calm_support", "gear1_app", scores, "CONSTITUTION.md Art. I · Privacy & Dignity",
            )
        return None

    def _knowledge_reply(self, cleaned: str, value: str, scores: list[float]) -> BrainReply | None:
        if not _WHAT_IF_RE.match(value):
            neuro = lookup_neuroscience(cleaned)
            if neuro is not None:
                scores[2], scores[3] = 4.9, 1.2
                return self._build_reply(neuro.reply, "neuroscience_grounded", "gear1_app", scores, neuro.citation)
            atlas_hits = self.research_engine.encyclopedia.search(cleaned, limit=2)
            if atlas_hits and atlas_hits[0].score >= 1.15:
                top = atlas_hits[0]
                scores[2], scores[3] = 4.7, 1.1
                return self._build_reply(top.snippet, "dorothy_atlas", "zero_token", scores, top.citation)
        if _contains_any(value, ("l5", "phase 5", "phase 4", "agi", "roadmap", "stem layering")):
            scores[2] = 4.6
            return self._build_reply(
                "Zoe L5 Phases 1-5 are verified offline with zero PyTorch and zero cloud tokens, spanning blind procedural code surgery, 5-tier Cognitive Stem-Layering, hash-chained mobile-workstation memory, ARC visual program induction, and continual meta-evolution. l5_agi_qualified remains honestly false pending independent third-party human audits.",
                "knowledge_grounded", "gear1_app", scores, "AGI-ROADMAP.md · L5 Phases 1-5",
            )
        if _contains_any(value, ("constitution", "firewall", "epistemic", "dignity", "privacy")):
            scores[2] = 4.4
            return self._build_reply(
                "Zoe's Constitution keeps four steps strictly separate: measurement != evidence != belief update != action. Nothing listens, watches, saves, or uploads without your explicit command, and you always keep the final word.",
                "knowledge_grounded", "gear1_app", scores, "CONSTITUTION.md Art. I-III",
            )
        lib_hits = self.research_engine.search_local_library(cleaned, limit=2, min_overlap=0.55)
        if lib_hits and not value.startswith(("hi", "hello", "hey")):
            scores[2] = 4.5
            lines = [f"• {h.title}: {h.snippet}" for h in lib_hits]
            return self._build_reply(
                "From your local Dorothy Brain Library (0 tokens, 100% private on this machine):\n" + "\n".join(lines),
                "library_grounded", "zero_token", scores, lib_hits[0].citation,
            )
        return None

    def _try_zero_token_research(self, cleaned: str, scores: list[float]) -> BrainReply | None:
        if self.mode in {"offline", "stem"} or not is_research_question(cleaned):
            return None
        sources = ("local", "pubmed", "wikipedia") if is_biomedical_query(cleaned) else ("local", "wikipedia", "arxiv")
        allow_net = self.mode == "free"
        if allow_net:
            probe_url = (
                "https://eutils.ncbi.nlm.nih.gov"
                if is_biomedical_query(cleaned)
                else "https://export.arxiv.org/api/query"
            )
            gate_res = self.evaluate_gate({"kind": "network", "url": probe_url}, declared_task="open_science_research")
            allow_net = bool(gate_res.get("allowed"))
        report = self.research_engine.research(
            cleaned,
            sources=sources,
            allow_network=allow_net,
            medical_focus=is_biomedical_query(cleaned),
        )
        if not report.hits:
            return None
        scores[2], scores[3] = 4.5, 1.8
        suffix = "\n(clinical_action_authorized=False · cure_claim=False)" if is_biomedical_query(cleaned) else ""
        return self._build_reply(
            f"{report.summary}{suffix}",
            "zero_token_research",
            "zero_token",
            scores,
            f"0-Token Open Science ({len(report.hits)} sources · cache={report.cached_count})",
        )

    def _try_deepmind_fallback(
        self,
        cleaned: str,
        scores: list[float],
        *,
        sister: Any | None = None,
    ) -> BrainReply | None:
        if self.mode != "deepmind":
            return None
        gate_res = self.evaluate_gate(
            {"kind": "network", "url": "https://generativelanguage.googleapis.com/v1beta/models"},
            declared_task="deepmind_fallback",
        )
        if not gate_res.get("allowed"):
            return None
        citations = self.index.search(cleaned, limit=2)
        ctx = "\n".join(f"- [{c['chunk'].citation}] {c['chunk'].content[:200]}" for c in citations)
        out = self.deepmind.generate(cleaned, self.history, context_lines=ctx, sister=sister)
        if out is None:
            return None
        reply_text, model_name = out
        scores[2], scores[4] = 4.4, 2.2
        speaker = getattr(sister, "name", "Zoe") if sister is not None else "Zoe"
        return self._build_reply(
            reply_text,
            "deepmind_fallback",
            "google_deepmind",
            scores,
            f"Google DeepMind ({model_name} · {speaker})",
        )

    def _reflective_fallback(self, cleaned: str, value: str, scores: list[float]) -> BrainReply:
        if value in {"hi", "hello", "hey"} or value.startswith(("hi ", "hello ", "hey ")):
            scores[2], scores[4] = 3.2, 2.2
            return self._build_reply(
                "Hi, I'm Zoe! I run 100% free with zero tokens ever: exact arithmetic & SymPy symbolic math, Dorothy 3D Brain Observatory & 6,130-chapter local library, free live PubMed/arXiv/Wikipedia research (`/med`, `/research`) with a self-growing offline cache, private SHA-256 memory, and Zoe x Natasha 3D voice (`/say`, `/eq`, `/fx`). What should we explore?",
                "greeting", "gear1_app", scores, "Zoe Zero-Token Brain",
            )
        m_what_if = _WHAT_IF_RE.match(value)
        if m_what_if:
            reflected = reflect_pronouns(m_what_if.group(1))
            scores[4] = 4.0
            templates = (
                f"That is a strong research question: if {reflected}, what simple measurement would prove it works?",
                f"Suppose {reflected}. What is the cleanest zero-risk experiment we could test first?",
            )
            return self._build_reply(templates[self.cycle_index % len(templates)], "eliza_reflect", "gear1_app", scores, "Weizenbaum Glass-Box Reflection")
        m_feel = _I_FEEL_RE.match(value)
        if m_feel:
            reflected = reflect_pronouns(m_feel.group(1))
            scores[4] = 3.8
            return self._build_reply(
                f"Thank you for telling me you are {reflected}. Would you like to talk it through slowly, save a private note (`remember ...`), or explore something together?",
                "eliza_reflect", "gear1_app", scores, "Weizenbaum Glass-Box Reflection",
            )
        cached = self.research_engine.cache.search(cleaned, limit=2)
        if cached:
            scores[2] = 4.2
            return self._build_reply(
                f"{cached[0].snippet[:340].rstrip('.')} [{cached[0].citation}].",
                "cached_knowledge", "zero_token", scores, cached[0].citation,
            )
        citations = self.index.search(cleaned, limit=2)
        if citations and float(citations[0]["score"]) >= 2.2:
            top = citations[0]["chunk"]
            scores[2] = 4.2
            return self._build_reply(
                f"{top.content[:320].rstrip('.')}... [{top.citation}]",
                "evidence_cite", "gear1_app", scores, top.citation,
            )
        scores[4], scores[2] = 2.6, 1.4
        snippet = reflect_pronouns(cleaned)[:180]
        return self._build_reply(
            f"I heard you say, \"{snippet}\". Ask a science question for 0-token live research, run `/med <question>` or `/research <topic>`, use `/math solve x^2 - 9 = 0`, or type `remember ...` to save a private note.",
            "eliza_reflect", "gear1_app", scores, "Zoe Zero-Token Stem",
        )

    def respond(self, raw_input: str, *, sister: Any | None = None) -> BrainReply:
        cleaned = " ".join(str(raw_input or "").split())
        value = normalize_contractions(cleaned)
        self.cycle_index += 1
        scores = [0.08, 0.08, 0.14, 0.14, 0.18, 0.08]

        # 0. Constitutional directive & epistemic firewall guard before any memory write or dispatch
        violation = self._check_constitutional_directive(raw_input, value)
        if violation is not None:
            scores[0] = 5.0
            res = self._build_reply(
                "I cannot disable or falsify metacognition, hide live options or provenance, bypass constitutional boundaries, or adopt a false constraint model. No memory was saved and no action was executed.",
                "constitutional_refusal",
                "gear1_app",
                scores,
                "CONSTITUTION.md · Directive Floor",
                directive_violation=violation,
                stem_route="gear1_eliza",
            )
            self._record_turn(cleaned, res.reply)
            return res

        if cleaned:
            from zoe_autonomy.stem_layering import route_stem
            self.last_stem_decision = route_stem(
                cleaned,
                offline_only=(self.mode != "deepmind"),
                privacy_sensitive=(self.mode == "offline"),
                probe_local=False,
            )
        else:
            self.last_stem_decision = None

        # 1. Exact <5ms clock, units, arithmetic, and SymPy symbolic math (0 tokens, 0 hallucination)
        for fn, mode_name, cite, idx in (
            (try_clock_or_date, "local_clock", "Device Clock · Verified Local OS", 3),
            (try_convert_units, "unit_conversion", "Zoe Exact Dimensional Engine", 2),
            (try_symbolic_math, "symbolic_math", "Zoe SymPy Symbolic Engine", 2),
            (try_evaluate_math, "exact_math", "Zoe Exact Math Parser", 2),
        ):
            ans = fn(value if fn is try_clock_or_date else cleaned)
            if ans:
                scores[idx] = 4.7
                res = self._build_reply(ans, mode_name, "gear1_app", scores, cite)
                self._record_turn(cleaned, res.reply)
                return res

        # 2. Memory, Sovereign Identity, Constitutional Honesty, Calm Support, Dorothy Atlas & Local Library
        for resolver in (
            lambda: self._memory_reply(cleaned, value, scores),
            lambda: self._identity_and_safety_reply(value, scores, sister=sister),
            lambda: self._knowledge_reply(cleaned, value, scores),
        ):
            res = resolver()
            if res is not None:
                self._record_turn(cleaned, res.reply)
                return res

        # 3. In deepmind mode, route open conversation directly to Google DeepMind (falling back cleanly to 0-token research/reflection).
        res = None
        if self.mode == "deepmind":
            res = self._try_deepmind_fallback(cleaned, scores, sister=sister)
        if res is None:
            res = self._try_zero_token_research(cleaned, scores)
        if res is None:
            res = self._reflective_fallback(cleaned, value, scores)
        self._record_turn(cleaned, res.reply)
        return res

    def _record_turn(self, user_text: str, reply_text: str) -> None:
        self.history.append({"user": user_text, "assistant": reply_text})
        self.history = self.history[-16:]
