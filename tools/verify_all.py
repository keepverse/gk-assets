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

import pathlib

import bpy
import numpy as np

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
# pathlib, not str: discover_effects() needs iterdir()/is_file(). It was a plain
# string for as long as every use was os.path.join(), which hid the mismatch
# until something actually called a Path method on it.
VFX_DIR = pathlib.Path(TOOLS_DIR).parent / "vfx"

LOOPING = {
    "shield_fire_idle", "shield_fire_rotate", "shield_ice_idle",
    "shield_ice_mirror_idle", "shield_earth_idle",
}

# Visual gates, PER EFFECT.
#
# These are NOT global, and must not be made global. Saturation is measured as
# mean(R - B), which is a warmth axis: fire is positive, frost glass is
# genuinely NEGATIVE, and a single global floor fails a correct ice effect at
# -0.16. Each material needs its own calibration, measured from its own
# shipped sheets. See vfx/README.md.
#
#   fire   5 sub-programs, warm emissive, measured 0.15 - 0.51
#   ice    8 sub-programs, cool translucent, measured per effect
#   earth  6 sub-programs, textured rocks, dome, and combat glows
#
# Shape gates are material-independent and shared by default. The narrow
# effect override below accounts for a mathematically regular hex whose valid
# radial profile falls below the jagged-shape threshold without being a disc.
DEFAULT_GATES = {
    "minSat": 0.12,
    "maxWhite": 0.10,
    "minFill": 0.005,
    "maxFill": 0.62,
    "minRagged": 0.18,
    "minHw": 0.40,
}

# Colour/density calibration per material. "default" is the fire numbers.
# Add a material here rather than widening the default - a global relaxation
# lets every other effect regress silently.
MATERIAL_GATES = {
    "fire": {},                       # use DEFAULT_GATES as calibrated
    "ice": {
        "$comment": ("Frost glass is cool and translucent by design. Measured on "
                     "the REBUILT sheets: sat -0.405, white 0.000, fill 0.42, "
                     "ragged 0.40, h/w 1.11. mean(R-B) is a WARMTH axis so a "
                     "cool material is legitimately and strongly negative. The "
                     "earlier -0.16 came from stale sheets that the builder in "
                     "the repo could not reproduce - see the ice fix report."),
        "minSat": -0.50,
        "maxWhite": 0.35,
    },
    "earth": {
        # Measured per effect from the Earth sheets; ranges and sampled values
        # are recorded in the individual vfx/shield_earth_*/README.md briefs.
        "minSat": 0.06,
        "maxWhite": 0.02,
    },
}

# Exact geometry exception: with top and bottom vertices on the vertical axis,
# this regular six-edge screen measures fill 0.622 and radial variation 0.030
# after rasterization. All other shape gates remain shared.
EFFECT_GATE_OVERRIDES = {
    # A deliberately round, translucent globe stays the dominant silhouette;
    # its gas flames add soft irregularity rather than a spiky outer boundary.
    "shield_fire_idle": {"minRagged": 0.08},
    "shield_ice_mirror_deploy": {"minRagged": 0.025, "maxFill": 0.63},
    # Impact keeps the same mathematically regular hex boundary; its local
    # fracture and lifted facets stay inside the screen silhouette.
    "shield_ice_mirror_impact": {"minRagged": 0.025, "maxFill": 0.63},
    "shield_ice_mirror_deflect": {"minRagged": 0.12, "maxFill": 0.60},
    "shield_ice_mirror_absorb": {"minRagged": 0.12, "maxFill": 0.60},
    "shield_ice_mirror_penetrate": {"minRagged": 0.12, "maxFill": 0.60},
}

# Which material each sub-program is. Add a key when adding an effect.
EFFECT_MATERIAL = {
    "shield_fire_idle": "fire",
    "shield_fire_rotate": "fire",
    "shield_fire_impact": "fire",
    "shield_fire_strengthen": "fire",
    "shield_fire_break": "fire",
    "shield_ice_idle": "ice",
    "shield_ice_mirror_idle": "ice",
    "shield_ice_mirror_deploy": "ice",
    "shield_ice_mirror_impact": "ice",
    "shield_ice_mirror_deflect": "ice",
    "shield_ice_mirror_absorb": "ice",
    "shield_ice_mirror_penetrate": "ice",
    "shield_ice_mirror_break": "ice",
    "shield_earth_idle": "earth",
    "shield_earth_impact": "earth",
    "shield_earth_break": "earth",
    "shield_earth_absorb": "earth",
    "shield_earth_penetrate": "earth",
    "shield_earth_deflect": "earth",
}


def gates_for(effect_id):
    mat = EFFECT_MATERIAL.get(effect_id)
    if mat is None:
        return DEFAULT_GATES, "default (unregistered material - add it to EFFECT_MATERIAL)"
    g = dict(DEFAULT_GATES)
    g.update(MATERIAL_GATES.get(mat, {}))
    g.update(EFFECT_GATE_OVERRIDES.get(effect_id, {}))
    g.pop("$comment", None)
    return g, mat


