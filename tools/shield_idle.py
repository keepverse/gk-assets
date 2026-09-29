"""
Fire Shield idle v2: a transparent 3D globe with simulated, warm fire.

The procedural scene is the source of truth. A Blender gas-domain fire simulation
provides the flame volume; a clear sphere, small sparks, and warm lights support
it. The simulation cache is regenerated under ignored tmp/ when built.
"""

import math
import os
import random
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shield_rig as rig  # noqa: E402

FRAMES = 48
OUTPUT_START = 13
RES = 512
ORTHO = 1.8
FPS = 24
CENTRE = Vector((0.0, 0.0, 0.50))
SHELL_RADIUS = 0.455
FLOW_COUNT = 7
BURST_COUNT = 3
SPARKS_PER_BURST = 5
EMBER_COUNT = 7
SEED = 2409


def _loop_t(frame):
    # Frames 1-12 warm the gas simulation before the 36-frame sprite loop.
    return (frame - OUTPUT_START) / (FRAMES - OUTPUT_START)


def _move_to_collection(obj, collection):
    for old_collection in list(obj.users_collection):
        old_collection.objects.unlink(obj)
    collection.objects.link(obj)
    return obj


def _set_input(node, names, value):
    if isinstance(names, str):
        names = (names,)
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            socket.default_value = value
            return socket
    return None


