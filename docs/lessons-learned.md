# Lessons learned

A condensed list of the rules baked into these skills, in order they were
caught while building real test projects (room_4x6, two-room house with
stairs, 4-roof comparison, 10×20 m office). Each is either ENFORCED
automatically by a helper, or documented as a gotcha in SKILL.md +
inline in the helper that triggers it.

Numbered approximately in the order they were discovered. Item numbers
match the agent memory file used during development so cross-references
from skill source still resolve.

## Core principle (foundational)

**Always IFC/BIM-correct. Never Blender-only.** Every void, fill, material,
parametric pset, connection MUST be a real IFC entity / relationship.
Blender modifiers (Boolean, Solidify, Array) and direct mesh edits LOOK
right in the viewport but get LOST on IFC export and break interop with
every other IFC tool.

The reach-for cheat sheet:

| Need | IFC mechanism |
|---|---|
| Void in element | `feature.add_feature` → `IfcRelVoidsElement` + `IfcOpeningElement` |
| Fill in opening | `feature.add_filling` → `IfcRelFillsElement` |
| Wall clip / cut | `ifcopenshell.api.geometry.add_clipping` → `IfcBooleanClippingResult` |
| Material | `material.assign_material` → `IfcRelAssociatesMaterial` + constituent set |
| Parametric door / window / stair / railing / roof | `BBIM_*` pset + `bim.add_*` operator |
| Wall-wall connection | `IfcRelConnectsPathElements` via `DumbWallJoiner.connect` |
| Type assignment | `type.assign_type` → `IfcRelDefinesByType` |
| Drawing / annotation | `bim.add_drawing` / `bim.add_annotation` → real IfcAnnotation entities |

## Parametric build pattern is two-phase

`bim.add_*` (door / window / stair / roof) creates the entity with
addon-default props. To get your dimensions you must:

```
bim.add_X
→ bim.enable_editing_X
→ set props (overall_width, overall_height, door_type, etc.)
→ bim.finish_editing_X    # writes pset, regenerates mesh
```

Skipping the editing wrap leaves the entity at default size and silently
breaks "set width=1.5" expectations.

## set_world_location is non-negotiable for placement

`obj.location = target` updates Blender but does NOT sync the IFC
`IfcLocalPlacement`. On every IFC save + reload, the entity reverts to
world origin. Use `set_world_location(obj, location)` which also calls
`bonsai.core.geometry.edit_object_placement` to commit the placement.

This is the lesson that broke an entire smoke-test run silently (model
looked correct in Blender, saved IFC had every element at origin).

## Doors / windows: target is the LEFT EDGE, not the centre

`add_parametric_window_to_wall(target=(x, y, sill_z))` places the window
with its LOCAL +X-most corner at `target`. The window body extends in
the **wall's local +X direction** from there.

To centre a 1.8 m window on y=3.0 of an east/west wall, pass
`target=(x_face, 2.1, sill_z)` (= centre y − W/2). For walls built by
the skill helpers, `add_equally_spaced_windows_to_wall` handles this
automatically — use it whenever placing more than one window in a wall.

## Default rule: windows are equally spaced and centred

When placing more than one window in a wall, every end-gap and every
between-window gap MUST be identical:

```
gap = (L − N · W) / (N + 1)
```

Window centres at `(i+1) · gap + (i + 0.5) · W` for i = 0 … N−1.

Hand-computed centres like "1.5 m from each wall end + 3 m between
windows" produce LEFT-LEANING runs (small start-gap, big end-gap) that
look wrong in every elevation. `add_equally_spaced_windows_to_wall(...)`
enforces the formula. For a wall with a centred door, split into two
segment calls — each side gets its own equal-spacing pattern.

## Hard rule: interior partitions MUST NOT overshoot into exterior walls

A WAL100 partition ending at a WAL200 exterior wall has its AXIS at the
exterior INNER face, NOT at the exterior centreline or outer face.
Otherwise the partition body extends INTO the exterior wall — a
knife-through-wall design error that breaks element separation, renders
wrong in Solibri / BIMVision / IFC.js, and pollutes quantity takeoffs.

`add_interior_wall(..., avoid_existing_walls=True)` (default ON)
auto-clips endpoints to the inner face of any STRICTLY THICKER existing
IfcWall. The thicker-only filter preserves L-corners between
same-thickness sibling partitions.

Caller can pass raw outer-edge coords (e.g. `start_xy=(0, 6)` for a
partition meeting the west wall) and the helper silently clips to
`(0.2, 6)`.

## Partial rule: interior partitions get IfcRelConnectsPathElements — but ONLY siblings

`add_interior_wall(..., connect_to_touching=True)` (default ON)
auto-connects new partitions to existing IfcWalls of the SAME thickness
(within 1 mm) at touching endpoints, via `DumbWallJoiner.connect`. This
creates `IfcRelConnectsPathElements` + triggers `recreate_wall` on both
walls for proper miter regen at interior L-corners.

**Same-thickness only.** `ifcopenshell.api.geometry.connect_wall` picks
the NEAREST endpoint of each wall as the connection. For two
same-thickness partitions both ENDING at a corner this gives correct
ATEND/ATEND with miter. For a partition meeting an exterior wall in a
T-junction, the exterior wall does NOT end at the junction — but
connect_wall still picks its nearest endpoint and the subsequent
`recreate_wall` TRIMS the exterior wall to that endpoint.

