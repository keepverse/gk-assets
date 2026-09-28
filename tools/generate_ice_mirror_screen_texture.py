"""Generate the procedural soft-frost texture for the deploy screen.

Run from the repository root:
    python tools/generate_ice_mirror_screen_texture.py

The deterministic RGBA source is stored beside the reusable Ice Shield
textures. A dark contact preview is written under the ignored lookdev folder.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "assets" / "vfx" / "ice_shield" / "textures" / "mirror_screen_v1"
TEXTURE_NAME = "T_IceShield_MirrorHexScreen_RGBA.png"
PREVIEW_PATH = ROOT / "assets" / "vfx" / "ice_shield" / "lookdev" / "ice_mirror_hexscreen_texture.png"
SEED = 49183


def make_texture(size: int) -> Image.Image:
    rng = np.random.default_rng(SEED)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    u = (xx + 0.5) / size
    v = (yy + 0.5) / size

    def soft_noise(cells: int) -> np.ndarray:
        """Upscale a deterministic low-frequency field without hard seams."""
        samples = rng.normal(0.0, 1.0, (cells, cells)).astype(np.float32)
        field = Image.fromarray(samples, "F").resize(
            (size, size), Image.Resampling.BICUBIC
        )
        return np.asarray(field, dtype=np.float32)

    # A few soft scales give the mirror face a quiet icy haze. There are no
    # polygon seams, spokes, or lines meeting at a point across the screen.
    cloud = (
        0.58 * soft_noise(5)
        + 0.29 * soft_noise(11)
        + 0.13 * soft_noise(23)
    )
    cloud /= max(float(cloud.std()), 1e-6)
    sheen = np.exp(-(((u - 0.30) / 0.28) ** 2 + ((v - 0.34) / 0.38) ** 2))
    secondary_sheen = np.exp(-(((u - 0.76) / 0.31) ** 2 + ((v - 0.72) / 0.25) ** 2))

    # Keep colour variation broad and low-contrast; opacity carries the
    # translucency while the single exterior rim defines the regular hex.
    frost = cloud[..., None] * np.array([7.0, 10.0, 13.0], dtype=np.float32)
    glint = (sheen + 0.55 * secondary_sheen)[..., None] * np.array(
        [11.0, 19.0, 25.0], dtype=np.float32
    )
    base = np.array([58.0, 116.0, 158.0], dtype=np.float32)
    grain = rng.normal(0.0, 0.8, (size, size, 1)).astype(np.float32)
    rgb = np.clip(base + frost + glint + grain, 0, 255).astype(np.uint8)

    # The average alpha stays close to the previous texture. Soft variation
    # creates a readable veil at gameplay size without painting an opaque slab.
    alpha = np.clip(20.0 + 3.2 * cloud + 5.0 * sheen + 2.5 * secondary_sheen, 8, 36)
    rgba = np.empty((size, size, 4), dtype=np.uint8)
    rgba[..., :3] = rgb
    rgba[..., 3] = alpha.astype(np.uint8)
    return Image.fromarray(rgba, "RGBA")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=1024, help="power-of-two texture size (default: 1024)")
    parser.add_argument("--out", type=Path, default=OUTPUT_DIR, help="source texture directory")
    parser.add_argument("--preview", type=Path, default=PREVIEW_PATH, help="dark contact preview path")
    args = parser.parse_args()
    if args.size < 256 or args.size > 4096 or args.size & (args.size - 1):
        parser.error("--size must be a power of two from 256 through 4096")

    args.out.mkdir(parents=True, exist_ok=True)
    texture = make_texture(args.size)
    target = args.out / TEXTURE_NAME
    texture.save(target, optimize=True)

    preview = Image.new("RGBA", texture.size, (5, 16, 35, 255))
    preview.alpha_composite(texture)
    args.preview.parent.mkdir(parents=True, exist_ok=True)
    preview.convert("RGB").resize((512, 512), Image.Resampling.LANCZOS).save(args.preview, optimize=True)
    print(f"texture: {target}")
    print(f"preview: {args.preview}")


if __name__ == "__main__":
    main()
