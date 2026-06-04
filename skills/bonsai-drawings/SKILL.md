---
name: bonsai-drawings
description: |
  Programmatically create and render 2D drawings (Plan, Section, Elevation,
  Reflected Plan) and final SVGs from a Bonsai IFC project in Blender. Uses
  Bonsai's native bim.add_drawing / bim.activate_drawing / bim.create_drawing
  operators — same as the "Drawings and Documents" sidebar panel.
  Use when the user wants to generate plan views, sections, elevations or
  export 2D construction drawings from a BIM model.
---

# Bonsai drawings — Plans, Sections, Elevations from Python

## Core principle: ALWAYS IFC/BIM-correct

Drawings are not just visual output — they are IFC entities
(`IfcAnnotation` cameras grouped under an `IfcGroup`) that travel with the
model. Every drawing operation in this skill drives an actual Bonsai
operator that creates real IFC entities. Don't fall back to standalone
Blender cameras + viewport screenshots — those don't round-trip the IFC.

The same rule applies to annotations (dimensions, levels, text): they MUST
be `IfcAnnotation` entities assigned to the drawing's group, not Blender
overlays. The skill's `add_dimension` does this via `bim.add_annotation`.

## When to use this

Trigger when the user wants to:
- Add Plan / Section / Elevation / Reflected Plan / Model views to an IFC project
- Generate SVG output for a drawing (linework + annotation + underlay combined)
- Render a whole set of construction drawings in one pass
- Pipe drawings into sheets/PDFs via Bonsai's sheeter

## The flow

Three operators, called in this order per drawing:

```
bim.add_drawing       → creates IfcAnnotation camera + drawing group
bim.activate_drawing  → switches scene camera to that view
bim.create_drawing    → renders SVG via OpenCASCADE
```

The interactive "Drawings and Documents" panel does the same thing — we just
set the props before each call instead of clicking buttons.

## ⚠️ MANDATORY: save the IFC via `bpy.ops.bim.save_project` BEFORE any drawing

**Hard prerequisite.** Bonsai's `bim.add_drawing` writes SVGs to
`<project_dir>/drawings/*.svg` where `<project_dir>` is resolved from
`tool.Ifc.get_path()`. If that returns an empty string (project never
saved through the operator), `tool.Ifc.resolve_uri("drawings/...")` keeps
the relative path as-is and Bonsai then calls
`os.makedirs("drawings", exist_ok=True)` from the process CWD. On Windows
that CWD is usually the Blender install directory, so the call raises:

```
PermissionError: [WinError 5] Access is denied: 'drawings'
```

…and a "Bonsai experienced an error :(" popup appears on screen.

The fix is one line:

```python
# ✅ DO — sets tool.Ifc.get_path() so drawings/ resolves to <ifc_dir>/drawings/
bpy.ops.bim.save_project(filepath=r"C:\path\to\project.ifc")

# ❌ DON'T — writes the file but does NOT update Bonsai's path state
tool.Ifc.get().write(r"C:\path\to\project.ifc")
```

`add_drawing(...)` in this skill now calls `_require_saved_ifc_path()`
defensively and raises a clear `RuntimeError` if the path is unset,
rather than letting the PermissionError reach the UI. If you DID call
`ifc.write(...)` earlier, follow it with a `bpy.ops.bim.save_project(...)`
to the same path before adding drawings.

## How to use

```python
from bonsai_drawings import (
    add_drawing,
    generate_drawing_svg,
    set_drawing_scale_and_extents,
    add_dimension,
    add_standard_drawings,
    render_all_drawings,
)

# One drawing at a time
plan_id = add_drawing("PLAN_VIEW")

# Right-size it for a 5×5m room: 7×7m camera coverage @ 1:50 → 140mm sheet
set_drawing_scale_and_extents(
    plan_id, scale="1:50", width=7.0, height=7.0, centre=(2.5, 2.5)
)

# Overall measurements (Bonsai DIMENSION = single span only)
add_dimension((0.0, -0.5, 0.0), (5.0, -0.5, 0.0))  # 5.000 m width
add_dimension((-0.5, 0.0, 0.0), (-0.5, 5.0, 0.0))  # 5.000 m depth

svg = generate_drawing_svg(plan_id)
print(svg)  # → .../drawings/MY STOREY PLAN.svg

# Or one-shot: Plan + N/S/E/W Elevations + 1 Section
drawings = add_standard_drawings(cursor_location=(2.5, 2.5, 1.5))
svgs = render_all_drawings(drawings)
```

## Choosing the right scale

Match scale + camera coverage to your subject so the result fits a paper size:

| Subject | Scale | Camera width | Sheet @ scale |
|---|---|---|---|
| Single room (5×5m) | 1:50 | 7m | 140mm |
| Small house (15×10m) | 1:100 | 20m | 200mm |
| Building floor (50×30m) | 1:200 | 60m | 300mm |
| Site (200m) | 1:500 | 250m | 500mm |

Rule of thumb: **camera coverage = subject + 2m margin**; pick the scale that
keeps the resulting sheet under ~A1 (594mm).

### Output location

