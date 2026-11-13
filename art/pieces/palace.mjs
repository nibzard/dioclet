// The palace board: Diocletian's palace at Spalato seen from above, drawn
// as an antiquarian survey in graphite and charcoal. The four gates, the
// crossing streets, and the six blocks are the real plan's, simplified
// to the game grid: the Temple of Jupiter stands in block D and the
// emperor's octagonal mausoleum in block E, either side of the cardo, as
// they do in Split. The sea lies to the south.
//
// Every game position comes from art/build/layout.json, which the print
// kit generates from the rules file. Nothing here invents geometry.
import { Sheet } from "../lib/core.mjs";
import { Artist, arcPoints } from "../lib/brush.mjs";
import { text, wrap } from "../lib/letters.mjs";
import * as M from "../lib/motifs.mjs";
import * as A from "../lib/architecture.mjs";
import * as K from "../lib/marks.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...M.W[name], ...extra });

const GATE_LABELS = {
  P0: ["GOLDEN GATE · NORTH"], P1: ["SILVER GATE", "EAST"],
  P2: ["BRONZE GATE · SOUTH"], P3: ["IRON GATE · WEST"],
};

const BLOCK_NAMES = {
  A: "HORREA", B: "CASTRA", C: "FABRICAE", D: "TEMPLVM IOVIS", E: "MAVSOLEVM", F: "PALATIVM",
};

export function renderPalace(layout, { dpi = 200, seed = 300 } = {}) {
  const P = layout.palace;
  const [W0, H0] = P.size_mm;
  const sheet = new Sheet({ widthMm: W0, heightMm: H0, dpi, seed });
  const a = new Artist(sheet, { seed: 1 });
  const [gx, gy, gw, gh] = P.grid_mm;
  const G = { x0: gx, y0: gy, x1: gx + gw, y1: gy + gh };
  const keepOut = [];      // circles where decoration must not go

  // Registration crosses get a white knockout in the kit; keep detail off them.
  for (const [x, y] of P.reg_marks_mm) keepOut.push([x, y, 6]);

  drawFrame(a, P);
  drawSea(a, P, G);
  drawPaving(a, P);
  drawWalls(a, P, G);
  for (const b of P.buildings) drawBlock(a, b, keepOut);
  drawMargins(a, P, G);
  drawTitle(a, P);

  // Play symbols last, each on cleared ground.
  const special = new Set();
  const key = (p) => `${p[0].toFixed(2)},${p[1].toFixed(2)}`;
  for (const p of Object.values(P.gates)) special.add(key(p));
  for (const p of Object.values(P.districts)) special.add(key(p));
  for (const p of P.glory_posts) special.add(key(p));
  special.add(key(P.checkpoint));
  for (const s of P.spaces) if (!special.has(key(s.mm))) K.streetSpace(a, s.mm[0], s.mm[1], 9.2);
  for (const [name, p] of Object.entries(P.districts)) K.treasureEntry(a, p[0], p[1], name, 10.6);
  for (const p of P.glory_posts) K.guardPost(a, p[0], p[1], 9.6);
  for (const p of Object.values(P.gates)) K.gateMark(a, p[0], p[1], 11.4);
  K.peristyle(a, P.checkpoint[0], P.checkpoint[1], 11.2);
  text(a, "PERISTYLE", P.checkpoint[0], P.checkpoint[1] - 12.6, 2.5, { medium: "charcoal", weight: 1.2 });
  drawGateLabels(a, P, G);
  drawKey(a, P, G);

  const out = sheet.compose();
  sheet.release();
  return out;
}

// ---------------------------------------------------------------------------

