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

| Skill | What it does | Trigger words |
|---|---|---|
| **`bonsai-walls`** | Rooms with mitered corners, slabs, parametric doors/windows (BBIM_Door / BBIM_Window), 4 roof types (mono-pitch / hip / gable / flat), wall-to-roof fits via `IfcBooleanClippingResult`, interior partitions with auto-clip + auto-connect, parametric stairs + railings, IfcSpaces with space boundaries, project grids, IDS + BCF helpers, multi-angle audit screenshots. | "build a room", "add wall", "add window", "add roof", "add stair", "fit walls to roof", "subdivide a space", "add grid", "validate IDS" |
| **`bonsai-drawings`** | `IfcAnnotation` cameras for Plan / Section / Elevation / Reflected Plan / Model views, SVG rendering via `bim.create_drawing`, dimensions (linear `IfcAnnotation` curves with auto-computed metre labels), drawing camera scale + extent control. | "create plan", "generate section", "elevation drawing", "add dimension" |

Each skill has its own `SKILL.md` that Claude Code loads automatically when
its trigger words appear in your prompt.

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
- **Bonsai 0.8.5+** Blender add-on (https://bonsai.coop/)
- **Bonsai MCP add-on** so Claude Code can drive Blender remotely
  (https://github.com/JotaDeRodriguez/Bonsai_mcp)
- **Claude Code** CLI (https://docs.claude.com/en/docs/claude-code/overview)
- Python 3.13 (ships with Blender 5.1)

### Install — three steps

1. **Clone this repo:**
   ```bash
   git clone https://github.com/<you>/bonsai-bim-skills.git
   cd bonsai-bim-skills
   ```

2. **Symlink (or copy) the skills into your Claude Code skill directory.**

   The directory varies by platform:
   - Linux / macOS: `~/.claude/skills/`
   - Windows: `C:\Users\<you>\.claude\skills\`

   ```bash
   # Linux / macOS
   ln -s "$(pwd)/skills/bonsai-walls"    ~/.claude/skills/bonsai-walls
   ln -s "$(pwd)/skills/bonsai-drawings" ~/.claude/skills/bonsai-drawings

   # Windows PowerShell (run as administrator for symlinks; otherwise copy)
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\bonsai-walls"    -Target "$pwd\skills\bonsai-walls"
   New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\bonsai-drawings" -Target "$pwd\skills\bonsai-drawings"
   ```

3. **Configure the Bonsai MCP server in Claude Code** so the agent can talk
   to Blender. See [`INSTALL.md`](INSTALL.md) for the full step-by-step.

### Run the smoke test

Open Blender → Scripting workspace → open `skills/bonsai-walls/examples/build_room_4x6.py` → ▶ Run Script.

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
├── docs/
│   ├── architecture.md                how the skills fit together
│   └── lessons-learned.md             49 hard-won rules baked in
└── skills/
    ├── bonsai-walls/
    │   ├── SKILL.md                   Claude Code skill manifest + usage
    │   ├── bonsai_room_with_miters.py  core helpers (~3500 lines)
    │   └── examples/
    │       ├── build_room_4x6.py            canonical smoke test
    │       ├── build_two_room_house.py      3-storey with stairs
    │       ├── build_office_10x20.py        the office in the screenshots
    │       └── test_roof_types.py           4 roofs side-by-side
    └── bonsai-drawings/
        ├── SKILL.md
        └── bonsai_drawings.py
```

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
