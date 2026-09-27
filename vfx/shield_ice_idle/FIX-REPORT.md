# Fix report — ice shield migration

Written after repairing `shield_ice_idle` following its move from the game
monorepo into this repo. Three defects, all of them silent. The point of this
report is that **none of them would have announced itself**: the build reported
success, verification reported PASS, and the effect rendered. Read this before
touching the ice builder or adding a linked-asset rig.

---

## 1. The builder wrote outside the repository

**Symptom:** every build wrote to
`D:\Works\source\Keepverse\blender\...` — a path that does not exist.

**Cause:** the script was authored for a monorepo where it lived at
`<repo>/blender/tools/shield_ice_build.py` and computed its root as:

```python
ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "blender" / "assets" / "vfx" / "ice_shield"
```

In this repo the script lives at `<repo>/tools/`, so `parents[2]` overshoots to
`D:\Works\source\Keepverse` — the *parent* of the repository. Adding a
hardcoded `"blender"` segment then pointed at a directory that never existed.

**Why it was silent:** nothing in the build checked that the paths it was about
to write were inside the repo. `asset_dir.mkdir(parents=True)` cheerfully
created the wrong tree.

**Fix:** derive the root from the script's own location by walking up until a
marker identifies the repository, rather than counting parents:

```python
def _find_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "vfx").is_dir() and (parent / "tools").is_dir():
            return parent
    return here.parent.parent
```

**Rule for next time:** never derive a repo root by counting `parents[n]` across
a migration boundary. Anchor on something that identifies the root — a
directory that must exist, a marker file, or an environment variable. If you
must count parents, add an assertion that the resolved path is inside the
repository before writing anything.

---

## 2. The committed sheets did not match the builder that ships with them

This is the one that mattered most, and it is not about paths.

**Symptom:** the migrated `sheets/` measured `sat -0.16` with mean RGB
`(0.72, 0.83, 0.93)` — pale, bright frost glass. Rebuilding from the script in
this repo produced `sat -0.405` with mean RGB `(0.22, 0.48, 0.61)` — deeper,
more saturated blue.

**Proof they were unreproducible, from file timestamps in the monorepo:**

| File | Last written |
|---|---|
| `vfx/shield_ice_idle/sheets/shell.png` | 03:48 |
| `vfx/shield_ice_idle/shield_ice_idle.blend` | 03:43 |
| `tools/shield_ice_build.py` | **05:10** |

The sheets were produced at 03:48. The script that is supposed to produce them
was last edited at 05:10. **The committed sheets were stale relative to the
committed builder** — nobody had rebuilt after the last authoring pass.

**Why it was silent:** nothing compared the sheets against the script. The
sheets were valid PNGs, passed every gate, and rendered a plausible shield.
The only evidence was a two-hour timestamp gap nobody thought to check.

**Fix:** the sheets are now regenerated from the shipped script, and the ice
material gates were recalibrated against the real output (see below). The
rebuilt look is correct — verified against
`lookdev/ice_shield_lookdev.png` and `preview/0012.png`: faceted translucent
dome, fracture lines, continuous arch rim, crown shard, open actor window.

**Rule for next time:** after changing a builder, **rebuild and re-verify before
believing the sheets.** A committed sheet is a build artefact like any other; if
the builder moved, the artefact is stale until proven otherwise. When a
measurement does not match what the source should produce, suspect the artefact
is out of date before suspecting the measurement.

---

## 3. The build printed no completion line, so it was indistinguishable from success

**Symptom:** `tools/build.py` decides a build worked by looking for the build
script's own completion line, because **Blender exits 0 even when it cannot
open or finish a `--python` script**. The fire builders print one. The ice
builder printed `[asset]`, `[vfx]`, `[sheet]`, `[lookdev]` — but nothing that
`build.py` recognised, so a failed ice build would have been reported as failed
for the wrong reason, and a successful one could not be distinguished from a
no-op.

**Fix:** the ice builder now prints the agreed completion line on success:

```
shield_ice_idle: 128 px/unit, 24 frames, kit=assets/vfx/ice_shield, effect=vfx/shield_ice_idle
```

**Rule for next time:** any script `build.py` drives must print the completion
line it greps for. A build that succeeds quietly is a build that will be
trusted when it has not run.

---

## 4. The ice gates were calibrated against the stale sheets

A direct consequence of defect 2, recorded because it changes the numbers
other people will copy.

The first ice calibration used the migrated sheets and set `minSat: -0.30`
around a measured `-0.16`. The rebuilt sheets measure **`-0.405`**, so that
gate failed correct output. The gates are now calibrated against the real
build:

| Property | Stale sheets | Rebuilt | Gate |
|---|---|---|---|
| saturation (α-weighted R−B) | −0.16 | **−0.405** | fails below −0.50 |
| white fraction | 0.17 | **0.000** | fails above 0.35 |
| fill ratio | 0.39 | 0.42 | fails above 0.62 |
| raggedness | 0.41 | 0.40 | fails below 0.18 |
| h/w | 1.06 | 1.11 | fails below 0.40 |

**Rule for next time:** a gate calibrated from an artefact of unknown
provenance is not a calibration. Rebuild first, then measure, then set the
threshold. And keep the measurement in a comment — see
`MATERIAL_GATES["ice"]["$comment"]` in `tools/verify_all.py`.

---

## What was verified after the fix

```
blender --background --factory-startup --python tools/shield_ice_build.py
  exit 0, 17s
  [asset] 3 files: shell 96 faces, rim 672 faces, crystal 36 faces
  [sheet] 3 files, 24 frames at 128px
  [vfx]   shield_ice_idle.blend, 3 libraries, all relative (//..\..\assets\vfx\ice_shield\...)
  shield_ice_idle: 128 px/unit, 24 frames, kit=assets/vfx/ice_shield, effect=vfx/shield_ice_idle

blender --background --factory-startup --python tools/verify_all.py
  exit 0, RESULT: PASS   (6/6 sub-programs, ice loop seam 0.028 = seamless)
```

Scene re-opened in the live Blender session, all three linked libraries
verified to resolve to real files, and the scene re-saved (104.8 KB, not
dirty).

---

## Review state — needs the owner

The earlier sign-off covered the **stale** sheets. The sheets have been
regenerated and the look has changed, so that sign-off no longer applies and
`review.json` has been cleared rather than carried over.

This effect is currently **machine-verified and not human-reviewed.** The
previous record was not carried across the rebuild, because recording it would
have implied someone had looked at output that did not exist at review time.

To record a decision on the new sheets:

```bash
python tools/review.py shield_ice_idle --list
python tools/review.py shield_ice_idle --approve --by "<your name>" --note "<what you saw>"
```

Check `preview/0012.png` and `lookdev/ice_shield_lookdev.png` first — the new
build is deeper and more saturated than the pale version that was signed off.
If the deeper look is not wanted, that is a colour-grading decision to make in
`shield_ice_build.py`, not something to work around in the gates.
