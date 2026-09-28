"""Generate deterministic, seamless PBR texture sets for the Earth Shield kit.

Run from the repository root:
    python tools/generate_earth_shield_textures.py
    python tools/generate_earth_shield_textures.py --size 2048

The source textures are written beside the future reusable Blender objects at
assets/vfx/earth_shield/textures/.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "assets" / "vfx" / "earth_shield" / "textures"


def smoothstep(edge0: float, edge1: float, value: np.ndarray) -> np.ndarray:
    """Cubic transition with a useful, explicit range."""
    t = np.clip((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def periodic_noise(size: int, cells: int, rng: np.random.Generator) -> np.ndarray:
    """Bilinearly interpolated value noise whose opposite edges tile exactly."""
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


def fractal_noise(
    size: int, seed: int, octaves: tuple[tuple[int, float], ...]
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    total = np.zeros((size, size), dtype=np.float32)
    weight_sum = 0.0
    for cells, weight in octaves:
        total += periodic_noise(size, cells, rng) * weight
        weight_sum += weight
    total /= weight_sum
    return total


def cellular_rock(size: int, cells: int, seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Periodic Voronoi facets, their fractured borders, and per-face variation."""
    rng = np.random.default_rng(seed)
    jitter = rng.uniform(0.16, 0.84, (cells, cells, 2)).astype(np.float32)
    face_tones = rng.uniform(0.28, 0.72, (cells, cells)).astype(np.float32)
    axis = np.arange(size, dtype=np.float32) * (cells / size)
    gx = np.floor(axis).astype(np.int32)
    gy = gx
    px = axis[None, :]
    py = axis[:, None]
    nearest = np.full((size, size), np.inf, dtype=np.float32)
    second = np.full_like(nearest, np.inf)
    face = np.zeros_like(nearest)

    # Only the surrounding 3x3 feature cells can own a point in this cell.
    # The wrapped feature lookup keeps the entire field seamless.
    for oy in (-1, 0, 1):
        cy = (gy + oy) % cells
        for ox in (-1, 0, 1):
            cx = (gx + ox) % cells
            feature_x = gx[None, :] + ox + jitter[cy[:, None], cx[None, :], 0]
            feature_y = gy[:, None] + oy + jitter[cy[:, None], cx[None, :], 1]
            dx = px - feature_x
            dy = py - feature_y
            distance = dx * dx + dy * dy
            closer = distance < nearest
            second = np.where(closer, nearest, np.minimum(second, distance))
            nearest = np.minimum(nearest, distance)
            face = np.where(closer, face_tones[cy[:, None], cx[None, :]], face)

    # Distances are in cell units; converting them keeps palette mixing
    # comparable as the facet count changes between rock types.
    nearest_distance = np.sqrt(nearest) / 0.72
    border_gap = np.sqrt(second) - np.sqrt(nearest)
    edge = 1.0 - smoothstep(0.025, 0.12, border_gap)
    return np.clip(nearest_distance, 0.0, 1.0), edge, face


def palette(value: np.ndarray, stops: tuple[tuple[float, tuple[int, int, int]], ...]) -> np.ndarray:
    """Interpolate an sRGB palette over a 0..1 geology field."""
    result = np.empty((*value.shape, 3), dtype=np.float32)
    for channel in range(3):
        result[..., channel] = np.interp(
            value,
            [stop[0] for stop in stops],
            [stop[1][channel] for stop in stops],
        )
    return result


def as_u8(value: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(value), 0, 255).astype(np.uint8)


