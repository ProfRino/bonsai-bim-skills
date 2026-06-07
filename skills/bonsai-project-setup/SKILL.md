---
name: bonsai-project-setup
description: |
  Set up a Bonsai IFC project from scratch (IfcProject + Site/Building/
  Storey + dual IfcWallType WAL200/WAL100 + IfcSlabType FLR200 + Frame/
  Glass/Panel IfcSurfaceStyle items linked to Blender materials), add
  additional IfcBuildingStorey entries, run mandatory multi-angle audit
  screenshots, author + validate IDS, round-trip via BCF, and apply
  Qto + OverallSize fillers before handover. Trigger on any task that
  reaches for "set up a project", "add a storey", "audit the model",
  "validate IDS", or "save BCF".
---

# bonsai-project-setup — project setup + audit + IDS / BCF

## When to use this

Trigger on:
- "set up a project", "new IFC project", "initialise IFC", "start a project"
- "add a storey", "add a floor", "second floor", "upper level"
- "audit the model", "screenshot", "visual check"
- "IDS", "validate", "validation report"
- "BCF", "issue tracker", "round-trip"
- "save IFC", "export IFC", "handover"

For walls / openings / roofs / stairs / spaces — see the per-element
skills.

## Core principle: ALWAYS IFC/BIM-correct

A project is more than geometry. Every IFC handover needs:

1. **Proper spatial hierarchy** — `IfcProject → IfcSite →
   IfcBuilding → IfcBuildingStorey`, each linked via `IfcRelAggregates`.
2. **Real types with materials** — `IfcWallType` + `IfcSlabType` with
   `IfcMaterialLayerSet` (NOT just a single material reference).
3. **Surface styles linked to Blender materials** —
   `BIMStyleProperties.ifc_definition_id` so the IFC style + Blender
   viewport color reference the same entity.
4. **Quantities + schema attributes filled** — `Qto_*BaseQuantities` +
   `OverallWidth` / `OverallHeight` on doors/windows. Bonsai does NOT
   auto-populate these for typed occurrences.
5. **IDS validation passed** — automated check that every element has
   the data downstream tools need (`Qto_WallBaseQuantities.Length`,
   material associations, geometry presence).
6. **Visual audit passed** — multi-angle screenshots show no
   geometric errors that IDS can't see (overlap, gaps, leftovers).

This skill ships the helpers for all 6.

## One-shot project setup

```python
import bonsai_bim_helpers as bw

bw.setup_project(
    project_name="10x20 office",
    site_name="Site",
    building_name="Building",
    storey_name="Ground Floor",
    storey_elevation=0.0,
    exterior_wall_type_name="WAL200",
    exterior_wall_thickness=0.2,
    interior_wall_type_name="WAL100",
    interior_wall_thickness=0.1,
    slab_type_name="FLR200",
    slab_thickness=0.2,
    material_name="Concrete",
    schema="IFC4",
)
```

What it creates:

- `IfcProject` + `IfcSite` + `IfcBuilding` + `IfcBuildingStorey` —
  linked via `IfcRelAggregates`.
- **Two `IfcWallType` entries**:
  - `WAL200` for exterior walls (200 mm, default for
    `create_room_with_mitered_corners`).
  - `WAL100` for interior partitions (100 mm, default for
    `add_interior_wall`).
  - Both share ONE `IfcMaterial` "Concrete" via separate
    `IfcMaterialLayerSet` entries (different layer thicknesses per type).
- **`IfcSlabType` `FLR200`** (200 mm).
- **Three `IfcSurfaceStyle` entries**: `Frame`, `Glass`, `Panel` — each
  with a linked Blender material whose `BIMStyleProperties.ifc_definition_id`
  points at the IFC style. This is what `apply_window_styles` /
  `apply_door_styles` from [`bonsai-openings`](../bonsai-openings/) use.

Backward compat: old `setup_project(wall_type_name="...",
wall_thickness=...)` kwargs are still accepted — they alias to the
EXTERIOR settings. The previous function name `bootstrap_project` is
still callable as an alias for `setup_project`.