def _new_surface(name, color, emission, emission_strength, roughness=0.35,
                 metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    principled = mat.node_tree.nodes.get("Principled BSDF")
    _set_input(principled, "Base Color", tuple(color) + (1.0,))
    _set_input(principled, "Roughness", roughness)
    _set_input(principled, "Metallic", metallic)
    _set_input(principled, ("Emission Color", "Emission"), tuple(emission) + (1.0,))
    _set_input(principled, "Emission Strength", emission_strength)
    return mat


def _glass_shell_mat():
    mat = bpy.data.materials.new("M_SF_GlassShell")
    nt = rig._blended(mat)
    nt.nodes.clear()
    coords = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 2.5
    noise.inputs["Roughness"].default_value = 0.62
    nt.links.new(coords.outputs["Generated"], noise.inputs["Vector"])
    surface = nt.nodes.new("ShaderNodeValToRGB")
    surface.color_ramp.elements[0].position = 0.30
    surface.color_ramp.elements[0].color = (0.12, 0.018, 0.002, 1.0)
    surface.color_ramp.elements[1].position = 0.70
    surface.color_ramp.elements[1].color = (0.85, 0.19, 0.012, 1.0)
    nt.links.new(noise.outputs["Fac"], surface.inputs["Fac"])
    fresnel = nt.nodes.new("ShaderNodeFresnel")
    fresnel.inputs["IOR"].default_value = 1.28

    # A faint, mottled surface across the sphere provides visible curvature.
    # Keep both the surface and rim translucent so the actor remains readable.
    rim_curve = nt.nodes.new("ShaderNodeMath")
    rim_curve.operation = "POWER"
    rim_curve.inputs[1].default_value = 2.0
    nt.links.new(fresnel.outputs["Fac"], rim_curve.inputs[0])
    rim_alpha = nt.nodes.new("ShaderNodeMath")
    rim_alpha.operation = "MULTIPLY"
    rim_alpha.inputs[1].default_value = 0.075
    nt.links.new(rim_curve.outputs[0], rim_alpha.inputs[0])
    surface_alpha = nt.nodes.new("ShaderNodeMapRange")
    surface_alpha.inputs["From Min"].default_value = 0.25
    surface_alpha.inputs["From Max"].default_value = 0.75
    surface_alpha.inputs["To Min"].default_value = 0.008
    surface_alpha.inputs["To Max"].default_value = 0.032
    nt.links.new(noise.outputs["Fac"], surface_alpha.inputs["Value"])
    alpha = nt.nodes.new("ShaderNodeMath")
    alpha.operation = "ADD"
    nt.links.new(surface_alpha.outputs["Result"], alpha.inputs[0])
    nt.links.new(rim_alpha.outputs[0], alpha.inputs[1])

    glass = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(surface.outputs["Color"], glass.inputs["Base Color"])
    _set_input(glass, "Roughness", 0.32)
    _set_input(glass, "Metallic", 0.05)
    _set_input(glass, ("Emission Color", "Emission"), (1.0, 0.09, 0.004, 1.0))
    _set_input(glass, "Emission Strength", 0.08)
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(alpha.outputs[0], mix.inputs[0])
    nt.links.new(transparent.outputs[0], mix.inputs[1])
    nt.links.new(glass.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def _make_sphere(name, radius, location, collection, material, segments=64):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=segments, ring_count=32, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.data.name = name
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    obj.data.materials.append(material)
    return _move_to_collection(obj, collection)


def _surface_trace(name, span, shape, collection, material):
    """A swept filament on the front of the sphere, not a camera-facing card."""
    points, radii = [], []
    for i in range(81):
        t = i / 80.0
        u = span[0] + (span[1] - span[0]) * t
        v = shape(u, t)
        depth = math.sqrt(max(0.0, 1.0 - u * u - v * v))
        points.append((SHELL_RADIUS * 1.006 * u,
                       SHELL_RADIUS * 1.006 * v,
                       SHELL_RADIUS * 1.006 * depth))
        radii.append(0.0032 * max(0.02, math.sin(math.pi * t) ** 0.7))
    return _tube_mesh(name, points, radii, collection, [material],
                      sides=6, object_location=CENTRE)


def _surface_trace_mat():
    mat = bpy.data.materials.new("M_SF_GlobeContour")
    nt = rig._blended(mat)
    nt.nodes.clear()
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    glow = nt.nodes.new("ShaderNodeEmission")
    glow.inputs["Color"].default_value = (1.0, 0.32, 0.045, 1.0)
    glow.inputs["Strength"].default_value = 0.55
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs[0].default_value = 0.30
    nt.links.new(transparent.outputs[0], mix.inputs[1])
    nt.links.new(glow.outputs[0], mix.inputs[2])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def _tube_mesh(name, centers, radii, collection, materials, closed=False,
               sides=9, object_location=(0.0, 0.0, 0.0), segment_materials=None,
               vertex_colors=None):
    centers = [Vector(point) for point in centers]
    rings = len(centers)
    vertices = []
    for i, point in enumerate(centers):
        if closed:
            tangent = centers[(i + 1) % rings] - centers[(i - 1) % rings]
        else:
            tangent = centers[min(i + 1, rings - 1)] - centers[max(i - 1, 0)]
        tangent.normalize()
        reference = Vector((0.0, 0.0, 1.0))
        if abs(tangent.dot(reference)) > 0.92:
            reference = Vector((0.0, 1.0, 0.0))
        axis_a = tangent.cross(reference).normalized()
        axis_b = tangent.cross(axis_a).normalized()
        for j in range(sides):
            angle = math.tau * j / sides
            offset = axis_a * math.cos(angle) + axis_b * math.sin(angle)
            vertices.append(tuple(point + offset * radii[i]))

    faces = []
    face_segments = []
    segments = rings if closed else rings - 1
    for i in range(segments):
        ni = (i + 1) % rings
        for j in range(sides):
            nj = (j + 1) % sides
            faces.append((i * sides + j, i * sides + nj,
                          ni * sides + nj, ni * sides + j))
            face_segments.append(i)

    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    if vertex_colors:
        heat = mesh.color_attributes.new(
            name="FlameHeat", type="FLOAT_COLOR", domain="POINT")
        for ring_index, color in enumerate(vertex_colors):
            for side_index in range(sides):
                heat.data[ring_index * sides + side_index].color = tuple(color) + (1.0,)
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = object_location
    for mat in materials:
        mesh.materials.append(mat)
    for polygon, segment in zip(mesh.polygons, face_segments):
        polygon.use_smooth = True
        if segment_materials:
            polygon.material_index = segment_materials[min(segment, len(segment_materials) - 1)]
    return obj


def _fire_plume_mat(name):
    """Shaded 3D fire with vertex heat and a light procedural surface breakup."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    coords = nt.nodes.new("ShaderNodeTexCoord")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 2.0
    noise.inputs["Roughness"].default_value = 0.68
    nt.links.new(coords.outputs["Generated"], noise.inputs["Vector"])
    heat = nt.nodes.new("ShaderNodeVertexColor")
    heat.layer_name = "FlameHeat"

    texture_tint = nt.nodes.new("ShaderNodeValToRGB")
    texture_tint.color_ramp.elements[0].color = (0.54, 0.22, 0.07, 1.0)
    texture_tint.color_ramp.elements[1].color = (1.0, 0.83, 0.46, 1.0)
    nt.links.new(noise.outputs["Fac"], texture_tint.inputs["Fac"])
    modulation = nt.nodes.new("ShaderNodeMixRGB")
    modulation.blend_type = "MULTIPLY"
    modulation.inputs[0].default_value = 0.18
    nt.links.new(heat.outputs["Color"], modulation.inputs[1])
    nt.links.new(texture_tint.outputs["Color"], modulation.inputs[2])

    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.10
    bump.inputs["Distance"].default_value = 0.012
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    _set_input(bsdf, "Base Color", (1.0, 0.19, 0.006, 1.0))
    _set_input(bsdf, "Roughness", 0.38)
    _set_input(bsdf, "Metallic", 0.04)
    _set_input(bsdf, ("Emission Color", "Emission"), (1.0, 0.20, 0.006, 1.0))
    _set_input(bsdf, "Emission Strength", 0.70)
    nt.links.new(modulation.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(modulation.outputs["Color"], bsdf.inputs.get("Emission Color") or bsdf.inputs.get("Emission"))
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return mat


def _fire_tongue(name, root, direction, length, width, bend, collection,
                 material, rng, heat_profile=None):
    direction = Vector(direction).normalized()
    reference = Vector((0.0, 0.0, 1.0))
    if abs(direction.dot(reference)) > 0.92:
        reference = Vector((0.0, 1.0, 0.0))
    side = direction.cross(reference).normalized()
    other = direction.cross(side).normalized()
    curl = rng.uniform(-0.16, 0.16)
    ts = (0.0, 0.12, 0.28, 0.48, 0.68, 0.87, 1.0)
    width_profile = (0.28, 0.72, 1.0, 0.82, 0.55, 0.23, 0.008)
    if heat_profile is None:
        heat_profile = (
            (1.0, 0.54, 0.075),
            (1.0, 0.43, 0.038),
            (1.0, 0.32, 0.018),
            (0.98, 0.23, 0.010),
            (0.86, 0.14, 0.005),
            (0.60, 0.060, 0.002),
            (0.32, 0.018, 0.001),
        )
    points, radii = [], []
    for t, profile in zip(ts, width_profile):
        sway = bend * math.sin(math.pi * t) + curl * length * math.sin(math.tau * t)
        point = direction * (length * t) + side * sway
        point += other * (0.035 * length * math.sin(math.pi * t))
        points.append(point)
        radii.append(width * profile)
    obj = _tube_mesh(
        name, points, radii, collection, [material], closed=False, sides=9,
        object_location=root, vertex_colors=heat_profile)
    return obj


def _area_light(name, location, color, energy, size, target):
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    data.color = color
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector(target) - Vector(location)).to_track_quat("-Z", "Y").to_euler()
    return obj


def _simulated_fire(collection):
    """Create Blender's native gas fire and leave its cache ready to bake."""
    scene = bpy.context.scene
    scene.gravity = (0.0, -9.81, -0.6)  # Fire rises along screen-up world Y.
    flow_specs = (
        (0.00, 0.44, 0.28),
        (-0.38, 0.22, 0.22),
        (-0.22, 0.38, 0.27),
        (0.22, 0.38, 0.26),
        (0.38, 0.22, 0.22),
        (-0.47, 0.03, 0.18),
        (0.47, 0.03, 0.18),
    )
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=24, ring_count=12, radius=0.035,
        location=(flow_specs[0][0], flow_specs[0][1], CENTRE.z))
    first = bpy.context.object
    first.name = "SF_FireFlow_00"
    bpy.ops.object.quick_smoke(style="FIRE")

    invisible = bpy.data.materials.new("M_SF_InvisibleFlow")
    nt = rig._blended(invisible)
    nt.nodes.clear()
    transparent = nt.nodes.new("ShaderNodeBsdfTransparent")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(transparent.outputs[0], out.inputs["Surface"])
    first.data.materials.append(invisible)
    first_flow = next(m for m in first.modifiers if m.type == "FLUID").flow_settings
    first_flow.fuel_amount = flow_specs[0][2]
    _move_to_collection(first, collection)

    for index, (x, y, fuel) in enumerate(flow_specs[1:], start=1):
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24, ring_count=12, radius=0.028,
            location=(x, y, CENTRE.z))
        flow = bpy.context.object
        flow.name = "SF_FireFlow_%02d" % index
        modifier = flow.modifiers.new("Fire Flow", "FLUID")
        modifier.fluid_type = "FLOW"
        modifier.flow_settings.flow_type = "FIRE"
        modifier.flow_settings.flow_behavior = "INFLOW"
        modifier.flow_settings.fuel_amount = fuel
        flow.data.materials.append(invisible)
        _move_to_collection(flow, collection)

    domain = bpy.data.objects["Smoke Domain"]
    domain.name = "SF_FireGasDomain"
    domain.location = (0.0, 0.38, CENTRE.z)
    domain.dimensions = (1.18, 1.05, 0.70)
    bpy.ops.object.select_all(action="DESELECT")
    domain.select_set(True)
    bpy.context.view_layer.objects.active = domain
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    _move_to_collection(domain, collection)

    settings = next(m for m in domain.modifiers if m.type == "FLUID").domain_settings
    settings.resolution_max = 112
    settings.vorticity = 1.0
    settings.beta = 0.6
    settings.use_noise = True
    settings.noise_scale = 2
    settings.use_dissolve_smoke = True
    settings.dissolve_speed = 10
    settings.cache_type = "ALL"
    settings.cache_frame_start = 1
    settings.cache_frame_end = FRAMES
    repo_root = Path(__file__).resolve().parents[1]
    tmp_root = (repo_root / "tmp").resolve()
    cache_dir = (tmp_root / "fluid_fire_idle").resolve()
    if cache_dir.parent != tmp_root:
        raise RuntimeError("Fire cache escaped the ignored tmp directory")
    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    settings.cache_directory = str(cache_dir)

    volume = domain.data.materials[0].node_tree.nodes.get("Principled Volume")
    # At 0.22 the flame alpha never exceeded 4/255, making the sprite nearly
    # invisible in-game despite bright unassociated RGB in Blender's preview.
    volume.inputs["Density"].default_value = 12.0
    volume.inputs["Density Attribute"].default_value = "flame"
    volume.inputs["Blackbody Intensity"].default_value = 3.0
    return domain


