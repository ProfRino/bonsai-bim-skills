"""End-to-end smoke test / template — build the room_4x6 two-storey house
from an empty IFC project, run the audit, validate against IDS, emit BCF.

Usage:
    1. Open Blender (5.x) with the Bonsai add-on enabled.
    2. (Optional) Start a new blend file: File → New → General. If a Bonsai
       project is already loaded, this script will use it — otherwise it
       will create one via bootstrap_project().
    3. Open the Scripting workspace and paste this script, or run via the
       Blender MCP `execute_blender_code` tool.
    4. Edit `OUTPUT_DIR` below to point at a writable folder.
    5. Run.

What it produces in `OUTPUT_DIR`:
    - room_4x6.ifc          ← the model (~ 190 KB, IFC4)
    - room_4x6.ids          ← the IDS spec the model is built to satisfy
    - room_4x6_report.html  ← human-readable IDS report
    - room_4x6_issues.bcfzip ← BCF issue queue (expected: 0 topics = green)

Success criterion: the BCF has 0 topics after the build. That's the
green-check state a BIM manager sees when a deliverable passes its
contract spec. If your BCF has > 0 topics, something in the skill or
the IDS author is out of sync with the build steps.

This script is the canonical "if you can run this end-to-end on a clean
install, the skill works" test. Used both as a user starting point and
as a CI smoke test.
"""
import os
import sys