## Add additional storeys

```python
storey_l2 = bw.add_storey(
    name="L2",
    elevation=3.0,     # world Z of the storey reference plane
    building=None,     # None → use the first IfcBuilding in the project
)
```

Aggregates the new storey into the building via `IfcRelAggregates`.
Use this for multi-floor projects (residential, commercial). The grid
is project-level so it's shared across storeys — don't author one per
floor.

## MANDATORY: multi-angle screenshot audit after every change

**Non-negotiable.** Every time you create / delete / move / resize an
IFC element, you MUST run `audit_with_screenshots()` and capture one
viewport image per angle BEFORE telling the user you're done. A single
perspective view is NOT enough — overlapping fills, missing windows on
the hidden faces, wall-roof gaps, and leftover / duplicate elements
only show up in elevations and top.

The recommended cycle: **FRONT → RIGHT → BACK → LEFT → TOP → PERSP_SE**
covers every wall face + plan + overall. For taller buildings add
`PERSP_NW`.

```python
from bonsai_bim_helpers import audit_with_screenshots

# In a single execute_blender_code call PER angle:
for view in audit_with_screenshots(angles=("FRONT","RIGHT","BACK","LEFT","TOP","PERSP_SE")):
    # The 3D View is now framed to `view`.  From the host side,
    # between each Blender call, fire the screenshot tool (e.g.
    # mcp__Blender__get_screenshot_of_window_as_image) and visually
    # check.
    pass
```

Use simple viewport screenshots (`get_screenshot_of_window_as_image`),
NOT rendered output. Rendered screenshots from inside an MCP loop
sometimes return solid black; the cheap viewport grab is more reliable
and faster.

### Audit checklist (per screenshot)

- [ ] No window inside a door's footprint (check exterior elevations)
- [ ] No door/window inside a wall corner (check both adjacent faces)
- [ ] Every wall has the openings the user requested (count per elevation)
- [ ] Wall-roof junction has no gap and no sliver above the roof
- [ ] No leftover/duplicate slabs (old flat roofs, etc.) — check TOP
- [ ] Stair top edge aligns with slab void (no gap, no overshoot)
- [ ] Grid bubbles don't overlap dimension chains

If a screenshot shows a problem, FIX IT before reporting the task done.
Re-screenshot the fix.

## Quantities + schema-attribute fillers

Bonsai does NOT auto-populate these for typed occurrences. Run before
any IDS validation / handover:

```python
bw.add_wall_quantities()             # Qto_WallBaseQuantities on every IfcWall
bw.fill_opening_overall_attrs()      # OverallWidth/Height on IfcDoor + IfcWindow
```

`add_wall_quantities()` computes (from the evaluated mesh):
`Length`, `Width`, `Height`, `GrossSideArea`, `NetSideArea` (subtracts
opening area sums), `GrossVolume`, `NetVolume`, footprint areas. The
`Net*` values walk every `IfcRelVoidsElement` on the wall, read the
filler's bbox, and subtract.

`fill_opening_overall_attrs()` reads from the BBIM pset if present,
else falls back to the geometry bbox.

## IDS — author + validate

IDS (Information Delivery Specification, buildingSMART XML) is the
authoritative format for "this IFC must contain X data". The skill
ships a baseline residential IDS author + a validator:

```python
ids = bw.author_room_ids(
    output_path=os.path.join(OUTPUT_DIR, "office.ids"),
    title="Office baseline",
    author="your-name",
    version="1.0",
    milestone="Schematic",
)
# `ids` is an ifctester.ids.Ids — you can append project-specific
# specs before saving.

results = bw.validate_against_ids(
    ifc_file_or_path=os.path.join(OUTPUT_DIR, "office.ifc"),
    ids_path=os.path.join(OUTPUT_DIR, "office.ids"),
    html_report_path=os.path.join(OUTPUT_DIR, "office_ids_report.html"),
)
# results = {"specs_pass": N, "specs_fail": M, "elements_checked": K}
```

