# Ice Shield Visual Match

**Reference:** `blender/assets/vfx/ice_shield/references/frostglass-aegis-concept.png`
**Scene:** `shield_ice_lookdev.blend`
**Render:** `lookdev/ice_shield_lookdev.png`
**Iteration:** 3/3
**Overall:** PARTIAL — the gameplay silhouette and reusable scene are ready to
review, but the render does not yet match the reference's fine luminous frost.

| Area | Rating | Notes |
|---|---|---|
| Camera and framing | Close | Centered orthographic hero view, crown and endpoints remain in frame. |
| Silhouette | Close | Connected top canopy and clear lower actor window; reference has a fuller, more rounded shell. |
| Depth and facets | Close | Faceted shell has a thin solid edge; the 128 px version is readable but simpler than the reference. |
| Material detail | Miss | Procedural frost/fracture variation is present, but the reference's bright irregular crystal veins are much stronger. |
| Lighting and glow | Close | Cool key/fill/rim and Fog Glow are configured; visible bloom is restrained at gameplay scale. |
| Sprite alpha | Match | Transparent production render has zero alpha in the four image corners and in the actor window. |

## Remaining gaps

1. The reference's hand-painted-looking frost and fractured highlights are not
   reproduced by the current procedural shader at 128 px.
2. The opaque look-dev render is a preview only; no plant/zombie proxy or in-game
   compositing test is included.
3. The idle scene is built and packed, but the separate gameplay impact/break
   events remain future work.
