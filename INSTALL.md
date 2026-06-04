# Installation guide

End-to-end setup to use these skills with Claude Code driving Blender +
Bonsai.

## 1. Prerequisites

| Tool | Version | Why |
|---|---|---|
| Blender | 5.1 or newer | host application |
| Bonsai | 0.8.5 or newer | OpenBIM authoring inside Blender |
| Bonsai MCP add-on | latest | exposes a localhost MCP server so Claude Code can drive Blender from outside |
| Claude Code | latest | the agent that loads + runs these skills |
| Python | 3.13 | ships with Blender 5.1; nothing to install separately |

Optional but recommended:

- `ifctester` (for IDS validation helpers)
- `ifcopenshell` clone of the source tree for reading internal Bonsai
  code while debugging (not required to run)

## 2. Install Blender + Bonsai

1. **Blender 5.1+** from [blender.org](https://www.blender.org/download/).
2. **Bonsai** — install from inside Blender:
   - Edit → Preferences → Get Extensions
   - Search for "Bonsai" → Install.
   - Restart Blender. The "BIM" workspace tab should appear.

## 3. Install the Bonsai MCP add-on

Claude Code drives Blender through a small MCP server that runs inside
the Blender process.

1. Download the add-on ZIP from
   [github.com/JotaDeRodriguez/Bonsai_mcp](https://github.com/JotaDeRodriguez/Bonsai_mcp).
2. In Blender: Edit → Preferences → Add-ons → Install from Disk → pick
   the ZIP.
3. Enable the add-on. A new panel ("MCP") appears in the 3D View sidebar
   (press `N` to open the sidebar).
4. Click **Start MCP Server**. Default port: `9876` (or `9877` if 9876
   is taken). Leave Blender running with the server started.

## 4. Clone this repo

```bash
git clone https://github.com/<you>/bonsai-bim-skills.git
cd bonsai-bim-skills
```

## 5. Wire the skills into Claude Code

Claude Code loads skills from `~/.claude/skills/<skill-name>/`. The
simplest setup is to symlink so edits in the repo propagate without
copying.

**Linux / macOS:**
```bash
mkdir -p ~/.claude/skills
ln -s "$(pwd)/skills/bonsai-walls"    ~/.claude/skills/bonsai-walls
ln -s "$(pwd)/skills/bonsai-drawings" ~/.claude/skills/bonsai-drawings
```

**Windows (PowerShell, requires admin OR developer mode):**
```powershell
New-Item -ItemType Directory -Path "$env:USERPROFILE\.claude\skills" -Force
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\bonsai-walls"    -Target "$pwd\skills\bonsai-walls"
New-Item -ItemType SymbolicLink -Path "$env:USERPROFILE\.claude\skills\bonsai-drawings" -Target "$pwd\skills\bonsai-drawings"
```

If symlinks are blocked, fall back to copying:
```powershell
Copy-Item -Recurse "$pwd\skills\bonsai-walls"    "$env:USERPROFILE\.claude\skills\bonsai-walls"
Copy-Item -Recurse "$pwd\skills\bonsai-drawings" "$env:USERPROFILE\.claude\skills\bonsai-drawings"
```

## 6. Configure Claude Code's MCP connection to Blender

Claude Code reads MCP server config from a JSON file (location depends
on platform — see Claude Code docs). Add an entry like:

```json
{
  "mcpServers": {
    "blender": {
      "command": "<path to MCP launcher>",
      "args": ["--port", "9877"]
    }
  }
}
```

Specifics vary by MCP server distribution — follow the Bonsai MCP
add-on's README.

## 7. Verify

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
- Make sure the Bonsai MCP server is still running (the panel button
  toggles between "Start" and "Stop").
- Try running `skills/bonsai-walls/examples/build_room_4x6.py` directly
  in Blender's Scripting workspace to isolate whether the issue is in
  the skill or in the Claude Code wiring.

## 8. Output paths

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

## 9. Troubleshooting

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
