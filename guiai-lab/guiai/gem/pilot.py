from __future__ import annotations

import math
import os
from pathlib import Path
import tempfile

from .artline import ArtlineDocument
from .geometry import verify
from .pentomino import COLORS, benchmark_budgets, solve_tiling, PIECE_NAMES
from .render import draw_cairo, write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


GUIDE_PAGES = ("cover", "route", "hourglass", "signals", "practice")


def hourglass_weights(count=8, phase=.5):
    if isinstance(count, bool) or not isinstance(count, int) or not 2 <= count <= 64:
        raise ValueError("hourglass positions must be an integer from 2 to 64")
    if isinstance(phase, bool) or not isinstance(phase, (int, float)) or not math.isfinite(phase) or not 0 <= phase <= 1:
        raise ValueError("hourglass phase must be between zero and one")
    early = [count - index for index in range(count)]
    late = list(reversed(early))
    early = [value / sum(early) for value in early]
    late = [value / sum(late) for value in late]
    weights = [(1 - phase) * first + phase * second for first, second in zip(early, late)]
    return {
        "positions": count,
        "phase": phase,
        "early": early,
        "late": late,
        "weights": weights,
        "sum": sum(weights),
        "conserved": math.isclose(sum(weights), 1, rel_tol=0, abs_tol=1e-12),
        "transformer_modified": False,
        "security_validated": False,
        "scope": "Normalized convex redistribution only; no attention implementation, threat detection, or defense efficacy claim.",
    }


def packet_spacing(arrivals):
    if not isinstance(arrivals, (list, tuple)) or not 2 <= len(arrivals) <= 256:
        raise ValueError("arrivals require 2-256 finite ordered timestamps")
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) for value in arrivals):
        raise ValueError("arrivals require finite numeric timestamps")
    if any(second < first for first, second in zip(arrivals, arrivals[1:])):
        raise ValueError("arrival timestamps must be ordered")
    intervals = [second - first for first, second in zip(arrivals, arrivals[1:])]
    mean = sum(intervals) / len(intervals)
    deviation = sum(abs(value - mean) for value in intervals) / len(intervals)
    return {
        "arrivals": list(arrivals),
        "intervals": intervals,
        "mean_interval": mean,
        "mean_absolute_interval_deviation": deviation,
        "synthetic": True,
        "clock_offset_estimated": False,
        "scope": "Mean absolute spacing deviation, not an RFC 3550 jitter estimator or a measurement of a real network.",
    }


def _base(title, subtitle, page):
    document = ArtlineDocument()
    document.add_element("rectangle", bounds=[0, 0, 1000, 700], fill="#08111f", stroke="#20304a", width=1)
    document.add_element("text", position=[52, 68], text=title, size=34, stroke="#67e8f9", width=1)
    document.add_element("text", position=[54, 101], text=subtitle, size=16, stroke="#9fb1c8", width=1)
    document.add_element("line", points=[[52, 122], [948, 122]], stroke="#20304a", width=2)
    document.add_element("text", position=[54, 670], text=f"ZOE · PRACTICE NAVIGATOR · {page:02d} / 05", size=13, stroke="#67e8f9", width=1)
    document.add_element("text", position=[638, 670], text="Synthetic study · not flight guidance", size=13, stroke="#fda4af", width=1)
    return document


def cover_document():
    document = _base("ZOE", "PRACTICE NAVIGATOR · A field guide to time, space, signals, and the next attempt", 1)
    document.add_element("text", position=[57, 169], text="PILOT'S PRACTICE GUIDE", size=22, stroke="#fde68a", width=1)
    document.add_element("ellipse", center=[264, 395], radii=[156, 156], fill="#101b2b", stroke="#67e8f9", width=3)
    document.add_element("ellipse", center=[264, 395], radii=[126, 126], fill="none", stroke="#31445d", width=1)
    for angle in range(0, 360, 30):
        radians = math.radians(angle)
        document.add_element("line", points=[[264 + 132 * math.cos(radians), 395 + 132 * math.sin(radians)], [264 + 148 * math.cos(radians), 395 + 148 * math.sin(radians)]], stroke="#67e8f9", width=2)
    document.add_element("line", points=[[112, 395], [416, 395]], stroke="#31445d", width=1)
    document.add_element("line", points=[[264, 243], [264, 547]], stroke="#31445d", width=1)
    document.add_element("path", points=[[151, 468], [212, 389], [285, 412], [352, 302], [385, 352]], closed=False, smooth=True, stroke="#86efac", width=4)
    document.add_element("ellipse", center=[264, 395], radii=[41, 41], fill="#08111f", stroke="#f0abfc", width=3)
    document.add_element("text", position=[250, 409], text="Z", size=33, stroke="#f0abfc", width=1)
    document.add_element("text", position=[151, 581], text="OBSERVE · ORIENT · DECIDE · REVIEW", size=15, stroke="#9fb1c8", width=1)
    labels = (("TIME", "SPACE", "NEXT"), ("1", "2", "3"), ("OBS", "FIX", "PLAN"), ("PAST", "NOW", "AGAIN"))
    for row, values in enumerate(labels):
        for column, label in enumerate(values):
            left = 535 + column * 135
            top = 211 + row * 91
            document.add_element("rounded_rectangle", bounds=[left, top, left + 111, top + 67], radius=8, fill="#101b2b", stroke="#67e8f9" if row == 0 else "#31445d", width=2)
            document.add_element("text", position=[left + 18, top + 43], text=label, size=20, stroke="#fde68a" if row == 0 else "#d8e5f2", width=1)
    document.add_element("text", position=[545, 601], text="THE COCKPIT IS A PRACTICE SPACE", size=16, stroke="#f0abfc", width=1)
    return document


