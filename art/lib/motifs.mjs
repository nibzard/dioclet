// The shared vocabulary of ornament. Board, cards, and tokens all draw
// from these motifs, so every piece reads as the work of one hand.
//
// Light comes from the upper left. Shadows fall to the lower right and
// are built from hatching that follows the form.
import { arcPoints, spline, dist } from "./brush.mjs";
import { text, measure } from "./letters.mjs";

const PI = Math.PI;

// ---------------------------------------------------------------------------
// Line weights. One table so every piece uses the same pencil box.

export const W = {
  hair: { medium: "graphite", width: 0.14, alpha: 0.55, grains: 2 },
  fine: { medium: "graphite", width: 0.24, alpha: 0.75, grains: 3 },
  firm: { medium: "graphite", width: 0.38, alpha: 0.85, grains: 4 },
  bold: { medium: "charcoal", width: 0.6, alpha: 0.9, grains: 5 },
  heavy: { medium: "charcoal", width: 0.95, alpha: 0.95, grains: 6 },
};

const w = (name, extra = {}) => ({ ...W[name], ...extra });

// Fill a closed path with tone: smudge plus form-following hatching.
// value 0..1 is how dark the tone is. Laser printers band on big flat
// grays, so tone stays mostly in hatching.
export function tone(a, pathFn, bounds, value, { angle = PI / 4, cross = false, smudge = true, gap } = {}) {
  if (value <= 0) return;
  if (smudge) a.smudge(pathFn, { alpha: 0.12 * value, blur: 0.8 });
  const g = gap ?? Math.max(0.55, 1.6 - value * 1.2);
  a.hatch(pathFn, bounds, { angle, gap: g, ...W.hair, alpha: 0.35 + 0.4 * value, run: 7 });
  if (cross || value > 0.55) {
    a.hatch(pathFn, bounds, { angle: angle + PI / 2.6, gap: g * 1.3, ...W.hair, alpha: 0.25 + 0.4 * value, run: 6 });
  }
}

// Polygon path helper.
export const poly = (pts) => (c) => {
  c.moveTo(pts[0][0], pts[0][1]);
  for (let i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]);
  c.closePath();
};

export const bbox = (pts, pad = 1) => {
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x0 = Math.min(...xs) - pad, y0 = Math.min(...ys) - pad;
  return [x0, y0, Math.max(...xs) - x0 + pad, Math.max(...ys) - y0 + pad];
};

// Lift a region back to near-white: the way an artist clears a plate for
// lettering with a kneaded eraser.
export function lift(a, pathFn, strength = 0.9) {
  a.erase(pathFn, { strength, blur: 0.5 });
}

// ---------------------------------------------------------------------------
// Laurel. A branch is a gently curving stem with paired leaves; each leaf
// is a pointed oval with a midrib and one side shaded.

export function leaf(a, x, y, ang, len, wid, opts = {}) {
  const ux = Math.cos(ang), uy = Math.sin(ang), nx = -uy, ny = ux;
  const tip = [x + ux * len, y + uy * len];
  const side = (s) => spline([[x, y], [x + ux * len * 0.35 + nx * wid * s, y + uy * len * 0.35 + ny * wid * s],
    [x + ux * len * 0.7 + nx * wid * 0.75 * s, y + uy * len * 0.7 + ny * wid * 0.75 * s], tip], 6);
  const left = side(1), right = side(-1);
  const outline = [...left, ...right.slice().reverse()];
  if (opts.shade !== false) {
    const shadePts = [...right, [x + ux * len * 0.5, y + uy * len * 0.5]];
    a.hatch(poly(shadePts), bbox(shadePts), { angle: ang + 0.9, gap: Math.max(0.28, wid * 0.22), ...W.hair, alpha: 0.6, run: wid * 2 });
  }
  a.stroke(left, w(opts.weight || "fine", { taper: [0.1, 0.3] }));
  a.stroke(right, w(opts.weight || "fine", { taper: [0.1, 0.3] }));
  if (len > 3) a.line([x + ux * len * 0.08, y + uy * len * 0.08], [x + ux * len * 0.8, y + uy * len * 0.8], w("hair", { bow: 0.1 }));
  return outline;
}

