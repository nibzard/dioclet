// Plan-view architecture: the palace seen from above, the way an
// eighteenth-century antiquarian surveyed Diocletian's ruins at Spalato.
// Roofs carry tile hatching, courts stay open and light, and every
// building casts a short shadow to the lower right.
import { arcPoints } from "./brush.mjs";
import { W, poly, bbox, tone, octagonPts, treeTop } from "./motifs.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...W[name], ...extra });

// Cast shadow: an L-shaped band below and to the right of a footprint.
export function castShadow(a, pts, depth = 1.6) {
  const sh = pts.map(([x, y]) => [x + depth, y + depth]);
  // Draw the shadow polygon minus the footprint by drawing it first; the
  // roof drawn later covers the overlap with its own marks and erasure.
  a.hatch(poly(sh), bbox(sh), { angle: PI / 4, gap: 0.55, ...W.hair, alpha: 0.55, run: 5 });
  a.erase(poly(pts), { strength: 1, blur: 0.15 });
}

// A gabled hall. ridge "h" runs east-west, "v" north-south. The plane
// facing away from the light (south or east) is hatched darker.
export function hall(a, x, y, wd, ht, { ridge = wd >= ht ? "h" : "v", shadow = 1.4, tiles = true } = {}) {
  const pts = [[x, y], [x + wd, y], [x + wd, y + ht], [x, y + ht]];
  if (shadow) castShadow(a, pts, shadow);
  if (ridge === "h") {
    const my = y + ht / 2;
    const lightPlane = [[x, y], [x + wd, y], [x + wd, my], [x, my]];
    const darkPlane = [[x, my], [x + wd, my], [x + wd, y + ht], [x, y + ht]];
    if (tiles) {
      // Tile rows run down the slope (perpendicular to the ridge).
      a.hatch(poly(lightPlane), bbox(lightPlane, 0), { angle: PI / 2, gap: 1.25, ...W.hair, alpha: 0.5, run: ht, wobble: 0.04 });
      a.hatch(poly(darkPlane), bbox(darkPlane, 0), { angle: PI / 2, gap: 0.72, ...W.hair, alpha: 0.78, run: ht, wobble: 0.04 });
      a.hatch(poly(darkPlane), bbox(darkPlane, 0), { angle: 0.15, gap: 1.55, ...W.hair, alpha: 0.38, run: 6 });
    }
    a.line([x, my], [x + wd, my], w("fine", { bow: 0.1 }));
  } else {
    const mx = x + wd / 2;
    const lightPlane = [[x, y], [mx, y], [mx, y + ht], [x, y + ht]];
    const darkPlane = [[mx, y], [x + wd, y], [x + wd, y + ht], [mx, y + ht]];
    if (tiles) {
      a.hatch(poly(lightPlane), bbox(lightPlane, 0), { angle: 0, gap: 1.25, ...W.hair, alpha: 0.5, run: wd, wobble: 0.04 });
      a.hatch(poly(darkPlane), bbox(darkPlane, 0), { angle: 0, gap: 0.72, ...W.hair, alpha: 0.78, run: wd, wobble: 0.04 });
      a.hatch(poly(darkPlane), bbox(darkPlane, 0), { angle: PI / 2 + 0.15, gap: 1.55, ...W.hair, alpha: 0.38, run: 6 });
    }
    a.line([mx, y], [mx, y + ht], w("fine", { bow: 0.1 }));
  }
  a.rect(x, y, wd, ht, w("firm", { overshoot: 0.35 }));
}

