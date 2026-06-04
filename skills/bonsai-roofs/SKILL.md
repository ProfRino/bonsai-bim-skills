---
name: bonsai-roofs
description: |
  Add roofs (mono-pitch / hip / gable / flat) and fit walls to roof
  underside via proper IFC clipping (IfcBooleanClippingResult +
  IfcHalfSpaceSolid) — not Blender Boolean modifiers. Trigger when the
  user wants to add a roof of any topology, or fit walls to a roof slope.
---

# bonsai-roofs — 4 roof topologies + wall-fit helpers

## When to use this

Trigger on:
- "add roof", "add a roof"
- "mono-pitch", "hip roof", "gable roof", "flat roof", "shed roof"
- "fit walls to roof", "clip walls under roof", "wall-roof gap"

For walls themselves: see [`bonsai-walls`](../bonsai-walls/).

## Core principle: ALWAYS IFC/BIM-correct

Roof clipping of wall tops MUST use `IfcBooleanClippingResult` with
`IfcHalfSpaceSolid` operands on the wall's representation — NOT a
Blender Boolean modifier (modifiers get LOST on IFC export, leaving
uniform-height walls that poke through the roof in every IFC viewer).

| Intent | ✅ IFC mechanism | ❌ Don't |
|---|---|---|
| Parametric roof | `bim.add_roof` + `BBIM_Roof` pset + edit-finish wrap | Custom mesh + `assign_class("IfcRoof")` |
| Wall slope at the top | `ifcopenshell.api.geometry.add_boolean(DIFFERENCE, [half_space])` → `IfcBooleanClippingResult` | Blender Boolean modifier |

## Pick the right roof for your topology

| Helper | Topology | Returns | BIM debt? |
|---|---|---|---|
| `add_hip_roof(footprint_xy, base_z, angle_deg, thickness, name)` | All 4 edges slope to a ridge or apex | Real BBIM_Roof parametric | None |
| `add_gable_roof(footprint_xy, base_z, angle_deg, thickness, gable_edge_indices, name)` | 2 sloped + 2 vertical gable ends | Real BBIM_Roof parametric (with rake edges at π/2) | None |
| `add_flat_roof(footprint_xy, base_z, thickness, name)` | No slope — solidified slab assigned IfcRoof.FLAT_ROOF | IfcRoof from IfcSlab | None |
| `add_mono_pitch_roof(room_min, room_max, wall_top_z, slope_axis, angle_deg, thickness, overhang, name)` | Single slope, two gable triangles | IfcRoof with **IfcFacetedBrep** body | ⚠️ Not BBIM_parametric — Bonsai's `add_roof` only supports HIP/GABLE upstream |

Each builder follows the same flow internally: `bpy.ops.bim.add_roof` →
`enable_editing_roof` → set props → `finish_editing_roof` (same
two-phase pattern as doors / windows).

### Wall-fit pairings

Pair each roof with the matching wall-fit helper:

| Roof | Wall-fit |
|---|---|
| Hip | `fit_walls_to_hip_roof(walls_by_side, eave_z, angle_deg, room_min, room_max, overhang, roof_thickness)` |
| Gable | `fit_walls_to_gable_roof(walls_by_side, eave_z, angle_deg, room_min, room_max, overhang, gable_sides, roof_thickness)` |
| Flat | (none needed — walls stay rectangular at the eave height) |
| Mono-pitch | `fit_walls_to_mono_pitch_roof_ifc(...)` — IFC-correct via clippings |

⚠️ **`fit_walls_to_mono_pitch_roof()` (no `_ifc` suffix) is DEPRECATED.**
It uses a Blender Boolean modifier which is LOST on IFC export. Use
`fit_walls_to_mono_pitch_roof_ifc(...)` instead — produces real
`IfcBooleanClippingResult` operations.

## Example — hip roof on a 4 × 4 m base

```python
import bonsai_bim_helpers as bw

W, D, H = 4.0, 4.0, 3.0
OVERHANG = 0.3

footprint = [
    (-OVERHANG, -OVERHANG),
    (W + OVERHANG, -OVERHANG),
    (W + OVERHANG, D + OVERHANG),
    (-OVERHANG, D + OVERHANG),
]
bw.add_hip_roof(
    footprint_xy=footprint, base_z=H,
    angle_deg=35.0, thickness=0.15,
    name="Hip_Roof",
)

# Walls (assume already built as south/east/north/west IfcWalls)
bw.fit_walls_to_hip_roof(
    walls_by_side={
        "south": south, "east": east,
        "north": north, "west": west,
    },
    eave_z=H, angle_deg=35.0,
    room_min=(0, 0), room_max=(W, D),
    overhang=OVERHANG,
    roof_thickness=0.15,
)
```

## Gable orientation — the counter-intuitive rule

`add_gable_roof(gable_edge_indices=(1, 3))` on a CCW polygon
`[(0,0), (W,0), (W,D), (0,D)]` produces a ridge along the **Y axis** at
x = W/2 — meaning **the gable ends face SOUTH + NORTH**, not east + west.

Always verify the ridge direction in the resulting roof bbox before
calling `fit_walls_to_gable_roof`. Pass `gable_sides=("south", "north")`
in this typical case.

## Roof-specific gotchas (learned the hard way)

- **`bim.add_roof` props don't generate geometry on their own.** Always
  wrap with `enable_editing_roof → set props → finish_editing_roof`.
  Same two-phase pattern as doors / windows.
- **`Bonsai's add_roof builds the slab with TOP face at `wall_top_z`** —
  so for a roof sitting on top of 3 m walls, pass `base_z=3.0` and the
  slab top is at z=3.0, sloping upward to the ridge.
- **Multi-plane wall clips: ONE `add_boolean` call beats nested
  individual calls.** Use
  `ifcopenshell.api.geometry.add_boolean(first_item=base,
  second_items=[hs1, hs2], operator="DIFFERENCE")` with multiple
  `IfcHalfSpaceSolid` operands in a single call. `_clip_wall_with_planes()`
  internally does this.
- **`IfcHalfSpaceSolid.AgreementFlag=False`** is the convention for
  half-spaces in Bonsai. Confusing if you're used to the opposite
  convention from CGAL / OpenCASCADE.
- **Plane reference point far from origin breaks the engine.** When
  transforming a world-space plane to wall-local frame, the reference
  point can land tens of metres away in local coords (e.g. local_y =
  +16 for east wall, −12 for west wall) and the east-vs-west asymmetry
  causes clips to silently fail on one side. Project the reference
  point to the closest plane point to the wall's origin via
  `pt = (n · pt) / ||n||² · n`. The helpers do this internally.
- **Cut planes reference the slab BOTTOM, not the eave centreline.**
  Otherwise walls poke through the roof bottom. For a roof sloped at
  `angle_deg`, the bottom-of-slab Z at the eave is
  `eave_z - roof_thickness / cos(angle)` (full vertical_thickness
  offset, not half).
- **Verify wall fit by per-vertex inspection, not bbox z_max.** A wall
  with a triangular gable profile can have its bbox z_max still equal
  to the original wall top — only the vertex check tells you the cut
  actually happened.

## Authoritative source references

| File | Lines | What |
|---|---|---|
| `bim/module/model/roof.py` | (whole) | `BBIM_Roof` add + edit operators |
| `ifcopenshell/api/geometry/add_boolean.py` | (whole) | Multi-operand boolean for IFC clipping |
| `bim/module/model/wall.py` | 1689+ | `DumbWallJoiner.clip` — half-space clipping internals |
