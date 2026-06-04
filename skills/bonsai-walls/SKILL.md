---
name: bonsai-walls
description: |
  Create rooms and polyline walls (with PROPER MITERED CORNERS) and fitted
  floor slabs in Blender + Bonsai. Matches what bpy.ops.bim.draw_polyline_wall
  and bpy.ops.bim.draw_slab_from_wall produce interactively. Trigger when the
  user wants to programmatically build IFC walls / partitions / a room
  outline / a slab fitted to wall geometry.
---

# bonsai-walls — walls + slabs + mitered corners

## When to use this

Trigger on:
- "build a room", "create a room", "polyline walls"
- "interior wall", "partition", "divider"
- "exterior wall", "load-bearing wall"
- "floor slab", "fit slab to walls"

For openings + doors + windows: see [`bonsai-openings`](../bonsai-openings/).
For roofs and roof-to-wall fits: see [`bonsai-roofs`](../bonsai-roofs/).
For stairs + railings: see [`bonsai-stairs`](../bonsai-stairs/).
For spaces + grid: see [`bonsai-spaces-grid`](../bonsai-spaces-grid/).
For project setup + audit + IDS: see [`bonsai-project-setup`](../bonsai-project-setup/).

## Core principle: ALWAYS IFC/BIM-correct

Every element, void, fill, material, parametric attribute MUST be a real
IFC entity with proper relationships. Blender modifiers (Boolean, Solidify,
Array) and direct mesh edits LOOK right in the viewport but get LOST on
IFC export and break interop with every other IFC tool (Solibri, BIMVision,
IFC.js, Revit, ArchiCAD).

For every operation, ask: "Will this survive `bim.save_project` → close →
re-open?" If no, find the IFC mechanism. The common ones:

| Intent | ✅ IFC-correct mechanism | ❌ Don't |
|---|---|---|
| Wall body | `DumbWallGenerator.create_wall_from_2_points` → LAYER2 + material set | Plain mesh `bpy.ops.mesh.primitive_cube_add` |
| Wall-to-wall connection | `DumbWallJoiner.connect` → `IfcRelConnectsPathElements` + miter regen | Just place walls touching each other |
| Wall clip / cut | `ifcopenshell.api.geometry.add_clipping` → `IfcBooleanClippingResult` | Blender Boolean modifier |
| Slab from walls | `DumbSlabGenerator("WALLS")` + Z-translate via `edit_object_placement` | `bpy.ops.mesh.primitive_plane_add` |
| Material | `material.assign_material` → `IfcRelAssociatesMaterial` + constituent set | Blender material slot only |

## Why the obvious approaches fail

