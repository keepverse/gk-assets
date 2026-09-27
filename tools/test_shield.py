"""
Measure a rendered shield composite against hard criteria.

An eyeball check kept passing things that were obviously wrong (a near-solid
"flame" with fill ratio 0.925 read as a rounded rectangle). This asserts the
properties a fire shield actually needs.

    blender --background --python blender/tools/test_shield.py -- <effect_dir>
"""

import os
import sys

import bpy
import numpy as np

PARAMS = {
    # authored at RES 512, downscaled by pack_sheets to this
    "gameplay_res": 128,
    "min_saturation": 0.28,   # mean (R-B) over lit pixels; washed-out fails
    "max_white_frac": 0.14,   # fraction of lit pixels that are near-white
    "min_fill": 0.10,         # of the bounding box; a thin wisp fails
    "max_fill": 0.62,         # a solid blob fails
    "min_ragged": 0.16,       # silhouette varies with angle; a disc is ~0.05
    "min_height_ratio": 0.45, # dome bbox height / width; a flat band fails
}


def measure(path):
    img = bpy.data.images.load(path)
    img.reload()
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    # Blender's buffer row 0 is the BOTTOM. Keep native order.
    arr = buf.reshape(h, w, 4).copy()
    bpy.data.images.remove(img)

    a = arr[..., 3]
    rgb = arr[..., :3]
    sel = a > 0.05
    if not sel.any():
        return None

    vals = a[sel]
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

    sat = float((rgb[..., 0] - rgb[..., 2])[sel].mean())
    white = float(((rgb[..., 0] > 0.93) & (rgb[..., 1] > 0.90))[sel].mean())
    fill = float(len(vals)) / float(bw * bh)

    return {
        "bbox": [bw, bh],
        "height_ratio": round(bh / float(bw), 3),
        "fill": round(fill, 3),
        "ragged": round(ragged, 3),
        "saturation": round(sat, 3),
        "white_frac": round(white, 3),
        "alpha_std": round(float(vals.std()), 3),
        "coverage": round(float(sel.mean()), 4),
    }


def main(argv):
    if not argv:
        print("usage: test_shield.py <effect_dir>")
        return 2
    fx = os.path.abspath(argv[0])
    prev = os.path.join(fx, "preview")
    if not os.path.isdir(prev):
        print("no preview dir: %s" % prev)
        return 1
    frames = sorted(f for f in os.listdir(prev) if f.endswith(".png"))
    if not frames:
        print("no preview frames")
        return 1

    # sample the loop, skipping the first and last which are loop boundaries
    picks = [frames[i] for i in (2, 6, 11, 16, 21) if i < len(frames)]
    rows = []
    worst = None
    for fn in picks:
        m = measure(os.path.join(prev, fn))
        if m is None:
            print("  %s: EMPTY" % fn)
            return 1
        rows.append((fn, m))
        # aggregate: a frame fails if ANY criterion is missed
        bad = []
        if m["saturation"] < PARAMS["min_saturation"]:
            bad.append("sat %.3f < %.2f" % (m["saturation"], PARAMS["min_saturation"]))
        if m["white_frac"] > PARAMS["max_white_frac"]:
            bad.append("white %.3f > %.2f" % (m["white_frac"], PARAMS["max_white_frac"]))
        if not (PARAMS["min_fill"] <= m["fill"] <= PARAMS["max_fill"]):
            bad.append("fill %.3f outside %.2f-%.2f" % (m["fill"], PARAMS["min_fill"], PARAMS["max_fill"]))
        if m["ragged"] < PARAMS["min_ragged"]:
            bad.append("ragged %.3f < %.2f" % (m["ragged"], PARAMS["min_ragged"]))
        if m["height_ratio"] < PARAMS["min_height_ratio"]:
            bad.append("h/w %.3f < %.2f" % (m["height_ratio"], PARAMS["min_height_ratio"]))
        if bad:
            worst = worst or (fn, bad)

    for fn, m in rows:
        print("  %s  bbox=%s h/w=%.2f fill=%.3f ragged=%.3f sat=%.3f white=%.3f"
              % (fn, m["bbox"], m["height_ratio"], m["fill"], m["ragged"],
                 m["saturation"], m["white_frac"]))

    if worst:
        print("\nFAIL on %s:" % worst[0])
        for b in worst[1]:
            print("   -", b)
        return 1
    print("\nRESULT: PASS (%d frames)" % len(rows))
    return 0


if __name__ == "__main__":
    # Blender passes: --background --factory-startup --python <this.py> -- <args>
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    argv = [a for a in argv if a and not a.lower().endswith(".py")]
    sys.exit(main(argv))
