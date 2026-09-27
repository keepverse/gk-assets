"""
Shield fire - BREAK. The shield fails and the fire vents.

    blender --background --python blender/tools/shield_break.py

Reading: a crack opens at one point, the barrier tears along it, the flames
blow outward and downward as the dome collapses, and the whole thing gutters
out. Structurally it is the inverse of impact - instead of a ripple travelling
around an intact ring, the ring is progressively DISABLED arc by arc from the
breach outward.

Timing (36 frames @ 24fps = 1.5s):
    1-4    over-charge: the shield flares bright right before failing
    3-14   breach: an arc of the ring around the crack is extinguished
    4-20   collapse: the dome contracts and sags as flames fall
    5-22   shards: burning fragments fly outward and tumble
    14-36  embers gutter out; nothing is left by frame 36
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig   # noqa: E402

FRAMES = 36
RES = 512
ORTHO = 1.8
RING = 16
RADIUS = 0.42
CARD_W = 0.13
CARD_H = 0.30
BEADS = 20
SHARDS = 20
SEED = 6660

BREACH = 0.0          # angle of the crack (+X)
SHATTER_SPAN = 2.4    # radians of the ring destroyed by the breach


def build():
    rig.wipe()
    px = rig.setup_scene(res=RES, ortho=ORTHO, tilt_deg=12.0, frames=FRAMES)
    cols = rig.collections("SF_Core", "SF_Flames", "SF_Rim", "SF_Shards",
                          "SF_Crack", "SF_Tail")

    base = rig.flame_mat("M_SF_FlameBase", (1.0, 0.55, 0.10), (0.42, 0.03, 0.00),
                         cycles=6.0, warp=0.50)
    card_mats = []
    for i in range(RING):
        m = base[0].copy()
        m.name = "M_SF_BrkFlame_%02d" % i
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

        # how close is this card to the breach?
        d = math.acos(max(-1.0, min(1.0, math.cos(a - BREACH))))
        near = max(0.0, 1.0 - d / (SHATTER_SPAN * 0.5))

        for f in range(1, FRAMES + 1):
            t = (f - 1) / float(FRAMES)
            # COLLAPSE: the dome sags and contracts as it fails
            if f <= 4:
                collapse = 0.0
            else:
                collapse = min(1.0, (f - 4) / 16.0)
            R = RADIUS * (1.0 - 0.34 * collapse)
            # flames fall: the whole ring sinks and shortens
            sink = -0.10 * collapse

            # each card dies progressively, nearest the breach first
            die_at = 3.0 + (1.0 - near) * 11.0
            if f < die_at:
                alive = 1.0
            else:
                alive = max(0.0, 1.0 - (f - die_at) / 5.0)

            # over-charge right before failing
            if f <= 4:
                charge = 1.0 + 1.4 * (f / 4.0)
            else:
                charge = 1.0

            s = (0.88 + 0.14 * math.sin(t * math.tau * 2.0 + phase)) * alive
            s *= (1.0 - 0.45 * collapse)
            ob.location = (R * math.cos(a), 0.16 * depth * (1.0 - 0.5 * collapse) + sink,
                           -0.02 + 0.015 * (i % 3))
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

            em.inputs["Strength"].default_value = min(1.0, charge * alive)
            em.inputs["Strength"].keyframe_insert("default_value", frame=f)

            mapn.inputs["Location"].default_value = (0.0, t * 1.5, 0.0)
            mapn.inputs["Location"].keyframe_insert("default_value", frame=f)
            if detail:
                detail.inputs["W"].default_value = t
                detail.inputs["W"].keyframe_insert("default_value", frame=f)

    # --- core: flares, then gutters to nothing ---
    m_core = rig.radial_mat("M_SF_Core", (1.0, 0.90, 0.60), (1.0, 0.28, 0.02), mask_hi=0.50)
    core = rig.card("SF_Core", 0.26, 0.20, cols["SF_Core"])
    core.data.materials.append(m_core)
    em = m_core.node_tree.nodes["Emission"]
    for f in range(1, FRAMES + 1):
        # over-charge peaks at 2.4x, which turned the core into a second pale
        # egg wider than the barrier. The failure reads from the ring going out
        # and the shards, not from the centre getting bright.
        if f <= 4:
            s = 0.9 + 0.38 * f
        else:
            s = max(0.0, 2.4 * (1.0 - (f - 4) / 12.0))
        core.location = (0.0, 0.04 - 0.10 * min(1.0, max(0.0, (f - 4) / 16.0)), -0.06)
        core.scale = (s, s, 1.0)
        core.keyframe_insert("location", frame=f)
        core.keyframe_insert("scale", frame=f)
        em.inputs["Strength"].default_value = min(1.0, 0.55 + 0.45 * max(0.0, 1.0 - (f - 1) / 8.0))
        em.inputs["Strength"].keyframe_insert("default_value", frame=f)

    # --- crack: the hot tear at the breach ---
    # Uses the flame shader, not radial_mat. A radial glow on a tall card is a
    # smooth ellipse, which reads as a floating pill; the thresholded flame
    # alpha gives a torn, irregular edge that reads as a rip.
    m_crack = rig.flame_mat("M_SF_Crack", (1.0, 0.99, 0.92), (1.0, 0.45, 0.05),
                            cycles=14.0, warp=0.75)
    crack_em = m_crack[0].node_tree.nodes["Emission"]
    crack_detail = rig.detail_noise(m_crack[0])
    crack_map = m_crack[0].node_tree.nodes["Mapping"]
    crack = rig.card("SF_Crack", 0.11, 0.40, cols["SF_Crack"])
    crack.data.materials.append(m_crack[0])
    for f in range(1, FRAMES + 1):
        # grow must be defined on every path: the first pass referenced it
        # outside the `2 <= f` guard, which is a NameError on frame 1.
        grow = min(1.0, max(0.0, (f - 2) / 5.0))
        if 2 <= f <= 15:
            fade = 1.0 if f <= 11 else max(0.0, 1.0 - (f - 11) / 4.0)
            s = (0.5 + 0.8 * grow) * fade
        else:
            s = 0.0
        crack.location = (RADIUS * math.cos(BREACH) + 0.03, 0.10, 0.07)
        crack.scale = (s, s * (0.6 + 0.7 * grow), 1.0)
        crack.keyframe_insert("location", frame=f)
        crack.keyframe_insert("scale", frame=f)
        t = (f - 1) / float(FRAMES)
        crack_map.inputs["Location"].default_value = (0.0, t * 2.0, 0.0)
        crack_map.inputs["Location"].keyframe_insert("default_value", frame=f)
        if crack_detail:
            crack_detail.inputs["W"].default_value = t * 1.4
            crack_detail.inputs["W"].keyframe_insert("default_value", frame=f)

    # --- rim: goes out arc by arc from the breach ---
    m_rim = rig.radial_mat("M_SF_Rim", (1.0, 0.96, 0.80), (1.0, 0.42, 0.05), mask_hi=0.44)
    for i in range(BEADS):
        a = (i / BEADS) * math.tau
        ob = rig.card("SF_Rim_%02d" % i, 0.062, 0.062, cols["SF_Rim"])
        ob.data.materials.append(m_rim)
        d = math.acos(max(-1.0, min(1.0, math.cos(a - BREACH))))
        near = max(0.0, 1.0 - d / (SHATTER_SPAN * 0.5))
        for f in range(1, FRAMES + 1):
            collapse = min(1.0, max(0.0, (f - 4) / 16.0))
            R = RADIUS * (1.0 - 0.34 * collapse)
            die_at = 3.0 + (1.0 - near) * 11.0
            alive = 1.0 if f < die_at else max(0.0, 1.0 - (f - die_at) / 5.0)
            depth = math.sin(a)
            s = 0.55 * alive
            ob.location = ((RADIUS + 0.05) * (1.0 - 0.34 * collapse) * math.cos(a),
                           0.16 * depth * (1.0 - 0.5 * collapse)
                           - 0.10 * collapse
                           + CARD_H * 0.50 * (1.0 - 0.5 * collapse),
                           -0.03)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

    # --- shards: burning fragments blown outward from the breach, tumbling ---
    m_shard = rig.radial_mat("M_SF_Shard", (1.0, 0.96, 0.80), (1.0, 0.30, 0.03), mask_hi=0.42)
    rng2 = random.Random(SEED + 7)
    for i in range(SHARDS):
        ob = rig.card("SF_Shard_%02d" % i,
                      rng2.uniform(0.05, 0.11), rng2.uniform(0.04, 0.09),
                      cols["SF_Shards"])
        ob.data.materials.append(m_shard)
        ang = BREACH + rng2.uniform(-1.1, 1.1)
        speed = rng2.uniform(0.022, 0.060)
        vx = math.cos(ang) * speed
        vy = math.sin(ang) * speed * 0.55
        spin = rng2.uniform(-0.22, 0.22)
        rot = rng2.uniform(0.0, math.tau)
        delay = 5 + rng2.randint(0, 6)
        x = RADIUS * math.cos(BREACH) * 0.95
        y = 0.08
        for f in range(1, FRAMES + 1):
            age = f - delay
            s = 0.0 if age < 0 else max(0.0, 1.0 - age / 18.0)
            ob.location = (x, y, 0.05)
            ob.scale = (s, s, 1.0)
            ob.rotation_euler = (0.0, 0.0, rot + spin * age)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
            ob.keyframe_insert("rotation_euler", frame=f)
            vx *= 0.955
            vy = vy * 0.955 - 0.011          # gravity: fragments fall
            x += vx
            y += vy

    # --- embers: the smouldering tail ---------------------------------------
    # Without this the effect was DEAD from frame 19 to 36: every other layer
    # had finished, so 18 of 36 sheet cells were empty. A break that gutters
    # out should leave falling cinders for the rest of the shot.
    m_tail = rig.radial_mat("M_SF_Tail", (1.0, 0.80, 0.35), (0.85, 0.16, 0.01), mask_hi=0.42)
    rng3 = random.Random(SEED + 11)
    TAIL = 30
    for i in range(TAIL):
        ob = rig.card("SF_Tail_%02d" % i,
                      rng3.uniform(0.05, 0.10), rng3.uniform(0.05, 0.10),
                      cols["SF_Tail"])
        ob.data.materials.append(m_tail)
        ang = rng3.uniform(0.0, math.tau)
        r0 = rng3.uniform(0.05, RADIUS)
        vy = rng3.uniform(0.004, 0.014)
        vx = rng3.uniform(-0.006, 0.006)
        # staggered start so cinders are still being shed late in the shot
        delay = 3 + rng3.randint(0, 20)
        life = rng3.randint(18, 30)
        x = r0 * math.cos(ang)
        y = r0 * math.sin(ang) * 0.5 + 0.05
        for f in range(1, FRAMES + 1):
            age = f - delay
            s = 0.0 if age < 0 else max(0.0, 1.0 - age / float(life)) * 0.8
            ob.location = (x, y - 0.10 * min(1.0, max(0.0, (f - 4) / 16.0)), 0.02)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)
            vy *= 0.975
            vx *= 0.97
            x += vx
            y += vy

    return px


LAYERS = {
    "core":   ["SF_Core"],
    "flames": ["SF_Flame_%02d" % i for i in range(RING)],
    "rim":    ["SF_Rim_%02d" % i for i in range(BEADS)],
    "crack":  ["SF_Crack"],
    "shards": ["SF_Shard_%02d" % i for i in range(SHARDS)],
    "tail":   ["SF_Tail_%02d" % i for i in range(30)],
}


if __name__ == "__main__":
    OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, "vfx", "shield_fire_break")
    px = build()
    n = rig.export(OUT, LAYERS)
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(os.path.abspath(OUT), "shield_fire_break.blend"))
    print("shield_fire_break: %d px/unit, %d PNGs" % (round(px, 1), n))
