"""Tier 5 Adversarial Regression Tests for Zoe Monorepo Phase-2 Flowing-GEM Pass."""

from __future__ import annotations

import json
import math
from pathlib import Path
import re
import signal
import sys
import threading
import time
from urllib import error as urlerror, request as urlrequest
import warnings

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
for _rel in ("components/ablation", "guiai-lab", "components/Zoe-Autonomy/src"):
    _p = str(REPO_ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _make_isolated_zoe_root(tmp_path: Path, name: str = "iso_no_research") -> Path:
    """Create a temp zoe_root with symlinked source/assets (no research/visual-archive/)."""
    iso_root = tmp_path / name
    iso_root.mkdir(parents=True, exist_ok=True)
    for item in ("guiai-lab", "components", "assets", "CONSTITUTION.md", "README.md"):
        src = REPO_ROOT / item
        if src.exists():
            (iso_root / item).symlink_to(src)
    (iso_root / "evidence").mkdir(parents=True, exist_ok=True)
    return iso_root


def _spawn_eliza(zoe_root: Path, state_dir: Path):
    from guiai.gem.eliza_view import create_server

    srv, eng, lock = create_server(zoe_root, state_dir=state_dir, host="127.0.0.1", port=0)
    port = srv.server_address[1]
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    return srv, eng, lock, f"http://127.0.0.1:{port}"


def _post_json(base_url: str, path: str, payload: object, timeout: float = 120.0):
    req = urlrequest.Request(
        f"{base_url}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return int(resp.status), json.loads(resp.read().decode("utf-8"))
    except urlerror.HTTPError as err:
        with err:
            return int(err.code), json.loads(err.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# Gap 1: _eliza_routes._run_l5_phase_spec pre-validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", [3, 4, 5, 6])
def test_t5_gap1_unknown_pillar_id_fast_400_without_running_suite(tmp_path: Path, phase: int) -> None:
    """Unknown pillar_id on POST /api/l5/phase{3..6}/run must reject in < 1.0s without executing pillars."""
    srv, _eng, _lk, base = _spawn_eliza(REPO_ROOT, tmp_path / f"state_p{phase}")
    try:
        t0 = time.monotonic()
        status, body = _post_json(base, f"/api/l5/phase{phase}/run", {"pillar_id": "nonexistent_pillar"})
        elapsed = time.monotonic() - t0
        assert status == 400
        assert "unknown pillar_id" in body.get("error", "")
        assert elapsed < 1.0, f"phase {phase} unknown pillar_id took {elapsed:.2f}s (executed pillars before rejecting!)"
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------
# Gap 2: l5_phase6_blind_evolution missing research/visual-archive/
# ---------------------------------------------------------------------------


def test_t5_gap2_blind_evolution_missing_visual_archive_no_index_error(tmp_path: Path) -> None:
    """Running blind_scratch_ast_meta_evolution without research/visual-archive/ must never raise IndexError or drop HTTP."""
    from zoe_autonomy.l5_phase6_blind_evolution import _accuracy_vec, _eval_node_vec, eval_pillar_03_blind_scratch_evolution

    assert _eval_node_vec("x0", np.array([])).shape == (0,)
    assert _accuracy_vec("x0", np.array([]), np.array([], dtype=np.int64)) == 0.0

    iso_root = _make_isolated_zoe_root(tmp_path)

    # Direct call must either return a structured non-passing dict or raise ValueError/FileNotFoundError (never IndexError)
    try:
        res = eval_pillar_03_blind_scratch_evolution(iso_root)
        assert isinstance(res, dict)
        assert res.get("passed") is False
    except (ValueError, FileNotFoundError):
        pass

    # HTTP route must return clean JSON HTTP 400 (or 200 with passed=False), never RemoteDisconnected
    srv, _eng, _lk, base = _spawn_eliza(iso_root, tmp_path / "iso_http_state")
    try:
        status, body = _post_json(base, "/api/l5/phase6/run", {"pillar_id": "blind_scratch_ast_meta_evolution"})
        assert status in {200, 400}
        assert isinstance(body, dict)
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------
# Gap 3: groove_forensics finite JSON & zero warnings on degenerate inputs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,onsets,grid_step_sec",
    [
        ("empty", [], 0.25),
        ("single", [0.25], 0.25),
        ("zero_grid_step", [0.0, 0.1, 0.2, 0.3, 0.4], 0.0),
        ("neg_grid_step", [0.0, 0.1, 0.2, 0.3, 0.4], -0.25),
        ("nan_in_onsets", [0.0, float("nan"), 0.5, 0.75], 0.25),
    ],
)
def test_t5_gap3_groove_forensics_degenerate_inputs_strict_json_no_warnings(
    label: str, onsets: list[float], grid_step_sec: float
) -> None:
    """analyze_onset_stream must emit 0 RuntimeWarnings and strict finite JSON (allow_nan=False)."""
    from guiai.gem.groove_forensics import analyze_onset_stream

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        doc = analyze_onset_stream(label, onsets, grid_step_sec)

    runtime_warns = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warns, f"{label} emitted RuntimeWarnings: {[str(w.message) for w in runtime_warns]}"
    if grid_step_sec <= 0.0:
        assert doc["grid_step_ms"] == 0.0
    encoded = json.dumps(doc, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded


# ---------------------------------------------------------------------------
# Gap 4: l5_phase6_repo_agent parity & test_eliza_routes timeout
# ---------------------------------------------------------------------------


def test_t5_gap4_repo_agent_tolerates_mobile_version_bump_without_touching_mobile() -> None:
    """12-point monorepo parity must accept Android and Apple Swift Info.plist >= 0.9.5 / build >= 16."""
    from zoe_autonomy.l5_phase6_repo_agent import _live_12point_monorepo_contract_audit

    parity = _live_12point_monorepo_contract_audit(REPO_ROOT)
    assert parity["checks_passed"] == parity["checks_total"] == 12, f"Parity failed: {parity['details']}"


def test_t5_gap4_swift_info_plist_version_bounds(tmp_path: Path) -> None:
    """_has_swift_version_at_least must accept >= (0.9.5, 16) and reject lower bounds or malformed XML."""
    import plistlib
    from zoe_autonomy.l5_phase6_repo_agent import _has_swift_version_at_least

    rel = "mobile/apple/Zoe/Info.plist"
    plist_path = tmp_path / rel
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    # Missing file -> False
    assert _has_swift_version_at_least(tmp_path, rel, 16, (0, 9, 5)) is False

    # Valid monotonic bounds (exact floor, minor bump, X.Y.Z minor jump, X.Y two-part version)
    for ver, build in (("0.9.5", "16"), ("0.9.6", "17"), ("0.10.0", "16"), ("1.0", "20")):
        plist_path.write_bytes(
            plistlib.dumps({"CFBundleShortVersionString": ver, "CFBundleVersion": build})
        )
        assert _has_swift_version_at_least(tmp_path, rel, 16, (0, 9, 5)) is True, (ver, build)

    # Negative controls: version below floor, build below floor, malformed XML
    for ver, build in (("0.9.4", "17"), ("0.9.6", "15")):
        plist_path.write_bytes(
            plistlib.dumps({"CFBundleShortVersionString": ver, "CFBundleVersion": build})
        )
        assert _has_swift_version_at_least(tmp_path, rel, 16, (0, 9, 5)) is False, (ver, build)

    plist_path.write_bytes(b"<plist><broken>")
    assert _has_swift_version_at_least(tmp_path, rel, 16, (0, 9, 5)) is False


def test_t5_gap4_test_eliza_routes_http_post_timeout_at_least_120() -> None:
    """test_eliza_routes._http_post timeout must be >= 120s so Phase 3/4 full POST routes cannot flake."""
    src = (REPO_ROOT / "components" / "Zoe-Autonomy" / "tests" / "test_eliza_routes.py").read_text(encoding="utf-8")
    m = re.search(r"def _http_post.*?urlopen\(req,\s*timeout=([0-9.]+)\)", src, flags=re.DOTALL)
    assert m is not None
    assert float(m.group(1)) >= 120.0, f"_http_post timeout={m.group(1)} < 120.0"


# ---------------------------------------------------------------------------
# Gap 5: EntropyMapper.scan_kloster_stopping EOF < max_samples
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_bytes", [1, 8, 11, 64, 256])
def test_t5_gap5_entropy_mapper_scan_kloster_stopping_abstains_at_eof(tmp_path: Path, n_bytes: int) -> None:
    """When file EOF < max_samples and signal did not trigger DECIDE_SIGNAL, must ABSTAIN (never GATHER_MORE)."""
    from ablation.analyzers.entropy_mapper import EntropyMapper

    rng = np.random.default_rng(2026 + n_bytes)
    p = tmp_path / f"eof_{n_bytes}.bin"
    p.write_bytes(rng.integers(0, 256, size=n_bytes, dtype=np.uint8).tobytes())

    verdict = EntropyMapper(str(p)).scan_kloster_stopping(max_samples=512, chunk_size=64)
    assert verdict["samples"] == n_bytes
    assert verdict.get("eof_reached") is True
    assert verdict["action"] == "ABSTAIN_INSUFFICIENT_EVIDENCE", (
        f"EOF reached at {n_bytes} < 512 bytes, expected ABSTAIN_INSUFFICIENT_EVIDENCE, got {verdict['action']}"
    )


# ---------------------------------------------------------------------------
# Gap 6: README.md verification script references exist
# ---------------------------------------------------------------------------


def test_t5_gap6_readme_all_script_commands_exist_on_disk() -> None:
    """Every scripts/*.py path referenced anywhere in README.md (including bash blocks) must exist."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    script_refs = sorted(set(re.findall(r"scripts/[A-Za-z0-9_.-]+\.py", readme)))
    missing = [rel for rel in script_refs if not (REPO_ROOT / rel).is_file()]
    assert not missing, f"README.md references non-existent scripts: {missing}"


# ---------------------------------------------------------------------------
# Gap 7: _eliza_routes POST type validation & seed=0 bug
# ---------------------------------------------------------------------------


def test_t5_gap7_eliza_routes_invalid_post_types_return_400_and_seed_zero_preserved(tmp_path: Path) -> None:
    """Invalid types in /api/stem/route and /api/playroom/jam must return HTTP 400 (not drop socket); seed=0 preserved."""
    srv, _eng, _lk, base = _spawn_eliza(REPO_ROOT, tmp_path / "state_types")
    try:
        for path, payload in (
            ("/api/stem/route", {"prompt": "hello", "files_count": None}),
            ("/api/stem/route", {"prompt": "hello", "files_count": True}),
            ("/api/playroom/jam", {"seed": [1]}),
            ("/api/playroom/jam", {"seed": True}),
        ):
            status, body = _post_json(base, path, payload)
            assert status == 400, f"{path} {payload} -> {status} {body}"
            assert "error" in body

        # seed=0 must NOT be silently overwritten to 2026
        req = urlrequest.Request(
            f"{base}/api/playroom/jam",
            data=json.dumps({"seed": 0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=30) as resp:
            assert resp.status == 200
            assert resp.headers.get("X-Zoe-Seed") == "0"
    finally:
        srv.shutdown()
        srv.server_close()


# ---------------------------------------------------------------------------
# Gap 8: _utils.atomic_write_json cleanup & _metrics coercion/NaN
# ---------------------------------------------------------------------------


def test_t5_gap8_atomic_write_json_cleans_tmp_and_auroc_handles_lists_and_nan(tmp_path: Path) -> None:
    from zoe_autonomy._metrics import auroc_argsort, auroc_tie_aware
    from zoe_autonomy._utils import atomic_write_json

    target = tmp_path / "fail.json"
    with pytest.raises(ValueError):
        atomic_write_json(target, {"x": float("nan")})
    assert not target.exists()
    assert not (tmp_path / "fail.json.tmp").exists(), "Leftover .tmp file was not cleaned up on ValueError"

    assert auroc_argsort([0, 1], [0.2, 0.8]) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        auroc_tie_aware([0, 1], [0.5, float("nan")])
    with pytest.raises(ValueError):
        auroc_tie_aware([0, 1], [0.5])


# ---------------------------------------------------------------------------
# Gap 9: Bridge 2 NaN/empty guards (MTF blur loss & Playroom)
# ---------------------------------------------------------------------------


def test_t5_gap9_mtf_blur_loss_nan_and_playroom_empty_grid_safe() -> None:
    from guiai.gem.creative_playroom import _measure_artifact_descriptors
    from guiai.gem.kloster_spatial_optical_law import kloster_mtf_blur_loss

    mtf = kloster_mtf_blur_loss(np.array([[np.nan, 1.0], [2.0, 3.0]]))
    assert json.dumps(mtf, allow_nan=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        desc = _measure_artifact_descriptors(np.zeros((0, 0), dtype=np.uint8))
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert json.dumps(desc, allow_nan=False)


# ---------------------------------------------------------------------------
# Gap 10: kloster_spatial_optical_law NaN/Inf/non-positive PSF & field guards
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_sigma", [float("nan"), float("inf"), float("-inf"), 0.0, -1.5])
def test_t5_r2_gap10a_mtf_blur_loss_invalid_psf_sigma_raises_value_error(bad_sigma: float) -> None:
    from guiai.gem.kloster_spatial_optical_law import kloster_mtf_blur_loss

    field = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    with pytest.raises(ValueError):
        kloster_mtf_blur_loss(field, psf_sigma=bad_sigma)


@pytest.mark.parametrize(
    "bad_psf",
    [
        np.array([[np.nan, 1.0], [1.0, 1.0]], dtype=np.float64),
        np.array([[np.inf, 1.0], [1.0, 1.0]], dtype=np.float64),
    ],
)
def test_t5_r2_gap10b_mtf_blur_loss_nonfinite_custom_psf_raises_value_error(bad_psf: np.ndarray) -> None:
    from guiai.gem.kloster_spatial_optical_law import kloster_mtf_blur_loss

    field = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        with pytest.raises(ValueError):
            kloster_mtf_blur_loss(field, psf=bad_psf)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]


@pytest.mark.parametrize(
    "bad_field",
    [
        np.array([[np.nan, 1.0], [2.0, 3.0]], dtype=np.float64),
        np.array([[np.inf, 1.0], [2.0, 3.0]], dtype=np.float64),
    ],
)
def test_t5_r2_gap10c_kloster_spatial_m2_nonfinite_field_returns_zero_no_warnings(bad_field: np.ndarray) -> None:
    from guiai.gem.kloster_spatial_optical_law import kloster_spatial_m2

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        val = kloster_spatial_m2(bad_field)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert math.isfinite(val) and val == 0.0


# ---------------------------------------------------------------------------
# Gap 11: creative_playroom._measure_artifact_descriptors shape & dtype safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,grid",
    [
        (
            "rect_4x8_uint8",
            np.array(
                [
                    [0, 1, 0, 1, 0, 1, 0, 1],
                    [1, 0, 1, 0, 1, 0, 1, 0],
                    [0, 1, 1, 0, 0, 1, 1, 0],
                    [1, 0, 0, 1, 1, 0, 0, 1],
                ],
                dtype=np.uint8,
            ),
        ),
        (
            "list_of_lists",
            [[0, 1, 0, 1], [1, 0, 1, 0], [0, 1, 0, 1], [1, 0, 1, 0]],
        ),
        (
            "float64_grid",
            np.array(
                [
                    [0.0, 1.0, 0.0, 1.0],
                    [1.0, 0.0, 1.0, 0.0],
                    [0.0, 1.0, 0.0, 1.0],
                    [1.0, 0.0, 1.0, 0.0],
                ],
                dtype=np.float64,
            ),
        ),
        (
            "neg_int_grid",
            np.array([[-1, 1], [1, 0]], dtype=np.int64),
        ),
    ],
)
def test_t5_r2_gap11_playroom_measure_descriptors_rect_and_non_uint8_safe(label: str, grid: object) -> None:
    from guiai.gem.creative_playroom import _measure_artifact_descriptors

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        desc = _measure_artifact_descriptors(grid)  # type: ignore[arg-type]
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)], label
    encoded = json.dumps(desc, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded


# ---------------------------------------------------------------------------
# Gap 12: cern_kloster_trigger._median3_probs NaN & groove_forensics overflow/NaN
# ---------------------------------------------------------------------------


def test_t5_r2_gap12_cern_median3_probs_nan_and_groove_overflow_safe() -> None:
    from guiai.gem.cern_kloster_trigger import _median3_probs
    from guiai.gem.groove_forensics import _analyze_kloster_groove_metrics, analyze_onset_stream

    probs = _median3_probs(np.array([np.nan, 1.0, 2.0, 3.0], dtype=np.float64))
    assert bool(np.all(np.isfinite(probs)))
    assert json.dumps(probs.tolist(), allow_nan=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        direct = _analyze_kloster_groove_metrics(
            np.array([0.0, 0.25, 0.5, 0.75]),
            np.array([0.0, 0.0, 0.0]),
            np.array([0.0, 0.0, 0.0]),
            float("nan"),
        )
        huge = analyze_onset_stream("huge_ts", [1e308, 1e308 + 1e300, 1e308 + 2e300, 1e308 + 3e300], 0.25)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert json.dumps(direct, allow_nan=False)
    assert json.dumps(huge, allow_nan=False)


# ---------------------------------------------------------------------------
# Gap 13: creative_playroom._measure_artifact_descriptors 1e308 density=inf
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("fill_val", [1e308, -1e308])
def test_t5_r3_gap13_playroom_measure_descriptors_extreme_float64_finite_json_no_warnings(fill_val: float) -> None:
    from guiai.gem.creative_playroom import _measure_artifact_descriptors

    grid = np.full((4, 4), fill_val, dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        desc = _measure_artifact_descriptors(grid)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    encoded = json.dumps(desc, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded


# ---------------------------------------------------------------------------
# Gap 14: groove_forensics extreme timestamp overflows (PLV, residuals, IOI)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,onsets,grid_step_sec",
    [
        ("inf_plv", [0.0, 1e307, 2e307, 3e307], 1.0),
        ("huge_res", [0.0, 1e307, 2e307, 3e307], 1.1e307),
        ("ioi_175", [0.0, 1.75e308, 1.76e308, 1.77e308], 1e307),
    ],
)
def test_t5_r3_gap14a_groove_forensics_extreme_timestamps_finite_json_no_warnings(
    label: str, onsets: list[float], grid_step_sec: float
) -> None:
    from guiai.gem.groove_forensics import analyze_onset_stream

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        doc = analyze_onset_stream(label, onsets, grid_step_sec)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)], label
    encoded = json.dumps(doc, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_t5_r3_gap14b_groove_forensics_polyrhythmic_plv_extreme_timestamps_finite() -> None:
    from guiai.gem.groove_forensics import polyrhythmic_plv

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        plv = polyrhythmic_plv([0.0, 1e308, 1.1e308, 1.2e308], [0.0, 1.0, 2.0, 3.0], 3, 2, 2.0)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert math.isfinite(plv) and 0.0 <= plv <= 1.0


# ---------------------------------------------------------------------------
# Gap 15: kloster_spatial_optical_law extreme float64 overflows
# ---------------------------------------------------------------------------


def test_t5_r3_gap15a_kloster_spatial_m2_cancellation_overflow_finite_no_warnings() -> None:
    from guiai.gem.kloster_spatial_optical_law import kloster_spatial_m2

    field = np.array([[1e160, -1e160], [1.0, 0.0]], dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        val = kloster_spatial_m2(field)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert math.isfinite(val)


def test_t5_r3_gap15b_kloster_mtf_blur_loss_extreme_uniform_field_no_warnings() -> None:
    from guiai.gem.kloster_spatial_optical_law import kloster_mtf_blur_loss

    field = np.full((4, 4), 1e308, dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        res = kloster_mtf_blur_loss(field)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert res["mtf_sharpness"] == 0.0
    assert json.dumps(res, allow_nan=False)


# ---------------------------------------------------------------------------
# Gap 16: EntropyMapper non-positive window/step & chunk_size=0 bugs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("window_size,step_size", [(0, 256), (-1, 256), (256, 0), (256, -10)])
def test_t5_r3_gap16a_entropy_mapper_rejects_nonpositive_window_or_step(
    tmp_path: Path, window_size: int, step_size: int
) -> None:
    from ablation.analyzers.entropy_mapper import EntropyMapper

    p = tmp_path / "sample.bin"
    p.write_bytes(b"\x00" * 512)

    def _timeout(_sig, _frame):
        raise TimeoutError(f"infinite loop for window_size={window_size}, step_size={step_size}")

    old_handler = signal.signal(signal.SIGALRM, _timeout)
    signal.alarm(2)
    try:
        with pytest.raises(ValueError):
            EntropyMapper(str(p), window_size=window_size, step_size=step_size).run()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


def test_t5_r3_gap16b_entropy_mapper_scan_kloster_stopping_chunk_size_zero_safe(tmp_path: Path) -> None:
    from ablation.analyzers.entropy_mapper import EntropyMapper

    p = tmp_path / "sample.bin"
    p.write_bytes(b"\x00" * 512)
    try:
        verdict = EntropyMapper(str(p)).scan_kloster_stopping(max_samples=512, chunk_size=0)
    except ValueError:
        return
    assert verdict["samples"] > 0
    assert verdict["action"] != "GATHER_MORE"


# ---------------------------------------------------------------------------
# Gap 17: Bridge 5 fsum OverflowError & _eliza_routes import-before-validation
# ---------------------------------------------------------------------------


def test_t5_r3_gap17a_bridge5_fallback_consensus_extreme_inputs_no_overflow() -> None:
    from zoe_autonomy.collaboration import _fallback_consensus_arbitration as collab_fb
    from zoe_autonomy.stem_layering import _fallback_consensus_arbitration as stem_fb

    dists = [[1e308, 1e308], [1e308, 0.0]]
    for fn in (collab_fb, stem_fb):
        res = fn(dists)
        assert json.dumps(res, allow_nan=False)


def test_t5_r3_gap17b_eliza_routes_run_l5_phase_spec_validates_before_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from guiai.gem import _eliza_routes

    ctx = _eliza_routes._ServerContext(
        zoe_root=REPO_ROOT,
        engine=None,
        lock=threading.RLock(),
        avatar_path=None,
        index_html="",
        synthesize_wav_fn=lambda _t, _a="speak": b"",
    )
    called: list[str] = []

    def _boom(name: str):
        called.append(name)
        raise AssertionError(f"import_module({name!r}) must not run before pillar_id validation")

    monkeypatch.setattr(_eliza_routes.importlib, "import_module", _boom)
    for spec in _eliza_routes._L5_PHASE_SPECS.values():
        with pytest.raises(ValueError, match="unknown pillar_id"):
            _eliza_routes._run_l5_phase_spec(ctx, spec, "nonexistent_pillar")
    assert called == []


# ---------------------------------------------------------------------------
# Gap 18: Bridge 5 Theorem 15 overflow / corrupted p_bar / wrong ABSTAIN
# ---------------------------------------------------------------------------


def test_t5_r4_gap18a_theorem15_extreme_dists_preserve_consensus_without_overflow() -> None:
    """kloster_multi_agent_consensus & zoe_os_mind fallback must match collaboration/stem_layering on 1e308 dists."""
    from guiai.gem.kloster_multi_agent_consensus import evaluate_consensus_arbitration
    from zoe_autonomy.collaboration import CollaborationBridge
    from zoe_autonomy.stem_layering import route_stem
    from zoe_autonomy.zoe_os_mind import _fallback_consensus_arbitration as zos_fb

    dists = [[1e308, 1e308], [1e308, 0.0]]
    for fn in (evaluate_consensus_arbitration, zos_fb):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            res = fn(dists)
        assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert res["verdict"] == "COORDINATE_CONSENSUS", res
        assert math.isclose(sum(res["consensus_p_bar"]), 1.0, abs_tol=1e-6), res["consensus_p_bar"]
        assert res["consensus_p_bar"] == pytest.approx([0.75, 0.25], abs=1e-6)
        json.dumps(res, allow_nan=False)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        cb_res = CollaborationBridge().evaluate("test", peer_distributions=dists)
        stem_res = route_stem(
            "architect and refactor multi-file AST verification invariant",
            files_count=5,
            multi_file=True,
            quorum_distributions=[[1e308, 1e308, 0.0, 0.0, 0.0], [1e308, 0.0, 0.0, 0.0, 0.0]],
        )
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert cb_res["measurement"]["theorem15_consensus"]["verdict"] == "COORDINATE_CONSENSUS"
    assert stem_res.quorum_arbitration is not None
    assert stem_res.quorum_arbitration["verdict"] == "COORDINATE_CONSENSUS"


def test_t5_r4_gap18b_theorem15_extreme_weights_preserve_consensus_without_overflow(tmp_path: Path) -> None:
    """Extreme finite weights=[1e308, 1e308] must normalize to [0.5, 0.5] without overflow or wrong ABSTAIN."""
    from guiai.gem.kloster_multi_agent_consensus import evaluate_consensus_arbitration
    from zoe_autonomy.zoe_os_mind import ZoeOSMind, _fallback_consensus_arbitration as zos_fb

    dists = [[1.0, 0.0], [0.9, 0.1]]
    weights = [1e308, 1e308]
    for fn in (evaluate_consensus_arbitration, zos_fb):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", RuntimeWarning)
            res = fn(dists, weights=weights)
        assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
        assert res["verdict"] == "COORDINATE_CONSENSUS", res
        assert res["consensus_p_bar"] == pytest.approx([0.95, 0.05], abs=1e-6)
        json.dumps(res, allow_nan=False)

    mind = ZoeOSMind(REPO_ROOT, tmp_path / "zoe_os_state")
    n_eng = len(mind.registry.components)
    d0 = [1.0] + [0.0] * (n_eng - 1)
    d1 = [0.9, 0.1] + [0.0] * (n_eng - 2)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        turn = mind.process_turn(
            "analyze firmware and particle trigger",
            committee_distributions=[d0, d1],
            committee_weights=[1e308, 1e308],
        )
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert turn["theorem15_consensus"]["verdict"] == "COORDINATE_CONSENSUS"
    assert turn["theorem15_consensus"]["contracted_top_probability"] == pytest.approx(0.95, abs=1e-5)


# ---------------------------------------------------------------------------
# Gap 19: cern_kloster_trigger._median3_probs 1e308 overflow -> sum=0.0
# ---------------------------------------------------------------------------


def test_t5_r4_gap19_cern_median3_probs_extreme_finite_normalizes_to_simplex_no_warnings() -> None:
    """_median3_probs on uniform 1e308 must return a valid probability vector summing to 1.0 with 0 warnings."""
    from guiai.gem.cern_kloster_trigger import _median3_probs

    ev = np.full(5, 1e308, dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        probs = _median3_probs(ev)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert bool(np.all(np.isfinite(probs)))
    assert math.isclose(float(np.sum(probs)), 1.0, abs_tol=1e-9), f"sum={float(np.sum(probs))}, probs={probs}"
    assert probs.tolist() == pytest.approx([0.2] * 5, abs=1e-9)


# ---------------------------------------------------------------------------
# Gap 20: kloster_spatial_optical_law custom PSF 1e308 & _quadrat_zk inf
# ---------------------------------------------------------------------------


def test_t5_r4_gap20a_mtf_blur_loss_extreme_finite_custom_psf_normalizes_cleanly() -> None:
    """Finite positive uniform PSF filled with 1e308 must normalize cleanly without overflow or ValueError."""
    from guiai.gem.kloster_spatial_optical_law import kloster_mtf_blur_loss

    field = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float64)
    psf = np.full((2, 2), 1e308, dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        res = kloster_mtf_blur_loss(field, psf=psf)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert json.dumps(res, allow_nan=False)
    assert math.isclose(res["m2_blurred"], 0.25, abs_tol=1e-12)


def test_t5_r4_gap20b_quadrat_zk_nonfinite_points_no_runtime_warning() -> None:
    """_quadrat_zk with inf coordinates must filter non-finite points cleanly without RuntimeWarning."""
    from guiai.gem.kloster_spatial_optical_law import _quadrat_zk

    pts = np.array([[np.inf, 0.5], [0.5, 0.5], [0.1, 0.1]], dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        res = _quadrat_zk(pts)
    assert not [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert json.dumps(res, allow_nan=False)


# ---------------------------------------------------------------------------
# Gap 21: _quadrat_zk out-of-[0,1]^2 toroidal leak & grid_n < 2 NaN/ValueError
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "oob_pt",
    [
        [1e308, -1e308],
        [1.09, 1.09],
    ],
)
def test_t5_r5_gap21a_quadrat_zk_mixed_inbounds_and_oob_no_overflow_or_corruption(oob_pt: list[float]) -> None:
    """Out-of-[0,1]^2 points must be excluded before both histogram2d and toroidal Ripley distances."""
    from guiai.gem.kloster_spatial_optical_law import _quadrat_zk

    baseline = _quadrat_zk(np.array([[0.1, 0.1], [0.2, 0.2]], dtype=np.float64))
    pts = np.array([[0.1, 0.1], [0.2, 0.2], oob_pt], dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        res = _quadrat_zk(pts)
    runtime_warns = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warns, f"oob={oob_pt} emitted warnings: {[str(w.message) for w in runtime_warns]}"
    assert json.dumps(res, allow_nan=False)
    assert res["points"] == 2
    assert math.isclose(res["besag_l_minus_r"], baseline["besag_l_minus_r"], abs_tol=1e-9), (
        f"oob={oob_pt} corrupted besag_l_minus_r: {res['besag_l_minus_r']} vs {baseline['besag_l_minus_r']}"
    )


@pytest.mark.parametrize("grid_n", [1, 0, -2])
def test_t5_r5_gap21b_quadrat_zk_degenerate_grid_n_returns_finite_json_no_warnings(grid_n: int) -> None:
    """_quadrat_zk with grid_n < 2 must return strict finite JSON with 0 RuntimeWarnings (no vmr=NaN)."""
    from guiai.gem.kloster_spatial_optical_law import _quadrat_zk

    pts = np.array([[0.1, 0.1], [0.2, 0.2]], dtype=np.float64)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", RuntimeWarning)
        res = _quadrat_zk(pts, grid_n=grid_n)
    runtime_warns = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert not runtime_warns, f"grid_n={grid_n} emitted warnings: {[str(w.message) for w in runtime_warns]}"
    encoded = json.dumps(res, allow_nan=False)
    assert "NaN" not in encoded and "Infinity" not in encoded
    assert math.isfinite(res["vmr"])
