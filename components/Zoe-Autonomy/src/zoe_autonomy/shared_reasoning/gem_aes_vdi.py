"""Digital Research GEM AES / VDI / RSC / ViewMAX Bridge for Shared Reasoning.

Original-code bridge connecting Zoe's existing ``guiai.gem`` Digital Research GEM
stack (built directly against John Elliott's GEM Information Archive at
``https://www.seasip.info/Gem/index.html``) with ``zoe_autonomy.shared_reasoning``
Architectures 1-9 under ``docs/CONSTITUTION.md``:

  - Article II.3: Visual scenes and metafiles are explicitly labeled
    ``visual_evidence_only=True`` — never presented as proof of correctness or
    authorization.
  - Article III / X: ``external_actions == 0``, ``sentience_claimed is False``,
    ``l5_agi_qualified is False``, ``zoe_clone_claimed is False``.
  - Article VIII: Preserves credit to Nicholas Michael Kloster (March 6, 2026)
    and honors Gary Kildall & Digital Research's GEM contributors.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import sys
from typing import Any

from .sdk_bridge import ATTRIBUTION_TEXT, bridge_constitutional_metadata

GEM_AES_VDI_CONTRACT = "zoe-gem-aes-vdi/v1"
GEM_ART_II_3_NOTICE = (
    "CONSTITUTION.md Art. II.3: GEM VDI scenes, AES dialogs, and metafiles provide "
    "visual inspection only (visual_evidence_only=True) and never constitute proof "
    "of correctness, safety, sentience, or autonomous authorization."
)
GEM_HISTORICAL_CREDIT = (
    "Honoring Gary Kildall and Digital Research GEM contributors (seasip.info/Gem/index.html); "
    f"{ATTRIBUTION_TEXT}"
)

# AES Function 25 (evnt_multi) event bitmasks per seasip.info/Gem/aes.html
MU_KEYBD = 0x0001
MU_BUTTON = 0x0002
MU_M1 = 0x0004
MU_M2 = 0x0008
MU_MESAG = 0x0010
MU_TIMER = 0x0020
_ALL_EVENT_FLAGS = MU_KEYBD | MU_BUTTON | MU_M1 | MU_M2 | MU_MESAG | MU_TIMER

MAX_GEM_METAFILE_BYTES = 1_048_576
VALID_VDI_DEVICES = ("cga", "vga", "ndc", "atari_st")
_VDI_DEVICE_DIMS: dict[str, tuple[int, int]] = {
    "cga": (320, 200),
    "vga": (640, 480),
    "ndc": (32767, 32767),
    "atari_st": (640, 400),
}
_VDI_SAFE_NAMED_COLORS = frozenset(
    {"white", "black", "red", "green", "blue", "cyan", "yellow", "magenta"}
)


def _ensure_guiai_importable() -> Path | None:
    """Locate ``guiai-lab`` relative to this module and add it to ``sys.path``."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "guiai-lab"
        if (candidate / "guiai" / "gem").is_dir():
            cand_str = str(candidate)
            if cand_str not in sys.path:
                sys.path.insert(0, cand_str)
            return candidate
    return None


_ensure_guiai_importable()

from guiai.gem import geometry as gem_geometry  # noqa: E402
from guiai.gem import model as gem_model  # noqa: E402
from guiai.gem import runner as gem_runner  # noqa: E402
from guiai.gem import seasip_gem  # noqa: E402
from guiai.gem import vdi as gem_vdi  # noqa: E402
from guiai.gem import zoe_atari_gem_rsc as atari_rsc  # noqa: E402
from guiai.gem import zoe_freegem_archive as freegem_archive  # noqa: E402
from guiai.gem import zoe_gem_themes as gem_themes  # noqa: E402

# Re-export canonical seasip.info GEM AES constants
MN_SELECTED: int = int(seasip_gem.MN_SELECTED)
WM_REDRAW: int = int(seasip_gem.WM_REDRAW)
WM_TOPPED: int = int(seasip_gem.WM_TOPPED)
WM_CLOSED: int = int(seasip_gem.WM_CLOSED)
WM_FULLED: int = int(seasip_gem.WM_FULLED)
WM_MOVED: int = int(seasip_gem.WM_MOVED)
WM_NEWTOP: int = int(seasip_gem.WM_NEWTOP)
WM_UNTOPPED: int = int(seasip_gem.WM_UNTOPPED)
MAX_AES_APP_WINDOWS: int = int(seasip_gem.MAX_AES_APP_WINDOWS)
STANDARD_WINDOW_KIND: int = int(seasip_gem.STANDARD_WINDOW_KIND)


def _gem_constitutional() -> dict[str, Any]:
    meta = bridge_constitutional_metadata(cloud_tokens_used=0)
    meta["visual_evidence_only"] = True
    meta["historical_credit"] = GEM_HISTORICAL_CREDIT
    return meta


def _require_nonbool_int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer, got {value!r}")
    return int(value)


