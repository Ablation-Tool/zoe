"""Unit tests for Milestone M3: Digital Research GEM AES/VDI Core (Balma & Fitler 1986)."""

from __future__ import annotations

from dataclasses import fields
import struct
from typing import Any

import pytest

from guiai.gem import geometry, runner, seasip_gem, vdi, zoe_atari_gem_rsc
from guiai.gem.zoe_gem_aes_vdi_core import (
    AC_CLOSE,
    AC_OPEN,
    ATTRIBUTION_TEXT,
    BEG_MCTRL,
    BEG_UPDATE,
    CHECKED,
    CLIP_OFF,
    CLIP_ON,
    CLOSER,
    DEFAULT,
    DISABLED,
    DNARROW,
    EDITABLE,
    END_MCTRL,
    END_UPDATE,
    EXIT,
    FIS_HOLLOW,
    FIS_PATTERN,
    FIS_SOLID,
    FMD_FINISH,
    FMD_GROW,
    FMD_SHRINK,
    FMD_START,
    FULLER,
    GRECT,
    G_BOX,
    G_BUTTON,
    G_FTEXT,
    G_ICON,
    G_STRING,
    G_TEXT,
    G_TITLE,
    HIDETREE,
    HSLIDE,
    INFO,
    LASTOB,
    LFARROW,
    MAX_AES_APP_WINDOWS,
    MD_ERASE,
    MD_REPLACE,
    MD_TRANS,
    MD_XOR,
    MN_SELECTED,
    MOVER,
    MU_BUTTON,
    MU_KEYBD,
    MU_M1,
    MU_M2,
    MU_MESAG,
    MU_TIMER,
    NAME,
    NDC_MODE,
    NIL,
    NORMAL,
    OUTLINED,
    RBUTTON,
    RC_MODE,
    ROOT,
    RTARROW,
    R_BIPDATA,
    R_BITBLK,
    R_FRIMG,
    R_FRSTR,
    R_IBPDATA,
    R_IBPMASK,
    R_IBPTEXT,
    R_ICONBLK,
    R_IMAGEDATA,
    R_OBJECT,
    R_OBSPEC,
    R_STRING,
    R_TEDINFO,
    R_TEPTEXT,
    R_TEPTMPLT,
    R_TEPVALID,
    R_TREE,
    SELECTABLE,
    SELECTED,
    SIZER,
    STANDARD_WINDOW_KIND,
    TOUCHEXIT,
    UPARROW,
    VSLIDE,
    WC_BORDER,
    WC_WORK,
    WF_CURRXYWH,
    WF_FIRSTXYWH,
    WF_FULLXYWH,
    WF_HSLIDE,
    WF_INFO,
    WF_NAME,
    WF_NEXTXYWH,
    WF_PREVXYWH,
    WF_TOP,
    WF_VSLIDE,
    WF_WORKXYWH,
    WM_CLOSED,
    WM_NEWTOP,
    WM_REDRAW,
    WM_TOPPED,
    WM_UNTOPPED,
    GemAesApplication,
    GemAesKernel,
    GemAesWindowTreeManager,
    GemObject,
    GemObjectTreeOps,
    GemResourceManager,
    GemVdiStateMachine,
    constitutional_metadata,
    decode_aes_message,
    form_alert,
    form_center,
    form_dial,
    form_do,
    menu_bar,
    menu_icheck,
    menu_ienable,
    menu_tnormal,
    rsrc_free,
    rsrc_gaddr,
    rsrc_load,
    rsrc_obfix,
)


def _make_sample_dialog_tree() -> list[GemObject]:
    """Build a valid dialog tree with EDITABLE, RBUTTONs, DISABLED, DEFAULT, EXIT, TOUCHEXIT."""
    return [
        # 0: ROOT dialog box (200x160)
        GemObject(
            ob_next=NIL, ob_head=1, ob_tail=6, ob_type=G_BOX,
            ob_flags=0, ob_state=OUTLINED, ob_x=0, ob_y=0, ob_w=200, ob_h=160,
        ),
        # 1: EDITABLE text field
        GemObject(
            ob_next=2, ob_head=NIL, ob_tail=NIL, ob_type=G_FTEXT,
            ob_flags=EDITABLE, ob_state=NORMAL, ob_x=10, ob_y=10, ob_w=180, ob_h=16,
            text="ZOE",
        ),
        # 2: Radio button group container (G_BOX)
        GemObject(
            ob_next=4, ob_head=3, ob_tail=3, ob_type=G_BOX,
            ob_flags=0, ob_state=NORMAL, ob_x=10, ob_y=36, ob_w=180, ob_h=44,
        ),
        # 3: Hidden placeholder — we'll place radio children inside container 2 properly below
        # Wait: let's make 3 & 4 children of 2, and 5, 6 children of 0:
        GemObject(
            ob_next=NIL, ob_head=NIL, ob_tail=NIL, ob_type=G_BUTTON,
            ob_flags=SELECTABLE | RBUTTON, ob_state=SELECTED, ob_x=4, ob_y=4, ob_w=80, ob_h=16,
            text="Opt A",
        ),
        GemObject(
            ob_next=NIL, ob_head=NIL, ob_tail=NIL, ob_type=G_BUTTON,
            ob_flags=SELECTABLE | RBUTTON, ob_state=NORMAL, ob_x=90, ob_y=4, ob_w=80, ob_h=16,
            text="Opt B",
        ),
        # 5: Disabled button
        GemObject(
            ob_next=6, ob_head=NIL, ob_tail=NIL, ob_type=G_BUTTON,
            ob_flags=SELECTABLE | EXIT, ob_state=DISABLED, ob_x=10, ob_y=120, ob_w=50, ob_h=20,
            text="Lock",
        ),
        # 6: Default OK EXIT button
        GemObject(
            ob_next=7, ob_head=NIL, ob_tail=NIL, ob_type=G_BUTTON,
            ob_flags=SELECTABLE | DEFAULT | EXIT, ob_state=NORMAL, ob_x=70, ob_y=120, ob_w=50, ob_h=20,
            text="OK",
        ),
        # 7: TOUCHEXIT button (LASTOB)
        GemObject(
            ob_next=0, ob_head=NIL, ob_tail=NIL, ob_type=G_BUTTON,
            ob_flags=SELECTABLE | TOUCHEXIT | LASTOB, ob_state=NORMAL, ob_x=130, ob_y=120, ob_w=50, ob_h=20,
            text="Help",
        ),
    ]


def _wired_dialog_tree() -> list[GemObject]:
    tree = _make_sample_dialog_tree()
    # Fix links cleanly for container 2 (children 3 and 4) and root 0 (children 1, 2, 5, 6, 7)
    tree[0].ob_head = 1
    tree[0].ob_tail = 7
    tree[1].ob_next = 2
    tree[2].ob_next = 5
    tree[2].ob_head = 3
    tree[2].ob_tail = 4
    tree[3].ob_next = 4
    tree[4].ob_next = 2
    tree[5].ob_next = 6
    tree[6].ob_next = 7
    tree[7].ob_next = 0
    return tree


# ============================================================================
# 1. Constitutional Metadata & Invariants (PROJECT.md § 1)
# ============================================================================

