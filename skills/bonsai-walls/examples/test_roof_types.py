"""Side-by-side test of 4 different roof types on identical 4x4 m bases.

Tests:
  1. MONO-PITCH (add_mono_pitch_roof — custom tessellated mesh, BIM debt)
  2. HIP        (add_hip_roof       — Bonsai BBIM parametric, ALL edges sloped)
  3. GABLE      (add_gable_roof     — Bonsai BBIM parametric, 2 edges vertical)
  4. FLAT       (add_flat_roof      — IfcSlab → IfcRoof, simplest)

Each gets its own 4x4 m base (1 storey, no openings — just walls + slab).
Buildings are spaced 6 m apart in X.

Run from Blender Scripting workspace with a 3D View open.
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

if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
if "bonsai_room_with_miters" in sys.modules:
    del sys.modules["bonsai_room_with_miters"]
import bonsai_room_with_miters as bw

import bpy
from bonsai import tool

# 3D View context override
def _find_3d_view():
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == 'VIEW_3D':
                region = next(r for r in area.regions if r.type == 'WINDOW')
                return win, area, region
    return None, None, None
_win, _area, _region = _find_3d_view()
if _area is None:
    raise RuntimeError("Open the Scripting/Layout workspace with a 3D View first.")
_override = bpy.context.temp_override(window=_win, area=_area, region=_region)
_override.__enter__()


# ---------------------------------------------------------------------------
# Bootstrap (1 storey is enough — we're not testing multi-storey here)
# ---------------------------------------------------------------------------
boot = bw.bootstrap_project(
    project_name="Roof types comparison",
)
print(f"Bootstrap done")


# ---------------------------------------------------------------------------
# Helper to build one 4x4 m base building at a given X offset
# ---------------------------------------------------------------------------
W = 4.0
D = 4.0
HEIGHT = 3.0
SPACING = 6.0   # X distance between buildings
OVERHANG = 0.3

def build_base(x_offset, name_prefix):
    """Build 4 walls + slab at (x_offset .. x_offset+W) × (0..D), z=0..HEIGHT.
    Returns the list of wall objs (for fit-walls if needed)."""
    corners = [
        (x_offset,     0),
        (x_offset + W, 0),
        (x_offset + W, D),
        (x_offset,     D),
    ]
    pairs = bw.create_room_with_mitered_corners(
        corners=corners, wall_type_name="WAL100",
        height=HEIGHT, closed=True,
        name_prefix=name_prefix + "_Wall",
    )
    walls = [obj for obj, _ in pairs]
    slab_obj, _ = bw.add_floor_slab_from_walls(
        wall_objs=walls, slab_type_name="FLR200",
        align_top_to_storey=True,
    )
    slab_obj.name = f"IfcSlab/{name_prefix}_Slab"
    return walls

import math

print("\n--- Base 1: MONO-PITCH ---")
walls1 = build_base(0 * SPACING, "Mono")
mono_angle = 15.0
bw.add_mono_pitch_roof(
    room_min=(0, 0),
    room_max=(W, D),
    wall_top_z=HEIGHT,
    slope_axis="X",
    angle_deg=mono_angle,
    thickness=0.15,
    overhang=OVERHANG,
    name="Mono_Roof",
)
# Fit B1 walls to mono-pitch slope (south + north slope, east stays high, west low)
mono_rise = math.tan(math.radians(mono_angle)) * (W + 2 * OVERHANG)
bw.fit_walls_to_mono_pitch_roof_ifc(
    wall_objs_by_side={
        "south": walls1[0], "east": walls1[1],
        "north": walls1[2], "west": walls1[3],
    },
    wall_base_height=HEIGHT,
    slope_axis="X",
    rise=mono_rise,
    room_min=(0, 0),
    room_max=(W, D),
    overhang=OVERHANG,
    base_world_z=HEIGHT,
)

print("\n--- Base 2: HIP ---")
x2 = 1 * SPACING
walls2 = build_base(x2, "Hip")
# Roof footprint = building footprint + overhang
hip_corners = [
    (x2 - OVERHANG,     -OVERHANG),
    (x2 + W + OVERHANG, -OVERHANG),
    (x2 + W + OVERHANG, D + OVERHANG),
    (x2 - OVERHANG,     D + OVERHANG),
]
hip_angle = 35.0
bw.add_hip_roof(
    footprint_xy=hip_corners,
    base_z=HEIGHT,
    angle_deg=hip_angle,
    thickness=0.15,
    name="Hip_Roof",
)
# Fit B2 walls to hip — each side clipped against its own slope face
bw.fit_walls_to_hip_roof(
    walls_by_side={
        "south": walls2[0], "east": walls2[1],
        "north": walls2[2], "west": walls2[3],
    },
    eave_z=HEIGHT,
    angle_deg=hip_angle,
    room_min=(x2, 0),
    room_max=(x2 + W, D),
    overhang=OVERHANG,
)

print("\n--- Base 3: GABLE ---")
x3 = 2 * SPACING
walls3 = build_base(x3, "Gable")
gable_corners = [
    (x3 - OVERHANG,     -OVERHANG),
    (x3 + W + OVERHANG, -OVERHANG),
    (x3 + W + OVERHANG, D + OVERHANG),
    (x3 - OVERHANG,     D + OVERHANG),
]
gable_angle = 35.0
bw.add_gable_roof(
    footprint_xy=gable_corners,
    base_z=HEIGHT,
    angle_deg=gable_angle,
    thickness=0.15,
    gable_edge_indices=(1, 3),   # E + W ends are gables; S + N slopes
    name="Gable_Roof",
)
# Fit B3 walls — Bonsai's add_roof + set_gable_roof_edge_angle on edges
# 1+3 produces a gable whose ridge runs along the Y axis at x=center.
# That means the GABLE ENDS face SOUTH + NORTH (the south + north walls
# are the ones that extend up into a triangular gable peaking at the
# ridge). The EAST + WEST walls sit under the sloped roof faces and
# stay at eave height.
bw.fit_walls_to_gable_roof(
    walls_by_side={
        "south": walls3[0], "east": walls3[1],
        "north": walls3[2], "west": walls3[3],
    },
    eave_z=HEIGHT,
    angle_deg=gable_angle,
    room_min=(x3, 0),
    room_max=(x3 + W, D),
    overhang=OVERHANG,
    gable_sides=("south", "north"),
)

print("\n--- Base 4: FLAT ---")
x4 = 3 * SPACING
walls4 = build_base(x4, "Flat")
flat_corners = [
    (x4 - OVERHANG,     -OVERHANG),
    (x4 + W + OVERHANG, -OVERHANG),
    (x4 + W + OVERHANG, D + OVERHANG),
    (x4 - OVERHANG,     D + OVERHANG),
]
bw.add_flat_roof(
    footprint_xy=flat_corners,
    base_z=HEIGHT,
    thickness=0.2,
    name="Flat_Roof",
)


# ---------------------------------------------------------------------------
# Save + report
# ---------------------------------------------------------------------------
import os
ifc_path = os.path.join(OUTPUT_DIR, "roof_types_comparison.ifc")
tool.Ifc.get().write(ifc_path)
print(f"\nSaved: {ifc_path}")

# Report counts
ifc = tool.Ifc.get()
roofs = ifc.by_type("IfcRoof")
print(f"\n{len(roofs)} IfcRoof entities:")
for r in roofs:
    print(f"  - {r.Name}  PredefinedType={r.PredefinedType}")
