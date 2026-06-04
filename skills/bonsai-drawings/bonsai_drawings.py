"""
Generate Plan / Section / Elevation drawings (SVG) from a Bonsai IFC project.

Replicates exactly what the Bonsai "Drawings and Documents" UI panel does:
  1. Add Drawing definitions (creates an IfcAnnotation camera per drawing).
  2. Activate a drawing — switches the scene camera to that drawing's view.
  3. Create Drawing — renders SVG via OpenCASCADE (or EEVEE/Cycles) and
     combines linework + annotation + underlay layers into a final SVG.

Source references (cloned IfcOpenShell repo):
  - bim/module/model/drawing/operator.py:163-192  (AddDrawing)
  - bim/module/model/drawing/operator.py:231-258  (CreateDrawing)
  - bim/module/model/drawing/operator.py:2389+    (ActivateDrawing)
  - bim/module/model/drawing/prop.py:285-291      (TARGET_VIEW_ITEMS)
  - tool/drawing.py:83                            (LOCATION_HINT_LITERALS)
  - tool/drawing.py:960-970                       (import_drawing)
"""

import os
import bpy
from mathutils import Matrix
import bonsai.tool as tool


# Valid target view literals (from prop.py TARGET_VIEW_ITEMS)
TARGET_VIEWS = ("PLAN_VIEW", "ELEVATION_VIEW", "SECTION_VIEW",
                "REFLECTED_PLAN_VIEW", "MODEL_VIEW")

# Valid location_hint literals for non-PLAN views (from tool/drawing.py:83)
DIRECTION_HINTS = ("PERSPECTIVE", "ORTHOGRAPHIC", "NORTH", "SOUTH", "EAST", "WEST")


def _require_saved_ifc_path():
    """Verify the active IFC has a real on-disk path BEFORE running any
    Bonsai drawing operator.

    Why this exists — Bonsai's `bim.add_drawing` operator calls
    `tool.Drawing.setup_shading_styles_path("drawings/...")`, which in
    turn calls `tool.Ifc.resolve_uri(...)`. That helper returns the
    relative `drawings/...` as-is if `tool.Ifc.get_path()` doesn't point
    at an actual file → `os.makedirs("drawings", exist_ok=True)` is then
    run from the process CWD. On Windows that CWD is typically
    `C:\\Program Files\\Blender` or the install directory and the call
    raises `PermissionError: [WinError 5] Access is denied: 'drawings'`,
    leaving a "Bonsai experienced an error :(" popup on screen.

    The fix is simple: save the IFC via `bpy.ops.bim.save_project(
    filepath=...)` (NOT `tool.Ifc.get().write(...)` — that bypasses
    Bonsai's state) BEFORE adding any drawing. This helper enforces it.

    Raises:
        RuntimeError with a clear, actionable message if the path is
        unset or unreachable.
    """
    ifc_path = tool.Ifc.get_path()
    if not ifc_path or not os.path.isfile(ifc_path):
        raise RuntimeError(
            "Bonsai's IFC path is not set or unreachable. "
            "Drawing operators write `<project_dir>/drawings/*.svg` "
            "relative to this path; without it the operator hits a "
            "PermissionError trying to create `drawings/` in the CWD. "
            "FIX: call `bpy.ops.bim.save_project(filepath=<absolute "
            "path>.ifc)` BEFORE adding any drawing — this is the only "
            "save method that updates `tool.Ifc.get_path()`. "
            "Plain `tool.Ifc.get().write(path)` does NOT update it."
        )


