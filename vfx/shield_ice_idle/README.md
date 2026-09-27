# Ice Shield — Idle

> **Review state: machine-verified, awaiting human review.**
> The sheets were rebuilt (see [FIX-REPORT.md](FIX-REPORT.md)) and the look
> changed — deeper and more saturated than the version previously signed off.
> `review.json` was cleared rather than carried over, because the prior sign-off
> covered sheets that no longer exist.
>
> **Read [REVIEW-PACKET.md](REVIEW-PACKET.md) before reviewing.** It has the
> per-layer measurements and a side-by-side over both the lawn and the dark
> viewer background.
>
> To record the decision:
> `python tools/review.py shield_ice_idle --approve --by "<name>" --note "<what you saw>"`

The idle effect is assembled from the three standalone, linked assets in
[`assets/vfx/ice_shield`](../../assets/vfx/ice_shield/README.md). It
uses one instance of each: shell, continuous rim, and crown shard. The actor
space stays open; there are no free-floating motes, bead chains, or decorative
object swarms.

`shield_ice_lookdev.blend` is the reusable artist scene: it opens on a dark
navy world with the hero camera, cool key/fill/rim lights, named FX collections,
and a restrained Fog Glow compositor. `shield_ice_idle.blend` is the matching
transparent production scene used by the sprite build. Both link the three
standalone assets with relative paths; edit an object in its source asset file
and rerun the builder to refresh the composition and sprites.

The baseline idle shell uses procedural noise, Voronoi fracture lines, a Fresnel
edge response, a thin solidified facet edge, and restrained static edge emission.
That baseline has no external texture maps; its 512 px transparent render remains
the source for 128 px gameplay cells. The V2 workbench below separately links the
V2 assets and their frost-vein texture test.

`shield_ice_workbench.blend` is the reusable lifecycle authoring scene. It opens
on `SCN_IceShield_Workbench`, keeps the existing idle scene intact, and includes
linked V2 source-asset references, a non-rendering actor-origin guide, a 1024 px
transparent RGBA camera setup, and a 24 fps timeline divided into cast (1–24),
idle (25–48), impact (49–72), and break (73–96). The idle range contains the
linked shell, rim, and crown instances with their copied animation shifted to
frames 25–48. Cast, impact, and break collections are deliberate staging folders
for the next authoring pass, not completed effects. The saved opening state is
frame 36 in camera/material preview with scene lights and world enabled; still
renders use the relative prefix `//lookdev/ice_shield_workbench_frame0036`. The
current 1024 px transparent render is
[`lookdev/ice_shield_workbench_frame0036.png`](lookdev/ice_shield_workbench_frame0036.png).
The latest V2 shell pass is more saturated and uses broader facets; the idle
silhouette and the cast/impact/break effects still need their later authoring
passes.

See [visual-match.md](visual-match.md) for the comparison result and the detail
that still falls short of the concept.

## Build, pack and verify

From the repository root, the same as every other sub-program:

```bash
python tools/build.py shield_ice_idle
```

That runs build → pack → verify in one step. To do it by hand:

```bash
"$BLENDER" --background --factory-startup --python tools/shield_ice_build.py
python tools/pack_sheets.py --fx vfx/shield_ice_idle
"$BLENDER" --background --factory-startup --python tools/verify_all.py
```

`BLENDER` comes from `python tools/blender_path.py` — never hardcode it. This
install's build also writes three one-object source `.blend` files, the linked
idle and look-dev scenes, 512px isolated layer sequences, 512px transparent
composite previews, and a 1024px opaque look-dev still. The packer downsamples
the transparent frames to the 128px cells declared in `effect.json`.
`projection.mode` is `flat`: a fixed-camera 3D render, not a turntable.

## Review state

**Machine-verified. Not human-reviewed.** The sheets were regenerated and the
look changed, so the previous sign-off was cleared rather than carried over —
see [REVIEW-PACKET.md](REVIEW-PACKET.md) for the measurements and the
side-by-side, and `python tools/review.py --list` for the current state.

Re-review whenever the effect is rebuilt: a sign-off covers the sheets that
existed when it was given. `review.py` reports the machine result and flags it
as `stale` once the sheets change.

Runtime wiring is intentionally out of scope. The repository documents the
Unity `VfxDirector` path separately from this Blender-to-sprite/Phaser pipeline.
