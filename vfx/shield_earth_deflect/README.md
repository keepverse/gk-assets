# Earth Shield — Deflect

> **State: machine verification pending; human review pending.** This is an
> actor-free, one-second sprite effect at 24 fps.

## Layers and timing

The single `earth` layer shows a textured stone approaching the shield, a
brief tight shock arc, and the stone turning away with a short warm trail. The
contact peaks around frames 5–9 and clears by frame 16. A few chips accent the
impact without filling the frame. The actor and scale guides are hidden from
the render.

## Measured sheet

Across all 24 packed cells, warmth is **0.081–0.118**, white fraction
**0**, fill **0.392–0.582**, raggedness **0.520–0.771**, and height/width
**0.530–0.650**. The verifier samples frames 3, 8, and 14; all three pass the
Earth material and shared shape gates.

## Known issues

- Redirect direction and debris density have not yet been reviewed in motion.

Build with `python tools/build.py shield_earth_deflect`.
