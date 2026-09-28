# Earth Shield Reference and Ice Shield Combat Plan

> **Status: machine-verified; human visual review pending.**
> This brief captures the Earth Shield pattern and records the Ice Mirror combat
> prototypes built from the saved idle and impact scenes.

## Earth Shield as the reference

The Earth idle establishes the effect around an actor-sized empty center. Its
deliverable is a 72-frame loop at 12 fps, sampled from a six-second Blender
cycle. A light, textured mineral dome reveals upward from the ground, expands
over source frames 3–32, holds through frame 82, retracts from the crown over
frames 86–106, and then rests hidden. Three smaller textured stones make one
full orbit every six seconds, independently of the dome. Combat responses keep
the same centered, actor-free composition and add a short, legible event.

| Response | Earth behavior | Ice direction to explore |
|---|---|---|
| **Impact** (24 frames) | A compact contact ring, brief fracture flare, and a few chips peak early and clear quickly. | A concentrated mirror fracture opens at the hit point. A few bevelled facets lift and tilt toward camera, then clear; keep the damage local rather than filling the hex with a web. |
| **Absorb** (36 frames) | The incoming stone reaches near-center contact first. The pulse starts after contact, then draws the stone and a few fragments inward. | Let the projectile touch first, then freeze it at the contact point. Draw it inward or dissolve it into a few frost flecks after the screen reacts. |
| **Break** (36 frames) | A segmented dome fracture releases a restrained number of panels, stones, and chips. | Break the screen into a few broad mirror facets with sparse small shards. Keep these fragments distinct from the three hero crystals; avoid a spiderweb pattern. |
| **Penetrate** (36 frames) | Separate entry and exit cracks appear at different times, each with a brief glow. | Use two distinct, angular puncture fractures and brief cold flashes at entry and exit. Preserve the hex silhouette between them. |
| **Deflect** (24 frames) | A tight shock arc redirects the incoming stone with a short trail and a few chips. | Flash like a prism at contact and bend the projectile away with a short icy trail. Keep the hit concentrated rather than explosive. |

These frame counts are Earth references, not locked Ice timings. The Earth idle
is machine-verified; its README marks human review as pending. The Earth combat
README files also describe their visual review as pending, so this is a design
reference rather than a claim that every Earth response is approved.

## Ice idle identity to preserve

The existing Ice mirror idle provides the baseline for every proposal here:

- Exactly **three major crystals** stay on their three prepared vertical bubble
  lanes. They bob up and down; they do not orbit or fall in rows.
- Five minor shards and eight snowflakes remain secondary companions. Combat
  animation should not duplicate the hero crystals or turn the companions into
  a bundle of extra large crystals.
- The shield body is one transparent, cold-blue, equal-sided hex screen. Its
  lower vertex points toward the ground. Keep the face clean: no spokes,
  inner rings, or spiderweb cracks.
- The idle is a 72-frame loop at 12 fps. Its screen grows from actor center
  through frame 9, holds through frame 27, then fades at full size by frame 42;
  it stays hidden through frame 72. The three crystals bob throughout.
- Combat sprites should share the actor-centered composition and visual
  language. The actor remains omitted from the rendered asset.

## Ice combat set

1. **Impact — saved prototype.** The actor-free one-shot uses a localized angular
   fracture and a few small 3D mirror facets that separate from the screen,
   catch light, and clear. The same response is integrated into the idle scene,
   where exactly three hero crystals continue their vertical bob.
2. **Deflect — 24 frames at 24 fps.** One shard reaches an upper-right contact,
   flashes, bends back up and away, then clears with a short icy trail.
3. **Absorb — 36 frames at 24 fps.** The shard touches first, pauses through
   the cold lock, then dissolves inward into four small frost flecks.
4. **Penetrate — 36 frames at 24 fps.** One shard crosses from left to right.
   Separate angular punctures mark entry at frame 8 and exit at frame 20.
5. **Break — 36 frames at 24 fps.** A contact flash releases three broad
   textured mirror panels and three small chips; the screen clears before the
   panels drift out.

The combat builders load the saved Ice Mirror idle scene, hide only the idle
impact layer, hold the same ground-pointing hex at full size, and add one local
event layer. Each scene validates exactly three distinct prepared hero
crystals, five minor shards, and eight snowflakes before rendering. The crystals
keep their vertical bubble motion through every response. All four remain WIP
until a person reviews them in motion at gameplay scale.