// A laurel branch along a curve. side: 1 or -1 for which way leaves lean.
export function laurelBranch(a, pts, { leafLen = 5, leafWid = 1.6, pairs = 8, berries = true, weight = "fine" } = {}) {
  const stem = spline(pts, 12);
  a.stroke(stem, w("firm", { taper: [0.05, 0.4] }));
  // Walk the stem, leaves get smaller toward the tip.
  const total = stem.reduce((s, p, i) => (i ? s + dist(stem[i - 1], p) : 0), 0);
  let acc = 0, k = 0;
  const marks = [];
  for (let i = 1; i < stem.length; i++) {
    acc += dist(stem[i - 1], stem[i]);
    if (acc >= (k + 0.6) * total / (pairs + 0.5)) { marks.push(i); k++; }
  }
  marks.forEach((i, j) => {
    const p = stem[i], q = stem[Math.min(stem.length - 1, i + 1)];
    const ang = Math.atan2(q[1] - p[1], q[0] - p[0]);
    const s = 1 - (j / marks.length) * 0.45;
    leaf(a, p[0], p[1], ang - 0.6 + a.rng.gauss(0.06), leafLen * s, leafWid * s, { weight });
    leaf(a, p[0], p[1], ang + 0.6 + a.rng.gauss(0.06), leafLen * s * 0.95, leafWid * s, { weight });
    if (berries && j % 3 === 1) {
      a.circle(p[0] + Math.cos(ang + 1.6) * leafWid * 0.9, p[1] + Math.sin(ang + 1.6) * leafWid * 0.9, leafWid * 0.32, w("fine"));
    }
  });
  // Terminal leaf.
  const e = stem[stem.length - 1], f = stem[stem.length - 3];
  leaf(a, e[0], e[1], Math.atan2(e[1] - f[1], e[0] - f[0]), leafLen * 0.6, leafWid * 0.6, { weight });
}

// Two branches meeting at the bottom: the corona.
export function laurelWreath(a, cx, cy, r, { leafLen, leafWid, pairs = 9, gap = 0.5, tie = true } = {}) {
  const L = leafLen ?? r * 0.32, Wd = leafWid ?? r * 0.1;
  for (const s of [1, -1]) {
    const pts = [];
    for (let i = 0; i <= 6; i++) {
      const t = PI / 2 + s * (0.18 + (PI - gap - 0.18) * (i / 6));
      pts.push([cx + Math.cos(t) * r, cy + Math.sin(t) * r]);
    }
    laurelBranch(a, pts, { leafLen: L, leafWid: Wd, pairs });
  }
  if (tie) {
    // Ribbon knot at the base.
    a.ellipse(cx, cy + r, r * 0.07, r * 0.05, w("firm"));
    for (const s of [1, -1]) {
      a.stroke(spline([[cx, cy + r], [cx + s * r * 0.12, cy + r * 1.12], [cx + s * r * 0.2, cy + r * 1.24]], 8), w("fine"));
      a.stroke(spline([[cx, cy + r], [cx + s * r * 0.07, cy + r * 1.15], [cx + s * r * 0.1, cy + r * 1.28]], 8), w("hair"));
    }
  }
}

// ---------------------------------------------------------------------------
// Tabula ansata: the plaque with dovetail handles that carries Roman
// inscriptions. Used for every label plate.

