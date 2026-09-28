# Ice Shield — Mirror Bubble Idle

**State: machine-verified; human visual review pending.** The gameplay asset is
an actor-free, transparent 72-frame loop at 12 fps (6 seconds). The three
existing crystals keep their bubble motion while the shared hex-screen rig
deploys and receives one localized mirror impact per loop.

## Motion and scene

Exactly three prepared hero crystals stay on three staggered guard stations:
an offset crown and two lower guards. Both lower crystals are lifted, and the
left guard is spaced farther out so all three remain distinct throughout the
loop. Each crystal repeatedly bobs up and down on its own vertical lane for two
cycles per loop. Their horizontal travel is zero. There are no orbit paths or
path constraints.

The screen body, rim, and impact response are part of this same scene and
Blender file. The screen starts at actor center and reaches full size at frame
9. The impact glint begins at frame 9; its shards lift and tilt, then the
fracture clears by frame 28. The screen holds at full size through frame 27
and fades without collapsing by frame 42. It stays invisible for frames 43–72,
then reappears when the loop wraps; the crystals keep bobbing the whole time.
The lower vertex points toward the ground.

Five prepared minor shards and eight snowflake cards stay near those three
heroes as small drifting companions. They remain secondary; no new crystal
meshes are generated or duplicated by the animation builder. The impact is
composed on the same hex-screen rig and shares its frame range, so all three
hero crystals remain visible and bob during the hit. The actor and field guides
stay in Blender but are hidden from the render.

The 73-position rig audit (frames 1–73, including the loop endpoint) measured:

- Hero count: **3**; path constraints: **0**
- Vertical travel ranges: **0.5961, 0.5900, 0.6498 units**
- Horizontal travel ranges: **0, 0, 0 units**
- Minimum hero separation: **1.5100 units**
- Minimum formation triangle area: **1.6193 square units**
- Actor screen radius: **1.0080–1.7940 units**
- Loop endpoint error: **0.000000**

The crystals are built from the prepared source
[`ice_mirror_flow.blend`](../../assets/vfx/ice_shield/ice_mirror_flow.blend),
using the crystal textures in `mirror_v1/` and snowflake textures in
`snowflake_v1/`. The screen uses the procedural texture in
`mirror_screen_v1/`. The animation and merged scene rig are built by
`tools/ice_shield_mirror_scene.py`; screen construction comes from
`tools/ice_mirror_screen_build.py`, and the shared fracture/facet response comes
from `tools/ice_mirror_impact_build.py`.
Build, pack, and verify it with:

```powershell
python tools/build.py shield_ice_mirror_idle
```

## Measured sheet

The packed 128px sheets passed `tools/verify_all.py`. On sampled composite
frames 11, 37, and 62, respectively:

| Measure | Frame 11 | Frame 37 | Frame 62 |
|---|---:|---:|---:|
| Screen state | Impact contact | Fading | Hidden |
| Fill | 0.506 | 0.152 | 0.170 |
| Warmth (mean R−B) | −0.411 | −0.431 | −0.444 |
| Silhouette raggedness | 0.195 | 0.313 | 0.857 |
| Height / width | 1.000 | 0.924 | 0.648 |
| White fraction | 0.0010 | 0.0000 | 0.0000 |

The packed alpha difference between frame 1 and frame 72 is **0.00929**, within
the seamless-loop threshold.

The sheets are the deliverable. Per-frame `sequences/` and composite `preview/`
images are regenerated and ignored. A local MP4 for motion review is also
ignored under `tmp/video/`:

```powershell
python tools/render_video.py --blend vfx/shield_ice_mirror_idle/shield_ice_mirror_idle.blend --output tmp/video/ice_mirror_idle_impact_review.mp4 --resolution-scale 65
```

## Review

Please review the loop over a game-like background. Confirm that exactly three
large crystals bob vertically around the actor-sized empty center, with the
minor shards and snowflakes staying secondary. No human sign-off has been
recorded.
