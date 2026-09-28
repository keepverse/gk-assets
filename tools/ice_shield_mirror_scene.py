"""Build the Ice Mirror idle as three looping vertical bubble flights.

The prepared .blend owns the crystal meshes, materials, textures, and
snowflake cards. This script adds three fixed guard stations around the actor.
Each major crystal bobs up and down on a fixed vertical lane. Companions have
small local drift; no major crystal travels around the actor on an orbit/path.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from ice_mirror_impact_build import (
    FRAME_COUNT as IMPACT_FRAME_COUNT,
    add_impact_response,
)
from ice_mirror_screen_build import add_screen_to_scene


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets" / "vfx" / "ice_shield"
SOURCE_BLEND = ASSET_DIR / "ice_mirror_flow.blend"
EFFECT_DIR = ROOT / "vfx" / "shield_ice_mirror_idle"
EFFECT_BLEND = EFFECT_DIR / "shield_ice_mirror_idle.blend"

FRAME_COUNT = 72
RENDER_SIZE = 512
CELL_SIZE = 128
RIG_COLLECTION = "85_Bubble_Bob_Rig"
VERTICAL_CYCLES = 2
HORIZONTAL_CYCLES = 3  # minor shards and snowflake companions only
IMPACT_START_FRAME = 7  # contact glint starts on frame 9, as the screen reaches full size

# Screen-space anchors form a deliberately staggered triangle around the
# camera's actor center. The unequal lower stations keep the three-crystal
# silhouette from collapsing into an evenly spaced ring/triangle as the heroes
# bob. Each crystal stays in its own small vertical flight zone; none follows a
# shared path or circles the actor.
HERO_ANCHORS = (
    (-0.45, 0.0, 2.75),     # offset crown
    (-1.75, 0.0, 1.45),     # lifted and widened lower left guard
    (1.35, 0.0, 0.95),      # lifted lower right guard
)
HERO_PHASES = (0.0, math.tau / 3.0, math.tau * 2.0 / 3.0)
HERO_VERTICAL_AMPLITUDES = (0.32, 0.30, 0.30)
HERO_HORIZONTAL_AMPLITUDES = (0.0, 0.0, 0.0)

# Assign the prepared minor shards and snowflake cards directly to the three
# guardian stations. These are companion groups, not extra moving routes.
MINOR_GROUPS = (0, 0, 1, 2, 2)
SNOWFLAKE_GROUPS = (0, 1, 2, 0, 1, 2, 0, 2)
MINOR_OFFSETS = {
    0: ((0.31, 0.0, -0.12), (-0.31, 0.0, -0.12)),
    1: ((-0.32, 0.0, 0.02),),
    2: ((0.31, 0.0, 0.12), (-0.31, 0.0, 0.12)),
}
SNOWFLAKE_OFFSETS = {
    0: ((-0.46, 0.0, 0.18), (0.45, 0.0, 0.13), (0.0, 0.0, -0.52)),
    1: ((-0.46, 0.0, 0.10), (0.42, 0.0, -0.26)),
    2: ((0.46, 0.0, 0.12), (-0.45, 0.0, 0.08), (0.0, 0.0, -0.50)),
}


def ensure_source_scene() -> None:
    """Always build from the saved prepared scene, not a stale output scene."""
    if not SOURCE_BLEND.is_file():
        raise FileNotFoundError(f"Prepared Ice Mirror scene not found: {SOURCE_BLEND}")
    current = Path(bpy.data.filepath).resolve() if bpy.data.filepath else None
    if current != SOURCE_BLEND.resolve():
        bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))


def collection_named(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def audit_prepared_objects(
    scene: bpy.types.Scene,
) -> tuple[list[bpy.types.Object], list[bpy.types.Object], list[bpy.types.Object]]:
    """Reject wrong source counts before creating any animation controls."""
    crystals = [obj for obj in scene.objects if obj.get("vfx_layer") == "crystals"]
    heroes = sorted(
        (obj for obj in crystals if obj.get("scale_class") == "hero"),
        key=lambda obj: obj.name,
    )
    minors = sorted(
        (obj for obj in crystals if obj.get("scale_class") == "minor"),
        key=lambda obj: obj.name,
    )
    flakes = sorted(
        (obj for obj in scene.objects if obj.get("vfx_layer") == "snowflakes"),
        key=lambda obj: obj.name,
    )

    if len(heroes) != 3:
        raise RuntimeError(f"Expected exactly three major crystal instances; found {len(heroes)}")
    if len(minors) != 5:
        raise RuntimeError(f"Expected five prepared minor shards; found {len(minors)}")
    if len(crystals) != len(heroes) + len(minors):
        raise RuntimeError(f"Unexpected crystal instances in the prepared scene: {len(crystals)}")
    if len(flakes) != 8:
        raise RuntimeError(f"Expected eight prepared snowflake cards; found {len(flakes)}")

    variants = set()
    for hero in heroes:
        collection = hero.instance_collection
        if collection is None:
            raise RuntimeError(f"Hero {hero.name} is not a prepared crystal collection instance")
        meshes = [obj for obj in collection.all_objects if obj.type == "MESH" and not obj.hide_render]
        if len(meshes) != 1:
            raise RuntimeError(
                f"Hero {hero.name} renders {len(meshes)} mesh objects from {collection.name}; "
                "each major variant must contain exactly one crystal mesh"
            )
        variants.add(collection.name)
    if len(variants) != 3:
        raise RuntimeError(f"Expected three distinct major crystal variants; found {sorted(variants)}")

    for crystal in (*heroes, *minors):
        if crystal.instance_collection is None:
            raise RuntimeError(f"Prepared crystal {crystal.name} lost its collection instance")
    return heroes, minors, flakes


def bind_driver(curve: bpy.types.FCurve, expression: str) -> None:
    driver = curve.driver
    driver.type = "SCRIPTED"
    driver.expression = expression


def frame_phase() -> str:
    return f"(frame - 1.0) / {FRAME_COUNT:.1f}"


def make_bubble_controller(
    hero: bpy.types.Object,
    index: int,
    collection: bpy.types.Collection,
) -> bpy.types.Object:
    anchor = HERO_ANCHORS[index]
    phase = HERO_PHASES[index]
    vertical_amplitude = HERO_VERTICAL_AMPLITUDES[index]
    horizontal_amplitude = HERO_HORIZONTAL_AMPLITUDES[index]
    seed = float(hero.get("path_seed", index + 1))

    controller = bpy.data.objects.new(f"ICE_RIG_BubbleGuard_{index + 1:02d}", None)
    collection.objects.link(controller)
    controller.location = anchor
    controller.empty_display_type = "SPHERE"
    controller.empty_display_size = 0.12
    controller.hide_render = True
    controller["role"] = "one of exactly three vertical-bob crystal controllers"
    controller["hero_crystal"] = hero.name
    controller["anchor"] = list(anchor)
    controller["vertical_motion"] = "repeating up/down bubble bob"
    controller["vertical_cycles"] = VERTICAL_CYCLES
    controller["horizontal_wobble_cycles"] = HORIZONTAL_CYCLES if horizontal_amplitude else 0
    controller["period_frames"] = FRAME_COUNT

    phase_expr = f"({frame_phase()} * {math.tau * VERTICAL_CYCLES:.12f} + {phase:.12f})"
    x_phase = phase * 0.73 + seed * 0.419
    z_expr = (
        f"{anchor[2]:.9f} + {vertical_amplitude:.9f} * sin({phase_expr})"
    )
    if horizontal_amplitude:
        x_expr = (
            f"{anchor[0]:.9f} + {horizontal_amplitude:.9f} * "
            f"sin({frame_phase()} * {math.tau * HORIZONTAL_CYCLES:.12f} + {x_phase:.12f})"
        )
        bind_driver(controller.driver_add("location", 0), x_expr)
    bind_driver(controller.driver_add("location", 2), z_expr)

    local_y = float(hero.location.y)
    local_rotation = hero.rotation_euler.copy()
    local_scale = hero.scale.copy()
    hero.parent = controller
    hero.matrix_parent_inverse = Matrix.Identity(4)
    hero.location = (0.0, local_y, 0.0)
    hero.rotation_euler = local_rotation
    hero.scale = local_scale
    hero["bubble_role"] = "one of exactly three major crystal guards"
    hero["bubble_controller"] = controller.name
    hero["bubble_phase"] = phase
    add_local_motion(hero, phase, seed, "hero")
    return controller


def add_local_motion(
    particle: bpy.types.Object,
    phase: float,
    seed: float,
    role: str,
    offset: tuple[float, float, float] | None = None,
) -> None:
    base = offset if offset is not None else tuple(particle.location)
    if role == "hero":
        lateral_amp, vertical_amp, twist_axis, twist_amp = 0.0, 0.025, 2, 0.08
    elif role == "minor":
        lateral_amp, vertical_amp, twist_axis, twist_amp = 0.045, 0.055, 2, 0.13
    else:
        lateral_amp, vertical_amp, twist_axis, twist_amp = 0.065, 0.080, 1, 0.12

    local_rotation = particle.rotation_euler.copy()
    local_scale = particle.scale.copy()
    particle.location = base
    particle.rotation_euler = local_rotation
    particle.scale = local_scale
    particle["bubble_role"] = role

    phase_expr = f"({frame_phase()} * {math.tau * VERTICAL_CYCLES:.12f} + {phase:.9f})"
    lateral_phase = phase * 0.61 + seed * 0.731
    if lateral_amp:
        x_curve = particle.driver_add("location", 0)
        bind_driver(
            x_curve,
            f"{base[0]:.9f} + {lateral_amp:.9f} * "
            f"sin({frame_phase()} * {math.tau * HORIZONTAL_CYCLES:.12f} + {lateral_phase:.9f})",
        )
    z_curve = particle.driver_add("location", 2)
    bind_driver(
        z_curve,
        f"{base[2]:.9f} + {vertical_amp:.9f} * "
        f"sin({phase_expr} + {seed * 1.213:.9f})",
    )
    twist = particle.driver_add("rotation_euler", twist_axis)
    bind_driver(
        twist,
        f"{local_rotation[twist_axis]:.9f} + {twist_amp:.9f} * "
        f"sin({phase_expr} + {seed * 0.417:.9f})",
    )


def attach_companions(
    particles: list[bpy.types.Object],
    controllers: list[bpy.types.Object],
    groups: tuple[int, ...],
    offsets: dict[int, tuple[tuple[float, float, float], ...]],
    role: str,
) -> None:
    if len(particles) != len(groups):
        raise RuntimeError(f"Expected {len(groups)} assigned {role} companions; found {len(particles)}")
    group_counts = [0, 0, 0]

    for particle, hero_index in zip(particles, groups):
        group_index = group_counts[hero_index]
        group_counts[hero_index] += 1
        group_offsets = offsets[hero_index]
        if group_index >= len(group_offsets):
            raise RuntimeError(f"Not enough authored {role} offsets for {particle.name}")

        local_y = float(particle.location.y)
        local_rotation = particle.rotation_euler.copy()
        local_scale = particle.scale.copy()
        offset = group_offsets[group_index]
        local_offset = (offset[0], local_y, offset[2])
        particle.parent = controllers[hero_index]
        particle.matrix_parent_inverse = Matrix.Identity(4)
        particle.location = local_offset
        particle.rotation_euler = local_rotation
        particle.scale = local_scale
        particle["bubble_controller"] = controllers[hero_index].name
        add_local_motion(
            particle,
            phase=(hero_index * 1.31 + group_index * 0.73),
            seed=float(particle.get("path_seed", group_index + 1)),
            role=role,
            offset=local_offset,
        )

    expected = [len(offsets[index]) for index in range(len(HERO_ANCHORS))]
    if group_counts != expected:
        raise RuntimeError(f"Expected {expected} {role} companions by guard; found {group_counts}")


def cross_2d(a: Vector, b: Vector) -> float:
    return a.x * b.y - a.y * b.x


def audit_bubble_formation(
    scene: bpy.types.Scene,
    controllers: list[bpy.types.Object],
    heroes: list[bpy.types.Object],
) -> dict[str, object]:
    """Check the three actual crystals bob vertically around the actor."""
    if len(controllers) != 3 or len(heroes) != 3:
        raise RuntimeError(f"Bubble audit requires 3 controllers and 3 heroes; got {len(controllers)}, {len(heroes)}")
    path_constraints = [
        (obj.name, constraint.name)
        for obj in scene.objects
        for constraint in obj.constraints
        if constraint.type == "FOLLOW_PATH"
    ]
    if path_constraints:
        raise RuntimeError(f"Bubble idle must not contain orbit/path constraints: {path_constraints}")

    camera = scene.camera
    if camera is None:
        raise RuntimeError("Prepared Ice scene has no camera")
    bpy.context.view_layer.update()
    camera_matrix = camera.matrix_world.copy()
    camera_inverse = camera_matrix.inverted()
    direction = camera_matrix.to_3x3() @ Vector((0.0, 0.0, -1.0))
    if abs(direction.y) < 1e-6:
        raise RuntimeError("Ice camera must look across the actor plane to audit the bubble formation")
    ray_distance = -camera.location.y / direction.y
    actor_center_world = camera.location + direction * ray_distance
    actor_center_camera = camera_inverse @ actor_center_world

    def screen_point(position: Vector) -> Vector:
        camera_point = camera_inverse @ position
        return Vector((camera_point.x - actor_center_camera.x, camera_point.y - actor_center_camera.y))

    position_samples: list[list[Vector]] = [[], [], []]
    minimum_pair_distance = float("inf")
    minimum_triangle_area = float("inf")
    minimum_actor_radius = float("inf")
    maximum_actor_radius = 0.0
    loop_error = 0.0
    first_frame: list[Vector] | None = None

    for frame in range(1, FRAME_COUNT + 2):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        points = [
            screen_point(hero.evaluated_get(depsgraph).matrix_world.translation)
            for hero in heroes
        ]
        for index, point in enumerate(points):
            position_samples[index].append(point)
        if frame == 1:
            first_frame = points
        elif frame == FRAME_COUNT + 1 and first_frame is not None:
            loop_error = max((a - b).length for a, b in zip(first_frame, points))

        radii = [point.length for point in points]
        minimum_actor_radius = min(minimum_actor_radius, min(radii))
        maximum_actor_radius = max(maximum_actor_radius, max(radii))
        for left in range(3):
            for right in range(left + 1, 3):
                minimum_pair_distance = min(minimum_pair_distance, (points[left] - points[right]).length)

        orientation = cross_2d(points[1] - points[0], points[2] - points[0])
        area = abs(orientation) * 0.5
        minimum_triangle_area = min(minimum_triangle_area, area)
        crosses = (
            cross_2d(points[1] - points[0], -points[0]),
            cross_2d(points[2] - points[1], -points[1]),
            cross_2d(points[0] - points[2], -points[2]),
        )
        if area < 0.5 or any(value * orientation < -1e-5 for value in crosses):
            raise RuntimeError(
                f"Three bobbing crystals do not enclose the actor at frame {frame}: "
                f"area={area:.3f}, actor_inside={all(value * orientation >= -1e-5 for value in crosses)}"
            )

    vertical_ranges = []
    horizontal_ranges = []
    for points in position_samples:
        vertical = [point.y for point in points]
        horizontal = [point.x for point in points]
        vertical_ranges.append(max(vertical) - min(vertical))
        horizontal_ranges.append(max(horizontal) - min(horizontal))
    if min(vertical_ranges) < 0.45:
        raise RuntimeError(f"A major crystal is not visibly bobbing vertically: ranges={vertical_ranges}")
    if max(horizontal_ranges) > 0.01:
        raise RuntimeError(
            f"Major crystals must stay on vertical bubble lanes; horizontal ranges={horizontal_ranges}"
        )
    if minimum_pair_distance < 1.4:
        raise RuntimeError(f"Major crystals crowd together: min separation={minimum_pair_distance:.3f}")
    if minimum_actor_radius < 0.7 or maximum_actor_radius > 2.2:
        raise RuntimeError(
            f"Major crystals leave the actor's protective field: "
            f"screen radius={minimum_actor_radius:.3f}..{maximum_actor_radius:.3f}"
        )
    if loop_error > 0.01:
        raise RuntimeError(f"Bubble motion does not loop: frame 1/73 error={loop_error:.4f}")

    return {
        "sampled_frames": FRAME_COUNT + 1,
        "path_constraints": 0,
        "major_crystals": 3,
        "vertical_ranges": [round(value, 4) for value in vertical_ranges],
        "horizontal_ranges": [round(value, 4) for value in horizontal_ranges],
        "min_hero_separation": round(minimum_pair_distance, 4),
        "min_triangle_area": round(minimum_triangle_area, 4),
        "actor_screen_radius": [round(minimum_actor_radius, 4), round(maximum_actor_radius, 4)],
        "loop_endpoint_error": round(loop_error, 6),
    }


def capture_asset_images() -> dict[str, Path]:
    image_paths: dict[str, Path] = {}
    for image in bpy.data.images:
        if image.source != "FILE":
            continue
        resolved = Path(bpy.path.abspath(image.filepath)).resolve()
        if resolved.is_relative_to(ASSET_DIR.resolve()):
            image_paths[image.name] = resolved
    return image_paths


def save_effect(image_paths: dict[str, Path]) -> None:
    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(EFFECT_BLEND))
    for image_name, absolute_path in image_paths.items():
        image = bpy.data.images.get(image_name)
        if image is not None:
            relative = os.path.relpath(absolute_path, EFFECT_DIR).replace("\\", "/")
            image.filepath = f"//{relative}"
    bpy.ops.wm.save_as_mainfile(filepath=str(EFFECT_BLEND))


def build_idle_scene() -> dict[str, object]:
    ensure_source_scene()
    scene = bpy.context.scene
    scene.name = "SCN_IceShield_MirrorBubbleIdle"
    heroes, minors, flakes = audit_prepared_objects(scene)

    rig_collection = collection_named(RIG_COLLECTION)
    controllers = [
        make_bubble_controller(hero, index, rig_collection)
        for index, hero in enumerate(heroes)
    ]
    attach_companions(minors, controllers, MINOR_GROUPS, MINOR_OFFSETS, "minor")
    attach_companions(flakes, controllers, SNOWFLAKE_GROUPS, SNOWFLAKE_OFFSETS, "snowflake")

    actor_collection = bpy.data.collections.get("00_Actor_Guide")
    if actor_collection is not None:
        actor_collection.hide_render = True
    guide = bpy.data.objects.get("ICE_Shield_FieldGuide")
    if guide is not None:
        guide.hide_render = True

    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.fps = 12
    scene.frame_start = 1
    scene.frame_end = FRAME_COUNT
    scene.render.filepath = "//"
    scene.view_settings.view_transform = "Standard"
    if scene.camera is None:
        raise RuntimeError("Prepared Ice scene has no camera")
    scene.camera.data.ortho_scale = 5.2

    screen_image, screen_root, screen_body, screen_rim, screen_timeline_audit = add_screen_to_scene(
        scene,
        (
            "82_MirrorScreen_Rig",
            "83_MirrorScreen_Body",
            "84_MirrorScreen_Rim",
        ),
    )
    screen_root["idle_cycle_frames"] = FRAME_COUNT
    screen_root["inactive_after_frame"] = 42
    screen_root["crystals_continue_while_hidden"] = True
    impact_collection = collection_named("86_Impact_Contact")
    impact_root, impact_objects, impact_shards = add_impact_response(
        impact_collection,
        parent_screen=screen_root,
        frame_offset=IMPACT_START_FRAME - 1,
        layer="impact",
        hero_crystal_count=len(heroes),
    )
    screen_root["impact_contact_frame"] = IMPACT_START_FRAME + 2
    screen_root["impact_facets"] = len(impact_shards)
    if len([obj for obj in scene.objects if obj.get("scale_class") == "hero"]) != 3:
        raise RuntimeError("Integrated mirror impact must retain exactly three hero crystals")
    if len(impact_objects) != 3 + len(impact_shards):
        raise RuntimeError(
            f"Integrated mirror impact has {len(impact_objects)} objects; "
            f"expected three fracture accents plus {len(impact_shards)} facets"
        )
    image_paths = capture_asset_images()
    scene["design"] = (
        "Three vertical bubble-bobbing ice crystals with companion shards and "
        "snowflakes; one ground-pointing hex screen expands, receives a localized "
        "eight-facet mirror impact, then fades. The three hero crystals remain in "
        "the same animated scene."
    )
    scene["impact_frame_range"] = [
        IMPACT_START_FRAME,
        IMPACT_START_FRAME + IMPACT_FRAME_COUNT - 1,
    ]
    scene["impact_hero_crystals_in_scene"] = len(heroes)

    formation_audit = audit_bubble_formation(scene, controllers, heroes)
    scene.frame_set(1 + FRAME_COUNT // 4)

    for marker_name, frame in (
        ("Bubble loop start", 1),
        ("Bubble ascent", 1 + FRAME_COUNT // 4),
        ("Bubble descent", 1 + FRAME_COUNT // 2),
        ("Bubble loop wrap", FRAME_COUNT + 1),
        ("Screen expands", 1),
        ("Screen full size", 9),
        ("Mirror impact contact", screen_root["impact_contact_frame"]),
        ("Mirror impact facets peak", IMPACT_START_FRAME + 13),
        ("Mirror impact cleared", IMPACT_START_FRAME + 21),
        ("Screen fade starts", 28),
        ("Screen fade complete", 42),
    ):
        old_marker = scene.timeline_markers.get(marker_name)
        if old_marker is not None:
            scene.timeline_markers.remove(old_marker)
        scene.timeline_markers.new(marker_name, frame=frame)

    save_effect(image_paths)
    return {
        "status": "built",
        "blend": str(EFFECT_BLEND),
        "major_crystal_instances": len(heroes),
        "major_crystal_meshes": 3,
        "major_crystal_bob_controllers": len(controllers),
        "minor_crystals": len(minors),
        "snowflake_cards": len(flakes),
        "impact_objects": len(impact_objects),
        "impact_facets": len(impact_shards),
        "impact_frame_range": scene["impact_frame_range"],
        "impact_hero_crystals_in_scene": len(heroes),
        "path_constraints": 0,
        "generated_crystal_meshes": 0,
        "frames": FRAME_COUNT,
        "fps": scene.render.fps,
        "duration_seconds": FRAME_COUNT / scene.render.fps,
        "vertical_cycles": VERTICAL_CYCLES,
        "image_paths_rebased": len(image_paths),
        "formation_audit": formation_audit,
        "screen_timeline_audit": screen_timeline_audit,
        "screen_layers": [screen_body.name, screen_rim.name],
    }
