# Fire Shield - Rotate

Baked Z-axis turntable. This is the sub-program that proves 3D-in-2D works.

**36 frames @ 24fps (1.5s per revolution) · 128px cell · 6×6 sheet · loops**

## The technique

A 2D game cannot render a 3D dome, so we bake one:

1. The flame ring is a real 3D arrangement — 16 cards on a cylinder of radius
   0.44 around the unit.
2. The camera is **orthographic**, so the projection is a true parallel view and
   there is no perspective skew as the rig turns. A perspective camera would
   shear the dome off-centre across the turntable.
3. The 36 frames are baked to one sheet and played as a looping sequence. The
   game needs no engine work at all.

## Two cues make it read as rotation

- **The cards genuinely travel.** Back cards move to the sides, front cards
  travel across, so the silhouette changes every frame.
- **Depth-keyframed emission.** Each card has its own material copy whose
  emission strength is driven by its position on the cylinder (0.22 at the back,
  1.0 at the front). Without this the turntable reads as a wobble rather than a
  rotation. It is a keyframed emission, not real lighting — the cards do not
  shade each other.

## The viewer's width curve

The sheet is square, but a turning dome is not: widest face-on, narrowest
edge-on. The manifest declares:

```json
"projection": { "mode": "turntable", "turntableSteps": 36, "spinAxis": "Z" }
```

and the viewer scales sprite width by `cos(turn)` per frame (floored at 0.22 so
the edge-on frame does not collapse to a sliver). Without it a 36-frame sheet
plays as a wobble, because every frame is an identical square sprite.

## Layers

| Layer | Blend | What it does |
|---|---|---|
| `core` | additive | Stays centred, shimmers. Does not rotate. |
| `flames` | additive | 16 cards on the cylinder, depth-keyframed emission. |
| `rim` | additive | 20 beads on the same cylinder, scaling with depth. |

## Known issues

- Card height is fixed at build time from each card's *starting* depth, so a card
  that starts at the back and rotates to the front keeps the short height it was
  built with. Fixing this means keyframing the mesh scale, not the object scale.
- The depth cue is emission, not lighting. It sells a still sequence but a
  consumer wanting true self-shadowing would need a real light and a Cycles bake.
- Phase 2 (8 fixed camera angles for genuine parallax) is the natural upgrade and
  reuses this rig unchanged — it only adds render passes.
