"""
Digital Research GEM / FreeGEM / ViewMAX Spec-Exact Codecs & AES Runtime.

Built directly against John Elliott's GEM Information Archive
(`https://www.seasip.info/Gem/`) and Nathan Lineback's ToastyTech GUI Gallery
(`http://toastytech.com/guis/indexgem.html`):
  - `palette.html`   — Standard 16-color GEM/VDI palette & GEM/5 extended palette
  - `aestruct.html`  — 24-byte `OBJECT`, 28-byte `TEDINFO`, `GRECT`, flags/states
  - `aes.html`       — `wind_create` widget bitmasks, 7-window limit, `form_alert`
  - `aesmsg.html`    — 16-byte (`<8h`) AES message packets (`MN_SELECTED`, `WM_*`)
  - `filefmt.html`   — PC GEM little-endian `.RSC` binary resource format (`RSHDR`)
  - `ff_gem.html`    — Little-endian 24-word `.GEM` VDI metafile spec validator
  - `ff_img.html`    — Big-endian RLE `.IMG` / `XIMG` multi-plane raster bitmap codec

Pure Python stdlib — zero external dependencies, deterministic byte-exact roundtrips.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import struct
from typing import Any, Dict, List, Optional, Sequence, Tuple

# ============================================================================
# 1. Exact GEM Palettes (seasip.info/Gem/palette.html)
# ============================================================================

GEM_STANDARD_PALETTE: Dict[int, Tuple[str, Tuple[int, int, int], str]] = {
    0:  ("white",        (255, 255, 255), "#FFFFFF"),
    1:  ("black",        (0,   0,   0),   "#000000"),
    2:  ("red",          (255, 0,   0),   "#FF0000"),
    3:  ("green",        (0,   255, 0),   "#00FF00"),
    4:  ("blue",         (0,   0,   255), "#0000FF"),
    5:  ("cyan",         (0,   255, 255), "#00FFFF"),
    6:  ("yellow",       (255, 255, 0),   "#FFFF00"),
    7:  ("magenta",      (255, 0,   255), "#FF00FF"),
    8:  ("light_grey",   (173, 170, 173), "#ADAAAD"),
    9:  ("dark_grey",    (82,  85,  82),  "#525552"),
    10: ("dark_red",     (173, 0,   0),   "#AD0000"),
    11: ("dark_green",   (0,   170, 0),   "#00AA00"),
    12: ("dark_blue",    (0,   0,   173), "#0000AD"),
    13: ("dark_cyan",    (0,   170, 173), "#00AAAD"),
    14: ("dark_yellow",  (173, 170, 0),   "#ADAA00"),
    15: ("dark_magenta", (173, 0,   173), "#AD00AD"),
}

GEM5_PALETTE_OVERRIDES: Dict[int, Tuple[str, Tuple[int, int, int], str]] = {
    8:  ("gem5_teal",     (0,   117, 107), "#00756B"),
    9:  ("gem5_gold",     (255, 195, 0),   "#FFC300"),
    10: ("gem5_slate",    (99,  97,  99),  "#636163"),
    11: ("gem5_sage",     (173, 195, 173), "#ADC3AD"),
    12: ("gem5_sage_alt", (173, 195, 173), "#ADC3AD"),
    13: ("gem5_paper",    (239, 235, 239), "#EFEBEF"),
    14: ("gem5_silver",   (198, 195, 198), "#C6C3C6"),
    15: ("gem5_pewter",   (156, 154, 156), "#9C9A9C"),
}

GEM_NAME_TO_INDEX: Dict[str, int] = {
    name: idx for idx, (name, _rgb, _hx) in GEM_STANDARD_PALETTE.items()
}
GEM_HEX_TO_INDEX: Dict[str, int] = {
    hx.upper(): idx for idx, (_name, _rgb, hx) in GEM_STANDARD_PALETTE.items()
}


def rgb_to_vdi_1000(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """Convert 8-bit RGB (0..255) into GEM VDI `vs_color` 0..1000 scale."""
    return tuple(int(round(max(0, min(255, c)) * 1000 / 255)) for c in rgb)  # type: ignore[return-value]


def nearest_gem_color_index(color: str) -> int:
    """Map a color name or #RRGGBB hex string to the closest GEM Standard index 0..15."""
    if not color or color == "none":
        return 0
    low = color.strip().lower()
    if low in GEM_NAME_TO_INDEX:
        return GEM_NAME_TO_INDEX[low]
    up = color.strip().upper()
    if up in GEM_HEX_TO_INDEX:
        return GEM_HEX_TO_INDEX[up]
    if up.startswith("#") and len(up) == 7:
        try:
            r, g, b = int(up[1:3], 16), int(up[3:5], 16), int(up[5:7], 16)
        except ValueError:
            return 1
        best_idx = 1
        best_d = 10**9
        for idx, (_nm, (pr, pg, pb), _hx) in GEM_STANDARD_PALETTE.items():
            d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if d < best_d:
                best_d = d
                best_idx = idx
        return best_idx
    return 1


# ============================================================================
# 2. Exact AES Constants, Messages, Window Styles & form_alert
#    (seasip.info/Gem/aes.html, aesmsg.html, aestruct.html)
# ============================================================================

# OBJECT types (aestruct.html)
G_BOX = 20
G_TEXT = 21
G_BOXTEXT = 22
G_IMAGE = 23
G_USERDEF = 24
G_IBOX = 25
G_BUTTON = 26
G_BOXCHAR = 27
G_STRING = 28
G_FTEXT = 29
G_FBOXTEXT = 30
G_ICON = 31
G_TITLE = 32
G_CLRICN = 33
G_DTMFDB = 34

OB_TYPE_NAMES: Dict[int, str] = {
    G_BOX: "G_BOX", G_TEXT: "G_TEXT", G_BOXTEXT: "G_BOXTEXT", G_IMAGE: "G_IMAGE",
    G_USERDEF: "G_USERDEF", G_IBOX: "G_IBOX", G_BUTTON: "G_BUTTON", G_BOXCHAR: "G_BOXCHAR",
    G_STRING: "G_STRING", G_FTEXT: "G_FTEXT", G_FBOXTEXT: "G_FBOXTEXT", G_ICON: "G_ICON",
    G_TITLE: "G_TITLE", G_CLRICN: "G_CLRICN", G_DTMFDB: "G_DTMFDB",
}