def _safe_hex_or_named_color(color: str, fallback: str = "#00756B") -> str:
    clean = str(color or "").strip()
    low = clean.lower()
    if low in _VDI_SAFE_NAMED_COLORS:
        return low
    if len(clean) == 7 and clean.startswith("#"):
        hex_part = clean[1:]
        if all(ch in "0123456789abcdefABCDEF" for ch in hex_part):
            return clean.upper()
    return fallback


def _trim_vdi_text(text: str, max_chars: int = 30) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return "ZOE GEM"
    return cleaned[:max_chars]


@dataclass(frozen=True)
class GemEventResult:
    """Deterministic result returned by ``GemEventMultiQueue.evnt_multi``."""

    matched_flags: int
    message: dict[str, Any] | None
    raw_bytes: bytes | None
    timer_elapsed_ms: int
    key_code: int | None = None
    button_state: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "matched_flags": self.matched_flags,
            "message": dict(self.message) if self.message is not None else None,
            "raw_hex": self.raw_bytes.hex() if self.raw_bytes is not None else None,
            "raw_len": len(self.raw_bytes) if self.raw_bytes is not None else 0,
            "timer_elapsed_ms": self.timer_elapsed_ms,
            "key_code": self.key_code,
            "button_state": self.button_state,
            "constitutional": _gem_constitutional(),
        }


class GemEventMultiQueue:
    """Deterministic in-memory AES 16-byte message pipe & ``evnt_multi`` dispatcher."""

    def __init__(self) -> None:
        self._queue: deque[bytes] = deque()
        self._history: list[dict[str, Any]] = []

    def post_message(
        self,
        msg_type: int,
        sender_apid: int = 0,
        extra_len: int = 0,
        w3: int = 0,
        w4: int = 0,
        w5: int = 0,
        w6: int = 0,
        w7: int = 0,
    ) -> bytes:
        """Encode an 8-word (`<8h`) AES message via ``seasip_gem`` and enqueue it."""
        vals = [
            _require_nonbool_int(v, name)
            for name, v in (
                ("msg_type", msg_type),
                ("sender_apid", sender_apid),
                ("extra_len", extra_len),
                ("w3", w3),
                ("w4", w4),
                ("w5", w5),
                ("w6", w6),
                ("w7", w7),
            )
        ]
        for val in vals:
            if not (-32768 <= val <= 32767):
                raise ValueError(f"AES int16 word out of range [-32768, 32767]: {val}")
        raw = bytes(
            seasip_gem.encode_aes_message(
                vals[0], vals[1], vals[2], vals[3], vals[4], vals[5], vals[6], vals[7]
            )
        )
        decoded = dict(seasip_gem.decode_aes_message(raw))
        self._queue.append(raw)
        self._history.append(decoded)
        return raw

    def evnt_multi(
        self,
        flags: int = MU_MESAG | MU_TIMER,
        *,
        timer_ms: int = 0,
        key_code: int | None = None,
        button_state: int = 0,
    ) -> GemEventResult:
        """Non-blocking deterministic ``evnt_multi`` dequeue matching AES event masks."""
        clean_flags = _require_nonbool_int(flags, "flags")
        clean_timer = _require_nonbool_int(timer_ms, "timer_ms")
        clean_button = _require_nonbool_int(button_state, "button_state")
        if clean_flags <= 0 or (clean_flags & ~_ALL_EVENT_FLAGS) != 0:
            raise ValueError(
                f"flags must be a non-empty subset of AES MU_* masks, got {clean_flags:#x}"
            )
        if clean_timer < 0:
            raise ValueError(f"timer_ms must be >= 0, got {clean_timer}")
        clean_key: int | None = None
        if key_code is not None:
            clean_key = _require_nonbool_int(key_code, "key_code")

        matched = 0
        raw_msg: bytes | None = None
        decoded_msg: dict[str, Any] | None = None

        if (clean_flags & MU_MESAG) and self._queue:
            raw_msg = self._queue.popleft()
            decoded_msg = dict(seasip_gem.decode_aes_message(raw_msg))
            matched |= MU_MESAG
        if (clean_flags & MU_KEYBD) and clean_key is not None:
            matched |= MU_KEYBD
        if (clean_flags & MU_BUTTON) and clean_button != 0:
            matched |= MU_BUTTON
        if (clean_flags & MU_TIMER) and (matched == 0 or clean_timer > 0):
            matched |= MU_TIMER

        return GemEventResult(
            matched_flags=matched,
            message=decoded_msg,
            raw_bytes=raw_msg,
            timer_elapsed_ms=clean_timer if (matched & MU_TIMER) else 0,
            key_code=clean_key if (matched & MU_KEYBD) else None,
            button_state=clean_button if (matched & MU_BUTTON) else 0,
        )

    def pending_count(self) -> int:
        return len(self._queue)

    def message_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(dict(item) for item in self._history)


