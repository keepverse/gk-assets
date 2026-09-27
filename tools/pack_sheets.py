"""
Pack per-frame PNG sequences into grid sprite sheets, driven by effect.json.

    python blender/tools/pack_sheets.py [--fx vfx/hit_impact] [--scale 2]

Every sub-program under blender/vfx/<name>/ must have an effect.json and a
sequences/<layer>/ directory of numbered frames. This writes sheets/<layer>.png
at the manifest's declared grid size, which is what the viewer tool loads.

Pure Pillow + numpy - no Blender needed, so it runs in CI or from a shell.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO_VFX = Path(__file__).resolve().parent.parent / "vfx"


def load_manifest(fx_dir: Path) -> dict:
    path = fx_dir / "effect.json"
    if not path.exists():
        raise SystemExit("no effect.json in %s" % fx_dir)
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def frames_for(seq_dir: Path) -> list[Path]:
    """Sorted frame list. Zero-padded names sort correctly with a plain glob."""
    if not seq_dir.exists():
        return []
    return sorted(p for p in seq_dir.glob("*.png") if p.is_file())


def pack(frames: list[Path], cell: int, cols: int, rows: int, out_path: Path) -> dict:
    """Grid-pack frames into one sheet.

    Imported tiles are flipped on load because PNG rows run top-down while the
    rest of the pipeline (and numpy slicing here) works bottom-up. Getting this
    wrong yields a vertically mirrored sheet, which is subtle and easy to miss.
    """
    need = cols * rows
    if len(frames) < need:
        print("   WARN %s: %d frames, grid needs %d" % (out_path.name, len(frames), need))

    sheet = Image.new("RGBA", (cols * cell, rows * cell), (0, 0, 0, 0))
    for i, f in enumerate(frames[:need]):
        with Image.open(f) as im:
            tile = im.convert("RGBA")
            if tile.size != (cell, cell):
                tile = tile.resize((cell, cell), Image.LANCZOS)
        sheet.paste(tile, ((i % cols) * cell, (i // cols) * cell))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)

    # Measure what we actually wrote so the manifest can be trusted later.
    arr = np.asarray(sheet).astype(np.float32) / 255.0
    cov = (arr[..., 3] > 0.05).mean()
    nonempty = sum(1 for i in range(min(len(frames), need))
                   if (np.asarray(sheet.crop(((i % cols) * cell, (i // cols) * cell,
                                              (i % cols + 1) * cell, (i // cols + 1) * cell)))
                       .astype(np.float32)[..., 3] > 0.05).any())
    return {
        "path": str(out_path),
        "size": list(sheet.size),
        "tiles_packed": min(len(frames), need),
        "nonempty_tiles": nonempty,
        "coverage": round(float(cov), 4),
    }


def write_index(targets: list[Path]) -> Path:
    """Regenerate vfx/index.json from the sub-programs found on disk."""
    ids = []
    for fx_dir in targets:
        if (fx_dir / "effect.json").exists():
            ids.append(load_manifest(fx_dir)["id"])
    ids.sort()
    out = REPO_VFX / "index.json"
    out.write_text(json.dumps({
        "$comment": ("Effect index. Lists ids only - the viewer then loads each "
                     "vfx/<id>/effect.json, so effect.json stays the single source "
                     "of truth. Regenerate with: python blender/tools/pack_sheets.py"),
        "effects": ids,
    }, indent=2) + "\n", encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fx", default=None, help="sub-program dir (default: all under vfx/)")
    ap.add_argument("--scale", type=int, default=1, help="cell size multiplier")
    ap.add_argument("--rows", type=int, default=None, help="override grid rows")
    ap.add_argument("--write-index", action="store_true", help="regenerate vfx/index.json")
    args = ap.parse_args(argv)

    targets = [Path(args.fx)] if args.fx else sorted(d for d in REPO_VFX.iterdir() if d.is_dir())
    rc = 0

    for fx_dir in targets:
        fx_dir = fx_dir if fx_dir.is_absolute() else (Path.cwd() / fx_dir)
        if not fx_dir.exists():
            print("skip (missing): %s" % fx_dir)
            rc = 1
            continue

        man = load_manifest(fx_dir)
        sp = man["sprite"]
        cell = sp["resolution"] * args.scale
        cols = sp["columns"]
        rows = args.rows or sp["rows"]
        need = sp["frameCount"]

        # Optional 3D projection block. Absent = flat top-down cards, which is
        # what hit_impact is. The packer only reports it; the viewer is what
        # actually consumes the width curve.
        proj = man.get("projection") or {"mode": "flat"}

        print("\n%s (%s)" % (man["name"], man["id"]))
        print("  grid %dx%d @ %dpx  frames=%d" % (cols, rows, cell, need))
        if proj.get("mode", "flat") != "flat":
            extra = ("  turntableSteps=%s" % proj["turntableSteps"]
                     if proj.get("turntableSteps") else "")
            print("  projection: %s%s" % (proj["mode"], extra))

        seq_root = fx_dir / "sequences"
        for layer in man["layers"]:
            frames = frames_for(seq_root / layer["id"])
            if not frames:
                print("   MISSING sequences/%s/ - nothing packed" % layer["id"])
                rc = 1
                continue
            info = pack(frames, cell, cols, rows, fx_dir / "sheets" / layer["sheet"])
            print("   %-8s %-14s %2d/%2d tiles  cov=%.4f" % (
                layer["id"], info["size"], info["nonempty_tiles"], need, info["coverage"]))

    if args.write_index and not args.fx:
        print("\nwrote %s" % write_index([t if t.is_absolute() else (Path.cwd() / t) for t in targets]))

    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
