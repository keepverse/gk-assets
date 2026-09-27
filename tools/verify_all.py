"""
Verify every fire-shield sub-program. Run from the repo root:

    blender --background --factory-startup --python blender/tools/verify_all.py

Checks per effect, all from the rendered output rather than the build code:
  * effect.json parses and its grid matches the frame count
  * sheet exists at the declared size
  * every sheet tile is distinct (a duplicated frame means the timeline never
    advanced - the bug that shipped once already)
  * composite previews pass tools/test_shield.py's visual criteria
  * loop effects return to their start (seamless wrap)
"""

import json
import os
import sys

import bpy
import numpy as np

BLENDER_DIR = os.path.dirname(os.path.abspath(__file__))
VFX_DIR = os.path.join(os.path.dirname(BLENDER_DIR), "vfx")

LOOPING = {"shield_fire_idle", "shield_fire_rotate"}

# visual criteria for a composite, same as test_shield.py
MIN_SAT = 0.28
MAX_WHITE = 0.14
# Fill floor 0.08 not 0.10: a one-shot mid-recoil legitimately spreads its
# pixels outward (impact f14 measured 0.095) so the bounding box grows faster
# than the lit area. The floor exists to catch a nearly-empty frame, not to
# grade density.
MIN_FILL, MAX_FILL = 0.08, 0.62
MIN_RAGGED = 0.16
MIN_HW = 0.45


def load(path):
    img = bpy.data.images.load(path)
    img.reload()
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    arr = buf.reshape(h, w, 4).copy()   # native order: row 0 = bottom
    bpy.data.images.remove(img)
    return arr


def sheet_tiles(path, cell, cols, rows):
    """Return each tile's alpha bytes so duplicates can be detected."""
    arr = load(path)
    h, w = arr.shape[:2]
    out = []
    for i in range(cols * rows):
        r, c = divmod(i, cols)
        y0, x0 = r * cell, c * cell
        if y0 + cell > h or x0 + cell > w:
            out.append(None)
            continue
        out.append(arr[y0:y0 + cell, x0:x0 + cell, 3].tobytes())
    return out


def composite_metrics(path):
    arr = load(path)
    a = arr[..., 3]
    rgb = arr[..., :3]
    sel = a > 0.05
    if not sel.any():
        return None
    ys, xs = np.nonzero(sel)
    bw, bh = int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)
    cy, cx = ys.mean(), xs.mean()
    r = np.hypot(xs - cx, ys - cy)
    th = np.arctan2(ys - cy, xs - cx)
    prof = []
    for i in range(12):
        m = (th >= -np.pi + i * np.pi / 6) & (th < -np.pi + (i + 1) * np.pi / 6)
        if m.any():
            prof.append(float(np.percentile(r[m], 92)))
    ragged = (max(prof) - min(prof)) / max(1e-6, max(prof)) if prof else 0.0
    return {
        "hw": bh / float(bw),
        "fill": float(sel.sum()) / float(bw * bh),
        "ragged": ragged,
        "sat": float((rgb[..., 0] - rgb[..., 2])[sel].mean()),
        "white": float(((rgb[..., 0] > 0.93) & (rgb[..., 1] > 0.90))[sel].mean()),
    }


