# Earth Shield — Break

> **State: machine verification pending; human review pending.** This is an
> actor-free, 1.5-second sprite effect at 24 fps.

## Layers and timing

The single `earth` layer composites a brief mineral flash, a segmented curved
dome fracture, and the three guardian stones with trailing fragments. The
fracture appears around frames 5–9; a restrained set of shell panels, stones,
and chips travel outward from frames 9–36. Panel scale and debris count are
held low so the shield break does not fill the actor's full gameplay cell. The
actor and scale guides are hidden from the render.

## Measured sheet

Across all 36 packed cells, warmth is **0.078–0.158**, white fraction
**0–0.006**, fill **0.114–0.579**, raggedness **0.282–0.718**, and height/width
**0.528–0.828**. The verifier samples frames 3, 6, and 10; fill at frame 10 is
**0.564**, below the shared 0.62 ceiling. All sampled cells pass the Earth
material and shared shape gates.

## Known issues

- Visual breakup and debris density have not yet been reviewed in motion.

Build with `python tools/build.py shield_earth_break`.
