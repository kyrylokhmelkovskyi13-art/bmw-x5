#!/usr/bin/env python3
"""Split Object_97's rim geometry into four wheels using the tire mesh centers.

Run with Blender's Python:
  blender --background --python tools/split_bmw_x5_wheels.py -- --source bmw-x5.glb --out build/wheel_split
The source GLB is never modified.
"""
import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Vector

# The tire object names and their MudRunner pivot names are known from the
# source model. Wheel centers are measured from the tire meshes at runtime.
WHEEL_MAP = {
    "wheel_a_side_a": ("Object_98", "wheel_pivot_end_a_side_a"),
    "wheel_b_side_a": ("Object_99", "wheel_pivot_end_b_side_a"),
    "wheel_b_side_b": ("Object_100", "wheel_pivot_end_b_side_b"),
    "wheel_a_side_b": ("Object_101", "wheel_pivot_end_a_side_b"),
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
    """World-space center of the object's transformed bounding box."""
    points = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return sum(points, Vector()) / len(points)


def split_rim_faces_by_nearest_tire(rim, tire_centers):
    """Assign every Object_97 polygon to the nearest measured tire center.

    Classification is performed per polygon, not per loose island, so rims
    made from many independent spokes/bolts/caps are handled without assuming
    a particular number of disconnected components.
    """
    source_mesh = rim.data
    buckets = {key: {"vertices": [], "faces": [], "material_indices": [], "smooth": []}
               for key in WHEEL_MAP}
    for polygon in source_mesh.polygons:
        world_centroid = sum(
            (rim.matrix_world @ source_mesh.vertices[index].co
             for index in polygon.vertices),
            Vector()
        ) / len(polygon.vertices)
        nearest_key = min(
            tire_centers,
            key=lambda key: (world_centroid - tire_centers[key]).length_squared
        )
        bucket = buckets[nearest_key]
        vertex_map = {}
        face = []
        for source_index in polygon.vertices:
            if source_index not in vertex_map:
                vertex_map[source_index] = len(bucket["vertices"])
                bucket["vertices"].append(tuple(source_mesh.vertices[source_index].co))
            face.append(vertex_map[source_index])
        bucket["faces"].append(face)
        bucket["material_indices"].append(polygon.material_index)
        bucket["smooth"].append(polygon.use_smooth)

    created = {}
    for key, bucket in buckets.items():
        if not bucket["faces"]:
            raise RuntimeError(
                "No Object_97 polygons were assigned to %s; tire centers may be invalid"
                % key
            )
        mesh = bpy.data.meshes.new(key + "_rim_mesh")
        mesh.from_pydata(bucket["vertices"], [], bucket["faces"])
        mesh.update()
        for material in source_mesh.materials:
            mesh.materials.append(material)
        for polygon, material_index, smooth in zip(
                mesh.polygons, bucket["material_indices"], bucket["smooth"]):
            polygon.material_index = min(material_index, max(0, len(mesh.materials) - 1))
            polygon.use_smooth = smooth
        part = bpy.data.objects.new(key + "_rim_part", mesh)
        bpy.context.scene.collection.objects.link(part)
        part.matrix_world = rim.matrix_world.copy()
        created[key] = part

    return created, {key: len(value["faces"]) for key, value in buckets.items()}


def extract_gltf_textures(out_dir):
    """Save every image imported from the GLB and write a material/image manifest."""
    texture_dir = out_dir / "textures"
    texture_dir.mkdir(parents=True, exist_ok=True)
    image_names = {}
    for index, image in enumerate(bpy.data.images):
        if image.type == "RENDER_RESULT" or image.size[0] == 0 or image.size[1] == 0:
            continue
        base = Path(image.name).stem or ("gltf_image_%02d" % index)
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in base)
        filename = "%02d_%s.png" % (index, safe)
        target = texture_dir / filename
        image.file_format = "PNG"
        image.save(filepath=str(target))
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError("Failed to extract GLB image: " + image.name)
        image_names[image.name] = "textures/" + filename

    lines = ["BMW X5 E53 material and texture inventory", "",
             "Extracted images (PNG):"]
    for name, path in sorted(image_names.items()):
        lines.append("%s -> %s" % (name, path))
    lines += ["", "Material slots and linked base-color images:"]
    for material in bpy.data.materials:
        lines.append("MATERIAL: " + material.name)
        found = False
        if material.use_nodes and material.node_tree:
            for node in material.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    found = True
                    lines.append("  IMAGE: %s -> %s" % (
                        node.image.name, image_names.get(node.image.name, "NOT_EXTRACTED")
                    ))
        if not found:
            lines.append("  IMAGE: none linked through an image-texture node")
    (out_dir / "MATERIAL_TEXTURE_INVENTORY.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print("GLTF_TEXTURES_EXTRACTED", len(image_names))


def main():
    args = arguments()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    source = Path(args.source).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    extract_gltf_textures(out)
    scene_meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    by_name = {obj.name: obj for obj in scene_meshes}
    required = [RIM_NAME] + [value[0] for value in WHEEL_MAP.values()]
    missing = [name for name in required if name not in by_name]
    if missing:
        raise RuntimeError("Missing expected source meshes: " + ", ".join(missing))

    rim = by_name[RIM_NAME]
    tires = {key: by_name[tire_name]
             for key, (tire_name, _pivot_name) in WHEEL_MAP.items()}
    tire_centers = {key: world_center(tire) for key, tire in tires.items()}

    # Partition all rim polygons spatially. This supports hundreds of loose
    # pieces because each face is assigned independently to its nearest tire.
    rim_parts, face_counts = split_rim_faces_by_nearest_tire(rim, tire_centers)

    wheel_objects = []
    for wheel_key, (tire_name, pivot_name) in WHEEL_MAP.items():
        tire = tires[wheel_key]
        rim_part = rim_parts[wheel_key]
        select_only(tire)
        rim_part.select_set(True)
        bpy.context.view_layer.objects.active = tire
        bpy.ops.object.join()
        tire.name = wheel_key
        tire.data.name = wheel_key + "_mesh"
        tire["mudrunner_pivot"] = pivot_name
        tire["source_rim"] = RIM_NAME
        tire["source_tire"] = tire_name
        tire["rim_polygon_count"] = face_counts[wheel_key]
        wheel_objects.append(tire)

    # The original combined rim object is no longer needed; the four generated
    # partitions have been joined to their corresponding tire meshes.
    bpy.data.objects.remove(rim, do_unlink=True)

    wheel_source_names = {RIM_NAME} | {value[0] for value in WHEEL_MAP.values()}
    body_objects = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and obj not in wheel_objects
        and obj.name not in wheel_source_names
        and not obj.name.startswith(RIM_NAME)
    ]
    if not body_objects:
        raise RuntimeError("No chassis/body meshes remain after wheel extraction")

    export_obj(out / "bmw_x5_body.obj", body_objects)
    for wheel_key, wheel in zip(WHEEL_MAP.keys(), wheel_objects):
        export_obj(out / (wheel_key + ".obj"), [wheel])

    report = [
        "BMW X5 E53 wheel split report",
        "Source: " + source.name,
        "Rim source: Object_97 (polygon-level nearest-tire assignment)",
        "Tire centers: world-space bounding-box centers measured from Objects 98-101",
        "Assigned rim polygons:",
    ]
    for wheel_key, (tire_name, pivot_name) in WHEEL_MAP.items():
        report.append("%s: %s + Object_97 polygons=%d -> %s" % (
            wheel_key, tire_name, face_counts[wheel_key], pivot_name
        ))
    report += [
        "",
        "Body OBJ excludes Object_97 and Objects 98, 99, 100, 101.",
        "Source GLB was not modified. Review all exported assets in MudRunner Editor.",
    ]
    (out / "SPLIT_REPORT.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print("WHEEL_SPLIT_OK")


if __name__ == "__main__":
    main()
