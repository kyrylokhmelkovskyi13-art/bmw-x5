#!/usr/bin/env python3
"""Rotate a wheel OBJ around its measured bounding-box center about Y."""
import argparse
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--input", required=True)
p.add_argument("--output", required=True)
p.add_argument("--degrees", type=float, choices=(-90.0, 90.0), required=True)
a = p.parse_args()

src = Path(a.input)
dst = Path(a.output)
lines = src.read_text(encoding="utf-8", errors="strict").splitlines()
verts = []
for line in lines:
    s = line.strip().split()
    if len(s) >= 4 and s[0] == "v":
        verts.append(tuple(map(float, s[1:4])))
if not verts:
    raise SystemExit("OBJ contains no vertices: " + str(src))

mins = [min(v[i] for v in verts) for i in range(3)]
maxs = [max(v[i] for v in verts) for i in range(3)]
c = [(mins[i] + maxs[i]) * 0.5 for i in range(3)]
# X is the measured source axle candidate. Rotation about Y maps X to +/-Z.
# Apply the same rotation to positions relative to wheel center and to normals.
import math
ang = math.radians(a.degrees)
co, si = math.cos(ang), math.sin(ang)

def rotate(x, y, z):
    return (co*x + si*z, y, -si*x + co*z)

out = []
for line in lines:
    s = line.strip().split()
    if len(s) >= 4 and s[0] == "v":
        x, y, z = map(float, s[1:4])
        rx, ry, rz = rotate(x-c[0], y-c[1], z-c[2])
        out.append("v %.9g %.9g %.9g" % (rx+c[0], ry+c[1], rz+c[2]))
    elif len(s) >= 4 and s[0] == "vn":
        x, y, z = map(float, s[1:4])
        rx, ry, rz = rotate(x, y, z)
        out.append("vn %.9g %.9g %.9g" % (rx, ry, rz))
    else:
        out.append(line)
dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text("\n".join(out) + "\n", encoding="utf-8")
print("WHEEL_ROTATION_VARIANT_OK", src.name, "degrees_Y", a.degrees,
      "center", c, "vertex_count", len(verts), "output", dst)
