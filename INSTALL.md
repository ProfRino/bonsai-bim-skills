# Installation guide

End-to-end setup to use these skills with Claude Code driving Blender +
Bonsai.

## 1. Prerequisites

### Required

| Tool | Version | Why |
|---|---|---|
| Blender | 5.1 or newer | host application |
| Bonsai | 0.8.5 or newer | OpenBIM authoring add-on inside Blender — provides the Python API (`from bonsai import tool`, `bpy.ops.bim.*`) that these skills call |
| **BlenderMCP** ([ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)) | latest | exposes a localhost MCP server with `execute_blender_code` + viewport screenshots. **This is what the skills drive Blender through.** |
| Claude Code | latest | the agent that loads + runs these skills |
| Python | 3.13 | ships with Blender 5.1; nothing to install separately |

### Recommended (tested-with-it stack)

| Tool | Why |
|---|---|
| **ifc-bonsai-mcp** ([Show2Instruct/ifc-bonsai-mcp](https://github.com/Show2Instruct/ifc-bonsai-mcp)) | Provides higher-level MCP tools (`mcp__bonsai-ifc__create_wall`, `create_door`, `create_roof`, `apply_style`, scene queries, etc.). These skills don't call those tools directly, but the development + verification of v0.1.0 was done with this MCP installed alongside BlenderMCP. Highly recommended — it lets Claude do ad-hoc IFC ops *outside* the skills' scope (poke at scene, query an entity, etc.) without needing to write a full `execute_blender_code` payload. |

> **About the naming:** the repo is `ifc-bonsai-mcp` (the URL above). The
> MCP server NAME — what shows up as the `mcp__bonsai-ifc__*` prefix on
> its tools — is `bonsai-ifc`. Don't be thrown by the swap.

### Optional

| Tool | Why optional |
|---|---|
| `ifctester` Python lib | Drives the IDS validation helpers (`author_room_ids`, `validate_against_ids`). Auto-installed with newer Bonsai builds. |
| `ifcopenshell` source clone | Useful for reading internal Bonsai code while debugging. Not required to run. |
| **Bonsai MCP** ([JotaDeRodriguez/Bonsai_mcp](https://github.com/JotaDeRodriguez/Bonsai_mcp)) — a different Blender-MCP project | Another option if BlenderMCP doesn't suit you. **Not** the verified setup for v0.1.0; included here for completeness. |

### MCP architecture (why two MCPs)

Two distinct layers:

```
Claude Code  ──MCP──▶  BlenderMCP server  ──socket──▶  Blender
                                                          │
                                                          ├─ Bonsai add-on (provides bpy.ops.bim.* + tool.Ifc etc.)
                                                          ├─ ifc-bonsai-mcp add-on (exposes its own MCP server with high-level IFC tools)
                                                          └─ <the skills' Python runs here>
```

- **BlenderMCP** is the transport: sends Python code from Claude into
  Blender's process and returns results. The skills use it via
  `mcp__Blender__execute_blender_code`.
- **ifc-bonsai-mcp** runs INSIDE Blender as another MCP server that
  Claude can talk to in parallel. It exposes high-level tools like
  `mcp__bonsai-ifc__create_wall`. **The skills do not use it** —
  every helper imports Bonsai's Python API directly inside
  `execute_blender_code` and bypasses higher-level MCP wrappers. But
  having it installed lets the agent use those tools for ad-hoc work
  outside the skill's scope, which is what we did during development.

When the skill code runs, it looks like:

```python
# Sent over BlenderMCP via execute_blender_code:
from bonsai import tool
from bonsai.bim.module.model.wall import DumbWallGenerator, DumbWallJoiner
import ifcopenshell.api
# ...
bpy.ops.bim.add_window()
```

Everything happens in-process inside Blender. The two MCPs are
independent — you could run with just BlenderMCP if you don't want
ifc-bonsai-mcp's extras.

## 2. Install Blender + Bonsai

1. **Blender 5.1+** from [blender.org](https://www.blender.org/download/).
2. **Bonsai** — install from inside Blender:
   - Edit → Preferences → Get Extensions
   - Search for "Bonsai" → Install.
   - Restart Blender. The "BIM" workspace tab should appear.

## 3. Install BlenderMCP (required)

[github.com/ahujasid/blender-mcp](https://github.com/ahujasid/blender-mcp)

1. Follow the install steps in that repo's README — typically a Blender
   add-on ZIP that you install via Edit → Preferences → Add-ons →
   Install from Disk.
2. Enable the add-on. A new panel ("BlenderMCP") appears in the 3D View
   sidebar (press `N` to open the sidebar).
3. Click **Connect to MCP server** (or **Start MCP Server**, depending
   on the version). Leave Blender running with the server connected.

## 4. Install ifc-bonsai-mcp (recommended)

[github.com/Show2Instruct/ifc-bonsai-mcp](https://github.com/Show2Instruct/ifc-bonsai-mcp)

This is the second MCP — runs inside Blender alongside BlenderMCP and
exposes Bonsai-specific tools (`create_wall`, `create_door`, scene
queries, etc.). The skills don't call these tools directly, but the
v0.1.0 verified setup had it installed.

Follow that repo's install instructions. The tool prefix it exposes to
Claude will be `mcp__bonsai-ifc__*`.

## 5. Configure Claude Code's MCP connections

Claude Code reads MCP server config from a JSON file (location depends
on platform — see Claude Code docs). With the verified setup you'll
have BOTH servers configured, e.g.:

```json
{
  "mcpServers": {
    "Blender": {
      "command": "<path or invocation per BlenderMCP README>"
    },
    "bonsai-ifc": {
      "command": "<path or invocation per ifc-bonsai-mcp README>"
    }
  }
}
```

Exact `command` strings come from each MCP's README — copy from there
verbatim.

## 6. Clone this repo

```bash
git clone https://github.com/ProfRino/bonsai-bim-skills.git
cd bonsai-bim-skills
```

## 7. Wire all 7 skills into Claude Code

Claude Code loads skills from `~/.claude/skills/<skill-name>/`. The
simplest setup is to symlink so edits in the repo propagate without
copying.

The 7 skills are:

- `bonsai-walls` — walls + slabs + mitered corners + interior partition rules
- `bonsai-openings` — doors + windows + equal-spacing rule + styling
- `bonsai-roofs` — 4 roof topologies + IFC-correct wall fits
- `bonsai-stairs` — parametric stairs + railings + stairwell voids
- `bonsai-spaces-grid` — IfcSpace + IfcGrid (with bubble extension control)
- `bonsai-project-setup` — project setup + storeys + audit + IDS + BCF
- `bonsai-drawings` — Plan / Section / Elevation + dimensions + SVG

**Linux / macOS:**
```bash
mkdir -p ~/.claude/skills
for skill in bonsai-walls bonsai-openings bonsai-roofs bonsai-stairs \
             bonsai-spaces-grid bonsai-project-setup bonsai-drawings; do
    ln -s "$(pwd)/skills/$skill" ~/.claude/skills/$skill
done
```

**Windows (PowerShell, requires admin OR developer mode):**
```powershell
New-Item -ItemType Directory -Path "$env:USERPROFILE\.claude\skills" -Force
foreach ($skill in 'bonsai-walls','bonsai-openings','bonsai-roofs','bonsai-stairs',
                    'bonsai-spaces-grid','bonsai-project-setup','bonsai-drawings') {
    New-Item -ItemType SymbolicLink `
        -Path "$env:USERPROFILE\.claude\skills\$skill" `
        -Target "$pwd\skills\$skill"
}
```

If symlinks are blocked, fall back to copying:
```powershell
foreach ($skill in 'bonsai-walls','bonsai-openings','bonsai-roofs','bonsai-stairs',
                    'bonsai-spaces-grid','bonsai-project-setup','bonsai-drawings') {
    Copy-Item -Recurse "$pwd\skills\$skill" "$env:USERPROFILE\.claude\skills\$skill"
}
```

> **About the duplicate `bonsai_bim_helpers.py` copies**: Claude Code
> expects each skill folder to be self-contained. The repo committed
> identical copies of `bonsai_bim_helpers.py` into 6 of the 7 skill
> folders so symlinking just works. Maintainers edit
> `canonical/bonsai_bim_helpers.py` and run `python tools/sync_modules.py`
> to update all 6 copies.

## 7b. (Developers only) Clone the Bonsai / IfcOpenShell source

Strongly recommended if you plan to write new helpers. The skills' code
imports Bonsai's Python API directly (`from bonsai import tool`,
`bpy.ops.bim.*`) — when something doesn't work the way you expect, the
fastest debugging path is reading Bonsai's source.

```bash
# Clone next to (or anywhere convenient relative to) this repo
git clone https://github.com/IfcOpenShell/IfcOpenShell.git
```

Key folders to bookmark:

| Folder | What's there |
|---|---|
| `IfcOpenShell/src/bonsai/bonsai/bim/module/` | Bonsai's Blender operators (`bpy.ops.bim.*`). One subfolder per topic: `model/wall.py` for walls, `model/roof.py` for roofs, `drawing/` for plans/sections/elevations, etc. |
| `IfcOpenShell/src/bonsai/bonsai/tool/` | `tool.Ifc` / `tool.Model` / `tool.Geometry` / `tool.Drawing` — the singletons our helpers call into. |
| `IfcOpenShell/src/ifcopenshell-python/ifcopenshell/api/` | Low-level IfcOpenShell API: `geometry/connect_wall.py`, `feature/add_feature.py`, `grid/create_axis_curve.py`, etc. |
| `IfcOpenShell/src/ifcopenshell-python/ifcopenshell/util/` | Helpers for reading IFC: `element.py` (get_psets, get_predefined_type), `placement.py` (matrix decomposition), `representation.py`. |

The SKILL.md files reference these paths with `<your_local_clone>/`
prefixes — replace with your actual clone location.

Optional: set an env var so your editor's "Go to symbol" jumps into the
right place:

```bash
export IFCOPENSHELL_REPO="$HOME/code/IfcOpenShell"
```

## 8. Verify

Open a new Claude Code session and ask:

> Build me a 4×6m room with mitered corners, a slab, a door, and one
> window per wall.

Claude should:
1. Auto-load the `bonsai-walls` skill (triggered by "build a room",
   "mitered corners", etc.).
2. Use `mcp__Blender__execute_blender_code` to run code against your
   running Blender + Bonsai.
3. Produce a complete IFC scene with all the proper entities.
4. Run `audit_with_screenshots` and grab one viewport image per angle
   (FRONT / RIGHT / BACK / LEFT / TOP / PERSP_SE).

If anything fails:

- Check Blender's System Console (Window → Toggle System Console on
  Windows) for tracebacks.
- Make sure the BlenderMCP server is still running (the sidebar panel
  toggles between "Connect" and "Disconnect").
- Try running `examples/build_room_4x6.py` directly in Blender's
  Scripting workspace to isolate whether the issue is in the skill or
  in the Claude Code wiring.

## 9. Output paths

The skills don't hardcode an output directory. Each example script has
an `OUTPUT_DIR` constant at the top that you adjust before running. For
end-to-end use:

```python
OUTPUT_DIR = r"C:\path\to\your\project\folder"
```

Saved artefacts per example:

- `<OUTPUT_DIR>/<project_name>.ifc` — the IFC model.
- `<OUTPUT_DIR>/<project_name>.ids` — IDS specification (if authored).
- `<OUTPUT_DIR>/drawings/*.svg` — rendered plans / sections / elevations.
- `<OUTPUT_DIR>/drawings/cache/*.h5` — Bonsai drawing cache (regenerate
  to refresh).

## 10. Troubleshooting

- **"Bonsai experienced an error :( ... PermissionError: drawings"** —
  you skipped `bpy.ops.bim.save_project(filepath=...)` before creating
  a drawing. The skill's `add_drawing()` helper now raises a clear
  RuntimeError before this happens. Save the IFC through the
  operator (not `ifc.write`) and retry.
- **"NameError: name 'H' is not defined" between
  `execute_blender_code` calls** — each call is a fresh Python
  namespace. Re-declare variables at the top of each subsequent call.
- **Drawing SVG rendered with stale grid extent** — Bonsai caches
  drawings via `.h5` files. Clear `<OUTPUT_DIR>/drawings/cache/*.h5`
  and re-render. (`add_project_grid` now handles this for you when
  recreating the grid.)
- **Wall axis trimmed after T-junction connection** — you connected a
  partition to a thicker exterior wall via `DumbWallJoiner`. Don't:
  `connect_wall` picks the exterior's nearest endpoint and trims it.
  `add_interior_wall` skips this case automatically; only
  same-thickness siblings get connected.