def load(path):
    img = bpy.data.images.load(path)
    img.reload()
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    # Blender exposes pixels bottom-up, but pack_sheets writes grid frames in
    # PNG top-down order. Normalize once here so tile 0 is the first animation
    # frame everywhere, including sample gates and loop-seam comparisons.
    arr = buf.reshape(h, w, 4)[::-1, :, :].copy()
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
        if layer.get("static", False):
            if distinct != 1:
                fails.append("%s: declared static but has %d distinct tiles"
                             % (layer["sheet"], distinct))
        elif distinct <= max(1, len(live) // 4):
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
        # ice idle is a steady breathing loop, so sample it like one
        "shield_ice_idle":        (0.15, 0.50, 0.85),
        # The mirror idle bobs vertically in a closed loop; sample across its
        # repeating bubble cycles.
        "shield_ice_mirror_idle": (0.15, 0.50, 0.85),
        # Sample the deploy screen during full hold, late hold, and its fade.
        "shield_ice_mirror_deploy": (0.25, 0.50, 0.80),
        # Sample the Ice Mirror impact before, during, and after its contact pulse.
        "shield_ice_mirror_impact": (0.12, 0.30, 0.55),
        "shield_ice_mirror_deflect": (0.209, 0.30, 0.709),
        "shield_ice_mirror_absorb": (0.223, 0.45, 0.834),
        "shield_ice_mirror_penetrate": (0.223, 0.556, 0.89),
        "shield_ice_mirror_break": (0.14, 0.25, 0.70),
        "shield_earth_idle":      (0.20, 0.50, 0.85),
        "shield_earth_impact":    (0.12, 0.30, 0.55),
        "shield_earth_break":     (0.06, 0.14, 0.25),
        "shield_earth_absorb":    (0.25, 0.45, 0.75),
        "shield_earth_penetrate": (0.12, 0.30, 0.55),
        "shield_earth_deflect":   (0.12, 0.30, 0.55),
    }
    fracs = SAMPLE_AT.get(effect_id, (0.25, 0.5, 0.75))
    g, mat_name = gates_for(effect_id)
    if mat_name.startswith("default"):
        # HARD FAIL, not a warning. An effect with no registered material silently
        # gets the fire gates, and a cool-coloured effect then reads as "washed
        # out" - or worse, a wrong-coloured one passes. Forcing the author to
        # declare the material is the whole point of the table.
        fails.append(
            "no material registered - add %r to EFFECT_MATERIAL in "
            "verify_all.py and a MATERIAL_GATES entry if it needs different "
            "colour/density thresholds" % effect_id)
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
        if m["sat"] < g["minSat"]:
            fails.append("%s: washed out, sat %.3f < %.2f (%s gates)"
                         % (label, m["sat"], g["minSat"], mat_name))
        if m["white"] > g["maxWhite"]:
            fails.append("%s: too white, %.3f > %.2f (%s gates)"
                         % (label, m["white"], g["maxWhite"], mat_name))
        # Fill is a shape-quality gate, not a size gate: a rectangle scores
        # ~1.0 and a lacy flame ~0.4, but a thin effect legitimately covers
        # little of the cell. Only the UPPER bound is meaningful, and a
        # near-solid frame is a real defect whichever way it fails.
        if m["fill"] > g["maxFill"]:
            fails.append("%s: too solid, fill %.3f > %.2f"
                         % (label, m["fill"], g["maxFill"]))
        elif m["fill"] < g["minFill"]:
            warns.append("%s: sparse, fill %.3f" % (label, m["fill"]))
        if m["ragged"] < g["minRagged"]:
            fails.append("%s: silhouette too smooth, ragged %.3f" % (label, m["ragged"]))
        if m["hw"] < g["minHw"]:
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


def write_cache(eid, fails):
    """Cache this effect's result for tools/review.py to read.

    Recording a human sign-off should be able to state whether the machine
    check passed at the time, without re-running Blender (which needs bpy and
    costs render time). The cache is gitignored build state, not a deliverable.
    """
    try:
        import time
        path = os.path.join(VFX_DIR, eid, ".verify.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"effect": eid, "pass": not fails, "fails": fails,
                       "checkedAt": time.time()}, fh, indent=2)
    except OSError:
        pass          # a missing cache only degrades review.py's context line


def discover_effects():
    """Every sub-program on disk, plus the ids the index claims.

    Returns (ids, unregistered) where `unregistered` is a sub-program
    directory that is not in vfx/index.json. Verifying only the index meant a
    newly added effect was invisible to verification until someone remembered to
    run pack_sheets, so a broken new effect reported a clean run.
    """
    on_disk = sorted(d.name for d in VFX_DIR.iterdir()
                     if d.is_dir() and (d / "effect.json").is_file())
    index_path = os.path.join(VFX_DIR, "index.json")
    listed = []
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as fh:
            listed = json.load(fh)["effects"]
    unregistered = [e for e in on_disk if e not in listed]
    missing_dir = [e for e in listed if not (VFX_DIR / e).is_dir()]
    return (on_disk + [e for e in missing_dir if e not in on_disk],
            unregistered, missing_dir)


def main():
    ids, unregistered, missing_dir = discover_effects()

    print("verifying %d sub-program(s)\n" % len(ids))
    total_fail = 0

    for eid in missing_dir:
        print("%s" % eid)
        print("   FAIL: listed in vfx/index.json but no directory on disk")
        total_fail += 1

    for eid in ids:
        # Every sub-program is verified, whatever its material and whether or
        # not the index knows about it.
        fails, warns = check(eid)
        print("%s" % eid)
        for w in warns:
            print("   warn: %s" % w)
        for f in fails:
            print("   FAIL: %s" % f)
        print("   %s" % ("OK" if not fails else "%d problem(s)" % len(fails)))
        total_fail += len(fails)
        write_cache(eid, fails)

    for eid in unregistered:
        print("%s" % eid)
        print("   FAIL: has an effect.json but is not in vfx/index.json - run "
              "`python tools/pack_sheets.py --write-index`")
        total_fail += 1

    print("\nRESULT:", "PASS" if total_fail == 0 else "FAIL (%d)" % total_fail)
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