def save_rgb(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(as_u8(pixels), mode="RGB").save(path, optimize=True)


def save_gray(path: Path, pixels: np.ndarray) -> None:
    Image.fromarray(as_u8(pixels), mode="L").save(path, optimize=True)


def make_maps(size: int, seed: int, kind: str) -> dict[str, np.ndarray]:
    broad = fractal_noise(size, seed, ((3, 0.48), (6, 0.30), (12, 0.15), (24, 0.07)))
    medium = fractal_noise(size, seed + 11, ((12, 0.46), (24, 0.32), (48, 0.22)))
    fine = fractal_noise(size, seed + 23, ((48, 0.48), (96, 0.34), (192, 0.18)))
    seam_field = fractal_noise(size, seed + 37, ((5, 0.58), (10, 0.29), (20, 0.13)))
    veins = 1.0 - smoothstep(0.012, 0.042, np.abs(seam_field - 0.5))
    flecks = smoothstep(0.54, 0.78, fine)
    facet_cells = {"basalt": 16, "sandstone": 12, "mossstone": 14, "quartz": 18}[kind]
    # Facet ownership only changes across a few dozen broad stone planes. Bake
    # that field at 256px and enlarge it; the full-resolution noise and seams
    # below retain fine detail without paying for a million Voronoi queries.
    facet_size = min(size, 256)
    face_distance, face_edges, face_tone = cellular_rock(facet_size, facet_cells, seed + 71)
    if facet_size != size:
        def enlarge(field: np.ndarray, resample: Image.Resampling) -> np.ndarray:
            # Pillow's float-mode resize can produce NaNs on some Windows/Pillow
            # builds. These normalized fields tolerate 8-bit interpolation.
            source = Image.fromarray(as_u8(field * 255.0), mode="L")
            enlarged = source.resize((size, size), resample)
            return np.asarray(enlarged, dtype=np.float32) / 255.0

        face_distance = enlarge(face_distance, Image.Resampling.BILINEAR)
        face_edges = enlarge(face_edges, Image.Resampling.BILINEAR)
        face_tone = enlarge(face_tone, Image.Resampling.NEAREST)

    # Creases follow noisy mineral boundaries; flecks break long lines into
    # shorter, less regular seams. Voronoi borders give the stone broad chipped
    # faces; both fields wrap across UV edges.
    fractures = np.maximum(veins * (0.58 + 0.42 * flecks), face_edges * 0.46)
    height = 0.22 + 0.35 * broad + 0.25 * medium + 0.10 * fine
    height += (face_tone - 0.5) * 0.19 - fractures * 0.10

    if kind == "basalt":
        color = palette(
            0.15 + 0.70 * broad + 0.15 * medium,
            ((0.0, (29, 32, 32)), (0.38, (48, 51, 49)), (0.70, (79, 73, 63)), (1.0, (123, 105, 82))),
        )
        seam_color = np.array((151.0, 105.0, 57.0), dtype=np.float32)
        color = color * (1.0 - fractures[..., None] * 0.52) + seam_color * fractures[..., None] * 0.52
        height -= fractures * 0.035
        roughness = 0.68 + 0.16 * medium + 0.08 * fine - fractures * 0.09
        normal_strength = 105.0

    elif kind == "sandstone":
        y = np.arange(size, dtype=np.float32)[:, None] / size
        warped_y = y + (broad - 0.5) * 0.016
        strata_wave = np.sin(warped_y * (2.0 * np.pi * 9.0) + (medium - 0.5) * 1.1)
        strata = smoothstep(0.15, 0.94, 0.5 + 0.5 * strata_wave)
        color = palette(
            np.clip(0.18 + 0.56 * broad + 0.16 * medium + 0.12 * strata, 0.0, 1.0),
            ((0.0, (56, 39, 31)), (0.38, (104, 68, 43)), (0.70, (153, 103, 57)), (1.0, (198, 151, 91))),
        )
        # Pale sediment ribbons are broad enough to read on a small rock.
        color = color * (0.88 + strata[..., None] * 0.12)
        height += (strata - 0.5) * 0.055 - fractures * 0.035
        roughness = 0.78 + 0.13 * fine + 0.06 * (1.0 - strata)
        normal_strength = 92.0

    elif kind == "mossstone":
        lichen_field = fractal_noise(size, seed + 53, ((8, 0.50), (16, 0.32), (32, 0.18)))
        lichen = smoothstep(0.60, 0.76, lichen_field) * (0.72 + 0.28 * fine)
        color = palette(
            0.16 + 0.67 * broad + 0.17 * medium,
            ((0.0, (30, 38, 36)), (0.40, (48, 55, 48)), (0.76, (77, 73, 54)), (1.0, (111, 100, 70))),
        )
        moss_color = palette(
            np.clip(0.30 + 0.56 * medium + 0.14 * fine, 0.0, 1.0),
            ((0.0, (66, 79, 43)), (0.50, (104, 119, 58)), (1.0, (151, 148, 77))),
        )
        color = color * (1.0 - lichen[..., None] * 0.86) + moss_color * lichen[..., None] * 0.86
        color *= 1.0 - fractures[..., None] * 0.20
        height += lichen * 0.025 - fractures * 0.035
        roughness = 0.82 + 0.11 * fine + 0.04 * lichen
        normal_strength = 98.0

    elif kind == "quartz":
        color = palette(
            0.18 + 0.66 * broad + 0.16 * medium,
            ((0.0, (39, 39, 37)), (0.42, (64, 59, 50)), (0.78, (105, 87, 64)), (1.0, (145, 120, 83))),
        )
        # A fine, warm quartz network catches light without looking emissive.
        quartz = fractures * (0.45 + 0.55 * smoothstep(0.35, 0.70, medium))
        seam_color = np.array((203.0, 171.0, 117.0), dtype=np.float32)
        color = color * (1.0 - quartz[..., None] * 0.82) + seam_color * quartz[..., None] * 0.82
        height += quartz * 0.026 - fractures * 0.025
        roughness = 0.72 + 0.16 * fine - quartz * 0.35
        normal_strength = 115.0

    else:
        raise ValueError(f"Unknown Earth Shield rock kind: {kind}")

    # Subtle grain stays visible at useful close-up scale without turning into
    # screen-space noise on the eventual small orbiting pieces.
    # Per-face value breaks up the cloud-like noise into readable rock facets.
    color *= (0.91 + face_tone[..., None] * 0.18)
    grain = (fine - 0.5) * 24.0 + (face_distance - 0.46) * 7.0
    color = np.clip(color + grain[..., None], 0.0, 255.0)
    height = np.clip(height + (fine - 0.5) * 0.055, 0.0, 1.0)
    roughness = np.clip(roughness, 0.52, 0.98)

    # Curvature-inspired cavity map from wrapped neighbouring samples. This is
    # intentionally soft; the generated map is a material cue, not baked AO.
    local_mean = (
        np.roll(height, 1, axis=0)
        + np.roll(height, -1, axis=0)
        + np.roll(height, 1, axis=1)
        + np.roll(height, -1, axis=1)
    ) * 0.25
    cavity = np.maximum(local_mean - height, 0.0)
    ao = np.clip(0.96 - cavity * 2.5 - fractures * 0.09, 0.68, 1.0)

    # Tangent-space OpenGL normal map (+Y in green). Wrapped derivatives make
    # both the image edge and the sampled normal continuous.
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) * 0.5
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) * 0.5
    nx, ny, nz = -dx * normal_strength, -dy * normal_strength, np.ones_like(height)
    length = np.sqrt(nx * nx + ny * ny + nz * nz)
    normal = np.stack((nx / length, ny / length, nz / length), axis=-1)
    normal = (normal + 1.0) * 127.5

    return {
        "BaseColor": color,
        "Roughness": roughness * 255.0,
        "Height": height * 255.0,
        "AO": ao * 255.0,
        "NormalGL": normal,
    }


ROCKS = (
    ("Rock01_BasaltHeart", "basalt", 1009),
    ("Rock02_SandstonePlate", "sandstone", 2027),
    ("Rock03_MossboundStone", "mossstone", 3049),
    ("Rock04_QuartzSeam", "quartz", 4051),
)


def generate(output: Path, size: int, seed_offset: int = 0) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, kind, seed in ROCKS:
        maps = make_maps(size, seed + seed_offset, kind)
        for map_name, pixels in maps.items():
            suffix = "png"
            path = output / f"T_EarthShield_{name}_{map_name}.{suffix}"
            if map_name == "BaseColor" or map_name == "NormalGL":
                save_rgb(path, pixels)
            else:
                save_gray(path, pixels)
            print(path.relative_to(ROOT) if path.is_relative_to(ROOT) else path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=1024, help="square texture size (default: 1024)")
    parser.add_argument("--seed-offset", type=int, default=0, help="change all rock patterns reproducibly")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="output texture directory")
    args = parser.parse_args()
    if args.size < 256 or args.size > 4096 or args.size & (args.size - 1):
        parser.error("--size must be a power of two from 256 through 4096")
    generate(args.out.resolve(), args.size, args.seed_offset)


if __name__ == "__main__":
    main()
