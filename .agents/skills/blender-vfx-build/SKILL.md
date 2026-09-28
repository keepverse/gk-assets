---
name: blender-vfx-build
description: Build or modify a Blender VFX sub-program in gk-assets - author a flame/layer rig, animate it, render a sprite sequence, and pack sheets. Use when asked to create a new VFX effect, change an existing one's timing or look, fix a render that looks wrong, drive Blender from the CLI, or target multiple Blender MCP ports. Triggers on "new vfx", "add effect", "shield flame", "smoke shader", "sprite sheet for <effect>", "the fire looks flat/wrong", "rebuild the effect", "Blender CLI", "multiple Blender instances", "MCP port".
---

# Building a VFX sub-program

## Before you start

Read `vfx/README.md`. It documents the rig and nine traps that each produced a
visibly wrong render. Skipping it costs several debug cycles.

Run `python tools/doctor.py` if anything misbehaves — it isolates the setup
failure modes (no Blender, dead MCP bridge, missing pip package) before you
start reading tracebacks.

## Workflow

1. **Pick the Blender.** Never hardcode it.

   ```bash
   python tools/blender_path.py --all
   ```

2. **Author** in `tools/<name>.py`, importing `shield_rig`. One collection per
   layer, per-card materials when a layer animates independently (a shared
   material cannot give two cards different keyframed values).

3. **Register** `(id, script stem)` in `EFFECTS` in `tools/build.py`. The script
   name is not always the effect id: `shield_fire_idle` → `shield_idle`.

4. **Build, pack and verify in one step:**

   ```bash
   python tools/build.py <id>
   ```

   That runs build → pack → verify in the only order that works, and refuses to
   report success when a build did not actually render. Do not hand-roll the
   three commands; that is how stale sheets ship.

5. **Look at it.** `python tools/serve.py` then open the printed URL. Or read
   `vfx/<id>/preview/composite_0007.png` directly.

6. **It is done.** `verify_all` passing means built and verified — correct
   shape, colour, frame count, closed loop. That is finished work, and nothing
   gates on a human sign-off. If the owner wants one recorded,
   `python tools/review_ui.py` opens the viewer with a sign-off bar; see the
   `vfx-human-review` skill. Never approve it yourself.

7. **Write the brief** in `vfx/<id>/README.md`: layers, frame timing, measured
   values, known issues.

## Registering a new effect

Add `(id, script stem)` to `EFFECTS` in `tools/build.py`, and add the id to
`vfx/index.json` via `pack_sheets.py --write-index`.

If the effect is a new **material**, also add a `MATERIAL_GATES` entry and an
`EFFECT_MATERIAL` key in `verify_all.py` — the gates are per material, not
global. Saturation is mean(R−B), a warmth axis: fire is positive, frost glass
is legitimately negative. Measure the new effect's distribution before setting
thresholds, and record the numbers in `vfx/README.md`.

## Measuring, not eyeballing

This is the rule that matters. An effect that "looks like fire" measured a fill
ratio of 0.925 — a solid rounded rectangle that passed visual review. Eyeballing
a sprite on a white page is unreliable; the eye cannot tell pale orange from
white.

Useful discriminators, all cheap to compute from a render's alpha channel:

| Property | Flame wants | A block/disc gives |
|---|---|---|
| fill ratio (lit / bounding box) | 0.25–0.70 | ~1.0 |
| silhouette raggedness (radius by angle) | > 0.18 | ~0.02 |
| alpha std | > 0.22 | low, or bimodal |
| frac alpha > 0.9 | < 0.12 | high |
| saturation (mean R−B) | > 0.40 | < 0.28 (washed) |
| bbox height / width | > 0.45 | < 0.3 (flat band) |

`tools/test_flame_card.py` does this for a single card and prints the
histogram. Copy that pattern for a new layer.

## Common failures and their causes

| Symptom | Cause |
|---|---|
| Card renders as a solid rectangle | Noise Fac sits above the gamma ramp's upper stop. Check the noise's *measured* range, not its nominal scale. |
| Left half of a card is solid | `\|uv.x*2-1\|` without `ABS` — the negative half clamps to the opaque stop. |
| Everything transparent | Ramp polarity inverted for the signal feeding it. Distance needs white-at-centre. |
| Whole card is one flat colour | A ColorRamp Fac fed the raw UV *vector*; Blender averages x and y, giving a diagonal. Use Separate XYZ. |
| Pale / washed out | AgX view transform, or emission strength > 1.0 clipping. |
| Diagonal seam | VectorMath SUBTRACT with a `default_value` AND a link on the same socket — the link wins and the default is dropped. |
| All 30 frames identical | Missing `scene.frame_set(f)`; `write_still` renders the current frame. |
| Effect occupies a thin horizontal band | Cards wider than `2*pi*R / count`; the ring closes into a solid stripe. |
| Preview/verify says "no preview frames" | Build did not run, or ran from the wrong cwd. |

