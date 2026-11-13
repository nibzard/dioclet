// The succession map: the second board, where the throne is contested.
// A single A4 landscape page: four city blocks around a crossing, gates
// at the compass points, the Peristyle at the centre, and the three
// faction meeting places on the street arms. Drawn as a companion sheet
// to the palace board: same paper, same pencil box, lighter hand - the
// map is a working chart, not a survey.
import { Sheet } from "../lib/core.mjs";
import { Artist } from "../lib/brush.mjs";
import { text, wrap } from "../lib/letters.mjs";
import * as M from "../lib/motifs.mjs";
import * as A from "../lib/architecture.mjs";
import * as K from "../lib/marks.mjs";

const PI = Math.PI;
const w = (name, extra = {}) => ({ ...M.W[name], ...extra });

const GATE_LABELS = { P0: "GOLDEN GATE", P1: "SILVER GATE", P2: "BRONZE GATE", P3: "IRON GATE" };
const BLOCK_NAMES = { I: "MERCATVS", II: "BALNEAE", III: "TABERNAE", IV: "DOMVS" };
const FACTION_LABELS = { army: "ARMY", officials: "OFFICIALS", elites: "CITY ELITES" };

export function renderSuccession(layout, { dpi = 300, seed = 400 } = {}) {
  const S = layout.succession;
  const [W0, H0] = S.size_mm;
  const sheet = new Sheet({ widthMm: W0, heightMm: H0, dpi, seed });
  const a = new Artist(sheet, { seed: 1 });
  const [gx, gy, gw, gh] = S.grid_mm;
  const G = { x0: gx, y0: gy, x1: gx + gw, y1: gy + gh };

  drawFrame(a, S);
  drawTitle(a, S);
  drawPaving(a, S);
  for (let i = 0; i < S.blocks.length; i++) drawBlock(a, S, i);

  // Play symbols.
  const special = new Set();
  const key = (p) => `${p[0].toFixed(2)},${p[1].toFixed(2)}`;
  for (const p of Object.values(S.gates)) special.add(key(p));
  for (const p of Object.values(S.factions)) special.add(key(p));
  special.add(key(S.checkpoint));
  for (const s of S.spaces) if (!special.has(key(s.mm))) K.streetSpace(a, s.mm[0], s.mm[1], 6.2);
  K.peristyle(a, S.checkpoint[0], S.checkpoint[1], 9.6);
  for (const p of Object.values(S.gates)) K.gateMark(a, p[0], p[1], 8.2);
  for (const [name, p] of Object.entries(S.factions)) {
    K.factionSite(a, p[0], p[1], name, 6.6);
    drawFactionLabel(a, name, p, S);
  }
  text(a, "PERISTYLE", S.checkpoint[0], S.checkpoint[1] + 13.6, 2.6, { medium: "charcoal", weight: 1.15 });
  for (const [pid, p] of Object.entries(S.gates)) drawGateLabel(a, pid, p, S, G);
  drawKey(a, S, G);

  const out = sheet.compose();
  sheet.release();
  return out;
}

function drawFrame(a, S) {
  a.rect(12, 8, 273, 196, w("bold", { width: 0.7, overshoot: 0.8 }));
  a.rect(13.6, 9.6, 269.8, 192.8, w("fine", { overshoot: 0.5 }));
  for (const [cx, cy] of [[12, 8], [285, 8], [12, 204], [285, 204]]) {
    M.lift(a, (c) => c.arc(cx, cy, 3.2, 0, PI * 2), 1);
    a.circle(cx, cy, 2.8, w("firm"));
    M.star(a, cx, cy, 2.1, { points: 8, inner: 0.45, weight: "firm", shade: false });
  }
}

function drawTitle(a, S) {
  const cx = S.size_mm[0] / 2;
  const cap = 6.4;
  const wd = text(a, "THE SUCCESSION MAP", cx, 21.5, cap, { style: "inscribed", medium: "charcoal", track: 0.06 });
  for (const s of [-1, 1]) {
    const x0 = cx + s * (wd / 2 + 3);
    M.laurelBranch(a, [[x0, 19], [x0 + s * 7, 17.4], [x0 + s * 13, 18.6]], { leafLen: 2.6, leafWid: 0.9, pairs: 4 });
  }
  text(a, "DIOCLETIAN'S PALACE · THE CONTEST FOR THE THRONE", cx, 26.8, 1.8, { medium: "graphite", weight: 1.05 });
}

