// Hand-drawn Roman capitals. No font files: each letter is a set of pen
// paths in a box one cap-height tall (y = 0 at the top, 1 at the
// baseline), drawn with a broad nib held at a fixed angle, the way the
// letter-cutters of the Empire laid out an inscription before carving.
//
// Two styles:
//   "inscribed" - for titles. The nib sweep is filled by dense pencil
//                 hatching and outlined, so the letter looks drawn and
//                 then shaded by hand. Serifs are added at stem ends.
//   "pencil"    - for small labels. One tapered stroke per path with
//                 mild thick-thin contrast.
import { arcPoints, spline } from "./brush.mjs";

const PI = Math.PI;
const L = (...pts) => pts;
const arc = (cx, cy, rx, ry, a0, a1) => arcPoints(cx, cy, rx, ry, a0, a1, 28);
const S = (...pts) => spline(pts, 8);

// Letters keep classical proportions: round letters wide, E F L S narrow.
export const GLYPHS = {
  A: [0.8, [L([0, 1], [0.4, 0], [0.8, 1]), L([0.17, 0.62], [0.63, 0.62])]],
  B: [0.6, [L([0, 1], [0, 0]), [[0, 0], ...arc(0.33, 0.24, 0.24, 0.24, -PI / 2, PI / 2), [0, 0.48]],
    [[0, 0.48], ...arc(0.35, 0.74, 0.26, 0.26, -PI / 2, PI / 2), [0, 1]]]],
  C: [0.82, [arc(0.46, 0.5, 0.46, 0.5, -0.72, -2 * PI + 0.62)]],
  D: [0.82, [L([0, 0], [0, 1]), [[0, 0], ...arc(0.32, 0.5, 0.5, 0.5, -PI / 2, PI / 2), [0, 1]]]],
  E: [0.56, [L([0.56, 0], [0, 0], [0, 1], [0.6, 1]), L([0, 0.49], [0.46, 0.49])]],
  F: [0.54, [L([0.56, 0], [0, 0], [0, 1]), L([0, 0.49], [0.46, 0.49])]],
  G: [0.88, [arc(0.46, 0.5, 0.46, 0.5, -0.72, -2 * PI + 0.28), L([0.58, 0.6], [0.9, 0.6], [0.9, 0.97])]],
  H: [0.74, [L([0, 0], [0, 1]), L([0.74, 0], [0.74, 1]), L([0, 0.5], [0.74, 0.5])]],
  I: [0.0, [L([0, 0], [0, 1])]],
  J: [0.36, [[[0.36, 0], ...arc(0.18, 0.78, 0.18, 0.22, 0, PI)]]],
  K: [0.66, [L([0, 0], [0, 1]), L([0.62, 0], [0, 0.56]), L([0.2, 0.4], [0.68, 1])]],
  L: [0.55, [L([0, 0], [0, 1], [0.56, 1])]],
  M: [0.92, [L([0, 1], [0.07, 0], [0.46, 1], [0.85, 0], [0.92, 1])]],
  N: [0.74, [L([0, 1], [0, 0], [0.74, 1], [0.74, 0])]],
  O: [0.96, [arc(0.48, 0.5, 0.48, 0.5, -PI / 2, 1.5 * PI + 0.05)]],
  P: [0.6, [L([0, 1], [0, 0]), [[0, 0], ...arc(0.33, 0.26, 0.26, 0.26, -PI / 2, PI / 2), [0, 0.52]]]],
  Q: [0.96, [arc(0.48, 0.5, 0.48, 0.5, -PI / 2, 1.5 * PI + 0.05), L([0.52, 0.86], [0.98, 1.12])]],
  R: [0.66, [L([0, 1], [0, 0]), [[0, 0], ...arc(0.33, 0.26, 0.26, 0.26, -PI / 2, PI / 2), [0, 0.52]],
    L([0.3, 0.52], [0.68, 1])]],
  S: [0.58, [S([0.54, 0.13], [0.38, 0.01], [0.13, 0.04], [0.04, 0.22], [0.18, 0.41], [0.42, 0.55],
    [0.57, 0.75], [0.47, 0.96], [0.2, 1.0], [0.01, 0.87])]],
  T: [0.72, [L([0, 0], [0.72, 0]), L([0.36, 0], [0.36, 1])]],
  U: [0.74, [[[0, 0], ...arc(0.37, 0.66, 0.37, 0.34, PI, 0), [0.74, 0]]]],
  V: [0.78, [L([0, 0], [0.39, 1], [0.78, 0])]],
  W: [1.08, [L([0, 0], [0.27, 1], [0.54, 0.12], [0.81, 1], [1.08, 0])]],
  X: [0.7, [L([0, 0], [0.7, 1]), L([0.7, 0], [0, 1])]],
  Y: [0.72, [L([0, 0], [0.36, 0.52], [0.72, 0]), L([0.36, 0.52], [0.36, 1])]],
  Z: [0.68, [L([0.04, 0], [0.66, 0], [0, 1], [0.7, 1])]],
  0: [0.6, [arc(0.3, 0.5, 0.3, 0.5, -PI / 2, 1.5 * PI + 0.05)]],
  1: [0.46, [L([0.06, 0.16], [0.26, 0], [0.26, 1]), L([0.04, 1], [0.48, 1])]],
  2: [0.6, [S([0.03, 0.22], [0.16, 0.03], [0.35, 0], [0.53, 0.13], [0.52, 0.33], [0.3, 0.6], [0, 1]), L([0, 1], [0.6, 1])]],
  3: [0.58, [S([0.03, 0.1], [0.25, 0], [0.5, 0.08], [0.5, 0.28], [0.24, 0.46]),
    S([0.24, 0.46], [0.55, 0.6], [0.56, 0.85], [0.3, 1], [0, 0.9])]],
  4: [0.64, [L([0.46, 1], [0.46, 0], [0, 0.68], [0.64, 0.68])]],
  5: [0.58, [L([0.55, 0], [0.1, 0], [0.05, 0.43]), S([0.05, 0.43], [0.3, 0.38], [0.55, 0.55], [0.55, 0.82], [0.3, 1], [0, 0.92])]],
  6: [0.58, [S([0.5, 0.05], [0.3, 0], [0.08, 0.2], [0, 0.6], [0.1, 0.92], [0.3, 1], [0.52, 0.88], [0.55, 0.65],
    [0.4, 0.48], [0.15, 0.5], [0.02, 0.65])]],
  7: [0.58, [L([0, 0], [0.58, 0], [0.2, 1])]],
  8: [0.56, [arc(0.28, 0.25, 0.23, 0.25, -PI / 2, 1.5 * PI), arc(0.28, 0.73, 0.28, 0.27, -PI / 2, 1.5 * PI)]],
  9: [0.58, [S([0.05, 0.95], [0.25, 1], [0.47, 0.8], [0.55, 0.4], [0.45, 0.08], [0.25, 0], [0.03, 0.12],
    [0, 0.35], [0.15, 0.52], [0.4, 0.5], [0.53, 0.35])]],
  ".": [0.14, [L([0.04, 0.9], [0.08, 0.99])]],
  ",": [0.12, [L([0.08, 0.92], [0.02, 1.12])]],
  "'": [0.1, [L([0.07, 0], [0.03, 0.24])]],
  "-": [0.38, [L([0, 0.56], [0.38, 0.56])]],
  "·": [0.14, [L([0.06, 0.5], [0.08, 0.54])]],
  "+": [0.54, [L([0, 0.56], [0.54, 0.56]), L([0.27, 0.3], [0.27, 0.82])]],
  ":": [0.12, [L([0.05, 0.3], [0.07, 0.35]), L([0.05, 0.93], [0.07, 0.98])]],
  "/": [0.42, [L([0.42, -0.04], [0, 1.04])]],
  "(": [0.22, [arc(0.42, 0.5, 0.4, 0.58, PI * 0.72, PI * 1.28)]],
  ")": [0.22, [arc(-0.2, 0.5, 0.4, 0.58, -PI * 0.28, PI * 0.28)]],
  " ": [0.36, []],
};

