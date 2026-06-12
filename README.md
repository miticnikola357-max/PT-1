# Strawberry Matcha Latte — Hyper-Realistic 3D

A real-time, photorealistic 3D recreation of a layered strawberry matcha latte,
built from the reference photo. Rendered in the browser with [Three.js] using
physically-based materials.

## What it recreates

- **Refractive glass tumbler** — `MeshPhysicalMaterial` with full transmission,
  IOR 1.5, clearcoat and a thick lathe-built base (light bends through it).
- **Layered drink** — strawberry purée (bottom), milk/yoghurt (middle) and the
  large matcha layer (top), with soft blend bands and a glossy meniscus.
- **Garnish** — strawberry slices (flesh, pale core, seeds), a whole berry at
  the rim, and a metallic straw.
- **Setting** — a procedural marble table and a polished silver coaster.
- **Lighting** — image-based environment lighting (`RoomEnvironment`) for real
  reflections/refraction, plus a warm key light with soft shadows and ACES
  filmic tone mapping.

## Run it

No build step. Just serve the folder and open it:

```bash
# any static server works
python3 -m http.server 8000
# then open http://localhost:8000
```

(Opening `index.html` directly also works in most browsers, but a local server
avoids module/CORS quirks.)

**Controls:** drag to orbit · scroll to zoom. The scene auto-rotates.

[Three.js]: https://threejs.org
