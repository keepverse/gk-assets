"""Generate deterministic, seamless PBR textures for the Ice Shield mirror kit.

Run from the repository root:
    python tools/generate_ice_mirror_textures.py
    python tools/generate_ice_mirror_textures.py --size 2048

The source maps go beside the reusable Ice Shield objects at
assets/vfx/ice_shield/textures/mirror_v1/. A review contact sheet is written to
the ignored assets/vfx/ice_shield/lookdev/ directory.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "assets" / "vfx" / "ice_shield" / "textures" / "mirror_v1"
PREVIEW_PATH = ROOT / "assets" / "vfx" / "ice_shield" / "lookdev" / "ice_mirror_texture_preview.png"
MAP_NAMES = ("BaseColor", "NormalGL", "Roughness", "Emission", "Height")
OBJECTS = (
    ("MirrorFace", "mirror_face", 1801),
    ("PrismFrame", "frame", 2903),
    ("GuardShard", "shard", 3719),
)


def smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    t = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def periodic_noise(size: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Bilinearly interpolated value noise with matching opposite edges."""
    lattice = rng.random((cells, cells), dtype=np.float32)
    coord = np.arange(size, dtype=np.float32) * (cells / size)
    base = np.floor(coord).astype(np.int32)
    frac = coord - base
    frac = frac * frac * (3.0 - 2.0 * frac)
    x0, x1 = base % cells, (base + 1) % cells
    y0, y1 = x0, x1
    top = lattice[y0[:, None], x0[None, :]] * (1.0 - frac[None, :]) + lattice[
        y0[:, None], x1[None, :]
    ] * frac[None, :]
    bottom = lattice[y1[:, None], x0[None, :]] * (1.0 - frac[None, :]) + lattice[
        y1[:, None], x1[None, :]
    ] * frac[None, :]
    return (top * (1.0 - frac[:, None]) + bottom * frac[:, None]).astype(np.float32)


def fractal_noise(size: int, seed: int, octaves: tuple[tuple[int, float], ...]) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = np.zeros((size, size), dtype=np.float32)
    weight_sum = 0.0
    for cells, weight in octaves:
        total += periodic_noise(size, cells, rng) * weight
        weight_sum += weight
    return total / weight_sum