def add_drawing(target_view, location_hint=None, cursor_location=None):
    """Create a single drawing definition.

    Args:
        target_view: one of TARGET_VIEWS.
        location_hint:
          - For PLAN_VIEW / REFLECTED_PLAN_VIEW: the IfcBuildingStorey integer
            ID (the storey to draw). If None, picks the first storey.
          - For ELEVATION_VIEW / SECTION_VIEW: one of DIRECTION_HINTS.
        cursor_location: optional (x,y,z) — the 3D cursor is used as the camera
          anchor for elevations and sections. Ignored for plans. If None,
          defaults to the current cursor.

    Returns:
        The IfcAnnotation entity ID of the new drawing camera.

    Raises:
        RuntimeError if the project hasn't been saved via
        `bpy.ops.bim.save_project(filepath=...)` first (see
        `_require_saved_ifc_path` for the rationale).
    """
    if target_view not in TARGET_VIEWS:
        raise ValueError(f"target_view must be one of {TARGET_VIEWS}")

    ifc = tool.Ifc.get()
    if ifc is None:
        raise RuntimeError("No IFC project loaded.")
    _require_saved_ifc_path()

    if target_view in ("PLAN_VIEW", "REFLECTED_PLAN_VIEW"):
        if location_hint is None:
            storeys = ifc.by_type("IfcBuildingStorey")
            if not storeys:
                raise RuntimeError("No IfcBuildingStorey to draw.")
            location_hint = storeys[0].id()
        location_hint_str = str(int(location_hint))
    else:
        if location_hint is None:
            location_hint = "NORTH"
        if location_hint not in DIRECTION_HINTS:
            raise ValueError(
                f"For {target_view}, location_hint must be one of {DIRECTION_HINTS}"
            )
        location_hint_str = location_hint

    if cursor_location is not None:
        bpy.context.scene.cursor.location = tuple(cursor_location)

    # Record existing drawing IDs so we can spot the newly added one
    before = {g.id() for g in ifc.by_type("IfcAnnotation")
              if (g.ObjectType or "").upper() == "DRAWING"}

    doc_props = tool.Drawing.get_document_props()
    doc_props.target_view = target_view
    doc_props.location_hint = location_hint_str
    bpy.ops.bim.add_drawing()

    after = {g.id() for g in ifc.by_type("IfcAnnotation")
             if (g.ObjectType or "").upper() == "DRAWING"}
    new_ids = after - before
    if not new_ids:
        raise RuntimeError("Drawing was not created — check storey/direction.")
    return next(iter(new_ids))


def generate_drawing_svg(drawing_id):
    """Render the SVG for a drawing.

    Args:
        drawing_id: IfcAnnotation entity ID of the drawing camera
                    (returned by add_drawing()).

    Returns:
        Path to the generated SVG, or None if not found.
    """
    bpy.ops.bim.activate_drawing(drawing=drawing_id)
    bpy.ops.bim.create_drawing(open_viewer=False)

    # Bonsai writes SVGs to <project_dir>/drawings/<DRAWING NAME>.svg
    # where <project_dir> is the folder of the active IFC file.  Use
    # `tool.Ifc.get_path()` which is the canonical source (the same one
    # Bonsai itself uses via `tool.Ifc.resolve_uri`); avoids reaching
    # into `wrapped_data.header.file_name` which is API-unstable across
    # ifcopenshell versions.
    ifc = tool.Ifc.get()
    entity = ifc.by_id(drawing_id)
    name = entity.Name
    ifc_path = tool.Ifc.get_path()
    if ifc_path and os.path.isfile(ifc_path):
        out = os.path.join(os.path.dirname(ifc_path), "drawings", f"{name}.svg")
        if os.path.exists(out):
            return out
    # Fallback — Blender file dir
    blend_dir = bpy.path.abspath("//")
    if blend_dir:
        candidate = os.path.join(blend_dir, "drawings", f"{name}.svg")
        if os.path.exists(candidate):
            return candidate
    return None


def set_drawing_scale_and_extents(
    drawing_id,
    scale="1:50",
    width=None,         # camera width in metres
    height=None,        # camera height in metres
    centre=None,        # (x, y) world position of camera centre
):
    """Configure a drawing's diagram scale and camera coverage.

    The interactive UI lets you tweak Scale / Width / Height in the Active
    Drawing panel. This wraps that with proper API calls.

    Common scale strings (must match Bonsai's diagram_scale enum):
      "1:20|1/20", "1:50|1/50", "1:100|1/100", "1:200|1/200"

    A short form like "1:50" is accepted — we expand it to the full enum
    identifier "1:50|1/50" automatically.

    Args:
        drawing_id: IfcAnnotation entity ID of the drawing.
        scale: e.g. "1:50" or the full "1:50|1/50".
        width / height: camera coverage in metres. For a 5x5m room, ~7x7m
            gives a comfortable margin.
        centre: (x, y) world position to centre the camera over.
    """
    bpy.ops.bim.activate_drawing(drawing=drawing_id)
    cam_obj = bpy.context.scene.camera
    cam_props = cam_obj.data.BIMCameraProperties

    if scale and "|" not in scale:
        # e.g. "1:50" -> "1:50|1/50"
        try:
            n, d = scale.split(":")
            scale = f"{scale}|{n}/{d}"
        except ValueError:
            raise ValueError(f"Bad scale format: {scale!r}")
    if scale:
        cam_props.diagram_scale = scale

    if width is not None:
        cam_props.width = float(width)
    if height is not None:
        cam_props.height = float(height)
    if width is not None or height is not None:
        cam_props.update_camera_resolution()

    if centre is not None:
        cam_obj.location.x = float(centre[0])
        cam_obj.location.y = float(centre[1])


