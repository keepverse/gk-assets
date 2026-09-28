# Ice Shield — Mirror Screen Deploy

**State: machine-verified; human visual review pending.** This actor-free,
transparent one-shot is the shield body: one cold blue, equal-sided hexagonal
mirror screen with a soft frost haze and a restrained icy rim.

## Motion

The screen starts as a small hex at the actor center, expands to full size,
holds, then fades without collapsing. The saved Blender scene has a 42-frame
range at 12 fps (3.5 seconds):

| Frames | Screen state |
|---|---|
| 1–9 | Grows from 2.5% scale to full size; reaches 0.78 opacity at frame 9 |
| 10–27 | Holds at full size and peak opacity |
| 28–42 | Smoothly fades at full size; frame 42 reaches zero opacity |

The scene timeline audit measured scale **1.0** at both frame 9 and frame 42,
opacity **0.78** through frame 27, and opacity **0.0** at frame 42. It also
confirmed that the screen does not collapse during the fade.

## Material and texture

The body uses the dedicated procedural RGBA texture
[`T_IceShield_MirrorHexScreen_RGBA.png`](../../assets/vfx/ice_shield/textures/mirror_screen_v1/T_IceShield_MirrorHexScreen_RGBA.png).
Its subtle low-frequency frost haze adds cold blue variation without hard
interior seams, spokes, or cells. The six body vertices form equal sides of
1.72 Blender units; the single cyclic rim has six equal sides of 1.90 units.
Both contours are checked by the builder. There is no inset ring. The rim uses
a cool cyan emission material at less than full opacity. The fixed rotation
puts the upper and lower corners on the vertical axis, with the lower corner
pointing toward the ground.

The texture is reproducible with:

```powershell
python tools/generate_ice_mirror_screen_texture.py
```

## Measured sheet

The packed 128px sheets pass `tools/verify_all.py`. Composite samples from the
packed sheets measure:

| Measure | Frame 11 | Frame 22 | Frame 34 |
|---|---:|---:|---:|
| Fill | 0.622 | 0.622 | 0.078 |
| Warmth (mean R−B) | −0.337 | −0.337 | −0.218 |
| Silhouette raggedness | 0.030 | 0.030 | 0.121 |
| Height / width | 1.143 | 1.143 | 1.143 |
| White fraction | 0.000 | 0.000 | 0.000 |

The equal-sided hex, with a vertex pointing up and another toward the ground,
has a packed-sheet radial-variation value of **0.0298**.
Its six body sides measure 1.72 units each within 0.00000002; the rim sides
measure 1.90 units each within 0.00000006. The verifier keeps shared shape
gates for other effects and uses a documented 0.025 raggedness floor and 0.63
fill ceiling only for this regular-hex design; aspect checks remain active.

At the 128px gameplay cell, mean composite alpha is **0.03529** during the
full-size hold (frame 22), **0.02198** during the fade (frame 34), and **0.0**
at frame 42. At frame 22, 30.6% of pixels exceed 0.05 alpha. The screen uses
low opacity so the actor can remain visible through it in game.

## Build and review

The production scene is
[`shield_ice_mirror_deploy.blend`](shield_ice_mirror_deploy.blend). Rebuild,
pack, and verify it with:

```powershell
python tools/build.py shield_ice_mirror_deploy
```

Per-frame sequences and flat previews are ignored and regenerated on each
build. A local review video is also ignored under `tmp/video/`:

```powershell
python tools/render_video.py --blend vfx/shield_ice_mirror_deploy/shield_ice_mirror_deploy.blend --output tmp/video/ice_mirror_deploy_review.mp4 --resolution-scale 65
```

Review the screen over a bright game background. The pale frost rim may need
contrast tuning there; no human sign-off has been recorded.
