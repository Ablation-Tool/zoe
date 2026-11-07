from __future__ import annotations

import hashlib
from pathlib import Path
import re


MAX_SOURCE_BYTES = 4 * 1024 * 1024


def _source(path, layout):
    path = Path(path)
    if not path.is_file():
        return {"path": layout.relative(path), "physical_path": str(path), "present": False}
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"host-integration source exceeds the 4 MiB bound: {path}")
    data = path.read_bytes()
    return {
        "path": layout.relative(path),
        "physical_path": str(path),
        "present": True,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _text(path):
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"host-integration source exceeds the 4 MiB bound: {path}")
    return path.read_text(encoding="utf-8")


def _version_key(value):
    return tuple(int(part) for part in value.split("."))


def host_integration_evidence(layout):
    from .cern_layout import CorpusLayout
    layout = CorpusLayout(layout)
    ftools = layout.path("source/ftools")
    wupper = layout.path("source/wupper")
    regmap = layout.path("source/regmap")
    drivers = layout.path("source/felix-tdaq-drivers")
    class_paths = {
        "acquisition": "FlxDaq.h",
        "offline_validation": "FlxChecker.h",
        "block_chunk_parser": "FlxParser.h",
        "dma_receiver": "FlxReceiver.h",
        "configuration": "FlxConfig.h",
        "upload_and_emulation": "FlxUpload.h",
    }
    ftool_classes = {}
    for role, name in class_paths.items():
        path = ftools / "src" / name
        record = _source(path, layout)
        if record["present"]:
            text = _text(path)
            record["methods"] = len(re.findall(r"^\s*(?:bool|void|int|int64_t|uint64_t|char\s*\*|std::string|uint8_t\s*\*)\s+\w+", text, re.MULTILINE))
        ftool_classes[role] = record
    daq_text = _text(ftools / "src" / "FlxDaq.h") if (ftools / "src" / "FlxDaq.h").is_file() else ""
    receiver_text = _text(ftools / "src" / "FlxReceiver.h") if (ftools / "src" / "FlxReceiver.h").is_file() else ""
    buffer_match = re.search(r"#define\s+DFLT_RECV_BUF_SIZE\s+(0x[0-9A-Fa-f]+)", receiver_text)
    ftools_result = {
        "root": _source(ftools / "README.md", layout),
        "classes": ftool_classes,
        "tool_source_count": len(list((ftools / "tools").glob("*.cpp"))) if (ftools / "tools").is_dir() else 0,
        "observation_tools": {
            "fcheck": {"mode": "offline-file", "blocked_options": {"-w": "writes ./dataout.dat"}},
            "ffile": {"mode": "offline-file"},
            "felink": {"mode": "offline-conversion"},
            "fscareply": {"mode": "offline-frame-parser"},
            "fcap": {"mode": "live-card-read"},
            "fedump": {"mode": "live-stream-read"},
            "frecv": {"mode": "live-stream-read"},
            "flx-info": {"mode": "live-card-read"},
            "flx-busy-mon": {"mode": "live-card-read"},
            "flx-dma-stat": {"mode": "live-card-read"},
        },
        "control_tools": {
            "fpepo": "peek becomes poke when a data word is supplied",
            "fflash": "writes firmware flash",
            "fflashprog": "loads flash image into FPGA",
            "feconf": "writes card configuration",
            "fupload": "uploads test or file data to e-links",
            "fplayback": "plays data through links",
            "femu": "controls onboard emulators",
            "fttcemu": "controls TTC emulator",
            "flx-reset": "resets card logic",
            "fgbtxconf": "writes GBTX registers",
            "fice": "reads or writes GBTX registers",
        },
        "statistics": [name for name in (
            "bytesAvailable", "bytesReceivedCount", "bytesWrittenCount", "bytesRecordedCount",
            "bytesRecordedInRunCount", "bytesFlushedCount", "bufferWrapCount", "bufferFullPercentage",
            "blocksChecked", "blockErrors", "seqNrErrors", "trailerErrors", "truncErrors",
            "errErrors", "crcErrors", "lengthErrors", "typeErrors",
        ) if re.search(rf"\b{name}\s*\(", daq_text)],
        "receiver_default_buffer_bytes": int(buffer_match.group(1), 16) if buffer_match else None,
        "source_derived_parser_features": ["block-size detection", "16/32-bit trailers", "chunk headers", "e-link filters", "SCA/CRC checks", "TTC/IC frames", "Phase 2 mapping"],
    }
    dma_path = wupper / "firmware" / "sources" / "pcie" / "dma_control.vhd"
    dma_text = _text(dma_path) if dma_path.is_file() else ""
    descriptor_match = re.search(r"NUMBER_OF_DESCRIPTORS\s*:\s*integer\s*:=\s*(\d+)", dma_text)
    wupper_result = {
        "sources": {
            role: _source(path, layout)
            for role, path in {
                "dma_control": dma_path,
                "dma_datapath": wupper / "firmware" / "sources" / "pcie" / "dma_read_write.vhd",
                "core": wupper / "firmware" / "sources" / "pcie" / "wupper_core.vhd",
                "linux_driver": wupper / "software" / "drivers" / "src" / "wupper.c",
                "contiguous_memory_driver": wupper / "software" / "drivers" / "src" / "cmem_rcc.c",
            }.items()
        },
        "descriptor_count": int(descriptor_match.group(1)) if descriptor_match else None,
        "capabilities": ["descriptor DMA", "circular buffers", "register map", "MSI-X interrupts", "backpressure thresholds", "resource locking"],
        "register_model": "BAR0 DMA, BAR1 interrupts, BAR2 application registers",
    }
    yaml_root = regmap / "yaml"
    versions = []
    for path in yaml_root.glob("registers-*.yaml"):
        match = re.fullmatch(r"registers-([0-9.]+)\.yaml", path.name)
        if match:
            versions.append((match.group(1), path))
    versions.sort(key=lambda row: _version_key(row[0]))
    latest_version, latest_path = versions[-1] if versions else (None, None)
    latest_text = _text(latest_path) if latest_path else ""
    register_names = sorted(set(re.findall(r"-\s+name:\s+([A-Z][A-Z0-9_{}]+)", latest_text)))
    regmap_result = {
        "versions": [version for version, _ in versions],
        "latest_version": latest_version,
        "latest_source": _source(latest_path, layout) if latest_path else None,
        "source_count": len(versions),
        "bar_roles": {"BAR0": "DMA descriptors and thresholds", "BAR1": "interrupt controller", "BAR2": "application-specific registers"},
        "dma_descriptor_count": int(match.group(1)) if (match := re.search(r"DMA_DESC:\s*\n\s*number:\s*(\d+)", latest_text)) else None,
        "status_register_examples": [name for name in register_names if any(token in name for token in ("STATUS", "EMPTY", "FULL", "DONE", "OUTSTANDING"))][:64],
        "write_sensitive_examples": [name for name in register_names if any(token in name for token in ("RESET", "ENABLE", "THRESHOLD", "POINTER"))][:64],
        "parser_scope": "bounded recognized YAML fields and register names; not a general YAML evaluator",
    }
    submodule_text = _text(drivers / ".gitmodules") if (drivers / ".gitmodules").is_file() else ""
    submodules = []
    for name in re.findall(r"path\s*=\s*(\S+)", submodule_text):
        path = drivers / name
        populated = path.is_dir() and any(item.is_file() for item in path.rglob("*"))
        submodules.append({"name": name, "source_present": populated, "status": "present" if populated else "unpopulated"})
    driver_result = {
        "packaging_source": _source(drivers / "Makefile", layout),
        "expected_submodules": submodules,
        "wupper_driver_fallback_present": wupper_result["sources"]["linux_driver"]["present"],
        "kernel_modules_referenced": ["cmem_rcc", "flx", "flxnet_dev", "flxnet_pcie"],
        "module_loading_performed": False,
    }
    return {
        "ftools": ftools_result,
        "wupper": wupper_result,
        "regmap": regmap_result,
        "drivers": driver_result,
        "zoe_execution_policy": {
            "source_analysis_only": True,
            "shell_execution": False,
            "hardware_reads": False,
            "hardware_writes": False,
            "module_loading": False,
            "raw_register_writes": False,
            "reason": "Zoe derives a structured capability map; it does not infer that sources, devices, drivers, or permission to operate them are present.",
        },
    }


