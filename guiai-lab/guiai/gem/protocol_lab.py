from __future__ import annotations

from pathlib import Path

from .atlas import _scene, _text
from .geometry import verify
from .render import write_png, write_svg
from .runner import verify_vdi
from .vdi import write_metafile


MODES = {"i2c": 0, "jtag": 1, "parallel": 2, "register": 3}


def _bytes(values, label="bytes"):
    if isinstance(values, (str, bytes, bytearray)):
        values = list(values)
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"{label} must be a sequence")
    result = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 255:
            raise ValueError(f"{label} contains a value outside the 8-bit range")
        result.append(value)
    return result


def header_checksum(header):
    header = _bytes(header, "SPECS header")
    if len(header) != 4:
        raise ValueError("SPECS header must contain four bytes")
    checksum = 0
    for value in header[:3]:
        checksum ^= (value >> 4) ^ (value & 0x0F)
    return checksum ^ (header[3] >> 4)


def payload_checksum(payload):
    checksum = 0
    for value in _bytes(payload, "SPECS payload"):
        checksum ^= value
    return checksum


def first_header_byte(address, mode):
    if isinstance(address, bool) or not isinstance(address, int) or not 0 <= address <= 0x3F:
        raise ValueError("SPECS slave address is six bits")
    if not isinstance(mode, (str, int)) or isinstance(mode, bool):
        raise ValueError("invalid SPECS mode")
    value = MODES.get(mode, mode) if isinstance(mode, str) else mode
    if isinstance(value, bool) or not isinstance(value, int) or value not in range(4):
        raise ValueError("invalid SPECS mode")
    return (address << 2) | value


def encode_specs_frame(header, payload):
    header = _bytes(header, "SPECS header")
    payload = _bytes(payload, "SPECS payload")
    if len(header) != 3:
        raise ValueError("SPECS encoding requires three header bytes")
    if len(payload) > 255:
        raise ValueError("SPECS demo payload is limited to 255 bytes")
    check = header_checksum((*header, 0))
    words = [{"value": value, "last": False} for value in (*header, check)]
    words.extend({"value": value, "last": False} for value in payload)
    words.append({"value": payload_checksum(payload), "last": False})
    if payload:
        words[-2]["last"] = True
    return words


def decode_specs_frame(words):
    if not isinstance(words, (list, tuple)) or not 5 <= len(words) <= 260:
        raise ValueError("SPECS frame must contain 5-260 words")
    values = []
    for word in words:
        if not isinstance(word, dict) or set(word) != {"value", "last"} or not isinstance(word["last"], bool):
            raise ValueError("SPECS word requires value and last fields")
        values.extend(_bytes([word["value"]], "SPECS word"))
    if header_checksum(values[:4]) != values[3] & 0x0F:
        raise ValueError("SPECS header checksum mismatch")
    if payload_checksum(values[4:-1]) != values[-1]:
        raise ValueError("SPECS payload checksum mismatch")
    expected_last = len(words) - 2 if len(words) > 5 else None
    for index, word in enumerate(words):
        if word["last"] != (index == expected_last):
            raise ValueError("SPECS ninth-bit marker mismatch")
    return values[:3], values[4:-1]


def is_long_read_count(read_count):
    if isinstance(read_count, bool) or not isinstance(read_count, int) or not 0 <= read_count <= 255:
        raise ValueError("read count outside 8-bit range")
    return read_count > 0x80


def reported_read_count(read_count):
    if isinstance(read_count, bool) or not isinstance(read_count, int) or not 0 <= read_count <= 255:
        raise ValueError("read count outside 8-bit range")
    return read_count & 0x7F


def amac_read_reply(identifier, sequence, address, data):
    for value, maximum, label in ((identifier, 0x1F, "communications ID"), (sequence, 7, "sequence"), (address, 0xFF, "address")):
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
            raise ValueError(f"invalid AMAC {label}")
    if isinstance(data, bool) or not isinstance(data, int) or not 0 <= data <= 0xFFFFFFFF:
        raise ValueError("AMAC data must be a 32-bit unsigned value")
    return [(identifier << 3) | sequence, address, *data.to_bytes(4, "big")]