Bonsai writes drawings to `<project_dir>/drawings/<DRAWING NAME>.svg`. The
project dir is the directory containing the open `.ifc` file. Each drawing
also has cached intermediate layers under `drawings/cache/`.

## Valid arguments

| Param | Valid values |
|---|---|
| `target_view` | `PLAN_VIEW`, `ELEVATION_VIEW`, `SECTION_VIEW`, `REFLECTED_PLAN_VIEW`, `MODEL_VIEW` |
| `location_hint` (plans) | integer storey ID — passed as string to the EnumProperty |
| `location_hint` (elev/section) | `PERSPECTIVE`, `ORTHOGRAPHIC`, `NORTH`, `SOUTH`, `EAST`, `WEST` |
| `cursor_location` | `(x, y, z)` — only used for elevations/sections to anchor the camera |

## Gotchas

- **Dimensions render as a curve, not a mesh.** `bim.add_annotation` with
  `object_type="DIMENSION"` creates an IfcAnnotation whose data is a
  `bpy.types.Curve` with one POLY spline of two control points. Set them via
  `obj.data.splines[0].points[i].co = (x, y, z, 1.0)` — 4D (w=1).
- **Dimension chains are NOT supported by Bonsai's stock `DIMENSION`
  annotation type — confirmed by testing.** Whether you create N separate
  single-segment dimensions OR one annotation with N+1 curve control points,
  the SVG renderer still emits arrow markers at every segment endpoint,
  producing the clashing `→←` look at every interior joint. For proper
  architectural chains you have two options:
    1. Use a single overall dimension only (skip the interior breakdown), OR
    2. Post-process the generated SVG to strip interior arrow markers
       between consecutive `<line>` elements that share endpoints.
  Investigate Bonsai's `ALIGNED_DIMENSION` predefined type (if added later
  upstream) or the in-development chain decorator before reattempting.
- **Reset matrix_world to identity before writing control points**, otherwise
  the points are interpreted in local space and you'll get the wrong line.
- **Stray placeholder dimensions** accumulate if you call `add_annotation`
  multiple times without naming them — Bonsai auto-names them
  `IfcAnnotation/DIMENSION`, `.001`, `.002`. Clean up unwanted ones before
  regenerating the drawing.
- **`add_drawing` reads `tool.Drawing.get_document_props()`** — you set
  `target_view` and `location_hint` on the doc props BEFORE calling the op.
- **The location_hint EnumProperty is a string**, even when it represents an
  integer storey ID. `add_drawing()` in this skill handles the str()/int()
  conversion automatically.
- **Elevations and sections use the 3D cursor as the camera anchor** (so set
  it to the centre of the area you want to document before calling).
- **`activate_drawing` takes the IfcAnnotation entity ID**, not the IfcGroup
  ID. The camera (`IfcAnnotation/MY STOREY PLAN`) is the drawing entity.
- **First SVG generation copies default assets** (`patterns.svg`, `markers.svg`,
  `default.css`) into `drawings/assets/` from Bonsai's bundle. That warning in
  stdout is expected on the first run.
- **`bim.create_drawing` is slow** (~0.5-1 sec per drawing). For large drawing
  sets, render in the background or batch overnight.
- **Switching back to model view requires `bpy.ops.bim.activate_model()`** —
  the "Activate Model" button at the top of Bonsai's Drawings panel.
  Plain `bpy.context.scene.camera = None` is not enough; the drawing context
  also affects element visibility and active representations.
- **`activate_model` leaks annotation markers** into the 3D view: section cut
  paths show as white lines, elevation/section/level marker IfcAnnotations
  cluster around the drawing camera origins. The skill's
  `activate_model_view(hide_annotation_markers=True)` hides everything that
  starts with `Item/` or `IfcAnnotation/` so the 3D model view is clean.
  They are hidden, not deleted — activating any drawing again restores them.

## Authoritative source references

| File | Lines | What it does |
|---|---|---|
| `bim/module/drawing/operator.py` | 163-192 | `AddDrawing` operator |
| `bim/module/drawing/operator.py` | 231-258 | `CreateDrawing` operator |
| `bim/module/drawing/operator.py` | 2389+   | `ActivateDrawing` operator |
| `bim/module/drawing/prop.py`     | 285-291 | `TARGET_VIEW_ITEMS` enum |
| `tool/drawing.py`                | 83      | `LOCATION_HINT_LITERALS` |
| `tool/drawing.py`                | 960-970 | `import_drawing` (asserts representation) |
| `bim/module/drawing/svgwriter.py` | (whole) | SVG writer — styling, layers, combine |
| `bim/module/drawing/sheeter.py`  | (whole) | Sheet composition (TODO: extend skill) |

Cloneable from [github.com/IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell).

## Related skills

- **bonsai-walls** — Build the 3D model (walls + slab + doors + windows)
  that these drawings document.

## TODO / future extensions

- Sheets: `bim.create_sheet` + `bim.add_drawing_to_sheet` → composed A1 / A3
  sheets with title block, scale bar, north arrow.
- Drawing styles: `bim.add_drawing_style` for layered linework / hatches.
- PDF export: configurable via Bonsai preferences `svg_command` / `pdf_command`.
