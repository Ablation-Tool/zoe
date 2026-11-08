import pytest

from agent_logging_system.neurogarden_spatial import (
    Volume, average_pool, convolve, project, projection_svg, recovery_coefficient, sphere,
)


def test_projection_axes_preserve_matrix_shapes_and_sums():
    volume = Volume(2, 2, 2, (1, 1, 1, 1, 1, 1, 1, 1))
    assert project(volume, "z") == [[2, 2], [2, 2]]
    assert project(volume, "y") == [[2, 2], [2, 2]]
    assert project(volume, "x") == [[2, 2], [2, 2]]
    with pytest.raises(ValueError):
        project(volume, "time")


def test_gaussian_psf_reduces_peak_recovery_without_creating_detail():
    original = sphere(7)
    blurred = convolve(original, 1.0)
    assert max(blurred.values) < max(original.values)
    assert 0 < recovery_coefficient(original, blurred) < 1
    assert all(value >= 0 for value in blurred.values)
    pooled = average_pool(blurred, 2)
    assert pooled.width == pooled.depth == pooled.height == 4
    assert all(value >= 0 for value in pooled.values)


def test_projection_svg_is_local_bounded_markup():
    svg = projection_svg(project(sphere(5), "z"), "Tiny <Zoe> & Dorothy")
    assert svg.startswith("<svg")
    assert "Tiny &lt;Zoe&gt; &amp; Dorothy" in svg
    assert "<script" not in svg
    assert "http" not in svg.replace('xmlns="http://www.w3.org/2000/svg"', "")
    with pytest.raises(ValueError):
        projection_svg([[0]])


def test_volume_bounds_are_enforced():
    with pytest.raises(ValueError):
        Volume(0, 1, 1, ())
    with pytest.raises(ValueError):
        sphere(0)
    with pytest.raises(ValueError):
        convolve(sphere(3), 4)
