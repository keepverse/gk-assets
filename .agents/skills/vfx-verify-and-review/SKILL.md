---
name: vfx-verify-and-review
description: Verify and review VFX sub-programs in gk-assets - run the test suite, interpret a failure, compare renders, and decide whether an effect is shippable. Use when asked to check VFX work, review an effect, interpret a verify_all or test_flame_card failure, or judge whether a render is acceptable. Triggers on "verify", "check the vfx", "review the effect", "is this good enough", "why does verify fail", "test_viewer".
---

# Verifying and reviewing VFX

## Run the suite first

```bash
"$BLENDER" --background --factory-startup --python tools/verify_all.py
```

`verify_all.py` checks, from the rendered output rather than the build code:
manifest/grid agreement, that no layer's frames collapsed to duplicates,
composite saturation / fill / raggedness / aspect at frames where the effect is
*intact*, and that looping effects have no empty frame and close their loop.

Targeted checks:

```bash
python tools/test_viewer.py --serve   # does the preview boot and play?
```

```bash
# one card in isolation, large
"$BLENDER" --background --factory-startup --python tools/test_flame_card.py
```

`test_flame_card.py` is the fastest way to iterate on a *shader* without ring
composition confusing the read. It prints the alpha histogram and a PASS/FAIL
against explicit gates.

## Reading a failure

| Message | Meaning | Fix |
|---|---|---|
| `no preview frames` | The build did not run, or ran from the wrong cwd. | Run the build script from the repo root. |
| `N live tiles but only M distinct` | Timeline did not advance. | Missing `scene.frame_set(f)`. |
| `repetitive layer` (warn only) | A slowly-breathing layer is legitimately repetitive. | Ignore. |
| `washed out, sat 0.21` | AgX, or emission > 1.0 clipping. | Standard transform, clamp strength. |
| `fill 0.93` | Solid block, not fire. | Noise Fac is saturating the gamma ramp. |
| `silhouette too smooth` | Reads as a disc. | Add a hard threshold on the noise. |
| `too flat, h/w 0.31` | Horizontal band, not a dome. | Card width exceeds ring circumference / count. |
| `looping effect has an empty frame` | A visible hole in the cycle. | Extend the layer's lifetime. |
| `loop seam delta 0.4` | The cycle will visibly jump. | Make frame N match frame 1. |

## Reviewing visually

The eye is unreliable on transparent sprites over a white page — it cannot tell
pale orange from white. Two habits:

- **Preview on a mid-grey or lawn background**, not white. The game's lawn is
  bright, and additive effects wash out over it. `serve.py`'s background
  selector exists for this.
- **Read a `preview/composite_*.png` directly** when you want a still; do not
  judge from a downscaled screenshot of the viewer.

Ask specific questions rather than "does it look good":

- Is the silhouette ragged, or is it a smooth oval?
- Is there a visible hot core with a cooler rim?
- Do the layers have different lifetimes, or do they all peak together?
- For a one-shot: does it decay to nothing, or stop dead?

An effect where every layer peaks on frame 1 reads as one static image, not an
event. That is the most common compositional failure and no numeric gate
catches it — check the timing table by eye.

## Judging shippability

An effect is ready when:

1. `verify_all.py` passes.
2. `test_viewer.py` passes and the effect plays in the preview.
3. Every layer in `effect.json` has a real note, and `knownIssues` is either
   empty or genuinely informative — not a restatement of the description.
4. `README.md` states the timing, the measured values, and the known limits.

It is **not** ready if it only looks acceptable. If a property was tuned until
it looked right, it has not been verified.
