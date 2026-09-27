"""Smoke test the VFX viewer: boot it headless and prove an effect renders.

    python tools/test_viewer.py [--port 8097]

The server is started automatically unless --no-serve is passed.

Why a screenshot and not a canvas readback: a WebGL drawing buffer is not
preserved after present, so getImageData on the canvas returns a blank buffer
even while the page is drawing correctly. The page screenshot captures the
composited result and is the only reliable assertion here.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
SIDEBAR_PX = 285          # CSS sidebar is 280px; leave a margin
BG = np.array([0x1F, 0x24, 0x30], dtype=np.int16)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8097)
    ap.add_argument("--serve", action="store_true", default=True)
    ap.add_argument("--no-serve", dest="serve", action="store_false")
    args = ap.parse_args(argv)

    url = "http://127.0.0.1:%d/tools/viewer.html" % args.port
    shot = TOOLS / ".smoke.png"

    proc = None
    if args.serve:
        proc = subprocess.Popen(
            [sys.executable, str(TOOLS / "serve.py"), "--port", str(args.port)],
            cwd=str(ROOT))
        time.sleep(2.5)

    errors: list[str] = []
    ignored: list[str] = []
    try:
        from playwright.sync_api import sync_playwright

        def on_failed(r):
            # The viewer probes /__phaser/phaser.esm.js with HEAD before it
            # imports the module for real. Chromium reports that probe as
            # ERR_ABORTED when the import supersedes it, which is a benign
            # artifact of the probe - not a broken page. The canvas assertions
            # below are the real test.
            if "__phaser" in r.url and "ERR_ABORTED" in (r.failure or ""):
                ignored.append(r.url)
                return
            errors.append("REQFAIL %s %s" % (r.url, r.failure))

        with sync_playwright() as pw:
            b = pw.chromium.launch()
            page = b.new_page(viewport={"width": 1100, "height": 720})
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("requestfailed", on_failed)
            page.goto(url, wait_until="load")
            time.sleep(4)     # let WebGL boot and the first effect load

            info = page.evaluate("""() => ({
                canvas: !!document.querySelector('canvas'),
                fxCount: document.querySelectorAll('.fx').length,
                active: document.querySelector('.fx.active')?.dataset.id,
                frame: document.getElementById('frame')?.textContent,
                err: document.querySelector('.err')?.textContent?.slice(0, 200) || null,
            })""")
            page.screenshot(path=str(shot))
            b.close()
    except ImportError:
        print("playwright not installed - skipping (pip install playwright)")
        return 0
    finally:
        if proc:
            proc.terminate()

    if ignored:
        print("ignored %d benign probe abort(s) on the phaser route" % len(ignored))

    arr = np.asarray(Image.open(shot).convert("RGB")).astype(np.int16)
    stage = arr[:, SIDEBAR_PX:, :]
    lit = int((stage.max(axis=-1) > 100).sum())
    differs = int((np.abs(stage - BG).sum(axis=-1) > 24).sum())

    print("canvas      :", info["canvas"])
    print("effects     :", info["fxCount"], "active:", info["active"])
    print("frame       :", info["frame"])
    print("stage lit   : %d px (differs from bg: %d)" % (lit, differs))
    print("screenshot  :", shot)
    if info.get("err"):
        print("ERROR PANEL:", info["err"])
    for e in errors[:10]:
        print("ERROR:", e)

    ok = (info["canvas"] and info["fxCount"] > 0 and not errors
          and not info.get("err")
          and lit > 200 and differs > 200)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
