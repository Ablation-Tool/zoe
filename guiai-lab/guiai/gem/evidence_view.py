from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from .evidence import (
    EvidenceIndex, demo_index, export_navigator, navigator_scene,
    save_evidence_report, shadow_finding, write_navigator_gallery,
)
from .twin import export_wav, timing_replay
from .video_library import VideoLibrary, export_video_library_scene, save_video_report


def parser():
    result = argparse.ArgumentParser(prog="evidence", description="Zoe Evidence Navigator · source-first bridges and bounded replay")
    commands = result.add_subparsers(dest="command", required=True)
    scene = commands.add_parser("scene", help="open the evidence navigator or export its scene")
    scene.add_argument("--index", help="explicit document-images/index.json")
    scene.add_argument("--bridge", type=int, default=1)
    scene.add_argument("--query", default="")
    scene.add_argument("--replay", action="store_true", help="include a synthetic timing/DMA replay")
    scene.add_argument("--verify", action="store_true", help="verify source, preview, and compatibility hashes while loading")
    scene.add_argument("--output", help="new .svg, .png, or .gem scene instead of opening GTK")
    scene.add_argument("--format", choices=("svg", "png", "gem"))
    scene.add_argument("--width", type=int, default=1400)
    query = commands.add_parser("query", help="retrieve cited evidence without generating telemetry")
    _index_arguments(query)
    query.add_argument("--query", default="")
    query.add_argument("--bridge", type=int)
    query.add_argument("--output")
    bridge = commands.add_parser("bridge", help="inspect one of the seven bridge proposals")
    _index_arguments(bridge)
    bridge.add_argument("--id", type=int, required=True)
    bridge.add_argument("--output")
    curriculum = commands.add_parser("curriculum", help="show a C1-C4 practice prompt and cited examples")
    _index_arguments(curriculum)
    curriculum.add_argument("--level", type=int, required=True)
    curriculum.add_argument("--query", default="")
    curriculum.add_argument("--output")
    verify = commands.add_parser("verify", help="verify all source, preview, compatibility, and bridge links")
    _index_arguments(verify)
    verify.add_argument("--output")
    twin = commands.add_parser("twin", help="generate a bounded synthetic timing/DMA replay and optional WAV")
    _index_arguments(twin)
    twin.add_argument("--channels", type=int, default=24)
    twin.add_argument("--events", type=int, default=64)
    twin.add_argument("--frequency", default="40.08")
    twin.add_argument("--buffer-limit", type=int, default=8)
    twin.add_argument("--consume-every", type=int, default=3)
    twin.add_argument("--output")
    twin.add_argument("--wav")
    ladder = commands.add_parser("ladder", help="compare LCB and STAR/Flink observation schemas without a hardware bridge")
    _index_arguments(ladder)
    ladder.add_argument("--stimuli", nargs="*")
    ladder.add_argument("--output")
    manifest = commands.add_parser("manifest", help="emit an observe-only manifest with explicit blocked operations")
    _index_arguments(manifest)
    manifest.add_argument("--output")
    shadow = commands.add_parser("shadow", help="retrieve exact saved findings without calling an LLM")
    shadow.add_argument("--finding", required=True)
    shadow.add_argument("--output")
    gallery = commands.add_parser("gallery", help="write a filtered local gallery with original previews and source links")
    _index_arguments(gallery)
    gallery.add_argument("--query", default="")
    gallery.add_argument("--output", required=True)
    video = commands.add_parser("video", help="use the original vidlib for cited transcript retrieval")
    video.add_argument("--library", default=str(Path.home() / "vidlib"), help="vidlib Markdown library; default: ~/vidlib")
    video.add_argument("--vidlib", default="vidlib", help="original vidlib executable or path")
    modes = video.add_mutually_exclusive_group(required=True)
    modes.add_argument("--search", help="search an existing local library without requesting network access")
    modes.add_argument("--index", dest="rebuild_index", action="store_true", help="explicitly rebuild the existing library index")
    modes.add_argument("--url", help="explicit YouTube video or playlist URL to retrieve")
    video.add_argument("--playlist", action="store_true", help="explicitly permit playlist retrieval; required for playlist URLs")
    video.add_argument("--limit", type=int, default=16, help="maximum cited results, from 1 to 64")
    video.add_argument("--timeout", type=float, default=300, help="original-tool process timeout in seconds")
    video.add_argument("--output", help="new no-overwrite Zoe evidence JSON report")
    video.add_argument("--scene-output", help="also export a new .svg, .png, or .gem citation scene")
    return result


