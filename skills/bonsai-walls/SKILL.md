---
name: bonsai-walls
description: |
  Create rooms / polyline walls (with PROPER MITERED CORNERS) and fitted floor
  slabs in Blender + Bonsai. Matches what bpy.ops.bim.draw_polyline_wall and
  bpy.ops.bim.draw_slab_from_wall produce interactively. Use whenever the user
  wants to programmatically build an IFC room and asks for clean wall-to-wall
  connections (not the overlapping joins that ifc-bonsai-mcp's
  create_polyline_walls produces) and/or a floor that fits without overlapping
  the wall bottoms.
---

# Bonsai walls — programmatic polyline with mitered corners

## MANDATORY: Audit with multi-angle screenshots after every change

**This is non-negotiable.** Every time you create, delete, move, or resize
an IFC element, you MUST run `audit_with_screenshots()` and capture one
viewport image per angle BEFORE telling the user you're done. A single
perspective view is NOT enough — overlapping fills, missing windows on the
hidden faces, wall-roof gaps, and leftover/duplicate elements only show up
in elevations and top.

The recommended cycle is **FRONT, RIGHT, BACK, LEFT, TOP, PERSP_SE** — that
covers every wall face plus a plan plus an overall. For taller buildings
add `PERSP_NW` (other side overview).

```python
from bonsai_room_with_miters import audit_with_screenshots
# In a single execute_blender_code call PER angle:
for view in audit_with_screenshots(angles=("FRONT","RIGHT","BACK","LEFT","TOP","PERSP_SE")):
    # The 3D View is now framed to `view`. From the host side, between
    # each Blender call, fire the screenshot tool (e.g.
    # mcp__Blender__get_screenshot_of_window_as_image) and visually check.
    pass
```

Use **simple viewport screenshots** (`get_screenshot_of_window_as_image`),
NOT rendered output. Rendered screenshots from inside an MCP loop sometimes
return solid black; the cheap viewport grab is more reliable and faster.

Audit checklist for every screenshot:
- [ ] No window inside a door's footprint (check exterior elevations)
- [ ] No door/window inside a wall corner (check both adjacent faces)
- [ ] Every wall has the openings the user requested (count per elevation)
- [ ] Wall-roof junction has no gap and no sliver above the roof
- [ ] No leftover/duplicate slabs (old flat roofs, etc.) — check TOP
- [ ] Stair top edge aligns with slab void (no gap, no overshoot)

If a screenshot shows a problem, FIX IT before reporting the task done.
Re-screenshot the fix. The user has explicitly stated frustration when the
LLM shortcuts this step.

## Core principle: ALWAYS IFC/BIM-correct

**Rule:** every element, every relationship, every void or fill MUST be
expressed via proper IFC entities and relationships. Blender-only mechanisms
(modifiers, mesh edits) are not acceptable substitutes — they look right in
the viewport but get LOST on IFC export, and break interoperability with
every other IFC tool (BIMVision, Solibri, IFC.js, Revit, ArchiCAD).

For every operation, ask: "Will this survive a `bim.save_project` → close
project → re-open?" If no, find the IFC mechanism. The common ones:

| Intent | ✅ IFC-correct mechanism | ❌ Don't |
|---|---|---|
| Cut a void in a wall/slab | `feature.add_feature(opening, element)` → `IfcRelVoidsElement` | Blender Boolean modifier |
| Fill an opening with door/window | `feature.add_filling(opening, filling)` → `IfcRelFillsElement` | Position the door near the wall |
| Wall slope/clip top | IFC `clippings` arg on `add_wall_representation`, OR `IfcBooleanClippingResult` with `IfcHalfSpaceSolid` | Blender Boolean cap |
| Material on element | `material.assign_material` → `IfcRelAssociatesMaterial` + constituent set | Blender material slot only |
| Parametric door/window/stair/railing | `BBIM_*` pset + `bim.add_door` / `bim.add_window` / `bim.add_stair` / `bim.add_railing` | Mesh edit / mesh-scale |
| Element-to-element connection | `IfcRelConnectsPathElements`, `IfcRelConnectsElements` | Visual alignment only |
| Type assignment | `type.assign_type` → `IfcRelDefinesByType` | Just copy mesh dims |
| Type duplication | `bim.duplicate_type` + dedupe shared CoordList | Hand-copy attributes |

