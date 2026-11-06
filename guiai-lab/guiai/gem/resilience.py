from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap

from .atlas import _ellipse, _line, _scene, _text
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


CISA_ROOT = "https://www.cisa.gov/topics/critical-infrastructure-security-and-resilience/critical-infrastructure-sectors"
SECTORS = {
    "chemical": {
        "name": "Chemical", "short": "Chemical", "url": f"{CISA_ROOT}/chemical-sector",
        "why": "Chemical production and transportation support products used throughout modern life and other infrastructure sectors.",
        "depends_on": ["transportation", "energy", "water", "critical-manufacturing"],
    },
    "commercial": {
        "name": "Commercial Facilities", "short": "Commercial", "url": f"{CISA_ROOT}/commercial-facilities-sector",
        "why": "Open-access places for shopping, business, entertainment, and lodging bring people together and require continuity and safe operation.",
        "depends_on": ["energy", "communications", "emergency", "transportation"],
    },
    "communications": {
        "name": "Communications", "short": "Comms", "url": f"{CISA_ROOT}/communications-sector",
        "why": "Communications enable business, government, public safety, coordination, and recovery across every other sector.",
        "depends_on": ["energy", "information-technology", "financial", "emergency", "transportation"],
    },
    "critical-manufacturing": {
        "name": "Critical Manufacturing", "short": "Manufacture", "url": f"{CISA_ROOT}/critical-manufacturing-sector",
        "why": "Manufacturing supplies essential metals, machinery, electrical equipment, and transportation equipment across interdependent supply chains.",
        "depends_on": ["transportation", "energy", "chemical", "water"],
    },
    "dams": {
        "name": "Dams", "short": "Dams", "url": f"{CISA_ROOT}/dams-sector",
        "why": "Dams and levees support water retention, flood control, irrigation, navigation, hydropower, and other essential services.",
        "depends_on": ["communications", "energy", "food", "transportation", "water"],
    },
    "defense": {
        "name": "Defense Industrial Base", "short": "Defense", "url": f"{CISA_ROOT}/defense-industrial-base-sector",
        "why": "The defense industrial base supplies research, production, delivery, and maintenance for military requirements and depends on commercial infrastructure owned by other sectors.",
        "depends_on": ["energy", "communications", "transportation", "critical-manufacturing"],
    },
    "emergency": {
        "name": "Emergency Services", "short": "Emergency", "url": f"{CISA_ROOT}/emergency-services-sector",
        "why": "Emergency management, medical services, fire and rescue, law enforcement, and public works protect life and support recovery.",
        "depends_on": ["communications", "energy", "transportation", "water", "healthcare"],
    },
    "energy": {
        "name": "Energy", "short": "Energy", "url": f"{CISA_ROOT}/energy-sector",
        "why": "Electricity, oil, and natural gas provide an enabling function for homes, industry, public health, and every other infrastructure sector.",
        "depends_on": ["communications", "transportation", "water", "critical-manufacturing"],
    },
    "financial": {
        "name": "Financial Services", "short": "Finance", "url": f"{CISA_ROOT}/financial-services-sector",
        "why": "Financial services support deposits, payments, credit, liquidity, investment, and the transfer of financial risk.",
        "depends_on": ["communications", "energy", "information-technology", "transportation"],
    },
    "food": {
        "name": "Food and Agriculture", "short": "Food", "url": f"{CISA_ROOT}/food-and-agriculture-sector",
        "why": "Food production, processing, storage, and distribution depend on clean water, transportation, energy, and agricultural chemicals.",
        "depends_on": ["water", "transportation", "energy", "chemical"],
    },
    "government": {
        "name": "Government Services and Facilities", "short": "Govt", "url": f"{CISA_ROOT}/government-facilities-sector",
        "why": "Government facilities support public functions, education, sensitive work, national laboratories, monuments, and essential knowledge.",
        "depends_on": ["energy", "communications", "information-technology", "transportation"],
    },
    "healthcare": {
        "name": "Healthcare and Public Health", "short": "Health", "url": f"{CISA_ROOT}/healthcare-and-public-health-sector",
        "why": "Healthcare and public health protect people from disease, disasters, and other hazards while depending on communications, energy, food, transport, and water.",
        "depends_on": ["communications", "emergency", "energy", "food", "information-technology", "transportation", "water"],
    },
    "information-technology": {
        "name": "Information Technology", "short": "IT", "url": f"{CISA_ROOT}/information-technology-sector",
        "why": "Distributed hardware, software, systems, and services underpin security, the economy, public health, safety, and the Internet.",
        "depends_on": ["communications", "energy", "critical-manufacturing"],
    },
    "nuclear": {
        "name": "Nuclear Reactors, Materials and Waste", "short": "Nuclear", "url": f"{CISA_ROOT}/nuclear-reactors-materials-and-waste-sector",
        "why": "Nuclear facilities, materials, and waste require specialized regulation, safety, environmental protection, and emergency preparedness.",
        "depends_on": ["energy", "water", "transportation", "emergency", "government"],
    },
    "transportation": {
        "name": "Transportation Systems", "short": "Transport", "url": f"{CISA_ROOT}/transportation-systems-sector",
        "why": "Aviation, roads, maritime systems, rail, pipelines, and postal networks move people and goods safely and securely.",
        "depends_on": ["energy", "communications", "information-technology", "critical-manufacturing"],
    },
    "water": {
        "name": "Water and Wastewater Systems", "short": "Water", "url": "https://www.cisa.gov/water-and-wastewater-systems-sector",
        "why": "Safe drinking water and effective wastewater treatment protect public health, support human activity, and prevent disease and environmental harm.",
        "depends_on": ["energy", "critical-manufacturing", "healthcare", "communications"],
    },
}
CLOCK_CANDIDATES = (
    {"name": "endeavour_tb.clk", "period_ps": 12500, "initial": 1},
    {"name": "endeavour_tb.clk40", "period_ps": 25000, "initial": 1},
    {"name": "endeavour_tb.clk_amac", "period_ps": 25000, "initial": 1},
)