def add_dimension(p1, p2, drawing_id=None):
    """Add a linear dimension annotation between two world-space points.

    Bonsai's `bim.add_annotation` operator creates a single placeholder line
    when `object_type="DIMENSION"`. We then overwrite the curve's two control
    points with the actual measurement endpoints.

    The dimension's text is computed automatically from the distance between
    p1 and p2 in metres (so passing (0,0,0)-(5,0,0) renders "5.000").

    Args:
        p1, p2: (x, y, z) world coordinates of the dimension endpoints.
        drawing_id: optional IfcAnnotation ID of the drawing the dimension
            belongs to. If None, uses the currently active drawing.

    Returns:
        The created Blender object (IfcAnnotation).

    Notes:
      - The annotation is added to the active drawing — call
        `bpy.ops.bim.activate_drawing(drawing=...)` first if needed.
      - The line extends EXACTLY from p1 to p2. To offset the dim line
        from the wall edge, offset p1/p2 yourself (e.g. y -= 0.5 to push
        below a south wall).
      - The geometry is a Bonsai-native Curve with a single POLY spline.

    Source: bim/module/drawing/operator.py:1731-1762 (AddAnnotation)
            tool/drawing.py:183-213 (create_annotation_object — "else" branch
            calls add_line_to_annotation which produces our 2-point curve)
    """
    if drawing_id is not None:
        bpy.ops.bim.activate_drawing(drawing=drawing_id)

    ann_props = tool.Drawing.get_annotation_props()
    ann_props.object_type = "DIMENSION"
    ann_props.relating_type_id = "0"

    # Snapshot scene to detect the new object
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    before = {o.name for o in bpy.data.objects}
    bpy.ops.bim.add_annotation()
    if bpy.context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    new = [n for n in (set(o.name for o in bpy.data.objects) - before)
           if n.startswith("IfcAnnotation/")]
    if not new:
        raise RuntimeError("add_annotation produced no IfcAnnotation object.")
    obj = bpy.data.objects[new[0]]

    # Reset matrix so curve control points read as world coords
    obj.matrix_world = Matrix.Identity(4)

    # Overwrite the POLY spline's two control points (curve.points are 4D)
    sp = obj.data.splines[0]
    sp.points[0].co = (float(p1[0]), float(p1[1]), float(p1[2]), 1.0)
    sp.points[1].co = (float(p2[0]), float(p2[1]), float(p2[2]), 1.0)
    return obj


def activate_model_view(hide_annotation_markers=True):
    """Exit any active drawing and return Blender to the free 3D model view.

    Equivalent to clicking the "Activate Model" button at the top of Bonsai's
    "Drawings and Documents" sidebar panel. Restores visibility of all model
    elements, resets representations to Model/Body/MODEL_VIEW, and frees
    the viewport from the active drawing's camera.

    Gotcha: `bpy.ops.bim.activate_model()` does NOT hide every drawing helper
    cleanly. Section cut paths leak through as `Item/IfcIndexedPolyCurve/*`
    stubs, and the section/elevation/level marker IfcAnnotations stay visible
    too — they appear as white lines and tiny line segments inside the model.
    Set `hide_annotation_markers=True` (default) to hide them all. They are
    NOT deleted — activating a drawing again will redisplay them.

    Source: bim/module/drawing/operator.py:2236-... (`ActivateModel`)
    """
    bpy.ops.bim.activate_model()

    if hide_annotation_markers:
        for o in bpy.data.objects:
            if (o.name.startswith("Item/") or
                o.name.startswith("IfcAnnotation/")):
                if not o.hide_get():
                    o.hide_set(True)


def add_standard_drawings(cursor_location=None):
    """Convenience: create one Plan + 4 Elevations (N/S/E/W) + 1 Section."""
    if cursor_location is None:
        cursor_location = bpy.context.scene.cursor.location
    drawings = {}
    drawings["PLAN"] = add_drawing("PLAN_VIEW")
    for d in ("NORTH", "SOUTH", "EAST", "WEST"):
        drawings[f"{d}_ELEVATION"] = add_drawing(
            "ELEVATION_VIEW", location_hint=d, cursor_location=cursor_location
        )
    drawings["NORTH_SECTION"] = add_drawing(
        "SECTION_VIEW", location_hint="NORTH", cursor_location=cursor_location
    )
    return drawings


def render_all_drawings(drawings_dict):
    """Render SVGs for every drawing in {name: ifc_id} dict."""
    svgs = {}
    for name, ifc_id in drawings_dict.items():
        svgs[name] = generate_drawing_svg(ifc_id)
    return svgs


# ---------------------------------------------------------------------------
# Standalone — Plan + 4 Elevations + 1 Section for the current storey
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Anchor elevations/sections at the centre of a 5x5m room at mid-height
    drawings = add_standard_drawings(cursor_location=(2.5, 2.5, 1.5))
    print(f"Created {len(drawings)} drawings: {list(drawings.keys())}")

    svgs = render_all_drawings(drawings)
    for name, path in svgs.items():
        print(f"  {name}: {path}")