function drawFrame(a, P) {
  const [x, y, wd, ht] = P.border_mm;
  a.rect(x, y, wd, ht, w("bold", { width: 0.7, overshoot: 0.8 }));
  a.rect(x + 1.6, y + 1.6, wd - 3.2, ht - 3.2, w("fine", { overshoot: 0.5 }));
  // Corner rosettes, small: the frame is a picture mount, not a feature.
  for (const [cx, cy] of [[x, y], [x + wd, y], [x, y + ht], [x + wd, y + ht]]) {
    M.lift(a, (c) => c.arc(cx, cy, 3.4, 0, PI * 2), 1);
    a.circle(cx, cy, 3.0, w("firm"));
    M.star(a, cx, cy, 2.3, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }
}

function drawSea(a, P, G) {
  // The Adriatic below the south front; light enough to print clean.
  const y0 = G.y1 + 9, y1 = P.border_mm[1] + P.border_mm[3] - 2.5;
  const x0 = P.border_mm[0] + 66, x1 = P.border_mm[0] + P.border_mm[2] - 58;
  M.waves(a, x0, y0, x1 - x0, y1 - y0, { density: 0.75 });
}

function drawPaving(a, P) {
  // Flagstones in the street cells, very light: they only show in the
  // narrow gaps between the roundels.
  const c = P.cell_mm;
  for (const s of P.spaces) {
    const [cx, cy] = s.mm;
    const x0 = cx - c / 2, y0 = cy - c / 2;
    for (let r = 0; r < 5; r++) {
      const yy = y0 + r * (c / 5);
      a.line([x0, yy], [x0 + c, yy], w("hair", { alpha: 0.22, bow: 0.05, wobble: 0.05 }));
      const off = (r % 2) * 2.5;
      for (let k = 0; k < 5; k++) {
        const xx = x0 + off + k * 5.1 + a.rng.gauss(0.4);
        if (xx > x0 + c) continue;
        a.line([xx, yy], [xx, yy + c / 5], w("hair", { alpha: 0.2, bow: 0 }));
      }
    }
  }
}

function wallBand(a, x0, y0, x1, y1, horizontal) {
  // Ashlar: courses along the wall, staggered joints, the outer face shaded.
  const pts = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  M.lift(a, M.poly(pts), 1);
  if (horizontal) {
    const n = 3;
    for (let i = 1; i < n; i++) {
      const yy = y0 + (i / n) * (y1 - y0);
      a.line([x0, yy], [x1, yy], w("hair", { alpha: 0.4, bow: 0.05 }));
      for (let xx = x0 + (i % 2) * 2.2; xx < x1; xx += 4.4 + a.rng() * 0.8) {
        a.line([xx, y0 + ((i - 1) / n) * (y1 - y0)], [xx, yy], w("hair", { alpha: 0.35, bow: 0 }));
      }
    }
  } else {
    const n = 3;
    for (let i = 1; i < n; i++) {
      const xx = x0 + (i / n) * (x1 - x0);
      a.line([xx, y0], [xx, y1], w("hair", { alpha: 0.4, bow: 0.05 }));
      for (let yy = y0 + (i % 2) * 2.2; yy < y1; yy += 4.4 + a.rng() * 0.8) {
        a.line([x0 + ((i - 1) / n) * (x1 - x0), yy], [xx, yy], w("hair", { alpha: 0.35, bow: 0 }));
      }
    }
  }
  a.rect(x0, y0, x1 - x0, y1 - y0, w("firm", { overshoot: 0.4 }));
}

function squareTower(a, cx, cy, s) {
  const pts = [[cx - s / 2, cy - s / 2], [cx + s / 2, cy - s / 2], [cx + s / 2, cy + s / 2], [cx - s / 2, cy + s / 2]];
  A.castShadow(a, pts, 1.2);
  // A pyramid roof: four hipped planes, the two away from the light dark.
  const c = [cx, cy];
  const planes = [[pts[0], pts[1], c], [pts[1], pts[2], c], [pts[2], pts[3], c], [pts[3], pts[0], c]];
  const shade = [0.15, 0.55, 0.75, 0.25];
  planes.forEach((pl, i) => {
    const gap = 1.4 - shade[i] * 0.9;
    a.hatch(M.poly(pl), M.bbox(pl, 0), { angle: i % 2 ? 0 : PI / 2, gap, ...M.W.hair, alpha: 0.35 + shade[i] * 0.4, run: s });
    a.line(pl[0], c, w("hair", { bow: 0 }));
  });
  a.polygon(pts, w("firm", { overshoot: 0.3 }));
}

function octTower(a, cx, cy, r) {
  const pts = M.octagonPts(cx, cy, r);
  A.castShadow(a, pts, 1.2);
  pts.forEach((p, i) => {
    const q = pts[(i + 1) % 8];
    const ang = Math.atan2((p[1] + q[1]) / 2 - cy, (p[0] + q[0]) / 2 - cx);
    const dark = Math.max(0, Math.cos(ang - PI / 4));
    if (dark > 0.2) {
      const tri = [p, q, [cx, cy]];
      a.hatch(M.poly(tri), M.bbox(tri, 0), { angle: ang + PI / 2, gap: 1.2 - dark * 0.6, ...M.W.hair, alpha: 0.4 + dark * 0.3, run: r });
    }
    a.line(p, [cx, cy], w("hair", { bow: 0, alpha: 0.4 }));
  });
  a.polygon(pts, w("firm", { overshoot: 0.2 }));
}

function drawWalls(a, P, G) {
  const t = 5.0;                    // wall thickness outside the grid
  wallBand(a, G.x0 - t, G.y0 - t, G.x1 + t, G.y0, true);
  wallBand(a, G.x0 - t, G.y1, G.x1 + t, G.y1 + t, true);
  wallBand(a, G.x0 - t, G.y0, G.x0, G.y1, false);
  wallBand(a, G.x1, G.y0, G.x1 + t, G.y1, false);
  // South front: the arcaded gallery over the sea.
  for (let x = G.x0 + 8; x < G.x1 - 8; x += 6.2) {
    const gx = P.gates.P2[0];
    if (Math.abs(x - gx) < 22) continue;
    M.archway(a, x, G.y1 + t - 0.6, 2.6, 3.4, { dark: 0.45, voussoirs: 5 });
  }
  // Corner towers.
  for (const [cx, cy] of [[G.x0 - 2.5, G.y0 - 2.5], [G.x1 + 2.5, G.y0 - 2.5], [G.x0 - 2.5, G.y1 + 2.5], [G.x1 + 2.5, G.y1 + 2.5]]) {
    squareTower(a, cx, cy, 12);
  }
  // Octagonal towers flank every gate, as at the Golden Gate.
  const gates = P.gates;
  const off = 16.5;
  octTower(a, gates.P0[0] - off, G.y0 - 3.4, 5.0);
  octTower(a, gates.P0[0] + off, G.y0 - 3.4, 5.0);
  octTower(a, gates.P2[0] - off, G.y1 + 3.4, 5.0);
  octTower(a, gates.P2[0] + off, G.y1 + 3.4, 5.0);
  octTower(a, G.x1 + 3.4, gates.P1[1] - off, 5.0);
  octTower(a, G.x1 + 3.4, gates.P1[1] + off, 5.0);
  octTower(a, G.x0 - 3.4, gates.P3[1] - off, 5.0);
  octTower(a, G.x0 - 3.4, gates.P3[1] + off, 5.0);
  // Interval towers along the walls, small, on the outer face.
  const c = P.cell_mm;
  const along = (from, to, fixed, horizontal, out, skip) => {
    for (let v = from + c * 3; v < to - c * 1.5; v += c * 3) {
      if (skip.some((s) => Math.abs(v - s) < 26)) continue;
      if (horizontal) squareTower(a, v, fixed + out * 3.2, 7.5);
      else squareTower(a, fixed + out * 3.2, v, 7.5);
    }
  };
  // The north wall keeps its interval towers clear of the title band.
  along(G.x0, G.x1, G.y0, true, -1, [gates.P0[0], 290]);
  along(G.x0, G.x1, G.y1, true, 1, [gates.P2[0]]);
  along(G.y0, G.y1, G.x0, false, -1, [gates.P3[1]]);
  along(G.y0, G.y1, G.x1, false, 1, [gates.P1[1]]);
}

// ---------------------------------------------------------------------------
// The six blocks. Each is a plan with its own purpose, and a tabula ansata
// carries the district letter.

function drawBlock(a, b, keepOut) {
  const [bx, by, bw, bh] = b.rect;
  const ins = 2.4;
  const x = bx + ins, y = by + ins, s = bw - ins * 2, t = bh - ins * 2;
  // Precinct wall.
  A.castShadow(a, [[x, y], [x + s, y], [x + s, y + t], [x, y + t]], 1.4);
  a.rect(x, y, s, t, w("bold", { width: 0.65, overshoot: 0.6 }));
  a.rect(x + 1.7, y + 1.7, s - 3.4, t - 3.4, w("fine", { overshoot: 0.4 }));
  const ix = x + 3.4, iy = y + 3.4, is = s - 6.8, it = t - 6.8;
  const plaque = PLANS[b.district](a, ix, iy, is, it, keepOut);
  // Plaque with the district letter and the block's Latin name.
  const [px, py] = plaque;
  M.tabula(a, px, py, 36, 28, { depth: 0.6 });
  text(a, b.district, px, py + 5.8, 15, { style: "inscribed", medium: "charcoal" });
  text(a, BLOCK_NAMES[b.district], px, py + 11.4, 2.4, { medium: "graphite", weight: 1.15, track: 0.15 });
}

const PLANS = {
  // Granaries: four long storehouses around a colonnaded yard.
  A(a, x, y, s, t) {
    const d = 22;
    A.hall(a, x + 2, y + 2, s - 4, d, { ridge: "h" });
    A.hall(a, x + 2, y + t - d - 2, s - 4, d, { ridge: "h" });
    A.hall(a, x + 2, y + d + 6, d - 4, t - 2 * d - 12, { ridge: "v" });
    A.hall(a, x + s - d - 2 + 4, y + d + 6, d - 4, t - 2 * d - 12, { ridge: "v" });
    A.court(a, x + d + 4, y + d + 6, s - 2 * d - 8, t - 2 * d - 12, { colonnade: true });
    return [x + s / 2, y + t / 2];
  },
  // Barracks: rows of quarters around a drill yard with a small shrine.
  B(a, x, y, s, t, keepOut) {
    const row = (yy, hh) => {
      const n = 3, gap = 3, wd = (s - 4 - gap * (n - 1)) / n;
      for (let i = 0; i < n; i++) A.hall(a, x + 2 + i * (wd + gap), yy, wd, hh, { ridge: "h" });
    };
    row(y + 2, 15);
    // The drill yard: open ground, two trees, the standard's shrine.
    A.court(a, x + 2, y + 21, s - 4, 34, { colonnade: false, paving: true });
    A.garden(a, x + 4, y + 23, s - 8, 30, 3, [...keepOut, [x + s * 0.5, y + 38, 8]]);
    A.temple(a, x + s * 0.5 - 4.5, y + 30, 9, 13, { front: "s", columns: [3, 4] });
    const left = [x + 2, y + 60, 30, t - 62], right = [x + s - 32, y + 60, 30, t - 62];
    for (const [hx, hy, hw, hh] of [left, right]) {
      A.hall(a, hx, hy, hw, (hh - 3) / 2, { ridge: "h" });
      A.hall(a, hx, hy + (hh + 3) / 2, hw, (hh - 3) / 2, { ridge: "h" });
    }
    return [x + s / 2, y + 60 + (t - 62) / 2];
  },
  // Workshops: small buildings along lanes, a cistern, a few trees.
  C(a, x, y, s, t) {
    const n = 3, gap = 5, cw = (s - 4 - gap * (n - 1)) / n;
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        const cx = x + 2 + i * (cw + gap), cy = y + 2 + j * (cw + gap);
        if (i === 1 && j === 1) continue;
        if ((i + j) % 2 === 0) {
          A.hall(a, cx, cy, cw, cw * 0.45, { ridge: "h" });
          A.hall(a, cx, cy + cw * 0.55, cw * 0.55, cw * 0.45, { ridge: "v" });
          A.dome(a, cx + cw * 0.8, cy + cw * 0.78, cw * 0.14, { ribs: 8 });
        } else {
          A.court(a, cx, cy, cw, cw, { colonnade: false, wall: false, paving: false });
          A.hall(a, cx, cy, cw, cw * 0.32, { ridge: "h" });
          A.hall(a, cx, cy + cw * 0.32, cw * 0.32, cw * 0.68, { ridge: "v" });
          A.garden(a, cx + cw * 0.38, cy + cw * 0.4, cw * 0.58, cw * 0.55, 2);
        }
      }
    }
    return [x + s / 2, y + t / 2];
  },
  // The Temple of Jupiter in its colonnaded precinct, with two round
  // temples beside it.
  D(a, x, y, s, t) {
    A.court(a, x + 2, y + 2, s - 4, t - 4, { colonnade: true, spacing: 3.6 });
    A.temple(a, x + s / 2 - 17, y + 9, 34, 50, { front: "s", columns: [6, 8] });
    A.roundTemple(a, x + 17, y + 30, 9);
    A.roundTemple(a, x + s - 17, y + 30, 9);
    A.garden(a, x + 6, y + 64, s - 12, t - 70, 6, [[x + s / 2, y + t - 26, 22]]);
    return [x + s / 2, y + t - 26];
  },
  // The mausoleum: the octagon in its precinct, a forecourt to the north.
  E(a, x, y, s, t, keepOut) {
    A.court(a, x + 2, y + 2, s - 4, t - 4, { colonnade: true, spacing: 3.6 });
    A.mausoleum(a, x + s / 2, y + 58, 23);
    // Forecourt: two cyprees and the plaque, clear of the octagon.
    M.cypress(a, x + 15, y + 26, 20);
    M.cypress(a, x + s - 15, y + 26, 18);
    return [x + s / 2, y + 17];
  },
  // The imperial apartments: halls with apses, a domed vestibule, and
  // garden courts.
  F(a, x, y, s, t) {
    A.dome(a, x + 16, y + 16, 11, { ribs: 16 });
    A.apseHall(a, x + 34, y + 4, 30, 22, "s");
    A.apseHall(a, x + s - 36, y + 4, 32, 26, "e");
    A.court(a, x + 4, y + 34, 34, 36, { colonnade: true, spacing: 3 });
    A.garden(a, x + 8, y + 38, 26, 28, 3);
    A.hall(a, x + s - 34, y + 36, 30, 32, { ridge: "v" });
    A.hall(a, x + 2, y + t - 16, s - 4, 14, { ridge: "h" });
    return [x + s / 2 + 4, y + t / 2 + 8];
  },
};

