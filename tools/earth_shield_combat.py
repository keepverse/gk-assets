"""Author actor-free Earth Shield combat VFX from the reusable idle scene."""

from __future__ import annotations

import math
import random
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
IDLE_BLEND = ROOT / "vfx" / "shield_earth_idle" / "shield_earth_idle.blend"
RENDER_SIZE = 512
FPS = 24
ABSORB_CONTACT_FRAME = 9
ABSORB_PULSE_FRAME = ABSORB_CONTACT_FRAME + 1
ABSORB_CAPTURE_END_FRAME = 27

EFFECTS = {
    "impact": {"id": "shield_earth_impact", "frames": 24, "columns": 6},
    "break": {"id": "shield_earth_break", "frames": 36, "columns": 6},
    "absorb": {"id": "shield_earth_absorb", "frames": 36, "columns": 6},
    "penetrate": {"id": "shield_earth_penetrate", "frames": 36, "columns": 6},
    "deflect": {"id": "shield_earth_deflect", "frames": 24, "columns": 6},
}


def link_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def animate_property(control: bpy.types.Object, prop: str, keys: tuple[tuple[int, float], ...]) -> None:
    for frame, value in keys:
        control[prop] = value
        control.keyframe_insert(data_path=f'["{prop}"]', frame=frame, group="Earth Shield Combat")


def drive_value(material: bpy.types.Material, node_name: str, control: bpy.types.Object, prop: str) -> None:
    path = f'nodes["{node_name}"].outputs[0].default_value'
    driver = material.node_tree.driver_add(path).driver
    driver.type = "SCRIPTED"
    driver.expression = "v"
    variable = driver.variables.new()
    variable.name = "v"
    variable.type = "SINGLE_PROP"
    variable.targets[0].id = control
    variable.targets[0].data_path = f'["{prop}"]'


def configure_dome(
    control: bpy.types.Object,
    material: bpy.types.Material,
    profiles: dict[str, tuple[tuple[int, float], ...]],
) -> None:
    control.animation_data_clear()
    material.node_tree.animation_data_clear()
    for prop, keys in profiles.items():
        animate_property(control, prop, keys)
    for node_name, prop in (
        ("ES_RevealHeight", "reveal_height"),
        ("ES_FrontOpacity", "front_opacity"),
        ("ES_FrontGlowStrength", "front_glow"),
        ("ES_IdlePhase", "idle_phase"),
        ("ES_IdleRimGlow", "idle_rim"),
        ("ES_ShellOpacity", "shell_alpha"),
        ("ES_RimOpacity", "rim_alpha"),
        ("ES_VeinOpacity", "vein_alpha"),
    ):
        drive_value(material, node_name, control, prop)


def profile(frames: int, points: tuple[tuple[int, float], ...]) -> tuple[tuple[int, float], ...]:
    return ((1, points[0][1]), *points[1:], (frames, points[-1][1]))


def emission_material(name: str, color: tuple[float, float, float], strength: float) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    emission = nodes.new("ShaderNodeEmission")
    emission.inputs["Color"].default_value = (*color, 1.0)
    emission.inputs["Strength"].default_value = strength
    material.node_tree.links.new(emission.outputs[0], output.inputs["Surface"])
    return material


def glass_shard_material() -> bpy.types.Material:
    material = bpy.data.materials.new("M_ES_CombatGlassShards")
    material.diffuse_color = (0.28, 0.48, 0.20, 0.72)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    shader = nodes.new("ShaderNodeBsdfPrincipled")
    shader.inputs["Base Color"].default_value = (0.30, 0.50, 0.20, 1.0)
    shader.inputs["Metallic"].default_value = 0.08
    shader.inputs["Roughness"].default_value = 0.24
    shader.inputs["Alpha"].default_value = 0.70
    if "Emission Color" in shader.inputs:
        shader.inputs["Emission Color"].default_value = (0.32, 0.52, 0.12, 1.0)
    elif "Emission" in shader.inputs:
        shader.inputs["Emission"].default_value = (0.32, 0.52, 0.12, 1.0)
    if "Emission Strength" in shader.inputs:
        shader.inputs["Emission Strength"].default_value = 0.28
    material.node_tree.links.new(shader.outputs["BSDF"], output.inputs["Surface"])
    try:
        material.surface_render_method = "BLENDED"
    except (AttributeError, TypeError):
        pass
    return material


