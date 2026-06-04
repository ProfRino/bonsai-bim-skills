# Changelog

All notable changes to this project will be documented in this file.

The format is loosely based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.2.0] — 2026-06-04

Repo restructure into 7 focused skills (was 2). No helper logic changes —
this is a pure repackaging release. The Python module renames + folder
restructure are the change.

### Changed (breaking, with backward-compat shim)

- **Renamed** `bonsai_room_with_miters.py` → `bonsai_bim_helpers.py`.
  The old name was a historical artefact from when the module only
  handled rooms-with-mitered-corners; it's now ~3500 lines spanning the
  full BIM authoring surface (walls + openings + roofs + stairs +
  spaces + grid + project setup + audit + IDS).

  **Backward-compat shim** — each skill folder also ships a tiny
  `bonsai_room_with_miters.py` that does `from bonsai_bim_helpers
  import *`, so existing user code keeps working.

- **Split `bonsai-walls` (monolithic) into 6 focused skills:**
  - `bonsai-walls` — walls + slabs + mitered corners + interior
    partition rules (auto-clip overshoot + same-thickness sibling
    auto-connect).
  - `bonsai-openings` — doors + windows + equal-spacing rule + Frame /
    Glass / Panel styling + `OverallWidth/Height` filler.
  - `bonsai-roofs` — 4 roof topologies + IFC-correct wall fits.
  - `bonsai-stairs` — parametric stairs + railings + stairwell voids.
  - `bonsai-spaces-grid` — `IfcSpace` + `IfcGrid` with
    `extension` parameter.
  - `bonsai-project-setup` — `bootstrap_project` + `add_storey` + audit
    screenshots + Qto fillers + IDS + BCF.

  Each skill has a focused SKILL.md (was one 30 KB SKILL.md covering
  everything).

- **Moved `examples/` from inside the skill folder up to repo root.**
  Now `examples/build_*.py` instead of `skills/bonsai-walls/examples/`.

- **Renamed import in examples** from
  `import bonsai_room_with_miters as bw` to
  `import bonsai_bim_helpers as bw`. The backward-compat shim means
  third-party scripts using the old name still work.

### Added

- `canonical/bonsai_bim_helpers.py` — the SINGLE source of truth for
  the helper module. The 6 element-related skill folders carry copies
  for self-containment.
- `tools/sync_modules.py` — copies `canonical/bonsai_bim_helpers.py`
  into every element-related skill folder. Run after editing the
  canonical module. Supports `--check` for CI drift detection.
- `INSTALL.md` section 7b — "(Developers only) Clone the Bonsai /
  IfcOpenShell source" — promoted from optional sidebar to a
  first-class step for anyone writing new helpers, with a table of key
  folders to bookmark.

### Same as 0.1.0

All helper behaviour, all 49+ baked-in rules, the GPL-3.0 license, the
GPL-3-aligned MCP recommendations, the screenshot audit protocol, IDS
+ BCF integration. Nothing functional changed — just packaging.

---

## [0.1.0] — 2026-06-04

First public release. Two Claude Code skills covering programmatic IFC
authoring + 2D drawings in Blender + Bonsai.

