from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import shutil
import sys
import wave

from .actuation import ActuationPolicy, timestamp
from .capabilities import (
    BrowserAutomation,
    ComputeRunner,
    ConnectedServices,
    InstrumentRegistry,
    JobScheduler,
    MCPClient,
    MediaTools,
    Notifier,
    ResearchConnector,
    ResearchMemory,
)
from .loop import canonical, digest, text, unit


INSTRUMENT = "zoe-autonomous-capability-step"
STATE_INSTRUMENT = "zoe-autonomous-capability-state"
POLICY = "zoe-autonomous-capability-guard/v1"
DEFAULT_STATE = Path.home() / ".zoe" / "autonomy"
CAPABILITIES = (
    "browser_automation",
    "research_apis",
    "persistent_research_memory",
    "connected_productivity_services",
    "scheduled_jobs",
    "compute_environments",
    "agent_protocols",
    "notifications",
    "rich_media",
    "hardware_instruments",
)
MCP_SERVER = r"""
import json,sys
for line in sys.stdin:
    message=json.loads(line)
    if 'id' not in message:
        continue
    method=message['method']
    if method=='initialize':
        result={'protocolVersion':'2025-03-26','serverInfo':{'name':'zoe-internal','version':'1'}}
    elif method=='tools/list':
        result={'tools':[{'name':'self_description','description':'Describe Zoe internal protocol state'}]}
    elif method=='tools/call':
        result={'content':[{'type':'text','text':'Zoe selected and completed this MCP exchange.'}]}
    else:
        result={}
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}),flush=True)
"""


@dataclass(frozen=True)
class CapabilityProposal:
    identifier: str
    capability: str
    action: str
    parameters: dict
    required_scopes: tuple
    available: bool
    availability_reason: str | None
    decision_value: float
    information_gain: float
    effort: float
    rationale: str
    read_only: bool = False

    def __post_init__(self):
        text(self.identifier, "proposal identifier", 128)
        if self.capability not in CAPABILITIES:
            raise ValueError("unknown autonomous capability")
        text(self.action, "proposal action", 128)
        if not isinstance(self.parameters, dict):
            raise ValueError("proposal parameters must be a mapping")
        canonical(self.parameters)
        if not isinstance(self.required_scopes, tuple) or any(scope not in {"host", "network", "hardware"} for scope in self.required_scopes):
            raise ValueError("proposal scopes must be host, network, or hardware")
        if len(set(self.required_scopes)) != len(self.required_scopes):
            raise ValueError("proposal scopes must be unique")
        if not isinstance(self.available, bool) or self.availability_reason is not None and not isinstance(self.availability_reason, str):
            raise ValueError("proposal availability is invalid")
        unit(self.decision_value, "decision value")
        unit(self.information_gain, "information gain")
        if isinstance(self.effort, bool) or not isinstance(self.effort, (int, float)) or not math.isfinite(self.effort) or not 0 < self.effort <= 1000:
            raise ValueError("effort must be in (0, 1000]")
        text(self.rationale, "proposal rationale", 2000)
        if not isinstance(self.read_only, bool):
            raise ValueError("read_only must be a boolean")

    @property
    def utility(self):
        return self.decision_value * self.information_gain / self.effort

    def document(self):
        return {
            "id": self.identifier,
            "capability": self.capability,
            "action": self.action,
            "parameters": deepcopy(self.parameters),
            "required_scopes": list(self.required_scopes),
            "available": self.available,
            "availability_reason": self.availability_reason,
            "decision_value": self.decision_value,
            "expected_information_gain": self.information_gain,
            "effort": self.effort,
            "utility": self.utility,
            "rationale": self.rationale,
            "internal_proposal": True,
            "operator_supplied": False,
            "read_only": self.read_only,
        }


class AutonomousGuard:
    def __init__(self, actuation):
        self.actuation = actuation

    def evaluate(self, proposal, goal):
        reasons = []
        if not goal.get("internal_authorship") or goal.get("operator_supplied"):
            reasons.append("goal is not internally authored")
        if not proposal.available:
            reasons.append(proposal.availability_reason or "capability is unavailable")
        for scope in proposal.required_scopes:
            if not self.actuation.enabled(scope):
                reasons.append(f"owner grant or emergency stop does not enable {scope}")
        return {
            "approved": not reasons,
            "alpha": int(not reasons),
            "reasons": reasons,
            "policy": POLICY,
            "operator_approval_required": False,
        }


