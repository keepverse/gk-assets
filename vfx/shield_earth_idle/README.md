# Earth Shield — Idle

> **State: machine-verified; human review pending.** The final deliverable is
> one actor-free, 72-frame transparent sheet at 12 fps. The Blender source
> cycle is six seconds at 24 fps; the sprite renderer samples every other frame.

The idle effect combines a very light mineral dome and three individually
textured stones, with two small trailing chips attached to each stone. The
stones are smaller and orbit closer to the actor, who remains the focal point.
They continue their orbit while the dome is hidden. The actor proxy remains a
non-rendering guide in the Blender scene so the composition keeps its intended
scale and center.

The dome begins with a bright ground-level reveal, expands over frames 3–32,
holds with restrained material motion through frame 82, retracts from the crown
over frames 86–106, then remains hidden until the next cycle. The stones make
one full orbit every six seconds, independently of the dome state. The 145th
Blender frame is the exact orbital and shader wrap point; the rendered scene
uses frames 1–144, and the sheet samples source frames 1, 3, ..., 143.

The source scene is
[`shield_earth_idle.blend`](shield_earth_idle.blend). It links three rock
material sets from [`assets/vfx/earth_shield/textures`](../../assets/vfx/earth_shield/textures/)
and includes the dome shader and animation controls. The rock kit's base scene
is [`earth_shield_orbit.blend`](../../assets/vfx/earth_shield/earth_shield_orbit.blend).

## Measured sheet

Across all 72 packed cells, warmth (mean R−B) is **0.085–0.132**, white
fraction **0–0.003**, fill **0.098–0.589**, raggedness **0.159–0.972**, and
height/width **0.215–0.885**. The verifier samples frames 15, 37, and 62; they
measure warmth **0.087, 0.085, 0.118**, fill **0.534, 0.572, 0.199**,
raggedness **0.732, 0.717, 0.429**, and height/width **0.585, 0.528, 0.475**.
All sampled cells pass the Earth warmth/white thresholds and shared shape
gates. The measured loop seam delta is **0.010**.

Build, pack, and verify the sheet in the normal pipeline:

```powershell
python tools/build.py shield_earth_idle
```

That renders 72 frames at 512 px, packs them into an 8×9 grid of 128 px cells,
and runs `verify_all.py`. `sequences/` and review outputs are regenerated and
ignored by Git; only the final sheet, source scene, manifest, and brief are
deliverables.

Regenerate a local review video from the same six-second Blender scene:

```powershell
python tools/render_video.py --blend vfx/shield_earth_idle/shield_earth_idle.blend --output tmp/video/earth_shield_idle.mp4 --resolution-scale 65
```

The MP4 is review-only and remains under ignored `tmp/`. No human sign-off is
recorded here; that belongs to the person reviewing the effect in motion.