function drawPaving(a, S) {
  const c = S.cell_mm;
  for (const s of S.spaces) {
    const [cx, cy] = s.mm;
    const x0 = cx - c / 2, y0 = cy - c / 2;
    for (let r = 0; r < 3; r++) {
      const yy = y0 + r * (c / 3);
      a.line([x0, yy], [x0 + c, yy], w("hair", { alpha: 0.2, bow: 0.05, wobble: 0.04 }));
      for (let k = 0; k < 3; k++) {
        const xx = x0 + (r % 2) * 2.75 + k * 5.5 + a.rng.gauss(0.4);
        if (xx > x0 + c) continue;
        a.line([xx, yy], [xx, yy + c / 3], w("hair", { alpha: 0.18, bow: 0 }));
      }
    }
  }
}

// Block plans, simpler than the palace's: this is a working map.
const PLANS = [
  // I, north-west: the market - stalls around an open court.
  (a, x, y, s, t) => {
    A.court(a, x + 2, y + 2, s - 4, t - 4, { colonnade: false });
    const n = 3, gap = 3, wd = (s - 10 - gap * (n - 1)) / n;
    for (let i = 0; i < n; i++) {
      A.hall(a, x + 5 + i * (wd + gap), y + 5, wd, (t - 14) * 0.32, { ridge: "h" });
      A.hall(a, x + 5 + i * (wd + gap), y + t - 5 - (t - 14) * 0.32, wd, (t - 14) * 0.32, { ridge: "h" });
    }
    A.garden(a, x + 6, y + t * 0.42, s - 12, t * 0.16, 2);
    return [x + s / 2, y + t / 2];
  },
  // II, north-east: the baths - a great hall, a round hot room, a plunge.
  (a, x, y, s, t) => {
    A.hall(a, x + 4, y + 4, s * 0.52, t - 8, { ridge: "v" });
    A.dome(a, x + s * 0.78, y + t * 0.32, Math.min(s, t) * 0.17, { ribs: 12 });
    M.waves(a, x + s * 0.62, y + t * 0.62, s * 0.3, t * 0.28, { density: 1 });
    a.rect(x + s * 0.62, y + t * 0.62, s * 0.3, t * 0.28, w("fine", { overshoot: 0.3 }));
    return [x + s / 2, y + t / 2];
  },
  // III, south-east: the shops - a row of tabernae on the street.
  (a, x, y, s, t) => {
    const n = 4, gap = 2.5, wd = (s - 8 - gap * (n - 1)) / n;
    for (let i = 0; i < n; i++) A.hall(a, x + 4 + i * (wd + gap), y + 4, wd, t * 0.4, { ridge: "h" });
    A.court(a, x + 4, y + t * 0.52, s - 8, t * 0.4, { colonnade: false });
    A.garden(a, x + 8, y + t * 0.58, s - 16, t * 0.28, 3);
    return [x + s / 2, y + t / 2];
  },
  // IV, south-west: the town house - atrium, garden, dining room.
  (a, x, y, s, t) => {
    A.court(a, x + 4, y + 4, s * 0.44, t - 8, { colonnade: true, spacing: 3.4 });
    A.garden(a, x + 7, y + 8, s * 0.38, t * 0.5, 3);
    A.apseHall(a, x + s * 0.56, y + 4, s * 0.36, t * 0.5, "s");
    A.hall(a, x + s * 0.56, y + t * 0.62, s * 0.36, t * 0.3, { ridge: "h" });
    return [x + s / 2, y + t / 2];
  },
];

function drawBlock(a, S, index) {
  const [bx, by, bw, bh] = S.blocks[index];
  const ins = 1.6;
  const x = bx + ins, y = by + ins, s = bw - ins * 2, t = bh - ins * 2;
  const pts = [[x, y], [x + s, y], [x + s, y + t], [x, y + t]];
  A.castShadow(a, pts, 1.2);
  a.rect(x, y, s, t, w("bold", { width: 0.6, overshoot: 0.5 }));
  a.rect(x + 1.4, y + 1.4, s - 2.8, t - 2.8, w("hair", { overshoot: 0.35 }));
  const numeral = ["I", "II", "III", "IV"][index];
  const [px, py] = PLANS[index](a, x + 2.8, y + 2.8, s - 5.6, t - 5.6);
  M.tabula(a, px, py, 30, 22, { depth: 0.5 });
  text(a, numeral, px, py + 4.6, 11, { style: "inscribed", medium: "charcoal" });
  text(a, BLOCK_NAMES[numeral], px, py + 8.8, 2.0, { medium: "graphite", weight: 1.1, track: 0.15 });
}