def add_curve(
    name: str,
    paths: list[list[tuple[float, float, float]]],
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    center: Vector,
    rotation,
    bevel: float,
    cyclic: bool = False,
) -> bpy.types.Object:
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1
    curve.bevel_depth = bevel
    curve.resolution_u = 1
    for path in paths:
        if len(path) < 2:
            continue
        spline = curve.splines.new("POLY")
        spline.points.add(len(path) - 1)
        for point, coordinate in zip(spline.points, path):
            point.co = (*coordinate, 1.0)
        spline.use_cyclic_u = cyclic
    obj = bpy.data.objects.new(name, curve)
    collection.objects.link(obj)
    obj.location = center
    obj.rotation_euler = rotation
    obj.data.materials.append(material)
    return obj


def ring_path(radius: float, samples: int = 64) -> list[tuple[float, float, float]]:
    return [
        (radius * math.cos(math.tau * i / samples), radius * math.sin(math.tau * i / samples), 0.0)
        for i in range(samples)
    ]


def scale_keys(obj: bpy.types.Object, keys: tuple[tuple[int, float], ...]) -> None:
    for frame, scale in keys:
        obj.scale = (scale, scale, scale)
        obj.keyframe_insert(data_path="scale", frame=frame)


def ring(
    name: str,
    radius: float,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    center: Vector,
    rotation,
    bevel: float = 0.018,
) -> bpy.types.Object:
    return add_curve(name, [ring_path(radius)], collection, material, center, rotation, bevel, cyclic=True)


def crack_paths(count: int, length: float, seed: int) -> list[list[tuple[float, float, float]]]:
    rng = random.Random(seed)
    paths = []
    for branch in range(count):
        angle = math.tau * branch / count + rng.uniform(-0.12, 0.12)
        points = [(0.0, 0.0, 0.0)]
        distance = 0.0
        x, y = 0.0, 0.0
        for _ in range(4):
            distance += length * rng.uniform(0.18, 0.30)
            angle += rng.uniform(-0.32, 0.32)
            x = math.cos(angle) * distance
            y = math.sin(angle) * distance
            points.append((x, y, rng.uniform(0.004, 0.018)))
        paths.append(points)
        if branch % 2 == 0:
            split = points[2]
            fork_angle = angle + rng.choice((-1, 1)) * rng.uniform(0.45, 0.9)
            end = (split[0] + math.cos(fork_angle) * length * 0.38,
                   split[1] + math.sin(fork_angle) * length * 0.38, 0.01)
            paths.append([points[1], split, end])
    return paths


def screen_basis(scene: bpy.types.Scene) -> tuple[Vector, Vector, Vector, object]:
    quaternion = scene.camera.matrix_world.to_quaternion()
    right = quaternion @ Vector((1.0, 0.0, 0.0))
    up = quaternion @ Vector((0.0, 1.0, 0.0))
    toward_camera = quaternion @ Vector((0.0, 0.0, 1.0))
    return right, up, toward_camera, quaternion.to_euler()


def screen_center(scene: bpy.types.Scene) -> tuple[Vector, Vector, Vector, object]:
    right, up, toward_camera, rotation = screen_basis(scene)
    center = Vector((0.0, 0.0, 1.15)) + toward_camera * 1.95
    return center, right, up, rotation


def impact_center(scene: bpy.types.Scene, offset_x: float = 0.58, offset_y: float = 0.18) -> tuple[Vector, Vector, Vector, object]:
    center, right, up, rotation = screen_center(scene)
    return center + right * offset_x + up * offset_y, right, up, rotation


def new_fragment(
    source: bpy.types.Object,
    name: str,
    collection: bpy.types.Collection,
    keys: tuple[tuple[int, Vector, float, tuple[float, float, float]], ...],
) -> bpy.types.Object:
    obj = source.copy()
    obj.data = source.data.copy()
    obj.name = name
    obj.parent = None
    obj.animation_data_clear()
    obj["role"] = "Earth Shield combat stone fragment"
    collection.objects.link(obj)
    for frame, location, scale, rotation in keys:
        obj.location = location
        obj.scale = (scale, scale, scale)
        obj.rotation_euler = rotation
        obj.keyframe_insert(data_path="location", frame=frame)
        obj.keyframe_insert(data_path="scale", frame=frame)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)
    return obj


