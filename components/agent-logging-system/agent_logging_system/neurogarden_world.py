"""A bounded generative research world with review-required experiments."""
from dataclasses import dataclass, field
from html import escape
import base64
import json
from pathlib import Path

DOMAINS = ("biology", "neuroscience", "physics", "cern", "gem", "community")


@dataclass
class Experiment:
    identifier: str
    domain: str
    question: str
    source: str
    limitations: str
    status: str = "proposed"
    measurements: list = field(default_factory=list)
    review: dict | None = None
    executed: bool = False


class World:
    def __init__(self, seed="neurogarden", max_experiments=64, emblem=None):
        if not 1 <= max_experiments <= 256:
            raise ValueError("world must retain 1 to 256 experiments")
        self.seed = str(seed)
        self.max_experiments = max_experiments
        self.experiments = {}
        self.ordinal = 0
        self.horizon_observations = []
        self.attachments = {}
        self.emblem = None
        if emblem is not None:
            path = Path(emblem)
            if path.stat().st_size > 2_000_000:
                raise ValueError("world emblem exceeds 2 MB")
            self.emblem = base64.b64encode(path.read_bytes()).decode("ascii")

    def open(self, domain, question, source, limitations):
        if domain not in DOMAINS:
            raise ValueError("unknown research domain")
        if len(self.experiments) >= self.max_experiments:
            raise ValueError("world experiment capacity reached")
        if not all(isinstance(value, str) and value.strip() for value in (question, source, limitations)):
            raise ValueError("question, source, and limitations are required")
        if len(question) > 512 or len(source) > 512 or len(limitations) > 1024:
            raise ValueError("experiment text exceeds bounds")
        identifier = f"{domain}-{len(self.experiments) + 1:03d}"
        experiment = Experiment(identifier, domain, question.strip(), source.strip(), limitations.strip())
        self.experiments[identifier] = experiment
        return experiment

    def measure(self, identifier, observation, method, scope):
        experiment = self.experiments[identifier]
        if not observation or not method or not scope:
            raise ValueError("measurement requires observation, method, and scope")
        if len(experiment.measurements) >= 64:
            raise ValueError("experiment measurement capacity reached")
        experiment.measurements.append({
            "observation": observation,
            "method": method,
            "scope": scope,
            "evidence": False,
        })
        experiment.status = "measured"
        return experiment

    def review(self, identifier, reviewer, decision):
        if decision not in {"accepted", "rejected", "needs-changes"}:
            raise ValueError("unknown review decision")
        if not reviewer or not isinstance(reviewer, str):
            raise ValueError("reviewer is required")
        experiment = self.experiments[identifier]
        if not experiment.measurements:
            raise ValueError("review requires a measurement")
        experiment.review = {"reviewer": reviewer, "decision": decision}
        experiment.status = "reviewed"
        return experiment

    def horizon(self):
        domain = DOMAINS[self.ordinal % len(DOMAINS)]
        proposal = {
            "domain": domain,
            "question": f"Explore {domain} observation {self.ordinal + 1}",
            "source": self.seed,
            "limitations": "horizon proposal only; requires a specific source and review before measurement",
            "ordinal": self.ordinal + 1,
            "opened": False,
        }
        self.ordinal += 1
        self.horizon_observations.append(proposal)
        if len(self.horizon_observations) > 64:
            self.horizon_observations.pop(0)
        return proposal

    def pulse(self):
        self.ordinal += 1
        self.horizon_observations.append({"ordinal": self.ordinal, "scene_only": True})
        if len(self.horizon_observations) > 64:
            self.horizon_observations.pop(0)
        return self.scene_svg()

    def document(self):
        document = {
            "schema": "neurogarden-world-v1",
            "seed": self.seed,
            "domains": list(DOMAINS),
            "ordinal": self.ordinal,
            "horizon_observations": self.horizon_observations,
            "experiments": [{
                "identifier": item.identifier,
                "domain": item.domain,
                "question": item.question,
                "source": item.source,
                "limitations": item.limitations,
                "status": item.status,
                "measurements": item.measurements,
                "review": item.review,
                "executed": item.executed,
            } for item in self.experiments.values()],
            "boundary": "A measurement is not evidence or action; review does not authorize clinical, physical, or autonomous execution. Living geometry is not consciousness.",
        }
        document.update(self.attachments)
        return document

    def save(self, path):
        path = Path(path)
        if path.exists():
            raise FileExistsError("world output must not overwrite an existing file")
        with path.open("x", encoding="utf-8") as output:
            json.dump(self.document(), output, indent=2, ensure_ascii=False)
            output.write("\n")

    def scene_svg(self):
        positions = {
            "biology": (240, 205), "neuroscience": (650, 170), "physics": (760, 360),
            "cern": (650, 545), "gem": (240, 545), "community": (150, 360),
        }
        parts = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="700" viewBox="0 0 960 700" role="img" aria-label="Neurogarden generative research world">',
            '<rect width="960" height="700" fill="#080d18"/>',
            '<text x="36" y="48" fill="#67e8f9" font-family="monospace" font-size="24">NEUROGARDEN / A shared research universe</text>',
            '<text x="36" y="76" fill="#f0abfc" font-family="monospace" font-size="13">PLAY · LEARN · ADAPT · CREATE · EXPLORE · SHARE</text>',
        ]
        center = (480, 360)
        phase = self.ordinal % 12
        for index, (domain, (x, y)) in enumerate(positions.items()):
            offset = ((phase + index * 2) % 12 - 6) * 2
            px, py = x + offset, y + ((phase + index * 3) % 12 - 6)
            parts.append(f'<line x1="{center[0]}" y1="{center[1]}" x2="{px}" y2="{py}" stroke="#334155" stroke-width="2"/>')
            color = ("#67e8f9", "#f0abfc", "#86efac", "#fde68a", "#93c5fd", "#fda4af")[index]
            parts.append(f'<ellipse cx="{px}" cy="{py}" rx="78" ry="45" fill="#101b2b" stroke="{color}" stroke-width="2"/>')
            parts.append(f'<text x="{px}" y="{py + 5}" text-anchor="middle" fill="{color}" font-family="monospace" font-size="15">{escape(domain.upper())}</text>')
            count = sum(item.domain == domain for item in self.experiments.values())
            parts.append(f'<text x="{px}" y="{py + 25}" text-anchor="middle" fill="#9fb1c8" font-family="monospace" font-size="11">{count} experiments</text>')
        parts.append('<ellipse cx="480" cy="360" rx="108" ry="78" fill="#101b2b" stroke="#67e8f9" stroke-width="3"/>')
        if self.emblem:
            parts.append(f'<image x="396" y="290" width="168" height="118" preserveAspectRatio="xMidYMid meet" href="data:image/png;base64,{self.emblem}"/>')
        else:
            parts.append('<ellipse cx="480" cy="360" rx="62" ry="38" fill="none" stroke="#f0abfc" stroke-width="2"/>')
        parts.extend([
            '<text x="480" y="432" text-anchor="middle" fill="#e2e8f0" font-family="monospace" font-size="20">ZOE + NICK</text>',
            '<text x="480" y="456" text-anchor="middle" fill="#9fb1c8" font-family="monospace" font-size="12">measurement ≠ evidence ≠ action</text>',
            f'<text x="36" y="662" fill="#9fb1c8" font-family="monospace" font-size="12">Living geometry · horizon {self.ordinal} · review before execution · not consciousness</text>',
            '</svg>',
        ])
        return "\n".join(parts) + "\n"