# OBJECT flags (aestruct.html)
SELECTABLE = 0x0001
DEFAULT = 0x0002
EXIT = 0x0004
EDITABLE = 0x0008
RBUTTON = 0x0010
LASTOB = 0x0020
TOUCHEXIT = 0x0040
HIDETREE = 0x0080
INDIRECT = 0x0100
ESCCANCEL = 0x0200
SCROLLER = 0x0800
FLAG3D = 0x1000
USECOLORCAT = 0x2000
FL3DBAK = 0x4000

# OBJECT states (aestruct.html)
NORMAL = 0x0000
SELECTED = 0x0001
CROSSED = 0x0002
CHECKED = 0x0004
DISABLED = 0x0008
OUTLINED = 0x0010
SHADOWED = 0x0020
WHITEBAK = 0x0040

# wind_create styles (aes.html Function 100)
NAME = 0x0001
CLOSER = 0x0002
FULLER = 0x0004
MOVER = 0x0008
INFO = 0x0010
SIZER = 0x0020
UPARROW = 0x0040
DNARROW = 0x0080
VSLIDE = 0x0100
LFARROW = 0x0200
RTARROW = 0x0400
HSLIDE = 0x0800
STANDARD_WINDOW_KIND = NAME | CLOSER | FULLER | MOVER | INFO | SIZER | UPARROW | DNARROW | VSLIDE
MAX_AES_APP_WINDOWS = 7  # Single-tasking PC GEM allows 7 app windows + handle 0 desktop

# AES message types (aesmsg.html — all messages are 16 bytes = eight 16-bit words)
MN_SELECTED = 10
WM_REDRAW = 20
WM_TOPPED = 21
WM_CLOSED = 22
WM_FULLED = 23
WM_ARROWED = 24
WM_HSLID = 25
WM_VSLID = 26
WM_SIZED = 27
WM_MOVED = 28
WM_NEWTOP = 29
WM_UNTOPPED = 30
AC_OPEN = 40
AC_CLOSE = 41

AES_MSG_NAMES: Dict[int, str] = {
    MN_SELECTED: "MN_SELECTED",
    WM_REDRAW: "WM_REDRAW",
    WM_TOPPED: "WM_TOPPED",
    WM_CLOSED: "WM_CLOSED",
    WM_FULLED: "WM_FULLED",
    WM_ARROWED: "WM_ARROWED",
    WM_HSLID: "WM_HSLID",
    WM_VSLID: "WM_VSLID",
    WM_SIZED: "WM_SIZED",
    WM_MOVED: "WM_MOVED",
    WM_NEWTOP: "WM_NEWTOP",
    WM_UNTOPPED: "WM_UNTOPPED",
    AC_OPEN: "AC_OPEN",
    AC_CLOSE: "AC_CLOSE",
}


def encode_aes_message(
    msg_type: int,
    sender_apid: int = 0,
    extra_len: int = 0,
    w3: int = 0,
    w4: int = 0,
    w5: int = 0,
    w6: int = 0,
    w7: int = 0,
) -> bytes:
    """Pack a standard 16-byte (8 x signed 16-bit word) PC GEM AES message."""
    return struct.pack("<8h", msg_type, sender_apid, extra_len, w3, w4, w5, w6, w7)


def decode_aes_message(raw: bytes) -> Dict[str, Any]:
    """Decode a 16-byte PC GEM AES message into structured words + symbolic name."""
    if len(raw) != 16:
        raise ValueError(f"AES message must be exactly 16 bytes, got {len(raw)}")
    words = struct.unpack("<8h", raw)
    return {
        "msg_type": words[0],
        "name": AES_MSG_NAMES.get(words[0], f"MSG_{words[0]}"),
        "sender_apid": words[1],
        "extra_len": words[2],
        "data": list(words[3:]),
        "words": list(words),
    }


def build_form_alert(icon: int, lines: Sequence[str], buttons: Sequence[str]) -> str:
    """Format an exact GEM AES Function 52 `form_alert` string `[icon][l1|...][b1|...]`.

    Per seasip.info/Gem/aes.html:
      - icon: 0=none, 1=note/warning, 2=question, 3=stop
      - lines: 1..5 text lines separated by `|`
      - buttons: 1..3 button captions separated by `|`
    """
    if icon not in (0, 1, 2, 3):
        raise ValueError("form_alert icon must be 0, 1, 2, or 3")
    clean_lines = [str(ln).replace("[", "(").replace("]", ")").replace("|", "/")[:40] for ln in lines if str(ln).strip()]
    clean_btns = [str(b).replace("[", "(").replace("]", ")").replace("|", "/")[:16] for b in buttons if str(b).strip()]
    if not 1 <= len(clean_lines) <= 5:
        raise ValueError("form_alert requires 1 to 5 lines")
    if not 1 <= len(clean_btns) <= 3:
        raise ValueError("form_alert requires 1 to 3 buttons")
    return f"[{icon}][{'|'.join(clean_lines)}][{'|'.join(clean_btns)}]"


def parse_form_alert(alert_str: str) -> Dict[str, Any]:
    """Parse and validate a GEM AES `form_alert` string."""
    s = alert_str.strip()
    if not (s.startswith("[") and s.endswith("]")):
        raise ValueError("invalid form_alert syntax")
    parts = s[1:-1].split("][")
    if len(parts) != 3:
        raise ValueError("form_alert must have exactly 3 bracketed sections")
    icon = int(parts[0])
    if icon not in (0, 1, 2, 3):
        raise ValueError("invalid form_alert icon")
    lines = parts[1].split("|")
    buttons = parts[2].split("|")
    if not 1 <= len(lines) <= 5 or not 1 <= len(buttons) <= 3:
        raise ValueError("form_alert line/button count out of spec")
    return {
        "icon": icon,
        "icon_name": {0: "none", 1: "note", 2: "question", 3: "stop"}[icon],
        "lines": lines,
        "buttons": buttons,
    }


@dataclass
class GemWindow:
    handle: int
    title: str
    info: str
    kind: int
    x: int
    y: int
    w: int
    h: int
    opened: bool = False
    fulled: bool = False
    layer_id: str = ""


