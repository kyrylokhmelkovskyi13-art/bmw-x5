# BMW X5 wheel pivot candidates

Generated from `geometry_inventory.json` with `tools/analyze_wheel_pivots.py`.

The report records four source-GLB wheel candidates by their measured bounding-box centers and dimensions. It is an inspection aid, not a finished MudRunner wheel rig.

## Current measured candidates

| Source mesh | Source X | Source Y | Source Z | Radius estimate | Width estimate |
|---|---:|---:|---:|---:|---:|
| Object_98 | 0.841595 | -1.694260 | -0.567175 | 0.444803 | 0.363830 |
| Object_99 | 0.841595 | 1.573150 | -0.567175 | 0.444803 | 0.363830 |
| Object_100 | -0.841595 | 1.573150 | -0.567175 | 0.444803 | 0.363830 |
| Object_101 | -0.841595 | -1.694260 | -0.567175 | 0.444803 | 0.363830 |

Values are source GLB / Blender scene units, not confirmed MudRunner meters.

## What is and is not established

- Four separated rubber-like, nearly circular meshes were detected.
- The smallest bounds dimension is source X, so source X is only a candidate axle direction.
- The two Y coordinate groups are labelled negative-Y and positive-Y ends. They are not labelled front/rear because the source vehicle-forward axis has not yet been verified against MudRunner's exported coordinate convention.
- No wheel mesh has been repositioned, rotated, or parented by this report.
- Steering pivots, suspension travel, wheel rotation, collision, and game physics remain unimplemented and untested.

Before creating a working wheel rig, inspect the exported .X in MudRunner Editor and confirm the forward, vertical, and axle axes. Then create the pivot frames at these measured centers using the Editor's verified frame convention.
