# gk-assets — agent guide

Blender-authored game assets. This repo is **only** the assets pipeline; it
holds no game logic, no build system for the game itself, and no source code
that ships in a build. If you are here to change gameplay, this is the wrong
repo — see `gk-core` / `gk-fusion`.

## Read before doing anything

**`vfx/README.md` is the technical document for the VFX pipeline** — the rig,
the 3D-in-2D technique, and nine rig traps that each shipped a visibly wrong
render before measurement caught it. Read it before authoring or editing an
effect. It is the highest-value file in the repo.

## Layout

```
tools/          scripts. blender_path.py resolves a Blender; the rest are
                build/verify/preview entry points.
vfx/            VFX sub-programs. One dir per effect:
  index.json      list of effect ids
  <id>/
    effect.json   MANIFEST - single source of truth for the viewer
    <id>.blend    the scene
    README.md     the brief: layers, timing, measured values, known issues
    sheets/       packed sprite sheets  <- the deliverable, committed
    sequences/    per-frame renders      <- regenerable, ignored
    preview/      flat composite frames  <- review only, ignored
render/         RESERVED. future full-frame / video-still output.
video/          RESERVED. future video generator.
```

`render/` and `video/` are intentionally empty placeholders. Do not fill them
until there is a tool to put in them.

## Working rules

**Measure, do not eyeball.** This is the rule that matters most. A flame card
that "looks like fire" to me measured a fill ratio of 0.925 — a solid rounded
rectangle. Several effects passed visual review and were wrong. Every claim
about an asset should be backed by a number from `verify_all.py`,
`test_flame_card.py`, or an explicit probe. When something looks wrong, measure
which property is wrong before tuning anything.

**Verify before claiming done.** `tools/verify_all.py` must pass. It reads the
rendered PNGs, not the build code, so it catches the failure mode that matters:
a script that exits 0 while producing garbage.

**Do not hand-tune parameters into a build script without a reason.** If a
number is magic, say why in a comment. If two effects need the same rig change,
change it in `shield_rig.py`, not per-effect.

**Author at 512, deliver at 128.** `sheets/` is the 128px gameplay cell,
downsampled by `pack_sheets.py`. The existing game art
(`actor-hud-elements/*.png`) is 128px, so that is the contract.

**Sheets are committed; sequences and previews are not.** Sheets are what the
game loads. `sequences/` is the packer's input and `preview/` is for human
review; both are rewritten on every build and would add ~68 MB of noise.

## Running Blender

Do not hardcode a Blender path. Use the resolver:

```bash
python tools/blender_path.py            # prints the resolved binary
python tools/blender_path.py --all      # lists every install + add-on status
```

It prefers the install that has the official Blender Lab **MCP add-on**
(5.1 on `D:`), because that is the one reachable from a live GUI session, and
falls back to the LTS install. The two produce different pixel output, so a
sheet rendered on one is not byte-identical to the other — a hardcoded path
rots silently the day that install moves.

To drive Blender interactively over MCP the add-on's socket server must be
running inside Blender. If tools report "cannot connect", check:

```powershell
Get-NetTCPConnection -LocalPort 9876
```

If nothing is listening, the server is fine and the *bridge* is dead: start it
from Blender's MCP preferences. Restarting Blender without ticking "Auto
Start" breaks this, and the error message points at the wrong layer.

## Common tasks

```bash
# build one effect (writes sequences/ and preview/)
blender --background --factory-startup --python tools/shield_idle.py

# rebuild every effect
for s in idle rotate impact strengthen break; do
  "$BLENDER" --background --factory-startup --python "tools/shield_$s.py"
done

# pack sheets + refresh the index
python tools/pack_sheets.py --write-index

# verify everything
blender --background --factory-startup --python tools/verify_all.py

# browser preview (needs a Phaser build; see tools/serve.py)
python tools/serve.py
```

## Adding an effect

1. `vfx/<id>/effect.json` — copy an existing one; it is the only place layout,
   blend mode, layer notes and known issues live.
2. `tools/<id>.py` — import `shield_rig` and compose layers. Per-card materials
   when a layer animates independently.
3. Build, pack, verify.
4. `vfx/<id>/README.md` — layers, frame timing, measured values, known issues.

`pack_sheets.py --write-index` adds it to the sidebar.

## What is not in scope here

- Game-side integration. These are assets plus documentation. The Phaser wiring,
  additive blend convention, and occupant-container parenting are specified in
  `vfx/README.md` but not implemented.
- The in-game Unity VFX layer (`docs/architecture/vfx-ssot.md` in the game
  repo) is a **separate** system, spec-locked to generated textures with no
  asset pipeline. Sheets from this repo are not for it.
