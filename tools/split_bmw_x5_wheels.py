#!/usr/bin/env python3
"""Split the four disconnected rims in Object_97 and pair them with Object_98-101.

Run with Blender's Python:
  blender --background --python tools/split_bmw_x5_wheels.py -- --source bmw-x5.glb --out build/wheel_split
The source GLB is never modified.
"""
import argparse
import sys
from pathlib import Path
import bpy
from mathutils import Vector

WHEEL_MAP = {
    "wheel_a_side_a": ("Object_98", "wheel_pivot_end_a_side_a", (0.841595, -1.69426, -0.567175)),
    "wheel_b_side_a": ("Object_99", "wheel_pivot_end_b_side_a", (0.841595, 1.57315, -0.567175)),
    "wheel_b_side_b": ("Object_100", "wheel_pivot_end_b_side_b", (-0.841595, 1.57315, -0.567175)),
    "wheel_a_side_b": ("Object_101", "wheel_pivot_end_a_side_b", (-0.841595, -1.69426, -0.567175)),
}
RIM_NAME = "Object_97"

def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--source", default="bmw-x5.glb")
    p.add_argument("--out", default="build/wheel_split")
    return p.parse_args(argv)

def select_only(obj):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

def export_obj(path, objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    path.parent.mkdir(parents=True, exist_ok=True)
    if not hasattr(bpy.ops.wm, "obj_export"):
        raise RuntimeError("Blender Wavefront OBJ exporter (bpy.ops.wm.obj_export) is unavailable")
    bpy.ops.wm.obj_export(filepath=str(path.resolve()), export_selected_objects=True, export_materials=True)

def world_center(obj):
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return sum(pts, Vector()) / 8.0

def main():
    args = arguments()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = Path(args.source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    scene_meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    by_name = {o.name: o for o in scene_meshes}
    required = [RIM_NAME] + [v[0] for v in WHEEL_MAP.values()]
    missing = [n for n in required if n not in by_name]
    if missing:
        raise RuntimeError("Missing expected source meshes: " + ", ".join(missing))

    rim = by_name[RIM_NAME]
    # Separate disconnected rim islands into individual Blender objects.
    select_only(rim)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    rim_parts = [o for o in bpy.context.scene.objects
                 if o.type == "MESH" and o.name.startswith(RIM_NAME)]
    if len(rim_parts) != 4:
        raise RuntimeError("Expected exactly four disconnected rim islands in Object_97; found %d. No guessed split was made." % len(rim_parts))

    # Match each rim island to the known tire center, then join the pair.
    unused = set(rim_parts)
    wheel_objects = []
    for wheel_key, (tire_name, pivot_name, center_tuple) in WHEEL_MAP.items():
        target = Vector(center_tuple)
        rim_part = min(unused, key=lambda o: (world_center(o) - target).length)
        unused.remove(rim_part)
        tire = by_name[tire_name]
        select_only(tire)
        tire.select_set(True)
        rim_part.select_set(True)
        bpy.context.view_layer.objects.active = tire
        bpy.ops.object.join()
        tire.name = wheel_key
        tire.data.name = wheel_key + "_mesh"
        tire["mudrunner_pivot"] = pivot_name
        tire["source_rim"] = RIM_NAME
        tire["source_tire"] = tire_name
        wheel_objects.append(tire)

    # Export chassis without the combined rim object or any of the four tires.
    wheel_source_names = {RIM_NAME} | {v[0] for v in WHEEL_MAP.values()}
    body_objects = [o for o in bpy.context.scene.objects
                    if o.type == "MESH" and o not in wheel_objects
                    and o.name not in wheel_source_names
                    and not o.name.startswith(RIM_NAME)]
    if not body_objects:
        raise RuntimeError("No chassis/body meshes remain after wheel extraction")
    export_obj(out / "bmw_x5_body.obj", body_objects)
    for wheel_key, wheel in zip(WHEEL_MAP.keys(), wheel_objects):
        export_obj(out / (wheel_key + ".obj"), [wheel])

    report = [
        "BMW X5 E53 wheel split report",
        "Source: " + source.name,
        "Rim source: Object_97 (four loose mesh islands)",
        "Tire/rim pairs:",
    ]
    for wheel_key, (tire_name, pivot_name, _) in WHEEL_MAP.items():
        report.append("%s: %s + Object_97 island -> %s" % (wheel_key, tire_name, pivot_name))
    report += ["", "Body OBJ excludes Object_97 and Objects 98, 99, 100, 101.",
               "Source GLB was not modified. Review all exported assets in MudRunner Editor."]
    (out / "SPLIT_REPORT.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("WHEEL_SPLIT_OK")

if __name__ == "__main__":
    main()