const SPACING = 0.2;           // gap between letters, in cap heights

export function measure(text, capH, { spacing = SPACING } = {}) {
  let w = 0;
  const chars = [...text.toUpperCase()];
  chars.forEach((ch, i) => {
    const g = GLYPHS[ch] || GLYPHS[" "];
    w += g[0] * capH + (i < chars.length - 1 ? spacing * capH + (ch === "I" ? 0.08 * capH : 0) : 0);
  });
  return w;
}

// Polygon of a broad nib dragged along a segment, wound consistently so
// a nonzero fill unions all of them.
function nibQuad(a, b, nx, ny) {
  const q = [[a[0] - nx, a[1] - ny], [b[0] - nx, b[1] - ny], [b[0] + nx, b[1] + ny], [a[0] + nx, a[1] + ny]];
  let area = 0;
  for (let i = 0; i < 4; i++) {
    const p = q[i], r = q[(i + 1) % 4];
    area += p[0] * r[1] - r[0] * p[1];
  }
  return area < 0 ? q.reverse() : q;
}

// Draw text. (x, y) is the anchor on the baseline; align is left, center,
// or right. Returns the drawn width.
export function text(artist, str, x, y, capH, opts = {}) {
  const o = {
    align: "center", style: "pencil", medium: "graphite", weight: 1, spacing: SPACING,
    nibAngle: -0.55, alpha: 0.85, serifs: true, track: 0, ...opts,
  };
  const width = measure(str, capH, { spacing: o.spacing + o.track });
  let cx = o.align === "center" ? x - width / 2 : o.align === "right" ? x - width : x;
  const top = y - capH;
  const rng = artist.rng;
  // Each letter sits a hair off the line and leans a hair, like a sign
  // painter's capitals.
  for (const ch of [...str.toUpperCase()]) {
    const g = GLYPHS[ch] || GLYPHS[" "];
    const lean = rng.gauss(0.012), dy = rng.gauss(0.012) * capH, sc = 1 + rng.gauss(0.01);
    const tf = ([px, py]) => {
      const lx = px * capH * sc, ly = py * capH * sc;
      return [cx + lx + (capH - ly) * lean, top + ly + dy];
    };
    const strokes = g[1].map((path) => path.map(tf));
    if (o.style === "inscribed") drawInscribed(artist, strokes, capH, o);
    else drawPencil(artist, strokes, capH, o);
    cx += g[0] * capH + (o.spacing + o.track) * capH + (ch === "I" ? 0.08 * capH : 0);
  }
  return width;
}

