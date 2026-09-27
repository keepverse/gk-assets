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

## First commands

```bash
pip install -r requirements.txt
python tools/doctor.py      # is this checkout ready? non-zero if blocked
python tools/build.py       # build all, pack, verify
```

Use `tools/build.py`, not the raw Blender invocations. It fixes the order
(build → pack → verify) and refuses to report success on a build that did not
actually render — Blender exits 0 even when it cannot open a script.

## Layout

```
tools/          scripts. doctor.py checks the setup; build.py is the entry
                point; blender_path.py resolves a Blender; the rest are
                build/pack/verify/preview helpers.
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
committed sheets, not the build code, so it catches the failure mode that
matters: a script that exits 0 while producing garbage.

**Never approve a review.** `tools/review.py` records a **human** visual
sign-off into `vfx/<id>/review.json`. Do not run `--approve` or `--reject`
yourself, and do not hand-write a `review.json`.

You can prove a sprite is the right shape, size, colour, frame count, and that
its loop closes. You cannot tell whether it reads as a shield in motion on a
bright lawn — that judgement stays human.

`verify_all.py` passing means *machine-verified*, which is **not** *reviewed*.
The two states are tracked separately so they are never confused. If the owner
tells you an effect works, you may record their decision with
`--by "<their name>"` and their words as the note; attributing it to yourself
would misstate who reviewed it. Report state with
`python tools/review.py --list`; do not change it.

**Gating is per material, not global.** Saturation is mean(R−B), a *warmth*
axis: fire measures +0.15 to +0.36, frost glass −0.16. One global floor fails
correct ice. Shape gates (raggedness, h/w, fill ceiling) are material-independent
and shared. **A new sub-program with no `EFFECT_MATERIAL` entry fails
verification on purpose** — the failure names the two tables to edit. Do not
work around it by widening `DEFAULT_GATES`; that lets every other effect
regress silently.

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
# everything: build, pack, verify
python tools/build.py

# one sub-program
python tools/build.py shield_fire_idle

# is the checkout usable
python tools/doctor.py

# browser preview (needs a Phaser build; see tools/serve.py)
python tools/serve.py

# call Blender directly
BLENDER=$(python tools/blender_path.py)
"$BLENDER" --background --factory-startup --python tools/shield_idle.py
```

## Adding an effect

1. `vfx/<id>/effect.json` — copy an existing one; it is the only place layout,
   blend mode, layer notes and known issues live.
2. `tools/<name>.py` — import `shield_rig` and compose layers. Per-card
   materials when a layer animates independently.
3. Register `(id, script stem)` in `EFFECTS` in `tools/build.py`. The script
   name is not always the effect id (`shield_fire_idle` → `shield_idle`).
4. `python tools/build.py <id>`
5. `vfx/<id>/README.md` — layers, frame timing, measured values, known issues.

`pack_sheets.py --write-index` adds it to the viewer sidebar.

## What is not in scope here

- Game-side integration. These are assets plus documentation. The Phaser wiring,
  additive blend convention, and occupant-container parenting are specified in
  `vfx/README.md` but not implemented.
- The in-game Unity VFX layer (`docs/architecture/vfx-ssot.md` in the game
  repo) is a **separate** system, spec-locked to generated textures with no
  asset pipeline. Sheets from this repo are not for it.
