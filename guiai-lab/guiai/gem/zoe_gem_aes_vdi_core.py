"""Digital Research GEM AES/VDI Core (Clean-Room Specification per Balma & Fitler 1986).

Implements Features #7–#10 for Zoe's Collaborative GEM Workbench:
  - Feature #7: `GemAesApplication` — `appl_init`/`appl_exit`/`appl_find`/`appl_write`/
    `appl_read` (supporting `msg[2] > 0` extra bytes), `evnt_multi` (`MU_KEYBD`, `MU_BUTTON`,
    `MU_M1`, `MU_M2`, `MU_MESAG`, `MU_TIMER`), and 16-byte `<8h` FIFO message pipe.
  - Feature #8: `GemAesWindowTreeManager` — `wind_create`..`wind_delete` enforcing
    `MAX_AES_APP_WINDOWS = 7` (`1..7`, `0 = DESK`), z-order tracking, `wind_calc`
    exact round-trip chrome geometry, `wind_update` balanced mutexes, and
    `walk_redraw_rectangles` (`WF_FIRSTXYWH`/`WF_NEXTXYWH` occlusion splitting).
  - Feature #9: `GemObject`, `GemObjectTreeOps`, Forms (`form_center`, `form_dial`,
    `form_do`, `form_alert`), Menus (`menu_bar`, `menu_icheck`, `menu_ienable`,
    `menu_tnormal`), and `GemResourceManager` (`rsrc_load`/`rsrc_free`/`rsrc_gaddr(0..16)`/
    `rsrc_obfix` supporting both little-endian PC GEM and big-endian Atari ST `.RSC`).
  - Feature #10: `GemVdiStateMachine` — `v_opnvwk`/`v_clsvwk`, `vq_extnd(0|1)`,
    NDC (`0..32767`, bottom-left) <-> RC (`0..max_x, 0..max_y`, top-left), `vs_clip`,
    `vswr_mode(1..4)`, style setters (`vsl_*`, `vsm_*`, `vsf_*`, `vst_*`), primitives
    & GDPs (`v_pline`, `v_pmarker`, `v_gtext`, `v_bar`, `v_fillarea`, `v_rbox`, `v_rfbox`,
    `vr_recfl`, `v_arc`, `v_pieslice`, `v_circle`, `v_ellarc`, `v_ellipse`), Ch. 6
    metafile escapes (`vm_filename`, `vm_pagesize`, `vm_coords`, `v_meta_extents`),
    `.GEM` metafile emission, and `Scene` spatial IR export.

Constitutional Invariants (`PROJECT.md § 1` & `docs/CONSTITUTION.md`):
  - Original clean-room Python code only; zero verbatim code from external books.
  - Offline-only, `advisory_only=True`, `read_only=True`, `external_actions=0`,
    `tokens_used=0`, `cloud_cost_usd=0.0`, `loopback_only=True`, `sentience_claimed=False`.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
import math
from pathlib import Path
import struct
from typing import Any, cast

from . import geometry as _gem_geometry
from . import model as _gem_model
from . import runner as _gem_runner
from . import seasip_gem
from . import vdi as _gem_vdi
from .zoe_sisters import SAFETY_INVARIANTS

# ============================================================================
# Section A — Constitutional & Epistemic Metadata (PROJECT.md § 1)
# ============================================================================

ATTRIBUTION_TEXT = "Nicholas Michael Kloster, March 6, 2026"
HISTORICAL_CREDIT = (
    "Honoring Gary Kildall and Digital Research GEM contributors "
    "(Balma & Fitler, 1986; seasip.info/Gem/)"
)
EPISTEMIC_LANES = frozenset(
    {"measurement", "evidence", "belief_update", "advisory_proposal"}
)


def constitutional_metadata(
    epistemic_lane: str = "measurement",
    *,
    read_only: bool = True,
    visual_evidence_only: bool = True,
) -> dict[str, Any]:
    """Return canonical constitutional metadata for M3 GEM AES/VDI records.

    Rejects auto-executing `"action"` or unknown epistemic lanes per `PROJECT.md § 1`.
    """
    if not isinstance(epistemic_lane, str) or epistemic_lane not in EPISTEMIC_LANES:
        raise ValueError(
            f"epistemic_lane must be one of {sorted(EPISTEMIC_LANES)}, got {epistemic_lane!r}"
        )
    return {
        "epistemic_lane": epistemic_lane,
        "measurement_lane_only": epistemic_lane == "measurement",
        "visual_evidence_only": bool(visual_evidence_only),
        "advisory_only": True,
        "read_only": bool(read_only),
        "external_actions": 0,
        "tokens_used": int(SAFETY_INVARIANTS["tokens_used"]),
        "cloud_cost_usd": float(SAFETY_INVARIANTS["cloud_cost_usd"]),
        "loopback_only": True,
        "sentience_claimed": bool(SAFETY_INVARIANTS["sentience_claimed"]),
        "l5_agi_qualified": False,
        "zoe_clone_claimed": bool(SAFETY_INVARIANTS["zoe_clone_claimed"]),
        "clinical_action_authorized": bool(SAFETY_INVARIANTS["clinical_action_authorized"]),
        "flight_control_authorized": bool(SAFETY_INVARIANTS["flight_control_authorized"]),
        "cure_claim": bool(SAFETY_INVARIANTS["cure_claim"]),
        "wet_lab_validation_required": bool(SAFETY_INVARIANTS["wet_lab_validation_required"]),
        "attribution": ATTRIBUTION_TEXT,
        "historical_credit": HISTORICAL_CREDIT,
    }


# ============================================================================
# Section B — Re-exports, Constants, Validation Helpers & GRECT
# ============================================================================

MAX_AES_APP_WINDOWS: int = int(seasip_gem.MAX_AES_APP_WINDOWS)

# Object types
G_BOX: int = int(seasip_gem.G_BOX)
G_TEXT: int = int(seasip_gem.G_TEXT)
G_BOXTEXT: int = int(seasip_gem.G_BOXTEXT)
G_IMAGE: int = int(seasip_gem.G_IMAGE)
G_USERDEF: int = int(seasip_gem.G_USERDEF)
G_IBOX: int = int(seasip_gem.G_IBOX)
G_BUTTON: int = int(seasip_gem.G_BUTTON)
G_BOXCHAR: int = int(seasip_gem.G_BOXCHAR)
G_STRING: int = int(seasip_gem.G_STRING)
G_FTEXT: int = int(seasip_gem.G_FTEXT)
G_FBOXTEXT: int = int(seasip_gem.G_FBOXTEXT)
G_ICON: int = int(seasip_gem.G_ICON)
G_TITLE: int = int(seasip_gem.G_TITLE)
G_CLRICN: int = int(seasip_gem.G_CLRICN)
G_DTMFDB: int = int(seasip_gem.G_DTMFDB)
OB_TYPE_NAMES: dict[int, str] = dict(seasip_gem.OB_TYPE_NAMES)

# Object flags
NONE_FLAG: int = 0x0000
SELECTABLE: int = int(seasip_gem.SELECTABLE)
DEFAULT: int = int(seasip_gem.DEFAULT)
EXIT: int = int(seasip_gem.EXIT)
EDITABLE: int = int(seasip_gem.EDITABLE)
RBUTTON: int = int(seasip_gem.RBUTTON)
LASTOB: int = int(seasip_gem.LASTOB)
TOUCHEXIT: int = int(seasip_gem.TOUCHEXIT)
HIDETREE: int = int(seasip_gem.HIDETREE)
INDIRECT: int = int(seasip_gem.INDIRECT)
ESCCANCEL: int = int(seasip_gem.ESCCANCEL)
SCROLLER: int = int(seasip_gem.SCROLLER)
FLAG3D: int = int(seasip_gem.FLAG3D)
USECOLORCAT: int = int(seasip_gem.USECOLORCAT)
FL3DBAK: int = int(seasip_gem.FL3DBAK)

# Object states
NORMAL: int = int(seasip_gem.NORMAL)
SELECTED: int = int(seasip_gem.SELECTED)
CROSSED: int = int(seasip_gem.CROSSED)
CHECKED: int = int(seasip_gem.CHECKED)
DISABLED: int = int(seasip_gem.DISABLED)
OUTLINED: int = int(seasip_gem.OUTLINED)
SHADOWED: int = int(seasip_gem.SHADOWED)
WHITEBAK: int = int(seasip_gem.WHITEBAK)

# Window kinds
NAME: int = int(seasip_gem.NAME)
CLOSER: int = int(seasip_gem.CLOSER)
FULLER: int = int(seasip_gem.FULLER)
MOVER: int = int(seasip_gem.MOVER)
INFO: int = int(seasip_gem.INFO)
SIZER: int = int(seasip_gem.SIZER)
UPARROW: int = int(seasip_gem.UPARROW)
DNARROW: int = int(seasip_gem.DNARROW)
VSLIDE: int = int(seasip_gem.VSLIDE)
LFARROW: int = int(seasip_gem.LFARROW)
RTARROW: int = int(seasip_gem.RTARROW)
HSLIDE: int = int(seasip_gem.HSLIDE)
STANDARD_WINDOW_KIND: int = int(seasip_gem.STANDARD_WINDOW_KIND)

# AES messages
MN_SELECTED: int = int(seasip_gem.MN_SELECTED)
WM_REDRAW: int = int(seasip_gem.WM_REDRAW)
WM_TOPPED: int = int(seasip_gem.WM_TOPPED)
WM_CLOSED: int = int(seasip_gem.WM_CLOSED)
WM_FULLED: int = int(seasip_gem.WM_FULLED)
WM_ARROWED: int = int(seasip_gem.WM_ARROWED)
WM_HSLID: int = int(seasip_gem.WM_HSLID)
WM_VSLID: int = int(seasip_gem.WM_VSLID)
WM_SIZED: int = int(seasip_gem.WM_SIZED)
WM_MOVED: int = int(seasip_gem.WM_MOVED)
WM_NEWTOP: int = int(seasip_gem.WM_NEWTOP)
WM_UNTOPPED: int = int(seasip_gem.WM_UNTOPPED)
AC_OPEN: int = int(seasip_gem.AC_OPEN)
AC_CLOSE: int = int(seasip_gem.AC_CLOSE)
AES_MSG_NAMES: dict[int, str] = dict(seasip_gem.AES_MSG_NAMES)
encode_aes_message = seasip_gem.encode_aes_message
decode_aes_message = seasip_gem.decode_aes_message

# Palettes
GEM_STANDARD_PALETTE = seasip_gem.GEM_STANDARD_PALETTE
GEM5_PALETTE_OVERRIDES = seasip_gem.GEM5_PALETTE_OVERRIDES
rgb_to_vdi_1000 = seasip_gem.rgb_to_vdi_1000
nearest_gem_color_index = seasip_gem.nearest_gem_color_index

# Event bitmasks
MU_KEYBD = 0x0001
MU_BUTTON = 0x0002
MU_M1 = 0x0004
MU_M2 = 0x0008
MU_MESAG = 0x0010
MU_TIMER = 0x0020
_ALL_MU_FLAGS = MU_KEYBD | MU_BUTTON | MU_M1 | MU_M2 | MU_MESAG | MU_TIMER

# Keyboard shift state flags
K_RSHIFT = 0x0001
K_LSHIFT = 0x0002
K_CTRL = 0x0004
K_ALT = 0x0008

# Window calculation modes
WC_BORDER = 0
WC_WORK = 1

# Window update lock codes
END_UPDATE = 0
BEG_UPDATE = 1
END_MCTRL = 2
BEG_MCTRL = 3

# Window get/set field codes
WF_KIND = 1
WF_NAME = 2
WF_INFO = 3
WF_WORKXYWH = 4
WF_WXYWH = 4
WF_CURRXYWH = 5
WF_CXYWH = 5
WF_PREVXYWH = 6
WF_PXYWH = 6
WF_FULLXYWH = 7
WF_FXYWH = 7
WF_HSLIDE = 8
WF_VSLIDE = 9
WF_TOP = 10
WF_FIRSTXYWH = 11
WF_NEXTXYWH = 12
WF_NEWDESK = 14
WF_HSLSIZE = 15
WF_VSLSIZE = 16
WF_SCREEN = 17

# Window arrow subcodes
WA_UPPAGE = 0
WA_DNPAGE = 1
WA_UPLINE = 2
WA_DNLINE = 3
WA_LFPAGE = 4
WA_RTPAGE = 5
WA_LFLINE = 6
WA_RTLINE = 7

# Object tree sentinel & edit constants
NIL = -1
ROOT = 0
MAX_TREE_DEPTH = 10
ED_START = 0
ED_INIT = 1
ED_CHAR = 2
ED_END = 3

# Form dial flags
FMD_START = 0
FMD_GROW = 1
FMD_SHRINK = 2
FMD_FINISH = 3

# Resource gaddr types (0..16)
R_TREE = 0
R_OBJECT = 1
R_TEDINFO = 2
R_ICONBLK = 3
R_BITBLK = 4
R_STRING = 5
R_IMAGEDATA = 6
R_OBSPEC = 7
R_TEPTEXT = 8
R_TEPTMPLT = 9
R_TEPVALID = 10
R_IBPMASK = 11
R_IBPDATA = 12
R_IBPTEXT = 13
R_BIPDATA = 14
R_FRSTR = 15
R_FRIMG = 16

# VDI constants
NDC_MODE = 0
RC_MODE = 2
CLIP_OFF = 0
CLIP_ON = 1
MD_REPLACE = 1
MD_TRANS = 2
MD_XOR = 3
MD_ERASE = 4
FIS_HOLLOW = 0
FIS_SOLID = 1
FIS_PATTERN = 2
FIS_HATCH = 3
FIS_USER = 4

# VDI opcodes & GDP subcodes
VDI_OP_ESCAPE = 5
VDI_OP_PLINE = 6
VDI_OP_PMARKER = 7
VDI_OP_GTEXT = 8
VDI_OP_FILLAREA = 9
VDI_OP_GDP = 11
VDI_OP_VST_HEIGHT = 12
VDI_OP_VST_ROTATION = 13
VDI_OP_VS_COLOR = 14
VDI_OP_VSL_TYPE = 15
VDI_OP_VSL_WIDTH = 16
VDI_OP_VSL_COLOR = 17
VDI_OP_VSM_TYPE = 18
VDI_OP_VSM_HEIGHT = 19
VDI_OP_VSM_COLOR = 20
VDI_OP_VST_FONT = 21
VDI_OP_VST_COLOR = 22
VDI_OP_VSF_INTERIOR = 23
VDI_OP_VSF_STYLE = 24
VDI_OP_VSF_COLOR = 25
VDI_OP_VSWR_MODE = 32
VDI_OP_VST_ALIGNMENT = 39
VDI_OP_VQ_EXTND = 102
VDI_OP_VSF_PERIMETER = 104
VDI_OP_VST_EFFECTS = 106
VDI_OP_VST_POINT = 107
VDI_OP_VSL_ENDS = 108
VDI_OP_VR_RECFL = 114
VDI_OP_VS_CLIP = 129

GDP_BAR = 1
GDP_ARC = 2
GDP_PIESLICE = 3
GDP_CIRCLE = 4
GDP_ELLIPSE = 5
GDP_ELLARC = 6
GDP_ELLPIE = 7
GDP_RBOX = 8
GDP_RFBOX = 9
GDP_JUSTIFIED = 10

ESC_META_EXTENTS = 98
ESC_WRITE_META = 99
ESC_VM_FILENAME = 100


def _require_nonbool_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    return int(value)


def _require_int16(value: Any, name: str) -> int:
    val = _require_nonbool_int(value, name)
    if not (-32768 <= val <= 32767):
        raise ValueError(f"{name} outside signed 16-bit range [-32768, 32767]: {val}")
    return val


def _require_flag_01(value: int | bool, name: str) -> int:
    if isinstance(value, bool):
        return 1 if value else 0
    val = _require_nonbool_int(value, name)
    if val not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1, got {val}")
    return val


def _require_nonbool_flag_01(value: Any, name: str) -> int:
    val = _require_nonbool_int(value, name)
    if val not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1, got {val}")
    return val


@dataclass(frozen=True)
class GRECT:
    """Digital Research GEM AES screen/window rectangle `(g_x, g_y, g_w, g_h)`."""

    g_x: int
    g_y: int
    g_w: int
    g_h: int

    def __post_init__(self) -> None:
        _require_int16(self.g_x, "g_x")
        _require_int16(self.g_y, "g_y")
        _require_int16(self.g_w, "g_w")
        _require_int16(self.g_h, "g_h")

    def __iter__(self) -> Iterator[int]:
        yield self.g_x
        yield self.g_y
        yield self.g_w
        yield self.g_h

    def __len__(self) -> int:
        return 4

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.g_x, self.g_y, self.g_w, self.g_h)

    def to_array(self) -> tuple[int, int, int, int]:
        """Convert GRECT `(x, y, w, h)` to inclusive VDI coordinates `(x1, y1, x2, y2)`."""
        if self.g_w <= 0 or self.g_h <= 0:
            return (self.g_x, self.g_y, self.g_x, self.g_y)
        return (self.g_x, self.g_y, self.g_x + self.g_w - 1, self.g_y + self.g_h - 1)

    def contains_point(self, px: int, py: int) -> bool:
        """Half-open containment `[g_x, g_x + g_w) x [g_y, g_y + g_h)`."""
        if self.g_w <= 0 or self.g_h <= 0:
            return False
        return (
            self.g_x <= px < self.g_x + self.g_w
            and self.g_y <= py < self.g_y + self.g_h
        )

    def intersect(self, other: GRECT) -> GRECT | None:
        """Return `rc_intersect` intersection if non-empty (`w > 0 and h > 0`), else `None`."""
        if self.g_w <= 0 or self.g_h <= 0 or other.g_w <= 0 or other.g_h <= 0:
            return None
        x1 = max(self.g_x, other.g_x)
        y1 = max(self.g_y, other.g_y)
        x2 = min(self.g_x + self.g_w, other.g_x + other.g_w)
        y2 = min(self.g_y + self.g_h, other.g_y + other.g_h)
        if x2 <= x1 or y2 <= y1:
            return None
        return GRECT(x1, y1, x2 - x1, y2 - y1)

    def subtract(self, occluder: GRECT) -> list[GRECT]:
        """Split `self` into non-overlapping positive-area rectangles outside `occluder`."""
        inter = self.intersect(occluder)
        if inter is None:
            return [self] if (self.g_w > 0 and self.g_h > 0) else []
        pieces: list[GRECT] = []
        sx1, sy1 = self.g_x, self.g_y
        sx2, sy2 = self.g_x + self.g_w, self.g_y + self.g_h
        ix1, iy1 = inter.g_x, inter.g_y
        ix2, iy2 = inter.g_x + inter.g_w, inter.g_y + inter.g_h

        # Top strip (full width of self)
        if iy1 > sy1:
            pieces.append(GRECT(sx1, sy1, sx2 - sx1, iy1 - sy1))
        # Bottom strip (full width of self)
        if sy2 > iy2:
            pieces.append(GRECT(sx1, iy2, sx2 - sx1, sy2 - iy2))
        # Left strip (height of intersection band)
        if ix1 > sx1:
            pieces.append(GRECT(sx1, iy1, ix1 - sx1, iy2 - iy1))
        # Right strip (height of intersection band)
        if sx2 > ix2:
            pieces.append(GRECT(ix2, iy1, sx2 - ix2, iy2 - iy1))
        return pieces


def _coerce_grect(
    rect: GRECT | Sequence[int],
    name: str = "rect",
    *,
    require_nonneg_dims: bool = False,
    require_pos_dims: bool = False,
) -> GRECT:
    if isinstance(rect, GRECT):
        gr = rect
    elif isinstance(rect, Sequence) and not isinstance(rect, (str, bytes, bytearray)):
        if len(rect) != 4:
            raise ValueError(f"{name} must have 4 elements (x, y, w, h), got {len(rect)}")
        gr = GRECT(
            _require_int16(rect[0], f"{name}[0]"),
            _require_int16(rect[1], f"{name}[1]"),
            _require_int16(rect[2], f"{name}[2]"),
            _require_int16(rect[3], f"{name}[3]"),
        )
    else:
        raise ValueError(f"{name} must be a GRECT or 4-int sequence, got {rect!r}")
    if require_nonneg_dims and (gr.g_w < 0 or gr.g_h < 0):
        raise ValueError(f"{name} width and height must be >= 0, got {gr.g_w}x{gr.g_h}")
    if require_pos_dims and (gr.g_w <= 0 or gr.g_h <= 0):
        raise ValueError(f"{name} width and height must be > 0, got {gr.g_w}x{gr.g_h}")
    return gr


# ============================================================================
# Typed Wrappers Around Untyped `vdi`, `model`, `geometry`, `runner` Modules
# ============================================================================

def _scene_from_dict(document: dict[str, Any]) -> Any:
    return _gem_model.Scene.from_dict(document)  # type: ignore[no-untyped-call]


def _verify_geometry(scene: Any) -> Any:
    return _gem_geometry.verify(scene)  # type: ignore[no-untyped-call]


def _verify_runner_vdi(scene: Any, data: bytes | None = None) -> Any:
    return _gem_runner.verify_vdi(scene, data)  # type: ignore[no-untyped-call]


def _parse_vdi_metafile(data: bytes) -> dict[str, Any]:
    return cast(dict[str, Any], _gem_vdi.parse_metafile(data))  # type: ignore[no-untyped-call]


# ============================================================================
# Section C — Feature #7: GemAesApplication & 16-Byte FIFO Message Pipe
# ============================================================================

@dataclass(frozen=True)
class AesEventMultiResult:
    """Structured result returned by `GemAesApplication.evnt_multi`."""

    matched_flags: int
    message: dict[str, Any] | None
    raw_bytes: bytes | None
    mx: int
    my: int
    mbutton: int
    kstate: int
    kreturn: int | None
    breturn: int
    timer_elapsed_ms: int
    extra_bytes_pending: int = 0

    def constitutional_metadata(self) -> dict[str, Any]:
        return constitutional_metadata(epistemic_lane="measurement")

    def to_dict(self) -> dict[str, Any]:
        return {
            "matched_flags": self.matched_flags,
            "message": dict(self.message) if self.message is not None else None,
            "raw_hex": self.raw_bytes.hex() if self.raw_bytes is not None else None,
            "raw_len": len(self.raw_bytes) if self.raw_bytes is not None else 0,
            "mx": self.mx,
            "my": self.my,
            "mbutton": self.mbutton,
            "kstate": self.kstate,
            "kreturn": self.kreturn,
            "breturn": self.breturn,
            "timer_elapsed_ms": self.timer_elapsed_ms,
            "extra_bytes_pending": self.extra_bytes_pending,
            "constitutional": self.constitutional_metadata(),
            "safety_invariants": dict(SAFETY_INVARIANTS),
        }


class GemAesKernel:
    """Shared in-memory AES process table & per-application byte FIFO pipes."""

    MAX_APPS = 16

    def __init__(self) -> None:
        self._apps: dict[int, str] = {}
        self._pipes: dict[int, bytearray] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        clean = str(name or "").strip()
        if not clean:
            raise ValueError("Application name must be non-empty")
        return clean[:8].ljust(8)

    def register(self, app_name: str, app_id: int | None = None) -> int:
        norm = self._normalize_name(app_name)
        if app_id is not None:
            apid = _require_nonbool_int(app_id, "app_id")
            if apid < 0 or apid >= self.MAX_APPS:
                raise ValueError(f"app_id must be in [0, {self.MAX_APPS - 1}], got {apid}")
            if apid in self._apps:
                raise ValueError(f"app_id {apid} is already registered")
            self._apps[apid] = norm
            self._pipes[apid] = bytearray()
            return apid
        for candidate in range(self.MAX_APPS):
            if candidate not in self._apps:
                self._apps[candidate] = norm
                self._pipes[candidate] = bytearray()
                return candidate
        return -1

    def unregister(self, apid: int) -> None:
        self._apps.pop(apid, None)
        self._pipes.pop(apid, None)

    def find(self, pname: str) -> int:
        target = self._normalize_name(pname)
        for apid, registered in self._apps.items():
            if registered == target or registered.rstrip() == target.rstrip():
                return apid
        return -1

    def pipe_for(self, apid: int) -> bytearray:
        if apid not in self._pipes:
            raise KeyError(f"Unknown AES ap_id: {apid}")
        return self._pipes[apid]


class GemAesApplication:
    """Clean-room Digital Research GEM AES Application & Event Manager (Ch. 2).

    Implements:
      - `appl_init`, `appl_exit`, `appl_find`, `appl_write`, `appl_read`
      - 16-byte `<8h` FIFO message pipe + `msg[2] > 0` extra payload byte streaming
      - `evnt_multi` (`MU_KEYBD`, `MU_BUTTON`, `MU_M1`, `MU_M2`, `MU_MESAG`, `MU_TIMER`)
      - Single-event helpers (`evnt_keybd`, `evnt_button`, `evnt_mouse`, `evnt_mesag`,
        `evnt_timer`, `evnt_dclick`)
    """

    def __init__(
        self,
        app_name: str = "ZOE_GEM",
        *,
        kernel: GemAesKernel | None = None,
    ) -> None:
        self._default_name = str(app_name or "ZOE_GEM")
        self._kernel = kernel if kernel is not None else GemAesKernel()
        self.ap_id: int = -1
        self.initialized: bool = False
        self.dclick_rate: int = 2
        self._history: list[dict[str, Any]] = []

    def _require_init(self) -> None:
        if not self.initialized or self.ap_id < 0:
            raise RuntimeError("AES application is not initialized; call appl_init() first")

    def constitutional_metadata(self) -> dict[str, Any]:
        return constitutional_metadata(epistemic_lane="measurement")

    def appl_init(
        self,
        app_name: str | None = None,
        *,
        app_id: int | None = None,
    ) -> int:
        """Register application with AES kernel and assign `ap_id >= 0` (or `-1` if full)."""
        if self.initialized:
            return self.ap_id
        name = self._default_name if app_name is None else app_name
        assigned = self._kernel.register(name, app_id=app_id)
        if assigned >= 0:
            self.ap_id = assigned
            self.initialized = True
        return assigned

    def appl_exit(self) -> int:
        """Release AES application slot and message pipe. Returns 1 on success, 0 if inactive."""
        if not self.initialized or self.ap_id < 0:
            return 0
        self._kernel.unregister(self.ap_id)
        self.ap_id = -1
        self.initialized = False
        return 1

    def appl_find(self, pname: str) -> int:
        """Look up an active application's `ap_id` by 8-char name (`-1` if absent)."""
        self._require_init()
        return self._kernel.find(pname)

    def appl_write(
        self,
        dest_apid: int,
        length: int,
        msg: Sequence[int] | bytes | bytearray,
        *,
        extra_bytes: bytes = b"",
    ) -> int:
        """Write `length` bytes (16-byte `<8h` message + optional extra bytes) to `dest_apid`."""
        self._require_init()
        target = _require_nonbool_int(dest_apid, "dest_apid")
        nbytes = _require_nonbool_int(length, "length")
        if nbytes <= 0:
            raise ValueError(f"appl_write length must be > 0, got {nbytes}")
        pipe = self._kernel.pipe_for(target)

        if isinstance(msg, (bytes, bytearray)):
            raw = bytes(msg)
            if extra_bytes:
                raw = raw + bytes(extra_bytes)
        else:
            words = list(msg)
            if len(words) != 8:
                raise ValueError(f"AES word message must have 8 words, got {len(words)}")
            packed = encode_aes_message(*(_require_int16(w, "msg_word") for w in words))
            raw = packed + bytes(extra_bytes)

        if len(raw) < nbytes:
            raise ValueError(
                f"appl_write buffer shorter than length: {len(raw)} < {nbytes}"
            )
        chunk = raw[:nbytes]
        pipe.extend(chunk)
        if len(chunk) >= 16:
            decoded = dict(decode_aes_message(chunk[:16]))
            decoded["extra_bytes_len"] = len(chunk) - 16
            self._history.append(decoded)
        return nbytes

    def appl_read(
        self,
        length_or_apid: int,
        length: int | None = None,
    ) -> bytes:
        """Read `length` bytes from an application's FIFO pipe (supports `(len)` or `(ap_id, len)`)."""
        self._require_init()
        if length is None:
            target = self.ap_id
            nbytes = _require_nonbool_int(length_or_apid, "length")
        else:
            target = _require_nonbool_int(length_or_apid, "ap_id")
            nbytes = _require_nonbool_int(length, "length")
        if nbytes <= 0:
            raise ValueError(f"appl_read length must be > 0, got {nbytes}")
        pipe = self._kernel.pipe_for(target)
        if len(pipe) < nbytes:
            raise ValueError(
                f"appl_read requested {nbytes} bytes from ap_id={target}, only {len(pipe)} available"
            )
        out = bytes(pipe[:nbytes])
        del pipe[:nbytes]
        return out

    def post_message(
        self,
        msg_type: int,
        sender_apid: int | None = None,
        extra_len: int = 0,
        w3: int = 0,
        w4: int = 0,
        w5: int = 0,
        w6: int = 0,
        w7: int = 0,
        *,
        dest_apid: int | None = None,
        extra_bytes: bytes = b"",
    ) -> bytes:
        """Encode a 16-byte `<8h` AES message (and optional `msg[2] > 0` payload) into FIFO."""
        self._require_init()
        src = self.ap_id if sender_apid is None else _require_int16(sender_apid, "sender_apid")
        dst = self.ap_id if dest_apid is None else _require_nonbool_int(dest_apid, "dest_apid")
        elen = _require_int16(extra_len, "extra_len")
        if elen < 0:
            raise ValueError(f"extra_len must be >= 0, got {elen}")
        if extra_bytes:
            if elen == 0:
                elen = _require_int16(len(extra_bytes), "extra_len")
            elif len(extra_bytes) != elen:
                raise ValueError(
                    f"extra_len ({elen}) does not match len(extra_bytes) ({len(extra_bytes)})"
                )
        raw = encode_aes_message(
            _require_int16(msg_type, "msg_type"),
            src,
            elen,
            _require_int16(w3, "w3"),
            _require_int16(w4, "w4"),
            _require_int16(w5, "w5"),
            _require_int16(w6, "w6"),
            _require_int16(w7, "w7"),
        )
        pipe = self._kernel.pipe_for(dst)
        pipe.extend(raw)
        if extra_bytes:
            pipe.extend(extra_bytes)
        decoded = dict(decode_aes_message(raw))
        decoded["extra_bytes_len"] = len(extra_bytes)
        self._history.append(decoded)
        return raw

    def pending_bytes(self, ap_id: int | None = None) -> int:
        self._require_init()
        target = self.ap_id if ap_id is None else _require_nonbool_int(ap_id, "ap_id")
        return len(self._kernel.pipe_for(target))

    def evnt_dclick(self, rate: int = 2, setit: int = 0) -> int:
        """Get (`setit=0`) or set (`setit=1`) double-click speed (`0..4`)."""
        self._require_init()
        s = _require_flag_01(setit, "setit")
        if s == 1:
            r = _require_nonbool_int(rate, "rate")
            if not 0 <= r <= 4:
                raise ValueError(f"evnt_dclick rate must be in 0..4, got {r}")
            self.dclick_rate = r
        return self.dclick_rate

    def evnt_multi(
        self,
        flags: int = MU_MESAG | MU_TIMER,
        *,
        bclicks: int = 1,
        bmask: int = 1,
        bstate: int = 1,
        m1_flag: int = 0,
        m1_rect: GRECT | Sequence[int] = (0, 0, 0, 0),
        m2_flag: int = 0,
        m2_rect: GRECT | Sequence[int] = (0, 0, 0, 0),
        timer_ms: int = 0,
        lo_timint: int | None = None,
        hi_timint: int | None = None,
        key_code: int | None = None,
        kstate: int = 0,
        mouse_x: int = 0,
        mouse_y: int = 0,
        button_state: int = 0,
        clicks: int = 0,
    ) -> AesEventMultiResult:
        """Evaluate AES `evnt_multi` over `MU_KEYBD | MU_BUTTON | MU_M1 | MU_M2 | MU_MESAG | MU_TIMER`.

        - `MU_M1` / `MU_M2`: `flag == 0` triggers when `(mouse_x, mouse_y)` is inside
          half-open `[x, x + w) x [y, y + h)`; `flag == 1` triggers when outside.
        - `MU_BUTTON`: matches when `(button_state & bmask) == (bstate & bmask)`.
        - `MU_MESAG`: pops one 16-byte `<8h` message from the FIFO pipe; if `msg[2] > 0`,
          the extra bytes remain in the pipe for `appl_read(msg[2])`.
        """
        self._require_init()
        clean_flags = _require_nonbool_int(flags, "flags")
        if clean_flags <= 0 or (clean_flags & ~_ALL_MU_FLAGS) != 0:
            raise ValueError(
                f"flags must be a non-empty subset of 0x003F, got {clean_flags:#x}"
            )
        if lo_timint is not None or hi_timint is not None:
            lo = 0 if lo_timint is None else _require_nonbool_int(lo_timint, "lo_timint")
            hi = 0 if hi_timint is None else _require_nonbool_int(hi_timint, "hi_timint")
            if not (0 <= lo <= 0xFFFF):
                raise ValueError(f"lo_timint must be in [0, 65535], got {lo}")
            if not (0 <= hi <= 0xFFFF):
                raise ValueError(f"hi_timint must be in [0, 65535], got {hi}")
            clean_timer = (hi << 16) | lo
        else:
            clean_timer = _require_nonbool_int(timer_ms, "timer_ms")
        if clean_timer < 0:
            raise ValueError(f"timer_ms must be >= 0, got {clean_timer}")

        clean_bclicks = _require_nonbool_int(bclicks, "bclicks")
        clean_bmask = _require_nonbool_int(bmask, "bmask")
        clean_bstate = _require_nonbool_int(bstate, "bstate")
        if (clean_flags & MU_BUTTON) and clean_bclicks <= 0:
            raise ValueError(f"bclicks must be >= 1 when MU_BUTTON is requested, got {clean_bclicks}")

        clean_m1_flag = _require_nonbool_flag_01(m1_flag, "m1_flag")
        clean_m2_flag = _require_nonbool_flag_01(m2_flag, "m2_flag")
        g_m1 = _coerce_grect(m1_rect, "m1_rect", require_nonneg_dims=True)
        g_m2 = _coerce_grect(m2_rect, "m2_rect", require_nonneg_dims=True)

        mx = _require_int16(mouse_x, "mouse_x")
        my = _require_int16(mouse_y, "mouse_y")
        mbutton = _require_nonbool_int(button_state, "button_state")
        clean_clicks = _require_nonbool_int(clicks, "clicks")
        clean_kstate = _require_nonbool_int(kstate, "kstate")
        clean_key: int | None = None
        if key_code is not None:
            clean_key = _require_int16(key_code, "key_code")

        matched = 0
        raw_msg: bytes | None = None
        decoded_msg: dict[str, Any] | None = None
        breturn = 0

        if clean_flags & MU_MESAG:
            pipe = self._kernel.pipe_for(self.ap_id)
            if len(pipe) >= 16:
                raw_msg = bytes(pipe[:16])
                del pipe[:16]
                decoded_msg = dict(decode_aes_message(raw_msg))
                matched |= MU_MESAG

        if (clean_flags & MU_KEYBD) and clean_key is not None:
            matched |= MU_KEYBD

        if (clean_flags & MU_BUTTON) and ((mbutton & clean_bmask) == (clean_bstate & clean_bmask)):
            matched |= MU_BUTTON
            if clean_clicks > 0:
                breturn = min(clean_clicks, clean_bclicks)
            else:
                breturn = 1

        if clean_flags & MU_M1:
            inside_m1 = g_m1.contains_point(mx, my)
            if (clean_m1_flag == 0 and inside_m1) or (clean_m1_flag == 1 and not inside_m1):
                matched |= MU_M1

        if clean_flags & MU_M2:
            inside_m2 = g_m2.contains_point(mx, my)
            if (clean_m2_flag == 0 and inside_m2) or (clean_m2_flag == 1 and not inside_m2):
                matched |= MU_M2

        if (clean_flags & MU_TIMER) and (matched == 0 or clean_timer > 0):
            matched |= MU_TIMER

        pending_extra = 0
        if decoded_msg is not None and int(decoded_msg["extra_len"]) > 0:
            pending_extra = min(int(decoded_msg["extra_len"]), self.pending_bytes())

        return AesEventMultiResult(
            matched_flags=matched,
            message=decoded_msg,
            raw_bytes=raw_msg,
            mx=mx,
            my=my,
            mbutton=mbutton,
            kstate=clean_kstate,
            kreturn=clean_key if (matched & MU_KEYBD) else None,
            breturn=breturn,
            timer_elapsed_ms=clean_timer if (matched & MU_TIMER) else 0,
            extra_bytes_pending=pending_extra,
        )

    def evnt_mesag(self) -> dict[str, Any] | None:
        res = self.evnt_multi(MU_MESAG)
        return res.message

    def evnt_keybd(self, key_code: int, kstate: int = 0) -> AesEventMultiResult:
        return self.evnt_multi(MU_KEYBD, key_code=key_code, kstate=kstate)

    def evnt_button(
        self,
        bclicks: int = 1,
        bmask: int = 1,
        bstate: int = 1,
        *,
        mouse_x: int = 0,
        mouse_y: int = 0,
        button_state: int = 0,
        clicks: int = 1,
    ) -> AesEventMultiResult:
        return self.evnt_multi(
            MU_BUTTON,
            bclicks=bclicks,
            bmask=bmask,
            bstate=bstate,
            mouse_x=mouse_x,
            mouse_y=mouse_y,
            button_state=button_state,
            clicks=clicks,
        )

    def evnt_mouse(
        self,
        flag: int,
        rect: GRECT | Sequence[int],
        *,
        mouse_x: int = 0,
        mouse_y: int = 0,
    ) -> AesEventMultiResult:
        return self.evnt_multi(
            MU_M1, m1_flag=flag, m1_rect=rect, mouse_x=mouse_x, mouse_y=mouse_y
        )

    def evnt_timer(self, timer_ms: int = 0) -> AesEventMultiResult:
        return self.evnt_multi(MU_TIMER, timer_ms=timer_ms)

    def message_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(entry) for entry in self._history)

    def snapshot(self) -> dict[str, Any]:
        return {
            "ap_id": self.ap_id,
            "initialized": self.initialized,
            "dclick_rate": self.dclick_rate,
            "pending_bytes": self.pending_bytes() if self.initialized else 0,
            "messages_logged": len(self._history),
            "constitutional": self.constitutional_metadata(),
        }


