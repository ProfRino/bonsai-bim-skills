# Architecture

High-level explanation of how these skills are organised, what assumes
what, and where to extend.

## Skills as Claude Code modules

A "skill" in Claude Code is a directory under `~/.claude/skills/<name>/`
containing:

- `SKILL.md` — Markdown manifest with YAML front matter that declares
  trigger words, scope, and inline usage docs.
- One or more Python modules that the skill loads via `sys.path.insert`
  inside `execute_blender_code` calls.
- Optionally an `examples/` subfolder with standalone reproducible
  scripts.

Claude Code parses the YAML front matter to pick which skill to load
when a user prompt matches its trigger words. The `SKILL.md` body is
included in the agent's context for the duration of the task.

## Two skills, one repo

| Skill | Source module | Scope |
|---|---|---|
| `bonsai-walls` | `bonsai_room_with_miters.py` | 3D authoring — walls, slabs, openings, fillings, roofs, fits, stairs, railings, spaces, grids, quantities, IDS validation |
| `bonsai-drawings` | `bonsai_drawings.py` | 2D output — drawings (IfcAnnotation cameras), camera setup, dimension annotations, SVG rendering |

The walls skill is the "model" half. The drawings skill is the "output"
half. The split keeps each skill's `SKILL.md` digestible and lets the
agent load only what's needed for a given task.

Both skills can be active at the same time (creating a model + plotting
it in one session); they share no state beyond the IFC file itself.

## Layering inside `bonsai_room_with_miters.py`

The module has ~3500 lines organised in functional groups:

```
1.  Imports + module-level helpers
    _setup_generator(...)
2.  Walls + slabs
    create_room_with_mitered_corners(...)
    add_floor_slab_from_walls(...)
    add_interior_wall(...)
       _adjust_interior_wall_endpoints(...)
       _connect_interior_wall_to_touching_walls(...)
3.  Openings + fillings
    add_door_to_wall(...)
    add_window_to_wall(...)
    add_parametric_window_to_wall(...)
    add_equally_spaced_windows_to_wall(...)
    apply_window_styles(...)
    add_parametric_door_to_wall(...)
    apply_door_styles(...)
    style_all_openings(...)
4.  Wall regeneration
    regen_all_walls(...)
    _add_filling_to_wall(...)
5.  Roofs (4 topologies)
    add_hip_roof(...)
    add_gable_roof(...)
    add_flat_roof(...)
    add_mono_pitch_roof(...)
6.  Wall fits to roofs
    set_world_location(...)
    _clip_wall_with_planes(...)
    _clip_wall_above_world_plane(...)
    fit_walls_to_hip_roof(...)
    fit_walls_to_gable_roof(...)
    fit_walls_to_mono_pitch_roof_ifc(...)
    fit_walls_to_mono_pitch_roof(...)
7.  Stairs + railings
    add_stairwell_opening_for_stair(...)
    add_parametric_stair(...)
    add_parametric_railing(...)
8.  Cleanup
    cleanup_orphan_walls(...)
9.  Spaces + storeys
    add_space(...)
    add_project_grid(...)
    extend_grid_axes(...)
    add_storey(...)
10. Doors (parametric + type duplication)
    duplicate_door_type(...)
    create_parametric_door_type(...)
11. Project setup + audit
    setup_project(...)
    add_wall_quantities(...)
    fill_opening_overall_attrs(...)
    audit_with_screenshots(...)
12. IDS + BCF
    author_room_ids(...)
    validate_against_ids(...)
```

(See the module source for exact ordering and helper docstrings.)

Higher-numbered groups depend on lower-numbered ones. The project setup
is last because it composes most of the others into a one-shot project
initialisation.

## Convention reference

The skills share these conventions across all helpers:

| Element | Default name | Default thickness / size |
|---|---|---|
| Exterior wall | `WAL200` | 200 mm |
| Interior partition | `WAL100` | 100 mm |
| Slab | `FLR200` | 200 mm |
| Door type | (none — use `add_parametric_door_to_wall` directly) | 0.9 × 2.0 m |
| Main entrance | (none — same helper) | 1.2 × 2.1 m |
| Window | (none — use `add_parametric_window_to_wall` directly) | 0.9 × 1.2 m, sill 0.9 m |
| Floor-to-floor height | n/a | 3.0 m |
| Project grid | `Grid` | 5 × 5 m, 4 m extension |

These come from `setup_project(...)` defaults. Pass kwargs to
override.

## What this skill does NOT cover

- **MEP** (`IfcPipe*`, `IfcDuct*`, etc.) — Bonsai has tooling for it
  but no helpers are baked in.
- **Foundations + structural** (footings, columns, beams,
  reinforcement) — no helpers yet.
- **Sheet layout + title blocks** — `bim.add_sheet` exists in Bonsai
  but isn't wrapped here.
- **Multi-building / site context** — `add_storey` adds storeys to
  one building; `IfcSite` + `IfcGeographicElement` aren't wrapped.
- **Schedule / quantity takeoff export** to CSV / COBie — quantities
  are populated on elements but extraction helpers aren't here.

These are all natural extensions — see the Contributing section of
the main README.

## Extending: how to add a new helper

1. **Decide which skill** it belongs in (model authoring → walls;
   2D output → drawings).
2. **Find the functional group** in the source where it fits (above).
   New helpers go AT THE BOTTOM of their group, after the existing
   helpers, so dependencies always resolve in source order.
3. **Write the helper as a top-level function** taking explicit
   arguments. No global state, no Blender selection assumptions
   (Bonsai operators are notorious for reading `context.selected_objects`
   silently — wrap your operator call in `with bpy.context.temp_override
   (...)` if needed).
4. **Add `IfcRel*` relationships** for every connection. The "Always
   IFC-correct" principle (see `lessons-learned.md`) is the only rule
   that matters here.
5. **Document inline** with a thorough docstring: args, the IFC mechanism
   it uses, known gotchas. The docstring IS the user-facing docs — these
   skills don't ship separate API reference.
6. **Update `SKILL.md`** with a section + a code example if the helper
   establishes a new rule or pattern (not for every minor helper).
7. **Add an entry to `CHANGELOG.md`** under Unreleased / next version.
8. **Add an integration check** to one of the `examples/` scripts so the
   helper is exercised end-to-end at every release.

## Where to ask for help

- Bonsai source: `<your_clone>/IfcOpenShell/src/bonsai/bonsai/`
- IfcOpenShell Python API: `<your_clone>/IfcOpenShell/src/ifcopenshell-python/ifcopenshell/api/`
- Bonsai community: [OSArch forum](https://community.osarch.org/)
- IfcOpenShell issues: [github.com/IfcOpenShell/IfcOpenShell](https://github.com/IfcOpenShell/IfcOpenShell)