def test_constitutional_metadata_invariants_and_lane_guard() -> None:
    meta = constitutional_metadata()
    assert meta["epistemic_lane"] == "measurement"
    assert meta["measurement_lane_only"] is True
    assert meta["visual_evidence_only"] is True
    assert meta["advisory_only"] is True
    assert meta["read_only"] is True
    assert meta["external_actions"] == 0
    assert meta["tokens_used"] == 0
    assert meta["cloud_cost_usd"] == 0.0
    assert meta["loopback_only"] is True
    assert meta["sentience_claimed"] is False
    assert meta["l5_agi_qualified"] is False
    assert meta["zoe_clone_claimed"] is False
    assert meta["clinical_action_authorized"] is False
    assert meta["flight_control_authorized"] is False
    assert meta["cure_claim"] is False
    assert meta["wet_lab_validation_required"] is True
    assert meta["attribution"] == ATTRIBUTION_TEXT
    assert "Gary Kildall" in meta["historical_credit"]

    adv = constitutional_metadata(epistemic_lane="advisory_proposal")
    assert adv["measurement_lane_only"] is False
    assert adv["advisory_only"] is True

    with pytest.raises(ValueError):
        constitutional_metadata(epistemic_lane="action")
    with pytest.raises(ValueError):
        constitutional_metadata(epistemic_lane="unknown_lane")


# ============================================================================
# 2. Feature #7: GemAesApplication & 16-Byte FIFO Message Pipe
# ============================================================================

def test_aes_application_lifecycle_and_appl_find_write_read() -> None:
    kernel = GemAesKernel()
    app1 = GemAesApplication("ZOE_MAIN", kernel=kernel)
    app2 = GemAesApplication("GEM_MON", kernel=kernel)

    with pytest.raises(RuntimeError):
        app1.evnt_timer(0)

    id1 = app1.appl_init()
    id2 = app2.appl_init()
    assert id1 == 0
    assert id2 == 1
    assert app1.appl_find("GEM_MON") == 1
    assert app1.appl_find("GEM_MON ") == 1
    assert app1.appl_find("MISSING") == -1

    # Write 16-byte message + 6 extra bytes (msg[2] = 6 > 0) from app1 to app2
    extra = b"ZOEEXT"
    written = app1.appl_write(
        id2,
        16 + len(extra),
        [WM_REDRAW, id1, len(extra), 1, 10, 20, 100, 80],
        extra_bytes=extra,
    )
    assert written == 22

    ev = app2.evnt_multi(MU_MESAG | MU_TIMER, timer_ms=0)
    assert ev.matched_flags == MU_MESAG
    assert ev.message is not None
    assert ev.message["msg_type"] == WM_REDRAW
    assert ev.message["extra_len"] == 6
    assert ev.extra_bytes_pending == 6
    assert ev.to_dict()["constitutional"]["external_actions"] == 0

    # Read remaining extra bytes using appl_read
    tail = app2.appl_read(id2, ev.message["extra_len"])
    assert tail == extra
    assert app2.pending_bytes() == 0

    assert app1.appl_exit() == 1
    assert app1.appl_exit() == 0
    assert app2.appl_exit() == 1


def test_aes_fifo_pipe_and_predefined_messages() -> None:
    app = GemAesApplication("PIPE_APP")
    app.appl_init()
    app.post_message(AC_OPEN, 0, 0, 0, 3)
    app.post_message(WM_UNTOPPED, 0, 0, 1, 2)
    app.post_message(AC_CLOSE, 0, 0, 3)

    m1 = app.evnt_mesag()
    m2 = app.evnt_mesag()
    m3 = app.evnt_mesag()
    m4 = app.evnt_mesag()
    assert m1 is not None and m1["msg_type"] == AC_OPEN and m1["data"][1] == 3
    assert m2 is not None and m2["msg_type"] == WM_UNTOPPED and m2["data"][:2] == [1, 2]
    assert m3 is not None and m3["msg_type"] == AC_CLOSE and m3["data"][0] == 3
    assert m4 is None

    with pytest.raises(ValueError):
        app.post_message(WM_REDRAW, 0, 0, 40000)  # int16 overflow
    with pytest.raises(ValueError):
        app.post_message(True, 0)


def test_evnt_multi_half_open_m1_m2_button_keybd_timer() -> None:
    app = GemAesApplication("EV_APP")
    app.appl_init()

    rect = GRECT(10, 20, 100, 50)  # [10, 110) x [20, 70)
    # Inside M1 -> enter (m1_flag=0) fires; right/bottom edge (110, 70) is outside!
    r_in = app.evnt_multi(MU_M1, m1_flag=0, m1_rect=rect, mouse_x=10, mouse_y=20)
    assert r_in.matched_flags == MU_M1

    r_edge = app.evnt_multi(MU_M1 | MU_M2, m1_flag=0, m1_rect=rect, m2_flag=1, m2_rect=rect, mouse_x=110, mouse_y=70)
    assert r_edge.matched_flags == MU_M2  # outside half-open boundary

    r_btn_key = app.evnt_multi(
        MU_KEYBD | MU_BUTTON | MU_TIMER,
        bclicks=2, bmask=1, bstate=1,
        button_state=1, clicks=2,
        key_code=0x1C0D, kstate=4,
        timer_ms=50,
    )
    assert r_btn_key.matched_flags == (MU_KEYBD | MU_BUTTON | MU_TIMER)
    assert r_btn_key.kreturn == 0x1C0D
    assert r_btn_key.kstate == 4
    assert r_btn_key.breturn == 2

    assert app.evnt_dclick(3, setit=1) == 3
    with pytest.raises(ValueError):
        app.evnt_multi(0)
    with pytest.raises(ValueError):
        app.evnt_multi(0x0040)


# ============================================================================
# 3. Feature #8: GemAesWindowTreeManager & Rectangle-List Redraw
# ============================================================================

def test_window_7_cap_zorder_and_lifecycle() -> None:
    app = GemAesApplication("WIN_APP")
    app.appl_init()
    mgr = GemAesWindowTreeManager(640, 400, event_app=app)

    handles = [
        mgr.wind_create(STANDARD_WINDOW_KIND, (10 + i * 20, 20 + i * 10, 200, 150), title=f"W{i}")
        for i in range(MAX_AES_APP_WINDOWS)
    ]
    assert handles == [1, 2, 3, 4, 5, 6, 7]
    # 8th window returns -1
    assert mgr.wind_create(NAME, (0, 0, 100, 100)) == -1

    # Closing window 7 keeps slot occupied until wind_delete
    mgr.wind_open(1)
    mgr.wind_open(2)
    assert mgr.top_handle == 2
    assert mgr.wind_find(5, 5) == 0
    assert mgr.wind_find(25, 35) == 1
    assert mgr.wind_find(40, 40) == 2

    mgr.wind_set(1, WF_TOP)
    assert mgr.top_handle == 1
    assert mgr.wind_find(40, 40) == 1
    assert mgr.wind_get(1, WF_TOP) == 1

    mgr.wind_close(1)
    assert mgr.top_handle == 2
    assert mgr.wind_create(NAME, (0, 0, 100, 100)) == -1

    mgr.wind_delete(7)
    reused = mgr.wind_create(NAME, (0, 0, 120, 90), title="Reused")
    assert reused == 7

    with pytest.raises(ValueError):
        mgr.wind_close(0)
    with pytest.raises(ValueError):
        mgr.wind_delete(0)


def test_wind_calc_exact_roundtrip_and_wind_update_balance() -> None:
    mgr = GemAesWindowTreeManager(640, 480)
    work = GRECT(50, 60, 300, 200)
    for kind in (0, NAME, NAME | INFO, STANDARD_WINDOW_KIND, STANDARD_WINDOW_KIND | HSLIDE | LFARROW | RTARROW):
        border = mgr.wind_calc(WC_BORDER, kind, work)
        roundtrip = mgr.wind_calc(WC_WORK, kind, border)
        assert roundtrip == work

    with pytest.raises(ValueError):
        mgr.wind_calc(WC_WORK, STANDARD_WINDOW_KIND, (0, 0, 10, 10))

    # Balanced wind_update
    assert mgr.wind_update(BEG_UPDATE) == 1
    assert mgr.wind_update(BEG_UPDATE) == 1
    assert mgr.update_lock_depth == 2
    assert mgr.wind_update(END_UPDATE) == 1
    assert mgr.wind_update(END_UPDATE) == 1
    assert mgr.update_lock_depth == 0
    with pytest.raises(ValueError):
        mgr.wind_update(END_UPDATE)

    assert mgr.wind_update(BEG_MCTRL) == 1
    assert mgr.mctrl_lock_depth == 1
    assert mgr.wind_update(END_MCTRL) == 1
    with pytest.raises(ValueError):
        mgr.wind_update(END_MCTRL)