def star_flink_evidence(layout, simulation):
    sources = [row for row in simulation["html_sources"] if row["path"].startswith("sims/star_flink/")]
    required = {
        "pkg_star_flink.vhd", "star_flink_encoder.vhd", "star_flink_decoder.vhd",
        "star_flink_sim_spy.vhd", "star_flink_tester.vhd",
    }
    present = {row["title"] for row in sources}
    return {
        "root": "sims/star_flink",
        "source_files": sources,
        "primary_source_views_complete": required <= present,
        "ieee_compatibility_packages": [row for row in sources if row["path"].startswith("sims/star_flink/ieee/")],
        "protocol": {
            "symbol_bits": 4,
            "data_bits_per_symbol": 3,
            "l0id_bits": 8,
            "data_symbols_per_l0id": 3,
            "clock_domains_mhz": [40, 160],
            "symbols": {
                "IDLE": "0x1", "BCR": "0x2", "LS": "0x3", "BCRLS": "0x4",
                "PR": "0x5", "LP": "0x6", "DATA7": "0x7",
                "DATA0-DATA6": "0x8-0xe",
            },
            "invalid_symbols": ["0x0", "0xf"],
            "shared_l0id_bus": "PR and LP each select mode; three 3-bit groups assemble one 8-bit L0ID",
            "alignment": "decoder chooses among eight shift-register/edge positions; tester selects 010",
            "serializer_scope": "toy 160 Mb serializer/deserializer for simulation",
        },
        "testbench": {
            "block_diagram": "sims/star_flink/readout130/star_flink_tb/struct_bd.svg",
            "path": ["star_flink_tester", "star_flink_encoder", "serial link", "star_flink_decoder"],
            "symbol_monitors": ["Uencspy", "Udecspy"],
            "stimulus": ["BCR", "LS", "BCRLS", "PR", "LP", "back-to-back PR/LP with BCR/LS"],
            "selected_alignment": "010",
            "output_enable": "asserted after reset and alignment selection",
        },
        "analysis_scope": "all primary HDL source views and testbench connectivity inspected; IEEE compatibility packages inventoried; no HDL simulation run",
        "simulation_run": False,
        "hardware_validation": False,
    }
