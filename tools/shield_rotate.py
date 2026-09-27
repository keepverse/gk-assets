"""
Shield fire - ROTATE. A baked Z turntable proving 3D-in-2D.

    blender --background --python blender/tools/shield_rotate.py

Technique
---------
A 2D game cannot render a 3D dome, so we bake one. The flame ring is a real 3D
arrangement (cards on a cylinder around the unit, lit from the front) and the
camera is ORTHOGRAPHIC, so the projection is a true parallel view - no
perspective skew as the rig turns.

Two things make it read as a solid rotating object rather than a cross-fade:

1. The cards genuinely move. Back cards travel to the sides and front cards
   travel across, so the silhouette changes every frame.
2. Cards fade as they pass to the BACK of the cylinder and brighten at the
   front. Without that depth cue a turntable is just a wobble.

The manifest declares projection.mode = "turntable", and the viewer applies a
cosine width curve on top, so the dome's projected width narrows and widens.
"""

import math
import os
import random
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig   # noqa: E402

FRAMES = 36          # a full turn; 36 frames at 24fps = 1.5s per revolution
RES = 512
ORTHO = 1.8
RING = 16
RADIUS = 0.44
CARD_W = 0.11
CARD_H = 0.30
SEED = 5150


def build():
    rig.wipe()
    px = rig.setup_scene(res=RES, ortho=ORTHO, tilt_deg=16.0, frames=FRAMES)
    cols = rig.collections("SF_Core", "SF_Flames", "SF_Rim")

    tiers = [
        rig.flame_mat("M_SF_FlameBig", (1.0, 0.55, 0.10), (0.42, 0.03, 0.00),
                      cycles=6.0, warp=0.50)[0],
        rig.flame_mat("M_SF_FlameMid", (1.0, 0.82, 0.40), (0.75, 0.10, 0.01),
                      cycles=8.0, warp=0.60)[0],
        rig.flame_mat("M_SF_FlameHot", (1.0, 0.97, 0.80), (1.0, 0.35, 0.03),
                      cycles=10.0, warp=0.70)[0],
    ]

    rng = random.Random(SEED)

    # --- depth fade material -------------------------------------------------
    # Cards dim as they rotate to the back. A single shared per-card material
    # cannot do this (they all need different values per frame), so each card
    # gets its own copy of a cheap emission-only material whose strength is
    # keyframed. Cheap, and it is the cue that sells the rotation.
    base = tiers[0]
    card_mats = []
    for i in range(RING):
        m = base.copy()
        m.name = "M_SF_RotFlame_%02d" % i
        m.node_tree.nodes["Emission"].inputs["Strength"].default_value = 1.0
        card_mats.append(m)

    for i in range(RING):
        base_a = (i / RING) * math.tau
        depth0 = math.sin(base_a)
        h = CARD_H * (0.62 + 0.80 * (depth0 * 0.5 + 0.5))
        ob = rig.card("SF_Flame_%02d" % i, CARD_W, h, cols["SF_Flames"])
        ob.data.materials.append(card_mats[i])
        phase = rng.uniform(0.0, math.tau)
        rate = rng.uniform(0.8, 1.3)
        detail = rig.detail_noise(card_mats[i])
        mapn = card_mats[i].node_tree.nodes["Mapping"]
        em = card_mats[i].node_tree.nodes["Emission"]

        for f in range(1, FRAMES + 1):
            t = (f - 1) / FRAMES
            turn = t * math.tau                     # one full revolution
            ang = base_a + turn                    # the card's own position
            depth = math.sin(ang)                   # +1 front, -1 back

            # the ring turns as a body
            x = RADIUS * math.cos(ang)
            y = 0.17 * depth
            ob.location = (x, y, -0.02 + 0.015 * (i % 3))
            # far cards shrink slightly, which reinforces the depth
            s = 0.92 - 0.16 * (-depth * 0.5 + 0.5) + 0.05 * math.sin(turn * rate * 2.0 + phase)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

            # DEPTH CUE: dim at the back, bright at the front. Without this the
            # turntable reads as a wobble instead of a rotation.
            em.inputs["Strength"].default_value = 0.22 + 0.78 * (depth * 0.5 + 0.5)
            em.inputs["Strength"].keyframe_insert("default_value", frame=f)

            mapn.inputs["Location"].default_value = (0.0, t * 1.5, 0.0)
            mapn.inputs["Location"].keyframe_insert("default_value", frame=f)
            if detail:
                detail.inputs["W"].default_value = t * 1.0
                detail.inputs["W"].keyframe_insert("default_value", frame=f)

    # --- core: stays put, breathes ------------------------------------------
    m_core = rig.radial_mat("M_SF_Core", (1.0, 0.88, 0.55), (1.0, 0.28, 0.02), mask_hi=0.50)
    m_core.node_tree.nodes["Emission"].inputs["Strength"].default_value = 0.55
    core = rig.card("SF_Core", 0.24, 0.18, cols["SF_Core"])
    core.data.materials.append(m_core)
    for f in range(1, FRAMES + 1):
        t = (f - 1) / FRAMES
        # A 2-cycle sine quantizes to only a handful of distinct frames (9 of
        # 36 measured). Use an incommensurate rate plus a slow drift so every
        # frame differs - the core should shimmer, not pulse.
        s = 0.90 * (1.0 + 0.10 * math.sin(t * math.tau * 3.0)
                    + 0.04 * math.sin(t * math.tau * 7.0 + 1.1)
                    + 0.03 * math.sin(t * math.tau * 1.0))
        core.location = (0.0, 0.04, -0.06)
        core.scale = (s, s, 1.0)
        core.keyframe_insert("location", frame=f)
        core.keyframe_insert("scale", frame=f)

    # --- rim: two arcs, counter-rotating, so the boundary stays readable ----
    m_rim = rig.radial_mat("M_SF_Rim", (1.0, 0.96, 0.80), (1.0, 0.42, 0.05), mask_hi=0.44)
    m_rim.node_tree.nodes["Emission"].inputs["Strength"].default_value = 0.7
    BEADS = 20
    for i in range(BEADS):
        a = (i / BEADS) * math.tau
        ob = rig.card("SF_Rim_%02d" % i, 0.055, 0.055, cols["SF_Rim"])
        ob.data.materials.append(m_rim)
        for f in range(1, FRAMES + 1):
            t = (f - 1) / FRAMES
            ang = a + t * math.tau
            depth = math.sin(ang)
            card_h = CARD_H * (0.62 + 0.80 * (depth * 0.5 + 0.5))
            s = (0.55 + 0.28 * depth) * (0.9 + 0.1 * math.sin(t * math.tau * 2.0))
            ob.location = ((RADIUS + 0.05) * math.cos(ang),
                           0.17 * depth + card_h * 0.50, -0.03)
            ob.scale = (s, s, 1.0)
            ob.keyframe_insert("location", frame=f)
            ob.keyframe_insert("scale", frame=f)

    return px


LAYERS = {
    "core":   ["SF_Core"],
    "flames": ["SF_Flame_%02d" % i for i in range(RING)],
    "rim":    ["SF_Rim_%02d" % i for i in range(20)],
}


if __name__ == "__main__":
    OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       os.pardir, "vfx", "shield_fire_rotate")
    px = build()
    n = rig.export(OUT, LAYERS)
    bpy.ops.wm.save_as_mainfile(
        filepath=os.path.join(os.path.abspath(OUT), "shield_fire_rotate.blend"))
    print("shield_fire_rotate: %d px/unit, %d PNGs" % (round(px, 1), n))
