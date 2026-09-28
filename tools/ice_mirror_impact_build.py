"""Build the actor-free Ice Mirror Shield contact response."""

from __future__ import annotations

import math
import os
import shutil
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ice_mirror_screen_build import (  # noqa: E402
    ACTOR_CENTER_Z,
    CELL_SIZE,
    PEAK_OPACITY,
    RENDER_SIZE,
    TEXTURE_PATH,
    add_screen_to_scene,
    child_collection,
    fresh_scene,
    ice_material,
    make_curve_object,
)


EFFECT_ID = "shield_ice_mirror_impact"
EFFECT_DIR = ROOT / "vfx" / EFFECT_ID
EFFECT_BLEND = EFFECT_DIR / f"{EFFECT_ID}.blend"
FRAME_COUNT = 24
FPS = 24
HIT_CENTER = (1.02, -0.20, ACTOR_CENTER_Z + 0.34)
FRACTURE_PATHS = (
    ((0.0, 0.0), (-0.09, 0.08), (-0.22, 0.13), (-0.38, 0.31)),
    ((0.0, 0.0), (-0.08, -0.02), (-0.18, -0.06), (-0.24, -0.12)),
    ((0.0, 0.0), (-0.03, -0.14), (-0.16, -0.23), (-0.28, -0.38)),
    ((0.0, 0.0), (0.13, 0.03), (0.22, 0.09)),
    ((0.0, 0.0), (0.03, 0.11), (0.15, 0.22), (0.12, 0.31)),
    ((-0.22, 0.13), (-0.29, 0.17), (-0.32, 0.24)),
    ((-0.16, -0.23), (-0.10, -0.30), (-0.07, -0.37)),
)
SHARDS = (
    {"name": "UpperLeft", "size": 0.57, "center": (-0.12, 0.19), "points": ((-0.06, -0.04), (0.04, -0.06), (0.09, 0.02), (-0.01, 0.08)), "drift": (-0.18, 0.28), "tilt": (0.34, -0.24, -0.28)},
    {"name": "Crown", "size": 0.82, "center": (-0.01, 0.30), "points": ((-0.05, -0.04), (0.04, -0.05), (0.03, 0.08)), "drift": (-0.03, 0.32), "tilt": (-0.22, 0.17, 0.26)},
    {"name": "Left", "size": 0.67, "center": (-0.23, 0.04), "points": ((-0.08, -0.03), (-0.01, -0.08), (0.08, 0.01)), "drift": (-0.31, 0.04), "tilt": (-0.26, 0.20, 0.31)},
    {"name": "Core", "size": 0.46, "center": (-0.08, 0.01), "points": ((-0.05, -0.03), (0.02, -0.06), (0.06, 0.02), (-0.02, 0.05)), "drift": (-0.08, 0.03), "tilt": (0.18, -0.25, 0.12)},
    {"name": "LowerLeft", "size": 0.88, "center": (-0.17, -0.16), "points": ((-0.06, 0.04), (0.05, 0.07), (0.08, -0.03), (-0.04, -0.08)), "drift": (-0.22, -0.22), "tilt": (0.28, -0.18, 0.25)},
    {"name": "Lower", "size": 0.53, "center": (-0.04, -0.30), "points": ((-0.06, 0.03), (0.05, 0.06), (0.01, -0.09)), "drift": (-0.02, -0.34), "tilt": (0.38, 0.12, -0.20)},
    {"name": "Outer", "size": 0.78, "center": (0.15, 0.11), "points": ((-0.05, -0.06), (0.07, -0.04), (0.06, 0.06), (-0.02, 0.09)), "drift": (0.17, 0.15), "tilt": (-0.31, 0.24, -0.19)},
    {"name": "LowerRight", "size": 0.62, "center": (0.11, -0.12), "points": ((-0.07, 0.03), (0.06, 0.04), (0.04, -0.07)), "drift": (0.12, -0.22), "tilt": (-0.19, -0.14, 0.33)},
)


