"""Collaborative 9-Sister GEM Workbench (Milestone M4, Features #12 & #13).

Multiplexes:
  1. All 9 canonical sisters (`Zoe, Gemma, Tosi, Mono, Tetra, Eliza, Sage, Flora, Lumen`)
     on the flat-topped hexagonal mesh (`zoe_hex_mesh.py`),
  2. The Figure 15.3 EDDBMS central hub & 6 domain spokes (`zoe_eddms.py`),
  3. The Digital Research GEM AES/VDI stack (`zoe_gem_aes_vdi_core.py`,
     Balma & Fitler 1986, strictly `<= MAX_AES_APP_WINDOWS = 7` windows),
  4. The read-only Ablation static/source bridge (`zoe_ablation_bridge.py`),
  5. Optional transactional GEM-Lab `Session` synchronization (`components/ablation/gem-lab`).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import os
from pathlib import Path
import stat
import sys
from typing import Any

from . import geometry, runner, seasip_gem
from .model import Scene
from .render import scene_to_svg
from .zoe_ablation_bridge import (
    AblationAdvisoryReport,
    AblationBridge,
    attach_ablation_to_eddms,
)
from .zoe_eddms import (
    EDDBMS_DOMAIN_MODULES,
    EDDBMS_SUBOPERATION_KEYS,
    EngineeringDesignDatabase,
    EngineeringDesignRecord,
    FunctionEngineeringSpecification,
)
from .zoe_gem_aes_vdi_core import (
    BEG_UPDATE,
    CLIP_OFF,
    CLIP_ON,
    CLOSER,
    DEFAULT,
    END_UPDATE,
    EXIT,
    FIS_SOLID,
    FULLER,
    G_BOX,
    G_BUTTON,
    G_STRING,
    G_TITLE,
    GRECT,
    INFO,
    LASTOB,
    MAX_AES_APP_WINDOWS,
    MD_REPLACE,
    MN_SELECTED,
    MOVER,
    MU_MESAG,
    MU_TIMER,
    NAME,
    NIL,
    RC_MODE,
    SELECTABLE,
    WF_INFO,
    WF_NAME,
    WF_TOP,
    WM_REDRAW,
    GemAesApplication,
    GemAesWindowTreeManager,
    GemObject,
    GemVdiStateMachine,
    form_center,
    menu_bar,
    menu_icheck,
)
from .zoe_hex_mesh import (
    ATTRIBUTION_TEXT,
    HASH_CHAIN_SEMANTICS,
    ConstitutionalViolationError,
    HexCollaborationMesh,
    build_default_zoe_mesh,
    sha256_canonical,
    validate_epistemic_lane,
)
from .zoe_sisters import SAFETY_INVARIANTS, ZOE_SISTERS, SisterModelSpec, resolve_sister

WORKBENCH_CONTRACT: str = "zoe-collaborative-gem-workbench/v1"
STANDARD_WORKBENCH_WINDOW_KIND: int = NAME | CLOSER | FULLER | MOVER | INFO

_DEFAULT_REPO_ROOT: Path = Path(__file__).resolve().parents[3]

# Six non-overlapping functional panes (within MAX_AES_APP_WINDOWS = 7).
_PANE_DEFS: tuple[tuple[str, str], ...] = (
    ("hex_mesh", "9-Sister Hex Mesh"),
    ("eddms_hub", "EDDBMS Central Hub"),
    ("eddms_spokes", "Domain Spokes (1-3)"),
    ("eddms_pipeline", "Pipeline (Prod->Post)"),
    ("vdi_canvas", "GEM VDI Canvas"),
    ("ablation_advisor", "Ablation Advisor (RO)"),
)


def constitutional_metadata(
    epistemic_lane: str = "advisory_proposal",
    *,
    read_only: bool = True,
) -> dict[str, Any]:
    """Return Project Contract #1 constitutional metadata for the GEM workbench."""
    lane = validate_epistemic_lane(epistemic_lane)
    if not isinstance(read_only, bool):
        raise ConstitutionalViolationError("read_only must be a bool")
    return {
        **SAFETY_INVARIANTS,
        "contract": WORKBENCH_CONTRACT,
        "epistemic_lane": lane,
        "measurement_lane_only": lane == "measurement",
        "advisory_only": True,
        "read_only": read_only,
        "external_actions": 0,
        "tokens_used": 0,
        "cloud_cost_usd": 0.0,
        "loopback_only": True,
        "sentience_claimed": False,
        "l5_agi_qualified": False,
        "zoe_clone_claimed": False,
        "clinical_action_authorized": False,
        "flight_control_authorized": False,
        "cure_claim": False,
        "wet_lab_validation_required": True,
        "autonomous_execution_allowed": False,
        "attribution": ATTRIBUTION_TEXT,
        "hash_chain_semantics": HASH_CHAIN_SEMANTICS,
        "tamper_evidence_only": True,
        "authentication_proof": False,
    }


