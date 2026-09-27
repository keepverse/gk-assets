"""
Shield fire - IDLE. A persistent aura that loops seamlessly.

    blender --background --python blender/tools/shield_idle.py
    (or paste+Run in the Blender Text Editor)

Structure: a ring of upright flame cards around a hot core, a bead of light
tracing the dome's boundary, and embers rising through it.
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig   # noqa: E402

FRAMES = 24
# Author at 4x the gameplay cell and let pack_sheets downscale. A 26x40px card
# cannot hold flame detail at any shader setting - the detail is sub-pixel and
# averages to a flat block. Downsampling from 512 keeps it.
RES = 512
ORTHO = 1.8
GAMEPLAY_RES = 128
RING = 14
RADIUS = 0.42
# Card size from the ring, not from a pixel guess. Circumference is 2*pi*R;
# a card wider than circumference/N closes the gaps into a solid band, which
# is what flattened the first build into a horizontal stripe.
#   2*pi*0.42 = 2.64 units around; /14 = 0.188 per slot, so 0.13 leaves gaps.
CARD_W = 0.13
CARD_H = 0.30
BEADS = 20
BEAD_PX = 30.0
EMBERS = 10
SEED = 4242


def build():
    # build() must be idempotent. Re-running it in a live session otherwise
    # leaves the previous rig behind, and Blender resolves the name collision
    # by suffixing ".001" - producing cards that have no material and never
    # render, sitting inside the good ones.
    rig.wipe()
    px = rig.setup_scene(res=RES, ortho=ORTHO, tilt_deg=12.0, frames=FRAMES)
    cols = rig.collections("SF_Core", "SF_Flames", "SF_Rim", "SF_Embers")

    CW, CH = CARD_W, CARD_H
    rng = random.Random(SEED)

    # three flame tiers so the ring has depth instead of reading as one band.
    # Values are the ones measured on a single 512px card render, not guessed.
    m_big = rig.flame_mat("M_SF_FlameBig", (1.0, 0.55, 0.10), (0.42, 0.03, 0.00),
                          cycles=6.0, gamma_lo=0.34, gamma_hi=0.70, warp=0.50, gain=1.7)
    m_mid = rig.flame_mat("M_SF_FlameMid", (1.0, 0.82, 0.40), (0.75, 0.10, 0.01),
                          cycles=8.0, gamma_lo=0.32, gamma_hi=0.66, warp=0.60, gain=1.6)
    m_hot = rig.flame_mat("M_SF_FlameHot", (1.0, 0.97, 0.80), (1.0, 0.35, 0.03),
                          cycles=10.0, gamma_lo=0.30, gamma_hi=0.62, warp=0.70, gain=1.5)
    tiers = [m_big[0], m_mid[0], m_hot[0]]

    # ---- flame ring ------------------------------------------------------
    # A dome, not a band: cards on the FAR side (depth +1) are tall and lifted,
    # cards on the NEAR side (depth -1) are short and low. With a 12-degree
    # camera tilt that vertical stagger is what reads as a volume enclosing
    # something rather than a horizontal stripe of fire.
    for i in range(RING):
        a = (i / RING) * math.tau
        depth = math.sin(a)                      # +1 far, -1 near
        h = CH * (0.60 + 0.85 * (depth * 0.5 + 0.5))
        ob = rig.card("SF_Flame_%02d" % i, CW, h, cols["SF_Flames"])
        ob.data.materials.append(tiers[i % 3])
        phase = rng.uniform(0.0, math.tau)
        rate = rng.uniform(0.7, 1.4)
        detail = rig.detail_noise(ob.data.materials[0])
        mapn = ob.data.materials[0].node_tree.nodes["Mapping"]
        for f in range(1, FRAMES + 1):
            t = (f - 1) / FRAMES
            # scroll the noise upward so tongues rise; the taper hides the wrap
            mapn.inputs["Location"].default_value = (0.0, t * 1.5, 0.0)
            mapn.inputs["Location"].keyframe_insert("default_value", frame=f)
            if detail:
                detail.inputs["W"].default_value = t * 1.0
                detail.inputs["W"].keyframe_insert("default_value", frame=f)
            ang = t * math.tau
            s = 0.88 + 0.16 * math.sin(ang * rate * 2.0 + phase)
            # sit each card so its BASE is on the ground ring, so taller far
            # cards arc upward rather than sinking through the centre
            ob.location = (RADIUS * math.cos(a) + 0.012 * math.sin(ang * rate + phase),
                           0.16 * depth + 0.010 * math.cos(ang * rate * 1.3 + phase),
                           -0.02 + 0.02 * (i % 3))
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

    # ---- core: a small hot pool BEHIND the flames, not a big pale disc.
    # Measured: at 0.44 units the core still covered more area than the whole
    # flame ring and read as a pale egg. 0.26 units and half brightness keeps
    # it as a warm centre the flames show through.
    m_core = rig.radial_mat("M_SF_Core", (1.0, 0.88, 0.55), (1.0, 0.28, 0.02), mask_hi=0.50)
    m_core.node_tree.nodes["Emission"].inputs["Strength"].default_value = 0.6
    core = rig.card("SF_Core", 0.26, 0.20, cols["SF_Core"])
    core.data.materials.append(m_core)
    for f in range(1, FRAMES + 1):
        t = (f - 1) / FRAMES * math.tau
        s = 0.90 * (1.0 + 0.12 * math.sin(t * 2.0))
        core.location = (0.0, 0.04, -0.06)
        core.scale = (s, s, 1.0)
        core.keyframe_insert("location", frame=f)
        core.keyframe_insert("scale", frame=f)

    # ---- rim beads: this is what reads as a BARRIER rather than a fire cloud.
    # They follow the same depth lift as the flames so the boundary arcs over
    # the unit instead of drawing a flat ellipse around its feet.
    m_rim = rig.radial_mat("M_SF_Rim", (1.0, 0.96, 0.80), (1.0, 0.42, 0.05), mask_hi=0.44)
    # The beads were reading as a chain of hard white balls floating above the
    # flames. Smaller, dimmer, and further out so they read as a highlight
    # along the shield's edge rather than a separate object.
    m_rim.node_tree.nodes["Emission"].inputs["Strength"].default_value = 0.75
    for i in range(BEADS):
        a = (i / BEADS) * math.tau
        ob = rig.card("SF_Rim_%02d" % i, BEAD_PX * 0.55 / px, BEAD_PX * 0.55 / px,
                      cols["SF_Rim"])
        ob.data.materials.append(m_rim)
        phase = rng.uniform(0.0, math.tau)
        for f in range(1, FRAMES + 1):
            t = (f - 1) / FRAMES
            ang = a + t * math.tau * 0.25
            depth = math.sin(ang)
            s = 0.55 + 0.30 * math.sin(t * math.tau * 3.0 + phase)
            # the bead sits at the TOP of the flame at that point on the ring
            card_h = CH * (0.60 + 0.85 * (depth * 0.5 + 0.5))
            ob.location = ((RADIUS + 0.05) * math.cos(ang),
                           0.16 * depth + card_h * 0.50,
                           -0.03)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

    # ---- embers ----
    m_emb = rig.radial_mat("M_SF_Ember", (1.0, 0.90, 0.55), (1.0, 0.28, 0.03), mask_hi=0.44)
    rng2 = random.Random(SEED + 1)
    for i in range(EMBERS):
        ob = rig.card("SF_Ember_%02d" % i, 26.0 / px, 26.0 / px, cols["SF_Embers"])
        ob.data.materials.append(m_emb)
        a0 = rng2.uniform(0.0, math.tau)
        r0 = rng2.uniform(0.16, 0.42)
        vy = rng2.uniform(0.012, 0.030)
        bs = rng2.uniform(0.7, 1.1)
        life = float(rng2.randint(13, 23))
        x, y = r0 * math.cos(a0), r0 * math.sin(a0) * 0.5
        for f in range(1, FRAMES + 1):
            fade = max(0.0, 1.0 - f / life)
            s = max(0.04, (fade ** 1.2) * bs)
            ob.location = (x, y, 0.02)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
            vy *= 0.97
            y += vy
            x += 0.004 * math.sin(f * 0.4 + a0)

    return px


LAYERS = {
    "core":   ["SF_Core"],
    "flames": ["SF_Flame_%02d" % i for i in range(RING)],
    "rim":    ["SF_Rim_%02d" % i for i in range(BEADS)],
    "embers": ["SF_Ember_%02d" % i for i in range(EMBERS)],
}


def export(out_dir, with_preview=True):
    return rig.export(out_dir, LAYERS, with_preview=with_preview)


if __name__ == "__main__":
    OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, "vfx", "shield_fire_idle")
    px = build()
    n = export(os.path.abspath(OUT))
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(os.path.abspath(OUT), "shield_fire_idle.blend"))
    print("shield_fire_idle: %d px/unit, %d PNGs -> %s" % (round(px, 1), n, OUT))
