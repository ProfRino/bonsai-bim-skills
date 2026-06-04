---
name: bonsai-spaces-grid
description: |
  Add IfcSpace entities (aggregated into a storey, with IfcRelSpaceBoundary
  to bounding walls / slab / roof + Qto_SpaceBaseQuantities) and IfcGrid
  systems with proper bubble-extension control (axes extend past the
  building far enough that the dimension chains don't overlap the
  bubbles). Trigger when the user wants to add rooms (as IfcSpace),
  define space boundaries, or add a column / dimension grid.
---

# bonsai-spaces-grid — IfcSpace + IfcGrid

## When to use this

Trigger on:
- "add a space", "add an IfcSpace", "define a room"
- "space boundary", "IfcRelSpaceBoundary"
- "add a grid", "project grid", "column grid", "dimensioning grid"

For walls + the rooms' physical boundaries: see [`bonsai-walls`](../bonsai-walls/).
For the IDS / quantity-takeoff pipeline that the spaces feed into:
see [`bonsai-project-setup`](../bonsai-project-setup/).

## Core principle: ALWAYS IFC/BIM-correct

Spatial elements live OUTSIDE the building-element hierarchy. They are
NOT contained in a storey via `IfcRelContainedInSpatialStructure` (that
relation is for walls / doors / slabs). They are AGGREGATED via
`IfcRelAggregates`. Get this wrong and the space won't appear under
the storey in any tree view (Bonsai outliner, Solibri navigator,
BIMVision tree, etc.).

| Intent | ✅ IFC mechanism | ❌ Don't |
|---|---|---|
| Space to storey | `IfcRelAggregates` (storey is `RelatingObject`, space is `RelatedObject`) | `IfcRelContainedInSpatialStructure` |
| Space → bounding element | `IfcRelSpaceBoundary` (physical or virtual, internal or external) | Just place the space near the wall |
| Grid axis | `IfcGridAxis` with explicit `AxisCurve` polyline endpoints | Just a Blender mesh edge |

## Add a space

```python
import bonsai_bim_helpers as bw
from bonsai import tool

ifc = tool.Ifc.get()
storey = ifc.by_type("IfcBuildingStorey")[0]

EXT = 0.2        # exterior wall thickness
INT_HALF = 0.05  # half of interior partition thickness

bw.add_space(
    name="NW_Room", long_name="NW private office",
    base_z=0.0, height=3.0,
    polygon_xy=[                                         # CCW interior footprint
        (EXT,              6.0 + INT_HALF),
        (4.625 - INT_HALF, 6.0 + INT_HALF),
        (4.625 - INT_HALF, 10.0 - EXT),
        (EXT,              10.0 - EXT),
    ],
    storey=storey,
    predef="INTERNAL",
    bounding_elements=[
        ("Ext_Wall_003", "PHYSICAL", "EXTERNAL"),
        ("Ext_Wall_004", "PHYSICAL", "EXTERNAL"),
        ("Int_NW_East",  "PHYSICAL", "INTERNAL"),
        ("Int_NW_South", "PHYSICAL", "INTERNAL"),
        ("Ground_Slab",  "PHYSICAL", "EXTERNAL_EARTH"),
        ("Office_Roof",  "PHYSICAL", "EXTERNAL"),
    ],
)
```

Effects:

1. **Aggregation** — adds (or extends) the `IfcRelAggregates` rel that
   makes the storey the parent of the space.
2. **Space boundaries** — one `IfcRelSpaceBoundary` per bounding element
   with `RelatedBuildingElement` set to the wall / slab / roof, plus
   `PhysicalOrVirtualBoundary` and `InternalOrExternalBoundary`
   classifiers.
3. **Quantities** — `Qto_SpaceBaseQuantities` populated from the polygon:
   `NetFloorArea` (shoelace), `NetVolume` (area × height),
   `GrossPerimeter`, `Height`.

`predef` accepts `INTERNAL` / `EXTERNAL` / `PARKING` / `GFA` / etc. —
the full `IfcSpaceTypeEnum`.

## Grid: bubbles MUST clear the dimension chains

**Hard rule** — `IfcGridAxis` lines extend `extension` metres past the
outermost axes. The default `extension=4.0` clears a 2-row dimension
chain (sub at ±1, overall at ±2) with 2 m of breathing room.

