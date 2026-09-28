"""Build Ice Mirror combat responses from the saved three-crystal idle scene."""

from __future__ import annotations

import math
import re
from pathlib import Path

import bpy
from mathutils import Vector

from ice_mirror_impact_build import (
    animate_glint,
    make_faceted_glint,
    mirror_shard_material,
    set_alpha_keys,
)
from ice_mirror_screen_build import (
    BODY_RADIUS,
    CELL_SIZE,
    PEAK_OPACITY,
    RENDER_SIZE,
    hex_points,
    ice_material,
    make_curve_object,
)


ROOT = Path(__file__).resolve().parents[1]
IDLE_BLEND = ROOT / "vfx" / "shield_ice_mirror_idle" / "shield_ice_mirror_idle.blend"
FPS = 24
CRYSTAL_FPS = 12
LAYER_IDS = ("crystals", "snowflakes", "body", "rim", "event")

EFFECTS = {
    "deflect": {
        "id": "shield_ice_mirror_deflect", "frames": 24,
        "markers": (("Projectile contact", 6), ("Prism deflection", 8), ("Trail clears", 18)),
    },
    "absorb": {
        "id": "shield_ice_mirror_absorb", "frames": 36,
        "markers": (("Shard contact", 9), ("Cold lock", 12), ("Absorb complete", 30)),
    },
    "penetrate": {
        "id": "shield_ice_mirror_penetrate", "frames": 36,
        "markers": (("Entry puncture", 8), ("Exit puncture", 20), ("Projectile clears", 32)),
    },
    "break": {
        "id": "shield_ice_mirror_break", "frames": 36,
        "markers": (("Impact flash", 5), ("Panels release", 9), ("Panel scatter peak", 25)),
    },
}


def link_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def set_scale_keys(obj: bpy.types.Object, keys: tuple[tuple[int, float], ...]) -> None:
    for frame, scale in keys:
        obj.scale = (scale, scale, scale)
        obj.keyframe_insert(data_path="scale", frame=frame)


def set_transform_keys(
    obj: bpy.types.Object,
    keys: tuple[tuple[int, float, float, float, float, float], ...],
) -> None:
    """Key frame, screen x/z, depth, size, and turn around the vertical axis."""
    for frame, x, z, depth, size, turn in keys:
        obj.location = (x, depth, z)
        obj.scale = (size, size, size)
        obj.rotation_euler = (0.0, turn, 0.0)
        obj.keyframe_insert(data_path="location", frame=frame)
        obj.keyframe_insert(data_path="scale", frame=frame)
        obj.keyframe_insert(data_path="rotation_euler", frame=frame)


def retime_idle_bob_drivers(scene: bpy.types.Scene) -> float:
    """Keep idle crystals on their authored real-time bob at the combat FPS."""
    frame_scale = CRYSTAL_FPS / FPS
    driver_owners = []
    for obj in scene.objects:
        role = obj.get("bubble_role")
        if obj.get("vertical_motion") or role in {"hero", "minor", "snowflake"}:
            driver_owners.append(obj)
    for obj in driver_owners:
        animation = obj.animation_data
        if animation is None:
            continue
        for curve in animation.drivers:
            expression = curve.driver.expression
            curve.driver.expression = re.sub(
                r"\bframe\b",
                f"(1.0 + (frame - 1.0) * {frame_scale:.6f})",
                expression,
            )
    return frame_scale


