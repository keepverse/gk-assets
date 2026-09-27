# Fire Shield - Impact

The shield absorbs a hit. One-shot, does not loop.

**24 frames @ 24fps (1.0s) · 128px cell · 6×4 sheet**

## Reading

A flare punches at the contact point, a ripple of bright beads races around the
barrier from that point, the flames recoil away from the impact and spring back,
and sparks arc off under gravity.

## Timing

```
 1-3   flare punches at the contact point
 2-13  ripple travels around the ring
 4-14  flames recoil outward from the hit
 5-21  sparks arc away and fade
12-24  flames settle back to idle height
```

## Layers

| Layer | Blend | What it does |
|---|---|---|
| `core` | additive | Small pool that brightens with the hit. Kept small on purpose — at 2.6x it became a second pale egg competing with the flare. |
| `flames` | additive | 14 cards; the recoil is weighted by angular distance from `HIT_ANGLE` so the hit reads as directional. |
| `rim` | additive | 20 beads travelling around the ring from the hit, brightest mid-travel. |
| `flare` | additive | The contact flash at `HIT_ANGLE` (+X). Decay stretched to frame 14 so later sheet cells still carry the glow. |
| `sparks` | additive | 16 particles with drag and gravity, staggered delays 2-7. |

## Known issues

- The hit direction is baked at +X. Striking from the left needs a mirrored
  sheet or a horizontal flip in game.
- Ripple beads travel 0.85 of a revolution, not all the way round, so there is a
  seam on the far side.
- Flames recoil by scaling down; a real recoil would also displace the card's
  noise pattern so the fire does not simply shrink.
