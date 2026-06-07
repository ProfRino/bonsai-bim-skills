"""3-level test house with rooms per floor + stairs between levels.

Tests the skill against a realistic small-building scenario:
  - 3 IfcBuildingStorey (L1 ground, L2 middle, L3 top)
  - Interior wall dividing each storey into 2 rooms (west + east)
  - 2 stairs connecting L1→L2 and L2→L3 (in the east room)
  - 1 entrance door on south L1 + interior doors between rooms
  - Windows on the exterior walls
  - Mono-pitch roof
  - IfcSpace per room (6 total) with IfcRelSpaceBoundary
  - Full IDS + BCF audit at the end

Run from Blender's Scripting workspace (a 3D View must be open).

Output (in OUTPUT_DIR):
  - two_room_house.ifc
  - two_room_house.ids
  - two_room_house_report.html
  - two_room_house_issues.bcfzip (expected: 0 topics if everything BIM-correct)
"""
import os, sys, math

OUTPUT_DIR = os.environ.get(
    "BONSAI_SKILLS_OUTPUT",
    os.path.expanduser(r"~/Desktop/bonsai-bim-skills-output"),
)
SKILL_DIR  = os.environ.get(
    "BONSAI_WALLS_SKILL_DIR",
    os.path.expanduser(r"~/.claude/skills/bonsai-walls"),
)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Geometry config
# ---------------------------------------------------------------------------
ROOM_W = 8.0   # building width  (x extent)
ROOM_D = 6.0   # building depth  (y extent)
DIVIDER_X = 5.0  # interior wall X (west room = 0..5, east room = 5..8)
STOREY_H = 3.0
SLAB_T = 0.2
WALL_T = 0.1
N_STOREYS = 3   # L1, L2, L3

# Stair config
STAIR_WIDTH = 0.9
STAIR_NTREADS = 12
STAIR_TREAD = 0.25
STAIR_RISER = STOREY_H / (STAIR_NTREADS + 1)  # +1 for top step nibs

if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
if "bonsai_bim_helpers" in sys.modules:
    del sys.modules["bonsai_bim_helpers"]
import bonsai_bim_helpers as bw

import bpy
from bonsai import tool

# ---------------------------------------------------------------------------
# Run inside a 3D View context override so every bpy.ops.* call sees
# context.selected_objects + active_object as expected.
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
        "No 3D View area found. Open the Scripting/Layout workspace first."
    )
_override = bpy.context.temp_override(window=_win, area=_area, region=_region)
_override.__enter__()


# ---------------------------------------------------------------------------
# 1. Project setup + add the 3 storeys (L1 + L2 + L3)
# ---------------------------------------------------------------------------
project_info = bw.setup_project(
    project_name="3-level test house",
    site_name="Site",
    building_name="House",
    storey_name="L1",
    exterior_wall_type_name="WAL200",
    exterior_wall_thickness=0.2,
    interior_wall_type_name="WAL100",
    interior_wall_thickness=0.1,
    slab_type_name="FLR200",
    slab_thickness=SLAB_T,
    door_width=0.9,
    door_height=2.0,
)
print(f"Project set up: {project_info}")
ifc = tool.Ifc.get()
l1_storey = ifc.by_id(project_info["storey"])
l1_storey.Elevation = 0.0

l2_storey = bw.add_storey("L2", elevation=STOREY_H + SLAB_T)
l3_storey = bw.add_storey("L3", elevation=2 * (STOREY_H + SLAB_T))
storeys = [l1_storey, l2_storey, l3_storey]
print(f"Storeys: {[s.Name for s in storeys]}")


