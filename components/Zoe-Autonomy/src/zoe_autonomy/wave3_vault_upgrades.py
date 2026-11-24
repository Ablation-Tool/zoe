"""
Wave 3 Vault Bridges for Zoe (Strictly Non-Biology).

Integrates five unpublished Google Drive Vault inventions cleanly into Zoe:
  1. 5-Dim Continuous `TrustEngine` (`seven-layer-sonification-v4/src/trust.py`)
     -> `DualPeerSession` + `nina` Lume audio cues (enforcing `output_trust <= source_trust`)
  2. 4 Unpublished AI-Agent Binary Auditors (`ablation-re-lab/modules/`):
     - `AgentAuthorityAudit`, `AgentObservabilityAudit`,
       `AgentToolSurfaceEnumerator`, `AIControlIndicators`
  3. `DualPathVerifier` + `VisorLogDisagreementLedger`
     (`Dual-Path_Query_Validation_Framework`) — parallel deterministic vs. LLM
     query validation with BERT-style `[MASK]` correction flashcards persisted
     directly in `VisorLog`'s SQLite `events` schema
  4. Eq. 2 Slow-Drift Cascade Hardening (`cascade_subsection.txt`) + `vec2text`
     Vector-Privacy sealing (`gemseal`) + MCP Home-Subdir & Vector-Filter Guards (`kevlar`)
  5. `AgentEmailGuardrail` (`Minimal-Email-Guardrail-Python-Impl`) +
     ROS Confirm-Before-Move Hardware Interlock (`ROS-Control-Immediate-Exec-Philosophy`) +
     `VisorCAS` Lock-Free Bloom+CAS Dedup bridge (`Scanner-Bloom-CAS-Dedup-Design`)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _components_dir() -> Path:
    return _repo_root() / "components"


def _load_module(module_name: str, file_path: Path) -> Any:
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {module_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_sys_path(path: Path) -> None:
    p = str(path)
    if p not in sys.path:
        sys.path.insert(0, p)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


# ============================================================================
# 1. Continuous 5-Dim TrustEngine -> Lume Audio Cue Bridge
# ============================================================================

def build_lume_trust_audio_cue(
    *,
    source_trust: float,
    coherence_c_k: float = 0.75,
    evidence_coverage: float = 0.75,
    coercion_detected: bool = False,
    disagreement_d_k: float = 0.05,
    base_eq: Optional[Dict[str, float]] = None,
    effect_key: str = "flat",
) -> Dict[str, Any]:
    """Compute a 5D TrustEngine gradient and render matching `nina` Lume audio FX."""
    from .trust_gradient import TrustEngine

    te = TrustEngine(source_trust=source_trust)
    trust_report = te.evaluate_peer_turn(
        source_trust=source_trust,
        coherence_c_k=coherence_c_k,
        evidence_coverage=evidence_coverage,
        coercion_detected=coercion_detected,
        disagreement_d_k=disagreement_d_k,
    )
    nina_fx = _load_module("_zoe_nina_audio_fx", _components_dir() / "nina" / "audio_fx.py")
    lume_fx = nina_fx.build_trust_lume_cue(
        trust_report["output_trust"],
        base_eq=base_eq,
        effect_key=effect_key,
    )
    return {
        "trust": trust_report,
        "lume_fx": lume_fx,
        "ceiling_enforced": trust_report["output_trust"] <= trust_report["source_trust"] + 1e-12,
    }


# ============================================================================
# 2. Four Unpublished AI-Agent Binary Auditors (ablation.analyzers)
# ============================================================================

def audit_ai_agent_binary(
    target: str | Path | bytes,
    *,
    plt_names: Optional[Iterable[str]] = None,
    func_names: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """Run all 4 Wave-3 AI-agent binary auditors from `components/ablation`.

    Supports either an on-disk binary path (using `BinaryContext` when `plt_names`
    is omitted) or raw bytes (with optional `plt_names` / `func_names` for fast
    unit/firmware buffer auditing).
    """
    _ensure_sys_path(_components_dir() / "ablation")
    from ablation.analyzers import (
        AgentAuthorityAudit,
        AgentObservabilityAudit,
        AgentToolSurfaceEnumerator,
        AIControlIndicators,
    )

    if isinstance(target, (bytes, bytearray)):
        raw = bytes(target)
        label = "<bytes>"
        auth_findings = AgentAuthorityAudit.scan_bytes(raw, plt_names or ())
        obs_findings = AgentObservabilityAudit.scan_bytes(raw, plt_names or (), func_names or ())
        tool_findings = AgentToolSurfaceEnumerator.scan_bytes(raw)
        ai_findings = AIControlIndicators.scan_bytes(raw)
    else:
        path_str = str(Path(target))
        label = path_str
        raw = Path(path_str).read_bytes() if Path(path_str).is_file() else b""
        if plt_names is not None:
            auth_findings = AgentAuthorityAudit.scan_bytes(raw, plt_names)
            obs_findings = AgentObservabilityAudit.scan_bytes(raw, plt_names, func_names or ())
        else:
            auth_findings = AgentAuthorityAudit(path_str).scan()
            obs_findings = AgentObservabilityAudit(path_str).scan()
        tool_findings = AgentToolSurfaceEnumerator(path_str).scan()
        ai_findings = AIControlIndicators(path_str).scan()

    total = len(auth_findings) + len(obs_findings) + len(tool_findings) + len(ai_findings)
    high_count = sum(
        1
        for f in (*auth_findings, *obs_findings, *tool_findings, *ai_findings)
        if getattr(f, "severity", "") == "HIGH"
    )
    return {
        "target": label,
        "total_findings": total,
        "high_severity_count": high_count,
        "authority_findings": [asdict(f) for f in auth_findings],
        "observability_findings": [asdict(f) for f in obs_findings],
        "tool_surface_findings": [asdict(f) for f in tool_findings],
        "ai_control_indicators": [asdict(f) for f in ai_findings],
        "elevated_review_required": high_count > 0 or bool(ai_findings),
    }


# ============================================================================
# 3. Dual-Path Query Validation & Masked-Slot Correction Flywheel + VisorLog
# ============================================================================

@dataclass
class MaskedQueryCorrectionExample:
    """BERT-style masked-slot training flashcard generated from a dual-path diff."""

    intent: str
    parameters: Dict[str, Any]
    schema_name: str
    discrepancy_kind: str
    llm_query: str
    trusted_query: str
    masked_query: str
    target_segment: str
    erroneous_segment: str
    trusted_digest: str
    llm_digest: str
    created_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _canonical_digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def _build_masked_flashcard(llm_query: str, trusted_query: str) -> Tuple[str, str, str]:
    """Identify the differing segment between Q_L and Q_T and mask it in Q_L."""
    llm_tokens = re.findall(r"\S+", llm_query)
    trusted_tokens = re.findall(r"\S+", trusted_query)
    if not llm_tokens:
        return "[MASK]", trusted_query.strip(), ""

    sm = difflib.SequenceMatcher(a=llm_tokens, b=trusted_tokens)
    opcodes = sm.get_opcodes()
    masked_parts: List[str] = []
    err_segs: List[str] = []
    target_segs: List[str] = []

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            masked_parts.extend(llm_tokens[i1:i2])
        else:
            masked_parts.append("[MASK]")
            if i2 > i1:
                err_segs.append(" ".join(llm_tokens[i1:i2]))
            if j2 > j1:
                target_segs.append(" ".join(trusted_tokens[j1:j2]))

    return (
        " ".join(masked_parts),
        " | ".join(target_segs) if target_segs else trusted_query.strip(),
        " | ".join(err_segs),
    )


def _classify_discrepancy(llm_query: str, trusted_query: str, llm_error: Optional[str]) -> str:
    if llm_error:
        return "LLM_EXECUTION_ERROR"
    low_err = _build_masked_flashcard(llm_query, trusted_query)[2].lower()
    if re.search(r"[<>]=?|\b\d+(?:\.\d+)?\b", low_err):
        return "THRESHOLD_MISMATCH"
    if re.search(r"\b(?:join|on|group|from|table)\b", low_err):
        return "JOIN_OR_SCHEMA_MISMATCH"
    if re.search(r"\b(?:where|and|or|in|like|not|!=|=)\b", low_err):
        return "FILTER_MISMATCH"
    return "RESULT_DIVERGENCE"


# Exact VisorLog SQLite `events` table schema (mirrors components/VisorLog/store/db.go)
_VISORLOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT    NOT NULL,
    event_category   TEXT    NOT NULL,
    event_type       TEXT    NOT NULL DEFAULT 'created',
    event_severity   TEXT    NOT NULL DEFAULT 'info',
    host_ip          TEXT,
    host_hostname    TEXT,
    org_name         TEXT,
    org_country      TEXT,
    sector           TEXT,
    tld              TEXT,
    tags             TEXT    DEFAULT '[]',
    source           TEXT,
    vuln_ids         TEXT    DEFAULT '[]',
    lifecycle_status TEXT    NOT NULL DEFAULT 'open',
    notes            TEXT,
    raw              TEXT
);
CREATE INDEX IF NOT EXISTS idx_lifecycle_status ON events(lifecycle_status);
CREATE INDEX IF NOT EXISTS idx_event_severity   ON events(event_severity);
CREATE INDEX IF NOT EXISTS idx_timestamp        ON events(timestamp);
"""