def test_walk_redraw_rectangles_occlusion_and_dirty_clip() -> None:
    mgr = GemAesWindowTreeManager(640, 480)
    # Create plain border windows (kind=0 -> 2px border) for exact coordinate reasoning
    h1 = mgr.wind_create(0, (100, 100, 204, 204))  # work rect: (102, 102, 200, 200)
    h2 = mgr.wind_create(0, (150, 150, 100, 100))  # occludes center of h1's work rect
    mgr.wind_open(h1)
    mgr.wind_open(h2)

    # Full dirty rect covers h1's work area -> split into 4 non-overlapping strips around h2
    frags = mgr.walk_redraw_rectangles(h1, (102, 102, 200, 200))
    assert len(frags) == 4
    total_area = sum(r.g_w * r.g_h for r in frags)
    assert total_area == (200 * 200) - (100 * 100)
    # Verify pairwise disjointness
    for i, a in enumerate(frags):
        for b in frags[i + 1 :]:
            assert a.intersect(b) is None

    # Disjoint dirty rect -> []
    assert mgr.walk_redraw_rectangles(h1, (0, 0, 50, 50)) == []

    # Raw WF_FIRSTXYWH / WF_NEXTXYWH terminates with (0, 0, 0, 0)
    raw_rects: list[GRECT] = []
    cur = mgr.wind_get(h1, WF_FIRSTXYWH)
    while cur.g_w > 0 and cur.g_h > 0:
        raw_rects.append(cur)
        cur = mgr.wind_get(h1, WF_NEXTXYWH)
    assert cur == GRECT(0, 0, 0, 0)
    assert raw_rects == frags

    # Complete occlusion yields []
    h3 = mgr.wind_create(0, (90, 90, 250, 250))
    mgr.wind_open(h3)
    assert mgr.walk_redraw_rectangles(h1, (0, 0, 640, 480)) == []


# ============================================================================
# 4. Feature #9: Object Tree, Form, Menu & Resource Manager
# ============================================================================

def test_gem_object_11_fields_and_tree_ops_validation() -> None:
    field_names = [f.name for f in fields(GemObject)]
    assert field_names[:11] == [
        "ob_next", "ob_head", "ob_tail", "ob_type", "ob_flags",
        "ob_state", "ob_spec", "ob_x", "ob_y", "ob_w", "ob_h",
    ]
    assert field_names[11:] == ["text"]

    tree = [
        GemObject(ob_next=NIL, ob_head=NIL, ob_tail=NIL, ob_type=G_BOX, ob_x=10, ob_y=20, ob_w=200, ob_h=120),
        GemObject(ob_type=G_BUTTON, ob_flags=SELECTABLE, ob_x=10, ob_y=15, ob_w=60, ob_h=20, text="A"),
        GemObject(ob_type=G_BUTTON, ob_flags=SELECTABLE | LASTOB, ob_x=80, ob_y=15, ob_w=60, ob_h=20, text="B"),
    ]
    assert GemObjectTreeOps.objc_add(tree, 0, 1) == 1
    assert GemObjectTreeOps.objc_add(tree, 0, 2) == 1
    GemObjectTreeOps.validate_tree(tree)

    # Offsets & hit-testing
    assert GemObjectTreeOps.objc_offset(tree, 1) == (20, 35)
    assert GemObjectTreeOps.objc_find(tree, 0, 5, 25, 40) == 1
    assert GemObjectTreeOps.objc_find(tree, 0, 5, 95, 40) == 2

    # HIDETREE suppresses hit-test & draw
    tree[1].ob_flags |= HIDETREE
    assert GemObjectTreeOps.objc_find(tree, 0, 5, 25, 40) == 0  # hits root box, not hidden child
    drawn = GemObjectTreeOps.objc_draw(tree, 0, 5, (0, 0, 300, 200))
    assert [op["obj_idx"] for op in drawn] == [0, 2]
    tree[1].ob_flags &= ~HIDETREE

    # Reorder & change
    assert GemObjectTreeOps.objc_order(tree, 2, 0) == 1
    assert tree[0].ob_head == 2 and tree[0].ob_tail == 1
    ch = GemObjectTreeOps.objc_change(tree, 1, SELECTED, redraw=True)
    assert ch["ob_state"] == SELECTED and len(ch["draw_ops"]) == 1

    # Seasip roundtrip
    stree = GemObjectTreeOps.to_seasip_tree(tree, name="SAMPLE")
    back = GemObjectTreeOps.from_seasip_tree(stree)
    assert len(back) == 3
    assert back[-1].ob_flags & LASTOB

    # Delete & negative guards
    assert GemObjectTreeOps.objc_delete(tree, 2) == 1
    with pytest.raises(ValueError):
        GemObjectTreeOps.objc_delete(tree, 0)  # cannot delete ROOT
    with pytest.raises(ValueError):
        GemObjectTreeOps.objc_add(tree, 1, 1)  # self-cycle
    with pytest.raises(ValueError):
        GemObjectTreeOps.objc_add(tree, 1, 0)  # adding ROOT

    # Missing LASTOB & cycle detection
    bad = [GemObject(ob_next=NIL, ob_w=10, ob_h=10)]
    with pytest.raises(ValueError):
        GemObjectTreeOps.validate_tree(bad)


def test_form_center_dial_do_and_alert() -> None:
    tree = _wired_dialog_tree()
    centered = form_center(tree, screen_w=640, screen_h=400)
    assert tree[0].ob_x == 220 and tree[0].ob_y == 120
    assert centered == GRECT(217, 117, 206, 166)  # +3px OUTLINED margin

    d1 = form_dial(FMD_START, (0, 0, 10, 10), centered)
    d2 = form_dial(FMD_FINISH, (0, 0, 10, 10), centered)
    assert d1["flag_name"] == "FMD_START"
    assert d2["flag_name"] == "FMD_FINISH"
    assert d1["constitutional"]["advisory_only"] is True

    # Click Opt B (radio mutual exclusion), click disabled Lock (ignored), type into EDITABLE, double-click TOUCHEXIT
    ax_b, ay_b = GemObjectTreeOps.objc_offset(tree, 4)
    ax_lock, ay_lock = GemObjectTreeOps.objc_offset(tree, 5)
    ax_help, ay_help = GemObjectTreeOps.objc_offset(tree, 7)

    res = form_do(
        tree,
        1,
        [
            {"type": "click", "x": ax_b + 5, "y": ay_b + 5},
            {"type": "click", "x": ax_lock + 5, "y": ay_lock + 5},
            {"type": "key", "char": "!"},
            {"type": "click", "x": ax_help + 5, "y": ay_help + 5, "clicks": 2},
        ],
    )
    assert not (tree[3].ob_state & SELECTED)  # Opt A deselected by RBUTTON
    assert bool(tree[4].ob_state & SELECTED)  # Opt B selected
    assert not (tree[5].ob_state & SELECTED)  # DISABLED ignored
    assert tree[1].text == "ZOE!"
    assert res["exit_obj"] == 7
    assert res["double_click"] is True
    assert res["exit_raw"] == (7 | 0x8000)

    # Return key triggers DEFAULT button
    tree2 = _wired_dialog_tree()
    res_def = form_do(tree2, 1, [{"type": "key", "key_code": 0x1C0D}])
    assert res_def["exit_obj"] == 6
    assert res_def["double_click"] is False

    # form_alert
    al_str = seasip_gem.build_form_alert(2, ["Verify GEM Core?"], ["Yes", "No"])
    al_res = form_alert(1, al_str, button_choice=2)
    assert al_res["icon"] == 2
    assert al_res["selected_label"] == "No"
    assert al_res["constitutional"]["external_actions"] == 0


