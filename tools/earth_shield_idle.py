"""Build the Earth Shield's reusable, looping idle dome animation."""

from __future__ import annotations

import math
import os
from pathlib import Path

import bpy


def find_repo_root() -> Path:
    candidates: list[Path] = []
    script_path = globals().get("__file__")
    if script_path:
        candidates.append(Path(script_path).resolve())
    if bpy.data.filepath:
        candidates.append(Path(bpy.data.filepath).resolve())
    candidates.append(Path.cwd().resolve())
    for candidate in candidates:
        for parent in (candidate, *candidate.parents):
            if (parent / "assets" / "vfx" / "earth_shield").is_dir():
                return parent
    raise RuntimeError("Could not locate gk-assets from this script, the open .blend, or Blender's working directory")


ROOT = find_repo_root()
ASSET_DIR = ROOT / "assets" / "vfx" / "earth_shield"
BASE_BLEND = ASSET_DIR / "earth_shield_orbit.blend"
EFFECT_DIR = ROOT / "vfx" / "shield_earth_idle"
OUTPUT_BLEND = EFFECT_DIR / "shield_earth_idle.blend"

DOME_RADIUS = 2.30
DOME_SEGMENTS = 96
DOME_RINGS = 48


def ensure_orbit_scene() -> None:
    """Load the orbit source when this script starts in an empty Blender file."""
    has_orbit = bpy.data.objects.get("ES_Shield_OrbitRoot") is not None
    has_material = bpy.data.materials.get("M_ES_DomeShell") is not None
    if has_orbit and has_material:
        return
    if not BASE_BLEND.is_file():
        raise FileNotFoundError(f"Earth Shield orbit source not found: {BASE_BLEND}")
    bpy.ops.wm.open_mainfile(filepath=str(BASE_BLEND))


def collection_named(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.get(name)
    if collection is None:
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)
    return collection


def remove_old_idle_objects() -> None:
    for name in ("ES_EarthShield_DomeShell", "ES_Shield_IdleControl"):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Curve):
                    bpy.data.curves.remove(data)


