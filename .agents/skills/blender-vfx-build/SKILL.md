---
name: blender-vfx-build
description: Build or modify a Blender VFX sub-program in gk-assets - author a flame/layer rig, animate it, render a sprite sequence, and pack sheets. Use when asked to create a new VFX effect, change an existing one's timing or look, or fix a render that looks wrong. Triggers on "new vfx", "add effect", "shield flame", "smoke shader", "sprite sheet for <effect>", "the fire looks flat/wrong", "rebuild the effect".
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

6. **Write the brief** in `vfx/<id>/README.md`: layers, frame timing, measured
   values, known issues.

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

## MCP note

If an interactive tool reports "cannot connect" to Blender, the server is
usually fine and the *bridge* is dead. Check
`Get-NetTCPConnection -LocalPort 9876`; if nothing is listening, start the
MCP Bridge Server from Blender's MCP preferences and tick Auto Start.