class GemAesDesk:
    """In-memory Digital Research PC GEM AES window & 16-byte message manager.

    Enforces the PC GEM 7-application-window limit (handles 1..7; handle 0 is
    the desktop root) and logs every 16-byte `WM_*` / `MN_SELECTED` message.
    """

    def __init__(self, screen_w: int = 640, screen_h: int = 400) -> None:
        self.screen_w = int(screen_w)
        self.screen_h = int(screen_h)
        self.windows: Dict[int, GemWindow] = {}
        self.top_handle: int = 0
        self.message_queue: List[bytes] = []

    def wind_create(
        self,
        kind: int,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        title: str = "",
        info: str = "",
        layer_id: str = "",
    ) -> int:
        for handle in range(1, MAX_AES_APP_WINDOWS + 1):
            if handle not in self.windows:
                self.windows[handle] = GemWindow(
                    handle=handle, title=title, info=info, kind=kind,
                    x=x, y=y, w=w, h=h, layer_id=layer_id,
                )
                return handle
        return -1  # Per aes.html Function 100: -1 if no windows available

    def wind_open(self, handle: int) -> bytes:
        win = self.windows[handle]
        win.opened = True
        self.top_handle = handle
        msg = encode_aes_message(WM_REDRAW, sender_apid=0, w3=handle, w4=win.x, w5=win.y, w6=win.w, w7=win.h)
        self.message_queue.append(msg)
        return msg

    def dispatch(self, raw_msg: bytes) -> Dict[str, Any]:
        dec = decode_aes_message(raw_msg)
        mtype = dec["msg_type"]
        handle = dec["data"][0]
        if mtype == WM_TOPPED and handle in self.windows:
            self.top_handle = handle
        elif mtype == WM_MOVED and handle in self.windows:
            win = self.windows[handle]
            win.x, win.y, win.w, win.h = dec["data"][1:5]
        elif mtype == WM_FULLED and handle in self.windows:
            win = self.windows[handle]
            win.fulled = not win.fulled
            if win.fulled:
                win.x, win.y, win.w, win.h = 0, 20, self.screen_w, self.screen_h - 20
        elif mtype == WM_CLOSED and handle in self.windows:
            self.windows[handle].opened = False
            open_handles = [h for h, w in self.windows.items() if w.opened]
            self.top_handle = open_handles[-1] if open_handles else 0
        self.message_queue.append(raw_msg)
        return dec

    def summary(self) -> Dict[str, Any]:
        return {
            "screen": [self.screen_w, self.screen_h],
            "max_app_windows": MAX_AES_APP_WINDOWS,
            "open_windows": [
                {
                    "handle": w.handle,
                    "title": w.title,
                    "info": w.info,
                    "layer_id": w.layer_id,
                    "kind_hex": f"0x{w.kind:04X}",
                    "grect": [w.x, w.y, w.w, w.h],
                }
                for w in self.windows.values()
                if w.opened
            ],
            "top_handle": self.top_handle,
            "messages_logged": len(self.message_queue),
        }


# ============================================================================
# 3. Exact PC GEM Binary `.RSC` Resource Compiler & Parser (RSHDR + OBJECT)
#    36-byte little-endian RSHDR (<18H) + 24-byte OBJECT (<hhhHHHIHHHH)
# ============================================================================

RSHDR_STRUCT = struct.Struct("<18H")
OBJECT_STRUCT = struct.Struct("<hhhHHHIHHHH")  # 24 bytes exact per aestruct.html
TEDINFO_STRUCT = struct.Struct("<IIIhhhhhhhh")  # 28 bytes exact per aestruct.html


def pack_ob_spec_box(
    *,
    char: int = 0,
    border_thickness: int = 1,
    border_color: int = 1,
    text_color: int = 1,
    opaque: bool = True,
    fill_pattern: int = 7,
    interior_color: int = 0,
) -> int:
    """Pack a 32-bit `ob_spec` bitfield for `G_BOX`/`G_IBOX`/`G_BOXCHAR`."""
    thickness_byte = border_thickness & 0xFF
    low16 = (
        (interior_color & 0x0F)
        | ((fill_pattern & 0x07) << 4)
        | ((1 if opaque else 0) << 7)
        | ((text_color & 0x0F) << 8)
        | ((border_color & 0x0F) << 12)
    )
    return ((char & 0xFF) << 24) | (thickness_byte << 16) | low16


@dataclass
class GemObject:
    ob_type: int
    x: int
    y: int
    w: int
    h: int
    flags: int = 0
    state: int = NORMAL
    text: Optional[str] = None
    ob_spec: int = 0
    parent: int = -1
    ob_next: int = -1
    ob_head: int = -1
    ob_tail: int = -1
    # Filled during RSC compilation
    _resolved_spec: int = field(default=0, repr=False)


class GemObjectTree:
    """Constructs a valid GEM AES `OBJECT` sibling/child tree ready for `.RSC`."""

    def __init__(self, name: str, w: int, h: int, *, fill_color: int = 0, border_color: int = 1) -> None:
        self.name = name
        self.objects: List[GemObject] = [
            GemObject(
                ob_type=G_BOX,
                x=0, y=0, w=w, h=h,
                flags=FLAG3D | FL3DBAK,
                state=OUTLINED,
                ob_spec=pack_ob_spec_box(border_thickness=-2, border_color=border_color, interior_color=fill_color),
            )
        ]

    def add(
        self,
        ob_type: int,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        parent: int = 0,
        flags: int = 0,
        state: int = NORMAL,
        text: Optional[str] = None,
        ob_spec: int = 0,
    ) -> int:
        idx = len(self.objects)
        obj = GemObject(
            ob_type=ob_type, x=x, y=y, w=w, h=h,
            flags=flags, state=state, text=text, ob_spec=ob_spec, parent=parent,
        )
        p = self.objects[parent]
        if p.ob_head == -1:
            p.ob_head = idx
            p.ob_tail = idx
            obj.ob_next = parent
        else:
            prev_tail = self.objects[p.ob_tail]
            prev_tail.ob_next = idx
            p.ob_tail = idx
            obj.ob_next = parent
        self.objects.append(obj)
        return idx


