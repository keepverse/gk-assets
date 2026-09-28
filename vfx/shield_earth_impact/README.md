# Earth Shield — Impact

> **State: machine verification pending; human review pending.** This is an
> actor-free, one-second sprite effect at 24 fps. The game composes it at the
> protected actor's origin.

## Layers and timing

The single `earth` layer composites the transparent mineral dome with a compact
warm shock ring, a short fracture flare, and a few stone chips. The contact
response peaks around frames 4–8 and clears by frame 18; the remaining frames
hold the quiet shield silhouette for a clean one-second sheet. The actor and
scale guides are hidden from the render.

## Measured sheet

Across all 24 packed cells, warmth is **0.083–0.134**, white fraction
**0**, fill **0.495–0.573**, raggedness **0.509–0.737**, and height/width
**0.528–0.613**. The verifier samples frames 3, 8, and 14; all three pass the
Earth material and shared shape gates.

## Known issues

- Visual response has not yet been reviewed over the game's backgrounds.

Build with `python tools/build.py shield_earth_impact`.
