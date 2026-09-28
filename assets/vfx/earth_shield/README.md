# Earth Shield rock material kit

## Concept: rubble constellation

The shield is a loose orbit of three compact guardian stones, not a closed
brown bubble. They circle the actor at staggered heights and depths, with only
two small chips trailing each stone. The tighter orbit and larger gaps keep the
actor as the focal point. On a hit, a few chips can snap outward and pull back
into the orbit. A later shield shader can add a brief amber or moss-green glint
at the stones' inner edges; the source textures stay matte and earthy.

The material kit gives the hero stones different silhouettes a matching but
varied geology: dark basalt with warm mineral seams, layered ochre sandstone,
moss caught in dark creases, and a quartz-veined shard. Reuse these looks for
small debris, with simpler geometry and varied scale. The different palettes
also make individual objects readable while orbiting quickly.

## Current deliverable

This is the reusable rock material kit and source scene for the registered
actor-free idle and combat sprite effects under `vfx/shield_earth_*`. Each
texture set is an independent square UV material source, and the scene shows
how the maps read on separate low-poly satellites. The texture generator is
deterministic:

```powershell
python tools/generate_earth_shield_textures.py
python tools/generate_earth_shield_textures.py --size 2048
```

The default output is `assets/vfx/earth_shield/textures/`. Pass `--seed-offset`
to make a new reproducible set, or `--out` to write elsewhere.

## Texture sets

| Object material | Intended use | Surface character |
|---|---|---|
| `Rock01_BasaltHeart` | Largest orbit anchor | Charcoal basalt, broken warm-brown mineral seams |
| `Rock02_SandstonePlate` | Broad, flatter orbit stone | Rust and ochre sediment bands |
| `Rock03_MossboundStone` | Earthy color accent | Dark stone with restrained olive lichen patches |
| `Rock04_QuartzSeam` | Smaller angular shard | Brown-gray stone with thin muted quartz veins |

Each set contains five maps named `T_EarthShield_<object>_<map>.png`:

- `BaseColor` — sRGB color input.
- `Roughness` — non-color grayscale input.
- `NormalGL` — tangent-space OpenGL normal (`+Y` green channel); connect through
  a Normal Map node.
- `Height` — non-color grayscale input for a restrained Bump node.
- `AO` — soft cavity cue; use lightly if the lighting setup needs it.

The maps tile at their image borders, so UV seams do not introduce a hard color
or normal discontinuity. Start with the material's height plugged into a Bump
node at low distance; tune its distance and normal strength against the eventual
rock size. Keep the color, normal and height sources beside the Blender objects
when those are authored; packed images alone are not source assets.

## Orbit blockout scene

`earth_shield_orbit.blend` is the reusable rock-material scene. It contains
three individually named, rounded hero stones, two separate angular trailing
chips attached to each hero, three tilted orbit planes with constant-speed
drivers, viewport-only orbit guides, and a non-rendering actor scale proxy. The
stones are smaller and orbit closer to the actor than the first five-stone
blockout. Each orbit completes one full loop every 144 frames at 24 fps. The
stones use basalt, sandstone, and moss-bound textures; the quartz texture stays
available for future incoming projectiles. All maps use relative links to the
source PNGs in `textures/`.

Rebuild the scene from the generator:

```powershell
& (python tools/blender_path.py) --background --factory-startup --python tools/earth_shield_orbit.py
```

Or send it to a running instance with:

```powershell
python tools/blender_mcp_cli.py --port 9876 --file tools/earth_shield_orbit.py
```

The actor, camera, lights, and orbit curves are lookdev guides; the actor proxy
and curves are hidden from renders.
This blockout establishes scale, spacing, and material assignments, not the
final game mesh, collision, or shield animation.

## Dome shell material

The base scene also contains the reusable shader `M_ES_DomeShell`. The idle
scene uses it on an open hemispherical shell. The shader uses Eevee blended
transparency, very low sage-tinted shell opacity,
procedural mineral mottling and seams, a warm white-gold Fresnel rim, and a
bright reveal band. Its reveal mask reads world-space Z for bottom-up shield
growth.

The named value nodes are the current look controls: `ES_RevealHeight` moves the
reveal front upward, `ES_RevealWidth` sets its thickness, `ES_ShellOpacity`,
`ES_RimOpacity`, and `ES_VeinOpacity` tune surface visibility, and
`ES_FrontOpacity` / `ES_FrontGlowStrength` tune the traveling edge.
`ES_IdlePhase` animates the procedural earth noise slowly during the active
state; `ES_IdleRimGlow` and `ES_SeamGlow` set its quieter idle glints. The idle
and combat scene builders drive these values from controller properties so the
material stays reusable and its shader values remain easy to inspect.

## Idle animation and video review

[`shield_earth_idle.blend`](../../../vfx/shield_earth_idle/shield_earth_idle.blend)
adds an open hemispherical shell and a six-second idle cycle to the orbit scene.
At 24 fps, the shield grows from the ground over frames 3–32, holds with
restrained mineral and rim motion through frame 82, retracts from the crown over
frames 86–106, then rests hidden through frame 144. The stones keep orbiting
while the dome is hidden. The material's animated values are driven by
`ES_Shield_IdleControl`; the shell does not fade in or out. The source builder
is `tools/earth_shield_idle.py`.

Build or refresh the scene, then render an MP4 review copy:

```powershell
& (python tools/blender_path.py) --background --factory-startup --python tools/earth_shield_idle.py
python tools/build.py shield_earth_idle
python tools/render_video.py --blend vfx/shield_earth_idle/shield_earth_idle.blend --output tmp/video/earth_shield_idle.mp4 --resolution-scale 65
```

`tools/render_video.py` is the reusable Blender-to-MP4 entry point. It reads
the scene's frame range and frame rate by default, uses Blender's movie encoder
when available, and otherwise renders temporary PNG frames and encodes them
with FFmpeg from `PATH`. It does not save changes to the source `.blend`. Its
default output is `tmp/video/<scene-name>.mp4`; `tmp/` is ignored so review
videos stay local. The gameplay sheet is 72 frames at 12 fps, sampled every
other source frame. It contains only the dome and orbiting stones; the actor
proxy remains in the scene for scale but never appears in the video or sheet.

## Combat VFX

The actor-free combat set is built from the idle scene and reuses its three
guardian stones, transparent dome, and stone textures. It contains impact,
break, absorb, penetrate, and deflect reactions. Each is a separate 2D sprite
sheet; incoming rocks are represented by textured stones, while the actor stays
out of the rendered assets.
