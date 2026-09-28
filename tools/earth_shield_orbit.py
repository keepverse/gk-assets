"""Build the Earth Shield orbit blockout scene and save its reusable rock meshes."""

from __future__ import annotations

import bmesh
import math
from pathlib import Path
import random

import bpy
from mathutils import Euler, Vector


def project_root() -> Path:
    """Resolve the repo from this script path or Blender's working directory."""
    script_path = globals().get("__file__")
    candidates = []
    if script_path:
        candidates.append(Path(script_path).resolve().parents[1])
    here = Path.cwd().resolve()
    candidates.extend((here, *here.parents))
    for candidate in candidates:
        if (candidate / "assets" / "vfx" / "earth_shield" / "textures").is_dir():
            return candidate
    raise RuntimeError("Could not locate gk-assets from the script path or Blender working directory")


ROOT = project_root()
ASSET_DIR = ROOT / "assets" / "vfx" / "earth_shield"
TEXTURE_DIR = ASSET_DIR / "textures"
BLEND_PATH = ASSET_DIR / "earth_shield_orbit.blend"

TEXTURE_SETS = {
    "BasaltHeart": "Rock01_BasaltHeart",
    "SandstonePlate": "Rock02_SandstonePlate",
    "MossboundStone": "Rock03_MossboundStone",
    "QuartzSeam": "Rock04_QuartzSeam",
}

HERO_ROCKS = (
    {
        "id": "01",
        "name": "BasaltHeart",
        "dims": (0.245, 0.215, 0.285),
        "radius": 1.43,
        "height": 0.12,
        "phase": 18,
        "tilt": (18, -14),
        "seed": 117,
    },
    {
        "id": "02",
        "name": "SandstonePlate",
        "dims": (0.285, 0.245, 0.17),
        "radius": 1.59,
        "height": -0.07,
        "phase": 151,
        "tilt": (-26, 19),
        "seed": 223,
    },
    {
        "id": "03",
        "name": "MossboundStone",
        "dims": (0.235, 0.22, 0.265),
        "radius": 1.47,
        "height": 0.15,
        "phase": 277,
        "tilt": (12, 34),
        "seed": 331,
    },
)

# One full orbit over six seconds. Frame 145 is the exact wrap point; frames
# 1..144 form the rendered six-second clip without a duplicate endpoint.
ORBIT_PERIOD_FRAMES = 144


def new_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def clear_scene() -> None:
    scene = bpy.context.scene
    scene.world = None
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for collection in list(scene.collection.children):
        scene.collection.children.unlink(collection)
        if collection.users == 0:
            bpy.data.collections.remove(collection)
    for datablocks in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.actions,
        bpy.data.materials,
        bpy.data.images,
        bpy.data.worlds,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def set_texture_space(image: bpy.types.Image, colorspace: str) -> None:
    image.colorspace_settings.name = colorspace


def load_image(path: Path, colorspace: str) -> bpy.types.Image:
    if not path.is_file():
        raise FileNotFoundError(f"Earth Shield texture not found: {path}")
    image = bpy.data.images.load(str(path), check_existing=True)
    set_texture_space(image, colorspace)
    return image


