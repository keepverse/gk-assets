"""Build the reusable ice-shield object kit and its sparse idle VFX scene.

Run with:
    blender --background --factory-startup --python blender/tools/shield_ice_build.py
    blender --background --factory-startup --python blender/tools/shield_ice_build.py -- --variant v2

Each source .blend contains exactly one mesh object. The idle scene links those
collections, instances each once, and renders isolated sprite layers, packed
128px sheets, and a composite preview. The v2 variant is built beside the
baseline so both looks remain available for review.
"""

from __future__ import annotations

import math
import argparse
import sys
from array import array
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "blender" / "assets" / "vfx" / "ice_shield"
EFFECT_DIR = ROOT / "blender" / "vfx" / "shield_ice_idle"
V2_ASSET_DIR = ASSET_DIR / "v2"
V2_EFFECT_DIR = EFFECT_DIR / "v2"
FRAME_COUNT = 24
FPS = 24
RENDER_SIZE = 512
SPRITE_SIZE = 128
SPRITE_COLUMNS = 6


def fresh_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0


def surface_material(
    name: str,
    color: tuple[float, float, float],
    opacity: float,
    fracture_gain: float = 1.0,
    fracture_image: bpy.types.Image | None = None,
) -> bpy.types.Material:
    """Create a frosted-glass master with separate broad and hairline fractures."""
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, opacity)
    nodes = mat.node_tree.nodes
    nodes.clear()
    links = mat.node_tree.links

    coordinates = nodes.new("ShaderNodeTexCoord")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 5.2
    noise.inputs["Roughness"].default_value = 0.76
    links.new(coordinates.outputs["Generated"], noise.inputs["Vector"])

    color_ramp = nodes.new("ShaderNodeValToRGB")
    low_stop, high_stop = color_ramp.color_ramp.elements
    middle_stop = color_ramp.color_ramp.elements.new(0.52)
    low_stop.position = 0.16
    low_stop.color = (*tuple(max(0.0, component * 0.24) for component in color), 1.0)
    middle_stop.color = (*tuple(min(1.0, component * 0.72 + 0.008) for component in color), 1.0)
    high_stop.position = 0.86
    high_stop.color = (*tuple(min(1.0, component * 1.18 + 0.015) for component in color), 1.0)
    links.new(noise.outputs["Fac"], color_ramp.inputs["Fac"])

    # A restrained warp keeps the facets irregular without turning their edges
    # into a dense, soft spiderweb.
    warp_noise = nodes.new("ShaderNodeTexNoise")
    warp_noise.inputs["Scale"].default_value = 3.6
    warp_noise.inputs["Detail"].default_value = 3.0
    warp_noise.inputs["Roughness"].default_value = 0.72
    links.new(coordinates.outputs["Generated"], warp_noise.inputs["Vector"])
    center_warp = nodes.new("ShaderNodeVectorMath")
    center_warp.operation = "SUBTRACT"
    center_warp.inputs[1].default_value = (0.5, 0.5, 0.5)
    links.new(warp_noise.outputs["Color"], center_warp.inputs[0])
    scale_warp = nodes.new("ShaderNodeVectorMath")
    scale_warp.operation = "SCALE"
    scale_warp.inputs[3].default_value = 0.035
    links.new(center_warp.outputs[0], scale_warp.inputs[0])
    warped_coordinates = nodes.new("ShaderNodeVectorMath")
    warped_coordinates.operation = "ADD"
    links.new(coordinates.outputs["Generated"], warped_coordinates.inputs[0])
    links.new(scale_warp.outputs[0], warped_coordinates.inputs[1])

    fracture_masks = []
    for label, scale, near_edge, fade_edge in (
        ("Sparse", 4.4, 0.0010, 0.0070),
    ):
        cells = nodes.new("ShaderNodeTexVoronoi")
        cells.label = f"{label} Ice Fracture Cells"
        cells.feature = "DISTANCE_TO_EDGE"
        cells.inputs["Scale"].default_value = scale
        links.new(warped_coordinates.outputs[0], cells.inputs["Vector"])
        mask = nodes.new("ShaderNodeValToRGB")
        mask.label = f"{label} Fracture Line Width"
        mask.color_ramp.elements[0].position = near_edge
        mask.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
        mask.color_ramp.elements[1].position = fade_edge
        mask.color_ramp.elements[1].color = (0.0, 0.0, 0.0, 1.0)
        links.new(cells.outputs["Distance"], mask.inputs["Fac"])
        fracture_masks.append(mask)

    image_texture = None
    fracture_source = fracture_masks[0].outputs["Color"]
    if fracture_image is not None:
        image_texture = nodes.new("ShaderNodeTexImage")
        image_texture.label = "Frost vein color detail (subtle albedo only)"
        image_texture.image = fracture_image
        image_texture.interpolation = "Linear"
        links.new(coordinates.outputs["UV"], image_texture.inputs["Vector"])
        # The authored map contains broad opaque ice plates as well as veins;
        # its alpha is not a line-only fracture mask. Keep fracture density in
        # the procedural cell field and use the image only for subtle color.

    fracture = nodes.new("ShaderNodeMath")
    fracture.operation = "MULTIPLY"
    fracture.inputs[1].default_value = fracture_gain
    links.new(fracture_source, fracture.inputs[0])

    layer_weight = nodes.new("ShaderNodeLayerWeight")
    fresnel_ramp = nodes.new("ShaderNodeValToRGB")
    fresnel_ramp.color_ramp.elements[0].position = 0.04
    fresnel_ramp.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)
    fresnel_ramp.color_ramp.elements[1].position = 0.52
    fresnel_ramp.color_ramp.elements[1].color = (1.0, 1.0, 1.0, 1.0)
    links.new(layer_weight.outputs["Fresnel"], fresnel_ramp.inputs["Fac"])

    edge_color = (
        min(1.0, color[0] * 0.25 + 0.08),
        min(1.0, color[1] * 0.45 + 0.42),
        min(1.0, color[2] * 0.45 + 0.55),
    )
    frost_color = nodes.new("ShaderNodeMixRGB")
    frost_color.label = "Frost glints in fracture channels"
    links.new(fracture.outputs[0], frost_color.inputs[0])
    links.new(color_ramp.outputs["Color"], frost_color.inputs[1])
    frost_color.inputs[2].default_value = (*edge_color, 1.0)
    surface_color = frost_color.outputs["Color"]
    if image_texture is not None:
        texture_mix = nodes.new("ShaderNodeMixRGB")
        texture_mix.label = "Subtle cold-blue vein modulation (no white plate overlay)"
        texture_mix.blend_type = "MULTIPLY"
        texture_mix.inputs[0].default_value = 0.20
        links.new(frost_color.outputs["Color"], texture_mix.inputs[1])
        links.new(image_texture.outputs["Color"], texture_mix.inputs[2])
        surface_color = texture_mix.outputs["Color"]

    crack_emission = nodes.new("ShaderNodeMath")
    crack_emission.operation = "MULTIPLY"
    crack_emission.inputs[1].default_value = 0.88
    links.new(fracture.outputs[0], crack_emission.inputs[0])
    edge_emission = nodes.new("ShaderNodeMath")
    edge_emission.operation = "MULTIPLY"
    edge_emission.inputs[1].default_value = 0.28
    links.new(fresnel_ramp.outputs["Color"], edge_emission.inputs[0])
    edge_and_crack = nodes.new("ShaderNodeMath")
    edge_and_crack.operation = "MAXIMUM"
    links.new(edge_emission.outputs[0], edge_and_crack.inputs[0])
    links.new(crack_emission.outputs[0], edge_and_crack.inputs[1])

    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Roughness"].default_value = 0.18
    principled.inputs["Metallic"].default_value = 0.025
    principled.inputs["IOR"].default_value = 1.31
    principled.inputs["Transmission Weight"].default_value = 0.12
    principled.inputs["Coat Weight"].default_value = 0.38
    principled.inputs["Coat Roughness"].default_value = 0.08
    principled.inputs["Specular IOR Level"].default_value = 0.62
    links.new(surface_color, principled.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.024
    links.new(fracture.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], principled.inputs["Normal"])

    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*edge_color, 1.0)
    emission.inputs["Strength"].default_value = 3.0 if "Rim" in name else 2.7 if "Crystal" in name else 2.2
    edge_mix = nodes.new("ShaderNodeMixShader")
    links.new(edge_and_crack.outputs[0], edge_mix.inputs[0])
    links.new(principled.outputs["BSDF"], edge_mix.inputs[1])
    links.new(emission.outputs["Emission"], edge_mix.inputs[2])

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    alpha_mix = nodes.new("ShaderNodeMixShader")
    alpha_mix.inputs[0].default_value = opacity
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(transparent.outputs[0], alpha_mix.inputs[1])
    links.new(edge_mix.outputs[0], alpha_mix.inputs[2])
    links.new(alpha_mix.outputs[0], output.inputs["Surface"])
    if hasattr(mat, "surface_render_method"):
        try:
            mat.surface_render_method = "BLENDED"
        except (TypeError, ValueError):
            pass
    elif hasattr(mat, "blend_method"):
        mat.blend_method = "BLEND"
    mat.use_backface_culling = False
    return mat