def compile_rsc(trees: Sequence[GemObjectTree], *, endian: str = "<") -> bytes:
    """Compile one or more `GemObjectTree`s into a binary `.RSC` resource file.

    Supports both:
      - `endian="<"` — Intel x86 PC GEM / FreeGEM / ViewMAX little-endian `.RSC`
      - `endian=">"` — Motorola 68000 Atari TOS big-endian `.RSC`
    """
    if endian not in ("<", ">"):
        raise ValueError("endian must be '<' (Intel x86 PC GEM) or '>' (Motorola 68000 Atari TOS)")
    if not trees:
        raise ValueError("at least one GemObjectTree is required")

    rshdr_s = struct.Struct(endian + "18H")
    obj_s = struct.Struct(endian + "hhhHHHIHHHH")
    ted_s = struct.Struct(endian + "IIIhhhhhhhh")

    # Section layout:
    #   [0..36)               : RSHDR (36 bytes)
    #   [rsh_string..]        : NUL-terminated CP437 string pool
    #   [rsh_tedinfo..]       : 28-byte TEDINFO structs (aligned even)
    #   [rsh_object..]        : 24-byte OBJECT structs
    #   [rsh_trindex..]       : 4-byte uint32 tree base offsets
    string_buf = bytearray()
    tedinfos: List[Tuple[int, int, int, int, int, int, int, int, int, int, int]] = []
    flat_objects: List[Tuple[int, GemObject]] = []  # (tree_idx, obj)
    tree_start_indices: List[int] = []

    str_base = rshdr_s.size

    def intern_string(s: str) -> int:
        offset = str_base + len(string_buf)
        string_buf.extend(s.encode("cp437", "replace") + b"\x00")
        return offset

    for t_idx, tree in enumerate(trees):
        tree_start_indices.append(len(flat_objects))
        for local_i, obj in enumerate(tree.objects):
            is_last = local_i == len(tree.objects) - 1
            if is_last:
                obj.flags |= LASTOB
            if obj.ob_type in (G_STRING, G_BUTTON, G_TITLE) and obj.text is not None:
                obj._resolved_spec = intern_string(obj.text)
            elif obj.ob_type in (G_TEXT, G_BOXTEXT, G_FTEXT, G_FBOXTEXT) and obj.text is not None:
                ptext_off = intern_string(obj.text)
                empty_off = intern_string("")
                ted_idx = len(tedinfos)
                # te_color: bg=0, pattern=7, opaque=1, text=1, border=1 -> 0x11F0
                tedinfos.append((ptext_off, empty_off, empty_off, 3, 0, 0, 0x11F0, 0, -1, len(obj.text) + 1, 1))
                obj._resolved_spec = ted_idx  # patched to absolute byte offset below
            else:
                obj._resolved_spec = obj.ob_spec
            flat_objects.append((t_idx, obj))

    if len(string_buf) % 2:
        string_buf.append(0)

    rsh_string = str_base
    rsh_tedinfo = rsh_string + len(string_buf)
    ted_bytes = bytearray()
    for t in tedinfos:
        ted_bytes.extend(ted_s.pack(*t))

    rsh_object = rsh_tedinfo + len(ted_bytes)
    obj_bytes = bytearray()
    for _t_idx, obj in flat_objects:
        spec = obj._resolved_spec
        if obj.ob_type in (G_TEXT, G_BOXTEXT, G_FTEXT, G_FBOXTEXT) and obj.text is not None:
            spec = rsh_tedinfo + spec * ted_s.size
        obj_bytes.extend(
            obj_s.pack(
                obj.ob_next, obj.ob_head, obj.ob_tail,
                obj.ob_type & 0xFFFF, obj.flags & 0xFFFF, obj.state & 0xFFFF,
                spec & 0xFFFFFFFF,
                obj.x & 0xFFFF, obj.y & 0xFFFF, obj.w & 0xFFFF, obj.h & 0xFFFF,
            )
        )

    rsh_trindex = rsh_object + len(obj_bytes)
    trindex_bytes = bytearray()
    for start_idx in tree_start_indices:
        trindex_bytes.extend(struct.pack(endian + "I", rsh_object + start_idx * obj_s.size))

    total_size = rsh_trindex + len(trindex_bytes)
    if total_size > 0xFFFF:
        raise ValueError("RSC exceeds 16-bit GEM resource size limit (64 KiB)")

    header = rshdr_s.pack(
        0,                   # rsh_vrsn (0 = standard GEM RSC)
        rsh_object,          # rsh_object
        rsh_tedinfo,         # rsh_tedinfo
        rsh_object,          # rsh_iconblk (unused)
        rsh_object,          # rsh_bitblk (unused)
        rsh_string,          # rsh_frstr
        rsh_string,          # rsh_string
        rsh_object,          # rsh_imdata
        rsh_object,          # rsh_frimg
        rsh_trindex,         # rsh_trindex
        len(flat_objects),   # rsh_nobs
        len(trees),          # rsh_ntree
        len(tedinfos),       # rsh_nted
        0,                   # rsh_nib
        0,                   # rsh_nbb
        0,                   # rsh_nstring
        0,                   # rsh_nimages
        total_size,          # rsh_rssize
    )
    return header + bytes(string_buf) + bytes(ted_bytes) + bytes(obj_bytes) + bytes(trindex_bytes)


def parse_rsc(data: bytes) -> Dict[str, Any]:
    """Parse and verify a dual-endian PC GEM (`<`) or Atari TOS 68000 (`>`) `.RSC`."""
    if len(data) < RSHDR_STRUCT.size:
        raise ValueError("RSC file truncated (< 36 byte RSHDR)")

    le_hdr = struct.unpack_from("<18H", data, 0)
    be_hdr = struct.unpack_from(">18H", data, 0)
    if le_hdr[17] == len(data) and le_hdr[1] <= len(data) and le_hdr[9] <= len(data):
        endian, arch, hdr = "<", "Intel x86 (PC GEM / FreeGEM / ViewMAX)", le_hdr
    elif be_hdr[17] == len(data) and be_hdr[1] <= len(data) and be_hdr[9] <= len(data):
        endian, arch, hdr = ">", "Motorola 68000 (Atari TOS)", be_hdr
    else:
        raise ValueError(f"RSC size/endian mismatch: le={le_hdr[17]}, be={be_hdr[17]}, actual={len(data)}")

    obj_s = struct.Struct(endian + "hhhHHHIHHHH")
    ted_s = struct.Struct(endian + "IIIhhhhhhhh")
    (
        rsh_vrsn, rsh_object, rsh_tedinfo, _rsh_iconblk, _rsh_bitblk, _rsh_frstr,
        rsh_string, _rsh_imdata, _rsh_frimg, rsh_trindex, rsh_nobs, rsh_ntree,
        rsh_nted, _rsh_nib, _rsh_nbb, _rsh_nstring, _rsh_nimages, rsh_rssize,
    ) = hdr

    def read_cstr(offset: int) -> str:
        if not 0 <= offset < len(data):
            return ""
        end = data.find(b"\x00", offset)
        if end == -1:
            end = len(data)
        return data[offset:end].decode("cp437", "replace")

    trees_out: List[List[Dict[str, Any]]] = []
    for t in range(rsh_ntree):
        tree_off = struct.unpack_from(endian + "I", data, rsh_trindex + t * 4)[0]
        objs: List[Dict[str, Any]] = []
        pos = tree_off
        while pos + obj_s.size <= len(data):
            nxt, head, tail, otype, flags, state, spec, x, y, w, h = obj_s.unpack_from(data, pos)
            text_val: Optional[str] = None
            low_type = otype & 0xFF
            if low_type in (G_STRING, G_BUTTON, G_TITLE):
                text_val = read_cstr(spec)
            elif low_type in (G_TEXT, G_BOXTEXT, G_FTEXT, G_FBOXTEXT) and spec + ted_s.size <= len(data):
                ptext_off = struct.unpack_from(endian + "I", data, spec)[0]
                text_val = read_cstr(ptext_off)
            objs.append({
                "index": len(objs),
                "ob_next": nxt, "ob_head": head, "ob_tail": tail,
                "ob_type": low_type, "ob_type_name": OB_TYPE_NAMES.get(low_type, str(low_type)),
                "ob_flags": flags, "ob_state": state, "ob_spec": spec,
                "grect": [x, y, w, h], "text": text_val,
            })
            pos += obj_s.size
            if flags & LASTOB:
                break
        trees_out.append(objs)

    return {
        "format": "GEM_RSC",
        "endian": endian,
        "arch": arch,
        "rsh_vrsn": rsh_vrsn,
        "rsh_nobs": rsh_nobs,
        "rsh_ntree": rsh_ntree,
        "rsh_nted": rsh_nted,
        "rsh_rssize": rsh_rssize,
        "trees": trees_out,
    }