def audit_hero_bubble_motion(
    scene: bpy.types.Scene,
    heroes: list[bpy.types.Object],
) -> dict[str, dict[str, float]]:
    """Prove each hero stays on its vertical lane and visibly bobs."""
    tracks: dict[str, list[Vector]] = {hero.name: [] for hero in heroes}
    for hero in heroes:
        controls = (hero, hero.parent)
        for control in controls:
            if control is None:
                continue
            if any(constraint.type == "FOLLOW_PATH" for constraint in control.constraints):
                raise RuntimeError(f"Hero crystal {hero.name} must not use an orbit/path constraint")

    for frame in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for hero in heroes:
            tracks[hero.name].append(
                hero.evaluated_get(depsgraph).matrix_world.translation.copy()
            )

    audit: dict[str, dict[str, float]] = {}
    for name, positions in tracks.items():
        x_range = max(point.x for point in positions) - min(point.x for point in positions)
        depth_range = max(point.y for point in positions) - min(point.y for point in positions)
        vertical_range = max(point.z for point in positions) - min(point.z for point in positions)
        if x_range > 0.02 or depth_range > 0.02:
            raise RuntimeError(
                f"Hero crystal {name} left its vertical bubble lane: "
                f"x range={x_range:.4f}, depth range={depth_range:.4f}"
            )
        if vertical_range < 0.02:
            raise RuntimeError(
                f"Hero crystal {name} has no visible vertical bob: range={vertical_range:.4f}"
            )
        audit[name] = {
            "x_range": round(x_range, 4),
            "depth_range": round(depth_range, 4),
            "vertical_range": round(vertical_range, 4),
        }

    scene.frame_set(scene.frame_start)
    return audit


def event_root(
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    name: str,
    x: float,
    z: float,
    depth: float = -0.045,
) -> bpy.types.Object:
    root = bpy.data.objects.new(name, None)
    collection.objects.link(root)
    root.parent = screen_root
    root.location = (x, depth, z)
    root.empty_display_type = "CIRCLE"
    root.empty_display_size = 0.08
    root.hide_render = True
    root["role"] = "localized Ice Mirror combat contact control"
    root["vfx_layer"] = "control"
    return root


def pulse_ring(
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    name: str,
    radius: float,
    color: tuple[float, float, float, float],
    strength: float,
    scale_keys: tuple[tuple[int, float], ...],
    alpha_keys: tuple[tuple[int, float], ...],
    bevel: float = 0.018,
) -> bpy.types.Object:
    points = [
        (radius * math.cos(math.tau * index / 48), radius * math.sin(math.tau * index / 48))
        for index in range(48)
    ]
    material = ice_material(f"MAT_{name}", None, color, strength)
    obj = make_curve_object(
        name,
        collection,
        root,
        [(points, True)],
        material,
        bevel,
        "event",
    )
    set_scale_keys(obj, scale_keys)
    set_alpha_keys(obj, alpha_keys)
    obj["role"] = "transient mirror contact pulse"
    return obj


def fracture_marks(
    collection: bpy.types.Collection,
    root: bpy.types.Object,
    name: str,
    paths: tuple[tuple[tuple[float, float], ...], ...],
    frames: int,
    start_frame: int = 1,
    color: tuple[float, float, float, float] = (0.28, 0.82, 1.0, 1.0),
) -> bpy.types.Object:
    material = ice_material(f"MAT_{name}", None, color, 0.78)
    obj = make_curve_object(
        name,
        collection,
        root,
        [(list(path), False) for path in paths],
        material,
        0.010,
        "event",
    )
    set_alpha_keys(obj, (
        (1, 0.0), (max(2, start_frame - 1), 0.0), (start_frame, 0.15),
        (start_frame + 2, 0.95), (start_frame + 5, 0.68),
        (min(frames - 1, start_frame + 9), 0.20), (frames, 0.0),
    ))
    obj["role"] = "short angular mirror puncture marks"
    return obj


def contact_glow(
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    name: str,
    x: float,
    z: float,
    contact_frame: int,
    end_frame: int,
    radius: float = 0.28,
) -> tuple[bpy.types.Object, bpy.types.Object]:
    root = event_root(collection, screen_root, f"ICE_RIG_{name}", x, z)
    glint = make_faceted_glint(collection, root, "event")
    animate_glint(glint, contact_frame - 3)
    ring = pulse_ring(
        collection,
        root,
        f"ICE_{name}_Pulse",
        radius,
        (0.30, 0.82, 1.0, 1.0),
        0.76,
        ((1, 0.001), (contact_frame, 0.28), (contact_frame + 3, 0.90),
         (contact_frame + 6, 1.30), (min(end_frame - 2, contact_frame + 10), 0.001),
         (end_frame, 0.001)),
        ((1, 0.0), (contact_frame - 1, 0.0), (contact_frame + 1, 0.88),
         (contact_frame + 4, 0.70), (min(end_frame - 1, contact_frame + 9), 0.0),
         (end_frame, 0.0)),
    )
    return root, ring


