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
# The chassis export needs a MudRunner collision frame named "cdt". The exporter
# interprets Y as vertical; dimensions are length, height, width in meters.
if not args.pivot_name:
    # Build collision from the complete imported chassis geometry bounds.
    body_points = [o.matrix_world * Vector(corner) for o in meshes for corner in o.bound_box]
    if not body_points:
        raise RuntimeError("Cannot build CDT: chassis has no bounding-box points")
    margin = 0.02
    min_x = min(v.x for v in body_points) - margin
    max_x = max(v.x for v in body_points) + margin
    min_y = min(v.y for v in body_points) - margin
    max_y = max(v.y for v in body_points) + margin
    min_z = min(v.z for v in body_points) - margin
    max_z = max(v.z for v in body_points) + margin
    verts = [(min_x,min_y,min_z), (max_x,min_y,min_z), (max_x,max_y,min_z), (min_x,max_y,min_z),
             (min_x,min_y,max_z), (max_x,min_y,max_z), (max_x,max_y,max_z), (min_x,max_y,max_z)]
    faces = [(0,1,2,3), (4,7,6,5), (0,4,5,1), (1,5,6,2),
             (2,6,7,3), (3,7,4,0)]
    cdt_mesh = bpy.data.meshes.new("cdt")
    cdt_mesh.from_pydata(verts, [], faces)
    cdt_mesh.update()
    cdt_obj = bpy.data.objects.new("cdt", cdt_mesh)
    bpy.context.scene.objects.link(cdt_obj)
    cdt_obj.parent = None
    cdt_obj.matrix_world.identity()
    meshes.append(cdt_obj)
    if len(cdt_obj.data.vertices) != 8 or len(cdt_obj.data.polygons) != 6:
        raise RuntimeError("CDT collision mesh was not created as an 8-vertex/6-face box")
    print("CDT_COLLISION_BOUNDS", (min_x,min_y,min_z), (max_x,max_y,max_z))
if not meshes:
    raise RuntimeError("OBJ import produced no mesh objects")
if args.pivot_name:
    points = [o.matrix_world * Vector(c) for o in meshes for c in o.bound_box]
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