def decode_amac_reply(reply):
    values = _bytes(reply, "AMAC reply")
    if len(values) not in {1, 6}:
        raise ValueError("AMAC reply must contain one acknowledgement byte or six read-reply bytes")
    status = values[0]
    result = {"id": status >> 3, "sequence": status & 7, "hex": bytes(values).hex().upper()}
    if len(values) == 6:
        result.update({"address": values[1], "data": int.from_bytes(values[2:], "big")})
    return result


def amac_read_next(address, data, sequence):
    if isinstance(sequence, bool) or not isinstance(sequence, int) or not 0 <= sequence <= 7:
        raise ValueError("AMAC sequence must be between zero and seven")
    if isinstance(address, bool) or not isinstance(address, int) or not 0 <= address <= 0xFF:
        raise ValueError("AMAC address must be between zero and 255")
    if isinstance(data, bool) or not isinstance(data, int) or not 0 <= data <= 0xFFFFFFFF:
        raise ValueError("AMAC data must be a 32-bit unsigned value")
    return (address + 1) & 0xFF, data, (sequence + 1) & 7


def amac_demo_replies(identifier=0x15):
    replies = [amac_read_reply(identifier, 7, 0x50, 0xFFFFFFF0)]
    address, data, sequence = 0x50, 0xFFFFFFF0, 7
    for _ in range(2):
        address, data, sequence = amac_read_next(address, data + 1, sequence)
        replies.append(amac_read_reply(identifier, sequence, address, data))
    return replies


