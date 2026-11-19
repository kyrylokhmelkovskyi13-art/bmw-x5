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
report = {
    "file": str(path),
    "bytes": len(data),
    "header": header.strip(),
    "frame_count": frames,
    "mesh_count": meshes,
    "material_count": materials,
    "mesh_normals_blocks": mesh_normals,
    "uv_blocks": mesh_uv,
    "frame_names": re.findall(r"\\bFrame\\s+([^\\s{]+)\\s*\\{", text),
    "wheel_candidate_frames": [
        name for name in ("Object_98", "Object_99", "Object_100", "Object_101")
        if re.search(r"\\bFrame\\s+" + re.escape(name) + r"\\s*\\{", text)
    ],
    "wheel_candidate_note": "Names are carried over from the source GLB object indices; wheel function is a geometry-based candidate and must be checked in MudRunner Editor.",
    "warning": "Structural text check only; does not prove MudRunner Editor or in-game compatibility."
}
out = Path(a.report)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
if meshes == 0:
    raise SystemExit("FAIL: no Mesh blocks found")