def _warm_fire_lights():
    """Light the shield body with a restrained, looping fire pulse."""
    for index, x in enumerate((-0.27, 0.27)):
        data = bpy.data.lights.new("SF_FireBounce_%02d" % index, "POINT")
        data.color = (1.0, 0.32, 0.07)
        data.shadow_soft_size = 0.30
        obj = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = (x, 0.31, 0.74)
        for frame in range(1, FRAMES + 1):
            t = _loop_t(frame)
            data.energy = 11.0 + 3.0 * math.sin(math.tau * t + index * 1.7)
            data.keyframe_insert("energy", frame=frame)


def _soft_fire_glow():
    group = bpy.data.node_groups.new("SF_FireGlow", "CompositorNodeTree")
    layers = group.nodes.new("CompositorNodeRLayers")
    glare = group.nodes.new("CompositorNodeGlare")
    glare.inputs["Type"].default_value = "Bloom"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = 1.0
    glare.inputs["Strength"].default_value = 0.15
    glare.inputs["Size"].default_value = 0.05
    group.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    output = group.nodes.new("NodeGroupOutput")
    group.links.new(layers.outputs["Image"], glare.inputs["Image"])
    group.links.new(glare.outputs["Image"], output.inputs["Image"])
    scene = bpy.context.scene
    scene.compositing_node_group = group
    scene.render.use_compositing = True