def spawn_fragments(
    scene: bpy.types.Scene,
    center: Vector,
    right: Vector,
    up: Vector,
    count: int,
    event_frame: int,
    end_frame: int,
    distance: float,
    seed: int,
    inward: bool = False,
) -> list[bpy.types.Object]:
    collection = link_collection("65_Combat_Stones")
    sources = [obj for obj in scene.objects if obj.get("role") == "small trailing orbit fragment"]
    if not sources:
        raise RuntimeError("Earth Shield source scene has no textured chips to reuse")
    rng = random.Random(seed)
    result = []
    for i in range(count):
        source = sources[i % len(sources)]
        angle = math.tau * i / count + rng.uniform(-0.18, 0.18)
        direction = right * math.cos(angle) + up * math.sin(angle)
        size = rng.uniform(1.2, 2.1)
        spin = tuple(rng.uniform(-math.pi, math.pi) for _ in range(3))
        if inward:
            outer = center + direction * distance
            visible_at = max(2, event_frame)
            keys = (
                (1, outer, 0.001, spin),
                (visible_at - 1, outer, 0.001, spin),
                (visible_at, outer, size, spin),
                (min(visible_at + 9, end_frame - 1), center + direction * 0.12, size * 0.7, spin),
                (end_frame, center, 0.001, spin),
            )
        else:
            keys = (
                (1, center, 0.001, spin),
                (event_frame, center, 0.001, spin),
                (min(event_frame + 2, end_frame - 2), center + direction * 0.14, size, spin),
                (min(event_frame + 9, end_frame - 1), center + direction * distance * 0.55, size * 0.85, spin),
                (end_frame, center + direction * distance, size * 0.30, spin),
            )
        result.append(new_fragment(source, f"ES_CombatChip_{seed}_{i + 1:02d}", collection, keys))
    return result


def projectile(
    scene: bpy.types.Scene,
    source_name: str,
    name: str,
    keys: tuple[tuple[int, Vector, float, tuple[float, float, float]], ...],
) -> bpy.types.Object:
    source = bpy.data.objects.get(source_name)
    if source is None:
        raise RuntimeError(f"Missing textured projectile source: {source_name}")
    collection = link_collection("64_Combat_Projectiles")
    return new_fragment(source, name, collection, keys)


def make_shell_shards(
    scene: bpy.types.Scene,
    collection: bpy.types.Collection,
    material: bpy.types.Material,
    frames: int,
) -> list[bpy.types.Object]:
    radius = 2.30
    sectors = 6
    bands = 2
    rng = random.Random(8128)
    objects = []
    for sector in range(sectors):
        for band in range(bands):
            phi0 = math.tau * sector / sectors
            phi1 = math.tau * (sector + 1) / sectors
            elevation0 = (math.pi * 0.5) * band / bands
            elevation1 = (math.pi * 0.5) * (band + 1) / bands
            vertices: list[Vector] = []
            for row in range(3):
                elevation = elevation0 + (elevation1 - elevation0) * row / 2
                for column in range(3):
                    phi = phi0 + (phi1 - phi0) * column / 2
                    if row not in (0, 2) and column not in (0, 2):
                        phi += rng.uniform(-0.05, 0.05)
                        elevation += rng.uniform(-0.035, 0.035)
                    vertices.append(Vector((
                        radius * math.cos(elevation) * math.cos(phi),
                        radius * math.cos(elevation) * math.sin(phi),
                        radius * math.sin(elevation),
                    )))
            center = sum(vertices, Vector()) / len(vertices)
            faces = []
            for row in range(2):
                for column in range(2):
                    lower = row * 3 + column
                    faces.append((lower, lower + 1, lower + 4, lower + 3))
            mesh = bpy.data.meshes.new(f"ES_BreakShardMesh_{sector:02d}_{band:02d}")
            mesh.from_pydata([tuple(v - center) for v in vertices], [], faces)
            mesh.update()
            obj = bpy.data.objects.new(f"ES_BreakShellShard_{sector:02d}_{band:02d}", mesh)
            collection.objects.link(obj)
            obj.data.materials.append(material)
            obj.location = center
            solidify = obj.modifiers.new("Thin fractured shell", "SOLIDIFY")
            solidify.thickness = 0.025
            direction = Vector((center.x, center.y, center.z - 1.02)).normalized()
            outward = center + direction * 0.72
            farther = center + direction * 1.45 + Vector((0.0, 0.0, -0.18))
            spin = tuple(rng.uniform(-0.65, 0.65) for _ in range(3))
            for frame, location, rotation, scale in (
                (1, center, (0.0, 0.0, 0.0), 0.001),
                (5, center, (0.0, 0.0, 0.0), 0.001),
                (9, center, (0.0, 0.0, 0.0), 0.50),
                (17, outward, spin, 0.72),
                (frames, farther, tuple(a * 1.8 for a in spin), 0.36),
            ):
                obj.location = location
                obj.rotation_euler = rotation
                obj.scale = (scale, scale, scale)
                obj.keyframe_insert(data_path="location", frame=frame)
                obj.keyframe_insert(data_path="rotation_euler", frame=frame)
                obj.keyframe_insert(data_path="scale", frame=frame)
            obj["role"] = "fractured Earth Shield dome panel"
            objects.append(obj)
    return objects


