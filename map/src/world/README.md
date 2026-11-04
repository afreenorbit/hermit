# Pixel world — owner: C

- `projection.ts` — equirectangular projection that auto-fits the hosts, zoom/pan, marker spreading
- `drawWorld.ts` — city ground (grass, lakes, roads) or world ground (baked land/sea mask)
- `route.ts` — dotted pixel arcs between consecutive stops
- `worldGrid.ts` — loads `public/data/world-grid.bin` (`scripts/make_pixel_world.py`)
- `WorldPanel.tsx` — canvas, houses with pixel faces, tooltips, controls