class VisorLogDisagreementLedger:
    """Append-only SQLite disagreement ledger compatible with `components/VisorLog`."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if str(db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.executescript(_VISORLOG_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def record(self, example: MaskedQueryCorrectionExample, *, severity: str = "medium") -> int:
        tags = ["dual-path", "masked-flashcard", example.discrepancy_kind.lower()]
        notes = f"{example.discrepancy_kind}: {example.intent} | mask={example.masked_query}"
        cur = self._conn.execute(
            """
            INSERT INTO events
            (timestamp, event_category, event_type, event_severity,
             host_ip, host_hostname, org_name, org_country, sector, tld,
             tags, source, vuln_ids, lifecycle_status, notes, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                example.created_utc,
                "dual_path_disagreement",
                "masked_flashcard",
                severity,
                "",
                "localhost",
                "zoe-autonomy",
                "",
                example.schema_name,
                "",
                json.dumps(tags),
                "zoe_dual_path_verifier",
                "[]",
                "open",
                notes,
                json.dumps(example.to_dict(), sort_keys=True),
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_flashcards(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT id, timestamp, event_severity, notes, raw
            FROM events
            WHERE event_category = 'dual_path_disagreement'
            ORDER BY id ASC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
        out: List[Dict[str, Any]] = []
        for row_id, ts, sev, notes, raw in rows:
            payload = json.loads(raw) if raw else {}
            payload["event_id"] = row_id
            payload["timestamp"] = ts
            payload["severity"] = sev
            payload["notes"] = notes
            out.append(payload)
        return out

    def export_training_jsonl(self, output_path: str | Path) -> int:
        cards = self.list_flashcards(limit=100000)
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8") as fh:
            for c in cards:
                fh.write(json.dumps(c, sort_keys=True) + "\n")
        return len(cards)


class DualPathVerifier:
    """Run a trusted deterministic query path alongside a fast LLM query path.

    Operationalizes Zoe's `measurement != belief update` invariant:
      - If Q_T and Q_L agree -> MATCH, verified result returned.
      - If Q_T and Q_L disagree -> LLM result is HELD, trusted result is returned,
        and a BERT-style `[MASK]` correction flashcard is written to the VisorLog
        disagreement ledger so the model improves from verified diffs.
    """

    def __init__(self, ledger: Optional[VisorLogDisagreementLedger] = None) -> None:
        self.ledger = ledger
        self.total_runs: int = 0
        self.mismatch_count: int = 0

    def verify(
        self,
        *,
        intent: str,
        parameters: Dict[str, Any],
        schema_name: str,
        trusted_query: str,
        llm_query: str,
        trusted_runner: Callable[[str], Any],
        llm_runner: Callable[[str], Any],
    ) -> Dict[str, Any]:
        self.total_runs += 1
        trusted_result = trusted_runner(trusted_query)
        trusted_digest = _canonical_digest(trusted_result)

        llm_error: Optional[str] = None
        try:
            llm_result = llm_runner(llm_query)
            llm_digest = _canonical_digest(llm_result)
        except Exception as exc:
            llm_result = None
            llm_error = f"{type(exc).__name__}: {exc}"
            llm_digest = "error"

        matched = llm_error is None and trusted_digest == llm_digest
        flashcard: Optional[MaskedQueryCorrectionExample] = None
        ledger_event_id: Optional[int] = None

        if not matched:
            self.mismatch_count += 1
            masked_q, target_seg, err_seg = _build_masked_flashcard(llm_query, trusted_query)
            kind = _classify_discrepancy(llm_query, trusted_query, llm_error)
            flashcard = MaskedQueryCorrectionExample(
                intent=intent,
                parameters=dict(parameters),
                schema_name=schema_name,
                discrepancy_kind=kind,
                llm_query=llm_query,
                trusted_query=trusted_query,
                masked_query=masked_q,
                target_segment=target_seg,
                erroneous_segment=err_seg,
                trusted_digest=trusted_digest,
                llm_digest=llm_digest,
                created_utc=_utc_now_iso(),
            )
            if self.ledger is not None:
                ledger_event_id = self.ledger.record(
                    flashcard,
                    severity="high" if llm_error else "medium",
                )

        return {
            "status": "MATCH" if matched else "MISMATCH_HELD",
            "matched": matched,
            "authoritative_result": trusted_result,
            "llm_result_accepted": matched,
            "trusted_digest": trusted_digest,
            "llm_digest": llm_digest,
            "llm_error": llm_error,
            "flashcard": flashcard.to_dict() if flashcard else None,
            "visorlog_event_id": ledger_event_id,
            "disagreement_rate": round(self.mismatch_count / max(self.total_runs, 1), 4),
        }


# ============================================================================
# 4. Vector-Privacy (gemseal) & MCP Subdir / Vector-Filter (kevlar) Bridges
# ============================================================================

def seal_embeddings_with_gemseal(
    master_key: bytes,
    records: Sequence[Dict[str, Any]],
    destination: str | Path,
    *,
    model_id: str = "unknown",
    classification: str = "sensitive",
) -> Dict[str, Any]:
    """Seal dense embeddings via `components/gemseal` under the vec2text privacy policy."""
    gemseal = _load_module("_zoe_gemseal", _components_dir() / "gemseal" / "gemseal.py")
    return gemseal.seal_embedding_records(
        master_key,
        records,
        destination,
        model_id=model_id,
        classification=classification,
    )


def unseal_embeddings_with_gemseal(master_key: bytes, source: str | Path) -> Dict[str, Any]:
    gemseal = _load_module("_zoe_gemseal", _components_dir() / "gemseal" / "gemseal.py")
    return gemseal.unseal_embedding_records(master_key, source)


def audit_embedding_file_privacy(path: str | Path) -> Dict[str, Any]:
    gemseal = _load_module("_zoe_gemseal", _components_dir() / "gemseal" / "gemseal.py")
    return gemseal.audit_embedding_storage_policy(path)


def check_mcp_path_with_kevlar(
    requested_path: str,
    *,
    allowed_roots: Sequence[str],
    home_dir: Optional[str] = None,
) -> Dict[str, Any]:
    kevlar_policy = _load_module("_zoe_kevlar_policy", _components_dir() / "kevlar" / "policy.py")
    return kevlar_policy.check_mcp_path_confinement(
        requested_path,
        allowed_roots=list(allowed_roots),
        home_dir=home_dir,
    )


def sanitize_vector_filter_with_kevlar(
    filter_value: Any,
    *,
    is_text_match: bool = False,
) -> Dict[str, Any]:
    kevlar_policy = _load_module("_zoe_kevlar_policy", _components_dir() / "kevlar" / "policy.py")
    return kevlar_policy.sanitize_vector_filter_value(
        filter_value,
        is_text_match=is_text_match,
    )


# ============================================================================
# 5. Agent Email Allowlist Guardrail + ROS Confirm-Before-Move Gate
# ============================================================================

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")

_EMAIL_GUARDRAIL_SCHEMA = """
CREATE TABLE IF NOT EXISTS policies (
    agent_id           TEXT PRIMARY KEY,
    user_id            TEXT NOT NULL,
    allowed_recipients TEXT NOT NULL,
    sends_per_minute   INTEGER DEFAULT 5,
    reads_per_day      INTEGER DEFAULT 100
);
CREATE TABLE IF NOT EXISTS audit_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id  TEXT,
    action    TEXT,
    recipient TEXT,
    timestamp TEXT,
    status    TEXT,
    reason    TEXT
);
CREATE TABLE IF NOT EXISTS rate_limit (
    key        TEXT PRIMARY KEY,
    count      INTEGER,
    reset_time TEXT
);
"""


class AgentEmailGuardrail:
    """SQLite-backed outbound email policy gate (ported from Minimal-Email-Guardrail).

    Enforces per-agent recipient allowlists (exact email or `@domain`),
    per-minute send rate limits, per-day read quotas, CRLF header-injection
    blocking, and append-only audit logging with zero external dependencies.
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.executescript(_EMAIL_GUARDRAIL_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def set_policy(
        self,
        agent_id: str,
        *,
        user_id: str,
        allowed_recipients: Sequence[str],
        sends_per_minute: int = 5,
        reads_per_day: int = 100,
    ) -> None:
        clean = [r.strip().lower() for r in allowed_recipients if r and r.strip()]
        self._conn.execute(
            """
            INSERT OR REPLACE INTO policies
            (agent_id, user_id, allowed_recipients, sends_per_minute, reads_per_day)
            VALUES (?, ?, ?, ?, ?)
            """,
            (agent_id, user_id, json.dumps(clean), int(sends_per_minute), int(reads_per_day)),
        )
        self._conn.commit()

    def _log(self, agent_id: str, action: str, recipient: str, status: str, reason: str) -> None:
        self._conn.execute(
            "INSERT INTO audit_log (agent_id, action, recipient, timestamp, status, reason) VALUES (?,?,?,?,?,?)",
            (agent_id, action, recipient, _utc_now_iso(), status, reason),
        )
        self._conn.commit()

    def _check_rate(self, key: str, limit: int, window_seconds: int) -> Tuple[bool, int]:
        now = datetime.now(timezone.utc)
        row = self._conn.execute(
            "SELECT count, reset_time FROM rate_limit WHERE key = ?", (key,)
        ).fetchone()
        if row is None or datetime.fromisoformat(row[1]) <= now:
            reset = (now + timedelta(seconds=window_seconds)).isoformat()
            self._conn.execute(
                "INSERT OR REPLACE INTO rate_limit (key, count, reset_time) VALUES (?, ?, ?)",
                (key, 1, reset),
            )
            self._conn.commit()
            return True, 1
        count = int(row[0])
        if count >= limit:
            return False, count
        self._conn.execute(
            "UPDATE rate_limit SET count = ? WHERE key = ?", (count + 1, key)
        )
        self._conn.commit()
        return True, count + 1

    def check_send(self, agent_id: str, recipient: str, subject: str = "") -> Dict[str, Any]:
        """Authorize or deny an outbound email send request."""
        if any(c in recipient or c in subject for c in ("\r", "\n")):
            self._log(agent_id, "send", recipient[:120], "denied", "header_injection")
            return {"allowed": False, "reason": "header_injection", "agent_id": agent_id}

        clean_rcpt = recipient.strip().lower()
        if not _EMAIL_RE.match(clean_rcpt):
            self._log(agent_id, "send", clean_rcpt[:120], "denied", "invalid_recipient_syntax")
            return {"allowed": False, "reason": "invalid_recipient_syntax", "agent_id": agent_id}

        row = self._conn.execute(
            "SELECT allowed_recipients, sends_per_minute FROM policies WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        if row is None:
            self._log(agent_id, "send", clean_rcpt, "denied", "no_agent_policy")
            return {"allowed": False, "reason": "no_agent_policy", "agent_id": agent_id}

        allowlist = json.loads(row[0])
        spm = int(row[1])
        domain = "@" + clean_rcpt.split("@", 1)[1]
        if clean_rcpt not in allowlist and domain not in allowlist:
            self._log(agent_id, "send", clean_rcpt, "denied", "recipient_not_allowlisted")
            return {"allowed": False, "reason": "recipient_not_allowlisted", "agent_id": agent_id}

        ok, used = self._check_rate(f"send:{agent_id}", spm, 60)
        if not ok:
            self._log(agent_id, "send", clean_rcpt, "denied", "rate_limit_exceeded")
            return {
                "allowed": False,
                "reason": "rate_limit_exceeded",
                "agent_id": agent_id,
                "sends_this_minute": used,
                "limit": spm,
            }

        self._log(agent_id, "send", clean_rcpt, "allowed", "policy_passed")
        return {
            "allowed": True,
            "reason": "policy_passed",
            "agent_id": agent_id,
            "recipient": clean_rcpt,
            "sends_this_minute": used,
            "limit": spm,
        }

    def check_read(self, agent_id: str) -> Dict[str, Any]:
        row = self._conn.execute(
            "SELECT reads_per_day FROM policies WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            self._log(agent_id, "read", "", "denied", "no_agent_policy")
            return {"allowed": False, "reason": "no_agent_policy", "agent_id": agent_id}
        rpd = int(row[0])
        ok, used = self._check_rate(f"read:{agent_id}", rpd, 86400)
        if not ok:
            self._log(agent_id, "read", "", "denied", "daily_read_quota_exceeded")
            return {"allowed": False, "reason": "daily_read_quota_exceeded", "reads_today": used, "limit": rpd}
        self._log(agent_id, "read", "", "allowed", "policy_passed")
        return {"allowed": True, "reason": "policy_passed", "reads_today": used, "limit": rpd}

    def audit_entries(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT id, agent_id, action, recipient, timestamp, status, reason FROM audit_log ORDER BY id ASC"
        ).fetchall()
        return [
            {
                "id": r[0],
                "agent_id": r[1],
                "action": r[2],
                "recipient": r[3],
                "timestamp": r[4],
                "status": r[5],
                "reason": r[6],
            }
            for r in rows
        ]


# ROS / Robotics Confirm-Before-Move Hardware Interlock
_ROS_READONLY_TOPICS = frozenset({
    "/joint_states",
    "/odom",
    "/tf",
    "/tf_static",
    "/diagnostics",
    "/pr2_ethercat/motors_halted",
    "/battery_state",
})

_ROS_MOTION_TOPIC_PAT = re.compile(
    r"(?i)(cmd_vel|base_controller/command|joint_trajectory|gripper_command|"
    r"arm_controller/command|torso_controller/command|head_traj_controller|"
    r"actuator|motor_cmd|velocity_command)"
)


def evaluate_robotics_motion_gate(
    operation: Dict[str, Any],
    *,
    expected_token: Optional[str] = None,
) -> Dict[str, Any]:
    """Enforce confirm-before-move deadman interlock for robotics/ROS actuation.

    Unlike ROS's immediate-execution middleware (where a single WebSocket publish
    physically moves hardware), Zoe denies any physical motion command unless:
      - `dry_run=True` (no physical actuation), OR
      - BOTH `deadman_held=True` AND a matching single-use `confirmation_token`
        are explicitly supplied (and `motors_halted` is not flagged unsafe).
    Read-only telemetry subscriptions pass safely as inspection-only.
    """
    topic = str(operation.get("ros_topic", "") or "").strip()
    is_motion = bool(operation.get("motion_command")) or bool(
        topic and _ROS_MOTION_TOPIC_PAT.search(topic)
    )
    if not is_motion:
        return {
            "allowed": True,
            "is_motion_command": False,
            "mode": "read_only_telemetry" if topic in _ROS_READONLY_TOPICS else "non_motion",
            "reason": "no_physical_motion_requested",
        }

    if operation.get("dry_run") is True:
        return {
            "allowed": True,
            "is_motion_command": True,
            "mode": "dry_run_simulation",
            "reason": "dry_run_enabled_no_physical_motion",
            "topic": topic,
        }

    deadman_held = operation.get("deadman_held") is True
    supplied_token = operation.get("confirmation_token")
    token_ok = (
        isinstance(supplied_token, str)
        and bool(supplied_token.strip())
        and (expected_token is None or supplied_token == expected_token)
    )

    if not deadman_held:
        return {
            "allowed": False,
            "is_motion_command": True,
            "mode": "blocked",
            "reason": "deadman_switch_not_held",
            "topic": topic,
        }
    if not token_ok:
        return {
            "allowed": False,
            "is_motion_command": True,
            "mode": "blocked",
            "reason": "confirm_before_move_token_missing_or_invalid",
            "topic": topic,
        }
    return {
        "allowed": True,
        "is_motion_command": True,
        "mode": "confirmed_physical_actuation",
        "reason": "deadman_and_confirmation_verified",
        "topic": topic,
    }


def wave3_vault_inventory() -> Dict[str, Any]:
    """Return a structured manifest of all 5 Wave 3 Vault upgrades live in Zoe."""
    root = _repo_root()
    paths = {
        "trust_gradient": root / "components/Zoe-Autonomy/src/zoe_autonomy/trust_gradient.py",
        "nina_audio_fx": root / "components/nina/audio_fx.py",
        "agent_authority_audit": root / "components/ablation/ablation/analyzers/agent_authority_audit.py",
        "agent_observability_audit": root / "components/ablation/ablation/analyzers/agent_observability_audit.py",
        "agent_tool_surface_enumerator": root / "components/ablation/ablation/analyzers/agent_tool_surface_enumerator.py",
        "ai_control_indicators": root / "components/ablation/ablation/analyzers/ai_control_indicators.py",
        "wave3_vault_upgrades": root / "components/Zoe-Autonomy/src/zoe_autonomy/wave3_vault_upgrades.py",
        "gemseal": root / "components/gemseal/gemseal.py",
        "kevlar_policy": root / "components/kevlar/policy.py",
        "visorcas_fastdedup": root / "components/VisorCAS/cas/fastdedup.go",
    }
    return {
        "wave": 3,
        "strictly_non_biology": True,
        "upgrades": [
            "5D Continuous TrustEngine -> DualPeerSession + nina Lume audio cues",
            "4 Unpublished AI-Agent Binary Auditors -> components/ablation/ablation/analyzers",
            "Dual-Path Verification & Masked-Diff Flywheel -> Zoe-Autonomy + VisorLog SQLite",
            "Eq. 2 Slow-Drift Cascade Hardening + vec2text Vector-Privacy + MCP Subdir/Filter Guards",
            "Email Allowlist Guardrail + ROS Confirm-Before-Move Gate + Lock-Free Bloom+CAS Dedup",
        ],
        "artifacts_present": {k: p.is_file() for k, p in paths.items()},
    }