def mesh_object(
    name: str,
    collection: bpy.types.Collection,
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[bpy.types.Material],
    material_indices: list[int],
    usage: str,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    for mat in materials:
        mesh.materials.append(mat)
    for polygon, index in zip(mesh.polygons, material_indices):
        polygon.material_index = index
        polygon.use_smooth = False
    obj["asset_kind"] = name
    obj["usage"] = usage
    return obj


def asset_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(f"COL_{name}")
    bpy.context.scene.collection.children.link(collection)
    return collection


def save_single_object_asset(filename: str, build_object, asset_dir: Path) -> None:
    fresh_scene()
    collection = asset_collection(filename.removesuffix(".blend").upper() + "_ASSET")
    obj = build_object(collection)
    if len(bpy.data.objects) != 1 or obj.type != "MESH":
        raise RuntimeError(f"{filename} must contain exactly one mesh object")
    if hasattr(obj, "asset_mark"):
        try:
            obj.asset_mark()
        except RuntimeError:
            pass
    out_path = asset_dir / filename
    bpy.ops.wm.save_as_mainfile(filepath=str(out_path))
    print(f"[asset] {out_path.relative_to(ROOT)}: {obj.name}, {len(obj.data.polygons)} faces")


def dome_point(v: float, phi: float) -> Vector:
    # Open-bottom elliptical shell; the middle stays transparent for the actor.
    radius = math.cos(v)
    return Vector((0.68 * radius * math.cos(phi), 0.38 * radius * math.sin(phi), 0.05 + 1.34 * math.sin(v)))


def build_shell(
    collection: bpy.types.Collection,
    fracture_texture_path: Path | None = None,
) -> bpy.types.Object:
    fracture_image = None
    if fracture_texture_path is not None:
        if not fracture_texture_path.is_file():
            raise FileNotFoundError(fracture_texture_path)
        fracture_image = bpy.data.images.load(str(fracture_texture_path), check_existing=False)
        fracture_image.pack()
    palette = [
        surface_material("MAT_Ice_Shell_CyanGlass", (0.02, 0.15, 0.50), 0.48, fracture_image=fracture_image),
        surface_material("MAT_Ice_Shell_DeepGlacier", (0.008, 0.025, 0.12), 0.40, fracture_image=fracture_image),
        surface_material("MAT_Ice_Shell_FrostFacet", (0.06, 0.30, 0.65), 0.54, fracture_image=fracture_image),
        surface_material("MAT_Ice_Shell_BlueGlass", (0.02, 0.10, 0.31), 0.44, fracture_image=fracture_image),
    ]
    vertices: list[tuple[float, float, float]] = []
    uv_coordinates: list[tuple[float, float]] = []
    faces: list[tuple[int, ...]] = []
    face_materials: list[int] = []
    azimuth_steps, height_steps = 16, 4
    top = math.pi / 2.0 - 0.18
    for row in range(height_steps):
        v0 = top * row / height_steps
        v1 = top * (row + 1) / height_steps
        sector_width = math.tau / azimuth_steps
        lower_shift = (row % 2) * 0.5
        upper_shift = ((row + 1) % 2) * 0.5
        for segment in range(azimuth_steps):
            # Small intentional openings keep the surface crystalline, not a solid ball.
            if (segment + row * 5) % 53 == 0:
                continue
            base_phi = -math.pi / 2.0 - math.pi / azimuth_steps
            phi0_lower = base_phi + (segment + lower_shift) * sector_width
            phi1_lower = phi0_lower + sector_width
            phi0_upper = base_phi + (segment + upper_shift) * sector_width
            phi1_upper = phi0_upper + sector_width
            center_phi = (phi0_lower + phi1_lower + phi0_upper + phi1_upper) / 4.0
            front_gap = abs((center_phi + math.pi / 2.0 + math.pi) % math.tau - math.pi)
            rear_gap = abs((center_phi - math.pi / 2.0 + math.pi) % math.tau - math.pi)
            actor_window = min(front_gap, rear_gap)
            if row < 2 and actor_window < 0.82:
                continue
            corners = [
                dome_point(v0, phi0_lower), dome_point(v0, phi1_lower),
                dome_point(v1, phi1_upper), dome_point(v1, phi0_upper),
            ]
            center = sum(corners, Vector()) / 4.0
            corners = [center + (point - center) * 0.999 for point in corners]
            u0_lower = (segment + lower_shift) / azimuth_steps
            u1_lower = u0_lower + 1.0 / azimuth_steps
            u0_upper = (segment + upper_shift) / azimuth_steps
            u1_upper = u0_upper + 1.0 / azimuth_steps
            t0, t1 = row / height_steps, (row + 1) / height_steps
            uv_coordinates.extend(((u0_lower, t0), (u1_lower, t0), (u1_upper, t1), (u0_upper, t1)))
            start = len(vertices)
            vertices.extend(tuple(point) for point in corners)
            faces.extend(((start, start + 1, start + 2), (start, start + 2, start + 3)))
            facet = (segment + row * 2) % len(palette)
            face_materials.extend((facet, (facet + 2) % len(palette)))
    obj = mesh_object(
        "ICE_SHIELD_SHELL", collection, vertices, faces, palette, face_materials,
        "Translucent frost-glass canopy with a connected crown and an open lower-front actor window.",
    )
    if fracture_texture_path is not None:
        obj["fracture_texture_source"] = fracture_texture_path.name
    thickness = obj.modifiers.new("MOD_IceShell_ThinFacetEdges", "SOLIDIFY")
    thickness.thickness = 0.008
    thickness.offset = 0.0
    thickness.use_rim = True
    uv_layer = obj.data.uv_layers.new(name="UV_IceShield_FrostVeins")
    for loop in obj.data.loops:
        uv_layer.data[loop.index].uv = uv_coordinates[loop.vertex_index]
    return obj


def append_tube(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    path: list[Vector],
    radius: float,
    sides: int,
) -> None:
    base = len(vertices)
    for i, point in enumerate(path):
        before = path[max(0, i - 1)]
        after = path[min(len(path) - 1, i + 1)]
        tangent = (after - before).normalized()
        side = tangent.cross(Vector((0.0, 1.0, 0.0)))
        if side.length < 1e-6:
            side = tangent.cross(Vector((1.0, 0.0, 0.0)))
        side.normalize()
        normal = tangent.cross(side).normalized()
        for j in range(sides):
            a = math.tau * j / sides
            offset = radius * (math.cos(a) * side + math.sin(a) * normal)
            vertices.append(tuple(point + offset))
    for i in range(len(path) - 1):
        for j in range(sides):
            a = base + i * sides + j
            b = base + i * sides + (j + 1) % sides
            c = base + (i + 1) * sides + (j + 1) % sides
            d = base + (i + 1) * sides + j
            faces.append((a, b, c, d))


def build_rim(collection: bpy.types.Collection) -> bpy.types.Object:
    materials = [
        surface_material("MAT_Ice_Rim_CyanEdge", (0.20, 0.62, 0.88), 0.96, fracture_gain=0.08),
        surface_material("MAT_Ice_Rim_DeepEdge", (0.08, 0.28, 0.56), 0.82, fracture_gain=0.08),
    ]
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    face_materials: list[int] = []
    sample_count, sides = 48, 7
    for material_index, depth_sign in enumerate((-1.0, 1.0)):
        path = []
        for i in range(sample_count + 1):
            t = math.pi * i / sample_count
            path.append(Vector((0.70 * math.cos(t), depth_sign * 0.38 * math.sin(t), 0.05 + 1.34 * math.sin(t))))
        before = len(faces)
        append_tube(vertices, faces, path, 0.015 if material_index == 0 else 0.009, sides)
        face_materials.extend([material_index] * (len(faces) - before))
    return mesh_object(
        "ICE_SHIELD_RIM", collection, vertices, faces, materials, face_materials,
        "One continuous two-sided arch edge that outlines the shell without a bead swarm.",
    )


def build_shard(collection: bpy.types.Collection) -> bpy.types.Object:
    palette = [
        surface_material("MAT_Ice_Crystal_BlueGlass", (0.10, 0.34, 0.68), 0.88, fracture_gain=0.22),
        surface_material("MAT_Ice_Crystal_CyanFacet", (0.26, 0.64, 0.82), 0.96, fracture_gain=0.22),
        surface_material("MAT_Ice_Crystal_FrostFacet", (0.56, 0.80, 0.92), 0.90, fracture_gain=0.22),
        surface_material("MAT_Ice_Crystal_ShadowFacet", (0.07, 0.20, 0.42), 0.84, fracture_gain=0.22),
    ]
    sides = 6
    levels = [(-0.25, 0.0, 0.0), (-0.09, 0.10, 0.055), (0.04, 0.16, 0.082), (0.15, 0.08, 0.042), (0.34, 0.0, 0.0)]
    vertices: list[tuple[float, float, float]] = [(0.0, 0.0, levels[0][0])]
    rings: list[list[int]] = []
    for level, (z, rx, ry) in enumerate(levels[1:-1], start=1):
        ring = []
        for side in range(sides):
            angle = math.tau * side / sides + level * 0.11
            x_shift = 0.018 * math.sin(level * 1.7)
            y_shift = 0.012 * math.cos(level * 1.3)
            ring.append(len(vertices))
            vertices.append((x_shift + rx * math.cos(angle), y_shift + ry * math.sin(angle), z))
        rings.append(ring)
    top_index = len(vertices)
    vertices.append((0.012, -0.006, levels[-1][0]))
    faces: list[tuple[int, ...]] = []
    face_materials: list[int] = []
    for side in range(sides):
        faces.append((0, rings[0][(side + 1) % sides], rings[0][side]))
        face_materials.append((side + 1) % len(palette))
    for row in range(len(rings) - 1):
        for side in range(sides):
            a = rings[row][side]
            b = rings[row][(side + 1) % sides]
            c = rings[row + 1][(side + 1) % sides]
            d = rings[row + 1][side]
            faces.extend(((a, b, c), (a, c, d)))
            face_materials.extend(((side + row) % len(palette), (side + row + 2) % len(palette)))
    for side in range(sides):
        faces.append((rings[-1][side], rings[-1][(side + 1) % sides], top_index))
        face_materials.append((side + 2) % len(palette))
    return mesh_object(
        "ICE_CRYSTAL_SHARD", collection, vertices, faces, palette, face_materials,
        "Single elongated faceted crown shard. Instance sparingly; one crown is enough for the idle shield.",
    )


def child_collection(name: str, parent: bpy.types.Collection) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def aim_at(obj: bpy.types.Object, target: Vector) -> None:
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def create_area_light(
    name: str,
    collection: bpy.types.Collection,
    location: tuple[float, float, float],
    target: Vector,
    color: tuple[float, float, float],
    energy: float,
    size: float,
) -> bpy.types.Object:
    light_data = bpy.data.lights.new(name, type="AREA")
    light_data.energy = energy
    light_data.color = color
    light_data.shape = "DISK"
    light_data.size = size
    light = bpy.data.objects.new(name, light_data)
    collection.objects.link(light)
    light.location = location
    aim_at(light, target)
    return light


def configure_compositor(scene: bpy.types.Scene) -> None:
    tree = bpy.data.node_groups.new("NT_IceShield_GlowComp", "CompositorNodeTree")
    scene.compositing_node_group = tree
    scene.use_nodes = True
    tree.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")

    nodes = tree.nodes
    nodes.clear()
    links = tree.links
    render_layers = nodes.new("CompositorNodeRLayers")
    render_layers.scene = scene
    render_layers.location = (-320, 40)
    glare = nodes.new("CompositorNodeGlare")
    glare.location = (-40, 40)
    glare.inputs["Type"].default_value = "Fog Glow"
    glare.inputs["Quality"].default_value = "High"
    glare.inputs["Threshold"].default_value = 0.65
    glare.inputs["Strength"].default_value = 0.32
    glare.inputs["Size"].default_value = 0.24
    output = nodes.new("NodeGroupOutput")
    output.location = (240, 40)
    links.new(render_layers.outputs["Image"], glare.inputs["Image"])
    links.new(glare.outputs["Image"], output.inputs["Image"])


def configure_render() -> dict[str, bpy.types.Collection]:
    scene = bpy.context.scene
    scene.name = "SCN_IceShield_Idle"
    scene["purpose"] = "Editable idle ice shield source scene and transparent sprite renderer."
    scene.render.engine = "BLENDER_EEVEE"
    if hasattr(scene, "eevee") and hasattr(scene.eevee, "taa_render_samples"):
        scene.eevee.taa_render_samples = 32
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    scene.view_settings.view_transform = "Standard"
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FRAME_COUNT
    if scene.world is None:
        scene.world = bpy.data.worlds.new("WORLD_IceShield_Night")
    scene.world.name = "WORLD_IceShield_Night"
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.007, 0.022, 0.055, 1.0)
    background.inputs["Strength"].default_value = 0.14

    fx_root = child_collection("COL_FX_IceShield", scene.collection)
    groups = {
        "shell": child_collection("COL_FX_Shell", fx_root),
        "rim": child_collection("COL_FX_Rim", fx_root),
        "crystal": child_collection("COL_FX_Crown", fx_root),
        "lights": child_collection("COL_Lights", scene.collection),
        "cameras": child_collection("COL_Cameras", scene.collection),
    }

    camera_data = bpy.data.cameras.new("CAM_IceShield_Hero_Data")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = 2.06
    camera = bpy.data.objects.new("CAM_IceShield_Hero", camera_data)
    groups["cameras"].objects.link(camera)
    target = Vector((0.0, 0.0, 0.72))
    target_obj = bpy.data.objects.new("EMPTY_CamTarget_IceShield", None)
    groups["cameras"].objects.link(target_obj)
    target_obj.location = target
    target_obj.empty_display_type = "SPHERE"
    target_obj.empty_display_size = 0.04
    target_obj.hide_render = True
    camera.location = (0.0, -5.2, 1.64)
    aim_at(camera, target)
    scene.camera = camera

    create_area_light("LGT_Key_Cool", groups["lights"], (-2.6, -2.9, 3.1), target, (0.57, 0.84, 1.0), 125.0, 2.0)
    create_area_light("LGT_Fill_Cyan", groups["lights"], (2.2, -2.2, 1.05), target, (0.24, 0.58, 0.92), 30.0, 2.5)
    create_area_light("LGT_Rim_Back", groups["lights"], (0.0, 1.4, 2.35), target, (0.52, 0.91, 1.0), 180.0, 1.5)
    configure_compositor(scene)
    return groups