# ============================================================================
# 4. Exact GEM `.IMG` / `XIMG` Big-Endian RLE Raster Bitmap Codec (ff_img.html)
# ============================================================================

IMG_HEADER_STRUCT = struct.Struct(">8H")  # Big-endian 8 words = 16 bytes


def _encode_img_scanline_plane(row_bytes: bytes) -> bytes:
    """Encode one plane of one scanline using ff_img.html RLE & literal records."""
    out = bytearray()
    n = len(row_bytes)
    i = 0
    while i < n:
        b = row_bytes[i]
        if b in (0x00, 0xFF):
            run = 1
            while i + run < n and row_bytes[i + run] == b and run < 127:
                run += 1
            if run >= 2 or b == 0x00:
                out.append((0x80 | run) if b == 0xFF else run)
                i += run
                continue
        # Literal bit-string run: 0x80, count (1..255), bytes...
        start = i
        i += 1
        while i < n and (i - start) < 255:
            if i + 2 < n and row_bytes[i] in (0x00, 0xFF) and row_bytes[i] == row_bytes[i + 1] == row_bytes[i + 2]:
                break
            i += 1
        chunk = row_bytes[start:i]
        out.append(0x80)
        out.append(len(chunk))
        out.extend(chunk)
    return bytes(out)


def encode_gem_img(
    pixels: Sequence[Sequence[int]],
    *,
    planes: int = 4,
    include_ximg_palette: bool = True,
    use_gem5_palette: bool = False,
) -> bytes:
    """Encode a 2D array of GEM palette indices (0..15 or 0..1) into a `.IMG` file.

    Strictly follows `seasip.info/Gem/ff_img.html`:
      - Big-endian 16-bit word header (`version=1`, `planes`, `pattern_size=2`,
        `pixel_width=85`, `pixel_height=85`, `image_width`, `image_height`)
      - Optional `XIMG` palette extension (`b"XIMG"`, RGB mode `0`, 16x3 VDI 0..1000 words)
      - Multi-plane rows stored per scanline in `planes` order, with vertical
        repeat records (`0x00, 0x00, 0xFF, count`) for identical consecutive lines.
    """
    if planes not in (1, 4):
        raise ValueError("GEM .IMG supports 1-plane mono or 4-plane 16-color")
    height = len(pixels)
    width = len(pixels[0]) if height else 0
    if width <= 0 or height <= 0:
        raise ValueError("image dimensions must be positive")
    row_byte_width = (width + 7) // 8

    ximg_ext = bytearray()
    if include_ximg_palette and planes == 4:
        ximg_ext.extend(b"XIMG")
        ximg_ext.extend(struct.pack(">H", 0))  # RGB palette type
        for idx in range(16):
            if use_gem5_palette and idx in GEM5_PALETTE_OVERRIDES:
                rgb = GEM5_PALETTE_OVERRIDES[idx][1]
            else:
                rgb = GEM_STANDARD_PALETTE[idx][1]
            vr, vg, vb = rgb_to_vdi_1000(rgb)
            ximg_ext.extend(struct.pack(">3H", vr, vg, vb))

    header_words = 8 + (len(ximg_ext) // 2)
    header = IMG_HEADER_STRUCT.pack(1, header_words, planes, 2, 85, 85, width, height)

    # Convert each scanline into `planes` packed bitplane byte rows
    encoded_scanlines: List[bytes] = []
    for y in range(height):
        row = pixels[y]
        line_buf = bytearray()
        for plane in range(planes):
            plane_bytes = bytearray(row_byte_width)
            bit_mask = 1 << plane
            for x in range(width):
                if row[x] & bit_mask:
                    plane_bytes[x >> 3] |= 0x80 >> (x & 7)
            line_buf.extend(_encode_img_scanline_plane(bytes(plane_bytes)))
        encoded_scanlines.append(bytes(line_buf))

    body = bytearray()
    y = 0
    while y < height:
        cur = encoded_scanlines[y]
        rep = 1
        while y + rep < height and encoded_scanlines[y + rep] == cur and rep < 255:
            rep += 1
        if rep > 1:
            body.extend(bytes([0x00, 0x00, 0xFF, rep]))
        body.extend(cur)
        y += rep

    return header + bytes(ximg_ext) + bytes(body)


def parse_gem_img(data: bytes) -> Dict[str, Any]:
    """Decode and validate a big-endian GEM `.IMG` / `XIMG` bitmap per `ff_img.html`."""
    if len(data) < 16:
        raise ValueError("GEM .IMG file truncated (< 16 bytes)")
    version, header_words, planes, pat_len, pix_w, pix_h, img_w, img_h = IMG_HEADER_STRUCT.unpack_from(data, 0)
    if version != 1 or header_words < 8 or planes not in (1, 4, 8):
        raise ValueError(f"invalid GEM .IMG header: version={version} words={header_words} planes={planes}")
    header_bytes = header_words * 2
    if len(data) < header_bytes:
        raise ValueError("GEM .IMG header extends past EOF")

    has_ximg = header_bytes >= 22 and data[16:20] == b"XIMG"
    row_byte_width = (img_w + 7) // 8
    pos = header_bytes
    decoded_rows: List[List[int]] = []

    while len(decoded_rows) < img_h and pos < len(data):
        vrep = 1
        if pos + 4 <= len(data) and data[pos] == 0x00 and data[pos + 1] == 0x00 and data[pos + 2] == 0xFF:
            vrep = data[pos + 3]
            pos += 4

        plane_rows: List[bytes] = []
        for _p in range(planes):
            buf = bytearray()
            while len(buf) < row_byte_width:
                if pos >= len(data):
                    raise ValueError("unexpected EOF inside GEM .IMG scanline")
                code = data[pos]
                pos += 1
                if code == 0x80:
                    cnt = data[pos]
                    pos += 1
                    buf.extend(data[pos:pos + cnt])
                    pos += cnt
                elif code == 0x00:
                    cnt = data[pos]
                    pos += 1
                    pat = data[pos:pos + pat_len]
                    pos += pat_len
                    buf.extend(pat * cnt)
                else:
                    fill_byte = 0xFF if (code & 0x80) else 0x00
                    cnt = code & 0x7F
                    buf.extend(bytes([fill_byte]) * cnt)
            plane_rows.append(bytes(buf[:row_byte_width]))

        pixel_row = [0] * img_w
        for plane_i, prow in enumerate(plane_rows):
            bit_val = 1 << plane_i
            for x in range(img_w):
                if prow[x >> 3] & (0x80 >> (x & 7)):
                    pixel_row[x] |= bit_val

        for _ in range(vrep):
            if len(decoded_rows) < img_h:
                decoded_rows.append(list(pixel_row))

    if len(decoded_rows) != img_h:
        raise ValueError(f"GEM .IMG decoded {len(decoded_rows)} rows, expected {img_h}")

    return {
        "format": "GEM_XIMG" if has_ximg else "GEM_IMG",
        "version": version,
        "header_words": header_words,
        "planes": planes,
        "pattern_size": pat_len,
        "pixel_size": [pix_w, pix_h],
        "width": img_w,
        "height": img_h,
        "has_ximg_palette": has_ximg,
        "bytes_consumed": pos,
        "pixels": decoded_rows,
    }


def scene_to_gem_img(
    scene: Any,
    *,
    width: int = 320,
    height: int = 200,
    use_gem5_palette: bool = False,
) -> bytes:
    """Rasterize a Zoe GEM Spatial IR `Scene` into a 4-plane 16-color GEM `.IMG` bitmap."""
    cw = max(1.0, float(scene.canvas["width"]))
    ch = max(1.0, float(scene.canvas["height"]))
    sx = (width - 1) / cw
    sy = (height - 1) / ch

    # Default background = index 0 (White)
    grid: List[List[int]] = [[0] * width for _ in range(height)]

    def draw_hline(x0: int, x1: int, y: int, col: int) -> None:
        if not 0 <= y < height:
            return
        a, b = max(0, min(x0, x1)), min(width - 1, max(x0, x1))
        row = grid[y]
        for x in range(a, b + 1):
            row[x] = col

    def draw_line(x0: int, y0: int, x1: int, y1: int, col: int) -> None:
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx_step = 1 if x0 < x1 else -1
        sy_step = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            if 0 <= x0 < width and 0 <= y0 < height:
                grid[y0][x0] = col
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx_step
            if e2 <= dx:
                err += dx
                y0 += sy_step

    for obj in scene.objects:
        otype = obj["type"]
        fill = obj.get("fill", "none")
        stroke = obj.get("stroke", "black")
        fcol = nearest_gem_color_index(fill) if fill != "none" else -1
        scol = nearest_gem_color_index(stroke) if stroke != "none" else -1

        if otype == "rectangle":
            l, t, r, b = obj["bounds"]
            x0, y0 = int(round(l * sx)), int(round(t * sy))
            x1, y1 = int(round(r * sx)), int(round(b * sy))
            if fcol >= 0:
                for yy in range(max(0, y0), min(height, y1 + 1)):
                    draw_hline(x0, x1, yy, fcol)
            if scol >= 0:
                draw_hline(x0, x1, y0, scol)
                draw_hline(x0, x1, y1, scol)
                draw_line(x0, y0, x0, y1, scol)
                draw_line(x1, y0, x1, y1, scol)
        elif otype in ("line", "polyline", "polygon"):
            pts = [(int(round(px * sx)), int(round(py * sy))) for px, py in obj["points"]]
            if scol >= 0:
                for i in range(len(pts) - 1):
                    draw_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], scol)
                if otype == "polygon" and len(pts) > 2:
                    draw_line(pts[-1][0], pts[-1][1], pts[0][0], pts[0][1], scol)
        elif otype == "ellipse":
            cx, cy = int(round(obj["center"][0] * sx)), int(round(obj["center"][1] * sy))
            rx, ry = max(1, int(round(obj["radii"][0] * sx))), max(1, int(round(obj["radii"][1] * sy)))
            if fcol >= 0:
                for dy in range(-ry, ry + 1):
                    span = int(round(rx * (max(0.0, 1.0 - (dy / ry) ** 2) ** 0.5)))
                    draw_hline(cx - span, cx + span, cy + dy, fcol)
            if scol >= 0:
                for deg in range(0, 360, 4):
                    import math
                    px = cx + int(round(rx * math.cos(math.radians(deg))))
                    py = cy + int(round(ry * math.sin(math.radians(deg))))
                    if 0 <= px < width and 0 <= py < height:
                        grid[py][px] = scol
        elif otype == "text" and scol >= 0:
            tx, ty = int(round(obj["position"][0] * sx)), int(round(obj["position"][1] * sy))
            span = min(width - 1 - max(0, tx), max(6, len(str(obj.get("text", ""))) * 3))
            draw_hline(tx, tx + span, ty, scol)

    return encode_gem_img(grid, planes=4, include_ximg_palette=True, use_gem5_palette=use_gem5_palette)


