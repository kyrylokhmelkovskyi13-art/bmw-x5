#!/usr/bin/env python3
"""Create a conservative wheel-pivot specification from the measured GLB inventory.

This does not modify the truck mesh or claim MudRunner axis compatibility. It
records the measured wheel centers and dimensions so pivots can be authored in
the Editor after confirming the exported coordinate convention.
"""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("inventory", help="geometry_inventory.json from blender_prepare.py")
p.add_argument("--out", default="build/wheel_pivot_candidates.json")
args = p.parse_args()

inventory = json.loads(Path(args.inventory).read_text(encoding="utf-8"))
wheels = inventory.get("wheel_candidates", [])
if len(wheels) != 4:
    raise SystemExit("Expected exactly four geometry-based wheel candidates; got %d" % len(wheels))

result = {
    "source": inventory.get("source"),
    "coordinate_space": inventory.get("units"),
    "status": "candidate_only_not_game_validated",
    "pivot_candidates": [],
    "notes": [
        "Pivot positions are measured from imported GLB object bounds, not guessed.",
        "The smallest bounding dimension suggests the axle direction is source X; verify the exported .X axis convention in MudRunner Editor before using it.",
        "The two wheel groups at source Y=-1.69426 and Y=+1.57315 are kept as end-A/end-B; front/rear is intentionally not assigned without confirming the vehicle forward axis.",
        "No wheel mesh geometry is altered by this report."
    ]
}

for wheel in sorted(wheels, key=lambda x: x["name"]):
    center = wheel["center"]
    dims = wheel["dimensions"]
    result["pivot_candidates"].append({
        "source_mesh": wheel["name"],
        "pivot_center_source": center,
        "estimated_radius_source_units": wheel["estimated_radius"],
        "estimated_width_source_units": wheel["estimated_width"],
        "axle_axis_candidate_source": "X",
        "side_candidate": "positive-X" if center[0] > 0 else "negative-X",
        "end_candidate": "negative-Y" if center[1] < 0 else "positive-Y",
        "bounding_dimensions_source": dims
    })

out = Path(args.out)
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
