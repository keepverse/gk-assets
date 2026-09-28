# Ice Shield — Mirror Impact

**State: machine-verified; human visual review pending.** This is
an actor-free, 24-frame one-shot at 24 fps. It reuses the Ice Mirror idle's
full-size, downward-pointing hex screen and breaks a small region around one
upper-right hit. The three idle crystals are not duplicated in this sprite.

## Motion and layers

The single `ice` layer keeps the translucent screen steady while a localized,
uneven fracture opens from the impact point. Five unequal angular branches and
two short offshoots stay near the contact; there is no repeated cell pattern or
full-screen web. Eight mirror facets use visibly varied size scales from 0.46
to 0.88, with bevelled edges and raised triangulated faces. They lift forward
from the screen, tilt in depth, catch blue light, and fade by frame 19. The fracture
stays visible during the separation and fades by frame 22, returning to the
quiet screen.

| Frames | Response |
|---|---|
| 1–2 | Intact hex holds |
| 3–6 | Contact flashes; uneven fractures open |
| 6–14 | Eight mixed-size facets lift and rotate toward camera |
| 15–19 | Facets drift apart and fade |
| 20–22 | Fracture marks fade; hex returns to quiet state |
| 23–24 | Quiet hex hold |

The contact direction is fixed to the upper-right for this prototype. Whether
the game needs other directions or a transformable impact is an open review
question; the sprite remains actor-free and centered on the same origin as the
idle screen.

The same fracture and facet response is also composed into the 72-frame Ice
Mirror idle scene, where the three existing hero crystals remain visible and
continue their vertical bubble motion through the hit.

The screen geometry and procedural frost-haze texture come from the shared
Ice Mirror screen builder. The shield stays at full scale throughout. Real
3D shard thickness, face normals, bevels, and area-light highlights carry the
depth cue; only the local fracture treatment moves and fades.

## Measured sheet

Across all 24 packed cells, warmth (mean R−B) is **−0.427 to −0.411**, white
fraction **0–0.005**, fill **0.612–0.622**, raggedness **0.030–0.048**, and
height/width **1.143**. The verifier samples frames 3, 8, and 14; they measure:

| Measure | Frame 3 | Frame 8 | Frame 14 |
|---|---:|---:|---:|
| Warmth (mean R−B) | −0.413 | −0.424 | −0.415 |
| White fraction | 0.000 | 0.000 | 0.000 |
| Fill | 0.618 | 0.614 | 0.613 |
| Silhouette raggedness | 0.038 | 0.045 | 0.042 |
| Height / width | 1.143 | 1.143 | 1.143 |

All sampled cells pass the Ice material and shape gates. The regular hex uses
the same narrow geometry exception as the Ice Mirror deploy screen: minimum
raggedness **0.025** and maximum fill **0.63**. The fracture and lifted facets
stay within the hex silhouette. The one-shot layer has **21 distinct tiles out
of 24**, with the remaining repetition coming from the quiet screen hold.

Build, pack, and verify with:

```powershell
python tools/build.py shield_ice_mirror_impact
```

Per-frame sequences and composite previews are regenerable review output and
remain ignored. Human visual review over a game-like background is pending.