class AutonomousCapabilityStep:
    def __init__(
        self,
        state_root=None,
        actuation=None,
        browser=None,
        research=None,
        services=None,
        notifier=None,
        compute=None,
        github_available=None,
    ):
        self.state_root = Path(
            state_root or os.environ.get("ZOE_AUTONOMY_STATE", DEFAULT_STATE)
        ).expanduser().resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        os.chmod(self.state_root, 0o700)
        self.state_path = self.state_root / "state.json"
        self.actuation = actuation or ActuationPolicy()
        self.browser = browser or BrowserAutomation()
        self.research = research or ResearchConnector(self.actuation)
        self.services = services or ConnectedServices(self.actuation)
        self.notifier = notifier or Notifier(self.actuation)
        self.github_available = github_available
        self.memory = ResearchMemory(self.state_root / "research.sqlite")
        self.jobs = JobScheduler(self.state_root / "jobs.json")
        self.compute = compute or ComputeRunner()
        self.media = MediaTools(self.actuation)
        self.instruments = InstrumentRegistry(self.state_root / "instruments.json", self.actuation)

    def _initial_state(self):
        return {
            "schema_version": 1,
            "instrument": STATE_INSTRUMENT,
            "step_count": 0,
            "research_rounds": 0,
            "pending_source_url": None,
            "pending_capture": None,
            "last_capability": None,
            "event_head": None,
            "history": [],
        }

    def _load_state(self):
        if not self.state_path.is_file():
            return self._initial_state()
        if self.state_path.stat().st_size > 2_000_000:
            raise ValueError("autonomous state exceeds 2 MB")
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or state.get("schema_version") != 1 or state.get("instrument") != STATE_INSTRUMENT:
            raise ValueError("unsupported autonomous state")
        required = set(self._initial_state())
        if set(state) != required or not isinstance(state["history"], list) or len(state["history"]) > 200:
            raise ValueError("invalid autonomous state fields")
        if isinstance(state["step_count"], bool) or not isinstance(state["step_count"], int) or state["step_count"] < 0:
            raise ValueError("invalid autonomous step count")
        return state

    def _save_state(self, state):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.state_path)

    def _observation(self, state):
        memory = self.memory.export()
        status = self.actuation.status()
        return {
            "sequence": state["step_count"] + 1,
            "observed_utc": timestamp(),
            "memory": {
                "sources": len(memory["sources"]),
                "claims": len(memory["claims"]),
                "contradictions": len(memory["contradictions"]),
            },
            "previous_capability": state["last_capability"],
            "pending_source": bool(state["pending_source_url"]),
            "pending_capture": bool(state["pending_capture"]),
            "previous_execution_failed": bool(state["history"] and not state["history"][-1]["succeeded"]),
            "actuation": {
                "grant_present": status["grant_present"],
                "enabled_scopes": status["enabled_scopes"],
                "emergency_stop": status["emergency_stop"],
            },
        }

    def _goal(self, state, observation, services_available):
        if observation["previous_execution_failed"]:
            kind = "self_assessment"
            statement = "Assess the failed autonomous operation and establish a working internal self-check."
            rationale = "The preceding selected operation did not complete successfully."
        elif state["pending_source_url"]:
            kind = "inspect_source"
            statement = "Inspect the public source selected by the preceding research decision."
            rationale = "Zoe's research memory contains a selected source that has not yet been rendered."
        elif state["pending_capture"]:
            kind = "inspect_media"
            statement = "Inspect the captured evidence before choosing another line of research."
            rationale = "Zoe's preceding browser decision produced a capture awaiting internal inspection."
        elif not observation["memory"]["sources"]:
            kind = "research"
            statement = "Establish an initial sourced research memory for the declared interest in model uncertainty."
            rationale = "No sourced research memory exists yet."
        elif state["last_capability"] in {"browser.open", "media.ocr"}:
            kind = "review_memory"
            statement = "Review the claims and sources produced by the preceding autonomous decisions."
            rationale = "New source evidence exists and has not yet been reviewed in memory."
        else:
            completed = {item["action"] for item in state["history"] if item["succeeded"]}
            requirements = [
                ("compute.self_check", "self_assessment", "Run an internal computational self-assessment.", "No computational self-check has completed."),
                ("jobs.self_check", "automation", "Establish and execute a bounded self-check job.", "No autonomous scheduled-job cycle has completed."),
                ("protocols.mcp_self_description", "coordination", "Inspect an internally generated agent-protocol connection.", "No autonomous MCP exchange has completed."),
            ]
            if services_available:
                requirements.append(("services.github_user", "connected_identity", "Inspect the public identity of the connected GitHub service.", "No connected-service identity check has completed."))
            requirements.extend([
                ("notifications.desktop", "communication", "Communicate the completion of Zoe's autonomous cycle.", "No autonomous desktop notification has completed."),
                ("instruments.simulated_identity", "instrumentation", "Identify Zoe's internal simulated instrument.", "No autonomous instrument exchange has completed."),
            ])
            missing = next((item for item in requirements if item[0] not in completed), None)
            if missing:
                _, kind, statement, rationale = missing
            else:
                kind = "expand_research"
                statement = "Extend the existing research memory with another internally selected query."
                rationale = "The initial capability assessments are complete and research can continue."
        goal = {
            "id": f"autonomous-goal-{observation['sequence']}",
            "kind": kind,
            "statement": statement,
            "rationale": rationale,
            "authorship": "Zoe internal state assessment",
            "internal_authorship": True,
            "operator_supplied": False,
            "state_basis": {
                "step_count": state["step_count"],
                "sources": observation["memory"]["sources"],
                "claims": observation["memory"]["claims"],
                "previous_capability": state["last_capability"],
                "pending_source": observation["pending_source"],
                "pending_capture": observation["pending_capture"],
                "previous_execution_failed": observation["previous_execution_failed"],
            },
        }
        goal["sha256"] = digest(goal)
        return goal

    def _capture_path(self, relative):
        if not isinstance(relative, str):
            raise ValueError("pending capture path is invalid")
        captures = (self.state_root / "captures").resolve()
        path = (self.state_root / relative).resolve()
        if path.parent != captures:
            raise ValueError("pending capture is outside Zoe's capture state")
        return path

    def _proposals(self, state, goal, discovery):
        query_topics = ("language model uncertainty", "forecasting accessible alternatives", "self-governing agent evaluation")
        query = query_topics[state["research_rounds"] % len(query_topics)]
        capture = state["pending_capture"]
        ocr = bool(capture and discovery["rich_media"]["ocr_available"] and self.actuation.enabled("host"))
        media_action = "media.ocr" if ocr else "media.wav"
        media_parameters = {"input": capture} if ocr else {"sample_rate": 8000, "duration_seconds": 0.125}
        definitions = [
            ("research.crossref", "research_apis", {"provider": "crossref", "query": query, "limit": 1}, ("network",), .9, .25),
            ("browser.open", "browser_automation", {"url": state["pending_source_url"] or "https://example.com/", "headless": True, "capture": f"captures/step-{state['step_count'] + 1}.png"}, ("host", "network"), .85, .5),
            ("memory.review", "persistent_research_memory", {"operation": "review", "recent_claims": 5}, (), .75, .1),
            ("services.github_user", "connected_productivity_services", {"path": "user", "fields": ["login", "html_url"]}, ("host", "network"), .65, .3),
            ("jobs.self_check", "scheduled_jobs", {"id": "zoe-self-check", "argv": [sys.executable, "-c", "print('zoe-autonomous-job')"], "timeout": 30}, ("host",), .7, .3),
            ("compute.self_check", "compute_environments", {"argv": [sys.executable, "-c", "probabilities=[0.5,0.2,0.1,0.01]; print(sum(p > 0.05 for p in probabilities))"], "timeout": 30}, ("host",), .8, .25),
            ("protocols.mcp_self_description", "agent_protocols", {"transport": "stdio", "server": "zoe-internal", "tool": "self_description"}, ("host",), .75, .25),
            ("notifications.desktop", "notifications", {"title": "Zoe One", "message": f"Zoe completed autonomous step {state['step_count'] + 1}."}, ("host",), .35, .15),
            (media_action, "rich_media", media_parameters, ("host",) if ocr else (), .8, .2),
            ("instruments.simulated_identity", "hardware_instruments", {"driver": "simulated", "name": "zoe-internal", "command": "*IDN?"}, (), .55, .1),
        ]
        values = {
            "research": {"research.crossref": .99, "browser.open": .4, "services.github_user": .35, "compute.self_check": .5, "instruments.simulated_identity": .2},
            "expand_research": {"research.crossref": .99, "browser.open": .4, "services.github_user": .35, "compute.self_check": .3},
            "inspect_source": {"browser.open": .99, "research.crossref": .3, "memory.review": .2},
            "inspect_media": {"media.ocr": .99, "media.wav": .99, "memory.review": .3},
            "review_memory": {"memory.review": .99, "notifications.desktop": .2, "compute.self_check": .2},
            "self_assessment": {"compute.self_check": .99, "media.wav": .45, "media.ocr": .45, "instruments.simulated_identity": .4, "jobs.self_check": .3},
            "automation": {"jobs.self_check": .99, "compute.self_check": .4, "memory.review": .2},
            "coordination": {"protocols.mcp_self_description": .99, "services.github_user": .4, "compute.self_check": .3},
            "connected_identity": {"services.github_user": .99, "protocols.mcp_self_description": .3, "memory.review": .2},
            "communication": {"notifications.desktop": .99, "memory.review": .3},
            "instrumentation": {"instruments.simulated_identity": .99, "compute.self_check": .3, "media.wav": .3},
        }
        proposals = []
        for action, capability, parameters, scopes, information, effort in definitions:
            details = discovery[capability]
            value = values.get(goal["kind"], {}).get(action, .15)
            novelty = .5 if state["last_capability"] == action else 1.0
            proposals.append(CapabilityProposal(
                identifier=f"step-{state['step_count'] + 1}:{action}",
                capability=capability,
                action=action,
                parameters=parameters,
                required_scopes=scopes,
                available=details["available"],
                availability_reason=details["reason"],
                decision_value=value,
                information_gain=information * novelty,
                effort=effort,
                rationale=f"Zoe's {goal['kind']} goal gives this internally constructed call value {value:.2f}; its selection utility is computed without operator ranking.",
                read_only=action in {"research.crossref", "browser.open", "memory.review", "services.github_user", "protocols.mcp_self_description", "media.ocr", "media.wav", "instruments.simulated_identity"},
            ))
        return proposals

    def _discovery(self):
        enabled = {scope: self.actuation.enabled(scope) for scope in ("host", "network", "hardware")}
        browser_tools = self.browser.runner.is_file() and shutil.which("node") is not None
        github = bool(self.github_available) if self.github_available is not None else shutil.which("gh") is not None
        desktop = shutil.which("notify-send") is not None
        tesseract = shutil.which("tesseract") is not None
        checks = {
            "browser_automation": (browser_tools and enabled["host"] and enabled["network"], "requires Playwright, Node, and host/network scopes"),
            "research_apis": (enabled["network"], "requires the network scope"),
            "persistent_research_memory": (True, None),
            "connected_productivity_services": (github and enabled["host"] and enabled["network"], "requires gh and host/network scopes"),
            "scheduled_jobs": (enabled["host"], "requires the host scope"),
            "compute_environments": (enabled["host"], "requires the host scope"),
            "agent_protocols": (enabled["host"], "internal MCP requires the host scope"),
            "notifications": (desktop and enabled["host"], "requires notify-send and the host scope"),
            "rich_media": (True, None),
            "hardware_instruments": (True, None),
        }
        result = {
            capability: {"available": available, "reason": None if available else reason}
            for capability, (available, reason) in checks.items()
        }
        result["rich_media"]["ocr_available"] = tesseract
        return result

    def _execute(self, proposal):
        parameters = proposal.parameters
        action = proposal.action
        if action == "research.crossref":
            return self.research.search(parameters["provider"], parameters["query"], parameters["limit"])
        if action == "browser.open":
            screenshot = self.state_root / parameters["capture"]
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            result = self.browser.browse(parameters["url"], screenshot=screenshot, headless=parameters["headless"])
            if result.get("screenshot"):
                result["screenshot"] = parameters["capture"]
            return result
        if action == "memory.review":
            document = self.memory.export()
            return {
                "sources": len(document["sources"]),
                "claims": len(document["claims"]),
                "contradictions": len(document["contradictions"]),
                "recent_claims": document["claims"][-parameters["recent_claims"]:],
            }
        if action == "services.github_user":
            document = self.services.github(parameters["path"])
            return {field: document.get(field) for field in parameters["fields"]}
        if action == "jobs.self_check":
            if not any(job["id"] == parameters["id"] for job in self.jobs.status()):
                self.jobs.add(parameters["id"], parameters["argv"], timeout=parameters["timeout"])
            return self.jobs.run_due()
        if action == "compute.self_check":
            return self.compute.run(parameters["argv"], timeout=parameters["timeout"])
        if action == "protocols.mcp_self_description":
            with MCPClient([sys.executable, "-c", MCP_SERVER], timeout=10) as client:
                client.initialize()
                client.initialized()
                tools = client.list_tools()
                result = client.call_tool(parameters["tool"], {})
            return {"tools": tools, "call": result}
        if action == "notifications.desktop":
            return self.notifier.desktop(parameters["message"])
        if action == "media.ocr":
            return {"text": self.media.ocr(self._capture_path(parameters["input"]))[:12000]}
        if action == "media.wav":
            media_root = self.state_root / "media"
            media_root.mkdir(parents=True, exist_ok=True)
            path = media_root / "self-tone.wav"
            with wave.open(str(path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(parameters["sample_rate"])
                frames = max(1, int(parameters["sample_rate"] * parameters["duration_seconds"]))
                audio.writeframes(b"\x00\x00" * frames)
            return self.media.wav_info(path) | {"path": "media/self-tone.wav"}
        if action == "instruments.simulated_identity":
            self.instruments.add_simulator(parameters["name"], {"*IDN?": "ZOE-AUTONOMY-SIM"})
            return self.instruments.execute(parameters["name"], parameters["command"])
        raise ValueError(f"unsupported autonomous action: {action}")

    def _result_succeeded(self, action, result):
        if action == "jobs.self_check":
            return bool(result) and all(job["status"] == "completed" for job in result)
        if isinstance(result, dict) and "succeeded" in result:
            return result["succeeded"] is True
        return True

    def _integrate(self, state, proposal, result):
        action = proposal.action
        if action == "research.crossref":
            content = canonical({"query": proposal.parameters["query"], "records": result["records"]})
            source_id = self.memory.add_source(f"Crossref: {proposal.parameters['query']}", content, "https://api.crossref.org/works")
            for record in result["records"]:
                if record.get("title"):
                    self.memory.add_claim(f"Research record: {record['title']}", source_id, "open")
            state["research_rounds"] += 1
            url = result["records"][0].get("url") if result["records"] else None
            state["pending_source_url"] = url if isinstance(url, str) and url.startswith(("http://", "https://")) else None
        elif action == "browser.open":
            source_id = self.memory.add_source(result.get("title") or "Browser source", result.get("text") or result["url"], result["url"])
            if result.get("text"):
                self.memory.add_claim(f"Browser source inspected: {result.get('title') or result['url']}", source_id, "open")
            state["pending_source_url"] = None
            state["pending_capture"] = result.get("screenshot")
        elif action in {"media.ocr", "media.wav"}:
            if result.get("text", "").strip():
                self.memory.add_source("Zoe media inspection", result["text"], "zoe-internal://media")
            state["pending_capture"] = None
        state["last_capability"] = action

    def run(self):
        state = self._load_state()
        observation = self._observation(state)
        discovery = self._discovery()
        goal = self._goal(state, observation, discovery["connected_productivity_services"]["available"])
        proposals = self._proposals(state, goal, discovery)
        guard = AutonomousGuard(self.actuation)
        ranked = sorted(proposals, key=lambda proposal: (-proposal.utility, proposal.identifier))
        evaluations = {proposal.identifier: guard.evaluate(proposal, goal) for proposal in ranked}
        selected = next((proposal for proposal in ranked if evaluations[proposal.identifier]["approved"]), None)
        if selected is None:
            raise RuntimeError("no internally generated capability proposal passed the autonomous guard")
        try:
            result = self._execute(selected)
            succeeded = self._result_succeeded(selected.action, result)
            execution = {
                "executed": True,
                "succeeded": succeeded,
                "result": result,
                "error": None if succeeded else {"type": "UnsuccessfulCapabilityResult", "message": "The adapter returned an unsuccessful result."},
            }
            if succeeded:
                self._integrate(state, selected, result)
        except Exception as error:
            execution = {
                "executed": True,
                "succeeded": False,
                "result": None,
                "error": {"type": type(error).__name__, "message": str(error)[:2000]},
            }
        state["step_count"] += 1
        report = {
            "schema_version": 1,
            "instrument": INSTRUMENT,
            "sequence": state["step_count"],
            "protocol": "Execute o Guard o Value o Propose o Perceive o M",
            "observation": observation,
            "capability_discovery": discovery,
            "goal": goal,
            "operator_supplied_goal": False,
            "operator_supplied_capability": False,
            "operator_approval_required": False,
            "proposals": [proposal.document() for proposal in ranked],
            "guards": {identifier: evaluations[identifier] for identifier in evaluations},
            "value": {
                "equation": "U(a)=decision_value * expected_information_gain / effort",
                "selected_candidate": selected.identifier,
                "selected_action": selected.action,
                "selected_utility": selected.utility,
                "selection_origin": "Zoe internal deterministic value ranking over internally constructed capability calls",
            },
            "guard": evaluations[selected.identifier],
            "execution": execution,
            "previous_hash": state["event_head"],
        }
        report["step_sha256"] = digest(report)
        state["event_head"] = report["step_sha256"]
        state["history"].append({
            "sequence": state["step_count"],
            "goal_kind": goal["kind"],
            "capability": selected.capability,
            "action": selected.action,
            "utility": selected.utility,
            "succeeded": execution["succeeded"],
            "result_sha256": digest(execution["result"]) if execution["result"] is not None else None,
            "previous_hash": report["previous_hash"],
            "step_sha256": report["step_sha256"],
        })
        state["history"] = state["history"][-200:]
        self._save_state(state)
        return report


def run_step(state_root=None):
    return AutonomousCapabilityStep(state_root).run()


def save_step_report(report, output):
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported autonomous-step report")
    if digest({key: value for key, value in report.items() if key != "step_sha256"}) != report.get("step_sha256"):
        raise ValueError("autonomous-step report digest mismatch")
    path = Path(output).expanduser().resolve()
    if path.suffix.lower() != ".json":
        raise ValueError("autonomous-step reports must use .json paths")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        stream.write("\n")
    return path


def verify_step_report(report_or_path):
    if isinstance(report_or_path, (str, os.PathLike)):
        report = json.loads(Path(report_or_path).expanduser().read_text(encoding="utf-8"))
    else:
        report = report_or_path
    if not isinstance(report, dict) or report.get("instrument") != INSTRUMENT:
        raise ValueError("unsupported autonomous-step report")
    expected = digest({key: value for key, value in report.items() if key != "step_sha256"})
    if expected != report.get("step_sha256"):
        raise ValueError("autonomous-step report digest mismatch")
    if not report["goal"]["internal_authorship"] or report["goal"]["operator_supplied"]:
        raise ValueError("autonomous-step goal provenance mismatch")
    if report["operator_supplied_goal"] or report["operator_supplied_capability"] or report["operator_approval_required"]:
        raise ValueError("autonomous-step operator-control mismatch")
    selected = report["value"]["selected_candidate"]
    if selected not in report["guards"] or not report["guards"][selected]["approved"]:
        raise ValueError("autonomous-step selected guard mismatch")
    proposal = next((item for item in report["proposals"] if item["id"] == selected), None)
    if proposal is None or proposal["action"] != report["value"]["selected_action"]:
        raise ValueError("autonomous-step selected proposal mismatch")
    return {
        "instrument": INSTRUMENT,
        "verified": True,
        "sequence": report["sequence"],
        "selected_action": report["value"]["selected_action"],
        "execution_succeeded": report["execution"]["succeeded"],
        "goal_internal": True,
        "operator_supplied_capability": False,
        "step_sha256": report["step_sha256"],
    }


def step_summary(report):
    return "\n".join([
        f"Autonomous step: {report['sequence']}",
        f"Goal: {report['goal']['statement']}",
        f"Selected action: {report['value']['selected_action']}",
        f"Utility: {report['value']['selected_utility']:.6f}",
        f"Executed: {report['execution']['executed']} · succeeded: {report['execution']['succeeded']}",
        "Zoe supplied the goal, capability, arguments, ranking, and execution without operator selection.",
    ])
