# Fire Shield - Idle v2

A transparent 3D globe holds a gentle fire crown around the actor. Blender's
native gas simulation provides the flames. Seven small emitters sit around the
upper half of the sphere; three brief surface eruptions and seven cinders add
life without turning the idle into a combat hit. The actor is intentionally
absent from the rendered asset.

**36 frames at 24 fps (1.5 s) · 128px gameplay cell · 6×6 sheet**

## Layers

| Layer | Blend | Content |
|---|---|---|
| `shell` | additive | Translucent shaded UV sphere and three curved front filaments. |
| `flames` | additive | Blender gas-domain fire with seven small emitters and warm blackbody light. |
| `bursts` | additive | Three staggered, small surface eruptions. |
| `embers` | additive | Seven cinders on closed paths. |

## Timing

- The simulation bakes frames 1–48. Frames 1–12 let the gas settle; frames
  13–48 become the delivered loop.
- The shell breathes once and the cinders trace closed paths over the 36
  delivered frames.
- The eruptions peak at 16%, 50%, and 83% of the loop.
- The `.blend` scene and `tools/shield_idle.py` are the source. The generated
  gas cache lives under ignored `tmp/fluid_fire_idle/`; run
  `python tools/build.py shield_fire_idle` to regenerate it and the sheets.

## Measured

`python tools/build.py shield_fire_idle` passes the packed-sheet verifier.
The 512px preview measures 7/255 alpha at the actor center and 105/255
maximum alpha in the fire layer at frame 24. Mean first-to-last alpha
difference is 0.0014 across the image (0.0032 in its upper quarter). The
review MP4 contains two 36-frame loops at 24 fps.

## Known issues

- The gas simulation may make the first and last delivered flames differ
  slightly; inspect the loop in the review video before final visual sign-off.
- The asset contains only the shield effect. The protected actor is added by
  the game.