def _index_arguments(parser):
    parser.add_argument("--index", help="explicit document-images/index.json")
    parser.add_argument("--verify", action="store_true", help="verify source, preview, and compatibility hashes while loading")
    parser.add_argument("--color")
    parser.add_argument("--complexity", type=int)
    parser.add_argument("--purpose")
    parser.add_argument("--novelty", type=int)
    parser.add_argument("--limit", type=int, default=16)


def _index(arguments):
    return EvidenceIndex.load(arguments.index, verify=arguments.verify) if arguments.index else demo_index()


def _filters(arguments):
    return {key: getattr(arguments, key) for key in ("color", "complexity", "purpose", "novelty", "limit")}


def _print(document):
    print(json.dumps(document, ensure_ascii=False, sort_keys=True))


def launch_evidence(index, bridge_id=1, timeline=None):
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("Zoe Evidence Navigator requires a GTK display; use --output for headless export")
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_foreign("cairo")
    from gi.repository import Gtk
    from .atlas_view import AtlasWindow
    window = AtlasWindow("evidence", evidence_index=index, bridge_id=bridge_id, timeline=timeline)
    window.show_all()
    window.connect("destroy", Gtk.main_quit)
    Gtk.main()
    return window


def main(argv=None):
    arguments = parser().parse_args(argv)
    try:
        if arguments.command == "scene":
            index = _index(arguments)
            timeline = timing_replay(index=index) if arguments.replay else None
            if arguments.output:
                output = export_navigator(arguments.output, index, arguments.bridge, timeline, arguments.format, arguments.width, arguments.query)
                _print({"instrument": "zoe-evidence-navigator", "output": str(output), "bytes": output.stat().st_size, "executed": False})
                return 0
            launch_evidence(index, arguments.bridge, timeline)
            return 0
        if arguments.command == "query":
            report = _index(arguments).retrieve(arguments.query, arguments.bridge, **_filters(arguments))
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "bridge":
            report = _index(arguments).bridge(arguments.id)
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "curriculum":
            report = _index(arguments).curriculum(arguments.level, arguments.query)
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "verify":
            index = EvidenceIndex.load(arguments.index, verify=True)
            bridges = [index.bridge(identifier) for identifier in range(1, 8)]
            report = {
                "instrument": "zoe-evidence-verification",
                "document_count": len(index.records),
                "compatibility_links_verified": len(index.records),
                "bridge_links_verified": sum(len(bridge["components"]) for bridge in bridges),
                "missing_bridge_targets": [component for bridge in bridges for component in bridge["components"] if not component["exists"]],
                "distribution": index.distribution(),
                "source_hashes_verified": True,
                "executed": False,
            }
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "twin":
            timeline = timing_replay(arguments.channels, arguments.events, arguments.frequency, arguments.buffer_limit, arguments.consume_every, _index(arguments))
            if arguments.output:
                from .twin import save_timeline
                save_timeline(timeline, arguments.output)
            audio = export_wav(timeline, arguments.wav)[1] if arguments.wav else None
            _print({"instrument": "zoe-timing-readout-twin", "events": timeline["event_count"], "descriptors": len(timeline["descriptors"]), "digest": timeline["digest"], "audio": audio, "hardware_accessed": False})
            return 0
        if arguments.command == "ladder":
            report = _index(arguments).ladder(arguments.stimuli)
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "manifest":
            report = _index(arguments).manifest()
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "shadow":
            report = shadow_finding(arguments.finding)
            if arguments.output:
                save_evidence_report(report, arguments.output)
            _print(report)
            return 0
        if arguments.command == "gallery":
            index = _index(arguments)
            output, report = write_navigator_gallery(index, arguments.output, arguments.query, arguments.color, arguments.complexity, arguments.purpose, arguments.limit)
            _print({"output": str(output), **report})
            return 0
        if arguments.command == "video":
            if arguments.playlist and not arguments.url:
                raise ValueError("--playlist requires --url")
            for destination, suffixes in ((arguments.output, {".json"}), (arguments.scene_output, {".svg", ".png", ".gem"})):
                if destination is None:
                    continue
                output = Path(destination)
                if output.exists():
                    raise FileExistsError(output)
                if output.suffix.lower() not in suffixes:
                    raise ValueError(f"vidlib output must use {', '.join(sorted(suffixes))}")
                if not output.parent.is_dir():
                    raise ValueError("vidlib output directory does not exist")
            library = VideoLibrary(arguments.library, arguments.vidlib, arguments.limit, arguments.timeout)
            if arguments.search is not None:
                report = library.search(arguments.search)
            elif arguments.rebuild_index:
                report = library.rebuild_index()
            else:
                report = library.fetch(arguments.url, arguments.playlist)
            if arguments.scene_output:
                export_video_library_scene(arguments.scene_output, report)
            if arguments.output:
                save_video_report(report, arguments.output)
            _print(report)
            return report["returncode"]
        return 2
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        print(f"evidence: {error}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
