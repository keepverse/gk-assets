"""
Locate a usable Blender for this repo.

There are two Blender installs on this machine:

    D:\\Program Files\\Blender Foundation\\Blender 5.1\\blender.exe
    C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe

5.1 is the one the MCP add-on is registered under and the one used for
interactive GUI work, so it is preferred. 5.2 is the newer LTS and is what
headless renders were previously using.

Why this is not just a constant: the two produce different results. A
sprite sheet rendered on 5.1 is not byte-identical to one rendered on 5.2,
and the MCP bridge only exists in the install that has the add-on. A script
that hardcodes one path silently rots the day that install moves or is
removed, so resolution is explicit and reports what it chose.

Usage:
    from blender_path import blender_exe
    subprocess.run([blender_exe(), "--background", "--python", script])

or:
    python blender_path.py          # prints the resolved path
    python blender_path.py --all    # lists every candidate and its status
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# Checked in order. The add-on is the deciding factor: a Blender without it
# cannot be driven interactively over MCP, which is the primary workflow here.
CANDIDATES: tuple[tuple[str, str], ...] = (
    (r"D:\Program Files\Blender Foundation\Blender 5.1\blender.exe", "5.1 (MCP add-on, GUI)"),
    (r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe", "5.2 (LTS, headless)"),
)

# Where the official MCP add-on registers, per Blender version.
ADDON_GLOBS = {
    "5.1": r"%APPDATA%\Blender Foundation\Blender\5.1\extensions\user_default\mcp",
}


def _addon_installed(version: str) -> bool:
    """True if the official Blender Lab MCP add-on is present for this version."""
    raw = ADDON_GLOBS.get(version)
    if not raw:
        return False
    path = Path(os.path.expandvars(raw))
    return path.is_dir() and (path / "__init__.py").exists()


def _version_of(exe: str) -> str:
    """Ask Blender for its version. Returns '' if it will not run."""
    try:
        out = subprocess.run(
            [exe, "--background", "--factory-startup", "--python-expr",
             "import bpy; print('VFXVER', bpy.app.version_string)"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    for line in (out.stdout or "").splitlines():
        if line.startswith("VFXVER"):
            return line.split(" ", 1)[1].strip()
    return ""


def candidates() -> list[dict]:
    """Every known Blender, with whether it exists and has the MCP add-on."""
    found = []
    seen = set()
    for path, note in CANDIDATES:
        found.append({"path": path, "note": note, "exists": Path(path).is_file(),
                      "version": path.rsplit("Blender ", 1)[-1].split("\\")[0],
                      "mcp_addon": _addon_installed(path.rsplit("Blender ", 1)[-1].split("\\")[0])})
        seen.add(path)

    # Anything on PATH is a legitimate last resort.
    on_path = shutil.which("blender")
    if on_path and on_path not in seen:
        found.append({"path": on_path, "note": "on PATH", "exists": True,
                      "version": "?", "mcp_addon": False})
    return found


def blender_exe(prefer_mcp: bool = True) -> str:
    """Return a usable blender.exe, or raise with an actionable message.

    prefer_mcp picks the install that has the MCP add-on when one exists, so
    `execute_blender_code` can reach the same Blender the GUI session is in.
    """
    cands = [c for c in candidates() if c["exists"]]
    if not cands:
        raise FileNotFoundError(
            "No Blender found. Looked at:\n  " +
            "\n  ".join(c["path"] for c in candidates()) +
            "\nSet BLENDER_PATH to override.")
    if prefer_mcp:
        with_mcp = [c for c in cands if c["mcp_addon"]]
        if with_mcp:
            return with_mcp[0]["path"]
    return cands[0]["path"]


def _main(argv: list[str]) -> int:
    if "--all" in argv:
        rows = candidates()
        width = max(len(r["path"]) for r in rows)
        for r in rows:
            status = "ok" if r["exists"] else "MISSING"
            addon = "mcp" if r["mcp_addon"] else "no-mcp"
            print(f"  {status:8} {addon:7} {r['path']:<{width}}  {r['note']}")
        try:
            print("\nresolved: %s" % blender_exe())
        except FileNotFoundError as exc:
            print("\n%s" % exc)
            return 1
        return 0

    try:
        exe = blender_exe()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(exe)
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
