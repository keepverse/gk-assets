"""
Record and clear HUMAN visual review sign-off for a sub-program.

    python tools/review.py --list
    python tools/review.py shield_fire_idle --review  "reads as a barrier on the lawn"
    python tools/review.py shield_fire_idle --approve
    python tools/review.py shield_fire_idle --reject  "flame looks like a solid blob"
    python tools/review.py shield_fire_idle --clear

Why this is separate from verify: `verify_all.py` proves a sprite is the right
shape, size, colour and frame count. It cannot tell you whether the effect
reads as a shield in motion on a bright lawn. That is a human judgement, and an
agent must not be able to make it. This script only ever records a decision a
person made; it never makes one.

State lives in vfx/<id>/review.json:

    status        "unreviewed" | "approved" | "rejected"
    reviewedBy    who approved it
    reviewedAt    ISO timestamp
    machine       the verify_all result at the time of review
    note          the reviewer's own words
    rejection     set when status is "rejected"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VFX = ROOT / "vfx"


def list_effects() -> list[str]:
    return sorted(d.name for d in VFX.iterdir()
                  if d.is_dir() and (d / "effect.json").is_file())


def review_path(eid: str) -> Path:
    return VFX / eid / "review.json"


def load(eid: str) -> dict:
    p = review_path(eid)
    if p.is_file():
        with p.open(encoding="utf-8") as fh:
            return json.load(fh)
    return {"id": eid, "status": "unreviewed"}


def save(eid: str, data: dict) -> Path:
    p = review_path(eid)
    data["updatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return p


def machine_result(eid: str) -> str:
    """Record what verify_all last concluded about this effect.

    Reads the cached result written by verify_all rather than re-running
    Blender: importing verify_all needs bpy, which plain python does not have,
    and recording a review should never silently spend render time. "stale"
    means verify_all has not run since the sheets were last modified.
    """
    p = VFX / eid / ".verify.json"
    if not p.is_file():
        return "not verified yet"
    try:
        with p.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return "unreadable (%r)" % exc
    if data.get("effect") != eid:
        return "unknown"
    newest_sheet = 0.0
    for sheet in (VFX / eid / "sheets").glob("*.png"):
        newest_sheet = max(newest_sheet, sheet.stat().st_mtime)
    if newest_sheet > data.get("checkedAt", 0):
        return "stale (sheets changed since last verify)"
    return "pass" if data.get("pass") else "FAIL: " + "; ".join(data.get("fails", [])[:2])


def cmd_list(_args) -> int:
    rows = []
    for eid in list_effects():
        r = load(eid)
        # RECOMPUTE rather than reading the snapshot stored at record time. The
        # stored "machine" string is frozen the moment a review is written, so
        # reading it can never notice a later rebuild - which is exactly the
        # case the stale flag exists to catch.
        machine = machine_result(eid) if r.get("status") == "approved" \
            else r.get("machine", "not verified yet")
        stale = machine.startswith("stale")
        rows.append((eid, r.get("status", "unreviewed"), r.get("reviewedBy", "-"), stale, machine))

    if not rows:
        print("no sub-programs found")
        return 0

    w = max(len(r[0]) for r in rows)
    print("  %-*s  %-9s  %-14s  %s" % (w, "SUB-PROGRAM", "REVIEW", "BY", "MACHINE"))
    for eid, status, who, stale, machine in rows:
        if status == "approved":
            mark = "STALE" if stale else "OK"
        elif status == "rejected":
            mark = "REJECTED"
        else:
            mark = "pending"
        print("  %-*s  %-9s  %-14s  %s" % (w, eid, mark, who, machine))

    approved = sum(1 for r in rows if r[1] == "approved" and not r[3])
    stale_n = sum(1 for r in rows if r[3])
    pending = sum(1 for r in rows if r[1] == "unreviewed")
    failed = [r for r in rows if r[1] == "approved" and r[4].startswith("FAIL")]

    print()
    if failed:
        print("  %d APPROVED effect(s) now FAIL verification:" % len(failed))
        for r in failed:
            print("    %s: %s" % (r[0], r[4]))
        print("  The build moved after the sign-off. Re-review before shipping.")
    if stale_n:
        print("  %d sign-off(s) STALE - the effect was rebuilt after review."
              % stale_n)
        print("  Re-review, then re-record. A sign-off covers the sheets that"
              " existed when it was given.")
    if pending:
        print("  %d sub-program(s) machine-verified and awaiting human review."
              % pending)
        print("  Record with: python tools/review.py <id> --approve"
              " --by \"<name>\" --note \"<what you saw>\"")
    if approved and not pending and not stale_n and not failed:
        print("  %d sub-program(s) reviewed and current." % approved)

    # A stale or failing sign-off is a real inconsistency: exit non-zero so a
    # script that checks review state cannot pass on a stale approval.
    return 1 if (stale_n or failed) else 0


def cmd_record(args) -> int:
    if args.effect not in list_effects():
        print("not a sub-program: %s" % args.effect)
        print("known: %s" % ", ".join(list_effects()))
        return 2
    if not args.by:
        print("--review/--approve require --by <who> so the sign-off is attributable")
        return 2
    if not args.note:
        print("require --note \"<what you saw>\" - a sign-off with no observation "
              "is not a review")
        return 2

    data = load(args.effect)
    data.update({
        "id": args.effect,
        "status": "approved" if args.approve else "rejected",
        "reviewedBy": args.by,
        "reviewedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": args.note,
        "machine": machine_result(args.effect),
    })
    data.pop("rejection", None)
    if not args.approve:
        data["rejection"] = args.note
    p = save(args.effect, data)
    print("%s: %s" % (args.effect, data["status"]))
    print("  by     %s" % args.by)
    print("  note   %s" % args.note)
    print("  machine %s" % data["machine"])
    print("  -> %s" % p)
    if not args.approve:
        print("\n  A rejected sub-program must not be presented as finished. "
              "Fix the effect, rebuild, then re-approve.")
    return 0


def cmd_clear(args) -> int:
    p = review_path(args.effect)
    if p.is_file():
        p.unlink()
        print("%s: review cleared" % args.effect)
    else:
        print("%s: no review recorded" % args.effect)
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", action="store_true", help="show review state of all")
    ap.add_argument("effect", nargs="?")
    ap.add_argument("--review", metavar="NOTE", help="record a human observation")
    ap.add_argument("--approve", action="store_true", help="mark reviewed and accepted")
    ap.add_argument("--reject", action="store_true", help="mark reviewed and refused")
    ap.add_argument("--by", metavar="WHO", help="who reviewed it")
    ap.add_argument("--note", metavar="TEXT", help="what the reviewer observed")
    ap.add_argument("--clear", action="store_true", help="remove the review record")
    args = ap.parse_args(argv)

    if args.list or not args.effect:
        return cmd_list(args)
    if args.clear:
        return cmd_clear(args)
    if args.review or args.reject or args.approve:
        if args.reject:
            args.approve = False
        return cmd_record(args)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