def test_menu_bar_icheck_ienable_tnormal_emits_mn_selected() -> None:
    app = GemAesApplication("MENU_APP")
    app.appl_init()

    menu_tree = [
        GemObject(ob_next=NIL, ob_head=1, ob_tail=2, ob_type=G_BOX, ob_w=640, ob_h=200),
        GemObject(ob_next=2, ob_head=NIL, ob_tail=NIL, ob_type=G_TITLE, ob_x=10, ob_y=0, ob_w=40, ob_h=16, text="File"),
        GemObject(ob_next=0, ob_head=3, ob_tail=4, ob_type=G_BOX, ob_x=10, ob_y=16, ob_w=100, ob_h=40),
        GemObject(ob_next=4, ob_head=NIL, ob_tail=NIL, ob_type=G_STRING, ob_x=0, ob_y=0, ob_w=100, ob_h=16, text="Open"),
        GemObject(ob_next=2, ob_head=NIL, ob_tail=NIL, ob_type=G_STRING, ob_flags=LASTOB, ob_x=0, ob_y=16, ob_w=100, ob_h=16, text="Quit"),
    ]
    bar = menu_bar(menu_tree, 1, app=app)
    assert bar["visible"] is True

    menu_icheck(menu_tree, 3, 1)
    assert menu_tree[3].ob_state & CHECKED
    menu_icheck(menu_tree, 3, 0)
    assert not (menu_tree[3].ob_state & CHECKED)

    menu_ienable(menu_tree, 4, 0)
    assert menu_tree[4].ob_state & DISABLED
    with pytest.raises(ValueError):
        menu_tnormal(menu_tree, 1, 0, app=app, item_idx=4)

    menu_ienable(menu_tree, 4, 1)
    menu_tnormal(menu_tree, 1, 0, app=app, item_idx=4)
    assert menu_tree[1].ob_state & SELECTED
    ev = app.evnt_multi(MU_MESAG)
    assert ev.matched_flags == MU_MESAG
    assert ev.message is not None
    assert ev.message["msg_type"] == MN_SELECTED
    assert ev.message["data"][:2] == [1, 4]
    menu_tnormal(menu_tree, 1, 1)
    assert not (menu_tree[1].ob_state & SELECTED)


def test_rsrc_load_gaddr_all_types_dual_endian_and_obfix() -> None:
    # 1. Little-endian PC GEM .RSC from seasip_gem.compile_rsc (with G_TEXT TEDINFO + G_BUTTON)
    stree = seasip_gem.GemObjectTree("MAIN", 200, 120)
    stree.add(G_TEXT, 10, 10, 120, 16, text="Header")
    stree.add(G_BUTTON, 10, 40, 80, 20, flags=SELECTABLE | EXIT, text="Close")
    le_rsc = seasip_gem.compile_rsc([stree], endian="<")

    assert rsrc_load(le_rsc) == 1
    t0 = rsrc_gaddr(R_TREE, 0)
    assert len(t0) == 3
    assert rsrc_gaddr(R_OBJECT, 2).text == "Close"
    assert rsrc_gaddr(R_TEDINFO, 0)["te_ptext"] == "Header"
    assert rsrc_gaddr(R_TEPTEXT, 0) == "Header"
    assert rsrc_gaddr(R_TEPTMPLT, 0) == ""
    assert rsrc_gaddr(R_TEPVALID, 0) == ""
    assert rsrc_gaddr(R_STRING, 0) == "Header"
    assert isinstance(rsrc_gaddr(R_OBSPEC, 0), int)
    assert rsrc_free() == 1
    assert rsrc_free() == 0

    # 2. Big-endian Atari ST .RSC from zoe_atari_gem_rsc.build_atari_rsc_bytes()
    be_rsc = zoe_atari_gem_rsc.build_atari_rsc_bytes(["ruby", "gem3"])
    rm = GemResourceManager()
    assert rm.rsrc_load(be_rsc) == 1
    assert rm.endian == ">"
    assert len(rm.rsrc_gaddr(R_TREE, 0)) == 3
    assert rm.rsrc_gaddr(R_ICONBLK, 0)["text"] == "ZOE RUBY"
    assert len(rm.rsrc_gaddr(R_IBPMASK, 0)) == 128
    assert len(rm.rsrc_gaddr(R_IBPDATA, 0)) == 128
    assert rm.rsrc_gaddr(R_IBPTEXT, 1) == "ZOE GEM3"
    assert rm.rsrc_gaddr(R_BITBLK, 0)["bi_wb"] == 4
    assert len(rm.rsrc_gaddr(R_BIPDATA, 0)) == 128
    assert len(rm.rsrc_gaddr(R_IMAGEDATA, 0)) == 128

    # 3. Synthetic .RSC with R_FRSTR (15) & R_FRIMG (16) so every 0..16 code is exercised
    # Layout: [0..36) RSHDR | "FREE\0\0" (6B) | image (4B) | BITBLK (14B) | frstr (4B) | frimg (4B) | OBJECT (24B) | trindex (4B)
    rsh_string = 36
    str_b = b"FREE\x00\x00"
    rsh_imdata = rsh_string + len(str_b)
    im_b = b"\xAA\x55\xAA\x55"
    rsh_bitblk = rsh_imdata + len(im_b)
    bb_b = struct.pack("<I5h", rsh_imdata, 2, 2, 0, 0, 1)
    rsh_frstr = rsh_bitblk + len(bb_b)
    frstr_b = struct.pack("<I", rsh_string)
    rsh_frimg = rsh_frstr + len(frstr_b)
    frimg_b = struct.pack("<I", rsh_bitblk)
    rsh_object = rsh_frimg + len(frimg_b)
    obj_b = struct.pack("<hhhHHHIHHHH", -1, -1, -1, G_BOX, LASTOB, NORMAL, 0, 0, 0, 10, 10)
    rsh_trindex = rsh_object + len(obj_b)
    tr_b = struct.pack("<I", rsh_object)
    total = rsh_trindex + len(tr_b)
    hdr_b = struct.pack(
        "<18H",
        0, rsh_object, rsh_object, rsh_object, rsh_bitblk, rsh_frstr,
        rsh_string, rsh_imdata, rsh_frimg, rsh_trindex,
        1, 1, 0, 0, 1, 1, 1, total,
    )
    assert rm.rsrc_load(hdr_b + str_b + im_b + bb_b + frstr_b + frimg_b + obj_b + tr_b) == 1
    assert rm.rsrc_gaddr(R_FRSTR, 0) == "FREE"
    assert rm.rsrc_gaddr(R_FRIMG, 0)["data_bytes"] == im_b

    with pytest.raises(ValueError):
        rm.rsrc_gaddr(99, 0)

    # 4. rsrc_obfix signed 8-bit high byte pixel offset
    packed_tree = [
        GemObject(
            ob_flags=LASTOB,
            ob_x=(2 << 8) | 5,      # 5 * 8 + 2 = 42
            ob_y=(0xFE << 8) | 3,   # 3 * 16 - 2 = 46
            ob_w=(4 << 8) | 10,     # 10 * 8 + 4 = 84
            ob_h=(0xFC << 8) | 2,   # 2 * 16 - 4 = 28
        )
    ]
    assert rsrc_obfix(packed_tree, 0, char_w=8, char_h=16) == (42, 46, 84, 28)