// An open court with an optional colonnade: column bases as small
// circles a little inside the wall line.
export function court(a, x, y, wd, ht, { colonnade = true, spacing = 3.2, paving = true, wall = true } = {}) {
  if (wall) a.rect(x, y, wd, ht, w("fine", { overshoot: 0.3 }));
  if (paving) {
    // Sparse paving joints, very light: the court must read as open air.
    for (let i = 0; i < (wd * ht) / 18; i++) {
      const px = x + 1 + a.rng() * (wd - 2), py = y + 1 + a.rng() * (ht - 2);
      const l = 0.8 + a.rng() * 1.6;
      if (a.rng() < 0.5) a.line([px, py], [px + l, py], w("hair", { alpha: 0.32, bow: 0 }));
      else a.line([px, py], [px, py + l], w("hair", { alpha: 0.32, bow: 0 }));
    }
  }
  if (colonnade) {
    const inset = 2.0;
    const nx = Math.max(2, Math.round((wd - inset * 2) / spacing));
    const ny = Math.max(2, Math.round((ht - inset * 2) / spacing));
    const r = 0.42;
    for (let i = 0; i <= nx; i++) {
      const cx = x + inset + (i / nx) * (wd - inset * 2);
      a.circle(cx, y + inset, r, w("fine"));
      a.circle(cx, y + ht - inset, r, w("fine"));
    }
    for (let j = 1; j < ny; j++) {
      const cy = y + inset + (j / ny) * (ht - inset * 2);
      a.circle(x + inset, cy, r, w("fine"));
      a.circle(x + wd - inset, cy, r, w("fine"));
    }
    // The portico roof behind the columns: a thin hatched band.
    const band = (x0, y0, x1, y1) => {
      const p = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
      a.hatch(poly(p), bbox(p, 0), { angle: PI / 4, gap: 0.8, ...W.hair, alpha: 0.3, run: 5 });
    };
    band(x, y, x + wd, y + inset - 0.7);
    band(x, y + ht - inset + 0.7, x + wd, y + ht);
    band(x, y, x + inset - 0.7, y + ht);
    band(x + wd - inset + 0.7, y, x + wd, y + ht);
  }
}

// A dome in plan: concentric rings, shading on the lower right.
export function dome(a, cx, cy, r, { ribs = 16, lantern = true } = {}) {
  castShadow(a, arcPoints(cx, cy, r, r, 0, PI * 2, 40), r * 0.12);
  const shade = arcPoints(cx, cy, r, r, -PI / 4, PI * 0.75, 30).concat(arcPoints(cx - r * 0.25, cy - r * 0.25, r * 0.8, r * 0.8, PI * 0.75, -PI / 4, 30));
  a.hatch(poly(shade), bbox(shade), { angle: PI / 4 + PI / 2, gap: 0.6, ...W.hair, alpha: 0.6, run: r });
  for (let i = 0; i < ribs; i++) {
    const t = (i / ribs) * PI * 2;
    a.line([cx + Math.cos(t) * r * 0.18, cy + Math.sin(t) * r * 0.18], [cx + Math.cos(t) * r * 0.97, cy + Math.sin(t) * r * 0.97], w("hair", { alpha: 0.35, bow: 0.05 }));
  }
  a.circle(cx, cy, r, w("firm"));
  a.circle(cx, cy, r * 0.62, w("hair", { alpha: 0.4 }));
  if (lantern) a.circle(cx, cy, r * 0.16, w("fine"));
}

// A temple in plan: podium, cella, columns on all sides, steps in front.
export function temple(a, x, y, wd, ht, { front = "n", columns = [4, 6] } = {}) {
  const pts = [[x, y], [x + wd, y], [x + wd, y + ht], [x, y + ht]];
  castShadow(a, pts, 1.6);
  a.rect(x, y, wd, ht, w("firm"));
  // Steps at the front.
  const steps = 5;
  for (let i = 1; i <= steps; i++) {
    const d = i * 0.9;
    if (front === "n") a.line([x + 2, y + d], [x + wd - 2, y + d], w("hair", { bow: 0 }));
    else a.line([x + 2, y + ht - d], [x + wd - 2, y + ht - d], w("hair", { bow: 0 }));
  }
  const sy = front === "n" ? y + steps * 0.9 + 1.5 : y + 1.5;
  const ey = front === "n" ? y + ht - 1.5 : y + ht - steps * 0.9 - 1.5;
  // Cella: the closed room, roofed and hatched.
  const cx0 = x + wd * 0.2, cx1 = x + wd * 0.8;
  const cy0 = front === "n" ? sy + (ey - sy) * 0.35 : sy + 2.5;
  const cy1 = front === "n" ? ey - 2.5 : sy + (ey - sy) * 0.65;
  hall(a, cx0, cy0, cx1 - cx0, cy1 - cy0, { ridge: "v", shadow: 0.6 });
  const [nc, nr] = columns;
  for (let i = 0; i < nc; i++) {
    const px = x + 2 + (i / (nc - 1)) * (wd - 4);
    a.circle(px, sy, 0.7, w("fine"));
    a.circle(px, ey, 0.7, w("fine"));
  }
  for (let j = 1; j < nr - 1; j++) {
    const py = sy + (j / (nr - 1)) * (ey - sy);
    a.circle(x + 2, py, 0.7, w("fine"));
    a.circle(x + wd - 2, py, 0.7, w("fine"));
  }
}

