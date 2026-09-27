"""
Shield fire - IMPACT. The shield absorbs a hit at the contact point.

    blender --background --python blender/tools/shield_impact.py

Reading: a burst flares at ONE side of the shield (the hit direction, authored
to +X), a ripple of bright beads races around the barrier from that point, the
flames recoil away from the impact and then recover, and a shower of sparks
flies off. It is a one-shot, so it does not loop - it plays once and dies.

Timing (24 frames @ 24fps = 1.0s):
    1-3   flare punches at the contact point
    2-10  ripple travels around the ring
    4-14  flames recoil outward from the hit
    5-20  sparks arc away and fade
    12-24 flames settle back to idle height
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig   # noqa: E402

FRAMES = 24
RES = 512
ORTHO = 1.8
RING = 14
RADIUS = 0.42
CARD_W = 0.13
CARD_H = 0.30
HIT_ANGLE = 0.0        # +X, i.e. the shield is struck from the right
RIPPLE_BEADS = 20
SPARKS = 16
SEED = 9090


def build():
    rig.wipe()
    px = rig.setup_scene(res=RES, ortho=ORTHO, tilt_deg=12.0, frames=FRAMES)
    cols = rig.collections("SF_Core", "SF_Flames", "SF_Rim", "SF_Flare", "SF_Sparks")

    flame_base = rig.flame_mat("M_SF_FlameBase", (1.0, 0.55, 0.10), (0.42, 0.03, 0.00),
                               cycles=6.0, warp=0.50)
    # per-card material so each can recoil independently
    card_mats = []
    for i in range(RING):
        m = flame_base[0].copy()
        m.name = "M_SF_ImpFlame_%02d" % i
        card_mats.append(m)

    rng = random.Random(SEED)

    for i in range(RING):
        base_a = (i / RING) * math.tau
        depth = math.sin(base_a)
        h = CARD_H * (0.60 + 0.85 * (depth * 0.5 + 0.5))
        ob = rig.card("SF_Flame_%02d" % i, CARD_W, h, cols["SF_Flames"])
        ob.data.materials.append(card_mats[i])
        phase = rng.uniform(0.0, math.tau)
        mapn = card_mats[i].node_tree.nodes["Mapping"]
        em = card_mats[i].node_tree.nodes["Emission"]
        detail = rig.detail_noise(card_mats[i])
        # how close is this card to the impact? 1.0 = right under the hit.
        d = math.acos(max(-1.0, min(1.0, math.cos(base_a - HIT_ANGLE))))
        near = max(0.0, 1.0 - d / 1.5)          # 1 at the hit, 0 far away

        for f in range(1, FRAMES + 1):
            t = (f - 1) / float(FRAMES)
            # RECOIL: knocked outward at frame ~5, springs back by ~16
            if f <= 4:
                push = 0.0
            elif f <= 14:
                push = 0.085 * near * math.sin((f - 4) / 10.0 * math.pi)
            else:
                push = 0.085 * near * (1.0 - (f - 14) / 10.0)

            x = RADIUS * math.cos(base_a) * (1.0 + push * 1.6)
            y = 0.16 * depth * (1.0 + push)
            s = (0.88 + 0.16 * math.sin(t * math.tau * 2.0 + phase)
                 - 0.30 * push)                 # knocked flat
            ob.location = (x, y, -0.02 + 0.015 * (i % 3))
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

            # bright where the hit lands, briefly
            em.inputs["Strength"].default_value = 1.0 + 2.2 * near * max(0.0, 1.0 - (f - 2) / 5.0)
            em.inputs["Strength"].keyframe_insert("default_value", frame=f)

            mapn.inputs["Location"].default_value = (0.0, t * 1.5, 0.0)
            mapn.inputs["Location"].keyframe_insert("default_value", frame=f)
            if detail:
                detail.inputs["W"].default_value = t
                detail.inputs["W"].keyframe_insert("default_value", frame=f)

    # --- flare: the contact flash, at the hit angle ---
    # Sized and scaled to the SHIELD, not the frame. The first pass used a
    # 0.42 card scaled to 1.95, which produced a disc wider than the whole
    # barrier and swallowed it. The flare is a bright spot ON the edge.
    m_flare = rig.radial_mat("M_SF_Flare", (1.0, 0.99, 0.94), (1.0, 0.42, 0.04), mask_hi=0.40)
    flare = rig.card("SF_Flare", 0.20, 0.20, cols["SF_Flare"])
    flare.data.materials.append(m_flare)
    for f in range(1, FRAMES + 1):
        if f <= 3:
            s = 0.55 + 0.30 * f            # punches outward
        elif f <= 14:
            # decay stretched to frame 14 (was 9) so the sheet's later cells
            # still carry the contact glow instead of being blank
            s = 1.45 - 0.085 * (f - 3)
        else:
            s = max(0.0, 0.78 - 0.078 * (f - 14))
        flare.location = (RADIUS * math.cos(HIT_ANGLE) + 0.04,
                          0.16 * math.sin(HIT_ANGLE) + 0.08, 0.05)
        flare.scale = (s, s, 1.0)
        flare.keyframe_insert("location", frame=f)
        flare.keyframe_insert("scale", frame=f)

    # --- ripple: beads race around the ring from the hit ---
    m_rim = rig.radial_mat("M_SF_Ripple", (1.0, 0.98, 0.86), (1.0, 0.45, 0.06), mask_hi=0.44)
    for i in range(RIPPLE_BEADS):
        ob = rig.card("SF_Rim_%02d" % i, 0.06, 0.06, cols["SF_Rim"])
        ob.data.materials.append(m_rim)
        for f in range(1, FRAMES + 1):
            # distance travelled around the ring since the hit
            travel = (f - 2) / 11.0
            if travel < 0.0 or travel > 1.0:
                s = 0.0
            else:
                s = 0.45 + 0.55 * math.sin(travel * math.pi)
            ang = HIT_ANGLE + travel * math.tau * 0.85
            depth = math.sin(ang)
            card_h = CARD_H * (0.60 + 0.85 * (depth * 0.5 + 0.5))
            ob.location = ((RADIUS + 0.05) * math.cos(ang),
                           0.16 * depth + card_h * 0.50, -0.03)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

    # --- sparks: arc away from the hit and fall ---
    m_spark = rig.radial_mat("M_SF_Spark", (1.0, 0.98, 0.88), (1.0, 0.34, 0.03), mask_hi=0.42)
    rng2 = random.Random(SEED + 3)
    for i in range(SPARKS):
        ob = rig.card("SF_Spark_%02d" % i, 0.05, 0.05, cols["SF_Sparks"])
        ob.data.materials.append(m_spark)
        spread = rng2.uniform(-0.9, 0.9)
        ang = HIT_ANGLE + spread
        speed = rng2.uniform(0.020, 0.055)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed
        delay = 2 + rng2.randint(0, 6)
        # long-lived so the later sheet cells carry embers rather than blanks
        life = rng2.randint(14, 21)
        x = RADIUS * math.cos(HIT_ANGLE)
        y = 0.16 * math.sin(HIT_ANGLE) + 0.05
        for f in range(1, FRAMES + 1):
            age = f - delay
            s = 0.0 if age < 0 else max(0.0, 1.0 - age / float(life)) * 0.8
            ob.location = (x, y, 0.06)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
            vx *= 0.95
            vy = vy * 0.95 - 0.010          # gravity
            x += vx
            y += vy

    # --- core: flares with the hit then settles ---
    m_core = rig.radial_mat("M_SF_Core", (1.0, 0.88, 0.55), (1.0, 0.28, 0.02), mask_hi=0.50)
    core = rig.card("SF_Core", 0.26, 0.20, cols["SF_Core"])
    core.data.materials.append(m_core)
    for f in range(1, FRAMES + 1):
        # core flares with the hit but must stay a small pool: at 2.6x it
        # became a second pale egg competing with the contact flare
        boost = 1.0 + 0.7 * max(0.0, 1.0 - (f - 1) / 6.0)
        s = 0.90 * boost
        core.location = (0.0, 0.04, -0.06)
        core.scale = (s, s, 1.0)
        core.keyframe_insert("location", frame=f)
        core.keyframe_insert("scale", frame=f)
    em = m_core.node_tree.nodes["Emission"]
    for f in range(1, FRAMES + 1):
        em.inputs["Strength"].default_value = 0.55 + 0.6 * max(0.0, 1.0 - (f - 1) / 6.0)
        em.inputs["Strength"].keyframe_insert("default_value", frame=f)

    return px


LAYERS = {
    "core":   ["SF_Core"],
    "flames": ["SF_Flame_%02d" % i for i in range(RING)],
    "rim":    ["SF_Rim_%02d" % i for i in range(RIPPLE_BEADS)],
    "flare":  ["SF_Flare"],
    "sparks": ["SF_Spark_%02d" % i for i in range(SPARKS)],
}


if __name__ == "__main__":
    OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, "vfx", "shield_fire_impact")
    px = build()
    n = rig.export(OUT, LAYERS)
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(os.path.abspath(OUT), "shield_fire_impact.blend"))
    print("shield_fire_impact: %d px/unit, %d PNGs" % (round(px, 1), n))
