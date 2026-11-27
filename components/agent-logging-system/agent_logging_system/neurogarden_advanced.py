"""Bounded SPD, bioheat, radiobiology, and neutrosophic teaching models from cited chapters."""
import math

SPD_SOURCE = "Riemannian Geometric Statistics in Medical Image Analysis, chapter 3, sections 3.2, 3.3.1, and 3.6.1"
HEAT_SOURCE = "Computational Intelligence and Predictive Analysis for Medical Science, bioheat transfer during RFA"
NS_SOURCE = "Neutrosophic Set in Medical Image Analysis, chapter 12, equations 4-7"


def eigen_symmetric(matrix):
    if len(matrix) != 2 or len(matrix[0]) != 2 or len(matrix[1]) != 2:
        raise ValueError("teaching implementation accepts 2x2 matrices")
    a, b = matrix[0]
    c, d = matrix[1]
    if not all(math.isfinite(value) for value in (a, b, c, d)):
        raise ValueError("matrix entries must be finite")
    if abs(b - c) > 1e-12:
        raise ValueError("matrix must be symmetric")
    discriminant = math.hypot(a - d, 2 * b)
    first = (a + d + discriminant) / 2
    second = (a + d - discriminant) / 2
    if abs(b) < 1e-15:
        v1 = (1.0, 0.0) if a >= d else (0.0, 1.0)
    else:
        length = math.hypot(b, first - a)
        v1 = (b / length, (first - a) / length)
    v2 = (-v1[1], v1[0])
    return (first, second), (v1, v2)


def eigen_spd(matrix):
    eigenvalues, eigenvectors = eigen_symmetric(matrix)
    if min(eigenvalues) <= 0:
        raise ValueError("matrix must be positive definite")
    return eigenvalues, eigenvectors


def spd_apply(matrix, function, positive=True):
    (d1, d2), (v1, v2) = eigen_spd(matrix) if positive else eigen_symmetric(matrix)
    x1, y1 = v1
    x2, y2 = v2
    f1, f2 = function(d1), function(d2)
    return (
        (f1 * x1 * x1 + f2 * x2 * x2, f1 * x1 * y1 + f2 * x2 * y2),
        (f1 * x1 * y1 + f2 * x2 * y2, f1 * y1 * y1 + f2 * y2 * y2),
    )


def spd_log(matrix):
    return spd_apply(matrix, math.log)


def spd_exp(matrix):
    return spd_apply(matrix, math.exp, positive=False)


def spd_sqrt(matrix):
    return spd_apply(matrix, math.sqrt)


def subtract(left, right):
    return tuple(tuple(left[row][column] - right[row][column] for column in range(2))
                 for row in range(2))


def multiply(left, right):
    return tuple(tuple(sum(left[row][index] * right[index][column] for index in range(2))
                       for column in range(2)) for row in range(2))


def inverse(matrix):
    determinant = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    if determinant <= 0:
        raise ValueError("matrix must be positive definite")
    return ((matrix[1][1] / determinant, -matrix[0][1] / determinant),
            (-matrix[1][0] / determinant, matrix[0][0] / determinant))


def frobenius_norm(matrix):
    return math.sqrt(sum(value * value for row in matrix for value in row))


def affine_distance(left, right):
    root_inverse = inverse(spd_sqrt(left))
    middle = multiply(multiply(root_inverse, right), root_inverse)
    return frobenius_norm(spd_log(middle))


def log_euclidean_distance(left, right):
    return frobenius_norm(subtract(spd_log(left), spd_log(right)))


def log_euclidean_mean(matrices):
    if not matrices or len(matrices) > 256:
        raise ValueError("mean requires 1 to 256 SPD matrices")
    logarithms = [spd_log(matrix) for matrix in matrices]
    average = tuple(tuple(sum(matrix[row][column] for matrix in logarithms) / len(logarithms)
                          for column in range(2)) for row in range(2))
    return spd_exp(average)


def pennes_heat(
    steps=200, grid=16, radius=0.05, delta_time=None,
    conductivity=0.512, density=1060, heat_capacity=3600,
    blood_density=1060, blood_heat_capacity=3600, perfusion=0.001,
    electrode_temperature=50.0, body_temperature=37.0,
):
    if not 8 <= grid <= 64 or not 1 <= steps <= 10_000:
        raise ValueError("invalid heat-model bounds")
    if not 0 < radius <= 1 or not 0 < conductivity <= 100 or not 0 < density <= 10_000 \
            or not 0 < heat_capacity <= 100_000 or not 0 < blood_density <= 10_000 \
            or not 0 < blood_heat_capacity <= 100_000 or not 0 <= perfusion <= 1:
        raise ValueError("invalid tissue properties")
    if not -100 < body_temperature < electrode_temperature < 300:
        raise ValueError("invalid teaching temperatures")
    alpha = conductivity / (density * heat_capacity)
    spacing = radius / (grid - 1)
    perfusion_rate = blood_density * blood_heat_capacity * perfusion / (density * heat_capacity)
    stability_limit = 1 / (2 * alpha / spacing ** 2 + perfusion_rate)
    if delta_time is None:
        delta_time = 0.9 * stability_limit
    if not 0 < delta_time <= stability_limit:
        raise ValueError("explicit heat step is unstable")
    temperatures = [body_temperature] * grid
    for _ in range(steps):
        updated = temperatures.copy()
        for index in range(1, grid - 1):
            radius_at_index = index * spacing
            laplacian = (temperatures[index - 1] - 2 * temperatures[index] + temperatures[index + 1]) / spacing ** 2
            radial = (temperatures[index - 1] - temperatures[index + 1]) / (2 * radius_at_index * spacing)
            updated[index] += delta_time * (alpha * (laplacian + radial) + perfusion_rate * (body_temperature - temperatures[index]))
        updated[0] = electrode_temperature
        updated[-1] = updated[-2]
        temperatures = updated
    return {
        "temperatures_celsius": temperatures,
        "spacing_m": spacing,
        "delta_time_s": delta_time,
        "steps": steps,
        "perfusion_rate_per_second": perfusion_rate,
        "source": HEAT_SOURCE,
        "clinical_claim": False,
    }


