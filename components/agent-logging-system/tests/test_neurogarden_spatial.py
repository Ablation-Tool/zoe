import pytest

from agent_logging_system.neurogarden_spatial import (
    Volume, average_pool, convolve, matrix_layout_review, project, projection_svg,
    recovery_coefficient, sphere, spatial_piecewise_profile,
)


def test_spatial_piecewise_profile_reproduces_all_chapter_branches():
    assert spatial_piecewise_profile(-3) == {
        "value": 0,
        "branch": "zero-low",
        "source": "MATLAB Numerical Calculations, chapter 6, exercise 6-6 fixed piecewise profile",
        "clinical_claim": False,
    }
    assert spatial_piecewise_profile(-2.5)["value"] == -15.625
    assert spatial_piecewise_profile(-2.5)["branch"] == "cubic"
    assert spatial_piecewise_profile(-2)["value"] == 4
    assert spatial_piecewise_profile(2)["value"] == 4
    assert spatial_piecewise_profile(2.5)["value"] == 2.5
    assert spatial_piecewise_profile(2.5)["branch"] == "linear"
    assert spatial_piecewise_profile(3)["branch"] == "zero-high"
    with pytest.raises(ValueError):
        spatial_piecewise_profile(float("nan"))


def test_matrix_layout_review_preserves_shape_and_guards_singular_inverse():
    singular = matrix_layout_review([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    assert singular["shape"] == [3, 3]
    assert singular["transpose"] == [[1, 4, 7], [2, 5, 8], [3, 6, 9]]
    assert singular["diagonal"] == [1, 5, 9]
    assert singular["column_major"] == [1, 4, 7, 2, 5, 8, 3, 6, 9]
    assert singular["determinant"] == 0
    assert singular["singular"] is True
    assert singular["inversion"] == "refused: zero determinant"
    rectangular = matrix_layout_review([[1, 3, 5], [7, 9, 0]])
    assert rectangular["shape"] == [2, 3]
    assert rectangular["transpose"] == [[1, 7], [3, 9], [5, 0]]
    assert rectangular["column_major"] == [1, 7, 3, 9, 5, 0]
    assert rectangular["determinant"] is None
    assert rectangular["singular"] is None
    invertible = matrix_layout_review([[1, 2], [3, 4]])
    assert invertible["determinant"] == -2
    assert invertible["singular"] is False
    assert "conditioning" in invertible["inversion"]
    assert not singular["clinical_claim"]
    with pytest.raises(ValueError):
        matrix_layout_review([[1, 2], [3]])
    with pytest.raises(ValueError):
        matrix_layout_review([[float("nan")]])


def test_matrix_layout_review_reproduces_chapter_five_determinants():
    result = matrix_layout_review([[1, 5, -2], [-7, 3, 1], [2, 2, -2]])
    assert result["determinant"] == -28
    assert result["singular"] is False
    rank_two = matrix_layout_review([[i + j - 0.5 for j in range(1, 6)] for i in range(1, 6)])
    assert rank_two["determinant"] == 0
    assert rank_two["singular"] is True
    assert rank_two["inversion"] == "refused: zero determinant"


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