# ============================================================================
# 5. `.GEM` Metafile Spec Verifier (seasip.info/Gem/ff_gem.html)
# ============================================================================

def verify_seasip_gem_metafile(data: bytes) -> Dict[str, Any]:
    """Validate a binary `.GEM` VDI metafile directly against `ff_gem.html`."""
    from .vdi import parse_metafile

    parsed = parse_metafile(data)
    hdr = parsed["header"]
    records = parsed["records"]
    magic = struct.unpack_from("<h", data, 0)[0]
    eof_word = struct.unpack_from("<h", data, len(data) - 2)[0]
    opcodes = sorted({r["command"] for r in records if r["command"] != -1})
    return {
        "valid": magic == -1 and eof_word == -1 and hdr["header_words"] >= 24 and hdr["coordinate_system"] in (0, 2),
        "magic_hex": f"0x{magic & 0xFFFF:04X}",
        "eof_hex": f"0x{eof_word & 0xFFFF:04X}",
        "header_words": hdr["header_words"],
        "version": hdr["version"],
        "coordinate_system": "RC" if hdr["coordinate_system"] == 2 else "NDC",
        "record_count": len(records),
        "vdi_opcodes": opcodes,
        "bytes": len(data),
    }


# ============================================================================
# 6. Digital Research GSX-80 / GSX-86 (1982) NDC 0..32767 Vector Driver Codec
#    & ToastyTech GUI Gallery Historical GEM Lineage (toastytech.com/guis/)
# ============================================================================