@dataclass(frozen=True)
class SignalTrace:
    storage_id: str
    events: tuple[tuple[int, int], ...]

    def __post_init__(self):
        if not isinstance(self.storage_id, str) or not 1 <= len(self.storage_id) <= 64:
            raise ValueError("storage ID must contain 1-64 characters")
        if not isinstance(self.events, tuple) or not 32 <= len(self.events) <= 64:
            raise ValueError("a trace requires 32-64 initial events")
        previous = -1
        for event in self.events:
            if not isinstance(event, tuple) or len(event) != 2:
                raise ValueError("events must contain timestamp and binary payload pairs")
            timestamp, payload = event
            if isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp <= previous:
                raise ValueError("event timestamps must be strictly increasing integers")
            if payload not in {0, 1} or isinstance(payload, bool):
                raise ValueError("clock evidence requires binary payloads")
            previous = timestamp


def clock_candidates(trace):
    if not isinstance(trace, SignalTrace):
        raise ValueError("clock candidates require a signal trace")
    matches = []
    for candidate in CLOCK_CANDIDATES:
        period = candidate["period_ps"]
        matches_signature = (
            trace.events[0][1] == candidate["initial"]
            and all(
                event[1] == (1 - index % 2 if candidate["initial"] else index % 2)
                and event[0] - trace.events[index - 1][0] == period / 2
                for index, event in enumerate(trace.events[1:33], 1)
            )
        )
        if matches_signature:
            matches.append(candidate)
    return matches


def classify_trace(trace):
    matches = clock_candidates(trace)
    if len(matches) == 1:
        status = "corroborated"
    elif matches:
        status = "ambiguous"
    else:
        status = "unmapped"
    return {
        "storage_id": trace.storage_id,
        "status": status,
        "candidates": [candidate["name"] for candidate in matches],
        "events_examined": len(trace.events),
        "source_signature_is_identity": False,
        "period_or_similarity_is_sufficient": False,
    }