# ============================================================================
# 5. Feature #10: GemVdiStateMachine, NDC/RC, Clipping, GDPs & Metafile
# ============================================================================

def test_vdi_workstation_ndc_rc_clipping_and_writing_modes() -> None:
    vdi_sm = GemVdiStateMachine()
    with pytest.raises(RuntimeError):
        vdi_sm.v_pline([(0, 0), (10, 10)])

    # Open RC workstation 640x480
    handle, wout = vdi_sm.v_opnvwk([1, 1, 1, 3, 1, 1, 1, 1, 1, 1, RC_MODE], width=640, height=480)
    assert handle == 1
    assert len(wout) == 57
    assert wout[0] == 639 and wout[1] == 479
    assert len(vdi_sm.vq_extnd(0)) == 57
    ext = vdi_sm.vq_extnd(1)
    assert len(ext) == 57 and ext[4] == 4

    # NDC <-> RC Y-axis flip roundtrip
    assert vdi_sm.ndc_to_rc(0, 0) == (0, 479)
    assert vdi_sm.ndc_to_rc(32767, 32767) == (639, 0)
    assert vdi_sm.rc_to_ndc(0, 479) == (0, 0)
    assert vdi_sm.rc_to_ndc(639, 0) == (32767, 32767)

    # Clipping & writing mode
    assert vdi_sm.vs_clip(CLIP_ON, (100, 100, 10, 20)) == (10, 20, 100, 100)
    assert vdi_sm.clip_enabled is True
    vdi_sm.vs_clip(CLIP_OFF, (0, 0, 0, 0))
    assert vdi_sm.clip_enabled is False

    for mode in (MD_REPLACE, MD_TRANS, MD_XOR, MD_ERASE):
        assert vdi_sm.vswr_mode(mode) == mode
    with pytest.raises(ValueError):
        vdi_sm.vswr_mode(5)

    vdi_sm.v_clsvwk()
    with pytest.raises(RuntimeError):
        vdi_sm.v_circle(100, 100, 20)


def test_vdi_styles_primitives_gdps_metafile_and_scene_verification() -> None:
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([31, 1, 2, 3, 4, 1, 1, FIS_SOLID, 1, 3, RC_MODE], width=640, height=400)

    # Ch. 6 metafile escapes
    assert vdi_sm.vm_filename("ZOE_M3.GEM") == "ZOE_M3.GEM"
    assert vdi_sm.vm_pagesize(2540, 1588) == (2540, 1588)
    assert vdi_sm.vm_coords(0, 0, 639, 399) == (0, 0, 639, 399)
    assert vdi_sm.v_meta_extents(10, 10, 600, 380) == (10, 10, 600, 380)

    # Style setters
    assert vdi_sm.vsl_type(2) == 2
    assert vdi_sm.vsl_width(3) == 3
    assert vdi_sm.vsl_color(4) == 4
    assert vdi_sm.vsl_ends(1, 2) == (1, 2)
    assert vdi_sm.vsm_type(5) == 5
    assert vdi_sm.vsm_height(12) == 12
    assert vdi_sm.vsm_color(2) == 2
    assert vdi_sm.vsf_interior(FIS_PATTERN) == FIS_PATTERN
    assert vdi_sm.vsf_style(4) == 4
    assert vdi_sm.vsf_color(3) == 3
    assert vdi_sm.vsf_perimeter(1) == 1
    assert vdi_sm.vst_height(14)[1] == 14
    assert vdi_sm.vst_point(12)[1] > 0
    assert vdi_sm.vst_rotation(900) == 900
    assert vdi_sm.vst_font(2) == 2
    assert vdi_sm.vst_color(1) == 1
    assert vdi_sm.vst_effects(0x09) == 0x09
    assert vdi_sm.vst_alignment(1, 2) == (1, 2)

    # Primitives & GDPs
    vdi_sm.vsf_interior(FIS_SOLID)
    vdi_sm.v_bar((20, 20, 120, 80))
    vdi_sm.v_rbox((140, 20, 240, 80))
    vdi_sm.v_rfbox((260, 20, 360, 80))
    vdi_sm.vr_recfl((380, 20, 440, 80))
    vdi_sm.v_pline([(20, 120), (120, 160), (220, 120)])
    vdi_sm.v_pmarker([(50, 200), (80, 200)])
    vdi_sm.v_fillarea([(260, 120), (320, 180), (200, 180)])
    vdi_sm.v_circle(480, 150, 40)
    vdi_sm.v_ellipse(480, 260, 60, 30)
    vdi_sm.v_arc(120, 280, 40, 0, 900)
    vdi_sm.v_pieslice(240, 280, 40, 900, 2700)
    vdi_sm.v_ellarc(360, 280, 50, 25, 0, 1800)
    vdi_sm.v_gtext(40, 350, "ZOE GEM VDI")

    # Metafile verification via vdi.parse_metafile & seasip_gem.verify_seasip_gem_metafile
    vdi_mod: Any = vdi
    geometry_mod: Any = geometry
    runner_mod: Any = runner
    gem_bytes = vdi_sm.to_gem_metafile()
    parsed = vdi_mod.parse_metafile(gem_bytes)
    assert parsed["header"]["header_words"] == 24
    assert parsed["header"]["coordinate_system"] == RC_MODE
    assert parsed["records"][-1]["command"] == -1
    seasip_check = seasip_gem.verify_seasip_gem_metafile(gem_bytes)
    assert seasip_check["valid"] is True

    # Scene verification via geometry.verify & runner.verify_vdi
    scene = vdi_sm.to_scene("m3-vdi-full-scene")
    assert geometry_mod.verify(scene).passed is True
    assert runner_mod.verify_vdi(scene).passed is True
    ver = vdi_sm.verify_scene_and_metafile("m3-vdi-full-scene")
    assert ver["metafile_valid"] is True
    assert ver["geometry_passed"] is True
    assert ver["vdi_roundtrip_passed"] is True
    assert ver["constitutional"]["visual_evidence_only"] is True
    assert vdi_sm.snapshot()["constitutional"]["external_actions"] == 0


def test_vdi_ndc_mode_workstation_and_scene_conversion() -> None:
    vdi_sm = GemVdiStateMachine()
    handle, wout = vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_HOLLOW, 1, 1, NDC_MODE], width=640, height=400)
    assert handle == 1
    assert wout[0] == 32767 and wout[1] == 32767
    vdi_sm.v_pline([(1000, 1000), (16000, 16000)])
    vdi_sm.v_arc(16384, 16384, 4000, 0, 1800)
    gem_bytes = vdi_sm.to_gem_metafile()
    assert seasip_gem.verify_seasip_gem_metafile(gem_bytes)["coordinate_system"] == "NDC"
    geometry_mod: Any = geometry
    runner_mod: Any = runner
    scene = vdi_sm.to_scene("m3-ndc-scene")
    assert geometry_mod.verify(scene).passed is True
    assert runner_mod.verify_vdi(scene).passed is True


# ============================================================================
# 6. Regression Tests for Challenger Defects (Iteration 2 Fixes)
# ============================================================================