Verified MCP stack for v0.1.0:
- [BlenderMCP](https://github.com/ahujasid/blender-mcp) — provides
  `execute_blender_code` (the only MCP tool the skills actually call).
- [ifc-bonsai-mcp](https://github.com/Show2Instruct/ifc-bonsai-mcp) —
  installed alongside; exposes `mcp__bonsai-ifc__*` high-level tools
  used by the agent for ad-hoc work outside the skill's scope. Skills
  themselves don't depend on it.

### Added

**`bonsai-walls` skill** (`bonsai_room_with_miters.py`, ~3500 lines):

- `bootstrap_project(...)` — full one-shot project setup: IfcProject +
  Site/Building/Storey + dual `IfcWallType` (WAL200 exterior 200 mm +
  WAL100 interior 100 mm sharing one Concrete IfcMaterial) + IfcSlabType
  (FLR200) + Frame / Glass / Panel `IfcSurfaceStyle` items linked to
  Blender materials via `BIMStyleProperties.ifc_definition_id`.
- `create_room_with_mitered_corners(corners, wall_type_name, height, closed)` —
  proper LAYER2 walls + `IfcRelConnectsPathElements` miters via
  `DumbWallGenerator.create_wall_from_2_points` +
  `DumbWallJoiner.connect`. Not the overlapping butt joins of
  ifc-bonsai-mcp's `create_polyline_walls`.
- `add_floor_slab_from_walls(...)` — DumbSlabGenerator + Z-translate so
  the slab top sits at Z=0 (walls rest on top, no overlap).
- `add_interior_wall(start_xy, end_xy, height, ..., avoid_existing_walls=True,
  connect_to_touching=True)` — interior partition with two HARD rules
  baked in: (a) auto-clip endpoints to the inner face of any thicker
  existing wall (no knife-through-wall overshoot); (b) auto-connect to
  same-thickness siblings via `DumbWallJoiner` for proper L-corner
  miters; partition-to-exterior junctions stay as clean butt joints
  (Bonsai's `connect_wall` would otherwise TRIM the exterior wall).
- `add_parametric_window_to_wall(...)` + `add_parametric_door_to_wall(...)` —
  real `BBIM_Window` / `BBIM_Door` occurrences (editable per-occurrence
  in Bonsai sidebar), with `FilledOpeningGenerator` voids + fills,
  IFC placement sync (critical for roundtrip), and auto-styling against
  project Frame / Glass / Panel surface styles.
- `add_equally_spaced_windows_to_wall(wall, count, ..., segment=None)` —
  DEFAULT skill rule: equal-spacing formula `gap = (L − N·W) / (N + 1)`
  with optional segment for walls split by a centred door.
- `add_mono_pitch_roof` + `add_hip_roof` + `add_gable_roof` +
  `add_flat_roof` — 4 roof topologies. Hip / gable / flat are real
  BBIM parametric; mono-pitch is a tessellated `IfcRoof` (Bonsai's
  parametric `add_roof` only supports HIP / GABLE — documented BIM debt).
- `fit_walls_to_hip_roof` + `fit_walls_to_gable_roof` +
  `fit_walls_to_mono_pitch_roof_ifc` — IFC-correct wall fits via
  `IfcBooleanClippingResult` + `IfcHalfSpaceSolid` (single
  `add_boolean(DIFFERENCE, [hs1, hs2, ...])` call for gable ends).
  No Blender-only Boolean modifiers.
- `add_parametric_stair(...)` — full `BBIM_Stair` parametric, with
  `top_slab_depth` + `has_top_nib=True` for clean upper-slab integration.
- `add_stairwell_opening_for_stair(...)` — opening fitted to the actual
  last tread back edge, NOT stair bbox max (bbox extends past last tread
  because of the top nib landing).
- `add_parametric_railing(...)` — `IfcRailing` + `BBIM_Railing` pset
  along a polyline; correct height conventions (1.1 m guard / 0.9 m
  handrail).
- `add_space(...)` — `IfcSpace` aggregated into a storey (NOT contained;
  IfcSpace requires `IfcRelAggregates`) with optional bounding elements
  → `IfcRelSpaceBoundary` per wall / slab / roof, and
  `Qto_SpaceBaseQuantities` (NetFloorArea, NetVolume, Height,
  GrossPerimeter) computed from the polygon.
- `add_project_grid(u_spacing, total_u, v_spacing, total_v, extension)` —
  `IfcGrid` + `IfcGridAxis` entries authored DIRECTLY via
  `ifcopenshell.api.grid.create_grid_axis` + `create_axis_curve` with
  the desired bubble extension baked in from the start. Bypasses
  Bonsai's `bim.add_grid` operator (which hardcodes ±2 m and ignores
  post-hoc axis edits).
- `add_storey(name, elevation, building)` — additional
  `IfcBuildingStorey` aggregated into the building.
- `add_wall_quantities()` + `fill_opening_overall_attrs()` —
  `Qto_WallBaseQuantities` + `IfcDoor.OverallWidth/Height` /
  `IfcWindow.OverallWidth/Height` schema attribute fillers. Bonsai
  doesn't auto-populate these.
- `style_all_openings(...)` — one-call helper that styles every
  un-styled door + window with project Frame / Glass / Panel surface
  styles in one pass.
- `audit_with_screenshots(angles=("FRONT","RIGHT","BACK","LEFT","TOP","PERSP_SE"))` —
  MANDATORY post-change audit cycle; frames the viewport for each
  angle so the caller can grab a screenshot and visually verify
  against a checklist.
- `author_room_ids(...)` + `validate_against_ids(...)` — IDS authoring
  + validation via `ifctester` for two-layer audit
  (visual + data).

**`bonsai-drawings` skill** (`bonsai_drawings.py`, ~300 lines):

- `add_drawing(target_view, location_hint, cursor_location)` — wraps
  `bim.add_drawing` for PLAN_VIEW / ELEVATION_VIEW / SECTION_VIEW /
  REFLECTED_PLAN_VIEW / MODEL_VIEW with defensive
  `_require_saved_ifc_path()` check (drawings require
  `bpy.ops.bim.save_project` to set `tool.Ifc.get_path()`).
- `set_drawing_scale_and_extents(drawing_id, scale, width, height, centre)` —
  configure diagram scale ("1:50" / "1:100" / "1:200") + camera
  coverage + centre.
- `add_dimension(p1, p2)` — linear `IfcAnnotation` curve with
  auto-computed metre label. Single span; multi-point chains DON'T
  work (arrows clash at joints).
- `generate_drawing_svg(drawing_id)` — renders the SVG via
  `bim.create_drawing` and returns its on-disk path.
- `add_standard_drawings(...)` + `render_all_drawings(...)` —
  convenience: 1 Plan + 4 Elevations (N/S/E/W) + 1 Section in one call.

### Hard rules baked in (49 lessons)

See [`docs/lessons-learned.md`](docs/lessons-learned.md) for the full
list. Highlights of the rules now ENFORCED automatically by the helpers:

- Windows are equally spaced and centred on the wall by default.
- Interior partitions never overshoot into thicker exterior walls
  (auto-clipped to inner faces).
- Interior partitions get `IfcRelConnectsPathElements` only to
  SAME-thickness siblings (cross-thickness connection trims the
  exterior wall — disastrous).
- Grid axes extend 4 m past the outermost axes by default so bubbles
  don't overlap the standard ±2 m dimension chain.
- Drawings require `bpy.ops.bim.save_project(filepath=...)` before
  creation (sets `tool.Ifc.get_path()`); plain `ifc.write` doesn't
  count.
- Multi-angle screenshot audit is MANDATORY after every change.
