"""End-to-end build of a 10 x 20 m single-storey open office.

Showcases every June 2026 addition to bonsai-walls in one script:
  * Dual wall types: WAL200 (exterior, 200 mm) + WAL100 (interior, 100 mm)
  * Equally-spaced + centred windows by default (lesson 44)
  * Interior partitions auto-clipped to exterior inner faces (lesson 45)
  * Interior L-corners auto-connected to siblings via DumbWallJoiner —
    partition-to-exterior junctions deliberately left as butt joints
    (lesson 46, the 20m->10.85m exterior wall trim was caught here)
  * Project grid (5 m x 5 m) with extended axes via the proper API,
    not Bonsai's hardcoded +/-2 m operator path (lessons 47 + 49)
  * 1:100 floor plan SVG with 12 linear dimensions on all 4 sides,
    saved via bpy.ops.bim.save_project FIRST so the drawings path
    resolves correctly (lesson 48)

Open Blender 5.1 + Bonsai 0.8.5+ with a 3D View, then Run Script.

Edit OUTPUT_DIR + SKILL_DIRS below to match your environment.
"""
import os
import sys
import math

# ---------------------------------------------------------------------------
# CONFIGURE FOR YOUR ENVIRONMENT
# ---------------------------------------------------------------------------
# Where IFC + SVG + IDS artefacts will be written
OUTPUT_DIR = os.path.expanduser(r"~/Desktop/bonsai-bim-skills-output")

# Where the cloned bonsai-bim-skills/skills/ subfolders live. Adjust if
# you cloned the repo somewhere else.
SKILL_DIRS = [
    os.path.expanduser(r"~/.claude/skills/bonsai-walls"),
    os.path.expanduser(r"~/.claude/skills/bonsai-drawings"),
]

# ---------------------------------------------------------------------------
import bpy
from mathutils import Vector, Euler

os.makedirs(OUTPUT_DIR, exist_ok=True)
for d in SKILL_DIRS:
    if d not in sys.path:
        sys.path.insert(0, d)
# Force fresh import so edits to skill source take effect in the same
# Blender session.
for mod_name in ("bonsai_room_with_miters", "bonsai_drawings"):
    if mod_name in sys.modules:
        del sys.modules[mod_name]

import bonsai_room_with_miters as bw
import bonsai_drawings as bd
from bonsai import tool


# 3D View context override — Bonsai operators read context.selected_objects
def _find_3d_view():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                region = next(r for r in area.regions if r.type == "WINDOW")
                return win, area, region
    return None, None, None


_win, _area, _region = _find_3d_view()
if _area is None:
    raise RuntimeError("Open Blender's Scripting/Layout workspace with a 3D View first.")
_override = bpy.context.temp_override(window=_win, area=_area, region=_region)
_override.__enter__()


# ===========================================================================
# 1. PROJECT BOOTSTRAP
# ===========================================================================
bw.bootstrap_project(
    project_name="10x20 office",
    exterior_wall_type_name="WAL200",
    exterior_wall_thickness=0.2,
    interior_wall_type_name="WAL100",
    interior_wall_thickness=0.1,
)
print("Bootstrap complete")


# ===========================================================================
# 2. EXTERIOR SHELL + GROUND SLAB + ROOF
# ===========================================================================
W, D, H = 20.0, 10.0, 3.0
OVERHANG = 0.3

# 4 mitred exterior walls (CCW from SW corner)
corners = [(0, 0), (W, 0), (W, D), (0, D)]
pairs = bw.create_room_with_mitered_corners(
    corners=corners,
    wall_type_name="WAL200",
    height=H,
    closed=True,
    name_prefix="Ext_Wall",
)
walls = [obj for obj, _ in pairs]
south, east, north, west = walls

# Ground slab — top flush with z=0
slab_obj, _ = bw.add_floor_slab_from_walls(
    wall_objs=walls,
    slab_type_name="FLR200",
    align_top_to_storey=True,
)
slab_obj.name = "IfcSlab/Ground_Slab"