function serifTicks(strokes, capH, top, base) {
  // Small horizontal serifs where a stem meets the cap line or baseline.
  const ticks = [];
  const tol = capH * 0.06;
  for (const s of strokes) {
    for (const [end, next] of [[s[0], s[1]], [s[s.length - 1], s[s.length - 2]]]) {
      if (!next) continue;
      const dx = next[0] - end[0], dy = next[1] - end[1];
      const steep = Math.abs(dy) > Math.abs(dx) * 1.2;
      if (!steep) continue;
      if (Math.abs(end[1] - top) < tol || Math.abs(end[1] - base) < tol) ticks.push(end);
    }
  }
  return ticks;
}

function drawPencil(artist, strokes, capH, o) {
  const w = Math.max(0.12, capH * 0.11) * o.weight;
  for (const s of strokes) {
    artist.stroke(s, { medium: o.medium, width: w, alpha: o.alpha, grains: 3,
      wobble: capH * 0.012, taper: [0.06, 0.1] });
  }
  if (o.serifs && capH >= 4) {
    const ys = strokes.flat().map((p) => p[1]);
    const top = Math.min(...ys), base = Math.max(...ys);
    for (const p of serifTicks(strokes, capH, top, base)) {
      artist.line([p[0] - capH * 0.09, p[1]], [p[0] + capH * 0.09, p[1]],
        { medium: o.medium, width: w * 0.6, alpha: o.alpha, wobble: 0, grains: 2, taper: [0.2, 0.2] });
    }
  }
}

function drawInscribed(artist, strokes, capH, o) {
  const nib = capH * 0.075 * o.weight;
  const nx = Math.cos(o.nibAngle) * nib, ny = Math.sin(o.nibAngle) * nib;
  const quads = [];
  for (const s of strokes) {
    for (let i = 1; i < s.length; i++) quads.push(nibQuad(s[i - 1], s[i], nx, ny));
  }
  const ys = strokes.flat().map((p) => p[1]);
  const top = Math.min(...ys), base = Math.max(...ys);
  const ticks = o.serifs ? serifTicks(strokes, capH, top, base) : [];
  for (const p of ticks) {
    const sw = capH * 0.13, sh = capH * 0.035;
    const sy = Math.abs(p[1] - top) < Math.abs(p[1] - base) ? p[1] : p[1] - sh * 2;
    quads.push(nibQuad([p[0] - sw, sy + sh], [p[0] + sw, sy + sh], 0, sh));
  }
  if (!quads.length) return;
  const xs = quads.flat().map((p) => p[0]), qy = quads.flat().map((p) => p[1]);
  const bx = Math.min(...xs) - 1, by = Math.min(...qy) - 1;
  const bounds = [bx, by, Math.max(...xs) - bx + 1, Math.max(...qy) - by + 1];
  const pathFn = (c) => {
    for (const q of quads) {
      c.moveTo(q[0][0], q[0][1]);
      for (let i = 1; i < 4; i++) c.lineTo(q[i][0], q[i][1]);
      c.closePath();
    }
  };
  // A soft underlayer so the letter reads as solid at a distance ...
  artist.smudge(pathFn, { alpha: 0.55 * o.alpha, blur: capH * 0.008 });
  // ... then hatched in two directions with a soft pencil.
  const gap = Math.max(0.16, capH * 0.035);
  artist.hatch(pathFn, bounds, { angle: o.nibAngle + 1.35, gap, medium: o.medium, width: gap * 1.2,
    alpha: 0.75 * o.alpha, wobble: 0.03, grains: 2, run: capH * 0.6 });
  artist.hatch(pathFn, bounds, { angle: o.nibAngle + 0.3, gap: gap * 1.4, medium: o.medium,
    width: gap * 0.9, alpha: 0.45 * o.alpha, wobble: 0.03, grains: 2, run: capH * 0.5 });
  // The pen skeleton, lightly, gives the letter a drawn edge.
  for (const s of strokes) {
    artist.stroke(s, { medium: "graphite", width: nib * 0.5, alpha: 0.35, grains: 2, wobble: capH * 0.006 });
  }
}

// Break a string into lines no wider than maxW at this cap height.
export function wrap(str, capH, maxW, opts = {}) {
  const words = str.split(/\s+/);
  const lines = [];
  let cur = "";
  for (const wd of words) {
    const next = cur ? cur + " " + wd : wd;
    if (cur && measure(next, capH, opts) > maxW) { lines.push(cur); cur = wd; } else cur = next;
  }
  if (cur) lines.push(cur);
  return lines;
}