def profiles_for(effect: str, frames: int) -> dict[str, tuple[tuple[int, float], ...]]:
    baseline = {
        "reveal_height": ((1, 2.30), (frames, 2.30)),
        "front_opacity": ((1, 0.025), (frames, 0.025)),
        "front_glow": ((1, 0.05), (frames, 0.05)),
        "idle_phase": ((1, 0.0), (frames, 0.0)),
        "idle_rim": ((1, 0.22), (frames, 0.22)),
        "shell_alpha": ((1, 0.025), (frames, 0.025)),
        "rim_alpha": ((1, 0.12), (frames, 0.12)),
        "vein_alpha": ((1, 0.035), (frames, 0.035)),
    }
    if effect == "impact":
        values = {
            "front_opacity": ((1, 0.025), (4, 0.40), (8, 0.12), (14, 0.025), (frames, 0.025)),
            "front_glow": ((1, 0.05), (4, 1.3), (7, 0.65), (12, 0.12), (frames, 0.05)),
            "idle_rim": ((1, 0.22), (4, 0.82), (8, 0.46), (14, 0.22), (frames, 0.22)),
            "rim_alpha": ((1, 0.12), (4, 0.36), (8, 0.25), (14, 0.12), (frames, 0.12)),
            "vein_alpha": ((1, 0.035), (4, 0.18), (8, 0.12), (14, 0.035), (frames, 0.035)),
        }
    elif effect == "break":
        values = {
            "front_opacity": ((1, 0.025), (4, 0.55), (7, 0.0), (frames, 0.0)),
            "front_glow": ((1, 0.05), (4, 1.6), (7, 0.0), (frames, 0.0)),
            "idle_rim": ((1, 0.22), (4, 1.0), (8, 0.0), (frames, 0.0)),
            "shell_alpha": ((1, 0.025), (4, 0.035), (8, 0.0), (frames, 0.0)),
            "rim_alpha": ((1, 0.12), (4, 0.48), (8, 0.0), (frames, 0.0)),
            "vein_alpha": ((1, 0.035), (4, 0.28), (8, 0.0), (frames, 0.0)),
        }
    elif effect == "absorb":
        values = {
            "front_opacity": ((1, 0.025), (ABSORB_CONTACT_FRAME, 0.025), (12, 0.50), (16, 0.24), (24, 0.04), (frames, 0.025)),
            "front_glow": ((1, 0.05), (ABSORB_CONTACT_FRAME, 0.05), (ABSORB_PULSE_FRAME, 0.42), (12, 1.4), (16, 0.65), (22, 0.16), (30, 0.05), (frames, 0.05)),
            "idle_phase": ((1, 0.0), (ABSORB_CONTACT_FRAME, 0.0), (14, 0.35), (22, 0.95), (30, 0.0), (frames, 0.0)),
            "idle_rim": ((1, 0.22), (ABSORB_CONTACT_FRAME, 0.22), (ABSORB_PULSE_FRAME, 0.52), (14, 0.88), (20, 0.42), (28, 0.22), (frames, 0.22)),
            "vein_alpha": ((1, 0.035), (ABSORB_CONTACT_FRAME, 0.035), (12, 0.13), (17, 0.32), (26, 0.06), (32, 0.035), (frames, 0.035)),
        }
    elif effect == "penetrate":
        values = {
            "front_opacity": ((1, 0.025), (8, 0.46), (12, 0.18), (21, 0.42), (28, 0.025), (frames, 0.025)),
            "front_glow": ((1, 0.05), (8, 1.4), (13, 0.28), (21, 1.2), (29, 0.05), (frames, 0.05)),
            "shell_alpha": ((1, 0.025), (13, 0.012), (20, 0.012), (27, 0.025), (frames, 0.025)),
            "idle_rim": ((1, 0.22), (8, 0.8), (14, 0.32), (22, 0.75), (29, 0.22), (frames, 0.22)),
            "vein_alpha": ((1, 0.035), (9, 0.24), (16, 0.10), (23, 0.22), (30, 0.035), (frames, 0.035)),
        }
    else:  # deflect
        values = {
            "front_opacity": ((1, 0.025), (5, 0.42), (8, 0.14), (14, 0.025), (frames, 0.025)),
            "front_glow": ((1, 0.05), (5, 1.35), (8, 0.45), (13, 0.08), (frames, 0.05)),
            "idle_rim": ((1, 0.22), (5, 0.82), (9, 0.40), (15, 0.22), (frames, 0.22)),
            "rim_alpha": ((1, 0.12), (5, 0.38), (9, 0.24), (15, 0.12), (frames, 0.12)),
        }
    baseline.update(values)
    return {name: tuple(keys) for name, keys in baseline.items()}