def neutrosophic_similarity(left, right):
    for name, triple in (("left", left), ("right", right)):
        if len(triple) != 3 or any(not math.isfinite(value) or not 0 <= value <= 1 for value in triple):
            raise ValueError(f"{name} memberships must be finite values in [0, 1]")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        raise ValueError("similarity requires nonzero membership vectors")
    return numerator / (left_norm * right_norm)


def linear_quadratic_survival(dose_per_fraction, fractions, alpha, beta):
    values = (dose_per_fraction, alpha, beta)
    if any(not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)
           for value in values):
        raise ValueError("LQ parameters must be finite numbers")
    if not isinstance(fractions, int) or isinstance(fractions, bool) or not 1 <= fractions <= 1000:
        raise ValueError("fractions must be a bounded positive integer")
    if not 0 < dose_per_fraction <= 1000 or not 0 <= alpha <= 100 \
            or not 0 <= beta <= 100 or alpha + beta == 0:
        raise ValueError("invalid LQ dose or coefficients")
    return math.exp(-fractions * dose_per_fraction * (alpha + beta * dose_per_fraction))


def radiobiology_model_review():
    survival = []
    for fractions in (1, 2, 5):
        dose = 15 / fractions
        survival.append({
            "fractions": fractions,
            "dose_per_fraction_gy": dose,
            "tumor_survival": linear_quadratic_survival(dose, fractions, 0.35, 0.035),
            "normal_tissue_survival": linear_quadratic_survival(dose, fractions, 0.15, 0.05),
        })
    tumor_survival = linear_quadratic_survival(2, 25, 0.35, 0.035)
    tcp = []
    for volume_cm3 in (0.1, 1, 10, 100):
        expected_survivors = 1e7 * volume_cm3 * tumor_survival
        tcp.append({
            "volume_cm3": volume_cm3,
            "clonogenic_cells": 1e7 * volume_cm3,
            "expected_survivors": expected_survivors,
            "tcp": math.exp(-expected_survivors),
        })
    normal_survival = linear_quadratic_survival(1.2, 50, 0.15, 0.05)
    fsu_failure = (1 - normal_survival) ** 10000
    serial_ntcp = [{
        "irradiated_fsus": count,
        "fsu_failure_probability": fsu_failure,
        "ntcp": -math.expm1(count * math.log1p(-fsu_failure)),
    } for count in (1, 10, 100, 1000)]
    return {
        "survival_at_total_15_gy": survival,
        "tcp_at_total_50_gy": tcp,
        "tcp_parameters": {"fractions": 25, "dose_per_fraction_gy": 2, "alpha": 0.35, "beta": 0.035, "density_per_cm3": 1e7},
        "serial_ntcp_at_total_60_gy": serial_ntcp,
        "ntcp_parameters": {"fractions": 50, "dose_per_fraction_gy": 1.2, "alpha": 0.15, "beta": 0.05, "cells_per_fsu": 10000, "normal_cell_survival": normal_survival},
        "assumptions": [
            "complete repair between fractions, uniform dose, and identical independent cells",
            "Poisson probability of zero surviving clonogenic tumor cells",
            "serial-organ FSU failure requires all 10,000 constituent cells to be killed",
        ],
        "omitted": ["repopulation", "redistribution", "incomplete repair", "reoxygenation", "heterogeneity", "inhomogeneous dose", "patient-specific outcomes"],
        "numeric_precision": "IEEE-754 double; probabilities may round to 0 or 1",
        "radiation_protection": {
            "effective_dose_is_not_absorbed_treatment_dose": True,
            "lnt_low_dose_estimates_are_model_dependent": True,
            "current_jurisdiction_limits_verified": False,
        },
        "source": "Biomedical Imaging (De Gruyter), sections 5.4.4–5.5.3, equations 5.98 and 5.101–5.107",
        "synthetic": True,
        "patient_specific": False,
        "treatment_planning_authorized": False,
        "clinical_claim": False,
    }
