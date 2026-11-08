import json

import pytest

from agent_logging_system.neurogarden_world import World


def measured_world():
    world = World("test")
    experiment = world.open("neuroscience", "How does PSF blur affect a synthetic sphere?", "Biomedical Imaging §2.5", "synthetic teaching only")
    world.measure(experiment.identifier, {"peak": 0.4}, "Gaussian convolution", "7³ synthetic voxels")
    return world, experiment


def test_measurement_review_and_action_remain_separate():
    world, experiment = measured_world()
    assert experiment.status == "measured"
    assert experiment.measurements[0]["evidence"] is False
    assert experiment.executed is False
    world.review(experiment.identifier, "human-reviewer", "accepted")
    assert experiment.status == "reviewed"
    assert experiment.executed is False
    document = world.document()
    assert document["experiments"][0]["review"]["decision"] == "accepted"
    assert document["experiments"][0]["executed"] is False


def test_world_requires_sources_and_bounds():
    world = World(max_experiments=1)
    with pytest.raises(ValueError):
        world.open("neuroscience", "missing limitations", "source", "")
    world.open("biology", "alignment", "Basic Applied Bioinformatics §9", "teaching only")
    with pytest.raises(ValueError):
        world.open("cern", "capacity", "test", "bounded")
    with pytest.raises(ValueError):
        world.review("biology-001", "reviewer", "accepted")


def test_scene_is_deterministic_and_export_never_overwrites(tmp_path):
    world, _ = measured_world()
    assert world.scene_svg() == world.scene_svg()
    assert "ZOE + NICK" in world.scene_svg()
    output = tmp_path / "world.json"
    world.save(output)
    document = json.loads(output.read_text())
    assert document["schema"] == "neurogarden-world-v1"
    with pytest.raises(FileExistsError):
        world.save(output)


def test_horizons_expand_without_opening_experiments_or_executing():
    first = World("shared")
    second = World("shared")
    proposal = first.horizon()
    assert proposal["opened"] is False
    assert not first.experiments
    second.horizon()
    assert first.pulse() == second.pulse()
    assert first.ordinal == second.ordinal == 2
    assert not first.experiments and not second.experiments
    assert first.document()["experiments"] == []
    assert "Living geometry" in first.scene_svg()
