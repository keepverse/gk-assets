# Fire Shield - Strengthen

A power-up. One-shot, does not loop.

**30 frames @ 24fps (1.25s) · 128px cell · 6×5 sheet**

## Reading

**Inhale → burst → settle.** That is what separates a buff from an impact: an
impact starts bright and decays, a strengthen starts quiet and gets brighter.

```
 1-8   inhale   ring contracts to 0.82x and dims to 45%
 9-12  burst    ring snaps out to 1.30x at full brightness
13-20  overshoot settles from 1.30x back to 1.0x
21-30  holds at 1.06x, brighter than the pre-buff idle
```

The envelope is a piecewise function (`envelope()` in the script) so each phase
tunes independently rather than fighting one long curve.

## Layers

| Layer | Blend | What it does |
|---|---|---|
| `core` | additive | Follows the same envelope. |
| `flames` | additive | 14 cards driven by the envelope, plus a fast outward kick on frames 9-14 so the burst reads as an explosion rather than a zoom. |
| `rim` | additive | 20 beads snapping outward on the burst. |
| `sparks` | additive | 18 particles thrown on the burst, staggered delays 9-12, long-lived so the sheet's later cells carry embers. |

## Known issues

- Emission is capped at 1.0 by the rig rule, so brightness above "full" is
  expressed by scale and layer count rather than by over-driving emission. A
  hotter peak would need a second additive pass.
- Does not return to idle — it holds at 1.06x. A de-buff or a transition sheet
  would be needed to hand back to `shield_fire_idle`.
- The `sparks` layer is the only one alive after frame ~22; the sheet is
  intentionally thinner at the end.
