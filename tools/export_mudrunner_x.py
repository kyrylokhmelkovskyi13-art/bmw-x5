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
os.makedirs(os.path.dirname(out_path), exist_ok=True)

# Start with a clean scene. The OBJ importer preserves the exported object names.
bpy.ops.wm.read_factory_settings(use_empty=True)
sys.path.insert(0, os.path.dirname(addon_dir))
import io_scene_mudrunner
io_scene_mudrunner.register()

bpy.ops.import_scene.obj(filepath=obj_path, use_split_objects=True, use_split_groups=True)
objects = [o for o in bpy.context.scene.objects if o.type == "MESH"]
if not objects:
    raise RuntimeError("OBJ import produced no mesh objects")

# This is deliberately a static geometry/exporter compatibility test only.
# It does not create MudRunner physics frames, collision meshes, or truck XML.
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
