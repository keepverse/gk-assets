# VFX sub-program pipeline

A sub-program is a self-contained game asset: one effect, authored in Blender,
delivered as packed sprite sheets, with a manifest that is the single source of
truth. This is the **contract** — what a sub-program must contain and what the
tools do with it. It is written for both rig styles, not just the fire shield.

## Registered sub-programs

| Sub-program | Frames | Rig | Status |
|---|---|---|---|
| `shield_fire_idle` | 36 | transparent 3D globe, native gas fire, small eruptions and cinders | wip |
| `shield_fire_rotate` | 36 | procedural cards, turntable | ready |
| `shield_fire_impact` | 24 | procedural cards | ready |
| `shield_fire_strengthen` | 30 | procedural cards | ready |
| `shield_fire_break` | 36 | procedural cards | ready |
| `shield_ice_idle` | 24 | linked reusable meshes | ready |
| `shield_ice_mirror_idle` | 72 | three vertical bubble-bobbing hero crystals + hex screen + one localized mirror impact | wip |
| `shield_ice_mirror_deploy` | 42 | standalone transparent textured hex screen: expand, hold, fade | wip |
| `shield_ice_mirror_impact` | 24 | steady hex screen + localized fracture and bevelled 3D facets | wip |
| `shield_ice_mirror_deflect` | 24 | prism contact bends one shard away; three idle crystals continue bobbing | wip |
| `shield_ice_mirror_absorb` | 36 | contact, cold lock, and inward frost dissolve; three idle crystals continue bobbing | wip |
| `shield_ice_mirror_penetrate` | 36 | timed entry and exit punctures; three idle crystals continue bobbing | wip |
| `shield_ice_mirror_break` | 36 | screen releases three broad facets and sparse chips; three idle crystals continue bobbing | wip |
| `shield_earth_idle` | 72 | textured orbit rocks + dome | wip |
| `shield_earth_impact` | 24 | textured dome contact response | wip |
| `shield_earth_break` | 36 | fractured dome + three stones | wip |
| `shield_earth_absorb` | 36 | inward stones + moss pulse | wip |
| `shield_earth_penetrate` | 36 | entry/exit fractures | wip |
| `shield_earth_deflect` | 24 | redirected textured stone | wip |

