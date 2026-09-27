"""
Isolated single-flame-card test. Renders ONE card large and centred so the
shader can be judged without the ring's composition confusing the read.

    blender --background --python blender/tools/test_flame_card.py
"""

import os
import sys

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig   # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   os.pardir, "tmp", "flame_card")


def main():
    os.makedirs(OUT, exist_ok=True)
    rig.wipe()
    px = rig.setup_scene(res=512, ortho=0.34, tilt_deg=0.0, frames=1)
    cols = rig.collections("SF_Flames")

    mat, nt, detail, mapn, warp = rig.flame_mat(
        "M_TEST", (1.0, 0.55, 0.10), (0.42, 0.03, 0.00),
        cycles=6.0, gamma_lo=0.42, gamma_hi=0.85, warp=0.55)

    ob = rig.card("CARD", 0.221, 0.33, cols["SF_Flames"])
    ob.data.materials.append(mat)
    scene = bpy.context.scene
    scene.frame_set(1)
    p = os.path.join(OUT, "flame_card.png")
    scene.render.filepath = p
    bpy.ops.render.render(write_still=True)

    img = bpy.data.images.load(p)
    img.reload()
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    # Blender's buffer row 0 is the BOTTOM of the image. Do not flip.
    arr = buf.reshape(h, w, 4).copy()
    bpy.data.images.remove(img)

    a = arr[..., 3]
    rgb = arr[..., :3]
    sel = a > 0.02
    if not sel.any():
        print("RESULT: FAIL - card rendered nothing")
        return 1
    vals = a[sel]
    ys, xs = np.nonzero(sel)
    bw, bh = int(xs.max() - xs.min()), int(ys.max() - ys.min())

    # How ragged is the silhouette? A rectangle has a nearly constant radius
    # from its centroid; a flame tongue varies a lot with angle. This is the
    # single best discriminator and the one an eyeball check kept missing.
    cy_, cx_ = ys.mean(), xs.mean()
    r = np.hypot(xs - cx_, ys - cy_)
    th = np.arctan2(ys - cy_, xs - cx_)
    prof = []
    for i in range(12):
        m = (th >= -np.pi + i * np.pi / 6) & (th < -np.pi + (i + 1) * np.pi / 6)
        if m.any():
            prof.append(float(np.percentile(r[m], 90)))
    ragged = (max(prof) - min(prof)) / max(1e-6, max(prof)) if prof else 0.0

    # Fill ratio: a solid rectangle fills its bounding box, a lacy flame does not.
    fill = len(vals) / float(bw * bh)

    hist = [int(((vals >= lo) & (vals < lo + 0.1)).sum()) for lo in np.arange(0, 1.0, 0.1)]

    print("card rendered %dx%d px" % (bw, bh))
    print("  aspect (w/h)      = %.2f    want 0.45-0.85" % (bw / max(1, bh)))
    print("  silhouette ragged = %.3f    want > 0.18  (rectangle is ~0.02)" % ragged)
    print("  fill ratio        = %.3f    want 0.25-0.70 (rectangle is ~1.0)" % fill)
    print("  alpha std         = %.3f    want > 0.22" % vals.std())
    print("  frac > 0.9        = %.3f    want < 0.12" % (vals > 0.9).mean())
    print("  saturation R-B    = %.3f    want > 0.40" % (rgb[..., 0] - rgb[..., 2])[sel].mean())
    print("  alpha histogram   = %s" % hist)
    print("  -> %s" % os.path.abspath(p))

    ok = (0.45 <= bw / max(1, bh) <= 0.85
          and ragged > 0.18
          and 0.25 <= fill <= 0.70
          and vals.std() > 0.22
          and (vals > 0.9).mean() < 0.12
          and (rgb[..., 0] - rgb[..., 2])[sel].mean() > 0.40)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
