---
name: bonsai-openings
description: |
  Add doors and windows (real BBIM parametric IfcDoor / IfcWindow with
  proper IfcRelVoidsElement + IfcRelFillsElement) to existing IfcWalls.
  Includes the default rule that windows in a wall are equally spaced
  and centred. Trigger when the user wants to add doors, windows,
  fillings, or wants to control window placement / styling.
---

# bonsai-openings — doors + windows + equal-spacing

## When to use this

Trigger on:
- "add a door", "add a window", "place a door / window"
- "equally spaced windows", "centred windows", "window layout"
- "door type", "operation type", "single swing", "double swing"
- "style windows", "Frame", "Glass", "Panel"

For walls themselves: see [`bonsai-walls`](../bonsai-walls/).
For project setup that creates door / window styles: see
[`bonsai-project-setup`](../bonsai-project-setup/).

## Core principle: ALWAYS IFC/BIM-correct

Every opening must be a real `IfcOpeningElement` linked to its host wall
via `IfcRelVoidsElement`, and each door/window must be a real
`IfcDoor`/`IfcWindow` linked to the opening via `IfcRelFillsElement`.
Direct mesh edits on a wall are not opening cuts — they don't survive
IFC export.

| Intent | ✅ IFC mechanism | ❌ Don't |
|---|---|---|
| Cut a void in a wall | `feature.add_feature(opening, wall)` → `IfcRelVoidsElement` | Boolean modifier in Blender |
| Fill an opening with door/window | `feature.add_filling(opening, filling)` → `IfcRelFillsElement` | Just place a door near the wall |
| Parametric door/window | `BBIM_Door`/`BBIM_Window` pset + `mesh.add_door` / `mesh.add_window` + edit + finish | `bim.duplicate_type` + mesh scale (proportions distort) |

## DEFAULT RULE: windows are equally spaced and centred

When placing more than one window in a wall, every end-gap and every
between-window gap MUST be identical:

```
gap = (L − N · W) / (N + 1)
```

so window centres land at `(i+1) · gap + (i + 0.5) · W` for i = 0 … N-1.

With N=1 the single window sits exactly at L/2. Asymmetric layouts
(clusters, off-centre runs) are EXCEPTION cases — only do them when the
design brief explicitly requires asymmetry.

The pitfall this fixes: hand-computed centres using "1.5 m from each
wall end + 3 m between" produce LEFT-LEANING runs (small start-gap, big
end-gap) that look wrong in every elevation.

```python
import bonsai_bim_helpers as bw

# 5 equally-spaced 1.5×1.4 m windows on a clean 20 m north wall, sill 0.9 m
bw.add_equally_spaced_windows_to_wall(
    wall_obj=north_wall, count=5,
    width=1.5, height=1.4, sill_height=0.9,
    name_prefix="N_W",
)

# Wall with a centred door at x = 10 — split into two segments
bw.add_equally_spaced_windows_to_wall(
    south_wall, count=2, segment=(0.0, 9.4),
    width=1.5, height=1.4, sill_height=0.9, name_prefix="S_W_left",
)
bw.add_equally_spaced_windows_to_wall(
    south_wall, count=2, segment=(10.6, 20.0),
    width=1.5, height=1.4, sill_height=0.9, name_prefix="S_W_right",
)
```

The helper uses `wall_obj.matrix_world` so any wall rotation works — as
long as the wall was built by `bonsai-walls` helpers (local +X along
wall length, local +Y into the room).

## Parametric vs typed occurrences

Two paths exist; use the parametric one for new work.