class GemWindowManager:
    """Digital Research GEM AES Window & Menu Manager backed by ``seasip_gem.GemAesDesk``."""

    def __init__(
        self,
        *,
        screen_w: int = 640,
        screen_h: int = 480,
        theme_key: str = "zoe-viewmax3",
        event_queue: GemEventMultiQueue | None = None,
    ) -> None:
        sw = _require_nonbool_int(screen_w, "screen_w")
        sh = _require_nonbool_int(screen_h, "screen_h")
        if sw <= 0 or sh <= 0 or sw > 32767 or sh > 32767:
            raise ValueError(f"screen dimensions must be in (0, 32767], got {sw}x{sh}")
        self.screen_w = sw
        self.screen_h = sh
        self.theme = gem_themes.resolve_viewmax_scheme(theme_key)
        self.theme_key = str(self.theme.key)
        self.desk = seasip_gem.GemAesDesk(screen_w=sw, screen_h=sh)
        self.event_queue = event_queue if event_queue is not None else GemEventMultiQueue()
        self._menu_titles: tuple[str, ...] = (
            "Desk",
            "File",
            "Chairs",
            "Quorum",
            "Steering",
            "VDI",
            "ViewMAX",
        )
        self._active_menu_index: int = 0

    def _require_window(self, handle: int) -> Any:
        h = _require_nonbool_int(handle, "handle")
        if h not in self.desk.windows:
            raise KeyError(f"Unknown GEM window handle: {h}")
        return self.desk.windows[h]

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
        """Allocate a GEM AES window handle (`1..7`), or `-1` when all 7 slots are full."""
        vals = [
            _require_nonbool_int(v, name)
            for name, v in (("kind", kind), ("x", x), ("y", y), ("w", w), ("h", h))
        ]
        if vals[3] <= 0 or vals[4] <= 0:
            raise ValueError(f"Window width/height must be positive, got {vals[3]}x{vals[4]}")
        for coord in vals[1:]:
            if not (-32768 <= coord <= 32767):
                raise ValueError(f"Window coordinate out of int16 range: {coord}")
        return int(
            self.desk.wind_create(
                vals[0],
                vals[1],
                vals[2],
                vals[3],
                vals[4],
                title=str(title),
                info=str(info),
                layer_id=str(layer_id),
            )
        )

    def wind_open(
        self,
        handle: int,
        *,
        rect: tuple[int, int, int, int] | None = None,
    ) -> bytes:
        """Open a created window, top it, and emit a 16-byte ``WM_REDRAW`` message."""
        win = self._require_window(handle)
        if rect is not None:
            if len(rect) != 4:
                raise ValueError("rect must be a 4-tuple (x, y, w, h)")
            rx, ry, rw, rh = (_require_nonbool_int(c, "rect") for c in rect)
            if rw <= 0 or rh <= 0:
                raise ValueError("rect width and height must be positive")
            win.x, win.y, win.w, win.h = rx, ry, rw, rh
        raw_desk = bytes(self.desk.wind_open(win.handle))
        raw_evt = self.event_queue.post_message(
            WM_REDRAW, 0, 0, win.handle, win.x, win.y, win.w, win.h
        )
        assert len(raw_desk) == 16
        return raw_evt

    def wind_get(self, handle: int, field_id: str = "work_rect") -> dict[str, Any]:
        """Inspect GEM AES window geometry/state (``work_rect``, ``curr_rect``, ``top``, ``meta``)."""
        win = self._require_window(handle)
        key = str(field_id).strip().lower()
        if key == "work_rect":
            title_h = 18 if (win.kind & int(seasip_gem.NAME)) else 0
            info_h = 14 if (win.kind & int(seasip_gem.INFO)) else 0
            wx = win.x + 2
            wy = win.y + title_h + info_h + 2
            ww = max(1, win.w - 4)
            wh = max(1, win.h - title_h - info_h - 4)
            return {
                "handle": win.handle,
                "field": "work_rect",
                "rect": [wx, wy, ww, wh],
                "opened": bool(win.opened),
            }
        if key in {"curr_rect", "rect"}:
            return {
                "handle": win.handle,
                "field": "curr_rect",
                "rect": [win.x, win.y, win.w, win.h],
                "opened": bool(win.opened),
            }
        if key == "top":
            return {
                "handle": win.handle,
                "field": "top",
                "top_handle": int(self.desk.top_handle),
                "is_top": int(self.desk.top_handle) == win.handle,
            }
        if key == "meta":
            return {
                "handle": win.handle,
                "title": win.title,
                "info": win.info,
                "layer_id": win.layer_id,
                "opened": bool(win.opened),
                "rect": [win.x, win.y, win.w, win.h],
            }
        raise ValueError(f"Unsupported wind_get field_id: {field_id!r}")

    def wind_set(self, handle: int, field_id: str, value: Any) -> dict[str, Any]:
        """Mutate GEM AES window properties (``top``, ``title``, ``info``, ``rect``)."""
        win = self._require_window(handle)
        key = str(field_id).strip().lower()
        msg_bytes: bytes | None = None
        if key == "top":
            self.desk.top_handle = win.handle
            msg_bytes = self.event_queue.post_message(WM_TOPPED, 0, 0, win.handle, 0, 0, 0, 0)
            self.desk.dispatch(msg_bytes)
        elif key == "title":
            win.title = str(value)
        elif key == "info":
            win.info = str(value)
        elif key == "rect":
            if not isinstance(value, (tuple, list)) or len(value) != 4:
                raise ValueError("wind_set('rect', ...) requires a 4-element (x, y, w, h)")
            rx, ry, rw, rh = (_require_nonbool_int(c, "rect") for c in value)
            if rw <= 0 or rh <= 0:
                raise ValueError("rect width and height must be positive")
            win.x, win.y, win.w, win.h = rx, ry, rw, rh
            msg_bytes = self.event_queue.post_message(WM_MOVED, 0, 0, win.handle, rx, ry, rw, rh)
            self.desk.dispatch(msg_bytes)
        else:
            raise ValueError(f"Unsupported wind_set field_id: {field_id!r}")
        return {
            "handle": win.handle,
            "field": key,
            "top_handle": int(self.desk.top_handle),
            "rect": [win.x, win.y, win.w, win.h],
            "title": win.title,
            "info": win.info,
            "message_emitted": msg_bytes is not None,
        }

    def wind_close(self, handle: int) -> bytes:
        """Close an open window (keeping handle allocated until ``wind_delete``) and emit ``WM_CLOSED``."""
        win = self._require_window(handle)
        win.opened = False
        if self.desk.top_handle == win.handle:
            open_others = [h for h, w in sorted(self.desk.windows.items()) if w.opened]
            self.desk.top_handle = open_others[-1] if open_others else 0
        raw_close = self.event_queue.post_message(WM_CLOSED, 0, 0, win.handle, 0, 0, 0, 0)
        self.desk.dispatch(raw_close)
        return raw_close

    def wind_delete(self, handle: int) -> None:
        """Free a GEM AES window slot so another ``wind_create`` can reuse it."""
        win = self._require_window(handle)
        if win.opened:
            self.wind_close(win.handle)
        del self.desk.windows[win.handle]

    def tile_windows_gem2(self) -> dict[int, tuple[int, int, int, int]]:
        """Compute a GEM/2 non-overlapping tiled layout for all open windows."""
        open_wins = [w for _, w in sorted(self.desk.windows.items()) if w.opened]
        if not open_wins:
            return {}
        menu_h = 24
        pad = 4
        avail_w = max(40, self.screen_w - 2 * pad)
        avail_h = max(40, self.screen_h - menu_h - 2 * pad)
        n = len(open_wins)
        cols = max(1, math.ceil(math.sqrt(n)))
        rows = max(1, math.ceil(n / cols))
        cell_w = max(20, (avail_w - (cols - 1) * pad) // cols)
        cell_h = max(20, (avail_h - (rows - 1) * pad) // rows)

        rects: dict[int, tuple[int, int, int, int]] = {}
        for idx, win in enumerate(open_wins):
            col = idx % cols
            row = idx // cols
            rx = pad + col * (cell_w + pad)
            ry = menu_h + pad + row * (cell_h + pad)
            win.x, win.y, win.w, win.h = rx, ry, cell_w, cell_h
            rects[win.handle] = (rx, ry, cell_w, cell_h)
        return rects

    def menu_bar(
        self,
        titles: Sequence[str] = (
            "Desk",
            "File",
            "Chairs",
            "Quorum",
            "Steering",
            "VDI",
            "ViewMAX",
        ),
        *,
        active_index: int = 0,
    ) -> dict[str, Any]:
        """Configure and describe the top GEM AES menu bar."""
        clean_titles = tuple(str(t).strip() for t in titles if str(t).strip())
        if not clean_titles:
            raise ValueError("menu_bar requires at least one non-empty title")
        idx = _require_nonbool_int(active_index, "active_index")
        if not (0 <= idx < len(clean_titles)):
            raise ValueError(f"active_index {idx} out of range for {len(clean_titles)} titles")
        self._menu_titles = clean_titles
        self._active_menu_index = idx
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "titles": list(clean_titles),
            "active_index": idx,
            "active_title": clean_titles[idx],
            "theme_key": self.theme_key,
            "constitutional": _gem_constitutional(),
        }

    def menu_tnormal(self, title_index: int, normal: bool = True) -> bytes:
        """Highlight (`normal=False`, emitting ``MN_SELECTED``) or restore a GEM menu title."""
        idx = _require_nonbool_int(title_index, "title_index")
        if not (0 <= idx < len(self._menu_titles)):
            raise ValueError(
                f"title_index {idx} out of range for {len(self._menu_titles)} menu titles"
            )
        if not normal:
            self._active_menu_index = idx
            raw_mn = self.event_queue.post_message(MN_SELECTED, 0, 0, idx, idx + 1, 0, 0, 0)
            self.desk.dispatch(raw_mn)
            return raw_mn
        return self.event_queue.post_message(WM_REDRAW, 0, 0, 0, 0, 0, self.screen_w, 24)

    def summary(self) -> dict[str, Any]:
        desk_sum = dict(self.desk.summary())
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "theme_key": self.theme_key,
            "screen": [self.screen_w, self.screen_h],
            "allocated_windows": len(self.desk.windows),
            "open_windows": len(desk_sum["open_windows"]),
            "max_windows": MAX_AES_APP_WINDOWS,
            "top_handle": int(self.desk.top_handle),
            "messages_logged": len(self.event_queue.message_log()),
            "pending_messages": self.event_queue.pending_count(),
            "menu_titles": list(self._menu_titles),
            "active_menu_index": self._active_menu_index,
            "constitutional": _gem_constitutional(),
        }


