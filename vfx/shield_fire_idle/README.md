# Fire Shield - Idle

Persistent aura. Loops seamlessly.

**24 frames @ 24fps (1.0s) · 128px cell · 6×4 sheet · loops**

## Layers

| Layer | Blend | What it does |
|---|---|---|
| `core` | additive | Small hot pool behind the flames (0.26 units, strength 0.6). |
| `flames` | additive | 14 upright cards on a ring of radius 0.42, card height scaled by ring depth. |
| `rim` | additive | 20 beads tracing the barrier edge on the same depth lift. |
| `embers` | additive | 10 embers rising with drag and fade-out. |

## Why it is a ring of cards, not a dome

A squashed sphere reads as a plastic ball at 128px regardless of shading. A ring
of upright flame cards with a **depth-lift stagger** (far side tall and raised,
near side short and low) reads as a volume enclosing something, and the rim
beads give it a boundary so it reads as a *barrier* rather than a fire cloud.

## Measured

From `verify_all.py`, 5 sampled frames:

```
saturation (R-B)     0.386 - 0.418
fill ratio           0.200 - 0.311
silhouette ragged    0.483 - 0.582
bbox h/w             0.63 - 0.71
white fraction max   0.064
loop seam (f1 vs f24 mean alpha delta)  0.020  -> seamless
```

## Tuning

`RADIUS`, `CARD_W`, `CARD_H` at the top of `tools/shield_idle.py`. Card width
must stay under `2*pi*R / RING` or the ring closes into a solid band — that is
what flattened an earlier build into a horizontal stripe.

## Known issues

- Rim beads read slightly as a chain of separate balls rather than a continuous
  edge. A continuous rim mesh would be cleaner but costs a separate alpha material.
- The dome silhouette comes entirely from the depth-lift stagger, not real 3D
  geometry, so rotating the unit would not rotate this shield. Use
  `shield_fire_rotate` when the unit turns.
