#!/usr/bin/env python
"""Export one OBJ asset to MudRunner DirectX .X using io_scene_mudrunner (Blender 2.78)."""
import argparse
import os
import sys
import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
p = argparse.ArgumentParser()
p.add_argument("--obj", required=True)
p.add_argument("--addon-dir", required=True)
p.add_argument("--out", required=True)
p.add_argument("--pivot-name", default="")
args = p.parse_args(argv)
obj_path, out_path, addon_dir = map(os.path.abspath, (args.obj, args.out, args.addon_dir))
if not os.path.isfile(obj_path):
    raise RuntimeError("OBJ input missing: " + obj_path)
if not os.path.isdir(addon_dir):
    raise RuntimeError("MudRunner exporter addon missing: " + addon_dir)
os.makedirs(os.path.dirname(out_path), exist_ok=True)

bpy.ops.wm.read_factory_settings()
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
sys.path.insert(0, os.path.dirname(addon_dir))
import io_scene_mudrunner
io_scene_mudrunner.register()
bpy.ops.import_scene.obj(filepath=obj_path, use_split_objects=True, use_split_groups=True)
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not meshes:
    raise RuntimeError("OBJ import produced no mesh objects")
if args.pivot_name:
    points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    center = sum(points, Vector()) / len(points)
    pivot = bpy.data.objects.new(args.pivot_name, None)
    bpy.context.scene.objects.link(pivot)
    pivot.location = center
    for mesh in meshes:
        mesh.parent = pivot
        mesh.matrix_parent_inverse = pivot.matrix_world.inverted()

result = bpy.ops.export_scene.mudrunner(
    filepath=out_path, SelectedOnly=False, CoordinateSystem="LEFT_HANDED",
    UpAxis="Y", FlattenType="scale", ExportNormals=True,
    ExportUVCoordinates=True, ExportMaterials=True,
    ExportSkinWeights=False, ApplyModifiers=True, Verbose=True)
if "FINISHED" not in result or not os.path.isfile(out_path) or os.path.getsize(out_path) < 128:
    raise RuntimeError("MudRunner .X export failed for " + obj_path)
print("ASSET_X_EXPORT_OK", out_path, os.path.getsize(out_path))
