"""Create deterministic, repo-owned Ice Shield snowflake sprites.

The three silhouettes are deliberately different: branched dendrite, pointed
lance, and compact rosette. They are drawn as vector-like geometry at 3x size,
then downsampled to clean 512px transparent PNGs for Blender cards.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "assets" / "vfx" / "ice_shield" / "textures" / "snowflake_v1"
PREVIEW = ROOT / "assets" / "vfx" / "ice_shield" / "lookdev" / "snowflake_texture_preview.png"
SIZE = 512
SCALE = 3
HI = SIZE * SCALE
CENTER = (HI // 2, HI // 2)


def point(radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return CENTER[0] + math.cos(radians) * radius, CENTER[1] - math.sin(radians) * radius


def radial_polygon(angle: float, r0: float, r1: float,
                   w0: float, w1: float) -> list[tuple[float, float]]:
    """Tapered radial shard with its broad end toward the center."""
    a0, a1 = point(r0, angle), point(r1, angle)
    perp = (-math.sin(math.radians(angle)), -math.cos(math.radians(angle)))
    return [
        (a0[0] + perp[0] * w0, a0[1] + perp[1] * w0),
        (a1[0] + perp[0] * w1, a1[1] + perp[1] * w1),
        (a1[0] - perp[0] * w1, a1[1] - perp[1] * w1),
        (a0[0] - perp[0] * w0, a0[1] - perp[1] * w0),
    ]


def line(draw: ImageDraw.ImageDraw, pts: list[tuple[float, float]], width: int,
         color: tuple[int, int, int, int]) -> None:
    draw.line(pts, fill=color, width=width, joint="curve")


def new_layers() -> tuple[Image.Image, Image.Image, ImageDraw.ImageDraw, ImageDraw.ImageDraw]:
    glow = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    art = Image.new("RGBA", (HI, HI), (0, 0, 0, 0))
    return glow, art, ImageDraw.Draw(glow), ImageDraw.Draw(art)


def finish(glow: Image.Image, art: Image.Image) -> Image.Image:
    glow = glow.filter(ImageFilter.GaussianBlur(9 * SCALE))
    # Keep the bloom soft and dim so the crisp branch silhouette remains clear
    # at the 128px gameplay size.
    glow.putalpha(glow.getchannel("A").point(lambda a: int(a * 0.42)))
    hi = Image.alpha_composite(glow, art)
    return hi.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def branching() -> Image.Image:
    glow, art, gd, d = new_layers()
    pale = (176, 239, 255, 255)
    highlight = (236, 252, 255, 255)
    faint = (100, 202, 244, 200)
    for arm in range(6):
        angle = arm * 60 + 30
        start, tip = point(23 * SCALE, angle), point(214 * SCALE, angle)
        line(gd, [start, tip], 22 * SCALE, (93, 198, 255, 110))
        line(d, [start, tip], 7 * SCALE, pale)
        line(d, [point(36 * SCALE, angle), point(207 * SCALE, angle)], 2 * SCALE, highlight)
        for fraction, length in ((0.39, 43), (0.57, 52), (0.75, 46), (0.90, 31)):
            base_r = 23 + 191 * fraction
            base = point(base_r * SCALE, angle)
            for sign in (-1, 1):
                end = (base[0] + math.cos(math.radians(angle + sign * 54)) * length * SCALE,
                       base[1] - math.sin(math.radians(angle + sign * 54)) * length * SCALE)
                line(gd, [base, end], 14 * SCALE, (83, 187, 246, 95))
                line(d, [base, end], 5 * SCALE, faint)
                line(d, [base, (base[0] + (end[0] - base[0]) * 0.78,
                                base[1] + (end[1] - base[1]) * 0.78)], 2 * SCALE, highlight)
    d.ellipse((CENTER[0] - 20 * SCALE, CENTER[1] - 20 * SCALE,
               CENTER[0] + 20 * SCALE, CENTER[1] + 20 * SCALE), fill=highlight)
    return finish(glow, art)


def lance() -> Image.Image:
    glow, art, gd, d = new_layers()
    ice = (172, 234, 255, 255)
    bright = (242, 253, 255, 255)
    blue = (86, 187, 240, 225)
    for arm in range(6):
        angle = arm * 60
        outer = radial_polygon(angle, 22 * SCALE, 218 * SCALE, 20 * SCALE, 1.7 * SCALE)
        mid = radial_polygon(angle, 30 * SCALE, 207 * SCALE, 10 * SCALE, 0.8 * SCALE)
        gd.polygon(outer, fill=(74, 184, 251, 105))
        d.polygon(outer, fill=blue)
        d.polygon(mid, fill=ice)
        d.line([point(28 * SCALE, angle), point(207 * SCALE, angle)], fill=bright, width=2 * SCALE)
        # Small paired cuts make the spokes feel faceted without adding a
        # second layer of arms.
        for r in (76, 132, 177):
            a = point(r * SCALE, angle)
            b = point((r + 20) * SCALE, angle + 7)
            c = point((r + 20) * SCALE, angle - 7)
            d.polygon([a, b, c], fill=(223, 249, 255, 220))
    d.polygon([point(28 * SCALE, i * 60) for i in range(6)], fill=bright)
    return finish(glow, art)


def rosette() -> Image.Image:
    glow, art, gd, d = new_layers()
    body = (150, 224, 251, 255)
    light = (231, 250, 255, 255)
    accent = (93, 190, 232, 230)
    for arm in range(6):
        angle = arm * 60 + 30
        petal = radial_polygon(angle, 24 * SCALE, 170 * SCALE, 25 * SCALE, 3 * SCALE)
        inner = radial_polygon(angle, 38 * SCALE, 154 * SCALE, 8 * SCALE, 1.2 * SCALE)
        gd.polygon(petal, fill=(81, 185, 239, 100))
        d.polygon(petal, fill=body)
        d.polygon(inner, fill=light)
        # A short transverse cut near each point gives the broad rosette a
        # crystalline, six-petal rather than starburst silhouette.
        center = point(123 * SCALE, angle)
        p1 = point(127 * SCALE, angle + 15)
        p2 = point(127 * SCALE, angle - 15)
        line(d, [p1, center, p2], 4 * SCALE, accent)
        for branch in (-1, 1):
            base = point(78 * SCALE, angle)
            end = point(107 * SCALE, angle + branch * 62)
            line(d, [base, end], 4 * SCALE, accent)
    d.ellipse((CENTER[0] - 33 * SCALE, CENTER[1] - 33 * SCALE,
               CENTER[0] + 33 * SCALE, CENTER[1] + 33 * SCALE), fill=light)
    d.ellipse((CENTER[0] - 14 * SCALE, CENTER[1] - 14 * SCALE,
               CENTER[0] + 14 * SCALE, CENTER[1] + 14 * SCALE), fill=accent)
    return finish(glow, art)


def make_preview(images: list[tuple[str, Image.Image]]) -> None:
    cell = 300
    sheet = Image.new("RGBA", (cell * len(images), cell), (9, 24, 42, 255))
    for idx, (name, image) in enumerate(images):
        tile = Image.new("RGBA", (cell, cell), (9, 24, 42, 255))
        enlarged = image.resize((cell - 36, cell - 36), Image.Resampling.LANCZOS)
        tile.alpha_composite(enlarged, ((cell - enlarged.width) // 2, 4))
        draw = ImageDraw.Draw(tile)
        draw.text((12, cell - 22), name, fill=(224, 245, 255, 255))
        sheet.alpha_composite(tile, (idx * cell, 0))
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    sheet.convert("RGB").save(PREVIEW, quality=95)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sprites = [
        ("Branching", branching()),
        ("Lance", lance()),
        ("Rosette", rosette()),
    ]
    for name, image in sprites:
        path = OUT_DIR / f"T_IceShield_Snowflake_{name}.png"
        image.save(path, optimize=True)
        print(f"wrote {path}")
    make_preview(sprites)
    print(f"wrote {PREVIEW}")


if __name__ == "__main__":
    main()