def route_document():
    document = _base("01 · Plot before you move", "A route is a sequence of inspectable choices, not a promise about the future", 2)
    for x in range(100, 901, 100):
        document.add_element("line", points=[[x, 170], [x, 540]], stroke="#20304a", width=1)
    for y in range(180, 541, 60):
        document.add_element("line", points=[[100, y], [900, y]], stroke="#20304a", width=1)
    points = [[140, 485], [285, 330], [460, 390], [670, 215], [830, 280]]
    document.add_element("path", points=points, closed=False, smooth=False, stroke="#67e8f9", width=4)
    labels = ("START", "OBSERVE", "ADJUST", "NEXT", "REVIEW")
    for index, (point, label) in enumerate(zip(points, labels)):
        document.add_element("ellipse", center=point, radii=[11, 11], fill="#fde68a", stroke="#fda4af", width=2)
        document.add_element("text", position=[point[0] - 28, point[1] + 34], text=label, size=13, stroke="#d8e5f2", width=1)
    document.add_element("text", position=[102, 589], text="remaining = max(0, agreed budget - elapsed)", size=19, stroke="#86efac", width=1)
    document.add_element("text", position=[102, 622], text="position′ = position + chosen displacement", size=18, stroke="#f0abfc", width=1)
    document.add_element("text", position=[622, 590], text="Toy coordinates only.", size=15, stroke="#fda4af", width=1)
    document.add_element("text", position=[622, 619], text="No wind, weather, or terrain model.", size=14, stroke="#fda4af", width=1)
    return document


def hourglass_document():
    document = _base("02 · The conserved hourglass", "A fixed quantity can move between past and future emphasis without being created", 3)
    report = hourglass_weights()
    outline = [[145, 178], [409, 178], [295, 351], [409, 524], [145, 524], [259, 351]]
    document.add_element("path", points=outline, closed=True, smooth=True, stroke="#67e8f9", width=4, fill="#101b2b")
    document.add_element("path", points=[[182, 210], [372, 210], [284, 329], [270, 329]], closed=True, smooth=True, fill="#fde68a", stroke="#fde68a", width=1)
    document.add_element("path", points=[[277, 380], [368, 492], [185, 492]], closed=True, smooth=True, fill="#f0abfc", stroke="#f0abfc", width=1)
    document.add_element("line", points=[[277, 326], [277, 392]], stroke="#fde68a", width=3)
    document.add_element("text", position=[167, 563], text="CONSTRAINT BUILDS CREATIVITY", size=16, stroke="#86efac", width=1)
    for index, weight in enumerate(report["weights"]):
        left = 490 + index * 54
        height = weight * 550
        document.add_element("rectangle", bounds=[left, 500 - height, left + 34, 500], fill="#67e8f9" if index < 4 else "#f0abfc", stroke="none", width=1)
        document.add_element("text", position=[left + 7, 524], text=str(index + 1), size=13, stroke="#9fb1c8", width=1)
    document.add_element("text", position=[491, 184], text="wᵢ(λ) = (1-λ)eᵢ + λlᵢ", size=23, stroke="#fde68a", width=1)
    document.add_element("text", position=[491, 219], text=f"Σwᵢ = {report['sum']:.1f} · λ = {report['phase']:.1f}", size=18, stroke="#86efac", width=1)
    document.add_element("text", position=[490, 570], text="Normalized toy weights; no transformer is modified.", size=15, stroke="#fda4af", width=1)
    document.add_element("text", position=[490, 600], text="Conservation is not security or attention control.", size=15, stroke="#fda4af", width=1)
    document.add_element("text", position=[490, 630], text="Inspired by the supplied Hourglass proposal; untested here.", size=13, stroke="#9fb1c8", width=1)
    return document