def demo_traces():
    traces = {}
    for identifier, period, storage in (("host80", 12500, "0x4B0"), ("host40", 25000, "0x658"), ("amac40", 25000, "0x758")):
        traces[identifier] = SignalTrace(storage, tuple((index * period // 2, 1 - index % 2) for index in range(64)))
    traces["unmapped"] = SignalTrace("0x900", tuple((index * 10000 + (index % 3) * 1000, (index // 5) % 2) for index in range(64)))
    return traces


def resilience_scene(sector_id="energy", trace_id="host80"):
    if sector_id not in SECTORS:
        raise ValueError(f"unknown infrastructure sector: {sector_id}")
    traces = demo_traces()
    if trace_id not in traces:
        raise ValueError(f"unknown signal trace: {trace_id}")
    sector = SECTORS[sector_id]
    selected = classify_trace(traces[trace_id])
    import math
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 800], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
    objects.append(_text("title", [42, 55], "Zoe Resilience Atlas", 30, "#67e8f9"))
    objects.append(_text("subtitle", [44, 84], "Essential services, evidence boundaries, and the space between signals", 15, "#9fb1c8"))
    objects.append(_text("sector-heading", [48, 132], "16 critical infrastructure sectors", 16, "#fde68a"))
    objects.append(_text("waveform-heading", [662, 132], "Waveform · synthetic preview", 15, "#fde68a"))
    center = [328, 374]
    positions = {}
    for index, identifier in enumerate(SECTORS):
        angle = -math.pi / 2 + index * math.tau / len(SECTORS)
        positions[identifier] = [center[0] + 225 * math.cos(angle), center[1] + 225 * math.sin(angle)]
    for dependency in sector["depends_on"]:
        objects.append(_line(f"dependency-{dependency}", center, positions[dependency], "#67e8f9", 2))
    for identifier, point in positions.items():
        dependency = identifier in sector["depends_on"]
        color = "#f0abfc" if identifier == sector_id else "#67e8f9" if dependency else "#31445d"
        objects.append(_ellipse(f"sector-{identifier}", point, [13, 13], color, color if identifier == sector_id or dependency else "#101b2b", 2))
        label = SECTORS[identifier]["short"]
        objects.append(_text(f"label-{identifier}", [point[0] - len(label) * 3.6, point[1] + 30], label, 12, color))
    objects.append(_ellipse("selected-center", center, [66, 66], "#f0abfc", "#101b2b", 3))
    objects.append(_text("selected-label", [center[0] - len(sector["short"]) * 5.5, center[1] + 7], sector["short"], 19, "#f0abfc"))
    objects.append(_text("dependency-label", [center[0] - 80, center[1] + 94], "documented example links", 12, "#9fb1c8"))
    colors = {"corroborated": "#67e8f9", "ambiguous": "#fde68a", "unmapped": "#9fb1c8"}
    for row, (identifier, trace) in enumerate(traces.items()):
        result = classify_trace(trace)
        top = 194 + row * 92
        color = "#f0abfc" if identifier == trace_id else colors[result["status"]]
        objects.append(_text(f"trace-label-{identifier}", [664, top - 12], f"{identifier} · {result['status']}", 13, color))
        points = []
        for index, (timestamp, payload) in enumerate(trace.events):
            points.append([666 + index * 280 / (len(trace.events) - 1), top + 47 - payload * 34])
        objects.append({"id": f"trace-{identifier}", "type": "polyline", "points": points, "stroke": color, "fill": "none", "width": 2})
        objects.append(_line(f"trace-base-{identifier}", [666, top + 48], [946, top + 48], "#20304a", 1))
    selected_name = selected["candidates"][0] if len(selected["candidates"]) == 1 else f"{len(selected['candidates'])} reviewed 40 MHz candidates" if selected["candidates"] else "no reviewed signature"
    objects.append(_text("selected-trace", [662, 568], f"Selected: {selected_name}", 13, colors[selected["status"]]))
    objects.append(_text("selected-sector", [45, 636], sector["name"], 21, "#67e8f9"))
    objects.append(_text("dependency-summary", [45, 665], f"Example dependencies: {', '.join(SECTORS[item]['short'] for item in sector['depends_on'])}; not an exhaustive graph.", 13, "#9fb1c8"))
    for index, line in enumerate(textwrap.wrap(sector["why"], width=90)):
        objects.append(_text(f"sector-why-{index}", [45, 691 + index * 23], line, 14, "#d8e5f2"))
    objects.append(_text("source", [45, 757], "Sources: CISA sector pages · CERN waveform-mapping methodology · no live monitoring", 13, "#9fb1c8"))
    objects.append(_text("boundary", [45, 783], "Measurement != evidence != belief update != action · no risk score or automatic control", 13, "#fda4af"))
    scene = _scene("zoe-resilience", 1000, 800, objects, "Zoe Resilience Atlas · services and signal evidence")
    report = {
        "sector": sector_id,
        "sector_name": sector["name"],
        "source": sector["url"],
        "dependencies": sector["depends_on"],
        "dependencies_exhaustive": False,
        "trace": selected,
        "live_monitoring": False,
        "risk_score": False,
        "automatic_action": False,
        "cern_reference": {
            "events_processed": 10759544,
            "storage_streams": 363,
            "corroborated": 1,
            "ambiguous": 2,
            "unmapped": 360,
            "source": "/media/cowboy/research/CERN/analysis/wdb/MAPPER.md",
        },
    }
    return scene, report


def export_resilience(path, sector_id="energy", trace_id="host80", kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("resilience export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("export directory does not exist")
    scene, _ = resilience_scene(sector_id, trace_id)
    report = verify_vdi(scene) if kind == "gem" else verify(scene)
    if not report.passed:
        raise ValueError(report.text())
    if kind == "gem":
        write_metafile(scene, path)
    elif kind == "svg":
        write_svg(scene, path, width)
    else:
        write_png(scene, path, width)
    return path
