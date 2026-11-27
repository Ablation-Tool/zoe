#!/usr/bin/env python3
"""
1-Click Blender 4 / Blender 5 Importer for Dorothy Brain Observatory (MNI152 mm)
Usage:
    blender --python import_dorothy_brain.py
"""
import math
from pathlib import Path
import bpy

HERE = Path(__file__).resolve().parent
COLL_NAME = "Dorothy_Brain_MNI152"

# Create dedicated collection
coll = bpy.data.collections.get(COLL_NAME) or bpy.data.collections.new(COLL_NAME)
if coll.name not in bpy.context.scene.collection.children:
    bpy.context.scene.collection.children.link(coll)

PARTS = [
    ("MNI152_Cortex_Left.obj",  "Cortex_Left_ICBM152",  (0.84, 0.64, 0.59, 1.0), 0.36, 0.15),
    ("MNI152_Cortex_Right.obj", "Cortex_Right_ICBM152", (0.84, 0.64, 0.59, 1.0), 0.36, 0.15),
    ("AAL_Cerebellum.obj",      "Cerebellum_AAL116",    (0.76, 0.55, 0.49, 1.0), 0.48, 0.08),
    ("AAL_Thalamus_Hippocampus_Amygdala.obj", "Thalamus_Limbic_AAL", (0.94, 0.72, 0.24, 1.0), 0.32, 0.05),
    ("CIT168_Subcortical_Nuclei.obj", "Subcortical_CIT168", (0.24, 0.58, 0.94, 1.0), 0.28, 0.05),
]

def make_material(name, rgba, roughness, sss_weight):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = rgba
        bsdf.inputs["Roughness"].default_value = roughness
        if "Subsurface Weight" in bsdf.inputs:
            bsdf.inputs["Subsurface Weight"].default_value = sss_weight
    return mat

for fname, obj_name, rgba, rough, sss in PARTS:
    path = HERE / fname
    if not path.exists():
        continue
    if hasattr(bpy.ops.wm, "obj_import"):
        bpy.ops.wm.obj_import(filepath=str(path))
    else:
        bpy.ops.import_scene.obj(filepath=str(path))
    for obj in list(bpy.context.selected_objects):
        obj.name = obj_name
        # Convert MNI millimeters to meters (0.001) and orient Z-up cleanly
        obj.scale = (0.001, 0.001, 0.001)
        obj.rotation_euler = (0.0, 0.0, 0.0)
        bpy.ops.object.shade_smooth()
        mat = make_material("Mat_" + obj_name, rgba, rough, sss)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        coll.objects.link(obj)

print("Imported Dorothy Brain Observatory MNI152 meshes into collection:", COLL_NAME)