def make_ice_dart(
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    name: str,
    keys: tuple[tuple[int, float, float, float, float, float], ...],
    alpha_keys: tuple[tuple[int, float], ...],
    color: tuple[float, float, float, float] = (0.42, 0.82, 1.0, 1.0),
) -> bpy.types.Object:
    """Create one low-poly, double-pointed 3D ice shard/projectile."""
    depth = 0.043
    ring = (
        (-0.078, -depth, -0.035),
        (0.0, -depth, -0.035),
        (0.078, -depth, -0.035),
        (0.078, depth, -0.035),
        (0.0, depth, -0.035),
        (-0.078, depth, -0.035),
    )
    vertices = [(0.0, 0.0, -0.29), *ring, (0.0, 0.0, 0.24)]
    back_tip = len(vertices) - 1
    faces = []
    for index in range(6):
        current = 1 + index
        following = 1 + (index + 1) % 6
        faces.append((0, current, following))
        faces.append((back_tip, following, current))
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], faces)
    material = mirror_shard_material(f"MAT_{name}", color)
    mesh.materials.append(material)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.parent = screen_root
    obj.color = (1.0, 1.0, 1.0, 0.0)
    obj["vfx_layer"] = "event"
    obj["role"] = "small faceted ice projectile or frost chip"
    bevel = obj.modifiers.new("Fine_Chip_Bevel", "BEVEL")
    bevel.width = 0.009
    bevel.segments = 2
    bevel.limit_method = "ANGLE"
    bevel.angle_limit = math.radians(22.0)
    bevel.harden_normals = True
    set_transform_keys(obj, keys)
    set_alpha_keys(obj, alpha_keys)
    return obj


def make_trail(
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    name: str,
    path: tuple[tuple[float, float], ...],
    color: tuple[float, float, float, float],
    strength: float,
    bevel: float,
    alpha_keys: tuple[tuple[int, float], ...],
) -> bpy.types.Object:
    material = ice_material(f"MAT_{name}", None, color, strength)
    trail = make_curve_object(
        name,
        collection,
        screen_root,
        [(list(path), False)],
        material,
        bevel,
        "event",
    )
    set_alpha_keys(trail, alpha_keys)
    trail["role"] = "short directional frost trail"
    return trail


def build_deflect(
    scene: bpy.types.Scene,
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    frames: int,
) -> dict[str, object]:
    x, z = 0.88, 0.34
    root, pulse = contact_glow(collection, screen_root, "DeflectContact", x, z, 6, frames, 0.32)
    fracture_marks(
        collection,
        root,
        "ICE_DeflectShortCracks",
        (
            ((0.0, 0.0), (-0.12, 0.10), (-0.22, 0.18)),
            ((0.0, 0.0), (0.13, -0.06), (0.23, -0.11)),
        ),
        frames,
        start_frame=6,
    )
    make_trail(
        collection,
        screen_root,
        "ICE_DeflectOutgoingTrail",
        ((x, z), (1.05, 0.42), (1.26, 0.60), (1.51, 0.86), (1.80, 1.20), (2.06, 1.52)),
        (0.20, 0.70, 1.0, 1.0),
        0.72,
        0.020,
        ((1, 0.0), (5, 0.0), (7, 0.55), (10, 0.90), (15, 0.62), (20, 0.0), (frames, 0.0)),
    )
    make_trail(
        collection,
        screen_root,
        "ICE_DeflectTrailCore",
        ((x, z), (1.08, 0.44), (1.34, 0.68), (1.64, 1.03), (1.95, 1.42)),
        (0.55, 0.92, 1.0, 1.0),
        0.48,
        0.007,
        ((1, 0.0), (6, 0.0), (8, 0.75), (12, 0.8), (16, 0.0), (frames, 0.0)),
    )
    make_ice_dart(
        collection,
        screen_root,
        "ICE_DeflectedShardProjectile",
        (
            (1, 2.25, 0.92, -0.08, 0.72, -2.05),
            (4, 1.46, 0.58, -0.09, 0.92, -2.05),
            (6, x, z, -0.11, 1.0, -2.05),
            (8, 1.00, 0.39, -0.12, 0.95, 0.72),
            (13, 1.43, 0.78, -0.14, 0.82, 0.82),
            (18, 2.06, 1.42, -0.16, 0.58, 0.88),
            (frames, 2.85, 2.02, -0.18, 0.001, 0.88),
        ),
        ((1, 0.0), (2, 0.78), (17, 0.78), (22, 0.25), (frames, 0.0)),
    )
    return {"contact_frame": 6, "pulse": pulse.name, "projectile": "one shard bends away from the hit"}