# Flat roof — 0.3 m overhang on every side
roof_corners = [
    (-OVERHANG, -OVERHANG),
    (W + OVERHANG, -OVERHANG),
    (W + OVERHANG, D + OVERHANG),
    (-OVERHANG, D + OVERHANG),
]
bw.add_flat_roof(
    footprint_xy=roof_corners,
    base_z=H,
    thickness=0.2,
    name="Office_Roof",
)

print("Shell + slab + roof complete")


# ===========================================================================
# 3. ENTRANCE DOOR + WINDOWS (equally spaced per default rule)
# ===========================================================================

# Main entrance — 1.2 m x 2.1 m double swing, centred on south wall at x=10
bw.add_parametric_door_to_wall(
    wall_obj=south,
    target=(9.4, 0.0, 0.0),     # left edge of door panel
    width=1.2,
    height=2.1,
    name="Main_Entrance",
    operation_type="DOUBLE_SWING_LEFT",
)

# South wall: 2 + door + 2.  Split into segments around the door.
bw.add_equally_spaced_windows_to_wall(
    south, count=2, width=1.5, height=1.4, sill_height=0.9,
    segment=(0.0, 9.4), name_prefix="S_W_left",
)
bw.add_equally_spaced_windows_to_wall(
    south, count=2, width=1.5, height=1.4, sill_height=0.9,
    segment=(10.6, 20.0), name_prefix="S_W_right",
)
# North wall (clean 20 m): 5 evenly-spaced windows
bw.add_equally_spaced_windows_to_wall(
    north, count=5, width=1.5, height=1.4, sill_height=0.9,
    name_prefix="N_W",
)
# East + West walls (clean 10 m each): 2 windows
bw.add_equally_spaced_windows_to_wall(
    east, count=2, width=1.5, height=1.4, sill_height=0.9,
    name_prefix="E_W",
)
bw.add_equally_spaced_windows_to_wall(
    west, count=2, width=1.5, height=1.4, sill_height=0.9,
    name_prefix="W_W",
)

print("Entrance + 13 windows placed")


# ===========================================================================
# 4. INTERIOR PARTITIONS (auto-clip + same-thickness sibling auto-connect)
# ===========================================================================

# Build the East/West spine partitions FIRST so the South partitions can
# L-corner connect to them via DumbWallJoiner.
# Partitions sit in the gaps between north windows so no partition clips
# a window. North windows are at x = 2.833 / 6.417 / 10.0 / 13.583 /
# 17.167; the gap midpoints between adjacent windows are x = 4.625 and
# x = 15.375 — partitions go there.
bw.add_interior_wall(start_xy=(4.625, 6.0),  end_xy=(4.625, 10.0),
                     height=H, wall_type_name="WAL100", name="Int_NW_East")
bw.add_interior_wall(start_xy=(15.375, 6.0), end_xy=(15.375, 10.0),
                     height=H, wall_type_name="WAL100", name="Int_NE_West")
# South partitions — start_xy can be flush with the exterior wall outer
# face (e.g. x=0); add_interior_wall auto-clips to the inner face (x=0.2).
nw_south_obj, _ = bw.add_interior_wall(
    start_xy=(0.0,    6.0), end_xy=(4.625, 6.0),
    height=H, wall_type_name="WAL100", name="Int_NW_South",
)
ne_south_obj, _ = bw.add_interior_wall(
    start_xy=(15.375, 6.0), end_xy=(20.0,  6.0),
    height=H, wall_type_name="WAL100", name="Int_NE_South",
)

# Interior doors — centred on each south partition.  Use the wall's
# ACTUAL local length (after clip + miter extension) so the door lands
# at the geometric centre regardless of build order.
def add_centred_door(wall, name, op):
    L = float(wall.dimensions.x)
    door_w = 0.9
    target_local = Vector(((L - door_w) / 2.0, 0.0, 0.0))
    target_world = wall.matrix_world @ target_local
    bw.add_parametric_door_to_wall(
        wall_obj=wall, target=tuple(target_world),
        width=door_w, height=2.0,
        name=name, operation_type=op,
    )

add_centred_door(nw_south_obj, "Door_NW", "SINGLE_SWING_LEFT")
add_centred_door(ne_south_obj, "Door_NE", "SINGLE_SWING_RIGHT")

print("4 partitions + 2 interior doors placed")


