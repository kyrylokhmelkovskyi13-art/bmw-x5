#!/usr/bin/env python3
"""Structural sanity check for the experimental DirectX text .X export."""
import argparse
import json
import re
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("file")
p.add_argument("--report", default="build/export/x_structure_report.json")
a = p.parse_args()

path = Path(a.file)
data = path.read_bytes()
if len(data) < 128:
    raise SystemExit("FAIL: .X file is missing or too small")

header = data[:16].decode("ascii", errors="replace")
if not header.startswith("xof "):
    raise SystemExit("FAIL: no DirectX .X header")
if b"txt" not in data[:16]:
    raise SystemExit("FAIL: exporter did not produce a text .X file")

text = data.decode("utf-8", errors="replace")
frames = len(re.findall(r"\bFrame\s+[A-Za-z_][A-Za-z0-9_]*\s*\{", text))
meshes = len(re.findall(r"\bMesh(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*\{", text))
materials = len(re.findall(r"\bMaterial(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*\{", text))
mesh_normals = len(re.findall(r"\bMeshNormals\s*\{", text))
mesh_uv = len(re.findall(r"\bMeshTextureCoords\s*\{", text))
# Recover frame ancestry from the nested DirectX text blocks. This checks
# hierarchy, not whether the game accepts the resulting coordinate system.
frame_parent = {}
frame_stack = []
brace_depth = 0
for token in re.finditer(r"\\bFrame\\s+([^\\s{]+)\\s*\\{|[{}]", text):
    value = token.group(0)
    if value.startswith("Frame"):
        name = token.group(1)
        parent = frame_stack[-1][0] if frame_stack else None
        frame_parent[name] = parent
        brace_depth += 1  # opening brace included in the Frame token
        frame_stack.append((name, brace_depth))
    elif value == "{":
        brace_depth += 1
    else:
        brace_depth -= 1
        while frame_stack and frame_stack[-1][1] > brace_depth:
            frame_stack.pop()

expected_wheel_parents = {
    "Object_98": "wheel_pivot_end_a_side_a",
    "Object_101": "wheel_pivot_end_a_side_b",
    "Object_99": "wheel_pivot_end_b_side_a",
    "Object_100": "wheel_pivot_end_b_side_b",
}
wheel_parent_checks = {
    child: {"expected_parent": parent, "actual_parent": frame_parent.get(child),
            "ok": frame_parent.get(child) == parent}
    for child, parent in expected_wheel_parents.items()
}
report = {
    "file": str(path),
    "bytes": len(data),
    "header": header.strip(),
    "frame_count": frames,
    "mesh_count": meshes,
    "material_count": materials,
    "mesh_normals_blocks": mesh_normals,
    "uv_blocks": mesh_uv,
    "frame_names": [name.strip() for name in re.findall(r"\bFrame\s+([^\s{]+)\s*\{", text)],
    "wheel_candidate_frames": [
        name for name in ("Object_98", "Object_99", "Object_100", "Object_101")
        if re.search(r"\bFrame\s+" + re.escape(name) + r"\s*\{", text)
    ],
    "wheel_pivot_frames": [
        name for name in (
            "wheel_pivot_end_a_side_a",
            "wheel_pivot_end_b_side_a",
            "wheel_pivot_end_b_side_b",
            "wheel_pivot_end_a_side_b",
        )
        if re.search(r"\bFrame\s+" + re.escape(name) + r"\s*\{", text)
    ],
    "wheel_parent_checks": wheel_parent_checks,\n    "wheel_candidate_note": "Source mesh names are geometry-based candidates. Pivot frame names are experimental and must be inspected in MudRunner Editor.",
    "warning": "Structural text check only; does not prove MudRunner Editor or in-game compatibility."
}
out = Path(a.report)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
if meshes == 0:
    raise SystemExit("FAIL: no Mesh blocks found")
if len(report["wheel_pivot_frames"]) != 4:
    raise SystemExit("FAIL: expected four exported wheel pivot frames; found %d" % len(report["wheel_pivot_frames"]))
