# Ice Shield Object Kit

This is a small Blender-ready asset kit, not a precomposed effect sheet. Each
`.blend` file contains one reusable mesh object in its own named collection:

| Asset | Object | Use |
|---|---|---|
| `ice_shield_shell.blend` | `ICE_SHIELD_SHELL` | Open-bottom, faceted frostglass shell. The actor remains visible through the low-opacity panels and deliberate gaps. |
| `ice_shield_rim.blend` | `ICE_SHIELD_RIM` | One continuous front/back arch edge; it replaces rows of separate glow beads. |
| `ice_crystal_shard.blend` | `ICE_SHIELD_SHARD` | One elongated faceted shard, intended as a restrained crown accent or a sparse reusable accent elsewhere. |

## Which version is current

**The three files above are the current canopy kit.** The legacy
`shield_ice_idle` scene links exactly these. The new mirror-flow effect uses
the separate `ice_mirror_flow.blend` source scene below.

The upstream repo accumulated `v2/`, `v3/` and `v4/` copies of the same three
meshes as lookdev history. Those are **not** shipped and are **not** linked. They
remain in the game monorepo at
`D:\Works\source\plant-vs-zombie-rise-of-summoner\blender\assets\vfx\ice_shield\`
for reference. If you need an older pass, take it from there deliberately — do
not copy a versioned directory in here and leave the reader guessing which is
current.

## Rules

- **A packed texture is not a source file.** If a `.blend` has a packed texture,
  the original image must exist under `textures/`.
- **Edit the source, then rerun the builder.** `tools/shield_ice_build.py`
  rebuilds the composition and sheets from these files; do not hand-edit the
  generated `shield_ice_idle.blend` or the change is lost on the next build.
- **Links are relative.** Scenes reference these with `//` paths, so moving
  the kit breaks them silently — Blender opens the scene with the link
  unresolved and renders nothing.

The assets are geometry plus procedural materials; they have no external texture
dependencies. Their origins are aligned for easy placement: the shell and rim
start at the ground plane, while the shard is centered around its own midpoint.
The idle scene links the collections from these source files, so the animation
does not copy their meshes or turn their geometry into a swarm.

## Mirror-flow authoring scene

[`ice_mirror_flow.blend`](ice_mirror_flow.blend) is the unanimated source scene
for `shield_ice_mirror_idle`. It contains three reusable, faceted mirror guard
collections (A, B, and C), a viewport-only actor and shield-field guide, the
orthographic camera, and studio lighting. The production idle uses one hero
crystal from each collection, keeping the count at exactly three. They bob up
and down in fixed vertical lanes around the actor; they do not orbit, descend,
or form repeated rows.

The prepared source scene contains three distinct major crystal collections,
one collection for each hero variant, plus five minor shards, eight snowflake
cards, and a viewport-only actor guide. The production idle builder places
exactly one major crystal from each collection in a staggered guard formation.
Minor shards and snowflakes stay as local companions.

The `MirrorFace`, `PrismFrame`, and `GuardShard` texture sets in
[`textures/mirror_v1/`](textures/mirror_v1/) are assigned in the source scene.
Each set contains base color, roughness, OpenGL normal, emission, and height
maps. Regenerate the prepared scene and production effect from
`tools/ice_shield_mirror_scene.py` and `tools/shield_ice_mirror_build.py` with:

```powershell
python tools/build.py shield_ice_mirror_idle
```

`tools/generate_ice_mirror_textures.py` reproduces the source maps and their
ignored texture preview sheet.

## Not migrated

Three things upstream are referenced by older notes but were **not** brought into
this repo, because the migrated `shield_ice_idle` does not link them:

- `materials/ice_shield_v3.blend` — the V3 lifecycle's seven effect shaders,
  used by `shield_ice_lifecycle`, which is still a WIP staging folder rather
  than a sub-program.
- the `v2/`, `v3/`, `v4/` versioned object kits and their textures.
- `references/ice-shield-object-kit-concept.png` and the frostglass concept
  image — lookdev references, not render targets.

All of it remains in the game monorepo under
`blender/assets/vfx/ice_shield/`. Migrate deliberately when the lifecycle work
picks up, and update "Which version is current" at the same time.

Source textures and generated alternatives are indexed in
[`textures/`](textures/README.md).