## Authoring rules that are not negotiable

- **Author at 512, deliver at 128.** `pack_sheets.py` downsamples. A 128px card
  is ~20–30px, so detail is sub-pixel and averages to a flat block.
- **Emission strength ≤ 1.0.** A sprite render writes shader RGB straight to
  the PNG. Above 1.0 every channel clips to white and the hue ramp is lost.
- **`view_transform = "Standard"`.** AgX is a filmic look that desaturates.
- **A few multiplied masks, not many.** Four multiplied EASE ramps give a
  smooth gradient, not fire. Use one hard threshold on the noise.
- **Cards rotate only if the mask is rotation-invariant.** UV-space masks
  rotate with the card, dragging the silhouette off-centre. Get life from the
  animated 4D noise `W` instead.

## Driving live Blender instances from the CLI

Use `tools/blender_mcp_cli.py` when an agent has no Blender MCP tools, when the
MCP session is attached to the wrong Blender, or when one command must reach
several Blender instances. It connects directly to the add-on's TCP bridge, so
it does not depend on the MCP stdio server or require reloading the MCP session.

Enable the Blender MCP add-on and start its bridge in each target Blender.
Give every instance a distinct port in the add-on preferences (the default is
`9876`), then pass those ports more than once:

```powershell
python tools/blender_mcp_cli.py --port 9876 --port 9877 --file tools/inspect_scene.py
```

The same code is sent concurrently to every listed port (up to 32 at once).
Inline code and stdin also work:

```powershell
python tools/blender_mcp_cli.py --port 9876 --code 'import bpy; result = {"version": bpy.app.version_string}'
Get-Content tools/inspect_scene.py -Raw | python tools/blender_mcp_cli.py --port 9876
```

The command prints one JSON response per target and exits non-zero if any
instance cannot be reached or returns an execution error. It uses only Python's
standard library. The default socket timeout is 300 seconds; override it with
`--timeout` for long renders. Each request must finish synchronously from the
client's perspective, the add-on limits request bodies to 10 MiB, and the CLI
caps a response at 64 MiB. The CLI exposes direct code execution; it does not
mirror Blender MCP's separate screenshot, inspection, and documentation tools.

This sends arbitrary Python to Blender. Keep the add-on listener on loopback or
another trusted network; the bridge has no authentication. The CLI does not
start Blender or start the add-on listener. For headless renders, continue to
use `tools/build.py` and `tools/blender_path.py`.

If the CLI cannot connect, check the selected port rather than assuming the
default is in use:

```powershell
Get-NetTCPConnection -LocalPort 9876,9877
```

## Rendering a local review video

For an MP4 review copy of an existing Blender scene, run:

```powershell
python tools/render_video.py --blend assets/vfx/<asset>/<scene>.blend
```

It reads the scene's frame range and frame rate by default and writes to ignored
`tmp/video/`. The renderer uses Blender's movie encoder when available; if that
Blender build lacks movie support, it renders temporary PNG frames and encodes
them with FFmpeg from `PATH`. It does not save changes to the source `.blend`.
This is separate from the sprite-sheet build and does not register an effect.

## Launching an isolated Blender session

When a task needs its own GUI process and bridge port, launch a fresh Blender
instance with:

```powershell
python tools/blender_mcp_launch.py
python tools/blender_mcp_launch.py --blend assets/vfx/earth_shield/rock_lookdev.blend
python tools/blender_mcp_launch.py --port 9884 --blender 'D:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
```

Without `--port`, the launcher selects a free port from `9876` through `9975`.
It prints the new Blender PID, port, and startup log path after the add-on bridge
starts. Pass that port to `blender_mcp_cli.py` to drive this instance. The
launcher starts a separate GUI process and starts the add-on server on that
port in process memory; it does not save the port into shared Blender user
preferences. It uses `tools/blender_path.py` by default and can override the
executable with `--blender`.

Each process has independent in-memory scene state. If two processes open and
save the same `.blend` path, they can still overwrite each other's file changes;
use separate file copies when the project data itself must be isolated.
