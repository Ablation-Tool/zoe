"""Tests for Dorothy's Continuum Volume Display and Zoe's Multi-Head Vision Dissector."""

from pathlib import Path
import tempfile
import numpy as np
from PIL import Image
import pytest

from agent_logging_system.neurogarden_continuum import (
    ContinuumVolume,
    accessible_volume,
    generate_hyperstreamline_tracts,
    render_volume_raycast,
    transfer_function_neurosurg,
)
from agent_logging_system.neurogarden_vision_heads import (
    compute_patch_embeddings,
    compute_self_attention,
    render_multihead_dissection,
)


def test_accessible_volume_monotonicity_and_bounds():
    prob = np.array([0.1, 0.4, 0.7, 0.9, 0.95], dtype=np.float32)
    count_low, frac_low = accessible_volume(prob, tau=0.2)
    count_mid, frac_mid = accessible_volume(prob, tau=0.65)
    count_high, frac_high = accessible_volume(prob, tau=0.92)

    assert count_low == 4
    assert count_mid == 3
    assert count_high == 1
    assert frac_low > frac_mid > frac_high
    assert pytest.approx(frac_mid, abs=1e-6) == 3 / 5

    with pytest.raises(ValueError):
        accessible_volume(prob, tau=1.2)
    with pytest.raises(ValueError):
        accessible_volume(prob, tau=-0.1)


def test_continuum_volume_raycast_and_tracts():
    d, h, w = 16, 16, 16
    density = np.zeros((d, h, w), dtype=np.float32)
    density[5:11, 5:11, 5:11] = 0.75
    confidence = np.full((d, h, w), 0.80, dtype=np.float32)
    confidence[0:4, :, :] = 0.40

    vol = ContinuumVolume(shape=(d, h, w), density=density, confidence=confidence)
    sd, sc = vol.sample_trilinear(0.0, 0.0, 0.0)
    assert sd > 0.7
    assert sc > 0.75

    rgb, meta_map, stats = render_volume_raycast(vol, width=24, height=24, steps=20, tau=0.65)
    assert rgb.shape == (24, 24, 3)
    assert meta_map.shape == (24, 24)
    assert np.all((rgb >= 0.0) & (rgb <= 1.0))
    assert stats["tau_threshold"] == 0.65
    assert stats["total_voxels"] == d * h * w
    assert stats["accessible_volume_count"] == (12 * 16 * 16)

    c, a = transfer_function_neurosurg(0.8)
    assert c.shape == (3,)
    assert 0.0 < a <= 1.0

    tracts = generate_hyperstreamline_tracts(n_points=40)
    assert len(tracts) == 2
    assert tracts[0]["points"].shape == (40, 3)


def test_multihead_vision_embeddings_and_attention():
    rng = np.random.default_rng(7)
    arr = rng.integers(0, 255, size=(128, 128, 3), dtype=np.uint8)
    emb, centers, edge_map, chroma_map, density_map = compute_patch_embeddings(arr, grid_n=8)

    assert emb.shape == (64, 8)
    assert centers.shape == (64, 2)
    assert edge_map.shape == (128, 128)
    assert chroma_map.shape == (128, 128, 3)
    assert density_map.shape == (128, 128)

    attn = compute_self_attention(emb, temperature=0.25)
    assert attn.shape == (64, 64)
    assert np.all(attn >= 0.0)
    row_sums = np.sum(attn, axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-5)

    with tempfile.TemporaryDirectory() as tmpdir:
        in_path = Path(tmpdir) / "in.png"
        out_path = Path(tmpdir) / "out.png"
        Image.fromarray(arr).save(in_path)
        telemetry = render_multihead_dissection(in_path, out_path, grid_n=8)
        assert out_path.exists()
        assert telemetry["total_tokens"] == 64
        assert telemetry["mean_attention_entropy"] > 0.0


def test_book_ingest_hashes_chapters_and_dissects_plates():
    from agent_logging_system.neurogarden_ingest import ingest_book_directory

    rng = np.random.default_rng(11)
    arr = rng.integers(0, 255, size=(96, 96, 3), dtype=np.uint8)
    with tempfile.TemporaryDirectory() as tmpdir:
        book_dir = Path(tmpdir) / "sample-book"
        img_dir = book_dir / "images"
        img_dir.mkdir(parents=True)
        (book_dir / "001_ch1.html").write_text("<html><body><h1>Ch1</h1></body></html>", encoding="utf-8")
        Image.fromarray(arr).save(img_dir / "plate1.png")

        out_dir = Path(tmpdir) / "ingest-out"
        manifest = ingest_book_directory(book_dir, out_dir, max_plates=1, grid_n=8)
        assert manifest["chapter_count"] == 1
        assert manifest["image_count"] == 1
        assert manifest["dissected_plate_count"] == 1
        assert manifest["clinical_action_authorized"] is False
        assert manifest["fully_read_claimed"] is False
        assert (out_dir / "ingest-manifest.json").is_file()

        with pytest.raises(FileExistsError):
            ingest_book_directory(book_dir, out_dir, max_plates=1, grid_n=8)

