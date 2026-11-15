// The succession map: the second board, where the throne is contested.
// It has the palace board's footprint and prints on the same four tiles,
// so a family can tape the two boards back to back. Six city quarters
// stand around the Peristyle; the gates sit pinwheel-fashion, each nine
// steps from the Peristyle; six roundels hold the face-down faction cards,
// one for each quarter.
// Drawn as the palace board's companion: same paper, same pencil box,
// same walls and margins, a busier town inside.
//
// Every game position comes from art/build/layout.json, which the print
// kit generates from the rules file. Nothing here invents geometry.
import { Sheet } from "../lib/core.mjs";
import { Artist } from "../lib/brush.mjs";
import { text, wrap } from "../lib/letters.mjs";
import * as M from "../lib/motifs.mjs";
import * as A from "../lib/architecture.mjs";
import * as K from "../lib/marks.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...M.W[name], ...extra });

const GATE_LABELS = {
  P0: ["GOLDEN GATE", "NORTH"], P1: ["SILVER GATE", "EAST"],
  P2: ["BRONZE GATE · SOUTH"], P3: ["IRON GATE · WEST"],
};
// Blocks in layout order: the north row west to east, then the south row.
const QUARTERS = [
  { numeral: "I", name: "MERCATVS", theme: "market" },
  { numeral: "II", name: "HORREA", theme: "granaries" },
  { numeral: "III", name: "BALNEAE", theme: "baths" },
  { numeral: "IV", name: "TABERNAE", theme: "shops" },
  { numeral: "V", name: "FANVM", theme: "temple" },
  { numeral: "VI", name: "DOMVS", theme: "houses" },
];
const PLAQUE = [32, 24];

export function renderSuccession(layout, { dpi = 200, seed = 400 } = {}) {
  const S = layout.succession;
  const [W0, H0] = S.size_mm;
  const sheet = new Sheet({ widthMm: W0, heightMm: H0, dpi, seed });
  const a = new Artist(sheet, { seed: 1 });
  const [gx, gy, gw, gh] = S.grid_mm;
  const G = { x0: gx, y0: gy, x1: gx + gw, y1: gy + gh };
  // Registration crosses get a white knockout in the kit; keep detail off them.
  const keepOut = S.reg_marks_mm.map(([x, y]) => [x, y, 7]);

  drawFrame(a, S);
  drawSea(a, S, G);
  drawPaving(a, S);
  drawWalls(a, S, G);
  S.blocks.forEach((rect, i) => drawQuarter(a, rect, QUARTERS[i], keepOut, S.cut_mm.x,
    S.card_doors.filter((d) => d.block === i)));
  drawMargins(a, S, G);
  drawTitle(a, S);

  // Play symbols last, each on cleared ground.
  const special = new Set();
  const key = (p) => `${p[0].toFixed(2)},${p[1].toFixed(2)}`;
  for (const p of Object.values(S.gates)) special.add(key(p));
  for (const p of S.card_spaces) special.add(key(p));
  for (const p of S.glory_posts) special.add(key(p));
  special.add(key(S.checkpoint));
  for (const s of S.spaces) if (!special.has(key(s.mm))) K.streetSpace(a, s.mm[0], s.mm[1], 9.2);
  for (const p of S.card_spaces) K.cardSpace(a, p[0], p[1], 10.6);
  for (const p of S.glory_posts) K.guardPost(a, p[0], p[1], 9.6);
  for (const p of Object.values(S.gates)) K.gateMark(a, p[0], p[1], 11.4);
  K.peristyle(a, S.checkpoint[0], S.checkpoint[1], 11.2);
  text(a, "PERISTYLE", S.checkpoint[0], S.checkpoint[1] - 12.6, 2.5, { medium: "charcoal", weight: 1.2 });
  drawGateLabels(a, S, G);
  drawKey(a, S, G);

  const out = sheet.compose();
  sheet.release();
  return out;
}

// ---------------------------------------------------------------------------
// Frame, sea, paving and walls: the palace board's, so both sides match.