def build_absorb(
    scene: bpy.types.Scene,
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    frames: int,
) -> dict[str, object]:
    x, z = 0.24, 0.10
    root, outer = contact_glow(collection, screen_root, "AbsorbContact", x, z, 9, frames, 0.30)
    pulse_ring(
        collection,
        root,
        "ICE_AbsorbColdLock",
        0.15,
        (0.62, 0.93, 1.0, 1.0),
        0.52,
        ((1, 0.001), (9, 0.001), (12, 0.32), (16, 0.92), (22, 1.20), (28, 0.001), (frames, 0.001)),
        ((1, 0.0), (10, 0.0), (14, 0.75), (21, 0.60), (27, 0.0), (frames, 0.0)),
        0.010,
    )
    make_ice_dart(
        collection,
        screen_root,
        "ICE_AbsorbedShardProjectile",
        (
            (1, -2.25, 0.74, -0.08, 0.68, 1.30),
            (6, -1.14, 0.38, -0.09, 0.88, 1.30),
            (9, x, z, -0.11, 1.0, 1.30),
            (12, x, z, -0.11, 1.0, 1.30),
            (18, 0.16, 0.07, -0.14, 0.88, 1.18),
            (24, 0.08, 0.035, -0.17, 0.62, 0.96),
            (30, 0.01, 0.005, -0.19, 0.20, 0.76),
            (32, 0.0, 0.0, -0.19, 0.001, 0.76),
            (frames, 0.0, 0.0, -0.19, 0.001, 0.76),
        ),
        ((1, 0.0), (2, 0.8), (22, 0.8), (28, 0.42), (31, 0.0), (frames, 0.0)),
    )
    fleck_angles = (0.2, 1.8, 3.2, 5.1)
    fleck_sizes = (0.19, 0.14, 0.17, 0.12)
    for index, (angle, size) in enumerate(zip(fleck_angles, fleck_sizes), start=1):
        start_x = x + math.cos(angle) * 0.36
        start_z = z + math.sin(angle) * 0.36
        make_ice_dart(
            collection,
            screen_root,
            f"ICE_AbsorbFrostFleck_{index:02d}",
            (
                (1, start_x, start_z, -0.10, 0.001, angle),
                (18, start_x, start_z, -0.13, size, angle),
                (23, x + math.cos(angle) * 0.15, z + math.sin(angle) * 0.15, -0.16, size * 0.75, angle + 0.3),
                (29, 0.0, 0.0, -0.18, size * 0.18, angle + 0.6),
                (32, 0.0, 0.0, -0.18, 0.001, angle + 0.6),
                (frames, 0.0, 0.0, -0.18, 0.001, angle + 0.6),
            ),
            ((1, 0.0), (17, 0.0), (19, 0.78), (25, 0.58), (31, 0.0), (frames, 0.0)),
            (0.62, 0.91, 1.0, 1.0),
        )
    return {"contact_frame": 9, "capture_end_frame": 30, "frost_flecks": 4, "pulse": outer.name}