def make_faceted_glint(
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    layer: str = "ice",
) -> bpy.types.Object:
    """A bright two-tone diamond marks the fracture origin."""
    cyan = ice_material(
        "MAT_IceImpact_Glint_Cyan", None, (0.20, 0.78, 1.0, 1.0), 0.72
    )
    blue = ice_material(
        "MAT_IceImpact_Glint_Blue", None, (0.22, 0.48, 0.92, 1.0), 0.72
    )
    points = (
        (0.0, -0.055, 0.105),
        (0.072, -0.055, 0.0),
        (0.0, -0.055, -0.105),
        (-0.072, -0.055, 0.0),
    )
    mesh = bpy.data.meshes.new("ICE_Impact_ContactDiamond_Mesh")
    mesh.from_pydata(points, [], [(0, 1, 2), (0, 2, 3)])
    mesh.materials.append(cyan)
    mesh.materials.append(blue)
    mesh.polygons[0].material_index = 0
    mesh.polygons[1].material_index = 1
    mesh.update()

    obj = bpy.data.objects.new("ICE_Impact_ContactDiamond", mesh)
    collection.objects.link(obj)
    obj.parent = root
    obj.location = (0.0, 0.0, 0.0)
    obj.color = (1.0, 1.0, 1.0, 1.0)
    obj["vfx_layer"] = layer
    obj["role"] = "small two-tone prism glint at the shield contact point"
    return obj


def mirror_shard_material(name: str, color: tuple[float, float, float, float]) -> bpy.types.Material:
    """Lit, lightly metallic glass with object-driven fade for flying facets."""
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    links = material.node_tree.links

    object_info = nodes.new("ShaderNodeObjectInfo")
    transparent = nodes.new("ShaderNodeBsdfTransparent")
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Metallic"].default_value = 0.42
    principled.inputs["Roughness"].default_value = 0.18
    principled.inputs["IOR"].default_value = 1.46
    if "Coat Weight" in principled.inputs:
        principled.inputs["Coat Weight"].default_value = 0.65
        principled.inputs["Coat Roughness"].default_value = 0.10
    if "Emission Color" in principled.inputs:
        principled.inputs["Emission Color"].default_value = (color[0], color[1], color[2], 1.0)
        principled.inputs["Emission Strength"].default_value = 0.08

    mix = nodes.new("ShaderNodeMixShader")
    output = nodes.new("ShaderNodeOutputMaterial")
    links.new(object_info.outputs["Alpha"], mix.inputs[0])
    links.new(transparent.outputs[0], mix.inputs[1])
    links.new(principled.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], output.inputs["Surface"])

    if hasattr(material, "surface_render_method"):
        try:
            material.surface_render_method = "BLENDED"
        except (TypeError, ValueError):
            pass
    elif hasattr(material, "blend_method"):
        material.blend_method = "BLEND"
    material.use_backface_culling = False
    material.diffuse_color = color
    return material