GSX_MAGIC = b"GSX86V1\x00"
GSX_OP_OPNWK = 1      # Open Workstation (load DD*.SYS / DD*.PRL device driver)
GSX_OP_CLSWK = 2      # Close Workstation
GSX_OP_CLRWK = 3      # Clear Workstation
GSX_OP_PLINE = 6      # Polyline (NDC 0..32767, bottom-left origin)
GSX_OP_GTEXT = 8      # Graphic Text (NDC 0..32767, bottom-left origin)
GSX_OP_FILLAREA = 9   # Filled Area polygon
GSX_OP_GDP = 11       # Generalized Drawing Primitive (subop 1 = Filled Bar)
GSX_OP_SL_COLOR = 17  # Set Polyline Color Index
GSX_OP_ST_COLOR = 22  # Set Graphic Text Color Index
GSX_OP_SF_INTERIOR = 23
GSX_OP_SF_COLOR = 25

GSX_OPCODE_NAMES: Dict[int, str] = {
    GSX_OP_OPNWK: "v_opnwk",
    GSX_OP_CLSWK: "v_clswk",
    GSX_OP_CLRWK: "v_clrwk",
    GSX_OP_PLINE: "v_pline",
    GSX_OP_GTEXT: "v_gtext",
    GSX_OP_FILLAREA: "v_fillarea",
    GSX_OP_GDP: "v_gdp",
    GSX_OP_SL_COLOR: "vsl_color",
    GSX_OP_ST_COLOR: "vst_color",
    GSX_OP_SF_INTERIOR: "vsf_interior",
    GSX_OP_SF_COLOR: "vsf_color",
}

TOASTYTECH_GEM_ERAS: Dict[str, Dict[str, Any]] = {
    "gsx": {
        "id": "gsx",
        "year": 1982,
        "title": "Digital Research GSX (1982)",
        "resolution": "NDC 0..32767 (device-independent)",
        "endian": "<",
        "arch": "CP/M-80 / CP/M-86 / MS-DOS GIOS",
        "desk_menu_position": "left",
        "hover_menus": False,
        "desktop_icons": False,
        "window_mode": "vector_workstation",
        "source_url": "http://toastytech.com/guis/gsx.html",
        "highlights": "Installable device drivers (DD*.SYS), bottom-left NDC 0..32767 vector space, DR-Draw & DR-Graph predecessor to GEM VDI.",
    },
    "gem11": {
        "id": "gem11",
        "year": 1985,
        "title": "GEM 1.1 (1985 · Pre-Lawsuit)",
        "resolution": "EGA 640x350 16-color",
        "endian": "<",
        "arch": "Intel x86 PC-DOS",
        "desk_menu_position": "left",
        "hover_menus": True,
        "desktop_icons": True,
        "window_mode": "overlapping",
        "source_url": "http://toastytech.com/guis/gem11.html",
        "highlights": "Overlapping resizable windows, Drive A:/C: & Trash Can on desktop, hover-to-open menus, Clock & Calculator DAs.",
    },
    "gem20": {
        "id": "gem20",
        "year": 1986,
        "title": "GEM 2.0 / 3.11 (1986-88 · Post-Lawsuit)",
        "resolution": "VGA 640x480 16-color",
        "endian": "<",
        "arch": "Intel x86 MS-DOS",
        "desk_menu_position": "right",
        "hover_menus": False,
        "desktop_icons": False,
        "window_mode": "tiled_two_pane",
        "source_url": "http://toastytech.com/guis/gem20.html",
        "highlights": "Apple settlement layout: 2 permanently open fixed-size tiled windows, zero desktop icons, Desk menu moved to far right, Print Spooler DA.",
    },
    "tos10": {
        "id": "tos10",
        "year": 1985,
        "title": "Atari TOS 1.0 (1985 · 68k ROM)",
        "resolution": "ST 320x200 / 640x400 ROM",
        "endian": ">",
        "arch": "Motorola 68000 (Atari ST/TT)",
        "desk_menu_position": "left",
        "hover_menus": True,
        "desktop_icons": True,
        "window_mode": "overlapping",
        "source_url": "http://toastytech.com/guis/tos.html",
        "highlights": "The Little Green Desktop in ROM: Filing-Cabinet File Drawers A:/C:, Trash Can, overlapping windows exempt from Apple PC settlement, big-endian 68k .RSC.",
    },
    "opengem": {
        "id": "opengem",
        "year": 1992,
        "title": "OpenGEM / ViewMAX 3D (1992+)",
        "resolution": "VGA/SVGA 3D AES 3.0",
        "endian": "<",
        "arch": "Intel x86 FreeGEM / ViewMAX",
        "desk_menu_position": "left",
        "hover_menus": False,
        "desktop_icons": True,
        "window_mode": "overlapping_3d",
        "source_url": "http://toastytech.com/guis/gem311.html",
        "highlights": "Restores desktop icons + overlapping windows with ViewMAX/FreeGEM sculpted 3D bevels (FLAG3D/FL3DBAK) and GEM/5 #00756B teal palette.",
    },
}