// ---------------------------------------------------------------------------

function drawTitle(a, P) {
  const cx = P.size_mm[0] / 2;
  const base = 18.2, cap = 7.6;
  const wdt = text(a, "DIOCLETIAN'S PALACE", cx, base, cap, { style: "inscribed", medium: "charcoal", track: 0.06 });
  // Laurel sprigs either side of the title.
  for (const s of [-1, 1]) {
    const x0 = cx + s * (wdt / 2 + 3);
    M.laurelBranch(a, [[x0, base - cap * 0.4], [x0 + s * 8, base - cap * 0.75], [x0 + s * 16, base - cap * 0.55]],
      { leafLen: 3.0, leafWid: 1.0, pairs: 5, berries: true });
  }
}

function drawGateLabels(a, P, G) {
  const g = P.gates;
  text(a, GATE_LABELS.P0[0], g.P0[0], G.y0 - 9.6, 2.5, { medium: "charcoal", weight: 1.1 });
  text(a, GATE_LABELS.P2[0], g.P2[0], G.y1 + 13.6, 2.5, { medium: "charcoal", weight: 1.1 });
  const ex = (G.x1 + P.border_mm[0] + P.border_mm[2]) / 2 + 1.5;
  text(a, GATE_LABELS.P1[0], ex, g.P1[1] - 12, 2.5, { medium: "charcoal", weight: 1.1 });
  text(a, GATE_LABELS.P1[1], ex, g.P1[1] - 7.5, 2.5, { medium: "charcoal", weight: 1.1 });
  // West: the margin is narrow, so the label runs up the page.
  const wx = P.border_mm[0] + 9.5;
  M.rotated(a, wx, g.P3[1], -PI / 2, () => {
    text(a, GATE_LABELS.P3[0], 0, 1.25, 2.5, { medium: "charcoal", weight: 1.1 });
  });
}

