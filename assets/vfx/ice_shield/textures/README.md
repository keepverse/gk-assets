# Ice Shield source textures

This directory holds additional reusable Ice Shield source images. The
`T_IceShield_FrostPanels_Alternate.png` image is a generated frost-panel variant
preserved from the asset-generation session (source
`exec-03eb685f-7669-4d83-b3eb-9c8243c15ce0.png`). It is an available art
source, **not currently assigned** to a V3 shield material.

Other generated images from that session were already present byte-for-byte:

- `../v2/textures/T_IceShield_FrostVeins_RGBA_v2.png` matches
  `exec-98855cc5-6b8f-4ab8-9291-d0aa134c8fff.png`.
- `../v4/textures/T_IceShield_FrostPanels_v4_generated.png` matches
  `exec-81c839c3-413d-458d-be56-8bb53c0a597f.png`.

Keep the versioned textures beside their existing object-kit sources; moving
them would break those Blender files' relative paths. The v2 shell object kit
loads its frost-vein image from the tracked `v2/textures/` source file.