def link_asset_collection(asset_path: Path, collection_name: str) -> bpy.types.Collection:
    relative_path = bpy.path.relpath(str(asset_path))
    with bpy.data.libraries.load(relative_path, link=True) as (data_from, data_to):
        if collection_name not in data_from.collections:
            raise RuntimeError(f"{collection_name} missing from {asset_path}")
        data_to.collections = [collection_name]
    collection = data_to.collections[0]
    if collection is None or collection.library is None:
        raise RuntimeError(f"failed to link {collection_name} from {asset_path}")
    return collection


def instance_asset(
    name: str,
    collection: bpy.types.Collection,
    parent: bpy.types.Collection,
    location: tuple[float, float, float],
) -> bpy.types.Object:
    obj = bpy.data.objects.new(name, None)
    obj.instance_type = "COLLECTION"
    obj.instance_collection = collection
    obj.location = location
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.08
    obj["source_asset"] = Path(collection.library.filepath).name
    parent.objects.link(obj)
    return obj


def animate_idle(roots: dict[str, bpy.types.Object]) -> None:
    scene = bpy.context.scene
    for frame in range(1, FRAME_COUNT + 1):
        t = (frame - 1) / (FRAME_COUNT - 1)
        phase = math.tau * t
        breathe = math.sin(phase)
        scene.frame_set(frame)
        shell = roots["shell"]
        shell.scale = (1.0 + 0.008 * breathe, 1.0 + 0.006 * breathe, 1.0 + 0.010 * breathe)
        shell.keyframe_insert(data_path="scale", frame=frame)
        rim = roots["rim"]
        rim.scale = (1.0 + 0.010 * math.sin(phase + 0.6), 1.0, 1.0 + 0.006 * math.sin(phase + 0.6))
        rim.keyframe_insert(data_path="scale", frame=frame)
        shard = roots["crystal"]
        shard.rotation_euler[1] = 0.045 * math.sin(phase)
        shard.rotation_euler[2] = 0.05 * math.sin(phase + 0.5)
        pulse = 1.0 + 0.025 * breathe
        shard.scale = (1.02 * pulse, 0.70 * pulse, 0.84 * pulse)
        shard.keyframe_insert(data_path="rotation_euler", frame=frame)
        shard.keyframe_insert(data_path="scale", frame=frame)