def scene_to_gsx_calls(scene: Any, *, driver_id: int = 1) -> List[Dict[str, Any]]:
    """Compile a verified Spatial IR `Scene` into authentic 1982 GSX-86 NDC calls.

    Per Digital Research's 1982 GSX Programmer's Guide (`GSX-80`/`GSX-86`):
      - Normalized Device Coordinates (NDC) run `0..32767` along both axes.
      - Origin `(0, 0)` is at the **bottom-left** corner (unlike GEM RC top-left).
    """
    cw = max(1.0, float(scene.canvas["width"]))
    ch = max(1.0, float(scene.canvas["height"]))

    def to_ndc(x: float, y: float) -> Tuple[int, int]:
        nx = max(0, min(32767, int(round((float(x) / cw) * 32767.0))))
        ny = max(0, min(32767, int(round((1.0 - float(y) / ch) * 32767.0))))
        return nx, ny

    calls: List[Dict[str, Any]] = [
        {"opcode": GSX_OP_OPNWK, "subopcode": 0, "ptsin": [], "intin": [driver_id, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0]},
        {"opcode": GSX_OP_CLRWK, "subopcode": 0, "ptsin": [], "intin": []},
    ]
    for obj in scene.objects:
        otype = obj["type"]
        fill = obj.get("fill", "none")
        stroke = obj.get("stroke", "black")
        if otype == "rectangle":
            l, t, r, b = obj["bounds"]
            p0 = to_ndc(l, b)  # bottom-left in GSX NDC
            p1 = to_ndc(r, t)  # top-right in GSX NDC
            if fill != "none":
                calls.append({"opcode": GSX_OP_SF_INTERIOR, "subopcode": 0, "ptsin": [], "intin": [1]})
                calls.append({"opcode": GSX_OP_SF_COLOR, "subopcode": 0, "ptsin": [], "intin": [nearest_gem_color_index(fill)]})
                calls.append({"opcode": GSX_OP_GDP, "subopcode": 1, "ptsin": [p0[0], p0[1], p1[0], p1[1]], "intin": []})
            if stroke != "none":
                calls.append({"opcode": GSX_OP_SL_COLOR, "subopcode": 0, "ptsin": [], "intin": [nearest_gem_color_index(stroke)]})
                calls.append({
                    "opcode": GSX_OP_PLINE, "subopcode": 0,
                    "ptsin": [p0[0], p0[1], p1[0], p0[1], p1[0], p1[1], p0[0], p1[1], p0[0], p0[1]],
                    "intin": [],
                })
        elif otype in ("line", "polyline", "polygon"):
            pts: List[int] = []
            for px, py in obj["points"]:
                nx, ny = to_ndc(px, py)
                pts.extend([nx, ny])
            if otype == "polygon" and len(pts) >= 4:
                pts.extend([pts[0], pts[1]])
            if stroke != "none":
                calls.append({"opcode": GSX_OP_SL_COLOR, "subopcode": 0, "ptsin": [], "intin": [nearest_gem_color_index(stroke)]})
                calls.append({"opcode": GSX_OP_PLINE, "subopcode": 0, "ptsin": pts, "intin": []})
        elif otype == "text":
            tx, ty = to_ndc(obj["position"][0], obj["position"][1])
            text = str(obj.get("text", ""))[:80]
            calls.append({"opcode": GSX_OP_ST_COLOR, "subopcode": 0, "ptsin": [], "intin": [nearest_gem_color_index(stroke)]})
            calls.append({"opcode": GSX_OP_GTEXT, "subopcode": 0, "ptsin": [tx, ty], "intin": [ord(ch_) & 0x7F for ch_ in text]})

    calls.append({"opcode": GSX_OP_CLSWK, "subopcode": 0, "ptsin": [], "intin": []})
    return calls


def encode_gsx_stream(scene: Any, *, driver_id: int = 1) -> bytes:
    """Serialize a verified `Scene` into a binary GSX-86 NDC `0..32767` call stream."""
    calls = scene_to_gsx_calls(scene, driver_id=driver_id)
    out = bytearray(GSX_MAGIC)
    out.extend(struct.pack("<HH", driver_id, len(calls)))
    for call in calls:
        ptsin = call["ptsin"]
        intin = call["intin"]
        out.extend(struct.pack("<4H", call["opcode"], len(ptsin) // 2, len(intin), call["subopcode"]))
        if ptsin:
            out.extend(struct.pack(f"<{len(ptsin)}h", *ptsin))
        if intin:
            out.extend(struct.pack(f"<{len(intin)}h", *intin))
    return bytes(out)


def parse_gsx_stream(data: bytes) -> Dict[str, Any]:
    """Decode and validate a binary GSX-86 NDC `0..32767` call stream."""
    if len(data) < 12 or data[:8] != GSX_MAGIC:
        raise ValueError("invalid GSX-86 stream magic")
    driver_id, expected_count = struct.unpack_from("<HH", data, 8)
    pos = 12
    calls: List[Dict[str, Any]] = []
    opcodes_seen: set[int] = set()
    max_ndc = 0
    while pos + 8 <= len(data) and len(calls) < expected_count:
        opcode, n_pts, n_int, subop = struct.unpack_from("<4H", data, pos)
        pos += 8
        ptsin = list(struct.unpack_from(f"<{n_pts * 2}h", data, pos)) if n_pts else []
        pos += n_pts * 4
        intin = list(struct.unpack_from(f"<{n_int}h", data, pos)) if n_int else []
        pos += n_int * 2
        opcodes_seen.add(opcode)
        if ptsin:
            max_ndc = max(max_ndc, max(ptsin))
        calls.append({"opcode": opcode, "name": GSX_OPCODE_NAMES.get(opcode, f"OP_{opcode}"), "subopcode": subop, "ptsin": ptsin, "intin": intin})
    if len(calls) != expected_count or pos != len(data):
        raise ValueError(f"GSX stream truncated or malformed: decoded={len(calls)} expected={expected_count}")
    return {
        "format": "DR_GSX86_NDC",
        "driver_id": driver_id,
        "coordinate_space": "NDC 0..32767 (bottom-left origin)",
        "call_count": len(calls),
        "opcodes": sorted(opcodes_seen),
        "opcode_names": [GSX_OPCODE_NAMES.get(o, str(o)) for o in sorted(opcodes_seen)],
        "max_ndc_coord": max_ndc,
        "bytes": len(data),
        "valid": calls[0]["opcode"] == GSX_OP_OPNWK and calls[-1]["opcode"] == GSX_OP_CLSWK and max_ndc <= 32767,
    }
