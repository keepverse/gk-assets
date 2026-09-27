"""
Check that this checkout is ready to build and verify assets.

    python tools/doctor.py

Prints one line per check and exits non-zero if anything blocks a build. Run
this first when something is not working, before reading a traceback: the
failure modes it covers (no Blender, a dead MCP bridge, a missing pip package)
all produce confusing errors further down.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))

OK, WARN, FAIL = "ok  ", "warn", "FAIL"


def check_blender():
    try:
        from blender_path import blender_exe
        exe = blender_exe()
    except FileNotFoundError as exc:
        return FAIL, "no Blender found - install it or set BLENDER_PATH", str(exc).splitlines()[0]
    except Exception as exc:                      # noqa: BLE001
        return FAIL, "blender_path.py raised", repr(exc)
    try:
        out = subprocess.run([exe, "--background", "--factory-startup", "--python-expr",
                              "import bpy; print('V', bpy.app.version_string)"],
                             capture_output=True, text=True, timeout=90)
        ver = next((l[2:] for l in out.stdout.splitlines() if l.startswith("V ")), "?")
    except (OSError, subprocess.SubprocessError) as exc:
        return FAIL, "Blender found but will not run", repr(exc)
    return OK, "Blender %s" % ver, exe


def check_mcp_addon():
    try:
        from blender_path import candidates
    except Exception as exc:                      # noqa: BLE001
        return FAIL, "could not import blender_path", repr(exc)
    rows = candidates()
    with_mcp = [r for r in rows if r["mcp_addon"]]
    if with_mcp:
        return OK, "MCP add-on present for %s" % with_mcp[0]["version"], with_mcp[0]["path"]
    return WARN, "MCP add-on not detected on any install (headless builds still work)", ""


def check_mcp_bridge():
    """The bridge is a TCP socket inside Blender; a dead one is the single most
    confusing failure because the MCP server starts fine and only fails per call."""
    import socket
    port = 9876
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", port))
    except OSError:
        return WARN, ("nothing listening on %d - start 'MCP Bridge Server' in Blender's "
                      "MCP preferences and tick Auto Start" % port), ""
    finally:
        s.close()
    return OK, "MCP bridge listening on %d" % port, ""


def check_python_packages():
    missing = []
    for mod, pkg in (("numpy", "numpy"), ("PIL", "Pillow")):
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)
    if missing:
        return FAIL, "missing pip packages: %s" % ", ".join(missing), "pip install -r requirements.txt"
    return OK, "numpy and Pillow importable", ""


def check_playwright():
    try:
        import playwright  # noqa: F401
    except ImportError:
        return WARN, "playwright not installed (only needed for tools/test_viewer.py)", ""
    return OK, "playwright importable", ""


def check_phaser():
    try:
        from serve import find_phaser
    except Exception as exc:                      # noqa: BLE001
        return WARN, "could not import serve: %r" % exc, ""
    p = find_phaser()
    if p is None:
        return WARN, "no Phaser build found (only needed for the browser preview)", "python tools/serve.py --phaser <path>"
    return OK, "Phaser found", str(p)


def check_assets():
    vfx = ROOT / "vfx"
    if not vfx.is_dir():
        return FAIL, "vfx/ missing", ""
    effects = [d for d in vfx.iterdir() if d.is_dir()]
    if not effects:
        return WARN, "no sub-programs in vfx/ yet", ""
    missing = []
    for d in effects:
        if not (d / "effect.json").is_file():
            missing.append(d.name + " (no effect.json)")
        if not list((d / "sheets").glob("*.png")) if (d / "sheets").is_dir() else True:
            missing.append(d.name + " (no sheets)")
    if missing:
        return WARN, "incomplete sub-programs: %s" % "; ".join(missing), "run pack_sheets.py"
    return OK, "%d sub-programs complete" % len(effects), ""


CHECKS = (
    ("Blender", check_blender, True),
    ("Python packages", check_python_packages, True),
    ("Sub-programs", check_assets, False),
    ("MCP add-on", check_mcp_addon, False),
    ("MCP bridge", check_mcp_bridge, False),
    ("Playwright", check_playwright, False),
    ("Phaser", check_phaser, False),
)


def main() -> int:
    print("gk-assets doctor\n")
    blocking = 0
    for name, fn, required in CHECKS:
        try:
            status, msg, detail = fn()
        except Exception as exc:                  # noqa: BLE001
            status, msg, detail = FAIL, "raised %r" % exc, ""
        print("  %s  %-18s %s" % (status, name, msg))
        if detail:
            print("        %s" % detail)
        if status == FAIL and required:
            blocking += 1
    print()
    if blocking:
        print("RESULT: %d blocking problem(s). Fix those before building." % blocking)
        return 1
    print("RESULT: ready. 'warn' items are optional and depend on what you are doing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