function drawFrame(a, S) {
  const [x, y, wd, ht] = S.border_mm;
  a.rect(x, y, wd, ht, w("bold", { width: 0.7, overshoot: 0.8 }));
  a.rect(x + 1.6, y + 1.6, wd - 3.2, ht - 3.2, w("fine", { overshoot: 0.5 }));
  for (const [cx, cy] of [[x, y], [x + wd, y], [x, y + ht], [x + wd, y + ht]]) {
    M.lift(a, (c) => c.arc(cx, cy, 3.4, 0, PI * 2), 1);
    a.circle(cx, cy, 3.0, w("firm"));
    M.star(a, cx, cy, 2.3, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }
}

function drawSea(a, S, G) {
  const y0 = G.y1 + 9, y1 = S.border_mm[1] + S.border_mm[3] - 2.5;
  const x0 = S.border_mm[0] + 66, x1 = S.border_mm[0] + S.border_mm[2] - 58;
  M.waves(a, x0, y0, x1 - x0, y1 - y0, { density: 0.75 });
}

function drawPaving(a, S) {
  const c = S.cell_mm;
  for (const s of S.spaces) {
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
  const pts = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
  M.lift(a, M.poly(pts), 1);
  const n = 3;
  for (let i = 1; i < n; i++) {
    if (horizontal) {
      const yy = y0 + (i / n) * (y1 - y0);
      a.line([x0, yy], [x1, yy], w("hair", { alpha: 0.4, bow: 0.05 }));
      for (let xx = x0 + (i % 2) * 2.2; xx < x1; xx += 4.4 + a.rng() * 0.8) {
        a.line([xx, y0 + ((i - 1) / n) * (y1 - y0)], [xx, yy], w("hair", { alpha: 0.35, bow: 0 }));
      }
    } else {
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

function drawWalls(a, S, G) {
  const t = 5.0;
  wallBand(a, G.x0 - t, G.y0 - t, G.x1 + t, G.y0, true);
  wallBand(a, G.x0 - t, G.y1, G.x1 + t, G.y1 + t, true);
  wallBand(a, G.x0 - t, G.y0, G.x0, G.y1, false);
  wallBand(a, G.x1, G.y0, G.x1 + t, G.y1, false);
  for (const [cx, cy] of [[G.x0 - 2.5, G.y0 - 2.5], [G.x1 + 2.5, G.y0 - 2.5], [G.x0 - 2.5, G.y1 + 2.5], [G.x1 + 2.5, G.y1 + 2.5]]) {
    squareTower(a, cx, cy, 12);
  }
  // Square towers flank each gate; the town's gates are plainer than
  // the palace's octagons.
  const g = S.gates, off = 16.5;
  squareTower(a, g.P0[0] - off, G.y0 - 3.2, 8);
  squareTower(a, g.P0[0] + off, G.y0 - 3.2, 8);
  squareTower(a, g.P2[0] - off, G.y1 + 3.2, 8);
  squareTower(a, g.P2[0] + off, G.y1 + 3.2, 8);
  squareTower(a, G.x1 + 3.2, g.P1[1] - off, 8);
  squareTower(a, G.x1 + 3.2, g.P1[1] + off, 8);
  squareTower(a, G.x0 - 3.2, g.P3[1] - off, 8);
  squareTower(a, G.x0 - 3.2, g.P3[1] + off, 8);
}

// ---------------------------------------------------------------------------
// The six quarters. Each is a grid of lots around a court that carries
// the plaque. A lot that would touch a registration cross stays open
// ground with a few trees, so the crosses print on clean paper. The
// middle quarters straddle the vertical tile cut, so their court moves
// to the west lots and the plaque stays on one sheet.

function drawQuarter(a, rect, q, keepOut, cutX, doors) {
  const [bx, by, bw, bh] = rect;
  const ins = 2.4;
  const x = bx + ins, y = by + ins, s = bw - ins * 2, t = bh - ins * 2;
  A.castShadow(a, [[x, y], [x + s, y], [x + s, y + t], [x, y + t]], 1.4);
  a.rect(x, y, s, t, w("bold", { width: 0.65, overshoot: 0.6 }));
  a.rect(x + 1.7, y + 1.7, s - 3.4, t - 3.4, w("fine", { overshoot: 0.4 }));

  const ix = x + 4, iy = y + 4, is = s - 8, it = t - 8;
  const cols = s > t * 1.3 ? 6 : 4, rows = 3, lane = 4;
  const lw = (is - lane * (cols - 1)) / cols, lh = (it - lane * (rows - 1)) / rows;
  const lot = (i, j) => [ix + i * (lw + lane), iy + j * (lh + lane)];
  const hits = (x0, y0, x1, y1) => keepOut.some(([kx, ky, kr]) =>
    kx + kr > x0 && kx - kr < x1 && ky + kr > y0 && ky - kr < y1);

  // The court spans two lots of the middle row: the middle two, or the
  // two west lots when the block straddles the cut.
  const ci = x < cutX && cutX < x + s ? 0 : cols / 2 - 1;
  const [cx0, cy0] = lot(ci, 1);
  const cw = lw * 2 + lane;
  const px = cx0 + cw / 2, py = cy0 + lh / 2;
  const box = M.tabulaBounds(px, py, PLAQUE[0], PLAQUE[1]);
  const LOTS = THEMES[q.theme];
  for (let j = 0; j < rows; j++) {
    for (let i = 0; i < cols; i++) {
      if (j === 1 && (i === ci || i === ci + 1)) continue;
      const [lx, ly] = lot(i, j);
      if (hits(lx, ly, lx + lw, ly + lh)) {
        A.garden(a, lx, ly, lw, lh, 3, keepOut);
        continue;
      }
      LOTS.lot(a, lx, ly, lw, lh, i, j);
    }
  }
  LOTS.court(a, cx0, cy0, cw, lh, [box]);
  // The door: the wall opens toward this quarter's faction card space.
  for (const d of doors) drawDoor(a, d.card[0], d.side === "north" ? y : y + t, d.side);
  M.tabula(a, px, py, PLAQUE[0], PLAQUE[1], { depth: 0.6 });
  text(a, q.numeral, px, py + 5, 13, { style: "inscribed", medium: "charcoal" });
  text(a, q.name, px, py + 9.6, 2.2, { medium: "graphite", weight: 1.15, track: 0.15 });
}

// A doorway in a quarter wall at (x, wy), drawn as if the card sits
// north of the wall (negative y); a south door is turned half a circle.
function drawDoor(a, x, wy, side, k = 1) {
  M.rotated(a, x, wy, side === "north" ? 0 : PI, () => {
    const pier = (x0) => {
      const pts = [[x0, 0], [x0 + 1.8 * k, 0], [x0 + 1.8 * k, 6.2 * k], [x0, 6.2 * k]];
      a.polygon(pts, w("firm", { overshoot: 0.15 }));
      a.hatch(M.poly(pts), M.bbox(pts), { angle: PI / 4, gap: 0.45, ...M.W.hair, alpha: 0.7 });
    };
    M.lift(a, (c) => c.rect(-6.8 * k, -0.9 * k, 13.6 * k, 7.8 * k), 1);
    pier(-6.8 * k);
    pier(5.0 * k);
    M.archway(a, 0, 6.0 * k, 6.2 * k, 6.4 * k, { dark: 0.4, voussoirs: 7 });
    a.line([-5.0 * k, 0], [5.0 * k, 0], w("fine", { bow: 0 }));
  });
}

const THEMES = {
  // The market: long stall halls in pairs, a colonnaded forum.
  market: {
    lot(a, x, y, wd, ht, i, j) {
      if ((i + j) % 3 === 2) {
        A.court(a, x, y, wd, ht, { colonnade: false, wall: true, paving: true });
        A.hall(a, x, y, wd, ht * 0.3, { ridge: "h" });
        return;
      }
      A.hall(a, x, y, wd, ht * 0.42, { ridge: "h" });
      A.hall(a, x, y + ht * 0.58, wd, ht * 0.42, { ridge: "h" });
    },
    court(a, x, y, wd, ht, keep) {
      A.court(a, x, y, wd, ht, { colonnade: true, spacing: 3.4 });
      A.garden(a, x + 3, y + 3, wd - 6, ht - 6, 2, keep);
    },
  },
  // The baths: domed hot rooms, plunge pools, a palaestra in the middle.
  baths: {
    lot(a, x, y, wd, ht, i, j) {
      const k = (i * 2 + j) % 3;
      if (k === 0) {
        A.hall(a, x, y, wd, ht, { ridge: "v" });
        A.dome(a, x + wd / 2, y + ht / 2, Math.min(wd, ht) * 0.3, { ribs: 12 });
      } else if (k === 1) {
        M.waves(a, x + 2, y + 2, wd - 4, ht - 4, { density: 1 });
        a.rect(x, y, wd, ht, w("firm", { overshoot: 0.3 }));
        a.rect(x + 1.5, y + 1.5, wd - 3, ht - 3, w("hair", { overshoot: 0.2 }));
      } else {
        A.apseHall(a, x, y, wd, ht, j === 0 ? "s" : "n");
      }
    },
    court(a, x, y, wd, ht, keep) {
      A.court(a, x, y, wd, ht, { colonnade: true, spacing: 3.0 });
      A.garden(a, x + 3, y + 3, wd - 6, ht - 6, 2, keep);
    },
  },
  // The shops: rows of tabernae along each lot, a yard behind them.
  shops: {
    lot(a, x, y, wd, ht, i, j) {
      const n = 3, gap = 1.8, sw = (wd - gap * (n - 1)) / n;
      const front = j === 2 ? y + ht * 0.55 : y;
      for (let k = 0; k < n; k++) A.hall(a, x + k * (sw + gap), front, sw, ht * 0.45, { ridge: "h" });
      const yard = j === 2 ? y : y + ht * 0.5;
      A.court(a, x, yard, wd, ht * 0.45, { colonnade: false, wall: true, paving: true });
      if ((i + j) % 2 === 0) A.garden(a, x + 2, yard + 2, wd - 4, ht * 0.45 - 4, 2);
    },
    court(a, x, y, wd, ht, keep) {
      A.court(a, x, y, wd, ht, { colonnade: false, paving: true });
      A.garden(a, x + 3, y + 3, wd - 6, ht - 6, 3, keep);
    },
  },
  // The granaries: long buttressed store halls, a loading yard.
  granaries: {
    lot(a, x, y, wd, ht, i, j) {
      if ((i + j) % 4 === 3) {
        A.court(a, x, y, wd, ht, { colonnade: false, wall: true, paving: true });
        return;
      }
      A.hall(a, x, y, wd * 0.46, ht, { ridge: "v" });
      A.hall(a, x + wd * 0.54, y, wd * 0.46, ht, { ridge: "v" });
    },
    court(a, x, y, wd, ht, keep) {
      A.court(a, x, y, wd, ht, { colonnade: false, paving: true });
      A.garden(a, x + 3, y + 3, wd - 6, ht - 6, 2, keep);
    },
  },
  // The sanctuary: small temples in walled precincts, a sacred grove.
  temple: {
    lot(a, x, y, wd, ht, i, j) {
      if ((i + j) % 2 === 0) {
        A.court(a, x, y, wd, ht, { colonnade: true, spacing: 3.0 });
        A.temple(a, x + wd * 0.2, y + ht * 0.15, wd * 0.6, ht * 0.7, { front: j === 0 ? "s" : "n", columns: [4, 6] });
      } else {
        A.court(a, x, y, wd, ht, { colonnade: false, wall: true, paving: false });
        A.garden(a, x + 2, y + 2, wd - 4, ht - 4, 4);
      }
    },
    court(a, x, y, wd, ht, keep) {
      A.court(a, x, y, wd, ht, { colonnade: true, spacing: 3.2 });
      A.garden(a, x + 3, y + 3, wd - 6, ht - 6, 2, keep);
    },
  },
  // The houses: atrium houses, each a court with rooms on two sides.
  houses: {
    lot(a, x, y, wd, ht, i, j) {
      A.court(a, x, y, wd, ht, { colonnade: (i + j) % 2 === 1, spacing: 3.2 });
      A.hall(a, x, y, wd, ht * 0.28, { ridge: "h" });
      const side = i % 2 === 0 ? x : x + wd * 0.7;
      A.hall(a, side, y + ht * 0.28, wd * 0.3, ht * 0.72, { ridge: "v" });
      const gx = i % 2 === 0 ? x + wd * 0.32 : x + 1.5;
      A.garden(a, gx, y + ht * 0.32, wd * 0.66, ht * 0.64, 2);
    },
    court(a, x, y, wd, ht, keep) {
      A.court(a, x, y, wd, ht, { colonnade: true, spacing: 3.6 });
      A.garden(a, x + 3, y + 3, wd - 6, ht - 6, 3, keep);
    },
  },
};

// ---------------------------------------------------------------------------

function drawTitle(a, S) {
  const cx = S.size_mm[0] / 2;
  // Slightly smaller than the palace title, with short sprigs: the north
  // gate's label stands just west of the title on this map.
  const base = 18.2, cap = 7.0;
  const wdt = text(a, "THE SUCCESSION MAP", cx, base, cap, { style: "inscribed", medium: "charcoal", track: 0.06 });
  for (const s of [-1, 1]) {
    const x0 = cx + s * (wdt / 2 + 2.5);
    M.laurelBranch(a, [[x0, base - cap * 0.4], [x0 + s * 4.5, base - cap * 0.75], [x0 + s * 8, base - cap * 0.55]],
      { leafLen: 2.6, leafWid: 0.9, pairs: 4, berries: true });
  }
}

function drawGateLabels(a, S, G) {
  const g = S.gates;
  text(a, GATE_LABELS.P0[0], g.P0[0], G.y0 - 12.4, 2.5, { medium: "charcoal", weight: 1.1 });
  text(a, GATE_LABELS.P0[1], g.P0[0], G.y0 - 8.4, 2.5, { medium: "charcoal", weight: 1.1 });
  text(a, GATE_LABELS.P2[0], g.P2[0], G.y1 + 13.6, 2.5, { medium: "charcoal", weight: 1.1 });
  const ex = (G.x1 + S.border_mm[0] + S.border_mm[2]) / 2 + 1.5;
  text(a, GATE_LABELS.P1[0], ex, g.P1[1] - 12, 2.5, { medium: "charcoal", weight: 1.1 });
  text(a, GATE_LABELS.P1[1], ex, g.P1[1] - 7.5, 2.5, { medium: "charcoal", weight: 1.1 });
  const wx = S.border_mm[0] + 9.5;
  M.rotated(a, wx, g.P3[1], -PI / 2, () => {
    text(a, GATE_LABELS.P3[0], 0, 1.25, 2.5, { medium: "charcoal", weight: 1.1 });
  });
}

function drawMargins(a, S, G) {
  const right0 = G.x1 + 9, right1 = S.border_mm[0] + S.border_mm[2] - 2;
  const rcx = (right0 + right1) / 2;
  M.compassRose(a, rcx, 56, 15);
  M.cypress(a, rcx + 9, 156, 44);
  M.column(a, rcx - 3, 92, 62, { shaft: 0.15 });
  const lx = S.border_mm[0] + 14;
  for (const [yy, h] of [[96, 30], [128, 24], [296, 30], [330, 26]]) M.cypress(a, lx + a.rng.gauss(1), yy, h);
}

function drawKey(a, S, G) {
  const x0 = G.x1 + 10, x1 = S.border_mm[0] + S.border_mm[2] - 3.5;
  const cx = (x0 + x1) / 2;
  let y = 232;
  text(a, "KEY", cx, y, 4.2, { style: "inscribed", medium: "charcoal" });
  y += 3.5;
  text(a, "THE CONTEST FOR THE THRONE", cx, y + 2.2, 1.7, { medium: "graphite" });
  y += 5;
  a.line([x0 + 4, y], [x1 - 4, y], w("fine"));
  y += 7;
  const items = [
    ["space", "STREET SPACE"],
    ["card", "FACTION CARD SPACE: SEARCH, THEN 1 PRESTIGE FOR SUPPORT"],
    ["gate", "GATE - RETURN HERE WHEN THE MAP OPENS"],
    ["peri", "PERISTYLE - PROCLAIM HERE"],
    ["block", "BUILDING - NO ENTRY"],
    ["door", "DOOR: THE QUARTER A CARD SPACE OPENS"],
    ["post", "GUARD POST: ROLL 4+ FOR 1 PRESTIGE"],
  ];
  const iconX = x0 + 5, textX = x0 + 11.5, textW = x1 - textX, cap = 1.9;
  for (const [kind, label] of items) {
    const lines = wrap(label, cap, textW);
    const hh = Math.max(9, lines.length * cap * 1.75 + 2.5);
    const iy = y + hh / 2 - 2;
    const r = 3.6;
    if (kind === "space") K.streetSpace(a, iconX, iy, r);
    if (kind === "card") K.cardSpace(a, iconX, iy, r + 0.4);
    if (kind === "gate") K.gateMark(a, iconX, iy, r + 0.5);
    if (kind === "peri") K.peristyle(a, iconX, iy, r + 0.4);
    if (kind === "block") {
      a.rect(iconX - r, iy - r, 2 * r, 2 * r, w("bold", { width: 0.45 }));
      A.hall(a, iconX - r + 1, iy - r + 1, 2 * r - 2, 2 * r - 2, { shadow: 0 });
    }
    if (kind === "door") {
      a.line([iconX - 4, iy - 1.6], [iconX + 4, iy - 1.6], w("bold", { width: 0.45 }));
      drawDoor(a, iconX, iy - 1.6, "north", 0.5);
    }
    if (kind === "post") M.star(a, iconX, iy, r, { points: 8, inner: 0.5, weight: "firm" });
    const ty0 = iy - ((lines.length - 1) * cap * 1.75) / 2 + cap / 2;
    lines.forEach((ln, i) => text(a, ln, textX, ty0 + i * cap * 1.75, cap, { align: "left", medium: "graphite", weight: 1.05 }));
    y += hh + 1.5;
  }
}
