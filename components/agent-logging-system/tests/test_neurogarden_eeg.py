import math

import pytest

from agent_logging_system.neurogarden_eeg import (
    band_powers, delay_embed, higuchi_dimension, lyapunov_estimate, shannon_entropy,
)


def sine(frequency, count=256, rate=256):
    return [math.sin(2 * math.pi * frequency * index / rate) for index in range(count)]


def test_alpha_and_beta_band_power_are_separated():
    alpha = band_powers(sine(10), 256)["alpha"]
    beta = band_powers(sine(20), 256)["beta"]
    assert alpha > 0.99
    assert beta > 0.99
    assert band_powers(sine(10), 256)["beta"] < 0.01


def test_delay_embedding_preserves_order_and_bounds():
    embedded = delay_embed([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], dimension=2, delay=2)
    assert embedded[0] == (2, 0)
    assert embedded[-1] == (15, 13)
    with pytest.raises(ValueError):
        delay_embed([1, 2], dimension=20)


def test_nonlinear_estimates_are_deterministic_and_not_diagnostic():
    samples = [math.sin(index / 7) + 0.1 * math.sin(index / 2) for index in range(256)]
    first = lyapunov_estimate(samples, dimension=3, delay=2)
    second = lyapunov_estimate(samples, dimension=3, delay=2)
    assert first == second
    assert math.isfinite(first)
    dimension = higuchi_dimension(samples)
    assert math.isfinite(dimension)
    assert dimension > 0


def test_shannon_entropy_uses_probability_mass():
    assert shannon_entropy([0.5, 0.5]) == 1
    assert shannon_entropy([1]) == 0
    with pytest.raises(ValueError):
        shannon_entropy([0, 0])