export function roundTemple(a, cx, cy, r, n = 10) {
  dome(a, cx, cy, r * 0.62, { ribs: 10 });
  for (let i = 0; i < n; i++) {
    const t = (i / n) * PI * 2;
    a.circle(cx + Math.cos(t) * r * 0.85, cy + Math.sin(t) * r * 0.85, 0.55, w("fine"));
  }
  a.circle(cx, cy, r, w("fine"));
}

// The octagonal mausoleum of Diocletian: an octagon ringed by columns,
// domed inside.
export function mausoleum(a, cx, cy, r) {
  const outer = octagonPts(cx, cy, r);
  castShadow(a, outer, 1.8);
  a.polygon(outer, w("bold", { overshoot: 0.3 }));
  a.polygon(octagonPts(cx, cy, r * 0.92), w("hair"));
  for (let i = 0; i < 24; i++) {
    const t = (i / 24) * PI * 2;
    const rr = r * 0.86 / Math.cos(((t - PI / 8) % (PI / 4)) - PI / 8);
    a.circle(cx + Math.cos(t) * rr * 0.97, cy + Math.sin(t) * rr * 0.97, 0.5, w("fine"));
  }
  const inner = octagonPts(cx, cy, r * 0.72);
  a.polygon(inner, w("firm"));
  dome(a, cx, cy, r * 0.62, { ribs: 16 });
}

// Scattered garden trees inside a region, kept off a list of keep-out
// circles.
export function garden(a, x, y, wd, ht, count, keepOut = []) {
  let placed = 0, tries = 0;
  while (placed < count && tries < count * 30) {
    tries++;
    const r = 1.6 + a.rng() * 1.6;
    const px = x + r + a.rng() * (wd - 2 * r), py = y + r + a.rng() * (ht - 2 * r);
    if (keepOut.some(([kx, ky, kr]) => Math.hypot(px - kx, py - ky) < kr + r)) continue;
    treeTop(a, px, py, r);
    keepOut.push([px, py, r + 0.6]);
    placed++;
  }
}

// An apsed hall (a basilica or triclinium) with the apse on one side.
export function apseHall(a, x, y, wd, ht, side = "s") {
  hall(a, x, y, wd, ht, { ridge: side === "s" || side === "n" ? "v" : "h" });
  const r = Math.min(wd, ht) * 0.32;
  let cx = x + wd / 2, cy = y + ht, a0 = 0, a1 = PI;
  if (side === "n") { cy = y; a0 = PI; a1 = 2 * PI; }
  if (side === "e") { cx = x + wd; cy = y + ht / 2; a0 = -PI / 2; a1 = PI / 2; }
  if (side === "w") { cx = x; cy = y + ht / 2; a0 = PI / 2; a1 = 1.5 * PI; }
  const pts = arcPoints(cx, cy, r, r, a0, a1, 20);
  tone(a, poly(pts), bbox(pts), 0.35, { angle: PI / 3 });
  a.stroke(pts, w("firm"));
}

export { tone };
