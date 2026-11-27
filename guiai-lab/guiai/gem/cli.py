from __future__ import annotations

import argparse
from dataclasses import dataclass
from importlib import import_module
import json
import os
from pathlib import Path
import sys
from typing import Any

from . import __version__
from ._root import resolve_zoe_root
from .agent import DEFAULT_AGENT_COMMAND, solve
from .geometry import VerificationReport, verify
from .model import Scene, demo_scene
from .render import write_png, write_svg
from .runner import export_run, replay, verify_vdi, write_failed_run
from .vdi import write_metafile
from .volume import DEFAULT_THRESHOLDS, measure_artifact, write_report


# View modules forwarded directly when invoked as `gem <view> ...`.
_VIEW_COMMANDS: dict[str, str] = {
    "artline": "create, edit, or export an original Zoe vector drawing",
    "pentomino": "play, replay, or compare timed spatial challenges",
    "pentacube": "play and verify pentomino cube permutations",
    "cicada": "run a bounded CERN and cicada-inspired internal clock",
    "pilot": "open or export the original Zoe Practice Navigator guide",
    "resilience": "explore essential services and signal evidence",
    "autonomy": "run Zoe's full self-governing autonomy loop",
    "presence": "inspect an explicit self-model and its uncertainties",
    "protocol": "decode SPECS and AMAC protocol evidence",
    "waveform": "replay bounded VCD and legacy waveform evidence",
    "patchbay": "inspect firmware, sign updates, and explore small-cog language models",
    "leadership": "practice leadership through action, advice, failure, learning, and adaptation",
    "maison": "explore executive clarity, luxury restraint, and enterprise evidence",
    "evidence": "navigate source-first evidence bridges and bounded replay",
}

_ATLAS_MODULE_CHOICES = (
    "unified", "felix", "cern", "brain", "field", "cognitive", "artline", "pentomino",
    "pentacube", "cicada", "pilot", "resilience", "autonomy", "presence", "protocol",
    "waveform", "patchbay", "leadership", "maison", "evidence", "qualia", "procrustes",
    "ellipses", "parabola", "circle", "clock", "graph", "volume", "onset", "horizon",
    "research", "dorothy", "dorothy-jenga", "dorothy-stack", "dorothy-rings",
)


@dataclass(frozen=True)
class R3Spec:
    """Declarative specification for one R3 theorem/observatory CLI command."""

    name: str
    help_text: str
    module_path: str
    suite_fn: str
    needs_root: bool
    html_module: str | None = None
    html_fn: str | None = None
    label: str = ""


# Shared R3 command registry consumed by `gem`, `zoe`, and `ZoeChat`.
R3_COMMAND_SPECS: dict[str, R3Spec] = {
    "theorem13": R3Spec(
        name="theorem13",
        help_text="run Theorem 13 Kloster finite-sample sequential stopping suite",
        module_path="guiai.gem.kloster_stopping_law",
        suite_fn="run_theorem13_stopping_suite",
        needs_root=True,
        label="Theorem 13 · Kloster Finite-Sample Stopping & Distinguisher Law",
    ),
    "theorem14": R3Spec(
        name="theorem14",
        help_text="run Theorem 14 Kloster spatial-optical filtration & MTF suite",
        module_path="guiai.gem.kloster_spatial_optical_law",
        suite_fn="run_kloster_theorem14_suite",
        needs_root=False,
        label="Theorem 14 · Kloster Spatial-Optical Filtration & MTF Law",
    ),
    "theorem15": R3Spec(
        name="theorem15",
        help_text="run Theorem 15 Kloster multi-agent consensus & Brier law suite",
        module_path="guiai.gem.kloster_multi_agent_consensus",
        suite_fn="run_kloster_theorem15_suite",
        needs_root=True,
        label="Theorem 15 · Kloster Multi-Agent Consensus & Exact Brier Law",
    ),
    "botanical": R3Spec(
        name="botanical",
        help_text="run C27 36-molecule Botanical Neuro-Oncology Atlas & Filbin-2018 lab",
        module_path="guiai.gem.kloster_botanical_atlas_36",
        suite_fn="run_botanical_atlas_c27_suite",
        needs_root=False,
        html_module="guiai.gem.botanical_atlas_explorer",
        html_fn="render_botanical_explorer_html",
        label="C27 Botanical Neuro-Oncology Atlas · 36 PubChem Molecules & Filbin-2018",
    ),
    "optics": R3Spec(
        name="optics",
        help_text="run Theorem 14 Optics Workbench (Scheimpflug, MTF, architectural isovist)",
        module_path="guiai.gem.kloster_spatial_optical_law",
        suite_fn="run_kloster_theorem14_suite",
        needs_root=False,
        html_module="guiai.gem.spatial_optical_workbench",
        html_fn="render_optics_workbench_html",
        label="Theorem 14 Optical Workbench (Optics · Scheimpflug · MTF · Isovist)",
    ),
    "proof-packet": R3Spec(
        name="proof-packet",
        help_text="run the 5-pillar Operational Metacognition Referee Proof Packet",
        module_path="guiai.gem.kloster_proof_packet",
        suite_fn="run_metacognition_proof_packet",
        needs_root=True,
        html_module="guiai.gem.proof_packet_arena",
        html_fn="render_proof_arena_html",
        label="Operational Metacognition Referee Proof Packet (5 Pillars)",
    ),
    "c28": R3Spec(
        name="c28",
        help_text="run C28 3D Pharmacophore compactness & histology MTF suite",
        module_path="guiai.gem.kloster_pharmacophore_spatial_c28",
        suite_fn="run_pharmacophore_spatial_c28_suite",
        needs_root=False,
        label="C28 3D Pharmacophore & Histology MTF Preclinical Suite",
    ),
}