Baseline IDS specs:

- Walls report `Qto_WallBaseQuantities.Length`
- Doors + windows declare `OverallWidth` + `OverallHeight`
- Exactly one `IfcRoof` in the project
- Walls + slabs have a material association

IDS catches DATA gaps that the screenshot audit can't see.

## BCF — round-trip via the issue file

BCF (BIM Collaboration Format) is the standard for "here are 22 things
I found wrong, with viewpoints" exchange. v0.2.0 has NO baked BCF-author
helper — the `.bcfzip` is produced inline via `ifctester.reporter.Bcf`,
exactly as the example scripts do:

```python
import ifctester, ifctester.ids, ifctester.reporter

ids = ifctester.ids.open(ids_path)
ids.validate(ifc)                              # the IFC entity, in-memory

bcf_rep = ifctester.reporter.Bcf(ids)
bcf_rep.report()
bcf_rep.to_file(os.path.join(OUTPUT_DIR, "office_issues.bcfzip"))
```

A clean build produces a `.bcfzip` with 0 topics. The file opens in
Bonsai's "BCF" sidebar panel — clicking each topic activates its
viewpoint (camera + element selection).

When activating BCF viewpoints in a Blender session, use the skill's
`activate_bcf_viewpoint_safely(viewpoint_guid)` wrapper instead of the
raw `bpy.ops.bim.activate_bcf_viewpoint`. The wrapper post-hides leaked
visualisation helpers (BCF viewpoints carry
`<Visibility DefaultVisibility="true"/>` which un-hides every helper
object the operator created — clutters the viewport).

⚠️ **TODO (roadmap)**: bake `bcf_from_ids_results(ids, output_path,
project_name)` as a one-call helper so the ad-hoc 5 lines above
collapse to one call. Not in v0.2.0.

## Two-layer audit principle

For a delivery-ready model you need BOTH:

1. **Visual audit** — multi-angle screenshots catch GEOMETRIC errors
   (overlap, gaps, wrong placement, leftover elements).
2. **IDS audit** — catches DATA errors (missing pset, missing material,
   missing schema attribute) the screenshots can't see.

Pass both before saying "done".

## Save IFC the RIGHT way

```python
# ✅ DO — sets tool.Ifc.get_path() so subsequent drawing operators work
bpy.ops.bim.save_project(filepath=ifc_path)

# ❌ DON'T — writes the file but does NOT update Bonsai's path state
tool.Ifc.get().write(ifc_path)
```

This matters because [`bonsai-drawings`](../bonsai-drawings/) needs
`tool.Ifc.get_path()` populated to write SVG files to
`<project_dir>/drawings/`. Plain `ifc.write()` writes the IFC but leaves
the path state empty → drawing operators hit `PermissionError` when
they try to `mkdir("drawings")` in the process CWD.

## Gotchas

- **`audit_with_screenshots` PERSP_SE doesn't reset from previous ortho
  view** — the helper now force-resets `rv3d.view_perspective='PERSP'`
  and clears stale rotation before applying the PERSP rotation.
- **`audit_with_screenshots` leaves orange selection outlines** if you
  forget to deselect — the helper now does `select_all(DESELECT)` after
  framing.
- **`bpy.ops.bim.create_project` reads scene props, not kwargs** —
  `setup_project` sets `BIMProjectProperties` on the scene before
  calling the operator.
- **Stair `top_slab_depth` MUST match the upper slab thickness** — see
  [`bonsai-stairs`](../bonsai-stairs/) for details.

## Authoritative source references

| File | Lines | What |
|---|---|---|
| `bim/module/project/operator.py` | (whole) | `bim.create_project` + `bim.save_project` |
| `ifcopenshell/util/element.py` | (whole) | `get_psets`, `get_predefined_type`, etc. |
| `ifctester/ids.py` | (whole) | IDS authoring + validation |
| `bcf/v2/...` | (whole) | BCF read / write |
