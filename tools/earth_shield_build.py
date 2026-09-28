"""Render the actor-free Earth Shield idle scene to its 12 fps sprite sequence."""

from __future__ import annotations

from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
EFFECT_DIR = ROOT / "vfx" / "shield_earth_idle"
SCENE_BLEND = EFFECT_DIR / "shield_earth_idle.blend"
SEQUENCE_DIR = EFFECT_DIR / "sequences" / "earth"

SOURCE_FPS = 24
SOURCE_FRAMES = 144
SOURCE_STRIDE = 2
RENDER_SIZE = 512
GAMEPLAY_CELL = 128


def render_sequence() -> dict[str, object]:
    if not SCENE_BLEND.is_file():
        raise FileNotFoundError(f"Earth Shield production scene not found: {SCENE_BLEND}")
    bpy.ops.wm.open_mainfile(filepath=str(SCENE_BLEND))
    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("Earth Shield scene has no active scene")
    if scene.render.fps != SOURCE_FPS or scene.frame_end != SOURCE_FRAMES:
        raise RuntimeError(
            f"Expected a {SOURCE_FRAMES}-frame, {SOURCE_FPS} fps source scene; "
            f"got {scene.frame_end} frames at {scene.render.fps} fps"
        )

    actor_guides = bpy.data.collections.get("00_Actor_Guide")
    if actor_guides is not None:
        actor_guides.hide_render = True
    for obj in scene.objects:
        if obj.get("role", "").startswith("non-production actor"):
            obj.hide_render = True

    if scene.camera is None:
        raise RuntimeError("Earth Shield scene has no camera")
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = RENDER_SIZE
    scene.render.resolution_y = RENDER_SIZE
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.render.use_file_extension = True
    scene.render.use_overwrite = True

    SEQUENCE_DIR.mkdir(parents=True, exist_ok=True)
    for stale in SEQUENCE_DIR.glob("frame_*.png"):
        stale.unlink()

    sample_frames = range(1, SOURCE_FRAMES + 1, SOURCE_STRIDE)
    rendered = 0
    for index, source_frame in enumerate(sample_frames, start=1):
        scene.frame_set(source_frame)
        scene.render.filepath = str(SEQUENCE_DIR / f"frame_{index:04d}")
        bpy.ops.render.render(write_still=True)
        output = SEQUENCE_DIR / f"frame_{index:04d}.png"
        if not output.is_file() or output.stat().st_size == 0:
            raise RuntimeError(f"Blender did not write frame {index}: {output}")
        rendered += 1

    if rendered != SOURCE_FRAMES // SOURCE_STRIDE:
        raise RuntimeError(f"Rendered {rendered} frames; expected 72")
    print(
        "EARTH_SHIELD_BUILD_COMPLETE "
        f"{rendered} frames, {RENDER_SIZE}px renders, {GAMEPLAY_CELL}px/unit gameplay cells"
    )
    return {
        "frames": rendered,
        "source_stride": SOURCE_STRIDE,
        "fps": SOURCE_FPS // SOURCE_STRIDE,
        "resolution": RENDER_SIZE,
        "sequence": str(SEQUENCE_DIR),
    }


result = render_sequence()
print("EARTH_SHIELD_RENDER_RESULT", result)
