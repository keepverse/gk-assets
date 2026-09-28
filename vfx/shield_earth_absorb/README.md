# Earth Shield — Absorb

> **State: machine verification pending; human review pending.** This is an
> actor-free, 1.5-second sprite effect at 24 fps.

## Layers and timing

The single `earth` layer lets the textured stone approach alone through frame
8 and impact near the dome's center at frame 9. The contact circle, dome glow,
and first absorb accents begin at frame 10, after the incoming stone reaches
the shield. From frames 11–27, the stone and a few fragments are pulled into
the central contact point; the effect clears by frame 31. The actor and scale
guides are hidden from the render.

## Measured sheet

Across all 36 packed cells, warmth is **0.082–0.097**, white fraction
**0–0.002**, fill **0.505–0.595**, raggedness **0.475–0.749**, and height/width
**0.479–0.613**. The verifier samples frames 10, 17, and 28; those frames have
fill **0.512, 0.518, 0.543**, respectively, and pass the Earth material and
shared shape gates.

## Known issues

- Absorption readability has not yet been reviewed over gameplay backgrounds.

Build with `python tools/build.py shield_earth_absorb`.
