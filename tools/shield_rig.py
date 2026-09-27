"""
Fire shield VFX rig - shared builders.

Run inside Blender (Text Editor or --python). Every sub-program under
blender/vfx/shield_fire_* imports from here so the rig stays consistent.

Design notes that are easy to get wrong (each one cost a render):

* A ColorRamp Fac takes a SCALAR. Feeding it the raw UV vector makes Blender
  average x and y, which gives a DIAGONAL gradient, not a vertical one.
  Always Separate XYZ and take .Y for "up" and .X for "across".

* Noise "Scale" is cycles across the input vector. UV spans 0..1 across a
  card, so Scale=N gives N cycles across the card. At 128px a card is only
  ~20-30px wide, so Scale=11 is sub-pixel and averages to flat mush.
  Measured: ~4 cycles gives ~4px features, which survives the downscale.

* A ColorRamp CLAMPS its Fac to 0..1. A negative signal therefore becomes 0.
  If the element at position 0 is white, everything turns opaque. Masks fed
  by an inverted signal must be black at 0 and white at 1.

* Emission Strength must stay <= 1.0. These are sprite renders: shader RGB is
  written straight to the PNG, so >1.0 clips every channel to white and
  destroys the hue ramp.

* Emission "Weight" sockets exist in Blender 5.x. Do not leave stray links on
  a socket you meant to leave at its default.

* view_transform must be "Standard". AgX is a filmic look that desaturates;
  fire renders cream instead of orange.
"""

import math
import random

import bpy


# --------------------------------------------------------------------------
# scene / render
# --------------------------------------------------------------------------

def setup_scene(res=128, ortho=1.8, tilt_deg=12.0, frames=24, fps=30):
    """Render + camera config. Ortho top-ish view matches the 2D lawn camera."""
    scene = bpy.context.scene
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.engine = "BLENDER_EEVEE"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.fps = fps
    scene.frame_start, scene.frame_end = 1, frames

    cam_data = bpy.data.cameras.get("SF_Cam") or bpy.data.cameras.new("SF_Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho
    cam_data.clip_start = 0.01
    cam_data.clip_end = 100.0

    cam = bpy.data.objects.get("SF_Cam")
    if cam is None:
        cam = bpy.data.objects.new("SF_Cam", cam_data)
        scene.collection.objects.link(cam)
    cam.data = cam_data
    t = math.radians(tilt_deg)
    d = 6.0
    cam.location = (0.0, -d * math.sin(t), d * math.cos(t))
    cam.rotation_euler = (t, 0.0, 0.0)
    scene.camera = cam
    return res / ortho          # pixels per blender unit


def wipe():
    """Remove the rig AND any name-suffixed leftovers.

    A plain select_all/delete only removes what is selectable. If a previous
    build left objects whose names Blender auto-suffixed (SF_Flame_00.001),
    they survive, get re-suffixed on the next build, and accumulate as
    invisible geometry that still has its own material slots.
    """
    for ob in [o for o in bpy.data.objects if o.name.startswith("SF_")]:
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=True)
    for c in [c for c in bpy.data.collections if c.name.startswith("SF_")]:
        bpy.data.collections.remove(c)
    for c in [c for c in bpy.data.collections if c.name.startswith("VFX_Shield")]:
        bpy.data.collections.remove(c)
    for m in [m for m in bpy.data.materials if m.name.startswith("M_SF_")]:
        bpy.data.materials.remove(m, do_unlink=True)
    for me in [m for m in bpy.data.meshes if m.name.startswith("SF_")]:
        bpy.data.meshes.remove(me, do_unlink=True)


def collections(*names):
    root = bpy.data.collections.new("VFX_ShieldFire")
    bpy.context.scene.collection.children.link(root)
    out = {}
    for n in names:
        c = bpy.data.collections.new(n)
        root.children.link(c)
        out[n] = c
    return out


# --------------------------------------------------------------------------
# geometry
# --------------------------------------------------------------------------

