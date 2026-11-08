"""Dorothy atlas geometry inside the Neurogarden research universe."""
from .neurogarden_world import World


def observation(record, parse_ply):
    mesh = parse_ply(record["data"])
    if not mesh.vertices:
        raise ValueError("atlas structure has no vertices")
    bounds = []
    center = []
    for axis in range(3):
        values = [vertex[axis] for vertex in mesh.vertices]
        low, high = min(values), max(values)
        bounds.append([low, high])
        center.append((low + high) / 2)
    return {
        "id": record["id"],
        "acronym": record["acronym"],
        "name": record["name"],
        "triangles": len(mesh.faces),
        "vertices": len(mesh.vertices),
        "bounds_ccf_units": bounds,
        "center_ccf_units": center,
        "sha256": record["sha256"],
        "registration": "Allen CCFv3 geometry only; no patient registration or diagnostic inference",
    }


class AtlasWorld(World):
    def __init__(self, scene, report, emblem=None):
        super().__init__("dorothy-neurogarden", emblem=emblem)
        self.atlas_scene = scene
        self.atlas_report = report

    def atlas_scene_svg(self):
        from guiai.gem.render import scene_to_svg
        return scene_to_svg(self.atlas_scene, width=1600)

    def document(self):
        document = super().document()
        document["atlas"] = self.atlas_report
        return document


def open_atlas_world(structures, emblem=None):
    if not structures:
        raise ValueError("at least one atlas structure is required")
    from guiai.gem.dorothy import dorothy_scene
    from guiai.gem.spatial3d import parse_ply
    world = AtlasWorld(*dorothy_scene(structures), emblem=emblem)
    world.attachments["atlas"] = world.atlas_report
    observations = [observation(record, parse_ply) for record in structures]
    for item in observations:
        experiment = world.open(
            "neuroscience",
            f"How does {item['acronym']} geometry project under a declared view?",
            f"Allen CCFv3 structure {item['id']}",
            "atlas geometry only; no patient registration, connectivity, diagnosis, or surgical authority",
        )
        world.measure(
            experiment.identifier,
            item,
            "PLY geometry bounds, source hash, and deterministic atlas projection",
            "Allen Mouse Common Coordinate Framework v3 (2017) meshes only",
        )
    world.attachments["atlas"]["observations"] = observations
    return world


def open_default_atlas_world(emblem=None):
    from guiai.gem.dorothy_data import load_structures
    return open_atlas_world(load_structures(), emblem=emblem)