def signals_document():
    document = _base("03 · Signals through the hourglass", "Layers hide details; measurements reveal variation, not guarantees", 4)
    layers = ("APPLICATION", "PRESENTATION", "SESSION", "TRANSPORT", "NETWORK · IP", "DATA LINK", "PHYSICAL")
    for index, label in enumerate(layers):
        width = 140 if index == 4 else 230 if index in {3, 5} else 300
        left = 230 - width / 2
        top = 149 + index * 62
        document.add_element("rectangle", bounds=[left, top, left + width, top + 45], fill="#101b2b" if index != 4 else "#164e63", stroke="#67e8f9", width=1)
        document.add_element("text", position=[left + 15, top + 29], text=label, size=14, stroke="#d8e5f2", width=1)
    report = packet_spacing([0, 10, 23, 32, 49, 61, 79, 90])
    for index, value in enumerate(report["intervals"]):
        left = 485 + index * 59
        document.add_element("rectangle", bounds=[left, 495 - value * 15, left + 35, 495], fill="#f0abfc" if value > report["mean_interval"] else "#67e8f9", stroke="none", width=1)
        document.add_element("text", position=[left + 4, 519], text=f"{value:g}", size=13, stroke="#d8e5f2", width=1)
    document.add_element("text", position=[484, 171], text="SYNTHETIC ARRIVAL SPACING", size=18, stroke="#fde68a", width=1)
    document.add_element("text", position=[484, 205], text=f"mean = {report['mean_interval']:.2f} ms", size=17, stroke="#86efac", width=1)
    document.add_element("text", position=[484, 235], text=f"mean absolute deviation = {report['mean_absolute_interval_deviation']:.2f} ms", size=14, stroke="#86efac", width=1)
    document.add_element("text", position=[484, 561], text="Delay can vary. Clocks can disagree.", size=15, stroke="#fda4af", width=1)
    document.add_element("text", position=[484, 591], text="This plot is not a live network measurement.", size=14, stroke="#fda4af", width=1)
    document.add_element("text", position=[484, 621], text="Not an RTP jitter estimator or offset estimate.", size=13, stroke="#9fb1c8", width=1)
    return document


def practice_document():
    document = _base("04 · Build Rome, then change the clock", "Twelve pieces, sixty cells, and the same strategy under different finite budgets", 5)
    game_report = benchmark_budgets()
    order = list(PIECE_NAMES)
    import random
    random.Random("zoe-time-study").shuffle(order)
    placements = solve_tiling(order)
    for placement in placements:
        for dx, dy in placement["cells"]:
            left = 83 + (placement["x"] + dx) * 31
            top = 164 + (placement["y"] + dy) * 31
            document.add_element("rectangle", bounds=[left, top, left + 28, top + 28], fill=COLORS[placement["name"]], stroke="#08111f", width=1)
    document.add_element("text", position=[81, 517], text="6 × 10 · 12 × 5 = 60", size=17, stroke="#86efac", width=1)
    for index, row in enumerate(game_report["budgets"]):
        top = 180 + index * 82
        document.add_element("rounded_rectangle", bounds=[400, top - 28, 905, top + 42], radius=8, fill="#101b2b", stroke="#31445d", width=1)
        document.add_element("text", position=[425, top], text=f"{row['budget_seconds']:>3} s", size=21, stroke="#fde68a", width=1)
        document.add_element("text", position=[544, top], text=f"{row['pieces_placed']:2d} / 12 pieces", size=18, stroke="#d8e5f2", width=1)
        document.add_element("text", position=[739, top], text=row["status"].replace("_", " "), size=16, stroke="#f0abfc", width=1)
        document.add_element("text", position=[426, top + 26], text=f"{row['filled_cells']} cells · {row['holes']} holes · same synthetic strategy", size=13, stroke="#9fb1c8", width=1)
    document.add_element("text", position=[403, 540], text="One synthetic second per piece · gravity held at 3600 s", size=14, stroke="#86efac", width=1)
    document.add_element("text", position=[403, 570], text="A strategy comparison, not a human optimum or IQ measure.", size=14, stroke="#fda4af", width=1)
    document.add_element("text", position=[80, 597], text="Attempt value = reward + information + future skill + enjoyment - expected failure cost", size=14, stroke="#f0abfc", width=1)
    document.add_element("text", position=[80, 627], text="The attempt-value model is a decision lens, not a biological equation.", size=13, stroke="#9fb1c8", width=1)
    return document


def guide_document(page="cover"):
    documents = {
        "cover": cover_document,
        "route": route_document,
        "hourglass": hourglass_document,
        "signals": signals_document,
        "practice": practice_document,
    }
    if page not in documents:
        raise ValueError(f"unknown pilot guide page: {page}")
    return documents[page]()


def guide_page(page="cover"):
    document = guide_document(page)
    return document.scene(), {"page": page, "elements": len(document.elements), "synthetic": True, "certified_flight_material": False, "security_validated": False}


def write_guide_pdf(path):
    path = Path(path)
    if path.suffix.lower() != ".pdf":
        raise ValueError("pilot guide output must use a .pdf path")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("guide directory does not exist")
    try:
        import cairo
    except ImportError as error:
        raise RuntimeError("PDF output requires Cairo") from error
    for page in GUIDE_PAGES:
        scene, _ = guide_page(page)
        report = verify(scene)
        if not report.passed:
            raise ValueError(report.text())
    descriptor, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        surface = cairo.PDFSurface(str(temporary), 1000, 700)
        surface.restrict_to_version(cairo.PDF_VERSION_1_4)
        for page in GUIDE_PAGES:
            scene, _ = guide_page(page)
            draw_cairo(cairo.Context(surface), scene, 1000, 700)
            surface.show_page()
        surface.finish()
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    return path


def export_guide_page(path, page="cover", kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("guide page export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("guide directory does not exist")
    scene, _ = guide_page(page)
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