# ===========================================================================
# 5. SPACES — NW Room + NE Room + Shared Workspace
# ===========================================================================
ifc = tool.Ifc.get()
storey = ifc.by_type("IfcBuildingStorey")[0]

EXT = 0.2        # exterior wall thickness
INT_HALF = 0.05  # half of interior partition thickness

# NW Room (NW corner, bounded by N + W exterior + 2 interior partitions)
bw.add_space(
    name="NW_Room", long_name="NW private office",
    base_z=0.0, height=H,
    polygon_xy=[
        (EXT,              6.0 + INT_HALF),
        (4.625 - INT_HALF, 6.0 + INT_HALF),
        (4.625 - INT_HALF, D - EXT),
        (EXT,              D - EXT),
    ],
    storey=storey, predef="INTERNAL",
    bounding_elements=[
        ("Ext_Wall_003", "PHYSICAL", "EXTERNAL"),
        ("Ext_Wall_004", "PHYSICAL", "EXTERNAL"),
        ("Int_NW_East",  "PHYSICAL", "INTERNAL"),
        ("Int_NW_South", "PHYSICAL", "INTERNAL"),
        ("Ground_Slab",  "PHYSICAL", "EXTERNAL_EARTH"),
        ("Office_Roof",  "PHYSICAL", "EXTERNAL"),
    ],
)

# NE Room (NE corner, mirror of NW)
bw.add_space(
    name="NE_Room", long_name="NE private office",
    base_z=0.0, height=H,
    polygon_xy=[
        (15.375 + INT_HALF, 6.0 + INT_HALF),
        (W - EXT,           6.0 + INT_HALF),
        (W - EXT,           D - EXT),
        (15.375 + INT_HALF, D - EXT),
    ],
    storey=storey, predef="INTERNAL",
    bounding_elements=[
        ("Ext_Wall_003", "PHYSICAL", "EXTERNAL"),
        ("Ext_Wall_002", "PHYSICAL", "EXTERNAL"),
        ("Int_NE_West",  "PHYSICAL", "INTERNAL"),
        ("Int_NE_South", "PHYSICAL", "INTERNAL"),
        ("Ground_Slab",  "PHYSICAL", "EXTERNAL_EARTH"),
        ("Office_Roof",  "PHYSICAL", "EXTERNAL"),
    ],
)

# Shared workspace — T-shape covering the south half + middle stretch
# between the two rooms.
bw.add_space(
    name="Shared_Workspace", long_name="Open-plan shared workspace",
    base_z=0.0, height=H,
    polygon_xy=[
        (EXT,                EXT),
        (W - EXT,            EXT),
        (W - EXT,            6.0 - INT_HALF),
        (15.375 + INT_HALF,  6.0 - INT_HALF),
        (15.375 + INT_HALF,  D - EXT),
        (4.625 - INT_HALF,   D - EXT),
        (4.625 - INT_HALF,   6.0 - INT_HALF),
        (EXT,                6.0 - INT_HALF),
    ],
    storey=storey, predef="INTERNAL",
    bounding_elements=[
        ("Ext_Wall_001", "PHYSICAL", "EXTERNAL"),
        ("Ext_Wall_002", "PHYSICAL", "EXTERNAL"),
        ("Ext_Wall_003", "PHYSICAL", "EXTERNAL"),
        ("Ext_Wall_004", "PHYSICAL", "EXTERNAL"),
        ("Int_NW_East",  "PHYSICAL", "INTERNAL"),
        ("Int_NW_South", "PHYSICAL", "INTERNAL"),
        ("Int_NE_West",  "PHYSICAL", "INTERNAL"),
        ("Int_NE_South", "PHYSICAL", "INTERNAL"),
        ("Ground_Slab",  "PHYSICAL", "EXTERNAL_EARTH"),
        ("Office_Roof",  "PHYSICAL", "EXTERNAL"),
    ],
)

print("3 IfcSpaces added with full space boundaries")


# ===========================================================================
# 6. PROJECT GRID — 5 m x 5 m, extended 4 m past axes (lesson 49)
# ===========================================================================
bw.add_project_grid(
    u_spacing=5.0, total_u=3,    # A, B, C at y = 0, 5, 10
    v_spacing=5.0, total_v=5,    # 01..05 at x = 0, 5, 10, 15, 20
    extension=4.0,               # bubbles at +/- 4 m, dim chains fit at +/- 2 m
)

