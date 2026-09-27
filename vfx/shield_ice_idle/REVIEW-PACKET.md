# Review packet — shield_ice_idle (rebuilt sheets)

The sheets were regenerated from the builder in this repo. They are **not** the
sheets that were previously signed off, so that sign-off no longer applies and
`review.json` was cleared rather than carried over.

This packet is the evidence for the review decision. An agent gathered it; the
decision is the owner's.

## What changed and why

The committed sheets were **stale** — written 03:48, while the builder in the
repo was last edited 05:10. They were not reproducible from the shipped script.
See [FIX-REPORT.md](FIX-REPORT.md).

## Measured difference, per layer

Frame 4, 128px cell, α-weighted.

| Layer | | coverage | sat (R−B) | mean RGB | peak α |
|---|---|---|---|---|---|
| `shell` | approved (stale) | 0.167 | −0.21 | (0.72, 0.83, 0.93) | 0.79 |
| | **rebuilt** | 0.188 | **−0.40** | **(0.22, 0.48, 0.62)** | 1.00 |
| `rim` | approved (stale) | 0.044 | −0.07 | (0.94, 0.97, 1.00) | 1.00 |
| | **rebuilt** | 0.049 | **−0.48** | **(0.33, 0.70, 0.82)** | 1.00 |
| `crystal` | approved (stale) | 0.009 | −0.22 | (0.70, 0.82, 0.91) | 1.00 |
| | **rebuilt** | 0.019 | **−0.34** | **(0.31, 0.54, 0.65)** | 1.00 |

Coverage is essentially unchanged, so **the silhouette and the amount of effect
are the same.** What changed is colour: the rebuild is roughly **53–64% of the
luminance** of the approved version, and considerably more saturated.

## What it looks like

`compare_shell.png` (regenerate with the snippet below). Left = previously
approved, right = rebuilt. Top row over a lawn green, bottom row over the
viewer's dark background.

The practical difference on a bright background: the **approved** version is
close to white and loses contrast against the lawn. The **rebuilt** version
stays blue and reads as ice.

That matters here specifically. `docs/architecture/vfx-ssot.md` in the game
repo records a live finding that additive and pale effects **wash out to
near-white over the bright lawn** — the same failure this improvement avoids.
The game lawn is the worst case for a pale sprite.

## To regenerate the comparison

```python
# in Blender, via the MCP or --python
import bpy, numpy as np
OLD = r"D:\Works\source\plant-vs-zombie-rise-of-summoner\blender\vfx\shield_ice_idle\sheets\shell.png"
NEW = r"D:\Works\source\Keepverse\gk-assets\vfx\shield_ice_idle\sheets\shell.png"
def tile(p, fi=3, cell=128, cols=6):
    img = bpy.data.images.load(p); img.reload()
    w, h = img.size
    buf = np.empty(w*h*4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    a = buf.reshape(h, w, 4).copy(); bpy.data.images.remove(img)
    r, c = divmod(fi, cols)
    return a[r*cell:(r+1)*cell, c*cell:(c+1)*cell, :]
def over(bg, t):
    a = t[..., 3:4]
    o = np.zeros_like(bg); o[..., :3] = t[..., :3]*a + bg[..., :3]*(1-a); o[..., 3] = 1.0
    return o
def bg(r, g, b):
    x = np.zeros((128,128,4), dtype=np.float32); x[...,0]=r; x[...,1]=g; x[...,2]=b; x[...,3]=1.0
    return x
ot, nt = tile(OLD), tile(NEW)
stack = np.concatenate([
    np.concatenate([over(bg(0.29,0.48,0.18), ot), over(bg(0.29,0.48,0.18), nt)], axis=1),
    np.concatenate([over(bg(0.06,0.07,0.09), ot), over(bg(0.06,0.07,0.09), nt)], axis=1),
])
o = bpy.data.images.new("cmp", stack.shape[1], stack.shape[0], alpha=True)
o.pixels.foreach_set(stack[::-1].ravel())
o.filepath_raw = "compare_shell.png"; o.file_format = "PNG"; o.save()
```

## Also worth looking at

- `preview/0012.png` — the rebuilt composite over transparency
- `lookdev/ice_shield_lookdev.png` — the opaque beauty render

## Decision

To accept the rebuilt sheets:

```bash
python tools/review.py shield_ice_idle --approve --by "<your name>" \
  --note "rebuilt sheets, deeper blue, reads better on lawn"
```

To go back to the paler look, that is a **colour decision in
`shield_ice_build.py`**, not something to work around by loosening the
verification gates. The gates exist to catch a regression, and relaxing them to
restore an appearance would disable exactly the check that caught the stale
sheets in the first place.

## Note on the stale sheets

The previously approved sheets still exist in the game monorepo at
`D:\Works\source\plant-vs-zombie-rise-of-summoner\blender\vfx\shield_ice_idle\sheets\`
(written 03:48). They are kept there deliberately, since they are the only
record of the look that was signed off.