def build_penetrate(
    scene: bpy.types.Scene,
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    frames: int,
) -> dict[str, object]:
    entry = (-0.82, 0.12)
    exit_point = (0.82, -0.10)
    for label, point, contact_frame, offset in (
        ("Entry", entry, 8, 5),
        ("Exit", exit_point, 20, 17),
    ):
        root = event_root(collection, screen_root, f"ICE_RIG_Penetrate{label}", *point)
        glint = make_faceted_glint(collection, root, "event")
        animate_glint(glint, offset)
        pulse_ring(
            collection,
            root,
            f"ICE_Penetrate{label}Pulse",
            0.22,
            (0.34, 0.82, 1.0, 1.0),
            0.72,
            ((1, 0.001), (contact_frame, 0.20), (contact_frame + 3, 0.85),
             (contact_frame + 6, 1.15), (min(frames - 2, contact_frame + 10), 0.001),
             (frames, 0.001)),
            ((1, 0.0), (contact_frame - 1, 0.0), (contact_frame + 1, 0.85),
             (contact_frame + 5, 0.48), (min(frames - 1, contact_frame + 9), 0.0), (frames, 0.0)),
            0.014,
        )
        fracture_marks(
            collection,
            root,
            f"ICE_Penetrate{label}Fracture",
            (
                ((0.0, 0.0), (-0.15, 0.10), (-0.25, 0.20)),
                ((0.0, 0.0), (0.14, 0.08), (0.22, 0.18)),
                ((0.0, 0.0), (0.15, -0.08), (0.25, -0.13)),
                ((0.0, 0.0), (-0.11, -0.13), (-0.20, -0.24)),
            ),
            frames,
            start_frame=contact_frame,
        )
    make_ice_dart(
        collection,
        screen_root,
        "ICE_PenetratingShardProjectile",
        (
            (1, -2.55, 0.26, -0.08, 0.76, 1.56),
            (7, -1.02, 0.14, -0.10, 0.90, 1.56),
            (8, entry[0], entry[1], -0.12, 0.95, 1.56),
            (15, -0.02, 0.00, -0.16, 1.0, 1.56),
            (20, exit_point[0], exit_point[1], -0.18, 0.95, 1.56),
            (27, 1.86, -0.22, -0.20, 0.82, 1.56),
            (33, 2.50, -0.30, -0.22, 0.44, 1.56),
            (frames, 2.85, -0.35, -0.24, 0.001, 1.56),
        ),
        ((1, 0.0), (2, 0.82), (29, 0.82), (34, 0.25), (frames, 0.0)),
    )
    return {"entry_frame": 8, "exit_frame": 20, "puncture_count": 2}


def make_split_panel(
    collection: bpy.types.Collection,
    parent: bpy.types.Object,
    screen_material: bpy.types.Material,
    name: str,
    boundary: tuple[tuple[float, float], ...],
    drift: tuple[float, float],
    spin: tuple[float, float, float],
    frames: int,
) -> bpy.types.Object:
    coords = [(0.0, 0.0), *boundary]
    vertices = [(x, 0.0, z) for x, z in coords]
    mesh = bpy.data.meshes.new(f"{name}_Mesh")
    mesh.from_pydata(vertices, [], [tuple(range(len(vertices)))])
    mesh.update()
    uv_layer = mesh.uv_layers.new(name="UV_MirrorBreakPanel")
    for loop in mesh.loops:
        x, _, z = mesh.vertices[loop.vertex_index].co
        uv_layer.data[loop.index].uv = (0.5 + x / (2.0 * BODY_RADIUS), 0.5 + z / (2.0 * BODY_RADIUS))
    mesh.materials.append(screen_material)
    panel = bpy.data.objects.new(name, mesh)
    collection.objects.link(panel)
    panel.parent = parent
    panel.color = (1.0, 1.0, 1.0, 0.0)
    panel["vfx_layer"] = "event"
    panel["role"] = "large textured polygon panel released from the hex screen"
    solidify = panel.modifiers.new("Thin_Mirror_Panel", "SOLIDIFY")
    solidify.thickness = 0.065
    bevel = panel.modifiers.new("Beveled_Panel_Edges", "BEVEL")
    bevel.width = 0.014
    bevel.segments = 2
    bevel.harden_normals = True
    dx, dz = drift
    transform = (
        (1, 0.0, -0.035, 0.0, 0.001, 0.0),
        (5, 0.0, -0.035, 0.0, 0.001, 0.0),
        (9, dx * 0.12, -0.12, dz * 0.12, 1.0, spin[2] * 0.20),
        (16, dx * 0.48, -0.22, dz * 0.48, 0.92, spin[2] * 0.65),
        (25, dx * 0.95, -0.36, dz * 0.95, 0.73, spin[2]),
        (frames, dx * 1.48, -0.52, dz * 1.48, 0.38, spin[2] * 1.35),
    )
    for frame, x, depth, z, scale, turn in transform:
        panel.location = (x, depth, z)
        panel.rotation_euler = (spin[0] * (frame - 1) / (frames - 1), turn, spin[1] * (frame - 1) / (frames - 1))
        panel.scale = (scale, scale, scale)
        panel.keyframe_insert(data_path="location", frame=frame)
        panel.keyframe_insert(data_path="rotation_euler", frame=frame)
        panel.keyframe_insert(data_path="scale", frame=frame)
    set_alpha_keys(panel, ((1, 0.0), (7, 0.0), (10, 0.84), (19, 0.84), (27, 0.56), (33, 0.18), (frames, 0.0)))
    return panel


