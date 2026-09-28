# Ice Shield — Mirror Deflect

**State: machine-verified; human visual review pending.** This is
an actor-free, 24-frame one-shot at 24 fps, built from the saved three-crystal
Ice Mirror idle scene.

## Layers and timing

The scene preserves exactly three distinct hero crystals, five minor shards,
and eight snowflakes from the idle. The crystals continue their vertical
bubble motion; none follows an orbit or falls in a row. The shield uses the
same full-size, transparent, ground-pointing hex.

One faceted projectile enters from the upper-right and contacts at frame 6. A
prism glint and tight pulse mark the hit. The projectile turns away at frame 8
and exits toward the upper-right with a short icy trail. The fracture and
trail fade by frame 20; the screen and crystals remain visible.

| Frames | Response |
|---|---|
| 1–5 | Shard approaches the screen |
| 6–8 | Contact glint and local pulse; projectile changes direction |
| 9–18 | Deflected shard clears with a short trail |
| 19–24 | Trail and contact accents clear |

The actor is omitted. Event direction is fixed to the upper-right for this
prototype.

## Measured sheet

Across all 24 packed composites, warmth is **−0.415 to −0.410**, white
fraction **0.000–0.002**, fill **0.438–0.554**, raggedness **0.127–0.199**,
and height/width **0.869–1.010**. The verifier samples frames 6, 8, and 18:

| Measure | Frame 6 | Frame 8 | Frame 18 |
|---|---:|---:|---:|
| Warmth (mean R−B) | −0.414 | −0.412 | −0.414 |
| White fraction | 0.001 | 0.002 | 0.001 |
| Fill | 0.529 | 0.523 | 0.492 |
| Silhouette raggedness | 0.127 | 0.131 | 0.192 |
| Height / width | 0.953 | 0.972 | 0.964 |

All sampled frames pass the Ice material and shape gates. The composition uses
a measured per-effect raggedness floor of **0.12** and fill ceiling of **0.60**.
The held body and rim are declared static in the manifest; their identical
tiles are checked explicitly.

## Known issues

- Contact direction is fixed; alternate impact locations are not yet authored.
- Human review of the redirect and trail at gameplay scale is pending.

Build with: python tools/build.py shield_ice_mirror_deflect