def protocol_scene(read_count=0x80):
    header = [first_header_byte(0x15, "jtag"), read_count, 0x01]
    payload = [0xDE, 0xAD, 0xBE, 0xEF]
    words = encode_specs_frame(header, payload)
    long_frame = is_long_read_count(read_count)
    reported = reported_read_count(read_count)
    reply = amac_read_reply(0x15, 3, 0x41, 0x12345678)
    decoded = decode_amac_reply(reply)
    replies = amac_demo_replies()
    objects = [{"id": "background", "type": "rectangle", "bounds": [0, 0, 1000, 760], "stroke": "#08111f", "fill": "#08111f", "width": 1}]
    objects.append(_text("title", [44, 57], "Zoe Protocol Lab", 31, "#67e8f9"))
    objects.append(_text("subtitle", [46, 86], "SPECS and AMAC · recovered formats, not device commands", 15, "#9fb1c8"))
    objects.append(_text("specs-heading", [50, 141], "SPECS serial framing", 20, "#fde68a"))
    objects.append(_text("specs-count", [50, 173], f"count=0x{read_count:02X} · long={str(long_frame).lower()} · reported={reported}", 15, "#d8e5f2"))
    colors = ["#67e8f9"] * 4 + ["#fde68a"] * len(payload) + ["#f0abfc"]
    for index, word in enumerate(words):
        left = 50 + index * 61
        objects.append({"id": f"word-{index}", "type": "rectangle", "bounds": [left, 198, left + 49, 239], "stroke": colors[index], "fill": "#101b2b", "width": 2})
        objects.append(_text(f"word-text-{index}", [left + 9, 224], f"{word['value']:02X}", 15, colors[index]))
        if word["last"]:
            objects.append(_text("ninth-marker", [left - 3, 257], "9th", 11, "#f0abfc"))
    objects.append(_text("word-labels", [51, 282], "3 header + H3 checksum · payload · XOR trailer", 13, "#9fb1c8"))
    objects.append(_text("checksum", [51, 311], f"H3={words[3]['value']:02X} · payload XOR={words[-1]['value']:02X} · checksums are not authentication", 13, "#fda4af"))
    objects.append(_text("boundary-title", [50, 353], "Read-count boundary: 128 is not long; 129 is long", 15, "#fde68a"))
    for offset, count in enumerate(range(120, 136)):
        left = 51 + offset * 34
        active = is_long_read_count(count)
        height = 66 if active else 20
        color = "#f0abfc" if count == read_count else "#67e8f9" if active else "#31445d"
        objects.append({"id": f"count-{count}", "type": "rectangle", "bounds": [left, 448 - height, left + 23, 448], "stroke": color, "fill": color, "width": 1})
        if count % 4 == 0 or count in {128, 129}:
            objects.append(_text(f"count-label-{count}", [left - 2, 471], str(count), 11, color))
    objects.append(_text("boundary-note", [51, 502], f"count {read_count}: long={str(long_frame).lower()} · reported bit-7-masked count={reported}", 13, "#d8e5f2"))
    objects.append(_text("amac-heading", [664, 141], "AMAC reply + read-next", 20, "#fde68a"))
    objects.append(_text("amac-reply", [664, 177], bytes(reply).hex().upper(), 20, "#67e8f9"))
    for index, (label, value) in enumerate((("ID", f"0x{decoded['id']:02X}"), ("sequence", decoded["sequence"]), ("address", f"0x{decoded['address']:02X}"), ("data", f"0x{decoded['data']:08X}"))):
        objects.append(_text(f"amac-field-{index}", [664, 212 + index * 29], f"{label}: {value}", 14, "#d8e5f2"))
    objects.append(_text("read-next-title", [664, 342], "Recorded focused-RTL examples", 14, "#9fb1c8"))
    for index, reply in enumerate(replies):
        objects.append(_text(f"read-next-{index}", [664, 375 + index * 37], f"{'read' if index == 0 else f'next {index}'}: {bytes(reply).hex().upper()}", 16, "#86efac" if index else "#67e8f9"))
    objects.append(_text("wrap-note", [664, 494], "seq 7 -> 0 · addr 0x50 -> 0x51 -> 0x52", 12, "#fde68a"))
    objects.append(_text("source", [51, 573], "Source: recovered SPECS and Endeavour research · model and recorded examples only", 13, "#9fb1c8"))
    objects.append(_text("scope", [51, 605], "No hardware, firmware, FPGA, or network operation · no new proof of correctness", 13, "#fda4af"))
    objects.append(_text("specs-long-definition", [51, 648], "SPECS long: count > 0x80 · reported: count & 0x7F · LSB-first bytes + ninth-bit marker", 14, "#d8e5f2"))
    objects.append(_text("firewall", [51, 687], "Measurement != evidence != belief update != action", 14, "#9fb1c8"))
    objects.append(_text("source-cern", [51, 722], "CERN / EDMS / Endeavour protocol research · preserve provenance and unknowns", 13, "#67e8f9"))
    scene = _scene("zoe-protocol-lab", 1000, 760, objects, "Zoe Protocol Lab · SPECS and AMAC evidence")
    report = {
        "read_count": read_count,
        "long": long_frame,
        "reported": reported,
        "frame_hex": " ".join(f"{word['value']:02X}" for word in words),
        "header_checksum": words[3]["value"],
        "payload_checksum": words[-1]["value"],
        "ninth_bit_index": next((index for index, word in enumerate(words) if word["last"]), None),
        "amac": decoded,
        "read_next_hex": [bytes(reply).hex().upper() for reply in replies],
        "hardware_accessed": False,
        "checksum_is_authentication": False,
        "source": "/media/cowboy/research/CERN/analysis/REPORT.md",
        "summary": f"SPECS count={read_count} · long={str(long_frame).lower()} · reported={reported}\nAMAC sequence 7 → 0 · address 0x50 → 0x51 → 0x52\nRecovered examples · no hardware command",
    }
    return scene, report


def export_protocol(path, read_count=0x80, kind=None, width=1400):
    path = Path(path)
    kind = kind or path.suffix.lower().lstrip(".")
    if kind not in {"svg", "png", "gem"}:
        raise ValueError("protocol export must be svg, png, or gem")
    if path.exists():
        raise FileExistsError(path)
    if not path.parent.is_dir():
        raise ValueError("protocol export directory does not exist")
    scene, _ = protocol_scene(read_count)
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