function drawMargins(a, P, G) {
  const right0 = G.x1 + 9, right1 = P.border_mm[0] + P.border_mm[2] - 2;
  const rcx = (right0 + right1) / 2;
  M.compassRose(a, rcx, 56, 15);
  // A single column stands in the east margin, a fragment of the
  // peristyle, with a cypress behind it.
  M.cypress(a, rcx + 9, 156, 44);
  M.column(a, rcx - 3, 92, 62, { shaft: 0.15 });
  // Cypresses along the west margin, away from the label and the marks.
  const lx = P.border_mm[0] + 14;
  for (const [yy, h] of [[96, 30], [128, 24], [296, 30], [330, 26]]) M.cypress(a, lx + a.rng.gauss(1), yy, h);
}

function drawKey(a, P, G) {
  const x0 = G.x1 + 10, x1 = P.border_mm[0] + P.border_mm[2] - 3.5;
  const cx = (x0 + x1) / 2;
  let y = 232;
  text(a, "KEY", cx, y, 4.2, { style: "inscribed", medium: "charcoal" });
  y += 3.5;
  text(a, "THE SUCCESSION · SIX TREASURES", cx, y + 2.2, 1.7, { medium: "graphite" });
  y += 5;
  a.line([x0 + 4, y], [x1 - 4, y], w("fine"));
  y += 7;
  const items = [
    ["space", "STREET SPACE"],
    ["entry", "TREASURE ENTRY (TAKE EQUIPMENT)"],
    ["gate", "GATE / START"],
    ["peri", "PERISTYLE - CLAIM HERE TO OPEN THE SUCCESSION"],
    ["post", "GUARD POST: ROLL 4+ FOR 1 PRESTIGE"],
    ["block", "BUILDING - NO ENTRY"],
    ["none", "FACTION MEETING PLACES LIVE ON THE SUCCESSION MAP"],
  ];
  const iconX = x0 + 5, textX = x0 + 11.5, textW = x1 - textX, cap = 1.9;
  for (const [kind, label] of items) {
    const lines = wrap(label, cap, textW);
    const hh = Math.max(9, lines.length * cap * 1.75 + 2.5);
    const iy = y + hh / 2 - 2;
    const r = 3.6;
    if (kind === "space") K.streetSpace(a, iconX, iy, r);
    if (kind === "entry") K.treasureEntry(a, iconX, iy, "A", r + 0.4);
    if (kind === "gate") K.gateMark(a, iconX, iy, r + 0.5);
    if (kind === "peri") K.peristyle(a, iconX, iy, r + 0.4);
    if (kind === "post") { M.star(a, iconX, iy, r, { points: 8, inner: 0.5, weight: "firm" }); }
    if (kind === "block") {
      const pts = [[iconX - r, iy - r], [iconX + r, iy - r], [iconX + r, iy + r], [iconX - r, iy + r]];
      a.rect(iconX - r, iy - r, 2 * r, 2 * r, w("bold", { width: 0.45 }));
      A.hall(a, iconX - r + 1, iy - r + 1, 2 * r - 2, 2 * r - 2, { shadow: 0 });
      void pts;
    }
    if (kind === "none") K.factionEmblem(a, iconX, iy, 2.8, "officials");
    const ty0 = iy - ((lines.length - 1) * cap * 1.75) / 2 + cap / 2;
    lines.forEach((ln, i) => text(a, ln, textX, ty0 + i * cap * 1.75, cap, { align: "left", medium: "graphite", weight: 1.05 }));
    y += hh + 1.5;
  }
}
