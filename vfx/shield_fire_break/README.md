# Fire Shield - Break

The shield fails. One-shot, does not loop.

**36 frames @ 24fps (1.5s) · 128px cell · 6×6 sheet**

## Reading

Structurally the inverse of impact: instead of a ripple travelling around an
*intact* ring, the ring is progressively **disabled arc by arc** from the breach
outward, while the dome contracts and sags.

```
 1-4   over-charge: the shield flares right before failing
 3-14  breach: an arc around the crack is extinguished
 4-20  collapse: the dome contracts 34% and sags
 5-23  shards: burning fragments blown out, tumbling under gravity
 3-36  tail: smouldering cinders carry the shot to its end
```

Each flame card dies on its own schedule, `die_at = 3 + (1-near)*11`, where
`near` is its angular proximity to the breach. That arc-by-arc extinction is what
separates a break from a fade-out.

## Layers

| Layer | Blend | What it does |
|---|---|---|
| `core` | additive | Over-charges to frame 4 then gutters out. Capped at 2.4x — higher and it became a pale egg wider than the barrier. |
| `flames` | additive | 16 cards, each dying progressively nearest-breach-first while the ring contracts and sags. |
| `rim` | additive | 20 beads going out on the same schedule, following the collapsing radius. |
| `crack` | additive | The tear at the breach. Uses the **flame shader**, not a radial glow — a radial mask on a tall card is a smooth ellipse that reads as a floating pill. |
| `shards` | additive | 20 tumbling fragments with drag and gravity, staggered delays 5-11. |
| `tail` | additive | 30 smouldering cinders. Without this every other layer finished by frame 19 and **18 of 36 sheet cells were blank**. |

## Known issues

- The breach angle is baked at +X.
- Cards die by scaling to zero, which reads as shrinking rather than burning
  out. A real extinguish would also desaturate each card, which the shared flame
  shader does not do per-card.
- The crack is a single card. A multi-card tear following the ring's curvature
  would read better, at the cost of a dedicated crack shader.
