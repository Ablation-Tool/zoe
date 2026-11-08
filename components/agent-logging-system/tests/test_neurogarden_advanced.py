import math

import pytest

from agent_logging_system.neurogarden_advanced import (
    affine_distance, linear_quadratic_survival, log_euclidean_distance, log_euclidean_mean,
    neutrosophic_similarity, pennes_heat, radiobiology_model_review, spd_log,
)

IDENTITY = ((1, 0), (0, 1))
ROTATED = ((2, 1), (1, 2))
ANISOTROPIC = ((3, 0.5), (0.5, 1.5))


def test_affine_and_log_euclidean_metrics_are_consistent():
    scaled = ((2, 0), (0, 2))
    expected = math.sqrt(2) * math.log(2)
    assert affine_distance(IDENTITY, scaled) == pytest.approx(expected)
    assert log_euclidean_distance(IDENTITY, scaled) == pytest.approx(expected)
    assert affine_distance(IDENTITY, IDENTITY) == 0
    assert log_euclidean_distance(IDENTITY, IDENTITY) == 0
    assert affine_distance(ROTATED, ROTATED) == pytest.approx(0, abs=1e-12)
    assert log_euclidean_distance(ROTATED, ROTATED) == pytest.approx(0, abs=1e-12)
    assert affine_distance(ROTATED, ANISOTROPIC) > 0
    assert affine_distance(ROTATED, ANISOTROPIC) == pytest.approx(affine_distance(ANISOTROPIC, ROTATED))
    diagonal = ((1, 0), (0, 2))
    assert log_euclidean_distance(IDENTITY, diagonal) == pytest.approx(math.log(2))
    with pytest.raises(ValueError):
        affine_distance(IDENTITY, ((0, 0), (0, 1)))


def test_log_euclidean_mean_is_spd():
    result = log_euclidean_mean([IDENTITY, ((2, 0), (0, 2))])
    assert result[0][0] == pytest.approx(math.sqrt(2))
    assert result[1][1] == pytest.approx(math.sqrt(2))
    diagonal = log_euclidean_mean([IDENTITY, ((2, 0), (0, 1))])
    assert diagonal[0] == pytest.approx((math.sqrt(2), 0))
    assert diagonal[1] == pytest.approx((0, 1))
    noncommuting = log_euclidean_mean([ROTATED, ANISOTROPIC])
    logs = [spd_log(ROTATED), spd_log(ANISOTROPIC)]
    actual_log = spd_log(noncommuting)
    for row in range(2):
        for column in range(2):
            expected = sum(log[row][column] for log in logs) / 2
            assert actual_log[row][column] == pytest.approx(expected)


def test_pennes_model_is_stable_and_preserves_boundaries():
    result = pennes_heat(steps=200)
    temperatures = result["temperatures_celsius"]
    assert all(math.isfinite(value) for value in temperatures)
    assert temperatures[0] == 50
    assert all(37 <= value <= 50 for value in temperatures)
    assert temperatures[-1] < 50
    assert result["clinical_claim"] is False
    cooled = pennes_heat(steps=200, perfusion=0.01)
    assert cooled["temperatures_celsius"][1] < temperatures[1]
    with pytest.raises(ValueError):
        pennes_heat(delta_time=1e9)


def test_neutrosophic_similarity_is_cosine_not_a_diagnosis():
    assert neutrosophic_similarity((1, 0, 0), (1, 0, 0)) == 1
    assert neutrosophic_similarity((1, 0, 0), (0, 1, 0)) == 0
    expected = 0.52 / math.sqrt(0.66) / math.sqrt(0.44)
    assert neutrosophic_similarity((0.8, 0.1, 0.1), (0.6, 0.2, 0.2)) == pytest.approx(expected)
    with pytest.raises(ValueError):
        neutrosophic_similarity((0, 0, 0), (1, 0, 0))
    with pytest.raises(ValueError):
        neutrosophic_similarity((2, 0, 0), (1, 0, 0))


def test_radiobiology_review_reproduces_synthetic_lq_tcp_and_serial_ntcp():
    review = radiobiology_model_review()
    survival = review["survival_at_total_15_gy"]
    assert survival[0]["tumor_survival"] == pytest.approx(math.exp(-15 * (0.35 + 0.035 * 15)))
    assert survival[1]["tumor_survival"] == pytest.approx(math.exp(-15 * (0.35 + 0.035 * 7.5)))
    assert survival[1]["normal_tissue_survival"] > survival[1]["tumor_survival"]
    assert survival[2]["normal_tissue_survival"] > survival[2]["tumor_survival"]
    largest = review["tcp_at_total_50_gy"][-1]
    assert largest["clonogenic_cells"] == 1e9
    assert largest["expected_survivors"] == pytest.approx(1e9 * math.exp(-21))
    assert largest["tcp"] == pytest.approx(math.exp(-1e9 * math.exp(-21)))
    serial = review["serial_ntcp_at_total_60_gy"]
    assert len(serial) == 4
    assert serial[0]["ntcp"] < serial[-1]["ntcp"]
    assert serial[-1]["ntcp"] == pytest.approx(-math.expm1(1000 * math.log1p(-serial[-1]["fsu_failure_probability"])))
    assert all(0 <= item["ntcp"] <= 1 for item in serial)
    assert review["synthetic"] and not review["patient_specific"]
    assert not review["treatment_planning_authorized"]
    assert not review["clinical_claim"]
    assert not review["radiation_protection"]["current_jurisdiction_limits_verified"]
    with pytest.raises(ValueError):
        linear_quadratic_survival(0, 1, 0.35, 0.035)
    with pytest.raises(ValueError):
        linear_quadratic_survival(2, 0, 0.35, 0.035)
    with pytest.raises(ValueError):
        linear_quadratic_survival(2, 1, 0, 0)
