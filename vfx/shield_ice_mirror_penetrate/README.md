# Ice Shield — Mirror Penetrate

**State: machine-verified; human visual review pending.** This is
an actor-free, 36-frame one-shot at 24 fps, built from the saved three-crystal
Ice Mirror idle scene.

## Layers and timing

The scene carries over exactly three distinct hero crystals, five minor
shards, and eight snowflakes. The crystals continue bobbing vertically in
place while the projectile passes. The body remains the same full-size,
transparent, ground-pointing hex.

One faceted shard enters from the left, marks the screen at frame 8, crosses
the actor-sized center, and exits at frame 20. Each puncture has its own short
prism glint, pulse, and angular fracture. The screen silhouette stays
continuous between the two localized events.

| Frames | Response |
|---|---|
| 1–7 | Projectile approaches the left edge |
| 8–13 | Entry flash and local fracture |
| 14–19 | Projectile crosses the shield center |
| 20–27 | Exit flash and second local fracture |
| 28–36 | Projectile and puncture accents clear |

The actor is omitted. Entry and exit points are fixed for this prototype.

## Measured sheet

Across all 36 packed composites, warmth is **−0.414 to −0.410**, white
fraction **0.000–0.004**, fill **0.452–0.554**, raggedness **0.133–0.199**,
and height/width **0.828–1.010**. The verifier samples frames 9, 21, and 33:

| Measure | Frame 9 | Frame 21 | Frame 33 |
|---|---:|---:|---:|
| Warmth (mean R−B) | −0.412 | −0.414 | −0.412 |
| White fraction | 0.003 | 0.001 | 0.001 |
| Fill | 0.532 | 0.504 | 0.452 |
| Silhouette raggedness | 0.142 | 0.196 | 0.190 |
| Height / width | 1.000 | 1.000 | 0.828 |

All sampled frames pass the Ice material and shape gates. The composition uses
a measured per-effect raggedness floor of **0.12** and fill ceiling of **0.60**.
The held body and rim are declared static in the manifest; their identical
tiles are checked explicitly.

## Known issues

- Entry and exit points are fixed; arbitrary projectile paths are not authored.
- Human review of the two-puncture readability is pending.

Build with: python tools/build.py shield_ice_mirror_penetrate
