"""
One command to review VFX sub-programs.

    python tools/review_ui.py                 # serve, open the browser, review mode on
    python tools/review_ui.py --port 8099
    python tools/review_ui.py --no-open
    python tools/review_ui.py --list          # just the review state, no server

Serves the viewer with a review overlay: each sub-program shows its verification
and human sign-off state, and the page reads the same review.json files
tools/review.py writes, so what you see in the browser is what gets recorded.

The point is to remove the friction between "something changed" and "someone
looked at it". A sign-off recorded from the viewer is a sign-off attributed to
whoever typed their name.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import sys
import threading
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

VIEWER = TOOLS / "viewer.html"
VFX = ROOT / "vfx"
REVIEW_JSON = "review.json"


def effect_ids() -> list[str]:
    return sorted(d.name for d in VFX.iterdir()
                  if d.is_dir() and (d / "effect.json").is_file())


def review_payload() -> list[dict]:
    """Review state for every sub-program, in the shape the viewer expects.

    Recomputes the machine result rather than trusting the snapshot stored in
    review.json, so a sub-program rebuilt after its sign-off shows as stale
    rather than as approved.
    """
    import review as review_mod

    out = []
    for eid in effect_ids():
        path = VFX / eid / REVIEW_JSON
        rec = {}
        if path.is_file():
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                rec = {}
        # ALWAYS recompute, for every sub-program regardless of review status.
        # An earlier version only recomputed for approved ones and fell back to
        # the snapshot stored in review.json otherwise - so an unreviewed effect
        # reported "not verified yet" in the browser while the CLI correctly
        # reported pass. The two tools must never disagree.
        machine = review_mod.machine_result(eid)
        out.append({
            "id": eid,
            "status": rec.get("status", "unreviewed"),
            "by": rec.get("reviewedBy"),
            "at": rec.get("reviewedAt"),
            "note": rec.get("note"),
            "machine": machine,
            "stale": machine.startswith("stale"),
            "failing": machine.startswith("FAIL"),
        })
    return out


def list_only() -> int:
    import review as review_mod
    return review_mod.cmd_list(None)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true", help="do not open a browser")
    ap.add_argument("--list", action="store_true",
                    help="print review state and exit (no server)")
    args = ap.parse_args(argv)

    if args.list:
        return list_only()

    if not VIEWER.exists():
        print("viewer not found: %s" % VIEWER)
        return 1

    import review as review_mod
    import serve as serve_mod
    phaser = serve_mod.find_phaser()
    if phaser is None:
        print("warning: no Phaser build found; the preview will not boot.")
        print("         Only the review overlay and manifest will load.")
        for c in serve_mod.PHASER_CANDIDATES:
            print("           %s" % c)

    handler = _build_handler(phaser)

    # Refuse to start on a port something else already owns. Binding would
    # either fail obscurely or, worse, appear to work while another service
    # answers - which is exactly what happened on 8082/8083, where unrelated
    # Windows services returned 404 for every route and the review UI silently
    # listed zero sub-programs.
    import socket as _socket
    probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
    probe.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
    try:
        probe.bind((args.host, args.port))
    except OSError as exc:
        probe.close()
        print("port %d on %s is already in use: %s" % (args.port, args.host, exc))
        print("pick another with --port <n>.")
        return 1
    probe.close()

    socketserver.TCPServer.allow_reuse_address = True
    url = "http://%s:%d/tools/viewer.html?review=1" % (args.host, args.port)
    with socketserver.TCPServer((args.host, args.port), handler) as httpd:
        rows = review_payload()
        done = sum(1 for r in rows
                   if r["status"] != "rejected" and r["machine"].startswith("pass"))
        signed = sum(1 for r in rows if r["status"] == "approved" and not r["stale"])
        print("VFX review: %s" % url)
        if phaser:
            print("  phaser : %s" % phaser)
        # Count complete work, not "pending review". A sign-off is optional
        # extra assurance; nothing is blocked without one, so reporting a
        # backlog of finished assets would be misleading.
        print("  %d sub-program(s) built and verified" % done)
        if signed < done:
            print("  %d also carry a human sign-off - optional, add one here if"
                  " you want the extra assurance" % signed)
        print("Ctrl+C to stop.")
        if not args.no_open:
            # Open after the socket is listening, or the page races the server.
            threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def _build_handler(phaser):
    """Single handler serving static files, the phaser route and the review API."""
    import serve as serve_mod

    class Handler(http.server.SimpleHTTPRequestHandler):
        def _json(self, obj, code=200):
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _phaser(self, body: bool):
            if phaser is None:
                self.send_error(404, "no Phaser build; pass --phaser")
                return
            data = phaser.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if body:
                self.wfile.write(data)

        def do_GET(self):  # noqa: N802
            route = self.path.split("?")[0]
            if route == "/__phaser/phaser.esm.js":
                self._phaser(body=True)
                return
            if route == "/__review/state":
                self._json(review_payload())
                return
            super().do_GET()

        def do_HEAD(self):  # noqa: N802
            if self.path.split("?")[0] == "/__phaser/phaser.esm.js":
                self._phaser(body=False)
                return
            super().do_HEAD()

        def do_POST(self):  # noqa: N802
            if self.path.split("?")[0] != "/__review/save":
                self.send_error(405)
                return
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                data = json.loads(raw.decode("utf-8"))
            except ValueError:
                self._json({"ok": False, "error": "invalid json"}, 400)
                return
            eid = (data.get("id") or "").strip()
            status = (data.get("status") or "").strip()
            by = (data.get("by") or "").strip()
            note = (data.get("note") or "").strip()
            if eid not in effect_ids():
                self._json({"ok": False, "error": "unknown sub-program"}, 400)
                return
            if status not in ("approved", "rejected"):
                self._json({"ok": False, "error": "status must be approved or rejected"}, 400)
                return
            if not by:
                self._json({"ok": False,
                            "error": "a sign-off must record who reviewed it"}, 400)
                return
            if not note:
                self._json({"ok": False,
                            "error": "a sign-off must record what was observed"}, 400)
                return
            import review as review_mod
            rec = {
                "id": eid, "status": status, "reviewedBy": by, "note": note,
                "machine": review_mod.machine_result(eid),
                "reviewedAt": review_mod.datetime.now(
                    review_mod.timezone.utc).isoformat(timespec="seconds"),
                "updatedAt": review_mod.datetime.now(
                    review_mod.timezone.utc).isoformat(timespec="seconds"),
            }
            (VFX / eid / REVIEW_JSON).write_text(
                json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            self._json({"ok": True, "review": rec})

        def log_message(self, *a):
            pass

    return functools.partial(Handler, directory=str(ROOT))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