def test_vdi_vs_clip_enforced_across_all_primitives_in_to_scene() -> None:
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 2, RC_MODE], width=640, height=400)
    vdi_sm.vs_clip(CLIP_ON, (50, 50, 150, 150))

    # Rectangles: partial clip, full cull, edge-touching zero-overlap cull
    vdi_sm.v_bar((0, 0, 300, 300))          # clipped -> [50, 50, 150, 150]
    vdi_sm.v_rbox((20, 20, 100, 100))        # clipped -> [50, 50, 100, 100]
    vdi_sm.v_rfbox((200, 200, 250, 250))     # completely outside -> culled
    vdi_sm.vr_recfl((0, 0, 50, 50))          # corner-touch only -> culled

    # Polylines: clipped diagonal + exit/re-enter split + outside cull
    vdi_sm.v_pline([(0, 0), (200, 200)])                     # clipped -> [(50, 50), (150, 150)]
    vdi_sm.v_pline([(0, 100), (100, 100), (200, 200), (120, 120)])  # stays/exits cleanly
    vdi_sm.v_pline([(200, 200), (250, 250)])                 # outside -> culled

    # Polygons: Sutherland-Hodgman partial clip + outside cull
    vdi_sm.v_fillarea([(0, 100), (100, 0), (200, 100), (100, 200)])  # diamond clipped inside [50..150]
    vdi_sm.v_fillarea([(0, 0), (40, 0), (20, 40)])                   # outside -> culled

    # Markers: inside kept & tick clamped, outside culled
    vdi_sm.v_pmarker([(50, 100), (200, 200)])

    # Circles / Ellipses / Arcs / Ellarcs / Pieslices: partial clip & outside cull
    vdi_sm.v_circle(100, 100, 80)            # partial clip -> bounds [50, 50, 150, 150]
    vdi_sm.v_ellipse(300, 300, 20, 10)       # outside -> culled
    vdi_sm.v_circle(0, 0, 60)                # bounding box overlaps [50,50], circle distance sqrt(5000)>60 -> culled
    vdi_sm.v_pieslice(100, 100, 80, 0, 900)  # clipped polygon
    vdi_sm.v_arc(100, 100, 80, 0, 900)       # clipped polyline
    vdi_sm.v_ellarc(300, 300, 30, 20, 0, 900)  # outside -> culled

    # Text: partial clip & outside cull
    vdi_sm.vst_height(20)
    vdi_sm.v_gtext(40, 100, "ZOE_GEM_CLIP")  # partially clipped
    vdi_sm.v_gtext(300, 300, "OUTSIDE")      # outside -> culled

    geometry_mod: Any = geometry
    scene = vdi_sm.to_scene("m3-clip-scene")
    assert geometry_mod.verify(scene).passed is True
    # Only the clipped surviving objects exist, and every object's bounds stay strictly inside [50, 50, 150, 150]
    assert len(scene.objects) == 9
    for obj in scene.objects:
        b = geometry_mod.object_bounds(obj)
        assert b.left >= 50.0 and b.top >= 50.0 and b.right <= 150.0 and b.bottom <= 150.0, (obj["id"], b)

    # Check exact clipped rectangle bounds on first object (v_bar)
    assert geometry_mod.object_bounds(scene.objects[0]) == geometry.Bounds(50.0, 50.0, 150.0, 150.0)


def test_vdi_fis_hollow_preserves_none_fill_in_to_scene() -> None:
    vdi_sm = GemVdiStateMachine()
    vdi_sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_HOLLOW, 1, 2, RC_MODE], width=640, height=400)
    vdi_sm.vsf_color(2)  # red fill_color, but fill_interior is FIS_HOLLOW!
    vdi_sm.v_bar((20, 20, 100, 100))
    vdi_sm.v_rfbox((120, 20, 200, 100))
    vdi_sm.vr_recfl((220, 20, 300, 100))
    vdi_sm.v_fillarea([(20, 140), (80, 180), (20, 220)])
    vdi_sm.v_circle(400, 150, 30)
    vdi_sm.v_pieslice(480, 150, 30, 0, 900)

    scene = vdi_sm.to_scene("m3-hollow-scene")
    assert len(scene.objects) == 6
    for obj in scene.objects:
        assert obj["fill"] == "none", f"Expected fill='none' for FIS_HOLLOW on {obj}"

    # Verify FIS_SOLID uses the fill_color
    vdi_sm.vsf_interior(FIS_SOLID)
    vdi_sm.v_bar((20, 260, 100, 320))
    scene2 = vdi_sm.to_scene("m3-solid-scene")
    assert scene2.objects[-1]["fill"] == "red"


def test_rsrc_load_palindrome_be_and_strict_truncation_validation() -> None:
    # 1. Big-endian palindrome rsh_rssize = 0x0404 (1028 bytes) must detect ">" cleanly
    obj = struct.pack(">3h3HI4h", -1, -1, -1, G_BOX, LASTOB, NORMAL, 0, 0, 0, 100, 100)
    hdr = struct.pack(
        ">18H",
        0, 0x0200, 0x0200, 0x0200, 0x0200, 0x0200, 36, 36, 0x0200, 0x0400,
        1, 1, 0, 0, 0, 0, 0, 0x0404,
    )
    pal = hdr + b"\x00" * (0x0200 - 36) + obj + b"\x00" * (0x0400 - 0x0200 - len(obj)) + struct.pack(">I", 0x0200)
    assert len(pal) == 0x0404
    rm = GemResourceManager()
    assert rm.rsrc_load(pal) == 1
    assert rm.endian == ">"
    assert len(rm.rsrc_gaddr(R_TREE, 0)) == 1

    # 1b. seasip_gem.compile_rsc with endian=">" loads cleanly alongside "<"
    st_be = seasip_gem.GemObjectTree("ATARI", 160, 80)
    st_be.add(G_BUTTON, 10, 10, 60, 20, flags=SELECTABLE | EXIT, text="BE_OK")
    be_compiled = seasip_gem.compile_rsc([st_be], endian=">")
    assert rm.rsrc_load(be_compiled) == 1
    assert rm.endian == ">"
    assert rm.rsrc_gaddr(R_OBJECT, 1).text == "BE_OK"

    # 2. Truncated FRSTR table must raise ValueError (not silent break)
    obj_le = struct.pack("<hhhHHHIHHHH", -1, -1, -1, G_BOX, LASTOB, NORMAL, 0, 0, 0, 10, 10)
    rsh_obj = 36
    rsh_tr = rsh_obj + len(obj_le)
    tr_le = struct.pack("<I", rsh_obj)
    total_frstr_trunc = rsh_tr + len(tr_le)
    hdr_frstr_trunc = struct.pack(
        "<18H",
        0, rsh_obj, rsh_obj, rsh_obj, rsh_obj, total_frstr_trunc,
        36, rsh_obj, rsh_obj, rsh_tr,
        1, 1, 0, 0, 0, 5, 0, total_frstr_trunc,
    )
    with pytest.raises(ValueError, match="FRSTR"):
        rm.rsrc_load(hdr_frstr_trunc + obj_le + tr_le)

    # 3. Truncated FRIMG table must raise ValueError (not silent break)
    hdr_frimg_trunc = struct.pack(
        "<18H",
        0, rsh_obj, rsh_obj, rsh_obj, rsh_obj, rsh_obj,
        36, rsh_obj, total_frstr_trunc, rsh_tr,
        1, 1, 0, 0, 0, 0, 3, total_frstr_trunc,
    )
    with pytest.raises(ValueError, match="FRIMG"):
        rm.rsrc_load(hdr_frimg_trunc + obj_le + tr_le)

    # 4. Misaligned trindex pointer (rsh_object + 5) must raise ValueError
    tr_misaligned = struct.pack("<I", rsh_obj + 5)
    hdr_misaligned = struct.pack(
        "<18H",
        0, rsh_obj, rsh_obj, rsh_obj, rsh_obj, rsh_obj,
        36, rsh_obj, rsh_obj, rsh_tr,
        1, 1, 0, 0, 0, 0, 0, total_frstr_trunc,
    )
    with pytest.raises(ValueError, match="misaligned"):
        rm.rsrc_load(hdr_misaligned + obj_le + tr_misaligned)

    # 5. Missing LASTOB in tree must raise ValueError
    obj_no_lastob = struct.pack("<hhhHHHIHHHH", -1, -1, -1, G_BOX, 0, NORMAL, 0, 0, 0, 10, 10)
    with pytest.raises(ValueError, match="LASTOB"):
        rm.rsrc_load(hdr_misaligned + obj_no_lastob + tr_le)