def render_frame(scene: bpy.types.Scene, path: Path) -> None:
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def build_idle_scene(asset_dir: Path, effect_dir: Path) -> None:
    fresh_scene()
    out_blend = effect_dir / "shield_ice_idle.blend"
    lookdev_blend = effect_dir / "shield_ice_lookdev.blend"
    groups = configure_render()
    # Save once so Blender can resolve all collection links relative to this scene.
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    roots = {
        "shell": instance_asset(
            "ICE_Idle_Shell", link_asset_collection(asset_dir / "ice_shield_shell.blend", "COL_ICE_SHIELD_SHELL_ASSET"), groups["shell"], (0.0, 0.0, 0.0)),
        "rim": instance_asset(
            "ICE_Idle_Rim", link_asset_collection(asset_dir / "ice_shield_rim.blend", "COL_ICE_SHIELD_RIM_ASSET"), groups["rim"], (0.0, 0.0, 0.0)),
        "crystal": instance_asset(
            "ICE_Idle_CrownShard", link_asset_collection(asset_dir / "ice_crystal_shard.blend", "COL_ICE_CRYSTAL_SHARD_ASSET"), groups["crystal"], (0.0, -0.40, 1.39)),
    }
    animate_idle(roots)

    sequence_root = effect_dir / "sequences"
    preview_root = effect_dir / "preview"
    sheet_root = effect_dir / "sheets"
    sheet_root.mkdir(parents=True, exist_ok=True)
    for key, root in roots.items():
        (sequence_root / key).mkdir(parents=True, exist_ok=True)
        for frame in range(1, FRAME_COUNT + 1):
            bpy.context.scene.frame_set(frame)
            for other in roots.values():
                other.hide_render = other != root
            render_frame(bpy.context.scene, sequence_root / key / f"{frame:04d}.png")
        root.hide_render = False
        pack_sprite_sheet(sequence_root / key, sheet_root / f"{key}.png")

    preview_root.mkdir(parents=True, exist_ok=True)
    for frame in range(1, FRAME_COUNT + 1):
        bpy.context.scene.frame_set(frame)
        for root in roots.values():
            root.hide_render = False
        render_frame(bpy.context.scene, preview_root / f"{frame:04d}.png")

    bpy.context.scene.frame_set(1)
    for root in roots.values():
        root.hide_render = False
    for library in bpy.data.libraries:
        library.filepath = bpy.path.relpath(library.filepath)
    linked_paths = [lib.filepath for lib in bpy.data.libraries]
    if len(linked_paths) != 3 or not all(path.startswith("//") for path in linked_paths):
        raise RuntimeError(f"asset libraries are not all relative: {linked_paths}")

    scene = bpy.context.scene
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.film_transparent = True
    scene["render_mode"] = "transparent sprite source"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    lookdev_root = effect_dir / "lookdev"
    lookdev_root.mkdir(parents=True, exist_ok=True)
    scene.name = "SCN_IceShield_Lookdev"
    scene["render_mode"] = "opaque dark-world look-dev preview"
    scene.render.resolution_x = RENDER_SIZE * 2
    scene.render.resolution_y = RENDER_SIZE * 2
    scene.render.film_transparent = False
    scene.frame_set(FRAME_COUNT // 2)
    render_frame(scene, lookdev_root / "ice_shield_lookdev.png")
    bpy.ops.wm.save_as_mainfile(filepath=str(lookdev_blend))
    print(f"[vfx] {out_blend}; linked assets={linked_paths}")
    print(f"[lookdev] {lookdev_blend.relative_to(ROOT)}; render={ (lookdev_root / 'ice_shield_lookdev.png').relative_to(ROOT) }")


def pack_sprite_sheet(sequence_dir: Path, out_path: Path) -> None:
    frames = sorted(sequence_dir.glob("*.png"))
    if len(frames) != FRAME_COUNT:
        raise RuntimeError(f"{sequence_dir} has {len(frames)} frames; expected {FRAME_COUNT}")
    rows = math.ceil(len(frames) / SPRITE_COLUMNS)
    sheet_width = SPRITE_COLUMNS * SPRITE_SIZE
    sheet_height = rows * SPRITE_SIZE
    sheet_pixels = array("f", [0.0]) * (sheet_width * sheet_height * 4)
    for index, frame_path in enumerate(frames):
        source = bpy.data.images.load(str(frame_path), check_existing=False)
        try:
            if (source.size[0], source.size[1]) != (SPRITE_SIZE, SPRITE_SIZE):
                source.scale(SPRITE_SIZE, SPRITE_SIZE)
            source_pixels = array("f", [0.0]) * (SPRITE_SIZE * SPRITE_SIZE * 4)
            source.pixels.foreach_get(source_pixels)
            x_start = (index % SPRITE_COLUMNS) * SPRITE_SIZE
            # Blender image buffers are bottom-up; reverse the row index so
            # frame 1 occupies the top-left cell expected by sprite sheets.
            y_start = (rows - 1 - index // SPRITE_COLUMNS) * SPRITE_SIZE
            row_length = SPRITE_SIZE * 4
            for row in range(SPRITE_SIZE):
                source_start = row * row_length
                target_start = ((y_start + row) * sheet_width + x_start) * 4
                sheet_pixels[target_start:target_start + row_length] = source_pixels[source_start:source_start + row_length]
        finally:
            bpy.data.images.remove(source)

    sheet = bpy.data.images.new(
        f"TMP_IceShield_Sheet_{out_path.stem}",
        width=sheet_width,
        height=sheet_height,
        alpha=True,
        float_buffer=False,
    )
    sheet.pixels.foreach_set(sheet_pixels)
    sheet.filepath_raw = str(out_path)
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)
    print(f"[sheet] {out_path}: {len(frames)} frames at {SPRITE_SIZE}px")


def prepare_fracture_texture(source_path: Path, size: int = 1024) -> Path:
    """Keep the generated source intact and save a power-of-two game texture copy."""
    out_path = source_path.with_name(f"{source_path.stem}_{size}.png")
    image = bpy.data.images.load(str(source_path), check_existing=False)
    try:
        image.scale(size, size)
        image.filepath_raw = str(out_path)
        image.file_format = "PNG"
        image.save()
    finally:
        bpy.data.images.remove(image)
    print(f"[texture] {out_path}: {size}x{size} RGBA")
    return out_path


def main(variant: str = "current") -> None:
    if variant == "current":
        asset_dir, effect_dir = ASSET_DIR, EFFECT_DIR
    elif variant == "v2":
        asset_dir, effect_dir = V2_ASSET_DIR, V2_EFFECT_DIR
    else:
        raise ValueError(f"unsupported build variant: {variant}")

    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "previews").mkdir(parents=True, exist_ok=True)
    effect_dir.mkdir(parents=True, exist_ok=True)
    fracture_texture_path = None
    if variant == "v2":
        source_texture = asset_dir / "textures" / "T_IceShield_FrostVeins_RGBA_v2.png"
        if not source_texture.is_file():
            raise FileNotFoundError(f"V2 frost map missing: {source_texture}")
        fracture_texture_path = prepare_fracture_texture(source_texture)
    save_single_object_asset(
        "ice_shield_shell.blend",
        lambda collection: build_shell(collection, fracture_texture_path),
        asset_dir,
    )
    save_single_object_asset("ice_shield_rim.blend", build_rim, asset_dir)
    save_single_object_asset("ice_crystal_shard.blend", build_shard, asset_dir)
    build_idle_scene(asset_dir, effect_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("current", "v2"), default="current")
    arguments, _ = parser.parse_known_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    main(arguments.variant)
