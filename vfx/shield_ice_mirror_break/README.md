# Ice Shield — Mirror Break

**State: machine-verified; human visual review pending.** This is
an actor-free, 36-frame one-shot at 24 fps, built from the saved three-crystal
Ice Mirror idle scene.

## Layers and timing

Exactly three distinct hero crystals, five minor shards, and eight snowflakes
carry over from the idle, and the hero crystals keep their vertical bubble
motion through the break. The screen begins as the same full-size,
ground-pointing hex.

A compact upper-right hit starts the break. Three broad textured mirror
panels separate from the screen, catch light as they tilt in depth, and drift
out. Three small chips supply secondary detail. The face has three broad seams,
with no repeated web of cracks. The actor is omitted.

| Frames | Response |
|---|---|
| 1–4 | Intact hex holds |
| 5–9 | Contact flash and three broad seams |
| 10–19 | Three panels release and hold apart |
| 20–30 | Panels drift and turn; three small chips clear |
| 31–36 | Fragments and screen finish fading |

The hit location and panel layout are fixed for this prototype.

## Measured sheet

Across all 36 packed composites, warmth is **−0.444 to −0.403**, white
fraction **0.000–0.002**, fill **0.146–0.554**, raggedness **0.135–0.513**,
and height/width **0.748–1.019**. The verifier samples frames 6, 10, and 26:

| Measure | Frame 6 | Frame 10 | Frame 26 |
|---|---:|---:|---:|
| Warmth (mean R−B) | −0.409 | −0.408 | −0.430 |
| White fraction | 0.001 | 0.000 | 0.000 |
| Fill | 0.415 | 0.526 | 0.288 |
| Silhouette raggedness | 0.207 | 0.212 | 0.218 |
| Height / width | 0.981 | 0.981 | 0.991 |

All sampled frames pass the Ice material and shared shape gates. The body and
rim visibly change during the break, so they remain ordinary animated layers.

## Known issues

- Panel layout and hit location are fixed.
- Human review of panel separation and retained crystal readability is pending.

Build with: python tools/build.py shield_ice_mirror_break