def register_r3_subparsers(commands) -> None:
    """Register all 7 R3 subcommands on an argparse subparsers object."""
    # Provide consistent flags across both `gem` and `zoe` CLIs.
    for name, spec in R3_COMMAND_SPECS.items():
        sub = commands.add_parser(name, help=spec.help_text)
        sub.add_argument("--zoe-root", help="Zoe source checkout; default: ZOE_ROOT")
        sub.add_argument("--json", action="store_true", help="emit full machine-readable JSON report")
        sub.add_argument("--output", help="new no-overwrite JSON evidence path")
        if spec.html_module:
            sub.add_argument("--html", help="new no-overwrite interactive HTML export path")


def run_r3_command(name: str, zoe_root: str | Path | None = None) -> dict[str, Any]:
    """Execute one registered R3 suite and return its JSON-serializable report."""
    if name not in R3_COMMAND_SPECS:
        raise ValueError(f"unsupported R3 command: {name}")
    spec = R3_COMMAND_SPECS[name]
    fn = getattr(import_module(spec.module_path), spec.suite_fn)
    if spec.needs_root:
        return fn(resolve_zoe_root(zoe_root))
    return fn()


def _format_theorem13_metrics(report: dict[str, Any]) -> list[str]:
    """Format Theorem 13 stopping metrics across crypto, bio, and GPT-2."""
    sym = report["sympy_proofs"]
    w3 = report["worlds"]["world3_real_gpt2_and_null"]
    return [
        f"  SymPy proofs exact={sym['all_sympy_proofs_exact']} · GPT-2 stopping + null trials={w3['null_calibration_trials']} · false_alarm_rate={w3['anytime_valid_false_alarm_rate']}",
        f"  Worlds verified: crypto={report['worlds']['world1_crypto_stopping']['verified']} · bio={report['worlds']['world2_bio_pains_stopping']['verified']}",
    ]


def _format_theorem14_metrics(report: dict[str, Any]) -> list[str]:
    """Format Theorem 14 continuous spatial-optical filtration metrics."""
    w1 = report["world1_spatial_point_patterns"]
    w2 = report["world2_optical_mtf_resolution"]
    return [
        f"  SymPy 6/6 proved={report['sympy_proofs']['all_proved']} · 2D Parseval max_err={w2['max_parseval_error']:.3e} · 200-blur monotone={w2['blur_monotonicity_200']}",
        f"  Point patterns verified={w1['verified']} · Architecture/drawing verified={report['world45_architecture_structure_drawing']['verified']}",
    ]


def _format_theorem15_metrics(report: dict[str, Any]) -> list[str]:
    """Format Theorem 15 multi-agent consensus and Brier gain metrics."""
    w2 = report["world2_helen_real_brier"]
    return [
        f"  SymPy 5/5 proved={report['sympy_proofs']['all_proved']} · HELEN obs={w2['n_real_obs']} · actual_brier_gain={w2['actual_brier_gain']:.6f} · row_err={w2['max_per_row_identity_err']:.2e}",
        f"  Worlds: 6-LLM vs echo={report['world1_6llm_vs_echo']['verified']} · FIPS-203 3-hospital={report['world3_fips203_consortium']['verified']}",
    ]


def _format_botanical_metrics(report: dict[str, Any]) -> list[str]:
    """Format C27 36-molecule botanical atlas and Filbin-2018 packing metrics."""
    return [
        f"  PubChem molecules={report['molecules_count']} · Filbin-2018 gene modules={len(report['published_gene_modules'])} · FIPS-203 slots={report['fips203_slots_packed']} (exact={report['fips203_216slot_3site_homomorphic_exact']})",
        f"  Theorem 13 Filbin stopping verified={report['theorem13_filbin_stopping']['verified']} · interactive HTML=`botanical_atlas_explorer`",
    ]


def _format_optics_metrics(report: dict[str, Any]) -> list[str]:
    """Format Theorem 14 optical workbench, Scheimpflug, and isovist metrics."""
    w3 = report["world3_scheimpflug_view_camera"]
    w2 = report["world2_optical_mtf_resolution"]
    w45 = report["world45_architecture_structure_drawing"]
    return [
        f"  Scheimpflug peak={w3['kloster_peak_theta_deg']} deg (theory {w3['theoretical_scheimpflug_deg']} deg, gain={w3['sharpness_gain_x']}x) · MTF sharp_M2={w2['m2_original_sharp']:.6f}",
        f"  Isovist corridor/plaza={w45['totten_isovist']['corridor_to_plaza_ratio']}x · arch N_eff redundancy={w45['cruz_structural']['redundancy_gain_x']}x · workbench=`spatial_optical_workbench`",
    ]


