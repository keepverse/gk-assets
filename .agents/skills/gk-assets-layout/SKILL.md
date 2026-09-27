---
name: gk-assets-layout
description: Orientation for the gk-assets repo - what belongs here, where Blender assets live, how to run builds and previews, and which adjacent Keepverse repos to use instead. Use when starting work in gk-assets, adding a new asset type, or deciding whether something belongs in this repo. Triggers on "gk-assets", "where do I put", "new asset type", "add a video generator", "this repo", "assets workflow".
---

# gk-assets layout

## What this repo is

Blender-authored game assets and the tooling to build them. **Nothing here
ships in the game build.** No gameplay logic, no engine integration, no
runtime code.

Adjacent Keepverse repos, for when the answer is not here:

| Repo | Holds |
|---|---|
| `gk-core` | Core game logic / data model |
| `gk-fusion` | The web front end (Phaser) |
| `gk-data` | Content and data |
| `gk-forge` | Tooling / generators |
| `tools` | Shared cross-repo tooling |

## Layout

```
tools/    scripts — blender_path.py resolves a Blender; serve/preview/pack/verify
vfx/      VFX sub-programs, one dir per effect (effect.json is authoritative)
render/   RESERVED for full-frame and video-still output
video/    RESERVED for a video generator
```

Both reserved dirs are intentionally empty. Do not add structure to them
speculatively — put a working tool there first.

## Running things

```bash
python tools/blender_path.py --all     # which Blender, and does it have MCP?
python tools/pack_sheets.py            # sequences -> sheets
python tools/serve.py                  # browser preview (needs a Phaser build)
```

`tools/blender_path.py` prefers the Blender that has the official MCP add-on
(5.1 on `D:`) over the LTS install (5.2 on `C:`). They render differently, so
do not hardcode one.

## VFX sub-program shape

```
vfx/<id>/
  effect.json    manifest: sprite grid, layers, blend modes, notes, knownIssues
  <id>.blend     the scene
  README.md      the brief
  sheets/        packed sprite sheets   <- committed, the deliverable
  sequences/     per-frame renders      <- ignored, regenerable
  preview/       flat composite frames  <- ignored, review only
```

`effect.json` is the single source of truth. The viewer reads it directly, so
never duplicate layout or blend data elsewhere.

## Conventions worth knowing

- **Author 512, deliver 128.** Sheets are downsampled to the gameplay cell.
- **Sheets committed, sequences/preview ignored.** Sheets are what the game
  loads; the rest is build output and would add ~68 MB.
- **Verify from rendered output.** `verify_all.py` reads PNGs, so it catches
  "script exited 0, produced garbage" — the failure that actually happens.

## Before authoring

Read `vfx/README.md` (the VFX pipeline document) and `AGENTS.md` (working
rules). Both exist because something went wrong the first time.

For the shader-level traps specifically, load the `blender-vfx-build` skill.