# ============================================================================
# Section D — Feature #8: GemAesWindowTreeManager & Rectangle-List Redraw
# ============================================================================

@dataclass
class _ManagedWindow:
    handle: int
    kind: int
    full_rect: GRECT
    curr_rect: GRECT
    prev_rect: GRECT
    title: str = ""
    info: str = ""
    layer_id: str = ""
    opened: bool = False
    fulled: bool = False
    hslide: int = 1
    vslide: int = 1
    hsize: int = 1000
    vsize: int = 1000
    rect_list: list[GRECT] = field(default_factory=list)
    rect_cursor: int = 0


class GemAesWindowTreeManager:
    """Digital Research GEM AES Window & Rectangle-List Redraw Manager (Ch. 2 & 4).

    Enforces `MAX_AES_APP_WINDOWS = 7` (handles `1..7`; handle `0` = desktop `DESK`),
    maintains exact z-order, reversible `wind_calc(WC_BORDER/WC_WORK)` chrome geometry,
    balanced `wind_update` locks, and `WF_FIRSTXYWH`/`WF_NEXTXYWH` occlusion clipping.
    """

    def __init__(
        self,
        screen_w: int = 640,
        screen_h: int = 400,
        *,
        event_app: GemAesApplication | None = None,
    ) -> None:
        sw = _require_nonbool_int(screen_w, "screen_w")
        sh = _require_nonbool_int(screen_h, "screen_h")
        if sw <= 0 or sh <= 0 or sw > 32767 or sh > 32767:
            raise ValueError(f"screen dimensions must be in (0, 32767], got {sw}x{sh}")
        self.screen_w = sw
        self.screen_h = sh
        self.desk = seasip_gem.GemAesDesk(screen_w=sw, screen_h=sh)
        self.event_app = event_app
        self._windows: dict[int, _ManagedWindow] = {}
        self._z_order: list[int] = []  # bottom-to-top open app handles
        self._update_lock_depth: int = 0
        self._mctrl_lock_depth: int = 0
        self._newdesk_tree: Any = None
        self._desk_rect_list: list[GRECT] = []
        self._desk_rect_cursor: int = 0

    def constitutional_metadata(self) -> dict[str, Any]:
        return constitutional_metadata(epistemic_lane="measurement")

    @property
    def top_handle(self) -> int:
        return self._z_order[-1] if self._z_order else 0

    @property
    def update_lock_depth(self) -> int:
        return self._update_lock_depth

    @property
    def mctrl_lock_depth(self) -> int:
        return self._mctrl_lock_depth

    def _require_app_window(self, handle: int) -> _ManagedWindow:
        h = _require_nonbool_int(handle, "handle")
        if h not in self._windows:
            raise KeyError(f"Unknown GEM window handle: {h}")
        return self._windows[h]

    def _emit_msg(
        self,
        msg_type: int,
        w3: int = 0,
        w4: int = 0,
        w5: int = 0,
        w6: int = 0,
        w7: int = 0,
    ) -> bytes:
        raw = encode_aes_message(msg_type, 0, 0, w3, w4, w5, w6, w7)
        if self.event_app is not None and self.event_app.initialized:
            self.event_app.post_message(msg_type, 0, 0, w3, w4, w5, w6, w7)
        return raw

    @staticmethod
    def _chrome_pads(kind: int) -> tuple[int, int, int, int]:
        """Return `(left_pad, top_pad, right_pad, bottom_pad)` for `kind` bitmask."""
        k = _require_nonbool_int(kind, "kind")
        if k < 0 or k > 0xFFFF:
            raise ValueError(f"window kind must be in [0, 0xFFFF], got {k:#x}")
        left = 2
        right = 16 if (k & (UPARROW | DNARROW | VSLIDE | SIZER)) else 2
        top = 2
        if k & (NAME | CLOSER | FULLER | MOVER):
            top += 18
        if k & INFO:
            top += 14
        bottom = 16 if (k & (LFARROW | RTARROW | HSLIDE | SIZER)) else 2
        return (left, top, right, bottom)

    def wind_calc(
        self,
        wtype: int,
        kind: int,
        rect: GRECT | Sequence[int],
    ) -> GRECT:
        """Convert between outer border (`WC_BORDER=0`) and work area (`WC_WORK=1`)."""
        wt = _require_nonbool_int(wtype, "wtype")
        if wt not in (WC_BORDER, WC_WORK):
            raise ValueError(f"wind_calc wtype must be WC_BORDER (0) or WC_WORK (1), got {wt}")
        gr = _coerce_grect(rect, "rect", require_pos_dims=True)
        left, top, right, bottom = self._chrome_pads(kind)
        if wt == WC_WORK:
            ww = gr.g_w - (left + right)
            wh = gr.g_h - (top + bottom)
            if ww <= 0 or wh <= 0:
                raise ValueError(
                    f"Window outer rect {gr.as_tuple()} too small for chrome pads "
                    f"({left}, {top}, {right}, {bottom})"
                )
            return GRECT(gr.g_x + left, gr.g_y + top, ww, wh)
        return GRECT(
            gr.g_x - left,
            gr.g_y - top,
            gr.g_w + left + right,
            gr.g_h + top + bottom,
        )

    def wind_create(
        self,
        kind: int,
        rect: GRECT | Sequence[int],
        *,
        title: str = "",
        info: str = "",
        layer_id: str = "",
    ) -> int:
        """Allocate AES window handle `1..7`, or return `-1` if all 7 slots are occupied."""
        k = _require_nonbool_int(kind, "kind")
        if k < 0 or k > 0xFFFF:
            raise ValueError(f"window kind must be in [0, 0xFFFF], got {k:#x}")
        full_gr = _coerce_grect(rect, "rect", require_pos_dims=True)
        handle = self.desk.wind_create(
            k,
            full_gr.g_x,
            full_gr.g_y,
            full_gr.g_w,
            full_gr.g_h,
            title=str(title),
            info=str(info),
            layer_id=str(layer_id),
        )
        if handle == -1:
            return -1
        self._windows[handle] = _ManagedWindow(
            handle=handle,
            kind=k,
            full_rect=full_gr,
            curr_rect=full_gr,
            prev_rect=full_gr,
            title=str(title),
            info=str(info),
            layer_id=str(layer_id),
        )
        return int(handle)

    def wind_open(
        self,
        handle: int,
        rect: GRECT | Sequence[int] | None = None,
    ) -> bytes:
        """Open a created window, push it to top of z-order, and emit `WM_REDRAW`."""
        win = self._require_app_window(handle)
        if rect is not None:
            new_gr = _coerce_grect(rect, "rect", require_pos_dims=True)
            win.prev_rect = win.curr_rect
            win.curr_rect = new_gr
            desk_win = self.desk.windows[win.handle]
            desk_win.x, desk_win.y, desk_win.w, desk_win.h = new_gr.as_tuple()
        prev_top = self.top_handle
        win.opened = True
        if win.handle in self._z_order:
            self._z_order.remove(win.handle)
        self._z_order.append(win.handle)
        self.desk.wind_open(win.handle)
        if prev_top != 0 and prev_top != win.handle:
            self._emit_msg(WM_UNTOPPED, prev_top, win.handle)
        return self._emit_msg(
            WM_REDRAW,
            win.handle,
            win.curr_rect.g_x,
            win.curr_rect.g_y,
            win.curr_rect.g_w,
            win.curr_rect.g_h,
        )

    def wind_close(self, handle: int) -> bytes:
        """Close an open window while retaining its handle, updating z-order top."""
        h = _require_nonbool_int(handle, "handle")
        if h == 0:
            raise ValueError("Cannot close desktop window handle 0")
        win = self._require_app_window(h)
        if not win.opened:
            raise ValueError(f"Window {h} is already closed")
        was_top = self.top_handle == h
        win.opened = False
        if h in self._z_order:
            self._z_order.remove(h)
        self.desk.windows[h].opened = False
        self.desk.top_handle = self.top_handle
        closed_msg = self._emit_msg(WM_CLOSED, h)
        if was_top and self.top_handle != 0:
            self._emit_msg(WM_NEWTOP, self.top_handle)
        return closed_msg

    def wind_delete(self, handle: int) -> int:
        """Close if open and free window slot `handle` for reuse."""
        h = _require_nonbool_int(handle, "handle")
        if h == 0:
            raise ValueError("Cannot delete desktop window handle 0")
        win = self._require_app_window(h)
        if win.opened:
            self.wind_close(h)
        del self._windows[h]
        self.desk.windows.pop(h, None)
        self.desk.top_handle = self.top_handle
        return 1

    def wind_find(self, mx: int, my: int) -> int:
        """Return topmost open window containing `(mx, my)`, or `0` (desktop)."""
        x = _require_int16(mx, "mx")
        y = _require_int16(my, "my")
        for h in reversed(self._z_order):
            win = self._windows[h]
            if win.opened and win.curr_rect.contains_point(x, y):
                return h
        return 0

    def wind_update(self, beg_end: int) -> int:
        """Acquire or release `UPDATE` (`1`/`0`) or `MCTRL` (`3`/`2`) lock with balance check."""
        code = _require_nonbool_int(beg_end, "beg_end")
        if code == BEG_UPDATE:
            self._update_lock_depth += 1
            return 1
        if code == END_UPDATE:
            if self._update_lock_depth <= 0:
                raise ValueError("Unbalanced wind_update(END_UPDATE): update lock depth is 0")
            self._update_lock_depth -= 1
            return 1
        if code == BEG_MCTRL:
            self._mctrl_lock_depth += 1
            return 1
        if code == END_MCTRL:
            if self._mctrl_lock_depth <= 0:
                raise ValueError("Unbalanced wind_update(END_MCTRL): mctrl lock depth is 0")
            self._mctrl_lock_depth -= 1
            return 1
        raise ValueError(f"Invalid wind_update code: {code}")

    def _work_rect_for(self, win: _ManagedWindow) -> GRECT:
        try:
            return self.wind_calc(WC_WORK, win.kind, win.curr_rect)
        except ValueError:
            return win.curr_rect

    def compute_visible_rectangles(self, handle: int) -> list[GRECT]:
        """Compute non-overlapping visible work rectangles of `handle` above higher-z occluders."""
        h = _require_nonbool_int(handle, "handle")
        screen_rect = GRECT(0, 0, self.screen_w, self.screen_h)
        if h == 0:
            visible: list[GRECT] = [screen_rect]
            for wh in self._z_order:
                w = self._windows[wh]
                if not w.opened:
                    continue
                next_vis: list[GRECT] = []
                for frag in visible:
                    next_vis.extend(frag.subtract(w.curr_rect))
                visible = next_vis
            return visible

        win = self._require_app_window(h)
        if not win.opened:
            return []
        work = self._work_rect_for(win)
        clipped = work.intersect(screen_rect)
        if clipped is None:
            return []
        visible = [clipped]
        idx = self._z_order.index(h)
        for occ_handle in self._z_order[idx + 1 :]:
            occ = self._windows[occ_handle]
            if not occ.opened:
                continue
            next_vis = []
            for frag in visible:
                next_vis.extend(frag.subtract(occ.curr_rect))
            visible = next_vis
        return visible

    def wind_get(self, handle: int, field_id: int | str) -> Any:
        """Query GEM window attribute (`WF_*` integer code or string alias)."""
        h = _require_nonbool_int(handle, "handle")
        if isinstance(field_id, str):
            alias = field_id.strip().lower()
            alias_map: dict[str, int] = {
                "kind": WF_KIND,
                "name": WF_NAME,
                "info": WF_INFO,
                "work_rect": WF_WORKXYWH,
                "work": WF_WORKXYWH,
                "curr_rect": WF_CURRXYWH,
                "rect": WF_CURRXYWH,
                "prev_rect": WF_PREVXYWH,
                "full_rect": WF_FULLXYWH,
                "hslide": WF_HSLIDE,
                "vslide": WF_VSLIDE,
                "top": WF_TOP,
                "firstxywh": WF_FIRSTXYWH,
                "nextxywh": WF_NEXTXYWH,
                "hslsize": WF_HSLSIZE,
                "vslsize": WF_VSLSIZE,
            }
            if alias == "meta":
                win = self._require_app_window(h)
                return {
                    "handle": win.handle,
                    "title": win.title,
                    "info": win.info,
                    "layer_id": win.layer_id,
                    "opened": win.opened,
                    "rect": list(win.curr_rect.as_tuple()),
                }
            if alias not in alias_map:
                raise ValueError(f"Unsupported wind_get field: {field_id!r}")
            code = alias_map[alias]
        else:
            code = _require_nonbool_int(field_id, "field_id")

        if code == WF_TOP:
            return self.top_handle
        if code == WF_SCREEN:
            return GRECT(0, 0, self.screen_w, self.screen_h)
        if h == 0:
            if code in (WF_WORKXYWH, WF_CURRXYWH, WF_FULLXYWH):
                return GRECT(0, 0, self.screen_w, self.screen_h)
            if code == WF_FIRSTXYWH:
                self._desk_rect_list = self.compute_visible_rectangles(0)
                self._desk_rect_cursor = 1 if self._desk_rect_list else 0
                return self._desk_rect_list[0] if self._desk_rect_list else GRECT(0, 0, 0, 0)
            if code == WF_NEXTXYWH:
                if self._desk_rect_cursor < len(self._desk_rect_list):
                    rect = self._desk_rect_list[self._desk_rect_cursor]
                    self._desk_rect_cursor += 1
                    return rect
                return GRECT(0, 0, 0, 0)
            raise ValueError(f"Unsupported wind_get field {code} on desktop handle 0")

        win = self._require_app_window(h)
        if code == WF_KIND:
            return win.kind
        if code == WF_NAME:
            return win.title
        if code == WF_INFO:
            return win.info
        if code == WF_WORKXYWH:
            return self._work_rect_for(win)
        if code == WF_CURRXYWH:
            return win.curr_rect
        if code == WF_PREVXYWH:
            return win.prev_rect
        if code == WF_FULLXYWH:
            return win.full_rect
        if code == WF_HSLIDE:
            return win.hslide
        if code == WF_VSLIDE:
            return win.vslide
        if code == WF_HSLSIZE:
            return win.hsize
        if code == WF_VSLSIZE:
            return win.vsize
        if code == WF_FIRSTXYWH:
            win.rect_list = self.compute_visible_rectangles(win.handle)
            if not win.rect_list:
                win.rect_cursor = 0
                return GRECT(0, 0, 0, 0)
            win.rect_cursor = 1
            return win.rect_list[0]
        if code == WF_NEXTXYWH:
            if 0 < win.rect_cursor < len(win.rect_list):
                rect = win.rect_list[win.rect_cursor]
                win.rect_cursor += 1
                return rect
            return GRECT(0, 0, 0, 0)
        raise ValueError(f"Unsupported wind_get field code: {code}")

    def wind_set(self, handle: int, field_id: int | str, *values: Any) -> dict[str, Any]:
        """Update GEM window property (`WF_NAME`, `WF_INFO`, `WF_CURRXYWH`, `WF_TOP`, sliders, etc.)."""
        h = _require_nonbool_int(handle, "handle")
        if isinstance(field_id, str):
            alias = field_id.strip().lower()
            alias_map: dict[str, int] = {
                "name": WF_NAME,
                "title": WF_NAME,
                "info": WF_INFO,
                "curr_rect": WF_CURRXYWH,
                "rect": WF_CURRXYWH,
                "hslide": WF_HSLIDE,
                "vslide": WF_VSLIDE,
                "top": WF_TOP,
                "newdesk": WF_NEWDESK,
                "hslsize": WF_HSLSIZE,
                "vslsize": WF_VSLSIZE,
            }
            if alias not in alias_map:
                raise ValueError(f"Unsupported wind_set field: {field_id!r}")
            code = alias_map[alias]
        else:
            code = _require_nonbool_int(field_id, "field_id")

        if code == WF_NEWDESK:
            self._newdesk_tree = values[0] if values else None
            return {"handle": 0, "field": WF_NEWDESK, "ok": 1}

        win = self._require_app_window(h)
        if code == WF_NAME:
            win.title = str(values[0]) if values else ""
            self.desk.windows[h].title = win.title
            return {"handle": h, "field": WF_NAME, "title": win.title}
        if code == WF_INFO:
            win.info = str(values[0]) if values else ""
            self.desk.windows[h].info = win.info
            return {"handle": h, "field": WF_INFO, "info": win.info}
        if code == WF_CURRXYWH:
            if len(values) == 1:
                new_gr = _coerce_grect(values[0], "rect", require_pos_dims=True)
            elif len(values) == 4:
                new_gr = _coerce_grect(values, "rect", require_pos_dims=True)
            else:
                raise ValueError("WF_CURRXYWH expects a GRECT or 4 ints (x, y, w, h)")
            win.prev_rect = win.curr_rect
            win.curr_rect = new_gr
            desk_win = self.desk.windows[h]
            desk_win.x, desk_win.y, desk_win.w, desk_win.h = new_gr.as_tuple()
            msg = self._emit_msg(WM_REDRAW, h, *new_gr.as_tuple()) if win.opened else None
            return {
                "handle": h,
                "field": WF_CURRXYWH,
                "rect": list(new_gr.as_tuple()),
                "msg_hex": msg.hex() if msg else None,
            }
        if code == WF_TOP:
            if not win.opened:
                raise ValueError(f"Cannot top closed window {h}")
            prev_top = self.top_handle
            if h in self._z_order:
                self._z_order.remove(h)
            self._z_order.append(h)
            self.desk.top_handle = h
            if prev_top != 0 and prev_top != h:
                self._emit_msg(WM_UNTOPPED, prev_top, h)
            msg = self._emit_msg(WM_TOPPED, h)
            return {"handle": h, "field": WF_TOP, "top_handle": h, "msg_hex": msg.hex()}
        if code == WF_HSLIDE:
            if not values:
                raise ValueError("WF_HSLIDE requires an integer slider position")
            pos = max(0, min(1000, _require_nonbool_int(values[0], "hslide")))
            win.hslide = pos
            return {"handle": h, "field": WF_HSLIDE, "value": pos}
        if code == WF_VSLIDE:
            if not values:
                raise ValueError("WF_VSLIDE requires an integer slider position")
            pos = max(0, min(1000, _require_nonbool_int(values[0], "vslide")))
            win.vslide = pos
            return {"handle": h, "field": WF_VSLIDE, "value": pos}
        if code == WF_HSLSIZE:
            if not values:
                raise ValueError("WF_HSLSIZE requires an integer slider size")
            sz = _require_nonbool_int(values[0], "hslsize")
            win.hsize = -1 if sz == -1 else max(1, min(1000, sz))
            return {"handle": h, "field": WF_HSLSIZE, "value": win.hsize}
        if code == WF_VSLSIZE:
            if not values:
                raise ValueError("WF_VSLSIZE requires an integer slider size")
            sz = _require_nonbool_int(values[0], "vslsize")
            win.vsize = -1 if sz == -1 else max(1, min(1000, sz))
            return {"handle": h, "field": WF_VSLSIZE, "value": win.vsize}
        raise ValueError(f"Unsupported wind_set field code: {code}")

    def walk_redraw_rectangles(
        self,
        win_id: int,
        dirty_rect: GRECT | Sequence[int],
    ) -> list[GRECT]:
        """Walk `WF_FIRSTXYWH`/`WF_NEXTXYWH` visible clip list intersected with `dirty_rect`."""
        dirty = _coerce_grect(dirty_rect, "dirty_rect", require_nonneg_dims=True)
        if dirty.g_w == 0 or dirty.g_h == 0:
            return []
        clips: list[GRECT] = []
        rect = cast(GRECT, self.wind_get(win_id, WF_FIRSTXYWH))
        while rect.g_w > 0 and rect.g_h > 0:
            clipped = rect.intersect(dirty)
            if clipped is not None:
                clips.append(clipped)
            rect = cast(GRECT, self.wind_get(win_id, WF_NEXTXYWH))
        return clips

    def summary(self) -> dict[str, Any]:
        return {
            "screen": [self.screen_w, self.screen_h],
            "max_app_windows": MAX_AES_APP_WINDOWS,
            "allocated_handles": sorted(self._windows.keys()),
            "z_order": list(self._z_order),
            "top_handle": self.top_handle,
            "update_lock_depth": self._update_lock_depth,
            "mctrl_lock_depth": self._mctrl_lock_depth,
            "constitutional": self.constitutional_metadata(),
        }

    def snapshot(self) -> dict[str, Any]:
        return self.summary()