def _scene_setup():
    px = rig.setup_scene(res=RES, ortho=ORTHO, tilt_deg=12.0, frames=FRAMES, fps=FPS)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RES
    scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    # Bake the warm-up frames too; only frames 13-48 become gameplay sprites.
    scene.frame_start = 1
    _area_light("SF_Key_Area", (-2.0, -2.6, 2.5), (1.0, 0.48, 0.20), 84.0, 0.72, CENTRE)
    _area_light("SF_Fill_Area", (2.0, -0.8, 1.4), (1.0, 0.20, 0.035), 9.0, 1.9, CENTRE)
    _area_light("SF_Rim_Area", (0.4, 2.3, 1.9), (1.0, 0.58, 0.20), 48.0, 0.72, CENTRE)
    _warm_fire_lights()
    _soft_fire_glow()
    return px


def _pulse(t, event_t, width=0.075):
    delta = (t - event_t + 0.5) % 1.0 - 0.5
    envelope = max(0.0, 1.0 - abs(delta) / width)
    return math.sin(envelope * math.pi * 0.5)


def build():
    rig.wipe()
    # Clear maps packed by the earlier opaque-sun version when rebuilding an
    # already-open scene; the transparent shield has no image textures.
    for image in list(bpy.data.images):
        if image.name.startswith("T_FireShield_SunSurface_"):
            bpy.data.images.remove(image)

    px = _scene_setup()
    cols = rig.collections("SF_Shell", "SF_Frame", "SF_Flames", "SF_Bursts", "SF_Embers")
    rng = random.Random(SEED)

    shell_mat = _glass_shell_mat()
    shell = _make_sphere(
        "SF_GlobeShell", SHELL_RADIUS, CENTRE, cols["SF_Shell"], shell_mat, segments=96)
    # The transparent envelope breathes without covering the actor.
    for frame in range(1, FRAMES + 1):
        t = _loop_t(frame)
        pulse = 1.0 + 0.024 * math.sin(math.tau * t)
        shell.scale = (pulse, pulse, pulse)
        shell.keyframe_insert("scale", frame=frame)

    # Three short filaments cling to the curved front hemisphere. Their depth
    # follows the sphere equation, giving the transparent globe surface cues
    # without placing an opaque disc over the actor.
    trace_mat = _surface_trace_mat()
    traces = [
        _surface_trace("SF_GlobeContour_Upper", (-0.80, 0.69),
                       lambda u, t: 0.22 + 0.20 * (1.0 - (u / 0.85) ** 2),
                       cols["SF_Shell"], trace_mat),
        _surface_trace("SF_GlobeContour_Lower", (-0.62, 0.77),
                       lambda u, t: -0.22 - 0.12 * (1.0 - (u / 0.85) ** 2),
                       cols["SF_Shell"], trace_mat),
        _surface_trace("SF_GlobeContour_Slant", (-0.42, 0.43),
                       lambda u, t: -0.39 + 0.87 * t + 0.07 * math.sin(math.pi * t),
                       cols["SF_Shell"], trace_mat),
    ]
    for frame in range(1, FRAMES + 1):
        t = _loop_t(frame)
        for index, trace in enumerate(traces):
            trace.rotation_euler.z = 0.035 * math.sin(math.tau * t + index)
            trace.keyframe_insert("rotation_euler", frame=frame)

    view_dir = Vector((0.0, -math.sin(math.radians(12.0)), math.cos(math.radians(12.0)))).normalized()
    basis_u = Vector((1.0, 0.0, 0.0))
    basis_v = view_dir.cross(basis_u).normalized()
    domain = _simulated_fire(cols["SF_Flames"])

    # Three localized micro-eruptions use actual tapered tubes and small
    # emissive icospheres; each pops once during the 1.5-second idle loop.
    burst_names = []
    burst_material = _fire_plume_mat("M_SF_BurstPlume")
    burst_times = (0.16, 0.50, 0.83)
    for event_index, event_t in enumerate(burst_times):
        angle = math.tau * (event_index / BURST_COUNT) + 0.24
        normal = (basis_u * math.cos(angle) + basis_v * math.sin(angle)).normalized()
        root = CENTRE + normal * SHELL_RADIUS
        flash_mat = _new_surface(
            "M_SF_BurstCore_%02d" % event_index,
            (0.70, 0.22, 0.008), (1.0, 0.57, 0.035), 0.92,
            roughness=0.28)
        flash = _make_sphere(
            "SF_BurstCore_%02d" % event_index, 0.024, root,
            cols["SF_Bursts"], flash_mat, segments=24)
        burst_names.append(flash.name)
        sparks = []
        for spark_index in range(SPARKS_PER_BURST):
            phase = math.tau * spark_index / SPARKS_PER_BURST + rng.uniform(-0.20, 0.20)
            tangent = (basis_u * math.cos(phase) + basis_v * math.sin(phase)).normalized()
            spark_dir = (normal * 0.58 + tangent * 0.82).normalized()
            spark = _fire_tongue(
                "SF_Burst_%02d_Spark_%02d" % (event_index, spark_index),
                root, spark_dir, rng.uniform(0.075, 0.12),
                rng.uniform(0.008, 0.014), rng.uniform(-0.018, 0.018),
                cols["SF_Bursts"], burst_material, rng,
                heat_profile=(
                    (1.0, 0.70, 0.16), (1.0, 0.55, 0.09),
                    (1.0, 0.38, 0.03), (1.0, 0.24, 0.012),
                    (0.82, 0.09, 0.003), (0.55, 0.035, 0.001),
                    (0.32, 0.01, 0.001)))
            sparks.append(spark)
            burst_names.append(spark.name)

        for frame in range(1, FRAMES + 1):
            t = _loop_t(frame)
            pop = _pulse(t, event_t, 0.082)
            scale = 0.018 + 0.982 * pop
            flash.scale = (scale, scale, scale)
            flash.keyframe_insert("scale", frame=frame)
            for spark in sparks:
                spark.scale = (scale, scale, scale)
                spark.keyframe_insert("scale", frame=frame)

    ember_mat = _new_surface(
        "M_SF_Cinder", (0.48, 0.065, 0.002), (1.0, 0.23, 0.006),
        0.72, roughness=0.40)
    ember_names = []
    for i in range(EMBER_COUNT):
        base_angle = rng.uniform(0.0, math.tau)
        phase = rng.uniform(0.0, math.tau)
        size = rng.uniform(0.008, 0.014)
        ember = _make_sphere(
            "SF_Cinder_%02d" % i, size, CENTRE, cols["SF_Embers"],
            ember_mat, segments=16)
        ember_names.append(ember.name)
        for frame in range(1, FRAMES + 1):
            t = _loop_t(frame)
            angle = base_angle + math.tau * t
            radius = SHELL_RADIUS + 0.075 + 0.020 * math.sin(math.tau * t + phase)
            depth = 0.035 * math.sin(math.tau * t + phase)
            point = CENTRE + basis_u * (radius * math.cos(angle))
            point += basis_v * (radius * math.sin(angle)) + view_dir * depth
            ember.location = point
            pulse = 0.78 + 0.18 * math.sin(math.tau * t + phase)
            ember.scale = (pulse, pulse, pulse)
            ember.keyframe_insert("location", frame=frame)
            ember.keyframe_insert("scale", frame=frame)

    return px, domain, burst_names, ember_names


