"""Run inside Blender: blender -b --python tools/blender_prepare.py -- --out build/blender"""
import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

def arg_value(flag, default):
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return Path(args[args.index(flag) + 1]) if flag in args else Path(default)

out = arg_value("--out", "build/blender")
out.mkdir(parents=True, exist_ok=True)

# Start from an empty scene and import the source GLB.
bpy.ops.wm.read_factory_settings(use_empty=True)
source = Path("bmw-x5.glb").resolve()
if not source.exists():
    raise FileNotFoundError(source)
bpy.ops.import_scene.gltf(filepath=str(source))

rows = []
for obj in sorted(bpy.context.scene.objects, key=lambda x: x.name):
    if obj.type != "MESH" or obj.data is None:
        continue
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = [min(v[i] for v in corners) for i in range(3)]
    maxs = [max(v[i] for v in corners) for i in range(3)]
    dims = [maxs[i] - mins[i] for i in range(3)]
    center = [(maxs[i] + mins[i]) / 2 for i in range(3)]
    rows.append({
        "name": obj.name,
        "vertices": len(obj.data.vertices),
        "polygons": len(obj.data.polygons),
        "materials": [m.name if m else None for m in obj.data.materials],
        "bounds_min": mins,
        "bounds_max": maxs,
        "dimensions": dims,
        "center": center,
        "rotation_euler": list(obj.matrix_world.to_euler()),
    })

wheel_candidates = []
for row in rows:
    dims = sorted(row["dimensions"])
    has_rubber = any("rubber" in (name or "").lower() for name in row["materials"])
    round_wheel_shape = dims[2] > 0 and 0.92 <= dims[1] / dims[2] <= 1.08 and dims[0] <= dims[2] * 0.60
    if has_rubber and round_wheel_shape:
        row["wheel_candidate"] = True
        wheel_candidates.append({
            "name": row["name"],
            "center": row["center"],
            "dimensions": row["dimensions"],
            "estimated_radius": (dims[1] + dims[2]) / 4,
            "estimated_width": dims[0],
            "axle_axis_candidate": "X (smallest bounding dimension)",
        })

# Cabin-zone shortlist. Include meshes whose bounds intersect the cabin and
# dashboard volume, even when the model author merged several parts into one mesh.
interior_candidates = []
for row in rows:
    lo = row["bounds_min"]
    hi = row["bounds_max"]
    intersects_cabin = (
        hi[0] >= -0.95 and lo[0] <= 0.95 and
        hi[1] >= -1.85 and lo[1] <= 0.95 and
        hi[2] >= -0.05 and lo[2] <= 1.20
    )
    if intersects_cabin and max(row["dimensions"]) <= 3.2:
        interior_candidates.append({
            "name": row["name"], "center": row["center"],
            "dimensions": row["dimensions"], "bounds_min": lo,
            "bounds_max": hi, "materials": row["materials"],
            "vertices": row["vertices"], "polygons": row["polygons"],
        })

report = {
    "source": source.name,
    "wheel_candidates": wheel_candidates,
    "interior_zone_candidates": interior_candidates,
    "units": "Blender scene units; source GLB unit scale retained",
    "object_count": len(rows),
    "objects": rows,
    "note": "Bounds are measured from imported geometry. Object labels do not identify mechanical function by themselves."
}
(out / "geometry_inventory.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

# Export all imported mesh objects to Wavefront OBJ as an interchange format.
# This is NOT the proprietary MudRunner .X format.
bpy.ops.object.select_all(action="DESELECT")
for obj in bpy.context.scene.objects:
    if obj.type == "MESH":
        obj.select_set(True)
bpy.context.view_layer.objects.active = next((o for o in bpy.context.scene.objects if o.type == "MESH"), None)
if hasattr(bpy.ops.wm, "obj_export"):
    bpy.ops.wm.obj_export(
        filepath=str((out / "bmw_x5_interchange.obj").resolve()),
        export_selected_objects=True,
        export_materials=True,
    )
    bpy.ops.object.select_all(action="DESELECT")
    wheel_names = {item["name"] for item in wheel_candidates}
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name in wheel_names:
            obj.select_set(True)
    bpy.context.view_layer.objects.active = next(
        (o for o in bpy.context.scene.objects if o.type == "MESH" and o.name in wheel_names), None
    )
    if wheel_names:
        bpy.ops.wm.obj_export(
            filepath=str((out / "wheel_candidates.obj").resolve()),
            export_selected_objects=True,
            export_materials=True,
        )
    bpy.ops.object.select_all(action="DESELECT")
    interior_names = {item["name"] for item in interior_candidates}
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and obj.name in interior_names:
            obj.select_set(True)
    bpy.context.view_layer.objects.active = next(
        (o for o in bpy.context.scene.objects if o.type == "MESH" and o.name in interior_names), None
    )
    if interior_names:
        bpy.ops.wm.obj_export(
            filepath=str((out / "interior_zone_candidates.obj").resolve()),
            export_selected_objects=True,
            export_materials=True,
        )
else:
    raise RuntimeError("This Blender build has no Wavefront OBJ exporter")

print("Prepared geometry inventory for", len(rows), "mesh objects")
