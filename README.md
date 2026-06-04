# bonsai-bim-skills

**Programmatic IFC / BIM authoring in Blender + Bonsai, packaged as
[Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
skills.** Build walls, slabs, roofs, doors, windows, stairs, spaces,
grids, and full SVG construction drawings (plans, sections, elevations)
from Python — all producing real IFC entities with proper relationships,
not Blender-only geometry that gets lost on export.

> Built and battle-tested against **Bonsai v0.8.5** + **Blender 5.1** with
> **IFC4** schema.

---

## What's in here

**7 focused Claude Code skills**, each with its own `SKILL.md` that the
agent loads automatically when its trigger words appear in your prompt:

| Skill | What it does | Trigger words |
|---|---|---|
| **`bonsai-walls`** | Rooms with mitered corners, exterior + interior partitions (auto-clip overshoot + same-thickness sibling auto-connect), floor slabs fitted to wall outlines | "build a room", "polyline walls", "interior wall", "partition", "fit slab" |
| **`bonsai-openings`** | Parametric BBIM doors + windows, equally-spaced windows rule (the `gap = (L − N·W)/(N+1)` default), Frame/Glass/Panel styling, OverallWidth/Height filler | "add a door", "add a window", "equally spaced", "style openings" |
| **`bonsai-roofs`** | 4 roof topologies (mono-pitch / hip / gable / flat), IFC-correct wall-to-roof fits via `IfcBooleanClippingResult` + `IfcHalfSpaceSolid` | "add roof", "fit walls to roof", "hip roof", "gable roof" |
| **`bonsai-stairs`** | Parametric `BBIM_Stair` with proper `top_slab_depth` connection, stairwell `IfcOpeningElement` sized to actual last-tread (not bbox), guard + handrail `IfcRailing` | "add stairs", "stairwell", "railing", "handrail" |
| **`bonsai-spaces-grid`** | `IfcSpace` (aggregated, with `IfcRelSpaceBoundary` + `Qto_SpaceBaseQuantities`), `IfcGrid` with configurable bubble extension (default 4 m so bubbles clear the dim chains) | "add a space", "space boundary", "project grid" |
| **`bonsai-project-setup`** | `bootstrap_project` (dual wall types + slab type + 3 styles + spatial hierarchy), `add_storey`, MANDATORY multi-angle audit screenshots, `Qto_*` + `OverallWidth/Height` fillers, IDS authoring + validation, BCF round-trip | "bootstrap", "set up project", "add storey", "audit", "IDS", "BCF" |
| **`bonsai-drawings`** | `IfcAnnotation` cameras for Plan / Section / Elevation / Reflected Plan / Model views, SVG rendering via `bim.create_drawing`, linear dimensions, scale + extent control | "create plan", "generate section", "elevation drawing", "add dimension" |

All 6 element-related skills share the **same Python module**
(`bonsai_bim_helpers.py`) — same source is copied into each skill folder
so each skill is self-contained for Claude Code's skill loader. A
`tools/sync_modules.py` script keeps the copies aligned with
`canonical/bonsai_bim_helpers.py` (the source of truth) for maintainers.

The `bonsai-drawings` skill has its own module (`bonsai_drawings.py`).

---

## Core principle: ALWAYS IFC/BIM-correct

Every element, void, fill, material, parametric property MUST be a real
IFC entity with proper relationships (`IfcRelVoidsElement`,
`IfcRelFillsElement`, `IfcRelAssociatesMaterial`, `IfcRelConnectsPathElements`,
`IfcRelDefinesByType`, etc.). Blender-only mechanisms (Boolean modifiers,
mesh edits, viewport overlays) look right on-screen but **get lost on IFC
export** and break interop with every other IFC tool — Solibri, BIMVision,
IFC.js, Revit, ArchiCAD.

Every helper in these skills does the IFC mechanism, not the Blender
shortcut. Known exceptions ("BIM-correctness debt") are flagged inline in
the source and in each `SKILL.md`.

---

## Quick start

### Prerequisites

- **Blender 5.1+** (https://www.blender.org/)
- **Bonsai 0.8.5+** Blender add-on (https://bonsai.coop/) — provides the
  Python API (`from bonsai import tool`, `bpy.ops.bim.*`) the skills call
- **BlenderMCP** (required) — https://github.com/ahujasid/blender-mcp
  — exposes `execute_blender_code` so Claude Code can drive Blender
- **ifc-bonsai-mcp** (recommended) — https://github.com/Show2Instruct/ifc-bonsai-mcp
  — second MCP running inside Blender; exposes high-level IFC tools
  (`create_wall`, `create_door`, etc.). The skills don't call these
  directly, but the verified v0.1.0 development was done with this MCP
  installed alongside BlenderMCP — keeping the parity makes
  troubleshooting easier and lets Claude do ad-hoc IFC ops outside the
  skill's scope.
- **Claude Code** CLI (https://docs.claude.com/en/docs/claude-code/overview)
- Python 3.13 (ships with Blender 5.1)

> See [`INSTALL.md`](INSTALL.md#mcp-architecture-why-two-mcps) for the
> full two-MCP architecture diagram and what each layer does.

### Install — three steps

1. **Clone this repo:**
   ```bash
   git clone https://github.com/ProfRino/bonsai-bim-skills.git
   cd bonsai-bim-skills
   ```

2. **Symlink (or copy) all 7 skills into your Claude Code skill directory.**

   The directory varies by platform:
   - Linux / macOS: `~/.claude/skills/`
   - Windows: `C:\Users\<you>\.claude\skills\`

   ```bash
   # Linux / macOS
   for skill in bonsai-walls bonsai-openings bonsai-roofs bonsai-stairs \
                bonsai-spaces-grid bonsai-project-setup bonsai-drawings; do
       ln -s "$(pwd)/skills/$skill" ~/.claude/skills/$skill
   done

   # Windows PowerShell (requires admin OR Dev Mode for symlinks; else copy)
   foreach ($skill in 'bonsai-walls','bonsai-openings','bonsai-roofs','bonsai-stairs',
                       'bonsai-spaces-grid','bonsai-project-setup','bonsai-drawings') {
       New-Item -ItemType SymbolicLink `
           -Path "$env:USERPROFILE\.claude\skills\$skill" `
           -Target "$pwd\skills\$skill"
   }
   ```

3. **Configure BlenderMCP (and optionally ifc-bonsai-mcp) in Claude
   Code** so the agent can talk to Blender. See [`INSTALL.md`](INSTALL.md)
   for the full step-by-step.

### Run the smoke test

Open Blender → Scripting workspace → open `examples/build_room_4x6.py` → ▶ Run Script.

You should get:
- A 4 × 6 m room with mitered corners (4 `IfcWall`)
- A `FLR200` ground slab
- 2 doors + 6 windows (all parametric BBIM)
- A mono-pitch `IfcRoof` with walls fitted via IFC clipping
- A stair to an upper storey
- An `IfcSpace` per room with proper `IfcRelSpaceBoundary` to each wall/slab/roof
- All elements with `Qto_*BaseQuantities` populated
- IDS validation passing 7/7 specs and 0 BCF topics

---

## What it looks like

The example `examples/build_office_10x20.py` produces a 10 × 20 m office
with:

- 4 exterior walls (`WAL200`, 200 mm) + 4 interior partitions
  (`WAL100`, 100 mm) auto-clipped to inner faces and auto-connected at
  L-corners via `IfcRelConnectsPathElements` (with proper miter
  regeneration via `tool.Model.recreate_wall`)
- 13 windows, equally spaced and centred per the default rule
  (`gap = (L − N·W) / (N + 1)`)
- 3 doors: 1 main entrance (1.2 × 2.1 m double swing) + 2 interior doors
  (0.9 × 2.0 m single swing) in `BBIM_Door` parametric form
- 3 `IfcSpace` entities (NW Room, NE Room, Shared Workspace) with
  explicit space boundaries to every adjacent wall + slab + roof
- A `5 m × 5 m` `IfcGrid` with extended axes (4 m past the building)
  so bubbles don't overlap dimension chains
- A 1:100 floor plan SVG with 12 linear dimensions covering overall
  extents + partition positions + door widths

Generated assets ship in [`examples/output/`](examples/output/) for
quick visual reference.

---

## Repo layout

```
bonsai-bim-skills/
├── README.md                          this file
├── LICENSE                            GPL-3.0 (matches Bonsai)
├── CHANGELOG.md                       per-release notes
├── INSTALL.md                         setup walkthrough
├── canonical/
│   └── bonsai_bim_helpers.py          SINGLE source of truth (~3500 lines)
├── docs/
│   ├── architecture.md                how the skills fit together + how to extend
│   └── lessons-learned.md             ~50 hard-won rules baked in
├── examples/                          full standalone build scripts
│   ├── build_room_4x6.py                  canonical smoke test
│   ├── build_two_room_house.py            3-storey with stairs
│   ├── build_office_10x20.py              the office in the screenshots
│   └── test_roof_types.py                 4 roofs side-by-side
├── tools/
│   └── sync_modules.py                copy canonical/* into each skill folder
└── skills/
    ├── bonsai-walls/                  walls + slabs + mitered corners + interior partition rules
    │   ├── SKILL.md
    │   ├── bonsai_bim_helpers.py          (copy of canonical/)
    │   └── bonsai_room_with_miters.py     backward-compat shim — `from bonsai_bim_helpers import *`
    ├── bonsai-openings/               doors + windows + equal spacing + Frame/Glass/Panel styling
    │   ├── SKILL.md
    │   ├── bonsai_bim_helpers.py          (same copy)
    │   └── bonsai_room_with_miters.py     (shim)
    ├── bonsai-roofs/                  4 roof topologies + IFC-correct wall fits
    │   ├── SKILL.md
    │   ├── bonsai_bim_helpers.py
    │   └── bonsai_room_with_miters.py
    ├── bonsai-stairs/                 parametric stairs + railings + stairwell voids
    │   ├── SKILL.md
    │   ├── bonsai_bim_helpers.py
    │   └── bonsai_room_with_miters.py
    ├── bonsai-spaces-grid/            IfcSpace + IfcGrid with bubble-extension control
    │   ├── SKILL.md
    │   ├── bonsai_bim_helpers.py
    │   └── bonsai_room_with_miters.py
    ├── bonsai-project-setup/          bootstrap + storeys + audit + IDS + BCF
    │   ├── SKILL.md
    │   ├── bonsai_bim_helpers.py
    │   └── bonsai_room_with_miters.py
    └── bonsai-drawings/               Plan / Section / Elevation + dimensions + SVG
        ├── SKILL.md
        └── bonsai_drawings.py              its own module
```

**Why each skill carries its own copy of `bonsai_bim_helpers.py`** —
Claude Code's skill loader expects each `~/.claude/skills/<skill>/`
folder to be SELF-CONTAINED (the Python files in it are added to
`sys.path` automatically when the skill is active). Copying the module
into every skill folder is the simplest way to keep that contract,
while a small `tools/sync_modules.py` script keeps the 6 copies aligned
with `canonical/bonsai_bim_helpers.py`. Maintainers edit the canonical
copy, run `python tools/sync_modules.py`, commit.

**Backward-compat shim** — the previous v0.1.0 module name was
`bonsai_room_with_miters.py`. v0.2.0 renamed it to `bonsai_bim_helpers.py`
(more accurate scope). The shim in each skill folder does
`from bonsai_bim_helpers import *` so old user code keeps working.

---

## Why this exists

Authoring IFC programmatically through Bonsai *works*, but the easy-to-
discover path produces broken IFC: missing `IfcRel*` relationships,
tessellated meshes where parametric is needed, `BBIM_*` psets left blank,
opening voids that don't cut wall bodies, partition walls that slice
through exterior walls, dimensions that round-trip to nowhere.

These skills codify ~50 hard-won rules from building several test models
(rooms, multi-storey houses, roof-type comparisons, the 10 × 20 m
office). Each helper has the BIM-correctness gotcha baked into its
behaviour and documented inline. See
[`docs/lessons-learned.md`](docs/lessons-learned.md) for the full list.

---

## Contributing

Issues and PRs welcome. The skills are still growing — likely additions:

- MEP (`IfcPipe*`, `IfcDuct*`, `IfcFlowFitting`)
- Foundations & structural (footings, columns, beams with reinforcement)
- Site context (`IfcGeographicElement`, terrain meshes)
- Schedule / quantity takeoff exports (CSV, COBie)
- Drawing sheets (`IfcDocumentInformation` + Bonsai sheeter integration)

---

## License

GPL-3.0 — see [LICENSE](LICENSE). Matches [Bonsai](https://bonsai.coop/)
to stay aligned with the wider OpenBIM ecosystem.

---

## Acknowledgements

Built on top of [Bonsai](https://bonsai.coop/) (formerly BlenderBIM) by
Dion Moult and contributors, [IfcOpenShell](https://ifcopenshell.org/)
by Thomas Krijnen, and the [Claude Code](https://docs.claude.com/en/docs/claude-code/overview)
skill system by Anthropic.

---

## Citation

If you use this tool in published work, please cite:

> Lovreglio, R. *bonsai-bim-skills*. Massey University.
> https://github.com/ProfRino/bonsai-bim-skills
