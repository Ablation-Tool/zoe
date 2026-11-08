import math

from agent_logging_system.neurogarden_neural import open_neural_world


def test_neural_world_combines_atlas_and_synthetic_signal_analysis():
    samples = [math.sin(2 * math.pi * 10 * index / 256) for index in range(256)]
    world = open_neural_world(samples, 256)
    observation = world.document()["neural_observation"]
    assert observation["band_powers"]["alpha"] > 0.99
    assert observation["band_powers"]["beta"] < 0.01
    assert observation["clinical_claim"] is False
    assert len(world.experiments) == 13
    assert world.experiments["neuroscience-013"].status == "measured"
