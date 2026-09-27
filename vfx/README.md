# Fire Shield VFX

Five sub-programs covering a fire shield's full lifecycle. Blender authors them,
`sheets/*.png` are the deliverable, and the Phaser viewer previews them in the
same engine the web game runs.

| Sub-program | Frames | Role |
|---|---|---|
| `shield_fire_idle` | 24 | Persistent aura. Loops. |
| `shield_fire_rotate` | 36 | Baked Z turntable. Loops. Proves 3D-in-2D. |
| `shield_fire_impact` | 24 | Absorbs a hit. One-shot. |
| `shield_fire_strengthen` | 30 | Power-up. One-shot. |
| `shield_fire_break` | 36 | Shield fails. One-shot. |

## Build

Each is an independent script sharing `shield_rig.py`:

```bash
blender --background --factory-startup --python blender/tools/shield_idle.py
blender --background --factory-startup --python blender/tools/shield_rotate.py
blender --background --factory-startup --python blender/tools/shield_impact.py
blender --background --factory-startup --python blender/tools/shield_strengthen.py
blender --background --factory-startup --python blender/tools/shield_break.py

python blender/tools/pack_sheets.py --write-index
blender --background --factory-startup --python blender/tools/verify_all.py
python blender/tools/serve.py     # then open the printed URL
```

## The rig

A shield is **not a dome mesh**. It is a ring of upright flame cards around a
small hot core, with bright beads tracing the barrier's edge. A squashed sphere
reads as a plastic ball at 128px no matter how the shader is tuned.

Two things make the ring read as a volume rather than a stripe of fire:

- **Depth-lift stagger.** Cards on the far side of the ring are tall and raised,
  near-side cards short and low. With the 12-16 degree camera tilt that vertical
  stagger is what reads as a dome.
- **Rim beads.** A boundary of small bright dots. Without it the effect is a
  fire cloud; with it, it is a barrier.

## The 3D-in-2D technique

`shield_fire_rotate` is a real 3D card cylinder rendered with an **orthographic**
camera, so the projection has no perspective skew as the rig turns. Two cues sell
the rotation:

1. Cards genuinely travel around the ring, so the silhouette changes per frame.
2. Each card has its own material copy whose emission is keyframed by depth
   (0.22 at the back, 1.0 at the front). Without this it reads as a wobble.

The manifest declares `projection.mode = "turntable"`, and the viewer applies a
cosine width curve on top so the dome's projected width narrows and widens as it
turns. Playing a 36-frame sheet as plain squares loses that entirely.

A second phase — 8 fixed camera angles for true parallax — is the natural
upgrade and reuses the same rig; it only adds render passes.

## Conventions that are easy to get wrong

Every one of these was a real bug, caught by measurement rather than by eye.
They are all enforced or documented in `shield_rig.py`.

- **Author at 512, deliver at 128.** `pack_sheets.py` downsamples. At 128 a card
  is ~20-30px, so flame detail is sub-pixel and averages to a flat block.
- **`view_transform = "Standard"`.** AgX is a filmic look that desaturates; fire
  renders cream instead of orange.
- **Emission strength ≤ 1.0.** These are sprite renders: shader RGB is written
  straight to the PNG, so >1.0 clips every channel to white and destroys the hue
  ramp. Brightness above "full" is expressed by scale and layer count instead.
- **A ColorRamp Fac takes a SCALAR.** Feeding it the raw UV vector makes Blender
  average x and y, giving a *diagonal* gradient. Always Separate XYZ and take
  `.Y` for up, `.X` for across.
- **A ColorRamp CLAMPS its Fac to 0..1.** A negative signal becomes 0, so a
  white-at-0 stop turns the whole surface opaque. This produced a "solid
  rectangle" flame that took several passes to find.
- **The horizontal pinch needs ABS.** `|uv.x*2-1|` is 0..1 across the card; the
  raw value is -1..1 and the negative half clamps to the opaque stop, making the
  left half of every card a solid block.
- **Multiply few masks, not many.** Four multiplied EASE ramps produced a smooth
  gradient with fill ratio 0.925 — a rounded rectangle. Real fire needs one hard
  threshold on the noise so the body is genuinely opaque with genuinely empty gaps.
- **Noise Scale is cycles across the input.** UV spans 0..1, so Scale=11 on a card
  is sub-pixel at 128. The detail noise threshold is placed against its measured
  range (0..0.73, mean 0.51).
- **`scene.frame_set(f)` is mandatory in the render loop.** `write_still` renders
  the *current* frame; without advancing it every output is a copy of frame 1.
  This shipped once already.
- **`wipe()` must remove suffixed leftovers.** A plain select-all/delete leaves
  auto-suffixed objects (`SF_Flame_00.001`) that accumulate as invisible
  geometry inside the good ones.

## Verification

`verify_all.py` asserts, from the rendered output rather than the build code:

- `effect.json` parses and its grid covers its frame count
- every sheet tile is distinct (a large fraction collapsing to one value means the
  timeline never advanced)
- composite previews pass saturation / fill / silhouette-raggedness / aspect
  criteria, sampled at frames where each effect is *intact*
- looping effects have no empty frame and return close to their start

`test_flame_card.py` does the same for a single card, and `test_shield.py` for one
composite. Measured on the shipped set:

| Effect | saturation | fill | raggedness | h/w |
|---|---|---|---|---|
| idle | 0.39-0.42 | 0.20-0.31 | 0.48-0.58 | 0.63-0.71 |
| impact / strengthen / break / rotate | all pass the same gates |

The `core` layers legitimately have few distinct frames (7/24 for idle) — a
slowly breathing glow is repetitive by design, so the duplicate check allows it
and only fails on a large collapse.

## Integration

Not wired into the game. When it is:

- **Phaser** (the web game, `web/fusion-rpg-web`): `load.spritesheet` with the
  manifest's cell size, then `anims.create`. Route new sheets through
  `requestSceneTexture` in `sceneArtState.ts` — it owns the de-dupe/in-flight
  race a raw `load.spritesheet` would hit.
- **The shield should be a child of the occupant container**, not a scene-root
  object, so it inherits transform, scale and hit-area conventions. `BoardLayers`
  has an `overlays` layer at depth 3000 that is currently empty.
- **No blend modes exist in the game yet** (`setBlendMode` returns zero matches),
  so these additive sheets would establish that convention.
- There is **no y-sort**. The game has never needed one.
- The in-game Unity layer (`docs/architecture/vfx-ssot.md` §12) is a separate
  system, spec-locked to generated textures with no asset pipeline. These sheets
  are not for it.