# ---------------------------------------------------------------------------
# CONFIG — edit these or override via environment variables
#   $env:BONSAI_SKILLS_OUTPUT  / BONSAI_SKILLS_OUTPUT  → where artefacts go
#   $env:BONSAI_WALLS_SKILL_DIR / BONSAI_WALLS_SKILL_DIR → where the skill source lives
# ---------------------------------------------------------------------------
import os
OUTPUT_DIR = os.environ.get(
    "BONSAI_SKILLS_OUTPUT",
    os.path.expanduser(r"~/Desktop/bonsai-bim-skills-output"),
)
SKILL_DIR  = os.environ.get(
    "BONSAI_WALLS_SKILL_DIR",
    os.path.expanduser(r"~/.claude/skills/bonsai-walls"),
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Building dimensions
ROOM_W = 4.0   # x extent (metres)
ROOM_D = 6.0   # y extent
L1_HEIGHT = 3.0
L2_HEIGHT = 3.0
WALL_THICKNESS = 0.1
SLAB_THICKNESS = 0.2

# ---------------------------------------------------------------------------
# Locate the skill module
# ---------------------------------------------------------------------------
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

# Force fresh load so iterating on the skill picks up edits
if "bonsai_room_with_miters" in sys.modules:
    del sys.modules["bonsai_room_with_miters"]
import bonsai_room_with_miters as bw

import bpy
from bonsai import tool
import ifcopenshell

# ---------------------------------------------------------------------------
# Some Bonsai operators read `context.selected_objects` and
# `context.active_object` directly. When this script is run via exec() or
# right after `bim.new_project`, the global context can be missing those
# attributes. Forcing every bpy.ops.* call to see a real 3D View area
# eliminates the issue. The override is harmless when run from Blender's
# interactive Scripting workspace — that context already has a 3D View.
# ---------------------------------------------------------------------------
def _find_3d_view():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return win, area, region
    return None, None, None

_win, _area, _region = _find_3d_view()
if _area is None:
    raise RuntimeError(
        "No 3D View area found. Open Blender's default Layout / Scripting "
        "workspace before running this script."
    )

_override = bpy.context.temp_override(window=_win, area=_area, region=_region)
_override.__enter__()  # apply for the rest of this script


# ---------------------------------------------------------------------------
# 1. Bootstrap — sets up IfcProject, Site, Building, Storey, wall + slab
#    types (WAL100, FLR200), and Frame/Glass/Panel IfcSurfaceStyle items.
#    Idempotent — safe to re-run.
# ---------------------------------------------------------------------------
boot = bw.bootstrap_project(
    project_name="Room 4x6 demo",
    site_name="My Site",
    building_name="My Building",
    storey_name="My Storey",
    wall_type_name="WAL100",
    wall_thickness=WALL_THICKNESS,
    slab_type_name="FLR200",
    slab_thickness=SLAB_THICKNESS,
)
print("Bootstrapped project:", boot)
ifc = tool.Ifc.get()
storey = ifc.by_id(boot["storey"])


# ---------------------------------------------------------------------------
# 2. L1 walls — mitered corners via Bonsai's DumbWallJoiner
# ---------------------------------------------------------------------------
l1_pairs = bw.create_room_with_mitered_corners(
    corners=[(0, 0), (ROOM_W, 0), (ROOM_W, ROOM_D), (0, ROOM_D)],
    wall_type_name="WAL100",
    height=L1_HEIGHT,
    closed=True,
    name_prefix="Room4x6",
)
l1_walls = [obj for obj, _ in l1_pairs]
print(f"L1 walls created: {len(l1_walls)}")


# ---------------------------------------------------------------------------
# 3. Ground slab (top flush with z=0)
# ---------------------------------------------------------------------------
ground_slab, _ = bw.add_floor_slab_from_walls(
    wall_objs=l1_walls,
    slab_type_name="FLR200",
    align_top_to_storey=True,
)
ground_slab.name = "IfcSlab/Slab"
tool.Ifc.get_entity(ground_slab).Name = "Slab"
print("Ground slab created")


# ---------------------------------------------------------------------------
# 4. L1 door + parametric windows on every side (centered to avoid
#    door / corner overlap)
# ---------------------------------------------------------------------------
# South-wall door at x=1.55 (so it spans 1.55-2.45 = centered on x=2)
south_l1, east_l1, north_l1, west_l1 = l1_walls
door_l1, _ = bw.add_door_to_wall(
    wall_obj=south_l1, position=(1.55, 0.0, 0.0),
    door_type_name=None,  # use first IfcDoorType in project (DT01)
)
door_l1.name = "IfcDoor/Door.002"
tool.Ifc.get_entity(door_l1).Name = "Door.002"

# L1 windows — one per remaining wall, BBIM parametric, auto-styled with
# project Frame + Glass
windows_l1_specs = [
    ("L1_East",  east_l1,  (ROOM_W, 4.5, 0.9), 0.9, 1.2),
    ("L1_North", north_l1, (1.55, ROOM_D, 0.9), 0.9, 1.2),
    ("L1_West",  west_l1,  (0.0,  3.9, 0.9), 1.8, 1.2),  # wider centered
]
for name, wall, pos, w, h in windows_l1_specs:
    bw.add_parametric_window_to_wall(
        wall_obj=wall, target=pos, width=w, height=h, name=name,
    )
print("L1 door + 3 windows placed")


# ---------------------------------------------------------------------------
# 5. Upper floor slab (between L1 and L2)
# ---------------------------------------------------------------------------
upper_floor, _ = bw.add_floor_slab_from_walls(
    wall_objs=l1_walls,
    slab_type_name="FLR200",
    align_top_to_storey=False,  # bottom of slab at top of L1 walls
)
bw.set_world_location(upper_floor, (0.0, 0.0, L1_HEIGHT))
upper_floor.name = "IfcSlab/UpperFloor"
tool.Ifc.get_entity(upper_floor).Name = "UpperFloor"
print("Upper floor slab placed")


# ---------------------------------------------------------------------------
# 6. L2 walls at z=L1_HEIGHT+SLAB_THICKNESS, with name prefix L2_Wall
# ---------------------------------------------------------------------------
l2_base = L1_HEIGHT + SLAB_THICKNESS
l2_pairs = bw.create_room_with_mitered_corners(
    corners=[(0, 0), (ROOM_W, 0), (ROOM_W, ROOM_D), (0, ROOM_D)],
    wall_type_name="WAL100",
    height=L2_HEIGHT,
    closed=True,
    name_prefix="L2_Wall",
)
l2_walls = [obj for obj, _ in l2_pairs]
# Shift L2 walls up to sit on the upper-floor slab
for w in l2_walls:
    bw.set_world_location(w, (w.location.x, w.location.y, l2_base))
print(f"L2 walls created (z base = {l2_base})")


# ---------------------------------------------------------------------------
# 7. L2 windows (no door upstairs)
# ---------------------------------------------------------------------------
south_l2, east_l2, north_l2, west_l2 = l2_walls
l2_sill = l2_base + 0.9
windows_l2_specs = [
    ("L2_South", south_l2, (1.55, 0.0,    l2_sill), 0.9, 1.2),
    ("L2_East",  east_l2,  (ROOM_W, 3.45, l2_sill), 0.9, 1.2),
    ("L2_North", north_l2, (1.55, ROOM_D, l2_sill), 0.9, 1.2),
    ("L2_West",  west_l2,  (0.0,  3.9,    l2_sill), 1.8, 1.2),
]
for name, wall, pos, w, h in windows_l2_specs:
    bw.add_parametric_window_to_wall(
        wall_obj=wall, target=pos, width=w, height=h, name=name,
    )
print("L2: 4 parametric windows placed")


# ---------------------------------------------------------------------------
# 8. Mono-pitch roof at top of L2 walls
# ---------------------------------------------------------------------------
roof_top = l2_base + L2_HEIGHT
bw.add_mono_pitch_roof(
    room_min=(0.0, 0.0),
    room_max=(ROOM_W, ROOM_D),
    wall_top_z=roof_top,
    slope_axis="X",
    angle_deg=14.0,
    thickness=0.15,
    overhang=0.3,
    name="MonoPitchRoof",
)
print("Mono-pitch roof created")


# ---------------------------------------------------------------------------
# 9. Fit L2 walls to roof underside — uses proper IFC IfcBooleanClippingResult,
#    survives roundtrip + every wall regeneration. ALL 4 walls clipped to
#    the slope plane (low side automatically reaches roof underside via the
#    same clip).
# ---------------------------------------------------------------------------
import math
rise = math.tan(math.radians(14.0)) * (ROOM_W + 2 * 0.3)
bw.fit_walls_to_mono_pitch_roof_ifc(
    wall_objs_by_side={
        "south": south_l2, "east": east_l2,
        "north": north_l2, "west": west_l2,
    },
    wall_base_height=L2_HEIGHT,
    slope_axis="X",
    rise=rise,
    room_min=(0.0, 0.0),
    room_max=(ROOM_W, ROOM_D),
    overhang=0.3,
)
print("Walls fitted to mono-pitch roof (IFC clipping)")


# ---------------------------------------------------------------------------
# 10. IfcSpace per storey + boundaries
# ---------------------------------------------------------------------------
interior = [
    (WALL_THICKNESS, WALL_THICKNESS),
    (ROOM_W - WALL_THICKNESS, WALL_THICKNESS),
    (ROOM_W - WALL_THICKNESS, ROOM_D - WALL_THICKNESS),
    (WALL_THICKNESS, ROOM_D - WALL_THICKNESS),
]
bw.add_space(
    name="L1_Room", long_name="Ground floor living room",
    base_z=0.0, height=L1_HEIGHT, polygon_xy=interior,
    storey=storey, predef="INTERNAL",
    bounding_elements=[
        ("Room4x6_001", "PHYSICAL", "EXTERNAL"),
        ("Room4x6_002", "PHYSICAL", "EXTERNAL"),
        ("Room4x6_003", "PHYSICAL", "EXTERNAL"),
        ("Room4x6_004", "PHYSICAL", "EXTERNAL"),
        ("Slab",         "PHYSICAL", "EXTERNAL_EARTH"),
        ("UpperFloor",   "PHYSICAL", "INTERNAL"),
    ],
)
bw.add_space(
    name="L2_Room", long_name="Upper floor bedroom",
    base_z=l2_base, height=L2_HEIGHT, polygon_xy=interior,
    storey=storey, predef="INTERNAL",
    bounding_elements=[
        ("L2_Wall_001", "PHYSICAL", "EXTERNAL"),
        ("L2_Wall_002", "PHYSICAL", "EXTERNAL"),
        ("L2_Wall_003", "PHYSICAL", "EXTERNAL"),
        ("L2_Wall_004", "PHYSICAL", "EXTERNAL"),
        ("UpperFloor",   "PHYSICAL", "INTERNAL"),
        ("MonoPitchRoof", "PHYSICAL", "EXTERNAL"),
    ],
)
print("2 IfcSpaces created with boundaries")


# ---------------------------------------------------------------------------
# 11. Close IDS data gaps — wall quantities + opening overall sizes
# ---------------------------------------------------------------------------
bw.add_wall_quantities()
bw.fill_opening_overall_attrs()
print("Qto_WallBaseQuantities + OverallWidth/Height attrs filled")


# ---------------------------------------------------------------------------
# 12. Save IFC + IDS + HTML report + BCF
# ---------------------------------------------------------------------------
os.makedirs(OUTPUT_DIR, exist_ok=True)
ifc_path  = os.path.join(OUTPUT_DIR, "room_4x6.ifc")
ids_path  = os.path.join(OUTPUT_DIR, "room_4x6.ids")
html_path = os.path.join(OUTPUT_DIR, "room_4x6_report.html")
bcf_path  = os.path.join(OUTPUT_DIR, "room_4x6_issues.bcfzip")

ifc.write(ifc_path)
print(f"IFC saved: {ifc_path}")

bw.author_room_ids(
    output_path=ids_path,
    title="Room 4x6 BIM quality spec",
    author=os.environ.get("BONSAI_SKILLS_AUTHOR", "your-name-here"),
    version="1.0",
    milestone="As-built",
)
print(f"IDS authored: {ids_path}")

result = bw.validate_against_ids(ifc, ids_path, html_report_path=html_path)
print(f"Validation: {result['specs']}")
print(f"Overall PASS: {result['overall']}")
print(f"HTML report: {html_path}")

# Emit BCF — should have 0 topics if the build is clean
import ifctester, ifctester.ids, ifctester.reporter, zipfile
ids = ifctester.ids.open(ids_path)
ids.validate(ifc)
bcf_rep = ifctester.reporter.Bcf(ids)
bcf_rep.report()
bcf_rep.to_file(bcf_path)

with zipfile.ZipFile(bcf_path) as z:
    topics = set(n.split("/")[0] for n in z.namelist() if "/" in n)

print(f"BCF written: {bcf_path}")
print(f"BCF topics: {len(topics)}  (expected: 0)")
print()
print("================================================================")
if result["overall"] and len(topics) == 0:
    print("  SMOKE TEST PASSED ✓")
    print(f"  4 artifacts produced in {OUTPUT_DIR}")
else:
    print("  SMOKE TEST FAILED ✗")
    print(f"  Open {html_path} or {bcf_path} for details")
print("================================================================")