@dataclass(frozen=True)
class GemFormAlert:
    """Verified GEM AES Function 52 ``form_alert`` specification + compiled ``.RSC`` dialog tree."""

    icon_id: int
    lines: tuple[str, ...]
    buttons: tuple[str, ...]
    default_btn: int
    form_alert_string: str
    object_tree_summary: dict[str, Any]
    rsc_bytes: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "icon_id": self.icon_id,
            "lines": list(self.lines),
            "buttons": list(self.buttons),
            "default_btn": self.default_btn,
            "form_alert_string": self.form_alert_string,
            "object_tree_summary": dict(self.object_tree_summary),
            "rsc_sha256": hashlib.sha256(self.rsc_bytes).hexdigest(),
            "rsc_bytes_len": len(self.rsc_bytes),
            "external_actions": 0,
            "visual_evidence_only": True,
            "constitutional": _gem_constitutional(),
        }


def build_form_alert(
    icon_id: int,
    lines: Sequence[str],
    buttons: Sequence[str],
    *,
    default_btn: int = 1,
    title: str = "ZOE_ALERT",
    endian: str = "<",
) -> GemFormAlert:
    """Build a spec-exact GEM ``form_alert`` string and compile its ``.RSC`` object tree."""
    clean_icon = _require_nonbool_int(icon_id, "icon_id")
    if clean_icon not in (0, 1, 2, 3):
        raise ValueError(f"icon_id must be 0, 1, 2, or 3, got {clean_icon}")
    if endian not in ("<", ">"):
        raise ValueError(f"endian must be '<' or '>', got {endian!r}")

    raw_lines = [str(ln).strip() for ln in lines if str(ln).strip()]
    raw_buttons = [str(b).strip() for b in buttons if str(b).strip()]
    if not (1 <= len(raw_lines) <= 5):
        raise ValueError(f"form_alert requires 1 to 5 non-empty lines, got {len(raw_lines)}")
    if not (1 <= len(raw_buttons) <= 3):
        raise ValueError(f"form_alert requires 1 to 3 non-empty buttons, got {len(raw_buttons)}")

    clean_default = _require_nonbool_int(default_btn, "default_btn")
    if not (1 <= clean_default <= len(raw_buttons)):
        raise ValueError(
            f"default_btn must be in 1..{len(raw_buttons)}, got {clean_default}"
        )

    alert_str = str(seasip_gem.build_form_alert(clean_icon, raw_lines, raw_buttons))
    parsed_alert = dict(seasip_gem.parse_form_alert(alert_str))
    clean_lines = tuple(parsed_alert["lines"])
    clean_buttons = tuple(parsed_alert["buttons"])

    # Construct authentic GEM AES object tree (G_BOX root at index 0 + G_STRING lines + G_BUTTON buttons)
    dialog_w = 46
    dialog_h = max(7, len(clean_lines) + 5)
    tree = seasip_gem.GemObjectTree(str(title or "ZOE_ALERT")[:24], dialog_w, dialog_h)
    root_idx = 0
    for row_idx, line_txt in enumerate(clean_lines):
        tree.add(
            seasip_gem.G_STRING,
            3,
            1 + row_idx,
            min(40, max(1, len(line_txt))),
            1,
            parent=root_idx,
            text=line_txt,
        )
    btn_y = len(clean_lines) + 2
    btn_w = max(8, (dialog_w - 6) // len(clean_buttons) - 1)
    for b_idx, btn_txt in enumerate(clean_buttons, start=1):
        flags = seasip_gem.SELECTABLE | seasip_gem.EXIT | seasip_gem.FLAG3D
        if b_idx == clean_default:
            flags |= seasip_gem.DEFAULT
        tree.add(
            seasip_gem.G_BUTTON,
            3 + (b_idx - 1) * (btn_w + 1),
            btn_y,
            btn_w,
            2,
            parent=root_idx,
            flags=flags,
            text=btn_txt,
        )

    rsc_bytes = bytes(seasip_gem.compile_rsc([tree], endian=endian))
    parsed_rsc = dict(seasip_gem.parse_rsc(rsc_bytes))
    tree_summary = {
        "title": str(title or "ZOE_ALERT")[:24],
        "endian": parsed_rsc["endian"],
        "arch": parsed_rsc["arch"],
        "rsh_nobs": parsed_rsc["rsh_nobs"],
        "rsh_ntree": parsed_rsc["rsh_ntree"],
        "rsh_rssize": parsed_rsc["rsh_rssize"],
        "icon_name": parsed_alert["icon_name"],
    }
    return GemFormAlert(
        icon_id=clean_icon,
        lines=clean_lines,
        buttons=clean_buttons,
        default_btn=clean_default,
        form_alert_string=alert_str,
        object_tree_summary=tree_summary,
        rsc_bytes=rsc_bytes,
    )


class GemVdiWorkstation:
    """Digital Research GEM VDI workstation wrapper compiling Spatial IR to ``.GEM`` metafiles."""

    def __init__(self, *, device: str = "vga", theme_key: str = "zoe-viewmax3") -> None:
        dev = str(device).strip().lower()
        if dev not in VALID_VDI_DEVICES:
            raise ValueError(f"device must be one of {VALID_VDI_DEVICES}, got {device!r}")
        self.device = dev
        self.theme = gem_themes.resolve_viewmax_scheme(theme_key)
        self.theme_key = str(self.theme.key)
        self.opened: bool = False
        self.handle: int = 0
        self.attributes: dict[str, Any] = {
            "vsl_color": "black",
            "vsf_color": _safe_hex_or_named_color(self.theme.title_active_bg, "#00756B"),
            "vsf_interior": 1,
            "vst_height": 160,
        }

    def v_opnwk(self, device: str | None = None) -> dict[str, Any]:
        """Open a virtual GEM VDI workstation for ``device``."""
        if device is not None:
            dev = str(device).strip().lower()
            if dev not in VALID_VDI_DEVICES:
                raise ValueError(f"device must be one of {VALID_VDI_DEVICES}, got {device!r}")
            self.device = dev
        self.opened = True
        self.handle = 1
        w, h = _VDI_DEVICE_DIMS[self.device]
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "handle": self.handle,
            "opened": True,
            "device": self.device,
            "dimensions": [w, h],
            "theme_key": self.theme_key,
            "attributes": dict(self.attributes),
            "constitutional": _gem_constitutional(),
        }

    def v_clswk(self) -> dict[str, Any]:
        """Close the active virtual GEM VDI workstation."""
        prev_handle = self.handle
        self.opened = False
        self.handle = 0
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "previous_handle": prev_handle,
            "opened": False,
            "device": self.device,
            "constitutional": _gem_constitutional(),
        }

    def set_attributes(
        self,
        *,
        vsl_color: str | None = None,
        vsf_color: str | None = None,
        vsf_interior: int | None = None,
        vst_height: int | None = None,
    ) -> dict[str, Any]:
        """Set VDI polyline/fill/text attributes."""
        if vsl_color is not None:
            self.attributes["vsl_color"] = _safe_hex_or_named_color(vsl_color, "black")
        if vsf_color is not None:
            self.attributes["vsf_color"] = _safe_hex_or_named_color(vsf_color, "#00756B")
        if vsf_interior is not None:
            interior = _require_nonbool_int(vsf_interior, "vsf_interior")
            if not (0 <= interior <= 4):
                raise ValueError(f"vsf_interior must be in 0..4, got {interior}")
            self.attributes["vsf_interior"] = interior
        if vst_height is not None:
            height = _require_nonbool_int(vst_height, "vst_height")
            if not (1 <= height <= 4096):
                raise ValueError(f"vst_height must be in 1..4096, got {height}")
            self.attributes["vst_height"] = height
        return dict(self.attributes)

    def build_shared_reasoning_scene(
        self,
        state_or_report: Mapping[str, Any] | Any = None,
        *,
        theme_key: str | None = None,
        scene_id: str = "zoe-shared-reasoning-gem-desk",
    ) -> Any:
        """Build a CGA/VGA/NDC-verifiable ``guiai.gem.model.Scene`` for Shared Reasoning."""
        scheme = gem_themes.resolve_viewmax_scheme(theme_key or self.theme_key)
        bg_hex = _safe_hex_or_named_color(scheme.desktop_bg, "#EFEBEF")
        bar_hex = _safe_hex_or_named_color(scheme.title_active_bg, "#00756B")
        pane_hex = _safe_hex_or_named_color(scheme.menu_bg, "#FFFFFF")
        accent_hex = _safe_hex_or_named_color(scheme.accent, "#FFC300")

        state: Mapping[str, Any] = {}
        if isinstance(state_or_report, Mapping):
            state = state_or_report
        elif state_or_report is not None and hasattr(state_or_report, "to_dict"):
            raw_d = state_or_report.to_dict()
            if isinstance(raw_d, Mapping):
                state = raw_d

        quorum_verdict = str(
            (state.get("quorum_result") or {}).get("verdict")
            if isinstance(state.get("quorum_result"), Mapping)
            else state.get("quorum_verdict", "QUORUM READY")
        )
        mcts_decision = str(
            (state.get("mcts_result") or {}).get("decision")
            if isinstance(state.get("mcts_result"), Mapping)
            else state.get("mcts_decision", "MCTS READY")
        )
        fork_active = bool(
            (state.get("steering_report") or {}).get("fork_detected")
            if isinstance(state.get("steering_report"), Mapping)
            else state.get("fork_detected", False)
        )
        turns_count = (
            (state.get("counterpoint_result") or {}).get("total_turns")
            if isinstance(state.get("counterpoint_result"), Mapping)
            else state.get("counterpoint_turns", 6)
        )

        # Every rectangle has generous separation (>= 120 units -> >= 3.8 CGA px)
        # and every text item has x + len(text)*size*0.62 comfortably inside its box.
        doc: dict[str, Any] = {
            "schema_version": 1,
            "id": str(scene_id or "zoe-shared-reasoning-gem-desk"),
            "title": "Zoe x Antigravity Shared-Reasoning GEM Desk",
            "canvas": {"width": 10000, "height": 6000},
            "objects": [
                {
                    "id": "menu_bar",
                    "type": "rectangle",
                    "bounds": [100, 100, 9900, 480],
                    "fill": bar_hex,
                    "stroke": "black",
                    "label": "GEM AES Menu Bar",
                },
                {
                    "id": "menu_text",
                    "type": "text",
                    "position": [260, 360],
                    "text": _trim_vdi_text("Desk File Chairs Quorum VDI", 30),
                    "size": 160,
                    "fill": "white",
                },
                {
                    "id": "win_blackboard",
                    "type": "rectangle",
                    "bounds": [100, 620, 4900, 2900],
                    "fill": pane_hex,
                    "stroke": "black",
                    "label": "Arch 6 Epistemic Blackboard",
                },
                {
                    "id": "txt_blackboard",
                    "type": "text",
                    "position": [260, 1100],
                    "text": _trim_vdi_text("BLACKBOARD: M != E != B != A", 30),
                    "size": 160,
                    "fill": "black",
                },
                {
                    "id": "win_quorum_mcts",
                    "type": "rectangle",
                    "bounds": [5100, 620, 9900, 2900],
                    "fill": pane_hex,
                    "stroke": "black",
                    "label": "Arch 3 MCTS & Arch 4 Quorum",
                },
                {
                    "id": "txt_quorum_mcts",
                    "type": "text",
                    "position": [5260, 1100],
                    "text": _trim_vdi_text(f"MCTS:{mcts_decision[:10]} Q:{quorum_verdict[:10]}", 30),
                    "size": 160,
                    "fill": "black",
                },
                {
                    "id": "win_counterpoint",
                    "type": "rectangle",
                    "bounds": [100, 3040, 4900, 5260],
                    "fill": pane_hex,
                    "stroke": "black",
                    "label": "Arch 9 Counterpoint Chairs",
                },
                {
                    "id": "txt_counterpoint",
                    "type": "text",
                    "position": [260, 3520],
                    "text": _trim_vdi_text(f"CHAIRS GEM/XM turns={turns_count}", 30),
                    "size": 160,
                    "fill": "black",
                },
                {
                    "id": "win_steering",
                    "type": "rectangle",
                    "bounds": [5100, 3040, 9900, 5260],
                    "fill": pane_hex,
                    "stroke": "black",
                    "label": "Arch 8 Fork Gate",
                },
                {
                    "id": "txt_steering",
                    "type": "text",
                    "position": [5260, 3520],
                    "text": _trim_vdi_text(
                        f"FORK ALERT:{'ON' if fork_active else 'OFF'} ART.II.3", 30
                    ),
                    "size": 160,
                    "fill": "black",
                },
                {
                    "id": "status_footer",
                    "type": "rectangle",
                    "bounds": [100, 5400, 9900, 5880],
                    "fill": accent_hex,
                    "stroke": "black",
                    "label": "ViewMAX Constitutional Footer",
                },
                {
                    "id": "footer_text",
                    "type": "text",
                    "position": [260, 5720],
                    "text": _trim_vdi_text("VISUAL ONLY ext=0 sent=False", 30),
                    "size": 160,
                    "fill": "black",
                },
            ],
            "constraints": [
                {"type": "inside_canvas", "object": "*"},
                {
                    "type": "nonoverlap",
                    "objects": [
                        "menu_bar",
                        "win_blackboard",
                        "win_quorum_mcts",
                        "win_counterpoint",
                        "win_steering",
                        "status_footer",
                    ],
                },
            ],
        }
        return gem_model.Scene.from_dict(doc)

    def compile_and_verify_vdi(
        self,
        scene: Any,
        *,
        profiles: Sequence[str] = ("cga", "vga", "ndc"),
    ) -> dict[str, Any]:
        """Compile ``scene`` to a ``.GEM`` VDI metafile and verify across CGA/VGA/NDC profiles."""
        for profile in profiles:
            if str(profile).lower() not in gem_runner.DEVICE_PROFILES:
                raise ValueError(
                    f"Unknown GEM device profile {profile!r}; expected one of "
                    f"{sorted(gem_runner.DEVICE_PROFILES)}"
                )

        source_report = gem_geometry.verify(scene)
        metafile_bytes = bytes(gem_vdi.scene_to_metafile(scene))
        if len(metafile_bytes) > MAX_GEM_METAFILE_BYTES:
            raise ValueError(
                f"Compiled .GEM metafile exceeds {MAX_GEM_METAFILE_BYTES} bytes: {len(metafile_bytes)}"
            )
        vdi_roundtrip = gem_runner.verify_vdi(scene, metafile_bytes)
        seasip_check = dict(seasip_gem.verify_seasip_gem_metafile(metafile_bytes))

        profile_results: dict[str, Any] = {}
        all_profiles_passed = True
        for profile in profiles:
            p_key = str(profile).lower()
            dev_rep = dict(gem_runner.verify_device(scene, p_key))
            p_ok = bool(dev_rep.get("passed", False))
            all_profiles_passed = all_profiles_passed and p_ok
            profile_results[p_key] = {
                "passed": p_ok,
                "dimensions": list(gem_runner.DEVICE_PROFILES[p_key]),
                "geometry_passed": bool((dev_rep.get("geometry") or {}).get("passed", False)),
                "vdi_passed": bool((dev_rep.get("vdi") or {}).get("passed", False)),
            }

        passed = bool(
            source_report.passed
            and vdi_roundtrip.passed
            and bool(seasip_check.get("valid", seasip_check.get("passed", False)))
            and all_profiles_passed
        )
        return {
            "contract": GEM_AES_VDI_CONTRACT,
            "passed": passed,
            "scene_id": str(getattr(scene, "id", None) or scene.document.get("id", "")),
            "scene_digest": str(scene.digest()),
            "source_geometry_passed": bool(source_report.passed),
            "vdi_roundtrip_passed": bool(vdi_roundtrip.passed),
            "seasip_metafile_valid": bool(
                seasip_check.get("valid", seasip_check.get("passed", False))
            ),
            "metafile_bytes_len": len(metafile_bytes),
            "metafile_sha256": hashlib.sha256(metafile_bytes).hexdigest(),
            "metafile_bytes": metafile_bytes,
            "profiles": profile_results,
            "profiles_passed": {k: bool(v["passed"]) for k, v in profile_results.items()},
            "visual_evidence_only": True,
            "art_ii_3_notice": GEM_ART_II_3_NOTICE,
            "constitutional": _gem_constitutional(),
        }