def add_area_light(
    scene: bpy.types.Scene,
    name: str,
    location: tuple[float, float, float],
    color: tuple[float, float, float],
    energy: float,
    size: float,
) -> None:
    data = bpy.data.lights.new(f"{name}_Data", "AREA")
    data.energy = energy
    data.color = color
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = location
    direction = Vector(HIT_CENTER) - Vector(location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_fracture_lines(
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    frame_offset: int = 0,
    layer: str = "ice",
) -> tuple[bpy.types.Object, bpy.types.Object]:
    paths = [(list(points), False) for points in FRACTURE_PATHS]
    shadow_material = ice_material(
        "MAT_IceMirror_FractureShadow", None, (0.015, 0.07, 0.14, 1.0), 0.9
    )
    edge_material = ice_material(
        "MAT_IceMirror_FractureEdge", None, (0.22, 0.76, 1.0, 1.0), 0.78
    )
    shadow = make_curve_object(
        "ICE_Mirror_FractureShadow", collection, root, paths, shadow_material, 0.031, layer
    )
    edge = make_curve_object(
        "ICE_Mirror_FractureEdge", collection, root, paths, edge_material, 0.010, layer
    )
    edge.location.y = -0.008
    shadow["role"] = "dark narrow bevel beneath the localized fracture"
    edge["role"] = "cool highlight along five uneven branches and two offshoots"
    set_alpha_keys(shadow, ((1, 0.0), (3, 0.25), (5, 0.82), (9, 0.72), (13, 0.55), (17, 0.35), (20, 0.15), (22, 0.0)), frame_offset)
    set_alpha_keys(edge, ((1, 0.0), (3, 0.40), (5, 1.0), (9, 0.88), (13, 0.58), (17, 0.38), (20, 0.16), (22, 0.0)), frame_offset)
    return shadow, edge


def add_prism_shard(
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    spec: dict[str, object],
    palette: tuple[tuple[float, float, float, float], ...],
    frame_offset: int = 0,
    layer: str = "ice",
) -> bpy.types.Object:
    """Create a thin extruded fragment with a raised, triangulated mirror face."""
    shard_size = float(spec["size"])
    points = [(point[0] * 1.20 * shard_size, point[1] * 1.20 * shard_size) for point in spec["points"]]
    area = sum(
        points[index][0] * points[(index + 1) % len(points)][1]
        - points[(index + 1) % len(points)][0] * points[index][1]
        for index in range(len(points))
    )
    if area < 0.0:
        points.reverse()

    count = len(points)
    center_x = sum(point[0] for point in points) / count
    center_z = sum(point[1] for point in points) / count
    depth = 0.070 * shard_size
    front_y = -depth * 0.5
    back_y = depth * 0.5
    vertices = [(x, front_y, z) for x, z in points]
    center_index = len(vertices)
    vertices.append((center_x, front_y - depth * 0.64, center_z))
    back_start = len(vertices)
    vertices.extend((x, back_y, z) for x, z in points)

    faces: list[tuple[int, ...]] = []
    for index in range(count):
        faces.append((index, (index + 1) % count, center_index))
    faces.append(tuple(back_start + index for index in reversed(range(count))))
    for index in range(count):
        next_index = (index + 1) % count
        faces.append((index, next_index, back_start + next_index, back_start + index))

    mesh = bpy.data.meshes.new(f"ICE_MirrorShard_{spec['name']}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    for index, color in enumerate(palette):
        mesh.materials.append(mirror_shard_material(f"MAT_IceMirrorShard_{spec['name']}_{index}", color))
    side_index = len(mesh.materials) - 1
    for index, polygon in enumerate(mesh.polygons):
        polygon.material_index = index % len(palette) if index < count else side_index
    mesh.update()

    obj = bpy.data.objects.new(f"ICE_MirrorShard_{spec['name']}", mesh)
    collection.objects.link(obj)
    obj.parent = root
    obj.location = (spec["center"][0], 0.13, spec["center"][1])
    obj.color = (1.0, 1.0, 1.0, 0.0)
    obj["vfx_layer"] = layer
    obj["role"] = "small extruded mirror facet that lifts and tilts toward camera"
    obj["thickness_units"] = depth

    bevel = obj.modifiers.new("Beveled_Mirror_Edges", "BEVEL")
    bevel.width = 0.009 * shard_size
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(25.0)
    bevel.harden_normals = True

    drift_x, drift_z = spec["drift"]
    tilt_x, tilt_y, tilt_z = spec["tilt"]
    transform_keys = (
        (1, 0.13, 0.0, 0.0, 0.0),
        (4, 0.10, 0.0, 0.0, 0.0),
        (7, -0.05, drift_x * 0.25, drift_z * 0.25, 0.10),
        (10, -0.16, drift_x * 0.75, drift_z * 0.75, 0.70),
        (14, -0.28, drift_x * 1.15, drift_z * 1.15, 1.0),
        (17, -0.34, drift_x * 1.3, drift_z * 1.3, 1.15),
    )
    for frame, depth_offset, dx, dz, turn in transform_keys:
        obj.location = (spec["center"][0] + dx, depth_offset, spec["center"][1] + dz)
        obj.rotation_euler = (tilt_x * turn, tilt_y * turn, tilt_z * turn)
        obj.keyframe_insert(data_path="location", frame=frame + frame_offset)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame + frame_offset)
    set_alpha_keys(obj, ((1, 0.0), (4, 0.0), (6, 0.95), (10, 0.95), (14, 0.68), (17, 0.26), (19, 0.0)), frame_offset)
    return obj


def set_alpha_keys(
    obj: bpy.types.Object,
    keys: tuple[tuple[int, float], ...],
    frame_offset: int = 0,
) -> None:
    for frame, alpha in keys:
        obj.color[3] = alpha
        obj.keyframe_insert(data_path="color", index=3, frame=frame + frame_offset)


def animate_glint(glint: bpy.types.Object, frame_offset: int = 0) -> None:
    set_alpha_keys(
        glint,
        ((1, 0.0), (3, 0.32), (5, 1.0), (7, 0.78), (10, 0.30), (13, 0.0)),
        frame_offset,
    )


def add_impact_response(
    collection: bpy.types.Collection,
    *,
    parent_screen: bpy.types.Object | None = None,
    frame_offset: int = 0,
    layer: str = "ice",
    hero_crystal_count: int = 0,
) -> tuple[bpy.types.Object, list[bpy.types.Object], list[bpy.types.Object]]:
    """Add the localized fracture and facets to a scene's existing screen."""
    root = bpy.data.objects.new("ICE_RIG_ImpactContact", None)
    collection.objects.link(root)
    root.empty_display_type = "SPHERE"
    root.empty_display_size = 0.08
    root.hide_render = True
    root["impact_location"] = "upper-right screen facet"
    root["hero_crystals_in_scene"] = hero_crystal_count
    root["timeline_offset"] = frame_offset
    if parent_screen is None:
        root.location = HIT_CENTER
    else:
        root.parent = parent_screen
        root.location = tuple(
            HIT_CENTER[index] - parent_screen.location[index]
            for index in range(3)
        )

    shadow, edge = add_fracture_lines(collection, root, frame_offset, layer)
    glint = make_faceted_glint(collection, root, layer)
    animate_glint(glint, frame_offset)
    palettes = (
        ((0.34, 0.78, 0.96, 1.0), (0.12, 0.46, 0.76, 1.0), (0.08, 0.24, 0.46, 1.0)),
        ((0.42, 0.84, 1.0, 1.0), (0.16, 0.54, 0.84, 1.0), (0.06, 0.20, 0.40, 1.0)),
        ((0.24, 0.68, 0.92, 1.0), (0.10, 0.38, 0.70, 1.0), (0.05, 0.18, 0.36, 1.0)),
        ((0.48, 0.88, 1.0, 1.0), (0.18, 0.56, 0.82, 1.0), (0.08, 0.26, 0.48, 1.0)),
    )
    shards = [
        add_prism_shard(
            collection,
            root,
            spec,
            palettes[index % len(palettes)],
            frame_offset,
            layer,
        )
        for index, spec in enumerate(SHARDS)
    ]
    objects = [shadow, edge, glint, *shards]
    root["facet_count"] = len(shards)
    return root, objects, shards


def build_scene() -> dict[str, object]:
    scene = fresh_scene()
    scene.name = "SCN_IceMirror_Impact"
    scene.render.fps = FPS
    scene.frame_start = 1
    scene.frame_end = FRAME_COUNT

    # Reuse the idle's exact face, rim, texture, and camera. Clear only the
    # deploy animation so the one-shot begins with the full shield visible.
    image, screen_root, body, rim, _ = add_screen_to_scene(scene)
    screen_root.animation_data_clear()
    body.animation_data_clear()
    rim.animation_data_clear()
    screen_root.scale = (1.0, 1.0, 1.0)
    body.color = (1.0, 1.0, 1.0, PEAK_OPACITY)
    rim.color = (1.0, 1.0, 1.0, PEAK_OPACITY)
    body["vfx_layer"] = "ice"
    rim["vfx_layer"] = "ice"
    screen_root["combat_screen_state"] = "full-size, translucent hex held throughout impact"

    collection = child_collection("86_Impact_Contact", scene.collection)
    root, response_objects, shards = add_impact_response(collection)
    root["hero_crystals_in_sprite"] = 0

    add_area_light(scene, "LIGHT_IceShard_Key", (-1.8, -3.2, 4.4), (0.58, 0.82, 1.0), 1800.0, 1.6)
    add_area_light(scene, "LIGHT_IceShard_Rim", (2.3, -2.6, 2.0), (0.16, 0.52, 1.0), 1300.0, 0.9)

    if scene.camera is None:
        raise RuntimeError("Ice Mirror impact scene has no camera")
    scene.camera.data.ortho_scale = 5.2
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
    scene.view_settings.view_transform = "Standard"

    scene["design"] = (
        "The idle's full-size translucent, ground-pointing mirror hex holds steady. "
        "A localized angular fracture branches from one upper-right contact. "
        "Eight differently sized extruded mirror facets lift, tilt toward camera, and clear. "
        "The idle's three hero crystals are not duplicated in this one-shot sprite."
    )
    scene["frame_timing"] = "quiet 1-2; fracture opens 3-6; facets lift 6-14; cracks clear by 22"
    scene["screen_hex_side_lengths"] = screen_root["body_hex_side_lengths"]
    scene["screen_rim_side_lengths"] = screen_root["rim_hex_side_lengths"]
    scene.frame_set(8)
    return {
        "blend": str(EFFECT_BLEND),
        "frames": FRAME_COUNT,
        "fps": FPS,
        "hit_center": [round(value, 3) for value in HIT_CENTER],
        "hero_crystals_in_sprite": 0,
        "impact_objects": len(response_objects),
        "fracture_branches": len(FRACTURE_PATHS),
        "extruded_mirror_facets": len(shards),
        "facet_size_scales": [round(float(spec["size"]), 2) for spec in SHARDS],
        "facet_thickness_units": [round(0.070 * spec["size"], 4) for spec in SHARDS],
        "hex_body_sides": screen_root["body_hex_side_lengths"],
        "hex_rim_sides": screen_root["rim_hex_side_lengths"],
        "screen_expands_or_collapses": False,
    }


def save_effect(image: bpy.types.Image) -> None:
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(EFFECT_BLEND))
    image.filepath = "//" + os.path.relpath(TEXTURE_PATH, EFFECT_DIR).replace("\\", "/")
    bpy.ops.wm.save_as_mainfile(filepath=str(EFFECT_BLEND))