function drawStreetNames(a, S, G) {
  // CARD O / DECVMANVS along the arms, tiny, in the margin.
  text(a, "CARDO", G.x0 - 8, S.checkpoint[1] + 12.5, 1.9, { medium: "graphite", weight: 1.05 });
  M.rotated(a, G.x1 + 9.5, S.checkpoint[1] - 12.5, -PI / 2, () => {
    text(a, "CARDO", 0, 1.25, 1.9, { medium: "graphite", weight: 1.05 });
  });
  M.rotated(a, S.checkpoint[0] - 12.5, G.y0 - 7.5, 0, () => {
    text(a, "DECVMANVS", 0, 1.25, 1.9, { medium: "graphite", weight: 1.05, align: "center" });
  });
  M.rotated(a, S.checkpoint[0] + 12.5, G.y1 + 9.5, 0, () => {
    text(a, "DECVMANVS", 0, 1.25, 1.9, { medium: "graphite", weight: 1.05, align: "center" });
  });
}

function drawGateLabel(a, pid, p, S, G) {
  const cap = 2.3;
  if (pid === "P0") text(a, GATE_LABELS.P0, p[0], G.y0 - 3.2, cap, { medium: "charcoal", weight: 1.1 });
  if (pid === "P2") text(a, GATE_LABELS.P2, p[0], G.y1 + 3.8, cap, { medium: "charcoal", weight: 1.1 });
  if (pid === "P1") M.rotated(a, G.x1 + 6.5, p[1] - 7.5, -PI / 2, () => {
    text(a, GATE_LABELS.P1, 0, 1.5, cap, { medium: "charcoal", weight: 1.1 });
  });
  if (pid === "P3") M.rotated(a, G.x0 - 6.5, p[1] + 7.5, PI / 2, () => {
    text(a, GATE_LABELS.P3, 0, 1.5, cap, { medium: "charcoal", weight: 1.1 });
  });
}

function drawFactionLabel(a, name, p, S) {
  const cap = 2.2;
  const label = FACTION_LABELS[name];
  const plate = (x, y, wd) => M.lift(a, (c) => {
    c.moveTo(x - wd / 2, y - cap - 1);
    c.lineTo(x + wd / 2, y - cap - 1);
    c.lineTo(x + wd / 2 + 1.2, y - cap / 2);
    c.lineTo(x + wd / 2, y + 1.2);
    c.lineTo(x - wd / 2, y + 1.2);
    c.lineTo(x - wd / 2 - 1.2, y - cap / 2);
    c.closePath();
  }, 0.95);
  if (name === "elites") {
    // Right of the circle, over the corner of block II.
    plate(p[0] + 11, p[1] + 0.8, 15);
    text(a, label, p[0] + 11, p[1] + 0.8, cap, { align: "left", medium: "charcoal", weight: 1.1 });
  } else if (name === "army") {
    plate(p[0], p[1] + 12.5, 10);
    text(a, label, p[0], p[1] + 12.5, cap, { medium: "charcoal", weight: 1.1 });
  } else {
    plate(p[0], p[1] + 12.5, 15);
    text(a, label, p[0], p[1] + 12.5, cap, { medium: "charcoal", weight: 1.1 });
  }
}

function drawKey(a, S, G) {
  const y0 = G.y1 + 11.5;
  a.line([16, y0 - 2.0], [281, y0 - 2.0], w("fine"));
  const items = [
    ["gate", "GATE - RETURN HERE WHEN THE MAP OPENS"],
    ["faction", "FACTION MEETING PLACE - 1 PRESTIGE FOR SUPPORT"],
    ["peri", "PERISTYLE - PROCLAIM THE CLAIM HERE"],
    ["space", "STREET SPACE - DUEL WINS PAY 1 PRESTIGE HERE"],
    ["block", "BUILDING - NO ENTRY"],
  ];
  // Two rows: three entries, then two, laid out on a shared centre line.
  const rows = [[items[0], items[1], items[2]], [items[3], items[4]]];
  let y = y0 + 3.8;
  for (const row of rows) {
    row.forEach(([kind, label], i) => {
      const iconX = row.length === 3 ? [58, 148.5, 239][i] : (i === 0 ? 100 : 197);
      if (kind === "gate") K.gateMark(a, iconX, y, 3.2);
      if (kind === "faction") K.factionSite(a, iconX, y, "officials", 3.2);
      if (kind === "peri") K.peristyle(a, iconX, y, 3.2);
      if (kind === "space") K.streetSpace(a, iconX, y, 3.0);
      if (kind === "block") {
        a.rect(iconX - 3.2, y - 3.2, 6.4, 6.4, w("bold", { width: 0.4 }));
        A.hall(a, iconX - 2.3, y - 2.3, 4.6, 4.6, { shadow: 0 });
      }
      const lines = wrap(label, 1.8, 92);
      const ty0 = y - ((lines.length - 1) * 1.8 * 1.7) / 2 + 0.9;
      lines.forEach((ln, j) => text(a, ln, iconX + 5.2, ty0 + j * 1.8 * 1.7, 1.8, { align: "left", medium: "graphite", weight: 1.05 }));
    });
    y += 8.2;
  }
}