export function tabula(a, cx, cy, wdt, hgt, { depth = 0.5, ears = true, lifted = true, weight = "firm" } = {}) {
  const x0 = cx - wdt / 2, x1 = cx + wdt / 2, y0 = cy - hgt / 2, y1 = cy + hgt / 2;
  const ear = ears ? hgt * 0.55 : 0;
  const outline = ears ? [[x0, y0], [x1, y0], [x1 + ear * 0.25, cy - hgt * 0.18], [x1 + ear, y0 - hgt * 0.05],
    [x1 + ear, y1 + hgt * 0.05], [x1 + ear * 0.25, cy + hgt * 0.18], [x1, y1], [x0, y1],
    [x0 - ear * 0.25, cy + hgt * 0.18], [x0 - ear, y1 + hgt * 0.05], [x0 - ear, y0 - hgt * 0.05],
    [x0 - ear * 0.25, cy - hgt * 0.18]] : [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  if (lifted) lift(a, poly(outline), 0.95);
  // Shadow on the lower right edge gives the plaque thickness.
  const sh = [[x1, y1], [x0, y1], [x0 + 0.8, y1 + 0.9], [x1 + 0.8, y1 + 0.9], [x1 + 0.8, y0 + 0.9]];
  a.hatch(poly(sh), bbox(sh), { angle: PI / 3, gap: 0.45, ...W.hair, alpha: 0.6 * depth / 0.5, run: 3 });
  a.polygon(outline, w(weight, { overshoot: 0.3 }));
  const inset = Math.min(1.4, hgt * 0.12);
  a.rect(x0 + inset, y0 + inset, wdt - inset * 2, hgt - inset * 2, w("hair", { overshoot: 0.2 }));
  if (ears) {
    for (const s of [-1, 1]) {
      const ex = s < 0 ? x0 - ear * 0.62 : x1 + ear * 0.62;
      a.circle(ex, cy, Math.max(0.35, hgt * 0.06), w("fine"));
    }
  }
  return outline;
}

// ---------------------------------------------------------------------------
// Rosettes and stars.

export function star(a, cx, cy, r, { points = 8, inner = 0.45, shade = true, weight = "bold" } = {}) {
  const pts = [];
  for (let i = 0; i < points * 2; i++) {
    const ang = -PI / 2 + (i * PI) / points;
    const rr = i % 2 ? r * inner : r;
    pts.push([cx + Math.cos(ang) * rr, cy + Math.sin(ang) * rr]);
  }
  if (shade) {
    // Each ray is a ridge: shade the half away from the light.
    for (let i = 0; i < points * 2; i += 2) {
      const tip = pts[i], next = pts[(i + 1) % pts.length];
      const facet = [[cx, cy], tip, next];
      const ang = Math.atan2(tip[1] - cy, tip[0] - cx);
      const lightness = Math.cos(ang - (-3 * PI / 4));
      if (lightness < 0.3) {
        a.hatch(poly(facet), bbox(facet), { angle: ang + PI / 2, gap: 0.42, ...W.hair, alpha: 0.75, run: r });
      }
      a.line([cx, cy], tip, w("hair", { bow: 0 }));
    }
  }
  a.polygon(pts, w(weight, { overshoot: 0.15 }));
  return pts;
}

export function octagonPts(cx, cy, r, rot = PI / 8) {
  return Array.from({ length: 8 }, (_, i) => [cx + Math.cos(rot + (i * PI) / 4) * r, cy + Math.sin(rot + (i * PI) / 4) * r]);
}

// ---------------------------------------------------------------------------
// Coins and seals: the token language. A beaded rim, a raised field, and
// a device in the middle.

export function coin(a, cx, cy, r, { beads = true, rim = true, worn = 0.2 } = {}) {
  lift(a, (c) => c.arc(cx, cy, r, 0, PI * 2), 0.9);
  // Rim shadow on the lower right, light on the upper left.
  const rimPts = arcPoints(cx, cy, r, r, PI * 0.0, PI * 0.95, 30).concat(arcPoints(cx, cy, r * 0.86, r * 0.86, PI * 0.95, 0, 30));
  a.hatch(poly(rimPts), bbox(rimPts), { angle: -PI / 4, gap: 0.38, ...W.hair, alpha: 0.6, run: r });
  a.circle(cx, cy, r, w("firm", { passes: 1 }));
  if (rim) a.circle(cx, cy, r * 0.86, w("fine"));
  if (beads) {
    const n = Math.max(18, Math.round(r * 3.2));
    for (let i = 0; i < n; i++) {
      if (a.rng() < worn * 0.4) continue;
      const ang = (i / n) * PI * 2;
      a.circle(cx + Math.cos(ang) * r * 0.93, cy + Math.sin(ang) * r * 0.93, r * 0.028 + 0.08, w("hair", { alpha: 0.7 }));
    }
  }
}

// Text set around an arc, the way coin legends run.
export function arcText(a, str, cx, cy, r, capH, { start = -PI / 2, spacing = 0.2, medium = "graphite", weight = 1, inside = false } = {}) {
  const chars = [...str];
  const total = measure(str, capH, { spacing });
  let ang = start - (total / r) / 2;
  for (const ch of chars) {
    const cw = measure(ch, capH, { spacing: 0 });
    const mid = ang + (cw / 2) / r;
    const x = cx + Math.cos(mid) * r, y = cy + Math.sin(mid) * r;
    // Rotate every layer so the letter stands on the circle.
    for (const m of ["wash", "graphite", "charcoal", "chalk"]) {
      const cc = a.sheet.ctx(m);
      cc.save();
      cc.translate(x, y);
      cc.rotate(mid + PI / 2 + (inside ? PI : 0));
    }
    text(a, ch, 0, capH / 2, capH, { medium, weight, serifs: false });
    for (const m of ["wash", "graphite", "charcoal", "chalk"]) a.sheet.ctx(m).restore();
    ang += (cw + spacing * capH) / r;
  }
}

// ---------------------------------------------------------------------------
// Architecture.

// A Doric-Tuscan column with base, fluted shaft, and capital. (cx, top)
// is the top of the abacus; h is the full height.
export function column(a, cx, top, h, { shaft = 0.12, fluted = true } = {}) {
  const sw = h * shaft;                 // shaft width at the base
  const capH = h * 0.08, baseH = h * 0.07;
  const s0 = top + capH, s1 = top + h - baseH;
  const taper = sw * 0.12;
  const shaftPts = [[cx - sw / 2 + taper, s0], [cx + sw / 2 - taper, s0], [cx + sw / 2, s1], [cx - sw / 2, s1]];
  // Shading: the right side of the round shaft turns from the light.
  const shadePts = [[cx + sw * 0.1, s0], [cx + sw / 2 - taper, s0], [cx + sw / 2, s1], [cx + sw * 0.12, s1]];
  a.hatch(poly(shadePts), bbox(shadePts), { angle: PI / 2 + 0.05, gap: 0.5, ...W.hair, alpha: 0.65, run: h });
  const deep = [[cx + sw * 0.32, s0], [cx + sw / 2 - taper, s0], [cx + sw / 2, s1], [cx + sw * 0.34, s1]];
  a.hatch(poly(deep), bbox(deep), { angle: PI / 4, gap: 0.6, ...W.hair, alpha: 0.5, run: 6 });
  a.line(shaftPts[0], shaftPts[3], w("firm", { bow: 0.1 }));
  a.line(shaftPts[1], shaftPts[2], w("firm", { bow: 0.1 }));
  if (fluted) {
    for (let f = -2; f <= 2; f++) {
      const fx = cx + (f / 5.5) * sw;
      a.line([fx + taper * f / 6, s0 + 0.8], [fx, s1 - 0.8], w("hair", { alpha: 0.4, bow: 0.05 }));
    }
  }
  // Capital: abacus slab, echinus curve, necking.
  const ab = sw * 1.5;
  a.rect(cx - ab / 2, top, ab, capH * 0.42, w("firm", { overshoot: 0.2 }));
  a.stroke(spline([[cx - ab * 0.42, top + capH * 0.42], [cx - sw * 0.52, top + capH * 0.85], [cx - sw / 2 + taper, s0]], 6), w("fine"));
  a.stroke(spline([[cx + ab * 0.42, top + capH * 0.42], [cx + sw * 0.52, top + capH * 0.85], [cx + sw / 2 - taper, s0]], 6), w("fine"));
  a.line([cx - sw / 2 + taper, s0], [cx + sw / 2 - taper, s0], w("fine"));
  // Base: torus and plinth.
  a.ellipse(cx, s1 + baseH * 0.3, sw * 0.62, baseH * 0.3, w("fine"));
  a.rect(cx - sw * 0.72, s1 + baseH * 0.55, sw * 1.44, baseH * 0.45, w("firm", { overshoot: 0.2 }));
  const plinthShade = [[cx + sw * 0.1, s1 + baseH * 0.55], [cx + sw * 0.72, s1 + baseH * 0.55], [cx + sw * 0.72, s1 + baseH], [cx + sw * 0.1, s1 + baseH]];
  a.hatch(poly(plinthShade), bbox(plinthShade), { angle: PI / 2, gap: 0.45, ...W.hair, alpha: 0.6, run: 3 });
}

// A round arch opening seen in elevation, with voussoirs.
export function archway(a, cx, base, wdt, hgt, { dark = 0.7, voussoirs = 9 } = {}) {
  const r = wdt / 2, spring = base - (hgt - r);
  const inner = [[cx - r, base], ...arcPoints(cx, spring, r, r, PI, 2 * PI, 24), [cx + r, base]];
  tone(a, poly(inner), bbox(inner), dark, { angle: PI / 3, cross: true });
  a.stroke(inner, w("firm", { taper: [0.02, 0.02] }));
  const R = r + Math.max(0.8, wdt * 0.16);
  a.stroke(arcPoints(cx, spring, R, R, PI, 2 * PI, 24), w("fine"));
  for (let i = 1; i < voussoirs; i++) {
    const t = PI + (i / voussoirs) * PI;
    a.line([cx + Math.cos(t) * r, spring + Math.sin(t) * r], [cx + Math.cos(t) * R, spring + Math.sin(t) * R], w("hair", { bow: 0 }));
  }
}

// A cypress tree, seen from the side: the tall flame of the Dalmatian coast.
export function cypress(a, x, base, h) {
  const wd = h * 0.16;
  const pts = [[x, base - h], [x + wd * 0.32, base - h * 0.72], [x + wd * 0.48, base - h * 0.3], [x + wd * 0.3, base - h * 0.04],
    [x - wd * 0.3, base - h * 0.04], [x - wd * 0.48, base - h * 0.3], [x - wd * 0.32, base - h * 0.72]];
  const outline = spline(pts, 6, true);
  // Foliage: short upward strokes that follow the flame, denser and
  // darker on the right (shadow) side.
  const n = Math.round(h * 11);
  const flicks = [];
  for (let i = 0; i < n; i++) {
    const t = Math.pow(a.rng(), 0.8);          // denser near the base
    const yy = base - h * (0.04 + 0.92 * t);
    const half = wd * 0.48 * (0.35 + 0.65 * Math.sin(Math.PI * Math.min(1, 0.15 + t * 0.85)));
    const xx = x + (a.rng() * 2 - 1) * half;
    const side = (xx - x) / Math.max(0.01, half);
    flicks.push([xx, yy, -PI / 2 + 0.5 + a.rng.gauss(0.16), 0.55 + a.rng() * 0.75, 0.4 + 0.45 * Math.max(0, side)]);
  }
  a.flicks(flicks, { medium: "graphite", width: 0.16, alpha: 0.7, grains: 2 });
  a.stroke(outline, w("fine", { alpha: 0.6, breaks: 0.05 }));
  a.line([x, base - h * 0.03], [x, base + h * 0.04], w("fine"));
}

// A tree seen from above (for the plan view): a scribbled crown with a
// shadow cast to the lower right.
export function treeTop(a, x, y, r) {
  a.smudge((c) => c.ellipse(x + r * 0.35, y + r * 0.35, r * 0.95, r * 0.85, 0, 0, PI * 2), { alpha: 0.18, blur: r * 0.15 });
  const loops = Math.round(r * 2.4);
  for (let i = 0; i < loops; i++) {
    const ang = a.rng() * PI * 2, rr = r * Math.sqrt(a.rng()) * 0.75;
    const px = x + Math.cos(ang) * rr, py = y + Math.sin(ang) * rr;
    const lr = r * (0.18 + a.rng() * 0.16);
    const shadow = (Math.cos(ang - PI / 4) * rr) / r;
    a.stroke(arcPoints(px, py, lr, lr * 0.85, a.rng() * 6, a.rng() * 6 + PI * 1.3, 10),
      w("hair", { alpha: 0.45 + 0.3 * Math.max(0, shadow), wobble: 0.05 }));
  }
  a.stroke(arcPoints(x, y, r, r * 0.95, 0, PI * 2.05, 40), w("fine", { alpha: 0.5, breaks: 0.15 }));
}

// Water: horizontal strokes that thicken in the troughs.
export function waves(a, x0, y0, wdt, hgt, { density = 1 } = {}) {
  const rows = Math.round(hgt / 1.6);
  for (let r = 0; r < rows; r++) {
    const y = y0 + (r + 0.5) * (hgt / rows);
    let x = x0 + a.rng() * 6;
    while (x < x0 + wdt) {
      const len = 3 + a.rng() * 7;
      if (a.rng() < 0.55 * density) {
        const amp = 0.35 + a.rng() * 0.35;
        const pts = [];
        for (let i = 0; i <= 10; i++) {
          const t = i / 10;
          pts.push([x + t * len, y + Math.sin(t * PI * 2) * amp * (1 - Math.abs(t - 0.5))]);
        }
        a.stroke(pts, w("hair", { alpha: 0.45 + 0.2 * a.rng(), taper: [0.3, 0.4] }));
      }
      x += len + 1 + a.rng() * 5;
    }
  }
}

// The Greek key (meander) band between two rules, along a straight edge.
export function meander(a, x0, y0, length, size, { vertical = false } = {}) {
  const u = size / 4;
  const step = size * 1.0;
  const n = Math.floor(length / step);
  const off = (length - n * step) / 2;
  const P = (along, across) => vertical ? [x0 + across, y0 + along] : [x0 + along, y0 + across];
  for (let i = 0; i < n; i++) {
    const s = off + i * step;
    // One key unit: an inward spiral drawn as a single polyline.
    const pts = [[s, size], [s, 0], [s + 3 * u, 0], [s + 3 * u, 3 * u], [s + u, 3 * u], [s + u, u], [s + 2 * u, u], [s + 2 * u, 2 * u]];
    a.stroke(pts.map(([p, q]) => P(p, q)), w("fine", { taper: [0.02, 0.1], wobble: 0.05 }));
    a.line(P(s, size), P(s + step, size), w("fine", { bow: 0.02 }));
  }
  a.line(P(0, -u * 0.8), P(length, -u * 0.8), w("firm", { bow: 0.1 }));
  a.line(P(0, size + u * 0.8), P(length, size + u * 0.8), w("firm", { bow: 0.1 }));
}

// Compass rose drawn as a mosaic star: eight rays, a laurel ring, and the
// four winds lettered in Latin.
export function compassRose(a, cx, cy, r) {
  a.circle(cx, cy, r * 0.98, w("fine"));
  a.circle(cx, cy, r * 0.9, w("hair"));
  for (let i = 0; i < 32; i++) {
    const t = (i / 32) * PI * 2;
    const l = i % 4 === 0 ? 0.1 : 0.05;
    a.line([cx + Math.cos(t) * r * 0.9, cy + Math.sin(t) * r * 0.9], [cx + Math.cos(t) * r * (0.9 - l), cy + Math.sin(t) * r * (0.9 - l)], w("hair", { bow: 0 }));
  }
  star(a, cx, cy, r * 0.55, { points: 4, inner: 0.22, weight: "firm" });
  star(a, cx, cy, r * 0.82, { points: 4, inner: 0.16, weight: "bold" });
  // North gets a solid tip so the direction reads instantly.
  const nTip = [[cx, cy - r * 0.82], [cx + r * 0.16 * Math.SQRT1_2, cy - r * 0.16 * Math.SQRT1_2], [cx, cy], [cx - r * 0.16 * Math.SQRT1_2, cy - r * 0.16 * Math.SQRT1_2]];
  tone(a, poly(nTip), bbox(nTip), 0.95, { cross: true });
  a.circle(cx, cy, r * 0.06, w("firm"));
  text(a, "N", cx, cy - r * 1.06, r * 0.2, { style: "inscribed", medium: "charcoal" });
}

// Draw fn() with every media layer translated and rotated, for vertical
// labels and anything set at an angle.
export function rotated(a, x, y, ang, fn) {
  for (const m of ["wash", "graphite", "charcoal", "chalk"]) {
    const c = a.sheet.ctx(m);
    c.save();
    c.translate(x, y);
    c.rotate(ang);
  }
  try { fn(); } finally { for (const m of ["wash", "graphite", "charcoal", "chalk"]) a.sheet.ctx(m).restore(); }
}
