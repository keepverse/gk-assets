---
name: vfx-human-review
description: Record, check and clear the HUMAN visual sign-off for a VFX sub-program in gk-assets. Use when asked to record a review, check what has been reviewed, mark an effect approved or rejected, or find out whether a sub-program is ready to ship. Triggers on "record review", "mark approved", "is it reviewed", "review status", "sign off", "reject the effect".
---

# Human visual review

`tools/verify_all.py` proves a sprite is the right shape, size, colour, frame
count and that its loop closes. It cannot tell you whether the effect *reads* as
a shield in motion on a bright lawn. That is a human judgement, and it is
tracked separately so the two are never confused.

## The rule

**Agents do not approve.** Do not run `--approve` or `--reject`, and never
hand-write a `review.json`.

An agent can measure everything about a sprite and still be wrong about whether
it looks right. Approving on the owner's behalf, or worse on your own
judgement, destroys the only signal the record exists to carry.

If the owner tells you an effect works, you may record **their** decision:

```bash
python tools/review.py <id> --approve --by "<their name>" --note "<their words>"
```

Attributing it to yourself would misstate who reviewed it.

## Commands

```bash
python tools/review.py --list          # state of every sub-program
python tools/review.py <id> --approve --by "who" --note "what you saw"
python tools/review.py <id> --reject  --by "who" --note "what is wrong"
python tools/review.py <id> --clear    # remove the record
```

Both `--by` and `--note` are required. A sign-off with no attribution, or with
no observation, is not a review — the tool refuses both.

## What a good note says

Not "looks good". Something a later reader can act on:

- "reads as a barrier at 1x on the lawn; the rim is the only thing that sells
  the edge" — tells the next person which layer carries the effect.
- "at 2x the flame tongues are visible but the core is a flat blob" — a
  specific, fixable defect.
- "the break is too abrupt after frame 20, embers vanish" — where to look.

## Reading the record

`vfx/<id>/review.json`:

```json
{
  "status": "approved",
  "reviewedBy": "who",
  "reviewedAt": "2026-09-27T08:47:24+00:00",
  "note": "what the reviewer observed",
  "machine": "pass"
}
```

`machine` is what `verify_all` concluded at review time, cached in
`vfx/<id>/.verify.json`. It reports:

- `pass` — verified, and the sheets have not changed since
- `stale (sheets changed since last verify)` — rebuild, then re-verify
- `FAIL: ...` — the effect was approved while failing verification
- `not verified yet` — no cached run

If `machine` is `stale` or `FAIL`, say so when reporting status. An approval on
a failing build is a discrepancy the owner needs to know about, not something to
smooth over.

## Reporting status

```bash
python tools/review.py --list
```

Distinguish clearly in any report:

- **machine-verified** — `verify_all` passes. Says nothing about how it looks.
- **human-reviewed** — a person signed off. This is the ship signal.

A sub-program can be verified and unreviewed (most of them right now), or
reviewed and stale. Never collapse the two into "done".
