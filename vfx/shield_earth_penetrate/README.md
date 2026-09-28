# Earth Shield — Penetrate

> **State: machine verification pending; human review pending.** This is an
> actor-free, 1.5-second sprite effect at 24 fps.

## Layers and timing

The single `earth` layer follows a textured stone through the dome. A small
entry fracture lands around frames 8–13, followed by a separate exit crack
around frames 20–25. The dome briefly brightens near each contact and returns
to its quiet state as the projectile leaves. The actor and scale guides are
hidden from the render.

## Measured sheet

Across all 36 packed cells, warmth is **0.067–0.122**, white fraction
**0–0.002**, fill **0.351–0.560**, raggedness **0.483–0.762**, and height/width
**0.479–0.613**. The verifier samples frames 5, 11, and 20; all three pass the
Earth material and shared shape gates.

## Known issues

- Front/back depth ordering needs human review against an actual character.

Build with `python tools/build.py shield_earth_penetrate`.