def _format_proof_packet_metrics(report: dict[str, Any]) -> list[str]:
    """Format 5-pillar proof packet and SHA256SUMS.orbit supply-chain status."""
    p1 = report["pillar1_sympy"]
    p2 = report["pillar2_16llm_and_distilgpt2"]
    p5 = report["pillar5_orbit_checksums"]
    return [
        f"  Pillar 1 SymPy={p1['total_proved']}/14 · Pillar 2 LLMs={p2['real_llms_verified']} (max_err={p2['max_knot_lebesgue_m4_error']:.2e}) · Pillar 3 reward={report['pillar3_causal_ablation']['mean_reward']}",
        f"  Pillar 4 GPT-2 null_far={report['pillar4_theorem13_gpt2_and_null']['anytime_valid_false_alarm_rate']} · Pillar 5 Orbit checksums={p5['ok']}/{p5['total']} (all_ok={p5['all_ok']})",
    ]


def _format_c28_metrics(report: dict[str, Any]) -> list[str]:
    """Format C28 3D pharmacophore compactness and histology MTF metrics."""
    p3 = report["pharmacophore_3d_atlas"]
    hm = report["histology_microarchitecture_mtf"]
    return [
        f"  3D Pharmacophores={p3['molecules_evaluated']} · CNS r_gyr={p3['mean_cns_r_gyr_angstrom']} A vs BBB-blocked={p3['mean_bbb_blocked_r_gyr_angstrom']} A · traps_blocked={p3['traps_blocked']}",
        f"  Histology MTF Parseval_err={hm['parseval_mtf_err']:.2e} · tumor_stop={hm['theorem13_tumor_stop']['action']} · csr_abstain={hm['theorem13_csr_abstain']['action']}",
    ]


_R3_METRIC_FORMATTERS = {
    "theorem13": _format_theorem13_metrics,
    "theorem14": _format_theorem14_metrics,
    "theorem15": _format_theorem15_metrics,
    "botanical": _format_botanical_metrics,
    "optics": _format_optics_metrics,
    "proof-packet": _format_proof_packet_metrics,
    "c28": _format_c28_metrics,
}


def format_r3_summary(name: str, report: dict[str, Any]) -> str:
    """Format a human-readable telemetry summary with constitutional invariants."""
    spec = R3_COMMAND_SPECS[name]
    sha = str(report.get("evidence_sha256", ""))[:16]
    all_verified = bool(report.get("all_verified", False))
    const = report.get("constitution", {})
    lines = [
        spec.label,
        f"  contract={report.get('contract')} · all_verified={all_verified} · verified={all_verified} · sha256={sha}...",
    ]
    lines.extend(_R3_METRIC_FORMATTERS[name](report))
    # Always emit explicit constitutional guardrails on every R3 summary.
    lines.append(
        "  sentience_claimed="
        f"{bool(const.get('sentience_claimed', False))}"
        f" · l5_agi_qualified={bool(const.get('l5_agi_qualified', False))}"
        f" · zoe_clone_claimed={bool(const.get('zoe_clone_claimed', False))}"
        f" · clinical_action_authorized={bool(const.get('clinical_action_authorized', False))}"
        f" · cure_claim={bool(const.get('cure_claim', False))}"
        f" · cloud_tokens_used={int(const.get('cloud_tokens_used', 0))}"
    )
    return "\n".join(lines)


def write_r3_json(report: dict[str, Any], path: str | Path) -> Path:
    """Write an R3 evidence JSON report with strict no-overwrite protection."""
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        handle.write("\n")
    return output


def write_r3_html(name: str, path: str | Path) -> Path:
    """Render and write an R3 interactive HTML observatory with no-overwrite."""
    spec = R3_COMMAND_SPECS[name]
    if not spec.html_module or not spec.html_fn:
        raise ValueError(f"{name} does not provide an interactive HTML export")
    raw = getattr(import_module(spec.html_module), spec.html_fn)()
    payload = raw if isinstance(raw, bytes) else str(raw).encode("utf-8")
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as handle:
        handle.write(payload)
    return output