def build_break(
    scene: bpy.types.Scene,
    collection: bpy.types.Collection,
    screen_root: bpy.types.Object,
    screen_body: bpy.types.Object,
    screen_rim: bpy.types.Object,
    frames: int,
) -> dict[str, object]:
    contact_root, _ = contact_glow(collection, screen_root, "BreakContact", 0.78, 0.25, 5, frames, 0.34)
    points = hex_points(BODY_RADIUS)
    break_root = event_root(collection, screen_root, "ICE_RIG_MirrorBreak", 0.0, 0.0, -0.04)
    screen_material = screen_body.data.materials[0]
    panel_groups = (
        (points[0], points[1], points[2]),
        (points[2], points[3], points[4]),
        (points[4], points[5], points[0]),
    )
    panel_drifts = ((-0.78, 0.28), (-0.10, -0.85), (0.82, 0.38))
    panel_spins = ((0.18, -0.20, -0.42), (-0.24, 0.16, 0.22), (0.16, 0.25, 0.46))
    panels = [
        make_split_panel(
            collection,
            break_root,
            screen_material,
            f"ICE_MirrorBreakPanel_{index + 1:02d}",
            boundary,
            panel_drifts[index],
            panel_spins[index],
            frames,
        )
        for index, boundary in enumerate(panel_groups)
    ]
    seams = tuple(((0.0, 0.0), points[index]) for index in (0, 2, 4))
    fracture_material = ice_material("MAT_IceBreakPanelSeams", None, (0.42, 0.88, 1.0, 1.0), 0.74)
    seam_obj = make_curve_object(
        "ICE_MirrorBreak_ThreePanelSeams",
        collection,
        break_root,
        [(list(path), False) for path in seams],
        fracture_material,
        0.013,
        "event",
    )
    set_alpha_keys(seam_obj, ((1, 0.0), (4, 0.3), (6, 0.92), (9, 0.72), (12, 0.0), (frames, 0.0)))
    set_alpha_keys(screen_body, ((1, PEAK_OPACITY), (4, PEAK_OPACITY), (7, 0.40), (10, 0.025), (frames, 0.0)))
    set_alpha_keys(screen_rim, ((1, PEAK_OPACITY), (4, PEAK_OPACITY), (6, 0.85), (9, 0.12), (11, 0.0), (frames, 0.0)))

    for index, (dx, dz) in enumerate(((-0.20, 0.14), (0.24, 0.08), (0.02, -0.24)), start=1):
        make_ice_dart(
            collection,
            screen_root,
            f"ICE_MirrorBreakChip_{index:02d}",
            (
                (1, 0.0, 0.0, -0.07, 0.001, index * 0.6),
                (8, dx * 0.25, dz * 0.25, -0.11, 0.38, index * 0.6),
                (17, dx * 0.80, dz * 0.80, -0.20, 0.30, index * 1.1),
                (28, dx * 1.6, dz * 1.6, -0.30, 0.14, index * 1.6),
                (frames, dx * 2.0, dz * 2.0, -0.36, 0.001, index * 2.0),
            ),
            ((1, 0.0), (6, 0.0), (9, 0.82), (18, 0.64), (30, 0.18), (frames, 0.0)),
            (0.44, 0.84, 1.0, 1.0),
        )
    return {"panel_count": len(panels), "chip_count": 3, "seam_count": len(seams), "contact_control": contact_root.name}