def render_sequence() -> dict[str, object]:
    scene = bpy.context.scene
    if Path(bpy.data.filepath).resolve() != EFFECT_BLEND.resolve():
        raise RuntimeError(f"Expected the Ice Mirror impact scene to be open: {EFFECT_BLEND}")
    if scene.camera is None:
        raise RuntimeError("Ice Mirror impact scene has no camera")

    sequence_dir = EFFECT_DIR / "sequences" / "ice"
    preview_dir = EFFECT_DIR / "preview"
    sequence_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    for output_dir in (sequence_dir, preview_dir):
        for stale in output_dir.glob("*.png"):
            stale.unlink()

    renderables = [obj for obj in scene.objects if obj.get("vfx_layer") == "ice"]
    expected_count = 5 + len(SHARDS)
    if len(renderables) != expected_count:
        raise RuntimeError(
            "Expected one body, one rim, two fracture tracks, one glint, "
            f"and {len(SHARDS)} extruded mirror facets; "
            f"got {len(renderables)} tagged objects"
        )

    for frame in range(1, FRAME_COUNT + 1):
        scene.frame_set(frame)
        scene.render.filepath = str((sequence_dir / f"{frame:04d}.png").with_suffix(""))
        bpy.ops.render.render(write_still=True)
        output = sequence_dir / f"{frame:04d}.png"
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Blender did not write impact frame {frame}: {output}")

        preview = preview_dir / f"composite_{frame:04d}.png"
        shutil.copy2(sequence_dir / f"{frame:04d}.png", preview)

    scene.frame_set(8)
    scene.render.filepath = "//"
    pixels_per_unit = CELL_SIZE / scene.camera.data.ortho_scale
    print(f"{EFFECT_ID}: {pixels_per_unit:.1f} px/unit, {FRAME_COUNT} frames at {FPS} fps")
    return {"frames": FRAME_COUNT, "resolution": RENDER_SIZE, "layer": str(sequence_dir)}


def main() -> None:
    if not TEXTURE_PATH.is_file():
        raise FileNotFoundError(f"Ice Mirror screen texture is missing: {TEXTURE_PATH}")
    build = build_scene()
    image = bpy.data.images.get("T_IceShield_MirrorHexScreen_RGBA.png")
    if image is None:
        image = bpy.data.images.load(str(TEXTURE_PATH), check_existing=True)
    save_effect(image)
    rendered = render_sequence()
    print("ICE_MIRROR_IMPACT_BUILD_COMPLETE", {**build, **rendered})


if __name__ == "__main__":
    main()