print("Grid added")


# ===========================================================================
# 7. QUANTITIES + STYLES + IFC SAVE
# ===========================================================================
bw.add_wall_quantities()
bw.fill_opening_overall_attrs()
bw.style_all_openings()

# IMPORTANT: save via the Bonsai OPERATOR (not ifc.write) so
# tool.Ifc.get_path() is populated — drawings need it (lesson 48).
ifc_path = os.path.join(OUTPUT_DIR, "office_10x20.ifc")
bpy.ops.bim.save_project(filepath=ifc_path)
print(f"IFC saved: {ifc_path}")


# ===========================================================================
# 8. FLOOR PLAN with dimensions
# ===========================================================================
plan_id = bd.add_drawing("PLAN_VIEW", location_hint=storey.id())

bd.set_drawing_scale_and_extents(
    drawing_id=plan_id,
    scale="1:100",
    width=32.0,       # m — covers building + 4 m grid extension + margin
    height=22.0,
    centre=(W / 2.0, D / 2.0),
)

bpy.ops.bim.activate_drawing(drawing=plan_id)

# Dim chain placement convention:
#   sub row    at  y/x = +/-1   (next-to-wall)
#   overall    at  y/x = +/-2   (outermost dim, INSIDE the grid)
#   grid       at  y/x = +/-4   (set by extension=4.0 above)
Z_PLAN = 1.0   # a touch above slab so dim curves render above plan items

# South side (below) — overall + 3 sub
bd.add_dimension((0.0,  -2.0, Z_PLAN), (W,    -2.0, Z_PLAN))
bd.add_dimension((0.0,  -1.0, Z_PLAN), (9.4,  -1.0, Z_PLAN))
bd.add_dimension((9.4,  -1.0, Z_PLAN), (10.6, -1.0, Z_PLAN))
bd.add_dimension((10.6, -1.0, Z_PLAN), (W,    -1.0, Z_PLAN))

# West side (left) — overall + 2 sub
bd.add_dimension((-2.0, 0.0, Z_PLAN), (-2.0, D,   Z_PLAN))
bd.add_dimension((-1.0, 0.0, Z_PLAN), (-1.0, 6.0, Z_PLAN))
bd.add_dimension((-1.0, 6.0, Z_PLAN), (-1.0, D,   Z_PLAN))

# North side (above) — partition x positions
bd.add_dimension((0.0,    D + 1.0, Z_PLAN), (4.625,  D + 1.0, Z_PLAN))
bd.add_dimension((4.625,  D + 1.0, Z_PLAN), (15.375, D + 1.0, Z_PLAN))
bd.add_dimension((15.375, D + 1.0, Z_PLAN), (W,      D + 1.0, Z_PLAN))

# East side (right) — same partition y split as west
bd.add_dimension((W + 1.0, 0.0, Z_PLAN), (W + 1.0, 6.0, Z_PLAN))
bd.add_dimension((W + 1.0, 6.0, Z_PLAN), (W + 1.0, D,   Z_PLAN))

# Re-save IFC with the drawing + dimensions baked in.
bpy.ops.bim.save_project(filepath=ifc_path)

# Render the SVG
svg_path = bd.generate_drawing_svg(plan_id)
print(f"Plan SVG: {svg_path}")


# ===========================================================================
# 9. FINAL AUDIT
# ===========================================================================
print("\n=== FINAL INVENTORY ===")
ifc = tool.Ifc.get()
for cls in ("IfcWall", "IfcDoor", "IfcWindow", "IfcSlab", "IfcRoof",
            "IfcSpace", "IfcGrid", "IfcGridAxis",
            "IfcRelConnectsPathElements", "IfcAnnotation"):
    print(f"  {cls}: {len(ifc.by_type(cls))}")

# Run the mandatory screenshot audit — the caller can grab one image
# per angle externally to verify nothing's broken.
bw.audit_with_screenshots(angles=("FRONT", "RIGHT", "BACK", "LEFT", "TOP", "PERSP_SE"))
print("Audit framing applied — capture each angle for visual verification.")

_override.__exit__(None, None, None)
print("\nDone.")