def card(name, w, h, coll):
    """Flat card in the XY plane, centred. w/h independent so a flame can be
    tall and narrow while a core glow is wide and short."""
    me = bpy.data.meshes.new(name)
    hw, hh = w / 2.0, h / 2.0
    me.from_pydata([(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], [],
                   [(0, 1, 2, 3)])
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    # index by vertex_index: loop order depends on face winding
    for lp in me.loops:
        uv.data[lp.index].uv = [(0, 0), (1, 0), (1, 1), (0, 1)][lp.vertex_index]
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _blended(mat):
    mat.use_nodes = True
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    mat.use_backface_culling = False
    return mat.node_tree


def _math(nt, op, val=None, b=None, x=0, y=0):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = (x, y)
    if b is not None:
        n.inputs[1].default_value = b
    if val is not None:
        if hasattr(val, "is_output"):
            nt.links.new(val, n.inputs[0])
        else:
            n.inputs[0].default_value = val
    return n


def _ramp(nt, pos0, col0, pos1, col1, x=0, y=0, ease=True):
    """A two-stop ColorRamp. Every mask in this rig goes through this so the
    stop order is always explicit - a white@0 stop on an inverted signal turns
    the entire surface opaque, which is the single most common failure here."""
    n = nt.nodes.new("ShaderNodeValToRGB")
    n.location = (x, y)
    if ease:
        n.color_ramp.interpolation = "EASE"
    n.color_ramp.elements[0].position = pos0
    n.color_ramp.elements[0].color = tuple(col0) + (1.0,)
    n.color_ramp.elements[1].position = pos1
    n.color_ramp.elements[1].color = tuple(col1) + (1.0,)
    return n


# --------------------------------------------------------------------------
# materials
# --------------------------------------------------------------------------

def flame_mat(name, base_col, tip_col, cycles=7.0, gamma_lo=0.34,
              gamma_hi=0.68, warp=0.55, gain=1.7, taper_end=0.68,
              pinch_end=0.58, strand_scale=16.0):
    """A single upright flame card.

    base_col is the colour at the card's BOTTOM (hottest), tip_col at the TOP.
    Fire is hottest where it is closest to the fuel, so the ramp runs hot at
    the base and darkens upward.

    Measured conventions (verified by rendering probes, not assumed):
      * uv.y == 0 is the card's BASE, uv.y == 1 is the TIP. A taper of
        white@0 -> black@taper_end therefore dissolves the top, which is what
        stops the flame ending in a hard horizontal cut.
      * |uv.x*2-1| is the across-card distance; ABS is mandatory because a
        ColorRamp clamps the negative half to the "opaque" stop and turns the
        left half of every card into a solid block.
      * A second, much finer noise is multiplied into the alpha. One octave
        cannot make holes, so the flame renders as a solid mass.
    """
    mat = bpy.data.materials.new(name)
    nt = _blended(mat)
    nt.nodes.clear()

    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1600, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-1440, 300)
    nt.links.new(tc.outputs["UV"], sep.inputs[0])

    # mapping is what we scroll to make tongues RISE
    mapn = nt.nodes.new("ShaderNodeMapping")
    mapn.location = (-1200, -180)
    mapn.inputs["Scale"].default_value = (1.0, 0.85, 1.0)
    nt.links.new(tc.outputs["UV"], mapn.inputs["Vector"])

    # domain warp: curls the flame so it licks rather than bubbles
    wn = nt.nodes.new("ShaderNodeTexNoise")
    wn.location = (-1000, -440)
    wn.noise_dimensions = "4D"
    wn.inputs["Scale"].default_value = 1.5
    wn.inputs["Detail"].default_value = 1.5
    nt.links.new(tc.outputs["UV"], wn.inputs["Vector"])

    wcen = nt.nodes.new("ShaderNodeVectorMath")
    wcen.operation = "SUBTRACT"
    wcen.location = (-820, -440)
    wcen.inputs[1].default_value = (0.5, 0.5, 0.5)
    nt.links.new(wn.outputs["Color"], wcen.inputs[0])

    wsc = nt.nodes.new("ShaderNodeVectorMath")
    wsc.operation = "SCALE"
    wsc.location = (-660, -440)
    wsc.inputs["Scale"].default_value = warp
    nt.links.new(wcen.outputs["Vector"], wsc.inputs[0])

    wadd = nt.nodes.new("ShaderNodeVectorMath")
    wadd.operation = "ADD"
    wadd.location = (-500, -300)
    nt.links.new(mapn.outputs["Vector"], wadd.inputs[0])
    nt.links.new(wsc.outputs["Vector"], wadd.inputs[1])

    fn = nt.nodes.new("ShaderNodeTexNoise")
    fn.location = (-320, -100)
    fn.noise_dimensions = "4D"
    fn.inputs["Scale"].default_value = cycles
    fn.inputs["Detail"].default_value = 5.0
    fn.inputs["Roughness"].default_value = 0.58
    fn.inputs["Distortion"].default_value = 0.5
    nt.links.new(wadd.outputs["Vector"], fn.inputs["Vector"])

    # ---- ALPHA ------------------------------------------------------------
    # Multiplying several EASE ramps produced a smooth gradient, not a flame:
    # measured fill ratio 0.925 (a near-solid card) with a monotonic alpha
    # histogram. Real fire needs a HARD threshold on the noise so the body is
    # genuinely opaque with genuinely empty gaps, and only the edges soften.
    #
    # body = threshold(detail noise), then shaped by the vertical taper and the
    # horizontal pinch. One threshold, not four multiplied ramps.
    #
    # MEASURED: the detail noise Fac inside a card runs 0..0.73, mean 0.51, so
    # the threshold is placed just either side of 0.5.
    body = _ramp(nt, 0.46, (0, 0, 0), 0.56, (1, 1, 1), x=-300, y=-200,
                 ease=False)
    nt.links.new(fn.outputs["Fac"], body.inputs["Fac"])

    # soften the body edge just enough to avoid aliasing
    body_soft = _ramp(nt, 0.30, (0, 0, 0), 0.70, (1, 1, 1), x=-140, y=-200)
    nt.links.new(body.outputs["Color"], body_soft.inputs["Fac"])

    # vertical taper: solid low, dissolved at the tip
    taper = _ramp(nt, 0.02, (1, 1, 1), 0.80, (0, 0, 0), x=-900, y=300)
    nt.links.new(sep.outputs[1], taper.inputs["Fac"])

    # horizontal pinch: 0 at the card's centre line, 1 at its edges
    xh = _math(nt, "MULTIPLY", sep.outputs[0], b=2.0, x=-1240, y=-60)
    xa = _math(nt, "SUBTRACT", xh.outputs[0], b=1.0, x=-1080, y=-60)
    xabs = _math(nt, "ABSOLUTE", xa.outputs[0], x=-920, y=-60)
    xp = _ramp(nt, 0.20, (1, 1, 1), 0.95, (0, 0, 0), x=-760, y=-60)
    nt.links.new(xabs.outputs[0], xp.inputs["Fac"])

    a1 = _math(nt, "MULTIPLY", body_soft.outputs["Color"], x=40, y=60)
    nt.links.new(taper.outputs["Color"], a1.inputs[1])
    a2 = _math(nt, "MULTIPLY", a1.outputs[0], x=200, y=60)
    nt.links.new(xp.outputs["Color"], a2.inputs[1])
    a3 = a2

    # ---- COLOUR -----------------------------------------------------------
    # Driven by the same thresholded body mask as the alpha, so the hot core
    # lands on the opaque flame and the ragged edge goes dark red. Driving the
    # colour from a separate noise produced white fringes on the gaps.
    heat = _ramp(nt, 0.0, tip_col, 1.0, base_col, x=-300, y=560, ease=True)
    nt.links.new(body_soft.outputs["Color"], heat.inputs["Fac"])

    cmul = nt.nodes.new("ShaderNodeMixRGB")
    cmul.location = (200, 500)
    cmul.blend_type = "MULTIPLY"
    # Fac 0.55 with two bright colours lands near white. 0.30 keeps saturation.
    cmul.inputs["Fac"].default_value = 0.30
    nt.links.new(heat.outputs["Color"], cmul.inputs[1])
    nzc = _ramp(nt, 0.0, (0.34, 0.11, 0.02), 1.0, (1.0, 0.88, 0.60), x=0, y=320)
    nt.links.new(sep.outputs[1], nzc.inputs["Fac"])
    nt.links.new(nzc.outputs["Color"], cmul.inputs[2])

    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (620, 500)
    em.inputs["Strength"].default_value = 1.0
    nt.links.new(cmul.outputs["Color"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.location = (620, 220)
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.location = (800, 360)
    nt.links.new(a3.outputs[0], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (980, 360)
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return mat, nt, fn, mapn, wn


def radial_mat(name, core_col, edge_col, mask_hi=0.46, strength=1.0):
    """Soft radial glow, used for the core, rim beads and embers."""
    mat = bpy.data.materials.new(name)
    nt = _blended(mat)
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    tc.location = (-1000, 0)
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    sep.location = (-820, 0)
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    offs = []
    for i in range(2):
        s = _math(nt, "SUBTRACT", sep.outputs[i], b=0.5, x=-660, y=60 - i * 140)
        offs.append(s)
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    comb.location = (-500, -40)
    nt.links.new(offs[0].outputs[0], comb.inputs["X"])
    nt.links.new(offs[1].outputs[0], comb.inputs["Y"])
    ln = nt.nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    ln.location = (-340, -40)
    nt.links.new(comb.outputs["Vector"], ln.inputs[0])

    mask = _ramp(nt, 0.0, (1, 1, 1), mask_hi, (0, 0, 0), x=-160, y=-40)
    # Distance is 0 at the centre and ~0.5 at the rim, so the mask must run
    # WHITE -> BLACK as distance grows. Black->white here makes the centre a
    # hole and the rim a solid square - the glow reads as a pale card.
    nt.links.new(ln.outputs["Value"], mask.inputs["Fac"])

    tint = nt.nodes.new("ShaderNodeValToRGB")
    tint.location = (-160, 220)
    tint.color_ramp.elements[0].color = tuple(edge_col) + (1.0,)
    tint.color_ramp.elements[1].color = tuple(core_col) + (1.0,)
    nt.links.new(ln.outputs["Value"], tint.inputs["Fac"])

    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (60, 220)
    em.inputs["Strength"].default_value = strength
    nt.links.new(tint.outputs["Color"], em.inputs["Color"])
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.location = (60, -60)
    mx = nt.nodes.new("ShaderNodeMixShader")
    mx.location = (240, 60)
    nt.links.new(mask.outputs["Color"], mx.inputs["Fac"])
    nt.links.new(tr.outputs[0], mx.inputs[1])
    nt.links.new(em.outputs[0], mx.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (420, 60)
    nt.links.new(mx.outputs[0], out.inputs["Surface"])
    return mat


def detail_noise(mat):
    """The main 4D detail noise of a flame material (the warp-fed one)."""
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == "TEX_NOISE" and n.inputs["Vector"].is_linked \
                and n.inputs["Vector"].links[0].from_node.type == "VECT_MATH":
            return n
    return None


def export(out_dir, layers, with_preview=True):
    """Render per-layer frame sequences plus a flat composite.

    `layers` maps a label to the object names that make it up. Each layer is
    rendered alone so the game can composite them in its own order, and the
    preview is the full stack for eyeballing.

    frame_set is mandatory: write_still renders the CURRENT frame, so without
    it every output is a copy of frame 1.
    """
    import os
    import shutil

    scene = bpy.context.scene
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    written = 0

    for label, names in layers.items():
        d = os.path.join(out_dir, "sequences", label)
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        members = set(names)
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.hide_render = o.name not in members
        for f in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(d, "%s_%04d.png" % (label, f))
            bpy.ops.render.render(write_still=True)
            written += 1

    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = False

    if with_preview:
        d = os.path.join(out_dir, "preview")
        if os.path.isdir(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)
        for f in range(scene.frame_start, scene.frame_end + 1):
            scene.frame_set(f)
            scene.render.filepath = os.path.join(d, "composite_%04d.png" % f)
            bpy.ops.render.render(write_still=True)
            written += 1

    scene.frame_set(1)
    return written
