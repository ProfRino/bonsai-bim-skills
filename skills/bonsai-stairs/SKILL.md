---
name: bonsai-stairs
description: |
  Add parametric IfcStair (with proper BBIM_Stair pset), the matching
  IfcOpeningElement that voids the upper slab, and IfcRailing guards
  around the opening. Trigger when the user wants stairs to an upper
  storey, a stairwell void, or a railing.
---

# bonsai-stairs — stairs + railings + stairwell openings

## When to use this

Trigger on:
- "add a stair", "add stairs", "stairs between floors"
- "stairwell", "stair opening", "stair void in slab"
- "railing", "handrail", "guard rail"
- "balustrade"

For walls + slabs: see [`bonsai-walls`](../bonsai-walls/).

## Core principle: ALWAYS IFC/BIM-correct

Stairs MUST be real `IfcStair` entities with `BBIM_Stair` psets (editable
treads, riser height, going, top slab connection). Stairwell voids MUST
be real `IfcOpeningElement` + `IfcRelVoidsElement` on the upper slab —
not Blender Boolean modifiers (which get LOST on IFC export, leaving a
solid slab that the stair pokes through in every IFC viewer).

| Intent | ✅ IFC mechanism | ❌ Don't |
|---|---|---|
| Parametric stair | `bim.add_stair` + `BBIM_Stair` pset + edit + finish | Tessellated mesh + `assign_class("IfcStair")` |
| Stairwell void in slab | `feature.add_feature(opening, slab)` → `IfcRelVoidsElement` | Boolean DIFFERENCE on slab mesh |
| Railing along path | `bim.add_railing` + `BBIM_Railing` pset along Blender mesh edges | Solidified curve in Blender |

## Add a parametric stair

```python
import bonsai_bim_helpers as bw

stair_obj, stair_entity = bw.add_parametric_stair(
    location=(2.0, 0.5, 0.0),       # bottom of first riser
    height=3.0,                      # floor-to-floor (matches storey separation)
    width=1.0,                       # tread depth perpendicular to direction
    n_treads=18,
    tread_depth=0.275,
    riser_height=3.0 / 18,
    direction="POSITIVE_Y",          # +Y → going north up the stair
    name="Stair_L1_to_L2",
    top_slab_depth=0.2,              # MUST match the upper slab thickness
    has_top_nib=True,                # adds the landing nib over the slab
)
```

Critical knobs:

- **`top_slab_depth` MUST match the upper slab thickness**. Otherwise
  the top step lands either below the slab face (gap) or pokes above it
  (overshoot).
- **`has_top_nib=True`** adds the parametric landing nib that lays on
  the upper slab. Without it, the top tread floats at the slab edge.
- **`direction`** is the world axis the stair goes UP toward, encoded
  as `POSITIVE_X` / `NEGATIVE_X` / `POSITIVE_Y` / `NEGATIVE_Y`.

The helper wraps `bim.add_stair → enable_editing_stair → set props →
finish_editing_stair` — the two-phase parametric pattern.

## Stairwell opening — bbox is a LIE

`stair.bbox.y_max` (or `.x_max` etc., depending on direction) INCLUDES
the top nib landing, which extends past the actual last tread back
edge. Sizing the stairwell opening to bbox leaves an empty strip past
the top tread.

**Always use `add_stairwell_opening_for_stair`** which sizes to the
actual last-tread back edge by reading the `BBIM_Stair.treads` list:

```python
bw.add_stairwell_opening_for_stair(
    stair_obj=stair_obj,
    slab_obj=upper_slab_obj,
    margin=0.05,        # 5 cm clearance around stair perimeter
)
```

This produces:
- `IfcOpeningElement` with footprint = stair tread perimeter + margin
- `IfcRelVoidsElement` connecting opening to the upper slab
- The upper slab body is regenerated with the void cut into it

## Add a railing along the stair / opening edge

`add_parametric_railing(path_points, height, name, predefined_type, closed)`:

- `path_points` — list of `(x, y, z)` world-space points defining the
  railing centreline. The path becomes a Blender mesh with vertex
  chain → edges; `bim.add_railing` reads the edges and runs the rail
  along them (Bonsai source: `railing.py:331-366`).
- `height` — typical values:
  - **1.1 m** for guard rails (around a stairwell opening on the upper
    floor — code-compliant fall protection).
  - **0.9 m** for stair handrails (one-sided, runs along the stair
    slope).
- `closed=True` — closed loop (balcony around a hole).
- `closed=False` — open polyline (stair handrail, one-sided guard).

```python
# 1.1 m guard around a stairwell opening (closed U around the void)
bw.add_parametric_railing(
    path_points=[
        (1.95, 0.45, 3.0),
        (1.95, 2.0,  3.0),
        (3.05, 2.0,  3.0),
        (3.05, 0.45, 3.0),
    ],
    height=1.1, name="Stairwell_Guard",
    predefined_type="GUARDRAIL", closed=False,   # open U
)

# 0.9 m handrail along the stair (one-sided)
bw.add_parametric_railing(
    path_points=[
        (1.95, 0.5, 0.9),
        (1.95, 5.4, 3.9),
    ],
    height=0.9, name="Stair_Handrail",
    predefined_type="HANDRAIL", closed=False,
)
```

## Gotchas

- **Top-nib landing IS NOT part of the last tread**. Sizing things to
  `stair.bbox` is wrong; use the `treads` list. See
  `add_stairwell_opening_for_stair`.
- **`bim.add_stair` runs against the addon's default config first**;
  the helper bypasses this by switching into edit mode before
  `bim.add_stair` runs, so your `n_treads`/`tread_depth`/etc. take
  immediate effect.
- **Stair connects to slab via parametric `top_slab_depth`** — match
  it to the slab thickness exactly. Mismatch produces a visible gap
  or overlap.
- **Guard rail around a stairwell should NOT be a closed loop** if
  the opening is at the head of a stair — closing the loop blocks the
  stair landing. Use a U-shape (`closed=False` with 4 points).
- **Railing direction matters for visual rendering** — the railing's
  uprights sit on the LEFT side of the path direction. Reverse
  `path_points` if the rails appear on the wrong side.

## Authoritative source references

| File | Lines | What |
|---|---|---|
| `bim/module/model/stair.py` | (whole) | `bim.add_stair` + `BBIM_Stair` editor |
| `bim/module/model/railing.py` | 331-366 | Railing path reader (Blender edges → IFC) |
| `ifcopenshell/api/feature/add_feature.py` | (whole) | `IfcRelVoidsElement` creation |