def test_v_opnvwk_max_dimensions_aligned_with_scene() -> None:
    vdi_sm = GemVdiStateMachine()
    with pytest.raises(ValueError, match="32767"):
        vdi_sm.v_opnvwk(width=32768, height=400)
    with pytest.raises(ValueError, match="32767"):
        vdi_sm.v_opnvwk(width=640, height=32768)

    handle, wout = vdi_sm.v_opnvwk(width=32767, height=32767)
    assert handle == 1
    assert wout[0] == 32766 and wout[1] == 32766
    vdi_sm.v_bar((0, 0, 100, 100))
    scene = vdi_sm.to_scene("max-dim-scene")
    assert scene.document["canvas"] == {"width": 32767.0, "height": 32767.0}


def test_evnt_multi_rejects_bool_negative_timers_and_int16_overflow() -> None:
    app = GemAesApplication("VAL_APP")
    app.appl_init()

    with pytest.raises(ValueError):
        app.evnt_multi(MU_M1, m1_flag=True)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_M2, m2_flag=False)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_TIMER, lo_timint=False, hi_timint=1)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_TIMER, lo_timint=1, hi_timint=True)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_TIMER, lo_timint=-1)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_TIMER, hi_timint=-1)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_TIMER, lo_timint=65536)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_KEYBD, key_code=40000)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_KEYBD, key_code=-40000)
    with pytest.raises(ValueError):
        app.evnt_multi(MU_KEYBD, key_code=True)


def test_vdi_vs_clip_ndc_mode_and_polyline_reentry_split() -> None:
    # 1. Polyline exiting and re-entering clip box must split without bogus interior chord
    vdi_rc = GemVdiStateMachine()
    vdi_rc.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, RC_MODE], width=640, height=400)
    vdi_rc.vs_clip(CLIP_ON, (100, 100, 200, 200))
    vdi_rc.v_pline([(120, 150), (250, 150), (250, 180), (150, 180)])
    rc_scene = vdi_rc.to_scene("m3-reentry-scene")
    assert len(rc_scene.objects) == 2
    assert rc_scene.objects[0]["points"] == [[120.0, 150.0], [200.0, 150.0]]
    assert rc_scene.objects[1]["points"] == [[200.0, 180.0], [150.0, 180.0]]

    # 2. NDC mode vs_clip maps clip bounds accurately to Scene space
    vdi_ndc = GemVdiStateMachine()
    vdi_ndc.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 2, NDC_MODE], width=640, height=400)
    vdi_ndc.vs_clip(CLIP_ON, (8192, 8192, 24575, 24575))
    vdi_ndc.v_bar((0, 0, 32767, 32767))
    vdi_ndc.v_bar((0, 0, 4000, 4000))  # outside -> culled
    geometry_mod: Any = geometry
    ndc_scene = vdi_ndc.to_scene("m3-ndc-clip-scene")
    assert len(ndc_scene.objects) == 1
    assert geometry_mod.verify(ndc_scene).passed is True
    b = geometry_mod.object_bounds(ndc_scene.objects[0])
    assert b.left >= 159.0 and b.right <= 480.0 and b.top >= 99.0 and b.bottom <= 300.0


# ============================================================================
# 7. Regression Tests for Challenger R2 Defects (Iteration 3 Fixes)
# ============================================================================

def test_vdi_clipped_ellipse_sub_half_radius_culled_and_verifies_cleanly() -> None:
    # 1. RC circle clipped to nrx=0.5 must be culled so verify_scene_and_metafile() never hits zero radius
    sm_rc = GemVdiStateMachine()
    sm_rc.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 2, RC_MODE], width=640, height=400)
    sm_rc.vs_clip(CLIP_ON, (0, 0, 51, 200))
    sm_rc.v_circle(100, 100, 50)
    assert sm_rc.to_scene("rc-subhalf-circle").objects == []
    ver_rc = sm_rc.verify_scene_and_metafile("rc-subhalf-circle")
    assert ver_rc["metafile_valid"] is True
    assert ver_rc["geometry_passed"] is True
    assert ver_rc["vdi_roundtrip_passed"] is True

    # 2. RC ellipse clipped to nry=0.5 must be culled
    sm_ell = GemVdiStateMachine()
    sm_ell.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 2, RC_MODE], width=640, height=400)
    sm_ell.vs_clip(CLIP_ON, (0, 0, 200, 51))
    sm_ell.v_ellipse(100, 100, 40, 50)
    assert sm_ell.to_scene("rc-subhalf-ellipse").objects == []
    assert sm_ell.verify_scene_and_metafile("rc-subhalf-ellipse")["vdi_roundtrip_passed"] is True

    # 3. NDC circle clipped to sub-0.5 radius must be culled; >0.5 radius survives and verifies cleanly
    sm_ndc = GemVdiStateMachine()
    sm_ndc.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 2, NDC_MODE], width=640, height=400)
    sm_ndc.vs_clip(CLIP_ON, (0, 0, 5020, 32767))
    sm_ndc.v_circle(10000, 16384, 5000)
    assert sm_ndc.to_scene("ndc-subhalf-circle").objects == []
    assert sm_ndc.verify_scene_and_metafile("ndc-subhalf-circle")["vdi_roundtrip_passed"] is True

    sm_survive = GemVdiStateMachine()
    sm_survive.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 2, RC_MODE], width=640, height=400)
    sm_survive.vs_clip(CLIP_ON, (0, 0, 52, 200))
    sm_survive.v_circle(100, 100, 50)
    surviving = sm_survive.to_scene("rc-surviving-circle").objects
    assert len(surviving) == 1
    assert surviving[0]["radii"] == [1.0, 50.0]
    assert sm_survive.verify_scene_and_metafile("rc-surviving-circle")["vdi_roundtrip_passed"] is True


def test_vdi_clip_polyline_ndc_round_collapse_culls_degenerate_segment() -> None:
    # Degenerate post-round_ndc segment must be culled instead of emitting a zero-length line
    sm = GemVdiStateMachine()
    sm.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, NDC_MODE], width=10, height=10)
    sm.vs_clip(CLIP_ON, (0, 0, 16384, 32767))
    sm.v_pline([(16383, 16384), (20000, 16384)])
    assert sm.to_scene("ndc-collapsed-line").objects == []

    # Polyline with a tiny interior segment that collapses under round_ndc should keep continuity without duplicates
    sm2 = GemVdiStateMachine()
    sm2.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, NDC_MODE], width=10, height=10)
    sm2.vs_clip(CLIP_ON, (0, 0, 32767, 32767))
    sm2.v_pline([(0, 16384), (16383, 16384), (16384, 16384), (32767, 16384)])
    objs = sm2.to_scene("ndc-collapsed-midseg").objects
    assert len(objs) == 1
    pts = objs[0]["points"]
    assert len(pts) == 3
    for i in range(len(pts) - 1):
        assert pts[i] != pts[i + 1]


def test_vdi_pmarker_zero_width_or_zero_height_clip_culled() -> None:
    sm_w = GemVdiStateMachine()
    sm_w.v_opnvwk(width=640, height=400)
    sm_w.vs_clip(CLIP_ON, (50, 50, 50, 100))
    sm_w.v_pmarker([(50, 75)])
    assert sm_w.to_scene("zero-width-pmarker").objects == []

    sm_h = GemVdiStateMachine()
    sm_h.v_opnvwk(width=640, height=400)
    sm_h.vs_clip(CLIP_ON, (50, 50, 100, 50))
    sm_h.v_pmarker([(75, 50)])
    assert sm_h.to_scene("zero-height-pmarker").objects == []