`shield_ice_lifecycle` exists as authoring scenes but is **not** a sub-program:
it has no `effect.json` and produces no sheets, so no tool can consume it. It is
a staging folder for the next ice authoring pass. See
[Not a sub-program](#not-a-sub-program) below.

## The contract

```
vfx/<id>/
  effect.json      REQUIRED. the manifest
  README.md        REQUIRED. the brief
  <id>.blend       REQUIRED. the production scene
  sheets/          REQUIRED, committed. the deliverable
  sequences/       optional, ignored. per-layer renders
  preview/         optional, ignored. flat composite frames
  lookdev/         optional, ignored. opaque beauty stills for review
```

The tools read only `effect.json`, `sheets/` and `sequences/`. A sub-program
that satisfies the contract works with every tool. Register its builder in
`EFFECTS` in `tools/build.py`, declare its material and calibrated gates in
`tools/verify_all.py`, then let the packer write `vfx/index.json`.

### effect.json

```jsonc
{
  "id": "shield_ice_idle",          // must match the directory name
  "name": "Ice Shield - Idle",
  "description": "...",
  "status": "ready",                // wip | ready
  "sprite": {
    "resolution": 128,              // GAMEPLAY cell; sheets are this size
    "frameCount": 24,
    "fps": 24,
    "columns": 6,                   // columns x rows must cover frameCount
    "rows": 4
  },
  "anchor": { "x": 0.5, "y": 0.5 },  // pivot within a frame
  "blend": "normal",                 // default for the effect
  "layers": [
    { "id": "shell", "sheet": "shell.png", "blend": "normal", "note": "..." }
  ],
  "projection": { "mode": "flat" }    // flat | turntable | angles
}
```

Required fields: `id`, `sprite.{resolution,frameCount,columns,rows}`,
`layers[].{id,sheet}`. The optional `static` field is a verifier contract;
other optional fields document the effect for the viewer.
For a layer intentionally held identical across the one-shot, set
`"static": true`; verification then requires one distinct packed tile instead
of treating repeated frames as a stalled animation.

`projection.mode` tells the viewer how to treat the frames:

- **`flat`** — fixed camera, each frame drawn as-is. The ice shield and four of
  the five fire effects use this.
- **`turntable`** — a baked rotation. The viewer applies a per-frame cosine
  width curve so the silhouette narrows and widens as it turns; played as plain
  squares it reads as a wobble. `shield_fire_rotate` uses this.
- **`angles`** — reserved for multi-camera sheets.

### README.md

Layers and what each does, frame-by-frame timing, measured verification values,
and **known issues**. An empty `knownIssues` is only honest if there genuinely
are none.

## Two rig styles

Both produce identical artefacts. The difference is where the source of truth
lives.

**Procedural (fire).** `tools/shield_<name>.py` imports `shield_rig` and
composes the effect from cards or lit meshes, materials and keyframes. The script is the
source of truth; the `.blend` is a build artefact. Rerunning reproduces the
scene exactly. Register in `EFFECTS` as `(id, script_stem)`.

**Linked-asset (ice).** Meshes live as standalone reusable `.blend` files under
`assets/vfx/<kit>/`, and the effect scene *links* them. Edit a source asset,
rerun the builder, and the composition and sheets refresh. Two rules:

- **A packed texture is not a source file.** If a `.blend` has a packed texture,
  the original image must exist under `textures/` in the repository.
- **Name the current version.** The ice kit accumulated `v2/`, `v3/`, `v4/` of
  the same three meshes. Only one version is linked by the production scene;
  the rest are lookdev history. Without a stated current version the next
  person links the wrong one. This repo keeps the base kit only, and the
  superseded versions stay in the game monorepo as reference.

## Build

```bash
python tools/build.py                      # everything registered
python tools/build.py shield_ice_idle      # one
```

`build.py` runs **build → pack → verify**, in that order. The order is not
cosmetic: packing before building ships stale sheets, and verifying before
packing checks nothing.

A build counts as successful only if it prints its own completion line.
**Blender exits 0 even when it cannot open a `--python` script**, so exit codes
alone are not trustworthy — this is why `build.py` ignores them.

## Verification

`verify_all.py` reads the **committed sheets**, not `preview/`. A fresh clone
can be verified without running a build, which is deliberate: a checker that
only works right after a build is not much of a check.

It asserts manifest/grid agreement, that no layer's frames collapsed to
duplicates, that composited frames meet the visual gates, and that looping
effects have no empty frame and close their loop. Compositing the layers
during verification mirrors what the game does at runtime.

### Gates are per material, not global

**The shipped ranges below come from the fire shield. They do not transfer to
frost glass or another cool material.** A frost-glass shell is legitimately
low-saturation and low-fill; gating it on the fire numbers would fail a correct asset.

| Gate | fire range | fails when | transfers to ice? |
|---|---|---|---|
| saturation (α-weighted R−B) | 0.15 – 0.51 | < 0.12 | **no — measure first** |
| white fraction | 0 – 0.022 | > 0.10 | yes |
| fill ratio | 0.011 – 0.365 | > 0.62 (lower advisory) | **no — measure first** |
| silhouette raggedness | 0.259 – 0.94 | < 0.18 | yes |
| bbox height / width | 0.44 – 0.90 | < 0.40 | yes |

The shape gates transfer because a smooth ellipse and a flat band are wrong for
a barrier in either material. The colour and density gates do not, because
frost glass is *supposed* to be pale and thin. A specified regular polygon can
be a correct barrier shape even when the radial-variation metric reports it as
too smooth; in that case use a narrow effect-specific override and document
the measured geometry. Do not relax the shared default.

`shield_ice_mirror_deploy` and `shield_ice_mirror_impact` reuse the same
regular, ground-pointing hex: body and rim sides measure 1.72 and 1.90 Blender
units, and the deploy sheet measures radial variation 0.030 and fill 0.622.
The impact sheet measures fill 0.614–0.622 and radial variation 0.030–0.042;
its localized fracture and facets stay inside the screen outline. Each effect has a narrow
override for this geometry; neither face has spokes, inner rings, or a web
pattern. See the individual effect README files for sampled measurements.

`SAMPLE_PER_EFFECT` in `verify_all.py` records which frames each effect is
sampled at, because a one-shot's tail is legitimately sparse — `shield_fire_break`
at frame 19 is falling cinders with no dome, and demanding a full barrier there
would fail a correct effect.

**When you add a sub-program in a new material, measure its distribution and
record it here and in `GATES` before trusting a pass.** A gate relaxed to
accommodate a real design is worse than a documented exception.

The Earth Shield family uses a 0.06 warmth floor and 0.02 white ceiling; the
idle sheet and each combat response are measured in their own README after
build. All share the shape gates.

## Review gate

`build.py` verifies automatically; **visual review is a human step and agents do
not perform it.** An agent can prove a sprite is the right shape, the right size
and the right colour. It cannot tell you whether the effect *reads* as a shield
in motion on a bright lawn. That judgement stays with a person.

So there are two states, and the tools enforce the first:

1. **Machine-verifiable** — `verify_all.py` passes. `status` may be `wip`.
2. **Human-reviewed** — someone opened the effect in the viewer, on the lawn
   background, at gameplay scale, and accepted it. Recorded in
   `review.json` next to the sub-program.

`tools/review.py` records and clears the human sign-off. `build.py` reports
which sub-programs have it, so "all verified" and "all reviewed" are never
confused.

## Conventions

Pipeline-level, so they apply to every sub-program regardless of rig.

**Resolution** — author at 512px, deliver at 128px. At 128 a card is ~20–30px,
so detail is sub-pixel and averages to a flat block. The game's
`actor-hud-elements` icon art is 128px, so that is the gameplay cell.

**Colour** — `view_transform = "Standard"`. AgX is a filmic look that
desaturates; saturated effects come out cream.

**Emission ≤ 1.0 for sprite-style emissive shading.** Shader RGB is written
straight to the PNG, so >1.0 clips every channel to white. This does **not**
apply to a physically lit glass render (as the ice shell uses) — the
constraint is about emission-based shading, not lit materials.

**Alpha masks are driven by distance, not angle.** A radial mask must be
`black at large distance → white at centre`. Getting the polarity backwards,
plus the ColorRamp's Fac clamp, turns the whole surface opaque.

**Sheets are committed; `sequences/`, `preview/` and `lookdev/` are not.**
Sheets are what the game loads. The rest is build output.

## Known traps

Each shipped a visibly wrong render before measurement caught it.

- `render_sequence` must call `scene.frame_set(frame)`; `write_still` renders
  the *current* frame, so without it every output is identical.
- `ShaderNodeMath` MULTIPLY_ADD silently falls back to defaults; spell constants
  as explicit MULTIPLY then ADD/SUBTRACT so a wrong value is visible.
- A `VectorMath` SUBTRACT with a `default_value` set **and** a link on the same
  socket uses the link and drops the default — a sheared field (hard diagonal
  seam) instead of a disc.
- A ColorRamp Fac takes a SCALAR. Feeding it the raw UV vector makes Blender
  average x and y, giving a diagonal gradient, not a vertical one.
- A ColorRamp **clamps** its Fac to 0..1, so a negative signal becomes 0 and a
  white-at-0 stop turns the whole surface opaque.
- A horizontal pinch needs `ABS`. Without it the negative half of `uv.x*2-1`
  clamps to the opaque stop and the left half of every card is solid.
- Multiplying several EASE ramps gives a smooth gradient, not fire. Use one
  hard threshold on the noise.
- Noise Scale is cycles across the input; UV spans 0..1, so a high scale is
  sub-pixel at 128px and averages flat.
- `wipe()` must remove suffixed leftovers; a plain select-all/delete leaves
  `SF_Flame_00.001` objects accumulating as invisible geometry.
- Sheets are packed top-down; tiles are pasted without flipping.
- Blender's image pixel API is bottom-up. `verify_all.py` flips packed sheet
  pixels back to top-down before indexing frames, or loop checks compare the
  wrong tiles.
- Blender exits 0 even when it cannot open a `--python` script.
- `Phaser.Scale.RESIZE` sizes to the parent's measured box; as a flex child
  that can be the full document height, pushing the effect off-screen. Use
  `FIT` with explicit dimensions.
- A *linked* `.blend` breaks silently if its source asset is missing. Blender
  opens the scene with the link unresolved and renders nothing. `doctor.py`
  should be extended to check links before a linked rig is trusted.

## Adding a sub-program

1. `vfx/<id>/effect.json` — copy an existing one; it is the only place layout,
   blend mode, layer notes and known issues live.
2. `tools/<name>.py` — `import shield_rig`, compose layers. Per-card materials
   when a layer animates independently.
3. Register `(id, script stem)` in `EFFECTS` in `tools/build.py`.
4. **Add the id to `EFFECT_MATERIAL` in `verify_all.py`.** Skipping this fails
   the build by design (see below).
5. `python tools/build.py <id>`
6. `vfx/<id>/README.md` — layers, frame timing, measured values, known issues.

`pack_sheets.py --write-index` adds it to the viewer sidebar.

### Three ways this goes wrong, and why the tools fail loudly

These were found by simulating a new agent following this document, not by
reading it. Each one had passed a "clean" verification before the guard was
added.

**A new effect is invisible to verification.** `verify_all` used to iterate
`vfx/index.json` only, so an effect that had not been packed yet was never
checked and the run reported PASS. It now discovers sub-programs from the
filesystem and fails on any effect with an `effect.json` that the index does
not list, telling you to run `pack_sheets.py --write-index`.

**An unregistered material gets the wrong gates.** A new effect that is not in
`EFFECT_MATERIAL` silently inherits the fire thresholds. For a cool or
green-tinted effect that is exactly backwards, and the symptom is a confusing
"washed out" failure on correct output — the same trap that made the ice shield
look non-conforming. An unregistered material is now a hard failure naming the
two tables to edit.

**A green build can still be a garbage build.** `build.py` requires the build
script's own completion line, not just a zero exit code, because Blender exits 0
even when it cannot open a `--python` script.

Together these mean: if `python tools/build.py` says PASS, the sub-program was
built, is registered, has an index entry, has a declared material, and met the
gates for that material. What it still cannot tell you is whether the effect
looks right — that is what the human review gate is for.

## Not a sub-program

Authoring scenes, workbenches and lookdev files are legitimate in the repo and
are not required to satisfy the contract. Keep them out of `vfx/index.json` or
the viewer and verifier will try to consume artefacts that do not exist.

`shield_ice_lifecycle` is the current example: six `.blend` files staging a
cast/idle/impact/break timeline, with no manifest and no sheets. It becomes a
sub-program when it gains an `effect.json` and produces sheets.

## Engine target

The browser preview is **Phaser 4**, the engine the web game runs. This repo is
not the web workspace, so `tools/serve.py` resolves a Phaser build and serves
it at a virtual `/__phaser/` route that the viewer's import map points at. An
import map is parsed before any page script runs, so the substitution has to
be server-side.

Game-side integration is **not** done for any sub-program. The Phaser wiring,
blend conventions and occupant-container parenting are specified but
unimplemented.

The in-game Unity VFX layer (`docs/architecture/vfx-ssot.md` in the game repo)
is a **separate** system, spec-locked to generated textures with no asset
pipeline. These sheets are not for it.