def add_impact_visuals(scene: bpy.types.Scene, effect: str, frames: int) -> None:
    fx_collection = link_collection("60_Combat_Glow")
    gold = emission_material("M_ES_CombatGold", (1.0, 0.43, 0.08), 0.82)
    pale = emission_material("M_ES_CombatPaleGold", (1.0, 0.73, 0.25), 0.78)
    green = emission_material("M_ES_CombatMossGlow", (0.46, 0.82, 0.18), 0.72)
    center, right, up, rotation = impact_center(scene)
    if effect == "impact":
        outer = ring("ES_ImpactShockOuter", 0.44, fx_collection, pale, center, rotation)
        inner = ring("ES_ImpactShockInner", 0.23, fx_collection, gold, center, rotation, 0.014)
        scale_keys(outer, ((1, 0.001), (3, 0.36), (7, 1.0), (12, 1.52), (18, 0.001), (frames, 0.001)))
        scale_keys(inner, ((1, 0.001), (4, 0.50), (8, 1.0), (13, 0.001), (frames, 0.001)))
        cracks = add_curve("ES_ImpactRadialCracks", crack_paths(8, 0.72, 103), fx_collection, gold, center, rotation, 0.014)
        scale_keys(cracks, ((1, 0.001), (3, 0.20), (5, 1.0), (9, 1.0), (15, 0.001), (frames, 0.001)))
        spawn_fragments(scene, center, right, up, 6, 4, frames, 1.05, 4401)
    elif effect == "absorb":
        shield_center, _, _, _ = screen_center(scene)
        contact = shield_center
        outer = ring("ES_AbsorbConvergingField", 0.66, fx_collection, green, contact, rotation, 0.022)
        inner = ring("ES_AbsorbCore", 0.28, fx_collection, pale, contact, rotation, 0.018)
        scale_keys(outer, ((1, 0.001), (ABSORB_CONTACT_FRAME, 0.001), (ABSORB_PULSE_FRAME, 0.36), (13, 1.0), (19, 0.72), (25, 0.20), (31, 0.001), (frames, 0.001)))
        scale_keys(inner, ((1, 0.001), (ABSORB_CONTACT_FRAME, 0.001), (11, 0.30), (14, 0.88), (20, 0.001), (frames, 0.001)))
        cracks = add_curve("ES_AbsorbVeinRays", crack_paths(6, 0.92, 112), fx_collection, green, contact, rotation, 0.011)
        scale_keys(cracks, ((1, 0.001), (ABSORB_CONTACT_FRAME, 0.001), (11, 0.62), (14, 1.0), (21, 0.55), (27, 0.001), (frames, 0.001)))
        projectile(scene, "ES_Rock_01_BasaltHeart", "ES_AbsorbedIncomingStone", (
            (1, shield_center + right * 2.55 + up * 0.5, 1.15, (0.2, 0.7, -0.4)),
            (6, shield_center + right * 1.75 + up * 0.32, 1.20, (0.4, 1.4, -0.8)),
            (ABSORB_CONTACT_FRAME, contact, 1.25, (0.6, 2.0, -1.1)),
            (14, contact, 1.20, (0.9, 2.8, -1.5)),
            (19, contact, 0.82, (1.0, 3.4, -1.9)),
            (24, contact, 0.42, (1.1, 3.8, -2.1)),
            (ABSORB_CAPTURE_END_FRAME, shield_center, 0.001, (1.2, 4.0, -2.2)),
            (frames, shield_center, 0.001, (1.2, 4.0, -2.2)),
        ))
        spawn_fragments(scene, contact, right, up, 6, 11, ABSORB_CAPTURE_END_FRAME, 0.62, 4512, inward=True)
    elif effect == "penetrate":
        entry = center - right * 0.72
        exit_point = center + right * 0.72
        for label, point, seed, at in (("Entry", entry, 117, 8), ("Exit", exit_point, 129, 20)):
            shock = ring(f"ES_Penetrate{label}Ring", 0.34, fx_collection, pale, point, rotation, 0.017)
            scale_keys(shock, ((1, 0.001), (at, 0.24), (at + 4, 1.0), (at + 9, 0.001), (frames, 0.001)))
            cracks = add_curve(f"ES_Penetrate{label}Cracks", crack_paths(7, 0.53, seed), fx_collection, gold, point, rotation, 0.012)
            scale_keys(cracks, ((1, 0.001), (at, 0.001), (at + 2, 0.8), (at + 6, 1.0), (at + 13, 0.001), (frames, 0.001)))
        projectile(scene, "ES_Rock_01_BasaltHeart", "ES_PenetratingIncomingStone", (
            (1, center - right * 3.15, 1.25, (0.0, 0.0, -0.3)),
            (7, center - right * 1.55, 1.35, (0.3, 1.2, -0.5)),
            (14, center, 1.48, (0.7, 2.4, -0.8)),
            (21, center + right * 1.55, 1.35, (1.0, 3.4, -1.1)),
            (28, center + right * 3.15, 1.10, (1.2, 4.4, -1.4)),
            (frames, center + right * 3.65, 0.70, (1.3, 4.8, -1.5)),
        ))
        spawn_fragments(scene, entry, right, up, 5, 8, frames, 0.68, 4623)
        spawn_fragments(scene, exit_point, right, up, 5, 20, frames, 0.68, 4624)
    elif effect == "deflect":
        shock = ring("ES_DeflectShockArc", 0.40, fx_collection, pale, center, rotation, 0.018)
        scale_keys(shock, ((1, 0.001), (4, 0.18), (7, 0.9), (11, 1.25), (16, 0.001), (frames, 0.001)))
        trail_points = [
            (1.52, 0.78, 0.0), (1.17, 0.55, 0.0), (0.86, 0.33, 0.0),
            (0.63, 0.14, 0.0), (0.42, 0.0, 0.0), (0.17, -0.08, 0.0),
        ]
        trail = add_curve("ES_DeflectedProjectileTrail", [trail_points], fx_collection, gold, center, rotation, 0.016)
        scale_keys(trail, ((1, 0.001), (4, 0.65), (6, 1.0), (9, 1.0), (15, 0.001), (frames, 0.001)))
        cracks = add_curve("ES_DeflectShortCracks", crack_paths(5, 0.45, 138), fx_collection, gold, center, rotation, 0.011)
        scale_keys(cracks, ((1, 0.001), (5, 0.001), (7, 0.7), (10, 0.6), (14, 0.001), (frames, 0.001)))
        projectile(scene, "ES_Rock_01_BasaltHeart", "ES_DeflectedIncomingStone", (
            (1, center + right * 2.30 + up * 1.0, 1.10, (0.4, 0.1, -0.3)),
            (4, center + right * 0.7 + up * 0.30, 1.15, (0.6, 1.2, -0.5)),
            (6, center, 1.20, (1.0, 2.2, -0.8)),
            (10, center + right * 0.7 + up * 0.55, 1.0, (1.3, 3.0, -1.3)),
            (16, center + right * 2.50 + up * 1.75, 0.70, (1.7, 4.2, -1.9)),
            (frames, center + right * 3.0 + up * 2.2, 0.001, (1.8, 4.8, -2.2)),
        ))
        spawn_fragments(scene, center, right, up, 5, 6, frames, 0.92, 4735)
    else:
        outer = ring("ES_BreakShockwave", 0.48, fx_collection, pale, center, rotation, 0.020)
        scale_keys(outer, ((1, 0.001), (3, 0.28), (6, 1.15), (10, 1.6), (14, 0.001), (frames, 0.001)))
        cracks = add_curve("ES_BreakFractureLines", crack_paths(12, 1.35, 149), fx_collection, pale, center, rotation, 0.019)
        scale_keys(cracks, ((1, 0.001), (3, 0.20), (5, 1.0), (8, 1.1), (12, 0.001), (frames, 0.001)))
        shards = glass_shard_material()
        shard_collection = link_collection("62_Broken_Dome_Panels")
        make_shell_shards(scene, shard_collection, shards, frames)
        spawn_fragments(scene, center, right, up, 10, 6, frames, 1.8, 4846)
        # The three guardian stones rupture out of their protected ring while
        # retaining their original textured meshes and small attached chips.
        rng = random.Random(4847)
        for index, rock in enumerate(obj for obj in scene.objects if obj.get("role") == "independent orbiting hero stone"):
            start_matrix = rock.matrix_world.copy()
            start = start_matrix.translation.copy()
            base_rotation = start_matrix.to_euler()
            radial = Vector((start.x, start.y, (start.z - 1.02) * 0.45)).normalized()
            spin = tuple(rng.uniform(-0.9, 0.9) for _ in range(3))
            rock.parent = None
            rock.matrix_world = start_matrix
            rock.animation_data_clear()
            for frame, position, size in (
                (1, start, 1.0),
                (6, start, 1.0),
                (15, start + radial * (0.55 + index * 0.07), 1.10),
                (frames, start + radial * (1.55 + index * 0.11), 0.92),
            ):
                progress = max(0.0, frame - 1.0) / max(1, frames - 1)
                rock.location = position
                rock.scale = (size, size, size)
                rock.rotation_euler = tuple(
                    base_rotation[axis] + spin[axis] * progress for axis in range(3)
                )
                rock.keyframe_insert(data_path="location", frame=frame)
                rock.keyframe_insert(data_path="scale", frame=frame)
                rock.keyframe_insert(data_path="rotation_euler", frame=frame)