| Approach | Problem |
|---|---|
| ifc-bonsai-mcp `create_polyline_walls` | Creates independent walls; no IFC connections; corners overlap |
| `bpy.ops.bim.extend_walls_to_wall` | Requires LAYER2-compatible walls; produces butt-joints (one wall ends at the other's face), not the wall-axis miter |
| `bpy.ops.bim.add_occurrence` per segment | Creates 1m-default walls; doesn't set proper axis representation length |
| `bpy.ops.bim.draw_polyline_wall` | Modal/interactive operator — can't be driven from a script |

## What actually works

From the Bonsai source (`<your_local_clone>/IfcOpenShell/src/bonsai/bonsai/bim/module/model/wall.py`):

1. **`DumbWallGenerator(relating_type)`** — builds typed LAYER2 walls via
   `create_wall_from_2_points()` with correct length / rotation / axis
   representation and material layer thickness.
2. **`DumbWallJoiner().connect(wall_a, wall_b)`** for each consecutive
   pair — calls `ifcopenshell.api.geometry.connect_wall()` which creates
   `IfcRelConnectsPathElements` with ATSTART/ATEND, then
   `tool.Model.recreate_wall()` regenerates the body with miter
   (algorithm in `regenerate_wall_representation.py:525`).

## How to use

Inside Blender (Scripting workspace, or via `execute_blender_code` MCP):

```python
import bonsai_bim_helpers as bw

# 5 × 5 m room with WAL100 walls, 3 m high, FLR200 slab
pairs = bw.create_room_with_mitered_corners(
    corners=[(0, 0), (5, 0), (5, 5), (0, 5)],
    wall_type_name="WAL100",
    height=3.0,
    closed=True,
    name_prefix="Room",
)
walls = [obj for obj, _ in pairs]

slab_obj, slab_entity = bw.add_floor_slab_from_walls(
    wall_objs=walls,
    slab_type_name="FLR200",
    align_top_to_storey=True,    # slab top at Z=0, walls sit on top
)
```

### Why `align_top_to_storey=True` matters

By default `DumbSlabGenerator` extrudes the slab UPWARD from the storey
reference plane (Z=0), so the slab body occupies `Z=0 … +thickness` and
overlaps the bottom of the walls. With `align_top_to_storey=True`, the
slab placement is translated DOWN by its thickness via
`ifcopenshell.api.geometry.edit_object_placement`, so the slab top sits
at Z=0 and walls rest cleanly on top.

### Prerequisites in the IFC project

- An IFC project must exist (use `bootstrap_project()` from
  [`bonsai-project-setup`](../bonsai-project-setup/) for a one-shot
  setup).
- At least one `IfcWallType` with a material layer set so
  `tool.Model.get_material_layer_parameters(wall_type)["thickness"]`
  returns a value. `bootstrap_project()` ships `WAL200` (200 mm
  exterior) and `WAL100` (100 mm interior) by default.

## Wall types convention — exterior vs interior

`bootstrap_project(...)` creates **TWO** `IfcWallType` entries by default:

- **`WAL200`** — 200 mm thick. Exterior + structural use.
- **`WAL100`** — 100 mm thick. Interior partitions.

Both reference one shared `IfcMaterial` "Concrete" via separate
`IfcMaterialLayerSet` entries (different layer thicknesses per type).

| Helper | Default wall type |
|---|---|
| `create_room_with_mitered_corners(..., wall_type_name=None)` | First `IfcWallType` in the project = **WAL200** |
| `create_room_with_mitered_corners(..., wall_type_name="WAL100")` | Explicit interior |
| `add_interior_wall(..., wall_type_name="WAL100")` | Default **WAL100** (interior) |

Both helpers fall back gracefully to the FIRST `IfcWallType` in the
project if the named one is missing.

## Interior partitions MUST NOT overshoot into exterior walls

**Default rule** — when an interior partition (e.g. WAL100) terminates at
an exterior wall (e.g. WAL200), its AXIS endpoint MUST sit at the INNER
FACE of the exterior wall, NOT at the outer face or centreline.
Otherwise the partition body extends *into* the exterior wall — a
knife-through-wall design error that:

- Breaks IFC element separation
- Shows up as an extruded sliver in every section view
- Renders incorrectly in Solibri / BIMVision / IFC.js
- Confuses quantity takeoffs (the partition's volume includes the overshoot)

`add_interior_wall(...)` auto-clips endpoints by default
(`avoid_existing_walls=True`):

```python
# Pass raw outer-edge coords — helper clips silently to (0.2, 6) → (4.625, 6)
bw.add_interior_wall(
    start_xy=(0.0, 6.0),     # would be inside the 200 mm west wall
    end_xy=(4.625, 6.0),
    height=3.0,
    wall_type_name="WAL100",
    name="Int_NW_South",
)
```

The clip rule:

1. For each endpoint, find every existing `IfcWall` whose thickness is
   STRICTLY GREATER than the new partition's thickness.
2. If the endpoint sits inside (or on the boundary of) that wall's XY
   bounding box, push it along the partition direction (toward the OTHER
   endpoint) until just past the bbox boundary.
3. Same-thickness sibling partitions are SKIPPED (so L-corners between
   two partitions stay intact).

Override with `avoid_existing_walls=False` ONLY for genuine through-walls
or non-axis-aligned obstacle geometry.

## Interior L-corners get IfcRelConnectsPathElements — siblings only

**Companion rule** — when two interior partitions of the SAME thickness
meet at an L-corner, they get a proper `IfcRelConnectsPathElements` +
mitered geometry. Partitions meeting EXTERIOR walls (different thickness)
do NOT get this connection — they stay as clean butt joints from the
no-overshoot clip.

Why the asymmetry — Bonsai's `connect_wall` (at
`<your_local_clone>/IfcOpenShell/src/ifcopenshell-python/ifcopenshell/api/geometry/connect_wall.py`)
writes connection types by picking the NEAREST endpoint of each wall.
For two sibling partitions both ENDING at a corner this is correct
(ATEND/ATEND → miter). For a partition meeting an exterior wall in a
T-junction, the exterior wall does NOT end at the junction — but
`connect_wall` still picks its nearest endpoint and the subsequent
`recreate_wall` TRIMS the exterior wall to that endpoint.

Observed catastrophically on the 10×20 office: 20 m north wall trimmed
to 10.85 m fragment between two partition T-junctions; east + west
walls reduced from 10 m to 6.1 m.

Until we wire `connect_wall`'s `is_atpath=True` branch explicitly, the
safe rule is **same-thickness siblings only**:

`add_interior_wall(...)` does this automatically via `connect_to_touching=
True` (default). After the no-overshoot clip:

1. Compute the new partition's own thickness from its IfcWallType.
2. Read both axis endpoints in world coords.
3. Find every existing `IfcWall` whose XY bbox contains either endpoint
   (within 10 mm) **AND whose thickness matches the new partition's
   within 1 mm**.
4. Call `DumbWallJoiner().connect(new, sibling)` for each match.

Partition-to-exterior junctions are intentionally left disconnected —
the geometry is right (axis ends at exterior inner face), only the IFC
topology is missing. Downstream tools handle this gracefully via
spatial adjacency.

Set `connect_to_touching=False` to disable when you'll wire all
connections yourself.

## Gotchas

- The Bonsai socket addon defaults to port 9876 (or 9877 if taken).
- `BIMModelProperties.relating_type_id` is a restricted EnumProperty —
  don't write to it. Pass the type ID directly to `add_occurrence`, or
  use the generator's `relating_type` constructor arg.
- Blender object name and IFC entity name are SEPARATE — set both if
  you want them to match.
- The miter is geometrically correct for any angle ≠ 0° and ≠ 180°. For
  perpendicular walls (90°) the miter cut is exactly 45°.
- **Re-running on a populated scene leaves orphan walls** at the same
  XYZ positions, which COVER UP doors/windows so they look "stuck on"
  or "fragmented". Use `cleanup_orphan_walls(name_prefix_to_keep)`
  before adding fillings. The voids are still correct — they're just
  hidden by the duplicate uncut wall.

## Authoritative source references

| File | Lines | What |
|---|---|---|
| `bim/module/model/wall.py` | (whole) | `DumbWallGenerator`, `DumbWallJoiner` |
| `ifcopenshell/api/geometry/connect_wall.py` | 30-64 | ATSTART/ATEND/ATPATH assignment |
| `ifcopenshell/api/geometry/regenerate_wall_representation.py` | 525+ | Miter geometry computation |

Cloneable from [github.com/IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell).
