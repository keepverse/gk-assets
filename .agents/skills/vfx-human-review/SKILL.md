---
name: vfx-human-review
description: Record, check and clear the optional human sign-off for a VFX sub-program in gk-assets, and report which sub-programs are complete. Use when asked to record a review, check review status, mark an effect approved or rejected, find out what is finished, or decide whether something is ready to ship. Triggers on "record review", "mark approved", "is it reviewed", "review status", "what's finished", "is it done", "sign off", "reject the effect".
---

# Human review (optional sign-off)

`tools/verify_all.py` passing means **built and verified**: right shape, size,
colour, frame count, no collapsed frames, closed loop. **That is finished
work.** Nothing in the build or verification path consults review state, and no
sub-program is blocked without a sign-off.

A sign-off is *optional extra assurance* — someone looked at it moving and
recorded a judgement. The two are tracked separately only so they are never
confused.

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
python tools/review_ui.py                      # browser: sign-off bar, opens viewer
python tools/review_ui.py --list               # state only, no server
python tools/review.py --list                  # state only, no server
python tools/review.py <id> --approve --by "who" --note "what you saw"
python tools/review.py <id> --reject  --by "who" --note "what is wrong"
python tools/review.py <id> --clear
```

Both `--by` and `--note` are required. A sign-off with no attribution, or with
no observation, is not a review — the tool refuses both, and so does the
review UI server.

## Reading the state

`--list` reports one of:

| State | Meaning |
|---|---|
| `done` | Built and verified. **Finished.** No sign-off. |
| `done+reviewed` | Built, verified, and a person signed off. |
| `STALE` | Builds and verifies, but was rebuilt after the sign-off. |
| `REJECTED` | A person looked and refused it. |
| `not built` | No sheets yet. Run `tools/build.py`. |
| `verify FAIL` | Broken. Not finished. |

Only `STALE` and `verify FAIL` exit non-zero. `done` exits 0 — absence of a
sign-off is not a problem to fix.

## What a good note says

Not "looks good". Something a later reader can act on:

- "reads as a barrier at 1x on the lawn; the rim is the only thing that sells
  the edge" — tells the next person which layer carries the effect.
- "at 2x the flame tongues are visible but the core is a flat blob" — a
  specific, fixable defect.
- "the break is too abrupt after frame 20, embers vanish" — where to look.

## Reporting status

```bash
python tools/review.py --list
```

Report **completeness** first, sign-off second:

> All 6 sub-programs are built and verified. None carries a human sign-off,
> which is optional.

Never say something is "pending review" or "awaiting sign-off" as though it
were unfinished. If the build moved after a sign-off, say that instead — that
is the case worth flagging.

