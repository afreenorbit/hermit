/** toCanvas / toSVG — same grid, two surfaces. Always integer scale. Owner: C. */
import { EMPTY, SWEETIE16, type PixelGrid } from '../palette';

export interface DrawOptions {
  /** Offset in grid cells. */
  x?: number;
  y?: number;
  /** Per-cell alpha, e.g. to dim every piece but the hovered one. */
  alpha?: (index: number) => number;
  /** Swap palette indices, e.g. to recolour a sprite. */
  remap?: (paletteIndex: number) => number;
}

export function toCanvas(
  grid: PixelGrid,
  ctx: CanvasRenderingContext2D,
  scale: number,
  opts: DrawOptions = {},
): void {
  const s = Math.max(1, Math.round(scale));
  const ox = opts.x ?? 0;
  const oy = opts.y ?? 0;
  ctx.imageSmoothingEnabled = false;
  for (let y = 0; y < grid.h; y++) {
    for (let x = 0; x < grid.w; x++) {
      const i = y * grid.w + x;
      let v = grid.cells[i] ?? EMPTY;
      if (v === EMPTY) continue;
      if (opts.remap) v = opts.remap(v);
      ctx.globalAlpha = opts.alpha ? opts.alpha(i) : 1;
      ctx.fillStyle = SWEETIE16[v] ?? '#000';
      ctx.fillRect((ox + x) * s, (oy + y) * s, s, s);
    }
  }
  ctx.globalAlpha = 1;
}

/** Paint a grid into an RGBA buffer at 1 pixel per cell. */
export function toImageData(grid: PixelGrid, target: ImageData, ox = 0, oy = 0): void {
  for (let y = 0; y < grid.h; y++) {
    const ty = oy + y;
    if (ty < 0 || ty >= target.height) continue;
    for (let x = 0; x < grid.w; x++) {
      const tx = ox + x;
      if (tx < 0 || tx >= target.width) continue;
      const v = grid.cells[y * grid.w + x] ?? EMPTY;
      if (v === EMPTY) continue;
      const rgb = RGB[v];
      if (!rgb) continue;
      const o = (ty * target.width + tx) * 4;
      target.data[o] = rgb[0];
      target.data[o + 1] = rgb[1];
      target.data[o + 2] = rgb[2];
      target.data[o + 3] = 255;
    }
  }
}

export const RGB: ReadonlyArray<readonly [number, number, number]> = SWEETIE16.map((hex) => [
  parseInt(hex.slice(1, 3), 16),
  parseInt(hex.slice(3, 5), 16),
  parseInt(hex.slice(5, 7), 16),
]);

/** Crisp SVG: horizontal runs of one colour merged into one rect. */
export function toSVG(grid: PixelGrid, scale = 1): string {
  const rects: string[] = [];
  for (let y = 0; y < grid.h; y++) {
    let x = 0;
    while (x < grid.w) {
      const v = grid.cells[y * grid.w + x] ?? EMPTY;
      let run = 1;
      while (x + run < grid.w && grid.cells[y * grid.w + x + run] === v) run++;
      if (v !== EMPTY) {
        rects.push(
          `<rect x="${x * scale}" y="${y * scale}" width="${run * scale}" height="${scale}" fill="${SWEETIE16[v]}"/>`,
        );
      }
      x += run;
    }
  }
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${grid.w * scale}" height="${grid.h * scale}" viewBox="0 0 ${grid.w * scale} ${grid.h * scale}" shape-rendering="crispEdges">${rects.join('')}</svg>`;
}

/** Runs of identical cells, for React SVG rendering without a string. */
export function toRuns(grid: PixelGrid): Array<{ x: number; y: number; w: number; c: number }> {
  const runs: Array<{ x: number; y: number; w: number; c: number }> = [];
  for (let y = 0; y < grid.h; y++) {
    let x = 0;
    while (x < grid.w) {
      const v = grid.cells[y * grid.w + x] ?? EMPTY;
      let run = 1;
      while (x + run < grid.w && grid.cells[y * grid.w + x + run] === v) run++;
      if (v !== EMPTY) runs.push({ x, y, w: run, c: v });
      x += run;
    }
  }
  return runs;
}
