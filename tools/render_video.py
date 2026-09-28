"""Render a Blender scene to a local H.264 MP4 review video.

Run from normal Python with a .blend path. Blender re-runs this same script in
background mode to render, so the scene is never saved or modified by export.
"""

from __future__ import annotations

import argparse
from collections import deque
import shutil
import subprocess
import sys
import tempfile
from threading import Thread
from pathlib import Path

try:
    import bpy  # type: ignore[import-not-found]
except ImportError:
    bpy = None


ROOT = Path(__file__).resolve().parents[1]
COMPLETE_MARKER = "REVIEW_VIDEO_RENDER_COMPLETE"


def worker_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Blender-side video render options")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--fps", type=int)
    parser.add_argument("--resolution-scale", type=int, default=100)
    return parser


def render_inside_blender(argv: list[str]) -> int:
    args = worker_parser().parse_args(argv)
    scene = bpy.context.scene
    if scene is None:
        raise RuntimeError("The loaded Blender file has no active scene")

    output = args.output.expanduser().resolve()
    if output.suffix.lower() != ".mp4":
        raise ValueError("Video output must use the .mp4 extension")
    if args.resolution_scale < 1 or args.resolution_scale > 100:
        raise ValueError("--resolution-scale must be between 1 and 100")

    start = scene.frame_start if args.start is None else args.start
    end = scene.frame_end if args.end is None else args.end
    if start < 0 or end < start:
        raise ValueError(f"Invalid frame range: {start}..{end}")

    output.parent.mkdir(parents=True, exist_ok=True)
    scene.frame_start = start
    scene.frame_end = end
    if args.fps is not None:
        if args.fps < 1 or args.fps > 240:
            raise ValueError("--fps must be between 1 and 240")
        scene.render.fps = args.fps
        scene.render.fps_base = 1.0
    scene.render.resolution_percentage = args.resolution_scale
    scene.render.use_overwrite = True

    try:
        scene.render.image_settings.file_format = "FFMPEG"
    except TypeError:
        scene.render.image_settings.file_format = "PNG"
        ffmpeg_exe = shutil.which("ffmpeg")
        if not ffmpeg_exe:
            raise RuntimeError(
                "This Blender build has no movie encoder and ffmpeg is not on PATH; "
                "install FFmpeg or use a Blender build with FFmpeg support"
            )

        fps = scene.render.fps / scene.render.fps_base
        with tempfile.TemporaryDirectory(prefix="gk_blender_video_") as temp_dir:
            frame_dir = Path(temp_dir)
            frame_prefix = frame_dir / "frame_"
            scene.render.filepath = str(frame_prefix)
            scene.render.use_file_extension = True
            scene.render.image_settings.file_format = "PNG"
            scene.render.image_settings.color_mode = "RGB"
            scene.render.image_settings.color_depth = "8"
            bpy.ops.render.render(animation=True)

            frames = list(frame_dir.glob("frame_*.png"))
            expected_frames = end - start + 1
            if len(frames) != expected_frames:
                raise RuntimeError(
                    f"Blender rendered {len(frames)} PNG frames; expected {expected_frames}"
                )

            command = [
                ffmpeg_exe, "-y", "-hide_banner", "-loglevel", "error",
                "-framerate", f"{fps:.6f}", "-start_number", str(start),
                "-i", str(frame_dir / "frame_%04d.png"),
                "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
            ]
            encoded = subprocess.run(command, capture_output=True, text=True, timeout=600)
            if encoded.returncode != 0:
                raise RuntimeError(f"FFmpeg encoding failed: {encoded.stderr.strip()}")
    else:
        scene.render.filepath = str(output)
        scene.render.use_file_extension = False
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
        scene.render.ffmpeg.ffmpeg_preset = "GOOD"
        scene.render.ffmpeg.audio_codec = "NONE"
        bpy.ops.render.render(animation=True)

    if not output.is_file():
        # Some Blender builds append the container suffix even when the path
        # already contains one; normalize that result to the requested path.
        appended = Path(str(output) + ".mp4")
        if appended.is_file():
            appended.replace(output)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"Blender finished without creating a video at {output}")
    print(f"{COMPLETE_MARKER} path={output} bytes={output.stat().st_size}", flush=True)
    return 0


def cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, required=True, help="source .blend file")
    parser.add_argument("--output", type=Path, help="MP4 path (default: tmp/video/<blend>.mp4)")
    parser.add_argument("--start", type=int, help="first frame; defaults to the scene range")
    parser.add_argument("--end", type=int, help="last frame; defaults to the scene range")
    parser.add_argument("--fps", type=int, help="override the scene frame rate")
    parser.add_argument("--resolution-scale", type=int, default=100,
                        help="render percentage from 1 to 100 (default: 100)")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Blender render timeout in seconds (default: 1800)")
    return parser


def launch_from_python(argv: list[str]) -> int:
    args = cli_parser().parse_args(argv)
    blend = args.blend.expanduser().resolve()
    if blend.suffix.lower() != ".blend" or not blend.is_file():
        print(f"Blender source file not found: {blend}", file=sys.stderr)
        return 2
    if args.timeout < 1:
        print("--timeout must be positive", file=sys.stderr)
        return 2

    output = args.output.expanduser().resolve() if args.output else ROOT / "tmp" / "video" / f"{blend.stem}.mp4"
    if output.suffix.lower() != ".mp4":
        print("Video output must use the .mp4 extension", file=sys.stderr)
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from blender_path import blender_exe

    command = [
        blender_exe(), "--background", str(blend), "--python", str(Path(__file__).resolve()), "--",
        "--output", str(output), "--resolution-scale", str(args.resolution_scale),
    ]
    for name in ("start", "end", "fps"):
        value = getattr(args, name)
        if value is not None:
            command.extend((f"--{name}", str(value)))

    print(f"Blender: {command[0]}", flush=True)
    print(f"Source: {blend}", flush=True)
    print(f"Output: {output}", flush=True)
    tail: deque[str] = deque(maxlen=40)
    try:
        process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None

        def report_output() -> None:
            assert process.stdout is not None
            for line in process.stdout:
                tail.append(line.rstrip())
                stripped = line.strip()
                if stripped.startswith(("Fra:", "Saved:", "Error", "ERROR", "Warning", COMPLETE_MARKER)):
                    print(stripped, flush=True)

        reader = Thread(target=report_output, daemon=True)
        reader.start()
        try:
            return_code = process.wait(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            reader.join(timeout=5)
            print(f"Blender render timed out after {args.timeout}s", file=sys.stderr)
            return 1
        reader.join()
    except OSError as exc:
        print(f"Could not launch Blender: {exc}", file=sys.stderr)
        return 1

    completed = any(COMPLETE_MARKER in line for line in tail)
    if return_code != 0 or not completed or not output.is_file() or output.stat().st_size == 0:
        print("Video render failed; Blender output follows:", file=sys.stderr)
        print("\n".join(tail), file=sys.stderr)
        return 1
    print(f"Rendered {output} ({output.stat().st_size:,} bytes)")
    return 0


def main() -> int:
    if bpy is not None:
        args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
        return render_inside_blender(args)
    return launch_from_python(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