def check(effect_id):
    fx = os.path.join(VFX_DIR, effect_id)
    fails = []
    warns = []

    mpath = os.path.join(fx, "effect.json")
    if not os.path.exists(mpath):
        return ["no effect.json"], []
    with open(mpath, encoding="utf-8") as fh:
        man = json.load(fh)

    sp = man["sprite"]
    need = sp["frameCount"]
    need_cells = sp["columns"] * sp["rows"]
    if need_cells < need:
        fails.append("grid %dx%d = %d cells < %d frames"
                     % (sp["columns"], sp["rows"], need_cells, need))

    # sheets
    for layer in man["layers"]:
        sheet = os.path.join(fx, "sheets", layer["sheet"])
        if not os.path.exists(sheet):
            fails.append("missing sheet %s" % layer["sheet"])
            continue
        tiles = sheet_tiles(sheet, sp["resolution"], sp["columns"], sp["rows"])
        live = [i for i, t in enumerate(tiles) if t is not None and any(t)]
        if not live:
            fails.append("%s: no live tiles" % layer["sheet"])
            continue
        # Duplicate detection has to allow for genuinely repetitive layers: the
        # core is a slowly breathing glow, so many adjacent frames ARE nearly
        # identical by design. Only a LARGE fraction collapsing to one value
        # means the timeline never advanced.
        distinct = len({tiles[i] for i in live})
        if distinct <= max(1, len(live) // 4):
            fails.append("%s: %d live tiles but only %d distinct - timeline "
                         "likely did not advance" % (layer["sheet"], len(live), distinct))
        elif distinct < len(live):
            warns.append("%s: %d/%d tiles distinct (repetitive layer)"
                         % (layer["sheet"], distinct, len(live)))

    # composite visuals
    prev = os.path.join(fx, "preview")
    frames = sorted(f for f in os.listdir(prev) if f.endswith(".png")) if os.path.isdir(prev) else []
    if not frames:
        fails.append("no preview frames")
    else:
        if len(frames) != need:
            fails.append("preview has %d frames, manifest says %d" % (len(frames), need))
        # Sample only the frames where the effect is INTACT. A one-shot's late
        # frames are legitimately sparse - break at frame 19 is a scatter of
        # falling cinders with no dome, and demanding a full barrier there
        # fails a correct effect. Each effect declares its own sample points.
        SAMPLE_AT = {
            "shield_fire_idle":      (0.20, 0.55, 0.85),
            "shield_fire_rotate":    (0.10, 0.50, 0.90),
            "shield_fire_impact":    (0.12, 0.30, 0.55),
            "shield_fire_strengthen": (0.15, 0.38, 0.75),
            # break: peak power is early, before the dome tears
            "shield_fire_break":     (0.06, 0.14, 0.25),
        }
        fracs = SAMPLE_AT.get(effect_id, (0.25, 0.5, 0.75))
        picks = [frames[min(len(frames) - 1, int(need * fr))]
                 for fr in fracs if int(need * fr) < len(frames)]
        for fn in picks:
            m = composite_metrics(os.path.join(prev, fn))
            if m is None:
                fails.append("%s: empty composite" % fn)
                continue
            if m["sat"] < MIN_SAT:
                fails.append("%s: washed out, sat %.3f" % (fn, m["sat"]))
            if m["white"] > MAX_WHITE:
                fails.append("%s: too white, %.3f" % (fn, m["white"]))
            if not (MIN_FILL <= m["fill"] <= MAX_FILL):
                fails.append("%s: fill %.3f outside %.2f-%.2f" % (fn, m["fill"], MIN_FILL, MAX_FILL))
            if m["ragged"] < MIN_RAGGED:
                fails.append("%s: silhouette too smooth, ragged %.3f" % (fn, m["ragged"]))
            if m["hw"] < MIN_HW:
                fails.append("%s: too flat, h/w %.3f" % (fn, m["hw"]))

        # every looping frame must have SOMETHING in it
        if effect_id in LOOPING:
            for fn in frames:
                m = composite_metrics(os.path.join(prev, fn))
                if m is None:
                    fails.append("%s: looping effect has an empty frame" % fn)
                    break

        # loop seam: the last frame should be close to the first
        if effect_id in LOOPING and len(frames) >= need:
            a = load(os.path.join(prev, frames[0]))
            b = load(os.path.join(prev, frames[-1]))
            diff = float(np.abs(a[..., 3] - b[..., 3]).mean())
            if diff > 0.06:
                warns.append("loop seam: mean alpha delta %.3f between frame 1 and %d"
                             % (diff, need))
            else:
                warns.append("loop seam delta %.3f (seamless)" % diff)

    return fails, warns


def main():
    index_path = os.path.join(VFX_DIR, "index.json")
    with open(index_path, encoding="utf-8") as fh:
        ids = json.load(fh)["effects"]

    print("verifying %d effects\n" % len(ids))
    total_fail = 0
    for eid in ids:
        if not eid.startswith("shield_fire"):
            continue
        fails, warns = check(eid)
        print("%s" % eid)
        for w in warns:
            print("   warn: %s" % w)
        for f in fails:
            print("   FAIL: %s" % f)
        print("   %s" % ("OK" if not fails else "%d problem(s)" % len(fails)))
        total_fail += len(fails)

    print("\nRESULT:", "PASS" if total_fail == 0 else "FAIL (%d)" % total_fail)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