def dispatch_r3_cli(arguments: argparse.Namespace) -> int:
    """Execute an R3 CLI command, emit summary/JSON, and write optional exports."""
    report = run_r3_command(arguments.command, getattr(arguments, "zoe_root", None))
    if getattr(arguments, "output", None):
        write_r3_json(report, arguments.output)
    html_path = getattr(arguments, "html", None)
    if html_path:
        write_r3_html(arguments.command, html_path)
    if getattr(arguments, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(format_r3_summary(arguments.command, report))
    return 0


def _add_scene_parsers(commands) -> None:
    """Register core Spatial IR scene demo, verify, render, replay, solve, and volume."""
    demo = commands.add_parser("demo", help="export the verified house example")
    demo.add_argument("--output", required=True, help="new or empty run directory")

    verify_parser = commands.add_parser("verify", help="verify a Spatial IR scene")
    verify_parser.add_argument("scene", help="scene JSON path")
    verify_parser.add_argument("--vdi", action="store_true", help="also recover and verify a GEM metafile")
    verify_parser.add_argument("--json", action="store_true", help="emit machine-readable reports")

    render = commands.add_parser("render", help="render a scene to SVG, PNG, or GEM VDI")
    render.add_argument("scene", help="scene JSON path")
    render.add_argument("--output", required=True, help="output artifact path")
    render.add_argument("--format", choices=("svg", "png", "gem"), help="default: infer from output suffix")
    render.add_argument("--width", type=int, default=1200, help="SVG/PNG width in pixels")

    replay_parser = commands.add_parser("replay", help="recompute verification from run artifacts")
    replay_parser.add_argument("run", help="GEM run directory")
    replay_parser.add_argument("--json", action="store_true", help="emit the complete recomputed report")

    agent = commands.add_parser("solve", help="generate, verify, and repair a scene with an external agent")
    agent.add_argument("request", help="natural-language drawing request")
    agent.add_argument("--output", required=True, help="new or empty run directory")
    agent.add_argument("--agent-command", default=DEFAULT_AGENT_COMMAND, help="command template; {prompt} is replaced, otherwise prompt uses stdin")
    agent.add_argument("--attempts", type=int, default=3, help="total generation/repair attempts, from 1 to 10")
    agent.add_argument("--timeout", type=float, default=120, help="timeout for each agent process in seconds")
    agent.add_argument("--constraints", help="JSON file containing required constraint objects")
    agent.add_argument("--cwd", help="working directory for the external agent")

    volume = commands.add_parser("volume", help="measure operational metacognition and optional accessible momentum")
    volume.add_argument("probabilities", help="NPZ file containing a full-vocabulary probability vector")
    volume.add_argument("--key", default="probabilities", help="NPZ key for the current distribution")
    volume.add_argument("--previous", help="earlier NPZ distribution used to compute momentum")
    volume.add_argument("--previous-key", help="NPZ key for the earlier distribution; default: current key")
    volume.add_argument("--tau", action="append", type=float, help="probability threshold; repeat for a sweep")
    volume.add_argument("--min-volume", type=int, default=1, help="target band lower bound")
    volume.add_argument("--max-volume", type=int, default=4, help="target band upper bound")
    volume.add_argument("--output", required=True, help="new evidence JSON path")


def _add_passthrough_parsers(commands) -> None:
    """Register the 14 GEM view subcommands forwarded to `<view>_view`."""
    for name, description in _VIEW_COMMANDS.items():
        command = commands.add_parser(name, help=description)
        command.add_argument("arguments", nargs=argparse.REMAINDER, help=f"arguments forwarded to Zoe {name}")


def _add_domain_parsers(commands) -> None:
    """Register atlas, master, qualia, dorothy, notebook, cognitive, felix-hdl, and cern."""
    atlas = commands.add_parser("atlas", help="open the native geometry atlas or export one module")
    atlas.add_argument("--module", choices=_ATLAS_MODULE_CHOICES, default="procrustes")
    atlas.add_argument("--output", help="export the default scene to .svg, .png, or .gem instead of opening GTK")
    atlas.add_argument("--format", choices=("svg", "png", "gem"), help="default: infer from output suffix")
    atlas.add_argument("--width", type=int, default=1200, help="SVG/PNG width in pixels")

    master = commands.add_parser("master", aliases=["brain", "zoe"], help="open Zoe / MASTER GEM with the BRAIN orchestrator")
    master.add_argument("--module", choices=_ATLAS_MODULE_CHOICES, default="brain")
    master.add_argument("--research-root", help="next-token-predictability repository; default: MASTER_GEM_RESEARCH_ROOT")
    master.add_argument("--cern-root", help="CERN corpus for the FELIX module; default: ZOE_CERN_ROOT or <workspace-parent>/CERN/Boutique")
    master.add_argument("--felix-build", help="FELIX build ID, card, or unique filename substring")
    master.add_argument("--observations", type=int, default=1, help="FELIX builds to observe for JSON/WAV export, 1-64")
    master.add_argument("--output", help="export the scene, FELIX memory, or FELIX sonification instead of opening GTK")
    master.add_argument("--format", choices=("svg", "png", "gem", "json", "wav"), help="default: infer from output suffix")
    master.add_argument("--width", type=int, default=1200, help="SVG/PNG width in pixels")

    qualia = commands.add_parser("qualia", help="run the Accessible Q-Volume toy demonstration and save JSON evidence")
    qualia.add_argument("--tau", action="append", type=float, help="additional q-arrow threshold; repeat to override the default 0.20 and 0.30")
    qualia.add_argument("--output", required=True, help="new JSON evidence path")

    dorothy = commands.add_parser("dorothy", help="Dorothy: render Allen CCFv3 structure meshes, or fetch the vendored atlas data")
    dorothy.add_argument("--fetch", action="store_true", help="download and hash the structure graph and PLY meshes into the local cache")
    dorothy.add_argument("--data-root", help="atlas cache directory; default: DOROTHY_CCF_ROOT or ~/.cache/dorothy/ccf_2017")
    dorothy.add_argument("--structures", help="comma-separated CCF structure IDs; default: the vendored 12-region set")
    dorothy.add_argument("--yaw", type=float, default=None, help="orbit yaw in degrees; default: per-view")
    dorothy.add_argument("--pitch", type=float, default=None, help="orbit pitch in degrees; default: per-view")
    dorothy.add_argument("--distance", type=float, help="camera distance in CCF units; default: fit the visible structures")
    dorothy.add_argument("--fov", type=float, default=35.0, help="vertical field of view in degrees")
    dorothy.add_argument("--shade-levels", type=int, default=16, help="flat-shading quantization per structure, 2-64")
    dorothy.add_argument("--output", help="export .svg, .png, or .gem instead of opening the native atlas")
    dorothy.add_argument("--format", choices=("svg", "png", "gem"), help="default: infer from output suffix")
    dorothy.add_argument("--width", type=int, default=1600, help="SVG/PNG width in pixels")
    dorothy.add_argument("--view", choices=("brain", "jenga", "stack", "rings"), default="brain", help="visualization variant")
    dorothy.add_argument("--layout", choices=("tower", "exploded", "pull"), default="tower", help="Jenga layout")
    dorothy.add_argument("--structure", type=int, help="structure ID: Jenga pull block or Rings center")
    dorothy.add_argument("--slices", type=int, default=8, help="Stack slab count, 2-32")
    dorothy.add_argument("--depth", type=int, default=3, help="Rings descendant depth, 1-5")

    notebook = commands.add_parser("notebook", help="verify, save, or render a Zoe Bayesian field notebook")
    notebook.add_argument("input", nargs="?", help="saved notebook JSON; omit to use the worked GEM example")
    notebook.add_argument("--output", required=True, help="new .json, .svg, .png, or .gem output path")
    notebook.add_argument("--format", choices=("json", "svg", "png", "gem"), help="default: infer from output suffix")
    notebook.add_argument("--width", type=int, default=1200, help="SVG/PNG width in pixels")

    cognitive = commands.add_parser("cognitive", help="save, verify, or render Zoe's bounded Cognitive Field")
    cognitive.add_argument("input", nargs="?", help="saved Cognitive Field JSON; omit to use the worked example")
    cognitive.add_argument("--output", required=True, help="new .json, .svg, .png, or .gem output path")
    cognitive.add_argument("--format", choices=("json", "svg", "png", "gem"), help="default: infer from output suffix")
    cognitive.add_argument("--width", type=int, default=1400, help="SVG/PNG width in pixels")

    hdl = commands.add_parser("felix-hdl", help="recover LCB and STAR/Flink HDL from HTML into clean source files")
    hdl.add_argument("--cern-root", help="CERN corpus; default: ZOE_CERN_ROOT or <workspace-parent>/CERN/Boutique")
    hdl.add_argument("--output", required=True, help="new or empty recovered-HDL output directory")

    cern = commands.add_parser("cern", help="inventory, audit, verify, and visualize the complete CERN corpus")
    cern.add_argument("operation", choices=("scan", "forge", "report", "chart", "verify"))
    cern.add_argument(
        "--cern-root",
        default=os.environ.get("ZOE_CERN_ROOT") or str(Path(__file__).resolve().parents[4] / "CERN"),
    )
    cern.add_argument("--input", help="existing corpus directory or Repair Atlas JSON")
    cern.add_argument("--output", required=True, help="new output directory or artifact path")
    cern.add_argument("--workers", type=int, default=1, help="parallel hash readers, 1-32")
    cern.add_argument("--format", choices=("json", "svg", "png", "gem"), help="chart format; default: infer from output suffix")


def _parser():
    """Build the top-level `gem` CLI parser."""
    parser = argparse.ArgumentParser(prog="gem", description="Executable Spatial IR, GEM VDI, and deterministic geometry verification")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    _add_scene_parsers(commands)
    _add_passthrough_parsers(commands)
    _add_domain_parsers(commands)
    register_r3_subparsers(commands)
    return parser


def _print_report(report):
    """Print human-readable Spatial IR verification report lines."""
    print(VerificationReport(report["scene_id"], report["results"]).text())


def _write_scene_output(scene: Scene, output: Path, fmt: str | None, width: int, error_msg: str) -> str:
    """Write a Spatial IR Scene as SVG, PNG, or GEM metafile and return format name."""
    kind = fmt or output.suffix.lower().lstrip(".")
    if kind == "svg":
        write_svg(scene, output, width)
    elif kind == "png":
        write_png(scene, output, width)
    elif kind == "gem":
        write_metafile(scene, output)
    else:
        raise ValueError(error_msg)
    return kind


def _try_view_passthrough(raw_arguments: list[str]) -> int | None:
    """Forward `gem <view> ...` directly to its `guiai.gem.<view>_view` entrypoint."""
    if not raw_arguments or raw_arguments[0] not in _VIEW_COMMANDS:
        return None
    return import_module(f".{raw_arguments[0]}_view", __package__).main(raw_arguments[1:])


def _handle_cern(arguments: argparse.Namespace) -> int:
    """Delegate `cern` operations to `guiai.gem.cern_cli`."""
    from .cern_cli import run
    return run(arguments)


def _handle_felix_hdl(arguments: argparse.Namespace) -> int:
    """Recover LCB and STAR/Flink HDL sources from HTML documents."""
    from .felix_hdl import export_html_hdl
    report = export_html_hdl(arguments.cern_root, arguments.output)
    print(json.dumps({
        "module": "felix-hdl",
        "file_count": report["file_count"],
        "line_count": report["line_count"],
        "languages": report["languages"],
        "output": report["output_root"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_view_command(arguments: argparse.Namespace) -> int:
    """Dispatch parsed view passthrough subcommands."""
    return import_module(f".{arguments.command}_view", __package__).main(arguments.arguments)


def _arrow_contract_ok(row: dict[str, Any], toy: dict[str, Any]) -> bool:
    """Check strict threshold equality and effective information for one Q-arrow."""
    import math

    delta = sum(p > row["tau"] for p in toy["after"].values()) - sum(p > row["tau"] for p in toy["before"].values())
    entered = sorted(s for s, p in toy["after"].items() if p > row["tau"] and toy["before"][s] <= row["tau"])
    exited = sorted(s for s, p in toy["before"].items() if p > row["tau"] and toy["after"][s] <= row["tau"])
    return (
        row["delta_accessible_q_volume"] == delta
        and row["entered"] == entered
        and row["exited"] == exited
        and math.isclose(row["ei_bits"], math.log2(4 / 3))
    )


def _verify_qualia_contract(toy: dict[str, Any], thresholds: list[float], deltas: list[int]) -> None:
    """Validate Accessible Q-Volume toy arithmetic against checked filtration laws."""
    # Verify default threshold deltas and strict inequality invariants across arrows.
    default_ok = thresholds != [0.20, 0.30] or (
        deltas == [-1, 3]
        and toy["arrows"][0]["exited"] == ["11"]
        and toy["arrows"][1]["entered"] == ["00", "01", "10"]
    )
    arrows_ok = all(_arrow_contract_ok(row, toy) for row in toy["arrows"])
    sweep_ok = (
        next(level for level in toy["after_sweep"] if level["tau"] == 1 / 3)["states"] == []
        and toy["two_way"]["past"]["accessible_q_volume"] == 3
        and toy["two_way"]["future"]["accessible_volume"] == 3
    )
    if not (default_ok and arrows_ok and sweep_ok):
        raise RuntimeError("Accessible Q-Volume toy arithmetic did not match its checked contract")


def _handle_qualia(arguments: argparse.Namespace) -> int:
    """Run the Accessible Q-Volume demonstration and save no-overwrite JSON."""
    from .qualia import accessible_q_toy, accessible_sweep, q_arrow_annotation, reconstruct_filtration

    toy = accessible_q_toy()
    thresholds = arguments.tau or [0.20, 0.30]
    toy["arrows"] = [q_arrow_annotation(toy["before"], toy["after"], tau) for tau in thresholds]
    for name in ("before", "after"):
        levels = [level["tau"] for level in toy[f"{name}_sweep"]] + thresholds
        toy[f"{name}_sweep"] = accessible_sweep(toy[name], levels)
    deltas = [row["delta_accessible_q_volume"] for row in toy["arrows"]]
    _verify_qualia_contract(toy, thresholds, deltas)

    report = {
        "schema_version": 1,
        "instrument": "Accessible Q-Volume toy demonstration",
        "source": "Balduzzi & Tononi (2009), Qualia: The Geometry of Integrated Information",
        "original_equation_credit": "Nicholas Michael Kloster, March 6, 2026",
        "extension_status": "proposed formal construction; toy arithmetic verified, not an empirically validated IIT implementation",
        "complete_filtration_identity": "rho(z) = sup{tau : z is in QB_tau}, with sup(empty) = 0; this is the continuous labeled-filtration identity",
        "finite_sweep_is_approximate": True,
        "phi_computed": False,
        "gamma_calculator": False,
        "consciousness_measured": False,
        "checks": {"arithmetic": "passed", "strict_threshold_equality": "passed", "two_way_record": "passed"},
        "sampled_reconstruction": {name: reconstruct_filtration(toy[f"{name}_sweep"]) for name in ("before", "after")},
        "toy": toy,
    }
    output = Path(arguments.output)
    if output.suffix.lower() != ".json":
        raise ValueError("qualia evidence output must use .json")
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({
        "instrument": report["instrument"],
        "output": str(output),
        "bytes": output.stat().st_size,
        "deltas": deltas,
        "ei_bits": toy["arrows"][0]["ei_bits"],
        "checks": report["checks"],
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_cognitive(arguments: argparse.Namespace) -> int:
    """Save, verify, or render Zoe's bounded Cognitive Field."""
    from .cognitive import CognitiveField, export_cognitive

    field = CognitiveField.load(arguments.input) if arguments.input else CognitiveField.demo()
    output, report = export_cognitive(field, arguments.output, arguments.format, arguments.width)
    print(json.dumps({
        "instrument": "Zoe Cognitive Field",
        "events": len(field.events),
        "active": len(field.working),
        "evicted": len(field.evicted),
        "declarative": len(field.declarative),
        "review_required": len(field.performance),
        "executed": False,
        "output": str(output),
        "bytes": output.stat().st_size,
        "verified": "verification" in report,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_notebook(arguments: argparse.Namespace) -> int:
    """Verify, save, or render a Zoe Bayesian field notebook."""
    from .field import FieldNotebook, field_scene

    notebook = FieldNotebook.load(arguments.input) if arguments.input else FieldNotebook.demo()
    output = Path(arguments.output)
    kind = arguments.format or output.suffix.lower().lstrip(".")
    if kind == "json":
        notebook.save(output)
    else:
        scene, _ = field_scene(notebook)
        _write_scene_output(scene, output, kind, arguments.width, "notebook output format must be json, svg, png, or gem")
    print(json.dumps({
        "instrument": "Zoe Bayesian field notebook",
        "events": len(notebook.events),
        "questions": len(notebook.questions),
        "claims": len(notebook.claims),
        "measurements": len(notebook.measurements),
        "output": str(output),
        "bytes": output.stat().st_size,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _build_dorothy_document(arguments: argparse.Namespace, dorothy_data, dorothy_scene):
    """Build the requested Dorothy brain/jenga/stack/rings Spatial IR document."""
    if arguments.view == "jenga":
        from .dorothy_jenga import default_jenga_document
        return default_jenga_document(
            arguments.data_root, layout=arguments.layout, selected=arguments.structure,
            yaw=arguments.yaw, pitch=arguments.pitch, fov=arguments.fov,
        )
    if arguments.view == "stack":
        from .dorothy_stack import default_stack_document
        return default_stack_document(
            arguments.data_root, slices=arguments.slices,
            yaw=arguments.yaw, pitch=arguments.pitch, fov=arguments.fov,
        )
    if arguments.view == "rings":
        from .dorothy_rings import default_rings_document
        return default_rings_document(
            arguments.data_root, center=arguments.structure or 997, max_depth=arguments.depth,
        )
    records = dorothy_data.load_structures(arguments.data_root, arguments.structures)
    return dorothy_scene(
        records,
        yaw=215.0 if arguments.yaw is None else arguments.yaw,
        pitch=-18.0 if arguments.pitch is None else arguments.pitch,
        distance=arguments.distance,
        fov=arguments.fov,
        shade_levels=arguments.shade_levels,
    )


def _handle_dorothy(arguments: argparse.Namespace) -> int:
    """Fetch, display, or export Dorothy Allen CCFv3 brain geometry."""
    from . import dorothy_data
    from .dorothy import dorothy_scene

    if arguments.data_root:
        os.environ["DOROTHY_CCF_ROOT"] = str(arguments.data_root)
    if arguments.fetch:
        ids = dorothy_data.parse_structure_ids(arguments.structures) if arguments.structures else dorothy_data.DEFAULT_STRUCTURE_IDS
        manifest = dorothy_data.fetch(arguments.data_root, ids)
        print(json.dumps({
            "atlas": manifest["atlas"],
            "citation": manifest["citation"],
            "root": str(dorothy_data.default_root()),
            "structures": [{"id": r["id"], "acronym": r["acronym"], "bytes": r["bytes"], "sha256": r["sha256"]} for r in manifest["structures"]],
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if not arguments.output:
        from .atlas_view import launch_atlas
        launch_atlas("dorothy" if arguments.view == "brain" else f"dorothy-{arguments.view}")
        return 0
    scene, report = _build_dorothy_document(arguments, dorothy_data, dorothy_scene)
    output = Path(arguments.output)
    _write_scene_output(scene, output, arguments.format, arguments.width, "Dorothy output format must be svg, png, or gem")
    print(json.dumps({
        "module": "dorothy",
        "output": str(output),
        "bytes": output.stat().st_size,
        "measurement": report,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_atlas(arguments: argparse.Namespace) -> int:
    """Open the native geometry atlas / MASTER GEM or export an artifact."""
    research_root = getattr(arguments, "research_root", None) or os.environ.get("MASTER_GEM_RESEARCH_ROOT")
    cern_root = getattr(arguments, "cern_root", None)
    felix_build = getattr(arguments, "felix_build", None)
    observations = getattr(arguments, "observations", 1)
    if not arguments.output:
        from .atlas_view import launch_atlas
        launch_atlas(arguments.module, research_root=research_root, cern_root=cern_root, felix_build=felix_build)
        return 0

    output = Path(arguments.output)
    kind = arguments.format or output.suffix.lower().lstrip(".")
    if arguments.module == "felix" and kind in {"json", "wav"}:
        from .felix import default_felix_observer
        observer = default_felix_observer(cern_root, felix_build, observations)
        if kind == "json":
            observer.save(output)
            report = observer.report()
        else:
            from .felix_audio import write_felix_sonification
            _, report = write_felix_sonification(observer, output)
    else:
        from .atlas import default_document
        scene, report = default_document(
            arguments.module, research_root=research_root, cern_root=cern_root,
            felix_build=felix_build, observations=observations,
        )
        _write_scene_output(scene, output, kind, arguments.width, "atlas output format must be svg, png, gem, or FELIX json/wav")
    print(json.dumps({
        "module": arguments.module,
        "output": str(output),
        "bytes": output.stat().st_size,
        "measurement": report,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _handle_volume(arguments: argparse.Namespace) -> int:
    """Measure operational metacognition A_tau(p) from an NPZ artifact."""
    report = measure_artifact(
        arguments.probabilities,
        key=arguments.key,
        previous_path=arguments.previous,
        previous_key=arguments.previous_key,
        thresholds=arguments.tau or DEFAULT_THRESHOLDS,
        minimum=arguments.min_volume,
        maximum=arguments.max_volume,
    )
    output = write_report(report, arguments.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    print(f"Evidence: {output}")
    return 0


def _handle_demo(arguments: argparse.Namespace) -> int:
    """Export and verify the built-in GEM house Spatial IR scene."""
    result = export_run(demo_scene(), arguments.output, trajectory=[{
        "sequence": 1, "kind": "builtin_demo", "outcome": "exported",
    }])
    _print_report(result.source.to_dict())
    print(f"VDI: {'PASS' if result.vdi.passed else 'FAIL'}")
    for profile, report in result.devices.items():
        print(f"{profile}: {'PASS' if report['passed'] else 'FAIL'}")
    print(f"Run: {result.path}")
    return 0 if result.passed else 1


def _handle_verify(arguments: argparse.Namespace) -> int:
    """Verify a Spatial IR scene JSON and optionally its VDI metafile."""
    scene = Scene.load(arguments.scene)
    source = verify(scene)
    documents = {"source": source.to_dict()}
    if arguments.vdi:
        documents["vdi"] = verify_vdi(scene).to_dict()
    if arguments.json:
        print(json.dumps(documents, indent=2, sort_keys=True))
    else:
        _print_report(documents["source"])
        if "vdi" in documents:
            print()
            _print_report(documents["vdi"])
    return 0 if all(report["passed"] for report in documents.values()) else 1


def _handle_render(arguments: argparse.Namespace) -> int:
    """Render a Spatial IR scene JSON to SVG, PNG, or GEM VDI."""
    scene = Scene.load(arguments.scene)
    output = Path(arguments.output)
    kind = _write_scene_output(scene, output, arguments.format, arguments.width, "output format must be svg, png, or gem")
    print(f"{kind}: {output} ({output.stat().st_size} bytes)")
    return 0


def _handle_replay(arguments: argparse.Namespace) -> int:
    """Recompute verification from an exported GEM run directory."""
    result = replay(arguments.run)
    if arguments.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        _print_report(result.source)
        _print_report(result.vdi)
        for profile, report in result.devices.items():
            print(f"{profile}: {'PASS' if report['passed'] else 'FAIL'} · source+VDI+invariants")
        print(f"Recorded reports match: {result.matches_recorded}")
    return 0 if result.passed and result.matches_recorded else 1


def _handle_solve(arguments: argparse.Namespace) -> int:
    """Generate, verify, and repair a scene using an external agent."""
    constraints = []
    if arguments.constraints:
        constraints = json.loads(Path(arguments.constraints).read_text(encoding="utf-8"))
        if not isinstance(constraints, list):
            raise ValueError("constraint file must contain a JSON array")
    result = solve(
        arguments.request,
        arguments.agent_command,
        constraints,
        max_attempts=arguments.attempts,
        timeout=arguments.timeout,
        cwd=arguments.cwd,
    )
    if result.scene is None:
        path = write_failed_run(arguments.output, result.trajectory, result.error or "no valid scene returned")
        print(f"No valid Spatial IR scene after {result.attempts} attempts. Trajectory: {path}", file=sys.stderr)
        return 1
    run = export_run(result.scene, arguments.output, trajectory=result.trajectory)
    _print_report(run.source.to_dict())
    print(f"Attempts: {result.attempts}")
    print(f"Source+VDI+devices: {'PASS' if run.passed else 'FAIL'}")
    print(f"Run: {run.path}")
    return 0 if run.passed else 1


# Declarative dispatch table covering all parsed `gem` subcommands.
_COMMAND_HANDLERS = {
    "cern": _handle_cern,
    "felix-hdl": _handle_felix_hdl,
    "qualia": _handle_qualia,
    "cognitive": _handle_cognitive,
    "notebook": _handle_notebook,
    "dorothy": _handle_dorothy,
    "atlas": _handle_atlas,
    "master": _handle_atlas,
    "brain": _handle_atlas,
    "zoe": _handle_atlas,
    "volume": _handle_volume,
    "demo": _handle_demo,
    "verify": _handle_verify,
    "render": _handle_render,
    "replay": _handle_replay,
    "solve": _handle_solve,
    **{name: _handle_view_command for name in _VIEW_COMMANDS},
    **{name: dispatch_r3_cli for name in R3_COMMAND_SPECS},
}


def main(argv=None):
    """CLI entrypoint for `gem`."""
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    # Pass raw view invocations straight through before argparse intercepts flags.
    passthrough = _try_view_passthrough(raw_arguments)
    if passthrough is not None:
        return passthrough
    arguments = _parser().parse_args(raw_arguments)
    try:
        handler = _COMMAND_HANDLERS.get(arguments.command)
        if handler is None:
            return 2
        return handler(arguments)
    except (OSError, ImportError, RuntimeError, ValueError) as error:
        print(f"gem: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