def rock_material(name: str, texture_set: str) -> bpy.types.Material:
    source = TEXTURE_SETS[texture_set]
    images = {
        "BaseColor": load_image(TEXTURE_DIR / f"T_EarthShield_{source}_BaseColor.png", "sRGB"),
        "AO": load_image(TEXTURE_DIR / f"T_EarthShield_{source}_AO.png", "Non-Color"),
        "Roughness": load_image(TEXTURE_DIR / f"T_EarthShield_{source}_Roughness.png", "Non-Color"),
        "NormalGL": load_image(TEXTURE_DIR / f"T_EarthShield_{source}_NormalGL.png", "Non-Color"),
        "Height": load_image(TEXTURE_DIR / f"T_EarthShield_{source}_Height.png", "Non-Color"),
    }

    material = bpy.data.materials.new(f"M_ES_{texture_set}")
    material.use_nodes = True
    material.diffuse_color = (0.22, 0.18, 0.13, 1.0)
    material.roughness = 0.84
    material["earth_shield_texture_set"] = texture_set
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (780, 80)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (500, 80)
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["Specular IOR Level"].default_value = 0.22
    links.new(shader.outputs["BSDF"], output.inputs["Surface"])

    uv = nodes.new("ShaderNodeTexCoord")
    uv.location = (-900, 100)

    def texture_node(map_name: str, image: bpy.types.Image, y: int) -> bpy.types.ShaderNodeTexImage:
        node = nodes.new("ShaderNodeTexImage")
        node.name = f"{map_name}_{texture_set}"
        node.label = map_name
        node.image = image
        node.extension = "REPEAT"
        node.interpolation = "Linear"
        node.location = (-660, y)
        links.new(uv.outputs["UV"], node.inputs["Vector"])
        return node

    base = texture_node("Base Color", images["BaseColor"], 400)
    ao = texture_node("Ambient Occlusion", images["AO"], 180)
    roughness = texture_node("Roughness", images["Roughness"], -40)
    normal = texture_node("OpenGL Normal", images["NormalGL"], -260)
    height = texture_node("Height", images["Height"], -480)

    ao_mix = nodes.new("ShaderNodeMixRGB")
    ao_mix.blend_type = "MULTIPLY"
    ao_mix.inputs["Fac"].default_value = 0.24
    ao_mix.location = (-100, 330)
    links.new(base.outputs["Color"], ao_mix.inputs["Color1"])
    links.new(ao.outputs["Color"], ao_mix.inputs["Color2"])
    links.new(ao_mix.outputs["Color"], shader.inputs["Base Color"])
    links.new(roughness.outputs["Color"], shader.inputs["Roughness"])

    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.space = "TANGENT"
    normal_map.inputs["Strength"].default_value = 0.38
    normal_map.location = (-100, -100)
    links.new(normal.outputs["Color"], normal_map.inputs["Color"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.12
    bump.inputs["Distance"].default_value = 0.012
    bump.location = (180, -100)
    links.new(height.outputs["Color"], bump.inputs["Height"])
    links.new(normal_map.outputs["Normal"], bump.inputs["Normal"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return material


def dome_shell_material() -> bpy.types.Material:
    """Create the reusable transparent shield shell shader, without a dome mesh."""
    material = bpy.data.materials.get("M_ES_DomeShell")
    if material is None:
        material = bpy.data.materials.new("M_ES_DomeShell")
    material.use_nodes = True
    material.use_fake_user = True
    material.surface_render_method = "BLENDED"
    material.diffuse_color = (0.20, 0.31, 0.20, 0.22)
    material["role"] = "transparent Earth Shield dome shell; geometry and animation authored separately"
    material["reveal_axis"] = "world Z, bottom to top"
    material["shell_opacity"] = 0.045
    material["rim_tint"] = "warm white-gold"

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (1220, 160)
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (600, 400)
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.location = (600, 140)
    shader.inputs["Metallic"].default_value = 0.04
    shader.inputs["Roughness"].default_value = 0.46
    shader.inputs["Specular IOR Level"].default_value = 0.28
    shader.inputs["Emission Color"].default_value = (1.0, 0.84, 0.57, 1.0)
    shader.inputs["Emission Strength"].default_value = 0.0
    shell_mix = nodes.new("ShaderNodeMixShader")
    shell_mix.name = "ES_TransparentShell"
    shell_mix.label = "Low-opacity shell + edge visibility"
    shell_mix.location = (900, 340)
    links.new(transparent.outputs["BSDF"], shell_mix.inputs[1])
    links.new(shader.outputs["BSDF"], shell_mix.inputs[2])

    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.location = (-1180, 680)
    separate = nodes.new("ShaderNodeSeparateXYZ")
    separate.location = (-960, 680)
    links.new(geometry.outputs["Position"], separate.inputs["Vector"])

    reveal_height = nodes.new("ShaderNodeValue")
    reveal_height.name = "ES_RevealHeight"
    reveal_height.label = "Reveal front: world Z, animate bottom → top"
    reveal_height.outputs[0].default_value = 2.30
    reveal_height.location = (-960, 940)

    reveal_width = nodes.new("ShaderNodeValue")
    reveal_width.name = "ES_RevealWidth"
    reveal_width.label = "Glow-front thickness"
    reveal_width.outputs[0].default_value = 0.075
    reveal_width.location = (-960, 1080)

    visible = nodes.new("ShaderNodeMath")
    visible.operation = "LESS_THAN"
    visible.name = "ES_RevealedBelowFront"
    visible.label = "Only show shell below reveal front"
    visible.location = (-690, 760)
    links.new(separate.outputs["Z"], visible.inputs[0])
    links.new(reveal_height.outputs[0], visible.inputs[1])

    front_delta = nodes.new("ShaderNodeMath")
    front_delta.operation = "SUBTRACT"
    front_delta.location = (-690, 570)
    links.new(separate.outputs["Z"], front_delta.inputs[0])
    links.new(reveal_height.outputs[0], front_delta.inputs[1])
    front_distance = nodes.new("ShaderNodeMath")
    front_distance.operation = "ABSOLUTE"
    front_distance.location = (-490, 570)
    links.new(front_delta.outputs[0], front_distance.inputs[0])
    front_band = nodes.new("ShaderNodeMapRange")
    front_band.name = "ES_AnimatedGlowBand"
    front_band.label = "Bright edge travels with reveal front"
    front_band.clamp = True
    front_band.inputs["From Min"].default_value = 0.0
    front_band.inputs["To Min"].default_value = 1.0
    front_band.inputs["To Max"].default_value = 0.0
    front_band.location = (-270, 570)
    links.new(front_distance.outputs[0], front_band.inputs["Value"])
    links.new(reveal_width.outputs[0], front_band.inputs["From Max"])

    texcoord = nodes.new("ShaderNodeTexCoord")
    texcoord.location = (-1180, 120)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.name = "ES_DomeEarthNoise"
    noise.label = "Soft mineral mottling"
    noise.noise_dimensions = "4D"
    noise.inputs["Scale"].default_value = 5.0
    noise.inputs["Detail"].default_value = 3.2
    noise.inputs["Roughness"].default_value = 0.62
    noise.location = (-960, 180)
    links.new(texcoord.outputs["Generated"], noise.inputs["Vector"])

    idle_phase = nodes.new("ShaderNodeValue")
    idle_phase.name = "ES_IdlePhase"
    idle_phase.label = "Animate slowly during active shield idle"
    idle_phase.outputs[0].default_value = 0.0
    idle_phase.location = (-1180, -100)
    links.new(idle_phase.outputs[0], noise.inputs["W"])

    earth_ramp = nodes.new("ShaderNodeValToRGB")
    earth_ramp.name = "ES_EarthTint"
    earth_ramp.label = "Smoky sage / mineral green"
    earth_ramp.color_ramp.elements[0].position = 0.22
    earth_ramp.color_ramp.elements[0].color = (0.035, 0.065, 0.046, 1.0)
    earth_ramp.color_ramp.elements[1].position = 0.78
    earth_ramp.color_ramp.elements[1].color = (0.22, 0.32, 0.17, 1.0)
    earth_ramp.location = (-690, 180)
    links.new(noise.outputs["Fac"], earth_ramp.inputs["Fac"])

    voronoi = nodes.new("ShaderNodeTexVoronoi")
    voronoi.name = "ES_MineralVeinTexture"
    voronoi.label = "Broad, restrained mineral seams"
    voronoi.feature = "DISTANCE_TO_EDGE"
    voronoi.inputs["Scale"].default_value = 3.2
    voronoi.inputs["Randomness"].default_value = 0.72
    voronoi.location = (-960, -250)
    links.new(texcoord.outputs["Generated"], voronoi.inputs["Vector"])

    vein_ramp = nodes.new("ShaderNodeValToRGB")
    vein_ramp.name = "ES_MineralVeinMask"
    vein_ramp.label = "Thin seam mask"
    vein_ramp.color_ramp.elements[0].position = 0.002
    vein_ramp.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    vein_ramp.color_ramp.elements[1].position = 0.014
    vein_ramp.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
    vein_ramp.location = (-690, -250)
    links.new(voronoi.outputs["Distance"], vein_ramp.inputs["Fac"])

    vein_tint = nodes.new("ShaderNodeMixRGB")
    vein_tint.blend_type = "MIX"
    vein_tint.name = "ES_MineralTint"
    vein_tint.label = "Subtle pale mineral lines"
    vein_tint.inputs["Color2"].default_value = (0.18, 0.24, 0.14, 1.0)
    vein_tint.location = (-270, 140)
    links.new(vein_ramp.outputs["Color"], vein_tint.inputs["Fac"])
    links.new(earth_ramp.outputs["Color"], vein_tint.inputs["Color1"])
    links.new(vein_tint.outputs["Color"], shader.inputs["Base Color"])

    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.10
    bump.inputs["Distance"].default_value = 0.012
    bump.location = (340, -80)
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])

    fresnel = nodes.new("ShaderNodeFresnel")
    fresnel.name = "ES_DomeRim"
    fresnel.label = "Edge glow control"
    fresnel.inputs["IOR"].default_value = 1.26
    fresnel.location = (-270, -500)

    shell_alpha = nodes.new("ShaderNodeValue")
    shell_alpha.name = "ES_ShellOpacity"
    shell_alpha.label = "Keep actor clearly visible"
    shell_alpha.outputs[0].default_value = 0.025
    shell_alpha.location = (-690, -640)

    rim_alpha = nodes.new("ShaderNodeValue")
    rim_alpha.name = "ES_RimOpacity"
    rim_alpha.label = "Fresnel edge opacity"
    rim_alpha.outputs[0].default_value = 0.12
    rim_alpha.location = (-690, -760)

    vein_alpha = nodes.new("ShaderNodeValue")
    vein_alpha.name = "ES_VeinOpacity"
    vein_alpha.label = "Mineral seam opacity"
    vein_alpha.outputs[0].default_value = 0.035
    vein_alpha.location = (-690, -880)

    front_alpha = nodes.new("ShaderNodeValue")
    front_alpha.name = "ES_FrontOpacity"
    front_alpha.label = "Reveal edge opacity"
    front_alpha.outputs[0].default_value = 0.40
    front_alpha.location = (-690, -1000)

    def multiply(name: str, label: str, left, right, location: tuple[int, int]):
        node = nodes.new("ShaderNodeMath")
        node.operation = "MULTIPLY"
        node.name = name
        node.label = label
        node.location = location
        links.new(left, node.inputs[0])
        links.new(right, node.inputs[1])
        return node.outputs[0]

    def add(name: str, label: str, left, right, location: tuple[int, int]):
        node = nodes.new("ShaderNodeMath")
        node.operation = "ADD"
        node.name = name
        node.label = label
        node.location = location
        links.new(left, node.inputs[0])
        links.new(right, node.inputs[1])
        return node.outputs[0]

    rim_opacity = multiply("ES_RimAlpha", "Rim contribution", fresnel.outputs[0], rim_alpha.outputs[0], (-430, -500))
    vein_opacity = multiply("ES_VeinAlpha", "Seam contribution", vein_ramp.outputs["Color"], vein_alpha.outputs[0], (-430, -720))
    front_opacity = multiply("ES_FrontAlpha", "Reveal-front contribution", front_band.outputs["Result"], front_alpha.outputs[0], (-430, -940))
    alpha_a = add("ES_OpacityAdd_01", "Base + rim", shell_alpha.outputs[0], rim_opacity, (-180, -500))
    alpha_b = add("ES_OpacityAdd_02", "Add seams", alpha_a, vein_opacity, (40, -500))
    alpha_c = add("ES_OpacityAdd_03", "Add reveal edge", alpha_b, front_opacity, (250, -500))
    visible_alpha = multiply("ES_OpacityVisible", "Hide unrevealed shell", alpha_c, visible.outputs[0], (470, -500))
    links.new(visible_alpha, shell_mix.inputs[0])

    front_energy = nodes.new("ShaderNodeValue")
    front_energy.name = "ES_FrontGlowStrength"
    front_energy.label = "White-gold reveal flash"
    front_energy.outputs[0].default_value = 1.35
    front_energy.location = (-270, -1120)
    rim_energy = nodes.new("ShaderNodeValue")
    rim_energy.name = "ES_IdleRimGlow"
    rim_energy.label = "Quiet active-state rim"
    rim_energy.outputs[0].default_value = 0.28
    rim_energy.location = (-270, -1260)
    vein_energy = nodes.new("ShaderNodeValue")
    vein_energy.name = "ES_SeamGlow"
    vein_energy.label = "Very faint mineral glint"
    vein_energy.outputs[0].default_value = 0.10
    vein_energy.location = (-270, -1400)

    glow_front = multiply("ES_GlowFront", "Moving bright edge", front_band.outputs["Result"], front_energy.outputs[0], (0, -1080))
    glow_rim = multiply("ES_GlowRim", "Soft dome rim", fresnel.outputs[0], rim_energy.outputs[0], (0, -1240))
    glow_vein = multiply("ES_GlowVeins", "Mineral glints", vein_ramp.outputs["Color"], vein_energy.outputs[0], (0, -1400))
    glow_a = add("ES_GlowAdd_01", "Front + rim glow", glow_front, glow_rim, (240, -1120))
    glow_b = add("ES_GlowAdd_02", "Add mineral glints", glow_a, glow_vein, (450, -1120))
    visible_glow = multiply("ES_GlowVisible", "Hide glow before reveal", glow_b, visible.outputs[0], (650, -900))

    links.new(visible_glow, shader.inputs["Emission Strength"])
    links.new(shell_mix.outputs[0], output.inputs["Surface"])
    return material


def hash_noise(direction: Vector, seed: int) -> float:
    value = math.sin(
        (direction.x + seed * 0.013) * 127.1
        + (direction.y - seed * 0.017) * 311.7
        + (direction.z + seed * 0.019) * 74.7
    ) * 43758.5453123
    return (value - math.floor(value)) * 2.0 - 1.0


def make_rock_mesh(
    name: str,
    dims: tuple[float, float, float],
    seed: int,
    subdivisions: int = 1,
    ruggedness: float = 0.17,
    smooth: bool = False,
) -> bpy.types.Mesh:
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdivisions, radius=1.0)
    dim_vector = Vector(dims)
    for vertex in bm.verts:
        direction = vertex.co.normalized()
        noise = hash_noise(direction, seed)
        wave = math.sin(direction.x * 8.0 + direction.z * 4.0 + seed) * ruggedness * 0.35
        radius = max(1.0 - ruggedness * 1.4, min(1.0 + ruggedness * 1.4, 1.0 + noise * ruggedness + wave))
        vertex.co = Vector((direction.x * dims[0], direction.y * dims[1], direction.z * dims[2])) * radius
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

    uv_layer = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        loop_values = []
        for loop_index in polygon.loop_indices:
            vertex = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            unit = Vector((vertex.x / dims[0], vertex.y / dims[1], vertex.z / dims[2])).normalized()
            u = 0.5 + math.atan2(unit.y, unit.x) / (2.0 * math.pi)
            v = 0.5 + math.asin(max(-1.0, min(1.0, unit.z))) / math.pi
            loop_values.append((loop_index, u, v))
        if max(value[1] for value in loop_values) - min(value[1] for value in loop_values) > 0.5:
            loop_values = [(loop_index, u + (1.0 if u < 0.5 else 0.0), v) for loop_index, u, v in loop_values]
        for loop_index, u, v in loop_values:
            uv_layer.data[loop_index].uv = (u, v)

    for polygon in mesh.polygons:
        polygon.use_smooth = smooth
    return mesh


def make_actor_sphere(name: str, location: tuple[float, float, float], scale: tuple[float, float, float], collection: bpy.types.Collection, material: bpy.types.Material) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=16, v_segments=8, radius=1.0)
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    bm.to_mesh(mesh)
    bm.free()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.location = location
    obj.scale = scale
    obj.data.materials.append(material)
    obj["role"] = "non-production actor scale guide"
    return obj