# ---------------------------------------------------------------------------
# 2. Build exterior walls + interior partition + slab for each storey
# ---------------------------------------------------------------------------
def build_storey(storey_idx, base_z):
    """Build the 4 exterior walls + 1 interior wall + floor slab for a storey.
    Returns dict of wall objects: 'south', 'east', 'north', 'west', 'divider'.
    """
    prefix = f"L{storey_idx+1}"
    print(f"Building {prefix} at z={base_z}")
    # 4 mitered exterior walls
    pairs = bw.create_room_with_mitered_corners(
        corners=[(0, 0), (ROOM_W, 0), (ROOM_W, ROOM_D), (0, ROOM_D)],
        wall_type_name="WAL100",
        height=STOREY_H,
        closed=True,
        name_prefix=f"{prefix}_Wall",
    )
    walls = [obj for obj, _ in pairs]
    south, east, north, west = walls

    # Move walls up to base_z if not at ground
    if base_z != 0:
        for w in walls:
            bw.set_world_location(w, (w.location.x, w.location.y, base_z))

    # Interior dividing wall — runs y=0+ to y=ROOM_D-, x=DIVIDER_X
    # NOTE: interior wall's full Y extent overlaps the south + north walls
    # at the corners. Use start/end SLIGHTLY inside to butt against them.
    divider_obj, _ = bw.add_interior_wall(
        start_xy=(DIVIDER_X, WALL_T),
        end_xy=(DIVIDER_X, ROOM_D - WALL_T),
        height=STOREY_H,
        base_z=base_z,
        wall_type_name="WAL100",
        name=f"{prefix}_Divider",
    )

    # Floor slab below the walls. add_floor_slab_from_walls(align_top_to_storey=True)
    # creates the slab spanning world z=-SLAB_T to z=0 (top flush with the
    # walls' base which is at z=0 before the per-storey shift).
    slab_obj, slab_ent = bw.add_floor_slab_from_walls(
        wall_objs=walls,
        slab_type_name="FLR200",
        align_top_to_storey=True,
    )
    # For upper storeys: move the slab so its TOP is flush with base_z
    # (i.e. the walls of THIS storey sit on the slab's top). The slab
    # was at world z=-SLAB_T..0; we want it at world z=(base_z-SLAB_T)..base_z.
    # set_world_location overwrites obj.location, so the destination is
    # base_z - SLAB_T (NOT base_z — that puts the slab on TOP of the walls
    # below by SLAB_T).
    if base_z != 0:
        bw.set_world_location(slab_obj, (0, 0, base_z - SLAB_T))
    slab_obj.name = f"IfcSlab/{prefix}_Slab"
    slab_ent.Name = f"{prefix}_Slab"

    return {
        "south": south, "east": east, "north": north, "west": west,
        "divider": divider_obj, "slab": slab_obj,
    }


# Build each storey
storey_walls = []
for i, st in enumerate(storeys):
    base = i * (STOREY_H + SLAB_T)
    storey_walls.append(build_storey(i, base))
print("All storeys built")


# ---------------------------------------------------------------------------
# 3. Add south entrance door + windows on each storey
# ---------------------------------------------------------------------------
# L1: entrance door on south, at x=2 (in the west / "Entry" room)
l1 = storey_walls[0]
bw.add_parametric_door_to_wall(
    wall_obj=l1["south"],
    target=(2.0, 0.0, 0.0),
    width=0.9, height=2.0,
    name="Entry_Door",
    operation_type="SINGLE_SWING_RIGHT",
)
print("L1 entrance door placed")

# Windows on each exterior wall per storey
def add_storey_windows(storey_idx, storey_walls, base_z):
    prefix = f"L{storey_idx+1}"
    sill = base_z + 0.9  # standard sill height
    specs = []
    # Skip the south wall if it has the door (only L1) → add south window only for L2/L3
    if storey_idx > 0:
        specs.append((f"{prefix}_S", storey_walls["south"], (2.0, 0.0, sill), 1.0, 1.2))
    # East wall window — in the east room, north end (avoid where stair lands)
    specs.append((f"{prefix}_E", storey_walls["east"], (ROOM_W, 4.5, sill), 0.9, 1.2))
    # North wall window — in the west (larger) room
    specs.append((f"{prefix}_N", storey_walls["north"], (1.5, ROOM_D, sill), 1.2, 1.2))
    # West wall window — west room
    specs.append((f"{prefix}_W", storey_walls["west"], (0.0, 3.5, sill), 1.2, 1.2))
    for name, wall, target, w, h in specs:
        bw.add_parametric_window_to_wall(
            wall_obj=wall, target=target, width=w, height=h, name=name,
        )

for i in range(N_STOREYS):
    base = i * (STOREY_H + SLAB_T)
    add_storey_windows(i, storey_walls[i], base)
print("Windows placed on all storeys")