LAYERS = {
    "shell": ["SF_GlobeShell", "SF_GlobeContour_Upper",
              "SF_GlobeContour_Lower", "SF_GlobeContour_Slant"],
    "flames": ["SF_FireGasDomain"] + [
        "SF_FireFlow_%02d" % i for i in range(FLOW_COUNT)],
    "bursts": [
        name for i in range(BURST_COUNT)
        for name in (["SF_BurstCore_%02d" % i] + [
            "SF_Burst_%02d_Spark_%02d" % (i, j)
            for j in range(SPARKS_PER_BURST)])
    ],
    "embers": ["SF_Cinder_%02d" % i for i in range(EMBER_COUNT)],
}


def export(out_dir, with_preview=True):
    return rig.export(out_dir, LAYERS, with_preview=with_preview)


if __name__ == "__main__":
    out_dir = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), os.pardir, "vfx", "shield_fire_idle"))
    px, domain, _bursts, _embers = build()
    blend_path = os.path.join(out_dir, "shield_fire_idle.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    bpy.ops.object.select_all(action="DESELECT")
    domain.select_set(True)
    bpy.context.view_layer.objects.active = domain
    bpy.ops.fluid.bake_all()
    bpy.context.scene.frame_start = OUTPUT_START
    written = export(out_dir)
    bpy.context.scene.frame_set(24)
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print("shield_fire_idle: %d px/unit, %d PNGs -> %s" % (round(px, 1), written, out_dir))
