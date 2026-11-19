#!/usr/bin/env python
"""Experimental OBJ -> MudRunner DirectX .X export using Blender 2.78 addon."""
import argparse
import os
import sys

import bpy


def parse_args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--obj", required=True)
    parser.add_argument("--addon-dir", required=True)
    parser.add_argument("--out", required=True)
    return parser.parse_args(argv)


args = parse_args()
obj_path = os.path.abspath(args.obj)
out_path = os.path.abspath(args.out)
addon_dir = os.path.abspath(args.addon_dir)
if not os.path.isdir(addon_dir):
    raise RuntimeError("MudRunner exporter addon directory does not exist: " + addon_dir)
if not os.path.isfile(obj_path):
    raise RuntimeError("OBJ input does not exist: " + obj_path)
if not os.path.isdir(os.path.dirname(out_path)):
    os.makedirs(os.path.dirname(out_path))

# Blender 2.78 predates the use_empty argument supported by newer releases.
bpy.ops.wm.read_factory_settings()
# Blender 2.78 factory settings create a default Cube. Remove every scene
# object before importing so no placeholder geometry leaks into the truck.
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
sys.path.insert(0, os.path.dirname(addon_dir))
import io_scene_mudrunner
io_scene_mudrunner.register()

bpy.ops.import_scene.obj(filepath=obj_path, use_split_objects=True, use_split_groups=True)
objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not objects:
    raise RuntimeError("OBJ import produced no mesh objects")

# Experimental wheel pivot hierarchy: the four geometry-based rubber wheel
# candidates are parented to empty frames placed at their measured world-space
# centers. Parent inverse preserves the visible wheel geometry in place.
# Front/rear and MudRunner axis assignments are intentionally not inferred.
wheel_layout = {
    "Object_98": "wheel_pivot_end_a_side_a",
    "Object_99": "wheel_pivot_end_b_side_a",
    "Object_100": "wheel_pivot_end_b_side_b",
    "Object_101": "wheel_pivot_end_a_side_b",
}
missing = sorted(set(wheel_layout) - {o.name for o in objects})
if missing:
    raise RuntimeError("Missing expected wheel candidate objects: " + ", ".join(missing))

for mesh_name, frame_name in wheel_layout.items():
    wheel = bpy.data.objects[mesh_name]
    world_corners = [wheel.matrix_world * Vector(corner) for corner in wheel.bound_box]
    center = sum(world_corners, Vector()) / 8.0
    pivot = bpy.data.objects.new(frame_name, None)
    bpy.context.scene.objects.link(pivot)
    pivot.location = center
    pivot.rotation_euler = (0.0, 0.0, 0.0)
    pivot.scale = (1.0, 1.0, 1.0)
    wheel.parent = pivot
    wheel.matrix_parent_inverse = pivot.matrix_world.inverted()

# This remains a hierarchy/export experiment only: collision frames, chassis
# bodies, suspension constraints, steering rack, and vehicle XML are not yet
# authored. The four empty frames must be confirmed in MudRunner Editor.
result = bpy.ops.export_scene.mudrunner(
    filepath=out_path,
    SelectedOnly=False,
    CoordinateSystem="LEFT_HANDED",
    UpAxis="Y",
    FlattenType="none",
    ExportNormals=True,
    ExportUVCoordinates=True,
    ExportMaterials=True,
    ExportSkinWeights=False,
    ApplyModifiers=True,
    Verbose=True,
)
if "FINISHED" not in result or not os.path.isfile(out_path) or os.path.getsize(out_path) < 128:
    raise RuntimeError("MudRunner exporter did not produce a plausible .X file")
print("EXPERIMENTAL_X_EXPORT_OK")
print("mesh_objects=%d" % len(objects))
print("output=%s" % out_path)
print("bytes=%d" % os.path.getsize(out_path))
