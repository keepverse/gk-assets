# Ice Shield — Mirror Absorb

**State: machine-verified; human visual review pending.** This is
an actor-free, 36-frame one-shot at 24 fps, built from the saved three-crystal
Ice Mirror idle scene.

## Layers and timing

Exactly three distinct hero crystals, five minor shards, and eight snowflakes
are carried over from the idle. The crystals keep their vertical bubble motion
through the full response. The shield is the same cold, transparent,
ground-pointing hex at full size.

The projectile arrives from the left and contacts near the shield center at
frame 9. It holds there until the cold lock begins after contact. Four small
faceted frost flecks then draw inward as the projectile shrinks and dissolves.
The absorption completes around frame 30.

| Frames | Response |
|---|---|
| 1–8 | Projectile approaches |
| 9–12 | Contact; projectile pauses before the cold lock |
| 13–22 | Cold lock brightens; frost flecks emerge |
| 23–30 | Projectile and flecks draw inward and dissolve |
| 31–36 | Quiet shield hold |

The actor is omitted. The contact location is fixed near center for this
prototype.

## Measured sheet

Across all 36 packed composites, warmth is **−0.414 to −0.410**, white
fraction **0.000–0.004**, fill **0.504–0.554**, raggedness **0.137–0.199**,
and height/width **0.934–1.010**. The verifier samples frames 9, 17, and 31:

| Measure | Frame 9 | Frame 17 | Frame 31 |
|---|---:|---:|---:|
| Warmth (mean R−B) | −0.412 | −0.411 | −0.412 |
| White fraction | 0.003 | 0.001 | 0.002 |
| Fill | 0.532 | 0.509 | 0.526 |
| Silhouette raggedness | 0.142 | 0.197 | 0.187 |
| Height / width | 1.000 | 1.010 | 0.981 |

All sampled frames pass the Ice material and shape gates. The composition uses
a measured per-effect raggedness floor of **0.12** and fill ceiling of **0.60**.
The held body and rim are declared static in the manifest; their identical
tiles are checked explicitly.

## Known issues

- Contact location is fixed near center; directional variants are not authored.
- Human review of the pause-before-absorption timing is pending.

Build with: python tools/build.py shield_ice_mirror_absorb