def default_workbench_specification() -> FunctionEngineeringSpecification:
    """Build deterministic default Function Engineering Specification for workbench startup."""
    return FunctionEngineeringSpecification(
        spec_id="FES-ZOE-WORKBENCH-001",
        title="Zoe 9-Sister Collaborative GEM Workbench",
        objective="Unite 9-sister hex mesh, EDDBMS hub/spokes, VDI canvas, and read-only Ablation",
        owner="Zoe Engineering Collective",
        constraints={"loopback_only": True, "max_aes_windows": MAX_AES_APP_WINDOWS},
        target_properties={"advisory_only": True, "tokens_used": 0, "cloud_cost_usd": 0.0},
        geometric_requirements={"canvas_w": 640, "canvas_h": 400, "panes": 6},
        special_instructions="Advisory GEM workbench only; wet-lab validation required; external_actions=0.",
    )


_GEM_LAB_SESSION_DIRS: tuple[str, ...] = (
    "bin",
    "artifacts",
    "checkpoints",
)

_GEM_LAB_SESSION_FILES: tuple[str, ...] = (
    "session.json",
    "events.jsonl",
    "state.json",
    ".init.lock",
    ".events.lock",
    ".state.lock",
    "AGENTS.md",
    "project.json",
    "bin/gem",
    "bin/gem.cmd",
)


def _validate_no_symlink_or_traversal(destination: str | Path, *, label: str = "GEM path") -> Path:
    """Reject empty/non-path inputs, symlinks, and '..' path traversal components prior to disk writes."""
    if not isinstance(destination, (str, Path)):
        raise ValueError(f"{label} must be a str or Path, got {type(destination).__name__}")
    if isinstance(destination, str) and not destination.strip():
        raise ValueError(f"{label} must be a non-empty path")
    raw_dest = Path(destination).expanduser()
    if not str(raw_dest).strip():
        raise ValueError(f"{label} must be a non-empty path")
    if ".." in raw_dest.parts:
        raise ValueError(f"{label} must not contain '..' traversal: {raw_dest}")
    norm_dest = Path(os.path.normpath(os.path.abspath(raw_dest)))
    for candidate in (raw_dest, *raw_dest.parents, norm_dest, *norm_dest.parents):
        if candidate.is_symlink():
            raise ValueError(f"{label} must not be or traverse a symbolic link: {candidate}")
    return raw_dest


def _validate_gem_lab_session_dir(clean_dir: Path) -> None:
    """Reject non-directory ancestors and symlinked or special GEM-Lab session dirs/files."""
    for candidate in (clean_dir, *clean_dir.parents):
        if os.path.lexists(candidate):
            if not stat.S_ISDIR(os.lstat(candidate).st_mode):
                raise NotADirectoryError(f"GEM-Lab session dir is not a directory: {candidate}")
            break
    if os.path.lexists(clean_dir):
        for dname in _GEM_LAB_SESSION_DIRS:
            dpath = clean_dir / dname
            if os.path.lexists(dpath):
                d_st = os.lstat(dpath)
                if stat.S_ISLNK(d_st.st_mode) or not stat.S_ISDIR(d_st.st_mode):
                    raise ValueError(
                        f"GEM-Lab session directory must be a non-symlink directory: {dpath}"
                    )
        for fname in _GEM_LAB_SESSION_FILES:
            fpath = clean_dir / fname
            if os.path.lexists(fpath):
                f_st = os.lstat(fpath)
                if stat.S_ISLNK(f_st.st_mode) or not stat.S_ISREG(f_st.st_mode):
                    raise ValueError(
                        f"GEM-Lab session file must be a regular non-symlink file: {fpath}"
                    )