def build_effect(effect: str) -> dict[str, object]:
    if effect not in EFFECTS:
        raise ValueError(f"Unknown Earth Shield combat effect: {effect}")
    if not IDLE_BLEND.is_file():
        raise FileNotFoundError(f"Earth Shield idle source scene is missing: {IDLE_BLEND}")

    bpy.ops.wm.open_mainfile(filepath=str(IDLE_BLEND))
    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("Earth Shield source has no active scene")
    scene.frame_set(1)
    frames = EFFECTS[effect]["frames"]
    effect_id = EFFECTS[effect]["id"]
    effect_dir = ROOT / "vfx" / effect_id
    scene.render.film_transparent = True
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.render.use_file_extension = True
    scene.render.use_overwrite = True
    scene.render.filepath = "//sequences/earth/frame_"
    scene.frame_start = 1
    scene.frame_end = frames

    actor_guides = bpy.data.collections.get("00_Actor_Guide")
    if actor_guides is not None:
        actor_guides.hide_render = True
    for obj in scene.objects:
        if obj.get("role", "").startswith("non-production actor"):
            obj.hide_render = True

    control = bpy.data.objects.get("ES_Shield_IdleControl")
    material = bpy.data.materials.get("M_ES_DomeShell")
    if control is None or material is None:
        raise RuntimeError("The Earth Shield source is missing its idle material controls")
    configure_dome(control, material, profiles_for(effect, frames))
    add_impact_visuals(scene, effect, frames)

    effect_dir.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    blend_path = effect_dir / f"{effect_id}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    sequence_dir = effect_dir / "sequences" / "earth"
    sequence_dir.mkdir(parents=True, exist_ok=True)
    for stale in sequence_dir.glob("frame_*.png"):
        stale.unlink()
    for frame in range(1, frames + 1):
        scene.frame_set(frame)
        scene.render.filepath = str(sequence_dir / f"frame_{frame:04d}")
        bpy.ops.render.render(write_still=True)
        output = sequence_dir / f"frame_{frame:04d}.png"
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Blender did not write {output}")

    print(
        f"EARTH_SHIELD_COMBAT_COMPLETE {effect_id}: {frames} frames at "
        f"{RENDER_SIZE}px, 128px/unit gameplay cells"
    )
    return {"effect": effect_id, "frames": frames, "fps": FPS, "blend": str(blend_path)}