# ============================================================================
# Section E — Feature #9: Object Tree, Form, Menu & Resource Manager
# ============================================================================

@dataclass
class GemObject:
    """Canonical 11-field Digital Research GEM `OBJECT` (`obdefs.h`, `PROJECT.md § 4`)."""

    ob_next: int = NIL
    ob_head: int = NIL
    ob_tail: int = NIL
    ob_type: int = G_BOX
    ob_flags: int = 0
    ob_state: int = NORMAL
    ob_spec: int = 0
    ob_x: int = 0
    ob_y: int = 0
    ob_w: int = 0
    ob_h: int = 0
    text: str | None = field(default=None, repr=False)


class GemObjectTreeOps:
    """Clean-room GEM AES Object Library operations with strict cycle & `LASTOB` checks."""

    @staticmethod
    def _build_parent_map(tree: Sequence[GemObject]) -> dict[int, int]:
        """Traverse children of all nodes, validating links and rejecting cycles."""
        n = len(tree)
        if n == 0:
            raise ValueError("Object tree cannot be empty")
        parent_of: dict[int, int] = {}
        for parent_idx, node in enumerate(tree):
            for fld_name, idx_val in (
                ("ob_next", node.ob_next),
                ("ob_head", node.ob_head),
                ("ob_tail", node.ob_tail),
            ):
                if idx_val != NIL and not (0 <= idx_val < n):
                    raise IndexError(
                        f"Object {parent_idx}.{fld_name}={idx_val} out of range [0, {n - 1}]"
                    )
            if (node.ob_head == NIL) != (node.ob_tail == NIL):
                raise ValueError(
                    f"Object {parent_idx} has inconsistent head/tail ({node.ob_head}, {node.ob_tail})"
                )
            if node.ob_head != NIL:
                seen_sibs: set[int] = set()
                cur = node.ob_head
                last = NIL
                while cur != parent_idx:
                    if cur == NIL:
                        raise ValueError(
                            f"Object {parent_idx} child chain hit NIL before returning to parent"
                        )
                    if cur in seen_sibs:
                        raise ValueError(
                            f"Cycle detected in sibling chain under parent {parent_idx} at {cur}"
                        )
                    if cur in parent_of:
                        raise ValueError(
                            f"Object {cur} has multiple parents ({parent_of[cur]} and {parent_idx})"
                        )
                    seen_sibs.add(cur)
                    parent_of[cur] = parent_idx
                    last = cur
                    cur = tree[cur].ob_next
                if last != node.ob_tail:
                    raise ValueError(
                        f"Object {parent_idx}.ob_tail={node.ob_tail} does not match last child {last}"
                    )
        # Verify no ancestor cycle from any node
        for idx in range(n):
            anc_seen: set[int] = set()
            cur = idx
            while cur in parent_of:
                if cur in anc_seen:
                    raise ValueError(f"Ancestor cycle detected at object {cur}")
                anc_seen.add(cur)
                cur = parent_of[cur]
        return parent_of

    @classmethod
    def validate_tree(cls, tree: Sequence[GemObject]) -> dict[int, int]:
        """Validate `LASTOB`, non-negative dims, bounds, and acyclicity; return `parent_of` map."""
        if not tree:
            raise ValueError("Object tree cannot be empty")
        if tree[0].ob_next != NIL:
            raise ValueError(f"Root object 0 must have ob_next == -1, got {tree[0].ob_next}")
        n = len(tree)
        for idx, obj in enumerate(tree):
            if obj.ob_w < 0 or obj.ob_h < 0:
                raise ValueError(f"Object {idx} has negative dimensions ({obj.ob_w}x{obj.ob_h})")
            has_lastob = bool(obj.ob_flags & LASTOB)
            if idx < n - 1 and has_lastob:
                raise ValueError(f"Premature LASTOB flag on non-final object {idx}")
            if idx == n - 1 and not has_lastob:
                raise ValueError(f"Final object {idx} is missing LASTOB (0x0020) flag")
        return cls._build_parent_map(tree)

    @classmethod
    def objc_add(cls, tree: list[GemObject], parent: int, child: int) -> int:
        """Append unlinked `child` as last child of `parent`, rejecting cycles/invalid bounds."""
        p = _require_nonbool_int(parent, "parent")
        c = _require_nonbool_int(child, "child")
        n = len(tree)
        if not (0 <= p < n) or not (0 <= c < n):
            raise IndexError(f"objc_add index out of range: parent={p}, child={c}, len={n}")
        if c == ROOT:
            raise ValueError("Cannot add ROOT object 0 as a child")
        if p == c:
            raise ValueError(f"Self-parenting cycle rejected: parent == child == {p}")
        parent_of = cls._build_parent_map(tree)
        if c in parent_of:
            raise ValueError(f"Child object {c} already has parent {parent_of[c]}")
        if tree[c].ob_next != NIL:
            raise ValueError(f"Child object {c} is already linked (ob_next={tree[c].ob_next})")
        # Reject if c is an ancestor of p
        anc = p
        while anc in parent_of:
            anc = parent_of[anc]
            if anc == c:
                raise ValueError(f"Cycle rejected: {c} is an ancestor of {p}")

        p_obj = tree[p]
        c_obj = tree[c]
        if p_obj.ob_head == NIL:
            p_obj.ob_head = c
            p_obj.ob_tail = c
            c_obj.ob_next = p
        else:
            tree[p_obj.ob_tail].ob_next = c
            p_obj.ob_tail = c
            c_obj.ob_next = p
        return 1

    @classmethod
    def objc_delete(cls, tree: list[GemObject], obj_idx: int) -> int:
        """Unlink `obj_idx` (cannot delete `ROOT=0`) from its parent's child chain."""
        idx = _require_nonbool_int(obj_idx, "obj_idx")
        n = len(tree)
        if not (0 <= idx < n):
            raise IndexError(f"objc_delete index {idx} out of range [0, {n - 1}]")
        if idx == ROOT:
            raise ValueError("Cannot delete ROOT object 0")
        parent_of = cls._build_parent_map(tree)
        if idx not in parent_of:
            raise ValueError(f"Object {idx} is not linked to any parent")
        p = parent_of[idx]
        p_obj = tree[p]
        target = tree[idx]
        if p_obj.ob_head == idx and p_obj.ob_tail == idx:
            p_obj.ob_head = NIL
            p_obj.ob_tail = NIL
        elif p_obj.ob_head == idx:
            p_obj.ob_head = target.ob_next
        else:
            prev = p_obj.ob_head
            while prev != NIL and prev != p and tree[prev].ob_next != idx:
                prev = tree[prev].ob_next
            if prev == NIL or prev == p:
                raise ValueError(f"Broken sibling chain for object {idx}")
            tree[prev].ob_next = target.ob_next
            if p_obj.ob_tail == idx:
                p_obj.ob_tail = prev
        target.ob_next = NIL
        return 1

    @classmethod
    def objc_order(cls, tree: list[GemObject], obj_idx: int, new_pos: int) -> int:
        """Reorder `obj_idx` among its parent's children (`0`=first, `-1`=last)."""
        idx = _require_nonbool_int(obj_idx, "obj_idx")
        pos = _require_nonbool_int(new_pos, "new_pos")
        n = len(tree)
        if not (0 <= idx < n):
            raise IndexError(f"objc_order index {idx} out of range [0, {n - 1}]")
        if idx == ROOT:
            raise ValueError("Cannot reorder ROOT object 0")
        parent_of = cls._build_parent_map(tree)
        if idx not in parent_of:
            raise ValueError(f"Object {idx} has no parent")
        p = parent_of[idx]
        p_obj = tree[p]
        siblings: list[int] = []
        cur = p_obj.ob_head
        while cur != p:
            siblings.append(cur)
            cur = tree[cur].ob_next
        siblings.remove(idx)
        if pos < 0 or pos >= len(siblings):
            siblings.append(idx)
        else:
            siblings.insert(pos, idx)
        p_obj.ob_head = siblings[0]
        p_obj.ob_tail = siblings[-1]
        for i, sib in enumerate(siblings):
            tree[sib].ob_next = siblings[i + 1] if i + 1 < len(siblings) else p
        return 1

    @classmethod
    def objc_offset(cls, tree: Sequence[GemObject], obj_idx: int) -> tuple[int, int]:
        """Compute absolute screen `(x, y)` of `obj_idx` by summing ancestor offsets."""
        idx = _require_nonbool_int(obj_idx, "obj_idx")
        n = len(tree)
        if not (0 <= idx < n):
            raise IndexError(f"objc_offset index {idx} out of range [0, {n - 1}]")
        parent_of = cls._build_parent_map(tree)
        ax, ay = 0, 0
        cur: int | None = idx
        seen: set[int] = set()
        while cur is not None:
            if cur in seen:
                raise ValueError(f"Cycle detected while computing offset for {idx}")
            seen.add(cur)
            ax += tree[cur].ob_x
            ay += tree[cur].ob_y
            cur = parent_of.get(cur)
        return (ax, ay)

    @classmethod
    def objc_find(
        cls,
        tree: Sequence[GemObject],
        start_obj: int,
        depth: int,
        mx: int,
        my: int,
    ) -> int:
        """Hit-test `(mx, my)` starting at `start_obj` up to `depth`, skipping `HIDETREE`."""
        start = _require_nonbool_int(start_obj, "start_obj")
        max_depth = _require_nonbool_int(depth, "depth")
        x = _require_int16(mx, "mx")
        y = _require_int16(my, "my")
        n = len(tree)
        if not (0 <= start < n):
            raise IndexError(f"objc_find start_obj {start} out of range [0, {n - 1}]")
        if max_depth < 0:
            raise ValueError(f"depth must be >= 0, got {max_depth}")
        cls._build_parent_map(tree)
        base_x, base_y = cls.objc_offset(tree, start)
        start_node = tree[start]
        # Account for root-relative offset when starting at start_obj
        origin_x = base_x - start_node.ob_x
        origin_y = base_y - start_node.ob_y

        found = -1

        def walk(idx: int, cur_depth: int, par_x: int, par_y: int) -> None:
            nonlocal found
            obj = tree[idx]
            if obj.ob_flags & HIDETREE:
                return
            ax = par_x + obj.ob_x
            ay = par_y + obj.ob_y
            if not (ax <= x < ax + obj.ob_w and ay <= y < ay + obj.ob_h):
                return
            found = idx
            if cur_depth >= max_depth or obj.ob_head == NIL:
                return
            child = obj.ob_head
            while child != idx and child != NIL:
                walk(child, cur_depth + 1, ax, ay)
                child = tree[child].ob_next

        walk(start, 0, origin_x, origin_y)
        return found

    @classmethod
    def objc_draw(
        cls,
        tree: Sequence[GemObject],
        start_obj: int,
        depth: int,
        clip_rect: GRECT | Sequence[int],
    ) -> list[dict[str, Any]]:
        """Produce clipped draw commands for visible subtree rooted at `start_obj`."""
        start = _require_nonbool_int(start_obj, "start_obj")
        max_depth = _require_nonbool_int(depth, "depth")
        n = len(tree)
        if not (0 <= start < n):
            raise IndexError(f"objc_draw start_obj {start} out of range [0, {n - 1}]")
        if max_depth < 0:
            raise ValueError(f"depth must be >= 0, got {max_depth}")
        clip = _coerce_grect(clip_rect, "clip_rect", require_nonneg_dims=True)
        if clip.g_w == 0 or clip.g_h == 0:
            return []
        cls._build_parent_map(tree)
        base_x, base_y = cls.objc_offset(tree, start)
        origin_x = base_x - tree[start].ob_x
        origin_y = base_y - tree[start].ob_y
        ops: list[dict[str, Any]] = []

        def walk(idx: int, cur_depth: int, par_x: int, par_y: int) -> None:
            obj = tree[idx]
            if obj.ob_flags & HIDETREE:
                return
            ax = par_x + obj.ob_x
            ay = par_y + obj.ob_y
            obj_rect = GRECT(ax, ay, obj.ob_w, obj.ob_h)
            inter = obj_rect.intersect(clip)
            if inter is not None:
                ops.append(
                    {
                        "obj_idx": idx,
                        "ob_type": obj.ob_type,
                        "ob_type_name": OB_TYPE_NAMES.get(obj.ob_type & 0xFF, str(obj.ob_type)),
                        "ob_flags": obj.ob_flags,
                        "ob_state": obj.ob_state,
                        "abs_rect": list(obj_rect.as_tuple()),
                        "clip_rect": list(inter.as_tuple()),
                        "text": obj.text,
                    }
                )
            if cur_depth >= max_depth or obj.ob_head == NIL:
                return
            child = obj.ob_head
            while child != idx and child != NIL:
                walk(child, cur_depth + 1, ax, ay)
                child = tree[child].ob_next

        walk(start, 0, origin_x, origin_y)
        return ops

    @classmethod
    def objc_change(
        cls,
        tree: list[GemObject],
        obj_idx: int,
        new_state: int,
        *,
        redraw: bool = False,
        clip_rect: GRECT | Sequence[int] | None = None,
    ) -> dict[str, Any]:
        """Update `ob_state` on `obj_idx` and optionally compute redraw ops."""
        idx = _require_nonbool_int(obj_idx, "obj_idx")
        if not (0 <= idx < len(tree)):
            raise IndexError(f"objc_change index {idx} out of range")
        state = _require_nonbool_int(new_state, "new_state") & 0xFFFF
        tree[idx].ob_state = state
        draw_ops: list[dict[str, Any]] = []
        if redraw:
            ax, ay = cls.objc_offset(tree, idx)
            c_rect = (
                _coerce_grect(clip_rect, "clip_rect", require_nonneg_dims=True)
                if clip_rect is not None
                else GRECT(ax, ay, tree[idx].ob_w, tree[idx].ob_h)
            )
            draw_ops = cls.objc_draw(tree, idx, 0, c_rect)
        return {
            "ok": 1,
            "obj_idx": idx,
            "ob_state": state,
            "redrawn": bool(redraw),
            "draw_ops": draw_ops,
        }

    @classmethod
    def to_seasip_tree(
        cls,
        tree: Sequence[GemObject],
        *,
        name: str = "TREE",
    ) -> seasip_gem.GemObjectTree:
        """Convert a canonical `GemObject` list into a `seasip_gem.GemObjectTree`."""
        parent_of = cls.validate_tree(tree)
        root = tree[0]
        stree = seasip_gem.GemObjectTree(name=name, w=root.ob_w, h=root.ob_h)
        stree.objects = [
            seasip_gem.GemObject(
                ob_type=obj.ob_type,
                x=obj.ob_x,
                y=obj.ob_y,
                w=obj.ob_w,
                h=obj.ob_h,
                flags=obj.ob_flags,
                state=obj.ob_state,
                text=obj.text,
                ob_spec=obj.ob_spec,
                parent=parent_of.get(idx, NIL),
                ob_next=obj.ob_next,
                ob_head=obj.ob_head,
                ob_tail=obj.ob_tail,
            )
            for idx, obj in enumerate(tree)
        ]
        return stree

    @staticmethod
    def from_seasip_tree(stree: seasip_gem.GemObjectTree) -> list[GemObject]:
        """Convert a `seasip_gem.GemObjectTree` into a canonical 11-field `GemObject` list."""
        out = [
            GemObject(
                ob_next=obj.ob_next,
                ob_head=obj.ob_head,
                ob_tail=obj.ob_tail,
                ob_type=obj.ob_type,
                ob_flags=obj.flags,
                ob_state=obj.state,
                ob_spec=obj.ob_spec,
                ob_x=obj.x,
                ob_y=obj.y,
                ob_w=obj.w,
                ob_h=obj.h,
                text=obj.text,
            )
            for obj in stree.objects
        ]
        if out:
            for obj in out[:-1]:
                obj.ob_flags &= ~LASTOB
            out[-1].ob_flags |= LASTOB
        return out


