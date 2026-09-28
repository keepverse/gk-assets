"""Build the actor-free Ice Mirror hex-screen deployment effect."""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
TEXTURE_PATH = (
    ROOT / "assets" / "vfx" / "ice_shield" / "textures" / "mirror_screen_v1"
    / "T_IceShield_MirrorHexScreen_RGBA.png"
)
EFFECT_DIR = ROOT / "vfx" / "shield_ice_mirror_deploy"
EFFECT_BLEND = EFFECT_DIR / "shield_ice_mirror_deploy.blend"

FRAME_COUNT = 42
FPS = 12
RENDER_SIZE = 512
CELL_SIZE = 128
GROWTH_END = 9
HOLD_END = 27
FADE_END = FRAME_COUNT
PEAK_OPACITY = 0.78
BODY_RADIUS = 1.72
CAMERA_ORTHO_SCALE = 5.2
ACTOR_CENTER_Z = 1.55
HEX_PHASE = math.radians(90.0)  # put the top and bottom vertices on the vertical axis


def fresh_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.name = "SCN_IceShield_MirrorScreenDeploy"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    scene.render.use_file_extension = True
    scene.render.use_overwrite = True
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FRAME_COUNT
    scene.view_settings.view_transform = "Standard"
    scene.use_nodes = False

    camera_data = bpy.data.cameras.new("CAM_IceMirrorScreen_Data")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = CAMERA_ORTHO_SCALE
    camera = bpy.data.objects.new("CAM_IceMirrorScreen", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (0.0, -8.5, ACTOR_CENTER_Z)
    camera.rotation_euler = (math.pi * 0.5, 0.0, 0.0)
    scene.camera = camera
    scene.render.filepath = "//"
    return scene


def child_collection(name: str, parent: bpy.types.Collection) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def ice_material(
    name: str,
    image: bpy.types.Image | None,
    color: tuple[float, float, float, float],
    strength: float,
) -> bpy.types.Material:
    """Emission plus object-alpha transparency keeps the cold look readable."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links

    object_info = nodes.new("ShaderNodeObjectInfo")
    object_info.label = "Animated deploy opacity"
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Strength"].default_value = strength
    if image is not None:
        texture = nodes.new("ShaderNodeTexImage")
        texture.label = "Procedural Mirror Hex Veil"
        texture.image = image
        texture.interpolation = "Linear"
        texture.extension = "EXTEND"
        emission.inputs["Color"].default_value = color
        links.new(texture.outputs["Color"], emission.inputs["Color"])
        alpha = nodes.new("ShaderNodeMath")
        alpha.operation = "MULTIPLY"
        links.new(texture.outputs["Alpha"], alpha.inputs[0])
        links.new(object_info.outputs["Alpha"], alpha.inputs[1])
        mix_factor = alpha.outputs[0]
    else:
        emission.inputs["Color"].default_value = color
        mix_factor = object_info.outputs["Alpha"]

    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(mix_factor, mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(emission.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])
    if hasattr(material, "surface_render_method"):
        try:
            material.surface_render_method = "BLENDED"
        except (TypeError, ValueError):
            pass
    elif hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
    material.use_backface_culling = False
    return material


def hex_points(radius: float, count: int = 6) -> list[tuple[float, float]]:
    return [
        (radius * math.cos(HEX_PHASE + i * math.tau / count),
         radius * math.sin(HEX_PHASE + i * math.tau / count))
        for i in range(count)
    ]


def audit_equal_hex(points: list[tuple[float, float]], label: str) -> list[float]:
    if len(points) != 6:
        raise RuntimeError(f"{label} must have exactly six vertices; got {len(points)}")
    sides = [
        math.dist(points[index], points[(index + 1) % 6])
        for index in range(6)
    ]
    if max(sides) - min(sides) > 1e-6:
        raise RuntimeError(f"{label} is not equal-sided: {sides}")
    return sides


def make_body_mesh(
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    material: bpy.types.Material,
    points: list[tuple[float, float]],
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new("ICE_MirrorScreen_BodyMesh")
    mesh.from_pydata([(x, 0.0, z) for x, z in points], [], [tuple(range(len(points)))])
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UV_MirrorHexScreen")
    for loop in mesh.loops:
        x, _, z = mesh.vertices[loop.vertex_index].co
        uv_layer.data[loop.index].uv = (
            0.5 + x / (2.0 * BODY_RADIUS),
            0.5 + z / (2.0 * BODY_RADIUS),
        )
    mesh.materials.append(material)
    obj = bpy.data.objects.new("ICE_MirrorScreen_HexGlass", mesh)
    collection.objects.link(obj)
    obj.parent = root
    obj.location = (0.0, 0.0, 0.0)
    obj.color = (1.0, 1.0, 1.0, 1.0)
    obj["vfx_layer"] = "body"
    obj["role"] = "transparent frost-haze hexagonal mirror shield body"
    return obj


def make_curve_object(
    name: str,
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    paths: list[tuple[list[tuple[float, float]], bool]],
    material: bpy.types.Material,
    bevel_depth: float,
    layer: str,
) -> bpy.types.Object:
    data = bpy.data.curves.new(f"{name}_Curve", "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1
    data.bevel_depth = bevel_depth
    data.bevel_resolution = 2
    for points, cyclic in paths:
        spline = data.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, (x, z) in zip(spline.points, points):
            point.co = (x, -0.035, z, 1.0)
        spline.use_cyclic_u = cyclic
    data.materials.append(material)
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    obj.parent = root
    obj.location = (0.0, 0.0, 0.0)
    obj.color = (1.0, 1.0, 1.0, 1.0)
    obj["vfx_layer"] = layer
    return obj


def bind_driver(curve: bpy.types.FCurve, expression: str) -> None:
    curve.driver.type = "SCRIPTED"
    curve.driver.expression = expression


def animate_deploy(root: bpy.types.Object, opacity_objects: list[bpy.types.Object]) -> str:
    """Expand to full size, hold there, then fade while keeping full scale."""
    grow_t = f"min(1.0,max(0.0,(frame-1.0)/{GROWTH_END - 1}.0))"
    growth = f"sin(1.5707963267948966*{grow_t})"
    fade_t = f"min(1.0,max(0.0,(frame-{HOLD_END}.0)/{FADE_END - HOLD_END}.0))"
    # Smoothstep keeps the fade gentle at both ends while never shrinking the screen.
    fade = f"(1.0-(3.0*({fade_t})**2-2.0*({fade_t})**3))"
    for axis in range(3):
        bind_driver(root.driver_add("scale", axis), f"0.025+0.975*{growth}")
    opacity_expression = f"{PEAK_OPACITY:.4f}*{growth}*{fade}"
    for obj in opacity_objects:
        bind_driver(obj.driver_add("color", 3), opacity_expression)
    root["growth_frames"] = GROWTH_END
    root["hold_until_frame"] = HOLD_END
    root["fade_end_frame"] = FADE_END
    root["end_scale"] = "full size; opacity reaches zero without collapse"
    return opacity_expression


def audit_timeline(scene: bpy.types.Scene, root: bpy.types.Object, opacity_objects: list[bpy.types.Object]) -> dict[str, object]:
    scales = []
    opacities: list[list[float]] = [[] for _ in opacity_objects]
    for frame in range(1, FRAME_COUNT + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        scales.append(float(root.evaluated_get(depsgraph).scale.x))
        for index, obj in enumerate(opacity_objects):
            opacities[index].append(float(obj.evaluated_get(depsgraph).color[3]))

    if any(b + 1e-4 < a for a, b in zip(scales[:GROWTH_END - 1], scales[1:GROWTH_END])):
        raise RuntimeError("Mirror screen scale must expand monotonically during its growth phase")
    if max(abs(value - 1.0) for value in scales[GROWTH_END - 1:]) > 1e-4:
        raise RuntimeError("Mirror screen must stay at full size through the hold and fade; no collapse")
    if any(b > a + 1e-4 for values in opacities for a, b in zip(values[HOLD_END - 1:], values[HOLD_END:])):
        raise RuntimeError("Mirror screen opacity must not rise again during the fade")
    if max(abs(values[GROWTH_END - 1] - PEAK_OPACITY) for values in opacities) > 1e-4:
        raise RuntimeError(
            "Mirror screen must reach its translucent peak opacity at the end of expansion; "
            f"measured={[round(values[GROWTH_END - 1], 4) for values in opacities]}"
        )
    if max(values[-1] for values in opacities) > 1e-4:
        raise RuntimeError("Mirror screen must finish fully faded")

    return {
        "frames": FRAME_COUNT,
        "growth_end": GROWTH_END,
        "hold_end": HOLD_END,
        "fade_end": FADE_END,
        "peak_opacity": PEAK_OPACITY,
        "scale_at_growth_end": round(scales[GROWTH_END - 1], 4),
        "scale_at_final_frame": round(scales[-1], 4),
        "opacity_at_growth_end": [round(values[GROWTH_END - 1], 4) for values in opacities],
        "opacity_at_hold_end": [round(values[HOLD_END - 1], 4) for values in opacities],
        "opacity_at_final_frame": [round(values[-1], 4) for values in opacities],
        "collapse": False,
    }


def add_screen_to_scene(
    scene: bpy.types.Scene,
    collection_names: tuple[str, str, str] = (
        "00_DeployRig",
        "80_HexGlassBody",
        "81_FrostRim",
    ),
) -> tuple[bpy.types.Image, bpy.types.Object, bpy.types.Object, bpy.types.Object, dict[str, object]]:
    """Add the shared hex-screen rig to an existing authoring scene."""
    if not TEXTURE_PATH.is_file():
        raise FileNotFoundError(
            f"Mirror screen texture is missing: {TEXTURE_PATH}; run tools/generate_ice_mirror_screen_texture.py"
        )
    if scene.camera is None:
        raise RuntimeError("The Ice Mirror screen requires the prepared scene camera")

    image = bpy.data.images.load(str(TEXTURE_PATH), check_existing=True)
    image.colorspace_settings.name = "sRGB"
    rig_collection = child_collection(collection_names[0], scene.collection)
    body_collection = child_collection(collection_names[1], scene.collection)
    rim_collection = child_collection(collection_names[2], scene.collection)
    root = bpy.data.objects.new("ICE_RIG_MirrorScreenDeploy", None)
    rig_collection.objects.link(root)
    root.location = (scene.camera.location.x, -0.16, scene.camera.location.z)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = 0.20
    root.hide_render = True

    body_material = ice_material("MAT_IceMirror_HexGlass", image, (0.16, 0.55, 0.82, 1.0), 0.72)
    rim_material = ice_material("MAT_IceMirror_FrostRim", None, (0.20, 0.70, 1.0, 1.0), 0.80)
    body_points = hex_points(BODY_RADIUS)
    body_sides = audit_equal_hex(body_points, "Screen body")
    body = make_body_mesh(body_collection, root, body_material, body_points)

    rim_points = hex_points(1.90)
    rim_sides = audit_equal_hex(rim_points, "Frost rim")
    rim = make_curve_object(
        "ICE_MirrorScreen_HexRim",
        rim_collection,
        root,
        [(rim_points, True)],
        rim_material,
        0.021,
        "rim",
    )

    opacity_objects = [body, rim]
    opacity_expression = animate_deploy(root, opacity_objects)
    audit = audit_timeline(scene, root, opacity_objects)
    root["body_hex_side_lengths"] = body_sides
    root["rim_hex_side_lengths"] = rim_sides
    root["opacity_driver"] = opacity_expression
    root["end_scale"] = "full size; opacity reaches zero without collapse"
    return image, root, body, rim, audit


def save_effect(texture: bpy.types.Image) -> None:
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(EFFECT_BLEND))
    texture.filepath = "//" + os.path.relpath(TEXTURE_PATH, EFFECT_DIR).replace("\\", "/")
    bpy.ops.wm.save_as_mainfile(filepath=str(EFFECT_BLEND))


def build_scene() -> dict[str, object]:
    scene = fresh_scene()
    image, root, body, rim, audit = add_screen_to_scene(scene)
    body_sides = root["body_hex_side_lengths"]
    rim_sides = root["rim_hex_side_lengths"]
    opacity_expression = root["opacity_driver"]
    scene["design"] = (
        "Transparent cold mirror hex screen with a soft frost haze and one "
        "equal-sided outline. Expand, hold full-size, then fade without collapse."
    )
    scene["screen_root"] = root.name
    scene.frame_set(1)
    save_effect(image)
    return {
        "blend": str(EFFECT_BLEND),
        "texture": str(TEXTURE_PATH),
        "body_hex_side_lengths": body_sides,
        "rim_hex_side_lengths": rim_sides,
        "timeline_audit": audit,
    }


def render_sequence() -> dict[str, object]:
    scene = bpy.context.scene
    if Path(bpy.data.filepath).resolve() != EFFECT_BLEND.resolve():
        raise RuntimeError(f"Expected the built Mirror Screen scene to be open: {EFFECT_BLEND}")
    layer_ids = ("body", "rim")
    layer_objects = [obj for obj in scene.objects if obj.get("vfx_layer")]
    preview_dir = EFFECT_DIR / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for layer_id in layer_ids:
        sequence_dir = EFFECT_DIR / "sequences" / layer_id
        sequence_dir.mkdir(parents=True, exist_ok=True)
        for stale in sequence_dir.glob("*.png"):
            stale.unlink()
    for stale in preview_dir.glob("*.png"):
        stale.unlink()

    for layer_id in layer_ids:
        for obj in layer_objects:
            obj.hide_render = obj.get("vfx_layer") != layer_id
        sequence_dir = EFFECT_DIR / "sequences" / layer_id
        for frame in range(1, FRAME_COUNT + 1):
            scene.frame_set(frame)
            frame_path = sequence_dir / f"{frame:04d}.png"
            scene.render.filepath = str(frame_path.with_suffix(""))
            bpy.ops.render.render(write_still=True)
            if not frame_path.is_file() or frame_path.stat().st_size == 0:
                raise RuntimeError(f"Blender did not write {layer_id} frame {frame}: {frame_path}")

    for obj in layer_objects:
        obj.hide_render = False
    for frame in range(1, FRAME_COUNT + 1):
        scene.frame_set(frame)
        frame_path = preview_dir / f"composite_{frame:04d}.png"
        scene.render.filepath = str(frame_path.with_suffix(""))
        bpy.ops.render.render(write_still=True)
        if not frame_path.is_file() or frame_path.stat().st_size == 0:
            raise RuntimeError(f"Blender did not write composite frame {frame}: {frame_path}")

    scene.frame_set(1)
    scene.render.filepath = "//"
    return {"frames": FRAME_COUNT, "layers": list(layer_ids), "resolution": RENDER_SIZE}


def main() -> None:
    build = build_scene()
    rendered = render_sequence()
    print(f"shield_ice_mirror_deploy: {CELL_SIZE / CAMERA_ORTHO_SCALE:.1f} px/unit, {FRAME_COUNT} frames at {FPS} fps")
    print("ICE_MIRROR_SCREEN_BUILD_COMPLETE", {**build, **rendered})


if __name__ == "__main__":
    main()