When in doubt, search the IfcOpenShell clone at
`<your_local_clone>/IfcOpenShell/src/bonsai/bonsai/bim/module/`
for the operator that produces the IFC entity you want.

## When to use this

Trigger when the user wants to:
- Build a room from a wall polyline (closed or open)
- Create walls programmatically with **clean mitered corners** at every junction
- Match the result of Bonsai's interactive Draw Polyline Wall tool
- Avoid the overlapping/intersecting corners produced by the ifc-bonsai-mcp's
  default `create_polyline_walls` MCP tool (which doesn't establish
  `IfcRelConnectsPathElements` between walls)

## Why the obvious approaches fail

| Approach | Problem |
|---|---|
| ifc-bonsai-mcp `create_polyline_walls` | Creates independent walls; no IFC connections; corners overlap |
| `bpy.ops.bim.extend_walls_to_wall` | Requires LAYER2-compatible walls; produces butt-joints (one wall ends at the other's face), not the wall-axis miter |
| `bpy.ops.bim.add_occurrence` per segment | Creates 1m-default walls; doesn't set proper axis representation length |
| `bpy.ops.bim.draw_polyline_wall` | Modal/interactive operator — can't be driven from a script |

## What actually works

The Bonsai source path (in `IfcOpenShell/src/bonsai/bonsai/bim/module/model/wall.py`):

1. **`DumbWallGenerator(relating_type)`** — builds typed LAYER2 walls via
   `create_wall_from_2_points()` with correct length/rotation/axis.
2. **`DumbWallJoiner().connect(wall2_obj, wall1_obj)`** for each consecutive
   pair — calls `ifcopenshell.api.geometry.connect_wall()` which creates
   `IfcRelConnectsPathElements` with ATSTART/ATEND, then
   `tool.Model.recreate_wall()` regenerates the body using the miter
   algorithm in `ifcopenshell/api/geometry/regenerate_wall_representation.py`
   (line 525 — "This creates 'mitering' behaviour").

## How to use

Inside Blender (Scripting workspace, or via execute_blender_code MCP), use the
reference script at:

`skills/bonsai-walls/bonsai_room_with_miters.py` (relative to the repo root)

```python
# Example: 5x5m room with WAL100 walls, 3m high, FLR200 floor
from bonsai_room_with_miters import (
    create_room_with_mitered_corners,
    add_floor_slab_from_walls,
)

# 1. Walls with mitered corners
pairs = create_room_with_mitered_corners(
    corners=[(0, 0), (5, 0), (5, 5), (0, 5)],
    wall_type_name="WAL100",   # or None to auto-pick first IfcWallType
    height=3.0,
    closed=True,
    name_prefix="MiterRoom",
)

# 2. Floor slab fitted to wall polygon, top flush with Z=0
wall_objs = [obj for obj, _ in pairs]
slab_obj, slab_entity = add_floor_slab_from_walls(
    wall_objs=wall_objs,
    slab_type_name="FLR200",   # or None to auto-pick first IfcSlabType
    align_top_to_storey=True,  # slab top at Z=0, walls sit on top (no overlap)
)
```

### Why `align_top_to_storey=True` matters

By default Bonsai's `DumbSlabGenerator` extrudes the slab UPWARD from the storey
reference plane (Z=0). That puts the slab BETWEEN Z=0 and Z=+thickness, which
overlaps the bottom of the walls (walls start at Z=0). Setting
`align_top_to_storey=True` translates the slab placement down by its thickness
via `ifcopenshell.api.geometry.edit_object_placement`, so the slab top sits at
Z=0 and walls rest cleanly on top.

### Prerequisites in the IFC project
- An IFC project must be loaded (`bpy.ops.bim.create_project()` or open file)
- At least one `IfcWallType` must exist with a material layer set (so
  `tool.Model.get_material_layer_parameters(wall_type)["thickness"]` returns
  a value). The Bonsai default project ships with WAL50/WAL100/WAL200/WAL300.

### After creation
Save with `bpy.ops.bim.save_project(filepath="...")`. The miter geometry is
baked into each wall's body representation via clipping booleans.

## Authoritative source references

| File | Lines | What it does |
|---|---|---|
| `bim/module/model/wall.py` | 887-912 | Polyline finalisation loop (call template) |
| `bim/module/model/wall.py` | 1092-1184 | `DumbWallGenerator` + `create_wall_from_2_points` |
| `bim/module/model/wall.py` | 1648-1657 | `DumbWallJoiner.connect()` |
| `ifcopenshell/api/geometry/connect_wall.py` | 30-64 | Axis intersection → ATSTART/ATEND |
| `ifcopenshell/api/geometry/regenerate_wall_representation.py` | 370-545 | Miter cut algorithm |
| `bim/module/model/slab.py` | 47-128 | `DumbSlabGenerator` (CURSOR/POLYLINE/WALLS modes) |
| `bim/module/model/slab.py` | 817-846 | `AddSlabFromWall` operator (`bim.draw_slab_from_wall`) |
| `tool/model.py` | (search) `get_polygons_from_wall_axis` | Builds slab outline from wall axes |

Cloneable from [github.com/IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell).

## Wall types (exterior vs interior — automatic)

`bootstrap_project()` creates **two** wall types by default:

| Name | Thickness | Use for |
|---|---|---|
| `WAL200` | 200 mm | EXTERIOR walls (perimeter, party walls, load-bearing) |
| `WAL100` | 100 mm | INTERIOR partitions (room dividers, non-load-bearing) |

Both use the same `IfcMaterial` ("Concrete") + `IfcMaterialLayerSet` —
they differ only in layer thickness. The convention follows typical
residential construction: 200 mm cavity/insulated exteriors,
100 mm stud partitions.

**Helpers auto-pick the right type:**

- `create_room_with_mitered_corners(corners, wall_type_name=None, ...)` —
  defaults to the FIRST `IfcWallType` in the project. Since
  `bootstrap_project` creates WAL200 first, exterior perimeters get the
  200 mm type by default. Pass `wall_type_name="WAL200"` explicitly if
  you want to be sure, or `"WAL100"` to override.
- `add_interior_wall(start_xy, end_xy, height, base_z, wall_type_name="WAL100", ...)` —
  defaults to WAL100. The function falls back gracefully to the first
  IfcWallType if WAL100 is missing (for projects bootstrapped before this
  change).

**Backwards-compat for the old single-type bootstrap signature:**
If you pass `wall_type_name="..."` + `wall_thickness=...` (the pre-Jun-2026
kwargs), the helper treats them as the EXTERIOR override:

```python
# Old code (still works):
bootstrap_project(wall_type_name="WAL150", wall_thickness=0.15)
# → exterior = WAL150 @ 150 mm; interior still defaults to WAL100 @ 100 mm

# New explicit form (preferred):
bootstrap_project(
    exterior_wall_type_name="WAL200", exterior_wall_thickness=0.2,
    interior_wall_type_name="WAL100", interior_wall_thickness=0.1,
)
```

## Roof helpers (4 shapes — pick by your building type)

Four roof helpers ship with the skill, each backed by the BIM-correct IFC
mechanism for that roof shape. Match the helper to the building, then call
the matching `fit_walls_to_*` helper to clip the L-top walls to the roof
underside.

| Roof shape | Builder | Wall-fit helper | IFC representation |
|---|---|---|---|
| Mono-pitch (shed) | `add_mono_pitch_roof()` | `fit_walls_to_mono_pitch_roof_ifc()` | Tessellated `IfcRoof` (BIM-correctness debt) |
| Hip | `add_hip_roof()` | `fit_walls_to_hip_roof()` | Parametric `IfcRoof` + `BBIM_Roof` pset |
| Gable | `add_gable_roof(..., gable_edge_indices=(1,3))` | `fit_walls_to_gable_roof(..., gable_sides=("south","north"))` | Parametric `IfcRoof` + `BBIM_Roof` + `set_gable_roof_edge_angle` |
| Flat | `add_flat_roof()` | (no fit needed) | Solidified slab + `assign_class(IfcRoof, FLAT_ROOF)` |

### Roof-specific gotchas (learned the hard way)

- **`bim.add_roof` requires `enable_editing_roof → set props → finish_editing_roof`.**
  Without the enable wrapper, `props.angle` / `props.roof_thickness` are
  written to the BBIM_Roof pset but the mesh isn't regenerated — the roof
  ships with addon defaults (10°, 0.1 m). Same pattern as
  `bim.add_door` / `bim.add_window` / `bim.add_stair`.
- **Gable edge index convention is counterintuitive.**
  `add_gable_roof(gable_edge_indices=(1, 3))` on a CCW square footprint
  (SW → SE → NE → NW) produces a roof whose RIDGE runs along the Y axis at
  x=center. The roof's GABLE END TRIANGLES face SOUTH + NORTH, NOT east +
  west like you'd expect from the edge indices. When fitting walls, pass
  `gable_sides=("south", "north")` to match. Verify the actual ridge
  direction by inspecting roof vertex bbox before assigning gable_sides.
- **`add_roof` builds slab with TOP face at the input `wall_top_z`**, not
  the centerline. The bottom face is `vertical_thickness = roof_thickness
  / cos(angle)` below — typically ~18 cm for 0.15 m at 35°. Wall-fit cut
  planes must reference the BOTTOM face (cut_eave_z = eave_z − vertical_
  thickness), otherwise walls poke through the slab's lower face. The
  fit helpers accept `roof_thickness` and apply this offset automatically.
- **Gable end walls need TWO clip planes in ONE `add_boolean` call.**
  Each gable end wall is bounded by two roof faces meeting at the ridge.
  Sequential `clip_solid` calls produce nested `IfcBooleanClippingResult`
  trees that the geometry engine sometimes interprets wrongly, leaving
  the wall as a tall rectangle. Use `ifcopenshell.api.geometry.add_boolean(
  first_item=base, second_items=[hs1, hs2], operator="DIFFERENCE")` with
  both `IfcHalfSpaceSolid` second-items in a single call. The skill's
  `_clip_wall_with_planes()` does this.
- **Plane location far from origin breaks the engine.** When transforming
  a world-space plane to wall-local frame via `R.T @ (world_pt − origin)`,
  the reference point can land tens of metres away in local coords (e.g.
  local_y = +16 for east wall, −12 for west wall). The east-vs-west
  asymmetry causes clips to silently fail on one side. Project the
  reference point to the closest plane point to the wall's origin via
  `pt = (n · pt) / ||n||² · n`. The helpers do this internally.
- **The mono-pitch helper still uses tessellated mesh** (Bonsai's
  parametric `add_roof` only supports HIP/GABLE). It's BIM-correctness
  debt; the roof IS an `IfcRoof` entity with proper IFC class, but its
  representation is `IfcFacetedBrep` rather than `BBIM_Roof`-driven.
  Acceptable for visual deliverables; flag in your IDS if downstream
  consumers require BBIM parametric roofs.

## Project grid (`IfcGrid`)

Every architectural project needs a grid for documentation, drawings, and
column / dimensioning references. Use the skill's `add_project_grid(...)`
helper — a thin wrapper around Bonsai's `bim.add_grid` operator
(`bonsai/bim/module/model/grid.py:32-79`).

Bonsai's axis convention:

- **U axes** run horizontally (parallel to world X), labelled LETTERS
  (A, B, C, ...). They sit at `y = i * u_spacing`.
- **V axes** run vertically (parallel to world Y), labelled zero-padded
  NUMBERS ("01", "02", ...). They sit at `x = i * v_spacing`.

The grid lines automatically extend 2 m past the outermost axes — standard
drafting practice so bubbles read clearly on the drawing margin.

```python
# Standard 5 m grid for a 20 m × 10 m office:
bw.add_project_grid(
    u_spacing=5.0, total_u=3,    # A, B, C at y = 0, 5, 10
    v_spacing=5.0, total_v=5,    # 01..05 at x = 0, 5, 10, 15, 20
)
```

Defaults:
- `u_spacing=5.0`, `total_u=3` (A/B/C)
- `v_spacing=5.0`, `total_v=5` (01..05)
- `name=None` (leaves Bonsai's default Blender obj name "Grid")

Gotchas:
- Grid axes are linked to `IfcGrid.UAxes` / `IfcGrid.VAxes`, NOT contained
  in the storey. They're project-level annotations.
- The grid sits at z=0 (storey reference plane). For multi-storey buildings
  the grid is shared across all storeys (you don't need one per floor).
- Axis labels can't be customised through the operator UI — they're
  auto-generated as A,B,C... / 01,02,03... Override via
  `ifcopenshell.api.grid.create_grid_axis(axis_tag="...")` for custom tags.

## Interior partitions MUST NOT overshoot into exterior walls

**Default rule** — when an interior partition wall (e.g. WAL100) terminates
at an exterior wall (e.g. WAL200), its AXIS endpoint MUST sit at the INNER
FACE of the exterior wall, not at the exterior wall's outer face or
centreline. Otherwise the partition body extends *into* the exterior wall
body — a knife-through-wall design error that:

- Breaks the IFC concept of separate building elements
- Shows up as an extruded sliver in section views and elevations
- Renders incorrectly in every IFC viewer (Solibri, BIMVision, IFC.js)
- Confuses quantity takeoffs (the partition's volume includes the overshoot)

`add_interior_wall(...)` now **auto-clips endpoints by default** (the
`avoid_existing_walls=True` argument). When you call:

```python
# Partition spans the full inner room — pass interior coords directly,
# OR pass exterior corner coords and let the auto-clip do the work:
bw.add_interior_wall(start_xy=(0,   6), end_xy=(4.625, 6),   # raw coords
                     height=3.0, wall_type_name="WAL100",
                     name="Int_NW_South")
# Result: axis clipped to (0.2, 6) → (4.625, 6). The 0.2 m overshoot
# into the 200 mm west exterior wall is removed automatically.
```

How the auto-clip works (`_adjust_interior_wall_endpoints`):

1. For each endpoint, find every existing `IfcWall` whose thickness is
   STRICTLY GREATER than the new partition's thickness.
2. If the endpoint sits inside (or on the boundary of) any such wall's XY
   bounding box, push it along the partition direction (toward the OTHER
   endpoint) until just past the boundary.
3. The "thicker walls only" filter preserves L-corners and T-junctions
   between same-thickness sibling partitions — those legitimately meet at
   a shared XY corner and should NOT be clipped.

Override with `avoid_existing_walls=False` ONLY for genuine through-walls
or when the obstacle walls are non-axis-aligned (the algorithm uses
axis-aligned bboxes; rotated obstacles need manual clipping).

## Interior L-corners get IfcRelConnectsPathElements — but ONLY siblings

**Companion rule** — when two interior partitions of the SAME thickness
meet at an L-corner, they get a proper `IfcRelConnectsPathElements` +
mitered geometry. Partitions meeting EXTERIOR walls (different thickness)
do NOT get this connection — they stay as clean butt joints from the
no-overshoot clip.

Why the asymmetry — Bonsai's `ifcopenshell.api.geometry.connect_wall`
(at `src/ifcopenshell-python/ifcopenshell/api/geometry/connect_wall.py`)
writes connection types by picking the NEAREST endpoint of each wall.
For two sibling partitions both ENDING at a corner this is correct
(ATEND/ATEND → miter). For a partition meeting an exterior wall in a
T-junction, the exterior wall does NOT end at the junction — but
connect_wall still picks its nearest endpoint (ATSTART or ATEND) and the
subsequent `recreate_wall` TRIMS the exterior wall to that endpoint.
Result observed on the office build: 20 m north wall trimmed to the
10.85 m fragment between the two partitions; east and west walls
trimmed from 10 m to 6.1 m. Until we wire the `is_atpath=True` branch
explicitly (requires detecting which wall is the "through" wall and
passing it in the right order), the safe rule is **same-thickness
siblings only**.

`add_interior_wall(...)` does this automatically via
`connect_to_touching=True` (default). After the no-overshoot clip places
the partition:

1. Compute the partition's own thickness from its IfcWallType layer set.
2. Read both axis endpoints in world coordinates.
3. Find every existing `IfcWall` whose XY bounding box contains either
   endpoint (within 10 mm) **AND whose thickness matches the new wall's
   within 1 mm**.
4. Call `DumbWallJoiner().connect(new, sibling)` for each match — produces
   `IfcRelConnectsPathElements` (ATEND/ATEND, ATSTART/ATEND, etc.) and
   `tool.Model.recreate_wall(...)` on both, generating the miter cap.

Partition-to-exterior junctions are intentionally left disconnected —
the geometry is right (axis ends at exterior inner face), only the IFC
topology is missing. Downstream tools handle this gracefully via spatial
adjacency.

Set `connect_to_touching=False` to disable when you'll wire all
connections yourself.

## Window placement: equally spaced and centred BY DEFAULT

**Default rule** — when placing more than one window in a wall, use
**equally-spaced, centred** placement unless the design requires otherwise.
Every end-gap, between-window gap, and trailing end-gap is identical:

```
gap = (L − N · W) / (N + 1)
```

This automatically centres the run on the wall. With N=1 the single window
sits exactly at L/2. Asymmetric layouts (clusters, off-centre runs) are
exception cases — call them out explicitly when the brief says so.

Use the one-call helper — it computes the centres and forwards each placement
to `add_parametric_window_to_wall()`:

```python
from bonsai_room_with_miters import add_equally_spaced_windows_to_wall

# 5 equally-spaced 1.5×1.4 m windows on a clean 20 m wall, sill 0.9 m
add_equally_spaced_windows_to_wall(
    north_wall, count=5,
    width=1.5, height=1.4, sill_height=0.9,
    name_prefix="N_W",
)

# Wall with a centred door: split into two segments and space each side
# (door occupies x = 9.4 … 10.6 in local-X)
add_equally_spaced_windows_to_wall(
    south_wall, count=2, segment=(0.0, 9.4),
    width=1.5, height=1.4, sill_height=0.9, name_prefix="S_left",
)
add_equally_spaced_windows_to_wall(
    south_wall, count=2, segment=(10.6, 20.0),
    width=1.5, height=1.4, sill_height=0.9, name_prefix="S_right",
)
```

Gotchas:

- The helper assumes the wall's **local +X is along its length** and **local
  +Y points into the room** — true for every wall built by
  `create_room_with_mitered_corners()` / `add_interior_wall()`. Hand-built
  walls with a different local frame won't get the right targets.
- `segment` is in **metres along the wall's local X axis** (0 at the wall's
  start vertex). Don't pass world-space X — pass distance along the wall.
- For a wall with a door, ALWAYS split into segments around the door. Don't
  rely on `skip_indices` unless the pitch genuinely lines up with the
  obstacle (rare).
- If the request really IS asymmetric (e.g. one large picture window flanked
  by two narrow ones), call `add_parametric_window_to_wall()` directly with
  explicit targets — `add_equally_spaced_windows_to_wall()` is only for the
  default uniform case.

## Gotchas

- The Bonsai socket addon defaults to port 9877 (patched from 9876) to avoid
  conflict with standard BlenderMCP.
- `BIMModelProperties.relating_type_id` is a restricted EnumProperty — don't
  write to it. Pass the type ID directly to `add_occurrence`, or use the
  generator's `relating_type` constructor arg.
- Wall name on the Blender object and the IFC entity are separate — set both
  if you want them to match.
- The miter is geometrically correct for any angle ≠ 0° and ≠ 180°. For
  perpendicular walls (90°) the miter cut is exactly 45°.
- **Doors/windows: `bpy.ops.bim.add_occurrence` ignores the cursor's Z** and
  places the filling at the storey reference Z=0. You MUST set
  `filling_obj.location.z = sill_height` and call `view_layer.update()` BEFORE
  `FilledOpeningGenerator.generate(target=...)`. When target is passed,
  the generator copies Z from `filling_obj.matrix_world.translation.z` and
  IGNORES `props.rl1`/`props.rl2`. (See `opening.py:282-288`.)
- **Stair vs. floor void: bbox y_max ≠ last tread back edge**. The stair's
  bounding box extends past where the last tread top is, because
  `top_slab_depth` adds a "top nib" landing that integrates into the slab
  above. Sizing the stairwell opening to the bbox leaves an empty strip
  beyond the last step. Find the actual back edge by inspecting vertices at
  the stair's top_z plane:
    `top_z = max(v.z for v in verts)`
    `last_step_y = max(v.y for v in verts if abs(v.z-top_z) < 0.01)`
  Use the skill's `add_stairwell_opening_for_stair()` which does this
  automatically and produces a proper `IfcRelVoidsElement`.
- **Stair-slab connection is parametric**. Match `top_slab_depth` to the
  upper slab thickness and keep `has_top_nib=True` so the top of the stair
  integrates with the slab edge instead of butting against it. Same for
  `base_slab_depth` and the lower slab. Use `add_parametric_stair(...)`.
- **`bim.add_stair` / `bim.add_door` use addon-preference defaults**, NOT the
  props you set BEFORE calling. The right pattern is:
    1. `bim.add_stair`            # creates with defaults
    2. `bim.enable_editing_stair` # opens parametric edit mode
    3. set props on the object's prop group
    4. `bim.finish_editing_stair` # regenerates with your values
  Same for door — without `finish_editing_door`, the visual is a "ghost"
  wireframe schematic instead of the solid panel.
- **The `door_type` property in BIMDoorProperties is the OPERATION enum**
  (not `operation_type` as in the IFC schema attribute). 8 valid values:
  `SINGLE_SWING_LEFT/RIGHT`, `DOUBLE_SWING_LEFT/RIGHT`,
  `DOUBLE_DOOR_SINGLE_SWING`, `SLIDING_TO_LEFT/RIGHT`, `DOUBLE_DOOR_SLIDING`.
- **Duplicating a door/window type via `bim.duplicate_type` + scaling**:
  multiple `IfcPolygonalFaceSet` items in the type's body OFTEN share ONE
  `IfcCartesianPointList3D`. Iterating items and scaling each one's coords
  DOUBLE-scales the shared list. Dedupe by `coords.id()` before scaling.
  Better: use `create_parametric_door_type(...)` for a real BBIM_Door type.
- **Mesh-scale != parametric**. `bim.duplicate_type` produces a stretched
  tessellated mesh — proportions distort (frame thickness, hardware position).
  For correct proportions at any size use the parametric flow
  (`bim.add_door` + `BBIM_Door` pset, via `create_parametric_door_type`).
- **DT01/02/03 demo-template doors carry Blender-only materials**
  (`Frame`, `Panel`), NOT IFC material assignments. When you duplicate or
  create a new door, the Blender mesh has no material slots and renders as
  outline-only in Solid shading. Attach the Blender materials directly:
  `obj.data.materials.append(bpy.data.materials["Panel"])` then assign
  faces to slot 0. ⚠️ This is NOT BIM-correct — for true cross-tool
  material display, use `material.assign_material` with a constituent set.
- **Door / window placement origin is at one CORNER, not the centre**
  (specifically the local +X edge of the filling). So calling
  `add_door_to_wall(position=(0, 3, 0))` on a wall that spans Y=0..6 puts the
  door's EDGE at y=3 — the door body extends in -Y to y≈2 → it sits in the
  left half. **To centre on the wall midline, shift the target by
  +half_door_width along the wall's axis direction.** For DT01 (≈1.01m wide):
  target_y = wall_mid_y + 0.505. The world-bbox direction depends on wall
  rotation — verify with `bound_box` after placement and adjust the sign.
- **Roofs: Bonsai's parametric `bpy.ops.bim.add_roof` only supports HIP/GABLE
  topology**. For a true mono-pitch (shed) roof — single slope, two gable
  triangles — building it as a tilted mesh + `solidify` modifier + then
  `bim.assign_class(ifc_class="IfcRoof")` is cleaner than trying to coerce
  the parametric generator with edge-angle hacks. Use
  `add_mono_pitch_roof(...)` in this skill.
  ⚠️ **BIM-correctness debt**: the result is a TESSELLATED IfcRoof, not
  parametric. No BBIM_Roof pset, no editable slope. Acceptable when the
  parametric generator doesn't support the topology, but consumers of the
  IFC file lose the ability to re-pitch the roof via parameters. If the
  user wants a fully parametric mono-pitch, the right path is to extend
  Bonsai's roof module or use IfcExtrudedAreaSolid with a trapezoidal
  profile placed at the slope angle.
- **Wall-to-roof fit: `fit_walls_to_mono_pitch_roof()` uses a Blender
  Boolean modifier to clip the gable walls.** ⚠️ **NOT BIM-correct.**
  The modifier survives the session but is LOST on IFC export — the saved
  IFC has uniformly tall walls, not the slanted gable tops. The proper IFC
  fix is to add `clippings` (a list of `IfcHalfSpaceSolid`) to the wall's
  representation via `ifcopenshell.api.geometry.add_clipping`, producing an
  `IfcBooleanClippingResult` in the wall body. TODO before relying on this
  skill for delivered IFC files.
- **Re-running on a populated scene leaves orphan walls** at the same XYZ
  positions, which COVER UP doors/windows so they look "stuck on" or
  "fragmented". Use `cleanup_orphan_walls(name_prefix_to_keep)` before adding
  fillings. The voids are still correct — they just can't be seen through the
  duplicate uncut wall.
