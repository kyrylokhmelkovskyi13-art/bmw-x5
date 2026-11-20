#!/usr/bin/env python
"""Export one OBJ asset to MudRunner DirectX .X using io_scene_mudrunner (Blender 2.78)."""
import argparse
import os
import sys
import bpy
from mathutils import Matrix, Vector

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

# Chassis/body meshes must have outward-facing normals before the legacy
# MudRunner .X exporter writes its MeshNormals blocks. Wheel meshes are left
# alone because their source normals/pivots are handled by the wheel pipeline.
if not args.pivot_name:
    import bmesh
    checked_meshes = 0
    for mesh_obj in meshes:
        bm = bmesh.new()
        bm.from_mesh(mesh_obj.data)
        if not bm.faces:
            bm.free()
            raise RuntimeError("Body mesh has no faces: " + mesh_obj.name)

        # First make adjacent face winding consistent. Then orient each
        # disconnected surface component independently: imported GLB objects
        # can contain multiple shells with separate winding.
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        remaining = set(bm.faces)
        mesh_positive = 0
        mesh_negative = 0
        checked_components = 0

        while remaining:
            seed = remaining.pop()
            component = [seed]
            stack = [seed]
            while stack:
                current = stack.pop()
                for edge in current.edges:
                    for neighbor in edge.link_faces:
                        if neighbor in remaining:
                            remaining.remove(neighbor)
                            component.append(neighbor)
                            stack.append(neighbor)

            # Tiny isolated fragments have no stable radial center;
            # recalc_face_normals above still makes their winding consistent.
            if len(component) < 4:
                checked_components += 1
                continue

            component_verts = set(v for face in component for v in face.verts)
            component_center = sum(
                (v.co for v in component_verts), Vector()
            ) / float(len(component_verts))

            def component_direction_counts():
                positive = 0
                negative = 0
                for face in component:
                    face_center = sum(
                        (v.co for v in face.verts), Vector()
                    ) / float(len(face.verts))
                    dot = face.normal.dot(face_center - component_center)
                    if dot > 1e-8:
                        positive += 1
                    elif dot < -1e-8:
                        negative += 1
                return positive, negative

            positive, negative = component_direction_counts()
            if negative > positive:
                bmesh.ops.reverse_faces(bm, faces=component)
                bm.normal_update()
                positive, negative = component_direction_counts()

            measurable = positive + negative
            if measurable and negative > positive:
                bm.free()
                raise RuntimeError(
                    "Inward-facing body component remains in %s: "
                    "outward=%d inward=%d"
                    % (mesh_obj.name, positive, negative)
                )
            mesh_positive += positive
            mesh_negative += negative
            checked_components += 1

        bm.normal_update()
        ratio = (
            float(mesh_positive) / (mesh_positive + mesh_negative)
            if mesh_positive + mesh_negative else 0.0
        )
        if mesh_positive + mesh_negative == 0:
            bm.free()
            raise RuntimeError("No measurable outward body faces in " + mesh_obj.name)
        bm.to_mesh(mesh_obj.data)
        mesh_obj.data.update()
        bm.free()
        checked_meshes += 1
        print("BODY_NORMALS_OUTWARD_OK", mesh_obj.name,
              "outward=", positive, "inward=", negative, "ratio=", round(ratio, 5))

    print("BODY_NORMALS_OUTWARD_VALIDATION_OK", "meshes=", checked_meshes)
if args.pivot_name:
    # Wheel OBJ vertices arrive in vehicle/world coordinates. MudRunner expects
    # the wheel pivot frame at the hub, with the exported mesh centered around
    # that frame. Rebase every mesh vertex into pivot-local coordinates and put
    # both the Blender object origin and the named export pivot at (0, 0, 0).
    world_points = [
        mesh.matrix_world * vertex.co
        for mesh in meshes
        for vertex in mesh.data.vertices
    ]
    if not world_points:
        raise RuntimeError("Wheel export contains no mesh vertices")
    min_v = Vector((
        min(v.x for v in world_points),
        min(v.y for v in world_points),
        min(v.z for v in world_points),
    ))
    max_v = Vector((
        max(v.x for v in world_points),
        max(v.y for v in world_points),
        max(v.z for v in world_points),
    ))
    center = (min_v + max_v) * 0.5

    for mesh in meshes:
        world_matrix = mesh.matrix_world.copy()
        for vertex in mesh.data.vertices:
            vertex.co = world_matrix * vertex.co - center
        mesh.data.update()
        mesh.matrix_world = Matrix.Identity(4)
        mesh.location = (0.0, 0.0, 0.0)
        mesh.rotation_euler = (0.0, 0.0, 0.0)
        mesh.scale = (1.0, 1.0, 1.0)

    pivot = bpy.data.objects.new(args.pivot_name, None)
    bpy.context.scene.objects.link(pivot)
    pivot.location = (0.0, 0.0, 0.0)
    pivot.rotation_euler = (0.0, 0.0, 0.0)
    pivot.scale = (1.0, 1.0, 1.0)
    pivot.matrix_world = Matrix.Identity(4)
    for mesh in meshes:
        mesh.parent = pivot
        mesh.matrix_parent_inverse = Matrix.Identity(4)

    centered_points = [
        mesh.matrix_world * vertex.co
        for mesh in meshes
        for vertex in mesh.data.vertices
    ]
    local_min = Vector((
        min(v.x for v in centered_points),
        min(v.y for v in centered_points),
        min(v.z for v in centered_points),
    ))
    local_max = Vector((
        max(v.x for v in centered_points),
        max(v.y for v in centered_points),
        max(v.z for v in centered_points),
    ))
    local_center = (local_min + local_max) * 0.5
    if max(abs(v) for v in local_center) > 0.00001:
        raise RuntimeError("Wheel geometry was not centered at pivot origin: %r" % (tuple(local_center),))
    if max(abs(v) for v in pivot.location) > 0.000001:
        raise RuntimeError("Wheel pivot origin is not (0, 0, 0)")
    print("WHEEL_PIVOT_ORIGIN_ZERO_OK", args.pivot_name,
          "source_center=", tuple(center), "local_bounds_center=", tuple(local_center))

result = bpy.ops.export_scene.mudrunner(
    filepath=out_path, SelectedOnly=False, CoordinateSystem="LEFT_HANDED",
    UpAxis="Y", FlattenType="scale", ExportNormals=True,
    ExportUVCoordinates=True, ExportMaterials=True,
    ExportSkinWeights=False, ApplyModifiers=True, Verbose=True)
if "FINISHED" not in result or not os.path.isfile(out_path) or os.path.getsize(out_path) < 128:
    raise RuntimeError("MudRunner .X export failed for " + obj_path)
print("ASSET_X_EXPORT_OK", out_path, os.path.getsize(out_path))