Observed catastrophically on the 10×20 office: 20 m north wall trimmed
to 10.85 m fragment between two partition T-junctions; east + west
walls reduced from 10 m to 6.1 m. Until `connect_wall`'s
`is_atpath=True` branch is wired explicitly, the safe rule is
**same-thickness siblings only**. Partition-to-exterior junctions stay
as clean butt joints (geometry correct via the clip; only IFC topology
missing).

## Stair bbox lies about the last step

`stair.bbox.y_max` includes the top nib landing, which extends past the
actual last tread back edge. Sizing the stairwell opening to bbox
leaves an empty strip past the top tread. Use
`add_stairwell_opening_for_stair(stair_obj, slab_obj, ...)` which fits
to the actual last-tread back edge from the BBIM_Stair `treads` pset.

## Stair connects to slab via parametric `top_slab_depth`

Match `top_slab_depth` to the slab thickness, and set `has_top_nib=True`
so the stair's top step lands cleanly on the slab face. Otherwise the
top tread either floats below the slab or pokes above it.

## IfcSpace is AGGREGATED, not CONTAINED

`IfcSpace` is a spatial element. Use `IfcRelAggregates` to put it under
a storey — NOT `IfcRelContainedInSpatialStructure` (which is for
building elements like walls and doors). `add_space(...)` does the
right thing. Get it wrong and the space won't appear under the storey
in any tree view.

## bim.assign_class double-prefixes Blender object names

Calling `bim.assign_class(ifc_class="IfcSpace")` on a Blender obj
named "IfcSpace/Foo" produces "IfcSpace/IfcSpace/Foo" because Bonsai
appends its own prefix. `add_space(...)` builds the mesh with the bare
name ("Foo"), runs `assign_class`, then renames to clean
"IfcSpace/Foo" after.

## Qto_*BaseQuantities + OverallWidth/Height are NOT auto-populated

A wall has no `Qto_WallBaseQuantities` until you put one there. A door
has no `OverallWidth` schema attribute until you set it. Bonsai
fills these automatically only for BBIM parametric occurrences; typed
occurrences (DT01-style IfcDoorType users) need explicit fills.

`add_wall_quantities()` + `fill_opening_overall_attrs()` are
one-call helpers that walk every element and fill what's missing.
Run them before any IDS validation / handover.

## Two-layer audit: screenshots + IDS

Visual screenshots catch the things IDS can't see (overlap, geometry
gaps, double slabs). IDS catches the DATA gaps screenshots can't see
(missing OverallWidth, missing material). You need BOTH for a
delivery-ready model. `validate_against_ids(...)` runs the IDS file,
returns a counts dict + optional styled HTML report.

## Multi-angle screenshot audit is MANDATORY

The standard cycle: FRONT → RIGHT → BACK → LEFT → TOP → PERSP_SE. Add
PERSP_NW for taller buildings. Single perspective view misses:
overlapping fills, missing windows on hidden faces, wall-roof gaps,
leftover slabs. `audit_with_screenshots(angles=(...))` cycles the
3D viewport for the caller to screenshot externally.

## Project grid: extension MUST exceed dim-chain offset

Bonsai's `bim.add_grid` operator hardcodes a +/-2 m axis extension. With
overall dimension chains conventionally placed at +/-2 m, bubbles
overlap dim text — an annotation collision = ERROR.

**Post-hoc axis edits are silently ignored by the SVG renderer** (h5
cache + axis snapshot at creation). The reliable fix is to DELETE the
grid and rebuild it with the extension baked in.

`add_project_grid(extension=4.0)` bypasses `bim.add_grid` entirely:
authors `IfcGrid` via `bonsai.core.root.assign_class`, then each axis
via `ifcopenshell.api.grid.create_grid_axis` +
`ifcopenshell.api.grid.create_axis_curve` with the desired extension.

## Drawings: save the IFC via the OPERATOR first

`bpy.ops.bim.save_project(filepath=...)` updates Bonsai's
`tool.Ifc.get_path()`. `tool.Ifc.get().write(path)` does NOT.

Bonsai's `bim.add_drawing` calls `tool.Drawing.setup_shading_styles_path
("drawings/...")` which calls `tool.Ifc.resolve_uri(...)`. With no path
set, `resolve_uri` returns the relative `drawings/...` unchanged, and
`os.makedirs("drawings")` runs from the process CWD (= Blender install
dir on Windows) → `PermissionError`. The "Bonsai experienced an error
:(" popup is this.

`add_drawing(...)` in the bonsai-drawings skill now defensively checks
this with `_require_saved_ifc_path()` and raises a clear RuntimeError
naming the fix.

## Delete + rebuild requires orphan purge

`ifcopenshell.api.run("root.remove_product", ...)` removes an IFC entity
cleanly. But the corresponding Blender obj keeps its
`BIMObjectProperties.ifc_definition_id` pointing at the deleted id. The
next `bpy.ops.bim.save_project` then crashes with
`RuntimeError: Instance #N not found` during placement sync.

After any IFC entity removal, walk all Blender objects:

```python
for obj in list(bpy.data.objects):
    props = tool.Blender.get_object_bim_props(obj)
    if not props.ifc_definition_id: continue
    try: ifc.by_id(props.ifc_definition_id)
    except RuntimeError: bpy.data.objects.remove(obj, do_unlink=True)
```

## See also

The agent memory file used during development has the full ~50 lessons
with extended context. Cross-references in skill source (e.g.
"lesson 46") refer to that file. Each rule above maps to one or more
entries there.
