#!/usr/bin/env python3
"""Measure the four wheel candidates in source-model coordinates.

This is geometry analysis only. It deliberately does not convert source axes
into MudRunner axes or generate physics XML.
"""
import argparse
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("inventory", help="geometry_inventory.json")
parser.add_argument("--out", default="build/wheel_layout_report.json")
args = parser.parse_args()

inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
wheels = inventory.get("wheel_candidates", [])
if len(wheels) != 4:
    raise SystemExit("Expected exactly four wheel candidates; found %d" % len(wheels))

by_name = {w["name"]: w for w in wheels}
if len(by_name) != 4:
    raise SystemExit("Wheel candidate names are not unique")

centers = {name: item["center"] for name, item in by_name.items()}
xs = sorted({round(c[0], 6) for c in centers.values()})
ys = sorted({round(c[1], 6) for c in centers.values()})
zs = [c[2] for c in centers.values()]
if len(xs) != 2 or len(ys) != 2:
    raise SystemExit("Candidates do not form a 2-by-2 layout in source X/Y")

track = abs(xs[1] - xs[0])
wheelbase = abs(ys[1] - ys[0])
mean_z = sum(zs) / len(zs)
radii = [float(w["estimated_radius"]) for w in wheels]
widths = [float(w["estimated_width"]) for w in wheels]

result = {
    "source": inventory.get("source"),
    "coordinate_space": inventory.get("units"),
    "status": "source_geometry_measurement_only",
    "wheel_candidates": [
        {
            "source_mesh": name,
            "center_source": centers[name],
            "radius_estimate_source_units": by_name[name]["estimated_radius"],
            "width_estimate_source_units": by_name[name]["estimated_width"]
        }
        for name in sorted(by_name)
    ],
    "measured_layout": {
        "track_between_wheel_centers_source_units": round(track, 6),
        "wheelbase_between_wheel_centers_source_units": round(wheelbase, 6),
        "mean_wheel_center_height_source_units": round(mean_z, 6),
        "candidate_track_axis_source": "X",
        "candidate_wheelbase_axis_source": "Y",
        "candidate_vertical_axis_source": "Z",
        "mean_radius_source_units": round(sum(radii) / len(radii), 6),
        "mean_width_source_units": round(sum(widths) / len(widths), 6)
    },
    "warnings": [
        "All measurements remain in source GLB/OBJ coordinates and units.",
        "Axis labels describe the observed source geometry only; they are not MudRunner coordinate assignments.",
        "Confirm model orientation and scale in MudRunner Editor before using these values for wheel frames or physics.",
        "This report does not create pivots, collision meshes, suspension, or truck XML."
    ]
}

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