def build_default_atari_rsc() -> bytes:
    """Compile Zoe's canonical Atari TOS big-endian ``.RSC`` bytes via ``guiai.gem``."""
    return bytes(atari_rsc.build_atari_rsc_bytes())


def inspect_gem_rsc(rsc_bytes: bytes, *, label: str = "ZOE_GEM.RSC") -> dict[str, Any]:
    """Validate Atari big-endian or PC little-endian ``.RSC`` bytes via ``guiai.gem``."""
    if not isinstance(rsc_bytes, (bytes, bytearray)):
        raise TypeError(f"rsc_bytes must be bytes or bytearray, got {type(rsc_bytes).__name__}")
    raw = bytes(rsc_bytes)
    if len(raw) < 36:
        raise ValueError(f"RSC buffer truncated ({len(raw)} < 36 byte RSHDR)")
    if len(raw) > MAX_GEM_METAFILE_BYTES:
        raise ValueError(f"RSC buffer exceeds {MAX_GEM_METAFILE_BYTES} bytes")

    parsed_general: dict[str, Any] | None = None
    parsed_atari: dict[str, Any] | None = None
    errors: list[str] = []

    try:
        parsed_general = dict(seasip_gem.parse_rsc(raw))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"seasip_gem.parse_rsc: {exc}")

    try:
        parsed_atari = dict(atari_rsc.parse_atari_rsc(raw))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"zoe_atari_gem_rsc.parse_atari_rsc: {exc}")

    if parsed_general is None and parsed_atari is None:
        raise ValueError("; ".join(errors) or "Invalid GEM .RSC binary")

    archive_meta: dict[str, Any] = {}
    try:
        archive_meta = dict(freegem_archive.inspect_rsc_bytes(raw, label=label))
    except Exception:  # noqa: BLE001
        archive_meta = {"label": label, "bytes_len": len(raw)}

    primary = parsed_general if parsed_general is not None else parsed_atari
    assert primary is not None
    return {
        "contract": GEM_AES_VDI_CONTRACT,
        "label": str(label),
        "bytes_len": len(raw),
        "rsc_sha256": hashlib.sha256(raw).hexdigest(),
        "endian": primary.get("endian", ">" if parsed_atari is not None else "<"),
        "arch": primary.get("arch", "Atari TOS / PC GEM"),
        "rsh_nobs": int(primary.get("rsh_nobs", 0)),
        "rsh_ntree": int(primary.get("rsh_ntree", 0)),
        "rsh_nib": int(primary.get("rsh_nib", len((parsed_atari or {}).get("icons", ())))),
        "archive_summary": archive_meta,
        "visual_evidence_only": True,
        "constitutional": _gem_constitutional(),
    }


__all__ = [
    "GEM_AES_VDI_CONTRACT",
    "GEM_ART_II_3_NOTICE",
    "GEM_HISTORICAL_CREDIT",
    "MAX_AES_APP_WINDOWS",
    "MAX_GEM_METAFILE_BYTES",
    "MN_SELECTED",
    "MU_BUTTON",
    "MU_KEYBD",
    "MU_M1",
    "MU_M2",
    "MU_MESAG",
    "MU_TIMER",
    "STANDARD_WINDOW_KIND",
    "VALID_VDI_DEVICES",
    "WM_CLOSED",
    "WM_FULLED",
    "WM_MOVED",
    "WM_NEWTOP",
    "WM_REDRAW",
    "WM_TOPPED",
    "WM_UNTOPPED",
    "GemEventMultiQueue",
    "GemEventResult",
    "GemFormAlert",
    "GemVdiWorkstation",
    "GemWindowManager",
    "build_default_atari_rsc",
    "build_form_alert",
    "inspect_gem_rsc",
]