def configure_scene(scene: bpy.types.Scene, effect_id: str, frames: int) -> tuple[bpy.types.Object, bpy.types.Object, bpy.types.Object]:
    screen_root = bpy.data.objects.get("ICE_RIG_MirrorScreenDeploy")
    screen_body = bpy.data.objects.get("ICE_MirrorScreen_HexGlass")
    screen_rim = bpy.data.objects.get("ICE_MirrorScreen_HexRim")
    if screen_root is None or screen_body is None or screen_rim is None:
        raise RuntimeError("Saved Ice Mirror idle is missing its single shared hex screen")
    screen_root.animation_data_clear()
    screen_body.animation_data_clear()
    screen_rim.animation_data_clear()
    screen_root.scale = (1.0, 1.0, 1.0)
    screen_body.color = (1.0, 1.0, 1.0, PEAK_OPACITY)
    screen_rim.color = (1.0, 1.0, 1.0, PEAK_OPACITY)
    screen_body["vfx_layer"] = "body"
    screen_rim["vfx_layer"] = "rim"
    screen_root["combat_response"] = effect_id

    for obj in scene.objects:
        layer = obj.get("vfx_layer")
        if layer == "impact":
            obj.hide_render = True
        elif layer in {"crystals", "snowflakes"}:
            obj.hide_render = False
    actor_guides = bpy.data.collections.get("00_Actor_Guide")
    if actor_guides is not None:
        actor_guides.hide_render = True
    scene.frame_start = 1
    scene.frame_end = frames
    scene.render.fps = FPS
    scene.render.fps_base = 1.0
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
    scene.render.filepath = "//"
    scene.view_settings.view_transform = "Standard"
    scene.use_nodes = False
    if scene.camera is None:
        raise RuntimeError("Saved Ice Mirror idle has no camera")
    scene.camera.data.ortho_scale = 5.2
    scene.name = f"SCN_{effect_id}"
    return screen_root, screen_body, screen_rim


def save_and_render(scene: bpy.types.Scene, effect_id: str, frames: int, summary: dict[str, object]) -> None:
    effect_dir = ROOT / "vfx" / effect_id
    blend_path = effect_dir / f"{effect_id}.blend"
    effect_dir.mkdir(parents=True, exist_ok=True)
    scene.frame_set(1)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    for marker in list(scene.timeline_markers):
        scene.timeline_markers.remove(marker)
    for marker_name, frame in summary.get("markers", (("Effect start", 1),)):
        scene.timeline_markers.new(marker_name, frame=frame)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    preview_dir = effect_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for folder in (*[effect_dir / "sequences" / layer for layer in LAYER_IDS], preview_dir):
        folder.mkdir(parents=True, exist_ok=True)
        for stale in folder.glob("*.png"):
            stale.unlink()

    renderables = [obj for obj in scene.objects if obj.get("vfx_layer") in LAYER_IDS]
    for layer_id in LAYER_IDS:
        sequence_dir = effect_dir / "sequences" / layer_id
        for obj in renderables:
            obj.hide_render = obj.get("vfx_layer") != layer_id
        if layer_id == "event" and not any(obj.get("vfx_layer") == "event" for obj in renderables):
            raise RuntimeError(f"{effect_id} has no rendered event objects")
        for frame in range(1, frames + 1):
            scene.frame_set(frame)
            frame_path = sequence_dir / f"{frame:04d}.png"
            scene.render.filepath = str(frame_path.with_suffix(""))
            bpy.ops.render.render(write_still=True)
            if not frame_path.is_file() or frame_path.stat().st_size == 0:
                raise RuntimeError(f"Blender did not render {layer_id} frame {frame}: {frame_path}")

    for obj in renderables:
        obj.hide_render = False
    for frame in range(1, frames + 1):
        scene.frame_set(frame)
        frame_path = preview_dir / f"composite_{frame:04d}.png"
        scene.render.filepath = str(frame_path.with_suffix(""))
        bpy.ops.render.render(write_still=True)
        if not frame_path.is_file() or frame_path.stat().st_size == 0:
            raise RuntimeError(f"Blender did not render composite frame {frame}: {frame_path}")
    scene.frame_set(min(frames, 12))
    scene.render.filepath = "//"
    print(f"{effect_id}: {CELL_SIZE / scene.camera.data.ortho_scale:.1f} px/unit, {frames} frames at {FPS} fps")
    print("ICE_MIRROR_COMBAT_COMPLETE", effect_id, summary)