Why this isn't trivial — Bonsai's `bim.add_grid` operator hardcodes a
+/-2 m extension (`bonsai/bim/module/model/grid.py:48-67`). With overall
dim chains conventionally placed at +/-2 m offset, the bubbles overlap
the dim text — an annotation collision = drawing ERROR. And:

> **Post-hoc axis edits don't propagate to the SVG renderer.**
> Bonsai caches drawings via `.h5` files and apparently snapshots axes
> at creation. Modifying `IfcGridAxis.AxisCurve.Points[i].Coordinates`
> after creation is silently ignored.

So the skill's `add_project_grid(...)` BYPASSES the operator entirely.
It authors the grid manually:

1. Creates the `IfcGrid` via `bonsai.core.root.assign_class`.
2. For each axis, calls `ifcopenshell.api.grid.create_grid_axis` +
   `ifcopenshell.api.grid.create_axis_curve` with the desired extension
   baked in from the start.
3. Builds matching Blender mesh objects with the same extended verts.

```python
# 5 m × 5 m grid over a 20 m × 10 m office, bubbles 4 m past axes
bw.add_project_grid(
    u_spacing=5.0, total_u=3,    # A, B, C at y = 0, 5, 10
    v_spacing=5.0, total_v=5,    # 01..05 at x = 0, 5, 10, 15, 20
    extension=4.0,
)
```

## Bonsai axis convention

- **U axes** run HORIZONTALLY (parallel to world X), labelled LETTERS
  `A`, `B`, `C`, …. Each U axis sits at `y = i * u_spacing`.
- **V axes** run VERTICALLY (parallel to world Y), labelled zero-padded
  NUMBERS `01`, `02`, …. Each V axis sits at `x = i * v_spacing`.

Note this is the OPPOSITE of the rows-vs-columns mental model most
people start with. The U/V naming follows mathematical parametric
surface convention, not architectural row/column convention.

Customize tags after creation by writing directly to
`IfcGridAxis.AxisTag` for any axis whose default tag doesn't suit
(e.g. `A → A1` for a multi-zone project).

## Grid extension tuning

| Dim chain rows | Recommended `extension` |
|---|---|
| 0 (just element + bubbles) | 2.0 (Bonsai default) — or 3.0 for safety |
| 1 (overall only at ±2) | 4.0 (default) |
| 2 (sub at ±1, overall at ±2) | 4.0 (default) — 2 m clear band above the overall row |
| Heavy annotation (room labels, equipment tags, multiple dim chains) | 5-6 |

## Gotchas

- **`bim.assign_class` double-prefixes the Blender object name.** If
  the obj is "IfcSpace/Foo" before `assign_class`, after it becomes
  "IfcSpace/IfcSpace/Foo". `add_space(...)` builds with the bare name
  ("Foo") then renames to clean "IfcSpace/Foo" after.
- **Bonsai's `load_*_space_boundaries` operators LOAD existing
  boundaries** for display in the outliner — they don't CREATE them.
  Use the `bounding_elements` arg of `add_space` to author boundaries
  during creation.
- **`Qto_SpaceBaseQuantities` keys for IFC4** are exactly:
  `NetFloorArea`, `GrossFloorArea`, `NetVolume`, `GrossVolume`,
  `Height`, `GrossPerimeter`, `FinishCeilingHeight`,
  `FinishFloorHeight`. The helper writes the first 4 + height +
  perimeter from the polygon.
- **Grid is PROJECT-level, not aggregated into a storey.** A single
  grid is shared across all storeys in a multi-storey building —
  don't author one per floor.
- **Deleting + recreating the grid orphans the IfcGrid Blender Empty**
  (BIMObjectProperties.ifc_definition_id still points at the now-removed
  IfcGrid id), which then breaks the next `bpy.ops.bim.save_project`
  with `Instance #N not found`. After any IfcGrid removal, walk
  `bpy.data.objects` and remove any whose
  `ifc_definition_id` no longer resolves.

## Authoritative source references

| File | Lines | What |
|---|---|---|
| `ifcopenshell/api/grid/create_grid_axis.py` | (whole) | Axis entity creation |
| `ifcopenshell/api/grid/create_axis_curve.py` | (whole) | Axis polyline endpoint authoring |
| `bim/module/model/grid.py` | 32-79 | Bonsai's `bim.add_grid` operator — the one we bypass |
| `bim/module/spatial/operator.py` | 581+ | `ToggleGrids` operator (UI) |
| `ifcopenshell/api/relationship/...` | various | `assign_to_group`, `assign_aggregates` for the storey relation |