def make_dome_mesh() -> bpy.types.Mesh:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    for ring in range(DOME_RINGS + 1):
        elevation = (math.pi * 0.5) * ring / DOME_RINGS
        ring_radius = DOME_RADIUS * math.cos(elevation)
        height = DOME_RADIUS * math.sin(elevation)
        for segment in range(DOME_SEGMENTS):
            angle = math.tau * segment / DOME_SEGMENTS
            vertices.append((ring_radius * math.cos(angle), ring_radius * math.sin(angle), height))

    for ring in range(DOME_RINGS):
        lower = ring * DOME_SEGMENTS
        upper = (ring + 1) * DOME_SEGMENTS
        for segment in range(DOME_SEGMENTS):
            next_segment = (segment + 1) % DOME_SEGMENTS
            faces.append((
                lower + segment,
                lower + next_segment,
                upper + next_segment,
                upper + segment,
            ))

    mesh = bpy.data.meshes.new("ES_EarthShield_DomeShell_Mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    return mesh


def add_driver(material: bpy.types.Material, node_name: str, control: bpy.types.Object, prop: str) -> None:
    tree = material.node_tree
    socket_path = f'nodes["{node_name}"].outputs[0].default_value'
    curve = tree.driver_add(socket_path)
    driver = curve.driver
    driver.type = "SCRIPTED"
    driver.expression = "value"
    variable = driver.variables.new()
    variable.name = "value"
    variable.type = "SINGLE_PROP"
    variable.targets[0].id = control
    variable.targets[0].data_path = f'["{prop}"]'


def animate_control(control: bpy.types.Object, prop: str, keys: tuple[tuple[int, float], ...]) -> None:
    for frame, value in keys:
        control[prop] = value
        control.keyframe_insert(data_path=f'["{prop}"]', frame=frame, group="Earth Shield Idle")


def build_idle() -> dict[str, object]:
    ensure_orbit_scene()
    scene = bpy.context.scene
    material = bpy.data.materials.get("M_ES_DomeShell")
    if material is None or not material.use_nodes:
        raise RuntimeError("M_ES_DomeShell is missing or has no node tree")

    remove_old_idle_objects()
    actor_collection = bpy.data.collections.get("00_Actor_Guide")
    if actor_collection is not None:
        actor_collection.hide_render = True
    shell_collection = collection_named("30_Transparent_Dome")
    rig_collection = collection_named("85_Orbit_Rig")

    dome = bpy.data.objects.new("ES_EarthShield_DomeShell", make_dome_mesh())
    shell_collection.objects.link(dome)
    dome.data.materials.append(material)
    dome["role"] = "animated transparent Earth Shield dome shell"
    dome["radius"] = DOME_RADIUS
    dome["surface"] = "open hemisphere; bottom-up world-Z reveal"

    control = bpy.data.objects.new("ES_Shield_IdleControl", None)
    rig_collection.objects.link(control)
    control.empty_display_type = "CIRCLE"
    control.empty_display_size = 0.22
    control["role"] = "Earth Shield idle animation and material driver controls"

    keyframes = {
        "reveal_height": (
            (1, -0.06), (3, 0.045), (32, DOME_RADIUS),
            (82, DOME_RADIUS), (106, -0.06), (145, -0.06),
        ),
        "front_opacity": (
            (1, 0.0), (3, 0.40), (29, 0.40), (35, 0.025),
            (82, 0.025), (86, 0.40), (103, 0.40), (109, 0.0), (145, 0.0),
        ),
        "front_glow": (
            (1, 0.05), (3, 1.60), (21, 1.60), (32, 1.20), (36, 0.08),
            (82, 0.08), (86, 1.50), (104, 1.50), (110, 0.05), (145, 0.05),
        ),
        "idle_phase": (
            (1, 0.0), (32, 0.0), (55, 0.45), (82, 0.85),
            (106, 0.85), (145, 0.0),
        ),
        "idle_rim": (
            (1, 0.22), (32, 0.22), (42, 0.29), (53, 0.21),
            (63, 0.30), (73, 0.22), (82, 0.27), (106, 0.22), (145, 0.22),
        ),
    }
    for prop, keys in keyframes.items():
        animate_control(control, prop, keys)

    # Clear only prior drivers from this reusable material before rebinding it.
    if material.node_tree.animation_data is not None:
        material.node_tree.animation_data_clear()
    add_driver(material, "ES_RevealHeight", control, "reveal_height")
    add_driver(material, "ES_FrontOpacity", control, "front_opacity")
    add_driver(material, "ES_FrontGlowStrength", control, "front_glow")
    add_driver(material, "ES_IdlePhase", control, "idle_phase")
    add_driver(material, "ES_IdleRimGlow", control, "idle_rim")

    scene.frame_start = 1
    scene.frame_end = 144
    scene.render.fps = 24
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = "//"
    scene.render.use_file_extension = True
    scene.frame_set(52)
    if scene.camera is not None:
        scene.camera.data.ortho_scale = 5.6

    for marker_name, frame in (
        ("Reveal from ground", 3),
        ("Fully formed / idle", 32),
        ("Retract from crown", 86),
        ("Inactive / loop rest", 110),
        ("Loop wrap", 145),
    ):
        if scene.timeline_markers.get(marker_name) is not None:
            scene.timeline_markers.remove(scene.timeline_markers[marker_name])
        scene.timeline_markers.new(marker_name, frame=frame)

    EFFECT_DIR.mkdir(parents=True, exist_ok=True)
    texture_paths: dict[str, Path] = {}
    for image in bpy.data.images:
        if image.source != "FILE":
            continue
        image_path = Path(bpy.path.abspath(image.filepath)).resolve()
        if image_path.is_relative_to(ASSET_DIR / "textures"):
            texture_paths[image.name] = image_path

    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    # Blender resolves // paths against the current .blend before remapping on
    # save_as_mainfile. Set the final relative paths only after the new scene
    # path is active, so they resolve from vfx/shield_earth_idle/.
    for image_name, image_path in texture_paths.items():
        relative = os.path.relpath(image_path, EFFECT_DIR).replace("\\", "/")
        bpy.data.images[image_name].filepath = f"//{relative}"
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    return {
        "status": "built",
        "blend": str(OUTPUT_BLEND),
        "dome": dome.name,
        "dome_radius": DOME_RADIUS,
        "dome_faces": len(dome.data.polygons),
        "frames": scene.frame_end - scene.frame_start + 1,
        "fps": scene.render.fps,
        "cycle_seconds": (scene.frame_end - scene.frame_start + 1) / scene.render.fps,
        "orbit_rocks": sum(1 for obj in scene.objects if obj.get("role") == "independent orbiting hero stone"),
        "orbit_chips": sum(1 for obj in scene.objects if obj.get("role") == "small trailing orbit fragment"),
        "shader_drivers": 5,
    }


result = build_idle()
print("EARTH_SHIELD_IDLE_BUILD_COMPLETE", result)
