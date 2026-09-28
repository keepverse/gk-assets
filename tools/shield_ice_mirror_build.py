"""Build and render the actor-free Ice Shield three-crystal bubble idle."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from ice_shield_mirror_scene import (  # noqa: E402
    CELL_SIZE,
    EFFECT_DIR,
    EFFECT_BLEND,
    FRAME_COUNT,
    RENDER_SIZE,
    build_idle_scene,
)


def render_sequence() -> dict[str, object]:
    scene = bpy.context.scene
    if Path(bpy.data.filepath).resolve() != EFFECT_BLEND.resolve():
        raise RuntimeError(f"Expected the rebuilt Ice Mirror scene to be open: {EFFECT_BLEND}")
    if scene.camera is None:
        raise RuntimeError("Ice Mirror scene has no camera")

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

    layer_ids = ("crystals", "snowflakes", "body", "rim", "impact")
    preview_dir = EFFECT_DIR / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    for layer_id in layer_ids:
        sequence_dir = EFFECT_DIR / "sequences" / layer_id
        sequence_dir.mkdir(parents=True, exist_ok=True)
        for stale in sequence_dir.glob("*.png"):
            stale.unlink()
    for stale in preview_dir.glob("*.png"):
        stale.unlink()

    layer_objects = [obj for obj in scene.objects if obj.get("vfx_layer")]
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

    scene.frame_set(12)
    scene.render.filepath = "//"
    pixels_per_unit = CELL_SIZE / scene.camera.data.ortho_scale
    print(f"shield_ice_mirror_idle: {pixels_per_unit:.1f} px/unit, {FRAME_COUNT} frames at 12 fps")
    return {"frames": FRAME_COUNT, "resolution": RENDER_SIZE,
            "layers": {layer: str(EFFECT_DIR / "sequences" / layer) for layer in layer_ids}}


def main() -> None:
    build_idle_scene()
    result = render_sequence()
    print("ICE_MIRROR_IDLE_BUILD_COMPLETE", result)


if __name__ == "__main__":
    main()