def form_center(
    tree: list[GemObject],
    *,
    screen_w: int = 640,
    screen_h: int = 400,
) -> GRECT:
    """Center dialog root `tree[0]` on screen, accounting for `OUTLINED`/`SHADOWED` margin."""
    if not tree:
        raise ValueError("form_center requires a non-empty object tree")
    sw = _require_nonbool_int(screen_w, "screen_w")
    sh = _require_nonbool_int(screen_h, "screen_h")
    root = tree[0]
    root.ob_x = max(0, (sw - root.ob_w) // 2)
    root.ob_y = max(0, (sh - root.ob_h) // 2)
    margin = 3 if (root.ob_state & (OUTLINED | SHADOWED)) else 0
    return GRECT(
        root.ob_x - margin,
        root.ob_y - margin,
        root.ob_w + 2 * margin,
        root.ob_h + 2 * margin,
    )


def form_dial(
    flag: int,
    littlest: GRECT | Sequence[int],
    biggest: GRECT | Sequence[int],
) -> dict[str, Any]:
    """Handle dialog lifecycle reserve/grow/shrink/finish (`FMD_START=0..FMD_FINISH=3`)."""
    f = _require_nonbool_int(flag, "flag")
    names = {
        FMD_START: "FMD_START",
        FMD_GROW: "FMD_GROW",
        FMD_SHRINK: "FMD_SHRINK",
        FMD_FINISH: "FMD_FINISH",
    }
    if f not in names:
        raise ValueError(f"form_dial flag must be in 0..3, got {f}")
    lit = _coerce_grect(littlest, "littlest", require_nonneg_dims=True)
    big = _coerce_grect(biggest, "biggest", require_nonneg_dims=True)
    return {
        "ok": 1,
        "flag": f,
        "flag_name": names[f],
        "littlest": list(lit.as_tuple()),
        "biggest": list(big.as_tuple()),
        "constitutional": constitutional_metadata(epistemic_lane="measurement"),
    }


def form_do(
    tree: list[GemObject],
    start_obj: int,
    events: Sequence[dict[str, Any]] | GemAesApplication,
) -> dict[str, Any]:
    """Execute deterministic GEM dialog interaction loop over `tree`.

    Supports `EDITABLE`, `SELECTABLE`, `RBUTTON` sibling mutual exclusion, `DEFAULT`,
    `EXIT`, `TOUCHEXIT`, `DISABLED`, and `0x8000` double-click exit bit.
    """
    parent_of = GemObjectTreeOps.validate_tree(tree)
    s_obj = _require_nonbool_int(start_obj, "start_obj")
    if s_obj != 0:
        if not (0 <= s_obj < len(tree)):
            raise IndexError(f"form_do start_obj {s_obj} out of range")
        if not (tree[s_obj].ob_flags & EDITABLE):
            raise ValueError(f"form_do start_obj {s_obj} is not EDITABLE")

    focus_obj = s_obj if s_obj > 0 else 0
    if focus_obj == 0:
        for idx, obj in enumerate(tree):
            if (obj.ob_flags & EDITABLE) and not (obj.ob_flags & HIDETREE) and not (obj.ob_state & DISABLED):
                focus_obj = idx
                break

    event_list: list[dict[str, Any]] = []
    if isinstance(events, GemAesApplication):
        while True:
            res = events.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=0)
            if res.message is None:
                break
            event_list.append({"type": "message", "message": res.message})
    else:
        event_list = list(events)

    exit_obj = -1
    double_click = False
    events_processed = 0

    for ev in event_list:
        events_processed += 1
        etype = str(ev.get("type", "click")).lower()
        if etype in ("click", "button", "mouse"):
            if "obj_idx" in ev:
                hit = _require_nonbool_int(ev["obj_idx"], "obj_idx")
                if not (0 <= hit < len(tree)) or (tree[hit].ob_flags & HIDETREE):
                    hit = -1
            else:
                mx = _require_int16(ev.get("x", ev.get("mx", 0)), "mx")
                my = _require_int16(ev.get("y", ev.get("my", 0)), "my")
                hit = GemObjectTreeOps.objc_find(tree, ROOT, MAX_TREE_DEPTH, mx, my)
            if hit < 0:
                continue
            target = tree[hit]
            if target.ob_state & DISABLED:
                continue
            if target.ob_flags & EDITABLE:
                focus_obj = hit
            if target.ob_flags & SELECTABLE:
                if target.ob_flags & RBUTTON:
                    p = parent_of.get(hit)
                    if p is not None:
                        sib = tree[p].ob_head
                        while sib != p and sib != NIL:
                            if tree[sib].ob_flags & RBUTTON:
                                tree[sib].ob_state &= ~SELECTED
                            sib = tree[sib].ob_next
                    target.ob_state |= SELECTED
                elif target.ob_flags & (EXIT | TOUCHEXIT):
                    target.ob_state |= SELECTED
                else:
                    target.ob_state ^= SELECTED
            if target.ob_flags & (EXIT | TOUCHEXIT):
                clicks = _require_nonbool_int(ev.get("clicks", 1), "clicks")
                double_click = clicks >= 2
                exit_obj = hit
                break
        elif etype in ("key", "keybd"):
            key_code = ev.get("key_code")
            ch = ev.get("char")
            is_return = (
                (key_code is not None and _require_nonbool_int(key_code, "key_code") in (0x1C0D, 0x000D, 13))
                or ch in ("\r", "\n")
            )
            if is_return:
                for idx, obj in enumerate(tree):
                    if (
                        (obj.ob_flags & DEFAULT)
                        and not (obj.ob_flags & HIDETREE)
                        and not (obj.ob_state & DISABLED)
                    ):
                        if obj.ob_flags & SELECTABLE:
                            obj.ob_state |= SELECTED
                        exit_obj = idx
                        break
                if exit_obj >= 0:
                    break
            elif focus_obj > 0 and not (tree[focus_obj].ob_state & DISABLED):
                cur_txt = tree[focus_obj].text or ""
                is_bksp = (
                    (key_code is not None and _require_nonbool_int(key_code, "key_code") in (0x0E08, 8))
                    or ch == "\b"
                )
                if is_bksp:
                    tree[focus_obj].text = cur_txt[:-1]
                elif isinstance(ch, str) and len(ch) == 1 and ch.isprintable():
                    tree[focus_obj].text = cur_txt + ch
                elif key_code is not None:
                    ascii_ch = _require_nonbool_int(key_code, "key_code") & 0xFF
                    if 32 <= ascii_ch <= 126:
                        tree[focus_obj].text = cur_txt + chr(ascii_ch)

    exit_raw = (exit_obj | 0x8000) if (exit_obj >= 0 and double_click) else exit_obj
    return {
        "exit_obj": exit_obj,
        "exit_raw": exit_raw,
        "double_click": double_click,
        "focus_obj": focus_obj,
        "events_processed": events_processed,
        "tree_states": [obj.ob_state for obj in tree],
        "tree_texts": {idx: obj.text for idx, obj in enumerate(tree) if obj.text is not None},
        "constitutional": constitutional_metadata(epistemic_lane="measurement"),
    }


def form_alert(
    default_btn: int,
    alert_str: str,
    *,
    button_choice: int | None = None,
) -> dict[str, Any]:
    """Validate and evaluate a GEM `form_alert` string via `seasip_gem.parse_form_alert`."""
    def_btn = _require_nonbool_int(default_btn, "default_btn")
    if not 0 <= def_btn <= 3:
        raise ValueError(f"default_btn must be in 0..3, got {def_btn}")
    parsed = seasip_gem.parse_form_alert(alert_str)
    buttons: list[str] = list(parsed["buttons"])
    chosen = (
        _require_nonbool_int(button_choice, "button_choice")
        if button_choice is not None
        else (def_btn if 1 <= def_btn <= len(buttons) else 1)
    )
    if not 1 <= chosen <= len(buttons):
        raise ValueError(
            f"button_choice {chosen} out of range [1, {len(buttons)}]"
        )
    return {
        "icon": parsed["icon"],
        "icon_name": parsed["icon_name"],
        "lines": list(parsed["lines"]),
        "buttons": buttons,
        "default_button": def_btn,
        "selected_button": chosen,
        "selected_label": buttons[chosen - 1],
        "alert_str": alert_str,
        "constitutional": constitutional_metadata(epistemic_lane="measurement"),
    }


def menu_bar(
    tree: list[GemObject],
    show: int | bool,
    *,
    app: GemAesApplication | None = None,
) -> dict[str, Any]:
    """Install/show (`1`) or erase (`0`) a GEM AES menu bar object tree."""
    GemObjectTreeOps.validate_tree(tree)
    flag = _require_flag_01(show, "show")
    if flag == 0:
        tree[0].ob_flags |= HIDETREE
    else:
        tree[0].ob_flags &= ~HIDETREE
    titles = [
        {"idx": idx, "text": obj.text, "state": obj.ob_state}
        for idx, obj in enumerate(tree)
        if obj.ob_type == G_TITLE
    ]
    return {
        "ok": 1,
        "visible": bool(flag),
        "ap_id": app.ap_id if (app is not None and app.initialized) else None,
        "titles": titles,
        "constitutional": constitutional_metadata(epistemic_lane="measurement"),
    }


def menu_icheck(tree: list[GemObject], item_idx: int, check: int | bool) -> int:
    """Set (`1`) or clear (`0`) `CHECKED` checkmark state on a menu item."""
    idx = _require_nonbool_int(item_idx, "item_idx")
    if not (0 <= idx < len(tree)):
        raise IndexError(f"menu_icheck item_idx {idx} out of range")
    flag = _require_flag_01(check, "check")
    if flag:
        tree[idx].ob_state |= CHECKED
    else:
        tree[idx].ob_state &= ~CHECKED
    return 1


def menu_ienable(tree: list[GemObject], item_idx: int, enable: int | bool) -> int:
    """Enable (`1`, clears `DISABLED`) or disable (`0`, sets `DISABLED`) a menu item."""
    idx = _require_nonbool_int(item_idx, "item_idx")
    if not (0 <= idx < len(tree)):
        raise IndexError(f"menu_ienable item_idx {idx} out of range")
    flag = _require_flag_01(enable, "enable")
    if flag:
        tree[idx].ob_state &= ~DISABLED
    else:
        tree[idx].ob_state |= DISABLED
    return 1


def menu_tnormal(
    tree: list[GemObject],
    title_idx: int,
    normal: int | bool,
    *,
    app: GemAesApplication | None = None,
    item_idx: int = 0,
) -> int:
    """Set menu title normal (`1`, clears `SELECTED`) or highlighted (`0`, sets `SELECTED`).

    When `normal == 0` and `item_idx > 0` and `app` is initialized, verifies the item
    is enabled and emits `MN_SELECTED` (`10`) into `app`.
    """
    t_idx = _require_nonbool_int(title_idx, "title_idx")
    if not (0 <= t_idx < len(tree)):
        raise IndexError(f"menu_tnormal title_idx {t_idx} out of range")
    i_idx = _require_nonbool_int(item_idx, "item_idx")
    if i_idx < 0:
        raise ValueError(f"menu_tnormal item_idx must be >= 0, got {i_idx}")
    flag = _require_flag_01(normal, "normal")
    if flag:
        tree[t_idx].ob_state &= ~SELECTED
    else:
        if tree[t_idx].ob_state & DISABLED:
            raise ValueError(f"Menu title {t_idx} is DISABLED")
        tree[t_idx].ob_state |= SELECTED
        if i_idx > 0:
            if not (0 <= i_idx < len(tree)):
                raise IndexError(f"menu item_idx {i_idx} out of range")
            if tree[i_idx].ob_state & DISABLED:
                raise ValueError(f"Menu item {i_idx} is DISABLED")
            if app is not None and app.initialized:
                app.post_message(MN_SELECTED, app.ap_id, 0, t_idx, i_idx)
    return 1


class GemResourceManager:
    """Clean-room GEM AES `.RSC` Loader (`rsrc_load`, `rsrc_free`, `rsrc_gaddr`, `rsrc_obfix`).

    Supports both Intel x86 little-endian PC GEM `.RSC` (`seasip_gem.compile_rsc`) and
    Motorola 68000 big-endian Atari ST `.RSC` (`zoe_atari_gem_rsc.build_atari_rsc_bytes`).
    """

    def __init__(self) -> None:
        self.loaded: bool = False
        self.endian: str = "<"
        self.header: dict[str, int] = {}
        self.trees: list[list[GemObject]] = []
        self.objects: list[GemObject] = []
        self.tedinfos: list[dict[str, Any]] = []
        self.iconblks: list[dict[str, Any]] = []
        self.bitblks: list[dict[str, Any]] = []
        self.strings: list[str] = []
        self.imagedata: list[bytes] = []
        self.frstrs: list[str] = []
        self.frimgs: list[dict[str, Any]] = []

    def rsrc_load(
        self,
        source: bytes | bytearray | Path | str,
        *,
        apply_obfix: bool = False,
        char_w: int = 8,
        char_h: int = 16,
    ) -> int:
        """Load a binary `.RSC` buffer or read-only file path into memory."""
        if isinstance(source, (bytes, bytearray)):
            data = bytes(source)
        elif isinstance(source, (Path, str)):
            data = Path(source).expanduser().read_bytes()
        else:
            raise ValueError(f"Unsupported .RSC source type: {type(source)!r}")

        if len(data) < 36:
            raise ValueError("RSC data truncated (< 36-byte RSHDR)")
        if len(data) > 0xFFFF:
            raise ValueError(f"RSC exceeds 64 KiB 16-bit limit: {len(data)}")

        le_hdr = struct.unpack_from("<18H", data, 0)
        be_hdr = struct.unpack_from(">18H", data, 0)

        def _is_structurally_valid(cand_endian: str, cand_hdr: tuple[int, ...]) -> bool:
            (
                _vrsn, c_obj, c_ted, c_ib, c_bb, c_frstr,
                _c_str, _c_im, c_frimg, c_tr, c_nobs, c_ntree,
                c_nted, c_nib, c_nbb, c_nstr, c_nimg, c_rssize,
            ) = cand_hdr
            if c_rssize != len(data):
                return False
            if c_obj < 36 or c_tr < 36:
                return False
            if (c_nted > 0 and c_ted < 36) or (c_nib > 0 and c_ib < 36) or (c_nbb > 0 and c_bb < 36):
                return False
            if (c_nstr > 0 and c_frstr < 36) or (c_nimg > 0 and c_frimg < 36):
                return False
            if c_obj + c_nobs * 24 > len(data):
                return False
            if c_tr + c_ntree * 4 > len(data):
                return False
            if c_ted + c_nted * 28 > len(data):
                return False
            if c_ib + c_nib * 34 > len(data):
                return False
            if c_bb + c_nbb * 14 > len(data):
                return False
            if c_frstr + c_nstr * 4 > len(data):
                return False
            if c_frimg + c_nimg * 4 > len(data):
                return False
            cand_obj_s = struct.Struct(cand_endian + "hhhHHHIHHHH")
            cand_ptr_s = struct.Struct(cand_endian + "I")
            for t_i in range(c_ntree):
                t_off = cand_ptr_s.unpack_from(data, c_tr + t_i * 4)[0]
                if t_off < c_obj or (t_off - c_obj) % cand_obj_s.size != 0:
                    return False
                s_idx = (t_off - c_obj) // cand_obj_s.size
                if not (0 <= s_idx < c_nobs):
                    return False
                found_lastob = False
                for o_idx in range(s_idx, c_nobs):
                    o_flags = cand_obj_s.unpack_from(data, c_obj + o_idx * cand_obj_s.size)[4]
                    if o_flags & LASTOB:
                        found_lastob = True
                        break
                if not found_lastob:
                    return False
            for s_i in range(c_nstr):
                s_ptr = cand_ptr_s.unpack_from(data, c_frstr + s_i * 4)[0]
                if not (36 <= s_ptr < len(data)):
                    return False
            for b_i in range(c_nimg):
                b_ptr = cand_ptr_s.unpack_from(data, c_frimg + b_i * 4)[0]
                if b_ptr < 36 or b_ptr + 14 > len(data):
                    return False
            return True

        le_valid = _is_structurally_valid("<", le_hdr)
        be_valid = _is_structurally_valid(">", be_hdr)
        if le_valid:
            endian = "<"
            hdr = le_hdr
        elif be_valid:
            endian = ">"
            hdr = be_hdr
        else:
            le_size_ok = le_hdr[17] == len(data)
            be_size_ok = be_hdr[17] == len(data)
            if le_size_ok and not be_size_ok:
                endian, hdr = "<", le_hdr
            elif be_size_ok and not le_size_ok:
                endian, hdr = ">", be_hdr
            elif le_size_ok and be_size_ok:
                le_off_ok = le_hdr[1] >= 36 and le_hdr[9] >= 36
                be_off_ok = be_hdr[1] >= 36 and be_hdr[9] >= 36
                if be_off_ok and not le_off_ok:
                    endian, hdr = ">", be_hdr
                else:
                    endian, hdr = "<", le_hdr
            else:
                raise ValueError(
                    f"RSC header size/endian mismatch: le={le_hdr[17]}, be={be_hdr[17]}, actual={len(data)}"
                )

        (
            rsh_vrsn, rsh_object, rsh_tedinfo, rsh_iconblk, rsh_bitblk, rsh_frstr,
            rsh_string, rsh_imdata, rsh_frimg, rsh_trindex, rsh_nobs, rsh_ntree,
            rsh_nted, rsh_nib, rsh_nbb, rsh_nstring, rsh_nimages, rsh_rssize,
        ) = hdr

        if rsh_object < 36 or rsh_trindex < 36:
            raise ValueError(
                f"RSC header section offset < 36: rsh_object={rsh_object}, rsh_trindex={rsh_trindex}"
            )
        if rsh_nted > 0 and rsh_tedinfo < 36:
            raise ValueError(f"RSC header rsh_tedinfo < 36: {rsh_tedinfo}")
        if rsh_nib > 0 and rsh_iconblk < 36:
            raise ValueError(f"RSC header rsh_iconblk < 36: {rsh_iconblk}")
        if rsh_nbb > 0 and rsh_bitblk < 36:
            raise ValueError(f"RSC header rsh_bitblk < 36: {rsh_bitblk}")
        if rsh_nstring > 0 and rsh_frstr < 36:
            raise ValueError(f"RSC header rsh_frstr < 36: {rsh_frstr}")
        if rsh_nimages > 0 and rsh_frimg < 36:
            raise ValueError(f"RSC header rsh_frimg < 36: {rsh_frimg}")

        hdr_names = (
            "rsh_vrsn", "rsh_object", "rsh_tedinfo", "rsh_iconblk", "rsh_bitblk",
            "rsh_frstr", "rsh_string", "rsh_imdata", "rsh_frimg", "rsh_trindex",
            "rsh_nobs", "rsh_ntree", "rsh_nted", "rsh_nib", "rsh_nbb",
            "rsh_nstring", "rsh_nimages", "rsh_rssize",
        )
        parsed_header = dict(zip(hdr_names, hdr))

        obj_s = struct.Struct(endian + "hhhHHHIHHHH")
        ted_s = struct.Struct(endian + "IIIhhhhhhhh")
        ib_s = struct.Struct(endian + "3I11h")
        bb_s = struct.Struct(endian + "I5h")
        ptr_s = struct.Struct(endian + "I")

        def read_cstr(offset: int) -> str:
            if not 0 <= offset < len(data):
                return ""
            end = data.find(b"\x00", offset)
            if end == -1:
                end = len(data)
            return data[offset:end].decode("cp437", "replace")

        def read_bytes(offset: int, nbytes: int) -> bytes:
            if nbytes <= 0 or not (0 <= offset < len(data)):
                return b""
            return data[offset : min(len(data), offset + nbytes)]

        strings_seen: list[str] = []
        imagedata_list: list[bytes] = []

        def record_string(s: str) -> None:
            strings_seen.append(s)

        # Parse TEDINFOs
        tedinfos: list[dict[str, Any]] = []
        for i in range(rsh_nted):
            off = rsh_tedinfo + i * ted_s.size
            if off + ted_s.size > len(data):
                raise ValueError(f"TEDINFO {i} truncated")
            (
                te_ptext, te_ptmplt, te_pvalid, te_font, te_junk1, te_just,
                te_color, te_junk2, te_thickness, te_txtlen, te_tmplen,
            ) = ted_s.unpack_from(data, off)
            s_text = read_cstr(te_ptext)
            s_tmplt = read_cstr(te_ptmplt)
            s_valid = read_cstr(te_pvalid)
            record_string(s_text)
            tedinfos.append(
                {
                    "te_ptext_off": te_ptext,
                    "te_ptmplt_off": te_ptmplt,
                    "te_pvalid_off": te_pvalid,
                    "te_ptext": s_text,
                    "te_ptmplt": s_tmplt,
                    "te_pvalid": s_valid,
                    "te_font": te_font,
                    "te_just": te_just,
                    "te_color": te_color,
                    "te_thickness": te_thickness,
                    "te_txtlen": te_txtlen,
                    "te_tmplen": te_tmplen,
                }
            )

        # Parse ICONBLKs
        iconblks: list[dict[str, Any]] = []
        for i in range(rsh_nib):
            off = rsh_iconblk + i * ib_s.size
            if off + ib_s.size > len(data):
                raise ValueError(f"ICONBLK {i} truncated")
            ib = ib_s.unpack_from(data, off)
            pmask_off, pdata_off, ptext_off = ib[0], ib[1], ib[2]
            w_icon, h_icon = ib[8], ib[9]
            byte_len = max(0, ((w_icon + 15) // 16) * 2 * h_icon)
            mask_bytes = read_bytes(pmask_off, byte_len)
            data_bytes = read_bytes(pdata_off, byte_len)
            lbl = read_cstr(ptext_off)
            record_string(lbl)
            imagedata_list.append(data_bytes)
            imagedata_list.append(mask_bytes)
            iconblks.append(
                {
                    "ib_pmask": pmask_off,
                    "ib_pdata": pdata_off,
                    "ib_ptext": ptext_off,
                    "ib_char": ib[3],
                    "ib_xchar": ib[4],
                    "ib_ychar": ib[5],
                    "ib_xicon": ib[6],
                    "ib_yicon": ib[7],
                    "ib_wicon": w_icon,
                    "ib_hicon": h_icon,
                    "ib_xtext": ib[10],
                    "ib_ytext": ib[11],
                    "ib_wtext": ib[12],
                    "ib_htext": ib[13],
                    "mask_bytes": mask_bytes,
                    "data_bytes": data_bytes,
                    "text": lbl,
                }
            )

        # Parse BITBLKs
        bitblks: list[dict[str, Any]] = []
        for i in range(rsh_nbb):
            off = rsh_bitblk + i * bb_s.size
            if off + bb_s.size > len(data):
                raise ValueError(f"BITBLK {i} truncated")
            bi_pdata, bi_wb, bi_hl, bi_x, bi_y, bi_color = bb_s.unpack_from(data, off)
            img_bytes = read_bytes(bi_pdata, max(0, bi_wb * bi_hl))
            imagedata_list.append(img_bytes)
            bitblks.append(
                {
                    "bi_pdata": bi_pdata,
                    "bi_wb": bi_wb,
                    "bi_hl": bi_hl,
                    "bi_x": bi_x,
                    "bi_y": bi_y,
                    "bi_color": bi_color,
                    "data_bytes": img_bytes,
                }
            )

        # Parse flat OBJECTs
        objects: list[GemObject] = []
        for i in range(rsh_nobs):
            off = rsh_object + i * obj_s.size
            if off + obj_s.size > len(data):
                raise ValueError(f"OBJECT {i} truncated")
            nxt, head, tail, otype, flags, state, spec, x, y, w, h = obj_s.unpack_from(data, off)
            low_type = otype & 0xFF
            txt: str | None = None
            if low_type in (G_STRING, G_BUTTON, G_TITLE):
                txt = read_cstr(spec)
                record_string(txt)
            elif low_type in (G_TEXT, G_BOXTEXT, G_FTEXT, G_FBOXTEXT) and spec + ted_s.size <= len(data):
                ptext_off = ptr_s.unpack_from(data, spec)[0]
                txt = read_cstr(ptext_off)
            elif low_type == G_ICON and rsh_iconblk <= spec < rsh_iconblk + rsh_nib * ib_s.size:
                ib_idx = (spec - rsh_iconblk) // ib_s.size
                txt = iconblks[ib_idx]["text"]
            objects.append(
                GemObject(
                    ob_next=nxt,
                    ob_head=head,
                    ob_tail=tail,
                    ob_type=otype,
                    ob_flags=flags,
                    ob_state=state,
                    ob_spec=spec,
                    ob_x=x,
                    ob_y=y,
                    ob_w=w,
                    ob_h=h,
                    text=txt,
                )
            )

        # Parse Tree index table
        trees: list[list[GemObject]] = []
        for t in range(rsh_ntree):
            t_ptr_off = rsh_trindex + t * 4
            if t_ptr_off + 4 > len(data):
                raise ValueError(f"trindex {t} truncated")
            tree_off = ptr_s.unpack_from(data, t_ptr_off)[0]
            if tree_off < rsh_object or (tree_off - rsh_object) % obj_s.size != 0:
                raise ValueError(
                    f"trindex {t} misaligned or before OBJECT table: {tree_off} (rsh_object={rsh_object})"
                )
            start_idx = (tree_off - rsh_object) // obj_s.size
            if not (0 <= start_idx < len(objects)):
                raise ValueError(f"trindex {t} points outside OBJECT table: {tree_off}")
            tree_objs: list[GemObject] = []
            idx = start_idx
            saw_lastob = False
            while idx < len(objects):
                obj = objects[idx]
                tree_objs.append(obj)
                if obj.ob_flags & LASTOB:
                    saw_lastob = True
                    break
                idx += 1
            if not saw_lastob:
                raise ValueError(f"Tree {t} missing LASTOB terminator")
            if apply_obfix:
                for local_i in range(len(tree_objs)):
                    self.rsrc_obfix(tree_objs, local_i, char_w=char_w, char_h=char_h)
            GemObjectTreeOps.validate_tree(tree_objs)
            trees.append(tree_objs)

        # Parse FRSTR & FRIMG tables
        frstrs: list[str] = []
        for i in range(rsh_nstring):
            off = rsh_frstr + i * 4
            if off + 4 > len(data):
                raise ValueError(f"FRSTR {i} truncated")
            str_ptr = ptr_s.unpack_from(data, off)[0]
            if not (36 <= str_ptr < len(data)):
                raise ValueError(f"FRSTR {i} string pointer out of bounds: {str_ptr}")
            frstrs.append(read_cstr(str_ptr))

        frimgs: list[dict[str, Any]] = []
        for i in range(rsh_nimages):
            off = rsh_frimg + i * 4
            if off + 4 > len(data):
                raise ValueError(f"FRIMG {i} truncated")
            bb_ptr = ptr_s.unpack_from(data, off)[0]
            if bb_ptr < 36 or bb_ptr + bb_s.size > len(data):
                raise ValueError(f"FRIMG {i} BITBLK target truncated or out of bounds: {bb_ptr}")
            bi_pdata, bi_wb, bi_hl, bi_x, bi_y, bi_color = bb_s.unpack_from(data, bb_ptr)
            frimgs.append(
                {
                    "bi_pdata": bi_pdata,
                    "bi_wb": bi_wb,
                    "bi_hl": bi_hl,
                    "bi_x": bi_x,
                    "bi_y": bi_y,
                    "bi_color": bi_color,
                    "data_bytes": read_bytes(bi_pdata, max(0, bi_wb * bi_hl)),
                }
            )

        # Fallback: scan string section if no strings were recorded via objects
        if not strings_seen and rsh_string < len(data):
            raw_strs = data[rsh_string : min(len(data), rsh_object)]
            for chunk in raw_strs.split(b"\x00"):
                if chunk:
                    strings_seen.append(chunk.decode("cp437", "replace"))

        self.header = parsed_header
        self.endian = endian
        self.trees = trees
        self.objects = objects
        self.tedinfos = tedinfos
        self.iconblks = iconblks
        self.bitblks = bitblks
        self.strings = strings_seen
        self.imagedata = imagedata_list
        self.frstrs = frstrs
        self.frimgs = frimgs
        self.loaded = True
        return 1

    def rsrc_free(self) -> int:
        """Release currently loaded resource tables. Returns 1 if loaded, 0 if empty."""
        if not self.loaded:
            return 0
        self.loaded = False
        self.header = {}
        self.trees = []
        self.objects = []
        self.tedinfos = []
        self.iconblks = []
        self.bitblks = []
        self.strings = []
        self.imagedata = []
        self.frstrs = []
        self.frimgs = []
        return 1

    def rsrc_gaddr(self, re_gtype: int, re_gindex: int) -> Any:
        """Retrieve resource item by type `0..16` (`R_TREE..R_FRIMG`) and index."""
        if not self.loaded:
            raise RuntimeError("No .RSC resource is currently loaded")
        gtype = _require_nonbool_int(re_gtype, "re_gtype")
        gindex = _require_nonbool_int(re_gindex, "re_gindex")
        if gindex < 0:
            raise IndexError(f"rsrc_gaddr index must be >= 0, got {gindex}")
        if gtype == R_TREE:
            return self.trees[gindex]
        if gtype == R_OBJECT:
            return self.objects[gindex]
        if gtype == R_TEDINFO:
            return self.tedinfos[gindex]
        if gtype == R_ICONBLK:
            return self.iconblks[gindex]
        if gtype == R_BITBLK:
            return self.bitblks[gindex]
        if gtype == R_STRING:
            return self.strings[gindex]
        if gtype == R_IMAGEDATA:
            return self.imagedata[gindex]
        if gtype == R_OBSPEC:
            return self.objects[gindex].ob_spec
        if gtype == R_TEPTEXT:
            return self.tedinfos[gindex]["te_ptext"]
        if gtype == R_TEPTMPLT:
            return self.tedinfos[gindex]["te_ptmplt"]
        if gtype == R_TEPVALID:
            return self.tedinfos[gindex]["te_pvalid"]
        if gtype == R_IBPMASK:
            return self.iconblks[gindex]["mask_bytes"]
        if gtype == R_IBPDATA:
            return self.iconblks[gindex]["data_bytes"]
        if gtype == R_IBPTEXT:
            return self.iconblks[gindex]["text"]
        if gtype == R_BIPDATA:
            return self.bitblks[gindex]["data_bytes"]
        if gtype == R_FRSTR:
            return self.frstrs[gindex]
        if gtype == R_FRIMG:
            return self.frimgs[gindex]
        raise ValueError(f"rsrc_gaddr re_gtype must be in 0..16, got {gtype}")

    @staticmethod
    def rsrc_obfix(
        tree: list[GemObject],
        obj_idx: int,
        char_w: int = 8,
        char_h: int = 16,
    ) -> tuple[int, int, int, int]:
        """Convert packed char+pixel coords (`low=char_units, high=signed_int8_px`) to pixels."""
        idx = _require_nonbool_int(obj_idx, "obj_idx")
        if not (0 <= idx < len(tree)):
            raise IndexError(f"rsrc_obfix index {idx} out of range")
        cw = _require_nonbool_int(char_w, "char_w")
        ch = _require_nonbool_int(char_h, "char_h")

        def fix_coord(val: int, cell: int) -> int:
            uval = val & 0xFFFF
            c_coord = uval & 0xFF
            px_raw = (uval >> 8) & 0xFF
            px_delta = px_raw - 256 if px_raw >= 128 else px_raw
            return c_coord * cell + px_delta

        obj = tree[idx]
        obj.ob_x = fix_coord(obj.ob_x, cw)
        obj.ob_y = fix_coord(obj.ob_y, ch)
        obj.ob_w = fix_coord(obj.ob_w, cw)
        obj.ob_h = fix_coord(obj.ob_h, ch)
        return (obj.ob_x, obj.ob_y, obj.ob_w, obj.ob_h)

    def summary(self) -> dict[str, Any]:
        return {
            "loaded": self.loaded,
            "endian": self.endian,
            "header": dict(self.header),
            "tree_count": len(self.trees),
            "object_count": len(self.objects),
            "tedinfo_count": len(self.tedinfos),
            "iconblk_count": len(self.iconblks),
            "bitblk_count": len(self.bitblks),
            "constitutional": constitutional_metadata(epistemic_lane="measurement"),
        }


_DEFAULT_RSRC_MANAGER = GemResourceManager()


def rsrc_load(
    source: bytes | bytearray | Path | str,
    *,
    apply_obfix: bool = False,
    char_w: int = 8,
    char_h: int = 16,
) -> int:
    return _DEFAULT_RSRC_MANAGER.rsrc_load(
        source, apply_obfix=apply_obfix, char_w=char_w, char_h=char_h
    )


def rsrc_free() -> int:
    return _DEFAULT_RSRC_MANAGER.rsrc_free()


def rsrc_gaddr(re_gtype: int, re_gindex: int) -> Any:
    return _DEFAULT_RSRC_MANAGER.rsrc_gaddr(re_gtype, re_gindex)


def rsrc_obfix(
    tree: list[GemObject],
    obj_idx: int,
    char_w: int = 8,
    char_h: int = 16,
) -> tuple[int, int, int, int]:
    return GemResourceManager.rsrc_obfix(tree, obj_idx, char_w=char_w, char_h=char_h)


# ============================================================================
# Section F — Feature #10: GemVdiStateMachine, Primitives, GDPs & .GEM Metafile
# ============================================================================

def _vdi_index_to_color_name(idx: int) -> str:
    entry = GEM_STANDARD_PALETTE.get(idx)
    if entry is None:
        return "black"
    name, _rgb, hex_str = entry
    if name in _gem_model.COLORS:
        return name
    return hex_str


class GemVdiStateMachine:
    """Clean-room Digital Research GEM VDI Virtual Workstation State Machine (Ch. 3 & 6).

    Supports `v_opnvwk`/`v_clsvwk`, `vq_extnd(0|1)`, NDC (`0..32767`, bottom-left) <->
    RC (`0..max_x, 0..max_y`, top-left) conversion, `vs_clip`, `vswr_mode(1..4)`,
    all attribute setters, all drawing primitives and GDPs, Ch. 6 metafile controls,
    `<24h` + `<4h` + `<-1>` `.GEM` metafile emission, and `Scene` export.
    """

    def __init__(self) -> None:
        self.handle: int = 0
        self.is_open: bool = False
        self.device_id: int = 1
        self.coord_mode: int = RC_MODE
        self.width: int = 640
        self.height: int = 400
        self.work_in: list[int] = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, RC_MODE]
        self.work_out: list[int] = [0] * 57

        # Drawing state
        self.writing_mode: int = MD_REPLACE
        self.clip_enabled: bool = False
        self.clip_rect: tuple[int, int, int, int] = (0, 0, 639, 399)

        # Line attributes
        self.line_type: int = 1
        self.line_width: int = 1
        self.line_color: int = 1
        self.line_ends: tuple[int, int] = (0, 0)

        # Marker attributes
        self.marker_type: int = 3
        self.marker_height: int = 10
        self.marker_color: int = 1

        # Fill attributes
        self.fill_interior: int = FIS_HOLLOW
        self.fill_style: int = 1
        self.fill_color: int = 1
        self.fill_perimeter: int = 1

        # Text attributes
        self.text_font: int = 1
        self.text_color: int = 1
        self.text_height: int = 13
        self.text_point: int = 10
        self.text_rotation: int = 0
        self.text_effects: int = 0
        self.text_alignment: tuple[int, int] = (0, 0)

        # Metafile state (Ch. 6)
        self.metafile_name: str = "GEMFILE.GEM"
        self.meta_page_size: tuple[int, int] = (2540, 1905)
        self.meta_coord_bounds: tuple[int, int, int, int] | None = None
        self.meta_extents: tuple[int, int, int, int] | None = None

        self.commands: list[dict[str, Any]] = []

    def constitutional_metadata(self) -> dict[str, Any]:
        return constitutional_metadata(
            epistemic_lane="measurement", read_only=True, visual_evidence_only=True
        )

    def _require_open(self) -> None:
        if not self.is_open or self.handle <= 0:
            raise RuntimeError("VDI workstation is not open; call v_opnvwk() first")

    def v_opnvwk(
        self,
        work_in: Sequence[int] | None = None,
        *,
        width: int = 640,
        height: int = 400,
    ) -> tuple[int, list[int]]:
        """Open a virtual VDI workstation (`work_in[10]` `0=NDC`, `2=RC`)."""
        w = _require_nonbool_int(width, "width")
        h = _require_nonbool_int(height, "height")
        if w <= 0 or h <= 0 or w > 32767 or h > 32767:
            raise ValueError(f"workstation width/height must be in [1, 32767], got {w}x{h}")

        if work_in is None:
            win = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, RC_MODE]
        else:
            win = [_require_int16(v, "work_in") for v in work_in]
        if len(win) != 11:
            raise ValueError(f"work_in must contain exactly 11 integers, got {len(win)}")
        if win[10] not in (NDC_MODE, RC_MODE):
            raise ValueError(f"work_in[10] coordinate mode must be 0 (NDC) or 2 (RC), got {win[10]}")

        self.handle = 1
        self.is_open = True
        self.device_id = win[0]
        self.work_in = list(win)
        self.width = w
        self.height = h
        self.coord_mode = win[10]

        self.line_type = win[1] if 1 <= win[1] <= 7 else 1
        self.line_width = 1
        self.line_color = win[2] if 0 <= win[2] <= 255 else 1
        self.line_ends = (0, 0)

        self.marker_type = win[3] if 1 <= win[3] <= 6 else 3
        self.marker_height = 10
        self.marker_color = win[4] if 0 <= win[4] <= 255 else 1

        self.text_font = win[5] if win[5] >= 1 else 1
        self.text_color = win[6] if 0 <= win[6] <= 255 else 1
        self.text_height = 13
        self.text_point = 10
        self.text_rotation = 0
        self.text_effects = 0
        self.text_alignment = (0, 0)

        self.fill_interior = win[7] if 0 <= win[7] <= 4 else FIS_HOLLOW
        self.fill_style = win[8] if win[8] >= 1 else 1
        self.fill_color = win[9] if 0 <= win[9] <= 255 else 1
        self.fill_perimeter = 1

        self.writing_mode = MD_REPLACE
        self.clip_enabled = False
        max_x = 32767 if self.coord_mode == NDC_MODE else w - 1
        max_y = 32767 if self.coord_mode == NDC_MODE else h - 1
        self.clip_rect = (0, 0, max_x, max_y)
        self.metafile_name = "GEMFILE.GEM"
        self.meta_page_size = (2540, max(1, round(2540 * h / w)))
        self.meta_coord_bounds = None
        self.meta_extents = None
        self.commands = []

        wout = [0] * 57
        wout[0] = max_x
        wout[1] = max_y
        wout[2] = 0
        wout[3] = 372
        wout[4] = 372
        wout[5] = 1
        wout[6] = 7
        wout[7] = 5
        wout[8] = 6
        wout[9] = 8
        wout[10] = 1
        wout[11] = 24
        wout[12] = 12
        wout[13] = 16
        for i in range(10):
            wout[14 + i] = i + 1
            wout[24 + i] = 3 if i in (0, 2, 3, 4, 6, 8, 9) else 0
        wout[35] = 1
        wout[36] = 1
        wout[37] = 1
        wout[38] = 1
        wout[39] = 16
        wout[40] = 1
        wout[41] = 1
        wout[42] = 1
        wout[43] = 1
        wout[44] = 4 if self.device_id == 31 else 2
        wout[45] = 8
        wout[46] = 8
        wout[47] = 8
        wout[48] = 64
        wout[49] = 1
        wout[50] = 0
        wout[51] = 15
        wout[52] = 0
        wout[53] = 1
        wout[54] = 8
        wout[55] = 16
        wout[56] = 80
        self.work_out = wout
        return (self.handle, list(wout))

    def v_clsvwk(self) -> None:
        """Close the virtual VDI workstation."""
        self.is_open = False
        self.handle = 0

    def vq_extnd(self, owflag: int = 0) -> list[int]:
        """Return 57-element `work_out` (`owflag=0`) or extended capabilities (`owflag=1`)."""
        self._require_open()
        flag = _require_flag_01(owflag, "owflag")
        if flag == 0:
            return list(self.work_out)
        ext = [0] * 57
        ext[0] = 4  # screen / vector workstation
        ext[1] = 16  # background colors
        ext[2] = 0x3F  # text effects mask
        ext[3] = 1  # scaling capable
        ext[4] = 4  # bitplanes
        ext[5] = 1  # LUT supported
        ext[6] = 100  # performance factor
        ext[7] = 1  # contour fill
        ext[8] = 1  # character rotation
        ext[9] = 4  # writing modes
        ext[10] = 2  # highest input mode
        ext[11] = 1  # text alignment
        ext[12] = 1  # inking
        ext[13] = 1  # rubberbanding
        ext[14] = 128  # max vertices
        ext[15] = 128  # max intin
        ext[16] = 4  # mouse buttons
        ext[17] = 1  # wide line types
        ext[18] = 1  # wide line writing modes
        ext[19] = 1 if self.clip_enabled else 0
        ext[20], ext[21], ext[22], ext[23] = self.clip_rect
        return ext

    def ndc_to_rc(self, nx: int, ny: int) -> tuple[int, int]:
        """Convert NDC `(0..32767, bottom-left)` to RC `(0..w-1, 0..h-1, top-left)`."""
        self._require_open()
        x = max(0, min(32767, _require_int16(nx, "nx")))
        y = max(0, min(32767, _require_int16(ny, "ny")))
        max_x = max(0, self.width - 1)
        max_y = max(0, self.height - 1)
        rx = int(round(x * max_x / 32767.0))
        ry = int(round((32767 - y) * max_y / 32767.0))
        return (max(0, min(max_x, rx)), max(0, min(max_y, ry)))

    def rc_to_ndc(self, rx: int, ry: int) -> tuple[int, int]:
        """Convert RC `(0..w-1, 0..h-1, top-left)` to NDC `(0..32767, bottom-left)`."""
        self._require_open()
        max_x = max(0, self.width - 1)
        max_y = max(0, self.height - 1)
        x = max(0, min(max_x, _require_int16(rx, "rx")))
        y = max(0, min(max_y, _require_int16(ry, "ry")))
        nx = 0 if max_x == 0 else int(round(x * 32767.0 / max_x))
        ny = 32767 if max_y == 0 else int(round(32767.0 - (y * 32767.0 / max_y)))
        return (max(0, min(32767, nx)), max(0, min(32767, ny)))

    @staticmethod
    def _rect_to_pxy(rect: Sequence[int] | GRECT) -> tuple[int, int, int, int]:
        if isinstance(rect, GRECT):
            x1, y1, x2, y2 = rect.to_array()
            return (
                _require_int16(x1, "x1"),
                _require_int16(y1, "y1"),
                _require_int16(x2, "x2"),
                _require_int16(y2, "y2"),
            )
        if len(rect) != 4:
            raise ValueError(f"rect must have 4 elements, got {len(rect)}")
        x1 = _require_int16(rect[0], "rect[0]")
        y1 = _require_int16(rect[1], "rect[1]")
        x2 = _require_int16(rect[2], "rect[2]")
        y2 = _require_int16(rect[3], "rect[3]")
        return (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))

    def vs_clip(
        self,
        clip_flag: int,
        rect: Sequence[int] | GRECT = (0, 0, 0, 0),
    ) -> tuple[int, int, int, int]:
        """Enable (`1`) or disable (`0`) VDI clipping rectangle `[x1, y1, x2, y2]`."""
        self._require_open()
        flag = _require_flag_01(clip_flag, "clip_flag")
        pxy = self._rect_to_pxy(rect)
        self.clip_enabled = bool(flag)
        self.clip_rect = pxy
        self.commands.append(
            {
                "opcode": VDI_OP_VS_CLIP,
                "subop": 0,
                "name": "vs_clip",
                "points": [(pxy[0], pxy[1]), (pxy[2], pxy[3])],
                "values": [flag],
            }
        )
        return pxy

    def vswr_mode(self, mode: int) -> int:
        """Set VDI writing mode (`1=MD_REPLACE, 2=MD_TRANS, 3=MD_XOR, 4=MD_ERASE`)."""
        self._require_open()
        m = _require_nonbool_int(mode, "mode")
        if m not in (MD_REPLACE, MD_TRANS, MD_XOR, MD_ERASE):
            raise ValueError(f"vswr_mode must be in 1..4, got {m}")
        self.writing_mode = m
        self.commands.append(
            {"opcode": VDI_OP_VSWR_MODE, "subop": 0, "name": "vswr_mode", "points": [], "values": [m]}
        )
        return m

    # Style setters
    def vsl_type(self, style: int) -> int:
        self._require_open()
        s = _require_nonbool_int(style, "style")
        self.line_type = s if 1 <= s <= 7 else 1
        self.commands.append(
            {"opcode": VDI_OP_VSL_TYPE, "subop": 0, "name": "vsl_type", "points": [], "values": [self.line_type]}
        )
        return self.line_type

    def vsl_width(self, width: int) -> int:
        self._require_open()
        w = max(1, _require_int16(width, "width"))
        self.line_width = w
        self.commands.append(
            {"opcode": VDI_OP_VSL_WIDTH, "subop": 0, "name": "vsl_width", "points": [(w, 0)], "values": []}
        )
        return self.line_width

    def vsl_color(self, color_idx: int) -> int:
        self._require_open()
        c = _require_nonbool_int(color_idx, "color_idx")
        self.line_color = c if 0 <= c <= 255 else 1
        self.commands.append(
            {"opcode": VDI_OP_VSL_COLOR, "subop": 0, "name": "vsl_color", "points": [], "values": [self.line_color]}
        )
        return self.line_color

    def vsl_ends(self, beg_style: int, end_style: int) -> tuple[int, int]:
        self._require_open()
        b = _require_nonbool_int(beg_style, "beg_style")
        e = _require_nonbool_int(end_style, "end_style")
        self.line_ends = (b if 0 <= b <= 2 else 0, e if 0 <= e <= 2 else 0)
        self.commands.append(
            {"opcode": VDI_OP_VSL_ENDS, "subop": 0, "name": "vsl_ends", "points": [], "values": list(self.line_ends)}
        )
        return self.line_ends

    def vsm_type(self, marker_type: int) -> int:
        self._require_open()
        m = _require_nonbool_int(marker_type, "marker_type")
        self.marker_type = m if 1 <= m <= 6 else 3
        self.commands.append(
            {"opcode": VDI_OP_VSM_TYPE, "subop": 0, "name": "vsm_type", "points": [], "values": [self.marker_type]}
        )
        return self.marker_type

    def vsm_height(self, height: int) -> int:
        self._require_open()
        h = max(1, _require_int16(height, "height"))
        self.marker_height = 1 if self.marker_type == 1 else h
        self.commands.append(
            {"opcode": VDI_OP_VSM_HEIGHT, "subop": 0, "name": "vsm_height", "points": [(0, self.marker_height)], "values": []}
        )
        return self.marker_height

    def vsm_color(self, color_idx: int) -> int:
        self._require_open()
        c = _require_nonbool_int(color_idx, "color_idx")
        self.marker_color = c if 0 <= c <= 255 else 1
        self.commands.append(
            {"opcode": VDI_OP_VSM_COLOR, "subop": 0, "name": "vsm_color", "points": [], "values": [self.marker_color]}
        )
        return self.marker_color

    def vsf_interior(self, style: int) -> int:
        self._require_open()
        s = _require_nonbool_int(style, "style")
        self.fill_interior = s if 0 <= s <= 4 else FIS_HOLLOW
        self.commands.append(
            {"opcode": VDI_OP_VSF_INTERIOR, "subop": 0, "name": "vsf_interior", "points": [], "values": [self.fill_interior]}
        )
        return self.fill_interior

    def vsf_style(self, style_idx: int) -> int:
        self._require_open()
        s = max(1, _require_int16(style_idx, "style_idx"))
        self.fill_style = s
        self.commands.append(
            {"opcode": VDI_OP_VSF_STYLE, "subop": 0, "name": "vsf_style", "points": [], "values": [self.fill_style]}
        )
        return self.fill_style

    def vsf_color(self, color_idx: int) -> int:
        self._require_open()
        c = _require_nonbool_int(color_idx, "color_idx")
        self.fill_color = c if 0 <= c <= 255 else 1
        self.commands.append(
            {"opcode": VDI_OP_VSF_COLOR, "subop": 0, "name": "vsf_color", "points": [], "values": [self.fill_color]}
        )
        return self.fill_color

    def vsf_perimeter(self, vis: int | bool) -> int:
        self._require_open()
        v = _require_flag_01(vis, "vis")
        self.fill_perimeter = v
        self.commands.append(
            {"opcode": VDI_OP_VSF_PERIMETER, "subop": 0, "name": "vsf_perimeter", "points": [], "values": [v]}
        )
        return v

    def vst_height(self, height: int) -> tuple[int, int, int, int]:
        self._require_open()
        h = max(1, _require_int16(height, "height"))
        self.text_height = h
        cw = max(1, round(h * 0.62))
        self.commands.append(
            {"opcode": VDI_OP_VST_HEIGHT, "subop": 0, "name": "vst_height", "points": [(0, h)], "values": []}
        )
        return (cw, h, cw + 1, h + 3)

    def vst_point(self, point: int) -> tuple[int, int, int, int]:
        self._require_open()
        pt = max(1, _require_int16(point, "point"))
        self.text_point = pt
        h = max(1, round(pt * 1.3))
        cw = max(1, round(h * 0.62))
        self.text_height = h
        self.commands.append(
            {"opcode": VDI_OP_VST_POINT, "subop": 0, "name": "vst_point", "points": [], "values": [pt]}
        )
        return (cw, h, cw + 1, h + 3)

    def vst_rotation(self, angle: int) -> int:
        self._require_open()
        ang = _require_int16(angle, "angle") % 3600
        self.text_rotation = ang
        self.commands.append(
            {"opcode": VDI_OP_VST_ROTATION, "subop": 0, "name": "vst_rotation", "points": [], "values": [ang]}
        )
        return ang

    def vst_font(self, font_id: int) -> int:
        self._require_open()
        fid = max(1, _require_int16(font_id, "font_id"))
        self.text_font = fid
        self.commands.append(
            {"opcode": VDI_OP_VST_FONT, "subop": 0, "name": "vst_font", "points": [], "values": [fid]}
        )
        return fid

    def vst_color(self, color_idx: int) -> int:
        self._require_open()
        c = _require_nonbool_int(color_idx, "color_idx")
        self.text_color = c if 0 <= c <= 255 else 1
        self.commands.append(
            {"opcode": VDI_OP_VST_COLOR, "subop": 0, "name": "vst_color", "points": [], "values": [self.text_color]}
        )
        return self.text_color

    def vst_effects(self, effect_mask: int) -> int:
        self._require_open()
        mask = _require_nonbool_int(effect_mask, "effect_mask") & 0x3F
        self.text_effects = mask
        self.commands.append(
            {"opcode": VDI_OP_VST_EFFECTS, "subop": 0, "name": "vst_effects", "points": [], "values": [mask]}
        )
        return mask

    def vst_alignment(self, hor_in: int, vert_in: int) -> tuple[int, int]:
        self._require_open()
        h = _require_nonbool_int(hor_in, "hor_in")
        v = _require_nonbool_int(vert_in, "vert_in")
        self.text_alignment = (h if 0 <= h <= 2 else 0, v if 0 <= v <= 5 else 0)
        self.commands.append(
            {
                "opcode": VDI_OP_VST_ALIGNMENT,
                "subop": 0,
                "name": "vst_alignment",
                "points": [],
                "values": list(self.text_alignment),
            }
        )
        return self.text_alignment

    # Drawing primitives & GDPs
    @staticmethod
    def _validate_points(
        pxy: Sequence[tuple[int, int] | Sequence[int]],
        min_pts: int,
        name: str,
    ) -> list[tuple[int, int]]:
        pts = [
            (_require_int16(pt[0], f"{name}.x"), _require_int16(pt[1], f"{name}.y"))
            for pt in pxy
        ]
        if len(pts) < min_pts:
            raise ValueError(f"{name} requires at least {min_pts} points, got {len(pts)}")
        if len(pts) > 32767:
            raise ValueError(f"{name} point count must be <= 32767, got {len(pts)}")
        return pts

    @staticmethod
    def _normalize_angle(angle: int) -> int:
        a = _require_int16(angle, "angle")
        if a == 3600:
            return 3600
        return a % 3600

    def _state_snapshot_attrs(self) -> dict[str, Any]:
        return {
            "writing_mode": self.writing_mode,
            "clip_enabled": self.clip_enabled,
            "clip_rect": self.clip_rect,
            "line_color": self.line_color,
            "line_type": self.line_type,
            "line_width": self.line_width,
            "marker_color": self.marker_color,
            "marker_type": self.marker_type,
            "fill_interior": self.fill_interior,
            "fill_color": self.fill_color,
            "fill_perimeter": self.fill_perimeter,
            "text_color": self.text_color,
            "text_height": self.text_height,
        }

    def v_pline(self, pxy: Sequence[tuple[int, int] | Sequence[int]]) -> dict[str, Any]:
        self._require_open()
        pts = self._validate_points(pxy, 2, "v_pline")
        cmd = {
            "opcode": VDI_OP_PLINE,
            "subop": 0,
            "name": "v_pline",
            "points": pts,
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_pmarker(self, pxy: Sequence[tuple[int, int] | Sequence[int]]) -> dict[str, Any]:
        self._require_open()
        pts = self._validate_points(pxy, 1, "v_pmarker")
        cmd = {
            "opcode": VDI_OP_PMARKER,
            "subop": 0,
            "name": "v_pmarker",
            "points": pts,
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_gtext(self, x: int, y: int, text: str) -> dict[str, Any]:
        self._require_open()
        px = _require_int16(x, "x")
        py = _require_int16(y, "y")
        s = str(text)
        encoded = list(s.encode("cp437", "replace")) + [0]
        if len(encoded) > 32767:
            raise ValueError(f"v_gtext encoded length must be <= 32767, got {len(encoded)}")
        cmd = {
            "opcode": VDI_OP_GTEXT,
            "subop": 0,
            "name": "v_gtext",
            "points": [(px, py)],
            "values": encoded,
            "text": s,
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_fillarea(self, pxy: Sequence[tuple[int, int] | Sequence[int]]) -> dict[str, Any]:
        self._require_open()
        pts = self._validate_points(pxy, 3, "v_fillarea")
        cmd = {
            "opcode": VDI_OP_FILLAREA,
            "subop": 0,
            "name": "v_fillarea",
            "points": pts,
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def vr_recfl(self, rect: Sequence[int] | GRECT) -> dict[str, Any]:
        self._require_open()
        x1, y1, x2, y2 = self._rect_to_pxy(rect)
        cmd = {
            "opcode": VDI_OP_VR_RECFL,
            "subop": 0,
            "name": "vr_recfl",
            "points": [(x1, y1), (x2, y2)],
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_bar(self, rect: Sequence[int] | GRECT) -> dict[str, Any]:
        self._require_open()
        x1, y1, x2, y2 = self._rect_to_pxy(rect)
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_BAR,
            "name": "v_bar",
            "points": [(x1, y1), (x2, y2)],
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_rbox(self, rect: Sequence[int] | GRECT) -> dict[str, Any]:
        self._require_open()
        x1, y1, x2, y2 = self._rect_to_pxy(rect)
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_RBOX,
            "name": "v_rbox",
            "points": [(x1, y1), (x2, y2)],
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_rfbox(self, rect: Sequence[int] | GRECT) -> dict[str, Any]:
        self._require_open()
        x1, y1, x2, y2 = self._rect_to_pxy(rect)
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_RFBOX,
            "name": "v_rfbox",
            "points": [(x1, y1), (x2, y2)],
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_arc(
        self, x: int, y: int, radius: int, begang: int, endang: int
    ) -> dict[str, Any]:
        self._require_open()
        cx, cy = _require_int16(x, "x"), _require_int16(y, "y")
        r = max(1, _require_int16(radius, "radius"))
        beg = self._normalize_angle(begang)
        end = self._normalize_angle(endang)
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_ARC,
            "name": "v_arc",
            "points": [(cx, cy), (r, 0)],
            "values": [beg, end],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_pieslice(
        self, x: int, y: int, radius: int, begang: int, endang: int
    ) -> dict[str, Any]:
        self._require_open()
        cx, cy = _require_int16(x, "x"), _require_int16(y, "y")
        r = max(1, _require_int16(radius, "radius"))
        beg = self._normalize_angle(begang)
        end = self._normalize_angle(endang)
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_PIESLICE,
            "name": "v_pieslice",
            "points": [(cx, cy), (r, 0)],
            "values": [beg, end],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_circle(self, x: int, y: int, radius: int) -> dict[str, Any]:
        self._require_open()
        cx, cy = _require_int16(x, "x"), _require_int16(y, "y")
        r = max(1, _require_int16(radius, "radius"))
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_CIRCLE,
            "name": "v_circle",
            "points": [(cx, cy), (r, r)],
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_ellipse(
        self, x: int, y: int, xradius: int, yradius: int
    ) -> dict[str, Any]:
        self._require_open()
        cx, cy = _require_int16(x, "x"), _require_int16(y, "y")
        rx = max(1, _require_int16(xradius, "xradius"))
        ry = max(1, _require_int16(yradius, "yradius"))
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_ELLIPSE,
            "name": "v_ellipse",
            "points": [(cx, cy), (rx, ry)],
            "values": [],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    def v_ellarc(
        self,
        x: int,
        y: int,
        xradius: int,
        yradius: int,
        begang: int,
        endang: int,
    ) -> dict[str, Any]:
        self._require_open()
        cx, cy = _require_int16(x, "x"), _require_int16(y, "y")
        rx = max(1, _require_int16(xradius, "xradius"))
        ry = max(1, _require_int16(yradius, "yradius"))
        beg = self._normalize_angle(begang)
        end = self._normalize_angle(endang)
        cmd = {
            "opcode": VDI_OP_GDP,
            "subop": GDP_ELLARC,
            "name": "v_ellarc",
            "points": [(cx, cy), (rx, ry)],
            "values": [beg, end],
            "attrs": self._state_snapshot_attrs(),
        }
        self.commands.append(cmd)
        return cmd

    # Chapter 6 Metafile Controls
    def vm_filename(self, filename: str) -> str:
        """Escape 5/100: bind new metafile output name (resets prior command buffer)."""
        self._require_open()
        clean = str(filename or "").strip()
        if not clean:
            raise ValueError("vm_filename requires a non-empty filename")
        encoded = list(clean.encode("cp437", "replace")) + [0]
        if len(encoded) > 32767:
            raise ValueError(f"vm_filename encoded length must be <= 32767, got {len(encoded)}")
        self.metafile_name = clean
        self.commands = [
            {
                "opcode": VDI_OP_ESCAPE,
                "subop": ESC_VM_FILENAME,
                "name": "vm_filename",
                "points": [],
                "values": encoded,
            }
        ]
        return self.metafile_name

    def vm_pagesize(self, page_width_tmm: int, page_height_tmm: int) -> tuple[int, int]:
        """Escape 5/99 (`intin=[0, w, h]`): set metafile physical page size in 0.1 mm."""
        self._require_open()
        pw = max(1, _require_int16(page_width_tmm, "page_width_tmm"))
        ph = max(1, _require_int16(page_height_tmm, "page_height_tmm"))
        self.meta_page_size = (pw, ph)
        self.commands.append(
            {
                "opcode": VDI_OP_ESCAPE,
                "subop": ESC_WRITE_META,
                "name": "vm_pagesize",
                "points": [],
                "values": [0, pw, ph],
            }
        )
        return self.meta_page_size

    def vm_coords(self, llx: int, lly: int, urx: int, ury: int) -> tuple[int, int, int, int]:
        """Escape 5/99 (`intin=[1, llx, lly, urx, ury]`): set metafile coordinate bounds."""
        self._require_open()
        c_llx = _require_int16(llx, "llx")
        c_lly = _require_int16(lly, "lly")
        c_urx = _require_int16(urx, "urx")
        c_ury = _require_int16(ury, "ury")
        if c_urx <= c_llx or c_urx <= 0 or c_ury < 0 or c_ury == c_lly:
            raise ValueError(
                f"vm_coords requires urx > llx, urx > 0, ury >= 0, and ury != lly; "
                f"got ({c_llx}, {c_lly}, {c_urx}, {c_ury})"
            )
        coords = (c_llx, c_lly, c_urx, c_ury)
        self.meta_coord_bounds = coords
        self.commands.append(
            {
                "opcode": VDI_OP_ESCAPE,
                "subop": ESC_WRITE_META,
                "name": "vm_coords",
                "points": [],
                "values": [1, *coords],
            }
        )
        return coords

    def v_meta_extents(self, xmin: int, ymin: int, xmax: int, ymax: int) -> tuple[int, int, int, int]:
        """Escape 5/98: set tight metafile bounding box."""
        self._require_open()
        x1 = _require_int16(xmin, "xmin")
        y1 = _require_int16(ymin, "ymin")
        x2 = _require_int16(xmax, "xmax")
        y2 = _require_int16(ymax, "ymax")
        if x1 > x2 or y1 > y2:
            raise ValueError(
                f"v_meta_extents requires xmin <= xmax and ymin <= ymax; got ({x1}, {y1}, {x2}, {y2})"
            )
        ext = (x1, y1, x2, y2)
        self.meta_extents = ext
        self.commands.append(
            {
                "opcode": VDI_OP_ESCAPE,
                "subop": ESC_META_EXTENTS,
                "name": "v_meta_extents",
                "points": [(ext[0], ext[1]), (ext[2], ext[3])],
                "values": [],
            }
        )
        return ext

    def to_gem_metafile(self) -> bytes:
        """Emit valid `<24h` + `<4h` + `<-1>` `.GEM` VDI metafile bytes."""
        all_xs: list[int] = []
        all_ys: list[int] = []
        for cmd in self.commands:
            for px, py in cmd["points"]:
                all_xs.append(int(px))
                all_ys.append(int(py))
        if self.meta_extents is not None:
            min_x, min_y, max_x, max_y = self.meta_extents
        elif all_xs and all_ys:
            min_x, min_y, max_x, max_y = min(all_xs), min(all_ys), max(all_xs), max(all_ys)
        else:
            min_x = min_y = max_x = max_y = 0

        if self.meta_coord_bounds is not None:
            cx1, cy1, cx2, cy2 = self.meta_coord_bounds
        elif self.coord_mode == NDC_MODE:
            cx1, cy1, cx2, cy2 = (0, 0, 32767, 32767)
        else:
            cx1, cy1, cx2, cy2 = (0, 0, max(1, self.width - 1), max(1, self.height - 1))

        header_words = [
            -1,
            24,
            101,
            self.coord_mode,
            min_x,
            min_y,
            max_x,
            max_y,
            self.meta_page_size[0],
            self.meta_page_size[1],
            cx1,
            cy1,
            cx2,
            cy2,
            0,
            *([0] * 9),
        ]
        records: list[bytes] = []
        for cmd in self.commands:
            opcode = int(cmd["opcode"])
            # App. F: vr_recfl is raster-only; represent in metafile as perimeter-less v_bar
            subop = int(cmd["subop"])
            if opcode == VDI_OP_VR_RECFL:
                opcode = VDI_OP_GDP
                subop = GDP_BAR
            pts: list[tuple[int, int]] = list(cmd["points"])
            vals: list[int] = list(cmd["values"])
            if len(pts) > 32767 or len(vals) > 32767:
                raise ValueError(
                    f"VDI metafile command {cmd.get('name', opcode)!r} exceeds 16-bit count limit "
                    f"(pts={len(pts)}, vals={len(vals)})"
                )
            flat_pts = [c for pt in pts for c in pt]
            rec = (
                struct.pack("<4h", opcode, len(pts), len(vals), subop)
                + (struct.pack(f"<{len(flat_pts)}h", *flat_pts) if flat_pts else b"")
                + (struct.pack(f"<{len(vals)}h", *vals) if vals else b"")
            )
            records.append(rec)

        data = struct.pack("<24h", *header_words) + b"".join(records) + struct.pack("<h", -1)
        # Self-check framing via vdi.parse_metafile & seasip_gem
        _parse_vdi_metafile(data)
        seasip_gem.verify_seasip_gem_metafile(data)
        return data

    @staticmethod
    def _dedup_consecutive_points(pts: Sequence[Sequence[float]]) -> list[list[float]]:
        cleaned: list[list[float]] = []
        for pt in pts:
            fx, fy = float(pt[0]), float(pt[1])
            if not cleaned or abs(cleaned[-1][0] - fx) > 1e-9 or abs(cleaned[-1][1] - fy) > 1e-9:
                cleaned.append([fx, fy])
        return cleaned

    @classmethod
    def _clean_polygon_points(cls, pts: Sequence[Sequence[float]]) -> list[list[float]]:
        cleaned = cls._dedup_consecutive_points(pts)
        if (
            len(cleaned) >= 2
            and abs(cleaned[0][0] - cleaned[-1][0]) <= 1e-9
            and abs(cleaned[0][1] - cleaned[-1][1]) <= 1e-9
        ):
            cleaned.pop()
        if len(cleaned) < 3:
            return []
        n = len(cleaned)
        area2 = abs(
            sum(
                cleaned[i][0] * cleaned[(i + 1) % n][1]
                - cleaned[(i + 1) % n][0] * cleaned[i][1]
                for i in range(n)
            )
        )
        if area2 <= 1e-6:
            return []
        return cleaned

    @staticmethod
    def _clip_segment_liang_barsky(
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        cx1: float,
        cy1: float,
        cx2: float,
        cy2: float,
    ) -> tuple[tuple[float, float], tuple[float, float]] | None:
        if cx2 < cx1 or cy2 < cy1:
            return None
        dx = x1 - x0
        dy = y1 - y0
        if dx == 0.0 and dy == 0.0:
            if cx1 <= x0 <= cx2 and cy1 <= y0 <= cy2:
                return ((x0, y0), (x1, y1))
            return None
        t0 = 0.0
        t1 = 1.0
        for p, q in (
            (-dx, x0 - cx1),
            (dx, cx2 - x0),
            (-dy, y0 - cy1),
            (dy, cy2 - y0),
        ):
            if p == 0.0:
                if q < 0.0:
                    return None
            else:
                r = q / p
                if p < 0.0:
                    if r > t1:
                        return None
                    if r > t0:
                        t0 = r
                else:
                    if r < t0:
                        return None
                    if r < t1:
                        t1 = r
        if t0 > t1:
            return None
        nx0 = max(cx1, min(cx2, x0 + t0 * dx))
        ny0 = max(cy1, min(cy2, y0 + t0 * dy))
        nx1 = max(cx1, min(cx2, x0 + t1 * dx))
        ny1 = max(cy1, min(cy2, y0 + t1 * dy))
        if abs(nx1 - nx0) <= 1e-9 and abs(ny1 - ny0) <= 1e-9:
            return None
        return ((nx0, ny0), (nx1, ny1))

    @classmethod
    def _clip_polyline_segments(
        cls,
        pts: Sequence[Sequence[float]],
        cx1: float,
        cy1: float,
        cx2: float,
        cy2: float,
        *,
        round_ndc: bool = False,
    ) -> list[list[list[float]]]:
        runs: list[list[list[float]]] = []
        current_run: list[list[float]] = []

        def _flush_run(run: list[list[float]]) -> None:
            if len(run) < 2:
                return
            dedup: list[list[float]] = []
            for pt in run:
                if not dedup or abs(dedup[-1][0] - pt[0]) > 1e-9 or abs(dedup[-1][1] - pt[1]) > 1e-9:
                    dedup.append(pt)
            if len(dedup) >= 2:
                runs.append(dedup)

        for idx in range(len(pts) - 1):
            seg = cls._clip_segment_liang_barsky(
                float(pts[idx][0]),
                float(pts[idx][1]),
                float(pts[idx + 1][0]),
                float(pts[idx + 1][1]),
                cx1,
                cy1,
                cx2,
                cy2,
            )
            if seg is None:
                _flush_run(current_run)
                current_run = []
                continue
            (sx0, sy0), (sx1, sy1) = seg
            if round_ndc:
                sx0 = max(cx1, min(cx2, round(sx0, 2)))
                sy0 = max(cy1, min(cy2, round(sy0, 2)))
                sx1 = max(cx1, min(cx2, round(sx1, 2)))
                sy1 = max(cy1, min(cy2, round(sy1, 2)))
            if abs(sx1 - sx0) <= 1e-9 and abs(sy1 - sy0) <= 1e-9:
                continue
            if not current_run:
                current_run = [[sx0, sy0], [sx1, sy1]]
            elif abs(current_run[-1][0] - sx0) <= 1e-6 and abs(current_run[-1][1] - sy0) <= 1e-6:
                if abs(current_run[-1][0] - sx1) > 1e-9 or abs(current_run[-1][1] - sy1) > 1e-9:
                    current_run.append([sx1, sy1])
            else:
                _flush_run(current_run)
                current_run = [[sx0, sy0], [sx1, sy1]]
        _flush_run(current_run)
        return runs

    @staticmethod
    def _clip_polygon_sutherland_hodgman(
        pts: Sequence[Sequence[float]],
        cx1: float,
        cy1: float,
        cx2: float,
        cy2: float,
        *,
        round_ndc: bool = False,
    ) -> list[list[float]]:
        if cx2 <= cx1 or cy2 <= cy1 or len(pts) < 3:
            return []
        output: list[tuple[float, float]] = [(float(p[0]), float(p[1])) for p in pts]
        edges: tuple[tuple[str, float], ...] = (
            ("left", cx1),
            ("right", cx2),
            ("top", cy1),
            ("bottom", cy2),
        )

        def inside(pt: tuple[float, float], edge: str, val: float) -> bool:
            if edge == "left":
                return pt[0] >= val
            if edge == "right":
                return pt[0] <= val
            if edge == "top":
                return pt[1] >= val
            return pt[1] <= val

        def intersect(
            a: tuple[float, float],
            b: tuple[float, float],
            edge: str,
            val: float,
        ) -> tuple[float, float]:
            ax, ay = a
            bx, by = b
            if edge in ("left", "right"):
                dx = bx - ax
                if abs(dx) <= 1e-12:
                    return (val, ay)
                t = (val - ax) / dx
                return (val, ay + t * (by - ay))
            dy = by - ay
            if abs(dy) <= 1e-12:
                return (ax, val)
            t = (val - ay) / dy
            return (ax + t * (bx - ax), val)

        for edge, val in edges:
            if not output:
                break
            inp = output
            output = []
            prev = inp[-1]
            for curr in inp:
                curr_in = inside(curr, edge, val)
                prev_in = inside(prev, edge, val)
                if curr_in:
                    if not prev_in:
                        output.append(intersect(prev, curr, edge, val))
                    output.append(curr)
                elif prev_in:
                    output.append(intersect(prev, curr, edge, val))
                prev = curr

        cleaned: list[list[float]] = []
        for px, py in output:
            rx = round(px, 2) if round_ndc else px
            ry = round(py, 2) if round_ndc else py
            cx = max(cx1, min(cx2, rx))
            cy = max(cy1, min(cy2, ry))
            if not cleaned or abs(cleaned[-1][0] - cx) > 1e-9 or abs(cleaned[-1][1] - cy) > 1e-9:
                cleaned.append([cx, cy])
        if (
            len(cleaned) >= 2
            and abs(cleaned[0][0] - cleaned[-1][0]) <= 1e-9
            and abs(cleaned[0][1] - cleaned[-1][1]) <= 1e-9
        ):
            cleaned.pop()
        if len(cleaned) < 3:
            return []
        n = len(cleaned)
        area2 = abs(
            sum(
                cleaned[i][0] * cleaned[(i + 1) % n][1]
                - cleaned[(i + 1) % n][0] * cleaned[i][1]
                for i in range(n)
            )
        )
        if area2 <= 1e-6:
            return []
        return cleaned

    def to_scene(self, scene_id: str = "gem-vdi-state-scene") -> Any:
        """Convert recorded VDI primitives into a verified `guiai.gem.model.Scene`."""
        canvas_w = float(self.width)
        canvas_h = float(self.height)
        max_x = max(1.0, canvas_w - 1.0)
        max_y = max(1.0, canvas_h - 1.0)
        is_ndc = self.coord_mode == NDC_MODE

        def map_pt(px: int, py: int) -> list[float]:
            if is_ndc:
                rx = round(max(0, min(32767, px)) * max_x / 32767.0, 2)
                ry = round((32767 - max(0, min(32767, py))) * max_y / 32767.0, 2)
                return [rx, ry]
            return [float(px), float(py)]

        def map_pt_linear(px: int, py: int) -> list[float]:
            if is_ndc:
                rx = px * max_x / 32767.0
                ry = (32767 - py) * max_y / 32767.0
                return [rx, ry]
            return [float(px), float(py)]

        objects: list[dict[str, Any]] = []
        constraints: list[dict[str, Any]] = []
        obj_counter = 0

        for cmd in self.commands:
            op = int(cmd["opcode"])
            sub = int(cmd["subop"])
            attrs = cmd.get("attrs") or {}
            line_col = _vdi_index_to_color_name(int(attrs.get("line_color", self.line_color)))
            fill_int = int(attrs.get("fill_interior", self.fill_interior))
            fill_col = (
                _vdi_index_to_color_name(int(attrs.get("fill_color", self.fill_color)))
                if fill_int != FIS_HOLLOW
                else "none"
            )
            text_col = _vdi_index_to_color_name(int(attrs.get("text_color", self.text_color)))

            clip_bounds: tuple[float, float, float, float] | None = None
            if bool(attrs.get("clip_enabled", False)):
                raw_clip = attrs.get("clip_rect", self.clip_rect)
                cp1 = map_pt(int(raw_clip[0]), int(raw_clip[1]))
                cp2 = map_pt(int(raw_clip[2]), int(raw_clip[3]))
                clip_bounds = (
                    min(cp1[0], cp2[0]),
                    min(cp1[1], cp2[1]),
                    max(cp1[0], cp2[0]),
                    max(cp1[1], cp2[1]),
                )

            obj_counter += 1
            oid = f"vdi-{obj_counter}"

            if op == VDI_OP_PLINE and len(cmd["points"]) >= 2:
                if clip_bounds is not None:
                    raw_pts = [map_pt_linear(x, y) for x, y in cmd["points"]]
                    runs = self._clip_polyline_segments(
                        raw_pts, *clip_bounds, round_ndc=is_ndc
                    )
                    for run_idx, run in enumerate(runs):
                        run_id = oid if len(runs) == 1 else f"{oid}-s{run_idx}"
                        otype = "line" if len(run) == 2 else "polyline"
                        objects.append(
                            {
                                "id": run_id,
                                "type": otype,
                                "points": run,
                                "fill": "none",
                                "stroke": line_col,
                            }
                        )
                else:
                    pts = self._dedup_consecutive_points([map_pt(x, y) for x, y in cmd["points"]])
                    if len(pts) < 2:
                        continue
                    otype = "line" if len(pts) == 2 else "polyline"
                    objects.append(
                        {"id": oid, "type": otype, "points": pts, "fill": "none", "stroke": line_col}
                    )
            elif op == VDI_OP_FILLAREA and len(cmd["points"]) >= 3:
                if clip_bounds is not None:
                    raw_pts = [map_pt_linear(x, y) for x, y in cmd["points"]]
                    pts = self._clip_polygon_sutherland_hodgman(
                        raw_pts, *clip_bounds, round_ndc=is_ndc
                    )
                else:
                    pts = self._clean_polygon_points([map_pt(x, y) for x, y in cmd["points"]])
                if not pts:
                    continue
                objects.append(
                    {
                        "id": oid,
                        "type": "polygon",
                        "points": pts,
                        "fill": fill_col,
                        "stroke": line_col,
                    }
                )
            elif op == VDI_OP_VR_RECFL or (op == VDI_OP_GDP and sub in (GDP_BAR, GDP_RBOX, GDP_RFBOX)):
                p1 = map_pt_linear(*cmd["points"][0]) if clip_bounds is not None else map_pt(*cmd["points"][0])
                p2 = map_pt_linear(*cmd["points"][1]) if clip_bounds is not None else map_pt(*cmd["points"][1])
                rx1 = min(p1[0], p2[0])
                ry1 = min(p1[1], p2[1])
                rx2 = max(p1[0], p2[0])
                ry2 = max(p1[1], p2[1])
                if clip_bounds is not None:
                    cx1, cy1, cx2, cy2 = clip_bounds
                    rx1 = max(rx1, cx1)
                    ry1 = max(ry1, cy1)
                    rx2 = min(rx2, cx2)
                    ry2 = min(ry2, cy2)
                    if rx2 <= rx1 or ry2 <= ry1:
                        continue
                    if is_ndc:
                        rx1 = max(cx1, min(cx2, round(rx1, 2)))
                        ry1 = max(cy1, min(cy2, round(ry1, 2)))
                        rx2 = max(cx1, min(cx2, round(rx2, 2)))
                        ry2 = max(cy1, min(cy2, round(ry2, 2)))
                        if rx2 <= rx1 or ry2 <= ry1:
                            continue
                bounds = [rx1, ry1, rx2, ry2]
                is_outlined_only = sub == GDP_RBOX
                rect_fill = "none" if is_outlined_only else fill_col
                objects.append(
                    {
                        "id": oid,
                        "type": "rectangle",
                        "bounds": bounds,
                        "fill": rect_fill,
                        "stroke": "none" if op == VDI_OP_VR_RECFL else line_col,
                    }
                )
            elif op == VDI_OP_GDP and sub in (GDP_CIRCLE, GDP_ELLIPSE):
                c = map_pt_linear(*cmd["points"][0]) if clip_bounds is not None else map_pt(*cmd["points"][0])
                rx_raw, ry_raw = cmd["points"][1]
                if is_ndc:
                    rx = max(1.0, round(rx_raw * max_x / 32767.0, 2))
                    ry = max(1.0, round(ry_raw * max_y / 32767.0, 2))
                else:
                    rx = float(max(1, rx_raw))
                    ry = float(max(1, ry_raw))
                if clip_bounds is not None:
                    cx1, cy1, cx2, cy2 = clip_bounds
                    if cx2 <= cx1 or cy2 <= cy1:
                        continue
                    qx = min(max(c[0], cx1), cx2)
                    qy = min(max(c[1], cy1), cy2)
                    if ((qx - c[0]) / rx) ** 2 + ((qy - c[1]) / ry) ** 2 > 1.0 + 1e-12:
                        continue
                    ex1, ey1, ex2, ey2 = c[0] - rx, c[1] - ry, c[0] + rx, c[1] + ry
                    ix1 = max(ex1, cx1)
                    iy1 = max(ey1, cy1)
                    ix2 = min(ex2, cx2)
                    iy2 = min(ey2, cy2)
                    if ix2 <= ix1 or iy2 <= iy1:
                        continue
                    if ix1 > ex1 or iy1 > ey1 or ix2 < ex2 or iy2 < ey2:
                        ncx = (ix1 + ix2) / 2.0
                        ncy = (iy1 + iy2) / 2.0
                        nrx = min((ix2 - ix1) / 2.0, ncx - cx1, cx2 - ncx)
                        nry = min((iy2 - iy1) / 2.0, ncy - cy1, cy2 - ncy)
                    else:
                        ncx, ncy, nrx, nry = c[0], c[1], rx, ry
                    rcx = int(round(ncx))
                    rcy = int(round(ncy))
                    max_rt_rx = min(float(rcx) - cx1, cx2 - float(rcx))
                    max_rt_ry = min(float(rcy) - cy1, cy2 - float(rcy))
                    nrx = min(nrx, max_rt_rx)
                    nry = min(nry, max_rt_ry)
                    if int(round(nrx)) > max_rt_rx:
                        nrx = float(math.floor(max_rt_rx))
                    if int(round(nry)) > max_rt_ry:
                        nry = float(math.floor(max_rt_ry))
                    if nrx <= 0.5 or nry <= 0.5 or int(round(nrx)) <= 0 or int(round(nry)) <= 0:
                        continue
                    c = [ncx, ncy]
                    rx, ry = nrx, nry
                if int(round(rx)) <= 0 or int(round(ry)) <= 0:
                    continue
                objects.append(
                    {
                        "id": oid,
                        "type": "ellipse",
                        "center": c,
                        "radii": [rx, ry],
                        "fill": fill_col,
                        "stroke": line_col,
                    }
                )
            elif op == VDI_OP_GDP and sub in (GDP_ARC, GDP_PIESLICE, GDP_ELLARC):
                cx, cy = cmd["points"][0]
                rx_raw, ry_raw = cmd["points"][1]
                if sub in (GDP_ARC, GDP_PIESLICE):
                    ry_raw = rx_raw
                beg, end = cmd["values"][0], cmd["values"][1]
                span = (end - beg) % 3600
                if span == 0:
                    span = 3600
                steps = max(4, min(24, span // 150))
                pt_mapper = map_pt_linear if clip_bounds is not None else map_pt
                arc_pts: list[list[float]] = []
                if sub == GDP_PIESLICE:
                    arc_pts.append(pt_mapper(cx, cy))
                for step in range(steps + 1):
                    ang_deg = (beg + span * (step / steps)) / 10.0
                    rad = math.radians(ang_deg)
                    px = round(cx + rx_raw * math.cos(rad))
                    py = round(cy + ry_raw * math.sin(rad))
                    if clip_bounds is None and not is_ndc:
                        px = max(-32767, min(32767, px))
                        py = max(-32767, min(32767, py))
                    arc_pts.append(pt_mapper(px, py))
                if sub == GDP_PIESLICE:
                    if clip_bounds is not None:
                        arc_pts = self._clip_polygon_sutherland_hodgman(
                            arc_pts, *clip_bounds, round_ndc=is_ndc
                        )
                    else:
                        arc_pts = self._clean_polygon_points(arc_pts)
                    if not arc_pts:
                        continue
                    objects.append(
                        {"id": oid, "type": "polygon", "points": arc_pts, "fill": fill_col, "stroke": line_col}
                    )
                else:
                    arc_pts = self._dedup_consecutive_points(arc_pts)
                    if len(arc_pts) < 2:
                        continue
                    if clip_bounds is not None:
                        runs = self._clip_polyline_segments(
                            arc_pts, *clip_bounds, round_ndc=is_ndc
                        )
                        for run_idx, run in enumerate(runs):
                            run_id = oid if len(runs) == 1 else f"{oid}-s{run_idx}"
                            otype = "line" if len(run) == 2 else "polyline"
                            objects.append(
                                {"id": run_id, "type": otype, "points": run, "fill": "none", "stroke": line_col}
                            )
                    else:
                        otype = "line" if len(arc_pts) == 2 else "polyline"
                        objects.append(
                            {"id": oid, "type": otype, "points": arc_pts, "fill": "none", "stroke": line_col}
                        )
            elif op == VDI_OP_GTEXT:
                pos = map_pt_linear(*cmd["points"][0]) if clip_bounds is not None else map_pt(*cmd["points"][0])
                txt = (str(cmd.get("text", "GEM")) or "GEM")[:500]
                sz = float(max(1, int(attrs.get("text_height", self.text_height))))
                if clip_bounds is not None:
                    cx1, cy1, cx2, cy2 = clip_bounds
                    tx1 = pos[0]
                    ty1 = pos[1] - sz
                    tx2 = pos[0] + len(txt) * sz * 0.62
                    ty2 = pos[1]
                    ix1 = max(tx1, cx1)
                    iy1 = max(ty1, cy1)
                    ix2 = min(tx2, cx2)
                    iy2 = min(ty2, cy2)
                    if ix2 <= ix1 or iy2 <= iy1:
                        continue
                    rx_rt = int(round(tx1))
                    ry_rt = int(round(ty2))
                    sz_rt = max(1, int(round(sz)))
                    eff_orig_sz = max(sz, float(sz_rt))
                    needs_clip = (
                        ix1 > tx1
                        or iy1 > ty1
                        or ix2 < tx2
                        or iy2 < ty2
                        or rx_rt < cx1
                        or (ry_rt - eff_orig_sz) < cy1
                        or (rx_rt + len(txt) * eff_orig_sz * 0.62) > cx2
                        or ry_rt > cy2
                    )
                    if needs_clip:
                        low_x = max(0.0, cx1)
                        low_y = max(0.0, cy1)
                        high_x = min(canvas_w, cx2)
                        high_y = min(canvas_h, cy2)
                        if high_x <= low_x or high_y <= low_y:
                            continue
                        rx_pos = max(int(round(ix1)), int(math.ceil(low_x)))
                        ry_pos = min(int(round(iy2)), int(math.floor(high_y)))
                        if (
                            rx_pos < low_x
                            or rx_pos >= high_x
                            or ry_pos < 1
                            or ry_pos <= low_y
                            or ry_pos > high_y
                        ):
                            continue
                        avail_w = min(ix2, high_x) - float(rx_pos)
                        max_sz_y = min(iy2, float(ry_pos)) - low_y
                        new_sz = min(iy2 - iy1, max_sz_y)
                        if new_sz < 0.5 or avail_w <= 0.0:
                            continue
                        char_w_orig = sz * 0.62
                        start_char = min(
                            len(txt) - 1,
                            max(0, int(math.floor((float(rx_pos) - tx1) / char_w_orig))),
                        )
                        sub_txt = txt[start_char:] or txt[:1]
                        char_w_new = new_sz * 0.62
                        max_chars = int(math.floor(avail_w / char_w_new + 1e-12))
                        if max_chars >= 1:
                            txt = sub_txt[:max_chars]
                        else:
                            txt = sub_txt[:1]
                            new_sz = min(new_sz, avail_w / 0.62)
                        if float(ry_pos) - float(int(round(new_sz))) < low_y:
                            new_sz = float(math.floor(float(ry_pos) - low_y))
                        while new_sz >= 0.5 and txt:
                            eff_sz = max(new_sz, float(int(round(new_sz))))
                            if (
                                float(ry_pos) - eff_sz >= low_y
                                and float(rx_pos) + len(txt) * eff_sz * 0.62 <= high_x
                            ):
                                break
                            if len(txt) > 1:
                                txt = txt[:-1]
                            else:
                                max_w_sz = avail_w / 0.62
                                if float(rx_pos) + max_w_sz * 0.62 > high_x:
                                    max_w_sz = math.nextafter(max_w_sz, 0.0)
                                if int(round(max_w_sz)) > max_w_sz:
                                    max_w_sz = float(math.floor(max_w_sz))
                                new_sz = min(new_sz, max_w_sz)
                                eff_sz = max(new_sz, float(int(round(new_sz))))
                                if (
                                    new_sz >= 0.5
                                    and float(ry_pos) - eff_sz >= low_y
                                    and float(rx_pos) + eff_sz * 0.62 <= high_x
                                ):
                                    break
                                new_sz = 0.0
                                break
                        if new_sz < 0.5 or int(round(new_sz)) < 1 or not txt:
                            continue
                        pos = [float(rx_pos), float(ry_pos)]
                        sz = float(new_sz)
                objects.append(
                    {
                        "id": oid,
                        "type": "text",
                        "position": pos,
                        "text": txt,
                        "size": sz,
                        "fill": "none",
                        "stroke": text_col,
                    }
                )
            elif op == VDI_OP_PMARKER:
                if clip_bounds is not None and (
                    clip_bounds[2] <= clip_bounds[0] or clip_bounds[3] <= clip_bounds[1]
                ):
                    continue
                for pt_i, (mx, my) in enumerate(cmd["points"]):
                    p = map_pt_linear(mx, my) if clip_bounds is not None else map_pt(mx, my)
                    if clip_bounds is not None:
                        cx1, cy1, cx2, cy2 = clip_bounds
                        if not (cx1 <= p[0] <= cx2 and cy1 <= p[1] <= cy2):
                            continue
                        if is_ndc:
                            p = [max(cx1, min(cx2, round(p[0], 2))), max(cy1, min(cy2, round(p[1], 2)))]
                        x_left = max(cx1, p[0] - 2)
                        x_right = min(cx2, p[0] + 2)
                    else:
                        x_left = max(0.0, p[0] - 2)
                        x_right = min(canvas_w, p[0] + 2)
                    if x_right - x_left <= 1e-9:
                        continue
                    objects.append(
                        {
                            "id": f"{oid}-m{pt_i}",
                            "type": "line",
                            "points": [[x_left, p[1]], [x_right, p[1]]],
                            "fill": "none",
                            "stroke": _vdi_index_to_color_name(int(attrs.get("marker_color", self.marker_color))),
                        }
                    )

        if objects:
            all_inside = True
            for item in objects:
                b = _gem_geometry.object_bounds(item)  # type: ignore[no-untyped-call]
                if b.left < 0 or b.top < 0 or b.right > canvas_w or b.bottom > canvas_h:
                    all_inside = False
                    break
            if all_inside:
                constraints.append({"type": "inside_canvas", "object": "*"})

        doc = {
            "schema_version": 1,
            "id": str(scene_id),
            "title": "Zoe GEM VDI State Machine Scene",
            "canvas": {"width": canvas_w, "height": canvas_h},
            "objects": objects,
            "constraints": constraints,
        }
        return _scene_from_dict(doc)

    @staticmethod
    def _scene_has_out_of_int16_bounds(scene: Any) -> bool:
        for item in scene.objects:
            b = _gem_geometry.object_bounds(item)  # type: ignore[no-untyped-call]
            if b.left < -32768 or b.top < -32768 or b.right > 32767 or b.bottom > 32767:
                return True
        return False

    def verify_scene_and_metafile(self, scene_id: str = "gem-vdi-state-scene") -> dict[str, Any]:
        """Verify both `.GEM` metafile framing and `Scene` spatial/VDI round-trip."""
        meta_bytes = self.to_gem_metafile()
        seasip_res = seasip_gem.verify_seasip_gem_metafile(meta_bytes)
        scene = self.to_scene(scene_id=scene_id)
        geom_report = _verify_geometry(scene)
        has_unclipped_commands = any(
            not bool((cmd.get("attrs") or {}).get("clip_enabled", False))
            for cmd in self.commands
            if "attrs" in cmd
        )
        vdi_roundtrip_error: str | None = None
        try:
            vdi_report = _verify_runner_vdi(scene)
            vdi_roundtrip_passed = bool(vdi_report.passed)
        except ValueError as exc:
            if not (
                has_unclipped_commands
                and self._scene_has_out_of_int16_bounds(scene)
                and "signed 16-bit range" in str(exc)
            ):
                raise
            vdi_roundtrip_passed = False
            vdi_roundtrip_error = str(exc)
        result: dict[str, Any] = {
            "metafile_bytes": len(meta_bytes),
            "metafile_valid": bool(seasip_res["valid"]),
            "geometry_passed": bool(geom_report.passed),
            "vdi_roundtrip_passed": vdi_roundtrip_passed,
            "constitutional": self.constitutional_metadata(),
        }
        if vdi_roundtrip_error is not None:
            result["vdi_roundtrip_error"] = vdi_roundtrip_error
        return result

    def snapshot(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "is_open": self.is_open,
            "device_id": self.device_id,
            "coord_mode": "NDC" if self.coord_mode == NDC_MODE else "RC",
            "dimensions": [self.width, self.height],
            "writing_mode": self.writing_mode,
            "clip_enabled": self.clip_enabled,
            "clip_rect": list(self.clip_rect),
            "command_count": len(self.commands),
            "metafile_name": self.metafile_name,
            "meta_page_size": list(self.meta_page_size),
            "constitutional": self.constitutional_metadata(),
        }


__all__ = [
    "AC_CLOSE",
    "AC_OPEN",
    "AES_MSG_NAMES",
    "ATTRIBUTION_TEXT",
    "AesEventMultiResult",
    "BEG_MCTRL",
    "BEG_UPDATE",
    "CHECKED",
    "CLIP_OFF",
    "CLIP_ON",
    "CLOSER",
    "CROSSED",
    "DEFAULT",
    "DISABLED",
    "DNARROW",
    "EDITABLE",
    "ED_CHAR",
    "ED_END",
    "ED_INIT",
    "ED_START",
    "END_MCTRL",
    "END_UPDATE",
    "EPISTEMIC_LANES",
    "ESCCANCEL",
    "EXIT",
    "FIS_HATCH",
    "FIS_HOLLOW",
    "FIS_PATTERN",
    "FIS_SOLID",
    "FIS_USER",
    "FL3DBAK",
    "FLAG3D",
    "FMD_FINISH",
    "FMD_GROW",
    "FMD_SHRINK",
    "FMD_START",
    "FULLER",
    "GEM5_PALETTE_OVERRIDES",
    "GEM_STANDARD_PALETTE",
    "GRECT",
    "G_BOX",
    "G_BOXCHAR",
    "G_BOXTEXT",
    "G_BUTTON",
    "G_CLRICN",
    "G_DTMFDB",
    "G_FBOXTEXT",
    "G_FTEXT",
    "G_IBOX",
    "G_ICON",
    "G_IMAGE",
    "G_STRING",
    "G_TEXT",
    "G_TITLE",
    "G_USERDEF",
    "GemAesApplication",
    "GemAesKernel",
    "GemAesWindowTreeManager",
    "GemObject",
    "GemObjectTreeOps",
    "GemResourceManager",
    "GemVdiStateMachine",
    "HIDETREE",
    "HISTORICAL_CREDIT",
    "HSLIDE",
    "INDIRECT",
    "INFO",
    "K_ALT",
    "K_CTRL",
    "K_LSHIFT",
    "K_RSHIFT",
    "LASTOB",
    "LFARROW",
    "MAX_AES_APP_WINDOWS",
    "MD_ERASE",
    "MD_REPLACE",
    "MD_TRANS",
    "MD_XOR",
    "MN_SELECTED",
    "MOVER",
    "MU_BUTTON",
    "MU_KEYBD",
    "MU_M1",
    "MU_M2",
    "MU_MESAG",
    "MU_TIMER",
    "NAME",
    "NDC_MODE",
    "NIL",
    "NONE_FLAG",
    "NORMAL",
    "OB_TYPE_NAMES",
    "OUTLINED",
    "RBUTTON",
    "RC_MODE",
    "ROOT",
    "RTARROW",
    "R_BIPDATA",
    "R_BITBLK",
    "R_FRIMG",
    "R_FRSTR",
    "R_IBPDATA",
    "R_IBPMASK",
    "R_IBPTEXT",
    "R_ICONBLK",
    "R_IMAGEDATA",
    "R_OBJECT",
    "R_OBSPEC",
    "R_STRING",
    "R_TEDINFO",
    "R_TEPTEXT",
    "R_TEPTMPLT",
    "R_TEPVALID",
    "R_TREE",
    "SCROLLER",
    "SELECTABLE",
    "SELECTED",
    "SHADOWED",
    "SIZER",
    "STANDARD_WINDOW_KIND",
    "TOUCHEXIT",
    "UPARROW",
    "USECOLORCAT",
    "VSLIDE",
    "WA_DNLINE",
    "WA_DNPAGE",
    "WA_LFLINE",
    "WA_LFPAGE",
    "WA_RTLINE",
    "WA_RTPAGE",
    "WA_UPLINE",
    "WA_UPPAGE",
    "WC_BORDER",
    "WC_WORK",
    "WF_CURRXYWH",
    "WF_CXYWH",
    "WF_FIRSTXYWH",
    "WF_FULLXYWH",
    "WF_FXYWH",
    "WF_HSLIDE",
    "WF_HSLSIZE",
    "WF_INFO",
    "WF_KIND",
    "WF_NAME",
    "WF_NEWDESK",
    "WF_NEXTXYWH",
    "WF_PREVXYWH",
    "WF_PXYWH",
    "WF_SCREEN",
    "WF_TOP",
    "WF_VSLIDE",
    "WF_VSLSIZE",
    "WF_WORKXYWH",
    "WF_WXYWH",
    "WHITEBAK",
    "WM_ARROWED",
    "WM_CLOSED",
    "WM_FULLED",
    "WM_HSLID",
    "WM_MOVED",
    "WM_NEWTOP",
    "WM_REDRAW",
    "WM_SIZED",
    "WM_TOPPED",
    "WM_UNTOPPED",
    "WM_VSLID",
    "constitutional_metadata",
    "decode_aes_message",
    "encode_aes_message",
    "form_alert",
    "form_center",
    "form_dial",
    "form_do",
    "menu_bar",
    "menu_icheck",
    "menu_ienable",
    "menu_tnormal",
    "nearest_gem_color_index",
    "rgb_to_vdi_1000",
    "rsrc_free",
    "rsrc_gaddr",
    "rsrc_load",
    "rsrc_obfix",
]
