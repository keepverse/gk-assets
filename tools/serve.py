"""
Serve the VFX viewer for local inspection.

    python tools/serve.py [--port 8097]

Two things differ from the repo this came from:

  * The root is gk-assets, not a monorepo. The viewer's import map resolves
    Phaser from a sibling web workspace, so that path is configurable and
    degrades to a clear message instead of a 404.
  * The viewer lives at tools/viewer.html, next to this script.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWER = Path(__file__).resolve().parent / "viewer.html"

# Where to find a Phaser 4 ESM build. First that exists wins; override with
# --phaser. These are absolute because gk-assets is not the web workspace.
PHASER_CANDIDATES = (
    Path(r"D:\Works\source\plant-vs-zombie-rise-of-summoner\web\fusion-rpg-web\node_modules\phaser\dist\phaser.esm.js"),
    Path(r"D:\Works\source\Keepverse\gk-fusion\node_modules\phaser\dist\phaser.esm.js"),
    ROOT / "node_modules" / "phaser" / "dist" / "phaser.esm.js",
)


def find_phaser() -> Path | None:
    for c in PHASER_CANDIDATES:
        if c.is_file():
            return c
    return None


def make_handler(phaser: Path | None):
    """Static handler plus the /__phaser/ virtual route.

    The viewer's import map points 'phaser' at /__phaser/phaser.esm.js because
    gk-assets is not the web workspace and there is no relative path to a
    Phaser build from here. An import map is resolved before any page script
    runs, so this substitution has to happen here rather than in the page.
    """
    class Handler(http.server.SimpleHTTPRequestHandler):
        _PHASER_ROUTE = "/__phaser/phaser.esm.js"

        def _serve_phaser(self, body: bool) -> None:
            if phaser is None:
                self.send_error(404, "No Phaser build found. Pass --phaser <path> "
                                    "to serve.py or install phaser.")
                return
            try:
                data = phaser.read_bytes()
            except OSError as exc:
                self.send_error(500, str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(data)

        def do_GET(self):  # noqa: N802 - stdlib naming
            if self.path.split("?")[0] == self._PHASER_ROUTE:
                self._serve_phaser(body=True)
                return
            super().do_GET()

        def do_HEAD(self):  # noqa: N802 - stdlib naming
            # The viewer probes with HEAD before importing. Without this the
            # probe 404s even though GET works, and the page reports a false
            # "engine unavailable".
            if self.path.split("?")[0] == self._PHASER_ROUTE:
                self._serve_phaser(body=False)
                return
            super().do_HEAD()

    return functools.partial(Handler, directory=str(ROOT))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8097)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--phaser", type=Path, default=None)
    args = ap.parse_args(argv)

    if not VIEWER.exists():
        print("viewer not found: %s" % VIEWER)
        return 1

    phaser = args.phaser or find_phaser()
    if phaser is None:
        print("warning: no Phaser ESM build found; the browser preview will not boot.")
        print("         Looked at:")
        for c in PHASER_CANDIDATES:
            print("           %s" % c)
        print("         Install phaser or pass --phaser <path>.")
        print("         Building and verifying do NOT need Phaser - only the preview does.")

    handler = make_handler(phaser)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        print("VFX viewer: http://%s:%d/tools/viewer.html" % (args.host, args.port))
        print("  phaser: %s" % (phaser if phaser else "NOT FOUND"))
        print("Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
