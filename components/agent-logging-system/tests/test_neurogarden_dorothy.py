from pathlib import Path

from agent_logging_system.neurogarden_dorothy import open_atlas_world, open_default_atlas_world


def test_real_atlas_geometry_is_measured_not_diagnosed():
    world = open_default_atlas_world()
    assert len(world.experiments) == 12
    document = world.document()
    assert document["atlas"]["atlas"].startswith("Allen Mouse")
    assert len(document["atlas"]["observations"]) == 12
    assert all(item["triangles"] > 0 for item in document["atlas"]["observations"])
    assert all("no patient registration" in item["registration"] for item in document["atlas"]["observations"])
    assert document["atlas"]["renderer"].startswith("deterministic software projection")
    assert "<svg" in world.atlas_scene_svg()


def test_atlas_requires_structures():
    try:
        open_atlas_world([])
    except ValueError as error:
        assert "at least one" in str(error)
    else:
        raise AssertionError("empty atlas was accepted")