def test_vdi_small_span_arc_and_ellarc_deduplicate_and_cull_degenerate_points() -> None:
    # Single-pixel collapsed arc & ellarc (both unclipped and clipped) must be culled
    sm = GemVdiStateMachine()
    sm.v_opnvwk(width=640, height=400)
    sm.v_arc(100, 100, 5, 0, 1)
    sm.v_ellarc(200, 200, 5, 3, 0, 1)
    assert sm.to_scene("small-arc-unclipped").objects == []

    sm_clip = GemVdiStateMachine()
    sm_clip.v_opnvwk(width=640, height=400)
    sm_clip.vs_clip(CLIP_ON, (50, 50, 250, 250))
    sm_clip.v_arc(100, 100, 5, 0, 1)
    sm_clip.v_ellarc(200, 200, 5, 3, 0, 1)
    assert sm_clip.to_scene("small-arc-clipped").objects == []

    # Small non-degenerate arc deduplicates consecutive identical vertices while keeping >= 2 distinct points
    sm_dedup = GemVdiStateMachine()
    sm_dedup.v_opnvwk(width=640, height=400)
    sm_dedup.v_arc(100, 100, 50, 0, 30)
    objs = sm_dedup.to_scene("small-arc-dedup").objects
    assert len(objs) == 1
    pts = objs[0]["points"]
    assert len(pts) >= 2
    for i in range(len(pts) - 1):
        assert pts[i] != pts[i + 1]


# ============================================================================
# 8. Regression Tests for Challenger R3 Defects (Iteration 4 Fixes)
# ============================================================================

def test_vdi_unclipped_pline_pieslice_and_fillarea_dedup_and_culling() -> None:
    # 1. RC unclipped zero-length v_pline must be culled
    sm_rc = GemVdiStateMachine()
    sm_rc.v_opnvwk(width=640, height=400)
    sm_rc.v_pline([(10, 10), (10, 10)])
    assert sm_rc.to_scene("rc-zero-pline").objects == []

    # 2. NDC 100x100 unclipped v_pline collapsing to 1 point culled; 3->2 points emits "line"
    sm_ndc_zero = GemVdiStateMachine()
    sm_ndc_zero.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, NDC_MODE], width=100, height=100)
    sm_ndc_zero.v_pline([(1000, 1000), (1001, 1000)])
    assert sm_ndc_zero.to_scene("ndc-zero-pline").objects == []

    sm_ndc_dup = GemVdiStateMachine()
    sm_ndc_dup.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, NDC_MODE], width=100, height=100)
    sm_ndc_dup.v_pline([(1000, 1000), (1001, 1000), (5000, 5000)])
    objs_line = sm_ndc_dup.to_scene("ndc-dedup-pline").objects
    assert len(objs_line) == 1
    assert objs_line[0]["type"] == "line"
    assert objs_line[0]["points"][0] != objs_line[0]["points"][1]

    # 3. Unclipped degenerate v_pieslice and v_fillarea must be culled
    sm_deg = GemVdiStateMachine()
    sm_deg.v_opnvwk(width=640, height=400)
    sm_deg.v_pieslice(100, 100, 1, 0, 1)
    sm_deg.v_fillarea([(10, 10), (10, 10), (10, 10)])
    sm_deg.v_fillarea([(20, 20), (40, 20), (60, 20)])  # collinear zero-area
    assert sm_deg.to_scene("rc-unclipped-degen-polys").objects == []

    # 4. Valid unclipped v_fillarea with duplicate/closing points keeps clean non-duplicate polygon
    sm_poly = GemVdiStateMachine()
    sm_poly.v_opnvwk(width=640, height=400)
    sm_poly.v_fillarea([(10, 10), (10, 10), (60, 10), (35, 50), (10, 10)])
    poly_objs = sm_poly.to_scene("rc-clean-poly").objects
    assert len(poly_objs) == 1
    pts = poly_objs[0]["points"]
    assert len(pts) == 3
    for i in range(len(pts)):
        assert pts[i] != pts[(i + 1) % len(pts)]


def test_vdi_clipped_ndc_gtext_and_odd_rc_circle_roundtrip_align() -> None:
    # 1. Standard 640x400 NDC_MODE clipped text near top edge must cull sub-pixel box cleanly
    sm_txt_cull = GemVdiStateMachine()
    sm_txt_cull.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, NDC_MODE], width=640, height=400)
    sm_txt_cull.vs_clip(CLIP_ON, (0, 32729, 32767, 32767))
    sm_txt_cull.vst_height(10)
    sm_txt_cull.v_gtext(1000, 32730, "Hello")
    assert sm_txt_cull.to_scene("ndc-clipped-text-cull").objects == []
    ver_cull = sm_txt_cull.verify_scene_and_metafile("ndc-clipped-text-cull")
    assert ver_cull["geometry_passed"] is True
    assert ver_cull["vdi_roundtrip_passed"] is True

    # 2. 640x400 NDC_MODE clipped text with enough height survives and passes VDI round-trip
    sm_txt_ok = GemVdiStateMachine()
    sm_txt_ok.v_opnvwk([1, 1, 1, 1, 1, 1, 1, FIS_SOLID, 1, 1, NDC_MODE], width=640, height=400)
    sm_txt_ok.vs_clip(CLIP_ON, (500, 29000, 10000, 32500))
    sm_txt_ok.vst_height(18)
    sm_txt_ok.v_gtext(100, 30000, "ZOE_CLIPPED_TEXT")
    ver_ok = sm_txt_ok.verify_scene_and_metafile("ndc-clipped-text-ok")
    assert ver_ok["geometry_passed"] is True
    assert ver_ok["vdi_roundtrip_passed"] is True
    txt_objs = sm_txt_ok.to_scene("ndc-clipped-text-ok").objects
    assert len(txt_objs) == 1

    # 3. Odd-width 321x201 RC_MODE clipped circle & ellipse pass verify_scene_and_metafile()
    sm_odd = GemVdiStateMachine()
    sm_odd.v_opnvwk(width=321, height=201)
    sm_odd.vs_clip(CLIP_ON, (318, 0, 321, 200))
    sm_odd.v_circle(319, 100, 10)
    sm_odd.vs_clip(CLIP_ON, (0, 198, 200, 201))
    sm_odd.v_ellipse(100, 199, 20, 10)
    ver_odd = sm_odd.verify_scene_and_metafile("odd-rc-clipped-ellipses")
    assert ver_odd["geometry_passed"] is True
    assert ver_odd["vdi_roundtrip_passed"] is True
    geometry_mod: Any = geometry
    odd_scene = sm_odd.to_scene("odd-rc-clipped-ellipses")
    assert len(odd_scene.objects) == 2
    for obj in odd_scene.objects:
        b = geometry_mod.object_bounds(obj)
        assert 0.0 <= b.left and b.right <= 321.0
        assert 0.0 <= b.top and b.bottom <= 201.0


def test_vdi_32767_unclipped_overflow_reports_roundtrip_error_without_crash() -> None:
    sm = GemVdiStateMachine()
    sm.v_opnvwk(width=32767, height=32767)
    sm.v_circle(32000, 32000, 5000)
    sm.v_arc(32000, 32000, 5000, 0, 900)
    ver = sm.verify_scene_and_metafile("max-unclipped-overflow")
    assert ver["metafile_valid"] is True
    assert ver["geometry_passed"] is True
    assert ver["vdi_roundtrip_passed"] is False
    assert "signed 16-bit range" in ver["vdi_roundtrip_error"]