| Helper | Result |
|---|---|
| `add_window_to_wall(wall, position, window_type_name)` | Occurrence of an existing `IfcWindowType`. Width/height come from the type's mesh — **NOT per-occurrence editable**. |
| `add_parametric_window_to_wall(wall, target, width, height, name)` | Real BBIM `IfcWindow` occurrence with its OWN `BBIM_Window` pset. Per-occurrence editable via Bonsai sidebar sliders. **Recommended.** |
| `add_parametric_door_to_wall(wall, target, width, height, operation_type, name)` | Same idea for doors. Bypasses the degenerate `IfcDoorType` path (`bim.add_door` doesn't build proper geometry for types). |

Door operation types (the BBIM_Door `door_type` enum):

- `SINGLE_SWING_LEFT`, `SINGLE_SWING_RIGHT`
- `DOUBLE_SWING_LEFT`, `DOUBLE_SWING_RIGHT`
- `DOUBLE_DOOR_SINGLE_SWING`
- `SLIDING_TO_LEFT`, `SLIDING_TO_RIGHT`
- `DOUBLE_DOOR_SLIDING`

```python
# Main entrance — 1.2 × 2.1 m double swing, left edge at world x=9.4
bw.add_parametric_door_to_wall(
    wall_obj=south_wall,
    target=(9.4, 0.0, 0.0),
    width=1.2, height=2.1,
    name="Main_Entrance",
    operation_type="DOUBLE_SWING_LEFT",
)
```

## Target geometry quirk — `target` is a corner, not the centre

`add_parametric_window_to_wall(target=(x, y, sill_z))` places the
window with its LOCAL +X-most edge at `target`. The body grows in the
**wall's local +X direction**.

To centre a 1.8 m window at y=3.0 of an east/west wall:

```python
target = (x_face, 3.0 - 1.8/2, sill_z)  # subtract half-width
```

For walls built by the skill, `add_equally_spaced_windows_to_wall(...)`
handles all this internally — use it whenever placing more than one
window so you never have to think about the corner-vs-centre rule.

## Styling (Frame / Glass / Panel)

`mesh.add_window` and `mesh.add_door` leave all their `IfcExtrudedAreaSolid`
items un-styled. Without explicit styling, BBIM windows render as flat
grey rectangles instead of dark frame + glass panes.

The skill auto-applies project styles to every parametric door / window
on creation:

| Item shape | Style assigned |
|---|---|
| `IfcArbitraryProfileDefWithVoids` (frame, sash) | `Frame` IfcSurfaceStyle |
| `IfcArbitraryClosedProfileDef` (glass pane) | `Glass` IfcSurfaceStyle |
| Largest extrusion depth (door panel) | `Panel` IfcSurfaceStyle |

The styles `Frame`, `Glass`, `Panel` are created by
[`bootstrap_project()`](../bonsai-project-setup/) and linked to Blender
materials via `BIMStyleProperties.ifc_definition_id`.

To re-style every opening in one call (e.g. after regenerating walls):

```python
bw.style_all_openings(
    frame_style_name="Frame",
    glass_style_name="Glass",
    panel_style_name="Panel",
)
```

## Quantities + schema attributes

Bonsai does NOT auto-populate `IfcDoor.OverallWidth` / `OverallHeight`
or `IfcWindow.OverallWidth` / `OverallHeight` schema attributes for
typed occurrences. Run `fill_opening_overall_attrs()` before any IDS
validation / handover:

```python
bw.fill_opening_overall_attrs()    # walks every IfcDoor + IfcWindow
```

Source priority: BBIM pset (if present) → fall back to geometry bbox.

## Gotchas

- **Setting `obj.location = target` doesn't sync IFC placement.** Without
  `set_world_location(obj, location)` the IFC placement reverts to
  origin on save+reload, even though Blender looks correct. The
  parametric helpers handle this internally; for hand placement, always
  use `set_world_location`.
- **Window grows in -Y from the target on east/west walls.** To centre
  a 1.8 m window at y=3.0 of a 6 m wall, pass `target=(x_face, 3.9,
  sill_z)`. (The `add_equally_spaced_windows_to_wall` helper does this
  math for you — prefer it.)
- **Re-running `add_*` cycles on a populated scene leaves orphan walls**
  that COVER UP doors/windows so they look "stuck on" or fragmented.
  Run `cleanup_orphan_walls(name_prefix_to_keep)` before re-adding
  fillings.
- **Switching wall representation wipes Blender modifiers** — including
  any roof-fit Boolean modifier from the legacy
  `fit_walls_to_mono_pitch_roof`. `regen_all_walls(restore_boolean_modifiers=True)`
  snapshots and restores them; or use the IFC-correct
  `fit_walls_to_mono_pitch_roof_ifc` from [`bonsai-roofs`](../bonsai-roofs/)
  which doesn't depend on Blender modifiers.

## Authoritative source references

| File | Lines | What |
|---|---|---|
| `bim/module/model/opening.py` | 411-483 | BBIM_Window create + edit flow |
| `bim/module/model/opening.py` | 282-288 | `FilledOpeningGenerator.generate` — note Z ignore |
| `ifcopenshell/api/feature/add_feature.py` | (whole) | `IfcRelVoidsElement` creation |
| `ifcopenshell/api/feature/add_filling.py` | (whole) | `IfcRelFillsElement` creation |
