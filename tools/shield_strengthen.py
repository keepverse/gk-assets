"""
Shield fire - STRENGTHEN. A power-up: the shield flares and intensifies.

    blender --background --python blender/tools/shield_strengthen.py

Reading: the whole barrier inhales (contracts, dims), then detonates outward in
a bright ring, then settles at a higher sustained intensity than it started.
That inhale-explode-settle is what separates a buff from an impact - an impact
starts bright and decays, a strengthen starts quiet and gets brighter.

Timing (30 frames @ 24fps = 1.25s):
    1-8    inhale: ring contracts to 0.82x and dims to 45%
    9-12   burst: ring snaps out to 1.30x at full brightness
    13-20  overshoot settles from 1.30x back to 1.0x
    21-30  holds at 1.06x, brighter than the pre-buff idle
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig   # noqa: E402

FRAMES = 30
RES = 512
ORTHO = 1.8
RING = 14
RADIUS = 0.42
CARD_W = 0.13
CARD_H = 0.30
BEADS = 20
SPARKS = 18
SEED = 3141


def envelope(f):
    """Radius multiplier and brightness multiplier over the effect.

    inhale -> burst -> settle. Piecewise so each phase can be tuned on its own
    rather than fighting one long curve.
    """
    if f <= 8:                                  # inhale
        t = (f - 1) / 7.0
        r = 1.0 - 0.18 * t
        b = 1.0 - 0.55 * t
    elif f <= 12:                               # burst
        t = (f - 8) / 4.0
        r = 0.82 + 0.48 * t
        b = 0.45 + 1.30 * t
    elif f <= 20:                               # settle back
        t = (f - 12) / 8.0
        r = 1.30 - 0.24 * t
        b = 1.75 - 0.50 * t
    else:                                       # hold, brighter than idle
        t = min(1.0, (f - 20) / 8.0)
        r = 1.06 - 0.06 * t
        b = 1.25 - 0.10 * t
    return r, b


def build():
    rig.wipe()
    px = rig.setup_scene(res=RES, ortho=ORTHO, tilt_deg=12.0, frames=FRAMES)
    cols = rig.collections("SF_Core", "SF_Flames", "SF_Rim", "SF_Sparks")

    base = rig.flame_mat("M_SF_FlameBase", (1.0, 0.55, 0.10), (0.42, 0.03, 0.00),
                         cycles=6.0, warp=0.50)
    card_mats = []
    for i in range(RING):
        m = base[0].copy()
        m.name = "M_SF_StrFlame_%02d" % i
        card_mats.append(m)

    rng = random.Random(SEED)

    for i in range(RING):
        a = (i / RING) * math.tau
        depth = math.sin(a)
        h = CARD_H * (0.60 + 0.85 * (depth * 0.5 + 0.5))
        ob = rig.card("SF_Flame_%02d" % i, CARD_W, h, cols["SF_Flames"])
        ob.data.materials.append(card_mats[i])
        phase = rng.uniform(0.0, math.tau)
        mapn = card_mats[i].node_tree.nodes["Mapping"]
        em = card_mats[i].node_tree.nodes["Emission"]
        detail = rig.detail_noise(card_mats[i])

        for f in range(1, FRAMES + 1):
            t = (f - 1) / float(FRAMES)
            r_mult, b_mult = envelope(f)
            # a fast outward kick on the burst, so it reads as an explosion
            kick = 0.0
            if 8 < f <= 14:
                kick = 0.10 * math.sin((f - 8) / 6.0 * math.pi)
            R = RADIUS * (r_mult + kick)
            ob.location = (R * math.cos(a), 0.16 * depth * r_mult,
                           -0.02 + 0.015 * (i % 3))
            s = (0.88 + 0.14 * math.sin(t * math.tau * 2.0 + phase)) * r_mult
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

            # emission is capped at 1.0 per the rig's rule, so brightness beyond
            # "full" is expressed by SCALE and by the rim/core, not by strength
            em.inputs["Strength"].default_value = min(1.0, b_mult)
            em.inputs["Strength"].keyframe_insert("default_value", frame=f)

            mapn.inputs["Location"].default_value = (0.0, t * 1.5, 0.0)
            mapn.inputs["Location"].keyframe_insert("default_value", frame=f)
            if detail:
                detail.inputs["W"].default_value = t
                detail.inputs["W"].keyframe_insert("default_value", frame=f)

    # --- core: follows the envelope, brightest on the burst ---
    m_core = rig.radial_mat("M_SF_Core", (1.0, 0.88, 0.55), (1.0, 0.28, 0.02), mask_hi=0.50)
    core = rig.card("SF_Core", 0.26, 0.20, cols["SF_Core"])
    core.data.materials.append(m_core)
    em = m_core.node_tree.nodes["Emission"]
    for f in range(1, FRAMES + 1):
        r_mult, b_mult = envelope(f)
        s = 0.90 * r_mult
        core.location = (0.0, 0.04, -0.06)
        core.scale = (s, s, 1.0)
        core.keyframe_insert("location", frame=f)
        core.keyframe_insert("scale", frame=f)
        em.inputs["Strength"].default_value = min(1.0, 0.55 * b_mult)
        em.inputs["Strength"].keyframe_insert("default_value", frame=f)

    # --- rim: the ring that snaps outward on the burst ---
    m_rim = rig.radial_mat("M_SF_Rim", (1.0, 0.96, 0.80), (1.0, 0.42, 0.05), mask_hi=0.44)
    for i in range(BEADS):
        a = (i / BEADS) * math.tau
        ob = rig.card("SF_Rim_%02d" % i, 0.062, 0.062, cols["SF_Rim"])
        ob.data.materials.append(m_rim)
        for f in range(1, FRAMES + 1):
            r_mult, b_mult = envelope(f)
            depth = math.sin(a)
            card_h = CARD_H * (0.60 + 0.85 * (depth * 0.5 + 0.5)) * r_mult
            s = (0.55 + 0.30 * b_mult) * (0.9 + 0.1 * math.sin(f * 0.5 + i))
            ob.location = ((RADIUS + 0.05) * r_mult * math.cos(a),
                           0.16 * depth * r_mult + card_h * 0.50, -0.03)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

    # --- sparks thrown outward on the burst ---
    m_spark = rig.radial_mat("M_SF_Spark", (1.0, 0.98, 0.88), (1.0, 0.34, 0.03), mask_hi=0.42)
    rng2 = random.Random(SEED + 5)
    for i in range(SPARKS):
        ob = rig.card("SF_Spark_%02d" % i, 0.05, 0.05, cols["SF_Sparks"])
        ob.data.materials.append(m_spark)
        ang = rng2.uniform(0.0, math.tau)
        speed = rng2.uniform(0.018, 0.048)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed * 0.5
        delay = 9 + rng2.randint(0, 3)
        # long-lived so the sheet's later cells are not empty: the burst is
        # frames 9-12 but embers should carry on well past the settle
        life = rng2.randint(14, 22)
        x = RADIUS * math.cos(ang) * 0.9
        y = RADIUS * math.sin(ang) * 0.5 + 0.05
        for f in range(1, FRAMES + 1):
            age = f - delay
            s = 0.0 if age < 0 else max(0.0, 1.0 - age / float(life)) * 0.85
            ob.location = (x, y, 0.06)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
            vx *= 0.94
            vy = vy * 0.94 - 0.008
            x += vx
            y += vy

    return px


LAYERS = {
    "core":   ["SF_Core"],
    "flames": ["SF_Flame_%02d" % i for i in range(RING)],
    "rim":    ["SF_Rim_%02d" % i for i in range(BEADS)],
    "sparks": ["SF_Spark_%02d" % i for i in range(SPARKS)],
}


if __name__ == "__main__":
    OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, "vfx", "shield_fire_strengthen")
    px = build()
    n = rig.export(OUT, LAYERS)
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(os.path.abspath(OUT), "shield_fire_strengthen.blend"))
    print("shield_fire_strengthen: %d px/unit, %d PNGs" % (round(px, 1), n))