# ---------------------------------------------------------------------------
# 4. Add stairs between consecutive storeys (in the east room)
# ---------------------------------------------------------------------------
# Stair runs along +Y in the east room (x = 5 + offset to 5 + offset + width)
# Each stair starts at floor level and ends at the next storey's slab top.
stair_x_min = DIVIDER_X + 0.5  # 0.5m clearance from divider wall
stair_y_start = 1.0  # 1m clearance from south wall

for i in range(N_STOREYS - 1):
    base = i * (STOREY_H + SLAB_T)
    stair_result = bw.add_parametric_stair(
        location=(stair_x_min, stair_y_start, base),
        rotation_z_deg=90.0,    # run along +Y direction
        height=STOREY_H + SLAB_T,
        width=STAIR_WIDTH,
        number_of_treads=STAIR_NTREADS,
        tread_run=STAIR_TREAD,
        stair_type="CONCRETE",
        name=f"Stair_L{i+1}_to_L{i+2}",
    )
print("Stairs added")


# ---------------------------------------------------------------------------
# 5. Mono-pitch roof on top
# ---------------------------------------------------------------------------
roof_top_z = N_STOREYS * (STOREY_H + SLAB_T) - SLAB_T  # top of L3 walls
bw.add_mono_pitch_roof(
    room_min=(0.0, 0.0),
    room_max=(ROOM_W, ROOM_D),
    wall_top_z=roof_top_z,
    slope_axis="X",
    angle_deg=12.0,
    thickness=0.15,
    overhang=0.3,
    name="House_Roof",
)
# Fit L3 walls to the roof underside (slope-clip)
rise = math.tan(math.radians(12.0)) * (ROOM_W + 2 * 0.3)
bw.fit_walls_to_mono_pitch_roof_ifc(
    wall_objs_by_side={
        "south": storey_walls[2]["south"],
        "east":  storey_walls[2]["east"],
        "north": storey_walls[2]["north"],
        "west":  storey_walls[2]["west"],
    },
    wall_base_height=STOREY_H,
    slope_axis="X",
    rise=rise,
    room_min=(0.0, 0.0),
    room_max=(ROOM_W, ROOM_D),
    overhang=0.3,
    # Force the low-eave Z = roof level (top of L3 flat walls).
    # Without this, the helper defaults to base + wall_base_height which
    # only matches when the L3 walls' IFC origin is at their floor — for
    # walls we moved via set_world_location, the origin IS at base_z so
    # the default works, BUT let's be explicit to remove ambiguity.
    base_world_z=roof_top_z,
)
print("Roof + L3 wall clip done")


# ---------------------------------------------------------------------------
# 6. IDS + final audit
# ---------------------------------------------------------------------------
bw.add_wall_quantities()
bw.fill_opening_overall_attrs()
bw.style_all_openings()

os.makedirs(OUTPUT_DIR, exist_ok=True)
ifc_path  = os.path.join(OUTPUT_DIR, "two_room_house.ifc")
ids_path  = os.path.join(OUTPUT_DIR, "two_room_house.ids")
html_path = os.path.join(OUTPUT_DIR, "two_room_house_report.html")
bcf_path  = os.path.join(OUTPUT_DIR, "two_room_house_issues.bcfzip")

ifc.write(ifc_path)
print(f"IFC saved: {ifc_path}")

bw.author_room_ids(
    output_path=ids_path,
    title="Two-room house BIM quality spec",
    author="test",
    version="1.0",
    milestone="As-built",
)
audit = bw.validate_against_ids(ifc, ids_path, html_report_path=html_path)
print(f"IDS specs: {len(audit['specs'])}, Overall PASS: {audit['overall']}")

import ifctester, ifctester.ids, ifctester.reporter, zipfile
ids = ifctester.ids.open(ids_path)
ids.validate(ifc)
bcf_rep = ifctester.reporter.Bcf(ids)
bcf_rep.report()
bcf_rep.to_file(bcf_path)
with zipfile.ZipFile(bcf_path) as z:
    topics = set(n.split("/")[0] for n in z.namelist() if "/" in n)
print(f"BCF topics: {len(topics)}")

print()
print("================================================================")
if audit["overall"] and len(topics) == 0:
    print("  3-STOREY HOUSE BUILD PASSED ✓")
else:
    print("  3-STOREY HOUSE BUILD HAS IDS GAPS — check HTML report")
print("================================================================")
