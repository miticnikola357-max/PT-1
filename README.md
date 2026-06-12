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
- **Ice cubes** — refractive rounded cubes floating in the matcha layer.
- **Condensation** — ~320 instanced water droplets clinging to the outer glass,
  with occasional elongated drips for a freshly-poured, chilled look.
- **Setting** — a procedural marble table and a polished silver coaster.
- **Lighting** — image-based environment lighting (`RoomEnvironment`) for real
  reflections/refraction, plus a warm key light with soft shadows and ACES
  filmic tone mapping.

## Run it

**Easiest — just open it in Chrome:** double-click **`strawberry-matcha-latte.html`**.
It's a single self-contained file (Three.js bundled in), so it works straight from
`file://` with no server.

Or serve the source version (`index.html`, which loads from `vendor/`):

```bash
# any static server works
python3 -m http.server 8000
# then open http://localhost:8000
```

To rebuild the standalone file after editing `index.html`:

```bash
npm install esbuild
node build-standalone.mjs
```

**Controls:** drag to orbit · scroll to zoom. The scene auto-rotates.

**Save photo:** click **📸 Save photo** (bottom-right) to render a crisp
~3000px PNG of the current view and download it.

**Record spin:** pick a length from the dropdown (4–16s) and click
**🎞 Record spin** to capture a 360° turntable as a video (MP4 where
supported, otherwise WebM). The rotation ends one frame short of a full
revolution so the clip **loops seamlessly**. Recording uses the canvas
`captureStream` + `MediaRecorder` API — best in Chrome/Edge.

[Three.js]: https://threejs.org