def new_empty(name: str, collection: bpy.types.Collection, display_type: str = "PLAIN_AXES") -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = display_type
    obj.empty_display_size = 0.14
    obj["role"] = "editable Earth Shield orbit control"
    return obj


def new_mesh_object(name: str, mesh: bpy.types.Mesh, collection: bpy.types.Collection, material: bpy.types.Material) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    return obj


def make_orbit_guide(name: str, root: bpy.types.Object, radius: float, height: float, phase: float, tilt: tuple[float, float], material: bpy.types.Material, collection: bpy.types.Collection) -> bpy.types.Object:
    curve = bpy.data.curves.new(f"{name}_Curve", type="CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = 0.004
    curve.bevel_resolution = 1
    spline = curve.splines.new("POLY")
    count = 96
    spline.points.add(count - 1)
    rotation = Euler((math.radians(tilt[0]), math.radians(tilt[1]), 0.0), "XYZ").to_quaternion()
    phase_radians = math.radians(phase)
    for index in range(count):
        angle = 2.0 * math.pi * index / (count - 1) + phase_radians
        local_point = rotation @ Vector((radius * math.cos(angle), radius * math.sin(angle), height))
        spline.points[index].co = (local_point.x, local_point.y, local_point.z, 1.0)
    guide = bpy.data.objects.new(name, curve)
    collection.objects.link(guide)
    guide.parent = root
    guide.data.materials.append(material)
    guide.hide_render = True
    guide.hide_select = True
    guide["role"] = "viewport-only orbit path guide"
    return guide


def make_area_light(name: str, location: tuple[float, float, float], target: Vector, energy: float, size: float, collection: bpy.types.Collection) -> bpy.types.Object:
    data = bpy.data.lights.new(name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new(name, data)
    collection.objects.link(light)
    light.location = location
    light.rotation_euler = (target - light.location).to_track_quat("-Z", "Y").to_euler()
    return light


def build_scene() -> dict[str, object]:
    clear_scene()
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.resolution_percentage = 100
    scene.render.fps = 24
    scene.render.film_transparent = False
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = "//"
    scene.render.use_file_extension = True
    scene.frame_start = 1
    scene.frame_end = ORBIT_PERIOD_FRAMES
    scene.frame_set(1)
    scene.view_settings.view_transform = "AgX"
    scene.unit_settings.system = "METRIC"

    actor_collection = new_collection("00_Actor_Guide")
    actor_collection.hide_render = True
    hero_collection = new_collection("10_Hero_Orbit_Rocks")
    debris_collection = new_collection("20_Orbit_Chips")
    guide_collection = new_collection("80_Orbit_Guides")
    rig_collection = new_collection("85_Orbit_Rig")
    lookdev_collection = new_collection("90_Lookdev")

    actor_material = bpy.data.materials.new("M_ES_ActorGuide")
    actor_material.diffuse_color = (0.055, 0.085, 0.065, 1.0)
    actor_material.use_nodes = True
    actor_shader = actor_material.node_tree.nodes.get("Principled BSDF")
    actor_shader.inputs["Base Color"].default_value = (0.055, 0.085, 0.065, 1.0)
    actor_shader.inputs["Roughness"].default_value = 0.92
    for name, location, scale in (
        ("ActorGuide_Torso", (0.0, 0.0, 0.98), (0.235, 0.19, 0.48)),
        ("ActorGuide_Head", (0.0, 0.0, 1.62), (0.16, 0.16, 0.19)),
        ("ActorGuide_Arms", (0.0, 0.0, 1.26), (0.52, 0.105, 0.11)),
        ("ActorGuide_Leg_L", (-0.125, 0.0, 0.35), (0.115, 0.135, 0.34)),
        ("ActorGuide_Leg_R", (0.125, 0.0, 0.35), (0.115, 0.135, 0.34)),
    ):
        make_actor_sphere(name, location, scale, actor_collection, actor_material)

    root = new_empty("ES_Shield_OrbitRoot", rig_collection, "SPHERE")
    root.location = (0.0, 0.0, 1.02)
    root["role"] = "center of the Earth Shield orbital volume"

    materials = {name: rock_material(name, name) for name in TEXTURE_SETS}
    dome_material = dome_shell_material()
    guide_material = bpy.data.materials.new("M_ES_OrbitGuide")
    guide_material.diffuse_color = (0.34, 0.24, 0.12, 1.0)
    guide_material.use_nodes = True
    guide_material.node_tree.nodes.get("Principled BSDF").inputs["Base Color"].default_value = (0.34, 0.24, 0.12, 1.0)

    hero_objects: list[bpy.types.Object] = []
    chip_count = 0
    for data in HERO_ROCKS:
        rock_id = data["id"]
        texture_set = data["name"]
        radius = float(data["radius"])
        height = float(data["height"])
        phase = float(data["phase"])
        tilt = data["tilt"]
        seed = int(data["seed"])

        plane = new_empty(f"ES_OrbitPlane_{rock_id}", rig_collection)
        plane.parent = root
        plane.location = (0.0, 0.0, 0.0)
        plane.rotation_euler = (math.radians(tilt[0]), math.radians(tilt[1]), 0.0)
        plane["orbit_radius"] = radius
        plane["orbit_tilt_degrees"] = [float(tilt[0]), float(tilt[1])]

        spin = new_empty(f"ES_OrbitSpin_{rock_id}", rig_collection)
        spin.parent = plane
        spin.location = (0.0, 0.0, 0.0)
        radians_per_frame = math.tau / ORBIT_PERIOD_FRAMES
        spin["orbit_period_frames"] = ORBIT_PERIOD_FRAMES
        spin["orbit_radians_per_frame"] = radians_per_frame
        rotation_curve = spin.driver_add("rotation_euler", 2)
        rotation_driver = rotation_curve.driver
        rotation_driver.type = "SCRIPTED"
        rotation_driver.expression = f"{radians_per_frame:.17g} * (frame - 1.0)"

        mesh_name = f"ES_Rock_{rock_id}_{texture_set}_Mesh"
        mesh = make_rock_mesh(mesh_name, data["dims"], seed, subdivisions=3, ruggedness=0.085, smooth=True)
        rock = new_mesh_object(f"ES_Rock_{rock_id}_{texture_set}", mesh, hero_collection, materials[texture_set])
        rock.parent = spin
        phase_radians = math.radians(phase)
        rock.location = (radius * math.cos(phase_radians), radius * math.sin(phase_radians), height)
        rock.rotation_euler = (
            math.radians((seed % 43) - 21),
            math.radians((seed % 59) - 29),
            math.radians((seed % 97) - 48),
        )
        rock["role"] = "independent orbiting hero stone"
        rock["texture_set"] = texture_set
        rock["orbit_radius"] = radius
        rock["orbit_phase_degrees"] = phase
        rock["orbit_plane"] = plane.name
        rock["orbit_controller"] = spin.name
        hero_objects.append(rock)

        make_orbit_guide(
            f"Guide_Orbit_{rock_id}_{texture_set}", root, radius, height, phase, tilt,
            guide_material, guide_collection,
        )

        rng = random.Random(seed * 13)
        chip_offsets = (
            Vector((0.00, -0.32, 0.07)),
            Vector((-0.13, -0.38, -0.08)),
        )
        for chip_index, offset in enumerate(chip_offsets, start=1):
            chip_count += 1
            jitter = Vector((rng.uniform(-0.045, 0.045), rng.uniform(-0.035, 0.035), rng.uniform(-0.04, 0.04)))
            chip_scale = rng.uniform(0.052, 0.075)
            chip_dims = (chip_scale * rng.uniform(0.75, 1.25), chip_scale * rng.uniform(0.65, 1.1), chip_scale * rng.uniform(0.7, 1.3))
            chip_mesh = make_rock_mesh(
                f"ES_Chip_{rock_id}_{chip_index:02d}_Mesh", chip_dims, seed + chip_index * 71,
                subdivisions=1, ruggedness=0.19, smooth=False,
            )
            chip = new_mesh_object(
                f"ES_Chip_{rock_id}_{chip_index:02d}_{texture_set}", chip_mesh, debris_collection, materials[texture_set],
            )
            chip.parent = rock
            chip.location = offset + jitter
            chip.rotation_euler = tuple(rng.uniform(-math.pi, math.pi) for _ in range(3))
            chip["role"] = "small trailing orbit fragment"
            chip["parent_hero"] = rock.name
            chip["texture_set"] = texture_set

    world = bpy.data.worlds.new("EarthShield_Lookdev_World")
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs["Color"].default_value = (0.018, 0.025, 0.035, 1.0)
    world.node_tree.nodes.get("Background").inputs["Strength"].default_value = 0.28
    scene.world = world

    target = Vector((0.0, 0.0, 1.02))
    make_area_light("Lookdev_Key", (-3.8, -4.8, 5.4), target, 850.0, 4.0, lookdev_collection)
    make_area_light("Lookdev_Fill", (4.5, -1.8, 2.8), target, 480.0, 3.5, lookdev_collection)
    make_area_light("Lookdev_Rim", (0.4, 3.8, 4.2), target, 1050.0, 2.6, lookdev_collection)

    camera_data = bpy.data.cameras.new("EarthShield_Orbit_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 4.8
    camera = bpy.data.objects.new("EarthShield_Orbit_Camera", camera_data)
    lookdev_collection.objects.link(camera)
    camera.location = (4.5, -8.2, 3.35)
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera

    for image in bpy.data.images:
        if image.source == "FILE" and Path(bpy.path.abspath(image.filepath)).is_relative_to(TEXTURE_DIR):
            image.filepath = f"//textures/{Path(image.filepath).name}"

    bpy.context.view_layer.objects.active = hero_objects[0]
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    hero_objects[0].select_set(True)

    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND_PATH))
    scene.frame_set(1)

    return {
        "status": "built",
        "blend": str(BLEND_PATH),
        "scene": scene.name,
        "hero_rocks": len(hero_objects),
        "orbit_chips": chip_count,
        "orbit_controllers": len(HERO_ROCKS) * 2,
        "orbit_period_frames": ORBIT_PERIOD_FRAMES,
        "actor_guide_rendered": False,
        "texture_sets": sorted(TEXTURE_SETS),
        "dome_material": dome_material.name,
        "dome_mesh_created": False,
        "objects": len(scene.objects),
    }


result = build_scene()
