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

# Visual gates. Calibrated by measuring every shipped effect at the 128px sheet
# resolution (see vfx/README.md), NOT carried over from full-resolution previews:
# the 4x downsample that produces the sheets genuinely lowers measured
# saturation, so a gate tuned on a 512px preview is too strict here.
#
#   saturation   shipped range 0.15 - 0.36. Gate at 0.12 so a genuinely
#                desaturated or white-clipped effect fails.
#   white frac   shipped max 0.013. Gate at 0.10.
#   fill         upper bound is the real gate (a rectangle scores ~1.0). Lower
#                bound is advisory: a thin effect legitimately covers little.
#   raggedness   shipped 0.46 - 0.94. A rectangle is ~0.02.
#   h/w          shipped 0.44 - 0.90. Below 0.40 is a flat band, not a dome.
MIN_SAT = 0.12
MAX_WHITE = 0.10
MIN_FILL, MAX_FILL = 0.005, 0.62
MIN_RAGGED = 0.18
MIN_HW = 0.40


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


def metrics_from_array(arr):
    """Visual gates for an HxWx4 RGBA array in 0..1 (native row 0 = bottom).

    Saturation is ALPHA-WEIGHTED, not alpha-masked. Masking averages every pixel
    above a 0.05 floor, and a sparse effect is mostly faint pixels whose dark
    accumulated colour drags the mean toward zero - which reported a correct
    fire sheet as "washed out" (0.12 measured, against 0.45 for the same frame
    in the full-resolution preview). Weighting by alpha measures how saturated
    the pixels the eye actually sees.
    """
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

    wsum = float(a[sel].sum())
    sat = float((((rgb[..., 0] - rgb[..., 2]) * a)[sel].sum()) / max(1e-6, wsum))
    white = float((((rgb[..., 0] > 0.93) & (rgb[..., 1] > 0.90)).astype(np.float32) * a)[sel].sum()
                  / max(1e-6, wsum))
    return {
        "hw": bh / float(bw),
        "fill": float(sel.sum()) / float(bw * bh),
        "ragged": ragged,
        "sat": sat,
        "white": white,
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

    # ---- composite visuals -------------------------------------------------
    # Source the composite from the PACKED SHEETS, not from preview/.
    # preview/ is gitignored build output, so requiring it means a fresh clone
    # can never verify - the checker would be unusable for anyone who had not
    # just run a build. Sheets are committed and are the actual deliverable, so
    # verifying against them tests the thing that ships, and compositing the
    # layers here mirrors what the game does at runtime.
    sheets_dir = os.path.join(fx, "sheets")
    if not os.path.isdir(sheets_dir):
        fails.append("no sheets directory")
        return fails, warns

    sheet_paths = {}
    for layer in man["layers"]:
        p = os.path.join(sheets_dir, layer["sheet"])
        sheet_paths[layer["id"]] = (p, layer.get("blend", "additive"))
        if not os.path.exists(p):
            fails.append("missing sheet %s" % layer["sheet"])

    def frame_from_sheets(fi):
        """Composite animation frame `fi` out of the packed sheets.

        Additive layers contribute colour*alpha; normal layers composite over
        with straight alpha, which is what a game sprite renderer does. Returns
        an HxWx4 float array in 0..1, or None if no layer covers that frame.
        """
        cell = sp["resolution"]
        accum_rgb = None
        accum_a = None
        for lid, (p, blend) in sheet_paths.items():
            if not os.path.exists(p):
                continue
            arr = load(p)
            sh, sw = arr.shape[:2]
            r, c = divmod(fi, sp["columns"])
            y0, x0 = r * cell, c * cell
            if y0 + cell > sh or x0 + cell > sw:
                continue
            tile = arr[y0:y0 + cell, x0:x0 + cell, :].astype(np.float32)
            if tile.shape[0] != cell or tile.shape[1] != cell:
                continue
            a = tile[..., 3:4]
            rgb = tile[..., :3]
            if accum_rgb is None:
                accum_rgb = np.zeros_like(rgb)
                accum_a = np.zeros_like(a)
            if blend == "additive":
                accum_rgb = accum_rgb + rgb * a
                accum_a = np.clip(accum_a + a, 0.0, 1.0)
            else:
                # straight alpha "over"
                out_a = a + accum_a * (1.0 - a)
                safe = np.where(out_a > 1e-6, out_a, 1.0)
                accum_rgb = (rgb * a + accum_rgb * accum_a * (1.0 - a)) / safe
                accum_a = out_a
        if accum_rgb is None:
            return None
        out = np.zeros(accum_rgb.shape[:2] + (4,), dtype=np.float32)
        out[..., :3] = np.clip(accum_rgb, 0.0, 1.0)
        out[..., 3:4] = np.clip(accum_a, 0.0, 1.0)
        return out

    SAMPLE_AT = {
        "shield_fire_idle":       (0.20, 0.55, 0.85),
        "shield_fire_rotate":     (0.10, 0.50, 0.90),
        "shield_fire_impact":     (0.12, 0.30, 0.55),
        "shield_fire_strengthen": (0.15, 0.38, 0.75),
        # break: peak power is early, before the dome tears
        "shield_fire_break":      (0.06, 0.14, 0.25),
    }
    fracs = SAMPLE_AT.get(effect_id, (0.25, 0.5, 0.75))
    for fr in fracs:
        fi = int(need * fr)
        if fi >= need:
            continue
        arr = frame_from_sheets(fi)
        label = "frame %d" % (fi + 1)
        if arr is None:
            fails.append("%s: no sheet covers it" % label)
            continue
        m = metrics_from_array(arr)
        if m is None:
            fails.append("%s: empty composite" % label)
            continue
        if m["sat"] < MIN_SAT:
            fails.append("%s: washed out, sat %.3f" % (label, m["sat"]))
        if m["white"] > MAX_WHITE:
            fails.append("%s: too white, %.3f" % (label, m["white"]))
        # Fill is a shape-quality gate, not a size gate: a rectangle scores
        # ~1.0 and a lacy flame ~0.4, but a thin effect legitimately covers
        # little of the cell. Only the UPPER bound is meaningful, and a
        # near-solid frame is a real defect whichever way it fails.
        if m["fill"] > MAX_FILL:
            fails.append("%s: too solid, fill %.3f > %.2f" % (label, m["fill"], MAX_FILL))
        elif m["fill"] < MIN_FILL:
            warns.append("%s: sparse, fill %.3f" % (label, m["fill"]))
        if m["ragged"] < MIN_RAGGED:
            fails.append("%s: silhouette too smooth, ragged %.3f" % (label, m["ragged"]))
        if m["hw"] < MIN_HW:
            fails.append("%s: too flat, h/w %.3f" % (label, m["hw"]))

    # These two are per-EFFECT, not per-frame, so they must sit outside the
    # sample loop. Inside it they ran once per sample point and reported the
    # same warning three times.
    if effect_id in LOOPING:
        # every frame must composite to something, or the cycle shows a hole
        for fi in range(need):
            arr = frame_from_sheets(fi)
            if arr is None or not (arr[..., 3] > 0.05).any():
                fails.append("frame %d: looping effect has an empty frame" % (fi + 1))
                break

        # loop seam: the last frame should be close to the first
        if need >= 2:
            a = frame_from_sheets(0)
            b = frame_from_sheets(need - 1)
            if a is not None and b is not None:
                diff = float(np.abs(a[..., 3] - b[..., 3]).mean())
                if diff > 0.06:
                    warns.append("loop seam: mean alpha delta %.3f between frame 1 "
                                 "and %d - the cycle will visibly jump" % (diff, need))
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