def _prepare_export_dest(
    path: str | Path,
    *,
    kind: str,
    label: str,
    overwrite: bool,
) -> Path:
    """Validate export destination against traversal, symlinks, special files, directories, and silent overwrite."""
    dest = _validate_no_symlink_or_traversal(path, label=label)
    for parent in (dest.parent, *dest.parent.parents):
        if os.path.lexists(parent):
            p_st = os.lstat(parent)
            if not stat.S_ISDIR(p_st.st_mode):
                raise NotADirectoryError(f"{label} parent path is not a directory: {parent}")
            break
    if os.path.lexists(dest):
        st = os.lstat(dest)
        if stat.S_ISDIR(st.st_mode):
            raise IsADirectoryError(f"{kind} export destination is a directory: {dest}")
        if not stat.S_ISREG(st.st_mode):
            raise ValueError(
                f"{kind} export destination must be a regular file (special file rejected): {dest}"
            )
        if not overwrite:
            raise FileExistsError(f"Refusing to overwrite existing {kind} file: {dest}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def _ensure_gem_lab_sys_path() -> Path:
    """Prepend `components/ablation/gem-lab` to `sys.path[0]` before importing `gem`."""
    gem_lab_root = str((_DEFAULT_REPO_ROOT / "components" / "ablation" / "gem-lab").resolve())
    if not sys.path or sys.path[0] != gem_lab_root:
        while gem_lab_root in sys.path:
            sys.path.remove(gem_lab_root)
        sys.path.insert(0, gem_lab_root)
    return Path(gem_lab_root)


def _build_menu_tree(screen_w: int) -> tuple[list[GemObject], dict[str, int]]:
    """Build a valid Balma & Fitler GEM menu bar covering all 9 sisters."""
    # Objects: 0=root, 1=Desk title, 2=Sisters title, 3=Sisters box, 4..12=9 sister items
    sister_start_idx = 4
    last_idx = sister_start_idx + len(ZOE_SISTERS) - 1
    tree: list[GemObject] = [
        GemObject(ob_next=NIL, ob_head=1, ob_tail=3, ob_type=G_BOX, ob_w=screen_w, ob_h=20),
        GemObject(ob_next=2, ob_head=NIL, ob_tail=NIL, ob_type=G_TITLE, ob_x=4, ob_y=0, ob_w=48, ob_h=16, text="Desk"),
        GemObject(ob_next=3, ob_head=NIL, ob_tail=NIL, ob_type=G_TITLE, ob_x=56, ob_y=0, ob_w=68, ob_h=16, text="Sisters"),
        GemObject(ob_next=0, ob_head=sister_start_idx, ob_tail=last_idx, ob_type=G_BOX, ob_x=56, ob_y=18, ob_w=120, ob_h=len(ZOE_SISTERS) * 16),
    ]
    sister_item_indices: dict[str, int] = {}
    for offset, sister in enumerate(ZOE_SISTERS):
        idx = sister_start_idx + offset
        is_last = idx == last_idx
        next_idx = 3 if is_last else idx + 1
        flags = LASTOB if is_last else 0
        tree.append(
            GemObject(
                ob_next=next_idx,
                ob_head=NIL,
                ob_tail=NIL,
                ob_type=G_STRING,
                ob_flags=flags,
                ob_x=0,
                ob_y=offset * 16,
                ob_w=120,
                ob_h=16,
                text=sister.name,
            )
        )
        sister_item_indices[sister.name] = idx
    return tree, sister_item_indices


def _build_status_dialog_tree() -> list[GemObject]:
    """Build a valid centered GEM status dialog tree."""
    return [
        GemObject(ob_next=NIL, ob_head=1, ob_tail=2, ob_type=G_BOX, ob_w=240, ob_h=96),
        GemObject(ob_next=2, ob_head=NIL, ob_tail=NIL, ob_type=G_STRING, ob_x=16, ob_y=16, ob_w=208, ob_h=16, text="Zoe 9-Sister Workbench"),
        GemObject(ob_next=0, ob_head=NIL, ob_tail=NIL, ob_type=G_BUTTON, ob_flags=SELECTABLE | DEFAULT | EXIT | LASTOB, ob_x=80, ob_y=60, ob_w=80, ob_h=20, text="OK"),
    ]


def _tiled_pane_rects(screen_w: int, screen_h: int) -> list[GRECT]:
    """Compute 6 non-overlapping tiled GRECTs below the 20px menu bar."""
    top_y = 20
    avail_h = screen_h - top_y
    row_h0 = avail_h // 2
    row_h1 = avail_h - row_h0
    col_w0 = screen_w // 3
    col_w1 = screen_w // 3
    col_w2 = screen_w - col_w0 - col_w1
    return [
        GRECT(0, top_y, col_w0, row_h0),
        GRECT(col_w0, top_y, col_w1, row_h0),
        GRECT(col_w0 + col_w1, top_y, col_w2, row_h0),
        GRECT(0, top_y + row_h0, col_w0, row_h1),
        GRECT(col_w0, top_y + row_h0, col_w1, row_h1),
        GRECT(col_w0 + col_w1, top_y + row_h0, col_w2, row_h1),
    ]


@dataclass
class _PaneContext:
    """Internal window metadata for one multiplexed workbench pane."""

    layer_id: str
    title: str
    handle: int
    outer_rect: GRECT


def _draw_pane_header(vdi_sm: GemVdiStateMachine, wr: GRECT, title: str, color_idx: int) -> None:
    """Draw outer pane frame and safely inset header text inside work rectangle `wr`."""
    x1, y1 = wr.g_x + 2, wr.g_y + 2
    x2, y2 = wr.g_x + wr.g_w - 3, wr.g_y + wr.g_h - 3
    vdi_sm.vsl_color(color_idx)
    vdi_sm.v_rbox((x1, y1, x2, y2))
    vdi_sm.vst_height(8)
    vdi_sm.vst_color(1)
    # Keep text baseline >= y1 + 10 and width inside x2 - 2.
    safe_label = title[: max(1, int((x2 - x1 - 12) / (8 * 0.62)))]
    vdi_sm.v_gtext(x1 + 6, y1 + 14, safe_label)


def _draw_hex_pane(vdi_sm: GemVdiStateMachine, wr: GRECT, mesh: HexCollaborationMesh, active_name: str) -> None:
    """Draw 9-sister hex cell nodes and shared-wall edges inside `wr`."""
    cx = wr.g_x + wr.g_w // 2
    cy = wr.g_y + wr.g_h // 2 + 12
    cells = sorted(mesh.cells(), key=lambda c: c.sister.slot)
    pos_map: dict[str, tuple[int, int]] = {}
    for cell in cells:
        px = max(wr.g_x + 18, min(wr.g_x + wr.g_w - 18, cx + cell.coord.q * 28 + cell.coord.r * 14))
        py = max(wr.g_y + 30, min(wr.g_y + wr.g_h - 14, cy + cell.coord.r * 24))
        pos_map[cell.cell_id] = (px, py)
    vdi_sm.vsl_color(4)
    for cell_a, _direction, cell_b in mesh.shared_walls():
        if cell_a in pos_map and cell_b in pos_map:
            vdi_sm.v_pline([pos_map[cell_a], pos_map[cell_b]])
    vdi_sm.vsf_interior(FIS_SOLID)
    for cell in cells:
        px, py = pos_map[cell.cell_id]
        vdi_sm.vsf_color(2 if cell.sister.name == active_name else 3)
        vdi_sm.v_circle(px, py, 6)


def _draw_eddms_pane(vdi_sm: GemVdiStateMachine, wr: GRECT, record: EngineeringDesignRecord) -> None:
    """Draw central EDDBMS hub bar and revision badge inside `wr`."""
    x1, y1 = wr.g_x + 12, wr.g_y + 28
    x2, y2 = wr.g_x + wr.g_w - 12, wr.g_y + wr.g_h - 16
    vdi_sm.vsf_interior(FIS_SOLID)
    vdi_sm.vsf_color(5)
    vdi_sm.v_bar((x1, y1, x2, y1 + 26))
    vdi_sm.vst_height(8)
    vdi_sm.vst_color(1)
    vdi_sm.v_gtext(x1 + 4, y1 + 44, f"REV {record.revision}")
    vdi_sm.v_gtext(x1 + 4, y1 + 60, record.record_sha256[:12])


def _draw_spokes_or_pipeline_pane(vdi_sm: GemVdiStateMachine, wr: GRECT, labels: tuple[str, ...]) -> None:
    """Draw 3 stacked module/pipeline bars inside `wr`."""
    x1 = wr.g_x + 10
    x2 = wr.g_x + wr.g_w - 10
    vdi_sm.vsf_interior(FIS_SOLID)
    for idx, label in enumerate(labels[:3]):
        by1 = wr.g_y + 26 + idx * 34
        by2 = min(wr.g_y + wr.g_h - 8, by1 + 22)
        if by2 <= by1 + 4:
            continue
        vdi_sm.vsf_color(2 + idx)
        vdi_sm.v_bar((x1, by1, x2, by2))
        vdi_sm.vst_height(7)
        vdi_sm.v_gtext(x1 + 4, by1 + 14, label[:18])


def _draw_vdi_canvas_pane(vdi_sm: GemVdiStateMachine, wr: GRECT, design_id: str) -> None:
    """Draw concentric Spatial IR ellipse/circle motif inside `wr`."""
    cx = wr.g_x + wr.g_w // 2
    cy = wr.g_y + wr.g_h // 2 + 10
    rx = max(12, min(56, wr.g_w // 3))
    ry = max(10, min(36, (wr.g_h - 32) // 3))
    vdi_sm.vsf_interior(FIS_SOLID)
    vdi_sm.vsf_color(6)
    vdi_sm.v_ellipse(cx, cy, rx, ry)
    vdi_sm.vsf_color(4)
    vdi_sm.v_circle(cx, cy, max(6, min(rx, ry) // 2))
    vdi_sm.vst_height(7)
    vdi_sm.v_gtext(wr.g_x + 10, wr.g_y + wr.g_h - 10, design_id[:18])


def _draw_ablation_pane(
    vdi_sm: GemVdiStateMachine,
    wr: GRECT,
    report: AblationAdvisoryReport | None,
) -> None:
    """Draw read-only Ablation advisory status bar inside `wr`."""
    x1, y1 = wr.g_x + 10, wr.g_y + 28
    x2, y2 = wr.g_x + wr.g_w - 10, wr.g_y + 56
    vdi_sm.vsf_interior(FIS_SOLID)
    vdi_sm.vsf_color(3 if report is None else 2)
    vdi_sm.v_bar((x1, y1, x2, y2))
    vdi_sm.vst_height(7)
    status_txt = "ABLATION RO IDLE" if report is None else f"{report.target_name[:12]} {report.target_sha256[:8]}"
    vdi_sm.v_gtext(x1 + 4, y1 + 46, status_txt)
    vdi_sm.v_gtext(x1 + 4, y1 + 62, "advisory_only=True")


class CollaborativeGemWorkbench:
    """Unified 9-sister collaborative GEM workbench (<= 7 AES windows, 0 cloud tokens)."""

    def __init__(
        self,
        spec: FunctionEngineeringSpecification | None = None,
        *,
        screen_w: int = 640,
        screen_h: int = 400,
    ) -> None:
        self.spec: FunctionEngineeringSpecification = (
            spec if spec is not None else default_workbench_specification()
        )
        self.spec.validate()
        self.screen_w: int = int(screen_w)
        self.screen_h: int = int(screen_h)

        # M1 Hex mesh + M2 EDDBMS database
        self.mesh: HexCollaborationMesh = build_default_zoe_mesh()
        self.db: EngineeringDesignDatabase = EngineeringDesignDatabase()
        self.record: EngineeringDesignRecord = self.db.ingest_specification(self.spec)
        self.design_id: str = self.record.general.design_id
        self.active_sister: SisterModelSpec = resolve_sister("Zoe")
        self.latest_ablation: AblationAdvisoryReport | None = None
        self.ablation_bridge: AblationBridge = AblationBridge()

        # M3 GEM AES application, menu bar, centered status dialog, and 6 tiled panes (<= 7)
        self.aes_app: GemAesApplication = GemAesApplication("ZOE_WB")
        self.ap_id: int = self.aes_app.appl_init()
        self.window_mgr: GemAesWindowTreeManager = GemAesWindowTreeManager(
            self.screen_w,
            self.screen_h,
            event_app=self.aes_app,
        )
        self.menu_tree, self._sister_menu_indices = _build_menu_tree(self.screen_w)
        menu_bar(self.menu_tree, 1, app=self.aes_app)
        menu_icheck(self.menu_tree, self._sister_menu_indices[self.active_sister.name], 1)

        self.dialog_tree: list[GemObject] = _build_status_dialog_tree()
        self.dialog_rect: GRECT = form_center(
            self.dialog_tree, screen_w=self.screen_w, screen_h=self.screen_h
        )

        self._panes: dict[str, _PaneContext] = {}
        self._init_tiled_windows()
        self.aes_app.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=0)

    def _init_tiled_windows(self) -> None:
        """Create and open 6 non-overlapping AES windows (strictly <= MAX_AES_APP_WINDOWS)."""
        rects = _tiled_pane_rects(self.screen_w, self.screen_h)
        for (layer_id, title), rect in zip(_PANE_DEFS, rects):
            handle = self.window_mgr.wind_create(
                STANDARD_WORKBENCH_WINDOW_KIND,
                rect,
                title=title,
                info=f"{self.design_id} · rev={self.record.revision}",
                layer_id=layer_id,
            )
            if handle <= 0:
                raise RuntimeError(f"Failed to allocate AES window for {layer_id}")
            self.window_mgr.wind_open(handle, rect)
            self._panes[layer_id] = _PaneContext(
                layer_id=layer_id,
                title=title,
                handle=handle,
                outer_rect=rect,
            )
        self.window_mgr.wind_set(self._panes["hex_mesh"].handle, WF_TOP)

    def constitutional_metadata(
        self,
        epistemic_lane: str = "advisory_proposal",
        *,
        read_only: bool = True,
    ) -> dict[str, Any]:
        """Return Contract #1 constitutional metadata for the workbench."""
        return constitutional_metadata(epistemic_lane, read_only=read_only)

    def focus_sister(self, sister_query: str) -> SisterModelSpec:
        """Focus one of the 9 sisters inside the existing Hex Mesh window (no extra windows)."""
        sister = resolve_sister(sister_query)
        prev_idx = self._sister_menu_indices.get(self.active_sister.name)
        if prev_idx is not None:
            menu_icheck(self.menu_tree, prev_idx, 0)
        self.active_sister = sister
        next_idx = self._sister_menu_indices.get(sister.name)
        if next_idx is not None:
            menu_icheck(self.menu_tree, next_idx, 1)

        hex_pane = self._panes["hex_mesh"]
        self.window_mgr.wind_set(hex_pane.handle, WF_NAME, f"Hex Mesh: {sister.name}")
        self.window_mgr.wind_set(hex_pane.handle, WF_INFO, f"slot={sister.slot} · {sister.signet}")
        self.window_mgr.wind_set(hex_pane.handle, WF_TOP)
        self.aes_app.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=0)
        return sister

    select_sister = focus_sister
    open_sister_pane = focus_sister

    def tick_collaboration(self, ticks: int = 1) -> dict[str, Any]:
        """Advance hexagonal neighbor coupling, sync bidirectional EDDBMS, and pump AES events."""
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks < 1:
            raise ValueError(f"ticks must be a positive non-bool int, got {ticks!r}")

        cells = sorted(self.mesh.cells(), key=lambda c: c.sister.slot)
        for _step in range(ticks):
            for cell in cells:
                nbrs = self.mesh.neighbors(cell.cell_id)
                if nbrs:
                    self.mesh.send_neighbor_message(
                        cell.cell_id,
                        nbrs[0],
                        "workbench.tick.sync",
                        {
                            "design_id": self.design_id,
                            "sister": cell.sister.name,
                            "mesh_tick": self.mesh.tick + 1,
                        },
                        epistemic_lane="measurement",
                    )
            tick_res = self.mesh.step_coupled_tick()
            sub_op = EDDBMS_SUBOPERATION_KEYS["PROJECT_MANAGEMENT"][0]
            patch = {
                "geometric": {
                    "analysis_process_formats": {
                        "workbench_ticks": {
                            f"tick_{tick_res.tick}": {
                                "trace_sha256": tick_res.trace_sha256,
                                "active_sister": self.active_sister.name,
                            }
                        }
                    }
                },
                "sub_operations": {
                    sub_op: {"tick": tick_res.tick, "trace_sha256": tick_res.trace_sha256[:16]}
                },
                "notes": f"Workbench collaborative tick {tick_res.tick}",
            }
            self.record = self.db.write_from_module(
                self.design_id,
                "PROJECT_MANAGEMENT",
                self.active_sister.name,
                patch,
                expected_revision=self.record.revision,
                epistemic_lane="advisory_proposal",
                sub_operation=sub_op,
            )
            hub_pane = self._panes["eddms_hub"]
            self.window_mgr.wind_set(hub_pane.handle, WF_INFO, f"{self.design_id} · rev={self.record.revision}")
            self.aes_app.post_message(WM_REDRAW, self.ap_id, 0, hub_pane.handle, *hub_pane.outer_rect.as_tuple())
            self.aes_app.post_message(MN_SELECTED, self.ap_id, 0, 2, self._sister_menu_indices[self.active_sister.name])
            self.aes_app.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=0)

        return {
            "contract": WORKBENCH_CONTRACT,
            "ticks_executed": ticks,
            "mesh_tick": self.mesh.tick,
            "eddms_revision": self.record.revision,
            "record_sha256": self.record.record_sha256,
            "active_sister": self.active_sister.name,
            **constitutional_metadata("advisory_proposal", read_only=False),
        }

    def run_ablation_inspection(
        self,
        target_path: str | Path | None = None,
        *,
        raw_bytes: bytes | None = None,
        target_name: str = "memory",
        mode: str = "auto",
        attach_to_eddms: bool = True,
    ) -> AblationAdvisoryReport:
        """Invoke read-only Ablation inspection and optionally attach findings to EDDBMS."""
        report = self.ablation_bridge.inspect_target_readonly(
            target_path=target_path,
            raw_bytes=raw_bytes,
            target_name=target_name,
            mode=mode,
        )
        if attach_to_eddms:
            self.record = attach_ablation_to_eddms(
                self.db,
                self.design_id,
                report,
                sister_name="Mono",
                expected_revision=self.record.revision,
            )
        self.latest_ablation = report
        ab_pane = self._panes["ablation_advisor"]
        self.window_mgr.wind_set(ab_pane.handle, WF_INFO, f"{report.target_name} · sha={report.target_sha256[:12]}")
        return report

    def _build_vdi_and_scene(self) -> tuple[Scene, bytes]:
        """Deterministically render all 6 tiled panes via Balma & Fitler VDI/AES redraw clipping (read-only)."""
        vdi_sm = GemVdiStateMachine()
        vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, 1, 1, 1, RC_MODE], width=self.screen_w, height=self.screen_h)
        vdi_sm.vswr_mode(MD_REPLACE)
        self.window_mgr.wind_update(BEG_UPDATE)
        try:
            for idx, (layer_id, _default_title) in enumerate(_PANE_DEFS):
                pane = self._panes[layer_id]
                work_rect = self.window_mgr.wind_get(pane.handle, "work_rect")
                for clip_rect in self.window_mgr.walk_redraw_rectangles(pane.handle, work_rect):
                    cx1, cy1 = clip_rect.g_x, clip_rect.g_y
                    cx2 = min(self.screen_w - 1, cx1 + clip_rect.g_w - 1)
                    cy2 = min(self.screen_h - 1, cy1 + clip_rect.g_h - 1)
                    vdi_sm.vs_clip(CLIP_ON, [cx1, cy1, cx2, cy2])
                    meta = self.window_mgr.wind_get(pane.handle, "meta")
                    _draw_pane_header(vdi_sm, clip_rect, str(meta["title"]), color_idx=1 + (idx % 6))
                    self._render_pane_content(vdi_sm, layer_id, clip_rect)
            vdi_sm.vs_clip(CLIP_OFF, [0, 0, self.screen_w, self.screen_h])
        finally:
            self.window_mgr.wind_update(END_UPDATE)

        scene = vdi_sm.to_scene(scene_id=f"zoe-gem-workbench-{self.design_id}")
        gem_bytes = vdi_sm.to_gem_metafile()
        vdi_sm.v_clsvwk()
        return scene, gem_bytes

    def _render_pane_content(self, vdi_sm: GemVdiStateMachine, layer_id: str, wr: GRECT) -> None:
        """Render deterministic pane-specific VDI geometry without mutating workbench state."""
        if layer_id == "hex_mesh":
            _draw_hex_pane(vdi_sm, wr, self.mesh, self.active_sister.name)
        elif layer_id == "eddms_hub":
            _draw_eddms_pane(vdi_sm, wr, self.record)
        elif layer_id == "eddms_spokes":
            _draw_spokes_or_pipeline_pane(vdi_sm, wr, EDDBMS_DOMAIN_MODULES[:3])
        elif layer_id == "eddms_pipeline":
            _draw_spokes_or_pipeline_pane(vdi_sm, wr, EDDBMS_DOMAIN_MODULES[3:])
        elif layer_id == "vdi_canvas":
            _draw_vdi_canvas_pane(vdi_sm, wr, self.design_id)
        else:
            _draw_ablation_pane(vdi_sm, wr, self.latest_ablation)

    def render_vdi_scene(self) -> Scene:
        """Render a verified Spatial IR v1 `Scene` (read-only, deterministic)."""
        scene, _gem_bytes = self._build_vdi_and_scene()
        geom_rep = geometry.verify(scene)  # type: ignore[no-untyped-call]
        if not geom_rep.passed:
            raise ValueError(f"Workbench VDI scene failed geometry verification: {geom_rep.issues}")
        vdi_rep = runner.verify_vdi(scene)  # type: ignore[no-untyped-call]
        if not vdi_rep.passed:
            raise ValueError(f"Workbench VDI scene failed round-trip verification: {vdi_rep.issues}")
        return scene

    def render_svg(self, width: int = 1200) -> str:
        """Render deterministic SVG view of the workbench VDI scene (read-only)."""
        return str(scene_to_svg(self.render_vdi_scene(), width=width))  # type: ignore[no-untyped-call]

    def export_svg(
        self,
        path: str | Path | None = None,
        *,
        width: int = 1200,
        overwrite: bool = False,
    ) -> str:
        """Export deterministic SVG markup with no-silent-overwrite and path-safety guards."""
        svg_text = self.render_svg(width=width)
        if path is not None:
            dest = _prepare_export_dest(
                path,
                kind="SVG",
                label="SVG export path",
                overwrite=overwrite,
            )
            mode = "w" if overwrite else "x"
            with dest.open(mode, encoding="utf-8") as handle:
                handle.write(svg_text)
        return svg_text

    def export_gem_metafile(
        self,
        path: str | Path | None = None,
        *,
        overwrite: bool = False,
    ) -> bytes:
        """Export deterministic `.GEM` metafile bytes with no-silent-overwrite protection."""
        _scene, gem_bytes = self._build_vdi_and_scene()
        report = seasip_gem.verify_seasip_gem_metafile(gem_bytes)
        if not report.get("valid", False):
            raise ValueError(f"Generated workbench GEM metafile failed verification: {report}")
        if path is not None:
            dest = _prepare_export_dest(
                path,
                kind="GEM",
                label="GEM metafile path",
                overwrite=overwrite,
            )
            mode = "wb" if overwrite else "xb"
            with dest.open(mode) as handle:
                handle.write(gem_bytes)
        return gem_bytes

    def sync_gem_lab(
        self,
        session_dir: str | Path,
        *,
        target: str | Path | None = None,
    ) -> dict[str, Any]:
        """Transactionally read `gem state` and emit an EDDBMS/Ablation observation to GEM-Lab."""
        _ensure_gem_lab_sys_path()
        from gem.events import Session

        clean_dir = _validate_no_symlink_or_traversal(session_dir, label="GEM-Lab session dir")
        _validate_gem_lab_session_dir(clean_dir)
        clean_target = _validate_no_symlink_or_traversal(target, label="GEM-Lab target") if target is not None else None
        if clean_target is not None:
            if not os.path.lexists(clean_target):
                raise FileNotFoundError(f"GEM-Lab target not found: {clean_target}")
            t_st = os.lstat(clean_target)
            if not (stat.S_ISREG(t_st.st_mode) or stat.S_ISDIR(t_st.st_mode)):
                raise ValueError(
                    f"GEM-Lab target must be a regular file or directory (special file rejected): {clean_target}"
                )
        if clean_target is None and not (clean_dir / "session.json").exists():
            raise ValueError(f"GEM-Lab session is uninitialized and no target was supplied: {clean_dir}")

        session = Session(clean_dir, binary=clean_target)
        state = session.current_state()
        ablation_sha = self.latest_ablation.target_sha256 if self.latest_ablation is not None else "none"
        node_id = f"obs:workbench:{self.design_id}:rev{self.record.revision}"
        if node_id not in session.events_by_id():
            session.emit(
                node_id,
                session.root_id,
                "observation",
                f"Workbench rev={self.record.revision}",
                "in_progress",
                "tool",
                f"eddms={self.record.record_sha256};ablation={ablation_sha}",
                f"9-sister workbench sync ({self.active_sister.name})",
            )
        return {
            "session_root": str(session.root),
            "emitted_id": node_id,
            "state": session.current_state(),
            "prior_revision": state.get("revision"),
            "constitutional": constitutional_metadata("advisory_proposal", read_only=False),
        }

    def snapshot_state(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot of all 9 sisters, <=7 AES windows, EDDBMS, and Ablation."""
        open_windows = [
            self.window_mgr.wind_get(self._panes[layer_id].handle, "meta")
            for layer_id, _title in _PANE_DEFS
        ]
        sisters_list = [
            {
                "name": c.sister.name,
                "slot": c.sister.slot,
                "signet": c.sister.signet,
                "coord": [c.coord.q, c.coord.r],
                "domain_module": c.domain_module,
            }
            for c in sorted(self.mesh.cells(), key=lambda cell: cell.sister.slot)
        ]
        ablation_summary: dict[str, Any]
        if self.latest_ablation is not None:
            ablation_summary = self.latest_ablation.to_dict()
        else:
            ablation_summary = {
                "status": "not_run",
                "advisory_only": True,
                "read_only": True,
                "epistemic_lane": "measurement",
                "external_actions": 0,
                "tokens_used": 0,
                "cloud_cost_usd": 0.0,
            }
        meta = constitutional_metadata("advisory_proposal", read_only=True)
        return {
            "contract": WORKBENCH_CONTRACT,
            "design_id": self.design_id,
            "spec_id": self.spec.spec_id,
            "eddms_revision": self.record.revision,
            "record_sha256": self.record.record_sha256,
            "pipeline_stage": self.record.pipeline_stage,
            "mesh_tick": self.mesh.tick,
            "active_sister": self.active_sister.name,
            "sisters": sisters_list,
            "open_windows": open_windows,
            "window_count": len(open_windows),
            "max_aes_app_windows": MAX_AES_APP_WINDOWS,
            "ablation": ablation_summary,
            "snapshot_sha256": sha256_canonical(
                {
                    "design_id": self.design_id,
                    "eddms_revision": self.record.revision,
                    "record_sha256": self.record.record_sha256,
                    "mesh_tick": self.mesh.tick,
                    "active_sister": self.active_sister.name,
                }
            ),
            "constitutional": copy.deepcopy(meta),
            "safety_invariants": copy.deepcopy(meta),
        }


def create_workbench(
    spec: FunctionEngineeringSpecification | None = None,
    *,
    screen_w: int = 640,
    screen_h: int = 400,
) -> CollaborativeGemWorkbench:
    """Create and initialize a 9-sister collaborative GEM workbench (<= 7 AES windows)."""
    return CollaborativeGemWorkbench(spec, screen_w=screen_w, screen_h=screen_h)


def sync_gem_lab(
    session_dir: str | Path,
    workbench: CollaborativeGemWorkbench | None = None,
    *,
    target: str | Path | None = None,
) -> dict[str, Any]:
    """Convenience helper syncing a workbench (or fresh default workbench) with GEM-Lab."""
    wb = workbench if workbench is not None else create_workbench()
    return wb.sync_gem_lab(session_dir, target=target)


__all__ = [
    "ATTRIBUTION_TEXT",
    "SAFETY_INVARIANTS",
    "STANDARD_WORKBENCH_WINDOW_KIND",
    "WORKBENCH_CONTRACT",
    "CollaborativeGemWorkbench",
    "constitutional_metadata",
    "create_workbench",
    "default_workbench_specification",
    "sync_gem_lab",
]