def cellular_facets(size: int, cells: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Periodic broad facets, seam proximity, and a per-facet value."""
    rng = np.random.default_rng(seed)
    jitter = rng.uniform(0.18, 0.82, (cells, cells, 2)).astype(np.float32)
    tones = rng.uniform(0.20, 0.92, (cells, cells)).astype(np.float32)
    axis = np.arange(size, dtype=np.float32) * (cells / size)
    gx = np.floor(axis).astype(np.int32)
    gy = gx
    px, py = axis[None, :], axis[:, None]
    nearest = np.full((size, size), np.inf, dtype=np.float32)
    second = np.full_like(nearest, np.inf)
    face_tone = np.zeros_like(nearest)

    for oy in (-1, 0, 1):
        cy = (gy + oy) % cells
        for ox in (-1, 0, 1):
            cx = (gx + ox) % cells
            fx = gx[None, :] + ox + jitter[cy[:, None], cx[None, :], 0]
            fy = gy[:, None] + oy + jitter[cy[:, None], cx[None, :], 1]
            distance = (px - fx) ** 2 + (py - fy) ** 2
            closer = distance < nearest
            second = np.where(closer, nearest, np.minimum(second, distance))
            nearest = np.minimum(nearest, distance)
            face_tone = np.where(closer, tones[cy[:, None], cx[None, :]], face_tone)

    gap = np.sqrt(second) - np.sqrt(nearest)
    edge = 1.0 - smoothstep(0.018, 0.095, gap)
    face_distance = np.sqrt(nearest) / 0.72
    return np.clip(face_tone, 0.0, 1.0), edge, np.clip(face_distance, 0.0, 1.0)


def palette(value: np.ndarray, stops: tuple[tuple[float, tuple[int, int, int]], ...]) -> np.ndarray:
    color = np.empty((*value.shape, 3), dtype=np.float32)
    for channel in range(3):
        color[..., channel] = np.interp(
            value,
            [stop[0] for stop in stops],
            [stop[1][channel] for stop in stops],
        )
    return color


def as_u8(value: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(value), 0, 255).astype(np.uint8)


def make_normal(height: np.ndarray, strength: float) -> np.ndarray:
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
    nx, ny, nz = -dx * strength, -dy * strength, np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    return (np.stack((nx / length, ny / length, nz / length), axis=-1) + 1.0) * 127.5


def make_maps(size: int, seed: int, kind: str) -> dict[str, np.ndarray]:
    broad = fractal_noise(size, seed, ((3, 0.52), (6, 0.30), (12, 0.18)))
    medium = fractal_noise(size, seed + 11, ((12, 0.50), (24, 0.32), (48, 0.18)))
    fine = fractal_noise(size, seed + 23, ((48, 0.52), (96, 0.30), (192, 0.18)))
    vein_field = fractal_noise(size, seed + 37, ((5, 0.56), (10, 0.29), (20, 0.15)))
    branch = fractal_noise(size, seed + 53, ((10, 0.58), (20, 0.29), (40, 0.13)))

    facet_size = min(size, 256)
    facet_cells = {"mirror_face": 7, "frame": 12, "shard": 8}[kind]
    tone, facet_edges, face_distance = cellular_facets(facet_size, facet_cells, seed + 71)
    if facet_size != size:
        def enlarge(field: np.ndarray, mode: Image.Resampling) -> np.ndarray:
            src = Image.fromarray(as_u8(field * 255.0), mode="L")
            return np.asarray(src.resize((size, size), mode), dtype=np.float32) / 255.0

        tone = enlarge(tone, Image.Resampling.NEAREST)
        facet_edges = enlarge(facet_edges, Image.Resampling.BILINEAR)
        face_distance = enlarge(face_distance, Image.Resampling.BILINEAR)

    # Noise contours make branching frost veins. The branch field keeps the
    # pattern broken and prevents a uniformly outlined, tiled-crack look.
    veins = 1.0 - smoothstep(0.009, 0.034, np.abs(vein_field - 0.5))
    veins *= 0.25 + 0.75 * smoothstep(0.32, 0.72, branch)
    bright_facet = smoothstep(0.60, 0.90, tone)
    grain = (fine - 0.5) * 10.0

    if kind == "mirror_face":
        value = np.clip(0.15 + tone * 0.48 + broad * 0.22 + medium * 0.15, 0.0, 1.0)
        color = palette(
            value,
            ((0.0, (14, 36, 75)), (0.25, (25, 70, 116)), (0.52, (54, 130, 176)),
             (0.78, (128, 202, 226)), (1.0, (218, 247, 253))),
        )
        line = np.maximum(veins * 0.78, facet_edges * bright_facet * 0.50)
        color = color * (1.0 - line[..., None] * 0.76) + np.array((176, 244, 255), dtype=np.float32) * line[..., None] * 0.76
        height = 0.42 + (tone - 0.5) * 0.095 + broad * 0.035 + medium * 0.014 + line * 0.025
        roughness = 0.16 + 0.12 * (1.0 - tone) + 0.24 * veins + 0.04 * fine
        emission = np.clip(veins * 0.58 + facet_edges * bright_facet * 0.25, 0.0, 0.82)
        normal_strength = 15.0

    elif kind == "frame":
        value = np.clip(0.12 + tone * 0.56 + broad * 0.20 + medium * 0.12, 0.0, 1.0)
        color = palette(
            value,
            ((0.0, (10, 31, 67)), (0.28, (18, 62, 111)), (0.58, (31, 117, 165)),
             (0.82, (95, 193, 220)), (1.0, (192, 240, 250))),
        )
        line = np.maximum(facet_edges * 0.72, veins * 0.32)
        color = color * (1.0 - line[..., None] * 0.70) + np.array((102, 218, 246), dtype=np.float32) * line[..., None] * 0.70
        height = 0.40 + (tone - 0.5) * 0.14 + broad * 0.04 + medium * 0.02 + line * 0.018
        roughness = 0.22 + 0.12 * (1.0 - tone) + 0.12 * veins + 0.04 * fine
        emission = np.clip(facet_edges * 0.31 + veins * 0.22, 0.0, 0.60)
        normal_strength = 19.0

    elif kind == "shard":
        value = np.clip(0.13 + tone * 0.50 + broad * 0.24 + medium * 0.13, 0.0, 1.0)
        color = palette(
            value,
            ((0.0, (13, 42, 85)), (0.28, (30, 79, 135)), (0.58, (62, 146, 191)),
             (0.82, (140, 213, 232)), (1.0, (224, 247, 252))),
        )
        line = np.maximum(veins * 0.52, facet_edges * bright_facet * 0.72)
        color = color * (1.0 - line[..., None] * 0.62) + np.array((157, 234, 250), dtype=np.float32) * line[..., None] * 0.62
        height = 0.40 + (tone - 0.5) * 0.12 + broad * 0.05 + medium * 0.02 + line * 0.02
        roughness = 0.19 + 0.13 * (1.0 - tone) + 0.18 * veins + 0.04 * fine
        emission = np.clip(veins * 0.28 + facet_edges * bright_facet * 0.38, 0.0, 0.72)
        normal_strength = 18.0
    else:
        raise ValueError(f"Unknown Ice Shield mirror texture type: {kind}")

    color = np.clip(color + grain[..., None], 0.0, 255.0)
    height = np.clip(height + (fine - 0.5) * 0.018 + (face_distance - 0.45) * 0.008, 0.0, 1.0)
    roughness = np.clip(roughness, 0.12, 0.68)
    return {
        "BaseColor": color,
        "NormalGL": make_normal(height, normal_strength),
        "Roughness": roughness * 255.0,
        "Emission": np.repeat((emission * 255.0)[..., None], 3, axis=2),
        "Height": height * 255.0,
    }


def save_map(path: Path, map_name: str, pixels: np.ndarray) -> None:
    if map_name in {"BaseColor", "NormalGL", "Emission"}:
        Image.fromarray(as_u8(pixels), mode="RGB").save(path, optimize=True)
    else:
        Image.fromarray(as_u8(pixels), mode="L").save(path, optimize=True)


def generate(output: Path, size: int, seed_offset: int = 0, preview_path: Path = PREVIEW_PATH) -> None:
    output.mkdir(parents=True, exist_ok=True)
    thumb = 256
    gutter, label_w, header_h = 12, 104, 30
    width = gutter + label_w + len(MAP_NAMES) * (thumb + gutter)
    height = header_h + gutter + len(OBJECTS) * (thumb + gutter)
    sheet = Image.new("RGB", (width, height), (10, 19, 35))
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    for col, map_name in enumerate(MAP_NAMES):
        x = gutter + label_w + col * (thumb + gutter)
        draw.text((x, 9), map_name, fill=(125, 187, 218), font=font)

    for row, (name, kind, seed) in enumerate(OBJECTS):
        maps = make_maps(size, seed + seed_offset, kind)
        y = header_h + gutter + row * (thumb + gutter)
        draw.text((gutter, y + 10), name, fill=(203, 232, 246), font=font)
        for col, map_name in enumerate(MAP_NAMES):
            path = output / f"T_IceShield_{name}_{map_name}.png"
            save_map(path, map_name, maps[map_name])
            pixels = as_u8(maps[map_name])
            mode = "RGB" if pixels.ndim == 3 else "L"
            preview = Image.fromarray(pixels, mode=mode).convert("RGB")
            preview.thumbnail((thumb, thumb), Image.Resampling.LANCZOS)
            x = gutter + label_w + col * (thumb + gutter)
            sheet.paste(preview, (x, y))
            print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)

    preview_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(preview_path, optimize=True)
    print(f"preview: {preview_path.relative_to(ROOT) if preview_path.is_relative_to(ROOT) else preview_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=1024, help="square map size (default: 1024)")
    parser.add_argument("--seed-offset", type=int, default=0, help="reproducible variation applied to all maps")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="source texture output directory")
    parser.add_argument("--preview", type=Path, default=PREVIEW_PATH, help="review contact sheet path")
    args = parser.parse_args()
    if args.size < 256 or args.size > 4096 or args.size & (args.size - 1):
        parser.error("--size must be a power of two from 256 through 4096")
    generate(args.out.resolve(), args.size, args.seed_offset, args.preview.resolve())


if __name__ == "__main__":
    main()
