"""
Build and verify every sub-program, or one of them.

    python tools/build.py                 # everything
    python tools/build.py shield_fire_idle
    python tools/build.py --skip-verify

The sequence is fixed and always the same order, because it is easy to run
pack before build (stale sheets) or verify before pack (nothing to check):

    1. build   render sequences + previews for each effect
    2. pack    sequences -> sheets, refresh vfx/index.json
    3. verify  assert the sheets and composites are correct

The point of wrapping it is that step 3 must never be skipped. A build script
that exits 0 while producing a solid rectangle instead of fire is the failure
this repo actually hit, and only the verifier catches it.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS))

# The sub-programs that exist. Kept explicit rather than globbed from the
# directory so a half-copied effect directory cannot silently join the build.
#
# (id, script stem) - the script is not always the effect id: the effect is
# shield_fire_idle but the builder is shield_idle.
#
# shield_ice_lifecycle is deliberately absent. It has authoring scenes but no
# effect.json and produces no sheets, so it is a staging folder, not a
# sub-program. See vfx/README.md "Not a sub-program".
EFFECTS = (
    ("shield_fire_idle", "shield_idle"),
    ("shield_fire_rotate", "shield_rotate"),
    ("shield_fire_impact", "shield_impact"),
    ("shield_fire_strengthen", "shield_strengthen"),
    ("shield_fire_break", "shield_break"),
    ("shield_ice_idle", "shield_ice_build"),
)

GREEN, RED, YELLOW, DIM, RESET = "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m"


def run(cmd: list[str], label: str, timeout: int = 1800) -> tuple[int, str]:
    print("%s>> %s%s" % (DIM, label, RESET), flush=True)
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return 1, "timed out after %ss" % timeout
    except OSError as exc:
        return 1, str(exc)
    out = (p.stdout or "") + (p.stderr or "")
    return p.returncode, out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("effects", nargs="*", help="sub-program ids (default: all)")
    ap.add_argument("--skip-verify", action="store_true",
                    help="build and pack only (not recommended)")
    ap.add_argument("--skip-build", action="store_true",
                    help="repack and verify existing sequences")
    args = ap.parse_args(argv)

    from blender_path import blender_exe
    blender = blender_exe()
    print("Blender: %s\n" % blender)

    effects = args.effects or [e for e, _ in EFFECTS]
    known = {e for e, _ in EFFECTS}
    unknown = [e for e in effects if e not in known]
    if unknown:
        print("unknown sub-program(s): %s" % ", ".join(unknown))
        print("known: %s" % ", ".join(sorted(known)))
        return 2
    script_for = dict(EFFECTS)

    failures = []
    t0 = time.time()

    # ---- 1. build -------------------------------------------------------
    if not args.skip_build:
        for e in effects:
            stem = script_for[e]
            script = "tools/%s.py" % stem
            if not (ROOT / script).is_file():
                print("%s   build FAILED: %s does not exist%s" % (RED, script, RESET))
                failures.append(("build", e))
                continue
            code, out = run([blender, "--background", "--factory-startup",
                             "--python", script], "build %s" % e)
            # Blender exits 0 even when it cannot open the script, and a script
            # that dies early still exits 0 in some paths. So the exit code is
            # not sufficient: require the build's own completion line.
            summary = next((l.strip() for l in out.splitlines() if "px/unit" in l), "")
            if code != 0 or not summary:
                failures.append(("build", e))
                print("%s   build FAILED (exit %d, no completion line)%s"
                      % (RED, code, RESET))
                tail = [l for l in out.splitlines()
                        if l.strip() and "Blender quit" not in l
                        and "Fra:" not in l and "Read prefs" not in l][-6:]
                for l in tail:
                    print("     %s" % l)
            else:
                print("%s   ok%s  %s" % (GREEN, RESET, summary))

    # ---- 2. pack --------------------------------------------------------
    code, out = run([sys.executable, "tools/pack_sheets.py", "--write-index"], "pack sheets")
    if code != 0:
        failures.append(("pack", "all"))
        print("%s   pack FAILED%s" % (RED, RESET))
        for l in out.splitlines()[-6:]:
            print("     %s" % l)
    else:
        tiles = [l.strip() for l in out.splitlines() if "tiles" in l]
        print("%s   ok%s  %d layer(s) packed" % (GREEN, RESET, len(tiles)))

    # ---- 3. verify ------------------------------------------------------
    if not args.skip_verify:
        code, out = run([blender, "--background", "--factory-startup",
                         "--python", "tools/verify_all.py"], "verify")
        lines = [l for l in out.splitlines()
                 if l.strip() and not l.startswith(("Read prefs", "Fra:", "Blender 5"))
                 and "Blender quit" not in l]
        for l in lines[-24:]:
            print("     %s" % l)
        if code != 0:
            failures.append(("verify", "all"))
    elif not args.skip_build:
        print("\n%s! verify skipped - an unverified build is not a finished one%s"
              % (YELLOW, RESET))

    dt = time.time() - t0
    print()
    if failures:
        print("%sRESULT: FAIL%s  %s in %.0fs" % (RED, RESET,
              ", ".join("%s/%s" % f for f in failures), dt))
        return 1
    print("%sRESULT: PASS%s  in %.0fs" % (GREEN, RESET, dt))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