def build_effect(kind: str) -> dict[str, object]:
    if kind not in EFFECTS:
        raise ValueError(f"Unknown Ice Mirror combat response: {kind}")
    if not IDLE_BLEND.is_file():
        raise FileNotFoundError(f"The saved Ice Mirror idle scene is missing: {IDLE_BLEND}")
    bpy.ops.wm.open_mainfile(filepath=str(IDLE_BLEND))
    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("The saved Ice Mirror idle has no active scene")
    spec = EFFECTS[kind]
    effect_id = spec["id"]
    frames = spec["frames"]
    scene.frame_set(1)

    all_crystals = [obj for obj in scene.objects if obj.get("vfx_layer") == "crystals"]
    heroes = [obj for obj in all_crystals if obj.get("scale_class") == "hero"]
    minors = [obj for obj in all_crystals if obj.get("scale_class") == "minor"]
    snowflakes = [obj for obj in scene.objects if obj.get("vfx_layer") == "snowflakes"]
    if len(heroes) != 3:
        raise RuntimeError(f"Expected exactly three prepared hero crystals; found {len(heroes)}")
    if len(all_crystals) != 8 or len(minors) != 5:
        raise RuntimeError(
            f"Expected three heroes and five minor crystal companions; "
            f"found {len(heroes)} heroes, {len(minors)} minors, {len(all_crystals)} total"
        )
    if len(snowflakes) != 8:
        raise RuntimeError(f"Prepared Ice idle has {len(snowflakes)} snowflakes; expected eight")

    hero_variants = []
    for hero in heroes:
        variant = hero.instance_collection
        if variant is None:
            raise RuntimeError(f"Hero crystal {hero.name} is not a prepared collection instance")
        meshes = [obj for obj in variant.all_objects if obj.type == "MESH" and not obj.hide_render]
        if len(meshes) != 1:
            raise RuntimeError(
                f"Hero variant {variant.name} must contain exactly one rendered crystal mesh; "
                f"found {len(meshes)}"
            )
        hero_variants.append(variant.name)
    if len(set(hero_variants)) != 3:
        raise RuntimeError(f"Expected three distinct prepared hero variants; found {sorted(hero_variants)}")

    screen_root, screen_body, screen_rim = configure_scene(scene, effect_id, frames)
    crystal_speed = retime_idle_bob_drivers(scene)
    crystal_motion = audit_hero_bubble_motion(scene, heroes)
    event_collection = link_collection(f"86_{kind.title()}_Response")
    if kind == "deflect":
        summary = build_deflect(scene, event_collection, screen_root, frames)
    elif kind == "absorb":
        summary = build_absorb(scene, event_collection, screen_root, frames)
    elif kind == "penetrate":
        summary = build_penetrate(scene, event_collection, screen_root, frames)
    else:
        summary = build_break(scene, event_collection, screen_root, screen_body, screen_rim, frames)

    summary.update({
        "hero_crystals": len(heroes),
        "hero_crystal_variants": sorted(hero_variants),
        "hero_motion_audit": crystal_motion,
        "minor_shards": len(minors),
        "snowflakes": len(snowflakes),
        "crystal_driver_time_scale": crystal_speed,
        "markers": spec["markers"],
    })
    scene["design"] = (
        f"Ice Mirror {kind}: built from the saved three-hero idle scene and "
        "its shared cold hex screen; exactly three prepared hero crystals "
        "continue their vertical bubble motion through the response."
    )
    scene["combat_summary"] = str({key: value for key, value in summary.items() if key != "markers"})
    scene["hero_crystals_in_scene"] = len(heroes)
    scene["hero_crystal_motion_real_time"] = crystal_speed
    save_and_render(scene, effect_id, frames, summary)
    return {"effect": effect_id, "frames": frames, "fps": FPS, "blend": str(ROOT / "vfx" / effect_id / f"{effect_id}.blend"), **summary}
